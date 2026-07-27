"""One definition of what a spoken-text stub looks like.

Tests capture speech by replacing ``ctx.say`` and ``ctx.say_event`` with a
stand-in that records what was said. Writing that stand-in inline meant the
signature was copied into well over a hundred tests, so adding a keyword to
the real method -- the message log's ``review`` flag was the last one --
broke a scatter of tests that had nothing to do with the change.

The signature lives here now. Adding a keyword to ``GameContext.say`` is one
edit in this file.

Typical use, unchanged from the inline lambdas it replaces::

    spoken: list[str] = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))

    events: list[tuple[str, bool]] = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(events, with_interrupt=True))
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def speech_stub(
    sink: list[Any] | None = None,
    *,
    tag: str | None = None,
    with_interrupt: bool = False,
    prefix: str = "",
    record: Callable[[str, bool], None] | None = None,
) -> Callable[..., None]:
    """A stand-in for ``GameContext.say`` / ``say_event`` that records calls.

    ``sink`` collects what was said, or is left out entirely to swallow the
    speech. What lands in it depends on what the test needs to assert:

    - by default, the spoken text alone;
    - ``with_interrupt=True`` for ``(text, interrupt)``, when the test cares
      whether a line cut off the one before it;
    - ``tag="event"`` to label the channel, for tests that capture both
      channels into one list and assert on their order;
    - ``prefix`` to mark the line itself, for the playtest harness, whose
      transcript is read back as one block of text.

    ``record`` takes over entirely, for a caller that keeps something richer
    than a list of lines. It still belongs here rather than in a hand-written
    stub, so that ``ctx.say``'s signature has exactly one definition.
    """

    def _speak(text: str, interrupt: bool = True, review: bool = True) -> None:
        if record is not None:
            record(text, interrupt)
            return
        if sink is None:
            return
        line = f"{prefix}{text}" if prefix else text
        if tag is not None:
            sink.append((tag, line, interrupt) if with_interrupt else (tag, line))
        else:
            sink.append((line, interrupt) if with_interrupt else line)

    return _speak
