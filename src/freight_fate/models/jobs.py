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
from .market import Market, market_condition


@dataclass(frozen=True)
class CargoType:
    key: str
    label: str
    rate_per_mile: float       # base $ per mile
    weight_tons: tuple[float, float]
    endorsement: str | None    # required license endorsement, if any
    fragile: bool = False
    min_level: int = 1
    equipment: str = "dry van"


CARGO_CATALOG: dict[str, CargoType] = {
    "general": CargoType("general", "general freight", 2.10, (8, 20), None),
    "retail": CargoType("retail", "retail goods", 2.25, (6, 16), None),
    "parcel": CargoType("parcel", "parcel freight", 2.55, (4, 12), None),
    "container": CargoType("container", "shipping containers", 2.40, (12, 24), None),
    "bulk": CargoType("bulk", "bulk materials", 2.30, (15, 25), None,
                      equipment="bulk trailer"),
    "grain": CargoType("grain", "grain", 2.20, (18, 25), None,
                       equipment="hopper trailer"),
    "farm_inputs": CargoType("farm_inputs", "farm inputs", 2.35, (10, 22), None,
                             equipment="dry van or bulk trailer"),
    "construction": CargoType("construction", "construction materials", 2.35, (14, 25),
                              None, equipment="flatbed or dry van"),
    "lumber_paper": CargoType("lumber_paper", "lumber and paper products", 2.45,
                              (10, 24), None, min_level=2,
                              equipment="flatbed or dry van"),
    "automotive": CargoType("automotive", "automotive parts", 2.75, (8, 20), None,
                            fragile=True, min_level=2, equipment="dry van"),
    "machinery": CargoType("machinery", "heavy machinery", 2.90, (15, 25),
                           "heavy_haul", fragile=True,
                           equipment="heavy-haul trailer"),
    "steel": CargoType("steel", "steel products", 2.85, (16, 25), "heavy_haul",
                       min_level=3, equipment="flatbed trailer"),
    "food": CargoType("food", "fresh food", 2.60, (8, 18), "refrigerated",
                      fragile=True, equipment="refrigerated trailer"),
    "refrigerated": CargoType("refrigerated", "refrigerated goods", 2.85, (8, 18),
                              "refrigerated", fragile=True,
                              equipment="refrigerated trailer"),
    "chemicals": CargoType("chemicals", "packaged industrial chemicals", 3.05,
                           (10, 22), "high_value", min_level=4,
                           equipment="sealed van or tanker-compatible trailer"),
    "electronics": CargoType("electronics", "electronics", 3.30, (4, 12), "high_value",
                             fragile=True, equipment="secure dry van"),
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


def facility_text(location_type: str, location_name: str, city: str,
                  locality: str = "") -> str:
    if location_type == "metro_market" or _is_legacy_facility_name(city, location_name):
        return f"the {city} metro freight market"
    place = f" near {locality}" if locality and locality not in location_name else ""
    return f"{facility_label(location_type)} {location_name}{place} in {city}"


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
    distance_mi: float       # shortest-route miles, used for pay and deadline
    pay: float
    deadline_game_h: float
    market_mult: float = 1.0   # market multiplier already applied to pay
    origin_type: str = "terminal"
    destination_location: str = ""
    destination_type: str = "terminal"
    origin_facility_id: str = ""
    destination_facility_id: str = ""
    origin_locality: str = ""
    destination_locality: str = ""
    bobtail: bool = False      # empty reposition run: relocate, no cargo or pay

    def describe(self, index: int | None = None, total: int | None = None) -> str:
        prefix = f"Job {index} of {total}: " if index is not None else ""
        condition = market_condition(self.market_mult)
        market = f" Lane note: Market is {condition}." if condition != "steady" else ""
        endorsement = ""
        if self.cargo.endorsement:
            endorsement = f" Requires {ENDORSEMENT_LABELS[self.cargo.endorsement]}."
        origin = "from " + self.origin_facility_text()
        dest = "to " + self.destination_facility_text()
        return (f"{prefix}{self.weight_tons:.0f} tons of {self.cargo.label} "
                f"{origin} {dest}. {self.distance_mi:.0f} miles. "
                f"Pays {self.pay:,.0f} dollars. "
                f"Deadline {self.deadline_game_h:.0f} hours. "
                f"Equipment: {self.cargo.equipment}.{market}{endorsement}")

    def origin_facility_text(self) -> str:
        return facility_text(
            self.origin_type, self.origin_location, self.origin, self.origin_locality)

    def destination_facility_text(self) -> str:
        return facility_text(
            self.destination_type,
            self.destination_location,
            self.destination,
            self.destination_locality,
        )

    def locked_reason(self, endorsements: set[str], level: int) -> str:
        if level < self.cargo.min_level:
            return f"Level {self.cargo.min_level} drivers unlock this cargo."
        if self.cargo.endorsement and self.cargo.endorsement not in endorsements:
            return f"Requires {ENDORSEMENT_LABELS[self.cargo.endorsement]}."
        return ""

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
        data.get("origin_location")
        or data.get("origin_facility")
        or f"{origin} freight market"
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

    Reuses the normal delivery drive (so HOS, fuel, weather, and save/resume all
    apply) but carries no cargo and pays nothing; on arrival the player simply
    parks at the destination city's hub and can shop its dispatch board.
    """
    route = world.supported_route(origin, destination)
    if route is None:
        return None
    miles = round(route.miles, 1)
    dest = world.cities[destination]
    dest_loc = dest.locations[0] if dest.locations else None
    return Job(
        CARGO_CATALOG["general"], 0.0, origin, "company yard", destination,
        miles, 0.0, required_hours(miles) * 3.0 + 24.0,
        origin_type="company_yard",
        destination_location=dest_loc.name if dest_loc else f"{destination} yard",
        destination_type=dest_loc.type if dest_loc else "company_yard",
        bobtail=True,
    )


# Career-arc distance caps: short regional hops while learning the ropes,
# cross-country hauls unlocking as a progression reward around level 4-5.
LEVEL_DISTANCE_CAPS = {1: 300.0, 2: 450.0, 3: 650.0, 4: 850.0, 5: 1200.0}
LONG_HAUL_MILES = 600.0   # what counts as a cross-country haul
HOOKUP_FEE = 120.0        # flat load/unload fee keeping short hops worthwhile
MINIMUM_PAY_BY_LEVEL = {
    1: (700.0, 1.55),
    2: (900.0, 1.65),
    3: (1050.0, 1.75),
}

# Deadline model: what a law-abiding trucker actually needs.
DEADLINE_AVG_MPH = 55.0   # achievable interstate average through zones and weather


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
            if self.breaks == 0 else
            f"{self.breaks} 30-minute break{'s' if self.breaks != 1 else ''}"
        )
        sleep_text = (
            "no 10-hour sleep"
            if self.sleeps == 0 else
            f"{self.sleeps} 10-hour sleep{'s' if self.sleeps != 1 else ''}"
        )
        coverage = ""
        if self.break_stop_count or self.sleep_stop_count:
            coverage = (f" Route has {self.break_stop_count} break-capable "
                        f"stop{'s' if self.break_stop_count != 1 else ''} "
                        f"and {self.sleep_stop_count} sleep-capable "
                        f"stop{'s' if self.sleep_stop_count != 1 else ''}.")
        return (f"Legal HOS plan: {self.drive_h:.1f} driving hours, "
                f"{break_text}, {sleep_text}.{coverage}")


def plan_hos(miles: float, route: Route | None = None) -> HosPlan:
    """Estimate the FMCSA-compliant plan for a property-carrying trip.

    Based on FMCSA's public HOS summary: 11 driving hours after 10 off-duty
    hours, a 14-hour window, and a 30-minute break after 8 cumulative driving
    hours. Split sleeper and 60/70-hour cycle limits are intentionally not
    modeled in this route estimate.
    """
    drive_h = miles / DEADLINE_AVG_MPH
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


def required_hours(miles: float) -> float:
    """Honest hours for the run: driving at an achievable average, plus the
    30-minute break every 8 driving hours and a 10-hour sleep for every
    11-hour shift the distance demands. Dispatch cannot ask for less."""
    return plan_hos(miles).total_h


def minimum_pay_for_level(miles: float, level: int) -> float:
    """Dispatch minimums keep short early jobs worth the player's time."""
    floor, per_mile = MINIMUM_PAY_BY_LEVEL.get(
        min(level, max(MINIMUM_PAY_BY_LEVEL)), MINIMUM_PAY_BY_LEVEL[3])
    return floor + miles * per_mile


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
        return LEVEL_DISTANCE_CAPS[5] + 500.0 * (level - 5)

    def offers(self, city: str, endorsements: set[str], count: int = 5,
               level: int = 1, market: Market | None = None) -> list[Job]:
        jobs: list[Job] = []
        city_obj = self.world.cities[city]
        candidates = self._candidates(city)
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
        dest_cycle = self._spread_destinations(reachable, level, count)
        attempts = 0
        while len(jobs) < count and attempts < count * 30:
            attempts += 1
            location = self._choose_origin_location(city_obj, level)
            cargo_key = self._choose_cargo_for_location(city_obj, location, level)
            cargo = CARGO_CATALOG[cargo_key]
            locked = cargo.endorsement and cargo.endorsement not in endorsements
            # a locked job may appear once in a while as a teaser, otherwise skip
            if locked and not (len(jobs) == count - 1 and self._rng.random() < 0.3):
                continue
            destination, miles, _legs = dest_cycle[len(jobs) % len(dest_cycle)]
            dest_location = self._destination_location(destination, cargo, level)
            if dest_location is None:
                continue
            jobs.append(self._make_job(cargo, city, location.name, destination,
                                       miles, market, level, location,
                                       dest_location))
        jobs.sort(key=lambda j: j.distance_mi)
        return jobs

    def _spread_destinations(
        self, reachable: list[tuple[str, float, int]], level: int, count: int,
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
            weights = [1.0 / (cand[1] ** exponent) for cand in available]
            pick = self._rng.choices(available, weights)[0]
            chosen.append(pick)
            available.remove(pick)
        return chosen or pool

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

    def _choose_destination(self, candidates: list[tuple[str, float, int]],
                            level: int) -> tuple[str, float, int]:
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

    def _choose_origin_location(self, city, level: int) -> Location:
        plausible = [
            location
            for location in city.locations
            if location.min_level <= level and self._cargo_for_location(location, level=level)
        ]
        if not plausible:
            plausible = list(city.locations)
        weights = [self._facility_weight(city, location) for location in plausible]
        return self._rng.choices(plausible, weights)[0]

    def _choose_cargo_for_location(self, city, location: Location, level: int) -> str:
        cargo_keys = self._cargo_for_location(location, level=level)
        if not cargo_keys:
            cargo_keys = tuple(cargo.key for cargo in CARGO_CATALOG.values()
                               if cargo.min_level <= level)
        weights = [self._cargo_weight(city, key) for key in cargo_keys]
        return self._rng.choices(cargo_keys, weights)[0]

    def _cargo_for_location(self, location: Location, role: str = "ships",
                            level: int | None = None) -> tuple[str, ...]:
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

    def _destination_location(self, city: str, cargo: CargoType,
                              level: int) -> Location | None:
        locations = self.world.cities[city].locations
        plausible = [
            loc for loc in locations
            if loc.min_level <= level and cargo.key in self._cargo_for_location(
                loc, role="receives", level=level)
        ]
        if not plausible:
            plausible = [
                loc for loc in locations
                if cargo.key in self._cargo_for_location(loc, role="receives")
            ]
        if not plausible:
            return None
        return self._rng.choices(
            plausible,
            [self._facility_weight(self.world.cities[city], loc) for loc in plausible],
        )[0]

    def _facility_weight(self, city, location: Location) -> float:
        weight = FACILITY_SELECTION_WEIGHTS.get(location.type, 0.85)
        for tag in city.market_tags:
            boosted = MARKET_TAG_CARGO_BONUS.get(tag, set())
            if boosted & set(location.ships + location.receives):
                weight += 0.25
        if location.template:
            weight *= 0.9
        return max(0.1, weight)

    def _cargo_weight(self, city, cargo_key: str) -> float:
        weight = 1.0
        for tag in city.market_tags:
            if cargo_key in MARKET_TAG_CARGO_BONUS.get(tag, set()):
                weight += 0.65
        cargo = CARGO_CATALOG[cargo_key]
        if cargo.endorsement:
            weight *= 0.8
        return weight

    def _make_job(self, cargo: CargoType, origin: str, origin_location: str,
                  destination: str, miles: float, market: Market | None,
                  level: int, origin_facility: Location,
                  destination_facility: Location) -> Job:
        weight = self._rng.uniform(*cargo.weight_tons)
        rate = cargo.rate_per_mile * self._rng.uniform(0.9, 1.15)
        mult = market.multiplier(cargo.key) if market is not None else 1.0
        base_pay = HOOKUP_FEE + miles * rate * (1.0 + weight / 120.0)
        pay = round(max(base_pay, minimum_pay_for_level(miles, level)) * mult, 2)
        # deadline: the honest HOS-compliant hours (driving, breaks, sleep),
        # shipper slack on top, plus a flat hour for fuel and the unexpected
        deadline = required_hours(miles) * self._rng.uniform(1.2, 1.5) + 1.0
        return Job(cargo, weight, origin, origin_location, destination,
                   round(miles, 1), pay, round(deadline, 1), market_mult=mult,
                   origin_type=origin_facility.type,
                   destination_location=destination_facility.name,
                   destination_type=destination_facility.type,
                   origin_facility_id=origin_facility.id,
                   destination_facility_id=destination_facility.id,
                   origin_locality=origin_facility.locality,
                   destination_locality=destination_facility.locality)
