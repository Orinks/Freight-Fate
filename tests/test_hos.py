"""Hours of service, fatigue, day/night, and overnight parking (1.5.0)."""

import json

import pygame
import pytest

from freight_fate.sim import hos
from freight_fate.sim.hos import (
    LIMITS,
    HosClock,
    clock_text,
    is_night,
    parking_full_probability,
    parking_is_full,
    reaction_window_mult,
    time_of_day,
)


def key_event(key, unicode="", mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode, mod=mod)


# -- clock math -------------------------------------------------------------------

def test_drive_accumulates_all_three_meters():
    c = HosClock()
    c.drive(90)
    assert c.driving_min == 90
    assert c.duty_min == 90
    assert c.since_break_min == 90


def test_parked_time_counts_against_duty_window_only():
    c = HosClock()
    c.on_duty(60)
    assert c.duty_min == 60
    assert c.driving_min == 0
    assert c.since_break_min == 0
    assert c.status == "on_duty_not_driving"


def test_break_resets_break_rule_but_not_the_shift():
    c = HosClock()
    c.drive(480)
    c.take_break(30)
    assert c.since_break_min == 0
    assert c.driving_min == 480
    assert c.duty_min == 510  # the break itself burns duty window
    assert c.status == "off_duty"


def test_on_duty_not_driving_satisfies_break_rule():
    c = HosClock()
    c.drive(480)
    c.on_duty(30)
    assert c.status == "on_duty_not_driving"
    assert c.since_break_min == 0
    assert c.driving_min == 480
    assert c.duty_min == 510


def test_short_break_does_not_satisfy_the_break_rule():
    c = HosClock()
    c.drive(100)
    c.take_break(15)
    assert c.since_break_min == 100


def test_sleep_resets_the_shift():
    c = HosClock()
    c.drive(600)
    c.check_warnings("realistic")
    c.sleep()
    assert c.driving_min == 0
    assert c.duty_min == 0
    assert c.since_break_min == 0
    assert c.status == "sleeper_berth"
    assert c.warned == []


def test_remaining_is_the_nearest_limit():
    c = HosClock()
    c.drive(400)
    # break binds first: 480 - 400 = 80 vs drive 260 vs duty 440
    assert c.remaining_min("realistic") == pytest.approx(80)


def test_violation_detection():
    c = HosClock()
    c.drive(481)
    assert c.in_violation("realistic")
    c2 = HosClock()
    c2.drive(479)
    assert not c2.in_violation("realistic")


# -- warnings -------------------------------------------------------------------

def drive_collecting(c: HosClock, minutes: float, mode: str = "realistic",
                     step: float = 5.0) -> list[str]:
    msgs = []
    elapsed = 0.0
    while elapsed < minutes:
        c.drive(step)
        elapsed += step
        msgs += c.check_warnings(mode)
    return msgs


def test_warnings_fire_once_per_threshold():
    c = HosClock()
    msgs = drive_collecting(c, 485)  # past the 8-hour break rule
    assert len([m for m in msgs if "2 hours until" in m]) == 1
    assert len([m for m in msgs if "1 hour until" in m]) == 1
    assert len([m for m in msgs if "30 minutes until" in m]) == 1
    assert len([m for m in msgs if "violation" in m]) == 1
    # driving on never repeats a break warning; only the separate
    # 11-hour drive limit may speak up as it approaches
    later = drive_collecting(c, 60)
    assert not any("break" in m for m in later)
    assert all("driving time" in m for m in later)


def test_warnings_mention_what_is_due():
    c = HosClock()
    msgs = drive_collecting(c, 365)  # crosses the 2-hour break threshold
    assert len(msgs) == 1
    assert "break" in msgs[0]


