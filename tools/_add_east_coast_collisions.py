"""One-off: add the 4 name-collision East Coast cities under disambiguated keys.

Charleston SC, Wilmington NC, Portland OR, and Springfield MO already own the
bare keys, so these get natural "City, State" keys (also the spoken form, so a
screen reader says the full unambiguous name). Coords are GeoNames; region is
derived by the project classifier. Same bare-leg approach as the main batch;
corridors/miles/POIs are filled by enrich_routes afterward.
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

# key -> (state, lat, lon, locations)
CITIES = {
    "Charleston, West Virginia": ("West Virginia", 38.34982, -81.63262, [
        {"name": "Kanawha Valley Chemical Terminal", "type": "terminal",
         "cargo": ["bulk", "general"]},
        {"name": "Charleston Distribution Center", "type": "distribution",
         "cargo": ["retail", "food"]},
    ]),
    "Portland, Maine": ("Maine", 43.66147, -70.25533, [
        {"name": "Portland Marine Terminal", "type": "port",
         "cargo": ["container", "refrigerated"]},
        {"name": "Casco Bay Cold Storage", "type": "distribution",
         "cargo": ["food", "refrigerated"]},
    ]),
    "Springfield, Massachusetts": ("Massachusetts", 42.10148, -72.58981, [
        {"name": "Springfield Rail Yard", "type": "rail",
         "cargo": ["machinery", "bulk"]},
        {"name": "Pioneer Valley Distribution", "type": "distribution",
         "cargo": ["retail", "food"]},
    ]),
    "Wilmington, Delaware": ("Delaware", 39.74595, -75.54659, [
        {"name": "Port of Wilmington", "type": "port",
         "cargo": ["container", "refrigerated"]},
        {"name": "Wilmington Chemical Terminal", "type": "terminal",
         "cargo": ["bulk", "general"]},
    ]),
}

# Undirected adjacencies (one entry each); neighbors are existing or main-batch.
ADJACENCIES = [
    ("Charleston, West Virginia", "Pittsburgh"),
    ("Charleston, West Virginia", "Roanoke"),
    ("Charleston, West Virginia", "Richmond"),
    ("Portland, Maine", "Manchester"),
    ("Portland, Maine", "Boston"),
    ("Springfield, Massachusetts", "Hartford"),
    ("Springfield, Massachusetts", "Worcester"),
    ("Springfield, Massachusetts", "Albany"),
    ("Springfield, Massachusetts", "New Haven"),
    ("Wilmington, Delaware", "Philadelphia"),
    ("Wilmington, Delaware", "Baltimore"),
    ("Wilmington, Delaware", "Salisbury"),
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
    for key, (state, lat, lon, locs) in CITIES.items():
        if key in cities:
            raise SystemExit(f"key collision: {key!r}")
        cities[key] = {
            "state": state,
            "region": classify_region(state, lat, lon),
            "locations": locs,
            "lat": round(lat, 4),
            "lon": round(lon, 4),
        }

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

    WORLD.write_text(json.dumps(world, indent=2) + "\n", encoding="utf-8")
    print(f"added {len(CITIES)} cities, {added} legs")
    print(f"world now: {len(cities)} cities, {len(world['legs'])} legs")
    # Append these legs to the ORS-mileage adoption list (';'-separated).
    new_pairs = [f"{a}:{b}" for a, b in ADJACENCIES]
    list_path = ROOT / ".route-cache" / "new_legs.txt"
    prev = list_path.read_text(encoding="utf-8").strip() if list_path.exists() else ""
    prev_pairs = [p for p in prev.replace(",", ";").split(";") if p]
    all_pairs = prev_pairs + new_pairs
    list_path.write_text(";".join(all_pairs), encoding="utf-8")
    print(f"adoption list now {len(all_pairs)} legs (';'-separated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
