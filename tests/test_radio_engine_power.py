"""The radio draws power from the engine: a dead cab is a silent one."""

import pytest
from speech_capture import speech_stub

from freight_fate.models.jobs import CARGO_CATALOG, Job


def _drive_job() -> Job:
    return Job(
        CARGO_CATALOG["general"],
        12.0,
        "Denver",
        "Denver Dry Warehouse",
        "Salt Lake City",
        520.0,
        2400.0,
        14.0,
    )


@pytest.fixture
def denver_driving(monkeypatch):
    from freight_fate.app import App
    from freight_fate.models.profile import Profile
    from freight_fate.states.driving import DrivingState

    app = App()
    played_music = []
    stopped = []
    spoken = []
    monkeypatch.setattr(
        app.ctx.audio, "play_music", lambda track, fade_ms=1500: played_music.append(track)
    )
    monkeypatch.setattr(app.ctx.audio, "stop_music", lambda fade_ms=0: stopped.append(fade_ms))
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    app.ctx.profile = Profile(name="Radio Power", current_city="Denver")
    route = app.ctx.world.route_from_cities(["Denver", "Salt Lake City"])
    driving = DrivingState(app.ctx, _drive_job(), route, trip_seed=777, start_hour=13.0)
    app.push_state(driving)
    try:
        yield app, driving, played_music, stopped, spoken
    finally:
        app.shutdown()


def test_radio_is_silent_until_the_engine_starts(denver_driving):
    app, driving, played_music, _stopped, _spoken = denver_driving
    # The top of every load: radio enabled, engine off, and nothing plays.
    assert driving.radio.enabled is True
    assert played_music == []

    driving.truck.start_engine()
    driving._update_audio(0.0)

    assert played_music, "the radio comes back on its own with the engine"


def test_engine_shutdown_cuts_the_radio(denver_driving):
    app, driving, played_music, stopped, _spoken = denver_driving
    driving.truck.start_engine()
    driving._update_audio(0.0)
    assert played_music
    stopped.clear()

    driving.truck.stop_engine()
    driving._update_audio(0.0)

    assert stopped, "the radio loses power with the engine"


def test_radio_keys_speak_the_no_power_line_with_the_engine_off(denver_driving):
    app, driving, played_music, _stopped, spoken = denver_driving

    driving._toggle_radio()
    driving._tune_radio(1)
    driving._jump_radio_category(1)

    assert played_music == []
    assert spoken.count("The engine is off. The radio has no power.") == 3
    # The player's wish is untouched: the radio is still on for ignition.
    assert driving.radio.enabled is True

    # The status key answers, but explains the silence.
    driving._speak_radio_status()
    assert spoken[-1].startswith("Radio on.")
    assert spoken[-1].endswith("The engine is off, so the radio has no power right now.")


def _shift_key_event(key, unicode_=""):
    import pygame

    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=pygame.KMOD_SHIFT, unicode=unicode_)


def test_shift_page_up_raises_radio_volume_ten_percent(denver_driving):
    app, driving, _played_music, _stopped, spoken = denver_driving
    import pygame

    app.ctx.settings.radio_volume = 0.25

    driving.handle_event(_shift_key_event(pygame.K_PAGEUP))

    assert app.ctx.settings.radio_volume == pytest.approx(0.35)
    assert spoken[-1] == "Radio volume 35 percent."


def test_shift_page_down_lowers_radio_volume_ten_percent(denver_driving):
    app, driving, _played_music, _stopped, spoken = denver_driving
    import pygame

    app.ctx.settings.radio_volume = 0.35

    driving.handle_event(_shift_key_event(pygame.K_PAGEDOWN))

    assert app.ctx.settings.radio_volume == pytest.approx(0.25)
    assert spoken[-1] == "Radio volume 25 percent."


def test_shift_semicolon_and_quote_mirror_the_page_keys(denver_driving):
    app, driving, _played_music, _stopped, spoken = denver_driving
    import pygame

    app.ctx.settings.radio_volume = 0.25

    driving.handle_event(_shift_key_event(pygame.K_SEMICOLON, ";"))
    assert app.ctx.settings.radio_volume == pytest.approx(0.35)
    assert spoken[-1] == "Radio volume 35 percent."

    driving.handle_event(_shift_key_event(pygame.K_QUOTE, "'"))
    assert app.ctx.settings.radio_volume == pytest.approx(0.25)
    assert spoken[-1] == "Radio volume 25 percent."


