"""Build-time route enrichment helpers for corridor metadata.

Runtime gameplay stays offline. This tool either reads checked-in world data or
performs tiny live smoke checks for one representative corridor: no-key
OSRM/Open-Meteo, or OpenRouteService driving-hgv (truck) routing when an
``ORS_API_KEY`` is set in the environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORLD_PATH = ROOT / "src" / "freight_fate" / "data" / "world.json"
CACHE_PATH = ROOT / ".route-cache"
USER_AGENT = "Freight-Fate route-enrichment smoke (https://github.com/Orinks/Freight-Fate)"
OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving/{coords}"
OPEN_METEO_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
# OpenRouteService heavy-goods (truck) routing. Build-time only; the key lives
# in the environment and is never bundled or read at runtime. One driving-hgv
# request returns truck-legal geometry with elevation plus steepness and
# tollway extras -- the inputs the corridor builders already consume.
ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/{profile}/geojson"
ORS_HGV_PROFILE = "driving-hgv"
ORS_API_KEY_ENV = "ORS_API_KEY"
ORS_EXTRA_INFO = ("steepness", "tollways", "waytype")
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_URLS = (
    OVERPASS_URL,
    "https://overpass.kumi.systems/api/interpreter",
)
CENSUS_STATES_URL = (
    "https://www2.census.gov/geo/tiger/GENZ2023/shp/"
    "cb_2023_us_state_500k.zip"
)
CENSUS_STATES_GEOJSON_URL = (
    "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
)
SIMPLE_STATES_GEOJSON_URL = (
    "https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json"
)
OSRM_TIMEOUT_S = 12
REQUIRED_METADATA_FIELDS = (
    "route_points",
    "checkpoints",
    "state_miles",
    "elevation_samples",
    "grade_segments",
    "curated_pois",
    "poi_density",
    "fuel_poi_support",
)
ELEVATION_SOURCE = (
    "Open-Meteo Elevation API development-time sample from Copernicus DEM GLO-90."
)
CORRIDOR_SOURCE = (
    "Development-time OSRM route geometry over OpenStreetMap, with Open-Meteo "
    "elevation samples, Census/OpenStreetMap state context, and curated "
    "corridor POIs checked in for offline runtime use."
)
HIGH_PRIORITY_REMAINING_CORRIDORS = (
    {
        "from": "Philadelphia",
        "to": "Pittsburgh",
        "label": "PA Turnpike / I-76 Allegheny corridor",
        "why": "major toll corridor with service plazas, grades, tunnels, and emergency service modeling",
    },
    {
        "from": "Cleveland",
        "to": "Chicago",
        "label": "Ohio/Indiana Turnpike and I-80/I-90 corridor",
        "why": "major toll and service-plaza-heavy Midwest freight corridor",
    },
    {
        "from": "New York",
        "to": "Boston",
        "label": "I-95 / New England toll corridor",
        "why": "extends Northeast toll and service-plaza realism beyond the current NY-Philadelphia batch",
    },
    {
        "from": "Philadelphia",
        "to": "Baltimore",
        "label": "I-95 Northeast Corridor south of Philadelphia",
        "why": "connects the current NJ/Philadelphia lane to the broader Northeast freight network",
    },
    {
        "from": "Pittsburgh",
        "to": "Cleveland",
        "label": "PA/Ohio Turnpike connector corridor",
        "why": "ties the PA Turnpike batch into the Ohio Turnpike network",
    },
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect or smoke-check offline corridor metadata."
    )
    parser.add_argument("--from-city", default="Chicago")
    parser.add_argument("--to-city", default="Indianapolis")
    parser.add_argument("--live-smoke", action="store_true",
                        help="Make tiny no-key OSRM and elevation requests.")
    parser.add_argument("--ors-smoke", action="store_true",
                        help="Make a tiny OpenRouteService driving-hgv (truck) "
                             f"request for the corridor. Requires the "
                             f"{ORS_API_KEY_ENV} environment variable (a free "
                             "OpenRouteService key, build-time only).")
    parser.add_argument("--coverage-report", action="store_true",
                        help="Report metadata coverage for every world leg.")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable JSON with --coverage-report.")
    parser.add_argument("--overpass-poi-smoke", action="store_true",
                        help="Make one tiny Overpass POI query near the corridor.")
    parser.add_argument("--enrich-all", action="store_true",
                        help="Enrich missing world legs from cached/no-key sources.")
    parser.add_argument("--write", action="store_true",
                        help="Write enriched metadata back to world.json.")
    parser.add_argument("--cache-dir", default=str(CACHE_PATH),
                        help="Directory for resumable live API response cache.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Maximum number of legs to enrich in this run.")
    parser.add_argument("--rate-limit", type=float, default=1.0,
                        help="Seconds to wait after uncached live API requests.")
    parser.add_argument("--no-overpass", action="store_true",
                        help="Skip live Overpass POI discovery during enrichment.")
    args = parser.parse_args(argv)

    data = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    if args.enrich_all:
        result = enrich_all_routes(
            data,
            cache_dir=Path(args.cache_dir),
            limit=args.limit or None,
            write=args.write,
            rate_limit_s=args.rate_limit,
            use_overpass=not args.no_overpass,
        )
        if args.write:
            WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True) if args.json
              else format_enrichment_result(result))
        return 0
    if args.coverage_report:
        report = coverage_report(data)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(format_coverage_report(report))
        return 0

    leg = _find_leg(data, args.from_city, args.to_city)
    if leg is None:
        raise SystemExit(f"No direct world leg {args.from_city} to {args.to_city}")

    corridor = leg.get("corridor", {})
    print(_offline_summary(leg, corridor))
    if args.live_smoke:
        result = _osrm_smoke(data, args.from_city, args.to_city)
        print(
            "OSRM live smoke: "
            f"{result['miles']:.1f} miles, "
            f"{result['points']} geometry points, "
            f"code {result['code']}"
        )
        elevation = _open_meteo_elevation_smoke(corridor)
        print(
            "Open-Meteo elevation smoke: "
            f"{elevation['samples']} samples, "
            f"{elevation['min_ft']:.0f}-{elevation['max_ft']:.0f} feet"
        )
    if args.ors_smoke:
        api_key = ors_api_key()
        if api_key is None:
            raise SystemExit(
                f"ORS smoke needs the {ORS_API_KEY_ENV} environment variable "
                "(a free OpenRouteService key). It is build-time only and is "
                "never bundled or read at runtime."
            )
        ors = _ors_smoke(data, args.from_city, args.to_city, api_key)
        print(
            "OpenRouteService HGV smoke: "
            f"{ors['miles']:.1f} miles, "
            f"{ors['points']} geometry points, "
            f"elevation {ors['min_ft']:.0f}-{ors['max_ft']:.0f} feet, "
            f"{ors['steepness_segments']} steepness segments, "
            f"tollway {'yes' if ors['has_tollway'] else 'no'}"
        )
    if args.overpass_poi_smoke:
        pois = _overpass_poi_smoke(corridor)
        print(
            "Overpass POI smoke: "
            f"{pois['elements']} elements in corridor bounding box, "
            f"{pois['actionable_candidates']} actionable candidates"
        )
    return 0


def enrich_all_routes(
    data: dict[str, Any],
    *,
    cache_dir: Path,
    limit: int | None,
    write: bool,
    rate_limit_s: float,
    use_overpass: bool,
) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    state_shapes = _load_state_shapes(cache_dir, rate_limit_s)
    processed = enriched = skipped = 0
    blockers: list[dict[str, Any]] = []
    for leg in data["legs"]:
        if limit is not None and processed >= limit:
            break
        corridor = leg.setdefault("corridor", {})
        needs = _leg_missing_fields(data, leg)
        if not needs:
            skipped += 1
            continue
        processed += 1
        try:
            route = _cached_osrm_route(data, leg, cache_dir, rate_limit_s)
            geometry = route["geometry"]["coordinates"]
            samples = _sample_geometry(geometry, float(leg["miles"]))
            elevations = _cached_elevations(samples, cache_dir, rate_limit_s)
            if "route_points" in needs:
                corridor["route_points"] = [
                    {"at_mi": round(point["at_mi"], 1),
                     "lat": round(point["lat"], 5),
                     "lon": round(point["lon"], 5)}
                    for point in samples
                ]
            if "elevation_samples" in needs:
                corridor["elevation_samples"] = [
                    {
                        "at_mi": round(point["at_mi"], 1),
                        "elevation_ft": round(elevation, 1),
                        "source": ELEVATION_SOURCE,
                    }
                    for point, elevation in zip(samples, elevations, strict=True)
                ]
            if "grade_segments" in needs:
                corridor["grade_segments"] = _grade_segments(samples, elevations, leg)
            if "checkpoints" in needs:
                corridor["checkpoints"] = _checkpoints(data, leg, samples)
            if "state_miles" in needs or "state_crossings" in needs:
                state_context = _state_context(data, leg, geometry, state_shapes)
                corridor["state_miles"] = state_context["state_miles"]
                if state_context["state_crossings"]:
                    corridor["state_crossings"] = state_context["state_crossings"]
                elif "state_crossings" in corridor:
                    corridor.pop("state_crossings")
            if not corridor.get("source"):
                corridor["source"] = CORRIDOR_SOURCE
            if "pois" in needs and use_overpass:
                stop = _discover_poi(data, leg, samples, cache_dir, rate_limit_s)
                if stop is not None:
                    leg["stops"] = [stop]
            if "pois" in _leg_missing_fields(data, leg):
                blockers.append({
                    "from": leg["from"],
                    "to": leg["to"],
                    "reason": "No actionable Overpass POI candidate found in sampled corridor searches.",
                    "next_action": (
                        "Run with --enrich-all --write after checking DOT/operator "
                        "sources or increasing Overpass search radius for this leg."
                    ),
                })
            else:
                enriched += 1
        except Exception as exc:  # noqa: BLE001 - batch report should keep moving.
            blockers.append({
                "from": leg["from"],
                "to": leg["to"],
                "reason": str(exc),
                "next_action": "Retry this leg after checking cache/API availability.",
            })
    report = coverage_report(data)
    return {
        "write": write,
        "processed": processed,
        "enriched_or_completed": enriched,
        "skipped_complete": skipped,
        "blockers": blockers,
        "coverage_totals": report["totals"],
    }


def format_enrichment_result(result: dict[str, Any]) -> str:
    totals = result["coverage_totals"]
    lines = [
        "Freight Fate route enrichment batch",
        f"Processed legs: {result['processed']}",
        f"Already complete: {result['skipped_complete']}",
        f"Completed in this view: {result['enriched_or_completed']}",
        f"Final playable metadata-backed legs: {totals['playable']}/{totals['legs']}",
        f"POIs with actions: {totals['pois_with_actions']}/{totals['legs']}",
        f"Expected crossings represented: "
        f"{totals['state_crossings_expected_present']}/"
        f"{totals['state_crossings_expected']}",
    ]
    if result["blockers"]:
        lines.append("Blockers:")
        for blocker in result["blockers"]:
            lines.append(
                f"- {blocker['from']} to {blocker['to']}: {blocker['reason']} "
                f"Next: {blocker['next_action']}"
            )
    return "\n".join(lines)


def _leg_missing_fields(data: dict[str, Any], leg: dict[str, Any]) -> list[str]:
    report = coverage_report({"cities": data["cities"], "legs": [leg]})
    return report["legs"][0]["missing"]


def _cached_osrm_route(
    data: dict[str, Any],
    leg: dict[str, Any],
    cache_dir: Path,
    rate_limit_s: float,
) -> dict[str, Any]:
    cities = data["cities"]
    start = cities[leg["from"]]
    end = cities[leg["to"]]
    coords = f"{start['lon']},{start['lat']};{end['lon']},{end['lat']}"
    params = {
        "overview": "simplified",
        "geometries": "geojson",
        "alternatives": "false",
        "steps": "false",
    }
    payload = _cached_json(
        cache_dir,
        "osrm",
        f"{leg['from']}--{leg['to']}--{leg['highway']}",
        OSRM_ROUTE_URL.format(coords=coords) + "?" + urllib.parse.urlencode(params),
        rate_limit_s=rate_limit_s,
    )
    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise RuntimeError(f"OSRM did not return a route: {payload.get('code')}")
    return payload["routes"][0]


def _cached_elevations(
    samples: list[dict[str, float]],
    cache_dir: Path,
    rate_limit_s: float,
) -> list[float]:
    params = urllib.parse.urlencode({
        "latitude": ",".join(str(point["lat"]) for point in samples),
        "longitude": ",".join(str(point["lon"]) for point in samples),
    })
    payload = _cached_json(
        cache_dir,
        "elevation",
        _hash_key(params),
        OPEN_METEO_ELEVATION_URL + "?" + params,
        rate_limit_s=rate_limit_s,
    )
    elevations_m = payload["elevation"]
    return [float(value) * 3.28084 for value in elevations_m]


def _discover_poi(
    data: dict[str, Any],
    leg: dict[str, Any],
    samples: list[dict[str, float]],
    cache_dir: Path,
    rate_limit_s: float,
) -> dict[str, Any] | None:
    candidate_points = [samples[len(samples) // 2]]
    if len(samples) >= 4:
        candidate_points.extend([samples[1], samples[-2]])
    for point in candidate_points:
        query = f"""
        [out:json][timeout:20];
        (
          node["amenity"="fuel"](
            around:5000,{point['lat']},{point['lon']});
          way["amenity"="fuel"](
            around:5000,{point['lat']},{point['lon']});
          node["highway"~"services|rest_area"](
            around:5000,{point['lat']},{point['lon']});
          way["highway"~"services|rest_area"](
            around:5000,{point['lat']},{point['lon']});
        );
        out tags center 12;
        """
        try:
            payload = _cached_overpass_json(
                cache_dir,
                f"{leg['from']}--{leg['to']}--{point['at_mi']:.1f}",
                urllib.parse.urlencode({"data": query}).encode("utf-8"),
                rate_limit_s=rate_limit_s,
            )
        except (TimeoutError, OSError):
            continue
        stop = _poi_from_overpass(data, leg, point, payload.get("elements", []))
        if stop is not None:
            return stop
    return None


def _poi_from_overpass(
    data: dict[str, Any],
    leg: dict[str, Any],
    point: dict[str, float],
    elements: list[dict[str, Any]],
) -> dict[str, Any] | None:
    ranked: list[tuple[int, dict[str, Any]]] = []
    for element in elements:
        tags = element.get("tags", {})
        if not tags:
            continue
        name = _clean_poi_name(tags.get("name") or tags.get("brand") or "")
        amenity = tags.get("amenity", "")
        highway = tags.get("highway", "")
        score = 0
        if name:
            score += 8
        if amenity == "fuel":
            score += 6
        if highway in {"services", "rest_area"}:
            score += 5
        if tags.get("hgv") in {"yes", "designated"} or "truck" in name.lower():
            score += 4
        if amenity == "parking":
            score += 2
        ranked.append((score, element))
    if not ranked:
        return None
    _score, element = max(ranked, key=lambda item: item[0])
    tags = element.get("tags", {})
    name = _clean_poi_name(tags.get("name") or tags.get("brand") or "")
    stop_type = _stop_type_from_tags(tags)
    if not name:
        highway = tags.get("highway")
        if highway == "rest_area":
            name = f"{leg['highway']} corridor rest area"
        elif stop_type in {"truck_parking", "public_rest_area"}:
            name = f"{leg['highway']} corridor truck parking"
        else:
            name = f"{leg['highway']} corridor fuel stop"
    services = _services_for_stop_type(stop_type)
    actions = _actions_for_stop_type(stop_type)
    return {
        "name": name,
        "type": stop_type,
        "at_mi": round(max(1.0, min(float(leg["miles"]) - 1.0, point["at_mi"])), 1),
        "source": (
            "OpenStreetMap/Overpass development-time corridor amenity query, "
            f"accessed 2026-06-16 near {leg['from']} to {leg['to']} via "
            f"{leg['highway']}; curated into gameplay POI without raw OSM IDs."
        ),
        "actions": actions,
        "services": services,
    }


def _stop_type_from_tags(tags: dict[str, str]) -> str:
    amenity = tags.get("amenity", "")
    highway = tags.get("highway", "")
    name = (tags.get("name") or tags.get("brand") or "").lower()
    if highway == "services":
        return "service_plaza"
    if highway == "rest_area":
        return "public_rest_area"
    if amenity == "parking":
        return "truck_parking"
    if "truck" in name or "travel" in name:
        return "travel_center"
    if amenity == "fuel":
        return "fuel_station"
    return "travel_center"


def _services_for_stop_type(stop_type: str) -> list[str]:
    return {
        "truck_stop": ["diesel", "food", "parking"],
        "travel_center": ["diesel", "food", "parking"],
        "fuel_station": ["diesel", "parking"],
        "service_plaza": ["diesel", "food", "parking"],
        "public_rest_area": ["parking", "restrooms"],
        "truck_parking": ["parking"],
        "weigh_station": ["inspection"],
        "repair_shop": ["repair", "parking"],
    }[stop_type]


def _actions_for_stop_type(stop_type: str) -> list[str]:
    return {
        "truck_stop": ["park", "save", "fuel", "food", "break", "sleep"],
        "travel_center": ["park", "save", "fuel", "food", "break", "sleep"],
        "fuel_station": ["park", "save", "fuel", "break"],
        "service_plaza": ["park", "save", "fuel", "food", "break"],
        "public_rest_area": ["park", "save", "break", "sleep"],
        "truck_parking": ["park", "save", "break", "sleep"],
        "weigh_station": ["inspect"],
        "repair_shop": ["park", "save", "repair"],
    }[stop_type]


def _clean_poi_name(value: str) -> str:
    name = " ".join(str(value).replace("\n", " ").split()).strip()
    lowered = name.lower()
    raw_markers = ("osm", "amenity=", "highway=", "node/", "way/", "relation/")
    if any(marker in lowered for marker in raw_markers):
        return ""
    return name[:80]


def _sample_geometry(
    geometry: list[list[float]],
    leg_miles: float,
    sample_count: int = 5,
) -> list[dict[str, float]]:
    if len(geometry) < 2:
        raise RuntimeError("OSRM route geometry has fewer than two points")
    distances = [0.0]
    for prev, cur in zip(geometry, geometry[1:], strict=False):
        distances.append(distances[-1] + _haversine_miles(prev[1], prev[0], cur[1], cur[0]))
    total = distances[-1] or 1.0
    desired = [leg_miles * i / (sample_count - 1) for i in range(sample_count)]
    samples = []
    for at_mi in desired:
        target = total * at_mi / leg_miles if leg_miles else 0.0
        index = next(
            (i for i, dist in enumerate(distances) if dist >= target),
            len(distances) - 1,
        )
        lon, lat = geometry[index]
        samples.append({"at_mi": at_mi, "lat": float(lat), "lon": float(lon)})
    samples[0]["at_mi"] = 0.0
    samples[-1]["at_mi"] = leg_miles
    return samples


def _grade_segments(
    samples: list[dict[str, float]],
    elevations_ft: list[float],
    leg: dict[str, Any],
) -> list[dict[str, Any]]:
    grades = []
    for start, end, elev_start, elev_end in zip(
        samples, samples[1:], elevations_ft, elevations_ft[1:], strict=False
    ):
        miles = max(0.1, end["at_mi"] - start["at_mi"])
        grade = (elev_end - elev_start) / (miles * 5280.0) * 100.0
        grades.append(grade)
    avg = sum(grades) / len(grades)
    max_abs = max(abs(grade) for grade in grades)
    terrain = str(leg.get("terrain", "flat"))
    if max_abs > 3.0:
        terrain = "mountain"
    elif max_abs > 0.8 and terrain == "flat":
        terrain = "hills"
    return [{
        "start_mi": 0.0,
        "end_mi": float(leg["miles"]),
        "avg_grade_pct": round(avg, 2),
        "terrain": terrain,
        "source": "Open-Meteo elevation samples summarized for corridor terrain.",
    }]


def _checkpoints(
    data: dict[str, Any],
    leg: dict[str, Any],
    samples: list[dict[str, float]],
) -> list[dict[str, Any]]:
    cities = data["cities"]
    mid = samples[len(samples) // 2]
    return [{
        "name": f"{leg['highway']} corridor between {leg['from']} and {leg['to']}",
        "at_mi": round(max(1.0, min(float(leg["miles"]) - 1.0, mid["at_mi"])), 1),
        "type": "place",
        "state": cities[leg["to"]]["state"],
        "highway": leg["highway"],
        "source": "Curated OSRM/OpenStreetMap corridor checkpoint.",
    }]


def _state_context(
    data: dict[str, Any],
    leg: dict[str, Any],
    geometry: list[list[float]],
    state_shapes: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    leg_miles = float(leg["miles"])
    endpoint_states = (data["cities"][leg["from"]]["state"],
                       data["cities"][leg["to"]]["state"])
    points = _state_points(geometry, leg_miles, state_shapes)
    if not points:
        points = [
            {"at_mi": 0.0, "state": endpoint_states[0]},
            {"at_mi": leg_miles, "state": endpoint_states[1]},
        ]
    points[0]["state"] = points[0].get("state") or endpoint_states[0]
    points[-1]["state"] = points[-1].get("state") or endpoint_states[1]
    sequence: list[dict[str, Any]] = []
    for point in points:
        state = point.get("state")
        if not state:
            continue
        if not sequence or sequence[-1]["state"] != state:
            sequence.append({"state": state, "at_mi": point["at_mi"]})
    if not sequence:
        sequence = [{"state": endpoint_states[0], "at_mi": 0.0}]
    if sequence[0]["at_mi"] != 0.0:
        sequence.insert(0, {"state": sequence[0]["state"], "at_mi": 0.0})
    if sequence[-1]["state"] != endpoint_states[1]:
        sequence.append({"state": endpoint_states[1], "at_mi": leg_miles})
    crossings = []
    for prev, cur in zip(sequence, sequence[1:], strict=False):
        if prev["state"] == cur["state"]:
            continue
        crossings.append({
            "at_mi": round(max(0.1, min(leg_miles - 0.1, cur["at_mi"])), 1),
            "from_state": prev["state"],
            "state": cur["state"],
            "place": f"{prev['state']}-{cur['state']} line on {leg['highway']}",
            "source": "Computed from OSRM route geometry and public U.S. state boundary GeoJSON.",
        })
    state_miles: list[dict[str, Any]] = []
    mileage: dict[str, float] = {}
    bounds = sequence + [{"state": sequence[-1]["state"], "at_mi": leg_miles}]
    for prev, cur in zip(bounds, bounds[1:], strict=False):
        miles = max(0.0, cur["at_mi"] - prev["at_mi"])
        mileage[prev["state"]] = mileage.get(prev["state"], 0.0) + miles
    if not mileage:
        mileage[endpoint_states[0]] = leg_miles
    for state, miles in mileage.items():
        if miles > 0:
            state_miles.append({"state": state, "miles": round(miles, 1)})
    total = sum(item["miles"] for item in state_miles)
    if state_miles and abs(total - leg_miles) >= 0.1:
        state_miles[-1]["miles"] = round(state_miles[-1]["miles"] + leg_miles - total, 1)
    return {"state_miles": state_miles, "state_crossings": crossings}


def _state_points(
    geometry: list[list[float]],
    leg_miles: float,
    state_shapes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    distances = [0.0]
    for prev, cur in zip(geometry, geometry[1:], strict=False):
        distances.append(distances[-1] + _haversine_miles(prev[1], prev[0], cur[1], cur[0]))
    total = distances[-1] or 1.0
    out = []
    for coord, raw_miles in zip(geometry, distances, strict=True):
        lon, lat = coord
        state = _state_for_point(float(lat), float(lon), state_shapes)
        out.append({"at_mi": raw_miles / total * leg_miles, "state": state})
    return out


def _load_state_shapes(cache_dir: Path, rate_limit_s: float) -> list[dict[str, Any]]:
    payload = _cached_json(
        cache_dir,
        "boundaries",
        "us-states-publicamundi",
        SIMPLE_STATES_GEOJSON_URL,
        rate_limit_s=rate_limit_s,
    )
    return payload.get("features", [])


def _state_for_point(lat: float, lon: float, features: list[dict[str, Any]]) -> str:
    for feature in features:
        geometry = feature.get("geometry", {})
        if _point_in_geometry(lat, lon, geometry):
            return str(feature.get("properties", {}).get("name", ""))
    return ""


def _point_in_geometry(lat: float, lon: float, geometry: dict[str, Any]) -> bool:
    geom_type = geometry.get("type")
    coordinates = geometry.get("coordinates", [])
    if geom_type == "Polygon":
        return any(_point_in_ring(lat, lon, ring) for ring in coordinates[:1])
    if geom_type == "MultiPolygon":
        return any(
            any(_point_in_ring(lat, lon, ring) for ring in polygon[:1])
            for polygon in coordinates
        )
    return False


def _point_in_ring(lat: float, lon: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i, point in enumerate(ring):
        xi, yi = point[0], point[1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _cached_json(
    cache_dir: Path,
    namespace: str,
    key: str,
    url: str,
    *,
    rate_limit_s: float,
) -> dict[str, Any]:
    path = _cache_file(cache_dir, namespace, key)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=OSRM_TIMEOUT_S + 20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if rate_limit_s > 0:
        time.sleep(rate_limit_s)
    return payload


def _cached_post_json(
    cache_dir: Path,
    namespace: str,
    key: str,
    url: str,
    body: bytes,
    *,
    rate_limit_s: float,
) -> dict[str, Any]:
    path = _cache_file(cache_dir, namespace, key)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=OSRM_TIMEOUT_S + 25) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if rate_limit_s > 0:
        time.sleep(rate_limit_s)
    return payload


def _cached_overpass_json(
    cache_dir: Path,
    key: str,
    body: bytes,
    *,
    rate_limit_s: float,
) -> dict[str, Any]:
    path = _cache_file(cache_dir, "overpass", key)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    last_error: Exception | None = None
    for url in OVERPASS_URLS:
        try:
            payload = _cached_post_json(
                cache_dir,
                "overpass",
                f"{key}--{_hash_key(url)}",
                url,
                body,
                rate_limit_s=rate_limit_s,
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2, sort_keys=True),
                            encoding="utf-8")
            return payload
        except (TimeoutError, urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise RuntimeError("No Overpass endpoint configured")


def _cache_file(cache_dir: Path, namespace: str, key: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in key)
    return cache_dir / namespace / f"{safe[:120]}.json"


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_mi = 3958.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_mi * math.atan2(a ** 0.5, (1 - a) ** 0.5)


def _find_leg(data: dict[str, Any], from_city: str, to_city: str) -> dict[str, Any] | None:
    for leg in data["legs"]:
        if leg["from"] == from_city and leg["to"] == to_city:
            return leg
    return None


def _offline_summary(leg: dict[str, Any], corridor: dict[str, Any]) -> str:
    crossings = corridor.get("state_crossings", [])
    points = corridor.get("route_points", [])
    checkpoints = corridor.get("checkpoints", [])
    elevations = corridor.get("elevation_samples", [])
    grade_segments = corridor.get("grade_segments", [])
    state_text = ", ".join(
        f"{item['from_state']} to {item['state']} at {item['at_mi']} mi"
        for item in crossings
    ) or "no explicit state crossings"
    terrain_text = (
        f"{len(elevations)} elevation samples, {len(grade_segments)} grade segments"
        if elevations or grade_segments else "no route-derived terrain"
    )
    return (
        f"Offline corridor {leg['from']} to {leg['to']}: "
        f"{leg['miles']} miles via {leg['highway']}; "
        f"{len(points)} route points, {len(checkpoints)} checkpoints, "
        f"{terrain_text}, {state_text}."
    )


def coverage_report(data: dict[str, Any]) -> dict[str, Any]:
    cities = data["cities"]
    legs = data["legs"]
    totals = {
        "legs": len(legs),
        "route_points": 0,
        "state_crossings": 0,
        "state_crossings_expected": 0,
        "state_crossings_expected_present": 0,
        "checkpoints": 0,
        "state_miles": 0,
        "elevation_samples": 0,
        "grade_segments": 0,
        "pois": 0,
        "pois_with_actions": 0,
        "curated_pois": 0,
        "placeholder_pois": 0,
        "legs_with_curated_pois": 0,
        "legs_with_placeholder_only": 0,
        "legs_with_sufficient_poi_density": 0,
        "legs_with_fuel_support": 0,
        "poi_density": 0,
        "fuel_poi_support": 0,
        "toll_events": 0,
        "toll_legs": 0,
        "playable": 0,
    }
    leg_reports = []
    for leg in legs:
        corridor = leg.get("corridor", {})
        stops = leg.get("stops", [])
        from_state = cities[leg["from"]]["state"]
        to_state = cities[leg["to"]]["state"]
        expected_crossing = from_state != to_state
        curated_stops = [
            stop for stop in stops
            if not _stop_is_placeholder(stop)
        ]
        placeholder_stops = [
            stop for stop in stops
            if _stop_is_placeholder(stop)
        ]
        min_pois = _minimum_curated_pois(float(leg["miles"]))
        min_fuel_pois = _minimum_fuel_capable_pois(float(leg["miles"]))
        curated_pois_complete = bool(curated_stops) and all(
            stop.get("source")
            and _stop_actions(stop)
            and _stop_parking(stop) != "unknown"
            and _stop_directions(stop)
            for stop in curated_stops
        )
        sufficient_density = len(curated_stops) >= min_pois
        sufficient_fuel_support = sum(
            1 for stop in curated_stops if "fuel" in _stop_actions(stop)
        ) >= min_fuel_pois
        present = {
            "route_points": len(corridor.get("route_points", [])) >= 2,
            "state_crossings": bool(corridor.get("state_crossings", [])),
            "checkpoints": bool(corridor.get("checkpoints", [])),
            "state_miles": bool(corridor.get("state_miles", [])),
            "elevation_samples": len(corridor.get("elevation_samples", [])) >= 2,
            "grade_segments": bool(corridor.get("grade_segments", [])),
            "pois": bool(stops),
            "pois_with_actions": curated_pois_complete,
            "curated_pois": curated_pois_complete,
            "poi_density": sufficient_density,
            "fuel_poi_support": sufficient_fuel_support,
        }
        missing = [
            field for field in REQUIRED_METADATA_FIELDS
            if not present[field]
        ]
        if expected_crossing and not present["state_crossings"]:
            missing.append("state_crossings")
        playable = not missing
        for field, ok in present.items():
            if ok:
                totals[field] += 1
        toll_events = corridor.get("toll_events", [])
        totals["toll_events"] += len(toll_events)
        totals["toll_legs"] += int(bool(toll_events))
        totals["curated_pois"] += len(curated_stops)
        totals["placeholder_pois"] += len(placeholder_stops)
        totals["legs_with_curated_pois"] += int(bool(curated_stops))
        totals["legs_with_placeholder_only"] += int(
            bool(placeholder_stops) and not curated_stops
        )
        totals["legs_with_sufficient_poi_density"] += int(sufficient_density)
        totals["legs_with_fuel_support"] += int(sufficient_fuel_support)
        totals["state_crossings_expected"] += int(expected_crossing)
        totals["state_crossings_expected_present"] += int(
            expected_crossing and present["state_crossings"]
        )
        totals["playable"] += int(playable)
        leg_reports.append({
            "from": leg["from"],
            "to": leg["to"],
            "highway": leg["highway"],
            "miles": leg["miles"],
            "endpoint_state_change": expected_crossing,
            "playable": playable,
            "present": present,
            "missing": missing,
            "unsupported_reasons": _unsupported_reasons(
                missing,
                curated_count=len(curated_stops),
                placeholder_count=len(placeholder_stops),
                minimum_curated_pois=min_pois,
                fuel_capable_count=sum(
                    1 for stop in curated_stops if "fuel" in _stop_actions(stop)
                ),
                minimum_fuel_capable_pois=min_fuel_pois,
            ),
            "poi_count": len(stops),
            "curated_poi_count": len(curated_stops),
            "placeholder_poi_count": len(placeholder_stops),
            "minimum_curated_pois": min_pois,
            "minimum_fuel_capable_pois": min_fuel_pois,
            "poi_actions": sorted({
                action for stop in curated_stops for action in _stop_actions(stop)
            }),
            "toll_event_count": len(toll_events),
        })
    percentages = {
        key: round(value / totals["legs"] * 100.0, 1)
        for key, value in totals.items()
        if key not in {
            "legs",
            "state_crossings_expected",
            "toll_events",
            "curated_pois",
            "placeholder_pois",
        }
    }
    if totals["state_crossings_expected"]:
        percentages["state_crossings_expected_present"] = round(
            totals["state_crossings_expected_present"]
            / totals["state_crossings_expected"] * 100.0,
            1,
        )
    return {
        "metadata_contract": {
            "playable_requires": list(REQUIRED_METADATA_FIELDS),
            "placeholder_pois_do_not_count_for_dispatch": True,
            "minimum_curated_pois_by_length": {
                "under_160_mi": 1,
                "160_to_320_mi": 2,
                "over_320_mi": 3,
            },
            "minimum_fuel_capable_pois_by_length": {
                "under_160_mi": 0,
                "160_mi_and_over": 1,
            },
            "state_crossings_required_when_endpoint_states_differ": True,
            "runtime_network_calls": False,
            "legacy_full_graph_available_for_old_saves": True,
        },
        "current_batch_notes": [
            "Full-network route geometry, elevation, state context, and "
            "source-backed truck-stop coverage are checked in for the current "
            "106-leg network. Placeholder POIs remain quarantined by the "
            "coverage contract and must not count for future dispatch lanes.",
        ],
        "high_priority_remaining_corridors": _priority_status(leg_reports),
        "totals": totals,
        "percentages": percentages,
        "legs": leg_reports,
        "missing_playable": [
            leg for leg in leg_reports if not leg["playable"]
        ],
    }


def format_coverage_report(report: dict[str, Any]) -> str:
    totals = report["totals"]
    pct = report["percentages"]
    lines = [
        "Freight Fate route metadata coverage",
        f"Total legs: {totals['legs']}",
        f"Playable metadata-backed legs: {totals['playable']} "
        f"({pct.get('playable', 0.0):.1f}%)",
        f"Route geometry: {totals['route_points']} "
        f"({pct.get('route_points', 0.0):.1f}%)",
        f"Elevation/grade: {totals['grade_segments']} "
        f"({pct.get('grade_segments', 0.0):.1f}%)",
        f"POIs with actions: {totals['pois_with_actions']} "
        f"({pct.get('pois_with_actions', 0.0):.1f}%)",
        f"Curated POIs: {totals['curated_pois']} on "
        f"{totals['legs_with_curated_pois']} legs; placeholder POIs: "
        f"{totals['placeholder_pois']} on "
        f"{totals['legs_with_placeholder_only']} placeholder-only legs",
        f"Sufficient curated stop density: "
        f"{totals['legs_with_sufficient_poi_density']} "
        f"({pct.get('legs_with_sufficient_poi_density', 0.0):.1f}%)",
        f"Fuel-capable curated support: "
        f"{totals['legs_with_fuel_support']} "
        f"({pct.get('legs_with_fuel_support', 0.0):.1f}%)",
        f"Toll metadata: {totals['toll_events']} events on "
        f"{totals['toll_legs']} legs "
        f"({pct.get('toll_legs', 0.0):.1f}% of legs)",
        f"Expected state crossings represented: "
        f"{totals['state_crossings_expected_present']}/"
        f"{totals['state_crossings_expected']} "
        f"({pct.get('state_crossings_expected_present', 0.0):.1f}%)",
        "",
        "Current toll-corridor note:",
        "- NJ Turnpike, PA Turnpike, Ohio Turnpike, Indiana Toll Road, "
        "New England, Delaware, and Maryland I-95 toll events are modeled as "
        "settlement charges where source-backed estimates are checked in.",
        "- Toll plazas and gantries are payment events; toll-road service plazas "
        "remain separate actionable POIs.",
        "",
        "High-priority remaining corridors:",
    ]
    for item in report["high_priority_remaining_corridors"]:
        status = "playable" if item["playable"] else "missing " + ", ".join(item["missing"])
        lines.append(f"- {item['label']}: {status}")
    lines += [
        "",
        "Incomplete legs:",
    ]
    for leg in report["missing_playable"][:25]:
        lines.append(
            f"- {leg['from']} to {leg['to']} via {leg['highway']}: "
            f"missing {', '.join(leg['missing'])}"
        )
    omitted = len(report["missing_playable"]) - 25
    if omitted > 0:
        lines.append(f"- ... {omitted} more incomplete legs")
    return "\n".join(lines)


def _stop_actions(stop: dict[str, Any]) -> tuple[str, ...]:
    default_actions = {
        "truck_stop": ("park", "save", "fuel", "food", "break", "sleep"),
        "travel_center": ("park", "save", "fuel", "food", "break", "sleep"),
        "fuel_station": ("park", "save", "fuel", "break"),
        "service_plaza": ("park", "save", "fuel", "food", "break"),
        "public_rest_area": ("park", "save", "break", "sleep"),
        "truck_parking": ("park", "save", "break", "sleep"),
        "weigh_station": ("inspect",),
        "repair_shop": ("park", "save", "repair"),
    }
    return tuple(stop.get("actions") or default_actions.get(stop.get("type"), ()))


def _stop_parking(stop: dict[str, Any]) -> str:
    parking = str(stop.get("parking", "")).strip()
    if parking:
        return parking
    if "parking" not in stop.get("services", ()) and "park" not in _stop_actions(stop):
        return "none"
    if stop.get("type") in {"truck_stop", "travel_center", "service_plaza"}:
        return "likely"
    if stop.get("type") in {"public_rest_area", "truck_parking"}:
        return "limited"
    return "unknown"


def _stop_directions(stop: dict[str, Any]) -> tuple[str, ...]:
    return tuple(stop.get("directions") or ("both",))


def _stop_is_placeholder(stop: dict[str, Any]) -> bool:
    if stop.get("curation") == "placeholder":
        return True
    text = f"{stop.get('name', '')} {stop.get('source', '')}".lower()
    markers = (
        "corridor rest area",
        "corridor truck parking",
        "corridor fuel stop",
        "descriptive gameplay stop seeded",
        "seeded for offline route coverage",
    )
    return any(marker in text for marker in markers)


def _minimum_curated_pois(miles: float) -> int:
    if miles < 160.0:
        return 1
    if miles <= 320.0:
        return 2
    return 3


def _minimum_fuel_capable_pois(miles: float) -> int:
    if miles < 160.0:
        return 0
    return 1


def _unsupported_reasons(
    missing: list[str],
    *,
    curated_count: int,
    placeholder_count: int,
    minimum_curated_pois: int,
    fuel_capable_count: int,
    minimum_fuel_capable_pois: int,
) -> list[str]:
    if not missing:
        return []
    reasons = []
    if "curated_pois" in missing and placeholder_count and not curated_count:
        reasons.append("placeholder-only POIs are quarantined and do not count")
    elif "curated_pois" in missing:
        reasons.append(
            "curated POIs are missing required source, actions, directions, or parking certainty"
        )
    if "poi_density" in missing:
        reasons.append(
            f"insufficient curated POI density: {curated_count}/{minimum_curated_pois}"
        )
    if "fuel_poi_support" in missing:
        reasons.append(
            "insufficient fuel-capable curated support: "
            f"{fuel_capable_count}/{minimum_fuel_capable_pois}"
        )
    for field in missing:
        if field in {"curated_pois", "poi_density", "fuel_poi_support"}:
            continue
        reasons.append(f"missing {field}")
    return reasons


def _priority_status(leg_reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for priority in HIGH_PRIORITY_REMAINING_CORRIDORS:
        leg = next(
            (
                item for item in leg_reports
                if item["from"] == priority["from"] and item["to"] == priority["to"]
            ),
            None,
        )
        out.append({
            **priority,
            "playable": bool(leg and leg["playable"]),
            "missing": [] if leg is None else leg["missing"],
        })
    return out


def _osrm_smoke(data: dict[str, Any], from_city: str, to_city: str) -> dict[str, Any]:
    cities = data["cities"]
    start = cities[from_city]
    end = cities[to_city]
    coords = f"{start['lon']},{start['lat']};{end['lon']},{end['lat']}"
    params = urllib.parse.urlencode({
        "overview": "simplified",
        "geometries": "geojson",
        "alternatives": "false",
        "steps": "false",
    })
    url = OSRM_ROUTE_URL.format(coords=coords) + "?" + params
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=OSRM_TIMEOUT_S) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    route = payload["routes"][0]
    return {
        "code": payload.get("code", "unknown"),
        "miles": float(route["distance"]) / 1609.344,
        "points": len(route.get("geometry", {}).get("coordinates", [])),
    }


def ors_api_key() -> str | None:
    """The OpenRouteService key from the environment, or None when unset.

    Build-time only: the key is read here in the tooling and is never bundled
    with the game or read at runtime.
    """
    key = os.environ.get(ORS_API_KEY_ENV, "").strip()
    return key or None


def _ors_request_body(start: dict[str, Any], end: dict[str, Any]) -> bytes:
    body = {
        "coordinates": [
            [float(start["lon"]), float(start["lat"])],
            [float(end["lon"]), float(end["lat"])],
        ],
        "elevation": True,
        "extra_info": list(ORS_EXTRA_INFO),
    }
    return json.dumps(body).encode("utf-8")


def fetch_ors_hgv_route(
    start: dict[str, Any],
    end: dict[str, Any],
    api_key: str,
    *,
    timeout_s: float = OSRM_TIMEOUT_S + 15,
) -> dict[str, Any]:
    """Live OpenRouteService driving-hgv request returning the raw GeoJSON.

    Build-time only. Kept separate from :func:`parse_ors_route` so the mapping
    can be unit-tested against a captured response without any network.
    """
    url = ORS_DIRECTIONS_URL.format(profile=ORS_HGV_PROFILE)
    req = urllib.request.Request(
        url,
        data=_ors_request_body(start, end),
        headers={
            "User-Agent": USER_AGENT,
            "Authorization": api_key,
            "Content-Type": "application/json",
            "Accept": "application/geo+json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_ors_route(payload: dict[str, Any]) -> dict[str, Any]:
    """Map an ORS driving-hgv GeoJSON response onto corridor-ready fields.

    Pure (no network) so it is unit-testable against a captured response.
    Returns the summary distance in miles, 2D ``[lon, lat]`` coordinates (the
    shape :func:`_sample_geometry` consumes), per-vertex elevation in feet
    (ORS returns 3D coordinates when ``elevation`` is requested, so no separate
    Open-Meteo elevation call is needed), the steepness extra-info segments, and
    whether the route touches any tollway.
    """
    features = payload.get("features") or []
    if not features:
        raise RuntimeError("ORS response has no route features")
    feature = features[0]
    coords3d = feature.get("geometry", {}).get("coordinates", [])
    if len(coords3d) < 2:
        raise RuntimeError("ORS route geometry has fewer than two points")
    coordinates = [[float(point[0]), float(point[1])] for point in coords3d]
    elevations_ft = [
        float(point[2]) * 3.28084 if len(point) > 2 else 0.0
        for point in coords3d
    ]
    props = feature.get("properties", {})
    distance_m = float(props.get("summary", {}).get("distance", 0.0))
    extras = props.get("extras", {})
    steepness = extras.get("steepness", {}).get("values", [])
    tollways = extras.get("tollways", {}).get("values", [])
    has_tollway = any(len(value) >= 3 and value[2] for value in tollways)
    return {
        "miles": distance_m / 1609.344,
        "coordinates": coordinates,
        "elevations_ft": elevations_ft,
        "steepness": steepness,
        "has_tollway": has_tollway,
    }


def _ors_smoke(
    data: dict[str, Any],
    from_city: str,
    to_city: str,
    api_key: str,
) -> dict[str, Any]:
    cities = data["cities"]
    payload = fetch_ors_hgv_route(cities[from_city], cities[to_city], api_key)
    parsed = parse_ors_route(payload)
    elevations = parsed["elevations_ft"]
    return {
        "miles": parsed["miles"],
        "points": len(parsed["coordinates"]),
        "min_ft": min(elevations) if elevations else 0.0,
        "max_ft": max(elevations) if elevations else 0.0,
        "steepness_segments": len(parsed["steepness"]),
        "has_tollway": parsed["has_tollway"],
    }


def _open_meteo_elevation_smoke(corridor: dict[str, Any]) -> dict[str, Any]:
    points = corridor.get("route_points", [])
    if not points:
        raise SystemExit("No route_points available for elevation smoke.")
    # Use a tiny subset: endpoints and one middle point if available.
    selected = [points[0]]
    if len(points) > 2:
        selected.append(points[len(points) // 2])
    if len(points) > 1:
        selected.append(points[-1])
    params = urllib.parse.urlencode({
        "latitude": ",".join(str(point["lat"]) for point in selected),
        "longitude": ",".join(str(point["lon"]) for point in selected),
    })
    req = urllib.request.Request(
        OPEN_METEO_ELEVATION_URL + "?" + params,
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=OSRM_TIMEOUT_S) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    elevations_m = payload["elevation"]
    elevations_ft = [float(value) * 3.28084 for value in elevations_m]
    return {
        "samples": len(elevations_ft),
        "min_ft": min(elevations_ft),
        "max_ft": max(elevations_ft),
    }


def _overpass_poi_smoke(corridor: dict[str, Any]) -> dict[str, Any]:
    points = corridor.get("route_points", [])
    if not points:
        raise SystemExit("No route_points available for Overpass smoke.")
    lats = [float(point["lat"]) for point in points]
    lons = [float(point["lon"]) for point in points]
    south, north = min(lats) - 0.05, max(lats) + 0.05
    west, east = min(lons) - 0.05, max(lons) + 0.05
    query = f"""
    [out:json][timeout:12];
    (
      node["amenity"~"fuel|parking|restaurant"]({south},{west},{north},{east});
      node["highway"="rest_area"]({south},{west},{north},{east});
      node["highway"="services"]({south},{west},{north},{east});
    );
    out tags center 20;
    """
    payload = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(
        OVERPASS_URL,
        data=payload,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=OSRM_TIMEOUT_S + 8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elements = data.get("elements", [])
    actionable = [
        element for element in elements
        if any(key in element.get("tags", {}) for key in ("amenity", "highway"))
    ]
    return {"elements": len(elements), "actionable_candidates": len(actionable)}


if __name__ == "__main__":
    sys.exit(main())
