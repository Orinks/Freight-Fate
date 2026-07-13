"""Truck physics tests."""

import pytest

from freight_fate.sim import TruckState
from freight_fate.sim.transmission import REVERSE


def drive(truck: TruckState, seconds: float, dt: float = 1 / 60) -> None:
    steps = int(seconds / dt)
    for _ in range(steps):
        truck.auto_shift()
        truck.update(dt)


def time_to_speed(
    truck: TruckState, target_mph: float, limit_s: float = 240.0, dt: float = 1 / 60
) -> float | None:
    for step in range(int(limit_s / dt)):
        truck.auto_shift()
        truck.update(dt)
        if truck.speed_mph >= target_mph:
            return (step + 1) * dt
    return None


def acceleration_marks(
    truck: TruckState, targets: tuple[float, ...], limit_s: float = 240.0, dt: float = 1 / 60
) -> dict[float, float | None]:
    marks = {target: None for target in targets}
    for step in range(int(limit_s / dt)):
        truck.auto_shift()
        truck.update(dt)
        elapsed = (step + 1) * dt
        for target in targets:
            if marks[target] is None and truck.speed_mph >= target:
                marks[target] = elapsed
        if all(value is not None for value in marks.values()):
            break
    return marks


def make_auto_truck() -> TruckState:
    t = TruckState()
    t.transmission.automatic = True
    t.start_engine()
    return t


def test_gross_mass_includes_cargo_payload():
    from freight_fate.sim.vehicle import KG_PER_TON, REFERENCE_CARGO_KG

    t = TruckState()
    # Default cargo equals the reference payload, so gross stays the tuned 36 t.
    assert t.cargo_kg == REFERENCE_CARGO_KG
    assert t.gross_mass_kg == pytest.approx(t.specs.mass_kg)
    tare = t.tare_kg
    assert tare == pytest.approx(t.specs.mass_kg - REFERENCE_CARGO_KG)
    # An empty deadhead is just the tractor and empty trailer.
    t.cargo_kg = 0.0
    assert t.gross_mass_kg == pytest.approx(tare)
    # A heavier load weighs proportionally more.
    t.cargo_kg = 25 * KG_PER_TON
    assert t.gross_mass_kg == pytest.approx(tare + 25 * KG_PER_TON)


def test_heavier_load_accelerates_slower():
    from freight_fate.sim.vehicle import KG_PER_TON

    light = make_auto_truck()
    light.cargo_kg = 0.0  # empty deadhead
    heavy = make_auto_truck()
    heavy.cargo_kg = 25 * KG_PER_TON  # a 25-ton load
    light.throttle = heavy.throttle = 1.0
    light_t = time_to_speed(light, 50.0)
    heavy_t = time_to_speed(heavy, 50.0)
    assert light_t is not None and heavy_t is not None
    assert heavy_t > light_t


def test_loaded_launch_uses_lower_low_speed_traction():
    from freight_fate.sim.vehicle import (
        LAUNCH_TRACTION_ROLLING_G,
        LAUNCH_TRACTION_START_G,
        G,
    )

    t = make_auto_truck()
    t.transmission.gear = 1
    t.rpm = t.specs.peak_torque_rpm
    t.throttle = 1.0

    start_force = abs(t.drive_force())
    t.velocity_mps = 25.0 / 2.23694
    rolling_force = abs(t.drive_force())

    assert start_force / t.gross_mass_kg == pytest.approx(G * LAUNCH_TRACTION_START_G)
    assert rolling_force / t.gross_mass_kg == pytest.approx(G * LAUNCH_TRACTION_ROLLING_G)
    assert start_force < rolling_force


def test_automatic_does_not_rush_through_low_gears_on_launch():
    t = make_auto_truck()
    t.throttle = 1.0

    drive(t, 5.0)

    assert 5.0 <= t.speed_mph <= 13.0
    assert t.transmission.gear <= 4


def test_heavier_load_raises_grade_resistance():
    from freight_fate.sim.vehicle import KG_PER_TON

    light = make_auto_truck()
    heavy = make_auto_truck()
    light.cargo_kg = 0.0
    heavy.cargo_kg = 25 * KG_PER_TON
    # Same speed on the same climb: the loaded rig fights more rolling and
    # grade resistance, which is what makes it lug uphill.
    for t in (light, heavy):
        t.velocity_mps = 25.0
        t.grade = 0.04
    assert heavy.resistance_force() > light.resistance_force()


