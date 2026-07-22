"""Packed sound assets for frozen builds.

Release builds ship the ``assets/sounds`` tree as a single masked pack file
(``freight_fate/sounds.pak``) instead of a browsable folder. The pack is a
deflated zip XOR-masked with a fixed key, so renaming it does not turn it
back into an openable archive; this deters casual editing, nothing more.
Source checkouts have no pack file and the audio engine reads the loose
files, so development is unchanged.

``tools/pack_sounds.py`` writes the pack; the audio engine reads it through
``open_default``. The pack payload is deterministic for identical inputs.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

PACK_MAGIC = b"FFPK1\x00"
DEFAULT_PACK_PATH = Path(__file__).parent / "sounds.pak"
# Fixed zip timestamp so identical inputs produce identical packs.
_EPOCH = (1980, 1, 1, 0, 0, 0)
_XOR_KEY = bytes.fromhex(
    "8f3a51c7e2946d0bb85f13a6c94e72d10d6b38f5a1c84e97625d0f3bb7a9c1e4"
    "49e8d2761b5fa3c087d4e91f6a2c53b8f0b6249dcd7183ea5e40f92c37a8d165"
)


def _mask(data: bytes) -> bytes:
    """XOR ``data`` with the repeating pack key (symmetric)."""
    if not data:
        return data
    import numpy as np

    repeats = len(data) // len(_XOR_KEY) + 1
    key = np.frombuffer((_XOR_KEY * repeats)[: len(data)], dtype=np.uint8)
    return (np.frombuffer(data, dtype=np.uint8) ^ key).tobytes()


def write_pack(sounds_dir: Path, output: Path, overlay_dir: Path | None = None) -> Path:
    """Pack every file under ``sounds_dir`` and return the pack path.

    ``overlay_dir`` (the licensed-audio tree) is merged on top: where both
    trees carry the same relative path, the overlay's file is packed. A build
    made on a machine that owns the licensed libraries ships them; a clean
    clone packs the synthesized fallbacks alone.
    """
    entries = {
        path.relative_to(sounds_dir).as_posix(): path
        for path in sounds_dir.rglob("*")
        if path.is_file()
    }
    if overlay_dir is not None and overlay_dir.is_dir():
        entries.update(
            (path.relative_to(overlay_dir).as_posix(), path)
            for path in overlay_dir.rglob("*")
            if path.is_file()
        )
    if not entries:
        raise ValueError(f"No sound assets to pack under {sounds_dir}")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=_EPOCH)
            z.writestr(info, entries[name].read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(PACK_MAGIC + _mask(buffer.getvalue()))
    return output


class SoundPack:
    """Read-only view of a masked sound pack, held in memory."""

    def __init__(self, path: Path) -> None:
        raw = path.read_bytes()
        if not raw.startswith(PACK_MAGIC):
            raise ValueError(f"Not a Freight Fate sound pack: {path}")
        self._zip = zipfile.ZipFile(io.BytesIO(_mask(raw[len(PACK_MAGIC) :])))

    def names(self) -> list[str]:
        return self._zip.namelist()

    def read(self, name: str) -> bytes | None:
        """Bytes for a pack-relative posix path, or None if absent."""
        try:
            return self._zip.read(name)
        except KeyError:
            return None


_default_pack: SoundPack | None = None
_default_pack_missing = False


def open_default() -> SoundPack | None:
    """The shipped pack, or None in source checkouts (no pack file)."""
    global _default_pack, _default_pack_missing
    if _default_pack is None and not _default_pack_missing:
        if DEFAULT_PACK_PATH.exists():
            _default_pack = SoundPack(DEFAULT_PACK_PATH)
        else:
            _default_pack_missing = True
    return _default_pack
