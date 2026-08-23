"""Tests for the masked sound pack used by frozen release builds."""

from __future__ import annotations

import hashlib
import os
import threading
import time
import zipfile
from pathlib import Path

import pytest
from asset_helpers import music_pack_available, needs_audio_assets

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


@needs_audio_assets
def test_committed_pack_has_freight_fate_header():
    assert assets_pack.DEFAULT_PACK_PATH.exists()
    pack_bytes = assets_pack.DEFAULT_PACK_PATH.read_bytes()
    # Repacked 2026-08-14 (weigh-station warning earcon): added the
    # procedural events/weigh_station_warning.ogg cue (owner ruling --
    # the scale gets its own earcon instead of reusing the shared
    # inspection cue). sounds.pak now holds 160 entries, the prior 159
    # preserved plus the one new asset.
    assert len(pack_bytes) == 7_781_859
    assert pack_bytes.startswith(assets_pack.PACK_MAGIC)
    assert hashlib.sha256(pack_bytes).hexdigest() == (
        "3ce9fc6b6fab461eebf3b75050c90c142e7d2e260178cf5b09b350afd066e7a2"
    )


@pytest.mark.skipif(
    not music_pack_available(),
    reason=(
        "music.pak not materialised (CI checks out without LFS: the pack is "
        "250 MB and fetching it per push exhausted the repository's budget). "
        "A pointer cannot be checked for the header it stands in for."
    ),
)
def test_committed_music_pack_has_freight_fate_header():
    assert assets_pack.DEFAULT_MUSIC_PACK_PATH.exists()
    pack_bytes = assets_pack.DEFAULT_MUSIC_PACK_PATH.read_bytes()
    # Split out of sounds.pak on 2026-08-14 alongside the radio
    # station-identity batch: 356 entries, the music/ subtree plus the new
    # station jingles and songs.
    assert len(pack_bytes) == 261_358_688
    assert pack_bytes.startswith(assets_pack.PACK_MAGIC)
    assert hashlib.sha256(pack_bytes).hexdigest() == (
        "3471842988e2bc01c259395d0b4d885b4c85a3a2d628efddf7a73006fd471c0a"
    )


@needs_audio_assets
def test_verify_sound_assets_passes_in_source_checkout():
    audio.verify_sound_assets()


def _reset_default_pack(monkeypatch, path: Path, music_path: Path | None = None) -> None:
    # Every caller here is testing pack behavior and wants packs enabled,
    # regardless of what conftest set based on this machine's loose tree
    # (it flips this on when assets/sounds/ui exists -- a builder-tree
    # sentinel these tests must not inherit).
    monkeypatch.delenv("FREIGHT_FATE_IGNORE_SOUND_PACK", raising=False)
    monkeypatch.setattr(assets_pack, "DEFAULT_PACK_PATH", path)
    monkeypatch.setattr(assets_pack, "_default_pack", None)
    monkeypatch.setattr(assets_pack, "_default_pack_missing", False)
    # Default to a path that is guaranteed not to exist, so a test that only
    # cares about the sounds side is not accidentally coupled to whatever the
    # real repo's music.pak happens to be (present or absent) right now.
    monkeypatch.setattr(
        assets_pack, "DEFAULT_MUSIC_PACK_PATH", music_path or path.parent / "__no_music_pack__.pak"
    )
    monkeypatch.setattr(assets_pack, "_default_music_pack", None)
    monkeypatch.setattr(assets_pack, "_default_music_pack_missing", False)
    monkeypatch.setattr(assets_pack, "_default_combined", None)
    monkeypatch.setattr(assets_pack, "_prefetch_started", False)


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


def test_prefetch_default_loads_once_for_concurrent_callers(tmp_path, monkeypatch):
    """The background prefetch and every racing open_default() caller must
    all see the one real load: the read-and-unmask work runs exactly once,
    and everyone gets the same SoundPack instance back."""
    sounds = _write_fixture_sounds(tmp_path)
    out = assets_pack.write_pack(sounds, tmp_path / "sounds.pak")
    _reset_default_pack(monkeypatch, out)

    calls: list[Path] = []
    real_init = assets_pack.SoundPack.__init__

    def slow_counting_init(self, path):
        calls.append(path)
        time.sleep(0.05)  # stand-in for the real ~0.3s read-and-unmask
        real_init(self, path)

    monkeypatch.setattr(assets_pack.SoundPack, "__init__", slow_counting_init)

    assets_pack.prefetch_default()

    results: list[assets_pack.SoundPack | None] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            results.append(assets_pack.open_default())
        except BaseException as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert not errors
    assert len(calls) == 1  # read off disk exactly once, not once per caller
    assert all(pack is results[0] for pack in results)
    assert results[0] is not None
    assert results[0].read("ui/menu_select.ogg") == b"fake ogg for menu select"


