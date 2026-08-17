"""The open scale and the rest key tell the same story.

Tester Jerry's report, 2026-08-12: the open-scale announcement ended "press T
for inspection check-in", but T while moving plans a sleep stop -- weigh
stations carry no sleep action -- so following the instruction planned a
travel center, X then armed THAT exit, and the truck crossed the scale unarmed
at speed straight into a bypass pull-over. These tests pin the fixed contract:
the announcement teaches the exit key, T near an open scale defers to the
scale instead of planning, X prefers the nearer scale over a planned sleep
stop, a short reminder fires before the bypass point, and the armed exit
stands down the moment a trooper stop begins.
"""

from __future__ import annotations

import pytest
from enforcement_helpers import open_scale_post

from freight_fate.speech_pacing import EventPriority


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Jerry", current_city="Buffalo")
    route = app.ctx.world.supported_route("Buffalo", "Rochester")
    job = Job(
        CARGO_CATALOG["general"],
        12.0,
        "Buffalo",
        "company yard",
        "Rochester",
        route.miles,
        1000.0,
        12.0,
        destination_location="Rochester freight market",
    )
    d = DrivingState(app.ctx, job, route, phase="delivery")
    d.trip.posts = []
    return d


def _with_scale(d, *, scale_mi=10.0, plaza_mi=11.0, scale_open=True):
    """An injected scale and a sleep-capable travel center just past it."""
    from freight_fate.sim.trip import RoadStop

    scale = RoadStop(
        "Ontario Scale",
        scale_mi,
        "weigh_station",
        ("inspect",),
        parking="none",
    )
    plaza = RoadStop(
        "Blue Beacon Travel Plaza",
        plaza_mi,
        "travel_center",
        ("park", "save", "fuel", "food", "break", "sleep"),
        parking="confirmed",
        exit_label="exit 55",
    )
    d.trip.stops = [scale, plaza]
    d.trip.posts = [open_scale_post(scale)] if scale_open else []
    return scale, plaza


def _capture(app, monkeypatch):
    """Record every say/say_event line plus the kwargs say_event carried."""
    spoken: list[str] = []
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(app.ctx, "say", lambda text, *a, **k: spoken.append(text))

    def _event(text, *a, **k):
        spoken.append(text)
        events.append((text, k))

    monkeypatch.setattr(app.ctx, "say_event", _event)
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    return spoken, events


# --- the announcement itself -------------------------------------------------


