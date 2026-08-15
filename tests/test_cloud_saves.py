"""Tests for the opt-in cloud save backup service.

These cover what must hold whether or not orinks.net is reachable: the
off-by-default path, the signature-stripped portable content form, debounce
and no-change skipping, the parent-revision conflict guard, the save-listener
hook, and restores (which must verify the server signature and receive a new
local signature). A fake transport and an injected clock keep every test
deterministic and free of real sockets.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import urllib.error

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from speech_capture import speech_stub

from freight_fate import cloud_save_integrity
from freight_fate.cloud_save_integrity import CloudSaveIntegrityError, canonical_profile
from freight_fate.cloud_saves import (
    AUTH_PAUSED_STATUS,
    DEBOUNCE_S,
    RETRY_INTERVAL_S,
    CloudAuthError,
    CloudSaves,
    SyncState,
    backup_summary,
    classify_upload_failure,
    cloud_content,
    conflict_status,
    delete_save,
    download_save,
    list_saves,
    profile_dict_from_content,
    rejection_status,
    restore_to_disk,
    save_slot_name,
    set_public_save,
    upload_save,
)
from freight_fate.models import profile as profile_module
from freight_fate.models.profile import SIGNATURE_FIELD, Profile, _decode_save_bytes
from freight_fate.online_presence import OnlineIdentity, base_url
from freight_fate.settings import Settings

IDENTITY = OnlineIdentity(driver_id="driver-testtest", driver_token="t" * 48)
TEST_KEY_ID = "test-key"
TEST_PRIVATE_KEY = Ed25519PrivateKey.generate()
TEST_PUBLIC_KEY = TEST_PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)


class FakeTransport:
    """Records every request; replies from a queue or raises."""

    def __init__(self, *, reply: dict | None = None, error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error
        self.requests: list[tuple[str, dict | None, dict[str, str]]] = []
        self.revision = 0

    def __call__(self, url: str, payload: dict | None, headers: dict[str, str]) -> dict:
        self.requests.append((url, payload, headers))
        if self.error is not None:
            raise self.error
        if self.reply is not None:
            return self.reply
        self.revision += 1
        return {"ok": True, "revision": self.revision}

    @property
    def posts(self) -> list[dict]:
        return [p for _, p, _ in self.requests if p is not None]


def auth_error(code: int = 401, error: str | None = None) -> urllib.error.HTTPError:
    """The server's answer to a retired driver token (see issue 64: a new
    token issued to a second computer retires the one stored here)."""
    body = json.dumps({"error": error} if error else {}).encode("utf-8")
    return urllib.error.HTTPError("url", code, "Unauthorized", None, io.BytesIO(body))


def conflict_error(latest_revision: int = 5) -> urllib.error.HTTPError:
    body = json.dumps(
        {
            "error": "conflict",
            "latestRevision": latest_revision,
            "latestCreatedAt": 1_700_000_000_000,
            "latestSummary": "Rig Hauler, level 9, 88,000 dollars",
        }
    ).encode("utf-8")
    return urllib.error.HTTPError("url", 409, "Conflict", None, io.BytesIO(body))


def rejected_error(reason: str = "invalid_achievement", code: int = 400) -> urllib.error.HTTPError:
    """The server's answer to a save the validator flatly refuses -- not a
    connection problem, and not transient: the same input will fail again."""
    body = json.dumps({"error": reason}).encode("utf-8")
    return urllib.error.HTTPError("url", code, "Bad Request", None, io.BytesIO(body))


class Clock:
    """A manually advanced monotonic clock."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def make_service(transport, clock, *, enabled=True, identity=IDENTITY):
    """A synchronous (non-threaded) service wired to a fake transport."""
    return CloudSaves(
        enabled=enabled,
        identity=identity,
        clock=clock,
        transport=transport,
        threaded=False,
    )


@pytest.fixture(autouse=True)
def isolated_cloud_integrity(monkeypatch):
    """Tests own the module-level hook; leave nothing behind."""
    monkeypatch.setattr(cloud_save_integrity, "PUBLIC_KEYS", {TEST_KEY_ID: TEST_PUBLIC_KEY})
    yield
    profile_module.save_listener = None


def drain(service, clock):
    """Let the debounce pass and pump once, as the worker would."""
    clock.advance(DEBOUNCE_S + 0.1)
    service.pump()


# -- content form ---------------------------------------------------------------


def test_cloud_content_is_portable_and_round_trips():
    profile = Profile(name="Road Star", money=12_345.0)
    profile.save()  # signs the local file; to_dict() carries the signature
    d = profile.to_dict()
    assert SIGNATURE_FIELD in d

    content, content_hash = cloud_content(d)
    restored = profile_dict_from_content(content)
    # The signature is machine-local: it must never travel.
    assert SIGNATURE_FIELD not in restored
    assert "_signature_version" not in restored
    assert restored["name"] == "Road Star"
    assert restored["money"] == 12_345.0
    assert restored["version"] == d["version"]

    # Deterministic bytes: the same snapshot always hashes the same, so
    # unchanged profiles can skip uploads by hash alone.
    again, again_hash = cloud_content(profile.to_dict())
    assert again == content
    assert again_hash == content_hash


def test_slot_name_matches_local_file_stem():
    profile = Profile(name="Road * Star?")
    assert save_slot_name(profile.name) == profile.path.stem


def test_backup_summary_reads_like_speech():
    d = Profile(name="Road Star", money=12_345.0).to_dict()
    assert backup_summary(d) == "Road Star, level 1, 12,345 dollars"


# -- disabled and unconfigured paths ---------------------------------------------


def test_cloud_saves_default_off():
    # Private backup and public Profile sharing are separate consents.
    assert Settings().cloud_saves is False


def test_disabled_never_posts():
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock, enabled=False)
    service.queue_backup(Profile(name="Road Star"))
    drain(service, clock)
    assert transport.requests == []


def test_enabled_without_identity_stays_dormant():
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock, identity=None)
    assert not service.enabled
    service.queue_backup(Profile(name="Road Star"))
    drain(service, clock)
    assert transport.requests == []


def test_status_says_off_while_backups_are_disabled():
    # The menu's status line must never claim readiness while the service is
    # off: signed-in 1.9 testers heard "Cloud backup is ready" and believed
    # they were backed up when nothing was ever uploaded.
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock, enabled=False)
    assert service.status == "Cloud backup is off. Saves on this computer are not backed up."
    service.set_enabled(True)
    assert service.status == "Cloud backup is ready."


# -- upload scheduling ------------------------------------------------------------


def test_debounce_holds_then_uploads_once():
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)
    profile = Profile(name="Road Star")

    # A burst of saves inside the debounce window collapses to one upload.
    service.queue_backup(profile)
    service.pump()
    assert transport.requests == []
    profile.money += 100
    service.queue_backup(profile)
    drain(service, clock)

    assert len(transport.posts) == 1
    payload = transport.posts[0]
    assert transport.requests[0][0] == f"{base_url()}/api/freight-fate/saves"
    assert payload["driverId"] == IDENTITY.driver_id
    assert payload["saveName"] == "Road Star"
    assert payload["parentRevision"] is None
    assert payload["saveVersion"] == profile.to_dict()["version"]
    assert transport.requests[0][2]["Authorization"] == f"Bearer {IDENTITY.driver_token}"
    # The upload carries the latest snapshot from the burst.
    uploaded = profile_dict_from_content(base64.b64decode(payload["content"]))
    assert uploaded["money"] == profile.money

    # The synced revision becomes the next upload's parent.
    assert service.sync_state.slot("Road Star")["revision"] == 1


def test_unchanged_profile_skips_the_upload():
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)
    profile = Profile(name="Road Star")

    service.queue_backup(profile)
    drain(service, clock)
    service.queue_backup(profile)  # nothing changed
    drain(service, clock)

    assert len(transport.posts) == 1


def test_next_change_uploads_with_the_synced_parent():
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)
    profile = Profile(name="Road Star")

    service.queue_backup(profile)
    drain(service, clock)
    profile.money += 500
    service.queue_backup(profile)
    drain(service, clock)

    assert len(transport.posts) == 2
    assert transport.posts[1]["parentRevision"] == 1
    assert service.sync_state.slot("Road Star")["revision"] == 2


