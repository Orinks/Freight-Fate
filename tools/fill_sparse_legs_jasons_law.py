"""Give long legs with no truck-usable stop a real, verified place to pull in.

After the access sweep and the Overpass gap fill, a handful of long legs still
carry no stop a combination vehicle can enter. Their existing stops are all
``bobtail_only`` -- untagged rural fuel that a 70-foot rig has no business
pulling into.

The instinct is to designate one anyway so the route is playable. This tries
the honest source first: the FHWA "Jason's Law" truck-parking inventory, an
official federal survey of real public truck parking with counted spaces,
published as NTAD via BTS. It exists because Jason Rivenburg was murdered in
2009 at an abandoned South Carolina gas station -- the only place left to park
when a receiver would not let him wait on their property. Using it to make sure
players always have a legal place to stop is the point of the law.

Unlike ``curate_route_pois.py``, which fills legs that are under POI DENSITY,
this targets legs that are under truck ACCESS: they may have several stops and
still leave a driver with nowhere to go. That distinction is why the existing
pass reported nothing to do here.

Whatever this cannot close is reported, and left alone. Designating a stop that
does not exist is a decision for the owner and Josh, not for a tool.

Usage::

    uv run python tools/fill_sparse_legs_jasons_law.py --min-miles 100 --report
    uv run python tools/fill_sparse_legs_jasons_law.py --min-miles 100 --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from curate_route_pois import (
    _project_candidate,
    fetch_jasons_law_candidates,
    fetch_loves_candidates,
    fetch_pilot_candidates,
)
from world_source import load_world, save_world

ROOT = Path(__file__).resolve().parents[1]
ACCESSED_DATE = "2026-07-19"

# How far off the corridor a surveyed facility may sit and still count as a
# stop on this leg. The enrichment recipe's placement gate is 2 miles; keep it.
MAX_OFFSET_MI = 2.0


def usable_stops(leg: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        stop
        for stop in leg.get("stops", [])
        if str(stop.get("vehicle_access", "tractor_trailer")) == "tractor_trailer"
    ]


def target_legs(data: dict[str, Any], min_miles: float) -> list[dict[str, Any]]:
    return [
        leg
        for leg in data["legs"]
        if float(leg.get("miles", 0.0) or 0.0) >= min_miles and not usable_stops(leg)
    ]


def fill(leg: dict[str, Any], candidates: list[Any], per_leg: int) -> list[dict[str, Any]]:
    miles = float(leg.get("miles", 0.0) or 0.0)
    taken = [float(s.get("at_mi", 0.0)) for s in leg.get("stops", [])]
    names = {str(s.get("name", "")).strip().lower() for s in leg.get("stops", [])}

    projected = []
    for candidate in candidates:
        hit = _project_candidate(leg, candidate)
        if hit is None or hit.distance_mi is None or hit.distance_mi > MAX_OFFSET_MI:
            continue
        if hit.name.strip().lower() in names:
            continue
        projected.append(hit)
    projected.sort(key=lambda c: c.distance_mi or 0.0)

    added: list[dict[str, Any]] = []
    for hit in projected:
        if len(added) >= per_leg:
            break
        stop = hit.to_stop()
        # Same rule the parser enforces: strictly inside the leg, never on a
        # city. _project_candidate already keeps 3 miles clear of each end,
        # but clamp anyway so a future change to that guard cannot break the
        # world the way an endpoint projection did during the gap fill.
        stop["at_mi"] = min(max(float(stop["at_mi"]), 0.1), round(miles - 0.1, 1))
        if any(abs(stop["at_mi"] - t) < 4.0 for t in taken):
            continue
        # Carry the coordinates so the classifier judges this stop on the same
        # evidence as every other one rather than being told what it is.
        stop["lat"], stop["lon"] = hit.lat, hit.lon
        leg.setdefault("stops", []).append(stop)
        taken.append(stop["at_mi"])
        names.add(stop["name"].strip().lower())
        added.append(stop)
    if added:
        leg["stops"].sort(key=lambda s: float(s.get("at_mi", 0.0)))
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-miles", type=float, default=100.0)
    parser.add_argument("--per-leg", type=int, default=2)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args(argv)

    data = load_world()
    targets = target_legs(data, args.min_miles)
    print(f"{len(targets)} leg(s) over {args.min_miles:.0f} mi with no truck-usable stop.")

    # Three independent authorities, because one source's silence proves
    # little: the federal survey, and the two biggest chains' own location
    # databases, which certainly know where their own stores are.
    survey = fetch_jasons_law_candidates(None)
    loves = fetch_loves_candidates()
    pilot = fetch_pilot_candidates()
    candidates = survey + loves + pilot
    print(
        f"{len(survey)} surveyed Jason's Law records, {len(loves)} Love's, "
        f"{len(pilot)} Pilot/Flying J -- {len(candidates)} candidates.\n"
    )

    closed = 0
    still_empty: list[str] = []
    for leg in targets:
        added = fill(leg, candidates, args.per_leg)
        if added:
            closed += 1
            if args.report:
                for stop in added:
                    print(
                        f"  + {leg['from']}->{leg['to']} ({leg.get('highway')}): "
                        f"{stop['name']} @ {stop['at_mi']} "
                        f"[{stop.get('parking_spaces', 0)} surveyed spaces]"
                    )
        else:
            still_empty.append(
                f"{leg['from']} -> {leg['to']} ({leg.get('highway')}, {leg['miles']:.0f} mi)"
            )

    print(f"\nClosed {closed} of {len(targets)} leg(s) with real surveyed facilities.")
    print(f"{len(still_empty)} leg(s) still have no truck-usable stop -- OWNER DECISION:")
    for line in still_empty:
        print(f"  {line}")

    if args.write:
        print(f"\nWrote {save_world(data)} shard(s).")
    else:
        print("\nDry run. Re-run with --write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
