"""Career economy balance: carrier billing, XP pacing, trust pay, money sinks."""

from types import SimpleNamespace

import pytest

from freight_fate.models.business import (
    COMPANY_DRIVER,
    LEASED_OWNER_OPERATOR,
    build_business_settlement,
    company_driver_pay,
    reputation_pay_bonus,
)
from freight_fate.models.career import (
    ENDORSEMENT_COURSE_COSTS,
    Career,
    xp_class_multiplier,
    xp_streak_bonus,
)
from freight_fate.models.economy import MOTEL_COST
from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.models.profile import Profile


def _job(cargo="general", miles=200.0, pay=900.0) -> Job:
    return Job(CARGO_CATALOG[cargo], 12.0, "Denver", "yard", "Salt Lake City", miles, pay, 12.0)


# -- XP multipliers -----------------------------------------------------------------


def test_specialty_and_premium_cargo_teach_more_per_mile():
    assert xp_class_multiplier(CARGO_CATALOG["refrigerated"]) == pytest.approx(1.4)
    assert xp_class_multiplier(CARGO_CATALOG["electronics"]) == pytest.approx(1.4)
    assert xp_class_multiplier(CARGO_CATALOG["automotive"]) == pytest.approx(1.15)
    assert xp_class_multiplier(CARGO_CATALOG["general"]) == pytest.approx(1.0)


def test_on_time_streak_compounds_and_late_resets_it():
    career = Career()
    career.record_delivery(100.0, 500.0, on_time=True, damage_pct=0.0)
    assert career.on_time_streak == 1
    first = career.xp
    assert first == pytest.approx(120.0)  # no bonus on the first run

    career.record_delivery(100.0, 500.0, on_time=True, damage_pct=0.0)
    assert career.xp - first == pytest.approx(120.0 * 1.05)  # streak of 2: +5%

    career.record_delivery(100.0, 500.0, on_time=False, damage_pct=0.0)
    assert career.on_time_streak == 0


def test_streak_bonus_caps_at_a_quarter():
    assert xp_streak_bonus(1) == pytest.approx(0.0)
    assert xp_streak_bonus(3) == pytest.approx(0.10)
    assert xp_streak_bonus(6) == pytest.approx(0.25)
    assert xp_streak_bonus(40) == pytest.approx(0.25)


def test_specialty_multiplier_applies_through_record_delivery():
    career = Career()
    career.record_delivery(100.0, 500.0, on_time=True, damage_pct=0.0, cargo_class_mult=1.4)
    assert career.xp == pytest.approx(100.0 * 1.2 * 1.4)


def test_streak_survives_the_save_round_trip():
    profile = Profile(name="Streak Save", current_city="Chicago")
    profile.career.on_time_streak = 4
    reloaded = Profile.from_dict(profile.to_dict())
    assert reloaded.career.on_time_streak == 4


# -- reputation-scaled pay ----------------------------------------------------------


def test_reputation_bonus_is_zero_at_start_and_grows_with_trust():
    assert reputation_pay_bonus(1000.0, None) == 0.0
    assert reputation_pay_bonus(1000.0, 50.0) == 0.0
    assert reputation_pay_bonus(1000.0, 40.0) == 0.0  # never a penalty
    assert reputation_pay_bonus(1000.0, 75.0) == pytest.approx(30.0)
    assert reputation_pay_bonus(1000.0, 100.0) == pytest.approx(60.0)


def test_trusted_company_driver_takes_home_more():
    job = _job(miles=800.0, pay=2000.0)
    rookie = company_driver_pay(job, 2000.0, on_time=True, reputation=50.0)
    veteran = company_driver_pay(job, 2000.0, on_time=True, reputation=100.0)
    assert veteran - rookie == pytest.approx(reputation_pay_bonus(2000.0, 100.0))

    low = build_business_settlement(
        COMPANY_DRIVER, job, 2000.0, on_time=True, driver_charges=0.0, reputation=50.0
    )
    high = build_business_settlement(
        COMPANY_DRIVER, job, 2000.0, on_time=True, driver_charges=0.0, reputation=100.0
    )
    assert high.net_before_advance > low.net_before_advance


def test_owner_operator_settlement_ignores_the_trust_bonus():
    job = _job(miles=800.0, pay=2000.0)
    base = build_business_settlement(
        LEASED_OWNER_OPERATOR, job, 2000.0, on_time=True, driver_charges=0.0
    )
    trusted = build_business_settlement(
        LEASED_OWNER_OPERATOR,
        job,
        2000.0,
        on_time=True,
        driver_charges=0.0,
        reputation=100.0,
    )
    assert trusted.net_before_advance == pytest.approx(base.net_before_advance)


# -- endorsement courses -------------------------------------------------------------