def test_transient_failure_retries_later():
    transport = FakeTransport(error=OSError("no network"))
    clock = Clock()
    service = make_service(transport, clock)
    service.queue_backup(Profile(name="Road Star"))
    drain(service, clock)
    assert len(transport.posts) == 1

    # Before the retry interval nothing new is attempted...
    service.pump()
    assert len(transport.posts) == 1

    # ...after it, the pending snapshot goes out and syncs.
    transport.error = None
    clock.advance(RETRY_INTERVAL_S + 0.1)
    service.pump()
    assert len(transport.posts) == 2
    assert service.sync_state.slot("Road Star")["revision"] == 1


# -- the conflict guard -----------------------------------------------------------


def test_conflict_marks_the_slot_and_stops_backups():
    transport = FakeTransport(error=conflict_error(latest_revision=5))
    clock = Clock()
    service = make_service(transport, clock)
    profile = Profile(name="Road Star")

    service.queue_backup(profile)
    drain(service, clock)
    assert len(transport.posts) == 1

    conflict = service.conflicts()["Road Star"]
    assert conflict["latestRevision"] == 5
    assert "level 9" in conflict["latestSummary"]

    # Until the player chooses a side, this slot must not retry into the
    # conflict -- another machine's newer save is at stake.
    transport.error = None
    profile.money += 999
    service.queue_backup(profile)
    drain(service, clock)
    assert len(transport.posts) == 1


def test_empty_cloud_conflict_restarts_the_slot_instead_of_sticking():
    """A conflict whose latest revision is null means the cloud slot is empty
    (the deployment was wiped, or the slot was deleted from another machine).
    There is no newer save at stake, so the guard must not stick: the slot
    starts over as a fresh upload instead of silently never backing up again.
    """
    transport = FakeTransport(error=conflict_error(latest_revision=None))
    clock = Clock()
    service = make_service(transport, clock)
    # This machine remembers a revision the server no longer has.
    service.sync_state.record_synced("Road Star", 7, "stale-hash")
    profile = Profile(name="Road Star")

    service.queue_backup(profile)
    drain(service, clock)
    assert len(transport.posts) == 1
    assert transport.posts[0]["parentRevision"] == 7
    # Not a real conflict: nothing is recorded for the player to resolve.
    assert service.conflicts() == {}

    # The stale revision is gone, and the retry goes out as a fresh slot.
    transport.error = None
    clock.advance(RETRY_INTERVAL_S + 0.1)
    service.pump()
    assert len(transport.posts) == 2
    assert transport.posts[1]["parentRevision"] is None
    assert service.sync_state.slot("Road Star")["revision"] == 1


def test_recorded_empty_cloud_conflict_heals_on_the_next_backup():
    """Older builds recorded the empty-cloud conflict as sticky. A save made
    under this build must clear that mark and back up fresh."""
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)
    service.sync_state.record_synced("Road Star", 7, "stale-hash")
    service.sync_state.record_conflict("Road Star", {"latestRevision": None})
    profile = Profile(name="Road Star")

    service.queue_backup(profile)
    drain(service, clock)
    assert len(transport.posts) == 1
    assert transport.posts[0]["parentRevision"] is None
    assert service.conflicts() == {}
    assert service.sync_state.slot("Road Star")["revision"] == 1


class RoutedTransport:
    """Serves the slot-list GET and the upload POST from one fake."""

    def __init__(self, *, list_reply, upload_reply=None, list_error=None) -> None:
        self.list_reply = list_reply
        self.list_error = list_error
        self.upload_reply = upload_reply or {"ok": True, "revision": 1}
        self.requests: list[tuple[str, dict | None, dict[str, str]]] = []

    def __call__(self, url: str, payload: dict | None, headers: dict[str, str]) -> dict:
        self.requests.append((url, payload, headers))
        if payload is None:  # the list fetch
            if self.list_error is not None:
                raise self.list_error
            return self.list_reply
        return self.upload_reply

    @property
    def posts(self) -> list[dict]:
        return [p for _, p, _ in self.requests if p is not None]


def test_stale_recorded_conflict_heals_when_the_cloud_slot_is_gone():
    """A conflict recorded against a cloud copy that has since vanished
    (deployment reset, slot deleted from another machine) must not block
    backups forever: the guard re-checks the cloud and starts over."""
    transport = RoutedTransport(list_reply={"ok": True, "saves": []})
    clock = Clock()
    service = make_service(transport, clock)
    service.sync_state.record_synced("Road Star", 7, "stale-hash")
    service.sync_state.record_conflict(
        "Road Star",
        {"latestRevision": 40, "latestCreatedAt": 1_700_000_000_000, "latestSummary": "level 18"},
    )
    profile = Profile(name="Road Star")

    service.queue_backup(profile)
    drain(service, clock)
    assert len(transport.posts) == 1
    assert transport.posts[0]["parentRevision"] is None
    assert service.conflicts() == {}
    assert service.sync_state.slot("Road Star")["revision"] == 1


def test_recorded_conflict_with_a_live_cloud_copy_still_blocks():
    transport = RoutedTransport(
        list_reply={"ok": True, "saves": [{"saveName": "Road Star", "revision": 40}]}
    )
    clock = Clock()
    service = make_service(transport, clock)
    service.sync_state.record_synced("Road Star", 7, "stale-hash")
    service.sync_state.record_conflict("Road Star", {"latestRevision": 40})
    profile = Profile(name="Road Star")

    service.queue_backup(profile)
    drain(service, clock)
    # The other machine's newer save is still at stake: nothing uploads and
    # the conflict stays for the player to resolve.
    assert transport.posts == []
    assert "Road Star" in service.conflicts()


def test_conflict_recheck_that_cannot_reach_the_cloud_keeps_the_guard():
    transport = RoutedTransport(list_reply={}, list_error=OSError("no route"))
    clock = Clock()
    service = make_service(transport, clock)
    service.sync_state.record_conflict("Road Star", {"latestRevision": 40})
    profile = Profile(name="Road Star")

    service.queue_backup(profile)
    drain(service, clock)
    assert transport.posts == []
    assert "Road Star" in service.conflicts()


def test_start_logs_the_sync_state_for_each_slot(caplog):
    """The startup dump puts every slot's sync state into the session log, so
    a tester's shared game.log explains a stalled career even when the
    session that recorded the conflict has rotated out of the kept logs."""
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)
    service.sync_state.record_synced("Road Star", 41, "hash-a")
    service.sync_state.record_synced("Night Owl", 3, "hash-b")
    service.sync_state.record_conflict(
        "Night Owl",
        {"latestRevision": 44, "latestCreatedAt": 1_700_000_000_000, "latestSummary": "level 18"},
    )

    with caplog.at_level(logging.INFO, logger="freight_fate.cloud_saves"):
        service.start()

    lines = [r.getMessage() for r in caplog.records if "Cloud sync state" in r.getMessage()]
    healthy = next(line for line in lines if "Road Star" in line)
    assert "revision 41" in healthy
    assert "conflict" not in healthy
    blocked = next(line for line in lines if "Night Owl" in line)
    assert "revision 3" in blocked
    assert "conflict" in blocked and "44" in blocked


def test_start_with_no_sync_state_says_so(caplog):
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)

    with caplog.at_level(logging.INFO, logger="freight_fate.cloud_saves"):
        service.start()

    assert any(
        "Cloud sync state" in r.getMessage() and "no careers" in r.getMessage()
        for r in caplog.records
    )


def test_keep_mine_overwrites_the_cloud_and_clears_the_conflict():
    transport = FakeTransport(error=conflict_error(latest_revision=5))
    clock = Clock()
    service = make_service(transport, clock)
    profile = Profile(name="Road Star")

    service.queue_backup(profile)
    drain(service, clock)
    assert "Road Star" in service.conflicts()

    transport.error = None
    transport.reply = {"ok": True, "revision": 6}
    assert service.resolve_keep_mine("Road Star", profile.to_dict())
    # The upload named the server's latest revision as parent: a plain
    # last-write-wins overwrite, chosen explicitly by the player.
    assert transport.posts[-1]["parentRevision"] == 5
    assert service.conflicts() == {}
    assert service.sync_state.slot("Road Star")["revision"] == 6


# -- upload failure classification (Jessie's report, 2026-08-14: an -------------
# -- invalid_achievement refusal was told to the player as "check your ---------
# -- connection") ----------------------------------------------------------------


