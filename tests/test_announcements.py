"""Announcement priority (safety preempts chatter) and speed-scaled lead time."""

import pygame
import pytest

from freight_fate.sim.trip import TripEvent, TripEventKind, Zone


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Cues", current_city="Buffalo")
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
    return DrivingState(app.ctx, job, route, phase="delivery")


def test_safety_cues_are_critical_and_chatter_is_not():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        zone = Zone(5.0, 8.0, 45.0, "construction")

        class _Cue:
            kind = "traffic"

        assert d._is_critical_event(TripEvent(TripEventKind.HAZARD, "Brake now!"))
        assert d._is_critical_event(TripEvent(TripEventKind.ZONE_ENTER, "zone", {"zone": zone}))
        assert d._is_critical_event(
            TripEvent(TripEventKind.GPS_CUE, "construction ahead", {"zone": zone})
        )
        assert d._is_critical_event(
            TripEvent(TripEventKind.GPS_CUE, "traffic ahead", {"cue": _Cue()})
        )
        # Ambient chatter is not critical.
        assert not d._is_critical_event(
            TripEvent(TripEventKind.GPS_CUE, "CB radio: patrol ahead", {"cb_patrol": object()})
        )
        assert not d._is_critical_event(TripEvent(TripEventKind.WEATHER_CHANGE, "rain"))
        assert not d._is_critical_event(TripEvent(TripEventKind.TOLL_CHARGED, "toll"))
        assert not d._is_critical_event(TripEvent(TripEventKind.GPS_CUE, "exit ahead"))
    finally:
        app.shutdown()


def test_terse_drive_entry_skips_startup_handholding(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        app.ctx.settings.speech_verbosity = 0
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))

        d.enter()

        assert spoken
        entry = spoken[0]
        assert "Press" not in entry
        assert "F1" not in entry
        assert "air" in entry
        assert "parking brake" in entry
    finally:
        app.shutdown()


def test_cold_start_low_air_does_not_stack_on_entry(monkeypatch):
    from freight_fate.app import App

    app = App()
    events = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))

        assert d.truck.air_low_warning
        assert d._low_air_said
        d.truck.start_engine()
        d._update_air_brake_announcements(was_ready=False, was_low=True, was_spring=True)

        assert events == []
    finally:
        app.shutdown()


def test_horn_loops_while_key_is_held():
    from freight_fate.app import App

    class Recorder:
        def __init__(self) -> None:
            self.calls = []

        def horn_start(self) -> None:
            self.calls.append("start")

        def horn_stop(self) -> None:
            self.calls.append("stop")

        def play(self, *_args, **_kwargs) -> None:
            pass

        def stop_world(self) -> None:
            pass

    app = App()
    try:
        d = _driving(app)
        audio = Recorder()
        app.ctx.audio = audio

        d.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_h, unicode="h"))
        d.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_h, unicode="h"))

        assert audio.calls == ["start", "stop"]

        d.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_h, unicode="h"))
        d.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode=""))
        assert audio.calls[-2:] == ["start", "stop"]
    finally:
        app.shutdown()


