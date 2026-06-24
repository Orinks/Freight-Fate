"""Speech fallback and audio engine tests (headless-safe)."""

from dataclasses import dataclass, field

from freight_fate.audio import ASSETS, AudioEngine
from freight_fate.speech import Speech, pick_backend, pick_event_backend


@dataclass
class FakeFeatures:
    is_supported_at_runtime: bool = True
    supports_output: bool = True
    supports_speak: bool = True


@dataclass
class FakeBackend:
    name: str
    priority: int
    features: FakeFeatures = field(default_factory=FakeFeatures)


class FakeContext:
    """Mimics prism.Context: a static, priority-ordered backend registry."""

    def __init__(self, backends: list[FakeBackend], best: str) -> None:
        self._backends = {b.name: b for b in backends}
        self._order = sorted(backends, key=lambda b: b.priority, reverse=True)
        self._best = best

    @property
    def backends_count(self) -> int:
        return len(self._order)

    def id_of(self, index_or_name):
        if isinstance(index_or_name, int):
            return self._order[index_or_name].name
        if index_or_name in self._backends:
            return index_or_name
        raise ValueError(index_or_name)

    def priority_of(self, backend_id) -> int:
        return self._backends[backend_id].priority

    def acquire(self, backend_id):
        return self._backends[backend_id]

    def acquire_best(self):
        return self._backends[self._best]


def registry(nvda_running: bool) -> FakeContext:
    """The shape of Prism's real registry: NVDA outranks everything even
    when it is not running."""
    return FakeContext(
        [
            FakeBackend("NVDA", 103, FakeFeatures(is_supported_at_runtime=nvda_running)),
            FakeBackend("JAWS", 100, FakeFeatures(is_supported_at_runtime=False)),
            FakeBackend("ONE_CORE", 98),
            FakeBackend("SAPI", 97),
        ],
        best="NVDA",
    )


def test_running_screen_reader_wins():
    assert pick_backend(registry(nvda_running=True)).name == "NVDA"


def test_falls_past_not_running_screen_readers():
    # NVDA is the registry's "best" but is not running: the highest-priority
    # backend that actually works at runtime must win instead.
    assert pick_backend(registry(nvda_running=False)).name == "ONE_CORE"


def test_env_override_is_honored():
    assert pick_backend(registry(nvda_running=False), "SAPI").name == "SAPI"


def test_unusable_override_falls_back_to_automatic_choice():
    assert pick_backend(registry(nvda_running=False), "JAWS").name == "ONE_CORE"
    assert pick_backend(registry(nvda_running=False), "NoSuch").name == "ONE_CORE"


def test_no_usable_backend_returns_none():
    ctx = FakeContext(
        [FakeBackend("NVDA", 103, FakeFeatures(is_supported_at_runtime=False))],
        best="NVDA",
    )
    assert pick_backend(ctx) is None


def test_backend_without_speak_or_output_is_skipped():
    ctx = FakeContext(
        [
            FakeBackend("BRAILLE_ONLY", 103,
                        FakeFeatures(supports_output=False, supports_speak=False)),
            FakeBackend("SAPI", 97),
        ],
        best="BRAILLE_ONLY",
    )
    assert pick_backend(ctx).name == "SAPI"


def test_event_channel_uses_sapi_alongside_the_screen_reader():
    ctx = registry(nvda_running=True)
    main = pick_backend(ctx)
    assert main.name == "NVDA"
    assert pick_event_backend(ctx, main).name == "SAPI"


def test_event_channel_skipped_when_main_voice_is_already_sapi():
    ctx = FakeContext(
        [
            FakeBackend("NVDA", 103, FakeFeatures(is_supported_at_runtime=False)),
            FakeBackend("SAPI", 97),
        ],
        best="NVDA",
    )
    main = pick_backend(ctx)
    assert main.name == "SAPI"
    assert pick_event_backend(ctx, main) is None


def test_event_channel_absent_when_sapi_is_unusable():
    ctx = FakeContext(
        [
            FakeBackend("NVDA", 103),
            FakeBackend("SAPI", 97, FakeFeatures(is_supported_at_runtime=False)),
        ],
        best="NVDA",
    )
    main = pick_backend(ctx)
    assert pick_event_backend(ctx, main) is None
    assert pick_event_backend(ctx, None) is None


