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


def test_generated_slow_zones_never_nest_or_touch(world):
    """Construction and traffic zones must be separated by open road.

    Regression: zones were placed by independent draws, so one construction
    zone could land inside another, or two could chain back to back
    (player-reported on the 2026-07-09 snapshot).
    """
    from freight_fate.sim.trip import ZONE_MIN_GAP_MI

    route = world.supported_route("Chicago", "St. Louis")
    assert route is not None
    for seed in range(300):
        trip = Trip(
            route,
            TruckState(),
            WeatherSystem(world.cities[route.cities[0]].region, seed=7),
            seed=seed,
        )
        zones = sorted(
            (z for z in trip.zones if z.reason in ("construction", "heavy traffic")),
            key=lambda z: z.start_mi,
        )
        for a, b in zip(zones, zones[1:], strict=False):
            assert b.start_mi - a.end_mi >= ZONE_MIN_GAP_MI, (
                f"seed {seed}: {a.reason} {a.start_mi:.1f}-{a.end_mi:.1f} and "
                f"{b.reason} {b.start_mi:.1f}-{b.end_mi:.1f} overlap or touch"
            )


def test_no_brake_hazards_on_facility_access_roads(world, monkeypatch):
    """A deadhead crawl to a pickup facility must never spring a "brake now"
    hazard: the access road is minutes long at yard speeds (player report).
    Forced to certainty, the hazard check still declines to fire there."""
    from freight_fate.sim.trip import Trip as TripClass
    from freight_fate.sim.trip_models import TripEventKind

    city = world.cities["chicago_il_us"]
    location = city.locations[0]
    route = world.facility_approach_route(city.key, location.name)
    trip = Trip(
        route,
        TruckState(),
        WeatherSystem(city.region, seed=7),
        seed=1,
    )
    assert trip._is_facility_approach_route()

    monkeypatch.setattr(TripClass, "_hazard_risk", lambda self: 1.0)
    trip._hazard_check_mi = 0.0
    trip._check_hazards(1.0)

    assert all(e.kind != TripEventKind.HAZARD for e in trip._events)

    # The same forced check on a normal route does fire, so this test would
    # catch the gate being lost.
    highway_route = world.supported_route("Chicago", "St. Louis")
    highway_trip = Trip(
        highway_route,
        TruckState(),
        WeatherSystem(city.region, seed=7),
        seed=1,
    )
    highway_trip._hazard_check_mi = 0.0
    highway_trip._check_hazards(1.0)
    assert any(e.kind == TripEventKind.HAZARD for e in highway_trip._events)
