"""Turn toll evidence into the tolls a driver actually pays.

Two halves, kept apart on purpose:

* what a leg CROSSES is a reading -- tools/toll_evidence.py measures the
  leg's own line against the tolled ways in the PBF;
* what that crossing COSTS is a curated judgment read off the authority's
  own schedule -- tools/toll_rates.py and the city-pair table in
  tools/toll_review_sheet.py.

This joins them. It will not invent the second half. A leg that crosses a
tolled road nobody has priced is REPORTED, not filled in with a plausible
number, because the whole reason the previous 46 toll events were rebuilt is
that every one of them was an estimate that read like a fact.

Provenance follows the house rule: every event says whether its amount was
read (an authority asserts it), derived (naming input and formula), or
assumed. Nothing here is assumed; unpriced crossings stay unpriced.

    uv run python tools/toll_price.py
    uv run python tools/toll_price.py --write
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from world_source import load_world, save_world  # noqa: E402


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tr = _load("toll_rates")
trs = _load("toll_review_sheet")

EVIDENCE = ROOT / "logs" / "toll-evidence.json"

# A rig with a working transponder is the normal case for a working driver,
# and every rate in the curated tables carries both. Plate price is kept on
# the event so a later feature can charge a driver who has let the tag lapse.
METHOD = "transponder"

# Which authority runs each facility, for the spoken line. Facility names come
# from OSM; the authority is what a driver would say they paid.
AUTHORITY: dict[str, str] = {
    "New York State Thruway": "New York State Thruway Authority",
    "New York State Thruway Berkshire Connector": "New York State Thruway Authority",
    "New England Thruway": "New York State Thruway Authority",
    "Pennsylvania Turnpike": "Pennsylvania Turnpike Commission",
    "Pennsylvania Turnpike Northeast Extension": "Pennsylvania Turnpike Commission",
    "Ohio Turnpike": "Ohio Turnpike and Infrastructure Commission",
    "Indiana Toll Road": "Indiana Toll Road Concession Company",
    "Massachusetts Turnpike": "Massachusetts Department of Transportation",
    "Maine Turnpike": "Maine Turnpike Authority",
    "Kansas Turnpike": "Kansas Turnpike Authority",
    "New Jersey Turnpike": "New Jersey Turnpike Authority",
    "New Jersey Turnpike Eastern Spur": "New Jersey Turnpike Authority",
    "Garden State Parkway": "New Jersey Turnpike Authority",
    "Florida's Turnpike": "Florida Turnpike Enterprise",
    "West Virginia Turnpike": "West Virginia Parkways Authority",
    "Chicago Skyway": "Skyway Concession Company",
    "Cimarron Turnpike": "Oklahoma Turnpike Authority",
    "Will Rogers Turnpike": "Oklahoma Turnpike Authority",
    "Harry E. Bailey Turnpike": "Oklahoma Turnpike Authority",
    "Indian Nation Turnpike": "Oklahoma Turnpike Authority",
    "Muskogee Turnpike": "Oklahoma Turnpike Authority",
    "Governor Roy Joseph Turner Turnpike": "Oklahoma Turnpike Authority",
}


def spoken_name(facility: str) -> str:
    """What the driver hears. Plain road language, no maintainer vocabulary."""
    return f"{facility} toll"


def priced(leg_key: str, runs: list[dict]) -> dict[str, Any] | None:
    """The curated rate for this leg, or None if nobody has read one."""
    frm, to = leg_key.split(":", 1)
    entry = trs.RESEARCHED.get((frm, to)) or trs.RESEARCHED.get((to, frm))
    if entry is None:
        return None
    facility = max(runs, key=lambda r: r["miles"])["facility"]
    return {
        "transponder": entry["transponder"],
        "plate": entry.get("plate", entry["transponder"]),
        "src": entry["src"],
        "facility": facility,
    }


def build_event(leg_key: str, runs: list[dict], rate: dict) -> dict[str, Any]:
    run = max(runs, key=lambda r: r["miles"])
    facility = rate["facility"]
    return {
        "name": spoken_name(facility),
        "at_mi": round(float(run["start_mi"]), 1),
        "road": facility,
        "authority": AUTHORITY.get(facility, ""),
        "method": METHOD,
        "amount": round(float(rate["transponder"]), 2),
        "plate_amount": round(float(rate["plate"]), 2),
        "estimated": False,
        # read: the authority's own published schedule asserts this figure for
        # a five-axle commercial vehicle. Not derived and not assumed.
        "source": f"read: {rate['src']}",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--evidence", type=Path, default=EVIDENCE)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    rows = json.loads(args.evidence.read_text(encoding="utf-8"))
    by_leg = {r["leg"]: r for r in rows}

    world = load_world()
    legs = {f"{leg['from']}:{leg['to']}": leg for leg in world["legs"]}

    events: dict[str, dict] = {}
    unpriced: list[tuple[str, float, str]] = []
    discarded: list[tuple[str, str]] = []

    for key, row in sorted(by_leg.items()):
        if key not in legs:
            continue
        frm, to = key.split(":", 1)
        not_tolled = tr.NOT_TOLLED.get(f"{frm}->{to}") or tr.NOT_TOLLED.get(f"{to}->{frm}")
        if not_tolled:
            discarded.append((key, not_tolled))
            continue
        rate = priced(key, row["runs"])
        if rate is None:
            biggest = max(row["runs"], key=lambda r: r["miles"])
            unpriced.append((key, biggest["miles"], biggest["facility"]))
            continue
        events[key] = build_event(key, row["runs"], rate)

    print(f"{len(by_leg)} legs cross a tolled road")
    print(f"  {len(events)} can be priced from a schedule someone has read")
    print(f"  {len(unpriced)} cross a road nobody has priced yet")
    print(f"  {len(discarded)} discarded -- research established they are not tolled for us\n")

    if discarded:
        print("discarded:")
        for key, why in discarded:
            print(f"  {key:44s} {why}")
        print()

    print("priced:")
    for key, ev in sorted(events.items(), key=lambda kv: -kv[1]["amount"]):
        print(f"  {key:44s} ${ev['amount']:7.2f}  {ev['road']}")

    print(f"\nunpriced, by how much road is involved (the research queue):")
    for key, miles, facility in sorted(unpriced, key=lambda x: -x[1])[:30]:
        print(f"  {key:44s} {miles:6.1f} mi  {facility}")
    if len(unpriced) > 30:
        print(f"  ... and {len(unpriced) - 30} more")

    if not args.write:
        print("\n(dry run -- pass --write to put these on the legs)")
        return 0

    touched = 0
    for leg in world["legs"]:
        key = f"{leg['from']}:{leg['to']}"
        if key not in events:
            continue
        corridor = leg.setdefault("corridor", {})
        corridor["toll_events"] = [events[key]]
        touched += 1
    save_world(world)
    print(f"\nwrote toll events onto {touched} legs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
