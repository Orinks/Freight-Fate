"""Bake FHWA HPMS Terrain_Type onto legs as ``corridor.hpms_terrain``.

Development-time helper (never called at runtime). For every leg with route
geometry it asks the national HPMS layer what terrain the road really runs
through and records the answer per leg.

WHY THIS EXISTS. The curve screen in ``data/curves.py`` needs to know whether
a leg is flat enough for a tight bend to be an artifact rather than the road.
It used the world's own ``terrain`` field, which is derived from NET
elevation change end to end and so calls I-70 through Glenwood Canyon "flat";
that screen took 21 real curves off the canyon. The replacement proxy --
feet of elevation range per mile -- was calibrated against this same HPMS
field on a 92-leg sample and came out a WEAK discriminator: Youden's J of
0.29, and at the chosen cut it mislabelled 54 percent of rolling and
mountainous legs. So the proxy was abandoned and the real classification
baked instead.

PROVENANCE. ``type`` is READ -- HPMS asserts it, we do not compute it. What
is DERIVED is which one value stands for a whole leg: HPMS classifies road
sections, a leg crosses many, and this takes the modal class over the
sections intersecting the leg's bounding box. That is recorded in the source
string rather than left for a reader to assume.

Run from the repo root:
    uv run python tools/build_terrain_type.py               # report only
    uv run python tools/build_terrain_type.py --write       # update the source

After a --write run, regenerate the runtime tree:
    uv run python tools/index_world.py
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from world_source import load_world, save_world  # noqa: E402

HPMS_QUERY_URL = (
    "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/"
    "hpms_v2_view/FeatureServer/0/query"
)
# 1/2/3 are the Green Book terrain classes HPMS carries. Verified against the
# data rather than taken on trust: Glenwood Canyon (I-70 CO) and US-550 at
# Silverton both return 3, and I-10 across the Mobile-to-New-Orleans coastal
# plain returns 1.
TERRAIN_NAMES = {1: "level", 2: "rolling", 3: "mountainous"}
HPMS_SOURCE = (
    "FHWA Highway Performance Monitoring System (HPMS) Terrain_Type, read from "
    "the national ArcGIS Living Atlas layer (Federal User Community "
    "hpms_v2_view). The class is HPMS's own; DERIVED here only in that one "
    "value stands for a whole leg -- the modal class over the HPMS sections "
    "intersecting the leg's bounding box, since HPMS classifies sections and a "
    "leg crosses many. Accessed 2026-08-19: "
    "https://www.fhwa.dot.gov/policyinformation/hpms.cfm"
)


def _bbox(leg: dict[str, Any]) -> tuple[float, float, float, float] | None:
    pts = (leg.get("corridor") or {}).get("route_points") or ()
    coords = [(p["lat"], p["lon"]) for p in pts if isinstance(p, dict)]
    if len(coords) < 2:
        return None
    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    return (min(lons), min(lats), max(lons), max(lats))


def _query_terrain(env: tuple[float, float, float, float]) -> Counter:
    params = urllib.parse.urlencode(
        {
            "where": "Terrain_Type IS NOT NULL",
            "geometry": ",".join(f"{v:.5f}" for v in env),
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "outSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "Terrain_Type",
            "returnGeometry": "false",
            "resultRecordCount": 800,
            "f": "json",
        }
    )
    with urllib.request.urlopen(f"{HPMS_QUERY_URL}?{params}", timeout=90) as fh:
        data = json.loads(fh.read())
    return Counter(
        f["attributes"]["Terrain_Type"]
        for f in data.get("features", ())
        if f.get("attributes", {}).get("Terrain_Type") in TERRAIN_NAMES
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bake HPMS terrain class onto legs.")
    parser.add_argument("--write", action="store_true", help="Write into the world source.")
    parser.add_argument("--force", action="store_true", help="Re-bake legs that already have one.")
    parser.add_argument("--max-legs", type=int, default=0)
    args = parser.parse_args(argv)

    data = load_world()
    targets = []
    for leg in data["legs"]:
        corridor = leg.get("corridor", {})
        if corridor.get("hpms_terrain") and not args.force:
            continue
        if _bbox(leg) is None:
            continue
        if not args.max_legs or len(targets) < args.max_legs:
            targets.append(leg)
    if not targets:
        print("No legs need a terrain class (use --force to redo).")
        return 0

    baked = 0
    agree = disagree = 0
    counts: Counter = Counter()
    for i, leg in enumerate(targets, start=1):
        env = _bbox(leg)
        try:
            found = _query_terrain(env)
        except Exception as exc:  # noqa: BLE001 - one bad leg must not abort the crawl
            print(f"[{i}/{len(targets)}] {leg['from']}->{leg['to']} skipped: {exc}", flush=True)
            continue
        if not found:
            print(f"[{i}/{len(targets)}] {leg['from']}->{leg['to']} no HPMS terrain", flush=True)
            continue
        kind = found.most_common(1)[0][0]
        counts[kind] += 1
        leg.setdefault("corridor", {})["hpms_terrain"] = {
            "type": int(kind),
            "name": TERRAIN_NAMES[kind],
            "sections": int(sum(found.values())),
            "source": HPMS_SOURCE,
        }
        baked += 1
        # How often the world's own label agrees with the real thing, which is
        # the number that justified this bake in the first place.
        was_flat = str(leg.get("terrain", "")) == "flat"
        if was_flat == (kind == 1):
            agree += 1
        else:
            disagree += 1
        if i % 25 == 0:
            print(f"[{i}/{len(targets)}] baked {baked}", flush=True)
        if args.write and baked and i % 50 == 0:
            save_world(data)
            print("    ...checkpointed the world source", flush=True)

    print(f"\n{len(targets)} legs processed, {baked} baked.")
    for kind, n in sorted(counts.items()):
        print(f"  {TERRAIN_NAMES[kind]:12s} {n:>5d}")
    total = agree + disagree
    if total:
        print(
            f"\nthe world's own flat/not-flat label agreed with HPMS on "
            f"{agree}/{total} legs ({100 * agree / total:.0f}%)"
        )
    if args.write:
        save_world(data)
        print("world source updated; run tools/index_world.py next.")
    else:
        print("(dry run; pass --write to update the world source)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
