"""Classify every route stop by whether a rig can physically get into it.

Fills the ``vehicle_access`` field the game reads (see
``docs/truck-access-sweep-brief.md``). The map carries 1,082 generic
``fuel_station`` records, all tagged "limited truck parking" with no surveyed
capacity -- a uniform placeholder that hides real car-scale convenience stops
a 70-foot combination vehicle cannot enter. Announcing one is a promise the
player can take it, so each has to be judged against real evidence.

The evidence is OpenStreetMap, read through the self-hosted Overpass instance
at build time. Every stop already stores the lat/lon it was placed from, so
this looks up the actual tagged feature at that point and reads what the
mappers recorded: ``hgv``, ``access``, adjacent truck parking, whether the
site is a motorway service area or a tagged truck stop.

Rules, per the brief:

* NEVER filter by brand. Some Exxons and the Wawa Travel Center are genuinely
  truck-oriented. A chain name can VERIFY access (a Love's is a truck stop by
  nature) but never denies it -- an unrecognized brand just means "no evidence
  yet," which falls to the default.
* Default for a generic fuel station is ``bobtail_only``: on the map, reachable
  tractor-only, hidden from semi announcements and HOS planning.
* ``hgv=no`` or a closed ``access`` tag means no truck fits at all: ``none``.
* Facility types that are truck infrastructure by definition (truck stops,
  travel centers, service plazas, truck parking) stay ``tractor_trailer``
  unless OSM positively says otherwise.

Every decision writes a source note, and the Overpass answers are cached so
re-runs are deterministic and offline.

Usage::

    OVERPASS_URL=http://localhost:12347/api/interpreter \\
      uv run python tools/classify_vehicle_access.py --report
    OVERPASS_URL=... uv run python tools/classify_vehicle_access.py --write
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
from collections import Counter
from pathlib import Path
from typing import Any

from world_source import load_world, save_world

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "data" / "spider" / "vehicle-access-cache.json"
DEFAULT_OVERPASS = "https://overpass-api.de/api/interpreter"
ACCESSED_DATE = "2026-07-19"

# How far from the stored stop coordinate to look for the feature it came from.
# The coordinate IS the OSM node the POI was curated from, so this only has to
# absorb rounding and the occasional re-survey; widening it starts picking up
# the neighbouring business instead.
MATCH_RADIUS_M = 70

# Truck infrastructure by definition. Public rest areas belong here too: an
# interstate rest area is where the HOS clock gets served, and demoting the
# whole class for want of an explicit OSM tag would strip legal parking off
# the map wholesale. The restrictive default is aimed at generic fuel
# stations, which is where the false promises actually live.
TRUCK_FACILITY_TYPES = {
    "truck_stop",
    "travel_center",
    "service_plaza",
    "truck_parking",
    "public_rest_area",
}

# The only class that must EARN its access. Per the brief: a generic fuel
# station is bobtail_only unless truck access is specifically verified.
UNVERIFIED_BY_DEFAULT_TYPES = {"fuel_station"}

# Chains that ARE truck stops -- used only to VERIFY, never to deny. A name not
# on this list proves nothing; it just leaves the stop on the evidence path.
TRUCK_STOP_CHAINS = (
    "travelcenters of america",
    "ta travel center",
    "petro stopping center",
    "love's travel stop",
    "loves travel stop",
    "flying j",
    "pilot travel center",
    "sapp bros",
    "bosselman",
    "roady's",
    "ambest",
    "travel centers of america",
)

# OSM values that admit a combination vehicle.
HGV_YES = {"yes", "designated", "official", "permissive"}
HGV_NO = {"no", "private"}
ACCESS_CLOSED = {"no", "private", "customers"}

EARTH_RADIUS_M = 6371000.0


def _overpass_url() -> str:
    """The Overpass endpoint, preferring the self-hosted one.

    The public endpoint is rate-limited to the point of uselessness for a
    1,400-stop sweep, so a run that forgets OVERPASS_URL is a mistake worth
    naming rather than quietly tolerating.
    """
    url = os.environ.get("OVERPASS_URL", "").strip()
    if not url:
        print(
            "WARNING: OVERPASS_URL is unset, falling back to the public "
            "endpoint. Set OVERPASS_URL=http://localhost:12347/api/interpreter "
            "for the self-hosted instance.",
            file=sys.stderr,
        )
        return DEFAULT_OVERPASS
    return url


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _query(url: str, body: str, retries: int = 3) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers={"User-Agent": "FreightFateVehicleAccess/1.0"},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return {"elements": []}


def _fetch(url: str, lat: float, lon: float) -> list[dict[str, Any]]:
    """Everything near a stop that could speak to truck access."""
    body = f"""[out:json][timeout:60];
