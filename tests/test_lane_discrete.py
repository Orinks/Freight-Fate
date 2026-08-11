"""Discrete lane layer: steering crossings, tap changes, closed-lane
policing, hazard dodges, keep-right pressure, and exit-lane gating."""

import pytest
from speech_capture import speech_stub

from freight_fate.sim.lane import CROSS_AT, LaneKeeping, lane_label
from freight_fate.sim.traffic_manager import TrafficVehicle
from freight_fate.sim.trip_models import Zone, hazard_is_dodgeable


def _driving(app):
    from freight_fate.models.jobs import CARGO_CATALOG, Job
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app.ctx.profile = Profile(name="Lanes", current_city="Buffalo")
    route = app.ctx.world.supported_route("Buffalo", "Rochester")
    job = Job(
        CARGO_CATALOG["general"],
        12.0,
        "Buffalo",
        "company yard",
        "Rochester",
        route.miles,
        1000.0,
        12.0,
        destination_location="Rochester freight market",
    )
    driving = DrivingState(app.ctx, job, route, phase="delivery")
    # A clean road for deterministic lane checks; tests add their own NPCs.
    driving.trip.traffic_manager.vehicles = []
    return driving


def _rolling(driving, mph: float = 60.0) -> None:
    driving.truck.start_engine()
    driving.truck.velocity_mps = mph / 2.2369362920544


def _npc(position_mi: float, lane: int, speed_mph: float = 50.0) -> TrafficVehicle:
    return TrafficVehicle(
        key=f"npc:{lane}:{position_mi}",
        position_mi=position_mi,
        speed_mph=speed_mph,
        target_speed_mph=speed_mph,
        relative_lane=-lane,
        intent="cruising",
        vehicle_class="car",
        lane=lane,
    )


# -- LaneKeeping: the discrete layer under the drift model -----------------------


def test_lane_labels():
    assert lane_label(0, 2) == "right"
    assert lane_label(1, 2) == "left"
    assert lane_label(1, 3) == "middle"
    assert lane_label(2, 3) == "left"


def test_steering_across_the_line_changes_lanes():
    lane = LaneKeeping(seed=3)
    lane.steering = -1.0  # hold left
    crossed = 0
    for _ in range(200):
        lane.update(0.1, 29.0, assist="off")
        if lane.crossed:
            crossed = lane.crossed
            break
    assert crossed == 1
    assert lane.lane == 1
    # Entered the new lane from its right side, still drifting across it.
    assert lane.offset > 0.0


def test_no_lane_to_the_left_means_the_median():
    lane = LaneKeeping(seed=3)
    lane.lane = 1  # already in the left lane
    lane.steering = -1.0
    fired = False
    for _ in range(400):
        if lane.update(0.1, 29.0, assist="off"):
            fired = True
            break
    assert fired  # off-road event, not a lane change
    assert lane.lane == 1
    assert lane.crossed == 0


def test_interior_lane_line_does_not_rumble():
    lane = LaneKeeping(seed=1)
    lane.offset = -1.0  # straddling the line toward the left lane
    assert lane.rumble_level() == 0.0
    lane.offset = 1.0  # drifting onto the shoulder
    assert lane.rumble_level() > 0.0
    assert "left" in lane_label(1, 2)


def test_describe_names_the_lane():
    lane = LaneKeeping(seed=1)
    assert lane.describe() == "In the right lane, centered."
    lane.lane = 1
    lane.offset = -0.5
    assert lane.describe() == "In the left lane, drifting left."


def test_set_lane_count_clamps_the_lane():
    lane = LaneKeeping(seed=1)
    lane.lane = 1
    lane.set_lane_count(1)
    assert lane.lane == 0
    assert CROSS_AT > 1.0  # crossing requires actually straddling the line


# -- Hazard dodgeability ----------------------------------------------------------


def test_fixed_lane_hazards_are_dodgeable_and_sweeping_ones_are_not():
    assert hazard_is_dodgeable("debris on the road")
    assert hazard_is_dodgeable("a vehicle stopped on the shoulder")
    assert hazard_is_dodgeable("a slow vehicle ahead")
    assert not hazard_is_dodgeable("a deer crossing the road")
    assert not hazard_is_dodgeable("ice on the bridge deck")
    assert not hazard_is_dodgeable("a dust storm dropping visibility")


