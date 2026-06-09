"""Transmission behavior tests."""

from freight_fate.sim.transmission import NEUTRAL, Transmission


def test_starts_in_neutral():
    tr = Transmission()
    assert tr.in_neutral
    assert tr.drive_ratio == 0.0


def test_manual_shift_requires_clutch():
    tr = Transmission()
    result = tr.request_gear(1)
    assert not result.ok
    assert result.grind
    tr.clutch = 1.0
    result = tr.request_gear(1)
    assert result.ok
    assert tr.gear == 1


def test_no_torque_path_while_clutch_pressed_or_shifting():
    tr = Transmission()
    tr.clutch = 1.0
    tr.request_gear(1)
    assert tr.drive_ratio == 0.0  # still shifting + clutch in
    tr.update(1.0)                # shift completes
    assert tr.drive_ratio == 0.0  # clutch still pressed
    tr.clutch = 0.0
    assert tr.drive_ratio > 0.0


def test_shift_to_neutral_never_needs_clutch():
    tr = Transmission()
    tr.clutch = 1.0
    tr.request_gear(3)
    tr.update(1.0)
    tr.clutch = 0.0
    result = tr.request_gear(NEUTRAL)
    assert result.ok
    assert tr.in_neutral


def test_invalid_gears_rejected():
    tr = Transmission()
    tr.clutch = 1.0
    assert not tr.request_gear(11).ok
    assert not tr.request_gear(-1).ok


def test_manual_rejected_in_automatic_mode():
    tr = Transmission(automatic=True)
    tr.clutch = 1.0
    assert not tr.request_gear(2).ok


def test_auto_upshifts_at_high_rpm():
    tr = Transmission(automatic=True, gear=3)
    assert tr.auto_update(1800, throttle=0.8, moving=True) == 4


def test_auto_downshifts_at_low_rpm():
    tr = Transmission(automatic=True, gear=5)
    assert tr.auto_update(900, throttle=0.1, moving=True) == 4


def test_auto_engages_first_from_neutral_on_throttle():
    tr = Transmission(automatic=True)
    assert tr.auto_update(600, throttle=0.5, moving=False) == 1


def test_auto_waits_for_shift_to_finish():
    tr = Transmission(automatic=True, gear=3)
    tr.auto_update(1800, 0.8, True)
    assert tr.shifting
    assert tr.auto_update(1800, 0.8, True) is None
    tr.update(1.0)
    assert not tr.shifting
