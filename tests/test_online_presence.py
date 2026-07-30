"""Tests for the opt-in orinks.net drivers-board service.

These cover the behaviour that must hold regardless of whether the site is
even reachable: the disabled/off-by-default path, heartbeat and change
scheduling, the off-duty grace and sign-off, credential storage, and the
pasted-credential verification. A fake transport and an injected clock keep
every test deterministic and free of real sockets.
"""

from __future__ import annotations

import json
import os
import stat
import urllib.error

import pytest
from conftest import FakeKeyring

from freight_fate import online_presence
from freight_fate.discord_presence import PresenceState
from freight_fate.online_presence import (
    HEARTBEAT_INTERVAL_S,
    IDLE_SIGNOFF_S,
    MIN_CHANGE_INTERVAL_S,
    OFF_DUTY_GRACE_S,
    OnlineIdentity,
    OnlinePresence,
    base_url,
    fetch_board,
    set_profile_sharing,
    verify_identity,
)
from freight_fate.settings import Settings


class FakeTransport:
    """Records every request; replies from a queue or raises."""

    def __init__(self, *, reply: dict | None = None, error: Exception | None = None) -> None:
        self.reply = {"ok": True} if reply is None else reply
        self.error = error
        self.requests: list[tuple[str, dict | None, dict[str, str]]] = []

    def __call__(self, url: str, payload: dict | None, headers: dict[str, str]) -> dict:
        self.requests.append((url, payload, headers))
        if self.error is not None:
            raise self.error
        return self.reply

    @property
    def posts(self) -> list[dict]:
        return [p for _, p, _ in self.requests if p is not None]


