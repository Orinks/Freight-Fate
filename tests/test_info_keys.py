"""On-demand driving info keys: speed limit (S), repeat (A), what's ahead (U)."""

import pygame
from speech_capture import speech_stub


def key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0)


def _driving(
    app,
    origin="Buffalo",
    destination="Rochester",
    origin_location="company yard",
):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Info Keys", current_city=origin)
    route = app.ctx.world.supported_route(origin, destination)
    job = Job(
        CARGO_CATALOG["general"],
        12.0,
        origin,
        origin_location,
        destination,
        route.miles,
        1000.0,
        12.0,
        destination_location=f"{destination} freight market",
    )
    return DrivingState(app.ctx, job, route, phase="delivery")


def _capture(app, monkeypatch):
    spoken = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
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
            TripEvent(
                TripEventKind.GPS_CUE,
                "Brake now! In 2 miles, construction ahead. Merge left for the "
                "flagger taper; speed limit 55, then 45 through the work zone.",
            )
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
        d.trip.zones = [
            Zone(5.0, 6.0, 55.0, "construction merge", closed_side="right"),
            Zone(6.0, 8.0, 45.0, "construction", closed_side="right"),
        ]
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_u))
        assert "construction taper" in spoken[-1]
        assert "right lane closed, merge left" in spoken[-1]
        assert "speed limit 55" in spoken[-1]
        # "construction zone" is the canonical spoken noun (docs/ontology.md).
        assert "then construction zone 45" in spoken[-1]

        # The readout used to say "merge left" whatever was shut, so on a
        # left-lane closure it sent the driver into the cones.
        d.trip.zones = [
            Zone(5.0, 6.0, 55.0, "construction merge", closed_side="left"),
            Zone(6.0, 8.0, 45.0, "construction", closed_side="left"),
        ]
        spoken.clear()
        d.handle_event(key_event(pygame.K_u))
        assert "left lane closed, merge right" in spoken[-1]

        # Roadwork with every lane open must not invent a merge either.
        d.trip.zones = [
            Zone(5.0, 6.0, 55.0, "construction merge"),
            Zone(6.0, 8.0, 45.0, "construction"),
        ]
        spoken.clear()
        d.handle_event(key_event(pygame.K_u))
        assert "all lanes open" in spoken[-1]
        assert "merge" not in spoken[-1]
    finally:
        app.shutdown()


def test_upcoming_key_never_reports_enforcement(monkeypatch):
    """U is the road, not the police (owner ruling, 2026-08-15).

    Enforcement heads-ups still reach the player on the CB; this key does
    not recite them in any hours-of-service mode, enforced or not.
    """
    from enforcement_helpers import always_observing_post

    from freight_fate.app import App
    from freight_fate.sim import hos

    app = App()
    try:
        d = _driving(app)
        for mode in ("realistic", "relaxed", "debug_off"):
            app.ctx.settings.hos_mode = mode
            d.trip.position_mi = 4.0
            d.trip.posts = [always_observing_post(at_mi=6.0, reach_mi=4.0)]
            spoken = _capture(app, monkeypatch)

            d.handle_event(key_event(pygame.K_u))

            report = spoken[-1].lower()
            assert d.trip.next_patrol_within(15.0) is not None, mode
            for word in ("enforcement", "patrol", "trooper", "police", "bear"):
                assert word not in report, (mode, word, report)
        assert hos.HOS_NON_ENFORCED_MODES  # the branch that used to gate this
    finally:
        app.shutdown()


