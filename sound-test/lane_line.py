"""Audition prototype: lane-line marker crossing, and a jake loop benchmark.

Audition only -- imports nothing from freight_fate, touches no save data.

WHY THIS EXISTS. The edge-rumble lane change could not reproduce Norm's
remembered "flurpflurp" and the arithmetic says it never will: crossing 3.6 m
in ~3 s is ~1.2 m/s laterally, so a 0.40 m rumble band holds each axle for
~330 ms while the axles are only 90-260 ms apart. They are forced to overlap.

A raised pavement marker is a different object. A wheel crossing the lane
line traverses the marker's ~0.10 m in well under 100 ms, and -- the key
part -- the crossing happens at ONE longitudinal point, so each axle hits AT
MOST ONE marker. Front wheel strikes it, rear wheel strikes the same marker
one wheelbase later. Two bumps. That is the flurp-flurp, and it is a car's
93 ms wheelbase delay that makes it read as a tight pair.

A tractor-trailer turns the same event into a five-hit roll spread over about
half a second, each hit quieter and duller than the last.

Usage: uv run python lane_line.py
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pulse_synth
from jake_v2 import jake
from pulse_synth import SR, cab_perspective, convolve, write_wav

pulse_synth.OUT = Path(__file__).resolve().parent

CAR_AXLES = [(0.0, 1.0), (2.70, 0.92)]
TRUCK_AXLES = [(0.0, 0.55), (6.10, 1.00), (7.35, 1.00), (12.9, 0.80), (14.15, 0.80)]


def marker_ir(hf_keep: float = 1.0) -> np.ndarray:
    """One raised marker under a tire: a dull, heavily damped thud.

    Bigger and lower than a milled groove -- a single discrete bump rather
    than one tooth of a comb -- but still rubber, so still short.
    """
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    ir = np.zeros(n)
    modes = ((48.0, 0.020, 1.00), (86.0, 0.014, 0.85), (140.0, 0.010, 0.60),
             (230.0, 0.007, 0.40), (390.0, 0.005, 0.24), (720.0, 0.003, 0.12))
    for freq, dec, gain in modes:
        tilt = 1.0 if freq < 100 else hf_keep ** (1.0 + freq / 400.0)
        ir += gain * tilt * np.exp(-t / dec) * np.sin(2 * np.pi * freq * t)
    # A little contact grit so it reads as plastic-on-rubber, not a drum.
    w = int(0.0018 * SR)
    return ir + 0.18 * convolve(ir, pulse_synth.RNG.standard_normal(w) * np.hanning(w))[:n]


def cross_markers(
    speed_ms: float,
    axles: list[tuple[float, float]],
    n_markers: int = 1,
    marker_spacing_m: float = 7.3,
    seconds: float = 2.5,
    label: str = "",
) -> np.ndarray:
    """Strike n markers, each hit once per axle, from the cab's seat."""
    n = int(seconds * SR)
    out = np.zeros(n)
    rows = []
    for m in range(n_markers):
        # Each successive marker is one spacing further along the line.
        t_marker = 0.6 + m * marker_spacing_m / speed_ms
        for dist, load in axles:
            gain, hf_keep, prop = cab_perspective(dist)
            t_hit = t_marker + dist / speed_ms + prop
            i = int(t_hit * SR)
            if not 0 <= i < n:
                continue
            ir = marker_ir(hf_keep) * load * gain
            out[i : i + len(ir)] += ir[: n - i]
            if m == 0:
                rows.append((dist, t_hit, 20 * np.log10(max(gain * load, 1e-9))))
    if label and rows:
        print(f"    {label}:")
        base = rows[0][1]
        for dist, t_hit, db in rows:
            print(f"      axle {dist:5.2f}m -> {(t_hit - base) * 1000:6.1f} ms after "
                  f"the first hit, {db:+5.1f} dB")
    return out


def seamless_jake_loop(rpm: float, cycles: int = 8, stage: int = 3) -> np.ndarray:
    """A loop holding a whole number of 720-degree cycles, so it can repeat.

    The half-order lope repeats every TWO revolutions, so a loop that is not
    an integer number of full four-stroke cycles will click at the seam and
    scramble the lope. One cycle is 120/RPM seconds.
    """
    seconds = cycles * 120.0 / rpm
    return jake(np.full(int(seconds * SR), rpm), stage=stage)


def main() -> None:
    print("lane-line markers -- a single marker, front axle then rear")
    write_wav("marker_car_65mph.wav",
              cross_markers(65 * 0.44704, CAR_AXLES, label="car 65 mph"))
    write_wav("marker_truck_65mph.wav",
              cross_markers(65 * 0.44704, TRUCK_AXLES, seconds=3.0, label="truck 65 mph"))

    print("\nlane-line markers -- clipping two markers on a shallow crossing")
    write_wav("marker_car_two_65mph.wav",
              cross_markers(65 * 0.44704, CAR_AXLES, n_markers=2, seconds=3.0))
    write_wav("marker_truck_two_65mph.wav",
              cross_markers(65 * 0.44704, TRUCK_AXLES, n_markers=2, seconds=3.5))

    print("\nlane-line markers -- slower, for comparison")
    write_wav("marker_truck_35mph.wav",
              cross_markers(35 * 0.44704, TRUCK_AXLES, seconds=3.5, label="truck 35 mph"))

    print("\nseamless jake loops (integer four-stroke cycles)")
    timings = []
    for rpm in (1200, 1400, 1600, 1800, 2000, 2200):
        t0 = time.perf_counter()
        loop = seamless_jake_loop(rpm)
        dt = (time.perf_counter() - t0) * 1000
        timings.append(dt)
        write_wav(f"jakeloop_{rpm}rpm.wav", loop)
        print(f"      {rpm} rpm: {len(loop) / SR * 1000:.0f} ms of audio "
              f"generated in {dt:.0f} ms")
    print(f"\n    six buckets generated in {sum(timings):.0f} ms total "
          f"-- cheap enough to build at startup rather than ship as assets")

    print(f"\nwrote to {pulse_synth.OUT}")


if __name__ == "__main__":
    main()
