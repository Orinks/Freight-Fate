"""Application shell: pygame window, state stack, and shared services."""

from __future__ import annotations

import contextlib
import faulthandler
import logging
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from . import __version__
from .achievements import AchievementAward, award
from .assets_pack import prefetch_default as prefetch_sound_pack
from .audio import EARCON_DUCK_S, SPEECH_DUCK_LEVEL, AudioEngine
from .controller import ControllerManager
from .data.world import World, get_world
from .discord_presence import DiscordPresence
from .held_keys import HeldKeys
from .ladder_earcons import register_ladder_earcons
from .lane_guide_tone import register_lane_guide_tone
from .message_log import MessageCategory, MessageLog
from .models.economy import Economy
from .models.profile import Profile
from .music import music_track_duration_s
from .settings import Settings
from .sound_catalog import entry_by_name
from .speech import EventPriority, EventSpeechPacer, Speech
from .speech_pacing import LADDER_EARCONS, Disposition, SpeechCategory
from .speech_text import SpokenMessage
from .states.base import State

if TYPE_CHECKING:
    # Not needed at runtime: cloud_saves.py (and what it pulls in --
    # cryptography.hazmat, by way of cloud_save_integrity) is only imported
    # where CloudSaves is actually constructed, below. See online_presence
    # and cloud_save_integrity for the matching lazy-import treatment of
    # keyring and cryptography.hazmat themselves.
    from .cloud_saves import CloudSaves

log = logging.getLogger(__name__)
# Every spoken line lands here too, so a logged playtest reads as a transcript of
# what the player heard -- the most faithful record for an audio-first game.
transcript = logging.getLogger("freight_fate.transcript")

# Where this session's log actually ended up, or None when nothing is being
# written to disk (a source checkout with no explicit log file, or a folder the
# game could not write to). Recorded by _configure_logging rather than derived
# again later, so the settings screen reports the real file instead of the one
# the game meant to open.
_log_file: Path | None = None


def active_log_path() -> Path | None:
    """The log file this session is writing, or None when there is none."""
    return _log_file


WINDOW_SIZE = (900, 640)
FPS = 60

_CONTROLLER_EVENTS = frozenset(
    {
        pygame.CONTROLLERBUTTONDOWN,
        pygame.CONTROLLERBUTTONUP,
        pygame.CONTROLLERAXISMOTION,
        pygame.CONTROLLERDEVICEADDED,
        pygame.CONTROLLERDEVICEREMOVED,
    }
)
BG_COLOR = (12, 12, 16)
TEXT_COLOR = (235, 235, 225)
HILIGHT_COLOR = (255, 210, 90)


def _stop_main_speech(speech) -> None:
    stop = getattr(speech, "stop_main", None) or getattr(speech, "stop", None)
    if stop is not None:
        stop()


def _stop_event_speech(speech) -> None:
    stop = getattr(speech, "stop_event", None)
    if stop is not None:
        stop()


