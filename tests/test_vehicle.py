"""Truck physics tests."""

from freight_fate.sim import TruckState


def drive(truck: TruckState, seconds: float, dt: float = 1 / 60) -> None:
    steps = int(seconds / dt)
    for _ in range(steps):
        truck.auto_shift()
        truck.update(dt)


def time_to_speed(truck: TruckState, target_mph: float,
                  limit_s: float = 240.0, dt: float = 1 / 60) -> float | None:
    for step in range(int(limit_s / dt)):
        truck.auto_shift()
        truck.update(dt)
        if truck.speed_mph >= target_mph:
            return (step + 1) * dt
    return None


def acceleration_marks(truck: TruckState, targets: tuple[float, ...],
                       limit_s: float = 240.0,
                       dt: float = 1 / 60) -> dict[float, float | None]:
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
    assert 60 <= t.speed_mph <= 75
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


def test_truck_does_not_move_in_neutral():
    t = TruckState()
    t.start_engine()
    t.throttle = 1.0
    drive(t, 5)
    assert t.velocity_mps == 0.0


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
