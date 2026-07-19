"""Baked OSM maxspeed: normalization, the leg step-function, and the runtime
preference of a real posted limit over the highway/region heuristic."""

from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path

import pytest

from freight_fate.data.world import Leg, SpeedLimitSample
from freight_fate.data.world_models import Route, StateMileage
from freight_fate.sim import Trip, TruckState, WeatherSystem
from freight_fate.sim.trip import _leg_speed_limit_at, corridor_speed_limit

ROOT = Path(__file__).resolve().parents[1]


def _load_enrich_routes():
    """Import tools/enrich_routes.py by path (tools is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "enrich_routes", ROOT / "tools" / "enrich_routes.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parse_osm_maxspeed = _load_enrich_routes().parse_osm_maxspeed


# --- maxspeed normalization -------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("55 mph", 55.0),
        ("65 mph", 65.0),
        ("55", 55.0),  # bare number assumed mph on the US map
        ("90 km/h", 55.0),  # 55.9 -> nearest 5
        ("100 kmh", 60.0),  # 62.1 -> nearest 5
        ("100 kph", 60.0),
        ("55 mph; 50 mph", 55.0),  # first (general) token wins
        ("60 mph;40 mph @ (wet)", 60.0),
        ("none", None),
        ("signals", None),
        ("variable", None),
        ("", None),
        ("RU:urban", None),  # no digits
        ("5 knots", None),  # nautical, ignored
        (None, None),
    ],
)
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
    leg = _leg(
        (
            SpeedLimitSample(0.0, 65.0),
            SpeedLimitSample(40.0, 70.0),
            SpeedLimitSample(80.0, 55.0),
        )
    )
    assert _leg_speed_limit_at(leg, 10.0) == 65.0
    assert _leg_speed_limit_at(leg, 40.0) == 70.0
    assert _leg_speed_limit_at(leg, 79.9) == 70.0
    assert _leg_speed_limit_at(leg, 90.0) == 55.0


def test_offset_before_first_sample_uses_first():
    leg = _leg((SpeedLimitSample(10.0, 60.0), SpeedLimitSample(50.0, 70.0)))
    assert _leg_speed_limit_at(leg, 0.0) == 60.0


# --- coverage-gap markers ---------------------------------------------------


def test_gap_marker_answers_none_instead_of_holding_the_last_posting():
    # The NY-12 lesson: a village 30 whose tagging ends must not rule the
    # untagged miles that follow -- inside the gap the caller's heuristic
    # answers.
    leg = _leg(
        (
            SpeedLimitSample(0.0, 30.0),
            SpeedLimitSample(1.2, None),
            SpeedLimitSample(40.0, 55.0),
        )
    )
    assert _leg_speed_limit_at(leg, 0.5) == 30.0
    assert _leg_speed_limit_at(leg, 20.0) is None
    assert _leg_speed_limit_at(leg, 45.0) == 55.0


def test_parser_accepts_gap_markers_and_still_rejects_bad_numbers():
    from freight_fate.data.world_parsing import _parse_speed_limit

    sample = _parse_speed_limit({"at_mi": 5.0, "mph": None}, 100.0, "A", "B")
    assert sample.mph is None
    with pytest.raises(ValueError):
        _parse_speed_limit({"at_mi": 5.0, "mph": 150.0}, 100.0, "A", "B")


def _load_repair():
    spec = importlib.util.spec_from_file_location(
        "repair_interstate_anchor_limits", ROOT / "tools" / "repair_interstate_anchor_limits.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.repair


def test_anchor_repair_keeps_gap_markers_and_drops_street_pollution():
    repair = _load_repair()
    data = {
        "legs": [
            {
                "from": "a",
                "to": "b",
                "highway": "I-40",
                "miles": 100.0,
                "corridor": {
                    "speed_limits": [
                        {"at_mi": 0.0, "mph": 40.0},  # city-street pollution
                        {"at_mi": 3.0, "mph": 70.0},
                        {"at_mi": 60.0, "mph": None},  # gap marker stays
                    ]
                },
            }
        ]
    }
    repaired = repair(data)
    assert len(repaired) == 1
    kept = data["legs"][0]["corridor"]["speed_limits"]
    assert kept == [{"at_mi": 3.0, "mph": 70.0}, {"at_mi": 60.0, "mph": None}]


def test_anchor_repair_trusts_a_surface_anchor_bounded_by_a_gap():
    # A town 35 at mile 0 that the sweep marked as ending 1 mile in never
    # owned the corridor -- the runtime already reverts inside the gap, so
    # the sample is honest and must survive the surface-anchor rule.
    repair = _load_repair()
    data = {
        "legs": [
            {
                "from": "a",
                "to": "b",
                "highway": "US-60",
                "miles": 80.0,
                "corridor": {
                    "speed_limits": [
                        {"at_mi": 0.0, "mph": 35.0},
                        {"at_mi": 1.0, "mph": None},
                        {"at_mi": 10.0, "mph": 65.0},
                    ]
                },
            }
        ]
    }
    assert repair(data) == []
    assert len(data["legs"][0]["corridor"]["speed_limits"]) == 3


# --- runtime preference and fallback ---------------------------------------


def _open_road_mile(trip):
    """A mile out on the open road, away from the urban-reduction radius."""
    return trip.total_miles / 2.0


def test_runtime_prefers_baked_maxspeed_over_heuristic(world):
    route = world.route_options("Chicago", "St. Louis")[0]
    heuristic = corridor_speed_limit(route.legs[0].highway, "heartland")
    baked = heuristic + 5.0  # a value the heuristic would never produce here
    # Chicago-St. Louis may route through intermediate cities, so bake the value
    # onto every leg -- the sampled open-road mile can land on any of them.
    route.legs[:] = [
        dataclasses.replace(leg, speed_limits=(SpeedLimitSample(0.0, baked),)) for leg in route.legs
    ]
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    assert trip._corridor_limit_at(_open_road_mile(trip)) == baked


def test_runtime_caps_general_baked_limit_to_state_truck_limit():
    leg = Leg(
        "A",
        "B",
        100.0,
        "I-5",
        "flat",
        (),
        state_miles=(StateMileage("California", 100.0),),
        speed_limits=(SpeedLimitSample(0.0, 65.0),),
    )
    trip = Trip(Route(["A", "B"], [leg]), TruckState(), WeatherSystem("california", seed=1), seed=2)
    assert trip._corridor_limit_at(50.0) == 55.0


def test_runtime_keeps_truck_specific_baked_limit():
    leg = Leg(
        "A",
        "B",
        100.0,
        "I-5",
        "flat",
        (),
        state_miles=(StateMileage("California", 100.0),),
        speed_limits=(SpeedLimitSample(0.0, 50.0, hgv=True),),
    )
    trip = Trip(Route(["A", "B"], [leg]), TruckState(), WeatherSystem("california", seed=1), seed=2)
    assert trip._corridor_limit_at(50.0) == 50.0


def test_runtime_caps_oregon_and_idaho_truck_limits():
    # Oregon (65) and Idaho (70) also hold trucks below the car limit; a baked
    # car speed above the cap is pulled down at runtime.
    for state, baked, expected in (("Oregon", 70.0, 65.0), ("Idaho", 75.0, 70.0)):
        leg = Leg(
            "A",
            "B",
            100.0,
            "I-84",
            "flat",
            (),
            state_miles=(StateMileage(state, 100.0),),
            speed_limits=(SpeedLimitSample(0.0, baked),),
        )
        trip = Trip(
            Route(["A", "B"], [leg]),
            TruckState(),
            WeatherSystem("pacific_northwest", seed=1),
            seed=2,
        )
        assert trip._corridor_limit_at(50.0) == expected


def test_runtime_reads_baked_profile_in_reverse_direction():
    leg = Leg(
        "A",
        "B",
        100.0,
        "I-65",
        "flat",
        (),
        state_miles=(StateMileage("Indiana", 100.0),),
        speed_limits=(
            SpeedLimitSample(0.0, 55.0),
            SpeedLimitSample(80.0, 70.0),
        ),
    )
    trip = Trip(
        Route(["B", "A"], [leg]), TruckState(), WeatherSystem("great_lakes", seed=1), seed=2
    )
    assert trip._corridor_limit_at(10.0) == 65.0
    assert trip._corridor_limit_at(90.0) == 55.0


def test_runtime_falls_back_to_heuristic_without_a_profile(world):
    route = world.route_options("Chicago", "Indianapolis")[0]
    route.legs[0] = dataclasses.replace(route.legs[0], speed_limits=())
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    mile = _open_road_mile(trip)
    leg_i, _ = trip._leg_at_mile(mile)
    expected = corridor_speed_limit(route.legs[leg_i].highway, trip._region_at(mile))
    assert trip._corridor_limit_at(mile) == expected


def test_baked_limit_wins_near_city(world):
    route = world.route_options("Chicago", "Indianapolis")[0]
    route.legs[0] = dataclasses.replace(route.legs[0], speed_limits=(SpeedLimitSample(0.0, 75.0),))
    trip = Trip(route, TruckState(), WeatherSystem("great_lakes", seed=1), seed=2)
    # Real posted data is authoritative; the city cap is only a fallback when
    # the route lacks baked speed samples.
    assert trip._corridor_limit_at(0.0) == 75.0
