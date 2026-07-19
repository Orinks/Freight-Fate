"""Locating sound assets in tests the way the game locates them.

Audio assets are resolved by KEY plus a preference list of extensions (see
``audio._asset_bytes``), not by a fixed filename -- music ships as Ogg Opus
while the effects tree is still Ogg Vorbis, and a WAV occasionally survives.
Tests that assert "this asset exists" should ask the same question the loader
asks, otherwise a format migration breaks a pile of tests that were never
really about the format.
"""

from __future__ import annotations

from pathlib import Path

# Same order the audio layer prefers: the smallest modern format first, the
# older ones kept so a partial migration still resolves.
AUDIO_EXTENSIONS = ("opus", "ogg", "wav")


def find_asset(root, key: str):
    """The first existing file for ``key`` under ``root``, or None.

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
    return find_asset(root, key) is not None
