"""Mid-trip save and resume: snapshot, persistence, and the continue flow."""

import pygame
import pytest


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def finish_timed_state(app):
    from freight_fate.states.base import TimedMessageState

    assert isinstance(app.state, TimedMessageState)
    app.state.update(app.state.remaining + 0.01)


def start_drive(app):
    """New career, accept the assigned dispatch, depart; returns DrivingState."""
    from freight_fate.states.city import PickupFacilityState
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
    return app.state


def drive_some(driving, miles: float = 8.0) -> None:
    """Advance the trip a few miles with simulated full-throttle frames."""
    driving.handle_event(key_event(pygame.K_e))
    driving.truck.transmission.automatic = True
    driving.truck.set_air_ready(parking_brake=False)
    for _ in range(60 * 60 * 5):
        driving.truck.throttle = 0.9
        driving.truck.auto_shift()
        driving.truck.update(1 / 60)
        driving.trip.update(1 / 60)
        if driving.trip.position_mi >= miles:
            break
    assert driving.trip.position_mi >= miles


def test_active_drive_snapshot_restores_idling_engine():
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        driving = start_drive(app)
        driving.truck.start_engine()
        snapshot = driving.snapshot()

        resumed = DrivingState.from_snapshot(app.ctx, snapshot)

        assert resumed is not None
        assert resumed.truck.engine_on
    finally:
        app.shutdown()


def quit_to_menu(app):
    from freight_fate.states.driving import PauseMenuState
    from freight_fate.states.main_menu import MainMenuState

    app.state.handle_event(key_event(pygame.K_ESCAPE))
    assert isinstance(app.state, PauseMenuState)
    pause = app.state
    while pause.items[pause.index].text != "Quit to main menu":
        pause.handle_event(key_event(pygame.K_DOWN))
    pause.handle_event(key_event(pygame.K_RETURN))
    assert isinstance(app.state, MainMenuState)


@pytest.mark.smoke
def test_quit_mid_drive_resumes_from_the_last_stop():
    # Saving is stops-only: quitting mid-drive does not persist the in-progress
    # position, so Continue resumes the leg from where it was last departed
    # (here, the origin terminal at the leg start), not from mid-drive.
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        driving = start_drive(app)
        job, route = driving.job, driving.route
        drive_some(driving)
        assert driving.trip.position_mi > 0.0   # we actually moved up the leg
        quit_to_menu(app)

        p = app.ctx.profile
        assert p.active_trip is not None
        assert p.active_trip["position_mi"] == 0.0   # leg start, not mid-drive

        # Continue from the main menu lands back in the drive at the leg start
        while not app.state.items[app.state.index].text.startswith("Continue latest career"):
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, DrivingState)
        resumed = app.state
        assert resumed.resumed
        assert resumed.job.destination == job.destination
        assert resumed.route.cities == route.cities
        assert resumed.trip.position_mi == 0.0
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
        while not app.state.items[app.state.index].text.startswith("Continue latest career"):
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
    from freight_fate.states.driving import ArrivalState, FacilityArrivalState

    app = App()
    try:
        driving = start_drive(app)
        drive_some(driving)
        quit_to_menu(app)
        assert app.ctx.profile.active_trip is not None
        while not app.state.items[app.state.index].text.startswith("Continue latest career"):
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        resumed = app.state
        resumed.trip.position_mi = resumed.trip.total_miles  # teleport to arrival
        resumed.trip.update(1 / 60)
        resumed.truck.velocity_mps = 0.0
        resumed._handle_arrival_gate()
        finish_timed_state(app)
        assert isinstance(app.state, FacilityArrivalState)
        app.state.handle_event(key_event(pygame.K_RETURN))
        finish_timed_state(app)
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


@pytest.mark.smoke
def test_abandoning_keeps_the_hours_spent_driving():
    """Regression: abandoning a job snapped the world clock back to the
    departure time, while HOS and fatigue kept the accrued hours."""
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState
    from freight_fate.states.driving import PauseMenuState

    app = App()
    try:
        driving = start_drive(app)
        drive_some(driving)
        before = app.ctx.profile.game_hours
        spent = driving.trip.game_minutes / 60.0
        assert spent > 0
        app.state.handle_event(key_event(pygame.K_ESCAPE))
        pause = app.state
        assert isinstance(pause, PauseMenuState)
        while pause.items[pause.index].text != "Abandon job":
            pause.handle_event(key_event(pygame.K_DOWN))
        pause.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CityMenuState)
        assert app.ctx.profile.game_hours == pytest.approx(before + spent)
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_trip_pacing_change_applies_to_the_active_trip():
    """Regression: changing Trip pacing from the pause menu was silently
    ignored until the next delivery."""
    from freight_fate.app import App

    app = App()
    try:
        driving = start_drive(app)
        assert driving.trip.time_scale == app.ctx.settings.time_scale
        app.ctx.settings.time_scale = 40.0
        driving.update(1 / 60)
        assert driving.trip.time_scale == 40.0
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_weather_source_change_applies_to_the_active_trip(monkeypatch):
    """Regression: the pause-menu setting changed the label, but the current
    drive kept using the old weather source until the next job."""
    from freight_fate.app import App

    class Provider:
        def request(self, city, lat, lon):
            pass

        def get(self, city):
            return None

    provider = Provider()
    app = App()
    try:
        driving = start_drive(app)
        assert driving.weather.provider is None
        monkeypatch.setattr(app.ctx, "real_weather_provider", lambda: provider)

        app.ctx.settings.real_weather = True
        driving.update(1 / 60)
        assert driving.weather.provider is provider

        driving.weather.live = True
        app.ctx.settings.real_weather = False
        driving.update(1 / 60)
        assert driving.weather.provider is None
        assert driving.weather.live is False
    finally:
        app.shutdown()


