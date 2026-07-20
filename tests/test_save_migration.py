"""Old flat-field saves migrate to per-truck condition records exactly once."""

import json

import pygame

from freight_fate.models.business import LEASED_OWNER_OPERATOR
from freight_fate.models.profile import (
    LEGACY_SAVE_SUFFIX,
    SAVE_VERSION,
    Profile,
    _decode_save_bytes,
    _migrate_flat_conditions,
    _signature_for,
)
from freight_fate.models.save_migration import migrate_save_data
from freight_fate.models.trucks import TRUCK_CATALOG
from freight_fate.profile_invariants import check_profile_invariants
from freight_fate.sim.vehicle import TruckSpecs


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def select_shop_item(shop, prefix):
    """Move the shop cursor onto the item starting with ``prefix``.

    Bounded on purpose: if a label ever changes, this fails loudly instead of
    spinning down a menu that will never show the item.
    """
    for _ in range(len(shop.items)):
        if shop.items[shop.index].text.startswith(prefix):
            return
        shop.handle_event(key_event(pygame.K_DOWN))
    raise AssertionError(
        f"No truck shop item starting with {prefix!r}; saw {[item.text for item in shop.items]}"
    )


def write_v4_save(
    name="Legacy",
    truck="heavy_hauler",
    owned=("rig", "heavy_hauler"),
    fuel=120.0,
    damage=40.0,
    tires=10.0,
    grime=60.0,
    signed=True,
):
    """Write a save shaped exactly like the pre-per-truck (version 4) format.

    Version-4 saves predate the packed container, so this writes plain JSON
    at the legacy ``.json`` path, exactly as a real old install left it.
    """
    p = Profile(name=name)
    packed_path = p.save()
    data = _decode_save_bytes(packed_path.read_bytes())[0]
    packed_path.unlink()
    data.pop("truck_conditions", None)
    data.pop("migration_notice_pending", None)
    data.pop("integrity_modified", None)
    data.pop("integrity_notice_pending", None)
    data.pop("_signature", None)
    data.pop("_signature_version", None)
    data["version"] = 4
    # The fan-out only treats ``truck`` as the driven tractor for an
    # owner-operator; a company driver runs whatever the carrier assigned.
    data["business_status"] = LEASED_OWNER_OPERATOR
    data["truck"] = truck
    data["owned_trucks"] = list(owned)
    data["truck_fuel_gal"] = fuel
    data["truck_damage_pct"] = damage
    data["tire_wear_pct"] = tires
    data["road_grime_pct"] = grime
    if signed:
        data["_signature_version"] = 1
        data["_signature"] = _signature_for(data)
    path = packed_path.with_suffix(LEGACY_SAVE_SUFFIX)
    path.write_text(json.dumps(data))
    return path


def test_v4_save_converts_to_per_truck_records():
    path = write_v4_save()
    loaded = Profile.load(path)

    # Condition records are plain dicts on this line.
    hauler = loaded.truck_conditions["heavy_hauler"]
    assert hauler["fuel_gal"] == 120.0
    assert hauler["damage_pct"] == 40.0
    assert hauler["tire_wear_pct"] == 10.0

    rig = loaded.truck_conditions["rig"]
    assert rig["fuel_gal"] == TruckSpecs().fuel_tank_gal
    # Parked trucks inherit the one saved wear and damage set rather than
    # starting pristine -- a swap must not launder a beaten-up career.
    assert rig["damage_pct"] == 40.0
    assert rig["tire_wear_pct"] == 10.0

    # Road grime is a profile field here, not part of a truck's record.
    assert loaded.road_grime_pct == 60.0

    assert loaded.migration_notice_pending is True
    assert not check_profile_invariants(loaded)


def test_v4_save_is_rewritten_to_disk_on_load():
    path = write_v4_save()
    loaded = Profile.load(path)
    # The conversion re-homes the career in the packed container; the old
    # plain-JSON file stays behind only as a .json.bak rollback copy.
    assert not path.exists()
    path = loaded.path
    on_disk = _decode_save_bytes(path.read_bytes())[0]
    assert on_disk["version"] == SAVE_VERSION
    assert "truck_conditions" in on_disk
    for legacy in ("truck_fuel_gal", "truck_damage_pct", "tire_wear_pct", "road_grime_pct"):
        assert legacy not in on_disk
    # Grime rides on the truck that got dirty, like every other kind of wear,
    # so the migrated figure lands in the records rather than on the profile.
    assert on_disk["truck_conditions"]["heavy_hauler"]["grime_pct"] == 60.0
    # The rewritten save loads cleanly, is validly signed, and migrates no more.
    again = Profile.load(path)
    assert again.needs_migration_resave is False
    assert again.truck_conditions["heavy_hauler"]["fuel_gal"] == 120.0


