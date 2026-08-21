"""Departure-side surface chaining: a loaded run out of a chain-capable
origin facility starts on its real streets and merges onto the highway,
mirroring the arrival chain (docs/surface-roads-plan.md Phase 3)."""

import pytest


def _turn_level_facility(world):
    """(city, location_name) of any facility with a tier-1 street chain."""
    for city in sorted(world.cities):
        for location in world.cities[city].locations:
            approach = world.facility_source_approach(city, location.name)
            if approach is not None and approach.turn_level and len(approach.segments) >= 2:
                return city, location.name
    pytest.skip("no turn-level facility approaches in the shipped data")


def _driving_from(app, city: str, location_name: str):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Chain", current_city=city)
    destination = (
        "Chicago" if app.ctx.world.resolve_city_key(city) != "chicago_il_us" else "Detroit"
    )
    routes = app.ctx.world.route_options(city, destination)
    if not routes:
        pytest.skip(f"no corridor route {city} -> {destination}")
    route = routes[0]
    job = Job(
        CARGO_CATALOG["general"],
        18,
        city,
        location_name,
        destination,
        round(route.miles),
        2000.0,
        20.0,
    )
    driving = DrivingState(app.ctx, job, route, phase="delivery")
    driving.trip.traffic_manager.vehicles = []
    return driving


def test_departure_route_reverses_the_chain_and_flips_the_turns():
    from freight_fate.app import App

    app = App()
    try:
        world = app.ctx.world
        city, location = _turn_level_facility(world)
        arrival = world.facility_approach_route(city, location)
        departure = world.facility_departure_route(city, location)

        assert departure is not None
        a_legs = list(arrival.legs)
        d_legs = list(departure.legs)
        assert [leg.highway for leg in d_legs] == [leg.highway for leg in reversed(a_legs)]
        assert d_legs[0].local_cue == f"Start on {d_legs[0].highway}."
        # Each outbound junction flips the inbound turn at the same corner.
        flips = {"left": "Turn right onto", "right": "Turn left onto", "ahead": "Continue onto"}
        for j in range(1, len(d_legs)):
            inbound_cue = a_legs[len(a_legs) - j].local_cue.lower()
            if inbound_cue.startswith("turn left"):
                expected = flips["left"]
            elif inbound_cue.startswith("turn right"):
                expected = flips["right"]
            elif inbound_cue.startswith("continue"):
                expected = flips["ahead"]
            else:
                expected = "Turn onto"
            assert d_legs[j].local_cue == f"{expected} {d_legs[j].highway}."
            assert d_legs[j].local_speed_mph == a_legs[len(a_legs) - 1 - j].local_speed_mph
    finally:
        app.shutdown()


def test_departure_chain_swaps_to_streets_and_merges_back():
    from freight_fate.app import App

    app = App()
    try:
        city, location = _turn_level_facility(app.ctx.world)
        d = _driving_from(app, city, location)
        highway = d.trip

        assert d._begin_departure_chain()
        assert d._departure_chain
        assert d.trip is not highway
        assert d._highway_trip is highway
        assert d.trip.start_hour == highway.start_hour
        assert d.trip.career_hours == highway.career_hours
        # Real streets: multi-segment, per-street speed, no random hazards.
        assert len(d.trip.route.legs) >= 2
        assert any(leg.local_speed_mph > 0 for leg in d.trip.route.legs)
        assert d.trip.hazard_scale == 0.0

        # No phantom "delivery exit" near the end of the short street trip.
        assert d._destination_exit_stop() is None

        # End of the streets: the merge hands the highway trip back with
        # the clock and the toll ledger.
        d.trip.game_minutes = 7.5
        surface_tolls = d.trip.toll_charges
        d._finish_departure_chain()
        assert d.trip is highway
        assert not d._departure_chain
        assert d._highway_trip is None
        assert highway.game_minutes == 7.5
        assert highway.toll_charges is surface_tolls
        assert d.lane.lane == 0  # merging in from the ramp, right lane
    finally:
        app.shutdown()


def test_departure_declines_without_turn_level_data():
    from freight_fate.app import App

    app = App()
    try:
        world = app.ctx.world
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
        d = _driving_from(app, found[0], found[1])
        old = d.trip
        assert not d._begin_departure_chain()
        assert d.trip is old
        assert not d._departure_chain
    finally:
        app.shutdown()


def test_departure_chain_survives_save_and_resume():
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        city, location = _turn_level_facility(app.ctx.world)
        d = _driving_from(app, city, location)
        assert d._begin_departure_chain()
        d.trip.position_mi = min(1.0, d.trip.total_miles / 2.0)
        snap = d.snapshot()
        assert snap["departure_chain"] is True

        resumed = DrivingState.from_snapshot(app.ctx, snap)
        assert resumed is not None
        assert resumed._departure_chain
        assert resumed._departure_checked  # no double-start on the first tick
        assert any(leg.local_speed_mph > 0 for leg in resumed.trip.route.legs)
        assert resumed.trip.position_mi == pytest.approx(d.trip.position_mi)
        assert resumed.trip.game_minutes == pytest.approx(d.trip.game_minutes)
    finally:
        app.shutdown()


