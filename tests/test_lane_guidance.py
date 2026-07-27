"""The lane-guidance director: silent when centered, awake for drift or curves."""

import pytest

from freight_fate.sim.lane import LaneKeeping
from freight_fate.sim.lane_guidance import (
    BED_MAX_VOLUME,
    CURVE_FLOOR_VOLUME,
    CURVE_LEAD_MI,
    DRIFT_SLEEP,
    DRIFT_WAKE,
    LaneGuidance,
    classify_boundaries,
)


def _lane(offset: float = 0.0) -> LaneKeeping:
    lane = LaneKeeping(seed=1)
    lane.offset = offset
    return lane


def _frame(g, lane, *, curve_active=False, curve_ahead_mi=None, assist_on=True):
    return g.update(
        lane, assist_on=assist_on, curve_active=curve_active, curve_ahead_mi=curve_ahead_mi
    )


def test_centered_straight_is_silent():
    g = LaneGuidance()
    frame = _frame(g, _lane(0.0))
    assert not frame.awake
    assert frame.volume == 0.0


def test_drift_wakes_and_hysteresis_holds():
    g = LaneGuidance()
    assert not _frame(g, _lane(DRIFT_WAKE - 0.05)).awake
    assert _frame(g, _lane(DRIFT_WAKE + 0.05)).awake
    # Back inside the wake line but above the sleep line: still awake.
    assert _frame(g, _lane(DRIFT_SLEEP + 0.05)).awake
    assert not _frame(g, _lane(DRIFT_SLEEP - 0.05)).awake


def test_sleep_after_drift_flags_the_centered_earcon():
    g = LaneGuidance()
    _frame(g, _lane(0.7))
    frame = _frame(g, _lane(0.05))
    assert not frame.awake
    assert frame.centered
    # A curve-only episode ends without the earcon: nothing drifted.
    _frame(g, _lane(0.0), curve_active=True)
    frame = _frame(g, _lane(0.0))
    assert not frame.centered


def test_curve_wakes_the_bed_even_centered():
    g = LaneGuidance()
    frame = _frame(g, _lane(0.0), curve_active=True)
    assert frame.awake
    assert frame.volume == pytest.approx(CURVE_FLOOR_VOLUME)
    assert frame.pan == pytest.approx(0.0)


def test_upcoming_curve_arms_inside_the_lead_window():
    g = LaneGuidance()
    assert not _frame(g, _lane(0.0), curve_ahead_mi=CURVE_LEAD_MI * 2).awake
    assert _frame(g, _lane(0.0), curve_ahead_mi=CURVE_LEAD_MI * 0.5).awake


def test_volume_grows_toward_the_line_and_pan_tracks_side():
    g = LaneGuidance()
    near = _frame(g, _lane(0.5))
    far = _frame(g, _lane(0.95))
    assert far.volume > near.volume
    assert far.volume <= BED_MAX_VOLUME
    left = _frame(g, _lane(-0.8))
    assert left.pan < 0.0 < far.pan


def test_assist_off_is_inert():
    g = LaneGuidance()
    frame = _frame(g, _lane(0.9), curve_active=True, assist_on=False)
    assert not frame.awake


def test_boundaries_divided_and_undivided():
    # Rightmost lane of a divided 3-lane: another lane left, shoulder right.
    assert classify_boundaries(0, 3, divided=True, interstate=True) == ("lane", "shoulder")
    # Leftmost lane of the same road: the median is past the left line.
    assert classify_boundaries(2, 3, divided=True, interstate=True) == ("median", "lane")
    # Undivided two-lane: the left line is the centerline with oncoming.
    assert classify_boundaries(0, 1, divided=False, interstate=False) == (
        "oncoming",
        "shoulder",
    )
    # No baked flag: interstates infer divided...
    assert classify_boundaries(1, 2, divided=None, interstate=True) == ("median", "lane")
    # ...and a one-lane-per-side road infers the centerline.
    assert classify_boundaries(0, 1, divided=None, interstate=False) == (
        "oncoming",
        "shoulder",
    )
