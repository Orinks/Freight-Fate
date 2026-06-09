"""Mid-trip save and resume: snapshot, persistence, and the continue flow."""

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
    app.state.handle_event(key_event(pygame.K_RETURN))  # job board
    board = app.state
    while board.jobs[board.index].cargo.endorsement:  # skip locked teasers
        board.handle_event(key_event(pygame.K_DOWN))
    app.state.handle_event(key_event(pygame.K_RETURN))  # accept job
    app.state.handle_event(key_event(pygame.K_RETURN))  # pick route
    assert isinstance(app.state, DrivingState)
    return app.state


def drive_some(driving, miles: float = 8.0) -> None:
    """Advance the trip a few miles with simulated full-throttle frames."""
    driving.handle_event(key_event(pygame.K_e))
    driving.truck.transmission.automatic = True
    for _ in range(60 * 60 * 5):
        driving.truck.throttle = 0.9
        driving.truck.auto_shift()
        driving.truck.update(1 / 60)
        driving.trip.update(1 / 60)
        if driving.trip.position_mi >= miles:
            break
    assert driving.trip.position_mi >= miles


def quit_to_menu(app):
    from freight_fate.states.driving import PauseMenuState
    from freight_fate.states.main_menu import MainMenuState

    app.state.handle_event(key_event(pygame.K_ESCAPE))
    assert isinstance(app.state, PauseMenuState)
    pause = app.state
    while pause.items[pause.index].text != "Save and quit to main menu":
        pause.handle_event(key_event(pygame.K_DOWN))
    pause.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, MainMenuState)


@pytest.mark.smoke
def test_save_and_quit_then_continue_resumes_the_trip():
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        driving = start_drive(app)
        job, route = driving.job, driving.route
        strikes = driving.speeding_strikes = 2
        drive_some(driving)
        position = driving.trip.position_mi
        minutes = driving.trip.game_minutes
        zones = driving.trip.zones
        quit_to_menu(app)

        p = app.ctx.profile
        assert p.active_trip is not None
        assert p.active_trip["position_mi"] == position

        # Continue from the main menu must land back in the drive
        while app.state.items[app.state.index].text != "Continue":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, DrivingState)
        resumed = app.state
        assert resumed.resumed
        assert resumed.job.destination == job.destination
        assert resumed.job.pay == job.pay
        assert resumed.job.deadline_game_h == job.deadline_game_h
        assert resumed.route.cities == route.cities
        assert abs(resumed.trip.position_mi - position) < 1e-6
        assert abs(resumed.trip.game_minutes - minutes) < 1e-6
        assert resumed.speeding_strikes == strikes
        # same trip seed -> identical construction/traffic zone layout
        assert resumed.trip.zones == zones
        # the truck resumes parked
        assert not resumed.truck.engine_on
        assert resumed.truck.velocity_mps == 0.0
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_resumed_trip_does_not_replay_passed_announcements():
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEventKind

    app = App()
    try:
        driving = start_drive(app)
        drive_some(driving)
        quit_to_menu(app)
        while app.state.items[app.state.index].text != "Continue":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        resumed = app.state
        # the first idle frame must not re-announce stops/cities behind us
        events = resumed.trip.update(1 / 60)
        replayed = [e for e in events if e.kind in
                    (TripEventKind.STOP_AHEAD, TripEventKind.CITY_REACHED,
                     TripEventKind.ZONE_ENTER)]
        assert not replayed
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_delivery_clears_the_saved_trip():
    from freight_fate.app import App
    from freight_fate.states.driving import ArrivalState

    app = App()
    try:
        driving = start_drive(app)
        drive_some(driving)
        quit_to_menu(app)
        assert app.ctx.profile.active_trip is not None
        while app.state.items[app.state.index].text != "Continue":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        resumed = app.state
        resumed.trip.position_mi = resumed.trip.total_miles  # teleport to arrival
        resumed.trip.update(1 / 60)
        resumed._arrive()
        assert isinstance(app.state, ArrivalState)
        assert app.ctx.profile.active_trip is None
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_abandoning_clears_the_saved_trip():
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState
    from freight_fate.states.driving import PauseMenuState

    app = App()
    try:
        driving = start_drive(app)
        drive_some(driving)
        app.ctx.profile.active_trip = driving.snapshot()  # as if resumed earlier
        app.state.handle_event(key_event(pygame.K_ESCAPE))
        assert isinstance(app.state, PauseMenuState)
        pause = app.state
        while pause.items[pause.index].text != "Abandon job":
            pause.handle_event(key_event(pygame.K_DOWN))
        pause.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CityMenuState)
        assert app.ctx.profile.active_trip is None
    finally:
        app.shutdown()


def test_snapshot_survives_profile_roundtrip():
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        drive_some(driving)
        quit_to_menu(app)
        p = app.ctx.profile
        from freight_fate.models.profile import Profile

        loaded = Profile.load(p.path)
        assert loaded.active_trip == p.active_trip
    finally:
        app.shutdown()


def test_corrupt_snapshot_falls_back_to_city():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import CityMenuState
    from freight_fate.states.main_menu import enter_world

    app = App()
    try:
        app.ctx.profile = Profile(name="Corrupt")
        app.ctx.profile.active_trip = {"job": {"cargo": "no_such_cargo"}}
        enter_world(app.ctx)
        assert isinstance(app.state, CityMenuState)
        assert app.ctx.profile.active_trip is None
    finally:
        app.shutdown()


def test_route_from_cities_roundtrip(world):
    route = world.shortest_route("Chicago", "Denver")
    rebuilt = world.route_from_cities(route.cities)
    assert rebuilt is not None
    assert rebuilt.cities == route.cities
    assert rebuilt.legs == route.legs
    assert world.route_from_cities(["Chicago"]) is None
    assert world.route_from_cities(["Chicago", "Not A City"]) is None
