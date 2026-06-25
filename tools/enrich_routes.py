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
import re
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
# OpenRouteService heavy-goods (truck) routing via the official `openrouteservice`
# SDK. Build-time only (the `tooling` dependency group); the key lives in the
# environment and is never bundled or read at runtime. One driving-hgv request
# returns truck-legal geometry with elevation plus steepness and tollway extras
# -- the inputs the corridor builders already consume.
ORS_HGV_PROFILE = "driving-hgv"
ORS_API_KEY_ENV = "ORS_API_KEY"
ORS_EXTRA_INFO = ("steepness", "tollways", "waytype")
# HeiGIT now serves the API at api.heigit.org; the SDK still defaults to the
# deprecated api.openrouteservice.org, so point it at the current host. The full
# endpoint becomes {base}/v2/directions/{profile}. Override with ORS_BASE_URL.
ORS_DEFAULT_BASE_URL = "https://api.heigit.org/openrouteservice"
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
# Dispatch gates on routing completeness only. Curated POIs are an additive
# quality layer (auto-sourced; reported via the non-blocking POI advisory), not a
# dispatch requirement -- the runtime HOS fallbacks keep a stop-less leg playable.
REQUIRED_METADATA_FIELDS = (
    "route_points",
    "checkpoints",
    "state_miles",
    "elevation_samples",
    "grade_segments",
)
# A long leg with no fuel-capable curated stop leans on the roadside-fuel
# fallback; flag it for optional curation without blocking dispatch.
LONG_LEG_POI_ADVISORY_MI = 250.0
ELEVATION_SOURCE = (
    "Open-Meteo Elevation API development-time sample from Copernicus DEM GLO-90."
)
CORRIDOR_SOURCE = (
    "Development-time OSRM route geometry over OpenStreetMap, with Open-Meteo "
    "elevation samples, Census/OpenStreetMap state context, and curated "
    "corridor POIs checked in for offline runtime use."
)
ORS_ELEVATION_SOURCE = (
    "OpenRouteService driving-hgv route elevation over OpenStreetMap "
    "(SRTM/elevation), sampled at development time."
)
ORS_CORRIDOR_SOURCE = (
    "Development-time OpenRouteService driving-hgv (truck) route geometry and "
    "elevation over OpenStreetMap, with Census/OpenStreetMap state context and "
    "curated corridor POIs checked in for offline runtime use."
)
ORS_GRADE_SOURCE = (
    "OpenRouteService route elevation profile segmented by terrain "
    "(development-time)."
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
    parser.add_argument("--ors-compare", action="store_true",
                        help="Read-only: compare the ORS driving-hgv corridor "
                             "for --from-city/--to-city against the checked-in "
                             f"data. Requires {ORS_API_KEY_ENV}.")
    parser.add_argument("--engine", choices=("osrm", "ors"), default="osrm",
                        help="Routing engine for --enrich-all. 'ors' uses the "
                             "driving-hgv truck profile (needs ORS_API_KEY and "
                             "the tooling group); 'osrm' (default) is car.")
    parser.add_argument("--refresh-geometry", action="store_true",
                        help="Re-derive route_points, elevation_samples, and "
                             "grade_segments for selected legs from --engine, "
                             "preserving curated miles, POIs, tolls, and named "
                             "crossings/checkpoints. Use with --only and --write.")
    parser.add_argument("--only", default="",
                        help="Semicolon-separated 'From:To' legs for "
                             "--refresh-geometry / --adopt-ors-miles, e.g. "
                             "'Denver:Salt Lake City;Philadelphia:Pittsburgh'. "
                             "Semicolons (not commas) so comma-bearing city "
                             "names like 'Charleston, West Virginia' parse.")
    parser.add_argument("--adopt-ors-miles", action="store_true",
                        help="Rewrite leg mileage to the real ORS driving-hgv "
                             "distance (rescaling corridor positions). Drives "
                             "pay/deadlines. Needs ORS_API_KEY + tooling group; "
                             "use with --write (and optionally --only).")
    parser.add_argument("--add-overpass-pois", action="store_true",
                        help="Additively enrich legs with named OpenStreetMap "
                             "truck POIs of any brand (Overpass). Use with "
                             "--write, --per-leg, and optionally --only.")
    parser.add_argument("--per-leg", type=int, default=2,
                        help="Max new POIs per leg for --add-overpass-pois.")
    parser.add_argument("--add-maxspeed", action="store_true",
                        help="Bake real OpenStreetMap maxspeed onto legs as a "
                             "speed_limits profile (Overpass). The runtime "
                             "prefers it over the highway/region heuristic. Use "
                             "with --write and optionally --only.")
    parser.add_argument("--prune-non-truck-pois", action="store_true",
                        help="Remove auto-discovered non-truck POIs (generic car "
                             "fuel) network-wide, keeping curated stops and "
                             "truck-relevant ones. Use with --write.")
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
        api_key = None
        if args.engine == "ors":
            api_key = ors_api_key()
            if api_key is None:
                raise SystemExit(
                    f"--engine ors needs the {ORS_API_KEY_ENV} environment "
                    "variable and the tooling group "
                    "(uv run --group tooling ...)."
                )
        result = enrich_all_routes(
            data,
            cache_dir=Path(args.cache_dir),
            limit=args.limit or None,
            write=args.write,
            rate_limit_s=args.rate_limit,
            use_overpass=not args.no_overpass,
            engine=args.engine,
            api_key=api_key,
        )
        if args.write:
            WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True) if args.json
              else format_enrichment_result(result))
        return 0
    if args.adopt_ors_miles:
        api_key = ors_api_key()
        if api_key is None:
            raise SystemExit(
                f"--adopt-ors-miles needs the {ORS_API_KEY_ENV} environment "
                "variable and the tooling group (uv run --group tooling ...)."
            )
        result = adopt_ors_miles(
            data,
            cache_dir=Path(args.cache_dir),
            rate_limit_s=args.rate_limit,
            api_key=api_key,
            only=_parse_only(args.only),
        )
        if args.write:
            WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            totals = result["coverage_totals"]
            print(f"Adopted ORS miles for {len(result['changed'])} leg(s); "
                  f"playable {totals['playable']}/{totals['legs']}"
                  f"{' (written)' if args.write else ' (dry run)'}")
        return 0
    if args.add_overpass_pois:
        result = add_overpass_pois(
            data,
            cache_dir=Path(args.cache_dir),
            rate_limit_s=args.rate_limit,
            only=_parse_only(args.only),
            per_leg=args.per_leg,
        )
        if args.write:
            WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            totals = result["coverage_totals"]
            print(f"Added {result['added_pois']} OSM POIs to "
                  f"{result['updated_legs']} legs; playable "
                  f"{totals['playable']}/{totals['legs']}; "
                  f"{len(result['legs_without_any_poi'])} legs still without a POI"
                  f"{' (written)' if args.write else ' (dry run)'}")
        return 0
    if args.add_maxspeed:
        result = bake_maxspeed(
            data,
            cache_dir=Path(args.cache_dir),
            rate_limit_s=args.rate_limit,
            only=_parse_only(args.only),
        )
        if args.write:
            WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"Baked OSM maxspeed onto {len(result['baked_legs'])} leg(s); "
                  f"{len(result['legs_without_maxspeed'])} without a corridor "
                  f"maxspeed tag"
                  f"{' (written)' if args.write else ' (dry run)'}")
        return 0
    if args.prune_non_truck_pois:
        result = prune_non_truck_pois(data)
        if args.write:
            WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            totals = result["coverage_totals"]
            print(f"Pruned {result['removed_pois']} non-truck POIs; "
                  f"{result['legs_emptied']} legs now stop-less; playable "
                  f"{totals['playable']}/{totals['legs']}"
                  f"{' (written)' if args.write else ' (dry run)'}")
        return 0
    if args.refresh_geometry:
        api_key = None
        if args.engine == "ors":
            api_key = ors_api_key()
            if api_key is None:
                raise SystemExit(
                    f"--engine ors needs the {ORS_API_KEY_ENV} environment "
                    "variable and the tooling group "
                    "(uv run --group tooling ...)."
                )
        result = refresh_corridors(
            data,
            cache_dir=Path(args.cache_dir),
            rate_limit_s=args.rate_limit,
            engine=args.engine,
            api_key=api_key,
            only=_parse_only(args.only),
        )
        if args.write:
            WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            totals = result["coverage_totals"]
            print(f"Refreshed {len(result['refreshed'])} corridor(s) via "
                  f"{args.engine}; playable {totals['playable']}/{totals['legs']}"
                  f"{' (written)' if args.write else ' (dry run)'}")
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
    if args.ors_compare:
        api_key = ors_api_key()
        if api_key is None:
            raise SystemExit(
                f"--ors-compare needs the {ORS_API_KEY_ENV} environment "
                "variable and the tooling group (uv run --group tooling ...)."
            )
        cmp = _ors_compare(data, args.from_city, args.to_city, api_key,
                           Path(args.cache_dir), args.rate_limit)
        current_grade = (f"{cmp['current_avg_grade_pct']}%"
                         if cmp["current_avg_grade_pct"] is not None else "n/a")
        print(
            "ORS vs checked-in: "
            f"miles {cmp['ors_miles']:.1f} vs {cmp['leg_miles']:.0f}; "
            f"terrain {cmp['ors_terrain']} vs {cmp['current_terrain']}; "
            f"avg grade {cmp['ors_avg_grade_pct']}% vs {current_grade}; "
            f"elevation {cmp['ors_min_ft']:.0f}-{cmp['ors_max_ft']:.0f} ft; "
            f"{cmp['ors_points']} ORS points; "
            f"tollway {'yes' if cmp['ors_has_tollway'] else 'no'} "
            f"(checked-in toll events: {cmp['current_toll_events']})"
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
    engine: str = "osrm",
    api_key: str | None = None,
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
            # New legs are added with a "TBD" shield; label them from OSRM's ref
            # field so 100+ legs don't need hand-assigned highways. Done before
            # the ORS fetch so its cache key uses the final highway.
            if str(leg.get("highway", "")).upper() in ("", "TBD"):
                derived_hw = _osrm_primary_highway(data, leg, cache_dir, rate_limit_s)
                if derived_hw:
                    leg["highway"] = derived_hw
            if engine == "ors":
                parsed = _cached_ors_route(data, leg, cache_dir, rate_limit_s, api_key)
                geometry = parsed["coordinates"]
                samples, elevations = ors_corridor_samples(
                    parsed, float(leg["miles"]),
                    sample_count=_ors_sample_count(float(leg["miles"])))
                elevation_source = ORS_ELEVATION_SOURCE
                corridor_source = ORS_CORRIDOR_SOURCE
                corridor["tollway_detected"] = parsed["has_tollway"]
            else:
                route = _cached_osrm_route(data, leg, cache_dir, rate_limit_s)
                geometry = route["geometry"]["coordinates"]
                samples = _sample_geometry(geometry, float(leg["miles"]))
                elevations = _cached_elevations(samples, cache_dir, rate_limit_s)
                elevation_source = ELEVATION_SOURCE
                corridor_source = CORRIDOR_SOURCE
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
                        "source": elevation_source,
                    }
                    for point, elevation in zip(samples, elevations, strict=True)
                ]
            if "grade_segments" in needs:
                corridor["grade_segments"] = (
                    grade_segments_from_samples(samples, elevations, leg)
                    if engine == "ors"
                    else _grade_segments(samples, elevations, leg))
                # Label the leg's coarse terrain from the real grades. Only new
                # legs reach here (fully-enriched legs are skipped above), so a
                # placeholder "flat" on a freshly-added mountain leg is corrected
                # without rewriting existing curated terrain.
                rank = {"flat": 0, "hills": 1, "mountain": 2}
                terrains = [s.get("terrain", "flat") for s in corridor["grade_segments"]]
                if terrains:
                    leg["terrain"] = max(terrains, key=lambda t: rank.get(t, 0))
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
                corridor["source"] = corridor_source
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


