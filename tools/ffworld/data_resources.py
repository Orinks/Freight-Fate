"""Where the build tools find the world data tree.

``DATA_ROOT`` is the ONE place this package names its data root; every other
path in it is derived from this constant. The game itself is Rust and reads
the baked ``world.ffdata`` container; this package exists only for the
Python build tools that generate and screen that data.
"""

from __future__ import annotations

from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"


def read_data_text(relative: str) -> str | None:
    """The text of a data file under ``DATA_ROOT``, or None when it is absent."""
    path = DATA_ROOT / Path(relative)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")
