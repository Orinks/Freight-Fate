"""Lane-count data bake (Job 3, lane-data slice) -- brief: docs/lane-data-brief.md.

Every leg's corridor learns how many lanes the real road carries, so future
mechanics (passing traffic, lane-end cues, exit-lane guidance, closures) have
honest data waiting. DATA-LAYER ONLY -- nothing in the game reads it yet, the
same way grades and dense speed limits were baked ahead of their physics.

Method (reuses the Job 2 way-matching machinery, ``straw_curve_sample``):
  * coords come from the archived dense polyline (``world_data/us/geometry/
    <state>.jsonl``), decoded -- fully offline and deterministic, no ORS
    re-fetch. Only the self-hosted Overpass (``OVERPASS_URL``) is queried, for
    the leg's ``lanes``-tagged ways.
  * each ~0.25 mi sample point is matched to the nearest governing way exactly
    like ``bake_speed_limits`` (shield-ref preferred, within
    ``MATCH_CORRIDOR_M``); its ``lanes`` / ``lanes:forward`` / ``lanes:backward``
    / ``oneway`` tags become the sample's value.
  * samples collapse to a step function, merged into ``corridor.lane_segments``.

HONEST ABSENCE: where OSM has no ``lanes`` tag the sample is a gap and NO
segment is emitted -- no defaults, no guesses. The runtime can default by road
class later.

Schema (nested under each leg's ``corridor``, sibling of ``grade_segments``):

  corridor.lane_segments = [
    {"start_mi", "end_mi", "lanes": int,        # the way's lanes tag
     "lanes_forward": int | absent, "lanes_backward": int | absent,
     "oneway": true | absent, "source": str},
    ...
  ]

Selection / batching (small reviewable diffs, commit per state):
  uv run --group tooling python tools/bake_lane_segments.py --state az --write
  uv run --group tooling python tools/bake_lane_segments.py --only a:b;c:d
  uv run --group tooling python tools/bake_lane_segments.py --all --write

Default is dry-run (report only); ``--write`` saves via ``world_source``. After
writing, regenerate the index (``tools/index_world.py``) and run the world
tests, per the brief.
"""

from __future__ import annotations

import argparse
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

import straw_curve_sample as scs  # noqa: E402  (the ratified matcher primitives)
from world_source import load_world, save_world  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GEOM_DIR = ROOT / "src" / "freight_fate" / "data" / "world_data" / "us" / "geometry"
OVERPASS_URL = os.environ.get("OVERPASS_URL", "http://localhost:12347/api/interpreter")

SOURCE_NOTE = (
    "OpenStreetMap lanes tags on the corridor highway ways (Overpass), "
    "development-time; total per the OSM lanes semantics (directional on "
    "oneway carriageways). ODbL, (c) OpenStreetMap contributors."
)

SAMPLE_STEP_M = 402.0  # ~0.25 mi between matched samples (matches bake_speed_limits)
MIN_SEG_MI = 0.3  # segments shorter than this are dropped unless at an interchange
INTERCHANGE_TOL_MI = 0.4  # a short segment this near an interchange is kept (lanes
#                           change fast there -- brief exception to the min-length rule)
LANES_MIN, LANES_MAX = 1, 10  # a tag outside this is absurd; logged and skipped
HIGHWAY_FILTER = "motorway|trunk|primary|secondary|tertiary"