def test_break_rearms_break_warnings_only():
    c = HosClock()
    drive_collecting(c, 485)        # all break warnings + violation spoken
    c.take_break(30)
    # next binding limit is the 11-hour drive clock (660): at 540 driving
    # the 2-hour warning for it fires once
    msgs = drive_collecting(c, 60)  # driving_min 485 -> 545
    assert any("driving time" in m and "2 hours" in m for m in msgs)
    # break thresholds can fire again on the fresh break window
    msgs = drive_collecting(c, 60)  # since_break 60 -> 120... not yet
    assert not any("break" in m for m in msgs)


def test_skipping_thresholds_speaks_only_the_most_urgent():
    c = HosClock()
    c.drive(470)  # jump straight to 10 minutes before the break rule
    msgs = c.check_warnings("realistic")
    assert len(msgs) == 1
    assert "30 minutes" in msgs[0]
    # the swallowed thresholds never fire later
    assert not any("2 hours" in m for m in drive_collecting(c, 5))


# -- modes -------------------------------------------------------------------

def test_relaxed_limits_are_25_percent_longer():
    drive, duty, brk = LIMITS["realistic"]
    assert LIMITS["relaxed"] == (drive * 1.25, duty * 1.25, brk * 1.25)


def test_relaxed_mode_delays_warnings():
    c = HosClock()
    c.drive(470)   # realistic would warn (10 minutes left before the break)
    assert c.check_warnings("relaxed") == []   # break rule now at 600
    assert not c.in_violation("relaxed")
    c.drive(140)   # 610 driving minutes: past the relaxed break rule
    assert c.in_violation("relaxed")


def test_off_mode_never_warns_or_violates():
    c = HosClock()
    c.drive(10_000)
    assert c.check_warnings("off") == []
    assert not c.in_violation("off")
    assert c.remaining_min("off") is None
    assert "debug bypass" in c.summary("off")


# -- serialization and compatibility ----------------------------------------------

def test_clock_roundtrips_through_dict():
    c = HosClock()
    c.drive(123)
    c.check_warnings("realistic")
    again = HosClock.from_dict(c.to_dict())
    assert again == c


def test_legacy_clock_data_migrates_to_eld_fields():
    data = {"driving_min": 120, "duty_min": 180, "since_break_min": 60}
    clock = HosClock.from_dict(data)
    assert clock.driving_min == 120
    assert clock.duty_min == 180
    assert clock.since_break_min == 60
    assert clock.status == "off_duty"
    assert clock.non_driving_min == 0


def test_clock_from_garbage_is_fresh():
    assert HosClock.from_dict(None) == HosClock()
    assert HosClock.from_dict("nonsense") == HosClock()
    assert HosClock.from_dict({"driving_min": "NaN-ish?"}) == HosClock()
    assert HosClock.from_dict({"driving_min": []}) == HosClock()


def test_v2_profile_loads_with_fresh_clock_and_no_fatigue():
    from freight_fate.models.profile import Profile

    p = Profile(name="V2 Driver")
    data = p.to_dict()
    data["version"] = 2
    data.pop("_signature", None)
    data.pop("_signature_version", None)
    del data["hos"]
    del data["fatigue"]
    p.path.write_text(json.dumps(data))
    loaded = Profile.load(p.path)
    assert loaded.hos == HosClock()
    assert loaded.fatigue == 0.0


def test_profile_persists_hos_and_fatigue():
    from freight_fate.models.profile import Profile

    p = Profile(name="Tired Driver")
    p.hos.drive(345)
    p.fatigue = 67.5
    loaded = Profile.load(p.save())
    assert loaded.hos.driving_min == 345
    assert loaded.fatigue == 67.5


# -- day/night ---------------------------------------------------------------------

def test_time_of_day_bands():
    assert time_of_day(6.0) == "dawn"
    assert time_of_day(12.0) == "day"
    assert time_of_day(20.0) == "dusk"
    assert time_of_day(23.0) == "night"
    assert time_of_day(3.0) == "night"
    assert time_of_day(27.0) == "night"  # wraps past midnight
    assert is_night(22.0) and not is_night(10.0)


