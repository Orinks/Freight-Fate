"""Baked curve geometry for the pacenote layer.

Reads ``world_data/us/gameplay/curves.jsonl`` -- the per-curve steering
rows from the dense geometry sweep (one bake direction per leg; the
runtime mirrors records when a route traverses a leg b-to-a). Connector
rows (interchange and ramp arcs) are excluded here: ramps carry their own
speech and the future curve-nav layer owns them.

Severity bands come from the advisory speed the bake computed at 0.3 g
lateral -- the same number a posted yellow diamond would show -- EXCEPT the
hairpin, which is a shape rather than a speed and is decided by deflection
alone (see ``HAIRPIN_DEFLECTION_DEG``).

Interstate mainline records are screened for sweep artifacts on the way in
(see ``INTERSTATE_MIN_RADIUS_FT``); the raw bake keeps every row.

US and state routes get a second, narrower screen: sweep artifacts also
land on non-interstate mainline (the same city-departure kink that hits an
interstate can ride the US-route out of the same city), but road class
alone cannot tell those apart from a real switchback -- US-550 and the Salt
River Canyon really are that sharp. ``curve_artifacts.jsonl``
(``tools/screen_curve_artifacts.py``) names the specific ``(leg, seq)``
records an offline check flagged: flat local ground where no real hairpin
can exist, city-departure geometry at a leg's ends off the mountains, and a
radius no through highway of any class can bend to. Everything else, sharp
or not, is left alone -- nothing in mountain terrain is ever flagged.

A third screen applies to mainline of every class and asks only whether a
record agrees with itself: a bend's recorded span has to be able to hold the
arc its own radius and deflection describe, and opposite-direction curves
cannot meet with no straight between them. Terrain cannot excuse either, so
unlike the two above, this one does look at mountain roads -- which is where
it was found (``ARC_CONSISTENCY_MIN``).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

from .data_resources import read_data_text

# The advisory at or below which a curve is an EXTREME CLAIM about the road,
# used by the artifact screens to ask "could a road here really do this?".
# Deliberately not the spoken hairpin test -- see HAIRPIN_DEFLECTION_DEG.
HAIRPIN_MAX_MPH = 25
SHARP_MAX_MPH = 35
MODERATE_MAX_MPH = 50
# What actually makes a hairpin, from the sign that names one. MUTCD gives
# the Hairpin Curve sign (W1-11) for a change in horizontal alignment of 135
# degrees or more -- a switchback, where the road comes back on itself. The
# advisory speed does not enter into it: MUTCD sorts curves by advisory
# separately and much lower down, using the Turn sign (W1-1) instead of the
# Curve sign at 30 mph or less.
#
# This used to read "advisory <= 25 OR deflection >= 150", and the advisory
# half was doing real damage. Across 33,930 baked curves it labelled 159
# hairpins where only 99 turn 135 degrees or more; the other 60 were tight
# little bends taken slowly, and the worst of them deflect TEN degrees. A
# driver was being told "hairpin left" for a road that barely bends, which
# spends the word on nothing and leaves it meaning less when a real
# switchback arrives. Darren asked whether a 94-degree corner through
# Norwich on NY-12 was "supposed to be there" (2026-08-23); the corner was,
# the word was not.
#
# The angle is necessary and NOT sufficient, which the data made plain. MUTCD
# says the hairpin sign goes up INSTEAD OF A TURN OR CURVE SIGN, and it is
# the Turn sign (advisory 30 or less) that a switchback would otherwise
# carry. Taking the angle alone put 7 hairpins on interstate mainline --
# among them a 143-degree bend on I-49 north of Fayetteville with an 811 ft
# radius and a 60 mph advisory. That is a real half-circle of road and a
# sweeping one; no driver calls it a hairpin, because you do not slow for it.
#
# Both together give 46 hairpins in 33,930 curves and NONE on an interstate,
# which is the check on the rule rather than a target it was fitted to:
# interstates do not switchback, and the rule works that out on its own.
HAIRPIN_TURN_MAX_MPH = 30
HAIRPIN_DEFLECTION_DEG = 135.0

# Interstate mainline geometry screen. The dense sweep baked some city
# departure geometry and interchange vertices as mainline rather than as
# connectors, which put 80-250 ft "hairpins" on roads that cannot bend that
# hard. Anything under 300 ft, or turning more than a switchback's worth, is
# a digitizing artifact.
#
# 300 is deliberately far below the DESIGN floor, and the difference is not
# slack -- it is Glenwood Canyon. TxDOT Roadway Design Manual Table 4-7 puts
# the minimum radius for a 50 mph design speed at 758 ft, and 50 mph is the
# lowest the Interstate system designs to; raising this constant to 758
# accordingly reads well and deletes real road, because I-70 through the
# canyon really does bend tighter than standard under design exceptions
# (tried and reverted, 2026-08-23 -- test_glenwood_canyon_interstate_curves
# _survive is what caught it). A screen sized to the design floor cannot
# tell a design exception from an artifact.
#
# The design floor IS applied, by the fourth screen below, and only where the
# ground cannot justify a tight bend: `_screenable_legs` gives every LEVEL
# leg a floor of `min_radius_ft(its own design speed)`. That is the same
# number, spent where it is safe to spend.
#
# Only the interstate class is screened here -- US and state routes really do
# switch back (US-550 over Red Mountain Pass, US-40 in the Rockies) and their
# sharp records are kept exactly as baked.
INTERSTATE_MIN_RADIUS_FT = 300
INTERSTATE_MAX_DEFLECTION_DEG = 150.0


# Geometry self-consistency screen, applied to mainline of every class.
#
# The two screens above ask "could a road of this class bend this hard?" and
# "does the ground under it allow a hairpin?". Both deliberately leave
# mountain terrain alone, because that is where real switchbacks live. This
# third screen asks something neither does and that terrain cannot excuse:
# does the record agree with ITSELF?
#
# A curve of radius R turning theta has an arc length of R*theta. The
# recorded start-to-end span is measured along the same road, so a healthy
# record spans at least its own arc -- the median mainline row comes in at
# 1.22x. A row spanning a small fraction of that is not a bend the sweep
# measured; it is two adjacent route points with a kink between them, and no
# amount of real mountain justifies it.
#
# Found on US-285 north of Santa Fe (owner playtest, 2026-08-17): a 160 ft
# "hairpin" turning 79.9 degrees over 53 feet of road, where that geometry
# needs 223. It sat in mountain terrain, so both existing screens correctly
# passed it, and the pacenote layer called a 25 mph hairpin on a road posted
# 35.
ARC_CONSISTENCY_MIN = 0.1
# What a row with no usable radius/deflection reports: comfortably passing,
# so an incomplete record is never dropped on arithmetic it never supplied.
_CONSISTENT_ENOUGH = 9.9

# The same artifact's other signature, and the one that caught the US-285
# case: a digitized kink shows up as opposite-direction curves with NO
# tangent between them. A real reversal at this radius has straight road in
# between -- a through highway cannot swap lock at a point. Both sides of the
# zig-zag go, not just the arithmetically worst one, because the wiggle is
# spurious as a whole: the road does not really go left-right-left there.
ZIGZAG_MAX_TANGENT_FT = 1.0
ZIGZAG_MAX_RADIUS_FT = 400
# One side must also fail arithmetic, at a looser bar than ARC_CONSISTENCY_MIN
# -- an abrupt reversal alone is suggestive, not proof, and compound S-curves
# are real.
ZIGZAG_ARC_MAX = 0.5


@dataclass(frozen=True)
class CurveRecord:
    """One baked curve in bake direction, miles from leg city a."""

    start_mi: float
    apex_mi: float
    end_mi: float
    direction: str  # "L" | "R"
    advisory_mph: int
    min_radius_ft: int
    deflection_deg: float
    connector: bool = False


@dataclass(frozen=True)
class RouteCurve:
    """A curve mapped onto route miles, in the direction of travel."""

    start_mi: float
    apex_mi: float
    end_mi: float
    direction: str  # "L" | "R"
    advisory_mph: int
    min_radius_ft: int
    deflection_deg: float
    connector: bool = False

    @property
    def severity(self) -> str:
        if (
            self.deflection_deg >= HAIRPIN_DEFLECTION_DEG
            and self.advisory_mph <= HAIRPIN_TURN_MAX_MPH
        ):
            return "hairpin"
        if self.advisory_mph <= SHARP_MAX_MPH:
            return "sharp"
        if self.advisory_mph <= MODERATE_MAX_MPH:
            return "moderate"
        return "gentle"


_CACHE: dict[str, tuple[CurveRecord, ...]] | None = None


# The AASHTO point-mass control, which is what every state design manual
# republishes: Rmin = V^2 / [15(0.01*emax + fmax)]  (FHWA-HRT-17-098, ch. 3;
# Green Book table 3-7 supplies fmax). This is COMPUTED from the published
# formula rather than a table typed in from memory, and the values it
# produces are checked against the TxDOT Roadway Design Manual's own tables
# 4-6 and 4-7 by test_the_radius_floor_matches_published_design_tables --
# an earlier pass of this screen used 1,330 ft as the interstate floor, which
# is in fact the SIXTY mph minimum, and let a design-speed step of bad
# geometry through.
AASHTO_SIDE_FRICTION = {
    20: 0.27,
    25: 0.23,
    30: 0.20,
    35: 0.18,
    40: 0.16,
    45: 0.15,
    50: 0.14,
    55: 0.13,
    60: 0.12,
    65: 0.11,
    70: 0.10,
    75: 0.09,
    80: 0.08,
}
# 8 percent is the most permissive superelevation any state builds to, so a
# curve under this floor is under EVERY standard, not merely under a strict
# one. Snow states cap at 6 percent and could justify a stricter screen; the
# looser number is the one that keeps this a screen for the impossible
# rather than a screen for the unusual.
SUPERELEVATION_MAX = 0.08


def min_radius_ft(design_speed_mph: float) -> float:
    """Tightest radius a road of this design speed may legally bend to."""
    speeds = sorted(AASHTO_SIDE_FRICTION)
    v = min(speeds, key=lambda s: abs(s - design_speed_mph))
    return (v * v) / (15.0 * (SUPERELEVATION_MAX + AASHTO_SIDE_FRICTION[v]))


# What the bake priced its advisory at: a comfortable lateral for a loaded
# truck, on a FLAT road (tools/straw_curve_sample.py, A_LAT_G).
ADVISORY_LATERAL_G = 0.30
# The bank a road is actually BUILT with, which is not the same question as
# the bank a road is ALLOWED. SUPERELEVATION_MAX above is 8 percent because
# the screen asks "is this curve under every standard anywhere" and wants the
# most permissive number. Crediting a curve with the full 8 would assume the
# steepest bank any state permits on every road in the country, and reading
# more bank than a road has reads out a higher safe speed than it has -- an
# error in the one direction that matters.
#
# Both manuals name the built rate and both say 6: TxDOT 4.7.3, "The
# Department normally uses a maximum superelevation rate of 6 percent",
# 8 only "where higher superelevation rates or sharper curves are desired"
# and only with a District Design Engineer's sign-off. Iowa DOT 2B-2, "For
# new construction, the superelevation rate is limited to 6%", reserving 8
# as the state ceiling.
SUPERELEVATION_BUILT = 0.06


def superelevation_at(radius_ft: float, design_speed_mph: float) -> float:
    """The bank a designer had to build to hold the design speed here.

    Zero where friction alone carries it -- a gentle curve gets normal crown
    -- and never above ``SUPERELEVATION_BUILT``, the rate roads are built to
    rather than the steeper one they are permitted.

    DERIVED, not surveyed: nothing in the bake records a real cross-slope, so
    this is the bank the governing equation demands, e = V^2/15R - f. AASHTO
    Method 5, which TxDOT Tables 4-6 and 4-7 are computed with, lays MORE
    bank than this on gentle curves and the same at the minimum radius -- so
    this reads low where it barely matters and true where it does, and every
    error runs toward caution.
    """
    if radius_ft <= 0.0 or design_speed_mph <= 0.0:
        return 0.0
    speeds = sorted(AASHTO_SIDE_FRICTION)
    v = min(speeds, key=lambda s: abs(s - design_speed_mph))
    needed = design_speed_mph**2 / (15.0 * radius_ft) - AASHTO_SIDE_FRICTION[v]
    return max(0.0, min(SUPERELEVATION_BUILT, needed))


def advisory_with_bank_mph(radius_ft: float, design_speed_mph: float) -> int:
    """The advisory the bake would have given had it known about the bank.

    The bake reads every curve as flat -- ``sqrt(0.30 g R)`` -- which throws
    away the e in the manual's own e + f = V^2/15R and understates every
    banked curve. On a 1,000 ft radius that is 67 mph read as safe against a
    designed-and-banked 75, and it is why trucks braked for interstate curves
    built to be taken at speed.

    Rounded to 5 like the bake's own, so the two are directly comparable.
    """
    if radius_ft <= 0.0:
        return 0
    e = superelevation_at(radius_ft, design_speed_mph)
    return int(round(math.sqrt(15.0 * radius_ft * (e + ADVISORY_LATERAL_G)) / 5.0) * 5)


# Which legs the screen may judge at all. It needs to know whether a tight
# bend is the road or an artifact, and that is a question about terrain.
#
# TWO PROXIES WERE TRIED AND BOTH FAILED, which is why this reads a bake:
#
#   1. The world's own ``terrain`` field. Derived from NET elevation change
#      end to end, so a road that climbs and drops all the way along without
#      getting anywhere reads as flat -- I-70 through Glenwood Canyon is
#      tagged "flat", and screening on it took 21 real curves off the canyon.
#   2. Feet of elevation range per mile. Calibrated against HPMS Terrain_Type
#      over a 92-leg sample and measured WEAK: Youden's J of 0.29, and at the
#      threshold it suggested it mislabelled 54 percent of rolling and
#      mountainous legs. A number tuned until it looked right, which is
#      exactly what AGENTS.md says not to ship.
#
# So the terrain class is read rather than guessed: FHWA HPMS Terrain_Type,
# baked per leg by tools/build_terrain_type.py. Only HPMS level ground is
# screened. A leg HPMS calls rolling or mountainous keeps every curve it has,
# and so does a leg HPMS has nothing to say about -- absence is not evidence
# of flatness, and the safe direction here is a curve too many.
HPMS_TERRAIN_LEVEL = 1


def _leg_is_level(leg) -> bool:
    """True only where HPMS itself says the ground is level."""
    terrain = getattr(leg, "hpms_terrain", None)
    return bool(terrain) and terrain.type == HPMS_TERRAIN_LEVEL


def _leg_design_speed(leg) -> float:
    """The speed this leg is built for, from its own baked limits.

    The posted limit is the honest stand-in for design speed and it is real
    data here -- OSM maxspeed swept per corridor -- so the floor follows the
    road instead of a guess about its class. The fastest posting on the leg
    is the one that matters: a curve has to be safe at the speed the road
    lets a truck reach. Legs with no baked limit fall back to the class
    default the runtime already uses elsewhere.
    """
    # A sample can carry a null mph (a posting the sweep found but could not
    # read); those say nothing about design speed and must not be compared.
    limits = [
        s.mph for s in getattr(leg, "speed_limits", ()) if s is not None and s.mph is not None
    ]
    if limits:
        return max(limits)
    highway = (leg.highway or "").upper()
    if highway.startswith("I-"):
        return 70.0
    return 55.0 if highway.startswith("US") else 45.0


def _screenable_legs() -> dict[str, float]:
    """``"a:b"`` -> radius floor, for legs flat enough to judge. Absent key
    means "do not screen this leg's curves"."""
    from .world import get_world

    out: dict[str, float] = {}
    for leg in get_world().legs:
        if not _leg_is_level(leg):
            continue
        floor = min_radius_ft(_leg_design_speed(leg))
        out[f"{leg.a}:{leg.b}"] = floor
        out[f"{leg.b}:{leg.a}"] = floor
    return out


# Below this the road is built to normal crown and the flat reading is the
# right one. TxDOT Table 4-3 splits exactly here: low-speed facilities (45 and
# below) distribute superelevation by AASHTO Method 2, which "only introduces
# superelevation after the maximum side friction has been used" and in
# practice leaves town streets unbanked; 50 and above use Method 5 and are
# banked as a matter of course.
BANKED_DESIGN_MIN_MPH = 50.0


def _leg_design_speeds() -> dict[str, float]:
    """``"a:b"`` -> the speed the leg is built for, for EVERY leg.

    ``_screenable_legs`` answers the same question but only for level ground,
    because that screen has no business judging a mountain road. The bank
    applies everywhere, so it needs its own pass.
    """
    from .world import get_world

    out: dict[str, float] = {}
    for leg in get_world().legs:
        design = _leg_design_speed(leg)
        out[f"{leg.a}:{leg.b}"] = design
        out[f"{leg.b}:{leg.a}"] = design
    return out


def _banked_advisory(row: dict, design_mph: float | None) -> int:
    """The row's advisory, corrected for the bank its road must carry."""
    baked = row["advisory_mph"]
    if design_mph is None or design_mph < BANKED_DESIGN_MIN_MPH:
        return baked
    radius = row.get("min_radius_ft") or 0.0
    if radius <= 0.0:
        return baked
    # Only ever upward: the bake read the road flat, and a bank can only help.
    # A curve that somehow reads slower banked than flat keeps the flat number
    # rather than being quietly slowed by a correction meant to speed it up.
    return max(baked, advisory_with_bank_mph(radius, design_mph))


