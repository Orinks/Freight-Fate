"""Cruise target stepping: plain steps snap to the fives, Ctrl steps by one.

Tester context (owner-approved design 2026-08-13): K captures the exact
current speed, so a cruise set at 32 used to step 37, 42 -- never landing
on the fives. Jerry latched the throttle and raced K to catch an even 35;
Sarah pointed at her dad's cruise stalk, which snaps. Plain steps now walk
the fives grid from wherever the target sits, and Ctrl with the same keys
moves by exactly one for the players who need a precise number.
"""

import pytest

from freight_fate.states.driving_core import (
    CRUISE_MAX_MPH,
    CRUISE_MIN_MPH,
    cruise_step_target,
)


def test_off_grid_snaps_up_to_the_next_five():
    assert cruise_step_target(32.0, 1, False) == pytest.approx(35.0)


def test_on_grid_steps_a_full_five_up():
    assert cruise_step_target(35.0, 1, False) == pytest.approx(40.0)


def test_off_grid_snaps_down_to_the_previous_five():
    assert cruise_step_target(32.0, -1, False) == pytest.approx(30.0)


def test_on_grid_steps_a_full_five_down():
    assert cruise_step_target(30.0, -1, False) == pytest.approx(25.0)


def test_float_fuzz_on_the_grid_still_moves_a_full_step():
    # A target that is 35 minus one part in a billion must behave as 35:
    # snapping it "up to 35" would be a no-op tap, the old complaint again.
    assert cruise_step_target(35.0 - 1e-9, 1, False) == pytest.approx(40.0)
    assert cruise_step_target(35.0 + 1e-9, -1, False) == pytest.approx(30.0)


def test_fine_steps_move_by_exactly_one():
    assert cruise_step_target(35.0, 1, True) == pytest.approx(36.0)
    assert cruise_step_target(35.0, -1, True) == pytest.approx(34.0)
    assert cruise_step_target(32.0, 1, True) == pytest.approx(33.0)


def test_both_step_kinds_clamp_to_the_bounds():
    assert cruise_step_target(CRUISE_MAX_MPH, 1, False) == pytest.approx(CRUISE_MAX_MPH)
    assert cruise_step_target(CRUISE_MAX_MPH, 1, True) == pytest.approx(CRUISE_MAX_MPH)
    assert cruise_step_target(CRUISE_MIN_MPH, -1, False) == pytest.approx(CRUISE_MIN_MPH)
    assert cruise_step_target(CRUISE_MIN_MPH, -1, True) == pytest.approx(CRUISE_MIN_MPH)
