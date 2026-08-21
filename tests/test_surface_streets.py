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


def test_the_access_road_posts_one_limit_and_the_gate(world):
    """One number for the chain, one change at the gate -- never a new posting
    every few hundred feet.

    The chain used to be zoned street by street, which announced a limit
    change per leg: half of all baked segments are under two tenths of a mile,
    so a driver heard the same "facility access road" post 15, then 25, then
    15 again with nothing under the wheels changing. None of those numbers is
    a reading -- the bake assumes 25 for a named street and 15 for an unnamed
    one wherever OSM carries no maxspeed, which is very nearly everywhere --
    so a change between them was the data reporting whether the way had a
    NAME, dressed as a sign.
    """
    route, geometry = _turn_level_route(world)
    trip = _trip(route)
    street_zones = [z for z in trip.zones if z.reason == "facility access road"]
    assert len(street_zones) == 1
    assert street_zones[0].start_mi == 0.0
    assert street_zones[0].end_mi == pytest.approx(trip.total_miles)
    # It speaks a speed the baked street data actually holds, and never a
    # lower crawl than the best street on the chain offers.
    baked_speeds = {segment.speed_mph for segment in geometry.segments}
    assert street_zones[0].limit_mph == max(baked_speeds)
    assert 5.0 <= street_zones[0].limit_mph <= 65.0
    # The gate zone still caps the final stretch.
    assert any(
        z.reason == "facility gate" and z.limit_mph == FACILITY_GATE_LIMIT_MPH for z in trip.zones
    )
    # And walking the chain, the posted limit changes exactly once: at the
    # gate. Anything else is a message promising a change that is not one.
    step = max(trip.total_miles / 400.0, 0.001)
    seen: list[float] = []
    mile = 0.0
    while mile <= trip.total_miles:
        limit, _ = trip.speed_limit_at(mile)
        if not seen or limit != seen[-1]:
            seen.append(limit)
        mile += step
    assert seen == [street_zones[0].limit_mph, FACILITY_GATE_LIMIT_MPH]


def test_single_leg_approaches_keep_the_blanket_zone(world):
    route = world.facility_approach_route("Chicago", world.city("Chicago").locations[0].name)
    if any(leg.local_speed_mph > 0 for leg in route.legs):
        pytest.skip("this facility gained turn-level data; blanket no longer applies")
    trip = _trip(route)
    access = [z for z in trip.zones if z.reason == "facility access road"]
    assert len(access) == 1
    assert access[0].limit_mph == 25.0
    assert access[0].end_mi == pytest.approx(trip.total_miles)
