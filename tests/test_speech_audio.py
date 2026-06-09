"""Speech fallback and audio engine tests (headless-safe)."""

from freight_fate.audio import ASSETS, AudioEngine
from freight_fate.speech import Speech


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
        r"""["']((?:ui|engine|vehicle|weather|ambient)/[a-z_]+)["']""")
    keys: set[str] = set()
    for py in src.rglob("*.py"):
        keys |= set(pattern.findall(py.read_text(encoding="utf-8")))
    assert keys, "expected to find sound keys in source"
    missing = [k for k in keys if not (ASSETS / f"{k}.wav").exists()]
    assert not missing, f"missing sound files: {missing}"


def test_music_tracks_exist():
    for track in ("menu_theme", "open_road", "night_haul"):
        assert (ASSETS / "music" / f"{track}.ogg").exists(), track
