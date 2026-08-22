"""Missing the facility gate: carry past it too fast and you loop back.

A truck that crosses the destination facility gate above the gate zone's own
posted limit has missed the entrance -- there is no invisible treadmill that
pins the trip at route end while the truck barrels on. The miss mirrors the
missed-destination-exit flow: a scripted loop back through the next safe
turnaround, game time charged, and the gate ahead again. Because the spoken
cue is the only signage, a pre-gate speed warning always precedes the first
possible miss, and a real-time reaction window is honored before one latches.
"""

import pytest
from speech_capture import speech_stub


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Gates", current_city="Buffalo")
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


def _capture_events(app, monkeypatch, *, with_interrupt: bool = False):
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken, with_interrupt=with_interrupt))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    return spoken


def _at_gate(d, *, mph: float, warned: bool = True) -> None:
    """Put the truck right at the finished route end, rolling at ``mph``."""
    d._destination_exit_taken = True
    d.trip.position_mi = d.trip.total_miles
    d.trip.finished = True
    d.truck.engine_on = True
    d.truck.velocity_mps = mph / 2.23694
    d._gate_speed_warned = warned
    d._gate_grace_s = 0.0


def test_fast_crossing_misses_the_gate_and_loops_back(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_facility_gate import GATE_MISS_LOOP_MIN

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch, with_interrupt=True)
        minutes = d.trip.game_minutes
        _at_gate(d, mph=70.0)
        d._handle_arrival_gate()
        assert d.trip.finished is False
        assert d.trip.position_mi < d.trip.total_miles
        assert d._gate_miss_count == 1
        assert d.trip.game_minutes == minutes + GATE_MISS_LOOP_MIN
        text, interrupt = spoken[-1]
        assert interrupt is True
        assert "safe turnaround" in text
        assert "slow to" in text.lower()
    finally:
        app.shutdown()


