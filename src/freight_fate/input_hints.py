"""Device-aware control hints for spoken prompts.

Freight Fate speaks a lot of instructions that name a control -- "press P to
release the parking brake", "hold the Up arrow to accelerate". With controller
support those prompts must name the *right* control for whichever device the
player is actually using. This module keeps a single table mapping a semantic
action to its keyboard phrase and its controller phrase, plus one lookup
function, so the surrounding sentences stay natural and there is exactly one
place to edit a control name.

The phrases are fragments meant to slot into a sentence after a verb, e.g.
``f"Press {control_hint('take_exit', device)} to take it."`` The keyboard side
matches the wording the game already used.
"""

from __future__ import annotations

KEYBOARD = "keyboard"
CONTROLLER = "controller"

# action -> (keyboard phrase, controller phrase)
_HINTS: dict[str, tuple[str, str]] = {
    "accelerate": ("the Up arrow", "the right trigger"),
    "brake": ("the Down arrow", "the left trigger"),
    "emergency_brake": ("B", "the left trigger fully"),
    "clutch": ("Left Shift", "the left bumper"),
    "gear_first": ("W", "the A button"),
    "gears": ("W and Q", "the A and X buttons"),
    "reverse": ("Backspace", "the X button"),
    "neutral": ("N", "neutral"),
    "engine": ("E", "right bumper plus A"),
    "parking_brake": ("P", "right bumper plus Y"),
    "take_exit": ("X", "D-pad down"),
    "rest": ("T", "right bumper plus D-pad down"),
    "cruise_set": ("K", "the Y button"),
    "cruise_adjust": ("plus and minus", "right bumper plus D-pad left or right"),
    "speed": ("Space", "the B button"),
    "status_menu": ("Tab", "right bumper plus Start"),
    "fuel": ("F", "right bumper plus B"),
    "clock": ("C", "D-pad right"),
    "route": ("R", "D-pad up"),
    "next_exit": ("Shift R", "right bumper plus D-pad up"),
    "weather": ("V", "D-pad left"),
    "lane": ("L", "the left stick"),
    "horn": ("H", "the left stick click"),
    "engine_brake": ("J", "the right stick click"),
    "pause": ("Escape", "Start"),
    "help": ("F1", "the Back button"),
    "stop_event_voice": ("Left or Right Control", "the Back button"),
}


def control_hint(action: str, device: str = KEYBOARD) -> str:
    """Phrase naming ``action``'s control for the active input ``device``.

    Falls back to the keyboard phrase for an unknown device, and returns the
    action name itself if it is not in the table (so a typo is audible in a
    test rather than crashing a prompt mid-drive).
    """
    kb, pad = _HINTS.get(action, (action, action))
    return pad if device == CONTROLLER else kb