def test_clock_text():
    assert clock_text(6.0) == "6 AM"
    assert clock_text(0.0) == "12 AM"
    assert clock_text(12.0) == "12 PM"
    assert clock_text(23.5) == "11:30 PM"
    assert clock_text(30.0) == "6 AM"


def test_clock_text_minute_rounding_carries_the_hour():
    # 59.99 minutes must round up to the next hour, not speak "11:60 PM",
    # and the AM/PM flip must follow the carried hour.
    assert clock_text(23.9999) == "12 AM"
    assert clock_text(11.9999) == "12 PM"
    assert clock_text(12.9999) == "1 PM"


def make_trip(world, start_hour, seed=2, start="Atlanta", end="Dallas"):
    from freight_fate.sim import Trip, TruckState, WeatherSystem

    route = world.route_options(start, end)[0]
    truck = TruckState()
    truck.transmission.automatic = True
    weather = WeatherSystem("south", seed=1)
    return Trip(route, truck, weather, seed=seed, start_hour=start_hour)


def test_night_zone_layout_is_deterministic(world):
    a = make_trip(world, start_hour=23.0, seed=11)
    b = make_trip(world, start_hour=23.0, seed=11)
    assert a.zones == b.zones


def test_night_produces_sparser_traffic(world):
    def traffic_count(hour):
        return sum(1 for s in range(40)
                   for z in make_trip(world, start_hour=hour, seed=s).zones
                   if z.reason == "heavy traffic")

    assert traffic_count(23.0) < traffic_count(12.0)


def test_night_raises_hazard_risk(world):
    day = make_trip(world, start_hour=12.0)
    night = make_trip(world, start_hour=23.0)
    assert night._hazard_risk() == pytest.approx(day._hazard_risk() + 0.10)


def test_trip_current_hour_advances_with_game_time(world):
    trip = make_trip(world, start_hour=6.0)
    trip.game_minutes = 18 * 60.0
    assert trip.current_hour == pytest.approx(0.0)  # 6 AM + 18 h = midnight


# -- fatigue ---------------------------------------------------------------------

def test_fatigue_grows_faster_at_night():
    assert hos.fatigue_rate_per_min(night=True) > hos.fatigue_rate_per_min(night=False)


def test_fatigue_shortens_the_reaction_window():
    assert reaction_window_mult(0.0) == 1.0
    assert reaction_window_mult(hos.FATIGUE_DROWSY) == 1.0
    assert reaction_window_mult(90.0) < 1.0
    assert reaction_window_mult(100.0) == pytest.approx(0.6)


def test_rest_helpers():
    assert hos.rest_break(50.0) == pytest.approx(15.0)
    assert hos.rest_break(10.0) == 0.0
    assert hos.rest_sleep(99.0) == 0.0
    assert hos.rest_shoulder(90.0) == 30.0   # poor rest floor
    assert hos.rest_shoulder(10.0) == 10.0   # never adds fatigue


def test_shoulder_damage_is_deterministic():
    for seed in range(20):
        assert (hos.shoulder_damage_due(seed, 88.0)
                == hos.shoulder_damage_due(seed, 88.0))
    results = {hos.shoulder_damage_due(seed, 88.0) for seed in range(100)}
    assert results == {True, False}


# -- overnight parking ----------------------------------------------------------------

def test_parking_is_only_scarce_at_night():
    assert parking_full_probability(12.0) == 0.0
    assert parking_full_probability(19.9) == 0.0
    assert 0.0 < parking_full_probability(20.0) < parking_full_probability(23.0)
    assert parking_full_probability(1.0) > parking_full_probability(20.0)
    assert parking_full_probability(3.9) > 0.0
    assert parking_full_probability(4.0) == 0.0


