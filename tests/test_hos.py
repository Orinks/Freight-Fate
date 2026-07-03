"""Hours of service, fatigue, day/night, and overnight parking (1.5.0)."""

import json
from types import SimpleNamespace

import pygame
import pytest

from freight_fate.sim import hos
from freight_fate.sim.hos import (
    LIMITS,
    DutyLog,
    HosClock,
    clock_text,
    is_night,
    parking_full_probability,
    parking_is_full,
    reaction_window_mult,
    time_of_day,
)


def test_hazard_scale_only_relaxes_relaxed_mode():
    from freight_fate.sim.hos import RELAXED_HAZARD_SCALE, hazard_scale

    assert hazard_scale("relaxed") == RELAXED_HAZARD_SCALE
    assert hazard_scale("relaxed") < 1.0
    assert hazard_scale("realistic") == 1.0
    assert hazard_scale("debug_off") == 1.0


def key_event(key, unicode="", mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode, mod=mod)


def finish_timed_state(app):
    from freight_fate.states.base import TimedMessageState

    assert isinstance(app.state, TimedMessageState)
    app.state.update(app.state.remaining + 0.01)


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


def test_eight_two_sleeper_split_restores_time_without_full_reset():
    c = HosClock()
    c.drive(300)
    c.sleeper_split_rest(480)
    c.drive(300)
    c.sleeper_split_rest(120)

    assert c.driving_min == pytest.approx(300)
    assert c.duty_min == pytest.approx(300)
    assert c.since_break_min == 0
    assert c.status == "sleeper_berth"
    assert c.split_pending_summary() is None


def test_normal_sleeper_periods_can_complete_split_credit():
    c = HosClock()
    c.drive(300)
    c.sleeper(480)
    c.drive(300)
    c.sleeper(120)

    assert c.driving_min == pytest.approx(300)
    assert c.duty_min == pytest.approx(300)
    assert c.split_pending_summary() is None


def test_rolling_sleeper_split_reuses_previous_short_rest():
    c = HosClock()
    c.sleeper(480)
    c.drive(240)
    c.off_duty(120)
    assert c.split_pending_summary() is None
    c.drive(300)
    c.sleeper(480)

    assert c.driving_min == pytest.approx(300)
    assert c.duty_min == pytest.approx(300)
    assert c.split_pending_summary() is None


def test_short_first_sleeper_split_preserves_between_rest_driving():
    c = HosClock()
    c.drive(60)
    c.sleeper(120)
    c.drive(600)
    c.sleeper(480)

    assert c.driving_min == pytest.approx(600)
    assert c.duty_min == pytest.approx(600)
    assert c.split_pending_summary() is None


def test_long_first_sleeper_split_preserves_between_rest_driving():
    c = HosClock()
    c.drive(60)
    c.sleeper(480)
    c.drive(300)
    c.sleeper(120)

    assert c.driving_min == pytest.approx(300)
    assert c.duty_min == pytest.approx(300)
    assert c.split_pending_summary() is None


def test_long_first_split_survives_fragmented_driving_history():
    c = HosClock()
    c.drive(60)
    c.sleeper(480)
    for _ in range(120):
        c.drive(2)
    c.sleeper(120)

    assert c.driving_min == pytest.approx(240)
    assert c.duty_min == pytest.approx(240)
    assert c.split_pending_summary() is None


def test_short_first_split_survives_fragmented_driving_history():
    c = HosClock()
    c.drive(60)
    c.sleeper(120)
    for _ in range(120):
        c.drive(2)
    c.sleeper(480)

    assert c.driving_min == pytest.approx(240)
    assert c.duty_min == pytest.approx(240)
    assert c.split_pending_summary() is None


def test_seven_three_sleeper_split_restores_time_without_full_reset():
    c = HosClock()
    c.drive(90)
    c.sleeper_split_rest(420)
    c.on_duty(60)
    c.drive(180)
    c.sleeper_split_rest(180)

    assert c.driving_min == pytest.approx(180)
    assert c.duty_min == pytest.approx(240)
    assert c.since_break_min == 0
    assert c.split_pending_summary() is None


