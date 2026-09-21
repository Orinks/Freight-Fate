"""Pack the sound assets into masked files for frozen builds.

The release build (``tools/build_release.py``) runs this so the shipped
game carries ``freight_fate/sounds.pak`` and ``freight_fate/music.pak``
instead of a browsable sounds folder -- the ``music/`` subtree packs
separately so the small SFX payload does not travel with the much larger
music library on every change. Source checkouts keep the loose, editable
``assets/sounds`` tree; the audio engine only reads a pack when it exists.

Run from the repository root: ``uv run python tools/pack_sounds.py``
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
SOUNDS_DIR = SRC_DIR / "freight_fate" / "assets" / "sounds"
# Licensed overlay (gitignored): packed over the committed tree when present.
LICENSED_DIR = SRC_DIR / "freight_fate" / "assets" / "sounds-licensed"
DEFAULT_OUTPUT = ROOT / "build" / "sounds.pak"
DEFAULT_MUSIC_OUTPUT = ROOT / "build" / "music.pak"


def _load_assets_pack():
    """Import the game's pack module by path (works without an installed package)."""
    spec = importlib.util.spec_from_file_location(
        "assets_pack", SRC_DIR / "freight_fate" / "assets_pack.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pack_sounds_only(
    sounds_dir: Path = SOUNDS_DIR,
    output: Path = DEFAULT_OUTPUT,
    overlay_dir: Path = LICENSED_DIR,
) -> Path:
    """Write everything except ``music/`` and return the pack path."""
    return _load_assets_pack().write_pack(
        sounds_dir,
        output,
        overlay_dir=overlay_dir,
        include=lambda name: not name.startswith("music/"),
    )


def pack_music_only(
    sounds_dir: Path = SOUNDS_DIR,
    output: Path = DEFAULT_MUSIC_OUTPUT,
    overlay_dir: Path = LICENSED_DIR,
) -> Path:
    """Write only the ``music/`` subtree and return the pack path."""
    return _load_assets_pack().write_pack(
        sounds_dir,
        output,
        overlay_dir=overlay_dir,
        include=lambda name: name.startswith("music/"),
    )


def pack(
    sounds_dir: Path = SOUNDS_DIR,
    output: Path = DEFAULT_OUTPUT,
    music_output: Path = DEFAULT_MUSIC_OUTPUT,
    overlay_dir: Path = LICENSED_DIR,
) -> tuple[Path, Path]:
    """Write both packs (split by the ``music/`` prefix) and return their paths."""
    return (
        pack_sounds_only(sounds_dir, output, overlay_dir),
        pack_music_only(sounds_dir, music_output, overlay_dir),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="where to write the sound pack (default: build/sounds.pak)",
    )
    parser.add_argument(
        "--music-out",
        type=Path,
        default=DEFAULT_MUSIC_OUTPUT,
        help="where to write the music pack (default: build/music.pak)",
    )
    args = parser.parse_args()
    sounds_out, music_out = pack(output=args.out, music_output=args.music_out)
    assets_pack = _load_assets_pack()
    for label, out in (("sound", sounds_out), ("music", music_out)):
        entries = len(assets_pack.SoundPack(out).names())
        size_mb = out.stat().st_size / 1e6
        print(f"Packed {entries} {label} asset(s) into {out} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
