"""Production curvature-adaptive geometry + maxspeed sweep (Job 2 fanout).

Generalizes the ratified straw sampler (``tools/straw_curve_sample.py``, reviewed
in ``docs/curve-geometry-straw-review.md``) over the whole network. One pass per
leg emits two layers:

  * ``world.json`` ``corridor.speed_limits`` -- the confirmed posted step
    function the runtime/linter/tests read. Dense sampling yields real
    transitions, so no lone city-street anchor survives and the anchor linter
    reports ZERO on fresh data. (Null coverage-gap markers live only in the
    derived shard; world.json carries numeric postings, per its schema.)
  * derived shards the runtime does not yet read (Phil wires curve-nav later):
      - ``world_data/us/geometry/<state>.jsonl`` -- the encoded archival polyline
      - ``world_data/us/gameplay/curves.jsonl``  -- per-curve steering rows
      - ``world_data/us/gameplay/ramps.jsonl``   -- runaway/escape ramps
      - ``world_data/us/gameplay/speed_limits.jsonl`` -- coverage-aware postings
    ``index_world.py`` only manages the files it derives from world.json, so
    these extra files are safe under ``world_data/`` and ``--check`` ignores them.

Phil's rev-2 riders, all folded in:
  1. keep-verbatim margin CURVE_PAD_M 80 -> 150 (edge-of-span curves survive the
     archive bake);
  2. runaway-ramp harvest in the same per-leg Overpass bbox query (fourth table);
  3. trailing gap marker (a leg ending in a >4 mi posting hole closes with null);
  4. per-shard ``data_version`` (each file hashed over its own records).

Selection / batching (fan out by region, compact between phases):
  uv run --group tooling python tools/bake_curve_geometry.py --only a:b;c:d
  uv run --group tooling python tools/bake_curve_geometry.py --region rockies
  uv run --group tooling python tools/bake_curve_geometry.py --all

Runs are idempotent and merge: a shard keeps records for legs outside the
selection and replaces those inside it, so region batches accumulate.

  OVERPASS_URL=http://localhost:12347/api/interpreter \
  ORS_BASE_URL=http://localhost:8080/ors ORS_API_KEY=selfhosted \
  uv run --group tooling python tools/bake_curve_geometry.py --region rockies
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import straw_curve_sample as scs  # noqa: E402  (the ratified primitives)
from enrich_routes_ors import fetch_ors_hgv_route, parse_ors_route  # noqa: E402
from enrich_routes_pois import MAXSPEED_SOURCE, _maxspeed_from_tags  # noqa: E402
from repair_interstate_anchor_limits import repair as _repair_profiles  # noqa: E402

# Rider 1: widen the keep-verbatim margin so marginal edge-of-span curves
# survive the archive bake (Phil measured a 951 ft sweep lost at the Colby
# approach with the 80 m straw margin).
scs.CURVE_PAD_M = 150.0

ROOT = Path(__file__).resolve().parent.parent
WORLD = ROOT / "src" / "freight_fate" / "data" / "world.json"
WORLD_DATA = ROOT / "src" / "freight_fate" / "data" / "world_data"
GEOM_DIR = WORLD_DATA / "us" / "geometry"
GAMEPLAY_DIR = WORLD_DATA / "us" / "gameplay"
ESCAPE_CACHE = ROOT / "src" / "freight_fate" / "data" / "escape_ramps.json"

OVERPASS_URL = os.environ.get("OVERPASS_URL", "http://localhost:12347/api/interpreter")
SCHEMA_VERSION = 1
SOURCE_NOTE = (
    "OpenRouteService driving-hgv (self-hosted) + OSM via Overpass "
    "(ODbL, (c) OpenStreetMap contributors)"
)
RAMP_SOURCE = "OpenStreetMap highway=escape ways (Overpass), development-time."
RAMP_MATCH_M = 160.0  # an escape way farther than this from the route isn't on it
RAMP_DEDUP_MI = 0.3  # same-side ramps closer than this are one physical ramp
FLUSH_EVERY = 25  # write world.json + shards every N legs so progress is durable


# --- combined per-leg Overpass query (maxspeed + escape ramps, rider 2) -----
def _overpass(query: str) -> dict[str, Any]:
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(OVERPASS_URL, data=data)
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def query_leg_ways(coords: list[list[float]]) -> list[dict]:
    """One bbox query for the leg's maxspeed-tagged ways.

    (Runaway ramps come from the offline escape-ramp cache, not Overpass: the
    self-hosted extract is filtered and carries no highway=escape ways -- see
    ``tools/harvest_escape_ramps.py``.)"""
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    pad = 0.02
    box = f"{min(lats) - pad},{min(lons) - pad},{max(lats) + pad},{max(lons) + pad}"
    query = f"""
    [out:json][timeout:120];
    way["highway"~"motorway|trunk|primary|secondary|tertiary"]["maxspeed"]({box});
    out geom tags;
    """
    return _overpass(query).get("elements", [])


# --- maxspeed step function (confirmed for world.json; gap-aware for shard) --
def bake_speed_limits(
    highway: str,
    coords: list[list[float]],
    cum_m: list[float],
    mile_scale: float,
    ways: list[dict],
) -> list[dict[str, Any]]:
    """Coverage-aware step function: numeric postings + null coverage gaps.

    Numeric rows carry MAXSPEED_SOURCE for the world.json schema; ``mph: null``
    rows mark a >SPEED_GAP_MI OSM hole (mid-leg and trailing, rider 3) and are
    stripped before the profile is written into world.json."""
    lats = [c[1] for c in coords]
    shield_nums = scs._shield_numbers(highway)
    interstate = str(highway).strip().upper().startswith("I-")
    coslat = math.cos(math.radians(sum(lats) / len(lats)))
    total_mi = round(cum_m[-1] / 1609.344 * mile_scale, 1)

    samples: list[dict[str, Any]] = []
    last_m = -1e9
    hole_start_mi: float | None = None
    for i, (lon, lat) in enumerate(coords):
        is_last = i == len(coords) - 1
        if cum_m[i] - last_m < 402.0 and not is_last:  # ~0.25 mi
            continue
        last_m = cum_m[i]
        at_mi = round(cum_m[i] / 1609.344 * mile_scale, 1)
        best: tuple[float, bool] | None = None
        best_on_shield = False
        best_dist = scs.MATCH_CORRIDOR_M
        for way in ways:
            parsed = _maxspeed_from_tags(way.get("tags", {}))
            if parsed is None:
                continue
            mph, is_hgv = parsed
            on_shield = scs._ref_matches_shield(way.get("tags", {}).get("ref", ""), shield_nums)
            geom = way.get("geometry", [])
            for a, b in zip(geom, geom[1:], strict=False):
                d = scs._point_seg_dist_m(lat, lon, a, b, coslat)
                if d > best_dist:
                    continue
                if on_shield and not best_on_shield:
                    best, best_on_shield, best_dist = (mph, is_hgv), True, d
                elif on_shield == best_on_shield and (best is None or d < best_dist):
                    best, best_dist = (mph, is_hgv), d
        # No US interstate mainline posts below 45 anywhere, so ANY sub-45 match
        # on an interstate leg is a wrong-road pickup (frontage road, ramp, a
        # mislabeled business loop) -- drop it at any position, not just the ends
        # the post-bake linter trims. Surface legs keep their honest small-town 30s.
        if best is None or (interstate and best[0] < 45.0):
            if hole_start_mi is None:
                hole_start_mi = at_mi
            continue
        mph, is_hgv = best
        if (
            hole_start_mi is not None
            and samples
            and samples[-1]["mph"] is not None
            and at_mi - hole_start_mi > scs.SPEED_GAP_MI
        ):
            samples.append({"at_mi": hole_start_mi, "mph": None, "hgv": False})
        hole_start_mi = None
        if samples and samples[-1]["mph"] == int(mph) and samples[-1]["hgv"] == is_hgv:
            continue
        row = {"at_mi": at_mi, "mph": int(mph), "hgv": is_hgv, "source": MAXSPEED_SOURCE}
        if samples and samples[-1]["at_mi"] == at_mi:
            samples[-1] = row
            continue
        samples.append(row)
    # Rider 3: a leg that ends in a long posting hole closes with a null marker.
    if (
        hole_start_mi is not None
        and samples
        and samples[-1]["mph"] is not None
        and total_mi - hole_start_mi > scs.SPEED_GAP_MI
    ):
        samples.append({"at_mi": hole_start_mi, "mph": None, "hgv": False})
    return samples


# --- runaway-ramp harvest (rider 2, from the offline escape cache) -----------
def load_escape_cache() -> list[dict]:
    if not ESCAPE_CACHE.exists():
        return []
    return json.loads(ESCAPE_CACHE.read_text(encoding="utf-8")).get("ramps", [])


def harvest_ramps(
    escape_cache: list[dict],
    coords: list[list[float]],
    cum_m: list[float],
    mile_scale: float,
) -> list[dict[str, Any]]:
    """Runaway ramps on this leg: cached escape centroids near the route line."""
    if not escape_cache:
        return []
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    coslat = math.cos(math.radians(sum(lats) / len(lats)))
    local = scs._to_local_m(coords)
    # cheap bbox pre-filter: only ramps inside the leg's bounding box (+~0.5 mi)
    pad = 0.01
    lo_lat, hi_lat = min(lats) - pad, max(lats) + pad
    lo_lon, hi_lon = min(lons) - pad, max(lons) + pad
    ramps: list[dict[str, Any]] = []
    for ramp in escape_cache:
        rlat, rlon = ramp["lat"], ramp["lon"]
        if not (lo_lat <= rlat <= hi_lat and lo_lon <= rlon <= hi_lon):
            continue
        best_i, best_d = 0, 1e18
        for i, (lon, lat) in enumerate(coords):
            d = scs._haversine_m(lat, lon, rlat, rlon)
            if d < best_d:
                best_d, best_i = d, i
        if best_d > RAMP_MATCH_M:
            continue  # near the leg's bbox but not on its actual road
        j = best_i + 1 if best_i < len(coords) - 1 else best_i - 1
        hx, hy = local[j][0] - local[best_i][0], local[j][1] - local[best_i][1]
        rx = math.radians(rlon) * 6371000.0 * coslat - local[best_i][0]
        ry = math.radians(rlat) * 6371000.0 - local[best_i][1]
        cross = hx * ry - hy * rx
        ramps.append(
            {
                "at_mi": round(cum_m[best_i] / 1609.344 * mile_scale, 1),
                "side": "L" if cross > 0 else "R",
                "name": str(ramp.get("name", "") or ramp.get("ref", "")).strip(),
                "source": ramp.get("source", RAMP_SOURCE),
            }
        )
    ramps.sort(key=lambda r: r["at_mi"])
    # One physical runaway ramp is often two OSM ways (ramp lane + arrestor bed),
    # so collapse same-side ramps within RAMP_DEDUP_MI into one, keeping a name.
    merged: list[dict[str, Any]] = []
    for r in ramps:
        if merged and r["side"] == merged[-1]["side"] and r["at_mi"] - merged[-1]["at_mi"] <= RAMP_DEDUP_MI:
            if not merged[-1]["name"] and r["name"]:
                merged[-1]["name"] = r["name"]
            continue
        merged.append(r)
    return merged


# --- shard I/O: merge selection into existing files, per-shard version -------
def _read_records(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Existing shard records grouped by leg id (meta line skipped)."""
    by_leg: dict[str, list[dict[str, Any]]] = {}
    if not path.exists():
        return by_leg
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith('{"meta"'):
            continue
        rec = json.loads(line)
        by_leg.setdefault(rec["leg"], []).append(rec)
    return by_leg