def test_short_off_duty_can_complete_sleeper_split():
    c = HosClock()
    c.drive(300)
    c.sleeper_split_rest(480)
    c.drive(60)
    c.off_duty(120)

    assert c.driving_min == pytest.approx(60)
    assert c.duty_min == pytest.approx(60)
    assert c.split_pending_summary() is None


def test_repeated_sleeper_splits_can_each_apply_credit():
    c = HosClock()
    c.drive(300)
    assert c.sleeper_split_rest(480) is False
    c.drive(60)
    c.off_duty(120)
    assert c.driving_min == pytest.approx(60)
    assert c.duty_min == pytest.approx(60)

    c.drive(300)
    assert c.sleeper_split_rest(480) is True
    assert c.driving_min == pytest.approx(300)
    assert c.duty_min == pytest.approx(300)
    c.drive(60)
    c.off_duty(120)

    assert c.driving_min == pytest.approx(60)
    assert c.duty_min == pytest.approx(60)
    assert c.split_pending_summary() is None


def test_full_off_duty_and_sleeper_resets_clear_split_pending_summary():
    off = HosClock()
    off.drive(300)
    off.off_duty(600)
    assert off.driving_min == 0
    assert off.split_pending_summary() is None

    sleeper = HosClock()
    sleeper.drive(300)
    sleeper.sleeper(600)
    assert sleeper.driving_min == 0
    assert sleeper.split_pending_summary() is None


def test_split_long_period_must_be_sleeper_berth():
    c = HosClock()
    c.drive(300)
    c.off_duty(480)
    c.drive(60)
    completed = c.sleeper_split_rest(120)

    assert completed is False
    assert c.driving_min == pytest.approx(360)
    assert c.duty_min == pytest.approx(960)


def test_split_pending_summary_names_needed_pair():
    c = HosClock()
    c.drive(300)
    c.sleeper_split_rest(480)

    assert c.split_pending_summary() == (
        "Sleeper split pending: pair this with 2 more hours at sleep-capable parking."
    )


def test_hos_summary_mentions_pending_sleeper_split():
    c = HosClock()
    c.drive(300)
    c.sleeper_split_rest(480)

    summary = c.summary("realistic")

    assert "Sleeper split pending" in summary
    assert "2 more hours" in summary


def test_completed_split_summary_stays_clear_after_dict_roundtrip():
    c = HosClock()
    c.drive(300)
    c.sleeper_split_rest(480)
    c.drive(300)
    c.sleeper_split_rest(120)

    again = HosClock.from_dict(c.to_dict())

    assert again.split_pending_summary() is None


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


def drive_collecting(
    c: HosClock, minutes: float, mode: str = "realistic", step: float = 5.0
) -> list[str]:
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
    drive_collecting(c, 485)  # all break warnings + violation spoken
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


def test_warning_batch_speaks_only_most_urgent_limit():
    c = HosClock()
    c.drive(900)

    msgs = c.check_warnings("realistic")

    assert len(msgs) == 1
    assert "violation" in msgs[0]
    assert "driving time" in msgs[0]


def test_break_only_violation_summary_requests_break_not_sleep():
    c = HosClock()
    c.drive(481)

    summary = c.summary("realistic")

    assert "30-minute break" in summary or "30 minute break" in summary
    assert "Sleep 10 hours" not in summary


def test_hos_summary_includes_time_units():
    c = HosClock()
    c.drive(120)

    summary = c.summary("realistic")

    assert "9.0 hours of driving left" in summary
    assert "break due in 6.0 hours" in summary
    assert "duty window closes in 12.0 hours" in summary


def test_hos_summary_omits_break_when_duty_window_closes_first():
    c = HosClock()
    c.driving_min = 414
    c.since_break_min = 270
    c.duty_min = 732
    c.status = "driving"

    summary = c.summary("realistic")

    assert "1.8 hours of duty window left" in summary
    assert "break due" not in summary


# -- modes -------------------------------------------------------------------


def test_relaxed_limits_are_25_percent_longer():
    drive, duty, brk = LIMITS["realistic"]
    assert LIMITS["relaxed"] == (drive * 1.25, duty * 1.25, brk * 1.25)


