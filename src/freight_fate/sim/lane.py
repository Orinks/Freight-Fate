"""Lane keeping: gentle drift within the lane, corrected by ear.

The truck wanders in its lane from three sources — slow random wander,
road curvature (from the route's terrain), and crosswind gusts scaled by
the weather. The player counters with the Left and Right arrows. All cues
are audio: engine and road noise pan with the lane offset, a rumble strip
sounds in the matching ear at the lane edge, and staying fully off the
lane triggers an off-road event.

The tuning goal is GENTLE: on a calm flat leg a correction every 15-30
seconds is plenty; mountain curves and storms demand genuine attention.
Heavier loads (see :mod:`vehicle`) respond more sluggishly to corrections.

Offset units: 0 is lane center, |offset| = 1 puts the tires on the lane
edge (rumble strip), |offset| >= OFF_ROAD is fully off the lane.
"""

from __future__ import annotations

import random

MPH_PER_MPS = 2.23694

ASSIST_LEVELS = ("off", "light", "realistic")

LANE_EDGE = 1.0          # tires touch the rumble strip here
OFF_ROAD = 1.3           # fully off the lane
MAX_OFFSET = 1.5         # physical clamp (ditch)
RUMBLE_START = 0.85      # rumble fades in from here to just past the edge
RUMBLE_FULL = 1.15

OFF_ROAD_GRACE_S = 2.0   # seconds fully off the lane before the event fires
OFF_ROAD_REPEAT_S = 3.0  # and again every few seconds while still off

# Drift rates in offset units per second at full strength.
WANDER_RATE = 0.05       # random wander: center to edge in ~20 s worst case
CURVE_RATE = 0.16        # a full mountain curve: center to edge in ~6 s
WIND_RATE = 0.11         # a storm-force gust: center to edge in ~9 s
STEER_RATE = 0.55        # full deflection recenters from the edge in ~1.8 s

# assist level -> (drift multiplier, steering authority multiplier)
ASSIST_TUNING = {"light": (0.55, 1.25), "realistic": (1.0, 1.0)}

REFERENCE_MASS_KG = 36_000.0  # steering authority is tuned at this gross weight


class LaneKeeping:
    """Lane position simulation for one trip; deterministic given a seed."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self.offset = 0.0        # -1 left edge .. +1 right edge
        self.steering = 0.0      # player input, -1 full left .. +1 full right
        self._wander = 0.0
        self._wander_target = 0.0
        self._wander_timer = 0.0
        self._gust = 0.0
        self._gust_target = 0.0
        self._gust_timer = 0.0
        self._off_road_timer = 0.0
        self._event_cooldown = 0.0

    def update(self, dt: float, speed_mps: float, curve: float = 0.0,
               wind: float = 0.0, mass_factor: float = 1.0,
               assist: str = "realistic") -> bool:
        """Advance by ``dt`` real seconds. Returns True when an off-road
        event fires (sustained |offset| >= OFF_ROAD).

        ``curve`` is signed road curvature -1..1 (see ``Trip.curve_at``),
        ``wind`` the weather's 0..1 wind strength, and ``mass_factor`` the
        truck's gross weight relative to a standard 36 t rig — heavier
        means slower steering response.
        """
        tuning = ASSIST_TUNING.get(assist)
        if tuning is None:  # "off": the truck holds its lane by itself
            self.offset = 0.0
            self._off_road_timer = 0.0
            return False
        drift_mult, steer_mult = tuning

        mph = speed_mps * MPH_PER_MPS
        if mph < 2.0:  # parked or crawling: nothing pushes the truck around
            self._off_road_timer = 0.0
            return False
        speed_factor = min(1.2, mph / 55.0)

        # Slow random wander: a new gentle pull every 10-25 seconds.
        self._wander_timer -= dt
        if self._wander_timer <= 0.0:
            self._wander_timer = self._rng.uniform(10.0, 25.0)
            self._wander_target = self._rng.uniform(-1.0, 1.0) * WANDER_RATE
        self._wander += (self._wander_target - self._wander) * min(1.0, dt / 3.0)

        # Crosswind gusts: faster cadence, strength scaled by the weather.
        self._gust_timer -= dt
        if self._gust_timer <= 0.0:
            self._gust_timer = self._rng.uniform(3.0, 8.0)
            self._gust_target = self._rng.uniform(-1.0, 1.0)
        self._gust += (self._gust_target - self._gust) * min(1.0, dt / 1.5)

        drift = (self._wander + curve * CURVE_RATE
                 + wind * self._gust * WIND_RATE) * drift_mult * speed_factor

        # Steering: full effect above ~25 mph, sluggish when heavy.
        authority = (STEER_RATE * steer_mult * min(1.0, mph / 25.0)
                     / max(0.5, mass_factor))
        self.offset += (drift + self.steering * authority) * dt
        self.offset = max(-MAX_OFFSET, min(MAX_OFFSET, self.offset))

        self._event_cooldown = max(0.0, self._event_cooldown - dt)
        if abs(self.offset) >= OFF_ROAD:
            self._off_road_timer += dt
            if (self._off_road_timer >= OFF_ROAD_GRACE_S
                    and self._event_cooldown <= 0.0):
                self._event_cooldown = OFF_ROAD_REPEAT_S
                return True
        else:
            self._off_road_timer = 0.0
        return False

    # -- audio cue helpers ---------------------------------------------------------

    @property
    def side(self) -> int:
        """-1 when left of center, +1 when right."""
        return -1 if self.offset < 0 else 1

    def pan(self) -> float:
        """Stereo pan for engine and road noise, -1 left .. +1 right."""
        return max(-0.8, min(0.8, self.offset * 0.6))

    def rumble_level(self) -> float:
        """0..1 rumble-strip loudness as the tires ride the lane edge."""
        return max(0.0, min(1.0, (abs(self.offset) - RUMBLE_START)
                            / (RUMBLE_FULL - RUMBLE_START)))

    # -- speech ----------------------------------------------------------------------

    def describe(self) -> str:
        """Spoken lane position for the on-demand info key."""
        side = "left" if self.offset < 0 else "right"
        away = abs(self.offset)
        if away < 0.25:
            return "Centered in your lane."
        if away < 0.7:
            return f"Drifting {side}."
        if away < OFF_ROAD:
            return f"At the {side} edge of your lane."
        return f"Off the road on the {side}!"
