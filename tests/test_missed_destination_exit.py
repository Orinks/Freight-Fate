"""Missed destination-exit recovery, including unlabeled US-highway finishes."""

from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive
from speech_capture import speech_stub


def _miss_destination_exit(driving):
    driving.trip.position_mi = driving.trip.total_miles
    driving.trip.finished = True
    driving.truck.velocity_mps = 20.0
    driving.update(1 / 60)


def test_missing_exit_details_still_recovers(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(driving, "_destination_exit_details", lambda *a, **k: None)
        stop = driving._destination_exit_stop()
        assert stop is not None

        for _ in range(2):
            missed_from = driving.trip.total_miles
            _miss_destination_exit(driving)

            assert isinstance(app.state, DrivingState)
            assert not driving.trip.finished
            assert driving.trip.position_mi < missed_from
            assert driving.trip.position_mi < stop.at_mi
            retry = driving._destination_exit_stop()
            assert retry is not None
            assert retry.at_mi > driving.trip.position_mi + 0.05
            assert "missed the destination exit" in events[-1].lower()
            assert "cannot find a safe turnaround" not in events[-1].lower()
            assert "ahead again" in events[-1].lower()
    finally:
        app.shutdown()


def test_hattiesburg_style_missed_destination_exit_moves_the_trip(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    try:
        app.ctx.profile = Profile(name="Hattiesburg Miss", current_city="gulfport_ms_us")
        route = app.ctx.world.supported_route("gulfport_ms_us", "hattiesburg_ms_us")
        assert route is not None
        assert route.cities[-1] == "hattiesburg_ms_us"
        assert not route.legs[-1].interchanges

        job = Job(
            CARGO_CATALOG["general"],
            12.0,
            "gulfport_ms_us",
            "company yard",
            "hattiesburg_ms_us",
            route.miles,
            1000.0,
            12.0,
            destination_location="Hattiesburg freight market",
        )
        driving = DrivingState(app.ctx, job, route, phase="delivery")
        quiet_trip(driving)
        release_air_brakes(driving)

        assert driving._destination_exit_details(include_past=True) is None
        stop = driving._destination_exit_stop()
        assert stop is not None

        missed_from = driving.trip.total_miles
        _miss_destination_exit(driving)

        assert not driving.trip.finished
        assert driving.trip.position_mi < missed_from
        assert driving.trip.position_mi < stop.at_mi
        spoken = events[-1].lower()
        assert "missed the destination exit" in spoken
        assert "dispatch reroutes you" not in spoken
        assert "ahead again" in spoken
        retry = driving._destination_exit_stop()
        assert retry is not None
        assert retry.at_mi - driving.trip.position_mi >= 5.0
    finally:
        app.shutdown()


def test_unrecoverable_miss_fails_honestly(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(driving, "_destination_exit_details", lambda *a, **k: None)
        monkeypatch.setattr(driving, "_synthetic_destination_exit_mi", lambda: 0.0)

        missed_from = driving.trip.total_miles
        _miss_destination_exit(driving)

        assert isinstance(app.state, DrivingState)
        assert driving.trip.position_mi == missed_from
        assert "cannot find a safe turnaround" in events[-1].lower()
        assert "ahead again" not in events[-1].lower()
    finally:
        app.shutdown()


def test_hattiesburg_recover_resumes_speeding_callout(monkeypatch):
    """After a clean US-49 miss-and-recover, 89 mph on the 65 limit speaks."""
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import SPEEDING_HOLD_S, DrivingState

    app = App()
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    try:
        app.ctx.profile = Profile(name="Hattiesburg Speed", current_city="gulfport_ms_us")
        route = app.ctx.world.supported_route("gulfport_ms_us", "hattiesburg_ms_us")
        assert route is not None
        job = Job(
            CARGO_CATALOG["general"],
            12.0,
            "gulfport_ms_us",
            "company yard",
            "hattiesburg_ms_us",
            route.miles,
            1000.0,
            12.0,
            destination_location="Hattiesburg freight market",
        )
        driving = DrivingState(app.ctx, job, route, phase="delivery")
        quiet_trip(driving)
        release_air_brakes(driving)

        _miss_destination_exit(driving)

        assert not driving.trip.finished
        assert not driving._missed_destination_exit_said
        assert not driving._destination_exit_taken
        limit, reason = driving.trip.speed_limit_at(driving.trip.position_mi)
        assert reason is None
        assert limit == 65.0
        assert driving.trip.active_patrol_at(driving.trip.position_mi) is None

        driving.truck.velocity_mps = 89.0 / 2.23694
        driving._update_speeding(SPEEDING_HOLD_S + 1.0)

        assert driving.speeding_strikes == 1
        assert driving._pull_over is None
        assert "speeding strike" in events[-1].lower()
        assert "65 miles per hour" in events[-1].lower()
    finally:
        app.shutdown()


def test_unrecoverable_miss_does_not_issue_gate_speed_strikes(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import SPEEDING_HOLD_S, DrivingState

    app = App()
    events = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        monkeypatch.setattr(driving, "_destination_exit_details", lambda *a, **k: None)
        monkeypatch.setattr(driving, "_synthetic_destination_exit_mi", lambda: 0.0)

        missed_from = driving.trip.total_miles
        _miss_destination_exit(driving)

        assert isinstance(app.state, DrivingState)
        assert driving.trip.position_mi == missed_from
        assert driving._missed_destination_exit_said
        driving.truck.velocity_mps = 89.0 / 2.23694
        driving._update_speeding(SPEEDING_HOLD_S + 1.0)

        assert driving.speeding_strikes == 0
        assert driving._pull_over is None
        assert not any("speeding strike" in event.lower() for event in events)
    finally:
        app.shutdown()