@pytest.mark.smoke
def test_arrival_summary_calls_out_early_delivery_bonus():
    from freight_fate.app import App
    from freight_fate.states.driving import ArrivalState

    app = App()
    try:
        driving = start_drive(app)
        driving.trip.game_minutes = driving.job.deadline_game_h * 30.0
        arrival = ArrivalState(app.ctx, driving)
        assert any("Early delivery bonus" in part
                   for part in arrival.summary_parts)
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


def test_snapshot_roundtrip_preserves_air_brake_state():
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        driving = start_drive(app)
        driving.truck.primary_air_psi = 88.0
        driving.truck.secondary_air_psi = 92.0
        driving.truck.trailer_air_psi = 95.0
        driving.truck.parking_brake = False
        snap = driving.snapshot()

        resumed = DrivingState.from_snapshot(app.ctx, snap)

        assert resumed is not None
        assert resumed.truck.air_pressure_psi == pytest.approx(88.0)
        assert resumed.truck.primary_air_psi == pytest.approx(88.0)
        assert resumed.truck.secondary_air_psi == pytest.approx(92.0)
        assert resumed.truck.trailer_air_psi == pytest.approx(95.0)
        assert not resumed.truck.parking_brake
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


def test_old_map_snapshot_still_resumes():
    """A mid-trip save written against the 21-city 1.2.x map must resume.

    The route below only uses legs from the original map; they are required
    to survive every map expansion (see ORIGINAL_ADJACENT_PAIRS in
    test_world.py).
    """
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState
    from freight_fate.states.main_menu import enter_world

    old_route = ["Chicago", "St. Louis", "Kansas City", "Denver"]
    app = App()
    try:
        p = Profile(name="Old Save")
        p.active_trip = {
            "job": {"cargo": "general", "weight_tons": 14.0,
                    "origin": "Chicago", "origin_location": "Cicero Rail Hub",
                    "destination": "Denver", "distance_mi": 1150.0,
                    "pay": 2800.0, "deadline_game_h": 31.0, "market_mult": 1.0},
            "route_cities": old_route,
            "trip_seed": 1234, "position_mi": 412.0, "game_minutes": 540.0,
            "start_damage": 3.0, "speeding_strikes": 1,
        }
        app.ctx.profile = p
        enter_world(app.ctx)
        assert isinstance(app.state, DrivingState)
        assert app.state.resumed
        assert app.state.route.cities == old_route
        assert app.state.trip.position_mi == 412.0
        assert app.state.job.destination == "Denver"
        assert app.state.truck.air_ready
        assert app.state.truck.parking_brake
    finally:
        app.shutdown()


def test_old_active_trip_gets_fair_deadline_floor():
    from freight_fate.app import App
    from freight_fate.models.jobs import fair_active_deadline, job_from_payload
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState
    from freight_fate.states.main_menu import enter_world

    app = App()
    try:
        route_cities = ["San Antonio", "Dallas"]
        job_payload = {
            "cargo": "general",
            "weight_tons": 14.0,
            "origin": "San Antonio",
            "origin_location": "San Antonio freight market",
            "destination": "Dallas",
            "distance_mi": 275.0,
            "pay": 1200.0,
            "deadline_game_h": 3.0,
            "market_mult": 1.0,
        }
        p = Profile(name="Deadline Floor")
        p.active_trip = {
            "job": job_payload,
            "route_cities": route_cities,
            "trip_seed": 1234,
            "position_mi": 50.0,
            "game_minutes": 180.0,
            "start_damage": 0.0,
            "speeding_strikes": 0,
        }
        app.ctx.profile = p
        route = app.ctx.world.route_from_cities(route_cities)
        expected = fair_active_deadline(
            job_from_payload(job_payload),
            route,
            hours_used=3.0,
            position_mi=50.0,
            world=app.ctx.world,
        )

        enter_world(app.ctx)

        assert isinstance(app.state, DrivingState)
        assert app.state.job.deadline_game_h == expected
        assert app.state.job.deadline_game_h > job_payload["deadline_game_h"]
    finally:
        app.shutdown()


def test_bare_city_job_snapshot_gets_facility_fallback():
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState
    from freight_fate.states.main_menu import enter_world

    app = App()
    try:
        p = Profile(name="Bare City Save")
        p.active_trip = {
            "job": {"cargo": "general", "weight_tons": 14.0,
                    "origin": "Chicago", "destination": "St. Louis",
                    "distance_mi": 298.0, "pay": 1200.0,
                    "deadline_game_h": 9.0, "market_mult": 1.0},
            "route_cities": ["Chicago", "St. Louis"],
            "trip_seed": 1234, "position_mi": 20.0, "game_minutes": 30.0,
            "start_damage": 0.0, "speeding_strikes": 0,
        }
        app.ctx.profile = p
        enter_world(app.ctx)

        assert isinstance(app.state, DrivingState)
        assert app.state.job.origin_facility_text() == "the Chicago metro freight market"
        assert app.state.job.destination_facility_text() == (
            "the St. Louis metro freight market")
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
