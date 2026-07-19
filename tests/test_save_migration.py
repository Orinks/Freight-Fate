"""Old flat-field saves migrate to per-truck condition records exactly once."""

import json

import pygame

from freight_fate.models.profile import SAVE_VERSION, Profile, _signature_for
from freight_fate.models.save_migration import migrate_save_data
from freight_fate.models.trucks import TRUCK_CATALOG
from freight_fate.profile_invariants import check_profile_invariants
from freight_fate.sim.vehicle import TruckSpecs


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


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
    """Write a save shaped exactly like the pre-per-truck (version 4) format."""
    p = Profile(name=name)
    path = p.save()
    data = json.loads(path.read_text())
    data.pop("truck_conditions", None)
    data.pop("migration_notice_pending", None)
    data.pop("_signature", None)
    data.pop("_signature_version", None)
    data["version"] = 4
    data["truck"] = truck
    data["owned_trucks"] = list(owned)
    data["truck_fuel_gal"] = fuel
    data["truck_damage_pct"] = damage
    data["tire_wear_pct"] = tires
    data["road_grime_pct"] = grime
    if signed:
        data["_signature_version"] = 1
        data["_signature"] = _signature_for(data)
    path.write_text(json.dumps(data))
    return path


def test_v4_save_converts_to_per_truck_records():
    path = write_v4_save()
    loaded = Profile.load(path)

    hauler = loaded.truck_conditions["heavy_hauler"]
    assert hauler.fuel_gal == 120.0
    assert hauler.damage_pct == 40.0
    assert hauler.tire_wear_pct == 10.0
    assert hauler.grime_pct == 60.0

    rig = loaded.truck_conditions["rig"]
    assert rig.fuel_gal == TruckSpecs().fuel_tank_gal
    assert rig.damage_pct == 0.0
    assert rig.tire_wear_pct == 0.0
    assert rig.grime_pct == 0.0

    assert loaded.migration_notice_pending is True
    assert not check_profile_invariants(loaded)


def test_v4_save_is_rewritten_to_disk_on_load():
    path = write_v4_save()
    Profile.load(path)
    on_disk = json.loads(path.read_text())
    assert on_disk["version"] == SAVE_VERSION
    assert "truck_conditions" in on_disk
    for legacy in ("truck_fuel_gal", "truck_damage_pct", "tire_wear_pct", "road_grime_pct"):
        assert legacy not in on_disk
    # The rewritten save loads cleanly, is validly signed, and migrates no more.
    again = Profile.load(path)
    assert again.needs_migration_resave is False
    assert again.truck_conditions["heavy_hauler"].fuel_gal == 120.0


def test_signed_v4_save_is_not_quarantined():
    path = write_v4_save(signed=True)
    loaded = Profile.load(path)  # a signature mismatch would raise and quarantine
    assert loaded.name == "Legacy"
    assert not path.with_suffix(path.suffix + ".invalid").exists()


def test_migration_clamps_impossible_legacy_values():
    path = write_v4_save(truck="rig", owned=("rig",), fuel=9_000.0, damage=250.0, tires=-5.0)
    loaded = Profile.load(path)
    rig = loaded.truck_conditions["rig"]
    assert rig.fuel_gal == TruckSpecs().fuel_tank_gal
    assert rig.damage_pct == 100.0
    assert rig.tire_wear_pct == 0.0


def test_migration_respects_long_range_tank_upgrade():
    data = {
        "version": 4,
        "truck": "heavy_hauler",
        "owned_trucks": ["rig", "heavy_hauler"],
        "upgrades": {"long_range_tank": 1},
        "truck_fuel_gal": 240.0,
    }
    migrated, changed = migrate_save_data(data)
    assert changed
    hauler_tank = TRUCK_CATALOG["heavy_hauler"].specs.fuel_tank_gal + 50.0
    assert migrated["truck_conditions"]["heavy_hauler"]["fuel_gal"] == 240.0
    assert migrated["truck_conditions"]["rig"]["fuel_gal"] == TruckSpecs().fuel_tank_gal + 50.0
    assert hauler_tank >= 240.0


def test_current_saves_pass_through_unchanged():
    p = Profile(name="Modern")
    path = p.save()
    data = json.loads(path.read_text())
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
        app.ctx.profile = Profile.load(path)
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


def test_bought_truck_starts_fresh_and_each_keeps_its_own_condition(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import TruckShopState

    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: None)
        app.ctx.profile = Profile(name="Fleet Condition")
        p = app.ctx.profile
        p.money = 60_000.0
        p.truck_fuel_gal = 40.0
        p.truck_damage_pct = 30.0
        p.tire_wear_pct = 12.0
        p.road_grime_pct = 55.0

        shop = TruckShopState(app.ctx)
        app.push_state(shop)
        while not shop.items[shop.index].text.startswith("Heavy hauler"):
            shop.handle_event(key_event(pygame.K_DOWN))
        shop.handle_event(key_event(pygame.K_RETURN))

        assert p.truck == "heavy_hauler"
        assert p.truck_fuel_gal == TRUCK_CATALOG["heavy_hauler"].specs.fuel_tank_gal
        assert p.truck_damage_pct == 0.0
        assert p.tire_wear_pct == 0.0
        assert p.road_grime_pct == 0.0

        # The rig kept its own condition and gets it back on switch.
        while not shop.items[shop.index].text.startswith("Standard rig"):
            shop.handle_event(key_event(pygame.K_DOWN))
        shop.handle_event(key_event(pygame.K_RETURN))
        assert p.truck == "rig"
        assert p.truck_fuel_gal == 40.0
        assert p.truck_damage_pct == 30.0

        loaded = Profile.load(p.path)
        assert loaded.truck_conditions["rig"].fuel_gal == 40.0
        assert loaded.truck_conditions["heavy_hauler"].damage_pct == 0.0
    finally:
        app.shutdown()


def test_invariants_flag_bad_per_truck_records():
    p = Profile(name="Bad Fleet")
    p.owned_trucks = ["rig", "heavy_hauler"]
    p.condition_for("heavy_hauler").fuel_gal = 9_000.0
    p.condition_for("rig").damage_pct = -5.0
    codes = {v.code for v in check_profile_invariants(p)}
    assert "fuel_range" in codes
    assert "damage" in codes


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
    p.condition_for("hover_truck").damage_pct = 12.0
    path = p.save()
    loaded = Profile.load(path)
    assert loaded.truck_conditions["hover_truck"].damage_pct == 12.0
    assert not check_profile_invariants(loaded)
