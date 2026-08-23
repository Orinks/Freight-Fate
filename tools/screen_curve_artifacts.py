"""Screen US/state-route curve artifacts the interstate screen can't reach.

Background
----------
``data/curves.py`` already drops interstate-mainline curve records that are
too sharp for an interstate to physically hold (radius < 300 ft or
deflection >= 150 deg) -- sweep artifacts from city-departure geometry and
interchange vertices baked as if they were mainline (ROADMAP, "Screen
artifact curves out of the highway bake", shipped 2026-08-09). That screen is
gated on highway class alone, because on an interstate NOTHING that sharp is
real. US and state routes are different: US-550 over Red Mountain Pass and
the Salt River Canyon on US-60 have hundreds of genuine sub-300-ft hairpins,
so gating on class would delete real switchbacks. The shipped screen's own
notes flagged the gap: "the same Denver departure artifact rides the US-40
leg, and no measured signal separates artifact from real switchback on that
class -- a future US/state pass needs a different discriminator."

The discriminators
------------------
All three ask the same question -- could a road of this class physically hold
this bend here? -- of a hairpin-severity curve (the same test
``RouteCurve.severity`` uses: advisory <= 25 mph or deflection >= 150 deg).
None of them looks at road class, because US and state routes really do
switch back.

``flat`` -- the curve sits on demonstrably FLAT local ground. No real hairpin
exists without a hill to switch back on. This reuses the exact terrain verdict
``reclassify_terrain.py`` computes from the dense archived elevation profile
(``world_data/us/geometry/``) and the shared ``terrain_rules`` thresholds, so
"flat" here means what it means everywhere else in the data.

``leg_end`` -- the curve sits within ``LEG_END_MI`` of either end of the leg,
on ground that is not "mountain". A leg ends at a city node, and the bake
stitches city-departure street geometry onto the mainline there; that is the
same artifact ``flat`` was built for, and terrain alone cannot see it once the
city sits on rolling ground. Mountain terrain is spared because a town in the
mountains really can have a switchback on its doorstep (US-119 out of
Charleston, KY-80 out of Hazard, US-95 out of Lewiston -- all preserved).

``radius`` -- the curve is tighter than ``MIN_ROAD_RADIUS_FT``, anywhere on
any leg. This is the sibling of the interstate screen's 300 ft floor, set
instead at the point no through highway of any class can bend: 50 ft is
tighter than a loaded tractor-trailer's own turning circle. The floor is
grounded in the data rather than assumed -- the tightest genuine switchback
the world carries is 54 ft (US-550 over Red Mountain Pass, mile 60.5), and
nothing in mountain terrain falls below the floor at all.

Verified against known cases before fanning out (see the tool's own
``--report``): the Denver-departure kink on US-40 (mile 1.7, flat) is
flagged; the mid-canyon US-40 hairpin over the Rockies foothills (mile
104, hills) is not; every US-550 Million Dollar Highway switchback and
every Salt River Canyon (Globe->Show Low, US-60) switchback reads
"mountain" and survives untouched. Across the whole world the three screens
together flag nothing in mountain terrain, which is the property to check
first if these thresholds are ever moved.

Output
------
Like ``ramps.jsonl`` and ``speed_limits.jsonl``, this is a small sibling
gameplay table under ``world_data/us/gameplay/`` -- NOT an edit to
``curves.jsonl``. The raw bake keeps every row (existing invariant); flagged
records are named in ``curve_artifacts.jsonl`` by ``(leg, seq)`` and
``data/curves.py`` skips them on load, exactly like the interstate screen
skips its records in memory rather than rewriting the archive.

THE ORDER MATTERS, AND NOTHING ENFORCES IT
------------------------------------------
These four passes form a chain, each reading the output of the last. Run them
in this order after any change to the curve data::

    uv run python tools/curve_valhalla_facts.py --all      # what road is it on
    uv run python tools/bake_curve_connectors.py --write   # mainline or connector
    uv run python tools/clamp_curve_advisories.py --write  # cap the advisory
    uv run python tools/screen_curve_artifacts.py          # drop impossible geometry

Skipping the last one has now stranded ``curve_artifacts.jsonl`` twice in a
single session. It names rows by ``(leg, seq)`` and only considers non-connector
rows, so the moment ``connector`` moves it can silently stop covering a row it
used to screen -- which is how a 44 ft radius turning 182 degrees survived as
mainline on US-30 out of Columbus. A stale screen does not announce itself; it
just quietly stops catching things.

Usage
-----
    uv run python tools/screen_curve_artifacts.py             # write + report
    uv run python tools/screen_curve_artifacts.py --check      # report only, exit 1 if stale
    uv run python tools/screen_curve_artifacts.py --report     # human-readable breakdown, no write
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reclassify_terrain import (  # noqa: E402  (path shim above must run first)
    GEOMETRY_DIR,
    MEDIAN_MI,
    classify_point,
    decode_profile,
    median_filter,
)
from world_source import load_world  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CURVES_PATH = (
    ROOT / "src" / "freight_fate" / "data" / "world_data" / "us" / "gameplay" / "curves.jsonl"
)
OUTPUT_PATH = (
    ROOT
    / "src"
    / "freight_fate"
    / "data"
    / "world_data"
    / "us"
    / "gameplay"
    / "curve_artifacts.jsonl"
)

# Same definition data/curves.py's RouteCurve.severity uses for "hairpin" --
# import-free copy so this tool has no runtime dependency on the baked data
# module (mirrors reclassify_terrain.py's own world_source-only imports).
# The screen's own question is "could a road here really do this?", so it
# keeps the BROAD test: a very low advisory is an extreme claim about the
# ground whether or not the road comes back on itself. That is deliberately
# not the spoken hairpin test, which MUTCD settles on shape alone (see
# data/curves.py HAIRPIN_DEFLECTION_DEG). One predicate was doing both jobs
# and they want different answers.
HAIRPIN_MAX_MPH = 25
HAIRPIN_DEFLECTION_DEG = 150.0

# How close to a leg's city node counts as departure geometry rather than
# mainline, and the radius no through highway of any class can hold.
LEG_END_MI = 2.5
MIN_ROAD_RADIUS_FT = 50

REASONS = {
    "flat": "flat local terrain at the curve's apex -- sweep artifact, not a real switchback",
    "leg_end": (
        "within 2.5 miles of the leg's city node on non-mountain ground -- "
        "city-departure geometry baked as mainline"
    ),
    "radius": (
        "tighter than 50 feet of radius -- no through highway of any class "
        "bends that hard, digitizing artifact"
    ),
}
SOURCE = (
    "data/curves.py hairpin-severity definition (advisory<=25mph or "
    "deflection>=150deg) intersected with reclassify_terrain.py's terrain "
    "verdict from the dense archived elevation profile, the leg's own city "
    "nodes, and a physical radius floor. Development-time screen, see "
    "tools/screen_curve_artifacts.py."
)


def _load_curves() -> dict[str, list[dict[str, Any]]]:
    by_leg: dict[str, list[dict[str, Any]]] = {}
    with CURVES_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "meta" in row:
                continue
            by_leg.setdefault(row["leg"], []).append(row)
    return by_leg


def _load_geometry() -> dict[str, dict[str, Any]]:
    geom: dict[str, dict[str, Any]] = {}
    for shard in sorted(GEOMETRY_DIR.glob("*.jsonl")):
        for i, line in enumerate(shard.read_text(encoding="utf-8").splitlines()):
            if i == 0 or not line.strip():
                continue
            rec = json.loads(line)
            geom[rec["leg"]] = rec
    return geom


def _is_extreme_claim(row: dict[str, Any]) -> bool:
    """Whether this row claims geometry worth asking the ground about."""
    return row["advisory_mph"] <= HAIRPIN_MAX_MPH or row["deflection_deg"] >= HAIRPIN_DEFLECTION_DEG


def _artifact_reason(row: dict[str, Any], terrain: str, leg_miles: float) -> str | None:
    """Which discriminator, if any, says this curve cannot be real here."""
    if terrain == "flat":
        return "flat"
    apex = float(row["apex_mi"])
    near_end = apex <= LEG_END_MI or (leg_miles > 0.0 and apex >= leg_miles - LEG_END_MI)
    if near_end and terrain != "mountain":
        return "leg_end"
    if row["min_radius_ft"] < MIN_ROAD_RADIUS_FT:
        return "radius"
    return None


def find_artifacts(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Every non-interstate mainline hairpin-severity curve no road can hold.

    Returns rows sorted by (leg, seq) -- the file's deterministic order.
    """
    legs_by_key = {f"{leg['from']}:{leg['to']}": leg for leg in data["legs"]}
    curves_by_leg = _load_curves()
    geom_by_leg = _load_geometry()

    flagged: list[dict[str, Any]] = []
    profile_cache: dict[str, list[tuple[float, float]] | None] = {}

    for leg_key, rows in sorted(curves_by_leg.items()):
        leg = legs_by_key.get(leg_key)
        if leg is None:
            continue
        highway = str(leg.get("highway") or "")
        if highway.upper().startswith("I-"):
            continue  # interstate mainline has its own runtime screen
        candidates = [r for r in rows if not r.get("connector") and _is_extreme_claim(r)]
        if not candidates:
            continue

        if leg_key not in profile_cache:
            rec = geom_by_leg.get(leg_key)
            if rec is None:
                profile_cache[leg_key] = None
            else:
                leg_miles = float(leg.get("miles") or rec.get("miles") or 0.0)
                profile_cache[leg_key] = median_filter(
                    decode_profile(rec["geom"], leg_miles), MEDIAN_MI
                )
        profile = profile_cache[leg_key]
        if profile is None:
            continue  # no geometry archive coverage; nothing to classify from

        leg_miles = float(leg.get("miles") or 0.0)
        for row in candidates:
            terrain = classify_point(profile, row["apex_mi"])
            why = _artifact_reason(row, terrain, leg_miles)
            if why is None:
                continue
            # The reason texts and the source live once in the meta header,
            # not repeated a thousand times; a row carries only the short key
            # that selects one, so it stays as lean as a curves.jsonl row.
            flagged.append(
                {
                    "leg": leg_key,
                    "seq": row["seq"],
                    "why": why,
                    "start_mi": row["start_mi"],
                    "apex_mi": row["apex_mi"],
                    "end_mi": row["end_mi"],
                    "direction": row["direction"],
                    "advisory_mph": row["advisory_mph"],
                    "min_radius_ft": row["min_radius_ft"],
                    "deflection_deg": row["deflection_deg"],
                    "highway": highway,
                }
            )
    flagged.sort(key=lambda r: (r["leg"], r["seq"]))
    return flagged


