"""Drivable pickup, loading, and transition into loaded delivery."""

import pygame


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def accept_pickup_drive(app):
    from freight_fate.states.driving import DrivingState
    from freight_fate.states.main_menu import MainMenuState

    app.push_state(MainMenuState(app.ctx))
    while app.state.items[app.state.index].text != "New career":
        app.state.handle_event(key_event(pygame.K_DOWN))
    app.state.handle_event(key_event(pygame.K_RETURN))
    app.state.handle_event(key_event(pygame.K_RETURN))  # default name
    app.state.handle_event(key_event(pygame.K_RETURN))  # default home terminal
    app.state.handle_event(key_event(pygame.K_RETURN))  # job board
    board = app.state
    while board.jobs[board.index].cargo.endorsement:
        board.handle_event(key_event(pygame.K_DOWN))
    board.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, DrivingState)
    assert app.state.phase == "pickup"
    return app.state


def arrive_at_pickup(app, speed_mps: float = 0.0):
    from freight_fate.states.city import PickupFacilityState

    driving = app.state
    driving.trip.position_mi = driving.trip.total_miles
    driving.trip.finished = True
    driving.truck.velocity_mps = speed_mps
    driving.update(1 / 60)
    if speed_mps <= 0.45:
        assert isinstance(app.state, PickupFacilityState)
        return app.state
    return driving


def test_accepting_job_starts_drivable_pickup_leg():
    from freight_fate.app import App
    from freight_fate.states.city import PickupFacilityState
    from freight_fate.states.driving import DrivingState

    app = App()
    spoken = []
    app.ctx.say = lambda text, interrupt=True: spoken.append(text)
    try:
        pickup = accept_pickup_drive(app)

        assert isinstance(app.state, DrivingState)
        assert not isinstance(app.state, PickupFacilityState)
        assert app.ctx.profile.active_trip["kind"] == "pickup_drive"
        assert app.ctx.profile.active_trip["job"]["origin_facility_id"]
        assert app.ctx.profile.active_trip["job"]["destination_facility_id"]
        assert pickup.route.miles > 2.0
        assert pickup.trip.total_miles == pickup.route.miles
        assert pickup.trip.remaining_miles == pickup.route.miles
        assert "Deadheading to pickup" in pickup.lines()[0]
        dispatch_messages = [
            text for text in spoken
            if "Dispatch accepted from Chicago Company Yard" in text
        ]
        assert dispatch_messages
        assert "Deadhead" in dispatch_messages[-1]
    finally:
        app.shutdown()


def test_facility_approach_route_has_real_mileage_and_label(world):
    jobs = world.cities["Chicago"].locations
    route = world.facility_approach_route("Chicago", jobs[0].name)

    assert route.miles > 2.0
    assert route.cities == ["Chicago", "Chicago"]
    assert route.highways
    assert "access road" in route.highways[0]
    assert route.describe().startswith(f"{route.miles:.0f} miles via")


def test_pickup_facility_waits_for_full_stop(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import PickupFacilityState
    from freight_fate.states.driving import DrivingState

    app = App()
    events = []
    monkeypatch.setattr(app.ctx, "say_event",
                        lambda text, interrupt=True: events.append(text))
    try:
        driving = accept_pickup_drive(app)

        arrive_at_pickup(app, speed_mps=26.8)
        assert isinstance(app.state, DrivingState)
        assert "Pickup facility ahead" in events[-1]
        assert "full stop to check in and load" in events[-1]

        driving.truck.velocity_mps = 1.1
        driving.update(1 / 60)
        assert isinstance(app.state, DrivingState)
        assert "pickup facility menu opens when stopped" in events[-1]

        driving.truck.velocity_mps = 0.0
        driving.update(1 / 60)
        assert isinstance(app.state, PickupFacilityState)
        assert app.state.items[app.state.index].text == "Check in at shipping office"
    finally:
        app.shutdown()


def test_save_resume_during_pickup_drive():
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState, PauseMenuState

    app = App()
    try:
        driving = accept_pickup_drive(app)
        driving.trip.restore(1.5, 12.0)

        driving.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, PauseMenuState)
        pause = app.state
        while pause.items[pause.index].text != "Save and quit to main menu":
            pause.handle_event(key_event(pygame.K_DOWN))
        pause.handle_event(key_event(pygame.K_RETURN))

        while not app.state.items[app.state.index].text.startswith("Continue latest career"):
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, DrivingState)
        assert app.state.resumed
        assert app.state.phase == "pickup"
        assert app.state.trip.position_mi == 1.5
        assert app.state.trip.game_minutes == 12.0
    finally:
        app.shutdown()


def test_pickup_arrival_state_and_loaded_planning_resume():
    from freight_fate.app import App
    from freight_fate.states.city import PickupFacilityState

    app = App()
    try:
        accept_pickup_drive(app)
        pickup = arrive_at_pickup(app)
        pickup.handle_event(key_event(pygame.K_RETURN))  # check in

        while pickup.items[pickup.index].text != "Save and quit to main menu":
            pickup.handle_event(key_event(pygame.K_DOWN))
        pickup.handle_event(key_event(pygame.K_RETURN))

        while not app.state.items[app.state.index].text.startswith("Continue latest career"):
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, PickupFacilityState)
        assert app.state.checked_in
        assert not app.state.loaded

        app.state.handle_event(key_event(pygame.K_RETURN))  # load
        assert app.state.loaded
        assert app.ctx.profile.active_trip["loaded"] is True

        while app.state.items[app.state.index].text != "Save and quit to main menu":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        while not app.state.items[app.state.index].text.startswith("Continue latest career"):
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, PickupFacilityState)
        assert app.state.loaded
        assert app.state.items[app.state.index].text == "Depart for destination"

        app.state.handle_event(key_event(pygame.K_RETURN))
        from freight_fate.states.driving import DrivingState

        assert isinstance(app.state, DrivingState)
    finally:
        app.shutdown()


def test_job_board_help_names_drivable_pickup_before_route_planning():
    from freight_fate.states.city import JobBoardState

    assert "local deadhead pickup drive from your terminal" in JobBoardState.intro_help
    assert "route planning" not in JobBoardState.intro_help
