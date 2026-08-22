"""An accessible text field: characters echo as you type, and a review
cursor lets you check what you typed without retyping it.

Extracted from the new-career name entry so the Radio app's station search
could share it; anything that asks a blind player to type a short string
should ride this rather than grow its own key handling.
"""

from __future__ import annotations

import pygame

from .base import State, spoken_char


class TextEntryState(State):
    """Accessible text entry: characters are echoed as you type.

    A review cursor tracks where in the typed text the player currently is
    (``self.cursor``, a gap position from 0 to ``len(self.name)``, the same
    way an OS text field's caret works). Left and Right step the cursor one
    character and speak whatever character sits between the old and new
    position -- the standard way a screen reader lets a player check what
    they typed without retyping it. Home and End jump to either end and speak
    the character now there. Typing and Backspace act at the cursor, not just
    at the end, so a player who arrows back to fix a letter edits in place
    instead of being surprised that Backspace deletes from the end regardless
    of where they were reviewing.

    Subclasses set ``heading`` and ``field_label`` for the visual lines,
    speak their own prompt in ``enter``, and act on Enter in ``_confirm``.
    """

    MAX_LEN = 24
    heading = "Text entry"
    field_label = "Text"
    captures_text_input = True  # keep typed commas; the global repeat key yields

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.name = ""
        self.cursor = 0

    def enter(self) -> None:
        self.ctx.say(
            f"{self.heading}. Type, then press Enter. "
            "Left and right arrows review the letters you have typed, "
            "Home and End jump to the start or end. Press Escape to cancel."
        )

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.ctx.audio.play("ui/menu_back")
            self.ctx.pop_state()
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._confirm()
        elif event.key == pygame.K_BACKSPACE:
            self._backspace()
        elif event.key == pygame.K_LEFT:
            self._move_cursor(-1)
        elif event.key == pygame.K_RIGHT:
            self._move_cursor(1)
        elif event.key == pygame.K_HOME:
            self._jump_cursor(0, "Start")
        elif event.key == pygame.K_END:
            self._jump_cursor(len(self.name), "End")
        elif event.key == pygame.K_F2:
            self.ctx.say(self.name if self.name else "Empty.", review=False)
        elif event.unicode and event.unicode.isprintable() and len(self.name) < self.MAX_LEN:
            self._insert(event.unicode)

    def _insert(self, ch: str) -> None:
        self.name = self.name[: self.cursor] + ch + self.name[self.cursor :]
        self.cursor += 1
        self.ctx.audio.play("ui/tick")
        self.ctx.say(spoken_char(ch), review=False)

    def _backspace(self) -> None:
        if self.cursor == 0:
            self.ctx.audio.play("ui/error")
            return
        removed = self.name[self.cursor - 1]
        self.name = self.name[: self.cursor - 1] + self.name[self.cursor :]
        self.cursor -= 1
        self.ctx.say(f"Deleted {spoken_char(removed)}. " + (self.name or "Empty."), review=False)

    def _move_cursor(self, delta: int) -> None:
        """Step the review cursor one character left or right.

        Both directions speak the character that sat between the old and new
        cursor position -- the character just moved over -- matching how a
        screen reader announces caret movement in a plain text field.
        """
        new_cursor = self.cursor + delta
        if new_cursor < 0 or new_cursor > len(self.name):
            self.ctx.audio.play("ui/error")
            return
        spoken_index = min(self.cursor, new_cursor)
        self.cursor = new_cursor
        self.ctx.say(spoken_char(self.name[spoken_index]), review=False)

    def _jump_cursor(self, target: int, label: str) -> None:
        if self.cursor == target:
            self.ctx.audio.play("ui/error")
            return
        self.cursor = target
        if not self.name:
            self.ctx.say(f"{label}. Empty.", review=False)
            return
        edge = self.name[0] if target == 0 else self.name[-1]
        self.ctx.say(f"{label}. {spoken_char(edge)}", review=False)

    def _confirm(self) -> None:
        raise NotImplementedError

    def lines(self) -> list[str]:
        marked = self.name[: self.cursor] + "|" + self.name[self.cursor :]
        return [
            self.heading,
            "",
            f"{self.field_label}: {marked}",
            "Left and right arrows review letters, Home and End jump to the "
            "ends. Enter to confirm, Escape to cancel, F2 to hear the whole text.",
        ]
