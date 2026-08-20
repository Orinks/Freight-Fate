"""Trooper pull-overs: enforcement posts, being observed speeding, the
interactive roadside pull-over, immediate tickets, warnings, and evasion."""

import pytest
from enforcement_helpers import always_observing_post, open_scale_post, watch_speed
from speech_capture import speech_stub

from freight_fate.sim import Trip, TruckState, WeatherSystem


def _trip(seed=7, hazard_scale=1.0, start_hour=12.0):
    world = __import__("freight_fate.data", fromlist=["get_world"]).get_world()
    route = world.route_options("Salt Lake City", "Las Vegas")[0]
    return Trip(
        route,
        TruckState(),
        WeatherSystem("great_basin", seed=1),
        seed=seed,
        hazard_scale=hazard_scale,
        start_hour=start_hour,
    )


# --- post model -------------------------------------------------------------


def _post_key(t):
    return [(round(p.at_mi, 1), p.kind, p.staffed) for p in t.posts]


def test_post_seeding_is_deterministic():
    assert _post_key(_trip()) == _post_key(_trip())


def test_roving_posts_create_state_trooper_npcs():
    t = _trip()

    troopers = [
        vehicle
        for vehicle in t.traffic_manager.vehicles
        if getattr(vehicle, "vehicle_class", "") == "state trooper"
    ]
    roving = [p for p in t.posts if p.kind == "roving_patrol" and p.staffed]

    assert t.posts
    assert len(troopers) == len(roving)
    assert all(vehicle.reason == "state trooper ahead" for vehicle in troopers)


def test_relaxed_hazards_do_not_thin_the_police():
    """A calmer hazard setting must not empty the roads of enforcement.

    Presence is a fact about the country, not a difficulty knob: hazard_scale
    used to divide the patrol count, so relaxed mode drove through a state
    with one patrol window in six hundred miles.
    """
    assert len(_trip(hazard_scale=0.3).posts) == len(_trip().posts)


def test_construction_zones_always_carry_a_work_zone_post():
    t = _trip()
    construction = [z for z in t.zones if z.reason == "construction"]
    if construction:
        zone = construction[0]
        covering = [
            p for p in t.posts if p.kind == "work_zone_post" and abs(p.at_mi - zone.start_mi) < 1.0
        ]
        assert covering


def test_active_post_returns_the_most_attentive_watcher():
    t = _trip()
    quiet = always_observing_post(at_mi=50.0, kind="urban_unit", notice=0.3)
    loud = always_observing_post(at_mi=50.0, kind="work_zone_post", notice=0.9)
    t.posts = [quiet, loud]
    assert t.active_post_at(50.0) is loud
    assert t.active_post_at(2000.0) is None


def test_cb_radio_warns_before_an_upcoming_post():
    from freight_fate.sim.trip import TripEventKind

    t = _trip()
    t.posts = [always_observing_post(at_mi=14.0, reach_mi=4.0)]
    t.position_mi = 10.0 - 0.1
    t.truck.velocity_mps = 1.0

    events = t.update(0.1)

    cb_events = [e for e in events if e.data.get("cb_patrol") is t.posts[0]]
    assert cb_events
    assert cb_events[0].kind == TripEventKind.GPS_CUE
    assert "CB chatter" in cb_events[0].message
    assert "bear" in cb_events[0].message


def test_cb_radio_post_warning_only_fires_once():
    t = _trip()
    t.posts = [always_observing_post(at_mi=14.0, reach_mi=4.0)]
    t.position_mi = 6.0
    t.truck.velocity_mps = 1.0

    first = t.update(0.1)
    second = t.update(0.1)

    assert sum(1 for e in first if e.data.get("cb_patrol") is t.posts[0]) == 1
    assert not any(e.data.get("cb_patrol") is t.posts[0] for e in second)


# --- driving-side: catching the speeder -------------------------------------


