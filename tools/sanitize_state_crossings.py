"""Offline cleanup for state-line crossing noise baked into world.json.

Highways that run alongside a river border picked up phantom state crossings
when corridor geometry was sampled vertex-by-vertex against a *simplified* state
boundary polygon: the route brushes the line, the point-in-polygon test flickers
across it, and a flurry of crossings the driver never actually makes gets written
into the data. I-84 hugging the Oregon bank of the Columbia Gorge is the worst
offender -- it parallels the OR/WA line for ~100 miles without ever crossing it,
yet the data claimed four round-trip crossings in that stretch.

This pass reuses the same round-trip dwell filter the enrichment generator now
applies (``enrich_routes.coalesce_short_states``) to scrub the already-baked
legs -- no network, no OSRM, no route regeneration. For every leg it rebuilds the
state sequence from the baked crossings, collapses short round-trip excursions,
and rewrites ``state_crossings`` / ``state_miles`` to match. Legs that are
already clean are left byte-for-byte untouched.

    python tools/sanitize_state_crossings.py            # rewrite world.json
    python tools/sanitize_state_crossings.py --check    # report only, exit 1 if dirty
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from enrich_routes import (  # noqa: E402  (path shim above must run first)
    WORLD_PATH,
    coalesce_short_states,
    crossings_from_sequence,
    spoken_state,
    state_miles_from_sequence,
)


def _sequence_from_crossings(
    crossings: list[dict[str, Any]],
    from_state: str,
    to_state: str,
    leg_miles: float,
) -> list[dict[str, Any]]:
    """Reconstruct the ordered ``{state, at_mi}`` sequence baked crossings imply."""
    sequence = [{"state": from_state, "at_mi": 0.0}]
    for crossing in crossings:
        sequence.append({"state": crossing["state"], "at_mi": float(crossing["at_mi"])})
    if sequence[-1]["state"] != to_state:
        sequence.append({"state": to_state, "at_mi": leg_miles})
    return sequence


def _key(crossings: list[dict[str, Any]]) -> list[tuple[str, str, float]]:
    return [(c["from_state"], c["state"], float(c["at_mi"])) for c in crossings]


def sanitize(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Scrub phantom crossings in place. Returns a per-leg change report."""
    cities = data["cities"]
    changes: list[dict[str, Any]] = []
    for leg in data["legs"]:
        corridor = leg.get("corridor")
        if not isinstance(corridor, dict):
            continue
        baked = corridor.get("state_crossings")
        if not baked:
            continue
        leg_miles = float(leg["miles"])
        endpoint_states = (
            spoken_state(data, cities[leg["from"]]["state"]),
            spoken_state(data, cities[leg["to"]]["state"]),
        )
        sequence = _sequence_from_crossings(
            baked, endpoint_states[0], endpoint_states[1], leg_miles
        )
        cleaned = coalesce_short_states(sequence, leg_miles)
        new_crossings = crossings_from_sequence(cleaned, leg_miles, leg["highway"])
        if _key(new_crossings) == _key(baked):
            continue  # already clean -- leave the leg untouched
        dropped = len(baked) - len(new_crossings)
        if new_crossings:
            corridor["state_crossings"] = new_crossings
        else:
            corridor.pop("state_crossings", None)
        corridor["state_miles"] = state_miles_from_sequence(cleaned, leg_miles, endpoint_states)
        changes.append(
            {
                "leg": f"{leg['from']} -> {leg['to']}",
                "highway": leg["highway"],
                "dropped": dropped,
                "before": [c["place"] for c in baked],
                "after": [c["place"] for c in new_crossings],
            }
        )
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report phantom crossings without writing; exit 1 if any remain.",
    )
    args = parser.parse_args(argv)

    data = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    changes = sanitize(data)

    if not changes:
        print("No phantom state crossings found; world.json is clean.")
        return 0

    total_dropped = sum(change["dropped"] for change in changes)
    print(
        f"{'Would scrub' if args.check else 'Scrubbed'} {total_dropped} phantom "
        f"crossing(s) across {len(changes)} leg(s):"
    )
    for change in changes:
        print(f"  {change['leg']} on {change['highway']}: -{change['dropped']}")
        print(f"    before: {change['before']}")
        print(f"    after:  {change['after']}")

    if args.check:
        return 1

    WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {WORLD_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
