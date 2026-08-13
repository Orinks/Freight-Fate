"""Real-seconds breathing gaps for the routine road talkers.

Owner report 2026-08-13: in every driving mode the routine events -- limit
changes, traffic calls, zone chatter -- arrive back to back, because time
compression spends road 10-40x faster than a real cab and each system
announces on road distance. The owner kept the clock (career pacing is
balanced on it) and chose to space the ANNOUNCEMENTS in real seconds, the
same law the corner warnings already follow. Mechanics are untouched:
limits still bind, cruise still follows; only the narration breathes.
"""

import pytest

from freight_fate.sim import Trip, TruckState, WeatherSystem
from freight_fate.sim.road_event_pacing import (
    LIMIT_GAP_REAL_S,
    TRAFFIC_GAP_REAL_S,
    ZONE_GAP_REAL_S,
    RoadEventBreather,
)
from freight_fate.sim.trip import TripEventKind


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_first_line_of_a_category_is_always_ready():
    b = RoadEventBreather(clock=FakeClock())
    assert b.ready("limit")
    assert b.ready("traffic")
    assert b.ready("zone")


def test_speaking_closes_the_window_for_the_gap():
    clock = FakeClock()
    b = RoadEventBreather(clock=clock)
    b.spoke("limit")
    clock.now += LIMIT_GAP_REAL_S - 0.5
    assert not b.ready("limit")
    clock.now += 1.0
    assert b.ready("limit")


def test_categories_are_independent():
    clock = FakeClock()
    b = RoadEventBreather(clock=clock)
    b.spoke("limit")
    assert b.ready("traffic")
    assert b.ready("zone")


def test_ready_never_consumes():
    b = RoadEventBreather(clock=FakeClock())
    assert b.ready("limit")
    assert b.ready("limit")  # polling twice is not speaking twice


def test_gap_constants_are_real_seconds_apart():
    # The gaps are the design's numbers; a drive-by refactor that halves
    # them silently reintroduces the chatter this exists to kill.
    assert pytest.approx(12.0) == LIMIT_GAP_REAL_S
    assert pytest.approx(10.0) == TRAFFIC_GAP_REAL_S
    assert pytest.approx(15.0) == ZONE_GAP_REAL_S


# --- Trip._check_speed_limit gating (Task 2) --------------------------------
#
# Trip wires the same RoadEventBreather (category "limit") into its posted-
# limit arrival line. These tests drive _check_speed_limit directly, the
# same way tests/test_weather_trip.py's speed-limit tests do, and control
# the breather's clock with the FakeClock above instead of the real one.


def _make_trip(world, start="Chicago", end="Indianapolis", seed=2):
    route = world.route_options(start, end)[0]
    truck = TruckState()
    truck.transmission.automatic = True
    truck.start_engine()
    weather = WeatherSystem("great_lakes", seed=1)
    trip = Trip(route, truck, weather, seed=seed)
    trip.traffic_manager.rolling_bubble = False
    trip._active_zone = None
    return trip


def _limit_messages(trip):
    return [e.message for e in trip._events if e.kind == TripEventKind.GPS_CUE]


def _install_fake_clock(trip, monkeypatch):
    """Wire a FakeClock into trip._event_breather -- a no-op before Task 2's
    __init__ change lands, so these tests are collectible (and the urgent
    test can pass "by accident") even against pre-gate code."""
    clock = FakeClock()
    if hasattr(trip, "_event_breather"):
        monkeypatch.setattr(trip._event_breather, "_clock", clock)
    return clock


def test_two_limit_changes_inside_the_gap_speak_once_with_the_newest(world, monkeypatch):
    trip = _make_trip(world)
    clock = _install_fake_clock(trip, monkeypatch)

    # First posting change: the window is open (nothing spoken yet), so it
    # speaks immediately.
    trip._announced_speed_limit = 55.0
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 60.0)
    trip._events.clear()
    trip._check_speed_limit()
    first = _limit_messages(trip)
    assert len(first) == 1
    assert "raised to" in first[0]

    # A second change 3 real seconds later is well inside LIMIT_GAP_REAL_S:
    # gated. It must not speak, and the gate leaves _announced_speed_limit
    # untouched so the miss is total, not a partial commit.
    clock.now += 3.0
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 65.0)
    trip._events.clear()
    trip._check_speed_limit()
    assert _limit_messages(trip) == []
    assert trip._announced_speed_limit == 60.0

    # Once the window reopens, the next check announces the CURRENT posting
    # (65) directly -- the missed 65 is never separately spoken as a
    # follow-up to the (also unspoken) intermediate state.
    clock.now += LIMIT_GAP_REAL_S
    trip._events.clear()
    trip._check_speed_limit()
    reopened = _limit_messages(trip)
    assert len(reopened) == 1
    assert "raised to" in reopened[0]
    assert trip._speed_value(65.0) in reopened[0]
    assert trip._speed_value(60.0) not in reopened[0]


def test_a_limit_bounce_inside_the_gap_never_speaks(world, monkeypatch):
    trip = _make_trip(world)
    clock = _install_fake_clock(trip, monkeypatch)
    trip.position_mi = 0.0

    # A drop small enough to stay routine (not the >10 mph urgent exemption).
    trip._announced_speed_limit = 55.0
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 45.0)
    trip._events.clear()
    trip._check_speed_limit()
    assert len(_limit_messages(trip)) == 1

    # Within the gap the posting bounces straight back up -- the owner's
    # "dropping and coming straight back" complaint. Gated: nothing new
    # spoken, and _announced_speed_limit stays at 45 (untouched).
    clock.now += 3.0
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 55.0)
    trip._events.clear()
    trip._check_speed_limit()
    assert _limit_messages(trip) == []
    assert trip._announced_speed_limit == 45.0

    # By the time the window opens, the reading has settled back to exactly
    # what was last spoken (45): current == last spoken, so the "if limit !=
    # announced" branch never triggers and nothing is said -- the bounce
    # stays fully dead, not merely delayed.
    clock.now += LIMIT_GAP_REAL_S
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 45.0)
    trip._events.clear()
    trip._check_speed_limit()
    assert _limit_messages(trip) == []
    assert trip._announced_speed_limit == 45.0


def test_a_big_unannounced_drop_cuts_the_gap(world, monkeypatch):
    trip = _make_trip(world)
    clock = _install_fake_clock(trip, monkeypatch)
    trip.position_mi = 0.0

    # A routine change speaks and closes the window.
    trip._announced_speed_limit = 70.0
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 65.0)
    trip._events.clear()
    trip._check_speed_limit()
    assert len(_limit_messages(trip)) == 1

    # 2 seconds later -- well inside LIMIT_GAP_REAL_S -- a serious,
    # never-preannounced drop (65 -> 45, a 20 mph cut) must cut the line: it
    # is ticket-relevant now, not something that can wait for the window.
    clock.now += 2.0
    monkeypatch.setattr(trip, "_corridor_limit_at", lambda mile: 45.0)
    trip._events.clear()
    trip._check_speed_limit()
    urgent = _limit_messages(trip)
    assert len(urgent) == 1
    assert "reduced to" in urgent[0]
    assert trip._speed_value(45.0) in urgent[0]
    assert trip._announced_speed_limit == 45.0
