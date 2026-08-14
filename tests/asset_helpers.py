"""Locating sound assets in tests the way the game locates them.

Audio assets are resolved by KEY plus a preference list of extensions (see
``audio._asset_bytes``), not by a fixed filename -- music ships as Ogg Opus
while the effects tree is still Ogg Vorbis, and a WAV occasionally survives.
Tests that assert "this asset exists" should ask the same question the loader
asks, otherwise a format migration breaks a pile of tests that were never
really about the format.

The shipped audio lives in ``src/freight_fate/sounds.pak`` and
``src/freight_fate/music.pak`` (the ``music/`` subtree packs separately, see
``freight_fate.assets_pack``); the loose ``assets/sounds`` tree is
builder-local source material and is not in the repo. These helpers consult
the loose tree first (a builder's checkout) and fall back to whichever pack
owns the key -- music.pak for a ``music/...`` name when it exists, sounds.pak
otherwise -- so the same assertions pass on a clean clone and on the machine
that authored the sounds.
"""

from __future__ import annotations

from pathlib import Path

# Same order the audio layer prefers: the smallest modern format first, the
# older ones kept so a partial migration still resolves.
AUDIO_EXTENSIONS = ("opus", "ogg", "wav")

_ASSETS_ROOT = Path(__file__).parents[1] / "src" / "freight_fate" / "assets" / "sounds"
_SOUNDS_PACK_PATH = Path(__file__).parents[1] / "src" / "freight_fate" / "sounds.pak"
_MUSIC_PACK_PATH = Path(__file__).parents[1] / "src" / "freight_fate" / "music.pak"
_sounds_pack = None
_music_pack = None


def _load_pack(path: Path):
    import sys

    sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
    from freight_fate.assets_pack import SoundPack

    return SoundPack(path) if path.exists() else False


def _sounds_pack_instance():
    global _sounds_pack
    if _sounds_pack is None:
        _sounds_pack = _load_pack(_SOUNDS_PACK_PATH)
    return _sounds_pack or None


def _music_pack_instance():
    global _music_pack
    if _music_pack is None:
        _music_pack = _load_pack(_MUSIC_PACK_PATH)
    return _music_pack or None


def _pack_for(pack_relative_name: str):
    """The pack that owns ``pack_relative_name``, mirroring the runtime's own
    routing in ``assets_pack._CombinedPack``: a ``music/...`` name comes from
    music.pak when that pack exists, otherwise -- same as sounds.pak for
    every other name -- from sounds.pak (which still carries ``music/``
    itself until the real repack splits it out)."""
    if pack_relative_name.startswith("music/"):
        music = _music_pack_instance()
        if music is not None:
            return music
    return _sounds_pack_instance()


def _pack_prefix(root) -> str | None:
    """Pack-entry prefix for ``root`` when it points inside the assets tree."""
    try:
        rel = Path(str(root)).resolve().relative_to(_ASSETS_ROOT.resolve())
    except (ValueError, OSError):
        return None
    return "" if str(rel) == "." else rel.as_posix() + "/"


def find_asset(root, key: str):
    """The first existing loose file for ``key`` under ``root``, or None.

    ``root`` may be a Path or an importlib.resources Traversable, so this
    works for both the on-disk tree and the packaged resource tree.
    """
    for ext in AUDIO_EXTENSIONS:
        candidate = root / f"{key}.{ext}"
        exists = candidate.is_file() if hasattr(candidate, "is_file") else Path(candidate).exists()
        if exists:
            return candidate
    return None


def asset_exists(root, key: str) -> bool:
    if find_asset(root, key) is not None:
        return True
    prefix = _pack_prefix(root)
    if prefix is None:
        return False
    pack = _pack_for(f"{prefix}{key}")
    if pack is None:
        return False
    names = set(pack.names())
    return any(f"{prefix}{key}.{ext}" in names for ext in AUDIO_EXTENSIONS)


def asset_bytes(root, key: str) -> bytes | None:
    """Asset content for ``key`` from the loose tree or the shipped pack."""
    path = find_asset(root, key)
    if path is not None:
        return Path(str(path)).read_bytes()
    prefix = _pack_prefix(root)
    if prefix is None:
        return None
    pack = _pack_for(f"{prefix}{key}")
    if pack is None:
        return None
    for ext in AUDIO_EXTENSIONS:
        data = pack.read(f"{prefix}{key}.{ext}")
        if data is not None:
            return data
    return None
