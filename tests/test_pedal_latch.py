"""Latching pedals: double-tap-and-hold keeps a pedal applied hands-free.

Owner design 2026-07-15: tap, press again and hold about half a second, a
click and "Throttle latched." mark the catch. A fresh press of the same key
takes the pedal back; the opposite pedal and safety overrides release it
instantly. A bare double-tap must never latch -- players feather in taps.
"""

import pygame

from freight_fate.sim.pedal_latch import (
    CATCH_HOLD_S,
    GAP_MAX_S,
    TAP_MAX_S,
    PedalLatch,
)

DT = 1 / 60


def _run(latch, held, seconds):
    """Poll the latch at frame rate; return the events it emitted."""
    events = []
    t = 0.0
    while t < seconds:
        event = latch.update(held, DT)
        if event:
            events.append(event)
        t += DT
    return events


def test_double_tap_and_hold_latches():
    latch = PedalLatch()
    assert _run(latch, True, 0.2) == []  # tap
    assert _run(latch, False, 0.2) == []  # release
    events = _run(latch, True, CATCH_HOLD_S + 0.1)  # press and hold
    assert events == ["latched"]
    assert latch.latched
    # Releasing the key keeps the pedal latched: that is the whole point.
    assert _run(latch, False, 1.0) == []
    assert latch.latched


def test_bare_double_tap_never_latches():
    latch = PedalLatch()
    for _ in range(4):  # feathering: tap tap tap tap
        _run(latch, True, 0.15)
        _run(latch, False, 0.15)
    assert not latch.latched


def test_a_long_first_press_is_driving_not_a_gesture():
    latch = PedalLatch()
    _run(latch, True, 2.0)  # a plain sustained hold
    _run(latch, False, 0.1)
    events = _run(latch, True, 2.0)  # another plain hold, right after
    assert events == []
    assert not latch.latched


def test_a_slow_second_press_does_not_latch():
    latch = PedalLatch()
    _run(latch, True, 0.2)
    _run(latch, False, GAP_MAX_S + 0.2)  # too slow: the tap expired
    events = _run(latch, True, CATCH_HOLD_S + 0.5)
    assert events == []
    assert not latch.latched


def test_a_fresh_press_of_the_same_key_releases():
    latch = PedalLatch()
    _run(latch, True, 0.2)
    _run(latch, False, 0.2)
    _run(latch, True, CATCH_HOLD_S + 0.1)
    _run(latch, False, 1.0)
    assert latch.latched

    events = _run(latch, True, 0.1)
    assert events == ["released"]
    assert not latch.latched
    # The releasing press acts as the pedal itself; holding it through the
    # tap window must not start a new gesture from mid-press.
    events = _run(latch, True, CATCH_HOLD_S + 1.0)
    assert events == []
    assert not latch.latched


def test_outside_release_reports_only_a_real_drop():
    latch = PedalLatch()
    assert latch.release() is False
    _run(latch, True, 0.2)
    _run(latch, False, 0.2)
    _run(latch, True, CATCH_HOLD_S + 0.1)
    assert latch.latched
    assert latch.release() is True
    assert not latch.latched


def test_tap_gesture_constants_are_gentler_than_the_catch():
    # The catch must demand a deliberate hold, clearly longer than a tap,
    # or feathering players will latch by accident.
    assert CATCH_HOLD_S > TAP_MAX_S


def _drive_frames(driving, held, seconds):
    t = 0.0
    while t < seconds:
        driving.update(DT)
        t += DT


