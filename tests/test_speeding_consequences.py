"""What speeding costs, now that it costs only what somebody saw.

This file used to guard a "speeding strike": hold nine over for six real
seconds anywhere on the route and the drive banked a charge, spoken as
"due at delivery" and deducted at the dock. Nobody had to be there. It was a
placeholder for enforcement that did not exist, and it was removed once real
enforcement did (owner ruling, 2026-08-09).

What it guards now is the replacement, which is a much shorter rule: an
officer who saw you charges you on the shoulder, and nothing else charges you
at all. The tests below pin both halves of that -- the free half especially,
because "you got away with it" is a feature and the easiest thing to
accidentally regress into a tax again.
"""

from enforcement_helpers import always_observing_post
from speech_capture import speech_stub


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
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    return spoken


def _speed_on_an_empty_road(d, *, over=15.0, seconds=30.0):
    """Hold well over the limit, for a long time, with nobody watching."""
    d.trip.posts = []
    d.trip.position_mi = d.trip.total_miles / 2.0
    d._enforcement_prev_mi = d.trip.position_mi
    limit, _ = d.trip.speed_limit_at(d.trip.position_mi)
    d.truck.velocity_mps = (limit + over) / 2.23694
    for _ in range(int(seconds / 0.5)):
        d.trip.position_mi += 0.02
        d._update_enforcement_watch(0.5)
        d._update_speeding(0.5)
    return limit


def test_speeding_nobody_saw_costs_nothing(monkeypatch):
    """The whole ruling, in one assertion.

    Half a minute at fifteen over on an empty road: no money moves, no charge
    is banked for the dock, and nothing is said about a fine, because there
    was no officer to say it.
    """
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        money_before = app.ctx.profile.money
        _speed_on_an_empty_road(d)
        assert app.ctx.profile.money == money_before
        assert app.ctx.profile.fines_owed == 0.0
        assert d.speeding_tickets == 0
        assert d._pull_over is None
        assert not [line for line in spoken if "fine" in line.lower()]
        assert not [line for line in spoken if "delivery" in line.lower()]
    finally:
        app.shutdown()


def test_the_silent_at_delivery_charge_is_gone_from_the_code(monkeypatch):
    """No attribute, no fine table, no settlement line to accidentally revive."""
    from freight_fate.app import App
    from freight_fate.states import driving, driving_core

    app = App()
    try:
        d = _driving(app)
        assert not hasattr(d, "speeding_strikes")
        assert not hasattr(d, "_speeding_timer")
        assert not hasattr(driving_core, "_speeding_settlement_fine")
        assert not hasattr(driving, "SPEEDING_HOLD_S")
    finally:
        app.shutdown()


def test_the_dash_still_warns_even_though_nothing_is_charged(monkeypatch):
    """Removing the tax must not remove the courtesy.

    The overspeed alert was never enforcement -- it is the carrier's dash
    nagging you, and it is the only reason a blind driver knows the limit
    dropped. It stays.
    """
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        _speed_on_an_empty_road(d, over=15.0, seconds=2.0)
        assert [line for line in spoken if "Watch your speed" in line]
        assert [line for line in spoken if "The limit is" in line]
    finally:
        app.shutdown()


def test_a_dropped_limit_still_earns_braking_room(monkeypatch):
    """The one fairness rule worth keeping from the strike era.

    A loaded truck cannot shed fifteen mph the instant a sign changes, so the
    grace that used to hold off a strike now holds off the over-limit distance
    an officer reads. Without it a post could clock you on the transition
    itself.
    """
    from freight_fate.app import App
    from freight_fate.sim.enforcement_observe import OBSERVE_HOLD_MI

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        d.trip.posts = []
        d.trip.position_mi = d.trip.total_miles / 2.0
        d._enforcement_prev_mi = d.trip.position_mi
        limit, _ = d.trip.speed_limit_at(d.trip.position_mi)
        d.truck.velocity_mps = (limit + 20.0) / 2.23694
        # A limit drop under the truck, with the driver off the throttle.
        d._enforced_limit_prev = limit + 15.0
        d._update_speeding(0.1, accelerator_held=False)
        assert d._limit_drop_grace_s > 0.0
        for _ in range(10):
            d.trip.position_mi += 0.05
            d._update_enforcement_watch(0.1)
        assert d._over_limit_mi < OBSERVE_HOLD_MI
    finally:
        app.shutdown()


def test_staying_on_the_throttle_through_the_drop_collapses_the_grace(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        d.trip.posts = []
        d.trip.position_mi = d.trip.total_miles / 2.0
        limit, _ = d.trip.speed_limit_at(d.trip.position_mi)
        d.truck.velocity_mps = (limit + 20.0) / 2.23694
        d._enforced_limit_prev = limit + 15.0
        d._update_speeding(0.1, accelerator_held=False)
        assert d._limit_drop_grace_s > 0.0
        d._update_speeding(0.1, accelerator_held=True)
        assert d._limit_drop_grace_s == 0.0
    finally:
        app.shutdown()


def test_being_seen_is_the_only_thing_that_costs_money(monkeypatch):
    """The other half: an officer who was there charges you on the shoulder."""
    from freight_fate.app import App
    from freight_fate.sim.enforcement_observe import OBSERVE_HOLD_MI

    app = App()
    try:
        d = _driving(app)
        _capture_events(app, monkeypatch)
        d.trip.position_mi = d.trip.total_miles / 2.0
        d._enforcement_prev_mi = d.trip.position_mi
        limit, _ = d.trip.speed_limit_at(d.trip.position_mi)
        d.trip.posts = [always_observing_post(at_mi=d.trip.position_mi + 0.2)]
        d.truck.velocity_mps = (limit + 25.0) / 2.23694
        d._over_limit_mi = OBSERVE_HOLD_MI * 2
        d._update_enforcement_watch(0.1)
        assert d._pull_over == "lights"
    finally:
        app.shutdown()


def test_the_metric_pull_over_call_uses_metric_units(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.enforcement_observe import OBSERVE_HOLD_MI

    app = App()
    try:
        app.ctx.settings.imperial_units = False
        d = _driving(app)
        spoken = _capture_events(app, monkeypatch)
        d.trip.position_mi = d.trip.total_miles / 2.0
        d._enforcement_prev_mi = d.trip.position_mi
        limit, _ = d.trip.speed_limit_at(d.trip.position_mi)
        d.trip.posts = [always_observing_post(at_mi=d.trip.position_mi + 0.2)]
        d.truck.velocity_mps = (limit + 25.0) / 2.23694
        d._over_limit_mi = OBSERVE_HOLD_MI * 2
        d._update_enforcement_watch(0.1)
        lights = next(line for line in spoken if "Lights and siren" in line)
        assert "kilometers per hour" in lights
        assert "miles per hour" not in lights
    finally:
        app.shutdown()
