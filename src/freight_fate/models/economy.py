"""Money: fuel prices, repairs, and running costs."""

from __future__ import annotations

import random

# Diesel $/gal by region, nudged by a per-session market wobble.
REGION_FUEL_PRICE = {
    "northeast": 4.15,
    "midwest": 3.70,
    "south": 3.55,
    "plains": 3.60,
    "rockies": 3.85,
    "southwest": 3.95,
    "west_coast": 4.85,
    "northwest": 4.35,
}

REPAIR_COST_PER_PCT = 85.0     # $ per percent of damage repaired
REST_COST = 35.0               # flat cost of a rest stop visit (food, parking)


class Economy:
    def __init__(self, seed: int | None = None) -> None:
        rng = random.Random(seed)
        self._market = {region: rng.uniform(0.92, 1.10) for region in REGION_FUEL_PRICE}

    def fuel_price(self, region: str) -> float:
        base = REGION_FUEL_PRICE.get(region, 3.80)
        return round(base * self._market.get(region, 1.0), 2)

    def fuel_cost(self, region: str, gallons: float) -> float:
        return round(self.fuel_price(region) * gallons, 2)

    @staticmethod
    def repair_cost(damage_pct: float) -> float:
        return round(damage_pct * REPAIR_COST_PER_PCT, 2)
