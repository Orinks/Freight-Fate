"""Ring spectra rebuild: resynthesize each engine band as a long seamless cut.

Track A of the 1.9 final slate (docs/plan-1.9-final-slate.md). After the
seam fixes, the transient patch, and the wobble, the owner still heard the
loop's own loudness contour repeating once per pass ("three shudders",
rate-scaled). The fingerprint is the short cut itself; this tool replaces
each driving band with a 4-6 s resynthesis OF ITS OWN approved cut:

- Harmonic skeleton: partials detected at multiples of the REVOLUTION rate
  (rpm/60 -- firing harmonics and lope sidebands are both included, since
  for an inline-six four-stroke every audible line sits on a revolution
  harmonic). Resynthesized as exact circular sinusoids (an integer number
  of revolutions in the output), original amplitudes and phases, plus a
  slow independent amplitude wander per octave group so no two seconds are
  identical.
- Noise floor: the between-partials PSD, regenerated as FRESH random-phase
  noise across the whole output length (circular by construction).

The result keeps the band's spectral character (formants live in the
partial amplitudes and the noise envelope), is seamless with no splice,
and contains no repeating envelope for the ear to memorize. The idle bed
stays the real recording; jake loops are untouched.

Usage: uv run python tools/engine_ring_extend.py
Writes <band>.wav in the licensed overlay (originals backed up alongside
as <band>.pre-extend.bak.wav) and A/B copies to C:\\temp\\ffsound.
"""

from __future__ import annotations

import os
import shutil

import numpy as np
import soundfile as sf

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LICENSED_ENGINE = os.path.join(
    REPO, "src", "freight_fate", "assets", "sounds-licensed", "engine"
)
AB_DIR = r"C:\temp\ffsound"

# (file, native rpm) -- must match audio.ENGINE_BANDS. Idle excluded: real.
BANDS = (
    ("low.wav", 950.0),
    ("mid.wav", 1150.0),
    ("midhigh.wav", 1425.0),
    ("high.wav", 1900.0),
)

TARGET_S = 5.0  # nominal output length; snapped to whole revolutions
MAX_PARTIAL_HZ = 9000.0
PARTIAL_SEARCH_BINS = 2  # peak search half-width around each predicted line
WANDER_DEPTH = 0.10  # +/- amplitude wander per octave group
WANDER_MAX_HZ = 2.5  # wander bandwidth: slower than the lope, never a tremolo
SEED = 0x52494E47  # "RING"; per-band offset added for decorrelation


def _refine_rev_hz(spec_mag: np.ndarray, sr: int, n: int, rev_hz_nominal: float) -> float:
    """Comb search: the revolution rate that best explains the line spectrum."""
    best = (0.0, rev_hz_nominal)
    for cand in np.linspace(rev_hz_nominal * 0.94, rev_hz_nominal * 1.06, 121):
        ks = np.arange(3, 31, 3)  # firing harmonics carry the energy
        bins = np.round(ks * cand * n / sr).astype(int)
        bins = bins[bins < len(spec_mag)]
        score = float(np.sum(spec_mag[bins]))
        if score > best[0]:
            best = (score, float(cand))
    return best[1]


