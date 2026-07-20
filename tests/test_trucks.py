"""Truck catalog, garage upgrades, and their effects on the physics model."""

from freight_fate.models.business import LEASED_OWNER_OPERATOR
from freight_fate.models.profile import Profile
from freight_fate.models.trucks import (
    TRUCK_CATALOG,
    UPGRADE_CATALOG,
    build_truck_specs,
)
from freight_fate.sim.vehicle import TruckSpecs, TruckState


def drive(truck: TruckState, seconds: float, dt: float = 1 / 60) -> None:
    for _ in range(int(seconds / dt)):
        truck.auto_shift()
        truck.update(dt)


def make_auto_truck(specs: TruckSpecs) -> TruckState:
    t = TruckState(specs=specs)
    t.transmission.automatic = True
    t.start_engine()
    return t


# -- spec building ---------------------------------------------------------------


def test_no_upgrades_returns_base_specs():
    assert build_truck_specs("rig", {}) == TruckSpecs()


def test_unknown_truck_falls_back_to_rig():
    assert build_truck_specs("hover_truck", {}) == TruckSpecs()


def test_engine_tune_adds_ten_percent_torque_per_tier():
    base = TruckSpecs()
    t1 = build_truck_specs("rig", {"engine_tune": 1})
    t2 = build_truck_specs("rig", {"engine_tune": 2})
    assert abs(t1.max_torque_nm - base.max_torque_nm * 1.1) < 1e-6
    assert abs(t2.max_torque_nm - base.max_torque_nm * 1.2) < 1e-6


def test_aero_kit_cuts_drag_twelve_percent():
    base = TruckSpecs()
    s = build_truck_specs("rig", {"aero_kit": 1})
    assert abs(s.drag_coefficient - base.drag_coefficient * 0.88) < 1e-9


def test_long_range_tank_adds_fifty_gallons():
    s = build_truck_specs("rig", {"long_range_tank": 1})
    assert s.fuel_tank_gal == TruckSpecs().fuel_tank_gal + 50.0


def test_reinforced_brakes_raise_fade_threshold():
    s = build_truck_specs("rig", {"reinforced_brakes": 1})
    assert s.brake_fade_temp_c > TruckSpecs().brake_fade_temp_c


def test_upgrades_stack():
    s = build_truck_specs(
        "rig", {"engine_tune": 2, "aero_kit": 1, "long_range_tank": 1, "reinforced_brakes": 1}
    )
    base = TruckSpecs()
    assert s.max_torque_nm > base.max_torque_nm
    assert s.drag_coefficient < base.drag_coefficient
    assert s.fuel_tank_gal > base.fuel_tank_gal
    assert s.brake_fade_temp_c > base.brake_fade_temp_c


def test_heavy_hauler_tradeoffs():
    rig = TRUCK_CATALOG["rig"].specs
    hauler = TRUCK_CATALOG["heavy_hauler"].specs
    assert hauler.max_torque_nm > rig.max_torque_nm
    assert hauler.fuel_tank_gal > rig.fuel_tank_gal
    assert hauler.drag_coefficient > rig.drag_coefficient
    assert hauler.fuel_burn_factor > rig.fuel_burn_factor


def test_truck_descriptions_explain_tradeoffs():
    rig = TRUCK_CATALOG["rig"].description
    hauler = TRUCK_CATALOG["heavy_hauler"].description
    assert "fuel economy" in rig
    assert "heavy loads" in hauler
    assert "thirstier engine" in hauler


def test_heavy_hauler_upgrades_apply_on_top():
    s = build_truck_specs("heavy_hauler", {"long_range_tank": 1})
    assert s.fuel_tank_gal == TRUCK_CATALOG["heavy_hauler"].specs.fuel_tank_gal + 50.0


def test_garage_says_upgrades_are_fleet_wide():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import TruckShopState, UpgradeShopState

    app = App()
    try:
        from freight_fate.models.business import LEASED_OWNER_OPERATOR

        app.ctx.profile = Profile(name="Fleet Copy")
        app.ctx.profile.business_status = LEASED_OWNER_OPERATOR
        app.ctx.profile.owned_trucks = ["rig"]
        upgrades = UpgradeShopState(app.ctx)
        trucks = TruckShopState(app.ctx)

        assert "apply to every tractor" in upgrades.intro_help
        assert "fleet upgrades apply" in trucks.intro_help.lower()
        trucks.enter()
        assert "thousand newton meters torque" in trucks.current_text()
        assert "gallon tank" in trucks.current_text()
    finally:
        app.shutdown()


# -- physics effects ---------------------------------------------------------------


def test_engine_tune_accelerates_faster():
    stock = make_auto_truck(build_truck_specs("rig", {}))
    tuned = make_auto_truck(build_truck_specs("rig", {"engine_tune": 2}))
    for t in (stock, tuned):
        t.throttle = 1.0
        drive(t, 45)
    assert tuned.velocity_mps > stock.velocity_mps


def test_aero_kit_raises_cruise_speed():
    stock = make_auto_truck(build_truck_specs("rig", {}))
    sleek = make_auto_truck(build_truck_specs("rig", {"aero_kit": 1}))
    for t in (stock, sleek):
        t.throttle = 1.0
        drive(t, 120)
    assert sleek.velocity_mps > stock.velocity_mps


