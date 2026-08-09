"""Locating sound assets in tests the way the game locates them.

Audio assets are resolved by KEY plus a preference list of extensions (see
``audio._asset_bytes``), not by a fixed filename -- music ships as Ogg Opus
while the effects tree is still Ogg Vorbis, and a WAV occasionally survives.
Tests that assert "this asset exists" should ask the same question the loader
asks, otherwise a format migration breaks a pile of tests that were never
really about the format.

The shipped audio lives in ``src/freight_fate/sounds.pak``; the loose
``assets/sounds`` tree is builder-local source material and is not in the
repo. These helpers consult the loose tree first (a builder's checkout) and
fall back to the committed pack, so the same assertions pass on a clean
clone and on the machine that authored the sounds.
"""

from __future__ import annotations

from pathlib import Path

# Same order the audio layer prefers: the smallest modern format first, the
# older ones kept so a partial migration still resolves.
AUDIO_EXTENSIONS = ("opus", "ogg", "wav")

_ASSETS_ROOT = Path(__file__).parents[1] / "src" / "freight_fate" / "assets" / "sounds"
_PACK_PATH = Path(__file__).parents[1] / "src" / "freight_fate" / "sounds.pak"
_pack = None


def _pack_instance():
    global _pack
    if _pack is None:
        import sys

        sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
        from freight_fate.assets_pack import SoundPack

        _pack = SoundPack(_PACK_PATH) if _PACK_PATH.exists() else False
    return _pack or None


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
    pack = _pack_instance()
    if prefix is None or pack is None:
        return False
    names = set(pack.names())
    return any(f"{prefix}{key}.{ext}" in names for ext in AUDIO_EXTENSIONS)


def asset_bytes(root, key: str) -> bytes | None:
    """Asset content for ``key`` from the loose tree or the shipped pack."""
    path = find_asset(root, key)
    if path is not None:
        return Path(str(path)).read_bytes()
    prefix = _pack_prefix(root)
    pack = _pack_instance()
    if prefix is None or pack is None:
        return None
    for ext in AUDIO_EXTENSIONS:
        data = pack.read(f"{prefix}{key}.{ext}")
        if data is not None:
            return data
    return None
