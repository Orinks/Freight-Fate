"""PrePass-style weigh-in-motion bypass: the transponder gate and verdicts.

Below the gate an open scale still demands every truck pull in, exactly as
before. With a weigh-in-motion transponder -- a free fleet issue for a
company driver at career level 4 (models.business.WEIGH_STATION_TRANSPONDER_
LEVEL), or a purchased subscription for an owner-operator -- the scale hands
back a green or red verdict right behind the existing open-scale notice
(states/driving_updates.py::_resolve_transponder_verdict). Green rolls past
free; red pulls in exactly like the old no-transponder flow. The fixture
shape below mirrors test_scale_check_in_guidance.py's.
"""

from __future__ import annotations

from enforcement_helpers import open_scale_post

from freight_fate.models.business import (
    LEASED_OWNER_OPERATOR,
    WEIGH_STATION_TRANSPONDER_LEVEL,
    WEIGH_STATION_TRANSPONDER_PER_MILE,
    has_weigh_station_transponder,
    independent_authority_charges_for_trailers,
    owner_operator_charges,
    weigh_station_transponder_eligibility,
)
from freight_fate.models.career import LEVEL_XP


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Transponder Test", current_city="Buffalo")
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
    d.trip.posts = []
    return d


def _with_scale(d, *, scale_mi=10.0):
    """A single open scale, matching test_scale_check_in_guidance.py's shape.

    Name and mile marker are fixed so the seeded rolls below are pinned to a
    known scale key: ``weigh:Ontario Scale:10.0``.
    """
    from freight_fate.sim.trip import RoadStop

    scale = RoadStop(
        "Ontario Scale",
        scale_mi,
        "weigh_station",
        ("inspect",),
        parking="none",
    )
    d.trip.stops = [scale]
    d.trip.posts = [open_scale_post(scale)]
    return scale


def _capture(app, monkeypatch):
    spoken: list[str] = []
    played: list[tuple[str, dict]] = []
    monkeypatch.setattr(app.ctx, "say", lambda text, *a, **k: spoken.append(text))
    monkeypatch.setattr(app.ctx, "say_event", lambda text, *a, **k: spoken.append(text))

    def _play(key, *a, **k):
        played.append((key, k))

    monkeypatch.setattr(app.ctx.audio, "play", _play)
    return spoken, played


def _grant_transponder(app):
    """Level up the profile past the free-issue gate."""
    app.ctx.profile.career.xp = LEVEL_XP[WEIGH_STATION_TRANSPONDER_LEVEL - 1]


# --- the gate: models/business.py --------------------------------------------


def test_company_driver_below_level_four_has_no_transponder():
    from freight_fate.models.profile import Profile

    p = Profile(name="Rookie")
    assert p.career.level < WEIGH_STATION_TRANSPONDER_LEVEL
    assert not has_weigh_station_transponder(p)


def test_company_driver_at_level_four_gets_a_free_transponder():
    from freight_fate.models.profile import Profile

    p = Profile(name="Trusted")
    p.career.xp = LEVEL_XP[WEIGH_STATION_TRANSPONDER_LEVEL - 1]
    assert p.career.level == WEIGH_STATION_TRANSPONDER_LEVEL
    assert has_weigh_station_transponder(p)


def test_owner_operator_needs_the_purchased_subscription_not_just_level():
    from freight_fate.models.profile import Profile

    p = Profile(name="Owner")
    p.business_status = LEASED_OWNER_OPERATOR
    p.career.xp = LEVEL_XP[WEIGH_STATION_TRANSPONDER_LEVEL - 1]
    # Level alone buys a company driver a free transponder, but this driver
    # has no fleet behind them -- the level gate does not apply.
    assert not has_weigh_station_transponder(p)

    ok, reasons = weigh_station_transponder_eligibility(p)
    assert ok and reasons == ()  # starting money already covers the signup fee

    p.money = 0.0
    ok, reasons = weigh_station_transponder_eligibility(p)
    assert not ok
    assert "dollars" in reasons[0]

    p.money = 100_000.0
    p.weigh_station_transponder = True
    assert has_weigh_station_transponder(p)
    ok, reasons = weigh_station_transponder_eligibility(p)
    assert not ok
    assert "already active" in reasons[0]


def test_transponder_settlement_charge_only_when_subscribed():
    from freight_fate.models.jobs import CARGO_CATALOG, Job

    job = Job(CARGO_CATALOG["general"], 20.0, "A", "yard", "B", 100.0, 1000.0, 12.0)

    plain = owner_operator_charges(job, 1000.0)
    assert not any("transponder" in c.label for c in plain)

    with_sub = owner_operator_charges(job, 1000.0, transponder=True)
    charge = next(c for c in with_sub if "transponder" in c.label)
    assert charge.amount == round(job.distance_mi * WEIGH_STATION_TRANSPONDER_PER_MILE, 2)

    # Own-authority settlement carries the same reserve, threaded the same way.
    authority_plain = independent_authority_charges_for_trailers(job, 1000.0)
    assert not any("transponder" in c.label for c in authority_plain)
    authority_with_sub = independent_authority_charges_for_trailers(job, 1000.0, transponder=True)
    assert any("transponder" in c.label for c in authority_with_sub)


