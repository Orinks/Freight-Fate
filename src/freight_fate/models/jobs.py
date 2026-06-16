"""Cargo catalog and job generation.

Jobs are generated at a city's freight locations, pay by real route miles,
and gate special cargo behind license endorsements earned through the
career system.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from ..data.world import LOCATION_TYPE_LABELS, Location, World
from .market import Market, market_condition


@dataclass(frozen=True)
class CargoType:
    key: str
    label: str
    rate_per_mile: float       # base $ per mile
    weight_tons: tuple[float, float]
    endorsement: str | None    # required license endorsement, if any
    fragile: bool = False


CARGO_CATALOG: dict[str, CargoType] = {
    "general": CargoType("general", "general freight", 2.10, (8, 20), None),
    "retail": CargoType("retail", "retail goods", 2.25, (6, 16), None),
    "container": CargoType("container", "shipping containers", 2.40, (12, 24), None),
    "bulk": CargoType("bulk", "bulk materials", 2.30, (15, 25), None),
    "machinery": CargoType("machinery", "heavy machinery", 2.90, (15, 25),
                           "heavy_haul", fragile=True),
    "food": CargoType("food", "fresh food", 2.60, (8, 18), "refrigerated", fragile=True),
    "refrigerated": CargoType("refrigerated", "refrigerated goods", 2.85, (8, 18),
                              "refrigerated", fragile=True),
    "electronics": CargoType("electronics", "electronics", 3.30, (4, 12), "high_value",
                             fragile=True),
}

ENDORSEMENT_LABELS = {
    None: "standard CDL",
    "refrigerated": "refrigerated endorsement",
    "heavy_haul": "heavy-haul endorsement",
    "high_value": "high-value endorsement",
}

FACILITY_CARGO: dict[str, set[str]] = {
    "air_cargo": {"electronics", "general"},
    "distribution": {"food", "general", "retail", "refrigerated"},
    "food_terminal": {"food", "refrigerated"},
    "industrial_park": {"bulk", "machinery", "retail"},
    "intermodal": {"bulk", "container", "general"},
    "manufacturing": {"bulk", "electronics", "machinery"},
    "port": {"bulk", "container", "electronics", "machinery"},
    "rail": {"bulk", "container", "machinery"},
    "retail_distribution": {"general", "retail"},
    "terminal": {"electronics", "general", "retail"},
    "warehouse": {"bulk", "general", "machinery", "retail"},
}


def facility_label(location_type: str) -> str:
    return LOCATION_TYPE_LABELS.get(location_type, location_type.replace("_", " "))


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

    def describe(self, index: int | None = None, total: int | None = None) -> str:
        prefix = f"Job {index} of {total}: " if index is not None else ""
        condition = market_condition(self.market_mult)
        market = f" Market is {condition}." if condition != "steady" else ""
        endorsement = ""
        if self.cargo.endorsement:
            endorsement = f" Requires {ENDORSEMENT_LABELS[self.cargo.endorsement]}."
        origin = f"from {facility_label(self.origin_type)} {self.origin_location}"
        if self.destination_location:
            dest = (f"to {facility_label(self.destination_type)} "
                    f"{self.destination_location} in {self.destination}")
        else:
            dest = f"to {self.destination}"
        return (f"{prefix}{self.weight_tons:.0f} tons of {self.cargo.label} "
                f"{origin} {dest}. {self.distance_mi:.0f} miles. "
                f"Pays {self.pay:,.0f} dollars. "
                f"Deadline {self.deadline_game_h:.0f} hours.{market}{endorsement}")

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


def required_hours(miles: float) -> float:
    """Honest hours for the run: driving at an achievable average, plus the
    30-minute break every 8 driving hours and a 10-hour sleep for every
    11-hour shift the distance demands. Dispatch cannot ask for less."""
    drive_h = miles / DEADLINE_AVG_MPH
    breaks_h = 0.5 * max(0, math.ceil(max(0.0, drive_h - 8.0) / 8.0))
    sleeps_h = 10.0 * max(0, math.ceil(max(0.0, drive_h - 11.0) / 11.0))
    return drive_h + breaks_h + sleeps_h


def minimum_pay_for_level(miles: float, level: int) -> float:
    """Dispatch minimums keep short early jobs worth the player's time."""
    floor, per_mile = MINIMUM_PAY_BY_LEVEL.get(
        min(level, max(MINIMUM_PAY_BY_LEVEL)), MINIMUM_PAY_BY_LEVEL[3])
    return floor + miles * per_mile


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
        self._candidates_cache: dict[str, list[tuple[str, float, int]]] = {}

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
        attempts = 0
        while len(jobs) < count and attempts < count * 12:
            attempts += 1
            location = self._rng.choice(city_obj.locations)
            cargo_key = self._rng.choice(self._cargo_for_location(location))
            cargo = CARGO_CATALOG[cargo_key]
            locked = cargo.endorsement and cargo.endorsement not in endorsements
            # a locked job may appear once in a while as a teaser, otherwise skip
            if locked and not (len(jobs) == count - 1 and self._rng.random() < 0.3):
                continue
            destination, miles, _legs = self._choose_destination(reachable, level)
            dest_location = self._destination_location(destination, cargo)
            jobs.append(self._make_job(cargo, city, location.name, destination,
                                       miles, market, level, location,
                                       dest_location))
        jobs.sort(key=lambda j: j.distance_mi)
        return jobs

    def _candidates(self, city: str) -> list[tuple[str, float, int]]:
        """(destination, route miles, route leg count) for every other city."""
        cached = self._candidates_cache.get(city)
        if cached is None:
            cached = []
            for dest in self.world.city_names():
                if dest == city:
                    continue
                route = self.world.supported_route(city, dest)
                if route is not None:
                    cached.append((dest, route.miles, len(route.legs)))
            self._candidates_cache[city] = cached
        return cached

    def _choose_destination(self, candidates: list[tuple[str, float, int]],
                            level: int) -> tuple[str, float, int]:
        pool = candidates
        if level <= 2:
            # rookie runs: mostly direct hops, sometimes a two-leg trip
            one = [c for c in candidates if c[2] == 1]
            two = [c for c in candidates if c[2] == 2]
            if level == 1 and one and (not two or self._rng.random() < 0.8):
                pool = one
            elif level == 2 and two and self._rng.random() < 0.55:
                pool = two
            elif one:
                pool = one
            elif two:
                pool = two
        elif level == 3:
            pool = [c for c in candidates if c[2] <= 3] or candidates
        else:
            # seasoned drivers see a dedicated cross-country slot now and then
            long_hauls = [c for c in candidates if c[1] >= LONG_HAUL_MILES]
            if long_hauls and self._rng.random() < 0.35:
                pool = long_hauls
        # nearer cities are likelier at every level: freight moves lane by lane
        weights = [1.0 / c[1] for c in pool]
        return self._rng.choices(pool, weights)[0]

    def _cargo_for_location(self, location: Location) -> tuple[str, ...]:
        allowed = FACILITY_CARGO.get(location.type)
        if not allowed:
            return location.cargo
        plausible = tuple(c for c in location.cargo if c in allowed)
        return plausible or location.cargo

    def _destination_location(self, city: str, cargo: CargoType) -> Location:
        locations = self.world.cities[city].locations
        plausible = [
            loc for loc in locations
            if cargo.key in self._cargo_for_location(loc)
        ]
        return self._rng.choice(plausible or list(locations))

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
                   destination_type=destination_facility.type)