def test_relaxed_mode_delays_warnings():
    c = HosClock()
    c.drive(470)  # realistic would warn (10 minutes left before the break)
    assert c.check_warnings("relaxed") == []  # break rule now at 600
    assert not c.in_violation("relaxed")
    c.drive(140)  # 610 driving minutes: past the relaxed break rule
    assert c.in_violation("relaxed")


def test_off_mode_never_warns_or_violates():
    c = HosClock()
    c.drive(10_000)
    assert c.check_warnings("off") == []
    assert not c.in_violation("off")
    assert c.remaining_min("off") is None
    assert "developer mode" not in c.summary("off")
    assert "enforcement is off" in c.summary("off")


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


def test_legacy_history_full_reset_does_not_become_pending_split():
    c = HosClock()
    c.drive(300)
    c.sleeper(600)
    data = c.to_dict()
    data.pop("split_rest_history", None)

    again = HosClock.from_dict(data)

    assert again.split_pending_summary() is None
    again.drive(60)
    again.off_duty(120)
    assert again.driving_min == pytest.approx(60)
    assert again.duty_min == pytest.approx(180)


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


def test_duty_log_records_coalesces_and_roundtrips():
    log = DutyLog()
    log.record("driving", 6.0, 7.0, "I-90 from Chicago to Toledo")
    log.record("driving", 7.0, 7.5, "I-90 from Chicago to Toledo")
    log.record("off_duty", 7.5, 8.0, "Ohio Turnpike service plaza", "30-minute break")

    assert len(log.segments) == 2
    assert log.segments[0].duration_hours == pytest.approx(1.5)
    assert log.totals_since(6.0, 8.0)["driving"] == pytest.approx(1.5)

    again = DutyLog.from_dict(log.to_dict())
    assert len(again.segments) == 2
    assert again.segments[1].note == "30-minute break"


def test_profile_persists_duty_log():
    from freight_fate.models.profile import Profile

    p = Profile(name="Log Driver")
    p.duty_log.record("on_duty_not_driving", 6.0, 6.25, "Chicago terminal", "pre-trip")
    loaded = Profile.load(p.save())
    assert len(loaded.duty_log.segments) == 1
    assert loaded.duty_log.segments[0].location == "Chicago terminal"


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
    weather = WeatherSystem("atlantic_southeast", seed=1)
    return Trip(route, truck, weather, seed=seed, start_hour=start_hour)


def test_night_zone_layout_is_deterministic(world):
    a = make_trip(world, start_hour=23.0, seed=11)
    b = make_trip(world, start_hour=23.0, seed=11)
    assert a.zones == b.zones


def test_night_produces_sparser_traffic(world):
    def traffic_count(hour):
        return sum(
            1
            for s in range(40)
            for z in make_trip(world, start_hour=hour, seed=s).zones
            if z.reason == "heavy traffic"
        )

    assert traffic_count(23.0) < traffic_count(12.0)


def test_rush_hour_increases_corridor_traffic_density(world):
    rush = make_trip(world, start_hour=8.0, start="Chicago", end="Indianapolis")
    midday = make_trip(world, start_hour=12.0, start="Chicago", end="Indianapolis")
    leg = rush.route.legs[0]

    assert rush._leg_traffic_density(leg, 0.0, False) > midday._leg_traffic_density(leg, 0.0, False)


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
    assert hos.rest_coffee_break(50.0) == pytest.approx(42.0)
    assert hos.rest_coffee_break(6.0) == 0.0
    assert hos.rest_coffee_break(50.0) > hos.rest_break(50.0)
    daytime_boost_min = (50.0 - hos.rest_coffee_break(50.0)) / hos.fatigue_rate_per_min(False)
    daytime_break_min = (50.0 - hos.rest_break(50.0)) / hos.fatigue_rate_per_min(False)
    assert 60.0 < daytime_boost_min < daytime_break_min
    assert hos.rest_break(50.0) == pytest.approx(15.0)
    assert hos.rest_break(10.0) == 0.0
    assert hos.rest_sleep(99.0) == 0.0
    assert hos.rest_shoulder(90.0) == 30.0  # poor rest floor
    assert hos.rest_shoulder(10.0) == 10.0  # never adds fatigue