def test_heavier_load_burns_more_fuel_reaching_speed():
    from freight_fate.sim.vehicle import KG_PER_TON

    light = make_auto_truck()
    heavy = make_auto_truck()
    light.cargo_kg = 0.0
    heavy.cargo_kg = 25 * KG_PER_TON
    light.throttle = heavy.throttle = 1.0
    light_start, heavy_start = light.fuel_gal, heavy.fuel_gal
    time_to_speed(light, 50.0)
    time_to_speed(heavy, 50.0)
    assert (heavy_start - heavy.fuel_gal) > (light_start - light.fuel_gal)


def test_load_over_rated_gross_brakes_more_gently():
    from freight_fate.sim.vehicle import KG_PER_TON, REFERENCE_CARGO_KG

    truck = make_auto_truck()
    truck.velocity_mps = 25.0
    truck.brake = 1.0
    truck.grip = 1.0

    def decel(cargo_kg: float) -> float:
        truck.cargo_kg = cargo_kg
        return abs(truck.brake_force()) / truck.gross_mass_kg

    rated = decel(REFERENCE_CARGO_KG)  # gross == rated gross
    light = decel(4 * KG_PER_TON)  # well under rated
    heavy = decel(REFERENCE_CARGO_KG + 6 * KG_PER_TON)  # over rated gross

    # At or below the rated gross, braking is friction-limited and the
    # deceleration does not depend on mass.
    assert light == pytest.approx(rated)
    # Over the rated gross the foundation brakes cannot keep up, so the rig
    # decelerates more gently -- a longer stop.
    assert heavy < rated


def test_heavier_load_heats_brakes_faster():
    from freight_fate.sim.vehicle import KG_PER_TON

    light = make_auto_truck()
    heavy = make_auto_truck()
    light.cargo_kg = 0.0
    heavy.cargo_kg = 25 * KG_PER_TON
    light.throttle = heavy.throttle = 0.0
    light.brake = heavy.brake = 1.0
    for _ in range(60):  # one second of hard braking from 25 m/s
        light.velocity_mps = max(light.velocity_mps, 25.0)
        heavy.velocity_mps = max(heavy.velocity_mps, 25.0)
        light.update(1 / 60)
        heavy.update(1 / 60)
    assert heavy.brake_temp_c > light.brake_temp_c


def test_engine_start_requires_fuel():
    t = TruckState()
    t.fuel_gal = 0.0
    assert not t.start_engine()
    t.fuel_gal = 10.0
    assert t.start_engine()
    assert not t.start_engine()  # already running


def test_full_throttle_reaches_highway_speed():
    t = make_auto_truck()
    t.throttle = 1.0
    drive(t, 120)
    assert 60 <= t.speed_mph <= 76
    assert t.transmission.gear == 10


def test_loaded_rig_accelerates_to_highway_speed_believably():
    t = make_auto_truck()
    t.throttle = 1.0

    marks = acceleration_marks(t, (60.0, 65.0, 70.0))

    assert 50.0 <= marks[60.0] <= 75.0
    assert marks[65.0] <= 90.0
    assert marks[70.0] <= 125.0


def test_highway_cruise_rpm_keeps_engine_audio_believable():
    t = make_auto_truck()
    t.throttle = 1.0
    to_65 = time_to_speed(t, 65.0)

    assert to_65 is not None
    assert t.transmission.gear == 10
    assert 1400.0 <= t.rpm <= 1900.0


def test_automatic_shift_does_not_flare_engine_rpm():
    t = make_auto_truck()
    t.throttle = 1.0
    t.transmission.gear = 3
    t.velocity_mps = 20.0
    t.rpm = 1700.0

    assert t.auto_shift() == 4
    rpm_before = t.rpm
    t.update(0.5)

    assert t.transmission.shifting
    assert t.rpm <= rpm_before