def test_resumed_highway_saves_stay_on_the_highway():
    from freight_fate.app import App
    from freight_fate.states.driving import DrivingState

    app = App()
    try:
        city, location = _turn_level_facility(app.ctx.world)
        d = _driving_from(app, city, location)
        d.trip.position_mi = 5.0
        snap = d.snapshot()
        assert snap["departure_chain"] is False

        resumed = DrivingState.from_snapshot(app.ctx, snap)
        assert resumed is not None
        assert not resumed._departure_chain
        assert resumed._departure_checked
        assert resumed.trip.position_mi == pytest.approx(5.0)

        # A pre-chain save format resumes exactly as before, too.
        del snap["departure_chain"]
        older = DrivingState.from_snapshot(app.ctx, snap)
        assert older is not None
        assert not older._departure_chain
    finally:
        app.shutdown()


def test_the_gate_is_at_the_yard_end_when_the_chain_is_driven_outbound():
    """The gate is a place on the chain, not "the last half mile" of whichever
    way you happen to be driving it.

    The same baked street chain is driven both ways -- in to the dock, and
    back out to the highway when a run starts at a facility. Zoning the gate
    onto the final stretch is right inbound and exactly wrong outbound, where
    the final stretch is the ON-RAMP: it held the truck to 15 where it should
    have been winding up to merge, and cruise refuses to engage inside a gate
    zone at all (Brandon, 2026-08-21).
    """
    from freight_fate.app import App
    from freight_fate.sim.trip import Trip
    from freight_fate.sim.trip_models import FACILITY_GATE_LIMIT_MPH
    from freight_fate.sim.vehicle import TruckState
    from freight_fate.sim.weather import WeatherSystem

    app = App()
    try:
        city, location = _turn_level_facility(app.ctx.world)
        outbound_route = app.ctx.world.facility_departure_route(city, location)
        assert outbound_route is not None

        def _gate(outbound: bool):
            trip = Trip(
                outbound_route,
                TruckState(),
                WeatherSystem(seed=3),
                seed=11,
                hazard_scale=0.0,
                outbound=outbound,
            )
            gates = [z for z in trip.zones if z.reason == "facility gate"]
            assert len(gates) == 1
            return trip, gates[0]

        trip, gate = _gate(True)
        assert gate.start_mi == 0.0, "leaving the yard, the gate is the first thing you pass"
        assert gate.end_mi < trip.total_miles
        # The road up to the on-ramp is street speed, not gate speed.
        end_limit, _ = trip.speed_limit_at(trip.total_miles)
        assert end_limit > FACILITY_GATE_LIMIT_MPH

        # Driven the other way down the same road, the gate is at the far end.
        inbound_trip, inbound_gate = _gate(False)
        assert inbound_gate.end_mi == pytest.approx(inbound_trip.total_miles)
        assert inbound_trip.speed_limit_at(inbound_trip.total_miles)[0] == FACILITY_GATE_LIMIT_MPH
    finally:
        app.shutdown()


def test_pulling_out_of_a_facility_clears_the_stop_pause():
    """An arrival pause must not outlive the stop it was made for.

    Automatic speed control pauses when the truck stops somewhere, and the
    resume path deliberately never lifts an ARRIVAL pause -- only a departure
    clears one. Nothing was clearing this one, so the pause earned by pulling
    in to load followed the driver back out onto the road: armed, paused, and
    refusing to engage for the rest of the run (Brandon, 2026-08-21).
    """
    from freight_fate.app import App

    app = App()
    try:
        city, location = _turn_level_facility(app.ctx.world)
        d = _driving_from(app, city, location)
        d._speed_control_armed = True
        d._speed_control_paused_at_stop = True
        assert d._begin_departure_chain(announce=False) is True
        assert d._speed_control_paused_at_stop is False
    finally:
        app.shutdown()


def test_the_acceleration_lane_is_real_road_and_the_keeper_drives_it():
    """Leaving a yard gets a real acceleration lane, and the automation that
    can work at low speed is the one that gets it.

    The lane is sized from the highway it feeds (AASHTO Green Book Table 10-3
    via TxDOT Table 3-13). The keeper takes it directly rather than the
    handoff falling to cruise: the trip swap lands late in the frame, so for
    one tick the new road reads as open highway with no zone, and cruise --
    which cannot hold below its own minimum speed -- ended up nominally
    engaged with nothing touching the throttle. The truck coasted the whole
    lane.
    """
    from freight_fate.app import App
    from freight_fate.sim.trip_models import acceleration_lane_mi

    app = App()
    try:
        city, location = _turn_level_facility(app.ctx.world)
        d = _driving_from(app, city, location)
        app.ctx.settings.speed_keeper = True
        d._speed_control_armed = True
        highway = d.trip
        assert d._begin_departure_chain(announce=False) is True
        # Rolling, because the keeper only takes a truck that is moving --
        # it is a speed HOLDER, not a launch control.
        d.truck.start_engine()
        d.truck.set_air_ready(parking_brake=False)
        d.truck.velocity_mps = 18.0 / 2.23694
        # Drive the streets out, then let the chain hand over.
        d.trip.position_mi = d.trip.total_miles
        d.trip.finished = True
        d._finish_departure_chain()

        expected = acceleration_lane_mi(highway.speed_limit_at(0.0)[0], highway.grade_at(0.0))
        assert d._departure_ramp_mi == pytest.approx(expected)
        assert d._departure_ramp_mi > 0.0
        # The keeper owns it, aiming at the road it is joining -- not cruise.
        assert d._keeper_mph is not None
        assert d._cruise_mph is None
        assert d._keeper_mph == pytest.approx(highway.speed_limit_at(0.0)[0])

        # And the lane runs out after the distance it claimed, not before.
        d._update_departure_ramp(d._departure_ramp_mi / 2.0)
        assert d._departure_ramp_mi is not None
        d._update_departure_ramp(d._departure_ramp_mi)
        assert d._departure_ramp_mi is None
    finally:
        app.shutdown()
