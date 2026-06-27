r"""Build source-backed city service POIs from local OSM extracts.

Development-time helper only. Runtime gameplay reads the checked-in compact
``city_services.json`` and never calls OSM, ORS, Overpass, or operator sites.

Example:
    uv run --group tooling python tools/build_city_services.py \
      --osm C:\Users\joshu\.cache\freight-fate-osm\regions\illinois-latest.osm.pbf \
      --city Chicago --radius-mi 28 --write
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import osmium

ROOT = Path(__file__).resolve().parents[1]
WORLD_PATH = ROOT / "src" / "freight_fate" / "data" / "world.json"
CITY_SERVICES_PATH = ROOT / "src" / "freight_fate" / "data" / "city_services.json"
EARTH_RADIUS_MI = 3958.7613
ACCESSED_DATE = "2026-06-27"
SERVICE_ORDER = ("freight_market", "garage", "truck_dealer")

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


class CityServiceHandler(osmium.SimpleHandler):
    def __init__(self, city_lat: float, city_lon: float, radius_mi: float) -> None:
        super().__init__()
        self.city_lat = city_lat
        self.city_lon = city_lon
        self.radius_mi = radius_mi
        self.candidates: list[Candidate] = []
        self.road_points: list[RoadPoint] = []

    def node(self, node) -> None:
        if not node.location.valid():
            return
        lat = float(node.location.lat)
        lon = float(node.location.lon)
        if not self._in_radius(lat, lon):
            return
        tags = _tags(node.tags)
        candidate = _candidate_from_tags(tags, lat, lon, f"node/{node.id}")
        if candidate is not None:
            self.candidates.append(candidate)

    def way(self, way) -> None:
        tags = _tags(way.tags)
        coords = _way_coords(way)
        if not coords:
            return
        local = [(lat, lon) for lat, lon in coords if self._in_radius(lat, lon)]
        if not local:
            return
        lat, lon = _centroid(local)
        candidate = _candidate_from_tags(tags, lat, lon, f"way/{way.id}")
        if candidate is not None:
            self.candidates.append(candidate)
        road_label = _road_label(tags)
        if road_label:
            stride = max(1, len(local) // 12)
            for rlat, rlon in local[::stride]:
                self.road_points.append(RoadPoint(rlat, rlon, road_label))

    def _in_radius(self, lat: float, lon: float) -> bool:
        return _haversine_mi(self.city_lat, self.city_lon, lat, lon) <= self.radius_mi


def build_city_services(
    osm_path: Path,
    city: str,
    state: str,
    city_lat: float,
    city_lon: float,
    radius_mi: float,
) -> list[dict[str, Any]]:
    candidates, road_points = _collect_from_osm(osm_path, city_lat, city_lon, radius_mi)
    chosen: dict[str, Candidate] = {}
    for key in SERVICE_ORDER:
        choices = [c for c in candidates if c.key == key]
        if not choices:
            continue
        choices.sort(key=lambda c: (-c.score, _haversine_mi(city_lat, city_lon, c.lat, c.lon)))
        chosen[key] = choices[0]

    entries: list[dict[str, Any]] = []
    for key in SERVICE_ORDER:
        candidate = chosen.get(key)
        if candidate is None:
            continue
        road = _nearest_road(candidate, road_points)
        approach_miles = _approach_miles(city_lat, city_lon, candidate.lat, candidate.lon)
        entries.append({
            "key": key,
            "kind": key,
            "name": candidate.name,
            "city": city,
            "state": state,
            "lat": round(candidate.lat, 6),
            "lon": round(candidate.lon, 6),
            "approach_miles": approach_miles,
            "approach_road": road,
            "source_type": "osm",
            "source_ref": candidate.source_ref,
            "fallback": False,
            "source_note": (
                "Source-backed city service POI from a local OpenStreetMap "
                f"extract for {city}, {state}; category mapped as "
                f"{candidate.mapping}; accessed {ACCESSED_DATE}."
            ),
        })
    return entries


def _collect_from_osm(
    osm_path: Path,
    city_lat: float,
    city_lon: float,
    radius_mi: float,
) -> tuple[list[Candidate], list[RoadPoint]]:
    candidates: list[Candidate] = []
    road_points: list[RoadPoint] = []
    entities = osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY
    processor = (
        osmium.FileProcessor(str(osm_path), entities=entities)
        .with_locations()
        .with_filter(osmium.filter.KeyFilter(
            "shop",
            "amenity",
            "craft",
            "office",
            "industrial",
            "landuse",
            "highway",
            "hgv",
            "service:vehicle:hgv",
        ))
    )
    for obj in processor:
        tags = _tags(obj.tags)
        if hasattr(obj, "nodes"):
            coords = _way_coords(obj)
            if not coords:
                continue
            local = [
                (lat, lon)
                for lat, lon in coords
                if _haversine_mi(city_lat, city_lon, lat, lon) <= radius_mi
            ]
            if not local:
                continue
            lat, lon = _centroid(local)
            candidate = _candidate_from_tags(tags, lat, lon, f"way/{obj.id}")
            if candidate is not None:
                candidates.append(candidate)
            road_label = _road_label(tags)
            if road_label:
                stride = max(1, len(local) // 12)
                for rlat, rlon in local[::stride]:
                    road_points.append(RoadPoint(rlat, rlon, road_label))
            continue
        if not obj.location.valid():
            continue
        lat = float(obj.location.lat)
        lon = float(obj.location.lon)
        if _haversine_mi(city_lat, city_lon, lat, lon) > radius_mi:
            continue
        candidate = _candidate_from_tags(tags, lat, lon, f"node/{obj.id}")
        if candidate is not None:
            candidates.append(candidate)
    return candidates, road_points


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
        "transport",
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


def _write_entries(path: Path, city: str, entries: list[dict[str, Any]],
                   source_path: Path, radius_mi: float) -> None:
    payload = {
        "version": 1,
        "source": {
            "family": "OpenStreetMap local extract",
            "file": str(source_path),
            "accessed": ACCESSED_DATE,
            "radius_mi": radius_mi,
        },
        "cities": {},
    }
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("version", 1)
    payload.setdefault("cities", {})
    payload["cities"][city] = entries
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--osm", type=Path, required=True,
                        help="Local .osm, .osm.pbf, or .osm.gz extract")
    parser.add_argument("--city", required=True, help="Supported Freight Fate city")
    parser.add_argument("--radius-mi", type=float, default=28.0)
    parser.add_argument("--output", type=Path, default=CITY_SERVICES_PATH)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    state, lat, lon = _world_city(args.city)
    entries = build_city_services(args.osm, args.city, state, lat, lon, args.radius_mi)
    print(json.dumps(entries, indent=2, sort_keys=True))
    missing = [key for key in SERVICE_ORDER if key not in {entry["key"] for entry in entries}]
    if missing:
        print(f"Missing source-backed services for {args.city}: {', '.join(missing)}")
    if args.write:
        _write_entries(args.output, args.city, entries, args.osm, args.radius_mi)
        print(f"Wrote {args.output}")
    return 0 if entries else 1


if __name__ == "__main__":
    raise SystemExit(main())
