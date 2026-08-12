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
"""

from __future__ import annotations

import json
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
    _CACHE = {key: tuple(rows) for key, rows in by_leg.items()}
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
