"""The lane-guidance director: silence when centered, the road bed leaning
toward the needed steer (pursuit) for drift or bends -- never a new tone."""

import pytest

from freight_fate.sim.lane import LaneKeeping
from freight_fate.sim.lane_guidance import (
    CURVE_LEAD_MI,
    DRIFT_SLEEP,
    DRIFT_WAKE,
    GUIDE_PAN_MAX,
    LaneGuidance,
    classify_boundaries,
)


def _lane(offset: float = 0.0) -> LaneKeeping:
    lane = LaneKeeping(seed=1)
    lane.offset = offset
    return lane


def _frame(g, lane, *, dt=1.0, curve_steer=0.0, curve_ahead_mi=None, assist_on=True):
    return g.update(
        lane, dt, assist_on=assist_on, curve_steer=curve_steer, curve_ahead_mi=curve_ahead_mi
    )


def test_centered_straight_leaves_the_bed_home():
    g = LaneGuidance()
    frame = _frame(g, _lane(0.0))
    assert not frame.awake
    assert frame.pan == 0.0


def test_drift_wakes_and_hysteresis_holds():
    g = LaneGuidance()
    assert not _frame(g, _lane(DRIFT_WAKE - 0.05)).awake
    assert _frame(g, _lane(DRIFT_WAKE + 0.05)).awake
    # Back inside the wake line but above the sleep line: still awake.
    assert _frame(g, _lane(DRIFT_SLEEP + 0.05)).awake
    assert not _frame(g, _lane(DRIFT_SLEEP - 0.05)).awake


def test_pursuit_pan_leans_toward_the_correction():
    # Drifting RIGHT: the wheel should go left, so the bed leans LEFT --
    # follow the sound back to center.
    g = LaneGuidance()
    frame = _frame(g, _lane(0.7))
    assert frame.awake
    assert frame.pan < 0.0
    g2 = LaneGuidance()
    frame = _frame(g2, _lane(-0.7))
    assert frame.pan > 0.0


def test_curve_leads_into_the_bend_even_centered():
    # A left bend wants a left steer: the bed leans left while centered.
    g = LaneGuidance()
    frame = _frame(g, _lane(0.0), curve_steer=-0.6)
    assert frame.awake
    assert frame.pan < 0.0
    # And the lean never exceeds the cap -- some road stays in both ears.
    g2 = LaneGuidance()
    for _ in range(5):
        frame = _frame(g2, _lane(0.9), curve_steer=-1.0)
    assert abs(frame.pan) <= GUIDE_PAN_MAX + 1e-9


def test_upcoming_curve_arms_inside_the_lead_window():
    g = LaneGuidance()
    assert not _frame(g, _lane(0.0), curve_ahead_mi=CURVE_LEAD_MI * 2).awake
    assert _frame(g, _lane(0.0), curve_ahead_mi=CURVE_LEAD_MI * 0.5).awake


def test_pan_slews_home_after_sleep():
    g = LaneGuidance()
    _frame(g, _lane(0.9))  # deep drift: bed leans well left
    assert g.pan < 0.0
    frame = _frame(g, _lane(0.0))  # settled: asleep, slewing home
    assert not frame.awake
    for _ in range(4):
        frame = _frame(g, _lane(0.0))
    assert frame.pan == 0.0


def test_sleep_after_drift_flags_the_centered_earcon():
    g = LaneGuidance()
    _frame(g, _lane(0.7))
    frame = _frame(g, _lane(0.05))
    assert not frame.awake
    assert frame.centered
    # A curve-only episode ends without the earcon: nothing drifted.
    _frame(g, _lane(0.0), curve_steer=0.4)
    frame = _frame(g, _lane(0.0))
    assert not frame.centered


def test_assist_off_is_inert():
    g = LaneGuidance()
    frame = _frame(g, _lane(0.9), curve_steer=-0.8, assist_on=False)
    assert not frame.awake
    assert frame.pan == 0.0


def test_edge_rungs_grade_by_structure():
    from freight_fate.sim.lane import OFF_ROAD, RUMBLE_START
    from freight_fate.sim.lane_guidance import (
        EDGE_CLIP_KEY,
        EDGE_SHOULDER_KEY,
        EDGE_STRIP_KEY,
        edge_rung,
    )

    assert edge_rung(RUMBLE_START - 0.1, boundary="shoulder") is None
    key, vol_clip = edge_rung(RUMBLE_START + 0.05, boundary="shoulder")
    assert key == EDGE_CLIP_KEY
    key, vol_strip = edge_rung(1.05, boundary="shoulder")
    assert key == EDGE_STRIP_KEY
    assert vol_strip > vol_clip  # louder as well as structurally different
    key, _ = edge_rung(OFF_ROAD + 0.05, boundary="shoulder")
    assert key == EDGE_SHOULDER_KEY
    # Past an undivided centerline there is no gravel: the strip stays the
    # outermost texture and the spoken warning carries the danger.
    key, _ = edge_rung(OFF_ROAD + 0.05, boundary="oncoming")
    assert key == EDGE_STRIP_KEY


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


def test_no_new_tone_ever():
    """The community ruling (roadmap, 2026-07-17): the guide is the existing
    road bed, never a new synthetic tone. Pin the module against a bed key
    quietly coming back."""
    import freight_fate.sim.lane_guidance as lg

    assert not hasattr(lg, "BED_KEY")


@pytest.mark.parametrize("boundary", ["shoulder", "median", "oncoming", "lane"])
def test_edge_rung_accepts_every_boundary(boundary):
    from freight_fate.sim.lane_guidance import edge_rung

    assert edge_rung(1.4, boundary=boundary) is not None