def test_truck_does_not_move_in_neutral():
    t = TruckState()
    t.start_engine()
    t.throttle = 1.0
    drive(t, 5)
    assert t.velocity_mps == 0.0


def test_truck_can_back_up_slowly_in_reverse():
    t = TruckState()
    t.start_engine()
    t.transmission.automatic = False
    t.transmission.clutch = 1.0
    assert t.transmission.request_gear(REVERSE).ok
    t.transmission.update(1.0)
    t.transmission.clutch = 0.0
    t.throttle = 0.4

    drive(t, 5)

    assert t.velocity_mps < 0.0
    assert 1.0 < t.speed_mph <= 11.0
    assert t.odometer_mi > 0.0


def test_braking_stops_the_truck():
    t = make_auto_truck()
    t.throttle = 1.0
    drive(t, 60)
    assert t.speed_mph > 40
    t.throttle = 0.0
    t.brake = 1.0
    drive(t, 30)
    assert t.speed_mph < 1
    assert t.engine_on  # downshifting prevented a stall


def test_high_gear_launch_stalls():
    t = TruckState()
    t.start_engine()
    t.transmission.automatic = False
    t.transmission.clutch = 1.0
    assert t.transmission.request_gear(6).ok
    t.transmission.clutch = 0.0
    t.throttle = 0.2
    drive(t, 3)
    assert t.stalled
    assert not t.engine_on


def test_rolling_automatic_kicks_down_instead_of_stalling():
    """Regression: a hard deceleration could leave an automatic lugging in a
    high gear in the one frame the shift delay blocked the RPM downshift, and
    the engine stalled while still rolling (above the 'stopped -> first' reset).
    It must kick down a gear and keep running instead."""
    t = make_auto_truck()
    t.transmission.gear = 5
    t.velocity_mps = 0.7  # rolling, but lugging below idle*0.5 in 5th
    t.throttle = 0.8
    t.transmission._shift_timer = 1 / 60  # shift lock expires inside this frame
    t.update(1 / 60)
    assert t.engine_on
    assert not t.stalled
    assert t.transmission.gear == 4  # dropped one gear


def test_hard_collision_stop_does_not_stall_an_automatic():
    """Regression: collisions used to strand the truck stopped in a high
    gear, where the engine stalled instantly on every restart."""
    t = make_auto_truck()
    t.throttle = 1.0
    drive(t, 90)
    assert t.transmission.gear >= 8
    for _ in range(3):
        t.apply_collision(0.9)
    assert t.velocity_mps < 0.5  # shoved to a crawl, box still in a high gear
    t.throttle = 0.0
    drive(t, 5)
    assert t.engine_on
    assert not t.stalled
    assert t.transmission.gear == 1


def test_emergency_brake_outbrakes_service_brakes():
    a = make_auto_truck()
    b = make_auto_truck()
    a.velocity_mps = b.velocity_mps = 30.0
    a.brake = b.brake = 1.0
    b.emergency_brake = True
    for _ in range(120):
        a.update(1 / 60)
        b.update(1 / 60)
    assert b.velocity_mps < a.velocity_mps


def test_fuel_burns_under_load_and_engine_dies_empty():
    t = make_auto_truck()
    t.fuel_gal = 0.02
    t.fuel_burn_mult = 50.0
    t.throttle = 1.0
    drive(t, 30)
    assert t.fuel_gal == 0.0
    assert not t.engine_on


def test_grade_slows_the_truck():
    flat = make_auto_truck()
    flat.throttle = 1.0
    drive(flat, 90)
    hill = make_auto_truck()
    hill.grade = 0.06
    hill.throttle = 1.0
    drive(hill, 90)
    assert hill.speed_mph < flat.speed_mph - 5


def test_low_grip_limits_acceleration():
    dry = make_auto_truck()
    dry.throttle = 1.0
    drive(dry, 10)
    ice = make_auto_truck()
    ice.grip = 0.2
    ice.throttle = 1.0
    drive(ice, 10)
    assert ice.velocity_mps < dry.velocity_mps


def test_collision_damages_and_slows():
    t = make_auto_truck()
    t.velocity_mps = 25.0
    t.apply_collision(0.6)
    assert t.velocity_mps < 25.0
    assert t.damage_pct > 0


