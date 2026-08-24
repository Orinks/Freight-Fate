"""The held-key tracker: driving must read a held arrow under JAWS.

JAWS swallows the physical arrow key and re-sends it to the game as an
instant press-and-release pair: one at the press, one at the Windows repeat
delay, then one per repeat at whatever spacing its script manages (about
250 ms on the owner's machine, measured 2026-08-24, not the 33 ms Windows
rate). A poll of ``pygame.key.get_pressed()`` never sees it held. The
tracker turns the train of pairs back into one hold, without changing what
the physical keyboard path (no screen reader, NVDA) reads.
"""

import pygame
from driving_feature_helpers import key_event, quiet_trip, release_air_brakes, start_drive

from freight_fate.held_keys import (
    FRESH_GRACE_MS,
    REPEAT_GRACE_MS,
    SYNTHETIC_FRAME_MAX_MS,
    HeldKeys,
    repeat_delay_ms,
    repeat_interval_ms,
)

FRAME_MS = 16  # 60 frames per second, as the game runs
DELAY_MS = 500  # the Windows default auto-repeat delay
INTERVAL_MS = 33  # ...and rate (about 30 per second)
# The owner's JAWS log, 2026-08-24: first repeat at 512 ms, then these.
JAWS_FIRST_REPEAT_MS = 512
JAWS_SPACINGS_MS = [263, 245, 269, 271, 242, 251, 270, 250, 244, 271, 249, 242, 254, 250]


class NoKeys:
    """SDL's view after a re-injected pair: nothing is down."""

    def __getitem__(self, key):
        return False


class Keys:
    def __init__(self, held=()):
        self.held = set(held)

    def __getitem__(self, key):
        return key in self.held


def down(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0)


def up(key):
    return pygame.event.Event(pygame.KEYUP, key=key, mod=0)


class Sim:
    """Advance the tracker frame by frame with a fake clock."""

    def __init__(self, tracker=None):
        self.tracker = tracker or HeldKeys(repeat_delay_ms=DELAY_MS, repeat_interval_ms=INTERVAL_MS)
        self.now = 1000
        self.tracker.begin_frame(self.now)

    def frame(self, *events, span=FRAME_MS):
        self.now += span
        self.tracker.begin_frame(self.now)
        for event in events:
            self.tracker.note(event)

    def held(self, key, pressed=None):
        return self.tracker.snapshot(pressed if pressed is not None else NoKeys())[key]

    def pair_times(self, start, seconds, first_repeat=DELAY_MS, spacings=(INTERVAL_MS,)):
        """When a screen reader re-sends pairs for a key held ``seconds``."""
        times = [start, start + first_repeat]
        i = 0
        while times[-1] < start + int(seconds * 1000):
            times.append(times[-1] + spacings[i % len(spacings)])
            i += 1
        return [t for t in times if t < start + int(seconds * 1000)]

    def screen_reader_hold(self, key, seconds, first_repeat=DELAY_MS, spacings=(INTERVAL_MS,)):
        """Deliver the pairs for a hold, frame by frame; return each frame's
        held reading from the first pair on."""
        pairs = self.pair_times(self.now, seconds, first_repeat, spacings)
        end = self.now + int(seconds * 1000)
        readings = []
        while self.now < end:
            events = ()
            if pairs and self.now >= pairs[0]:
                events = (down(key), up(key))
                pairs.pop(0)
            self.frame(*events)
            readings.append(self.held(key))
        return readings

    def frames_until_released(self, key, limit_ms=2000):
        start = self.now
        while self.held(key):
            self.frame()
            assert self.now - start <= limit_ms, (
                f"still held {self.now - start} ms after the pairs stopped"
            )
        return self.now - start


def test_physical_hold_still_reads_straight_from_sdl():
    sim = Sim()
    assert sim.held(pygame.K_UP, Keys({pygame.K_UP}))
    assert not sim.held(pygame.K_UP, Keys())
    assert not sim.held(pygame.K_DOWN, Keys({pygame.K_UP}))


def test_a_re_injected_pair_reads_held_until_the_first_repeat_would_come():
    sim = Sim()
    sim.frame(down(pygame.K_UP), up(pygame.K_UP))
    assert sim.held(pygame.K_UP)
    pressed_at = sim.now
    while sim.now < pressed_at + DELAY_MS:
        sim.frame()
        assert sim.held(pygame.K_UP), f"lapsed {sim.now - pressed_at} ms after the press"
    while sim.now < pressed_at + DELAY_MS + FRESH_GRACE_MS + FRAME_MS:
        sim.frame()
    assert not sim.held(pygame.K_UP)


