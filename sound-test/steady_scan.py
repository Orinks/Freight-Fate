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
SOURCES = {
    "896": LV / "SemiTruckMac_S08IN.896.wav",  # THE donor (interior, driving)
    "60624": LV / "SemiTruckEngine_BW.60624.wav",  # interior high-rpm take
}
# (label, target rpm band as firing Hz lo/hi). rpm = 20 * firing Hz.
TARGETS = [("high1800", 82.0, 98.0), ("mid1150", 54.0, 61.0)]
WIN_S = 3.5
HOP_S = 0.5


def analyze(x: np.ndarray, sr: int):
    """Per-hop (pitch, env, hiss) tracks for the whole take."""
    b, a = butter(4, 180 / (sr / 2), "low")
    low = filtfilt(b, a, x)
    hop = int(sr * HOP_S)
    frame = int(sr * 1.0)
    rows = []
    for i in range(0, len(x) - frame, hop):
        seg = low[i : i + frame] * np.hanning(frame)
        spec = np.abs(np.fft.rfft(seg))
        freqs = np.fft.rfftfreq(frame, 1 / sr)
        band = (freqs > 40) & (freqs < 130)
        pitch = freqs[band][np.argmax(spec[band])]
        raw = x[i : i + frame]
        env = float(np.sqrt(np.mean(raw * raw)))
        wide = np.abs(np.fft.rfft(raw * np.hanning(frame)))
        hiss = float(
            np.sum(wide[(freqs > 3000) & (freqs < 8000)] ** 2) / (np.sum(wide**2) + 1e-12)
        )
        rows.append((i / sr, pitch, env, hiss))
    return rows


def scan_source(name: str, path: Path):
    x = C.load_wav(path)
    sr = C.SR
    rows = analyze(x, sr)
    per_win = int(WIN_S / HOP_S)
    results = {label: [] for label, _lo, _hi in TARGETS}
    for start in range(0, len(rows) - per_win):
        chunk = rows[start : start + per_win]
        pitches = np.array([r[1] for r in chunk])
        envs = np.array([r[2] for r in chunk])
        hisses = np.array([r[3] for r in chunk])
        med = float(np.median(pitches))
        spread = float(pitches.max() / max(pitches.min(), 1e-6) - 1.0)
        swing = float((envs.max() - envs.min()) / max(envs.mean(), 1e-9))
        hiss = float(hisses.mean())
        for label, lo, hi in TARGETS:
            if lo <= med <= hi:
                score = spread * 2.0 + swing + hiss * 10.0
                results[label].append((score, chunk[0][0], med, spread, swing, hiss))
    return x, sr, results


def main() -> None:
    best_cuts = []
    for name, path in SOURCES.items():
        if not path.exists():
            print(f"  MISSING source {path}")
            continue
        x, sr, results = scan_source(name, path)
        for label, _lo, _hi in TARGETS:
            found = sorted(results[label])[:5]
            if not found:
                print(f"{name} {label}: no windows in range")
                continue
            print(f"{name} {label}: top windows (score | t0 | rpm | pitch± | env | hiss)")
            for score, t0, med, spread, swing, hiss in found:
                print(
                    f"   {score:5.2f} | {t0:6.1f}s | {med * 20:4.0f} | "
                    f"{spread * 100:4.1f}% | {swing * 100:4.0f}% | {hiss * 100:4.2f}%"
                )
            score, t0, med, *_ = found[0]
            seg = x[int(t0 * sr) : int((t0 + WIN_S) * sr)]
            loop = C.make_seamless_loop(seg)
            out = OUT / f"scan_{label}_{name}.wav"
            C.write_wav(str(out), loop)
            best_cuts.append((out.name, t0, med * 20))
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
