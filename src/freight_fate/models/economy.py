"""Money: fuel prices, repairs, and running costs."""

from __future__ import annotations

import random

# Diesel $/gal by region, nudged by a per-session market wobble.
REGION_FUEL_PRICE = {
    "northeast": 4.15,
    "appalachia": 3.95,
    "great_lakes": 3.75,
    "heartland": 3.60,
    "southern_plains": 3.45,
    "mid_south": 3.45,
    "atlantic_southeast": 3.65,
    "gulf_coast": 3.40,
    "florida": 3.85,
    "rockies": 3.95,
    "great_basin": 4.10,
    "desert_southwest": 4.00,
    "california": 5.10,
    "pacific_northwest": 4.45,
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
