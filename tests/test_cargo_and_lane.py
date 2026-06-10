"""Cargo weight physics and audio lane keeping (1.3.0)."""

import pygame
import pytest

from freight_fate.sim import LaneKeeping, TruckState
from freight_fate.sim.lane import MAX_OFFSET, OFF_ROAD
from freight_fate.sim.vehicle import TON_KG

# -- cargo weight in the physics ----------------------------------------------


def drive(truck: TruckState, seconds: float, dt: float = 1 / 60) -> None:
    for _ in range(int(seconds / dt)):
        truck.auto_shift()
        truck.update(dt)


def loaded_truck(tons: float) -> TruckState:
    t = TruckState()
    t.transmission.automatic = True
    t.set_cargo_tons(tons)
    t.start_engine()
    return t


def test_cargo_mass_changes_gross_weight():
    t = TruckState()
    t.set_cargo_tons(25.0)
    assert t.cargo_mass_kg == pytest.approx(25 * TON_KG)
    assert t.total_mass_kg == pytest.approx(t.specs.tractor_mass_kg + 25 * TON_KG)
    assert abs(t.cargo_tons - 25.0) < 1e-9


def test_heavier_load_accelerates_slower():
    light = loaded_truck(8)
    light.throttle = 1.0
    drive(light, 25)
    heavy = loaded_truck(25)
    heavy.throttle = 1.0
    drive(heavy, 25)
    assert heavy.velocity_mps < light.velocity_mps * 0.85


def test_heavier_load_climbs_grades_slower():
    light = loaded_truck(8)
    light.grade = 0.05
    light.throttle = 1.0
    drive(light, 90)
    heavy = loaded_truck(25)
    heavy.grade = 0.05
    heavy.throttle = 1.0
    drive(heavy, 90)
    assert heavy.speed_mph < light.speed_mph - 5


def test_max_load_still_climbs_a_mountain_grade():
    """A 25-ton haul on a 6% grade must keep moving in low gears."""
    t = loaded_truck(25)
    t.grade = 0.06
    t.velocity_mps = 13.0  # entered the grade with some momentum
    t.throttle = 1.0
    slowest = t.speed_mph
    for _ in range(int(120 * 60)):
        t.auto_shift()
        t.update(1 / 60)
        slowest = min(slowest, t.speed_mph)
    assert t.engine_on and not t.stalled
    assert slowest > 5.0


def stopping_distance(tons: float, from_mps: float = 26.8) -> float:
    t = loaded_truck(tons)
    t.velocity_mps = from_mps
    t.throttle = 0.0
    t.brake = 1.0
    for _ in range(60 * 60):
        t.update(1 / 60)
        if t.velocity_mps < 0.1:
            break
    assert t.velocity_mps < 0.1
    return t.odometer_mi * 1609.344


def test_heavier_load_brakes_longer():
    light = stopping_distance(8)
    heavy = stopping_distance(25)
    assert heavy > light * 1.15


def cruise_gallons_per_mile(tons: float, target_mph: float = 55.0) -> float:
    t = loaded_truck(tons)
    dt = 1 / 60
    for phase_s in (90.0, 120.0):  # spin-up, then the measured window
        if phase_s == 120.0:
            fuel0, odo0 = t.fuel_gal, t.odometer_mi
        for _ in range(int(phase_s / dt)):
            err = target_mph - t.speed_mph
            t.throttle = max(0.0, min(1.0, t.throttle + 0.05 * err * dt))
            t.auto_shift()
            t.update(dt)
    miles = t.odometer_mi - odo0
    assert miles > 1.0
    return (fuel0 - t.fuel_gal) / miles


def test_heavier_load_burns_more_fuel_per_mile():
    light = cruise_gallons_per_mile(8)
    heavy = cruise_gallons_per_mile(25)
    assert heavy > light * 1.05


# -- lane keeping ----------------------------------------------------------------


def run_lane(lane: LaneKeeping, seconds: float, dt: float = 0.1,
             speed_mps: float = 29.0, **kw) -> int:
    fired = 0
    for _ in range(int(seconds / dt)):
        if lane.update(dt, speed_mps, **kw):
            fired += 1
    return fired


def test_drift_accumulates_and_correction_counters_it():
    lane = LaneKeeping(seed=7)
    run_lane(lane, 12, curve=1.0)  # hard uncorrected curve
    drifted = abs(lane.offset)
    assert drifted > 0.5
    for _ in range(100):  # a player steering against the offset
        lane.steering = max(-1.0, min(1.0, -lane.offset * 2))
        lane.update(0.1, 29.0, curve=0.0)
    assert abs(lane.offset) < 0.2


