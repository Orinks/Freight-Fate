"""Save/reload checkpoints for the critical career 1.9 journey."""

import pytest
from playtest_harness import PlaytestHarness


@pytest.mark.career_1_9
def test_pickup_facility_checkpoint_restores_job_profile_and_spoken_context(monkeypatch):
    from freight_fate.states.city import PickupFacilityState
    from freight_fate.states.city_pickup import pickup_snapshot

    with PlaytestHarness(monkeypatch) as harness:
        result = harness.start_delivery(profile_name="Pickup Resume", stop_at_pickup=True)
        state = harness.app.state
        snapshot = pickup_snapshot(state.job, checked_in=state.checked_in, loaded=state.loaded)
        harness.app.ctx.profile.active_trip = snapshot
        resumed = PickupFacilityState.from_snapshot(harness.app.ctx, snapshot)
        assert resumed is not None
        resumed.announce_entry()

        assert resumed.job == state.job
        assert harness.app.ctx.profile.name == "Pickup Resume"
        assert snapshot["kind"] == "pickup"

    result.assert_ordered("Arrived at pickup", "Arrived at pickup")


@pytest.mark.career_1_9
def test_highway_checkpoint_restores_phase_route_position_job_and_profile(monkeypatch):
    from freight_fate.states.driving import DrivingState

    with PlaytestHarness(monkeypatch) as harness:
        harness.start_delivery(profile_name="Highway Resume")
        driving = harness.driving
        driving.trip.position_mi = min(12.5, driving.trip.total_miles / 2)
        snapshot = driving.snapshot()
        harness.app.ctx.profile.active_trip = snapshot
        resumed = DrivingState.from_snapshot(harness.app.ctx, snapshot)

        assert resumed is not None
        assert resumed.phase == driving.phase == "delivery"
        assert resumed.job.cargo == driving.job.cargo
        assert resumed.job.origin == driving.job.origin
        assert resumed.job.destination == driving.job.destination
        assert resumed.job.destination_location == driving.job.destination_location
        assert resumed.route.cities == driving.route.cities
        assert resumed.trip.position_mi == pytest.approx(driving.trip.position_mi)
        assert harness.app.ctx.profile.name == "Highway Resume"


@pytest.mark.career_1_9
def test_destination_surface_checkpoint_restores_street_position(monkeypatch):
    from test_career_1_9_surface import _chain_delivery

    from freight_fate.states.driving import DrivingState

    with PlaytestHarness(monkeypatch) as harness:
        driving = _chain_delivery(harness)
        assert driving._begin_surface_chain()
        driving.trip.position_mi = min(0.5, driving.trip.total_miles / 2)
        snapshot = driving.snapshot()
        resumed = DrivingState.from_snapshot(harness.app.ctx, snapshot)

        assert resumed is not None
        assert resumed._surface_chain
        assert resumed.phase == "delivery"
        assert resumed.job.cargo == driving.job.cargo
        assert resumed.job.origin == driving.job.origin
        assert resumed.job.destination == driving.job.destination
        assert resumed.job.destination_location == driving.job.destination_location
        assert resumed.route.cities == driving.route.cities
        assert resumed.trip.position_mi == pytest.approx(driving.trip.position_mi)
        assert harness.app.ctx.profile.name == "Surface Driver"