def test_damage_reduces_power():
    t = make_auto_truck()
    t.damage_pct = 90.0
    assert t.health_factor < 0.5


def test_refuel_caps_at_tank_size():
    t = TruckState()
    t.fuel_gal = 100.0
    added = t.refuel(1000.0)
    assert added == 50.0
    assert t.fuel_gal == t.specs.fuel_tank_gal


def test_brake_heat_builds_and_cools():
    t = make_auto_truck()
    t.velocity_mps = 30.0
    t.brake = 1.0
    for _ in range(600):
        t._update_temps(1 / 60)
    hot = t.brake_temp_c
    assert hot > 40
    t.brake = 0.0
    t.velocity_mps = 20.0
    for _ in range(6000):
        t._update_temps(1 / 60)
    assert t.brake_temp_c < hot


def test_tire_wear_accrues_with_miles_and_load():
    from freight_fate.sim.vehicle import KG_PER_TON

    light = make_auto_truck()
    heavy = make_auto_truck()
    light.cargo_kg = 0.0
    heavy.cargo_kg = 25 * KG_PER_TON
    for t in (light, heavy):
        t.velocity_mps = 25.0
        t.fuel_burn_mult = 60.0  # a compressed-time cruise, like a real trip
        for _ in range(600):
            t._update_wear(1 / 60)
    assert light.tire_wear_pct > 0.0
    assert heavy.tire_wear_pct > light.tire_wear_pct


def test_parked_truck_does_not_wear_tires_or_brakes():
    t = TruckState()
    t.set_air_ready(parking_brake=True)  # spring brakes applied, speed zero
    for _ in range(600):
        t._update_wear(1 / 60)
    assert t.tire_wear_pct == 0.0
    assert t.brake_wear_pct == 0.0


def test_jake_brake_spares_the_service_brakes():
    """The same descent on the jake costs the shoes nothing; riding the
    service brakes wears them -- the whole point of the jake as a mechanic."""
    service = make_auto_truck()
    jake = make_auto_truck()
    for t in (service, jake):
        t.velocity_mps = 13.0  # ~30 mph downgrade
        t.grade = -0.06
    service.brake = 0.5
    jake.engine_brake = True
    for _ in range(1200):  # 20 seconds of descent
        service._update_wear(1 / 60)
        jake._update_wear(1 / 60)
    assert service.brake_wear_pct > 0.0
    assert jake.brake_wear_pct == 0.0


def test_hot_brakes_wear_faster():
    cool = make_auto_truck()
    glazed = make_auto_truck()
    for t in (cool, glazed):
        t.velocity_mps = 20.0
        t.brake = 1.0
    glazed.brake_temp_c = glazed.specs.brake_fade_temp_c + 50.0
    cool._update_wear(1.0)
    glazed._update_wear(1.0)
    assert glazed.brake_wear_pct > cool.brake_wear_pct


def test_worn_tires_cut_grip_and_lengthen_stops():
    fresh = make_auto_truck()
    bald = make_auto_truck()
    bald.tire_wear_pct = 100.0
    assert bald.effective_grip < fresh.effective_grip
    fresh.velocity_mps = bald.velocity_mps = 25.0
    fresh.brake = bald.brake = 1.0
    assert abs(bald.brake_force()) < abs(fresh.brake_force())


def test_worn_brakes_fade_sooner_and_pull_weaker():
    fresh = make_auto_truck()
    worn = make_auto_truck()
    worn.brake_wear_pct = 80.0
    assert worn.brake_fade_onset_c < fresh.brake_fade_onset_c
    fresh.velocity_mps = worn.velocity_mps = 25.0
    fresh.brake = worn.brake = 1.0
    # Cool brakes: worn shoes still pull weaker than fresh ones.
    assert abs(worn.brake_force()) < abs(fresh.brake_force())
    # At a temperature between the worn and fresh fade onsets, only the
    # worn shoes have started to fade.
    temp = (worn.brake_fade_onset_c + fresh.brake_fade_onset_c) / 2.0
    fresh.brake_temp_c = worn.brake_temp_c = temp
    ratio = abs(worn.brake_force()) / abs(fresh.brake_force())
    assert ratio < worn.brake_wear_factor


