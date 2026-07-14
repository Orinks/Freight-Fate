"""Map statistics: counts for changelogs, the morning tally, and (later) an
in-game "explore the map" screen.

Reads the checked-in world data and reports how much map there is: cities
(dispatchable freight nodes), legs (routes between them), real checkpoints
(named orientation places) versus the synthetic placeholders still to be
enriched, truck stops (and how many carry a real coordinate for the
surface-street layer), and a per-region city breakdown.

Read-only. Run any time:
    uv run python tools/map_stats.py
    uv run python tools/map_stats.py --json      # machine-readable
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORLD_PATH = ROOT / "src" / "freight_fate" / "data" / "world.json"
PLACEHOLDER_MARK = "corridor between"


def _is_real_checkpoint(cp: dict[str, Any]) -> bool:
    return PLACEHOLDER_MARK not in str(cp.get("name", ""))


def compute_stats(data: dict[str, Any]) -> dict[str, Any]:
    cities = data.get("cities", {})
    legs = data.get("legs", [])

    real_cp = placeholder_cp = 0
    stops = stops_with_coord = 0
    legs_with_real = legs_placeholder_only = legs_no_cp = 0
    total_miles = 0.0
    for leg in legs:
        total_miles += float(leg.get("miles", 0) or 0)
        checkpoints = leg.get("corridor", {}).get("checkpoints", [])
        reals = [c for c in checkpoints if _is_real_checkpoint(c)]
        placeholders = [c for c in checkpoints if not _is_real_checkpoint(c)]
        real_cp += len(reals)
        placeholder_cp += len(placeholders)
        if reals:
            legs_with_real += 1
        elif placeholders:
            legs_placeholder_only += 1
        else:
            legs_no_cp += 1
        for stop in leg.get("stops", []):
            stops += 1
            if stop.get("lat") is not None and stop.get("lon") is not None:
                stops_with_coord += 1

    by_region = Counter(str(c.get("region", "unknown")) for c in cities.values())

    return {
        "cities": len(cities),
        "legs": len(legs),
        "total_miles": round(total_miles),
        "real_checkpoints": real_cp,
        "placeholder_checkpoints": placeholder_cp,
        "truck_stops": stops,
        "truck_stops_with_coordinate": stops_with_coord,
        "legs_with_real_checkpoints": legs_with_real,
        "legs_placeholder_only": legs_placeholder_only,
        "legs_without_checkpoints": legs_no_cp,
        "cities_by_region": dict(sorted(by_region.items(), key=lambda kv: -kv[1])),
    }


def format_stats(s: dict[str, Any]) -> str:
    lines = [
        "Freight Fate map statistics",
        "===========================",
        f"Cities (dispatchable freight nodes): {s['cities']}",
        f"Legs (routes between cities):        {s['legs']}",
        f"Total drivable miles:                {s['total_miles']:,}",
        "",
        f"Real named checkpoints:              {s['real_checkpoints']}",
        f"Placeholder checkpoints (to enrich): {s['placeholder_checkpoints']}",
        f"Truck stops:                         {s['truck_stops']}",
        f"  of those with a real coordinate:   {s['truck_stops_with_coordinate']}",
        "",
        f"Legs with real checkpoints:          {s['legs_with_real_checkpoints']}",
        f"Legs still placeholder-only:         {s['legs_placeholder_only']}",
        f"Legs with no checkpoints:            {s['legs_without_checkpoints']}",
        "",
        "Cities by region:",
    ]
    lines += [f"  {region}: {count}" for region, count in s["cities_by_region"].items()]
    return "\n".join(lines)


def _load_ref(ref: str) -> dict[str, Any] | None:
    """Load world.json from a git ref (e.g. 'dev'), or None if unavailable."""
    rel = WORLD_PATH.relative_to(ROOT).as_posix()
    out = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=ROOT, capture_output=True)
    if out.returncode != 0:
        return None
    return json.loads(out.stdout.decode("utf-8"))


def format_delta(cur: dict[str, Any], base: dict[str, Any], ref: str) -> str:
    dm = cur["total_miles"] - base["total_miles"]
    dc = cur["cities"] - base["cities"]
    dl = cur["legs"] - base["legs"]
    return "\n".join(
        [
            f"Map drop vs {ref}:",
            f"  Drivable miles added:   {dm:+,}  (now {cur['total_miles']:,})",
            f"  Cities added:           {dc:+}  (now {cur['cities']})",
            f"  Legs added:             {dl:+}  (now {cur['legs']})",
            "",
            "Changelog line:",
            f"  This drop adds {dm:,} drivable miles -- the map now has "
            f"{cur['total_miles']:,} miles of road across {cur['cities']} cities "
            f"and {cur['legs']} routes.",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report Freight Fate map statistics.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--since",
        metavar="GITREF",
        help="Also report miles/cities/legs added vs a git ref (e.g. 'dev', "
        "'origin/dev'), with a ready-to-paste changelog line.",
    )
    args = parser.parse_args(argv)
    data = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    stats = compute_stats(data)
    if args.json:
        out = dict(stats)
        if args.since:
            base = _load_ref(args.since)
            if base is not None:
                b = compute_stats(base)
                out["since"] = {
                    "ref": args.since,
                    "miles_added": stats["total_miles"] - b["total_miles"],
                    "cities_added": stats["cities"] - b["cities"],
                    "legs_added": stats["legs"] - b["legs"],
                }
        print(json.dumps(out, indent=2))
        return 0
    print(format_stats(stats))
    if args.since:
        base = _load_ref(args.since)
        if base is None:
            print(f"\n(could not load world.json at ref {args.since!r})")
        else:
            print("\n" + format_delta(stats, compute_stats(base), args.since))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
