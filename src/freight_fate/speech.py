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


class Speech:
    """Speech output channel for the whole game.

    All game text flows through :meth:`say`. ``interrupt=True`` (the default)
    cuts off the previous utterance, which is what menu navigation wants;
    pass ``interrupt=False`` for queued announcements such as tutorial text.
    """

    def __init__(self) -> None:
        self._ctx = None
        self._backend = None
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
        except Exception:
            log.exception("Speech unavailable; continuing silently")
            self._ctx = None
            self._backend = None

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

    def stop(self) -> None:
        """Silence any in-progress speech."""
        if self._backend is None:
            return
        try:
            if self._backend.features.supports_stop:
                self._backend.stop()
        except Exception:
            pass

    def shutdown(self) -> None:
        """Release the backend and context. Safe to call more than once."""
        self.stop()
        self._backend = None
        self._ctx = None
