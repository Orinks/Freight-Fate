"""Speech history walk-back: quick repeat presses step back through the ring.

Owner design 2026-07-15: the comma key must reach more than the newest line.
First press repeats what just spoke; pressing again within a few seconds
walks one line older per press; a fresh announcement snaps back to newest.
"""

import pygame
from driving_feature_helpers import key_event, quiet_trip, start_drive
from speech_capture import speech_stub

from freight_fate.speech import SpeechHistory


class _Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def _walked(history):
    step = history.step_back()
    assert step is not None
    return step


def test_first_press_speaks_the_newest_line():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    h.record("Fuel 62 gallons.")
    h.record("Safe speed 45.")

    assert _walked(h) == (0, "Safe speed 45.")


def test_quick_presses_walk_one_line_older_each():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    for line in ("first", "second", "third"):
        h.record(line)

    assert _walked(h) == (0, "third")
    clock.now += 2.0
    assert _walked(h) == (1, "second")
    clock.now += 2.0
    assert _walked(h) == (2, "first")


def test_walk_clamps_at_the_oldest_line():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    h.record("only line")

    assert _walked(h) == (0, "only line")
    clock.now += 1.0
    assert _walked(h) == (0, "only line")


def test_a_pause_longer_than_the_window_snaps_back_to_newest():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    for line in ("first", "second", "third"):
        h.record(line)
    assert _walked(h) == (0, "third")
    clock.now += 2.0
    assert _walked(h) == (1, "second")

    clock.now += SpeechHistory.STEP_WINDOW_S + 0.1
    assert _walked(h) == (0, "third")


def test_a_fresh_announcement_resets_the_walk():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    h.record("first")
    h.record("second")
    assert _walked(h) == (0, "second")
    clock.now += 1.0
    assert _walked(h) == (1, "first")

    h.record("breaking news")
    clock.now += 1.0
    assert _walked(h) == (0, "breaking news")


def test_consecutive_duplicates_collapse():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    h.record("older line")
    for _ in range(5):
        h.record("Cruise set, 55.")

    assert _walked(h) == (0, "Cruise set, 55.")
    clock.now += 1.0
    assert _walked(h) == (1, "older line")


def test_ring_keeps_only_the_newest_lines():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    for i in range(SpeechHistory.KEPT + 5):
        h.record(f"line {i}")

    seen = []
    step = h.step_back()
    while step is not None:
        back, line = step
        if seen and back == seen[-1][0]:
            break  # clamped at the oldest
        seen.append((back, line))
        clock.now += 1.0
        step = h.step_back()
    assert len(seen) == SpeechHistory.KEPT
    assert seen[0][1] == f"line {SpeechHistory.KEPT + 4}"
    assert seen[-1][1] == "line 5"


def test_empty_history_returns_none():
    h = SpeechHistory(clock=_Clock())
    assert h.step_back() is None


def test_comma_walks_back_through_game_and_event_speech():
    """End to end: both channels land in one ring, and older lines speak
    with a spoken "N back:" position so the player knows where they are."""
    from freight_fate.app import App

    app = App()
    try:
        spoken = []
        app.ctx.speech.say = speech_stub(spoken)
        app.ctx.settings.sapi_events = False

        app.ctx.say("Fuel 62 gallons.")
        app.ctx.say_event("Crossing the Agua Fria River.")
        del spoken[:]

        app.ctx.repeat_last_spoken()
        assert spoken[-1] == "Crossing the Agua Fria River."
        app.ctx.repeat_last_spoken()
        assert spoken[-1] == "1 back: Fuel 62 gallons."
        app.ctx.repeat_last_spoken()
        assert spoken[-1] == "1 back: Fuel 62 gallons."

        # A fresh line ends the walk: the next press repeats it plainly.
        app.ctx.say("Chains are on.")
        app.ctx.repeat_last_spoken()
        assert spoken[-1] == "Chains are on."
    finally:
        app.shutdown()


def test_period_steps_forward_toward_the_newest_line():
    # Comma older, period newer -- the Civilization VI pairing (owner
    # report 2026-07-23: period did nothing).
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    h.record("Fuel 62 gallons.")
    h.record("Safe speed 45.")
    h.record("Next exit 2 miles.")
    h.step_back()  # newest
    h.step_back()  # 1 back
    h.step_back()  # 2 back
    assert h.step_forward() == (1, "Safe speed 45.")
    assert h.step_forward() == (0, "Next exit 2 miles.")
    # At the newest line, period stays put instead of wrapping.
    assert h.step_forward() == (0, "Next exit 2 miles.")


