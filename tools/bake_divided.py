"""Bake a per-leg ``divided`` flag from real OSM carriageway geometry.

Curve navigation (Track B) needs to know whether a leg's road is a divided
highway (the LEFT edge is a median) or undivided (the left edge is the
centerline with oncoming traffic). Today only ``lanes`` is baked and the
runtime infers divided from road class; this bakes the truth for the
ambiguous middle (multilane US/state highways).

Signal: OSM maps a divided carriageway as paired ``oneway=yes`` ways and an
undivided road as a single two-way way. (``dual_carriageway``/``divider`` tags
are essentially unused in US OSM -- verified -- so ``oneway`` is the signal.)
Per leg we walk the archived route geometry, match each ~0.25 mi point to the
nearest shield-matching corridor way from the state PBF, and take the fraction
of matched mainline miles that ride a oneway carriageway.

Source: the local per-state Geofabrik PBF cache (``~/.cache/freight-fate-osm``)
via osmium -- the corridor ways carry ``oneway`` with complete geometry, and
the extract is offline and deterministic. (The self-hosted Overpass corridor
extract also carries corridor ``oneway``, but the PBF is the authoritative,
complete source, per the track spec.)

HONEST ABSENCE: a leg whose matched mainline is a clear oneway majority is
``divided: true``; a clear two-way majority is ``divided: false``; a genuinely
mixed leg, or one with too little matched mainline to judge, gets NO field --
the runtime's road-class inference stays the fallback there.

  uv run --group tooling python tools/bake_divided.py --state az            # dry run
  uv run --group tooling python tools/bake_divided.py --all --write
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import osmium

sys.path.insert(0, str(Path(__file__).resolve().parent))

import straw_curve_sample as scs  # noqa: E402  (decode + matcher primitives)
from world_source import load_world, save_world  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GEOM_DIR = ROOT / "src" / "freight_fate" / "data" / "world_data" / "us" / "geometry"
CACHE_DIR = Path(os.environ.get("FF_OSM_CACHE", Path.home() / ".cache" / "freight-fate-osm" / "regions"))

CORRIDOR_CLASSES = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "motorway_link",
    "trunk_link",
    "primary_link",
}
SAMPLE_STEP_M = 402.0  # ~0.25 mi between matched samples
MATCH_M = scs.MATCH_CORRIDOR_M  # a way farther than this from the route does not govern
DIVIDED_HI = 0.60  # >= this fraction of matched miles oneway -> divided
DIVIDED_LO = 0.40  # <= this -> undivided; the 0.4-0.6 band is a genuine mix -> omit
#                    (a per-leg bool would mislead there; road-class inference stays)
MIN_MATCHED_MI = 2.0  # too little matched mainline to judge -> omit
SOURCE_NOTE = "OSM carriageway oneway geometry (Geofabrik PBF, offline), development-time."

STATE_SLUGS = {"District of Columbia": "district-of-columbia"}


def state_slug(state: str) -> str:
    return STATE_SLUGS.get(state, state.lower().replace(" ", "-"))


def _oneway(tags: dict[str, str]) -> bool:
    return str(tags.get("oneway", "")).strip().lower() in ("yes", "true", "1", "-1")


# --- geometry archive: decode per-leg route coords --------------------------
def load_geometry_by_code(code: str) -> dict[str, list[list[float]]]:
    path = GEOM_DIR / f"{code}.jsonl"
    out: dict[str, list[list[float]]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith('{"meta"'):
            continue
        rec = json.loads(line)
        out[rec["leg"]] = scs.decode_geometry(rec["geom"])
    return out


# --- collect corridor ways from the state PBF, bucketed to legs -------------
def _leg_bbox(coords: list[list[float]], pad: float = 0.02) -> tuple[float, float, float, float]:
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (min(lats) - pad, max(lats) + pad, min(lons) - pad, max(lons) + pad)


def _bbox_intersect(a, b) -> bool:
    return not (a[1] < b[0] or b[1] < a[0] or a[3] < b[2] or b[3] < a[2])


def build_grid(leg_boxes: dict[str, tuple]) -> dict[tuple[int, int], list[str]]:
    """Coarse 0.1-degree grid: cell -> leg ids whose bbox covers it, so a way's
    candidate legs are a dict lookup rather than a scan of every leg."""
    grid: dict[tuple[int, int], list[str]] = {}
    for lid, box in leg_boxes.items():
        for row in range(math.floor(box[0] * 10), math.floor(box[1] * 10) + 1):
            for col in range(math.floor(box[2] * 10), math.floor(box[3] * 10) + 1):
                grid.setdefault((row, col), []).append(lid)
    return grid


def collect_ways(
    pbf_path: Path,
    leg_boxes: dict[str, tuple],
    grid: dict[tuple[int, int], list[str]],
    ways_by_leg: dict[str, list[dict]],
) -> None:
    """Stream one state PBF and append its shield-tagged corridor ways to every
    overlapping leg's bucket. Accumulates across states so a leg that crosses a
    state line is judged over its whole length, not just its from-state slice."""
    processor = (
        osmium.FileProcessor(str(pbf_path), entities=osmium.osm.osm_entity_bits.NODE | osmium.osm.osm_entity_bits.WAY)
        .with_locations()
        .with_filter(osmium.filter.KeyFilter("highway"))
    )
    for way in processor:
        if not hasattr(way, "nodes"):
            continue
        tags = {str(t.k): str(t.v) for t in way.tags}
        if tags.get("highway") not in CORRIDOR_CLASSES:
            continue
        ref = tags.get("ref", "")
        if not ref:
            continue  # unmatched-shield ways cannot be trusted as the mainline
        pts = []
        for node in way.nodes:
            try:
                if node.location.valid():
                    pts.append({"lat": float(node.location.lat), "lon": float(node.location.lon)})
            except osmium.InvalidLocationError:
                continue
        if len(pts) < 2:
            continue
        cand: set[str] = set()
        for p in pts:
            cand.update(grid.get((math.floor(p["lat"] * 10), math.floor(p["lon"] * 10)), ()))
        if not cand:
            continue
        wbox = (
            min(p["lat"] for p in pts),
            max(p["lat"] for p in pts),
            min(p["lon"] for p in pts),
            max(p["lon"] for p in pts),
        )
        record = {
            "geometry": pts,
            "ref": ref,
            "oneway": _oneway(tags),
            "link": tags.get("highway", "").endswith("_link"),
        }
        for lid in cand:
            if _bbox_intersect(wbox, leg_boxes[lid]):
                ways_by_leg[lid].append(record)


# --- per-leg divided decision -----------------------------------------------
def divided_fraction(
    coords: list[list[float]],
    cum_m: list[float],
    mile_scale: float,
    ways: list[dict],
    shield_nums: set[str],
) -> tuple[float, float]:
    """(oneway fraction of matched miles, matched miles) for the road the route
    actually rides. Shield-preferred so the leg's own highway wins ties, but
    with a nearest-corridor fallback: many legs are labeled by their headline
    highway yet routed along a parallel road (Huntsville->Nashville is tagged
    I-65 but runs US-231), and the divided question is about the pavement under
    the truck, not the label. Ramps (``_link``) never define the character."""
    lats = [c[1] for c in coords]
    coslat = math.cos(math.radians(sum(lats) / len(lats)))
    step_mi = SAMPLE_STEP_M / 1609.344 * mile_scale
    oneway_mi = matched_mi = 0.0
    last_m = -1e9
    for i, (lon, lat) in enumerate(coords):
        is_last = i == len(coords) - 1
        if cum_m[i] - last_m < SAMPLE_STEP_M and not is_last:
            continue
        last_m = cum_m[i]
        best: bool | None = None
        best_on_shield = False
        best_dist = MATCH_M
        for way in ways:
            if way["link"]:
                continue
            on_shield = scs._ref_matches_shield(way["ref"], shield_nums)
            geom = way["geometry"]
            for a, b in zip(geom, geom[1:], strict=False):
                d = scs._point_seg_dist_m(lat, lon, a, b, coslat)
                if d > best_dist:
                    continue
                if on_shield and not best_on_shield:
                    best, best_on_shield, best_dist = way["oneway"], True, d
                elif on_shield == best_on_shield and (best is None or d < best_dist):
                    best, best_dist = way["oneway"], d
        if best is None:
            continue
        matched_mi += step_mi
        if best:
            oneway_mi += step_mi
    frac = oneway_mi / matched_mi if matched_mi else 0.0
    return frac, matched_mi


def decide(frac: float, matched_mi: float) -> bool | None:
    if matched_mi < MIN_MATCHED_MI:
        return None
    if frac >= DIVIDED_HI:
        return True
    if frac <= DIVIDED_LO:
        return False
    return None  # genuinely mixed -> omit, road-class inference stays the fallback


# --- driver -----------------------------------------------------------------
def select_legs(world: dict, args) -> list[dict]:
    legs = world["legs"]
    cities = world["cities"]
    if args.only:
        wanted = {tuple(p.split(":")) for p in args.only.split(";") if ":" in p}
        return [L for L in legs if (L["from"], L["to"]) in wanted or (L["to"], L["from"]) in wanted]
    if args.state:
        st = args.state.lower()
        return [L for L in legs if str(cities.get(L["from"], {}).get("state", "")).lower() == st]
    return list(legs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--only", help="semicolon slug pairs a:b;c:d")
    g.add_argument("--state", help="two-letter state code, e.g. az")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--write", action="store_true", help="save via world_source (default dry run)")
    ap.add_argument("--json-out", help="write per-leg report")
    args = ap.parse_args()

    world = load_world()
    cities = world["cities"]
    legs = select_legs(world, args)
    legs.sort(key=lambda L: (L["from"], L["to"]))
    leg_index = {(L["from"], L["to"]): L for L in world["legs"]}
    print(f"selected {len(legs)} legs | write={args.write}", flush=True)

    # Per-leg route coords come from the from-state geometry shard (the archive
    # stores each leg whole in its from-state file), but the ROADS come from
    # every state the route touches, so a cross-state leg is judged end to end.
    geom_cache: dict[str, dict[str, list[list[float]]]] = {}
    leg_coords: dict[str, list[list[float]]] = {}
    leg_boxes: dict[str, tuple] = {}
    needed_codes: set[str] = set()
    counts = {"divided": 0, "undivided": 0, "omit": 0, "no_geom": 0, "no_pbf": 0}
    for L in legs:
        lid = f"{L['from']}:{L['to']}"
        from_code = str(cities[L["from"]]["state"]).lower()
        if from_code not in geom_cache:
            geom_cache[from_code] = load_geometry_by_code(from_code)
        coords = geom_cache[from_code].get(lid)
        if not coords or len(coords) < 2:
            counts["no_geom"] += 1
            continue
        leg_coords[lid] = coords
        leg_boxes[lid] = _leg_bbox(coords)
        needed_codes.add(from_code)
        needed_codes.add(str(cities[L["to"]]["state"]).lower())

    grid = build_grid(leg_boxes)
    ways_by_leg: dict[str, list[dict]] = {lid: [] for lid in leg_boxes}
    for code in sorted(needed_codes):
        full = _CODE_TO_NAME.get(code, code)
        pbf = CACHE_DIR / f"{state_slug(full)}-latest.osm.pbf"
        if not pbf.exists():
            print(f"  PBF missing: {pbf.name}", flush=True)
            continue
        collect_ways(pbf, leg_boxes, grid, ways_by_leg)
        print(f"  scanned {code}", flush=True)

    report: list[dict] = []
    for L in legs:
        lid = f"{L['from']}:{L['to']}"
        if lid not in leg_coords:
            continue
        coords = leg_coords[lid]
        cum = scs._cumulative_m(coords)
        raw_mi = cum[-1] / 1609.344
        leg_miles = float(L.get("miles", 0)) or None
        mile_scale = (leg_miles / raw_mi) if leg_miles and raw_mi else 1.0
        shield = scs._shield_numbers(L.get("highway", ""))
        frac, matched = divided_fraction(coords, cum, mile_scale, ways_by_leg.get(lid, []), shield)
        verdict = decide(frac, matched)
        target = leg_index[(L["from"], L["to"])]
        if verdict is None:
            target.pop("divided", None)
            counts["omit"] += 1
        else:
            target["divided"] = verdict
            counts["divided" if verdict else "undivided"] += 1
        report.append(
            {"leg": lid, "highway": L.get("highway"), "oneway_frac": round(frac, 2),
             "matched_mi": round(matched, 1), "divided": verdict}
        )

    if args.write:
        save_world(world)
        print("saved world source", flush=True)
    print(f"\nDONE: {counts}", flush=True)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps({"counts": counts, "legs": report}, indent=2), encoding="utf-8")
        print(f"wrote {args.json_out}", flush=True)
    return 0


_CODE_TO_NAME = {
    "al": "Alabama", "ak": "Alaska", "az": "Arizona", "ar": "Arkansas", "ca": "California",
    "co": "Colorado", "ct": "Connecticut", "de": "Delaware", "dc": "District of Columbia",
    "fl": "Florida", "ga": "Georgia", "id": "Idaho", "il": "Illinois", "in": "Indiana",
    "ia": "Iowa", "ks": "Kansas", "ky": "Kentucky", "la": "Louisiana", "me": "Maine",
    "md": "Maryland", "ma": "Massachusetts", "mi": "Michigan", "mn": "Minnesota",
    "ms": "Mississippi", "mo": "Missouri", "mt": "Montana", "ne": "Nebraska", "nv": "Nevada",
    "nh": "New Hampshire", "nj": "New Jersey", "nm": "New Mexico", "ny": "New York",
    "nc": "North Carolina", "nd": "North Dakota", "oh": "Ohio", "ok": "Oklahoma",
    "or": "Oregon", "pa": "Pennsylvania", "ri": "Rhode Island", "sc": "South Carolina",
    "sd": "South Dakota", "tn": "Tennessee", "tx": "Texas", "ut": "Utah", "vt": "Vermont",
    "va": "Virginia", "wa": "Washington", "wv": "West Virginia", "wi": "Wisconsin", "wy": "Wyoming",
}


if __name__ == "__main__":
    sys.exit(main())
