"""Audio backend selection, the BASS engine model, and the pygame fallback."""

import pytest

from freight_fate import audio
from freight_fate.audio import (
    ENGINE_FREQ_MAX_MULT,
    ENGINE_LOOP_GAIN,
    ENGINE_RPM_IDLE,
    ENGINE_RPM_MAX,
    AudioEngine,
    _asset_path,
    engine_freq_mult,
    engine_load_gain,
)
from freight_fate.music import ALL_MUSIC_TRACKS


@pytest.fixture(autouse=True)
def _free_leaked_bass():
    """Free any BASS device a test leaves initialized.

    A test whose body fails before its own ``a.shutdown()`` would otherwise
    leave the BASS no-sound device initialized. The next ``AudioEngine()``
    then hits ``BASS_ERROR_ALREADY`` during construction and silently falls
    back to pygame, turning a single failure into a cascade of skipped BASS
    tests -- and leaking the init into later test files.
    """
    yield
    try:
        from sound_lib.external.pybass import BASS_Free, BASS_SetDevice

        BASS_SetDevice(0)
        BASS_Free()  # best-effort; a no-op when nothing is initialized
    except Exception:
        pass


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
    assert engine_freq_mult(0) == 1.0  # clamped below idle
    assert engine_freq_mult(99_999) == ENGINE_FREQ_MAX_MULT  # clamped above redline
    mid = engine_freq_mult((ENGINE_RPM_IDLE + ENGINE_RPM_MAX) / 2)
    assert abs(mid - (1.0 + ENGINE_FREQ_MAX_MULT) / 2) < 1e-9


def test_engine_load_gain_keeps_idle_audible_and_unloads_during_shift():
    assert engine_load_gain(0.0) == 0.55
    assert engine_load_gain(0.08) < engine_load_gain(0.7)
    assert engine_load_gain(1.0) == 1.0


def test_split_volume_settings_apply_to_silent_backend():
    backend = audio._NullBackend()
    backend.set_volumes(
        master=0.8,
        sfx=0.7,
        music=0.6,
        weather=0.5,
        engine=0.4,
        ui=0.9,
    )

    assert backend.master_volume == 0.8
    assert backend.sfx_volume == 0.7
    assert backend.music_volume == 0.6
    assert backend.weather_volume == 0.5
    assert backend.engine_volume == 0.4
    assert backend.ui_volume == 0.9


def test_sound_lookup_prefers_ogg_when_available():
    assert _asset_path("weather/rain_light", ("ogg", "wav")).name == "rain_light.ogg"
    assert _asset_path("weather/snow_wind", ("ogg", "wav")).name == "snow_wind.ogg"
    assert _asset_path("vehicle/brake_air", ("ogg", "wav")).name == "brake_air.ogg"
    assert _asset_path("vehicle/brake_release", ("ogg", "wav")).name == "brake_release.ogg"
    assert _asset_path("vehicle/brake_set", ("ogg", "wav")).name == "brake_set.ogg"
    assert _asset_path("vehicle/horn", ("ogg", "wav")).name == "horn.ogg"
    assert _asset_path("vehicle/gear_shift", ("ogg", "wav")).name == "gear_shift.ogg"
    assert _asset_path("vehicle/road", ("ogg", "wav")).name == "road.ogg"


def test_engine_recordings_prefer_ogg_over_generated_wav():
    assert _asset_path("engine/idle", ("ogg", "wav")).name == "idle.ogg"
    assert _asset_path("engine/start", ("ogg", "wav")).name == "start.ogg"
    assert _asset_path("engine/shutdown", ("ogg", "wav")).name == "shutdown.ogg"


def test_engine_start_recording_is_short_one_shot():
    import soundfile as sf

    info = sf.info(str(_asset_path("engine/start", ("ogg", "wav"))))
    duration = info.frames / info.samplerate
    assert duration <= 4.25


def test_vehicle_horn_and_shift_recordings_are_short_one_shots():
    import soundfile as sf

    horn = sf.info(str(_asset_path("vehicle/horn", ("ogg", "wav"))))
    horn_duration = horn.frames / horn.samplerate
    assert horn_duration <= 1.0

    shift = sf.info(str(_asset_path("vehicle/gear_shift", ("ogg", "wav"))))
    shift_duration = shift.frames / shift.samplerate
    assert shift_duration <= 0.8


def test_pygame_music_never_loops_catalog_tracks(monkeypatch):
    calls = []
    backend = audio._PygameBackend.__new__(audio._PygameBackend)
    backend.enabled = True
    backend.master_volume = 1.0
    backend.music_volume = 0.5
    backend._music_track = None

    monkeypatch.setattr(audio.pygame.mixer.music, "load", lambda path, namehint="": None)
    monkeypatch.setattr(audio.pygame.mixer.music, "set_volume", lambda volume: None)
    monkeypatch.setattr(
        audio.pygame.mixer.music,
        "play",
        lambda *, loops, fade_ms: calls.append((loops, fade_ms)),
    )

    for track in ALL_MUSIC_TRACKS:
        backend.play_music(track.key, fade_ms=123)
        backend._music_track = None

    assert calls == [(0, 123)] * len(ALL_MUSIC_TRACKS)


