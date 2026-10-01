"""Re-derive state crossings and mileage from archived dense leg geometry.

Dry-run by default. Equal state sequences are updated only when a boundary
shifts by at least ``--min-shift``; ``--only`` explicitly overrides sequence
differences for the named legs.

    python tools/rederive_state_context.py [--only "a:b;c:d"] [--write]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import enrich_routes_states as ers  # noqa: E402
import leg_geometry as lg  # noqa: E402
import straw_curve_sample as scs  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

ROUTE_POINT_AGREEMENT_MI = 5.0
BOUNDARIES_CACHE = ROOT / ".route-cache" / "osm_state_boundaries.json"
GRID_CELL_DEG = 0.05
EVENT_MERGE_MI = 20.0 / 1609.344
INTERSECTION_EPSILON = 1e-10
PARALLEL_EPSILON = 1e-16
STALE_PUBLICAMUNDI_SOURCE = (
    "derived 2026-10-01: the leg's archived dense route geometry sampled against public U.S. "
    "state boundary GeoJSON; at_mi = cumulative geometry distance at each boundary change, "
    "rescaled to leg miles; state miles = differences of those boundaries."
)
STATE_CONTEXT_SOURCE = (
    "derived 2026-10-01: the leg's archived dense route geometry intersected with OpenStreetMap "
    "U.S. state boundary relations (boundary=administrative, admin_level=4); at_mi = cumulative "
    "geometry distance at each boundary crossing, rescaled to leg miles; state miles = "
    "differences of those boundaries. OpenStreetMap, Geofabrik us-latest extract 2026-09-29: "
    "https://www.openstreetmap.org/."
)


@dataclass
class StateBoundaryIndex:
    segments: list[tuple[str, float, float, float, float]]
    grid: dict[tuple[int, int], list[int]]
    edges_by_state: dict[str, list[tuple[float, float, float, float]]]
    bboxes: dict[str, tuple[float, float, float, float]]


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


def load_state_boundaries(cache_path: Path = BOUNDARIES_CACHE) -> list[dict[str, Any]]:
    if not cache_path.exists():
        raise FileNotFoundError(
            f"no OSM state-boundary cache at {cache_path} — run "
            "uv run --group tooling python tools/extract_osm_state_boundaries.py "
            "--pbf ~/osm/us-latest.osm.pbf"
        )
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    states = payload.get("states")
    if not isinstance(states, list) or not states:
        raise ValueError(f"no states in OSM boundary cache: {cache_path}")
    return states


def build_boundary_index(states: list[dict[str, Any]]) -> StateBoundaryIndex:
    segments: list[tuple[str, float, float, float, float]] = []
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    edges_by_state: dict[str, list[tuple[float, float, float, float]]] = defaultdict(list)
    bboxes: dict[str, tuple[float, float, float, float]] = {}

    def add_cells(segment_id: int, x1: float, y1: float, x2: float, y2: float) -> None:
        x_min, x_max = sorted((x1, x2))
        y_min, y_max = sorted((y1, y2))
        for cell_x in range(
            math.floor(x_min / GRID_CELL_DEG), math.floor(x_max / GRID_CELL_DEG) + 1
        ):
            for cell_y in range(
                math.floor(y_min / GRID_CELL_DEG), math.floor(y_max / GRID_CELL_DEG) + 1
            ):
                grid[(cell_x, cell_y)].append(segment_id)

    for state in states:
        name = str(state["name"])
        coordinates = [
            (float(point[0]), float(point[1])) for way in state.get("ways", []) for point in way
        ]
        if not coordinates:
            continue
        longitudes = [point[0] for point in coordinates]
        latitudes = [point[1] for point in coordinates]
        bboxes[name] = (min(longitudes), min(latitudes), max(longitudes), max(latitudes))

        for way in state.get("ways", []):
            for first, second in zip(way, way[1:], strict=False):
                lon1, lat1 = float(first[0]), float(first[1])
                lon2, lat2 = float(second[0]), float(second[1])
                lon_delta = (lon2 - lon1 + 180.0) % 360.0 - 180.0
                unwrapped_lon2 = lon1 + lon_delta
                edges_by_state[name].append((lon1, lat1, unwrapped_lon2, lat2))
                for offset in (-360.0, 0.0, 360.0):
                    shifted_x1 = lon1 + offset
                    shifted_x2 = unwrapped_lon2 + offset
                    if max(shifted_x1, shifted_x2) < -180.0 or min(shifted_x1, shifted_x2) > 180.0:
                        continue
                    segments.append((name, shifted_x1, lat1, shifted_x2, lat2))
                    add_cells(len(segments) - 1, shifted_x1, lat1, shifted_x2, lat2)

    return StateBoundaryIndex(
        segments=segments,
        grid=dict(grid),
        edges_by_state=dict(edges_by_state),
        bboxes=bboxes,
    )


def _unwrap_near(longitude: float, reference: float) -> float:
    return reference + (longitude - reference + 180.0) % 360.0 - 180.0


def _point_in_state(lon: float, lat: float, edges: list[tuple[float, float, float, float]]) -> bool:
    inside = False
    for lon1, lat1, lon2, lat2 in edges:
        x1 = _unwrap_near(lon1, lon)
        x2 = x1 + (lon2 - lon1)
        if (lat1 > lat) != (lat2 > lat):
            crossing_lon = x1 + (x2 - x1) * (lat - lat1) / (lat2 - lat1)
            if lon < crossing_lon:
                inside = not inside
    return inside


def _initial_membership(lon: float, lat: float, index: StateBoundaryIndex) -> set[str]:
    members = set()
    for state, bbox in index.bboxes.items():
        if not (
            bbox[0] - INTERSECTION_EPSILON <= lon <= bbox[2] + INTERSECTION_EPSILON
            and bbox[1] - INTERSECTION_EPSILON <= lat <= bbox[3] + INTERSECTION_EPSILON
        ):
            continue
        if _point_in_state(lon, lat, index.edges_by_state[state]):
            members.add(state)
    return members


def _candidate_segment_ids(
    lon1: float, lat1: float, lon2: float, lat2: float, index: StateBoundaryIndex
) -> set[int]:
    x_min, x_max = sorted((lon1, lon2))
    y_min, y_max = sorted((lat1, lat2))
    candidates: set[int] = set()
    for cell_x in range(math.floor(x_min / GRID_CELL_DEG), math.floor(x_max / GRID_CELL_DEG) + 1):
        for cell_y in range(
            math.floor(y_min / GRID_CELL_DEG), math.floor(y_max / GRID_CELL_DEG) + 1
        ):
            candidates.update(index.grid.get((cell_x, cell_y), ()))
    return candidates


def _cross(first: tuple[float, float], second: tuple[float, float]) -> float:
    return first[0] * second[1] - first[1] * second[0]


def _intersection_parameter(
    route_start: tuple[float, float],
    route_end: tuple[float, float],
    edge_start: tuple[float, float],
    edge_end: tuple[float, float],
) -> float | None:
    route_delta = (route_end[0] - route_start[0], route_end[1] - route_start[1])
    edge_delta = (edge_end[0] - edge_start[0], edge_end[1] - edge_start[1])
    denominator = _cross(route_delta, edge_delta)
    if abs(denominator) <= PARALLEL_EPSILON:
        return None
    offset = (edge_start[0] - route_start[0], edge_start[1] - route_start[1])
    route_t = _cross(offset, edge_delta) / denominator
    edge_t = _cross(offset, route_delta) / denominator
    if (
        -INTERSECTION_EPSILON <= route_t <= 1.0 + INTERSECTION_EPSILON
        and -INTERSECTION_EPSILON <= edge_t <= 1.0 + INTERSECTION_EPSILON
    ):
        return max(0.0, min(1.0, route_t))
    return None


def _boundary_events(
    geometry: list[list[float]], index: StateBoundaryIndex
) -> list[dict[str, Any]]:
    cumulative_mi = [0.0]
    segment_lengths_mi = []
    for first, second in zip(geometry, geometry[1:], strict=False):
        length_mi = (
            scs._haversine_m(float(first[1]), float(first[0]), float(second[1]), float(second[0]))
            / 1609.344
        )
        segment_lengths_mi.append(length_mi)
        cumulative_mi.append(cumulative_mi[-1] + length_mi)

    hits: list[tuple[float, str]] = []
    for route_index, (first, second) in enumerate(zip(geometry, geometry[1:], strict=False)):
        lon1, lat1 = float(first[0]), float(first[1])
        lon2, lat2 = float(second[0]), float(second[1])
        unwrapped_lon2 = _unwrap_near(lon2, lon1)
        route_start = (lon1, lat1)
        route_end = (unwrapped_lon2, lat2)
        candidate_ids = _candidate_segment_ids(lon1, lat1, unwrapped_lon2, lat2, index)
        for segment_id in candidate_ids:
            state, edge_lon1, edge_lat1, edge_lon2, edge_lat2 = index.segments[segment_id]
            route_t = _intersection_parameter(
                route_start,
                route_end,
                (edge_lon1, edge_lat1),
                (edge_lon2, edge_lat2),
            )
            if route_t is not None:
                hits.append(
                    (
                        cumulative_mi[route_index] + route_t * segment_lengths_mi[route_index],
                        state,
                    )
                )

    hits.sort()
    events: list[dict[str, Any]] = []
    for at_mi, state in hits:
        if events and at_mi - events[-1]["start_mi"] <= EVENT_MERGE_MI:
            events[-1]["states"].add(state)
        else:
            events.append({"at_mi": at_mi, "start_mi": at_mi, "states": {state}})
    return events


def derive_state_context(
    data: dict[str, Any],
    leg: dict[str, Any],
    geometry: list[list[float]],
    boundaries: StateBoundaryIndex,
) -> dict[str, Any]:
    leg_miles = float(leg["miles"])
    endpoint_states = (
        ers.spoken_state(data, data["cities"][leg["from"]]["state"]),
        ers.spoken_state(data, data["cities"][leg["to"]]["state"]),
    )
    if len(geometry) < 2:
        return {"state_crossings": [], "state_miles": [], "warnings": []}

    membership = _initial_membership(float(geometry[0][0]), float(geometry[0][1]), boundaries)
    warnings = []
    if len(membership) > 1:
        warnings.append(
            f"{_leg_id(leg)}: start point belongs to multiple OSM states {sorted(membership)}"
        )
    if len(membership) == 1:
        current_state = next(iter(membership))
    elif membership and endpoint_states[0] not in membership:
        current_state = sorted(membership)[0]
    else:
        current_state = endpoint_states[0]
    sequence = [{"state": current_state, "at_mi": 0.0}]
    last_state = current_state

    geometry_mi = sum(
        scs._haversine_m(float(first[1]), float(first[0]), float(second[1]), float(second[0]))
        / 1609.344
        for first, second in zip(geometry, geometry[1:], strict=False)
    )
    scale = leg_miles / geometry_mi if geometry_mi else 1.0
    empty_start_mi = 0.0 if not membership else None
    for event in _boundary_events(geometry, boundaries):
        event_mi = event["at_mi"] * scale
        if not membership and empty_start_mi is not None:
            empty_miles = event_mi - empty_start_mi
            if empty_miles > 1.0:
                warnings.append(
                    f"{_leg_id(leg)}: no OSM state membership from "
                    f"{empty_start_mi:.1f} to {event_mi:.1f} mi "
                    f"({empty_miles:.1f} mi); retained {last_state}"
                )

        for state in event["states"]:
            if state in membership:
                membership.remove(state)
            else:
                membership.add(state)

        if len(membership) == 1:
            next_state = next(iter(membership))
            if next_state != last_state:
                sequence.append({"state": next_state, "at_mi": event_mi})
            last_state = next_state
        elif not membership:
            if empty_start_mi is None:
                empty_start_mi = event_mi
        else:
            warnings.append(
                f"{_leg_id(leg)}: multiple OSM states {sorted(membership)} "
                f"at {event_mi:.1f} mi; retained {last_state}"
            )
        if membership:
            empty_start_mi = None

    if not membership and empty_start_mi is not None:
        empty_miles = leg_miles - empty_start_mi
        if empty_miles > 1.0:
            warnings.append(
                f"{_leg_id(leg)}: no OSM state membership from "
                f"{empty_start_mi:.1f} to {leg_miles:.1f} mi "
                f"({empty_miles:.1f} mi); retained {last_state}"
            )

    if sequence[-1]["state"] != endpoint_states[1]:
        sequence.append({"state": endpoint_states[1], "at_mi": leg_miles})
    sequence = ers.coalesce_short_states(sequence, leg_miles)
    return {
        "state_crossings": ers.crossings_from_sequence(sequence, leg_miles, leg["highway"]),
        "state_miles": ers.state_miles_from_sequence(sequence, leg_miles, endpoint_states),
        "warnings": warnings,
    }


def process_world(
    data: dict[str, Any],
    state_boundaries: list[dict[str, Any]] | StateBoundaryIndex,
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
        "warnings": [],
    }
    boundary_index = (
        state_boundaries
        if isinstance(state_boundaries, StateBoundaryIndex)
        else build_boundary_index(state_boundaries)
    )
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
        derived = derive_state_context(data, leg, coords, boundary_index)
        report["warnings"].extend(derived.get("warnings", []))
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
        new_start_state = new_state_miles[0]["state"] if new_state_miles else start_state
        new_sequence = _state_sequence(new_crossings, new_start_state)
        sequence_matches = old_sequence == new_sequence
        selected = only is not None and leg_id in only
        stale_source = any(
            item.get("source") == STALE_PUBLICAMUNDI_SOURCE
            for item in old_crossings + old_state_miles
        )
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
        should_update = selected or (sequence_matches and (shift >= min_shift or stale_source))
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
    if report["warnings"]:
        lines.extend(["Boundary warnings:", *(f"  {item}" for item in report["warnings"])])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help='semicolon-separated "from:to" leg ids')
    parser.add_argument("--min-shift", type=float, default=1.0)
    parser.add_argument("--cache", type=Path, default=BOUNDARIES_CACHE)
    parser.add_argument("--write", action="store_true", help="save changed world source")
    args = parser.parse_args(argv)

    try:
        state_boundaries = load_state_boundaries(args.cache)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    data = load_world()
    report = process_world(
        data,
        state_boundaries,
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
