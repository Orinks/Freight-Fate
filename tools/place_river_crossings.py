"""Place and remove river landmarks against dense archived geometry.

The tool reads matching OSM waterways and river polygons from a Geofabrik PBF,
placing existing ``category == "river"`` landmarks at real crossings and
removing named waters the archived route never crosses. It is dry-run by default.

    python tools/place_river_crossings.py --pbf ~/osm/us-latest.osm.pbf
"""

from __future__ import annotations

import argparse
import bisect
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import leg_geometry as lg  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

WATERWAY_TYPES = {"river", "stream", "canal", "drain"}
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
    return cache_dir / (f"river-features-v4-{stat.st_size}-{stat.st_mtime_ns}-{name_hash}.json.gz")


WATER_FEATURE_FILTERS = (
    "w/waterway=river,stream,canal,drain",
    "r/type=waterway",
    "w/water=river",
    "r/water=river",
)


def _water_feature_pbf(pbf_path: Path, cache_dir: Path) -> Path:
    stat = pbf_path.stat()
    cache_dir.mkdir(parents=True, exist_ok=True)
    filtered_path = cache_dir / f"river-source-v1-{stat.st_size}-{stat.st_mtime_ns}.osm.pbf"
    if filtered_path.exists():
        return filtered_path

    osmium = shutil.which("osmium")
    if osmium is None:
        raise RuntimeError("the osmium command is required to filter river features from the PBF")
    temporary_path = cache_dir / f".{filtered_path.name}.tmp"
    subprocess.run(
        [
            osmium,
            "tags-filter",
            "--no-progress",
            "--output",
            str(temporary_path),
            "--overwrite",
            "--output-format",
            "pbf",
            str(pbf_path),
            *WATER_FEATURE_FILTERS,
        ],
        check=True,
    )
    os.replace(temporary_path, filtered_path)
    return filtered_path


def _relation_features(
    pbf_path: Path, names: set[str]
) -> tuple[dict[int, set[str]], list[dict[str, Any]]]:
    import osmium

    relation_names: dict[int, set[str]] = {}
    polygons: list[dict[str, Any]] = []
    relations = osmium.FileProcessor(str(pbf_path), entities=osmium.osm.osm_entity_bits.RELATION)
    for relation in relations:
        name = relation.tags.get("name")
        if not name or str(name).casefold() not in names:
            continue
        name = str(name)
        if relation.tags.get("type") == "waterway":
            for member in relation.members:
                if member.type == "w":
                    relation_names.setdefault(int(member.ref), set()).add(name)
        if relation.tags.get("natural") == "water" and relation.tags.get("water") == "river":
            members = [
                {"way_id": int(member.ref), "role": str(member.role)}
                for member in relation.members
                if member.type == "w" and member.role in ("", "outer", "inner")
            ]
            if members:
                polygons.append({"relation_id": int(relation.id), "name": name, "members": members})
    return relation_names, polygons


def _way_coordinates(way: Any) -> list[list[float]]:
    coordinates = []
    for node in way.nodes:
        location = node.location
        if not location.valid():
            return []
        coordinates.append([float(location.lon), float(location.lat)])
    return coordinates if len(coordinates) >= 2 else []


def _waterway_names_for_way(
    way_id: int,
    name: str,
    waterway_type: str | None,
    relation_names: dict[int, set[str]],
    wanted: set[str],
) -> list[str]:
    matched_names = set(relation_names.get(way_id, ()))
    if waterway_type in WATERWAY_TYPES and name and name.casefold() in wanted:
        matched_names.add(name)
    if waterway_type not in WATERWAY_TYPES and not matched_names:
        return []
    return sorted(matched_names, key=str.casefold)


def _stitch_rings(
    members: list[dict[str, Any]], ways_by_id: dict[int, list[list[float]]]
) -> tuple[list[list[list[float]]], list[list[list[float]]]]:
    rings: dict[str, list[list[list[float]]]] = {"outer": [], "inner": []}
    for role in ("outer", "inner"):
        remaining = [
            list(ways_by_id[member["way_id"]])
            for member in members
            if (member["role"] == role or (role == "outer" and not member["role"]))
            and member["way_id"] in ways_by_id
        ]
        while remaining:
            ring = remaining.pop()
            while ring[0] != ring[-1]:
                end = ring[-1]
                match_index = next(
                    (
                        index
                        for index, segment in enumerate(remaining)
                        if segment[0] == end or segment[-1] == end
                    ),
                    None,
                )
                if match_index is None:
                    ring = []
                    break
                segment = remaining.pop(match_index)
                if segment[-1] == end:
                    segment.reverse()
                ring.extend(segment[1:])
            if len(ring) >= 4 and ring[0] == ring[-1]:
                rings[role].append(ring)
    return rings["outer"], rings["inner"]


