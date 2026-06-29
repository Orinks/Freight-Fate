"""State-trooper pull-overs: patrol windows, getting caught speeding, the
interactive traffic stop, immediate tickets, warnings, and evasion."""

from freight_fate.sim import Trip, TruckState, WeatherSystem
from freight_fate.sim.trip import PatrolWindow


def _trip(seed=7, hazard_scale=1.0, start_hour=12.0):
    world = __import__("freight_fate.data", fromlist=["get_world"]).get_world()
    route = world.route_options("Salt Lake City", "Las Vegas")[0]
    return Trip(route, TruckState(), WeatherSystem("great_basin", seed=1),
                seed=seed, hazard_scale=hazard_scale, start_hour=start_hour)


# --- patrol model -----------------------------------------------------------

def _patrol_key(t):
    return [(round(p.start_mi, 1), round(p.intensity, 3)) for p in t.patrols]


def test_patrol_seeding_is_deterministic():
    assert _patrol_key(_trip()) == _patrol_key(_trip())


def test_relaxed_mode_has_fewer_patrols():
    assert len(_trip(hazard_scale=0.3).patrols) <= len(_trip().patrols)


def test_construction_zones_are_always_hot_patrols():
    t = _trip()
    construction = [z for z in t.zones if z.reason == "construction"]
    if construction:
        covering = t.active_patrol_at(
            (construction[0].start_mi + construction[0].end_mi) / 2)
        assert covering is not None and covering.intensity >= 0.5


def test_active_patrol_returns_hottest_window():
    t = _trip()
    t.patrols = [PatrolWindow(0.0, 100.0, 0.3, "speed trap"),
                 PatrolWindow(0.0, 100.0, 0.8, "construction patrol")]
    assert t.active_patrol_at(50.0).intensity == 0.8
    assert t.active_patrol_at(200.0) is None


# --- driving-side: catching the speeder -------------------------------------

def _driving(app, *, patrol_intensity=1.0):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Leadfoot", current_city="Buffalo")
    route = app.ctx.world.supported_route("Buffalo", "Rochester")
    job = Job(CARGO_CATALOG["general"], 12.0, "Buffalo", "company yard",
              "Rochester", route.miles, 1000.0, 12.0,
              destination_location="Rochester freight market")
    d = DrivingState(app.ctx, job, route, phase="delivery")
    total = d.trip.total_miles
    if patrol_intensity is None:
        d.trip.patrols = []
    else:
        d.trip.patrols = [PatrolWindow(0.0, total, patrol_intensity, "speed trap")]
    return d


def _quiet(app, monkeypatch):
    monkeypatch.setattr(app.ctx, "say", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx, "say_event", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)


def _speed_for(d, over=20.0):
    from freight_fate.states.driving import SPEEDING_HOLD_S
    d.trip.position_mi = d.trip.total_miles / 2.0
    limit, _ = d.trip.speed_limit_at(d.trip.position_mi)
    d.truck.velocity_mps = (limit + over) / 2.23694
    d._update_speeding(SPEEDING_HOLD_S + 1.0)
    return limit


def test_speeding_in_a_patrol_window_starts_a_pull_over(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        _speed_for(d)
        assert d._pull_over == "lights"
        assert d.speeding_strikes == 0          # caught -> no silent strike
    finally:
        app.shutdown()


def test_metric_pull_over_announcement_uses_metric_units(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.imperial_units = False
        d = _driving(app, patrol_intensity=1.0)
        spoken = []
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: spoken.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        _speed_for(d)
        assert "kilometers per hour" in spoken[-1]
        assert "miles per hour" not in spoken[-1]
    finally:
        app.shutdown()


def test_speeding_with_no_patrol_records_a_silent_strike(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app, patrol_intensity=None)
        _quiet(app, monkeypatch)
        _speed_for(d)
        assert d._pull_over is None
        assert d.speeding_strikes == 1
    finally:
        app.shutdown()


def test_debug_off_mode_never_pulls_you_over(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        app.ctx.settings.hos_mode = "debug_off"
        _quiet(app, monkeypatch)
        _speed_for(d)
        assert d._pull_over is None
        assert d.speeding_strikes == 1
    finally:
        app.shutdown()


# --- the stop: tickets, warnings, evasion -----------------------------------

def test_stopping_issues_an_immediate_ticket(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import (
        SPEEDING_TICKET_FINES,
        TrafficStopState,
    )

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        _speed_for(d, over=25.0)            # well over -> a ticket, not a warning
        p = app.ctx.profile
        money_before = p.money
        rep_before = p.career.reputation
        d.truck.velocity_mps = 0.0          # brake to a full stop on the shoulder
        d._update_pull_over(1.0)
        assert isinstance(app.state, TrafficStopState)
        assert d.speeding_tickets == 1
        assert d.ticket_fines_paid == SPEEDING_TICKET_FINES[0]
        assert p.money == money_before - SPEEDING_TICKET_FINES[0]
        assert p.career.reputation < rep_before
    finally:
        app.shutdown()


def test_metric_traffic_stop_outcome_uses_metric_units(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import TrafficStopState

    app = App()
    try:
        app.ctx.settings.imperial_units = False
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        _speed_for(d, over=25.0)
        d.truck.velocity_mps = 0.0
        d._update_pull_over(1.0)
        assert isinstance(app.state, TrafficStopState)
        text = app.state._outcome_text
        assert "kilometers per hour" in text
        assert "miles per hour" not in text
    finally:
        app.shutdown()


def test_first_marginal_stop_is_a_warning(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        _speed_for(d, over=12.0)            # only marginally over, first stop
        p = app.ctx.profile
        money_before = p.money
        d.truck.velocity_mps = 0.0
        d._update_pull_over(1.0)
        assert d.speeding_tickets == 0      # warning, no charge
        assert p.money == money_before
    finally:
        app.shutdown()


def test_ignoring_the_lights_is_logged_as_evasion(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        limit = _speed_for(d, over=25.0)
        assert d._pull_over == "lights"
        p = app.ctx.profile
        money_before = p.money
        # Keep driving past the ignore distance without stopping.
        d.truck.velocity_mps = (limit + 25.0) / 2.23694
        d.trip.position_mi = d._pull_over_start_mi + 3.0
        d._update_pull_over(1.0)
        assert d._pull_over is None
        assert d.speeding_tickets == 1
        assert p.money < money_before
    finally:
        app.shutdown()


def test_ticket_counters_survive_snapshot(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        d.speeding_tickets = 2
        d.ticket_fines_paid = 450.0
        app.ctx.profile.active_trip = None
        snap = d.snapshot()
        restored = DrivingState.from_snapshot(app.ctx, snap)
        assert restored is not None
        assert restored.speeding_tickets == 2
        assert restored.ticket_fines_paid == 450.0
    finally:
        app.shutdown()