def _dumps_rows(flagged: list[dict[str, Any]]) -> str:
    payload = "\n".join(json.dumps(row, sort_keys=True) for row in flagged)
    data_version = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    meta = {
        "meta": {
            "schema": 2,
            "data_version": data_version,
            "layer": "curve_artifacts",
            "reasons": REASONS,
            "source": SOURCE,
            "params": {
                "hairpin_max_mph": HAIRPIN_MAX_MPH,
                "hairpin_deflection_deg": HAIRPIN_DEFLECTION_DEG,
                "leg_end_mi": LEG_END_MI,
                "min_road_radius_ft": MIN_ROAD_RADIUS_FT,
            },
        }
    }
    lines = [json.dumps(meta, sort_keys=True)]
    lines.extend(json.dumps(row, sort_keys=True) for row in flagged)
    return "\n".join(lines) + "\n"


def _report(flagged: list[dict[str, Any]]) -> None:
    by_leg: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}
    for row in flagged:
        by_leg.setdefault(row["leg"], []).append(row)
        counts[row["why"]] = counts.get(row["why"], 0) + 1
    breakdown = ", ".join(f"{counts.get(why, 0)} {why}" for why in REASONS)
    print(f"{len(flagged)} hairpin artifact(s) across {len(by_leg)} leg(s): {breakdown}")
    for leg_key in sorted(by_leg):
        rows = by_leg[leg_key]
        highway = rows[0]["highway"]
        miles = ", ".join(f"{r['apex_mi']:.2f} ({r['why']})" for r in rows)
        print(f"  {leg_key} ({highway}): {len(rows)} at mile(s) {miles}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report without writing; exit 1 if curve_artifacts.jsonl is stale.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print the human-readable breakdown without writing.",
    )
    args = parser.parse_args(argv)

    data = load_world()
    flagged = find_artifacts(data)
    text = _dumps_rows(flagged)

    _report(flagged)

    if args.report:
        return 0

    current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else None
    if current == text:
        print(f"\n{OUTPUT_PATH} is already up to date.")
        return 0

    if args.check:
        print(f"\n{OUTPUT_PATH} is stale; run `uv run python tools/screen_curve_artifacts.py`.")
        return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(text, encoding="utf-8")
    print(f"\nWrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
