"""Lane-guidance audio director: decides what the steering ear hears.

Pure logic, no audio calls -- the driving state feeds it the lane model and
the curve context each frame and plays whatever it returns. Keeping it a
plain object keeps the whole cue ladder testable headless.

The owner's contract (2026-07-27): centered and stable is SILENT -- the
engine and the tires are the soundscape. Guidance wakes for exactly two
reasons: the truck is drifting toward a lane line, or a curve is coming up
(or underway) and the driver needs continuous position to steer through it.
It goes back to sleep on the straight.

What plays when awake is one panned bed on a reserved loop channel, panned
toward the side the truck is drifting to -- hear it right, steer left, push
the sound back out of the cab. Volume grows toward the line. Crossing onto
a true road edge is not this module's voice: the edge ladder (rumble strip,
shoulder) stays with the lane model's ``rumble_level`` and the departure
events, which grade by STRUCTURE, not loudness.

``boundary`` names what is past the lane line on each side of the CURRENT
lane, so the departure sounds and spoken warnings can say the truth:
``lane`` (another lane of same-direction traffic), ``median`` (a divided
highway's left edge), ``oncoming`` (an undivided road's centerline), or
``shoulder`` (the right road edge).
"""

from __future__ import annotations

from dataclasses import dataclass

from .lane import LANE_EDGE, LaneKeeping

# The bed stays asleep inside this much of lane center: normal wander on a
# straight never wakes it (WANDER_RATE drift stays well inside 0.35).
DRIFT_WAKE = 0.45
# Hysteresis: once awake, sleep only after settling back inside this.
DRIFT_SLEEP = 0.30
# A curve wakes the bed this many miles before its start...
CURVE_LEAD_MI = 0.30
# ...and holds it this long past its end, so the exit straightening is heard.
CURVE_TAIL_MI = 0.05
# Bed volume ramp: silent at the wake line, full voice with tires on the line.
BED_MIN_VOLUME = 0.10
BED_MAX_VOLUME = 0.55
# In a curve the bed idles at this floor even when centered: continuous
# position is the point -- steering by ear needs a carrier to pan.
CURVE_FLOOR_VOLUME = 0.16
BED_FADE_MS = 220

BED_KEY = "vehicle/lane_bed"


def classify_boundaries(
    lane: int, lane_count: int, *, divided: bool | None, interstate: bool
) -> tuple[str, str]:
    """(left, right) of the current lane: lane / median / oncoming / shoulder.

    ``divided`` is the baked flag when the world has one; ``None`` falls back
    to an honest inference: an interstate is divided by definition, and a
    road with one lane per side is an undivided two-lane whose left line is
    the centerline. The multilane middle ground defaults to divided until
    the divided-flag bake (Track D2) says otherwise.
    """
    if divided is None:
        divided = interstate or lane_count >= 2
    left = "median" if divided else "oncoming"
    if lane < lane_count - 1:
        left = "lane"
    right = "shoulder" if lane <= 0 else "lane"
    return left, right


@dataclass
class GuidanceFrame:
    """One frame of guidance output for the driving state to perform."""

    awake: bool
    volume: float  # bed loop volume, 0 when asleep
    pan: float  # -1 full left .. 1 full right, the side the truck drifts to
    centered: bool = False  # this frame ended a drift episode back at center


class LaneGuidance:
    """Wake/sleep and bed shaping. One instance per drive."""

    def __init__(self) -> None:
        self._awake = False
        self._episode_drifted = False

    @property
    def awake(self) -> bool:
        return self._awake

    def update(
        self,
        lane: LaneKeeping,
        *,
        assist_on: bool,
        curve_active: bool,
        curve_ahead_mi: float | None,
    ) -> GuidanceFrame:
        """Advance one frame. ``curve_ahead_mi`` is distance to the next
        curve's start (None when nothing is within lookahead); the caller
        applies CURVE_TAIL_MI when reporting ``curve_active``."""
        if not assist_on:
            self._awake = False
            self._episode_drifted = False
            return GuidanceFrame(False, 0.0, 0.0)

        drift = abs(lane.offset)
        in_curve_window = curve_active or (
            curve_ahead_mi is not None and curve_ahead_mi <= CURVE_LEAD_MI
        )
        was_awake = self._awake
        if self._awake:
            self._awake = in_curve_window or drift > DRIFT_SLEEP
        else:
            self._awake = in_curve_window or drift > DRIFT_WAKE
        if self._awake and drift > DRIFT_WAKE:
            self._episode_drifted = True
        if not self._awake:
            centered = was_awake and self._episode_drifted
            self._episode_drifted = False
            return GuidanceFrame(False, 0.0, 0.0, centered=centered)

        # Volume: how close the tires are to the line, on top of the curve
        # floor. Pan tracks the offset direction -- the bed sits on the side
        # the truck is sliding toward.
        closeness = max(0.0, min(1.0, (drift - DRIFT_SLEEP) / (LANE_EDGE - DRIFT_SLEEP)))
        volume = BED_MIN_VOLUME + closeness * (BED_MAX_VOLUME - BED_MIN_VOLUME)
        if in_curve_window:
            volume = max(volume, CURVE_FLOOR_VOLUME)
        pan = max(-1.0, min(1.0, lane.offset / LANE_EDGE))
        return GuidanceFrame(True, volume, pan)
