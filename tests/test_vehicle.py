"""Truck physics tests."""

from freight_fate.sim import TruckState


def drive(truck: TruckState, seconds: float, dt: float = 1 / 60) -> None:
    steps = int(seconds / dt)
    for _ in range(steps):
        truck.auto_shift()
        truck.update(dt)


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
