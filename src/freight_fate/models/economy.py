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

# Dispatcher pay advances: a recovery line for a driver who has run the
# balance negative and can no longer afford fuel. Cash now, drawn against
# the next settlement and repaid automatically at delivery. Offered only
# when cash is already low so it stays a safety net against a soft lock,
# not free liquidity. Mirrors how carriers and factoring services front a
# driver fuel money against a load in transit.
PAY_ADVANCE_LIMIT = 1500.0          # most you can owe at once
PAY_ADVANCE_GRANT = 500.0           # cash per request
PAY_ADVANCE_ELIGIBLE_BELOW = 10.0   # only offered at single-digit cash or worse


def pay_advance_grant(money: float, outstanding: float) -> float:
    """Dollars a dispatcher will advance now, or 0 when none is available.

    Available only while cash is low (a recovery tool) and only up to the
    outstanding-advance ceiling, so it can never become a bottomless loan.
    """
    if money >= PAY_ADVANCE_ELIGIBLE_BELOW:
        return 0.0
    headroom = PAY_ADVANCE_LIMIT - max(0.0, outstanding)
    if headroom < 1.0:
        return 0.0
    return round(min(PAY_ADVANCE_GRANT, headroom), 2)


def pay_advance_unavailable_reason(money: float, outstanding: float) -> str:
    """Spoken explanation for why no advance is available right now."""
    if money >= PAY_ADVANCE_ELIGIBLE_BELOW:
        return ("A pay advance is only for getting unstuck when cash is low. "
                f"You have {money:,.0f} dollars.")
    return ("You have reached your pay-advance limit. Deliver a load to pay "
            "it down before drawing more.")


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
