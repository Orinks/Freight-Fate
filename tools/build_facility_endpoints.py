r"""Build source-backed freight facility endpoints from local OSM extracts.

Runtime gameplay reads ``facility_endpoints.json`` offline. This tool is
build-time only and never calls OSM, ORS, OSRM, Overpass, or external APIs.

Example:
    uv run --group tooling python tools/build_facility_endpoints.py \
      --cache-dir C:\Users\joshu\.cache\freight-fate-osm\regions --write
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

from freight_fate.data.world import get_world

ROOT = Path(__file__).resolve().parents[1]
FACILITY_ENDPOINTS_PATH = ROOT / "src" / "freight_fate" / "data" / "facility_endpoints.json"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "freight-fate-osm" / "regions"
ACCESSED_DATE = "2026-06-27"
EARTH_RADIUS_MI = 3958.7613
DEFAULT_RADIUS_MI = 32.0

RAW_MARKERS = (
    "osm_id",
    "amenity=",
    "highway=",
    "operator=",
    "node/",
    "way/",
    "relation/",
)
STATE_SLUGS = {"District of Columbia": "district-of-columbia"}
TARGET_FACILITY_TYPES = {
    "air_cargo",
    "automotive_plant",
    "chemical_petroleum_terminal",
    "cold_storage",
    "company_yard",
    "cross_dock",
    "distribution",
    "dry_warehouse",
    "food_processor",
    "food_terminal",
    "grocery_retail_dc",
    "industrial_park",
    "intermodal",
    "intermodal_ramp",
    "manufacturing",
    "manufacturing_plant",
    "parcel_hub",
    "port",
    "port_terminal",
    "rail",
    "retail_distribution",
    "steel_industrial",
    "terminal",
    "warehouse",
}


@dataclass(frozen=True)
class FacilityTarget:
    facility_id: str
    city: str
    state: str
    name: str
    facility_type: str
    lat: float
    lon: float
    source_note: str


@dataclass(frozen=True)
class Candidate:
    roles: tuple[str, ...]
    name: str
    lat: float
    lon: float
    score: int
    source_ref: str
    mapping: str


@dataclass
class CityBucket:
    targets: list[FacilityTarget] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)


def build_facility_endpoints(cache_dir: Path, *, radius_mi: float = DEFAULT_RADIUS_MI) -> dict[str, Any]:
    targets = collect_targets()
    by_state: dict[str, dict[str, CityBucket]] = defaultdict(dict)
    for target in targets:
        by_state[target.state].setdefault(target.city, CityBucket()).targets.append(target)

    payload = {
        "version": 1,
        "generated": {
            "accessed": ACCESSED_DATE,
            "family": "OpenStreetMap local Geofabrik extracts plus checked-in world facilities",
            "radius_mi": radius_mi,
            "source_policy": "Build-time only; runtime reads this compact checked-in file.",
            "gate_policy": (
                "OSM facility polygons/points are endpoint evidence. Gate, yard, driveway, "
                "and dock hints stay false unless a future source explicitly provides them."
            ),
            "road_policy": (
                "This layer does not snap sourced endpoints to roads. Runtime may combine "
                "it with local_approaches.json for existing nearest-road context."
            ),
        },
        "sources": [],
        "endpoints": {},
    }
    for state in sorted(by_state):
        extract = state_extract_path(cache_dir, state)
        payload["sources"].append(source_record(state, extract))
        buckets = by_state[state]
        if extract.exists():
            collect_state_candidates(extract, buckets, radius_mi)
        for city in sorted(buckets):
            for record in endpoint_records_for_city(buckets[city], extract, radius_mi):
                payload["endpoints"][record["facility_id"]] = record
    payload["coverage"] = coverage_summary(payload["endpoints"])
    return payload


def collect_targets() -> list[FacilityTarget]:
    world = get_world()
    targets: list[FacilityTarget] = []
    for city_name in world.city_names():
        city = world.cities[city_name]
        for location in city.locations:
            targets.append(FacilityTarget(
                facility_id=location.id,
                city=city_name,
                state=city.state,
                name=location.name,
                facility_type=location.type,
                lat=location.lat or city.lat,
                lon=location.lon or city.lon,
                source_note=location.source_note,
            ))
    return targets


def collect_state_candidates(
    osm_path: Path,
    buckets: dict[str, CityBucket],
    radius_mi: float,
) -> None:
    cities = {
        city: (bucket.targets[0].lat, bucket.targets[0].lon)
        for city, bucket in buckets.items()
        if bucket.targets
    }
    entities = osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY
    keys = [
        "name",
        "operator",
        "brand",
        "industrial",
        "landuse",
        "man_made",
        "building",
        "office",
        "amenity",
        "shop",
        "railway",
        "aeroway",
        "harbour",
        "seamark:type",
        "waterway",
    ]
    processor = (
        osmium.FileProcessor(str(osm_path), entities=entities)
        .with_locations()
        .with_filter(osmium.filter.KeyFilter(*keys))
    )
    for obj in processor:
        tags = _tags(obj.tags)
        if hasattr(obj, "nodes"):
            coords = _way_coords(obj)
            if not coords:
                continue
            lat, lon = _centroid(coords)
            candidate = candidate_from_tags(tags, lat, lon, f"way/{obj.id}")
            if candidate is None:
                continue
            for city in nearby_cities(cities, lat, lon, radius_mi):
                buckets[city].candidates.append(candidate)
            continue
        try:
            if not obj.location.valid():
                continue
            lat = float(obj.location.lat)
            lon = float(obj.location.lon)
        except osmium.InvalidLocationError:
            continue
        candidate = candidate_from_tags(tags, lat, lon, f"node/{obj.id}")
        if candidate is None:
            continue
        for city in nearby_cities(cities, lat, lon, radius_mi):
            buckets[city].candidates.append(candidate)


def endpoint_records_for_city(
    bucket: CityBucket,
    extract: Path,
    radius_mi: float,
) -> list[dict[str, Any]]:
    used_refs: set[str] = set()
    records: list[dict[str, Any]] = []
    for target in sorted(bucket.targets, key=lambda item: item.facility_id):
        candidate = choose_candidate(target, bucket.candidates, used_refs)
        if candidate is None:
            records.append(fallback_record(
                target,
                reason=f"No high-confidence source-backed OSM facility endpoint found within {radius_mi:.0f} miles in {extract.name}.",
            ))
            continue
        used_refs.add(candidate.source_ref)
        records.append({
            "facility_id": target.facility_id,
            "city": target.city,
            "state": target.state,
            "facility_name": target.name,
            "facility_type": target.facility_type,
            "endpoint_name": candidate.name,
            "lat": round(candidate.lat, 6),
            "lon": round(candidate.lon, 6),
            "approach_miles": approach_miles(target.lat, target.lon, candidate.lat, candidate.lon),
            "approach_road": "local facility access road",
            "source_type": "osm_facility_endpoint",
            "source_ref": candidate.source_ref,
            "source_backed": True,
            "fallback": False,
            "fallback_reason": "",
            "nearest_road_context": False,
            "turn_level_geometry": False,
            "gate_hint": False,
            "yard_hint": False,
            "dock_hint": False,
            "mapping": candidate.mapping,
            "source_note": (
                "Source-backed freight facility endpoint from a local OpenStreetMap "
                f"extract for {target.city}, {target.state}; matched to "
                f"{target.facility_type} by {candidate.mapping}; road snapping, gates, "
                f"yards, and docks are not claimed by this layer; accessed {ACCESSED_DATE}."
            ),
        })
    return records


def choose_candidate(
    target: FacilityTarget,
    candidates: list[Candidate],
    used_refs: set[str],
) -> Candidate | None:
    if target.facility_type not in TARGET_FACILITY_TYPES:
        return None
    choices = [
        candidate for candidate in candidates
        if target.facility_type in candidate.roles and candidate.source_ref not in used_refs
    ]
    if not choices:
        return None
    choices.sort(key=lambda candidate: (
        -candidate.score,
        _haversine_mi(target.lat, target.lon, candidate.lat, candidate.lon),
        candidate.name,
    ))
    return choices[0]


def fallback_record(target: FacilityTarget, reason: str) -> dict[str, Any]:
    return {
        "facility_id": target.facility_id,
        "city": target.city,
        "state": target.state,
        "facility_name": target.name,
        "facility_type": target.facility_type,
        "endpoint_name": target.name,
        "lat": round(target.lat, 6),
        "lon": round(target.lon, 6),
        "approach_miles": 0.0,
        "approach_road": "",
        "source_type": "representative_fallback",
        "source_ref": "",
        "source_backed": False,
        "fallback": True,
        "fallback_reason": reason,
        "nearest_road_context": False,
        "turn_level_geometry": False,
        "gate_hint": False,
        "yard_hint": False,
        "dock_hint": False,
        "mapping": "",
        "source_note": (
            f"Representative fallback for {target.name} in {target.city}; "
            "not a claim about a specific real-world shipper, gate, yard, or dock."
        ),
    }


def candidate_from_tags(
    tags: dict[str, str],
    lat: float,
    lon: float,
    source_ref: str,
) -> Candidate | None:
    name = clean_text(tags.get("name") or tags.get("operator") or tags.get("brand") or "")
    if not name:
        return None
    roles, score, mapping = classify(tags, name)
    if not roles:
        return None
    return Candidate(tuple(sorted(roles)), name, lat, lon, score, source_ref, mapping)


def classify(tags: dict[str, str], name: str) -> tuple[set[str], int, str]:
    lower_name = name.lower()
    values = " ".join(f"{key}={value}" for key, value in sorted(tags.items())).lower()
    text = f"{lower_name} {values}"
    roles: set[str] = set()
    score = 0
    reasons: list[str] = []

    logistics_terms = ("logistics", "freight", "warehouse", "distribution", "terminal", "cross dock", "cross-dock")
    industrial_terms = ("industrial", "manufacturing", "plant", "factory", "works")
    if tags.get("industrial") == "logistics" or any(term in text for term in logistics_terms):
        roles.update({"dry_warehouse", "warehouse", "distribution", "terminal", "cross_dock", "company_yard"})
        score += 78
        reasons.append("logistics/warehouse/freight tags or name")
    if tags.get("office") in {"logistics", "freight_forwarder"}:
        roles.update({"terminal", "distribution", "company_yard"})
        score += 84
        reasons.append("logistics office tags")
    if tags.get("landuse") in {"industrial", "commercial"} and any(term in text for term in logistics_terms):
        roles.update({"dry_warehouse", "warehouse", "distribution", "industrial_park"})
        score += 68
        reasons.append("industrial landuse with freight naming")

    if tags.get("railway") in {"yard", "terminal", "rail"} or "intermodal" in text or "rail yard" in text:
        roles.update({"intermodal_ramp", "intermodal", "rail"})
        score += 88
        reasons.append("rail/intermodal tags or name")
    if tags.get("landuse") == "railway" and any(term in text for term in ("yard", "intermodal", "terminal")):
        roles.update({"intermodal_ramp", "intermodal", "rail"})
        score += 70
        reasons.append("railway landuse with terminal naming")

    if tags.get("aeroway") in {"terminal", "hangar", "apron"} and any(term in text for term in ("cargo", "freight", "air cargo")):
        roles.add("air_cargo")
        score += 86
        reasons.append("air cargo tags or name")
    if "air cargo" in text or "cargo center" in text:
        roles.add("air_cargo")
        score += 78
        reasons.append("air cargo name")

    if tags.get("harbour") or tags.get("seamark:type") or any(term in text for term in ("port", "container terminal", "marine terminal")):
        roles.update({"port", "port_terminal"})
        score += 84
        reasons.append("port/container terminal tags or name")

    if any(term in text for term in ("cold storage", "refrigerated", "reefer", "freezer")):
        roles.add("cold_storage")
        score += 82
        reasons.append("cold storage naming")
    if any(term in text for term in ("food", "produce", "grocery")) and any(term in text for term in logistics_terms):
        roles.update({"food_terminal", "food_processor", "grocery_retail_dc"})
        score += 70
        reasons.append("food/grocery logistics naming")

    if tags.get("man_made") == "works" or tags.get("building") in {"industrial", "factory"} or any(term in text for term in industrial_terms):
        roles.update({"manufacturing", "manufacturing_plant", "industrial_park"})
        score += 68
        reasons.append("manufacturing/industrial tags")
    if any(term in text for term in ("steel", "metal", "mill")):
        roles.add("steel_industrial")
        score += 78
        reasons.append("steel/metal naming")
    if any(term in text for term in ("automotive", "auto plant", "assembly", "vehicle plant")):
        roles.add("automotive_plant")
        score += 78
        reasons.append("automotive plant naming")
    if any(term in text for term in ("chemical", "petroleum", "oil terminal", "tank farm", "refinery")):
        roles.add("chemical_petroleum_terminal")
        score += 78
        reasons.append("chemical/petroleum naming")
    if any(term in text for term in ("parcel", "package", "sortation", "fulfillment")):
        roles.add("parcel_hub")
        score += 76
        reasons.append("parcel/fulfillment naming")
    if tags.get("shop") == "truck" or "truck terminal" in text:
        roles.update({"terminal", "company_yard"})
        score += 75
        reasons.append("truck terminal tags or name")

    if score < 68:
        return set(), 0, ""
    return roles, min(score, 99), "; ".join(reasons[:3])


def coverage_summary(endpoints: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, dict[str, int]] = {}
    source_backed = 0
    fallback = 0
    gate_hints = 0
    for record in endpoints.values():
        item = by_type.setdefault(record["facility_type"], {"total": 0, "source_backed": 0, "fallback": 0})
        item["total"] += 1
        if record["source_backed"]:
            source_backed += 1
            item["source_backed"] += 1
        else:
            fallback += 1
            item["fallback"] += 1
        if record["gate_hint"] or record["yard_hint"] or record["dock_hint"]:
            gate_hints += 1
    return {
        "facilities": len(endpoints),
        "source_backed": source_backed,
        "fallback": fallback,
        "nearest_road_context": sum(1 for record in endpoints.values() if record["nearest_road_context"]),
        "turn_level_geometry": sum(1 for record in endpoints.values() if record["turn_level_geometry"]),
        "gate_yard_dock_hints": gate_hints,
        "by_type": by_type,
    }


def nearby_cities(
    cities: dict[str, tuple[float, float]],
    lat: float,
    lon: float,
    radius_mi: float,
) -> list[str]:
    return [
        city for city, (city_lat, city_lon) in cities.items()
        if _haversine_mi(city_lat, city_lon, lat, lon) <= radius_mi
    ]


def approach_miles(start_lat: float, start_lon: float, lat: float, lon: float) -> float:
    straight_line = _haversine_mi(start_lat, start_lon, lat, lon)
    return round(max(2.1, min(35.0, straight_line * 1.25)), 1)


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


def _centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    return (
        sum(lat for lat, _lon in points) / len(points),
        sum(lon for _lat, lon in points) / len(points),
    )


def clean_text(value: str) -> str:
    text = " ".join(str(value).split()).strip()
    lowered = text.lower()
    if any(marker in lowered for marker in RAW_MARKERS):
        return ""
    return text


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=FACILITY_ENDPOINTS_PATH)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    payload = build_facility_endpoints(args.cache_dir)
    print(json.dumps(payload["coverage"], indent=2, sort_keys=True))
    if args.write:
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
