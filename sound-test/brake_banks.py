"""Sort the licensed brake material into the two round-robin banks + an e-brake.

Locked spec (Norm 2026-07-21):
  PRESS   -> clunk bank, shuffle RR, level by press force
  RELEASE -> hiss bank,  shuffle RR, length + level by how hard you braked
  E-BRAKE -> one big sustained air event (the full Bantam)
  All quiet under the engine; +-pitch/level jitter per trigger at play time.

Clunk vs hiss is decided by spectral centroid (low = mechanical clunk, high =
air). Hiss intensity is trimmed to length at play time, not pre-baked. Outputs
to C:\\temp\\ffsound\\brakes as brake_clunk_NN / brake_hiss_NN / ebrake_full.

Usage: uv run --with numpy --with soundfile --with scipy python sound-test/brake_banks.py
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
SOURCES = [
    LV / "SemiTruckBrake_S08IN.913.wav",   # clunk (low body)
    LV / "SemiTruckBrake_S08IN.914.wav",
    LV / "SemiTruckBrake_S08IN.915.wav",
    LV / "SemiTruckBrake_S08IN.916.wav",
    LV / "SemiTruckAirBrake_BWU.95.wav",
    IND / "AirBrake_BW.20321.wav",
]
CLUNK_CENTROID = 2800.0  # below this (after HP) reads as clunk, above as hiss


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


def centroid(x: np.ndarray) -> float:
    S = np.abs(np.fft.rfft(x * np.hanning(len(x)))); f = np.fft.rfftfreq(len(x), 1 / C.SR)
    return float((S * f).sum() / (S.sum() or 1.0))


def chuff(seg: np.ndarray, max_s: float = 0.55) -> np.ndarray:
    seg = hp(seg)
    seg = seg[:int(max_s * C.SR)].copy()
    atk = int(0.008 * C.SR); seg[:atk] *= np.linspace(0, 1, atk)
    tail = int(len(seg) * 0.45); seg[-tail:] *= np.linspace(1, 0, tail) ** 1.5
    return seg


def bantam_events(x: np.ndarray, max_events: int = 14) -> list[np.ndarray]:
    xh = hp(x); env = np.convolve(np.abs(xh), np.ones(int(0.005 * C.SR)) / int(0.005 * C.SR), "same")
    thr = np.percentile(env, 90) * 0.6; gap = int(0.35 * C.SR); w = int(0.005 * C.SR)
    out = []; i = 0
    while i < len(env) - int(0.55 * C.SR) and len(out) < max_events:
        if env[i] > thr and env[i] >= env[max(0, i - w):i + w].max() - 1e-9:
            out.append(x[i:i + int(0.55 * C.SR)]); i += gap
        else:
            i += 1
    return out


def main() -> None:
    clunks: list[np.ndarray] = []
    hisses: list[np.ndarray] = []
    pool = [C.load_wav(p) for p in SOURCES]
    if BANTAM.exists():
        pool += bantam_events(C.load_wav(BANTAM))
    for x in pool:
        a = max(0, int(np.argmax(np.abs(hp(x)))) - int(0.02 * C.SR))
        c = chuff(x[a:a + int(0.55 * C.SR)])
        if np.sqrt(np.mean(c ** 2)) < 1e-3:
            continue
        (clunks if centroid(c) < CLUNK_CENTROID else hisses).append(c)
    for i, c in enumerate(clunks, 1):
        write(f"brake_clunk_{i:02d}.wav", c)
    for i, h in enumerate(hisses, 1):
        write(f"brake_hiss_{i:02d}.wav", h)
    # e-brake: one big sustained air event -- 2.5 s of the Bantam machine running
    if BANTAM.exists():
        x = C.load_wav(BANTAM)
        mid = len(x) // 2
        eb = hp(x[mid:mid + int(2.5 * C.SR)]).copy()
        atk = int(0.02 * C.SR); eb[:atk] *= np.linspace(0, 1, atk)
        eb[-int(0.2 * C.SR):] *= np.linspace(1, 0, int(0.2 * C.SR))
        write("ebrake_full.wav", eb)
    print(f"  clunk bank: {len(clunks)}   hiss bank: {len(hisses)}   + ebrake_full.wav")
    print(f"  wrote to {OUT}")


if __name__ == "__main__":
    main()
