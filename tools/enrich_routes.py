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
OSRM_TIMEOUT_S = 12


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect or smoke-check offline corridor metadata."
    )
    parser.add_argument("--from-city", default="Chicago")
    parser.add_argument("--to-city", default="Indianapolis")
    parser.add_argument("--live-smoke", action="store_true",
                        help="Make tiny no-key OSRM and elevation requests.")
    args = parser.parse_args(argv)

    data = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
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


if __name__ == "__main__":
    sys.exit(main())
