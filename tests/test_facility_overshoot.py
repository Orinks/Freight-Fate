"""Missing the facility gate: carry past it too fast and you loop back.

A truck that crosses the destination facility gate above the gate zone's own
posted limit has missed the entrance -- there is no invisible treadmill that
pins the trip at route end while the truck barrels on. The miss mirrors the
missed-destination-exit flow: a scripted loop back through the next safe
turnaround, game time charged, and the gate ahead again. Because the spoken
cue is the only signage, a pre-gate speed warning always precedes the first
possible miss, and a real-time reaction window is honored before one latches.
"""

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


def test_terse_mode_hears_the_essential_cues(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.speech_verbosity = 0
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
