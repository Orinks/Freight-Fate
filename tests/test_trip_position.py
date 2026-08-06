"""Where the truck is on the map: interpolating a position along the route."""

from freight_fate.data.world import get_world
from freight_fate.sim.radio import distance_mi
from freight_fate.sim.trip import Trip
from freight_fate.sim.vehicle import TruckState
from freight_fate.sim.weather import WeatherSystem


def _trip(start="Buffalo", end="Rochester"):
    world = get_world()
    route = world.supported_route(start, end)
    return Trip(route, TruckState(), WeatherSystem(seed=1), seed=7), world


def test_position_starts_at_the_origin_city_and_ends_at_the_destination():
    trip, world = _trip()
    origin = world.cities[trip.route.cities[0]]
    destination = world.cities[trip.route.cities[-1]]

    start = trip.position_latlon(0.0)
    end = trip.position_latlon(trip.total_miles)
    assert start is not None and end is not None
    # Within a mile of the city the route is anchored on.
    assert distance_mi(start[0], start[1], origin.lat, origin.lon) < 1.0
    assert distance_mi(end[0], end[1], destination.lat, destination.lon) < 1.0


def test_position_follows_the_route_forward():
    trip, _ = _trip()
    origin = trip.position_latlon(0.0)
    half = trip.position_latlon(trip.total_miles / 2.0)
    end = trip.position_latlon(trip.total_miles)
    assert origin is not None and half is not None and end is not None
    # Halfway along is genuinely between the ends, not sitting on either.
    assert distance_mi(*origin, *half) > 5.0
    assert distance_mi(*half, *end) > 5.0


def test_travelled_distance_is_in_the_right_ballpark():
    """Summing the interpolated path must not wildly disagree with the route."""
    trip, _ = _trip()
    steps = 40
    total = 0.0
    previous = trip.position_latlon(0.0)
    for i in range(1, steps + 1):
        point = trip.position_latlon(trip.total_miles * i / steps)
        total += distance_mi(*previous, *point)
        previous = point
    # Straight-line hops between samples cut corners, so the geodesic sum is a
    # lower bound on road miles -- but it must not be a different journey.
    assert 0.5 * trip.total_miles < total <= trip.total_miles * 1.05


def test_position_defaults_to_where_the_truck_is():
    trip, _ = _trip()
    trip.position_mi = trip.total_miles / 3.0
    assert trip.position_latlon() == trip.position_latlon(trip.total_miles / 3.0)


def test_positions_outside_the_route_clamp_to_its_ends():
    """Overshooting either end must land on that city, not past it.

    A leg's baked polyline can run slightly longer than the leg length it is
    filed under, so without clamping the far end of the run reads as a point
    beyond the destination.
    """
    trip, world = _trip()
    destination = world.cities[trip.route.cities[-1]]

    assert trip.position_latlon(-500.0) == trip.position_latlon(0.0)
    assert trip.position_latlon(trip.total_miles + 500.0) == trip.position_latlon(trip.total_miles)
    end = trip.position_latlon(trip.total_miles)
    assert distance_mi(end[0], end[1], destination.lat, destination.lon) < 1.0


def test_the_geometry_is_built_once_and_reused():
    trip, _ = _trip()
    first = trip._geo_samples()
    assert first is trip._geo_samples()
    assert len(first[0]) == len(first[1]) > 1


def test_a_reversed_leg_still_runs_origin_to_destination():
    """The same pair of cities driven the other way must not run backwards."""
    forward, world = _trip("Buffalo", "Rochester")
    backward, _ = _trip("Rochester", "Buffalo")
    buffalo = world.cities["buffalo_ny_us"]

    start_back = backward.position_latlon(0.0)
    # Driving Rochester to Buffalo starts far from Buffalo and ends near it.
    assert distance_mi(*start_back, buffalo.lat, buffalo.lon) > 20.0
    end_back = backward.position_latlon(backward.total_miles)
    assert distance_mi(*end_back, buffalo.lat, buffalo.lon) < 1.0
    # And the forward run is the mirror image.
    start_fwd = forward.position_latlon(0.0)
    assert distance_mi(*start_fwd, buffalo.lat, buffalo.lon) < 1.0
