"""One-off: add a 2nd freight city to each single-city state (depth pass).

Brings the 13 thin states (one city each) up to two, so every contiguous state
has real intrastate presence and better through-routing. Same documented
pipeline as the East Coast batch: coords from pick_nodes/GeoNames, region from
classify_region, bare legs (highway TBD, haversine seed miles) enriched
afterward by enrich_routes --engine ors + --adopt-ors-miles + POI pass.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, "src")
from freight_fate.data.regions import classify_region  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "src" / "freight_fate" / "data" / "world.json"

# name -> (state, lat, lon, locations). Coords: pick_nodes pool or GeoNames.
CITIES = {
    "Fort Smith": ("Arkansas", 35.38592, -94.39855, [
        {"name": "River Valley Distribution", "type": "distribution",
         "cargo": ["retail", "general"]},
        {"name": "Fort Smith Freight Terminal", "type": "terminal",
         "cargo": ["machinery", "bulk"]}]),
    "Dover": ("Delaware", 39.15817, -75.52437, [
        {"name": "Dover Distribution Center", "type": "distribution",
         "cargo": ["retail", "food"]},
        {"name": "Kent County Warehouse", "type": "warehouse",
         "cargo": ["general", "electronics"]}]),
    "Bangor": ("Maine", 44.80118, -68.77781, [
        {"name": "Bangor Freight Terminal", "type": "terminal",
         "cargo": ["general", "food"]},
        {"name": "Penobscot Distribution", "type": "distribution",
         "cargo": ["retail", "refrigerated"]}]),
    "Duluth": ("Minnesota", 46.78327, -92.10658, [
        {"name": "Port of Duluth-Superior", "type": "port",
         "cargo": ["bulk", "container"]},
        {"name": "Twin Ports Distribution", "type": "distribution",
         "cargo": ["retail", "general"]}]),
    "Gulfport": ("Mississippi", 30.36742, -89.09282, [
        {"name": "Port of Gulfport", "type": "port",
         "cargo": ["container", "refrigerated"]},
        {"name": "Gulf Coast Distribution", "type": "distribution",
         "cargo": ["retail", "food"]}]),
    "Missoula": ("Montana", 46.87215, -113.994, [
        {"name": "Missoula Freight Yard", "type": "rail",
         "cargo": ["machinery", "bulk"]},
        {"name": "Bitterroot Distribution", "type": "distribution",
         "cargo": ["retail", "general"]}]),
    "Portsmouth": ("New Hampshire", 43.07176, -70.76256, [
        {"name": "Port of New Hampshire", "type": "port",
         "cargo": ["bulk", "general"]},
        {"name": "Seacoast Distribution", "type": "distribution",
         "cargo": ["retail", "food"]}]),
    "Bismarck": ("North Dakota", 46.80833, -100.78374, [
        {"name": "Bismarck Distribution Center", "type": "distribution",
         "cargo": ["retail", "general"]},
        {"name": "Missouri Valley Warehouse", "type": "warehouse",
         "cargo": ["machinery", "bulk"]}]),
    "Westerly": ("Rhode Island", 41.37760, -71.82728, [
        {"name": "Westerly Distribution", "type": "distribution",
         "cargo": ["retail", "general"]},
        {"name": "Pawcatuck Warehouse", "type": "warehouse",
         "cargo": ["food", "general"]}]),
    "Rapid City": ("South Dakota", 44.08054, -103.23101, [
        {"name": "Black Hills Distribution", "type": "distribution",
         "cargo": ["retail", "general"]},
        {"name": "Rapid City Freight Terminal", "type": "terminal",
         "cargo": ["machinery", "bulk"]}]),
    "Montpelier": ("Vermont", 44.26006, -72.57539, [
        {"name": "Montpelier Freight Depot", "type": "terminal",
         "cargo": ["general", "food"]},
        {"name": "Central Vermont Warehouse", "type": "warehouse",
         "cargo": ["retail", "machinery"]}]),
    "Morgantown": ("West Virginia", 39.62953, -79.95590, [
        {"name": "Morgantown Distribution", "type": "distribution",
         "cargo": ["retail", "general"]},
        {"name": "Monongahela Industrial Park", "type": "industrial_park",
         "cargo": ["machinery", "bulk"]}]),
    "Rock Springs": ("Wyoming", 41.58746, -109.20290, [
        {"name": "Rock Springs Freight Terminal", "type": "terminal",
         "cargo": ["bulk", "machinery"]},
        {"name": "Sweetwater Distribution", "type": "distribution",
         "cargo": ["retail", "general"]}]),
}

ADJACENCIES = [
    ("Fort Smith", "Little Rock"), ("Fort Smith", "Tulsa"),
    ("Dover", "Wilmington, Delaware"), ("Dover", "Salisbury"),
    ("Bangor", "Portland, Maine"), ("Bangor", "Manchester"),
    ("Duluth", "Minneapolis"), ("Duluth", "Fargo"),
    ("Gulfport", "New Orleans"), ("Gulfport", "Jackson"),
    ("Missoula", "Billings"), ("Missoula", "Spokane"),
    ("Portsmouth", "Portland, Maine"), ("Portsmouth", "Manchester"),
    ("Portsmouth", "Boston"),
    ("Bismarck", "Fargo"), ("Bismarck", "Billings"),
    ("Westerly", "Providence"), ("Westerly", "New Haven"),
    ("Rapid City", "Sioux Falls"), ("Rapid City", "Billings"),
    ("Montpelier", "Burlington"), ("Montpelier", "Manchester"),
    ("Morgantown", "Pittsburgh"), ("Morgantown", "Charleston, West Virginia"),
    ("Rock Springs", "Cheyenne"), ("Rock Springs", "Salt Lake City"),
]

ROAD_CIRCUITY = 1.2


def haversine_mi(a, b):
    r = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def main() -> int:
    world = json.loads(WORLD.read_text(encoding="utf-8"))
    cities = world["cities"]
    for name, (state, lat, lon, locs) in CITIES.items():
        if name in cities:
            raise SystemExit(f"key collision: {name!r}")
        cities[name] = {"state": state, "region": classify_region(state, lat, lon),
                        "locations": locs, "lat": round(lat, 4), "lon": round(lon, 4)}

    existing = {frozenset((leg["from"], leg["to"])) for leg in world["legs"]}
    added = 0
    for a, b in ADJACENCIES:
        if a not in cities or b not in cities:
            raise SystemExit(f"leg references unknown city: {a} / {b}")
        if frozenset((a, b)) in existing:
            continue
        ca = (cities[a]["lat"], cities[a]["lon"])
        cb = (cities[b]["lat"], cities[b]["lon"])
        miles = round(haversine_mi(ca, cb) * ROAD_CIRCUITY)
        world["legs"].append({"from": a, "to": b, "miles": miles,
                              "highway": "TBD", "terrain": "flat"})
        existing.add(frozenset((a, b)))
        added += 1

    # degree check
    deg: dict[str, int] = {}
    for leg in world["legs"]:
        deg[leg["from"]] = deg.get(leg["from"], 0) + 1
        deg[leg["to"]] = deg.get(leg["to"], 0) + 1
    under = [n for n in CITIES if deg.get(n, 0) < 2]
    if under:
        raise SystemExit(f"degree<2 cities: {under}")

    WORLD.write_text(json.dumps(world, indent=2) + "\n", encoding="utf-8")
    print(f"added {len(CITIES)} cities, {added} legs")
    print(f"world now: {len(cities)} cities, {len(world['legs'])} legs")
    (ROOT / ".route-cache" / "depth_legs.txt").write_text(
        ";".join(f"{a}:{b}" for a, b in ADJACENCIES), encoding="utf-8")
    print(f"adoption list: {len(ADJACENCIES)} legs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