def test_parking_full_is_deterministic_per_seed_and_stop():
    for seed in range(20):
        assert (parking_is_full(seed, 88.0, 23.0)
                == parking_is_full(seed, 88.0, 23.0))
    # both outcomes occur across seeds
    results = {parking_is_full(s, 88.0, 23.0) for s in range(100)}
    assert results == {True, False}


def test_parking_fills_more_often_later_in_the_evening():
    full_at = lambda h: sum(parking_is_full(s, 88.0, h) for s in range(200))  # noqa: E731
    assert full_at(20.5) < full_at(23.5)


# -- driving state integration ----------------------------------------------------------

def start_drive(app):
    """New career, accept an unlocked job, pick a route; returns DrivingState."""
    from freight_fate.states.city import PickupFacilityState, RouteSelectState
    from freight_fate.states.driving import DrivingState
    from freight_fate.states.main_menu import MainMenuState

    app.push_state(MainMenuState(app.ctx))
    while app.state.items[app.state.index].text != "New career":
        app.state.handle_event(key_event(pygame.K_DOWN))
    app.state.handle_event(key_event(pygame.K_RETURN))
    app.state.handle_event(key_event(pygame.K_RETURN))  # default name
    app.state.handle_event(key_event(pygame.K_RETURN))  # default home terminal
    app.state.handle_event(key_event(pygame.K_RETURN))  # job board
    board = app.state
    while board.jobs[board.index].cargo.endorsement:  # skip locked teasers
        board.handle_event(key_event(pygame.K_DOWN))
    app.state.handle_event(key_event(pygame.K_RETURN))  # accept job
    assert isinstance(app.state, DrivingState)
    assert app.state.phase == "pickup"
    app.state.trip.position_mi = app.state.trip.total_miles
    app.state.trip.finished = True
    app.state.truck.velocity_mps = 0.0
    app.state.update(1 / 60)
    assert isinstance(app.state, PickupFacilityState)
    app.state.handle_event(key_event(pygame.K_RETURN))  # check in at origin
    app.state.handle_event(key_event(pygame.K_RETURN))  # load at dock
    app.state.handle_event(key_event(pygame.K_RETURN))  # depart for destination
    assert isinstance(app.state, RouteSelectState)
    app.state.handle_event(key_event(pygame.K_RETURN))  # accept planned route
    assert isinstance(app.state, DrivingState)
    assert app.state.phase == "delivery"
    app.state.truck.set_air_ready(parking_brake=False)
    return app.state


def select(menu, label):
    while not menu.items[menu.index].text.startswith(label):
        menu.handle_event(key_event(pygame.K_DOWN))
    menu.handle_event(key_event(pygame.K_RETURN))


def park_at_first_stop(driving):
    stop = driving.trip.stops[0]
    driving.trip.position_mi = stop.at_mi
    return stop


def park_away_from_stops(driving, *, after_stop) -> None:
    position = after_stop.at_mi + 2.0
    while position < driving.trip.total_miles - 1.0:
        driving.trip.position_mi = position
        nearby = driving.trip.nearest_stop_within() is not None
        sleep_ahead = driving._upcoming_stop_with_action("sleep", 30.0) is not None
        if not nearby and not sleep_ahead:
            return
        position += 5.0
    raise AssertionError("route has no shoulder-sleep test position away from stops")