def _circular_wander(rng: np.random.Generator, length: int, sr: int) -> np.ndarray:
    """Smooth zero-mean wander, circular by construction (random-phase irfft)."""
    spec = np.zeros(length // 2 + 1, dtype=complex)
    max_bin = max(2, int(WANDER_MAX_HZ * length / sr))
    mags = rng.random(max_bin - 1)
    phases = rng.uniform(0.0, 2.0 * np.pi, max_bin - 1)
    spec[1:max_bin] = mags * np.exp(1j * phases)
    w = np.fft.irfft(spec, length)
    peak = np.max(np.abs(w)) + 1e-12
    return w / peak


def extend(path: str, native_rpm: float, band_index: int) -> None:
    x, sr = sf.read(path, dtype="float64")
    if x.ndim > 1:
        x = x.mean(axis=1)
    n = len(x)
    window = np.hanning(n)
    spec = np.fft.rfft(x * window)
    spec_mag = np.abs(spec)

    rev_hz = _refine_rev_hz(spec_mag, sr, n, native_rpm / 60.0)

    # Output grid: an integer number of revolutions near TARGET_S.
    revs = max(8, round(TARGET_S * rev_hz))
    out_len = int(round(revs / rev_hz * sr))
    rev_hz_exact = revs * sr / out_len  # partials at k*rev_hz_exact are circular

    # -- harmonic skeleton ----------------------------------------------------
    rng = np.random.default_rng(SEED + band_index)
    t = np.arange(out_len) / sr
    harmonic = np.zeros(out_len)
    harmonic_energy = 0.0
    noise_spec_mag = spec_mag.copy()
    k_max = int(MAX_PARTIAL_HZ / rev_hz)
    groups: dict[int, np.ndarray] = {}
    for k in range(1, k_max + 1):
        center = int(round(k * rev_hz * n / sr))
        lo = max(1, center - PARTIAL_SEARCH_BINS)
        hi = min(len(spec) - 1, center + PARTIAL_SEARCH_BINS + 1)
        if hi <= lo:
            continue
        peak_bin = lo + int(np.argmax(spec_mag[lo:hi]))
        # Line-vs-floor test: a real partial stands above its neighborhood.
        nb_lo, nb_hi = max(1, peak_bin - 12), min(len(spec) - 1, peak_bin + 13)
        floor = np.median(spec_mag[nb_lo:nb_hi]) + 1e-12
        if spec_mag[peak_bin] < 3.0 * floor:
            continue
        amp = 2.0 * spec_mag[peak_bin] / np.sum(window)
        phase = np.angle(spec[peak_bin])
        octave = int(np.log2(max(1, k)))
        if octave not in groups:
            groups[octave] = _circular_wander(rng, out_len, sr)
        wander = 1.0 + WANDER_DEPTH * groups[octave]
        harmonic += amp * wander * np.cos(2.0 * np.pi * k * rev_hz_exact * t + phase)
        harmonic_energy += 0.5 * amp * amp
        # Remove the line (and its skirt) from the noise estimate.
        noise_spec_mag[max(1, peak_bin - 2) : peak_bin + 3] = floor

    # -- fresh noise floor ----------------------------------------------------
    # Median-smooth the residual magnitude into an envelope, resample it onto
    # the output grid, and give it brand-new random phase everywhere.
    env = noise_spec_mag.copy()
    kernel = 9
    padded = np.pad(env, kernel // 2, mode="edge")
    env = np.array(
        [np.median(padded[i : i + kernel]) for i in range(len(env))]
    )
    src_freqs = np.fft.rfftfreq(n, 1.0 / sr)
    out_freqs = np.fft.rfftfreq(out_len, 1.0 / sr)
    env_out = np.interp(out_freqs, src_freqs, env)
    phases = rng.uniform(0.0, 2.0 * np.pi, len(env_out))
    noise_spec = env_out * np.exp(1j * phases)
    noise_spec[0] = 0.0
    noise = np.fft.irfft(noise_spec, out_len)
    # Energy bookkeeping: match the residual's share of the original signal.
    orig_power = float(np.mean(x**2))
    noise_power_target = max(orig_power - harmonic_energy, 0.02 * orig_power)
    noise *= np.sqrt(noise_power_target / (np.mean(noise**2) + 1e-12))

    out = harmonic + noise
    out *= np.sqrt(orig_power / (np.mean(out**2) + 1e-12))
    peak = np.max(np.abs(out))
    if peak > 0.97:
        out = out / peak * 0.97

    backup = os.path.splitext(path)[0] + ".pre-extend.bak.wav"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    sf.write(path, out.astype(np.float32), sr, subtype="PCM_16")
    name = os.path.basename(path)
    os.makedirs(AB_DIR, exist_ok=True)
    sf.write(
        os.path.join(AB_DIR, name.replace(".wav", "_extended.wav")),
        out.astype(np.float32),
        sr,
    )
    n_partials = sum(1 for _ in groups)  # octave groups actually used
    print(
        f"{name:12s} rev {rev_hz:5.2f} Hz  {n/sr:5.2f}s -> {out_len/sr:5.2f}s "
        f"({revs} revs)  harm/total {harmonic_energy/orig_power:4.2f}  "
        f"octave groups {n_partials}"
    )


def main() -> None:
    for i, (name, native) in enumerate(BANDS):
        path = os.path.join(LICENSED_ENGINE, name)
        if os.path.exists(path):
            extend(path, native, i)
        else:
            print(f"{name}: missing, skipped")


if __name__ == "__main__":
    main()
