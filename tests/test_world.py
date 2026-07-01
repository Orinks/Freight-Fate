"""World data and route graph tests."""

# Every direct connection that existed in the 21-city 1.2.x map. Old
# mid-trip snapshots store these as consecutive route_cities pairs, so each
# one must remain a direct leg forever (or ship with a save migration).
ORIGINAL_ADJACENT_PAIRS = [
    ("New York", "Boston"),
    ("New York", "Philadelphia"),
    ("Philadelphia", "Pittsburgh"),
    ("Pittsburgh", "Cleveland"),
    ("Cleveland", "Chicago"),
    ("Chicago", "Indianapolis"),
    ("Indianapolis", "Nashville"),
    ("Nashville", "Atlanta"),
    ("Indianapolis", "St. Louis"),
    ("Chicago", "St. Louis"),
    ("St. Louis", "Nashville"),
    ("St. Louis", "Kansas City"),
    ("Kansas City", "Denver"),
    ("Denver", "Salt Lake City"),
    ("Denver", "Albuquerque"),
    ("Albuquerque", "Phoenix"),
    ("Phoenix", "Los Angeles"),
    ("Salt Lake City", "Las Vegas"),
    ("Las Vegas", "Los Angeles"),
    ("Dallas", "Albuquerque"),
    ("Dallas", "St. Louis"),
    ("Atlanta", "Dallas"),
    ("Los Angeles", "San Francisco"),
    ("San Francisco", "Salt Lake City"),
    ("San Francisco", "Portland"),
    ("Portland", "Seattle"),
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


def test_route_options_reject_out_of_direction_detours(world):
    from freight_fate.data.world import _max_alternate_miles

    for start, end in [
        ("Philadelphia", "New York"),  # Northeast Corridor freight
        ("Philadelphia", "Boston"),  # I-95 with plausible I-84 option
        ("Atlanta", "Dallas"),  # I-20, not a St. Louis loop
        ("Dallas", "Los Angeles"),  # Southwest corridors
        ("Denver", "Seattle"),  # I-80/I-84 or US-95/I-90
        ("New York", "Los Angeles"),  # long-haul alternatives still allowed
    ]:
        best = world.shortest_route(start, end)
        options = world.route_options(start, end, count=5)
        assert options
        assert options[0].cities == best.cities
        assert all(route.miles <= _max_alternate_miles(best.miles) for route in options)


def test_northeast_corridors_prefer_i95_not_inland_loops(world):
    philly_ny = world.route_options("Philadelphia", "New York", count=5)
    # Best option is the direct I-95 hop. The NJ Turnpike alternate via
    # Trenton/Newark is the real I-95 corridor, so it is allowed; loops inland
    # through the Alleghenies (Pittsburgh/Harrisburg) or Great Lakes are not.
    assert philly_ny[0].cities == ["Philadelphia", "New York"]
    assert philly_ny[0].highways == ["I-95"]
    inland = {"Pittsburgh", "Buffalo", "Harrisburg", "Scranton", "Binghamton"}
    assert all(inland.isdisjoint(route.cities) for route in philly_ny)

    philly_boston = world.route_options("Philadelphia", "Boston", count=5)
    assert philly_boston[0].cities == ["Philadelphia", "New York", "Boston"]
    assert philly_boston[0].highways == ["I-95"]
    assert all("Pittsburgh" not in route.cities for route in philly_boston)
    assert all("Buffalo" not in route.cities for route in philly_boston)


def test_shortest_route_is_actually_shortest(world):
    direct = world.shortest_route("New York", "Boston")
    assert direct is not None
    # New York's node is the Hunts Point (Bronx) freight hub, so I-95 legs land
    # there rather than at lower Manhattan; the direct hop is 205 mi.
    assert direct.miles == 205
    assert len(direct.legs) == 1


def test_unknown_city_raises(world):
    import pytest

    with pytest.raises(KeyError):
        world.shortest_route("New York", "Atlantis")


def test_every_city_has_locations_with_known_cargo(world):
    from freight_fate.data.world import FREIGHT_LOCATION_TYPES
    from freight_fate.models.jobs import CARGO_CATALOG

    for city in world.cities.values():
        assert city.locations, f"{city.name} has no freight locations"
        for loc in city.locations:
            assert loc.id, f"{loc.name} has no stable id"
            assert loc.city == city.name
            assert loc.type in FREIGHT_LOCATION_TYPES, f"unknown location type {loc.type}"
            assert loc.spoken_name
            assert loc.source_note
            assert loc.roles
            assert loc.ships or loc.receives
            for cargo in loc.cargo:
                assert cargo in CARGO_CATALOG, f"unknown cargo {cargo} at {loc.name}"
            for cargo in loc.ships + loc.receives:
                assert cargo in CARGO_CATALOG, f"unknown role cargo {cargo} at {loc.name}"


def test_home_terminal_prefers_explicit_terminal_and_falls_back_to_yard(world):
    explicit = world.home_terminal("Nashville")
    fallback = world.home_terminal("Chicago")

    assert explicit.name == "Music City Freight"
    assert explicit.label == "company terminal"
    assert explicit.spoken_name == "company terminal: Music City Freight"
    assert explicit.service_area == "Nashville, Tennessee"
    assert fallback.name == "Chicago Company Yard"
    assert fallback.label == "company yard"
    assert fallback.spoken_name == "company yard: Chicago Company Yard"


def test_freight_location_categories_are_live(world):
    types = {loc.type for city in world.cities.values() for loc in city.locations}
    expected = {
        "air_cargo",
        "automotive_plant",
        "chemical_petroleum_terminal",
        "cold_storage",
        "company_yard",
        "construction_materials_yard",
        "cross_dock",
        "dry_warehouse",
        "farm_elevator",
        "food_processor",
        "grocery_retail_dc",
        "intermodal_ramp",
        "lumber_paper",
        "manufacturing_plant",
        "mine_quarry",
        "parcel_hub",
        "port_terminal",
        "steel_industrial",
    }
    assert expected <= types


def test_each_metro_expands_to_representative_facilities(world):
    for city in world.cities.values():
        assert len(city.locations) >= 6
        assert city.market_tags
        assert any(loc.template for loc in city.locations)
        assert any(loc.type in {"company_yard", "terminal"} for loc in city.locations)


def test_route_stops_have_trucker_relevant_types(world):
    from freight_fate.data.world import (
        DEFAULT_POI_ACTIONS,
        PARKING_CERTAINTY_LABELS,
        POI_ACTIONS,
        STOP_DIRECTIONS,
        STOP_TYPE_LABELS,
    )

    route = world.shortest_route("San Antonio", "Dallas")
    assert route is not None
    assert route.stop_details
    assert all(stop.type in STOP_TYPE_LABELS for stop in route.stop_details)
    assert any(stop.spoken_name.startswith("travel center:") for stop in route.stop_details)
    assert all(stop.source for stop in route.stop_details)
    assert all(stop.actions for stop in route.stop_details)
    assert all(stop.curated for stop in route.stop_details)
    assert all(stop.parking in PARKING_CERTAINTY_LABELS for stop in route.stop_details)
    assert all(set(stop.directions) <= STOP_DIRECTIONS for stop in route.stop_details)
    assert all(set(stop.actions) <= POI_ACTIONS for stop in route.stop_details)
    assert all(
        set(stop.actions) <= set(DEFAULT_POI_ACTIONS[stop.type]) for stop in route.stop_details
    )

    parking_route = world.shortest_route("Los Angeles", "San Diego")
    assert any(stop.type == "public_rest_area" for stop in parking_route.stop_details)


def test_public_rest_areas_do_not_imply_repair(world):
    rest_area_actions = [
        stop.actions for leg in world.legs for stop in leg.stops if stop.type == "public_rest_area"
    ]
    assert rest_area_actions
    assert all("repair" not in actions for actions in rest_area_actions)
    assert all("roadside_assistance" not in actions for actions in rest_area_actions)


def test_route_stops_have_explicit_valid_positions(world):
    for leg in world.legs:
        for stop in leg.stops:
            assert 0.0 < stop.at_mi < leg.miles, f"{leg.a}-{leg.b}: {stop}"
            assert stop.directions
            assert stop.parking


def test_no_placeholder_pois_remain_in_current_route_network(world):
    placeholders = [
        (leg.a, leg.b, stop.name) for leg in world.legs for stop in leg.stops if not stop.curated
    ]
    assert placeholders == []

    route = world.supported_route("Memphis", "Nashville")
    assert route is not None
    assert route.metadata_complete(world)


def test_poi_names_are_curated_not_raw_osm_dump(world):
    raw_markers = ("osm_id", "amenity=", "highway=", "operator=", "node/", "way/")
    for city in world.cities.values():
        for facility in city.locations:
            lowered = facility.name.lower()
            assert not any(marker in lowered for marker in raw_markers), facility.name
            assert facility.spoken_name
    for leg in world.legs:
        for stop in leg.stops:
            lowered = stop.name.lower()
            assert not any(marker in lowered for marker in raw_markers), stop.name
            assert stop.spoken_name
        for toll in leg.toll_events:
            lowered = toll.name.lower()
            assert not any(marker in lowered for marker in raw_markers), toll.name


def test_world_rejects_raw_source_text_in_player_poi_name():
    import pytest

    from freight_fate.data.world import World

    data = {
        "cities": {
            "A": {
                "state": "One",
                "region": "midwest",
                "lat": 40,
                "lon": -90,
                "locations": [{"name": "A Yard", "type": "terminal", "cargo": ["general"]}],
            },
            "B": {
                "state": "One",
                "region": "midwest",
                "lat": 41,
                "lon": -91,
                "locations": [{"name": "B Yard", "type": "terminal", "cargo": ["general"]}],
            },
        },
        "legs": [
            {
                "from": "A",
                "to": "B",
                "miles": 80,
                "highway": "I-1",
                "terrain": "flat",
                "stops": [
                    {
                        "name": "amenity=fuel node/123",
                        "type": "travel_center",
                        "at_mi": 30,
                        "source": "fixture",
                    }
                ],
            }
        ],
    }

    with pytest.raises(ValueError, match="raw OSM"):
        World(data)


def test_world_rejects_raw_source_text_in_player_facility_name():
    import pytest

    from freight_fate.data.world import World

    data = {
        "cities": {
            "A": {
                "state": "One",
                "region": "midwest",
                "lat": 40,
                "lon": -90,
                "locations": [
                    {"name": "warehouse way/123", "type": "terminal", "cargo": ["general"]}
                ],
            },
            "B": {
                "state": "One",
                "region": "midwest",
                "lat": 41,
                "lon": -91,
                "locations": [{"name": "B Yard", "type": "terminal", "cargo": ["general"]}],
            },
        },
        "legs": [],
    }

    with pytest.raises(ValueError, match="raw source text"):
        World(data)


def test_repair_action_requires_matching_service_metadata():
    import pytest

    from freight_fate.data.world import World

    data = {
        "cities": {
            "A": {
                "state": "One",
                "region": "midwest",
                "lat": 40,
                "lon": -90,
                "locations": [{"name": "A Yard", "type": "terminal", "cargo": ["general"]}],
            },
            "B": {
                "state": "One",
                "region": "midwest",
                "lat": 41,
                "lon": -91,
                "locations": [{"name": "B Yard", "type": "terminal", "cargo": ["general"]}],
            },
        },
        "legs": [
            {
                "from": "A",
                "to": "B",
                "miles": 80,
                "highway": "I-1",
                "terrain": "flat",
                "stops": [
                    {
                        "name": "Example Service Plaza",
                        "type": "service_plaza",
                        "at_mi": 30,
                        "source": "fixture source names emergency service provider",
                        "actions": ["park", "save", "repair"],
                        "services": ["parking"],
                    }
                ],
            }
        ],
    }

    with pytest.raises(ValueError, match="matching source-backed service"):
        World(data)


def test_explicit_roadside_assistance_service_can_extend_plaza_actions():
    from freight_fate.data.world import World

    data = {
        "cities": {
            "A": {
                "state": "One",
                "region": "midwest",
                "lat": 40,
                "lon": -90,
                "locations": [{"name": "A Yard", "type": "terminal", "cargo": ["general"]}],
            },
            "B": {
                "state": "One",
                "region": "midwest",
                "lat": 41,
                "lon": -91,
                "locations": [{"name": "B Yard", "type": "terminal", "cargo": ["general"]}],
            },
        },
        "legs": [
            {
                "from": "A",
                "to": "B",
                "miles": 80,
                "highway": "I-1",
                "terrain": "flat",
                "stops": [
                    {
                        "name": "Example Turnpike Service Plaza",
                        "type": "service_plaza",
                        "at_mi": 30,
                        "source": "fixture source names authorized emergency road service",
                        "actions": ["park", "save", "fuel", "break", "roadside_assistance"],
                        "services": ["diesel", "parking", "roadside_assistance"],
                    }
                ],
            }
        ],
    }

    stop = World(data).legs[0].stops[0]
    assert "roadside_assistance" in stop.actions
    assert "roadside_assistance" in stop.services


def test_corridor_metadata_supports_offline_itineraries(world):
    route = world.route_from_cities(["Chicago", "Indianapolis"])
    leg = route.legs[0]

    assert leg.route_points
    assert leg.route_points[0].at_mi == 0.0
    assert leg.route_points[-1].at_mi == leg.miles
    assert leg.elevation_samples
    assert leg.elevation_samples[0].elevation_ft > 500.0
    assert leg.grade_segments
    assert {segment.terrain for segment in leg.grade_segments} == {"flat"}
    assert max(abs(segment.avg_grade_pct) for segment in leg.grade_segments) < 0.2
    assert [crossing.state for crossing in leg.state_crossings] == ["Indiana"]
    assert leg.state_crossings[0].at_mi == 32.8
    assert any(
        checkpoint.name == "Gary and Hammond industrial corridor" for checkpoint in leg.checkpoints
    )
    assert sum(state_miles.miles for state_miles in leg.state_miles) == leg.miles


def test_supported_routes_require_complete_corridor_metadata(world):
    supported_pairs = [
        ("Chicago", "Indianapolis"),
        ("Chicago", "St. Louis"),
        ("Memphis", "Little Rock"),
        ("San Antonio", "Dallas"),
        ("Des Moines", "Chicago"),
        ("Phoenix", "Los Angeles"),
        ("Denver", "Salt Lake City"),
        ("New York", "Boston"),
        ("Indianapolis", "Nashville"),
        ("Nashville", "Atlanta"),
        ("Kansas City", "Denver"),
        ("Dallas", "Albuquerque"),
    ]
    for start, end in supported_pairs:
        route = world.supported_route(start, end)
        assert route is not None, f"{start} to {end} is not dispatch-supported"
        assert route.metadata_complete(world)

    for leg in world.legs:
        # Dispatch requires routing metadata only; POIs are additive.
        assert world.leg_metadata_complete(leg), f"{leg.a}-{leg.b}"
        curated = [stop for stop in leg.stops if stop.curated]
        # Any POIs that are present must still be valid (source/actions/parking).
        assert all(stop.source for stop in curated), f"{leg.a}-{leg.b}"
        assert all(stop.actions for stop in curated), f"{leg.a}-{leg.b}"
        assert all(stop.parking != "unknown" for stop in curated), f"{leg.a}-{leg.b}"
        route = world.route_from_cities([leg.a, leg.b])
        assert all(stop.curated for stop in route.stop_details), f"{leg.a}-{leg.b}"


def test_tier_one_priority_corridors_keep_multi_stop_curated_fuel_support(world):
    expected = {
        ("Atlanta", "Dallas"): 3,
        ("Dallas", "Albuquerque"): 3,
        ("Dallas", "St. Louis"): 3,
        ("Kansas City", "Denver"): 3,
        ("San Francisco", "Salt Lake City"): 3,
        ("San Francisco", "Portland"): 3,
        ("Portland", "Salt Lake City"): 3,
    }

    for (start, end), minimum_stops in expected.items():
        route = world.supported_route(start, end)
        assert route is not None, f"{start} to {end} is not dispatch-supported"
        curated = route.stop_details
        fuel_capable = [stop for stop in curated if "fuel" in stop.actions]
        assert len(curated) >= minimum_stops, f"{start}-{end}"
        assert len(fuel_capable) >= 2, f"{start}-{end}"
        assert any(stop.parking == "confirmed" for stop in curated), f"{start}-{end}"
        assert all(stop.curated for stop in curated), f"{start}-{end}"


def test_southern_hos_pressure_corridors_have_added_safe_stops(world):
    expected = {
        ("Dallas", "Albuquerque"): {
            "Love's Travel Stop Wichita Falls",
            "Flying J Travel Center Tucumcari",
        },
        ("Dallas", "St. Louis"): {
            "Love's Travel Stop Ardmore",
            "Love's Travel Stop Rolla",
        },
        ("Atlanta", "Dallas"): {
            "Pilot Travel Center Tallapoosa",
            "Love's Travel Stop Heflin",
        },
        ("Nashville", "Atlanta"): {"Flying J Travel Center Resaca"},
    }
    for pair, names in expected.items():
        route = world.supported_route(*pair)
        assert route is not None
        stops = {stop.name: stop for stop in route.stop_details}
        assert names <= set(stops)
        for name in names:
            stop = stops[name]
            assert stop.curated
            assert stop.parking == "confirmed"
            assert {"park", "save", "fuel", "break", "sleep"} <= set(stop.actions)
            assert "2026-06-18" in stop.source


def test_southern_sleep_stop_gaps_are_no_longer_extreme(world):
    def max_sleep_gap(start: str, end: str) -> float:
        route = world.supported_route(start, end)
        assert route is not None
        points = [0.0]
        points.extend(stop.at_mi for stop in route.stop_details if "sleep" in stop.actions)
        points.append(route.miles)
        points.sort()
        return max(b - a for a, b in zip(points, points[1:], strict=False))

    assert max_sleep_gap("Dallas", "Albuquerque") < 180.0
    assert max_sleep_gap("Dallas", "St. Louis") < 200.0
    assert max_sleep_gap("Atlanta", "Dallas") < 215.0
    assert max_sleep_gap("Nashville", "Atlanta") < 120.0


def test_toll_metadata_is_explicit_and_separate_from_service_plazas(world):
    route = world.route_from_cities(["New York", "Philadelphia"])
    assert route.toll_events
    assert route.estimated_tolls > 0

    toll_names = {event.name for event in route.toll_events}
    stop_names = {stop.name for leg in route.legs for stop in leg.stops}
    assert toll_names.isdisjoint(stop_names)

    event = route.toll_events[0]
    assert event.road == "New Jersey Turnpike"
    assert event.authority == "New Jersey Turnpike Authority"
    assert event.method == "ticket_system"
    assert event.amount > 0
    assert event.estimated
    assert "toll" in event.source.lower()

    plazas = [stop for leg in route.legs for stop in leg.stops if stop.type == "service_plaza"]
    assert plazas
    assert all("fuel" in plaza.actions for plaza in plazas)


def test_world_rejects_missing_stop_position():
    import pytest

    from freight_fate.data.world import World

    data = {
        "cities": {
            "A": {"state": "Test", "region": "midwest", "locations": []},
            "B": {"state": "Test", "region": "midwest", "locations": []},
        },
        "legs": [
            {
                "from": "A",
                "to": "B",
                "miles": 100,
                "highway": "I-1",
                "terrain": "flat",
                "stops": ["Synthetic midpoint"],
            }
        ],
    }

    with pytest.raises(ValueError, match="missing explicit at_mi"):
        World(data)


def test_world_rejects_out_of_range_stop_position():
    import pytest

    from freight_fate.data.world import World

    data = {
        "cities": {
            "A": {"state": "Test", "region": "midwest", "locations": []},
            "B": {"state": "Test", "region": "midwest", "locations": []},
        },
        "legs": [
            {
                "from": "A",
                "to": "B",
                "miles": 100,
                "highway": "I-1",
                "terrain": "flat",
                "stops": [{"name": "Past the city", "type": "travel_center", "at_mi": 130}],
            }
        ],
    }

    with pytest.raises(ValueError, match="outside leg mileage"):
        World(data)


def test_route_describe_mentions_miles_and_highway(world):
    route = world.shortest_route("Chicago", "Indianapolis")
    text = route.describe()
    assert "183" in text
    assert "I-65" in text


# -- graph integrity -----------------------------------------------------------


def test_every_city_has_coordinates_and_a_known_region(world):
    from freight_fate.sim.weather import REGION_WEIGHTS

    for city in world.cities.values():
        assert city.region in REGION_WEIGHTS, f"{city.name}: region {city.region}"
        assert 24 < city.lat < 50, f"{city.name}: lat {city.lat}"
        assert -125 < city.lon < -66, f"{city.name}: lon {city.lon}"
        assert len(city.locations) >= 2, f"{city.name}: too few freight locations"


def test_legs_are_sane_and_unique(world):
    seen = set()
    for leg in world.legs:
        assert leg.a in world.cities, f"unknown endpoint {leg.a}"
        assert leg.b in world.cities, f"unknown endpoint {leg.b}"
        assert leg.terrain in {"flat", "hills", "mountain"}, leg
        # Real metro-twin and drayage corridors (Newark-NYC ~11 mi, Norfolk-
        # Virginia Beach ~18, New Haven-Bridgeport ~21) are legitimate short
        # freight lanes; only ban truly trivial or cross-country single legs.
        assert 10 <= leg.miles <= 800, f"absurd mileage: {leg}"
        pair = frozenset((leg.a, leg.b))
        assert pair not in seen, f"duplicate leg {leg.a}-{leg.b}"
        seen.add(pair)


def leg_terrain(world, a, b):
    route = world.route_from_cities([a, b])
    assert route is not None, f"no direct leg {a}-{b}"
    return route.legs[0].terrain


def test_famous_corridors_have_real_terrain(world):
    """Pin well-known trucking geography so it cannot drift back to flat.

    Each entry names the grade or landform that earns the label.
    """
    expected = {
        # the legendary grades
        ("Nashville", "Atlanta"): "mountain",  # I-24 Monteagle Mountain
        ("Knoxville", "Nashville"): "mountain",  # I-40 Cumberland Plateau
        ("Charlotte", "Knoxville"): "mountain",  # I-40 Pigeon River Gorge
        ("Philadelphia", "Pittsburgh"): "mountain",  # PA Turnpike Alleghenies
        ("Baltimore", "Pittsburgh"): "mountain",  # Sideling Hill country
        ("Sacramento", "Reno"): "mountain",  # I-80 Donner Pass
        ("Denver", "Albuquerque"): "mountain",  # I-25 Raton Pass
        ("Boise", "Portland"): "mountain",  # I-84 Cabbage Hill
        ("Spokane", "Seattle"): "mountain",  # I-90 Snoqualmie Pass
        ("Spokane", "Boise"): "mountain",  # US-95 White Bird grade
        # honest rolling country
        ("St. Louis", "Kansas City"): "hills",  # I-70 Missouri River hills
        ("Wichita", "Kansas City"): "hills",  # I-35 Flint Hills
        ("Oklahoma City", "Dallas"): "hills",  # I-35 Arbuckle Mountains
        ("Memphis", "Nashville"): "hills",  # I-40 Highland Rim
        ("Milwaukee", "Minneapolis"): "hills",  # I-94 driftless coulees
        ("New York", "Boston"): "hills",  # I-95 rolling Connecticut
        ("Richmond", "Raleigh"): "hills",  # I-85 piedmont
        ("Phoenix", "Los Angeles"): "hills",  # I-10 San Gorgonio Pass
        ("Amarillo", "Albuquerque"): "hills",  # I-40 Clines Corners climb
        # genuinely flat country stays flat
        ("Kansas City", "Denver"): "flat",  # I-70 across the high plains
        ("Chicago", "St. Louis"): "flat",  # I-55 Illinois prairie
        ("New Orleans", "Houston"): "flat",  # I-10 Gulf coastal plain
        ("Omaha", "Cheyenne"): "flat",  # I-80 Platte River valley
        ("Jacksonville", "Miami"): "flat",  # I-95 Florida coast
    }
    for (a, b), terrain in expected.items():
        assert leg_terrain(world, a, b) == terrain, f"{a}-{b}"


def test_dijkstra_connects_every_city_pair(world):
    names = world.city_names()
    seen = {names[0]}
    stack = [names[0]]
    while stack:
        city = stack.pop()
        for leg in world.legs:
            if leg.a == city and leg.b not in seen:
                seen.add(leg.b)
                stack.append(leg.b)
            elif leg.b == city and leg.a not in seen:
                seen.add(leg.a)
                stack.append(leg.a)
    assert seen == set(names)


def test_original_map_is_preserved_for_old_saves(world):
    for a, b in ORIGINAL_ADJACENT_PAIRS:
        assert world.route_from_cities([a, b]) is not None, (
            f"old direct leg {a}-{b} no longer resolves"
        )
