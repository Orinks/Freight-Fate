r"""Bake the streets from an exit's ramp terminal to a road stop's driveway.

Owner order (2026-09-24, via the lead): a truck stop, travel center or fuel
station off an exit is reached by turning at the ramp's end, driving a short
stretch of the crossroad and turning into the lot. The game had no record of
that stretch, so the lot entrance sat at the end of the ramp.

For every stop whose serving interchange the stop snap already decided
(``interchange_mi``, ``tools/snap_stops_to_interchanges.py``) and whose
coordinates were READ (not an opposite-direction copy's mile marker), a
chain is routed from each ramp terminal that exit has (``ramp_terminal_*``,
per direction) to the stop, with the same street detail as the facility
chains (``street_chain.py``: limit and its kind, controls, driveway). It is
written on the stop as ``approach_chains``, one per terminal, whole.

Stops sitting ON the mainline -- rest areas, weigh stations, turnpike
service plazas, whose ramp leads straight into the lot -- get no chain, told
apart two ways: the stop snap links no exit to them (every public rest area
and weigh station in the data), and, where it did, a route from the terminal
that never touches a public street is a ramp into the lot, recorded as the
failure ``on_mainline``.

    uv run --group tooling python tools/build_stop_approaches.py --states Iowa
    uv run --group tooling python tools/build_stop_approaches.py --write
    uv run --group tooling python tools/build_stop_approaches.py --only "a->b;c->d" --write
    uv run python tools/index_world.py

``--only`` rebakes the stops on some legs (after their exits were
re-derived); every stop on them is judged afresh, so one whose exit moved or
lost its ramp terminal loses the chain it had.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import street_chain  # noqa: E402
from build_interchanges_base import select_only  # noqa: E402
from snap_stops_to_interchanges import fabricated_coordinates  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "freight-fate-osm" / "regions"
# The longest terminal-to-stop search. A stop a snapped exit "serves" from
# further than the facility chains' own limit is not served by it.
MAX_ROUTE_MI = 18.0
ON_MAINLINE = "on_mainline"
APPROACH_SOURCE = (
    "derived: routed over the local OpenStreetMap extract from this exit's ramp "
    "terminal node (read) to the stop's read coordinates; per-street limit, "
    "controls and driveway as in facility_approaches.json generated.street_sources"
)


def _local_geometry():
    path = ROOT / "tools" / "build_local_geometry.py"
    spec = importlib.util.spec_from_file_location("build_local_geometry", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def state_at(leg: dict[str, Any], at_mi: float) -> str:
    """The state a leg-frame mile lies in, by the leg's state mileage."""
    run = 0.0
    rows = leg.get("corridor", {}).get("state_miles") or []
    for row in rows:
        run += float(row["miles"])
        if at_mi <= run:
            return str(row["state"])
    return str(rows[-1]["state"]) if rows else ""