def test_signed_v4_save_is_not_quarantined():
    path = write_v4_save(signed=True)
    loaded = Profile.load(path)  # a signature mismatch would raise and quarantine
    assert loaded.name == "Legacy"
    assert not path.with_suffix(path.suffix + ".invalid").exists()


def test_migration_clamps_impossible_legacy_values():
    path = write_v4_save(truck="rig", owned=("rig",), fuel=9_000.0, damage=250.0, tires=-5.0)
    loaded = Profile.load(path)
    rig = loaded.truck_conditions["rig"]
    assert rig["fuel_gal"] == TruckSpecs().fuel_tank_gal
    assert rig["damage_pct"] == 100.0
    assert rig["tire_wear_pct"] == 0.0


def test_migration_respects_long_range_tank_upgrade():
    data = {
        "version": 4,
        "truck": "heavy_hauler",
        "business_status": LEASED_OWNER_OPERATOR,
        "owned_trucks": ["rig", "heavy_hauler"],
        "upgrades": {"long_range_tank": 1},
        "truck_fuel_gal": 240.0,
    }
    migrated, changed = migrate_save_data(data)
    assert changed
    # migrate_save_data only flags the conversion on this line; the records
    # themselves are built by the profile's fan-out, which is the authority.
    conditions = _migrate_flat_conditions(migrated)
    hauler_tank = TRUCK_CATALOG["heavy_hauler"].specs.fuel_tank_gal + 50.0
    assert conditions["heavy_hauler"]["fuel_gal"] == 240.0
    assert conditions["rig"]["fuel_gal"] == TruckSpecs().fuel_tank_gal + 50.0
    assert hauler_tank >= 240.0


def test_current_saves_pass_through_unchanged():
    p = Profile(name="Modern")
    path = p.save()
    data = _decode_save_bytes(path.read_bytes())[0]
    migrated, changed = migrate_save_data(data)
    assert changed is False
    assert migrated is data


def test_migration_notice_shows_once_then_enters_world(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState
    from freight_fate.states.main_menu import enter_world
    from freight_fate.states.save_notice import SaveMigrationNoticeState

    path = write_v4_save(name="Notice")
    app = App()
    try:
        spoken = []
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile.load(path)

        enter_world(app.ctx)
        assert isinstance(app.state, SaveMigrationNoticeState)
        assert any("older versions" in text for text in spoken)
        assert app.state.items[0].text == "OK"

        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CityMenuState)
        assert app.ctx.profile.migration_notice_pending is False

        # The dismissal is saved: a fresh load goes straight into the world.
        # (The conversion moved the career into its packed .ffsave file.)
        app.ctx.profile = Profile.load(app.ctx.profile.path)
        assert app.ctx.profile.migration_notice_pending is False
        enter_world(app.ctx)
        assert isinstance(app.state, CityMenuState)
    finally:
        app.shutdown()


def test_migration_notice_escape_also_acknowledges(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState
    from freight_fate.states.main_menu import enter_world
    from freight_fate.states.save_notice import SaveMigrationNoticeState

    path = write_v4_save(name="Escape Notice")
    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: None)
        app.ctx.profile = Profile.load(path)
        enter_world(app.ctx)
        assert isinstance(app.state, SaveMigrationNoticeState)
        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, CityMenuState)
        assert app.ctx.profile.migration_notice_pending is False
    finally:
        app.shutdown()