def _write_shard(path: Path, by_leg: dict[str, list[dict[str, Any]]], extra_params: dict) -> None:
    """Rewrite a shard: meta line (content-hashed, rider 4) + sorted records.

    Records already carry their ``leg`` id; legs are emitted in sorted order so
    shard bytes never depend on processing order (determinism, acceptance #2)."""
    lines = [
        json.dumps(rec, sort_keys=True) for leg in sorted(by_leg) for rec in by_leg[leg]
    ]
    payload = "\n".join(lines)
    data_version = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    meta = {
        "meta": {
            "schema": SCHEMA_VERSION,
            "data_version": data_version,
            "source": SOURCE_NOTE,
            "params": {
                "a_lat_g": scs.A_LAT_G,
                "quant_deg": scs.QUANT_DEG,
                "radius_window_m": scs.RADIUS_WINDOW_M,
                "curve_radius_ft": scs.CURVE_RADIUS_FT,
                "curve_pad_m": scs.CURVE_PAD_M,
                "eps_tangent_m": scs.DP_EPS_TANGENT_M,
                "point_budget": scs.POINT_BUDGET,
                "sign_hysteresis_deg": scs.SIGN_HYSTERESIS_DEG,
                "deflection_floor_deg": scs.DEFLECTION_FLOOR_DEG,
                "connector_window_mi": scs.CONNECTOR_WINDOW_MI,
                "speed_gap_mi": scs.SPEED_GAP_MI,
                **extra_params,
            },
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, sort_keys=True) + "\n" + payload + ("\n" if payload else ""), encoding="utf-8")


