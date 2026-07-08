"""Bake narratable roadside features onto legs -- the map-pipeline half of the
OSM roadside-narration feature (the SELECT filter is tools/enrich_routes_landmarks.py).

For each leg: query the self-hosted Overpass (OVERPASS_URL) for narratable OSM
features along the corridor, find WHERE the route meets each one by geometry --
  node  (mountain pass / museum): nearest projection onto the route,
  way   (river): line crossing with the route,
  way/relation (park/forest/wilderness/reserve zone): first route point inside
        the polygon (the entry point),
classify + name-clean via the filter, rank, cap per leg, and write them as the
leg's own `corridor.landmarks` cue list (NOT checkpoints -- no dispatch/
enforcement semantics). Additive + idempotent (overwrites the leg's landmarks).

    python bake_landmarks.py [--only "a_b_us:c_d_us;..."] [--per-leg 8] [--write]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "src" / "freight_fate" / "data" / "world.json"
sys.path.insert(0, str(ROOT / "tools"))
from enrich_routes_landmarks import (  # noqa: E402
    NARRATABLE_OSM_TAGS,
    classify_narratable_feature,
    spoken_landmark_text,
)

OVERPASS_URL = os.environ.get("OVERPASS_URL", "http://localhost:12347/api/interpreter")
R_MI = 3958.8

# Curated landmark categories owned elsewhere -- hand-placed heritage markers and
# the authored billboards from bake_billboards.py. This tool regenerates only the
# OSM-derived features, so it must PRESERVE these when it overwrites a leg (else a
# re-bake silently wipes the Loneliest Road marker and every placed billboard).
CURATED_CATEGORIES = {"highway_marker", "billboard_sign"}
POINT_OFF_MI = 4.0      # keep a pass/museum/river crossing within this of the route
SAMPLE_STEP_MI = 20.0   # bbox sample spacing along the corridor
BBOX_RADIUS_M = 14000   # ~14 km half-box at each sample


def hav(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R_MI * 2 * math.asin(math.sqrt(a))


def route_cum(route):
    """Cumulative miles at each route vertex (haversine; leg miles rescale later)."""
    cum = [0.0]
    for i in range(1, len(route)):
        cum.append(cum[-1] + hav(*route[i - 1], *route[i]))
    return cum


def _seg_nearest(px, py, ax, ay, bx, by):
    """Nearest point on segment A-B to P, in flat lat/lon space; return (t, qx, qy)."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return 0.0, ax, ay
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return t, ax + t * dx, ay + t * dy


def project_on_route(route, cum, lat, lon):
    """Nearest point on the route polyline to (lat,lon); return (at_mi, off_mi)."""
    best = (1e9, 0.0)
    for i in range(1, len(route)):
        ay, ax = route[i - 1]
        by, bx = route[i]
        t, qy, qx = _seg_nearest(lon, lat, ax, ay, bx, by)
        off = hav(lat, lon, qx, qy)
        if off < best[0]:
            seg_mi = cum[i - 1] + t * (cum[i] - cum[i - 1])
            best = (off, seg_mi)
    return best[1], best[0]


def _ccw(ax, ay, bx, by, cx, cy):
    return (cy - ay) * (bx - ax) > (by - ay) * (cx - ax)


def _segments_cross(a, b, c, d):
    """True if segment a-b crosses c-d (each pt is (lat,lon))."""
    (ay, ax), (by, bx), (cy, cx), (dy, dx) = a, b, c, d
    return (_ccw(ax, ay, cx, cy, dx, dy) != _ccw(bx, by, cx, cy, dx, dy)) and (
        _ccw(ax, ay, bx, by, cx, cy) != _ccw(ax, ay, bx, by, dx, dy)
    )


def river_crossing_mi(route, cum, line):
    """First mile where the route polyline crosses river polyline `line`, or None."""
    for i in range(1, len(route)):
        for j in range(1, len(line)):
            if _segments_cross(route[i - 1], route[i], line[j - 1], line[j]):
                # approximate crossing at segment i's start-ish midpoint
                return round((cum[i - 1] + cum[i]) / 2, 1)
    return None


