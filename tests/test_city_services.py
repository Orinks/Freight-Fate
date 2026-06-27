import pygame


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def test_city_services_are_source_backed(world):
    services = world.city_services("Chicago")

    assert [service.key for service in services] == [
        "freight_market",
        "garage",
        "truck_dealer",
    ]
    assert all(service.source_note for service in services)
    assert all(service.spoken_name for service in services)
    for service in services:
        assert not service.fallback
        assert service.source_type == "osm"
        assert service.lat
        assert service.lon
        assert "OpenStreetMap" in service.source_note
        assert "node/" not in service.spoken_name.lower()
        assert "way/" not in service.spoken_name.lower()
        route = world.city_service_route("Chicago", service.key)
        assert route.miles == service.approach_miles
        assert route.highways[0] == service.approach_road


def test_city_services_fallback_when_no_source_data(world):
    services = world.city_services("Nashville")

    assert [service.key for service in services] == [
        "freight_market",
        "garage",
        "truck_dealer",
    ]
    assert all(service.fallback for service in services)
    assert all(service.source_type == "fallback" for service in services)
    assert all(service.source_note for service in services)


def test_city_service_drive_requires_enter_before_opening(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import CityMenuState, CityServiceSelectState, GarageState
    from freight_fate.states.driving import (
        DRIVE_PHASE_CITY_SERVICE,
        DrivingState,
        DrivingStatusScreenState,
    )

    monkeypatch.setenv("FREIGHT_FATE_AUDIO_BACKEND", "pygame")
    app = App()
    try:
        spoken = []
        monkeypatch.setattr(app.ctx.audio, "play", lambda *args, **kwargs: None)
        monkeypatch.setattr(app.ctx, "play_music_sequence", lambda *args, **kwargs: None)
        monkeypatch.setattr(app.ctx.audio, "set_ambient", lambda *args, **kwargs: None)
        monkeypatch.setattr(app.ctx, "say",
                            lambda text, interrupt=True: spoken.append(text))
        monkeypatch.setattr(app.ctx, "say_event",
                            lambda text, interrupt=True: spoken.append(text))
        app.ctx.profile = Profile(name="Services", current_city="Chicago")
        app.push_state(CityMenuState(app.ctx))

        while app.state.items[app.state.index].text != "Drive to city services":
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, CityServiceSelectState)

        garage_name = app.ctx.world.city_service("Chicago", "garage").name
        while garage_name not in app.state.items[app.state.index].text:
            app.state.handle_event(key_event(pygame.K_DOWN))
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, DrivingState)
        assert app.state.phase == DRIVE_PHASE_CITY_SERVICE
        driver_status = DrivingStatusScreenState(app.ctx, app.state, "driver")
        status_lines = driver_status._driver_lines()
        assert "Load: no cargo, local city service drive" in status_lines
        assert any(line.startswith("Time: ") and "hours used" in line for line in status_lines)
        assert not any("tons of general freight" in line for line in status_lines)

        app.state.trip.position_mi = app.state.trip.total_miles
        app.state.trip.finished = True
        app.state.truck.velocity_mps = 0.0
        app.state.update(1 / 60)
        assert isinstance(app.state, DrivingState)
        assert app.ctx.profile.active_trip["kind"] == "city_service_drive"
        assert app.ctx.profile.active_trip["position_mi"] == app.state.trip.total_miles
        assert any("Press Enter to go inside" in text for text in spoken)

        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, GarageState)
        assert app.ctx.profile.active_trip is None
    finally:
        app.shutdown()
