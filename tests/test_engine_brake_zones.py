"""No-engine-brake zones: towns ban the jake by local noise ordinance.

There is no state or federal law against engine braking; the restriction is
municipal, posted at the city limits, with the descent and emergency uses of
the retarder staying legitimate everywhere. The game maps those ordinances
onto the same urban radius that lowers the speed limit near a route city, and
-- because the spoken cue is the sign -- always warns before the first fine.
"""

from speech_capture import speech_stub


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Jake", current_city="Buffalo")
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


class _NoKeys:
    def __getitem__(self, _key):
        return False


def _capture_events(app, monkeypatch):
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    return spoken


def _roll_with_jake(d, monkeypatch, *, mile: float, grade: float = 0.0) -> None:
    """Put the truck at ``mile``, rolling at road speed with the jake on."""
    d.trip.position_mi = mile
    d.truck.engine_on = True
    d.truck.transmission.gear = 8
    d.truck.throttle = 0.0
    d.truck.velocity_mps = 55.0 / 2.23694
    d.truck.engine_brake = True
    monkeypatch.setattr(d.trip, "grade_at", lambda mile: grade)


def test_zone_violation_warns_before_any_fine(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        money = app.ctx.profile.money
        _roll_with_jake(d, monkeypatch, mile=2.0)  # inside the Buffalo zone
        d._update_engine_brake_zone(0.1)
        assert d.jake_zone_fines == 0
        assert app.ctx.profile.money == money
        assert "No engine brakes" in spoken[-1]
        assert "Buffalo" in spoken[-1]
    finally:
        app.shutdown()


def test_keeping_the_jake_on_past_the_grace_draws_a_fine(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_engine_brake import (
        JAKE_ZONE_FINES,
        JAKE_ZONE_GRACE_S,
    )

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        money = app.ctx.profile.money
        _roll_with_jake(d, monkeypatch, mile=2.0)
        d._update_engine_brake_zone(0.1)  # warning
        d._update_engine_brake_zone(JAKE_ZONE_GRACE_S + 1.0)  # grace expires
        assert d.jake_zone_fines == 1
        assert app.ctx.profile.money == money - JAKE_ZONE_FINES[0]
        assert f"{JAKE_ZONE_FINES[0]:,.0f} dollar" in spoken[-1]
        assert "engine braking" in spoken[-1]
    finally:
        app.shutdown()


def test_switching_off_within_the_grace_avoids_the_fine(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_engine_brake import JAKE_ZONE_GRACE_S

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        _roll_with_jake(d, monkeypatch, mile=2.0)
        d._update_engine_brake_zone(0.1)  # warning
        d.truck.engine_brake = False  # driver complies
        d._update_engine_brake_zone(JAKE_ZONE_GRACE_S + 5.0)
        assert d.jake_zone_fines == 0
    finally:
        app.shutdown()


def test_descent_grade_is_exempt(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_engine_brake import JAKE_ZONE_GRACE_S

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _roll_with_jake(d, monkeypatch, mile=2.0, grade=-0.04)  # 4 percent down
        d._update_engine_brake_zone(0.1)
        d._update_engine_brake_zone(JAKE_ZONE_GRACE_S + 5.0)
        assert d.jake_zone_fines == 0
        assert spoken == []
    finally:
        app.shutdown()


def test_open_road_jake_use_stays_free(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_engine_brake import JAKE_ZONE_GRACE_S

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _roll_with_jake(d, monkeypatch, mile=d.trip.total_miles / 2.0)
        d._update_engine_brake_zone(JAKE_ZONE_GRACE_S + 5.0)
        assert d.jake_zone_fines == 0
        assert spoken == []
    finally:
        app.shutdown()


def test_hazard_emergency_is_exempt(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_engine_brake import JAKE_ZONE_GRACE_S

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _roll_with_jake(d, monkeypatch, mile=2.0)
        d._hazard_deadline = 6.0  # braking for a live hazard warning
        d._update_engine_brake_zone(0.1)
        d._update_engine_brake_zone(JAKE_ZONE_GRACE_S + 5.0)
        assert d.jake_zone_fines == 0
        assert spoken == []
    finally:
        app.shutdown()


def test_cruise_jake_releases_entering_a_zone_with_a_spoken_reason(monkeypatch):
    # A real driver flips engine-brake mode off coming into town; cruise now
    # does the same, telling the player once why the retarder note stopped.
    from freight_fate.app import App
    from freight_fate.states.driving_engine_brake import JAKE_ZONE_GRACE_S

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _roll_with_jake(d, monkeypatch, mile=2.0)
        d._cruise_jake_stage = 3  # automation raised it, not the driver's stalk
        d._update_engine_brake_zone(0.1)
        assert d.truck.engine_brake_stage == 0
        assert d._cruise_jake_stage == 0
        assert "Cruise is holding the engine brake off" in spoken[-1]
        assert "Buffalo" in spoken[-1]
        d._update_engine_brake_zone(JAKE_ZONE_GRACE_S + 5.0)
        assert d.jake_zone_fines == 0
    finally:
        app.shutdown()


def test_curve_assist_jake_releases_in_zone_with_its_own_reason(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_engine_brake import JAKE_ZONE_GRACE_S

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _roll_with_jake(d, monkeypatch, mile=2.0)
        d._curve_assist_jake = True  # the assist engaged it for a bend
        d._update_engine_brake_zone(0.1)
        assert d.truck.engine_brake_stage == 0
        assert d._curve_assist_jake is False
        assert "curve assist is using the brakes" in spoken[-1]
        d._update_engine_brake_zone(JAKE_ZONE_GRACE_S + 5.0)
        assert d.jake_zone_fines == 0
    finally:
        app.shutdown()


def test_assist_zone_cue_speaks_once_per_zone_and_never_in_terse(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _roll_with_jake(d, monkeypatch, mile=2.0)
        d._cruise_jake_stage = 3
        d._update_engine_brake_zone(0.1)
        assert len(spoken) == 1
        # Cruise tries the retarder again further into the same zone.
        d.truck.engine_brake = True
        d._cruise_jake_stage = 2
        d._update_engine_brake_zone(0.1)
        assert d.truck.engine_brake_stage == 0
        assert len(spoken) == 1  # released again, said nothing new

        terse = _driving(app)
        terse_spoken = _capture_events(app, monkeypatch)
        monkeypatch.setattr(terse, "_terse_speech", lambda: True)
        _roll_with_jake(terse, monkeypatch, mile=2.0)
        terse._cruise_jake_stage = 3
        terse._update_engine_brake_zone(0.1)
        assert terse.truck.engine_brake_stage == 0  # still released
        assert terse_spoken == []  # advisory-class: terse stays quiet
    finally:
        app.shutdown()


def test_cruise_keeps_its_jake_in_zone_on_a_real_downgrade(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _roll_with_jake(d, monkeypatch, mile=2.0, grade=-0.04)
        d._cruise_jake_stage = 3
        d._update_engine_brake_zone(0.1)
        assert d.truck.engine_brake_stage > 0  # safety wins over the ordinance
        assert d._cruise_jake_stage == 3
        assert spoken == []
    finally:
        app.shutdown()


def test_assists_may_not_raise_the_jake_inside_a_zone(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        _roll_with_jake(d, monkeypatch, mile=2.0)
        d.truck.engine_brake = False
        assert d._assist_jake_allowed() is False  # flat ground in town
        monkeypatch.setattr(d.trip, "grade_at", lambda mile: -0.04)
        assert d._assist_jake_allowed() is True  # a real downgrade is exempt
        monkeypatch.setattr(d.trip, "grade_at", lambda mile: 0.0)
        d.trip.position_mi = d.trip.total_miles / 2.0
        assert d._assist_jake_allowed() is True  # open road
    finally:
        app.shutdown()


def test_curve_assist_takes_the_drums_for_a_corner_inside_a_zone(monkeypatch):
    """The sign outranks the corner.

    How much speed a corner needs off decides whether the retarder is worth
    reaching for; the posted no engine brake zone decides whether it is
    available at all. A bend in town with twenty mph to shed is still
    slowed, on the service brakes.
    """
    from freight_fate.app import App
    from freight_fate.data.curves import RouteCurve

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        _roll_with_jake(d, monkeypatch, mile=2.0)  # inside the Buffalo zone
        d.truck.engine_brake = False
        d.truck.rpm = 1500.0
        d.truck.grip = 1.0
        d.truck.brake = 0.0
        curve = RouteCurve(
            start_mi=2.0,
            apex_mi=2.1,
            end_mi=2.2,
            direction="L",
            advisory_mph=35,  # twenty under the truck's 55
            min_radius_ft=1200,
            deflection_deg=40.0,
        )
        monkeypatch.setattr(d.trip, "curve_at", lambda _mile: curve)
        d._update_lane(_NoKeys(), 1 / 60)
        assert d.truck.engine_brake_stage == 0
        assert d._curve_assist_jake is False
        assert d.truck.brake > 0.0
    finally:
        app.shutdown()


def test_cruise_snubs_with_service_brakes_instead_of_the_jake_in_zone(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        _roll_with_jake(d, monkeypatch, mile=2.0)
        d.truck.engine_brake = False
        d.truck.brake = 0.0
        d._auto_jake = False
        # Four over the target on flat ground inside the zone: the retarder
        # stays quiet and the drums take the snub instead.
        d._hold_cruise_from_above(0.1, -4.0, closing=False)
        assert d.truck.engine_brake_stage == 0
        assert d._cruise_jake_stage == 0
        assert d.truck.brake > 0.0
    finally:
        app.shutdown()


def test_one_citation_per_continuous_engagement(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_engine_brake import JAKE_ZONE_GRACE_S

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        _roll_with_jake(d, monkeypatch, mile=2.0)
        d._update_engine_brake_zone(0.1)
        d._update_engine_brake_zone(JAKE_ZONE_GRACE_S + 1.0)
        assert d.jake_zone_fines == 1
        # Still on, still in the zone: the citation is written, not repeated.
        for _ in range(10):
            d._update_engine_brake_zone(JAKE_ZONE_GRACE_S + 1.0)
        assert d.jake_zone_fines == 1
    finally:
        app.shutdown()


def test_fines_escalate_and_cap(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_engine_brake import (
        JAKE_ZONE_FINES,
        JAKE_ZONE_GRACE_S,
    )

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        money = app.ctx.profile.money
        _roll_with_jake(d, monkeypatch, mile=2.0)
        for _ in range(4):
            d.truck.engine_brake = True
            d._update_engine_brake_zone(0.1)  # fresh warning
            d._update_engine_brake_zone(JAKE_ZONE_GRACE_S + 1.0)  # fine
            d.truck.engine_brake = False
            d._update_engine_brake_zone(0.1)  # engagement ends
        assert d.jake_zone_fines == 4
        expected = sum(JAKE_ZONE_FINES) + JAKE_ZONE_FINES[-1]
        assert app.ctx.profile.money == money - expected
        assert d.jake_fines_paid == expected
    finally:
        app.shutdown()


def test_approach_callout_when_the_jake_is_on(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_engine_brake import JAKE_ZONE_WARN_MI

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        # Just short of the Rochester zone, retarder on from the open road.
        from freight_fate.sim.trip_models import URBAN_RADIUS_MI

        start_mi = d.trip.total_miles - URBAN_RADIUS_MI
        _roll_with_jake(d, monkeypatch, mile=start_mi - JAKE_ZONE_WARN_MI / 2.0)
        d._update_engine_brake_zone(0.1)
        assert len(spoken) == 1
        assert "No engine brake zone" in spoken[0]
        assert "Rochester" in spoken[0]
        d._update_engine_brake_zone(0.1)  # said once, not every frame
        assert len(spoken) == 1
    finally:
        app.shutdown()


def test_no_approach_callout_with_the_jake_off(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving_engine_brake import JAKE_ZONE_WARN_MI

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        from freight_fate.sim.trip_models import URBAN_RADIUS_MI

        start_mi = d.trip.total_miles - URBAN_RADIUS_MI
        _roll_with_jake(d, monkeypatch, mile=start_mi - JAKE_ZONE_WARN_MI / 2.0)
        d.truck.engine_brake = False
        d._update_engine_brake_zone(0.1)
        assert spoken == []
    finally:
        app.shutdown()


def test_terse_speech_still_hears_the_violation_warning(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.speech_verbosity = 0
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _roll_with_jake(d, monkeypatch, mile=2.0)
        d._update_engine_brake_zone(0.1)
        assert spoken, "terse mode must still hear the warning that gates the fine"
        assert "No engine brake zone" in spoken[-1]
    finally:
        app.shutdown()


def test_snapshot_round_trips_the_citations(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        d.jake_zone_fines = 2
        d.jake_fines_paid = 450.0
        resumed = DrivingState.from_snapshot(app.ctx, d.snapshot())
        assert resumed is not None
        assert resumed.jake_zone_fines == 2
        assert resumed.jake_fines_paid == 450.0
    finally:
        app.shutdown()
