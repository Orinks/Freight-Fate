"""The safety record: how interesting this driver looks to an inspector.

Real commercial enforcement does not pick trucks at random. Every carrier
carries a score built from its inspection and violation history, and the
screening software at a scale reads it before anyone looks at the truck. A
clean operator is waved through year after year; a dirty one is pulled in
every time, which feels less like bad luck than like being followed.

That is the dial this file provides, and it is what makes a clean career
pleasant and a dirty one relentless -- without the game having to cheat, and
without a clean driver's police contacts ever costing them anything.

**Spoken as "safety record". Never as ISS, never as CSA, never as a score.**
Those are trade acronyms; a player hearing "your ISS is 78" learns nothing.
The number is internal. What the game says out loud is a band.

Higher is worse, matching the real convention: 0 is a driver nobody has any
reason to look at, 100 is one every screening lane flags.
"""

from __future__ import annotations

SAFETY_RECORD_MIN = 0.0
SAFETY_RECORD_MAX = 100.0

# A brand-new career has no history at all. Neither clean nor dirty: unknown,
# and unknown gets looked at a little more than proven-clean does.
SAFETY_RECORD_BASELINE = 30.0

# Band edges. "Targeted" sits at the real screening threshold.
BAND_CLEAN_BELOW = 40.0
BAND_TARGETED_AT = 75.0

BAND_CLEAN = "clean"
BAND_WATCHED = "watched"
BAND_TARGETED = "targeted"

# What each input is worth. Citations dominate, because a citation is a
# recorded finding; damage matters because it is visible from the shoulder;
# reputation pulls both ways because a carrier in good standing gets the
# benefit of the doubt.
CITATION_WEIGHT = 7.0
CITATION_CAP = 35.0
SERIOUS_WEIGHT = 9.0
SERIOUS_CAP = 27.0
OUT_OF_SERVICE_WEIGHT = 12.0
OUT_OF_SERVICE_CAP = 24.0
FATIGUE_EVENT_WEIGHT = 6.0
FATIGUE_EVENT_CAP = 18.0
# Damage starts counting where an officer could see it from a passing lane.
DAMAGE_NOTICE_PCT = 40.0
DAMAGE_WEIGHT = 0.45
DAMAGE_CAP = 27.0
# A clean inspection is the only thing that buys the record back down, and it
# is worth less than a citation costs -- which is exactly how the real ratings
# behave, and why drivers guard a clean record rather than repairing one.
CLEAN_INSPECTION_CREDIT = 3.5
CLEAN_INSPECTION_CAP = 21.0
# Reputation shifts the baseline by up to this much in either direction.
REPUTATION_SWING = 12.0
REPUTATION_NEUTRAL = 50.0


def _clamp(value: float, low: float = SAFETY_RECORD_MIN, high: float = SAFETY_RECORD_MAX) -> float:
    return max(low, min(high, value))


def selection_score(
    *,
    reputation: float = REPUTATION_NEUTRAL,
    citations: int = 0,
    serious_violations: int = 0,
    out_of_service_events: int = 0,
    fatigue_events: int = 0,
    clean_inspections: int = 0,
    damage_pct: float = 0.0,
) -> float:
    """How interesting this driver looks to a screening lane, 0 to 100.

    Pure: every input is passed in, so the same history always produces the
    same number and the function is testable without a Profile.
    """
    score = SAFETY_RECORD_BASELINE
    score += min(CITATION_CAP, CITATION_WEIGHT * max(0, int(citations)))
    score += min(SERIOUS_CAP, SERIOUS_WEIGHT * max(0, int(serious_violations)))
    score += min(OUT_OF_SERVICE_CAP, OUT_OF_SERVICE_WEIGHT * max(0, int(out_of_service_events)))
    score += min(FATIGUE_EVENT_CAP, FATIGUE_EVENT_WEIGHT * max(0, int(fatigue_events)))
    visible_damage = max(0.0, float(damage_pct) - DAMAGE_NOTICE_PCT)
    score += min(DAMAGE_CAP, DAMAGE_WEIGHT * visible_damage)
    score -= min(CLEAN_INSPECTION_CAP, CLEAN_INSPECTION_CREDIT * max(0, int(clean_inspections)))
    # Standing with the carrier and the shippers is not a safety rating, but a
    # driver nobody has a complaint about does get the benefit of the doubt.
    rep_offset = (float(reputation) - REPUTATION_NEUTRAL) / REPUTATION_NEUTRAL
    score -= REPUTATION_SWING * max(-1.0, min(1.0, rep_offset))
    return round(_clamp(score), 2)


def score_for_profile(profile, *, damage_pct: float = 0.0) -> float:
    """The safety record for a live Profile, read defensively.

    Every field is read with a default so this works against a partially
    built profile, an older save, and the test fixtures -- and so a field a
    parallel change is still adding cannot break the whole enforcement layer.
    """
    career = getattr(profile, "career", None)
    record = getattr(profile, "driving_record", None)
    stats = getattr(profile, "achievement_stats", None) or {}
    return selection_score(
        reputation=float(getattr(career, "reputation", REPUTATION_NEUTRAL) or REPUTATION_NEUTRAL),
        citations=int(getattr(record, "citations", 0) or 0),
        serious_violations=len(getattr(record, "serious_violations", ()) or ()),
        out_of_service_events=int(getattr(profile, "out_of_service_events", 0) or 0),
        fatigue_events=int(getattr(record, "fatigue_events", 0) or 0),
        clean_inspections=int(stats.get("inspections_passed", 0) or 0),
        damage_pct=float(damage_pct or 0.0),
    )


def refresh_selection_score(profile, *, damage_pct: float = 0.0) -> float:
    """Recompute and store the record on the profile, returning it."""
    score = score_for_profile(profile, damage_pct=damage_pct)
    profile.selection_score = score
    return score


def safety_band(score: float) -> str:
    if score < BAND_CLEAN_BELOW:
        return BAND_CLEAN
    if score < BAND_TARGETED_AT:
        return BAND_WATCHED
    return BAND_TARGETED


def safety_record_text(score: float) -> str:
    """The spoken line. A band and a reason, never a number and never jargon."""
    band = safety_band(score)
    if band == BAND_CLEAN:
        return "Safety record: clean. Inspectors have no reason to pull you in."
    if band == BAND_WATCHED:
        return "Safety record: watched. Open scales will look at you more often than not."
    return "Safety record: targeted. Expect to be pulled in at every open scale."


def inspection_selection_chance(score: float) -> float:
    """Odds an open scale sends this driver to the inspection lane.

    Clean drivers are waved through nearly always; a targeted one is not
    waved through at all. This is the whole difference between the pleasant
    career and the relentless one.
    """
    band = safety_band(score)
    if band == BAND_CLEAN:
        return 0.08
    if band == BAND_WATCHED:
        return 0.45
    return 1.0


__all__ = [
    "BAND_CLEAN",
    "BAND_CLEAN_BELOW",
    "BAND_TARGETED",
    "BAND_TARGETED_AT",
    "BAND_WATCHED",
    "SAFETY_RECORD_BASELINE",
    "SAFETY_RECORD_MAX",
    "SAFETY_RECORD_MIN",
    "inspection_selection_chance",
    "refresh_selection_score",
    "safety_band",
    "safety_record_text",
    "score_for_profile",
    "selection_score",
]
