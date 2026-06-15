"""Pickup, loading, and transition into loaded delivery."""

import pygame


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def start_pickup(app):
    from freight_fate.states.city import JobBoardState, PickupFacilityState
    from freight_fate.states.main_menu import MainMenuState

    app.push_state(MainMenuState(app.ctx))
    while app.state.items[app.state.index].text != "New career":
        app.state.handle_event(key_event(pygame.K_DOWN))
    app.state.handle_event(key_event(pygame.K_RETURN))
    app.state.handle_event(key_event(pygame.K_RETURN))  # default name
    app.state.handle_event(key_event(pygame.K_RETURN))  # default home terminal
    app.state.handle_event(key_event(pygame.K_RETURN))  # job board
    assert isinstance(app.state, JobBoardState)
    board = app.state
    while board.jobs[board.index].cargo.endorsement:
        board.handle_event(key_event(pygame.K_DOWN))
    board.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, PickupFacilityState)
    return app.state


def test_accepting_job_creates_pickup_objective_before_route_planning():
    from freight_fate.app import App
    from freight_fate.states.city import PickupFacilityState, RouteSelectState
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        pickup = start_pickup(app)

        assert isinstance(app.state, PickupFacilityState)
        assert not isinstance(app.state, RouteSelectState)
        assert not isinstance(app.state, DrivingState)
        assert app.ctx.profile.active_trip["kind"] == "pickup"
        assert app.ctx.profile.active_trip["checked_in"] is False
        assert pickup.items[pickup.index].text == "Check in at shipping office"
        assert any("Check-in required" in line for line in pickup.lines())
    finally:
        app.shutdown()


def test_loading_requires_check_in_and_full_stop(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import RouteSelectState

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: spoken.append(text))
    try:
        pickup = start_pickup(app)

        pickup.truck.velocity_mps = 1.1
        pickup.handle_event(key_event(pygame.K_RETURN))  # check in
        assert pickup.checked_in
        assert pickup.items[pickup.index].text == "Load cargo at dock"

        pickup.handle_event(key_event(pygame.K_RETURN))
        assert not pickup.loaded
        assert "full stop before loading" in spoken[-1]

        pickup.truck.velocity_mps = 0.0
        pickup.handle_event(key_event(pygame.K_RETURN))
        assert pickup.loaded
        assert pickup.items[pickup.index].text == "Plan destination route"

        pickup.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, RouteSelectState)
    finally:
        app.shutdown()


def test_pickup_save_and_resume_preserves_loading_state():
    from freight_fate.app import App
    from freight_fate.states.city import PickupFacilityState

    app = App()
    try:
        pickup = start_pickup(app)
        pickup.handle_event(key_event(pygame.K_RETURN))  # check in
        pickup.handle_event(key_event(pygame.K_RETURN))  # load
        assert pickup.loaded

        while pickup.items[pickup.index].text != "Save and quit to main menu":
            pickup.handle_event(key_event(pygame.K_DOWN))
        pickup.handle_event(key_event(pygame.K_RETURN))

        while not app.state.items[app.state.index].text.startswith("Continue latest career"):
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))

        assert isinstance(app.state, PickupFacilityState)
        assert app.state.checked_in
        assert app.state.loaded
        assert app.state.items[app.state.index].text == "Plan destination route"
    finally:
        app.shutdown()


def test_job_board_help_names_pickup_before_route_planning():
    from freight_fate.states.city import JobBoardState

    assert "pickup objective" in JobBoardState.intro_help
    assert "route planning" not in JobBoardState.intro_help
