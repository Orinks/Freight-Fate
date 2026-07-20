"""Find legs that cross tolled roads, and legs whose toll data is missing.

The map prices 46 toll events across 16 authorities, but every one of them was
placed by hand and every amount is marked ``estimated``. This finds the rest by
evidence instead of memory: OpenStreetMap tags tolled ways ``toll=yes``, so
walking each leg's real geometry and asking the local Overpass what is tolled
there produces the actual list -- including the ones nobody thought of.

Read-only. It writes a report, never world data: what a leg crosses is
evidence, but what a toll COSTS a five-axle rig comes from the authority's
published rate table, and that is a curated judgment, not a scrape.

Sampling is sparse on purpose (every ``STEP_MI`` with a wide radius). Toll
infrastructure is continuous for miles -- a turnpike does not appear for one
mile and vanish -- so a coarse walk finds it without 25,000 queries.

Usage::

    OVERPASS_URL=http://localhost:12347/api/interpreter \\
      uv run python tools/toll_scan.py --json logs/toll-scan.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from world_source import load_world

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / ".route-cache" / "toll-scan"

STEP_MI = 15.0
RADIUS_M = 3000
EARTH_RADIUS_MI = 3958.7613


def _overpass_url() -> str:
    url = os.environ.get("OVERPASS_URL", "").strip()
    if not url:
        raise SystemExit("Set OVERPASS_URL=http://localhost:12347/api/interpreter")
    return url


def _bbox(lat: float, lon: float, radius_m: float) -> str:
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * max(0.1, math.cos(math.radians(lat))))
    return f"{lat - dlat},{lon - dlon},{lat + dlat},{lon + dlon}"


def _polyline(leg: dict[str, Any]) -> list[tuple[float, float, float]]:
    points = (leg.get("corridor") or {}).get("route_points") or []
    out = [
        (float(p["lat"]), float(p["lon"]), float(p["at_mi"]))
        for p in points
        if "lat" in p and "lon" in p and "at_mi" in p
    ]
    return sorted(out, key=lambda p: p[2])


def _interpolate(line: list[tuple[float, float, float]], at_mi: float) -> tuple[float, float]:
    if at_mi <= line[0][2]:
        return line[0][0], line[0][1]
    for (lat1, lon1, mi1), (lat2, lon2, mi2) in zip(line, line[1:], strict=False):
        if mi1 <= at_mi <= mi2:
            span = mi2 - mi1
            t = 0.0 if span <= 0 else (at_mi - mi1) / span
            return lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t
    return line[-1][0], line[-1][1]


def _query(url: str, body: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url, data=body.encode("utf-8"), headers={"User-Agent": "FreightFateTollScan/1.0"}
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == 2:
                return {"elements": []}
            time.sleep(2 * (attempt + 1))
    return {"elements": []}


def _sample(url: str, key: str, lat: float, lon: float) -> list[dict[str, Any]]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")).get("elements", [])
    # Only roads a truck would actually be routed onto.
    body = (
        f'[out:json][timeout:50];way({_bbox(lat, lon, RADIUS_M)})'
        f'[highway~"^(motorway|trunk|primary|motorway_link|trunk_link)$"][toll];out tags 30;'
    )
    payload = _query(url, body)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return payload.get("elements", [])


def _highway_forms(highway: str) -> set[str]:
    """The ways OSM might spell a leg's highway: 'I-95' -> {'i-95', 'i 95'}."""
    raw = str(highway or "").strip().lower()
    if not raw:
        return set()
    return {raw, raw.replace("-", " "), raw.replace("-", "")}


# Managed/HOT/express lanes run inside the same corridor and carry the same
# route number as the free mainline, so a ref match alone lets them through.
# Tractor-trailers are barred from essentially all of them (I-30 and I-35W
# TEXpress, the Georgia Express Lanes, I-25 Express, the Katy managed lanes),
# so a truck on that corridor is on the free general-purpose lanes and pays
# nothing. A toll we can never be charged is worse than no toll at all.
MANAGED_LANE_MARKERS = (
    "express",
    "texpress",
    "expr",
    "hot lane",
    "managed",
    "toll lane",
    "hov",
)


def _is_managed_lane(tags: dict[str, str]) -> bool:
    name = f"{tags.get('name', '')} {tags.get('ref', '')}".lower()
    if any(marker in name for marker in MANAGED_LANE_MARKERS):
        return True
    # A ref like "I 10 Toll" is a tolled carriageway running beside the free
    # interstate of the same number -- Houston's Katy managed lanes, which
    # ban trucks. The free mainline's own ref never carries the word.
    ref = str(tags.get("ref", "")).lower()
    if "toll" in ref:
        return True
    # An explicit truck ban settles it whatever the name says.
    return str(tags.get("hgv", "")).lower() in {"no", "private"}


