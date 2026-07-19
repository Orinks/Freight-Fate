"""Prototype curvature-adaptive geometry sampler -- the STRAW RECORD generator.

This is NOT the production sweep. It instantiates the schema from
``docs/curve-geometry-schema-strawman.md`` on two real sample legs so Phil can
review the actual encoded representation (not just headers) before the
network-wide Job 2 run is unlocked. Rev 2 folds in Phil's straw review
(`docs/curve-geometry-straw-review.md`).

Test pair (owner-ratified):
  * canyon  -- globe_az_us:show_low_az_us  (US-60, Salt River Canyon, ~88 mi)
  * straight -- hays_ks_us:colby_ks_us     (I-70, Kansas High Plains, ~109 mi)

For each leg it:
  1. fetches the fine ORS driving-hgv geometry (the same undecimated polyline
     the grade sampler already walks -- no new requests beyond the one route),
  2. measures curvature: radius from a fixed-length sliding-arc circle fit
     (stable under quantization), plus per-vertex signed heading change,
  3. detects curves, SPLITTING each curving run at every sustained sign change
     so a serpentine yields its separate L and R curves, and derives a physics
     advisory speed v = sqrt(a_lat * R) at the binding (min-radius) apex,
  4. runs a curvature-adaptive Douglas-Peucker: eps=0 inside curve spans (the
     archive must be able to re-bake the gameplay tables), loose eps on
     tangents under a per-leg tangent budget,
  5. ONE Overpass bbox query per leg for maxspeed ways -> a collapsed
     speed_limits step function (interstate shield-less sub-45 guard kept;
     concurrency refs like "US 60;SR 77" accepted),
  6. emits the ARCHIVAL encoded geometry (delta+quantize, text) and the small
     BAKED gameplay tables (speed_limits, curves) as sharded NDJSON, each shard
     led by a meta record (schema, content-addressed data_version, source,
     bake params), and self-verifies with a decode -> re-bake round-trip check.

Run:
  OVERPASS_URL=http://localhost:12347/api/interpreter \
  ORS_BASE_URL=http://localhost:8080/ors ORS_API_KEY=selfhosted \
  uv run --group tooling python tools/straw_curve_sample.py
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from enrich_routes_ors import fetch_ors_hgv_route, parse_ors_route  # noqa: E402
from enrich_routes_pois import _maxspeed_from_tags  # noqa: E402
from world_source import load_world  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "straw"

OVERPASS_URL = os.environ.get("OVERPASS_URL", "http://localhost:12347/api/interpreter")

SCHEMA_VERSION = 1
SOURCE_NOTE = (
    "OpenRouteService driving-hgv (self-hosted) + OSM via Overpass "
    "(ODbL, (c) OpenStreetMap contributors)"
)

# --- Sampler tuning (Phil ratified these as production starting values) ------
QUANT_DEG = 5  # 1e-5 deg ~= 1.1 m quantization for the archival stream
CURVE_RADIUS_FT = 3000.0  # a vertex tighter than this is "curving" for a Class-8
A_LAT_G = 0.30  # comfortable dry-loaded lateral accel for the advisory speed
RADIUS_WINDOW_M = 80.0  # sliding-arc window for the circle-fit radius (Phil's #2)
DP_EPS_TANGENT_M = 30.0  # loose simplification on near-straight runs
CURVE_PAD_M = 80.0  # keep-all margin around curve spans so edges re-fit identically
POINT_BUDGET = 600  # tangent-only vertex cap (curves set their own floor)
SIGN_WOBBLE_DEG = 1.0  # |turn| under this is neutral (doesn't set a direction)
SIGN_HYSTERESIS_DEG = 5.0  # sustained opposing turn needed to split a run (Phil's #1)
DEFLECTION_FLOOR_DEG = 8.0  # a real curve turns at least this much (per direction)
CONNECTOR_WINDOW_MI = 0.75  # first/last in-town stretch -> tag curves, don't drop
MATCH_CORRIDOR_M = 90.0  # how near a maxspeed way must be to govern a sample point
SPEED_GAP_MI = 4.0  # a posting-free run longer than this becomes an explicit gap

MPS_TO_MPH = 2.2369362920544
FT_PER_M = 3.280839895

TEST_LEGS = [
    ("globe_az_us", "show_low_az_us", "canyon"),
    ("hays_ks_us", "colby_ks_us", "straight"),
]


# --- geometry primitives ----------------------------------------------------
def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _to_local_m(coords: list[list[float]]) -> list[tuple[float, float]]:
    """Equirectangular projection to metres about the leg centroid."""
    lat0 = sum(c[1] for c in coords) / len(coords)
    coslat = math.cos(math.radians(lat0))
    r = 6371000.0
    return [(math.radians(lon) * r * coslat, math.radians(lat) * r) for lon, lat in coords]


def _cumulative_m(coords: list[list[float]]) -> list[float]:
    out = [0.0]
    for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:], strict=False):
        out.append(out[-1] + _haversine_m(lat1, lon1, lat2, lon2))
    return out


def _turn_deg(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    """Signed heading change (deg, +left / -right) from AB to BC."""
    ax, ay = a
    bx, by = b
    cx, cy = c
    if math.hypot(bx - ax, by - ay) < 1e-6 or math.hypot(cx - bx, cy - by) < 1e-6:
        return 0.0
    h1 = math.atan2(by - ay, bx - ax)
    h2 = math.atan2(cy - by, cx - bx)
    return math.degrees((h2 - h1 + math.pi) % (2 * math.pi) - math.pi)


def _window_radius_ft(cum_m: list[float], turn: list[float], i: int) -> float:
    """Radius (ft) at vertex i from heading integration over a sliding arc.

    R = arc_length / |total heading change| over a ~RADIUS_WINDOW_M window --
    the "heading change / turn radius over a sliding window" of the original
    design memo. Integrating the turn over several vertices is stable under
    both vertex spacing and 1.1 m quantization, where a 3-point circumradius
    is not (Phil's #2): a circle fit needs a well-conditioned arc this coarse
    ORS geometry (median ~56 m spacing) rarely provides. Returns inf on a
    near-straight window."""
    n = len(cum_m)
    half = RADIUS_WINDOW_M / 2.0
    lo = i
    while lo > 0 and cum_m[i] - cum_m[lo - 1] <= half:
        lo -= 1
    hi = i
    while hi < n - 1 and cum_m[hi + 1] - cum_m[i] <= half:
        hi += 1
    lo = min(lo, i - 1) if i > 0 else i  # at least one segment on each side
    hi = max(hi, i + 1) if i < n - 1 else i
    arc = cum_m[hi] - cum_m[lo]
    total_turn = sum(turn[k] for k in range(lo + 1, hi + 1) if 0 < k < n - 1)
    rad = math.radians(abs(total_turn))
    if arc < 1e-6 or rad < 1e-4:
        return math.inf
    return (arc / rad) * FT_PER_M


def _advisory_mph(radius_ft: float) -> float:
    r_m = radius_ft / FT_PER_M
    v = math.sqrt(A_LAT_G * 9.80665 * r_m)  # m/s
    return int(round(v * MPS_TO_MPH / 5.0) * 5)


# --- curvature analysis + switchback-aware curve detection ------------------
def analyse_curvature(coords: list[list[float]], cum_m: list[float]) -> dict[str, Any]:
    local = _to_local_m(coords)
    n = len(local)
    turn = [0.0] * n
    for i in range(1, n - 1):
        turn[i] = _turn_deg(local[i - 1], local[i], local[i + 1])
    radius_ft = [math.inf] * n
    for i in range(1, n - 1):
        radius_ft[i] = _window_radius_ft(cum_m, turn, i)
    curving = [r < CURVE_RADIUS_FT for r in radius_ft]

    def sign_at(k: int) -> int:
        if turn[k] > SIGN_WOBBLE_DEG:
            return 1
        if turn[k] < -SIGN_WOBBLE_DEG:
            return -1
        return 0

    def split_run(i: int, j: int) -> list[tuple[int, int]]:
        """Split a curving run [i, j) at every sustained sign change."""
        segs: list[tuple[int, int]] = []
        seg_start = i
        cur_sign = 0
        opp_start: int | None = None
        opp_acc = 0.0
        for k in range(i, j):
            sk = sign_at(k)
            if cur_sign == 0:
                if sk != 0:
                    cur_sign = sk
                continue
            if sk == cur_sign:
                opp_start, opp_acc = None, 0.0
            elif sk == -cur_sign:
                if opp_start is None:
                    opp_start = k
                opp_acc += abs(turn[k])
                if opp_acc >= SIGN_HYSTERESIS_DEG:
                    segs.append((seg_start, opp_start))
                    seg_start, cur_sign = opp_start, -cur_sign
                    opp_start, opp_acc = None, 0.0
        segs.append((seg_start, j))
        return segs

    curves: list[dict[str, Any]] = []
    i, seq = 1, 0
    while i < n - 1:
        if not curving[i]:
            i += 1
            continue
        j = i
        while j < n - 1 and curving[j]:
            j += 1
        for a, b in split_run(i, j):
            deflection = sum(turn[k] for k in range(a, b))
            if abs(deflection) < DEFLECTION_FLOOR_DEG:
                continue
            span = range(a, b + 1)
            apex_k = min(span, key=lambda k: radius_ft[k])
            min_r = radius_ft[apex_k]
            if not math.isfinite(min_r):
                continue
            seq += 1
            curves.append(
                {
                    "seq": seq,
                    "_a": a,
                    "_b": b,
                    "_apex": apex_k,
                    "direction": "L" if deflection > 0 else "R",
                    "min_radius_ft": round(min_r),
                    "deflection_deg": round(abs(deflection), 1),
                    "advisory_mph": _advisory_mph(min_r),
                }
            )
        i = j
    return {"radius_ft": radius_ft, "curving": curving, "curves": curves}


def _at_mi(cum_m: list[float], k: int, mile_scale: float) -> float:
    """Leg-miles position of vertex k: raw distance rescaled to leg.miles (Phil's #4)."""
    return round(cum_m[k] / 1609.344 * mile_scale, 2)


def _gameplay_curve(
    c: dict[str, Any], raw_idx: list[int], cum_raw: list[float], mile_scale: float
) -> dict[str, Any]:
    """A gameplay row: geometry from the decoded archive, mileage from raw cum.

    ``c`` carries decoded-stream indices; ``raw_idx[k]`` maps each back to its
    raw vertex so at_mi rides the authoritative raw distance (never the ~1%-short
    decoded stream), rescaled to the curated leg.miles."""
    return {
        "seq": c["seq"],
        "start_mi": _at_mi(cum_raw, raw_idx[c["_a"]], mile_scale),
        "end_mi": _at_mi(cum_raw, raw_idx[c["_b"]], mile_scale),
        "apex_mi": _at_mi(cum_raw, raw_idx[c["_apex"]], mile_scale),
        "direction": c["direction"],
        "min_radius_ft": c["min_radius_ft"],
        "deflection_deg": c["deflection_deg"],
        "advisory_mph": c["advisory_mph"],
    }


# --- curvature-adaptive Douglas-Peucker (eps=0 in curves) -------------------
def _dp(local: list[tuple[float, float]], lo: int, hi: int, eps: float, keep: set[int]) -> None:
    if hi <= lo + 1:
        return
    ax, ay = local[lo]
    bx, by = local[hi]
    dx, dy = bx - ax, by - ay
    seg = math.hypot(dx, dy)
    worst_d, worst_i = -1.0, -1
    for i in range(lo + 1, hi):
        px, py = local[i]
        if seg < 1e-9:
            d = math.hypot(px - ax, py - ay)
        else:
            d = abs(dx * (ay - py) - (ax - px) * dy) / seg
        if d > worst_d:
            worst_d, worst_i = d, i
    if worst_d > eps:
        keep.add(worst_i)
        _dp(local, lo, worst_i, eps, keep)
        _dp(local, worst_i, hi, eps, keep)


def _keepall_mask(curving: list[bool], cum_m: list[float]) -> list[bool]:
    """Vertices to preserve verbatim: every curve vertex, padded by the fit window."""
    n = len(curving)
    mask = [False] * n
    k = 0
    while k < n:
        if not curving[k]:
            k += 1
            continue
        j = k
        while j < n and curving[j]:
            j += 1
        lo = k
        while lo > 0 and cum_m[k] - cum_m[lo - 1] <= CURVE_PAD_M:
            lo -= 1
        hi = j - 1
        while hi < n - 1 and cum_m[hi + 1] - cum_m[j - 1] <= CURVE_PAD_M:
            hi += 1
        for m in range(lo, hi + 1):
            mask[m] = True
        k = j
    return mask


def adaptive_simplify(
    coords: list[list[float]], curving: list[bool], cum_m: list[float], budget: int
) -> list[int]:
    """Retained vertex indices: curve spans kept verbatim, tangents simplified."""
    local = _to_local_m(coords)
    n = len(local)
    keepall = _keepall_mask(curving, cum_m)
    base = {0, n - 1} | {k for k in range(n) if keepall[k]}

    def build(eps_t: float) -> list[int]:
        keep = set(base)
        ordered = sorted(keep)
        for a, b in zip(ordered, ordered[1:], strict=False):
            if b > a + 1:
                _dp(local, a, b, eps_t, keep)
        return sorted(keep)

    ordered = build(DP_EPS_TANGENT_M)
    eps_t = DP_EPS_TANGENT_M
    while len(ordered) > budget and eps_t < 4000:
        eps_t *= 1.6
        ordered = build(eps_t)
    return ordered


# --- archival encoding (delta + quantize, text) -----------------------------
def encode_geometry(
    coords: list[list[float]], elevations_ft: list[float], idx: list[int]
) -> dict[str, Any]:
    scale = 10**QUANT_DEG
    lat_q = [round(coords[i][1] * scale) for i in idx]
    lon_q = [round(coords[i][0] * scale) for i in idx]
    ele_m = [round(elevations_ft[i] / FT_PER_M) for i in idx]

    def deltas(vals: list[int]) -> list[int]:
        return [b - a for a, b in zip(vals, vals[1:], strict=False)]

    return {
        "q": QUANT_DEG,
        "n": len(idx),
        "lat0": lat_q[0],
        "lon0": lon_q[0],
        "ele0_m": ele_m[0],
        "dlat": deltas(lat_q),
        "dlon": deltas(lon_q),
        "dele_m": deltas(ele_m),
    }


def decode_geometry(geom: dict[str, Any]) -> list[list[float]]:
    """Reconstruct [lon, lat] vertices from an encoded record (round-trip check)."""
    scale = 10 ** geom["q"]
    lat, lon = geom["lat0"], geom["lon0"]
    coords = [[lon / scale, lat / scale]]
    for dlat, dlon in zip(geom["dlat"], geom["dlon"], strict=False):
        lat += dlat
        lon += dlon
        coords.append([lon / scale, lat / scale])
    return coords


# --- maxspeed: ONE bbox query per leg, matched locally ----------------------
def _shield_numbers(highway: str) -> set[str]:
    return set(re.findall(r"\d+", str(highway)))


def _ref_matches_shield(ref: str, shield_nums: set[str]) -> bool:
    """True if any concurrency ref number matches the leg shield (US 60;SR 77)."""
    if not shield_nums:
        return False
    return bool(shield_nums & set(re.findall(r"\d+", str(ref))))


def _overpass(query: str) -> dict[str, Any]:
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(OVERPASS_URL, data=data)
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _point_seg_dist_m(plat: float, plon: float, a: dict, b: dict, coslat: float) -> float:
    r = 6371000.0
    ax, ay = math.radians(a["lon"]) * r * coslat, math.radians(a["lat"]) * r
    bx, by = math.radians(b["lon"]) * r * coslat, math.radians(b["lat"]) * r
    px, py = math.radians(plon) * r * coslat, math.radians(plat) * r
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 < 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def bake_speed_limits(
    highway: str, coords: list[list[float]], cum_m: list[float], mile_scale: float
) -> tuple[list[dict[str, Any]], int]:
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    pad = 0.02
    box = f"{min(lats) - pad},{min(lons) - pad},{max(lats) + pad},{max(lons) + pad}"
    query = f"""
    [out:json][timeout:120];
    way["highway"~"motorway|trunk|primary|secondary|tertiary"]["maxspeed"]({box});
    out geom tags;
    """
    ways = _overpass(query).get("elements", [])
    shield_nums = _shield_numbers(highway)
    interstate = str(highway).strip().upper().startswith("I-")
    coslat = math.cos(math.radians(sum(lats) / len(lats)))

    samples: list[dict[str, Any]] = []
    last_m = -1e9
    hole_start_mi: float | None = None  # start of a run with no OSM maxspeed match
    for i, (lon, lat) in enumerate(coords):
        if cum_m[i] - last_m < 402.0 and i != len(coords) - 1:  # ~0.25 mi
            continue
        last_m = cum_m[i]
        at_mi = round(cum_m[i] / 1609.344 * mile_scale, 1)
        best: tuple[float, bool] | None = None
        best_on_shield = False
        best_dist = MATCH_CORRIDOR_M
        for way in ways:
            parsed = _maxspeed_from_tags(way.get("tags", {}))
            if parsed is None:
                continue
            mph, is_hgv = parsed
            on_shield = _ref_matches_shield(way.get("tags", {}).get("ref", ""), shield_nums)
            for a, b in zip(way.get("geometry", []), way.get("geometry", [])[1:], strict=False):
                d = _point_seg_dist_m(lat, lon, a, b, coslat)
                if d > best_dist:
                    continue
                if on_shield and not best_on_shield:
                    best, best_on_shield, best_dist = (mph, is_hgv), True, d
                elif on_shield == best_on_shield and (best is None or d < best_dist):
                    best, best_dist = (mph, is_hgv), d
        if best is None or (interstate and not best_on_shield and best[0] < 45.0):
            # No usable posted limit here. Remember where coverage was lost so a
            # long hole becomes an explicit gap marker, not a stale carried value.
            if hole_start_mi is None:
                hole_start_mi = at_mi
            continue
        mph, is_hgv = best
        # A hole longer than SPEED_GAP_MI closes the previous posting: OSM has no
        # data across it, so the runtime falls back to heuristic + curve advisory.
        if (
            hole_start_mi is not None
            and samples
            and samples[-1]["mph"] is not None
            and at_mi - hole_start_mi > SPEED_GAP_MI
        ):
            samples.append({"at_mi": hole_start_mi, "mph": None, "hgv": False})
        hole_start_mi = None
        if samples and samples[-1]["mph"] == int(mph) and samples[-1]["hgv"] == is_hgv:
            continue
        if samples and samples[-1]["at_mi"] == at_mi:
            samples[-1] = {"at_mi": at_mi, "mph": int(mph), "hgv": is_hgv}
            continue
        samples.append({"at_mi": at_mi, "mph": int(mph), "hgv": is_hgv})
    return samples, len(ways)


# --- round-trip acceptance check (Phil's #3) --------------------------------
def roundtrip_check(geom: dict[str, Any], authoritative: list[dict[str, Any]]) -> dict[str, Any]:
    """Decode the archive, re-detect curves, diff against the shipped table.

    The shipped gameplay tables are baked FROM the decoded archive, so a fresh
    decode -> re-bake must reproduce them exactly: same curve count, identical
    radii and advisories. This proves anyone holding only the archive shard
    reconstructs the exact gameplay layer -- the archive IS sufficient. A miss
    means analyse_curvature is non-deterministic: a bake bug, per Phil's rule."""
    coords = decode_geometry(geom)
    cum_m = _cumulative_m(coords)
    rebaked = analyse_curvature(coords, cum_m)["curves"]
    ok = len(rebaked) == len(authoritative)
    worst_radius_pct = 0.0
    advisories_equal = True
    if ok:
        for p, r in zip(authoritative, rebaked, strict=False):
            if p["min_radius_ft"] and r["min_radius_ft"]:
                pct = abs(p["min_radius_ft"] - r["min_radius_ft"]) / p["min_radius_ft"] * 100
                worst_radius_pct = max(worst_radius_pct, pct)
            advisories_equal &= p["advisory_mph"] == r["advisory_mph"]
    passed = ok and worst_radius_pct <= 10.0 and advisories_equal
    return {
        "passed": passed,
        "shipped_curves": len(authoritative),
        "rebaked_curves": len(rebaked),
        "worst_radius_pct": round(worst_radius_pct, 1),
        "advisories_equal": advisories_equal,
    }


# --- driver -----------------------------------------------------------------
def main() -> None:
    world = load_world()
    nodes = world["cities"]
    api_key = os.environ.get("ORS_API_KEY", "selfhosted")
    (OUT / "us" / "geometry").mkdir(parents=True, exist_ok=True)
    (OUT / "us" / "gameplay").mkdir(parents=True, exist_ok=True)

    legs_meta = {(L["from"], L["to"]): L for L in world["legs"]}
    summary: list[dict[str, Any]] = []
    geom_by_state: dict[str, list[dict[str, Any]]] = {}
    speed_rows: list[str] = []
    curve_rows: list[str] = []

    # sorted iteration -> shard content never depends on traversal order
    for frm, to, kind in sorted(TEST_LEGS):
        leg = legs_meta[(frm, to)]
        highway = leg.get("highway", "")
        leg_miles = float(leg.get("miles", 0)) or None
        start = {"lat": nodes[frm]["lat"], "lon": nodes[frm]["lon"]}
        end = {"lat": nodes[to]["lat"], "lon": nodes[to]["lon"]}
        print(f"[{kind}] {frm} -> {to}  ({highway})  fetching ORS ...", flush=True)
        parsed = parse_ors_route(fetch_ors_hgv_route(start, end, api_key))
        coords = parsed["coordinates"]
        elev = parsed["elevations_ft"]
        cum_raw = _cumulative_m(coords)
        raw_mi = cum_raw[-1] / 1609.344
        mile_scale = (leg_miles / raw_mi) if leg_miles else 1.0  # leg-miles convention (#4)
        print(f"    {len(coords)} raw vertices, {raw_mi:.1f} mi (leg.miles={leg_miles})", flush=True)

        # 1. detect curves on the full-resolution raw geometry (decides keep-mask)
        curv_raw = analyse_curvature(coords, cum_raw)
        idx = adaptive_simplify(coords, curv_raw["curving"], cum_raw, POINT_BUDGET)
        geom = encode_geometry(coords, elev, idx)

        # 2. bake the shipped tables FROM the decoded archive -- so the archive is
        #    sufficient by construction (Phil's #3). Mileage still rides raw cum.
        coords_dec = decode_geometry(geom)
        cum_dec = _cumulative_m(coords_dec)
        curv_dec = analyse_curvature(coords_dec, cum_dec)

        print("    querying Overpass maxspeed bbox ...", flush=True)
        speeds, way_count = bake_speed_limits(highway, coords, cum_raw, mile_scale)

        conn_hi = (leg_miles or raw_mi) - CONNECTOR_WINDOW_MI
        gameplay_curves = []
        for c in curv_dec["curves"]:
            row = _gameplay_curve(c, idx, cum_raw, mile_scale)
            if row["end_mi"] <= CONNECTOR_WINDOW_MI or row["start_mi"] >= conn_hi:
                row["connector"] = True
            gameplay_curves.append(row)

        rt = roundtrip_check(geom, curv_dec["curves"])
        raw_curve_count = len(curv_raw["curves"])

        state = nodes[frm]["state"].lower()
        leg_id = f"{frm}:{to}"
        geom_by_state.setdefault(state, []).append(
            {"leg": leg_id, "highway": highway, "miles": round(leg_miles or raw_mi, 2), "geom": geom}
        )
        for s in speeds:
            speed_rows.append(json.dumps({"leg": leg_id, **s}, sort_keys=True))
        for row in gameplay_curves:
            curve_rows.append(json.dumps({"leg": leg_id, **row}, sort_keys=True))

        raw_bytes = len(json.dumps([[round(c[0], 6), round(c[1], 6)] for c in coords]))
        enc_bytes = len(json.dumps(geom))
        non_conn = sum(1 for r in gameplay_curves if not r.get("connector"))
        summary.append(
            {
                "leg": leg_id,
                "kind": kind,
                "highway": highway,
                "miles": round(leg_miles or raw_mi, 1),
                "raw_vertices": len(coords),
                "kept_vertices": len(idx),
                "curves_raw_detected": raw_curve_count,
                "curves": len(gameplay_curves),
                "curves_non_connector": non_conn,
                "speed_steps": len(speeds),
                "maxspeed_ways_seen": way_count,
                "raw_coord_bytes": raw_bytes,
                "encoded_geom_bytes": enc_bytes,
                "compression_x": round(raw_bytes / enc_bytes, 1) if enc_bytes else 0,
                "roundtrip": rt,
            }
        )
        print(
            f"    kept {len(idx)}/{len(coords)} verts, {len(gameplay_curves)} curves "
            f"({non_conn} non-connector), {len(speeds)} speed steps | "
            f"round-trip {'PASS' if rt['passed'] else 'FAIL'} {rt}",
            flush=True,
        )

    # content-addressed data_version over the geometry payload (deterministic)
    geom_payload = json.dumps(geom_by_state, sort_keys=True)
    data_version = "sha256:" + hashlib.sha256(geom_payload.encode("utf-8")).hexdigest()[:12]
    meta = {
        "meta": {
            "schema": SCHEMA_VERSION,
            "data_version": data_version,
            "source": SOURCE_NOTE,
            "params": {
                "a_lat_g": A_LAT_G,
                "quant_deg": QUANT_DEG,
                "radius_window_m": RADIUS_WINDOW_M,
                "curve_radius_ft": CURVE_RADIUS_FT,
                "eps_tangent_m": DP_EPS_TANGENT_M,
                "eps_curve_m": 0,
                "point_budget": POINT_BUDGET,
                "sign_hysteresis_deg": SIGN_HYSTERESIS_DEG,
                "deflection_floor_deg": DEFLECTION_FLOOR_DEG,
                "connector_window_mi": CONNECTOR_WINDOW_MI,
            },
        }
    }
    meta_line = json.dumps(meta, sort_keys=True)

    for state, recs in geom_by_state.items():
        lines = [meta_line] + [json.dumps(r, sort_keys=True) for r in recs]
        (OUT / "us" / "geometry" / f"{state}.jsonl").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
    (OUT / "us" / "gameplay" / "speed_limits.jsonl").write_text(
        "\n".join([meta_line] + speed_rows) + "\n", encoding="utf-8"
    )
    (OUT / "us" / "gameplay" / "curves.jsonl").write_text(
        "\n".join([meta_line] + curve_rows) + "\n", encoding="utf-8"
    )
    (OUT / "straw-summary.json").write_text(
        json.dumps({"data_version": data_version, "legs": summary}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print("\n=== STRAW RECORD SUMMARY ===")
    print(json.dumps({"data_version": data_version, "legs": summary}, indent=2, sort_keys=True))
    if not all(s["roundtrip"]["passed"] for s in summary):
        print("\n!!! round-trip check FAILED on at least one leg -- archive not sufficient")
        sys.exit(1)


if __name__ == "__main__":
    main()
