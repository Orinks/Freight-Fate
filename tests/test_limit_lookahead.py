"""The co-driver warns before a posted-limit drop and sizes short zones.

Born from the NY-12 playtest (2026-07-19): real village 30s every few miles
are honest data, but hitting one blind at 55 in a Class-8 is not playable.
The warning reuses the curve-pacenote eligibility math (reaction plus
comfortable braking), and a short village zone has its length spoken on
entry so it reads as a passing event, not a new cruising speed.
"""

from __future__ import annotations

from freight_fate.data.world import Leg, SpeedLimitSample
from freight_fate.data.world_models import Route, StateMileage
from freight_fate.sim import Trip, TruckState, WeatherSystem
from freight_fate.sim.trip import _spoken_short_miles
from freight_fate.sim.trip_models import TripEventKind


def _trip(world, speed_limits, *, imperial=True):
    """A quiet 100-mile US-highway trip between real cities (the heuristic
    branch needs real city regions), with a synthetic posted profile."""
    leg = Leg(
        "aberdeen_sd_us",
        "pierre_sd_us",
        100.0,
        "US-83",
        "flat",
        (),
        state_miles=(StateMileage("South Dakota", 100.0),),
        speed_limits=tuple(speed_limits),
    )
    route = Route(["aberdeen_sd_us", "pierre_sd_us"], [leg])
    trip = Trip(route, TruckState(), WeatherSystem("upper_midwest", seed=1), seed=2)
    trip.imperial = imperial
    trip.zones = []
    trip.curves = ()
    trip._hazard_check_mi = 1e9
    trip._inspection_check_mi = 1e9
    return trip


def _cues(trip, position_mi, speed_mph):
    trip.position_mi = position_mi
    trip.truck.velocity_mps = speed_mph * 0.44704
    return [e.message for e in trip.update(0) if e.kind == TripEventKind.GPS_CUE]


VILLAGE = (
    SpeedLimitSample(0.0, 65.0),
    SpeedLimitSample(50.0, 30.0),
    SpeedLimitSample(50.6, 65.0),
)


def test_warns_before_a_big_drop_at_speed(world):
    trip = _trip(world, VILLAGE)
    cues = _cues(trip, 49.8, 55.0)
    assert "Speed limit drops to 30 in a quarter mile." in cues


def test_warning_fires_once(world):
    trip = _trip(world, VILLAGE)
    _cues(trip, 49.8, 55.0)
    assert not [c for c in _cues(trip, 49.85, 55.0) if "drops to" in c]


def test_no_warning_when_already_slow(world):
    trip = _trip(world, VILLAGE)
    assert not [c for c in _cues(trip, 49.8, 30.0) if "drops to" in c]


def test_no_warning_outside_the_braking_window(world):
    # 1.4 miles out at 55 is far beyond reaction plus comfortable braking.
    trip = _trip(world, VILLAGE)
    assert not [c for c in _cues(trip, 48.6, 55.0) if "drops to" in c]


def test_no_warning_for_a_small_step(world):
    trip = _trip(
        world,
        (SpeedLimitSample(0.0, 65.0), SpeedLimitSample(50.0, 60.0)),
    )
    assert not [c for c in _cues(trip, 49.8, 65.0) if "drops to" in c]


def test_short_zone_length_spoken_on_entry(world):
    trip = _trip(world, VILLAGE)
    _cues(trip, 49.0, 55.0)  # seed the announced limit at 65
    cues = _cues(trip, 50.05, 30.0)
    assert "Speed limit reduced to 30 for half a mile." in cues


def test_long_zone_entry_stays_unsized(world):
    trip = _trip(
        world,
        (SpeedLimitSample(0.0, 65.0), SpeedLimitSample(50.0, 30.0)),
    )
    _cues(trip, 49.0, 55.0)
    cues = _cues(trip, 50.05, 30.0)
    reduced = [c for c in cues if c.startswith("Speed limit reduced")]
    assert reduced == ["Speed limit reduced to 30."]


def test_gap_marker_ends_a_village_zone(world):
    # The NY-12 shape: a village 30 whose OSM tagging ends 0.6 miles in.
    # Inside the gap the heuristic answers (US highway 65), not the stale 30.
    trip = _trip(
        world,
        (SpeedLimitSample(40.0, 30.0), SpeedLimitSample(40.6, None)),
    )
    assert trip._corridor_limit_at(40.3) == 30.0
    assert trip._corridor_limit_at(45.0) == 65.0


def test_spoken_short_miles_units():
    assert _spoken_short_miles(0.2, True) == "a quarter mile"
    assert _spoken_short_miles(0.5, True) == "half a mile"
    assert _spoken_short_miles(0.5, False) == "800 meters"
