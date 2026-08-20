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


def test_a_single_lane_road_has_no_side_to_name():
    """ "The right lane" on a one-lane road invites the driver to wonder what
    is in the left one, when there is no left one (Cary, 2026-08-15)."""
    from freight_fate.sim.lane import lane_phrase

    lane = LaneKeeping(seed=1)
    lane.set_lane_count(1)
    lane.offset = 0.0
    assert lane.describe() == "In the lane, centered."
    lane.offset = -0.5
    assert lane.describe() == "In the lane, drifting left."
    assert lane_phrase(0, 1) == "the lane"
    # Two lanes and up still name the side, which is the whole point there.
    assert lane_phrase(0, 2) == "the right lane"


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
    assert hazard_is_dodgeable("a mattress lying in the lane")
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
        assert "left lane is closed; keep right" in trip._zone_entry_message(closed_left)
        assert "right lane is closed; keep left" in trip._zone_entry_message(closed_right)
    finally:
        app.shutdown()


def test_the_side_announced_is_the_side_that_is_shut():
    """Shane's report: told the right lane was closed, then found the closure
    on the other side. The zone stores a side, so the lane the callouts name
    and the lane the game shuts are one fact -- on a three-wide road too,
    where a bare index of 1 used to be the middle lane while every line
    called it the left one."""
    from freight_fate.data.world_models import LaneSegment

    trip = _synthetic_trip([LaneSegment(0.0, 900.0, lanes=3, oneway=True)], 900.0, 7)
    assert trip.lane_count_at(100.0) == 3
    for side, expected in (("right", 0), ("left", 2)):
        zone = Zone(90.0, 120.0, 45.0, "construction", closed_side=side)
        trip.zones = [zone]
        shut, keep = trip._closure_phrases(zone)
        assert shut == side
        assert keep != side
        index = trip.closed_lane_at(100.0)
        assert index == expected
        # What the player is told, and which lane the game shuts, agree.
        assert lane_label(index, 3) == shut
        assert f"The {shut} lane is closed" in trip._zone_warning_message(zone, 2.0)
        assert f"keep {keep}" in trip._zone_entry_message(zone)


def test_a_closure_keeps_its_side_where_the_road_widens():
    """A stored lane index means a different lane at either end of one work
    zone; the side does not."""
    from freight_fate.data.world_models import LaneSegment

    trip = _synthetic_trip(
        [
            LaneSegment(0.0, 100.0, lanes=2, oneway=True),
            LaneSegment(100.0, 900.0, lanes=3, oneway=True),
        ],
        900.0,
        11,
    )
    zone = Zone(90.0, 120.0, 45.0, "construction", closed_side="left")
    trip.zones = [zone]
    assert trip.closed_lane_at(95.0) == 1  # left of two
    assert trip.closed_lane_at(110.0) == 2  # still the left one, of three
    assert lane_label(trip.closed_lane_at(95.0), 2) == "left"
    assert lane_label(trip.closed_lane_at(110.0), 3) == "left"


def test_a_jam_over_the_work_zone_cannot_hide_the_closure():
    """``active_zone`` answers with the slowest zone at the mile, so a jam
    laid over the roadwork used to leave the closure unenforced and unspoken
    while the warning had already named it."""
    from freight_fate.data.world_models import LaneSegment

    trip = _synthetic_trip([LaneSegment(0.0, 900.0, lanes=2, oneway=True)], 900.0, 5)
    work = Zone(90.0, 120.0, 45.0, "construction", closed_side="right")
    jam = Zone(80.0, 130.0, 25.0, "heavy traffic")
    trip.zones = [work, jam]
    trip.position_mi = 100.0
    assert trip.active_zone is jam  # the slower of the two
    assert trip.active_closure() is work
    assert trip.closed_lane_at() == 0


