"""Playing one catalog entry, faithfully and without leaving anything ringing.

A demo is a short script: fire each cue at its moment, hold the ones that are
loops for as long as they declare, and release everything the moment the demo
ends -- whether it ended on its own, was replaced by another, or the screen
was closed underneath it.

Held cues go through ``hold_alert``, which is a dead man's switch: it stops on
its own a fraction of a second after the re-assertions stop. A continuous tone
in a blind player's headphones must never be able to outlive the thing that
started it, and routing every held demo cue through that one mechanism is what
makes that true here without a second watchdog to get wrong.
"""

from __future__ import annotations

from .audio import CH_ALERT
from .sound_catalog import Cue, SoundEntry


class SoundDemo:
    """Sequences one :class:`SoundEntry`'s cues against an audio engine."""

    def __init__(self, audio) -> None:
        self._audio = audio
        self._entry: SoundEntry | None = None
        self._pending: list[Cue] = []
        self._elapsed = 0.0
        self._hold_key = ""
        self._hold_volume = 1.0
        self._hold_left = 0.0

    @property
    def running(self) -> bool:
        return self._entry is not None

    def start(self, entry: SoundEntry) -> None:
        """Play ``entry`` from the top, cancelling whatever was running."""
        self.stop()
        self._entry = entry
        self._pending = sorted(entry.plays, key=lambda cue: cue.delay_s)
        self._elapsed = 0.0
        self._fire_due()

    def update(self, dt: float) -> None:
        if self._entry is None:
            return
        self._elapsed += dt
        self._fire_due()
        if self._hold_key:
            self._hold_left -= dt
            if self._hold_left <= 0.0:
                self._release()
            else:
                # Re-assert every frame: the engine's own watchdog drops the
                # tone if this ever stops, which is the behaviour we want.
                self._audio.hold_alert(self._hold_key, volume=self._hold_volume)
        if not self._pending and not self._hold_key:
            self._entry = None

    def stop(self) -> None:
        """End the demo now and release anything it was holding."""
        self._release()
        self._entry = None
        self._pending = []
        self._elapsed = 0.0

    # -- internals -------------------------------------------------------------

    def _fire_due(self) -> None:
        while self._pending and self._pending[0].delay_s <= self._elapsed:
            self._play(self._pending.pop(0))

    def _play(self, cue: Cue) -> None:
        key = self._resolve(cue)
        if not key:
            return
        if cue.hold_s > 0.0:
            self._release()  # one held cue at a time: the alert channel is one channel
            self._audio.hold_alert(key, volume=cue.volume)
            self._audio.set_loop_pan(CH_ALERT, cue.pan)
            self._hold_key = key
            self._hold_volume = cue.volume
            self._hold_left = cue.hold_s
            return
        self._audio.play(key, volume=cue.volume, pan=cue.pan)

    def _resolve(self, cue: Cue) -> str:
        """``cue.key`` where it exists, else its fallback, else nothing.

        The licensed overlay carries cues a clean clone does not have. A demo
        that silently played nothing would teach a player that a real cue is
        silent, which is the worst thing this screen could do.
        """
        has_asset = getattr(self._audio, "has_asset", None)
        if has_asset is None or has_asset(cue.key):
            return cue.key
        if cue.fallback and has_asset(cue.fallback):
            return cue.fallback
        return ""

    def _release(self) -> None:
        if not self._hold_key:
            return
        self._hold_key = ""
        self._hold_left = 0.0
        self._audio.release_alert()
