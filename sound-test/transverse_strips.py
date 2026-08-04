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
GROUP_GAP_M = 9.5  # centre-to-centre between groups -> a slow, deliberate duh...duh


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
    # A different ANIMAL from the shoulder strip, not a louder cousin
    # (owner 2026-07-27: too similar). The milled edge is a bright buzz;
    # these are big raised bars under the whole truck -- a heavy grain
    # into a dark body makes each group a deep DOUBLE-THUD, and a
    # sub-weight layer puts it in the chest, not the ears.
    sig = convolve(out, grain(0.0032))
    body = convolve(sig, body_ir(0.22))
    sub = convolve(sig, body_ir(0.06))
    n2 = min(len(body), len(sub))
    sig = body[:n2] + 1.2 * sub[:n2]
    top = float(np.max(np.abs(sig))) or 1.0
    return sig / top * 0.98


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


def build_bar_solid() -> np.ndarray:
    """The stop bar's continuous tone: the parking-sensor 'solid' zone.

    Owner spec (written straight into the manual, 2026-07-27): ticks
    quicken from 300 feet, and AT the bar, still moving, the tone goes
    continuous -- your last leeway to be nearly stopped.

    Pitched DOWN to 400 Hz (owner call 2026-08-03, on a playtester's
    report: at 1250 it was piercing, and a tone you hold for seconds at a
    time has to be one you can stand). It no longer sits in the bink's
    pitch family, so the fuse now reads as a change of register rather
    than the ticks running together -- a clearer "you are there" than a
    faster version of the same beep, and calm enough to hold. The octave
    stays, quietly: it keeps the tone speaking over engine noise instead
    of humming underneath it. Seamless by integer cycles: 400 Hz and its
    octave both complete exactly on the loop."""
    seconds = 0.5
    t = np.arange(int(SR * seconds)) / SR
    sig = np.sin(2.0 * np.pi * 400.0 * t) + 0.3 * np.sin(2.0 * np.pi * 800.0 * t)
    top = float(np.max(np.abs(sig))) or 1.0
    return sig / top * 0.7


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
    write_mono("vehicle/bar_solid.wav", build_bar_solid())


if __name__ == "__main__":
    main()
