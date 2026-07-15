"""Freight market: per-cargo-class pay multipliers that drift day by day.

Each cargo class carries a multiplier between 0.8 and 1.3 applied to job
pay. Multipliers move once per in-game day with a seeded random walk, so a
profile's market history is deterministic: replaying the same seed over the
same days always lands on the same numbers. The whole state is persisted on
the player profile.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

MARKET_MIN = 0.8
MARKET_MAX = 1.3
DAILY_DRIFT = 0.06

# Cargo classes tracked by the market (mirrors jobs.CARGO_CATALOG; kept as a
# literal so this module needs no imports from the job layer).
MARKET_CARGO_KEYS = (
    "general",
    "retail",
    "parcel",
    "container",
    "bulk",
    "grain",
    "farm_inputs",
    "construction",
    "lumber_paper",
    "automotive",
    "machinery",
    "steel",
    "food",
    "refrigerated",
    "chemicals",
    "electronics",
)


def market_condition(multiplier: float) -> str:
    """Spoken one-word market condition for a multiplier."""
    if multiplier >= 1.07:
        return "tight"
    if multiplier <= 0.97:
        return "loose"
    return "steady"


def _clamp(value: float) -> float:
    return max(MARKET_MIN, min(MARKET_MAX, value))


@dataclass
class Market:
    seed: int = field(default_factory=lambda: random.randrange(2**31))
    day: int = 0
    multipliers: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        missing = [key for key in MARKET_CARGO_KEYS if key not in self.multipliers]
        if not missing:
            return
        # Careers saved before a cargo-class expansion carry multipliers only
        # for the classes that existed then. Newly tracked classes get their
        # seeded starting values -- the same draw a fresh market would make --
        # so every career trades the full catalog and stays deterministic.
        rng = random.Random(self.seed)
        seeded = {key: round(rng.uniform(0.9, 1.15), 3) for key in MARKET_CARGO_KEYS}
        for key in missing:
            self.multipliers[key] = seeded[key]

    def multiplier(self, cargo_key: str) -> float:
        return self.multipliers.get(cargo_key, 1.0)

    def condition(self, cargo_key: str) -> str:
        return market_condition(self.multiplier(cargo_key))

    def advance_to(self, day: int) -> bool:
        """Walk the market forward to the given in-game day.

        Each elapsed day every class drifts by a step drawn from a generator
        seeded with (profile seed, day), so catching up several days at once
        gives the same result as advancing one day at a time.
        """
        changed = False
        while self.day < day:
            self.day += 1
            rng = random.Random(self.seed * 1_000_003 + self.day)
            for key in sorted(self.multipliers):
                step = rng.uniform(-DAILY_DRIFT, DAILY_DRIFT)
                self.multipliers[key] = round(_clamp(self.multipliers[key] + step), 3)
            changed = True
        return changed

    def summary(self) -> str:
        """Spoken job-board headline naming the standout cargo classes."""
        items = sorted(self.multipliers.items())
        tight = sorted((kv for kv in items if kv[1] >= 1.07), key=lambda kv: kv[1], reverse=True)
        loose = sorted((kv for kv in items if kv[1] <= 0.97), key=lambda kv: kv[1])
        if not tight and not loose:
            return "Freight market is steady across the board."
        parts = [
            f"{key.replace('_', ' ')} {market_condition(mult)}"
            for key, mult in tight[:2] + loose[:2]
        ]
        return "Market watch: " + ", ".join(parts) + "."