def test_bass_music_never_loops_catalog_tracks(monkeypatch):
    class FakeStream:
        handle = 1

        def set_volume(self, volume):
            pass

        def play(self):
            pass

    loop_flags = []
    backend = audio._BassBackend.__new__(audio._BassBackend)
    backend.master_volume = 1.0
    backend.music_volume = 0.5
    backend._music_track = None
    backend._music_stream = None
    backend._BassError = Exception
    backend._ATTRIB_VOL = 0
    backend._slide = object()
    backend._bass_call = lambda *args: None

    def fake_stream(data, label, looping):
        loop_flags.append(looping)
        return FakeStream()

    monkeypatch.setattr(backend, "_stream", fake_stream)

    for track in ALL_MUSIC_TRACKS:
        backend.play_music(track.key, fade_ms=123)
        backend._music_track = None
        backend._music_stream = None

    assert loop_flags == [False] * len(ALL_MUSIC_TRACKS)


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


def _record_sfx_keys(monkeypatch, impl):
    """Record every sound key the backend opens, without changing behavior."""
    keys: list[str] = []
    original = impl._sfx_stream

    def spy(key, looping=False):
        keys.append(key)
        return original(key, looping)

    monkeypatch.setattr(impl, "_sfx_stream", spy)
    return keys


def test_silent_engine_start_skips_the_ignition_crank(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    impl = a._impl
    keys = _record_sfx_keys(monkeypatch, impl)
    a.engine_start(play_start_sound=False)  # resume / menu-return path
    assert a.engine_running
    assert "engine/start" not in keys  # the crank must not replay
    assert impl._engine_stream is not None  # the loop still comes up
    a.engine_stop()
    a.shutdown()


def test_deliberate_engine_start_plays_crank_and_arms_crossfade(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    impl = a._impl
    keys = _record_sfx_keys(monkeypatch, impl)
    a.engine_start()  # deliberate ignition
    assert "engine/start" in keys
    # A crank fade-out plus the loop fade-in are scheduled, and the loop starts
    # silent so the ignition is not drowned out.
    assert len(impl._fades) == 2
    assert impl._engine_intro_gain == 0.0
    a.engine_stop()
    a.shutdown()


def test_engine_start_crossfade_ramps_the_loop_up_over_time(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    impl = a._impl
    a.engine_start()
    assert impl._engine_intro_gain == 0.0
    # Advance well past the clip length plus the crossfade window.
    for _ in range(400):
        a.update(0.05)
    assert impl._engine_intro_gain == 1.0
    assert len(impl._fades) == 0  # finished fades are dropped
    a.engine_stop()
    a.shutdown()


def test_engine_starting_true_during_crank_then_clears(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    a.engine_start()  # deliberate ignition
    assert a.engine_starting  # loop has not taken over yet
    # Advance past the clip length plus the crossfade window.
    for _ in range(400):
        a.update(0.05)
    assert not a.engine_starting  # loop has taken over
    assert a.engine_running
    a.engine_stop()
    a.shutdown()


def test_silent_engine_start_is_never_marked_starting(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    a.engine_start(play_start_sound=False)  # resume / menu-return path
    assert not a.engine_starting  # no crank, nothing to gate on
    a.engine_stop()
    a.shutdown()


def test_engine_stop_clears_engine_starting(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    a.engine_start()
    assert a.engine_starting
    a.engine_stop()  # stopping mid-crank must leave clean state
    assert not a.engine_starting
    a.shutdown()


def test_null_backend_is_never_engine_starting():
    assert audio._NullBackend().engine_starting is False


def test_engine_stop_clears_pending_fades(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    impl = a._impl
    a.engine_start()
    assert len(impl._fades) > 0
    a.engine_stop()
    assert len(impl._fades) == 0
    assert impl._engine_intro_gain == 1.0
    a.shutdown()


def test_road_noise_loop_tracks_speed(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    a.set_road_noise(30.0)
    assert audio.CH_ROAD in a._impl._loops
    assert a._impl._loops[audio.CH_ROAD][0] == "vehicle/road"
    assert a._impl._loops[audio.CH_ROAD][1] == 1.0
    a.set_road_noise(0.0)
    assert audio.CH_ROAD not in a._impl._loops
    a.shutdown()


def test_new_context_loops_enter_mixer_at_full_gain(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    a.set_wind(2.0)
    assert a._impl._loops[audio.CH_WEATHER_B][0] == "weather/wind"
    assert a._impl._loops[audio.CH_WEATHER_B][1] == 1.0
    a.set_ambient("poi/facility_gate")
    assert a._impl._loops[audio.CH_AMBIENT][0] == "poi/facility_gate"
    assert a._impl._loops[audio.CH_AMBIENT][1] == 1.0
    assert ENGINE_LOOP_GAIN == 1.0
    a.shutdown()


def test_horn_uses_reserved_loop_slot(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    a.horn_start()
    assert a._impl._loops[audio.CH_HORN][0] == "vehicle/horn"
    a.horn_stop()
    assert audio.CH_HORN not in a._impl._loops
    a.shutdown()


def test_bass_horn_sustains_then_rings_out_on_release(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    impl = a._impl
    a.horn_start()
    a.horn_start()  # key autorepeat must not stack a second horn
    assert list(impl._sustains) == [audio.CH_HORN]
    stream = impl._loops[audio.CH_HORN][2]
    a.horn_stop()
    # The loop is released and the channel handed off, but the stream keeps
    # playing its release tail (retained so it is not freed mid-tail).
    assert audio.CH_HORN not in impl._sustains
    assert audio.CH_HORN not in impl._loops
    assert stream in impl._retained
    a.shutdown()


def test_bass_horn_press_during_release_tail_does_not_stack(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    impl = a._impl
    a.horn_start()
    a.horn_stop()  # tail is now ringing out on the channel
    tail = impl._releasing.get(audio.CH_HORN)
    assert tail is not None and tail[1].is_playing
    retained = len(impl._retained)
    a.horn_start()  # pressed again mid-tail: must be ignored, not stacked
    assert audio.CH_HORN not in impl._sustains  # no new held loop
    assert audio.CH_HORN not in impl._loops
    assert impl._releasing.get(audio.CH_HORN) is tail  # same tail, no new stream
    assert len(impl._retained) == retained  # nothing new retained
    a.shutdown()


def test_pygame_horn_press_during_release_tail_does_not_restart(monkeypatch):
    monkeypatch.setenv("FREIGHT_FATE_AUDIO_BACKEND", "pygame")
    a = AudioEngine()
    if a.backend_name != "pygame":
        pytest.skip("pygame backend unavailable")
    impl = a._impl
    a.horn_start()
    a.horn_stop()
    state = impl._sustains[audio.CH_HORN]
    assert state["phase"] == "release"
    a.horn_start()  # mid-tail press: must not restart the horn
    assert impl._sustains[audio.CH_HORN] is state
    assert impl._sustains[audio.CH_HORN]["phase"] == "release"
    a.shutdown()


def test_pygame_horn_sustain_phase_transitions(monkeypatch):
    monkeypatch.setenv("FREIGHT_FATE_AUDIO_BACKEND", "pygame")
    a = AudioEngine()
    if a.backend_name != "pygame":
        pytest.skip("pygame backend unavailable")
    impl = a._impl
    a.horn_start()
    a.horn_start()  # idempotent while held
    assert list(impl._sustains) == [audio.CH_HORN]
    assert impl._sustains[audio.CH_HORN]["phase"] == "sustain"
    # The loop region is sliced shorter than the whole file, proving we loop an
    # interior region rather than the full horn.
    head, body, _tail = next(iter(impl._segment_cache.values()))
    assert body.get_length() < head.get_length()
    a.horn_stop()
    assert impl._sustains[audio.CH_HORN]["phase"] == "release"
    a.shutdown()


def test_pygame_backend_does_not_play_reverse_loop_through_mixer(monkeypatch):
    backend = audio._PygameBackend.__new__(audio._PygameBackend)

    def fail_start_loop(*_args, **_kwargs):
        raise AssertionError("reverse cue must not use pygame.mixer")

    monkeypatch.setattr(backend, "start_loop", fail_start_loop)

    backend.reverse_start()
    backend.reverse_stop()


def test_bass_one_shots_survive_garbage_collection(monkeypatch):
    # Channel.__del__ in sound_lib frees the BASS handle on garbage
    # collection; the backend must hold a reference until playback ends,
    # or every one-shot (menu sounds, horn, warnings) is cut off instantly.
    import gc
    import weakref

    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    try:
        impl = a._impl
        a.play("ui/menu_move")
        assert impl._retained
        stream = impl._retained[-1]
        assert stream.is_playing  # the one-shot really started on the device

        # Drop every local strong reference and force a collection. Without the
        # backend's retain list, Channel.__del__ would run here and free the
        # BASS handle mid-playback; the retained wrapper must survive the sweep.
        # (Asserting is_playing *after* gc would instead race a real-time
        # engine: ui/menu_move is only ~70 ms, so a scheduling stall on a
        # loaded CI runner lets it finish naturally and flake the check.)
        marker = weakref.ref(stream)
        del stream
        gc.collect()
        assert marker() is not None
        assert impl._retained[-1] is marker()
    finally:
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