def test_heavier_load_steers_more_sluggishly():
    light = LaneKeeping(seed=5)
    heavy = LaneKeeping(seed=5)
    for lane in (light, heavy):
        lane.offset = 1.0
        lane.steering = -1.0
    run_lane(light, 2.0, mass_factor=23_000 / 36_000)
    run_lane(heavy, 2.0, mass_factor=39_000 / 36_000)
    assert light.offset < heavy.offset  # the light truck recentered further


def test_wind_scales_drift():
    """Storm-force wind makes the truck move around its lane far more."""
    calm = LaneKeeping(seed=3)
    windy = LaneKeeping(seed=3)
    path_calm = path_windy = 0.0
    prev_c = prev_w = 0.0
    dt = 0.1
    for _ in range(int(120 / dt)):
        calm.update(dt, 29.0, wind=0.0)
        windy.update(dt, 29.0, wind=0.9)
        path_calm += abs(calm.offset - prev_c)
        path_windy += abs(windy.offset - prev_w)
        prev_c, prev_w = calm.offset, windy.offset
    assert path_windy > path_calm * 1.5


def test_no_drift_while_parked():
    lane = LaneKeeping(seed=2)
    run_lane(lane, 60, speed_mps=0.0, curve=1.0, wind=1.0)
    assert lane.offset == 0.0


def test_off_road_fires_after_sustained_max_offset():
    lane = LaneKeeping(seed=1)
    fired = run_lane(lane, 40, curve=1.0)  # nobody at the wheel
    assert abs(lane.offset) >= OFF_ROAD
    assert abs(lane.offset) <= MAX_OFFSET
    assert 2 <= fired <= 13  # grace period first, then repeats


def test_assist_off_keeps_the_truck_centered():
    lane = LaneKeeping(seed=4)
    lane.offset = 0.9
    fired = run_lane(lane, 30, curve=1.0, wind=1.0, assist="off")
    assert fired == 0
    assert lane.offset == 0.0


def test_light_assist_drifts_less_than_realistic():
    light = LaneKeeping(seed=11)
    real = LaneKeeping(seed=11)
    light_sum = real_sum = 0.0
    dt = 0.1
    for _ in range(int(60 / dt)):
        light.update(dt, 29.0, curve=0.4, assist="light")
        real.update(dt, 29.0, curve=0.4, assist="realistic")
        light_sum += abs(light.offset)
        real_sum += abs(real.offset)
    assert light_sum < real_sum


def test_lane_describe_positions():
    lane = LaneKeeping()
    assert "Centered" in lane.describe()
    lane.offset = 0.5
    assert lane.describe() == "Drifting right."
    lane.offset = -0.9
    assert "left edge" in lane.describe()
    lane.offset = -1.4
    assert "Off the road" in lane.describe()
    assert lane.rumble_level() == 1.0
    assert lane.pan() < 0


def test_curve_follows_terrain():
    from freight_fate.data.world import Leg, Route
    from freight_fate.sim.trip import Trip
    from freight_fate.sim.weather import WeatherSystem

    def max_curve(terrain: str) -> float:
        leg = Leg("A", "B", 200.0, "I-00", terrain, ())
        trip = Trip(Route(["A", "B"], [leg]), TruckState(),
                    WeatherSystem(seed=0), seed=0)
        return max(abs(trip.curve_at(mi / 10)) for mi in range(2000))

    flat, mountain = max_curve("flat"), max_curve("mountain")
    assert flat <= 0.12
    assert mountain > 0.6
    assert flat < mountain


# -- settings ---------------------------------------------------------------------


def test_steering_assist_setting_round_trips():
    from freight_fate.settings import Settings

    s = Settings()
    assert s.steering_assist == "off"  # default preserves existing behavior
    s.steering_assist = "realistic"
    s.save()
    assert Settings.load().steering_assist == "realistic"
    s.steering_assist = "bogus value"
    s.save()
    assert Settings.load().steering_assist == "off"  # validated on load


# -- snapshot resume ----------------------------------------------------------------


@pytest.mark.smoke
def test_snapshot_resume_preserves_lane_and_load():
    from test_trip_resume import drive_some, key_event, quit_to_menu, start_drive

    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        app.ctx.settings.steering_assist = "realistic"
        driving = start_drive(app)
        weight = driving.job.weight_tons
        assert driving.truck.cargo_mass_kg == pytest.approx(weight * TON_KG)
        drive_some(driving)
        driving.lane.offset = -0.62
        quit_to_menu(app)

        while app.state.items[app.state.index].text != "Continue":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        resumed = app.state
        assert isinstance(resumed, DrivingState)
        assert resumed.lane.offset == pytest.approx(-0.62)
        assert resumed.truck.cargo_mass_kg == pytest.approx(weight * TON_KG)
    finally:
        app.shutdown()
