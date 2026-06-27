"""Headless end-to-end smoke test: boot the app and play through a delivery."""

import pygame
import pytest


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def finish_timed_state(app):
    from freight_fate.states.base import TimedMessageState

    assert isinstance(app.state, TimedMessageState)
    app.state.update(app.state.remaining + 0.01)


def select(menu, label):
    while not menu.items[menu.index].text.startswith(label):
        menu.handle_event(key_event(pygame.K_DOWN))
    menu.handle_event(key_event(pygame.K_RETURN))


@pytest.mark.smoke
def test_garage_offers_partial_fuel_and_repairs_when_cash_is_short():
    from freight_fate.app import App
    from freight_fate.models.business import LEASED_OWNER_OPERATOR
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import GarageState

    app = App()
    try:
        app.ctx.profile = Profile(name="Partial Garage")
        p = app.ctx.profile
        p.current_city = "Chicago"
        p.business_status = LEASED_OWNER_OPERATOR
        app.push_state(GarageState(app.ctx))

        p.money = 100.0
        p.truck_fuel_gal = 0.0
        select(app.state, "Refuel")
        assert 1.0 <= p.truck_fuel_gal < p.truck_specs().fuel_tank_gal
        assert p.money == pytest.approx(0.0, abs=0.01)

        p.money = 170.0
        p.truck_damage_pct = 10.0
        app.state.refresh()
        select(app.state, "Repair")
        assert p.truck_damage_pct == pytest.approx(8.0)
        assert p.money == pytest.approx(0.0)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_full_game_flow_headless(monkeypatch):
    from freight_fate import __version__
    from freight_fate.app import App
    from freight_fate.states.city import (
        CityMenuState,
        JobBoardState,
        PickupFacilityState,
    )
    from freight_fate.states.driving import ArrivalState, DrivingState, FacilityArrivalState
    from freight_fate.states.main_menu import (
        HomeCityState,
        HomeTerminalState,
        MainMenuState,
        NameEntryState,
    )

    app = App()
    try:
        spoken = []
        monkeypatch.setattr(app.ctx, "say",
                            lambda text, interrupt=True: spoken.append(text))
        app.push_state(MainMenuState(app.ctx))
        menu = app.state
        assert isinstance(menu, MainMenuState)
        assert menu.lines()[0] == "Freight Fate"
        assert any(
            f"Welcome to Freight Fate, version {__version__}." in line
            for line in spoken
        )

        # navigate to "New career" and select it
        while menu.items[menu.index].text != "New career":
            menu.handle_event(key_event(pygame.K_DOWN))
        menu.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, NameEntryState)

        for ch in "Smoke":
            app.state.handle_event(key_event(ord(ch.lower()), ch))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, HomeTerminalState)
        app.state.handle_event(key_event(pygame.K_RETURN))  # default region: Great Lakes
        assert isinstance(app.state, HomeCityState)
        app.state.handle_event(key_event(pygame.K_RETURN))  # default city: Chicago
        assert isinstance(app.state, CityMenuState)
        assert app.ctx.profile is not None
        assert app.ctx.profile.name == "Smoke"
        assert app.ctx.profile.current_city == "Chicago"

        # Open dispatch board and accept a short unlocked job so the bounded
        # smoke run can finish while still driving below enforcement speeds.
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, JobBoardState)
        assert app.state.jobs
        board = app.state
        unlocked = [
            (i, job)
            for i, job in enumerate(board.jobs)
            if not job.locked_reason(app.ctx.profile.career.endorsements, app.ctx.profile.career.level)
        ]
        assert unlocked
        target_index, _job = min(unlocked, key=lambda item: item[1].distance_mi)
        while board.index != target_index:
            board.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, DrivingState)
        assert app.state.phase == "pickup"
        app.state.trip.position_mi = app.state.trip.total_miles
        app.state.trip.finished = True
        app.state.truck.velocity_mps = 0.0
        app.state.update(1 / 60)
        finish_timed_state(app)
        assert isinstance(app.state, PickupFacilityState)
        app.state.handle_event(key_event(pygame.K_RETURN))  # check in at origin
        assert "Load cargo at dock" in app.state.items[app.state.index].text
        app.state.handle_event(key_event(pygame.K_RETURN))  # load at dock
        finish_timed_state(app)
        assert "Depart for destination" in app.state.items[app.state.index].text
        app.state.handle_event(key_event(pygame.K_RETURN))
        from freight_fate.states.city import RouteSelectState

        assert isinstance(app.state, RouteSelectState)
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, DrivingState)
        assert app.state.phase == "delivery"
        departure = next(text for text in reversed(spoken)
                         if "Navigation set for" in text)
        assert "Navigation set for" in departure
        assert "Loaded trip is" in departure
        assert "Departing now" in departure
        assert "Legal HOS plan" not in departure
        assert "Fuel-capable stops" not in departure
        assert "Parking notes" not in departure

        driving = app.state
        # start the engine and drive the whole trip with simulated input
        driving.handle_event(key_event(pygame.K_e))
        assert driving.truck.engine_on
        driving.truck.transmission.automatic = True
        driving.truck.set_air_ready(parking_brake=False)
        driving.trip._hazard_check_mi = 1e9
        driving.trip._inspection_check_mi = 1e9
        driving.trip.traffic_leads = []

        # The dispatch board's shortest unlocked job varies run to run, so a
        # flat frame budget flaked when the only short job was still long
        # enough to outlast it. Size the ceiling to this trip's distance with
        # a conservative crawl-speed floor; the loop still breaks the moment
        # the trip finishes, so normal runs cost the same.
        crawl_mph = 15.0
        max_frames = int(driving.trip.total_miles / crawl_mph * 3600 * 60) + 60 * 60
        for _frame in range(max_frames):
            limit_mph, _reason = driving.trip.speed_limit_at(driving.trip.position_mi)
            target_mph = max(25.0, limit_mph + 5.0)
            if driving.truck.speed_mph > target_mph:
                driving.truck.throttle = 0.0
                driving.truck.brake = 0.5
            else:
                driving.truck.throttle = 0.8
                driving.truck.brake = 0.0
            # trip.update reapplies physics every frame that can randomly slow a
            # long headless drive below the budget: simulated weather can turn to
            # ice and cap traction to a crawl, terrain grade drags on long climbs,
            # fuel burns at time_scale (20x) so the tank can empty mid-route and
            # cut the engine, and this controller's bang-bang braking against a
            # target near the truck's governed speed bleeds the air reservoirs
            # until the spring brakes latch. This is a flow smoke test -- that
            # physics is covered by test_weather_trip, test_vehicle, and the
            # air-brake tests -- so pin full traction, flat ground, a full tank,
            # and charged air for a deterministic drive, matching the
            # hazard/inspection/traffic neutralisation above.
            driving.truck.grip = 1.0
            driving.truck.grade = 0.0
            driving.truck.fuel_gal = driving.truck.specs.fuel_tank_gal
            driving.truck.air_pressure_psi = driving.truck.specs.air_governor_cut_out_psi
            driving.truck.parking_brake = False
            driving.truck.auto_shift()
            driving.truck.update(1 / 60)
            for event in driving.trip.update(1 / 60):
                driving._handle_trip_event(event)
            driving._update_hazard(1 / 60)
            # always brake through hazards so the smoke run never crashes
            if driving._hazard_deadline is not None:
                driving.truck.velocity_mps = 5.0
            if driving.trip.finished:
                driving.truck.velocity_mps = 0.0
                driving._handle_arrival_gate()
                finish_timed_state(app)
                break
        else:  # never hit trip.finished -- a real stall, not just a tight cap
            raise AssertionError(
                f"delivery never finished in {max_frames} frames: "
                f"{driving.trip.position_mi:.1f}/{driving.trip.total_miles:.1f} mi")
        assert isinstance(app.state, FacilityArrivalState)
        app.state.handle_event(key_event(pygame.K_RETURN))
        finish_timed_state(app)
        assert isinstance(app.state, ArrivalState)
        assert app.ctx.profile.career.deliveries == 1
        assert app.ctx.profile.career.total_earnings > 0
        assert app.ctx.profile.current_city == driving.job.destination

        # continue back to the destination terminal hub
        while not app.state.items[app.state.index].text.startswith("Continue to"):
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CityMenuState)
        assert app.state.title == app.ctx.world.home_terminal(driving.job.destination).name

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
    from freight_fate.models.business import LEASED_OWNER_OPERATOR
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
        app.state.handle_event(key_event(pygame.K_RETURN))  # default region
        app.state.handle_event(key_event(pygame.K_RETURN))  # default home terminal
        assert isinstance(app.state, CityMenuState)
        p = app.ctx.profile
        p.business_status = LEASED_OWNER_OPERATOR
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
        from freight_fate.models.profile import Profile

        reloaded = Profile.load(p.path)
        assert reloaded.upgrades.get("engine_tune") == 1
        shop.handle_event(key_event(pygame.K_RETURN))
        assert p.upgrades.get("engine_tune") == 2
        reloaded = Profile.load(p.path)
        assert reloaded.upgrades.get("engine_tune") == 2
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
        reloaded = Profile.load(p.path)
        assert reloaded.truck == "heavy_hauler"
        assert "heavy_hauler" in reloaded.owned_trucks
        assert "currently driving" in trucks.items[trucks.index].text

        # switch back to the standard rig (already owned, no charge)
        money_before = p.money
        while "Standard rig" not in trucks.items[trucks.index].text:
            trucks.handle_event(key_event(pygame.K_DOWN))
        trucks.handle_event(key_event(pygame.K_RETURN))
        assert p.truck == "rig"
        assert p.money == money_before
        reloaded = Profile.load(p.path)
        assert reloaded.truck == "rig"
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_discord_presence_toggle_is_accessible_and_wired(monkeypatch):
    """The Discord presence setting is a spoken, keyboard-driven menu item that
    flips the saved setting and notifies the presence service -- and presence is
    constructed dormant (never started) so it touches nothing until the game
    loop runs."""
    from freight_fate.app import App
    from freight_fate.states.main_menu import SettingsCategoryState

    app = App()
    try:
        spoken: list[str] = []
        monkeypatch.setattr(app.ctx, "say",
                            lambda text, interrupt=True: spoken.append(text))
        toggles: list[bool] = []
        monkeypatch.setattr(app.presence, "set_enabled", toggles.append)

        app.push_state(SettingsCategoryState(app.ctx, "gameplay"))
        menu = app.state
        idx = next(i for i, item in enumerate(menu.items)
                   if item.text.startswith("Discord presence"))
        menu.index = idx
        assert menu.items[idx].help  # spoken help text exists for F1
        before = app.ctx.settings.discord_presence

        menu.handle_event(key_event(pygame.K_RETURN))  # activate to toggle
        assert app.ctx.settings.discord_presence != before
        assert menu.items[idx].text.endswith("off" if before else "on")
        assert spoken and spoken[-1].startswith("Discord presence:")
        assert toggles == [app.ctx.settings.discord_presence]
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_upgrades_are_money_gated():
    from freight_fate.app import App
    from freight_fate.models.business import LEASED_OWNER_OPERATOR
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import UpgradeShopState

    app = App()
    try:
        app.ctx.profile = Profile(name="Broke")
        app.ctx.profile.business_status = LEASED_OWNER_OPERATOR
        app.ctx.profile.money = 10.0
        app.push_state(UpgradeShopState(app.ctx))
        shop = app.state
        shop.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.profile.upgrades == {}
        assert app.ctx.profile.money == 10.0
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_upgrade_f1_help_explains_player_benefits():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import UpgradeShopState

    app = App()
    try:
        app.ctx.profile = Profile(name="Helper")
        app.push_state(UpgradeShopState(app.ctx))
        help_by_label = {}
        for item in app.state.items:
            label = item.text.split(":", 1)[0].split(",", 1)[0].lower()
            help_by_label[label] = item.help.lower()

        assert "more pulling power" in help_by_label["engine tune"]
        assert "heavy freight" in help_by_label["engine tune"]
        assert "burn less fuel at highway speed" in help_by_label["aerodynamic kit"]
        assert "same tank last longer" in help_by_label["aerodynamic kit"]
        assert "fifty gallons" in help_by_label["long-range tank"]
        assert "carry more fuel" in help_by_label["long-range tank"]
        assert "more distance between fuel stops" in help_by_label["long-range tank"]
        assert "emergency stops" in help_by_label["reinforced brakes"]
        assert "downhill control" in help_by_label["reinforced brakes"]
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_pause_and_abandon_returns_to_city():
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState, PickupFacilityState, RouteSelectState
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
        app.state.handle_event(key_event(pygame.K_RETURN))  # default region
        app.state.handle_event(key_event(pygame.K_RETURN))  # default home terminal
        app.state.handle_event(key_event(pygame.K_RETURN))  # job board
        board = app.state
        while board.jobs[board.index].cargo.endorsement:  # skip locked teasers
            board.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))  # accept job
        assert isinstance(app.state, DrivingState)
        assert app.state.phase == "pickup"
        app.state.trip.position_mi = app.state.trip.total_miles
        app.state.trip.finished = True
        app.state.truck.velocity_mps = 0.0
        app.state.update(1 / 60)
        finish_timed_state(app)
        assert isinstance(app.state, PickupFacilityState)
        app.state.handle_event(key_event(pygame.K_RETURN))  # check in at origin
        app.state.handle_event(key_event(pygame.K_RETURN))  # load at dock
        finish_timed_state(app)
        app.state.handle_event(key_event(pygame.K_RETURN))  # depart for destination
        assert isinstance(app.state, RouteSelectState)
        app.state.handle_event(key_event(pygame.K_RETURN))  # accept planned route
        assert isinstance(app.state, DrivingState)
        assert app.state.phase == "delivery"
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