def _point_in_ring(lat, lon, ring):
    """Ray-cast point-in-polygon; ring is a list of (lat,lon)."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def zone_entry_mi(route, cum, rings):
    """Mile where the route first enters any outer ring of a zone, or None."""
    for i, (lat, lon) in enumerate(route):
        if any(_point_in_ring(lat, lon, r) for r in rings):
            return round(cum[i], 1)
    return None


def _assemble_rings(arcs):
    """Join multipolygon member arcs (open ways sharing endpoints) into closed rings."""
    arcs = [a for a in arcs if len(a) >= 2]
    used = [False] * len(arcs)
    rings = []
    for s in range(len(arcs)):
        if used[s]:
            continue
        ring = list(arcs[s])
        used[s] = True
        changed = True
        while changed and ring[0] != ring[-1]:
            changed = False
            for i, arc in enumerate(arcs):
                if used[i]:
                    continue
                if arc[0] == ring[-1]:
                    ring.extend(arc[1:])
                elif arc[-1] == ring[-1]:
                    ring.extend(reversed(arc[:-1]))
                elif arc[-1] == ring[0]:
                    ring[:0] = arc[:-1]
                elif arc[0] == ring[0]:
                    ring[:0] = list(reversed(arc[1:]))
                else:
                    continue
                used[i] = changed = True
        rings.append(ring)
    return rings


def _element_rings(el):
    """Outer polygon rings for a way/relation element from Overpass `out geom`."""
    if el["type"] == "way" and el.get("geometry"):
        return [[(g["lat"], g["lon"]) for g in el["geometry"]]]
    arcs = [
        [(g["lat"], g["lon"]) for g in m["geometry"]]
        for m in el.get("members", [])
        if m.get("role") in ("outer", "") and m.get("geometry")
    ]
    return _assemble_rings(arcs)


def _element_line(el):
    return [(g["lat"], g["lon"]) for g in el.get("geometry", [])]


def overpass(bbox):
    body = "\n".join(f'  {t}["{k}"="{v}"]({bbox});' for t, k, v in NARRATABLE_OSM_TAGS)
    q = f"[out:json][timeout:90];\n(\n{body}\n);\nout geom;"
    data = urllib.parse.urlencode({"data": q}).encode("utf-8")
    req = urllib.request.Request(OVERPASS_URL, data=data)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


_REL_CACHE: dict = {}


def fetch_relation(rel_id):
    """Full geometry for one relation by id (a bbox query strips members outside it)."""
    if rel_id in _REL_CACHE:
        return _REL_CACHE[rel_id]
    q = f"[out:json][timeout:90];rel({rel_id});out geom;"
    data = urllib.parse.urlencode({"data": q}).encode("utf-8")
    req = urllib.request.Request(OVERPASS_URL, data=data)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            els = json.loads(resp.read()).get("elements", [])
        result = els[0] if els else None
    except Exception:
        result = None
    _REL_CACHE[rel_id] = result
    return result


def _bbox(lat, lon, radius_m):
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * math.cos(math.radians(lat)) or 1e-6)
    return f"{lat - dlat},{lon - dlon},{lat + dlat},{lon + dlon}"


def bake_leg(leg, per_leg):
    rp = leg.get("corridor", {}).get("route_points", [])
    if len(rp) < 2:
        return []
    route = [(p["lat"], p["lon"]) for p in rp]
    raw_cum = route_cum(route)
    scale = float(leg["miles"]) / (raw_cum[-1] or 1.0)
    cum = [c * scale for c in raw_cum]

    # sample bboxes along the corridor and union the elements (dedupe by id)
    elements = {}
    step = max(1, int(len(route) * SAMPLE_STEP_MI / (cum[-1] or SAMPLE_STEP_MI)))
    for idx in range(0, len(route), step):
        lat, lon = route[idx]
        try:
            payload = overpass(_bbox(lat, lon, BBOX_RADIUS_M))
        except Exception:
            continue
        for el in payload.get("elements", []):
            elements[(el["type"], el["id"])] = el

    # Relations (national forests/parks) come back from a bbox query with member
    # geometry stripped to the box; re-fetch each in full so the polygon closes.
    for (typ, oid), el in list(elements.items()):
        if typ == "relation" and not any(m.get("geometry") for m in el.get("members", [])):
            full = fetch_relation(oid)
            if full:
                elements[(typ, oid)] = full

    found = {}
    for el in elements.values():
        feat = classify_narratable_feature(el.get("tags", {}))
        if not feat:
            continue
        if feat["category"] == "river" and not feat["name"].lower().rstrip().endswith("river"):
            continue  # skip creeks/bayous/harbors mistagged waterway=river -- spam control
        at_mi = None
        if feat["kind"] == "point" and feat["category"] != "river":
            lat, lon = el.get("lat"), el.get("lon")
            if lat is None:
                continue
            mi, off = project_on_route(route, cum, lat, lon)
            if off <= POINT_OFF_MI:
                at_mi = round(mi, 1)
        elif feat["category"] == "river":
            at_mi = river_crossing_mi(route, cum, _element_line(el))
        else:  # zone
            at_mi = zone_entry_mi(route, cum, _element_rings(el))
        if at_mi is None:
            continue
        rec = {
            "name": feat["name"],
            "category": feat["category"],
            "kind": feat["kind"],
            "at_mi": at_mi,
            "spoken": spoken_landmark_text(feat),
            "rank": feat["rank"],
        }
        prev = found.get(feat["name"])
        if prev is None or rec["rank"] > prev["rank"]:
            found[feat["name"]] = rec

    # Museum spam control: museums cluster at metro endpoints (a big city has
    # dozens). Drop endpoint-city museums and keep at most one genuinely mid-route
    # museum -- the evocative "roadside museum" case -- so museums stay rare color,
    # not a city directory. Rivers/forests/passes are unaffected.
    miles = float(leg["miles"])
    buf = min(12.0, miles / 4)
    museums = [r for r in found.values() if r["category"] == "museum"]
    museums = [m for m in museums if buf <= m["at_mi"] <= miles - buf]
    museums = sorted(museums, key=lambda m: abs(m["at_mi"] - miles / 2))[:1]
    pool = [r for r in found.values() if r["category"] != "museum"] + museums
    ranked = sorted(pool, key=lambda r: (-r["rank"], r["at_mi"]))[:per_leg]
    ranked.sort(key=lambda r: r["at_mi"])
    for r in ranked:
        r.pop("rank", None)
    return ranked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--per-leg", type=int, default=8)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    only = {frozenset(p.split(":")) for p in a.only.split(";") if ":" in p}

    d = json.loads(WORLD.read_text(encoding="utf-8"))
    total_lm = updated = 0
    for leg in d["legs"]:
        if only and frozenset((leg["from"], leg["to"])) not in only:
            continue
        lms = bake_leg(leg, a.per_leg)
        if a.only and len(only) <= 4:  # verbose for small runs
            print(f"{leg['from']}->{leg['to']}: {[(r['spoken'], r['at_mi']) for r in lms]}")
        if lms:
            # Regenerate only the OSM-derived features; keep any curated ones
            # (billboards, hand-placed heritage markers) that other tools own.
            existing = leg.get("corridor", {}).get("landmarks", [])
            curated = [lm for lm in existing if lm.get("category") in CURATED_CATEGORIES]
            leg.setdefault("corridor", {})["landmarks"] = sorted(
                curated + lms, key=lambda r: r["at_mi"]
            )
            total_lm += len(lms)
            updated += 1
    print(f"landmarks: {total_lm} across {updated} legs")
    if a.write:
        WORLD.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
        print("WRITTEN")
    else:
        print("(dry run)")


if __name__ == "__main__":
    raise SystemExit(main())
