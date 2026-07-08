"""Career start choices, carrier benefits, and equipment semantics."""

import pygame
import pytest

from freight_fate.models.business import (
    COMPANY_DRIVER,
    LEASED_OWNER_OPERATOR,
    OWNER_OPERATOR_LEVEL,
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

    northstar = company_driver_pay(short_job, short_job.pay, True, DEFAULT_START_KEY)
    training = company_driver_pay(short_job, short_job.pay, True, "great_lakes_training")
    assert training > northstar

    northstar_long = company_driver_pay(long_floor_job, long_floor_job.pay, True, DEFAULT_START_KEY)
    prairie = company_driver_pay(long_floor_job, long_floor_job.pay, True, "prairie_link")
    assert prairie > northstar_long

    northstar_bonus = company_driver_pay(
        high_gross_job, high_gross_job.pay, True, DEFAULT_START_KEY
    )
    summit = company_driver_pay(high_gross_job, high_gross_job.pay, True, "summit_value")
    assert summit > northstar_bonus


def test_carrier_key_changes_settlement_math():
    job = _job(miles=80.0, pay=600.0)

    northstar = build_business_settlement(
        COMPANY_DRIVER,
        job,
        job.pay,
        on_time=True,
        driver_charges=0.0,
        carrier_key=DEFAULT_START_KEY,
    )
    training = build_business_settlement(
        COMPANY_DRIVER,
        job,
        job.pay,
        on_time=True,
        driver_charges=0.0,
        carrier_key="great_lakes_training",
    )

    assert training.net_before_advance > northstar.net_before_advance
    assert training.business_charges == ()


def test_carrier_key_can_bias_job_mix_weighting(world):
    from freight_fate.models.jobs import JobBoard

    board = JobBoard(world, seed=1)

    baseline = board._cargo_weight(  # noqa: SLF001 - focused model regression
        world.city("Kansas City"), "grain", DEFAULT_START_KEY
    )
    prairie = board._cargo_weight(  # noqa: SLF001 - focused model regression
        world.city("Kansas City"), "grain", "prairie_link"
    )

    assert prairie > baseline


def test_company_carriers_have_distinct_dispatch_weighting(world):
    from freight_fate.models.jobs import JobBoard

    board = JobBoard(world, seed=1)
    chicago = world.resolve_city_key("Chicago")
    milwaukee = world.resolve_city_key("Milwaukee")
    kc_key = world.resolve_city_key("Kansas City")
    short = next(c for c in board._candidates(chicago) if c[0] == milwaukee)  # noqa: SLF001
    long = next(c for c in board._candidates(chicago) if c[0] == kc_key)  # noqa: SLF001

    northstar_short_ratio = board._destination_weight(  # noqa: SLF001
        chicago, short, 2, DEFAULT_START_KEY
    ) / board._destination_weight(chicago, long, 2, DEFAULT_START_KEY)  # noqa: SLF001
    training_short_ratio = board._destination_weight(  # noqa: SLF001
        chicago, short, 2, "great_lakes_training"
    ) / board._destination_weight(chicago, long, 2, "great_lakes_training")  # noqa: SLF001
    assert training_short_ratio > northstar_short_ratio

    kansas_city = world.resolve_city_key("Kansas City")
    origin_region = world.cities[kansas_city].region
    same_region = next(
        c
        for c in board._candidates(kansas_city)  # noqa: SLF001
        if world.cities[c[0]].region == origin_region
    )
    other_region = next(
        c
        for c in board._candidates(kansas_city)  # noqa: SLF001
        if world.cities[c[0]].region != origin_region
    )
    prairie_region_ratio = board._destination_weight(  # noqa: SLF001
        kansas_city, same_region, 2, "prairie_link"
    ) / board._destination_weight(kansas_city, other_region, 2, "prairie_link")  # noqa: SLF001
    northstar_region_ratio = board._destination_weight(  # noqa: SLF001
        kansas_city, same_region, 2, DEFAULT_START_KEY
    ) / board._destination_weight(kansas_city, other_region, 2, DEFAULT_START_KEY)  # noqa: SLF001
    assert prairie_region_ratio > northstar_region_ratio

    cap = board.distance_cap(5)
    candidate = (world.resolve_city_key("Los Angeles"), cap, 3)
    denver = world.resolve_city_key("Denver")
    assert board._destination_weight(  # noqa: SLF001
        denver, candidate, 5, "summit_value"
    ) > board._destination_weight(denver, candidate, 5, DEFAULT_START_KEY)  # noqa: SLF001


def test_training_carrier_adds_modest_deadline_slack(world):
    from freight_fate.models.jobs import JobBoard

    cargo = CARGO_CATALOG["general"]
    origin = world.city("Chicago").locations[0]
    destination = world.city("Milwaukee").locations[0]
    northstar = JobBoard(world, seed=8)._make_job(  # noqa: SLF001
        cargo,
        "Chicago",
        origin.name,
        "Milwaukee",
        92.0,
        None,
        1,
        origin,
        destination,
        DEFAULT_START_KEY,
    )
    training = JobBoard(world, seed=8)._make_job(  # noqa: SLF001
        cargo,
        "Chicago",
        origin.name,
        "Milwaukee",
        92.0,
        None,
        1,
        origin,
        destination,
        "great_lakes_training",
    )

    assert training.deadline_game_h > northstar.deadline_game_h


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
    assert p.active_trailer_programs() == ("dry_van",)
    assert p.money == pytest.approx(18_000.0)
    assert p.truck_damage_pct > 0
    assert p.career.level >= OWNER_OPERATOR_LEVEL
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
    spoken = []
    try:
        app.ctx.say = lambda text, *a, **k: spoken.append(text)
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
        assert "First-day briefing" in spoken[-1]
        assert "Prairie Link Regional" in spoken[-1]
        assert "same-region lanes" in spoken[-1]
        assert any(item.text == "First-day briefing" for item in app.state.items)
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


def test_first_day_briefing_names_owner_operator_costs():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import (
        CityMenuState,
        first_day_orientation_message,
        first_dispatch_done,
    )

    app = App()
    try:
        app.ctx.profile = Profile(name="Owner Briefing", current_city="Chicago")
        apply_start_option(app.ctx.profile, start_option(OWNER_OPERATOR_START_KEY))
        state = CityMenuState(app.ctx)
        state.refresh()

        message = first_day_orientation_message(app.ctx)

        assert "leased to Northstar Freight Lines" in message
        assert "own the starter tractor" in message
        assert "working capital" in message
        assert "fuel, repairs, truck wear" in message
        assert all(item.text != "First-day briefing" for item in state.items)
        assert any(item.text == "Career plan" for item in state.items)
        assert not first_dispatch_done(app.ctx.profile)

        app.ctx.profile.achievements.append("first_dispatch")
        state.refresh()
        assert all(item.text != "First-day briefing" for item in state.items)
        assert first_dispatch_done(app.ctx.profile)
    finally:
        app.shutdown()
