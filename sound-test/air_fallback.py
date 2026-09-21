"""Committed fallback for vehicle/air_pressurize: a parametric air-fill loop.

The licensed overlay carries the real-spectrum hiss (pressurize.py resynthesizes
from a purchased sample's spectrum, so it must stay out of git). A clean clone
still references the key, so the committed tree needs a fallback with clean
provenance: this one is built from a purely parametric magnitude target --
band-limited noise with a gentle high tilt, nothing sampled, nothing measured.

Same zero-seam construction as the overlay hiss: write the target magnitude
over the rfft bins of exactly one loop length, give every bin a seeded random
phase, and inverse-FFT. The result is one period of a periodic signal --
constant level, no crossfade, no seam. A faint compressor-pump wobble is added
as amplitude modulation with an integer number of cycles per loop, so the
seam stays exact. Deterministic (seeded), so it regenerates byte-identical.

Writes src/freight_fate/assets/sounds/vehicle/air_pressurize.ogg (COMMITTED).

Usage: uv run --with scipy python sound-test/air_fallback.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

SR = 44100
LOOP_S = 6.0
N = int(SR * LOOP_S)
OUT = (
    Path(__file__).resolve().parents[1]
    / "src" / "freight_fate" / "assets" / "sounds" / "vehicle" / "air_pressurize.ogg"
)

# Pump wobble: ~2.2 Hz compressor rhythm, snapped to whole cycles per loop.
PUMP_CYCLES = round(2.2 * LOOP_S)
PUMP_DEPTH = 0.14
TARGET_RMS = 10 ** (-20 / 20)  # -20 dBFS, in line with the other beds


def magnitude_target(freqs: np.ndarray) -> np.ndarray:
    """Cab-muffled air-fill spectrum, drawn parametrically.

    Flat through the hiss body, shelved off below 250 Hz (the cab wall keeps
    the lows out of a thin air line) and tilted -6 dB/oct above 1.2 kHz so it
    reads as air, not static. Hard band edges at 120 Hz and 9 kHz.
    """
    mag = np.ones_like(freqs)
    lo = np.clip(freqs / 250.0, 0.0, 1.0)
    mag *= lo * lo  # 12 dB/oct low shelf
    tilt = np.ones_like(freqs)
    above = freqs > 1200.0
    tilt[above] = 1200.0 / freqs[above]  # -6 dB/oct
    mag *= tilt
    mag[(freqs < 120.0) | (freqs > 9000.0)] = 0.0
    return mag


def main() -> None:
    import soundfile as sf

    rng = np.random.default_rng(896)  # the donor cab's number, for luck
    freqs = np.fft.rfftfreq(N, 1.0 / SR)
    spectrum = magnitude_target(freqs) * np.exp(1j * rng.uniform(0, 2 * np.pi, freqs.size))
    spectrum[0] = 0.0
    x = np.fft.irfft(spectrum, n=N)

    phase = 2 * np.pi * PUMP_CYCLES * np.arange(N) / N
    x *= 1.0 + PUMP_DEPTH * np.sin(phase)

    x *= TARGET_RMS / np.sqrt(np.mean(x * x))
    peak = np.max(np.abs(x))
    if peak > 0.98:
        x *= 0.98 / peak
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(OUT), x.astype("float32"), SR, format="OGG", subtype="VORBIS")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB, {LOOP_S:.0f}s seamless loop)")


def _run_with_deep_stack() -> None:
    """soundfile 0.14 + libsndfile 1.2.2 Vorbis writes overflow the default
    Windows main-thread stack on multi-second buffers (see encode_pack.py)."""
    import threading

    threading.stack_size(64 * 1024 * 1024)
    t = threading.Thread(target=main)
    t.start()
    t.join()


if __name__ == "__main__":
    _run_with_deep_stack()
