"""Which fault is it: the label, or the route?

Some legs are labelled for an interstate their baked route never joins, and
two different faults look identical from inside the data. A truck router tells
them apart, which is what this measures:

  * the interstate IS the road between those two cities and the BAKED route is
    what is wrong -- Corpus Christi to San Antonio is 98 percent I-37 by any
    sane routing, and the archived polyline goes another way. That leg wants
    REROUTING (``reroute_leg.py`` then ``reroute_enrich.py``), and relabelling
    it would enshrine the bad route;
  * the interstate does not serve that pair at all -- Tampa to Miami is
    Florida's Turnpike, I-75 runs up the west coast. The LABEL is the fault
    and ``repair_leg_labels.py`` fixes it, reading the split this writes.

ONE ASYMMETRY, AND IT IS THE ROUTER'S
-------------------------------------
That second verdict is only safe on an INTERSTATE leg. Truck costing prefers
a freeway, so on a leg named for a US or state route the router will take the
parallel interstate and score the leg's own road at zero -- which says the
freeway is faster, not that the label is wrong. A secondary-road run is a
legitimate thing for a leg to be. Those legs are reported as a question and
never as a verdict. The REROUTE verdict has no such problem: it only fires
when the router actually rides the road the leg is named for.

``repair_leg_labels.py --split`` has always wanted this file and there was
never a tool that produced one, so the split had to be re-derived by hand
every time anyone needed it. This is that tool.

HOW A LEG BECOMES SUSPECT
-------------------------
From the map-matched coverage in ``curve_osm.jsonl``: an interstate-labelled
leg whose own archived polyline rides its own shield for at most
``SUSPECT_FRAC`` of the miles the matcher could read. That file is written by
``curve_valhalla_facts.py --all`` and is not checked in, so run that first.

MEASURED, NOT CHOSEN
--------------------
The verdict per leg is the share of the ROUTER's mileage that rides the
labelled shield, from the same map matcher. When this was first run across 40
suspect legs the distribution had a 14-point hole in it::

    0 0 0 0 0 0 0 2 2 4  |  18 18 24 25 25 30 ... 93 98 98

so the threshold is read off the data rather than picked. This prints the
distribution every time for exactly that reason: a threshold that stops
separating anything is a threshold that has to be re-derived.

    uv run python tools/probe_leg_labels.py --out .route-cache/label-split.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import reroute_leg as rr  # noqa: E402
import straw_curve_sample as scs  # noqa: E402
from bake_curve_connectors import FACTS  # noqa: E402
from world_source import load_world  # noqa: E402

# A leg riding its own shield for no more than this much of its matched miles
# is worth asking the router about.
#
# Probing generously costs router time and cannot change a verdict -- the
# verdict is the router's -- where probing tightly silently drops real cases.
# It has already done that twice: at 4 percent this missed Corpus Christi to
# San Antonio, which rides US-181 for 60 of its 76 matched miles and is the
# worked example in every document about this bug; at 25 percent it missed
# 82 more interstate legs that spend between a quarter and half their miles
# off their own road. Half is where a leg stops being mostly-somewhere-else.
SUSPECT_FRAC = 0.50

# ...but a leg is only nominated for REROUTING if the router's route beats the
# baked one by this much as well as clearing ``reroute_leg.MIN_ON_LABEL``.
# Rerouting changes the leg's mileage, and mileage is pay and deadlines, so a
# ten-point improvement is not worth moving what a player earns for a run they
# know. A big gap is; that is the case this whole job exists for.
MIN_GAIN = 0.25


def load_coverage(path: Path) -> dict[str, dict]:
    """``leg id -> coverage row`` from the map-matcher's facts shard."""
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "coverage_samples" in row:
            out[row["leg"]] = row
    return out


