"""Highway exits and cruise control, end to end through the driving state."""

import pygame
import pytest


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def start_drive(app):
    """New career, accept an unlocked job, pick a route; returns DrivingState."""
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
    while board.jobs[board.index].cargo.endorsement:  # skip locked teasers
        board.handle_event(key_event(pygame.K_DOWN))
    app.state.handle_event(key_event(pygame.K_RETURN))  # accept job
    app.state.handle_event(key_event(pygame.K_RETURN))  # pick route
    assert isinstance(app.state, DrivingState)
    return app.state


def quiet_trip(driving):
    """Push random hazards and inspections beyond this test's horizon."""
    driving.trip._hazard_check_mi = 1e9
    driving.trip._inspection_check_mi = 1e9


# -- highway exits -------------------------------------------------------------


@pytest.mark.smoke
def test_exit_flow_reaches_the_rest_stop_menu():
    from freight_fate.app import App
    from freight_fate.states.driving import ParkingFullState, RestStopState

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 2.0
        driving.truck.velocity_mps = 15.0   # ~34 mph: slow enough for the ramp
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is stop

        driving.trip.position_mi = stop.at_mi   # reach the exit point
        driving.update(1 / 60)
        assert driving._ramp_mi is not None     # on the ramp
        assert driving._exit_stop is None

        driving._ramp_mi = 0.0                  # end of the ramp...
        driving.truck.velocity_mps = 0.0        # ...braked to a stop
        driving.update(1 / 60)
        assert isinstance(app.state, (RestStopState, ParkingFullState))
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_exit_missed_when_too_fast():
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 1.0
        driving.truck.velocity_mps = 29.0   # ~65 mph: way too fast for the ramp
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is stop
        driving.trip.position_mi = stop.at_mi
        driving.update(1 / 60)
        assert driving._ramp_mi is None         # blew past it
        assert driving._exit_stop is None
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_exit_key_is_a_toggle_and_needs_an_exit_nearby():
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        # far from any stop: X does not arm
        driving.trip.position_mi = 0.0
        if driving.trip.stops[0].at_mi > 6.0:
            driving.handle_event(key_event(pygame.K_x))
            assert driving._exit_stop is None
        # in range it arms; pressing X again cancels
        stop = driving.trip.stops[0]
        driving.trip.position_mi = stop.at_mi - 2.0
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is stop
        driving.handle_event(key_event(pygame.K_x))
        assert driving._exit_stop is None
    finally:
        app.shutdown()


# -- cruise control -------------------------------------------------------------


@pytest.mark.smoke
def test_cruise_control_holds_the_set_speed():
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        t = driving.truck
        driving.handle_event(key_event(pygame.K_e))   # engine on
        t.transmission.gear = 10
        t.velocity_mps = 26.8                          # ~60 mph
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph == pytest.approx(60.0, abs=1.0)
        for _ in range(60 * 15):                       # 15 seconds, no keys held
            driving.update(1 / 60)
        assert driving._cruise_mph is not None
        assert abs(t.speed_mph - 60.0) < 5.0
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_cruise_control_requires_road_speed_and_cancels_on_hazard():
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        # parked: refuses to engage
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is None
        # engaged at speed, a hazard hands control back to the driver
        driving.handle_event(key_event(pygame.K_e))
        driving.truck.transmission.gear = 10
        driving.truck.velocity_mps = 26.8
        driving.handle_event(key_event(pygame.K_k))
        assert driving._cruise_mph is not None
        hazard = TripEvent(TripEventKind.HAZARD, "Brake now!", {"deadline_s": 4.0})
        driving._handle_trip_event(hazard)
        assert driving._cruise_mph is None
    finally:
        app.shutdown()