@pytest.mark.smoke
def test_fatigued_driver_gets_a_shorter_hazard_window():
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    try:
        driving = start_drive(app)
        hazard = TripEvent(TripEventKind.HAZARD, "Brake now!", {"deadline_s": 4.0})
        app.ctx.profile.fatigue = 0.0
        driving._handle_trip_event(hazard)
        assert driving._hazard_deadline == pytest.approx(4.0)
        app.ctx.profile.fatigue = 100.0
        driving._handle_trip_event(hazard)
        assert driving._hazard_deadline == pytest.approx(2.4)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_rest_stop_menu_break_and_sleep():
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState, RestStopState

    app = App()
    try:
        driving = start_drive(app)
        park_at_first_stop(driving)
        driving.hos.drive(490)            # past the break rule
        app.ctx.profile.fatigue = 50.0
        driving.handle_event(key_event(pygame.K_t))
        assert isinstance(app.state, RestStopState)
        labels = [i.text for i in app.state.items]
        assert "Take a 30-minute break" in labels
        assert "Sleep 10 hours" in labels

        minutes_before = driving.trip.game_minutes
        select(app.state, "Take a 30-minute break")
        assert driving.trip.game_minutes == minutes_before + 30.0
        assert driving.hos.since_break_min == 0.0
        assert app.ctx.profile.fatigue == pytest.approx(15.0)

        select(app.state, "Sleep 10 hours")
        assert driving.trip.game_minutes == minutes_before + 30.0 + 600.0
        assert driving.hos.driving_min == 0.0
        assert driving.hos.duty_min == 0.0
        assert app.ctx.profile.fatigue == 0.0

        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, DrivingState)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_full_parking_offers_drive_on_and_shoulder(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import (
        DrivingState,
        ParkingFullState,
        ShoulderSleepConfirmationState,
    )

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say",
                        lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        park_at_first_stop(driving)
        monkeypatch.setattr("freight_fate.sim.hos.parking_is_full",
                            lambda *a, **k: True)
        monkeypatch.setattr("freight_fate.sim.hos.shoulder_fine_due",
                            lambda *a, **k: True)
        monkeypatch.setattr("freight_fate.sim.hos.shoulder_damage_due",
                            lambda *a, **k: True)
        driving.handle_event(key_event(pygame.K_t))
        assert isinstance(app.state, ParkingFullState)
        labels = [i.text for i in app.state.items]
        assert any(text.startswith("Drive on") for text in labels)
        assert any("shoulder" in text for text in labels)

        select(app.state, "Park on the shoulder")
        assert isinstance(app.state, ShoulderSleepConfirmationState)
        assert "emergency-only" in spoken[-1]
        assert "possible" in spoken[-1] or "may be ticketed" in spoken[-1]

        # shoulder parking: HOS reset, fatigue floor 30, deadline kept counting
        driving.hos.drive(700)
        app.ctx.profile.fatigue = 95.0
        money_before = app.ctx.profile.money
        damage_before = driving.truck.damage_pct
        minutes_before = driving.trip.game_minutes
        select(app.state, "Sleep on the shoulder")
        assert isinstance(app.state, DrivingState)
        assert driving.trip.game_minutes == minutes_before + 600.0
        assert driving.hos.driving_min == 0.0
        assert app.ctx.profile.fatigue == 30.0
        assert app.ctx.profile.money == money_before - hos.SHOULDER_FINE
        assert driving.truck.damage_pct == pytest.approx(
            damage_before + hos.SHOULDER_DAMAGE_PCT)
        assert app.ctx.profile.active_trip is not None
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_emergency_shoulder_sleep_pause_menu_constraints(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import PauseMenuState, ShoulderSleepConfirmationState

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say",
                        lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        stop = park_at_first_stop(driving)
        driving.hos.drive(500)
        assert driving.emergency_shoulder_sleep_reason() is None

        driving.trip.position_mi = stop.at_mi + 2.0
        driving.truck.velocity_mps = 15.0
        assert driving.emergency_shoulder_sleep_reason() is None

        driving.truck.velocity_mps = 0.0
        reason = driving.emergency_shoulder_sleep_reason()
        assert reason is not None
        assert "past your hours-of-service limit" in reason

        driving.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, PauseMenuState)
        labels = [item.text for item in app.state.items]
        assert "Emergency shoulder sleep" in labels

        select(app.state, "Emergency shoulder sleep")
        assert isinstance(app.state, ShoulderSleepConfirmationState)
        assert "If hours of service are enforced" in spoken[-1]
        assert "minor truck damage" in spoken[-1]
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_hos_off_still_allows_fatigue_emergency_shoulder_sleep(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import PauseMenuState, ShoulderSleepConfirmationState

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say",
                        lambda text, interrupt=True: spoken.append(text))
    try:
        app.ctx.settings.hos_mode = "debug_off"
        driving = start_drive(app)
        stop = park_at_first_stop(driving)

        park_away_from_stops(driving, after_stop=stop)
        driving.truck.velocity_mps = 0.0
        app.ctx.profile.fatigue = 20.0
        assert driving.emergency_shoulder_sleep_reason() is None

        app.ctx.profile.fatigue = hos.FATIGUE_SEVERE
        reason = driving.emergency_shoulder_sleep_reason()
        assert reason is not None
        assert "Fatigue is severe" in reason

        driving.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, PauseMenuState)
        labels = [item.text for item in app.state.items]
        assert "Emergency shoulder sleep" in labels

        select(app.state, "Emergency shoulder sleep")
        assert isinstance(app.state, ShoulderSleepConfirmationState)
        assert "poor rest" in spoken[-1]
        assert "If hours of service are enforced" in spoken[-1]
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_parking_never_full_during_the_day():
    from freight_fate.app import App
    from freight_fate.states.driving import RestStopState

    app = App()
    try:
        driving = start_drive(app)
        park_at_first_stop(driving)
        assert not (driving.trip.current_hour >= 20 or driving.trip.current_hour < 4)
        driving.handle_event(key_event(pygame.K_t))   # 6 AM start: lot has room
        assert isinstance(app.state, RestStopState)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_city_sleep_resets_hours_and_advances_the_clock():
    """A spent duty window used to follow you into the city with no way to
    sleep it off short of driving (illegally) to a rest stop."""
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState
    from freight_fate.states.main_menu import MainMenuState

    app = App()
    try:
        app.push_state(MainMenuState(app.ctx))
        while app.state.items[app.state.index].text != "New career":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        app.state.handle_event(key_event(pygame.K_RETURN))  # default name
        app.state.handle_event(key_event(pygame.K_RETURN))  # home terminal
        assert isinstance(app.state, CityMenuState)
        p = app.ctx.profile
        p.hos.drive(660)          # a fully spent shift
        p.fatigue = 75.0
        before = p.game_hours
        select(app.state, "Sleep 10 hours")
        assert p.game_hours == pytest.approx(before + 10.0)
        assert p.hos.driving_min == 0.0
        assert p.hos.duty_min == 0.0
        assert p.fatigue == 0.0
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_snapshot_roundtrip_preserves_hos_fatigue_and_fines():
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        driving = start_drive(app)
        driving.hos.drive(372)
        driving.hos.check_warnings("realistic")
        driving.hos_fine_count = 2
        app.ctx.profile.fatigue = 41.5
        snap = driving.snapshot()
        resumed = DrivingState.from_snapshot(app.ctx, snap)
        assert resumed is not None
        assert resumed.hos.driving_min == 372
        assert resumed.hos.warned == driving.hos.warned
        assert resumed.hos_fine_count == 2
        assert app.ctx.profile.fatigue == 41.5
        # the resumed state shares the profile's clock, like a fresh drive
        assert resumed.hos is app.ctx.profile.hos
    finally:
        app.shutdown()


