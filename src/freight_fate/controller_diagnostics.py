"""Controller input diagnostic tool.

Freight Fate reads controllers through SDL's *GameController* API
(``pygame._sdl2.controller``), which remaps any recognized pad onto the Xbox
button layout. On some pads -- notably the DualSense -- the D-pad, sticks, stick
clicks, and face buttons come through, but the triggers and shoulder buttons do
not. That is the signature of an SDL controller-*mapping* gap for that specific
device: the raw pad may still be emitting those inputs on the lower *joystick*
layer, but SDL never surfaces them as GameController events.

To tell those cases apart, this tool listens on **both** layers at once and logs
them side by side:

* ``[GC ]`` -- the GameController (``CONTROLLER*``) events, exactly what the game
  itself sees.
* ``[JOY]`` -- the raw joystick (``JOY*``) events plus each device's GUID, name,
  and axis/button counts, i.e. what SDL actually delivers before mapping.

Press LT/RT/LB/RB on the problem pad and read which layer (if any) reports them:

* ``[JOY]`` only  -> a mapping gap; fixable via an ``SDL_GAMECONTROLLERCONFIG``
  mapping or a HIDAPI hint.
* neither         -> the input never reaches SDL.
* both            -> the issue is elsewhere in the game's input path.

Everything is printed to the terminal and written to ``controller-diagnostics.log``
in the current directory (overwritten on each launch). Exit with Ctrl+C; the log
file is left in place for review.
"""

from __future__ import annotations

import contextlib
import logging
import os
from pathlib import Path

LOG_FILENAME = "controller-diagnostics.log"

# The game normalizes analog axes against this; we report both raw and
# normalized so the numbers line up with what controller.py works with.
AXIS_MAX = 32767.0

log = logging.getLogger("freight_fate.controller_diagnostics")


def _prepare_environment() -> None:
    """Reproduce the game's pre-``pygame.init()`` environment.

    These hints change how SDL binds PlayStation pads (they opt the DS4/DualSense
    into HIDAPI), so matching them here keeps the diagnostic honest: the pad is
    enumerated exactly as it is when the game runs. Mirrors ``app.App.__init__``.
    """
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    os.environ.setdefault("SDL_JOYSTICK_HIDAPI_PS4_RUMBLE", "1")
    os.environ.setdefault("SDL_JOYSTICK_HIDAPI_PS5_RUMBLE", "1")


def _configure_logging(log_path: Path) -> None:
    """Log to the terminal and to a fresh file (overwritten each launch)."""
    fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(fmt)

    log.setLevel(logging.INFO)
    log.handlers = [stream, file_handler]
    log.propagate = False


def _build_reverse_map(prefix: str) -> dict[int, str]:
    """Map pygame constant values back to friendly names for a given prefix.

    e.g. ``CONTROLLER_BUTTON_`` -> ``{0: "a", 1: "b", ...}`` so an event's button
    index prints as a name instead of a bare number.
    """
    import pygame

    mapping: dict[int, str] = {}
    for name in dir(pygame):
        if name.startswith(prefix):
            value = getattr(pygame, name)
            if isinstance(value, int):
                mapping.setdefault(value, name[len(prefix) :].lower())
    return mapping


def _hat_str(value: tuple[int, int]) -> str:
    x, y = value
    vertical = {1: "up", -1: "down"}.get(y, "")
    horizontal = {1: "right", -1: "left"}.get(x, "")
    label = " ".join(part for part in (vertical, horizontal) if part) or "centered"
    return f"{value} ({label})"


def _log_inventory(sdl_controller, pygame) -> None:
    """Print a one-time snapshot of every device on both layers.

    The joystick GUID plus axis/button counts are the decisive clues for a
    mapping gap: a DualSense with the "wrong" GUID or an unexpected axis count is
    exactly what SDL fails to map onto the trigger/shoulder controls.
    """
    log.info("=== Device inventory ===")

    gc_count = sdl_controller.get_count()
    log.info("SDL sees %d device slot(s).", gc_count)
    for index in range(gc_count):
        is_ctrl = sdl_controller.is_controller(index)
        try:
            name = sdl_controller.name_forindex(index) or "unknown"
        except Exception:  # pragma: no cover - driver dependent
            name = "unknown"
        log.info(
            "  slot %d: recognized as GameController=%s, name=%r",
            index,
            is_ctrl,
            name,
        )

    joy_count = pygame.joystick.get_count()
    log.info("Raw joystick layer sees %d device(s).", joy_count)
    for index in range(joy_count):
        joy = pygame.joystick.Joystick(index)
        with contextlib.suppress(Exception):  # pragma: no cover - driver dependent
            joy.init()
        try:
            power = joy.get_power_level()
        except Exception:  # pragma: no cover - not on every backend
            power = "unknown"
        log.info(
            "  joystick %d: name=%r guid=%s axes=%d buttons=%d hats=%d power=%s",
            index,
            joy.get_name(),
            joy.get_guid(),
            joy.get_numaxes(),
            joy.get_numbuttons(),
            joy.get_numhats(),
            power,
        )
    log.info("=== Press controls now. Triggers=LT/RT, shoulders=LB/RB. Ctrl+C to exit. ===")