def test_the_owners_jaws_train_is_one_continuous_hold_from_the_first_pair():
    """Replays the measured log: no learned spacing yet, 250 ms repeats."""
    sim = Sim()
    readings = sim.screen_reader_hold(pygame.K_UP, 4.0, JAWS_FIRST_REPEAT_MS, JAWS_SPACINGS_MS)
    assert all(readings), f"the hold broke at frame {readings.index(False)} of {len(readings)}"
    # Letting go reads late by one spacing plus grace: the price of a
    # screen reader that only re-sends the key four times a second.
    lag = sim.frames_until_released(pygame.K_UP)
    assert lag <= max(JAWS_SPACINGS_MS) + REPEAT_GRACE_MS + 2 * FRAME_MS
    # The fake clock delivers pairs on frame boundaries, so the learned
    # spacing can sit one frame off the nominal value.
    assert abs(sim.tracker.learned_spacing_ms - max(JAWS_SPACINGS_MS)) <= FRAME_MS
    # The next hold, on another key, starts with the spacing already known.
    readings = sim.screen_reader_hold(pygame.K_DOWN, 3.0, JAWS_FIRST_REPEAT_MS, JAWS_SPACINGS_MS)
    assert all(readings)
    assert (
        sim.frames_until_released(pygame.K_DOWN)
        <= max(JAWS_SPACINGS_MS) + REPEAT_GRACE_MS + 2 * FRAME_MS
    )


def test_a_fast_repeat_train_lapses_quickly_once_its_spacing_is_learned():
    sim = Sim()
    readings = sim.screen_reader_hold(pygame.K_UP, 2.0)
    assert all(readings), f"the hold broke at frame {readings.index(False)} of {len(readings)}"
    assert abs(sim.tracker.learned_spacing_ms - INTERVAL_MS) <= FRAME_MS
    assert sim.frames_until_released(pygame.K_UP) <= INTERVAL_MS + REPEAT_GRACE_MS + 3 * FRAME_MS
    # Once a hold has lapsed, a fresh press earns the full fresh pulse again.
    sim.frame(down(pygame.K_UP), up(pygame.K_UP))
    pressed_at = sim.now
    while sim.now < pressed_at + DELAY_MS:
        sim.frame()
        assert sim.held(pygame.K_UP)


def test_a_fingers_rhythm_never_teaches_the_repeat_spacing():
    # Real taps (release in a later frame) at a steady 200 ms: physical
    # keyboards never produce repeat pairs, so nothing is learned from them.
    sim = Sim()
    for _ in range(6):
        sim.frame(down(pygame.K_DOWN))
        for _ in range(3):
            sim.frame()
        sim.frame(up(pygame.K_DOWN))
        assert not sim.held(pygame.K_DOWN)
        for _ in range(8):
            sim.frame()
    assert sim.tracker.learned_spacing_ms is None
    assert sim.tracker.repeat_pulse_ms == sim.tracker.fresh_pulse_ms


def test_the_finger_lifting_ends_the_hold_at_once():
    sim = Sim()
    sim.frame(down(pygame.K_DOWN))
    for _ in range(5):
        sim.frame()
        assert sim.held(pygame.K_DOWN, Keys({pygame.K_DOWN}))
    sim.frame(up(pygame.K_DOWN))
    assert not sim.held(pygame.K_DOWN)


def test_a_pair_that_lands_after_a_hitch_is_not_a_hold():
    # A whole real tap can arrive in one batch after a long frame; the honest
    # answer is "not held", not a half-second of brake.
    sim = Sim()
    sim.frame(down(pygame.K_DOWN), up(pygame.K_DOWN), span=SYNTHETIC_FRAME_MAX_MS + 100)
    assert not sim.held(pygame.K_DOWN)


def test_a_second_tap_before_the_delay_is_a_fresh_press_not_a_repeat():
    sim = Sim()
    sim.frame(down(pygame.K_DOWN), up(pygame.K_DOWN))
    for _ in range(9):  # about 150 ms later: a double tap
        sim.frame()
    sim.frame(down(pygame.K_DOWN), up(pygame.K_DOWN))
    second_at = sim.now
    while sim.now < second_at + DELAY_MS:
        sim.frame()
        assert sim.held(pygame.K_DOWN)


