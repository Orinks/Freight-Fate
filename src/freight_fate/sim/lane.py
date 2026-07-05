"""Lane model for the 1-D driving view: a discrete lane index plus a
continuous position within the current lane.

``lane`` counts from the rightmost driving lane (0) leftward; a rural
two-lane interstate is lanes 0 (right) and 1 (left). ``offset`` is centered
at 0.0 within the current lane. Absolute 1.0 means the tires are touching
the lane line, and larger values mean the truck is leaving the lane: across
a line with a neighboring lane that becomes a lane change, across the
outside edge it becomes the shoulder or the median.
"""

from __future__ import annotations

import random

MPH_PER_MPS = 2.23694

ASSIST_LEVELS = ("off", "light", "realistic")
LANE_EDGE = 1.0
LANE_WIDTH = 2.0  # offset units from one lane center to the next
CROSS_AT = 1.12  # straddling the line this far commits the lane change
OFF_ROAD = 1.3
MAX_OFFSET = 1.5
RUMBLE_START = 0.85
RUMBLE_FULL = 1.15
OFF_ROAD_GRACE_S = 2.0
OFF_ROAD_REPEAT_S = 3.0
WANDER_RATE = 0.05
CURVE_RATE = 0.12
WIND_RATE = 0.10
STEER_RATE = 0.55
ASSIST_TUNING = {"light": (0.45, 1.35), "realistic": (1.0, 1.0)}

DEFAULT_LANE_COUNT = 2


def lane_label(index: int, count: int) -> str:
    """Spoken name for a lane index: right, left, or middle."""
    if index <= 0:
        return "right"
    if index >= count - 1:
        return "left"
    return "middle"


class LaneKeeping:
    """Small deterministic lane simulation for audio-only steering cues."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self.offset = 0.0
        self.steering = 0.0
        self.lane = 0  # everyone starts in the right lane
        self.lane_count = DEFAULT_LANE_COUNT
        self.crossed = 0  # last update's lane change: +1 left, -1 right
        self._wander = 0.0
        self._wander_target = 0.0
        self._wander_timer = 0.0
        self._gust = 0.0
        self._gust_target = 0.0
        self._gust_timer = 0.0
        self._off_road_timer = 0.0
        self._event_cooldown = 0.0

    @property
    def lane_name(self) -> str:
        return lane_label(self.lane, self.lane_count)

    def set_lane_count(self, count: int) -> None:
        self.lane_count = max(1, count)
        self.lane = min(self.lane, self.lane_count - 1)

    def _edge_excursion(self) -> float:
        """How far past center toward a road *edge* -- a side with no
        neighboring lane. Drifting toward another lane never rumbles; the
        rumble strip lives on the shoulder and the median."""
        if self.offset > 0.0 and self.lane == 0:
            return self.offset
        if self.offset < 0.0 and self.lane >= self.lane_count - 1:
            return -self.offset
        return 0.0

    def update(
        self,
        dt: float,
        speed_mps: float,
        *,
        curve: float = 0.0,
        wind: float = 0.0,
        assist: str = "off",
    ) -> bool:
        """Advance the lane model.

        Returns True when the truck has been off the road edge long enough to
        fire a warning/damage event. A completed drift across an interior lane
        line is reported through ``crossed`` (+1 moved left, -1 moved right)
        for the frame it happens. ``assist='off'`` preserves the pre-existing
        driving behavior by keeping the truck centered; the discrete ``lane``
        is still honored there, driven by tap-to-change controls.
        """
        self.crossed = 0
        tuning = ASSIST_TUNING.get(assist)
        if tuning is None:
            self.offset = 0.0
            self._off_road_timer = 0.0
            return False
        drift_mult, steer_mult = tuning

        mph = speed_mps * MPH_PER_MPS
        if mph < 2.0:
            self._off_road_timer = 0.0
            return False
        speed_factor = min(1.2, mph / 55.0)

        self._wander_timer -= dt
        if self._wander_timer <= 0.0:
            self._wander_timer = self._rng.uniform(10.0, 25.0)
            self._wander_target = self._rng.uniform(-1.0, 1.0) * WANDER_RATE
        self._wander += (self._wander_target - self._wander) * min(1.0, dt / 3.0)

        self._gust_timer -= dt
        if self._gust_timer <= 0.0:
            self._gust_timer = self._rng.uniform(3.0, 8.0)
            self._gust_target = self._rng.uniform(-1.0, 1.0)
        self._gust += (self._gust_target - self._gust) * min(1.0, dt / 1.5)

        drift = (
            (self._wander + curve * CURVE_RATE + wind * self._gust * WIND_RATE)
            * drift_mult
            * speed_factor
        )
        authority = STEER_RATE * steer_mult * min(1.0, mph / 25.0)
        self.offset += (drift + self.steering * authority) * dt

        # Straddle an interior line far enough and the truck is in the next
        # lane over: re-center the offset relative to the new lane so the
        # player finishes the change by straightening out.
        if self.offset <= -CROSS_AT and self.lane < self.lane_count - 1:
            self.lane += 1
            self.offset += LANE_WIDTH
            self.crossed = 1
        elif self.offset >= CROSS_AT and self.lane > 0:
            self.lane -= 1
            self.offset -= LANE_WIDTH
            self.crossed = -1
        self.offset = max(-MAX_OFFSET, min(MAX_OFFSET, self.offset))

        self._event_cooldown = max(0.0, self._event_cooldown - dt)
        if self._edge_excursion() >= OFF_ROAD:
            self._off_road_timer += dt
            if self._off_road_timer >= OFF_ROAD_GRACE_S and self._event_cooldown <= 0.0:
                self._event_cooldown = OFF_ROAD_REPEAT_S
                return True
        else:
            self._off_road_timer = 0.0
        return False

    def rumble_level(self) -> float:
        """0..1 rumble-strip cue level at the road edge (shoulder or median)."""
        return max(
            0.0,
            min(1.0, (self._edge_excursion() - RUMBLE_START) / (RUMBLE_FULL - RUMBLE_START)),
        )

    def describe(self) -> str:
        lane_part = f"In the {self.lane_name} lane"
        side = "left" if self.offset < 0 else "right"
        away = abs(self.offset)
        if away < 0.25:
            return f"{lane_part}, centered."
        if away < 0.7:
            return f"{lane_part}, drifting {side}."
        if self._edge_excursion() >= OFF_ROAD:
            return f"Off the road on the {side}!"
        if away < CROSS_AT:
            return f"{lane_part}, at the {side} edge of the lane."
        return f"{lane_part}, crossing the {side} lane line."
