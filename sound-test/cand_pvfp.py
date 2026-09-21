"""Candidate PVFP -- formant-preserving phase vocoder.

Method: take a seamless INTERIOR idle loop (real driver's-seat stock, so its
fullness and body already match the reference). To reach a target rpm, move the
firing RATE by resampling in time (a time-varying resample gives a continuous
glide), then re-impose the idle's FIXED spectral envelope frame-by-frame in the
STFT domain (cepstral-smoothed original_env / shifted_env). The harmonics move
with rpm; the ~800 Hz cab/block body does NOT -- no micro-engine drift.

Idle   = the real interior loop, tiled (no shift; formants and fullness native).
Rev    = one continuous 7 s pull, idle rpm -> ~1800, formant-locked throughout.
Cruise = the idle loop shifted to a steady 1500 rpm, re-looped seamless.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.signal import stft, istft

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cand_common as C  # noqa: E402

KEY = "pvfp"
RNG = np.random.default_rng(7)

IDLE_RPM = 650.0
NPERSEG = 4096
NOVERLAP = 3072          # 75% overlap -- COLA-safe with a Hann window
LIFTER_Q = 90            # cepstral quefrency cutoff: smooth over the harmonics,
                         # keep the broad body/cab formants (features > ~500 Hz)


# --- spectral-envelope machinery --------------------------------------------


def _cep_env(mag: np.ndarray, q: int = LIFTER_Q) -> np.ndarray:
    """Cepstral-smoothed magnitude envelope of one spectrum (harmonics removed).

    Low-quefrency liftering keeps the broad spectral shape (the fixed cab/block
    formants) and discards the fine harmonic comb, so the estimate is the same
    envelope whether the engine idles or revs.
    """
    logm = np.log(np.maximum(mag, 1e-9))
    cep = np.fft.irfft(logm, n=2 * (len(mag) - 1))
    lift = np.zeros_like(cep)
    lift[:q] = 1.0
    lift[-q + 1:] = 1.0          # keep the mirror half symmetric
    lift[0] = 1.0
    env = np.exp(np.fft.rfft(cep * lift).real)
    return env


def _target_envelope(loop: np.ndarray) -> np.ndarray:
    """The FIXED formant template: cepstral envelope of the idle's mean spectrum."""
    f, t, Z = stft(loop, fs=C.SR, window="hann", nperseg=NPERSEG,
                   noverlap=NOVERLAP, boundary=None)
    mean_mag = np.abs(Z).mean(axis=1)
    return _cep_env(mean_mag)


def _reimpose_formants(x: np.ndarray, e_target: np.ndarray) -> np.ndarray:
    """Multiply every STFT frame by e_target / its own smoothed envelope.

    x has already had its firing rate moved (by resampling), which dragged the
    formants along; this pins them back to e_target so the body stays put.
    """
    f, t, Z = stft(x, fs=C.SR, window="hann", nperseg=NPERSEG,
                   noverlap=NOVERLAP, boundary="zeros", padded=True)
    Zc = np.empty_like(Z)
    for k in range(Z.shape[1]):
        mag = np.abs(Z[:, k])
        env = _cep_env(mag)
        gain = e_target / np.maximum(env, env.max() * 1e-4)
        Zc[:, k] = Z[:, k] * gain
    _, y = istft(Zc, fs=C.SR, window="hann", nperseg=NPERSEG,
                 noverlap=NOVERLAP, boundary=True)
    return y[:len(x)]


def _resample_varying(src: np.ndarray, ratio: np.ndarray) -> np.ndarray:
    """Read src at a time-varying rate: pos advances by ratio[n] each out-sample.

    ratio == 1 plays at idle pitch; ratio > 1 reads faster -> firing rate (and
    every harmonic) rises by that factor, a smooth continuous glide.
    """
    pos = np.cumsum(ratio)
    pos = pos - pos[0]                       # start at the loop's head
    idx = np.arange(len(src))
    return np.interp(pos % (len(src) - 1), idx, src)


# --- build the three deliverables -------------------------------------------


def build_idle_loop() -> np.ndarray:
    """Real interior idle, cut to a steady window near 650 rpm, made seamless."""
    src = C.load_wav(C.LICENSED["int_idle_low"])
    win = C.find_steady_window(src, IDLE_RPM, dur_s=2.6)
    if win is None:                          # fall back to the take's calm head
        win = src[int(2 * C.SR):int(4.6 * C.SR)]
    # trim tiny DC/level drift, then crossfade-loop it
    win = win - win.mean()
    return C.make_seamless_loop(win, xfade_s=0.14)


def build_rev(loop: np.ndarray, e_target: np.ndarray,
              start_rpm: float, end_rpm: float, dur_s: float) -> np.ndarray:
    n = int(dur_s * C.SR)
    # smootherstep rpm ramp so the pull eases in and settles, not a linear line
    u = np.linspace(0.0, 1.0, n)
    s = u * u * u * (u * (u * 6 - 15) + 10)
    rpm = start_rpm + (end_rpm - start_rpm) * s
    ratio = rpm / IDLE_RPM
    src = C.tile(loop, dur_s * float(ratio.max()) + 2.0)
    shifted = _resample_varying(src, ratio)
    y = _reimpose_formants(shifted, e_target)
    return y[:n]


def build_cruise(loop: np.ndarray, e_target: np.ndarray,
                 rpm: float, dur_s: float) -> np.ndarray:
    ratio = rpm / IDLE_RPM
    src = C.tile(loop, dur_s * ratio + 2.0)
    r = np.full(int((dur_s + 0.4) * C.SR), ratio)
    shifted = _resample_varying(src, r)
    y = _reimpose_formants(shifted, e_target)
    # re-loop the steady result so cruise tiles cleanly too
    y = C.make_seamless_loop(y[int(0.2 * C.SR):int((dur_s + 0.2) * C.SR)],
                             xfade_s=0.12)
    return C.tile(y, dur_s)


def main() -> None:
    loop = build_idle_loop()
    e_target = _target_envelope(loop)

    idle_out = C.tile(loop, 6.0)
    rev = build_rev(loop, e_target, IDLE_RPM, 1800.0, 7.0)
    cruise = C.tile(build_cruise(loop, e_target, 1500.0, 4.0), 4.0)

    paths = [
        C.write_wav(f"candidate_{KEY}_idle.wav", idle_out),
        C.write_wav(f"candidate_{KEY}_rev.wav", rev),
        C.write_wav(f"candidate_{KEY}_cruise1500.wav", cruise),
    ]

    def rms(x):
        return float(np.sqrt(np.mean(np.asarray(x) ** 2)))

    print("wrote:")
    for p in paths:
        print("  ", p)
    print("rms  idle=%.3f rev=%.3f cruise=%.3f"
          % (rms(idle_out), rms(rev), rms(cruise)))
    print("score:", C.score(loop, rev))


if __name__ == "__main__":
    main()
