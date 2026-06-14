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

    def update(self, dt: float) -> None:
        pass

    def lines(self) -> list[str]:
        """Visible text for the window, mirroring what speech says."""
        return []


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
    intro_help = "Use up and down arrows to navigate, Enter to select, Escape to go back."

    def __init__(self, ctx: GameContext) -> None:
        super().__init__(ctx)
        self.items: list[MenuItem] = []
        self.index = 0

    def build_items(self) -> list[MenuItem]:
        raise NotImplementedError

    def enter(self) -> None:
        self.items = self.build_items()
        self.index = min(self.index, max(0, len(self.items) - 1))
        self.ctx.audio.play("ui/menu_open")
        self.announce_entry()

    def announce_entry(self) -> None:
        self.ctx.say(f"{self.title}. {self.current_text()}")

    def refresh(self, keep_index: bool = True) -> None:
        old = self.index
        self.items = self.build_items()
        self.index = min(old if keep_index else 0, max(0, len(self.items) - 1))

    def current_text(self) -> str:
        if not self.items:
            return "No options available."
        return f"{self.items[self.index].text}. {self.index + 1} of {len(self.items)}."

    def speak_current(self) -> None:
        self.ctx.say(self.current_text())

    def current_help(self) -> str:
        if not self.items:
            return self.intro_help
        item = self.items[self.index]
        item_help = item.help or f"Select {item.text}."
        return f"{self.intro_help} {item_help}".strip()

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
        elif event.unicode and event.unicode.isalnum():
            self._first_letter_jump(event.unicode.lower())

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
