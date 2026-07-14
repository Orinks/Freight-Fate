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
import urllib.error

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from freight_fate import cloud_save_integrity
from freight_fate.cloud_save_integrity import CloudSaveIntegrityError, canonical_profile
from freight_fate.cloud_saves import (
    DEBOUNCE_S,
    RETRY_INTERVAL_S,
    CloudAuthError,
    CloudSaves,
    SyncState,
    backup_summary,
    cloud_content,
    download_save,
    list_saves,
    profile_dict_from_content,
    restore_to_disk,
    save_slot_name,
    upload_save,
)
from freight_fate.models import profile as profile_module
from freight_fate.models.profile import SIGNATURE_FIELD, Profile
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
    assert SIGNATURE_FIELD in json.loads(path.read_text(encoding="utf-8"))
    backup = path.with_suffix(".json.bak")
    assert backup.exists()
    assert json.loads(backup.read_text(encoding="utf-8"))["money"] == 5.0
    # The fallback file must not appear in the careers list.
    assert path.with_suffix(".json.bak") not in Profile.list_saves()

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
    app.ctx.say = lambda text, interrupt=True: spoken.append(text)
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
    app.ctx.say = lambda text, interrupt=True: spoken.append(text)
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

    assert "Reconnect under Settings, Online" in service.status
    # Not transient: the snapshot is dropped instead of retried forever.
    drain(service, clock)
    assert len(transport.posts) == 1


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
