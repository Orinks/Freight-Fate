"""Re-derive state crossings and mileage from archived dense leg geometry.

Dry-run by default. Equal state sequences are updated only when a boundary
shifts by at least ``--min-shift``; ``--only`` explicitly overrides sequence
differences for the named legs.

    python tools/rederive_state_context.py [--only "a:b;c:d"] [--write]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import enrich_routes_states as ers  # noqa: E402
import leg_geometry as lg  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

ROUTE_POINT_AGREEMENT_MI = 5.0
STATE_CONTEXT_SOURCE = (
    "derived 2026-10-01: the leg's archived dense route geometry sampled against public "
    "U.S. state boundary GeoJSON; at_mi = cumulative geometry distance at each boundary "
    "change, rescaled to leg miles; state miles = differences of those boundaries."
)


def parse_only(value: str | None) -> set[str] | None:
    if value is None:
        return None
    return {item.strip() for item in value.split(";") if item.strip()}


def _leg_id(leg: dict[str, Any]) -> str:
    return f"{leg['from']}:{leg['to']}"


def _dense_geometry(
    leg: dict[str, Any],
) -> tuple[list[list[float]], str | None]:
    geometry = lg.corridor_geometry(leg)
    polyline = lg.archived_polyline(lg.leg_id_of(leg), lg.state_code_of(leg))
    if not geometry or not polyline:
        return [], "no dense archived geometry"

    max_off_mi = lg.route_point_max_off_mi(leg, polyline[0])
    if max_off_mi is None:
        return [], "route-point agreement could not be checked"
    if max_off_mi > ROUTE_POINT_AGREEMENT_MI:
        return [], f"route_points are {max_off_mi:.2f} mi from archive (limit 5.00)"

    coords = [[float(lon), float(lat)] for lat, lon, _at_mi in geometry]
    if len(coords) < 2:
        return [], "dense archived geometry has fewer than two vertices"
    return coords, None


def _state_sequence(crossings: list[dict[str, Any]], start_state: str) -> list[str]:
    if not crossings:
        return [start_state] if start_state else []
    states = [crossings[0].get("from_state")]
    states.extend(crossing.get("state") for crossing in crossings)
    return [str(state) for state in states if state]


def _max_crossing_shift(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> float:
    if len(old) != len(new):
        return float("inf")
    return max(
        (
            abs(float(before["at_mi"]) - float(after["at_mi"]))
            for before, after in zip(old, new, strict=True)
        ),
        default=0.0,
    )


def process_world(
    data: dict[str, Any],
    state_shapes: list[dict[str, Any]],
    *,
    min_shift: float = 1.0,
    only: set[str] | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "legs_total": len(data.get("legs", ())),
        "legs_scanned": 0,
        "guard_skipped": [],
        "geometry_skipped": [],
        "sequence_differs": [],
        "changed": [],
    }
    for leg in data.get("legs", ()):
        leg_id = _leg_id(leg)
        coords, skip_reason = _dense_geometry(leg)
        if skip_reason:
            entry = f"{leg_id}: {skip_reason}"
            if "route_points are" in skip_reason:
                report["guard_skipped"].append(entry)
            else:
                report["geometry_skipped"].append(entry)
            continue

        report["legs_scanned"] += 1
        corridor = leg.get("corridor") or {}
        old_state_miles = list(corridor.get("state_miles") or [])
        old_crossings = list(corridor.get("state_crossings") or [])
        derived = ers._state_context(data, leg, coords, state_shapes)
        new_crossings = [
            dict(item, source=STATE_CONTEXT_SOURCE) for item in derived["state_crossings"]
        ]
        new_state_miles = [
            dict(item, source=STATE_CONTEXT_SOURCE) for item in derived["state_miles"]
        ]

        start_state = ers.spoken_state(
            data, data.get("cities", {}).get(leg.get("from"), {}).get("state", "")
        )
        old_sequence = _state_sequence(old_crossings, start_state)
        new_sequence = _state_sequence(new_crossings, start_state)
        sequence_matches = old_sequence == new_sequence
        selected = only is not None and leg_id in only
        if not sequence_matches:
            report["sequence_differs"].append(
                {
                    "leg": leg_id,
                    "old": old_sequence,
                    "new": new_sequence,
                    "updated": selected,
                }
            )

        shift = _max_crossing_shift(old_crossings, new_crossings)
        should_update = selected or (sequence_matches and shift >= min_shift)
        if not should_update:
            continue

        if old_crossings == new_crossings and corridor.get("state_miles") == new_state_miles:
            continue
        leg.setdefault("corridor", {})["state_crossings"] = new_crossings
        leg["corridor"]["state_miles"] = new_state_miles
        report["changed"].append(
            {
                "leg": leg_id,
                "old_crossings": old_crossings,
                "new_crossings": new_crossings,
                "old_state_miles": old_state_miles,
                "new_state_miles": new_state_miles,
                "sequence_matches": sequence_matches,
            }
        )
    return report


def _format_report(report: dict[str, Any]) -> str:
    lines = [
        f"Legs: {report['legs_total']} total; {report['legs_scanned']} scanned; "
        f"{len(report['guard_skipped'])} skipped by agreement guard; "
        f"{len(report['geometry_skipped'])} skipped for missing/unusable geometry.",
        f"Changed legs: {len(report['changed'])}.",
        "Changed crossings:",
    ]
    for item in report["changed"]:
        lines.append(
            f"  {item['leg']} (sequence {'same' if item['sequence_matches'] else 'different'})"
        )
        lines.append(f"    old: {item['old_crossings']}")
        lines.append(f"    new: {item['new_crossings']}")
    lines.extend(
        [
            "Sequence differs:",
            *(
                f"  {item['leg']}: {item['old']} -> {item['new']}"
                f"{' (updated by --only)' if item['updated'] else ' (report only)'}"
                for item in report["sequence_differs"]
            ),
        ]
    )
    lines.extend(
        [
            "Skipped by agreement guard:",
            *(f"  {item}" for item in report["guard_skipped"]),
            "Skipped for geometry:",
            *(f"  {item}" for item in report["geometry_skipped"]),
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help='semicolon-separated "from:to" leg ids')
    parser.add_argument("--min-shift", type=float, default=1.0)
    parser.add_argument("--write", action="store_true", help="save changed world source")
    args = parser.parse_args(argv)

    data = load_world()
    state_shapes = ers._load_state_shapes(Path(".route-cache"), 1.0)
    report = process_world(
        data,
        state_shapes,
        min_shift=args.min_shift,
        only=parse_only(args.only),
    )
    print(_format_report(report))
    if args.write:
        print(f"Saved {save_world(data)} world-source files.")
    else:
        print("Dry run only; world source was not written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