def _parse_only(value: str) -> set[tuple[str, str]]:
    # Legs are separated by ';' (not ',') so city names containing a comma
    # (e.g. "Charleston, West Virginia", disambiguated from Charleston, SC) parse
    # correctly. 'From:To' splits on the first ':'.
    pairs: set[tuple[str, str]] = set()
    for item in (value or "").split(";"):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise SystemExit(f"--only entries must be 'From:To', got {item!r}")
        a, b = item.split(":", 1)
        pairs.add((a.strip(), b.strip()))
    return pairs


def refresh_corridors(
    data: dict[str, Any],
    *,
    cache_dir: Path,
    rate_limit_s: float,
    engine: str,
    api_key: str | None,
    only: set[tuple[str, str]],
) -> dict[str, Any]:
    """Re-derive the geometry/terrain layer of selected legs from a routing
    engine, preserving every curated field.

    Only ``route_points``, ``elevation_samples``, ``grade_segments``, and the
    corridor source note are rewritten. Curated miles, POIs/stops, toll events,
    and the hand-named state crossings and checkpoints are left untouched, so a
    regeneration improves truck-legal geometry and real elevation without losing
    curation or changing pay/deadline-affecting mileage.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    refreshed: list[dict[str, Any]] = []
    for leg in data["legs"]:
        key = (leg["from"], leg["to"])
        if only and key not in only and (leg["to"], leg["from"]) not in only:
            continue
        corridor = leg.setdefault("corridor", {})
        miles = float(leg["miles"])
        if engine == "ors":
            parsed = _cached_ors_route(data, leg, cache_dir, rate_limit_s, api_key)
            samples, elevations = ors_corridor_samples(
                parsed, miles, sample_count=_ors_sample_count(miles))
            elevation_source = ORS_ELEVATION_SOURCE
            corridor_source = ORS_CORRIDOR_SOURCE
            corridor["tollway_detected"] = parsed["has_tollway"]
            grade_segments = grade_segments_from_samples(samples, elevations, leg)
        else:
            route = _cached_osrm_route(data, leg, cache_dir, rate_limit_s)
            samples = _sample_geometry(route["geometry"]["coordinates"], miles)
            elevations = _cached_elevations(samples, cache_dir, rate_limit_s)
            elevation_source = ELEVATION_SOURCE
            corridor_source = CORRIDOR_SOURCE
            grade_segments = _grade_segments(samples, elevations, leg)
        corridor["route_points"] = [
            {"at_mi": round(p["at_mi"], 1),
             "lat": round(p["lat"], 5),
             "lon": round(p["lon"], 5)}
            for p in samples
        ]
        corridor["elevation_samples"] = [
            {"at_mi": round(p["at_mi"], 1),
             "elevation_ft": round(e, 1),
             "source": elevation_source}
            for p, e in zip(samples, elevations, strict=True)
        ]
        corridor["grade_segments"] = grade_segments
        corridor["source"] = corridor_source
        refreshed.append({"from": leg["from"], "to": leg["to"],
                          "engine": engine, "points": len(samples)})
    return {"refreshed": refreshed,
            "coverage_totals": coverage_report(data)["totals"]}


def _rescale_corridor_positions(leg: dict[str, Any], factor: float,
                                new_miles: float) -> None:
    """Scale every at_mi position in a leg to a new total mileage.

    Keeps the corridor consistent (endpoints land exactly on 0 and new_miles)
    and clamps interior positions strictly inside the leg so the world loader's
    range validators still accept stops, crossings, checkpoints, and tolls.
    """
    corridor = leg.get("corridor", {})

    def interior(value: float) -> float:
        return max(0.1, min(round(new_miles - 0.1, 1), round(value * factor, 1)))

    for endpoint_field in ("route_points", "elevation_samples"):
        points = corridor.get(endpoint_field, [])
        for point in points:
            point["at_mi"] = round(min(new_miles, max(0.0, point["at_mi"] * factor)), 1)
        if points:
            points[0]["at_mi"] = 0.0
            points[-1]["at_mi"] = round(new_miles, 1)

    segments = corridor.get("grade_segments", [])
    for seg in segments:
        seg["start_mi"] = round(min(new_miles, max(0.0, seg["start_mi"] * factor)), 1)
        seg["end_mi"] = round(min(new_miles, max(0.0, seg["end_mi"] * factor)), 1)
        if seg["end_mi"] <= seg["start_mi"]:
            seg["end_mi"] = round(min(new_miles, seg["start_mi"] + 0.1), 1)
    if segments:
        segments[0]["start_mi"] = 0.0
        segments[-1]["end_mi"] = round(new_miles, 1)

    for field in ("state_crossings", "checkpoints", "toll_events"):
        for item in corridor.get(field, []):
            item["at_mi"] = interior(item["at_mi"])
    for stop in leg.get("stops", []):
        stop["at_mi"] = interior(stop["at_mi"])

    # state_miles is a per-state breakdown, not an at_mi; scale it so it still
    # sums to the leg total, fixing rounding drift on the last entry.
    state_miles = corridor.get("state_miles", [])
    for entry in state_miles:
        entry["miles"] = round(entry["miles"] * factor, 1)
    if state_miles:
        drift = round(new_miles - sum(e["miles"] for e in state_miles), 1)
        state_miles[-1]["miles"] = round(state_miles[-1]["miles"] + drift, 1)


def adopt_ors_miles(
    data: dict[str, Any],
    *,
    cache_dir: Path,
    rate_limit_s: float,
    api_key: str | None,
    only: set[tuple[str, str]],
) -> dict[str, Any]:
    """Rewrite leg mileage to the real ORS driving-hgv distance.

    Leg miles drive pay and deadlines, so accurate truck distances correct the
    economy. Every corridor at_mi position is rescaled to the new total so
    curated stops/crossings/tolls stay valid; their lat/lon and curation are
    otherwise preserved.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    changed: list[dict[str, Any]] = []
    for leg in data["legs"]:
        key = (leg["from"], leg["to"])
        if only and key not in only and (leg["to"], leg["from"]) not in only:
            continue
        old_miles = float(leg["miles"])
        parsed = _cached_ors_route(data, leg, cache_dir, rate_limit_s, api_key)
        new_miles = round(parsed["miles"])
        if new_miles <= 0 or new_miles == old_miles:
            continue
        leg["miles"] = new_miles
        _rescale_corridor_positions(leg, new_miles / old_miles, float(new_miles))
        changed.append({"from": leg["from"], "to": leg["to"],
                        "old_miles": old_miles, "new_miles": new_miles})
    return {"changed": changed, "coverage_totals": coverage_report(data)["totals"]}


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
        box = _bbox(point["lat"], point["lon"], 5000)
        query = f"""
        [out:json][timeout:40];
        (
          nwr["amenity"="fuel"]({box});
          nwr["highway"~"services|rest_area"]({box});
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
        except (TimeoutError, OSError, RuntimeError):
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
        "parking": _parking_for_stop_type(stop_type),
        "actions": actions,
        "services": services,
    }


OVERPASS_POI_SOURCE = (
    "OpenStreetMap/Overpass development-time corridor amenity query, accessed "
    "2026-06-21; curated into a gameplay POI (clean name, normalized category) "
    "without raw OSM IDs."
)


def _bbox(lat: float, lon: float, radius_m: float) -> str:
    """A ``south,west,north,east`` box roughly ``radius_m`` around a point.

    Used as an Overpass bbox filter instead of ``around:``. On the public
    Overpass instances ``around:`` radius filters over broad amenity unions
    routinely time out (server aborts at 30-60s with an empty ``remark``
    payload); the equivalent bbox query returns the same POIs in a few seconds.
    """
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * max(0.1, math.cos(math.radians(lat))))
    return f"{lat - dlat},{lon - dlon},{lat + dlat},{lon + dlon}"


def _overpass_named_candidates(
    leg: dict[str, Any],
    samples: list[dict[str, float]],
    cache_dir: Path,
    rate_limit_s: float,
    want: int,
) -> list[dict[str, Any]]:
    """Named truck-relevant POIs of any brand near a leg, from OpenStreetMap.

    Brand-agnostic: returns Love's, Pilot, TA, Road Ranger, Kwik Trip,
    independents, rest areas, service plazas, and HGV truck parking alike --
    whatever OSM has a real name for. Unnamed amenities are skipped (no synthetic
    placeholders). Deduped by name, capped at ``want``.
    """
    candidate_points = [samples[len(samples) // 2]]
    if len(samples) >= 4:
        candidate_points += [samples[1], samples[-2]]
    if len(samples) >= 6:
        candidate_points += [samples[len(samples) // 4], samples[3 * len(samples) // 4]]
    # Gather across points, then rank: truck stops first, generic corridor fuel
    # as a fallback, warehouse/grocery retail fuel dropped entirely. Keeping the
    # best per name means one slow point doesn't starve the leg of good POIs.
    best: dict[str, tuple[int, dict[str, Any]]] = {}
    for point in candidate_points:
        box = _bbox(point["lat"], point["lon"], 6000)
        query = f"""
        [out:json][timeout:40];
        (
          nwr["amenity"="fuel"]["name"]({box});
          nwr["highway"~"services|rest_area"]["name"]({box});
          nwr["amenity"="parking"]["hgv"="yes"]["name"]({box});
        );
        out tags center 25;
        """
        try:
            payload = _cached_overpass_json(
                cache_dir,
                f"named--{leg['from']}--{leg['to']}--{point['at_mi']:.1f}",
                urllib.parse.urlencode({"data": query}).encode("utf-8"),
                rate_limit_s=rate_limit_s,
            )
        except (TimeoutError, OSError, urllib.error.URLError,
                urllib.error.HTTPError, RuntimeError):
            continue  # skip this point/leg; all endpoints failed or timed out
        at_mi = round(max(1.0, min(float(leg["miles"]) - 1.0, point["at_mi"])), 1)
        for element in payload.get("elements", []):
            tags = element.get("tags", {})
            raw = tags.get("name") or tags.get("brand") or ""
            try:
                name = _clean_poi_name(raw)
            except ValueError:
                continue
            if not name:
                continue
            score = _truck_relevance(tags, name)
            if score is None:
                continue  # retail/grocery fuel -- not a truck stop
            stop_type = _stop_type_from_tags(tags)
            cand = {
                "name": name,
                "type": stop_type,
                "at_mi": at_mi,
                "source": OVERPASS_POI_SOURCE,
                "parking": _parking_for_stop_type(stop_type),
                "actions": _actions_for_stop_type(stop_type),
                "services": _services_for_stop_type(stop_type),
            }
            existing = best.get(name.lower())
            if existing is None or score > existing[0]:
                best[name.lower()] = (score, cand)
    ranked = sorted(best.values(), key=lambda item: item[0], reverse=True)
    return [cand for _score, cand in ranked[:want]]


# Truck-stop brands / keywords (highest-value POIs for a freight game).
_TRUCK_POI_KEYWORDS = (
    "love's", "loves travel", "pilot", "flying j", "ta travel", "travelcenters",
    "petro stopping", "ta petro", "road ranger", "ambest", "sapp bros",
    "kwik trip", "kwik star", "one9", "roady", "mr. fuel", "busy bee",
    "travel center", "travel plaza", "travel stop", "truck stop", "truckstop",
    "service plaza", "truck plaza",
)
# Warehouse-club / grocery fuel: real OSM amenity=fuel points, but not truck
# stops (members-only pumps, no big-rig access -- Buc-ee's famously bans trucks).
_RETAIL_FUEL_KEYWORDS = (
    "sam's club", "sams club", "costco", "bj's", "walmart", "kroger", "meijer",
    "safeway", "albertsons", "h-e-b", "heb ", "buc-ee", "bucee", "wegmans",
    "publix", "giant eagle", "fred meyer", "king soopers", "stop & shop",
    "stop and shop", "woodman",
)
# Names that are not a place a driver stops for fuel/rest -- OSM mistags or
# mandatory-only facilities that shouldn't surface as a chooseable stop.
_NON_STOP_KEYWORDS = ("cleaning service", "weigh station", "inspection station")
_RETAIL_SHOP_TAGS = {"supermarket", "wholesale", "department_store", "convenience"}


def _truck_relevance(tags: dict[str, str], name: str) -> int | None:
    """Rank a candidate POI for a freight game; ``None`` means drop it.

    Truck-relevant only: service plazas, rest areas, HGV-tagged or HGV-diesel
    fuel, dedicated truck parking, and named truck-stop brands. A plain
    ``amenity=fuel`` car station with no truck signal is dropped -- a Class-8
    driver does not pull a 70-foot rig into a corner Shell. Warehouse/grocery
    retail and OSM mistags are rejected too.
    """
    low = name.lower()
    if len(low.strip()) < 2:
        return None  # meaningless single-char names ("B")
    if any(word in low for word in _RETAIL_FUEL_KEYWORDS):
        return None
    if any(word in low for word in _NON_STOP_KEYWORDS):
        return None
    if tags.get("shop", "") in _RETAIL_SHOP_TAGS:
        return None
    amenity = tags.get("amenity", "")
    highway = tags.get("highway", "")
    hgv = tags.get("hgv", "") in {"yes", "designated"}
    hgv_diesel = tags.get("fuel:HGV_diesel", "") in {"yes", "designated"}
    is_brand = any(word in low for word in _TRUCK_POI_KEYWORDS)
    truck_signal = (
        highway in {"services", "rest_area"}
        or hgv or hgv_diesel or is_brand or amenity == "parking"
    )
    if not truck_signal:
        return None  # generic car fuel -- not a truck stop
    score = 0
    if highway == "services":
        score += 10
    if highway == "rest_area":
        score += 8
    if hgv or hgv_diesel:
        score += 8
    if is_brand:
        score += 10
    if amenity == "fuel":
        score += 3
    if amenity == "parking":
        score += 1
    return score


def add_overpass_pois(
    data: dict[str, Any],
    *,
    cache_dir: Path,
    rate_limit_s: float,
    only: set[tuple[str, str]],
    per_leg: int = 2,
) -> dict[str, Any]:
    """Additively enrich legs with named OSM truck POIs of any brand.

    Purely additive (POIs do not gate dispatch): adds up to ``per_leg`` new
    named stops per leg, deduped against existing Love's/Pilot curation. Robust
    to Overpass hiccups -- a leg that errors or finds nothing is simply skipped,
    and the cache makes re-runs resumable.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    added = updated = 0
    still_empty: list[str] = []
    for leg in data["legs"]:
        key = (leg["from"], leg["to"])
        if only and key not in only and (leg["to"], leg["from"]) not in only:
            continue
        points = leg.get("corridor", {}).get("route_points", [])
        if len(points) < 2:
            continue
        stops = leg.setdefault("stops", [])
        existing = {str(s.get("name", "")).lower() for s in stops}
        taken_mi = [float(s["at_mi"]) for s in stops]
        cands = _overpass_named_candidates(
            leg, points, cache_dir, rate_limit_s, per_leg + len(existing) + 6)
        fresh = []
        for cand in cands:
            if cand["name"].lower() in existing:
                continue
            at = float(cand["at_mi"])
            # Keep stops visibly apart on the corridor: a cluster of POIs found
            # near one sample point would otherwise land on nearly the same mile.
            if any(abs(at - t) < MIN_STOP_SPACING_MI for t in taken_mi):
                continue
            fresh.append(cand)
            existing.add(cand["name"].lower())
            taken_mi.append(at)
            if len(fresh) >= per_leg:
                break
        if fresh:
            leg["stops"] = sorted(stops + fresh, key=lambda s: float(s["at_mi"]))
            _spread_stop_positions(leg["stops"], leg["miles"])
            added += len(fresh)
            updated += 1
        elif not stops:
            still_empty.append(f"{leg['from']}-{leg['to']}")
    return {
        "added_pois": added,
        "updated_legs": updated,
        "legs_without_any_poi": still_empty,
        "coverage_totals": coverage_report(data)["totals"],
    }


