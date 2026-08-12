"""Packed sound assets for frozen builds.

Release builds ship the ``assets/sounds`` tree as a single masked pack file
(``freight_fate/sounds.pak``) instead of a browsable folder. The pack is a
deflated zip XOR-masked with a fixed key, so renaming it does not turn it
back into an openable archive; this deters casual editing, nothing more.
Career 1.9 source checkouts receive the encrypted pack through Git LFS. Tests
can explicitly disable the default pack and exercise the loose-file fallback.

``tools/pack_sounds.py`` writes the pack; the audio engine reads it through
``open_default``. The pack payload is deterministic for identical inputs.
"""

from __future__ import annotations

import io
import logging
import os
import threading
import zipfile
import zlib
from pathlib import Path

log = logging.getLogger(__name__)

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

    ``overlay_dir`` (the licensed-audio tree) is merged on top and wins by
    sound KEY (path stem), not just exact path: the loader prefers ogg over
    wav inside the pack, so a committed ``engine/mid.ogg`` fallback would
    shadow a licensed ``engine/mid.wav`` if both shipped. A build made on a
    machine that owns the licensed libraries ships them; a clean clone packs
    the synthesized fallbacks alone.
    """
    entries = {
        path.relative_to(sounds_dir).as_posix(): path
        for path in sounds_dir.rglob("*")
        if path.is_file()
    }
    if overlay_dir is not None and overlay_dir.is_dir():
        overlay_entries = {
            path.relative_to(overlay_dir).as_posix(): path
            for path in overlay_dir.rglob("*")
            if path.is_file()
        }
        overlay_stems = {name.rsplit(".", 1)[0] for name in overlay_entries}
        entries = {
            name: path
            for name, path in entries.items()
            if name.rsplit(".", 1)[0] not in overlay_stems
        }
        entries.update(overlay_entries)
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


_default_pack: SoundPack | None = None
_default_pack_missing = False
# Guards both the read-and-unmask work and the two globals above. A plain
# lock (rather than a Future/Event) doubles as the join: whichever thread --
# the background prefetch, or a caller of open_default() that got there
# first -- is inside this lock actually reading the ~225MB pack off disk,
# every other thread blocks on the lock itself instead of polling anything.
_load_lock = threading.Lock()
_prefetch_started = False


def _load_default_pack_locked() -> None:
    """Do the actual read-and-unmask. Caller must hold ``_load_lock``."""
    global _default_pack, _default_pack_missing
    if _default_pack is not None or _default_pack_missing:
        return  # someone else finished this while we waited for the lock
    if DEFAULT_PACK_PATH.exists():
        try:
            _default_pack = SoundPack(DEFAULT_PACK_PATH)
        except Exception:
            log.warning(
                "Unreadable sound pack at %s; reading loose sound files instead",
                DEFAULT_PACK_PATH,
                exc_info=True,
            )
            _default_pack_missing = True
        else:
            log.info(
                "Sound pack loaded: %s (%d entries)",
                DEFAULT_PACK_PATH,
                len(_default_pack.names()),
            )
    else:
        _default_pack_missing = True


def prefetch_default() -> None:
    """Start loading the shipped pack on a background thread.

    The pack is a ~225MB file that gets read fully into memory and XOR
    unmasked; today that ~0.3s lands synchronously on whichever sound plays
    first (typically a main-menu sound), stalling it. Called as early as
    possible in ``App()`` construction, this overlaps that cost with the
    rest of startup (world load especially) instead of adding to it.

    Safe to call more than once (a no-op once a load has started or
    finished) and safe even when there is no pack to load. Never blocks: the
    actual wait happens in :func:`open_default`, via the same lock, so a
    corrupt or half-written pack still raises/logs exactly as it does today
    -- just on whichever thread ends up doing the work, main or background.
    """
    global _prefetch_started
    if os.environ.get("FREIGHT_FATE_IGNORE_SOUND_PACK") == "1":
        return
    if _prefetch_started or _default_pack is not None or _default_pack_missing:
        return
    _prefetch_started = True

    def _run() -> None:
        with _load_lock:
            _load_default_pack_locked()

    threading.Thread(target=_run, name="ffpack-prefetch", daemon=True).start()


def open_default() -> SoundPack | None:
    """The shipped pack, or None when there is no usable pack file.

    An unreadable pack -- a truncated copy, a half-finished download, a file
    from another build -- is treated as no pack at all rather than raised.
    A source checkout still has its loose sound tree to fall back on, so the
    game keeps its sound; a frozen build has nothing to fall back to, but it
    says so in the log instead of failing on the first sound it plays.

    If :func:`prefetch_default` already has this underway on a background
    thread, this blocks on ``_load_lock`` until that finishes instead of
    redoing the read itself -- the first sound request pays only whatever
    time is left on the prefetch, not the whole ~0.3s again.
    """
    if os.environ.get("FREIGHT_FATE_IGNORE_SOUND_PACK") == "1":
        return None
    if _default_pack is None and not _default_pack_missing:
        with _load_lock:
            _load_default_pack_locked()
    return _default_pack
