"""Cargo catalog and job generation.

Jobs are generated at a city's freight locations, pay by real route miles,
and gate special cargo behind license endorsements earned through the
career system.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ..data.world import World
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
    "machinery": CargoType("machinery", "heavy machinery", 2.90, (15, 25), None, fragile=True),
    "food": CargoType("food", "fresh food", 2.60, (8, 18), "refrigerated", fragile=True),
    "refrigerated": CargoType("refrigerated", "refrigerated goods", 2.85, (8, 18),
                              "refrigerated", fragile=True),
    "electronics": CargoType("electronics", "electronics", 3.30, (4, 12), "high_value",
                             fragile=True),
}

ENDORSEMENT_LABELS = {
    None: "standard CDL",
    "refrigerated": "refrigerated endorsement",
    "high_value": "high-value endorsement",
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

    def describe(self, index: int | None = None, total: int | None = None) -> str:
        prefix = f"Job {index} of {total}: " if index is not None else ""
        condition = market_condition(self.market_mult)
        market = f" Market is {condition}." if condition != "steady" else ""
        endorsement = ""
        if self.cargo.endorsement:
            endorsement = f" Requires {ENDORSEMENT_LABELS[self.cargo.endorsement]}."
        return (f"{prefix}{self.weight_tons:.0f} tons of {self.cargo.label} "
                f"to {self.destination}. {self.distance_mi:.0f} miles. "
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


class JobBoard:
    """Generates job offers at a city, filtered by the player's endorsements."""

    def __init__(self, world: World, seed: int | None = None) -> None:
        self.world = world
        self._rng = random.Random(seed)

    def offers(self, city: str, endorsements: set[str], count: int = 5,
               level: int = 1, market: Market | None = None) -> list[Job]:
        jobs: list[Job] = []
        city_obj = self.world.cities[city]
        others = [c for c in self.world.city_names() if c != city]
        # early levels keep hauls regional so new players aren't buried
        max_miles = 400 + level * 350
        attempts = 0
        while len(jobs) < count and attempts < count * 12:
            attempts += 1
            location = self._rng.choice(city_obj.locations)
            cargo_key = self._rng.choice(location.cargo)
            cargo = CARGO_CATALOG[cargo_key]
            locked = cargo.endorsement and cargo.endorsement not in endorsements
            # a locked job may appear once in a while as a teaser, otherwise skip
            if locked and not (len(jobs) == count - 1 and self._rng.random() < 0.3):
                continue
            destination = self._rng.choice(others)
            route = self.world.shortest_route(city, destination)
            if route is None or route.miles > max_miles:
                continue
            jobs.append(self._make_job(cargo, city, location.name, destination,
                                       route.miles, market))
        jobs.sort(key=lambda j: j.distance_mi)
        return jobs

    def _make_job(self, cargo: CargoType, origin: str, origin_location: str,
                  destination: str, miles: float, market: Market | None) -> Job:
        weight = self._rng.uniform(*cargo.weight_tons)
        rate = cargo.rate_per_mile * self._rng.uniform(0.9, 1.15)
        mult = market.multiplier(cargo.key) if market is not None else 1.0
        pay = round(miles * rate * (1.0 + weight / 120.0) * mult, 2)
        # deadline: 50 mph average plus generous slack
        deadline = miles / 50.0 * self._rng.uniform(1.35, 1.7)
        return Job(cargo, weight, origin, origin_location, destination,
                   round(miles, 1), pay, round(deadline, 1), market_mult=mult)