class GameContext:
    """Shared services handed to every state."""

    def __init__(self, app: App) -> None:
        self._app = app
        self.speech: Speech = app.speech
        self.audio: AudioEngine = app.audio
        self.controller: ControllerManager = app.controller
        self.held_keys: HeldKeys = app.held_keys
        self.settings: Settings = app.settings
        self.world: World = app.world
        self.economy: Economy = app.economy
        self.profile: Profile | None = None
        self._real_weather = None
        self._real_traffic = None
        self._truck_parking = None
        self._music_pool_positions: dict[tuple[str, tuple[str, ...]], int] = {}
        self._music_pool_last: dict[str, str] = {}
        self._music_rotation_pool: tuple[str, tuple[str, ...]] | None = None
        self._music_rotation_track: str | None = None
        self._music_rotation_elapsed_s = 0.0
        self.achievement_notice = ""
        self.achievement_notice_timer = 0.0
        # Anti-backlog projection for the dedicated event voice: queued
        # driving events that would start speaking stale get flushed instead.
        self._event_pacer = EventSpeechPacer()
        # Whether the game mix is currently stepped down under the event
        # voice (Settings > Audio; see _engage_speech_duck).
        self._speech_ducked = False
        # Deadline for a duck an earcon opened, in real seconds. Zero when the
        # duck belongs to a spoken line, which the pacer's projection ends.
        self._earcon_duck_until = 0.0
        # True only while a control the player actually pressed is being
        # handled. See ``player_asked``: a readout somebody asked for cuts the
        # line in progress even at the wheel, where unasked-for lines queue.
        self._speech_requested = False
        # FIRST_OCCURRENCE and TRANSITIONS need memory of what has already
        # been said; Settings cannot hold it, so it lives here beside the
        # pacer. ``_ladder_said`` is leg-scoped ("once per leg"),
        # ``_ladder_last`` is the last text seen per key so a re-assertion
        # can be told from a change of state.
        self._ladder_said: set[tuple[str, str]] = set()
        self._ladder_last: dict[str, str] = {}
        # True while a playtest-lever scenario runs unsaved (see
        # playtest_levers.apply_continue_levers); save_profile honors it.
        self.playtest_sandbox = False
        self.message_log = app.message_log
        # The S4 ladder's earcons (LADDER_EARCONS below) can now play from
        # any screen the silencing gate fires on, not only the Learn game
        # sounds screen that used to be the sole registrant. Idempotent and
        # cheap, so doing it once here means the drive never has to wait on
        # that screen having been visited first.
        register_ladder_earcons()
        # Same reason, same shape: the guide tone must exist before a
        # drive starts, not only after the Learn screen has been opened.
        register_lane_guide_tone()

    def _ladder_applies(self) -> bool:
        """Whether the driving speech rung may silence anything yet.

        First-run teaching outranks the rung, exactly as it outranks terse
        (research doc R15). A player who picks the quietest setting before
        their first drive is the one who most needs to be told the status,
        help, and hazard keys exist -- silence them and they can never pull
        information nobody told them about. The gate is ``tutorial_done``
        itself, so finishing the walkthrough and then choosing a quiet rung
        resurrects nothing.

        ``GameContext.profile`` is ``Profile | None`` (``app.py:98``), and
        the default here is deliberately ``True``: no profile means nobody
        is on a first drive, so the rung applies normally.
        """
        return bool(getattr(self.profile, "tutorial_done", True))

    def _play_ladder_earcon(self, category: SpeechCategory | None) -> None:
        """Sound the cue standing in for a category the rung just cut.

        Spec invariant 3: what drops out of speech lands on the earcon layer
        or the message log, so cutting is legitimate rather than
        exclusionary. Only called where ``speech_disposition`` is already
        ``EARCON`` -- ``SILENT`` never reaches here, which is the entire
        difference at the voice between the ``quiet`` and ``urgent_only``
        rungs. ``LADDER_EARCONS`` names the cue by the catalog entry's
        canonical noun; the entry itself (``sound_catalog.py``) is the one
        place its key, volume, and pan are written down, so this resolves
        through it rather than keeping a second copy that could drift.

        A category missing from ``LADDER_EARCONS``, or a name the catalog
        does not carry, is a data bug in that table (a test pins every
        EARCON row against the catalog) -- not something to raise mid-drive
        over, so it is skipped rather than crashing the game.
        """
        if category is None:
            return
        name = LADDER_EARCONS.get(category)
        if name is None:
            return
        entry = entry_by_name(name)
        if entry is None or not entry.plays:
            return
        cue = entry.plays[0]
        self.audio.play(cue.key, volume=cue.volume, pan=cue.pan)

    def _online_enabled(self, setting: bool) -> bool:
        """True when both the master ``online_services`` switch and the
        individual ``setting`` are enabled.

        The master governs the orinks.net and sharing services only (drivers
        board, profile sharing, cloud backup, Mastodon, Discord presence).
        Live-data simulation sources -- weather, traffic, parking -- follow
        their own Settings toggles and are deliberately NOT gated here
        (owner ruling, 2026-08-08: two testers lost real weather to the
        master switch without a word of explanation)."""
        return self.settings.online_services and setting

    def real_weather_provider(self):
        """Shared NWS provider when real weather is enabled, else None.

        Created lazily and kept for the whole session so its cache spans trips.
        """
        if not self.settings.real_weather:
            return None
        if self._real_weather is None:
            from .sim.real_weather import RealWeatherProvider

            self._real_weather = RealWeatherProvider()
        return self._real_weather

    def warm_real_weather(self, city_key: str) -> None:
        """Start fetching a city's live weather before any drive needs it.

        The provider caches observations per station, so a trip leaving this
        city finds its first route cell already answered and starts live
        instead of holding "loading". Quietly a no-op when real weather is
        off or the city is unknown.
        """
        provider = self.real_weather_provider()
        if provider is None:
            return
        try:
            key = self.world.resolve_city_key(city_key)
            city = self.world.cities[key]
        except (KeyError, AttributeError):
            return
        if city.lat or city.lon:
            provider.request(f"city:{key}", city.lat, city.lon)

    def real_traffic_provider(self):
        """Shared state 511 provider when real traffic is enabled, else None.

        Created lazily and kept for the whole session so its cache spans trips.
        """
        if not self.settings.real_traffic:
            return None
        if self._real_traffic is None:
            from .sim.real_traffic import RealTrafficProvider

            self._real_traffic = RealTrafficProvider()
        return self._real_traffic

    def truck_parking_provider(self):
        """Shared TPIMS provider when real parking is enabled, else None.

        Created lazily and kept for the whole session so its cache spans trips.
        """
        if not self.settings.real_parking:
            return None
        if self._truck_parking is None:
            from .sim.truck_parking import TruckParkingProvider

            self._truck_parking = TruckParkingProvider()
        return self._truck_parking

    def say(
        self,
        text: str,
        interrupt: bool = True,
        review: bool = True,
        *,
        category: SpeechCategory | None = None,
    ) -> None:
        if (
            not self.settings.speaks(category)
            and self._ladder_applies()
            and (not self._speech_requested)
        ):
            # The player's rung silences this category. The line still
            # reaches the review log, so the information is cut from the
            # drive, not from the game -- the review key that exists to
            # answer for it still can. Where the rung's disposition is
            # EARCON rather than SILENT, the sound layer marks the moment
            # instead of the words -- the two rungs that share this branch
            # are otherwise identical at the voice.
            #
            # A line the player ASKED for is exempt (``_speech_requested``,
            # set by ``player_asked()`` around key and button handling) --
            # the same escape ``say_event`` has carried as ``force`` since
            # the ladder shipped, missing here. Without it, pressing the
            # cruise dial at quiet answered with a chime and no number: the
            # rung was silencing an answer to a question the player had just
            # asked, which is not what a rung is for (owner, 2026-08-17).
            # The RENDERING still follows the rung, so quiet answers the
            # dial with "62" rather than a sentence.
            if isinstance(text, SpokenMessage):
                text = text.render(self.settings.renders_terse()) or text.normal
            if self._event_pacer.is_silenced_repeat(text):
                # A keyless standing condition (no ``key=`` reaches this
                # method) re-fires on a timer while the drive is otherwise
                # unchanged. The gate above never used to consult the pacer,
                # so a silenced repeat still hit the earcon on every frame --
                # the quiet rung machine-gunning a sound where coaching says
                # one sentence and falls silent. The plain repeat window is
                # enough here; there is no ``key=`` to track a condition by.
                # ``is_silenced_repeat``/``note_silenced`` are a namespace of
                # their own (not ``is_repeat``/``note_spoken``): a silenced
                # occurrence must never write into the state the SPEAKING
                # path reads, or raising the rung mid-drive while this same
                # condition is still active would find its own silenced text
                # already on file and go quiet for the sentence the rung now
                # promises.
                return
            if self.settings.speech_disposition(category) is Disposition.EARCON:
                self._play_ladder_earcon(category)
            self._event_pacer.note_silenced(text)
            transcript.info("[ladder] %s silenced: %s", self.settings.driving_speech, text)
            if review:
                self.message_log.add(text, MessageCategory.GENERAL)
            return
        if isinstance(text, SpokenMessage):
            # A normal/terse pair resolves here, in the delivery layer, so
            # coverage never again depends on a call-site branch (research
            # doc, R5). An empty rendering is a line terse mode drops whole.
            text = text.render(self.settings.renders_terse())
            if not text:
                return
        transcript.info("%s", text)
        if (
            interrupt
            and not self._speech_requested
            and getattr(self._app.state, "paces_main_speech", False)
        ):
            # At the wheel, the main channel queues instead of cutting: an
            # achievement or assist notice must not stamp on the line the
            # player was mid-way through hearing. Menus and readers keep
            # their default interrupt -- a screen over the drive is the top
            # state, so navigation there still cancels speech the way every
            # screen reader does. A queued line also cannot purge a shared
            # voice, so the rescue below has nothing to hand back.
            #
            # A line the player ASKED for is exempt (``_speech_requested``).
            # The rule above was aimed at lines nobody asked for, but it was
            # applied to every main-channel line at the wheel, so pressing a
            # key stopped cutting the speech in progress -- which is what 1.8
            # does and what every screen reader does (Sarah R. via the owner,
            # 2026-08-16). Answering the key you just pressed is the whole
            # contract of an info key.
            interrupt = False
        cut = None
        if interrupt and self._event_voice_shares_main():
            # In this configuration the main channel is also carrying the
            # road, so an info reply's interrupt can land on a ROUTE or
            # CRITICAL event line mid-sentence (a tester blew a weigh station
            # this way). The reply still answers first; the cut line queues
            # right behind it.
            cut = self._event_pacer.note_channel_purged()
        self.speech.say(text, interrupt)
        if cut is not None:
            self._requeue_cut_event(cut)
        if review:
            self.message_log.add(text, MessageCategory.GENERAL)

    def _event_voice_shares_main(self) -> bool:
        """True when driving events speak on the main channel.

        Either the player chose the main voice for events (Settings >
        Speech), or the dedicated-voice preference found no separate backend
        to bind, so :meth:`Speech.say_event` falls back to the main channel.
        """
        if not self.settings.sapi_events:
            return True
        return not getattr(self.speech, "has_separate_event_voice", False)

    def _requeue_cut_event(self, cut: tuple[str, EventPriority]) -> None:
        """Finish delivering a ROUTE or CRITICAL line an interrupt cut short.

        Straight to the voice, queued: the line already passed the pacer,
        the transcript, and the message log when it was first submitted, so
        this is the same delivery completing rather than a new event. The
        pacer tracks it again, so a further genuine interrupt can hand it
        back a second time; it cannot ping-pong forever, because a requeue
        is never interrupting and an identical interrupting line is never
        handed back behind itself.
        """
        text, priority = cut
        # Name the line. A bare "cut line requeued" says a hand-back happened
        # and not what came back, which is the one thing an audit needs: four
        # separate lines have now been found coming back after their moment
        # had passed (the scale exit, the destination exit, the hazard dodge
        # call, the dock hold prompt), each by a tester hearing it rather than
        # by anyone reading a bench transcript. With the text here, a
        # playtest log answers the question by itself -- grep the requeues,
        # read each one, ask whether it was still true.
        transcript.info(f"[pacer] cut line requeued: {text}")
        self._event_pacer.note_queued(text, priority)
        if self.settings.sapi_events:
            self.speech.say_event(text, interrupt=False)
        else:
            self.speech.say(text, interrupt=False)

    def reset_ladder_leg_memory(self) -> None:
        """Forget what has been said once, at a leg boundary.

        FIRST_OCCURRENCE is "speaks the first time per leg", so a new leg is
        a fresh road and the tip is worth one more telling.
        """
        self._ladder_said.clear()

    def _ladder_repeats(self, text: str, category, key: str | None) -> bool:
        """Whether this rung's disposition drops this line as already-said.

        The two dispositions the table has always promised and
        ``Settings.speaks`` never delivered: it branches on EARCON/SILENT
        alone, so FIRST_OCCURRENCE and TRANSITIONS both behaved exactly like
        FULL, and standard was therefore indistinguishable from coaching
        (roadmap, and owner 2026-08-17: "should standard and coaching make a
        difference? There should be").

        FIRST_OCCURRENCE: this LINE said once per leg, then nothing. Keyed
        on the key and the text together, not the key alone: the
        disposition exists for a coaching tip that repeats word for word,
        and keying on the condition instead meant a keyed readout whose
        number moves was said once and swallowed for the rest of the leg.

        TRANSITIONS: "enter, worsen, and clear only". A ``key`` names a
        standing condition, and status lines carry the state they are
        reporting in their own text -- so a line identical to the last one
        under this key is the condition re-asserting itself and a changed
        one is the transition.

        A line with NO key is not a standing condition; it is a discrete
        moment, and its call site has already decided this occurrence is
        worth saying (``_lane_gap_said_keys``, ``_air_ready_said``, an edge
        flag). The rung has nothing to compare it against, so it does not
        suppress it. This fallback used to key on the text itself, which
        turned "enter, worsen, and clear" into "this exact sentence once per
        leg, ever" -- 310 lines dropped in one leg of a tester's log on
        STANDARD, the default rung, including every return to a speed the
        truck had already passed through once (Darren, 2026-08-19). The pacer's own
        repeat window still stops the same line landing twice in a breath,
        which is the only repetition there was ever anything to blunt.
        """
        disposition = self.settings.speech_disposition(category)
        if disposition is Disposition.FIRST_OCCURRENCE:
            slot = (key, text) if key else ("", text)
            if slot in self._ladder_said:
                return True
            self._ladder_said.add(slot)
            return False
        if disposition is Disposition.TRANSITIONS:
            if key is None:
                return False
            if self._ladder_last.get(key) == text:
                return True
            self._ladder_last[key] = text
            return False
        return False

    def say_event(
        self,
        text: str,
        interrupt: bool = True,
        review: bool = True,
        *,
        priority: EventPriority | None = None,
        key: str | None = None,
        force: bool = False,
        category: SpeechCategory | None = None,
        valid=None,
    ) -> None:
        """Driving event announcements (hazards, warnings, weather, ...).

        ``valid``, when given, is a zero-argument callable answering "is this
        line still true?" -- consulted if the line is cut mid-sentence and
        offered a rescue. A line whose moment has passed (the scale is behind
        the truck, the damage total has moved on) is dropped instead of
        replayed verbatim; message review holds the words either way.

        With the dedicated SAPI event voice enabled, events speak on their own
        channel, where ``interrupt`` only cuts off a previous event -- so an
        urgent cue can still jump ahead of a stale one without touching the
        screen reader.

        With it disabled the player has chosen to hear events through their
        screen reader. Urgent events first flush stale game speech, then speak
        as a fresh queued utterance so old messages do not bury the warning.

        Every line first passes the pacer, which knows what the player has
        already heard. A line identical to one spoken a moment ago is dropped
        outright -- one moment noticed on several frames is still one moment.
        ``key`` marks a standing condition (a damaged load, an engine at
        redline) rather than an event: it speaks when it starts and again only
        when what it says has changed. ``force`` is for a line the player
        asked for and must hear whether or not it repeats.

        Queued events then ride an anti-backlog projection either way: a line
        that would start speaking well after the moment it described flushes
        the expired backlog and speaks now instead of joining the recital.
        ``priority`` sets how long it is willing to wait first -- route
        announcements (the planned stop, the exit) give ambient chatter well
        under a second before going in front of it.

        An interrupting line's purge also lands on whatever the voice was
        mid-way through. When that was a ROUTE or CRITICAL line still
        plausibly speaking, the pacer hands it back and it is resubmitted
        queued, right behind the interrupting line -- safety line first,
        then the line it stepped on, never dropped.

        ``review`` keeps a line out of the reviewable message log. An assist
        that interrupts to say it is acting would otherwise land exactly where
        the warning it cut off should be, so the review keys that exist to
        rescue an interrupted line would hand back the interruption instead.

        ``text`` may be a :class:`SpokenMessage` normal/terse pair; the
        player's speech mode picks the rendering here, so terse coverage is
        a property of the message definition rather than of the call site.
        A pair whose terse rendering is empty is dropped whole in terse
        mode: not spoken, not logged, exactly like a muted chatter line.
        """
        if not self.settings.speaks(category) and not force and self._ladder_applies():
            # The player's rung silences this category. The line still
            # reaches the review log and the status keys, so the
            # information is cut from the drive, not from the game.
            # ``force`` is a line the player asked for and must hear. Where
            # the rung's disposition is EARCON rather than SILENT, the sound
            # layer marks the moment instead of the words.
            if isinstance(text, SpokenMessage):
                text = text.render(self.settings.renders_terse()) or text.normal
            if self._event_pacer.is_silenced_repeat(text, key=key):
                # A keyed standing condition (an engine held at redline, a
                # locked-out air brake) re-fires on a timer by design while
                # the condition holds -- that is what keeps it audible when
                # the rung speaks it. But this gate used to return before
                # ever reaching the pacer, so a silenced repeat still played
                # the earcon and logged the line on every re-fire: the quiet
                # rung machine-gunning a sound where coaching says one
                # sentence and falls silent for the rest of the drive.
                # ``is_silenced_repeat``/``note_silenced`` deliberately do NOT
                # share ``is_repeat``/``_conditions`` with the speaking path
                # below: if a silenced occurrence wrote ``_conditions[key]``,
                # raising the rung mid-drive while this same condition was
                # still active (still locked out, still at redline) would
                # have the speaking path's own ``is_repeat`` see its silenced
                # text already on file, read the now-audible occurrence as an
                # unchanged repeat, and skip it -- the rung the player raised
                # specifically to hear this condition going quiet instead.
                return
            if self.settings.speech_disposition(category) is Disposition.EARCON:
                self._play_ladder_earcon(category)
                # The cue is standing in for the words, so it gets the room
                # the words would have had (see _engage_earcon_duck).
                self._engage_earcon_duck()
            self._event_pacer.note_silenced(text, key=key)
            transcript.info("[ladder] %s silenced: %s", self.settings.driving_speech, text)
            if review:
                self.message_log.add(text, MessageCategory.EVENT)
            return
        if isinstance(text, SpokenMessage):
            text = text.render(self.settings.renders_terse())
            if not text:
                return
        if not force and self._ladder_applies() and self._ladder_repeats(text, category, key):
            # Said once already, and this rung only promised once. Logged,
            # so the review keys still answer for it.
            transcript.info("[ladder] %s already said: %s", self.settings.driving_speech, text)
            if review:
                self.message_log.add(text, MessageCategory.EVENT)
            return
        if self._event_pacer.is_repeat(text, key=key, force=force):
            # Already in the player's ear. Not spoken, not logged, not
            # reviewable: as far as the drive is concerned it never happened
            # a second time.
            return
        if priority is None:
            priority = EventPriority.CRITICAL if interrupt else EventPriority.AMBIENT
        if (
            not interrupt
            and priority == EventPriority.AMBIENT
            and self.settings.sapi_events
            and self._event_pacer.would_start_stale(text, priority)
        ):
            # Chatter that would start speaking after the moment it described
            # is dropped, not promoted to an interrupt: losing it costs the
            # player nothing (the enum's own words), and the old stale-flush
            # made the least important class the only one guaranteed to
            # preempt. The review log still keeps the line -- recovery is
            # exactly what the log is for. Not marked heard: the player
            # never heard it, so an identical later moment speaks fresh.
            transcript.info("[pacer] stale ambient dropped: %s", text)
            if review:
                self.message_log.add(text, MessageCategory.EVENT)
            return
        transcript.info("[event] %s", text)
        self._event_pacer.note_spoken(text, key=key)
        cut = None
        if self.settings.sapi_events:
            if interrupt:
                cut = self._event_pacer.note_interrupt(text, priority, category, valid)
            elif self._event_pacer.should_flush(text, priority, valid=valid):
                # The channel is backed up past the point of truth: purging
                # and speaking fresh IS the queued line's honest delivery.
                # The purge can still have cut a line that was genuinely
                # mid-sentence, so it is handed back and requeued behind this
                # one exactly as an interrupt's would be -- never dropped.
                transcript.info("[pacer] stale event backlog flushed")
                cut = self._event_pacer.take_flush_cut()
                interrupt = True
            self.speech.say_event(text, interrupt)
        else:
            if interrupt:
                cut = self._event_pacer.note_interrupt(text, priority, category, valid)
                _stop_main_speech(self.speech)
            else:
                self._event_pacer.note_queued(text, priority, category, valid)
            self.speech.say(text, interrupt=False)
        self._engage_speech_duck()
        if cut is not None:
            self._requeue_cut_event(cut)
        if review:
            self.message_log.add(text, MessageCategory.EVENT)

    def _engage_earcon_duck(self) -> None:
        """Step the mix back for an earcon, the way it steps back for words.

        Tester Shane, 2026-08-17: "some of the sounds when you put speech in
        quiet mode have been significantly lowered." Measured absolutely they
        were not -- the confirmation note came out about 4 dB LOUDER than the
        chime it replaced, and a trooper pass never drops below its old level.
        Both measurements missed the point, because a listener hears a level
        RELATIVE to what is under it.

        A spoken line ducks engine, weather and radio to SPEECH_DUCK_LEVEL
        while it talks. A silenced line returns from ``say_event`` before
        reaching that duck, so its earcon played against the full road bed --
        roughly 6 dB worse off than the words it stands in for, and quiet is
        precisely the rung where confirmation, status and coaching ALL become
        earcons. So the sound that carries the information was the one
        competing hardest to be heard.

        The window is real seconds and short, because the cues are short: the
        longest (the two-note coaching chime) runs 0.18 s. It is not the
        pacer's projection, which describes a voice that in this case is
        never going to speak.
        """
        if not self.settings.duck_audio_for_speech:
            return
        self._speech_ducked = True
        self._earcon_duck_until = time.monotonic() + EARCON_DUCK_S
        self.audio.set_speech_duck(SPEECH_DUCK_LEVEL)

    def _engage_speech_duck(self) -> None:
        """Step the game mix back while the event voice speaks (R13).

        XAG 105's guideline made a setting: engine, weather, and the radio
        drop to half volume so a warning survives a loud cab without the
        voice itself getting louder. Restoration is edge-driven, not
        polled: update_speech_duck runs once per frame from the main loop
        and restores the mix when the pacer's projection -- the same
        estimate the staleness budget runs on -- says the voice is done.
        """
        if not self.settings.duck_audio_for_speech:
            return
        self._speech_ducked = True
        self.audio.set_speech_duck(SPEECH_DUCK_LEVEL)

    def update_speech_duck(self) -> None:
        """Per-frame: bring the mix back once the event voice falls silent.

        An earcon duck holds for its own short window instead, since the
        pacer has nothing to project for a line that was never spoken.
        """
        if not self._speech_ducked:
            return
        if self._earcon_duck_until and time.monotonic() < self._earcon_duck_until:
            return
        if self._event_pacer.busy():
            return
        self._speech_ducked = False
        self._earcon_duck_until = 0.0
        self.audio.set_speech_duck(1.0)

    def reset_event_condition(self, key: str) -> None:
        """A standing condition has cleared; let it announce itself afresh."""
        self._event_pacer.forget_condition(key)
        # TRANSITIONS means enter, worsen and clear. A condition that
        # genuinely cleared and comes back is an ENTER, even though its text
        # is word-for-word what was said last time -- so the last-text memory
        # has to be dropped here too, or standard swallows the second real
        # warning (test_the_air_brake_lockout_recurs_once_it_clears_and_
        # comes_back, which is the failure this caught).
        self._ladder_last.pop(key, None)

    def pause_event_speech(self) -> None:
        """The player stepped off the road: silence the road and drop its backlog.

        Stopping the channel is what actually purges the voice's own queue --
        without it, everything the road had submitted before the pause is
        still in there and gets performed the moment the player comes back
        (tester transcript, 2026-08-11).
        """
        self._event_pacer.pause()
        _stop_event_speech(self.speech)

    def resume_event_speech(self) -> None:
        """Back at the wheel; nothing from before the pause is news."""
        self._event_pacer.resume()
        _stop_event_speech(self.speech)

    @contextlib.contextmanager
    def player_asked(self):
        """Mark everything spoken inside as an answer to a control press.

        Wrapped around the driving state's input handlers rather than added
        to each readout, for the same reason the pacing rule itself is
        central: there are twenty-odd info keys and they gain new siblings
        every week, and a rule that has to be remembered per call site is one
        that will be missed. Anything spoken from a key press is by
        definition something the player asked for.

        Re-entrant and restoring, so a handler that opens a menu which speaks
        does not leave the flag stuck on for the ambient lines that follow.
        """
        previous = self._speech_requested
        self._speech_requested = True
        try:
            yield
        finally:
            self._speech_requested = previous

    def event_voice_busy(self) -> bool:
        """Whether the event voice is mid-delivery right now.

        The same projection the audio duck restores on, so a control that has
        to decide "is there anything to shut up" is trusting the estimate the
        mix already trusts rather than inventing a second one.
        """
        return self._event_pacer.busy()

    def stop_event_speech(self) -> None:
        self._event_pacer.reset()
        _stop_event_speech(self.speech)

    def stop_speech(self) -> None:
        """Silence all in-progress speech on both channels (main and event).

        Menus and readers speak through the main channel, so the driving-only
        ``stop_event_speech`` does not quiet them. This silences everything so a
        single key works as a "stop talking" everywhere in the game.
        """
        self._event_pacer.reset()
        _stop_main_speech(self.speech)
        _stop_event_speech(self.speech)

    # -- state stack ------------------------------------------------------------

    def push_state(self, state: State, should_enter: bool = True) -> None:
        self._app.push_state(state, should_enter)

    def pop_state(self, should_exit: bool = True, reentry: bool = True) -> None:
        self._app.pop_state(should_exit, reentry)

    def replace_state(self, state: State, should_exit: bool = True, reentry: bool = True) -> None:
        self._app.replace_state(state, should_exit, reentry)

    def reset_to(self, state: State, should_exit: bool = True, reentry: bool = True) -> None:
        self._app.reset_to(state, should_exit, reentry)

    def quit(self) -> None:
        self._app.running = False

    def apply_active_radio_settings(self) -> None:
        """Apply a radio settings change to a covered drive, right now.

        Flipping streamer-safe from the pause settings is a promise about
        what is on the air at this moment; the active drive must react
        while the menu still covers it, not at some later reception tick."""
        for state in reversed(self._app.states):
            apply = getattr(state, "apply_radio_settings_now", None)
            if apply is not None:
                apply()
                break

    def save_profile(self) -> None:
        # Driving-school sandbox: the profile is a throwaway copy and must
        # never reach disk; the real save is restored when school ends.
        # Playtest-lever sandbox: a forced scenario run is temporary by
        # default -- the career file on disk stays exactly as it was.
        if getattr(self, "school_sandbox", False) or getattr(self, "playtest_sandbox", False):
            return
        if self.profile is not None:
            self.profile.save()

    def apply_volumes(self) -> None:
        self.audio.set_volumes(
            master=self.settings.master_volume,
            sfx=self.settings.sfx_volume,
            music=self.settings.music_volume,
            weather=self.settings.weather_volume,
            engine=self.settings.engine_volume,
            ui=self.settings.ui_volume,
        )
        self.audio.set_engine_voice(self.settings.engine_voice == "classic")
        self.audio.set_jake_voice(self.settings.jake_voice == "classic")

    def apply_presence(self) -> None:
        """Reflect the Discord presence setting (e.g. after a settings change)."""
        self._app.presence.set_enabled(self._online_enabled(self.settings.discord_presence))

    def apply_online_presence(self) -> None:
        """Reflect the drivers-board setting (e.g. after a settings change)."""
        enabled = (
            self._online_enabled(self.settings.online_presence)
            and not self.settings.profile_sharing_pending_off
        )
        self._app.online.set_enabled(enabled)
        self._app.journal.set_enabled(enabled)

    def apply_cloud_saves(self) -> None:
        """Reflect the cloud backup setting (e.g. after a settings change)."""
        self._app.cloud.set_enabled(self._online_enabled(self.settings.cloud_saves))

    def apply_mastodon_sharing(self) -> None:
        """Reflect the Mastodon sharing setting (e.g. after a settings change)."""
        self._app.mastodon.set_enabled(self._online_enabled(self.settings.mastodon_sharing))

    def cloud_saves_service(self) -> CloudSaves:
        """The backup service, for the Cloud backup menu."""
        return self._app.cloud

    def adopt_online_identity(self, identity) -> None:
        """Adopt freshly confirmed account credentials (setup flow). The
        drivers board and cloud backup share them."""
        self._app.online.set_identity(identity)
        self._app.cloud.set_identity(identity)
        self._app.journal.set_identity(identity)
        self._app.mastodon.set_identity(identity)

    def apply_controller(self) -> None:
        """Reflect the controller setting (e.g. after a settings change)."""
        self.controller.set_enabled(self.settings.controller_enabled)

    def apply_haptics(self) -> None:
        """Reflect the haptics setting (e.g. after a settings change)."""
        self.controller.set_haptics_enabled(self.settings.haptics_enabled)

    def control_hint(self, action: str) -> str:
        """Name a control for a spoken prompt, following the active device."""
        return self.controller.hint(action)

    def apply_speech(self) -> None:
        self.speech.select_event_backend(
            self.settings.event_backend if self.settings.sapi_events else None
        )
        # If the saved voice was not on this machine (e.g. a Windows save's
        # SAPI opened on macOS), record the one actually used so the menu and
        # later sessions reflect reality.
        if self.settings.sapi_events:
            actual = self.speech.event_backend_name
            if actual not in ("none", "unknown") and actual != self.settings.event_backend:
                self.settings.event_backend = actual
        self.speech.configure(
            rate=self.settings.speech_rate,
            pitch=self.settings.speech_pitch,
            volume=self.settings.speech_volume,
            voice=self.settings.speech_voice or None,
        )

    def next_music_track(self, pool_name: str, sequence: tuple[str, ...]) -> str:
        """Advance a session-local music pool without immediate repeats."""
        if not sequence:
            return ""
        if len(sequence) == 1:
            track = sequence[0]
            self._music_pool_last[pool_name] = track
            return track
        key = (pool_name, sequence)
        index = (self._music_pool_positions.get(key, -1) + 1) % len(sequence)
        if sequence[index] == self._music_pool_last.get(pool_name):
            index = (index + 1) % len(sequence)
        self._music_pool_positions[key] = index
        track = sequence[index]
        self._music_pool_last[pool_name] = track
        return track

    def play_music_sequence(
        self,
        pool_name: str,
        sequence: tuple[str, ...],
        *,
        fade_ms: int = 1500,
        advance: bool = False,
    ) -> str:
        """Play or refresh a pool without jarring compatible menu restarts."""
        if (
            not advance
            and self._music_rotation_pool is not None
            and self._music_rotation_track is not None
            and self._music_rotation_pool[0] == pool_name
        ):
            self._music_rotation_pool = (pool_name, sequence)
            return self._music_rotation_track
        track = self.next_music_track(pool_name, sequence)
        if not track:
            self.clear_music_rotation()
            return track
        self._music_rotation_pool = (pool_name, sequence)
        self._music_rotation_track = track
        self._music_rotation_elapsed_s = 0.0
        self.audio.play_music(track, fade_ms=fade_ms)
        return track

    def update_music_rotation(self, dt: float) -> None:
        """Advance music beds when their one-shot playback ends."""
        if self._music_rotation_pool is None or self._music_rotation_track is None:
            # No menu bed is rotating. A drive sitting under this menu (pause,
            # settings, a traffic stop...) keeps its own playlist turning over,
            # so the music does not fall silent when the current track ends.
            for state in reversed(self._app.states[:-1]):
                tick = getattr(state, "tick_covered_music", None)
                if tick is not None:
                    tick(dt)
                    break
            return
        self._music_rotation_elapsed_s += max(0.0, dt)
        if self._music_rotation_elapsed_s < music_track_duration_s(self._music_rotation_track):
            return
        pool_name, sequence = self._music_rotation_pool
        self.play_music_sequence(pool_name, sequence, advance=True)

    def clear_music_rotation(self) -> None:
        self._music_rotation_pool = None
        self._music_rotation_track = None
        self._music_rotation_elapsed_s = 0.0

    def award_achievement(
        self,
        achievement_id: str,
        *,
        event: bool = False,
        interrupt: bool = False,
        announce: bool = True,
    ) -> AchievementAward | None:
        if self.profile is None:
            return None
        result = award(self.profile, achievement_id)
        if result is None:
            return None
        # Through the guard: a sandboxed session's achievements evaporate
        # with the rest of the run instead of leaking to disk.
        self.save_profile()
        from .online_journal import queue_achievement

        if queue_achievement(
            self._app.journal, result.achievement, earned_at_ms=int(time.time() * 1000)
        ):
            self._app.journal.flush_async()
        self.achievement_notice = result.message
        self.achievement_notice_timer = 12.0
        if not announce:
            return result
        self.audio.play("ui/level_up", volume=0.8)
        # Live, an achievement is its earcon and its name; the flavor prose is
        # never read at speed (research doc R9). The full record still reaches
        # the review log, and the achievements menu keeps it for good.
        from .speech_text import achievement_announced

        self.say(achievement_announced(result.achievement.name), interrupt=interrupt, review=False)
        self.message_log.add(str(result.message), MessageCategory.GENERAL)
        return result


