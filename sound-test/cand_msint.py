"""Candidate: MULTISAMPLE REAL INTERIOR.

Pure real cab audio -- no synthesis. Cut steady INTERIOR windows at a ladder of
rpm anchors from the three driver's-seat takes, turn each into a seamless loop,
and build the rev by variable-rate reading the two nearest anchors and
equal-power crossfading them. Each anchor is only ever AUDIBLE when the target
rpm is within ~12% of it (anchors are spaced <=25% apart, so the crossfade
midpoint sits <=sqrt(1.25)-1 ~= 12% of resample), which keeps the fixed
cab/block formants from marching up with rpm -- no micro-engine.

Run from repo root:
  uv run --with numpy --with soundfile --with scipy python sound-test/cand_msint.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

import cand_common as C

KEY = "msint"
RNG = np.random.default_rng(7)

# Anchor ladder. Targets are search hints chosen where the INTERIOR takes really
# dwell (measured, not from filenames); each cut window's TRUE firing rate is
# re-measured and used as the anchor rpm, so the ladder is honest and monotonic.
# Spacing stays <=25% (geometric midpoint within ~12% resample of both anchors --
# the formant-preservation budget) everywhere except one 1.30x step at the top
# (1470 -> 1915), where no clean interior dwell exists between; a ~14% resample
# there is far less audible than at idle and is noted as the sole caveat.
# (target, take, cut duration in seconds)
ANCHOR_PLAN = [
    (650.0, "int_idle_low", 3.0),
    (820.0, "int_idle_low", 2.5),
    (1000.0, "int_mid", 1.4),     # clean short dwell ~940
    (1150.0, "int_mid", 2.0),     # clean dwell ~1170
    (1300.0, "int_mid", 2.0),     # clean dwell ~1290
    (1470.0, "int_mid", 2.5),     # rock-steady ~1470
    (1880.0, "int_high", 3.0),    # clean ~1915, the top of the pull
]


def _true_rpm(win: np.ndarray) -> tuple[float, float]:
    """Robust firing rate of a cut window: 1 s analysis frames kill the octave
    flips a short frame gives, median over the window, plus its spread."""
    _, r = C.rpm_track(win, hop_s=0.25, win_s=1.0)
    r = r[r > 0]
    if len(r) == 0:
        return 0.0, 0.0
    return float(np.median(r)), float(r.std())


def cut_anchor(take_key: str, target: float, dur_s: float = 2.5):
    """Steadiest interior window near target -> (seamless loop, TRUE rpm).

    Widen the rpm tolerance until a dwell is found, then RE-MEASURE the cut's
    real firing rate and use that as the anchor rpm -- targets are only search
    hints, so a take that dwells at 940 instead of 1000 still lands honestly.
    If nothing dwells near target, fall back to the take's steadiest window.
    """
    x = C.load_wav(C.LICENSED[take_key])
    win, used_tol = None, None
    for tol in (60.0, 100.0, 160.0, 260.0, 400.0):
        win = C.find_steady_window(x, target, dur_s=dur_s, tol=tol)
        if win is not None:
            used_tol = tol
            break
    fell_back = False
    if win is None:
        t, r = C.rpm_track(x)
        hop = t[1] - t[0]
        need = int(dur_s / hop)
        best, bdev = 0, 1e9
        for i in range(0, max(1, len(r) - need)):
            seg = r[i:i + need]
            if np.any(seg <= 0):
                continue
            d = float(seg.std())
            if d < bdev:
                bdev, best = d, i
        win = x[int(t[best] * C.SR):int(t[best] * C.SR) + int(dur_s * C.SR)]
        fell_back = True
    actual, spread = _true_rpm(win)
    actual = actual or target
    loop = C.make_seamless_loop(win)
    note = "FALLBACK" if fell_back else f"tol={used_tol}"
    print(f"  anchor hint {target:>5.0f} <- {take_key:<13} TRUE {actual:6.0f} rpm "
          f"(spread {spread:4.0f}) [{note}]  loop {len(loop)/C.SR:.2f}s")
    return loop, actual


def vari_read(loop: np.ndarray, rate: np.ndarray) -> np.ndarray:
    """Read a seamless loop at a per-sample rate (target/anchor) with wrap.

    Continuous fractional read pointer -> phase stays coherent as the rate glides
    across the pull. Vectorised via a cumulative read position.
    """
    L = len(loop)
    pos = np.cumsum(rate)
    pos = pos - rate[0]  # start at 0
    idx = pos % L
    i0 = np.floor(idx).astype(np.int64) % L
    i1 = (i0 + 1) % L
    frac = idx - np.floor(idx)
    return loop[i0] * (1.0 - frac) + loop[i1] * frac


def build_rev(anchors, rpm0=650.0, rpm1=1800.0, dur_s=7.0, band=0.5) -> np.ndarray:
    """Continuous pull: variable-rate read every anchor along the rpm track,
    then equal-power crossfade the two that bracket the moment's rpm."""
    n = int(dur_s * C.SR)
    t = np.linspace(0.0, 1.0, n)
    # gentle ease so the pull breathes rather than ramping like a slider
    ease = t * t * (3.0 - 2.0 * t)
    r = rpm0 + (rpm1 - rpm0) * ease

    a = np.array([ar for _, ar in anchors])          # measured rpm, ascending
    loops = [lp for lp, _ in anchors]
    m = len(a)

    # bracket index + blend factor within each segment. NARROW the crossover:
    # a full-segment equal-power fade plays two DIFFERENT real takes at ~equal
    # level through the whole middle, and their independent firing phases comb
    # -- that is the "muddy in the middle of the rev" Norm hears. Instead hold
    # one anchor alone across most of its segment and blend the two only in a
    # short band around the midpoint, so decorrelated takes rarely overlap.
    seg = np.clip(np.searchsorted(a, r) - 1, 0, m - 2)
    theta = np.clip((r - a[seg]) / (a[seg + 1] - a[seg]), 0.0, 1.0)
    # band=0.5 recovers a full equal-power blend (formant-stable, but the two
    # takes overlap through the whole middle -> mud). A smaller band holds one
    # anchor alone across most of the segment (less mud, but wider resample =>
    # more formant drift). The right value is an ear call.
    tt = np.clip((theta - (0.5 - band)) / (2.0 * band), 0.0, 1.0)
    w_lo = np.cos(tt * np.pi / 2.0)
    w_hi = np.sin(tt * np.pi / 2.0)

    out = np.zeros(n)
    for k in range(m):
        wk = np.zeros(n)
        mlo = seg == k
        wk[mlo] += w_lo[mlo]           # anchor k is the lower bracket
        mhi = seg == (k - 1)
        wk[mhi] += w_hi[mhi]           # anchor k is the upper bracket
        if not wk.any():
            continue
        sig = vari_read(loops[k], r / a[k])
        out += sig * wk

    # Gentle level compensation. An anti-phase crossover sums BELOW idle level
    # -- Norm's "volume drops slightly" through the first ~1.75 s where three
    # low anchors crowd together. Flatten only the SLOW envelope (~0.3 s), never
    # the firing ripple, so loudness holds constant without pumping the texture.
    w = int(0.30 * C.SR)
    env = np.sqrt(np.convolve(out ** 2, np.ones(w) / w, "same"))
    tgt = float(np.median(env[env > 0])) or 1.0
    out = out * np.clip(tgt / np.maximum(env, tgt * 0.35), 0.6, 1.8)
    return out


