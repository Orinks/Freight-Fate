"""Speech fallback and audio engine tests (headless-safe)."""

from dataclasses import dataclass, field

from freight_fate.audio import ASSETS, AudioEngine
from freight_fate.speech import Speech, pick_backend


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


def test_speech_disabled_by_env_is_silent_and_safe():
    s = Speech()
    assert not s.available
    assert s.backend_name == "none"
    s.say("hello")        # must not raise
    s.say("")             # empty text is fine
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
        r"""["']((?:ui|engine|vehicle|weather|ambient|driver)/[a-z_]+)["']""")
    keys: set[str] = set()
    for py in src.rglob("*.py"):
        keys |= set(pattern.findall(py.read_text(encoding="utf-8")))
    assert keys, "expected to find sound keys in source"
    missing = [k for k in keys if not (ASSETS / f"{k}.wav").exists()]
    assert not missing, f"missing sound files: {missing}"


def test_music_tracks_exist():
    for track in ("menu_theme", "open_road", "night_haul"):
        assert (ASSETS / "music" / f"{track}.ogg").exists(), track