def test_latched_throttle_drives_the_truck_hands_free(monkeypatch):
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    class FakeKeys:
        def __init__(self, held):
            self.held = held

        def __getitem__(self, key):
            return key in self.held

    app = App()
    events = []
    played = []
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(
        app.ctx, "say_event", lambda text, interrupt=True: events.append(text)
    )
    monkeypatch.setattr(
        app.ctx.audio, "play", lambda key, volume=1.0: played.append(key)
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        release_air_brakes(driving)

        held.add(pygame.K_UP)
        _drive_frames(driving, held, 0.2)
        held.discard(pygame.K_UP)
        _drive_frames(driving, held, 0.2)
        held.add(pygame.K_UP)
        _drive_frames(driving, held, CATCH_HOLD_S + 0.2)
        assert "Throttle latched." in events
        assert "ui/tick" in played

        held.discard(pygame.K_UP)
        _drive_frames(driving, held, 1.0)
        assert driving.truck.throttle > 0.9  # hands off, pedal still down

        # The opposite pedal releases instantly, as it brakes.
        events.clear()
        held.add(pygame.K_DOWN)
        _drive_frames(driving, held, 0.2)
        assert "Throttle released." in events
        held.discard(pygame.K_DOWN)
        _drive_frames(driving, held, 1.0)
        assert driving.truck.throttle == 0.0
    finally:
        app.shutdown()


def test_latch_setting_off_keeps_pedals_plain(monkeypatch):
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    class FakeKeys:
        def __init__(self, held):
            self.held = held

        def __getitem__(self, key):
            return key in self.held

    app = App()
    events = []
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(
        app.ctx, "say_event", lambda text, interrupt=True: events.append(text)
    )
    try:
        app.ctx.settings.pedal_latch = False
        driving = start_drive(app)
        quiet_trip(driving)
        release_air_brakes(driving)

        held.add(pygame.K_UP)
        _drive_frames(driving, held, 0.2)
        held.discard(pygame.K_UP)
        _drive_frames(driving, held, 0.2)
        held.add(pygame.K_UP)
        _drive_frames(driving, held, CATCH_HOLD_S + 0.2)
        assert "Throttle latched." not in events

        held.discard(pygame.K_UP)
        _drive_frames(driving, held, 1.0)
        assert driving.truck.throttle == 0.0
    finally:
        app.shutdown()


def test_settings_menu_offers_latching_pedals():
    from freight_fate.states.main_menu import SettingsCategoryState

    fields = [field for field, _, _ in SettingsCategoryState._driving_assist_specs()]
    assert "pedal_latch" in fields


def test_catch_beats_the_direction_change_gesture():
    # Both gestures share the pedal keys at a standstill; the latch must
    # catch before a direction change can arm-and-fire, or latching the
    # brake at a stop would grab reverse a tenth of a second later.
    from freight_fate.states.driving import DIRECTION_CHANGE_HOLD_S

    assert CATCH_HOLD_S < DIRECTION_CHANGE_HOLD_S


def test_latching_the_brake_at_a_standstill_never_grabs_reverse(monkeypatch):
    """The latch gesture's second press is also a press-and-hold at a
    standstill -- the exact shape of the direction-change gesture. The
    catch must win: latching a pedal means "hold this", not "back up"."""
    from driving_feature_helpers import quiet_trip, release_air_brakes, start_drive

    from freight_fate.app import App

    class FakeKeys:
        def __init__(self, held):
            self.held = held

        def __getitem__(self, key):
            return key in self.held

    app = App()
    events = []
    held = set()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: FakeKeys(held))
    monkeypatch.setattr(
        app.ctx, "say_event", lambda text, interrupt=True: events.append(text)
    )
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        release_air_brakes(driving)
        assert driving.truck.transmission.automatic
        assert abs(driving.truck.velocity_mps) < 0.3  # parked at the yard

        held.add(pygame.K_DOWN)
        _drive_frames(driving, held, 0.2)
        held.discard(pygame.K_DOWN)
        _drive_frames(driving, held, 0.2)
        held.add(pygame.K_DOWN)
        _drive_frames(driving, held, 2.0)  # held well past both thresholds
        held.discard(pygame.K_DOWN)
        _drive_frames(driving, held, 1.0)

        assert "Brake latched." in events
        assert not driving.truck.transmission.in_reverse
        assert "Reverse selected. Backing slowly." not in events
    finally:
        app.shutdown()
