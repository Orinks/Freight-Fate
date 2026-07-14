"""Repair interstate speed-limit profiles polluted by city-street samples.

The maxspeed bake samples each checked-in route point inside a 400 m box and
prefers a way matching the leg's highway shield -- but at the mile-0 and
end-of-leg city anchors the interstate itself is often outside the box, so
the fallback ("highest posted limit found") bakes a city arterial's 25-40
onto the corridor, and the step function then holds that street value for
miles of interstate (owner-found live: I-10 Buckeye-Phoenix enforced 30 mph
for ten miles).

No posted US interstate mainline runs below 45 mph, so on interstate-class
legs an anchor sample under 45 is a wrong-road match, never a real limit.
This repair drops leading and trailing sub-45 samples from interstate legs'
``corridor.speed_limits``; the step function heals itself (the runtime holds
the first surviving sample back to mile 0). Interior samples are left alone,
and non-interstate highways keep their honest small-town 30s. Offline and
deterministic -- no Overpass required. The bake tool gains the same guard so
future sweeps cannot reintroduce the pollution.

Usage:
    uv run python tools/repair_interstate_anchor_limits.py          # dry run
    uv run python tools/repair_interstate_anchor_limits.py --write
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

WORLD_PATH = Path(__file__).resolve().parent.parent / "src" / "freight_fate" / "data" / "world.json"

INTERSTATE_MIN_PLAUSIBLE_MPH = 45.0


def is_interstate(highway: str) -> bool:
    return str(highway).strip().upper().startswith("I-")


def repair(data: dict) -> list[dict]:
    repaired: list[dict] = []
    for leg in data["legs"]:
        if not is_interstate(leg.get("highway", "")):
            continue
        corridor = leg.get("corridor") or {}
        samples = corridor.get("speed_limits")
        if not samples:
            continue
        dropped: list[dict] = []
        while samples and samples[0]["mph"] < INTERSTATE_MIN_PLAUSIBLE_MPH:
            dropped.append(samples.pop(0))
        while samples and samples[-1]["mph"] < INTERSTATE_MIN_PLAUSIBLE_MPH:
            dropped.append(samples.pop())
        if not dropped:
            continue
        if samples:
            corridor["speed_limits"] = samples
        else:
            # Every sample was street pollution: drop the profile entirely so
            # the runtime falls back to the highway/region heuristic.
            del corridor["speed_limits"]
        repaired.append(
            {
                "leg": f"{leg['from']}-{leg['to']}",
                "highway": leg["highway"],
                "dropped": [{"at_mi": d["at_mi"], "mph": d["mph"]} for d in dropped],
                "kept": len(samples),
            }
        )
    return repaired


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="write world.json (default: dry run)")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = parser.parse_args()

    data = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    repaired = repair(data)

    if args.json:
        print(json.dumps(repaired, indent=2))
    else:
        for entry in repaired:
            drops = ", ".join(f"{d['mph']:.0f} mph at mile {d['at_mi']}" for d in entry["dropped"])
            print(f"{entry['leg']} ({entry['highway']}): dropped {drops}; {entry['kept']} samples kept")
    print(f"\n{len(repaired)} interstate legs repaired ({'written' if args.write else 'dry run'})")

    if args.write and repaired:
        WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
