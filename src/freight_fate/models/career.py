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
    # The back half of the arc stops being about heavier freight and starts
    # being about freight that fights back. A tank is the first of those.
    "tank": 16,
}

# Paying for the course yourself unlocks an endorsement before the carrier
# would sponsor it -- real drivers buy their own training to get ahead.
ENDORSEMENT_COURSE_COSTS = {
    "refrigerated": 900.0,
    "heavy_haul": 1_600.0,
    "high_value": 1_300.0,
    "tank": 2_400.0,
}

ENDORSEMENT_LABELS_SPOKEN = {
    "refrigerated": "refrigerated",
    "heavy_haul": "heavy-haul",
    "high_value": "high-value",
    "tank": "tank vehicle",
}

# The full credential ladder, as the invariants export renders it: the
# carrier-sponsored level (None = course-only; the site must never
# level-derive those), the spoken/public label, and the ladder tier.
# Mirrors ``models::credentials::CREDENTIALS`` in the Rust runtime, which
# is the source of truth for gameplay.
CREDENTIALS_EXPORT = {
    "manual_transmission": {"level": None, "label": "manual transmission", "tier": "training"},
    "refrigerated": {"level": 2, "label": "refrigerated", "tier": "certificate"},
    "flatbed_securement": {"level": 2, "label": "flatbed securement", "tier": "certificate"},
    "heavy_haul": {"level": 3, "label": "heavy-haul", "tier": "certificate"},
    "high_value": {"level": 4, "label": "high-value", "tier": "certificate"},
    "doubles_triples": {"level": None, "label": "doubles", "tier": "endorsement"},
    "tank": {"level": 16, "label": "tank vehicle", "tier": "endorsement"},
    "hazmat": {"level": None, "label": "hazmat", "tier": "endorsement"},
    "twic": {"level": None, "label": "TWIC port card", "tier": "specialist"},
    "lcv": {"level": None, "label": "LCV", "tier": "specialist"},
}

# Experience scales with what the freight demands, not just its miles:
# specialty (endorsement) cargo and premium mid-level cargo teach more per
# mile, a run of consecutive on-time deliveries compounds the lesson, and
# bringing the cargo in undamaged proves the lesson stuck. Every settled
# load also teaches a flat slice of the trade -- docks, paperwork, people --
# so short early hauls still move the career.
#
# Cloud-save screening re-derives the highest XP an honest career could hold
# from these, via profile_integrity_invariants. Change any of them and the
# export must be regenerated: the server once kept its own 1.2 per mile,
# which these rates outgrew, and honest drivers had backups refused for it.
XP_SPECIALTY_MULT = 1.5
XP_PREMIUM_MULT = 1.25
XP_STREAK_STEP = 0.05  # extra share per consecutive on-time delivery
XP_STREAK_MAX_BONUS = 0.45
XP_CLEAN_BONUS = 0.15  # bonus share for delivering with no real damage
DELIVERY_COMPLETION_XP = 150.0  # flat lesson per settled load (halved late)
XP_PER_MILE_ON_TIME = 1.6
XP_PER_MILE_LATE = 0.9


# Nobody grooms a driver on a final warning for promotion. A carrier that has
# stopped trusting a driver puts them on routine freight and stops investing
# in them, and the career moves slower for it.
#
# Three rules bind these numbers. A driver in full trust is at exactly 1.0, so
# the tuned arc to level 30 does not move a minute for anyone running clean.
# Nothing ever reaches zero, because a driver digging out has to be able to
# make progress or the career is a trap with a menu. And every rate is at or
# below 1.0, so the XP ceiling exported to cloud-save screening still bounds
# every honest career.
#
# Keyed by the spoken band strings from ``enforcement`` rather than importing
# them, which would close an import cycle. A test pins the two together.
STANDING_XP_RATE = {
    "full": 1.0,
    "guarded": 0.9,
    "poor": 0.75,
    "last chance": 0.6,
}


def standing_xp_rate(band: str) -> float:
    """How fast the career moves at this level of dispatch trust."""
    return STANDING_XP_RATE.get(band, 1.0)


def xp_rate_clause(band: str) -> str:
    """One sentence saying the career has slowed, and why. Empty when it has not.

    Never the number. A multiplier a player cannot check turns every
    settlement into arithmetic and reads as an accusation; what they need is
    the cause and the way out, which they can act on.
    """
    if standing_xp_rate(band) >= 1.0:
        return ""
    return (
        f"While your dispatch trust is {band}, the carrier keeps you on "
        "routine freight, so career experience comes in more slowly until it "
        "is back up."
    )