def test_paid_course_unlocks_endorsement_before_its_level(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import EndorsementCourseState

    app = App()
    try:
        spoken = []
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile(name="Course Buyer", current_city="Chicago")
        p = app.ctx.profile
        p.money = 5_000.0
        assert "refrigerated" not in p.career.endorsements  # level 1

        app.push_state(EndorsementCourseState(app.ctx))
        state = app.state
        while "Refrigerated course" not in state.items[state.index].text:
            state.index += 1
        state.items[state.index].action()

        assert "refrigerated" in p.career.endorsements
        assert p.money == pytest.approx(5_000.0 - ENDORSEMENT_COURSE_COSTS["refrigerated"])
        assert "Course complete" in spoken[-1]
        # the purchase persists through a save round-trip
        reloaded = Profile.from_dict(p.to_dict())
        assert "refrigerated" in reloaded.career.endorsements
    finally:
        app.shutdown()


def test_course_is_refused_without_the_money(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import EndorsementCourseState

    app = App()
    try:
        spoken = []
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        app.ctx.profile = Profile(name="Broke Student", current_city="Chicago")
        app.ctx.profile.money = 100.0

        app.push_state(EndorsementCourseState(app.ctx))
        state = app.state
        while "Heavy-haul course" not in state.items[state.index].text:
            state.index += 1
        state.items[state.index].action()

        assert "heavy_haul" not in app.ctx.profile.career.endorsements
        assert app.ctx.profile.money == 100.0
        assert "costs" in spoken[-1]
    finally:
        app.shutdown()


def test_carrier_sponsorship_still_grants_endorsements_by_level():
    career = Career(xp=5_000.0)  # level 4
    assert {"refrigerated", "heavy_haul", "high_value"} <= career.endorsements
    # buying after earning changes nothing
    career.purchased_endorsements.append("refrigerated")
    assert "refrigerated" in career.endorsements


# -- carrier billing on the road -----------------------------------------------------


def _driving(app, business_status=COMPANY_DRIVER):
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Road Bills", current_city="Denver")
    app.ctx.profile.business_status = business_status
    if business_status != COMPANY_DRIVER:
        app.ctx.profile.owned_trucks = ["rig"]
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    driving = DrivingState(app.ctx, _job(), route, trip_seed=99, start_hour=10.0)
    app.push_state(driving)
    driving.truck.fuel_gal = 40.0
    return driving


def _stop(driving, actions=("fuel", "break")):
    return SimpleNamespace(
        name="Test Travel Center",
        at_mi=driving.trip.position_mi,
        type="travel_center",
        actions=tuple(actions),
        services=(),
        parking="limited",
        exit_label="",
        spoken_name="Test Travel Center",
        parking_text="limited truck parking",
    )


def test_company_driver_road_fuel_is_carrier_billed(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import RestStopState

    app = App()
    try:
        spoken = []
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        driving = _driving(app)
        money_before = app.ctx.profile.money
        state = RestStopState(app.ctx, driving, _stop(driving))
        app.push_state(state)

        state._refuel()

        assert app.ctx.profile.money == money_before
        assert driving.truck.fuel_gal == pytest.approx(driving.truck.specs.fuel_tank_gal)
        assert any("carrier fuel card" in text for text in spoken)
    finally:
        app.shutdown()


def test_owner_operator_road_fuel_still_costs_cash(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import RestStopState

    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: None)
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        driving = _driving(app, business_status=LEASED_OWNER_OPERATOR)
        app.ctx.profile.money = 10_000.0
        state = RestStopState(app.ctx, driving, _stop(driving))
        app.push_state(state)

        state._refuel()

        assert app.ctx.profile.money < 10_000.0
    finally:
        app.shutdown()


def test_company_out_of_fuel_rescue_hits_reputation_not_wallet(monkeypatch):
    from freight_fate.app import App

    app = App()
    try:
        events = []
        monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: events.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        driving = _driving(app)
        p = app.ctx.profile
        money_before = p.money
        rep_before = p.career.reputation

        driving._handle_out_of_fuel()

        assert p.money == money_before
        assert p.career.reputation == pytest.approx(rep_before - 2.0)
        assert "carrier account" in events[-1]
    finally:
        app.shutdown()


# -- motel rest ----------------------------------------------------------------------


def test_motel_sleep_costs_money_and_gives_full_rest(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import RestStopState

    app = App()
    try:
        spoken = []
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        driving = _driving(app)
        p = app.ctx.profile
        p.money = 500.0
        p.fatigue = 80.0
        driving.hos.drive(300.0)
        state = RestStopState(app.ctx, driving, _stop(driving, actions=("break", "fuel")))
        app.push_state(state)

        labels = [item.text for item in state.items]
        assert any(label.startswith("Motel room") for label in labels)
        state._motel_sleep()

        assert p.money == pytest.approx(500.0 - MOTEL_COST)
        assert p.fatigue == 0.0
        assert driving.hos.driving_min == 0.0
        assert any("wake fresh" in text for text in spoken)
    finally:
        app.shutdown()


def test_motel_is_refused_when_broke(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import RestStopState

    app = App()
    try:
        spoken = []
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        driving = _driving(app)
        p = app.ctx.profile
        p.money = 20.0
        p.fatigue = 80.0

        state = RestStopState(app.ctx, driving, _stop(driving, actions=("break",)))
        app.push_state(state)
        state._motel_sleep()

        assert p.money == 20.0
        assert p.fatigue == 80.0
        assert "costs" in spoken[-1]
    finally:
        app.shutdown()


def test_parking_full_night_offers_a_motel(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import ParkingFullState

    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: None)
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        driving = _driving(app)
        p = app.ctx.profile
        p.money = 500.0
        p.fatigue = 90.0
        state = ParkingFullState(app.ctx, driving, _stop(driving, actions=("sleep",)))
        app.push_state(state)

        labels = [item.text for item in state.items]
        assert any(label.startswith("Motel room") for label in labels)
        state._motel()

        assert p.money == pytest.approx(500.0 - MOTEL_COST)
        assert p.fatigue == 0.0
    finally:
        app.shutdown()