class Clock:
    """A manually advanced monotonic clock."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


IDENTITY = OnlineIdentity(driver_id="driver-testtest", driver_token="t" * 48)

DRIVING = PresenceState("Driving: Chicago to Dallas", "steel coils, 45% there")
RESTING = PresenceState("Resting at a stop", "steel coils, 45% there")


def make_service(transport, clock, *, enabled=True, identity=IDENTITY):
    """A synchronous (non-threaded) service wired to a fake transport."""
    return OnlinePresence(
        enabled=enabled,
        identity=identity,
        clock=clock,
        transport=transport,
        threaded=False,
    )


# -- disabled and unconfigured paths ------------------------------------------


def test_profile_sharing_defaults_off_without_setup():
    assert Settings().online_presence is False
    assert OnlineIdentity.load() is None
    service = OnlinePresence(enabled=Settings().online_presence, identity=OnlineIdentity.load())
    assert not service.enabled


def test_profile_sharing_posts_one_authoritative_boolean():
    transport = FakeTransport(reply={"ok": True, "enabled": False})
    assert set_profile_sharing(IDENTITY, False, transport=transport) == "ok"
    url, payload, headers = transport.requests[0]
    assert url.endswith("/api/freight-fate/profile-sharing")
    assert payload == {"driverId": IDENTITY.driver_id, "enabled": False}
    assert headers["Authorization"].startswith("Bearer ")


def test_disabled_never_posts():
    transport = FakeTransport()
    service = make_service(transport, Clock(), enabled=False)
    service.start()
    service.update(DRIVING)
    service.shutdown()
    assert transport.requests == []


def test_enabled_without_identity_stays_dormant():
    transport = FakeTransport()
    service = make_service(transport, Clock(), identity=None)
    assert not service.enabled
    service.start()
    service.update(DRIVING)
    service.shutdown()
    assert transport.requests == []


# -- heartbeat scheduling ------------------------------------------------------


def test_first_update_posts_immediately_with_credentials():
    transport = FakeTransport()
    service = make_service(transport, Clock())
    service.start()
    service.update(DRIVING)

    url, payload, headers = transport.requests[0]
    assert url == f"{base_url()}/api/freight-fate/presence"
    assert payload == {
        "driverId": IDENTITY.driver_id,
        "activity": DRIVING.activity,
        "detail": DRIVING.detail,
    }
    assert headers == {"Authorization": f"Bearer {IDENTITY.driver_token}"}


def test_identical_state_reposts_only_on_the_heartbeat():
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)
    service.start()
    service.update(DRIVING)
    assert len(transport.posts) == 1

    # The same snapshot again, before the heartbeat: nothing new goes out.
    clock.advance(HEARTBEAT_INTERVAL_S / 2)
    service._pump()
    assert len(transport.posts) == 1

    # Past the heartbeat the same snapshot is resent to keep the TTL alive.
    clock.advance(HEARTBEAT_INTERVAL_S / 2)
    service._pump()
    assert len(transport.posts) == 2
    assert transport.posts[1]["activity"] == DRIVING.activity


def test_changes_are_throttled_then_flushed():
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)
    service.start()
    service.update(DRIVING)

    # A change right away is throttled...
    clock.advance(MIN_CHANGE_INTERVAL_S / 2)
    service.update(RESTING)
    assert len(transport.posts) == 1

    # ...and flushes once the change window has passed.
    clock.advance(MIN_CHANGE_INTERVAL_S / 2)
    service._pump()
    assert len(transport.posts) == 2
    assert transport.posts[1]["activity"] == RESTING.activity


def test_failed_post_is_retried_on_the_heartbeat_schedule():
    transport = FakeTransport(error=OSError("offline"))
    clock = Clock()
    service = make_service(transport, clock)
    service.start()
    service.update(DRIVING)
    assert len(transport.requests) == 1

    # Not hammered while the site is down...
    clock.advance(1.0)
    service._pump()
    assert len(transport.requests) == 1

    # ...but tried again a heartbeat later, and recovery works.
    transport.error = None
    clock.advance(HEARTBEAT_INTERVAL_S)
    service._pump()
    assert len(transport.requests) == 2


# -- going off duty -------------------------------------------------------------


def test_off_duty_signs_off_after_the_grace():
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)
    service.start()
    service.update(DRIVING)

    service.update(None)
    assert len(transport.posts) == 1  # grace running; still on the board

    clock.advance(OFF_DUTY_GRACE_S + 1)
    service._pump()
    assert transport.posts[-1] == {
        "driverId": IDENTITY.driver_id,
        "activity": "",
        "detail": "",
    }


def test_brief_menu_detour_does_not_bounce_the_driver():
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)
    service.start()
    service.update(DRIVING)

    # A two-second status-screen visit reports None, then driving again.
    service.update(None)
    clock.advance(2.0)
    service.update(DRIVING)
    clock.advance(OFF_DUTY_GRACE_S)
    service._pump()

    assert all(post["activity"] for post in transport.posts)  # no sign-off sent


def test_off_duty_without_ever_posting_sends_nothing():
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)
    service.start()
    service.update(None)
    clock.advance(OFF_DUTY_GRACE_S + 1)
    service._pump()
    assert transport.requests == []


def test_idle_snapshot_signs_off_and_goes_quiet():
    # A truck parked with the game left running (not paused) reports the
    # identical snapshot forever; after the idle window the service must
    # leave the board and stop spending heartbeats on it.
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)
    service.start()
    service.update(DRIVING)
    assert len(transport.posts) == 1

    # Half the window in: still a live driver, heartbeats keep the TTL alive.
    clock.advance(IDLE_SIGNOFF_S / 2)
    service._pump()
    assert transport.posts[-1]["activity"] == DRIVING.activity

    # Window crossed: one sign-off, then silence on later heartbeat slots.
    clock.advance(IDLE_SIGNOFF_S / 2)
    service._pump()
    assert transport.posts[-1]["activity"] == ""
    sent = len(transport.posts)
    clock.advance(HEARTBEAT_INTERVAL_S * 2)
    service._pump()
    assert len(transport.posts) == sent


def test_snapshot_change_relists_an_idle_driver():
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)
    service.start()
    service.update(DRIVING)
    clock.advance(IDLE_SIGNOFF_S)
    service._pump()
    assert transport.posts[-1]["activity"] == ""

    # Rolling again changes the snapshot, which restarts the idle clock and
    # puts the driver back on the board within the change throttle.
    service.update(RESTING)
    clock.advance(MIN_CHANGE_INTERVAL_S)
    service._pump()
    assert transport.posts[-1]["activity"] == RESTING.activity

    # And the driver stays live from there: the next heartbeat still goes out.
    clock.advance(HEARTBEAT_INTERVAL_S)
    service._pump()
    assert transport.posts[-1]["activity"] == RESTING.activity


def test_shutdown_signs_off():
    transport = FakeTransport()
    service = make_service(transport, Clock())
    service.start()
    service.update(DRIVING)
    service.shutdown()
    assert transport.posts[-1]["activity"] == ""


def test_disable_signs_off_and_reenable_resumes():
    transport = FakeTransport()
    clock = Clock()
    service = make_service(transport, clock)
    service.start()
    service.update(DRIVING)

    service.set_enabled(False)
    assert transport.posts[-1]["activity"] == ""
    assert not service.enabled

    service.set_enabled(True)
    service.update(DRIVING)
    assert transport.posts[-1]["activity"] == DRIVING.activity


# -- identity storage ------------------------------------------------------------


def test_identity_round_trips_through_disk():
    identity = OnlineIdentity(driver_id="road-star-abcd1234", driver_token="s" * 68)
    identity.save()
    loaded = OnlineIdentity.load()
    assert loaded == identity


def test_saved_identity_keeps_the_token_out_of_the_json_file():
    """The public Driver ID stays on disk; the secret never does.

    Contributed by trodick in https://github.com/Orinks/Freight-Fate/pull/133.
    """
    identity = OnlineIdentity(driver_id="road-star-abcd1234", driver_token="s" * 68)
    identity.save()

    payload = OnlineIdentity.path().read_text(encoding="utf-8")
    assert '"driver_id"' in payload
    assert "driver_token" not in payload
    assert identity.driver_token not in payload
    assert not OnlineIdentity.token_path().exists()


def _next_session() -> None:
    """Forget the process-lifetime token cache, as restarting the game would."""
    OnlineIdentity._token_cache.clear()


def test_identity_falls_back_to_an_owner_only_file_without_a_secret_store(monkeypatch):
    monkeypatch.setattr(online_presence, "keyring", None)
    identity = OnlineIdentity(driver_id="road-star-abcd1234", driver_token="s" * 68)
    if os.name == "nt":
        with pytest.raises(OSError, match="disabled on Windows"):
            identity.save()
        assert not OnlineIdentity.token_path().exists()
        assert not OnlineIdentity.path().exists()
        return

    identity.save()

    identity_file = OnlineIdentity.path()
    assert json.loads(identity_file.read_text(encoding="utf-8")) == {
        "driver_id": identity.driver_id,
        "driver_token": identity.driver_token,
    }
    assert not OnlineIdentity.token_path().exists()
    _next_session()
    assert OnlineIdentity.load() == identity
    assert stat.S_IMODE(identity_file.stat().st_mode) == 0o600


def test_fallback_ignores_a_stale_permissive_temp_file(monkeypatch):
    if os.name == "nt":
        pytest.skip("Windows never writes a plaintext fallback identity")

    monkeypatch.setattr(online_presence, "keyring", None)
    stale = OnlineIdentity.path().with_suffix(".json.tmp")
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("stale, non-secret data", encoding="utf-8")
    stale.chmod(0o644)

    identity = OnlineIdentity(driver_id="road-star-abcd1234", driver_token="s" * 68)
    identity.save()

    assert stale.read_text(encoding="utf-8") == "stale, non-secret data"
    assert stat.S_IMODE(OnlineIdentity.path().stat().st_mode) == 0o600


def test_failed_legacy_migration_keeps_the_original_token(monkeypatch):
    path = OnlineIdentity.path()
    path.parent.mkdir(parents=True, exist_ok=True)
    token = "s" * 68
    path.write_text(
        json.dumps({"driver_id": "road-star-abcd1234", "driver_token": token}),
        encoding="utf-8",
    )
    monkeypatch.setattr(OnlineIdentity, "_store_token", lambda *_args: False)
    monkeypatch.setattr(
        OnlineIdentity,
        "_write_identity_file",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("storage unavailable")),
    )

    assert OnlineIdentity.load() == OnlineIdentity(
        driver_id="road-star-abcd1234", driver_token=token
    )
    _next_session()

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["driver_token"] == token
    assert OnlineIdentity.load() == OnlineIdentity(
        driver_id="road-star-abcd1234", driver_token=token
    )


def test_the_secret_store_is_read_once_and_not_once_per_menu_frame(monkeypatch):
    reads = []
    store = FakeKeyring()
    get_password = store.get_password

    def counted(service, username):
        reads.append(username)
        return get_password(service, username)

    monkeypatch.setattr(store, "get_password", counted)
    monkeypatch.setattr(online_presence, "keyring", store)

    identity = OnlineIdentity(driver_id="road-star-abcd1234", driver_token="s" * 68)
    identity.save()
    _next_session()

    assert [OnlineIdentity.load() for _ in range(20)] == [identity] * 20
    assert len(reads) == 1


def test_a_secret_store_that_refuses_falls_back_instead_of_failing(monkeypatch):
    """The real headless-Linux shape: keyring imports, every call raises."""

    class RefusingKeyring:
        def set_password(self, service, username, password):
            raise RuntimeError("no recommended backend was available")

        def get_password(self, service, username):
            raise RuntimeError("no recommended backend was available")

    monkeypatch.setattr(online_presence, "keyring", RefusingKeyring())
    identity = OnlineIdentity(driver_id="road-star-abcd1234", driver_token="s" * 68)
    if os.name == "nt":
        with pytest.raises(OSError, match="disabled on Windows"):
            identity.save()
        assert not OnlineIdentity.token_path().exists()
        assert not OnlineIdentity.path().exists()
        return

    identity.save()

    payload = json.loads(OnlineIdentity.path().read_text(encoding="utf-8"))
    assert payload["driver_token"] == identity.driver_token
    assert not OnlineIdentity.token_path().exists()
    _next_session()
    assert OnlineIdentity.load() == identity


def test_a_token_written_by_an_older_build_moves_into_the_secret_store():
    path = OnlineIdentity.path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"driver_id": "road-star-abcd1234", "driver_token": "s" * 68}),
        encoding="utf-8",
    )

    loaded = OnlineIdentity.load()
    assert loaded == OnlineIdentity(driver_id="road-star-abcd1234", driver_token="s" * 68)
    # Loading is what migrates: nobody has to re-paste their credentials.
    assert "driver_token" not in path.read_text(encoding="utf-8")
    assert not OnlineIdentity.token_path().exists()
    assert OnlineIdentity.load() == loaded


def test_a_fallback_token_file_is_cleared_once_a_secret_store_appears(monkeypatch):
    if os.name == "nt":
        pytest.skip("Windows never writes a plaintext fallback token")

    identity = OnlineIdentity(driver_id="road-star-abcd1234", driver_token="s" * 68)
    monkeypatch.setattr(online_presence, "keyring", None)
    OnlineIdentity.path().write_text(
        json.dumps({"driver_id": identity.driver_id}),
        encoding="utf-8",
    )
    OnlineIdentity.token_path().write_text(identity.driver_token, encoding="utf-8")
    assert OnlineIdentity.token_path().exists()

    monkeypatch.setattr(online_presence, "keyring", FakeKeyring())
    _next_session()
    assert OnlineIdentity.load() == identity
    assert not OnlineIdentity.token_path().exists()
    assert OnlineIdentity.load() == identity


def test_failed_fallback_replacement_keeps_the_existing_identity(monkeypatch):
    if os.name == "nt":
        pytest.skip("Windows never writes a plaintext fallback identity")

    monkeypatch.setattr(online_presence, "keyring", None)
    original = OnlineIdentity(driver_id="road-star-original", driver_token="a" * 68)
    original.save()
    replacement = OnlineIdentity(driver_id="road-star-replaced", driver_token="b" * 68)
    monkeypatch.setattr(
        replacement,
        "_write_identity_file",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("metadata unavailable")),
    )

    with pytest.raises(OSError, match="metadata unavailable"):
        replacement.save()
    _next_session()

    assert OnlineIdentity.load() == original


# -- packaging guard --------------------------------------------------------------


def test_the_secret_store_report_passes_on_a_source_checkout():
    ok, detail = online_presence.secret_store_report()
    assert ok, detail
    assert detail


def test_the_secret_store_report_fails_when_the_backends_are_not_packaged(monkeypatch):
    """What a build that dropped keyring's entry points would look like.

    This is the whole value of the check: without it a packaged build would
    keep every driver token in the fallback file and say nothing.
    """
    from importlib import metadata

    monkeypatch.setattr(metadata, "entry_points", lambda **kwargs: [])
    ok, detail = online_presence.secret_store_report()
    assert not ok
    assert "not registered in this build" in detail


def test_the_secret_store_report_fails_without_keyring_at_all(monkeypatch):
    monkeypatch.setattr(online_presence, "keyring", None)
    ok, detail = online_presence.secret_store_report()
    assert not ok
    assert "not installed" in detail


def test_the_release_build_asks_for_keyrings_backends_and_metadata():
    """The packaging flags and the CI probe must not drift apart."""
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from tools.build_release import KEYRING_NUITKA_ARGS, build_nuitka_command

    assert KEYRING_NUITKA_ARGS == [
        "--include-package=keyring.backends",
        "--include-distribution-metadata=keyring",
    ]
    command = build_nuitka_command(root / "tools" / "_entry.py")
    for arg in KEYRING_NUITKA_ARGS:
        assert arg in command


def test_missing_or_malformed_identity_loads_as_none():
    assert OnlineIdentity.load() is None
    path = OnlineIdentity.path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"driver_id": "x", "driver_token": "short"}), encoding="utf-8")
    assert OnlineIdentity.load() is None
    path.write_text("not json", encoding="utf-8")
    assert OnlineIdentity.load() is None


# -- verification and board helpers ----------------------------------------------


def test_base_url_env_override(monkeypatch):
    monkeypatch.setenv("FREIGHT_FATE_ONLINE_URL", "http://localhost:3000/")
    assert base_url() == "http://localhost:3000"


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://orinks.net", code, "err", None, None)


def test_verify_identity_ok_posts_an_off_duty_signoff():
    transport = FakeTransport(reply={"ok": True, "cleared": True})
    assert verify_identity(IDENTITY, transport=transport) == "ok"
    url, payload, headers = transport.requests[0]
    assert url.endswith("/api/freight-fate/presence")
    # Empty activity means "off duty": validating never puts us on the board.
    assert payload == {"driverId": IDENTITY.driver_id, "activity": "", "detail": ""}
    assert headers["Authorization"] == f"Bearer {IDENTITY.driver_token}"


def test_verify_identity_maps_the_failure_modes():
    assert (
        verify_identity(IDENTITY, transport=FakeTransport(error=_http_error(404)))
        == "driver_not_found"
    )
    assert (
        verify_identity(IDENTITY, transport=FakeTransport(error=_http_error(401))) == "unauthorized"
    )
    # Other 4xx codes mean the server answered and refused the credentials
    # (issue 63: a malformed paste came back as HTTP 400), which must not be
    # reported to the player as a connection problem.
    assert verify_identity(IDENTITY, transport=FakeTransport(error=_http_error(400))) == "rejected"
    assert verify_identity(IDENTITY, transport=FakeTransport(error=_http_error(422))) == "rejected"
    assert verify_identity(IDENTITY, transport=FakeTransport(error=_http_error(500))) == "error"
    assert verify_identity(IDENTITY, transport=FakeTransport(error=OSError())) == "error"
    assert verify_identity(IDENTITY, transport=FakeTransport(reply={"ok": False})) == "error"


def test_fetch_board_returns_drivers_or_none():
    drivers = [{"displayName": "Road Star", "activity": "Driving", "detail": "", "updatedAt": 1}]
    assert fetch_board(transport=FakeTransport(reply={"drivers": drivers})) == drivers
    assert fetch_board(transport=FakeTransport(reply={})) is None
    assert fetch_board(transport=FakeTransport(error=OSError())) is None


# -- build identity reporting --------------------------------------------------


def test_client_version_reports_source_checkout_without_a_build_stamp():
    # Tests run from a source checkout, so there is no build_info.json and
    # the reported identity must be the source form, not a bogus stable tag.
    import freight_fate
    from freight_fate.online_presence import client_version

    assert client_version() == f"source-{freight_fate.__version__}"


def test_client_version_reports_the_packaged_build_tag(monkeypatch):
    from freight_fate import online_presence, updater

    monkeypatch.setattr(
        updater,
        "load_build_info",
        lambda version: updater.BuildInfo(tag="nightly-20260711", channel="dev", built_at=""),
    )
    assert online_presence.client_version() == "nightly-20260711"

    # A mangled stamp must not be able to break the request header: spaces
    # and control characters are dropped rather than sent.
    monkeypatch.setattr(
        updater,
        "load_build_info",
        lambda version: updater.BuildInfo(tag="bad tag\n", channel="dev", built_at=""),
    )
    assert online_presence.client_version() == "badtag"


def test_default_transport_stamps_the_build_in_the_user_agent(monkeypatch):
    import urllib.request

    from freight_fate import online_presence

    captured = {}

    class FakeResponse:
        def read(self):
            return b'{"ok": true}'

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(req, timeout=None, context=None):
        captured["user_agent"] = req.get_header("User-agent")
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    reply = online_presence._http_json("https://example.test/api", {"x": 1}, {})
    assert reply == {"ok": True}
    assert captured["user_agent"] == f"FreightFate/{online_presence.client_version()}"
