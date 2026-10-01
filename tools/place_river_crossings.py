"""Re-place existing river landmarks against dense archived geometry.

The tool reads matching waterway=river ways from a Geofabrik PBF and moves
only existing ``category == "river"`` landmarks. It is dry-run by default.

    python tools/place_river_crossings.py --pbf ~/osm/us-latest.osm.pbf
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import leg_geometry as lg  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

ROUTE_POINT_AGREEMENT_MI = 5.0
OSM_CACHE_DIR = Path.home() / "osm"
DEFAULT_PBF = OSM_CACHE_DIR / "us-latest.osm.pbf"
SHIFT_BUCKETS = ("0-1", "1-3", "3-5", "5-10", "10+")
SEGMENT_GRID_DEG = 0.25
MAX_SEGMENT_GRID_CELLS = 4096


def parse_only(value: str | None) -> set[str] | None:
    if value is None:
        return None
    return {item.strip() for item in value.split(";") if item.strip()}


def _leg_id(leg: dict[str, Any]) -> str:
    return f"{leg['from']}:{leg['to']}"


def _river_names(data: dict[str, Any]) -> set[str]:
    return {
        str(landmark["name"]).casefold()
        for leg in data.get("legs", ())
        for landmark in (leg.get("corridor") or {}).get("landmarks", ())
        if landmark.get("category") == "river" and landmark.get("name")
    }


def _cache_path(pbf_path: Path, names: set[str], cache_dir: Path) -> Path:
    stat = pbf_path.stat()
    name_hash = hashlib.sha256("\0".join(sorted(names)).encode("utf-8")).hexdigest()[:12]
    return cache_dir / (f"river-lines-{stat.st_size}-{stat.st_mtime_ns}-{name_hash}.json.gz")


def _relation_names_by_way(pbf_path: Path, names: set[str]) -> dict[int, set[str]]:
    import osmium

    relation_names: dict[int, set[str]] = {}
    relations = osmium.FileProcessor(
        str(pbf_path), entities=osmium.osm.osm_entity_bits.RELATION
    ).with_filter(osmium.filter.TagFilter(("type", "waterway")))
    for relation in relations:
        name = relation.tags.get("name")
        if not name or str(name).casefold() not in names:
            continue
        for member in relation.members:
            if member.type == "w":
                relation_names.setdefault(int(member.ref), set()).add(str(name))
    return relation_names


def extract_river_lines(
    pbf_path: Path, names: set[str], cache_dir: Path = OSM_CACHE_DIR
) -> list[dict[str, Any]]:
    """Extract named matching river ways using a disk-backed location index."""
    import osmium

    cache_dir.mkdir(parents=True, exist_ok=True)
    wanted = {name.casefold() for name in names}
    if not wanted:
        return []

    started = time.monotonic()
    print("    reading waterway relations for unnamed river ways", flush=True)
    relation_names = _relation_names_by_way(pbf_path, wanted)
    print(f"    {len(relation_names):,} river-way memberships found", flush=True)

    previous_tmpdir = os.environ.get("TMPDIR")
    os.environ["TMPDIR"] = str(cache_dir)
    lines: list[dict[str, Any]] = []
    seen = 0
    try:
        ways = (
            osmium.FileProcessor(
                str(pbf_path),
                entities=osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY,
            )
            .with_locations("sparse_file_array")
            .with_filter(osmium.filter.KeyFilter("waterway"))
        )
        for way in ways:
            seen += 1
            tags = way.tags
            if tags.get("waterway") != "river":
                continue
            name = tags.get("name")
            if name:
                matching_names = [str(name)] if str(name).casefold() in wanted else []
            else:
                matching_names = sorted(relation_names.get(int(way.id), ()), key=str.casefold)
            if not matching_names:
                continue

            coords = []
            for node in way.nodes:
                location = node.location
                if not location.valid():
                    coords = []
                    break
                coords.append([float(location.lon), float(location.lat)])
            if len(coords) < 2:
                continue
            lines.extend(
                {"way_id": int(way.id), "name": name, "coords": coords} for name in matching_names
            )
    finally:
        if previous_tmpdir is None:
            os.environ.pop("TMPDIR", None)
        else:
            os.environ["TMPDIR"] = previous_tmpdir

    print(
        f"    scanned {seen:,} waterway-tagged ways; extracted {len(lines):,} river lines "
        f"({time.monotonic() - started:.0f}s)",
        flush=True,
    )
    return lines


def load_or_extract_river_lines(
    pbf_path: Path, names: set[str], cache_dir: Path = OSM_CACHE_DIR
) -> list[dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(pbf_path, names, cache_dir)
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            lines = json.load(stream)
        print(f"    loaded {len(lines):,} cached river lines from {path}", flush=True)
        return lines

    lines = extract_river_lines(pbf_path, names, cache_dir)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(lines, stream, separators=(",", ":"))
    print(f"    cached {len(lines):,} river lines at {path}", flush=True)
    return lines


def _dense_route(
    leg: dict[str, Any],
) -> tuple[list[tuple[float, float]], list[float], str | None]:
    geometry = lg.corridor_geometry(leg)
    polyline = lg.archived_polyline(lg.leg_id_of(leg), lg.state_code_of(leg))
    if not geometry or not polyline:
        return [], [], "no dense archived geometry"

    max_off_mi = lg.route_point_max_off_mi(leg, polyline[0])
    if max_off_mi is None:
        return [], [], "route-point agreement could not be checked"
    if max_off_mi > ROUTE_POINT_AGREEMENT_MI:
        return [], [], f"route_points are {max_off_mi:.2f} mi from archive (limit 5.00)"

    route = [(float(lat), float(lon)) for lat, lon, _at_mi in geometry]
    cum = [float(at_mi) for _lat, _lon, at_mi in geometry]
    if len(route) < 2 or len(route) != len(cum):
        return [], [], "dense archived geometry has fewer than two vertices"
    return route, cum, None


def _all_crossings(
    route: list[tuple[float, float]],
    cum: list[float],
    line: list[tuple[float, float]],
    route_grid: tuple[dict[tuple[int, int], list[int]], list[int]] | None = None,
) -> list[tuple[float, float, float]]:
    """Return all (mile, lat, lon) segment intersections for one waterway."""
    route_grid = route_grid or _route_segment_grid(route)
    buckets, overflow = route_grid
    crossings = []
    for j in range(1, len(line)):
        (cy, cx), (dy, dx) = line[j - 1], line[j]
        cells = _grid_cells(cx, cy, dx, dy)
        if cells is None:
            candidate_segments = set(range(1, len(route)))
        else:
            candidate_segments = set(overflow)
            for cell in cells:
                candidate_segments.update(buckets.get(cell, ()))
        for i in candidate_segments:
            (ay, ax), (by, bx) = route[i - 1], route[i]
            if (
                max(ax, bx) < min(cx, dx)
                or max(cx, dx) < min(ax, bx)
                or max(ay, by) < min(cy, dy)
                or max(cy, dy) < min(ay, by)
            ):
                continue
            rx, ry = bx - ax, by - ay
            sx, sy = dx - cx, dy - cy
            denominator = rx * sy - ry * sx
            if abs(denominator) < 1e-12:
                continue
            qpx, qpy = cx - ax, cy - ay
            t = (qpx * sy - qpy * sx) / denominator
            u = (qpx * ry - qpy * rx) / denominator
            if 0 <= t <= 1 and 0 <= u <= 1:
                crossings.append((cum[i - 1] + t * (cum[i] - cum[i - 1]), ay + t * ry, ax + t * rx))
    return sorted(crossings)


def _grid_cells(x1: float, y1: float, x2: float, y2: float) -> tuple[tuple[int, int], ...] | None:
    min_x = int(min(x1, x2) // SEGMENT_GRID_DEG)
    max_x = int(max(x1, x2) // SEGMENT_GRID_DEG)
    min_y = int(min(y1, y2) // SEGMENT_GRID_DEG)
    max_y = int(max(y1, y2) // SEGMENT_GRID_DEG)
    if (max_x - min_x + 1) * (max_y - min_y + 1) > MAX_SEGMENT_GRID_CELLS:
        return None
    return tuple((x, y) for x in range(min_x, max_x + 1) for y in range(min_y, max_y + 1))


def _route_segment_grid(
    route: list[tuple[float, float]],
) -> tuple[dict[tuple[int, int], list[int]], list[int]]:
    buckets: dict[tuple[int, int], list[int]] = {}
    overflow = []
    for i in range(1, len(route)):
        (lat1, lon1), (lat2, lon2) = route[i - 1], route[i]
        cells = _grid_cells(lon1, lat1, lon2, lat2)
        if cells is None:
            overflow.append(i)
            continue
        for cell in cells:
            buckets.setdefault(cell, []).append(i)
    return buckets, overflow


def _crossings_for_name(
    route: list[tuple[float, float]],
    cum: list[float],
    name: str,
    lines_by_name: dict[str, list[dict[str, Any]]],
    route_grid: tuple[dict[tuple[int, int], list[int]], list[int]],
) -> list[tuple[float, float, float, int, str]]:
    crossings = []
    for line in lines_by_name.get(name.casefold(), ()):
        coords = [(float(lat), float(lon)) for lon, lat in line["coords"]]
        crossings.extend(
            (at_mi, lat, lon, int(line["way_id"]), str(line["name"]))
            for at_mi, lat, lon in _all_crossings(route, cum, coords, route_grid)
        )
    return crossings


def _shift_bucket(shift: float) -> str:
    if shift < 1.0:
        return "0-1"
    if shift < 3.0:
        return "1-3"
    if shift < 5.0:
        return "3-5"
    if shift < 10.0:
        return "5-10"
    return "10+"


def _river_source(way_id: int, name: str, pbf_date: str) -> str:
    return (
        f"derived 2026-10-01: crossing of OSM waterway way {way_id} ({name}) with the "
        "leg's archived dense route geometry; at_mi = cum[i-1] + t*(cum[i]-cum[i-1]) "
        "rescaled to leg miles, taking the crossing nearest the previous at_mi when "
        "the river crosses more than once. OpenStreetMap, Geofabrik us-latest extract "
        f"{pbf_date}: https://www.openstreetmap.org/."
    )


def process_world(
    data: dict[str, Any],
    lines: list[dict[str, Any]],
    *,
    pbf_date: str,
    only: set[str] | None = None,
) -> dict[str, Any]:
    lines_by_name: dict[str, list[dict[str, Any]]] = {}
    for line in lines:
        lines_by_name.setdefault(str(line["name"]).casefold(), []).append(line)

    report: dict[str, Any] = {
        "legs_total": len(data.get("legs", ())),
        "legs_scanned": 0,
        "guard_skipped": [],
        "geometry_skipped": [],
        "legs_without_rivers": 0,
        "rivers_moved": 0,
        "changed_legs": 0,
        "histogram": {bucket: 0 for bucket in SHIFT_BUCKETS},
        "unmatched": [],
        "only_changes": [],
    }
    for leg in data.get("legs", ()):
        leg_id = _leg_id(leg)
        if only is not None and leg_id not in only:
            continue
        corridor = leg.get("corridor") or {}
        landmarks = corridor.get("landmarks") or []
        rivers = [item for item in landmarks if item.get("category") == "river"]
        if not rivers:
            report["legs_without_rivers"] += 1
            continue

        route, cum, skip_reason = _dense_route(leg)
        if skip_reason:
            entry = f"{leg_id}: {skip_reason}"
            if "route_points are" in skip_reason:
                report["guard_skipped"].append(entry)
            else:
                report["geometry_skipped"].append(entry)
            continue
        report["legs_scanned"] += 1
        route_grid = _route_segment_grid(route)
        leg_changed = False
        for landmark in rivers:
            name = str(landmark.get("name") or "")
            old_at_mi = float(landmark["at_mi"])
            candidates = _crossings_for_name(route, cum, name, lines_by_name, route_grid)
            if not candidates:
                entry = {"leg": leg_id, "name": name, "at_mi": old_at_mi}
                report["unmatched"].append(entry)
                if only is not None:
                    report["only_changes"].append(
                        f"{leg_id} {name}: {old_at_mi:.1f} -> no crossing (unmatched)"
                    )
                continue

            at_mi, lat, lon, way_id, osm_name = min(
                candidates, key=lambda item: (abs(item[0] - old_at_mi), item[0], item[3])
            )
            new_at_mi = round(at_mi, 1)
            updates = {
                "at_mi": new_at_mi,
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "source": _river_source(way_id, osm_name, pbf_date),
            }
            if any(landmark.get(key) != value for key, value in updates.items()):
                landmark.update(updates)
                leg_changed = True

            shift = abs(old_at_mi - new_at_mi)
            report["histogram"][_shift_bucket(shift)] += 1
            report["rivers_moved"] += 1
            if only is not None:
                report["only_changes"].append(
                    f"{leg_id} {name}: {old_at_mi:.1f} -> {new_at_mi:.1f}"
                )

        if leg_changed:
            landmarks.sort(key=lambda item: item["at_mi"])
            report["changed_legs"] += 1

    return report


def _format_report(report: dict[str, Any]) -> str:
    lines = [
        f"Legs: {report['legs_total']} total; {report['legs_scanned']} scanned; "
        f"{len(report['guard_skipped'])} skipped by agreement guard; "
        f"{len(report['geometry_skipped'])} skipped for missing/unusable geometry; "
        f"{report['legs_without_rivers']} had no river landmarks.",
        f"Rivers moved: {report['rivers_moved']} across {report['changed_legs']} changed legs.",
        "Shift histogram: "
        + ", ".join(f"{bucket} mi: {report['histogram'][bucket]}" for bucket in SHIFT_BUCKETS),
        "Skipped by agreement guard:",
        *(f"  {item}" for item in report["guard_skipped"]),
        "Skipped for geometry:",
        *(f"  {item}" for item in report["geometry_skipped"]),
        "Unmatched rivers:",
        *(
            f"  {item['leg']} {item['name']} at {item['at_mi']:.1f} mi"
            for item in report["unmatched"]
        ),
    ]
    if report["only_changes"]:
        lines.extend(["--only river positions:", *(f"  {item}" for item in report["only_changes"])])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbf", type=Path, default=DEFAULT_PBF)
    parser.add_argument("--only", help='semicolon-separated "from:to" leg ids')
    parser.add_argument("--write", action="store_true", help="save changed world source")
    args = parser.parse_args(argv)

    data = load_world()
    names = _river_names(data)
    lines = load_or_extract_river_lines(args.pbf, names)
    pbf_date = datetime.fromtimestamp(args.pbf.stat().st_mtime, timezone.utc).date().isoformat()
    report = process_world(data, lines, pbf_date=pbf_date, only=parse_only(args.only))
    print(_format_report(report))
    if args.write:
        print(f"Saved {save_world(data)} world-source files.")
    else:
        print("Dry run only; world source was not written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