MAXSPEED_SOURCE = (
    "OpenStreetMap maxspeed tags on the corridor highway ways (Overpass), "
    "development-time, normalized to mph; maxspeed:hgv preferred where tagged."
)
KMH_TO_MPH = 0.621371
# OSM `maxspeed` values that carry no numeric posted limit -- leave the leg to
# the runtime heuristic rather than inventing a number.
_MAXSPEED_NON_NUMERIC = {"none", "signals", "walk", "variable", "no", "unknown"}
_MAXSPEED_NUMBER = re.compile(r"(\d+(?:\.\d+)?)")
# Mainline corridor way classes worth a posted limit; service/link roads ignored.
_MAXSPEED_HIGHWAY_CLASSES = ("motorway", "trunk", "primary", "secondary")


def parse_osm_maxspeed(raw: Any, *, default_kmh: bool = False) -> float | None:
    """Normalize a raw OSM ``maxspeed`` value to mph, or ``None`` if unusable.

    Handles the common shapes: ``"55 mph"``, a bare ``"55"`` (assumed mph for the
    US map unless ``default_kmh``, matching OSM's km/h default for non-US data),
    metric ``"90 km/h"``/``"100 kmh"``, the ``"none"``/``"signals"`` non-values,
    and lists like ``"55 mph; 50 mph"`` (the first parseable token wins, i.e. the
    general limit before conditional ones). Results are rounded to the nearest
    5 mph and clamped to a sane truck range; anything unparseable returns
    ``None`` so the caller can fall back to the heuristic."""
    if raw is None:
        return None
    for token in re.split(r"[;,]", str(raw)):
        token = token.strip().lower()
        if not token or token in _MAXSPEED_NON_NUMERIC:
            continue
        if "knots" in token:
            continue
        match = _MAXSPEED_NUMBER.search(token)
        if not match:
            continue
        value = float(match.group(1))
        if "mph" in token:
            mph = value
        elif any(unit in token for unit in ("km/h", "kmh", "kph")):
            mph = value * KMH_TO_MPH
        else:
            mph = value * KMH_TO_MPH if default_kmh else value
        mph = round(mph / 5.0) * 5.0
        if mph < 5.0:
            continue
        return min(85.0, mph)
    return None


