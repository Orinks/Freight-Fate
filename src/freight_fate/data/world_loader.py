from __future__ import annotations

import json
from pathlib import Path


def load_world_data(root: Path) -> dict:
    """Load indexed country data from world_data/index.json."""
    index_path = root / "index.json"
    index = _load_json(index_path)
    if "countries" not in index:
        raise ValueError(f"{index_path} does not contain a 'countries' list")

    data = {"cities": {}, "legs": []}
    # Spoken-name lookup for state and country codes ("MS" -> "Mississippi").
    # Optional so pre-slug data trees and minimal test fixtures still load.
    geo_path = root / "geo.json"
    if geo_path.exists():
        data["geo"] = _load_json(geo_path)
    for country in index["countries"]:
        code = country["code"]
        country_dir = root / country["path"]
        cities_path = country_dir / country.get("cities", "cities.json")
        legs_path = country_dir / country.get("legs", "legs.json")
        cities_data = _load_json(cities_path)
        legs_data = _load_json(legs_path)

        if "cities" not in cities_data:
            raise ValueError(f"{cities_path} does not contain a 'cities' object")
        if "legs" not in legs_data:
            raise ValueError(f"{legs_path} does not contain a 'legs' list")

        for name, city in cities_data["cities"].items():
            if name in data["cities"]:
                raise ValueError(f"Duplicate city {name!r} in {cities_path}")
            city.setdefault("country", code)
            data["cities"][name] = city
        data["legs"].extend(legs_data["legs"])
    return data


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
