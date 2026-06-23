"""Discover highway interchanges along each leg and curate them into world.json.

Development-time helper (never called at runtime). For every Interstate leg it:

1. Fetches densified OSRM geometry through the leg's checked-in ``route_points``
   so each exit can be snapped to an accurate ``at_mi``.
2. Queries Overpass for ``highway=motorway_junction`` nodes that lie on a
   mainline way carrying the leg's Interstate shield (e.g. ``ref ~ "I 95"``),
   plus the ``destination``-tagged ramps beside them -- the green-sign control
   text.
3. Collapses the two per-direction junction nodes for an exit into one record,
   snaps it, merges the ramp destinations, and enforces a minimum spacing so
   the spoken cues stay readable.
4. Writes an additive ``corridor.interchanges`` array, leaving every other
   field untouched. Runtime gameplay reads only the checked-in result.

Interchanges are an *additive* layer like curated POIs; they are not a dispatch
requirement, so a leg with no clean OSM exit data simply gets none.

Run from the repo root:
    uv run python tools/build_interchanges.py            # report only
    uv run python tools/build_interchanges.py --write     # update world.json
    uv run python tools/build_interchanges.py --only "New York->Philadelphia" --write
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORLD_PATH = ROOT / "src" / "freight_fate" / "data" / "world.json"
CACHE_DIR = ROOT / ".route-cache" / "interchanges"
OVERPASS_MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving/{coords}"
USER_AGENT = "FreightFate interchange curation (https://github.com/Orinks/Freight-Fate)"
ACCESSED_DATE = "2026-06-23"
EARTH_RADIUS_MI = 3958.7613

SAMPLE_SPACING_MI = 10.0   # how often to drop an Overpass probe along the leg
PROBE_RADIUS_M = 9_000     # search radius per probe
RAMP_NEAR_M = 350.0        # a ramp this close to a junction belongs to it
MIN_EXIT_SPACING_MI = 2.0  # collapse exits closer than this (keep the richer)
MAX_DESTINATIONS = 3       # cap control cities per exit for speech brevity


# --- geometry ---------------------------------------------------------------

def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


def _osrm_geometry(route_points: list[dict[str, Any]], rate_limit: float
                   ) -> list[tuple[float, float, float]] | None:
    """Dense [(lat, lon, cumulative_mi), ...] following the leg's waypoints."""
    if len(route_points) < 2:
        return None
    coords = ";".join(f"{p['lon']},{p['lat']}" for p in route_points)
    params = urllib.parse.urlencode({
        "overview": "full", "geometries": "geojson",
        "alternatives": "false", "steps": "false",
    })
    url = OSRM_ROUTE_URL.format(coords=coords) + "?" + params
    payload = _cached_get(url, "osrm", rate_limit)
    if payload is None:
        return None
    try:
        geom = payload["routes"][0]["geometry"]["coordinates"]
    except (KeyError, IndexError):
        return None
    out: list[tuple[float, float, float]] = []
    cum = 0.0
    prev: tuple[float, float] | None = None
    for lon, lat in geom:
        if prev is not None:
            cum += _haversine_mi(prev[0], prev[1], lat, lon)
        out.append((lat, lon, cum))
        prev = (lat, lon)
    return out


def _snap_at_mi(lat: float, lon: float,
                geom: list[tuple[float, float, float]],
                leg_miles: float) -> tuple[float, float]:
    """Nearest geometry vertex -> (at_mi scaled into the leg's frame, dist_mi)."""
    best_d = float("inf")
    best_cum = 0.0
    for glat, glon, cum in geom:
        d = _haversine_mi(lat, lon, glat, glon)
        if d < best_d:
            best_d = d
            best_cum = cum
    total = geom[-1][2] or leg_miles
    at_mi = best_cum / total * leg_miles
    return at_mi, best_d


# --- Overpass ---------------------------------------------------------------

def _shield_pattern(highway: str) -> str | None:
    """'I-95' -> regex 'I 95([^0-9]|$)'. Interstate shields only (clean OSM
    motorway_junction tagging); returns None for non-Interstate legs."""
    primary = highway.replace(",", "/").split("/")[0].strip()
    m = re.match(r"^I-(\d+)$", primary)
    if not m:
        return None
    return f"I {m.group(1)}([^0-9]|$)"


def _sample_points(geom: list[tuple[float, float, float]]
                   ) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    next_at = 0.0
    total = geom[-1][2]
    for lat, lon, cum in geom:
        if cum >= next_at:
            points.append((lat, lon))
            next_at += SAMPLE_SPACING_MI
    if total - (next_at - SAMPLE_SPACING_MI) > 1.0:  # always probe the tail
        points.append((geom[-1][0], geom[-1][1]))
    return points


def _overpass_query(shield_rx: str, lat: float, lon: float) -> str:
    r = PROBE_RADIUS_M
    return (
        f"[out:json][timeout:60];"
        f'way["highway"="motorway"]["ref"~"{shield_rx}"]'
        f"(around:{r},{lat},{lon})->.m;"
        f'node(w.m)["highway"="motorway_junction"]'
        f"(around:{r},{lat},{lon})->.jx;"
        f".jx out body;"
        f'way(around.jx:{int(RAMP_NEAR_M)})["highway"="motorway_link"]'
        f'["destination"]->.r;'
        f".r out tags center;"
    )


