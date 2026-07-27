"""Production bake: dead-man's-curve transverse rumble strips + lane locator.

Two assets for curve navigation:

``vehicle/transverse_strips.wav`` -- the wake-up ahead of a hairpin. Real
DOTs cut transverse rumble strips ACROSS the travel lane before curves
that kill people: grouped bars the whole truck crosses, reading as
duh-duh duh-duh duh-duh -- each burst is the steer axle then the drive
axles over one bar group. Louder and spikier than the shoulder strip on
purpose: less cab filtering, more high frequency kept, because the real
thing is under all six tires at speed and it is MEANT to wake the driver.
Center image (the game plays it unpanned -- the bars span the lane).

``vehicle/lane_locator.wav`` -- a soft on-demand position tock, panned by
the game to where the truck sits in its lane. Quiet and rounded: it is
information the player summoned, never an alarm.

Usage: uv run python sound-test/transverse_strips.py  (writes to assets)
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pulse_synth import SR, body_ir, convolve, grain  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "src" / "freight_fate" / "assets" / "sounds"

SPEED_MS = 22.0  # ~50 mph approach: the design speed the bar spacing assumes
# Tractor axle geometry, metres behind the steer axle, with load weights.
AXLES = [(0.0, 1.0), (3.8, 0.95), (5.1, 0.9)]
BARS_PER_GROUP = 4
BAR_SPACING_M = 0.6  # bars inside one group
GROUP_COUNT = 3
GROUP_GAP_M = 7.0  # centre-to-centre between groups -> the duh...duh rhythm


def build_strips() -> np.ndarray:
    total_m = GROUP_COUNT * GROUP_GAP_M + 10.0
    n = int(total_m / SPEED_MS * SR)
    out = np.zeros(n)
    for group in range(GROUP_COUNT):
        group_at = group * GROUP_GAP_M
        for bar in range(BARS_PER_GROUP):
            bar_at = group_at + bar * BAR_SPACING_M
            for axle_m, load in AXLES:
                t_hit = (bar_at + axle_m) / SPEED_MS
                i = int(t_hit * SR)
                if 0 <= i < n:
                    out[i] += load
    # Spikier than the shoulder strip: a sharper grain and a body that
    # keeps far more high end (hf_keep 0.55 vs the cab's usual smoothing).
    sig = convolve(out, grain(0.0011))
    sig = convolve(sig, body_ir(0.55))
    top = float(np.max(np.abs(sig))) or 1.0
    return sig / top * 0.95


def build_lane_line() -> np.ndarray:
    """Crossing the raised markers on an interior lane line: the flurp-flurp.

    Each axle strikes the marker line ONCE, front to back -- a tractor-
    trailer turns a car's tight two-bump into a five-hit roll spread over
    half a second, each hit quieter and duller than the last (the
    lane_line.py audition's arithmetic). Panned by the game toward the
    side being crossed. NOT a rumble strip: interior lines have no milled
    grooves, and the edge ladder stays the edges' voice."""
    axles_m = [(0.0, 1.0), (3.8, 0.85), (5.1, 0.75), (12.5, 0.55), (13.8, 0.45)]
    n = int(1.0 * SR)
    out = np.zeros(n)
    for dist_m, gain in axles_m:
        i = int(dist_m / SPEED_MS * SR)
        if i < n:
            out[i] += gain
    sig = convolve(out, grain(0.0016))
    sig = convolve(sig, body_ir(0.45))
    top = float(np.max(np.abs(sig))) or 1.0
    return sig / top * 0.8


def build_bink() -> np.ndarray:
    """The curve cue: a short bright bink, not a click (owner call
    2026-07-27 -- a click is not loud enough to carry a safety cue).
    Distinct from the signal tone (lower tock) and the locator (soft)."""
    seconds = 0.13
    t = np.arange(int(SR * seconds)) / SR
    sig = np.sin(2.0 * np.pi * 1250.0 * t) + 0.4 * np.sin(2.0 * np.pi * 2500.0 * t)
    env = np.minimum(t / 0.003, 1.0) * np.exp(-t / 0.035)
    sig *= env
    top = float(np.max(np.abs(sig))) or 1.0
    return sig / top * 0.9


def build_locator() -> np.ndarray:
    seconds = 0.07
    t = np.arange(int(SR * seconds)) / SR
    sig = np.sin(2.0 * np.pi * 620.0 * t) + 0.25 * np.sin(2.0 * np.pi * 1240.0 * t)
    env = np.minimum(t / 0.005, 1.0) * np.exp(-t / 0.018)
    sig *= env
    top = float(np.max(np.abs(sig))) or 1.0
    return sig / top * 0.6


def write_mono(rel: str, sig: np.ndarray) -> None:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.clip(np.nan_to_num(sig), -1.0, 1.0)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes((data * 32767.0).astype("<i2").tobytes())
    print(f"wrote {path} ({len(sig) / SR:.2f}s)")


def main() -> None:
    write_mono("vehicle/transverse_strips.wav", build_strips())
    write_mono("vehicle/lane_locator.wav", build_locator())
    write_mono("vehicle/curve_bink.wav", build_bink())
    write_mono("vehicle/lane_line_cross.wav", build_lane_line())


if __name__ == "__main__":
    main()