def test_upcoming_key_does_not_repeat_the_next_exit_key(monkeypatch):
    """Shift+R is the listed-exit key, word for word; U stopped echoing it."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = 4.0
        d.trip.zones = []
        d.trip.stops = []
        d.trip.curves = ()
        cue = d.trip.next_exit_cue()
        assert cue is not None, "route has no listed exit to echo"
        d.trip.position_mi = max(0.0, cue.at_mi - 5.0)
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_u))

        assert cue.text not in spoken[-1]
    finally:
        app.shutdown()


def test_upcoming_key_leads_with_the_ramp_light(monkeypatch):
    """The stop bar is the nearest thing on a signal-controlled ramp."""
    from freight_fate.app import App
    from freight_fate.sim.trip import Zone

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = 4.0
        d.trip.zones = [Zone(5.0, 8.0, 45.0, "construction")]
        d._ramp_mi = 0.4
        d._ramp_control = "signal"
        d._ramp_terminal_done = False
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_u))

        report = spoken[-1]
        assert report.startswith("Coming up: light ")
        assert "stop bar" in report
        # The zone still follows it; the light only takes the lead.
        assert report.index("stop bar") < report.index("construction")
    finally:
        app.shutdown()


def test_upcoming_key_stays_a_couple_of_sentences(monkeypatch):
    """Everything at once is still four clauses, not the old paragraph."""
    from enforcement_helpers import always_observing_post

    from freight_fate.app import App
    from freight_fate.sim.trip import Zone

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = 4.0
        d.trip.zones = [
            Zone(5.0, 6.0, 55.0, "construction merge", closed_side="right"),
            Zone(6.0, 8.0, 45.0, "construction", closed_side="right"),
        ]
        d.trip.posts = [always_observing_post(at_mi=6.0, reach_mi=4.0)]
        d._ramp_mi = 0.4
        d._ramp_control = "signal"
        d._ramp_terminal_done = False
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_u))

        from freight_fate.states.driving_controls import UPCOMING_MAX_CLAUSES

        report = spoken[-1]
        assert report.count(". ") + 1 <= UPCOMING_MAX_CLAUSES, report
        # The traffic-pressure clause restated the taper beside it.
        assert "move left and target" not in report, report
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
        d.trip.curves = ()
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_u))
        assert "Nothing notable" in spoken[-1]
    finally:
        app.shutdown()


def test_driving_help_describes_x_as_signal_not_take_exit(monkeypatch):
    from driving_feature_helpers import key_event, quiet_trip, start_drive

    from freight_fate.app import App

    spoken = []
    app = App()
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.handle_event(key_event(pygame.K_F1))

        help_text = spoken[-1]
        assert "X signals for the next announced route exit" in help_text
        assert "X takes the next announced exit" not in help_text
    finally:
        app.shutdown()


def test_name_entry_keeps_its_commas():
    from freight_fate.states.main_menu import NameEntryState

    assert NameEntryState.captures_text_input is True


def test_safe_speed_key_speaks_one_number(monkeypatch):
    """D: terse, weather baked into the math and never into the sentence."""
    from freight_fate.app import App
    from freight_fate.sim.weather import WeatherKind

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = d.trip.total_miles / 2  # out on the open road
        limit, _ = d.trip.speed_limit_at(d.trip.position_mi)
        spoken = _capture(app, monkeypatch)

        # Clear weather: the posted limit is the safe speed.
        d.weather.current = WeatherKind.CLEAR
        d.handle_event(key_event(pygame.K_d))
        assert spoken[-1] == f"Safe speed {limit:.0f} miles per hour."

        # Rain caps below the posted limit -- the number drops, and the
        # sentence never says why (the whole point of the terse key).
        d.weather.current = WeatherKind.RAIN
        d.handle_event(key_event(pygame.K_d))
        assert spoken[-1] == "Safe speed 55 miles per hour."
        assert "rain" not in spoken[-1].lower()
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
    from freight_fate.states.driving_location import spoken_closing_distance

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = 20.0
        stop = next(s for s in d.trip.stops if s.at_mi > d.trip.position_mi)
        d.trip.planned_stop_key = stop.key
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_r))

        report = spoken[-1]
        ahead = spoken_closing_distance(stop.at_mi - d.trip.position_mi, d.trip.imperial)
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


def test_safe_speed_key_answers_for_the_ramp(monkeypatch):
    """On the ramp (or with an armed exit close ahead) the ramp speed rules."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        from freight_fate.sim.weather import WeatherKind

        d.weather.current = WeatherKind.CLEAR
        d.trip.position_mi = d.trip.total_miles / 2
        d._ramp_mi = d.trip.position_mi  # on the ramp now
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_d))
        assert spoken[-1] == "Safe speed 45 miles per hour for the ramp."
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