def _is_flat_ground_artifact(row: dict, floor: float) -> bool:
    """A bend tighter than its own road may legally hold, on level ground.

    The owner's report, 2026-08-19: "when I'm cruising down the highway or
    turnpike in a car, it hardly ever curves." Measured, the map disagreed
    with the road: interstate curve callouts ran 5.7 per hundred miles and
    the median interstate curve radius sat at 1,342 ft against an 1,815 ft
    floor for a 70 mph road.

    The tell is the record disagreeing with ITSELF, which is why this needs
    both halves -- a radius under the floor AND ground HPMS calls level.
    Rough country earns a tight bend and keeps it.
    """
    return row["min_radius_ft"] < floor


def _interstate_leg_keys() -> frozenset[str]:
    """``"a:b"`` keys, both directions, for interstate-class legs."""
    # Imported inside the function: the world module is heavy and has no need
    # of curve data, so the dependency is kept one-way.
    from .world import get_world

    keys: set[str] = set()
    for leg in get_world().legs:
        if (leg.highway or "").upper().startswith("I-"):
            keys.add(f"{leg.a}:{leg.b}")
            keys.add(f"{leg.b}:{leg.a}")
    return frozenset(keys)


def _is_interstate_artifact(row: dict) -> bool:
    """True for a record no interstate mainline could physically hold."""
    return (
        row["min_radius_ft"] < INTERSTATE_MIN_RADIUS_FT
        or row["deflection_deg"] >= INTERSTATE_MAX_DEFLECTION_DEG
    )


