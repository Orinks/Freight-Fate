"""Which tolled facilities does each leg actually cross, and for how far?

Evidence only. What a toll COSTS a five-axle rig is a curated judgment from
the authority's own schedule (``tools/toll_rates.py``); what a leg CROSSES is
a reading, and this is the reading.

Matches each leg's real geometry against the tolled ways collected by
``tools/toll_ways.py``, groups the hits into contiguous runs, and names each
run by its operator so a rate can be attached to it. A run is what gets
priced: "this leg is on the New Jersey Turnpike from mile 3 to mile 47" is a
thing an authority's schedule can answer. "This leg touches a tolled way" is
not.

    uv run python tools/toll_evidence.py --json logs/toll-evidence.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import leg_geometry as lg  # noqa: E402
import straw_curve_sample as scs  # noqa: E402
import toll_scan as ts  # noqa: E402
from world_source import load_world  # noqa: E402

WAYS = ROOT / ".route-cache" / "toll-ways.json"
# How near the road a tolled way must run to be the road the truck is on.
# Wider than the curve matcher's 90 m because a divided turnpike's two
# carriageways are mapped as separate ways a hundred metres apart, and the
# leg's line sits on one of them.
MATCH_M = 200.0
# Sample the leg this often when asking "am I on a tolled way here".
STEP_M = 402.0  # a quarter mile
# A run shorter than this is a crossing, not a journey: an overpass above a
# turnpike, or a moment where the line clips a parallel tolled ramp.
MIN_RUN_MI = 0.75
CELL_DEG = 0.05


def load_ways() -> tuple[list[dict], dict]:
    ways = json.loads(WAYS.read_text(encoding="utf-8"))
    index: dict[tuple[int, int], list[int]] = {}
    for position, way in enumerate(ways):
        for lat, lon in way["geometry"]:
            index.setdefault((int(lat / CELL_DEG), int(lon / CELL_DEG)), []).append(position)
    for cell in index:
        index[cell] = sorted(set(index[cell]))
    return ways, index


def chargeable(tags: dict) -> bool:
    """Is this a tolled way a tractor-trailer can actually be charged on?

    Managed, HOT and express lanes run inside the same corridor under the same
    route number as the free mainline, and tractor-trailers are barred from
    essentially all of them. A truck on that corridor is on the free
    general-purpose lanes beside them, paying nothing. Charging it for a lane
    it is not allowed to enter is worse than charging it nothing.

    The judgment lives in ``toll_scan`` and is shared rather than restated:
    this file kept sighting I-25 Express, the I-10 Metro ExpressLanes and the
    95 Express Lanes -- 38 leg-crossings' worth -- because it never asked.
    """
    if ts._is_managed_lane(tags):
        return False
    # A tolled RAMP is not the road being charged for. Ramps run beside the
    # free mainline at every interchange, so at this match radius a leg on a
    # free interstate clips them constantly -- and 21,203 of them carry no
    # name, operator, ref or network at all, which is where "unnamed tolled
    # road" came from as the third most-sighted facility in the country.
    # The facility a truck actually pays is mainline, and mainline is named.
    return not str(tags.get("highway", "")).endswith("_link")


def facility_of(tags: dict) -> str:
    """What to call the thing being charged for."""
    for key in ("name", "operator", "ref", "network"):
        value = str(tags.get(key) or "").strip()
        if value:
            return value
    return "unnamed tolled road"


def runs_for(coords, miles: float, ways, index) -> list[dict[str, Any]]:
    cum = scs._cumulative_m(coords)
    scale = miles / (cum[-1] / 1609.344) if cum[-1] else 1.0
    hits: list[tuple[float, str]] = []
    last = -1e9
    for i, (lon, lat) in enumerate(coords):
        if cum[i] - last < STEP_M and i != len(coords) - 1:
            continue
        last = cum[i]
        at_mi = cum[i] / 1609.344 * scale
        coslat = math.cos(math.radians(lat))
        best_name, best_d = None, MATCH_M
        cell = (int(lat / CELL_DEG), int(lon / CELL_DEG))
        seen: set[int] = set()
        for dlat in (-1, 0, 1):
            for dlon in (-1, 0, 1):
                seen.update(index.get((cell[0] + dlat, cell[1] + dlon), ()))
        for position in seen:
            way = ways[position]
            geometry = way["geometry"]
            for a, b in zip(geometry, geometry[1:], strict=False):
                d = scs._point_seg_dist_m(
                    lat, lon, {"lat": a[0], "lon": a[1]}, {"lat": b[0], "lon": b[1]}, coslat
                )
                if d < best_d and chargeable(way["tags"]):
                    best_d, best_name = d, facility_of(way["tags"])
        if best_name:
            hits.append((at_mi, best_name))

    runs: list[dict[str, Any]] = []
    for at_mi, name in hits:
        if runs and runs[-1]["facility"] == name and at_mi - runs[-1]["end_mi"] <= 2.0:
            runs[-1]["end_mi"] = at_mi
            continue
        runs.append({"facility": name, "start_mi": at_mi, "end_mi": at_mi})
    return [
        {
            "facility": r["facility"],
            "start_mi": round(r["start_mi"], 1),
            "end_mi": round(r["end_mi"], 1),
            "miles": round(r["end_mi"] - r["start_mi"], 1),
        }
        for r in runs
        if r["end_mi"] - r["start_mi"] >= MIN_RUN_MI
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, default=ROOT / "logs" / "toll-evidence.json")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    ways, index = load_ways()
    print(f"{len(ways):,} tolled ways loaded", flush=True)
    world = load_world()
    legs = world["legs"][: args.limit or None]
    out = []
    for n, leg in enumerate(legs, 1):
        polyline = lg.archived_polyline(lg.leg_id_of(leg), lg.state_code_of(leg))
        if not polyline:
            continue
        runs = runs_for(polyline[0], float(leg["miles"]), ways, index)
        if not runs:
            continue
        corridor = leg.get("corridor") or {}
        out.append(
            {
                "leg": lg.leg_id_of(leg),
                "highway": leg.get("highway", ""),
                "miles": float(leg["miles"]),
                "has_events": len(corridor.get("toll_events") or []),
                "router_says_toll": bool(corridor.get("tollway_detected")),
                "runs": runs,
            }
        )
        print(
            f"[{n}/{len(legs)}] {lg.leg_id_of(leg):44s} "
            + ", ".join(f"{r['facility']} {r['miles']:.0f}mi" for r in runs),
            flush=True,
        )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(out, indent=1), encoding="utf-8")

    from collections import Counter

    facilities = Counter(r["facility"] for row in out for r in row["runs"])
    print(f"\n{len(out)} legs cross a tolled road, over {len(facilities)} distinct facilities")
    print("\nthe twenty most-crossed:")
    for name, count in facilities.most_common(20):
        print(f"  {count:4d} crossings  {name}")
    print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
