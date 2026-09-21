from __future__ import annotations

import json
from pathlib import Path


def _load_legs(country_dir: Path, country: dict) -> list:
    """Read a country's legs, from a sharded ``legs/`` directory or one file.

    The US legs outgrew a single 60 MB file, so they ship as per-state shards
    an index entry points at with ``legs_dir``. Shards are read in sorted
    filename order, which is the order the build tools write them in, so the
    merged list is the same every load. Small trees (test fixtures, any future
    country that stays small) can still name a single ``legs`` file.
    """
    legs_dir = country.get("legs_dir")
    if legs_dir:
        legs = []
        for shard in sorted((country_dir / legs_dir).glob("*.json")):
            shard_data = _load_json(shard)
            if "legs" not in shard_data:
                raise ValueError(f"{shard} does not contain a 'legs' list")
            legs.extend(shard_data["legs"])
        return legs

    legs_path = country_dir / country.get("legs", "legs.json")
    legs_data = _load_json(legs_path)
    if "legs" not in legs_data:
        raise ValueError(f"{legs_path} does not contain a 'legs' list")
    return legs_data["legs"]


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
        cities_data = _load_json(cities_path)

        if "cities" not in cities_data:
            raise ValueError(f"{cities_path} does not contain a 'cities' object")
        legs = _load_legs(country_dir, country)

        for name, city in cities_data["cities"].items():
            if name in data["cities"]:
                raise ValueError(f"Duplicate city {name!r} in {cities_path}")
            city.setdefault("country", code)
            data["cities"][name] = city
        data["legs"].extend(legs)
    return data


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
