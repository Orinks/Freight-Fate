"""Production bake: the freeway traffic bed, traffic/highway_bed.

The distant roar of an interstate: the tire noise of a few hundred vehicles,
none of them near enough to be its own sound (the near ones have their own
loops, panned and levelled from the real vehicles). Three steady noise bands
and a handful of soft, irregular far-off passes, decorrelated left and right
so it sits around the cab rather than in the middle of it.

Steady on purpose. The first bed (2026-10-08, genny) swelled on a nine-second
tremolo over noise bursts that also decayed across the loop, and the owner
heard it as an ocean (2026-10-09). Nothing here modulates slower than a pass,
and the level holds within a decibel or two across the loop.

Deterministic: fixed seeds, numpy only. Run from the repository root:

    python sound-test/highway_bed.py build/sound-test/highway_bed.wav

then encode at -22 LUFS integrated (docs/audio-levels.md): measure with
ffmpeg's loudnorm, apply the difference as static gain, and
ffmpeg -c:a libvorbis -q:a 5.
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

RATE = 44100
LENGTH_S = 12.0
CROSSFADE_S = 1.5
# (centre or cutoff Hz, width in octaves or None for a lowpass, gain)
BANDS = [
    (250.0, None, 0.6),  # low rumble: engines and the road surface
    (800.0, 1.4, 0.55),  # tire roar, the body of it
    (2200.0, 1.0, 0.12),  # a little hiss so it reads as tires, not wind
]
# Far-off passes: start s, length s, relative level, pan 0 left .. 1 right.
PASSES = [
    (0.6, 2.4, 0.10, 0.25),
    (2.4, 1.9, 0.07, 0.75),
    (3.9, 3.0, 0.12, 0.35),
    (5.8, 2.1, 0.06, 0.70),
    (7.0, 2.6, 0.09, 0.30),
    (8.9, 1.7, 0.07, 0.65),
    (10.1, 2.8, 0.10, 0.40),
]
PASS_CENTRE_HZ = 900.0


def shaped_noise(n: int, seed: int, centre: float, octaves: float | None) -> np.ndarray:
    """Unit-RMS noise with a smooth band (or lowpass) shape, made in the
    frequency domain so it holds a perfectly steady level."""
    rng = np.random.default_rng(seed)
    spectrum = np.fft.rfft(rng.standard_normal(n))
    freqs = np.fft.rfftfreq(n, 1.0 / RATE)
    if octaves is None:
        shape = 1.0 / np.sqrt(1.0 + (freqs / centre) ** 4)
    else:
        distance = np.log2(np.maximum(freqs, 1.0) / centre) / (octaves / 2.0)
        shape = np.exp(-0.5 * distance**2)
    signal = np.fft.irfft(spectrum * shape, n)
    return signal / np.sqrt((signal**2).mean())


def render() -> np.ndarray:
    n = int((LENGTH_S + CROSSFADE_S) * RATE)
    channels = []
    for side in range(2):
        mix = np.zeros(n)
        for index, (centre, octaves, gain) in enumerate(BANDS):
            mix += gain * shaped_noise(n, 100 * side + index, centre, octaves)
        channels.append(mix)
    passes = shaped_noise(n, 900, PASS_CENTRE_HZ, 1.2)
    t = np.arange(n) / RATE
    for start, length, level, pan in PASSES:
        inside = (t >= start) & (t < start + length)
        phase = (t[inside] - start) / length
        swell = level * 3.0 * np.sin(np.pi * phase) ** 2
        channels[0][inside] += passes[inside] * swell * np.sqrt(1.0 - pan)
        channels[1][inside] += passes[inside] * swell * np.sqrt(pan)
    stereo = np.stack(channels, axis=1)
    # Equal-power crossfade of the tail into the head, so the loop is seamless.
    fade = int(CROSSFADE_S * RATE)
    body = n - fade
    out = stereo[:body].copy()
    ramp = np.linspace(0.0, 1.0, fade)[:, None]
    out[:fade] = stereo[:fade] * np.sqrt(ramp) + stereo[body:] * np.sqrt(1.0 - ramp)
    return out / (np.abs(out).max() * 1.12)


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "build/sound-test/highway_bed.wav")
    out.parent.mkdir(parents=True, exist_ok=True)
    pcm = (render() * 32767.0).astype("<i2")
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
