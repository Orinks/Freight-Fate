"""Freight Fate's masked sound-pack format: the writer and a reader.

Release builds ship the ``assets/sounds`` tree as two masked pack files
instead of a browsable folder: ``freight_fate/music.pak`` carries every entry
under ``music/``, ``freight_fate/sounds.pak`` carries everything else. Each
pack is a deflated zip XOR-masked with a fixed key, so renaming one does not
turn it back into an openable archive; this deters casual editing, nothing
more.

``tools/pack_sounds.py`` writes both packs with :func:`write_pack`; the Rust
game (``ff_core::assets_pack``) reads them. :class:`SoundPack` is the Python
reader the build and the tests use to check what a pack carries. The pack
payload is deterministic for identical inputs.
"""

from __future__ import annotations

import io
import logging
import zipfile
import zlib
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)

PACK_MAGIC = b"FFPK1\x00"
# The committed sounds.pak and the builder-local music.pak.
PACK_DIR = Path(__file__).resolve().parents[1] / "assets"
DEFAULT_PACK_PATH = PACK_DIR / "sounds.pak"
DEFAULT_MUSIC_PACK_PATH = PACK_DIR / "music.pak"
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


def write_pack(
    sounds_dir: Path,
    output: Path,
    overlay_dir: Path | None = None,
    include: Callable[[str], bool] | None = None,
) -> Path:
    """Pack files under ``sounds_dir`` and return the pack path.

    ``overlay_dir`` (the licensed-audio tree) is merged on top and wins by
    sound KEY (path stem), not just exact path: the loader prefers ogg over
    wav inside the pack, so a committed ``engine/mid.ogg`` fallback would
    shadow a licensed ``engine/mid.wav`` if both shipped. A build made on a
    machine that owns the licensed libraries ships them; a clean clone packs
    the synthesized fallbacks alone. Editor backups (``*.bak``) never ship:
    one already rode a builder's loose tree into a released pack.

    ``include``, when given, keeps only pack-relative names it accepts --
    the base tree and overlay are still merged first (by full stem
    precedence, exactly as with no filter), so an overlay entry routes to
    whichever pack its own path belongs to. ``tools/pack_sounds.py`` calls
    this twice, once per prefix, to split ``music/`` into its own pack.
    """
    entries = {
        path.relative_to(sounds_dir).as_posix(): path
        for path in sounds_dir.rglob("*")
        if path.is_file() and path.suffix != ".bak"
    }
    if overlay_dir is not None and overlay_dir.is_dir():
        overlay_entries = {
            path.relative_to(overlay_dir).as_posix(): path
            for path in overlay_dir.rglob("*")
            if path.is_file() and path.suffix != ".bak"
        }
        overlay_stems = {name.rsplit(".", 1)[0] for name in overlay_entries}
        entries = {
            name: path
            for name, path in entries.items()
            if name.rsplit(".", 1)[0] not in overlay_stems
        }
        entries.update(overlay_entries)
    if include is not None:
        entries = {name: path for name, path in entries.items() if include(name)}
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
        self._name_set: set[str] | None = None

    def names(self) -> list[str]:
        return self._zip.namelist()

    def has(self, name: str) -> bool:
        """Whether the pack carries ``name``, without decompressing it."""
        if self._name_set is None:
            self._name_set = set(self._zip.namelist())
        return name in self._name_set

    def read(self, name: str) -> bytes | None:
        """Bytes for a pack-relative posix path, or None if absent.

        A damaged entry counts as absent, not as an error: the caller then
        falls back to the loose sound tree, so one corrupt member costs its
        own sound instead of every sound after it.
        """
        try:
            return self._zip.read(name)
        except KeyError:
            return None
        except (OSError, zipfile.BadZipFile, zlib.error, EOFError):
            log.warning("Damaged entry in sound pack: %s", name, exc_info=True)
            return None