def arc_consistency(record: CurveRecord) -> float:
    """Recorded span as a multiple of the arc this bend's own geometry needs.

    1.0 means the span exactly holds the curve; the median mainline record is
    1.22. Below 1 the record is describing a turn sharper than the road it
    claims to occupy. Returns a large number when radius or deflection is
    missing, so an incomplete row is never screened out on arithmetic it
    never supplied.
    """
    need = record.min_radius_ft * math.radians(record.deflection_deg)
    if need <= 0.0:
        return _CONSISTENT_ENOUGH
    span_ft = (record.end_mi - record.start_mi) * 5280.0
    return span_ft / need


def _screen_geometry(records: list[CurveRecord]) -> list[CurveRecord]:
    """Drop mainline rows that contradict their own geometry.

    Two rules, both blind to road class and terrain -- see
    ``ARC_CONSISTENCY_MIN`` and ``ZIGZAG_MAX_TANGENT_FT``. Connectors are
    exempt, matching the screens above: a ramp really does bend that hard,
    and its arcs are recorded against a different baseline.

    Together these drop about 2.3% of surviving mainline rows.
    """
    mainline = sorted(
        (r for r in records if not r.connector), key=lambda r: (r.start_mi, r.apex_mi)
    )
    doomed: set[int] = set()
    for i, record in enumerate(mainline):
        if arc_consistency(record) < ARC_CONSISTENCY_MIN:
            doomed.add(i)
    for i, (left, right) in enumerate(zip(mainline, mainline[1:], strict=False)):
        if left.direction == right.direction:
            continue
        if (right.start_mi - left.end_mi) * 5280.0 > ZIGZAG_MAX_TANGENT_FT:
            continue
        if min(left.min_radius_ft, right.min_radius_ft) > ZIGZAG_MAX_RADIUS_FT:
            continue
        if min(arc_consistency(left), arc_consistency(right)) >= ZIGZAG_ARC_MAX:
            continue
        doomed.add(i)
        doomed.add(i + 1)
    kept = [r for i, r in enumerate(mainline) if i not in doomed]
    kept.extend(r for r in records if r.connector)
    kept.sort(key=lambda r: (r.start_mi, r.apex_mi))
    return kept


