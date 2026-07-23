"""Find genuinely steady engine holds by measurement, not trust.

The shipped engine/high band was cut from 896's 109-121s on the label
"highway cruise" -- Norm's ear (2026-07-22) heard what the metrics confirm:
the window contains a throttle-off sag ("sounds like the truck stopped"),
a recorded air HISS, and near-idle content. This scanner slides a window
over the interior takes and scores every position on the three things a
band loop actually needs:

  pitch spread   -- firing-band track (lowpass<180, 40-130 Hz peak) must
                    hold one rpm, not sweep;
  envelope swing -- slow RMS must not surge (the stop-start jutter);
  hiss ratio     -- 3-8 kHz energy over total; air hisses and brake events
                    light this up, a working diesel cab does not.

Prints the ranked table per rpm target and cuts the best window per target
as a seamless loop (period-landed join via cand_common), loudness-matched,
into C:\\temp\\ffsound\\896\\scan_<target>_<source>.wav for Norm's ear.

Usage: uv run --with scipy python sound-test/steady_scan.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cand_common as C  # noqa: E402

LV = Path(r"C:\temp\ffsound\Splice\Samples\packs\Large Vehicles")
OUT = Path(r"C:\temp\ffsound\896")
# name -> (path, needs_interiorize). 904/905 are the same Mack family as the
# 896 donor, exterior steady holds unlocked by the validated interiorize().
SOURCES = {
    "896": (LV / "SemiTruckMac_S08IN.896.wav", False),
    "60624": (LV / "SemiTruckEngine_BW.60624.wav", False),
    "904": (LV / "SemiTruckMac_S08IN.904.wav", True),
    "905": (LV / "SemiTruckMac_S08IN.905.wav", True),
}
# (label, target rpm lo/hi). rpm comes from the ACF period, order-proof.
TARGETS = [("high1800", 1650.0, 2050.0), ("mid1150", 1080.0, 1230.0)]
WIN_S = 3.5
HOP_S = 0.5


def _acf_rpm(seg: np.ndarray, sr: int) -> float:
    """Order-proof rpm: the firing period via autocorrelation.

    Spectral peak-picking mistakes a strong 6th order of an idle for the
    firing line of a high hold (it mislabeled a 950 idle as 1900 -- the
    owner's ear caught it, twice). The ACF's shortest strong lag IS the
    firing period; harmonics land on its multiples, never below it.
    """
    seg = seg - np.mean(seg)
    n = len(seg)
    acf = np.fft.irfft(np.abs(np.fft.rfft(seg, n * 2)) ** 2)[:n]
    if acf[0] <= 0:
        return 0.0
    acf = acf / acf[0]
    lo, hi = int(sr * 20.0 / 3400.0), int(sr * 20.0 / 450.0)  # rpm 3400..450
    window = acf[lo:hi]
    strongest = float(window.max())
    threshold = 0.85 * strongest
    for k in range(len(window)):
        if window[k] >= threshold:
            return 20.0 * sr / (lo + k)
    return 0.0


def analyze(x: np.ndarray, sr: int):
    """Per-hop (rpm, env, hiss) tracks for the whole take."""
    b, a = butter(4, 250 / (sr / 2), "low")
    low = filtfilt(b, a, x)
    hop = int(sr * HOP_S)
    frame = int(sr * 1.0)
    rows = []
    for i in range(0, len(x) - frame, hop):
        rpm = _acf_rpm(low[i : i + frame], sr)
        raw = x[i : i + frame]
        env = float(np.sqrt(np.mean(raw * raw)))
        wide = np.abs(np.fft.rfft(raw * np.hanning(frame)))
        freqs = np.fft.rfftfreq(frame, 1 / sr)
        hiss = float(
            np.sum(wide[(freqs > 3000) & (freqs < 8000)] ** 2) / (np.sum(wide**2) + 1e-12)
        )
        rows.append((i / sr, rpm, env, hiss))
    return rows


def scan_source(name: str, path: Path, interior: bool):
    x = C.load_wav(path)
    if interior:
        x = C.interiorize(x)
    sr = C.SR
    rows = analyze(x, sr)
    per_win = int(WIN_S / HOP_S)
    results = {label: [] for label, _lo, _hi in TARGETS}
    for start in range(0, len(rows) - per_win):
        chunk = rows[start : start + per_win]
        rpms = np.array([r[1] for r in chunk])
        envs = np.array([r[2] for r in chunk])
        hisses = np.array([r[3] for r in chunk])
        med = float(np.median(rpms))
        if med <= 0:
            continue
        spread = float(rpms.max() / max(rpms.min(), 1e-6) - 1.0)
        swing = float((envs.max() - envs.min()) / max(envs.mean(), 1e-9))
        hiss = float(hisses.mean())
        for label, lo, hi in TARGETS:
            if lo <= med <= hi:
                score = spread * 2.0 + swing + hiss * 10.0
                results[label].append((score, chunk[0][0], med, spread, swing, hiss))
    return x, sr, results


def main() -> None:
    best_cuts = []
    for name, (path, interior) in SOURCES.items():
        if not path.exists():
            print(f"  MISSING source {path}")
            continue
        x, sr, results = scan_source(name, path, interior)
        for label, _lo, _hi in TARGETS:
            found = sorted(results[label])[:5]
            if not found:
                print(f"{name} {label}: no windows in range")
                continue
            print(f"{name} {label}: top windows (score | t0 | rpm | rpm± | env | hiss)")
            for score, t0, med, spread, swing, hiss in found:
                print(
                    f"   {score:5.2f} | {t0:6.1f}s | {med:4.0f} | "
                    f"{spread * 100:4.1f}% | {swing * 100:4.0f}% | {hiss * 100:4.2f}%"
                )
            score, t0, med, *_ = found[0]
            seg = x[int(t0 * sr) : int((t0 + WIN_S) * sr)]
            loop = C.make_seamless_loop(seg)
            out = OUT / f"scan_{label}_{name}.wav"
            C.write_wav(str(out), loop)
            best_cuts.append((out.name, t0, med))
    print()
    for cut_name, t0, rpm in best_cuts:
        print(f"  staged {cut_name}  (from {t0:.1f}s, ~{rpm:.0f} rpm)")


def _run_with_deep_stack() -> None:
    import threading

    threading.stack_size(64 * 1024 * 1024)
    t = threading.Thread(target=main)
    t.start()
    t.join()


if __name__ == "__main__":
    _run_with_deep_stack()
