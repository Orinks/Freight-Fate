"""Production bake: the in-lane guidance bed (`vehicle/lane_bed.wav`).

The curve-nav guidance loop: a soft, airy carrier the driving state pans
toward the side the truck is drifting to and fades with closeness to the
lane line. It has to sit UNDER the engine and tires (it is guidance, not
an alarm), stay identifiable against both (they are broadband and pitched
low; this is a narrow airy cluster higher up), and loop without a seam.

Seamless by construction: the noise band comes from an inverse FFT of a
shaped magnitude spectrum with random phases -- the buffer is periodic by
definition -- and every amplitude modulation completes an integer number
of cycles over the loop. No crossfade, no seam to click. LOOPING BEDS ARE
WAV, NEVER VORBIS (the codec smears loop points into clicks).

Mono on purpose: the game pans it per frame; a mono source keeps the
image a single object the pan can place.

Usage: uv run python sound-test/lane_bed.py  (writes straight to assets)
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000
SECONDS = 4.0
N = int(SR * SECONDS)
OUT = Path(__file__).resolve().parents[1] / "src" / "freight_fate" / "assets" / "sounds"
RNG = np.random.default_rng(11)  # fixed seed: reruns are byte-identical


def periodic_band_noise(center_hz: float, width_hz: float, gain: float = 1.0) -> np.ndarray:
    """Loop-periodic band-limited noise via random-phase inverse FFT."""
    freqs = np.fft.rfftfreq(N, 1.0 / SR)
    mag = np.exp(-0.5 * ((freqs - center_hz) / (width_hz / 2.354)) ** 2)  # gaussian band
    phase = RNG.uniform(0.0, 2.0 * np.pi, len(freqs))
    phase[0] = 0.0  # DC and (even-N) nyquist bins must stay real
    if N % 2 == 0:
        phase[-1] = 0.0
    spectrum = mag * np.exp(1j * phase)
    sig = np.fft.irfft(spectrum, n=N)
    top = float(np.max(np.abs(sig))) or 1.0
    return sig / top * gain


def loop_lfo(cycles: int, depth: float, phase: float = 0.0) -> np.ndarray:
    """A slow sine that completes exactly ``cycles`` over the loop."""
    t = np.arange(N) / N
    return 1.0 - depth * 0.5 * (1.0 + np.sin(2.0 * np.pi * (cycles * t + phase)))


def build() -> np.ndarray:
    # The airy carrier: a narrow band around 540 Hz -- above the engine's
    # weight, below the pacenote voice -- with a second fainter band a
    # musical fifth up so it reads as one designed object, not a whistle.
    bed = periodic_band_noise(540.0, 160.0, gain=1.0)
    bed += periodic_band_noise(810.0, 120.0, gain=0.35)
    # Slow breathing keeps it alive without drawing attention: two beat
    # rates, both integer cycles across the loop, never in step.
    bed *= loop_lfo(3, 0.22)
    bed *= loop_lfo(7, 0.12, phase=0.31)
    top = float(np.max(np.abs(bed))) or 1.0
    return bed / top * 0.85


def write_mono_wav(rel: str, sig: np.ndarray) -> Path:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.clip(sig, -1.0, 1.0)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes((data * 32767.0).astype("<i2").tobytes())
    return path


def main() -> None:
    path = write_mono_wav("vehicle/lane_bed.wav", build())
    seam = abs(float(build()[0]) - float(build()[-1]))
    print(f"wrote {path} ({SECONDS:.0f}s mono {SR} Hz, seam delta {seam:.6f})")


if __name__ == "__main__":
    main()