def test_over_rev_wears_engine_not_damage():
    t = make_auto_truck()
    t.rpm = t.specs.max_rpm * 1.1  # the road driving the engine past the governor
    t._update_wear(1.0)
    assert t.engine_wear_pct > 0.5
    assert t.damage_pct == 0.0


def test_jake_force_scales_with_gear_stage_and_rpm():
    """The jake is torque through the gearing: a lower gear multiplies it, a
    lighter stage weakens it, and low RPM starves it -- the grade discipline."""
    t = make_auto_truck()
    t.velocity_mps = 15.0
    t.throttle = 0.0
    t.rpm = 1800.0
    t.engine_brake_stage = 3
    t.transmission.gear = 8
    tall = t.jake_brake_force()
    t.transmission.gear = 7
    low = t.jake_brake_force()
    assert tall > 0.0
    assert low > tall  # lower gear, more retard at the wheels
    t.engine_brake_stage = 1
    assert t.jake_brake_force() < low / 2.0  # stage 1 is a third of stage 3
    t.engine_brake_stage = 3
    t.rpm = 900.0
    assert t.jake_brake_force() < low  # slow engine, weak jake


def test_engine_brake_bool_view_selects_full_stage():
    t = make_auto_truck()
    t.engine_brake = True
    assert t.engine_brake_stage == 3
    assert t.engine_brake
    t.engine_brake = False
    assert t.engine_brake_stage == 0


def test_governed_speed_is_not_abuse():
    """Sitting AT the governor is normal diesel running; overspeed wear only
    starts past it, when a downgrade drives the engine through the wheels."""
    t = make_auto_truck()
    t.rpm = t.specs.max_rpm
    t._update_wear(1.0)
    assert t.engine_wear_pct < 0.1


def test_lugging_wears_the_engine():
    lugger = TruckState()
    lugger.start_engine()
    lugger.transmission.automatic = False
    lugger.transmission.gear = 8
    lugger.velocity_mps = 3.0
    lugger.throttle = 1.0
    lugger.rpm = lugger.specs.idle_rpm  # far below the torque band, wide open
    clean = TruckState()
    clean.start_engine()
    clean.transmission.automatic = False
    clean.transmission.gear = 8
    clean.velocity_mps = 25.0
    clean.throttle = 1.0
    clean.rpm = clean.specs.peak_torque_rpm
    lugger._update_wear(1.0)
    clean._update_wear(1.0)
    assert lugger.engine_wear_pct > clean.engine_wear_pct + 0.01


def test_engine_wear_cuts_power():
    fresh = make_auto_truck()
    tired = make_auto_truck()
    tired.engine_wear_pct = 100.0
    for t in (fresh, tired):
        t.transmission.gear = 10
        t.velocity_mps = 25.0
        t.rpm = t.specs.peak_torque_rpm
        t.throttle = 1.0
    assert tired.drive_force() < fresh.drive_force()


def test_engine_wear_burns_more_fuel_for_the_same_power():
    """At low speed both trucks are traction-limited to the same drive force,
    so equal power output shows the worn engine's fuel penalty cleanly."""
    fresh = make_auto_truck()
    tired = make_auto_truck()
    tired.engine_wear_pct = 100.0
    for t in (fresh, tired):
        t.transmission.gear = 1
        t.velocity_mps = 5.0
        t.rpm = t.specs.peak_torque_rpm
        t.throttle = 1.0
    assert tired.drive_force() == pytest.approx(fresh.drive_force())
    fresh_start, tired_start = fresh.fuel_gal, tired.fuel_gal
    fresh._update_fuel(10.0)
    tired._update_fuel(10.0)
    assert (tired_start - tired.fuel_gal) > (fresh_start - fresh.fuel_gal)


def test_wear_clamps_at_100():
    t = make_auto_truck()
    t.tire_wear_pct = t.brake_wear_pct = t.engine_wear_pct = 99.999
    t.velocity_mps = 30.0
    t.brake = 1.0
    t.rpm = t.specs.max_rpm
    t.fuel_burn_mult = 10_000.0
    t._update_wear(60.0)
    assert t.tire_wear_pct == 100.0
    assert t.brake_wear_pct == 100.0
    assert t.engine_wear_pct == 100.0


