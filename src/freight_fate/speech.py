"""Screen reader output via Prism (the ``prismatoid`` package).

Prism is a screen reader abstraction layer that unifies NVDA, JAWS, SAPI,
VoiceOver, Speech Dispatcher, and many other backends behind one API. This
module wraps it in a small game-friendly interface that:

* never crashes the game if speech is unavailable (silent fallback),
* prefers ``output`` (speech + braille) and falls back to ``speak``,
* can be disabled with the ``FREIGHT_FATE_NO_SPEECH=1`` environment variable
  (used by the headless test suite and CI).
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


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
            self._backend = self._ctx.acquire_best()
            self._prism_error = prism.PrismError
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
