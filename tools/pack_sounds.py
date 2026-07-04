"""Pack the sound assets into a single masked file for frozen builds.

The release build (``tools/build_release.py``) runs this so the shipped
game carries ``freight_fate/sounds.pak`` instead of a browsable sounds
folder. Source checkouts keep the loose, editable ``assets/sounds`` tree;
the audio engine only reads the pack when it exists.

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
DEFAULT_OUTPUT = ROOT / "build" / "sounds.pak"


def _load_assets_pack():
    """Import the game's pack module by path (works without an installed package)."""
    spec = importlib.util.spec_from_file_location(
        "assets_pack", SRC_DIR / "freight_fate" / "assets_pack.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pack(sounds_dir: Path = SOUNDS_DIR, output: Path = DEFAULT_OUTPUT) -> Path:
    """Write the sound pack and return its path."""
    return _load_assets_pack().write_pack(sounds_dir, output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="where to write the pack (default: build/sounds.pak)",
    )
    args = parser.parse_args()
    out = pack(output=args.out)
    print(f"Packed sound assets into {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
