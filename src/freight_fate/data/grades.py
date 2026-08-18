"""Load-time screen for elevation artifacts in the baked grade data.

All 146,496 grade segments in the world come from one place -- an
OpenRouteService route elevation profile over SRTM, segmented by terrain --
and a few hundred of them describe a slope no road of their class and terrain
can hold. 455 exceed 8 percent; the steepest is +14.4 percent on I-5. The tell
is the same one the curve sweep left behind: the extremes sit on 0.2 and 0.3
mile spans, which is the length of a bridge or an overpass, and a profile
crossing a structure reads the deck rather than the road under it.

WHY THIS SCREEN CANNOT COPY ``curves.py`` AND EXEMPT THE MOUNTAINS. There,
mountain terrain is never flagged, because a real switchback lives there. Here
the single worst record -- the I-5 14.4 -- is itself labelled ``mountain``,
and the label is coarse enough (3,098 segments carry it) that exempting it
would shelter most of the interstate artifacts. Road class replaces terrain as
the discriminator because it carries a harder fact: the interstate system is
designed to a 6 percent maximum, and the famously brutal exceptions -- I-70
west of Denver, I-17 out of Phoenix, I-80 over Donner -- sit at 6 to 7. There
is no 12 percent interstate. US and state routes really do climb harder
(US-550 over Red Mountain Pass, CA-299 through the Trinity Alps), so their
ceilings are set well above anything real and only catch the frankly
impossible.

WHY THIS ONE CLAMPS WHERE ``curves.py`` DROPS. Curves are discrete events and
a dropped one is simply never announced. Grades tile the leg continuously, and
``Trip.grade_at`` falls through to a synthesized terrain average for any mile
no segment covers -- so dropping a spike out of the middle of a real climb
would replace a measured-but-noisy reading with an invented one. Clamping
keeps the sign, keeps the climb, and caps the physics at what the road can
actually hold.

The bake is never edited (see the provenance rule in ``CLAUDE.md``). A clamped
segment records the adjustment in its own ``source``, so a later reader can
see that this value was derived here rather than read from the profile.
"""

from __future__ import annotations

from .world_models import GradeSegment

# Steepest sustained grade a road of each class is built to, in percent.
# Interstates are designed to 6; 7 leaves room for the handful of real
# mountain exceptions without admitting anything the class cannot hold. The
# other two are deliberately loose -- they exist to catch profile noise, not
# to argue with a genuinely severe US or state route pass.
CLASS_CEILING_PCT = {"interstate": 7.0, "us": 10.0, "state": 12.0}

# Ceiling implied by the bake's own terrain label, which is the other half of
# the self-contradiction: a segment calling itself flat cannot also be a
# 14 percent wall. Measured against the data, flat sits at 4.98 percent for
# its 99th percentile and hills at 7.61, so these cut the tail and nothing
# else. ``mountain`` gets a number only so the lookup is total; class governs
# there in every case that matters.
TERRAIN_CEILING_PCT = {"flat": 6.0, "hills": 8.0, "mountain": 12.0}

_CLAMP_NOTE = (
    " Slope clamped at load from {raw:+.2f} to {capped:+.2f} percent -- derived, not read: "
    "above the {ceiling:.0f} percent ceiling for {road_class} in {terrain} terrain "
    "(freight_fate.data.grades)."
)


def road_class(highway: str) -> str:
    """``interstate``, ``us`` or ``state`` from a leg's highway designation.

    Anything not designated ``I-n`` or ``US-n`` is treated as a state route,
    which is the loosest ceiling -- an unknown designation should never be
    screened harder than a known one.
    """
    name = (highway or "").strip().upper()
    if name.startswith("I-") and name[2:3].isdigit():
        return "interstate"
    if name.startswith("US-"):
        return "us"
    return "state"


def grade_ceiling_pct(highway: str, terrain: str) -> float:
    """The stricter of what the road class and the terrain label allow."""
    by_class = CLASS_CEILING_PCT[road_class(highway)]
    by_terrain = TERRAIN_CEILING_PCT.get(terrain, max(TERRAIN_CEILING_PCT.values()))
    return min(by_class, by_terrain)


def screen_grade_segments(
    segments: tuple[GradeSegment, ...], highway: str
) -> tuple[GradeSegment, ...]:
    """Cap slopes the road cannot hold, leaving every plausible one untouched.

    Returns the same objects where nothing was capped, so an unscreened world
    round-trips identically.
    """
    screened = []
    for segment in segments:
        ceiling = grade_ceiling_pct(highway, segment.terrain)
        if abs(segment.avg_grade_pct) <= ceiling:
            screened.append(segment)
            continue
        capped = ceiling if segment.avg_grade_pct > 0 else -ceiling
        note = _CLAMP_NOTE.format(
            raw=segment.avg_grade_pct,
            capped=capped,
            ceiling=ceiling,
            road_class=road_class(highway),
            terrain=segment.terrain,
        )
        screened.append(
            GradeSegment(
                segment.start_mi,
                segment.end_mi,
                capped,
                segment.terrain,
                (segment.source + note).strip(),
            )
        )
    return tuple(screened)
