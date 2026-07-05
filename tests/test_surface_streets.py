"""Surface-street segment driving: baked turn cues spoken at boundaries and
per-street speed zones, per docs/surface-roads-plan.md Phase 2."""

import pytest

from freight_fate.sim.trip import Trip
from freight_fate.sim.trip_models import FACILITY_GATE_LIMIT_MPH
from freight_fate.sim.vehicle import TruckState
from freight_fate.sim.weather import WeatherSystem


def _turn_level_route(world):
    """Any city-service route built from tier-1 turn-level segments."""
    for city in sorted(world.cities):
        for service in world.city_services(city):
            geometry = world.city_service_geometry(city, service.key)
            if geometry is not None and geometry.turn_level and len(geometry.segments) >= 3:
                return world.city_service_route(city, service.key), geometry
    pytest.skip("no turn-level city service geometry in the shipped data")


def _trip(route) -> Trip:
    truck = TruckState()
    truck.transmission.automatic = True
    return Trip(route, truck, WeatherSystem("heartland", seed=1), seed=2)


def test_turn_level_route_carries_segment_cues_and_speeds(world):
    route, geometry = _turn_level_route(world)
    assert len(route.legs) == len(geometry.segments)
    for leg, segment in zip(route.legs, geometry.segments, strict=True):
        assert leg.highway == segment.road
        assert leg.local_cue == segment.cue
        assert leg.local_speed_mph == segment.speed_mph


def test_navigation_cues_speak_the_baked_maneuvers(world):
    route, geometry = _turn_level_route(world)
    trip = _trip(route)
    spoken = " | ".join(cue.near_text for cue in trip.navigation_cues)
    # Every road-change maneuver from the baked data is announced verbatim
    # (same-road consecutive segments collapse into the previous cue).
    for prev, segment in zip(geometry.segments, geometry.segments[1:], strict=False):
        if segment.road != prev.road:
            assert segment.cue.rstrip(".") in spoken
    assert geometry.segments[0].cue.rstrip(".") in spoken


def test_surface_zones_follow_the_street_speeds(world):
    route, _geometry = _turn_level_route(world)
    trip = _trip(route)
    street_zones = [z for z in trip.zones if z.reason == "facility access road"]
    assert street_zones
    # Zones tile the whole route and carry the baked street speeds.
    assert street_zones[0].start_mi == 0.0
    assert street_zones[-1].end_mi == pytest.approx(trip.total_miles)
    for zone in street_zones:
        assert zone.limit_mph in {15.0, 25.0}
    # Adjacent same-speed streets merge: no zero-length or duplicate zones.
    for a, b in zip(street_zones, street_zones[1:], strict=False):
        assert b.start_mi == pytest.approx(a.end_mi)
        assert a.limit_mph != b.limit_mph or len(street_zones) == 1
    # The gate zone still caps the final stretch.
    assert any(
        z.reason == "facility gate" and z.limit_mph == FACILITY_GATE_LIMIT_MPH for z in trip.zones
    )


def test_single_leg_approaches_keep_the_blanket_zone(world):
    route = world.facility_approach_route("Chicago", world.cities["Chicago"].locations[0].name)
    if any(leg.local_speed_mph > 0 for leg in route.legs):
        pytest.skip("this facility gained turn-level data; blanket no longer applies")
    trip = _trip(route)
    access = [z for z in trip.zones if z.reason == "facility access road"]
    assert len(access) == 1
    assert access[0].limit_mph == 25.0
    assert access[0].end_mi == pytest.approx(trip.total_miles)
