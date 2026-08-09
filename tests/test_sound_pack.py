"""Tests for the masked sound pack used by frozen release builds."""

from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import Path

import pytest

from freight_fate import assets_pack, audio

ROOT = Path(__file__).resolve().parents[1]
SOUNDS_DIR = ROOT / "src" / "freight_fate" / "assets" / "sounds"

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


def test_pack_missing_overlay_dir_is_fine(tmp_path):
    sounds = _write_fixture_sounds(tmp_path)
    out = assets_pack.write_pack(
        sounds, tmp_path / "sounds.pak", overlay_dir=tmp_path / "not_there"
    )
    assert sorted(assets_pack.SoundPack(out).names()) == [
        "music/open_road.wav",
        "ui/menu_select.ogg",
    ]


def test_asset_path_prefers_licensed_overlay(tmp_path, monkeypatch):
    base = _write_fixture_sounds(tmp_path)
    overlay = tmp_path / "licensed"
    (overlay / "ui").mkdir(parents=True)
    # Overlay wins even across the extension preference order: its .wav beats
    # the base tree's .ogg for the same key.
    (overlay / "ui" / "menu_select.wav").write_bytes(b"licensed wav")
    monkeypatch.setattr(audio, "ASSETS", base)
    monkeypatch.setattr(audio, "ASSETS_LICENSED", overlay)
    found = audio._asset_path("ui/menu_select", ("ogg", "wav"))
    assert found == overlay / "ui" / "menu_select.wav"
    # Keys the overlay does not carry still resolve from the base tree.
    assert audio._asset_path("music/open_road", ("ogg", "wav")) is not None


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


@needs_loose_tree
def test_asset_bytes_reads_loose_files_without_pack():
    # The test environment explicitly exercises the loose-file fallback.
    assert os.environ["FREIGHT_FATE_IGNORE_SOUND_PACK"] == "1"
    found = audio._asset_bytes("ui/menu_select", ("ogg", "wav"))
    assert found is not None
    data, ext = found
    assert data == (SOUNDS_DIR / "ui" / f"menu_select.{ext}").read_bytes()


def test_committed_pack_has_freight_fate_header():
    assert assets_pack.DEFAULT_PACK_PATH.exists()
    pack_bytes = assets_pack.DEFAULT_PACK_PATH.read_bytes()
    assert len(pack_bytes) == 224_884_245
    assert pack_bytes.startswith(assets_pack.PACK_MAGIC)
    assert hashlib.sha256(pack_bytes).hexdigest() == (
        "cad82d380f73c98a6cfb84527ee09f59c6579dfac8a9fddb5200100a7f85a3b3"
    )


def test_verify_sound_assets_passes_in_source_checkout():
    audio.verify_sound_assets()


def _reset_default_pack(monkeypatch, path: Path) -> None:
    monkeypatch.setattr(assets_pack, "DEFAULT_PACK_PATH", path)
    monkeypatch.setattr(assets_pack, "_default_pack", None)
    monkeypatch.setattr(assets_pack, "_default_pack_missing", False)


@needs_loose_tree
def test_unreadable_pack_falls_back_to_loose_files(tmp_path, monkeypatch):
    # A truncated or half-copied pack must not take the sound with it: a
    # source checkout still has the real tree, and it has to keep playing.
    broken = tmp_path / "sounds.pak"
    broken.write_bytes(assets_pack.PACK_MAGIC + b"not a zip, only noise")
    _reset_default_pack(monkeypatch, broken)
    assert assets_pack.open_default() is None
    found = audio._asset_bytes("ui/menu_select", ("ogg", "wav"))
    assert found is not None
    audio.verify_sound_assets()


@needs_loose_tree
def test_pack_from_another_program_falls_back_to_loose_files(tmp_path, monkeypatch):
    # Wrong magic entirely -- someone renamed an unrelated file into place.
    stranger = tmp_path / "sounds.pak"
    stranger.write_bytes(b"PK\x03\x04 whatever this is")
    _reset_default_pack(monkeypatch, stranger)
    assert assets_pack.open_default() is None
    assert audio._asset_bytes("ui/menu_select", ("ogg", "wav")) is not None


