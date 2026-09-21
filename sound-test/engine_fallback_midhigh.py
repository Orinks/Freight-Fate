"""Committed fallback for engine/midhigh: a parametric 1425 rpm loop.

The licensed ring gained a fifth band (engine/midhigh, 1425 rpm) to split
the too-wide mid->high gap; the committed tree needs a synthesized fallback
under the same key so a clean clone still resolves every referenced asset.
Same clean-provenance construction as air_fallback.py: a purely parametric
spectrum -- the 6-cylinder firing series at 1425 rpm (f0 = rpm/20 = 71.25 Hz)
over a shaped noise bed -- rendered periodic in the frequency domain (every
component on an exact bin of the loop length, zero seam), seeded and
deterministic. Loudness is matched to the committed engine/mid.ogg so the
fallback ring stays level across bands.

Writes src/freight_fate/assets/sounds/engine/midhigh.ogg (COMMITTED).

Usage: uv run --with scipy python sound-test/engine_fallback_midhigh.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

SR = 44100
RPM = 1425.0
F0 = RPM / 20.0  # 6-cyl four-stroke firing fundamental
LOOP_S = 4.0  # 71.25 Hz * 4 s = 285 cycles, exactly periodic
N = int(SR * LOOP_S)
ASSETS = Path(__file__).resolve().parents[1] / "src" / "freight_fate" / "assets" / "sounds"
OUT = ASSETS / "engine" / "midhigh.ogg"
REF = ASSETS / "engine" / "mid.ogg"  # loudness reference


def main() -> None:
    import soundfile as sf

    rng = np.random.default_rng(1425)
    freqs = np.fft.rfftfreq(N, 1.0 / SR)
    spectrum = np.zeros(freqs.size, dtype=complex)

    # The firing series: harmonics to ~2.2 kHz with a gentle rolloff and a
    # little per-harmonic level scatter so it reads as machinery, not organ.
    for n_h in range(1, int(2200 / F0) + 1):
        bin_i = int(round(n_h * F0 * LOOP_S))
        if bin_i >= freqs.size:
            break
        level = (1.0 / n_h**1.25) * rng.uniform(0.7, 1.0)
        spectrum[bin_i] = level * np.exp(1j * rng.uniform(0, 2 * np.pi))

    # Broadband combustion/exhaust bed: band-limited noise, -6 dB/oct above
    # 500 Hz, at about a fifth of the harmonic energy.
    noise_mag = np.zeros_like(freqs)
    band = (freqs > 60.0) & (freqs < 6000.0)
    noise_mag[band] = 1.0
    above = freqs > 500.0
    noise_mag[above] *= 500.0 / freqs[above]
    noise = noise_mag * np.exp(1j * rng.uniform(0, 2 * np.pi, freqs.size))
    harmonic_energy = np.sqrt(np.sum(np.abs(spectrum) ** 2))
    noise_energy = np.sqrt(np.sum(np.abs(noise) ** 2))
    if noise_energy > 0:
        noise *= 0.2 * harmonic_energy / noise_energy
    spectrum += noise
    spectrum[0] = 0.0

    x = np.fft.irfft(spectrum, n=N)

    ref, _sr = sf.read(str(REF), always_2d=False)
    if ref.ndim > 1:
        ref = ref.mean(axis=1)
    target_rms = float(np.sqrt(np.mean(ref * ref)))
    x *= target_rms / np.sqrt(np.mean(x * x))
    peak = np.max(np.abs(x))
    if peak > 0.98:
        x *= 0.98 / peak
    sf.write(str(OUT), x.astype("float32"), SR, format="OGG", subtype="VORBIS")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB, rms matched to mid.ogg)")


def _run_with_deep_stack() -> None:
    import threading

    threading.stack_size(64 * 1024 * 1024)
    t = threading.Thread(target=main)
    t.start()
    t.join()


if __name__ == "__main__":
    _run_with_deep_stack()