def test_a_closure_always_leaves_somewhere_to_go():
    """The never-stuck invariant: wherever a lane is shut, another lane on our
    side is open at that same mile."""
    from freight_fate.data.world_models import LaneSegment

    segments = [
        LaneSegment(0.0, 300.0, lanes=2, oneway=True),
        LaneSegment(300.0, 600.0, lanes=3, oneway=True),
        LaneSegment(600.0, 900.0, lanes=2, oneway=True),
    ]
    checked = 0
    for seed in range(25):
        trip = _synthetic_trip(segments, 900.0, seed)
        for start, end in _closure_footprints(trip):
            mile = start
            while mile <= end:
                count = trip.lane_count_at(mile)
                closed = trip.closed_lane_at(mile)
                if closed is not None:
                    checked += 1
                    assert count >= 2
                    assert 0 <= closed < count
                    assert closed in (0, count - 1)  # never the middle lane
                    assert any(lane != closed for lane in range(count))
                mile += 0.25
    assert checked  # the sweep actually saw closures


def test_has_open_adjacent_lane_at_reads_lane_count_and_closures():
    """The one authority a hazard warning's wording answers to: the same
    lane count a lane change is refused against, and the same work-zone
    closure ``closed_lane_at`` already reads."""
    from freight_fate.data.world_models import LaneSegment

    one_lane = _synthetic_trip([LaneSegment(0.0, 900.0, lanes=2, oneway=False)], 900.0, 1)
    assert not one_lane.has_open_adjacent_lane_at(100.0)  # nowhere on this side at all

    two_lane = _synthetic_trip([LaneSegment(0.0, 900.0, lanes=2, oneway=True)], 900.0, 2)
    assert two_lane.has_open_adjacent_lane_at(100.0)

    # The only other lane on a two-lane road, coned off: no escape either.
    two_lane.zones = [Zone(90.0, 120.0, 45.0, "construction", closed_side="right")]
    assert not two_lane.has_open_adjacent_lane_at(100.0)

    # A third lane still leaves somewhere to go once one is closed.
    three_lane = _synthetic_trip([LaneSegment(0.0, 900.0, lanes=3, oneway=True)], 900.0, 3)
    three_lane.zones = [Zone(90.0, 120.0, 45.0, "construction", closed_side="right")]
    assert three_lane.has_open_adjacent_lane_at(100.0)


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

        # NOT doubled for the zone: the base is already the roadwork penalty
        # (RSMo 304.585), so doubling would charge twice for the same fact.
        expected = citation_fine(WORK_ZONE_BARRELS_FINE, 0)
        assert expected == pytest.approx(WORK_ZONE_BARRELS_FINE)
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

        expected = citation_fine(WORK_ZONE_BARRELS_FINE, 0)
        cited = [s for s in spoken if "through the barrels is a citation" in s]
        assert cited
        assert f"{expected:,.0f} dollars" in cited[0]
        # It must NOT claim a doubling it did not apply.
        assert "doubled" not in cited[0]
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

        # Priors still escalate it, up to the repeat cap; the zone does not.
        expected = citation_fine(WORK_ZONE_BARRELS_FINE, 2)
        assert expected == pytest.approx(WORK_ZONE_BARRELS_FINE * 2.0)
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

        expected = citation_fine(WORK_ZONE_BARRELS_FINE, 0)
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


def test_a_narrowing_road_never_leaves_the_truck_in_the_closed_lane(monkeypatch):
    """The other half of Shane's trap. He was told the right lane was closed
    and moved left; where the road drops a lane the count clamp renumbers the
    lanes under the truck, and the lane he had moved into became the closed
    one. The road moved him, so the road moves him back out -- no barrels, no
    citation, and he is told what happened."""
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _rolling(d, 55.0)
        d.trip.position_mi = 6.0
        d.trip.zones.append(Zone(5.0, 9.0, 45.0, "construction", closed_side="left"))
        d.lane.set_lane_count(3)
        d.lane.lane = 1  # the middle lane, open: the left one is coned off
        d._leave_a_lane_the_road_closed()  # seed the lane count it has seen
        before = d.truck.damage_pct

        d.lane.set_lane_count(2)  # the road drops a lane under the truck
        assert d.trip.closed_lane_at(lane_count=2) == 1  # which is where it now is
        d._leave_a_lane_the_road_closed()

        assert d.lane.lane == 0
        assert d._merge_deadline is None
        assert d.truck.damage_pct == pytest.approx(before)
        assert spoken and "left lane is closed" in spoken[-1]
        assert "right lane" in spoken[-1]
    finally:
        app.shutdown()


