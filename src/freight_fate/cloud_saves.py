"""Optional cloud save backup: careers mirrored to the player's Orinks account.

This module is the *only* place that knows about the Orinks cloud save API.
After each local save the game hands the profile snapshot to
:class:`CloudSaves`, which uploads it (debounced, on a background thread) to
a revisioned slot on orinks.net under the same account-issued Driver ID and
token the drivers board already uses -- the player never handles a second
credential. Restores and conflict choices run through the Cloud backup menu
(see :mod:`freight_fate.states.cloud_save_states`).

Everything here is best-effort and non-fatal by design, mirroring
:mod:`freight_fate.online_presence`: if the player is offline, the site is
down, or the feature is disabled, the game saves locally exactly as before.
No error ever propagates into the game loop.

Sync model: last-write-wins with a conflict guard. Every upload names the
cloud revision it was based on; if another machine advanced the slot in the
meantime the server answers 409 and nothing is overwritten -- the slot is
marked conflicted here and the Cloud backup menu offers a spoken choice
between the two copies.

Privacy: off by default, separate from drivers-board sharing (whose spoken
disclosure promises save files are never sent). Backups are private to the
player's own Orinks account; nothing appears on any public page.

The uploaded content is the profile JSON *without* the local HMAC signature
fields: the signing secret is per-machine, so a signed save restored onto
another computer would be quarantined as tampered. Unsigned saves are
accepted and re-signed on first load (see models/profile.py), which makes
the stripped form the portable one. Transfer integrity is covered by a
sha256 content hash verified on both upload (server-side) and download.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import logging
import threading
import time
import urllib.error
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from .online_presence import OnlineIdentity, Transport, _http_json, base_url

if TYPE_CHECKING:
    from .models.profile import Profile

log = logging.getLogger(__name__)

# A save burst (delivery, achievement, rest) writes the file several times in
# a few seconds; the debounce collapses that into one upload.
DEBOUNCE_S = 8.0

# After a failed upload (site down, no network) retry on this cadence rather
# than every worker wake-up.
RETRY_INTERVAL_S = 120.0

# Matches MAX_SAVE_BYTES on the server; checked here so an oversized profile
# fails quietly in the log instead of with a rejected request.
MAX_UPLOAD_BYTES = 900 * 1024

_WORKER_TICK_S = 60.0

# The profile's integrity-signature fields (models/profile.py). Stripped from
# cloud content: the signature only verifies on the machine that wrote it.
_SIGNATURE_FIELDS = ("_signature", "_signature_version")


def save_slot_name(profile_name: str) -> str:
    """The cloud slot for a profile: the same sanitized stem as its file name
    (Profile.path), so slot and local file always pair up."""
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in profile_name).strip()
    return safe or "Driver"


def cloud_content(profile_dict: dict) -> tuple[bytes, str]:
    """The upload form of a profile snapshot: signature-stripped JSON,
    gzipped deterministically, plus its sha256 hex digest."""
    portable = {k: v for k, v in profile_dict.items() if k not in _SIGNATURE_FIELDS}
    raw = json.dumps(portable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    content = gzip.compress(raw, mtime=0)
    return content, hashlib.sha256(content).hexdigest()


def profile_dict_from_content(content: bytes) -> dict:
    """Decode downloaded content back to a profile dict. Raises ValueError
    when the bytes are not a gzipped profile object."""
    try:
        data = json.loads(gzip.decompress(content).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"cloud save content is not a gzipped profile: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("cloud save content is not a profile object")
    return data


def _saves_url() -> str:
    return f"{base_url()}/api/freight-fate/saves"


def _auth_headers(identity: OnlineIdentity) -> dict[str, str]:
    return {"Authorization": f"Bearer {identity.driver_token}"}


def _error_body(e: urllib.error.HTTPError) -> dict:
    try:
        body = json.loads(e.read().decode("utf-8"))
        return body if isinstance(body, dict) else {}
    except Exception:
        return {}


# -- sync state ----------------------------------------------------------------


class SyncState:
    """What this machine knows about each cloud slot, persisted next to the
    saves: the last revision it synced (uploaded or restored) and the content
    hash at that point, so unchanged profiles skip the upload entirely.

    A ``conflict`` entry means the server refused an upload because another
    machine advanced the slot; it clears when the player resolves the slot
    from the Cloud backup menu.
    """

    def __init__(self) -> None:
        self._slots: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._loaded = False

    @staticmethod
    def path():
        from .models.profile import data_dir

        return data_dir() / "cloud_saves.json"

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            with open(self.path(), encoding="utf-8") as f:
                data = json.load(f)
            slots = data.get("slots")
            if isinstance(slots, dict):
                self._slots = {k: dict(v) for k, v in slots.items() if isinstance(v, dict)}
        except (FileNotFoundError, json.JSONDecodeError, OSError, AttributeError):
            pass

    def _persist(self) -> None:
        path = self.path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"slots": self._slots}, f, indent=2)
            tmp.replace(path)
        except OSError:
            log.debug("Could not persist cloud sync state", exc_info=True)

    def slot(self, name: str) -> dict:
        with self._lock:
            self._ensure_loaded()
            return dict(self._slots.get(name, {}))

    def slots(self) -> dict[str, dict]:
        with self._lock:
            self._ensure_loaded()
            return {k: dict(v) for k, v in self._slots.items()}

    def record_synced(self, name: str, revision: int, content_hash: str) -> None:
        with self._lock:
            self._ensure_loaded()
            self._slots[name] = {"revision": revision, "hash": content_hash}
            self._persist()

    def record_conflict(self, name: str, latest: dict) -> None:
        with self._lock:
            self._ensure_loaded()
            entry = self._slots.setdefault(name, {})
            entry["conflict"] = {
                "latestRevision": latest.get("latestRevision"),
                "latestCreatedAt": latest.get("latestCreatedAt"),
                "latestSummary": latest.get("latestSummary"),
            }
            self._persist()

    def clear_conflict(self, name: str) -> None:
        with self._lock:
            self._ensure_loaded()
            entry = self._slots.get(name)
            if entry and "conflict" in entry:
                del entry["conflict"]
                self._persist()


# -- API calls (used by the service worker and, via menus, worker threads) -----


def upload_save(
    identity: OnlineIdentity,
    *,
    save_name: str,
    profile_dict: dict,
    parent_revision: int | None,
    summary: str,
    transport: Transport = _http_json,
) -> dict:
    """One upload attempt. Returns the reply dict on success, or a dict with
    ``ok=False`` and a ``reason`` (``conflict`` carries the server's latest
    revision details). Network trouble is ``reason="error"``."""
    content, content_hash = cloud_content(profile_dict)
    if len(content) > MAX_UPLOAD_BYTES:
        log.warning(
            "Cloud backup of %s skipped: %d bytes exceeds the limit", save_name, len(content)
        )
        return {"ok": False, "reason": "too_large"}
    version = profile_dict.get("version")
    payload = {
        "driverId": identity.driver_id,
        "saveName": save_name,
        "saveVersion": version if isinstance(version, int) else 0,
        "parentRevision": parent_revision,
        "contentHash": content_hash,
        "content": base64.b64encode(content).decode("ascii"),
        "summary": summary,
    }
    try:
        reply = transport(_saves_url(), payload, _auth_headers(identity))
    except urllib.error.HTTPError as e:
        body = _error_body(e)
        if e.code == 409 and body.get("error") == "conflict":
            return {"ok": False, "reason": "conflict", **body}
        reason = body.get("error") or f"http_{e.code}"
        log.warning("Cloud backup of %s failed: %s", save_name, reason)
        return {"ok": False, "reason": str(reason)}
    except Exception as e:
        log.debug("Cloud backup of %s failed: %s", save_name, e)
        return {"ok": False, "reason": "error"}
    if reply.get("ok") and isinstance(reply.get("revision"), int):
        return {"ok": True, "revision": reply["revision"], "contentHash": content_hash}
    return {"ok": False, "reason": "error"}


def list_saves(identity: OnlineIdentity, *, transport: Transport = _http_json) -> list[dict] | None:
    """All kept cloud revisions for this driver (newest first), or None when
    the site is unreachable. Called from menu worker threads only."""
    url = f"{_saves_url()}?driverId={identity.driver_id}"
    try:
        reply = transport(url, None, _auth_headers(identity))
    except Exception as e:
        log.debug("Cloud save list failed: %s", e)
        return None
    saves = reply.get("saves")
    return saves if isinstance(saves, list) else None


def download_save(
    identity: OnlineIdentity,
    *,
    save_name: str,
    revision: int | None = None,
    transport: Transport = _http_json,
) -> dict | None:
    """One cloud revision, decoded and hash-verified: a dict with the slot
    metadata plus ``profile`` (the profile dict) -- or None on any failure.
    Called from menu worker threads only."""
    url = f"{_saves_url()}/content?driverId={identity.driver_id}&saveName={urllib.parse.quote(save_name)}"
    if revision is not None:
        url += f"&revision={revision}"
    try:
        reply = transport(url, None, _auth_headers(identity))
        content = base64.b64decode(reply["content"])
    except Exception as e:
        log.debug("Cloud save download failed: %s", e)
        return None
    if hashlib.sha256(content).hexdigest() != reply.get("contentHash"):
        log.warning("Cloud save download of %s failed its integrity check", save_name)
        return None
    try:
        profile_dict = profile_dict_from_content(content)
    except ValueError as e:
        log.warning("Cloud save download of %s unusable: %s", save_name, e)
        return None
    return {
        "saveName": reply.get("saveName", save_name),
        "revision": reply.get("revision"),
        "saveVersion": reply.get("saveVersion"),
        "summary": reply.get("summary", ""),
        "createdAt": reply.get("createdAt"),
        "contentHash": reply.get("contentHash"),
        "profile": profile_dict,
    }


def restore_to_disk(payload: dict, sync_state: SyncState | None = None) -> Path:
    """Write a downloaded cloud save over the local profile file.

    The current local file (if any) is kept beside it as ``.json.bak`` --
    invisible to the profile list, which only globs ``*.json``. The restored
    file is written *unsigned*; the game re-signs it with this machine's
    secret on first load. Records the restored revision in the sync state so
    the next local save uploads with the right parent.
    """
    from .models.profile import profiles_dir

    name = save_slot_name(str(payload["profile"].get("name", payload["saveName"])))
    path = profiles_dir() / f"{name}.json"
    if path.exists():
        try:
            backup = path.with_suffix(".json.bak")
            backup.unlink(missing_ok=True)
            path.replace(backup)
        except OSError:
            log.warning("Could not keep a local backup before restoring %s", name, exc_info=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload["profile"], f, indent=2)
    tmp.replace(path)
    if sync_state is not None and isinstance(payload.get("revision"), int):
        _, content_hash = cloud_content(payload["profile"])
        sync_state.record_synced(payload["saveName"], payload["revision"], content_hash)
        sync_state.clear_conflict(payload["saveName"])
    return path


def backup_summary(profile_dict: dict) -> str:
    """A short spoken line describing a snapshot, shown in the restore menu."""
    name = profile_dict.get("name", "Driver")
    money = profile_dict.get("money")
    career = profile_dict.get("career") or {}
    xp = career.get("xp") if isinstance(career, dict) else None
    bits = [str(name)]
    if isinstance(xp, int | float):
        from .models.career import level_for_xp

        bits.append(f"level {level_for_xp(float(xp))}")
    if isinstance(money, int | float):
        bits.append(f"{money:,.0f} dollars")
    return ", ".join(bits)


# -- the backup service ---------------------------------------------------------


class CloudSaves:
    """Best-effort save uploader for the player's Orinks account.

    Gameplay never calls this directly: models/profile.py invokes the save
    listener after every successful local save, and :meth:`queue_backup`
    snapshots the profile and returns immediately. A daemon worker owns all
    HTTP: it debounces bursts of saves, skips uploads whose content already
    matches the cloud, and records conflicts for the Cloud backup menu to
    resolve. :meth:`shutdown` flushes the pending upload briefly so quitting
    right after a delivery still backs it up.

    The worker is optional (``threaded=False``) so tests can drive the exact
    same logic synchronously with an injected clock and transport.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        identity: OnlineIdentity | None = None,
        debounce_s: float = DEBOUNCE_S,
        retry_s: float = RETRY_INTERVAL_S,
        clock: Callable[[], float] = time.monotonic,
        transport: Transport = _http_json,
        threaded: bool = True,
        sync_state: SyncState | None = None,
    ) -> None:
        self._identity = identity
        self._enabled = bool(enabled) and identity is not None
        self._debounce = max(0.0, float(debounce_s))
        self._retry = max(1.0, float(retry_s))
        self._clock = clock
        self._transport = transport
        self._threaded = threaded
        self.sync_state = sync_state if sync_state is not None else SyncState()

        self._lock = threading.Lock()
        # slot name -> (profile dict snapshot, queued-at time)
        self._pending: dict[str, tuple[dict, float]] = {}
        self._retry_at: float | None = None

        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False

    # -- public API -----------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def identity(self) -> OnlineIdentity | None:
        return self._identity

    def set_identity(self, identity: OnlineIdentity | None) -> None:
        """Adopt freshly confirmed credentials (from the setup flow)."""
        self._identity = identity
        if identity is None:
            self.set_enabled(False)

    def set_enabled(self, enabled: bool) -> None:
        """Toggle at runtime (from the settings menu)."""
        enabled = bool(enabled) and self._identity is not None
        if enabled == self._enabled:
            return
        self._enabled = enabled
        if enabled:
            self.start()
        else:
            self._stop_worker()
            with self._lock:
                self._pending.clear()

    def start(self) -> None:
        """Begin the worker after app initialisation. Safe when disabled."""
        if not self._enabled or self._started:
            return
        self._started = True
        self._stop.clear()
        if self._threaded:
            self._thread = threading.Thread(target=self._run, name="cloud-saves", daemon=True)
            self._thread.start()

    def queue_backup(self, profile: Profile) -> None:
        """Snapshot a just-saved profile for upload; returns immediately."""
        if not self._enabled:
            return
        try:
            snapshot = profile.to_dict()
        except Exception:  # never let backup break the save that triggered it
            log.debug("Cloud backup snapshot failed", exc_info=True)
            return
        name = save_slot_name(profile.name)
        with self._lock:
            self._pending[name] = (snapshot, self._clock())
        if self._threaded:
            self._wake.set()
        else:
            self.pump()

    def shutdown(self) -> None:
        """Flush the pending upload briefly and stop the worker. Never raises."""
        self._stop_worker()
        if not self._enabled:
            return
        with self._lock:
            has_pending = bool(self._pending)
        if not has_pending:
            return
        if not self._threaded:
            self.pump(force=True)
            return
        # Quitting must not hang on a dead network: one bounded attempt.
        flusher = threading.Thread(
            target=lambda: self.pump(force=True), name="cloud-saves-flush", daemon=True
        )
        flusher.start()
        flusher.join(timeout=5.0)

    def conflicts(self) -> dict[str, dict]:
        """Slots the server refused to overwrite, for the Cloud backup menu."""
        return {
            name: entry["conflict"]
            for name, entry in self.sync_state.slots().items()
            if "conflict" in entry
        }

    # -- worker / single-step logic ------------------------------------------

    def _stop_worker(self) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None
        self._started = False
        self._stop.clear()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.pump()
            except Exception:  # pragma: no cover - defensive belt-and-braces
                log.debug("Cloud saves pump failed", exc_info=True)
            self._wake.wait(self._worker_wait())
            self._wake.clear()

    def _worker_wait(self) -> float:
        now = self._clock()
        with self._lock:
            if not self._pending:
                return _WORKER_TICK_S
            oldest = min(t for _, t in self._pending.values())
        if self._retry_at is not None:
            return max(0.05, self._retry_at - now)
        return max(0.05, self._debounce - (now - oldest))

    def pump(self, force: bool = False) -> None:
        """Upload every due pending slot. ``force`` ignores the debounce and
        retry backoff (shutdown flush)."""
        if not self._enabled or self._identity is None:
            return
        now = self._clock()
        if not force and self._retry_at is not None and now < self._retry_at:
            return
        with self._lock:
            due = [
                (name, snapshot)
                for name, (snapshot, queued_at) in self._pending.items()
                if force or now - queued_at >= self._debounce
            ]
        for name, snapshot in due:
            if self._stop.is_set() and not force:
                return
            self._upload_slot(name, snapshot)

    def _done_with(self, name: str, snapshot: dict) -> None:
        """Drop a handled snapshot -- unless a newer save replaced it while
        the upload was in flight, which must stay queued."""
        with self._lock:
            current = self._pending.get(name)
            if current is not None and current[0] is snapshot:
                del self._pending[name]

    def _upload_slot(self, name: str, snapshot: dict) -> None:
        slot = self.sync_state.slot(name)
        if "conflict" in slot:
            # Never retry into a known conflict; the player resolves it from
            # the Cloud backup menu. Drop the snapshot -- the local file is
            # still the source of truth for "keep mine".
            self._done_with(name, snapshot)
            return
        _, content_hash = cloud_content(snapshot)
        if slot.get("hash") == content_hash:
            self._done_with(name, snapshot)
            return
        result = upload_save(
            self._identity,
            save_name=name,
            profile_dict=snapshot,
            parent_revision=slot.get("revision"),
            summary=backup_summary(snapshot),
            transport=self._transport,
        )
        if result.get("ok"):
            self.sync_state.record_synced(name, result["revision"], result["contentHash"])
            self._done_with(name, snapshot)
            self._retry_at = None
            log.info("Cloud backup of %s uploaded as revision %s", name, result["revision"])
            return
        if result.get("reason") == "conflict":
            self.sync_state.record_conflict(name, result)
            self._done_with(name, snapshot)
            log.warning(
                "Cloud backup of %s skipped: the cloud copy is newer (revision %s)",
                name,
                result.get("latestRevision"),
            )
            return
        if result.get("reason") in ("unauthorized", "driver_not_found", "too_large"):
            # Not transient: retrying with the same inputs cannot succeed.
            self._done_with(name, snapshot)
            return
        # Transient (network, 5xx): keep the snapshot, back off.
        self._retry_at = self._clock() + self._retry

    def resolve_keep_mine(self, name: str, profile_dict: dict) -> bool:
        """Conflict choice: overwrite the cloud with this machine's save.

        Called from a menu worker thread. Uploads with the server's latest
        revision as parent, which the conflict entry recorded.
        """
        if self._identity is None:
            return False
        slot = self.sync_state.slot(name)
        conflict = slot.get("conflict") or {}
        parent = conflict.get("latestRevision")
        result = upload_save(
            self._identity,
            save_name=name,
            profile_dict=profile_dict,
            parent_revision=parent if isinstance(parent, int) else None,
            summary=backup_summary(profile_dict),
            transport=self._transport,
        )
        if result.get("ok"):
            self.sync_state.record_synced(name, result["revision"], result["contentHash"])
            self.sync_state.clear_conflict(name)
            return True
        if result.get("reason") == "conflict":
            # The cloud moved again since the conflict was recorded; refresh
            # the details so the menu speaks current numbers.
            self.sync_state.record_conflict(name, result)
        return False