def test_shift_page_down_clamps_at_muted(denver_driving):
    app, driving, _played_music, _stopped, spoken = denver_driving
    import pygame

    app.ctx.settings.radio_volume = 0.05

    driving.handle_event(_shift_key_event(pygame.K_PAGEDOWN))

    assert app.ctx.settings.radio_volume == pytest.approx(0.0)
    assert spoken[-1] == "Radio volume muted."

    # A second press at the floor stays put, not negative.
    driving.handle_event(_shift_key_event(pygame.K_PAGEDOWN))
    assert app.ctx.settings.radio_volume == pytest.approx(0.0)
    assert spoken[-1] == "Radio volume muted."


def test_shift_page_up_clamps_at_all_the_way_up(denver_driving):
    app, driving, _played_music, _stopped, spoken = denver_driving
    import pygame

    app.ctx.settings.radio_volume = 0.95

    driving.handle_event(_shift_key_event(pygame.K_PAGEUP))

    assert app.ctx.settings.radio_volume == pytest.approx(1.0)
    assert spoken[-1] == "Radio volume all the way up."

    # A second press at the ceiling stays put, not over 100.
    driving.handle_event(_shift_key_event(pygame.K_PAGEUP))
    assert app.ctx.settings.radio_volume == pytest.approx(1.0)
    assert spoken[-1] == "Radio volume all the way up."


def test_shift_volume_works_with_the_engine_off_and_radio_off(denver_driving):
    """The setting is what it is regardless of power state: no "engine is
    off" line, unlike the plain tune and category keys."""
    app, driving, _played_music, _stopped, spoken = denver_driving
    import pygame

    assert driving.truck.engine_on is False
    driving.radio.enabled = False
    app.ctx.settings.radio_volume = 0.25

    driving.handle_event(_shift_key_event(pygame.K_PAGEUP))

    assert app.ctx.settings.radio_volume == pytest.approx(0.35)
    assert spoken[-1] == "Radio volume 35 percent."
    assert "no power" not in spoken[-1].lower()


def test_shift_volume_applies_live_while_the_radio_plays(denver_driving):
    app, driving, played_music, _stopped, _spoken = denver_driving
    import pygame

    driving.truck.start_engine()
    driving._update_audio(0.0)
    assert played_music
    app.ctx.settings.radio_volume = 0.25

    driving.handle_event(_shift_key_event(pygame.K_PAGEUP))

    assert app.ctx.audio.music_volume == pytest.approx(0.35)


def test_plain_and_ctrl_tune_behavior_unchanged_by_shift(denver_driving):
    """Adding the Shift branch must not disturb the existing plain tune or
    Ctrl category-jump behavior, and Ctrl+Shift still leaves the volume
    alone -- Ctrl wins, exactly like before Shift existed."""
    import pygame

    app, driving, _played_music, _stopped, spoken = denver_driving
    driving.truck.start_engine()
    driving._update_audio(0.0)
    before_volume = app.ctx.settings.radio_volume
    before_station = driving.radio.station_id

    driving.handle_event(
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_PAGEDOWN, mod=0, unicode="")
    )
    assert driving.radio.station_id != before_station
    assert app.ctx.settings.radio_volume == pytest.approx(before_volume)

    driving.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_PAGEUP, mod=0, unicode=""))
    assert driving.radio.station_id == before_station
    assert app.ctx.settings.radio_volume == pytest.approx(before_volume)

    category_before = driving.radio.station_id
    driving.handle_event(
        pygame.event.Event(
            pygame.KEYDOWN,
            key=pygame.K_PAGEDOWN,
            mod=pygame.KMOD_CTRL | pygame.KMOD_SHIFT,
            unicode="",
        )
    )
    assert app.ctx.settings.radio_volume == pytest.approx(before_volume)
    assert "Radio volume" not in spoken[-1]
    assert driving.radio.station_id != category_before