def _maxspeed_from_tags(tags: dict[str, str]) -> tuple[float, bool] | None:
    """Posted mph for a highway way, preferring the truck-specific tag.

    Returns ``(mph, is_hgv)`` or ``None`` when the way has no usable maxspeed."""
    hgv_mph = parse_osm_maxspeed(tags.get("maxspeed:hgv"))
    if hgv_mph is not None:
        return hgv_mph, True
    mph = parse_osm_maxspeed(tags.get("maxspeed"))
    if mph is not None:
        return mph, False
    return None


def _maxspeed_at_point(
    leg: dict[str, Any],
    point: dict[str, float],
    cache_dir: Path,
    rate_limit_s: float,
) -> tuple[float, bool] | None:
    """Best posted limit on the corridor's highway near one route point.

    Queries OSM ways carrying a ``maxspeed`` within a short radius and prefers
    the way whose ``ref`` matches the leg's highway shield (e.g. ``I 95``), so a
    parallel frontage road's 45 mph doesn't override the interstate."""
    box = _bbox(point["lat"], point["lon"], 400)
    classes = "|".join(_MAXSPEED_HIGHWAY_CLASSES)
    query = f"""
    [out:json][timeout:40];
    way["highway"~"{classes}"]["maxspeed"]({box});
    out tags 40;
    """
    try:
        payload = _cached_overpass_json(
            cache_dir,
            f"maxspeed--{leg['from']}--{leg['to']}--{point['at_mi']:.1f}",
            urllib.parse.urlencode({"data": query}).encode("utf-8"),
            rate_limit_s=rate_limit_s,
        )
    except (TimeoutError, OSError, urllib.error.URLError,
            urllib.error.HTTPError, RuntimeError):
        return None
    shield = _highway_digits(str(leg.get("highway", "")))
    best: tuple[float, bool] | None = None
    best_on_shield = False
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        parsed = _maxspeed_from_tags(tags)
        if parsed is None:
            continue
        mph, is_hgv = parsed
        on_shield = bool(shield) and _highway_digits(tags.get("ref", "")) == shield
        # A way matching the leg's shield always wins; otherwise keep the highest
        # posted limit found (the mainline, not a ramp or frontage road).
        if on_shield and not best_on_shield:
            best, best_on_shield = (mph, is_hgv), True
        elif on_shield == best_on_shield and (best is None or mph > best[0]):
            best = (mph, is_hgv)
    return best


