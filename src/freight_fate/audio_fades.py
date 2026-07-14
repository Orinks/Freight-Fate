"""Reusable, backend-agnostic volume fades driven by a per-frame ``dt``.

Nothing here touches an audio backend directly. A :class:`Fade` is just a
timed ramp between two numbers with a chosen easing curve; it calls a
supplied ``apply(value)`` setter each frame. This keeps the fade machinery
independent of whether the volume ultimately lands on a pygame channel, a
BASS stream, or a plain multiplier -- the caller wires that up.

Typical use for a crossfade::

    sched = FadeScheduler()
    sched.add(Fade(clip.set_volume, 1.0, 0.0, 0.9, curve="linear"))
    sched.add(Fade(set_loop_gain, 0.0, 1.0, 0.9, curve="linear"))
    # then, each frame:
    sched.update(dt)
"""

from __future__ import annotations

import math
from collections.abc import Callable

__all__ = ["CURVES", "curve", "Fade", "FadeScheduler"]

# Easing curves map linear progress ``t`` in [0, 1] to eased progress in
# [0, 1], with f(0) == 0 and f(1) == 1. A Fade interpolates
# ``start + (end - start) * curve(t)``.
#
# The equal-power pair keeps the summed loudness of a crossfade roughly
# constant: run the outgoing sound's fade with ``equal_power_out`` and the
# incoming one with ``equal_power_in``.


def _clamp01(t: float) -> float:
    return 0.0 if t < 0.0 else 1.0 if t > 1.0 else t


def _exponential(t: float, k: float = 4.0) -> float:
    # Slow-start exponential ramp, normalized to hit exactly 0 and 1.
    return (math.exp(k * t) - 1.0) / (math.exp(k) - 1.0)


CURVES: dict[str, Callable[[float], float]] = {
    "linear": lambda t: t,
    "ease_in": lambda t: t * t,
    "ease_out": lambda t: 1.0 - (1.0 - t) * (1.0 - t),
    "ease_in_out": lambda t: t * t * (3.0 - 2.0 * t),  # smoothstep
    "exponential": _exponential,
    # Equal-power crossfade pair (constant perceived loudness through a blend).
    "equal_power_in": lambda t: math.sin(t * math.pi / 2.0),
    "equal_power_out": lambda t: 1.0 - math.cos(t * math.pi / 2.0),
}


def curve(name: str) -> Callable[[float], float]:
    """Look up a curve by name, defaulting to linear for unknown names."""
    return CURVES.get(name, CURVES["linear"])


# Module-level alias so Fade can resolve a name without the ``curve`` parameter
# shadowing the lookup function.
_resolve_curve = curve


class Fade:
    """A single timed volume ramp advanced by :meth:`advance`.

    ``apply(value)`` is called every frame with the current interpolated
    value; ``duration_s`` is the ramp length and ``delay_s`` an optional wait
    before it begins (during the delay the value stays at ``start``). Pass a
    curve name from :data:`CURVES` or a callable. ``on_done`` fires once when
    the ramp reaches ``end``.
    """

    def __init__(
        self,
        apply: Callable[[float], None],
        start: float,
        end: float,
        duration_s: float,
        curve: str | Callable[[float], float] = "linear",
        delay_s: float = 0.0,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        self._apply = apply
        self._start = float(start)
        self._end = float(end)
        self._duration = max(0.0, float(duration_s))
        self._curve = _resolve_curve(curve) if isinstance(curve, str) else curve
        self._delay = max(0.0, float(delay_s))
        self._on_done = on_done
        self._elapsed = 0.0
        self._done = False
        # Present the starting value immediately (covers the delay window and
        # zero-duration fades before the first advance lands).
        self._apply(self._start)

    @property
    def done(self) -> bool:
        return self._done

    def advance(self, dt: float) -> bool:
        """Advance by ``dt`` seconds; return True once the ramp has finished."""
        if self._done:
            return True
        self._elapsed += max(0.0, dt)
        if self._elapsed < self._delay:
            return False
        if self._duration <= 0.0:
            t = 1.0
        else:
            t = _clamp01((self._elapsed - self._delay) / self._duration)
        value = self._start + (self._end - self._start) * self._curve(t)
        self._apply(value)
        if t >= 1.0:
            self._done = True
            if self._on_done is not None:
                self._on_done()
        return self._done


class FadeScheduler:
    """Holds active fades and advances them together each frame."""

    def __init__(self) -> None:
        self._fades: list[Fade] = []

    def add(self, fade: Fade) -> Fade:
        self._fades.append(fade)
        return fade

    def update(self, dt: float) -> None:
        if not self._fades:
            return
        self._fades = [f for f in self._fades if not f.advance(dt)]

    def clear(self) -> None:
        self._fades.clear()

    def __len__(self) -> int:
        return len(self._fades)
