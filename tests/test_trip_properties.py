"""Property checks for route-backed trip simulation invariants."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from freight_fate.sim import Trip, TruckState, WeatherSystem

SUPPORTED_ROUTE_PAIRS = (
    ("Buffalo", "Rochester"),
    ("Chicago", "Indianapolis"),
    ("Chicago", "St. Louis"),
    ("Denver", "Cheyenne"),
    ("Memphis", "Nashville"),
)


@pytest.mark.property
@given(
    route_pair=st.sampled_from(SUPPORTED_ROUTE_PAIRS),
    progress=st.floats(min_value=0.0, max_value=1.25, allow_nan=False, allow_infinity=False),
    imperial=st.booleans(),
)
def test_trip_position_derived_values_stay_bounded(world, route_pair, progress, imperial):
    route = world.supported_route(*route_pair)
    assert route is not None
    trip = Trip(
        route,
        TruckState(),
        WeatherSystem(world.cities[route.cities[0]].region, seed=7),
        seed=11,
        imperial=imperial,
    )

    trip.position_mi = route.miles * progress

    assert 0.0 <= trip.remaining_miles <= trip.total_miles
    assert 0 <= trip.current_leg_index < len(route.legs)

    leg_index, leg_start = trip._leg_at_mile(trip.position_mi)
    assert 0 <= leg_index < len(route.legs)
    assert math.isclose(leg_start, trip._leg_starts[leg_index])

    speed_limit, reason = trip.speed_limit_at(trip.position_mi)
    assert 0 < speed_limit <= 85
    assert reason is None or reason

    assert trip.navigation_cues == sorted(trip.navigation_cues, key=lambda cue: cue.at_mi)
    assert all(0.0 <= cue.at_mi <= trip.total_miles for cue in trip.navigation_cues)
