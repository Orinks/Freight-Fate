"""The held-key tracker: driving must read a held arrow under JAWS.

JAWS swallows the physical arrow key and re-sends it to the game as an
instant press-and-release pair, once per keyboard auto-repeat. A poll of
``pygame.key.get_pressed()`` never sees it held. The tracker turns the
train of pairs back into one hold, without changing what the physical
keyboard path (no screen reader, NVDA) reads.
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

    def jaws_hold(self, key, seconds):
        """What JAWS delivers for a key held ``seconds``: a pair now, then a
        pair per auto-repeat after the delay. Returns the frames it read held."""
        start = self.now
        end = start + int(seconds * 1000)
        next_pair = start
        held_frames = []
        while self.now < end:
            events = ()
            if self.now >= next_pair:
                events = (down(key), up(key))
                next_pair = (start + DELAY_MS) if next_pair == start else next_pair + INTERVAL_MS
            self.frame(*events)
            held_frames.append(self.held(key))
        return held_frames


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


def test_a_repeat_train_is_one_continuous_hold_that_lapses_quickly():
    sim = Sim()
    frames = sim.jaws_hold(pygame.K_UP, 2.0)
    assert all(frames), f"the hold broke at frame {frames.index(False)} of {len(frames)}"
    released_at = sim.now
    while sim.held(pygame.K_UP):
        sim.frame()
        assert sim.now - released_at <= INTERVAL_MS + REPEAT_GRACE_MS + 2 * FRAME_MS
    # Once a hold has lapsed, a fresh press earns the full fresh pulse again.
    sim.frame(down(pygame.K_UP), up(pygame.K_UP))
    pressed_at = sim.now
    while sim.now < pressed_at + DELAY_MS:
        sim.frame()
        assert sim.held(pygame.K_UP)


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


def test_clear_and_focus_loss_drop_every_pulse():
    sim = Sim()
    sim.frame(down(pygame.K_UP), up(pygame.K_UP))
    sim.tracker.clear()
    assert not sim.held(pygame.K_UP)
    sim.frame(down(pygame.K_UP), up(pygame.K_UP))
    sim.frame(pygame.event.Event(pygame.WINDOWFOCUSLOST))
    assert not sim.held(pygame.K_UP)


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
    assert tracker.repeat_pulse_ms == 400 + REPEAT_GRACE_MS


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


def test_driving_reads_a_jaws_held_accelerator_as_throttle(monkeypatch):
    """End to end: the pairs JAWS delivers for a held Up arrow drive the truck."""
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
        # A hold of two seconds, frame by frame through the real update.
        start = sim.now
        next_pair = start
        while sim.now < start + 2000:
            events = ()
            if sim.now >= next_pair:
                events = (down(pygame.K_UP), up(pygame.K_UP))
                next_pair = (start + DELAY_MS) if next_pair == start else next_pair + INTERVAL_MS
            sim.frame(*events)
            driving.update(FRAME_MS / 1000)
        assert truck.throttle > 0.9
        # The finger lifts: the pairs stop, and the throttle comes off within
        # a few frames instead of lingering.
        for _ in range(60):
            sim.frame()
            driving.update(FRAME_MS / 1000)
        assert truck.throttle == 0.0
    finally:
        app.shutdown()
