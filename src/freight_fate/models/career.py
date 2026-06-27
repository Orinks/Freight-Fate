"""Career progression: experience, levels, endorsements, and reputation."""

from __future__ import annotations

from dataclasses import dataclass

from .career_ladder import MAX_CAREER_LEVEL, next_rank_for_level, rank_for_level

# XP needed for each level in the 20-level career ladder.
LEVEL_XP = [
    0,
    1000,
    2500,
    4500,
    7000,
    10_000,
    14_000,
    19_000,
    25_000,
    32_000,
    40_000,
    50_000,
    62_000,
    76_000,
    92_000,
    110_000,
    130_000,
    152_000,
    176_000,
    202_000,
]

# Endorsements unlocked automatically at these levels.
ENDORSEMENT_LEVELS = {
    "refrigerated": 2,
    "heavy_haul": 3,
    "high_value": 4,
}

ENDORSEMENT_ANNOUNCEMENTS = {
    "refrigerated": ("You earned the refrigerated endorsement. "
                     "Food and refrigerated cargo jobs are now available."),
    "heavy_haul": ("You earned the heavy-haul endorsement. "
                   "Heavy machinery jobs are now available."),
    "high_value": ("You earned the high-value endorsement. "
                   "Electronics jobs are now available."),
}


def level_for_xp(xp: float) -> int:
    level = 1
    for i, threshold in enumerate(LEVEL_XP[1:], start=2):
        if xp >= threshold:
            level = i
    return min(level, MAX_CAREER_LEVEL)


@dataclass
class Career:
    xp: float = 0.0
    reputation: float = 50.0       # 0..100
    deliveries: int = 0
    on_time_deliveries: int = 0
    total_miles: float = 0.0
    total_earnings: float = 0.0

    @property
    def level(self) -> int:
        return level_for_xp(self.xp)

    @property
    def rank(self):
        return rank_for_level(self.level)

    @property
    def endorsements(self) -> set[str]:
        return {e for e, lvl in ENDORSEMENT_LEVELS.items() if self.level >= lvl}

    def record_delivery(self, miles: float, pay: float, on_time: bool,
                        damage_pct: float) -> list[str]:
        """Apply a finished delivery; returns announcements (level ups etc.)."""
        before_level = self.level
        before_endorsements = self.endorsements

        self.deliveries += 1
        self.total_miles += miles
        self.total_earnings += pay
        gained = miles * (1.2 if on_time else 0.8)
        self.xp += gained
        if on_time:
            self.on_time_deliveries += 1
            self.reputation = min(100.0, self.reputation + 2.0)
        else:
            self.reputation = max(0.0, self.reputation - 4.0)
        if damage_pct > 25:
            self.reputation = max(0.0, self.reputation - 3.0)

        messages: list[str] = []
        if self.level > before_level:
            rank = self.rank
            messages.append(
                f"Level up! You are now level {self.level}: {rank.title}. "
                f"Unlock: {rank.unlock}"
            )
        for endorsement in self.endorsements - before_endorsements:
            messages.append(ENDORSEMENT_ANNOUNCEMENTS[endorsement])
        return messages

    def summary(self) -> str:
        pct = (100 * self.on_time_deliveries / self.deliveries) if self.deliveries else 100
        rank = self.rank
        next_rank = next_rank_for_level(self.level)
        next_text = (
            f" Next: level {next_rank.level}, {next_rank.title}."
            if next_rank is not None else
            " You are at the top career rank."
        )
        return (f"Level {self.level}, {rank.title}. {self.xp:.0f} experience. "
                f"Reputation {self.reputation:.0f} out of 100. "
                f"{self.deliveries} deliveries, {pct:.0f} percent on time. "
                f"{self.total_miles:,.0f} lifetime miles, "
                f"{self.total_earnings:,.0f} dollars earned. "
                f"Career stage: {rank.stage}. {rank.status}.{next_text}")