def xp_rate_settlement_clause(band: str) -> str:
    """The same fact as a clause, to ride an existing settlement line."""
    if standing_xp_rate(band) >= 1.0:
        return ""
    return f"at the slower rate that comes with {band} dispatch trust"


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


def streak_bonus_xp(streak: int, base_xp: float, mileage_xp: float) -> float:
    """XP the on-time streak adds, capped at what the miles themselves taught.

    The share applies to the whole award, flat completion XP included -- but
    a streak can at most double the road lesson, never mint XP off the flat
    per-delivery award. Without the cap, chaining board-minimum 25-mile hops
    farmed the streak against a base that is nearly all completion XP. The
    cap only binds below about 77 miles at plain freight; the honest pacing
    model's shortest deal is 105 miles, so the contracted arc to level 30 is
    unchanged to the float.
    """
    return min(xp_streak_bonus(streak) * base_xp, mileage_xp)


ENDORSEMENT_ANNOUNCEMENTS = {
    "refrigerated": (
        "You earned the refrigerated endorsement. "
        "Food and refrigerated cargo jobs are now available."
    ),
    "heavy_haul": (
        "You earned the heavy-haul endorsement. Heavy machinery jobs are now available."
    ),
    "high_value": ("You earned the high-value endorsement. Electronics jobs are now available."),
    "tank": (
        "You earned the tank vehicle endorsement. Liquid bulk jobs are now available. "
        "A tank load keeps moving after you do: brake early, brake once, and "
        "listen for the wave coming back."
    ),
}


def xp_to_next_level(xp: float) -> float | None:
    """Experience still owed before the next level, or None at the ceiling.

    The summary said what level you are and what the next RANK is, but never
    the number between them, so the one question a player actually asks --
    how much more -- had no answer anywhere in the game (Brandon, tester
    report 2026-08-17).
    """
    level = level_for_xp(xp)
    if level >= MAX_CAREER_LEVEL:
        return None
    return max(0.0, LEVEL_XP[level] - xp)


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
    # Courses taken whose background check has not cleared yet, and grants
    # not yet repeated at a terminal (the Rust runtime drives both; the
    # fields exist here so the exported careerFields list matches a save).
    pending_credentials: list = field(default_factory=list)
    unacknowledged_grants: list = field(default_factory=list)

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
        standing_rate: float = 1.0,
    ) -> list[str]:
        """Apply a finished delivery; returns announcements (level ups etc.).

        ``standing_rate`` slows the career for a driver the carrier has
        stopped investing in. It defaults to 1.0 and is applied only when it
        is not 1.0, so a clean driver's XP is the same arithmetic it has
        always been, down to the float.
        """
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
        mileage_xp = miles * per_mile * max(1.0, cargo_class_mult)
        gained = completion + mileage_xp
        if on_time:
            gained += streak_bonus_xp(self.on_time_streak, gained, mileage_xp)
        if damage_pct <= 1.0:
            gained *= 1.0 + XP_CLEAN_BONUS
        if standing_rate != 1.0:
            gained *= max(0.0, min(1.0, float(standing_rate)))
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
            # A big delivery can jump several ranks at once; every rank
            # passed through gets its own line so its unlock is actually
            # heard, not just the final rank's (single-level phrasing is
            # unchanged: the loop runs once and reads identically).
            for gained_level in range(before_level + 1, self.level + 1):
                rank = rank_for_level(gained_level)
                messages.append(
                    f"Level up! You are now level {gained_level}: "
                    f"{rank.title}. Unlock: {rank.unlock}"
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
        owed = xp_to_next_level(self.xp)
        # The number the player is actually asking for, next to the level it
        # belongs to rather than buried at the end of a long readout.
        owed_text = f" {owed:,.0f} more to level {self.level + 1}." if owed is not None else ""
        return (
            f"Level {self.level}, {rank.title}. {self.xp:.0f} experience."
            f"{owed_text} "
            f"Reputation {self.reputation:.0f} out of 100. "
            f"{self.deliveries} deliveries, {pct:.0f} percent on time. "
            f"{self.total_miles:,.0f} lifetime miles, "
            f"{self.total_earnings:,.0f} dollars earned. "
            f"Career stage: {rank.stage}. {rank.status}.{next_text}"
        )
