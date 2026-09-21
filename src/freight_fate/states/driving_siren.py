"""The held siren, and the synthesized signature that leads it.

Two accessibility failures live here, and this module is both fixes.

**The siren was a single shot.** ``events/police_siren`` played once, mono,
dead centre, at a fixed level, and never repeated -- and ``_update_pull_over``
contained no audio at all. A player who missed that one wail had no ongoing
evidence a cruiser was behind them at any point in the entire stop. The siren
is now a held loop on its own reserved channel, panned and levelled to track
the cruiser as a real object. **The rise in level over the first few seconds
is the "he is coming up behind you" information**, and it is the single most
important cue in the whole enforcement system: a fixed-level siren says a
police car exists, a rising one says it is closing on you.

**The radio made sirens ambiguous.** The station catalog ships around
thirty-eight always-available police and fire scanner streams, and nothing
ducked the radio for anything. A siren in the headphones could equally be the
programme. So enforcement leads with a signature the game synthesizes here:
two dry, hard-gated sine tones, no room, no noise floor, no codec artifacts.
That is not a claim that nothing could ever imitate it -- a station can in
principle broadcast anything. It is a shape that survives being heard against
programme material, and it is always played into a ducked radio (see
``_radio_cue_duck``), so it lands in a hole rather than on top of a mix. For a
pull-over the radio is CUT outright rather than ducked: the sudden silence is
itself an unambiguous cue that something has taken over the cab.

The realistic siren stays layered underneath the signature. The signature says
"this is the game talking to you about enforcement"; the siren says what it is.
"""

from __future__ import annotations

import array
import io
import math
import wave

from ..audio import CH_SIREN, register_generated_sound

# -- the synthesized signature ----------------------------------------------

SIGNATURE_KEY = "enforcement/signature"
SIGNATURE_RATE = 44100
# A rising minor sixth. Deliberately musical and deliberately dry: two pure
# tones with hard gates and no tail are the opposite of everything else in the
# cab, which is all engine, air, tyre and weather noise.
SIGNATURE_LOW_HZ = 660.0
SIGNATURE_HIGH_HZ = 1056.0
SIGNATURE_TONE_S = 0.13
SIGNATURE_GAP_S = 0.04
SIGNATURE_REPEATS = 2
SIGNATURE_EDGE_S = 0.008  # raised-cosine edges, just enough to kill the click
SIGNATURE_PEAK = 0.55

# The marked-unit pass is a two-element signature: the marker LEADS the
# vehicle whoosh. A garnished whoosh -- one clip differing from the civilian
# pass only by a subtle chirp buried inside it -- disappears under engine,
# road, weather and radio. A marker at or above the whoosh's level, arriving
# first, survives where the garnish does not.
PASS_MARKER_LEAD_S = 0.2

# -- the held siren ----------------------------------------------------------

# Loop the interior of the four-second siren asset, letting the attack play
# once and the tail ring out on release.
SIREN_LOOP_START_S = 0.6
SIREN_LOOP_END_S = 3.4
# The level the siren starts at when a cruiser first lights up, and how long
# it takes to reach full. This ramp is the cue.
SIREN_START_LEVEL = 0.25
SIREN_RISE_S = 4.0
SIREN_FULL_LEVEL = 1.0
SIREN_RELEASE_FADE_MS = 400
# A held sound in a blind player's headphones must never outlive the thing it
# is about. Same dead man's switch as the held alert tone: the owner
# re-asserts it every frame, and it stops on its own the moment that stops.
SIREN_HOLD_TIMEOUT_S = 0.4


def _envelope(index: int, total: int, edge: int) -> float:
    """Raised-cosine edges on a rectangular tone."""
    if edge <= 0:
        return 1.0
    if index < edge:
        return 0.5 - 0.5 * math.cos(math.pi * index / edge)
    if index >= total - edge:
        return 0.5 - 0.5 * math.cos(math.pi * (total - 1 - index) / edge)
    return 1.0


