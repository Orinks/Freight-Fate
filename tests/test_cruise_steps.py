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


def _cruise_at(driving, mph):
    driving.truck.engine_on = True
    driving.truck.velocity_mps = mph / 2.2369362920544
    driving._engage_cruise(mph)


def test_plus_key_snaps_an_off_grid_cruise_target(monkeypatch):
    import pygame
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive
    from speech_capture import speech_stub

    from freight_fate.app import App

    app = App()
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx, "say_event", speech_stub())
        _cruise_at(d, 32.0)

        d.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_EQUALS, mod=0, unicode="="))
        assert d._cruise_mph == pytest.approx(35.0)
        d.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_EQUALS, mod=0, unicode="="))
        assert d._cruise_mph == pytest.approx(40.0)
    finally:
        app.shutdown()


def test_ctrl_plus_and_minus_step_by_one(monkeypatch):
    import pygame
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive
    from speech_capture import speech_stub

    from freight_fate.app import App

    app = App()
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx, "say_event", speech_stub())
        _cruise_at(d, 35.0)

        d.handle_event(
            pygame.event.Event(
                pygame.KEYDOWN, key=pygame.K_EQUALS, mod=pygame.KMOD_CTRL, unicode=""
            )
        )
        assert d._cruise_mph == pytest.approx(36.0)
        d.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_MINUS, mod=pygame.KMOD_CTRL, unicode="")
        )
        assert d._cruise_mph == pytest.approx(35.0)
    finally:
        app.shutdown()


def test_keeper_zone_adjust_snaps_the_resume_target(monkeypatch):
    """The speed keeper owns a restricted zone, but +/- still steps the
    remembered open-road target that adaptive cruise resumes to -- and must
    not disturb the keeper's own held speed while it does."""
    import pygame
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive
    from speech_capture import speech_stub

    from freight_fate.app import App
    from freight_fate.sim.trip_models import Zone

    app = App()
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx, "say_event", speech_stub())
        d.truck.engine_on = True
        start = d.trip.position_mi
        d.trip.zones.append(Zone(start - 0.1, start + 3.0, 25.0, "school"))
        d.truck.velocity_mps = 25.0 / 2.2369362920544
        d._engage_keeper(25.0, "school", target_mph=25.0, announce=False)
        keeper_before = d._keeper_mph
        d._speed_control_target_mph = 62.0

        d.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_EQUALS, mod=0, unicode="="))

        assert d._speed_control_target_mph == pytest.approx(65.0)
        assert d._keeper_mph == pytest.approx(keeper_before)
    finally:
        app.shutdown()


def test_keeper_raw_capture_rounds_to_the_whole_mph(monkeypatch):
    """_engage_keeper's plain K-set branch (no explicit target_mph) rounds the
    captured speed to the whole mph the player hears, mirroring
    _engage_cruise's rounding -- otherwise an unrounded 24.95 would spend the
    first snap tap healing an invisible fraction instead of making an
    audible step."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive
    from speech_capture import speech_stub

    from freight_fate.app import App
    from freight_fate.sim.trip_models import Zone

    app = App()
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx, "say_event", speech_stub())
        d.truck.engine_on = True
        start = d.trip.position_mi
        d.trip.zones.append(Zone(start - 0.1, start + 3.0, 30.0, "school"))
        d.truck.velocity_mps = 24.95 / 2.2369362920544  # off the whole mph

        d._engage_keeper(30.0, "school", announce=False)

        assert d._keeper_mph == pytest.approx(25.0)
    finally:
        app.shutdown()


def test_high_idle_still_owns_the_keys_when_parked(monkeypatch):
    """Parked with a latched high idle, +/- steps the idle RPM, not any
    cruise or keeper target -- the branch _adjust_cruise checks first."""
    import pygame
    from driving_feature_helpers import quiet_trip, start_drive
    from speech_capture import speech_stub

    from freight_fate.app import App
    from freight_fate.sim.vehicle import HIGH_IDLE_DEFAULT_RPM, HIGH_IDLE_STEP_RPM

    app = App()
    try:
        d = start_drive(app)
        quiet_trip(d)
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx, "say_event", speech_stub())
        t = d.truck
        t.set_air_ready(parking_brake=True)
        t.start_engine()
        t.velocity_mps = 0.0
        t.high_idle_rpm = HIGH_IDLE_DEFAULT_RPM

        d.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_EQUALS, mod=0, unicode="="))

        assert t.high_idle_rpm == pytest.approx(HIGH_IDLE_DEFAULT_RPM + HIGH_IDLE_STEP_RPM)
        assert d._cruise_mph is None
        assert d._speed_control_target_mph is None
    finally:
        app.shutdown()


def test_engaging_cruise_rounds_to_the_speed_the_player_hears(monkeypatch):
    """Regression (found in Task 3 verification, 2026-08-13): _engage_cruise
    used to store the truck's raw unrounded speed (26.8 m/s -> 59.949992
    mph), a fraction the player never hears -- speed_text already rounds the
    readout to a clean "sixty". The first plain plus tap then spent itself
    healing that invisible fraction onto the grid (59.95 -> 60) instead of
    making an audible step, the exact no-op complaint this feature exists to
    kill. The captured target must already be the whole number the player
    heard when it engaged."""
    import pygame
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive
    from speech_capture import speech_stub

    from freight_fate.app import App

    app = App()
    try:
        d = start_drive(app)
        quiet_trip(d)
        release_air_brakes(d)
        monkeypatch.setattr(app.ctx, "say", speech_stub())
        monkeypatch.setattr(app.ctx, "say_event", speech_stub())
        d.truck.engine_on = True
        d.truck.velocity_mps = 26.8  # -> 59.949992 mph, off the fives grid
        d._engage_cruise(d.truck.speed_mph)
        assert d._cruise_mph == pytest.approx(60.0)

        d.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_EQUALS, mod=0, unicode="="))

        assert d._cruise_mph == pytest.approx(65.0)
    finally:
        app.shutdown()