def test_shoulder_damage_is_deterministic():
    for seed in range(20):
        assert hos.shoulder_damage_due(seed, 88.0) == hos.shoulder_damage_due(seed, 88.0)
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
        assert parking_is_full(seed, 88.0, 23.0) == parking_is_full(seed, 88.0, 23.0)
    # both outcomes occur across seeds
    results = {parking_is_full(s, 88.0, 23.0) for s in range(100)}
    assert results == {True, False}


def test_parking_fills_more_often_later_in_the_evening():
    full_at = lambda h: sum(parking_is_full(s, 88.0, h) for s in range(200))  # noqa: E731
    assert full_at(20.5) < full_at(23.5)


# -- driving state integration ----------------------------------------------------------


def start_drive(app):
    """New career, accept the assigned dispatch, depart; returns DrivingState."""
    from freight_fate.states.city import PickupFacilityState
    from freight_fate.states.driving import DrivingState
    from freight_fate.states.main_menu import MainMenuState

    app.push_state(MainMenuState(app.ctx))
    while app.state.items[app.state.index].text != "New career":
        app.state.handle_event(key_event(pygame.K_DOWN))
    app.state.handle_event(key_event(pygame.K_RETURN))
    app.state.handle_event(key_event(pygame.K_RETURN))  # default name
    app.state.handle_event(key_event(pygame.K_RETURN))  # default career start
    app.state.handle_event(key_event(pygame.K_RETURN))  # default region
    app.state.handle_event(key_event(pygame.K_RETURN))  # default home terminal
    app.state.handle_event(key_event(pygame.K_RETURN))  # job board
    assert app.state.assigned_mode
    app.state.handle_event(key_event(pygame.K_RETURN))  # accept assigned job
    assert isinstance(app.state, DrivingState)
    assert app.state.phase == "pickup"
    app.state.trip.position_mi = app.state.trip.total_miles
    app.state.trip.finished = True
    app.state.truck.velocity_mps = 0.0
    app.state.update(1 / 60)
    finish_timed_state(app)
    assert isinstance(app.state, PickupFacilityState)
    app.state.handle_event(key_event(pygame.K_RETURN))  # check in at origin
    app.state.handle_event(key_event(pygame.K_RETURN))  # load at dock
    finish_timed_state(app)
    app.state.handle_event(key_event(pygame.K_RETURN))  # depart on assigned route
    assert isinstance(app.state, DrivingState)
    assert app.state.phase == "delivery"
    app.state.truck.set_air_ready(parking_brake=False)
    return app.state


def select(menu, label):
    while not menu.items[menu.index].text.startswith(label):
        menu.handle_event(key_event(pygame.K_DOWN))
    menu.handle_event(key_event(pygame.K_RETURN))


