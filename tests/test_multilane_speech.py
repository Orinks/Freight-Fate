"""Track D: multilane speech -- lane counts spoken from baked lane_segments.

Speech wiring only: the road status and route briefing say the lane count, and
a callout fires when the count changes mid-leg. No traffic, no lane-position
mechanics. Honest absence: legs with no baked lane data say nothing.
"""

from freight_fate.data.world_models import LaneSegment, Leg, Route
from freight_fate.sim.trip import Trip
from freight_fate.sim.vehicle import TruckState
from freight_fate.sim.weather import WeatherSystem


def _leg(a, b, miles, segs, highway="US-1"):
    return Leg(a, b, miles, highway, "flat", (), lane_segments=tuple(segs))


# -- LaneSegment.your_side ---------------------------------------------------
def test_your_side_oneway_is_the_tagged_count():
    seg = LaneSegment(0.0, 5.0, lanes=3, oneway=True)
    assert seg.your_side(forward=True) == 3
    assert seg.your_side(forward=False) == 3  # symmetric carriageway assumption
    assert seg.divided is True


def test_your_side_undivided_splits_the_total():
    seg = LaneSegment(0.0, 5.0, lanes=4, oneway=False)
    assert seg.your_side(forward=True) == 2
    assert seg.divided is False
    # a two-lane road is one lane your side, never zero
    assert LaneSegment(0.0, 1.0, lanes=2).your_side(True) == 1


def test_your_side_prefers_directional_tags():
    seg = LaneSegment(0.0, 5.0, lanes=5, lanes_forward=3, lanes_backward=2)
    assert seg.your_side(forward=True) == 3
    assert seg.your_side(forward=False) == 2


# -- Route.lane_summary (briefing) -------------------------------------------
def test_route_lane_summary_reports_dominant_and_divided():
    route = Route(
        ["a", "b"], [_leg("a", "b", 10.0, [LaneSegment(0.0, 10.0, lanes=2, oneway=True)])]
    )
    assert route.lane_summary == "mostly divided, two lanes your side"
    assert "two lanes your side" in route.describe()


def test_route_lane_summary_empty_without_data():
    route = Route(["a", "b"], [_leg("a", "b", 10.0, [])])
    assert route.lane_summary == ""
    assert "lanes your side" not in route.describe()


def test_route_lane_summary_respects_travel_direction():
    # Reversed leg (route enters at b): forward=False, directional split flips.
    seg = LaneSegment(0.0, 10.0, lanes=5, lanes_forward=3, lanes_backward=2)
    fwd = Route(["a", "b"], [_leg("a", "b", 10.0, [seg])])
    rev = Route(["b", "a"], [_leg("a", "b", 10.0, [seg])])
    assert "three lanes your side" in fwd.lane_summary
    assert "two lanes your side" in rev.lane_summary


# -- Trip: status readout ----------------------------------------------------
def _trip(cities):
    from freight_fate.data import get_world

    route = get_world().route_from_cities(cities)
    return Trip(route, TruckState(), WeatherSystem(seed=1), seed=1)


def test_status_readout_speaks_lane_count(world):
    trip = _trip(["Albuquerque", "Gallup"])
    trip.position_mi = 20.0  # rural I-40, divided two lanes
    assert trip._current_lane_text() == "divided, two lanes your side"
    assert "lanes your side" in trip.progress_summary()


def test_status_readout_silent_without_lane_data(world):
    trip = _trip(["Albuquerque", "Gallup"])
    trip.position_mi = 0.5  # leg start, before lane coverage begins
    assert trip.lanes_at() is None
    assert trip._current_lane_text() == ""


# -- Trip: mid-leg change callout --------------------------------------------
def _lane_callouts(trip, mileposts):
    out = []
    trip.position_mi = 0.0
    trip._check_lane_changes()  # seed
    for mp in mileposts:
        trip.position_mi = mp
        trip._events = []
        trip._check_lane_changes()
        out += [e.message for e in trip._events if e.kind.name == "LANE"]
    return out


def test_lane_change_callouts_widen_and_narrow(world):
    trip = _trip(["Albuquerque", "Gallup"])  # runs 4 -> 3 -> 4 -> 2
    msgs = _lane_callouts(trip, [4.0, 6.0, 11.0, 15.0, 40.0])
    assert any("widens to four lanes" in m for m in msgs)
    assert any("Down to three lanes" in m for m in msgs)
    assert any("Down to two lanes" in m for m in msgs)


def test_short_runs_collapse_no_spam(world):
    # ABQ has 0.3-0.5 mi 5-lane slivers; none should become a callout.
    trip = _trip(["Albuquerque", "Gallup"])
    msgs = _lane_callouts(trip, [p / 2.0 for p in range(0, 300)])
    assert not any("five lanes" in m for m in msgs)


def test_callouts_seeded_on_resume_do_not_replay(world):
    # Starting already past a boundary must not announce it.
    trip = _trip(["Albuquerque", "Gallup"])
    trip.position_mi = 40.0  # past every ABQ-metro change
    trip._check_lane_changes()  # seeds silently
    trip._events = []
    trip.position_mi = 45.0
    trip._check_lane_changes()
    assert not [e for e in trip._events if e.kind.name == "LANE"]


def test_synthetic_change_message_direction():
    assert Trip._lane_change_message(2, 3) == "Road widens to three lanes your side."
    assert Trip._lane_change_message(3, 1) == "Down to one lane your side."


def test_the_driver_is_never_offered_more_lanes_than_speech_can_name(world):
    """Owner, 2026-08-19: "We don't support five lane highways yet, just three."

    It is a speech limit before it is a driving one. ``lane_label`` has three
    names -- right, left, middle -- so on a road of four or more, every
    interior lane is announced as "the middle lane" and a player working by
    ear cannot tell which one they are in, nor which one just came open.

    The HPMS bake records real per-direction counts and they run to six on
    urban freeways. That record stays true; the cap is on what the DRIVER is
    offered.
    """
    from freight_fate.sim.trip_models import MAX_DRIVABLE_LANES, leg_lane_count

    assert MAX_DRIVABLE_LANES == 3

    route = world.route_from_cities(["Chicago", "Indianapolis"])
    truck = TruckState()
    weather = WeatherSystem("midwest", seed=1)
    trip = Trip(route, truck, weather, seed=2)

    for mile in range(0, int(trip.total_miles), 25):
        assert trip.lane_count_at(float(mile)) <= MAX_DRIVABLE_LANES

    # And the cap is real even when the road really does carry more.
    import dataclasses

    route.legs[0] = dataclasses.replace(route.legs[0], lanes=6, lane_segments=())
    trip = Trip(route, truck, weather, seed=2)
    assert leg_lane_count(route.legs[0]) == 6  # the record is untouched
    assert trip.lane_count_at(0.0) == MAX_DRIVABLE_LANES


def test_traffic_capacity_still_uses_the_real_lane_count(world):
    """The other half: clamping capacity too would invent jams.

    A six-lane urban freeway carrying its real volume flows. Divide that
    volume by three lanes because three is all the driver can be put in, and
    the congestion model reports stop-and-go on a road that is moving --
    which is why the cap lives in ``lane_count_at`` and not in the bake or
    in ``leg_aadt_at``.
    """
    from freight_fate.sim.trip_models import congestion_ratio

    six = congestion_ratio(250_000, 8.0, 6, False)
    three = congestion_ratio(250_000, 8.0, 3, False)
    assert three > six
    # The real count is what keeps this freeway out of the jam band.
    assert six < 1.0 < three