# -- Construction closures --------------------------------------------------------


def test_construction_zones_sometimes_close_a_lane():
    from freight_fate.app import App
    from freight_fate.sim.trip import Trip

    app = App()
    try:
        route = app.ctx.world.supported_route("Chicago", "St. Louis")
        assert route is not None
        found_closed = found_open = False
        from freight_fate.models.profile import Profile
        from freight_fate.sim.vehicle import TruckState
        from freight_fate.sim.weather import WeatherSystem

        app.ctx.profile = Profile(name="Zones", current_city="Chicago")
        for seed in range(60):
            trip = Trip(
                route,
                TruckState(),
                WeatherSystem("great_lakes", seed=seed),
                time_scale=20.0,
                seed=seed,
                start_hour=10.0,
                imperial=True,
                hazard_scale=1.0,
            )
            for zone in trip.zones:
                if zone.reason != "construction":
                    continue
                if zone.closed_lane in (0, 1):
                    found_closed = True
                    # The taper ahead carries the same closure for its callout.
                    tapers = [
                        z
                        for z in trip.zones
                        if z.reason == "construction merge" and abs(z.end_mi - zone.start_mi) < 0.01
                    ]
                    assert tapers and tapers[0].closed_lane == zone.closed_lane
                elif zone.closed_lane is None:
                    found_open = True
            if found_closed and found_open:
                break
        assert found_closed and found_open
    finally:
        app.shutdown()


def test_closure_messages_name_the_closed_side():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        trip = d.trip
        closed_right = Zone(5.0, 8.0, 45.0, "construction", closed_lane=0)
        closed_left = Zone(5.0, 8.0, 45.0, "construction", closed_lane=1)
        open_zone = Zone(5.0, 8.0, 45.0, "construction")
        assert "right lane is closed; merge left" in trip._zone_warning_message(closed_right, 2.0)
        assert "left lane is closed; merge right" in trip._zone_warning_message(closed_left, 2.0)
        assert "hold your lane" in trip._zone_warning_message(open_zone, 2.0)
        assert "stay in the right lane" in trip._zone_entry_message(closed_left)
    finally:
        app.shutdown()


def test_riding_a_closed_lane_warns_then_hits_the_barrels():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d, 55.0)
        d.trip.position_mi = 6.0
        d.trip.zones.append(Zone(5.0, 9.0, 45.0, "construction", closed_lane=1))
        d.lane.lane = 1
        before = d.truck.damage_pct

        d._update_merge(0.1)
        assert d._merge_deadline is not None  # warned, clock running
        assert d.truck.damage_pct == pytest.approx(before)

        for _ in range(200):
            d._update_merge(0.1)
            if d._merge_deadline is None:
                break
        assert d.lane.lane == 0  # shoved into the open lane
        assert d.truck.damage_pct > before
    finally:
        app.shutdown()


def test_moving_over_in_time_avoids_the_barrels():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d, 55.0)
        d.trip.position_mi = 6.0
        d.trip.zones.append(Zone(5.0, 9.0, 45.0, "construction", closed_lane=1))
        d.lane.lane = 1
        before = d.truck.damage_pct

        d._update_merge(0.1)  # warning
        d.lane.lane = 0  # player merges out
        for _ in range(120):
            d._update_merge(0.1)
        assert d.truck.damage_pct == pytest.approx(before)
    finally:
        app.shutdown()


def _synthetic_trip(segments, miles: float, seed: int):
    """A trip over one made-up leg with the given baked lane segments."""
    from freight_fate.data.world_models import Leg, Route
    from freight_fate.sim.trip import Trip
    from freight_fate.sim.vehicle import TruckState
    from freight_fate.sim.weather import WeatherSystem

    leg = Leg("a", "b", miles, "US-30", "flat", (), lane_segments=tuple(segments))
    return Trip(
        Route(cities=["a", "b"], legs=[leg]),
        TruckState(),
        WeatherSystem(seed=seed),
        time_scale=1.0,
        seed=seed,
    )


