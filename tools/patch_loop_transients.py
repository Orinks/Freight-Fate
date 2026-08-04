"""Patch click transients baked inside looping engine beds.

The formant-model bands all inherited one click-ish transient from the
anchor recording (owner heard it 2026-07-27: a click at low speeds,
"shick shick shick" at high -- once per loop pass, rate-scaled). The
seam tools cannot touch it because it is not at the seam.

For each event (high-passed envelope above DETECT_RATIO x the file
median), the region is replaced with clean material from elsewhere in
the same file. The donor offset snaps to a whole number of the file's
dominant cycle (autocorrelation pitch) so the engine rhythm does not
hiccup at the patch, and both edges crossfade linearly (correlated,
near-periodic material). Jake loops are exempt: their pops ARE the
instrument.

Usage: uv run python tools/patch_loop_transients.py  (repairs in place,
prints a before/after event report).
"""

from __future__ import annotations

import os

import numpy as np
import soundfile as sf
from scipy.signal import butter, filtfilt

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LICENSED_ENGINE = os.path.join(
    REPO, "src", "freight_fate", "assets", "sounds-licensed", "engine"
)
TARGETS = ("idle.wav", "low.wav", "mid.wav", "midhigh.wav", "high.wav")

DETECT_RATIO = 2.0
FRAME_S = 0.005
PAD_S = 0.02  # patch this much on each side of a detected event
EDGE_S = 0.01  # crossfade length at each patch edge


def _hp_envelope(x: np.ndarray, sr: int) -> np.ndarray:
    b, a = butter(4, 4000 / (sr / 2), btype="high")
    hp = filtfilt(b, a, x)
    frame = int(FRAME_S * sr)
    m = len(hp) // frame
    return np.sqrt(np.mean(hp[: m * frame].reshape(m, frame) ** 2, axis=1))


def _events(env: np.ndarray) -> list[tuple[int, int]]:
    med = np.median(env) + 1e-12
    hot = env / med > DETECT_RATIO
    events: list[list[int]] = []
    for i, flag in enumerate(hot):
        if not flag:
            continue
        if events and i - events[-1][1] <= 6:
            events[-1][1] = i
        else:
            events.append([i, i])
    return [(s, e) for s, e in events]


def _dominant_cycle(x: np.ndarray, sr: int) -> int:
    """Lag of the strongest autocorrelation peak in the 30-130 ms range."""
    n = min(len(x), sr)  # one second is plenty
    seg = x[:n] - np.mean(x[:n])
    ac = np.correlate(seg, seg, "full")[n - 1 :]
    lo, hi = int(0.03 * sr), min(int(0.13 * sr), n - 1)
    return lo + int(np.argmax(ac[lo:hi]))


def patch(path: str) -> None:
    x, sr = sf.read(path, dtype="float64")
    if x.ndim > 1:
        x = x.mean(axis=1)
    env = _hp_envelope(x, sr)
    events = _events(env)
    if not events:
        print(f"{os.path.basename(path):14s} clean, untouched")
        return
    frame = int(FRAME_S * sr)
    pad = int(PAD_S * sr)
    edge = int(EDGE_S * sr)
    cycle = _dominant_cycle(x, sr)
    med = np.median(env) + 1e-12
    out = x.copy()
    for s_f, e_f in events:
        start = max(0, s_f * frame - pad)
        end = min(len(x), (e_f + 1) * frame + pad)
        length = end - start
        # Donor: the phase-aligned offset (whole cycles away) whose own
        # envelope is quietest and which stays inside the file.
        best = None
        for k in range(1, len(x) // cycle):
            for sign in (-1, 1):
                d_start = start + sign * k * cycle
                if d_start < 0 or d_start + length > len(x):
                    continue
                d_lo = d_start // frame
                d_hi = min(len(env), (d_start + length) // frame + 1)
                worst = float(np.max(env[d_lo:d_hi]) / med) if d_hi > d_lo else 99.0
                if best is None or worst < best[0]:
                    best = (worst, d_start)
        if best is None or best[0] > DETECT_RATIO:
            print(f"{os.path.basename(path):14s} NO clean donor for {start/sr:.2f}s -- skipped")
            continue
        donor = x[best[1] : best[1] + length].copy()
        ramp = np.linspace(0.0, 1.0, edge)
        donor[:edge] = out[start : start + edge] * (1.0 - ramp) + donor[:edge] * ramp
        donor[-edge:] = donor[-edge:] * (1.0 - ramp) + out[end - edge : end] * ramp
        out[start:end] = donor
    after = _hp_envelope(out, sr)
    peak = np.max(np.abs(out)) + 1e-12
    if peak > 0.99:
        out = out / peak * 0.99
    sf.write(path, out.astype(np.float32), sr, subtype="PCM_16")
    print(
        f"{os.path.basename(path):14s} {len(events)} event(s) patched  "
        f"worst {np.max(env)/med:.1f}x -> {np.max(after)/np.median(after):.1f}x"
    )


def main() -> None:
    for name in TARGETS:
        path = os.path.join(LICENSED_ENGINE, name)
        if os.path.exists(path):
            patch(path)


if __name__ == "__main__":
    main()
