"""Repair interstate speed-limit profiles polluted by city-street samples.

The maxspeed bake samples each checked-in route point inside a 400 m box and
prefers a way matching the leg's highway shield -- but at the mile-0 and
end-of-leg city anchors the interstate itself is often outside the box, so
the fallback ("highest posted limit found") bakes a city arterial's 25-40
onto the corridor, and the step function then holds that street value for
miles of interstate (owner-found live: I-10 Buckeye-Phoenix enforced 30 mph
for ten miles).

No posted US interstate mainline runs below 45 mph, so on interstate-class
legs a sample under 45 is a wrong-road match, never a real limit -- at ANY
position. The 2026-07-14 pass dropped only leading and trailing (anchor)
samples and left interior ones alone; a player then found the interior
class live on I-55 toward Memphis (a mid-leg 40 from a snapped side-road
way, enforced on the mainline), and a census showed 147 such samples
map-wide. This repair now drops every sub-45 sample from interstate legs'
``corridor.speed_limits``; the step function heals itself (the runtime
holds the previous surviving sample across the gap, and the first sample
back to mile 0). Non-interstate highways keep their honest small-town 30s.
Offline and deterministic -- no Overpass required.

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


# On US highways and state routes a 25-40 sample is often honest -- the
# corridor really does run down a town's main street -- so only the mile-0
# anchor sample is suspect, and only when the corridor's own character
# contradicts it: the next sample fast (55+) and far enough out that the
# street value would own miles of highway (US-60 out of Phoenix held a baked
# 25 for 22 miles of the Superstition Freeway).
SURFACE_ANCHOR_MAX_MPH = 45.0
SURFACE_NEXT_MIN_MPH = 55.0
SURFACE_MIN_SPAN_MI = 5.0
SURFACE_SOLE_SAMPLE_MIN_LEG_MI = 15.0


def repair(data: dict) -> list[dict]:
    repaired: list[dict] = []
    for leg in data["legs"]:
        corridor = leg.get("corridor") or {}
        samples = corridor.get("speed_limits")
        if not samples:
            continue
        dropped: list[dict] = []
        if is_interstate(leg.get("highway", "")):
            kept_samples = [s for s in samples if s["mph"] >= INTERSTATE_MIN_PLAUSIBLE_MPH]
            if len(kept_samples) != len(samples):
                dropped.extend(s for s in samples if s["mph"] < INTERSTATE_MIN_PLAUSIBLE_MPH)
                samples[:] = kept_samples
        elif (
            len(samples) >= 2
            and samples[0]["at_mi"] == 0.0
            and samples[0]["mph"] < SURFACE_ANCHOR_MAX_MPH
            and samples[1]["mph"] >= SURFACE_NEXT_MIN_MPH
            and samples[1]["at_mi"] >= SURFACE_MIN_SPAN_MI
        ) or (
            # A lone sub-45 anchor sample owning a long leg: the sweep found
            # maxspeed only at the city anchor (Globe's 35 ruled all 88 miles
            # to Show Low), so the whole profile is street pollution. Dropping
            # it hands the leg back to the highway/region heuristic, which is
            # honest where a town street value is not. Short town-to-town hops
            # keep their limits -- 35 the whole way is real on those.
            len(samples) == 1
            and leg.get("miles", 0.0) >= SURFACE_SOLE_SAMPLE_MIN_LEG_MI
            and samples[0]["mph"] < SURFACE_ANCHOR_MAX_MPH
            and samples[0]["at_mi"] in (0.0, leg.get("miles"))
        ):
            dropped.append(samples.pop(0))
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
            print(
                f"{entry['leg']} ({entry['highway']}): dropped {drops}; {entry['kept']} samples kept"
            )
    print(f"\n{len(repaired)} interstate legs repaired ({'written' if args.write else 'dry run'})")

    if args.write and repaired:
        WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
