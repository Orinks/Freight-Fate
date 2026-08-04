"""Production bake: the edge-boundary ladder loops for curve navigation.

Three loopable textures from the edge_nav.py audition machinery, one per
boundary STATE -- the ladder grades by structure, not loudness, so the
states stay separable under engine and road noise:

    vehicle/edge_clip.wav      clipping the strip: intermittent, grooves
                               catching and dropping out at random
    vehicle/edge_strip.wav     fully on the strip: periodic pitched buzz
    vehicle/edge_shoulder.wav  off the pavement: aperiodic gravel, no pitch

Mono on purpose (the game pans them to the drift side per frame), 48 kHz,
WAV because LOOPING BEDS ARE NEVER VORBIS. Rendered at a 62 mph reference;
the structural read (intermittent / periodic / aperiodic) survives speed
being a little off, which is the point of grading by structure.

Seamless looping: these are stationary pulse/noise processes, so the bake
renders a tail past the loop length and wrap-folds the spill back onto the
start -- convolution tails land where they would have landed had the loop
always been playing.

Usage: uv run python sound-test/edge_ladder.py  (writes straight to assets)
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from edge_nav import gravel_texture, strip_texture  # noqa: E402
from pulse_synth import SR  # noqa: E402

SECONDS = 4.0
TAIL_S = 0.5  # rendered past the loop, wrap-folded onto the start
OUT = Path(__file__).resolve().parents[1] / "src" / "freight_fate" / "assets" / "sounds"

SPEED_MS = 62 * 0.44704

# key -> (strip engagement, gravel amount, output gain)
RUNGS: dict[str, tuple[float, float, float]] = {
    "vehicle/edge_clip": (0.45, 0.0, 0.80),
    "vehicle/edge_strip": (1.0, 0.0, 0.85),
    "vehicle/edge_shoulder": (0.0, 1.0, 0.85),
}


def wrap_fold(sig: np.ndarray, loop_n: int) -> np.ndarray:
    """Fold everything past the loop length back onto the start."""
    out = sig[:loop_n].copy()
    tail = sig[loop_n:]
    out[: len(tail)] += tail[: loop_n]
    return out


def bake(engagement: float, gravel: float, gain: float) -> np.ndarray:
    n = int((SECONDS + TAIL_S) * SR)
    sig = np.zeros(n)
    if engagement > 0.0:
        sig += strip_texture(SPEED_MS, np.full(n, engagement))
    if gravel > 0.0:
        sig += 1.15 * gravel_texture(SPEED_MS, np.full(n, gravel))
    looped = wrap_fold(np.nan_to_num(sig), int(SECONDS * SR))
    top = float(np.max(np.abs(looped))) or 1.0
    return looped / top * gain


def write_mono_wav(rel: str, sig: np.ndarray) -> Path:
    path = OUT / f"{rel}.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.clip(sig, -1.0, 1.0)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes((data * 32767.0).astype("<i2").tobytes())
    return path


def main() -> None:
    for key, (engagement, gravel, gain) in RUNGS.items():
        path = write_mono_wav(key, bake(engagement, gravel, gain))
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
