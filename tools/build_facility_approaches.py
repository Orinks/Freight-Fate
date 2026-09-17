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

A chain belongs to the endpoint it was routed to. When the endpoint re-sweep
(``build_facility_endpoints``) has REPLACED a facility's endpoint, the chain
is rebuilt toward the new one and the fresh chain wins. If the rebuild finds
no path the old streets stay (owner ruling, 2026-09-17: a chain is kept until
one replaces it) but the row says so: ``stale_endpoint`` names the endpoint
the streets still lead to and why the rebuild failed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from freight_fate.data.world import get_world

sys.path.insert(0, str(Path(__file__).resolve().parent))
from facility_endpoint_screen import NAME_MATCHED_TYPES, screen_endpoint  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
FACILITY_ENDPOINTS_PATH = ROOT / "src" / "freight_fate" / "data" / "facility_endpoints.json"
LOCAL_APPROACHES_PATH = ROOT / "src" / "freight_fate" / "data" / "local_approaches.json"
FACILITY_APPROACHES_PATH = ROOT / "src" / "freight_fate" / "data" / "facility_approaches.json"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "freight-fate-osm" / "regions"
ACCESSED_DATE = "2026-06-27"
DEFAULT_STATES = ("Illinois", "Indiana", "Ohio")
MAX_ROUTE_MI = 18.0
EARTH_RADIUS_MI = 3958.7613
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
#
# 2026-09-17: those three now route when the endpoint screen is on (the
# default), because the screen is the stricter rule they were waiting for: it
# reads the endpoint's own OSM tags and wants the trade stated by tag or by a
# whole word in the name. 45 of their 193 sourced endpoints pass. With
# `--no-endpoint-screen` they stay out, as before.
#
# 2026-09-17, after the endpoint re-sweep: the sibling types of the set above
# (an "intermodal" or "rail" facility is an intermodal ramp by another name,
# "manufacturing" a manufacturing plant) route on the same terms. They were
# left out because nobody trusted their endpoints; the screen is that trust.
SCREENED_SIBLING_TYPES = frozenset(
    {"air_cargo", "food_terminal", "industrial_park", "intermodal", "manufacturing", "rail"}
)
SCREEN_REFUSAL_PREFIX = "Sourced endpoint failed the freight-site screen: "


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
    # `node/123` or `way/456`: the OSM object the endpoint sweep matched.
    endpoint_source_ref: str = ""


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
    endpoint_screen: bool = True,
) -> dict[str, Any]:
    """Route the batch and return the payload to write.

    With ``endpoint_screen`` (the default) a target is only routed when its
    endpoint's own OSM object reads as a freight site; see
    ``facility_endpoint_screen``. A refused target is still an attempted one:
    its row takes the refusal as its fallback reason.

    With ``existing`` (the checked-in payload) the result is a merge: only
    facilities this run attempted, or found new geometry for, change; see
    :func:`merge_existing` for the rules. Without it the payload is a whole
    rebuild in which every facility outside the batch is a fallback record.
    """
    local_geometry = _load_local_geometry_tool()
    targets = collect_targets()
    state_set = set(states)
    eligible_types = HIGH_CONFIDENCE_TYPES | (
        NAME_MATCHED_TYPES | SCREENED_SIBLING_TYPES if endpoint_screen else set()
    )
    routable = [
        target
        for target in targets
        if target.endpoint_source_backed
        and not target.endpoint_fallback
        and target.state in state_set
        and target.facility_type in eligible_types
        and routed_approach_miles(target) <= max_route_mi
    ]
    routed: dict[str, Any] = {}
    # Why each unrouted target failed, straight from the path search.
    failures: dict[str, str] = {}
    # Facilities a state extract was actually searched for; a missing extract
    # leaves its state's facilities unattempted so a merge keeps their rows.
    attempted: set[str] = set()
    sources: list[dict[str, Any]] = []
    for state_index, state in enumerate(states, start=1):
        extract = local_geometry.state_extract_path(cache_dir, state)
        sources.append(local_geometry.source_record(state, extract))
        in_state = [target for target in routable if target.state == state]
        refused = 0
        if extract.exists() and in_state and endpoint_screen:
            tags = local_geometry.read_object_tags(
                extract, {target.endpoint_source_ref for target in in_state}
            )
            passed = []
            for target in in_state:
                accepted, why = screen_endpoint(
                    target.facility_type,
                    target.endpoint_name,
                    tags.get(target.endpoint_source_ref),
                )
                if accepted:
                    passed.append(target)
                else:
                    attempted.add(target.facility_id)
                    failures[target.facility_id] = SCREEN_REFUSAL_PREFIX + why
            refused = len(in_state) - len(passed)
            in_state = passed
        state_targets = [_geometry_target(local_geometry, target) for target in in_state]
        print(
            f"[{state_index}/{len(states)}] {state}: {len(state_targets)} routable targets"
            + (f", {refused} refused by the endpoint screen" if endpoint_screen else "")
            + ("" if extract.exists() else " (extract missing, skipped)"),
            flush=True,
        )
        if extract.exists() and state_targets:
            attempted.update(target.target_id for target in state_targets)
            routed.update(local_geometry.route_state_targets(extract, state_targets, failures))

    approaches = {
        target.facility_id: approach_record(
            target,
            routed.get(target.facility_id),
            state_set,
            failures.get(target.facility_id, ""),
        )
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
    the fresh record, which is also how a chain whose endpoint the re-sweep
    replaced gets rebuilt; a prior turn-level chain the batch could not better
    is kept (so ``turn_level`` never falls below the base file), and when its
    endpoint has been replaced and the batch tried and failed to reach the new
    one it is kept WITH a ``stale_endpoint`` note (:func:`chain_is_current`); a
    facility the batch attempted and still could not route takes the fresh
    fallback, whose reason is this run's real routing outcome (so does a
    chainless row whose endpoint changed); anything else keeps its prior
    record untouched, which is what protects the estimated-near-city
    residuals and every state outside the batch. Facilities the world no
    longer knows drop, as in a whole rebuild. ``generated`` keeps every prior
    key the batch does not own (``regeocode_far_pins`` included), the state
    list becomes the union, and ``merge`` records what the batch did.
    """
    prior = existing.get("approaches") or {}
    batch_state_set = set(fresh["generated"]["states"])
    summary = {"new_geometry": 0, "kept_turn_level": 0, "refreshed": 0, "kept": 0, "added": 0}
    rebuilt = stale = 0
    approaches: dict[str, Any] = {}
    for facility_id, record in fresh["approaches"].items():
        old = prior.get(facility_id)
        if old is None:
            approaches[facility_id] = record
            summary["added"] += 1
        elif record["turn_level"]:
            approaches[facility_id] = record
            summary["new_geometry"] += 1
            if old.get("turn_level") and not chain_is_current(old, record):
                rebuilt += 1
        elif old.get("turn_level"):
            if facility_id in attempted and not chain_is_current(old, record):
                old = {
                    **old,
                    "stale_endpoint": {
                        "leads_to": old.get("endpoint_name", ""),
                        "endpoint_now": record.get("endpoint_name", ""),
                        "rebuild_failed": record.get("fallback_reason", ""),
                        "accessed": accessed,
                    },
                }
                stale += 1
            approaches[facility_id] = old
            summary["kept_turn_level"] += 1
        elif facility_id in attempted or (
            record.get("state") in batch_state_set
            and record.get("endpoint_source_backed")
            and old.get("endpoint_name") != record.get("endpoint_name")
        ):
            # Tried and failed, or a chainless row of a type this tool does
            # not route whose endpoint the re-sweep has since replaced.
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
    if rebuilt or stale:
        # Only a batch that met a re-swept endpoint reports these.
        generated["merge"]["rebuilt_to_new_endpoint"] = rebuilt
        generated["merge"]["stale_chain_kept"] = stale

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


def chain_is_current(old: dict[str, Any], fresh: dict[str, Any]) -> bool:
    """Whether the prior chain was routed to the endpoint the facility has
    NOW. READ from the two rows: a row copies its endpoint's name and source
    note when it is built, and the endpoint re-sweep rewrites both when it
    replaces an endpoint (and neither when it keeps or merely labels one)."""
    return old.get("endpoint_name") == fresh.get("endpoint_name") and old.get(
        "source_note"
    ) == fresh.get("source_note")


def shared_turn_level(existing: dict[str, Any], merged: dict[str, Any]) -> tuple[int, int]:
    """Turn-level counts before and after a merge over the facilities both
    payloads know, so a facility the world retired does not read as a lost
    chain."""
    prior = existing.get("approaches") or {}
    rows = merged.get("approaches") or {}
    shared = prior.keys() & rows.keys()
    before = sum(1 for facility_id in shared if prior[facility_id].get("turn_level"))
    after = sum(1 for facility_id in shared if rows[facility_id].get("turn_level"))
    return before, after


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
                    endpoint_source_ref=endpoint.source_ref,
                )
            )
    return targets


def routed_approach_miles(target: FacilityTarget) -> float:
    """Expected road miles from the city context to the point being ROUTED TO.

    DERIVED: straight line from the city context to the source-backed
    endpoint times 1.25, the detour factor `build_local_approaches` and
    `build_facility_endpoints` both use. It sizes the path search
    (`shortest_geometry` gives up past 1.8 times this) and the
    `--max-route-mi` gate.

    Until 2026-09-17 both read `local_approach_miles`, which is measured to
    the facility's REPRESENTATIVE pin. That pin sits near the city centre, so
    the figure was the 2.1-mile floor and the search stopped at 3.78 road
    miles while the endpoint it was routing to lay three to seven miles out.
    It was the largest single cause of "no connected public-road path": 52 of
    88 such failures in California, New York and Texas had a path and ran out
    of budget. The representative figure is kept as a lower bound so a
    facility routed before the fix is searched at least as far as it was.
    """
    straight_line = _haversine_mi(target.start_lat, target.start_lon, target.lat, target.lon)
    to_endpoint = round(min(35.0, straight_line * 1.25), 1)
    return max(to_endpoint, target.local_approach_miles)


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(a))


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
        approach_miles=routed_approach_miles(target),
        source_note=target.endpoint_source_note,
    )


def approach_record(
    target: FacilityTarget,
    geometry,
    state_set: set[str],
    route_failure: str = "",
) -> dict[str, Any]:
    too_short = geometry is not None and (
        geometry.miles <= MIN_CHAIN_ROUTE_MI
        or (geometry.miles <= MIN_PLAYABLE_ROUTE_MI and len(geometry.segments) < 2)
    )
    turn_level = geometry is not None and not too_short
    reason = fallback_reason(target, state_set, turn_level, route_failure)
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


# One sentence per way the path search can come back empty (the codes are
# `build_local_geometry.ROUTE_FAILURE_*`). Read from the search, not assumed.
ROUTE_FAILURE_REASONS = {
    "no_start_road": "No public road was found near the city context in the local extract.",
    "no_target_road": (
        "No public surface road was found within the snap distance of the sourced endpoint."
    ),
    "over_budget": (
        "A public-road path to the sourced endpoint exists but is longer than the "
        "bounded search for a facility at this distance."
    ),
    "disconnected": (
        "The roads at the sourced endpoint do not join the city context over public "
        "surface roads; a private yard road, a motorway or water lies between."
    ),
}


def fallback_reason(
    target: FacilityTarget,
    state_set: set[str],
    turn_level: bool,
    route_failure: str = "",
) -> str:
    if turn_level:
        return ""
    if not target.endpoint_source_backed or target.endpoint_fallback:
        return (
            "Facility endpoint is representative fallback, so source-backed routing is not claimed."
        )
    if target.state not in state_set:
        return "Source-backed endpoint is outside this bounded Midwest road-snap batch."
    if route_failure.startswith(SCREEN_REFUSAL_PREFIX):
        return f"{route_failure} A street chain to it is not claimed."
    if target.facility_type not in (
        HIGH_CONFIDENCE_TYPES | NAME_MATCHED_TYPES | SCREENED_SIBLING_TYPES
    ):
        return "Facility type was outside the high-confidence road-snap category set."
    if routed_approach_miles(target) > MAX_ROUTE_MI:
        return "Facility is beyond the bounded local route distance for this pass."
    return ROUTE_FAILURE_REASONS.get(
        route_failure,
        "No connected public-road path was found between the city context and sourced endpoint.",
    )


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
        # Sourced endpoints the freight-site screen would not route to: the
        # share of "source-backed" that is a railway line, a substation, a shop.
        "endpoint_screen_refused": sum(
            1
            for item in records.values()
            if str(item.get("fallback_reason", "")).startswith(SCREEN_REFUSAL_PREFIX)
        ),
        "representative_fallback": sum(
            1 for item in records.values() if item["representative_fallback"]
        ),
        # Chains still leading to an endpoint the re-sweep replaced, because
        # no path to the new endpoint was found.
        "stale_chain_kept": sum(1 for item in records.values() if item.get("stale_endpoint")),
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
    parser.add_argument(
        "--endpoint-screen",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Route only to endpoints whose own OSM tags read as a freight site "
            "(default on; off restores the pre-2026-09-17 behaviour)"
        ),
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
        endpoint_screen=args.endpoint_screen,
    )
    if existing is not None:
        print("Merge:", json.dumps(payload["generated"]["merge"], sort_keys=True), flush=True)
        before = int((existing.get("coverage") or {}).get("turn_level") or 0)
        after = payload["coverage"]["turn_level"]
        print(f"turn_level {before} -> {after}", flush=True)
        kept_before, kept_after = shared_turn_level(existing, payload)
        if kept_after < kept_before:
            # merge_existing keeps every prior chain a facility still has, so
            # this cannot happen; refusing to write is cheaper than shipping a
            # silent regression. (A raw count can drop legitimately when the
            # world retires a facility, hence the shared-facility comparison.)
            print("Refusing to write: a facility lost its turn-level chain in the merge.")
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