def test_reinforced_brakes_resist_fade_when_hot():
    stock = TruckState()
    upgraded = TruckState(specs=build_truck_specs("rig", {"reinforced_brakes": 1}))
    for t in (stock, upgraded):
        t.velocity_mps = 25.0
        t.brake = 1.0
        t.brake_temp_c = 480.0  # past stock fade onset, below upgraded onset
    assert upgraded.brake_force() > stock.brake_force()


def test_heavy_hauler_burns_more_fuel():
    rig = make_auto_truck(build_truck_specs("rig", {}))
    hauler = make_auto_truck(build_truck_specs("heavy_hauler", {}))
    for t in (rig, hauler):
        t.fuel_gal = 50.0
        t.velocity_mps = 25.0
        t.throttle = 0.0  # idle burn isolates the model's thirst factor
        t._update_fuel(60.0)
    assert hauler.fuel_gal < rig.fuel_gal


# -- profile persistence ------------------------------------------------------------


def test_profile_persists_truck_and_upgrades():
    p = Profile(name="Garage Test")
    p.business_status = LEASED_OWNER_OPERATOR
    p.truck = "heavy_hauler"
    p.owned_trucks = ["rig", "heavy_hauler"]
    p.upgrades = {"engine_tune": 2, "aero_kit": 1}
    path = p.save()
    loaded = Profile.load(path)
    assert loaded.truck == "heavy_hauler"
    assert loaded.owned_trucks == ["rig", "heavy_hauler"]
    assert loaded.upgrades == {"engine_tune": 2, "aero_kit": 1}
    specs = loaded.truck_specs()
    hauler = TRUCK_CATALOG["heavy_hauler"].specs
    assert abs(specs.max_torque_nm - hauler.max_torque_nm * 1.2) < 1e-6


def test_old_save_without_truck_fields_loads_with_defaults():
    import json

    from freight_fate.models.profile import LEGACY_SAVE_SUFFIX, _decode_save_bytes

    p = Profile(name="Legacy")
    path = p.save()
    data = _decode_save_bytes(path.read_bytes())[0]
    path.unlink()
    for legacy_missing in (
        "truck",
        "owned_trucks",
        "upgrades",
        "market",
        "trailer_programs",
        "owned_trailers",
        "tire_wear_pct",
        "brake_wear_pct",
        "engine_wear_pct",
        "road_grime_pct",
        "active_buffs",
    ):
        data.pop(legacy_missing, None)
    data.pop("_signature", None)
    data.pop("_signature_version", None)
    # An old install left this save as plain unsigned JSON.
    legacy_path = path.with_suffix(LEGACY_SAVE_SUFFIX)
    legacy_path.write_text(json.dumps(data))
    loaded = Profile.load(legacy_path)
    assert loaded.truck == "rig"
    assert loaded.owned_trucks == []
    assert loaded.visible_owned_trucks() == ()
    assert loaded.upgrades == {}
    assert loaded.active_trailer_programs() == ()
    assert loaded.visible_owned_trailers() == ()
    assert loaded.tire_wear_pct == 0.0
    assert loaded.brake_wear_pct == 0.0
    assert loaded.engine_wear_pct == 0.0
    assert loaded.road_grime_pct == 0.0
    assert loaded.active_buffs == []
    # Per-truck condition is reached through the flat names on this line; they
    # route to the active truck's record rather than a typed accessor.
    assert loaded.truck_damage_pct == 0.0
    assert loaded.truck_conditions.get("rig", {}).get("damage_pct", 0.0) == 0.0
    assert loaded.market.multipliers  # fresh market seeded on load


def test_truck_condition_round_trips_through_profile():
    from freight_fate.sim.vehicle import TruckState

    p = Profile(name="Wear Sync")
    p.truck_fuel_gal = 120.0
    p.truck_damage_pct = 8.0
    p.tire_wear_pct = 12.0
    p.brake_wear_pct = 34.0
    p.engine_wear_pct = 5.5
    truck = TruckState()
    p.load_truck_condition(truck)
    assert truck.fuel_gal == 120.0
    assert truck.damage_pct == 8.0
    assert truck.tire_wear_pct == 12.0
    assert truck.brake_wear_pct == 34.0
    assert truck.engine_wear_pct == 5.5

    truck.tire_wear_pct += 1.5
    truck.brake_wear_pct += 2.0
    truck.engine_wear_pct += 0.25
    truck.fuel_gal -= 30.0
    p.store_truck_condition(truck)
    assert p.truck_fuel_gal == 90.0
    assert p.tire_wear_pct == 13.5
    assert p.brake_wear_pct == 36.0
    assert p.engine_wear_pct == 5.75


def test_company_driver_profile_uses_assigned_standard_tractor():
    p = Profile(name="Assigned Rig")
    p.truck = "heavy_hauler"
    p.owned_trucks = ["rig", "heavy_hauler"]
    p.upgrades = {"engine_tune": 2, "long_range_tank": 1}

    specs = p.truck_specs()

    assert p.visible_owned_trucks() == ()
    assert p.active_truck_key() == "rig"
    assert specs == TruckSpecs()


def test_upgrade_catalog_prices_and_tiers():
    assert UPGRADE_CATALOG["engine_tune"].max_tier == 2
    for upgrade in UPGRADE_CATALOG.values():
        assert upgrade.max_tier >= 1
        assert all(price > 0 for price in upgrade.prices)
        assert upgrade.description