def test_classify_upload_failure_sorts_the_three_honest_families():
    assert classify_upload_failure("invalid_achievement") == "rejected"
    assert classify_upload_failure("too_large") == "rejected"
    assert classify_upload_failure("unauthorized") == "auth"
    assert classify_upload_failure("driver_not_found") == "auth"
    assert classify_upload_failure("http_401") == "auth"
    # A raw network error, a 5xx, or a code this table has not been taught
    # yet must default to network -- retry is the safe failure mode.
    assert classify_upload_failure("error") == "network"
    assert classify_upload_failure("http_500") == "network"
    assert classify_upload_failure(None) == "network"


def test_a_permanent_refusal_is_never_left_to_retry_as_if_it_were_the_network():
    """Two server refusals were missing from this table, so
    ``classify_upload_failure`` sorted them as "network" and the queue backed
    off and retried forever without telling the player anything. Neither can
    ever succeed on a retry: one needs the player to free a slot, the other
    needs the server fixed. Same class as Jessie's ``invalid_achievement``
    told as "check your connection" (2026-08-14), different codes."""
    assert classify_upload_failure("too_many_slots") == "rejected"
    assert classify_upload_failure("signing_unavailable") == "rejected"


@pytest.mark.parametrize(
    "reason, expected",
    [
        ("too_many_slots", "as many careers backed up as the server keeps"),
        ("signing_unavailable", "could not finish signing"),
    ],
)
def test_each_new_refusal_gets_its_own_honest_sentence(reason, expected):
    """A refusal the player can clear themselves and one that is ours to fix
    must not share the generic line -- only one of them has anything to do."""
    spoken = rejection_status("Little Bear", reason)
    assert spoken.startswith("Little Bear: backup not accepted.")
    assert expected in spoken
    # No jargon reaches the player: the reason code itself never speaks.
    assert reason not in spoken


def test_resolve_keep_mine_reports_network_for_a_transport_error():
    transport = FakeTransport(error=OSError("network unreachable"))
    service = make_service(transport, Clock())
    profile = Profile(name="Road Star")

    assert service.resolve_keep_mine("Road Star", profile.to_dict()) == "network"


def test_resolve_keep_mine_reports_auth_for_a_retired_token():
    transport = FakeTransport(error=auth_error())
    service = make_service(transport, Clock())
    profile = Profile(name="Road Star")

    assert service.resolve_keep_mine("Road Star", profile.to_dict()) == "auth"


def test_resolve_keep_mine_reports_rejected_for_a_validator_refusal():
    # The raw reason rides along (Shane's report, 2026-08-14: the menu that
    # resolves a conflict needs it to speak the same career-named,
    # family-split story as the background queue, not a bare tag).
    transport = FakeTransport(error=rejected_error("invalid_achievement"))
    service = make_service(transport, Clock())
    profile = Profile(name="Road Star")

    assert (
        service.resolve_keep_mine("Road Star", profile.to_dict()) == "rejected:invalid_achievement"
    )


@pytest.mark.parametrize(
    "reason", ["impossible_xp", "impossible_money", "invalid_schema", "unsupported_version"]
)
def test_resolve_keep_mine_carries_every_rejected_reason(reason):
    """Every code classify_upload_failure sorts as "rejected" round-trips
    through resolve_keep_mine's return value -- not just the one used above
    -- so cloud_save_states.py can build the right family-specific story for
    each of them."""
    transport = FakeTransport(error=rejected_error(reason))
    service = make_service(transport, Clock())
    profile = Profile(name="Road Star")

    assert service.resolve_keep_mine("Road Star", profile.to_dict()) == f"rejected:{reason}"


def test_resolve_keep_mine_rejection_logs_the_raw_reason_but_the_tag_never_speaks_it(caplog):
    transport = FakeTransport(error=rejected_error("impossible_money"))
    service = make_service(transport, Clock())
    profile = Profile(name="Road Star")

    with caplog.at_level(logging.WARNING, logger="freight_fate.cloud_saves"):
        result = service.resolve_keep_mine("Road Star", profile.to_dict())

    lines = [r.getMessage() for r in caplog.records if "keep-mine upload" in r.getMessage()]
    assert any("Road Star" in line and "impossible_money" in line for line in lines)
    assert result == "rejected:impossible_money"


# -- the save-listener hook -------------------------------------------------------


def test_every_profile_save_queues_a_backup():
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)
    profile_module.save_listener = service.queue_backup

    profile = Profile(name="Road Star")
    profile.save()
    drain(service, clock)

    assert len(transport.posts) == 1
    assert transport.posts[0]["saveName"] == "Road Star"


def test_a_failing_listener_never_breaks_the_local_save():
    def explode(_profile):
        raise RuntimeError("backup service on fire")

    profile_module.save_listener = explode
    profile = Profile(name="Road Star")
    path = profile.save()  # must not raise
    assert path.exists()
    assert Profile.load(path).name == "Road Star"


# -- download and restore ----------------------------------------------------------


def make_cloud_reply(profile_dict: dict, revision: int = 3) -> dict:
    content, content_hash = cloud_content(profile_dict)
    portable = profile_dict_from_content(content)
    signature = TEST_PRIVATE_KEY.sign(canonical_profile(portable))
    return {
        "ok": True,
        "saveName": save_slot_name(str(profile_dict.get("name", "Driver"))),
        "revision": revision,
        "saveVersion": profile_dict.get("version", 0),
        "contentHash": content_hash,
        "sizeBytes": len(content),
        "summary": backup_summary(profile_dict),
        "createdAt": 1_700_000_000_000,
        "content": base64.b64encode(content).decode("ascii"),
        "sig": base64.b64encode(signature).decode("ascii"),
        "keyId": TEST_KEY_ID,
        "signedAt": "2026-07-13T12:00:00.000Z",
        "validatorVersion": 1,
    }


def test_download_verifies_the_content_hash():
    good = make_cloud_reply(Profile(name="Road Star").to_dict())
    payload = download_save(IDENTITY, save_name="Road Star", transport=FakeTransport(reply=good))
    assert payload is not None
    assert payload["profile"]["name"] == "Road Star"

    tampered = dict(good, contentHash="0" * 64)
    assert (
        download_save(IDENTITY, save_name="Road Star", transport=FakeTransport(reply=tampered))
        is None
    )


def test_download_rejects_missing_or_future_verification_metadata():
    unsigned = make_cloud_reply(Profile(name="Road Star").to_dict())
    unsigned.pop("sig")
    with pytest.raises(CloudSaveIntegrityError) as missing:
        download_save(IDENTITY, save_name="Road Star", transport=FakeTransport(reply=unsigned))
    assert missing.value.code == "unverified"

    future = make_cloud_reply(Profile(name="Road Star").to_dict())
    future["validatorVersion"] = 2
    with pytest.raises(CloudSaveIntegrityError) as newer:
        download_save(IDENTITY, save_name="Road Star", transport=FakeTransport(reply=future))
    assert newer.value.code == "update_required"


def test_download_rejects_payload_changed_after_server_signing():
    reply = make_cloud_reply(Profile(name="Road Star", money=77_000.0).to_dict())
    changed = Profile(name="Road Star", money=88_000.0).to_dict()
    content, content_hash = cloud_content(changed)
    reply["content"] = base64.b64encode(content).decode("ascii")
    reply["contentHash"] = content_hash

    with pytest.raises(CloudSaveIntegrityError) as tampered:
        download_save(IDENTITY, save_name="Road Star", transport=FakeTransport(reply=reply))

    assert tampered.value.code == "integrity_failed"


def test_restore_verifies_then_writes_a_locally_signed_save():
    # The cloud copy came from another machine. Its portable payload has an
    # orinks.net signature, then receives this installation's local HMAC before
    # the atomic replacement is installed.
    original = Profile(name="Road Star", money=77_000.0)
    reply = make_cloud_reply(original.to_dict(), revision=4)
    payload = download_save(IDENTITY, save_name="Road Star", transport=FakeTransport(reply=reply))

    # An older local save exists and must survive as the fallback file.
    local = Profile(name="Road Star", money=5.0)
    local_path = local.save()

    sync_state = SyncState()
    path = restore_to_disk(payload, sync_state)
    assert path == local_path

    restored = Profile.load(path)
    assert restored.money == 77_000.0
    # Locally re-signed, and not flagged: a verified restore is not a tamper.
    assert restored.integrity_modified is False
    assert SIGNATURE_FIELD in _decode_save_bytes(path.read_bytes())[0]
    backup = path.with_suffix(".ffsave.bak")
    assert backup.exists()
    assert _decode_save_bytes(backup.read_bytes())[0]["money"] == 5.0
    # The fallback file must not appear in the careers list.
    assert backup not in Profile.list_saves()

    # The restored revision is the next upload's parent, so continuing this
    # career does not immediately conflict with the copy just downloaded.
    assert sync_state.slot("Road Star")["revision"] == 4


