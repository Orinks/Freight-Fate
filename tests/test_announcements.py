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
                "In 2 miles, construction ahead. Speed limit 45.",
                {"zone": zone},
            )
        )
        assert calls[-1][1] is True  # the warning preempts whatever is talking

        d._handle_trip_event(TripEvent(TripEventKind.WEATHER_CHANGE, "Weather: rain."))
        assert calls[-1][1] is False  # ambient chatter yields and queues
    finally:
        app.shutdown()


def test_zone_warning_lead_scales_with_speed_and_pacing():
    from freight_fate.app import App
    from freight_fate.sim.trip import ZONE_WARNING_LOOKAHEAD_MI, ZONE_WARNING_MAX_MI

    app = App()
    try:
        d = _driving(app)
        d.trip.time_scale = 20.0

        d.truck.velocity_mps = 0.0  # crawling -> the minimum base lead
        crawl = d.trip._zone_warning_lookahead_mi()
        assert crawl == pytest.approx(ZONE_WARNING_LOOKAHEAD_MI)

        d.truck.velocity_mps = 70 / 2.23694  # highway speed -> more warning
        fast = d.trip._zone_warning_lookahead_mi()
        assert fast > crawl
        assert fast <= ZONE_WARNING_MAX_MI

        d.trip.time_scale = 40.0  # faster pacing compresses time -> even more lead
        faster = d.trip._zone_warning_lookahead_mi()
        assert faster >= fast
    finally:
        app.shutdown()
