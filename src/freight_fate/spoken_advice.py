"""Retiring instructions the player has demonstrated (research doc R7).

Some spoken prompts teach a control the game names on every wheel entry or
every stop callout, forever: "Press E to start the engine", "F1 lists the
controls", "Press X to signal for the exit". Once a player has done the
thing a few times the instruction is noise, and the pull-model query keys
keep the information reachable, so retiring the auto-nag loses nothing.

Retirement is gated on a small persisted counter, but the counter is keyed
to the *control binding and the transmission mode it was earned under*, so a
remapped key or a switch to manual re-teaches the new hint afresh -- the
standing rule that spoken advice never names a control the current settings
do not give this driver, cutting both ways (never name a wrong key, never go
silent where the key is now different). The binding is captured as the hint
phrase itself: change the device, or remap the key, and the phrase changes,
which changes the key, which resets the count to zero.

The counters live in the profile's ``achievement_stats`` dict (already
persisted and general-purpose) under a ``hint:`` namespace, so no new save
field is needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .achievements import increment_stat, int_stat

if TYPE_CHECKING:
    from .models.profile import Profile

# Spoken until the player has performed the action this many times under the
# current binding and transmission. Small: three unremarkable repetitions is
# enough to show the control is known.
RETIRE_AFTER = 3


def _counter_key(action: str, binding: str, transmission: str) -> str:
    return f"hint:{action}:{binding}:{transmission}"


def _transmission_label(automatic: bool) -> str:
    return "auto" if automatic else "manual"


def instruction_retired(profile: Profile, action: str, *, binding: str, automatic: bool) -> bool:
    """Whether ``action``'s spoken instruction has been earned into silence
    for the current ``binding`` and transmission mode."""
    key = _counter_key(action, binding, _transmission_label(automatic))
    return int_stat(profile, key) >= RETIRE_AFTER


def note_demonstrated(profile: Profile, action: str, *, binding: str, automatic: bool) -> int:
    """Record that the player just performed ``action`` under this binding and
    transmission. Returns the new count. Stops counting past the retirement
    threshold so the stored number never runs away."""
    key = _counter_key(action, binding, _transmission_label(automatic))
    if int_stat(profile, key) >= RETIRE_AFTER:
        return RETIRE_AFTER
    return increment_stat(profile, key)
