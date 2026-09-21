"""Load-time screen for elevation artifacts in the baked grade data.

Almost all of the world's 144,431 grade segments come from one place -- an
OpenRouteService route elevation profile over SRTM, segmented by terrain --
and some of them describe a slope no road of their class and terrain can hold.
The tell is the same one the curve sweep left behind: the extremes sit on 0.2
and 0.3 mile spans, which is the length of a bridge or an overpass, and a
profile crossing a structure reads the deck rather than the road under it.

1,106 segments no longer come from that profile. On 2026-09-19 every span this
screen clamped was read a second time against USGS 3DEP, and where 3DEP
returned a slope the road class could hold, the segment was re-sourced to the
measurement and says so in its own ``source`` (``tools/screen_grades_3dep.py``).
That took the world from 455 segments over 8 percent to 141, and the count
this screen still clamps from 1,271 to 242.

What the re-read did NOT do is make this screen unnecessary, and the reason is
worth keeping: 165 of those spans came back with 3DEP CONFIRMING the profile
at 10 to 13 percent on roads that cannot hold it -- I-79 in West Virginia at
-13.4, for one. Two elevation models agree there because both read ground, and
the road is on a bridge above it. A second elevation source cannot see that.
The class ceiling is the only thing that does, which is why those 165 were left
for this screen rather than written into the bake.

WHY THIS SCREEN CANNOT COPY ``curves.py`` AND EXEMPT THE MOUNTAINS. There,
mountain terrain is never flagged, because a real switchback lives there. Here
the worst record left after the 3DEP re-read -- I-68 at 14.0 between
Morgantown and Cumberland -- sits on a leg labelled ``mountain``, and the
label is coarse enough (3,098 segments carry it) that exempting it would
shelter most of the interstate artifacts. Road class replaces terrain as
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

# Ceiling implied by terrain, which is the other half of the
# self-contradiction: a segment on level ground cannot also be a 14 percent
# wall. Measured against the data, flat sits at 4.98 percent for its 99th
# percentile and hills at 7.61, so these cut the tail and nothing else.
# ``mountain`` gets a number only so the lookup is total; class governs there
# in every case that matters.
TERRAIN_CEILING_PCT = {"flat": 6.0, "hills": 8.0, "mountain": 12.0}

# WHICH terrain, though. The bake's own label is derived from net elevation
# change end to end and is wrong often enough to matter: checked against FHWA
# HPMS Terrain_Type over 1,273 legs it agreed on only 67 percent, and the
# worst records in the world sit on legs the label calls ``mountain``
# (ceiling 12) while HPMS calls that ground LEVEL.
#
# So the HPMS class leads where it exists, and the segment's own label is the
# fallback. HPMS speaks in Green Book terms; these are its names in ours.
#
# The cost of that, measured: HPMS returns ONE verdict for a whole leg, so
# US-160 over Wolf Creek Pass, US-101 through the redwoods and US-20 over
# Santiam all come back ``level`` across 500 to 800 sections. Before the 3DEP
# re-read that held 96 real grades down to 6 percent. The re-read fixed those
# by measuring them; the rule is unchanged because loosening it was scored
# against those same readings and let 386 to 543 artifacts through.
HPMS_TERRAIN_TO_LABEL = {1: "flat", 2: "hills", 3: "mountain"}

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
    """The stricter of what the road class and the terrain allow."""
    by_class = CLASS_CEILING_PCT[road_class(highway)]
    by_terrain = TERRAIN_CEILING_PCT.get(terrain, max(TERRAIN_CEILING_PCT.values()))
    return min(by_class, by_terrain)


def screen_grade_segments(
    segments: tuple[GradeSegment, ...],
    highway: str,
    hpms_terrain: int | None = None,
) -> tuple[GradeSegment, ...]:
    """Cap slopes the road cannot hold, leaving every plausible one untouched.

    Returns the same objects where nothing was capped, so an unscreened world
    round-trips identically.
    """
    # HPMS leads where the leg has a class; the segment's own label is the
    # fallback, and stays the fallback rather than being overwritten, so a
    # leg HPMS never classified screens exactly as it did before.
    leg_terrain = HPMS_TERRAIN_TO_LABEL.get(hpms_terrain) if hpms_terrain else None
    screened = []
    for segment in segments:
        ceiling = grade_ceiling_pct(highway, leg_terrain or segment.terrain)
        if abs(segment.avg_grade_pct) <= ceiling:
            screened.append(segment)
            continue
        capped = ceiling if segment.avg_grade_pct > 0 else -ceiling
        note = _CLAMP_NOTE.format(
            raw=segment.avg_grade_pct,
            capped=capped,
            ceiling=ceiling,
            road_class=road_class(highway),
            terrain=leg_terrain or segment.terrain,
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
