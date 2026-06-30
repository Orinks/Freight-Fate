"""Baked OSM maxspeed: normalization, the leg step-function, and the runtime
preference of a real posted limit over the highway/region heuristic."""

from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path

import pytest

from freight_fate.data.world import Leg, SpeedLimitSample
from freight_fate.sim import Trip, TruckState, WeatherSystem
from freight_fate.sim.trip import _leg_speed_limit_at, corridor_speed_limit

ROOT = Path(__file__).resolve().parents[1]


def _load_enrich_routes():
    """Import tools/enrich_routes.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "enrich_routes", ROOT / "tools" / "enrich_routes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parse_osm_maxspeed = _load_enrich_routes().parse_osm_maxspeed


# --- maxspeed normalization -------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("55 mph", 55.0),
    ("65 mph", 65.0),
    ("55", 55.0),              # bare number assumed mph on the US map
    ("90 km/h", 55.0),         # 55.9 -> nearest 5
    ("100 kmh", 60.0),         # 62.1 -> nearest 5
    ("100 kph", 60.0),
    ("55 mph; 50 mph", 55.0),  # first (general) token wins
    ("60 mph;40 mph @ (wet)", 60.0),
    ("none", None),
    ("signals", None),
    ("variable", None),
    ("", None),
    ("RU:urban", None),        # no digits
    ("5 knots", None),         # nautical, ignored
    (None, None),
])
def test_parse_osm_maxspeed(raw, expected):
    assert parse_osm_maxspeed(raw) == expected


def test_parse_osm_maxspeed_default_kmh_for_non_us_data():
    # A bare number is km/h under OSM's default convention when asked.
    assert parse_osm_maxspeed("90", default_kmh=True) == 55.0


def test_parse_osm_maxspeed_clamps_to_truck_range():
    assert parse_osm_maxspeed("200 mph") == 85.0


# --- leg step function ------------------------------------------------------

def _leg(speed_limits=()):
    return Leg("A", "B", 100.0, "I-95", "flat", (), speed_limits=speed_limits)


def test_unbaked_leg_returns_none():
    assert _leg_speed_limit_at(_leg(), 50.0) is None


def test_single_sample_applies_everywhere():
    leg = _leg((SpeedLimitSample(0.0, 65.0),))
    assert _leg_speed_limit_at(leg, 0.0) == 65.0
    assert _leg_speed_limit_at(leg, 99.0) == 65.0


def test_step_function_picks_last_sample_at_or_before_offset():
    leg = _leg((
        SpeedLimitSample(0.0, 65.0),
        SpeedLimitSample(40.0, 70.0),
        SpeedLimitSample(80.0, 55.0),
    ))
    assert _leg_speed_limit_at(leg, 10.0) == 65.0
    assert _leg_speed_limit_at(leg, 40.0) == 70.0
    assert _leg_speed_limit_at(leg, 79.9) == 70.0
    assert _leg_speed_limit_at(leg, 90.0) == 55.0


def test_offset_before_first_sample_uses_first():
    leg = _leg((SpeedLimitSample(10.0, 60.0), SpeedLimitSample(50.0, 70.0)))
    assert _leg_speed_limit_at(leg, 0.0) == 60.0


# --- runtime preference and fallback ---------------------------------------

def _open_road_mile(trip):
    """A mile out on the open road, away from the urban-reduction radius."""
    return trip.total_miles / 2.0


def test_runtime_prefers_baked_maxspeed_over_heuristic(world):
    route = world.route_options("Chicago", "Indianapolis")[0]
    leg = route.legs[0]
    heuristic = corridor_speed_limit(leg.highway, "great_lakes")
    baked = heuristic + 5.0  # a value the heuristic would never produce here
    route.legs[0] = dataclasses.replace(
        leg, speed_limits=(SpeedLimitSample(0.0, baked),))
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    assert trip._corridor_limit_at(_open_road_mile(trip)) == baked


def test_runtime_falls_back_to_heuristic_without_a_profile(world):
    route = world.route_options("Chicago", "Indianapolis")[0]
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    mile = _open_road_mile(trip)
    leg_i, _ = trip._leg_at_mile(mile)
    expected = corridor_speed_limit(route.legs[leg_i].highway,
                                    trip._region_at(mile))
    assert trip._corridor_limit_at(mile) == expected


def test_baked_limit_wins_near_city(world):
    route = world.route_options("Chicago", "Indianapolis")[0]
    route.legs[0] = dataclasses.replace(
        route.legs[0], speed_limits=(SpeedLimitSample(0.0, 75.0),))
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    # Real posted data is authoritative; the city cap is only a fallback when
    # the route lacks baked speed samples.
    assert trip._corridor_limit_at(0.0) == 75.0
