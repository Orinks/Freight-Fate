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

Privacy: off by default and separate from public Profile sharing. Backups are
private to the player's own orinks.net account; only an allowlisted summary of the
latest accepted revision can supply detailed public statistics when Profile
sharing is independently enabled.

The uploaded content is the profile JSON *without* the local HMAC signature
fields: the signing secret is per-machine. orinks.net validates that portable
payload before accepting a revision and signs it with Ed25519. Downloads are
hash-checked and signature-verified before any local file is touched; a
successful restore is immediately HMAC-signed for this installation.
"""

from __future__ import annotations

import base64
import contextlib
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

from .cloud_save_integrity import CloudSaveIntegrityError, verify_cloud_revision
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


def _http_delete(url: str, payload: dict | None, headers: dict[str, str]) -> dict:
    """Transport-shaped DELETE, so tests can stub it like every other call."""
    return _http_json(url, payload, headers, method="DELETE")


def _auth_headers(identity: OnlineIdentity) -> dict[str, str]:
    return {"Authorization": f"Bearer {identity.driver_token}"}


def _error_body(e: urllib.error.HTTPError) -> dict:
    try:
        body = json.loads(e.read().decode("utf-8"))
        return body if isinstance(body, dict) else {}
    except Exception:
        return {}


class CloudAuthError(Exception):
    """orinks.net answered but refused this machine's driver credentials.

    Raised (never swallowed into a generic ``None``) so the Cloud backup
    menus can tell the player to reconnect instead of blaming the network.
    The usual cause: the account issued a fresh driver token to another
    computer, which retires the token stored on this one.
    """


# The spoken guidance for CloudAuthError, shared by every cloud menu so the
# player always hears the same recovery path. orinks.net issues one token
# per computer, so a refusal means this computer's token was signed out
# from the account's computer list (or replaced by a sign-out-everywhere).
AUTH_HELP = (
    "orinks.net no longer accepts this computer's sign-in. Usually this "
    "computer was signed out from the computer list on your orinks.net "
    "driver setup page: open that page, choose Add computer to get a fresh "
    "token, then paste it under Set up orinks.net account on the Online "
    "menu. If your driver is not on that page at all, the account itself is "
    "gone rather than this computer's sign-in, which can happen after the "
    "site is rebuilt; make a new account and connect it the same way."
)


def _auth_refused(e: urllib.error.HTTPError, body: dict) -> bool:
    """Whether orinks.net refused this machine's credentials.

    Two different situations arrive here and the site does not distinguish
    them: a retired token (this computer signed out from the account's
    computer list) and a driver record that no longer exists at all. Both
    answer ``404 {"error": "driver_not_found"}`` -- observed on the staging
    site on 2026-08-11, after the deployment behind it was rebuilt and every
    driver issued before the move stopped resolving. AUTH_HELP therefore
    covers both, since the recovery differs: Add computer for the first,
    a whole new account for the second.
    """
    return e.code == 401 or body.get("error") in ("unauthorized", "driver_not_found")


# -- upload failure classification ---------------------------------------------
#
# ``upload_save`` hands back a ``reason`` string that is a network problem, an
# auth problem, or one of the validator's refusal codes -- three situations a
# player needs three different honest sentences for (Jessie's report,
# 2026-08-14: an ``invalid_achievement`` refusal was told to the player as
# "check your connection", which sent them chasing their network for a
# problem that was never there). Every caller that turns an upload result
# into player-facing wording -- the background queue in ``_upload_slot`` and
# the foreground "keep this computer's save" retry in
# ``CloudSavesService.resolve_keep_mine`` -- must classify through the one
# table below, so a new validator code only has to be added in one place.

# The credentials were retired (usually by connecting another computer, or a
# driver record that no longer exists); every retry fails identically until
# the player reconnects from the Online menu.
AUTH_FAILURE_REASONS = frozenset({"unauthorized", "driver_not_found", "http_401"})

# The server read this save and refused it outright. Retrying with the same
# save can never succeed -- it is not a connection problem, it is something
# for the developers to fix.
REJECTED_UPLOAD_REASONS = frozenset(
    {
        "too_large",
        "invalid_schema",
        "invalid_name",
        "invalid_city",
        "invalid_range",
        "invalid_possession",
        "invalid_career",
        "impossible_xp",
        "impossible_money",
        "invalid_market",
        "invalid_hos",
        "invalid_achievement",
        "unsupported_version",
    }
)


def classify_upload_failure(reason: str | None) -> str:
    """Sort an ``upload_save`` failure ``reason`` into the family its
    player-facing wording actually differs by.

    Returns ``"auth"``, ``"rejected"``, or ``"network"`` -- the last one is
    the honest default for anything not recognized (a raw network error, a
    5xx, or a code the validator has not been taught to this table yet):
    treating an unknown reason as transient and worth a retry is the safe
    failure mode, never the other way around.
    """
    if reason in AUTH_FAILURE_REASONS:
        return "auth"
    if reason in REJECTED_UPLOAD_REASONS:
        return "rejected"
    return "network"


# Within "rejected", the two arithmetic cross-checks -- recomputed XP ceiling,
# recomputed money ceiling -- earn a different story than every other refusal:
# only a real cross-check failure means the numbers themselves do not add up,
# so only this pair says "flagged for review" and offers the appeal. A false
# flag hit a real career on this exact wording (2026-08-14), so the appeal
# sentence stays attached to it on purpose.
ARITHMETIC_REJECTION_REASONS = frozenset({"impossible_xp", "impossible_money"})

# Schema and version refusals mean this build and the server disagree about
# what a save even looks like -- almost always a build gap, not something the
# player did to the save.
SCHEMA_REJECTION_REASONS = frozenset({"invalid_schema", "unsupported_version"})


def rejection_status(name: str, reason: str | None) -> str:
    """The player-facing status line for a server-refused upload.

    Always names the career (Shane's report, 2026-08-14: with more than one
    career backed up he could not tell which one had been refused, or why),
    then splits the "rejected" family by what the reason code actually means
    to a player instead of one line for every cause. Shared by the background
    auto-backup queue (:meth:`CloudSaves._upload_slot`) and the foreground
    "keep this computer's save" retry (:meth:`CloudSaves.resolve_keep_mine`,
    via :mod:`freight_fate.states.cloud_save_states`) so both speak the same
    story for the same reason code.
    """
    if reason in ARITHMETIC_REJECTION_REASONS:
        return (
            f"{name}: backup not accepted. The numbers in this save do not "
            "look like possible play, so the server declined it and flagged "
            "it for review. Your local career is safe and nothing public "
            "changed. If you think this is wrong, say so in the tester "
            "document."
        )
    if reason in SCHEMA_REJECTION_REASONS:
        return (
            f"{name}: backup not accepted. Your game and the server "
            "disagree about this save's shape -- usually a build mismatch, "
            "not something you did. Your local career is safe."
        )
    return (
        f"{name}: backup not accepted. Your local career is safe. Public details were not updated."
    )


# The status line for the auth family, shared by the background queue and the
# manual "Save game" announcement so a paused sign-in is always told the same
# way. AUTH_HELP (above) carries the full recovery path when a menu can offer
# it; this is the short standing line.
AUTH_PAUSED_STATUS = (
    "Backups are paused: orinks.net no longer accepts this "
    "computer's sign-in. Reconnect from the Online menu."
)


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

    def forget(self, name: str) -> None:
        """Drop everything known about a slot, conflict included. Called after
        the cloud copy is deleted so the next local save starts a fresh slot
        instead of naming a revision that no longer exists."""
        with self._lock:
            self._ensure_loaded()
            if name in self._slots:
                del self._slots[name]
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


def list_saves(identity: OnlineIdentity, *, transport: Transport = _http_json) -> dict | None:
    """All kept cloud revisions for this driver (``saves``, newest first) plus
    which career fronts the public profile (``publicSaveName``, None when no
    career is designated or the server predates the choice) -- or None when
    the site is unreachable. Raises :class:`CloudAuthError` when the server
    answers but refuses the credentials. Called from menu worker threads only."""
    url = f"{_saves_url()}?driverId={identity.driver_id}"
    try:
        reply = transport(url, None, _auth_headers(identity))
    except urllib.error.HTTPError as e:
        body = _error_body(e)
        if _auth_refused(e, body) or e.code == 404:
            log.warning(
                "Cloud save list refused (HTTP %s): this computer's sign-in is no longer accepted",
                e.code,
            )
            raise CloudAuthError from e
        log.warning("Cloud save list failed: HTTP %s", e.code)
        return None
    except Exception as e:
        log.debug("Cloud save list failed: %s", e)
        return None
    saves = reply.get("saves")
    if not isinstance(saves, list):
        return None
    public = reply.get("publicSaveName")
    return {"saves": saves, "publicSaveName": public if isinstance(public, str) else None}


def set_public_save(
    identity: OnlineIdentity,
    *,
    save_name: str | None,
    transport: Transport = _http_json,
) -> bool:
    """Choose which career fronts the driver's public profile (None returns
    to the server's first-uploader rule). True on success, False when the site
    could not be reached or refused. Raises :class:`CloudAuthError` when the
    server answers but refuses the credentials. Called from menu worker
    threads only."""
    url = f"{_saves_url()}/public-career"
    payload = {"driverId": identity.driver_id, "saveName": save_name}
    try:
        reply = transport(url, payload, _auth_headers(identity))
    except urllib.error.HTTPError as e:
        body = _error_body(e)
        if _auth_refused(e, body):
            log.warning(
                "Public career choice refused (HTTP %s): this computer's sign-in is no longer accepted",
                e.code,
            )
            raise CloudAuthError from e
        log.warning("Public career choice failed: HTTP %s", e.code)
        return False
    except Exception as e:
        log.debug("Public career choice failed: %s", e)
        return False
    return bool(reply.get("ok"))


def delete_save(
    identity: OnlineIdentity,
    *,
    save_name: str,
    transport: Transport = _http_delete,
) -> bool:
    """Remove every kept cloud revision of one slot from the account. True on
    success, False when the site could not be reached or refused. Raises
    :class:`CloudAuthError` when the server answers but refuses the
    credentials. Called from menu worker threads only."""
    url = f"{_saves_url()}?driverId={identity.driver_id}&saveName={urllib.parse.quote(save_name)}"
    try:
        reply = transport(url, None, _auth_headers(identity))
    except urllib.error.HTTPError as e:
        body = _error_body(e)
        if _auth_refused(e, body):
            log.warning(
                "Cloud delete of %s refused (HTTP %s): this computer's sign-in is no longer accepted",
                save_name,
                e.code,
            )
            raise CloudAuthError from e
        log.warning("Cloud delete of %s failed: HTTP %s", save_name, e.code)
        return False
    except Exception as e:
        log.debug("Cloud delete of %s failed: %s", save_name, e)
        return False
    return bool(reply.get("ok"))


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
    except urllib.error.HTTPError as e:
        body = _error_body(e)
        if _auth_refused(e, body):
            log.warning(
                "Cloud save download of %s refused (HTTP %s): this computer's sign-in is no longer accepted",
                save_name,
                e.code,
            )
            raise CloudAuthError from e
        log.warning("Cloud save download of %s failed: HTTP %s", save_name, e.code)
        return None
    except Exception as e:
        log.debug("Cloud save download failed: %s", e)
        return None
    try:
        content = base64.b64decode(reply["content"])
    except Exception as e:
        log.debug("Cloud save download failed: %s", e)
        return None
    if hashlib.sha256(content).hexdigest() != reply.get("contentHash"):
        log.warning("Cloud save download of %s failed its integrity check", save_name)
        return None
    try:
        profile_dict = profile_dict_from_content(content)
        verify_cloud_revision(profile_dict, reply)
    except ValueError as e:
        log.warning("Cloud save download of %s unusable: %s", save_name, e)
        if isinstance(e, CloudSaveIntegrityError):
            raise
        return None
    return {
        "saveName": reply.get("saveName", save_name),
        "revision": reply.get("revision"),
        "saveVersion": reply.get("saveVersion"),
        "summary": reply.get("summary", ""),
        "createdAt": reply.get("createdAt"),
        "contentHash": reply.get("contentHash"),
        "sig": reply.get("sig"),
        "keyId": reply.get("keyId"),
        "signedAt": reply.get("signedAt"),
        "validatorVersion": reply.get("validatorVersion"),
        # Absolution from the server, carried only on a reply whose revision
        # signature just verified above. The flag rides outside that signature,
        # so it is not proof of anything on its own -- but the worst a forged
        # one can do is clear a local advisory mark, and shared features read
        # the server's verdict rather than this flag.
        "clearIntegrityFlag": reply.get("clearIntegrityFlag") is True,
        "profile": profile_dict,
    }


def restore_to_disk(payload: dict, sync_state: SyncState | None = None) -> Path:
    """Write a downloaded cloud save over the local profile file.

    Verification and construction happen before touching disk. The current
    local file (if any) is kept beside it as ``.ffsave.bak``. The replacement
    is atomically installed with this machine's HMAC signature, and the old
    file is put back if installation fails. Sync state changes only after
    success.
    """
    from .models.profile import (
        LEGACY_SAVE_SUFFIX,
        SAVE_SUFFIX,
        LegacyCareerError,
        encode_save_bytes,
        is_pre_1_9_save,
        save_path_for,
    )

    # Careers created before the 1.9 line do not restore here, for the same
    # reason the load gate refuses their local files: 1.9 starts everyone
    # fresh. Checked before anything touches disk; the cloud copy stays in
    # the account, still restorable by the 1.8 builds that made it.
    if is_pre_1_9_save(payload["profile"]):
        raise LegacyCareerError(str(payload["profile"].get("name") or "Driver"))
    profile = verify_cloud_revision(payload["profile"], payload)
    # Absolution. The server grants this only on a revision it signed and
    # fully validated, so a career that was marked purely for moving between
    # computers stops carrying the mark. The signature is verified above,
    # before this is read -- an unsigned or failed reply never gets here, and
    # a career that really was edited fails validation instead of arriving
    # with the flag set.
    if payload.get("clearIntegrityFlag") is True:
        profile.integrity_modified = False
        profile.integrity_notice_pending = False
    signed_data = profile.to_dict()
    name = save_slot_name(profile.name)
    path = save_path_for(name)
    tmp = path.with_suffix(SAVE_SUFFIX + ".tmp")
    backup = path.with_suffix(SAVE_SUFFIX + ".bak")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "wb") as f:
        f.write(encode_save_bytes(signed_data))
    moved_old = False
    try:
        if path.exists():
            backup.unlink(missing_ok=True)
            path.replace(backup)
            moved_old = True
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True)
        if moved_old and backup.exists() and not path.exists():
            backup.replace(path)
        raise
    # A leftover plain-JSON save for this career would shadow nothing (the
    # packed file wins), but move it aside so only one live copy remains.
    legacy = path.with_suffix(LEGACY_SAVE_SUFFIX)
    if legacy.exists():
        with contextlib.suppress(OSError):
            legacy.replace(legacy.with_suffix(".json.bak"))
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
        # slot name -> (profile dict snapshot, queued-at time, attempt token).
        # The token rides with the snapshot so an upload's terminal result is
        # always recorded against the attempt that queued it, never against a
        # manual attempt that started while it was in flight.
        self._pending: dict[str, tuple[dict, float, int]] = {}
        self._retry_at: float | None = None
        # Manual "Save game" attempts (backup_now): the latest attempt token
        # handed out per slot, and the outcome recorded when an upload for
        # that slot reaches a terminal result. Both guarded by self._lock.
        self._attempts: dict[str, int] = {}
        self._outcomes: dict[str, tuple[int, str]] = {}

        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False
        self._status = "Cloud backup is ready."

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
        self._log_sync_state()
        self._stop.clear()
        if self._threaded:
            self._thread = threading.Thread(target=self._run, name="cloud-saves", daemon=True)
            self._thread.start()

    def _log_sync_state(self) -> None:
        """One line per known slot at startup: the kept session logs only go
        back two sessions, so a stall whose conflict was recorded earlier
        would otherwise leave no trace in the log a tester shares."""
        slots = self.sync_state.slots()
        if not slots:
            log.info("Cloud sync state: no careers have synced from this computer yet")
            return
        for name, entry in sorted(slots.items()):
            revision = entry.get("revision")
            synced = (
                f"last synced revision {revision}"
                if revision is not None
                else "no revision synced yet"
            )
            conflict = entry.get("conflict")
            if conflict is None:
                log.info("Cloud sync state for %s: %s", name, synced)
            else:
                log.info(
                    "Cloud sync state for %s: %s; a conflict against cloud "
                    "revision %s is waiting in the Cloud backup menu",
                    name,
                    synced,
                    conflict.get("latestRevision"),
                )

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
            # Token 0: a background save, which no manual watch ever matches.
            self._pending[name] = (snapshot, self._clock(), 0)
        if self._threaded:
            self._wake.set()
        else:
            self.pump()

    def backup_now(self, profile: Profile) -> int | None:
        """Snapshot a just-saved profile and attempt its upload promptly.

        The manual "Save game" path (Shane's report, 2026-08-14: a silent
        background upload is indistinguishable from no backup for a screen
        reader user). Like :meth:`queue_backup`, but the snapshot is queued
        as already past the debounce, the transient-retry backoff is lifted
        for this attempt, and the worker is woken immediately. Every other
        semantic -- the content-hash skip, conflict, rejection, and auth
        handling -- is exactly the background queue's.

        Returns an attempt token the caller can poll through
        :meth:`outcome_for` without ever blocking, or None when the service
        is off or the snapshot failed.
        """
        if not self._enabled:
            return None
        try:
            snapshot = profile.to_dict()
        except Exception:  # never let backup break the save that triggered it
            log.debug("Cloud backup snapshot failed", exc_info=True)
            return None
        name = save_slot_name(profile.name)
        with self._lock:
            token = self._attempts.get(name, 0) + 1
            self._attempts[name] = token
            # Queued as already debounce-old, so the next pump owes it an
            # attempt instead of a wait.
            self._pending[name] = (snapshot, self._clock() - self._debounce, token)
            # A manual save is the player asking now: this attempt does not
            # sit out a backoff armed by an earlier transient failure.
            self._retry_at = None
        if self._threaded:
            self._wake.set()
        else:
            self.pump()
        return token

    def outcome_for(self, name: str, token: int) -> str | None:
        """The recorded outcome of a :meth:`backup_now` attempt, or None
        while it is still in flight. Never blocks.

        Outcomes: ``"accepted"``, ``"unchanged"`` (the cloud already holds
        this exact content), ``"conflict"`` (recorded for the Cloud backup
        menu), ``"auth"``, ``"network"`` (still retrying in the background),
        or ``"rejected:<reason>"``.
        """
        with self._lock:
            entry = self._outcomes.get(name)
            if entry is None or entry[0] < token:
                return None
            return entry[1]

    def _note_outcome(self, name: str, token: int, outcome: str) -> None:
        """Record a terminal upload result under the attempt token its
        snapshot was queued with (0 for background saves, which no poller
        ever matches). Uploads run outside the lock, so an upload already in
        flight when a newer manual attempt starts finishes carrying its own
        older token: it must neither answer for the newer attempt nor
        overwrite the newer attempt's recorded result."""
        with self._lock:
            current = self._outcomes.get(name)
            if current is None or token >= current[0]:
                self._outcomes[name] = (token, outcome)

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

    @property
    def status(self) -> str:
        """Short persistent player-facing result for the Cloud backup menu."""
        # Never claim readiness while the service is off: 1.9 testers heard
        # "ready" with the setting off and believed they were backed up.
        if not self._enabled:
            return "Cloud backup is off. Saves on this computer are not backed up."
        with self._lock:
            return self._status

    def _set_status(self, message: str) -> None:
        with self._lock:
            self._status = message

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
            oldest = min(t for _, t, _ in self._pending.values())
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
                (name, snapshot, token)
                for name, (snapshot, queued_at, token) in self._pending.items()
                if force or now - queued_at >= self._debounce
            ]
        for name, snapshot, token in due:
            if self._stop.is_set() and not force:
                return
            self._upload_slot(name, snapshot, token)

    def _done_with(self, name: str, snapshot: dict) -> None:
        """Drop a handled snapshot -- unless a newer save replaced it while
        the upload was in flight, which must stay queued."""
        with self._lock:
            current = self._pending.get(name)
            if current is not None and current[0] is snapshot:
                del self._pending[name]

    def _upload_slot(self, name: str, snapshot: dict, token: int = 0) -> None:
        slot = self.sync_state.slot(name)
        conflict = slot.get("conflict")
        if conflict is not None and conflict.get("latestRevision") is None:
            # Recorded by an older build against an empty cloud slot (wiped
            # deployment, or deleted from another machine). No newer save
            # exists to protect, so start the slot over instead of staying
            # silent forever.
            self.sync_state.forget(name)
            slot = {}
        elif conflict is not None:
            # A known conflict names a real cloud revision -- but that copy
            # may have vanished since it was recorded (deployment reset, or
            # the slot deleted from another machine), and then there is
            # nothing left to protect. Re-check before staying silent.
            if self._cloud_slot_exists(name):
                # Still there: the player resolves it from the Cloud backup
                # menu. Drop the snapshot -- the local file is still the
                # source of truth for "keep mine".
                self._done_with(name, snapshot)
                self._note_outcome(name, token, "conflict")
                return
            log.info(
                "Cloud backup of %s was blocked by a conflict whose cloud "
                "copy no longer exists; restarting the slot fresh",
                name,
            )
            self.sync_state.forget(name)
            slot = {}
        _, content_hash = cloud_content(snapshot)
        if slot.get("hash") == content_hash:
            self._done_with(name, snapshot)
            self._note_outcome(name, token, "unchanged")
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
            self._set_status("Latest backup accepted and server-verified.")
            self._note_outcome(name, token, "accepted")
            log.info("Cloud backup of %s uploaded as revision %s", name, result["revision"])
            return
        if result.get("reason") == "conflict":
            if result.get("latestRevision") is None:
                # The cloud slot is empty -- the staging deployment was wiped,
                # or the slot was deleted from another machine -- so there is
                # no newer save to protect. Drop the stale revision and let the
                # retry pass re-create the slot from this machine's save.
                self.sync_state.forget(name)
                self._retry_at = self._clock() + self._retry
                self._note_outcome(name, token, "network")
                log.info(
                    "Cloud backup of %s named a revision the cloud no longer "
                    "has; restarting the slot fresh",
                    name,
                )
                return
            self.sync_state.record_conflict(name, result)
            self._done_with(name, snapshot)
            self._note_outcome(name, token, "conflict")
            log.warning(
                "Cloud backup of %s skipped: the cloud copy is newer (revision %s)",
                name,
                result.get("latestRevision"),
            )
            return
        family = classify_upload_failure(result.get("reason"))
        if family == "auth":
            # The credentials were retired (usually by connecting another
            # computer); every retry would fail identically, and the player
            # can only fix it by reconnecting.
            self._set_status(AUTH_PAUSED_STATUS)
            self._done_with(name, snapshot)
            self._note_outcome(name, token, "auth")
            return
        if family == "rejected":
            # Not transient: retrying with the same inputs cannot succeed.
            # The raw reason code is logged for review but never spoken --
            # only the honest, career-named story below is.
            reason = result.get("reason")
            log.warning("Cloud backup of %s was rejected: %s", name, reason)
            self._set_status(rejection_status(name, reason))
            self._done_with(name, snapshot)
            self._note_outcome(name, token, f"rejected:{reason}")
            return
        # Transient (network, 5xx): keep the snapshot, back off.
        self._retry_at = self._clock() + self._retry
        self._note_outcome(name, token, "network")

    def _cloud_slot_exists(self, name: str) -> bool:
        """Whether the cloud still holds any revision of this slot. Errs on
        the side of True: an unreachable or refusing server must keep the
        conflict guard in place."""
        try:
            reply = list_saves(self._identity, transport=self._transport)
        except CloudAuthError:
            return True
        if reply is None:
            return True
        # The reply grew a wrapper dict when the public-career choice landed;
        # accept both shapes so this survives either side of that change.
        entries = reply["saves"] if isinstance(reply, dict) else reply
        return any(entry.get("saveName") == name for entry in entries)

    def resolve_keep_mine(self, name: str, profile_dict: dict) -> str:
        """Conflict choice: overwrite the cloud with this machine's save.

        Called from a menu worker thread. Uploads with the server's latest
        revision as parent, which the conflict entry recorded. Returns
        ``"ok"`` on success, or the classified failure family the caller
        needs to speak the real cause instead of always blaming the
        connection (Jessie's report, 2026-08-14; see
        ``classify_upload_failure``): ``"auth"``, ``"conflict"`` (the cloud
        moved again since this conflict was recorded), ``"network"``, or --
        for a server rejection -- ``"rejected:<reason>"``, carrying the raw
        reason code so the caller can build the same career-named,
        family-split story as the background queue via
        :func:`rejection_status` (this menu is the exact button a
        conflicted tester presses, so a bare "rejected" tag with no career
        name or cause was not enough; see :mod:`freight_fate.states.cloud_save_states`).
        """
        if self._identity is None:
            return "network"
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
            return "ok"
        if result.get("reason") == "conflict":
            # The cloud moved again since the conflict was recorded; refresh
            # the details so the menu speaks current numbers.
            self.sync_state.record_conflict(name, result)
            return "conflict"
        reason = result.get("reason")
        log.warning("Cloud keep-mine upload of %s failed: %s", name, reason)
        family = classify_upload_failure(reason)
        if family == "rejected":
            # Carry the raw reason through the return value the caller
            # already treats as an opaque tag, so it can speak the same
            # career-named, family-split story cases 1-4 speak -- never the
            # raw code itself, which stays log-only (logged just above).
            return f"rejected:{reason}"
        return family