def enforcement_signature_wav() -> bytes:
    """Deterministic 16-bit stereo WAV bytes for the enforcement signature.

    Pure arithmetic, no random source, no floating-point ordering hazard: the
    same build always produces the same bytes, so the sound is as reproducible
    as any shipped asset and needs no place in the sound pack.
    """
    samples = array.array("h")
    tone_n = int(SIGNATURE_TONE_S * SIGNATURE_RATE)
    gap_n = int(SIGNATURE_GAP_S * SIGNATURE_RATE)
    edge_n = int(SIGNATURE_EDGE_S * SIGNATURE_RATE)
    peak = int(SIGNATURE_PEAK * 32767)
    for _ in range(SIGNATURE_REPEATS):
        for freq in (SIGNATURE_LOW_HZ, SIGNATURE_HIGH_HZ):
            step = 2.0 * math.pi * freq / SIGNATURE_RATE
            for i in range(tone_n):
                value = int(peak * _envelope(i, tone_n, edge_n) * math.sin(step * i))
                samples.append(value)
                samples.append(value)
            for _ in range(gap_n):
                samples.append(0)
                samples.append(0)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(SIGNATURE_RATE)
        out.writeframes(samples.tobytes())
    return buffer.getvalue()


_registered = False


def register_enforcement_sounds() -> None:
    """Publish the synthesized signature under an ordinary sound key.

    Idempotent, and cheap enough to call from a driving state's constructor.
    """
    global _registered
    if _registered:
        return
    register_generated_sound(SIGNATURE_KEY, enforcement_signature_wav(), "wav")
    _registered = True


class SirenLoop:
    """A siren that tracks a cruiser, on its own channel and its own bus.

    Assert it every frame with :meth:`hold` for as long as the cruiser is
    there, and call :meth:`service` every frame unconditionally. If the holds
    stop -- a menu opening over the drive, the stop resolving, an owner that
    lost the frame -- it releases itself within a fraction of a second.
    """

    def __init__(self) -> None:
        self.active = False
        self.elapsed_s = 0.0
        self._hold_s = 0.0
        self._pan = 0.0
        self._level = SIREN_START_LEVEL

    @property
    def level(self) -> float:
        """Current siren level: the rise, which is the information."""
        if not self.active:
            return 0.0
        ramp = min(1.0, self.elapsed_s / max(1e-6, SIREN_RISE_S))
        return SIREN_START_LEVEL + (SIREN_FULL_LEVEL - SIREN_START_LEVEL) * ramp

    def hold(self, audio, *, pan: float = 0.0) -> None:
        """Sound the siren for the next moment only. Call every frame."""
        self._hold_s = SIREN_HOLD_TIMEOUT_S
        self._pan = max(-1.0, min(1.0, pan))
        if not self.active:
            self.active = True
            self.elapsed_s = 0.0
            audio.start_sustain_loop(
                CH_SIREN,
                "events/police_siren",
                SIREN_LOOP_START_S,
                SIREN_LOOP_END_S,
                units="seconds",
                volume=self.level,
            )
        audio.set_loop_volume(CH_SIREN, self.level)
        audio.set_loop_pan(CH_SIREN, self._pan)

    def service(self, audio, dt: float) -> None:
        """Advance the ramp and release the loop if the holds stopped."""
        if not self.active:
            return
        self.elapsed_s += dt
        self._hold_s -= dt
        if self._hold_s <= 0.0:
            self.stop(audio)

    def stop(self, audio) -> None:
        if not self.active:
            return
        self.active = False
        self.elapsed_s = 0.0
        self._hold_s = 0.0
        audio.release_sustain_loop(CH_SIREN, fade_ms=SIREN_RELEASE_FADE_MS)


__all__ = [
    "PASS_MARKER_LEAD_S",
    "SIGNATURE_HIGH_HZ",
    "SIGNATURE_KEY",
    "SIGNATURE_LOW_HZ",
    "SIGNATURE_RATE",
    "SIREN_FULL_LEVEL",
    "SIREN_HOLD_TIMEOUT_S",
    "SIREN_RISE_S",
    "SIREN_START_LEVEL",
    "SirenLoop",
    "enforcement_signature_wav",
    "register_enforcement_sounds",
]