def test_unverified_restore_changes_neither_disk_nor_sync_state():
    local = Profile(name="Road Star", money=5.0)
    path = local.save()
    before = path.read_bytes()
    reply = make_cloud_reply(Profile(name="Road Star", money=77_000.0).to_dict())
    payload = download_save(IDENTITY, save_name="Road Star", transport=FakeTransport(reply=reply))
    assert payload is not None
    payload["sig"] = base64.b64encode(b"x" * 64).decode("ascii")
    sync_state = SyncState()

    with pytest.raises(CloudSaveIntegrityError, match="signature"):
        restore_to_disk(payload, sync_state)

    assert path.read_bytes() == before
    assert sync_state.slots() == {}


def test_upload_rejects_oversized_content():
    import os

    huge = Profile(name="Road Star").to_dict()
    # Incompressible padding: repeated text would gzip under the cap.
    huge["achievement_stats"] = {"pad": os.urandom(2 * 1024 * 1024).hex()}
    result = upload_save(
        IDENTITY,
        save_name="Road Star",
        profile_dict=huge,
        parent_revision=None,
        summary="too big",
        transport=FakeTransport(),
    )
    assert result == {"ok": False, "reason": "too_large"}


# -- settings menu -----------------------------------------------------------------


def key_event(key):
    import pygame

    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode="", mod=0)


def open_online_settings(app):
    import pygame

    from freight_fate.states.main_menu import SettingsState

    picker = SettingsState(app.ctx)
    app.push_state(picker)
    while picker.items[picker.index].text != "Online":
        picker.handle_event(key_event(pygame.K_DOWN))
    picker.handle_event(key_event(pygame.K_RETURN))
    return app.state


def test_cloud_toggle_requires_the_account_setup_first():
    import pygame

    from freight_fate.app import App

    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        cat = open_online_settings(app)
        while not cat.items[cat.index].text.startswith("Back up saves"):
            cat.handle_event(key_event(pygame.K_DOWN))
        assert cat.items[cat.index].text == "Back up saves to your orinks.net account: not set up"

        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.cloud_saves is False
        assert any("same orinks.net sign-in" in t for t in spoken)
    finally:
        app.shutdown()


def test_cloud_toggle_speaks_the_disclosure_when_turned_on():
    import pygame

    from freight_fate.app import App
    from freight_fate.states.cloud_save_states import CLOUD_DISCLOSURE

    IDENTITY.save()
    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        cat = open_online_settings(app)
        while not cat.items[cat.index].text.startswith("Back up saves"):
            cat.handle_event(key_event(pygame.K_DOWN))
        assert cat.items[cat.index].text == "Back up saves to your orinks.net account: off"

        cat.handle_event(key_event(pygame.K_RETURN))
        consent = app.state
        assert consent.title == "Turn Cloud backup on?"
        assert consent.items[0].text == "No, keep Cloud backup off"
        assert app.ctx.settings.cloud_saves is False
        assert any(CLOUD_DISCLOSURE in t for t in spoken)

        consent.handle_event(key_event(pygame.K_DOWN))
        consent.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.cloud_saves is True
        assert app.cloud.enabled
        assert Settings.load().cloud_saves is True

        spoken.clear()
        cat.handle_event(key_event(pygame.K_RETURN))
        assert app.ctx.settings.cloud_saves is False
        assert not app.cloud.enabled
    finally:
        app.shutdown()


# -- retired credentials (issue 64) ----------------------------------------------


def test_list_saves_refused_credentials_raise_cloud_auth_error():
    # A 401 means orinks.net answered and said no: the menus must tell the
    # player to reconnect, never blame the network.
    with pytest.raises(CloudAuthError):
        list_saves(IDENTITY, transport=FakeTransport(error=auth_error(401)))


def test_list_saves_unknown_driver_raises_cloud_auth_error():
    with pytest.raises(CloudAuthError):
        list_saves(
            IDENTITY, transport=FakeTransport(error=auth_error(404, error="driver_not_found"))
        )


def test_list_saves_network_trouble_stays_none():
    assert list_saves(IDENTITY, transport=FakeTransport(error=OSError("no route"))) is None


# -- the public career choice -----------------------------------------------------


def test_list_saves_carries_the_public_career_choice():
    transport = FakeTransport(
        reply={
            "ok": True,
            "saves": [{"saveName": "Road Star", "revision": 1}],
            "publicSaveName": "Road Star",
        }
    )
    reply = list_saves(IDENTITY, transport=transport)
    assert reply == {
        "saves": [{"saveName": "Road Star", "revision": 1}],
        "publicSaveName": "Road Star",
    }


def test_list_saves_from_a_server_without_the_choice_says_none():
    # orinks.net builds from before the public-career choice send only the
    # saves list; the menu must read that as "no career designated".
    transport = FakeTransport(reply={"ok": True, "saves": []})
    assert list_saves(IDENTITY, transport=transport) == {"saves": [], "publicSaveName": None}


def test_set_public_save_posts_the_choice():
    transport = FakeTransport(reply={"ok": True, "publicSaveName": "Road Star"})
    assert set_public_save(IDENTITY, save_name="Road Star", transport=transport)
    url, payload, headers = transport.requests[0]
    assert url.endswith("/saves/public-career")
    assert payload == {"driverId": IDENTITY.driver_id, "saveName": "Road Star"}
    assert headers["Authorization"] == f"Bearer {IDENTITY.driver_token}"


def test_set_public_save_refused_credentials_raise_cloud_auth_error():
    with pytest.raises(CloudAuthError):
        set_public_save(
            IDENTITY, save_name="Road Star", transport=FakeTransport(error=auth_error(401))
        )


def test_set_public_save_network_trouble_stays_false():
    assert not set_public_save(
        IDENTITY, save_name="Road Star", transport=FakeTransport(error=OSError("no route"))
    )


def test_download_refused_credentials_raise_cloud_auth_error():
    with pytest.raises(CloudAuthError):
        download_save(
            IDENTITY, save_name="Road Star", transport=FakeTransport(error=auth_error(401))
        )


def test_upload_with_retired_token_pauses_backups_with_reconnect_status():
    transport = FakeTransport(error=auth_error(401))
    clock = Clock()
    service = make_service(transport, clock)
    service.queue_backup(Profile(name="Road Star"))
    drain(service, clock)

    assert "Reconnect from the Online menu" in service.status
    # Not transient: the snapshot is dropped instead of retried forever.
    drain(service, clock)
    assert len(transport.posts) == 1


# -- rejected-upload status split (Shane's report, 2026-08-14: with more than -----
# -- one career backed up he could not tell which one was refused, or why) --------


def test_upload_rejected_for_impossible_money_names_the_career_and_offers_appeal():
    transport = FakeTransport(error=rejected_error("impossible_money"))
    clock = Clock()
    service = make_service(transport, clock)
    service.queue_backup(Profile(name="Road Star"))
    drain(service, clock)

    status = service.status
    assert status.startswith("Road Star: backup not accepted.")
    assert "flagged it for review" in status
    assert "tester document" in status


def test_upload_rejected_for_impossible_xp_speaks_the_same_arithmetic_story():
    transport = FakeTransport(error=rejected_error("impossible_xp"))
    clock = Clock()
    service = make_service(transport, clock)
    service.queue_backup(Profile(name="Night Owl"))
    drain(service, clock)

    status = service.status
    assert status.startswith("Night Owl: backup not accepted.")
    assert "flagged it for review" in status


def test_upload_rejected_for_invalid_schema_blames_the_build_not_the_player():
    transport = FakeTransport(error=rejected_error("invalid_schema"))
    clock = Clock()
    service = make_service(transport, clock)
    service.queue_backup(Profile(name="Road Star"))
    drain(service, clock)

    status = service.status
    assert status.startswith("Road Star: backup not accepted.")
    assert "build mismatch" in status
    assert "flagged" not in status


def test_upload_rejected_for_unsupported_version_speaks_the_same_schema_story():
    transport = FakeTransport(error=rejected_error("unsupported_version"))
    clock = Clock()
    service = make_service(transport, clock)
    service.queue_backup(Profile(name="Road Star"))
    drain(service, clock)

    assert "build mismatch" in service.status


