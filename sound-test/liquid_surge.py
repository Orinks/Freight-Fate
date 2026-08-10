"""Production bake: the liquid-surge cue layer for tank trailers.

Three assets, all synthesized, all deterministic:

    vehicle/liquid_wash.wav        looping bed: liquid on the move. The game
                                   holds it only while the slug is running and
                                   scales its gain by how fast it is running.
    vehicle/liquid_hit.wav         one-shot: the wave arriving at the head.
    vehicle/liquid_hit_lateral.wav one-shot: the wave arriving at the side --
                                   the rollover case, so a different voice.

Two constraints shaped the spectrum. The jake brake runs on its own channel at
full gain during exactly the deceleration that produces surge, and neither
audio backend has per-loop EQ to carve a hole in it. And the engine and road
beds own everything below about a kilohertz. So this layer does not sonify the
*mass* of the liquid, which would sit right underneath both -- it sonifies the
*surface*: the wash and the slap, banded into 1.5-4 kHz where the only other
occupant is the FM fringe hiss, and that only with the radio on.

The wash is filtered noise with a slow amplitude undulation, so it reads as
moving water rather than as a tone -- there is a standing rule against new
steering tones and this is deliberately not one. The hit is a short broadband
slap through the tank shell's modal ring: brief, unmistakable, and loud enough
to survive a mono speaker at a low effects volume, because it is the event the
whole layer exists to deliver. The lateral hit is the same slap through a
tighter, higher ring so the two are never confused; side-to-side surge is the
one that rolls trucks over, and it also gets speech.

Mono on purpose -- surge is never panned, because the left/right axis already
carries lane guidance and the drift side. 48 kHz, WAV, because LOOPING BEDS
ARE NEVER VORBIS: Vorbis has no overlap partner across the loop wrap and puts
a click back into the seam.

Usage: uv run python sound-test/liquid_surge.py  (writes straight to assets)
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pulse_synth import SR, bank_ir, convolve  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "src" / "freight_fate" / "assets" / "sounds"

WASH_SECONDS = 3.0
WASH_TAIL_S = 0.4

# Fixed seed: the bake is byte-identical on every machine and every rerun.
RNG = np.random.default_rng(1907)

# The band the surface lives in. Below this the engine and the road bed have
# all the body; above it there is nothing to hear over road noise anyway.
WASH_LOW_HZ = 1500.0
WASH_HIGH_HZ = 4000.0

# The tank shell's modal ring, struck by the arriving wave, as
# (frequency, decay seconds, gain). Fore-and-aft is the long dimension: a
# lower, looser ring against the front head, and it rings on a little.
SHELL_FORE = ((520.0, 0.10, 0.90), (1180.0, 0.060, 0.60), (2350.0, 0.035, 0.35))
# Side to side is the bore: shorter, tighter, higher, and dying faster. It
# must never be mistaken for the fore-aft slap -- it means something else.
SHELL_LATERAL = ((900.0, 0.055, 0.90), (2050.0, 0.032, 0.70), (3600.0, 0.020, 0.40))


def band_noise(n: int, low_hz: float, high_hz: float) -> np.ndarray:
    """White noise kept to a frequency band, done in the spectrum so the
    edges are exact and the result is stationary (and therefore loopable)."""
    spec = np.fft.rfft(RNG.standard_normal(n))
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    keep = (freqs >= low_hz) & (freqs <= high_hz)
    # Soften the band edges so it reads as water rather than as a filter.
    shape = np.zeros_like(freqs)
    shape[keep] = 1.0
    roll = np.exp(-(((freqs - (low_hz + high_hz) / 2.0) / ((high_hz - low_hz) / 1.6)) ** 2))
    spec *= shape * roll
    return np.fft.irfft(spec, n)


def wrap_fold(sig: np.ndarray, loop_n: int) -> np.ndarray:
    """Fold everything past the loop length back onto the start."""
    out = sig[:loop_n].copy()
    tail = sig[loop_n:]
    out[: len(tail)] += tail[:loop_n]
    return out


def bake_wash() -> np.ndarray:
    """Moving liquid: banded noise under a slow, irregular undulation.

    The undulation is built from frequencies that complete a whole number of
    cycles in the loop, so the modulation crosses the seam without a step.
    """
    loop_n = int(WASH_SECONDS * SR)
    n = loop_n + int(WASH_TAIL_S * SR)
    t = np.arange(n) / SR
    sig = band_noise(n, WASH_LOW_HZ, WASH_HIGH_HZ)
    # Three integer-cycle partials: sloshing is not periodic, but it is not
    # steady either, and this gives it a surface without giving it a pitch.
    env = np.ones(n)
    for cycles, depth, phase in ((2, 0.30, 0.0), (3, 0.20, 1.7), (5, 0.12, 3.1)):
        env += depth * np.sin(2 * np.pi * cycles * t / WASH_SECONDS + phase)
    sig *= env / np.max(env)
    looped = wrap_fold(np.nan_to_num(sig), loop_n)
    top = float(np.max(np.abs(looped))) or 1.0
    return looped / top * 0.72


def bake_hit(modes: tuple[tuple[float, float, float], ...], gain: float) -> np.ndarray:
    """The wave arriving: a short broadband slap through the shell's ring."""
    n = int(0.55 * SR)
    t = np.arange(n) / SR
    # The impact itself: a fast noise burst with the surface's band on top of
    # a broader thump, so it carries on small speakers and in mono.
    burst = RNG.standard_normal(n) * np.exp(-t / 0.012)
    surface = band_noise(n, WASH_LOW_HZ, WASH_HIGH_HZ) * np.exp(-t / 0.045)
    sig = convolve(burst + 0.8 * surface, bank_ir(modes))[:n]
    sig *= np.exp(-t / 0.13)
    top = float(np.max(np.abs(sig))) or 1.0
    return np.nan_to_num(sig) / top * gain


def write_mono_wav(rel: str, sig: np.ndarray) -> Path:
    path = OUT / f"{rel}.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.clip(sig, -1.0, 1.0)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes((data * 32767.0).astype("<i2").tobytes())
    return path


def main() -> None:
    written = [
        write_mono_wav("vehicle/liquid_wash", bake_wash()),
        write_mono_wav("vehicle/liquid_hit", bake_hit(SHELL_FORE, 0.95)),
        write_mono_wav("vehicle/liquid_hit_lateral", bake_hit(SHELL_LATERAL, 0.92)),
    ]
    for path in written:
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
