"""Save-format migrations: upgrade older save dicts to the current shape.

``Profile.from_dict`` runs :func:`migrate_save_data` on every raw save dict
before parsing, so all entry points -- disk loads, cloud restores -- see the
current schema. Each migration works on the plain dict, never on a Profile
instance, and must tolerate missing or malformed fields: an old save that
survived loading before must keep loading after.
"""

from __future__ import annotations

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
    """Pre-per-truck save: flag the conversion, and leave the records to the
    profile.

    The fan-out itself lives in ``profile._migrate_flat_conditions``, which is
    the authority on a condition record's shape on this line -- it also carries
    brake wear, engine wear and traction gear, which this module's older
    four-field record knew nothing about. Building the records here would
    satisfy the profile's "already migrated?" check with a record missing those
    fields, and the wear would be lost on every legacy save. The flat fields are
    deliberately left in place for that fan-out to read.
    """
    data["migration_notice_pending"] = True
    return data