def test_a_narrowing_road_with_no_closure_says_the_forced_move(monkeypatch):
    """Darren's report, 2026-08-14: a highway narrowing to one lane with no
    work zone at all moved the truck without a word -- LaneKeeping.set_lane_
    count clamps the lane index silently. This is the same forced-move trap
    as the closure case above, minus the cones, so it gets the same
    never-dropped treatment (interrupt=True, the closure call's own
    mechanism)."""
    from freight_fate.app import App

    app = App()
    calls: list[tuple[str, bool]] = []
    try:
        d = _driving(app)
        app.ctx.speech.say_event = speech_stub(calls, with_interrupt=True)
        _rolling(d, 55.0)
        d.lane.set_lane_count(2)
        d.lane.lane = 1  # the left lane, which is about to stop existing
        d._leave_a_lane_the_road_closed()  # seed the lane count it has seen

        d._lane_before_narrow = d.lane.lane  # what _update_lane captures pre-clamp
        d.lane.set_lane_count(1)  # the road itself narrows to one lane
        d._leave_a_lane_the_road_closed()

        assert d.lane.lane == 0
        assert len(calls) == 1
        text, interrupt = calls[0]
        assert "road narrows to one lane" in text
        # Narrowing to ONE lane already tells the driver which lane they are
        # in, so the line no longer names a side that does not exist any more
        # (Cary, 2026-08-15) -- it just says they were moved.
        assert "You are moved over." in text
        assert "right lane" not in text
        assert interrupt is True  # never-dropped, same family as the closure call
        assert text in [m.text for m in app.ctx.message_log.messages]
    finally:
        app.shutdown()


def test_a_narrowing_road_stays_silent_when_the_truck_already_survives(monkeypatch):
    """The clamp only moves a truck sitting in a lane that stops existing.
    Already in the lane that survives the narrowing, nothing was forced and
    nothing needs saying."""
    from freight_fate.app import App

    app = App()
    calls: list[tuple[str, bool]] = []
    try:
        d = _driving(app)
        app.ctx.speech.say_event = speech_stub(calls, with_interrupt=True)
        _rolling(d, 55.0)
        d.lane.set_lane_count(2)
        d.lane.lane = 0  # already in the right lane, which survives
        d._leave_a_lane_the_road_closed()  # seed the lane count it has seen
        before_log = len(app.ctx.message_log.messages)

        d._lane_before_narrow = d.lane.lane
        d.lane.set_lane_count(1)  # the road narrows, but the truck never moves
        d._leave_a_lane_the_road_closed()

        assert d.lane.lane == 0
        assert calls == []
        assert len(app.ctx.message_log.messages) == before_log
    finally:
        app.shutdown()


