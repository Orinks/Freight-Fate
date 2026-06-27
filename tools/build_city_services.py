r"""Build source-backed city service POIs from local OSM extracts.

Development-time helper only. Runtime gameplay reads the checked-in compact
``city_services.json`` and never calls OSM, ORS, Overpass, or operator sites.

Examples:
    uv run --group tooling python tools/build_city_services.py \
      --osm C:\Users\joshu\.cache\freight-fate-osm\regions\illinois-latest.osm.pbf \
      --city Chicago --write

    uv run --group tooling python tools/build_city_services.py \
      --all-supported --cache-dir C:\Users\joshu\.cache\freight-fate-osm\regions \
      --write
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import osmium

ROOT = Path(__file__).resolve().parents[1]
WORLD_PATH = ROOT / "src" / "freight_fate" / "data" / "world.json"
CITY_SERVICES_PATH = ROOT / "src" / "freight_fate" / "data" / "city_services.json"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "freight-fate-osm" / "regions"
EARTH_RADIUS_MI = 3958.7613
ACCESSED_DATE = "2026-06-27"
SERVICE_ORDER = ("freight_market", "garage", "truck_dealer")
DEFAULT_RADIUS_MI = 28.0

SERVICE_LABELS = {
    "freight_market": "freight market office",
    "garage": "garage",
    "truck_dealer": "truck dealer",
}

FALLBACK_APPROACH_MILES = {
    "freight_market": 2.5,
    "garage": 1.4,
    "truck_dealer": 4.5,
}

FALLBACK_APPROACH_ROADS = {
    "freight_market": "local freight district streets",
    "garage": "terminal service road",
    "truck_dealer": "dealer access road",
}

ROAD_HIGHWAYS = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "service",
}

RAW_TEXT_MARKERS = (
    "osm_id",
    "amenity=",
    "highway=",
    "operator=",
    "node/",
    "way/",
    "relation/",
)

STATE_SLUGS = {
    "District of Columbia": "district-of-columbia",
}


@dataclass(frozen=True)
class CityInfo:
    name: str
    state: str
    lat: float
    lon: float
    radius_mi: float = DEFAULT_RADIUS_MI


@dataclass(frozen=True)
class Candidate:
    key: str
    name: str
    lat: float
    lon: float
    score: int
    source_ref: str
    mapping: str


@dataclass(frozen=True)
class RoadPoint:
    lat: float
    lon: float
    label: str


@dataclass
class CityBucket:
    city: CityInfo
    candidates: list[Candidate] = field(default_factory=list)
    roads: list[RoadPoint] = field(default_factory=list)


def build_city_services(
    osm_path: Path,
    city: str,
    state: str,
    city_lat: float,
    city_lon: float,
    radius_mi: float,
) -> list[dict[str, Any]]:
    buckets = collect_state_services(
        osm_path,
        [CityInfo(city, state, city_lat, city_lon, radius_mi)],
        include_roads=True,
    )
    return build_entries_for_city(buckets[city], osm_path)


def build_all_supported(
    cache_dir: Path,
    *,
    radius_mi: float = DEFAULT_RADIUS_MI,
) -> dict[str, Any]:
    cities = load_world_cities(radius_mi=radius_mi)
    by_state: dict[str, list[CityInfo]] = defaultdict(list)
    for city in cities:
        by_state[city.state].append(city)

    payload: dict[str, Any] = {
        "version": 2,
        "generated": {
            "accessed": ACCESSED_DATE,
            "family": "OpenStreetMap local Geofabrik extracts",
            "radius_mi": radius_mi,
            "source_policy": "Build-time only; runtime reads this compact checked-in file.",
        },
        "sources": [],
        "cities": {},
    }

    for state in sorted(by_state):
        extract = state_extract_path(cache_dir, state)
        state_cities = sorted(by_state[state], key=lambda item: item.name)
        if not extract.exists():
            for city in state_cities:
                payload["cities"][city.name] = fallback_entries(
                    city,
                    f"Missing local OSM extract: {extract}",
                )
            payload["sources"].append(source_record(state, extract, available=False))
            continue
        payload["sources"].append(source_record(state, extract, available=True))
        buckets = collect_state_services(extract, state_cities, include_roads=False)
        for city in state_cities:
            payload["cities"][city.name] = build_entries_for_city(buckets[city.name], extract)

    payload["coverage"] = coverage_summary(payload)
    return payload


def collect_state_services(
    osm_path: Path,
    cities: list[CityInfo],
    *,
    include_roads: bool = False,
) -> dict[str, CityBucket]:
    buckets = {city.name: CityBucket(city) for city in cities}
    entities = osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY
    keys = [
        "shop",
        "amenity",
        "craft",
        "office",
        "industrial",
        "landuse",
        "hgv",
        "service:vehicle:hgv",
    ]
    if include_roads:
        keys.append("highway")
    processor = (
        osmium.FileProcessor(str(osm_path), entities=entities)
        .with_locations()
        .with_filter(osmium.filter.KeyFilter(*keys))
    )
    for obj in processor:
        tags = _tags(obj.tags)
        if hasattr(obj, "nodes"):
            _collect_way(obj, tags, cities, buckets, include_roads=include_roads)
            continue
        _collect_node(obj, tags, cities, buckets)
    return buckets


def _collect_node(obj, tags: dict[str, str], cities: list[CityInfo],
                  buckets: dict[str, CityBucket]) -> None:
    if not obj.location.valid():
        return
    lat = float(obj.location.lat)
    lon = float(obj.location.lon)
    candidate_cache: Candidate | None | bool = False
    for city in nearby_cities(cities, lat, lon):
        if candidate_cache is False:
            candidate_cache = _candidate_from_tags(tags, lat, lon, f"node/{obj.id}")
        if candidate_cache is not None:
            buckets[city.name].candidates.append(candidate_cache)


def _collect_way(obj, tags: dict[str, str], cities: list[CityInfo],
                 buckets: dict[str, CityBucket], *, include_roads: bool) -> None:
    coords = _way_coords(obj)
    if not coords:
        return
    road_label = _road_label(tags)
    for city in cities:
        local = [
            (lat, lon)
            for lat, lon in coords
            if _haversine_mi(city.lat, city.lon, lat, lon) <= city.radius_mi
        ]
        if not local:
            continue
        lat, lon = _centroid(local)
        candidate = _candidate_from_tags(tags, lat, lon, f"way/{obj.id}")
        if candidate is not None:
            buckets[city.name].candidates.append(candidate)
        if road_label and include_roads:
            stride = max(1, len(local) // 12)
            for rlat, rlon in local[::stride]:
                buckets[city.name].roads.append(RoadPoint(rlat, rlon, road_label))


def build_entries_for_city(bucket: CityBucket, source_path: Path) -> list[dict[str, Any]]:
    city = bucket.city
    chosen: dict[str, Candidate] = {}
    for key in SERVICE_ORDER:
        choices = [c for c in bucket.candidates if c.key == key]
        if not choices:
            continue
        choices.sort(key=lambda c: (-c.score, _haversine_mi(city.lat, city.lon, c.lat, c.lon)))
        chosen[key] = choices[0]

    entries: list[dict[str, Any]] = []
    for key in SERVICE_ORDER:
        candidate = chosen.get(key)
        if candidate is None:
            entries.append(fallback_entry(
                city,
                key,
                "No realistic source-backed OSM candidate found within "
                f"{city.radius_mi:.0f} miles in {source_path.name}.",
            ))
            continue
        road = _nearest_road(candidate, bucket.roads)
        approach_miles = _approach_miles(city.lat, city.lon, candidate.lat, candidate.lon)
        entries.append({
            "key": key,
            "kind": key,
            "name": candidate.name,
            "city": city.name,
            "state": city.state,
            "lat": round(candidate.lat, 6),
            "lon": round(candidate.lon, 6),
            "approach_miles": approach_miles,
            "approach_road": road,
            "source_type": "osm",
            "source_ref": candidate.source_ref,
            "fallback": False,
            "source_note": (
                "Source-backed city service POI from a local OpenStreetMap "
                f"extract for {city.name}, {city.state}; category mapped as "
                f"{candidate.mapping}; accessed {ACCESSED_DATE}."
            ),
        })
    return entries


def fallback_entries(city: CityInfo, reason: str) -> list[dict[str, Any]]:
    return [fallback_entry(city, key, reason) for key in SERVICE_ORDER]


def fallback_entry(city: CityInfo, key: str, reason: str) -> dict[str, Any]:
    names = {
        "freight_market": f"{city.name} Freight Market Office",
        "garage": f"{city.name} Company Yard Garage",
        "truck_dealer": f"{city.name} Truck Dealer",
    }
    return {
        "key": key,
        "kind": key,
        "name": names[key],
        "city": city.name,
        "state": city.state,
        "lat": round(city.lat, 6),
        "lon": round(city.lon, 6),
        "approach_miles": FALLBACK_APPROACH_MILES[key],
        "approach_road": FALLBACK_APPROACH_ROADS[key],
        "source_type": "fallback",
        "source_ref": "",
        "fallback": True,
        "fallback_reason": reason,
        "source_note": (
            f"Representative fallback {SERVICE_LABELS[key]} for {city.name}, "
            f"{city.state}; not a claim about a real-world service POI."
        ),
    }


def coverage_summary(payload: dict[str, Any]) -> dict[str, Any]:
    city_count = len(payload["cities"])
    source_backed = 0
    fallback = 0
    by_role: dict[str, dict[str, int]] = {
        key: {"source_backed": 0, "fallback": 0} for key in SERVICE_ORDER
    }
    fallback_roles: dict[str, list[str]] = {}
    for city, entries in payload["cities"].items():
        city_fallbacks: list[str] = []
        for entry in entries:
            role = entry["key"]
            if entry.get("fallback"):
                fallback += 1
                by_role[role]["fallback"] += 1
                city_fallbacks.append(role)
            else:
                source_backed += 1
                by_role[role]["source_backed"] += 1
        if city_fallbacks:
            fallback_roles[city] = city_fallbacks
    return {
        "cities": city_count,
        "service_roles": city_count * len(SERVICE_ORDER),
        "source_backed": source_backed,
        "fallback": fallback,
        "by_role": by_role,
        "cities_with_any_fallback": len(fallback_roles),
        "fallback_roles": fallback_roles,
    }


def source_record(state: str, extract: Path, *, available: bool) -> dict[str, Any]:
    record: dict[str, Any] = {
        "state": state,
        "file": str(extract),
        "available": available,
    }
    if available:
        stat = extract.stat()
        record["bytes"] = stat.st_size
        record["modified"] = stat.st_mtime
    return record


def nearby_cities(cities: list[CityInfo], lat: float, lon: float) -> list[CityInfo]:
    return [
        city for city in cities
        if _haversine_mi(city.lat, city.lon, lat, lon) <= city.radius_mi
    ]


def load_world_cities(*, radius_mi: float = DEFAULT_RADIUS_MI) -> list[CityInfo]:
    data = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    return [
        CityInfo(
            name=str(name),
            state=str(raw["state"]),
            lat=float(raw["lat"]),
            lon=float(raw["lon"]),
            radius_mi=radius_mi,
        )
        for name, raw in sorted(data["cities"].items())
    ]


def state_slug(state: str) -> str:
    return STATE_SLUGS.get(state, state.lower().replace(" ", "-"))


def state_extract_path(cache_dir: Path, state: str) -> Path:
    return cache_dir / f"{state_slug(state)}-latest.osm.pbf"


def _tags(tags) -> dict[str, str]:
    return {str(tag.k): str(tag.v) for tag in tags}


def _way_coords(way) -> list[tuple[float, float]]:
    coords: list[tuple[float, float]] = []
    for node in way.nodes:
        try:
            if node.location.valid():
                coords.append((float(node.location.lat), float(node.location.lon)))
        except osmium.InvalidLocationError:
            continue
    return coords


def _candidate_from_tags(
    tags: dict[str, str],
    lat: float,
    lon: float,
    source_ref: str,
) -> Candidate | None:
    name = _clean_name(tags.get("name") or tags.get("operator") or tags.get("brand") or "")
    if not name:
        return None
    key, score, mapping = _classify(tags, name)
    if key is None:
        return None
    return Candidate(key, name, lat, lon, score, source_ref, mapping)


def _classify(tags: dict[str, str], name: str) -> tuple[str | None, int, str]:
    lower_name = name.lower()
    values = " ".join(f"{key}={value}" for key, value in sorted(tags.items())).lower()
    text = f"{lower_name} {values}"
    truck_terms = (
        "truck",
        "hgv",
        "diesel",
        "fleet",
        "freightliner",
        "kenworth",
        "peterbilt",
        "mack",
        "international",
        "volvo trucks",
    )
    logistics_terms = (
        "logistics",
        "freight",
        "intermodal",
        "distribution",
        "warehouse",
        "terminal",
        "cross dock",
    )

    if tags.get("shop") == "truck" or any(term in text for term in (
        "freightliner",
        "kenworth",
        "peterbilt",
        "mack truck",
        "international trucks",
        "volvo trucks",
    )):
        return "truck_dealer", 90, "truck dealer or heavy-vehicle sales/service tags"
    if "dealer" in lower_name and any(term in text for term in truck_terms):
        return "truck_dealer", 82, "dealer name with truck/heavy-vehicle context"

    repair_tags = {tags.get("shop"), tags.get("amenity"), tags.get("craft")}
    if {"truck_repair", "vehicle_repair", "car_repair"} & repair_tags:
        score = 80 if any(term in text for term in truck_terms) else 50
        return "garage", score, "vehicle repair tags with truck relevance scoring"
    if "repair" in lower_name and any(term in text for term in truck_terms):
        return "garage", 76, "repair name with truck/heavy-vehicle context"

    if tags.get("office") in {"logistics", "freight_forwarder"}:
        return "freight_market", 86, "logistics or freight-forwarder office tags"
    if tags.get("office") == "transport" and any(term in text for term in logistics_terms):
        return "freight_market", 78, "transport office with freight/logistics context"
    if tags.get("industrial") == "logistics":
        return "freight_market", 80, "industrial logistics tag"
    if tags.get("landuse") == "industrial" and any(term in text for term in logistics_terms):
        return "freight_market", 70, "industrial landuse with logistics/freight name"
    if any(term in lower_name for term in logistics_terms):
        return "freight_market", 64, "named logistics/freight facility"

    return None, 0, ""


def _clean_name(value: str) -> str:
    name = " ".join(str(value).split()).strip()
    lowered = name.lower()
    if any(marker in lowered for marker in RAW_TEXT_MARKERS):
        return ""
    return name


def _road_label(tags: dict[str, str]) -> str:
    if tags.get("highway") not in ROAD_HIGHWAYS:
        return ""
    name = _clean_name(tags.get("name", ""))
    ref = _clean_name(tags.get("ref", ""))
    if name and ref:
        return f"{name} ({ref})"
    return name or ref


def _nearest_road(candidate: Candidate, roads: list[RoadPoint]) -> str:
    if not roads:
        return "local industrial access road"
    nearest = min(roads, key=lambda road: _haversine_mi(
        candidate.lat, candidate.lon, road.lat, road.lon))
    return nearest.label


def _approach_miles(city_lat: float, city_lon: float, lat: float, lon: float) -> float:
    straight_line = _haversine_mi(city_lat, city_lon, lat, lon)
    return round(max(0.6, min(25.0, straight_line * 1.35)), 1)


def _centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    return (
        sum(lat for lat, _lon in points) / len(points),
        sum(lon for _lat, lon in points) / len(points),
    )


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


def _world_city(city: str) -> tuple[str, float, float]:
    data = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    raw = data["cities"][city]
    return str(raw["state"]), float(raw["lat"]), float(raw["lon"])


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_single_city(path: Path, city: str, entries: list[dict[str, Any]],
                       source_path: Path, radius_mi: float) -> None:
    payload = {
        "version": 2,
        "generated": {
            "accessed": ACCESSED_DATE,
            "family": "OpenStreetMap local extract",
            "radius_mi": radius_mi,
            "source_policy": "Build-time only; runtime reads this compact checked-in file.",
        },
        "sources": [source_record(entries[0]["state"] if entries else "", source_path,
                                  available=source_path.exists())],
        "cities": {},
    }
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("version", 2)
    payload.setdefault("cities", {})
    payload["cities"][city] = entries
    payload["coverage"] = coverage_summary(payload)
    _write_payload(path, payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--all-supported", action="store_true",
                      help="Build all supported world.json cities from local state extracts")
    mode.add_argument("--city", help="Supported Freight Fate city for a single-city build")
    parser.add_argument("--osm", type=Path,
                        help="Local .osm, .osm.pbf, or .osm.gz extract for --city")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR,
                        help="Directory containing <state>-latest.osm.pbf files")
    parser.add_argument("--radius-mi", type=float, default=DEFAULT_RADIUS_MI)
    parser.add_argument("--output", type=Path, default=CITY_SERVICES_PATH)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    if args.all_supported:
        payload = build_all_supported(args.cache_dir, radius_mi=args.radius_mi)
        print(json.dumps(payload["coverage"], indent=2, sort_keys=True))
        if args.write:
            _write_payload(args.output, payload)
            print(f"Wrote {args.output}")
        return 0

    if args.osm is None:
        parser.error("--city requires --osm")
    state, lat, lon = _world_city(args.city)
    city_info = CityInfo(args.city, state, lat, lon, args.radius_mi)
    entries = build_city_services(args.osm, args.city, state, lat, lon, args.radius_mi)
    found = {entry["key"] for entry in entries}
    entries.extend(
        fallback_entry(
            city_info,
            key,
            f"No realistic source-backed OSM candidate found within {args.radius_mi:.0f} miles "
            f"in {args.osm.name}.",
        )
        for key in SERVICE_ORDER
        if key not in found
    )
    entries.sort(key=lambda item: SERVICE_ORDER.index(item["key"]))
    print(json.dumps(entries, indent=2, sort_keys=True))
    if args.write:
        _write_single_city(args.output, args.city, entries, args.osm, args.radius_mi)
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