def _post_overpass(query: str, rate_limit: float) -> dict[str, Any] | None:
    return _cached_post(query, rate_limit)


# --- caching ----------------------------------------------------------------

def _cache_file(tag: str, key: str) -> Path:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{tag}-{digest}.json"


def _cached_get(url: str, tag: str, rate_limit: float) -> dict[str, Any] | None:
    cf = _cache_file(tag, url)
    if cf.exists():
        return json.loads(cf.read_text(encoding="utf-8"))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (TimeoutError, OSError, urllib.error.URLError) as exc:
        print(f"    OSRM error: {type(exc).__name__}: {exc}")
        return None
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cf.write_text(json.dumps(payload), encoding="utf-8")
    if rate_limit > 0:
        time.sleep(rate_limit)
    return payload


def _cached_post(query: str, rate_limit: float) -> dict[str, Any] | None:
    cf = _cache_file("overpass", query)
    if cf.exists():
        return json.loads(cf.read_text(encoding="utf-8"))
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    # Public Overpass throttles bulk use (429) and sheds load (504). Sweep the
    # mirrors a few times with exponential backoff so a long crawl rides out a
    # rate-limit window instead of dropping the leg. Cache makes a re-run free.
    for attempt in range(4):
        for url in OVERPASS_MIRRORS:
            req = urllib.request.Request(
                url, data=body,
                headers={"User-Agent": USER_AGENT,
                         "Content-Type": "application/x-www-form-urlencoded"})
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except (TimeoutError, OSError, urllib.error.URLError) as exc:
                code = getattr(exc, "code", "")
                print(f"    Overpass {url.split('/')[2]} -> {type(exc).__name__} "
                      f"{code}; trying next mirror")
                continue
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cf.write_text(json.dumps(payload), encoding="utf-8")
            if rate_limit > 0:
                time.sleep(rate_limit)
            return payload
        backoff = 15.0 * (attempt + 1)
        print(f"    all mirrors busy; backing off {backoff:.0f}s "
              f"(attempt {attempt + 1}/4)")
        time.sleep(backoff)
    return None


# --- discovery --------------------------------------------------------------

RAW_MARKERS = ("node/", "way/", "relation/", "amenity=", "highway=")
# Lane-control / vehicle-class words that ride in OSM destination tags. A
# destination made up *only* of these (e.g. "Cars Only", "Trucks - Buses",
# "Buses And Cars Only") is lane signage, not a place to head "toward".
VEHICLE_CONTROL_WORDS = {
    "cars", "car", "trucks", "truck", "buses", "bus", "vehicles", "only",
    "no", "hov", "express", "local", "left", "right", "lane", "lanes",
    "exit", "toll", "ezpass",
}
_CONNECTOR_WORDS = {"and"}


def _clean_place(value: str) -> str:
    text = " ".join(str(value).replace("\n", " ").split()).strip()
    lowered = text.lower()
    if not text or any(marker in lowered for marker in RAW_MARKERS):
        return ""
    words = [w for w in re.findall(r"[a-z]+", lowered) if w not in _CONNECTOR_WORDS]
    if words and all(w in VEHICLE_CONTROL_WORDS for w in words):
        return ""
    return text


def _split_destinations(raw: str) -> list[str]:
    out: list[str] = []
    for piece in str(raw).split(";"):
        place = _clean_place(piece)
        if place and place not in out:
            out.append(place)
    return out


def discover_leg(leg: dict[str, Any], rate_limit: float) -> list[dict[str, Any]]:
    highway = str(leg.get("highway", ""))
    shield_rx = _shield_pattern(highway)
    if shield_rx is None:
        return []
    route_points = list(leg.get("corridor", {}).get("route_points", ()))
    geom = _osrm_geometry(route_points, rate_limit)
    if not geom:
        return []
    leg_miles = float(leg["miles"])

    junctions: dict[int, dict[str, Any]] = {}     # node id -> {lat, lon, ref, name}
    ramps: list[dict[str, Any]] = []              # {lat, lon, destination, via}
    for lat, lon in _sample_points(geom):
        payload = _post_overpass(_overpass_query(shield_rx, lat, lon), rate_limit)
        if payload is None:
            continue
        for el in payload.get("elements", []):
            tags = el.get("tags", {})
            if el.get("type") == "node" and tags.get("highway") == "motorway_junction":
                junctions[el["id"]] = {
                    "lat": el["lat"], "lon": el["lon"],
                    "ref": str(tags.get("ref", "")).strip(),
                    "name": _clean_place(tags.get("name", "")),
                }
            elif el.get("type") == "way" and tags.get("highway") == "motorway_link":
                center = el.get("center") or {}
                if "lat" not in center:
                    continue
                ramps.append({
                    "lat": center["lat"], "lon": center["lon"],
                    "destinations": _split_destinations(tags.get("destination", "")),
                    "via": str(tags.get("destination:ref", "")).strip(),
                })

    return _assemble(junctions, ramps, geom, leg_miles, highway)


