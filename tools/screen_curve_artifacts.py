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

The discriminator
------------------
Terrain, not road class. A hairpin-severity curve (the same test
``RouteCurve.severity`` uses: advisory <= 25 mph or deflection >= 150 deg)
sitting on demonstrably FLAT local ground is not a real switchback -- no
real hairpin exists without a hill to switch back on. This reuses the exact
terrain verdict ``reclassify_terrain.py`` already computes from the dense
archived elevation profile (``world_data/us/geometry/``) and the shared
``terrain_rules`` thresholds, so "flat" here means the same thing it means
everywhere else in the data. Curves in "hills" or "mountain" local terrain
are left alone even when very sharp -- that is real geography (rolling
two-lanes in the Ozarks, real climbs), and the recipe's rule holds: never
delete without a strong, specific signal.

Verified against known cases before fanning out (see the tool's own
``--report``): the Denver-departure kink on US-40 (mile 1.7, flat) is
flagged; the mid-canyon US-40 hairpin over the Rockies foothills (mile
104, hills) is not; every US-550 Million Dollar Highway switchback and
every Salt River Canyon (Globe->Show Low, US-60) switchback reads
"mountain" and survives untouched.

Output
------
Like ``ramps.jsonl`` and ``speed_limits.jsonl``, this is a small sibling
gameplay table under ``world_data/us/gameplay/`` -- NOT an edit to
``curves.jsonl``. The raw bake keeps every row (existing invariant); flagged
records are named in ``curve_artifacts.jsonl`` by ``(leg, seq)`` and
``data/curves.py`` skips them on load, exactly like the interstate screen
skips its records in memory rather than rewriting the archive.

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
HAIRPIN_MAX_MPH = 25
HAIRPIN_DEFLECTION_DEG = 150.0

REASON = "flat local terrain at the curve's apex -- sweep artifact, not a real switchback"
SOURCE = (
    "data/curves.py hairpin-severity definition (advisory<=25mph or "
    "deflection>=150deg) intersected with reclassify_terrain.py's terrain "
    "verdict from the dense archived elevation profile; flat local ground "
    "cannot hold a real hairpin. Development-time screen, see "
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


def _is_hairpin_severity(row: dict[str, Any]) -> bool:
    return row["advisory_mph"] <= HAIRPIN_MAX_MPH or row["deflection_deg"] >= HAIRPIN_DEFLECTION_DEG


def find_artifacts(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Every non-interstate mainline hairpin-severity curve on flat ground.

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
        candidates = [r for r in rows if not r.get("connector") and _is_hairpin_severity(r)]
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

        for row in candidates:
            terrain = classify_point(profile, row["apex_mi"])
            if terrain != "flat":
                continue
            # Every row shares one reason and one source (the discriminator
            # is uniform); those live once in the meta header, not repeated
            # 900+ times, so a row stays exactly as lean as a curves.jsonl row.
            flagged.append(
                {
                    "leg": leg_key,
                    "seq": row["seq"],
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
            "schema": 1,
            "data_version": data_version,
            "layer": "curve_artifacts",
            "reason": REASON,
            "source": SOURCE,
            "params": {
                "hairpin_max_mph": HAIRPIN_MAX_MPH,
                "hairpin_deflection_deg": HAIRPIN_DEFLECTION_DEG,
            },
        }
    }
    lines = [json.dumps(meta, sort_keys=True)]
    lines.extend(json.dumps(row, sort_keys=True) for row in flagged)
    return "\n".join(lines) + "\n"


def _report(flagged: list[dict[str, Any]]) -> None:
    by_leg: dict[str, list[dict[str, Any]]] = {}
    for row in flagged:
        by_leg.setdefault(row["leg"], []).append(row)
    print(f"{len(flagged)} flat-terrain hairpin artifact(s) across {len(by_leg)} leg(s):")
    for leg_key in sorted(by_leg):
        rows = by_leg[leg_key]
        highway = rows[0]["highway"]
        miles = ", ".join(f"{r['apex_mi']:.2f}" for r in rows)
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
