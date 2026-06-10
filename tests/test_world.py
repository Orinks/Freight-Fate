"""World data and route graph tests."""

# Every direct connection that existed in the 21-city 1.2.x map. Old
# mid-trip snapshots store these as consecutive route_cities pairs, so each
# one must remain a direct leg forever (or ship with a save migration).
ORIGINAL_ADJACENT_PAIRS = [
    ("New York", "Boston"), ("New York", "Philadelphia"),
    ("Philadelphia", "Pittsburgh"), ("Pittsburgh", "Cleveland"),
    ("Cleveland", "Chicago"), ("Chicago", "Indianapolis"),
    ("Indianapolis", "Nashville"), ("Nashville", "Atlanta"),
    ("Indianapolis", "St. Louis"), ("Chicago", "St. Louis"),
    ("St. Louis", "Nashville"), ("St. Louis", "Kansas City"),
    ("Kansas City", "Denver"), ("Denver", "Salt Lake City"),
    ("Denver", "Albuquerque"), ("Albuquerque", "Phoenix"),
    ("Phoenix", "Los Angeles"), ("Salt Lake City", "Las Vegas"),
    ("Las Vegas", "Los Angeles"), ("Dallas", "Albuquerque"),
    ("Dallas", "St. Louis"), ("Atlanta", "Dallas"),
    ("Los Angeles", "San Francisco"), ("San Francisco", "Salt Lake City"),
    ("San Francisco", "Portland"), ("Portland", "Seattle"),
    ("Portland", "Salt Lake City"),
]


def test_world_loads(world):
    assert len(world.cities) >= 45
    assert len(world.legs) >= 80


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


# -- graph integrity -----------------------------------------------------------

def test_every_city_has_coordinates_and_a_known_region(world):
    from freight_fate.sim.weather import REGION_WEIGHTS

    for city in world.cities.values():
        assert city.region in REGION_WEIGHTS, f"{city.name}: region {city.region}"
        assert 24 < city.lat < 50, f"{city.name}: lat {city.lat}"
        assert -125 < city.lon < -66, f"{city.name}: lon {city.lon}"
        assert len(city.locations) >= 2, f"{city.name}: too few freight locations"


def test_no_city_is_a_dead_end(world):
    for name in world.city_names():
        assert len(world.neighbors(name)) >= 2, f"{name} is a dead end"


def test_legs_are_sane_and_unique(world):
    seen = set()
    for leg in world.legs:
        assert leg.a in world.cities, f"unknown endpoint {leg.a}"
        assert leg.b in world.cities, f"unknown endpoint {leg.b}"
        assert leg.terrain in {"flat", "hills", "mountain"}, leg
        assert 50 <= leg.miles <= 800, f"absurd mileage: {leg}"
        pair = frozenset((leg.a, leg.b))
        assert pair not in seen, f"duplicate leg {leg.a}-{leg.b}"
        seen.add(pair)


def test_dijkstra_connects_every_city_pair(world):
    names = world.city_names()
    for start in names:
        for end in names:
            if start != end:
                assert world.shortest_route(start, end) is not None, \
                    f"{end} unreachable from {start}"


def test_original_map_is_preserved_for_old_saves(world):
    for a, b in ORIGINAL_ADJACENT_PAIRS:
        assert world.route_from_cities([a, b]) is not None, \
            f"old direct leg {a}-{b} no longer resolves"
