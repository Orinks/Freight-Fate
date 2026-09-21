"""A round-robin bank of brake-release hisses, so repeated braking varies.

Norm 2026-07-21: the single trimmed release has a low hum and repeats too
obviously -- find more releases and round-robin them. The Bantam brake machine
is 61 s of a valve pressed and released over and over: auto-segment it into
individual actuations, add the distinct one-shot brakes, high-pass out the sub-
200 Hz hum, trim each to a short chuff, level-match. The game cycles through the
bank so ten brake taps sound like ten real ones.

Renders brake_rr_NN.wav + a brake_rr_demo.wav (all of them, spaced) to
C:\\temp\\ffsound\\brakes.

Usage: uv run --with numpy --with soundfile --with scipy python sound-test/brake_trim.py
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cand_common as C  # noqa: E402

OUT = Path(r"C:\temp\ffsound\brakes")
LV = Path(r"C:\temp\ffsound\splice\Samples\packs\Large Vehicles")
IND = Path(r"C:\temp\ffsound\splice\Samples\packs\Industry Vol. 1")
BANTAM = IND / "BantamBrakeMach_S08IN.62.wav"
ONE_SHOTS = [
    LV / "SemiTruckBrake_S08IN.914.wav",
    LV / "SemiTruckBrake_S08IN.915.wav",
    LV / "SemiTruckBrake_S08IN.916.wav",
    LV / "SemiTruckAirBrake_BWU.95.wav",
    IND / "AirBrake_BW.20321.wav",
]


def hp(x: np.ndarray, fc: float = 200.0) -> np.ndarray:
    b, a = butter(2, fc / (C.SR / 2), "high")
    return filtfilt(b, a, x)


def write(name: str, x: np.ndarray, target_rms: float = 0.10) -> None:
    x = np.nan_to_num(np.asarray(x, float))
    x = x * (target_rms / (float(np.sqrt(np.mean(x ** 2))) or 1.0))
    p = float(np.max(np.abs(x))) or 1.0
    if p > 0.97:
        x = x * (0.97 / p)
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / name), "wb") as fh:
        fh.setnchannels(1); fh.setsampwidth(2); fh.setframerate(C.SR)
        fh.writeframes((x * 32767).astype("<i2").tobytes())


def chuff(seg: np.ndarray, max_s: float = 0.5) -> np.ndarray:
    """Trim to a short release: onset, 8 ms attack, tail eased so no long sssh."""
    seg = hp(seg)
    n = min(len(seg), int(max_s * C.SR))
    seg = seg[:n].copy()
    atk = int(0.008 * C.SR)
    seg[:atk] *= np.linspace(0, 1, atk)
    tail = int(len(seg) * 0.45)
    seg[-tail:] *= np.linspace(1, 0, tail) ** 1.5
    return seg


def segment_bantam(x: np.ndarray, min_gap_s: float = 0.35, max_events: int = 12) -> list[np.ndarray]:
    """Cut the machine loop at its loudest onsets (each valve actuation)."""
    xh = hp(x)
    env = np.abs(xh)
    w = int(0.005 * C.SR)
    env = np.convolve(env, np.ones(w) / w, "same")
    thr = np.percentile(env, 90) * 0.6
    gap = int(min_gap_s * C.SR)
    events = []
    i = 0
    while i < len(env) - int(0.5 * C.SR) and len(events) < max_events:
        if env[i] > thr and (env[i] >= env[max(0, i - w):i + w].max() - 1e-9):
            events.append(chuff(x[i:i + int(0.5 * C.SR)]))
            i += gap
        else:
            i += 1
    return events


def main() -> None:
    bank: list[np.ndarray] = []
    if BANTAM.exists():
        bank += segment_bantam(C.load_wav(BANTAM))
    for p in ONE_SHOTS:
        if p.exists():
            x = C.load_wav(p)
            a = int(np.argmax(np.abs(hp(x))) )  # near the onset peak
            a = max(0, a - int(0.02 * C.SR))
            bank.append(chuff(x[a:a + int(0.5 * C.SR)]))
    # drop any near-silent slices
    bank = [b for b in bank if np.sqrt(np.mean(b ** 2)) > 1e-3]
    for i, b in enumerate(bank, 1):
        write(f"brake_rr_{i:02d}.wav", b)
    print(f"  {len(bank)} round-robin releases (high-passed, trimmed)")
    # demo: all of them spaced, to hear the variety
    gap = np.zeros(int(0.5 * C.SR))
    demo = np.concatenate([np.concatenate([b / (np.abs(b).max() or 1) * 0.7, gap]) for b in bank])
    write("brake_rr_demo.wav", demo)
    print(f"  wrote brake_rr_demo.wav ({len(demo)/C.SR:.1f}s) to {OUT}")


if __name__ == "__main__":
    main()
