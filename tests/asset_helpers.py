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

import pytest

# Same order the audio layer prefers: the smallest modern format first, the
# older ones kept so a partial migration still resolves.
AUDIO_EXTENSIONS = ("opus", "ogg", "wav")

_ASSETS_ROOT = Path(__file__).parents[1] / "src" / "freight_fate" / "assets" / "sounds"
_SOUNDS_PACK_PATH = Path(__file__).parents[1] / "src" / "freight_fate" / "sounds.pak"
_MUSIC_PACK_PATH = Path(__file__).parents[1] / "src" / "freight_fate" / "music.pak"
_sounds_pack = None
_music_pack = None


# A Git LFS pointer is a ~130 byte text stub standing in for the real file,
# and it EXISTS -- so an existence check alone reads an unmaterialised pack as
# present and every asset lookup then fails against something that is not a
# pack at all. CI checks out without LFS on purpose (see .github/workflows/
# ci.yml: the music pack is 250 MB and fetching it per push exhausted the
# repository's LFS budget), so this is the ordinary case there, not an error.
_LFS_POINTER_MAGIC = b"version https://git-lfs"


def _is_lfs_pointer(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(len(_LFS_POINTER_MAGIC)) == _LFS_POINTER_MAGIC
    except OSError:
        return False


def pack_available(path: Path) -> bool:
    """Whether a pack is really here, rather than an LFS pointer to it."""
    return path.exists() and not _is_lfs_pointer(path)


def sounds_pack_available() -> bool:
    return pack_available(_SOUNDS_PACK_PATH)


def music_pack_available() -> bool:
    return pack_available(_MUSIC_PACK_PATH)


def loose_sound_tree_available() -> bool:
    """Builder machines carry the loose tree; it is not in the repo."""
    return (_ASSETS_ROOT / "ui").exists()


def audio_assets_available() -> bool:
    """Whether the real audio is reachable at all, by either route.

    What a test that asserts "every catalog entry has a file" actually needs.
    False on a clone with neither the loose tree nor a materialised pack,
    where that assertion is about missing DATA rather than a missing sound.
    """
    return loose_sound_tree_available() or sounds_pack_available()


# Ready-made markers for the tests that need real audio content rather than a
# fixture they build themselves. CI checks out without LFS on purpose (see the
# note above), so on a runner these skip and on a builder machine -- or any
# clone with the packs materialised -- they run in full. Without them the same
# tests fail against a 130 byte pointer, which reads as "the audio is broken"
# when the truth is "the audio was never fetched".
needs_audio_assets = pytest.mark.skipif(
    not audio_assets_available(),
    reason=(
        "no audio assets: sounds.pak is an unmaterialised LFS pointer and the "
        "loose sound tree is builder-local. Fetch with "
        "`git lfs pull --include=src/freight_fate/sounds.pak` to run this."
    ),
)

needs_music_pack = pytest.mark.skipif(
    not music_pack_available(),
    reason=(
        "music.pak not materialised (250 MB; CI checks out without LFS). "
        "Fetch with `git lfs pull --include=src/freight_fate/music.pak`."
    ),
)


def _load_pack(path: Path):
    import sys

    sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
    from freight_fate.assets_pack import SoundPack

    return SoundPack(path) if pack_available(path) else False


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
    music.pak when that pack exists, otherwise from sounds.pak.

    That fallback no longer finds anything. The split has happened: sounds.pak
    carries no ``music/`` entries at all, and music.pak is not in the
    repository. So a ``music/...`` lookup resolves only where the music pack
    is, which is why a test that reads one has to be marked
    ``needs_music_pack`` rather than ``needs_audio_assets`` -- the latter is
    satisfied by sounds.pak and would let the test run somewhere the music
    can never be found.
    """
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
