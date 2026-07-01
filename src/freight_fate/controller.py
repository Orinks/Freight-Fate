"""Game-controller support, isolated in one module.

Freight Fate is keyboard- and screen-reader-first; this adds an *optional*
second input device that never displaces the keyboard. It uses the newer
``pygame._sdl2.controller`` API, which maps any recognized pad onto the Xbox
button layout, so friendly names (A/B/X/Y, bumpers, D-pad) are the same
regardless of the physical controller.

Design notes:

* Event-driven. Buttons and hot-plug arrive as SDL ``CONTROLLER*`` events.
  The only continuous reads are the analog axes (steering, throttle, brake,
  clutch): those are cached from ``CONTROLLERAXISMOTION`` events and smoothed
  on :meth:`ControllerManager.tick`, so the driving loop reads cached state
  rather than polling the device.
* Headless-safe. If the controller subsystem or a device is unavailable (CI,
  dummy SDL drivers), the manager degrades to "no controller" without raising.
* One active controller. Several may be connected; we bind the first and, if
  it is unplugged, raise a disconnect signal the app uses to pause and speak.
"""

from __future__ import annotations

import contextlib
import logging
from enum import Enum, auto

import pygame

from .input_hints import CONTROLLER, KEYBOARD, control_hint

log = logging.getLogger(__name__)

# Deadzones from the design spec: 10% for the sticks, 4% for the triggers.
STICK_DEADZONE = 0.10
TRIGGER_DEADZONE = 0.04
AXIS_MAX = 32767.0

# Held D-pad left/right auto-repeat for adjusting menu options.
REPEAT_DELAY_S = 0.30  # wait before the first repeat
REPEAT_FAST_S = 0.03  # fastest repeat once fully accelerated
REPEAT_RAMP_S = 1.50  # time held over which it accelerates

# Minimal analog smoothing: triggers and clutch reach their target quickly but
# not instantly, matching how the keyboard ramps feel today.
SMOOTH_RATE = 18.0


class ControllerAction(Enum):
    MENU_UP = auto()
    MENU_DOWN = auto()
    ADJUST_LEFT = auto()
    ADJUST_RIGHT = auto()
    CONFIRM = auto()
    BACK = auto()
    HELP = auto()


_BUTTON_LABELS = {
    pygame.CONTROLLER_BUTTON_A: "A button",
    pygame.CONTROLLER_BUTTON_B: "B button",
    pygame.CONTROLLER_BUTTON_X: "X button",
    pygame.CONTROLLER_BUTTON_Y: "Y button",
    pygame.CONTROLLER_BUTTON_LEFTSHOULDER: "left bumper",
    pygame.CONTROLLER_BUTTON_RIGHTSHOULDER: "right bumper",
    pygame.CONTROLLER_BUTTON_LEFTSTICK: "left stick click",
    pygame.CONTROLLER_BUTTON_RIGHTSTICK: "right stick click",
    pygame.CONTROLLER_BUTTON_DPAD_UP: "D-pad up",
    pygame.CONTROLLER_BUTTON_DPAD_DOWN: "D-pad down",
    pygame.CONTROLLER_BUTTON_DPAD_LEFT: "D-pad left",
    pygame.CONTROLLER_BUTTON_DPAD_RIGHT: "D-pad right",
    pygame.CONTROLLER_BUTTON_BACK: "Back button",
    pygame.CONTROLLER_BUTTON_START: "Start button",
}

_MENU_ACTIONS = {
    pygame.CONTROLLER_BUTTON_DPAD_UP: ControllerAction.MENU_UP,
    pygame.CONTROLLER_BUTTON_DPAD_DOWN: ControllerAction.MENU_DOWN,
    pygame.CONTROLLER_BUTTON_DPAD_LEFT: ControllerAction.ADJUST_LEFT,
    pygame.CONTROLLER_BUTTON_DPAD_RIGHT: ControllerAction.ADJUST_RIGHT,
    pygame.CONTROLLER_BUTTON_A: ControllerAction.CONFIRM,
    pygame.CONTROLLER_BUTTON_B: ControllerAction.BACK,
    pygame.CONTROLLER_BUTTON_BACK: ControllerAction.HELP,
}