def test_modified_notice_shows_once_then_enters_world(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import encode_save_bytes
    from freight_fate.states.city import CityMenuState
    from freight_fate.states.main_menu import enter_world
    from freight_fate.states.save_notice import SaveModifiedNoticeState

    p = Profile(name="Edited")
    path = p.save()
    data = _decode_save_bytes(path.read_bytes())[0]
    data["money"] = 999_999.0
    path.write_bytes(encode_save_bytes(data))

    app = App()
    try:
        spoken = []
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile.load(path)
        assert app.ctx.profile.integrity_modified is True

        enter_world(app.ctx)
        assert isinstance(app.state, SaveModifiedNoticeState)
        assert any("marked as modified" in text for text in spoken)

        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CityMenuState)
        assert app.ctx.profile.integrity_notice_pending is False
        # The mark itself never clears from a dismissal.
        assert app.ctx.profile.integrity_modified is True

        # The dismissal is saved: a fresh load goes straight into the world.
        app.ctx.profile = Profile.load(path)
        assert app.ctx.profile.integrity_notice_pending is False
        enter_world(app.ctx)
        assert isinstance(app.state, CityMenuState)
    finally:
        app.shutdown()


def test_bought_truck_starts_fresh_and_each_keeps_its_own_condition(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import TruckShopState

    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: None)
        app.ctx.profile = Profile(name="Fleet Condition")
        p = app.ctx.profile
        # Only an owner-operator buys or switches tractors; a company driver
        # sees a locked shop with nothing to pick.
        p.business_status = LEASED_OWNER_OPERATOR
        p.owned_trucks = ["rig"]
        p.money = 60_000.0
        p.truck_fuel_gal = 40.0
        p.truck_damage_pct = 30.0
        p.tire_wear_pct = 12.0
        p.road_grime_pct = 55.0

        shop = TruckShopState(app.ctx)
        app.push_state(shop)
        select_shop_item(shop, "Heavy hauler")
        shop.handle_event(key_event(pygame.K_RETURN))

        assert p.truck == "heavy_hauler"
        assert p.truck_fuel_gal == TRUCK_CATALOG["heavy_hauler"].specs.fuel_tank_gal
        assert p.truck_damage_pct == 0.0
        assert p.tire_wear_pct == 0.0
        # Grime belongs to the truck that earned it, so a tractor off the lot
        # is clean no matter how filthy the one it replaces was.
        assert p.road_grime_pct == 0.0

        # The rig kept its own condition and gets it back on switch.
        select_shop_item(shop, "Standard rig")
        shop.handle_event(key_event(pygame.K_RETURN))
        assert p.truck == "rig"
        assert p.truck_fuel_gal == 40.0
        assert p.truck_damage_pct == 30.0
        assert p.tire_wear_pct == 12.0
        # ...including the grime it was parked with.
        assert p.road_grime_pct == 55.0

        loaded = Profile.load(p.path)
        assert loaded.truck_conditions["rig"]["fuel_gal"] == 40.0
        assert loaded.truck_conditions["rig"]["grime_pct"] == 55.0
        assert loaded.truck_conditions["heavy_hauler"]["damage_pct"] == 0.0
        assert loaded.truck_conditions["heavy_hauler"]["grime_pct"] == 0.0
    finally:
        app.shutdown()


def test_invariants_flag_bad_per_truck_records():
    p = Profile(name="Bad Fleet")
    p.owned_trucks = ["rig", "heavy_hauler"]
    p.provision_truck_condition("heavy_hauler")
    p.provision_truck_condition("rig")
    p.truck_conditions["heavy_hauler"]["fuel_gal"] = 9_000.0
    p.truck_conditions["rig"]["damage_pct"] = -5.0
    violations = check_profile_invariants(p)
    codes = {v.code for v in violations}
    assert "fuel_range" in codes
    # Wear and damage share one code here; the detail names the bad meter.
    assert any(v.code == "condition_range" and "damage" in v.detail for v in violations)


def test_condition_round_trips_through_save_and_load():
    p = Profile(name="Round Trip")
    p.truck = "rig"
    p.truck_fuel_gal = 77.0
    p.truck_damage_pct = 3.5
    path = p.save()
    loaded = Profile.load(path)
    assert loaded.truck_fuel_gal == 77.0
    assert loaded.truck_damage_pct == 3.5
    assert loaded.migration_notice_pending is False
    assert not check_profile_invariants(loaded)


def test_unknown_truck_key_condition_is_preserved():
    p = Profile(name="Future Fleet")
    p.owned_trucks = ["rig", "hover_truck"]
    p.provision_truck_condition("hover_truck")
    p.truck_conditions["hover_truck"]["damage_pct"] = 12.0
    path = p.save()
    loaded = Profile.load(path)
    assert loaded.truck_conditions["hover_truck"]["damage_pct"] == 12.0
    assert not check_profile_invariants(loaded)
