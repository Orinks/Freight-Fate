"""Announcement priority (safety preempts chatter) and speed-scaled lead time."""

import pytest

from freight_fate.sim.trip import TripEvent, TripEventKind, Zone


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Cues", current_city="Buffalo")
    route = app.ctx.world.supported_route("Buffalo", "Rochester")
    job = Job(CARGO_CATALOG["general"], 12.0, "Buffalo", "company yard",
              "Rochester", route.miles, 1000.0, 12.0,
              destination_location="Rochester freight market")
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
            TripEvent(TripEventKind.GPS_CUE, "construction ahead", {"zone": zone}))
        assert d._is_critical_event(
            TripEvent(TripEventKind.GPS_CUE, "traffic ahead", {"cue": _Cue()}))
        # Ambient chatter is not critical.
        assert not d._is_critical_event(
            TripEvent(TripEventKind.GPS_CUE, "CB radio: patrol ahead",
                      {"cb_patrol": object()}))
        assert not d._is_critical_event(TripEvent(TripEventKind.WEATHER_CHANGE, "rain"))
        assert not d._is_critical_event(TripEvent(TripEventKind.TOLL_CHARGED, "toll"))
        assert not d._is_critical_event(TripEvent(TripEventKind.GPS_CUE, "exit ahead"))
    finally:
        app.shutdown()


def test_zone_warning_interrupts_while_weather_chatter_queues(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        calls = []
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: calls.append((text, interrupt)))
        zone = Zone(5.0, 8.0, 45.0, "construction")

        d._handle_trip_event(TripEvent(
            TripEventKind.GPS_CUE,
            "Brake now! In 2 miles, construction ahead. Speed limit 45.",
            {"zone": zone}))
        assert calls[-1][1] is True   # the warning preempts whatever is talking

        d._handle_trip_event(TripEvent(TripEventKind.WEATHER_CHANGE, "Weather: rain."))
        assert calls[-1][1] is False  # ambient chatter yields and queues
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
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: calls.append((text, interrupt)))
        monkeypatch.setattr(app.ctx.audio, "play",
                            lambda key, **kwargs: sounds.append(key))

        d._handle_trip_event(TripEvent(
            TripEventKind.GPS_CUE,
            "CB radio reports a trooper ahead in 5 miles on this speed trap. "
            "Check your speed.",
            {"cb_patrol": PatrolWindow(10.0, 14.0, 0.8, "speed trap")},
        ))

        assert sounds[-1] == "events/cb_radio_chatter"
        assert calls[-1][1] is False
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

        d.truck.velocity_mps = 0.0   # crawling -> the minimum base lead
        crawl = d.trip._zone_warning_lookahead_mi()
        assert crawl == pytest.approx(ZONE_WARNING_LOOKAHEAD_MI)

        d.truck.velocity_mps = 70 / 2.23694   # highway speed -> more warning
        fast = d.trip._zone_warning_lookahead_mi()
        expected = ZONE_WARNING_REAL_S * 70.0 * d.trip.time_scale / 3600.0
        assert fast == pytest.approx(expected, abs=0.05)
        assert fast <= ZONE_WARNING_MAX_MI

        d.trip.time_scale = 40.0   # faster pacing compresses time -> even more lead
        faster = d.trip._zone_warning_lookahead_mi()
        assert faster >= fast
        assert faster == pytest.approx(ZONE_WARNING_MAX_MI)
    finally:
        app.shutdown()