def _on_route(tags: dict[str, str], highway: str) -> bool:
    """Is this tolled way part of the road the leg actually drives?

    Proximity is not use: I-30 into Dallas runs within a couple of miles of
    the George Bush Turnpike and the Dallas North Tollway, and a truck on I-30
    pays neither. Requiring the way's own ref to name the leg's highway keeps
    a parallel tollway from billing a driver who never left the free road.
    """
    forms = _highway_forms(highway)
    if not forms or _is_managed_lane(tags):
        return False
    ref = str(tags.get("ref", "")).lower()
    return any(form in ref for form in forms)


def scan_leg(leg: dict[str, Any], url: str) -> dict[str, Any]:
    line = _polyline(leg)
    if len(line) < 2:
        return {"tolled_ways": [], "sampled": 0}
    key_base = f"{leg['from']}--{leg['to']}"
    found: dict[str, dict[str, str]] = {}
    sampled = 0
    mi = 0.0
    miles = float(leg.get("miles", 0.0) or 0.0)
    while mi <= miles:
        lat, lon = _interpolate(line, mi)
        for element in _sample(url, f"{key_base}--{mi:.0f}", lat, lon):
            tags = element.get("tags") or {}
            if str(tags.get("toll", "")).lower() not in {"yes", "designated"}:
                continue
            name = tags.get("name") or tags.get("ref") or tags.get("highway") or "unnamed"
            entry = {
                "name": name,
                "ref": tags.get("ref", ""),
                "toll": tags.get("toll", ""),
                "toll_hgv": tags.get("toll:hgv", ""),
                "operator": tags.get("operator", ""),
                "at_mi": round(mi, 1),
                "on_route": _on_route(tags, leg.get("highway", "")),
            }
            # An on-route sighting always wins over a nearby one of the same name.
            if name not in found or entry["on_route"]:
                found[name] = entry
        sampled += 1
        mi += STEP_MI
    return {"tolled_ways": list(found.values()), "sampled": sampled}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Write the full report here.")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    url = _overpass_url()
    data = load_world()
    legs = data["legs"][: args.limit or None]

    missing: list[dict[str, Any]] = []
    confirmed: list[dict[str, Any]] = []
    nearby: list[dict[str, Any]] = []
    for index, leg in enumerate(legs, 1):
        has_events = bool((leg.get("corridor") or {}).get("toll_events"))
        result = scan_leg(leg, url)
        if not result["tolled_ways"]:
            continue
        on_route = [w for w in result["tolled_ways"] if w["on_route"]]
        # A sighting only at mile 0 or at the far end is the sample sitting on
        # the city itself, where it picks up urban toll infrastructure the
        # highway never touches (Houston's downtown tollways, Brownsville's
        # international bridges). Real turnpikes appear mid-corridor too. Not
        # excluded -- a genuine endpoint toll plaza exists -- but flagged, so
        # a human reads these rather than trusting them.
        miles = float(leg.get("miles", 0.0) or 0.0)
        endpoint_only = bool(on_route) and all(
            w["at_mi"] <= 0.01 or w["at_mi"] >= miles - STEP_MI for w in on_route
        )
        row = {
            "from": leg["from"],
            "to": leg["to"],
            "highway": leg.get("highway", ""),
            "miles": round(float(leg.get("miles", 0.0) or 0.0), 1),
            "has_toll_events": has_events,
            "on_route": on_route,
            "endpoint_only": endpoint_only,
            "nearby_only": [w for w in result["tolled_ways"] if not w["on_route"]],
        }
        # Only a tolled way ON the leg's own highway counts as missing data;
        # a tollway running alongside is noise a driver never pays.
        if on_route:
            (confirmed if has_events else missing).append(row)
        elif not has_events:
            nearby.append(row)
        if index % 100 == 0:
            print(f"  ...{index}/{len(legs)} legs, {len(missing)} missing", flush=True)

    solid = [r for r in missing if not r["endpoint_only"]]
    edge = [r for r in missing if r["endpoint_only"]]
    print(f"\nLegs on a tolled road with NO toll data: {len(missing)}")
    print(f"  confident (seen mid-corridor): {len(solid)}")
    for row in solid:
        names = ", ".join(w["name"] for w in row["on_route"][:3])
        print(f"    {row['from']}->{row['to']} ({row['highway']}, {row['miles']:.0f}mi): {names}")
    print(f"  endpoint-only, NEEDS A HUMAN EYE: {len(edge)}")
    for row in edge:
        names = ", ".join(w["name"] for w in row["on_route"][:3])
        print(f"    {row['from']}->{row['to']} ({row['highway']}, {row['miles']:.0f}mi): {names}")
    print(f"\nLegs already priced and confirmed on a tolled road: {len(confirmed)}")
    print(f"Legs merely passing NEAR a tollway (no charge, listed for review): {len(nearby)}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {"missing": missing, "confirmed": confirmed, "nearby_only": nearby}, indent=2
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
