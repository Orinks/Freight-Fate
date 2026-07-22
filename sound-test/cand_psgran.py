"""Candidate: PITCH-SYNCHRONOUS GRANULAR (KEY = psgran).

Cut grains one firing period long from a steady INTERIOR idle window, centred on
detected firing transients (pitch marks) and Hann-windowed at ~2x overlap.
Resynthesise by scattering grains overlap-add at the TARGET firing rate, drawing
grain source positions at random from across the window, with a small Poisson-ish
jitter on trigger time to break the metallic comb while staying pitched.

The grain length is FIXED (idle-derived) at every rpm. Only the trigger RATE
moves. Because each grain is untouched real waveform, the ~800 Hz cab/block body
resonance never shifts -- rev = firings closer together, not a smaller engine.
Overlap grows with rpm (2x at idle -> ~5x at 1800), which fills the bed as a real
engine blurs its firings. Seamless via wrap-add into a fixed-length loop buffer:
the buffer is genuinely periodic, so its join is a real sample adjacency.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

import cand_common as C

KEY = "psgran"
RNG = np.random.default_rng(7)

IDLE_RPM = 647.0
FIRING_HZ = IDLE_RPM / 20.0                 # 32.35 Hz firing rate at idle
T_IDLE = C.SR / FIRING_HZ                    # ~1484 samples per firing


# --- build the grain pool from a steady interior idle window -----------------

def _envelope(x: np.ndarray, ms: float = 2.0) -> np.ndarray:
    w = max(4, int(ms * 1e-3 * C.SR))
    return np.convolve(np.abs(x), np.ones(w) / w, mode="same")


def _refine_period(env: np.ndarray, guess: float) -> float:
    """Autocorrelate the envelope near the idle firing period to lock T."""
    lo, hi = int(guess * 0.85), int(guess * 1.18)
    best, best_v = guess, -1.0
    e = env - env.mean()
    for lag in range(lo, hi):
        v = float(np.dot(e[:-lag], e[lag:]))
        if v > best_v:
            best_v, best = v, lag
    return float(best)


def _pitch_marks(env: np.ndarray, period: float) -> list[int]:
    """Place one mark per firing, snapped to the local envelope peak."""
    n = len(env)
    # anchor on the strongest peak inside the first firing period
    anchor = int(np.argmax(env[: int(period)]))
    marks = []
    k = 0
    win = int(period * 0.30)
    while True:
        c = int(round(anchor + k * period))
        if c - period / 2 < 0:
            k += 1
            continue
        if c + period / 2 >= n:
            break
        a, b = max(0, c - win), min(n, c + win)
        c = a + int(np.argmax(env[a:b]))
        marks.append(c)
        k += 1
    return marks


def build_grains(overlap: float = 2.0):
    """Return (grains[list of (L,) arrays], L) from a steady 647 rpm window."""
    src = C.load_wav(C.LICENSED["int_idle_low"])
    win = C.find_steady_window(src, IDLE_RPM, 2.5)
    if win is None:
        win = src[: int(2.5 * C.SR)]
    win = win - win.mean()
    env = _envelope(win)
    period = _refine_period(env, T_IDLE)
    marks = _pitch_marks(env, period)
    L = int(round(overlap * period))
    if L % 2:
        L += 1
    half = L // 2
    hann = np.hanning(L)
    grains = []
    for m in marks:
        if m - half < 0 or m + half >= len(win):
            continue
        g = win[m - half:m + half] * hann
        grains.append(g.astype(float))
    return grains, L


# --- granular resynthesis ----------------------------------------------------

def _draw(grains: list[np.ndarray]) -> np.ndarray:
    return grains[int(RNG.integers(len(grains)))]


def synth_loop(grains, L, firing_hz, n_periods, jitter=0.03):
    """Wrap-add a fixed number of grains at a steady rate -> a periodic loop."""
    T = C.SR / firing_hz
    loop_len = int(round(n_periods * T))
    buf = np.zeros(loop_len)
    half = L // 2
    for k in range(n_periods):
        c = k * T + RNG.normal(0.0, jitter * T)
        g = _draw(grains)
        idx = (np.round(c).astype(int) + np.arange(-half, half)) % loop_len
        buf[idx] += g
    return buf


def synth_rev(grains, L, f0, f1, dur_s, hold_lo=0.5, hold_hi=0.5, jitter=0.03):
    """Continuous pull: hold idle, ramp firing rate to f1, hold high."""
    n = int((dur_s + hold_lo + hold_hi) * C.SR)
    out = np.zeros(n + L)
    half = L // 2
    # instantaneous firing frequency over time (samples)
    t = np.arange(n) / C.SR
    f = np.empty(n)
    ramp_end = hold_lo + dur_s
    f[t < hold_lo] = f0
    ramp = (t >= hold_lo) & (t < ramp_end)
    frac = (t[ramp] - hold_lo) / dur_s
    f[ramp] = f0 + (f1 - f0) * frac
    f[t >= ramp_end] = f1
    # integrate phase; drop a grain each time phase crosses an integer
    phase = np.cumsum(f) / C.SR
    total = int(np.floor(phase[-1]))
    for k in range(total):
        pos = int(np.searchsorted(phase, k))
        c = pos + int(RNG.normal(0.0, jitter * (C.SR / f[min(pos, n - 1)])))
        a = c - half
        g = _draw(grains)
        lo = max(0, a)
        gi0 = lo - a
        hi = min(len(out), a + L)
        out[lo:hi] += g[gi0:gi0 + (hi - lo)]
    return out[:n]


def main():
    grains, L = build_grains(overlap=3.0)
    print(f"grains={len(grains)} L={L} ({L / C.SR * 1e3:.1f} ms)")

    # --- idle: ~3 s periodic loop, tiled to 6 s so any seam is audible -------
    idle_periods = int(round(3.0 * FIRING_HZ))
    idle_loop = synth_loop(grains, L, FIRING_HZ, idle_periods, jitter=0.03)
    idle_loop = C.make_seamless_loop(idle_loop)
    idle_out = C.tile(idle_loop, 6.0)

    # --- rev: idle (~650) -> 1800 rpm continuous pull ------------------------
    f_idle = IDLE_RPM / 20.0
    f_hi = 1800.0 / 20.0
    rev = synth_rev(grains, L, f_idle, f_hi, dur_s=6.0, hold_lo=0.5, hold_hi=0.5)

    # --- cruise: steady 1500 rpm loop, ~4 s ----------------------------------
    f_cruise = 1500.0 / 20.0
    cruise_periods = int(round(2.0 * f_cruise))       # ~2 s buffer
    cruise_loop = synth_loop(grains, L, f_cruise, cruise_periods, jitter=0.03)
    cruise_loop = C.make_seamless_loop(cruise_loop)
    cruise_out = C.tile(cruise_loop, 4.0)

    p1 = C.write_wav(f"candidate_{KEY}_idle.wav", idle_out)
    p2 = C.write_wav(f"candidate_{KEY}_rev.wav", rev)
    p3 = C.write_wav(f"candidate_{KEY}_cruise1500.wav", cruise_out)

    for tag, arr in (("idle", idle_out), ("rev", rev), ("cruise", cruise_out)):
        rms = float(np.sqrt(np.mean(np.asarray(arr) ** 2)))
        print(f"{tag:7s} rms={rms:.3f} len={len(arr) / C.SR:.2f}s")

    print("SCORE", C.score(idle_loop, rev))
    print(p1)
    print(p2)
    print(p3)


if __name__ == "__main__":
    main()
