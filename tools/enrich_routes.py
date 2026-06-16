"""Build-time route enrichment helpers for corridor metadata.

Runtime gameplay stays offline. This tool either reads checked-in world data or
performs tiny live OSRM/Open-Meteo smoke checks for one representative corridor.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORLD_PATH = ROOT / "src" / "freight_fate" / "data" / "world.json"
USER_AGENT = "Freight-Fate route-enrichment smoke (https://github.com/Orinks/Freight-Fate)"
OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving/{coords}"
OPEN_METEO_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSRM_TIMEOUT_S = 12
REQUIRED_METADATA_FIELDS = (
    "route_points",
    "checkpoints",
    "state_miles",
    "elevation_samples",
    "grade_segments",
    "pois",
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
    parser.add_argument("--coverage-report", action="store_true",
                        help="Report metadata coverage for every world leg.")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable JSON with --coverage-report.")
    parser.add_argument("--overpass-poi-smoke", action="store_true",
                        help="Make one tiny Overpass POI query near the corridor.")
    args = parser.parse_args(argv)

    data = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
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
    if args.overpass_poi_smoke:
        pois = _overpass_poi_smoke(corridor)
        print(
            "Overpass POI smoke: "
            f"{pois['elements']} elements in corridor bounding box, "
            f"{pois['actionable_candidates']} actionable candidates"
        )
    return 0


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
        "playable": 0,
    }
    leg_reports = []
    for leg in legs:
        corridor = leg.get("corridor", {})
        stops = leg.get("stops", [])
        from_state = cities[leg["from"]]["state"]
        to_state = cities[leg["to"]]["state"]
        expected_crossing = from_state != to_state
        present = {
            "route_points": len(corridor.get("route_points", [])) >= 2,
            "state_crossings": bool(corridor.get("state_crossings", [])),
            "checkpoints": bool(corridor.get("checkpoints", [])),
            "state_miles": bool(corridor.get("state_miles", [])),
            "elevation_samples": len(corridor.get("elevation_samples", [])) >= 2,
            "grade_segments": bool(corridor.get("grade_segments", [])),
            "pois": bool(stops),
            "pois_with_actions": bool(stops) and all(
                stop.get("source") and _stop_actions(stop) for stop in stops
            ),
        }
        missing = [
            field for field in REQUIRED_METADATA_FIELDS
            if not present["pois_with_actions" if field == "pois" else field]
        ]
        if expected_crossing and not present["state_crossings"]:
            missing.append("state_crossings")
        playable = not missing
        for field, ok in present.items():
            if ok:
                totals[field] += 1
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
            "poi_count": len(stops),
            "poi_actions": sorted({action for stop in stops for action in _stop_actions(stop)}),
        })
    percentages = {
        key: round(value / totals["legs"] * 100.0, 1)
        for key, value in totals.items()
        if key not in {"legs", "state_crossings_expected"}
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
            "state_crossings_required_when_endpoint_states_differ": True,
            "runtime_network_calls": False,
            "legacy_full_graph_available_for_old_saves": True,
        },
        "current_batch_notes": [
            "New York to Philadelphia includes source-backed NJ Turnpike-style "
            "service plaza POIs. PA Turnpike and Ohio/Indiana Turnpike "
            "corridors are not yet playable metadata-backed lanes.",
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
        f"Expected state crossings represented: "
        f"{totals['state_crossings_expected_present']}/"
        f"{totals['state_crossings_expected']} "
        f"({pct.get('state_crossings_expected_present', 0.0):.1f}%)",
        "",
        "Current toll-corridor note:",
        "- New York to Philadelphia has NJ Turnpike-style service plaza POIs.",
        "- PA Turnpike and Ohio/Indiana Turnpike corridors are not complete yet.",
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
