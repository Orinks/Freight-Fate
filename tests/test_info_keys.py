"""On-demand driving info keys: speed limit (S), repeat (A), what's ahead (U)."""

import pygame


def key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0)


def _driving(app, origin="Buffalo", destination="Rochester"):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Info Keys", current_city=origin)
    route = app.ctx.world.supported_route(origin, destination)
    job = Job(
        CARGO_CATALOG["general"],
        12.0,
        origin,
        "company yard",
        destination,
        route.miles,
        1000.0,
        12.0,
        destination_location=f"{destination} freight market",
    )
    return DrivingState(app.ctx, job, route, phase="delivery")


def _capture(app, monkeypatch):
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True, review=True: spoken.append(text))
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


def test_speed_key_includes_cruise_set_speed_when_active(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d._cruise_mph = 55.0
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_SPACE))
        assert "automatic speed control" in spoken[-1]
        assert "cruise set at 55 miles per hour" in spoken[-1]
    finally:
        app.shutdown()


def test_speed_key_includes_speed_keeper_target_when_active(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d._keeper_mph = 15.0
        d._speed_control_target_mph = 55.0
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_SPACE))
        assert "automatic speed control" in spoken[-1]
        assert "speed keeper holding 15 miles per hour" in spoken[-1]
        assert "open-road target 55 miles per hour" in spoken[-1]
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
        d.trip.position_mi = d.trip.total_miles / 2  # out on the open road
        limit, _ = d.trip.speed_limit_at(d.trip.position_mi)
        d.truck.velocity_mps = (limit + 15) / 2.23694  # 15 mph over
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_s))
        assert "over" in spoken[-1]
    finally:
        app.shutdown()


def test_metric_speed_limit_key_reports_overage_in_metric_units(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.imperial_units = False
        d = _driving(app)
        d.trip.position_mi = d.trip.total_miles / 2
        limit, _ = d.trip.speed_limit_at(d.trip.position_mi)
        d.truck.velocity_mps = (limit + 15) / 2.23694
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_s))
        assert "kilometers per hour over" in spoken[-1]
        assert "miles per hour" not in spoken[-1]
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
        d._handle_trip_event(
            TripEvent(TripEventKind.GPS_CUE, "In 2 miles, construction ahead. Speed limit 45.")
        )
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
        d.trip.zones = [Zone(5.0, 8.0, 45.0, "construction")]
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_u))
        assert "construction" in spoken[-1]
        assert "speed limit" in spoken[-1].lower()
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
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_u))
        assert "Nothing notable" in spoken[-1]
    finally:
        app.shutdown()


def test_route_key_reports_progress_then_road_state_and_destination(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import Zone

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = 40.0
        d.trip.zones = [Zone(35.0, 45.0, 45.0, "construction")]
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_r))

        report = spoken[-1]
        # Two short sentences and nothing else: the grade, the zone, the
        # nearest named place, and the next maneuver all have their own key.
        pct = round(100 * d.trip.position_mi / d.trip.total_miles)
        assert report == (
            f"{pct} percent there, 34 miles left. "
            "On I-90 East in New York, toward Rochester, New York."
        )
    finally:
        app.shutdown()


def test_route_key_counts_down_to_a_planned_stop_instead_of_the_destination(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = 20.0
        stop = next(s for s in d.trip.stops if s.at_mi > d.trip.position_mi)
        d.trip.planned_stop_key = stop.key
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_r))

        report = spoken[-1]
        ahead = d.trip._distance_text(stop.at_mi - d.trip.position_mi)
        assert f"{ahead} to {stop.spoken_name}." in report
        assert "left." not in report
        assert "On I-90 East in New York, toward Rochester, New York." in report
    finally:
        app.shutdown()


def test_route_key_falls_back_to_the_destination_once_the_plan_is_behind(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        stop = d.trip.stops[0]
        d.trip.planned_stop_key = stop.key
        d.trip.position_mi = stop.at_mi + 1.0
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_r))

        report = spoken[-1]
        assert f"{d.trip._distance_text(d.trip.remaining_miles)} left." in report
        assert stop.spoken_name not in report
    finally:
        app.shutdown()


def test_route_key_reports_reverse_route_direction(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app, "Rochester", "Buffalo")
        d.trip.position_mi = 34.8
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_r))

        report = spoken[-1]
        assert "On I-90 West in New York, toward Buffalo, New York" in report
    finally:
        app.shutdown()


def test_clock_key_leads_with_time_then_schedule_verdict(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = 40.0
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_c))
        report = spoken[-1]
        # Time first, verdict right behind it: the first line of a braille
        # display must carry the answer, not a preamble.
        assert not report.startswith("It is")
        verdict_at = max(
            report.find("On schedule: arrival in"), report.find("Running behind: arrival in")
        )
        assert 0 < verdict_at < 60
        assert "deadline in" in report
        assert "due" in report
    finally:
        app.shutdown()


def test_terse_clock_key_drops_calendar_and_stop_planning(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.speech_verbosity = 0
        d = _driving(app)
        d.trip.position_mi = 40.0
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_c))
        terse_report = spoken[-1]
        assert "deadline in" in terse_report

        app.ctx.settings.speech_verbosity = 1
        spoken.clear()
        d.handle_event(key_event(pygame.K_c))
        assert len(terse_report) < len(spoken[-1])
        assert ", due " not in terse_report  # no appointment restatement
        assert "Next legal stop" not in terse_report
    finally:
        app.shutdown()


def test_status_menu_carries_the_drivers_board_progress_percent(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = 40.0
        pct = round(100 * d.trip.position_mi / d.trip.total_miles)
        assert f"Progress: {pct} percent there" in d.status_lines()
    finally:
        app.shutdown()


def test_upcoming_key_uses_metric_distances(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.imperial_units = False
        d = _driving(app)
        d.trip.imperial = False
        d.trip.position_mi = 20.0
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_u))

        report = spoken[-1]
        assert "kilometers" in report
        assert " miles" not in report
    finally:
        app.shutdown()


def test_route_key_uses_metric_distances(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.imperial_units = False
        d = _driving(app)
        d.trip.imperial = False
        d.trip.position_mi = 20.0
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_r))

        report = spoken[-1]
        assert "87 kilometers left." in report
        assert " miles" not in report
    finally:
        app.shutdown()