# --- leg selection ----------------------------------------------------------
def select_legs(world: dict, args: argparse.Namespace) -> list[dict]:
    legs = world["legs"]
    cities = world["cities"]
    if args.only:
        wanted = {tuple(p.split(":")) for p in args.only.split(";") if ":" in p}
        return [L for L in legs if (L["from"], L["to"]) in wanted or (L["to"], L["from"]) in wanted]
    if args.region:
        reg = args.region.lower()
        return [
            L
            for L in legs
            if reg in (str(cities.get(L["from"], {}).get("region", "")).lower(),
                       str(cities.get(L["to"], {}).get("region", "")).lower())
        ]
    sel = list(legs)
    if args.limit:
        sel = sel[: args.limit]
    return sel


# --- driver -----------------------------------------------------------------
def process_leg(
    leg: dict, cities: dict, api_key: str, escape_cache: list[dict]
) -> dict[str, Any] | None:
    frm, to = leg["from"], leg["to"]
    highway = leg.get("highway", "")
    leg_miles = float(leg.get("miles", 0)) or None
    start = {"lat": cities[frm]["lat"], "lon": cities[frm]["lon"]}
    end = {"lat": cities[to]["lat"], "lon": cities[to]["lon"]}
    via = tuple(leg.get("route_via", []) or ())
    parsed = parse_ors_route(fetch_ors_hgv_route(start, end, api_key, via=via))
    coords = parsed["coordinates"]
    elev = parsed["elevations_ft"]
    cum_raw = scs._cumulative_m(coords)
    raw_mi = cum_raw[-1] / 1609.344
    mile_scale = (leg_miles / raw_mi) if leg_miles else 1.0

    curv_raw = scs.analyse_curvature(coords, cum_raw)
    idx = scs.adaptive_simplify(coords, curv_raw["curving"], cum_raw, scs.POINT_BUDGET)
    geom = scs.encode_geometry(coords, elev, idx)
    coords_dec = scs.decode_geometry(geom)
    cum_dec = scs._cumulative_m(coords_dec)
    curv_dec = scs.analyse_curvature(coords_dec, cum_dec)

    maxspeed_ways = query_leg_ways(coords)
    speed_full = bake_speed_limits(highway, coords, cum_raw, mile_scale, maxspeed_ways)
    ramps = harvest_ramps(escape_cache, coords, cum_raw, mile_scale)

    conn_hi = (leg_miles or raw_mi) - scs.CONNECTOR_WINDOW_MI
    gameplay_curves = []
    for c in curv_dec["curves"]:
        row = scs._gameplay_curve(c, idx, cum_raw, mile_scale)
        if row["end_mi"] <= scs.CONNECTOR_WINDOW_MI or row["start_mi"] >= conn_hi:
            row["connector"] = True
        gameplay_curves.append(row)

    rt = scs.roundtrip_check(geom, curv_dec["curves"])
    # world.json profile: numeric confirmed postings only (schema needs a number),
    # then run the anchor linter's OWN repair so fresh data is clean by
    # construction -- it drops interstate sub-45 end anchors and fast-corridor
    # surface mile-0/end city-street anchors exactly as the post-bake linter
    # would, guaranteeing it then reports ZERO (repair is idempotent).
    world_profile = [
        {"at_mi": s["at_mi"], "mph": s["mph"], "source": s["source"], "hgv": s["hgv"]}
        for s in speed_full
        if s["mph"] is not None
    ]
    _tmp = {
        "legs": [
            {
                "from": frm,
                "to": to,
                "highway": highway,
                "miles": leg_miles or round(raw_mi, 2),
                "corridor": {"speed_limits": world_profile},
            }
        ]
    }
    _repair_profiles(_tmp)
    world_profile = _tmp["legs"][0].get("corridor", {}).get("speed_limits", [])
    return {
        "leg_id": f"{frm}:{to}",
        "state": str(cities[frm]["state"]).lower(),
        "highway": highway,
        "miles": round(leg_miles or raw_mi, 2),
        "geom": geom,
        "curves": gameplay_curves,
        "ramps": ramps,
        "speed_full": speed_full,
        "world_profile": world_profile,
        "roundtrip": rt,
        "raw_curves": len(curv_raw["curves"]),
        "kept": len(idx),
        "raw_vertices": len(coords),
    }