def test_upload_rejected_for_an_unknown_city_names_the_server_as_behind():
    """A city the server has not caught up with is nobody's fault.

    Under the generic wording this reads as an unexplained refusal, and it is
    a live failure mode: a stale deployed catalog stopped a tester's backups
    for a day (2026-08-14) with nothing to tell them why.
    """
    transport = FakeTransport(error=rejected_error("invalid_city"))
    clock = Clock()
    service = make_service(transport, clock)
    service.queue_backup(Profile(name="Road Star"))
    drain(service, clock)

    status = service.status
    assert status.startswith("Road Star: backup not accepted.")
    assert "does not recognise the town" in status
    assert "flagged" not in status


def test_upload_rejected_for_an_unrecognized_code_falls_back_safely_with_the_name():
    transport = FakeTransport(error=rejected_error("invalid_market"))
    clock = Clock()
    service = make_service(transport, clock)
    service.queue_backup(Profile(name="Road Star"))
    drain(service, clock)

    assert service.status == (
        "Road Star: backup not accepted. Your local career is safe. "
        "Public details were not updated."
    )


def test_upload_rejected_logs_the_raw_reason_but_never_speaks_it(caplog):
    transport = FakeTransport(error=rejected_error("impossible_money"))
    clock = Clock()
    service = make_service(transport, clock)

    with caplog.at_level(logging.WARNING, logger="freight_fate.cloud_saves"):
        service.queue_backup(Profile(name="Road Star"))
        drain(service, clock)

    lines = [r.getMessage() for r in caplog.records if "was rejected" in r.getMessage()]
    assert any("Road Star" in line and "impossible_money" in line for line in lines)
    # The raw code is logged for review; the spoken status never says it.
    assert "impossible_money" not in service.status


# -- cross-language canonicalization (the byte form both sides sign) -------------


def test_canonical_profile_matches_the_server_byte_for_byte():
    # Expected string produced by the server's own canonicalization
    # (JSON.stringify over sorted keys, then the non-ASCII escape pass) run
    # in Node. The signature only verifies when Python lays out numbers the
    # same way: whole floats lose their ".0", decimals hold down to 1e-6,
    # exponents are unpadded, and negative zero prints as "0".
    payload = {
        "b": [1.5, 2.0, 1e-7, 0.00001],
        "a": {"x": -0.0, "y": 129881.73999999999, "z": 29571.0},
        "n": None,
        "s": "café — truck",
        "t": True,
        "big": 1e21,
        "tiny": 8.673617379884035e-19,
        "whole": 6.0,
    }
    expected = (
        '{"a":{"x":0,"y":129881.73999999999,"z":29571},'
        '"b":[1.5,2,1e-7,0.00001],"big":1e+21,"n":null,'
        '"s":"caf\\u00e9 \\u2014 truck","t":true,'
        '"tiny":8.673617379884035e-19,"whole":6}'
    )
    assert canonical_profile(payload) == expected.encode("utf-8")


def test_whole_float_profile_signature_round_trips():
    # The exact shape that broke every real restore: ordinary careers carry
    # whole floats (total_miles, reputation), which the old canonical form
    # rendered as "29571.0" while the server had signed "29571".
    profile = Profile(name="Road Star", money=77_000.0)
    reply = make_cloud_reply(profile.to_dict())
    payload = download_save(IDENTITY, save_name="Road Star", transport=FakeTransport(reply=reply))
    assert payload is not None
    assert payload["profile"]["money"] == 77_000.0


def test_server_absolution_clears_the_modified_mark_on_restore():
    """A career marked only because it moved computers gets released.

    The server grants this on a revision it signed and fully validated, so
    honest machine-movers stop carrying the mark forever. A profile that
    really was edited fails validation and never gets the signal.
    """
    marked = Profile(name="Road Star", money=77_000.0)
    marked.integrity_modified = True
    marked.integrity_notice_pending = True
    reply = make_cloud_reply(marked.to_dict(), revision=4)
    reply["clearIntegrityFlag"] = True
    payload = download_save(IDENTITY, save_name="Road Star", transport=FakeTransport(reply=reply))

    path = restore_to_disk(payload, SyncState())
    restored = Profile.load(path)

    assert restored.integrity_modified is False
    assert restored.integrity_notice_pending is False
    assert restored.money == 77_000.0


def test_a_restore_without_absolution_leaves_the_mark_alone():
    """Absence of the signal is not permission to clear the mark."""
    marked = Profile(name="Road Star", money=77_000.0)
    marked.integrity_modified = True
    reply = make_cloud_reply(marked.to_dict(), revision=4)
    payload = download_save(IDENTITY, save_name="Road Star", transport=FakeTransport(reply=reply))

    path = restore_to_disk(payload, SyncState())

    assert Profile.load(path).integrity_modified is True


# -- deleting a cloud slot -------------------------------------------------------


def test_delete_save_issues_a_delete_for_the_named_slot():
    transport = FakeTransport(reply={"ok": True, "deletedRevisions": 3})

    assert delete_save(IDENTITY, save_name="Road Star", transport=transport) is True

    url, payload, headers = transport.requests[0]
    assert url == (
        f"{base_url()}/api/freight-fate/saves?driverId={IDENTITY.driver_id}&saveName=Road%20Star"
    )
    assert payload is None
    assert headers["Authorization"] == f"Bearer {IDENTITY.driver_token}"


def test_delete_save_network_trouble_is_false():
    assert (
        delete_save(
            IDENTITY, save_name="Road Star", transport=FakeTransport(error=OSError("no route"))
        )
        is False
    )


def test_delete_save_refused_credentials_raise_cloud_auth_error():
    with pytest.raises(CloudAuthError):
        delete_save(IDENTITY, save_name="Road Star", transport=FakeTransport(error=auth_error(401)))


def test_forget_drops_the_slot_and_its_conflict():
    sync_state = SyncState()
    sync_state.record_synced("Road Star", 3, "hash")
    sync_state.record_conflict("Road Star", {"latestRevision": 4})

    sync_state.forget("Road Star")

    assert sync_state.slots() == {}
    # Idempotent: forgetting an unknown slot is not an error.
    sync_state.forget("Road Star")


def test_delete_menu_flow_confirms_then_forgets_the_slot(monkeypatch):
    import time as time_module

    import pygame

    from freight_fate import cloud_saves as cloud_saves_module
    from freight_fate.app import App
    from freight_fate.states.cloud_save_states import CloudSlotState

    IDENTITY.save()
    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        app.cloud.sync_state.record_synced("Road Star", 3, "hash")
        entry = {
            "saveName": "Road Star",
            "revision": 3,
            "createdAt": 1_700_000_000_000,
            "summary": "Rig Hauler, level 9",
        }
        slot = CloudSlotState(app.ctx, "Road Star", [entry])
        app.push_state(slot)
        while not slot.items[slot.index].text.startswith("Delete"):
            slot.handle_event(key_event(pygame.K_DOWN))
        slot.handle_event(key_event(pygame.K_RETURN))

        confirm = app.state
        assert confirm.title == "Delete the cloud backups?"
        # Safe default first: "No" is the focused item.
        assert confirm.items[0].text == "No, keep the cloud backups"
        assert any("cannot be brought back" in t for t in spoken)

        calls = {}

        def fake_delete(identity, *, save_name, transport=None):
            calls["save_name"] = save_name
            return True

        monkeypatch.setattr(cloud_saves_module, "delete_save", fake_delete)
        confirm.handle_event(key_event(pygame.K_DOWN))
        confirm.handle_event(key_event(pygame.K_RETURN))

        deadline = time_module.time() + 5.0
        while slot._outcome is None and time_module.time() < deadline:
            time_module.sleep(0.01)
        slot.update(0.0)

        assert calls["save_name"] == "Road Star"
        assert app.cloud.sync_state.slots() == {}
        assert slot.revisions == []
        assert any("removed from your orinks.net account" in t for t in spoken)
        # The slot menu no longer offers a delete for backups that are gone.
        assert not any(item.text.startswith("Delete") for item in slot.items)
    finally:
        app.shutdown()


