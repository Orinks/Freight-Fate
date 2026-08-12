"""Career economy balance: carrier billing, XP pacing, trust pay, money sinks."""

from types import SimpleNamespace

import pytest
from speech_capture import speech_stub

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
    assert xp_class_multiplier(CARGO_CATALOG["refrigerated"]) == pytest.approx(1.5)
    assert xp_class_multiplier(CARGO_CATALOG["electronics"]) == pytest.approx(1.5)
    assert xp_class_multiplier(CARGO_CATALOG["automotive"]) == pytest.approx(1.25)
    assert xp_class_multiplier(CARGO_CATALOG["general"]) == pytest.approx(1.0)


def test_on_time_streak_compounds_and_late_resets_it():
    career = Career()
    career.record_delivery(100.0, 500.0, on_time=True, damage_pct=50.0)
    assert career.on_time_streak == 1
    first = career.xp
    # completion XP plus per-mile XP, no streak bonus on the first run
    assert first == pytest.approx(150.0 + 100.0 * 1.6)

    career.record_delivery(100.0, 500.0, on_time=True, damage_pct=50.0)
    assert career.xp - first == pytest.approx((150.0 + 100.0 * 1.6) * 1.05)  # streak of 2

    career.record_delivery(100.0, 500.0, on_time=False, damage_pct=50.0)
    assert career.on_time_streak == 0


def test_late_deliveries_still_teach_a_reduced_lesson():
    career = Career()
    career.record_delivery(100.0, 500.0, on_time=False, damage_pct=50.0)
    assert career.xp == pytest.approx(75.0 + 100.0 * 0.9)


def test_clean_cargo_pays_a_bonus_lesson():
    career = Career()
    career.record_delivery(100.0, 500.0, on_time=True, damage_pct=0.0)
    assert career.xp == pytest.approx((150.0 + 100.0 * 1.6) * 1.15)


def test_streak_bonus_caps_near_half():
    assert xp_streak_bonus(1) == pytest.approx(0.0)
    assert xp_streak_bonus(3) == pytest.approx(0.10)
    assert xp_streak_bonus(6) == pytest.approx(0.25)
    assert xp_streak_bonus(10) == pytest.approx(0.45)
    assert xp_streak_bonus(40) == pytest.approx(0.45)


def test_short_hop_streak_bonus_is_capped_at_the_mileage_xp():
    # A board-minimum 25-mile hop at a deep on-time streak: the streak bonus
    # is capped at what the miles themselves taught (25 * 1.6 = 40 XP), not
    # 45 percent of the whole award including the flat completion XP. This is
    # the short-hop farming cap: a streak can at most double the road lesson,
    # it cannot mint XP off the flat per-delivery award.
    career = Career()
    career.on_time_streak = 9  # this delivery makes it 10, the share cap
    career.record_delivery(25.0, 300.0, on_time=True, damage_pct=0.0)
    base = 150.0 + 25.0 * 1.6
    mileage_xp = 25.0 * 1.6
    assert career.xp == pytest.approx((base + mileage_xp) * 1.15)


def test_streak_beyond_the_cap_adds_nothing_more():
    # Once both caps are saturated, a longer streak earns the same bonus.
    at_cap = Career()
    at_cap.on_time_streak = 19
    at_cap.record_delivery(25.0, 300.0, on_time=True, damage_pct=0.0)

    far_beyond = Career()
    far_beyond.on_time_streak = 39
    far_beyond.record_delivery(25.0, 300.0, on_time=True, damage_pct=0.0)

    assert far_beyond.xp == pytest.approx(at_cap.xp)


def test_honest_haul_streak_values_unchanged_below_the_cap():
    # Real freight is untouched: on any haul long enough that the road XP
    # exceeds the capped share of the award (about 77 miles and up at plain
    # freight), the streak bonus is the same arithmetic it has always been.
    long_haul = Career()
    long_haul.on_time_streak = 11  # deep streak, share already at 0.45
    long_haul.record_delivery(500.0, 1800.0, on_time=True, damage_pct=0.0)
    assert long_haul.xp == pytest.approx((150.0 + 500.0 * 1.6) * 1.45 * 1.15)

    # Even the shortest freight the honest pacing model deals (105 miles at
    # level 1) sits above the threshold; 80 miles still clears it.
    short_honest = Career()
    short_honest.on_time_streak = 14
    short_honest.record_delivery(80.0, 400.0, on_time=True, damage_pct=0.0)
    assert short_honest.xp == pytest.approx((150.0 + 80.0 * 1.6) * 1.45 * 1.15)


def test_specialty_multiplier_applies_through_record_delivery():
    career = Career()
    career.record_delivery(100.0, 500.0, on_time=True, damage_pct=50.0, cargo_class_mult=1.5)
    assert career.xp == pytest.approx(150.0 + 100.0 * 1.6 * 1.5)


def test_single_level_up_speaks_the_one_rank(monkeypatch):
    """A one-rank promotion keeps the exact wording players already expect."""
    from freight_fate.models.career_ladder import rank_for_level

    career = Career()
    # 150 completion + 600 * 1.6 mileage XP = 1110: past the 1000 threshold
    # for level 2, short of the 2500 threshold for level 3.
    messages = career.record_delivery(600.0, 900.0, on_time=True, damage_pct=50.0)
    assert career.level == 2
    rank = rank_for_level(2)
    level_ups = [m for m in messages if m.startswith("Level up!")]
    assert level_ups == [f"Level up! You are now level 2: {rank.title}. Unlock: {rank.unlock}"]


