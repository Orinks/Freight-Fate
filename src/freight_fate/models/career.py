"""Career progression: experience, levels, endorsements, and reputation."""

from __future__ import annotations

from dataclasses import dataclass

# XP needed to go from level N to N+1 (then +1500 per level beyond the table)
LEVEL_XP = [0, 1000, 2500, 4500, 7000, 10_000, 14_000, 19_000, 25_000]

# What a mile of driving teaches, by whether the load landed on time. These are
# named (not inline) because the cloud-save validator re-derives the highest XP
# a career could honestly hold from them: a hand-copied ceiling on the server
# drifts the moment these move, and the failure lands on the player as a
# rejected backup. Export them via profile_integrity_invariants instead.
XP_PER_MILE_ON_TIME = 1.2
XP_PER_MILE_LATE = 0.8

# Endorsements unlocked automatically at these levels.
ENDORSEMENT_LEVELS = {
    "refrigerated": 2,
    "heavy_haul": 3,
    "high_value": 4,
}

ENDORSEMENT_ANNOUNCEMENTS = {
    "refrigerated": (
        "You earned the refrigerated endorsement. "
        "Food and refrigerated cargo jobs are now available."
    ),
    "heavy_haul": (
        "You earned the heavy-haul endorsement. Heavy machinery jobs are now available."
    ),
    "high_value": ("You earned the high-value endorsement. Electronics jobs are now available."),
}


def level_for_xp(xp: float) -> int:
    level = 1
    for i, threshold in enumerate(LEVEL_XP[1:], start=2):
        if xp >= threshold:
            level = i
    extra = xp - LEVEL_XP[-1]
    if extra > 0:
        level = len(LEVEL_XP) + int(extra // 1500)
    return level


@dataclass
class Career:
    xp: float = 0.0
    reputation: float = 50.0  # 0..100
    deliveries: int = 0
    on_time_deliveries: int = 0
    total_miles: float = 0.0
    total_earnings: float = 0.0

    @property
    def level(self) -> int:
        return level_for_xp(self.xp)

    @property
    def endorsements(self) -> set[str]:
        return {e for e, lvl in ENDORSEMENT_LEVELS.items() if self.level >= lvl}

    def record_delivery(
        self, miles: float, pay: float, on_time: bool, damage_pct: float
    ) -> list[str]:
        """Apply a finished delivery; returns announcements (level ups etc.)."""
        before_level = self.level
        before_endorsements = self.endorsements

        self.deliveries += 1
        self.total_miles += miles
        self.total_earnings += pay
        gained = miles * (XP_PER_MILE_ON_TIME if on_time else XP_PER_MILE_LATE)
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
            messages.append(f"Level up! You are now a level {self.level} driver.")
        for endorsement in self.endorsements - before_endorsements:
            messages.append(ENDORSEMENT_ANNOUNCEMENTS[endorsement])
        return messages

    def summary(self) -> str:
        pct = (100 * self.on_time_deliveries / self.deliveries) if self.deliveries else 100
        return (
            f"Level {self.level} driver. {self.xp:.0f} experience. "
            f"Reputation {self.reputation:.0f} out of 100. "
            f"{self.deliveries} deliveries, {pct:.0f} percent on time. "
            f"{self.total_miles:,.0f} lifetime miles, "
            f"{self.total_earnings:,.0f} dollars earned."
        )
