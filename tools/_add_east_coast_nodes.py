"""One-off: add the East Coast expansion nodes + bare legs to world.json.

This is the deliberate "add nodes/legs" step of the documented pipeline
(docs/osm-routing-plan.md): coordinates/region come from tools/pick_nodes.py
(GeoNames + classify_region), legs are bare (highway "TBD", placeholder miles
via haversine). The corridor geometry, elevation, terrain, highway shields,
state crossings, POIs, and real ORS truck miles are filled afterward by
`enrich_routes.py --enrich-all --engine ors --write` and `--adopt-ors-miles`.
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
CANDS = ROOT / ".route-cache" / "node_candidates.json"

# (name, state) -> coords come from pick_nodes candidates; SALISBURY (MD) and any
# pick_nodes name-collision are sourced from GeoNames here. Region is always
# derived by the project classifier, never hand-typed.
MANUAL_COORDS = {
    ("Salisbury", "Maryland"): (38.36067, -75.59937),
}

# 2 freight locations per city (cargo categories + types from the existing world
# vocabulary). Real facility names where known.
LOCATIONS = {
    "Newark": [
        {"name": "Port Newark Container Terminal", "type": "port",
         "cargo": ["container", "general"]},
        {"name": "Meadowlands Distribution Center", "type": "distribution",
         "cargo": ["retail", "food"]},
    ],
    "Trenton": [
        {"name": "Trenton Freight Terminal", "type": "terminal",
         "cargo": ["general", "machinery"]},
        {"name": "Hamilton Distribution Park", "type": "distribution",
         "cargo": ["retail", "electronics"]},
    ],
    "Atlantic City": [
        {"name": "Egg Harbor Distribution", "type": "distribution",
         "cargo": ["food", "refrigerated"]},
        {"name": "Atlantic Coast Warehouse", "type": "warehouse",
         "cargo": ["retail", "general"]},
    ],
    "Salisbury": [
        {"name": "Delmarva Poultry Cold Storage", "type": "distribution",
         "cargo": ["food", "refrigerated"]},
        {"name": "Salisbury Distribution Center", "type": "warehouse",
         "cargo": ["retail", "general"]},
    ],
    "Burlington": [
        {"name": "Burlington Freight Depot", "type": "terminal",
         "cargo": ["general", "food"]},
        {"name": "Champlain Valley Warehouse", "type": "warehouse",
         "cargo": ["retail", "machinery"]},
    ],
    "Norfolk": [
        {"name": "Norfolk International Terminals", "type": "port",
         "cargo": ["container", "machinery"]},
        {"name": "Hampton Roads Distribution", "type": "distribution",
         "cargo": ["retail", "refrigerated"]},
    ],
    "Harrisburg": [
        {"name": "Capital Region Intermodal", "type": "intermodal",
         "cargo": ["container", "machinery"]},
        {"name": "Harrisburg Distribution Hub", "type": "distribution",
         "cargo": ["retail", "general"]},
    ],
    "Scranton": [
        {"name": "Scranton Intermodal Terminal", "type": "intermodal",
         "cargo": ["container", "general"]},
        {"name": "Lackawanna Distribution Center", "type": "distribution",
         "cargo": ["retail", "food"]},
    ],
    "Binghamton": [
        {"name": "Binghamton Rail Yard", "type": "rail",
         "cargo": ["machinery", "bulk"]},
        {"name": "Southern Tier Warehouse", "type": "warehouse",
         "cargo": ["general", "electronics"]},
    ],
    "Erie": [
        {"name": "Port of Erie", "type": "port",
         "cargo": ["bulk", "container"]},
        {"name": "Erie Manufacturing Works", "type": "manufacturing",
         "cargo": ["machinery", "general"]},
    ],
    "New Haven": [
        {"name": "New Haven Port Terminal", "type": "port",
         "cargo": ["bulk", "general"]},
        {"name": "Long Wharf Distribution", "type": "distribution",
         "cargo": ["food", "retail"]},
    ],
    "Augusta": [
        {"name": "Savannah River Terminal", "type": "terminal",
         "cargo": ["bulk", "machinery"]},
        {"name": "Augusta Distribution Center", "type": "distribution",
         "cargo": ["retail", "general"]},
    ],
    "Macon": [
        {"name": "Macon Intermodal Park", "type": "intermodal",
         "cargo": ["container", "retail"]},
        {"name": "Middle Georgia Distribution", "type": "distribution",
         "cargo": ["food", "general"]},
    ],
    "Greenville": [
        {"name": "Upstate Inland Port", "type": "intermodal",
         "cargo": ["container", "machinery"]},
        {"name": "Greenville Distribution Center", "type": "distribution",
         "cargo": ["retail", "electronics"]},
    ],
}

# Target nodes (name, state). Region/coords derived; locations from LOCATIONS.
TARGETS = [
    ("Newark", "New Jersey"), ("Trenton", "New Jersey"),
    ("Atlantic City", "New Jersey"), ("Salisbury", "Maryland"),
    ("Burlington", "Vermont"), ("Norfolk", "Virginia"),
    ("Harrisburg", "Pennsylvania"), ("Scranton", "Pennsylvania"),
    ("Erie", "Pennsylvania"), ("Binghamton", "New York"),
    ("New Haven", "Connecticut"), ("Augusta", "Georgia"),
    ("Macon", "Georgia"), ("Greenville", "South Carolina"),
]

# Undirected adjacencies (listed once). Each pair: one new city + neighbor.
ADJACENCIES = [
    ("Newark", "New York"), ("Newark", "Philadelphia"),
    ("Newark", "Trenton"), ("Newark", "Allentown"),
    ("Trenton", "Philadelphia"), ("Trenton", "Atlantic City"),
    ("Atlantic City", "Philadelphia"),
    ("Salisbury", "Baltimore"), ("Salisbury", "Norfolk"),
    ("Burlington", "Albany"), ("Burlington", "Manchester"),
    ("Norfolk", "Virginia Beach"), ("Norfolk", "Richmond"),
    ("Norfolk", "Raleigh"),
    ("Harrisburg", "Philadelphia"), ("Harrisburg", "Baltimore"),
    ("Harrisburg", "Allentown"), ("Harrisburg", "Pittsburgh"),
    ("Harrisburg", "Scranton"),
    ("Scranton", "Allentown"), ("Scranton", "Binghamton"),
    ("Binghamton", "Syracuse"), ("Binghamton", "Albany"),
    ("Erie", "Pittsburgh"), ("Erie", "Buffalo"), ("Erie", "Cleveland"),
    ("New Haven", "Bridgeport"), ("New Haven", "Hartford"),
    ("New Haven", "New York"),
    ("Augusta", "Atlanta"), ("Augusta", "Columbia"),
    ("Augusta", "Savannah"), ("Augusta", "Macon"),
    ("Macon", "Atlanta"), ("Macon", "Savannah"),
    ("Greenville", "Atlanta"), ("Greenville", "Charlotte"),
    ("Greenville", "Columbia"),
]

ROAD_CIRCUITY = 1.2  # placeholder miles; ORS adopts the real truck distance


def haversine_mi(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def main() -> int:
    world = json.loads(WORLD.read_text(encoding="utf-8"))
    cities = world["cities"]
    cand_index = {}
    for c in json.loads(CANDS.read_text(encoding="utf-8")):
        cand_index[(c["name"], c["state"])] = (c["lat"], c["lon"])

    added_cities = []
    for name, state in TARGETS:
        if name in cities:
            raise SystemExit(f"key collision: {name!r} already in world.json")
        lat, lon = MANUAL_COORDS.get((name, state)) or cand_index[(name, state)]
        cities[name] = {
            "state": state,
            "region": classify_region(state, lat, lon),
            "locations": LOCATIONS[name],
            "lat": round(lat, 4),
            "lon": round(lon, 4),
        }
        added_cities.append(name)

    existing = {frozenset((leg["from"], leg["to"])) for leg in world["legs"]}
    added_legs = 0
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
        added_legs += 1

    WORLD.write_text(json.dumps(world, indent=2) + "\n", encoding="utf-8")
    print(f"added {len(added_cities)} cities, {added_legs} legs")
    print("cities:", ", ".join(added_cities))
    print(f"world now: {len(cities)} cities, {len(world['legs'])} legs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
