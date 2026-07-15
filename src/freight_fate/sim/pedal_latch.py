"""Latching pedals: double-tap-and-hold keeps a pedal held hands-free.

A free input-accessibility accommodation (owner design, playtest
2026-07-15): some players cannot keep a key held down through a long pull
or a steady descent snub, and pumping taps tires everyone's fingers
eventually. The latched accelerator is the old hand-throttle knob, a real
cab control; a latched service brake on a long grade cooks the drums
exactly like the brake-fire physics says it should.

The gesture lives on the pedal keys themselves, no chord to learn. A bare
double-tap would false-trigger on feathering (players pump the throttle in
taps), so the catch is DOUBLE-TAP-AND-HOLD: tap, then press again and keep
holding about half a second. The caller plays a catch click (its own
sound, distinct from the gear click) and speaks the state both ways.
Release is any fresh press of the same key, which returns the pedal to the
hand; the caller also force-releases on the opposite pedal and on safety
overrides (hazards, emergency braking, the overspeed alarm).

The machine is polled with the pedal's held state each frame, so it works
identically for keyboard keys and anything mapped onto them.
"""

from __future__ import annotations

TAP_MAX_S = 0.35  # a first press longer than this is driving, not a gesture
GAP_MAX_S = 0.35  # tap release to second press; longer and the tap expires
CATCH_HOLD_S = 0.5  # the second press must hold this long to catch


class PedalLatch:
    """One pedal's latch: poll ``update`` every frame with the held state.

    ``latched`` is the output the caller blends into the pedal's effective
    state. ``update`` returns ``"latched"`` on the catch, ``"released"``
    when a fresh press of the same key returns the pedal to the hand, and
    ``None`` otherwise, so the caller can click and speak the transitions.
    """

    def __init__(self) -> None:
        self.latched = False
        # idle: pedal up, ready for a gesture. tap: first press in progress.
        # gap: tapped, waiting for the second press. arming: second press
        # held, timing toward the catch. engaging: latched, the catching
        # press not yet released. resting: latched, pedal keys up. manual:
        # a plain sustained hold; wait for a full release before any gesture.
        self._state = "idle"
        self._timer = 0.0

    def update(self, held: bool, dt: float) -> str | None:
        self._timer += dt
        if self.latched:
            if self._state == "engaging":
                if not held:
                    self._state = "resting"
            elif held:  # resting + a fresh press: back to the hand
                self.latched = False
                self._state = "manual"
                return "released"
            return None
        if self._state == "idle":
            if held:
                self._state = "tap"
                self._timer = 0.0
        elif self._state == "tap":
            if not held:
                self._state = "gap" if self._timer <= TAP_MAX_S else "idle"
                self._timer = 0.0
            elif self._timer > TAP_MAX_S:
                self._state = "manual"
        elif self._state == "gap":
            if held:
                self._state = "arming"
                self._timer = 0.0
            elif self._timer > GAP_MAX_S:
                self._state = "idle"
        elif self._state == "arming":
            if not held:
                # Released before the catch: just feathering. The release
                # counts as a fresh tap so pumping can roll into a catch.
                self._state = "gap"
                self._timer = 0.0
            elif self._timer >= CATCH_HOLD_S:
                self.latched = True
                self._state = "engaging"
                return "latched"
        elif self._state == "manual" and not held:
            self._state = "idle"
        return None

    def release(self) -> bool:
        """Drop the latch from outside: opposite pedal or a safety override.

        Returns True when there was a latch to drop, so the caller speaks
        only real transitions. Lands in ``manual`` so a key still physically
        held keeps driving the pedal without starting a new gesture."""
        if not self.latched:
            return False
        self.latched = False
        self._state = "manual"
        return True
