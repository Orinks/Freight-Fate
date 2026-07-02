"""Shared helpers for driving-state feature tests."""

import pygame


class HeldKeys:
    def __init__(self, *pressed: int) -> None:
        self.pressed = set(pressed)

    def __getitem__(self, key: int) -> bool:
        return key in self.pressed


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def finish_timed_state(app):
    while getattr(app.state, "remaining", 0) > 0:
        app.state.update(1 / 60)


def release_air_brakes(driving):
    driving.truck.set_air_ready(parking_brake=False)


def set_trip_traffic(driving, vehicles):
    driving.trip.traffic_manager.vehicles = list(vehicles)


def start_drive(app):
    """New career, accept the assigned dispatch, depart; returns DrivingState.

    New company hires run the load and route dispatch assigns, so the board
    offers a single assignment and departure skips the route menu.
    """
    from freight_fate.states.city import CityMenuState, PickupFacilityState
    from freight_fate.states.driving import DrivingState
    from freight_fate.states.main_menu import MainMenuState

    app.push_state(MainMenuState(app.ctx))
    while app.state.items[app.state.index].text != "New career":
        app.state.handle_event(key_event(pygame.K_DOWN))
    app.state.handle_event(key_event(pygame.K_RETURN))
    app.state.handle_event(key_event(pygame.K_RETURN))  # default name
    app.state.handle_event(key_event(pygame.K_RETURN))  # default career start
    app.state.handle_event(key_event(pygame.K_RETURN))  # default region
    app.state.handle_event(key_event(pygame.K_RETURN))  # default home terminal
    app.state.handle_event(key_event(pygame.K_RETURN))  # job board
    if isinstance(app.state, CityMenuState):
        app.state.handle_event(key_event(pygame.K_RETURN))  # dispatch board
    assert app.state.assigned_mode
    app.state.handle_event(key_event(pygame.K_RETURN))  # accept assigned job
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
    app.state.handle_event(key_event(pygame.K_RETURN))  # depart on assigned route
    assert isinstance(app.state, DrivingState)
    assert app.state.phase == "delivery"
    release_air_brakes(app.state)
    return app.state


def quiet_trip(driving):
    """Push random hazards and inspections beyond this test's horizon."""
    from freight_fate.sim.weather import WeatherKind

    driving.trip._hazard_check_mi = 1e9
    driving.trip._inspection_check_mi = 1e9
    driving.trip.traffic_manager.vehicles = []
    driving.weather.current = WeatherKind.CLEAR


def open_limits(driving):
    """Lift posted speed limits out of the way so a test can isolate cruise
    hold/follow behavior from the predictive-ACC limit cap."""
    driving.trip.speed_limit_at = lambda mile: (200.0, None)


def take_destination_exit(driving):
    """Move onto the delivery ramp and stop at the destination gate."""
    destination = driving._destination_exit_stop()
    assert destination is not None
    driving._exit_stop = destination
    driving._exit_lane_alignment = 1.0
    driving.trip.position_mi = destination.at_mi
    driving.truck.velocity_mps = 0.0
    driving._update_exit(0.0)
    driving._update_exit(driving._ramp_mi)
    finish_timed_state(driving.ctx._app)


def mark_destination_exit_taken(driving):
    driving._destination_exit_taken = True
    driving.trip.finished = True
    driving.trip.position_mi = driving.trip.total_miles


def open_status_screen(app, label):
    """From the open driving status picker, open a named screen submenu."""
    from freight_fate.states.driving import DrivingStatusScreenState

    picker = app.state
    while picker.items[picker.index].text != label:
        picker.handle_event(key_event(pygame.K_DOWN))
    picker.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, DrivingStatusScreenState)
    return app.state


def open_driver_apps(app):
    """From the open driving status picker, open the driver tablet menu."""
    from freight_fate.states.driving import DriverAppsState

    picker = app.state
    while picker.items[picker.index].text != "Driver apps":
        picker.handle_event(key_event(pygame.K_DOWN))
    picker.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, DriverAppsState)
    return app.state


def open_driver_app(app, label):
    """From the driver tablet menu, open one app."""
    from freight_fate.states.driving import DriverAppScreenState

    apps = app.state
    while apps.items[apps.index].text != label:
        apps.handle_event(key_event(pygame.K_DOWN))
    apps.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, DriverAppScreenState)
    return app.state