def main() -> None:
    print(f"[{KEY}] cutting interior anchors...")
    anchors = [cut_anchor(tk, tgt, dur_s=d) for tgt, tk, d in ANCHOR_PLAN]
    anchors.sort(key=lambda a: a[1])  # ascending by TRUE rpm -> monotonic ladder
    print("  ladder rpm:", [round(ar) for _, ar in anchors])

    # --- idle: a dedicated fuller/longer cut at the idle dwell (~650) ---
    idle_loop, idle_rpm = cut_anchor("int_idle_low", 650.0, dur_s=3.5)
    idle_out = C.tile(idle_loop, 6.0)

    # --- rev: continuous 650 -> 1800 pull ---
    # band 0.30: hold each anchor alone across most of its segment (less mud
    # than a full equal-power blend) without the formant drift of a very tight
    # crossover; level-comp inside build_rev flattens the residual dip.
    rev = build_rev(anchors, rpm0=650.0, rpm1=1800.0, dur_s=7.0, band=0.30)

    # --- cruise 1500: the rock-steady ~1470 int_mid dwell, pulled to 1500 ---
    xm = C.load_wav(C.LICENSED["int_mid"])
    c15 = C.find_steady_window(xm, 1470.0, dur_s=2.5, tol=60.0)
    if c15 is None:
        c15 = C.find_steady_window(xm, 1470.0, dur_s=2.5, tol=160.0)
    cr_rpm, _ = _true_rpm(c15)
    rate = 1500.0 / (cr_rpm or 1500.0)
    pulled = vari_read(c15, np.full(int(len(c15) / rate), rate))
    cruise_loop = C.make_seamless_loop(pulled)
    print(f"  cruise1500 <- int_mid {cr_rpm:.0f} rpm pulled to 1500 (rate {rate:.3f})")
    cruise_out = C.tile(cruise_loop, 4.0)

    p_idle = C.write_wav(f"candidate_{KEY}_idle.wav", idle_out)
    p_rev = C.write_wav(f"candidate_{KEY}_rev.wav", rev)
    p_cruise = C.write_wav(f"candidate_{KEY}_cruise1500.wav", cruise_out)

    for tag, p in (("idle", p_idle), ("rev", p_rev), ("cruise", p_cruise)):
        x = C.load_wav(p)
        print(f"  {tag:<6} {p}  rms {np.sqrt(np.mean(x**2)):.3f}  {len(x)/C.SR:.2f}s")

    metrics = C.score(idle_loop, rev)
    print(f"[{KEY}] score:", metrics)


if __name__ == "__main__":
    main()