def test_period_out_of_the_blue_answers_with_the_newest_line():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    h.record("Fuel 62 gallons.")
    h.record("Safe speed 45.")
    assert h.step_forward() == (0, "Safe speed 45.")


def test_period_after_the_window_snaps_to_newest():
    clock = _Clock()
    h = SpeechHistory(clock=clock)
    h.record("Fuel 62 gallons.")
    h.record("Safe speed 45.")
    h.step_back()
    h.step_back()  # 1 back, mid-walk
    clock.now += SpeechHistory.STEP_WINDOW_S + 1
    assert h.step_forward() == (0, "Safe speed 45.")


def test_hazard_warning_and_outcome_replay_on_a_comma_and_period(monkeypatch):
    """Both established review paths retain the warning and its resolution."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind
    from freight_fate.states.driving_core import HAZARD_SAFE_MPH

    app = App()
    main_speech = []
    monkeypatch.setattr(
        app.ctx.speech, "say", lambda text, interrupt=True: main_speech.append(text)
    )
    monkeypatch.setattr(app.ctx.speech, "say_event", lambda text, interrupt=True: None)
    monkeypatch.setattr(app.ctx, "award_achievement", lambda *args, **kwargs: None)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        warning = "Brake now! A slow vehicle ahead."
        outcome = "Hazard avoided. Well done."
        driving._handle_trip_event(TripEvent(TripEventKind.HAZARD, warning, {"deadline_s": 3.0}))

        driving.handle_event(key_event(pygame.K_a))
        assert main_speech[-1] == warning
        app.ctx.repeat_last_spoken()
        assert main_speech[-1] == warning

        driving.truck.velocity_mps = (HAZARD_SAFE_MPH - 1.0) / 2.2369362920544
        driving._update_hazard(1 / 60)

        driving.handle_event(key_event(pygame.K_a))
        assert main_speech[-1] == outcome
        app.ctx.repeat_last_spoken()
        assert main_speech[-1] == outcome
        app.ctx.repeat_last_spoken()
        assert main_speech[-1] == f"1 back: {warning}"
        app.ctx.step_forward_spoken()
        assert main_speech[-1] == outcome
    finally:
        app.shutdown()


def test_collision_outcome_replays_on_a_and_speech_history(monkeypatch):
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    main_speech = []
    monkeypatch.setattr(
        app.ctx.speech, "say", lambda text, interrupt=True: main_speech.append(text)
    )
    monkeypatch.setattr(app.ctx.speech, "say_event", lambda text, interrupt=True: None)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        warning = "Brake now! Debris on the road."
        driving._handle_trip_event(TripEvent(TripEventKind.HAZARD, warning, {"deadline_s": 0.0}))
        driving.truck.velocity_mps = 40.0 / 2.2369362920544
        driving._hazard_deadline = 0.0
        driving._update_hazard(1 / 60)
        outcome = f"Collision! The truck took damage. Total damage {driving.truck.damage_pct:.0f} percent."

        driving.handle_event(key_event(pygame.K_a))
        assert main_speech[-1] == outcome
        app.ctx.repeat_last_spoken()
        assert main_speech[-1] == outcome
        app.ctx.repeat_last_spoken()
        assert main_speech[-1] == f"1 back: {warning}"
    finally:
        app.shutdown()


def test_name_entry_keeps_punctuation_for_driver_names():
    from freight_fate.app import App
    from freight_fate.states.main_menu import NameEntryState

    app = App()
    try:
        state = NameEntryState(app.ctx)
        assert state.captures_text_input
        state.handle_event(key_event(pygame.K_COMMA, ","))
        state.handle_event(key_event(pygame.K_PERIOD, "."))
        assert state.name == ",."
    finally:
        app.shutdown()


def test_review_replay_stops_the_event_voice(monkeypatch):
    from freight_fate.app import App

    app = App()
    stopped = []
    monkeypatch.setattr(app.ctx, "stop_event_speech", lambda: stopped.append(True))
    monkeypatch.setattr(app.ctx.speech, "say", lambda text, interrupt=True: None)
    try:
        app.ctx.say_event("Hazard warning.")
        app.ctx.repeat_last_spoken()
        assert stopped == [True]
    finally:
        app.shutdown()


def test_a_replay_stops_the_event_voice(monkeypatch):
    from freight_fate.app import App

    app = App()
    stopped = []
    monkeypatch.setattr(app.ctx, "stop_event_speech", lambda: stopped.append(True))
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True: None)
    try:
        driving = start_drive(app)
        driving._last_event_message = "Hazard warning."
        driving.handle_event(key_event(pygame.K_a))
        assert stopped == [True]
    finally:
        app.shutdown()