def _closure_footprints(trip):
    """(taper start, work zone end) for every construction zone that cones
    off a lane."""
    out = []
    for zone in trip.zones:
        if zone.reason != "construction" or zone.closed_lane is None:
            continue
        tapers = [
            z
            for z in trip.zones
            if z.reason == "construction merge" and abs(z.end_mi - zone.start_mi) < 0.01
        ]
        start = tapers[0].start_mi if tapers else zone.start_mi
        out.append((start, zone.end_mi))
    return out


def test_a_one_lane_road_never_gets_a_coned_off_lane():
    """Shane's Detroit-Mansfield trap: the work zone closed the only lane the
    road had, so there was nowhere legal to be."""
    from freight_fate.data.world_models import LaneSegment

    for seed in range(40):
        # Undivided two-way, so one lane our side for the whole leg.
        trip = _synthetic_trip([LaneSegment(0.0, 900.0, lanes=2, oneway=False)], 900.0, seed)
        assert _closure_footprints(trip) == [], f"seed {seed} coned off the only lane"


def test_a_closure_never_straddles_a_stretch_that_narrows():
    """A zone that starts on two lanes and ends on one is the same trap."""
    from freight_fate.data.world_models import LaneSegment

    segments = [
        LaneSegment(0.0, 450.0, lanes=2, oneway=True),  # two lanes our side
        LaneSegment(450.0, 900.0, lanes=2, oneway=False),  # one lane our side
    ]
    for seed in range(40):
        trip = _synthetic_trip(segments, 900.0, seed)
        for start, end in _closure_footprints(trip):
            mile = start
            while mile <= end:
                assert trip.lane_count_at(mile) >= 2, f"seed {seed} closes a lane at mile {mile}"
                mile += 0.25


def test_riding_a_closed_lane_with_nowhere_to_go_is_never_punished(monkeypatch):
    """The trap in Shane's log: pinned in lane zero on a one-lane stretch, the
    merge warning fired forever and the barrels took a bite every few seconds."""
    from freight_fate.app import App

    app = App()
    events: list[tuple[str, bool]] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(events, with_interrupt=True))
        _rolling(d, 55.0)
        d.trip.position_mi = 6.0
        d.trip.zones.append(Zone(5.0, 9.0, 45.0, "construction", closed_lane=0))
        d.lane.set_lane_count(1)  # the road narrowed under the zone
        before = d.truck.damage_pct

        for _ in range(400):
            d._update_merge(0.1)

        assert d._merge_deadline is None
        assert d.truck.damage_pct == pytest.approx(before)
        assert not [text for text, _ in events if "closed" in text]
    finally:
        app.shutdown()


def _run_into_the_barrels(d, zone) -> None:
    """Ride the coned-off lane until the barrels take the truck."""
    d.trip.position_mi = (zone.start_mi + zone.end_mi) / 2.0
    d.trip.zones.append(zone)
    d.lane.lane = zone.closed_lane
    for _ in range(200):
        d._update_merge(0.1)
        if d._merge_deadline is None and d.lane.lane != zone.closed_lane:
            return
    raise AssertionError("the barrels never fired")


def test_plowing_the_barrels_costs_a_fine_and_a_serious_violation(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.enforcement import WORK_ZONE_BARRELS_FINE, citation_fine

    app = App()
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub())
        _rolling(d, 55.0)
        p = app.ctx.profile
        record = p.driving_record
        before_money = p.money
        before_serious = len(record.serious_violations)

        _run_into_the_barrels(d, Zone(5.0, 9.0, 45.0, "construction", closed_lane=1))

        # Knocking the barrels down happens inside the cones by definition, so
        # this citation is always the doubled figure.
        expected = citation_fine(WORK_ZONE_BARRELS_FINE, 0, construction_zone=True)
        assert expected == pytest.approx(WORK_ZONE_BARRELS_FINE * 2.0)
        assert p.money == pytest.approx(before_money - expected)
        assert d.ticket_fines_paid == pytest.approx(expected)
        assert len(record.serious_violations) == before_serious + 1
    finally:
        app.shutdown()


