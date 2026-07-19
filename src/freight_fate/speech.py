"""Screen reader output via Prism (the ``prismatoid`` package).

Prism is a screen reader abstraction layer that unifies NVDA, JAWS, SAPI,
VoiceOver, Speech Dispatcher, and many other backends behind one API. This
module wraps it in a small game-friendly interface that:

* never crashes the game if speech is unavailable (silent fallback),
* picks the best backend that is actually usable on this machine: Prism's
  ``acquire_best`` cannot be trusted for this -- it returns the highest
  priority backend that already has a live cached instance (whatever the
  game happens to be holding), and otherwise ranks by static registry
  priority whether or not that screen reader is running -- so the registry
  is enumerated in priority order and every candidate is validated against
  its live ``is_supported_at_runtime`` check,
* treats Prism's ``UIA`` backend (the route to Narrator, via UI Automation
  notifications) as a gated last resort: it reports runtime support on every
  modern Windows whether or not anyone is listening, so it is skipped unless
  Narrator is actually running -- and even then it only wins when no other
  voice works, because the backend raises every notification with
  ``NotificationProcessing_ImportantAll``, which Narrator queues without
  ever cancelling: interrupt and stop are no-ops, so menu browsing through
  it piles up unread items,
* keeps watching while the game runs: if the player switches screen readers
  mid-session (NVDA off, Narrator on, back to NVDA), a periodic health check
  re-detects the running one and reconnects speech instead of going silent,
* prefers ``output`` (speech + braille) and falls back to ``speak``,
* can be disabled with the ``FREIGHT_FATE_NO_SPEECH=1`` environment variable
  (used by the headless test suite and CI), and forced to a specific backend
  with ``FREIGHT_FATE_SPEECH_BACKEND=<name>`` (for example ``SAPI``).
"""

from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger(__name__)

# Seconds between runtime health checks of the speech backend. Short enough
# that a player who switches screen readers hears the game again within a few
# seconds, long enough that the registry scan costs nothing per frame.
REFRESH_INTERVAL_S = 3.0


def _usable(backend) -> bool:
    """True when the backend can actually speak on this machine right now."""
    try:
        features = backend.features
    except Exception:
        return False
    return bool(
        features.is_supported_at_runtime and (features.supports_output or features.supports_speak)
    )


