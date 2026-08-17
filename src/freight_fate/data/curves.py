"""Baked curve geometry for the pacenote layer.

Reads ``world_data/us/gameplay/curves.jsonl`` -- the per-curve steering
rows from the dense geometry sweep (one bake direction per leg; the
runtime mirrors records when a route traverses a leg b-to-a). Connector
rows (interchange and ramp arcs) are excluded here: ramps carry their own
speech and the future curve-nav layer owns them.

Severity bands come from the advisory speed the bake computed at 0.3 g
lateral -- the same number a posted yellow diamond would show -- with
deflection promoting true switchbacks to hairpins regardless of radius.

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

HAIRPIN_MAX_MPH = 25
SHARP_MAX_MPH = 35
MODERATE_MAX_MPH = 50
HAIRPIN_DEFLECTION_DEG = 150.0

# Interstate mainline geometry screen. The dense sweep baked some city
# departure geometry and interchange vertices as mainline rather than as
# connectors, which put 80-250 ft "hairpins" on roads that cannot bend that
# hard: an interstate is designed for 50 mph even in mountainous terrain, so
# its tightest real mainline curve is roughly 500-600 ft of radius (the
# notorious urban exceptions, posted 35, sit right about there). Anything
# under 300 ft, or turning more than a switchback's worth, is a digitizing
# artifact. Only the interstate class is screened -- US and state routes
# really do switch back (US-550 over Red Mountain Pass, US-40 in the
# Rockies) and their sharp records are kept exactly as baked.
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
        if self.advisory_mph <= HAIRPIN_MAX_MPH or self.deflection_deg >= HAIRPIN_DEFLECTION_DEG:
            return "hairpin"
        if self.advisory_mph <= SHARP_MAX_MPH:
            return "sharp"
        if self.advisory_mph <= MODERATE_MAX_MPH:
            return "moderate"
        return "gentle"


_CACHE: dict[str, tuple[CurveRecord, ...]] | None = None


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
                # Connector arcs (interchange ramps) stay in the data with
                # their flag: curve physics wants them, spoken layers skip
                # them -- ramps carry their own speech.
                by_leg.setdefault(row["leg"], []).append(
                    CurveRecord(
                        start_mi=row["start_mi"],
                        apex_mi=row["apex_mi"],
                        end_mi=row["end_mi"],
                        direction=row["direction"],
                        advisory_mph=row["advisory_mph"],
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
