"""Catalog snapshot shared with the orinks.net cloud-save validator."""

from __future__ import annotations

import json
from pathlib import Path

from .achievements import ACHIEVEMENTS
from .models.career import LEVEL_XP, Career
from .models.market import MARKET_CARGO_KEYS
from .models.profile import SAVE_VERSION, Profile
from .models.trucks import TRUCK_CATALOG, UPGRADE_CATALOG, TruckCondition

# Signature keys ride inside the saved file but never inside a cloud upload --
# the upload strips them and the server signs its own revision instead.
_LOCAL_ONLY_FIELDS = frozenset({"_signature", "_signature_version"})


def _json_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def _profile_fields() -> list[str]:
    """Top-level keys a cloud upload carries, straight off the dataclass.

    The validator checks uploads against an exact field list. Hand-keeping
    that list on the server means it silently falls behind the moment a field
    is added or removed here -- and the failure is a flat schema rejection
    that reads to the player as "your backup is broken", not as version skew.
    Export it instead, so the two sides cannot drift.
    """
    return sorted((set(Profile.__dataclass_fields__) | {"version"}) - _LOCAL_ONLY_FIELDS)


def _truck_condition_fields() -> list[str]:
    """Keys inside one owned truck's condition record.

    Same reason as _profile_fields, one level down: the validator checks each
    record against an exact list, and this record is where new per-truck state
    lands (brake and engine wear, traction gear). A hand-kept copy on the
    server would reject the next build's saves the moment one is added.
    """
    return sorted(TruckCondition.__dataclass_fields__)


def invariant_data() -> dict:
    # Source-tree-only export for the orinks.net validator; never called by
    # the game at runtime, so frozen builds (which carry no world_data
    # tree) are unaffected.
    data_root = Path(__file__).resolve().parent / "data" / "world_data"
    cities = json.loads((data_root / "us" / "cities.json").read_text(encoding="utf-8"))[
        "cities"
    ]  # runtime-data-ok
    countries = json.loads((data_root / "geo.json").read_text(encoding="utf-8"))[
        "countries"
    ]  # runtime-data-ok
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
        "profileFields": _profile_fields(),
        "careerFields": sorted(Career.__dataclass_fields__),
        "truckConditionFields": _truck_condition_fields(),
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
