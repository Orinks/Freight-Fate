"""Synthesized earcons for the categories the S4 driving speech ladder
retires to sound (R14, ``docs/ontology.md``'s "Terse speech grammar").

``COACHING`` and ``STATUS`` have no existing cue that means what an earcon
standing in for either needs to mean -- every candidate already carries a
meaning of its own (the overspeed chime says "you are speeding", not "here
was a tip"), and reusing one would teach a player two different things under
one sound. These two tones are synthesized rather than shipped, the same way
the enforcement signature is (``states/driving_siren.py``): pure arithmetic,
so the same build always produces the same bytes and nothing needs an LFS
entry.

Deliberately plainer than the enforcement signature, which has to survive
being heard against radio static and repeats twice on purpose. These two only
need to be tellable apart from each other and from everything else already
playing: coaching is two rising notes (a tip offered), status is one short
low note (something changed, look at it later if you want to).
"""

from __future__ import annotations

import array
import io
import math
import wave

from .audio import register_generated_sound

COACHING_NOTE_KEY = "ladder/coaching_note"
STATUS_NOTE_KEY = "ladder/status_note"

_RATE = 44100
_EDGE_S = 0.008  # raised-cosine edges, just enough to kill the click


def _envelope(index: int, total: int, edge: int) -> float:
    """Raised-cosine edges on a rectangular tone, matching the signature's."""
    if edge <= 0:
        return 1.0
    if index < edge:
        return 0.5 - 0.5 * math.cos(math.pi * index / edge)
    if index >= total - edge:
        return 0.5 - 0.5 * math.cos(math.pi * (total - 1 - index) / edge)
    return 1.0


def _tone_samples(freq_hz: float, dur_s: float, peak: float) -> array.array:
    n = int(dur_s * _RATE)
    edge = int(_EDGE_S * _RATE)
    step = 2.0 * math.pi * freq_hz / _RATE
    amp = int(peak * 32767)
    samples = array.array("h")
    for i in range(n):
        value = int(amp * _envelope(i, n, edge) * math.sin(step * i))
        samples.append(value)
        samples.append(value)
    return samples


def _wav_bytes(samples: array.array) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(_RATE)
        out.writeframes(samples.tobytes())
    return buffer.getvalue()


def coaching_note_wav() -> bytes:
    """A soft two-note rising chime: a tip offered, not an alarm."""
    samples = _tone_samples(523.25, 0.09, 0.4) + _tone_samples(659.25, 0.09, 0.4)
    return _wav_bytes(samples)


def status_note_wav() -> bytes:
    """A single short, low tock: a state changed, nothing to act on now."""
    return _wav_bytes(_tone_samples(392.0, 0.08, 0.35))


_registered = False


def register_ladder_earcons() -> None:
    """Publish both synthesized earcons under their ordinary sound keys.

    Idempotent, mirroring ``driving_siren.register_enforcement_sounds``:
    safe to call from the Learn screen every time it opens, and cheap enough
    that nothing needs to remember whether it already ran.
    """
    global _registered
    if _registered:
        return
    register_generated_sound(COACHING_NOTE_KEY, coaching_note_wav(), "wav")
    register_generated_sound(STATUS_NOTE_KEY, status_note_wav(), "wav")
    _registered = True
