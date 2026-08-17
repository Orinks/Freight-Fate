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

The purge that delivers an interrupting line cuts both ways: it flushes dead
chatter, but it also lands on whatever the voice was mid-way through -- and
when that was a ROUTE or CRITICAL line (the weigh station notice, the planned
stop), the player lost an instruction, not colour (a tester blew a weigh
station this way, 2026-08-12). The pacer therefore keeps the newest such line
alongside its projected finish time, and an interrupt arriving before that
moment hands the line back to the caller to queue right behind the
interrupting one: safety line first, then the line it stepped on.

Durations are estimated from text length at a conservative default-voice
speaking rate. A faster voice just flushes a little less eagerly than it
could; a slower one flushes a little late but stays bounded -- either way the
player never again waits through a paragraph of expired narration.
"""

from __future__ import annotations

import time
from enum import IntEnum, StrEnum


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


class SpeechCategory(StrEnum):
    """What a line of informational speech is ABOUT.

    Orthogonal to :class:`EventPriority`, which says how long a line waits
    and whether staleness may drop it. Urgency alone gave the verbosity
    system only one lever -- length -- which is why compressing every
    message (stage S2) did not make the drive quieter: it never reduced how
    many things speak. The rung table below cuts by category instead.

    Flavor -- billboards, place names, landmarks, roadside colour -- is
    deliberately absent. It answers to the chatter switches and the
    place-callouts ladder, and the owner set those separately (2026-08-15).

    A recurring miscategorisation the review caught three times (2026-08-16):
    a line that names a key the player must press to keep moving is never
    CONFIRMATION. CONFIRMATION is an outcome report -- the assist cleared it,
    the latch caught, here is what happened. A stalled engine, a grounded
    tractor, a scrapped chain set are unrequested failures that stop the
    truck and demand a next action; at quiet and urgent_only CONFIRMATION
    is an EARCON, so miscategorising one of these turns the instruction that
    gets the truck moving again into a chime. Route it by what actually
    changed instead: SAFETY when the truck will not move and the line says
    what to press, MONEY when it cost money or equipment.
    """

    SAFETY = "safety"
    NAVIGATION = "navigation"
    # Navigation you cannot recover from -- take this exit, turn here, you
    # missed it -- against navigation that is a heads-up on what the road is
    # about to do. Both are navigation and both speak at quiet; they part
    # company at urgent_only, where the heads-up becomes a tone and the
    # unrecoverable one keeps its words. Splitting them is what makes the
    # two quietest rungs different settings rather than near-copies (owner,
    # 2026-08-17: the strict "only if you must act" rule describes
    # urgent_only, and quiet should be "still very little" above it).
    NAVIGATION_ADVISORY = "navigation_advisory"
    MONEY = "money"
    COACHING = "coaching"
    CONFIRMATION = "confirmation"
    STATUS = "status"


class Disposition(StrEnum):
    """What a rung does with a category.

    ``EARCON`` and ``SILENT`` both stop the words; they differ in whether
    the sound layer still marks the moment. Neither loses the line -- both
    still reach the message log, and the status-query keys still answer, so
    nothing the ladder cuts becomes unreachable.
    """

    FULL = "full"  # speaks, normal rendering
    TERSE = "terse"  # speaks, terse rendering -- never silence
    FIRST_OCCURRENCE = "first"  # speaks the first time per leg, then silent
    TRANSITIONS = "transitions"  # speaks on enter, worsen, and clear only
    EARCON = "earcon"  # the sound layer carries it; no words
    SILENT = "silent"  # no words, no sound; log and status keys only


DRIVING_SPEECH_MODES = ("coaching", "standard", "quiet", "urgent_only")

# The rung table. Read a row as "at this rung, a line of this category is
# delivered this way". Safety and money are FULL or TERSE in every row and a
# test pins that: R1's never-dropped contract outranks any rung.
DRIVING_SPEECH_DISPOSITIONS: dict[str, dict[SpeechCategory, Disposition]] = {
    "coaching": {
        SpeechCategory.SAFETY: Disposition.FULL,
        SpeechCategory.MONEY: Disposition.FULL,
        SpeechCategory.NAVIGATION: Disposition.FULL,
        SpeechCategory.NAVIGATION_ADVISORY: Disposition.FULL,
        SpeechCategory.COACHING: Disposition.FULL,
        SpeechCategory.CONFIRMATION: Disposition.FULL,
        SpeechCategory.STATUS: Disposition.FULL,
    },
    "standard": {
        SpeechCategory.SAFETY: Disposition.FULL,
        SpeechCategory.MONEY: Disposition.FULL,
        SpeechCategory.NAVIGATION: Disposition.FULL,
        SpeechCategory.NAVIGATION_ADVISORY: Disposition.FULL,
        SpeechCategory.COACHING: Disposition.FIRST_OCCURRENCE,
        SpeechCategory.CONFIRMATION: Disposition.FULL,
        SpeechCategory.STATUS: Disposition.TRANSITIONS,
    },
    "quiet": {
        SpeechCategory.SAFETY: Disposition.TERSE,
        SpeechCategory.MONEY: Disposition.TERSE,
        SpeechCategory.NAVIGATION: Disposition.TERSE,
        SpeechCategory.NAVIGATION_ADVISORY: Disposition.TERSE,
        SpeechCategory.COACHING: Disposition.EARCON,
        SpeechCategory.CONFIRMATION: Disposition.EARCON,
        SpeechCategory.STATUS: Disposition.EARCON,
    },
    "urgent_only": {
        SpeechCategory.SAFETY: Disposition.TERSE,
        SpeechCategory.MONEY: Disposition.TERSE,
        SpeechCategory.NAVIGATION: Disposition.TERSE,
        SpeechCategory.NAVIGATION_ADVISORY: Disposition.EARCON,
        SpeechCategory.COACHING: Disposition.SILENT,
        SpeechCategory.CONFIRMATION: Disposition.EARCON,
        SpeechCategory.STATUS: Disposition.SILENT,
    },
}

DEFAULT_DRIVING_SPEECH = "standard"

# The sound that carries a category once a rung stops speaking it. Every
# value is a real ``SoundEntry.name`` in the Learn game sounds catalog
# (``sound_catalog.CATALOG``) -- pinned by
# ``test_every_earcon_category_is_learnable`` -- because a sound the player
# cannot look up is information removed rather than information moved (R14).
# CONFIRMATION reuses the hazard-clear chime that already shipped in S3
# rather than inventing a second success cue; COACHING and STATUS have no
# existing sound that means what an earcon here needs to mean, so each gets
# its own synthesized entry (``ladder_earcons.py``).
LADDER_EARCONS = {
    SpeechCategory.NAVIGATION_ADVISORY: "Road ahead note",
    SpeechCategory.COACHING: "Coaching note",
    SpeechCategory.CONFIRMATION: "Hazard clear",
    SpeechCategory.STATUS: "Status note",
}


def disposition_for(mode: str, category: SpeechCategory | None) -> Disposition:
    """How this rung delivers this category.

    An unknown rung reads as the default rather than raising: a settings
    file edited by hand must not be able to crash the drive. A ``None``
    category is an unclassified call site and always speaks -- the rendering
    still follows the rung, so it gets shorter but never disappears.
    """
    row = (
        DRIVING_SPEECH_DISPOSITIONS.get(mode) or DRIVING_SPEECH_DISPOSITIONS[DEFAULT_DRIVING_SPEECH]
    )
    if category is None:
        return row[SpeechCategory.SAFETY]
    return row.get(SpeechCategory(category), Disposition.FULL)


class EventSpeechPacer:
    """Keeps the dedicated event voice from performing the past.

    See the module docstring for the whole picture. The caller's contract:

    * ``is_repeat`` decides whether the player has already heard this; a True
      means say nothing at all.
    * ``note_spoken`` records a line that did reach the voice.
    * ``is_silenced_repeat``/``note_silenced`` are the same pair for a line
      the driving speech rung cut to an earcon or to nothing -- a private
      namespace so a silenced occurrence can dedupe its own earcon without
      ever registering as something ``is_repeat`` would recognise as heard.
    * ``note_interrupt`` for an interrupting line (it purges the channel), or
      ``should_flush`` for a queued one -- True there means the backlog has
      gone stale and this line must be submitted interrupting instead.
    * ``note_interrupt`` may hand back the ROUTE or CRITICAL line the purge
      cut off mid-sentence; the caller resubmits it queued (``note_queued``)
      so the player still hears it, right behind the line that cut it.
    * ``note_channel_purged`` when speech outside the pacer's view (an info
      reply on a shared voice) purges the channel -- same hand-back.
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
        # The same two maps, but for occurrences the driving speech rung
        # silenced (an earcon or nothing, never the words). Kept separate
        # from ``_recent``/``_conditions`` on purpose: those two belong to
        # what the player actually heard, and ``is_repeat`` consults them to
        # decide whether a genuinely spoken line would be news. If a
        # silenced occurrence wrote into that same state, raising the rung
        # mid-drive while a standing condition was still active (still
        # locked out, still at redline) would find the SILENCED text sitting
        # in ``_conditions``, read the now-audible occurrence as an unchanged
        # repeat, and skip it -- exactly the rung promising full sentences
        # going quiet for the condition the player raised it to hear about.
        self._silenced_recent: dict[str, float] = {}
        self._silenced_conditions: dict[str, str] = {}
        # Set by pause(): the next line purges the channel, so anything the
        # voice was still holding when the player stepped away cannot surface
        # behind it.
        self._purge_next = False
        # The newest ROUTE or CRITICAL line submitted, with the projection's
        # estimate of when it finishes speaking. An interrupt landing before
        # that moment plausibly cut it off mid-sentence; it is handed back to
        # the caller so the player still hears it.
        self._protected: tuple[str, EventPriority, float] | None = None

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
        self._silenced_conditions.pop(key, None)

    # -- what the rung silenced (earcon-only or fully quiet) ----------------------

    def is_silenced_repeat(
        self,
        text: str,
        *,
        key: str | None = None,
        window: float | None = None,
    ) -> bool:
        """True when this silenced occurrence was already marked (earcon or not).

        The silenced branches' own dedup: mirrors :meth:`is_repeat`'s rules
        exactly, but reads a namespace private to occurrences the rung cut,
        never ``_conditions``/``_recent``. A silenced repeat must not go
        unmarked (that is the earcon machine-gun this exists to stop), but it
        must equally never be mistaken for a genuinely spoken occurrence by
        :meth:`is_repeat` once the rung changes and the condition is still
        active -- that would silence the very line the player raised the
        rung to hear.
        """
        if not text:
            return False
        if key is not None and self._silenced_conditions.get(key) == text:
            return True
        budget = self.REPEAT_WINDOW_S if window is None else window
        if budget <= 0.0:
            return False
        last = self._silenced_recent.get(text)
        return last is not None and self._clock() - last < budget

    def note_silenced(self, text: str, *, key: str | None = None) -> None:
        """Record a silenced occurrence (earcon played, or fully quiet)."""
        if not text:
            return
        now = self._clock()
        self._silenced_recent[text] = now
        if key is not None:
            self._silenced_conditions[key] = text
        if len(self._silenced_recent) > self.RECENT_LIMIT:
            self._silenced_recent = {
                line: said
                for line, said in self._silenced_recent.items()
                if now - said < self.RECENT_MEMORY_S
            }

    # -- the backlog projection ---------------------------------------------------

    def _track(
        self, text: str, priority: EventPriority, category: SpeechCategory | None = None
    ) -> None:
        """Remember the newest line worth rescuing if an interrupt lands on it.

        A CONFIRMATION never takes the slot, whatever priority it was spoken
        at. Confirmations default to CRITICAL because they answer something
        the player just did, so they used to qualify -- and then the next
        interrupting line on the main channel handed the finished
        confirmation back to be requeued, where it resurfaced AFTER, and
        could bury, the line the player had actually just asked for. The slot
        exists to rescue a warning cut off mid-sentence; an outcome report
        that already finished, and whose outcome may since have been
        contradicted (the transmission flipped back, the units changed
        again), is not that. Found by the adversarial harness on
        settings_flips_mid_drive, and made routine rather than rare once
        pressed keys began interrupting again (2026-08-16).
        """
        if category is SpeechCategory.CONFIRMATION:
            self._protected = None
            return
        if priority >= EventPriority.ROUTE:
            self._protected = (text, EventPriority(priority), self._clear_at)

    def _take_protected(self, cutting_text: str | None = None):
        """Hand over the protected line if it was plausibly cut mid-speech.

        The slot empties either way: a line is given back at most once per
        cut, and a line whose projected finish had already passed was heard
        in full, not destroyed. A line cutting itself is one line, not two,
        so it is never handed back behind its own delivery.
        """
        held = self._protected
        self._protected = None
        if held is None:
            return None
        text, priority, done_at = held
        if self._clock() >= done_at or text == cutting_text:
            return None
        return text, priority

    def note_interrupt(
        self,
        text: str,
        priority: EventPriority = EventPriority.CRITICAL,
        category: SpeechCategory | None = None,
    ) -> tuple[str, EventPriority] | None:
        """An interrupting line purges the channel: the projection restarts.

        Returns the ROUTE or CRITICAL line the purge plausibly cut off
        mid-sentence -- its projected finish had not yet passed -- so the
        caller can queue it right back behind the interrupting line. Chatter,
        lines already heard in full, and a line interrupting itself return
        None: nothing worth giving back was destroyed."""
        cut = self._take_protected(text)
        self._purge_next = False
        self._clear_at = self._clock() + self._duration_s(text)
        self._track(text, priority, category)
        return cut

    def note_queued(
        self,
        text: str,
        priority: EventPriority = EventPriority.AMBIENT,
        category: SpeechCategory | None = None,
    ) -> None:
        """Extend the projection for a line delivered queued, no verdict asked.

        For the deliveries that must never flush: a rescued cut-off line
        (it has to fall in BEHIND the line that cut it, never purge it) and
        event lines riding the main channel, where the backlog belongs to
        the main voice rather than the pacer."""
        start = max(self._clock(), self._clear_at)
        self._clear_at = start + self._duration_s(text)
        self._track(text, EventPriority(priority), category)

    def note_channel_purged(self) -> tuple[str, EventPriority] | None:
        """Speech outside the pacer's view purged the channel events ride on.

        Only meaningful when the event voice is collapsed onto the main
        channel: an info reply's interrupt there lands on whatever event line
        was mid-sentence. Returns the cut ROUTE or CRITICAL line exactly as
        :meth:`note_interrupt` would; the projection falls with the purge
        (the interrupting speech itself is not the pacer's to time)."""
        cut = self._take_protected()
        self._clear_at = 0.0
        return cut

    def busy(self) -> bool:
        """Whether the projection says the event voice is still speaking.

        The channel cannot be asked directly (nothing in Prism reports queue
        state), so this is the same estimate the staleness budget runs on.
        It is what audio ducking restores on: the mix steps back while this
        is True and comes back the frame it goes False. Purges, pauses, and
        resets zero the projection, so a silenced channel reads not-busy at
        once instead of waiting out a stale estimate."""
        return self._clock() < self._clear_at

    def would_start_stale(self, text: str, priority: EventPriority = EventPriority.AMBIENT) -> bool:
        """Whether this queued line would start past its priority's budget.

        A pure reading -- the projection is not touched, nothing is tracked.
        The caller uses it to decide a line's fate BEFORE committing it to
        the channel: chatter that would start stale is dropped silently
        (UIA MostRecent semantics -- superseded telemetry is discarded, not
        read late), where :meth:`should_flush` would instead deliver it
        interrupting. A purge armed by pause() is not staleness; that path
        stays with should_flush, whose first line back purges the backlog.
        """
        if self._purge_next:
            return False
        start = max(self._clock(), self._clear_at)
        budget = self.WAIT_BUDGET_S.get(EventPriority(priority), self.STALE_WAIT_S)
        return start - self._clock() > budget

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
            self._protected = None
            self._track(text, EventPriority(priority))
            return True
        start = max(now, self._clear_at)
        budget = self.WAIT_BUDGET_S.get(EventPriority(priority), self.STALE_WAIT_S)
        if start - now > budget:
            # A stale flush takes the whole backlog, protected slot included:
            # everything in it described miles already driven.
            self._clear_at = now + self._duration_s(text)
            self._protected = None
            self._track(text, EventPriority(priority))
            return True
        self._clear_at = start + self._duration_s(text)
        self._track(text, EventPriority(priority))
        return False

    def reset(self) -> None:
        """The channel was silenced outside the pacer's view (Ctrl, menus)."""
        self._clear_at = 0.0
        self._purge_next = False
        self._protected = None

    # -- leaving and returning to the road ----------------------------------------

    def pause(self) -> None:
        """The player has stepped off the road (pause menu, a stop, settings).

        The caller silences the event channel; this drops the projection with
        it and arms the purge, so the first line spoken back on the road
        cannot arrive behind a backlog describing where the truck used to be.
        """
        self._clear_at = 0.0
        self._purge_next = True
        self._protected = None

    def resume(self) -> None:
        """Back at the wheel. Nothing from before the pause is news."""
        self._clear_at = 0.0
        self._purge_next = True
        self._protected = None