@dataclass
class FakeParamFeatures:
    is_supported_at_runtime: bool = True
    supports_output: bool = True
    supports_speak: bool = True
    supports_set_rate: bool = False
    supports_set_pitch: bool = False
    supports_set_volume: bool = False
    supports_set_voice: bool = False
    supports_count_voices: bool = False
    supports_get_voice_name: bool = False


class RecordingBackend:
    """A backend that records the parameters Speech.configure pushes to it."""

    def __init__(self, name, voices, features):
        self.name = name
        self._voices = list(voices)
        self.features = features
        self.rate = None
        self.pitch = None
        self.volume = None
        self.voice = None
        self.spoken = []

    @property
    def voices_count(self):
        return len(self._voices)

    def get_voice_name(self, idx):
        return self._voices[idx]

    def output(self, text, interrupt=True):
        self.spoken.append((text, interrupt))

    def speak(self, text, interrupt=True):
        self.output(text, interrupt)


def _configurable_speech():
    """A Speech with an unsupported main voice and a fully adjustable event
    voice -- the common real layout (running NVDA plus a SAPI event voice)."""
    s = Speech()  # FREIGHT_FATE_NO_SPEECH (conftest) leaves it empty
    main = RecordingBackend("NVDA", [], FakeParamFeatures())
    event = RecordingBackend(
        "SAPI", ["David", "Zira"],
        FakeParamFeatures(supports_set_rate=True, supports_set_pitch=True,
                          supports_set_volume=True, supports_set_voice=True,
                          supports_count_voices=True, supports_get_voice_name=True))
    s._backend = main
    s._event_backend = event
    return s, main, event


def test_configure_pushes_params_to_supporting_backends_only():
    s, main, event = _configurable_speech()
    s.configure(rate=0.8, pitch=0.3, volume=0.5, voice="Zira")
    assert (event.rate, event.pitch, event.volume, event.voice) == (0.8, 0.3, 0.5, 1)
    # the unsupported main voice is left untouched
    assert (main.rate, main.pitch, main.volume, main.voice) == (None, None, None, None)


def test_adjustment_preview_uses_configurable_voice():
    s, main, event = _configurable_speech()

    assert s.say_adjustment_preview("speech_rate", "Speech rate: 60 percent.")

    assert main.spoken == []
    assert event.spoken == [("Speech rate: 60 percent.", True)]


def test_adjustment_preview_falls_back_when_setting_is_not_configurable():
    s, _main, _event = _configurable_speech()

    assert not s.say_adjustment_preview("speech_verbosity", "Speech verbosity: normal.")


def test_configure_preserves_onecore_default_pitch_at_midpoint():
    s = Speech()
    event = RecordingBackend(
        "OneCore", [],
        FakeParamFeatures(supports_set_rate=True, supports_set_pitch=True),
    )
    s._event_backend = event
    s.configure(rate=0.5, pitch=0.5)
    assert event.rate == 0.5
    assert event.pitch is None
    s.configure(pitch=0.7)
    assert event.pitch == 0.7


def test_supports_and_voice_names_reflect_backend_features():
    s, _main, _event = _configurable_speech()
    assert s.supports_rate and s.supports_pitch and s.supports_volume
    assert s.voice_names() == ["David", "Zira"]


def test_configure_skips_unknown_voice_name():
    s, _main, event = _configurable_speech()
    s.configure(voice="Nonexistent")
    assert event.voice is None


def test_no_configurable_backend_reports_no_support():
    s = Speech()
    s._backend = RecordingBackend("NVDA", [], FakeParamFeatures())
    s._event_backend = None
    assert not s.supports_rate
    assert not s.supports_pitch
    assert not s.supports_volume
    assert s.voice_names() == []
    s.configure(rate=0.9, voice="David")  # must not raise


def _multi_voice_ctx():
    """A registry shaped like a real Windows box with NVDA running: the screen
    reader plus two controllable software voices."""
    params = dict(supports_set_rate=True, supports_set_pitch=True,
                  supports_set_volume=True, supports_set_voice=True,
                  supports_count_voices=True, supports_get_voice_name=True)
    return FakeContext(
        [
            FakeBackend("NVDA", 103, FakeParamFeatures()),
            FakeBackend("OneCore", 98, FakeParamFeatures(**params)),
            FakeBackend("SAPI", 97, FakeParamFeatures(**params)),
        ],
        best="NVDA",
    )


