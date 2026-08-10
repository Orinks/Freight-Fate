"""Street turns cost speed, not reflex.

A turn is a speed you have to be under by the time you reach it -- announced
a full spoken window out, anchored to the street's own posted limit, and
capped at what a trailer can turn. Arriving over it is the failure, and the
failure is the shipped loop-back through the next safe turnaround, never a
timed reaction window. Escalation is here from the first build: the core
sentence never changes, help is appended, and the turn is eventually made for
the player so a route can never become unfinishable.

The same module keeps the panned road bed alive through turns and ramp
connectors, which used to fall silent exactly when a blind driver needs the
only continuous directional audio the game has.
"""

from speech_capture import speech_stub


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Corners", current_city="Buffalo")
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
    d.trip.traffic_manager.vehicles = []
    return d


def _street_chain(d, *, time_scale: float = 1.0):
    """Swap the drive onto a deterministic three-block facility street chain.

    Leg 1 is a left onto a 25 mph street (advise 20, the trailer cap); leg 2
    is a right onto a 15 mph service way (advise 15, the street's own limit).
    """
    from freight_fate.data.world_models import Leg, Route
    from freight_fate.sim import Trip

    city = d.trip.route.cities[0]
    legs = [
        Leg(
            city,
            city,
            0.6,
            "East Navarre Street",
            "flat",
            (),
            local_cue="Start on East Navarre Street.",
            local_speed_mph=25.0,
        ),
        Leg(
            city,
            city,
            0.5,
            "North Michigan Street",
            "flat",
            (),
            local_cue="Turn left onto North Michigan Street.",
            local_speed_mph=25.0,
        ),
        Leg(
            city,
            city,
            0.5,
            "West Sample Street",
            "flat",
            (),
            local_cue="Turn right onto West Sample Street.",
            local_speed_mph=15.0,
        ),
    ]
    trip = Trip(Route([city] * 4, legs), d.truck, d.trip.weather, seed=3, time_scale=time_scale)
    trip.traffic_manager.vehicles = []
    d.trip = trip
    d._reset_turn_state_for_trip()
    return trip


def _capture(app, monkeypatch, *, with_interrupt: bool = False):
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken, with_interrupt=with_interrupt))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    return spoken


def _mph(d, mph: float) -> None:
    d.truck.engine_on = True
    d.truck.velocity_mps = mph / 2.23694


def _at_turn(d, at_mi: float, *, mph: float) -> None:
    """Roll up to a turn, hear its call, and let the reaction window expire."""
    d.trip.position_mi = at_mi - 0.2
    _mph(d, mph)
    d._update_turn_commitment(0.016)
    d.trip.position_mi = at_mi
    d._update_turn_commitment(d._turn_grace_s + 1.0)


# -- the approach call -------------------------------------------------------


