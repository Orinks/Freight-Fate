"""Controller haptics (rumble), isolated from the device layer.

Freight Fate is audio-first; rumble only *reinforces* cues a player already
hears. This module owns the *shape* of every effect and knows nothing about
pygame or SDL: :class:`RumbleEngine` is handed a ``send(low, high, duration_ms)``
and a ``stop()`` callable by :class:`~freight_fate.controller.ControllerManager`,
so it drives a real pad in the game and a list-recording fake in tests.

The two motors map onto the request's geography:

* ``low_frequency`` -- the large **left-grip** motor.
* ``high_frequency`` -- the small **right-grip** motor.

So "starting at the right and moving to the left" is a high->low sweep, and an
alert "blip of the high-frequency side" is a short right-grip buzz.

Effects come in two kinds:

* **One-shots** (hazard sweep, alert blip, collision impact): an envelope
  ``fn(t)`` over normalized time ``0..1`` that runs for a fixed duration and
  then drops itself.
* **Continuous** (rumble strip, hard-brake shudder): a level refreshed every
  frame while the condition holds. A short TTL means the caller never has to
  send an explicit "off" -- the effect stops on its own a few frames after the
  refreshes stop.

Every frame :meth:`tick` combines whatever is active (per-motor max), issues a
single device call, and stops the device once on the active->idle edge.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

# Re-issued every frame with a duration a few frames long, so a dropped frame
# never leaves an audible gap; each new call replaces the last on SDL.
FRAME_RUMBLE_MS = 120

# Continuous effects are refreshed each frame; if the refresh stops, the effect
# lapses this many seconds later (a few frames at 60 fps).
CONTINUOUS_TTL_S = 0.05

# Hazard sweep: two overlapping raised-cosine bumps across a 0.75 s window, the
# right (high) leading and the left (low) trailing.
HAZARD_DURATION_MS = 750
_HAZARD_HIGH_CENTER, _HAZARD_HIGH_HALF, _HAZARD_HIGH_PEAK = 0.25, 0.32, 0.85
_HAZARD_LOW_CENTER, _HAZARD_LOW_HALF, _HAZARD_LOW_PEAK = 0.62, 0.34, 1.0

# Alert blip: a short right-grip (high) buzz.
ALERT_INTENSITY = 0.6
ALERT_DURATION_MS = 120

# Collision impact: a heavy low thump that decays, with a brief high crack.
IMPACT_DURATION_MS = 350

# Rumble strip: both motors buzz between a non-zero floor and a ceiling, the
# right side pulsing faster than the left -- a deliberately harsh, alternating
# feel that never fully releases either motor.
_STRIP_LOW_HZ = 9.0
_STRIP_HIGH_HZ = 16.0

# Hard braking: a continuous low shudder scaled by brake force, with a light
# high texture on top.
_BRAKE_SHUDDER_HZ = 22.0
_BRAKE_TEXTURE_HZ = 30.0


def _clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value


def _bump(t: float, center: float, half: float, peak: float) -> float:
    """A raised-cosine (Hann) bump peaking at ``center`` with half-width
    ``half``; zero outside the window. Used to shape the hazard sweep."""
    d = abs(t - center)
    if d >= half:
        return 0.0
    return peak * 0.5 * (1.0 + math.cos(math.pi * d / half))


def _osc(phase: float, hz: float) -> float:
    """A 0..1 oscillation at ``hz`` cycles per second."""
    return 0.5 * (1.0 + math.sin(2.0 * math.pi * hz * phase))


@dataclass
class _OneShot:
    duration: float  # seconds
    fn: Callable[[float], tuple[float, float]]  # t in 0..1 -> (low, high)
    elapsed: float = 0.0


@dataclass
class RumbleEngine:
    """Schedules and mixes haptic effects, driving an injected device."""

    send: Callable[[float, float, int], None]
    stop: Callable[[], None]

    _phase: float = 0.0
    _oneshots: list[_OneShot] = field(default_factory=list)
    _strip_level: float = 0.0
    _strip_ttl: float = 0.0
    _brake_level: float = 0.0
    _brake_ttl: float = 0.0
    _active: bool = False

    # -- one-shot effects -----------------------------------------------------

    def alert(
        self, intensity: float = ALERT_INTENSITY, duration_ms: int = ALERT_DURATION_MS
    ) -> None:
        """A short high-frequency blip that accompanies an alert."""
        amp = _clamp01(intensity)
        self._oneshots.append(_OneShot(duration_ms / 1000.0, lambda _t: (0.0, amp)))

    def hazard(self) -> None:
        """The 750 ms right->left sweep for a communicated hazard."""

        def envelope(t: float) -> tuple[float, float]:
            high = _bump(t, _HAZARD_HIGH_CENTER, _HAZARD_HIGH_HALF, _HAZARD_HIGH_PEAK)
            low = _bump(t, _HAZARD_LOW_CENTER, _HAZARD_LOW_HALF, _HAZARD_LOW_PEAK)
            return low, high

        self._oneshots.append(_OneShot(HAZARD_DURATION_MS / 1000.0, envelope))

    def impact(self, severity: float) -> None:
        """A heavy low thump for a collision (louder than an alert blip)."""
        sev = _clamp01(severity)
        low_peak = 0.6 + 0.4 * sev
        high_peak = 0.4 * sev

        def envelope(t: float) -> tuple[float, float]:
            low = low_peak * (1.0 - t) ** 1.5  # quick attack, decaying thump
            high = high_peak * max(0.0, 1.0 - 4.0 * t)  # brief crack at the hit
            return low, high

        self._oneshots.append(_OneShot(IMPACT_DURATION_MS / 1000.0, envelope))

    # -- continuous effects (refresh each frame while active) -----------------

    def rumble_strip(self, level: float) -> None:
        """Refresh the harsh rumble-strip buzz; ``level`` is 0..1."""
        self._strip_level = _clamp01(level)
        self._strip_ttl = CONTINUOUS_TTL_S

    def hard_brake(self, level: float) -> None:
        """Refresh the hard-braking shudder; ``level`` is 0..1."""
        self._brake_level = _clamp01(level)
        self._brake_ttl = CONTINUOUS_TTL_S

    # -- per-frame drive ------------------------------------------------------

    def tick(self, dt: float) -> None:
        self._phase += dt
        low = high = 0.0

        self._strip_ttl -= dt
        if self._strip_ttl > 0.0:
            s = 0.55 + 0.45 * self._strip_level
            low = max(low, s * (0.55 + 0.45 * _osc(self._phase, _STRIP_LOW_HZ)))
            high = max(high, s * (0.60 + 0.40 * _osc(self._phase, _STRIP_HIGH_HZ)))

        self._brake_ttl -= dt
        if self._brake_ttl > 0.0:
            shudder = 0.85 + 0.15 * _osc(self._phase, _BRAKE_SHUDDER_HZ)
            low = max(low, (0.35 + 0.55 * self._brake_level) * shudder)
            high = max(high, 0.15 * self._brake_level * _osc(self._phase, _BRAKE_TEXTURE_HZ))

        for eff in self._oneshots:
            eff.elapsed += dt
        self._oneshots = [e for e in self._oneshots if e.elapsed < e.duration]
        for eff in self._oneshots:
            elow, ehigh = eff.fn(eff.elapsed / eff.duration)
            low = max(low, elow)
            high = max(high, ehigh)

        low, high = _clamp01(low), _clamp01(high)
        if low > 0.0 or high > 0.0:
            self.send(low, high, FRAME_RUMBLE_MS)
            self._active = True
        elif self._active:
            self.stop()
            self._active = False

    def reset(self) -> None:
        """Drop every effect and silence the device (disconnect / haptics off)."""
        self._oneshots.clear()
        self._strip_ttl = self._brake_ttl = 0.0
        self._strip_level = self._brake_level = 0.0
        if self._active:
            self._active = False
        self.stop()