# --- tag parsing ------------------------------------------------------------
def _clean_int(raw: Any) -> int | None:
    """A clean positive integer, or None. Rejects '2;3', '1.5', '', negatives."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or not s.lstrip("-").isdigit():
        return None
    try:
        return int(s)
    except ValueError:
        return None


def lanes_from_tags(tags: dict[str, Any]) -> dict[str, Any] | None:
    """The lane value a matched way contributes, or None if it has no usable count.

    ``lanes`` follows OSM semantics verbatim: on a ``oneway`` carriageway it is
    the count in that direction; on an undivided two-way it is the total both
    ways. The ``oneway`` flag disambiguates downstream, so we store the raw int
    rather than guessing a split."""
    n = _clean_int(tags.get("lanes"))
    if n is None or not (LANES_MIN <= n <= LANES_MAX):
        return None
    out: dict[str, Any] = {"lanes": n}
    f = _clean_int(tags.get("lanes:forward"))
    b = _clean_int(tags.get("lanes:backward"))
    if f is not None and LANES_MIN <= f <= LANES_MAX:
        out["lanes_forward"] = f
    if b is not None and LANES_MIN <= b <= LANES_MAX:
        out["lanes_backward"] = b
    if str(tags.get("oneway", "")).strip().lower() in ("yes", "true", "1", "-1"):
        out["oneway"] = True
    return out


# --- Overpass: one bbox query per leg, matched locally ----------------------
def _overpass(query: str) -> dict[str, Any]:
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(OVERPASS_URL, data=data)
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def query_leg_lane_ways(coords: list[list[float]]) -> list[dict]:
    """One bbox query for the leg's lanes-tagged ways (mirror of Job 2's query)."""
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    pad = 0.02
    box = f"{min(lats) - pad},{min(lons) - pad},{max(lats) + pad},{max(lons) + pad}"
    query = f"""
    [out:json][timeout:120];
    way["highway"~"{HIGHWAY_FILTER}"]["lanes"]({box});
    out geom tags;
    """
    return _overpass(query).get("elements", [])


# --- geometry archive: decode per-leg coords --------------------------------
def load_state_geometry(state: str) -> dict[str, list[list[float]]]:
    """{leg_id: decoded [lon,lat] coords} for one state's geometry shard."""
    path = GEOM_DIR / f"{state}.jsonl"
    out: dict[str, list[list[float]]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith('{"meta"'):
            continue
        rec = json.loads(line)
        out[rec["leg"]] = scs.decode_geometry(rec["geom"])
    return out


# --- lane step function + segment build -------------------------------------
def _match_lane_value(
    lat: float,
    lon: float,
    ways: list[dict],
    shield_nums: set[str],
    coslat: float,
) -> dict[str, Any] | None:
    """Nearest governing way's lane value at a point (Job 2 shield-preferred match)."""
    best: dict[str, Any] | None = None
    best_on_shield = False
    best_dist = scs.MATCH_CORRIDOR_M
    for way in ways:
        parsed = lanes_from_tags(way.get("tags", {}))
        if parsed is None:
            continue
        on_shield = scs._ref_matches_shield(way.get("tags", {}).get("ref", ""), shield_nums)
        geom = way.get("geometry", [])
        for a, b in zip(geom, geom[1:], strict=False):
            d = scs._point_seg_dist_m(lat, lon, a, b, coslat)
            if d > best_dist:
                continue
            if on_shield and not best_on_shield:
                best, best_on_shield, best_dist = parsed, True, d
            elif on_shield == best_on_shield and (best is None or d < best_dist):
                best, best_dist = parsed, d
    return best


def _value_key(val: dict[str, Any]) -> tuple:
    return tuple(sorted((k, v) for k, v in val.items()))


def build_lane_segments(
    coords: list[list[float]],
    cum_m: list[float],
    mile_scale: float,
    ways: list[dict],
    shield_nums: set[str],
    interchange_mi: list[float],
) -> tuple[list[dict[str, Any]], float, float]:
    """Sample -> step function -> merged segments. Returns (segments, covered_mi, total_mi)."""
    lats = [c[1] for c in coords]
    coslat = math.cos(math.radians(sum(lats) / len(lats)))
    total_mi = round(cum_m[-1] / 1609.344 * mile_scale, 1)

    # sample every ~0.25 mi; each sample is a lane value dict or None (gap)
    samples: list[tuple[float, dict[str, Any] | None]] = []
    last_m = -1e9
    for i, (lon, lat) in enumerate(coords):
        is_last = i == len(coords) - 1
        if cum_m[i] - last_m < SAMPLE_STEP_M and not is_last:
            continue
        last_m = cum_m[i]
        at_mi = round(cum_m[i] / 1609.344 * mile_scale, 1)
        val = _match_lane_value(lat, lon, ways, shield_nums, coslat)
        samples.append((at_mi, val))

    # step function -> raw segments. A gap closes the open segment at the last
    # matched sample (honest absence: we never claim lanes across an untagged
    # stretch). A value change closes at the transition point.
    segs: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for at_mi, val in samples:
        if val is None:
            if cur is not None:
                cur["end_mi"] = cur["_last_mi"]
                segs.append(cur)
                cur = None
            continue
        key = _value_key(val)
        if cur is not None and cur["_key"] == key:
            cur["_last_mi"] = at_mi
            continue
        if cur is not None:
            cur["end_mi"] = at_mi
            segs.append(cur)
        cur = {"start_mi": at_mi, "end_mi": at_mi, "_last_mi": at_mi, "_key": key, "value": val}
    if cur is not None:
        cur["end_mi"] = total_mi
        segs.append(cur)

    # drop sub-0.3mi slivers unless they sit at an interchange (lanes change fast
    # there), then re-merge any adjacent identical spans dropping left behind.
    kept: list[dict[str, Any]] = []
    for s in segs:
        length = s["end_mi"] - s["start_mi"]
        if length <= 0:
            continue
        at_ic = any(
            abs(s["start_mi"] - m) <= INTERCHANGE_TOL_MI or abs(s["end_mi"] - m) <= INTERCHANGE_TOL_MI
            for m in interchange_mi
        )
        if length < MIN_SEG_MI and not at_ic:
            continue
        kept.append(s)

    merged: list[dict[str, Any]] = []
    for s in kept:
        if (
            merged
            and merged[-1]["_key"] == s["_key"]
            and abs(merged[-1]["end_mi"] - s["start_mi"]) <= 0.15
        ):
            merged[-1]["end_mi"] = s["end_mi"]
            continue
        merged.append(s)

    out: list[dict[str, Any]] = []
    covered_mi = 0.0
    for s in merged:
        covered_mi += s["end_mi"] - s["start_mi"]
        rec = {
            "start_mi": round(s["start_mi"], 1),
            "end_mi": round(s["end_mi"], 1),
            **s["value"],
            "source": SOURCE_NOTE,
        }
        out.append(rec)
    return out, round(covered_mi, 1), total_mi


# --- driver -----------------------------------------------------------------
def select_legs(world: dict, args: argparse.Namespace) -> list[dict]:
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
    g.add_argument("--only", help="semicolon-separated slug pairs, e.g. a:b;c:d")
    g.add_argument("--state", help="all legs whose FROM city is in this state (e.g. az)")
    g.add_argument("--all", action="store_true", help="every leg in the network")
    ap.add_argument("--write", action="store_true", help="save via world_source (default dry-run)")
    ap.add_argument("--json-out", help="write a per-leg coverage report to this path")
    args = ap.parse_args()

    world = load_world()
    cities = world["cities"]
    legs = select_legs(world, args)
    legs.sort(key=lambda L: (L["from"], L["to"]))  # deterministic order
    leg_index = {(L["from"], L["to"]): L for L in world["legs"]}
    print(f"selected {len(legs)} legs | write={args.write}", flush=True)

    geom_cache: dict[str, dict[str, list[list[float]]]] = {}
    per_state_cov: dict[str, list[float]] = {}  # state -> [covered_mi, total_mi]
    report: list[dict[str, Any]] = []
    done = failed = empty = 0
    total_segs = 0

    for n, leg in enumerate(legs, 1):
        frm, to = leg["from"], leg["to"]
        key = (frm, to)
        lid = f"{frm}:{to}"
        state = str(cities[frm]["state"]).lower()
        highway = leg.get("highway", "")
        leg_miles = float(leg.get("miles", 0)) or None

        if state not in geom_cache:
            geom_cache[state] = load_state_geometry(state)
        coords = geom_cache[state].get(lid)
        if not coords or len(coords) < 2:
            failed += 1
            print(f"  [{n}/{len(legs)}] {lid} SKIP: no geometry archive", flush=True)
            continue

        try:
            ways = query_leg_lane_ways(coords)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            failed += 1
            print(f"  [{n}/{len(legs)}] {lid} OVERPASS FAILED: {exc}", flush=True)
            continue

        cum_m = scs._cumulative_m(coords)
        raw_mi = cum_m[-1] / 1609.344
        mile_scale = (leg_miles / raw_mi) if leg_miles and raw_mi else 1.0
        shield_nums = scs._shield_numbers(highway)
        interchange_mi = [
            float(ic["at_mi"])
            for ic in leg.get("corridor", {}).get("interchanges", [])
            if isinstance(ic, dict) and "at_mi" in ic
        ]

        segs, covered_mi, total_mi = build_lane_segments(
            coords, cum_m, mile_scale, ways, shield_nums, interchange_mi
        )

        cov = per_state_cov.setdefault(state, [0.0, 0.0])
        cov[0] += covered_mi
        cov[1] += total_mi

        target = leg_index[key]
        if segs:
            target.setdefault("corridor", {})["lane_segments"] = segs
            done += 1
            total_segs += len(segs)
        else:
            # honest absence: no coverage -> carry no lane_segments key
            if "lane_segments" in target.get("corridor", {}):
                del target["corridor"]["lane_segments"]
            empty += 1

        report.append(
            {"leg": lid, "state": state, "segments": len(segs),
             "covered_mi": covered_mi, "total_mi": total_mi}
        )
        if n % 10 == 0 or n == len(legs):
            pct = 100.0 * covered_mi / total_mi if total_mi else 0.0
            print(
                f"  [{n}/{len(legs)}] {lid}: {len(segs)} segs, "
                f"{covered_mi}/{total_mi} mi ({pct:.0f}%)",
                flush=True,
            )
        if args.write and n % 50 == 0:
            save_world(world)  # durable progress on long --all runs
            print(f"    -- flushed world source at {n}", flush=True)

    if args.write:
        save_world(world)
        print("saved world source", flush=True)

    print(f"\nDONE: {done} legs with lanes, {empty} no-coverage, {failed} skipped/failed", flush=True)
    print(f"total segments: {total_segs}", flush=True)
    print("coverage by state (covered / total route-mi):", flush=True)
    net_cov = net_tot = 0.0
    for st in sorted(per_state_cov):
        c, t = per_state_cov[st]
        net_cov += c
        net_tot += t
        pct = 100.0 * c / t if t else 0.0
        print(f"  {st}: {c:.0f}/{t:.0f} mi ({pct:.0f}%)", flush=True)
    net_pct = 100.0 * net_cov / net_tot if net_tot else 0.0
    print(f"NETWORK: {net_cov:.0f}/{net_tot:.0f} mi ({net_pct:.1f}%)", flush=True)

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(
                {"legs": report, "network_covered_mi": round(net_cov, 1),
                 "network_total_mi": round(net_tot, 1), "network_pct": round(net_pct, 2),
                 "total_segments": total_segs},
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"wrote report -> {args.json_out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
