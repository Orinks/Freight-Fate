"""The single terrain rule: is a stretch of road flat, hills, or mountain?

Terrain is relief in context, not one steep number. The enrichment pipeline's
old test -- "grade over 3% is mountain" -- had no relief and no duration, so a
lone 4% creek-crossing roller in the East Texas piney woods read "mountain" and
the status readout told a Texan he was in the mountains (Josh, 2026-07-19).

Both the offline reclassifier (``reclassify_terrain.py``, working from the dense
archived elevation profiles) and the live enrichment (``enrich_routes_ors.py``,
working from an ORS route's sampled elevations) must reach the same verdict, so
the decision lives here once. Each caller measures local steepness and nearby
relief from whatever data it has and asks :func:`terrain_for`; the thresholds
are shared so the two paths never drift.

Thresholds were tuned against the acceptance list in
``docs/terrain-audit-brief.md``: Texas Hill Country and East Texas read
flat/hills (their steepest sustained mile tops out near 4.2%), while the
Grapevine, the Siskiyous, Monteagle, and Denver-Silverthorne stay mountain.
"""

from __future__ import annotations

# Steepness is a grade held for about a mile (a "sustained" grade), not an
# instantaneous pitch. Relief is the rise-and-fall of the ground nearby.
MTN_SUSTAIN_SOLO = 5.0   # a mile this steep is mountain on its own -- the East's
                         # escarpments (Monteagle, Sideling Hill, the Ozark ramp
                         # grades) run 5-8% at only 400-900 ft of relief, well
                         # above Texas Hill Country's 4.2% ceiling.
MTN_SUSTAIN_PCT = 4.0    # a shade less steep still counts as mountain...
MTN_RELIEF_FT = 1000.0   # ...when the surrounding relief is genuinely large.
BIG_RELIEF_FT = 2000.0   # or huge relief carrying repeated stiff pitches.
HILL_GRADE_PCT = 1.5     # a gentle sustained grade is hills...
HILL_RELIEF_FT = 400.0   # ...as is moderate relief with no real grade.

# Leg-level rollup from the classified stretches.
LEG_MTN_FRAC = 0.15      # this fraction mountain makes the leg a mountain leg...
LEG_MTN_MI = 6.0         # ...or this many mountain miles outright, so a real pass
                         # on a long haul still reads mountain (Monteagle's 7
                         # mountain miles on the 134-mile Chattanooga-Nashville run).
LEG_HILL_FRAC = 0.20     # hills+mountain fraction that makes the leg hills.

RANK = {"flat": 0, "hills": 1, "mountain": 2}


def terrain_for(steep_pct: float, relief_ft: float, pitches: int = 0) -> str:
    """Classify one stretch from its sustained steepness and nearby relief.

    ``steep_pct``  -- the steepest grade held ~a mile at/near this stretch.
    ``relief_ft``  -- max minus min ground elevation in the surrounding window.
    ``pitches``    -- repeated stiff (>= 3%) climbs in that window (optional).
    """
    steep = abs(steep_pct)
    if (
        steep >= MTN_SUSTAIN_SOLO
        or (steep >= MTN_SUSTAIN_PCT and relief_ft >= MTN_RELIEF_FT)
        or (relief_ft >= BIG_RELIEF_FT and pitches >= 2)
    ):
        return "mountain"
    if steep >= HILL_GRADE_PCT or relief_ft >= HILL_RELIEF_FT:
        return "hills"
    return "flat"


def leg_terrain(mtn_mi: float, hill_mi: float, leg_miles: float) -> str:
    """Roll stretch mileages up to a single leg label."""
    total = leg_miles or (mtn_mi + hill_mi) or 1.0
    if mtn_mi / total >= LEG_MTN_FRAC or mtn_mi >= LEG_MTN_MI:
        return "mountain"
    if (mtn_mi + hill_mi) / total >= LEG_HILL_FRAC:
        return "hills"
    return "flat"
