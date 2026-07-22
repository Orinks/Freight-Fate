"""Truck physics tests."""

import pytest

from freight_fate.sim import TruckState
from freight_fate.sim.transmission import REVERSE
from freight_fate.sim.vehicle import REFERENCE_CARGO_KG


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


def test_manual_governor_holds_low_gear_without_engine_damage():
    truck = TruckState()
    truck.start_engine()
    truck.set_air_ready(parking_brake=False)
    truck.transmission.gear = 1
    truck.throttle = 1.0

    drive(truck, 20.0)
    speed_at_governor = truck.speed_mph
    damage_at_governor = truck.damage_pct
    drive(truck, 10.0)

    assert truck.rpm == pytest.approx(truck.specs.max_rpm)
    assert truck.speed_mph == pytest.approx(speed_at_governor, abs=0.5)
    assert truck.damage_pct == pytest.approx(damage_at_governor)


@pytest.mark.parametrize("grade", [0.04, 0.06, 0.08])
def test_loaded_automatic_avoids_steep_grade_shift_hunting(grade):
    from freight_fate.sim.vehicle import KG_PER_TON

    truck = make_auto_truck()
    truck.set_air_ready(parking_brake=False)
    truck.cargo_kg = 25 * KG_PER_TON
    truck.grade = grade
    truck.throttle = 1.0
    shifts = 0
    previous_gear = truck.transmission.gear
    for _ in range(90 * 60):
        truck.auto_shift()
        truck.update(1 / 60)
        if truck.transmission.gear != previous_gear:
            shifts += 1
            previous_gear = truck.transmission.gear

    assert shifts <= 12
    assert truck.speed_mph > 3.0


def test_loaded_automatic_uses_progressive_early_upshifts():
    truck = make_auto_truck()
    truck.set_air_ready(parking_brake=False)
    truck.throttle = 1.0
    shifts = []
    previous_gear = truck.transmission.gear
    for step in range(90 * 60):
        truck.auto_shift()
        truck.update(1 / 60)
        if truck.transmission.gear != previous_gear:
            shifts.append(((step + 1) / 60, truck.transmission.gear))
            previous_gear = truck.transmission.gear
        if truck.transmission.gear >= 5:
            break

    early_times = [when for when, gear in shifts if 2 <= gear <= 5]
    assert len(early_times) == 4
    assert all(b - a >= 1.5 for a, b in zip(early_times, early_times[1:], strict=False))


def test_empty_automatic_shifts_low_range_faster_than_loaded():
    def time_to_fifth(cargo_kg):
        truck = make_auto_truck()
        truck.set_air_ready(parking_brake=False)
        truck.cargo_kg = cargo_kg
        truck.throttle = 1.0
        for step in range(90 * 60):
            truck.auto_shift()
            truck.update(1 / 60)
            if truck.transmission.gear >= 5:
                return (step + 1) / 60
        return None

    loaded_time = time_to_fifth(REFERENCE_CARGO_KG)
    empty_time = time_to_fifth(0.0)
    assert loaded_time is not None and empty_time is not None
    assert empty_time < loaded_time


def test_automatic_spaces_downshifts_while_stopping():
    truck = make_auto_truck()
    truck.set_air_ready(parking_brake=False)
    truck.transmission.gear = 10
    truck.velocity_mps = 26.8
    truck.brake = 0.65
    shifts = []
    previous_gear = 10
    for step in range(30 * 60):
        truck.auto_shift()
        truck.update(1 / 60)
        if truck.transmission.gear != previous_gear:
            if truck.speed_mph >= 1.0:
                shifts.append((step + 1) / 60)
            previous_gear = truck.transmission.gear
        if truck.speed_mph < 1.0:
            break

    assert all(b - a >= 1.65 for a, b in zip(shifts, shifts[1:], strict=False))


def test_empty_automatic_selects_third_as_starting_gear():
    truck = make_auto_truck()
    truck.set_air_ready(parking_brake=False)
    truck.cargo_kg = 0.0
    truck.throttle = 1.0

    assert truck.auto_shift() == 3


def test_loaded_automatic_selects_first_as_starting_gear():
    truck = make_auto_truck()
    truck.set_air_ready(parking_brake=False)
    truck.throttle = 1.0

    assert truck.auto_shift() == 1


def test_empty_automatic_can_skip_an_unneeded_gear():
    truck = make_auto_truck()
    truck.set_air_ready(parking_brake=False)
    truck.cargo_kg = 0.0
    truck.transmission.gear = 3
    truck.velocity_mps = 8.0
    truck.throttle = 1.0

    assert truck.auto_shift() == 5


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


def test_engine_off_air_reservoirs_leak_during_parked_time():
    t = TruckState()
    t.set_air_ready(parking_brake=True)

    t.advance_parked_time(10 * 60)

    assert t.air_pressure_psi == pytest.approx(t.specs.air_cold_start_psi)
    assert t.air_low_warning
    assert not t.air_ready
    assert not t.air_compressor_active


def test_running_engine_prevents_parked_time_air_leak():
    t = TruckState()
    t.set_air_ready(parking_brake=True)
    t.start_engine()

    t.advance_parked_time(10 * 60)

    assert t.air_pressure_psi == pytest.approx(t.specs.air_governor_cut_out_psi)


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
