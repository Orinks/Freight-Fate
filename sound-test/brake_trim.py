"""Short brake release-hisses, trimmed from the licensed air-brake samples.

Norm's ear (2026-07-21): a real truck brakes with a SHORT hiss on release, not
the long loud "psssssh" of the raw samples -- and it scales with how hard you
were braking. So trim just the onset off the cleanest hisses, cut the long tail,
and make feather / light / firm intensities for the ear to judge.

Renders to C:\\temp\\ffsound\\brakes.

Usage: uv run --with numpy --with soundfile python sound-test/brake_trim.py
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cand_common as C  # noqa: E402

OUT = Path(r"C:\temp\ffsound\brakes")
LV = Path(r"C:\temp\ffsound\splice\Samples\packs\Large Vehicles")
# Cleanest short hisses with a sharp onset.
SOURCES = {
    "s916": LV / "SemiTruckBrake_S08IN.916.wav",
    "s914": LV / "SemiTruckBrake_S08IN.914.wav",
}
# (tag, seconds) -- feather is a touch, firm is a real stop; all short.
INTENSITIES = [("feather", 0.14), ("light", 0.26), ("firm", 0.45)]


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


def onset(x: np.ndarray) -> int:
    env = np.abs(x)
    w = int(0.003 * C.SR)
    env = np.convolve(env, np.ones(w) / w, "same")
    thr = env.max() * 0.2
    hits = np.nonzero(env > thr)[0]
    return int(hits[0]) if len(hits) else 0


def main() -> None:
    SR = C.SR
    for key, path in SOURCES.items():
        x = C.load_wav(path)
        a = onset(x)
        for tag, dur in INTENSITIES:
            n = int(dur * SR)
            clip = x[a:a + n].copy()
            # 8 ms attack so it starts clean; the last 40% eased out so the long
            # "sssh" tail is gone and it reads as a short chuff.
            atk = int(0.008 * SR)
            clip[:atk] *= np.linspace(0, 1, atk)
            tail = int(len(clip) * 0.4)
            clip[-tail:] *= np.linspace(1, 0, tail) ** 1.5
            # firmer press = a touch more level; feather sits back
            gain = {"feather": 0.6, "light": 0.8, "firm": 1.0}[tag]
            write(f"brake_{key}_{tag}.wav", clip * gain)
            print(f"  brake_{key}_{tag}.wav  {dur*1000:3.0f}ms")
    print(f"\nwrote short brake hisses to {OUT}")


if __name__ == "__main__":
    main()
