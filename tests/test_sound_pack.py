"""Tests for the masked sound pack used by frozen release builds."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import assets_pack
import pytest
from asset_helpers import music_pack_available, needs_audio_assets

ROOT = Path(__file__).resolve().parents[1]
SOUNDS_DIR = ROOT / "assets" / "sounds"

# The loose sound tree is builder-local source material (the repo ships only
# sounds.pak). Fallback-path tests that read it run where it exists and skip
# on clean clones, where the pack is the only source.
needs_loose_tree = pytest.mark.skipif(
    not (SOUNDS_DIR / "ui").exists(),
    reason="builder-local loose sound tree not present",
)


def _write_fixture_sounds(tmp_path: Path) -> Path:
    sounds = tmp_path / "sounds"
    (sounds / "ui").mkdir(parents=True)
    (sounds / "music").mkdir()
    (sounds / "ui" / "menu_select.ogg").write_bytes(b"fake ogg for menu select")
    (sounds / "music" / "open_road.wav").write_bytes(b"fake wav for open road")
    return sounds


def test_pack_round_trips_files(tmp_path):
    sounds = _write_fixture_sounds(tmp_path)
    out = assets_pack.write_pack(sounds, tmp_path / "sounds.pak")
    pack = assets_pack.SoundPack(out)
    assert sorted(pack.names()) == ["music/open_road.wav", "ui/menu_select.ogg"]
    assert pack.read("ui/menu_select.ogg") == b"fake ogg for menu select"
    assert pack.read("music/open_road.wav") == b"fake wav for open road"
    assert pack.read("ui/not_there.ogg") is None


def test_pack_is_not_a_plain_zip_after_renaming(tmp_path):
    sounds = _write_fixture_sounds(tmp_path)
    out = assets_pack.write_pack(sounds, tmp_path / "sounds.pak")
    renamed = out.with_suffix(".zip")
    renamed.write_bytes(out.read_bytes())
    assert not zipfile.is_zipfile(renamed)
    raw = renamed.read_bytes()
    assert raw.startswith(assets_pack.PACK_MAGIC)
    assert b"menu_select" not in raw  # entry names are masked too


def test_pack_overlay_replaces_and_adds(tmp_path):
    sounds = _write_fixture_sounds(tmp_path)
    overlay = tmp_path / "licensed"
    (overlay / "ui").mkdir(parents=True)
    (overlay / "engine").mkdir()
    (overlay / "ui" / "menu_select.ogg").write_bytes(b"licensed menu select")
    (overlay / "engine" / "low.ogg").write_bytes(b"licensed engine low")
    out = assets_pack.write_pack(sounds, tmp_path / "sounds.pak", overlay_dir=overlay)
    pack = assets_pack.SoundPack(out)
    assert pack.read("ui/menu_select.ogg") == b"licensed menu select"  # replaced
    assert pack.read("engine/low.ogg") == b"licensed engine low"  # added
    assert pack.read("music/open_road.wav") == b"fake wav for open road"  # untouched


def test_pack_overlay_wins_by_key_across_extensions(tmp_path):
    # The loader tries ogg before wav inside the pack, so a committed ogg
    # fallback must not ship beside a licensed wav for the same key.
    sounds = _write_fixture_sounds(tmp_path)
    overlay = tmp_path / "licensed"
    (overlay / "ui").mkdir(parents=True)
    (overlay / "ui" / "menu_select.wav").write_bytes(b"licensed wav")
    out = assets_pack.write_pack(sounds, tmp_path / "sounds.pak", overlay_dir=overlay)
    pack = assets_pack.SoundPack(out)
    assert pack.read("ui/menu_select.wav") == b"licensed wav"
    assert pack.read("ui/menu_select.ogg") is None  # stale-extension twin dropped


def test_pack_excludes_editor_backups(tmp_path):
    # A jake .bak from a builder's loose tree once rode into a released pack;
    # backups stay out of the payload, from the committed tree and the
    # licensed overlay both.
    sounds = _write_fixture_sounds(tmp_path)
    (sounds / "ui" / "menu_select.ogg.bak").write_bytes(b"stale backup")
    overlay = tmp_path / "licensed"
    (overlay / "engine").mkdir(parents=True)
    (overlay / "engine" / "low.ogg").write_bytes(b"licensed engine low")
    (overlay / "engine" / "jake.synth-original.wav.bak").write_bytes(b"synth original")
    out = assets_pack.write_pack(sounds, tmp_path / "sounds.pak", overlay_dir=overlay)
    names = assets_pack.SoundPack(out).names()
    assert not [name for name in names if name.endswith(".bak")]
    assert "engine/low.ogg" in names
    assert "ui/menu_select.ogg" in names


def test_pack_missing_overlay_dir_is_fine(tmp_path):
    sounds = _write_fixture_sounds(tmp_path)
    out = assets_pack.write_pack(
        sounds, tmp_path / "sounds.pak", overlay_dir=tmp_path / "not_there"
    )
    assert sorted(assets_pack.SoundPack(out).names()) == [
        "music/open_road.wav",
        "ui/menu_select.ogg",
    ]


def test_pack_is_deterministic(tmp_path):
    sounds = _write_fixture_sounds(tmp_path)
    first = assets_pack.write_pack(sounds, tmp_path / "a.pak").read_bytes()
    second = assets_pack.write_pack(sounds, tmp_path / "b.pak").read_bytes()
    assert first == second


@needs_audio_assets
def test_committed_pack_has_freight_fate_header():
    assert assets_pack.DEFAULT_PACK_PATH.exists()
    pack_bytes = assets_pack.DEFAULT_PACK_PATH.read_bytes()
    # Repacked 2026-09-11 (traffic cues): the eleven pass and crossing cues
    # added on 2026-08-20 (pickup, motorcycle, bus, tractor passes; car,
    # pickup, box truck, semi, motorcycle, bus, tractor crossings) were
    # regenerated through the ElevenLabs Sound Effects API and MERGED into the
    # shipped pack, 162 -> 173 entries. The eleven were never in the pack
    # before (the numpy stand-ins only ever lived in the loose tree), so the
    # prior 162 are preserved byte for byte.
    #
    # Repacked 2026-08-29 (the scale verdict tones): added the procedural
    # events/scale_green.ogg and events/scale_red.ogg cues, which the code and
    # the sound catalog both named while the pack carried neither -- and the
    # release ships THIS pack rather than baking a fresh one, so both lights
    # changed in silence for players. 162 entries, the prior 160 preserved
    # byte for byte plus the two new assets.
    #
    # Merged into rather than rebuilt, deliberately: a plain
    # tools/pack_sounds.py run on the current builder machine yields 113
    # entries, because 60 API-generated effects are no longer in the loose
    # tree. Re-baking here would silently drop them.
    #
    # Repacked 2026-08-14 (weigh-station warning earcon): added the procedural
    # events/weigh_station_warning.ogg cue, taking the pack 159 -> 160.
    assert len(pack_bytes) == 8_278_280
    assert pack_bytes.startswith(assets_pack.PACK_MAGIC)
    assert hashlib.sha256(pack_bytes).hexdigest() == (
        "33e35cab8258f5eccaf5553d698ffcfca24d65e986bd579f24579250a981bae6"
    )


@pytest.mark.skipif(
    not music_pack_available(),
    reason=(
        "music.pak is not in the repository: at 250 MB it is downloaded from "
        "a private release URL when needed, so only a builder machine holding "
        "it can check the header it stands in for."
    ),
)
def test_committed_music_pack_has_freight_fate_header():
    assert assets_pack.DEFAULT_MUSIC_PACK_PATH.exists()
    pack_bytes = assets_pack.DEFAULT_MUSIC_PACK_PATH.read_bytes()
    # Repacked 2026-09-19: 25 selected songs, preserving all 380 prior entries.
    # Repacked 2026-09-13 for two owner-supplied instrumentals, D-Major
    # Medley (a menu bed) and From Bossa to Blues (a day drive bed):
    # 378 -> 380 entries, merged into the prior pack.
    #
    # Repacked 2026-09-11 for the gospel, tejano, synthwave and Night Line
    # song batch (nineteen songs, see CHANGELOG Unreleased): 359 -> 378
    # entries, merged into the prior pack rather than rebuilt.
    #
    # Repacked 2026-08-30 for "Four Sources and the Truth" (a country song
    # about trusting the forecast): 358 -> 359 entries. Before that,
    # 356 -> 358 on 2026-08-26 for "Dangerous Dan" and "Dial-up Summer".
    #
    # Split out of sounds.pak on 2026-08-14 alongside the radio
    # station-identity batch: 356 entries, the music/ subtree plus the new
    # station jingles and songs.
    assert len(pack_bytes) == 367_493_532
    assert pack_bytes.startswith(assets_pack.PACK_MAGIC)
    assert hashlib.sha256(pack_bytes).hexdigest() == (
        "5d72f39a56320a147e0061122c3426ab9e920c388ac0bb1f67ed1ce72e976fc0"
    )


def test_damaged_entry_costs_only_its_own_sound(tmp_path, monkeypatch):
    sounds = _write_fixture_sounds(tmp_path)
    out = assets_pack.write_pack(sounds, tmp_path / "sounds.pak")
    pack = assets_pack.SoundPack(out)

    real_read = pack._zip.read

    def read(name):
        if name == "ui/menu_select.ogg":
            raise zipfile.BadZipFile("bad CRC")
        return real_read(name)

    monkeypatch.setattr(pack._zip, "read", read)
    assert pack.read("ui/menu_select.ogg") is None  # damaged, reported as absent
    assert pack.read("music/open_road.wav") == b"fake wav for open road"  # unharmed


@needs_loose_tree
def test_real_assets_tree_round_trips(tmp_path):
    out = assets_pack.write_pack(SOUNDS_DIR, tmp_path / "sounds.pak")
    pack = assets_pack.SoundPack(out)
    files = [path for path in SOUNDS_DIR.rglob("*") if path.is_file()]
    assert sorted(pack.names()) == sorted(path.relative_to(SOUNDS_DIR).as_posix() for path in files)
    sample = next(path for path in files if path.suffix in (".ogg", ".wav"))
    assert pack.read(sample.relative_to(SOUNDS_DIR).as_posix()) == sample.read_bytes()


# -- music/sounds pack split (2026-08-14) -------------------------------------


def _load_pack_sounds_tool():
    """Import tools/pack_sounds.py by path (tools is not a package)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("pack_sounds", ROOT / "tools" / "pack_sounds.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pack_sounds_tool_splits_music_into_its_own_pack(tmp_path):
    sounds = tmp_path / "sounds"
    (sounds / "music").mkdir(parents=True)
    (sounds / "engine").mkdir()
    (sounds / "music" / "x.ogg").write_bytes(b"music track bytes")
    (sounds / "engine" / "y.ogg").write_bytes(b"engine sound bytes")
    pack_sounds = _load_pack_sounds_tool()

    sounds_out, music_out = pack_sounds.pack(
        sounds_dir=sounds,
        output=tmp_path / "out" / "sounds.pak",
        music_output=tmp_path / "out" / "music.pak",
        # No overlay dir under this tmp tree, so the split is not at the
        # mercy of whatever licensed overlay the builder machine happens to have.
        overlay_dir=tmp_path / "no-overlay-here",
    )

    sounds_pack = assets_pack.SoundPack(sounds_out)
    music_pack = assets_pack.SoundPack(music_out)
    assert sounds_pack.names() == ["engine/y.ogg"]
    assert music_pack.names() == ["music/x.ogg"]
    assert sounds_pack.read("engine/y.ogg") == b"engine sound bytes"
    assert music_pack.read("music/x.ogg") == b"music track bytes"
