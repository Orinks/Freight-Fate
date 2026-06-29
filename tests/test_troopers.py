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


def test_patrol_windows_create_state_trooper_npcs():
    t = _trip()

    troopers = [
        vehicle for vehicle in t.traffic_manager.vehicles
        if getattr(vehicle, "vehicle_class", "") == "state trooper"
    ]

    assert t.patrols
    assert len(troopers) == len(t.patrols)
    assert all(vehicle.reason == "state trooper ahead" for vehicle in troopers)


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
    t.patrols = [PatrolWindow(0.0, 100.0, 0.3, "highway enforcement"),
                 PatrolWindow(0.0, 100.0, 0.8, "work zone enforcement")]
    assert t.active_patrol_at(50.0).intensity == 0.8
    assert t.active_patrol_at(200.0) is None


def test_cb_radio_warns_before_upcoming_patrol():
    from freight_fate.sim.trip import CB_PATROL_LOOKAHEAD_MI, TripEventKind

    t = _trip()
    t.patrols = [PatrolWindow(10.0, 14.0, 0.8, "highway enforcement")]
    t.position_mi = 10.0 - CB_PATROL_LOOKAHEAD_MI + 0.1
    t.truck.velocity_mps = 1.0

    events = t.update(0.1)

    cb_events = [e for e in events if e.data.get("cb_patrol") is t.patrols[0]]
    assert cb_events
    assert cb_events[0].kind == TripEventKind.GPS_CUE
    assert "drivers report a bear ahead" in cb_events[0].message
    assert "check your speed" in cb_events[0].message


def test_cb_radio_patrol_warning_only_fires_once():
    t = _trip()
    t.patrols = [PatrolWindow(10.0, 14.0, 0.8, "highway enforcement")]
    t.position_mi = 6.0
    t.truck.velocity_mps = 1.0

    first = t.update(0.1)
    second = t.update(0.1)

    assert sum(1 for e in first if e.data.get("cb_patrol") is t.patrols[0]) == 1
    assert not any(e.data.get("cb_patrol") is t.patrols[0] for e in second)


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
        d.trip.patrols = [
            PatrolWindow(0.0, total, patrol_intensity, "highway enforcement")
        ]
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
    from freight_fate.states.driving import FAILURE_TO_STOP_FINE, FelonyStopState

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        limit = _speed_for(d, over=25.0)
        assert d._pull_over == "lights"
        p = app.ctx.profile
        money_before = p.money
        rep_before = p.career.reputation
        # Keep driving past the ignore distance without stopping.
        d.truck.velocity_mps = (limit + 25.0) / 2.23694
        d.trip.position_mi = d._pull_over_start_mi + 3.0
        d._update_pull_over(1.0)
        assert isinstance(app.state, FelonyStopState)
        assert d._pull_over is None
        assert d.failure_to_stop_count == 1
        assert d.ticket_fines_paid == FAILURE_TO_STOP_FINE
        assert p.money == money_before - FAILURE_TO_STOP_FINE
        assert p.career.reputation < rep_before
    finally:
        app.shutdown()


