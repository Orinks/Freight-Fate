"""Game controller (gamepad) support: devices, input translation, and rumble.

Every screen in the game is driven by ``pygame`` keyboard events, and the
driving state additionally polls held keys each frame. Rather than teach each
screen about joysticks, this module translates a connected controller into the
input the game already understands:

* Discrete button and D-pad presses become synthetic ``KEYDOWN`` events,
  dispatched through the normal ``handle_event`` path. The mapping depends on
  the active screen's *mode* ("menu" or "driving") so the same physical buttons
  read naturally in both contexts.
* The driving state reads analog throttle, brake, and steering each frame from
  :meth:`ControllerManager.read`, alongside the keyboard.
* :meth:`ControllerManager.rumble` mirrors the audio cues for rumble strips,
  hazards, and collisions.

The translation and analog logic are intentionally free of hidden global state
so they can be unit tested by feeding synthetic events and a fake joystick,
with no physical hardware required.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass

import pygame

log = logging.getLogger(__name__)

# SDL2 game-controller layout, as pygame reports it for XInput-style pads.
AXIS_LEFT_X = 0
AXIS_LEFT_Y = 1
AXIS_RIGHT_X = 2
AXIS_RIGHT_Y = 3
AXIS_LEFT_TRIGGER = 4
AXIS_RIGHT_TRIGGER = 5

BTN_A = 0
BTN_B = 1
BTN_X = 2
BTN_Y = 3
BTN_LB = 4
BTN_RB = 5
BTN_BACK = 6
BTN_START = 7
BTN_LSTICK = 8
BTN_RSTICK = 9

# Tuning constants.
STEER_DEADZONE = 0.15        # left-stick slack ignored before steering reads
TRIGGER_DEADZONE = 0.06      # trigger pull ignored before it counts as input
TRIGGER_REST_EPS = 0.5       # a trigger at or below -this is confirmed at rest
NAV_THRESHOLD = 0.6          # stick push past this counts as a menu move

# Button -> keyboard key, per input mode. Buttons absent from a table do
# nothing in that mode (e.g. B in driving is the held emergency brake, read in
# :meth:`ControllerManager.read`, not a discrete press).
_MENU_BUTTON_KEYS = {
    BTN_A: pygame.K_RETURN,
    BTN_B: pygame.K_ESCAPE,
    BTN_START: pygame.K_RETURN,
    BTN_BACK: pygame.K_ESCAPE,
    BTN_X: pygame.K_F1,
    BTN_Y: pygame.K_F1,
    BTN_LB: pygame.K_HOME,
    BTN_RB: pygame.K_END,
}
_DRIVING_BUTTON_KEYS = {
    BTN_A: pygame.K_e,          # start/stop the engine
    BTN_X: pygame.K_h,          # horn
    BTN_Y: pygame.K_p,          # parking brake
    BTN_LB: pygame.K_x,         # take the next exit
    BTN_RB: pygame.K_k,         # adaptive cruise
    BTN_BACK: pygame.K_TAB,     # status menu
    BTN_START: pygame.K_ESCAPE,  # pause menu
    BTN_LSTICK: pygame.K_t,     # rest-stop / POI menu
    BTN_RSTICK: pygame.K_l,     # lane position
}

# D-pad direction (hat value) -> keyboard key, per mode.
_MENU_HAT_KEYS = {
    (0, 1): pygame.K_UP,
    (0, -1): pygame.K_DOWN,
    (-1, 0): pygame.K_LEFT,
    (1, 0): pygame.K_RIGHT,
}
_DRIVING_HAT_KEYS = {
    (0, 1): pygame.K_r,         # route progress
    (0, -1): pygame.K_v,        # weather
    (-1, 0): pygame.K_f,        # fuel
    (1, 0): pygame.K_c,         # clock and hours
}


@dataclass(frozen=True)
class ControllerInput:
    """A frame's worth of analog controller state for the driving loop."""

    throttle: float = 0.0       # 0..1, right trigger
    brake: float = 0.0          # 0..1, left trigger
    steer: float = 0.0          # -1..1, left stick X (negative = left)
    emergency: bool = False     # B held: emergency brake
    clutch: bool = False         # reserved; controllers do not drive manual gears


NEUTRAL_INPUT = ControllerInput()


def apply_deadzone(value: float, deadzone: float) -> float:
    """Center deadzone with edge rescaling so motion starts smoothly at the edge."""
    magnitude = abs(value)
    if magnitude <= deadzone:
        return 0.0
    sign = 1.0 if value > 0 else -1.0
    scaled = (magnitude - deadzone) / (1.0 - deadzone)
    return sign * min(1.0, scaled)


def _safe_name(joystick) -> str:
    try:
        return joystick.get_name()
    except Exception:  # pragma: no cover - driver quirk
        return "controller"