def test_event_backend_options_lists_software_voices_by_priority():
    s = Speech()
    s._ctx = _multi_voice_ctx()
    s._backend = s._ctx.acquire("NVDA")  # the main voice is excluded
    assert s.event_backend_options() == ["OneCore", "SAPI"]


def test_select_event_backend_switches_and_clears():
    s = Speech()
    s._ctx = _multi_voice_ctx()
    s._backend = s._ctx.acquire("NVDA")
    s.select_event_backend("OneCore")
    assert s.event_backend_name == "OneCore"
    s.select_event_backend(None)               # back to the main voice
    assert s.event_backend_name == "none"
    # Asking for the main voice by name is not a real separate option, so the
    # preference falls back to the best available one (None is how you pick the
    # main voice for events).
    s.select_event_backend("NVDA")
    assert s.event_backend_name == "OneCore"


def test_event_backend_falls_back_to_platform_voice():
    # A macOS-shaped registry: VoiceOver running, AVSpeech as the software voice,
    # no SAPI. A Windows save's "SAPI" preference must still land on a real voice.
    params = dict(supports_set_rate=True, supports_set_pitch=True,
                  supports_set_volume=True, supports_set_voice=True,
                  supports_count_voices=True, supports_get_voice_name=True)
    ctx = FakeContext(
        [
            FakeBackend("VoiceOver", 103, FakeParamFeatures()),
            FakeBackend("AVSpeech", 98, FakeParamFeatures(**params)),
        ],
        best="VoiceOver",
    )
    s = Speech()
    s._ctx = ctx
    s._backend = ctx.acquire("VoiceOver")
    s.select_event_backend("SAPI")             # not on this machine
    assert s.event_backend_name == "AVSpeech"  # best available wins


def test_event_backend_none_when_no_separate_voice_exists():
    # Only a screen reader is usable: there is nothing to separate onto.
    ctx = FakeContext([FakeBackend("VoiceOver", 103, FakeParamFeatures())],
                      best="VoiceOver")
    s = Speech()
    s._ctx = ctx
    s._backend = ctx.acquire("VoiceOver")
    s.select_event_backend("SAPI")
    assert s.event_backend_name == "none"


def test_speech_disabled_by_env_is_silent_and_safe():
    s = Speech()
    assert not s.available
    assert s.backend_name == "none"
    assert s.event_backend_name == "none"
    s.say("hello")        # must not raise
    s.say("")             # empty text is fine
    s.say_event("hazard")  # falls back to the (absent) main voice safely
    s.stop()
    s.shutdown()
    s.shutdown()          # idempotent


def test_audio_engine_headless_noops():
    audio = AudioEngine()
    # with the dummy SDL driver the mixer may or may not init; either way
    # every call must be safe
    audio.play("ui/menu_select")
    audio.play("nonexistent/sound")
    audio.engine_start()
    audio.set_engine_rpm(1500, 0.5)
    audio.set_road_noise(20.0)
    audio.set_weather("weather/rain_light", 0.8)
    audio.set_wind(0.5)
    audio.play_music("menu_theme")
    audio.play_music("not_a_track")
    audio.set_volumes(master=0.5, sfx=0.5, music=0.5)
    audio.stop_world()
    audio.stop_music()
    audio.shutdown()


def test_all_referenced_assets_exist():
    """Every sound key used in the codebase must exist on disk."""
    import re
    from pathlib import Path

    src = Path(__file__).parents[1] / "src" / "freight_fate"
    pattern = re.compile(
        r"""["']((?:ui|engine|vehicle|weather|ambient|driver|events|facility|poi)/[a-z_]+)["']""")
    keys: set[str] = set()
    for py in src.rglob("*.py"):
        keys |= set(pattern.findall(py.read_text(encoding="utf-8")))
    assert keys, "expected to find sound keys in source"
    missing = [
        k for k in keys
        if not ((ASSETS / f"{k}.wav").exists() or (ASSETS / f"{k}.ogg").exists())
    ]
    assert not missing, f"missing sound files: {missing}"


def test_music_tracks_exist():
    from freight_fate.music import ALL_MUSIC_TRACKS

    for track in (track.key for track in ALL_MUSIC_TRACKS):
        assert (ASSETS / "music" / f"{track}.ogg").exists(), track