def park_at_first_stop(driving):
    # Prefer a sleep-capable stop the truck can actually open: additive
    # service-plaza/fuel POIs may sort ahead of the curated overnight stops, and
    # the rest / parking-full menus only apply where sleeping is offered.
    # nearest_stop_within returns the first stop within range in sorted order, so
    # skip sleepers shadowed by a nearer non-sleep stop.
    stops = driving.trip.stops

    def opens_here(stop):
        for other in stops:
            if abs(other.at_mi - stop.at_mi) <= 1.5:
                return other is stop
        return False

    stop = next((s for s in stops if "sleep" in s.actions and opens_here(s)), None)
    if stop is None:
        # Job-board variety means some routes carry no sleep-capable stop; inject
        # a deterministic one so the sleep / parking-full tests never depend on
        # which route the career happened to draw.
        from freight_fate.sim.trip import RoadStop

        stop = RoadStop(
            name="Test Travel Center",
            at_mi=max(1.0, driving.trip.total_miles * 0.5),
            type="travel_center",
            actions=("park", "save", "fuel", "food", "break", "sleep"),
            services=("diesel", "food", "parking"),
            parking="confirmed",
        )
        driving.trip.stops = [stop]
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
def test_hos_violation_speech_interrupts_but_threshold_warning_does_not(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=False: spoken.append((text, interrupt)),
    )
    try:
        driving = start_drive(app)
        app.ctx.settings.hos_mode = "realistic"
        app.ctx.settings.time_scale = 60.0
        driving.trip.time_scale = 60.0
        driving.truck.velocity_mps = 25.0  # past 50 mph: full compression

        driving.hos.driving_min = LIMITS["realistic"][0] - 121.0
        driving.hos.duty_min = driving.hos.driving_min
        driving.hos.since_break_min = 0.0
        driving._update_hours_and_fatigue(1.0)
        warning = spoken[-1]
        assert warning[0].startswith("Hours of service: 2 hours")
        assert warning[1] is False

        driving.hos.driving_min = LIMITS["realistic"][0] - 0.5
        driving.hos.duty_min = driving.hos.driving_min
        driving.hos.since_break_min = 0.0
        driving.hos.warned.clear()
        driving._update_hours_and_fatigue(1.0)
        violation = spoken[-1]
        assert violation[0].startswith("Hours of service violation:")
        assert violation[1] is True
    finally:
        app.shutdown()