class ControllerManager:
    """Owns the active gamepad and converts its input for the rest of the game.

    ``joystick_module`` defaults to :mod:`pygame.joystick`; tests inject a fake
    module exposing ``init``/``get_init``/``get_count``/``Joystick`` to exercise
    device handling without real hardware.
    """

    def __init__(self, *, joystick_module=None) -> None:
        self._module = joystick_module if joystick_module is not None else pygame.joystick
        self.joystick = None
        self._instance_id: int | None = None
        self._nav_zone: dict[int, int] = {}      # axis -> -1/0/1 for menu nav edges
        self._trigger_seen: set[int] = set()      # axes confirmed to rest at -1
        # Preferred device name, so the chosen pad is re-picked next session even
        # though connection indices are not stable. "" = first one found.
        self.preferred_name = ""

    # -- device lifecycle ----------------------------------------------------------

    def start(self) -> None:
        """Initialise the joystick subsystem and attach the preferred pad, if any."""
        try:
            if not self._module.get_init():
                self._module.init()
        except Exception:
            log.warning("Joystick subsystem unavailable", exc_info=True)
            return
        if self.device_count() > 0:
            self._attach(self._preferred_index())

    def _attach(self, index: int) -> None:
        try:
            joystick = self._module.Joystick(index)
            joystick.init()
        except Exception:
            log.warning("Could not open controller %s", index, exc_info=True)
            return
        self.joystick = joystick
        try:
            self._instance_id = joystick.get_instance_id()
        except Exception:  # pragma: no cover - older pygame
            self._instance_id = index
        self._nav_zone.clear()
        self._trigger_seen.clear()
        log.info("Controller connected: %s", _safe_name(joystick))

    def device_count(self) -> int:
        try:
            return self._module.get_count()
        except Exception:  # pragma: no cover - driver quirk
            return 0

    def device_names(self) -> list[str]:
        """Names of every connected controller, in connection-index order."""
        names: list[str] = []
        for index in range(self.device_count()):
            try:
                names.append(_safe_name(self._module.Joystick(index)))
            except Exception:  # pragma: no cover - driver quirk
                names.append("controller")
        return names

    def _preferred_index(self) -> int:
        """Index of the device to attach when starting.

        A saved preferred name wins. With no saved choice, prefer a device SDL
        recognises as a game controller so a flight stick or wheel sharing the
        bus is not grabbed ahead of an actual pad; otherwise fall back to the
        first device.
        """
        if self.preferred_name:
            for index, name in enumerate(self.device_names()):
                if name == self.preferred_name:
                    return index
        gamepad = self._first_gamepad_index()
        return gamepad if gamepad is not None else 0

    def _first_gamepad_index(self) -> int | None:
        """First device SDL maps as a game controller, or ``None`` if unknown.

        Only consulted for the real joystick backend; with an injected fake
        module (tests) it returns ``None`` so selection stays index-based.
        """
        if self._module is not pygame.joystick:
            return None
        try:
            from pygame._sdl2 import controller as sdl2_controller
            sdl2_controller.init()
            for index in range(self.device_count()):
                if sdl2_controller.is_controller(index):
                    return index
        except Exception:  # pragma: no cover - older or headless SDL
            return None
        return None

    def select(self, index: int) -> bool:
        """Switch to the controller at ``index``; records it as preferred."""
        if not 0 <= index < self.device_count():
            return False
        self._detach()
        self._attach(index)
        if self.joystick is not None:
            self.preferred_name = self.name
            return True
        return False

    def select_next(self, step: int = 1) -> bool:
        """Cycle to another connected controller; returns True if one switched."""
        names = self.device_names()
        if len(names) < 2:
            return False
        current = self.name
        start = names.index(current) if current in names else 0
        return self.select((start + step) % len(names))

    def _detach(self) -> None:
        if self.joystick is None:
            return
        log.info("Controller disconnected: %s", _safe_name(self.joystick))
        with contextlib.suppress(Exception):  # pragma: no cover - driver quirk
            self.joystick.quit()
        self.joystick = None
        self._instance_id = None
        self._nav_zone.clear()
        self._trigger_seen.clear()

    @property
    def connected(self) -> bool:
        return self.joystick is not None

    @property
    def name(self) -> str:
        return _safe_name(self.joystick) if self.joystick is not None else ""

    def handle_system_event(self, event: pygame.event.Event) -> bool:
        """Process device add/remove events. Returns True when consumed."""
        etype = event.type
        if etype == pygame.JOYDEVICEADDED:
            # A pad appeared. If none is active, or the newcomer is the preferred
            # one, switch to it; otherwise keep the current pad.
            if self.joystick is None:
                self._attach(self._preferred_index())
            elif self.preferred_name and self.name != self.preferred_name:
                self._attach_preferred_if_present()
            return True
        if etype == pygame.JOYDEVICEREMOVED:
            removed = getattr(event, "instance_id", None)
            if self.joystick is not None and (
                    removed is None or removed == self._instance_id):
                self._detach()
                if self.device_count() > 0:
                    self._attach(self._preferred_index())
            return True
        return False

    def _attach_preferred_if_present(self) -> None:
        names = self.device_names()
        if self.preferred_name in names:
            self._detach()
            self._attach(names.index(self.preferred_name))

    # -- discrete input translation ------------------------------------------------

    def _owns(self, event: pygame.event.Event) -> bool:
        """Whether an input event came from the active controller.

        A flight stick, racing wheel, or second pad on the same machine emits
        the same joystick event types. Without this check their input would
        drive the game too -- and because a HOTAS throttle rests off-center and
        streams motion endlessly, it both steals menu navigation and corrupts
        the per-axis nav state shared by :meth:`_nav_edge`. Events with no
        ``instance_id`` (the synthetic events used in tests) and the case of no
        active device are treated as owned, so behaviour there is unchanged.
        """
        if self._instance_id is None:
            return True
        eid = getattr(event, "instance_id", None)
        return eid is None or eid == self._instance_id

    def translate(self, event: pygame.event.Event, mode: str = "menu"):
        """Translate a joystick input event into synthetic key events.

        Returns ``None`` for events that are not controller input (so the caller
        dispatches them unchanged), an empty list for controller events consumed
        without a key (analog motion, or input from another device), or a list
        of synthetic ``KEYDOWN`` events.
        """
        etype = event.type
        if etype not in (
                pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION, pygame.JOYAXISMOTION):
            return None
        if not self._owns(event):
            return []
        if etype == pygame.JOYBUTTONDOWN:
            table = _DRIVING_BUTTON_KEYS if mode == "driving" else _MENU_BUTTON_KEYS
            key = table.get(event.button)
            return [_key_event(key)] if key is not None else []
        if etype == pygame.JOYHATMOTION:
            table = _DRIVING_HAT_KEYS if mode == "driving" else _MENU_HAT_KEYS
            key = table.get(tuple(event.value))
            return [_key_event(key)] if key is not None else []
        return self._axis_events(event, mode)

    def _axis_events(self, event: pygame.event.Event, mode: str):
        # While driving the sticks and triggers are analog, polled by read().
        if mode == "driving":
            return []
        axis = event.axis
        if axis == AXIS_LEFT_Y:
            return self._nav_edge(axis, event.value, pygame.K_UP, pygame.K_DOWN)
        if axis == AXIS_LEFT_X:
            return self._nav_edge(axis, event.value, pygame.K_LEFT, pygame.K_RIGHT)
        return []

    def _nav_edge(self, axis: int, value: float, neg_key: int, pos_key: int):
        zone = 0
        if value <= -NAV_THRESHOLD:
            zone = -1
        elif value >= NAV_THRESHOLD:
            zone = 1
        previous = self._nav_zone.get(axis, 0)
        self._nav_zone[axis] = zone
        if zone == 0 or zone == previous:
            return []
        return [_key_event(neg_key if zone < 0 else pos_key)]

    # -- analog input --------------------------------------------------------------

    def read(self) -> ControllerInput:
        """Sample analog throttle, brake, steering, and the emergency brake."""
        joystick = self.joystick
        if joystick is None:
            return NEUTRAL_INPUT
        try:
            steer = apply_deadzone(joystick.get_axis(AXIS_LEFT_X), STEER_DEADZONE)
            throttle = self._trigger(joystick, AXIS_RIGHT_TRIGGER)
            brake = self._trigger(joystick, AXIS_LEFT_TRIGGER)
            emergency = bool(joystick.get_button(BTN_B))
        except Exception:
            log.debug("Controller read failed", exc_info=True)
            return NEUTRAL_INPUT
        return ControllerInput(
            throttle=throttle, brake=brake, steer=steer, emergency=emergency)

    def _trigger(self, joystick, axis: int) -> float:
        """Normalise a trigger axis from its -1..1 rest/full range to 0..1.

        SDL reports an untouched trigger as ``-1`` once it has moved, but may
        report ``0`` before the first event -- which naively normalises to a
        phantom half-pull. Until the axis is seen at rest, it reads as zero.
        """
        try:
            raw = joystick.get_axis(axis)
        except Exception:  # pragma: no cover - driver quirk
            return 0.0
        if raw <= -TRIGGER_REST_EPS:
            self._trigger_seen.add(axis)
        if axis not in self._trigger_seen:
            return 0.0
        value = (raw + 1.0) / 2.0
        return value if value >= TRIGGER_DEADZONE else 0.0

    # -- rumble --------------------------------------------------------------------

    def rumble(self, low: float, high: float, duration_ms: int) -> bool:
        joystick = self.joystick
        if joystick is None:
            return False
        try:
            return bool(joystick.rumble(low, high, duration_ms))
        except Exception:  # pragma: no cover - device without rumble
            return False

    def stop_rumble(self) -> None:
        joystick = self.joystick
        if joystick is None:
            return
        with contextlib.suppress(Exception):  # pragma: no cover - device without rumble
            joystick.stop_rumble()


def _key_event(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0)