def _deadzone(value: float, dead: float) -> float:
    """Rescale a normalized axis so it is 0 inside the deadzone and reaches
    full range at the edge, avoiding a sudden jump just past the threshold."""
    magnitude = abs(value)
    if magnitude <= dead:
        return 0.0
    scaled = (magnitude - dead) / (1.0 - dead)
    return scaled if value >= 0 else -scaled


class ControllerManager:
    """Owns the active controller and translates its events for the game."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.active_device = KEYBOARD  # which device the player last used
        self._controller = None
        self._instance_id: int | None = None
        self._name = ""
        self._disconnected = False  # latched until the app consumes it

        # Raw (event) and smoothed (tick) analog targets. The clutch is a digital
        # bumper, so it stays instant like the keyboard Shift and is not smoothed.
        self._steer_target = 0.0
        self._throttle_target = 0.0
        self._brake_target = 0.0
        self._clutch = 0.0
        self._throttle = 0.0
        self._brake = 0.0
        self.modifier = False  # right bumper held -> secondary bindings

        # D-pad left/right auto-repeat.
        self._repeat_button: int | None = None
        self._repeat_countdown = 0.0
        self._repeat_held = 0.0

        try:
            from pygame._sdl2 import controller as sdl_controller

            self._sdl = sdl_controller
            self._sdl.init()
            self._open_first()
        except Exception:  # pragma: no cover - platform/driver dependent
            log.info("Controller subsystem unavailable; keyboard only", exc_info=True)
            self._sdl = None

    # -- device lifecycle -----------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._controller is not None

    @property
    def active(self) -> bool:
        """True when a controller is connected and controller input is on."""
        return self.enabled and self._controller is not None

    @property
    def name(self) -> str:
        return self._name

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self._reset_analog()
            self.active_device = KEYBOARD

    def _open_first(self) -> None:
        if self._sdl is None:
            return
        for index in range(self._sdl.get_count()):
            if self._sdl.is_controller(index):
                try:
                    self._controller = self._sdl.Controller(index)
                except Exception:  # pragma: no cover - driver dependent
                    continue
                self._instance_id = self._controller.id
                try:
                    self._name = self._sdl.name_forindex(index) or "controller"
                except Exception:  # pragma: no cover
                    self._name = "controller"
                log.info("Controller connected: %s", self._name)
                return

    def take_disconnect(self) -> bool:
        """Return and clear the pending-disconnect flag (app pauses on True)."""
        if self._disconnected:
            self._disconnected = False
            return True
        return False

    def _reset_analog(self) -> None:
        self._steer_target = self._throttle_target = 0.0
        self._brake_target = self._clutch = 0.0
        self._throttle = self._brake = 0.0
        self.modifier = False
        self._repeat_button = None

    # -- input notification ---------------------------------------------------

    def note_keyboard(self) -> None:
        """Record that the keyboard was just used, so hints name keys."""
        self.active_device = KEYBOARD

    @property
    def device(self) -> str:
        return CONTROLLER if (self.active and self.active_device == CONTROLLER) else KEYBOARD

    def hint(self, action: str) -> str:
        """Control phrase for ``action`` naming whatever device is in use."""
        return control_hint(action, self.device)

    # -- event handling -------------------------------------------------------

    def process_event(self, event: pygame.event.Event) -> None:
        """Update device/axis/modifier state from a CONTROLLER* event."""
        etype = event.type
        if etype == pygame.CONTROLLERDEVICEADDED:
            if self._controller is None:
                self._open_first()
            return
        if etype == pygame.CONTROLLERDEVICEREMOVED:
            if self._instance_id is not None and event.instance_id == self._instance_id:
                self._controller = None
                self._instance_id = None
                self._reset_analog()
                self._disconnected = True
                log.info("Controller disconnected")
            return
        if not self.active or event.instance_id != self._instance_id:
            return
        if etype == pygame.CONTROLLERAXISMOTION:
            self._on_axis(event.axis, event.value)
        elif etype == pygame.CONTROLLERBUTTONDOWN:
            self.active_device = CONTROLLER
            self._on_button_down(event.button)
        elif etype == pygame.CONTROLLERBUTTONUP:
            self._on_button_up(event.button)

    def _on_axis(self, axis: int, raw: int) -> None:
        value = raw / AXIS_MAX
        if axis == pygame.CONTROLLER_AXIS_LEFTX:
            self._steer_target = _deadzone(value, STICK_DEADZONE)
            if self._steer_target:
                self.active_device = CONTROLLER
        elif axis == pygame.CONTROLLER_AXIS_TRIGGERRIGHT:
            self._throttle_target = _deadzone(max(0.0, value), TRIGGER_DEADZONE)
            if self._throttle_target:
                self.active_device = CONTROLLER
        elif axis == pygame.CONTROLLER_AXIS_TRIGGERLEFT:
            self._brake_target = _deadzone(max(0.0, value), TRIGGER_DEADZONE)
            if self._brake_target:
                self.active_device = CONTROLLER

    def _on_button_down(self, button: int) -> None:
        if button == pygame.CONTROLLER_BUTTON_RIGHTSHOULDER:
            self.modifier = True
        elif button == pygame.CONTROLLER_BUTTON_LEFTSHOULDER:
            self._clutch = 1.0  # instant, like holding Shift
        if button in (
            pygame.CONTROLLER_BUTTON_DPAD_LEFT,
            pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
        ):
            self._repeat_button = button
            self._repeat_countdown = REPEAT_DELAY_S
            self._repeat_held = 0.0

    def _on_button_up(self, button: int) -> None:
        if button == pygame.CONTROLLER_BUTTON_RIGHTSHOULDER:
            self.modifier = False
        elif button == pygame.CONTROLLER_BUTTON_LEFTSHOULDER:
            self._clutch = 0.0
        if button == self._repeat_button:
            self._repeat_button = None

    def menu_action(self, event: pygame.event.Event) -> ControllerAction | None:
        """The semantic menu action for a CONTROLLERBUTTONDOWN, or None."""
        if event.type != pygame.CONTROLLERBUTTONDOWN:
            return None
        return _MENU_ACTIONS.get(event.button)

    def button_label(self, button: int) -> str:
        return _BUTTON_LABELS.get(button, "a button")

    # -- per-frame update -----------------------------------------------------

    def tick(self, dt: float) -> list[pygame.event.Event]:
        """Smooth analog axes and return synthetic D-pad repeat events."""
        if not self.active:
            return []
        self._throttle = self._smooth(self._throttle, self._throttle_target, dt)
        self._brake = self._smooth(self._brake, self._brake_target, dt)
        return self._repeats(dt)

    @staticmethod
    def _smooth(current: float, target: float, dt: float) -> float:
        return current + (target - current) * min(1.0, SMOOTH_RATE * dt)

    def _repeats(self, dt: float) -> list[pygame.event.Event]:
        if self._repeat_button is None:
            return []
        self._repeat_held += dt
        self._repeat_countdown -= dt
        events: list[pygame.event.Event] = []
        while self._repeat_countdown <= 0.0:
            events.append(
                pygame.event.Event(
                    pygame.CONTROLLERBUTTONDOWN,
                    button=self._repeat_button,
                    instance_id=self._instance_id,
                )
            )
            fraction = min(1.0, self._repeat_held / REPEAT_RAMP_S)
            interval = REPEAT_DELAY_S - (REPEAT_DELAY_S - REPEAT_FAST_S) * fraction
            self._repeat_countdown += interval
        return events

    # -- analog reads for the driving loop ------------------------------------

    @property
    def steering(self) -> float:
        return self._steer_target if self.active else 0.0

    @property
    def throttle(self) -> float:
        return self._throttle if self.active else 0.0

    @property
    def brake(self) -> float:
        return self._brake if self.active else 0.0

    @property
    def clutch(self) -> float:
        return self._clutch if self.active else 0.0

    def shutdown(self) -> None:
        self._controller = None
        if self._sdl is not None:
            with contextlib.suppress(Exception):  # pragma: no cover
                self._sdl.quit()
            self._sdl = None
