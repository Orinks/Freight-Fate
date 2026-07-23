"""Build the whole engine ring from ONE clean anchor via the formant model.

Owner's call after hearing engine_high_formant.py's 1900 ("amazingly
correct"): use the formant model for the whole family. It also solves the
baked-in hiss at the root -- the mid cut came from 896's air-build phase,
so a real fill hiss sits at 1.4-5.5s of the loop, and every derived band
inherited it (the periodic hiss the owner chased in-game, once per loop
pass per band).

Construction:
1. The mid_flat loop is seamless, so roll it to start at 5.6s and take the
   contiguous CLEAN span that wraps the join (5.6 -> 6.0 -> 1.35s, ~1.75s,
   hiss <= 3 percent everywhere) -> re-loop with a period-landed join.
   That clean loop IS the mid band (native ~1150), and the single anchor
   for everything above idle.
2. Formant-shift the anchor to 950, 1425, and 1900: resample for the
   honest firing rate, then one static envelope-correction filter per
   band puts the 896 cab's formants back (fixed formants, moving rate).
   The idle band stays the real, separately-cut, measured-clean idle_680.

Deterministic. Writes cruise_mid_1150_clean.wav and overwrites the three
derived band files under C:\\temp\\ffsound\\896; re-run encode_pack.py.

Usage: uv run --with scipy python sound-test/engine_ring_formant.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cand_common as C  # noqa: E402

DIR = Path(r"C:\temp\ffsound\896")
SRC = DIR / "cruise_mid_1150_flat.wav"
CLEAN_START_S = 5.6  # roll point: the hiss-free span wraps the loop join
CLEAN_LEN_S = 1.75
NATIVE = 1150
TARGETS = {
    "engine_low_950": 950,
    "engine_midhigh_1425": 1425,
    "engine_high_1900_formant": 1900,
}
ENV_SMOOTH_HZ = 90.0


def envelope_db(x: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    n = len(x)
    mag = np.abs(np.fft.rfft(x * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    width = max(3, int(ENV_SMOOTH_HZ / (freqs[1] - freqs[0])) | 1)
    smooth = median_filter(20.0 * np.log10(mag + 1e-9), size=width, mode="nearest")
    return freqs, smooth


def formant_shift(x: np.ndarray, sr: int, native: float, target: float) -> np.ndarray:
    shifted = resample_poly(x, int(native), int(target))
    f_orig, env_orig = envelope_db(x, sr)
    f_shift, env_shift = envelope_db(shifted, sr)
    n = len(shifted)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    correction_db = np.clip(
        np.interp(freqs, f_orig, env_orig) - np.interp(freqs, f_shift, env_shift), -18.0, 18.0
    )
    y = np.fft.irfft(np.fft.rfft(shifted) * 10.0 ** (correction_db / 20.0), n=n)
    y *= np.sqrt(np.mean(x * x)) / np.sqrt(np.mean(y * y))
    peak = np.max(np.abs(y))
    if peak > 0.98:
        y *= 0.98 / peak
    return y.astype("float32")


def main() -> None:
    import soundfile as sf

    x, sr = sf.read(str(SRC), always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    rolled = np.roll(x, -int(CLEAN_START_S * sr))
    clean = C.make_seamless_loop(rolled[: int(CLEAN_LEN_S * sr)])
    peak = np.max(np.abs(clean))
    if peak > 0.98:
        clean = clean * (0.98 / peak)
    sf.write(str(DIR / "cruise_mid_1150_clean.wav"), clean.astype("float32"), sr, subtype="FLOAT")
    print(f"anchor cruise_mid_1150_clean.wav: {len(clean) / sr:.2f}s from the hiss-free span")

    for name, target in TARGETS.items():
        y = formant_shift(clean, sr, NATIVE, target)
        sf.write(str(DIR / f"{name}.wav"), y, sr, subtype="FLOAT")
        print(f"{name}.wav: {len(y) / sr:.2f}s at {target} rpm, 896 formants")


def _run_with_deep_stack() -> None:
    import threading

    threading.stack_size(64 * 1024 * 1024)
    t = threading.Thread(target=main)
    t.start()
    t.join()


if __name__ == "__main__":
    _run_with_deep_stack()
