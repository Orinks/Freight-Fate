"""Flatten the macro envelope of the 896 band cuts -- kill the loop surge.

Measured (2026-07-22, owner heard it as "stop-start jutter" at 1700-1800):
cruise_high_1800 swings 64 percent in slow RMS across its 6 s loop, and
cruise_mid_1150 swings 50 -- the "steady holds" carry the real driver's
throttle surging, so every loop pass is a surge cycle. Same cure as the
pressurization loop: divide out the SLOW envelope (computed circularly, so
the loop point stays exact) while keeping the fast combustion texture, then
re-derive the pitched bands (950, 1425) from the flattened mid so the whole
ring is surge-free.

idle_680 is left untouched: approved by ear, and idles genuinely wander.

Writes *_flat.wav plus re-derived engine_low_950 / engine_midhigh_1425 under
C:\\temp\\ffsound\\896. Deterministic. Re-run encode_pack.py afterward.

Usage: uv run --with scipy python sound-test/engine_band_flatten.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt, resample_poly

DIR = Path(r"C:\temp\ffsound\896")
# Below this is "surge", above is engine texture. 4 Hz: the stop-start
# cadence the owner heard sits at 2-5 Hz, while the per-cylinder lope that
# makes it a diesel lives at 15-30 Hz (rev rate and half-orders) -- safely
# above the knee even at 1150 rpm.
ENV_CUTOFF_HZ = 4.0


def flatten(name: str, sr_expect: int | None = None) -> None:
    import soundfile as sf

    src = DIR / f"{name}.wav"
    x, sr = sf.read(str(src), always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    # Circular slow envelope: wrap-pad so the loop point sees the same
    # neighborhood as any interior sample and stays seamless.
    pad = sr  # one second of wrap context each side
    xc = np.concatenate([x[-pad:], x, x[:pad]])
    b, a = butter(2, ENV_CUTOFF_HZ / (sr / 2), "low")
    env = np.sqrt(np.maximum(filtfilt(b, a, xc * xc), 1e-12))[pad:-pad]
    flat = x * (float(np.mean(env)) / env)
    peak = np.max(np.abs(flat))
    if peak > 0.98:
        flat *= 0.98 / peak
    dst = DIR / f"{name}_flat.wav"
    sf.write(str(dst), flat.astype("float32"), sr, subtype="FLOAT")
    swing = (env.max() - env.min()) / env.mean()
    print(f"{name}: envelope swing {swing * 100:.0f}% -> flattened ({dst.name})")


def rederive(src_name: str, dst_name: str, native: int, target: int) -> None:
    import soundfile as sf

    x, sr = sf.read(str(DIR / f"{src_name}.wav"), always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    y = resample_poly(x, native, target).astype("float32")
    sf.write(str(DIR / f"{dst_name}.wav"), np.clip(y, -1.0, 1.0), sr, subtype="FLOAT")
    print(f"{dst_name}: re-derived from {src_name} at {target} rpm")


def main() -> None:
    flatten("cruise_mid_1150")
    flatten("cruise_high_1800")
    rederive("cruise_mid_1150_flat", "engine_low_950", 1150, 950)
    rederive("cruise_mid_1150_flat", "engine_midhigh_1425", 1150, 1425)


def _run_with_deep_stack() -> None:
    import threading

    threading.stack_size(64 * 1024 * 1024)
    t = threading.Thread(target=main)
    t.start()
    t.join()


if __name__ == "__main__":
    _run_with_deep_stack()
