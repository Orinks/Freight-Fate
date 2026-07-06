"""Surface chaining: the destination ramp flows onto the facility's real
street chain and ends at the gate, per docs/surface-roads-plan.md Phase 3."""

import pytest


def _turn_level_facility(world):
    """(city, location_name) of any facility with a tier-1 street chain."""
    for city in sorted(world.cities):
        for location in world.cities[city].locations:
            approach = world.facility_source_approach(city, location.name)
            if approach is not None and approach.turn_level and len(approach.segments) >= 2:
                return city, location.name
    pytest.skip("no turn-level facility approaches in the shipped data")


def _driving_to(app, city: str, location_name: str):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Chain", current_city="Chicago")
    route = app.ctx.world.route_options("Chicago", city)
    if not route:
        pytest.skip(f"no corridor route Chicago -> {city}")
    route = route[0]
    job = Job(
        CARGO_CATALOG["general"],
        18,
        "Chicago",
        "Chicago Terminal",
        city,
        round(route.miles),
        2000.0,
        20.0,
        destination_location=location_name,
    )
    driving = DrivingState(app.ctx, job, route, phase="delivery")
    driving.trip.traffic_manager.vehicles = []
    return driving


def test_chain_swaps_to_streets_and_keeps_the_clock():
    from freight_fate.app import App

    app = App()
    try:
        city, location = _turn_level_facility(app.ctx.world)
        d = _driving_to(app, city, location)
        highway = d.trip
        highway.game_minutes = 123.0
        d._destination_exit_taken = True

        assert d._begin_surface_chain()
        assert d._surface_chain
        assert d.trip is not highway
        assert d._highway_trip is highway
        # Clock, weekday, and settlement continuity.
        assert d.trip.game_minutes == 123.0
        assert d.trip.start_hour == highway.start_hour
        assert d.trip.career_hours == highway.career_hours
        assert d.trip.toll_charges is highway.toll_charges
        # The streets are real tier-1 segments with per-street zones.
        assert len(d.trip.route.legs) >= 2
        assert any(leg.local_speed_mph > 0 for leg in d.trip.route.legs)
        assert any(z.reason == "facility access road" for z in d.trip.zones)
        assert any(z.reason == "facility gate" for z in d.trip.zones)
        # No random hazards on the last city miles.
        assert d.trip.hazard_scale == 0.0
    finally:
        app.shutdown()


def test_chain_declines_without_turn_level_data():
    from freight_fate.app import App

    app = App()
    try:
        world = app.ctx.world
        # Find a facility WITHOUT a turn-level approach.
        found = None
        for city in sorted(world.cities):
            for location in world.cities[city].locations:
                approach = world.facility_source_approach(city, location.name)
                if approach is None or not approach.turn_level:
                    found = (city, location.name)
                    break
            if found:
                break
        assert found
        d = _driving_to(app, found[0], found[1])
        old = d.trip
        assert not d._begin_surface_chain()
        assert d.trip is old
        assert not d._surface_chain
    finally:
        app.shutdown()


def test_chain_survives_save_and_resume():
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        city, location = _turn_level_facility(app.ctx.world)
        d = _driving_to(app, city, location)
        d._destination_exit_taken = True
        assert d._begin_surface_chain()
        d.trip.position_mi = min(1.0, d.trip.total_miles / 2.0)
        snap = d.snapshot()
        assert snap["surface_chain"] is True

        resumed = DrivingState.from_snapshot(app.ctx, snap)
        assert resumed is not None
        assert resumed._surface_chain
        assert resumed._destination_exit_taken
        assert any(leg.local_speed_mph > 0 for leg in resumed.trip.route.legs)
        assert resumed.trip.position_mi == pytest.approx(d.trip.position_mi)
        assert resumed.trip.game_minutes == pytest.approx(d.trip.game_minutes)
    finally:
        app.shutdown()


def test_old_saves_resume_without_a_chain():
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        city, location = _turn_level_facility(app.ctx.world)
        d = _driving_to(app, city, location)
        d.trip.position_mi = 5.0
        snap = d.snapshot()
        del snap["surface_chain"]  # pre-chain save format

        resumed = DrivingState.from_snapshot(app.ctx, snap)
        assert resumed is not None
        assert not resumed._surface_chain
        assert resumed.trip.position_mi == pytest.approx(5.0)
    finally:
        app.shutdown()


def test_ramp_completion_enters_the_chain():
    from freight_fate.app import App
    from freight_fate.sim.trip import RoadStop

    app = App()
    try:
        city, location = _turn_level_facility(app.ctx.world)
        d = _driving_to(app, city, location)
        d._destination_exit_taken = True
        d._ramp_mi = 0.0
        d._ramp_stop = RoadStop(location, 10.0, "delivery_destination", ("deliver",))
        d._ramp_control = "none"
        d._ramp_terminal_done = True
        d.truck.velocity_mps = 0.0

        d._update_exit(0.0)

        assert d._surface_chain
        assert not d.trip.finished  # the drive continues on the streets
        assert d._ramp_mi is None
    finally:
        app.shutdown()