# --- driving mechanic: states/driving_updates.py -----------------------------


def test_below_the_gate_the_scale_still_demands_every_truck(monkeypatch):
    """Old behavior, unchanged, for a driver with no transponder."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)  # profile starts at level 1: below the gate
        # Seed 0 rolls green for this exact scale key if a transponder is
        # ever consulted; picking it here proves the gate -- not the roll --
        # is what keeps the old behavior in force.
        d.trip_seed = 0
        spoken, played = _capture(app, monkeypatch)
        scale = _with_scale(d)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 55.0 / 2.23694

        d._check_weigh_station_enforcement(8.0)

        assert not any("Green light" in s or "Red light" in s for s in spoken)
        assert not any(k in ("events/scale_green", "events/scale_red") for k, _ in played)
        assert d._weigh_station_transponder_verdict == {}

        d.trip.position_mi = scale.at_mi + 0.1
        d._check_weigh_station_enforcement(scale.at_mi - 0.1)

        assert d._pull_over == "lights"  # unarmed bypass still charges
        assert d._pull_over_kind == "weigh_station_bypass"
    finally:
        app.shutdown()


def test_transponder_green_bypasses_without_a_charge(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _grant_transponder(app)
        # Seed 0 rolls under WEIGH_STATION_TRANSPONDER_BYPASS_SHARE for this
        # exact scale key ("weigh:Ontario Scale:10.0").
        d.trip_seed = 0
        spoken, played = _capture(app, monkeypatch)
        scale = _with_scale(d)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 55.0 / 2.23694

        d._check_weigh_station_enforcement(8.0)

        key = d._weigh_station_key(scale)
        assert d._weigh_station_transponder_verdict[key] == "green"
        assert any("Green light" in s for s in spoken)
        assert any(k == "events/scale_green" for k, _ in played)
        # The base open-scale notice still speaks -- the verdict rides on
        # top of it, never in place of it.
        assert any("Open weigh station ahead" in s for s in spoken)

        money_before = app.ctx.profile.money
        d.trip.position_mi = scale.at_mi + 0.1
        d._check_weigh_station_enforcement(scale.at_mi - 0.1)

        assert d._pull_over is None
        assert app.ctx.profile.money == money_before
        assert key in d.enforcement_events
    finally:
        app.shutdown()


def test_transponder_red_pulls_in_like_the_old_flow(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _grant_transponder(app)
        # Seed 18 rolls at or over the bypass share for this exact scale key,
        # AND lands under the separate (unrelated) bypass-catch roll that
        # _charge_weigh_station_bypass makes on its own named draw, so the
        # red-lighted crossing below is deterministically caught rather than
        # silently missed.
        d.trip_seed = 18
        spoken, played = _capture(app, monkeypatch)
        scale = _with_scale(d)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 55.0 / 2.23694

        d._check_weigh_station_enforcement(8.0)

        key = d._weigh_station_key(scale)
        assert d._weigh_station_transponder_verdict[key] == "red"
        assert any("Red light" in s for s in spoken)
        assert any(k == "events/scale_red" for k, _ in played)

        d.trip.position_mi = scale.at_mi + 0.1
        d._check_weigh_station_enforcement(scale.at_mi - 0.1)

        assert d._pull_over == "lights"
        assert d._pull_over_kind == "weigh_station_bypass"
    finally:
        app.shutdown()


def test_overweight_load_is_always_red_lighted(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _grant_transponder(app)
        # Seed 0 would roll green if the load were not overweight (see the
        # green test above) -- the overweight check must win regardless.
        d.trip_seed = 0
        monkeypatch.setattr(d, "_cargo_is_overweight", lambda: True)
        spoken, _ = _capture(app, monkeypatch)
        scale = _with_scale(d)
        d.trip.position_mi = 8.2
        d.truck.velocity_mps = 55.0 / 2.23694

        d._check_weigh_station_enforcement(8.0)

        key = d._weigh_station_key(scale)
        assert d._weigh_station_transponder_verdict[key] == "red"
        assert any("Red light" in s for s in spoken)
    finally:
        app.shutdown()


def test_transponder_verdict_is_seeded_off_trip_seed_and_stop(monkeypatch):
    """Same trip seed and stop always settle the same way; no wall-clock luck."""
    from freight_fate.app import App

    def _verdict(trip_seed):
        app = App()
        try:
            d = _driving(app)
            _grant_transponder(app)
            d.trip_seed = trip_seed
            _capture(app, monkeypatch)
            scale = _with_scale(d)
            key = d._weigh_station_key(scale)
            d._resolve_transponder_verdict(scale, key)
            return d._weigh_station_transponder_verdict[key]
        finally:
            app.shutdown()

    assert _verdict(0) == _verdict(0) == "green"
    assert _verdict(18) == _verdict(18) == "red"
