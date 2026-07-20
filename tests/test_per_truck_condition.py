"""Condition follows the truck, not the profile.

Wear, damage, and fuel live in ``truck_conditions`` keyed by truck, and the
flat ``tire_wear_pct``/``truck_fuel_gal``/... names proxy to whichever truck
is active. These tests pin the invariants that matter for cheating and for
the future rental system: swapping tractors never teleports condition, the
garage fixes the truck you drove, and per-truck wear is under the save
signature just like money is.
"""

from __future__ import annotations

import json

from freight_fate.models import profile as profmod
from freight_fate.models.business import (
    COMPANY_DRIVER,
    LEASED_OWNER_OPERATOR,
)
from freight_fate.models.profile import Profile, _decode_save_bytes, encode_save_bytes


def _read_save(path):
    """The profile dict inside a save file, packed or legacy."""
    return _decode_save_bytes(path.read_bytes())[0]


def _write_packed(path, data):
    path.write_bytes(encode_save_bytes(data))


def _owner_operator_fleet() -> Profile:
    p = Profile(name="Fleet", business_status=LEASED_OWNER_OPERATOR)
    p.truck = "rig"
    p.owned_trucks = ["rig", "heavy_hauler"]
    p.provision_truck_condition("rig", 150.0)
    p.provision_truck_condition("heavy_hauler", 200.0)
    return p


def test_wear_accrues_per_truck_not_across_the_fleet():
    p = _owner_operator_fleet()

    p.tire_wear_pct = 25.0  # wear the rig we're driving
    assert p.active_truck_key() == "rig"
    assert p.tire_wear_pct == 25.0

    p.truck = "heavy_hauler"  # switch tractors at the dealer
    assert p.tire_wear_pct == 0.0  # the other truck is untouched

    p.truck = "rig"
    assert p.tire_wear_pct == 25.0  # rig kept its wear


def test_switching_trucks_does_not_teleport_fuel_or_damage():
    p = _owner_operator_fleet()
    p.truck_fuel_gal = 40.0
    p.truck_damage_pct = 12.0

    p.truck = "heavy_hauler"
    assert p.truck_fuel_gal == 200.0  # its own full tank, not the rig's 40
    assert p.truck_damage_pct == 0.0  # its own condition, not the rig's damage


def test_servicing_the_active_truck_leaves_parked_trucks_worn():
    p = _owner_operator_fleet()
    p.truck_conditions["heavy_hauler"]["tire_wear_pct"] = 40.0
    p.tire_wear_pct = 60.0

    p.tire_wear_pct = 0.0  # the garage services the truck we drove in

    assert p.tire_wear_pct == 0.0
    assert p.truck_conditions["heavy_hauler"]["tire_wear_pct"] == 40.0


def test_traction_equipment_rides_the_truck_record():
    """Tire compound and the chain set bolt to the truck: they follow a swap
    like wear does, and records saved before the fields existed read as the
    all-season, no-chains defaults."""
    p = _owner_operator_fleet()
    p.tire_type = "winter"
    p.chains_owned = True
    p.chain_wear_pct = 30.0

    p.truck = "heavy_hauler"  # the other tractor has its own equipment
    assert p.tire_type == "all_season"
    assert not p.chains_owned
    assert p.chain_wear_pct == 0.0

    p.truck = "rig"
    assert p.tire_type == "winter"
    assert p.chains_owned
    assert p.chain_wear_pct == 30.0

    # A record written before the equipment fields existed: defaults apply.
    del p.truck_conditions["rig"]["tire_type"]
    del p.truck_conditions["rig"]["chains_owned"]
    del p.truck_conditions["rig"]["chain_wear_pct"]
    assert p.tire_type == "all_season"
    assert not p.chains_owned
    assert p.chain_wear_pct == 0.0


def test_equipment_flows_through_the_truck_condition_funnel():
    """load/store round-trip: the compound reaches the TruckState, chain wear
    accrued on the road comes back, and the compound choice stays garage-only."""
    from freight_fate.sim.vehicle import TruckState

    p = _owner_operator_fleet()
    p.tire_type = "winter"
    p.chains_owned = True

    truck = TruckState()
    p.load_truck_condition(truck)
    assert truck.tire_type == "winter"
    assert truck.chain_wear_pct == 0.0

    truck.chain_wear_pct = 45.0  # a pass worth of chained miles
    p.store_truck_condition(truck)
    assert p.chain_wear_pct == 45.0
    assert p.tire_type == "winter"
    assert p.chains_owned  # ownership is profile equipment, not physics state


def test_company_driver_condition_keys_under_the_assigned_rig():
    p = Profile(name="Company", business_status=COMPANY_DRIVER)
    p.truck = "heavy_hauler"  # stray value; company drivers still run "rig"

    assert p.active_truck_key() == "rig"
    p.brake_wear_pct = 12.0

    assert p.truck_conditions["rig"]["brake_wear_pct"] == 12.0
    assert "heavy_hauler" not in p.truck_conditions


