"""Lightweight lane-position model for the 1-D driving view.

Offset units are centered at 0.0. Absolute 1.0 means the tires are touching
the lane edge, and larger values mean the truck is leaving the lane.
"""

from __future__ import annotations

import random

MPH_PER_MPS = 2.23694

ASSIST_LEVELS = ("off", "light", "realistic")
LANE_EDGE = 1.0
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


class LaneKeeping:
    """Small deterministic lane simulation for audio-only steering cues."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self.offset = 0.0
        self.steering = 0.0
        self._wander = 0.0
        self._wander_target = 0.0
        self._wander_timer = 0.0
        self._gust = 0.0
        self._gust_target = 0.0
        self._gust_timer = 0.0
        self._off_road_timer = 0.0
        self._event_cooldown = 0.0

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

        Returns True when the truck has been off the lane long enough to fire a
        warning/damage event. ``assist='off'`` preserves the pre-existing driving
        behavior by keeping the truck centered.
        """
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
        self.offset = max(-MAX_OFFSET, min(MAX_OFFSET, self.offset))

        self._event_cooldown = max(0.0, self._event_cooldown - dt)
        if abs(self.offset) >= OFF_ROAD:
            self._off_road_timer += dt
            if self._off_road_timer >= OFF_ROAD_GRACE_S and self._event_cooldown <= 0.0:
                self._event_cooldown = OFF_ROAD_REPEAT_S
                return True
        else:
            self._off_road_timer = 0.0
        return False

    def rumble_level(self) -> float:
        """0..1 rumble-strip cue level at the lane edge."""
        return max(
            0.0,
            min(1.0, (abs(self.offset) - RUMBLE_START) / (RUMBLE_FULL - RUMBLE_START)),
        )

    def describe(self) -> str:
        side = "left" if self.offset < 0 else "right"
        away = abs(self.offset)
        if away < 0.25:
            return "Centered in your lane."
        if away < 0.7:
            return f"Drifting {side}."
        if away < OFF_ROAD:
            return f"At the {side} edge of your lane."
        return f"Off the road on the {side}!"
