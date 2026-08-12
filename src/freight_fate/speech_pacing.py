"""Pacing, repeat suppression, and priority for the driving event voice.

The event channel is a queue the game cannot inspect: it hands lines to a
voice that speaks them in submission order, and nothing in Prism will say
what is still waiting. Three things go wrong when the road talks straight
into it, all three reported from the same tester transcript (2026-08-11):

* **The same moment said several times.** A code path that notices something
  runs every frame, so one sideswipe arrives as three identical lines inside
  half a second.
* **A standing condition read out forever.** A damaged load, an engine held
  at redline -- the truck is still in that state, so the warning fires again
  every few seconds for the rest of the drive. The player needs it when it
  starts and again when it gets worse, not on a loop.
* **The line that mattered buried.** The stop the player planned waits behind
  weather, tolls, and traffic chatter, and is still waiting when the exit has
  gone by.

:class:`EventSpeechPacer` answers all three from one place.

Its original job -- and still its core -- is the backlog projection: each
submitted line extends a projected clear time by its estimated speaking
duration, so the game knows roughly when the voice falls silent. A queued
line that would START speaking more than its priority's budget after the
moment it described is by definition stale, and the caller delivers it
interrupting instead, which purges the dead backlog. Interrupting lines
reset the projection to truth, so estimate drift never outlives one backlog.

On top of that it remembers what the player has already heard (so a repeat
inside ``REPEAT_WINDOW_S`` never reaches the voice twice), what each standing
condition last said (so it speaks again only when it has something new to
say), and how long a line of each priority is willing to wait -- a route
announcement waits a moment behind chatter and then goes ahead of it.

Durations are estimated from text length at a conservative default-voice
speaking rate. A faster voice just flushes a little less eagerly than it
could; a slower one flushes a little late but stays bounded -- either way the
player never again waits through a paragraph of expired narration.
"""

from __future__ import annotations

import time
from enum import IntEnum


class EventPriority(IntEnum):
    """How long a line is willing to wait behind what is already speaking.

    ``AMBIENT`` is the running commentary of the road -- weather, tolls, state
    lines, roadside colour. Missing one costs the player nothing.

    ``ROUTE`` is the drive itself: the stop the player planned, the exit they
    have to take. It gets a much shorter patience than chatter, so it goes
    ahead of a backlog rather than behind it.

    ``CRITICAL`` is a warning to act on now. It is always delivered
    interrupting, so it never consults the budget at all.
    """

    AMBIENT = 0
    ROUTE = 1
    CRITICAL = 2


