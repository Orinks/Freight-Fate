"""Transmission behavior tests."""

from freight_fate.sim.transmission import (
    AUTO_UPSHIFT_RPM,
    FINAL_DRIVE,
    GEAR_RATIOS,
    JAKE_MAX_RPM,
    JAKE_PRESELECT_RPM,
    NEUTRAL,
    REVERSE,
    Transmission,
)
from freight_fate.sim.vehicle import TruckSpecs


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
    tr.update(1.0)  # shift completes
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


def test_manual_reverse_requires_clutch():
    tr = Transmission()
    result = tr.request_gear(REVERSE)
    assert not result.ok
    assert result.grind
    tr.clutch = 1.0
    result = tr.request_gear(REVERSE)
    assert result.ok
    assert tr.in_reverse
    assert result.message == "reverse"
    tr.update(1.0)
    tr.clutch = 0.0
    assert tr.drive_ratio < 0.0


def test_invalid_gears_rejected():
    tr = Transmission()
    tr.clutch = 1.0
    assert not tr.request_gear(11).ok
    assert not tr.request_gear(-2).ok


def test_manual_rejected_in_automatic_mode():
    tr = Transmission(automatic=True)
    tr.clutch = 1.0
    assert not tr.request_gear(2).ok


def test_auto_upshifts_at_high_rpm():
    # The upshift point now comes from the caller (the vehicle passes its
    # progressive per-gear schedule); at exactly the threshold the box holds,
    # one RPM over it shifts.
    tr = Transmission(automatic=True, gear=3)
    assert (
        tr.auto_update(
            AUTO_UPSHIFT_RPM,
            throttle=0.8,
            moving=True,
            upshift_rpm=AUTO_UPSHIFT_RPM,
        )
        is None
    )
    assert (
        tr.auto_update(
            AUTO_UPSHIFT_RPM + 1,
            throttle=0.8,
            moving=True,
            upshift_rpm=AUTO_UPSHIFT_RPM,
        )
        == 4
    )


def test_auto_downshifts_at_low_rpm():
    tr = Transmission(automatic=True, gear=5)
    assert tr.auto_update(900, throttle=0.1, moving=True) == 4


def test_auto_holds_gear_while_braking_instead_of_upshifting():
    # High rpm would normally upshift, but braking from speed must not gear up.
    tr = Transmission(automatic=True, gear=5)
    assert tr.auto_update(1800, throttle=0.0, moving=True, braking=True) is None
    # Still allowed to downshift as the brake scrubs speed and rpm falls.
    assert tr.auto_update(900, throttle=0.0, moving=True, braking=True) == 4
    # Without braking the same high rpm still upshifts (default unchanged).
    tr = Transmission(automatic=True, gear=5)
    assert tr.auto_update(1800, throttle=0.8, moving=True) == 6


def test_engine_brake_preselects_down_and_holds_the_retard_band():
    # Below the retard band with the jake on: drop a gear to make it bite.
    tr = Transmission(automatic=True, gear=8)
    assert tr.auto_update(1400, throttle=0.0, moving=True, engine_braking=True) == 7
    tr.update(2.0)  # let the shift finish
    # In the band: hold the gear even though plain RPM rules would upshift.
    assert tr.auto_update(2000, throttle=0.0, moving=True, engine_braking=True) is None
    # Never preselect into a gear that would spin the engine past the ceiling.
    tr = Transmission(automatic=True, gear=7)
    rpm = JAKE_PRESELECT_RPM - 50
    assert rpm * GEAR_RATIOS[5] / GEAR_RATIOS[6] > JAKE_MAX_RPM
    assert tr.auto_update(rpm, throttle=0.0, moving=True, engine_braking=True) is None


def test_engine_protection_upshifts_past_the_rpm_ceiling():
    # The road spinning the engine past the ceiling beats the jake hold:
    # a real automatic protects its engine even mid-descent.
    tr = Transmission(automatic=True, gear=7)
    assert tr.auto_update(JAKE_MAX_RPM + 10, throttle=0.0, moving=True, engine_braking=True) == 8
    tr = Transmission(automatic=True, gear=7)
    assert tr.auto_update(JAKE_MAX_RPM + 10, throttle=0.0, moving=True, braking=True) == 8


def test_auto_engages_first_from_neutral_on_throttle():
    tr = Transmission(automatic=True)
    assert tr.auto_update(600, throttle=0.5, moving=False) == 1


def test_auto_drops_to_first_when_stopped_in_high_gear():
    # Regression: a collision can stop the truck while the box is still in a
    # high gear. The automatic must return to first instead of leaving the
    # engine to lug and stall on every restart (a soft-lock).
    tr = Transmission(automatic=True, gear=7)
    assert tr.auto_update(400, throttle=0.0, moving=False) == 1
    tr.update(1.0)
    assert tr.auto_update(600, throttle=0.0, moving=False) is None  # stays put


def test_auto_waits_for_shift_to_finish():
    tr = Transmission(automatic=True, gear=3)
    tr.auto_update(AUTO_UPSHIFT_RPM + 1, 0.8, True)
    assert tr.shifting
    assert tr.auto_update(1800, 0.8, True) is None
    tr.update(0.8)
    assert tr.shifting
    tr.update(0.3)
    assert not tr.shifting


def test_auto_respects_minimum_interval_between_shifts():
    tr = Transmission(automatic=True, gear=2)
    assert tr.auto_update(1800, 0.8, True, minimum_shift_interval_s=3.5) == 3
    tr.update(1.0)
    assert not tr.shifting
    assert tr.auto_update(1800, 0.8, True, minimum_shift_interval_s=3.5) is None
    tr.update(2.5)
    assert tr.auto_update(1800, 0.8, True, minimum_shift_interval_s=3.5) == 4


def test_auto_does_not_shift_out_of_reverse():
    tr = Transmission(automatic=True, gear=REVERSE)
    assert tr.auto_update(1900, throttle=0.5, moving=True) is None
    assert tr.in_reverse


def _rpm_at_speed_mph(speed_mph: float, gear: int) -> float:
    specs = TruckSpecs()
    meters_per_second = speed_mph / 2.23694
    wheel_rps = meters_per_second / (2 * 3.141592653589793 * specs.wheel_radius_m)
    return wheel_rps * 60.0 * GEAR_RATIOS[gear - 1] * FINAL_DRIVE


def test_upper_automatic_gears_are_not_reached_at_city_speed():
    # Regression for issue #15: the previous hybrid ratio set shifted from
    # 9th into 10th in the mid-40 mph range, making the upper gears feel
    # compressed. At 46 mph, 9th should still be below the upshift threshold.
    assert _rpm_at_speed_mph(46.0, 9) < AUTO_UPSHIFT_RPM
    assert _rpm_at_speed_mph(58.0, 9) >= AUTO_UPSHIFT_RPM


def test_top_gear_cruises_in_diesel_rpm_band():
    rpm = _rpm_at_speed_mph(60.0, 10)
    assert 1200 <= rpm <= 1500
