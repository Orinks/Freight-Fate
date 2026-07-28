"""Regression coverage for the existing speech-review controls."""

import pygame
from driving_feature_helpers import key_event, quiet_trip, start_drive


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
    monkeypatch.setattr(app.ctx, "say", lambda text, interrupt=True, review=True: None)
    try:
        driving = start_drive(app)
        driving._last_event_message = "Hazard warning."
        driving.handle_event(key_event(pygame.K_a))
        assert stopped == [True]
    finally:
        app.shutdown()