def test_zone_warning_interrupts_while_weather_chatter_queues(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        calls = []
        monkeypatch.setattr(
            app.ctx, "say_event", lambda text, interrupt=True: calls.append((text, interrupt))
        )
        zone = Zone(5.0, 8.0, 45.0, "construction")

        d._handle_trip_event(
            TripEvent(
                TripEventKind.GPS_CUE,
                "Brake now! In 2 miles, construction ahead. Merge left for the "
                "flagger taper; speed limit 55, then 45 through the work zone.",
                {"zone": zone},
            )
        )
        assert calls[-1][1] is True  # the warning preempts whatever is talking

        d._handle_trip_event(TripEvent(TripEventKind.WEATHER_CHANGE, "Weather: rain."))
        assert calls[-1][1] is False  # ambient chatter yields and queues
    finally:
        app.shutdown()


def test_curve_callout_setting_controls_the_single_automatic_announcement(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        calls = []
        monkeypatch.setattr(
            app.ctx, "say_event", lambda text, interrupt=True: calls.append((text, interrupt))
        )
        monkeypatch.setattr(app.ctx.audio, "play", lambda *args, **kwargs: None)
        event = TripEvent(
            TripEventKind.CURVE,
            "Sharp curve left, half a mile, advisory 35.",
            {"advisory_mph": 35},
        )

        d._handle_trip_event(event)
        # Curve calls interrupt: queued behind chatter they arrived with the
        # bend seconds away (owner's AZ-260 log, 2026-07-19).
        assert calls == [(event.message, True)]

        app.ctx.settings.curve_callouts = False
        d._handle_trip_event(event)
        assert calls == [(event.message, True)]
    finally:
        app.shutdown()


def test_cb_radio_chatter_queues_and_uses_cb_audio(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import PatrolWindow

    app = App()
    try:
        d = _driving(app)
        calls = []
        sounds = []
        monkeypatch.setattr(
            app.ctx, "say_event", lambda text, interrupt=True: calls.append((text, interrupt))
        )
        monkeypatch.setattr(app.ctx.audio, "play", lambda key, **kwargs: sounds.append(key))

        d._handle_trip_event(
            TripEvent(
                TripEventKind.GPS_CUE,
                "CB chatter in 5 miles: drivers report a bear ahead. "
                "Ease back and check your speed.",
                {"cb_patrol": PatrolWindow(10.0, 14.0, 0.8, "highway enforcement")},
            )
        )

        assert sounds[-1] == "events/cb_radio_chatter"
        assert calls[-1][1] is False
    finally:
        app.shutdown()


def test_truly_ambient_chatter_is_spaced_without_blocking_safety(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import PatrolWindow
    from freight_fate.states.driving import AMBIENT_EVENT_SPACING_S

    app = App()
    try:
        d = _driving(app)
        calls = []
        monkeypatch.setattr(
            app.ctx, "say_event", lambda text, interrupt=True: calls.append((text, interrupt))
        )
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)

        d._handle_trip_event(TripEvent(TripEventKind.WEATHER_CHANGE, "Weather: rain."))
        d._handle_trip_event(
            TripEvent(
                TripEventKind.GPS_CUE,
                "CB chatter in 5 miles: drivers report a bear ahead.",
                {"cb_patrol": PatrolWindow(10.0, 14.0, 0.8, "highway enforcement")},
            )
        )
        d._handle_trip_event(TripEvent(TripEventKind.GPS_CUE, "Exit 12 ahead."))

        assert calls == [("Weather: rain.", False), ("Exit 12 ahead.", False)]

        d._handle_trip_event(TripEvent(TripEventKind.HAZARD, "Brake now! Debris."))
        assert calls[-1] == ("Brake now! Debris.", True)

        d._update_ambient_events(AMBIENT_EVENT_SPACING_S)
        assert calls[-1] == ("Brake now! Debris.", True)

        d._hazard_deadline = None
        d._handle_trip_event(
            TripEvent(
                TripEventKind.GPS_CUE,
                "CB chatter in 4 miles: drivers report a bear ahead.",
                {"cb_patrol": PatrolWindow(11.0, 14.0, 0.8, "highway enforcement")},
            )
        )
        d._update_ambient_events(AMBIENT_EVENT_SPACING_S)
        assert calls[-1] == ("CB chatter in 4 miles: drivers report a bear ahead.", False)
    finally:
        app.shutdown()


def test_departure_merge_cue_is_emitted_before_the_stop_notice(world):
    """Regression: at departure the travel-plaza notice used to be emitted
    ahead of the onramp merge cue, so the one actionable instruction was the
    last thing queued on the event voice."""
    from test_weather_trip import make_trip

    from freight_fate.sim.trip_models import RoadStop

    trip, _truck = make_trip(world)
    trip.stops = [RoadStop("Test Travel Plaza", 1.0)]
    trip._announced_stops = set()
    events = trip.update(1 / 60)

    kinds = [
        "merge" if getattr(e.data.get("cue"), "kind", "") == "onramp" else e.kind.value
        for e in events
        if e.kind in (TripEventKind.GPS_CUE, TripEventKind.STOP_AHEAD)
    ]
    assert "merge" in kinds
    assert "stop_ahead" in kinds
    assert kinds.index("merge") < kinds.index("stop_ahead")


def test_stop_notice_yields_to_recent_route_speech(monkeypatch):
    """A travel-plaza notice right after a spoken navigation line queues
    behind the spacing window instead of stacking on the instruction."""
    from freight_fate.app import App
    from freight_fate.sim.driving_modes import tuning_for_time_scale

    app = App()
    try:
        d = _driving(app)
        calls = []
        monkeypatch.setattr(
            app.ctx, "say_event", lambda text, interrupt=True: calls.append((text, interrupt))
        )
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)

        merge = "Merge onto I-90 East toward South Bend; 66 miles."
        plaza = "service plaza: Petro Stopping Centers in 1 mile. Press X to signal for the exit."
        d._handle_trip_event(TripEvent(TripEventKind.GPS_CUE, merge))
        d._handle_trip_event(TripEvent(TripEventKind.STOP_AHEAD, plaza))
        assert [text for text, _ in calls] == [merge]  # the plaza notice waits

        d._update_ambient_events(tuning_for_time_scale(d.trip.time_scale).ambient_spacing_s)
        assert calls[-1] == (plaza, False)  # and speaks once the window clears
    finally:
        app.shutdown()


def test_ambient_chatter_waits_while_hazard_is_active(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import AMBIENT_EVENT_SPACING_S

    app = App()
    try:
        d = _driving(app)
        calls = []
        monkeypatch.setattr(
            app.ctx, "say_event", lambda text, interrupt=True: calls.append((text, interrupt))
        )

        d._hazard_deadline = 5.0
        d._handle_trip_event(TripEvent(TripEventKind.WEATHER_CHANGE, "Weather: rain."))
        assert calls == []

        d._update_ambient_events(AMBIENT_EVENT_SPACING_S)
        assert calls == []

        d._hazard_deadline = None
        d._update_ambient_events(0.0)
        assert calls == [("Weather: rain.", False)]
    finally:
        app.shutdown()


def test_critical_zone_clears_pending_ambient_chatter(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import AMBIENT_EVENT_SPACING_S

    app = App()
    try:
        d = _driving(app)
        calls = []
        monkeypatch.setattr(
            app.ctx, "say_event", lambda text, interrupt=True: calls.append((text, interrupt))
        )
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)

        d._handle_trip_event(TripEvent(TripEventKind.WEATHER_CHANGE, "Weather: rain."))
        d._handle_trip_event(TripEvent(TripEventKind.STATE_CROSSING, "Crossing Ohio."))
        assert calls == [("Weather: rain.", False)]

        zone = Zone(5.0, 8.0, 45.0, "construction")
        d._handle_trip_event(
            TripEvent(
                TripEventKind.ZONE_ENTER,
                "Construction ahead. Speed limit 45.",
                {"zone": zone},
            )
        )
        assert calls[-1] == ("Construction ahead. Speed limit 45.", True)

        d._update_ambient_events(AMBIENT_EVENT_SPACING_S)
        assert calls[-1] == ("Construction ahead. Speed limit 45.", True)
    finally:
        app.shutdown()


def test_zone_warning_lead_scales_with_speed_and_pacing():
    from freight_fate.app import App
    from freight_fate.sim.trip import (
        ZONE_WARNING_LOOKAHEAD_MI,
        ZONE_WARNING_MAX_MI,
        ZONE_WARNING_REAL_S,
    )

    app = App()
    try:
        d = _driving(app)
        d.trip.time_scale = 20.0

        d.truck.velocity_mps = 0.0  # crawling -> the minimum base lead
        crawl = d.trip._zone_warning_lookahead_mi()
        assert crawl == pytest.approx(ZONE_WARNING_LOOKAHEAD_MI)

        d.truck.velocity_mps = 70 / 2.23694  # highway speed -> more warning
        fast = d.trip._zone_warning_lookahead_mi()
        expected = ZONE_WARNING_REAL_S * 70.0 * d.trip.time_scale / 3600.0
        assert fast == pytest.approx(expected, abs=0.05)
        assert fast <= ZONE_WARNING_MAX_MI

        d.trip.time_scale = 40.0  # faster pacing compresses time -> even more lead
        faster = d.trip._zone_warning_lookahead_mi()
        assert faster >= fast
        assert faster == pytest.approx(ZONE_WARNING_MAX_MI)
    finally:
        app.shutdown()