def test_grade_key_reads_slope_and_verdict(monkeypatch):
    """G speaks the grade under the wheels and the sim's own force verdict."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture(app, monkeypatch)
        t = d.truck

        t.grade = 0.0
        d.handle_event(key_event(pygame.K_g))
        assert "Level road" in spoken[-1]

        # A loaded climb the engine cannot hold: uphill plus losing speed.
        t.start_engine()
        t.set_air_ready(parking_brake=False)
        t.grade = 0.06
        t.cargo_kg = 21_500.0
        t.transmission.gear = 10
        t.velocity_mps = 26.8
        t.throttle = 1.0
        d.handle_event(key_event(pygame.K_g))
        assert "percent uphill" in spoken[-1]
        assert "lose speed" in spoken[-1]

        # Downhill with no jake and speed building: the warning speaks.
        t.grade = -0.05
        t.throttle = 0.0
        t.engine_brake_stage = 0
        d.handle_event(key_event(pygame.K_g))
        assert "percent downhill" in spoken[-1]
        assert "set the jake" in spoken[-1]
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


def _alt(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=pygame.KMOD_LALT)


def test_clock_key_keeps_one_hours_clause_instead_of_the_whole_report(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.hos.drive(300.0)
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_c))
        report = spoken[-1]
        # The limit that comes first still rides the clock key: a driver can
        # be on schedule and out of hours at once.
        assert "Break due in 3.0 hours." in report
        # ...but the full ELD report belongs to Tab and the three hours keys.
        assert "hours of driving left" not in report
        assert "ELD status" not in report
    finally:
        app.shutdown()


def test_clock_key_points_at_the_hours_keys_for_the_first_three_presses(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture(app, monkeypatch)
        notice = "Hours of service moved to Alt A, Alt S, and Alt D."
        for _ in range(3):
            d.handle_event(key_event(pygame.K_c))
            assert notice in spoken[-1]
        d.handle_event(key_event(pygame.K_c))
        assert notice not in spoken[-1]
        assert app.ctx.profile.hos_key_notice_left == 0
    finally:
        app.shutdown()


def test_alt_a_s_and_d_each_answer_one_hours_question(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.hos.drive(300.0)
        spoken = _capture(app, monkeypatch)

        d.handle_event(_alt(pygame.K_a))
        assert spoken[-1].startswith("At the wheel so far:")
        assert "5.0 hours driving" in spoken[-1]

        d.handle_event(_alt(pygame.K_s))
        assert spoken[-1].startswith("Break due in 3.0 hours")

        d.handle_event(_alt(pygame.K_d))
        assert spoken[-1].startswith("Driving time left: 6.0 hours")
        assert "Duty window closes in 9.0 hours" in spoken[-1]
    finally:
        app.shutdown()


def test_the_hours_keys_leave_plain_a_s_and_d_alone(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_s))
        assert "Speed limit" in spoken[-1]
        d.handle_event(key_event(pygame.K_d))
        assert "Safe speed" in spoken[-1] or "safe speed" in spoken[-1]
        d.handle_event(key_event(pygame.K_a))
        assert "At the wheel" not in spoken[-1]
    finally:
        app.shutdown()


def test_alt_d_carries_the_next_legal_stop_context(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.hos.drive(300.0)
        spoken = _capture(app, monkeypatch)
        d.handle_event(_alt(pygame.K_d))
        verbose = spoken[-1]
        # The stop-planning clause moved off the clock key onto the key that
        # answers "when does this shift end".
        assert "legal stop" in verbose or "No route stop" in verbose

        app.ctx.settings.speech_verbosity = 0
        d.handle_event(_alt(pygame.K_d))
        assert "Next legal stop" not in spoken[-1]
        assert len(spoken[-1]) < len(verbose)
    finally:
        app.shutdown()


def test_controller_clock_button_keeps_the_whole_hours_report(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.hos.drive(300.0)
        spoken = _capture(app, monkeypatch)
        event = pygame.event.Event(
            pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_DPAD_RIGHT
        )
        d.handle_controller(event, app.ctx.controller)
        # A pad has nowhere to put three more info buttons, so this one press
        # must still carry the hours a keyboard player gets from Alt A/S/D.
        assert "hours of driving left" in spoken[-1]
        assert "Hours of service moved to" not in spoken[-1]
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


def test_route_key_answers_with_the_gate_on_the_facility_approach(monkeypatch):
    """After the destination exit, R describes the approach, not the dead
    highway (playtest 2026-07-22: 'on I-90 West, 3 miles remaining' with a
    frozen countdown while rolling city streets toward the gate)."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d._destination_exit_taken = True
        d.trip.position_mi = d.trip.total_miles - 2.0
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_r))

        report = spoken[-1]
        assert report.startswith("Route status: off the highway, on the facility approach")
        assert "I-90" not in report
        assert "into the trip" not in report
    finally:
        app.shutdown()


