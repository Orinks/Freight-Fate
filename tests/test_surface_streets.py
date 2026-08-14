"""Surface-street segment driving: baked turn cues spoken at boundaries and
per-street speed zones, per docs/surface-roads-plan.md Phase 2."""

import pytest

from freight_fate.data.world_models import Leg, Route
from freight_fate.sim.trip import Trip
from freight_fate.sim.trip_models import FACILITY_GATE_LIMIT_MPH
from freight_fate.sim.vehicle import TruckState
from freight_fate.sim.weather import WeatherSystem


def _turn_level_route(world):
    """Any tier-1 turn-level baked local geometry, built into a drivable
    Route directly from the retained ``local_geometry`` data.

    The drive-to-city-services feature (and its ``city_service_route``/
    ``city_service_geometry`` convenience wrappers) was retired, but the
    turn-level street-chain bake it used to source test data from is still
    shipped, so this rebuilds the same Route the wrapper used to hand back.
    """
    for city in sorted(world.cities):
        for service in world.city_services(city):
            geometry = world.local_geometry(f"city_service:{city}:{service.key}")
            if geometry is not None and geometry.turn_level and len(geometry.segments) >= 3:
                legs = [
                    Leg(
                        city,
                        city,
                        segment.miles,
                        segment.road,
                        "flat",
                        (),
                        local_cue=segment.cue,
                        local_speed_mph=segment.speed_mph,
                    )
                    for segment in geometry.segments
                ]
                return Route([city] * (len(legs) + 1), legs), geometry
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
    # The bake now carries REAL posted limits (30s, 35s, 45s...), so the
    # invariant is the test's own name: each zone speaks a speed that the
    # baked street data actually holds, inside the plausible street band.
    baked_speeds = {segment.speed_mph for segment in _geometry.segments}
    for zone in street_zones:
        assert zone.limit_mph in baked_speeds
        assert 5.0 <= zone.limit_mph <= 65.0
    # Adjacent same-speed streets merge: no zero-length or duplicate zones.
    for a, b in zip(street_zones, street_zones[1:], strict=False):
        assert b.start_mi == pytest.approx(a.end_mi)
        assert a.limit_mph != b.limit_mph or len(street_zones) == 1
    # The gate zone still caps the final stretch.
    assert any(
        z.reason == "facility gate" and z.limit_mph == FACILITY_GATE_LIMIT_MPH for z in trip.zones
    )


def test_single_leg_approaches_keep_the_blanket_zone(world):
    route = world.facility_approach_route("Chicago", world.city("Chicago").locations[0].name)
    if any(leg.local_speed_mph > 0 for leg in route.legs):
        pytest.skip("this facility gained turn-level data; blanket no longer applies")
    trip = _trip(route)
    access = [z for z in trip.zones if z.reason == "facility access road"]
    assert len(access) == 1
    assert access[0].limit_mph == 25.0
    assert access[0].end_mi == pytest.approx(trip.total_miles)
