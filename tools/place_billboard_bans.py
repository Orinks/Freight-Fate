"""Derive leg-local scenic-highway billboard bans from archived route geometry."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import leg_geometry as lg  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

CDOT_DATASET_ID = "6aqe-63uq"
CDOT_URL = (
    f"https://data.colorado.gov/api/geospatial/{CDOT_DATASET_ID}?method=export&format=GeoJSON"
)
CDOT_CACHE_NAME = "cdot-scenic-byways-all.geojson"
DEFAULT_PBF = Path.home() / "osm" / "us-latest.osm.pbf"
DEFAULT_CACHE = Path.home() / ".cache" / "freight-fate-billboard-bans"
PBF_DATE = "2026-09-29"
SAMPLE_MI = 0.05
MAX_NEARBY_M = 150.0
MERGE_GAP_MI = 1.0
MIN_SPAN_MI = 1.0
ROAD_GRID_DEG = 0.02
STATE_EXTRACTION_BBOXES = (
    {"left": -109.2, "bottom": 36.8, "right": -101.9, "top": 41.1},
    {"left": -124.9, "bottom": 45.4, "right": -116.8, "top": 49.1},
)
COORDS = {
    "thorp_road": (47.0576218838765, -120.67680098114678),
    "east_sunset_way": (47.53206566301691, -122.02177168491544),
    "queets": (47.534, -124.343),
    "olympia": (47.03789939559459, -122.90078999130353),
}
WASHINGTON_SEGMENTS = (
    {
        "name": "Washington I-90 Scenic System: East Sunset Way to Thorp Road",
        "ref": "I 90",
        "source": "RCW 47.39.020; off-premise sign restriction: RCW 47.42.040",
        "bbox": (
            min(COORDS["thorp_road"][1], COORDS["east_sunset_way"][1]) - 0.03,
            min(COORDS["thorp_road"][0], COORDS["east_sunset_way"][0]) - 0.03,
            max(COORDS["thorp_road"][1], COORDS["east_sunset_way"][1]) + 0.03,
            max(COORDS["thorp_road"][0], COORDS["east_sunset_way"][0]) + 0.03,
        ),
        "termini": (COORDS["thorp_road"], COORDS["east_sunset_way"]),
    },
    {
        "name": "Washington US-195 Scenic System",
        "ref": "US 195",
        "source": "RCW 47.39.020; off-premise sign restriction: RCW 47.42.040",
        "bbox": None,
        "termini": None,
    },
    {
        "name": "Washington US-101 Olympic Peninsula Scenic System",
        "ref": "US 101",
        "source": "RCW 47.39.020; off-premise sign restriction: RCW 47.42.040",
        "bbox": (-124.45, 46.95, -122.85, 48.2),
        "termini": (COORDS["queets"], COORDS["olympia"]),
    },
)


def sample_geometry(
    geometry: list[tuple[float, float, float]], spacing_mi: float
) -> list[tuple[float, float, float]]:
    if len(geometry) < 2:
        return []
    targets = np.arange(0.0, geometry[-1][2], spacing_mi)
    if not len(targets) or geometry[-1][2] - float(targets[-1]) > 1e-9:
        targets = np.append(targets, geometry[-1][2])
    out = []
    segment = 0
    for target in targets:
        while segment + 1 < len(geometry) - 1 and geometry[segment + 1][2] < target:
            segment += 1
        first, second = geometry[segment], geometry[segment + 1]
        span = second[2] - first[2]
        fraction = 0.0 if span <= 0 else min(1.0, max(0.0, (target - first[2]) / span))
        out.append(
            (
                first[0] + fraction * (second[0] - first[0]),
                first[1] + fraction * (second[1] - first[1]),
                float(target),
            )
        )
    return out


def merge_and_filter_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for span in spans:
        if float(span["to_mi"]) < float(span["from_mi"]):
            continue
        grouped[str(span["name"])].append(dict(span))

    result = []
    for _name, rows in grouped.items():
        rows.sort(key=lambda row: (float(row["from_mi"]), float(row["to_mi"])))
        merged: list[dict[str, Any]] = []
        for row in rows:
            if merged and float(row["from_mi"]) - float(merged[-1]["to_mi"]) < MERGE_GAP_MI:
                merged[-1]["to_mi"] = max(float(merged[-1]["to_mi"]), float(row["to_mi"]))
                merged[-1]["way_ids"] = sorted(
                    set(merged[-1].get("way_ids", [])) | set(row.get("way_ids", []))
                )
                if merged[-1].get("route_refs") or row.get("route_refs"):
                    merged[-1]["route_refs"] = sorted(
                        set(merged[-1].get("route_refs", [])) | set(row.get("route_refs", []))
                    )
                merged[-1]["source"] = "; ".join(
                    sorted({merged[-1].get("source", ""), row.get("source", "")} - {""})
                )
            else:
                merged.append(row)
        result.extend(
            row for row in merged if float(row["to_mi"]) - float(row["from_mi"]) >= MIN_SPAN_MI
        )
    return sorted(result, key=lambda row: (str(row["name"]), float(row["from_mi"])))


def ref_numbers(value: str) -> set[str]:
    return {str(int(number)) for number in re.findall(r"\d+", value) if int(number) > 0}


def route_ref_matches(value: str, expected: str) -> bool:
    def normalize(text: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", text.upper())

    return normalize(expected) in {normalize(part) for part in value.split(";") if normalize(part)}


def expected_route_numbers(properties: dict[str, Any]) -> set[str]:
    normalized_properties = {str(key).upper(): value for key, value in properties.items()}
    value = normalized_properties.get("LABEL")
    if value is None:
        value = normalized_properties.get("ROUTE")
    return ref_numbers(str(value or "")) - {"0"}


def expected_route_refs(properties: dict[str, Any]) -> set[str]:
    numbers = expected_route_numbers(properties)
    return {f"{prefix} {number}" for number in numbers for prefix in ("CO", "US")}


def _xy_m(lat: float, lon: float, latitude_origin: float) -> tuple[float, float]:
    return (
        lon * 111_320.0 * math.cos(math.radians(latitude_origin)),
        lat * 110_574.0,
    )


def _segment_distance_m(
    lat: float, lon: float, first: tuple[float, float], second: tuple[float, float]
) -> float:
    origin = (lat + first[0] + second[0]) / 3.0
    point = np.array(_xy_m(lat, lon, origin))
    start = np.array(_xy_m(first[0], first[1], origin))
    end = np.array(_xy_m(second[0], second[1], origin))
    delta = end - start
    length = float(np.dot(delta, delta))
    fraction = (
        0.0 if length == 0 else min(1.0, max(0.0, float(np.dot(point - start, delta) / length)))
    )
    return float(np.linalg.norm(point - (start + fraction * delta)))


def _segment_length_m(first: tuple[float, float], second: tuple[float, float]) -> float:
    origin = (first[0] + second[0]) / 2.0
    return float(np.linalg.norm(np.subtract(_xy_m(*second, origin), _xy_m(*first, origin))))


def corridor_ref_pbf(pbf: Path, cache_dir: Path) -> Path:
    osmium = shutil.which("osmium")
    if not osmium:
        raise RuntimeError("osmium is required to make a memory-safe corridor PBF")
    boxes = [dict(box) for box in STATE_EXTRACTION_BBOXES]
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "pbf": str(pbf.resolve()),
                "size": pbf.stat().st_size,
                "mtime": pbf.stat().st_mtime_ns,
                "boxes": boxes,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:16]
    build_dir = cache_dir / fingerprint
    build_dir.mkdir(parents=True, exist_ok=True)
    result = build_dir / "highway-ways.osm.pbf"
    if result.exists():
        return result

    config = {
        "directory": str(build_dir),
        "extracts": [
            {"output": f"box-{index:05d}.osm.pbf", "bbox": box} for index, box in enumerate(boxes)
        ],
    }
    config_path = build_dir / "extract-config.json"
    config_path.write_text(json.dumps(config))
    for path in build_dir.glob("box-*.osm.pbf"):
        path.unlink()
    for path in (build_dir / "all-ways.osm.pbf", result):
        path.unlink(missing_ok=True)
    subprocess.run(
        [
            osmium,
            "extract",
            "--no-progress",
            "--overwrite",
            "--strategy=simple",
            "--config",
            str(config_path),
            str(pbf),
        ],
        check=True,
    )
    parts = [
        build_dir / f"box-{index:05d}.osm.pbf"
        for index in range(len(boxes))
        if (build_dir / f"box-{index:05d}.osm.pbf").exists()
    ]
    merged = build_dir / "all-ways.osm.pbf"
    subprocess.run(
        [osmium, "merge", "--no-progress", "--output", str(merged), *map(str, parts)],
        check=True,
    )
    subprocess.run(
        [
            osmium,
            "tags-filter",
            "--no-progress",
            "--output",
            str(result),
            str(merged),
            "w/highway",
        ],
        check=True,
    )
    return result


def nearest_osm_ref_matches(
    pbf: Path, samples_by_leg: dict[str, list[tuple[float, float, float]]]
) -> dict[str, list[list[dict[str, Any]]]]:
    import osmium

    flat = [
        (leg_id, index, lat, lon, mile)
        for leg_id, samples in samples_by_leg.items()
        for index, (lat, lon, mile) in enumerate(samples)
    ]
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for point_id, (_, _, lat, lon, _) in enumerate(flat):
        grid[(math.floor(lon / ROAD_GRID_DEG), math.floor(lat / ROAD_GRID_DEG))].append(point_id)
    candidates: dict[int, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    processor = osmium.FileProcessor(str(pbf)).with_locations("flex_mem")
    for way in processor:
        if not way.is_way():
            continue
        ref = way.tags.get("ref")
        if not ref or not way.tags.get("highway"):
            continue
        nodes = [
            (node.location.lat, node.location.lon) for node in way.nodes if node.location.valid()
        ]
        for first, second in zip(nodes, nodes[1:], strict=False):
            mean_lat = (first[0] + second[0]) / 2.0
            lat_pad = MAX_NEARBY_M / 110_574.0
            lon_pad = MAX_NEARBY_M / (111_320.0 * max(0.2, math.cos(math.radians(mean_lat))))
            cells = {
                (cx, cy)
                for cx in range(
                    math.floor((min(first[1], second[1]) - lon_pad) / ROAD_GRID_DEG),
                    math.floor((max(first[1], second[1]) + lon_pad) / ROAD_GRID_DEG) + 1,
                )
                for cy in range(
                    math.floor((min(first[0], second[0]) - lat_pad) / ROAD_GRID_DEG),
                    math.floor((max(first[0], second[0]) + lat_pad) / ROAD_GRID_DEG) + 1,
                )
            }
            for point_id in {idx for cell in cells for idx in grid.get(cell, ())}:
                _, _, lat, lon, _ = flat[point_id]
                distance = _segment_distance_m(lat, lon, first, second)
                if distance > MAX_NEARBY_M:
                    continue
                way_id = str(way.id)
                key = (way_id, ref)
                old = candidates[point_id].get(key)
                if old is None or distance < old["distance_m"]:
                    candidates[point_id][key] = {
                        "distance_m": distance,
                        "way_id": way_id,
                        "ref": ref,
                    }

    out: dict[str, list[list[dict[str, Any]]]] = {
        leg_id: [[] for _ in samples] for leg_id, samples in samples_by_leg.items()
    }
    for point_id, rows in candidates.items():
        leg_id, sample_index, _, _, _ = flat[point_id]
        out[leg_id][sample_index] = sorted(
            rows.values(), key=lambda row: (row["distance_m"], row["way_id"], row["ref"])
        )
    return out


def _cdot_segments(
    features: list[dict[str, Any]],
) -> tuple[list[tuple[str, set[str], tuple[float, float], tuple[float, float]]], cKDTree]:
    segments = []
    centers = []
    for feature in features:
        properties = feature.get("properties") or {}
        name = str(properties.get("NAME") or properties.get("name") or "").strip()
        expected_refs = expected_route_refs(properties)
        if not name or not expected_refs:
            continue
        coordinates = feature.get("geometry", {}).get("coordinates") or []
        lines = (
            coordinates
            if feature.get("geometry", {}).get("type") == "MultiLineString"
            else [coordinates]
        )
        for line in lines:
            for first, second in zip(line, line[1:], strict=False):
                start = (float(first[1]), float(first[0]))
                end = (float(second[1]), float(second[0]))
                distance_m = _segment_length_m(start, end)
                pieces = max(1, math.ceil(distance_m / 60.0))
                previous = start
                for piece in range(1, pieces + 1):
                    fraction = piece / pieces
                    current = (
                        start[0] + fraction * (end[0] - start[0]),
                        start[1] + fraction * (end[1] - start[1]),
                    )
                    segments.append((name, expected_refs, previous, current))
                    centers.append(
                        ((previous[0] + current[0]) / 2.0, (previous[1] + current[1]) / 2.0)
                    )
                    previous = current
    if not centers:
        raise ValueError("CDOT dataset contains no usable route segments")
    xys = [_xy_m(lat, lon, 39.0) for lat, lon in centers]
    return segments, cKDTree(xys)


def _point_in_bbox(lat: float, lon: float, bbox: tuple[float, float, float, float] | None) -> bool:
    if bbox is None:
        return True
    left, bottom, right, top = bbox
    return left <= lon <= right and bottom <= lat <= top


def _point_route_mile(
    geometry: list[tuple[float, float, float]], point: tuple[float, float]
) -> tuple[float, float]:
    best_mile, best_distance = 0.0, float("inf")
    for first, second in zip(geometry, geometry[1:], strict=False):
        origin = (first[0] + second[0] + point[0]) / 3.0
        scale_x = 3958.7613 * math.pi / 180.0 * math.cos(math.radians(origin))
        scale_y = 3958.7613 * math.pi / 180.0
        dx, dy = (second[1] - first[1]) * scale_x, (second[0] - first[0]) * scale_y
        px, py = (point[1] - first[1]) * scale_x, (point[0] - first[0]) * scale_y
        length_squared = dx * dx + dy * dy
        fraction = (
            0.0 if length_squared == 0 else min(1.0, max(0.0, (px * dx + py * dy) / length_squared))
        )
        distance = math.hypot(px - fraction * dx, py - fraction * dy)
        if distance < best_distance:
            best_distance = distance
            best_mile = first[2] + fraction * (second[2] - first[2])
    return best_mile, best_distance


def _sample_runs(
    name: str,
    samples: list[tuple[float, float, float]],
    matches: list[dict[str, Any] | None],
    source_prefix: str,
) -> list[dict[str, Any]]:
    rows = []
    for index, match in enumerate(matches):
        if match is None:
            continue
        rows.append(
            {
                "name": name,
                "from_mi": max(0.0, samples[index][2] - SAMPLE_MI / 2.0),
                "to_mi": min(samples[-1][2], samples[index][2] + SAMPLE_MI / 2.0),
                "way_ids": [str(match["way_id"])],
                "route_refs": [str(match["ref"])],
                "source": source_prefix,
            }
        )
    return merge_and_filter_spans(rows)


def _load_cdot(cache_dir: Path) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / CDOT_CACHE_NAME
    if not path.exists():
        request = urllib.request.Request(
            CDOT_URL, headers={"User-Agent": "Freight-Fate scenic-road-data"}
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            path.write_bytes(response.read())
    return json.loads(path.read_text())


def _leg_id(leg: dict[str, Any]) -> str:
    return f"{leg['from']}:{leg['to']}"


def _span_source(
    prefix: str, pbf_date: str, way_ids: list[str], route_refs: list[str] | None = None
) -> str:
    ids = ", ".join(sorted(set(way_ids)))
    refs = ", ".join(sorted(set(route_refs or [])))
    route_source = f"; OSM route refs: {refs}" if refs else ""
    return f"{prefix}{route_source}; OpenStreetMap US PBF {pbf_date}; OSM way IDs: {ids}."


def derive_colorado_spans(
    features: list[dict[str, Any]],
    samples_by_leg: dict[str, list[tuple[float, float, float]]],
    osm_matches: dict[str, list[list[dict[str, Any]]]],
    pbf_date: str,
) -> dict[str, list[dict[str, Any]]]:
    segments, tree = _cdot_segments(features)
    output = {}
    for leg_id, samples in samples_by_leg.items():
        matches = osm_matches[leg_id]
        by_name: dict[str, list[dict[str, Any] | None]] = {}
        for sample_index, (lat, lon, _) in enumerate(samples):
            osm_candidates = matches[sample_index]
            point = _xy_m(lat, lon, 39.0)
            segment_indices = tree.query_ball_point(point, MAX_NEARBY_M + 40.0)
            for osm_match in osm_candidates:
                if float(osm_match["distance_m"]) > MAX_NEARBY_M:
                    continue
                for segment_index in segment_indices:
                    name, expected_refs, first, second = segments[segment_index]
                    if not any(
                        route_ref_matches(str(osm_match["ref"]), expected_ref)
                        for expected_ref in expected_refs
                    ):
                        continue
                    exact_distance = _segment_distance_m(lat, lon, first, second)
                    if exact_distance > MAX_NEARBY_M:
                        continue
                    sample_matches = by_name.setdefault(name, [None] * len(samples))
                    prior = sample_matches[sample_index]
                    row = {
                        "distance_m": exact_distance,
                        "way_id": osm_match["way_id"],
                        "ref": osm_match["ref"],
                    }
                    if prior is None or exact_distance < prior["distance_m"]:
                        sample_matches[sample_index] = row

        leg_spans = []
        for name, sample_matches in by_name.items():
            prefix = (
                f"Colorado SB21-263 / C.R.S. 43-1-401; CDOT Colorado Scenic and Historic Byways "
                f"GeoJSON dataset {CDOT_DATASET_ID}; exact CDOT route label and OSM route refs agree"
            )
            derived = _sample_runs(name, samples, sample_matches, prefix)
            for span in derived:
                span["source"] = _span_source(
                    prefix, pbf_date, span["way_ids"], span.get("route_refs", [])
                )
            leg_spans.extend(derived)
        output[leg_id] = merge_and_filter_spans(leg_spans)
    return output


def ref_numbers_for_osm(ref: str) -> set[str]:
    return ref_numbers(ref)


def derive_washington_spans(
    geometry: list[tuple[float, float, float]],
    samples: list[tuple[float, float, float]],
    osm_matches: list[list[dict[str, Any]]],
    pbf_date: str,
) -> list[dict[str, Any]]:
    spans = []
    for spec in WASHINGTON_SEGMENTS:
        sample_matches: list[dict[str, Any] | None] = [None] * len(samples)
        for index, ((lat, lon, _), candidates) in enumerate(zip(samples, osm_matches, strict=True)):
            matches = [
                candidate
                for candidate in candidates
                if route_ref_matches(str(candidate["ref"]), spec["ref"])
            ]
            if not matches or not _point_in_bbox(lat, lon, spec["bbox"]):
                continue
            sample_matches[index] = min(matches, key=lambda row: float(row["distance_m"]))
        prefix = f"{spec['source']}; designated segment: {spec['name']}; route ref {spec['ref']}"
        derived = _sample_runs(spec["name"], samples, sample_matches, prefix)
        termini = spec["termini"]
        if termini:
            for span in derived:
                for endpoint in termini:
                    projected_mile, offset_mi = _point_route_mile(geometry, endpoint)
                    if offset_mi <= 2.0:
                        if abs(projected_mile - span["from_mi"]) <= 3.0:
                            span["from_mi"] = max(span["from_mi"], projected_mile)
                        if abs(projected_mile - span["to_mi"]) <= 3.0:
                            span["to_mi"] = min(span["to_mi"], projected_mile)
                span["from_mi"] = max(0.0, float(span["from_mi"]))
                span["to_mi"] = min(geometry[-1][2], float(span["to_mi"]))
        for span in derived:
            span["source"] = _span_source(
                prefix, pbf_date, span["way_ids"], span.get("route_refs", [])
            )
        spans.extend(derived)
    return merge_and_filter_spans(spans)


def update_world(data: dict[str, Any], generated: dict[str, list[dict[str, Any]]]) -> int:
    changed = 0
    for leg in data["legs"]:
        leg_id = _leg_id(leg)
        if leg_id not in generated:
            continue
        corridor = leg.setdefault("corridor", {})
        spans = []
        for row in generated[leg_id]:
            record = {
                "from_mi": round(float(row["from_mi"]), 2),
                "to_mi": round(float(row["to_mi"]), 2),
                "name": str(row["name"]),
                "source": str(row["source"]),
            }
            if record["to_mi"] - record["from_mi"] >= MIN_SPAN_MI:
                spans.append(record)
        spans.sort(key=lambda row: (row["name"], row["from_mi"], row["to_mi"]))
        if corridor.get("billboard_bans") != spans:
            corridor["billboard_bans"] = spans
            changed += 1
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbf", type=Path, default=DEFAULT_PBF)
    parser.add_argument("--pbf-date", default=PBF_DATE)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--cdot-cache", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    data = load_world()
    geometries: dict[str, list[tuple[float, float, float]]] = {}
    samples_by_leg = {}
    for leg in data["legs"]:
        leg_id = _leg_id(leg)
        geometry = lg.corridor_geometry(leg)
        if not geometry:
            continue
        states = {
            str(row.get("state", "")).lower()
            for row in leg.get("corridor", {}).get("state_miles", []) or []
        }
        if not states.intersection({"colorado", "washington"}):
            continue
        geometries[leg_id] = geometry
        samples_by_leg[leg_id] = sample_geometry(geometry, SAMPLE_MI)

    pbf = corridor_ref_pbf(args.pbf, args.cache_dir)
    osm_matches = nearest_osm_ref_matches(pbf, samples_by_leg)
    cdot_path = args.cdot_cache or args.cache_dir / CDOT_CACHE_NAME
    if cdot_path.exists():
        features = json.loads(cdot_path.read_text()).get("features", [])
    else:
        features = _load_cdot(args.cache_dir).get("features", [])
    colorado_ids = {
        leg_id
        for leg_id, geometry in geometries.items()
        if any(
            str(row.get("state", "")).lower() == "colorado"
            for leg in data["legs"]
            if _leg_id(leg) == leg_id
            for row in leg.get("corridor", {}).get("state_miles", []) or []
        )
    }
    colorado = derive_colorado_spans(
        features,
        {leg_id: samples_by_leg[leg_id] for leg_id in colorado_ids},
        {leg_id: osm_matches[leg_id] for leg_id in colorado_ids},
        args.pbf_date,
    )
    generated = dict(colorado)
    for leg_id, geometry in geometries.items():
        leg_states = {
            str(row.get("state", "")).lower()
            for leg in data["legs"]
            if _leg_id(leg) == leg_id
            for row in leg.get("corridor", {}).get("state_miles", []) or []
        }
        if "washington" in leg_states:
            generated.setdefault(leg_id, []).extend(
                derive_washington_spans(
                    geometry, samples_by_leg[leg_id], osm_matches[leg_id], args.pbf_date
                )
            )
    changed = update_world(data, generated)
    span_count = sum(len(rows) for rows in generated.values())
    print(f"Derived {span_count} spans on {len(generated)} legs; {changed} legs changed.")
    if args.write:
        save_world(data)
        print("Wrote world source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
