"""Cargo catalog and job generation.

Jobs are generated at a city's freight locations, pay by real route miles,
and gate special cargo behind license endorsements earned through the
career system.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ..data.world import (
    FACILITY_CARGO_ROLES,
    LOCATION_TYPE_LABELS,
    Location,
    Route,
    World,
)
from ..sim.trip_models import (
    DESTINATION_APPROACH_LIMIT_MPH,
    DESTINATION_APPROACH_ZONE_MI,
    FACILITY_ACCESS_LIMIT_MPH,
    FACILITY_GATE_LIMIT_MPH,
    FACILITY_GATE_ZONE_MI,
    URBAN_LIMIT_MPH,
    URBAN_RADIUS_MI,
    _leg_speed_limit_at,
    corridor_speed_limit,
)
from .business_constants import DIRECT_FREIGHT_PAY_MULT
from .market import Market, market_condition
from .start_options import DEFAULT_START_KEY, start_option
from .trailers import equipment_text_for_cargo, required_program_text, trailer_keys_for_cargo


@dataclass(frozen=True)
class CargoType:
    key: str
    label: str
    rate_per_mile: float  # base $ per mile
    weight_tons: tuple[float, float]
    endorsement: str | None  # required license endorsement, if any
    fragile: bool = False
    min_level: int = 1
    equipment: str = ""

    @property
    def equipment_text(self) -> str:
        return self.equipment or equipment_text_for_cargo(self.key)


CARGO_CATALOG: dict[str, CargoType] = {
    "general": CargoType("general", "general freight", 2.10, (8, 20), None),
    "retail": CargoType("retail", "retail goods", 2.25, (6, 16), None),
    "parcel": CargoType("parcel", "parcel freight", 2.55, (4, 12), None),
    "container": CargoType("container", "shipping containers", 2.40, (12, 24), None),
    "bulk": CargoType("bulk", "bulk materials", 2.30, (15, 25), None),
    "grain": CargoType("grain", "grain", 2.20, (18, 25), None),
    "farm_inputs": CargoType("farm_inputs", "farm inputs", 2.35, (10, 22), None),
    "construction": CargoType("construction", "construction materials", 2.35, (14, 25), None),
    "lumber_paper": CargoType(
        "lumber_paper", "lumber and paper products", 2.45, (10, 24), None, min_level=2
    ),
    "automotive": CargoType(
        "automotive", "automotive parts", 2.75, (8, 20), None, fragile=True, min_level=2
    ),
    "machinery": CargoType(
        "machinery", "heavy machinery", 2.90, (15, 25), "heavy_haul", fragile=True
    ),
    "steel": CargoType("steel", "steel products", 2.85, (16, 25), "heavy_haul", min_level=3),
    "food": CargoType("food", "fresh food", 2.60, (8, 18), "refrigerated", fragile=True),
    "refrigerated": CargoType(
        "refrigerated", "refrigerated goods", 2.85, (8, 18), "refrigerated", fragile=True
    ),
    "chemicals": CargoType(
        "chemicals", "packaged industrial chemicals", 3.05, (10, 22), "high_value", min_level=4
    ),
    "electronics": CargoType(
        "electronics", "electronics", 3.30, (4, 12), "high_value", fragile=True
    ),
}

ENDORSEMENT_LABELS = {
    None: "standard CDL",
    "refrigerated": "refrigerated endorsement",
    "heavy_haul": "heavy-haul endorsement",
    "high_value": "high-value endorsement",
}

FACILITY_CARGO: dict[str, set[str]] = {
    facility_type: set(roles.get("ships", ())) | set(roles.get("receives", ()))
    for facility_type, roles in FACILITY_CARGO_ROLES.items()
}

MARKET_TAG_CARGO_BONUS = {
    "agriculture": {"grain", "food", "refrigerated", "farm_inputs", "bulk"},
    "air": {"electronics", "parcel", "general"},
    "automotive": {"automotive", "steel", "machinery", "electronics"},
    "border": {"retail", "container", "general", "parcel"},
    "chemical": {"chemicals", "bulk"},
    "cold_chain": {"food", "refrigerated"},
    "construction": {"construction", "bulk", "steel", "lumber_paper"},
    "energy": {"chemicals", "bulk"},
    "food": {"food", "refrigerated", "grain"},
    "industrial": {"steel", "machinery", "bulk", "construction"},
    "intermodal": {"container", "general", "retail", "automotive"},
    "lumber": {"lumber_paper", "construction"},
    "manufacturing": {"machinery", "electronics", "automotive", "steel"},
    "mining": {"bulk", "construction", "machinery"},
    "parcel": {"parcel", "electronics"},
    "port": {"container", "bulk", "automotive", "chemicals"},
    "retail": {"retail", "general", "parcel"},
    "river_port": {"bulk", "grain", "container"},
    "steel": {"steel", "machinery", "construction"},
}

FACILITY_SELECTION_WEIGHTS = {
    "company_yard": 0.45,
    "cross_dock": 1.15,
    "dry_warehouse": 1.0,
    "grocery_retail_dc": 1.05,
    "port_terminal": 1.25,
    "intermodal_ramp": 1.25,
    "parcel_hub": 1.15,
    "farm_elevator": 1.15,
    "food_processor": 1.0,
    "cold_storage": 1.0,
    "automotive_plant": 0.95,
    "chemical_petroleum_terminal": 0.85,
    "steel_industrial": 0.95,
    "mine_quarry": 0.8,
    "lumber_paper": 0.9,
}


def facility_label(location_type: str) -> str:
    return LOCATION_TYPE_LABELS.get(location_type, location_type.replace("_", " "))


def facility_text(location_type: str, location_name: str, city: str, locality: str = "") -> str:
    if location_type == "metro_market" or _is_legacy_facility_name(city, location_name):
        return f"the {city} metro freight market"
    place = f" near {locality}" if locality and locality not in location_name else ""
    return f"{facility_label(location_type)} {location_name}{place} in {city}"


def facility_offer_text(
    location_type: str, location_name: str, city: str, locality: str = ""
) -> str:
    if location_type == "metro_market" or _is_legacy_facility_name(city, location_name):
        return f"the {city} metro freight market"
    place = f" near {locality}" if locality and locality not in location_name else ""
    return f"{location_name}{place} in {city}"


def _is_legacy_facility_name(city: str, location_name: str) -> bool:
    normalized = str(location_name or "").strip().lower()
    city_lower = city.lower()
    return normalized in {
        "",
        city_lower,
        f"{city_lower} freight market",
        f"{city_lower} metro freight market",
    }


@dataclass
class Job:
    cargo: CargoType
    weight_tons: float
    origin: str
    origin_location: str
    destination: str
    distance_mi: float  # shortest-route miles, used for pay and deadline
    pay: float
    deadline_game_h: float
    market_mult: float = 1.0  # market multiplier already applied to pay
    origin_type: str = "terminal"
    destination_location: str = ""
    destination_type: str = "terminal"
    origin_facility_id: str = ""
    destination_facility_id: str = ""
    origin_locality: str = ""
    destination_locality: str = ""
    bobtail: bool = False  # empty reposition run: relocate, no cargo or pay

    def describe(
        self,
        index: int | None = None,
        total: int | None = None,
        pay_label: str = "Pays",
        trailer_note: str = "",
        display_pay: float | None = None,
        market_preview: str = "",
    ) -> str:
        prefix = f"Job {index} of {total}: " if index is not None else ""
        condition = market_condition(self.market_mult)
        market = f" Lane note: Market is {condition}." if condition != "steady" else ""
        preview = f" {market_preview}" if market_preview else ""
        endorsement = ""
        if self.cargo.endorsement:
            endorsement = f" Requires {ENDORSEMENT_LABELS[self.cargo.endorsement]}."
        origin = "from " + self.origin_offer_text()
        dest = "to " + self.destination_offer_text()
        trailer = f" {trailer_note}" if trailer_note else ""
        pay = self.pay if display_pay is None else display_pay
        return (
            f"{prefix}{self.weight_tons:.0f} tons of {self.cargo.label} "
            f"{origin} {dest}. {self.distance_mi:.0f} miles. "
            f"{pay_label} {pay:,.0f} dollars. "
            f"Deadline {self.deadline_game_h:.0f} hours. "
            f"Equipment: {self.cargo.equipment_text}.{trailer}{preview}{market}"
            f"{endorsement}"
        )

    def origin_facility_text(self) -> str:
        return facility_text(
            self.origin_type, self.origin_location, self.origin, self.origin_locality
        )

    def origin_offer_text(self) -> str:
        return facility_offer_text(
            self.origin_type, self.origin_location, self.origin, self.origin_locality
        )

    def destination_facility_text(self) -> str:
        return facility_text(
            self.destination_type,
            self.destination_location,
            self.destination,
            self.destination_locality,
        )

    def destination_offer_text(self) -> str:
        return facility_offer_text(
            self.destination_type,
            self.destination_location,
            self.destination,
            self.destination_locality,
        )

    def equipment_text(self) -> str:
        return self.cargo.equipment_text

    def locked_reason(
        self,
        endorsements: set[str],
        level: int,
        *,
        trailer_programs: set[str] | tuple[str, ...] | None = None,
        carrier_trailer_support: bool = True,
    ) -> str:
        if level < self.cargo.min_level:
            return f"Level {self.cargo.min_level} drivers unlock this cargo."
        if self.cargo.endorsement and self.cargo.endorsement not in endorsements:
            return f"Requires {ENDORSEMENT_LABELS[self.cargo.endorsement]}."
        if (
            not carrier_trailer_support
            and trailer_programs is not None
            and not (set(trailer_programs) & set(self.required_trailers()))
        ):
            return f"Requires {required_program_text(self.cargo.key)} trailer program."
        return ""

    def required_trailers(self) -> tuple[str, ...]:
        return trailer_keys_for_cargo(self.cargo.key)

    def payout(self, hours_taken: float, damage_pct: float, on_time_bonus: float = 0.15) -> float:
        """Final payment given delivery time and cargo condition."""
        pay = self.pay
        if hours_taken <= self.deadline_game_h:
            margin = 1.0 - hours_taken / self.deadline_game_h
            pay *= 1.0 + on_time_bonus * margin
        else:
            hours_late = hours_taken - self.deadline_game_h
            pay *= max(0.4, 1.0 - 0.08 * hours_late)
        if self.cargo.fragile:
            pay *= max(0.5, 1.0 - damage_pct / 100.0)
        else:
            pay *= max(0.7, 1.0 - damage_pct / 200.0)
        return round(pay, 2)


def job_payload(job: Job) -> dict:
    return {
        "cargo": job.cargo.key,
        "weight_tons": job.weight_tons,
        "origin": job.origin,
        "origin_location": job.origin_location,
        "origin_type": job.origin_type,
        "origin_facility_id": job.origin_facility_id,
        "origin_locality": job.origin_locality,
        "destination": job.destination,
        "destination_location": job.destination_location,
        "destination_type": job.destination_type,
        "destination_facility_id": job.destination_facility_id,
        "destination_locality": job.destination_locality,
        "distance_mi": job.distance_mi,
        "pay": job.pay,
        "deadline_game_h": job.deadline_game_h,
        "market_mult": job.market_mult,
        "bobtail": job.bobtail,
    }


def job_from_payload(data: dict) -> Job:
    cargo = CARGO_CATALOG[data["cargo"]]
    origin = str(data["origin"])
    destination = str(data["destination"])
    origin_location = str(
        data.get("origin_location") or data.get("origin_facility") or f"{origin} freight market"
    )
    destination_location = str(
        data.get("destination_location")
        or data.get("destination_facility")
        or f"{destination} freight market"
    )
    return Job(
        cargo,
        float(data["weight_tons"]),
        origin,
        origin_location,
        destination,
        float(data["distance_mi"]),
        float(data["pay"]),
        float(data["deadline_game_h"]),
        market_mult=float(data.get("market_mult", 1.0)),
        origin_type=str(data.get("origin_type", "metro_market")),
        destination_location=destination_location,
        destination_type=str(data.get("destination_type", "metro_market")),
        origin_facility_id=str(data.get("origin_facility_id", "")),
        destination_facility_id=str(data.get("destination_facility_id", "")),
        origin_locality=str(data.get("origin_locality", "")),
        destination_locality=str(data.get("destination_locality", "")),
        bobtail=bool(data.get("bobtail", False)),
    )


def make_reposition_job(world: World, origin: str, destination: str) -> Job | None:
    """A zero-pay empty 'bobtail' run to relocate to a nearby city.

    Reuses the normal delivery drive for fuel, weather, and save/resume, but
    carries no cargo and pays nothing. It is player-chosen personal conveyance,
    so the ELD records it as off duty instead of freight-duty driving; on
    arrival the player simply parks at the destination city's hub and can shop
    its dispatch board.
    """
    route = world.supported_route(origin, destination)
    if route is None:
        return None
    miles = round(route.miles, 1)
    dest = world.cities[destination]
    dest_loc = dest.locations[0] if dest.locations else None
    return Job(
        CARGO_CATALOG["general"],
        0.0,
        origin,
        "company yard",
        destination,
        miles,
        0.0,
        required_hours(miles, route, world) * 3.0 + 24.0,
        origin_type="company_yard",
        destination_location=dest_loc.name if dest_loc else f"{destination} yard",
        destination_type=dest_loc.type if dest_loc else "company_yard",
        bobtail=True,
    )


# Shortest job the dispatch board will offer. Cities stand for whole freight
# areas, so a haul below this is a trivial across-town hop (e.g. New York to
# Newark at 11 miles) rather than a real dispatch.
MIN_JOB_DISTANCE_MI = 25.0

# Career-arc distance caps: short regional hops while learning the ropes,
# cross-country hauls unlocking as a progression reward around level 4-5.
LEVEL_DISTANCE_CAPS = {1: 300.0, 2: 450.0, 3: 650.0, 4: 850.0, 5: 1200.0}
# Above level 5 the cap keeps growing gradually toward the longest supported
# coast-to-coast corridor (~2,800 miles). The old 500-mile-per-level growth
# blew past every real U.S. route by level 12, so haul length stopped feeling
# like progression; this keeps longer freight unlocking into the late teens.
LEVEL_DISTANCE_CAP_STEP_MI = 120.0
MAX_DISPATCH_DISTANCE_MI = 3000.0
LONG_HAUL_MILES = 600.0  # what counts as a cross-country haul
HOOKUP_FEE = 120.0  # flat load/unload fee keeping short hops worthwhile
MINIMUM_PAY_BY_LEVEL = {
    1: (700.0, 1.55),
    2: (900.0, 1.65),
    3: (1050.0, 1.75),
}
LONG_HAUL_MINIMUM_RATE_BY_LEVEL = {
    4: 4.75,
    5: 5.25,
}

# Deadline model: what a law-abiding trucker actually needs.
DEADLINE_AVG_MPH = 55.0  # achievable interstate average through zones and weather
DEADLINE_PLANNING_SPEED_FACTOR = 0.88
DEADLINE_SAMPLE_MI = 2.0
DEADLINE_MIN_SEGMENT_MPH = 10.0
DEADLINE_DISPATCH_MIN_SLACK_H = 1.0
DEADLINE_DISPATCH_SLACK_RANGE = (1.2, 1.5)
ACTIVE_TRIP_FAIRNESS_SLACK = 1.2


@dataclass(frozen=True)
class HosPlan:
    drive_h: float
    breaks: int
    sleeps: int
    break_stop_count: int = 0
    sleep_stop_count: int = 0

    @property
    def total_h(self) -> float:
        return self.drive_h + self.breaks * 0.5 + self.sleeps * 10.0

    def summary(self) -> str:
        break_text = (
            "no 30-minute break"
            if self.breaks == 0
            else f"{self.breaks} 30-minute break{'s' if self.breaks != 1 else ''}"
        )
        sleep_text = (
            "no 10-hour sleep"
            if self.sleeps == 0
            else f"{self.sleeps} 10-hour sleep{'s' if self.sleeps != 1 else ''}"
        )
        coverage = ""
        if self.break_stop_count or self.sleep_stop_count:
            coverage = (
                f" Route has {self.break_stop_count} break-capable "
                f"stop{'s' if self.break_stop_count != 1 else ''} "
                f"and {self.sleep_stop_count} sleep-capable "
                f"stop{'s' if self.sleep_stop_count != 1 else ''}."
            )
        return (
            f"Legal HOS plan: {self.drive_h:.1f} driving hours, "
            f"{break_text}, {sleep_text}.{coverage}"
        )


def plan_hos(
    miles: float,
    route: Route | None = None,
    world: World | None = None,
) -> HosPlan:
    """Estimate the FMCSA-compliant plan for a property-carrying trip.

    Based on FMCSA's public HOS summary: 11 driving hours after 10 off-duty
    hours, a 14-hour window, and a 30-minute break after 8 cumulative driving
    hours. Split sleeper and 60/70-hour cycle limits are intentionally not
    modeled in this route estimate.
    """
    drive_h = (
        route_drive_hours(route, world=world) if route is not None else miles / DEADLINE_AVG_MPH
    )
    return _plan_hos_for_drive_hours(drive_h, route)


def _plan_hos_for_drive_hours(drive_h: float, route: Route | None = None) -> HosPlan:
    """Apply the HOS break/sleep model to already-estimated driving hours."""

    breaks = 0
    sleeps = 0
    remaining = drive_h
    since_break = 0.0
    drive_this_shift = 0.0
    while remaining > 1e-6:
        if since_break >= 8.0:
            breaks += 1
            since_break = 0.0
        if drive_this_shift >= 11.0:
            sleeps += 1
            drive_this_shift = 0.0
            since_break = 0.0
        step = min(remaining, 8.0 - since_break, 11.0 - drive_this_shift)
        remaining -= step
        since_break += step
        drive_this_shift += step
    break_stops = sleep_stops = 0
    if route is not None:
        for stop in route.stop_details:
            actions = set(stop.actions)
            break_stops += "break" in actions or "food" in actions
            sleep_stops += "sleep" in actions
    return HosPlan(drive_h, breaks, sleeps, break_stops, sleep_stops)


def required_hours(
    miles: float,
    route: Route | None = None,
    world: World | None = None,
) -> float:
    """Honest hours for the run: driving at an achievable average, plus the
    30-minute break every 8 driving hours and a 10-hour sleep for every
    11-hour shift the distance demands. Dispatch cannot ask for less."""
    return plan_hos(miles, route, world).total_h


def route_required_hours(
    route: Route,
    start_mi: float = 0.0,
    world: World | None = None,
) -> float:
    """Minimum legal time for the actual route from ``start_mi`` onward."""

    return _plan_hos_for_drive_hours(
        route_drive_hours(route, start_mi=start_mi, world=world), route
    ).total_h


def dispatch_deadline_hours(
    miles: float,
    slack: float,
    route: Route | None = None,
    world: World | None = None,
) -> float:
    """Deadline from the current route-aware timing model plus dispatch slack."""

    return required_hours(miles, route, world) * slack + DEADLINE_DISPATCH_MIN_SLACK_H


def fair_active_deadline(
    job: Job,
    route: Route,
    hours_used: float,
    position_mi: float,
    world: World | None = None,
) -> float:
    """One-time compatibility floor for jobs saved before route-aware timing.

    Older source snapshots may have a deadline from the old mileage-only model.
    On resume, keep generous existing deadlines, but lift too-tight ones enough
    to cover both the whole route's fair model and the route still ahead.
    """

    full_floor = dispatch_deadline_hours(route.miles, ACTIVE_TRIP_FAIRNESS_SLACK, route, world)
    remaining_floor = (
        hours_used
        + route_required_hours(route, start_mi=position_mi, world=world)
        * ACTIVE_TRIP_FAIRNESS_SLACK
        + DEADLINE_DISPATCH_MIN_SLACK_H
    )
    return round(max(job.deadline_game_h, full_floor, remaining_floor), 1)


def route_drive_hours(
    route: Route | None,
    start_mi: float = 0.0,
    world: World | None = None,
) -> float:
    """Route-aware drive-time estimate using posted limits where available."""

    if route is None:
        return 0.0
    start_mi = max(0.0, min(route.miles, start_mi))
    if route.miles <= start_mi:
        return 0.0
    hours = 0.0
    leg_starts: list[float] = []
    acc = 0.0
    for leg in route.legs:
        leg_starts.append(acc)
        acc += leg.miles
    city_mileposts = leg_starts + [route.miles]
    is_facility_approach = len(route.cities) >= 2 and route.cities[0] == route.cities[-1]
    for index, (leg_start, leg) in enumerate(zip(leg_starts, route.legs, strict=True)):
        leg_end = leg_start + leg.miles
        segment_start = max(start_mi, leg_start)
        if segment_start >= leg_end:
            continue
        offset = segment_start - leg_start
        while offset < leg.miles - 1e-6:
            step = min(DEADLINE_SAMPLE_MI, leg.miles - offset)
            global_start = leg_start + offset
            if global_start + step <= start_mi:
                offset += step
                continue
            mid = global_start + step / 2.0
            mph = _route_planning_limit(
                route,
                index,
                leg,
                offset + step / 2.0,
                mid,
                city_mileposts,
                is_facility_approach,
                world,
            )
            hours += step / max(DEADLINE_MIN_SEGMENT_MPH, mph)
            offset += step
    return hours


def _route_planning_limit(
    route: Route,
    leg_index: int,
    leg,
    offset_mi: float,
    route_mi: float,
    city_mileposts: list[float],
    is_facility_approach: bool,
    world: World | None,
) -> float:
    if is_facility_approach:
        limit = FACILITY_ACCESS_LIMIT_MPH
    else:
        baked = _leg_speed_limit_at(leg, offset_mi)
        toward_city = route.cities[min(leg_index + 1, len(route.cities) - 1)]
        region = _route_city_region(toward_city, world)
        limit = baked if baked is not None else corridor_speed_limit(leg.highway, region)
        if baked is None and any(abs(route_mi - mp) <= URBAN_RADIUS_MI for mp in city_mileposts):
            limit = min(limit, URBAN_LIMIT_MPH)
        if route_mi >= max(0.0, route.miles - DESTINATION_APPROACH_ZONE_MI):
            limit = min(limit, DESTINATION_APPROACH_LIMIT_MPH)
    if route_mi >= max(0.0, route.miles - FACILITY_GATE_ZONE_MI):
        limit = min(limit, FACILITY_GATE_LIMIT_MPH)
    return limit * DEADLINE_PLANNING_SPEED_FACTOR


def _route_city_region(city: str, world: World | None) -> str:
    if world is None:
        return ""
    city_obj = world.cities.get(city)
    return "" if city_obj is None else city_obj.region


def minimum_pay_for_level(miles: float, level: int) -> float:
    """Dispatch minimums keep short early jobs worth the player's time."""
    floor, per_mile = MINIMUM_PAY_BY_LEVEL.get(
        min(level, max(MINIMUM_PAY_BY_LEVEL)), MINIMUM_PAY_BY_LEVEL[3]
    )
    pay = floor + miles * per_mile
    long_haul_rate = LONG_HAUL_MINIMUM_RATE_BY_LEVEL.get(
        min(level, max(LONG_HAUL_MINIMUM_RATE_BY_LEVEL))
    )
    if long_haul_rate is not None and miles >= LONG_HAUL_MILES:
        pay = max(pay, miles * long_haul_rate)
    return pay