def test_each_key_keeps_its_own_hold():
    sim = Sim()
    sim.frame(down(pygame.K_UP), up(pygame.K_UP))
    sim.frame(down(pygame.K_LEFT), up(pygame.K_LEFT))
    assert sim.held(pygame.K_UP) and sim.held(pygame.K_LEFT)
    assert not sim.held(pygame.K_RIGHT)
    sim.frame(up(pygame.K_UP))  # a later release: the finger, not the pair
    assert not sim.held(pygame.K_UP)
    assert sim.held(pygame.K_LEFT)


def test_clear_and_focus_loss_drop_every_pulse_but_keep_the_learning():
    sim = Sim()
    sim.screen_reader_hold(pygame.K_UP, 1.5, JAWS_FIRST_REPEAT_MS, JAWS_SPACINGS_MS)
    assert sim.tracker.learned_spacing_ms is not None
    sim.tracker.clear()
    assert not sim.held(pygame.K_UP)
    sim.frame(down(pygame.K_UP), up(pygame.K_UP))
    sim.frame(pygame.event.Event(pygame.WINDOWFOCUSLOST))
    assert not sim.held(pygame.K_UP)
    assert sim.tracker.learned_spacing_ms is not None


def test_windows_repeat_settings_decode_to_the_documented_timing():
    assert repeat_delay_ms(0) == 250
    assert repeat_delay_ms(1) == 500
    assert repeat_delay_ms(3) == 1000
    assert repeat_delay_ms(99) == 1000  # clamped, never a runaway pulse
    assert repeat_interval_ms(31) == 33
    assert repeat_interval_ms(0) == 400
    assert repeat_interval_ms(-5) == 400
    tracker = HeldKeys(repeat_delay_ms=1000, repeat_interval_ms=400)
    assert tracker.fresh_pulse_ms == 1000 + FRESH_GRACE_MS
    assert tracker.repeat_pulse_ms == tracker.fresh_pulse_ms  # nothing learned yet


def test_a_new_screen_never_inherits_the_last_screens_hold():
    from freight_fate.app import App
    from freight_fate.states.base import State

    app = App()
    try:
        app.held_keys.begin_frame(1000)
        app.held_keys.note(down(pygame.K_UP))
        app.held_keys.note(up(pygame.K_UP))
        assert app.ctx.held_keys.snapshot(NoKeys())[pygame.K_UP]
        app.push_state(State(app.ctx))
        assert not app.ctx.held_keys.snapshot(NoKeys())[pygame.K_UP]
        app.held_keys.note(down(pygame.K_UP))
        app.held_keys.note(up(pygame.K_UP))
        app.pop_state()
        assert not app.ctx.held_keys.snapshot(NoKeys())[pygame.K_UP]
    finally:
        app.shutdown()


def test_driving_reads_a_jaws_held_accelerator_as_steady_throttle(monkeypatch):
    """End to end, at the measured JAWS cadence: the pairs for a held Up
    arrow drive the truck, the throttle never stutters, and it comes off
    within a second of the pairs stopping."""
    from freight_fate.app import App

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: NoKeys())
    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        release_air_brakes(driving)
        driving.handle_event(key_event(pygame.K_e))  # engine on
        truck = driving.truck
        assert truck.throttle == 0.0
        sim = Sim(app.held_keys)
        pairs = sim.pair_times(sim.now, 4.0, JAWS_FIRST_REPEAT_MS, JAWS_SPACINGS_MS)
        end = sim.now + 4000
        lowest_after_full = 1.0
        reached_full = False
        while sim.now < end:
            events = ()
            if pairs and sim.now >= pairs[0]:
                events = (down(pygame.K_UP), up(pygame.K_UP))
                pairs.pop(0)
            sim.frame(*events)
            driving.update(FRAME_MS / 1000)
            if truck.throttle > 0.95:
                reached_full = True
            elif reached_full:
                lowest_after_full = min(lowest_after_full, truck.throttle)
        assert reached_full
        assert lowest_after_full >= 0.9, f"throttle stuttered down to {lowest_after_full:.2f}"
        # The finger lifts: the pairs stop, and the throttle comes off.
        for _ in range(60):
            sim.frame()
            driving.update(FRAME_MS / 1000)
        assert truck.throttle == 0.0
    finally:
        app.shutdown()
