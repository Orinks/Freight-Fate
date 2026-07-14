"""Career progression: experience, levels, endorsements, and reputation."""

from __future__ import annotations

from dataclasses import dataclass, field

from .career_ladder import MAX_CAREER_LEVEL, next_rank_for_level, rank_for_level

# XP needed for each level in the 30-level career ladder. The first 20
# thresholds stay fixed so existing saves keep their current level. Levels
# 21 through 30 are new on the 1.9 line and are paced so each late rank
# lands after a solid evening or two of freight instead of a lost weekend:
# the whole arc is a months-long career, but every level keeps paying out.
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
    216_000,
    231_000,
    247_000,
    264_000,
    282_000,
    301_000,
    321_000,
    342_000,
    364_000,
    387_000,
]

# Endorsements unlock automatically at these levels: the carrier sponsors
# the training once dispatch trusts you with the freight.
ENDORSEMENT_LEVELS = {
    "refrigerated": 2,
    "heavy_haul": 3,
    "high_value": 4,
}

# Paying for the course yourself unlocks an endorsement before the carrier
# would sponsor it -- real drivers buy their own training to get ahead.
ENDORSEMENT_COURSE_COSTS = {
    "refrigerated": 900.0,
    "heavy_haul": 1_600.0,
    "high_value": 1_300.0,
}

ENDORSEMENT_LABELS_SPOKEN = {
    "refrigerated": "refrigerated",
    "heavy_haul": "heavy-haul",
    "high_value": "high-value",
}

# Experience scales with what the freight demands, not just its miles:
# specialty (endorsement) cargo and premium mid-level cargo teach more per
# mile, a run of consecutive on-time deliveries compounds the lesson, and
# bringing the cargo in undamaged proves the lesson stuck. Every settled
# load also teaches a flat slice of the trade -- docks, paperwork, people --
# so short early hauls still move the career.
XP_SPECIALTY_MULT = 1.5
XP_PREMIUM_MULT = 1.25
XP_STREAK_STEP = 0.05  # extra share per consecutive on-time delivery
XP_STREAK_MAX_BONUS = 0.45
XP_CLEAN_BONUS = 0.15  # bonus share for delivering with no real damage
DELIVERY_COMPLETION_XP = 150.0  # flat lesson per settled load (halved late)
XP_PER_MILE_ON_TIME = 1.6
XP_PER_MILE_LATE = 0.9


def xp_class_multiplier(cargo) -> float:
    """How much more a delivery teaches, by cargo demands."""
    if getattr(cargo, "endorsement", None):
        return XP_SPECIALTY_MULT
    if getattr(cargo, "min_level", 1) >= 2:
        return XP_PREMIUM_MULT
    return 1.0


def xp_streak_bonus(streak: int) -> float:
    """Bonus XP share for consecutive on-time deliveries (0 for the first)."""
    return min(XP_STREAK_MAX_BONUS, XP_STREAK_STEP * max(0, streak - 1))


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
    return min(level, MAX_CAREER_LEVEL)


@dataclass
class Career:
    xp: float = 0.0
    reputation: float = 50.0  # 0..100
    deliveries: int = 0
    on_time_deliveries: int = 0
    total_miles: float = 0.0
    total_earnings: float = 0.0
    dispatch_declines_used: int = 0  # assigned-load refusals since last level-up
    on_time_streak: int = 0  # consecutive on-time deliveries
    purchased_endorsements: list[str] = field(default_factory=list)  # self-paid courses

    @property
    def level(self) -> int:
        return level_for_xp(self.xp)

    @property
    def rank(self):
        return rank_for_level(self.level)

    @property
    def endorsements(self) -> set[str]:
        earned = {e for e, lvl in ENDORSEMENT_LEVELS.items() if self.level >= lvl}
        purchased = {e for e in self.purchased_endorsements if e in ENDORSEMENT_LEVELS}
        return earned | purchased

    def record_delivery(
        self,
        miles: float,
        pay: float,
        on_time: bool,
        damage_pct: float,
        cargo_class_mult: float = 1.0,
    ) -> list[str]:
        """Apply a finished delivery; returns announcements (level ups etc.)."""
        before_level = self.level
        before_endorsements = self.endorsements

        self.deliveries += 1
        self.total_miles += miles
        self.total_earnings += pay
        if on_time:
            self.on_time_streak += 1
        else:
            self.on_time_streak = 0
        completion = DELIVERY_COMPLETION_XP * (1.0 if on_time else 0.5)
        per_mile = XP_PER_MILE_ON_TIME if on_time else XP_PER_MILE_LATE
        gained = completion + miles * per_mile * max(1.0, cargo_class_mult)
        if on_time:
            gained *= 1.0 + xp_streak_bonus(self.on_time_streak)
        if damage_pct <= 1.0:
            gained *= 1.0 + XP_CLEAN_BONUS
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
            # A promotion clears the assigned-load refusals dispatch remembers.
            self.dispatch_declines_used = 0
            rank = self.rank
            messages.append(
                f"Level up! You are now level {self.level}: {rank.title}. Unlock: {rank.unlock}"
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
            if next_rank is not None
            else " You are at the top career rank."
        )
        return (
            f"Level {self.level}, {rank.title}. {self.xp:.0f} experience. "
            f"Reputation {self.reputation:.0f} out of 100. "
            f"{self.deliveries} deliveries, {pct:.0f} percent on time. "
            f"{self.total_miles:,.0f} lifetime miles, "
            f"{self.total_earnings:,.0f} dollars earned. "
            f"Career stage: {rank.stage}. {rank.status}.{next_text}"
        )
