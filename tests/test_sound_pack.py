"""Tests for the masked sound pack used by frozen release builds."""

from __future__ import annotations

import zipfile
from pathlib import Path

from freight_fate import assets_pack, audio

ROOT = Path(__file__).resolve().parents[1]
SOUNDS_DIR = ROOT / "src" / "freight_fate" / "assets" / "sounds"


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


def test_pack_is_deterministic(tmp_path):
    sounds = _write_fixture_sounds(tmp_path)
    first = assets_pack.write_pack(sounds, tmp_path / "a.pak").read_bytes()
    second = assets_pack.write_pack(sounds, tmp_path / "b.pak").read_bytes()
    assert first == second


def test_asset_bytes_prefers_pack(tmp_path, monkeypatch):
    sounds = _write_fixture_sounds(tmp_path)
    pack = assets_pack.SoundPack(assets_pack.write_pack(sounds, tmp_path / "sounds.pak"))
    monkeypatch.setattr(assets_pack, "open_default", lambda: pack)
    found = audio._asset_bytes("ui/menu_select", ("ogg", "wav"))
    assert found == (b"fake ogg for menu select", "ogg")


def test_asset_bytes_reads_loose_files_without_pack():
    # Source checkouts never have a pack file; the loose tree is the source.
    assert not assets_pack.DEFAULT_PACK_PATH.exists()
    found = audio._asset_bytes("ui/menu_select", ("ogg", "wav"))
    assert found is not None
    data, ext = found
    assert data == (SOUNDS_DIR / "ui" / f"menu_select.{ext}").read_bytes()


def test_verify_sound_assets_passes_in_source_checkout():
    audio.verify_sound_assets()


def test_real_assets_tree_round_trips(tmp_path):
    out = assets_pack.write_pack(SOUNDS_DIR, tmp_path / "sounds.pak")
    pack = assets_pack.SoundPack(out)
    files = [path for path in SOUNDS_DIR.rglob("*") if path.is_file()]
    assert sorted(pack.names()) == sorted(path.relative_to(SOUNDS_DIR).as_posix() for path in files)
    sample = next(path for path in files if path.suffix in (".ogg", ".wav"))
    assert pack.read(sample.relative_to(SOUNDS_DIR).as_posix()) == sample.read_bytes()