@pytest.mark.parametrize(
    ("upload_result", "expected_fragments"),
    [
        (
            {"ok": False, "reason": "error"},
            ["check your connection"],
        ),
        (
            {"ok": False, "reason": "http_401"},
            ["no longer accepts this computer's sign-in"],
        ),
        (
            # Arithmetic cross-check refusal: named career, flagged for
            # review, and the owner-required appeal sentence (a real career
            # was false-flagged by this exact wording on 2026-08-14).
            {"ok": False, "reason": "impossible_money"},
            ["road star", "flagged it for review", "tester document"],
        ),
        (
            # Schema/version refusal: named career, blames a build
            # mismatch, never "flagged".
            {"ok": False, "reason": "invalid_schema"},
            ["road star", "build mismatch", "not something you did"],
        ),
        (
            # A rejected code with no specific family: named career, the
            # generic wording, still not "check your connection".
            {"ok": False, "reason": "invalid_achievement"},
            ["road star", "backup not accepted"],
        ),
    ],
    ids=["network", "auth", "rejected_arithmetic", "rejected_schema", "rejected_unknown"],
)
def test_keep_mine_retry_speaks_the_real_cause(monkeypatch, upload_result, expected_fragments):
    """Jessie's report, 2026-08-14: the server refused an upload with
    invalid_achievement, but the game blamed the connection. The "Keep this
    computer's save and back it up" retry must now speak the real family --
    network, auth, or a server rejection -- not one line for all three.
    Shane's report, same day: for a server rejection specifically, it must
    also name the career and split the story by reason code, the same as
    the background auto-backup queue does."""
    import time as time_module

    from freight_fate import cloud_saves as cloud_saves_module
    from freight_fate.app import App
    from freight_fate.states.cloud_save_states import CloudSlotState

    IDENTITY.save()
    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        Profile(name="Road Star").save()
        monkeypatch.setattr(cloud_saves_module, "upload_save", lambda *a, **k: dict(upload_result))

        slot = CloudSlotState(app.ctx, "Road Star", [])
        app.push_state(slot)
        slot.start_keep_mine()

        deadline = time_module.time() + 5.0
        while slot._outcome is None and time_module.time() < deadline:
            time_module.sleep(0.01)
        slot.update(0.0)

        joined = " ".join(spoken).lower()
        for fragment in expected_fragments:
            assert fragment in joined, spoken
        # The message never claims a network problem for a server
        # rejection, and never claims a server rejection for an actual
        # network problem.
        if upload_result["reason"] not in ("error", "http_401"):
            assert not any(
                "check your connection" in t.lower() and "backup not accepted" not in t.lower()
                for t in spoken
            )
        # The raw reason code is logged for review; it is never spoken.
        if upload_result["reason"] not in ("error", "http_401"):
            assert upload_result["reason"] not in joined
    finally:
        app.shutdown()


def test_backup_menu_says_off_and_offers_the_opt_in(monkeypatch):
    import pygame

    from freight_fate import cloud_saves as cloud_saves_module
    from freight_fate.app import App
    from freight_fate.states.cloud_save_states import CloudBackupState

    IDENTITY.save()
    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        monkeypatch.setattr(
            cloud_saves_module,
            "list_saves",
            lambda identity, **kw: {"saves": [], "publicSaveName": None},
        )
        state = CloudBackupState(app.ctx)
        app.push_state(state)
        assert state._fetched.wait(5.0)
        state.update(0.0)

        assert any(item.text.startswith("Status: Cloud backup is off") for item in state.items)
        while state.items[state.index].text != "Turn Cloud backup on":
            state.handle_event(key_event(pygame.K_DOWN))
        state.handle_event(key_event(pygame.K_RETURN))

        consent = app.state
        assert consent.title == "Turn Cloud backup on?"
        consent.handle_event(key_event(pygame.K_DOWN))
        consent.handle_event(key_event(pygame.K_RETURN))

        assert app.ctx.settings.cloud_saves is True
        assert app.cloud.enabled
        # Back on the rebuilt backup menu: the opt-in is gone and the status
        # line reports readiness instead of off.
        assert app.state is state
        assert state._fetched.wait(5.0)
        state.update(0.0)
        assert not any(item.text == "Turn Cloud backup on" for item in state.items)
        assert any(item.text == "Status: Cloud backup is ready." for item in state.items)
    finally:
        app.shutdown()


# -- the 1.9 cutover gate (careers from the 1.8 line do not restore here) --------


def make_legacy_profile_dict(name="Road Star", money=77_000.0) -> dict:
    """A cloud snapshot as a 1.8-line build would have uploaded it:
    save version 5, no created-on marker."""
    data = Profile(name=name, money=money).to_dict()
    data.pop("created_line", None)
    data["version"] = 5
    return data


def test_legacy_cloud_restore_refuses_without_touching_anything():
    from freight_fate.models.profile import LegacyCareerError

    local = Profile(name="Road Star", money=5.0)
    path = local.save()
    before = path.read_bytes()
    reply = make_cloud_reply(make_legacy_profile_dict())
    payload = download_save(IDENTITY, save_name="Road Star", transport=FakeTransport(reply=reply))
    assert payload is not None
    sync_state = SyncState()

    with pytest.raises(LegacyCareerError):
        restore_to_disk(payload, sync_state)

    # Refused before anything was written: the local save is byte-for-byte
    # intact, no fallback file appeared, and the sync state never moved.
    # (The cloud copy is only ever read here; deleting is a separate,
    # confirmed menu action.)
    assert path.read_bytes() == before
    assert not path.with_suffix(".ffsave.bak").exists()
    assert sync_state.slots() == {}


def test_current_line_backup_without_marker_still_restores():
    # A 1.9 tester's backup from before the created-on marker existed: the
    # save version vouches for it, exactly as the local load gate does.
    data = Profile(name="Road Star", money=77_000.0).to_dict()
    data.pop("created_line", None)
    reply = make_cloud_reply(data)
    payload = download_save(IDENTITY, save_name="Road Star", transport=FakeTransport(reply=reply))
    path = restore_to_disk(payload, SyncState())
    restored = Profile.load(path)
    assert restored.money == 77_000.0
    assert restored.created_line == "1.9"


def test_legacy_snapshot_is_labeled_and_refused_before_the_confirm_step():
    import pygame

    from freight_fate.app import App
    from freight_fate.states.cloud_save_states import LEGACY_BACKUP_NOTICE, CloudSlotState

    IDENTITY.save()
    app = App()
    spoken = []
    app.ctx.say = speech_stub(spoken)
    try:
        entry = {
            "saveName": "Old Timer",
            "revision": 3,
            "saveVersion": 5,
            "createdAt": 1_700_000_000_000,
            "summary": "Old Timer, level 50",
        }
        slot = CloudSlotState(app.ctx, "Old Timer", [entry])
        app.push_state(slot)
        restore_items = [item.text for item in slot.items if item.text.startswith("Restore")]
        assert any("from an earlier version of Freight Fate" in text for text in restore_items)

        while not slot.items[slot.index].text.startswith("Restore"):
            slot.handle_event(key_event(pygame.K_DOWN))
        slot.handle_event(key_event(pygame.K_RETURN))

        # No confirmation screen opened, nothing was downloaded or deleted;
        # the refusal is spoken kindly and the menu stays put.
        assert app.state is slot
        assert any(LEGACY_BACKUP_NOTICE in text for text in spoken)
        assert any("stays safe in your orinks.net account" in text for text in spoken)
    finally:
        app.shutdown()


# -- the manual backup attempt (Shane's report, 2026-08-14: hitting Save gave ----
# -- no sign a backup ran, so a silent one was indistinguishable from none) ------


def test_backup_now_skips_the_debounce():
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)

    token = service.backup_now(Profile(name="Road Star"))

    # No debounce wait: the attempt went out inside the call.
    assert len(transport.posts) == 1
    assert service.outcome_for("Road Star", token) == "accepted"
    assert service.sync_state.slot("Road Star")["revision"] == 1


def test_backup_now_bypasses_the_transient_retry_backoff():
    transport = FakeTransport(error=OSError("no network"))
    clock = Clock()
    service = make_service(transport, clock)
    service.queue_backup(Profile(name="Road Star"))
    drain(service, clock)
    assert len(transport.posts) == 1  # failed: the backoff is armed

    # A background pump sits the backoff out...
    service.pump()
    assert len(transport.posts) == 1

    # ...the manual attempt does not.
    transport.error = None
    token = service.backup_now(Profile(name="Road Star"))
    assert len(transport.posts) == 2
    assert service.outcome_for("Road Star", token) == "accepted"


def test_backup_now_reports_content_already_on_the_server():
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)
    profile = Profile(name="Road Star")
    service.queue_backup(profile)
    drain(service, clock)

    token = service.backup_now(profile)  # nothing changed since

    assert len(transport.posts) == 1  # the content-hash skip still holds
    assert service.outcome_for("Road Star", token) == "unchanged"


