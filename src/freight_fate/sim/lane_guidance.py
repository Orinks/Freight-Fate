"""Lane-guidance director: pans the EXISTING road bed toward the steer.

Pure logic, no audio calls -- the driving state feeds it the lane model and
the curve context each frame and applies the pan it returns to the road
noise loop. Keeping it a plain object keeps the cue logic testable headless.

The design is the community-resolved one on the roadmap (JaceK's audiogames
ruling, owner concurring, 2026-07-17), plus the owner's wake/sleep contract
(2026-07-27):

- Silence-is-centered: on a straight, centered and stable, guidance does
  nothing at all -- the road bed sits where it always sits.
- NO new steering tones, ever: continuous synthetic tones overwhelm the
  soundscape and hurt players with sensory or hearing issues. The guide is
  the EXISTING road/tire bed, panned along the arc.
- Pursuit, not error-nulling: the bed leans toward where the wheel should
  go -- follow the sound. In a bend it leads into the curve; in a drift it
  sits toward lane center. (Forza's audio steering guide panned
  engine+tires the same way; pursuit tracking beats error-nulling in the
  human-factors literature.)
- The guide wakes for exactly two reasons: drifting toward a lane line, or
  a curve inside its lead window (or underway). It slews home and sleeps
  on the straight.
- Drift cues stay underneath as the error backstop: the edge-boundary
  ladder (intermittent clip / periodic strip / aperiodic gravel) and the
  departure warnings, which grade by structure, not loudness.

``boundary`` names what is past the lane line on each side of the CURRENT
lane, so the edge sounds and spoken warnings can say the truth: ``lane``
(another lane of same-direction traffic), ``median`` (a divided highway's
left edge), ``oncoming`` (an undivided road's centerline), or ``shoulder``
(the right road edge).
"""

from __future__ import annotations

from dataclasses import dataclass

from .lane import LANE_EDGE, LaneKeeping

# The guide stays asleep inside this much of lane center: normal wander on a
# straight never wakes it (WANDER_RATE drift stays well inside 0.35).
DRIFT_WAKE = 0.45
# Hysteresis: once awake, sleep only after settling back inside this.
DRIFT_SLEEP = 0.30
# A curve wakes the guide this many miles before its start.
CURVE_LEAD_MI = 0.30
# The bed never pans fully into one ear: some road stays on both sides so
# the soundscape keeps its floor under the guide.
GUIDE_PAN_MAX = 0.8
# How fast the bed slews toward its target, pan units per second: quick
# enough to lead a bend, slow enough to read as leaning, not jumping.
PAN_SLEW_PER_S = 1.6

# The edge-boundary ladder: three structural states (intermittent clip,
# periodic strip, aperiodic shoulder) so the rungs stay separable under
# engine and road noise. Offsets are lane-model units (see sim.lane).
EDGE_CLIP_KEY = "vehicle/edge_clip"
EDGE_STRIP_KEY = "vehicle/edge_strip"
EDGE_SHOULDER_KEY = "vehicle/edge_shoulder"
EDGE_STRIP_AT = 1.0  # past this the whole tire is on the strip
EDGE_VOLUME_MIN = 0.35
EDGE_VOLUME_MAX = 0.80


def edge_rung(excursion: float, *, boundary: str) -> tuple[str, float] | None:
    """(loop key, volume) for a road-edge excursion, or None inside the lane.

    ``boundary`` is what lies past this edge (classify_boundaries). The
    gravel shoulder rung only exists where there IS gravel: past an
    undivided centerline the pavement continues into the oncoming lane, so
    the strip stays the outermost texture and the spoken warning carries
    the danger.
    """
    from .lane import OFF_ROAD, RUMBLE_START

    if excursion < RUMBLE_START:
        return None
    span = max(OFF_ROAD - RUMBLE_START, 0.01)
    level = min(1.0, (excursion - RUMBLE_START) / span)
    volume = EDGE_VOLUME_MIN + level * (EDGE_VOLUME_MAX - EDGE_VOLUME_MIN)
    if excursion >= OFF_ROAD and boundary != "oncoming":
        return EDGE_SHOULDER_KEY, EDGE_VOLUME_MAX
    if excursion >= EDGE_STRIP_AT:
        return EDGE_STRIP_KEY, volume
    return EDGE_CLIP_KEY, volume


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
    pan: float  # road-bed pan, -1..1: the side the wheel should go toward
    centered: bool = False  # this frame ended a drift episode back at center


class LaneGuidance:
    """Wake/sleep and pursuit-pan shaping. One instance per drive."""

    def __init__(self) -> None:
        self._awake = False
        self._episode_drifted = False
        self.pan = 0.0  # current slewed pan, applied to the road bed

    @property
    def awake(self) -> bool:
        return self._awake

    def update(
        self,
        lane: LaneKeeping,
        dt: float,
        *,
        assist_on: bool,
        curve_steer: float,
        curve_ahead_mi: float | None,
    ) -> GuidanceFrame:
        """Advance one frame.

        ``curve_steer`` is the signed steer the active bend asks for
        (-1 full left .. 1 full right, 0 when no bend is active);
        ``curve_ahead_mi`` is distance to the next curve's start (None when
        nothing is inside the lookahead).
        """
        if not assist_on:
            self._awake = False
            self._episode_drifted = False
            self.pan = 0.0
            return GuidanceFrame(False, 0.0)

        drift = abs(lane.offset)
        in_curve_window = curve_steer != 0.0 or (
            curve_ahead_mi is not None and curve_ahead_mi <= CURVE_LEAD_MI
        )
        was_awake = self._awake
        if self._awake:
            self._awake = in_curve_window or drift > DRIFT_SLEEP
        else:
            self._awake = in_curve_window or drift > DRIFT_WAKE
        if self._awake and drift > DRIFT_WAKE:
            self._episode_drifted = True

        # Pursuit target: lean into the bend, corrected toward lane center.
        # Asleep, the target is home -- the bed slews back where it lives.
        if self._awake:
            target = curve_steer - lane.offset / LANE_EDGE
            target = max(-GUIDE_PAN_MAX, min(GUIDE_PAN_MAX, target))
        else:
            target = 0.0
        step = PAN_SLEW_PER_S * max(0.0, dt)
        if abs(target - self.pan) <= step:
            self.pan = target
        else:
            self.pan += step if target > self.pan else -step

        if not self._awake:
            centered = was_awake and self._episode_drifted
            self._episode_drifted = False
            return GuidanceFrame(False, self.pan, centered=centered)
        return GuidanceFrame(True, self.pan)