def test_pre_1_5_snapshot_resumes_with_fresh_clock():
    """A 1.2-1.4 era snapshot (no HOS keys) must load with defaults."""
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState
    from freight_fate.states.main_menu import enter_world

    app = App()
    try:
        p = Profile(name="Old Save")
        p.active_trip = {
            "job": {"cargo": "general", "weight_tons": 14.0,
                    "origin": "Chicago", "origin_location": "Cicero Rail Hub",
                    "destination": "Denver", "distance_mi": 1150.0,
                    "pay": 2800.0, "deadline_game_h": 31.0, "market_mult": 1.0},
            "route_cities": ["Chicago", "St. Louis", "Kansas City", "Denver"],
            "trip_seed": 1234, "position_mi": 412.0, "game_minutes": 540.0,
            "start_damage": 3.0, "speeding_strikes": 1,
        }
        app.ctx.profile = p
        enter_world(app.ctx)
        assert isinstance(app.state, DrivingState)
        assert app.state.resumed
        assert app.state.hos == HosClock()
        assert app.state.hos_fine_count == 0
        assert p.fatigue == 0.0
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_inspections_fire_only_in_violation(world):
    from freight_fate.sim.trip import TripEventKind

    def run_trip(violating):
        trip = make_trip(world, start_hour=12.0, seed=5,
                         start="Chicago", end="Indianapolis")
        truck = trip.truck
        truck.start_engine()
        truck.throttle = 0.85
        trip.hos_violation = violating
        events = []
        for _ in range(60 * 60 * 30):
            truck.auto_shift()
            truck.update(1 / 60)
            events += trip.update(1 / 60)
            if trip.finished:
                break
        return [e for e in events if e.kind == TripEventKind.INSPECTION]

    assert run_trip(violating=False) == []
    assert len(run_trip(violating=True)) >= 1


