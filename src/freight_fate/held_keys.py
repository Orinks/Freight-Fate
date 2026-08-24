"""Held keys as the driving loop should see them, screen reader or not.

Driving reads the pedals and the wheel by polling: is Up down right now?
``pygame.key.get_pressed()`` answers from the key events SDL received, and
with no screen reader, or with NVDA, that is the physical keyboard: a held
key reads held until the finger lifts.

JAWS is different. It binds the arrow keys to its own scripts in every
application, so its keyboard hook swallows the physical press, runs the
script, and re-sends the key to the application as a synthetic
press-and-release pair. The game sees a tap that lasts zero frames, which a
poll never catches: menus react to the press event and work, driving polls
and does nothing until the player passes one key through with JAWS Key+3.
Holding the key does not help by itself, but the keyboard's auto-repeat
still runs underneath; every repeat goes through the same hook and arrives
as another press-and-release pair, at the operating system's repeat delay
and rate.

This tracker turns that train back into a hold. Every press starts a pulse
sized to the operating system's repeat timing: long enough to reach the
first auto-repeat after a fresh press, and just past one repeat interval
once repeats are arriving. A release that lands in the same frame as its
press (or the next one) is synthetic -- nobody taps a key inside one frame
-- and leaves the pulse alone; a release any later is the player's finger
and ends it. The driving loop reads a key as held when SDL says so OR a
pulse is alive, so the physical-keyboard path is exactly what it always was
and the re-injected path reads as a hold that lapses about one repeat
interval after the finger lifts.

Two honest limits. A screen reader that re-injects keys never shows the game
how long a tap lasted, so under JAWS a tap reads as a hold for the repeat
delay (half a second at the Windows default) and a gesture built on tap
length cannot be seen. And the game cannot tell whether such a screen
reader is running, so the pulse logic is always on; on the physical path it
only ever adds a hold when a whole press-and-release arrives inside one
short frame, which a finger cannot do.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Mapping

import pygame

log = logging.getLogger(__name__)

# Fallbacks when the operating system will not say: the Windows defaults
# (delay setting 1 of 0..3 is 500 ms; rate setting 31 of 0..31 is about 30
# repeats per second).
DEFAULT_REPEAT_DELAY_MS = 500
DEFAULT_REPEAT_INTERVAL_MS = 33

# Grace on top of the operating system's timing. The fresh-press pulse has
# to outlast the repeat delay plus the screen reader's script latency and a
# frame of batching; the per-repeat pulse has to outlast one interval plus
# a frame, and it is how long after the finger lifts the key still reads
# held, so it stays short.
FRESH_GRACE_MS = 150
REPEAT_GRACE_MS = 100

# A release this soon after its press is synthetic: the same frame, or the
# next one at 60 frames per second. The fastest finger tap is far longer.
SYNTHETIC_GAP_MS = 25

# ...but only when the frame was a normal one. After a long hitch a whole
# real tap can land in one batch, and then the honest answer is "not held",
# never a half-second hold. A re-injected pair dropped this way costs
# nothing: the next repeat pair re-establishes the hold a frame later.
SYNTHETIC_FRAME_MAX_MS = 40

# A press this soon after its pulse train began cannot be the operating
# system's first auto-repeat (which never fires early), so it is a new tap of
# the same key and earns a fresh full pulse.
REPEAT_EARLY_TOLERANCE_MS = 60

_SPI_GETKEYBOARDDELAY = 0x0016
_SPI_GETKEYBOARDSPEED = 0x000A


def repeat_delay_ms(setting: int) -> int:
    """Windows keyboard delay setting (0..3) to milliseconds before the
    first auto-repeat: 250 ms per step, so 0 is 250 ms and 3 is a second."""
    return (max(0, min(3, int(setting))) + 1) * 250


def repeat_interval_ms(setting: int) -> int:
    """Windows keyboard speed setting (0..31) to milliseconds between
    auto-repeats: 0 is about 2.5 repeats per second, 31 about 30."""
    rate = 2.5 + 27.5 * max(0, min(31, int(setting))) / 31
    return round(1000 / rate)


def os_repeat_timing() -> tuple[int, int]:
    """(delay, interval) in ms of the keyboard auto-repeat, from Windows when
    it answers, else the defaults. Only Windows has JAWS, and only Windows
    exposes the setting this cheaply, so nothing else is asked."""
    if sys.platform != "win32":
        return DEFAULT_REPEAT_DELAY_MS, DEFAULT_REPEAT_INTERVAL_MS
    try:
        import ctypes

        user32 = ctypes.windll.user32
        delay = ctypes.c_uint(0)
        speed = ctypes.c_uint(0)
        got_delay = user32.SystemParametersInfoW(_SPI_GETKEYBOARDDELAY, 0, ctypes.byref(delay), 0)
        got_speed = user32.SystemParametersInfoW(_SPI_GETKEYBOARDSPEED, 0, ctypes.byref(speed), 0)
    except Exception:
        log.debug("Keyboard repeat timing unavailable; using defaults", exc_info=True)
        return DEFAULT_REPEAT_DELAY_MS, DEFAULT_REPEAT_INTERVAL_MS
    delay_ms = repeat_delay_ms(delay.value) if got_delay else DEFAULT_REPEAT_DELAY_MS
    interval_ms = repeat_interval_ms(speed.value) if got_speed else DEFAULT_REPEAT_INTERVAL_MS
    return delay_ms, interval_ms


class HeldSnapshot:
    """One frame's answer to "is this key held?", indexed like
    ``pygame.key.get_pressed()`` so the driving code reads it unchanged."""

    __slots__ = ("_pressed", "_pulsed")

    def __init__(self, pressed, pulsed: frozenset[int]) -> None:
        self._pressed = pressed
        self._pulsed = pulsed

    def __getitem__(self, key: int) -> bool:
        return bool(self._pressed[key]) or key in self._pulsed

    @property
    def pulsed(self) -> frozenset[int]:
        """Keys held only by a re-injected press train (for diagnostics)."""
        return self._pulsed


class HeldKeys:
    """Track which keys the player is holding, fed by the app's event loop.

    ``begin_frame`` once per frame with the frame's tick time, ``note`` for
    every event, ``snapshot`` whenever a state wants to poll. ``clear``
    forgets the pulses (the app calls it when the state stack changes, so a
    screen never inherits the last screen's held keys).
    """

    def __init__(
        self,
        repeat_delay_ms: int | None = None,
        repeat_interval_ms: int | None = None,
    ) -> None:
        if repeat_delay_ms is None or repeat_interval_ms is None:
            os_delay, os_interval = os_repeat_timing()
            repeat_delay_ms = os_delay if repeat_delay_ms is None else repeat_delay_ms
            repeat_interval_ms = os_interval if repeat_interval_ms is None else repeat_interval_ms
        self._delay_ms = int(repeat_delay_ms)
        self._interval_ms = int(repeat_interval_ms)
        self._now = 0
        self._frame_span_ms = 0
        self._pulse_until: dict[int, int] = {}
        self._train_start: dict[int, int] = {}
        self._pressed_at: dict[int, int] = {}

    # -- timing -------------------------------------------------------------------

    @property
    def repeat_delay_ms(self) -> int:
        return self._delay_ms

    @property
    def repeat_interval_ms(self) -> int:
        return self._interval_ms

    @property
    def fresh_pulse_ms(self) -> int:
        """How long a lone press reads held: to the first auto-repeat, plus grace."""
        return self._delay_ms + FRESH_GRACE_MS

    @property
    def repeat_pulse_ms(self) -> int:
        """How long each repeat extends the hold: one interval, plus grace."""
        return self._interval_ms + REPEAT_GRACE_MS

    def refresh_repeat_timing(self) -> None:
        """Re-read the operating system's repeat timing (on window focus, so a
        player who changed the keyboard settings gets them without a restart)."""
        self._delay_ms, self._interval_ms = os_repeat_timing()

    # -- feeding --------------------------------------------------------------------

    def begin_frame(self, now_ms: int) -> None:
        self._frame_span_ms = now_ms - self._now if self._now else 0
        self._now = now_ms

    def note(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self._press(event.key)
        elif event.type == pygame.KEYUP:
            self._release(event.key)
        elif event.type == pygame.WINDOWFOCUSLOST:
            # SDL releases every key when the window loses focus; the pulses
            # go with them so alt-tabbing away never leaves a pedal down.
            self.clear()
        elif event.type == pygame.WINDOWFOCUSGAINED:
            self.refresh_repeat_timing()

    def clear(self) -> None:
        self._pulse_until.clear()
        self._train_start.clear()

    def _press(self, key: int) -> None:
        now = self._now
        until = self._pulse_until.get(key, 0)
        start = self._train_start.get(key)
        repeating = (
            until > now
            and start is not None
            and now - start >= self._delay_ms - REPEAT_EARLY_TOLERANCE_MS
        )
        if repeating:
            window = self.repeat_pulse_ms
        else:
            window = self.fresh_pulse_ms
            self._train_start[key] = now
        self._pulse_until[key] = max(until, now + window)
        self._pressed_at[key] = now

    def _release(self, key: int) -> None:
        pressed_at = self._pressed_at.get(key)
        synthetic = (
            pressed_at is not None
            and self._now - pressed_at <= SYNTHETIC_GAP_MS
            and self._frame_span_ms <= SYNTHETIC_FRAME_MAX_MS
        )
        if synthetic:
            return
        self._pulse_until.pop(key, None)
        self._train_start.pop(key, None)

    # -- reading --------------------------------------------------------------------

    def pulsed(self) -> frozenset[int]:
        """Keys a re-injected press train is holding as of this frame."""
        now = self._now
        dead = [key for key, until in self._pulse_until.items() if until <= now]
        for key in dead:
            self._pulse_until.pop(key, None)
            self._train_start.pop(key, None)
        return frozenset(self._pulse_until)

    def snapshot(self, pressed: Mapping[int, bool] | None = None) -> HeldSnapshot:
        """This frame's held keys: SDL's own state (``pygame.key.get_pressed``
        unless ``pressed`` is given) plus any live pulse."""
        if pressed is None:
            pressed = pygame.key.get_pressed()
        return HeldSnapshot(pressed, self.pulsed())
