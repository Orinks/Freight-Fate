"""Company-driver to owner-operator business arc tests."""

import pygame
import pytest

from freight_fate.models.business import (
    COMPANY_DRIVER,
    LEASED_OWNER_OPERATOR,
    OWNER_OPERATOR_BUY_IN,
    OWNER_OPERATOR_DELIVERIES,
    OWNER_OPERATOR_LEVEL,
    OWNER_OPERATOR_REPUTATION,
    OWNER_OPERATOR_WORKING_CAPITAL,
    business_path_label,
    business_status_summary,
    next_business_unlock,
    owner_operator_eligibility,
)
from freight_fate.models.career import LEVEL_XP
from freight_fate.models.career_ladder import CAREER_RANKS, STARTER_CARRIER_NAME


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def test_twenty_level_ladder_has_business_arc_titles():
    assert len(CAREER_RANKS) == 20
    assert [rank.level for rank in CAREER_RANKS] == list(range(1, 21))
    assert CAREER_RANKS[0].title == "Yard Trainee"
    assert CAREER_RANKS[4].title == "Owner-Operator Apprentice"
    assert CAREER_RANKS[14].title == "Leased-On Owner-Operator"
    assert CAREER_RANKS[-1].title == "Independent Operator"


def test_owner_operator_unlock_requires_career_and_working_capital():
    from freight_fate.models.profile import Profile

    p = Profile(name="Business Gate")

    ok, reasons = owner_operator_eligibility(p)
    assert not ok
    assert any(f"Reach level {OWNER_OPERATOR_LEVEL}" in reason for reason in reasons)
    assert STARTER_CARRIER_NAME in business_status_summary(p)
    assert "company driver" in business_status_summary(p)

    p.career.xp = LEVEL_XP[OWNER_OPERATOR_LEVEL - 1]
    p.career.deliveries = OWNER_OPERATOR_DELIVERIES
    p.career.reputation = OWNER_OPERATOR_REPUTATION
    p.money = OWNER_OPERATOR_BUY_IN + OWNER_OPERATOR_WORKING_CAPITAL

    ok, reasons = owner_operator_eligibility(p)
    assert ok
    assert reasons == ()

    p.pay_advance = 100.0
    ok, reasons = owner_operator_eligibility(p)
    assert not ok
    assert any("advance" in reason for reason in reasons)


def test_level_five_is_preparation_not_owner_operator_unlock():
    from freight_fate.models.profile import Profile

    p = Profile(name="Prep Gate")
    p.career.xp = LEVEL_XP[4]
    p.career.deliveries = 20
    p.career.reputation = 90
    p.money = 200_000.0

    ok, reasons = owner_operator_eligibility(p)

    assert not ok
    assert any(f"Reach level {OWNER_OPERATOR_LEVEL}" in reason for reason in reasons)
    assert "Owner-Operator Apprentice" in business_status_summary(p)
    assert "Regional Fleet Driver" in next_business_unlock(p)


def test_business_path_reports_starter_company_rank_and_next_unlock():
    from freight_fate.models.profile import Profile

    p = Profile(name="Path Copy")
    p.career.xp = LEVEL_XP[10]

    assert STARTER_CARRIER_NAME in business_path_label(p)
    assert "Owner-Operator Candidate" in business_path_label(p)
    assert "Working Capital Builder" in next_business_unlock(p)


def test_business_status_menu_unlocks_owner_operator_when_qualified():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import BusinessStatusState

    app = App()
    try:
        app.ctx.profile = Profile(name="Owner Path", current_city="Chicago")
        p = app.ctx.profile
        p.career.xp = LEVEL_XP[OWNER_OPERATOR_LEVEL - 1]
        p.career.deliveries = OWNER_OPERATOR_DELIVERIES
        p.career.reputation = OWNER_OPERATOR_REPUTATION
        p.money = OWNER_OPERATOR_BUY_IN + OWNER_OPERATOR_WORKING_CAPITAL + 500

        app.push_state(BusinessStatusState(app.ctx))
        menu = app.state
        assert any("Buy into leased-on owner-operator" in item.text for item in menu.items)
        assert any("Carrier and rank" in item.text for item in menu.items)
        assert any("Next business unlock" in item.text for item in menu.items)
        while "Buy into leased-on owner-operator" not in menu.items[menu.index].text:
            menu.handle_event(key_event(pygame.K_DOWN))
        menu.handle_event(key_event(pygame.K_RETURN))

        assert p.business_status == LEASED_OWNER_OPERATOR
        assert p.money == pytest.approx(OWNER_OPERATOR_WORKING_CAPITAL + 500)
        assert p.dispatch_board_cache is None
    finally:
        app.shutdown()