def flush(world: dict, geom_by_state, curves_by_leg, ramps_by_leg, speed_by_leg) -> None:
    # ensure_ascii=True matches world.json's existing \uXXXX escaping, so the only
    # diff is the speed_limits we changed -- no spurious churn on unrelated names.
    WORLD.write_text(json.dumps(world, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    for state, by_leg in geom_by_state.items():
        _write_shard(GEOM_DIR / f"{state}.jsonl", by_leg, {"layer": "geometry"})
    _write_shard(GAMEPLAY_DIR / "curves.jsonl", curves_by_leg, {"layer": "curves"})
    _write_shard(GAMEPLAY_DIR / "ramps.jsonl", ramps_by_leg, {"layer": "ramps"})
    _write_shard(GAMEPLAY_DIR / "speed_limits.jsonl", speed_by_leg, {"layer": "speed_limits"})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--only", help="semicolon-separated slug pairs, e.g. a:b;c:d")
    g.add_argument("--region", help="all legs touching a region (e.g. rockies)")
    g.add_argument("--all", action="store_true", help="every leg in the network")
    ap.add_argument("--limit", type=int, help="cap leg count (with --all, for smoke tests)")
    args = ap.parse_args()

    world = json.loads(WORLD.read_text(encoding="utf-8"))
    cities = world["cities"]
    api_key = os.environ.get("ORS_API_KEY", "selfhosted")
    legs = select_legs(world, args)
    legs.sort(key=lambda L: (L["from"], L["to"]))  # deterministic order (acceptance #2)
    escape_cache = load_escape_cache()
    print(f"selected {len(legs)} legs | {len(escape_cache)} escape ramps in cache", flush=True)

    # start shard accumulators from what's already on disk, then overlay selection
    curves_by_leg = _read_records(GAMEPLAY_DIR / "curves.jsonl")
    ramps_by_leg = _read_records(GAMEPLAY_DIR / "ramps.jsonl")
    speed_by_leg = _read_records(GAMEPLAY_DIR / "speed_limits.jsonl")
    geom_by_state: dict[str, dict[str, list[dict]]] = {}
    for shard in sorted(GEOM_DIR.glob("*.jsonl")) if GEOM_DIR.exists() else []:
        geom_by_state[shard.stem] = _read_records(shard)

    leg_index = {(L["from"], L["to"]): L for L in world["legs"]}
    done = failed = rt_fail = 0
    for n, leg in enumerate(legs, 1):
        key = (leg["from"], leg["to"])
        try:
            r = process_leg(leg, cities, api_key, escape_cache)
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, KeyError, OSError) as exc:
            failed += 1
            print(f"  [{n}/{len(legs)}] {key[0]}:{key[1]} FAILED: {exc}", flush=True)
            continue
        if not r["roundtrip"]["passed"]:
            rt_fail += 1
            print(f"  [{n}/{len(legs)}] {r['leg_id']} ROUND-TRIP FAIL {r['roundtrip']}", flush=True)
            continue
        lid = r["leg_id"]
        # world.json: write the confirmed profile onto the actual leg object only
        # when the dense bake produced one. If it found nothing (no OSM maxspeed,
        # or every sample was city-street pollution the linter drops), LEAVE any
        # existing profile untouched -- the sweep must never regress a leg that
        # already had coverage down to the bare heuristic.
        if r["world_profile"]:
            leg_index[key].setdefault("corridor", {})["speed_limits"] = r["world_profile"]
        # shards
        geom_by_state.setdefault(r["state"], {})[lid] = [
            {"leg": lid, "highway": r["highway"], "miles": r["miles"], "geom": r["geom"]}
        ]
        curves_by_leg[lid] = [{"leg": lid, **c} for c in r["curves"]]
        ramps_by_leg[lid] = [{"leg": lid, **rp} for rp in r["ramps"]]
        speed_by_leg[lid] = [{"leg": lid, **s} for s in r["speed_full"]]
        done += 1
        if n % 10 == 0 or n == len(legs):
            print(
                f"  [{n}/{len(legs)}] {lid}: {r['kept']}/{r['raw_vertices']} verts, "
                f"{len(r['curves'])} curves, {len(r['ramps'])} ramps, "
                f"{len(r['world_profile'])} speed rows",
                flush=True,
            )
        if n % FLUSH_EVERY == 0:
            flush(world, geom_by_state, curves_by_leg, ramps_by_leg, speed_by_leg)
            print(f"    -- flushed at {n}", flush=True)

    flush(world, geom_by_state, curves_by_leg, ramps_by_leg, speed_by_leg)
    print(f"\nDONE: {done} baked, {failed} fetch-failed, {rt_fail} round-trip-failed", flush=True)
    return 1 if rt_fail else 0


if __name__ == "__main__":
    sys.exit(main())