def test_the_barrel_citation_says_the_charged_figure_and_why(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.enforcement import WORK_ZONE_BARRELS_FINE, citation_fine

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _rolling(d, 55.0)
        _run_into_the_barrels(d, Zone(5.0, 9.0, 45.0, "construction", closed_lane=1))

        expected = citation_fine(WORK_ZONE_BARRELS_FINE, 0, construction_zone=True)
        cited = [s for s in spoken if "through the barrels is a citation" in s]
        assert cited
        assert f"{expected:,.0f} dollars" in cited[0]
        assert f"{WORK_ZONE_BARRELS_FINE:,.0f} dollars" not in cited[0]
        assert "doubled" in cited[0] and "construction zone" in cited[0]
    finally:
        app.shutdown()


def test_the_barrel_citation_escalates_for_a_repeat_offender(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.enforcement import WORK_ZONE_BARRELS_FINE, citation_fine

    app = App()
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub())
        _rolling(d, 55.0)
        p = app.ctx.profile
        p.driving_record.citations = 2
        before_money = p.money

        _run_into_the_barrels(d, Zone(5.0, 9.0, 45.0, "construction", closed_lane=1))

        # Base x (1 + 0.5 x 2 priors) x 2 for the zone: compounded, not added.
        expected = citation_fine(WORK_ZONE_BARRELS_FINE, 2, construction_zone=True)
        assert expected == pytest.approx(WORK_ZONE_BARRELS_FINE * 2.0 * 2.0)
        assert p.money == pytest.approx(before_money - expected)
    finally:
        app.shutdown()


def test_the_barrel_fine_is_charged_once_per_work_zone(monkeypatch):
    """Two strikes in one closure is one refusal to merge, so one citation --
    the tester's log caught the barrels twice in eight seconds."""
    from freight_fate.app import App
    from freight_fate.models.enforcement import WORK_ZONE_BARRELS_FINE, citation_fine

    app = App()
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub())
        _rolling(d, 55.0)
        p = app.ctx.profile
        before_money = p.money
        zone = Zone(5.0, 9.0, 45.0, "construction", closed_lane=1)

        _run_into_the_barrels(d, zone)
        damage_after_one = d.truck.damage_pct
        d.trip.zones.remove(zone)
        _run_into_the_barrels(d, zone)

        expected = citation_fine(WORK_ZONE_BARRELS_FINE, 0, construction_zone=True)
        assert p.money == pytest.approx(before_money - expected)
        assert d.truck.damage_pct > damage_after_one  # the truck still pays
    finally:
        app.shutdown()