@pytest.mark.smoke
def test_inspection_fines_escalate_and_hit_reputation():
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    try:
        driving = start_drive(app)
        p = app.ctx.profile
        rep = p.career.reputation
        money = p.money
        event = TripEvent(TripEventKind.INSPECTION, "Weigh station.")
        driving._handle_inspection(event)
        driving._handle_inspection(event)
        assert p.money == money - hos.HOS_FINES[0] - hos.HOS_FINES[1]
        assert p.career.reputation == rep - 2 * hos.HOS_REPUTATION_HIT
        assert driving.hos_fine_count == 2
    finally:
        app.shutdown()


def test_route_backed_weigh_station_emits_evidence(world):
    from freight_fate.sim.trip import RoadStop, TripEventKind

    trip = make_trip(world, start_hour=12.0, seed=5,
                     start="Chicago", end="Indianapolis")
    trip.stops = [
        RoadStop("Example Scale", 10.0, "weigh_station", ("inspect",), ())
    ]
    trip.position_mi = 10.1
    trip.hos_violation = True
    trip._events = []

    trip._check_inspections(1.0)

    events = [e for e in trip._events if e.kind == TripEventKind.INSPECTION]
    assert len(events) == 1
    assert events[0].data["context"] == "weigh_station"
    assert events[0].data["evidence"] == ("HOS/ELD violation",)


@pytest.mark.smoke
def test_serious_hos_inspection_orders_out_of_service_reset():
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    try:
        driving = start_drive(app)
        p = app.ctx.profile
        driving.hos.drive(481)
        money = p.money
        minutes = driving.trip.game_minutes
        event = TripEvent(
            TripEventKind.INSPECTION,
            "Inspection station open.",
            {"key": "scale:1", "evidence": ("HOS/ELD violation",)},
        )

        driving._handle_inspection(event)

        assert p.money == money - hos.HOS_FINES[0]
        assert driving.trip.game_minutes == minutes + hos.SLEEP_MIN
        assert driving.hos.driving_min == 0
        assert driving.out_of_service_count == 1

        driving._handle_inspection(event)
        assert p.money == money - hos.HOS_FINES[0]
        assert driving.out_of_service_count == 1
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_hos_clock_runs_on_game_time():
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        app.ctx.settings.hos_mode = "realistic"
        driving.truck.velocity_mps = 10.0   # rolling: counts as driving
        before = driving.hos.driving_min
        driving._update_hours_and_fatigue(1.0)  # one real second
        gained = driving.hos.driving_min - before
        assert gained == pytest.approx(driving.trip.time_scale / 60.0)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_settings_menu_cycles_hours_of_service():
    from freight_fate.app import App
    from freight_fate.states.main_menu import SettingsState

    app = App()
    try:
        assert app.ctx.settings.hos_mode == "realistic"
        state = SettingsState(app.ctx)
        app.push_state(state)
        while not state.items[state.index].text.startswith("Hours of service"):
            state.handle_event(key_event(pygame.K_DOWN))
        state.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.hos_mode == "relaxed"
        state.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.hos_mode == "realistic"
        state.handle_event(key_event(pygame.K_LEFT))
        assert app.ctx.settings.hos_mode == "relaxed"
    finally:
        app.shutdown()


