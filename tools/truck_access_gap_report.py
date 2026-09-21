"""Where does the access sweep leave a driver with nowhere legal to stop?

Reclassifying a stop as ``bobtail_only`` is honest, but it is not free: the
stop stops counting toward HOS planning, and a corridor that looked served can
turn into a long serviceless stretch. This reports those stretches so they get
filled with REAL facilities -- truck stops, service plazas, rest areas -- per
docs/map-enrichment-recipe.md, rather than left as a silent regression or
papered over with a fake stop.

It reports BEFORE and AFTER for every leg, so the cost of the sweep is visible
rather than inferred: "before" ignores vehicle_access (every curated stop
counts, the pre-sweep world), "after" counts only stops a combination vehicle
can enter.

A "serviceless stretch" is measured between consecutive usable stops, and
includes the run from the leg start to the first one and from the last one to
the leg end -- a leg with no usable stop at all has a stretch equal to its
whole length.

Usage::

    uv run python tools/truck_access_gap_report.py --action sleep --top 25
    uv run python tools/truck_access_gap_report.py --json report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from world_source import load_world

ROOT = Path(__file__).resolve().parents[1]

# A stretch longer than this with no legal place to shut down is the shape of
# the problem the brief cares about: the player is out of hours with nowhere
# to go. Not a hard rule -- rural corridors are honestly empty -- but the
# threshold that decides what lands in the report.
LONG_STRETCH_MI = 100.0


def _usable(stop: dict[str, Any], action: str, *, respect_access: bool) -> bool:
    if action and action not in (stop.get("actions") or ()):
        return False
    if not respect_access:
        return True
    return str(stop.get("vehicle_access", "tractor_trailer")) == "tractor_trailer"


def longest_stretch(leg: dict[str, Any], action: str, *, respect_access: bool) -> float:
    """Longest run of miles on this leg with no usable stop."""
    miles = float(leg.get("miles", 0.0) or 0.0)
    points = sorted(
        float(stop.get("at_mi", 0.0))
        for stop in leg.get("stops", [])
        if _usable(stop, action, respect_access=respect_access)
    )
    if not points:
        return miles
    worst = points[0]  # start of leg to the first stop
    for earlier, later in zip(points, points[1:], strict=False):
        worst = max(worst, later - earlier)
    return max(worst, miles - points[-1])  # last stop to the end


def build_report(data: dict[str, Any], action: str) -> dict[str, Any]:
    rows = []
    for leg in data["legs"]:
        # Dropping stops can only lengthen a serviceless stretch, so after is
        # always >= before. Every leg is reported: filtering here once hid all
        # 565 worsened legs behind a comfortable zero.
        before = longest_stretch(leg, action, respect_access=False)
        after = longest_stretch(leg, action, respect_access=True)
        rows.append(
            {
                "from": leg["from"],
                "to": leg["to"],
                "highway": leg.get("highway", ""),
                "miles": round(float(leg.get("miles", 0.0) or 0.0), 1),
                "before_mi": round(before, 1),
                "after_mi": round(after, 1),
                "worsened_mi": round(after - before, 1),
            }
        )
    rows.sort(key=lambda row: (-row["worsened_mi"], -row["after_mi"]))
    long_after = [row for row in rows if row["after_mi"] >= LONG_STRETCH_MI]
    return {
        "action": action,
        "long_stretch_threshold_mi": LONG_STRETCH_MI,
        "legs_total": len(rows),
        "legs_worsened": sum(1 for row in rows if row["worsened_mi"] > 0),
        "legs_over_threshold_before": sum(
            1 for row in rows if row["before_mi"] >= LONG_STRETCH_MI
        ),
        "legs_over_threshold_after": len(long_after),
        "legs": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--action",
        default="sleep",
        help="Which capability must be reachable (sleep, fuel, break; '' = any stop).",
    )
    parser.add_argument("--top", type=int, default=25, help="How many legs to print.")
    parser.add_argument("--json", type=Path, help="Also write the full report here.")
    args = parser.parse_args(argv)

    report = build_report(load_world(), args.action)

    print(f"Truck-access gap report -- capability: {args.action or 'any stop'}")
    print(f"  legs: {report['legs_total']}, worsened by the sweep: {report['legs_worsened']}")
    print(
        f"  legs with a stretch >= {LONG_STRETCH_MI:.0f} mi: "
        f"{report['legs_over_threshold_before']} before -> "
        f"{report['legs_over_threshold_after']} after"
    )
    print()
    print(f"  {'leg':<44} {'hwy':<10} {'before':>8} {'after':>8} {'worse':>8}")
    for row in report["legs"][: args.top]:
        leg = f"{row['from']} -> {row['to']}"
        print(
            f"  {leg:<44.44} {row['highway']:<10.10} "
            f"{row['before_mi']:>8.1f} {row['after_mi']:>8.1f} {row['worsened_mi']:>8.1f}"
        )

    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
