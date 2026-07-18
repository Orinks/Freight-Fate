"""Baked curve geometry for the pacenote layer.

Reads ``world_data/us/gameplay/curves.jsonl`` -- the per-curve steering
rows from the dense geometry sweep (one bake direction per leg; the
runtime mirrors records when a route traverses a leg b-to-a). Connector
rows (interchange and ramp arcs) are excluded here: ramps carry their own
speech and the future curve-nav layer owns them.

Severity bands come from the advisory speed the bake computed at 0.3 g
lateral -- the same number a posted yellow diamond would show -- with
deflection promoting true switchbacks to hairpins regardless of radius.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_SHARD = Path(__file__).parent / "world_data" / "us" / "gameplay" / "curves.jsonl"

HAIRPIN_MAX_MPH = 25
SHARP_MAX_MPH = 35
MODERATE_MAX_MPH = 50
HAIRPIN_DEFLECTION_DEG = 150.0


@dataclass(frozen=True)
class CurveRecord:
    """One mainline curve in bake direction, miles from leg city a."""

    start_mi: float
    apex_mi: float
    end_mi: float
    direction: str  # "L" | "R"
    advisory_mph: int
    min_radius_ft: int
    deflection_deg: float


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

    @property
    def severity(self) -> str:
        if (
            self.advisory_mph <= HAIRPIN_MAX_MPH
            or self.deflection_deg >= HAIRPIN_DEFLECTION_DEG
        ):
            return "hairpin"
        if self.advisory_mph <= SHARP_MAX_MPH:
            return "sharp"
        if self.advisory_mph <= MODERATE_MAX_MPH:
            return "moderate"
        return "gentle"


_CACHE: dict[str, tuple[CurveRecord, ...]] | None = None


def _load() -> dict[str, tuple[CurveRecord, ...]]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    by_leg: dict[str, list[CurveRecord]] = {}
    if _SHARD.exists():
        with _SHARD.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if "meta" in row or row.get("connector"):
                    continue
                by_leg.setdefault(row["leg"], []).append(
                    CurveRecord(
                        start_mi=row["start_mi"],
                        apex_mi=row["apex_mi"],
                        end_mi=row["end_mi"],
                        direction=row["direction"],
                        advisory_mph=row["advisory_mph"],
                        min_radius_ft=row["min_radius_ft"],
                        deflection_deg=row["deflection_deg"],
                    )
                )
    _CACHE = {key: tuple(rows) for key, rows in by_leg.items()}
    return _CACHE


def leg_curves(leg_key: str) -> tuple[CurveRecord, ...]:
    """Baked mainline curves for ``"a_slug:b_slug"``, bake direction."""
    return _load().get(leg_key, ())


_MIRROR = {"L": "R", "R": "L"}


def route_curves(route, cities: list[str]) -> tuple[RouteCurve, ...]:
    """Every mainline curve on the route, in travel order and direction.

    ``cities`` is the route's city sequence; each leg is mirrored when the
    route runs it b-to-a (offsets flip across the leg, left becomes right).
    """
    out: list[RouteCurve] = []
    leg_start = 0.0
    for from_city, leg in zip(cities, route.legs, strict=False):
        forward = from_city == leg.a
        for rec in leg_curves(f"{leg.a}:{leg.b}"):
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
                )
            )
        leg_start += leg.miles
    out.sort(key=lambda c: c.start_mi)
    return tuple(out)
