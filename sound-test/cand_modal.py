"""Candidate MODAL -- many-resonator physical model (pure-synth control route).

Method: peak-pick the real interior idle spectrum into ~30 FIXED modes
(frequency, Q, gain). Those modes ARE the cab/block formants -- a parallel bank
of constant-gain biquad resonators that never move. Excite the bank with a
six-cylinder diesel firing model (order 1-5-3-6-2-4, one firing per cylinder per
two revolutions, staggered evenly, with per-cylinder amplitude trims, a
half-order lope, small combustion-to-combustion jitter, and a knock noise burst
that grows with load). Only the firing RATE tracks rpm; the resonators -- and a
single fixed corrective EQ anchored to the real idle's 1/3-octave contour --
stay put. So the ~800 Hz body does not rise with rpm: no micro-engine.

Idle   647 rpm, seamless loop tiled to 6 s.
Rev    one continuous 7 s pull, 647 -> ~1800 rpm, formants locked.
Cruise steady 1500 rpm, re-looped seamless, 4 s.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks, lfilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cand_common as C  # noqa: E402

KEY = "modal"
RNG = np.random.default_rng(7)

IDLE_RPM = 647.0
FIRING_ORDER = [1, 5, 3, 6, 2, 4]     # classic inline-six firing order
LOPE_DEPTH = 0.16                     # half-order amplitude wobble (~5 Hz @ idle)
C2C_JITTER = 0.06                     # combustion-to-combustion amplitude spread
CYL_TRIM_SD = 0.05                    # fixed per-cylinder amplitude imbalance
KNOCK_BASE = 0.45                     # combustion grit already present at idle
KNOCK_GAIN = 0.55                     # extra knock that comes in with load
BED_LEVEL = 1.0                       # continuous mechanical/airflow bed (fills
                                      # the gaps between firings -> real fullness)
N_MODES = 30


# --- derive the fixed mode bank from the real idle ---------------------------


def derive_modes() -> list[tuple[float, float, float]]:
    """Peak-pick the real interior idle into fixed (freq, Q, gain) resonators.

    Smooth the idle magnitude spectrum in log-frequency (roughly 1/12 octave) so
    the firing comb is tamed but the broad cab/block humps survive, then take the
    most prominent maxima between 40 Hz and 4.5 kHz. Gains carry the real body
    shape; Q rises gently with frequency so low modes stay broad and warm.
    """
    real = C.load_wav(C.REF_IDLE)
    n = len(real)
    S = np.abs(np.fft.rfft(real * np.hanning(n)))
    f = np.fft.rfftfreq(n, 1.0 / C.SR)

    # log-frequency moving-average smoothing of the magnitude envelope
    logf = np.log2(np.maximum(f, 1.0))
    env = np.empty_like(S)
    half = 1.0 / 12.0
    for i in range(len(S)):
        env[i] = S[np.abs(logf - logf[i]) <= half].mean()

    band = (f >= 40.0) & (f <= 4500.0)
    idx0 = np.argmax(band)
    e = env[band]
    ff = f[band]
    # min ~1/6-octave spacing between picked modes
    df = f[1] - f[0]
    peaks, props = find_peaks(e, distance=max(1, int((ff.mean() / 6) / df)),
                              prominence=e.max() * 0.02)
    if len(peaks) < N_MODES:
        peaks, props = find_peaks(e, prominence=e.max() * 0.005)
    order = np.argsort(props["prominences"])[::-1][:N_MODES]
    peaks = np.sort(peaks[order])

    modes: list[tuple[float, float, float]] = []
    for p in peaks:
        fp = float(ff[p])
        g = float(e[p])
        q = float(np.clip(fp / 45.0, 5.0, 11.0))
        modes.append((fp, q, g))
    # normalise gains so the loudest mode is 1.0
    gmax = max(m[2] for m in modes) or 1.0
    return [(fp, q, g / gmax) for (fp, q, g) in modes]


# --- excitation: the six-cylinder firing model -------------------------------


def _pulse_kernel() -> np.ndarray:
    """One combustion pressure spike: near-instant rise, ~2 ms fall."""
    L = int(0.004 * C.SR)
    t = np.arange(L)
    return np.exp(-t / (0.0008 * C.SR))


def build_excitation(rpm_of_t: np.ndarray) -> np.ndarray:
    """Impulse-plus-knock excitation whose firing RATE follows rpm_of_t.

    Firing rate is rpm/20 Hz (six firings per two-revolution cycle). Phase is
    integrated sample by sample so the rev is a continuous glide, not a step.
    Each firing drops a deterministic combustion spike (drives the tonal modes)
    plus a load-scaled noise burst (the diesel grit), trimmed per cylinder,
    loped at half order, and jittered combustion to combustion.
    """
    n = len(rpm_of_t)
    exc = np.zeros(n)
    kern = _pulse_kernel()
    lk = len(kern)

    cyl_trim = 1.0 + RNG.normal(0.0, CYL_TRIM_SD, 6)

    rate = rpm_of_t / 20.0 / C.SR          # firings per sample
    phase = np.cumsum(rate)
    ev = np.where(np.diff(np.floor(phase)) >= 1)[0] + 1

    for idx in ev:
        k = int(phase[idx])                # global firing count
        cyl = FIRING_ORDER[k % 6] - 1
        lope = 1.0 + LOPE_DEPTH * np.sin(2.0 * np.pi * (k / 6.0))
        amp = cyl_trim[cyl] * lope * (1.0 + RNG.normal(0.0, C2C_JITTER))
        load = float(np.clip((rpm_of_t[idx] - 600.0) / 1200.0, 0.0, 1.0))
        knock = KNOCK_BASE + KNOCK_GAIN * load
        L = min(lk, n - idx)
        seg = kern[:L]
        exc[idx:idx + L] += amp * seg
        exc[idx:idx + L] += amp * knock * RNG.standard_normal(L) * seg
    # Continuous mechanical/airflow bed: a steady low-level broadband drive so
    # the resonators never fall completely silent between firings. Its level is
    # fixed (not load-scaled), so it fills the idle without dragging the rev
    # spectrum upward -- the bed keeps the same body at every rpm.
    exc += BED_LEVEL * RNG.standard_normal(n)
    return exc


def _biquad_bandpass(f0: float, q: float):
    w0 = 2.0 * np.pi * f0 / C.SR
    alpha = np.sin(w0) / (2.0 * q)
    b = np.array([alpha, 0.0, -alpha])
    a = np.array([1.0 + alpha, -2.0 * np.cos(w0), 1.0 - alpha])
    return b / a[0], a / a[0]


def run_bank(exc: np.ndarray, modes) -> np.ndarray:
    """Parallel fixed resonator bank -- the sum is the engine body's response."""
    out = np.zeros_like(exc)
    for (f0, q, g) in modes:
        b, a = _biquad_bandpass(f0, q)
        out += g * lfilter(b, a, exc)
    return out


