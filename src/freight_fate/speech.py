"""Screen reader output via Prism (the ``prismatoid`` package).

Prism is a screen reader abstraction layer that unifies NVDA, JAWS, SAPI,
VoiceOver, Speech Dispatcher, and many other backends behind one API. This
module wraps it in a small game-friendly interface that:

* never crashes the game if speech is unavailable (silent fallback),
* picks the best backend that is actually usable on this machine: Prism's
  registry lists every backend it was compiled with (NVDA first by static
  priority) whether or not that screen reader is running, so the choice is
  validated against ``is_supported_at_runtime`` and falls down the priority
  list instead of binding to a screen reader that is not there,
* prefers ``output`` (speech + braille) and falls back to ``speak``,
* can be disabled with the ``FREIGHT_FATE_NO_SPEECH=1`` environment variable
  (used by the headless test suite and CI), and forced to a specific backend
  with ``FREIGHT_FATE_SPEECH_BACKEND=<name>`` (for example ``SAPI``).
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


def _usable(backend) -> bool:
    """True when the backend can actually speak on this machine right now."""
    try:
        features = backend.features
    except Exception:
        return False
    return bool(features.is_supported_at_runtime
                and (features.supports_output or features.supports_speak))


def pick_backend(ctx, override: str | None = None):
    """Choose a speech backend from a Prism context.

    ``acquire_best`` ranks by static registry priority, which can return a
    screen reader that is installed in the registry but not running (NVDA
    outranks everything). Validate its runtime support, then fall back
    through the remaining backends in priority order. Returns None when
    nothing on the machine can speak.
    """
    if override:
        try:
            backend = ctx.acquire(ctx.id_of(override))
            if _usable(backend):
                return backend
            log.warning("Requested speech backend %s is not usable; "
                        "falling back to automatic choice", override)
        except Exception:
            log.warning("Requested speech backend %s not found; "
                        "falling back to automatic choice", override,
                        exc_info=True)
    try:
        best = ctx.acquire_best()
        if _usable(best):
            return best
        log.info("Prism's preferred backend %s is not running; "
                 "trying the others", getattr(best, "name", "?"))
    except Exception:
        log.debug("acquire_best failed", exc_info=True)
    try:
        ids = [ctx.id_of(i) for i in range(ctx.backends_count)]
        ids.sort(key=ctx.priority_of, reverse=True)
    except Exception:
        log.warning("Could not enumerate speech backends", exc_info=True)
        return None
    for backend_id in ids:
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
        if os.environ.get("FREIGHT_FATE_NO_SPEECH"):
            log.info("Speech disabled via FREIGHT_FATE_NO_SPEECH")
            return
        try:
            import prism

            self._ctx = prism.Context()
            self._backend = pick_backend(
                self._ctx, os.environ.get("FREIGHT_FATE_SPEECH_BACKEND"))
            self._prism_error = prism.PrismError
            if self._backend is None:
                log.warning("No usable speech backend on this machine; "
                            "continuing silently")
                self._ctx = None
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

    def _any_supports(self, feature: str) -> bool:
        for backend in self._backends():
            try:
                if getattr(backend.features, feature):
                    return True
            except Exception:
                continue
        return False

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
                if (features.supports_set_voice
                        and features.supports_count_voices
                        and features.supports_get_voice_name):
                    return [backend.get_voice_name(i)
                            for i in range(backend.voices_count)]
            except Exception:
                continue
        return []

    def configure(self, *, rate: float | None = None, pitch: float | None = None,
                  volume: float | None = None, voice: str | None = None) -> None:
        """Push speech parameters to every backend that supports them.

        Unsupported parameters (and backends) are skipped silently, and any
        backend failure is logged without disturbing the others or the game."""
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
                log.warning("Could not set speech %s on %s", attr,
                            getattr(backend, "name", "?"), exc_info=True)
        if voice and (features.supports_set_voice
                      and features.supports_count_voices
                      and features.supports_get_voice_name):
            try:
                for i in range(backend.voices_count):
                    if backend.get_voice_name(i) == voice:
                        backend.voice = i
                        break
            except Exception:
                log.warning("Could not set speech voice on %s",
                            getattr(backend, "name", "?"), exc_info=True)

    def say(self, text: str, interrupt: bool = True) -> None:
        """Speak (and braille, where supported) the given text."""
        if self._backend is None or not text:
            return
        try:
            features = self._backend.features
            if features.supports_output:
                self._backend.output(text, interrupt)
            elif features.supports_speak:
                self._backend.speak(text, interrupt)
        except self._prism_error:
            log.warning("Speech output failed", exc_info=True)
        except Exception:
            log.exception("Unexpected speech failure; disabling speech")
            self._backend = None

    def say_event(self, text: str, interrupt: bool = True) -> None:
        """Speak on the dedicated event voice (SAPI), so the player's screen
        reader cannot talk over it; falls back to the main channel."""
        if not text:
            return
        backend = self._event_backend
        if backend is None:
            self.say(text, interrupt)
            return
        try:
            features = backend.features
            if features.supports_output:
                backend.output(text, interrupt)
            elif features.supports_speak:
                backend.speak(text, interrupt)
        except self._prism_error:
            log.warning("Event speech output failed", exc_info=True)
        except Exception:
            log.exception("Unexpected event speech failure; "
                          "falling back to the main voice")
            self._event_backend = None
            self.say(text, interrupt)

    def stop(self) -> None:
        """Silence any in-progress speech on both channels."""
        for backend in (self._backend, self._event_backend):
            if backend is None:
                continue
            try:
                if backend.features.supports_stop:
                    backend.stop()
            except Exception:
                pass

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
