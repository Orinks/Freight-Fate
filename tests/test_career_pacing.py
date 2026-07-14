"""The 30-level arc is a months-long career with steady level-up pacing.

These tests drive the deterministic pacing model in ``tools/career_pacing.py``
against the real ``Career.record_delivery`` math, the real level thresholds,
and the real dispatch distance caps. They are the design contract for the
1.9 career arc:

- early levels land within a session or two, so a new driver feels motion;
- the whole ladder takes on the order of months of real evenings, not days;
- no single late level turns into a wall.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pacing():
    spec = importlib.util.spec_from_file_location(
        "career_pacing", ROOT / "tools" / "career_pacing.py"
    )
    module = importlib.util.module_from_spec(spec)
    # Registered before exec so the module's dataclasses can resolve their
    # own module during class creation.
    sys.modules["career_pacing"] = module
    spec.loader.exec_module(module)
    return module


def _timeline():
    return _pacing().simulate_career(seed=42)


def test_simulation_reaches_the_top_of_the_ladder():
    timeline = _timeline()
    assert timeline[-1].level == 30
    levels = [checkpoint.level for checkpoint in timeline]
    assert levels == list(range(1, 31))
    hours = [checkpoint.real_hours for checkpoint in timeline]
    assert hours == sorted(hours)


def test_the_first_session_already_levels_up():
    timeline = _timeline()
    by_level = {checkpoint.level: checkpoint for checkpoint in timeline}
    assert by_level[2].real_hours <= 2.0
    assert by_level[3].real_hours <= 5.0


def test_the_early_arc_moves_and_the_whole_arc_takes_months():
    timeline = _timeline()
    by_level = {checkpoint.level: checkpoint for checkpoint in timeline}
    # Load choice (8) lands inside the first stretch of evenings.
    assert 8.0 <= by_level[8].real_hours <= 30.0
    # The owner-operator gate (18) is a real investment.
    assert 70.0 <= by_level[18].real_hours <= 170.0
    # Level 30 lands after months of real play (roughly five months at two
    # hours a night, eleven at one), but not so far out nobody sees it.
    assert 220.0 <= by_level[30].real_hours <= 400.0


def test_no_late_level_becomes_a_wall():
    timeline = _timeline()
    by_level = {checkpoint.level: checkpoint for checkpoint in timeline}
    for level in range(21, 31):
        gap = by_level[level].real_hours - by_level[level - 1].real_hours
        assert 1.0 <= gap <= 25.0, f"level {level} took {gap:.1f} hours"


def test_pacing_holds_across_seeds():
    pacing = _pacing()
    for seed in (1, 7, 99):
        timeline = pacing.simulate_career(seed=seed)
        by_level = {checkpoint.level: checkpoint for checkpoint in timeline}
        assert 220.0 <= by_level[30].real_hours <= 420.0
        assert by_level[18].real_hours >= 60.0