def test_failure_to_stop_gives_staged_warnings(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        d = _driving(app, patrol_intensity=1.0)
        monkeypatch.setattr(app.ctx, "say", lambda *a, **k: None)
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, *a, **k: spoken.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        limit = _speed_for(d, over=25.0)
        d.truck.velocity_mps = (limit + 25.0) / 2.23694

        d.trip.position_mi = d._pull_over_start_mi + 0.9
        d._update_pull_over(1.0)
        d.trip.position_mi = d._pull_over_start_mi + 1.6
        d._update_pull_over(1.0)

        assert any("Failure-to-stop warning" in s for s in spoken)
        assert any("Final failure-to-stop warning" in s for s in spoken)
        assert d.failure_to_stop_count == 0
    finally:
        app.shutdown()


def test_failure_to_stop_warning_acknowledges_signal(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        d = _driving(app, patrol_intensity=1.0)
        monkeypatch.setattr(app.ctx, "say", lambda text, *a, **k: spoken.append(text))
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, *a, **k: spoken.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        limit = _speed_for(d, over=25.0)
        d._signal_pull_over()
        d.truck.velocity_mps = (limit + 25.0) / 2.23694

        d.trip.position_mi = d._pull_over_start_mi + 0.9
        d._update_pull_over(1.0)

        assert any("You signaled for the stop" in s for s in spoken)
        assert d.failure_to_stop_count == 0
    finally:
        app.shutdown()


def test_felony_stop_cancels_loaded_run_and_returns_to_terminal(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState
    from freight_fate.states.driving import FelonyStopState

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        _speed_for(d, over=25.0)
        app.ctx.profile.active_trip = d.snapshot()
        damage_before = d.truck.damage_pct
        game_hours_before = app.ctx.profile.game_hours

        d.trip.position_mi = d._pull_over_start_mi + 3.0
        d.truck.velocity_mps = 65.0 / 2.23694
        d._update_pull_over(1.0)

        assert isinstance(app.state, FelonyStopState)
        assert app.state.load_lost is True
        assert app.ctx.profile.active_trip is None
        assert app.ctx.profile.truck_damage_pct > damage_before
        assert app.ctx.profile.game_hours > game_hours_before

        app.state.go_back()
        assert isinstance(app.state, CityMenuState)
    finally:
        app.shutdown()


def test_felony_stop_does_not_claim_load_loss_for_empty_run(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import FelonyStopState

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        d.job.bobtail = True
        _speed_for(d, over=25.0)

        d.trip.position_mi = d._pull_over_start_mi + 3.0
        d.truck.velocity_mps = 65.0 / 2.23694
        d._update_pull_over(1.0)

        assert isinstance(app.state, FelonyStopState)
        assert app.state.load_lost is False
    finally:
        app.shutdown()


def test_debug_off_mode_clears_active_pull_over_without_felony(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        _speed_for(d, over=25.0)
        app.ctx.settings.hos_mode = "debug_off"

        d.trip.position_mi = d._pull_over_start_mi + 3.0
        d.truck.velocity_mps = 65.0 / 2.23694
        d._update_pull_over(1.0)

        assert d._pull_over is None
        assert d.failure_to_stop_count == 0
    finally:
        app.shutdown()


def test_weigh_station_blow_past_starts_enforcement_stop(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import RoadStop
    from freight_fate.states.driving import (
        WEIGH_STATION_BYPASS_FINE,
        EnforcementStopState,
    )

    app = App()
    try:
        d = _driving(app, patrol_intensity=None)
        _quiet(app, monkeypatch)
        d.trip.stops = [
            RoadStop("Ontario Scale", 10.0, "weigh_station", ("inspect",))
        ]
        d.trip.position_mi = 10.1
        d.truck.velocity_mps = 55.0 / 2.23694

        d._check_weigh_station_enforcement(9.9)

        assert d._pull_over == "lights"
        assert d._pull_over_kind == "weigh_station_bypass"

        money_before = app.ctx.profile.money
        rep_before = app.ctx.profile.career.reputation
        d.truck.velocity_mps = 0.0
        d._update_pull_over(1.0)
        assert isinstance(app.state, EnforcementStopState)
        assert d.ticket_fines_paid == WEIGH_STATION_BYPASS_FINE
        assert app.ctx.profile.money == money_before - WEIGH_STATION_BYPASS_FINE
        assert app.ctx.profile.career.reputation < rep_before
    finally:
        app.shutdown()


def test_weigh_station_warning_is_spoken_before_bypass(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import RoadStop

    app = App()
    spoken = []
    try:
        d = _driving(app, patrol_intensity=None)
        monkeypatch.setattr(app.ctx, "say", lambda *a, **k: None)
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, *a, **k: spoken.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        d.trip.stops = [
            RoadStop("Ontario Scale", 10.0, "weigh_station", ("inspect",))
        ]
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 45.0 / 2.23694

        d._check_weigh_station_enforcement(8.0)
        d._check_weigh_station_enforcement(8.1)

        assert len([s for s in spoken if "Open weigh station ahead" in s]) == 1
        assert "press T for inspection check-in" in spoken[0]
    finally:
        app.shutdown()


def test_debug_off_mode_bypasses_scale_blow_past(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import RoadStop

    app = App()
    try:
        d = _driving(app, patrol_intensity=None)
        app.ctx.settings.hos_mode = "debug_off"
        _quiet(app, monkeypatch)
        d.trip.stops = [
            RoadStop("Ontario Scale", 10.0, "weigh_station", ("inspect",))
        ]
        d.trip.position_mi = 10.1
        d.truck.velocity_mps = 55.0 / 2.23694

        d._check_weigh_station_enforcement(9.9)

        assert d._pull_over is None
        assert not d.enforcement_events
    finally:
        app.shutdown()


def test_scale_bypass_does_not_overwrite_active_pull_over(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import RoadStop

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        limit = _speed_for(d, over=25.0)
        assert d._pull_over == "lights"
        d.trip.stops = [
            RoadStop("Ontario Scale", 10.0, "weigh_station", ("inspect",))
        ]
        d.trip.position_mi = 10.1
        d.truck.velocity_mps = (limit + 25.0) / 2.23694

        d._check_weigh_station_enforcement(9.9)

        assert d._pull_over == "lights"
        assert d._pull_over_kind == "speeding"
    finally:
        app.shutdown()


def test_unsafe_damage_in_patrol_starts_safety_stop(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import UNSAFE_DAMAGE_FINE

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        d.trip.position_mi = d.trip.total_miles / 2.0
        d.truck.damage_pct = 70.0
        d.truck.velocity_mps = 35.0 / 2.23694

        d._check_unsafe_damage_enforcement()

        assert d._pull_over == "lights"
        assert d._pull_over_kind == "unsafe_damage"
        money_before = app.ctx.profile.money
        d.truck.velocity_mps = 0.0
        d._update_pull_over(1.0)
        assert d.ticket_fines_paid == UNSAFE_DAMAGE_FINE
        assert app.ctx.profile.money == money_before - UNSAFE_DAMAGE_FINE
    finally:
        app.shutdown()


def test_unsafe_damage_needs_active_enforcement(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app, patrol_intensity=None)
        _quiet(app, monkeypatch)
        d.truck.damage_pct = 85.0
        d.truck.velocity_mps = 35.0 / 2.23694

        d._check_unsafe_damage_enforcement()

        assert d._pull_over is None
        assert not d.enforcement_events
    finally:
        app.shutdown()


def test_f1_help_names_non_speed_enforcement_pullovers(monkeypatch):
    import pygame

    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        d = _driving(app, patrol_intensity=None)
        monkeypatch.setattr(app.ctx, "say", lambda text, *a, **k: spoken.append(text))
        monkeypatch.setattr(app.ctx, "say_event", lambda *a, **k: None)
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)

        d.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_F1}))

        assert spoken
        assert "scale bypass, or unsafe equipment" in spoken[-1]
        assert "signal, then brake to a stop" in spoken[-1]
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
        d.failure_to_stop_count = 1
        app.ctx.profile.active_trip = None
        snap = d.snapshot()
        restored = DrivingState.from_snapshot(app.ctx, snap)
        assert restored is not None
        assert restored.speeding_tickets == 2
        assert restored.ticket_fines_paid == 450.0
        assert restored.failure_to_stop_count == 1
    finally:
        app.shutdown()