def test_approach_call_names_the_side_street_distance_and_speed(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _street_chain(d)
        spoken = _capture(app, monkeypatch)
        d.trip.position_mi = 0.4
        _mph(d, 30.0)
        d._update_turn_commitment(0.016)
        assert len(spoken) == 1
        assert spoken[0] == (
            "Left turn onto North Michigan Street, a quarter mile. Advise 20 miles per hour."
        )
        assert d._turn_grace_s > 0.0
        d._update_turn_commitment(0.016)
        assert len(spoken) == 1  # said once, not every frame
    finally:
        app.shutdown()


def test_terse_keeps_direction_street_and_distance_but_drops_the_advisory(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.speech_verbosity = 0
        d = _driving(app)
        _street_chain(d)
        spoken = _capture(app, monkeypatch)
        d.trip.position_mi = 0.4
        _mph(d, 30.0)
        d._update_turn_commitment(0.016)
        assert spoken[0] == "Left turn onto North Michigan Street, a quarter mile."
        # Never a bare "Right now": the verb always leads.
        assert "Right now" not in spoken[0]
    finally:
        app.shutdown()


def test_a_cold_arrival_at_the_turn_still_gets_its_window(monkeypatch):
    # A resumed save can reach the turn without ever hearing the approach.
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _street_chain(d)
        spoken = _capture(app, monkeypatch)
        d.trip.position_mi = 0.6
        _mph(d, 45.0)
        d._update_turn_commitment(0.016)
        assert spoken[-1].startswith("Turn left now onto North Michigan Street.")
        assert d._turn_miss_count == 0
        assert d._turn_grace_s > 0.0
    finally:
        app.shutdown()


def test_the_window_is_real_seconds_not_a_fixed_distance(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_turns import TURN_WINDOW_MAX_MI, TURN_WINDOW_MIN_MI

    app = App()
    try:
        d = _driving(app)
        _street_chain(d, time_scale=40.0)
        _capture(app, monkeypatch)
        _mph(d, 55.0)
        assert d._turn_window_mi() == TURN_WINDOW_MAX_MI
        _street_chain(d, time_scale=1.0)
        _mph(d, 20.0)
        assert d._turn_window_mi() == TURN_WINDOW_MIN_MI
    finally:
        app.shutdown()


def test_the_approach_decompresses_the_clock(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _street_chain(d, time_scale=40.0)
        _capture(app, monkeypatch)
        d.trip.position_mi = 0.4
        _mph(d, 30.0)
        assert d.trip.effective_time_scale > 1.0
        d._update_turn_commitment(0.016)
        assert d.trip.controlled_turn is True
        assert d.trip.effective_time_scale == 1.0
        d.trip.position_mi = 0.6
        _mph(d, 18.0)
        d._update_turn_commitment(d._turn_grace_s + 1.0)
        assert d.trip.controlled_turn is False
    finally:
        app.shutdown()


# -- the turn speed ----------------------------------------------------------


def test_turn_speed_anchors_to_the_street_and_caps_at_the_trailer_limit(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_turns import TURN_CORNER_MAX_MPH

    app = App()
    try:
        d = _driving(app)
        trip = _street_chain(d)
        _capture(app, monkeypatch)
        cues = [c for c in trip.navigation_cues if c.key.startswith("local:turn:")]
        assert len(cues) == 2
        # A 25 mph street is still only turnable at the trailer cap.
        assert d._turn_speed_mph(cues[0]) == TURN_CORNER_MAX_MPH
        # A 15 mph service way keeps its own, slower, posted limit.
        assert d._turn_speed_mph(cues[1]) == 15.0
    finally:
        app.shutdown()


def test_under_the_turn_speed_passes_cleanly(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _street_chain(d)
        _capture(app, monkeypatch)
        minutes = d.trip.game_minutes
        _at_turn(d, 0.6, mph=18.0)
        assert d._turn_miss_count == 0
        assert d.trip.game_minutes == minutes
        assert d.trip.position_mi == 0.6
    finally:
        app.shutdown()


def test_no_miss_while_the_turns_own_cue_is_still_speaking(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _street_chain(d)
        _capture(app, monkeypatch)
        d.trip.position_mi = 0.4
        _mph(d, 40.0)
        d._update_turn_commitment(0.016)
        grace = d._turn_grace_s
        assert grace > 0.0
        d.trip.position_mi = 0.6
        d._update_turn_commitment(0.016)
        assert d._turn_miss_count == 0  # still inside the spoken window
        d._update_turn_commitment(grace + 1.0)
        assert d._turn_miss_count == 1
    finally:
        app.shutdown()


def test_a_hazard_never_reads_as_a_missed_turn(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _street_chain(d)
        _capture(app, monkeypatch)
        d._hazard_deadline = 5.0  # a swerve is not a blown turn
        _at_turn(d, 0.6, mph=45.0)
        assert d._turn_miss_count == 0
    finally:
        app.shutdown()


def test_a_microsleep_never_reads_as_a_missed_turn(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _street_chain(d)
        _capture(app, monkeypatch)
        d._microsleep_deadline = 3.0
        _at_turn(d, 0.6, mph=45.0)
        assert d._turn_miss_count == 0
    finally:
        app.shutdown()


# -- the miss and its escalation --------------------------------------------


def test_over_the_turn_speed_loops_back_and_charges_time(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_turns import TURN_MISS_LOOP_MIN

    app = App()
    try:
        d = _driving(app)
        _street_chain(d)
        spoken = _capture(app, monkeypatch, with_interrupt=True)
        minutes = d.trip.game_minutes
        _at_turn(d, 0.6, mph=45.0)
        assert d._turn_miss_count == 1
        assert d.trip.game_minutes == minutes + TURN_MISS_LOOP_MIN
        assert d.trip.position_mi < 0.6  # dropped back onto the approach
        text, interrupt = spoken[-1]
        assert interrupt is True
        assert text == (
            "You missed the turn onto North Michigan Street. You continue to the "
            "next safe turnaround and loop back onto the approach. The turn is "
            "ahead again."
        )
    finally:
        app.shutdown()


def test_the_loop_back_drops_a_full_spoken_window(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _street_chain(d)
        _capture(app, monkeypatch)
        _at_turn(d, 0.6, mph=45.0)
        # A full window back, never a fixed distance, so the retry is winnable.
        assert d.trip.position_mi == 0.6 - d._turn_window_mi()
    finally:
        app.shutdown()


def test_the_loop_back_resets_every_say_once_latch(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        trip = _street_chain(d)
        _capture(app, monkeypatch)
        trip._announced_navigation.add("local:turn:1:advance")
        trip._announced_navigation.add("local:turn:1:near")
        _at_turn(d, 0.6, mph=45.0)
        assert "local:turn:1" not in d._turn_advised
        assert "local:turn:1:advance" not in trip._announced_navigation
        assert "local:turn:1:near" not in trip._announced_navigation
        assert trip.controlled_turn is False
        # And the re-approach really does speak and pass.
        _at_turn(d, 0.6, mph=18.0)
        assert d._turn_miss_count == 1
    finally:
        app.shutdown()


def test_terse_miss_keeps_the_essentials(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.speech_verbosity = 0
        d = _driving(app)
        _street_chain(d)
        spoken = _capture(app, monkeypatch)
        _at_turn(d, 0.6, mph=45.0)
        assert spoken[-1] == "Missed the turn. Safe turnaround. Turn ahead again."
    finally:
        app.shutdown()


def test_a_repeat_miss_appends_help_to_an_identical_core_sentence(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _street_chain(d)
        spoken = _capture(app, monkeypatch)
        _at_turn(d, 0.6, mph=45.0)
        first = spoken[-1]
        assert "Brake to" not in first
        _at_turn(d, 1.1, mph=45.0)
        second = spoken[-1]
        assert second.startswith("You missed the turn onto West Sample Street.")
        assert "Brake to 15 miles per hour" in second
        assert "Down arrow" in second  # the brake key this driver actually has
    finally:
        app.shutdown()


def test_a_second_miss_on_the_same_turn_is_made_for_the_player(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_turns import TURN_MISS_LOOP_MIN

    app = App()
    try:
        d = _driving(app)
        _street_chain(d)
        spoken = _capture(app, monkeypatch)
        minutes = d.trip.game_minutes
        _at_turn(d, 0.6, mph=45.0)  # loops back
        _at_turn(d, 0.6, mph=45.0)  # same turn again: no second loop
        assert d._turn_miss_count == 2
        assert d.trip.game_minutes == minutes + 2 * TURN_MISS_LOOP_MIN
        assert d.trip.position_mi > 0.6  # routed around, past the turn
        assert "The turn is made for you" in spoken[-1]
        assert spoken[-1].startswith("You missed the turn onto North Michigan Street.")
        # The turn is settled: it never comes back to be missed a third time.
        assert d._turn_cue_in_play().key == "local:turn:2"
    finally:
        app.shutdown()


def test_the_third_miss_anywhere_completes_the_turn(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_turns import TURN_MISS_LOOP_MIN

    app = App()
    try:
        d = _driving(app)
        _street_chain(d)
        spoken = _capture(app, monkeypatch)
        d._turn_miss_count = 2  # two turns already blown on this run
        minutes = d.trip.game_minutes
        _at_turn(d, 0.6, mph=45.0)
        assert d._turn_miss_count == 3
        assert d.trip.game_minutes == minutes + TURN_MISS_LOOP_MIN  # time still charged
        assert d.trip.position_mi > 0.6
        assert "The turn is made for you" in spoken[-1]
    finally:
        app.shutdown()


def test_snapshot_round_trips_the_turn_miss_count(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        d = _driving(app)
        _capture(app, monkeypatch)
        d._turn_miss_count = 2
        resumed = DrivingState.from_snapshot(app.ctx, d.snapshot())
        assert resumed is not None
        assert resumed._turn_miss_count == 2
    finally:
        app.shutdown()


def test_highway_junctions_are_never_judged(monkeypatch):
    # Highway maneuver cues carry no direction, radius, or lane ordinal, so
    # they stay warn-only; nothing on a corridor route is a judged turn.
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _capture(app, monkeypatch)
        assert d._turn_cue_in_play() is None
        d._update_turn_commitment(0.016)
        assert d._turn_miss_count == 0
    finally:
        app.shutdown()


# -- the guide runs through turns and ramps ---------------------------------


def test_the_road_bed_leans_through_a_street_turn(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _street_chain(d)
        _capture(app, monkeypatch)
        _mph(d, 20.0)
        d.trip.position_mi = 0.2  # nothing to lean into yet
        assert d._curve_steer_demand() == 0.0
        d.trip.position_mi = 0.5  # leaning in
        leaning = d._curve_steer_demand()
        assert leaning < 0.0  # a left turn leans left
        d.trip.position_mi = 0.6  # at the turn, full lean
        assert d._curve_steer_demand() < leaning
        # And the right turn leans the other way.
        d.trip.position_mi = 0.65
        d._update_turn_commitment(0.016)
        d.trip.position_mi = 1.1
        assert d._curve_steer_demand() > 0.0
    finally:
        app.shutdown()


def test_the_road_bed_leans_through_a_ramp_connector(monkeypatch):
    from freight_fate.app import App
    from freight_fate.data.curves import RouteCurve

    app = App()
    try:
        d = _driving(app)
        _capture(app, monkeypatch)
        connector = RouteCurve(
            start_mi=d.trip.position_mi - 0.05,
            apex_mi=d.trip.position_mi,
            end_mi=d.trip.position_mi + 0.05,
            direction="R",
            advisory_mph=30,
            min_radius_ft=300,
            deflection_deg=80.0,
            connector=True,
        )
        monkeypatch.setattr(d.trip, "curve_at", lambda _mi: connector)
        _mph(d, 40.0)
        # This returned 0.0 before the fix: the guide went silent on ramps.
        assert d._curve_steer_demand() > 0.0
    finally:
        app.shutdown()


def test_the_road_bed_leans_on_an_exit_ramp(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_turns import RAMP_GUIDE_DEMAND

    app = App()
    try:
        d = _driving(app)
        _capture(app, monkeypatch)
        monkeypatch.setattr(d.trip, "curve_at", lambda _mi: None)
        d._ramp_mi = 0.3
        assert d._curve_steer_demand() == RAMP_GUIDE_DEMAND
    finally:
        app.shutdown()
