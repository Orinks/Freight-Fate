"""Catalog snapshot shared with the orinks.net cloud-save validator."""

from __future__ import annotations

import json
from pathlib import Path

from .achievements import ACHIEVEMENTS
from .models.career import LEVEL_XP
from .models.market import MARKET_CARGO_KEYS
from .models.profile import SAVE_VERSION
from .models.trucks import TRUCK_CATALOG, UPGRADE_CATALOG


def _json_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def invariant_data() -> dict:
    data_root = Path(__file__).resolve().parent / "data" / "world_data"
    cities = json.loads((data_root / "us" / "cities.json").read_text(encoding="utf-8"))["cities"]
    countries = json.loads((data_root / "geo.json").read_text(encoding="utf-8"))["countries"]
    states = countries["US"]["states"]
    city_labels = {
        slug: f"{city['spoken_city']}, {states.get(city.get('state'), city.get('state', ''))}".rstrip(
            ", "
        )
        for slug, city in cities.items()
    }
    return {
        "achievementIds": sorted(achievement.id for achievement in ACHIEVEMENTS),
        "cityLabels": dict(sorted(city_labels.items())),
        "levelXp": LEVEL_XP,
        "marketCargoKeys": sorted(MARKET_CARGO_KEYS),
        "sourceSaveVersion": SAVE_VERSION,
        "truckLabels": {key: truck.label for key, truck in TRUCK_CATALOG.items()},
        "truckPrices": {key: _json_number(truck.price) for key, truck in TRUCK_CATALOG.items()},
        "upgradePrices": {
            key: [_json_number(price) for price in upgrade.prices]
            for key, upgrade in UPGRADE_CATALOG.items()
        },
    }


def rendered_invariants() -> str:
    return json.dumps(invariant_data(), indent=2, sort_keys=True) + "\n"