class App:
    def __init__(self) -> None:
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        # Opt PS4/PS5 pads into HIDAPI rumble so their motors work like Xbox
        # pads. Must be set before pygame.init(); Xbox/XInput needs no flag.
        os.environ.setdefault("SDL_JOYSTICK_HIDAPI_PS4_RUMBLE", "1")
        os.environ.setdefault("SDL_JOYSTICK_HIDAPI_PS5_RUMBLE", "1")
        if os.environ.get("FREIGHT_FATE_NO_SPEECH"):
            os.environ["SDL_VIDEODRIVER"] = "dummy"
            os.environ["SDL_AUDIODRIVER"] = "dummy"
        # Kick the ~225MB sound pack's read-and-unmask onto a background
        # thread before anything else: it has no dependency on pygame or the
        # world data that follows, so it overlaps the rest of startup instead
        # of stalling the first sound played (see assets_pack.open_default).
        prefetch_sound_pack()
        pygame.init()
        pygame.display.set_caption(f"Freight Fate {__version__}")
        self.screen = pygame.display.set_mode(WINDOW_SIZE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Segoe UI, DejaVu Sans, Arial", 26)
        self.font_big = pygame.font.SysFont("Segoe UI, DejaVu Sans, Arial", 34, bold=True)

        self.settings = Settings.load()
        self.speech = Speech()
        self.message_log = MessageLog()
        self.audio = AudioEngine()
        self.world = get_world()
        self.economy = Economy()
        self.presence = DiscordPresence(enabled=self.settings.discord_presence)
        # OnlineIdentity/OnlinePresence/CloudSaves/JournalOutbox are imported
        # here rather than at module level so a launch that never touches
        # keyring or cryptography.hazmat (see online_presence._keyring and
        # cloud_save_integrity.verify_cloud_revision) does not pay their
        # import cost either.
        #
        # identity is loaded unconditionally, not gated on whether any
        # online setting is currently on: OnlinePresence/CloudSaves.
        # set_enabled() both refuse to turn on without an identity already in
        # hand (see online_presence.OnlinePresence.set_enabled), and nothing
        # re-loads it when a player flips a setting on mid-session -- only
        # the account-link flow (adopt_online_identity) does that. A player
        # who linked an account and then turned every online setting off
        # must still be able to turn one back on later without re-pasting
        # credentials. The load itself stays cheap for the common case
        # anyway: no account ever linked means no online.json, and
        # OnlineIdentity.load() returns before touching keyring at all.
        from .online_presence import OnlineIdentity, OnlinePresence

        identity = OnlineIdentity.load()
        self.online = OnlinePresence(
            enabled=self.settings.online_presence,
            identity=identity,
        )
        from .cloud_saves import CloudSaves

        self.cloud = CloudSaves(
            enabled=self.settings.cloud_saves,
            identity=identity,
        )
        from .online_journal import JournalOutbox

        self.journal = JournalOutbox(
            identity=identity,
            enabled=self.settings.online_presence,
            path=OnlineIdentity.path().with_name("online-outbox.json"),
        )
        # Mastodon shares ride the same durable-outbox machinery but keep
        # their own file and enabled flag: posting to the player's own
        # Mastodon account is a separate consent from public Profile sharing.
        self.mastodon = JournalOutbox(
            identity=identity,
            enabled=self.settings.mastodon_sharing,
            path=OnlineIdentity.path().with_name("online-mastodon-outbox.json"),
        )
        # Every profile save, wherever it happens, queues a cloud backup.
        from .models import profile as profile_module

        def saved_profile(profile) -> None:
            self.cloud.queue_backup(profile)

        self._profile_save_listener = saved_profile
        profile_module.save_listener = saved_profile
        self.controller = ControllerManager(
            enabled=self.settings.controller_enabled,
            haptics=self.settings.haptics_enabled,
        )
        # What the player is holding, as driving polls it. Fed from the
        # event loop so a screen reader that re-sends keys as instant
        # press-and-release pairs (JAWS) still reads as a hold.
        self.held_keys = HeldKeys()
        self.ctx = GameContext(self)
        self.ctx.apply_volumes()
        self.ctx.apply_speech()

        self.states: list[State] = []
        self.running = False

    # -- state stack ------------------------------------------------------------

    @property
    def state(self) -> State | None:
        return self.states[-1] if self.states else None

    def push_state(self, state: State, should_enter: bool = True) -> None:
        self.held_keys.clear()  # a new screen never inherits held keys
        self.states.append(state)
        if should_enter:
            state.enter()

    def _handle_close_request(self) -> None:
        """Alt+F4 and the window's close button ask, they do not just go.

        Closing the window used to end the process on the spot. Mid-drive
        that is destructive and silent: saving happens only at stops, so the
        leg being driven is gone and the save still points at the last stop.
        Darren lost two routes to a mis-hit Alt+F4 and asked for the same
        gate Escape already puts in front of quitting (2026-08-22).

        The second close request is obeyed without further argument. A
        confirmation the player cannot get past would be a worse bug than
        the one it fixes -- if speech has dropped, or the dialog is somehow
        unreachable, Alt+F4 twice always closes the game.
        """
        from .states.main_menu import ConfirmQuitState

        if isinstance(self.state, ConfirmQuitState):
            self.running = False
            return
        self.push_state(ConfirmQuitState(self.ctx, unsaved_drive=self._drive_in_progress()))

    def _drive_in_progress(self) -> bool:
        """Whether a leg is being driven right now, saved nowhere."""
        from .states.driving import DrivingState

        return any(isinstance(state, DrivingState) for state in self.states)

    def _take_top(self, should_exit: bool = True) -> None:
        """Lift the top state off the stack, without deciding what follows.

        Emptying the stack only ends the game when the player backed out of the
        last state; the rebuilding methods below empty it on their way to a new
        state, so they use this instead of pop_state.
        """
        if self.states:
            self.held_keys.clear()
            state = self.states.pop()
            if should_exit:
                state.exit()

    def pop_state(self, should_exit: bool = True, reentry: bool = True) -> None:
        self._take_top(should_exit)
        if self.state is not None:
            if reentry:
                self.state.enter()
        else:
            self.running = False

    def replace_state(self, state: State, should_exit: bool = True, reentry: bool = True) -> None:
        self._take_top(should_exit)
        self.push_state(state, reentry)

    def reset_to(self, state: State, should_exit: bool = True, reentry: bool = True) -> None:
        while self.states:
            self._take_top(should_exit)
        self.push_state(state, reentry)

    def _dispatch_controller(self, event: pygame.event.Event) -> None:
        """Feed a controller event to the manager, then to the active state.

        The manager updates its cached axis/modifier/hot-plug state first and
        reports whether the event is an accepted button press for the bound
        controller; only those reach the state, so a duplicate from a pad that
        enumerates twice can never fire an action a second time.
        """
        forward = self.controller.process_event(event)
        if forward and self.controller.active and self.state is not None:
            self.state.handle_controller(event, self.controller)

    def dispatch_to_state(self, event: pygame.event.Event) -> None:
        """Hand a keyboard/window event to the active state.

        Message review gets first refusal on every key press, which is what
        makes the review controls work on every screen instead of only the ones
        that remembered to call ``handle_message_review``. A state that takes
        typed text declines them itself.
        """
        if self.state is None:
            return
        if event.type == pygame.KEYDOWN:
            self.controller.note_keyboard()
            if self.state.handle_message_review(event):
                return
        self.state.handle_event(event)

    # -- main loop ------------------------------------------------------------

    def run(self, max_frames: int | None = None) -> None:
        """Main loop. ``max_frames`` runs that many frames then exits
        cleanly; used by the --smoke build check."""
        from .states.main_menu import MainMenuState

        self.running = True
        self.push_state(MainMenuState(self.ctx))
        self.presence.start()  # after init; never blocks if Discord is absent
        self.online.start()  # opt-in drivers board; dormant unless confirmed
        self.cloud.start()  # opt-in save backup; dormant unless confirmed
        frames = 0
        try:
            while self.running:
                dt = self.clock.tick(FPS) / 1000.0
                try:
                    events = pygame.event.get()
                except Exception:
                    # A controller hot-plug (notably a Bluetooth resume) can make
                    # SDL's internal instance-id map inconsistent, and pygame's
                    # controller layer then raises out of the C event pump
                    # (KeyError surfacing as SystemError). Losing this batch of
                    # events is survivable; crashing the game is not.
                    log.exception(
                        "pygame.event.get() failed (frame %d; controller %s); skipping this batch",
                        frames,
                        "connected" if self.controller.connected else "disconnected",
                    )
                    with contextlib.suppress(Exception):
                        pygame.event.pump()
                    continue
                self.held_keys.begin_frame(pygame.time.get_ticks())
                for event in events:
                    self.held_keys.note(event)
                    if event.type == pygame.WINDOWFOCUSGAINED:
                        # Switching screen readers happens outside the game;
                        # re-check speech the moment the player comes back.
                        self.speech.request_refresh()
                    if event.type == pygame.QUIT:
                        self._handle_close_request()
                    elif event.type in _CONTROLLER_EVENTS:
                        self._dispatch_controller(event)
                    elif self.state is not None:
                        self.dispatch_to_state(event)
                # Auto-repeat (held D-pad left/right) and analog smoothing.
                # Synthetic repeats go straight to the state (bypassing the
                # manager, whose press state must not be reset) and only where
                # the menu wants adjust-repeat -- driving keeps D-pad discrete.
                repeats = self.controller.tick(dt)
                state = self.state
                if state is not None and getattr(state, "wants_controller_repeat", False):
                    for event in repeats:
                        state.handle_controller(event, self.controller)
                # Reconnect speech if the player's screen reader changed.
                self.speech.poll(dt)
                if self.controller.take_disconnect():
                    self.ctx.say(
                        "Controller disconnected. You can keep playing with the "
                        "keyboard, or reconnect your controller.",
                    )
                    if self.state is not None:
                        self.state.on_controller_disconnect()
                # Cloud backup refusals speak wherever the player is --
                # driving or in menus -- not only on the terminal's Save
                # game item: the worker thread queues them and this loop
                # delivers, queued on the normal announcement channel so a
                # backup notice never cuts off urgent driving speech.
                for line in self.cloud.take_announcements():
                    self.ctx.say(line, interrupt=False)
                self.ctx.audio.update(dt)  # advance time-based audio fades
                self.ctx.update_speech_duck()  # restore the mix after speech
                if self.state is not None:
                    self.state.update(dt)
                    self.presence.update(self.state.presence())
                    self.online.update(self.state.online_presence())
                if self.ctx.achievement_notice_timer > 0:
                    self.ctx.achievement_notice_timer = max(
                        0.0,
                        self.ctx.achievement_notice_timer - dt,
                    )
                    if self.ctx.achievement_notice_timer == 0:
                        self.ctx.achievement_notice = ""
                self.render()
                frames += 1
                if max_frames is not None and frames >= max_frames:
                    self.running = False
        finally:
            self.shutdown()

    def render(self) -> None:
        self.screen.fill(BG_COLOR)
        state = self.state
        if state is not None:
            y = 30
            base_lines = state.lines()
            if self.ctx.achievement_notice:
                lines = base_lines[:16] + ["", self.ctx.achievement_notice]
            else:
                lines = base_lines[:18]
            for i, line in enumerate(lines[:18]):
                font = self.font_big if i == 0 else self.font
                color = HILIGHT_COLOR if line.startswith("> ") else TEXT_COLOR
                surf = font.render(line, True, color)
                self.screen.blit(surf, (40, y))
                y += font.get_height() + 6
        pygame.display.flip()

    def shutdown(self) -> None:
        # Through the guard, not straight to disk: the quit-time save is how
        # a sandboxed playtest session leaked its whole run onto the real
        # career (owner-found live: the Denver snow run persisted at quit
        # despite the sandbox holding for the entire drive).
        self.ctx.save_profile()
        self.settings.save()
        self.presence.shutdown()
        self.online.shutdown()
        self.cloud.shutdown()  # flushes the final save's backup, bounded
        from .models import profile as profile_module

        if profile_module.save_listener == self._profile_save_listener:
            profile_module.save_listener = None
        self.controller.shutdown()
        self.audio.shutdown()
        self.speech.shutdown()
        pygame.quit()


def _configure_logging() -> None:
    """Console logging from source; a fresh log file in the packaged game.

    The windowed build has no console, so without a file every warning --
    update failures especially -- vanishes. The log lives in the game folder
    (logs/game.log) where a player can find and share it without mixing it
    with durable saves.
    """
    global _log_file
    from . import updater

    packaged = updater.is_frozen()
    # An explicit log file (set for playtests/observation) forces file output and
    # an INFO default even from a source checkout, so a session can be reviewed
    # after the fact without streaming to a console.
    explicit_log_file = os.environ.get("FREIGHT_FATE_LOG_FILE")
    default_level = "INFO" if (packaged or explicit_log_file) else "WARNING"
    level = os.environ.get("FREIGHT_FATE_LOG", default_level)
    handlers = None

    log_path = None
    if explicit_log_file:
        log_path = Path(explicit_log_file)
    elif packaged:
        from .models.profile import game_root

        log_path = game_root() / "logs" / "game.log"
    if log_path is not None:
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            # Keep the previous run's log as game.prev.log: after a crash the
            # player relaunches the game to report it, and that relaunch must
            # not wipe the evidence.
            if log_path.exists():
                # Rotation is best-effort; a locked file still gets a fresh log.
                prev = log_path.with_name(f"{log_path.stem}.prev{log_path.suffix}")
                with contextlib.suppress(OSError):
                    log_path.replace(prev)
            handlers = [logging.FileHandler(log_path, mode="w", encoding="utf-8")]
            # Crashes inside native libraries (audio, video) kill the process
            # without ever reaching Python logging; faulthandler writes the
            # tracebacks straight to the log file as the process dies.
            faulthandler.enable(file=handlers[0].stream)
            _log_file = log_path
        except OSError:
            pass  # unwritable disk: console-only is the best we can do
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> int:
    _configure_logging()
    smoke = "--smoke" in sys.argv[1:]  # CI: boot, render a few frames, exit 0
    from .single_instance import SingleInstanceGuard

    guard = SingleInstanceGuard()
    if not guard.acquire():
        log.warning("Freight Fate is already running.")
        return 0
    try:
        if smoke:
            # The build check must prove world data loads (frozen builds
            # carry it baked into the executable, not as files) and that
            # sound assets are readable (frozen builds ship a pack file).
            from .audio import verify_sound_assets
            from .data.world import get_world
            from .online_presence import secret_store_report

            get_world()
            verify_sound_assets()
            # And the deepest load path: continuing a career imports the
            # driving stack, which reads every baked runtime data file. A
            # missing file must fail the build here, not a player's first
            # Continue career (frozen 1.9 canary, 2026-07-18).
            from .data.buffs import BUFF_CATALOG
            from .data.curves import leg_curves
            from .data.world_local_data import load_facility_approaches
            from .radio import load_radio_catalog
            from .states import driving  # noqa: F401

            if not BUFF_CATALOG:
                raise RuntimeError("smoke: buff catalog is empty")
            if not leg_curves("aberdeen_sd_us:pierre_sd_us"):
                raise RuntimeError("smoke: curve shard is empty")
            if not load_facility_approaches():
                raise RuntimeError("smoke: facility approaches are empty")
            load_radio_catalog()
            # And that the online driver token can still reach the platform
            # secret store: keyring finds its backends through entry points,
            # which a packaged build loses silently (see secret_store_report).
            store_ok, store_detail = secret_store_report()
            log.info("Secret store: %s", store_detail)
            if not store_ok:
                raise RuntimeError(f"Secret store unreachable in this build: {store_detail}")
        App().run(max_frames=5 if smoke else None)
    except Exception:
        log.exception("Fatal error")
        return 1
    finally:
        guard.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
