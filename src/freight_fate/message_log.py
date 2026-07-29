"""The reviewable log of everything the game has said.

One log backs every review control. ``GameContext.say`` and ``say_event`` file
each spoken line here under its category, and ``State.handle_message_review``
walks it. Text the player does not need to review a second time -- menu items
as they arrow past them, the review announcements themselves -- is spoken with
``review=False`` and never reaches the log, which is what keeps navigation
noise out of the history.
"""

import time
from dataclasses import dataclass
from enum import Enum

# How many messages to keep. Long careers speak a lot, and a log that grows for
# the whole session is both unbounded memory and a history nobody can walk.
DEFAULT_LIMIT = 200

# How long a review session stays open after the last review key. Inside the
# window the player is browsing, so new speech must not drag the cursor out
# from under them. Outside it they have gone back to driving, and the next
# press means "repeat what was just said" rather than "resume where I left
# off twenty messages ago".
REVIEW_WINDOW_S = 10.0


class MessageCategory(Enum):
    GENERAL = "general"
    EVENT = "event"


@dataclass
class Message:
    text: str
    category: MessageCategory


class MessageLog:
    _FILTERS = (
        None,
        MessageCategory.GENERAL,
        MessageCategory.EVENT,
    )

    def __init__(self, limit: int = DEFAULT_LIMIT, clock=None) -> None:
        self.messages: list[Message] = []
        self.limit = limit
        self._clock = clock or time.monotonic

        # When the last review key was pressed, or None if the player has not
        # reviewed yet. Drives the review-session window.
        self._reviewed_at: float | None = None

        # None means show messages from every category.
        self.filter: MessageCategory | None = None

        # Position within the currently filtered list.
        # -1 means there is no current message.
        self.index = -1

        # True while the cursor sits on a message the player has not reviewed
        # yet. The first press of the back key then re-speaks it rather than
        # stepping past it, so the key reads as "repeat what was just said"
        # before it reads as "go back one".
        self._fresh = False

    def add(self, text: str, category: MessageCategory) -> None:
        if not text:
            return
        # The same line twice running is one thing to review, not two: a status
        # key pressed twice should not make the reviewer step over a duplicate.
        if self.messages and self.messages[-1].text == text:
            return

        old_filtered = self.filtered_messages()
        was_at_latest = not old_filtered or self.index >= len(old_filtered) - 1
        current = old_filtered[self.index] if 0 <= self.index < len(old_filtered) else None

        self.messages.append(Message(text, category))
        self._trim()

        new_filtered = self.filtered_messages()

        # Follow new messages only when the reviewer was already at the end.
        if was_at_latest and new_filtered:
            self.index = len(new_filtered) - 1
            self._fresh = True
        else:
            # Trimming can drop messages from under a reviewer who has walked
            # back, so track the message itself rather than its old position.
            self.index = self._locate(current, new_filtered)

    def filtered_messages(self) -> list[Message]:
        if self.filter is None:
            return self.messages

        return [message for message in self.messages if message.category is self.filter]

    def current_message(self) -> Message | None:
        messages = self.filtered_messages()

        if not messages:
            self.index = -1
            return None

        self._clamp_index()
        return messages[self.index]

    def _begin_review(self) -> None:
        """Open or extend a review session.

        A press that arrives after the window has closed starts over: back at
        the newest message, showing every category. Without this a player who
        glanced at the history mid-run stays parked there for the rest of the
        drive, and the next press reads them something from twenty messages
        ago -- or, with a category filter still set, silently hides half of
        what has happened since.
        """
        now = self._clock()
        lapsed = self._reviewed_at is None or now - self._reviewed_at > REVIEW_WINDOW_S
        self._reviewed_at = now
        if lapsed:
            self.filter = None
            self._move_to_latest()

    def message_in_review(self) -> Message | None:
        """The message a review action acts on, opening a session first.

        ``current_message`` stays a plain query; this is what a key press
        should use, so copying after a long silence copies what was just said
        rather than wherever the cursor was left.
        """
        self._begin_review()
        return self.current_message()

    def previous_message(self) -> Message | None:
        self._begin_review()
        messages = self.filtered_messages()

        if not messages:
            self.index = -1
            return None

        # The first press after new speech repeats it instead of stepping back.
        if self._fresh:
            self._fresh = False
            self._clamp_index()
            return messages[self.index]

        if self.index <= 0:
            return None
        self.index -= 1

        return messages[self.index]

    def next_message(self) -> Message | None:
        self._begin_review()
        messages = self.filtered_messages()
        self._fresh = False

        if not messages:
            self.index = -1
            return None

        if self.index >= len(messages) - 1:
            return None
        self.index += 1

        return messages[self.index]

    def first_message(self) -> Message | None:
        self._begin_review()
        messages = self.filtered_messages()
        self._fresh = False

        if not messages:
            self.index = -1
            return None

        self.index = 0
        return messages[self.index]

    def last_message(self) -> Message | None:
        self._begin_review()
        messages = self.filtered_messages()
        self._fresh = False

        if not messages:
            self.index = -1
            return None

        self.index = len(messages) - 1
        return messages[self.index]

    def position_from_latest(self) -> int:
        """How many messages back the cursor sits, 0 being the newest."""
        messages = self.filtered_messages()

        if not messages or self.index < 0:
            return 0

        return max(0, len(messages) - 1 - self.index)

    def previous_category(self) -> str | None:
        self._begin_review()
        position = self._FILTERS.index(self.filter)
        if position <= 0:
            return None
        self.filter = self._FILTERS[position - 1]
        self._move_to_latest()
        return self.category_name()

    def next_category(self) -> str | None:
        self._begin_review()
        position = self._FILTERS.index(self.filter)
        if position >= len(self._FILTERS) - 1:
            return None
        self.filter = self._FILTERS[position + 1]
        self._move_to_latest()
        return self.category_name()

    def category_name(self) -> str:
        if self.filter is None:
            return "All"

        return self.filter.value.capitalize()

    def _trim(self) -> None:
        if self.limit > 0 and len(self.messages) > self.limit:
            del self.messages[: len(self.messages) - self.limit]

    @staticmethod
    def _locate(message: Message | None, messages: list[Message]) -> int:
        if not messages:
            return -1
        if message is not None:
            for position, candidate in enumerate(messages):
                if candidate is message:
                    return position
        # The message the player was on has aged out; the oldest kept one is
        # the closest place to leave them.
        return 0

    def _move_to_latest(self) -> None:
        messages = self.filtered_messages()
        # Landing on a category shows its newest message, which the player has
        # not heard in this category yet.
        self._fresh = bool(messages)

        if messages:
            self.index = len(messages) - 1
        else:
            self.index = -1

    def _clamp_index(self) -> None:
        messages = self.filtered_messages()

        if not messages:
            self.index = -1
        elif self.index < 0:
            self.index = 0
        elif self.index >= len(messages):
            self.index = len(messages) - 1