def extract_river_lines(
    pbf_path: Path, names: set[str], cache_dir: Path = OSM_CACHE_DIR
) -> list[dict[str, Any]]:
    """Extract named waterways and river polygons from a filtered PBF."""
    import osmium

    cache_dir.mkdir(parents=True, exist_ok=True)
    wanted = {name.casefold() for name in names}
    if not wanted:
        return []

    started = time.monotonic()
    feature_pbf = _water_feature_pbf(pbf_path, cache_dir)
    print("    reading named waterway relations and river polygons", flush=True)
    relation_names, polygon_relations = _relation_features(feature_pbf, wanted)
    member_ids = {
        member["way_id"] for relation in polygon_relations for member in relation["members"]
    }
    print(
        f"    {len(relation_names):,} waterway memberships and "
        f"{len(polygon_relations):,} river polygons found",
        flush=True,
    )

    previous_tmpdir = os.environ.get("TMPDIR")
    os.environ["TMPDIR"] = str(cache_dir)
    features: list[dict[str, Any]] = []
    polygon_member_ways: dict[int, list[list[float]]] = {}
    scanned_way_ids: set[int] = set()
    seen = 0
    try:
        ways = (
            osmium.FileProcessor(
                str(feature_pbf),
                entities=osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY,
            )
            .with_locations("flex_mem")
            .with_filter(osmium.filter.KeyFilter("waterway", "natural"))
        )
        for way in ways:
            if not hasattr(way, "nodes"):
                continue
            seen += 1
            tags = way.tags
            way_id = int(way.id)
            scanned_way_ids.add(way_id)
            name = str(tags.get("name") or "")
            coords = _way_coordinates(way)
            if not coords:
                continue
            if way_id in member_ids:
                polygon_member_ways[way_id] = coords

            for matched_name in _waterway_names_for_way(
                way_id, name, str(tags.get("waterway") or "") or None, relation_names, wanted
            ):
                features.append(
                    {
                        "geometry": "line",
                        "feature_type": "waterway way",
                        "feature_id": way_id,
                        "name": matched_name,
                        "coords": coords,
                    }
                )
            if (
                tags.get("natural") == "water"
                and tags.get("water") == "river"
                and name.casefold() in wanted
                and len(coords) >= 4
                and coords[0] == coords[-1]
            ):
                features.append(
                    {
                        "geometry": "polygon",
                        "feature_type": "river polygon way",
                        "feature_id": way_id,
                        "name": name,
                        "outer": [coords],
                        "inner": [],
                    }
                )

        missing_member_ids = (member_ids | relation_names.keys()) - scanned_way_ids
        if missing_member_ids:
            member_ways = (
                osmium.FileProcessor(
                    str(feature_pbf),
                    entities=osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY,
                )
                .with_locations("flex_mem")
                .with_filter(osmium.filter.IdFilter(missing_member_ids))
            )
            for way in member_ways:
                way_id = int(way.id)
                if not hasattr(way, "nodes") or way_id not in missing_member_ids:
                    continue
                coords = _way_coordinates(way)
                if not coords:
                    continue
                if way_id in member_ids:
                    polygon_member_ways[way_id] = coords
                for matched_name in sorted(relation_names.get(way_id, ()), key=str.casefold):
                    features.append(
                        {
                            "geometry": "line",
                            "feature_type": "waterway way",
                            "feature_id": way_id,
                            "name": matched_name,
                            "coords": coords,
                        }
                    )
    finally:
        if previous_tmpdir is None:
            os.environ.pop("TMPDIR", None)
        else:
            os.environ["TMPDIR"] = previous_tmpdir

    for relation in polygon_relations:
        outer, inner = _stitch_rings(relation["members"], polygon_member_ways)
        if outer:
            features.append(
                {
                    "geometry": "polygon",
                    "feature_type": "river polygon relation",
                    "feature_id": relation["relation_id"],
                    "name": relation["name"],
                    "outer": outer,
                    "inner": inner,
                }
            )
    features.sort(
        key=lambda feature: (
            str(feature["name"]).casefold(),
            str(feature["feature_type"]),
            int(feature["feature_id"]),
        )
    )
    print(
        f"    scanned {seen:,} tagged ways; extracted {len(features):,} water features "
        f"({time.monotonic() - started:.0f}s)",
        flush=True,
    )
    return features