def test_multi_level_up_speaks_every_rank_passed_through(monkeypatch):
    """A delivery big enough to jump several ranks must not go silent on the
    ranks in between -- every passed rank's unlock is spoken, in order."""
    from freight_fate.models.career_ladder import rank_for_level

    career = Career()
    career.xp = 999.0  # one XP short of level 2
    assert career.level == 1
    # 150 completion + 3000 * 1.6 mileage XP = 4950; 999 + 4950 = 5949,
    # which lands inside the level-4 band (4500..7000): levels 2 and 3 are
    # passed through in the same delivery.
    messages = career.record_delivery(3000.0, 5000.0, on_time=True, damage_pct=50.0)
    assert career.level == 4
    level_ups = [m for m in messages if m.startswith("Level up!")]
    assert level_ups == [
        f"Level up! You are now level {lvl}: {rank_for_level(lvl).title}. "
        f"Unlock: {rank_for_level(lvl).unlock}"
        for lvl in (2, 3, 4)
    ]


def test_first_twenty_thresholds_stay_save_compatible():
    from freight_fate.models.career import LEVEL_XP

    # Shipped 1.8 careers were leveled against these numbers; changing them
    # would silently re-level existing saves.
    assert LEVEL_XP[:20] == [
        0,
        1000,
        2500,
        4500,
        7000,
        10_000,
        14_000,
        19_000,
        25_000,
        32_000,
        40_000,
        50_000,
        62_000,
        76_000,
        92_000,
        110_000,
        130_000,
        152_000,
        176_000,
        202_000,
    ]
    assert len(LEVEL_XP) == 30
    assert sorted(LEVEL_XP) == LEVEL_XP


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
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
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
        assert any("Course complete" in text for text in spoken)
        # Paying your own tuition earns its badge, spoken after the course.
        assert "self_paid_course" in p.achievements
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
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
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
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
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
        monkeypatch.setattr(app.ctx, "say", speech_stub())
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
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events))
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
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
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


def test_motel_sleep_shuts_the_engine_off(monkeypatch):
    """A motel room is still a real sleep: the truck must not idle all night
    just because the driver bedded down off the lot instead of in the
    sleeper. Every other sleep option already shut the engine down; the
    motel room was the one path that skipped it while still sending the
    driver to bed (tester report: Darren Duff, build 1.9.0.dev0)."""
    from freight_fate.app import App
    from freight_fate.states.driving import RestStopState

    app = App()
    try:
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        driving = _driving(app)
        p = app.ctx.profile
        p.money = 500.0
        driving.truck.start_engine()
        app.ctx.audio.engine_start(play_start_sound=False)
        assert driving.truck.engine_on is True
        assert app.ctx.audio.engine_running is True
        state = RestStopState(app.ctx, driving, _stop(driving, actions=("break", "fuel")))
        app.push_state(state)

        state._motel_sleep()

        # The engine is off at the start of the sleep, in both the sim state
        # and the audio loop -- not just claimed, actually stopped.
        assert driving.truck.engine_on is False
        assert app.ctx.audio.engine_running is False
        assert any("shut down the engine" in text for text in spoken)
    finally:
        app.shutdown()


def test_motel_is_refused_when_broke(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import RestStopState

    app = App()
    try:
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
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
        monkeypatch.setattr(app.ctx, "say", speech_stub())
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


def test_parking_full_motel_shuts_the_engine_off_and_wake_prompt_matches(monkeypatch):
    """The full-lot motel path used to end with "Press E to start the
    engine" without ever having stopped it -- the wake prompt claimed a
    state the sim never reached. Shutting the engine down here makes that
    prompt true instead of just spoken."""
    from freight_fate.app import App
    from freight_fate.states.driving import ParkingFullState

    app = App()
    try:
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        driving = _driving(app)
        p = app.ctx.profile
        p.money = 500.0
        driving.truck.start_engine()
        app.ctx.audio.engine_start(play_start_sound=False)
        state = ParkingFullState(app.ctx, driving, _stop(driving, actions=("sleep",)))
        app.push_state(state)

        state._motel()

        # The wake prompt tells the driver to start the engine; that must
        # actually be true, in both the sim state and the audio loop.
        assert driving.truck.engine_on is False
        assert app.ctx.audio.engine_running is False
        assert any("start the engine" in text for text in spoken)
    finally:
        app.shutdown()


def test_a_full_lot_still_lets_you_fuel(monkeypatch):
    """The pumps and the parking lot are separate facilities.

    A full lot used to swallow the whole stop, so an overnight run could
    pass a row of open pumps and still go dry between stops.
    """
    from freight_fate.app import App
    from freight_fate.states.driving import ParkingFullState

    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        driving = _driving(app, business_status=LEASED_OWNER_OPERATOR)
        p = app.ctx.profile
        p.money = 5_000.0
        driving.truck.fuel_gal = 20.0
        state = ParkingFullState(app.ctx, driving, _stop(driving, actions=("sleep", "fuel")))
        app.push_state(state)

        labels = [item.text for item in state.items]
        assert any(label.startswith("Refuel ") for label in labels)
        state._refuel()

        assert driving.truck.fuel_gal == pytest.approx(driving.truck.specs.fuel_tank_gal)
        assert p.money < 5_000.0
    finally:
        app.shutdown()


def test_a_full_lot_without_pumps_offers_no_fuel(monkeypatch):
    """A rest area is not a truck stop: no island, no fuel row."""
    from freight_fate.app import App
    from freight_fate.states.driving import ParkingFullState

    app = App()
    try:
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
        driving = _driving(app)
        state = ParkingFullState(app.ctx, driving, _stop(driving, actions=("sleep",)))
        app.push_state(state)

        assert not any(item.text.startswith("Refuel ") for item in state.items)
    finally:
        app.shutdown()