def test_backup_now_reports_a_rejection_with_its_reason():
    transport = FakeTransport(error=rejected_error("invalid_achievement"))
    service = make_service(transport, Clock())

    token = service.backup_now(Profile(name="Road Star"))

    assert service.outcome_for("Road Star", token) == "rejected:invalid_achievement"


def test_backup_now_reports_the_auth_family():
    service = make_service(FakeTransport(error=auth_error()), Clock())

    token = service.backup_now(Profile(name="Road Star"))

    assert service.outcome_for("Road Star", token) == "auth"


def test_backup_now_reports_network_trouble_and_keeps_retrying():
    transport = FakeTransport(error=OSError("no route"))
    clock = Clock()
    service = make_service(transport, clock)

    token = service.backup_now(Profile(name="Road Star"))

    assert service.outcome_for("Road Star", token) == "network"
    # The snapshot stays queued for the background retry cadence.
    transport.error = None
    clock.advance(RETRY_INTERVAL_S + 0.1)
    service.pump()
    assert service.sync_state.slot("Road Star")["revision"] == 1


def test_backup_now_records_a_fresh_conflict():
    transport = FakeTransport(error=conflict_error(latest_revision=5))
    service = make_service(transport, Clock())

    token = service.backup_now(Profile(name="Road Star"))

    assert service.outcome_for("Road Star", token) == "conflict"
    assert "Road Star" in service.conflicts()


def test_backup_now_respects_a_recorded_conflict():
    # The conflict guard is unchanged: a live cloud copy still blocks the
    # upload -- but the manual attempt reports it instead of staying silent.
    transport = RoutedTransport(
        list_reply={"ok": True, "saves": [{"saveName": "Road Star", "revision": 40}]}
    )
    service = make_service(transport, Clock())
    service.sync_state.record_conflict("Road Star", {"latestRevision": 40})

    token = service.backup_now(Profile(name="Road Star"))

    assert transport.posts == []
    assert service.outcome_for("Road Star", token) == "conflict"


def test_backup_now_disabled_returns_no_token():
    service = make_service(FakeTransport(), Clock(), enabled=False)
    assert service.backup_now(Profile(name="Road Star")) is None


def test_outcome_for_ignores_results_from_an_earlier_attempt():
    service = make_service(FakeTransport(), Clock())
    token = service.backup_now(Profile(name="Road Star"))
    assert service.outcome_for("Road Star", token) == "accepted"
    # A later attempt's poller never hears the old result.
    assert service.outcome_for("Road Star", token + 1) is None


def test_an_upload_in_flight_when_save_is_pressed_keeps_its_own_verdict():
    """Uploads run outside the lock, so a background upload (a delivery
    autosave, a retry pass) can already be on the wire when the player
    presses Save game. Its terminal result must stay stamped with its own
    queued-under token: the wrong save's verdict must never be spoken as
    this save's outcome, and the manual attempt's own result must never be
    silenced or overwritten by the older upload finishing late."""
    clock = Clock()
    service = None  # assigned below; the transport closes over it
    tokens: list[int] = []
    newer = Profile(name="Road Star")
    newer.money += 777.0  # the manual snapshot differs from the autosave's

    class MidFlightSave(FakeTransport):
        """The first request is the background upload already in flight;
        while it is on the wire the player presses Save game (run to
        completion re-entrantly, the synchronous stand-in for the worker
        thread), and then the old upload comes back refused."""

        def __call__(self, url, payload, headers):
            self.requests.append((url, payload, headers))
            if len(self.requests) == 1:
                tokens.append(service.backup_now(newer))
                raise rejected_error("invalid_achievement")
            self.revision += 1
            return {"ok": True, "revision": self.revision}

    transport = MidFlightSave()
    service = make_service(transport, clock)
    service.queue_backup(Profile(name="Road Star"))
    drain(service, clock)

    assert len(transport.posts) == 2  # the autosave, then the manual attempt
    # The manual attempt's watch hears its own accepted result -- not the
    # older upload's rejection, which finished after it and carries the
    # background token no watch ever matches.
    assert service.outcome_for("Road Star", tokens[0]) == "accepted"


# -- background refusals speak everywhere (owner decision, 2026-08-15: automatic --
# -- saves upload silently, so a blind player never heard a career stop backing up)


def test_background_rejection_announces_exactly_once_across_retries():
    transport = FakeTransport(error=rejected_error("impossible_money"))
    clock = Clock()
    service = make_service(transport, clock)
    profile = Profile(name="Road Star")

    service.queue_backup(profile)
    drain(service, clock)

    lines = service.take_announcements()
    assert len(lines) == 1
    assert lines[0].startswith("Road Star: backup not accepted.")
    assert "flagged it for review" in lines[0]
    # The raw reason code stays log-only, exactly as in the status line.
    assert "impossible_money" not in lines[0]

    # Every later save refused for the same cause stays silent.
    for _ in range(3):
        profile.money += 1.0
        service.queue_backup(profile)
        drain(service, clock)
    assert service.take_announcements() == []


def test_background_refusal_speaks_again_when_the_cause_changes():
    transport = FakeTransport(error=rejected_error("invalid_schema"))
    clock = Clock()
    service = make_service(transport, clock)
    profile = Profile(name="Road Star")

    service.queue_backup(profile)
    drain(service, clock)
    assert "build mismatch" in service.take_announcements()[0]

    transport.error = rejected_error("impossible_money")
    profile.money += 1.0
    service.queue_backup(profile)
    drain(service, clock)

    lines = service.take_announcements()
    assert len(lines) == 1
    assert "flagged it for review" in lines[0]


def test_success_after_a_spoken_refusal_announces_recovery_and_rearms():
    transport = FakeTransport(error=rejected_error("impossible_money"))
    clock = Clock()
    service = make_service(transport, clock)
    profile = Profile(name="Road Star")

    service.queue_backup(profile)
    drain(service, clock)
    assert len(service.take_announcements()) == 1

    transport.error = None
    profile.money += 1.0
    service.queue_backup(profile)
    drain(service, clock)
    assert service.take_announcements() == ["Road Star is backed up again."]

    # A clean backup with nothing to recover from stays silent...
    profile.money += 1.0
    service.queue_backup(profile)
    drain(service, clock)
    assert service.take_announcements() == []

    # ...and the dedupe is re-armed: the same refusal speaks once more.
    transport.error = rejected_error("impossible_money")
    profile.money += 1.0
    service.queue_backup(profile)
    drain(service, clock)
    assert len(service.take_announcements()) == 1


def test_background_auth_refusal_speaks_the_reconnect_line_once():
    transport = FakeTransport(error=auth_error(401))
    clock = Clock()
    service = make_service(transport, clock)
    profile = Profile(name="Road Star")

    service.queue_backup(profile)
    drain(service, clock)
    assert service.take_announcements() == [AUTH_PAUSED_STATUS]

    profile.money += 1.0
    service.queue_backup(profile)
    drain(service, clock)
    assert service.take_announcements() == []


def test_background_conflict_announces_the_choice_line_once():
    transport = FakeTransport(error=conflict_error(latest_revision=5))
    clock = Clock()
    service = make_service(transport, clock)
    profile = Profile(name="Road Star")

    service.queue_backup(profile)
    drain(service, clock)
    assert service.take_announcements() == [conflict_status("Road Star")]

    # Later saves blocked by the same recorded conflict stay silent.
    profile.money += 1.0
    service.queue_backup(profile)
    drain(service, clock)
    assert service.take_announcements() == []


def test_background_network_trouble_stays_a_silent_retry():
    # Transient failures retry on their own; the manual save path already
    # voices them on demand, so the global channel says nothing.
    transport = FakeTransport(error=OSError("no route"))
    clock = Clock()
    service = make_service(transport, clock)

    service.queue_backup(Profile(name="Road Star"))
    drain(service, clock)

    assert service.take_announcements() == []


def test_manual_refusal_never_reaches_the_global_channel():
    # The terminal's Save game item polls and speaks its own outcome
    # (states/city.py); announcing it here too would say the refusal twice.
    transport = FakeTransport(error=rejected_error("invalid_achievement"))
    service = make_service(transport, Clock())

    token = service.backup_now(Profile(name="Road Star"))

    assert service.outcome_for("Road Star", token) == "rejected:invalid_achievement"
    assert service.take_announcements() == []


