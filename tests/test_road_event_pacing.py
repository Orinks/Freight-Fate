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

from freight_fate.sim.road_event_pacing import (
    LIMIT_GAP_REAL_S,
    TRAFFIC_GAP_REAL_S,
    ZONE_GAP_REAL_S,
    RoadEventBreather,
)


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