def test_severe_fatigue_drift_warning_is_urgent(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(
        app.ctx,
        "say_event",
        lambda text, interrupt=False: spoken.append((text, interrupt)),
    )
    try:
        driving = start_drive(app)
        app.ctx.profile.fatigue = hos.FATIGUE_SEVERE
        driving.truck.velocity_mps = 20.0

        driving._update_hours_and_fatigue(1.0)

        warning = spoken[-1]
        assert warning[0].startswith("You are dangerously drowsy")
        assert warning[1] is True
    finally:
        app.shutdown()


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
        driving.hos.drive(490)  # past the break rule
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
def test_food_and_coffee_break_boosts_alertness_without_resetting_break_rule(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import RoadStop
    from freight_fate.states.driving import RestStopState

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        stop = RoadStop(
            name="Test Coffee Stop",
            at_mi=max(1.0, driving.trip.total_miles * 0.5),
            type="travel_center",
            actions=("park", "food", "break", "sleep"),
            services=("food", "parking"),
            parking="confirmed",
        )
        driving.trip.stops = [stop]
        driving.trip.position_mi = stop.at_mi
        driving.hos.drive(100.0)
        app.ctx.profile.fatigue = 55.0
        driving.handle_event(key_event(pygame.K_t))
        assert isinstance(app.state, RestStopState)

        food_item = next(item for item in app.state.items if item.text == "Food and coffee break")
        assert "Coffee eases fatigue a little" in food_item.help
        assert "does not satisfy the 30-minute break rule" in food_item.help

        minutes_before = driving.trip.game_minutes
        select(app.state, "Food and coffee break")

        assert driving.trip.game_minutes == pytest.approx(minutes_before + 15.0)
        assert driving.hos.since_break_min == pytest.approx(100.0)
        assert app.ctx.profile.fatigue == pytest.approx(47.0)
        assert "coffee helps you stay alert a little longer" in spoken[-1]
        assert "does not reset your 30-minute break requirement" in spoken[-1]
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_sleep_capable_stop_offers_sleeper_split_choices():
    from freight_fate.app import App
    from freight_fate.states.driving import RestStopState

    app = App()
    try:
        driving = start_drive(app)
        sleeper = SimpleNamespace(
            name="Big Truck Stop",
            at_mi=driving.trip.position_mi,
            type="truck_stop",
            actions=("break", "fuel", "sleep"),
            services=(),
            parking="confirmed",
            exit_label="",
            spoken_name="Big Truck Stop",
            parking_text="confirmed truck parking",
        )
        items = RestStopState(app.ctx, driving, sleeper).build_items()
        labels = [i.text for i in items]

        assert "Sleep 2 hours in sleeper berth" in labels
        assert "Sleep 3 hours in sleeper berth" in labels
        assert "Sleep 7 hours in sleeper berth" in labels
        assert "Sleep 8 hours in sleeper berth" in labels
        assert "Sleep 10 hours" in labels
        back = next(i for i in items if i.text == "Back to the road")
        assert back.help
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_split_sleeper_rest_action_advances_clock_and_speaks_status(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import RestStopState

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    awards = []
    original_award = app.ctx.award_achievement

    def record_award(achievement_id: str, **kwargs):
        awards.append((achievement_id, len(spoken)))
        return original_award(achievement_id, **kwargs)

    monkeypatch.setattr(app.ctx, "award_achievement", record_award)
    try:
        driving = start_drive(app)
        sleeper = SimpleNamespace(
            name="Big Truck Stop",
            at_mi=driving.trip.position_mi,
            type="truck_stop",
            actions=("break", "fuel", "sleep"),
            services=(),
            parking="confirmed",
            exit_label="",
            spoken_name="Big Truck Stop",
            parking_text="confirmed truck parking",
        )
        app.push_state(RestStopState(app.ctx, driving, sleeper))
        before = driving.trip.game_minutes

        select(app.state, "Sleep 8 hours in sleeper berth")

        assert driving.trip.game_minutes == pytest.approx(before + 480.0)
        assert driving.hos.status == "sleeper_berth"
        status_index = next(i for i, text in enumerate(spoken) if "Sleeper split pending" in text)
        assert ("slept_on_route", status_index + 1) in awards

        spoken.clear()
        driving.hos.drive(300)
        select(app.state, "Sleep 2 hours in sleeper berth")

        completed_line = spoken[-1]
        assert "Sleeper split credited" in completed_line
        assert "hours of driving left" in completed_line
        assert "duty window closes" in completed_line
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
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        park_at_first_stop(driving)
        monkeypatch.setattr("freight_fate.sim.hos.parking_is_full", lambda *a, **k: True)
        monkeypatch.setattr("freight_fate.sim.hos.shoulder_fine_due", lambda *a, **k: True)
        monkeypatch.setattr("freight_fate.sim.hos.shoulder_damage_due", lambda *a, **k: True)
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
        assert driving.truck.damage_pct == pytest.approx(damage_before + hos.SHOULDER_DAMAGE_PCT)
        assert app.ctx.profile.active_trip is not None
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_emergency_shoulder_sleep_pause_menu_constraints(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import PauseMenuState, ShoulderSleepConfirmationState

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
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
        assert app.state.items[app.state.index].text == ("Cancel and keep looking for a safe stop")
        assert "previous menu" in app.state.intro_help
        assert "returns to the road" not in app.state.intro_help
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_hos_off_still_allows_fatigue_emergency_shoulder_sleep(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import PauseMenuState, ShoulderSleepConfirmationState

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        app.ctx.settings.hos_mode = "debug_off"
        driving = start_drive(app)
        stop = park_at_first_stop(driving)

        park_away_from_stops(driving, after_stop=stop)
        driving.truck.velocity_mps = 0.0
        # Stopped with no POI nearby: shoulder sleep is always an option now,
        # even rested and with HOS enforcement off -- you can choose to rest.
        app.ctx.profile.fatigue = 20.0
        reason = driving.emergency_shoulder_sleep_reason()
        assert reason is not None
        assert "pull over and rest" in reason

        # Severe fatigue escalates the wording but it was already available.
        app.ctx.profile.fatigue = hos.FATIGUE_SEVERE
        reason = driving.emergency_shoulder_sleep_reason()
        assert reason is not None
        assert "Fatigue is severe" in reason

        # Moving, it is not offered -- you cannot sleep while rolling.
        driving.truck.velocity_mps = 12.0
        assert driving.emergency_shoulder_sleep_reason() is None
        driving.truck.velocity_mps = 0.0  # back to a stop for the pause-menu check

        driving.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, PauseMenuState)
        labels = [item.text for item in app.state.items]
        assert "Emergency shoulder sleep" in labels

        select(app.state, "Emergency shoulder sleep")
        assert isinstance(app.state, ShoulderSleepConfirmationState)
        assert "poor rest" in spoken[-1]
        assert "If hours of service are enforced" in spoken[-1]

        minutes_before = driving.trip.game_minutes
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, PauseMenuState)
        assert driving.trip.game_minutes == minutes_before
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_break_only_stop_always_offers_emergency_lot_sleep(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import RestStopState

    app = App()
    try:
        driving = start_drive(app)  # fresh hours, not tired

        # A break/fuel stop (no sleeper) still offers a lot sleep -- you can
        # always choose to sleep, even with hours to spare.
        break_only = SimpleNamespace(
            name="Roadside Rest",
            at_mi=driving.trip.position_mi,
            type="rest_area",
            actions=("break", "fuel"),
            services=(),
            parking="day_only",
            exit_label="",
            spoken_name="Roadside Rest",
            parking_text="day parking",
        )
        labels = [i.text for i in RestStopState(app.ctx, driving, break_only).build_items()]
        assert "Sleep 10 hours in the lot" in labels
        assert "Emergency sleep in the lot" not in labels
        assert "Sleep 10 hours" not in labels
        assert not any("sleeper berth" in label for label in labels)

        # A sleeper stop offers the full sleep instead, not the lot fallback.
        sleeper = SimpleNamespace(
            name="Big Truck Stop",
            at_mi=driving.trip.position_mi,
            type="truck_stop",
            actions=("break", "fuel", "sleep"),
            services=(),
            parking="overnight",
            exit_label="",
            spoken_name="Big Truck Stop",
            parking_text="overnight parking",
        )
        labels = [i.text for i in RestStopState(app.ctx, driving, sleeper).build_items()]
        assert "Sleep 10 hours" in labels
        assert "Emergency sleep in the lot" not in labels
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
        driving.handle_event(key_event(pygame.K_t))  # 6 AM start: lot has room
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
        app.state.handle_event(key_event(pygame.K_RETURN))  # default career start
        app.state.handle_event(key_event(pygame.K_RETURN))  # default region
        app.state.handle_event(key_event(pygame.K_RETURN))  # home terminal
        assert isinstance(app.state, CityMenuState)
        p = app.ctx.profile
        p.hos.drive(660)  # a fully spent shift
        p.fatigue = 75.0
        before = p.game_hours
        select(app.state, "Sleep 10 hours")
        assert p.game_hours == pytest.approx(before + 10.0)
        assert p.hos.driving_min == 0.0
        assert p.hos.duty_min == 0.0
        assert p.fatigue == 0.0
    finally:
        app.shutdown()


def test_dispatch_warns_before_accepting_job_that_exceeds_current_hos(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.jobs import JobBoard
    from freight_fate.sim.hos import LIMITS
    from freight_fate.states.city import JobBoardState

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    try:
        from freight_fate.models.profile import Profile

        app.ctx.profile = Profile(name="HOS Dispatch", current_city="Austin")
        app.ctx.settings.hos_mode = "realistic"
        app.ctx.profile.current_city = "Austin"
        app.ctx.profile.hos.drive(LIMITS["realistic"][0] - 30.0)
        jobs = JobBoard(app.ctx.world, seed=2).offers("Austin", set(), level=2)
        job = next(j for j in jobs if app.ctx.world.supported_route(j.origin, j.destination))
        board = JobBoardState(app.ctx, [job])

        board._accept(job)

        assert "Hours warning" in spoken[-1]
        assert app.ctx.profile.active_trip is None

        board._accept(job)

        assert app.ctx.profile.active_trip is not None
    finally:
        app.shutdown()


def test_dispatch_board_warns_when_all_generated_jobs_exceed_current_hos(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.sim.hos import LIMITS
    from freight_fate.states.city import JobBoardState

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    try:
        from freight_fate.models.career import LEVEL_XP

        app.ctx.profile = Profile(name="All Risky", current_city="Austin")
        app.ctx.profile.career.xp = LEVEL_XP[7]  # senior: browsable board
        app.ctx.settings.hos_mode = "realistic"
        app.ctx.profile.hos.drive(LIMITS["realistic"][0] - 10.0)
        jobs = JobBoard(app.ctx.world, seed=2).offers("Austin", set(), level=2)[:5]
        assert len(jobs) == 5
        board = JobBoardState(app.ctx, jobs)

        board.announce_entry()

        assert "every listed dispatch would need an extra legal rest" in spoken[-1]
        for job in jobs:
            board._accept(job)
            assert "Hours warning" in spoken[-1]
            assert app.ctx.profile.active_trip is None

        board._accept(jobs[-1])

        assert app.ctx.profile.active_trip is not None
    finally:
        app.shutdown()


def test_dispatch_does_not_warn_after_hours_reset(monkeypatch):
    """A full 10-hour reset must clear the dispatch hours warning, even for
    multi-day runs: the route's own sleeps are budgeted into the deadline,
    so only hours already spent this shift are worth warning about."""
    from freight_fate.app import App
    from freight_fate.models.jobs import JobBoard
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import JobBoardState

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    try:
        app.ctx.profile = Profile(name="Rested", current_city="Austin")
        app.ctx.settings.hos_mode = "realistic"
        app.ctx.profile.hos.drive(600.0)  # a nearly spent shift...
        app.ctx.profile.hos.sleep()  # ...wiped by the 10-hour reset
        jobs = JobBoard(app.ctx.world, seed=2).offers("Austin", set(), level=2)[:5]
        board = JobBoardState(app.ctx, jobs)

        board.announce_entry()

        assert "extra legal rest" not in spoken[-1]

        job = next(j for j in jobs if app.ctx.world.supported_route(j.origin, j.destination))
        board._accept(job)

        assert "Hours warning" not in spoken[-1]
        assert app.ctx.profile.active_trip is not None
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
            "job": {
                "cargo": "general",
                "weight_tons": 14.0,
                "origin": "Chicago",
                "origin_location": "Cicero Rail Hub",
                "destination": "Denver",
                "distance_mi": 1150.0,
                "pay": 2800.0,
                "deadline_game_h": 31.0,
                "market_mult": 1.0,
            },
            "route_cities": ["Chicago", "St. Louis", "Kansas City", "Denver"],
            "trip_seed": 1234,
            "position_mi": 412.0,
            "game_minutes": 540.0,
            "start_damage": 3.0,
            "speeding_strikes": 1,
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
        trip = make_trip(world, start_hour=12.0, seed=5, start="Chicago", end="Indianapolis")
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

    trip = make_trip(world, start_hour=12.0, seed=5, start="Chicago", end="Indianapolis")
    trip.stops = [RoadStop("Example Scale", 10.0, "weigh_station", ("inspect",), ())]
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
        driving.truck.velocity_mps = 10.0  # rolling: counts as driving
        before = driving.hos.driving_min
        driving._update_hours_and_fatigue(1.0)  # one real second
        gained = driving.hos.driving_min - before
        # below cruise speed the clock compresses less than the configured
        # pacing, and the HOS ledger follows the same effective scale
        assert gained == pytest.approx(driving.trip.effective_time_scale / 60.0)
        assert gained < driving.trip.time_scale / 60.0

        driving.truck.velocity_mps = 27.0  # ~60 mph: full pacing
        before = driving.hos.driving_min
        driving._update_hours_and_fatigue(1.0)
        gained = driving.hos.driving_min - before
        assert gained == pytest.approx(driving.trip.time_scale / 60.0)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_players_own_parking_brake_press_arms_waiting():
    """Only the player's P press fast-forwards the wait; the auto-set brake
    at trip start must not, or pre-trip setup would burn game time."""
    from freight_fate.app import App
    from freight_fate.sim.trip import PARKED_TIME_SCALE_MULT

    app = App()
    try:
        driving = start_drive(app)
        trip = driving.trip
        truck = driving.truck
        truck.velocity_mps = 0.0
        truck.parking_brake = False

        driving._toggle_parking_brake()  # the player parks deliberately

        assert truck.parking_brake
        assert trip.waiting
        assert trip.effective_time_scale == pytest.approx(trip.time_scale * PARKED_TIME_SCALE_MULT)

        driving._toggle_parking_brake()  # trying to leave always disarms

        assert not trip.waiting
    finally:
        app.shutdown()