def test_no_open_lane_means_no_fine(monkeypatch):
    """The bug charging for itself would be worse than the bug: a driver with
    nowhere to merge must not lose a dollar."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub())
        _rolling(d, 55.0)
        p = app.ctx.profile
        record = p.driving_record
        before_money = p.money
        before_serious = len(record.serious_violations)
        d.trip.position_mi = 6.0
        d.trip.zones.append(Zone(5.0, 9.0, 45.0, "construction", closed_lane=0))
        d.lane.set_lane_count(1)

        for _ in range(400):
            d._update_merge(0.1)
        # Even reached directly, the citation refuses to write itself.
        d._cite_barrel_strike(d.trip.zones[-1])

        assert p.money == pytest.approx(before_money)
        assert d.ticket_fines_paid == pytest.approx(0.0)
        assert len(record.serious_violations) == before_serious
    finally:
        app.shutdown()


def test_tap_change_refuses_the_closed_lane():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d, 55.0)
        d.trip.position_mi = 6.0
        d.trip.zones.append(Zone(5.0, 9.0, 45.0, "construction", closed_lane=1))
        d._tap_lane_change(1)
        assert d._lane_change_target is None
        assert d.lane.lane == 0
    finally:
        app.shutdown()


# -- Tap lane changes (steering assist off) ----------------------------------------


def test_tap_lane_change_completes_after_the_timed_drift():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d)
        assert d.lane.lane == 0
        d._tap_lane_change(1)
        assert d._lane_change_target == 1
        assert d.lane.lane == 0  # not there yet
        for _ in range(40):
            d._update_tap_lane_change(0.1)
        assert d.lane.lane == 1
        assert d._lane_change_target is None
    finally:
        app.shutdown()


def test_tap_lane_change_needs_speed_and_a_real_lane():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d._tap_lane_change(1)  # engine off, parked
        assert d._lane_change_target is None
        _rolling(d)
        d._tap_lane_change(-1)  # already in the right lane
        assert d._lane_change_target is None
    finally:
        app.shutdown()


def test_asking_for_a_lane_the_road_does_not_have_names_that_side(monkeypatch):
    """Answering "you are already in the right lane" to someone asking to go
    left tells them nothing about why they cannot."""
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        _rolling(d)
        d.lane.set_lane_count(1)

        d._tap_lane_change(1)
        assert d._lane_change_target is None
        assert spoken == ["There is no lane to your left here."]

        spoken.clear()
        d._tap_lane_change(-1)
        assert spoken == ["There is no lane to your right here."]
    finally:
        app.shutdown()


# -- Hazard dodges and sideswipes ---------------------------------------------------


def test_changing_lanes_dodges_a_dodgeable_hazard():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d)
        d._hazard_deadline = 5.0
        d._hazard_dodgeable = True
        d._hazard_lane = 0
        d.lane.lane = 1  # the change just landed
        d._finish_lane_change()
        assert d._hazard_deadline is None
    finally:
        app.shutdown()


def test_a_brake_only_hazard_cannot_be_dodged():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d)
        d._hazard_deadline = 5.0
        d._hazard_dodgeable = False
        d._hazard_lane = 0
        d.lane.lane = 1
        d._finish_lane_change()
        assert d._hazard_deadline is not None
    finally:
        app.shutdown()


def test_swerving_into_occupied_space_is_a_sideswipe():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d)
        d._hazard_deadline = 5.0
        d._hazard_dodgeable = True
        d._hazard_lane = 0
        d.trip.traffic_manager.vehicles = [_npc(d.trip.position_mi + 0.1, lane=1)]
        before = d.truck.damage_pct
        d.lane.lane = 1
        d._finish_lane_change()
        assert d.truck.damage_pct > before
        assert d._hazard_deadline is not None  # the hazard is still coming
    finally:
        app.shutdown()


def test_hazard_event_records_dodge_context():
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    try:
        d = _driving(app)
        _rolling(d)
        d._handle_trip_event(
            TripEvent(
                TripEventKind.HAZARD,
                "Brake or change lanes! Debris on the road.",
                {"deadline_s": 4.0, "dodgeable": True},
            )
        )
        assert d._hazard_deadline is not None
        assert d._hazard_dodgeable is True
        assert d._hazard_lane == d.lane.lane
    finally:
        app.shutdown()


# -- Keep right except to pass ------------------------------------------------------


def test_camping_the_left_lane_draws_a_cb_nag():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d)
        d.lane.lane = 1
        for _ in range(50):
            d._update_keep_right(1.0)
        assert d._keep_right_nags == 1
        # Dropping back right resets the pressure.
        d.lane.lane = 0
        d._update_keep_right(1.0)
        assert d._keep_right_nags == 0
        assert d._left_lane_s == 0.0
    finally:
        app.shutdown()


def test_left_lane_is_fine_while_passing():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d, 60.0)
        d.lane.lane = 1
        # Slower traffic in the right lane just ahead: a legitimate pass.
        d.trip.traffic_manager.vehicles = [_npc(d.trip.position_mi + 0.3, lane=0, speed_mph=45.0)]
        for _ in range(50):
            d._update_keep_right(1.0)
        assert d._keep_right_nags == 0
    finally:
        app.shutdown()


def test_left_lane_is_fine_when_the_right_lane_is_coned_off():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d, 50.0)
        d.trip.position_mi = 6.0
        d.trip.zones.append(Zone(5.0, 9.0, 45.0, "construction", closed_lane=0))
        d.lane.lane = 1
        for _ in range(50):
            d._update_keep_right(1.0)
        assert d._keep_right_nags == 0
    finally:
        app.shutdown()


# -- Exits leave from the right lane -------------------------------------------------


def test_exit_readiness_requires_the_right_lane():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d._exit_lane_alignment = 1.0  # fully aligned in-lane
        assert d._exit_lane_ready()
        d.lane.lane = 1
        assert not d._exit_lane_ready()
        d._lane_change_target = 0  # already moving back right at the gore
        assert d._exit_lane_ready()
    finally:
        app.shutdown()


def test_snapshot_round_trips_the_lane_index():
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        d.lane.lane = 1
        snap = d.snapshot()
        assert snap["lane_index"] == 1
    finally:
        app.shutdown()
