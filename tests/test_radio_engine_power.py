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
