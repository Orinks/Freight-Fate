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


class TimedMessageState(State):
    """A brief, spoken transition that ignores stray held navigation keys."""

    def __init__(
        self,
        ctx: GameContext,
        *,
        title: str,
        message: str,
        status: str,
        seconds: float,
        on_complete: Callable[[], None],
        complete_text: str = "",
        sound_key: str = "ui/notify",
    ) -> None:
        super().__init__(ctx)
        self.title = title
        self.message = message
        self.status = status
        self.seconds = max(0.0, seconds)
        self.remaining = self.seconds
        self.on_complete = on_complete
        self.complete_text = complete_text
        self.sound_key = sound_key
        self._complete = False

    def enter(self) -> None:
        if self.sound_key:
            self.ctx.audio.play(self.sound_key)
        self.ctx.say(self.message, interrupt=True)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (
            pygame.K_F1,
            pygame.K_ESCAPE,
            pygame.K_RETURN,
            pygame.K_SPACE,
            pygame.K_KP_ENTER,
        ):
            self.ctx.say(self.status)

    def update(self, dt: float) -> None:
        super().update(dt)
        if self._complete:
            return
        self.remaining = max(0.0, self.remaining - dt)
        if self.remaining > 0.0:
            return
        self._complete = True
        if self.complete_text:
            self.ctx.say(self.complete_text, interrupt=False)
        self.on_complete()

    def lines(self) -> list[str]:
        return [
            self.title,
            "",
            self.status,
            f"Ready in {self.remaining:.1f} seconds.",
        ]


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
