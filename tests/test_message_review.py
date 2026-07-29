"""Regression coverage for the speech-review controls.

These drive ``App.dispatch_to_state``, the one place key events reach a state,
so they cover the wiring a player actually presses rather than the log in
isolation -- ``tests/test_message_log.py`` covers the log itself.
"""

import pygame
from driving_feature_helpers import key_event, quiet_trip, start_drive


def ctrl_key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=pygame.KMOD_LCTRL)


def test_hazard_warning_and_outcome_replay_on_a_comma_and_period(monkeypatch):
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

        app.dispatch_to_state(key_event(pygame.K_a))
        assert main_speech[-1] == warning
        app.dispatch_to_state(key_event(pygame.K_COMMA))
        assert main_speech[-1] == warning

        driving.truck.velocity_mps = (HAZARD_SAFE_MPH - 1.0) / 2.2369362920544
        driving._update_hazard(1 / 60)

        app.dispatch_to_state(key_event(pygame.K_a))
        assert main_speech[-1] == outcome
        app.dispatch_to_state(key_event(pygame.K_COMMA))
        assert main_speech[-1] == outcome
        app.dispatch_to_state(key_event(pygame.K_COMMA))
        assert main_speech[-1] == f"1 back: {warning}"
        app.dispatch_to_state(key_event(pygame.K_PERIOD))
        assert main_speech[-1] == outcome
    finally:
        app.shutdown()


def test_collision_outcome_replays_on_a_and_message_review(monkeypatch):
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

        app.dispatch_to_state(key_event(pygame.K_a))
        assert main_speech[-1] == outcome
        app.dispatch_to_state(key_event(pygame.K_COMMA))
        assert main_speech[-1] == outcome
        app.dispatch_to_state(key_event(pygame.K_COMMA))
        assert main_speech[-1] == f"1 back: {warning}"
    finally:
        app.shutdown()


def test_name_entry_keeps_punctuation_for_driver_names():
    from freight_fate.app import App
    from freight_fate.states.main_menu import NameEntryState

    app = App()
    try:
        state = NameEntryState(app.ctx)
        app.push_state(state)
        assert state.captures_text_input
        app.dispatch_to_state(key_event(pygame.K_COMMA, ","))
        app.dispatch_to_state(key_event(pygame.K_PERIOD, "."))
        assert state.name == ",."
    finally:
        app.shutdown()


def test_review_works_outside_driving(monkeypatch):
    """The old review path was wired into the driving state alone."""
    from freight_fate.app import App
    from freight_fate.states.main_menu import MainMenuState

    app = App()
    main_speech = []
    try:
        app.push_state(MainMenuState(app.ctx))
        app.ctx.say("Fuel is running low.")
        app.ctx.say("Weigh station ahead.")
        monkeypatch.setattr(
            app.ctx.speech, "say", lambda text, interrupt=True: main_speech.append(text)
        )

        app.dispatch_to_state(key_event(pygame.K_COMMA))
        assert main_speech[-1] == "Weigh station ahead."
        app.dispatch_to_state(key_event(pygame.K_COMMA))
        assert main_speech[-1] == "1 back: Fuel is running low."
    finally:
        app.shutdown()


def test_menu_navigation_stays_out_of_the_review_log():
    from freight_fate.app import App
    from freight_fate.states.main_menu import MainMenuState

    app = App()
    try:
        app.push_state(MainMenuState(app.ctx))
        app.ctx.say("Fuel is running low.")
        app.dispatch_to_state(key_event(pygame.K_DOWN))
        app.dispatch_to_state(key_event(pygame.K_DOWN))

        texts = [message.text for message in app.ctx.message_log.messages]
        assert texts[-1] == "Fuel is running low."
    finally:
        app.shutdown()


def test_pausing_mid_run_leaves_no_trace_in_the_history():
    """Checking the pause menu is where you are, not something that happened."""
    from freight_fate.app import App
    from freight_fate.sim.trip import TripEvent, TripEventKind

    app = App()
    monkeypatch_free_speech(app)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        app.ctx.message_log.messages.clear()
        app.ctx.message_log.index = -1

        for index in range(3):
            driving._handle_trip_event(
                TripEvent(TripEventKind.HAZARD, f"Announcement {index}.", {"deadline_s": 9.0})
            )
            driving._hazard_active = False
            app.dispatch_to_state(key_event(pygame.K_ESCAPE))  # open the pause menu
            app.dispatch_to_state(key_event(pygame.K_RETURN))  # resume

        assert [message.text for message in app.ctx.message_log.messages] == [
            "Announcement 0.",
            "Announcement 1.",
            "Announcement 2.",
        ]
    finally:
        app.shutdown()


def monkeypatch_free_speech(app):
    app.ctx.speech.say = lambda text, interrupt=True: None
    app.ctx.speech.say_event = lambda text, interrupt=True: None
    app.ctx.award_achievement = lambda *args, **kwargs: None


def test_review_jumps_to_first_and_last(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.base import State

    app = App()
    main_speech = []
    try:
        # A bare state speaks nothing on entry, so the log holds only what this
        # test puts in it and the "N back" counts are exact.
        app.push_state(State(app.ctx))
        for text in ("One.", "Two.", "Three."):
            app.ctx.say(text)
        monkeypatch.setattr(
            app.ctx.speech, "say", lambda text, interrupt=True: main_speech.append(text)
        )

        app.dispatch_to_state(ctrl_key_event(pygame.K_COMMA))
        assert main_speech[-1] == "2 back: One."
        app.dispatch_to_state(ctrl_key_event(pygame.K_PERIOD))
        assert main_speech[-1] == "Three."
    finally:
        app.shutdown()


def test_review_replay_stops_the_event_voice(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.main_menu import MainMenuState

    app = App()
    stopped = []
    try:
        app.push_state(MainMenuState(app.ctx))
        monkeypatch.setattr(app.ctx.speech, "say", lambda text, interrupt=True: None)
        app.ctx.say_event("Hazard warning.")
        monkeypatch.setattr(app.ctx, "stop_event_speech", lambda: stopped.append(True))
        app.dispatch_to_state(key_event(pygame.K_COMMA))
        assert stopped == [True]
    finally:
        app.shutdown()


def test_a_replay_stops_the_event_voice(monkeypatch):
    from freight_fate.app import App

    app = App()
    stopped = []
    monkeypatch.setattr(app.ctx, "stop_event_speech", lambda: stopped.append(True))
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True, review=True: None)
    try:
        driving = start_drive(app)
        driving._last_event_message = "Hazard warning."
        app.dispatch_to_state(key_event(pygame.K_a))
        assert stopped == [True]
    finally:
        app.shutdown()
