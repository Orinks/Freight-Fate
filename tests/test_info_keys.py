"""On-demand driving info keys: speed limit (S), repeat (A), what's ahead (U)."""

import pygame


def key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode="")


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Info Keys", current_city="Buffalo")
    route = app.ctx.world.supported_route("Buffalo", "Rochester")
    job = Job(CARGO_CATALOG["general"], 12.0, "Buffalo", "company yard",
              "Rochester", route.miles, 1000.0, 12.0,
              destination_location="Rochester freight market")
    return DrivingState(app.ctx, job, route, phase="delivery")


def _capture(app, monkeypatch):
    spoken = []
    monkeypatch.setattr(app.ctx, "say",
                        lambda text, interrupt=True: spoken.append(text))
    return spoken


def test_speed_limit_key_reads_the_posted_limit(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_s))
        assert "Speed limit" in spoken[-1]
        assert "per hour" in spoken[-1]
    finally:
        app.shutdown()


def test_weather_key_reads_safe_speed_in_metric_units(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.imperial_units = False
        d = _driving(app)
        from freight_fate.sim.weather import WeatherKind

        d.weather.current = WeatherKind.RAIN
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_v))
        assert "Safe speed about 89 kilometers per hour" in spoken[-1]
    finally:
        app.shutdown()


def test_speed_limit_key_reports_how_far_over_you_are(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = d.trip.total_miles / 2   # out on the open road
        limit, _ = d.trip.speed_limit_at(d.trip.position_mi)
        d.truck.velocity_mps = (limit + 15) / 2.23694   # 15 mph over
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_s))
        assert "over" in spoken[-1]
    finally:
        app.shutdown()


def test_repeat_key_replays_the_last_route_announcement(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    try:
        d = _driving(app)
        spoken = _capture(app, monkeypatch)
        # Nothing announced yet.
        d.handle_event(key_event(pygame.K_a))
        assert "No recent announcement" in spoken[-1]
        # After a route announcement, A replays it verbatim.
        d._handle_trip_event(TripEvent(
            TripEventKind.GPS_CUE,
            "Brake now! In 2 miles, construction ahead. Merge left for the "
            "flagger taper; speed limit 55, then 45 through the work zone."))
        spoken.clear()
        d.handle_event(key_event(pygame.K_a))
        assert "construction ahead" in spoken[-1]
    finally:
        app.shutdown()


def test_upcoming_key_reports_an_imposed_limit_ahead(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import Zone

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = 0.0
        d.trip.zones = [
            Zone(5.0, 6.0, 55.0, "construction merge"),
            Zone(6.0, 8.0, 45.0, "construction"),
        ]
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_u))
        assert "construction taper" in spoken[-1]
        assert "merge left" in spoken[-1]
        assert "speed limit 55" in spoken[-1]
        assert "then work zone 45" in spoken[-1]
    finally:
        app.shutdown()


def test_upcoming_key_reports_cb_patrol_ahead(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import PatrolWindow

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = 4.0
        d.trip.zones = []
        d.trip.stops = []
        d.trip.navigation_cues = []
        d.trip.patrols = [PatrolWindow(10.0, 14.0, 0.8, "highway enforcement")]
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_u))

        assert "CB chatter reports a bear ahead" in spoken[-1]
    finally:
        app.shutdown()


def test_upcoming_key_handles_a_clear_road(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = 0.0
        d.trip.zones = []
        d.trip.stops = []
        d.trip.navigation_cues = []
        d.trip.patrols = []
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_u))
        assert "Nothing notable" in spoken[-1]
    finally:
        app.shutdown()
