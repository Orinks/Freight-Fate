"""Company-driver to owner-operator business arc tests."""

import pygame
import pytest

from freight_fate.models.business import (
    COMPANY_DRIVER,
    LEASED_OWNER_OPERATOR,
    OWNER_OPERATOR_BUY_IN,
    OWNER_OPERATOR_WORKING_CAPITAL,
    business_status_summary,
    owner_operator_eligibility,
)


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def test_owner_operator_unlock_requires_career_and_working_capital():
    from freight_fate.models.profile import Profile

    p = Profile(name="Business Gate")

    ok, reasons = owner_operator_eligibility(p)
    assert not ok
    assert any("Reach level 5" in reason for reason in reasons)
    assert "company driver" in business_status_summary(p)

    p.career.xp = 7000
    p.career.deliveries = 10
    p.career.reputation = 65
    p.money = OWNER_OPERATOR_BUY_IN + OWNER_OPERATOR_WORKING_CAPITAL

    ok, reasons = owner_operator_eligibility(p)
    assert ok
    assert reasons == ()

    p.pay_advance = 100.0
    ok, reasons = owner_operator_eligibility(p)
    assert not ok
    assert any("advance" in reason for reason in reasons)


def test_business_status_menu_unlocks_owner_operator_when_qualified():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import BusinessStatusState

    app = App()
    try:
        app.ctx.profile = Profile(name="Owner Path", current_city="Chicago")
        p = app.ctx.profile
        p.career.xp = 7000
        p.career.deliveries = 10
        p.career.reputation = 65
        p.money = OWNER_OPERATOR_BUY_IN + OWNER_OPERATOR_WORKING_CAPITAL + 500

        app.push_state(BusinessStatusState(app.ctx))
        menu = app.state
        assert any("Become owner-operator" in item.text for item in menu.items)
        while "Become owner-operator" not in menu.items[menu.index].text:
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