def test_manual_success_after_a_spoken_refusal_recovers_silently_and_rearms():
    transport = FakeTransport(error=rejected_error("impossible_money"))
    clock = Clock()
    service = make_service(transport, clock)
    profile = Profile(name="Road Star")

    service.queue_backup(profile)
    drain(service, clock)
    assert len(service.take_announcements()) == 1

    # The player hits Save game and the upload goes through: the city
    # watch speaks "Backed up to the cloud." on its own, so the global
    # channel must not add a second line for the same event.
    transport.error = None
    profile.money += 1.0
    token = service.backup_now(profile)
    assert service.outcome_for("Road Star", token) == "accepted"
    assert service.take_announcements() == []

    # The dedupe still re-armed: the same refusal speaks once more.
    transport.error = rejected_error("impossible_money")
    profile.money += 1.0
    service.queue_backup(profile)
    drain(service, clock)
    assert len(service.take_announcements()) == 1


def test_manual_refusal_seeds_the_dedupe_for_the_background_channel():
    # A conflict spoken by the manual Save game watch (states/city.py) is
    # already in the player's ear; the next automatic save blocked by the
    # same standing conflict must not repeat the identical sentence.
    transport = FakeTransport(error=conflict_error(latest_revision=5))
    clock = Clock()
    service = make_service(transport, clock)
    profile = Profile(name="Road Star")

    token = service.backup_now(profile)
    assert service.outcome_for("Road Star", token) == "conflict"
    assert service.take_announcements() == []  # the menu watch owns this one

    profile.money += 1.0
    service.queue_backup(profile)
    drain(service, clock)
    assert service.take_announcements() == []


def test_auth_announcement_is_one_per_outage_not_per_career():
    transport = FakeTransport(error=auth_error(401))
    clock = Clock()
    service = make_service(transport, clock)

    service.queue_backup(Profile(name="Road Star"))
    drain(service, clock)
    assert service.take_announcements() == [AUTH_PAUSED_STATUS]

    # The sign-in belongs to this computer, not to the career: loading
    # another career during the same outage must not repeat the line.
    service.queue_backup(Profile(name="Night Owl"))
    drain(service, clock)
    assert service.take_announcements() == []

    # A successful upload proves the sign-in works again -- silently:
    # neither career's slot spoke a refusal, so nothing recovers aloud.
    transport.error = None
    service.queue_backup(Profile(name="Night Owl"))
    drain(service, clock)
    assert service.take_announcements() == []

    # ...and a fresh outage after that speaks afresh.
    transport.error = auth_error(401)
    service.queue_backup(Profile(name="Road Star"))
    drain(service, clock)
    assert service.take_announcements() == [AUTH_PAUSED_STATUS]


def test_take_announcements_drains_the_queue():
    transport = FakeTransport(error=rejected_error("impossible_money"))
    clock = Clock()
    service = make_service(transport, clock)
    service.queue_backup(Profile(name="Road Star"))
    drain(service, clock)

    assert len(service.take_announcements()) == 1
    assert service.take_announcements() == []


def test_app_loop_speaks_queued_background_refusals(monkeypatch):
    """The worker thread never speaks; the app's main loop drains
    take_announcements and delivers on the normal announcement channel --
    the same polled pattern as the controller-disconnect notice."""
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    clock = Clock()
    app.cloud = make_service(FakeTransport(error=rejected_error("impossible_money")), clock)
    app.cloud.queue_backup(Profile(name="Road Star"))
    drain(app.cloud, clock)

    app.run(max_frames=3)  # run() shuts the app down on its way out

    refusals = [t for t in spoken if t.startswith("Road Star: backup not accepted.")]
    assert len(refusals) == 1


# -- the Save game item at the terminal speaks the backup result ------------------


def make_terminal_menu(app, service):
    """The terminal menu over an injected cloud service. The state is not
    entered: enter() starts music and warms live weather, and _save needs
    neither."""
    from freight_fate.states.city import CityMenuState

    app.cloud = service
    app.ctx.profile = Profile(name="Road Star", current_city="Chicago")
    return CityMenuState(app.ctx)


def test_terminal_save_speaks_the_accepted_backup(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    try:
        menu = make_terminal_menu(app, make_service(FakeTransport(), Clock()))

        menu._save()
        assert spoken[-1] == "Game saved. Backing up."

        menu.update(0.0)
        assert spoken[-1] == "Backed up to the cloud."
    finally:
        app.shutdown()


def test_terminal_save_says_when_the_latest_save_is_already_backed_up(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    try:
        menu = make_terminal_menu(app, make_service(FakeTransport(), Clock()))
        menu._save()
        menu.update(0.0)

        spoken.clear()
        menu._save()
        menu.update(0.0)

        # The line has to answer the worry a driver actually has here. After
        # fuelling and buying tires they KNOW the career changed, so a bare
        # "already backed up" reads as the game refusing to send it (Shane,
        # 2026-08-15). Naming what is true -- the cloud copy matches this
        # computer -- is the part that settles it.
        assert spoken == [
            "Game saved. Backing up.",
            "Already backed up. The cloud copy matches this computer's save.",
        ]
    finally:
        app.shutdown()


def test_terminal_save_speaks_a_rejection_with_the_career_named(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    try:
        service = make_service(FakeTransport(error=rejected_error("impossible_money")), Clock())
        menu = make_terminal_menu(app, service)

        menu._save()
        menu.update(0.0)

        assert spoken[-2] == "Game saved. Backing up."
        assert spoken[-1].startswith("Road Star: backup not accepted.")
        assert "flagged it for review" in spoken[-1]
        # The raw reason code stays log-only, exactly as in the background queue.
        assert "impossible_money" not in " ".join(spoken)
    finally:
        app.shutdown()


def test_terminal_save_with_cloud_off_mentions_it_only_when_an_account_exists(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    try:
        # An account is configured but backup is off: the save says so.
        menu = make_terminal_menu(app, make_service(FakeTransport(), Clock(), enabled=False))
        menu._save()
        assert spoken == [
            "Game saved.",
            "Cloud backup is off. Saves on this computer are not backed up.",
        ]

        # No account at all: saving stays local and quiet, exactly as before.
        app.cloud = make_service(FakeTransport(), Clock(), enabled=False, identity=None)
        spoken.clear()
        menu._save()
        assert spoken == ["Game saved."]
    finally:
        app.shutdown()


def test_terminal_save_hands_a_silent_attempt_back_to_the_background(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import BACKUP_RESULT_WAIT_S

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    try:
        # A threaded service whose worker is never started: the outcome can
        # never land inside the wait, deterministically.
        service = CloudSaves(
            enabled=True,
            identity=IDENTITY,
            transport=FakeTransport(error=OSError("no route")),
            threaded=True,
        )
        menu = make_terminal_menu(app, service)

        menu._save()
        assert spoken[-1] == "Game saved. Backing up."

        menu.update(BACKUP_RESULT_WAIT_S / 2)
        assert spoken[-1] == "Game saved. Backing up."

        menu.update(BACKUP_RESULT_WAIT_S)
        assert spoken[-1] == "The backup will keep retrying in the background."

        # Exactly one result line: nothing else ever arrives for this save.
        menu.update(60.0)
        assert spoken.count("The backup will keep retrying in the background.") == 1
    finally:
        app.shutdown()


def test_sandbox_save_never_reaches_the_cloud(monkeypatch):
    """A driving-school or forced-playtest sandbox save never reaches disk
    (save_profile's own guard), so it must never reach the cloud either --
    the throwaway profile shares the real career's slot name -- and must
    not promise a backup out loud."""
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    try:
        transport = FakeTransport()
        menu = make_terminal_menu(app, make_service(transport, Clock()))
        monkeypatch.setattr(app.ctx, "playtest_sandbox", True, raising=False)

        menu._save()
        menu.update(0.0)

        assert transport.requests == []
        assert spoken == ["Game saved."]
    finally:
        app.shutdown()


def test_leaving_the_terminal_drops_the_pending_backup_announcement(monkeypatch):
    from freight_fate.app import App

    app = App()
    spoken = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    try:
        service = CloudSaves(
            enabled=True,
            identity=IDENTITY,
            transport=FakeTransport(),
            threaded=True,  # worker never started: the outcome stays pending
        )
        menu = make_terminal_menu(app, service)
        menu._save()

        menu.exit()
        spoken.clear()
        menu.update(60.0)

        assert spoken == []
    finally:
        app.shutdown()