def test_legacy_flat_condition_fans_out_to_every_owned_truck():
    data = {
        "name": "Legacy Fleet",
        "business_status": LEASED_OWNER_OPERATOR,
        "truck": "rig",
        "owned_trucks": ["rig", "heavy_hauler"],
        "tire_wear_pct": 30.0,
        "brake_wear_pct": 20.0,
        "engine_wear_pct": 10.0,
        "truck_damage_pct": 15.0,
        "truck_fuel_gal": 60.0,
    }

    p = Profile.from_dict(data)

    # The active truck inherits the whole flat set, fuel included.
    assert p.active_truck_key() == "rig"
    assert p.tire_wear_pct == 30.0
    assert p.brake_wear_pct == 20.0
    assert p.engine_wear_pct == 10.0
    assert p.truck_damage_pct == 15.0
    assert p.truck_fuel_gal == 60.0

    # The parked truck inherits the wear and damage (no free pristine spare)
    # but gets a full tank rather than the active truck's 60 gallons.
    parked = p.truck_conditions["heavy_hauler"]
    assert parked["tire_wear_pct"] == 30.0
    assert parked["brake_wear_pct"] == 20.0
    assert parked["engine_wear_pct"] == 10.0
    assert parked["damage_pct"] == 15.0
    assert parked["fuel_gal"] > 60.0


def test_per_truck_conditions_round_trip_and_stay_signed():
    p = _owner_operator_fleet()
    p.tire_wear_pct = 22.0
    p.truck_conditions["heavy_hauler"]["engine_wear_pct"] = 5.0

    path = p.save()
    loaded = Profile.load(path)

    assert loaded.tire_wear_pct == 22.0
    assert loaded.truck_conditions["heavy_hauler"]["fuel_gal"] == 200.0
    assert loaded.truck_conditions["heavy_hauler"]["engine_wear_pct"] == 5.0


def test_tampering_per_truck_wear_marks_the_profile_modified():
    """Scrubbing wear out of a packed save does not go unnoticed.

    Per-truck conditions are inside the signed payload, so a hand-edited
    container fails its signature. Such a save is no longer quarantined -- it
    loads and carries a sticky ``integrity_modified`` mark instead.
    """
    p = Profile(name="Cheater Fleet")
    p.tire_wear_pct = 50.0
    path = p.save()

    data = _read_save(path)
    data["truck_conditions"]["rig"]["tire_wear_pct"] = 0.0  # scrub the wear
    _write_packed(path, data)

    loaded = Profile.load(path)
    assert loaded.integrity_modified is True
    assert loaded.integrity_notice_pending is True
    assert path.exists()  # marked, not quarantined
    assert not path.with_suffix(path.suffix + ".invalid").exists()

    # The mark is signed into the rewritten save and survives a clean reload.
    assert Profile.load(path).integrity_modified is True

    # Stripping the signature instead of re-signing is caught the same way.
    stripped = _read_save(path)
    stripped["truck_conditions"]["rig"]["tire_wear_pct"] = 0.0
    stripped.pop(profmod.SIGNATURE_FIELD)
    _write_packed(path, stripped)
    assert Profile.load(path).integrity_modified is True


def test_v1_signed_legacy_save_loads_and_migrates_without_quarantine():
    """A save signed by a pre-per-truck build must validate, not quarantine.

    v1 signed the flat condition fields; the current build must recognize that
    older field set from ``_signature_version`` and re-sign on the next save.
    v1 saves were plain JSON on disk, so the fixture lives at the legacy
    ``.json`` path and load converts it into the packed container.
    """
    p = Profile(name="V1 Signed", business_status=LEASED_OWNER_OPERATOR)
    p.truck = "rig"
    p.owned_trucks = ["rig"]
    data = p.to_dict()

    # Rewrite in the old flat shape and sign it the way a v1 build would.
    data.pop("truck_conditions", None)
    data["truck_damage_pct"] = 9.0
    data["tire_wear_pct"] = 18.0
    data["brake_wear_pct"] = 7.0
    data["engine_wear_pct"] = 3.0
    data["truck_fuel_gal"] = 70.0
    data[profmod.SIGNATURE_VERSION_FIELD] = 1
    data[profmod.SIGNATURE_FIELD] = profmod._signature_for(data, 1)
    legacy = p.path.with_suffix(profmod.LEGACY_SAVE_SUFFIX)
    legacy.write_text(json.dumps(data))

    loaded = Profile.load(legacy)  # must not raise ProfileIntegrityError

    assert loaded.tire_wear_pct == 18.0
    assert loaded.brake_wear_pct == 7.0
    assert loaded.engine_wear_pct == 3.0
    assert loaded.truck_damage_pct == 9.0
    assert loaded.truck_fuel_gal == 70.0
    # A validly signed legacy save is neither quarantined nor flagged.
    assert loaded.integrity_modified is False
    assert not legacy.with_suffix(".json.invalid").exists()

    # The load upgraded both the on-disk shape and the signature version.
    resaved = _read_save(p.path)
    assert resaved[profmod.SIGNATURE_VERSION_FIELD] == profmod.SIGNATURE_VERSION
    assert isinstance(resaved.get("truck_conditions"), dict)
    reloaded = Profile.load(p.path)
    assert reloaded.tire_wear_pct == 18.0  # still valid under v2
    assert reloaded.integrity_modified is False
