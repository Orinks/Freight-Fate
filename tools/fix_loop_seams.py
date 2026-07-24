"""Repair loop-seam clicks in looping engine/jake assets.

Vorbis is lossy at file edges: the first and last codec frames have no
overlap partner across the loop wrap, so even a PCM-perfect circular loop
comes back from encode/decode with a discontinuity at the joint (owner
heard it 2026-07-24 -- a click cycling with the revs, and a repeating
level dip on the jake loops). Two-part fix, applied per asset:

1. Classic loop splice: the output loop is ``x[W:]``, and its final W
   samples crossfade into ``x[0:W]`` -- the material that originally
   preceded the head -- so the wrap lands on genuinely continuous audio.
2. Write WAV (PCM_16), not Ogg: lossless, so no codec can smear the seam
   again. Looping beds are short; the size cost is small and the loader
   already prefers a present ogg, so the stale ogg must be deleted.

Usage: uv run python tools/fix_loop_seams.py  (repairs in place, prints a
before/after seam report; delete the replaced .ogg files it lists).
"""

from __future__ import annotations

import glob
import os

import numpy as np
import soundfile as sf

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LICENSED_ENGINE = os.path.join(
    REPO, "src", "freight_fate", "assets", "sounds-licensed", "engine"
)
COMMITTED_ENGINE = os.path.join(REPO, "src", "freight_fate", "assets", "sounds", "engine")

SPLICE_S = 0.025  # crossfade window; short enough to leave the character alone
EDGE_TRIM_S = 0.004  # drop the codec-smeared first/last frames before splicing


def seam_report(x: np.ndarray) -> tuple[float, float]:
    d_med = float(np.median(np.abs(np.diff(x)))) + 1e-12
    return abs(float(x[0] - x[-1])) / d_med, d_med


def _trim_faded_edges(x: np.ndarray, rate: int) -> np.ndarray:
    """Drop generator fade-in/out at the file edges before splicing.

    The original jake loops carried a ~60 ms baked fade-in, so every loop
    pass replayed a level dip -- the owner's "repeating crossfade thingy."
    Trim 10 ms frames from each end until they hold 90 percent of the
    file's median level.
    """
    frame = max(1, int(0.01 * rate))
    m = len(x) // frame
    env = np.sqrt(np.mean(x[: m * frame].reshape(m, frame) ** 2, axis=1))
    med = np.median(env) + 1e-12
    lo = 0
    while lo < m // 4 and env[lo] < 0.9 * med:
        lo += 1
    hi = m
    while hi > 3 * m // 4 and env[hi - 1] < 0.9 * med:
        hi -= 1
    return x[lo * frame : hi * frame]


def loop_splice(x: np.ndarray, rate: int) -> np.ndarray:
    x = _trim_faded_edges(x, rate)
    trim = int(EDGE_TRIM_S * rate)
    x = x[trim:-trim] if len(x) > 4 * trim else x
    w = int(SPLICE_S * rate)
    if len(x) < 4 * w:
        w = len(x) // 4
    head = x[:w]
    out = x[w:].copy()
    ramp = np.linspace(0.0, 1.0, w)
    # Linear, not equal-power: these loops are near-periodic, so the tail and
    # the head's preceding material are correlated -- a sqrt ramp dips or
    # bumps the level through the joint, a linear one holds it flat.
    out[-w:] = out[-w:] * (1.0 - ramp) + head * ramp
    return out


def repair(path: str) -> str | None:
    x, rate = sf.read(path, dtype="float64")
    if x.ndim > 1:
        x = x.mean(axis=1)
    before, _ = seam_report(x)
    fixed = loop_splice(x, rate)
    after, _ = seam_report(fixed)
    peak = np.max(np.abs(fixed)) + 1e-12
    if peak > 0.99:
        fixed = fixed / peak * 0.99
    wav_path = os.path.splitext(path)[0] + ".wav"
    sf.write(wav_path, fixed.astype(np.float32), rate, subtype="PCM_16")
    name = os.path.basename(path)
    print(f"{name:22s} seam {before:6.1f}x -> {after:4.1f}x   wrote {os.path.basename(wav_path)}")
    return path


def main() -> None:
    replaced: list[str] = []
    for name in ("idle.ogg", "low.ogg", "mid.ogg", "midhigh.ogg", "high.ogg"):
        path = os.path.join(LICENSED_ENGINE, name)
        if os.path.exists(path):
            replaced.append(repair(path))
    for path in sorted(glob.glob(os.path.join(COMMITTED_ENGINE, "jake_*.ogg"))):
        replaced.append(repair(path))
    print("\nDelete the stale ogg files (the loader prefers ogg over wav):")
    for path in replaced:
        if path:
            print(f"  {path}")


if __name__ == "__main__":
    main()
