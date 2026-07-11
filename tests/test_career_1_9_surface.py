"""Transcript-backed career 1.9 surface-road transition scenarios."""

import pygame
import pytest
from playtest_harness import PlaytestHarness


def _chain_delivery(harness):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    world = harness.app.ctx.world
    facilities = []
    for city in sorted(world.cities):
        for location in world.cities[city].locations:
            approach = world.facility_approach_route(city, location.name)
            departure = world.facility_departure_route(city, location.name)
            if approach and departure and len(approach.legs) >= 2 and len(departure.legs) >= 2:
                facilities.append((city, location.name))
    for origin, origin_location in facilities:
        for destination, destination_location in facilities:
            if origin == destination:
                continue
            routes = world.route_options(origin, destination)
            if routes:
                route = routes[0]
                job = Job(
                    CARGO_CATALOG["general"],
                    18,
                    origin,
                    origin_location,
                    destination,
                    round(route.miles),
                    2000.0,
                    20.0,
                    destination_location=destination_location,
                )
                harness.app.ctx.profile = Profile(name="Surface Driver", current_city=origin)
                driving = DrivingState(harness.app.ctx, job, route, phase="delivery")
                harness.app.push_state(driving)
                harness.driving = driving
                harness._neutralize_random_trip_friction()
                return driving
    pytest.skip("no connected pair of chain-capable facilities")


@pytest.mark.career_1_9
@pytest.mark.smoke
def test_complete_surface_transition_chain_has_ordered_spoken_cues(monkeypatch):
    with PlaytestHarness(monkeypatch) as harness:
        result = harness.result
        driving = _chain_delivery(harness)

        assert driving._begin_departure_chain()
        assert driving._departure_chain
        departure_snapshot = driving.snapshot()
        driving._finish_departure_chain()
        assert not driving._departure_chain
        assert driving.lane.lane == 0

        # Real destination-intent key and the actual surface swap seam.
        harness.press_key(pygame.K_x, "x")
        assert driving._begin_surface_chain()
        assert driving._surface_chain
        approach_snapshot = driving.snapshot()

        assert departure_snapshot["departure_chain"] is True
        assert approach_snapshot["surface_chain"] is True
        result.assert_ordered(
            "Out of the gate and onto city streets",
            "Up the ramp and onto",
            "Off the ramp and onto city streets",
        )
        result.assert_screen_reader_friendly()
