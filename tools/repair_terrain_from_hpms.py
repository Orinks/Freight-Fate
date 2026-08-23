"""Raise a leg's terrain label to "mountain" where FHWA says mountainous.

WHY THIS EXISTS, AND WHY IT IS SO NARROW
----------------------------------------
The ``terrain`` label and the baked FHWA HPMS terrain class disagree a great
deal, in both directions:

    HPMS level        label flat       570      HPMS mountainous label mountain  39
    HPMS rolling      label flat       207      HPMS mountainous label hills     19
    HPMS rolling      label hills      164      HPMS mountainous label flat       4
    HPMS level        label hills      129
    HPMS level        label mountain    82
    HPMS rolling      label mountain    59

Reconciling all of that is a real change and not this one. 141 legs are
labelled mountain that HPMS calls level or rolling, and deciding those needs
its own before/after -- the label is relief-in-context from the elevation
archive (``tools/reclassify_terrain.py``) and HPMS is a road-class survey;
they measure related but different things, and the label is not simply wrong
wherever it is louder.

This tool moves ONE direction only: 23 legs where HPMS says mountainous and
the label does not. That direction is safe because it is the direction where
both sources agree there is relief and only the label is quiet -- Asheville
to Knoxville (the I-40 Pigeon River Gorge, 1,800 ft of range and a 7 percent
grade, labelled "hills"), Edwards to Glenwood Springs (the canyon, labelled
"hills"), Chattanooga to Knoxville (labelled "flat").

It surfaced when correcting 176 leg mileages changed which of two equivalent
I-40 representations the router picks for Charlotte to Knoxville. The newly
preferred chain runs through Asheville, and its route briefing announced
"rolling hills" before the Pigeon River Gorge. The mileage correction did not
cause the bad label; it made an existing one audible.

Nothing but the label moves. Grades, radii and every number a physics model
reads are untouched, exactly as ``reclassify_terrain.py`` promises.

Usage
-----
    uv run python tools/repair_terrain_from_hpms.py --report
    uv run python tools/repair_terrain_from_hpms.py --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from world_source import load_world, save_world  # noqa: E402

HPMS_MOUNTAINOUS = 3


def plan(world: dict) -> list[tuple[str, str, str]]:
    """``(leg id, current label, miles)`` for every leg HPMS calls mountainous
    whose label disagrees."""
    out = []
    for leg in world["legs"]:
        terrain = str(leg.get("terrain") or "").strip()
        hpms = (leg.get("corridor") or {}).get("hpms_terrain") or {}
        if hpms.get("type") == HPMS_MOUNTAINOUS and terrain != "mountain":
            out.append((f"{leg['from']}:{leg['to']}", terrain or "(unset)", leg.get("miles")))
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply the correction")
    ap.add_argument("--report", action="store_true", help="print the plan, no write")
    args = ap.parse_args()

    world = load_world()
    rows = plan(world)
    print(f"{len(rows)} legs HPMS calls mountainous whose label says otherwise:")
    for leg_id, label, miles in rows:
        print(f"  {leg_id:52s} {label:9s} -> mountain   ({miles} mi)")
    if not args.write:
        return 0

    wanted = {leg_id for leg_id, _, _ in rows}
    changed = 0
    for leg in world["legs"]:
        if f"{leg['from']}:{leg['to']}" in wanted:
            leg["terrain"] = "mountain"
            changed += 1
    save_world(world)
    print(f"\nraised {changed} labels; nothing else on those legs was touched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