def test_route_key_answers_with_the_gate_when_the_route_has_ended(monkeypatch):
    """Rolled past the gate: R agrees with the S key's gate override."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d._destination_exit_taken = True
        d.trip.position_mi = d.trip.total_miles
        d.trip.finished = True
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_r))

        assert spoken[-1].startswith("Route status: you have arrived")
        assert "Stop to dock" in spoken[-1]
    finally:
        app.shutdown()


def _on_the_surface_chain(app):
    """A drive handed over to the destination facility's street chain."""
    d = _driving(app)
    d._destination_exit_taken = True
    d._ramp_mi = None
    assert d._begin_surface_chain(announce=False), "no street chain for this facility"
    return d


def test_route_key_never_says_zero_miles_closing_on_the_gate(monkeypatch):
    """Named regression for the owner report of 2026-08-15.

    ``Trip._distance_text`` rounds to whole miles, so every answer inside
    the last half mile was "0 miles to the gate" -- and at 25 mph on city
    streets that half mile takes over a minute. Walk the chain down to a
    couple of hundred feet and the countdown has to keep meaning something.
    """
    from freight_fate.app import App

    app = App()
    try:
        d = _on_the_surface_chain(app)
        assert d.trip.total_miles >= 0.5, "chain too short to walk the whole ladder"
        spoken = _capture(app, monkeypatch)
        heard = []
        for remaining in (0.5, 0.4, 0.3, 0.2, 0.1, 0.05, 200 / 5280.0, 60 / 5280.0):
            if remaining > d.trip.total_miles:
                continue
            d.trip.position_mi = d.trip.total_miles - remaining
            spoken.clear()
            d.handle_event(key_event(pygame.K_r))
            heard.append(spoken[-1])

        assert heard, "the chain was too short to walk down"
        for report in heard:
            assert "0 miles" not in report, report
            assert "0 kilometers" not in report, report
        assert "200 feet to the gate" in heard[-2], heard[-2]
        assert "50 feet to the gate" in heard[-1], heard[-1]
        assert "half a mile to the gate" in heard[0], heard[0]
    finally:
        app.shutdown()


def test_route_key_names_the_street_under_the_wheels(monkeypatch):
    """The chain's report follows the truck, not the street it started on."""
    from freight_fate.app import App

    app = App()
    try:
        d = _on_the_surface_chain(app)
        legs = d.trip.route.legs
        assert len(legs) >= 2
        spoken = _capture(app, monkeypatch)

        d.trip.position_mi = legs[0].miles * 0.5
        d.handle_event(key_event(pygame.K_r))
        assert f"on city streets, {legs[0].highway}," in spoken[-1], spoken[-1]

        d.trip.position_mi = legs[0].miles + legs[1].miles * 0.5
        d.handle_event(key_event(pygame.K_r))
        assert f"on city streets, {legs[1].highway}," in spoken[-1], spoken[-1]
    finally:
        app.shutdown()