def baked_on_label(row: dict) -> float | None:
    """Share of a leg's OWN polyline that rides its own shield.

    Straight off the matcher's own coverage count, not recomputed from the
    ``ridden_refs`` summary -- that summary keeps only the eight commonest
    names, so a leg whose shield falls outside the top eight would read as
    zero and be called worse than it is.
    """
    samples = row.get("coverage_samples") or 0
    if not samples:
        return None
    return (row.get("coverage_on_shield") or 0) / samples


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--facts", type=Path, default=FACTS, help=f"coverage shard (default {FACTS})")
    ap.add_argument("--out", type=Path, required=True, help="where to write the split JSON")
    ap.add_argument("--limit", type=int, default=0, help="probe at most this many legs")
    args = ap.parse_args()

    if not args.facts.exists():
        print(f"{args.facts} is missing -- run tools/curve_valhalla_facts.py --all first.")
        return 1
    coverage = load_coverage(args.facts)
    world = load_world()
    cities = world["cities"]

    suspects = []
    unread = 0
    for leg in world["legs"]:
        highway = str(leg.get("highway") or "")
        # Every leg named for a numbered route, not only the interstates. The
        # interstate filter was inherited from repair_leg_labels and hid a
        # bug rather than expressing a policy: rides_its_label only counted a
        # matched road whose name began with "I", so a US or state leg scored
        # zero however faithfully it drove its own road, and reroute_leg
        # would have refused every one of them.
        if scs.shield_key(highway) is None:
            continue
        if leg.get("rerouted"):
            continue  # already put back on its road
        leg_id = f"{leg['from']}:{leg['to']}"
        row = coverage.get(leg_id)
        if row is None:
            unread += 1
            continue
        share = baked_on_label(row)
        if share is not None and share <= SUSPECT_FRAC:
            suspects.append((leg, share))
    suspects.sort(key=lambda item: f"{item[0]['from']}:{item[0]['to']}")
    if args.limit:
        suspects = suspects[: args.limit]
    print(
        f"{len(suspects)} legs ride their own shield for "
        f"{100 * SUSPECT_FRAC:.0f}% of their baked miles or less"
        + (f" ({unread} legs had no coverage reading)" if unread else "")
    )
    print("asking the router about each, about twenty seconds a leg\n", flush=True)

    rows: list[dict] = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for n, (leg, baked_share) in enumerate(suspects, 1):
        leg_id = f"{leg['from']}:{leg['to']}"
        highway = str(leg.get("highway") or "")
        fetched = rr.fetch_route(cities[leg["from"]], cities[leg["to"]])
        if fetched is None:
            print(f"  [{n}/{len(suspects)}] {leg_id}: the router returned no route")
            continue
        shape, miles, _has_toll = fetched
        share, dominant = rr.rides_its_label(shape, highway)
        rows.append(
            {
                "leg": leg_id,
                "highway": highway,
                "baked_on_label_frac": round(baked_share, 4),
                "on_label_frac": round(share, 4),
                "baked_miles": float(leg["miles"]),
                "router_miles": round(miles, 1),
                "router_dominant_road": dominant,
            }
        )
        # Written as it goes: this is an hour of somebody else's free service,
        # and losing it to a dropped connection at leg 38 is not acceptable.
        args.out.write_text(json.dumps(rows, indent=1, sort_keys=True), encoding="utf-8")
        print(
            f"  [{n}/{len(suspects)}] {leg_id:46s} {highway:8s} "
            f"baked {100 * baked_share:3.0f}% -> router {100 * share:3.0f}% "
            f"({dominant}, {miles:.0f} mi against {leg['miles']})",
            flush=True,
        )

    shares = sorted(round(100 * row["on_label_frac"]) for row in rows)
    print("\nthe router's on-label share across the suspects, sorted:")
    print("  " + " ".join(str(value) for value in shares))
    gap, at = 0, 0
    for low, high in zip(shares, shares[1:], strict=False):
        if high - low > gap:
            gap, at = high - low, low
    print(f"  widest hole: {gap} points, just above {at}")

    # The verdict line is reroute_leg's own refusal threshold, so this tool
    # can never nominate a leg that tool would then refuse -- and the gain
    # bar on top of it keeps a marginal improvement from moving a player's
    # pay for a run they already know.
    def gain(row: dict) -> float:
        return row["on_label_frac"] - row["baked_on_label_frac"]

    reroute = [
        row for row in rows if row["on_label_frac"] >= rr.MIN_ON_LABEL and gain(row) >= MIN_GAIN
    ]
    marginal = [
        row for row in rows if row["on_label_frac"] >= rr.MIN_ON_LABEL and gain(row) < MIN_GAIN
    ]

    # A RELABEL verdict is only safe on an interstate leg, and the asymmetry
    # is the router's cost model rather than anything about the data. Truck
    # costing prefers a freeway, so on a leg named for a US or state route the
    # router will happily take the parallel interstate and score the leg's own
    # road at zero -- which says the freeway is faster, not that the label is
    # wrong. Plenty of legs are secondary-road runs on purpose. So those are
    # reported as a question, never as a verdict.
    def is_interstate(row: dict) -> bool:
        key = scs.shield_key(row["highway"])
        return bool(key and key[0] == "I")

    relabel = [row for row in rows if row["on_label_frac"] < rr.MIN_ON_LABEL and is_interstate(row)]
    router_prefers_elsewhere = [
        row for row in rows if row["on_label_frac"] < rr.MIN_ON_LABEL and not is_interstate(row)
    ]
    print(f"\n{len(reroute)} legs want REROUTING (their own road IS the road):")
    for row in sorted(reroute, key=lambda r: -gain(r)):
        print(
            f"  {row['leg']:46s} {row['highway']:8s} "
            f"{100 * row['baked_on_label_frac']:3.0f}% -> {100 * row['on_label_frac']:3.0f}%  "
            f"{row['baked_miles']:.0f} -> {row['router_miles']:.0f} mi"
        )
    print(
        f"\n{len(marginal)} legs would improve by less than {100 * MIN_GAIN:.0f} points "
        "and are LEFT ALONE (not worth moving the pay):"
    )
    for row in sorted(marginal, key=lambda r: -gain(r)):
        print(
            f"  {row['leg']:46s} {row['highway']:8s} "
            f"{100 * row['baked_on_label_frac']:3.0f}% -> {100 * row['on_label_frac']:3.0f}%"
        )
    print(f"\n{len(relabel)} interstate legs want RELABELLING (that road does not serve the pair):")
    for row in sorted(relabel, key=lambda r: r["leg"]):
        print(f"  {row['leg']:46s} {row['highway']:8s} drives {row['router_dominant_road']}")
    print(
        f"\n{len(router_prefers_elsewhere)} US/state legs where the router took a different "
        "road. NOT a verdict: truck costing prefers a freeway, so this is only\n"
        "  a question about whether the leg is a secondary-road run on purpose."
    )
    for row in sorted(router_prefers_elsewhere, key=lambda r: r["leg"]):
        print(
            f"  {row['leg']:46s} {row['highway']:8s} "
            f"baked {100 * row['baked_on_label_frac']:3.0f}% on its own road, "
            f"router took {row['router_dominant_road']}"
        )
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
