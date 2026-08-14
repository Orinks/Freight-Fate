"""Money-path tests for the plan-driven radio generation runners.

No network, no ffmpeg, no real assets touched: ``_post_bytes``,
``_mp3_bytes_to_samples``, ``_write_ogg``, and ``_subscription`` are all
monkeypatched to record calls and hand back tiny synthetic data instead of
talking to ElevenLabs, and every asset path is redirected into a pytest
``tmp_path``. What's still exercised for real is the part that matters for
a money-spending script: which station/ad/song produces which output
filename, whether an existing file is skipped or regenerated, and whether
a missing prerequisite (imaging SFX) fails loudly instead of spending.

tools/radio_generate_content.py and tools/generate_radio.py import each
other as bare sibling modules (each does its own
``sys.path.insert(0, <tools dir>)`` then a plain ``import``), not through
the ``tools.`` package prefix the other test files use for read-only
constant checks -- so this file mirrors that bare-import style to land
monkeypatches on the exact module objects the runners actually call into.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import generate_radio  # noqa: E402
import radio_content_plan  # noqa: E402
import radio_generate_content as rgc  # noqa: E402
from radio_content_plan import AdPlan, SongPlan, StationPlan  # noqa: E402

RATE = 44100
STUB_SAMPLES = np.linspace(-0.3, 0.3, 2205).astype(np.float64)  # 0.05s @ 44100

FAKE_VOICE_MAP = {"HostVoice": "voice-id-host", "AdVoice": "voice-id-ad"}

FAKE_STATION = StationPlan(
    station_id="test-teststation",
    name="Test Station",
    voice="HostVoice",
    voice_fallbacks=("Nobody", "Nobody Else"),
    persona="test persona",
    playlist="country",
    host_lines=("Line one for the test station.", "Line two for the test station."),
    id_lines=("T-E-S-T, Test Station, Testville.",),
    jingle_prompts=(
        ("id_teststation_01", "Ten second test jingle, singing the station name"),
        ("id_teststation_02", "Twelve second test jingle, singing it again"),
    ),
)
FAKE_STATIONS = {"teststation": FAKE_STATION}

FAKE_AD = AdPlan(
    key="ad_test_shop",
    business="Test Shop",
    voice="AdVoice",
    script="This is a short fake ad script, purely for testing the runner.",
    formats=("country",),
)
FAKE_AD_PLAN = (FAKE_AD,)

FAKE_SONG = SongPlan(
    key="radio_oldies_test_song",
    title="Test Song",
    description="fake song for testing",
    prompt="A fake test song prompt, doo-wop style",
    length_ms=5_000,
    instrumental=False,
)
FAKE_SONG_PLAN = {"oldies": (FAKE_SONG,)}

FAKE_SFX_PROMPTS = {
    "radio_imaging_whoosh_short": "fake whoosh prompt",
    "radio_imaging_riser": "fake riser prompt",
}


def _write_fake_sfx(sfx_dir: Path) -> None:
    sfx_dir.mkdir(parents=True, exist_ok=True)
    tone = (0.1 * np.sin(2.0 * np.pi * 440.0 * np.linspace(0.0, 0.05, 2205))).astype("float32")
    for name in ("radio_imaging_whoosh_short", "radio_imaging_riser"):
        sf.write(str(sfx_dir / f"{name}.ogg"), tone, RATE, format="OGG", subtype="VORBIS")


@pytest.fixture
def money_path(monkeypatch, tmp_path):
    """Redirect every asset path + the content plan into an isolated,
    disposable fixture, and fake out the three points that would otherwise
    touch the network or shell out to ffmpeg."""
    assets = tmp_path / "assets"
    music_dir = assets / "music"
    sfx_dir = assets / "radio" / "imaging"
    music_dir.mkdir(parents=True)

    voice_cache = tmp_path / "voices.json"
    voice_cache.write_text(json.dumps(FAKE_VOICE_MAP), encoding="utf-8")

    monkeypatch.setattr(rgc, "ASSETS", assets)
    monkeypatch.setattr(rgc, "SFX_DIR", sfx_dir)
    monkeypatch.setattr(rgc, "VOICE_CACHE", voice_cache)
    # _write_asset is called from here but defined in generate_radio.py, so
    # its "ASSETS / relpath" lookup resolves against generate_radio's own
    # globals, not radio_generate_content's -- both need patching or a real
    # run leaks files into the actual (gitignored, builder-local) asset tree.
    monkeypatch.setattr(generate_radio, "ASSETS", assets)

    monkeypatch.setattr(radio_content_plan, "STATIONS", FAKE_STATIONS)
    monkeypatch.setattr(radio_content_plan, "AD_PLAN", FAKE_AD_PLAN)
    monkeypatch.setattr(radio_content_plan, "SONG_PLAN", FAKE_SONG_PLAN)
    monkeypatch.setattr(radio_content_plan, "SFX_PROMPTS", FAKE_SFX_PROMPTS)

    post_calls: list[dict] = []

    def fake_post_bytes(url, key, body, timeout=600):
        post_calls.append({"url": url, "body": body, "timeout": timeout})
        return b"FAKE-MP3-BYTES"

    monkeypatch.setattr(rgc, "_post_bytes", fake_post_bytes)

    def fake_mp3_bytes_to_samples(mp3_bytes):
        return STUB_SAMPLES.copy(), RATE

    monkeypatch.setattr(rgc, "_mp3_bytes_to_samples", fake_mp3_bytes_to_samples)

    write_ogg_calls: list[Path] = []

    def fake_write_ogg(mp3_bytes, out):
        write_ogg_calls.append(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"FAKE-OGG-STUB")

    monkeypatch.setattr(rgc, "_write_ogg", fake_write_ogg)

    subscription_calls: list[str] = []
    counter = {"count": 1_000}

    def fake_subscription(key):
        subscription_calls.append(key)
        counter["count"] += 37
        return {"character_count": counter["count"], "character_limit": 1_000_000}

    monkeypatch.setattr(rgc, "_subscription", fake_subscription)

    return SimpleNamespace(
        assets=assets,
        music_dir=music_dir,
        sfx_dir=sfx_dir,
        post_calls=post_calls,
        write_ogg_calls=write_ogg_calls,
        subscription_calls=subscription_calls,
    )


# --- --plan-hosts -----------------------------------------------------------


def test_plan_hosts_filenames_and_resume(money_path):
    rgc.run_plan_hosts("fake-key", "teststation")

    assert (money_path.music_dir / "host_teststation_01.ogg").exists()
    assert (money_path.music_dir / "host_teststation_02.ogg").exists()
    assert len(money_path.post_calls) == 2  # one TTS call per host_line

    # Resume: both files already exist -> no new spend.
    money_path.post_calls.clear()
    rgc.run_plan_hosts("fake-key", "teststation")
    assert money_path.post_calls == []

    # --force regenerates regardless.
    rgc.run_plan_hosts("fake-key", "teststation", force=True)
    assert len(money_path.post_calls) == 2


def test_plan_hosts_unknown_station_fails_before_any_spend(money_path):
    with pytest.raises(SystemExit, match="Unknown station"):
        rgc.run_plan_hosts("fake-key", "not-a-real-station")
    assert money_path.post_calls == []


# --- --plan-ids ---------------------------------------------------------


def test_plan_ids_missing_sfx_names_the_flag(money_path):
    assert not money_path.sfx_dir.exists()
    with pytest.raises(SystemExit, match="--sfx"):
        rgc.run_plan_ids("fake-key", "teststation")
    assert money_path.post_calls == []  # fails before any TTS/Music spend


def test_plan_ids_filenames_follow_the_asset_key_and_03_contract(money_path):
    _write_fake_sfx(money_path.sfx_dir)

    rgc.run_plan_ids("fake-key", "teststation")

    music = money_path.music_dir
    assert (music / "id_teststation_03.ogg").exists(), "spoken ID at _03"
    assert (music / "id_teststation_01.ogg").exists(), "first jingle at its own asset_key"
    assert (music / "id_teststation_02.ogg").exists(), "second jingle at its own asset_key"
    # 1 spoken-ID TTS call + 2 jingle Music calls
    assert len(money_path.post_calls) == 3

    # Resume: everything already exists -> no new spend.
    money_path.post_calls.clear()
    rgc.run_plan_ids("fake-key", "teststation")
    assert money_path.post_calls == []

    # --force regenerates all three.
    rgc.run_plan_ids("fake-key", "teststation", force=True)
    assert len(money_path.post_calls) == 3


# --- --plan-ads -----------------------------------------------------------


def test_plan_ads_filename_is_the_full_ad_key(money_path):
    rgc.run_plan_ads("fake-key")

    assert (money_path.music_dir / "ad_test_shop.ogg").exists()
    assert len(money_path.post_calls) == 1

    money_path.post_calls.clear()
    rgc.run_plan_ads("fake-key")
    assert money_path.post_calls == []

    rgc.run_plan_ads("fake-key", force=True)
    assert len(money_path.post_calls) == 1


# --- --plan-songs -----------------------------------------------------------


def test_plan_songs_filename_is_the_song_key(money_path):
    rgc.run_plan_songs("fake-key", "oldies")

    assert (money_path.music_dir / "radio_oldies_test_song.ogg").exists()
    assert money_path.write_ogg_calls  # went through the raw-mp3 _write_ogg path

    money_path.post_calls.clear()
    rgc.run_plan_songs("fake-key", "oldies")
    assert money_path.post_calls == []


def test_plan_songs_unknown_pool_raises(money_path):
    with pytest.raises(SystemExit, match="Unknown song pool"):
        rgc.run_plan_songs("fake-key", "not-a-real-pool")
    assert money_path.post_calls == []


def _fake_song_pool(n: int) -> tuple:
    return tuple(
        SongPlan(
            key=f"radio_oldies_limit_song_{i}",
            title=f"Limit Song {i}",
            description="fake song for limit tests",
            prompt="A fake test song prompt, doo-wop style",
            length_ms=5_000,
            instrumental=False,
        )
        for i in range(n)
    )


def test_plan_songs_limit_stops_after_n_fresh_generations(money_path, monkeypatch, capsys):
    songs = _fake_song_pool(4)
    monkeypatch.setattr(radio_content_plan, "SONG_PLAN", {"oldies": songs})

    rgc.run_plan_songs("fake-key", "oldies", limit=2)

    assert (money_path.music_dir / f"{songs[0].key}.ogg").exists()
    assert (money_path.music_dir / f"{songs[1].key}.ogg").exists()
    assert not (money_path.music_dir / f"{songs[2].key}.ogg").exists()
    assert not (money_path.music_dir / f"{songs[3].key}.ogg").exists()
    assert len(money_path.post_calls) == 2

    out = capsys.readouterr().out
    assert "limit 2 reached, 2 of 4 pool songs remain ungenerated" in out


def test_plan_songs_limit_ignores_already_on_disk(money_path, monkeypatch):
    songs = _fake_song_pool(4)
    monkeypatch.setattr(radio_content_plan, "SONG_PLAN", {"oldies": songs})
    # Pre-existing file: must not count against the limit.
    (money_path.music_dir / f"{songs[0].key}.ogg").write_bytes(b"already-here")

    rgc.run_plan_songs("fake-key", "oldies", limit=2)

    assert (money_path.music_dir / f"{songs[0].key}.ogg").read_bytes() == b"already-here"
    assert (money_path.music_dir / f"{songs[1].key}.ogg").exists()  # fresh #1
    assert (money_path.music_dir / f"{songs[2].key}.ogg").exists()  # fresh #2
    assert not (money_path.music_dir / f"{songs[3].key}.ogg").exists()
    assert len(money_path.post_calls) == 2  # only the two fresh generations spend


def test_plan_songs_no_limit_is_byte_identical_to_before(money_path, monkeypatch):
    songs = _fake_song_pool(3)
    monkeypatch.setattr(radio_content_plan, "SONG_PLAN", {"oldies": songs})

    rgc.run_plan_songs("fake-key", "oldies")

    for song in songs:
        assert (money_path.music_dir / f"{song.key}.ogg").exists()
    assert len(money_path.post_calls) == 3


# --- --probe ----------------------------------------------------------------


def test_probe_respects_the_resume_gate(money_path):
    rgc.run_probe("fake-key")

    out = money_path.music_dir / "radio_oldies_test_song.ogg"
    assert out.exists()
    assert len(money_path.post_calls) == 1
    assert len(money_path.subscription_calls) == 2  # before + after

    # Re-run without --force: must NOT re-spend, but must still report the
    # subscription before/after (this is the fix for the HIGH finding --
    # previously a re-probe silently re-spent Music credits).
    money_path.post_calls.clear()
    money_path.subscription_calls.clear()
    rgc.run_probe("fake-key")
    assert money_path.post_calls == []
    assert len(money_path.subscription_calls) == 2

    # --force regenerates and re-measures.
    money_path.post_calls.clear()
    rgc.run_probe("fake-key", force=True)
    assert len(money_path.post_calls) == 1


# --- CLI argument parsing (generate_radio.py) --------------------------------


def test_cli_plan_ads_does_not_swallow_a_trailing_token(monkeypatch):
    """Regression guard: --plan-ads and --probe take no value, so a stray
    token after them must be rejected, not silently consumed as if it were
    an (unsupported) argument."""
    calls = []
    monkeypatch.setattr(rgc, "run_plan_ads", lambda key, force=False: calls.append(("ads", force)))
    monkeypatch.setattr(generate_radio, "_api_key", lambda: "fake-key")
    monkeypatch.setattr(generate_radio, "report_durations", lambda: None)

    with pytest.raises(SystemExit, match="Unrecognized argument"):
        generate_radio.main(["--plan-ads", "extra-token"])
    assert calls == []  # never reached dispatch


def test_cli_probe_does_not_swallow_a_trailing_token(monkeypatch):
    calls = []
    monkeypatch.setattr(rgc, "run_probe", lambda key, force=False: calls.append(("probe", force)))
    monkeypatch.setattr(generate_radio, "_api_key", lambda: "fake-key")
    monkeypatch.setattr(generate_radio, "report_durations", lambda: None)

    with pytest.raises(SystemExit, match="Unrecognized argument"):
        generate_radio.main(["--probe", "extra-token"])
    assert calls == []


def test_cli_rejects_unrecognized_flag_before_touching_the_api_key(monkeypatch):
    def boom():
        raise AssertionError("must not reach _api_key for a pure argument error")

    monkeypatch.setattr(generate_radio, "_api_key", boom)
    with pytest.raises(SystemExit, match="Unrecognized argument"):
        generate_radio.main(["--plan-hosts", "roadhouse", "--bogus-flag"])


def test_cli_probe_forwards_force(monkeypatch):
    calls = []
    monkeypatch.setattr(rgc, "run_probe", lambda key, force=False: calls.append(("probe", force)))
    monkeypatch.setattr(generate_radio, "_api_key", lambda: "fake-key")
    monkeypatch.setattr(generate_radio, "report_durations", lambda: None)

    generate_radio.main(["--probe", "--force"])
    assert calls == [("probe", True)]


# --- --limit N (only meaningful with --plan-songs) ---------------------------


def test_cli_limit_forwards_to_run_plan_songs(monkeypatch):
    calls = []
    monkeypatch.setattr(
        rgc,
        "run_plan_songs",
        lambda key, pool, force=False, limit=None: calls.append((pool, force, limit)),
    )
    monkeypatch.setattr(generate_radio, "_api_key", lambda: "fake-key")
    monkeypatch.setattr(generate_radio, "report_durations", lambda: None)

    generate_radio.main(["--plan-songs", "oldies", "--limit", "3"])
    assert calls == [("oldies", False, 3)]


def test_cli_plan_songs_without_limit_passes_limit_none(monkeypatch):
    calls = []
    monkeypatch.setattr(
        rgc,
        "run_plan_songs",
        lambda key, pool, force=False, limit=None: calls.append((pool, force, limit)),
    )
    monkeypatch.setattr(generate_radio, "_api_key", lambda: "fake-key")
    monkeypatch.setattr(generate_radio, "report_durations", lambda: None)

    generate_radio.main(["--plan-songs", "oldies"])
    assert calls == [("oldies", False, None)]


def test_cli_limit_without_plan_songs_exits(monkeypatch):
    monkeypatch.setattr(generate_radio, "_api_key", lambda: "fake-key")

    with pytest.raises(SystemExit, match="--limit is only meaningful together with --plan-songs"):
        generate_radio.main(["--limit", "3"])


def test_cli_limit_zero_exits(monkeypatch):
    with pytest.raises(SystemExit, match="positive integer"):
        generate_radio.main(["--plan-songs", "oldies", "--limit", "0"])


def test_cli_limit_non_integer_exits(monkeypatch):
    with pytest.raises(SystemExit, match="positive integer"):
        generate_radio.main(["--plan-songs", "oldies", "--limit", "abc"])


def test_cli_limit_missing_value_exits(monkeypatch):
    with pytest.raises(SystemExit, match="--limit requires a value"):
        generate_radio.main(["--plan-songs", "oldies", "--limit"])