def _driving(app, *, patrol_intensity=1.0):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Leadfoot", current_city="Buffalo")
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
    total = d.trip.total_miles
    if patrol_intensity is None:
        d.trip.posts = []
    else:
        # One post that watches the whole route and has already been heard,
        # so a test can put the truck anywhere and ask what it sees.
        d.trip.posts = [
            always_observing_post(at_mi=total, reach_mi=total + 1.0, notice=patrol_intensity)
        ]
    return d


def _quiet(app, monkeypatch):
    monkeypatch.setattr(app.ctx, "say", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx, "say_event", lambda *a, **k: None)
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)


def _speed_for(d, over=20.0):
    """Speed past a watching post far enough for it to read the speed.

    Observation is distance-quantised now, not held on the wall clock, so
    the setup is "the truck has run this far over the limit", not "this many
    real seconds have passed".
    """
    return watch_speed(d, over=over)


def _past_grace(d):
    """Skip the spoken-instruction grace so a test can judge the tracker.

    Nothing about the stop is judged until the trigger message has had time
    to be read out; every test below that exercises compliance is asking
    about what happens after that.
    """
    d._pull_over_grace_s = 0.0


def test_speeding_past_a_staffed_post_starts_a_pull_over(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        _speed_for(d)
        assert d._pull_over == "lights"
        assert d.speeding_tickets == 0  # the ticket is written at the stop, not here
    finally:
        app.shutdown()


def test_metric_pull_over_announcement_uses_metric_units(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.imperial_units = False
        d = _driving(app, patrol_intensity=1.0)
        spoken = []
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        _speed_for(d)
        assert "kilometers per hour" in spoken[-1]
        assert "miles per hour" not in spoken[-1]
    finally:
        app.shutdown()


def test_speeding_with_no_post_watching_costs_nothing(monkeypatch):
    """Getting away with it is the intended outcome, not a gap.

    This used to assert a silent strike was banked for the dock. There is no
    such thing any more: an empty road charges nothing, which is both honest
    and what happens on a real one.
    """
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app, patrol_intensity=None)
        _quiet(app, monkeypatch)
        money_before = app.ctx.profile.money
        _speed_for(d)
        assert d._pull_over is None
        assert d.speeding_tickets == 0
        assert app.ctx.profile.money == money_before
        assert app.ctx.profile.fines_owed == 0.0
    finally:
        app.shutdown()


def test_debug_off_mode_never_pulls_you_over(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        app.ctx.settings.hos_mode = "debug_off"
        _quiet(app, monkeypatch)
        money_before = app.ctx.profile.money
        _speed_for(d)
        assert d._pull_over is None
        assert d.speeding_tickets == 0
        assert app.ctx.profile.money == money_before
    finally:
        app.shutdown()


# --- the stop: tickets, warnings, evasion -----------------------------------


def test_stopping_issues_an_immediate_ticket(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.enforcement import speeding_citation_fine
    from freight_fate.states.driving import TrafficStopState

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        _speed_for(d, over=25.0)  # well over -> a ticket, not a warning
        p = app.ctx.profile
        money_before = p.money
        rep_before = p.career.reputation
        d.truck.velocity_mps = 0.0  # brake to a full stop on the shoulder
        d._update_pull_over(1.0)
        assert isinstance(app.state, TrafficStopState)
        assert d.speeding_tickets == 1
        expected = speeding_citation_fine(
            app.state.over, 0, construction_zone=app.state.construction_zone
        )
        assert d.ticket_fines_paid == expected
        assert p.money == money_before - expected
        assert p.career.reputation < rep_before
        # 25 over is a serious traffic violation, and the record says so.
        assert p.driving_record.serious_in_window(p.game_hours) == 1
    finally:
        app.shutdown()


def test_stopping_drops_engine_audio_to_idle(monkeypatch):
    """The engine keeps running through a traffic stop -- you are pulled over
    on the shoulder, not parked for the night -- but the engine loop must not
    keep sounding like it is still under highway load once the truck is
    actually at rest (tester report, build 1.9.0.dev0)."""
    from freight_fate.app import App
    from freight_fate.states.driving import TrafficStopState

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        samples = []
        monkeypatch.setattr(
            app.ctx.audio,
            "set_engine_rpm",
            lambda rpm, throttle=0.0: samples.append((rpm, throttle)),
        )
        d.truck.engine_on = True
        # Whatever the engine was doing while braking to the stop -- still
        # revving, still carrying some throttle.
        d.truck.rpm = 1800.0
        d.truck.throttle = 0.7
        _speed_for(d, over=25.0)
        d.truck.velocity_mps = 0.0  # brake to a full stop on the shoulder
        d._update_pull_over(1.0)
        assert isinstance(app.state, TrafficStopState)
        # The engine stays on: this is a traffic stop, not an overnight park.
        assert d.truck.engine_on is True
        # But it reads as idle the instant the stop opens.
        idle_rpm = d.truck.specs.idle_rpm
        assert d.truck.rpm == pytest.approx(idle_rpm)
        assert d.truck.throttle == 0.0
        assert samples
        assert samples[-1] == (pytest.approx(idle_rpm), 0.0)
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
        _speed_for(d, over=12.0)  # only marginally over, first stop
        p = app.ctx.profile
        money_before = p.money
        d.truck.velocity_mps = 0.0
        d._update_pull_over(1.0)
        assert d.speeding_tickets == 0  # warning, no charge
        assert p.money == money_before
    finally:
        app.shutdown()


class _Roll:
    """A stand-in RNG with a fixed .random() value for deterministic rolls."""

    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


def test_accelerating_away_ends_in_a_forced_stop_not_a_felony(monkeypatch):
    """Not stopping is not running: troopers force it and write a citation.

    Reaching a felony by never braking used to be possible in about five
    seconds, while the trigger message was still being spoken. A pursuit is
    now only reachable by holding the run key on purpose.
    """
    from freight_fate.app import App
    from freight_fate.models.enforcement import FAILURE_TO_STOP_CITATION_FINE
    from freight_fate.states.driving import EnforcementStopState, FelonyStopState

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        limit = _speed_for(d, over=25.0)
        assert d._pull_over == "lights"
        _past_grace(d)
        p = app.ctx.profile
        money_before = p.money
        rep_before = p.career.reputation
        base = (limit + 25.0) / 2.23694
        for i in range(40):
            d.truck.velocity_mps = base + (i + 1) * 1.0 / 2.23694
            d._update_pull_over(1.0)
            if d._pull_over is None:
                break
        assert not isinstance(app.state, FelonyStopState)
        assert isinstance(app.state, EnforcementStopState)
        assert d.failure_to_stop_count == 0  # no pursuit was ever started
        assert d.truck.velocity_mps == 0.0  # and the truck is actually stopped
        assert p.money < money_before
        assert p.career.reputation < rep_before
        assert app.state.fine >= FAILURE_TO_STOP_CITATION_FINE
        # It is still a serious violation on the record.
        assert p.driving_record.serious_in_window(p.game_hours) >= 1
    finally:
        app.shutdown()


def test_a_compliant_driver_is_never_charged_with_running(monkeypatch):
    """Steady speed, no signal, cruise engaged, realistic pacing: no felony.

    This is the exact shape of a player who is listening to the instruction.
    The old tracker convicted them at about 5.07 seconds.
    """
    from freight_fate.app import App
    from freight_fate.states.driving import FelonyStopState

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        limit = _speed_for(d, over=25.0)
        assert d._pull_over is not None
        # Lighting a driver up hands the wheel back rather than leaving an
        # assist holding a steady speed into the drain.
        assert d._cruise_mph is None
        assert d.trip.pull_over_active  # and the clock stops compressing
        speed = (limit + 25.0) / 2.23694
        for _ in range(10):
            d.truck.velocity_mps = speed  # dead steady, never signalled
            d._update_pull_over(1.0)
        assert not isinstance(app.state, FelonyStopState)
        assert d.failure_to_stop_count == 0
    finally:
        app.shutdown()


def test_failure_to_stop_gives_staged_warnings(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    try:
        d = _driving(app, patrol_intensity=1.0)
        monkeypatch.setattr(app.ctx, "say", lambda *a, **k: None)
        monkeypatch.setattr(app.ctx, "say_event", lambda text, *a, **k: spoken.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        limit = _speed_for(d, over=25.0)
        _past_grace(d)
        d.truck.velocity_mps = (limit + 25.0) / 2.23694

        # The warnings run on real seconds now, not trip miles: compression
        # could burn through two miles before the first could ever speak.
        for _ in range(9):
            d._update_pull_over(1.0)
        assert any("Failure-to-stop warning" in s for s in spoken)
        for _ in range(8):
            d._update_pull_over(1.0)
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
        monkeypatch.setattr(app.ctx, "say_event", lambda text, *a, **k: spoken.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        limit = _speed_for(d, over=25.0)
        d._signal_pull_over()
        _past_grace(d)
        d.truck.velocity_mps = (limit + 25.0) / 2.23694

        for _ in range(9):
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

        # Only a deliberate held opt-in starts a pursuit.
        d._evade_pull_over()

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
        d._evade_pull_over()

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
    from freight_fate.models.enforcement import WEIGH_STATION_BYPASS_FINE, citation_fine
    from freight_fate.sim.trip import RoadStop
    from freight_fate.states.driving import INSPECTION_MIN, EnforcementStopState

    app = App()
    try:
        d = _driving(app, patrol_intensity=None)
        # A bypass is caught, not certain -- seed 1 lands under the 85 percent
        # catch chance for this exact scale key, so the stop is deterministic.
        d.trip_seed = 1
        _quiet(app, monkeypatch)
        d.trip.stops = [RoadStop("Ontario Scale", 10.0, "weigh_station", ("inspect",))]
        d.trip.posts = [*d.trip.posts, open_scale_post(d.trip.stops[0])]
        d.trip.position_mi = 10.1
        d.truck.velocity_mps = 55.0 / 2.23694

        d._check_weigh_station_enforcement(9.9)

        assert d._pull_over == "lights"
        assert d._pull_over_kind == "weigh_station_bypass"

        money_before = app.ctx.profile.money
        rep_before = app.ctx.profile.career.reputation
        citations_before = app.ctx.profile.driving_record.citations
        minutes_before = d.trip.game_minutes
        d.truck.velocity_mps = 0.0
        d._update_pull_over(1.0)
        assert isinstance(app.state, EnforcementStopState)
        # A clean career on open road: the base amount, unscaled. Asked of the
        # helper rather than hardcoded, so a rebalance moves one number.
        expected = citation_fine(
            WEIGH_STATION_BYPASS_FINE, 0, construction_zone=app.state.construction_zone
        )
        assert d.ticket_fines_paid == expected
        assert app.ctx.profile.money == money_before - expected
        assert app.ctx.profile.career.reputation < rep_before
        # Recorded on the driving record like any other citation.
        assert app.ctx.profile.driving_record.citations == citations_before + 1
        # Dodging the check-in lane does not dodge the inspection: the trooper
        # runs it right there, on the same clock the scale itself would cost.
        assert d.trip.game_minutes == minutes_before + INSPECTION_MIN
        assert "full inspection" in app.state._outcome_text
    finally:
        app.shutdown()


def test_weigh_station_bypass_is_not_certain_and_stays_silent_when_missed(monkeypatch):
    """The scale house watches, but a unit still has to catch up to you.

    Seed 11 rolls over the 85 percent catch chance for this exact scale key,
    so the same crossing that seed 1 catches gets away clean -- silently, by
    design. The event is still marked so the scale never re-rolls the miss.
    """
    from freight_fate.app import App
    from freight_fate.sim.trip import RoadStop

    app = App()
    try:
        d = _driving(app, patrol_intensity=None)
        d.trip_seed = 11
        _quiet(app, monkeypatch)
        d.trip.stops = [RoadStop("Ontario Scale", 10.0, "weigh_station", ("inspect",))]
        d.trip.posts = [*d.trip.posts, open_scale_post(d.trip.stops[0])]
        d.trip.position_mi = 10.1
        d.truck.velocity_mps = 55.0 / 2.23694
        money_before = app.ctx.profile.money
        citations_before = app.ctx.profile.driving_record.citations

        d._check_weigh_station_enforcement(9.9)

        assert d._pull_over is None
        assert d._weigh_station_key(d.trip.stops[0]) in d.enforcement_events
        assert app.ctx.profile.money == money_before
        assert app.ctx.profile.driving_record.citations == citations_before
    finally:
        app.shutdown()


def test_closed_scale_never_charges_a_bypass(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.enforcement_posts import KIND_SCALE_APRON, METHOD_BY_KIND, EnforcementPost
    from freight_fate.sim.trip import RoadStop

    app = App()
    try:
        d = _driving(app, patrol_intensity=None)
        d.trip_seed = 1
        _quiet(app, monkeypatch)
        stop = RoadStop("Ontario Scale", 10.0, "weigh_station", ("inspect",))
        d.trip.stops = [stop]
        # A closed scale still carries an apron post -- state police may be
        # sitting on it -- but the silence-means-closed rule holds: no scale
        # bypass charge can ever come from it.
        d.trip.posts = [
            *d.trip.posts,
            EnforcementPost(
                at_mi=stop.at_mi,
                kind=KIND_SCALE_APRON,
                method=METHOD_BY_KIND[KIND_SCALE_APRON],
                reach_mi=0.5,
                facing="both",
                staffed=True,
                anchor=stop.key,
                announced=True,
            ),
        ]
        d.trip.position_mi = 10.1
        d.truck.velocity_mps = 55.0 / 2.23694
        money_before = app.ctx.profile.money

        d._check_weigh_station_enforcement(9.9)

        assert d._pull_over is None
        assert not d.enforcement_events
        assert app.ctx.profile.money == money_before
    finally:
        app.shutdown()


def test_weigh_station_warning_is_spoken_before_bypass(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import RoadStop

    app = App()
    spoken = []
    played = []
    try:
        d = _driving(app, patrol_intensity=None)
        monkeypatch.setattr(app.ctx, "say", lambda *a, **k: None)
        monkeypatch.setattr(app.ctx, "say_event", lambda text, *a, **k: spoken.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda key, **k: played.append(key))
        d.trip.stops = [RoadStop("Ontario Scale", 10.0, "weigh_station", ("inspect",))]
        d.trip.posts = [*d.trip.posts, open_scale_post(d.trip.stops[0])]
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 45.0 / 2.23694

        d._check_weigh_station_enforcement(8.0)
        d._check_weigh_station_enforcement(8.1)

        assert len([s for s in spoken if "Open weigh station ahead" in s]) == 1
        # The notice teaches the exit key first; the rest key only once
        # stopped at the scale. "Press T" at speed plans a sleep stop, which
        # is the instruction that used to march drivers into the bypass.
        assert "Signal for the scale exit with X" in spoken[0]
        assert "Once you are stopped at the scale, press T to check in" in spoken[0]
        # Its own earcon, not the shared inspection cue (owner ruling,
        # 2026-08-14): testers could not tell the scale-ahead warning apart
        # from being looked at for something else.
        assert played.count("events/weigh_station_warning") == 1
        assert "events/inspection_warning" not in played
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
        d.trip.stops = [RoadStop("Ontario Scale", 10.0, "weigh_station", ("inspect",))]
        d.trip.posts = [*d.trip.posts, open_scale_post(d.trip.stops[0])]
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
        d.trip.stops = [RoadStop("Ontario Scale", 10.0, "weigh_station", ("inspect",))]
        d.trip.posts = [*d.trip.posts, open_scale_post(d.trip.stops[0])]
        d.trip.position_mi = 10.1
        d.truck.velocity_mps = (limit + 25.0) / 2.23694

        d._check_weigh_station_enforcement(9.9)

        assert d._pull_over == "lights"
        assert d._pull_over_kind == "speeding"
    finally:
        app.shutdown()


def test_unsafe_damage_in_patrol_starts_safety_stop(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.enforcement import UNSAFE_DAMAGE_FINE, citation_fine

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
        expected = citation_fine(
            UNSAFE_DAMAGE_FINE, 0, construction_zone=app.state.construction_zone
        )
        assert d.ticket_fines_paid == expected
        assert app.ctx.profile.money == money_before - expected
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


# --- construction zones and repeat offenders --------------------------------


def _pave_construction(d):
    """Lay real roadwork over the whole route, so any stop happens inside it."""
    from freight_fate.sim.trip_models import Zone

    d.trip.zones = [Zone(0.0, d.trip.total_miles, 45.0, "construction")]


def test_the_merge_taper_counts_as_being_in_the_construction_zone(monkeypatch):
    """One signed footprint: the cones and the doubled-fine sign start there."""
    from freight_fate.app import App
    from freight_fate.sim.trip_models import Zone

    app = App()
    try:
        d = _driving(app, patrol_intensity=None)
        _quiet(app, monkeypatch)
        d.trip.position_mi = 5.0
        d.trip.zones = [Zone(4.0, 6.0, 55.0, "construction merge")]
        assert d.trip.in_construction_zone
        d.trip.zones = [Zone(4.0, 6.0, 45.0, "heavy traffic")]
        assert not d.trip.in_construction_zone
    finally:
        app.shutdown()


def test_roadwork_hides_behind_a_jam_and_still_doubles_the_fine(monkeypatch):
    """active_zone returns the slowest zone; the predicate must not use it."""
    from freight_fate.app import App
    from freight_fate.sim.trip_models import Zone

    app = App()
    try:
        d = _driving(app, patrol_intensity=None)
        _quiet(app, monkeypatch)
        d.trip.position_mi = 5.0
        d.trip.zones = [
            Zone(4.0, 6.0, 45.0, "construction"),
            Zone(4.0, 6.0, 20.0, "heavy traffic"),
        ]
        assert d.trip.active_zone.reason == "heavy traffic"
        assert d.trip.in_construction_zone
    finally:
        app.shutdown()


def test_a_scale_bypass_in_roadwork_costs_double_and_says_so(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.enforcement import WEIGH_STATION_BYPASS_FINE, citation_fine
    from freight_fate.sim.trip import RoadStop
    from freight_fate.states.driving import EnforcementStopState

    app = App()
    try:
        d = _driving(app, patrol_intensity=None)
        d.trip_seed = 1  # lands under the 85 percent catch chance; see above
        _quiet(app, monkeypatch)
        _pave_construction(d)
        d.trip.stops = [RoadStop("Ontario Scale", 10.0, "weigh_station", ("inspect",))]
        d.trip.posts = [*d.trip.posts, open_scale_post(d.trip.stops[0])]
        d.trip.position_mi = 10.1
        d.truck.velocity_mps = 55.0 / 2.23694

        d._check_weigh_station_enforcement(9.9)
        assert d._pull_over_construction_zone

        money_before = app.ctx.profile.money
        d.truck.velocity_mps = 0.0
        d._update_pull_over(1.0)

        assert isinstance(app.state, EnforcementStopState)
        expected = citation_fine(WEIGH_STATION_BYPASS_FINE, 0, construction_zone=True)
        assert expected == WEIGH_STATION_BYPASS_FINE * 2.0
        assert app.ctx.profile.money == money_before - expected
        # The driver hears the figure that was actually charged, and why.
        text = app.state._outcome_text
        assert f"{expected:,.0f} dollars" in text
        assert "doubled" in text and "construction zone" in text
    finally:
        app.shutdown()


def test_a_repeat_scale_bypass_in_roadwork_compounds_rather_than_adds(monkeypatch):
    """The owner's call: 1,800 x 1.5 x 2 = 5,400 on a second offense."""
    from freight_fate.app import App
    from freight_fate.models.enforcement import WEIGH_STATION_BYPASS_FINE, citation_fine
    from freight_fate.sim.trip import RoadStop

    app = App()
    try:
        d = _driving(app, patrol_intensity=None)
        d.trip_seed = 1  # lands under the 85 percent catch chance; see above
        _quiet(app, monkeypatch)
        _pave_construction(d)
        app.ctx.profile.driving_record.citations = 1
        d.trip.stops = [RoadStop("Ontario Scale", 10.0, "weigh_station", ("inspect",))]
        d.trip.posts = [*d.trip.posts, open_scale_post(d.trip.stops[0])]
        d.trip.position_mi = 10.1
        d.truck.velocity_mps = 55.0 / 2.23694

        d._check_weigh_station_enforcement(9.9)
        money_before = app.ctx.profile.money
        d.truck.velocity_mps = 0.0
        d._update_pull_over(1.0)

        expected = citation_fine(WEIGH_STATION_BYPASS_FINE, 1, construction_zone=True)
        assert expected == 5_400.0
        assert expected != WEIGH_STATION_BYPASS_FINE * 2.5  # not added
        assert app.ctx.profile.money == money_before - expected
    finally:
        app.shutdown()


def test_a_speeding_ticket_in_roadwork_doubles_and_the_line_says_the_charge(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.enforcement import speeding_citation_fine
    from freight_fate.states.driving import TrafficStopState

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        _pave_construction(d)
        _speed_for(d, over=25.0)  # well over -> a ticket, not a warning
        assert d._pull_over_construction_zone
        p = app.ctx.profile
        money_before = p.money
        d.truck.velocity_mps = 0.0
        d._update_pull_over(1.0)

        assert isinstance(app.state, TrafficStopState)
        assert app.state.construction_zone
        base = speeding_citation_fine(app.state.over, 0)
        expected = speeding_citation_fine(app.state.over, 0, construction_zone=True)
        assert expected == base * 2.0
        assert d.ticket_fines_paid == expected
        assert p.money == money_before - expected
        text = app.state._outcome_text
        assert f"{expected:,.0f} dollars" in text
        assert "doubled" in text and "construction zone" in text
    finally:
        app.shutdown()


def test_leaving_the_zone_before_stopping_does_not_undo_the_doubling(monkeypatch):
    """The zone that counts is where the violation happened, not the shoulder."""
    from freight_fate.app import App
    from freight_fate.models.enforcement import speeding_citation_fine
    from freight_fate.states.driving import TrafficStopState

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        _pave_construction(d)
        _speed_for(d, over=25.0)
        d.trip.zones = []  # rolled out the far end before braking
        assert not d.trip.in_construction_zone
        d.truck.velocity_mps = 0.0
        d._update_pull_over(1.0)

        assert isinstance(app.state, TrafficStopState)
        assert app.state.construction_zone
        assert d.ticket_fines_paid == speeding_citation_fine(
            app.state.over, 0, construction_zone=True
        )
    finally:
        app.shutdown()


def test_a_non_speeding_stop_escalates_with_priors(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.enforcement import UNSAFE_DAMAGE_FINE, citation_fine

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        app.ctx.profile.driving_record.citations = 2
        d.trip.position_mi = d.trip.total_miles / 2.0
        d.truck.damage_pct = 70.0
        d.truck.velocity_mps = 35.0 / 2.23694

        d._check_unsafe_damage_enforcement()
        money_before = app.ctx.profile.money
        d.truck.velocity_mps = 0.0
        d._update_pull_over(1.0)

        expected = citation_fine(
            UNSAFE_DAMAGE_FINE, 2, construction_zone=app.state.construction_zone
        )
        assert expected > UNSAFE_DAMAGE_FINE
        assert app.ctx.profile.money == money_before - expected
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


def test_braking_to_a_stop_reaches_the_roadside_stop(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states import driving_rest_states
    from freight_fate.states.driving import (
        PULL_OVER_FULL_COMPLIANCE,
        TrafficStopState,
    )

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        # The clean-stop leniency is a real one-in-four chance seeded on the
        # trip; this test is about reaching the roadside stop and being
        # ticketed, so take the leniency off the table rather than leaving a
        # one-in-four flake in it.
        monkeypatch.setattr(driving_rest_states, "PULL_OVER_CLEAN_STOP_WARN_CHANCE", 0.0)
        _speed_for(d, over=25.0)
        d._signal_pull_over()  # signal, then brake steadily
        _past_grace(d)
        for _ in range(4):
            d._update_pull_over(1.0, service_braking=True)
        assert d._pull_over_compliance >= PULL_OVER_FULL_COMPLIANCE
        d.truck.velocity_mps = 0.0
        d._update_pull_over(1.0)
        assert isinstance(app.state, TrafficStopState)
        assert app.state.clean_stop is True
        assert d.speeding_tickets == 1  # over 25 -> a ticket, not waived here
    finally:
        app.shutdown()


def test_clean_stop_can_waive_a_ticket_to_a_warning(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import TrafficStopState

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        _speed_for(d, over=25.0)
        d._signal_pull_over()
        _past_grace(d)
        for _ in range(4):
            d._update_pull_over(1.0, service_braking=True)
        # The leniency roll is now a named, position-quantised seed so a
        # reload cannot re-roll it; force it by making it always succeed.
        monkeypatch.setattr(
            "freight_fate.states.driving_rest_states.PULL_OVER_CLEAN_STOP_WARN_CHANCE", 1.0
        )
        p = app.ctx.profile
        money_before = p.money
        d.truck.velocity_mps = 0.0
        d._update_pull_over(1.0)
        assert isinstance(app.state, TrafficStopState)
        assert d.speeding_tickets == 0
        assert p.money == money_before
        assert "let it go" in app.state._outcome_text
    finally:
        app.shutdown()


def test_failing_to_signal_takes_a_one_time_deduction(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        _speed_for(d, over=25.0)
        _past_grace(d)
        # Brake steadily but never signal: compliance climbs until the 5 s
        # signal grace lapses, when a one-time deduction drops it.
        comp = []
        for _ in range(7):
            d._update_pull_over(1.0, service_braking=True)
            comp.append(d._pull_over_compliance)
        assert d._pull_over_nosignal_hit is True
        # The tick that crosses the grace dips below the prior tick.
        assert comp[5] < comp[4]
    finally:
        app.shutdown()


def test_continuous_coasting_slowly_drains_compliance(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app, patrol_intensity=1.0)
        _quiet(app, monkeypatch)
        _speed_for(d, over=25.0)
        d._signal_pull_over()  # signal so only coasting is in play
        _past_grace(d)
        before = d._pull_over_compliance
        # Hold a steady speed (neither braking nor accelerating) for 5 s.
        for _ in range(5):
            d._update_pull_over(1.0)
        assert d._pull_over is not None  # coasting drains, but not instantly
        assert d._pull_over_compliance < before
    finally:
        app.shutdown()


def test_out_of_service_stop_shuts_down_the_engine(monkeypatch):
    """The ten-hour out-of-service order is a real overnight fast-forward: it
    must shut the engine down like every other sleep path (motel, sleeper
    split, shoulder, lot), not leave it idling through the night, and it must
    tell the driver how to get moving again afterward."""
    from freight_fate.app import App
    from freight_fate.states.driving import EnforcementStopState

    app = App()
    try:
        d = _driving(app, patrol_intensity=None)
        _quiet(app, monkeypatch)
        d.truck.start_engine()
        assert d.truck.engine_on

        app.push_state(
            EnforcementStopState(
                app.ctx,
                d,
                title="Log check",
                summary="Evidence: HOS/ELD violation.",
                fine=500.0,
                reputation_hit=10.0,
                signaled=True,
                return_message="Back on the highway with a reset clock.",
                out_of_service=True,
            )
        )

        assert d.truck.engine_on is False
        text = app.state._outcome_text
        assert "shut down the engine" in text.lower()
        # Ten hours parked with the engine off bleeds the air down, so the
        # driver needs the restart instruction to get moving again.
        assert "start the engine" in text.lower()
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
