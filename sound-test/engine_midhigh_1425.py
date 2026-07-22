"""Build the engine MID-HIGH band (1425 rpm) from the 896 mid cut.

The mid (1150) to high (1800) gap is a 1.565 ratio -- too wide for one
crossfade: a cut stretched that far moves its formants audibly (the launch
smear), and with rate clamps the two members of the blend play clashing
pitches (the 1700-1800 "stop-start jutter" the owner heard: ~10 Hz beat
between a clamped mid and a tracking high). A fifth band at 1425 splits the
gap into 1.24 and 1.263 ratios, so with the narrow geometric-midpoint
crossfade windows no cut ever plays more than ~16 percent off its recorded
speed. Same construction as engine_low_950.py, pitched the other way.

Deterministic. Writes C:\\temp\\ffsound\\896\\engine_midhigh_1425.wav;
re-run encode_pack.py afterward.

Usage: uv run --with scipy python sound-test/engine_midhigh_1425.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

SRC = Path(r"C:\temp\ffsound\896\cruise_mid_1150.wav")
DST = Path(r"C:\temp\ffsound\896\engine_midhigh_1425.wav")
NATIVE, TARGET = 1150, 1425


def main() -> None:
    import soundfile as sf

    x, sr = sf.read(str(SRC), always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    # Raise the pitch by TARGET/NATIVE: fewer samples at the same rate.
    y = resample_poly(x, NATIVE, TARGET).astype("float32")
    sf.write(str(DST), np.clip(y, -1.0, 1.0), sr, subtype="FLOAT")
    print(f"wrote {DST.name}: {len(y) / sr:.1f}s at nominal {TARGET} rpm")


def _run_with_deep_stack() -> None:
    import threading

    threading.stack_size(64 * 1024 * 1024)
    t = threading.Thread(target=main)
    t.start()
    t.join()


if __name__ == "__main__":
    _run_with_deep_stack()
