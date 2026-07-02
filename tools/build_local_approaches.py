r"""Build compact local road approach data from checked-in world data and local OSM.

This is a build-time helper. Runtime gameplay reads ``local_approaches.json``
offline and never calls OSM, ORS, OSRM, Overpass, or external APIs.

Example:
    uv run --group tooling python tools/build_local_approaches.py \
      --cache-dir C:\Users\joshu\.cache\freight-fate-osm\regions --write
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import osmium

from freight_fate.data.world import get_world

ROOT = Path(__file__).resolve().parents[1]
CITY_SERVICES_PATH = ROOT / "src" / "freight_fate" / "data" / "city_services.json"
LOCAL_APPROACHES_PATH = ROOT / "src" / "freight_fate" / "data" / "local_approaches.json"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "freight-fate-osm" / "regions"
ACCESSED_DATE = "2026-06-27"
EARTH_RADIUS_MI = 3958.7613
GRID_DEGREES = 0.08
SEARCH_RADIUS_MI = 1.25

ROAD_HIGHWAYS = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "service",
    "living_street",
}

STATE_SLUGS = {"District of Columbia": "district-of-columbia"}


@dataclass
class Target:
    target_id: str
    target_type: str
    city: str
    state: str
    name: str
    lat: float
    lon: float
    role: str
    estimated: bool
    source_note: str
    fallback_reason: str = ""
    best_road: str = ""
    best_distance_mi: float = 999.0


def build_local_approaches(cache_dir: Path) -> dict[str, Any]:
    targets = collect_targets()
    by_state: dict[str, list[Target]] = defaultdict(list)
    for target in targets:
        by_state[target.state].append(target)

    sources: list[dict[str, Any]] = []
    for state, state_targets in sorted(by_state.items()):
        extract = state_extract_path(cache_dir, state)
        sources.append(source_record(state, extract))
        if extract.exists():
            snap_roads(extract, state_targets)
        else:
            for target in state_targets:
                target.fallback_reason = f"Missing local OSM extract: {extract}"

    approaches = {target.target_id: approach_record(target) for target in targets}
    payload = {
        "version": 1,
        "generated": {
            "accessed": ACCESSED_DATE,
            "family": "OpenStreetMap local Geofabrik extracts plus checked-in world data",
            "source_policy": "Build-time only; runtime reads this compact checked-in file.",
            "search_radius_mi": SEARCH_RADIUS_MI,
        },
        "sources": sources,
        "coverage": coverage_summary(approaches),
        "approaches": approaches,
    }
    return payload


def collect_targets() -> list[Target]:
    world = get_world()
    city_services = json.loads(CITY_SERVICES_PATH.read_text(encoding="utf-8"))
    targets: list[Target] = []

    for city_name in world.city_names():
        city = world.cities[city_name]
        for entry in city_services["cities"][city_name]:
            fallback = bool(entry.get("fallback"))
            targets.append(
                Target(
                    target_id=f"city_service:{slug(city_name)}:{entry['key']}",
                    target_type="city_service",
                    city=city_name,
                    state=city.state,
                    name=str(entry["name"]),
                    lat=float(entry["lat"]),
                    lon=float(entry["lon"]),
                    role=str(entry["key"]),
                    estimated=fallback,
                    source_note=str(entry.get("source_note", "")),
                    fallback_reason=str(entry.get("fallback_reason", "")),
                )
            )
        for location in city.locations:
            estimated = bool(location.template or "representative" in location.source_note.lower())
            targets.append(
                Target(
                    target_id=f"facility:{location.id}",
                    target_type="facility",
                    city=city_name,
                    state=city.state,
                    name=location.name,
                    lat=location.lat or city.lat,
                    lon=location.lon or city.lon,
                    role=location.type,
                    estimated=estimated,
                    source_note=location.source_note,
                    fallback_reason=(
                        "Facility coordinate is representative, so approach is an estimated "
                        "local road context rather than a real driveway or gate."
                        if estimated
                        else ""
                    ),
                )
            )
    return targets


def snap_roads(osm_path: Path, targets: list[Target]) -> None:
    grid = build_grid(targets)
    entities = osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY
    processor = (
        osmium.FileProcessor(str(osm_path), entities=entities)
        .with_locations()
        .with_filter(osmium.filter.KeyFilter("highway"))
    )
    for way in processor:
        if not hasattr(way, "nodes"):
            continue
        tags = {str(tag.k): str(tag.v) for tag in way.tags}
        road = road_label(tags)
        if not road:
            continue
        for lat, lon in way_coords(way):
            for target in nearby_targets(grid, lat, lon):
                distance = haversine_mi(lat, lon, target.lat, target.lon)
                if distance < target.best_distance_mi:
                    target.best_distance_mi = distance
                    target.best_road = road


def approach_record(target: Target) -> dict[str, Any]:
    has_road = bool(target.best_road) and target.best_distance_mi <= SEARCH_RADIUS_MI
    road = target.best_road if has_road else fallback_road(target)
    fallback = not has_road
    fallback_reason = target.fallback_reason
    if fallback and not fallback_reason:
        fallback_reason = (
            f"No named public OSM road found within {SEARCH_RADIUS_MI:.2f} miles "
            "of the target coordinate."
        )
    straight_line = haversine_mi(
        city_lat_lon(target)[0], city_lat_lon(target)[1], target.lat, target.lon
    )
    access_pad = target.best_distance_mi if has_road else 0.5
    minimum_miles = 2.1 if target.target_type == "facility" else 0.4
    approach_miles = round(max(minimum_miles, min(35.0, straight_line * 1.25 + access_pad)), 1)
    source_type = "osm_nearest_road" if has_road else "fallback_context"
    if target.estimated and has_road:
        source_type = "estimated_target_osm_nearest_road"
    return {
        "target_type": target.target_type,
        "city": target.city,
        "name": target.name,
        "role": target.role,
        "lat": round(target.lat, 6),
        "lon": round(target.lon, 6),
        "road": road,
        "approach_miles": approach_miles,
        "distance_to_road_mi": round(target.best_distance_mi if has_road else 0.0, 2),
        "source_type": source_type,
        "estimated": bool(target.estimated or fallback),
        "fallback": fallback,
        "fallback_reason": fallback_reason,
        "source_note": target.source_note,
        "turn_segments": [
            f"Use {road} for the local approach.",
            "Final gate or dock path is not turn-level sourced yet.",
        ],
    }


def city_lat_lon(target: Target) -> tuple[float, float]:
    world = get_world()
    city = world.cities[target.city]
    return city.lat, city.lon


def fallback_road(target: Target) -> str:
    if target.target_type == "city_service":
        return "local city service streets"
    return "local facility access road"


def coverage_summary(approaches: dict[str, dict[str, Any]]) -> dict[str, Any]:
    total = len(approaches)
    by_type: dict[str, dict[str, int]] = {}
    for record in approaches.values():
        item = by_type.setdefault(
            record["target_type"],
            {
                "total": 0,
                "osm_road": 0,
                "fallback": 0,
                "estimated": 0,
            },
        )
        item["total"] += 1
        if record["fallback"]:
            item["fallback"] += 1
        else:
            item["osm_road"] += 1
        if record["estimated"]:
            item["estimated"] += 1
    return {
        "approaches": total,
        "osm_road": sum(1 for record in approaches.values() if not record["fallback"]),
        "fallback": sum(1 for record in approaches.values() if record["fallback"]),
        "estimated": sum(1 for record in approaches.values() if record["estimated"]),
        "by_type": by_type,
    }


def build_grid(targets: list[Target]) -> dict[tuple[int, int], list[Target]]:
    grid: dict[tuple[int, int], list[Target]] = defaultdict(list)
    for target in targets:
        key = cell(target.lat, target.lon)
        grid[key].append(target)
    return grid


def nearby_targets(
    grid: dict[tuple[int, int], list[Target]], lat: float, lon: float
) -> list[Target]:
    row, col = cell(lat, lon)
    out: list[Target] = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            out.extend(grid.get((row + dr, col + dc), ()))
    return out


def cell(lat: float, lon: float) -> tuple[int, int]:
    return (math.floor(lat / GRID_DEGREES), math.floor(lon / GRID_DEGREES))


def road_label(tags: dict[str, str]) -> str:
    if tags.get("highway") not in ROAD_HIGHWAYS:
        return ""
    name = clean_name(tags.get("name", ""))
    ref = clean_name(tags.get("ref", ""))
    if name and ref:
        return f"{name} ({ref})"
    return name or ref or "unnamed public road"


def clean_name(value: str) -> str:
    return " ".join(str(value).split()).strip()


def way_coords(way) -> list[tuple[float, float]]:
    coords: list[tuple[float, float]] = []
    for node in way.nodes:
        try:
            if node.location.valid():
                coords.append((float(node.location.lat), float(node.location.lon)))
        except osmium.InvalidLocationError:
            continue
    return coords


def state_slug(state: str) -> str:
    return STATE_SLUGS.get(state, state.lower().replace(" ", "-"))


def state_extract_path(cache_dir: Path, state: str) -> Path:
    return cache_dir / f"{state_slug(state)}-latest.osm.pbf"


def source_record(state: str, extract: Path) -> dict[str, Any]:
    record: dict[str, Any] = {"state": state, "file": str(extract), "available": extract.exists()}
    if extract.exists():
        stat = extract.stat()
        record["bytes"] = stat.st_size
        record["modified"] = stat.st_mtime
    return record


def slug(value: str) -> str:
    out = []
    pending_dash = False
    for char in value.lower():
        if char.isalnum():
            if pending_dash and out:
                out.append("-")
            out.append(char)
            pending_dash = False
        else:
            pending_dash = True
    return "".join(out).strip("-") or "item"


def haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=LOCAL_APPROACHES_PATH)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    payload = build_local_approaches(args.cache_dir)
    print(json.dumps(payload["coverage"], indent=2, sort_keys=True))
    if args.write:
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