def _flagged_artifact_keys() -> frozenset[tuple[str, int]]:
    """``(leg, seq)`` pairs the US/state-route artifact screen flagged.

    Baked offline by ``tools/screen_curve_artifacts.py`` -- see that tool's
    docstring for the three discriminators (flat local ground under a
    hairpin-severity curve, city-departure geometry at a leg's ends off the
    mountains, and a radius no through highway of any class can bend to).
    Missing file reads as "nothing flagged" rather than an error, the same
    fail-open the interstate screen takes when curves.jsonl itself is absent.
    """
    text = read_data_text("world_data/us/gameplay/curve_artifacts.jsonl")
    if text is None:
        return frozenset()
    keys: set[tuple[str, int]] = set()
    for line in text.splitlines():
        if line.strip():
            row = json.loads(line)
            if "meta" in row:
                continue
            keys.add((row["leg"], row["seq"]))
    return frozenset(keys)


def _load() -> dict[str, tuple[CurveRecord, ...]]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    by_leg: dict[str, list[CurveRecord]] = {}
    text = read_data_text("world_data/us/gameplay/curves.jsonl")
    if text is not None:
        interstate_legs = _interstate_leg_keys()
        flagged_artifacts = _flagged_artifact_keys()
        screenable = _screenable_legs()
        design_speeds = _leg_design_speeds()
        for line in text.splitlines():
            if line.strip():
                row = json.loads(line)
                if "meta" in row:
                    continue
                connector = bool(row.get("connector", False))
                # Screen sweep artifacts off interstate mainline before they
                # can reach any consumer: a bogus hairpin call, a physics
                # shove, and a time-decompression stall all read the same
                # records. Ramps are exempt -- they really are that sharp.
                if not connector and row["leg"] in interstate_legs and _is_interstate_artifact(row):
                    continue
                # Second screen: US/state-route mainline records an offline
                # terrain check flagged as sitting on flat ground (see
                # _flagged_artifact_keys). Keyed by (leg, seq) rather than a
                # runtime rule, because the discriminator needs the dense
                # elevation archive this loader has no reason to carry.
                if not connector and (row["leg"], row.get("seq")) in flagged_artifacts:
                    continue
                # Fourth screen: any class, any route -- a bend tighter than
                # the road's own design speed allows, on ground with no
                # relief to justify it. See _is_flat_ground_artifact.
                floor = screenable.get(row["leg"])
                if not connector and floor is not None and _is_flat_ground_artifact(row, floor):
                    continue
                # Connector arcs (interchange ramps) stay in the data with
                # their flag: curve physics wants them, spoken layers skip
                # them -- ramps carry their own speech.
                by_leg.setdefault(row["leg"], []).append(
                    CurveRecord(
                        start_mi=row["start_mi"],
                        apex_mi=row["apex_mi"],
                        end_mi=row["end_mi"],
                        direction=row["direction"],
                        advisory_mph=_banked_advisory(row, design_speeds.get(row["leg"])),
                        min_radius_ft=row["min_radius_ft"],
                        deflection_deg=row["deflection_deg"],
                        connector=connector,
                    )
                )
    # Third screen, needing neighbours and so running per leg once the rows
    # are gathered rather than line by line above.
    _CACHE = {key: tuple(_screen_geometry(rows)) for key, rows in by_leg.items()}
    return _CACHE


