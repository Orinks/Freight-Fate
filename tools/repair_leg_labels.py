"""Name a leg for the road it actually drives.

Some legs are labelled for an interstate their baked route never touches. The
curated I-40 from Hickory to Charlotte drives NC-16 for 78 percent of its
miles and I-40 for none of them, and the game says "on I-40" the whole way.

WHICH LEGS, AND WHY NOT ALL OF THEM
-----------------------------------
Two different faults look identical from inside the data, and a truck router
tells them apart. Ask Valhalla for the truck route between the two city nodes
and measure how much of ITS mileage rides the labelled interstate:

  * A high share means the interstate IS the road between those cities and the
    BAKED route is what is wrong -- Corpus Christi to San Antonio is 98
    percent I-37 by any sane routing, and ORS simply picked badly. Relabelling
    such a leg to US-181 would enshrine the bad route. Those want rerouting,
    which is a corridor re-bake and not this tool.
  * A share near zero means the interstate does not serve that pair at all.
    Tampa to Miami is Florida's Turnpike; I-75 goes up the west coast. The
    label is the fault, and this tool fixes it.

WHERE THE LINE IS, AND WHY IT MOVED. The first run of this read the line off
the data: the distribution across 40 suspect legs had a 14-point hole in it
(0 0 0 0 0 0 0 2 2 4 | 18 18 24 25 25 30 ... 93 98 98), ten legs below and
thirty above. That hole has since CLOSED -- re-measured with a loaded-semi
routing profile the distribution runs continuously from 0 to 96 -- so the
line is no longer a gap but ``reroute_leg.MIN_ON_LABEL``, the same share
below which that tool refuses to reroute. One threshold, two tools, and no
leg can fall between them.

The split itself comes from ``tools/probe_leg_labels.py``, which is what
``--split`` wants.

THE NEW NAME IS READ, NOT CHOSEN
--------------------------------
It comes from map-matching the leg's own archived polyline: whichever route
shield carries the most of its miles. A leg with no clear majority is LEFT
ALONE and reported, because there is no honest single name for a route that
threads four roads -- naming it after a 30 percent plurality would trade one
wrong label for a less obviously wrong one.

Concurrencies are counted once per mile, not once per shield. "US 31" and
"US 31 BUS" on the same mile are the same mile; counting both produced a
"114 percent" share on Sault Ste. Marie to Traverse City before this was
fixed, which is the sort of number that tells you the method is wrong. It
changed a verdict, too: Cape Girardeau to Paducah read IL-3 at 61 percent
under the double count and US-60 at 45 under the honest one, which moved it
out of the rename set and into the leave-alone list where it belongs.

AFTER RUNNING THIS, RE-SCREEN THE ARTIFACTS. ``data/curves.py`` picks its
interstate geometry screen by ``highway`` starting with "I-", so a leg that
stops being an interstate moves from that screen to the US/state one, and
``curve_artifacts.jsonl`` has to be re-baked to cover it::

    uv run python tools/repair_leg_labels.py --split <file> --write
    uv run python tools/index_world.py
    uv run python tools/screen_curve_artifacts.py

Usage
-----
    uv run python tools/probe_leg_labels.py --out .route-cache/label-split.json
    uv run python tools/repair_leg_labels.py --split .route-cache/label-split.json --report
    uv run python tools/repair_leg_labels.py --split .route-cache/label-split.json --write
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reroute_leg as rr  # noqa: E402
from bake_curve_connectors import FACTS, load_facts  # noqa: E402
from world_source import load_world, save_world  # noqa: E402

# A leg whose baked route gives no road this much of its miles has no honest
# single name, and is reported rather than renamed.
MAJORITY = 0.50

# How the world writes a shield, and the spellings OSM uses for the same thing.
_PREFIX = {"ILLINOIS ROUTE": "IL", "STATE ROUTE": "SR", "STATE HIGHWAY": "SR"}
_SHIELD = re.compile(
    r"^(I|US|SR|CR|M|K|Illinois Route|State Route|State Highway|[A-Z]{2})\s*[- ]?\s*(\d+)",
    re.IGNORECASE,
)


def shield(name: str) -> str | None:
    """``"Illinois Route 3"`` -> ``"IL-3"``; a street name -> ``None``."""
    match = _SHIELD.match(name.strip())
    if not match:
        return None
    prefix = match.group(1).upper()
    return f"{_PREFIX.get(prefix, prefix)}-{match.group(2)}"


def dominant_road(coverage_row: dict) -> tuple[str | None, float]:
    """The shield carrying most of a leg's miles, and its share.

    Each mile votes ONCE. A concurrency names several shields on one mile and
    the mile belongs to all of them, but crediting each separately lets the
    shares sum past 100 percent -- which is how this method announced that a
    leg rode US-31 for 114 percent of itself.
    """
    refs = coverage_row.get("ridden_refs") or {}
    samples = coverage_row.get("coverage_samples") or 0
    if not refs or not samples:
        return None, 0.0
    tally: collections.Counter[str] = collections.Counter()
    for name, count in refs.items():
        key = shield(str(name))
        if key:
            tally[key] = max(tally[key], count)  # once per mile, not once per spelling
    if not tally:
        return None, 0.0
    name, count = tally.most_common(1)[0]
    return name, min(1.0, count / samples)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split", required=True, help="JSON from the router probe")
    ap.add_argument("--write", action="store_true", help="apply the new labels")
    ap.add_argument("--report", action="store_true", help="print the plan, no write")
    args = ap.parse_args()

    coverage, _facts = load_facts(FACTS)
    world = load_world()
    by_id = {f"{leg['from']}:{leg['to']}": leg for leg in world["legs"]}
    split = json.loads(Path(args.split).read_text(encoding="utf-8"))

    rename, leave = [], []
    for row in split:
        if row["on_label_frac"] >= rr.MIN_ON_LABEL:
            continue  # the interstate IS the road here; this wants rerouting
        leg = by_id.get(row["leg"])
        if leg is None:
            continue
        name, share = dominant_road(coverage.get(row["leg"]) or {})
        entry = (row["leg"], str(leg.get("highway")), name, share)
        (rename if name and share >= MAJORITY else leave).append(entry)

    print(f"{len(rename)} legs get the name of the road they drive:\n")
    print(f"{'leg':46s} {'was':8s} {'becomes':10s} share")
    for leg_id, was, name, share in sorted(rename):
        print(f"{leg_id:46s} {was:8s} {name:10s} {100 * share:4.0f}%")
    print(f"\n{len(leave)} have no majority road and are LEFT ALONE:\n")
    for leg_id, was, name, share in sorted(leave):
        best = f"{name} {100 * share:.0f}%" if name else "no shield at all"
        print(f"  {leg_id:46s} {was:8s} best is {best}")

    if not args.write:
        return 0
    for leg_id, _was, name, _share in rename:
        by_id[leg_id]["highway"] = name
    save_world(world)
    print(
        f"\nrenamed {len(rename)} legs -- now re-run index_world.py and screen_curve_artifacts.py"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