def test_settings_menu_saves_each_change():
    from freight_fate.app import App
    from freight_fate.settings import Settings
    from freight_fate.states.main_menu import SettingsState

    app = App()
    try:
        state = SettingsState(app.ctx)
        app.push_state(state)
        assert app.ctx.settings.imperial_units is True
        while not state.items[state.index].text.startswith("Units"):
            state.handle_event(key_event(pygame.K_DOWN))
        state.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.imperial_units is False
        assert Settings.load().imperial_units is False
    finally:
        app.shutdown()


def test_settings_menu_volume_survives_new_app_session():
    from freight_fate.app import App
    from freight_fate.settings import Settings
    from freight_fate.states.main_menu import SettingsState

    app = App()
    try:
        state = SettingsState(app.ctx)
        app.push_state(state)
        state.handle_event(key_event(pygame.K_TAB))
        assert state.title == "Audio 2/4"
        while not state.items[state.index].text.startswith("Music volume"):
            state.handle_event(key_event(pygame.K_DOWN))
        state.handle_event(key_event(pygame.K_RIGHT))
        assert app.ctx.settings.music_volume == 0.6
        assert Settings.load().music_volume == 0.6
        while not state.items[state.index].text.startswith("Weather sounds volume"):
            state.handle_event(key_event(pygame.K_UP))
        state.handle_event(key_event(pygame.K_RIGHT))
        assert app.ctx.settings.weather_volume == 0.75
        assert Settings.load().weather_volume == 0.75
        state.handle_event(key_event(pygame.K_LEFT))
        assert app.ctx.settings.weather_volume == 0.65
        assert Settings.load().weather_volume == 0.65
    finally:
        app.shutdown()

    next_app = App()
    try:
        assert next_app.ctx.settings.music_volume == 0.6
        assert next_app.ctx.audio.music_volume == 0.6
        assert next_app.ctx.settings.weather_volume == 0.65
        assert next_app.ctx.audio.weather_volume == 0.65
    finally:
        next_app.shutdown()


def test_settings_menu_f1_has_help_for_every_item():
    from freight_fate.app import App
    from freight_fate.states.main_menu import SettingsState

    app = App()
    try:
        state = SettingsState(app.ctx)
        app.push_state(state)
        for screen_index in range(len(state.screens)):
            state.screen_index = screen_index
            state.refresh(keep_index=False)
            for i, item in enumerate(state.items):
                state.index = i
                text = state.current_help()
                assert item.text in text or item.help
                assert len(text) > len(state.intro_help)
    finally:
        app.shutdown()


def test_settings_menu_pages_like_status_panel():
    from freight_fate.app import App
    from freight_fate.states.main_menu import SettingsState

    app = App()
    try:
        state = SettingsState(app.ctx)
        app.push_state(state)

        assert state.title == "Gameplay 1/4"
        state.handle_event(key_event(pygame.K_TAB))
        assert state.title == "Audio 2/4"
        state.handle_event(key_event(pygame.K_TAB))
        assert state.title == "Speech and weather 3/4"
        state.handle_event(key_event(pygame.K_TAB, mod=pygame.KMOD_SHIFT))
        assert state.title == "Audio 2/4"
        assert state.items[state.index].text.startswith("Master volume")
        state.handle_event(key_event(pygame.K_DOWN))
        assert state.items[state.index].text.startswith("Gameplay cues volume")
    finally:
        app.shutdown()