def test_route_key_counts_down_to_the_on_ramp_leaving_the_origin_gate(monkeypatch):
    """The departure chain is city streets, and the highway readout was
    wrong on it twice over: it called a two-mile street chain's percent the
    run's progress, and it pointed the driver "toward" the city they were
    standing in (owner report, 2026-08-15)."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app, "Rochester", "Buffalo", origin_location="Rochester freight market")
        assert d._begin_departure_chain(announce=False), "no departure chain for this facility"
        highway = d._highway_trip.route.legs[0].highway
        d.trip.position_mi = d.trip.total_miles * 0.5
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_r))

        report = spoken[-1]
        assert report.startswith("Route status: on city streets,")
        assert f"to the {highway} on-ramp." in report, report
        assert "percent there" not in report, report
        assert "toward" not in report, report
        assert "0 miles" not in report, report
    finally:
        app.shutdown()


def test_route_key_answers_the_pickup_drive_as_city_streets(monkeypatch):
    """The pickup drive is streets from end to end: no highway leg to frame."""
    from freight_fate.app import App
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        origin, location = "Rochester", "Rochester freight market"
        app.ctx.profile = Profile(name="Info Keys", current_city=origin)
        highway = app.ctx.world.supported_route(origin, "Buffalo")
        job = Job(
            CARGO_CATALOG["general"],
            12.0,
            origin,
            location,
            "Buffalo",
            highway.miles,
            1000.0,
            12.0,
            destination_location="Buffalo freight market",
        )
        route = app.ctx.world.facility_approach_route(origin, location)
        d = DrivingState(app.ctx, job, route, phase="pickup")
        d.trip.position_mi = max(0.0, d.trip.total_miles - 200 / 5280.0)
        spoken = _capture(app, monkeypatch)

        d.handle_event(key_event(pygame.K_r))

        report = spoken[-1]
        assert report.startswith("Route status: on city streets,")
        assert "200 feet to the gate at" in report, report
        assert "percent there" not in report, report
    finally:
        app.shutdown()


def _fixed_grade(driving, pct, *, until_mi=None):
    """Put a constant grade under the wheels for the whole scanned window."""
    limit = driving.trip.total_miles if until_mi is None else until_mi
    driving.trip.grade_at = lambda mile: pct / 100.0 if mile <= limit else 0.0
    driving.truck.grade = pct / 100.0


def test_grade_key_reads_the_slope_and_whether_the_truck_holds_it(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = 5.0
        _fixed_grade(d, -5.0, until_mi=9.0)
        d.truck.start_engine()
        d.truck.set_air_ready(parking_brake=False)
        d.truck.velocity_mps = 60.0 / 2.23694
        d.truck.transmission.gear = d.truck.transmission.num_gears
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_g))
        said = spoken[-1]
        assert "Grade 5.0 percent downhill" in said, said
        # The run is spoken, and so is the verdict from the force balance.
        assert "for another" in said, said
        assert "Speed is building" in said or "jake" in said, said
    finally:
        app.shutdown()


def test_grade_key_names_the_next_steep_grade_ahead(monkeypatch):
    """One press answers both what you are on and what is coming."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = 5.0
        # Level here, a 6 percent downgrade waiting three miles out.
        d.trip.grade_at = lambda mile: -0.06 if 8.0 <= mile <= 11.0 else 0.0
        d.truck.grade = 0.0
        d.truck.velocity_mps = 60.0 / 2.23694
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_g))
        said = spoken[-1]
        assert said.startswith("Level road."), said
        assert "Next, a 6.0 percent downgrade in" in said, said
    finally:
        app.shutdown()


def test_grade_key_says_when_nothing_steep_is_coming(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.trip.position_mi = 5.0
        d.trip.grade_at = lambda mile: 0.0
        d.truck.grade = 0.0
        spoken = _capture(app, monkeypatch)
        d.handle_event(key_event(pygame.K_g))
        assert "Nothing steep in the next" in spoken[-1], spoken[-1]
    finally:
        app.shutdown()