def leg_curves(leg_key: str, mainline_only: bool = True) -> tuple[CurveRecord, ...]:
    """Baked curves for ``"a_slug:b_slug"``, bake direction. Connector
    arcs are excluded unless asked for."""
    rows = _load().get(leg_key, ())
    if mainline_only:
        return tuple(r for r in rows if not r.connector)
    return rows


_MIRROR = {"L": "R", "R": "L"}


def route_curves(route, cities: list[str], mainline_only: bool = True) -> tuple[RouteCurve, ...]:
    """Every curve on the route, in travel order and direction.

    ``cities`` is the route's city sequence; each leg is mirrored when the
    route runs it b-to-a (offsets flip across the leg, left becomes right).
    Pass ``mainline_only=False`` to keep connector arcs for physics.
    """
    out: list[RouteCurve] = []
    leg_start = 0.0
    for from_city, leg in zip(cities, route.legs, strict=False):
        forward = from_city == leg.a
        for rec in leg_curves(f"{leg.a}:{leg.b}", mainline_only=mainline_only):
            if forward:
                start, apex, end = rec.start_mi, rec.apex_mi, rec.end_mi
                direction = rec.direction
            else:
                start = leg.miles - rec.end_mi
                apex = leg.miles - rec.apex_mi
                end = leg.miles - rec.start_mi
                direction = _MIRROR[rec.direction]
            out.append(
                RouteCurve(
                    start_mi=leg_start + start,
                    apex_mi=leg_start + apex,
                    end_mi=leg_start + end,
                    direction=direction,
                    advisory_mph=rec.advisory_mph,
                    min_radius_ft=rec.min_radius_ft,
                    deflection_deg=rec.deflection_deg,
                    connector=rec.connector,
                )
            )
        leg_start += leg.miles
    out.sort(key=lambda c: c.start_mi)
    return tuple(out)
