"""Load baked curve geometry from gameplay/curves.jsonl.

63,724 baked curve records (radius, direction, advisory speed) per leg,
loaded at runtime on first access and cached per leg pair.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .data_resources import read_data_text

CURVES_RESOURCE = "world_data/us/gameplay/curves.jsonl"


@dataclass(frozen=True)
class CurveRecord:
    """A single baked curve along a leg.

    All mile offsets are relative to the leg in the A->B direction; the
    Trip resolves them to trip miles at construction time.
    """

    start_mi: float
    apex_mi: float
    end_mi: float
    deflection_deg: float
    direction: str  # "L" or "R"
    min_radius_ft: float
    advisory_mph: float
    connector: bool = False

    @property
    def length_mi(self) -> float:
        return max(0.0, self.end_mi - self.start_mi)

    @property
    def is_sharp(self) -> bool:
        """True for curves that genuinely demand driver attention.

        A curve with a radius above ~3000 ft at highway speed is nearly
        straight; advisory speeds at or near the posted limit don't need
        special attention. Only curves below advisory 50 or radius < 2500 ft
        count as "sharp" enough to announce.
        """
        return self.advisory_mph < 50 or self.min_radius_ft < 2500.0

    @property
    def is_gentle(self) -> bool:
        """True for broad, high-speed curves that rarely need a spoken note."""
        return not self.is_sharp and not self.connector

    @property
    def spoken_direction(self) -> str:
        return "left" if self.direction == "L" else "right"

    @property
    def spoken_phrase(self) -> str:
        """Brief pacenote: 'sharp curve left' or 'curve right'."""
        prefix = "sharp " if self.is_sharp else ""
        return f"{prefix}curve {self.spoken_direction}"

    @property
    def severity(self) -> str:
        """Plain-language pacenote severity derived from the baked advisory."""
        if self.advisory_mph <= 25 or self.deflection_deg >= 150.0:
            return "hairpin"
        if self.advisory_mph <= 35:
            return "sharp"
        if self.advisory_mph <= 50:
            return "moderate"
        return "gentle"


# -- per-leg cache ---------------------------------------------------------------

_curves_cache: dict[str, tuple[CurveRecord, ...]] | None = None


def _load_all_curves() -> dict[str, tuple[CurveRecord, ...]]:
    """Load every curve from the JSONL, keyed by leg slug pair.

    Returns a dict mapping ``"from_city:to_city"`` to its sorted curve tuple.
    The leg key matches the ``leg`` field in the JSONL.
    """
    text = read_data_text(CURVES_RESOURCE)
    if text is None:
        return {}

    by_leg: dict[str, list[CurveRecord]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "meta" in raw:
            continue
        leg_key = str(raw.get("leg", ""))
        if not leg_key:
            continue
        record = CurveRecord(
            start_mi=float(raw.get("start_mi", 0.0)),
            apex_mi=float(raw.get("apex_mi", 0.0)),
            end_mi=float(raw.get("end_mi", 0.0)),
            deflection_deg=float(raw.get("deflection_deg", 0.0)),
            direction=str(raw.get("direction", "L")),
            min_radius_ft=float(raw.get("min_radius_ft", 99999.0)),
            advisory_mph=float(raw.get("advisory_mph", 70.0)),
            connector=bool(raw.get("connector", False)),
        )
        by_leg.setdefault(leg_key, []).append(record)

    # Sort each leg's curves by start_mi.
    result: dict[str, tuple[CurveRecord, ...]] = {}
    for leg_key, records in by_leg.items():
        records.sort(key=lambda c: c.start_mi)
        result[leg_key] = tuple(records)

    return result


def get_curves(leg_key: str) -> tuple[CurveRecord, ...]:
    """Return all curve records for a leg pair, cached globally."""
    global _curves_cache
    if _curves_cache is None:
        _curves_cache = _load_all_curves()
    return _curves_cache.get(leg_key, ())


def leg_curve_key(a: str, b: str) -> str:
    """Canonical leg key for the curve lookup, matching the JSONL format."""
    return f"{a}:{b}" if a < b else f"{b}:{a}"
