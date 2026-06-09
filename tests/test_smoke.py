"""Headless end-to-end smoke test: boot the app and play through a delivery."""

import pygame
import pytest


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


@pytest.mark.smoke
def test_full_game_flow_headless():
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState, JobBoardState, RouteSelectState
    from freight_fate.states.driving import ArrivalState, DrivingState
    from freight_fate.states.main_menu import MainMenuState, NameEntryState

    app = App()
    try:
        app.push_state(MainMenuState(app.ctx))
        menu = app.state
        assert isinstance(menu, MainMenuState)
        assert menu.lines()[0] == "Freight Fate"

        # navigate to "New career" and select it
        while menu.items[menu.index].text != "New career":
            menu.handle_event(key_event(pygame.K_DOWN))
        menu.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, NameEntryState)

        for ch in "Smoke":
            app.state.handle_event(key_event(ord(ch.lower()), ch))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CityMenuState)
        assert app.ctx.profile is not None
        assert app.ctx.profile.name == "Smoke"

        # open job board, accept the first job
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, JobBoardState)
        assert app.state.jobs
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, RouteSelectState)
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, DrivingState)

        driving = app.state
        # start the engine and drive the whole trip with simulated input
        driving.handle_event(key_event(pygame.K_e))
        assert driving.truck.engine_on
        driving.truck.transmission.automatic = True
        money_before = app.ctx.profile.money

        for _frame in range(60 * 60 * 30):
            driving.truck.throttle = 0.9
            driving.truck.auto_shift()
            driving.truck.update(1 / 60)
            for event in driving.trip.update(1 / 60):
                driving._handle_trip_event(event)
            driving._update_hazard(1 / 60)
            # always brake through hazards so the smoke run never crashes
            if driving._hazard_deadline is not None:
                driving.truck.velocity_mps = 5.0
            if driving.trip.finished:
                driving._arrive()
                break
        assert isinstance(app.state, ArrivalState)
        assert app.ctx.profile.money > money_before
        assert app.ctx.profile.career.deliveries == 1
        assert app.ctx.profile.current_city == driving.job.destination

        # continue back to the city hub
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CityMenuState)

        # render a frame of every reachable lines() output
        app.render()
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_menu_first_letter_navigation():
    from freight_fate.app import App
    from freight_fate.states.main_menu import MainMenuState

    app = App()
    try:
        app.push_state(MainMenuState(app.ctx))
        menu = app.state
        menu.handle_event(key_event(ord("s"), "s"))
        assert menu.items[menu.index].text.lower().startswith("s")
        menu.handle_event(key_event(pygame.K_END))
        assert menu.index == len(menu.items) - 1
        menu.handle_event(key_event(pygame.K_HOME))
        assert menu.index == 0
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_garage_upgrade_and_truck_purchase_flow():
    from freight_fate.app import App
    from freight_fate.states.city import (
        CityMenuState,
        GarageState,
        TruckShopState,
        UpgradeShopState,
    )
    from freight_fate.states.main_menu import MainMenuState, NameEntryState

    app = App()
    try:
        app.push_state(MainMenuState(app.ctx))
        while app.state.items[app.state.index].text != "New career":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, NameEntryState)
        app.state.handle_event(key_event(pygame.K_RETURN))  # default name
        assert isinstance(app.state, CityMenuState)
        p = app.ctx.profile
        p.money = 200_000.0

        # city -> garage -> upgrades
        while not app.state.items[app.state.index].text.startswith("Garage"):
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, GarageState)
        while app.state.items[app.state.index].text != "Upgrades":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, UpgradeShopState)

        # buy engine tune tier 1, then tier 2; a third press must not charge
        shop = app.state
        while "Engine tune" not in shop.items[shop.index].text:
            shop.handle_event(key_event(pygame.K_DOWN))
        shop.handle_event(key_event(pygame.K_RETURN))
        assert p.upgrades.get("engine_tune") == 1
        shop.handle_event(key_event(pygame.K_RETURN))
        assert p.upgrades.get("engine_tune") == 2
        money_after_tiers = p.money
        shop.handle_event(key_event(pygame.K_RETURN))
        assert p.upgrades.get("engine_tune") == 2
        assert p.money == money_after_tiers
        assert "owned" in shop.items[shop.index].text

        # back to garage, then the truck shop
        shop.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, GarageState)
        while app.state.items[app.state.index].text != "Trucks":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, TruckShopState)

        trucks = app.state
        while "Heavy hauler" not in trucks.items[trucks.index].text:
            trucks.handle_event(key_event(pygame.K_DOWN))
        money_before = p.money
        trucks.handle_event(key_event(pygame.K_RETURN))
        assert p.truck == "heavy_hauler"
        assert "heavy_hauler" in p.owned_trucks
        assert p.money == money_before - 52_000.0
        assert "currently driving" in trucks.items[trucks.index].text

        # switch back to the standard rig (already owned, no charge)
        money_before = p.money
        while "Standard rig" not in trucks.items[trucks.index].text:
            trucks.handle_event(key_event(pygame.K_DOWN))
        trucks.handle_event(key_event(pygame.K_RETURN))
        assert p.truck == "rig"
        assert p.money == money_before
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_upgrades_are_money_gated():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import UpgradeShopState

    app = App()
    try:
        app.ctx.profile = Profile(name="Broke")
        app.ctx.profile.money = 10.0
        app.push_state(UpgradeShopState(app.ctx))
        shop = app.state
        shop.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.profile.upgrades == {}
        assert app.ctx.profile.money == 10.0
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_pause_and_abandon_returns_to_city():
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState
    from freight_fate.states.driving import DrivingState, PauseMenuState
    from freight_fate.states.main_menu import MainMenuState, NameEntryState

    app = App()
    try:
        app.push_state(MainMenuState(app.ctx))
        while app.state.items[app.state.index].text != "New career":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, NameEntryState)
        app.state.handle_event(key_event(pygame.K_RETURN))  # default name
        app.state.handle_event(key_event(pygame.K_RETURN))  # job board
        app.state.handle_event(key_event(pygame.K_RETURN))  # accept job
        app.state.handle_event(key_event(pygame.K_RETURN))  # pick route
        assert isinstance(app.state, DrivingState)
        origin = app.state.job.origin

        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, PauseMenuState)
        pause = app.state
        money = app.ctx.profile.money
        while pause.items[pause.index].text != "Abandon job":
            pause.handle_event(key_event(pygame.K_DOWN))
        pause.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CityMenuState)
        assert app.ctx.profile.money == money - 500.0
        assert app.ctx.profile.current_city == origin
    finally:
        app.shutdown()