class EventSpeechPacer:
    """Keeps the dedicated event voice from performing the past.

    See the module docstring for the whole picture. The caller's contract:

    * ``is_repeat`` decides whether the player has already heard this; a True
      means say nothing at all.
    * ``note_spoken`` records a line that did reach the voice.
    * ``note_interrupt`` for an interrupting line (it purges the channel), or
      ``should_flush`` for a queued one -- True there means the backlog has
      gone stale and this line must be submitted interrupting instead.
    * ``pause``/``resume`` around a screen that takes the player off the road.
    """

    STALE_WAIT_S = 3.0  # a queued line may start at most this far in the past
    BASE_UTTERANCE_S = 0.4  # per-utterance pause before the voice gets going
    CHARS_PER_S = 13.0  # the default Windows voice at its default rate

    # Two identical lines this close together are one thing happening, not
    # two, whichever code path noticed it. Deliberately short: it collapses a
    # burst of frames without ever swallowing the second press of a key the
    # player pushed on purpose.
    REPEAT_WINDOW_S = 2.5

    # How long a line of each priority will wait behind a backlog before it
    # is better to purge the channel and speak now. Route announcements have
    # almost no patience: a planned stop that arrives after its exit is worse
    # than a piece of chatter cut off mid-word.
    WAIT_BUDGET_S = {
        EventPriority.AMBIENT: STALE_WAIT_S,
        EventPriority.ROUTE: 0.8,
        EventPriority.CRITICAL: STALE_WAIT_S,
    }

    # Bound on the remembered-lines map, so a long career cannot grow it
    # without limit.
    RECENT_LIMIT = 256
    RECENT_MEMORY_S = 300.0

    def __init__(self, clock=None) -> None:
        self._clock = clock or time.monotonic
        self._clear_at = 0.0
        # text -> when the player last heard it.
        self._recent: dict[str, float] = {}
        # condition key -> the last thing said about it.
        self._conditions: dict[str, str] = {}
        # Set by pause(): the next line purges the channel, so anything the
        # voice was still holding when the player stepped away cannot surface
        # behind it.
        self._purge_next = False

    def _duration_s(self, text: str) -> float:
        return self.BASE_UTTERANCE_S + len(text) / self.CHARS_PER_S

    # -- what the player has already heard ---------------------------------------

    def is_repeat(
        self,
        text: str,
        *,
        key: str | None = None,
        force: bool = False,
        window: float | None = None,
    ) -> bool:
        """True when saying this again would tell the player nothing new.

        ``key`` names a standing condition -- a state of the world rather than
        a moment in it. A condition speaks when it starts and again only when
        what there is to say about it has changed, so a worsening number is
        news and the same number is not.

        ``force`` is for a line the player asked for: a status key, a
        deliberate replay. It is always heard.
        """
        if force or not text:
            return False
        if key is not None and self._conditions.get(key) == text:
            return True
        budget = self.REPEAT_WINDOW_S if window is None else window
        if budget <= 0.0:
            return False
        last = self._recent.get(text)
        return last is not None and self._clock() - last < budget

    def note_spoken(self, text: str, *, key: str | None = None) -> None:
        """Record a line that reached the voice."""
        if not text:
            return
        now = self._clock()
        self._recent[text] = now
        if key is not None:
            self._conditions[key] = text
        if len(self._recent) > self.RECENT_LIMIT:
            self._recent = {
                line: said
                for line, said in self._recent.items()
                if now - said < self.RECENT_MEMORY_S
            }

    def forget_condition(self, key: str) -> None:
        """A standing condition has cleared; let it announce itself afresh."""
        self._conditions.pop(key, None)

    # -- the backlog projection ---------------------------------------------------

    def note_interrupt(self, text: str) -> None:
        """An interrupting line purges the channel: the projection restarts."""
        self._purge_next = False
        self._clear_at = self._clock() + self._duration_s(text)

    def should_flush(self, text: str, priority: EventPriority = EventPriority.AMBIENT) -> bool:
        """Decide a queued line's fate and update the projection either way.

        Returns True when the line would otherwise start stale -- the caller
        must then submit it interrupting (which purges the dead backlog).
        ``priority`` sets how long this line is willing to wait: a route
        announcement gives a backlog of chatter under a second before it goes
        in front of it.
        """
        now = self._clock()
        if self._purge_next:
            # Coming back from a pause. Whatever the voice was still holding
            # when the player stepped away is about a mile they have already
            # been told about, so the first line back purges it.
            self._purge_next = False
            self._clear_at = now + self._duration_s(text)
            return True
        start = max(now, self._clear_at)
        budget = self.WAIT_BUDGET_S.get(EventPriority(priority), self.STALE_WAIT_S)
        if start - now > budget:
            self._clear_at = now + self._duration_s(text)
            return True
        self._clear_at = start + self._duration_s(text)
        return False

    def reset(self) -> None:
        """The channel was silenced outside the pacer's view (Ctrl, menus)."""
        self._clear_at = 0.0
        self._purge_next = False

    # -- leaving and returning to the road ----------------------------------------

    def pause(self) -> None:
        """The player has stepped off the road (pause menu, a stop, settings).

        The caller silences the event channel; this drops the projection with
        it and arms the purge, so the first line spoken back on the road
        cannot arrive behind a backlog describing where the truck used to be.
        """
        self._clear_at = 0.0
        self._purge_next = True

    def resume(self) -> None:
        """Back at the wheel. Nothing from before the pause is news."""
        self._clear_at = 0.0
        self._purge_next = True
