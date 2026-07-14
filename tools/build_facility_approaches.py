r"""Build bounded source-backed freight facility approach geometry.

Runtime gameplay reads ``facility_approaches.json`` offline. This tool is
build-time only and uses local OSM extracts; it never calls live routing APIs.

Example:
    uv run --group tooling python tools/build_facility_approaches.py \
      --cache-dir C:\Users\joshu\.cache\freight-fate-osm\regions --write
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from freight_fate.data.world import get_world

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
FACILITY_ENDPOINTS_PATH = ROOT / "src" / "freight_fate" / "data" / "facility_endpoints.json"
LOCAL_APPROACHES_PATH = ROOT / "src" / "freight_fate" / "data" / "local_approaches.json"
FACILITY_APPROACHES_PATH = ROOT / "src" / "freight_fate" / "data" / "facility_approaches.json"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "freight-fate-osm" / "regions"
ACCESSED_DATE = "2026-06-27"
DEFAULT_STATES = ("Illinois", "Indiana", "Ohio")
MAX_ROUTE_MI = 18.0
# A single-segment path shorter than this adds nothing over the fallback leg,
# but a genuine multi-turn chain stays playable well below it now that the
# runtime drives surface segments (Phases 2-3 of docs/surface-roads-plan.md).
MIN_PLAYABLE_ROUTE_MI = 2.0
MIN_CHAIN_ROUTE_MI = 0.5
RAW_MARKERS = ("osm_id", "amenity=", "highway=", "operator=", "node/", "way/", "relation/")
HIGH_CONFIDENCE_TYPES = {
    "company_yard",
    "cross_dock",
    "distribution",
    "dry_warehouse",
    "intermodal_ramp",
    "manufacturing_plant",
    "parcel_hub",
    "terminal",
    "warehouse",
}


@dataclass(frozen=True)
class FacilityTarget:
    facility_id: str
    city: str
    state: str
    facility_name: str
    facility_type: str
    endpoint_name: str
    lat: float
    lon: float
    start_lat: float
    start_lon: float
    endpoint_source_backed: bool
    endpoint_fallback: bool
    endpoint_source_note: str
    local_approach_miles: float
    local_approach_road: str


def _load_local_geometry_tool():
    path = TOOLS_DIR / "build_local_geometry.py"
    spec = importlib.util.spec_from_file_location("build_local_geometry", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_facility_approaches(
    cache_dir: Path,
    *,
    states: tuple[str, ...] = DEFAULT_STATES,
    max_route_mi: float = MAX_ROUTE_MI,
) -> dict[str, Any]:
    local_geometry = _load_local_geometry_tool()
    targets = collect_targets()
    state_set = set(states)
    routable = [
        target
        for target in targets
        if target.endpoint_source_backed
        and not target.endpoint_fallback
        and target.state in state_set
        and target.facility_type in HIGH_CONFIDENCE_TYPES
        and target.local_approach_miles <= max_route_mi
    ]
    routed: dict[str, Any] = {}
    sources: list[dict[str, Any]] = []
    for state in states:
        extract = local_geometry.state_extract_path(cache_dir, state)
        sources.append(local_geometry.source_record(state, extract))
        state_targets = [
            _geometry_target(local_geometry, target) for target in routable if target.state == state
        ]
        if extract.exists() and state_targets:
            routed.update(local_geometry.route_state_targets(extract, state_targets))

    approaches = {
        target.facility_id: approach_record(target, routed.get(target.facility_id), state_set)
        for target in targets
    }
    return {
        "version": 1,
        "generated": {
            "accessed": ACCESSED_DATE,
            "family": "OpenStreetMap local Geofabrik extracts plus checked-in facility endpoints",
            "source_policy": "Build-time only; runtime reads this compact checked-in file.",
            "states": list(states),
            "max_route_mi": max_route_mi,
            "road_policy": (
                "Only source-backed endpoints in the bounded state/type batch are "
                "eligible for snapped road and turn geometry. Other facilities keep "
                "explicit fallback metadata."
            ),
            "gate_policy": (
                "No gate, yard, dock, driveway, or private entrance is claimed unless "
                "future source data explicitly proves it."
            ),
        },
        "sources": sources,
        "coverage": coverage_summary(approaches),
        "approaches": approaches,
    }


def collect_targets() -> list[FacilityTarget]:
    # Read endpoints and local approaches through the world so their keys are
    # remapped onto current slug facility ids (the checked-in files may still
    # carry pre-slug keys); facilities the data files miss are skipped rather
    # than crashing the batch.
    world = get_world()
    targets: list[FacilityTarget] = []
    for city_name in world.city_names():
        city = world.city(city_name)
        for location in city.locations:
            endpoint = world.facility_endpoint(city_name, location.name)
            approach = world.facility_approach(city_name, location.name)
            if endpoint is None or approach is None:
                continue
            targets.append(
                FacilityTarget(
                    facility_id=location.id,
                    city=city_name,
                    state=city.state,
                    facility_name=location.name,
                    facility_type=location.type,
                    endpoint_name=endpoint.endpoint_name,
                    lat=endpoint.lat,
                    lon=endpoint.lon,
                    start_lat=city.lat,
                    start_lon=city.lon,
                    endpoint_source_backed=endpoint.source_backed,
                    endpoint_fallback=endpoint.fallback,
                    endpoint_source_note=endpoint.source_note,
                    local_approach_miles=approach.approach_miles,
                    local_approach_road=approach.road,
                )
            )
    return targets


def _geometry_target(local_geometry, target: FacilityTarget):
    return local_geometry.Target(
        target_id=target.facility_id,
        target_type="facility",
        city=target.city,
        state=target.state,
        name=target.endpoint_name,
        lat=target.lat,
        lon=target.lon,
        start_lat=target.start_lat,
        start_lon=target.start_lon,
        role=target.facility_type,
        estimated=False,
        fallback_reason="",
        approach_road=target.local_approach_road,
        approach_miles=target.local_approach_miles,
        source_note=target.endpoint_source_note,
    )


def approach_record(
    target: FacilityTarget,
    geometry,
    state_set: set[str],
) -> dict[str, Any]:
    too_short = geometry is not None and (
        geometry.miles <= MIN_CHAIN_ROUTE_MI
        or (geometry.miles <= MIN_PLAYABLE_ROUTE_MI and len(geometry.segments) < 2)
    )
    turn_level = geometry is not None and not too_short
    reason = fallback_reason(target, state_set, turn_level)
    if too_short:
        reason = "Public-road path is shorter than the playable facility approach floor."
    segments = (
        list(geometry.segments)
        if turn_level
        else [
            {
                "road": target.local_approach_road or "local facility access road",
                "miles": round(max(target.local_approach_miles, 0.4), 2),
                "cue": (
                    f"Use {target.local_approach_road or 'the local facility access road'} "
                    "for the facility approach."
                ),
                "speed_mph": 25.0,
            }
        ]
    )
    cleaned = [clean_segment(segment) for segment in segments]
    return {
        "target_type": "facility",
        "facility_id": target.facility_id,
        "city": target.city,
        "state": target.state,
        "facility_name": target.facility_name,
        "facility_type": target.facility_type,
        "endpoint_name": target.endpoint_name,
        "endpoint_source_backed": target.endpoint_source_backed,
        "road_snapped": geometry is not None,
        "turn_level": turn_level,
        "source_type": "osm_local_road_graph" if turn_level else "facility_approach_fallback",
        "estimated": not turn_level,
        "fallback": not turn_level,
        "fallback_reason": reason,
        "nearest_road_context": geometry is not None,
        "representative_fallback": target.endpoint_fallback,
        "gate_hint": False,
        "yard_hint": False,
        "dock_hint": False,
        "total_miles": round(geometry.miles if turn_level else target.local_approach_miles, 2),
        "approach_road": cleaned[0]["road"],
        "segments": cleaned,
        "final_hint": (
            "Route reaches the sourced facility vicinity; final gate, yard, dock, "
            "and driveway are not source-backed."
            if turn_level
            else "Facility approach uses fallback road context; final gate, yard, dock, "
            "and driveway are not source-backed."
        ),
        "source_note": target.endpoint_source_note,
    }


def fallback_reason(target: FacilityTarget, state_set: set[str], turn_level: bool) -> str:
    if turn_level:
        return ""
    if not target.endpoint_source_backed or target.endpoint_fallback:
        return (
            "Facility endpoint is representative fallback, so source-backed routing is not claimed."
        )
    if target.state not in state_set:
        return "Source-backed endpoint is outside this bounded Midwest road-snap batch."
    if target.facility_type not in HIGH_CONFIDENCE_TYPES:
        return "Facility type was outside the high-confidence road-snap category set."
    if target.local_approach_miles > MAX_ROUTE_MI:
        return "Facility is beyond the bounded local route distance for this pass."
    return "No connected public-road path was found between the city context and sourced endpoint."


def clean_segment(segment: dict[str, Any]) -> dict[str, Any]:
    road = clean_text(str(segment["road"])) or "unnamed public road"
    cue = clean_text(str(segment["cue"])) or f"Use {road} for the facility approach."
    return {
        "road": road,
        "miles": round(float(segment["miles"]), 2),
        "cue": cue,
        "speed_mph": float(segment.get("speed_mph", 25.0)),
    }


def clean_text(value: str) -> str:
    text = " ".join(str(value).split()).strip()
    lowered = text.lower()
    if any(marker in lowered for marker in RAW_MARKERS):
        return ""
    return text


def coverage_summary(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "facilities": len(records),
        "source_backed_endpoints": sum(
            1 for item in records.values() if item["endpoint_source_backed"]
        ),
        "road_snapped": sum(1 for item in records.values() if item["road_snapped"]),
        "turn_level": sum(1 for item in records.values() if item["turn_level"]),
        "nearest_road_fallback": sum(
            1
            for item in records.values()
            if item["endpoint_source_backed"] and not item["road_snapped"]
        ),
        "representative_fallback": sum(
            1 for item in records.values() if item["representative_fallback"]
        ),
        "gate_yard_dock_hints": sum(
            1
            for item in records.values()
            if item["gate_hint"] or item["yard_hint"] or item["dock_hint"]
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=FACILITY_APPROACHES_PATH)
    parser.add_argument("--states", nargs="*", default=list(DEFAULT_STATES))
    parser.add_argument("--max-route-mi", type=float, default=MAX_ROUTE_MI)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    payload = build_facility_approaches(
        args.cache_dir,
        states=tuple(args.states),
        max_route_mi=args.max_route_mi,
    )
    print(json.dumps(payload["coverage"], indent=2, sort_keys=True))
    if args.write:
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
