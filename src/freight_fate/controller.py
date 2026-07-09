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
from .rumble import RumbleEngine

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

    def __init__(self, enabled: bool = True, haptics: bool = True) -> None:
        self.enabled = enabled
        self._haptics_enabled = haptics
        self.active_device = KEYBOARD  # which device the player last used
        self._controller = None
        self._instance_id: int | None = None
        self._name = ""
        self._disconnected = False  # latched until the app consumes it
        # A freshly opened pad reports a device id from ``Controller.id`` that a
        # hot-plug can leave stale (the events then arrive under a different id).
        # We treat the opened id as provisional and adopt the id of the first
        # real event we see, so the binding always matches the live event stream.
        self._id_pending = False
        # Buttons currently held, so a duplicate press (some pads/drivers deliver
        # a button twice) fires its action only once, on the genuine transition.
        self._buttons_down: set[int] = set()
        # Last "foreign" instance id we logged a dropped event for, so a stream
        # of events from a stale/other pad logs once rather than every frame.
        self._logged_mismatch_id: int | None = None
        # Haptics live in their own pygame-free engine; we only supply the
        # guarded device send/stop and drive it once per frame in tick().
        self.rumble = RumbleEngine(send=self._device_rumble, stop=self._device_stop_rumble)

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

    def set_haptics_enabled(self, enabled: bool) -> None:
        self._haptics_enabled = enabled
        if not enabled:
            self.rumble.reset()

    # -- haptics device layer -------------------------------------------------

    def _device_rumble(self, low: float, high: float, duration_ms: int) -> None:
        if not (self.active and self._haptics_enabled) or self._controller is None:
            return
        with contextlib.suppress(Exception):  # pragma: no cover - driver dependent
            self._controller.rumble(low, high, duration_ms)

    def _device_stop_rumble(self) -> None:
        if self._controller is None:
            return
        with contextlib.suppress(Exception):  # pragma: no cover - driver dependent
            self._controller.stop_rumble()

    # Controls SDL surfaces on a fully mapped pad; a reconnect that drops these
    # is the signature of the "dead triggers/shoulders" fault, so we check them.
    _ESSENTIAL_MAPPINGS = ("lefttrigger", "righttrigger", "leftshoulder", "rightshoulder")

    def _open_index(self, index: int) -> bool:
        """Bind the GameController at ``index``; return True on success."""
        if self._sdl is None or not self._sdl.is_controller(index):
            return False
        try:
            self._controller = self._sdl.Controller(index)
        except Exception:  # pragma: no cover - driver dependent
            log.debug("Could not open controller at slot %d", index, exc_info=True)
            return False
        self._instance_id = self._controller.id
        # Provisional: the first real event's instance id is authoritative (see
        # _id_pending), which self-heals a stale id left by a hot-plug.
        self._id_pending = True
        try:
            self._name = self._sdl.name_forindex(index) or "controller"
        except Exception:  # pragma: no cover
            self._name = "controller"
        log.info("Controller connected: %s (instance %s)", self._name, self._instance_id)
        self._log_capabilities(index)
        return True

    def _open_first(self) -> None:
        if self._sdl is None:
            return
        for index in range(self._sdl.get_count()):
            if self._open_index(index):
                return

    def _log_capabilities(self, index: int) -> None:
        """DEBUG snapshot of the bound pad, plus a WARNING if the trigger and
        shoulder controls are unmapped -- the fingerprint of the reconnect bug
        where those inputs stop responding while the rest of the pad works."""
        if self._controller is None:
            return
        mapping: dict[str, str] = {}
        with contextlib.suppress(Exception):  # pragma: no cover - driver dependent
            mapping = self._controller.get_mapping()
        with contextlib.suppress(Exception):  # pragma: no cover - driver dependent
            joy = self._controller.as_joystick()
            log.debug(
                "Controller %r caps: guid=%s axes=%d buttons=%d hats=%d",
                self._name,
                joy.get_guid(),
                joy.get_numaxes(),
                joy.get_numbuttons(),
                joy.get_numhats(),
            )
        if mapping:
            missing = [name for name in self._ESSENTIAL_MAPPINGS if not mapping.get(name)]
            log.debug("Controller %r mapping keys: %s", self._name, sorted(mapping))
            if missing:
                log.warning(
                    "Controller %r reconnected without %s mapped; "
                    "brake/throttle and bumpers may not respond",
                    self._name,
                    ", ".join(missing),
                )

    def _close_controller(self) -> None:
        """Release the SDL controller before dropping our reference, so its
        bookkeeping is torn down cleanly across a hot-plug."""
        if self._controller is not None:
            with contextlib.suppress(Exception):  # pragma: no cover - driver/stub dependent
                self._controller.quit()
        self._controller = None
        self._instance_id = None
        self._id_pending = False
        self._buttons_down.clear()

    def _is_attached(self) -> bool:
        """Whether the bound pad is still physically present. Assumes attached
        if the API is unavailable (e.g. the test stub), so we don't drop a
        working binding on a spurious ADDED event."""
        if self._controller is None:
            return False
        try:
            return bool(self._controller.attached())
        except Exception:  # pragma: no cover - driver/stub dependent
            return True

    def _reopen(self) -> None:
        """Drop the current pad and bind whatever is connected now.

        The first real event's instance id (see ``_id_pending``) corrects a
        stale id left by a hot-plug, so we never cycle the SDL subsystem:
        quitting and re-initializing it while the event loop is live
        re-registers SDL's controller event watch and makes every controller
        event arrive twice."""
        self._close_controller()
        self._open_first()

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
        self._buttons_down.clear()
        self.rumble.reset()

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

    def process_event(self, event: pygame.event.Event) -> bool:
        """Update device/axis/modifier state from a CONTROLLER* event.

        Returns True only for a button press/release that belongs to the bound
        controller and should be forwarded to the active state. Axis, device,
        and rejected (foreign-id) events return False, so the app never routes a
        stray event -- e.g. a duplicate from a pad that enumerates twice -- into
        a game action."""
        etype = event.type
        if etype == pygame.CONTROLLERDEVICEADDED:
            device_index = getattr(event, "device_index", None)
            log.debug("Controller device added (slot %s)", device_index)
            # Re-open when nothing is bound, or the bound pad has quietly
            # detached (a missed REMOVED event) -- otherwise a stale binding
            # would block the reconnect.
            if self._controller is not None and self._is_attached():
                log.debug("Ignoring add; a pad is already bound (instance %s)", self._instance_id)
                return False
            # Re-open in place. The first real event's id (see _id_pending)
            # corrects a stale id from the hot-plug; we deliberately do not cycle
            # the SDL subsystem, which would double every controller event.
            self._reopen()
            return False
        if etype == pygame.CONTROLLERDEVICEREMOVED:
            log.debug("Controller device removed (instance %s)", event.instance_id)
            if self._instance_id is not None and event.instance_id == self._instance_id:
                self._close_controller()
                self._reset_analog()
                self._disconnected = True
                self._logged_mismatch_id = None
                log.info("Controller disconnected")
            return False
        if not self.active:
            return False
        if event.instance_id != self._instance_id:
            if self._id_pending:
                # First real event after (re)open: its id is authoritative, so a
                # stale id from Controller.id after a hot-plug is corrected here.
                log.info(
                    "Controller bound to instance %s (opened as %s)",
                    event.instance_id,
                    self._instance_id,
                )
                self._instance_id = event.instance_id
                self._id_pending = False
                self._logged_mismatch_id = None
            else:
                # A genuinely foreign id: a second pad, or a duplicate from a pad
                # that enumerates twice. Drop it (log once) so it never doubles a
                # toggle or other action.
                if event.instance_id != self._logged_mismatch_id:
                    self._logged_mismatch_id = event.instance_id
                    log.debug(
                        "Dropping controller event from instance %s (bound to %s)",
                        event.instance_id,
                        self._instance_id,
                    )
                return False
        else:
            # Matched the bound id, so it is live: stop treating the id as
            # provisional (a duplicate under a different id is now a duplicate).
            self._id_pending = False
        if etype == pygame.CONTROLLERAXISMOTION:
            self._on_axis(event.axis, event.value)
            return False
        elif etype == pygame.CONTROLLERBUTTONDOWN:
            if event.button in self._buttons_down:
                # Duplicate press with no intervening release: ignore it so a pad
                # that delivers a button twice cannot fire the action twice.
                log.debug(
                    "Ignoring duplicate button-down %s (instance %s)",
                    event.button,
                    event.instance_id,
                )
                return False
            self._buttons_down.add(event.button)
            self.active_device = CONTROLLER
            log.debug("Button down %s (instance %s)", event.button, event.instance_id)
            self._on_button_down(event.button)
            return True
        elif etype == pygame.CONTROLLERBUTTONUP:
            if event.button not in self._buttons_down:
                return False  # stray/duplicate release
            self._buttons_down.discard(event.button)
            log.debug("Button up %s (instance %s)", event.button, event.instance_id)
            self._on_button_up(event.button)
            return True
        return False

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
        # Always drive the rumble engine so queued effects decay and expire even
        # when no controller is bound; the device send is guarded either way.
        self.rumble.tick(dt)
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
    def throttle_target(self) -> float:
        """Instantaneous trigger position, before smoothing. Press/release
        detection (e.g. the reverse shift gesture) must read this so a quick
        tap registers -- the smoothed reads above lag behind the trigger."""
        return self._throttle_target if self.active else 0.0

    @property
    def brake_target(self) -> float:
        return self._brake_target if self.active else 0.0

    @property
    def clutch(self) -> float:
        return self._clutch if self.active else 0.0

    def shutdown(self) -> None:
        self.rumble.reset()  # silence the pad before we drop it
        self._close_controller()
        if self._sdl is not None:
            with contextlib.suppress(Exception):  # pragma: no cover
                self._sdl.quit()
            self._sdl = None
