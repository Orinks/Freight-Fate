"""Career start choices, carrier benefits, and equipment semantics."""

import pygame
import pytest

from freight_fate.models.business import (
    COMPANY_DRIVER,
    LEASED_OWNER_OPERATOR,
    build_business_settlement,
    company_driver_pay,
)
from freight_fate.models.jobs import CARGO_CATALOG, Job
from freight_fate.models.start_options import (
    DEFAULT_START_KEY,
    OWNER_OPERATOR_START_KEY,
    START_MODE_COMPANY,
    START_MODE_OWNER_OPERATOR,
    START_OPTIONS,
    all_start_options,
    apply_start_option,
    company_start_options,
    start_option,
)


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def _job(*, miles=80.0, pay=600.0):
    return Job(
        CARGO_CATALOG["general"],
        12.0,
        "Chicago",
        "Chicago yard",
        "Milwaukee",
        miles,
        pay,
        8.0,
    )


def test_start_options_are_grounded_and_player_facing():
    options = all_start_options()
    company = company_start_options()

    assert len(company) >= 3
    assert START_OPTIONS[DEFAULT_START_KEY].carrier_name == "Northstar Freight Lines"
    assert any(option.mode == START_MODE_OWNER_OPERATOR for option in options)
    for option in options:
        assert option.label
        assert option.menu_summary
        assert option.help_text
        if option.mode == START_MODE_COMPANY:
            assert option.company_pay is not None
            assert option.owned_trucks == ()
            assert "carrier" in option.help_text.lower()
        else:
            assert option.mode == START_MODE_OWNER_OPERATOR
            assert option.owned_trucks
            assert option.starting_money > 0
            assert "operating costs" in option.help_text


def test_company_carrier_pay_plans_have_distinct_benefits():
    short_job = _job(miles=80.0, pay=600.0)
    long_floor_job = _job(miles=500.0, pay=500.0)
    high_gross_job = _job(miles=300.0, pay=3000.0)

    northstar = company_driver_pay(
        short_job, short_job.pay, True, DEFAULT_START_KEY)
    training = company_driver_pay(
        short_job, short_job.pay, True, "great_lakes_training")
    assert training > northstar

    northstar_long = company_driver_pay(
        long_floor_job, long_floor_job.pay, True, DEFAULT_START_KEY)
    prairie = company_driver_pay(
        long_floor_job, long_floor_job.pay, True, "prairie_link")
    assert prairie > northstar_long

    northstar_bonus = company_driver_pay(
        high_gross_job, high_gross_job.pay, True, DEFAULT_START_KEY)
    summit = company_driver_pay(
        high_gross_job, high_gross_job.pay, True, "summit_value")
    assert summit > northstar_bonus


def test_carrier_key_changes_settlement_math():
    job = _job(miles=80.0, pay=600.0)

    northstar = build_business_settlement(
        COMPANY_DRIVER, job, job.pay, on_time=True, driver_charges=0.0,
        carrier_key=DEFAULT_START_KEY)
    training = build_business_settlement(
        COMPANY_DRIVER, job, job.pay, on_time=True, driver_charges=0.0,
        carrier_key="great_lakes_training")

    assert training.net_before_advance > northstar.net_before_advance
    assert training.business_charges == ()


def test_carrier_key_can_bias_job_mix_weighting(world):
    from freight_fate.models.jobs import JobBoard

    board = JobBoard(world, seed=1)

    baseline = board._cargo_weight(  # noqa: SLF001 - focused model regression
        world.cities["Kansas City"], "grain", DEFAULT_START_KEY)
    prairie = board._cargo_weight(  # noqa: SLF001 - focused model regression
        world.cities["Kansas City"], "grain", "prairie_link")

    assert prairie > baseline


def test_apply_company_start_keeps_assigned_equipment():
    from freight_fate.models.profile import Profile

    p = Profile(name="Company Choice", current_city="Milwaukee")
    apply_start_option(p, start_option("great_lakes_training"))

    assert p.carrier_name == "Great Lakes Training Transport"
    assert p.carrier_key == "great_lakes_training"
    assert p.start_mode == START_MODE_COMPANY
    assert p.business_status == COMPANY_DRIVER
    assert p.owned_trucks == []
    assert p.visible_owned_trucks() == ()
    assert not p.owns_equipment()


def test_owner_operator_start_applies_owned_equipment_and_costs():
    from freight_fate.models.profile import Profile

    p = Profile(name="Owner Start", current_city="Chicago")
    apply_start_option(p, start_option(OWNER_OPERATOR_START_KEY))

    assert p.start_mode == START_MODE_OWNER_OPERATOR
    assert p.business_status == LEASED_OWNER_OPERATOR
    assert p.owns_equipment()
    assert p.visible_owned_trucks() == ("rig",)
    assert p.money == pytest.approx(18_000.0)
    assert p.truck_damage_pct > 0
    assert p.career.level >= 15
    assert p.career.deliveries >= 35
    assert p.career.total_miles > 0


def test_new_career_start_menu_lists_company_and_owner_operator():
    from freight_fate.app import App
    from freight_fate.states.main_menu import CareerStartState

    app = App()
    try:
        app.push_state(CareerStartState(app.ctx, "Choice Driver"))
        labels = [item.text for item in app.state.items]

        assert any("Northstar Freight Lines" in label for label in labels)
        assert any("Great Lakes Training Transport" in label for label in labels)
        assert any("Owner-operator start" in label for label in labels)
        assert "assigned carrier equipment" in app.state.intro_help
        assert "higher risk" in app.state.intro_help
    finally:
        app.shutdown()


def test_new_company_career_choice_creates_company_profile():
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState
    from freight_fate.states.main_menu import CareerStartState, HomeCityState

    app = App()
    try:
        app.push_state(CareerStartState(app.ctx, "Prairie Driver"))
        while "Prairie Link Regional" not in app.state.items[app.state.index].text:
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, HomeCityState)
        assert "Kansas City" in app.state.items[app.state.index].text
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, CityMenuState)
        profile = app.ctx.profile
        assert profile.carrier_name == "Prairie Link Regional"
        assert profile.business_status == COMPANY_DRIVER
        assert profile.visible_owned_trucks() == ()
    finally:
        app.shutdown()


def test_owner_operator_start_unlocks_equipment_systems():
    from freight_fate.app import App
    from freight_fate.states.city import TruckShopState, UpgradeShopState
    from freight_fate.states.main_menu import CareerStartState, HomeCityState

    app = App()
    try:
        app.push_state(CareerStartState(app.ctx, "Owner Choice"))
        while "Owner-operator start" not in app.state.items[app.state.index].text:
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, HomeCityState)
        app.state.handle_event(key_event(pygame.K_RETURN))

        profile = app.ctx.profile
        assert profile.business_status == LEASED_OWNER_OPERATOR
        assert profile.visible_owned_trucks() == ("rig",)

        app.push_state(TruckShopState(app.ctx))
        assert "currently driving" in app.state.items[0].text
        assert any("buy for" in item.text for item in app.state.items)
        app.pop_state()
        app.push_state(UpgradeShopState(app.ctx))
        assert "locked" not in app.state.items[0].text.lower()
    finally:
        app.shutdown()
