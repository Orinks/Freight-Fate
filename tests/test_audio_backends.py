"""Audio backend selection, the BASS engine model, and the pygame fallback."""

import pytest

from freight_fate import audio
from freight_fate.audio import (
    ENGINE_FREQ_MAX_MULT,
    ENGINE_RPM_IDLE,
    ENGINE_RPM_MAX,
    AudioEngine,
    _asset_path,
    engine_freq_mult,
)


def exercise(a: AudioEngine) -> None:
    """Every facade call must be safe regardless of backend."""
    a.play("ui/menu_select")
    a.play("nonexistent/sound")
    a.engine_start()
    a.set_engine_rpm(1500, 0.5)
    a.set_engine_rpm(2200, 1.0)
    a.set_road_noise(20.0)
    a.set_road_noise(0.0)
    a.set_weather("weather/rain_light", 0.8)
    a.set_weather(None)
    a.set_wind(0.5)
    a.set_ambient("ambient/truck_stop", 0.4)
    a.play_music("menu_theme")
    a.play_music("open_road")
    a.play_music("not_a_track")
    a.set_volumes(master=0.5, sfx=0.5, music=0.5)
    a.stop_world()
    a.stop_music()
    a.shutdown()


def test_bass_backend_selected_by_default(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    assert a.backend_name == "bass"
    assert a.enabled
    exercise(a)


def test_env_var_forces_pygame_backend(monkeypatch):
    monkeypatch.setenv("FREIGHT_FATE_AUDIO_BACKEND", "pygame")
    a = AudioEngine()
    assert a.backend_name in ("pygame", "none")
    exercise(a)


def test_fallback_to_pygame_when_bass_init_fails(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)

    def broken_bass():
        raise RuntimeError("BASS failed to initialize")

    monkeypatch.setattr(audio, "_BassBackend", broken_bass)
    a = AudioEngine()
    assert a.backend_name in ("pygame", "none")
    exercise(a)


def test_engine_freq_mult_mapping():
    assert engine_freq_mult(ENGINE_RPM_IDLE) == 1.0
    assert abs(engine_freq_mult(ENGINE_RPM_MAX) - ENGINE_FREQ_MAX_MULT) < 1e-9
    assert engine_freq_mult(0) == 1.0                  # clamped below idle
    assert engine_freq_mult(99_999) == ENGINE_FREQ_MAX_MULT  # clamped above redline
    mid = engine_freq_mult((ENGINE_RPM_IDLE + ENGINE_RPM_MAX) / 2)
    assert abs(mid - (1.0 + ENGINE_FREQ_MAX_MULT) / 2) < 1e-9


def test_sound_lookup_prefers_ogg_when_available():
    assert _asset_path("weather/rain_light", ("ogg", "wav")).name == "rain_light.ogg"
    assert _asset_path("weather/snow_wind", ("ogg", "wav")).name == "snow_wind.ogg"
    assert _asset_path("vehicle/road", ("ogg", "wav")).name == "road.ogg"


def test_engine_trial_recordings_prefer_ogg_over_generated_wav():
    assert _asset_path("engine/idle", ("ogg", "wav")).name == "idle.ogg"
    assert _asset_path("engine/start", ("ogg", "wav")).name == "start.ogg"
    assert _asset_path("engine/shutdown", ("ogg", "wav")).name == "shutdown.ogg"


def test_bass_engine_uses_single_pitched_loop(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    impl = a._impl
    a.engine_start()
    assert a.engine_running
    assert impl._engine_stream is not None
    assert impl._engine_base_freq > 0
    # frequency targets follow RPM; repeated slides must be safe
    for rpm in (600, 1100, 1800, 2200, 900):
        a.set_engine_rpm(rpm, throttle=0.7)
    a.engine_stop()
    assert not a.engine_running
    assert impl._engine_stream is None
    a.shutdown()


def test_road_noise_loop_tracks_speed(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    a.set_road_noise(30.0)
    assert audio.CH_ROAD in a._impl._loops
    assert a._impl._loops[audio.CH_ROAD][0] == "vehicle/road"
    a.set_road_noise(0.0)
    assert audio.CH_ROAD not in a._impl._loops
    a.shutdown()


def test_bass_one_shots_survive_garbage_collection(monkeypatch):
    # Channel.__del__ in sound_lib frees the BASS handle on garbage
    # collection; the backend must hold a reference until playback ends,
    # or every one-shot (menu sounds, horn, warnings) is cut off instantly
    import gc

    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    impl = a._impl
    a.play("ui/menu_move")
    gc.collect()
    assert impl._retained
    assert impl._retained[-1].is_playing
    a.shutdown()


def test_bass_fading_loops_stay_alive_during_fade(monkeypatch):
    import gc

    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    impl = a._impl
    a.set_weather("weather/rain_light", 0.8)
    assert impl._loops
    a.set_weather(None)  # 1200 ms fade-out
    gc.collect()
    assert not impl._loops
    assert impl._retained
    assert impl._retained[-1].is_playing  # still fading, not cut off
    a.shutdown()


def test_bass_headless_uses_no_sound_device(monkeypatch):
    # conftest sets SDL_AUDIODRIVER=dummy, which must route BASS to the
    # "no sound" device so CI runs the full pipeline without hardware
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    assert a.enabled
    assert a._impl._output.get_device() == audio.BASS_NO_SOUND_DEVICE
    a.shutdown()
