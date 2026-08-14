from speech_capture import speech_stub


def test_city_services_are_source_backed(world):
    services = world.city_services("Indianapolis")

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


def test_city_services_fallback_when_no_source_data(world):
    services = world.city_services("Erie")

    assert [service.key for service in services] == [
        "freight_market",
        "garage",
        "truck_dealer",
    ]
    assert not services[0].fallback
    assert not services[1].fallback
    assert services[2].fallback
    assert services[2].source_type == "fallback"
    assert services[2].fallback_reason
    assert all(service.source_note for service in services)


def test_city_service_data_covers_every_supported_city(world):
    raw_markers = ("osm_id", "amenity=", "highway=", "operator=", "node/", "way/")

    source_backed = 0
    fallback = 0
    for city in world.city_names():
        services = world.city_services(city)
        assert [service.key for service in services] == [
            "freight_market",
            "garage",
            "truck_dealer",
        ]
        for service in services:
            assert service.spoken_name
            assert not any(marker in service.spoken_name.lower() for marker in raw_markers)
            assert service.source_note
            if service.fallback:
                fallback += 1
                assert service.source_type == "fallback"
                assert service.fallback_reason
            else:
                source_backed += 1
                assert service.source_type == "osm"
                assert service.lat
                assert service.lon
                assert service.approach_miles > 0
                assert service.approach_road

    # The sweep now covers every city on the map. Each city's three services
    # are source-backed where a real POI sits within the city-errand cap, and
    # fall back to a synthesized errand where none does.
    assert source_backed == 1174
    assert fallback == len(world.city_names()) * 3 - source_backed


def test_city_service_snapshot_drops_to_terminal(monkeypatch):
    """A save from before local city-service drives were retired can still
    carry one mid-trip. There is no route or phase left to resume it with, so
    loading it should park the driver at the terminal instead of crashing."""
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.city import CityMenuState
    from freight_fate.states.main_menu import enter_world

    app = App()
    try:
        spoken = []
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        app.ctx.profile = Profile(name="Retired Drive", current_city="Chicago")
        app.ctx.profile.active_trip = {"kind": "city_service_drive", "job": {}, "trip_seed": 1}
        app.ctx.profile.money = 4_321.0
        app.ctx.profile.game_hours = 88.0

        enter_world(app.ctx)

        assert isinstance(app.state, CityMenuState)
        assert app.ctx.profile.active_trip is None
        assert app.ctx.profile.money == 4_321.0
        assert app.ctx.profile.game_hours == 88.0
        assert (
            "Local service drives were retired in this update; you are parked at the terminal."
        ) in spoken

        # The clear must reach disk, not just the in-memory profile, so the
        # notice does not replay on every future load of this save.
        reloaded = Profile.load(app.ctx.profile.path)
        assert reloaded.active_trip is None
    finally:
        app.shutdown()
