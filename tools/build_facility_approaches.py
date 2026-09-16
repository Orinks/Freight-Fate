r"""Build bounded source-backed freight facility approach geometry.

Runtime gameplay reads ``facility_approaches.json`` offline. This tool is
build-time only and uses local OSM extracts; it never calls live routing APIs.

Example:
    uv run --group tooling python tools/build_facility_approaches.py \
      --cache-dir C:\Users\joshu\.cache\freight-fate-osm\regions --write

Batches merge by default (``--merge-existing``): the checked-in file is the
base, and a run over a few states can only add or refresh what it actually
routed. A turn-level chain is never replaced by a fallback, a facility this
run did not attempt keeps its record byte for byte (so the estimated-near-city
residuals from the far-pin regeocode keep their honest reason), and the
``generated.regeocode_far_pins`` block survives. ``--no-merge-existing``
is the old whole-file rebuild.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
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
    "cold_storage",
    "company_yard",
    "cross_dock",
    "distribution",
    "dry_warehouse",
    "farm_elevator",
    "food_processor",
    "grocery_retail_dc",
    "intermodal_ramp",
    "manufacturing_plant",
    "parcel_hub",
    "port",
    "port_terminal",
    "terminal",
    "warehouse",
}
# Widened 2026-09-16 after reading the type-excluded endpoint names: cold
# storage, food processors, grocery DCs and grain elevators name the
# business they are (Americold, Dot Foods, US Foods). Ports are in on the
# roadmap's say-so, though a share of their endpoints are rail subdivisions
# and transit terminals the endpoint sweep matched on "terminal". Left out on
# purpose: steel_industrial, automotive_plant and chemical_petroleum_terminal,
# whose endpoints were matched by name substring ("Steele Street", "Assembly
# of God", "Refinery Ballpark") -- a confident street chain to the wrong door
# is worse than the fallback. Widen those after the endpoint re-sweep.


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
    existing: dict[str, Any] | None = None,
    accessed: str = ACCESSED_DATE,
) -> dict[str, Any]:
    """Route the batch and return the payload to write.

    With ``existing`` (the checked-in payload) the result is a merge: only
    facilities this run attempted, or found new geometry for, change; see
    :func:`merge_existing` for the rules. Without it the payload is a whole
    rebuild in which every facility outside the batch is a fallback record.
    """
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
    # Facilities a state extract was actually searched for; a missing extract
    # leaves its state's facilities unattempted so a merge keeps their rows.
    attempted: set[str] = set()
    sources: list[dict[str, Any]] = []
    for state_index, state in enumerate(states, start=1):
        extract = local_geometry.state_extract_path(cache_dir, state)
        sources.append(local_geometry.source_record(state, extract))
        state_targets = [
            _geometry_target(local_geometry, target) for target in routable if target.state == state
        ]
        print(
            f"[{state_index}/{len(states)}] {state}: {len(state_targets)} routable targets"
            + ("" if extract.exists() else " (extract missing, skipped)"),
            flush=True,
        )
        if extract.exists() and state_targets:
            attempted.update(target.target_id for target in state_targets)
            routed.update(local_geometry.route_state_targets(extract, state_targets))

    approaches = {
        target.facility_id: approach_record(target, routed.get(target.facility_id), state_set)
        for target in targets
    }
    payload = {
        "version": 1,
        "generated": {
            "accessed": accessed,
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
    if existing is None:
        return payload
    return merge_existing(existing, payload, attempted, accessed=accessed)


def merge_existing(
    existing: dict[str, Any],
    fresh: dict[str, Any],
    attempted: set[str],
    *,
    accessed: str = ACCESSED_DATE,
) -> dict[str, Any]:
    """Fold a batch payload into the checked-in one without losing chains.

    Per facility, in order: a facility the batch routed to turn level takes
    the fresh record; a prior turn-level chain the batch could not better is
    kept (so ``turn_level`` never falls below the base file); a facility the
    batch attempted and still could not route takes the fresh fallback, whose
    reason is this run's real routing outcome; anything else keeps its prior
    record untouched, which is what protects the estimated-near-city
    residuals and every state outside the batch. Facilities the world no
    longer knows drop, as in a whole rebuild. ``generated`` keeps every prior
    key the batch does not own (``regeocode_far_pins`` included), the state
    list becomes the union, and ``merge`` records what the batch did.
    """
    prior = existing.get("approaches") or {}
    summary = {"new_geometry": 0, "kept_turn_level": 0, "refreshed": 0, "kept": 0, "added": 0}
    approaches: dict[str, Any] = {}
    for facility_id, record in fresh["approaches"].items():
        old = prior.get(facility_id)
        if old is None:
            approaches[facility_id] = record
            summary["added"] += 1
        elif record["turn_level"]:
            approaches[facility_id] = record
            summary["new_geometry"] += 1
        elif old.get("turn_level"):
            approaches[facility_id] = old
            summary["kept_turn_level"] += 1
        elif facility_id in attempted:
            approaches[facility_id] = record
            summary["refreshed"] += 1
        else:
            approaches[facility_id] = old
            summary["kept"] += 1

    batch_states = list(fresh["generated"]["states"])
    generated = dict(existing.get("generated") or {})
    for key in ("family", "source_policy", "road_policy", "gate_policy", "max_route_mi"):
        generated[key] = fresh["generated"][key]
    generated["states"] = sorted(set(generated.get("states") or []) | set(batch_states))
    generated["merge"] = {"accessed": accessed, "batch_states": batch_states, **summary}

    batch_state_set = set(batch_states)
    sources = [
        source
        for source in existing.get("sources") or []
        if source.get("state") not in batch_state_set
    ] + list(fresh["sources"])
    sources.sort(key=lambda source: str(source.get("state", "")))

    return {
        "version": fresh["version"],
        "generated": generated,
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
    # Inherited from build_local_geometry, which decides the wording; a
    # blank here means the segment carried no road at all.
    road = clean_text(str(segment["road"])) or "a side street"
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
    parser.add_argument(
        "--merge-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Fold this batch into --existing instead of rebuilding the whole file "
            "(default on; a batch can then only add or refresh what it routed)"
        ),
    )
    parser.add_argument(
        "--existing",
        type=Path,
        default=FACILITY_APPROACHES_PATH,
        help="Base payload for --merge-existing (default: the checked-in file)",
    )
    parser.add_argument(
        "--accessed",
        default=time.strftime("%Y-%m-%d"),
        help="Date stamped on this batch (default: today)",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    existing = None
    if args.merge_existing and args.existing.exists():
        existing = json.loads(args.existing.read_text(encoding="utf-8"))
        print("Coverage before (base file):", flush=True)
        print(json.dumps(existing.get("coverage") or {}, indent=2, sort_keys=True))
    elif args.merge_existing:
        print(f"No base file at {args.existing}; building the whole file.", flush=True)

    payload = build_facility_approaches(
        args.cache_dir,
        states=tuple(args.states),
        max_route_mi=args.max_route_mi,
        existing=existing,
        accessed=args.accessed,
    )
    if existing is not None:
        print("Merge:", json.dumps(payload["generated"]["merge"], sort_keys=True), flush=True)
        before = int((existing.get("coverage") or {}).get("turn_level") or 0)
        after = payload["coverage"]["turn_level"]
        print(f"turn_level {before} -> {after}", flush=True)
        if after < before:
            # merge_existing keeps every prior chain, so this cannot happen;
            # refusing to write is cheaper than shipping a silent regression.
            print("Refusing to write: merged turn_level fell below the base file.", flush=True)
            return 1
        print("Coverage after (merged):", flush=True)
    print(json.dumps(payload["coverage"], indent=2, sort_keys=True))
    if args.write:
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