def test_open_scale_notice_teaches_the_exit_key_then_the_rest_key(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken, events = _capture(app, monkeypatch)
        _with_scale(d)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 45.0 / 2.23694

        d._check_weigh_station_enforcement(8.0)

        notices = [s for s in spoken if "Open weigh station ahead" in s]
        assert len(notices) == 1
        notice = notices[0]
        assert "All trucks must pull in" in notice
        assert "signal for the scale exit with X" in notice
        assert "Once you are stopped at the scale, press T to check in" in notice
        # The old instruction that planned a truck stop instead is gone.
        assert "press T for inspection check-in" not in notice
    finally:
        app.shutdown()


def test_open_scale_notice_carries_route_priority(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _, events = _capture(app, monkeypatch)
        _with_scale(d)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 45.0 / 2.23694

        d._check_weigh_station_enforcement(8.0)

        kwargs = next(k for text, k in events if "Open weigh station ahead" in text)
        assert kwargs.get("priority") is EventPriority.ROUTE
        assert kwargs.get("interrupt") is False
    finally:
        app.shutdown()


def test_scale_notice_lookahead_sample_covers_the_real_sentence():
    """The spoken lead is sized from a sample; it must not undershoot the
    real wording with a long stop name and the longest control phrases."""
    from freight_fate.input_hints import control_hint
    from freight_fate.states.driving_core import ramp_arrival_grace_seconds
    from freight_fate.states.driving_enforcement import SCALE_NOTICE_SAMPLE

    real = (
        "Open weigh station ahead in two miles: Northbound Platte River "
        "Port of Entry. All trucks must pull in. Slow below fifteen and "
        f"signal for the scale exit with {control_hint('take_exit', 'controller')}. "
        "Once you are stopped at the scale, press "
        f"{control_hint('rest', 'controller')} to check in."
    )
    assert ramp_arrival_grace_seconds(SCALE_NOTICE_SAMPLE, 0.0) >= ramp_arrival_grace_seconds(
        real, 0.0
    )


# --- the half-mile reminder --------------------------------------------------


def test_reminder_fires_once_when_still_fast_with_no_scale_exit_armed(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken, events = _capture(app, monkeypatch)
        scale, _ = _with_scale(d)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 45.0 / 2.23694
        d._check_weigh_station_enforcement(8.0)  # the one-shot notice latches

        d.trip.position_mi = 9.6
        d._check_weigh_station_enforcement(9.5)
        d.trip.position_mi = 9.7
        d._check_weigh_station_enforcement(9.6)

        # The reminder used to hard-code "half a mile" wherever inside that
        # window it fired, so at this position -- three tenths out -- it
        # overstated the road left, and against the fixed approach line it
        # read as the scale receding while the truck closed (2026-08-15).
        reminders = [s for s in spoken if s.startswith("Weigh station in ")]
        assert reminders == ["Weigh station in half a mile. Slow below fifteen for the scale."]
        kwargs = next(k for text, k in events if k and "Weigh station in " in text)
        assert kwargs.get("priority") is EventPriority.ROUTE
    finally:
        app.shutdown()


def test_reminder_speaks_the_road_actually_left(monkeypatch):
    """Fired well inside the window, it must not still claim half a mile.

    The distance was hard-coded to the threshold, so a reminder that landed
    at a couple of hundred yards overstated the road left -- and beside the
    approach line, which speaks a real short distance, the scale appeared to
    move further away as the truck closed on it (gate harness, 2026-08-15).
    """
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken, _events = _capture(app, monkeypatch)
        scale, _ = _with_scale(d)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 45.0 / 2.23694
        d._check_weigh_station_enforcement(8.0)  # latch the one-shot notice

        # Deep inside the reminder window rather than at its edge.
        d.trip.position_mi = scale.at_mi - 0.15
        d._check_weigh_station_enforcement(scale.at_mi - 0.2)

        reminders = [s for s in spoken if s.startswith("Weigh station in ")]
        assert reminders == ["Weigh station in a quarter mile. Slow below fifteen for the scale."]
    finally:
        app.shutdown()


def test_reminder_stays_quiet_once_the_scale_exit_is_armed(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken, _ = _capture(app, monkeypatch)
        scale, _ = _with_scale(d)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 45.0 / 2.23694
        d._check_weigh_station_enforcement(8.0)
        d._exit_stop = scale
        d._exit_signal_on = True

        d.trip.position_mi = 9.6
        d._check_weigh_station_enforcement(9.5)

        assert not [s for s in spoken if "half a mile" in s]
    finally:
        app.shutdown()


def test_reminder_stays_quiet_below_the_bypass_speed(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken, _ = _capture(app, monkeypatch)
        _with_scale(d)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 45.0 / 2.23694
        d._check_weigh_station_enforcement(8.0)
        d.truck.velocity_mps = 10.0 / 2.23694

        d.trip.position_mi = 9.6
        d._check_weigh_station_enforcement(9.5)

        assert not [s for s in spoken if "half a mile" in s]
    finally:
        app.shutdown()


# --- T while moving: the scale outranks rest planning (variant A) ------------


def test_rest_key_at_speed_defers_to_the_open_scale(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken, events = _capture(app, monkeypatch)
        _with_scale(d)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 54.0 / 2.23694
        state_before = app.state

        d._try_rest_stop()

        firsts = [s for s in spoken if "Weigh station first" in s]
        assert len(firsts) == 1
        line = firsts[0]
        assert "All trucks must stop" in line
        assert "signal for the scale exit with X" in line
        assert "Rest planning can wait until you are past the scale" in line
        # Queued on the event voice behind the scale warning, never over it.
        kwargs = next(k for text, k in events if "Weigh station first" in text)
        assert kwargs.get("interrupt") is False
        # Nothing was planned, selected, or opened.
        assert not [s for s in spoken if "Planned sleep stop selected" in s]
        assert d.trip.planned_stop_key is None
        assert d._selected_stop_key is None
        assert app.state is state_before
    finally:
        app.shutdown()


def test_rest_key_defer_notice_carries_route_priority(monkeypatch):
    # Regression: _scale_outranks_rest_planning called say_event with no
    # priority=, so it defaulted to AMBIENT and would_start_stale could
    # drop it silently behind the exit-lane and cruise backlog -- the "scale
    # comes first" instruction the player asked for by pressing T never
    # reaching them. Its sibling _weigh_station_reminder already passes
    # priority=EventPriority.ROUTE (see
    # test_open_scale_notice_carries_route_priority above); this line must
    # match. Invisible under the old transcript harness, which bypassed the
    # pacer entirely -- it only became visible once the harness stopped
    # doing that (task 9), which is also why the adversarial battery's
    # scale_check_in_guidance scenario went red until this fix landed.
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken, events = _capture(app, monkeypatch)
        _with_scale(d)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 54.0 / 2.23694

        d._try_rest_stop()

        kwargs = next(k for text, k in events if "Weigh station first" in text)
        assert kwargs.get("priority") is EventPriority.ROUTE
    finally:
        app.shutdown()


def test_rest_key_plans_normally_when_the_scale_is_closed(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken, _ = _capture(app, monkeypatch)
        _, plaza = _with_scale(d, scale_open=False)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 54.0 / 2.23694

        d._try_rest_stop()

        assert not [s for s in spoken if "Weigh station first" in s]
        assert [s for s in spoken if "Planned sleep stop selected" in s]
        assert d._selected_stop_key == plaza.key
    finally:
        app.shutdown()


def test_rest_key_plans_normally_when_the_scale_is_behind(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken, _ = _capture(app, monkeypatch)
        _, plaza = _with_scale(d, scale_mi=10.0, plaza_mi=12.5)
        d.trip.position_mi = 11.6  # well past the scale, plaza ahead
        d.truck.velocity_mps = 54.0 / 2.23694

        d._try_rest_stop()

        assert not [s for s in spoken if "Weigh station first" in s]
        assert d._selected_stop_key == plaza.key
    finally:
        app.shutdown()


def test_rest_key_police_stop_guard_still_outranks_the_scale(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken, _ = _capture(app, monkeypatch)
        _with_scale(d)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 54.0 / 2.23694
        d._pull_over = "lights"

        d._try_rest_stop()

        assert [s for s in spoken if "Resolve the police stop" in s]
        assert not [s for s in spoken if "Weigh station first" in s]
    finally:
        app.shutdown()


def test_rest_key_ignores_the_scale_in_a_casual_hos_mode(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken, _ = _capture(app, monkeypatch)
        _, plaza = _with_scale(d)
        app.ctx.settings.hos_mode = "debug_off"
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 54.0 / 2.23694

        d._try_rest_stop()

        assert not [s for s in spoken if "Weigh station first" in s]
        assert d._selected_stop_key == plaza.key
    finally:
        app.shutdown()


# --- X: the nearer open scale claims the exit (variant B) --------------------


def test_exit_key_prefers_the_nearer_open_scale_over_the_planned_stop(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken, _ = _capture(app, monkeypatch)
        scale, plaza = _with_scale(d)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 54.0 / 2.23694
        # A sleep stop planned earlier, before the scale entered the picture.
        d.trip.planned_stop_key = plaza.key
        d._selected_stop_key = plaza.key

        d._take_exit()

        assert d._exit_signal_on is True
        assert d._exit_stop is not None and d._exit_stop.key == scale.key
        claim = next(s for s in spoken if "Signal on for the scale exit" in s)
        assert "Ontario Scale" in claim
        assert "Your planned sleep stop waits until you are past the scale" in claim
    finally:
        app.shutdown()


def test_exit_key_leaves_a_nearer_selected_stop_alone(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken, _ = _capture(app, monkeypatch)
        scale, plaza = _with_scale(d, scale_mi=11.0, plaza_mi=10.0)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 54.0 / 2.23694
        d.trip.planned_stop_key = plaza.key
        d._selected_stop_key = plaza.key

        d._take_exit()

        assert d._exit_stop is not None and d._exit_stop.key == plaza.key
        assert not [s for s in spoken if "Signal on for the scale exit" in s]
    finally:
        app.shutdown()


def test_crossing_with_the_scale_exit_armed_is_not_charged_at_the_gore(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _capture(app, monkeypatch)
        scale, _ = _with_scale(d)
        d._exit_stop = scale
        d._exit_signal_on = True
        d.trip.position_mi = 10.1
        d.truck.velocity_mps = 18.0 / 2.23694

        d._check_weigh_station_enforcement(9.9)

        assert d._pull_over is None
        assert d._weigh_station_pending is scale
    finally:
        app.shutdown()


# --- the pull-over owns the road: the armed exit stands down -----------------


def test_pull_over_stands_down_the_armed_exit(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        # A bypass is caught, not certain (85 percent) -- seed 1 lands under
        # that chance for this exact scale key, so the stop is deterministic.
        d.trip_seed = 1
        spoken, _ = _capture(app, monkeypatch)
        scale, plaza = _with_scale(d)
        d.trip.position_mi = 10.1
        d.truck.velocity_mps = 54.0 / 2.23694
        d._exit_stop = plaza
        d._exit_signal_on = True
        d._cruise_exit_mph = 40.0

        d._charge_weigh_station_bypass(scale)

        assert d._pull_over == "lights"
        assert d._exit_stop is None
        assert d._exit_signal_on is False
        assert d._cruise_exit_mph is None
        assert [s for s in spoken if "Exit approach canceled" in s]
    finally:
        app.shutdown()


def test_pull_over_with_no_armed_exit_says_nothing_about_exits(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.trip_seed = 1  # lands under the 85 percent catch chance; see above
        spoken, _ = _capture(app, monkeypatch)
        scale, _ = _with_scale(d)
        d.trip.position_mi = 10.1
        d.truck.velocity_mps = 54.0 / 2.23694

        d._charge_weigh_station_bypass(scale)

        assert d._pull_over == "lights"
        assert not [s for s in spoken if "Exit approach canceled" in s]
    finally:
        app.shutdown()


# --- T at the scale: the nearest stop wins -----------------------------------


def test_nearest_stop_within_returns_the_nearest_not_the_first_listed(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _capture(app, monkeypatch)
        scale, plaza = _with_scale(d, scale_mi=10.4, plaza_mi=10.0)
        # The plaza is listed after the scale but sits first on the road; from
        # just short of the scale, the scale is the nearest stop.
        d.trip.stops = [plaza, scale]
        d.trip.position_mi = 10.35

        nearest = d.trip.nearest_stop_within()

        assert nearest is not None and nearest.key == scale.key
    finally:
        app.shutdown()


def test_rest_key_stopped_at_the_scale_opens_the_scale_menu(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_rest_states import RestStopState

    app = App()
    try:
        d = _driving(app)
        _capture(app, monkeypatch)
        scale, plaza = _with_scale(d, scale_mi=10.0, plaza_mi=10.6)
        d.trip.stops = [plaza, scale]  # plaza listed first, scale nearer
        d.trip.position_mi = 10.05
        d.truck.velocity_mps = 0.0

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(app.ctx, "push_state", lambda state: setattr(app, "_pushed", state))
            d._try_rest_stop()

        pushed = getattr(app, "_pushed", None)
        assert isinstance(pushed, RestStopState)
        assert pushed.stop.key == scale.key
    finally:
        app.shutdown()
