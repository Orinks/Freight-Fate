"""Whether the real sound packs and the loose sound tree are on this machine.

The shipped audio lives in ``assets/sounds.pak`` and
``assets/music.pak`` (the ``music/`` subtree packs separately, see
``tools/assets_pack.py``). music.pak is not in the repository: at 250 MB it is
downloaded when a build needs it. The loose ``assets/sounds`` tree is
builder-local source material. Tests that need real audio content skip where
it is absent instead of failing on missing data.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ASSETS_DIR = Path(__file__).parents[1] / "assets"
_ASSETS_ROOT = _ASSETS_DIR / "sounds"
_SOUNDS_PACK_PATH = _ASSETS_DIR / "sounds.pak"
_MUSIC_PACK_PATH = _ASSETS_DIR / "music.pak"


def music_pack_available() -> bool:
    return _MUSIC_PACK_PATH.exists()


def audio_assets_available() -> bool:
    """Whether the real audio is reachable at all: the loose tree or sounds.pak."""
    return (_ASSETS_ROOT / "ui").exists() or _SOUNDS_PACK_PATH.exists()


needs_audio_assets = pytest.mark.skipif(
    not audio_assets_available(),
    reason="no audio assets: neither sounds.pak nor the builder-local loose sound tree is here",
)
