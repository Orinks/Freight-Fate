"""Driving-pressure distinctions for Relaxed, Standard and Real time."""

import pygame
import pytest
from driving_feature_helpers import HeldKeys, key_event, quiet_trip, start_drive
from speech_capture import speech_stub


def test_driving_mode_tuning_keeps_standard_baseline_and_softens_only_relaxed():
    from freight_fate.sim.driving_modes import tuning_for_time_scale

    relaxed = tuning_for_time_scale(10.0)
    standard = tuning_for_time_scale(20.0)

    assert [relaxed.name, standard.name] == ["relaxed", "standard"]
    assert relaxed.reaction_window > standard.reaction_window
    assert relaxed.collision_damage < standard.collision_damage
    assert relaxed.fatigue_rate < standard.fatigue_rate
    assert relaxed.ambient_spacing_s > standard.ambient_spacing_s
    assert relaxed.routine_speech_interval_s > standard.routine_speech_interval_s

    # The retired Realistic scale, and any other custom one, still resolves
    # to standard's pressure rather than raising -- a save or a bench that
    # sets the raw trip value has to keep driving. 40x is reachable in play
    # regardless: PARKED_TIME_SCALE_MULT doubles standard while parked.
    assert tuning_for_time_scale(40.0).name == "standard"


def test_real_time_is_standard_pressure_on_the_real_clock():
    """Real time (1x) differs from standard only in the clock. It carries
    standard's pressure tuning field for field, the same way the retired
    Realistic did: the row's third choice is a clock, not a difficulty."""
    from freight_fate.sim.driving_modes import tuning_for_time_scale

    real = tuning_for_time_scale(1.0)
    standard = tuning_for_time_scale(20.0)

    assert real.name == "real time"
    assert standard.name == "standard"
    for field in (
        "hazard_frequency",
        "reaction_window",
        "collision_damage",
        "fatigue_rate",
        "ambient_spacing_s",
        "routine_speech_interval_s",
    ):
        assert getattr(real, field) == getattr(standard, field), field


def test_real_time_runs_the_real_clock_rolling_and_parked(world):
    """At real time the clock is real at every speed, and stays real while
    parked with the brake set: the two-times parked fast-forward belongs to
    the compressed pacings, which it keeps."""
    from test_weather_trip import make_trip

    from freight_fate.sim.trip import FULL_COMPRESSION_MPH, PARKED_TIME_SCALE_MULT

    trip, truck = make_trip(world, time_scale=1.0)
    truck.velocity_mps = 0.0
    truck.parking_brake = True
    assert trip.effective_time_scale == pytest.approx(1.0)
    trip.waiting = True
    assert trip.effective_time_scale == pytest.approx(1.0)
    before = trip.game_minutes
    trip.update(60.0)
    assert trip.game_minutes - before == pytest.approx(1.0)

    trip.waiting = False
    truck.parking_brake = False
    truck.velocity_mps = (FULL_COMPRESSION_MPH + 10.0) / 2.23694
    assert trip.effective_time_scale == pytest.approx(1.0)
    truck.velocity_mps = 20.0 / 2.23694
    assert trip.effective_time_scale == pytest.approx(1.0)

    # The compressed pacings keep their parked fast-forward.
    trip, truck = make_trip(world, time_scale=20.0)
    truck.velocity_mps = 0.0
    truck.parking_brake = True
    trip.waiting = True
    assert trip.effective_time_scale == pytest.approx(20.0 * PARKED_TIME_SCALE_MULT)


def test_pause_settings_mode_change_updates_active_trip_pressure(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.driving import PauseMenuState
    from freight_fate.states.main_menu import (
        GameplaySettingsState,
        SettingsCategoryState,
        SettingsState,
    )

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
        # Gameplay is the first row and now opens its own submenu; Driving mode
        # lives under Difficulty and hours of service.
        app.state.handle_event(key_event(pygame.K_RETURN))
        assert isinstance(app.state, GameplaySettingsState)
        while not app.state.items[app.state.index].text.startswith("Difficulty"):
            app.state.handle_event(key_event(pygame.K_DOWN))
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

        app.ctx.settings.time_scale = 20.0
        driving.update(0.0)
        assert driving.trip.hazard_scale == pytest.approx(1.0)
    finally:
        app.shutdown()


def test_speed_keeper_ease_window_follows_the_driving_mode(monkeypatch):
    # The keeper's ease is budgeted in real seconds, so a compressed clock has
    # to buy more road for the same warning. A corner is the exception: it
    # decompresses the trip to real time, and the ease is sized on that clock
    # rather than on the pacing the player picked.
    from freight_fate.app import App
    from freight_fate.states.driving_speed_control import KEEPER_EASE_MAX_MI

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        driving.truck.velocity_mps = 25.0 / 2.23694

        assert (
            driving._keeper_ease_mi(20.0, 10.0)
            > driving._keeper_ease_mi(20.0, 4.0)
            > driving._keeper_ease_mi(20.0, 1.0)
        )
        # The ceiling trims the discretionary reaction budget so a long
        # access road is not crawled -- but never the PHYSICAL shed, which
        # the window's docstring promises is a floor. At 40x the 25-to-20
        # shed alone outruns the cap, so the window follows the physics
        # (clamping it was how the keeper arrived at 15.47 over a 15 sign
        # on long-route draws -- the one-in-four flake, fixed 2026-08-20).
        window_40x = driving._keeper_ease_mi(20.0, 40.0)
        assert window_40x > KEEPER_EASE_MAX_MI
        # The cap still binds where reaction, not physics, is the bigger
        # ask: a one-mph trim at 30x wants little shed road, and the six-plus
        # seconds of hearing-and-deciding it would otherwise buy are what the
        # ceiling exists to trim.
        assert driving._keeper_ease_mi(24.0, 30.0) == pytest.approx(KEEPER_EASE_MAX_MI)

        # A bigger drop buys more road than the base window at the same pacing.
        assert driving._keeper_ease_mi(5.0, 1.0) > driving._keeper_ease_mi(24.0, 1.0)

        # A corner runs on the real clock whichever pacing the player chose, so
        # its ease is sized there and never on the compressed road. Sizing it
        # on the pacing read the corner as close from half a mile back and held
        # the whole block at the corner speed.
        driving.trip.time_scale = 40.0
        driving.trip.controlled_turn = False
        assert driving.trip.effective_time_scale > 1.0
        assert driving._keeper_turn_ease_scale() == pytest.approx(1.0)
        driving.trip.controlled_turn = True
        assert driving._keeper_turn_ease_scale() == pytest.approx(1.0)
    finally:
        app.shutdown()


def test_hos_warning_waits_until_active_hazard_is_resolved(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
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