def test_air_pressure_builds_when_engine_running_and_stops_at_cutout():
    t = TruckState()
    t.set_cold_air_start()

    assert t.air_pressure_psi == 55.0
    assert not t.air_compressor_active

    drive(t, 5)
    assert t.air_pressure_psi == 55.0

    t.start_engine()
    drive(t, 30)

    assert t.air_pressure_psi == pytest.approx(t.specs.air_governor_cut_out_psi)
    assert not t.air_compressor_active


def test_air_compressor_cuts_in_when_pressure_drops_below_cut_in():
    t = TruckState()
    t.set_air_ready(parking_brake=False)
    t.start_engine()
    t.air_pressure_psi = t.specs.air_governor_cut_in_psi - 1.0

    t.update(0.1)

    assert t.air_compressor_active
    assert t.air_pressure_psi > t.specs.air_governor_cut_in_psi - 1.0


def test_brake_applications_consume_air_and_trigger_low_air_warning():
    t = TruckState()
    t.set_air_ready(parking_brake=False)

    for _ in range(18):
        t.brake = 1.0
        t.update(0.1)
        t.brake = 0.0
        t.update(0.1)

    assert t.air_pressure_psi < t.specs.air_low_warning_psi
    assert t.air_low_warning


def test_service_brakes_drain_separate_air_reservoirs():
    t = TruckState()
    t.set_air_ready(parking_brake=False)

    t.brake = 1.0
    t.update(0.1)

    assert t.primary_air_psi < t.secondary_air_psi < t.trailer_air_psi
    assert t.air_pressure_psi == pytest.approx(t.primary_air_psi)


def test_compressor_builds_all_reservoirs_before_cutout():
    t = TruckState()
    t.primary_air_psi = 92.0
    t.secondary_air_psi = 118.0
    t.trailer_air_psi = 86.0
    t.start_engine()

    assert t.air_compressor_active
    drive(t, 20)

    assert t.primary_air_psi == pytest.approx(t.specs.air_governor_cut_out_psi)
    assert t.secondary_air_psi == pytest.approx(t.specs.air_governor_cut_out_psi)
    assert t.trailer_air_psi == pytest.approx(t.specs.air_governor_cut_out_psi)
    assert not t.air_compressor_active


def test_parking_brake_release_requires_ready_air_pressure():
    t = TruckState()
    t.set_cold_air_start()

    assert not t.release_parking_brake()
    assert t.parking_brake

    t.air_pressure_psi = t.specs.air_parking_release_psi
    assert t.release_parking_brake()
    assert not t.parking_brake


def test_parking_brake_holds_truck_until_released():
    t = make_auto_truck()
    t.set_air_ready(parking_brake=True)
    t.throttle = 1.0

    drive(t, 5)

    assert t.speed_mph == 0.0

    assert t.release_parking_brake()
    drive(t, 5)

    assert t.speed_mph > 1.0


def test_air_brake_snapshot_preserves_richer_reservoir_state():
    t = TruckState()
    t.primary_air_psi = 91.2
    t.secondary_air_psi = 103.4
    t.trailer_air_psi = 97.6
    t.parking_brake = False
    t.air_compressor_active = True

    restored = TruckState()
    restored.restore_air_brake_snapshot(t.air_brake_snapshot(), default_ready=False)

    assert restored.primary_air_psi == pytest.approx(91.2)
    assert restored.secondary_air_psi == pytest.approx(103.4)
    assert restored.trailer_air_psi == pytest.approx(97.6)
    assert not restored.parking_brake


def test_old_air_brake_snapshot_restores_all_reservoirs_from_pressure():
    t = TruckState()

    t.restore_air_brake_snapshot(
        {"schema": 1, "pressure_psi": 88.0, "parking_brake": False},
        default_ready=False,
    )

    assert t.primary_air_psi == pytest.approx(88.0)
    assert t.secondary_air_psi == pytest.approx(88.0)
    assert t.trailer_air_psi == pytest.approx(88.0)
    assert t.air_pressure_psi == pytest.approx(88.0)
    assert not t.parking_brake
