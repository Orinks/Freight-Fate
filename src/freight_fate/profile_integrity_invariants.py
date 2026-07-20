"""Catalog snapshot shared with the orinks.net cloud-save validator."""

from __future__ import annotations

import json
from pathlib import Path

from .achievements import ACHIEVEMENTS
from .models.career import LEVEL_XP, XP_PER_MILE_ON_TIME, Career
from .models.economy import PAY_ADVANCE_LIMIT
from .models.market import MARKET_CARGO_KEYS
from .models.profile import SAVE_VERSION, STARTING_MONEY, Profile
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


def _xp_per_mile_max() -> float:
    """The most XP one mile can teach, taking every bonus at its best.

    The validator's ceiling is `deliveries * flat + miles * this`. It has to
    sit at or above what the game can actually award, because anything lower
    convicts honest drivers -- the tighter the fit, the more a later balance
    pass costs. Recompute it here from the real constants when the XP model
    grows terms (class, streak, and condition multipliers all land on this
    line in the 1.9 career arc).
    """
    return XP_PER_MILE_ON_TIME


def _xp_flat_per_delivery() -> float:
    """XP a settled load teaches regardless of distance (none on this line)."""
    return 0.0


def _truck_condition_fields() -> list[str]:
    """Keys inside one owned truck's condition record.

    Same reason as _profile_fields, one level down: the validator checks each
    record against an exact list, and this record is where new per-truck state
    lands (brake and engine wear, traction gear). A hand-kept copy on the
    server would reject the next build's saves the moment one is added.
    """
    return sorted(TruckCondition.__dataclass_fields__)


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
        # The economy terms the cloud-save validator needs to tell an edited
        # career from an honest one. They ship as data for the same reason the
        # field lists do: a copy kept on the server falls behind the next
        # balance pass, and every honest player on the new build then hears
        # that their backup was rejected. See the money and XP checks in
        # convex/freightFateSharedProfileValidation.ts.
        "startingMoney": _json_number(STARTING_MONEY),
        "payAdvanceLimit": _json_number(PAY_ADVANCE_LIMIT),
        "xpPerMileMax": _json_number(_xp_per_mile_max()),
        "xpFlatPerDelivery": _json_number(_xp_flat_per_delivery()),
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
