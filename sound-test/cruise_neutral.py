"""Cruise loop from the neutral-rev hold (Splice 60624), + a road-bed mix.

896 never cruises steady (it's driven hard), so the steady RPM tone for holding
a speed comes from the take where the driver put it in neutral and revved to a
sustained hold (~1200 rpm). A neutral rev is unloaded, not a true loaded cruise
-- but in game the engine plays UNDER a road bed, and the road sells the driving
while this just holds the RPM. Norm's call, 2026-07-21.

Renders cruise_neutral.wav (engine only) and cruise_neutral_MIX.wav (engine under
a road bed at cruise level) to C:\\temp\\ffsound\\896.

Usage: uv run --with numpy --with soundfile --with scipy python sound-test/cruise_neutral.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cand_common as C  # noqa: E402
from engine_896 import OUT, cycle_loop, write  # noqa: E402

SRC = C.LICENSED["int_high"]        # SemiTruckEngine_BW.60624 -- the neutral-rev take
ROAD = Path(__file__).resolve().parents[1] / "src" / "freight_fate" / "assets" / "sounds" / "vehicle" / "road.ogg"


def find_hold(x: np.ndarray) -> tuple[float, float, float]:
    """Steadiest ~5 s window above 900 rpm (low-pass tracked, knock removed)."""
    SR = C.SR
    b, a = butter(4, 180 / (SR / 2), "low")
    xl = filtfilt(b, a, x)
    win = int(0.5 * SR); hop = int(0.5 * SR)
    f = np.fft.rfftfreq(win, 1 / SR); lo, hi = np.searchsorted(f, (24.0, 120.0)); ff = f[lo:hi]
    prev = 33.0; T = []; R = []; L = []
    for i in range(0, len(x) - win, hop):
        s = xl[i:i + win] * np.hanning(win); S = np.abs(np.fft.rfft(s))[lo:hi]
        rms = float(np.sqrt(np.mean(x[i:i + win] ** 2)))
        if S.max() < 1e-6 or rms < 0.003:
            T.append(i / SR); R.append(0.0); L.append(rms); prev = 33.0; continue
        w = S * np.exp(-((ff - prev) / 14.0) ** 2); pk = ff[int(np.argmax(w))]; prev = 0.6 * prev + 0.4 * pk
        T.append(i / SR); R.append(pk * 20); L.append(rms)
    R = np.array(R); L = np.array(L); T = np.array(T)
    need = 10  # 5 s
    best = None
    for i in range(len(R) - need):
        seg, lv = R[i:i + need], L[i:i + need]
        if np.any(seg < 900) or np.any(lv < 0.004):
            continue
        score = float(seg.std() + 5000 * lv.std())
        if best is None or score < best[0]:
            best = (score, T[i], T[i + need], float(seg.mean()))
    if best is None:
        raise SystemExit("no steady hold >900 rpm found")
    return best[1], best[2], best[3]


def main() -> None:
    SR = C.SR
    x = C.load_wav(SRC)
    a, b, rpm = find_hold(x)
    print(f"neutral-rev hold: {a:.1f}-{b:.1f}s  ~{rpm:.0f} rpm (low-pass; Norm heard ~1200)")
    seg = x[int((a + 0.3) * SR):int((b - 0.3) * SR)]
    loop, cyc = cycle_loop(seg, rpm)
    tiled = C.tile(loop, 6.0)
    write("cruise_neutral.wav", tiled)
    rd_src = C.load_wav(ROAD)

    def road_mix(engine_loop: np.ndarray) -> np.ndarray:
        rd = np.tile(rd_src, int(np.ceil(len(engine_loop) / len(rd_src))))[:len(engine_loop)]
        e = engine_loop / (np.abs(engine_loop).max() or 1.0)
        rd = rd / (np.abs(rd).max() or 1.0)
        return e * (0.55 * 0.9) + rd * (0.72 * 0.9)   # engine under road, cruise levels

    write("cruise_neutral_MIX.wav", road_mix(tiled))
    print(f"  base loop {len(loop)/SR:.2f}s cycle {cyc*1000:.0f}ms seam {C.seam_check(loop):.2f}")

    # Aggression ladder: read the loop faster to raise the firing rate a LITTLE
    # (higher/harder cruise) while keeping the formant shift small. 1.15x/1.30x
    # nudge ~1120 rpm toward ~1290/~1460 without chipmunking.
    for ratio, pct in ((1.15, 15), (1.30, 30)):
        idx = np.arange(0.0, len(loop), ratio)
        up = np.interp(idx, np.arange(len(loop)), loop)
        up_tiled = C.tile(up, 6.0)
        write(f"cruise_agg{pct}.wav", up_tiled)
        write(f"cruise_agg{pct}_MIX.wav", road_mix(up_tiled))
        print(f"  +{pct}% -> ~{rpm*ratio:.0f} rpm  cruise_agg{pct}.wav + _MIX.wav")

    # Proof the sampled cruise TRACKS rpm rather than sticking: read the loop at
    # a per-sample rate driven by an rpm curve -- cruise, climb a grade (rpm up),
    # crest, come back down. This is exactly how the game drives it every frame.
    n = int(12.0 * SR); t = np.arange(n) / SR
    def seg(t0, t1, r0, r1):
        m = (t >= t0) & (t < t1)
        return m, r0 + (r1 - r0) * np.clip((t - t0) / (t1 - t0), 0, 1)
    rpm_curve = np.full(n, rpm)
    for t0, t1, r0, r1 in ((2, 6, rpm, rpm * 1.16), (6, 7, rpm * 1.16, rpm * 1.16), (7, 11, rpm * 1.16, rpm)):
        m, v = seg(t0, t1, r0, r1); rpm_curve[m] = v[m]
    L = len(loop); rate = rpm_curve / rpm
    pos = np.cumsum(rate) - rate[0]; idx = pos % L
    i0 = np.floor(idx).astype(np.int64) % L; i1 = (i0 + 1) % L; frac = idx - np.floor(idx)
    grade = loop[i0] * (1 - frac) + loop[i1] * frac
    write("cruise_grade_MIX.wav", road_mix(grade))
    print(f"  grade demo: {rpm:.0f} -> {rpm*1.16:.0f} -> {rpm:.0f} rpm  cruise_grade_MIX.wav")
    print(f"wrote to {OUT}")


if __name__ == "__main__":
    main()