def stop_targets(legs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """One work item per stop that can have a chain, and why the rest cannot."""
    fabricated = fabricated_coordinates(legs)
    counts: dict[str, int] = defaultdict(int)
    work = []
    for leg_i, leg in enumerate(legs):
        by_mi = {
            round(float(ix["at_mi"]), 6): ix
            for ix in leg.get("corridor", {}).get("interchanges") or []
        }
        for stop_i, stop in enumerate(leg.get("stops") or []):
            counts["stops"] += 1
            if "interchange_mi" not in stop:
                counts["no_serving_exit"] += 1
                continue
            if "lat" not in stop or id(stop) in fabricated:
                counts["no_read_coordinates"] += 1
                continue
            ix = by_mi.get(round(float(stop["interchange_mi"]), 6))
            terminals = [
                {**ix[f"ramp_terminal_{d}"], "exit": {"direction": d}}
                for d in ("forward", "backward")
                if ix and ix.get(f"ramp_terminal_{d}")
            ]
            if not terminals:
                counts["exit_has_no_terminal"] += 1
                continue
            work.append(
                {
                    "leg": leg_i,
                    "stop": stop_i,
                    "state": state_at(leg, float(stop["at_mi"])),
                    "lat": float(stop["lat"]),
                    "lon": float(stop["lon"]),
                    "name": str(stop["name"]),
                    "terminals": terminals,
                }
            )
    return work, dict(counts)


def route_stops(
    cache_dir: Path,
    work: list[dict[str, Any]],
    states: set[str] | None,
    town_judge: street_chain.TownJudge | None = None,
) -> dict[tuple[int, int], dict[str, Any]]:
    """(leg, stop) -> ``approach_chains``/``approach_chains_failed`` fields.

    ``town_judge`` None is the real bake: built from the Census boundaries,
    and refused without them (``street_chain.census_town_judge``)."""
    town_judge = town_judge or street_chain.census_town_judge()
    lg = _local_geometry()
    by_state: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in work:
        if states is None or item["state"] in states:
            by_state[item["state"]].append(item)
    out: dict[tuple[int, int], dict[str, Any]] = {}
    for n, (state, items) in enumerate(sorted(by_state.items()), start=1):
        extract = lg.state_extract_path(cache_dir, state)
        print(f"[{n}/{len(by_state)}] {state}: {len(items)} stops", flush=True)
        if not extract.exists():
            continue
        targets, starts = [], {}
        for item in items:
            target_id = f"{item['leg']}:{item['stop']}"
            first = item["terminals"][0]
            targets.append(
                lg.Target(
                    target_id=target_id,
                    target_type="road_stop",
                    city="",
                    state=state,
                    name=item["name"],
                    lat=item["lat"],
                    lon=item["lon"],
                    start_lat=first["lat"],
                    start_lon=first["lon"],
                    role="road_stop",
                    estimated=False,
                    fallback_reason="",
                    approach_road="",
                    approach_miles=0.0,
                    source_note="",
                )
            )
            starts[target_id] = street_chain.exit_starts(
                item["lat"], item["lon"], item["terminals"], MAX_ROUTE_MI
            )
        exit_routes: dict[tuple[str, int], Any] = {}
        lg.route_state_targets(
            extract,
            targets,
            {},
            yard_roads=True,
            street_detail=True,
            exit_starts=starts,
            exit_routes=exit_routes,
            town_judge=town_judge,
        )
        for item in items:
            target_id = f"{item['leg']}:{item['stop']}"
            fields = street_chain.exit_chain_records(
                target_id, item["terminals"], exit_routes, _clean, float("inf")
            )
            chains = []
            for chain in fields["exit_chains"]:
                if not chain["street_counts"].get("street_edges"):
                    fields["exit_chains_failed"].append(
                        {"terminal_node": chain["terminal_node"], "route_failure": ON_MAINLINE}
                    )
                    continue
                chains.append(chain)
            out[(item["leg"], item["stop"])] = {
                "approach_chains": chains,
                "approach_chains_failed": fields["exit_chains_failed"],
            }
    return out


def _clean(segment: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "road",
        "miles",
        "cue",
        "speed_mph",
        "turn_deg",
        "limit_mph",
        "limit_source",
        "limit_basis",
    )
    out = {key: segment[key] for key in keys if key in segment}
    out["miles"] = round(float(out["miles"]), 2)
    out["turn_deg"] = round(float(out.get("turn_deg", 0.0)), 1)
    out["controls"] = segment.get("controls") or []
    return out


def meta(legs: list[dict[str, Any]], counts: dict[str, int]) -> dict[str, Any]:
    by_type: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    failed: dict[str, int] = defaultdict(int)
    chains = with_driveway = 0
    for leg in legs:
        for stop in leg.get("stops") or []:
            row = by_type[str(stop.get("type"))]
            row["stops"] += 1
            if stop.get("approach_chains"):
                row["with_chain"] += 1
            for chain in stop.get("approach_chains") or []:
                chains += 1
                with_driveway += 1 if chain.get("driveway") else 0
            for miss in stop.get("approach_chains_failed") or []:
                failed[miss["route_failure"] or "unknown"] += 1
    return {
        "kind": "derived",
        "source": APPROACH_SOURCE,
        "stops": counts,
        "chains": chains,
        "chains_with_driveway": with_driveway,
        "terminals_failed": dict(sorted(failed.items())),
        "by_type": {k: dict(v) for k, v in sorted(by_type.items())},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--states", nargs="*", default=None)
    parser.add_argument(
        "--only", default="", help="legs to rebake, 'from_slug->to_slug;...' (default all)"
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    data = load_world()
    legs = data["legs"]
    in_scope = {id(leg) for leg in (select_only(legs, args.only) if args.only else legs)}
    states = set(args.states) if args.states else None
    work, counts = stop_targets(legs)
    work = [item for item in work if id(legs[item["leg"]]) in in_scope]
    print(f"{len(work)} stops routable; {counts}", flush=True)
    found = route_stops(args.cache_dir, work, states)
    # Every stop in scope is judged afresh: one whose exit moved, or lost its
    # ramp terminal, must not keep a chain from a ramp that is not there.
    extract_exists = _local_geometry().state_extract_path
    for leg in legs:
        if id(leg) not in in_scope:
            continue
        for stop in leg.get("stops") or []:
            state = state_at(leg, float(stop["at_mi"]))
            if states is not None and state not in states:
                continue
            if extract_exists(args.cache_dir, state).exists():
                for key in ("approach_chains", "approach_chains_failed", "approach_source"):
                    stop.pop(key, None)
    for (leg_i, stop_i), fields in found.items():
        stop = legs[leg_i]["stops"][stop_i]
        for key in ("approach_chains", "approach_chains_failed", "approach_source"):
            stop.pop(key, None)
        if fields["approach_chains"]:
            stop["approach_chains"] = fields["approach_chains"]
            stop["approach_source"] = APPROACH_SOURCE
        if fields["approach_chains_failed"]:
            stop["approach_chains_failed"] = fields["approach_chains_failed"]
    data["stop_approach_bake"] = meta(legs, counts)
    print(data["stop_approach_bake"], flush=True)
    if args.write:
        save_world(data)
        print("wrote the world source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
