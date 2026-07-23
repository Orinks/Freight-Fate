"""Build engine/high (1900 rpm) by formant-preserving pitch shift of the 896 mid.

The scan verdict (steady_scan.py, order-proof ACF rpm): NO take in the
library holds a real steady high rpm -- 896 never does (it is driven), the
60624 "high" windows are order-jumping sweeps, and the 904/905 exterior
Mac takes only sweep through 1900. So the high band is synthesized from the
896 donor itself, the owner's call ("switch to the formant model"):

1. Resample the flattened mid cut 1150 -> 1900 (naive pitch-up: the firing
   rate is now honestly 1900, but the cab formants moved up 1.652x with it
   -- the chipmunk).
2. Measure the long-term spectral envelope of the ORIGINAL mid and of the
   shifted copy, and apply their ratio as ONE static zero-phase filter over
   the whole loop. For a steady loop this puts the body resonances back
   exactly where the real cab has them -- fixed formants, moving rate, the
   project's locked principle -- with no frame-by-frame vocoder artifacts.
   Circular application keeps the loop seamless.

Deterministic. Writes C:\\temp\\ffsound\\896\\engine_high_1900_formant.wav;
re-run encode_pack.py afterward.

Usage: uv run --with scipy python sound-test/engine_high_formant.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import resample_poly

DIR = Path(r"C:\temp\ffsound\896")
SRC = DIR / "cruise_mid_1150_flat.wav"
DST = DIR / "engine_high_1900_formant.wav"
NATIVE, TARGET = 1150, 1900
ENV_SMOOTH_HZ = 90.0  # spectral-envelope smoothing width: above the firing
# line spacing (~95 Hz at 1900) so the envelope tracks formants, not partials


def envelope_db(x: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    """Long-term smoothed log-magnitude spectrum (the formant envelope)."""
    n = len(x)
    mag = np.abs(np.fft.rfft(x * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    width = max(3, int(ENV_SMOOTH_HZ / (freqs[1] - freqs[0])) | 1)
    smooth = median_filter(20.0 * np.log10(mag + 1e-9), size=width, mode="nearest")
    return freqs, smooth


def main() -> None:
    import soundfile as sf

    x, sr = sf.read(str(SRC), always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)

    shifted = resample_poly(x, NATIVE, TARGET)  # pitch up 1.652x, formants too

    f_orig, env_orig = envelope_db(x, sr)
    f_shift, env_shift = envelope_db(shifted, sr)

    n = len(shifted)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    orig_on = np.interp(freqs, f_orig, env_orig)
    shift_on = np.interp(freqs, f_shift, env_shift)
    correction_db = np.clip(orig_on - shift_on, -18.0, 18.0)
    correction = 10.0 ** (correction_db / 20.0)
    # Zero-phase, circular: filtering in the frequency domain of the whole
    # loop keeps the join exact.
    y = np.fft.irfft(np.fft.rfft(shifted) * correction, n=n)

    y *= np.sqrt(np.mean(x * x)) / np.sqrt(np.mean(y * y))
    peak = np.max(np.abs(y))
    if peak > 0.98:
        y *= 0.98 / peak
    sf.write(str(DST), y.astype("float32"), sr, subtype="FLOAT")
    print(f"wrote {DST.name}: {len(y) / sr:.1f}s at 1900 rpm, formants restored to the 896 cab")


def _run_with_deep_stack() -> None:
    import threading

    threading.stack_size(64 * 1024 * 1024)
    t = threading.Thread(target=main)
    t.start()
    t.join()


if __name__ == "__main__":
    _run_with_deep_stack()
