"""Reusable sustain-loop-with-release playback for BASS (sound_lib) streams.

A real "attack -> sustain -> release" sound -- a horn held down, a siren, an
engine that idles then spins down -- should loop only a short interior region
while it is held, then play its natural release tail once let go. Plain
whole-file looping instead replays the attack every cycle and never lets the
release ring out.

This module is the BASS half of that model. :class:`SustainLoop` drives a raw
``BASS_ChannelSetSync`` position sync that seeks the stream back to the loop
start each time playback reaches the loop end; :meth:`SustainLoop.release`
removes the sync so playback flows past the loop end through to the end of the
file. Because the sync is a *mixtime* sync, the seek happens during mixing and
the loop is seamless.

Nothing here depends on the game's :class:`~freight_fate.audio.AudioEngine`; it
operates on any ``sound_lib`` stream exposing ``.handle``, ``get_frequency``,
and ``seconds_to_bytes``, so it can be reused by any BASS-backed sound. The
pygame fallback backend has no equivalent seek/sync primitive and implements
its own segment-based version.

Loop points may be given in samples or seconds; :func:`to_seconds` is the
shared conversion so every caller agrees on units.
"""

from __future__ import annotations

import logging

__all__ = ["to_seconds", "SustainLoop"]

log = logging.getLogger(__name__)


def to_seconds(pos: float, units: str = "samples", freq: float | None = None) -> float:
    """Convert a loop point to seconds.

    ``units`` is ``"samples"`` (``freq`` in Hz is then required) or
    ``"seconds"`` (``pos`` is returned unchanged).
    """
    if units == "seconds":
        return float(pos)
    if units == "samples":
        if not freq:
            raise ValueError("a stream frequency is required to convert samples to seconds")
        return float(pos) / float(freq)
    raise ValueError(f"unknown loop-point units: {units!r}")


class SustainLoop:
    """A live sustain loop on one BASS stream, seeking start<-end each cycle.

    Construct it on a stream that is created **non-looping** and already
    playing (or about to play): it installs a mixtime position sync at
    ``loop_end`` that seeks back to ``loop_start``. Call :meth:`release` to let
    the release tail play out, or :meth:`stop` when tearing the loop down.
    """

    def __init__(self, stream, loop_start: float, loop_end: float, *, units: str = "samples"):
        # Imported lazily so environments without BASS (pygame-only) can still
        # import this module for ``to_seconds`` without pulling in sound_lib.
        from sound_lib.external.pybass import (
            BASS_POS_BYTE,
            BASS_SYNC_MIXTIME,
            BASS_SYNC_POS,
            SYNCPROC,
            BASS_ChannelRemoveSync,
            BASS_ChannelSetPosition,
            BASS_ChannelSetSync,
        )

        self._stream = stream
        self._handle = stream.handle
        self._remove_sync = BASS_ChannelRemoveSync
        self._pos_byte = BASS_POS_BYTE
        self._released = False
        self._sync = 0

        try:
            freq = stream.get_frequency()
        except Exception:  # pragma: no cover - defensive; freq only used for samples
            freq = None
        start_s = to_seconds(loop_start, units, freq)
        end_s = to_seconds(loop_end, units, freq)
        if end_s <= start_s:
            raise ValueError("loop_end must be after loop_start")
        self._start_byte = int(stream.seconds_to_bytes(start_s))
        end_byte = int(stream.seconds_to_bytes(end_s))

        # BASS keeps a raw pointer to this callback for as long as the sync is
        # registered; pin it to the instance so Python does not free it out
        # from under the mixer thread. The seek is done at mixtime so it lands
        # exactly on the loop boundary with no audible gap.
        def _on_loop_end(handle, channel, data, user):
            BASS_ChannelSetPosition(channel, self._start_byte, self._pos_byte)

        self._proc = SYNCPROC(_on_loop_end)
        self._sync = BASS_ChannelSetSync(
            self._handle, BASS_SYNC_POS | BASS_SYNC_MIXTIME, end_byte, self._proc, None
        )

    @property
    def released(self) -> bool:
        return self._released

    def release(self) -> None:
        """Remove the loop sync so playback continues into the release tail.

        Idempotent: safe to call more than once (e.g. a defensive stop after a
        key release).
        """
        if self._released:
            return
        self._released = True
        try:
            self._remove_sync(self._handle, self._sync)
        except Exception:  # pragma: no cover - stream may already be gone
            log.debug("SustainLoop.release: sync already removed", exc_info=True)

    def stop(self) -> None:
        """Tear the loop down. The caller is responsible for stopping the stream."""
        self.release()
