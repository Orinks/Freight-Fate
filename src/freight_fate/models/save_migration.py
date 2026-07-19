"""Save-format migrations: upgrade older save dicts to the current shape.

``Profile.from_dict`` runs :func:`migrate_save_data` on every raw save dict
before parsing, so all entry points -- disk loads, cloud restores -- see the
current schema. Each migration works on the plain dict, never on a Profile
instance, and must tolerate missing or malformed fields: an old save that
survived loading before must keep loading after.
"""

from __future__ import annotations

from dataclasses import asdict

from .trucks import TruckCondition, build_truck_specs

# Flat per-profile condition fields written by save versions 4 and earlier,
# before each owned truck kept its own record.
LEGACY_TRUCK_FIELDS = (
    "truck_fuel_gal",
    "truck_damage_pct",
    "tire_wear_pct",
    "road_grime_pct",
)


def migrate_save_data(data: dict) -> tuple[dict, bool]:
    """Return ``(data upgraded to the current shape, whether anything changed)``."""
    version = data.get("version")
    if isinstance(version, int) and version >= 5:
        return data, False
    return _migrate_to_per_truck_conditions(dict(data)), True


def _migrate_to_per_truck_conditions(data: dict) -> dict:
    """v4 -> v5: move the flat condition fields into per-truck records.

    The truck the player was driving keeps its values (clamped to honest
    ranges); every other owned truck starts purchase-fresh.
    """
    active = str(data.get("truck", "rig"))
    owned = data.get("owned_trucks")
    owned_keys = [str(k) for k in owned] if isinstance(owned, list) and owned else [active]
    upgrades = data.get("upgrades")
    if not isinstance(upgrades, dict):
        upgrades = {}
    conditions = {key: asdict(TruckCondition.fresh(key, upgrades)) for key in owned_keys}
    record = conditions.setdefault(active, asdict(TruckCondition.fresh(active, upgrades)))
    tank = build_truck_specs(active, upgrades).fuel_tank_gal
    for legacy_key, new_key, high in (
        ("truck_fuel_gal", "fuel_gal", tank),
        ("truck_damage_pct", "damage_pct", 100.0),
        ("tire_wear_pct", "tire_wear_pct", 100.0),
        ("road_grime_pct", "grime_pct", 100.0),
    ):
        value = data.pop(legacy_key, None)
        if isinstance(value, (int, float)):
            record[new_key] = max(0.0, min(high, float(value)))
    data["truck_conditions"] = conditions
    data["migration_notice_pending"] = True
    return data
