"""Speeding strikes surface their cost the moment they land (the bridge to the
trooper/enforcement milestone), judged against the leg's real posted limit."""


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Speeder", current_city="Buffalo")
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


def _capture_events(app, monkeypatch):
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    return spoken


def _force_strike(d):
    from freight_fate.states.driving import SPEEDING_HOLD_S, SPEEDING_LEEWAY_MPH

    d.trip.position_mi = d.trip.total_miles / 2.0  # out on the open road
    limit, _ = d.trip.speed_limit_at(d.trip.position_mi)
    d.truck.velocity_mps = (limit + SPEEDING_LEEWAY_MPH + 5) / 2.23694
    d._update_speeding(SPEEDING_HOLD_S + 1.0)  # hold past the window
    return limit


def test_first_strike_announces_the_running_fine(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import _speeding_settlement_fine

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _force_strike(d)
        assert d.speeding_strikes == 1
        expected = _speeding_settlement_fine(1)
        assert "Speeding strike" in spoken[-1]
        assert f"{expected:,.0f} dollars" in spoken[-1]
        assert "due at delivery" in spoken[-1]
    finally:
        app.shutdown()


def test_metric_strike_announces_limit_in_metric_units(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        app.ctx.settings.imperial_units = False
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _force_strike(d)
        assert "Speeding strike" in spoken[-1]
        assert "kilometers per hour" in spoken[-1]
        assert "miles per hour" not in spoken[-1]
    finally:
        app.shutdown()


def test_strike_cost_climbs_with_each_strike(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import _speeding_settlement_fine

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _force_strike(d)
        _force_strike(d)
        assert d.speeding_strikes == 2
        assert f"{_speeding_settlement_fine(2):,.0f} dollars" in spoken[-1]
    finally:
        app.shutdown()


def test_capped_fine_says_it_is_maxed(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        d.speeding_strikes = 5  # already at the 400-dollar cap
        _force_strike(d)
        assert "maximum" in spoken[-1]
        assert "400-dollar" in spoken[-1]
    finally:
        app.shutdown()


def test_within_leeway_records_no_strike(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import SPEEDING_HOLD_S, SPEEDING_LEEWAY_MPH

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        d.trip.position_mi = d.trip.total_miles / 2.0
        limit, _ = d.trip.speed_limit_at(d.trip.position_mi)
        # A few mph over, but inside the leeway: no strike no matter how long.
        d.truck.velocity_mps = (limit + SPEEDING_LEEWAY_MPH - 2) / 2.23694
        d._update_speeding(SPEEDING_HOLD_S + 5.0)
        assert d.speeding_strikes == 0
    finally:
        app.shutdown()