# --- one fixed corrective EQ anchored to the real idle contour ---------------


def third_oct_gain(x: np.ndarray) -> np.ndarray:
    """Per-1/3-octave amplitude gain that pulls x's contour onto the real idle.

    Energy-matched over 200-1000 Hz (the band the two already agree on), clipped
    to +/-~9 dB so it corrects the broad shape without inventing a resonance.
    Derived ONCE from the idle and reused verbatim for rev and cruise, so it is a
    fixed cab filter -- it cannot drift the formants with rpm.
    """
    real = C.load_wav(C.REF_IDLE)
    pr = C.band_power(real)
    px = C.band_power(x)
    m = (C.THIRD_OCT >= 200.0) & (C.THIRD_OCT <= 1000.0)
    scale = pr[m].sum() / (px[m].sum() or 1.0)
    ratio = np.sqrt((pr + 1e-12) / ((px * scale) + 1e-12))
    return np.clip(ratio, 0.36, 2.8)


def apply_logf_gain(x: np.ndarray, gain: np.ndarray) -> np.ndarray:
    """Zero-phase filter: interpolate the 1/3-octave gain across x's own bins."""
    n = len(x)
    f = np.fft.rfftfreq(n, 1.0 / C.SR)
    lf = np.log2(np.maximum(f, 1.0))
    g = np.interp(lf, np.log2(C.THIRD_OCT), gain,
                  left=gain[0], right=gain[-1])
    return np.fft.irfft(np.fft.rfft(x) * g, n)


# --- build the three deliverables --------------------------------------------


def synth(rpm_of_t: np.ndarray, modes) -> np.ndarray:
    return run_bank(build_excitation(rpm_of_t), modes)


def main() -> None:
    modes = derive_modes()

    # Idle: 3 s of steady 647 rpm; derive the fixed EQ here, reuse everywhere.
    idle_raw = synth(np.full(int(3.0 * C.SR), IDLE_RPM), modes)
    gain = third_oct_gain(idle_raw)
    idle_eq = apply_logf_gain(idle_raw, gain)
    body = idle_eq[int(0.3 * C.SR):int(2.7 * C.SR)]
    body = body - body.mean()
    loop = C.make_seamless_loop(body, xfade_s=0.14)
    idle_out = C.tile(loop, 6.0)

    # Rev: continuous 7 s pull 647 -> 1800, smootherstep ramp, same modes + EQ.
    n = int(7.0 * C.SR)
    u = np.linspace(0.0, 1.0, n)
    s = u * u * u * (u * (u * 6 - 15) + 10)
    rpm = IDLE_RPM + (1800.0 - IDLE_RPM) * s
    rev = apply_logf_gain(synth(rpm, modes), gain)

    # Cruise: steady 1500 rpm, EQ, re-loop seamless, tile to 4 s.
    cruise_raw = apply_logf_gain(synth(np.full(int(1.6 * C.SR), 1500.0), modes),
                                 gain)
    cbody = cruise_raw[int(0.25 * C.SR):int(1.45 * C.SR)]
    cbody = cbody - cbody.mean()
    cruise = C.tile(C.make_seamless_loop(cbody, xfade_s=0.12), 4.0)

    paths = [
        C.write_wav(f"candidate_{KEY}_idle.wav", idle_out),
        C.write_wav(f"candidate_{KEY}_rev.wav", rev),
        C.write_wav(f"candidate_{KEY}_cruise1500.wav", cruise),
    ]

    def rms(x):
        return float(np.sqrt(np.mean(np.asarray(x) ** 2)))

    print("modes (f,Q,g):")
    for mfq in modes:
        print("   %6.1f Hz  Q%4.1f  g%.3f" % mfq)
    print("wrote:")
    for p in paths:
        print("  ", p)
    print("rms  idle=%.3f rev=%.3f cruise=%.3f"
          % (rms(idle_out), rms(rev), rms(cruise)))
    print("score:", C.score(loop, rev))


if __name__ == "__main__":
    main()