def test_a_lane_the_driver_steered_into_is_still_theirs_to_answer_for(monkeypatch):
    """The rescue above must not become a free pass: with the road unchanged,
    riding the cones still earns the warning and the barrels."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub())
        _rolling(d, 55.0)
        d.trip.position_mi = 6.0
        d.trip.zones.append(Zone(5.0, 9.0, 45.0, "construction", closed_side="left"))
        d._leave_a_lane_the_road_closed()
        d.lane.lane = 1  # steered into the closed lane

        d._leave_a_lane_the_road_closed()
        assert d.lane.lane == 1  # nothing moved under the truck

        d._update_merge(0.1)
        assert d._merge_deadline is not None
    finally:
        app.shutdown()


def test_a_tap_change_refuses_a_lane_that_closed_on_the_way_over(monkeypatch):
    """A lane change takes seconds; the cones can arrive inside them. The
    completion used to commit the move whatever had happened meanwhile."""
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _rolling(d, 55.0)
        d.trip.position_mi = 6.0
        d._tap_lane_change(1)
        assert d._lane_change_target == 1

        # The work zone starts under the truck while the change is running.
        d.trip.zones.append(Zone(5.0, 9.0, 45.0, "construction", closed_side="left"))
        for _ in range(40):
            d._update_tap_lane_change(0.1)

        assert d.lane.lane == 0
        assert d._lane_change_target is None
        assert spoken and "left lane is closed" in spoken[-1]
    finally:
        app.shutdown()


def test_the_taper_warns_a_truck_in_the_lane_that_is_closing(monkeypatch):
    """The merge taper is where the closure starts. Riding it used to be
    silent all the way to the first barrel."""
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
        _rolling(d, 55.0)
        d.trip.position_mi = 4.5
        d.trip.zones.append(Zone(4.0, 5.0, 55.0, "construction merge", closed_side="left"))
        d.lane.lane = 1  # riding the lane that closes at the barrels
        before = d.truck.damage_pct

        for _ in range(200):
            d._update_merge(0.1)

        assert spoken and "closes at the work zone ahead" in spoken[0]
        assert len([s for s in spoken if "closes at the work zone" in s]) == 1
        assert d._merge_deadline is None  # the barrel clock belongs to the work zone
        assert d.truck.damage_pct == pytest.approx(before)
    finally:
        app.shutdown()


def test_the_taper_refuses_a_move_into_the_lane_that_is_closing(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken: list[str] = []
    try:
        d = _driving(app)
        monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
        _rolling(d, 55.0)
        d.trip.position_mi = 4.5
        d.trip.zones.append(Zone(4.0, 5.0, 55.0, "construction merge", closed_side="left"))

        d._tap_lane_change(1)
        assert d._lane_change_target is None
        assert d.lane.lane == 0
        assert spoken == ["The left lane closes at the work zone ahead."]
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


def test_one_contact_is_billed_and_announced_once():
    """Pinballing across the same line is one sideswipe, not three.

    Tester transcript, 2026-08-11: "You sideswiped a box truck in the right
    lane! The truck took damage, now 13 percent." three times inside six
    tenths of a second, for one brush against one vehicle -- and the damage
    charged three times with it.
    """
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d)
        spoken: list[str] = []
        d.ctx.say_event = lambda text, *a, **k: spoken.append(text)
        d.trip.traffic_manager.vehicles = [_npc(d.trip.position_mi + 0.1, lane=1)]
        d.lane.lane = 1
        d._finish_lane_change()
        after_first = d.truck.damage_pct
        # The tires roll the markers again as the truck settles back over.
        d._finish_lane_change()
        d._finish_lane_change()
        assert len(spoken) == 1
        assert d.truck.damage_pct == after_first
    finally:
        app.shutdown()


def test_a_later_sideswipe_is_its_own_contact():
    """The guard is a cooldown, not a once-per-trip latch."""
    from freight_fate.app import App

    app = App()
    try:
        d = _driving(app)
        _rolling(d)
        spoken: list[str] = []
        d.ctx.say_event = lambda text, *a, **k: spoken.append(text)
        d.trip.traffic_manager.vehicles = [_npc(d.trip.position_mi + 0.1, lane=1)]
        d.lane.lane = 1
        d._finish_lane_change()
        d._sideswipe_cooldown_s = 0.0  # seconds later, moving over again
        d._finish_lane_change()
        assert len(spoken) == 2
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
                "Change lanes or brake! Debris on the road.",
                {"deadline_s": 4.0, "dodgeable": True},
            )
        )
        assert d._hazard_deadline is not None
        assert d._hazard_dodgeable is True
        assert d._hazard_lane == d.lane.lane
    finally:
        app.shutdown()


# -- Hazard wording must not offer a lane change nobody can make -------------------


def test_traffic_pressure_hazard_says_brake_only_with_no_lane_to_swerve_into():
    """Manual playtest, US-285 toward Denver, 2026-08-12: one lane your
    side, and the lead-vehicle warning still said "Change lanes or brake!"
    -- an escape the road never offered. The lead-vehicle branch must ask
    the same lane authority a real lane change answers to."""
    from freight_fate.data.world_models import LaneSegment
    from freight_fate.sim.trip import TripEventKind
    from freight_fate.sim.trip_models import TrafficContext

    trip = _synthetic_trip([LaneSegment(0.0, 900.0, lanes=2, oneway=False)], 900.0, 3)
    trip.position_mi = 50.0
    trip._traffic_warning_mi = 0.0
    lead = _npc(50.05, lane=0, speed_mph=30.0)
    lead.intent = "braking"
    trip.traffic_context = lambda: TrafficContext(lead=lead, gap_mi=0.01, closing_mph=20.0)

    trip._check_hazards(1.0)

    events = [e for e in trip._events if e.kind == TripEventKind.HAZARD]
    assert events
    assert events[0].message == "Brake! Brake lights right ahead."
    assert "change lanes" not in events[0].message
    assert events[0].data["dodgeable"] is True  # brake alone still takes it nearly to a stop


def test_traffic_pressure_hazard_keeps_the_lane_offer_when_one_exists():
    """Same lead-vehicle warning, but on a road with somewhere to go: the
    wording is unchanged from before this fix."""
    from freight_fate.data.world_models import LaneSegment
    from freight_fate.sim.trip import TripEventKind
    from freight_fate.sim.trip_models import TrafficContext

    trip = _synthetic_trip([LaneSegment(0.0, 900.0, lanes=2, oneway=True)], 900.0, 4)
    trip.position_mi = 50.0
    trip._traffic_warning_mi = 0.0
    lead = _npc(50.05, lane=0, speed_mph=30.0)
    lead.intent = "braking"
    trip.traffic_context = lambda: TrafficContext(lead=lead, gap_mi=0.01, closing_mph=20.0)

    trip._check_hazards(1.0)

    events = [e for e in trip._events if e.kind == TripEventKind.HAZARD]
    assert events
    assert events[0].message == "Change lanes or brake! Brake lights right ahead."


def test_random_dodgeable_hazard_says_brake_only_with_no_lane_to_swerve_into(monkeypatch):
    """The fixed-object hazard family (debris, a stopped vehicle) gets the
    same treatment as the lead-vehicle warning: no lane, no offer."""
    import freight_fate.sim.trip_road_events as road_events
    from freight_fate.data.world_models import LaneSegment
    from freight_fate.sim.trip import Trip, TripEventKind

    trip = _synthetic_trip([LaneSegment(0.0, 900.0, lanes=2, oneway=False)], 900.0, 9)
    trip.position_mi = 50.0
    trip._hazard_check_mi = 0.0
    # The synthetic route's cities are not in the world, so the region lookup
    # _check_hazards makes on the way to eligible_hazards (stubbed below)
    # cannot resolve; pin a real region name.
    monkeypatch.setattr(Trip, "current_region", property(lambda self: "great_lakes"))
    monkeypatch.setattr(trip, "_hazard_risk", lambda: 2.0)  # certain to fire
    monkeypatch.setattr(
        road_events, "eligible_hazards", lambda *a, **k: [("debris on the road", 1.0)]
    )

    trip._check_hazards(0.0)

    events = [e for e in trip._events if e.kind == TripEventKind.HAZARD]
    assert events
    assert events[0].message == "Brake! Debris on the road."
    assert events[0].data["dodgeable"] is True


def test_hazard_hint_and_clearing_need_no_lane_when_there_is_none():
    """One lane your side: the lingering hint must not offer a lane change,
    and a lane-change refusal must never be required to clear the hazard --
    slowing alone, with no lane change ever attempted, still resolves it and
    earns the achievement."""
    from freight_fate.app import App
    from freight_fate.states.driving import HAZARD_CREEP_MPH, HAZARD_SAFE_MPH, MPH_PER_MPS

    app = App()
    spoken: list[str] = []
    awarded: list[str] = []
    try:
        d = _driving(app)
        d.ctx.say_event = lambda text, *a, **k: spoken.append(text)
        d.ctx.award_achievement = lambda key, **k: awarded.append(key)
        _rolling(d, 65.0)
        d.trip.has_open_adjacent_lane_at = lambda mile=None: False
        d._hazard_deadline = 5.0
        d._hazard_dodgeable = True
        d._hazard_lane = d.lane.lane
        d._hazard_slow_hint_said = False
        d._automatic_braking_announced = False

        # Slow past the old moving-hazard speed: the hint fires once, and
        # never names a lane change.
        d.truck.velocity_mps = (HAZARD_SAFE_MPH - 1.0) / MPH_PER_MPS
        d._update_hazard(1 / 60)
        assert spoken.count("It is still in your lane. Nearly stop.") == 1
        assert not any("change lanes" in text for text in spoken)

        # Never changed lanes: nearly stopping alone still clears it.
        d.truck.velocity_mps = (HAZARD_CREEP_MPH - 1.0) / MPH_PER_MPS
        d._update_hazard(1 / 60)
        assert d._hazard_deadline is None
        assert "hazard_avoided" in awarded
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