def test_prefetch_default_is_a_harmless_noop_when_called_twice(tmp_path, monkeypatch):
    sounds = _write_fixture_sounds(tmp_path)
    out = assets_pack.write_pack(sounds, tmp_path / "sounds.pak")
    _reset_default_pack(monkeypatch, out)
    assets_pack.prefetch_default()
    assets_pack.prefetch_default()  # must not start a second thread/load
    pack = assets_pack.open_default()
    assert pack is not None
    assert pack.read("ui/menu_select.ogg") == b"fake ogg for menu select"


@needs_loose_tree
def test_prefetch_with_unreadable_pack_still_falls_back_via_open_default(tmp_path, monkeypatch):
    # A corrupt pack found by the background prefetch must land exactly
    # where it does today: no pack, loose files answer, nothing raised.
    broken = tmp_path / "sounds.pak"
    broken.write_bytes(assets_pack.PACK_MAGIC + b"not a zip, only noise")
    _reset_default_pack(monkeypatch, broken)
    assets_pack.prefetch_default()
    assert assets_pack.open_default() is None
    found = audio._asset_bytes("ui/menu_select", ("ogg", "wav"))
    assert found is not None


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


def _write_split_fixture_packs(tmp_path: Path) -> tuple[Path, Path]:
    """A sounds.pak fixture and a separate music.pak fixture, disjoint keys."""
    sounds_src = tmp_path / "sounds_src"
    (sounds_src / "engine").mkdir(parents=True)
    (sounds_src / "engine" / "y.ogg").write_bytes(b"engine sound bytes")
    sounds_out = assets_pack.write_pack(sounds_src, tmp_path / "sounds.pak")

    music_src = tmp_path / "music_src"
    (music_src / "music").mkdir(parents=True)
    (music_src / "music" / "x.ogg").write_bytes(b"music track bytes")
    music_out = assets_pack.write_pack(music_src, tmp_path / "music.pak")
    return sounds_out, music_out


def test_loader_routes_music_names_to_music_pack(tmp_path, monkeypatch):
    sounds_out, music_out = _write_split_fixture_packs(tmp_path)
    _reset_default_pack(monkeypatch, sounds_out, music_path=music_out)

    combined = assets_pack.open_default()
    assert combined is not None
    assert combined.read("music/x.ogg") == b"music track bytes"
    assert combined.read("engine/y.ogg") == b"engine sound bytes"
    assert combined.has("music/x.ogg") and not combined.has("engine/x.ogg")
    assert combined.has("engine/y.ogg") and not combined.has("music/y.ogg")
    assert sorted(combined.names()) == ["engine/y.ogg", "music/x.ogg"]


def test_missing_music_pack_falls_back_while_sounds_pack_still_serves(tmp_path, monkeypatch):
    # assets_pack-level check: the music side of the combined pack answers
    # nothing when music.pak itself is missing, while the sounds side is
    # untouched -- audio._asset_bytes takes it from there to the loose tree.
    sounds_out, _music_out = _write_split_fixture_packs(tmp_path)
    missing_music = tmp_path / "no_music_here.pak"
    _reset_default_pack(monkeypatch, sounds_out, music_path=missing_music)

    combined = assets_pack.open_default()
    assert combined is not None  # the sounds side is still good
    assert combined.read("engine/y.ogg") == b"engine sound bytes"
    assert combined.read("music/x.ogg") is None
    assert combined.has("music/x.ogg") is False


@needs_loose_tree
def test_missing_music_pack_falls_back_to_loose_music_files(tmp_path, monkeypatch):
    # End to end through audio._asset_bytes: a real music key falls back to
    # the loose tree while an unrelated sounds.pak key still comes off the
    # pack -- the two packs fail independently.
    sounds = _write_fixture_sounds(tmp_path)
    sounds_out = assets_pack.write_pack(sounds, tmp_path / "sounds.pak")
    missing_music = tmp_path / "no_music_here.pak"
    _reset_default_pack(monkeypatch, sounds_out, music_path=missing_music)

    found = audio._asset_bytes("music/drive_always_around", ("opus", "ogg", "wav"))
    assert found is not None
    data, ext = found
    assert data == (SOUNDS_DIR / "music" / f"drive_always_around.{ext}").read_bytes()

    assert audio._asset_bytes("ui/menu_select", ("ogg", "wav")) == (
        b"fake ogg for menu select",
        "ogg",
    )
