"""State machine foundation and the accessible menu base class.

Every screen is a ``State`` on the app's state stack. ``MenuState`` provides
fully speech-driven list navigation: arrow keys with wrap-around, Home/End,
first-letter jumping, Enter to activate, Escape to go back, and F1 to repeat
contextual help. Each state also exposes ``lines()`` — visible text mirroring
the speech output for low-vision players and sighted helpers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from ..app import GameContext


def end_sentence(text: str) -> str:
    """A spoken fragment ending in exactly one sentence mark, never two.

    Menu/list labels are sometimes plain ("Sleep 10 hours") and sometimes whole
    sentences that already end in a period (settlement summary lines). Appending
    "." unconditionally produces ".." which a screen reader voices as "dot dot",
    so add the period only when one is not already there."""
    text = text.rstrip()
    return text if text.endswith((".", "!", "?", ":")) else text + "."


class State:
    """Base class for all game screens."""

    def __init__(self, ctx: GameContext) -> None:
        self.ctx = ctx

    def enter(self) -> None:
        """Called when the state becomes active (pushed or revealed)."""

    def exit(self) -> None:
        """Called when the state is removed from the stack."""

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    # Controller buttons a plain keyboard-driven state understands, translated
    # into the key events it already handles. This keeps simple screens (update
    # prompts, name entry, the help reader) usable from a controller without
    # bespoke code. MenuState and the driving state override this entirely.
    _CONTROLLER_KEYS = None  # built lazily to avoid importing pygame constants early

    def handle_controller(self, event: pygame.event.Event, manager) -> None:
        if event.type != pygame.CONTROLLERBUTTONDOWN:
            return
        keys = State._controller_key_map()
        key = keys.get(event.button)
        if key is not None:
            self.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=""))

    @staticmethod
    def _controller_key_map() -> dict[int, int]:
        if State._CONTROLLER_KEYS is None:
            State._CONTROLLER_KEYS = {
                pygame.CONTROLLER_BUTTON_A: pygame.K_RETURN,
                pygame.CONTROLLER_BUTTON_B: pygame.K_ESCAPE,
                pygame.CONTROLLER_BUTTON_BACK: pygame.K_F1,
                pygame.CONTROLLER_BUTTON_DPAD_UP: pygame.K_UP,
                pygame.CONTROLLER_BUTTON_DPAD_DOWN: pygame.K_DOWN,
                pygame.CONTROLLER_BUTTON_DPAD_LEFT: pygame.K_LEFT,
                pygame.CONTROLLER_BUTTON_DPAD_RIGHT: pygame.K_RIGHT,
            }
        return State._CONTROLLER_KEYS

    def on_controller_disconnect(self) -> None:
        """Called when the active controller is unplugged. The driving state
        pauses; menus keep going on the keyboard."""

    def update(self, dt: float) -> None:
        update_music_rotation = getattr(self.ctx, "update_music_rotation", None)
        if update_music_rotation is not None:
            update_music_rotation(dt)

    def lines(self) -> list[str]:
        """Visible text for the window, mirroring what speech says."""
        return []

    def presence(self):
        """Broad, privacy-safe activity for Discord Rich Presence, or None.

        Returns a :class:`~freight_fate.discord_presence.PresenceState` (or
        ``None`` to leave presence unchanged). The app polls the active state
        each frame and hands the result to the presence service; states only
        report status here and never touch Discord itself.
        """
        return None


@dataclass
class MenuItem:
    label: str | Callable[[], str]
    action: Callable[[], None]
    help: str = ""

    @property
    def text(self) -> str:
        return self.label() if callable(self.label) else self.label


class MenuState(State):
    """A vertically navigated, fully spoken menu."""

    title = "Menu"
    intro_help = (
        "Use up and down arrows to navigate, Enter to select, Escape to go back. "
        "Left or Right Control stops the current speech."
    )
    open_sound_key = "ui/menu_open"

    def __init__(self, ctx: GameContext) -> None:
        super().__init__(ctx)
        self.items: list[MenuItem] = []
        self.index = 0

    def build_items(self) -> list[MenuItem]:
        raise NotImplementedError

    def enter(self) -> None:
        self.items = self.build_items()
        self.index = min(self.index, max(0, len(self.items) - 1))
        self.ctx.audio.play(self.open_sound_key)
        self.announce_entry()

    def announce_entry(self) -> None:
        self.ctx.say(f"{end_sentence(self.title)} {self.current_text()}")

    def refresh(self, keep_index: bool = True) -> None:
        old = self.index
        self.items = self.build_items()
        self.index = min(old if keep_index else 0, max(0, len(self.items) - 1))

    def current_text(self) -> str:
        if not self.items:
            return "No options available."
        label = end_sentence(self.items[self.index].text)
        if not getattr(self.ctx.settings, "announce_menu_position", True):
            return label
        return f"{label} {self.index + 1} of {len(self.items)}."

    def speak_current(self) -> None:
        self.ctx.say(self.current_text())

    def current_help(self) -> str:
        if not self.items:
            return self.intro_help
        item = self.items[self.index]
        return item.help or f"{item.text}."

    def move(self, delta: int) -> None:
        if not self.items:
            return
        self.index = (self.index + delta) % len(self.items)
        self.ctx.audio.play("ui/menu_move")
        self.speak_current()

    def jump(self, index: int) -> None:
        if not self.items:
            return
        self.index = max(0, min(index, len(self.items) - 1))
        self.ctx.audio.play("ui/menu_move")
        self.speak_current()

    def activate(self) -> None:
        if not self.items:
            return
        self.ctx.audio.play("ui/menu_select")
        self.items[self.index].action()

    def go_back(self) -> None:
        self.ctx.audio.play("ui/menu_back")
        self.ctx.pop_state()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        key = event.key
        if key == pygame.K_DOWN:
            self.move(1)
        elif key == pygame.K_UP:
            self.move(-1)
        elif key == pygame.K_HOME:
            self.jump(0)
        elif key == pygame.K_END:
            self.jump(len(self.items) - 1)
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            self.activate()
        elif key == pygame.K_ESCAPE:
            self.go_back()
        elif key == pygame.K_F1:
            self.ctx.say(self.current_help())
        elif key in (pygame.K_LCTRL, pygame.K_RCTRL):
            self.ctx.stop_speech()
        elif event.unicode and event.unicode.isalnum():
            self._first_letter_jump(event.unicode.lower())

    # -- controller -----------------------------------------------------------

    # Menus opt into held D-pad left/right auto-repeat for adjusting options.
    wants_controller_repeat = True

    def adjust(self, direction: int) -> None:
        """Change the current option (D-pad left/right). No-op unless the menu
        has adjustable options; ``SettingsCategoryState`` overrides this."""

    def handle_controller(self, event: pygame.event.Event, manager) -> None:
        from ..controller import ControllerAction

        action = manager.menu_action(event)
        if action == ControllerAction.MENU_DOWN:
            self.move(1)
        elif action == ControllerAction.MENU_UP:
            self.move(-1)
        elif action == ControllerAction.ADJUST_RIGHT:
            self.adjust(1)
        elif action == ControllerAction.ADJUST_LEFT:
            self.adjust(-1)
        elif action == ControllerAction.CONFIRM:
            self.activate()
        elif action == ControllerAction.BACK:
            self.go_back()
        elif action == ControllerAction.HELP:
            self.ctx.say(self.current_help())

    def _first_letter_jump(self, char: str) -> None:
        if not self.items:
            return
        n = len(self.items)
        for offset in range(1, n + 1):
            i = (self.index + offset) % n
            if self.items[i].text.lower().startswith(char):
                self.index = i
                self.ctx.audio.play("ui/menu_move")
                self.speak_current()
                return

    def lines(self) -> list[str]:
        out = [self.title, ""]
        for i, item in enumerate(self.items):
            marker = "> " if i == self.index else "  "
            out.append(marker + item.text)
        return out