def load_or_extract_river_features(
    pbf_path: Path, names: set[str], cache_dir: Path = OSM_CACHE_DIR
) -> list[dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(pbf_path, names, cache_dir)
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            features = json.load(stream)
        print(f"    loaded {len(features):,} cached water features from {path}", flush=True)
        return features

    features = extract_river_lines(pbf_path, names, cache_dir)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(features, stream, separators=(",", ":"))
    print(f"    cached {len(features):,} water features at {path}", flush=True)
    return features


def _dense_route(
    leg: dict[str, Any],
) -> tuple[list[tuple[float, float]], list[float], str | None]:
    geometry = lg.corridor_geometry(leg)
    if not geometry:
        return [], [], "no dense archived geometry"

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


def _route_point_at(
    route: list[tuple[float, float]], cum: list[float], at_mi: float
) -> tuple[float, float]:
    index = max(0, min(len(route) - 2, bisect.bisect_right(cum, at_mi) - 1))
    span = cum[index + 1] - cum[index]
    ratio = 0.0 if span <= 0 else (at_mi - cum[index]) / span
    lat1, lon1 = route[index]
    lat2, lon2 = route[index + 1]
    return lat1 + ratio * (lat2 - lat1), lon1 + ratio * (lon2 - lon1)


def _point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    previous_lon, previous_lat = ring[-1]
    for current_lon, current_lat in ring:
        if (current_lat > lat) != (previous_lat > lat):
            crossing_lon = (previous_lon - current_lon) * (lat - current_lat) / (
                previous_lat - current_lat
            ) + current_lon
            if lon < crossing_lon:
                inside = not inside
        previous_lon, previous_lat = current_lon, current_lat
    return inside


def _inside_polygon(
    lon: float, lat: float, outer: list[list[list[float]]], inner: list[list[list[float]]]
) -> bool:
    return any(_point_in_ring(lon, lat, ring) for ring in outer) and not any(
        _point_in_ring(lon, lat, ring) for ring in inner
    )


def _polygon_midpoints(
    route: list[tuple[float, float]],
    cum: list[float],
    feature: dict[str, Any],
    route_grid: tuple[dict[tuple[int, int], list[int]], list[int]],
) -> list[tuple[float, float, float]]:
    outer = feature["outer"]
    inner = feature.get("inner", [])
    boundaries = [cum[0], cum[-1]]
    for ring in [*outer, *inner]:
        line = [(float(lat), float(lon)) for lon, lat in ring]
        boundaries.extend(
            at_mi for at_mi, _lat, _lon in _all_crossings(route, cum, line, route_grid)
        )
    boundaries.sort()
    unique_boundaries = []
    for at_mi in boundaries:
        if not unique_boundaries or at_mi - unique_boundaries[-1] > 1e-7:
            unique_boundaries.append(at_mi)

    spans: list[list[float]] = []
    for start, end in zip(unique_boundaries, unique_boundaries[1:], strict=False):
        if end - start <= 1e-8:
            continue
        lat, lon = _route_point_at(route, cum, (start + end) / 2.0)
        if _inside_polygon(lon, lat, outer, inner):
            if spans and abs(spans[-1][1] - start) <= 1e-7:
                spans[-1][1] = end
            else:
                spans.append([start, end])
    return [
        ((start + end) / 2.0, *_route_point_at(route, cum, (start + end) / 2.0))
        for start, end in spans
    ]


def _crossings_for_name(
    route: list[tuple[float, float]],
    cum: list[float],
    name: str,
    features_by_name: dict[str, list[dict[str, Any]]],
    route_grid: tuple[dict[tuple[int, int], list[int]], list[int]],
) -> list[tuple[float, float, float, int, str, str]]:
    crossings = []
    for feature in features_by_name.get(name.casefold(), ()):
        if feature.get("geometry") == "polygon":
            candidates = _polygon_midpoints(route, cum, feature, route_grid)
        else:
            coords = [(float(lat), float(lon)) for lon, lat in feature["coords"]]
            candidates = _all_crossings(route, cum, coords, route_grid)
        crossings.extend(
            (
                at_mi,
                lat,
                lon,
                int(feature["feature_id"]),
                str(feature["name"]),
                str(feature["feature_type"]),
            )
            for at_mi, lat, lon in candidates
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


def _river_source(feature_type: str, feature_id: int, name: str, pbf_date: str) -> str:
    return (
        f"derived 2026-10-01: placed by tools/place_river_crossings.py at the crossing of "
        f"OSM {feature_type} {feature_id} ({name}) with the "
        "leg's archived dense route geometry; at_mi = cum[i-1] + t*(cum[i]-cum[i-1]) "
        "rescaled to leg miles, taking the crossing nearest the previous at_mi when "
        "the river crosses more than once. OpenStreetMap, Geofabrik us-latest extract "
        f"{pbf_date}: https://www.openstreetmap.org/."
    )


def process_world(
    data: dict[str, Any],
    features: list[dict[str, Any]],
    *,
    pbf_date: str,
    only: set[str] | None = None,
) -> dict[str, Any]:
    features_by_name: dict[str, list[dict[str, Any]]] = {}
    for feature in features:
        features_by_name.setdefault(str(feature["name"]).casefold(), []).append(feature)

    report: dict[str, Any] = {
        "legs_total": len(data.get("legs", ())),
        "legs_scanned": 0,
        "geometry_skipped": [],
        "legs_without_rivers": 0,
        "rivers_placed": 0,
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
            report["geometry_skipped"].append(entry)
            continue
        report["legs_scanned"] += 1
        route_grid = _route_segment_grid(route)
        leg_changed = False
        removed_ids: set[int] = set()
        for landmark in rivers:
            name = str(landmark.get("name") or "")
            old_at_mi = float(landmark["at_mi"])
            candidates = _crossings_for_name(route, cum, name, features_by_name, route_grid)
            if not candidates:
                entry = {"leg": leg_id, "name": name, "at_mi": old_at_mi}
                report["unmatched"].append(entry)
                removed_ids.add(id(landmark))
                leg_changed = True
                if only is not None:
                    report["only_changes"].append(
                        f"{leg_id} {name}: {old_at_mi:.1f} -> removed (no crossing)"
                    )
                continue

            at_mi, lat, lon, feature_id, osm_name, feature_type = min(
                candidates, key=lambda item: (abs(item[0] - old_at_mi), item[0], item[3])
            )
            new_at_mi = round(at_mi, 1)
            updates = {
                "at_mi": new_at_mi,
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "source": _river_source(feature_type, feature_id, osm_name, pbf_date),
            }
            if any(landmark.get(key) != value for key, value in updates.items()):
                landmark.update(updates)
                leg_changed = True

            shift = abs(old_at_mi - new_at_mi)
            report["histogram"][_shift_bucket(shift)] += 1
            report["rivers_placed"] += 1
            if only is not None:
                report["only_changes"].append(
                    f"{leg_id} {name}: {old_at_mi:.1f} -> {new_at_mi:.1f}"
                )

        if leg_changed:
            corridor["landmarks"] = [
                landmark for landmark in landmarks if id(landmark) not in removed_ids
            ]
            landmarks = corridor["landmarks"]
            landmarks.sort(key=lambda item: item["at_mi"])
            report["changed_legs"] += 1

    return report


def _format_report(report: dict[str, Any]) -> str:
    lines = [
        f"Legs: {report['legs_total']} total; {report['legs_scanned']} scanned; "
        f"{len(report['geometry_skipped'])} skipped for missing/unusable geometry; "
        f"{report['legs_without_rivers']} had no river landmarks.",
        f"Rivers placed: {report['rivers_placed']}; "
        f"removed: {len(report['unmatched'])} across {report['changed_legs']} changed legs.",
        "Shift histogram: "
        + ", ".join(f"{bucket} mi: {report['histogram'][bucket]}" for bucket in SHIFT_BUCKETS),
        "Skipped for geometry:",
        *(f"  {item}" for item in report["geometry_skipped"]),
        "Removed unmatched rivers:",
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
    parser.add_argument(
        "--removed-out",
        type=Path,
        help="write the list of removed false river callouts as JSON",
    )
    args = parser.parse_args(argv)

    data = load_world()
    names = _river_names(data)
    features = load_or_extract_river_features(args.pbf, names)
    pbf_date = datetime.fromtimestamp(args.pbf.stat().st_mtime, timezone.utc).date().isoformat()
    report = process_world(data, features, pbf_date=pbf_date, only=parse_only(args.only))
    print(_format_report(report))
    if args.removed_out:
        args.removed_out.parent.mkdir(parents=True, exist_ok=True)
        args.removed_out.write_text(
            json.dumps(report["unmatched"], indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {len(report['unmatched'])} removed river callouts to {args.removed_out}")
    if args.write:
        print(f"Saved {save_world(data)} world-source files.")
    else:
        print("Dry run only; world source was not written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