def _narrator_running() -> bool:
    """True when Windows Narrator is up.

    Narrator has no client API of its own: Prism reaches it through UI
    Automation notifications (the ``UIA`` backend), and only a running
    Narrator reads those aloud. The backend cannot tell the difference --
    it reports runtime support whenever UIA itself exists, which is every
    modern Windows -- so the process check lives here."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        class ProcessEntry32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260),
            ]

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
        if snapshot in (None, wintypes.HANDLE(-1).value):
            return False
        try:
            entry = ProcessEntry32W()
            entry.dwSize = ctypes.sizeof(ProcessEntry32W)
            found = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
            while found:
                if entry.szExeFile.lower() == "narrator.exe":
                    return True
                found = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
            return False
        finally:
            kernel32.CloseHandle(snapshot)
    except Exception:
        log.debug("Narrator detection failed", exc_info=True)
        return False


def _name_of(ctx, backend_id) -> str:
    try:
        return ctx.name_of(backend_id)
    except Exception:
        return str(backend_id)


# Ranks the UIA backend below every other voice even while Narrator is
# running. Prism's UIA backend raises all notifications with
# NotificationProcessing_ImportantAll, which Narrator queues without ever
# cancelling -- interrupt and stop are no-ops -- so menu browsing through it
# stacks up unread items. Until that is fixed upstream (the fix is
# ImportantMostRecent for the interrupt case), UIA is only for machines
# where nothing else can speak at all: queued speech beats silence.
_UIA_LAST_RESORT_PRIORITY = -1


def pick_backend(ctx, override: str | None = None):
    """Choose a speech backend from a Prism context.

    Prism's ``acquire_best`` is unsuitable: it returns the highest-priority
    backend that merely has a live cached instance -- which is whatever this
    game already holds, so a screen reader started mid-session would never be
    noticed -- and otherwise ranks by static registry priority whether or not
    that screen reader is running. Instead, enumerate the registry in
    priority order and validate every candidate against its live runtime
    check. The ``UIA`` backend (Narrator's route) claims runtime support
    unconditionally, so it is skipped unless Narrator is actually running,
    and even then ranked last (see ``_UIA_LAST_RESORT_PRIORITY``). Returns
    None when nothing on the machine can speak.
    """
    if override:
        try:
            backend = ctx.acquire(ctx.id_of(override))
            if _usable(backend):
                return backend
            log.warning(
                "Requested speech backend %s is not usable; falling back to automatic choice",
                override,
            )
        except Exception:
            log.warning(
                "Requested speech backend %s not found; falling back to automatic choice",
                override,
                exc_info=True,
            )
    try:
        narrator = _narrator_running()
        candidates = []
        for index in range(ctx.backends_count):
            backend_id = ctx.id_of(index)
            name = _name_of(ctx, backend_id)
            if name == "UIA":
                if not narrator:
                    continue
                priority = _UIA_LAST_RESORT_PRIORITY
            else:
                priority = ctx.priority_of(backend_id)
            candidates.append((priority, backend_id))
        candidates.sort(key=lambda entry: entry[0], reverse=True)
    except Exception:
        log.warning("Could not enumerate speech backends", exc_info=True)
        return None
    for _, backend_id in candidates:
        try:
            backend = ctx.acquire(backend_id)
        except Exception:
            continue
        if _usable(backend):
            return backend
    return None


# Preferred separate event voice per platform; the first one that exists wins.
# These are the controllable software TTS engines, not screen readers: SAPI is
# Windows, AVSpeech is macOS, Speech Dispatcher is Linux. ``select_event_backend``
# falls back to whatever the machine actually has, so this is only a hint.
EVENT_BACKEND = "SAPI"


def pick_event_backend(ctx, main_backend, name: str = EVENT_BACKEND):
    """A second, independent voice for driving events.

    Screen readers interrupt the game's speech with their own chatter, so
    critical announcements (hazards, warnings) can be cut off mid-sentence.
    Routing events through a dedicated software voice (SAPI on Windows,
    AVSpeech on macOS, Speech Dispatcher on Linux) keeps the two streams
    from talking over each other. Returns None when the main channel
    already is that backend (nothing to separate) or it is unusable, in
    which case events fall back to the main channel.
    """
    if main_backend is None:
        return None
    try:
        if main_backend.name == name:
            return None
    except Exception:
        return None
    try:
        backend = ctx.acquire(ctx.id_of(name))
    except Exception:
        log.info("Event speech backend %s not available", name, exc_info=True)
        return None
    return backend if _usable(backend) else None


class Speech:
    """Speech output channel for the whole game.

    All game text flows through :meth:`say`. ``interrupt=True`` (the default)
    cuts off the previous utterance, which is what menu navigation wants;
    pass ``interrupt=False`` for queued announcements such as tutorial text.
    """

    def __init__(self) -> None:
        self._ctx = None
        self._backend = None
        self._event_backend = None
        self._prism_error: type[Exception] = Exception
        self._override = os.environ.get("FREIGHT_FATE_SPEECH_BACKEND")
        self._event_pref: str | None = None
        self._config: dict[str, float | str] = {}
        self._refresh_timer = 0.0
        if os.environ.get("FREIGHT_FATE_NO_SPEECH"):
            log.info("Speech disabled via FREIGHT_FATE_NO_SPEECH")
            return
        try:
            import prism

            self._ctx = prism.Context()
            self._backend = pick_backend(self._ctx, self._override)
            self._prism_error = prism.PrismError
            if self._backend is None:
                # Keep the context: the player may start their screen reader
                # after the game, and refresh() will connect to it then.
                log.warning("No usable speech backend yet; will keep checking")
            else:
                log.info("Speech backend: %s", self._backend.name)
                self.select_event_backend(EVENT_BACKEND)
                if self._event_backend is not None:
                    log.info("Event speech backend: %s", self.event_backend_name)
        except Exception:
            log.exception("Speech unavailable; continuing silently")
            self._ctx = None
            self._backend = None
            self._event_backend = None

    @property
    def available(self) -> bool:
        return self._backend is not None

    @property
    def backend_name(self) -> str:
        if self._backend is None:
            return "none"
        try:
            return self._backend.name
        except Exception:
            return "unknown"

    @property
    def event_backend_name(self) -> str:
        if self._event_backend is None:
            return "none"
        try:
            return self._event_backend.name
        except Exception:
            return "unknown"

    # -- adjustable parameters -------------------------------------------------
    #
    # Prism exposes rate, pitch, volume (each a 0..1 float) and voice (an index)
    # per backend, gated by feature flags. Running screen readers such as NVDA
    # report no support -- they own those settings themselves -- while software
    # voices like SAPI and OneCore support all of them. A change is pushed to
    # every backend that supports it, so the main voice and the separate event
    # voice stay in sync.

    def _backends(self):
        return [b for b in (self._backend, self._event_backend) if b is not None]

    @staticmethod
    def _backend_supports(backend, feature: str) -> bool:
        try:
            return bool(getattr(backend.features, feature))
        except Exception:
            return False

    def _any_supports(self, feature: str) -> bool:
        return any(self._backend_supports(backend, feature) for backend in self._backends())

    @property
    def supports_rate(self) -> bool:
        return self._any_supports("supports_set_rate")

    @property
    def supports_pitch(self) -> bool:
        return self._any_supports("supports_set_pitch")

    @property
    def supports_volume(self) -> bool:
        return self._any_supports("supports_set_volume")

    def event_backend_options(self) -> list[str]:
        """Usable backends that can serve as a separate event voice.

        These are the controllable software voices (SAPI, OneCore, ...) other
        than the main voice -- screen readers are excluded because they cannot
        be driven independently. Ordered by Prism's registry priority."""
        if self._ctx is None or self._backend is None:
            return []
        try:
            main_name = self._backend.name
        except Exception:
            return []
        try:
            ids = [self._ctx.id_of(i) for i in range(self._ctx.backends_count)]
        except Exception:
            return []
        options: list[str] = []
        for backend_id in ids:
            try:
                backend = self._ctx.acquire(backend_id)
                name = backend.name
                if name == main_name or not _usable(backend):
                    continue
                features = backend.features
                if features.supports_set_voice or features.supports_set_rate:
                    options.append(name)
            except Exception:
                continue
        return options

    def select_event_backend(self, name: str | None) -> None:
        """Choose which backend speaks driving events (None = the main voice).

        ``name`` is a preference: if that backend is not on this machine (for
        example a Windows save's ``SAPI`` opened on macOS), the best available
        separate software voice is used instead, so the feature works the same
        on every platform. Falls back to the main voice only when there is no
        separate voice at all."""
        # Remember the preference even when it cannot be honored right now:
        # refresh() re-runs the selection after a backend swap or when a
        # screen reader appears mid-session.
        self._event_pref = name or None
        if self._ctx is None or self._backend is None:
            return
        if not name:
            self._event_backend = None
            return
        options = self.event_backend_options()
        if name not in options and options:
            name = options[0]
        self._event_backend = pick_event_backend(self._ctx, self._backend, name)

    def voice_names(self) -> list[str]:
        """Installed voice names from the first backend that lets us pick one.

        Empty when no backend supports voice selection (for example when the
        only voice is a running screen reader)."""
        for backend in self._backends():
            try:
                features = backend.features
                if (
                    features.supports_set_voice
                    and features.supports_count_voices
                    and features.supports_get_voice_name
                ):
                    return [backend.get_voice_name(i) for i in range(backend.voices_count)]
            except Exception:
                continue
        return []

    def configure(
        self,
        *,
        rate: float | None = None,
        pitch: float | None = None,
        volume: float | None = None,
        voice: str | None = None,
    ) -> None:
        """Push speech parameters to every backend that supports them.

        Unsupported parameters (and backends) are skipped silently, and any
        backend failure is logged without disturbing the others or the game.
        The values are remembered so a backend swap mid-session (see
        :meth:`refresh`) can re-apply the player's settings to the new voice."""
        for key, value in (("rate", rate), ("pitch", pitch), ("volume", volume), ("voice", voice)):
            if value is not None:
                self._config[key] = value
        for backend in self._backends():
            self._configure_backend(backend, rate, pitch, volume, voice)

    def _configure_backend(self, backend, rate, pitch, volume, voice) -> None:
        try:
            features = backend.features
        except Exception:
            return
        for value, supported, attr in (
            (rate, "supports_set_rate", "rate"),
            (pitch, "supports_set_pitch", "pitch"),
            (volume, "supports_set_volume", "volume"),
        ):
            if value is None or not getattr(features, supported, False):
                continue
            if attr == "pitch" and _preserve_backend_default_pitch(backend, value):
                continue
            try:
                setattr(backend, attr, float(value))
            except Exception:
                log.warning(
                    "Could not set speech %s on %s",
                    attr,
                    getattr(backend, "name", "?"),
                    exc_info=True,
                )
        if voice and (
            features.supports_set_voice
            and features.supports_count_voices
            and features.supports_get_voice_name
        ):
            try:
                for i in range(backend.voices_count):
                    if backend.get_voice_name(i) == voice:
                        backend.voice = i
                        break
            except Exception:
                log.warning(
                    "Could not set speech voice on %s", getattr(backend, "name", "?"), exc_info=True
                )

    def _speak_with_backend(self, backend, text: str, interrupt: bool) -> bool:
        try:
            features = backend.features
            if features.supports_output:
                backend.output(text, interrupt)
                return True
            elif features.supports_speak:
                backend.speak(text, interrupt)
                return True
        except self._prism_error:
            log.warning("Speech output failed", exc_info=True)
        except Exception:
            log.exception("Unexpected speech failure")
        return False

    def say(self, text: str, interrupt: bool = True) -> None:
        """Speak (and braille, where supported) the given text."""
        if self._backend is None or not text:
            return
        if self._speak_with_backend(self._backend, text, interrupt):
            return
        # The utterance failed: the screen reader probably just quit or was
        # switched. Re-detect immediately and retry once so this line is not
        # lost; if nothing can speak right now, poll() keeps looking.
        self._backend = None
        if (
            self.refresh(announce=False)
            and self._backend is not None
            and not self._speak_with_backend(self._backend, text, interrupt)
        ):
            self._backend = None

    def say_event(self, text: str, interrupt: bool = True) -> None:
        """Speak on the dedicated event voice (SAPI), so the player's screen
        reader cannot talk over it; falls back to the main channel."""
        if not text:
            return
        backend = self._event_backend
        if backend is None:
            if interrupt:
                self.stop_main()
            self.say(text, interrupt=False)
            return
        # Let the backend perform the interruption as part of the new output
        # call. Calling stop() immediately before output(..., interrupt=True)
        # is redundant and could crash inside Prism's Windows SAPI stop path
        # when urgent road events arrived back to back (issue #85).
        if not self._speak_with_backend(backend, text, interrupt):
            self._event_backend = None
            if interrupt:
                self.stop_main()
            self.say(text, interrupt=False)

    # -- runtime re-detection ----------------------------------------------------
    #
    # The backend chosen at startup can die at any time: players switch screen
    # readers mid-session (NVDA to Narrator and back), restart them, or start
    # them after the game. These hooks notice within a few seconds and rebind
    # speech to whatever is running instead of leaving the game mute.

    def refresh(self, announce: bool = True) -> bool:
        """Re-detect which screen reader or voice should be speaking.

        Runs the same selection as startup: the environment override first,
        then the highest-priority backend that is usable right now. When the
        choice changes, the event voice is re-selected and the player's
        speech settings are re-applied to the new voice. Returns True when
        the main voice changed."""
        if self._ctx is None:
            return False
        old_backend = self._backend
        old_name = self.backend_name if old_backend is not None else None
        try:
            backend = pick_backend(self._ctx, self._override)
        except Exception:
            log.exception("Speech re-detection failed")
            return False
        if backend is None:
            if old_backend is None:
                return False
            log.warning("Speech backend %s went away and nothing else can speak", old_name)
            self._backend = None
            self._event_backend = None
            return True
        try:
            new_name = backend.name
        except Exception:
            new_name = "unknown"
        if old_backend is not None and new_name == old_name:
            # Same main voice as before; just make sure the event voice is
            # alive too (it can die independently, e.g. a SAPI hiccup).
            if self._event_pref and self._event_backend is None:
                self.select_event_backend(self._event_pref)
                if self._event_backend is not None and self._config:
                    self.configure(**self._config)
            return False
        self._backend = backend
        log.info("Speech backend switched: %s -> %s", old_name or "none", new_name)
        self.select_event_backend(self._event_pref)
        if self._config:
            self.configure(**self._config)
        if announce:
            # The UIA backend is how the game reaches Narrator; players know
            # the screen reader's name, not the plumbing's.
            display = "Narrator" if new_name == "UIA" else new_name
            self.say(f"Speech is now using {display}.", interrupt=False)
        return True

    def poll(self, dt: float) -> None:
        """Periodic health check, driven every frame by the game loop."""
        if self._ctx is None:
            return
        self._refresh_timer += dt
        if self._refresh_timer < REFRESH_INTERVAL_S:
            return
        self._refresh_timer = 0.0
        self.refresh()

    def request_refresh(self) -> None:
        """Make the next :meth:`poll` re-detect immediately.

        Called when the game window regains focus: switching screen readers
        happens outside the game, so that is the moment a change most likely
        just occurred."""
        self._refresh_timer = REFRESH_INTERVAL_S

    _PREVIEW_FEATURES = {
        "speech_rate": "supports_set_rate",
        "speech_pitch": "supports_set_pitch",
        "speech_volume": "supports_set_volume",
        "speech_voice": "supports_set_voice",
    }

    def say_adjustment_preview(self, setting: str, text: str, interrupt: bool = True) -> bool:
        """Speak a settings preview through the voice affected by the setting.

        If the main screen reader cannot be configured but a separate SAPI or
        OneCore voice can, preview changes through that configurable voice.
        """
        feature = self._PREVIEW_FEATURES.get(setting)
        if feature is None or not text:
            return False
        for backend in self._backends():
            if self._backend_supports(backend, feature):
                return self._speak_with_backend(backend, text, interrupt)
        return False

    @staticmethod
    def _stop_backend(backend) -> None:
        if backend is None:
            return
        try:
            if backend.features.supports_stop:
                backend.stop()
        except Exception:
            pass

    def stop_main(self) -> None:
        """Silence in-progress main speech without cutting off event speech."""
        self._stop_backend(self._backend)

    def stop_event(self) -> None:
        """Silence in-progress event speech without cutting off main speech."""
        self._stop_backend(self._event_backend)

    def stop(self) -> None:
        """Silence any in-progress speech on both channels."""
        for backend in (self._backend, self._event_backend):
            self._stop_backend(backend)

    def shutdown(self) -> None:
        """Release the backends and context. Safe to call more than once."""
        self.stop()
        self._backend = None
        self._event_backend = None
        self._ctx = None


def _preserve_backend_default_pitch(backend, value: float) -> bool:
    """Some backends, notably OneCore, use their own native default pitch.

    Prism reports that default as NaN on Windows. Forcing the neutral settings
    value onto it changes the sound, so leave pitch untouched until the player
    deliberately moves the setting away from the midpoint.
    """
    name = getattr(backend, "name", "")
    return name.lower() in {"onecore", "one_core"} and float(value) == 0.5
