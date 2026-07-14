"""Career pacing model: how many real hours the 30-level arc takes.

Simulates a representative player against the *real* career math --
``Career.record_delivery``, the real ``LEVEL_XP`` thresholds, and the real
dispatch distance caps -- while modeling real-world time from the driving
simulation's clock compression (cruise speed under the default 10x
``time_scale``, plus menu/dock overhead and accelerated sleeper time on
multi-shift hauls).

This is the design contract for the months-long 1.9 career arc. The tests
in ``tests/test_career_pacing.py`` pin its bands; run it directly for the
full level-by-level table:

    uv run python tools/career_pacing.py
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from freight_fate.models.career import (  # noqa: E402
    XP_PREMIUM_MULT,
    XP_SPECIALTY_MULT,
    Career,
)
from freight_fate.models.jobs import JobBoard  # noqa: E402

# Real-time model: highway cruise under the default clock compression.
CRUISE_MPH = 60.0
TIME_SCALE = 10.0  # settings.py default
PARKED_TIME_SCALE_MULT = 2.0  # deliberate waiting runs the clock faster
MENU_OVERHEAD_REAL_H = 0.15  # dispatch board, pickup, dock work per delivery
SLEEP_GAME_H = 10.0
DRIVE_H_PER_SHIFT = 11.0

# Player model: a steady, competent driver, not a perfect one.
ON_TIME_RATE = 0.90
CLEAN_RATE = 0.80
SPECIALTY_RATE = 0.30  # share of runs on endorsement freight once unlocked
SENIOR_SPECIALTY_RATE = 0.45  # level 11+ boards weight endorsement freight up
PREMIUM_RATE = 0.30  # share of runs on premium mid-level freight


@dataclass(frozen=True)
class LevelCheckpoint:
    level: int
    deliveries: int
    real_hours: float
    xp: float


def _delivery_real_hours(miles: float) -> float:
    """Real minutes a haul costs: driving, dock time, and sleeper shifts."""
    drive_game_h = miles / CRUISE_MPH
    hours = drive_game_h / TIME_SCALE + MENU_OVERHEAD_REAL_H
    sleeps = int(drive_game_h / DRIVE_H_PER_SHIFT)
    hours += sleeps * SLEEP_GAME_H / (TIME_SCALE * PARKED_TIME_SCALE_MULT)
    return hours


def simulate_career(
    seed: int = 0,
    target_level: int = 30,
    max_deliveries: int = 20_000,
) -> list[LevelCheckpoint]:
    """Level-by-level checkpoints for one simulated career."""
    rng = random.Random(seed)
    career = Career()
    hours = 0.0
    deliveries = 0
    timeline = [LevelCheckpoint(1, 0, 0.0, 0.0)]
    while career.level < target_level and deliveries < max_deliveries:
        level = career.level
        cap = JobBoard.distance_cap(level)
        miles = max(60.0, min(rng.uniform(0.35, 0.95) * cap, 1_500.0))
        on_time = rng.random() < ON_TIME_RATE
        clean = rng.random() < CLEAN_RATE
        roll = rng.random()
        specialty_rate = SENIOR_SPECIALTY_RATE if level >= 11 else SPECIALTY_RATE
        if level >= 3 and roll < specialty_rate:
            mult = XP_SPECIALTY_MULT
        elif level >= 2 and roll < specialty_rate + PREMIUM_RATE:
            mult = XP_PREMIUM_MULT
        else:
            mult = 1.0
        career.record_delivery(
            miles,
            0.0,
            on_time,
            0.0 if clean else 30.0,
            cargo_class_mult=mult,
        )
        deliveries += 1
        hours += _delivery_real_hours(miles)
        while career.level > timeline[-1].level:
            timeline.append(LevelCheckpoint(timeline[-1].level + 1, deliveries, hours, career.xp))
    return timeline


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    timeline = simulate_career(seed=seed)
    print(f"Career pacing (seed {seed}): level / deliveries / real hours / xp")
    previous = 0.0
    for checkpoint in timeline:
        gap = checkpoint.real_hours - previous
        previous = checkpoint.real_hours
        print(
            f"  level {checkpoint.level:>2}  "
            f"{checkpoint.deliveries:>4} deliveries  "
            f"{checkpoint.real_hours:>7.1f} h total  "
            f"(+{gap:5.1f} h)  {checkpoint.xp:>9,.0f} xp"
        )
    total = timeline[-1].real_hours
    print(f"Total to level {timeline[-1].level}: {total:.0f} real wall-clock hours")
    print(f"At one hour per evening: about {total / 30.4:.1f} real-life months")
    print(f"At two and a half hours every day: about {total / (2.5 * 30.4):.1f} months")


if __name__ == "__main__":
    main()
