"""Audition prototype v3: the jake at the operating points you actually hear.

Audition only -- imports nothing from freight_fate, touches no save data.
Builds on jake_v2.py in the same directory.

v2 compared the three stages at 1500 rpm, which is a real operating point but
an unusual one -- light braking, low revs, not much happening. Retarding POWER
goes as (active cylinders x RPM), so a jake does its useful work up around
1800-2100 rpm, and drivers downshift specifically to keep the revs there.
That is why the sound everyone knows is high-stage, high-rev, and punctuated
by shifts (Norm, 2026-07-18: "you always hear the jake down shifting").

The shift gaps matter as much as the buzz. A jake cuts out while the clutch is
in and resumes when the gear takes -- at a HIGHER rpm, because a lower gear
spins the engine faster at the same road speed. That interrupted, stair-
stepping pattern is the signature, more than any single steady tone is.

Usage: uv run python jake_v3.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pulse_synth
from jake_v2 import jake
from pulse_synth import SR, smoothstep, write_wav

pulse_synth.OUT = Path(__file__).resolve().parent


def seg(seconds: float, rpm_from: float, rpm_to: float) -> np.ndarray:
    t = np.linspace(0.0, 1.0, int(seconds * SR))
    return rpm_from + (rpm_to - rpm_from) * t


def decel_with_downshifts(stage: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Slowing on the jake, downshifting to hold the revs up.

    Each downshift is a short gap (clutch in, jake drops out) followed by a
    jump UP in rpm as the lower gear takes. Returns (rpm curve, gate).
    """
    parts, gates = [], []

    def run(seconds: float, a: float, b: float) -> None:
        parts.append(seg(seconds, a, b))
        gates.append(np.ones(int(seconds * SR)))

    def shift(seconds: float = 0.45) -> None:
        n = int(seconds * SR)
        parts.append(np.full(n, 1200.0))
        # Fast fade out, brief silence, fast fade back in.
        g = np.ones(n)
        g[: int(n * 0.25)] = np.linspace(1.0, 0.0, int(n * 0.25))
        g[int(n * 0.25) : int(n * 0.75)] = 0.0
        g[int(n * 0.75) :] = np.linspace(0.0, 1.0, n - int(n * 0.75))
        gates.append(g)

    run(2.2, 2050, 1320)   # jake pulling the revs down
    shift()
    run(2.0, 1880, 1280)   # downshifted, revs jumped back up
    shift()
    run(2.0, 1830, 1240)
    shift()
    run(1.8, 1760, 1350)
    return np.concatenate(parts), np.concatenate(gates)


def main() -> None:
    print("the classic: high stage, high revs")
    for rpm in (1900, 2100):
        write_wav(f"jake3_stage3_{rpm}rpm.wav", jake(np.full(int(3.0 * SR), rpm), stage=3))

    print("\nstage comparison at 2000 rpm (a REALISTIC operating point)")
    for stage in (1, 2, 3):
        write_wav(f"jake3_stage{stage}_2000rpm.wav",
                  jake(np.full(int(3.5 * SR), 2000.0), stage=stage))

    print("\nslowing on the jake, with downshifts -- the pattern you know")
    for stage in (1, 2, 3):
        rpm_curve, gate = decel_with_downshifts(stage)
        sig = jake(rpm_curve, stage=stage) * gate
        write_wav(f"jake3_decel_downshifts_stage{stage}.wav", sig)

    print("\nlong descent, holding a gear (steady, no shifts)")
    t = np.arange(int(8.0 * SR)) / SR
    # Speed creeping up against the jake, then settling as it takes hold.
    rpm_curve = 1750 + 260 * smoothstep(t / 3.0) - 120 * smoothstep((t - 4.0) / 4.0)
    write_wav("jake3_long_descent_stage3.wav", jake(rpm_curve, stage=3))

    print(f"\nwrote to {pulse_synth.OUT}")


if __name__ == "__main__":
    main()
