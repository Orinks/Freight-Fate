"""How often does the road ask a loaded truck to slow down?

Counts curves through the GAME's loader, so every screen and the flagged
artifact list are applied. A raw count out of the bake answers a different
question and has been mistaken for this one.

Two numbers per leg, because they move independently:

* **mainline curves** -- every bend the bake kept on the through road.
  Connector arcs are excluded: interchange ramps really are that sharp and
  carry their own speech, so counting them buries the signal. Counting them
  turned 199 into 18,187 the first time this was written.
* **calls at 65 or less** -- bends a truck holding an interstate limit has
  to come off the throttle for. That is the count a player HEARS.

The four controls are roads whose bends are known and real -- they are the
reason the feature exists. A change that quiets the network is only good if
these hold. Twice a screen that looked like a clean win on the totals had
taken Glenwood Canyon apart: the canyon follows the river at mild grade, so
its ground reads flat while the walls force the bends, and any rule keyed on
terrain relief deletes it.

    uv run python tools/curve_noise.py
    uv run python tools/curve_noise.py --interstate-only
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("FREIGHT_FATE_NO_SPEECH", "1")

from freight_fate.data import curves as C  # noqa: E402
from world_source import load_world  # noqa: E402

# The speed a truck holds when nothing is in the way. A curve advising less
# than this is a curve the driver is told about.
CRUISE_MPH = 65

# leg key (bake direction) -> (mainline curves, calls at or below cruise, name)
CONTROLS = {
    "edwards_co_us:glenwood_springs_co_us": (70, 20, "Glenwood Canyon"),
    "silverthorne_co_us:edwards_co_us": (59, 3, "Vail Pass"),
    "globe_az_us:show_low_az_us": (143, 77, "Salt River Canyon"),
    "durango_co_us:montrose_co_us": (276, 180, "US-550 Million Dollar Highway"),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--interstate-only", action="store_true")
    ap.add_argument("--cruise", type=int, default=CRUISE_MPH)
    args = ap.parse_args()

    interstates = C._interstate_leg_keys()
    miles_of = {f"{leg['from']}:{leg['to']}": float(leg["miles"]) for leg in load_world()["legs"]}

    curves = calls = 0
    miles = 0.0
    for key in C._load():
        if args.interstate_only and key not in interstates:
            continue
        rows = C.leg_curves(key)
        curves += len(rows)
        calls += sum(1 for r in rows if r.advisory_mph <= args.cruise)
        miles += miles_of.get(key, 0.0)

    scope = "interstate legs" if args.interstate_only else "all legs"
    every = miles / calls if calls else float("inf")
    print(f"{curves:,} mainline curves over {miles:,.0f} mi of {scope}")
    print(f"{calls:,} ask a truck at {args.cruise} to slow -- one every {every:.0f} mi\n")

    print("controls:")
    ok = True
    for key, (want_curves, want_calls, name) in CONTROLS.items():
        rows = C.leg_curves(key)
        got_curves = len(rows)
        got_calls = sum(1 for r in rows if r.advisory_mph <= args.cruise)
        moved = got_curves != want_curves or got_calls != want_calls
        ok = ok and not moved
        note = f"   <-- WAS {want_curves} / {want_calls}" if moved else ""
        print(f"  {name:32s} {got_curves:4d} curves, {got_calls:4d} calls{note}")

    if not ok:
        print("\nA CONTROL MOVED. These roads' bends are real and known. Do not")
        print("adopt a change that moves them without re-reading the road.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
