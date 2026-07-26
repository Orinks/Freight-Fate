from dataclasses import dataclass
from enum import Enum

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

    def __init__(self) -> None:
        self.messages: list[Message] = []

        # None means show messages from every category.
        self.filter: MessageCategory | None = None

        # Position within the currently filtered list.
        # -1 means there is no current message.
        self.index = -1

    def add(self, text: str, category: MessageCategory) -> None:
        if not text:
            return

        old_filtered = self.filtered_messages()
        was_at_latest = (
            not old_filtered
            or self.index >= len(old_filtered) - 1
        )

        self.messages.append(Message(text, category))

        new_filtered = self.filtered_messages()

        # Follow new messages only when the reviewer was already at the end.
        if was_at_latest and new_filtered:
            self.index = len(new_filtered) - 1
        else:
            self._clamp_index()

    def filtered_messages(self) -> list[Message]:
        if self.filter is None:
            return self.messages

        return [
            message
            for message in self.messages
            if message.category is self.filter
        ]

    def current_message(self) -> Message | None:
        messages = self.filtered_messages()

        if not messages:
            self.index = -1
            return None

        self._clamp_index()
        return messages[self.index]

    def previous_message(self) -> Message | None:
        messages = self.filtered_messages()

        if not messages:
            self.index = -1
            return None

        if self.index <= 0: return None
        self.index -= 1

        return messages[self.index]

    def next_message(self) -> Message | None:
        messages = self.filtered_messages()

        if not messages:
            self.index = -1
            return None

        if self.index >= len(messages) - 1: return None
        self.index += 1

        return messages[self.index]

    def first_message(self) -> Message | None:
        messages = self.filtered_messages()

        if not messages:
            self.index = -1
            return None

        self.index = 0
        return messages[self.index]

    def last_message(self) -> Message | None:
        messages = self.filtered_messages()

        if not messages:
            self.index = -1
            return None

        self.index = len(messages) - 1
        return messages[self.index]

    def previous_category(self) -> str | None:
        position = self._FILTERS.index(self.filter)
        if position <= 0: return None
        self.filter = self._FILTERS[position-1]
                self._move_to_latest()
        return self.category_name()

    def next_category(self) -> str | None:
        position = self._FILTERS.index(self.filter)
        if position >= len(self._FILTERS)-1: return None
        self.filter = self._FILTERS[position + 1]
        self._move_to_latest()
        return self.category_name()

    def category_name(self) -> str:
        if self.filter is None:
            return "All"

        return self.filter.value.capitalize()

    def _move_to_latest(self) -> None:
        messages = self.filtered_messages()

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