def _highway_digits(highway: str) -> str:
    """The route number from a shield/ref, e.g. ``I-95`` or ``I 95`` -> ``95``."""
    digits = re.findall(r"\d+", str(highway))
    return digits[0] if digits else ""


def bake_maxspeed(
    data: dict[str, Any],
    *,
    cache_dir: Path,
    rate_limit_s: float,
    only: set[tuple[str, str]],
) -> dict[str, Any]:
    """Bake a real OSM ``maxspeed`` profile onto each leg from its route points.

    Additive and idempotent: samples the posted limit at each checked-in route
    point, collapses consecutive equal values into a step function, and stores it
    as ``corridor.speed_limits`` (mph, already normalized). Legs where OSM has no
    maxspeed on the corridor are left without a profile, so the runtime keeps
    using the highway/region heuristic for them."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    baked: list[dict[str, Any]] = []
    skipped: list[str] = []
    for leg in data["legs"]:
        key = (leg["from"], leg["to"])
        if only and key not in only and (leg["to"], leg["from"]) not in only:
            continue
        points = leg.get("corridor", {}).get("route_points", [])
        if len(points) < 2:
            skipped.append(f"{leg['from']}-{leg['to']}")
            continue
        samples: list[dict[str, Any]] = []
        for point in points:
            result = _maxspeed_at_point(leg, point, cache_dir, rate_limit_s)
            if result is None:
                continue
            mph, is_hgv = result
            at_mi = round(float(point["at_mi"]), 1)
            # Collapse a repeated limit into the step function it represents.
            if samples and samples[-1]["mph"] == mph and samples[-1]["hgv"] == is_hgv:
                continue
            samples.append({"at_mi": at_mi, "mph": mph,
                            "source": MAXSPEED_SOURCE, "hgv": is_hgv})
        if samples:
            leg.setdefault("corridor", {})["speed_limits"] = samples
            baked.append({"from": leg["from"], "to": leg["to"],
                          "samples": len(samples)})
        else:
            skipped.append(f"{leg['from']}-{leg['to']}")
    return {
        "baked_legs": baked,
        "legs_without_maxspeed": skipped,
        "coverage_totals": coverage_report(data)["totals"],
    }


_TRUCK_STOP_TYPES = {"travel_center", "truck_stop", "service_plaza",
                     "public_rest_area", "truck_parking"}


def _stop_is_truck_relevant(stop: dict[str, Any]) -> bool:
    """Whether a stored stop is somewhere a Class-8 driver actually stops.

    Raw OSM tags are not retained on the stored stop, so this judges by the
    stored type and name: keep service plazas, rest areas, truck parking,
    travel/truck centers, and named truck-stop brands; a plain ``fuel_station``
    (generic car gas) is not truck-relevant.
    """
    if str(stop.get("type", "")) in _TRUCK_STOP_TYPES:
        return True
    low = str(stop.get("name", "")).lower()
    return any(word in low for word in _TRUCK_POI_KEYWORDS)


def prune_non_truck_pois(data: dict[str, Any]) -> dict[str, Any]:
    """Strip auto-discovered non-truck POIs (generic car fuel) network-wide.

    Only Overpass-discovered stops are filtered; curated (hand-verified) stops
    are always kept. Purely subtractive -- POIs are advisory and dispatch gates
    on routing metadata, so a leg left stop-less stays playable.
    """
    removed = legs_emptied = 0
    for leg in data["legs"]:
        stops = leg.get("stops", [])
        if not stops:
            continue
        kept = []
        for stop in stops:
            src = str(stop.get("source", ""))
            is_overpass = "Overpass" in src and "amenity query" in src
            if is_overpass and not _stop_is_truck_relevant(stop):
                removed += 1
                continue
            kept.append(stop)
        if len(kept) != len(stops):
            leg["stops"] = kept
            if not kept:
                legs_emptied += 1
    return {
        "removed_pois": removed,
        "legs_emptied": legs_emptied,
        "coverage_totals": coverage_report(data)["totals"],
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
    if amenity == "fuel" and (
        tags.get("hgv", "") in {"yes", "designated"}
        or tags.get("fuel:HGV_diesel", "") in {"yes", "designated"}
    ):
        return "travel_center"  # truck-capable fuel; keep it truck-typed
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


# Minimum spacing between a newly-added POI and any existing stop. Several real
# truck stops often cluster at one interchange; surfacing them on near-identical
# miles reads as a "two stops on the same mile" bug while driving, so pick stops
# that are genuinely spread along the corridor instead.
MIN_STOP_SPACING_MI = 10.0


def _nearest_free_mile(
    target: float, taken: list[float], min_gap: float, lo: float, hi: float,
) -> float:
    """Closest mile to ``target`` that is >= ``min_gap`` from every taken mile."""
    def is_free(mile: float) -> bool:
        return all(abs(mile - t) >= min_gap - 1e-9 for t in taken)

    target = round(min(hi, max(lo, target)), 1)
    if is_free(target):
        return target
    step = 0.5
    for k in range(1, int((hi - lo) / step) + 2):
        for cand in (round(target + k * step, 1), round(target - k * step, 1)):
            if lo <= cand <= hi and is_free(cand):
                return cand
    return target


def _spread_stop_positions(
    stops: list[dict[str, Any]], leg_miles: float, *, min_gap: float = 1.0,
) -> list[dict[str, Any]]:
    """Give every stop its own truck-mile marker.

    Discovered POIs inherit their corridor sample point's mileage, so several
    can land on the same mile (and on top of a curated stop). Curated stops keep
    their authoritative positions; each discovered stop is nudged to the nearest
    free mile at least ``min_gap`` apart, staying within the leg."""
    lo, hi = 1.0, max(1.0, round(float(leg_miles) - 1.0, 1))
    taken = [round(float(s["at_mi"]), 1)
             for s in stops if s.get("source") != OVERPASS_POI_SOURCE]
    movable = sorted(
        (s for s in stops if s.get("source") == OVERPASS_POI_SOURCE),
        key=lambda s: float(s["at_mi"]))
    for stop in movable:
        at = _nearest_free_mile(float(stop["at_mi"]), taken, min_gap, lo, hi)
        stop["at_mi"] = at
        taken.append(at)
    stops.sort(key=lambda s: float(s["at_mi"]))
    return stops


def _parking_for_stop_type(stop_type: str) -> str:
    """Explicit truck-parking availability for a discovered POI.

    The coverage contract treats ``parking == "unknown"`` as incomplete, so a
    discovered stop must declare a concrete value. Big travel centers and
    service plazas reliably have it; rest areas and dedicated truck lots have
    some; a generic fuel station offers a pull-in at best, not overnight."""
    if stop_type in {"truck_stop", "travel_center", "service_plaza"}:
        return "likely"
    return "limited"


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


def _overpass_is_error(payload: dict[str, Any]) -> bool:
    """True if an Overpass HTTP-200 body is actually a server-side failure.

    Overpass reports query timeouts and rate limits as a 200 response carrying
    an empty ``elements`` list plus a ``remark`` -- so a naive cache treats the
    failure as a valid "nothing here" answer. A genuinely empty area returns no
    ``remark``, so only remark-bearing bodies are failures.
    """
    remark = str(payload.get("remark", "")).lower()
    return any(
        token in remark
        for token in ("runtime error", "timed out", "rate_limited", "too many")
    )


def _cached_overpass_json(
    cache_dir: Path,
    key: str,
    body: bytes,
    *,
    rate_limit_s: float,
) -> dict[str, Any]:
    path = _cache_file(cache_dir, "overpass", key)
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if not _overpass_is_error(cached):
            return cached
        path.unlink()  # drop a stale failure so this run can retry it
    last_error: Exception | None = None
    for url in OVERPASS_URLS:
        per_url = _cache_file(cache_dir, "overpass", f"{key}--{_hash_key(url)}")
        try:
            payload = _cached_post_json(
                cache_dir,
                "overpass",
                f"{key}--{_hash_key(url)}",
                url,
                body,
                rate_limit_s=rate_limit_s,
            )
        except (TimeoutError, urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
            last_error = exc
            per_url.unlink(missing_ok=True)
            continue
        if _overpass_is_error(payload):
            # Server aborted (timeout / rate limit). Don't cache the failure;
            # try the next endpoint instead.
            last_error = RuntimeError(
                f"Overpass error from {url}: {payload.get('remark', '').strip()}")
            per_url.unlink(missing_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True),
                        encoding="utf-8")
        return payload
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
        "toll_review_pending": 0,
        "poi_review_pending": 0,
        "playable": 0,
    }
    leg_reports = []
    toll_review: list[dict[str, Any]] = []
    poi_review: list[dict[str, Any]] = []
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
        if corridor.get("tollway_detected") and not toll_events:
            totals["toll_review_pending"] += 1
            toll_review.append({
                "from": leg["from"],
                "to": leg["to"],
                "highway": leg["highway"],
                "note": "ORS flags a tollway but no toll_events are curated.",
            })
        fuel_capable = sum(
            1 for stop in curated_stops if "fuel" in _stop_actions(stop))
        if float(leg["miles"]) >= LONG_LEG_POI_ADVISORY_MI and fuel_capable == 0:
            totals["poi_review_pending"] += 1
            poi_review.append({
                "from": leg["from"],
                "to": leg["to"],
                "highway": leg["highway"],
                "miles": leg["miles"],
                "note": ("Long leg with no fuel-capable curated stop; leans on "
                         "the roadside-fuel fallback. Curation optional."),
            })
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
            "pois_are_advisory_not_required_for_dispatch": True,
            "placeholder_pois_do_not_count_for_dispatch": True,
            "advisory_minimum_curated_pois_by_length": {
                "under_160_mi": 1,
                "160_to_320_mi": 2,
                "over_320_mi": 3,
            },
            "advisory_minimum_fuel_capable_pois_by_length": {
                "under_160_mi": 0,
                "160_mi_and_over": 1,
            },
            "state_crossings_required_when_endpoint_states_differ": True,
            "runtime_network_calls": False,
            "legacy_full_graph_available_for_old_saves": True,
        },
        "current_batch_notes": [
            "Dispatch gates on routing metadata (geometry, elevation, grade, "
            f"state context) for the current {len(legs)}-leg network, from OSRM "
            "or the OpenRouteService driving-hgv route (elevation inline). "
            "Curated source-backed truck-stop coverage is now an additive "
            "quality layer, not a dispatch requirement; placeholder POIs stay "
            "quarantined and never count as curated. Long legs without a "
            "fuel/rest stop are flagged in poi_review, not blocked.",
        ],
        "toll_review": toll_review,
        "poi_review": poi_review,
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


def _unsupported_reasons(missing: list[str], **_poi_advisory: int) -> list[str]:
    """Blocking (routing) reasons a leg is not dispatchable.

    POIs are advisory and never appear in ``missing`` anymore, so they are not
    reported here; the extra keyword arguments are accepted for call-site
    compatibility and ignored.
    """
    return [f"missing {field}" for field in missing]


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


def _ors_directions_kwargs(start: dict[str, Any], end: dict[str, Any]) -> dict[str, Any]:
    """The driving-hgv directions request as SDK keyword arguments.

    Pure, so it is unit-testable without the SDK installed.
    """
    return {
        "coordinates": [
            [float(start["lon"]), float(start["lat"])],
            [float(end["lon"]), float(end["lat"])],
        ],
        "profile": ORS_HGV_PROFILE,
        "format": "geojson",
        "elevation": True,
        "extra_info": list(ORS_EXTRA_INFO),
    }


def fetch_ors_hgv_route(
    start: dict[str, Any],
    end: dict[str, Any],
    api_key: str,
    *,
    timeout_s: float = OSRM_TIMEOUT_S + 15,
) -> dict[str, Any]:
    """Live OpenRouteService driving-hgv request returning the raw GeoJSON.

    Uses the official ``openrouteservice`` SDK (build-time ``tooling`` group),
    which handles auth and rate-limit retries. Kept separate from
    :func:`parse_ors_route` so the mapping can be unit-tested without network or
    the SDK installed. The SDK is imported lazily so the rest of this tool runs
    with the standard library alone.
    """
    try:
        import openrouteservice
    except ImportError as exc:
        raise SystemExit(
            "The OpenRouteService SDK is not installed. It is a build-time "
            "dependency: run with `uv run --group tooling ...`."
        ) from exc
    base_url = os.environ.get("ORS_BASE_URL", ORS_DEFAULT_BASE_URL)
    client = openrouteservice.Client(
        key=api_key, base_url=base_url, timeout=timeout_s,
        retry_over_query_limit=True)
    return client.directions(**_ors_directions_kwargs(start, end))


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


_OSRM_REF_RE = re.compile(r"([A-Za-z]{1,3})\s*-?\s*(\d+)")


def _osrm_primary_highway(
    data: dict[str, Any], leg: dict[str, Any], cache_dir: Path, rate_limit_s: float,
) -> str:
    """Dominant route shield for a leg, from OSRM's step ``ref`` field.

    OSRM separates the highway ref ("I 40") from the road name, so the
    longest-distance ref is reliably the through highway -- unlike ORS step
    names, which often carry only a concurrent US/state route. Interstates win
    when present, else the longest ref (so California's CA-99 legs label
    correctly too). Free and key-less; used only to *label* new legs -- the
    truck route itself still comes from ORS. Returns "" if OSRM is unavailable.
    """
    cities = data["cities"]
    start, end = cities[leg["from"]], cities[leg["to"]]
    coords = f"{start['lon']},{start['lat']};{end['lon']},{end['lat']}"
    params = {"overview": "false", "steps": "true",
              "alternatives": "false", "geometries": "geojson"}
    try:
        payload = _cached_json(
            cache_dir, "osrm-steps", f"{leg['from']}--{leg['to']}",
            OSRM_ROUTE_URL.format(coords=coords) + "?" + urllib.parse.urlencode(params),
            rate_limit_s=rate_limit_s)
    except (TimeoutError, OSError, urllib.error.URLError, urllib.error.HTTPError):
        return ""
    if payload.get("code") != "Ok" or not payload.get("routes"):
        return ""
    by_ref: dict[str, float] = {}
    for route_leg in payload["routes"][0].get("legs", []):
        for step in route_leg.get("steps", []):
            dist = float(step.get("distance", 0.0))
            for part in str(step.get("ref", "") or "").split(";"):
                match = _OSRM_REF_RE.search(part)
                if match:
                    ref = f"{match.group(1).upper()}-{match.group(2)}"
                    by_ref[ref] = by_ref.get(ref, 0.0) + dist
    if not by_ref:
        return ""
    interstates = {r: d for r, d in by_ref.items() if r.startswith("I-")}
    pool = interstates or by_ref
    return max(pool, key=pool.__getitem__)


def _cached_ors_route(
    data: dict[str, Any],
    leg: dict[str, Any],
    cache_dir: Path,
    rate_limit_s: float,
    api_key: str,
) -> dict[str, Any]:
    """Parsed ORS driving-hgv route for a leg, caching the raw GeoJSON.

    Caching keeps re-runs off the rate-limited API; the committed artifact is
    still ``world.json``, and ``.route-cache/`` stays local (git-ignored).
    """
    cities = data["cities"]
    path = _cache_file(cache_dir, "ors", f"{leg['from']}--{leg['to']}--{leg['highway']}")
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = fetch_ors_hgv_route(cities[leg["from"]], cities[leg["to"]], api_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        if rate_limit_s > 0:
            time.sleep(rate_limit_s)
    return parse_ors_route(payload)


def ors_corridor_samples(
    parsed: dict[str, Any],
    leg_miles: float,
    sample_count: int = 5,
) -> tuple[list[dict[str, float]], list[float]]:
    """Evenly spaced corridor samples plus their elevation, from a parsed ORS
    route. Mirrors :func:`_sample_geometry` but carries the per-vertex elevation
    ORS returns inline, so no separate elevation request is needed.
    """
    coords = parsed["coordinates"]
    elevations = parsed["elevations_ft"]
    if len(coords) < 2:
        raise RuntimeError("ORS route geometry has fewer than two points")
    distances = [0.0]
    for prev, cur in zip(coords, coords[1:], strict=False):
        distances.append(distances[-1] + _haversine_miles(prev[1], prev[0], cur[1], cur[0]))
    total = distances[-1] or 1.0
    desired = [leg_miles * i / (sample_count - 1) for i in range(sample_count)]
    samples: list[dict[str, float]] = []
    sample_elevations: list[float] = []
    for at_mi in desired:
        target = total * at_mi / leg_miles if leg_miles else 0.0
        index = next(
            (i for i, dist in enumerate(distances) if dist >= target),
            len(distances) - 1,
        )
        lon, lat = coords[index]
        samples.append({"at_mi": at_mi, "lat": float(lat), "lon": float(lon)})
        sample_elevations.append(
            elevations[index] if index < len(elevations)
            else (elevations[-1] if elevations else 0.0)
        )
    samples[0]["at_mi"] = 0.0
    samples[-1]["at_mi"] = leg_miles
    return samples, sample_elevations


def _ors_sample_count(miles: float) -> int:
    """Corridor sample count for ORS legs.

    ORS returns elevation inline (no per-point Open-Meteo call), so denser
    sampling is cheap and gives real terrain. Roughly one sample per 30 miles,
    clamped so short legs still get a usable profile and long legs stay compact.
    """
    return max(5, min(25, int(miles // 30) + 2))


def _terrain_for_grade(abs_grade_pct: float) -> str:
    if abs_grade_pct > 3.0:
        return "mountain"
    if abs_grade_pct > 0.8:
        return "hills"
    return "flat"


def grade_segments_from_samples(
    samples: list[dict[str, float]],
    elevations_ft: list[float],
    leg: dict[str, Any],
) -> list[dict[str, Any]]:
    """Multiple grade segments grouping consecutive same-terrain intervals.

    Unlike the single averaged segment, this keeps real up/down structure (a
    mountain leg shows its climbs and descents instead of washing out to ~0%).
    Falls back to the single-segment builder when samples are too sparse.
    """
    if len(samples) < 3:
        return _grade_segments(samples, elevations_ft, leg)
    intervals: list[tuple[float, float, float, str]] = []
    for start, end, elev_a, elev_b in zip(
        samples, samples[1:], elevations_ft, elevations_ft[1:], strict=False
    ):
        run_mi = max(0.1, end["at_mi"] - start["at_mi"])
        grade = (elev_b - elev_a) / (run_mi * 5280.0) * 100.0
        intervals.append((start["at_mi"], end["at_mi"], grade,
                          _terrain_for_grade(abs(grade))))
    segments: list[dict[str, Any]] = []
    seg_start, seg_end, grades, terrain = (
        intervals[0][0], intervals[0][1], [intervals[0][2]], intervals[0][3])
    for start, end, grade, kind in intervals[1:]:
        if kind == terrain:
            seg_end = end
            grades.append(grade)
        else:
            segments.append(_grade_segment(seg_start, seg_end, grades, terrain))
            seg_start, seg_end, grades, terrain = start, end, [grade], kind
    segments.append(_grade_segment(seg_start, seg_end, grades, terrain))
    return segments


def _grade_segment(start_mi: float, end_mi: float, grades: list[float],
                   terrain: str) -> dict[str, Any]:
    return {
        "start_mi": round(start_mi, 1),
        "end_mi": round(end_mi, 1),
        "avg_grade_pct": round(sum(grades) / len(grades), 2),
        "terrain": terrain,
        "source": ORS_GRADE_SOURCE,
    }


def _ors_compare(
    data: dict[str, Any],
    from_city: str,
    to_city: str,
    api_key: str,
    cache_dir: Path,
    rate_limit_s: float,
) -> dict[str, Any]:
    """Read-only sanity check: ORS-derived corridor vs the checked-in one."""
    leg = _find_leg(data, from_city, to_city)
    if leg is None:
        raise SystemExit(f"No direct world leg {from_city} to {to_city}")
    parsed = _cached_ors_route(data, leg, cache_dir, rate_limit_s, api_key)
    miles = float(leg["miles"])
    samples, elevations = ors_corridor_samples(parsed, miles)
    ors_grade = _grade_segments(samples, elevations, leg)[0]
    corridor = leg.get("corridor", {})
    current_grades = corridor.get("grade_segments") or [{}]
    return {
        "leg_miles": miles,
        "ors_miles": parsed["miles"],
        "ors_points": len(parsed["coordinates"]),
        "ors_min_ft": min(elevations) if elevations else 0.0,
        "ors_max_ft": max(elevations) if elevations else 0.0,
        "ors_avg_grade_pct": ors_grade["avg_grade_pct"],
        "ors_terrain": ors_grade["terrain"],
        "current_terrain": current_grades[0].get("terrain", leg.get("terrain")),
        "current_avg_grade_pct": current_grades[0].get("avg_grade_pct"),
        "ors_has_tollway": parsed["has_tollway"],
        "current_toll_events": len(corridor.get("toll_events", ())),
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
