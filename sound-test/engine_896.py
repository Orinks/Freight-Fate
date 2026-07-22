"""The winning engine voice, re-anchored from ONE coherent truck (Splice 896).

msint won the ear test; this is its cleanup. Instead of anchors stitched from
several takes, every piece is cut from a single real interior recording of a
Mack driving around (SemiTruckMac_S08IN.896) -- so idle, cruise and rev all
share the same engine's character, knock and cab. RPM labels come from the
low-pass tracker (knock removed) and Norm's ear, both verified.

The architecture is simpler than a full multisample because the rev is now a
REAL recorded acceleration, not a crossfade of static anchors:

  idle        steady loop, ~680 rpm
  cruise-mid  steady loop, ~1150 rpm    (a warm hold before the drive)
  cruise-high steady loop, ~1800 rpm    (real highway cruise)
  rev-launch  real acceleration pulling away from a stop (gear-tracking)
  rev-load    real sustained high-rpm pull (lugging at load)

Every clip is loudness-matched so the audition is a fair A/B; the game sets true
levels at runtime. Outputs to C:\\temp\\ffsound\\896.

Usage: uv run --with numpy --with soundfile --with scipy python sound-test/engine_896.py
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cand_common as C  # noqa: E402

OUT = Path(r"C:\temp\ffsound\896")
SRC = C.LICENSED["ext_range_a"]  # SemiTruckMac_S08IN.896, interior (per Norm's ear)

# (name, start_s, end_s, kind, rpm). Steady windows -> loops closed on whole
# FOUR-STROKE CYCLES (so the half-order lope closes, not just the firing cycle);
# pulls -> one-shots. Windows off the low-pass map; pull timestamps are Norm's ear.
PIECES = [
    ("idle_680",        2.8,   6.3, "loop", 680.0),  # shifted +1s: first second still settling (Norm's ear)
    ("cruise_mid_1150", 8.0,  13.6, "loop", 1150.0),
    ("cruise_high_1800", 109.0, 120.5, "loop", 1800.0),
    ("rev_launch",      18.5,  27.5, "pull", 0.0),
    ("rev_load",        84.0, 100.0, "pull", 0.0),
]


def cycle_loop(x: np.ndarray, rpm: float) -> tuple[np.ndarray, float]:
    """Loop on a whole number of four-stroke cycles so the lope closes too.

    A four-stroke cycle is two revolutions -- the period over which the firing
    order AND the half-order lope both repeat. Closing the loop on the fast
    firing cycle (29 ms at idle) still leaves the slow ~5 Hz lope mismatched at
    the seam, which swells and settles over the first half second of every loop
    (Norm's "weird phase boundary thing"). Find the true cycle period by
    autocorrelation near 120/rpm seconds, cut an integer number of them, and
    short-crossfade the join -- where the two blended stretches are one whole
    cycle apart and therefore already matched.
    """
    n = len(x)
    P0 = 120.0 / rpm * C.SR
    lo, hi = int(P0 * 0.82), int(P0 * 1.22)
    xc = x - x.mean()
    m = 1 << int(np.ceil(np.log2(2 * n)))
    F = np.fft.rfft(xc, m)
    ac = np.fft.irfft(F * np.conj(F), m)[:n]
    period = lo + int(np.argmax(ac[lo:hi]))
    xf = int(0.012 * C.SR)
    k = max(1, (n - xf) // period)
    L = k * period
    loop = x[:L].copy()
    w = np.linspace(0.0, 1.0, xf)
    loop[:xf] = x[:xf] * w + x[L:L + xf] * (1.0 - w)
    return loop, period / C.SR


def write(name: str, x: np.ndarray, target_rms: float = 0.12, peak_ceiling: float = 0.97) -> None:
    x = np.nan_to_num(np.asarray(x, float))
    x = x * (target_rms / (float(np.sqrt(np.mean(x ** 2))) or 1.0))
    p = float(np.max(np.abs(x))) or 1.0
    if p > peak_ceiling:
        x = x * (peak_ceiling / p)
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / name), "wb") as fh:
        fh.setnchannels(1); fh.setsampwidth(2); fh.setframerate(C.SR)
        fh.writeframes((x * 32767).astype("<i2").tobytes())


def main() -> None:
    x = C.load_wav(SRC)
    SR = C.SR
    print(f"896: {len(x)/SR:.1f}s interior\n")
    for name, a, b, kind, rpm in PIECES:
        seg = x[int(a * SR):int(b * SR)].copy()
        if kind == "loop":
            loop, cyc = cycle_loop(seg, rpm)
            out = C.tile(loop, 6.0)
            write(f"{name}.wav", out)
            print(f"  {name:18s} loop {len(loop)/SR:4.2f}s  cycle {cyc*1000:3.0f}ms x{round(len(loop)/SR/cyc)}"
                  f"  seam {C.seam_check(loop):4.2f}  fullness {C.fullness(loop):.2f}")
        else:
            fi = int(0.04 * SR)
            seg[:fi] *= np.linspace(0, 1, fi); seg[-fi:] *= np.linspace(1, 0, fi)
            write(f"{name}.wav", seg)
            print(f"  {name:18s} pull {len(seg)/SR:4.1f}s  ({a}-{b}s of 896)")
    print(f"\nwrote the 896 voice set to {OUT}")


if __name__ == "__main__":
    main()
