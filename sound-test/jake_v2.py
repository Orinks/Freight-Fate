"""Audition prototype v2: the jake, per-cylinder instead of a uniform buzz.

Scratchpad/audition only -- imports nothing from freight_fate, touches no
save data. Builds on pulse_synth.py in the same directory.

v1 modelled all six cylinders as identical and evenly spaced, which by
construction gives a dead-steady grrrrrrr. Two things make a real jake lope
instead (Norm, 2026-07-18: "grrgrrgrrgrr, not grrrrrrr"):

1. The cycle is 720 degrees, not 360. The six releases form a repeating
   GROUP of six, and per-cylinder differences in valve lash, compression and
   exhaust path length to the collector make them unequal -- so the
   amplitude pattern repeats at half-order, RPM/120 Hz. 12.5 Hz at 1500 rpm.
2. A three-stage brake on an inline-six runs 2, 4 or 6 cylinders. On the low
   stage most cylinders stay silent, so the pops come in a cluster and then
   a GAP every two revolutions. That is a far stronger lope than per-cylinder
   trim alone, and it is the sound of a low brake setting.

Firing order 1-5-3-6-2-4 is standard for an inline-six. WHICH cylinders a
partial stage uses is a guess here (grouped by housing, in pairs) -- the
staging concept and the 2/4/6 counts are real, the specific grouping is not
claimed to be verified.

Usage: uv run python jake_v2.py
"""

from __future__ import annotations

import numpy as np
from pulse_synth import (
    AIR_RUSH,
    OUT,
    SR,
    bank_ir,
    convolve,
    grain,
    pulse_train,
    smoothstep,
    write_wav,
)

FIRING_ORDER = [1, 5, 3, 6, 2, 4]

# Per-cylinder character. Trim is amplitude, skew detunes that cylinder's
# stack resonance slightly -- different runner length to the collector, so a
# marginally different pipe. Fixed (not random per run) so the lope is a
# stable property of the engine rather than noise.
CYLINDER_TRIM = {1: 1.00, 2: 0.86, 3: 1.09, 4: 0.81, 5: 0.97, 6: 1.14}
CYLINDER_SKEW = {1: 1.000, 2: 0.978, 3: 1.031, 4: 0.964, 5: 1.012, 6: 1.045}

# Which cylinders brake at each stage, grouped in pairs by housing.
STAGES = {
    1: [1, 2],
    2: [1, 2, 5, 6],
    3: [1, 2, 3, 4, 5, 6],
}

STACK = [
    (95.0, 0.055, 1.00),
    (185.0, 0.040, 0.70),
    (430.0, 0.022, 0.45),
    (900.0, 0.014, 0.28),
    (1750.0, 0.008, 0.15),
]


def stack_ir(skew: float) -> np.ndarray:
    return bank_ir([(f * skew, d, g) for f, d, g in STACK])


def jake(rpm_curve: np.ndarray, stage: int = 3, wobble: float = 0.06) -> np.ndarray:
    """Sum one pulse train per braking cylinder.

    Each cylinder releases once per 720 degrees, i.e. at RPM/120 Hz, offset
    from its neighbours by a sixth of the cycle in firing order. With all six
    active that recombines into the familiar RPM/20 buzz -- but now with the
    half-order amplitude pattern riding on it, because the six contributions
    are no longer identical.
    """
    n = len(rpm_curve)
    cycle_rate = rpm_curve / 120.0  # one full four-stroke cycle
    active = STAGES[stage]
    out = np.zeros(n)
    for slot, cyl in enumerate(FIRING_ORDER):
        if cyl not in active:
            continue
        phase0 = slot / 6.0
        # Cycle-to-cycle unsteadiness: air and lash vary a little every turn.
        amp = CYLINDER_TRIM[cyl] * (1.0 + wobble * np.sin(2 * np.pi * 0.7 * np.arange(n) / SR))
        pops = convolve(pulse_train(cycle_rate, amp, phase0=phase0), stack_ir(CYLINDER_SKEW[cyl]))
        air = convolve(pulse_train(cycle_rate, 0.55 * amp, phase0=phase0), grain(0.004))
        out += pops + 0.35 * convolve(air, bank_ir(AIR_RUSH))
    return out


def steady(rpm: float, seconds: float, stage: int = 3) -> np.ndarray:
    return jake(np.full(int(seconds * SR), rpm), stage=stage)


def engage(rpm: float = 1900.0, seconds: float = 4.5, stage: int = 3) -> np.ndarray:
    """Clatter in, then the buzz sliding down as the truck slows."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    rpm_curve = rpm - (rpm - 1150.0) * smoothstep(t / seconds)
    sig = jake(rpm_curve, stage=stage) * np.minimum(1.0, t / 0.05)
    clatter = np.zeros(n)
    for onset, gain in ((0.0, 1.0), (0.018, 0.6), (0.041, 0.35)):
        i = int(onset * SR)
        ir = bank_ir([(320.0, 0.012, 1.0), (1400.0, 0.006, 0.7)])
        clatter[i : i + len(ir)] += gain * ir[: n - i]
    return sig + 0.8 * clatter


def main() -> None:
    print("jake v2 -- stage comparison at 1500 rpm (half-order lope = 12.5 Hz)")
    for stage in (1, 2, 3):
        write_wav(f"jake2_stage{stage}_1500rpm.wav", steady(1500, 3.5, stage))

    print("\njake v2 -- full stage 3 across the range")
    for rpm in (1200, 1500, 1800, 2100):
        write_wav(f"jake2_stage3_{rpm}rpm_{rpm / 20:.0f}hz.wav", steady(rpm, 3.0, 3))

    print("\njake v2 -- low stage across the range (the loping one)")
    for rpm in (1200, 1500, 1800):
        write_wav(f"jake2_stage1_{rpm}rpm.wav", steady(rpm, 3.0, 1))

    print("\njake v2 -- engagement sweeps")
    write_wav("jake2_engage_stage3.wav", engage(stage=3))
    write_wav("jake2_engage_stage1.wav", engage(stage=1))

    print("\nexaggerated cylinder spread (is more lope better?)")
    saved = dict(CYLINDER_TRIM)
    for cyl, trim in ((2, 0.65), (4, 0.58), (6, 1.30), (3, 1.22)):
        CYLINDER_TRIM[cyl] = trim
    write_wav("jake2_stage3_1500rpm_rough.wav", steady(1500, 3.5, 3))
    CYLINDER_TRIM.update(saved)

    print(f"\nwrote to {OUT}")


if __name__ == "__main__":
    main()