# Reachable-destination candidates depend only on the (static) world, not the
# board seed. Cache them once across all JobBoard instances, keyed by world: the
# city hub and the tests spin up many fresh boards, and recomputing a supported
# route to every city each time scaled terribly as the network grew to 160+.
_CANDIDATES_CACHE: dict[int, dict[str, list[tuple[str, float, int]]]] = {}


class JobBoard:
    """Generates job offers at a city, filtered by the player's endorsements.

    Destinations follow a career arc: low levels offer mostly single-leg hops
    to neighboring cities, the distance cap grows with level, and every level
    weights destination choice by proximity so freight follows plausible
    lanes instead of teleporting across the country. New dispatches only use
    metadata-supported corridors; the broad legacy graph remains available for
    old saves while enrichment coverage expands.
    """

    def __init__(self, world: World, seed: int | None = None) -> None:
        self.world = world
        self._rng = random.Random(seed)

    @staticmethod
    def distance_cap(level: int) -> float:
        if level in LEVEL_DISTANCE_CAPS:
            return LEVEL_DISTANCE_CAPS[level]
        return min(
            MAX_DISPATCH_DISTANCE_MI,
            LEVEL_DISTANCE_CAPS[5] + LEVEL_DISTANCE_CAP_STEP_MI * (level - 5),
        )

    def offers(
        self,
        city: str,
        endorsements: set[str],
        count: int = 5,
        level: int = 1,
        market: Market | None = None,
        carrier_key: str | None = None,
        direct_freight: bool = False,
    ) -> list[Job]:
        jobs: list[Job] = []
        city_obj = self.world.cities[city]
        carrier_key = carrier_key or DEFAULT_START_KEY
        candidates = [c for c in self._candidates(city) if c[1] >= MIN_JOB_DISTANCE_MI]
        cap = self.distance_cap(level)
        reachable = [c for c in candidates if c[1] <= cap]
        if not reachable and candidates:
            # remote terminals (long legs all around): offer the nearest few
            reachable = sorted(candidates, key=lambda c: c[1])[:4]
        if not reachable:
            return jobs
        # Pick a spread of DISTINCT destinations up front so the board never
        # collapses to one back-and-forth city (a start with a single nearby
        # neighbour used to be locked into one route). Nearer cities stay likelier.
        dest_cycle = self._spread_destinations(city, reachable, level, count, carrier_key)
        attempts = 0
        while len(jobs) < count and attempts < count * 30:
            attempts += 1
            location = self._choose_origin_location(city_obj, level, carrier_key)
            cargo_key = self._choose_cargo_for_location(city_obj, location, level, carrier_key)
            cargo = CARGO_CATALOG[cargo_key]
            locked = cargo.endorsement and cargo.endorsement not in endorsements
            # a locked job may appear once in a while as a teaser, otherwise skip
            if locked and not (len(jobs) == count - 1 and self._rng.random() < 0.3):
                continue
            destination, miles, _legs = dest_cycle[len(jobs) % len(dest_cycle)]
            dest_location = self._destination_location(destination, cargo, level)
            if dest_location is None:
                continue
            jobs.append(
                self._make_job(
                    cargo,
                    city,
                    location.name,
                    destination,
                    miles,
                    market,
                    level,
                    location,
                    dest_location,
                    carrier_key,
                    direct_freight,
                )
            )
        jobs.sort(key=lambda j: j.distance_mi)
        return jobs

    def _spread_destinations(
        self,
        origin: str,
        reachable: list[tuple[str, float, int]],
        level: int,
        count: int,
        carrier_key: str = DEFAULT_START_KEY,
    ) -> list[tuple[str, float, int]]:
        """A weighted spread of distinct destinations (nearer = likelier).

        Aims for at least three distinct cities (or as many as the network
        allows) so the dispatch board offers real choices instead of repeating
        one destination. Rookies still lean toward short hauls.
        """
        best: dict[str, tuple[str, float, int]] = {}
        for cand in reachable:
            if cand[0] not in best or cand[1] < best[cand[0]][1]:
                best[cand[0]] = cand
        pool = list(best.values())
        target = min(len(pool), max(3, count))
        exponent = 2.0 if level <= 2 else 1.0
        chosen: list[tuple[str, float, int]] = []
        available = pool[:]
        while available and len(chosen) < target:
            weights = [
                self._destination_weight(origin, cand, level, carrier_key, exponent)
                for cand in available
            ]
            pick = self._rng.choices(available, weights)[0]
            chosen.append(pick)
            available.remove(pick)
        return chosen or pool

    def _destination_weight(
        self,
        origin: str,
        candidate: tuple[str, float, int],
        level: int,
        carrier_key: str = DEFAULT_START_KEY,
        exponent: float | None = None,
    ) -> float:
        """Weighted lane fit for a carrier's modest dispatch tendencies."""
        destination, miles, _legs = candidate
        exponent = exponent if exponent is not None else (2.0 if level <= 2 else 1.0)
        weight = 1.0 / (miles**exponent)
        option = start_option(carrier_key)
        cap = max(1.0, self.distance_cap(level))
        if option.dispatch.short_haul_bias:
            short_factor = max(0.0, 1.0 - min(miles, cap) / cap)
            weight *= 1.0 + option.dispatch.short_haul_bias * short_factor
        if option.dispatch.long_haul_bias:
            long_factor = min(1.0, miles / cap)
            weight *= 1.0 + option.dispatch.long_haul_bias * long_factor
        if option.dispatch.regional_bias:
            origin_region = self.world.cities[origin].region
            if self.world.cities[destination].region == origin_region:
                weight *= 1.0 + option.dispatch.regional_bias
        return max(weight, 1e-12)

    def _candidates(self, city: str) -> list[tuple[str, float, int]]:
        """(destination, route miles, route leg count) for every other city."""
        per_world = _CANDIDATES_CACHE.setdefault(id(self.world), {})
        cached = per_world.get(city)
        if cached is None:
            cached = []
            for dest in self.world.city_names():
                if dest == city:
                    continue
                route = self.world.supported_route(city, dest)
                if route is not None:
                    cached.append((dest, route.miles, len(route.legs)))
            per_world[city] = cached
        return cached

    def _choose_destination(
        self, candidates: list[tuple[str, float, int]], level: int
    ) -> tuple[str, float, int]:
        pool = candidates
        if level >= 4:
            # seasoned drivers see a dedicated cross-country slot now and then
            long_hauls = [c for c in candidates if c[1] >= LONG_HAUL_MILES]
            if long_hauls and self._rng.random() < 0.35:
                pool = long_hauls
        # Nearer destinations are likelier, and rookies lean harder toward short
        # hauls (squared distance falloff). Crucially the pool is never narrowed
        # to a single-leg-only set -- that locked sparse start cities into one
        # back-and-forth route. Leg count no longer gates which cities appear.
        exponent = 2.0 if level <= 2 else 1.0
        weights = [1.0 / (c[1] ** exponent) for c in pool]
        return self._rng.choices(pool, weights)[0]

    def _choose_origin_location(
        self,
        city,
        level: int,
        carrier_key: str = DEFAULT_START_KEY,
    ) -> Location:
        plausible = [
            location
            for location in city.locations
            if location.min_level <= level and self._cargo_for_location(location, level=level)
        ]
        if not plausible:
            plausible = list(city.locations)
        weights = [self._facility_weight(city, location, carrier_key) for location in plausible]
        return self._rng.choices(plausible, weights)[0]

    def _choose_cargo_for_location(
        self,
        city,
        location: Location,
        level: int,
        carrier_key: str = DEFAULT_START_KEY,
    ) -> str:
        cargo_keys = self._cargo_for_location(location, level=level)
        if not cargo_keys:
            cargo_keys = tuple(
                cargo.key for cargo in CARGO_CATALOG.values() if cargo.min_level <= level
            )
        weights = [self._cargo_weight(city, key, carrier_key) for key in cargo_keys]
        return self._rng.choices(cargo_keys, weights)[0]

    def _cargo_for_location(
        self, location: Location, role: str = "ships", level: int | None = None
    ) -> tuple[str, ...]:
        role_values = location.ships if role == "ships" else location.receives
        if not role_values:
            role_values = tuple(FACILITY_CARGO.get(location.type, ())) or location.cargo
        allowed = []
        for key in role_values:
            cargo = CARGO_CATALOG.get(key)
            if cargo is None:
                continue
            if level is not None and cargo.min_level > level:
                continue
            allowed.append(key)
        return tuple(allowed)

    def _destination_location(self, city: str, cargo: CargoType, level: int) -> Location | None:
        locations = self.world.cities[city].locations
        plausible = [
            loc
            for loc in locations
            if loc.min_level <= level
            and cargo.key in self._cargo_for_location(loc, role="receives", level=level)
        ]
        if not plausible:
            plausible = [
                loc
                for loc in locations
                if cargo.key in self._cargo_for_location(loc, role="receives")
            ]
        if not plausible:
            return None
        return self._rng.choices(
            plausible,
            [self._facility_weight(self.world.cities[city], loc) for loc in plausible],
        )[0]

    def _facility_weight(
        self,
        city,
        location: Location,
        carrier_key: str = DEFAULT_START_KEY,
    ) -> float:
        weight = FACILITY_SELECTION_WEIGHTS.get(location.type, 0.85)
        for tag in city.market_tags:
            boosted = MARKET_TAG_CARGO_BONUS.get(tag, set())
            if boosted & set(location.ships + location.receives):
                weight += 0.25
        if location.template:
            weight *= 0.9
        option = start_option(carrier_key)
        if option.cargo_weight_bonus:
            cargo_keys = set(location.ships + location.receives)
            if cargo_keys & set(option.cargo_weight_bonus):
                weight += 0.2
        return max(0.1, weight)

    def _cargo_weight(
        self,
        city,
        cargo_key: str,
        carrier_key: str = DEFAULT_START_KEY,
    ) -> float:
        weight = 1.0
        for tag in city.market_tags:
            if cargo_key in MARKET_TAG_CARGO_BONUS.get(tag, set()):
                weight += 0.65
        cargo = CARGO_CATALOG[cargo_key]
        if cargo.endorsement:
            weight *= 0.8
        weight += start_option(carrier_key).cargo_weight_bonus.get(cargo_key, 0.0)
        return weight

    def _make_job(
        self,
        cargo: CargoType,
        origin: str,
        origin_location: str,
        destination: str,
        miles: float,
        market: Market | None,
        level: int,
        origin_facility: Location,
        destination_facility: Location,
        carrier_key: str = DEFAULT_START_KEY,
        direct_freight: bool = False,
    ) -> Job:
        weight = self._rng.uniform(*cargo.weight_tons)
        rate = cargo.rate_per_mile * self._rng.uniform(0.9, 1.15)
        mult = market.multiplier(cargo.key) if market is not None else 1.0
        base_pay = HOOKUP_FEE + miles * rate * (1.0 + weight / 120.0)
        direct_mult = DIRECT_FREIGHT_PAY_MULT if direct_freight else 1.0
        pay = round(max(base_pay, minimum_pay_for_level(miles, level)) * mult * direct_mult, 2)
        # deadline: the honest HOS-compliant hours (driving, breaks, sleep),
        # shipper slack on top, plus a flat hour for fuel and the unexpected
        route = self.world.supported_route(origin, destination)
        slack = self._rng.uniform(*DEADLINE_DISPATCH_SLACK_RANGE)
        deadline = (
            dispatch_deadline_hours(miles, slack, route, self.world)
            * start_option(carrier_key).dispatch.deadline_slack
        )
        return Job(
            cargo,
            weight,
            origin,
            origin_location,
            destination,
            round(miles, 1),
            pay,
            round(deadline, 1),
            market_mult=mult,
            origin_type=origin_facility.type,
            destination_location=destination_facility.name,
            destination_type=destination_facility.type,
            origin_facility_id=origin_facility.id,
            destination_facility_id=destination_facility.id,
            origin_locality=origin_facility.locality,
            destination_locality=destination_facility.locality,
        )
