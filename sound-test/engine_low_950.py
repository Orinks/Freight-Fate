"""Build the engine LOW band (950 rpm) from the 896 mid cut.

The old low band was the 60624 neutral-rev hold, labeled ~1000 rpm -- but its
firing fundamental measures 56.2 Hz = ~1125 rpm, 30 rpm under the mid cut, and
60624 is (probably) a different truck than the 896 donor. Both problems at
once: retire it, and pitch the 896 mid cut (native 1150) down to 950 by
resampling -- a 17% shift, inside the no-chipmunk tolerance, same truck, same
loaded cab timbre. The ring's rate clamps (0.85-1.30) then cover 578-1495 rpm
continuously through the launch zone: 680 reaches 884, 950 spans 807-1235.

Deterministic. Writes C:\\temp\\ffsound\\896\\engine_low_950.wav; re-run
encode_pack.py afterward.

Usage: uv run --with scipy python sound-test/engine_low_950.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

SRC = Path(r"C:\temp\ffsound\896\cruise_mid_1150.wav")
DST = Path(r"C:\temp\ffsound\896\engine_low_950.wav")
NATIVE, TARGET = 1150, 950


def main() -> None:
    import soundfile as sf

    x, sr = sf.read(str(SRC), always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    # Lower the pitch by NATIVE/TARGET: stretch to more samples, keep the rate.
    y = resample_poly(x, NATIVE, TARGET).astype("float32")
    sf.write(str(DST), np.clip(y, -1.0, 1.0), sr, subtype="FLOAT")

    # Verify: strongest low peak should sit near the 2x firing harmonic,
    # 2 * TARGET/20 = 95 Hz (the fundamental itself is weaker in these cabs).
    from scipy.signal import butter, filtfilt

    b, a = butter(4, 180 / (sr / 2), "low")
    z = filtfilt(b, a, y)
    spec = np.abs(np.fft.rfft(z * np.hanning(len(z))))
    freqs = np.fft.rfftfreq(len(z), 1 / sr)
    band = (freqs > 20) & (freqs < 115)
    f0 = freqs[band][np.argmax(spec[band])]
    print(f"wrote {DST.name}: {len(y) / sr:.1f}s, low peak {f0:.1f} Hz "
          f"(target 2x harmonic {2 * TARGET / 20:.1f} Hz)")


def _run_with_deep_stack() -> None:
    import threading

    threading.stack_size(64 * 1024 * 1024)
    t = threading.Thread(target=main)
    t.start()
    t.join()


if __name__ == "__main__":
    _run_with_deep_stack()