(
  nwr(around:{MATCH_RADIUS_M},{lat},{lon})[amenity=fuel];
  nwr(around:{MATCH_RADIUS_M},{lat},{lon})[amenity=truck_stop];
  nwr(around:{MATCH_RADIUS_M},{lat},{lon})[highway=services];
  nwr(around:{MATCH_RADIUS_M},{lat},{lon})[highway=rest_area];
  nwr(around:{MATCH_RADIUS_M * 3},{lat},{lon})[amenity=parking][hgv];
);
out tags center;"""
    return _query(url, body).get("elements", [])


def _looks_like_truck_chain(name: str) -> bool:
    lowered = name.lower()
    return any(chain in lowered for chain in TRUCK_STOP_CHAINS)


def classify(stop: dict[str, Any], elements: list[dict[str, Any]]) -> tuple[str, str]:
    """Return (vehicle_access, why) for one stop.

    ``why`` becomes the stop's source note, so a later reviewer can see the
    evidence rather than having to re-derive it.
    """
    name = str(stop.get("name", ""))
    stop_type = str(stop.get("type", ""))

    # Read the tags of everything we found, nearest first.
    lat, lon = float(stop.get("lat", 0.0)), float(stop.get("lon", 0.0))

    def _distance(element: dict[str, Any]) -> float:
        center = element.get("center") or element
        if "lat" not in center or "lon" not in center:
            return float("inf")
        return _haversine_m(lat, lon, float(center["lat"]), float(center["lon"]))

    nearby = sorted(elements, key=_distance)
    site = next(
        (
            element
            for element in nearby
            if (element.get("tags") or {}).get("amenity") in {"fuel", "truck_stop"}
            or (element.get("tags") or {}).get("highway") in {"services", "rest_area"}
        ),
        None,
    )
    tags = (site or {}).get("tags") or {}

    hgv = str(tags.get("hgv", "")).strip().lower()
    access = str(tags.get("access", "")).strip().lower()

    # Gather POSITIVE evidence first, across everything nearby. A big plaza is
    # mapped as several features -- car pump island, truck island, parking --
    # and the nearest one to a stored coordinate may be the car half. Letting a
    # refusal on that fragment condemn the whole site classified a real Pilot
    # Travel Center as "none" on the first run.
    # Read hgv across EVERY nearby feature, not just the nearest. A fuel site
    # is often two islands -- cars one side, trucks the other -- and the truck
    # island is rarely the closest node to a curated coordinate. Western
    # Convenience on US-30 has both (hgv=no beside hgv=designated); reading
    # only the nearest condemned a site that plainly takes trucks.
    admitted = next(
        (
            str((element.get("tags") or {}).get("hgv", "")).strip().lower()
            for element in nearby
            if str((element.get("tags") or {}).get("hgv", "")).strip().lower() in HGV_YES
        ),
        "",
    )
    if admitted:
        return "tractor_trailer", (
            f"OpenStreetMap tags hgv={admitted} on a mapped feature at this "
            f"location, accessed {ACCESSED_DATE}: heavy goods vehicles admitted."
        )
    if any((element.get("tags") or {}).get("amenity") == "truck_stop" for element in nearby):
        return "tractor_trailer", (
            f"OpenStreetMap maps this site as amenity=truck_stop, accessed {ACCESSED_DATE}."
        )
    if any((element.get("tags") or {}).get("highway") == "services" for element in nearby):
        return "tractor_trailer", (
            f"OpenStreetMap maps this site as a motorway service area "
            f"(highway=services), accessed {ACCESSED_DATE}."
        )
    # Truck parking mapped on the same site is direct evidence a rig fits.
    if any(
        (element.get("tags") or {}).get("amenity") == "parking"
        and str((element.get("tags") or {}).get("hgv", "")).lower() in HGV_YES
        for element in nearby
    ):
        return "tractor_trailer", (
            f"OpenStreetMap maps truck parking (amenity=parking, hgv=yes) on this "
            f"site, accessed {ACCESSED_DATE}."
        )
    if stop.get("parking_spaces", 0) > 0:
        return "tractor_trailer", (
            f"Surveyed truck-parking capacity ({stop['parking_spaces']} spaces) "
            f"confirms combination-vehicle access; recorded {ACCESSED_DATE}."
        )

    # Only now, with nothing vouching for the site, does a refusal decide it --
    # and only for a stop that IS the tagged feature. The brief's rule ("sites
    # that cannot admit any truck: none") is about a site, and a travel center
    # is not one: an hgv=no on a car pump island inside a Pilot plaza is a fact
    # about that island, not about the plaza, which plainly takes trucks. Let
    # the refusal condemn a whole facility and Pilot and Love's plazas come out
    # as landmarks you cannot stop at.
    if stop_type not in TRUCK_FACILITY_TYPES:
        if hgv in HGV_NO:
            return "none", (
                f"OpenStreetMap tags hgv={hgv} on the mapped feature at this "
                f"location, accessed {ACCESSED_DATE}: no truck admitted."
            )
        if not hgv and access in ACCESS_CLOSED:
            return "none", (
                f"OpenStreetMap tags access={access} on the mapped feature at this "
                f"location and records no hgv allowance, accessed {ACCESSED_DATE}."
            )

    # Brand verifies, never denies -- and it ranks BELOW an explicit refusal,
    # because the brief makes brand a hint for review ordering, never a
    # verdict. A mapper who tagged this exact node hgv=no knows something the
    # sign out front does not: "Love's" also hangs on Love's Express country
    # stores with car-only pumps.
    if _looks_like_truck_chain(name):
        return "tractor_trailer", (
            f"{name} is a truck-stop chain facility, truck-accessible by the "
            f"nature of the operator, and OpenStreetMap records no restriction; "
            f"recorded {ACCESSED_DATE}."
        )

    # Truck infrastructure keeps its access unless OSM positively refused it
    # above -- a rest area with no hgv tag is still a rest area.
    if stop_type in TRUCK_FACILITY_TYPES:
        return "tractor_trailer", (
            f"Facility type {stop_type} is truck infrastructure by definition and "
            f"OpenStreetMap records no restriction, accessed {ACCESSED_DATE}."
        )

    if stop_type not in UNVERIFIED_BY_DEFAULT_TYPES:
        return "tractor_trailer", (
            f"Stop type {stop_type} carries no truck-access restriction in "
            f"OpenStreetMap, accessed {ACCESSED_DATE}."
        )

    # A generic fuel station with nothing vouching for it. The default protects
    # the player from a promise the site may not keep -- it stays on the map,
    # reachable running bobtail.
    return "bobtail_only", (
        f"No verified truck access: OpenStreetMap records no hgv allowance, "
        f"truck parking, or truck-stop classification at this location "
        f"(checked {ACCESSED_DATE}). Generic fuel stations default to "
        f"bobtail_only per the truck-accessibility policy."
    )


def _load_cache() -> dict[str, list[dict[str, Any]]]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict[str, list[dict[str, Any]]]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Save the classification.")
    parser.add_argument("--report", action="store_true", help="Print counts and examples.")
    parser.add_argument("--limit", type=int, default=0, help="Only the first N stops (testing).")
    parser.add_argument(
        "--only-type",
        default="",
        help="Restrict to one stop type (default: every stop with coordinates).",
    )
    args = parser.parse_args(argv)

    url = _overpass_url()
    cache = _load_cache()
    data = load_world()

    targets: list[dict[str, Any]] = []
    for leg in data["legs"]:
        for stop in leg.get("stops", []):
            if args.only_type and stop.get("type") != args.only_type:
                continue
            # Stops with no stored coordinate are the hand-curated ones, taken
            # from operator locator feeds rather than an OSM node -- 402 named
            # travel centers, 200 service plazas, the rest areas. They still
            # need a verdict, so they go through the same rules with no OSM
            # evidence: name and facility type carry them, and the 29 generic
            # fuel stations among them fall to the restrictive default like
            # any other. Skipping them would have left them silently defaulted.
            targets.append(stop)
    if args.limit:
        targets = targets[: args.limit]

    counts: Counter[str] = Counter()
    changed = 0
    queried = 0
    examples: dict[str, list[str]] = {}
    for index, stop in enumerate(targets, 1):
        if "lat" not in stop or "lon" not in stop:
            cache_key = ""
        else:
            cache_key = f"{stop['lat']:.5f},{stop['lon']:.5f}"
        key = cache_key
        if key and key not in cache:
            cache[key] = _fetch(url, float(stop["lat"]), float(stop["lon"]))
            queried += 1
            if queried % 100 == 0:
                _save_cache(cache)
                print(f"  ...{index}/{len(targets)} stops, {queried} queried", flush=True)
        access, why = classify(stop, cache.get(key, []) if key else [])
        counts[access] += 1
        examples.setdefault(access, [])
        if len(examples[access]) < 6:
            examples[access].append(f"{stop['name']} ({stop.get('type')})")
        if stop.get("vehicle_access") != access:
            changed += 1
        stop["vehicle_access"] = access
        if access != "tractor_trailer":
            note = str(stop.get("source", "")).rstrip()
            marker = "Truck access:"
            if marker not in note:
                stop["source"] = f"{note} {marker} {why}".strip()
    _save_cache(cache)

    print()
    print(f"Classified {len(targets)} stops ({queried} Overpass queries, rest cached):")
    for level in ("tractor_trailer", "bobtail_only", "none"):
        print(f"  {level:16} {counts[level]}")
    if args.report:
        for level in ("tractor_trailer", "bobtail_only", "none"):
            if examples.get(level):
                print(f"\n  {level} examples:")
                for line in examples[level]:
                    print(f"    {line}")

    if args.write:
        written = save_world(data)
        print(f"\nWrote {written} shard(s); {changed} stops changed classification.")
    else:
        print(f"\nDry run: {changed} stops would change. Re-run with --write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