@needs_loose_tree
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

    # And the loader treats that absence as a miss, so the loose tree answers.
    monkeypatch.setattr(assets_pack, "open_default", lambda: pack)
    found = audio._asset_bytes("ui/menu_select", ("ogg", "wav"))
    assert found is not None
    assert found[0] == (SOUNDS_DIR / "ui" / f"menu_select.{found[1]}").read_bytes()


def _pack_with_partial_ring(tmp_path: Path) -> assets_pack.SoundPack:
    """A pack carrying every engine band but one -- an older pack's ring."""
    sounds = _write_fixture_sounds(tmp_path)
    (sounds / "engine").mkdir()
    for key in sorted(audio.ENGINE_BAND_KEYS):
        if key == "engine/midhigh":
            continue  # the band the checkout added later
        name = key.split("/", 1)[1]
        (sounds / "engine" / f"{name}.ogg").write_bytes(f"old {name} band".encode())
    return assets_pack.SoundPack(assets_pack.write_pack(sounds, tmp_path / "sounds.pak"))


@needs_loose_tree
def test_partial_ring_in_pack_is_not_blended_with_the_loose_tree(tmp_path, monkeypatch):
    # Bands crossfade into each other, so a pack that is missing one band must
    # not supply the other four: the whole ring comes off the loose tree.
    pack = _pack_with_partial_ring(tmp_path)
    monkeypatch.setattr(assets_pack, "open_default", lambda: pack)
    for key in sorted(audio.ENGINE_BAND_KEYS):
        found = audio._asset_bytes(key, ("ogg", "wav"))
        assert found is not None, key
        data, ext = found
        assert not data.startswith(b"old "), f"{key} came from the partial pack"
        # Whichever loose file answers -- licensed overlay or committed tree.
        loose = audio._asset_path(key, ("ogg", "wav"))
        assert loose is not None and loose.suffix == f".{ext}"
        assert data == loose.read_bytes()
    # Everything outside the ring still prefers the pack, as before.
    assert audio._asset_bytes("ui/menu_select", ("ogg", "wav")) == (
        b"fake ogg for menu select",
        "ogg",
    )


def test_complete_ring_in_pack_is_used(tmp_path, monkeypatch):
    sounds = _write_fixture_sounds(tmp_path)
    (sounds / "engine").mkdir()
    for key in sorted(audio.ENGINE_BAND_KEYS):
        name = key.split("/", 1)[1]
        (sounds / "engine" / f"{name}.ogg").write_bytes(f"packed {name} band".encode())
    pack = assets_pack.SoundPack(assets_pack.write_pack(sounds, tmp_path / "sounds.pak"))
    monkeypatch.setattr(assets_pack, "open_default", lambda: pack)
    for key in sorted(audio.ENGINE_BAND_KEYS):
        name = key.split("/", 1)[1]
        assert audio._asset_bytes(key, ("ogg", "wav")) == (f"packed {name} band".encode(), "ogg")


@needs_loose_tree
def test_older_pack_still_serves_the_keys_it_has(tmp_path, monkeypatch):
    # munchkinbear's case: an older pack alongside a current checkout. Keys the
    # old pack carries play from it; keys added since come off the loose tree.
    old = _write_fixture_sounds(tmp_path)
    pack = assets_pack.SoundPack(assets_pack.write_pack(old, tmp_path / "sounds.pak"))
    monkeypatch.setattr(assets_pack, "open_default", lambda: pack)
    assert audio._asset_bytes("ui/menu_select", ("ogg", "wav")) == (
        b"fake ogg for menu select",
        "ogg",
    )
    newer = audio._asset_bytes("vehicle/edge_strip", ("ogg", "wav"))
    assert newer is not None  # not in the old pack; comes from the checkout


@needs_loose_tree
def test_real_assets_tree_round_trips(tmp_path):
    out = assets_pack.write_pack(SOUNDS_DIR, tmp_path / "sounds.pak")
    pack = assets_pack.SoundPack(out)
    files = [path for path in SOUNDS_DIR.rglob("*") if path.is_file()]
    assert sorted(pack.names()) == sorted(path.relative_to(SOUNDS_DIR).as_posix() for path in files)
    sample = next(path for path in files if path.suffix in (".ogg", ".wav"))
    assert pack.read(sample.relative_to(SOUNDS_DIR).as_posix()) == sample.read_bytes()
