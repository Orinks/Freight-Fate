"""World data and route graph tests."""


def test_world_loads(world):
    assert len(world.cities) >= 18
    assert len(world.legs) >= 24


def test_every_city_reachable_from_everywhere(world):
    names = world.city_names()
    start = names[0]
    for city in names[1:]:
        route = world.shortest_route(start, city)
        assert route is not None, f"{city} unreachable from {start}"
        assert route.cities[0] == start
        assert route.cities[-1] == city


def test_route_legs_chain_correctly(world):
    route = world.shortest_route("New York", "Los Angeles")
    assert route is not None
    for i, leg in enumerate(route.legs):
        assert {route.cities[i], route.cities[i + 1]} == {leg.a, leg.b}


def test_route_options_are_distinct_and_sorted(world):
    options = world.route_options("New York", "Los Angeles", count=3)
    assert len(options) >= 2
    paths = {tuple(r.cities) for r in options}
    assert len(paths) == len(options)
    miles = [r.miles for r in options]
    assert miles == sorted(miles)


def test_shortest_route_is_actually_shortest(world):
    direct = world.shortest_route("New York", "Boston")
    assert direct is not None
    assert direct.miles == 215
    assert len(direct.legs) == 1


def test_unknown_city_raises(world):
    import pytest

    with pytest.raises(KeyError):
        world.shortest_route("New York", "Atlantis")


def test_every_city_has_locations_with_known_cargo(world):
    from freight_fate.models.jobs import CARGO_CATALOG

    for city in world.cities.values():
        assert city.locations, f"{city.name} has no freight locations"
        for loc in city.locations:
            for cargo in loc.cargo:
                assert cargo in CARGO_CATALOG, f"unknown cargo {cargo} at {loc.name}"


def test_route_describe_mentions_miles_and_highway(world):
    route = world.shortest_route("Chicago", "Indianapolis")
    text = route.describe()
    assert "184" in text
    assert "I-65" in text