def test_slow_crossing_arrives_normally(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _at_gate(d, mph=10.0, warned=False)
        d._handle_arrival_gate()
        assert d.trip.finished is True
        assert d._gate_miss_count == 0
        assert "Destination ahead" in spoken[-1]
        d.truck.velocity_mps = 0.3 / 2.23694
        d._handle_arrival_gate()
        assert d._arrival_menu_open is True
    finally:
        app.shutdown()


def test_pre_gate_warning_names_a_target_speed(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        d._destination_exit_taken = True
        d.trip.position_mi = d.trip.total_miles - 0.3
        d.truck.engine_on = True
        d.truck.velocity_mps = 40.0 / 2.23694
        d._check_gate_approach_warning(0.016)
        assert len(spoken) == 1
        assert "Facility gate in" in spoken[0]
        assert "15 miles per hour" in spoken[0]
        assert d._gate_grace_s > 0.0
        d._check_gate_approach_warning(0.016)
        assert len(spoken) == 1  # said once, not every frame
    finally:
        app.shutdown()


def test_no_instant_miss_inside_the_reaction_window(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        d._destination_exit_taken = True
        d.trip.position_mi = d.trip.total_miles - 0.3
        d.truck.engine_on = True
        d.truck.velocity_mps = 40.0 / 2.23694
        d._check_gate_approach_warning(0.016)  # warning spoken, window opens
        grace = d._gate_grace_s
        assert grace > 0.0
        d.trip.position_mi = d.trip.total_miles
        d.trip.finished = True
        d._handle_arrival_gate()
        assert d.trip.finished is True  # still inside the reaction window
        assert d._gate_miss_count == 0
        assert "Destination ahead" in spoken[-1]
        d._check_gate_approach_warning(grace + 1.0)  # the window expires
        d._handle_arrival_gate()
        assert d.trip.finished is False
        assert d._gate_miss_count == 1
    finally:
        app.shutdown()


def test_first_gate_contact_without_a_warning_still_gets_a_window(monkeypatch):
    # A resumed save can arrive at the gate cold: the miss clock must start
    # with the gate's own stop line, never latch on first contact.
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _at_gate(d, mph=40.0, warned=False)
        d._handle_arrival_gate()
        assert d.trip.finished is True
        assert d._gate_miss_count == 0
        assert "Destination ahead" in spoken[-1]
        assert d._gate_speed_warned is True
        assert d._gate_grace_s > 0.0
    finally:
        app.shutdown()


def test_destination_approach_assist_never_misses(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.destination_approach_assist = True
        d = _driving(app)
        _capture_events(app, monkeypatch)
        _at_gate(d, mph=40.0)
        d._handle_arrival_gate()
        assert d.trip.finished is True
        assert d._gate_miss_count == 0
        assert d.truck.brake == 1.0  # the assist is braking the truck itself
    finally:
        app.shutdown()


def test_hazard_braking_never_misses(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        _at_gate(d, mph=40.0)
        d._hazard_deadline = 5.0  # mid-hazard: braking hard is the right move
        d._handle_arrival_gate()
        assert d.trip.finished is True
        assert d._gate_miss_count == 0
    finally:
        app.shutdown()


def test_repeat_miss_appends_the_help_clause(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _at_gate(d, mph=70.0)
        d._handle_arrival_gate()
        first = spoken[-1]
        assert "Settings" not in first
        _at_gate(d, mph=70.0)
        d._handle_arrival_gate()
        second = spoken[-1]
        assert first in second  # the core line stays identical, help is appended
        assert "Down arrow" in second
        assert "Destination approach assist" in second
    finally:
        app.shutdown()


def test_miss_resets_the_gate_latches(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        _at_gate(d, mph=70.0)
        d._arrival_stop_said = True
        d._arrival_full_stop_said = True
        d._gate_reminder_s = 5.0
        d._handle_arrival_gate()
        assert d._arrival_stop_said is False
        assert d._arrival_full_stop_said is False
        assert d._gate_reminder_s == 0.0
        assert d._gate_speed_warned is False  # the next approach warns fresh
    finally:
        app.shutdown()


def test_reapproach_after_a_miss_arrives_normally(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _at_gate(d, mph=70.0)
        d._handle_arrival_gate()  # the miss
        # Back at the gate at a sane speed this time.
        d.trip.position_mi = d.trip.total_miles
        d.trip.finished = True
        d.truck.velocity_mps = 2.0 / 2.23694
        d._handle_arrival_gate()
        assert "Stop to dock" in spoken[-1]
        d.truck.velocity_mps = 0.3 / 2.23694
        d._handle_arrival_gate()
        assert d._arrival_menu_open is True
    finally:
        app.shutdown()


def test_the_gate_warning_names_a_limit_that_is_really_posted(monkeypatch):
    """ "Slow to 15" has to be the number in force, not a number nothing posts.

    The arrival zones are dropped at trip start so no silent low limit writes
    speeding fines under a spoken 65 on the final freeway miles. That left the
    pre-gate warning naming 15 while the last half mile still read the
    corridor's own limit, so every assist held the corridor number straight
    through the entrance and into the loop-back (owner playtest, 2026-08-21).
    """
    from freight_fate.app import App
    from freight_fate.sim.trip_models import FACILITY_GATE_LIMIT_MPH

    app = App()
    try:
        d = _driving(app)
        # While the truck is still on the highway, nothing has changed: the
        # arrival zones stay off the map.
        assert not any(zone.reason == "facility gate" for zone in d.trip.zones)
        corridor, _ = d.trip.speed_limit_at(d.trip.total_miles - 0.3)
        assert corridor > FACILITY_GATE_LIMIT_MPH

        # Taking the destination exit puts the driveway's own limit back.
        # This is the NO-CHAIN case: a facility whose own streets become the
        # trip posts its gate from that chain instead, and posting one here as
        # well would announce the same gate twice.
        d._surface_chain_route = lambda: None
        d._destination_exit_taken = True
        d._post_gate_zone()
        posted, reason = d.trip.speed_limit_at(d.trip.total_miles - 0.3)
        assert reason == "facility gate"
        assert posted == FACILITY_GATE_LIMIT_MPH

        spoken = _capture_events(app, monkeypatch)
        d.trip.position_mi = d.trip.total_miles - 0.3
        d.truck.engine_on = True
        d.truck.velocity_mps = 40.0 / 2.23694
        d._check_gate_approach_warning(0.016)
        # The spoken target and the posted limit are the same number.
        assert app.ctx.settings.speed_text(posted) in spoken[0]
        # Posting it twice would stack two gate zones on one driveway.
        d._post_gate_zone()
        assert [z.reason for z in d.trip.zones].count("facility gate") == 1
    finally:
        app.shutdown()


def test_terse_mode_hears_the_essential_cues(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.driving_speech = "quiet"
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        d._destination_exit_taken = True
        d.trip.position_mi = d.trip.total_miles - 0.3
        d.truck.engine_on = True
        d.truck.velocity_mps = 40.0 / 2.23694
        d._check_gate_approach_warning(0.016)
        assert "Gate in" in spoken[-1]
        assert "Slow to" in spoken[-1]
        _at_gate(d, mph=70.0)
        d._handle_arrival_gate()
        assert "Missed the gate" in spoken[-1]
        assert "Safe turnaround" in spoken[-1]
        assert "slow to" in spoken[-1].lower()
    finally:
        app.shutdown()


def test_time_is_charged_each_loop(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_facility_gate import GATE_MISS_LOOP_MIN

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        minutes = d.trip.game_minutes
        for _ in range(2):
            _at_gate(d, mph=70.0)
            d._handle_arrival_gate()
        assert d.trip.game_minutes == minutes + 2 * GATE_MISS_LOOP_MIN
    finally:
        app.shutdown()


def test_missed_gate_loop_charges_hos_fatigue_and_fuel(monkeypatch):
    """The spoken "The clock is still running" line must be true: a gate
    miss's scripted loop-back costs real HOS, fatigue, and fuel, not just
    the game clock -- otherwise the loop is a free-time exploit."""
    from freight_fate.app import App
    from freight_fate.states.driving_facility_gate import GATE_MISS_LOOP_MIN

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        driving_before = d.hos.driving_min
        fatigue_before = app.ctx.profile.fatigue
        d.truck.rpm = d.truck.specs.idle_rpm
        fuel_before = d.truck.fuel_gal

        _at_gate(d, mph=70.0)
        d._handle_arrival_gate()

        assert d.hos.driving_min == pytest.approx(driving_before + GATE_MISS_LOOP_MIN)
        assert app.ctx.profile.fatigue > fatigue_before
        assert d.truck.fuel_gal < fuel_before
        # Idle-rate honesty: ~0.8 gal/h floor, so twenty minutes is a small,
        # bounded sip, not a fraction of a highway-cruise burn.
        assert fuel_before - d.truck.fuel_gal < 1.0
    finally:
        app.shutdown()


def test_snapshot_round_trips_the_miss_count(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        d._gate_miss_count = 2
        resumed = DrivingState.from_snapshot(app.ctx, d.snapshot())
        assert resumed is not None
        assert resumed._gate_miss_count == 2
    finally:
        app.shutdown()


def test_a_facility_with_its_own_streets_does_not_get_a_second_gate_zone(monkeypatch):
    """One gate, one announcement.

    A facility whose approach is a real street chain drives those streets as a
    trip of their own, and that trip builds a gate zone at its end. Posting one
    on the highway trip as well put the same gate on the map twice, so the
    driver heard it announced coming off the ramp and again on the streets
    (owner, 2026-08-21).
    """
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d._surface_chain_route = lambda: object()  # this facility has streets
        d._destination_exit_taken = True
        d._post_gate_zone()
        assert not any(zone.reason == "facility gate" for zone in d.trip.zones)
    finally:
        app.shutdown()


def test_the_hold_prompt_does_not_come_back_once_the_menu_is_open(monkeypatch):
    """ "Press Enter to continue" must not be handed back after Enter.

    The prompt speaks once -- the say-once flag sees to that, and a real
    roll-in produces exactly one. The repeats Shane heard at a dock came from
    the speech layer handing a cut line back so it can finish, which is right
    in general and wrong for a line that asks for a keypress the driver has
    since made (Shane, 2026-08-21).
    """
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        app.ctx.settings.destination_approach_assist = True
        spoken = _capture_events(app, monkeypatch)
        _at_gate(d, mph=0.2, warned=False)
        d._handle_arrival_gate()
        holds = [t for t in spoken if "stopped and holding" in t]
        assert len(holds) == 1, f"the prompt spoke {len(holds)} times"

        # Said once and only once, however long the driver sits there.
        for _ in range(50):
            d._handle_arrival_gate()
        holds = [t for t in spoken if "stopped and holding" in t]
        assert len(holds) == 1
    finally:
        app.shutdown()


def _surface_chain_driving(app, monkeypatch):
    """A real facility street chain, driven the way an arrival really is.

    Not a stand-in: the docstring on
    ``test_the_destination_approach_assist_actually_brings_the_truck_to_a_stop``
    records three fake-object versions of this that all passed while the game
    drove past the market. The chain is a separate same-city Trip
    (``_begin_surface_chain``), and only a real one has the zones that
    re-engage the keeper.
    """
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    d = start_drive(app)
    quiet_trip(d)
    release_air_brakes(d)
    app.ctx.settings.destination_approach_assist = True
    app.ctx.settings.speed_keeper = True
    for city, location in (
        ("spokane_wa_us", "Spokane metro freight market"),
        ("kenosha_wi_us", "Kenosha Cross-Dock"),
        ("gary_in_us", "Gary Company Yard"),
    ):
        d.job.destination, d.job.destination_location = city, location
        if d._surface_chain_route() is not None:
            break
    else:
        pytest.skip("no baked facility street chain available in this world")
    d.trip.position_mi = d.trip.total_miles
    d.trip.finished = True
    assert d._begin_surface_chain(announce=False)
    return d


def test_the_approach_assist_stops_the_truck_on_a_facility_street_chain(monkeypatch):
    """Owner, Spokane, 2026-08-21: "it did not automatically stop at the
    destination; I had to stop." The third report of the same sentence --
    Odessa 2026-08-19 is in the exits suite, and that fix covered the RAMP.

    A ramp-to-gate arrival works: the truck comes in at 45, the cap binds a
    tenth of a mile out and the shed is long and gentle. A STREET CHAIN does
    not: the keeper holds the zone limit, the cap does not bind until about
    25 metres out, and 15 mph cannot be shed in 25 metres. Measured before
    this test existed, the truck crossed the arrival point at 14.1 mph.
    """
    from freight_fate.app import App
    from freight_fate.sim.trip_models import FACILITY_GATE_LIMIT_MPH
    from freight_fate.states.driving_core import DOCKING_MAX_MPH

    app = App()
    try:
        d = _surface_chain_driving(app, monkeypatch)
        _capture_events(app, monkeypatch)
        trip = d.trip
        d.truck.start_engine()
        d.truck.transmission.automatic = True
        d.truck.transmission.gear = 4
        d.truck.velocity_mps = 15.0 / 2.23694
        # Automatic speed control is ARMED coming off the highway, which is
        # what lets the zone keeper re-engage itself on the chain -- the very
        # thing that drives the truck through the arrival point.
        d._speed_control_armed = True

        # What the owner actually asked for: the truck stops itself. The
        # driver never touches a pedal in this test, so anything that halts
        # the rig is the assist. Measured as the end-to-end outcome rather
        # than the speed at one instant -- crossing the point at 8 mph and
        # halting a truck-length later is a different complaint from rolling
        # through at 14 with nothing on the brake, and only the driver's
        # pedal foot tells them apart.
        past_the_point_mi = 0.0
        speed_at_point = None
        stopped_at = None
        for _frame in range(60 * 900):
            d.update(1 / 60)
            if speed_at_point is None and (
                trip.remaining_miles <= 0.0 or trip.finished or d.trip is not trip
            ):
                speed_at_point = d.truck.speed_mph
            if speed_at_point is not None:
                # Integrated, not read off the trip: position_mi jumps when
                # the chain trip is swapped out at the arrival, so the only
                # honest measure of how far the truck ran past the point is
                # its own speed through the frames after it.
                past_the_point_mi += d.truck.velocity_mps / 1609.344 / 60.0
            if d.truck.speed_mph <= DOCKING_MAX_MPH:
                stopped_at = past_the_point_mi
                break
        assert speed_at_point is not None, "never reached the arrival point"
        assert stopped_at is not None, (
            f"the truck never stopped; it was still doing {d.truck.speed_mph:.1f} mph. "
            "The approach assist is supposed to stop it without the driver braking."
        )
        # Under the gate zone's own limit on the way in, so the arrival is
        # not scored as a blown gate.
        assert speed_at_point <= FACILITY_GATE_LIMIT_MPH, speed_at_point
        # How far past the point it may run is pinned separately, below.
    finally:
        app.shutdown()


def test_the_approach_assist_stops_within_a_truck_length_of_the_gate(monkeypatch):
    """The other half of the Spokane report: stopping means stopping AT the
    gate, not a city block past it.

    The first version of the fix stopped the truck 347 feet past the point at
    8 mph, because the assist re-decided every frame against its own curve --
    over it, brake; under it, stand down -- and standing down zeroed the
    servo and handed the pedals back. An arrival that has begun is LATCHED
    now: it keeps the pedals to the point and the servo tracks the road's
    real demand down, so the truck stops where the gate is."""
    from freight_fate.app import App
    from freight_fate.states.driving_core import DOCKING_MAX_MPH

    app = App()
    try:
        d = _surface_chain_driving(app, monkeypatch)
        _capture_events(app, monkeypatch)
        trip = d.trip
        d.truck.start_engine()
        d.truck.transmission.automatic = True
        d.truck.transmission.gear = 4
        d.truck.velocity_mps = 15.0 / 2.23694
        d._speed_control_armed = True

        past_mi = 0.0
        arrived = False
        for _frame in range(60 * 900):
            d.update(1 / 60)
            if not arrived and (trip.remaining_miles <= 0.0 or trip.finished or d.trip is not trip):
                arrived = True
            if arrived:
                past_mi += d.truck.velocity_mps / 1609.344 / 60.0
            if d.truck.speed_mph <= DOCKING_MAX_MPH:
                break
        # A tractor-trailer is about 70 feet. Stopping at the gate means
        # stopping within its own length of it, not a city block later.
        assert past_mi * 5280.0 <= 70.0, f"stopped {past_mi * 5280:.0f} feet past the gate"
    finally:
        app.shutdown()


def test_the_ramp_is_not_the_arrival_when_a_street_chain_follows_it(monkeypatch):
    """Owner, Spokane, 2026-08-22: "it didn't stop where I can pull it in."

    With the pedal finally reaching the truck, the assist stopped it dead at
    the bottom of the destination ramp -- a mile of city streets short of the
    gate -- and left automatic speed control paused the arrival way for the
    whole chain. The ramp's end is a driving continuation when a chain
    follows (the ramp terminal hands off "at whatever legal speed the
    terminal let through"); the arrival is the chain's own, a mile on.
    """
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App
    from freight_fate.states.driving import RAMP_LENGTH_MI

    app = App()
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        app.ctx.settings.destination_approach_assist = True
        for city, location in (
            ("spokane_wa_us", "Spokane metro freight market"),
            ("kenosha_wi_us", "Kenosha Cross-Dock"),
            ("gary_in_us", "Gary Company Yard"),
        ):
            d.job.destination, d.job.destination_location = city, location
            d._destination_chain_ahead = None
            if d._surface_chain_route() is not None:
                break
        else:
            pytest.skip("no baked facility street chain available in this world")
        assert d._destination_street_chain_ahead()

        # On the destination ramp, well inside the distance a 30 mph truck
        # needs to stop: exactly where the ramp-as-gate branch latched.
        destination = d._destination_exit_stop()
        assert destination is not None
        d._ramp_stop = destination
        d._ramp_mi = 0.05
        d.truck.start_engine()
        d.truck.transmission.automatic = True
        d.truck.transmission.gear = 6
        d.truck.velocity_mps = 30.0 / 2.23694
        d.truck.brake = 0.0
        d._update_destination_approach_assist()

        assert not d._destination_arrival_active
        assert d.truck.brake == 0.0
        assert d._destination_assist_brake == 0.0

        # And the same ramp IS the arrival when nothing follows it: the
        # ramp-to-dock delivery the 2026-08-19 fix was made for still stops.
        d._destination_chain_ahead = False
        d._ramp_mi = RAMP_LENGTH_MI * 0.1
        d._update_destination_approach_assist()
        assert d._destination_arrival_active
        assert d.truck.brake > 0.0
    finally:
        app.shutdown()
