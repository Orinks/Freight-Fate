"""Audio backend selection, the BASS engine model, and the pygame fallback."""

import threading
import time

import pytest
from asset_helpers import needs_audio_assets

from freight_fate import audio
from freight_fate.audio import (
    ENGINE_FREQ_MAX_MULT,
    ENGINE_LOOP_GAIN,
    ENGINE_RPM_IDLE,
    ENGINE_RPM_MAX,
    AudioEngine,
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


def test_engine_band_weights_edges_blend_and_pure_zones():
    import math

    natives = tuple(rpm for _key, rpm in audio.ENGINE_BANDS)
    n = len(natives)

    def solo(index):
        expected = [0.0] * n
        expected[index] = 1.0
        return tuple(expected)

    # Outside the ring the nearest band carries alone.
    assert audio.engine_band_weights(0, natives) == solo(0)
    assert audio.engine_band_weights(natives[0], natives) == solo(0)
    assert audio.engine_band_weights(natives[-1], natives) == solo(-1 % n)
    assert audio.engine_band_weights(9999, natives) == solo(-1 % n)
    # At the geometric midpoint of a gap exactly two bands blend equal-power.
    mid = math.sqrt(natives[1] * natives[2])
    w = audio.engine_band_weights(mid, natives)
    assert w[1] > 0.0 and w[2] > 0.0
    assert sum(1 for x in w if x > 0.0) == 2
    assert sum(x * x for x in w) == pytest.approx(1.0)
    # Just off a native rpm the band is PURE -- the crossfade windows are
    # narrow, so a cut near its recorded speed never shares the mix (this is
    # what kills both the formant smear and the two-pitch beat).
    for i, native in enumerate(natives[:-1]):
        assert audio.engine_band_weights(native + 10, natives) == solo(i)
        if i > 0:
            assert audio.engine_band_weights(native - 10, natives) == solo(i)
    # A sweep never needs more than a bounded stretch from any sounding band:
    # wherever a band has weight, rpm/native stays inside the safety clamps.
    rpm = 300.0
    while rpm < 2400.0:
        for weight, native in zip(audio.engine_band_weights(rpm, natives), natives, strict=True):
            if weight > 1e-6 and natives[0] <= rpm <= natives[-1]:
                ratio = rpm / native
                assert audio.ENGINE_BAND_RATE_MIN <= ratio <= audio.ENGINE_BAND_RATE_MAX
        rpm += 7.0


def test_engine_load_gain_keeps_audible_load_contour():
    # Floor raised off the old 0.55 so coasting is not too quiet, but the span
    # stays wide enough to hear effort changes and the automatic-shift unload.
    assert engine_load_gain(-1.0) == pytest.approx(0.68)
    assert engine_load_gain(0.0) == pytest.approx(0.68)
    assert engine_load_gain(0.45) == pytest.approx(0.824)
    assert engine_load_gain(0.08) < engine_load_gain(0.7)
    assert engine_load_gain(1.0) == 1.0
    assert engine_load_gain(2.0) == 1.0


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


@needs_audio_assets
def test_sound_lookup_prefers_ogg_when_available():
    # _asset_bytes answers from the pack on clean clones and from the loose
    # tree on builder machines; the extension preference holds either way.
    for key in (
        "weather/rain_light",
        "weather/snow_wind",
        "vehicle/brake_air",
        "vehicle/brake_release",
        "vehicle/brake_set",
        "vehicle/horn",
        "vehicle/gear_shift",
        "vehicle/road",
    ):
        found = audio._asset_bytes(key, ("ogg", "wav"))
        assert found is not None, key
        assert found[1] == "ogg", key


@needs_audio_assets
def test_engine_recordings_resolve_for_the_ring_and_one_shots():
    # Looping beds may resolve to WAV (lossy edges break loop seams --
    # tools/fix_loop_seams.py); the licensed overlay's file wins where
    # present. One-shots stay ogg.
    assert audio._asset_bytes("engine/idle", ("ogg", "wav"))[1] in {"ogg", "wav"}
    assert audio._asset_bytes("engine/start", ("ogg", "wav"))[1] == "ogg"
    assert audio._asset_bytes("engine/shutdown", ("ogg", "wav"))[1] == "ogg"


def _shipped_duration_s(key: str) -> float:
    import io

    import soundfile as sf

    data, _ext = audio._asset_bytes(key, ("ogg", "wav"))
    info = sf.info(io.BytesIO(data))
    return info.frames / info.samplerate


@needs_audio_assets
def test_engine_start_recording_is_short_one_shot():
    assert _shipped_duration_s("engine/start") <= 4.25


@needs_audio_assets
def test_vehicle_horn_and_shift_recordings_are_short_one_shots():
    assert _shipped_duration_s("vehicle/horn") <= 1.0
    assert _shipped_duration_s("vehicle/gear_shift") <= 0.8


@needs_audio_assets
def test_asset_length_matches_a_real_decode_of_the_same_clip():
    """A one-shot is handed to the mixer without a handle, so the only way to
    know when it stops sounding is to measure the clip. Read from the
    container's own headers -- no decoder, no audio device -- and cross-checked
    here against an actual decode."""
    for key in ("driver/yawn", "events/spike_strip", "vehicle/signal_tone", "vehicle/bar_solid"):
        assert audio.asset_length_s(key) == pytest.approx(_shipped_duration_s(key), abs=0.01)


def test_asset_length_covers_synthesized_cues_and_shrugs_at_unknown_keys():
    from freight_fate.states.driving_siren import SIGNATURE_KEY, register_enforcement_sounds

    register_enforcement_sounds()
    assert audio.asset_length_s(SIGNATURE_KEY) > 0.0, "a generated cue has a length too"
    assert audio.asset_length_s("nothing/at_all") == 0.0


@needs_audio_assets
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


def _init_radio_fields(backend):
    """The async radio-connect state a bare __new__ backend is missing."""
    backend._radio_lock = threading.Lock()
    backend._radio_generation = 0
    backend._radio_pending = None
    backend._radio_connecting_url = None
    backend._radio_failed_url = None
    backend._radio_threads = []


def _join_radio_workers(backend, timeout=5.0):
    deadline = time.monotonic() + timeout
    for thread in list(backend._radio_threads):
        thread.join(max(0.0, deadline - time.monotonic()))


@needs_audio_assets
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
    _init_radio_fields(backend)

    def fake_stream(data, label, looping):
        loop_flags.append(looping)
        return FakeStream()

    monkeypatch.setattr(backend, "_stream", fake_stream)

    for track in ALL_MUSIC_TRACKS:
        backend.play_music(track.key, fade_ms=123)
        backend._music_track = None
        backend._music_stream = None

    assert loop_flags == [False] * len(ALL_MUSIC_TRACKS)


def test_bass_radio_stream_uses_url_stream(monkeypatch):
    class FakeStream:
        handle = 1

        def __init__(self):
            self.volume = None
            self.played = False

        def set_volume(self, volume):
            self.volume = volume

        def play(self):
            self.played = True

    opened = []
    slides = []
    backend = audio._BassBackend.__new__(audio._BassBackend)
    backend.master_volume = 1.0
    backend.music_volume = 0.5
    backend._music_track = None
    backend._music_stream = None
    backend._BassError = Exception
    backend._ATTRIB_VOL = 0
    backend._slide = object()
    backend._bass_call = lambda *args: slides.append(args)
    _init_radio_fields(backend)

    def fake_url_stream(url, autofree):
        opened.append(url)
        return FakeStream()

    monkeypatch.setattr(backend, "_URLStream", fake_url_stream, raising=False)

    backend.play_radio_stream("https://example.test/live.mp3", fade_ms=321)
    assert backend._music_track is None  # the connect happens off-thread
    _join_radio_workers(backend)
    backend._collect_radio_stream()

    assert opened == ["https://example.test/live.mp3"]
    assert backend._music_track == "https://example.test/live.mp3"
    assert backend._music_stream.played
    assert backend._music_stream.volume == 0.0
    assert slides[-1][-1] == 321


def test_bass_engine_wobble_meanders_and_shapes_the_ring(monkeypatch):
    # Anti-repetition: each band's rate and gain take a slow bounded random
    # walk so a seam-clean loop's period is never exactly fixed -- the ear
    # cannot lock onto the recurrence. Rate stays within ~5 cents.
    class FakeStream:
        def __init__(self):
            self.handle = 1
            self.volume = None

        def set_volume(self, volume):
            self.volume = volume

    slides = []
    backend = audio._BassBackend.__new__(audio._BassBackend)
    backend.master_volume = 1.0
    backend.engine_volume = 1.0
    backend._BassError = Exception
    backend._ATTRIB_FREQ = 1
    backend._slide = object()
    backend._bass_call = lambda _fn, _handle, _attr, value, _ms: slides.append(value)
    backend._fades = audio.FadeScheduler()
    backend._engine_running = True
    backend._engine_starting = False
    backend._engine_stream = None
    backend._engine_last_rpm = 950.0
    backend._engine_last_throttle = 0.0
    backend._engine_duck = 1.0
    backend._engine_intro_gain = 1.0
    backend._engine_intro_load = 0.0
    backend._engine_bands = [(950.0, FakeStream(), 44100.0)]
    backend._engine_wobble = [[0.0, 0.0]]
    backend._wobble_rng = __import__("random").Random(7)
    _init_radio_fields(backend)

    for _ in range(120):  # ~2 s of frames
        backend.update(1.0 / 60.0)
    rate_walk, gain_walk = backend._engine_wobble[0]
    assert rate_walk != 0.0 and abs(rate_walk) <= audio.ENGINE_WOBBLE_RATE_MAX
    assert gain_walk != 0.0 and abs(gain_walk) <= audio.ENGINE_WOBBLE_GAIN_MAX

    backend.set_engine_rpm(950.0, 0.0)
    assert slides[-1] == pytest.approx(44100.0 * (1.0 + rate_walk))
    base_level = audio.engine_load_gain(0.0)
    assert backend._engine_bands[0][1].volume == pytest.approx(base_level * (1.0 + gain_walk))


def test_bass_radio_stream_recreates_a_stalled_stream(monkeypatch):
    # Re-tuning the SAME url must rebuild a dead connection (the dock bed or
    # a network stall killed it); only a live stream is allowed to dedupe.
    class FakeStream:
        def __init__(self, playing):
            self.handle = 1
            self.is_playing = playing
            self.volume = None

        def set_volume(self, volume):
            self.volume = volume

        def play(self):
            self.is_playing = True

    backend = audio._BassBackend.__new__(audio._BassBackend)
    backend.master_volume = 1.0
    backend.music_volume = 0.5
    backend._BassError = Exception
    backend._ATTRIB_VOL = 0
    backend._slide = object()
    backend._bass_call = lambda *args: None
    backend._fade_out = lambda stream, fade_ms: None
    backend._music_stream = FakeStream(playing=False)
    backend._music_track = "https://example.test/live.mp3"
    _init_radio_fields(backend)

    opened = []

    def fake_url_stream(url, autofree):
        opened.append(url)
        return FakeStream(playing=True)

    monkeypatch.setattr(backend, "_URLStream", fake_url_stream, raising=False)

    backend.play_radio_stream("https://example.test/live.mp3", fade_ms=100)
    _join_radio_workers(backend)
    backend._collect_radio_stream()
    assert opened == ["https://example.test/live.mp3"]
    assert backend._music_stream.is_playing

    backend.play_radio_stream("https://example.test/live.mp3", fade_ms=100)
    assert opened == ["https://example.test/live.mp3"]


@needs_audio_assets
def test_bass_engine_model_matches_available_cuts(monkeypatch):
    # With the licensed multisample cuts installed the engine comes up as the
    # crossfade ring; a clean clone (synthesized engine/idle only) falls back
    # to the single pitched loop. Either way rpm tracking must be safe.
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    impl = a._impl
    have_all_cuts = all(
        audio._asset_bytes(key, ("ogg", "wav")) is not None for key, _rpm in audio.ENGINE_BANDS
    )
    a.engine_start()
    assert a.engine_running
    if have_all_cuts:
        assert len(impl._engine_bands) == len(audio.ENGINE_BANDS)
        assert impl._engine_stream is None
    else:
        assert impl._engine_bands == []
        assert impl._engine_stream is not None
        assert impl._engine_base_freq > 0
    # frequency targets follow RPM; repeated slides must be safe
    for rpm in (600, 1100, 1800, 2200, 900):
        a.set_engine_rpm(rpm, throttle=0.7)
    a.engine_stop()
    assert not a.engine_running
    assert impl._engine_stream is None
    assert impl._engine_bands == []
    a.shutdown()


def test_engine_voice_setting_switches_models_live(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    impl = a._impl
    have_all_cuts = all(
        audio._asset_bytes(key, ("ogg", "wav")) is not None for key, _rpm in audio.ENGINE_BANDS
    )
    a.set_engine_voice(True)  # classic
    a.engine_start(play_start_sound=False)
    assert impl._engine_bands == []
    assert impl._engine_stream is not None  # the classic pitched loop
    if have_all_cuts:
        a.set_engine_voice(False)  # back to real, live, mid-run
        assert a.engine_running
        assert len(impl._engine_bands) == len(audio.ENGINE_BANDS)
        assert impl._engine_stream is None
    a.engine_stop()
    a.shutdown()


@needs_audio_assets
def test_both_1600_jake_cuts_ship():
    """The future jake A/B needs both cuts in the loose tree and the pack --
    the routing has nothing to route to otherwise."""
    from pathlib import Path

    from asset_helpers import asset_exists

    sounds_root = Path(__file__).parents[1] / "src" / "freight_fate" / "assets" / "sounds"
    assert asset_exists(sounds_root, audio.JAKE_RECORDED_KEY)
    assert asset_exists(sounds_root, audio.JAKE_CLASSIC_KEY)


@needs_audio_assets
def test_jake_voice_setting_routes_the_synth_key_and_applies_live(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    try:
        # has_asset resolves the key the player-facing catalog and the real
        # drive both use -- the routing must be invisible to callers.
        assert a.has_asset(audio.JAKE_RECORDED_KEY)
        a.set_jake_voice(True)  # classic, before anything is sounding
        assert a.has_asset(audio.JAKE_RECORDED_KEY)

        a.set_jake_voice(False)  # real again
        a.start_loop(audio.CH_JAKE, audio.JAKE_RECORDED_KEY, volume=0.5)
        loop = a._impl._loops[audio.CH_JAKE]
        assert loop[0] == audio.JAKE_RECORDED_KEY

        a.set_jake_voice(True)  # classic, live, mid-growl
        loop = a._impl._loops[audio.CH_JAKE]
        assert loop[0] == audio.JAKE_CLASSIC_KEY
        assert loop[1] == 0.5  # the level carries across the re-voice

        a.set_jake_voice(False)  # back to real, live
        loop = a._impl._loops[audio.CH_JAKE]
        assert loop[0] == audio.JAKE_RECORDED_KEY

        a.stop_loop(audio.CH_JAKE)
    finally:
        a.shutdown()


@needs_audio_assets
def test_the_jake_toggle_re_voices_whatever_band_is_sounding(monkeypatch):
    """This asserted the opposite -- that a band other than 1600 "must not be
    touched by the toggle" -- on the premise that only 1600 had a classic
    alternative.

    That premise stopped being true on 2026-08-17, when _voice_key was made
    to map EVERY band to the one synth cut so a driver on classic could not
    hear Jerry's recording at the other bands. Leaving the sounding band
    alone then meant the toggle silently did nothing on five of the six
    bands, and the voice you had just left kept playing (owner, 2026-08-19:
    "either the synthesized brake plays or the recorded one, not both").

    A loop on a NON-jake channel is still none of this toggle's business,
    which is what the guard checks now.
    """
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    try:
        a.set_jake_voice(False)
        # Asking for the 1800 band on "real" sounds the one recording -- that
        # is the routing. What this pins is that the toggle re-voices it.
        a.start_loop(audio.CH_JAKE, "engine/jake_1800", volume=0.4)
        assert a._impl._loops[audio.CH_JAKE][0] == audio.JAKE_RECORDED_KEY
        a.set_jake_voice(True)
        loop = a._impl._loops[audio.CH_JAKE]
        assert loop[0] == audio.JAKE_CLASSIC_KEY, "the 1800 band kept the old voice"
        assert loop[1] == 0.4
        a.stop_loop(audio.CH_JAKE)
    finally:
        a.shutdown()


def test_classic_voice_prefers_the_original_recording(monkeypatch):
    # Settings "classic" promises the 1.8.x engine. Its cut ships under its
    # own key (engine_classic/idle) precisely because the licensed overlay
    # owns engine/idle -- with the rebuilt bank installed the shared key is
    # the rebuilt cut, and classic must not quietly follow it.
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    assert audio._asset_bytes(audio.ENGINE_CLASSIC_LOOP_KEY, ("ogg", "wav")) is not None
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    impl = a._impl
    requested: list[str] = []
    real_sfx_stream = impl._sfx_stream

    def spying_sfx_stream(key, **kwargs):
        requested.append(key)
        return real_sfx_stream(key, **kwargs)

    monkeypatch.setattr(impl, "_sfx_stream", spying_sfx_stream)
    a.set_engine_voice(True)  # classic
    a.engine_start(play_start_sound=False)
    assert audio.ENGINE_CLASSIC_LOOP_KEY in requested
    assert impl._engine_bands == []
    assert impl._engine_stream is not None
    a.engine_stop()
    a.shutdown()


@needs_audio_assets
def test_bass_engine_falls_back_to_pitched_loop_without_cuts(monkeypatch):
    # A clean clone carries only the synthesized engine/idle: the ring cannot
    # form, and the legacy single pitched loop must come up instead.
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    impl = a._impl
    original = impl._sfx_stream

    def only_idle(key, looping=False):
        if key in {band_key for band_key, _rpm in audio.ENGINE_BANDS} - {"engine/idle"}:
            return None
        return original(key, looping)

    monkeypatch.setattr(impl, "_sfx_stream", only_idle)
    a.engine_start()
    assert a.engine_running
    assert impl._engine_bands == []
    assert impl._engine_stream is not None
    assert impl._engine_base_freq > 0
    for rpm in (600, 1500, 2200):
        a.set_engine_rpm(rpm, throttle=0.5)
    a.engine_stop()
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


@needs_audio_assets
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
    # The engine voice still comes up: the ring when the cuts are installed,
    # the legacy loop otherwise.
    assert impl._engine_bands or impl._engine_stream is not None
    a.engine_stop()
    a.shutdown()


@needs_audio_assets
def test_deliberate_engine_start_plays_crank_and_arms_crossfade(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")
    impl = a._impl
    keys = _record_sfx_keys(monkeypatch, impl)
    a.engine_start()  # deliberate ignition
    assert "engine/start" in keys
    # A crank fade-out, the loop fade-in, and the post-handoff load settle are
    # scheduled; the loop starts silent so the ignition is not drowned out, and
    # its load is boosted to full so it meets the crank tail without a dip.
    assert len(impl._fades) == 3
    assert impl._engine_intro_gain == 0.0
    assert impl._engine_intro_load == 1.0
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


@needs_audio_assets
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


@needs_audio_assets
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


@needs_audio_assets
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


@needs_audio_assets
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


@needs_audio_assets
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


@needs_audio_assets
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


@needs_audio_assets
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


def _bank_facade(monkeypatch, present: set[str]):
    """A facade with a fake asset universe, its plays recorded."""
    a = AudioEngine.__new__(AudioEngine)
    a._impl = audio._NullBackend()
    a._banks = {}
    a._bank_order = {}
    a._last_bank_key = {}
    a._asset_known = {}
    a._jake_voice_classic = False
    monkeypatch.setattr(
        audio, "_asset_bytes", lambda key, exts: (b"d", "ogg") if key in present else None
    )
    played: list[tuple[str, float]] = []
    monkeypatch.setattr(a, "play", lambda key, volume=1.0, pan=0.0: played.append((key, volume)))
    return a, played


def test_play_bank_cycles_every_cut_without_immediate_repeats(monkeypatch):
    cuts = {"vehicle/hit_01", "vehicle/hit_02", "vehicle/hit_03"}
    a, played = _bank_facade(monkeypatch, cuts)
    for _ in range(30):
        a.play_bank("vehicle/hit", "vehicle/fallback")
    keys = [key for key, _vol in played]
    assert set(keys) == cuts
    # Shuffled full cycles: every block of three is a permutation of the bank,
    # and no cut ever lands twice in a row across cycle seams.
    for i in range(0, 30, 3):
        assert set(keys[i : i + 3]) == cuts
    assert all(keys[i] != keys[i - 1] for i in range(1, 30))
    # The per-trigger level jitter stays inside its band.
    assert all(0.85 <= vol <= 1.17 for _key, vol in played)


def test_play_bank_falls_back_to_the_classic_cue(monkeypatch):
    a, played = _bank_facade(monkeypatch, set())
    a.play_bank("vehicle/hit", "vehicle/fallback", volume=0.6)
    assert played == [("vehicle/fallback", 0.6)]  # exact volume: no jitter on fallback


def test_has_asset_caches_the_lookup(monkeypatch):
    a, _played = _bank_facade(monkeypatch, {"vehicle/ebrake"})
    assert a.has_asset("vehicle/ebrake")
    assert not a.has_asset("vehicle/not_there")
    monkeypatch.setattr(audio, "_asset_bytes", lambda key, exts: None)
    assert a.has_asset("vehicle/ebrake")  # cached, not re-probed


def test_pygame_backend_does_not_play_reverse_loop_through_mixer(monkeypatch):
    backend = audio._PygameBackend.__new__(audio._PygameBackend)

    def fail_start_loop(*_args, **_kwargs):
        raise AssertionError("reverse cue must not use pygame.mixer")

    monkeypatch.setattr(backend, "start_loop", fail_start_loop)

    backend.reverse_start()
    backend.reverse_stop()


@needs_audio_assets
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


@needs_audio_assets
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


@needs_audio_assets
def test_bass_road_noise_frequency_changes_with_speed(monkeypatch):
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    if a.backend_name != "bass":
        pytest.skip("BASS backend unavailable")

    slides = []

    def fake_bass_call(fn, *args):
        if fn == a._impl._slide and args[1] == a._impl._ATTRIB_FREQ:
            slides.append(args[2])
        return fn(*args)

    a._impl._bass_call = fake_bass_call

    a.set_road_noise(15.0)
    assert len(slides) > 0
    base_freq = a._impl._loops[audio.CH_ROAD][2]._road_base_freq
    assert slides[-1] == pytest.approx(base_freq * 0.85)

    a.shutdown()


def test_the_classic_jake_voice_covers_every_rpm_band():
    """One voice per setting, whatever the rpm (owner, 2026-08-17: "it is
    playing both").

    The drive picks a cut per rpm band -- engine/jake_1200 through _2200 --
    and the classic voice is a single synthesized cut. The swap used to match
    only the exact 1600 key, so a driver on "classic" got the synth at 1600
    and the recorded cut at every other band; rpm moves constantly on a
    descent, so the two voices alternated.
    """
    from freight_fate.audio import JAKE_CLASSIC_KEY, JAKE_RECORDED_KEY, AudioEngine
    from freight_fate.states.driving_updates import JAKE_LOOP_RPMS

    engine = AudioEngine()
    try:
        bands = [f"engine/jake_{band}" for band in JAKE_LOOP_RPMS]

        engine._jake_voice_classic = True
        assert {engine._voice_key(k) for k in bands} == {JAKE_CLASSIC_KEY}

        engine._jake_voice_classic = False
        recorded = {engine._voice_key(k) for k in bands}
        # CORRECTED 2026-08-19. This asserted "the recorded voice keeps its
        # per-band cuts", and that belief left the bug half-fixed for two
        # days: those per-band cuts are SYNTHS. There is one real jake
        # recording, engine/jake_1600; 1200, 1400, 1800, 2000 and 2200 are
        # the older synthesized set. So "real" had the identical fault
        # mirrored -- the recording at 1600, a synth everywhere else -- and
        # the owner heard both voices whichever setting he chose. One voice
        # per setting has to mean one voice in BOTH directions.
        assert recorded == {JAKE_RECORDED_KEY}, (
            "real must collapse to the one recording too; the other bands are synths"
        )
        assert JAKE_CLASSIC_KEY not in recorded
    finally:
        engine.shutdown()


@needs_audio_assets
def test_the_jake_voice_switch_applies_on_every_band_not_just_1600(monkeypatch):
    """Owner, 2026-08-19: "either the synthesized brake plays or the recorded
    one, not both. Both is annoying."

    The live swap guarded on the sounding loop being JAKE_RECORDED_KEY or
    JAKE_CLASSIC_KEY -- the 1600 band. A descent runs 1200 through 2200, so
    flipping the setting on any other band did nothing at all: the voice you
    had just left kept sounding until rpm next crossed a boundary. One
    descent, both voices.
    """
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    try:
        a.set_jake_voice(False)
        # Growling on a band that is NOT 1600 -- the case the guard missed.
        # Asking for the 1400 band on "real" sounds the one recording -- that
        # is the routing, and the whole point of it.
        a.start_loop(audio.CH_JAKE, "engine/jake_1400", volume=0.5)
        assert a._impl._loops[audio.CH_JAKE][0] == audio.JAKE_RECORDED_KEY

        a.set_jake_voice(True)  # classic, live, mid-growl on 1400
        assert a._impl._loops[audio.CH_JAKE][0] == audio.JAKE_CLASSIC_KEY, (
            "the switch did nothing off the 1600 band"
        )
        assert a._impl._loops[audio.CH_JAKE][1] == 0.5  # level carries across

        a.set_jake_voice(False)  # back to real, live
        assert a._impl._loops[audio.CH_JAKE][0].startswith(audio.JAKE_BAND_PREFIX)
        a.stop_loop(audio.CH_JAKE)
    finally:
        a.shutdown()


def test_the_classic_jake_is_not_restarted_by_every_rpm_band(monkeypatch):
    """On classic every band maps to one synth cut, so a caller caching the
    BAND key saw each rpm crossing as a new sound and restarted the same file
    over itself -- 120 ms of crossfade at a time, all the way down a grade.
    ``voice_key`` exists so the drive can cache what will actually sound."""
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    try:
        a.set_jake_voice(True)
        bands = [f"engine/jake_{rpm}" for rpm in (1200, 1400, 1600, 1800, 2000, 2200)]
        assert len({a.voice_key(b) for b in bands}) == 1, (
            "the classic voice should resolve every band to one cut"
        )
        a.set_jake_voice(False)
        assert len({a.voice_key(b) for b in bands}) == 1, (
            "real must resolve to one voice too -- there is only one recording"
        )
    finally:
        a.shutdown()


def test_one_jake_voice_sounds_whatever_the_rpm_in_both_directions(monkeypatch):
    """Owner, 2026-08-19: "both the synth and the recording play when the jake
    is used despite the setting."

    There is exactly ONE real jake recording (engine/jake_1600). The other
    five band files -- 1200, 1400, 1800, 2000, 2200 -- are synths, kept from
    before it was made.

    2026-08-17 fixed the classic direction: every band maps to the synth, so
    "classic" stopped meaning "synth at 1600, the recording everywhere else".
    The REAL direction had the identical fault mirrored and was left alone --
    band keys passed straight through, so "real" meant the recording at 1600
    and a synth at every other band. Rpm moves constantly on a descent, so
    both voices sounded whichever setting was chosen.
    """
    monkeypatch.delenv("FREIGHT_FATE_AUDIO_BACKEND", raising=False)
    a = AudioEngine()
    try:
        bands = [f"engine/jake_{rpm}" for rpm in (1200, 1400, 1600, 1800, 2000, 2200)]

        a.set_jake_voice(False)
        assert {a.voice_key(b) for b in bands} == {audio.JAKE_RECORDED_KEY}

        a.set_jake_voice(True)
        assert {a.voice_key(b) for b in bands} == {audio.JAKE_CLASSIC_KEY}

        # The Learn game sounds entry demos the classic cut by name, so asking
        # for it explicitly must never be re-voiced into the other one.
        for classic in (False, True):
            a.set_jake_voice(classic)
            assert a.voice_key(audio.JAKE_CLASSIC_KEY) == audio.JAKE_CLASSIC_KEY
    finally:
        a.shutdown()