def test_company_driver_garage_service_is_carrier_billed():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import GarageState

    app = App()
    try:
        app.ctx.profile = Profile(name="Company Service", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = COMPANY_DRIVER
        p.money = 25.0
        p.truck_fuel_gal = 0.0
        p.truck_damage_pct = 12.0
        app.push_state(GarageState(app.ctx))

        assert p.visible_owned_trucks() == ()
        assert "assigned company tractor" in app.state.items[0].text
        assert "carrier billed" in app.state.items[0].text
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert p.truck_fuel_gal == pytest.approx(p.truck_specs().fuel_tank_gal)
        assert p.money == pytest.approx(25.0)

        app.state.index = 1
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert p.truck_damage_pct == pytest.approx(0.0)
        assert p.money == pytest.approx(25.0)
    finally:
        app.shutdown()


def test_company_driver_truck_status_says_assigned_not_owned():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.models.trucks import TruckSpecs
    from freight_fate.states.city import CityMenuState

    app = App()
    spoken: list[str] = []
    try:
        app.ctx.profile = Profile(name="Assigned Tractor", current_city="Chicago")
        app.ctx.profile.owned_trucks = ["rig", "heavy_hauler"]  # legacy save data
        app.ctx.profile.truck = "heavy_hauler"
        app.ctx.profile.upgrades = {"engine_tune": 2}
        app.ctx.say = lambda text, interrupt=True: spoken.append(text)
        menu = CityMenuState(app.ctx)
        menu._truck_status()

        assert spoken
        assert "Assigned Northstar Freight Lines tractor" in spoken[-1]
        assert "Owned tractor" not in spoken[-1]
        assert "standard rig" in spoken[-1]
        assert app.ctx.profile.truck_specs().max_torque_nm == pytest.approx(
            TruckSpecs().max_torque_nm)
    finally:
        app.shutdown()


def test_company_driver_shops_hide_owned_truck_language():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import TruckShopState, UpgradeShopState

    app = App()
    spoken: list[str] = []
    try:
        app.ctx.profile = Profile(name="No Ownership", current_city="Chicago")
        p = app.ctx.profile
        p.owned_trucks = ["rig", "heavy_hauler"]  # old save values stay hidden
        p.money = 200_000.0
        app.ctx.say = lambda text, interrupt=True: spoken.append(text)

        app.push_state(TruckShopState(app.ctx))
        assert "carrier-assigned tractor" in app.state.items[0].text
        assert not any("owned" in item.text.lower() for item in app.state.items)
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert p.truck == "rig"
        assert p.money == pytest.approx(200_000.0)
        assert "carrier-assigned" in spoken[-1]

        app.pop_state()
        app.push_state(UpgradeShopState(app.ctx))
        assert "carrier-assigned tractor" in app.state.items[0].text
        assert not any("owned" in item.text.lower() for item in app.state.items)
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert p.upgrades == {}
        assert p.money == pytest.approx(200_000.0)
        assert "carrier-assigned" in spoken[-1]
    finally:
        app.shutdown()


def test_owner_operator_buy_in_records_first_owned_tractor():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import BusinessStatusState

    app = App()
    try:
        app.ctx.profile = Profile(name="Buy In Equipment", current_city="Chicago")
        p = app.ctx.profile
        p.career.xp = LEVEL_XP[OWNER_OPERATOR_LEVEL - 1]
        p.career.deliveries = OWNER_OPERATOR_DELIVERIES
        p.career.reputation = OWNER_OPERATOR_REPUTATION
        p.money = OWNER_OPERATOR_BUY_IN + OWNER_OPERATOR_WORKING_CAPITAL

        app.push_state(BusinessStatusState(app.ctx))
        while (
            "Buy into leased-on owner-operator"
            not in app.state.items[app.state.index].text
        ):
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert p.business_status == LEASED_OWNER_OPERATOR
        assert p.truck == "rig"
        assert p.visible_owned_trucks() == ("rig",)
    finally:
        app.shutdown()


def test_owner_operator_can_buy_switch_and_upgrade_owned_equipment():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import TruckShopState, UpgradeShopState

    app = App()
    try:
        app.ctx.profile = Profile(name="Owned Equipment", current_city="Chicago")
        p = app.ctx.profile
        p.business_status = LEASED_OWNER_OPERATOR
        p.owned_trucks = ["rig"]
        p.money = 200_000.0

        app.push_state(UpgradeShopState(app.ctx))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert p.upgrades
        assert p.money < 200_000.0

        app.pop_state()
        money_after_upgrade = p.money
        app.push_state(TruckShopState(app.ctx))
        while "Heavy hauler" not in app.state.items[app.state.index].text:
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert p.truck == "heavy_hauler"
        assert "heavy_hauler" in p.visible_owned_trucks()
        assert p.money == pytest.approx(money_after_upgrade - 52_000.0)

        while "Standard rig" not in app.state.items[app.state.index].text:
            app.state.handle_event(key_event(pygame.K_DOWN))
        money_before_switch = p.money
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert p.truck == "rig"
        assert p.money == pytest.approx(money_before_switch)
    finally:
        app.shutdown()


def test_company_driver_board_labels_carrier_gross(world):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import CityMenuState, JobBoardState

    app = App()
    try:
        app.ctx.profile = Profile(name="Board Labels", current_city="Chicago")
        app.push_state(CityMenuState(app.ctx))
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, JobBoardState)
        assert app.state.jobs
        assert "Carrier gross" in app.state.items[0].text
    finally:
        app.shutdown()


def test_late_company_driver_still_uses_company_settlement_until_buy_in():
    from freight_fate.models.business import build_business_settlement
    from freight_fate.models.jobs import CARGO_CATALOG, Job

    job = Job(
        CARGO_CATALOG["general"],
        18.0,
        "Chicago",
        "Chicago yard",
        "Milwaukee",
        92.0,
        1800.0,
        6.0,
    )
    settlement = build_business_settlement(
        COMPANY_DRIVER, job, 1800.0, on_time=True, driver_charges=0.0)

    assert settlement.status == COMPANY_DRIVER
    assert settlement.business_charges == ()
