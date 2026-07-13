"""Driving-pressure distinctions for Relaxed, Standard, and Realistic."""

import pygame
import pytest
from driving_feature_helpers import HeldKeys, key_event, quiet_trip, start_drive


def test_driving_mode_tuning_keeps_standard_baseline_and_softens_only_relaxed():
    from freight_fate.sim.driving_modes import tuning_for_time_scale

    relaxed = tuning_for_time_scale(10.0)
    standard = tuning_for_time_scale(20.0)
    realistic = tuning_for_time_scale(40.0)

    assert [relaxed.name, standard.name, realistic.name] == [
        "relaxed",
        "standard",
        "realistic",
    ]
    assert relaxed.reaction_window > standard.reaction_window == realistic.reaction_window
    assert relaxed.collision_damage < standard.collision_damage == realistic.collision_damage
    assert relaxed.fatigue_rate < standard.fatigue_rate == realistic.fatigue_rate
    assert relaxed.ambient_spacing_s > standard.ambient_spacing_s
    assert relaxed.routine_speech_interval_s > standard.routine_speech_interval_s


def test_pause_settings_mode_change_updates_active_trip_pressure(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import PauseMenuState
    from freight_fate.states.main_menu import SettingsCategoryState, SettingsState

    app = App()
    monkeypatch.setattr(pygame.key, "get_pressed", HeldKeys)
    monkeypatch.setattr(app.ctx.audio, "play", lambda *args, **kwargs: None)
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        app.ctx.settings.hos_mode = "realistic"
        app.ctx.settings.time_scale = 20.0
        driving.update(0.0)
        assert driving.trip.hazard_scale == pytest.approx(1.0)

        app.push_state(PauseMenuState(app.ctx, driving))
        for _ in range(len(app.state.items)):
            if app.state.items[app.state.index].text == "Settings":
                break
            app.state.handle_event(key_event(pygame.K_DOWN))
        assert app.state.items[app.state.index].text == "Settings"
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, SettingsState)
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, SettingsCategoryState)
        for _ in range(len(app.state.items)):
            if app.state.items[app.state.index].text.startswith("Driving mode"):
                break
            app.state.handle_event(key_event(pygame.K_DOWN))
        assert app.state.items[app.state.index].text.startswith("Driving mode")
        app.state.handle_event(key_event(pygame.K_LEFT))
        assert app.ctx.settings.time_scale == 10.0

        while not isinstance(app.state, PauseMenuState):
            app.state.handle_event(key_event(pygame.K_ESCAPE))
        app.state.handle_event(key_event(pygame.K_ESCAPE))
        driving.update(0.0)
        assert driving.trip.hazard_scale == pytest.approx(0.55)

        app.ctx.settings.time_scale = 40.0
        driving.update(0.0)
        assert driving.trip.hazard_scale == pytest.approx(1.0)
    finally:
        app.shutdown()


def test_hos_warning_waits_until_active_hazard_is_resolved(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", lambda text, interrupt=True: spoken.append(text))
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.hos.driving_min = 11 * 60
        driving._hazard_deadline = 4.0

        driving._update_hours_and_fatigue(0.0)
        assert not any("Hours of service" in line for line in spoken)

        driving._hazard_deadline = None
        driving._update_hours_and_fatigue(0.0)
        assert any("Hours of service violation" in line for line in spoken)
    finally:
        app.shutdown()