def _open_controllers(sdl_controller) -> list:
    """Open every recognized GameController so it emits CONTROLLER* events.

    Same open pattern as ``controller.ControllerManager._open_first``, but we
    bind *all* of them rather than just the first, so a diagnostic session covers
    whatever the tester has plugged in.
    """
    controllers = []
    for index in range(sdl_controller.get_count()):
        if sdl_controller.is_controller(index):
            try:
                controllers.append(sdl_controller.Controller(index))
            except Exception:  # pragma: no cover - driver dependent
                log.warning("Could not open GameController at slot %d", index, exc_info=True)
    return controllers


def _run_loop(pygame, axis_names: dict[int, str], button_names: dict[int, str]) -> None:
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            etype = event.type

            if etype == pygame.QUIT:
                return

            # -- GameController layer (what the game sees) --------------------
            elif etype == pygame.CONTROLLERAXISMOTION:
                name = axis_names.get(event.axis, f"axis{event.axis}")
                log.info(
                    "[GC ] AXIS  %-13s raw=%+6d norm=%+.3f (device %s)",
                    name,
                    event.value,
                    event.value / AXIS_MAX,
                    event.instance_id,
                )
            elif etype in (pygame.CONTROLLERBUTTONDOWN, pygame.CONTROLLERBUTTONUP):
                action = "DOWN" if etype == pygame.CONTROLLERBUTTONDOWN else "UP  "
                name = button_names.get(event.button, f"button{event.button}")
                log.info(
                    "[GC ] BTN   %-13s %s (device %s)",
                    name,
                    action,
                    event.instance_id,
                )
            elif etype == pygame.CONTROLLERDEVICEADDED:
                log.info("[GC ] device added (slot %s)", getattr(event, "device_index", "?"))
            elif etype == pygame.CONTROLLERDEVICEREMOVED:
                log.info("[GC ] device removed (device %s)", getattr(event, "instance_id", "?"))

            # -- Raw joystick layer (what SDL delivers pre-mapping) ----------
            elif etype == pygame.JOYAXISMOTION:
                log.info(
                    "[JOY] AXIS  index=%-2d value=%+.3f (device %s)",
                    event.axis,
                    event.value,
                    event.instance_id,
                )
            elif etype in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                action = "DOWN" if etype == pygame.JOYBUTTONDOWN else "UP  "
                log.info(
                    "[JOY] BTN   index=%-2d %s (device %s)",
                    event.button,
                    action,
                    event.instance_id,
                )
            elif etype == pygame.JOYHATMOTION:
                log.info(
                    "[JOY] HAT   index=%-2d %s (device %s)",
                    event.hat,
                    _hat_str(event.value),
                    event.instance_id,
                )
            elif etype == pygame.JOYDEVICEADDED:
                joy = pygame.joystick.Joystick(event.device_index)
                joy.init()
                log.info(
                    "[JOY] device added: name=%r guid=%s",
                    joy.get_name(),
                    joy.get_guid(),
                )
            elif etype == pygame.JOYDEVICEREMOVED:
                log.info("[JOY] device removed (device %s)", getattr(event, "instance_id", "?"))

        clock.tick(60)


def main() -> int:
    _prepare_environment()

    log_path = Path.cwd() / LOG_FILENAME
    _configure_logging(log_path)

    import pygame

    log.info("Controller diagnostics starting.")
    log.info("Logging to %s (overwritten on each launch).", log_path)

    pygame.init()
    pygame.display.set_caption("Freight Fate - Controller Diagnostics")
    # A visible window keeps the OS event pump alive; on Windows, controller and
    # joystick events are not delivered reliably to a windowless process.
    pygame.display.set_mode((480, 160))

    # Both input layers, initialized together so the same physical pad reports on
    # each: the GameController layer the game uses, and the raw joystick layer.
    from pygame._sdl2 import controller as sdl_controller

    sdl_controller.init()
    pygame.joystick.init()

    controllers = _open_controllers(sdl_controller)
    _log_inventory(sdl_controller, pygame)

    axis_names = _build_reverse_map("CONTROLLER_AXIS_")
    button_names = _build_reverse_map("CONTROLLER_BUTTON_")

    try:
        _run_loop(pygame, axis_names, button_names)
    except KeyboardInterrupt:
        log.info("Interrupted (Ctrl+C). Exiting.")
    finally:
        controllers.clear()  # drop references before quitting SDL
        pygame.quit()
        log.info("Controller diagnostics stopped. Log saved to %s", log_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
