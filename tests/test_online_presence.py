"""Tests for the opt-in orinks.net drivers-board service.

These cover the behaviour that must hold regardless of whether the site is
even reachable: the disabled/off-by-default path, heartbeat and change
scheduling, the off-duty grace and sign-off, credential storage, and the
pasted-credential verification. A fake transport and an injected clock keep
every test deterministic and free of real sockets.
"""

from __future__ import annotations

import json
import urllib.error

from freight_fate.discord_presence import PresenceState
from freight_fate.online_presence import (
    HEARTBEAT_INTERVAL_S,
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