def _assemble(junctions: dict[int, dict[str, Any]], ramps: list[dict[str, Any]],
              geom: list[tuple[float, float, float]], leg_miles: float,
              highway: str) -> list[dict[str, Any]]:
    # Collapse the two per-carriageway junction nodes that share an exit ref
    # into one logical exit; ref-less nodes are grouped by their snapped mile.
    by_key: dict[str, list[dict[str, Any]]] = {}
    for node in junctions.values():
        at_mi, dist = _snap_at_mi(node["lat"], node["lon"], geom, leg_miles)
        if dist > 1.5 or not (1.0 < at_mi < leg_miles - 1.0):
            continue  # off-corridor match or too close to an endpoint
        node["at_mi"] = at_mi
        key = f"ref:{node['ref']}" if node["ref"] else f"mi:{round(at_mi / 0.5)}"
        by_key.setdefault(key, []).append(node)

    exits: list[dict[str, Any]] = []
    for group in by_key.values():
        at_mi = sum(n["at_mi"] for n in group) / len(group)
        ref = next((n["ref"] for n in group if n["ref"]), "")
        name = next((n["name"] for n in group if n["name"]), "")
        # Gather destinations from ramps near any node in this group.
        dests: list[str] = []
        via = ""
        for node in group:
            for ramp in ramps:
                if _haversine_mi(node["lat"], node["lon"],
                                 ramp["lat"], ramp["lon"]) * 1609.34 > RAMP_NEAR_M:
                    continue
                for d in ramp["destinations"]:
                    if d not in dests:
                        dests.append(d)
                if not via and ramp["via"]:
                    via = ramp["via"]
        if not (ref or dests or name):
            continue
        exits.append({
            "at_mi": round(at_mi, 1),
            "exit_ref": ref,
            "name": name,
            "destinations": dests[:MAX_DESTINATIONS],
            "via": via,
            "highway": highway,
            "source": (
                "OpenStreetMap highway=motorway_junction exit ref and "
                "destination sign tags on the leg's Interstate shield, snapped "
                f"to checked-in OSRM route geometry, accessed {ACCESSED_DATE}: "
                "https://www.openstreetmap.org/"
            ),
        })

    return _space_out(exits)


def _richness(ex: dict[str, Any]) -> int:
    return (1 if ex["exit_ref"] else 0) + len(ex["destinations"])


def _space_out(exits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Greedily keep the richest exits, dropping any within MIN_EXIT_SPACING_MI
    of one already kept, so the spoken cues do not crowd each other."""
    kept: list[dict[str, Any]] = []
    for ex in sorted(exits, key=lambda e: (-_richness(e), e["at_mi"])):
        if all(abs(ex["at_mi"] - k["at_mi"]) >= MIN_EXIT_SPACING_MI for k in kept):
            kept.append(ex)
    kept.sort(key=lambda e: e["at_mi"])
    return kept


# --- driver -----------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Curate OSM interchanges into world.json.")
    parser.add_argument("--write", action="store_true",
                        help="Write discovered interchanges back into world.json.")
    parser.add_argument("--only", default="",
                        help="Limit to one leg, e.g. 'New York->Philadelphia'.")
    parser.add_argument("--max-legs", type=int, default=0)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    parser.add_argument("--force", action="store_true",
                        help="Re-discover legs that already have interchanges.")
    args = parser.parse_args(argv)

    data = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    legs = data["legs"]
    if args.only:
        a, _, b = args.only.partition("->")
        legs = [leg for leg in legs if leg["from"] == a.strip() and leg["to"] == b.strip()]
        if not legs:
            raise SystemExit(f"No leg {args.only!r}")

    total_added = 0
    updated_legs = 0
    eligible = 0
    processed = 0
    for leg in legs:
        if _shield_pattern(str(leg.get("highway", ""))) is None:
            continue
        eligible += 1
        corridor = leg.setdefault("corridor", {})
        if corridor.get("interchanges") and not args.force:
            continue
        if args.max_legs and processed >= args.max_legs:
            break
        processed += 1
        label = f"{leg['from']}->{leg['to']} ({leg['highway']})"
        print(f"[{processed}] {label}", flush=True)
        found = discover_leg(leg, args.rate_limit)
        print(f"    {len(found)} interchanges", flush=True)
        if found:
            corridor["interchanges"] = found
            total_added += len(found)
            updated_legs += 1
        # Flush periodically so a long crawl is crash-safe and resumable: a
        # re-run without --force skips legs already written here.
        if args.write and updated_legs and processed % 10 == 0:
            WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print(f"    ...checkpointed world.json ({updated_legs} legs so far)",
                  flush=True)

    print(f"\n{eligible} Interstate legs eligible; "
          f"{processed} processed, {updated_legs} populated, "
          f"{total_added} interchanges total.")
    if args.write and updated_legs:
        WORLD_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {WORLD_PATH}")
    elif not args.write:
        print("(dry run; pass --write to update world.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
