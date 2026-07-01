"""Tests for the optional Discord Rich Presence service.

These cover the behaviour that must hold regardless of whether Discord is even
installed: pure formatting, the disabled path, a missing/unavailable RPC,
de-duplication and throttling of updates, and clean shutdown. A fake RPC client
and an injected clock keep every test deterministic and free of real sockets.
"""

from __future__ import annotations

import time

from freight_fate.discord_presence import (
    DEFAULT_CLIENT_ID,
    MAX_FIELD_LEN,
    DiscordPresence,
    PresenceState,
    driving_presence,
    format_activity,
)


class FakeRpc:
    """A stand-in for ``pypresence.Presence`` recording every call."""

    def __init__(
        self, *, connect_error: Exception | None = None, update_error: Exception | None = None
    ) -> None:
        self.connect_error = connect_error
        self.update_error = update_error
        self.connects = 0
        self.updates: list[dict] = []
        self.cleared = 0
        self.closed = 0

    def connect(self):
        self.connects += 1
        if self.connect_error is not None:
            raise self.connect_error

    def update(self, **kwargs):
        if self.update_error is not None:
            raise self.update_error
        self.updates.append(kwargs)

    def clear(self):
        self.cleared += 1

    def close(self):
        self.closed += 1


class Clock:
    """A manually advanced monotonic clock."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def make_presence(rpc, clock, *, enabled=True, min_interval_s=15.0):
    """A synchronous (non-threaded) service wired to a fake RPC and clock."""
    return DiscordPresence(
        enabled=enabled,
        client_id="test-app-id",
        min_interval_s=min_interval_s,
        clock=clock,
        rpc_factory=lambda _cid: rpc,
        session_start=1234.0,
        threaded=False,
    )


# -- application id -----------------------------------------------------------


def test_default_client_id_is_the_registered_freight_fate_app():
    assert DEFAULT_CLIENT_ID == "1519334426453082162"
    assert DEFAULT_CLIENT_ID.isdecimal()


def test_default_client_id_is_used_when_no_override_is_supplied():
    captured: list[str] = []

    def factory(client_id: str):
        captured.append(client_id)
        return FakeRpc()

    presence = DiscordPresence(
        min_interval_s=0.0,
        rpc_factory=factory,
        threaded=False,
    )
    presence.start()
    presence.update(PresenceState("In the main menu"))
    presence.shutdown()

    assert captured == [DEFAULT_CLIENT_ID]


# -- formatting ---------------------------------------------------------------


def test_format_activity_maps_fields_and_includes_start():
    payload = format_activity(PresenceState("Driving a route", "Chicago to Dallas"), start=1234.0)
    assert payload["details"] == "Driving a route"
    assert payload["state"] == "Chicago to Dallas"
    assert payload["start"] == 1234


def test_format_activity_omits_empty_state_line():
    payload = format_activity(PresenceState("In the main menu"))
    assert payload["details"] == "In the main menu"
    assert "state" not in payload
    assert "start" not in payload


def test_format_activity_truncates_to_discord_limit():
    long_detail = "x" * 500
    payload = format_activity(PresenceState("A" * 500, long_detail))
    assert len(payload["details"]) <= MAX_FIELD_LEN
    assert len(payload["state"]) <= MAX_FIELD_LEN
    assert payload["details"].endswith("…")


def test_driving_presence_is_privacy_safe_and_concise():
    state = driving_presence(
        phase="delivery",
        origin="Chicago",
        destination="Dallas",
        cargo="steel coils",
        fraction=0.42,
        moving=True,
        truck_label="Standard rig",
    )
    assert state.activity == "Driving: Chicago to Dallas"
    assert "steel coils" in state.detail
    assert "40% there" in state.detail  # rounded to nearest 5%
    assert "Standard rig" in state.detail
    # Nothing private leaks into the strings.
    blob = (state.activity + state.detail).lower()
    assert "save" not in blob and "/" not in blob and "\\" not in blob


def test_driving_presence_stopped_and_pickup_phrasing():
    stopped = driving_presence(
        phase="delivery",
        origin="Reno",
        destination="Boise",
        cargo="lumber",
        fraction=0.9,
        moving=False,
    )
    assert stopped.activity.startswith("Stopped")

    pickup = driving_presence(
        phase="pickup",
        origin="Tampa",
        destination="Miami",
        cargo="produce",
        fraction=0.1,
        moving=True,
    )
    assert "pickup" in pickup.activity.lower()
    assert "produce" in pickup.detail


def test_driving_presence_clamps_fraction():
    assert (
        "0% there"
        in driving_presence(
            phase="delivery", origin="A", destination="B", cargo="x", fraction=-1.0, moving=True
        ).detail
    )
    assert (
        "100% there"
        in driving_presence(
            phase="delivery", origin="A", destination="B", cargo="x", fraction=2.0, moving=True
        ).detail
    )


# -- disabled mode ------------------------------------------------------------


def test_disabled_never_touches_rpc():
    rpc = FakeRpc()
    clock = Clock()
    presence = make_presence(rpc, clock, enabled=False)
    presence.start()
    presence.update(PresenceState("In the main menu"))
    presence.shutdown()
    assert not presence.enabled
    assert rpc.connects == 0
    assert rpc.updates == []


# -- missing dependency / unavailable Discord ---------------------------------


def test_missing_dependency_leaves_service_dormant():
    # rpc_factory=None models pypresence being absent entirely.
    presence = DiscordPresence(rpc_factory=None, threaded=False)
    assert not presence.enabled
    presence.start()
    presence.update(PresenceState("In the main menu"))
    presence.shutdown()  # must not raise


def test_discord_closed_is_handled_and_retried_after_backoff():
    rpc = FakeRpc(connect_error=ConnectionRefusedError("Discord not running"))
    clock = Clock()
    presence = make_presence(rpc, clock)
    presence.start()
    presence.update(PresenceState("In the main menu"))
    assert rpc.connects == 1  # tried once
    assert rpc.updates == []  # nothing sent; no crash
    assert not presence.connected

    # Within the backoff window it does not hammer the socket.
    presence.update(PresenceState("At the terminal"))
    assert rpc.connects == 1

    # After the backoff window it tries again.
    clock.advance(31.0)
    presence.update(PresenceState("Driving a route"))
    assert rpc.connects == 2
    presence.shutdown()


def test_update_failure_drops_connection_for_reconnect():
    rpc = FakeRpc(update_error=RuntimeError("pipe closed"))
    clock = Clock()
    presence = make_presence(rpc, clock)
    presence.start()
    presence.update(PresenceState("Driving a route"))
    assert rpc.connects == 1
    assert not presence.connected  # disconnected after the failed update
    presence.shutdown()  # never raises


# -- throttling / de-duplication ---------------------------------------------


def test_identical_state_is_not_resent():
    rpc = FakeRpc()
    clock = Clock()
    presence = make_presence(rpc, clock)
    presence.start()
    presence.update(PresenceState("Driving a route", "Chicago to Dallas"))
    presence.update(PresenceState("Driving a route", "Chicago to Dallas"))
    presence.update(PresenceState("Driving a route", "Chicago to Dallas"))
    assert len(rpc.updates) == 1
    presence.shutdown()


def test_changes_are_throttled_then_flushed():
    rpc = FakeRpc()
    clock = Clock()
    presence = make_presence(rpc, clock, min_interval_s=15.0)
    presence.start()
    presence.update(PresenceState("In the main menu"))
    assert len(rpc.updates) == 1

    # A new state inside the throttle window is held back, not sent.
    clock.advance(5.0)
    presence.update(PresenceState("At the terminal"))
    assert len(rpc.updates) == 1

    # Once the window passes, the latest state flushes on the next report.
    clock.advance(11.0)
    presence.update(PresenceState("Driving a route"))
    assert len(rpc.updates) == 2
    assert rpc.updates[-1]["details"] == "Driving a route"
    presence.shutdown()


def test_first_update_sends_immediately():
    rpc = FakeRpc()
    clock = Clock()
    presence = make_presence(rpc, clock)
    presence.start()
    presence.update(PresenceState("In the main menu"))
    assert len(rpc.updates) == 1
    assert rpc.updates[0]["details"] == "In the main menu"
    presence.shutdown()


# -- shutdown cleanup ---------------------------------------------------------


def test_shutdown_clears_and_closes_the_rpc():
    rpc = FakeRpc()
    clock = Clock()
    presence = make_presence(rpc, clock)
    presence.start()
    presence.update(PresenceState("Driving a route"))
    presence.shutdown()
    assert rpc.cleared == 1
    assert rpc.closed == 1
    assert not presence.connected


def test_shutdown_is_idempotent_and_safe_without_start():
    presence = make_presence(FakeRpc(), Clock())
    presence.shutdown()
    presence.shutdown()  # no error on a second call or when never started


def test_set_enabled_toggles_runtime_state():
    rpc = FakeRpc()
    clock = Clock()
    presence = make_presence(rpc, clock)
    presence.start()
    presence.update(PresenceState("Driving a route"))
    assert len(rpc.updates) == 1

    presence.set_enabled(False)
    assert not presence.enabled
    assert rpc.cleared == 1  # disabling tears the presence down
    presence.update(PresenceState("At the terminal"))
    assert len(rpc.updates) == 1  # ignored while disabled

    # Re-enabling reconnects and re-shows the last reported state at once.
    presence.set_enabled(True)
    assert len(rpc.updates) == 2
    assert rpc.updates[-1]["details"] == "Driving a route"

    # A fresh distinct state flushes after the throttle window.
    clock.advance(20.0)
    presence.update(PresenceState("At the terminal"))
    assert len(rpc.updates) == 3
    assert rpc.updates[-1]["details"] == "At the terminal"
    presence.shutdown()


# -- threaded path smoke ------------------------------------------------------


def test_threaded_service_sends_and_shuts_down():
    rpc = FakeRpc()
    presence = DiscordPresence(
        client_id="test-app-id",
        min_interval_s=0.0,
        rpc_factory=lambda _cid: rpc,
        threaded=True,
    )
    presence.start()
    presence.update(PresenceState("In the main menu"))
    # Give the worker a moment to connect and push the first update.
    deadline = time.monotonic() + 2.0
    while not rpc.updates and time.monotonic() < deadline:
        time.sleep(0.01)
    presence.shutdown()
    assert rpc.connects >= 1
    assert rpc.updates
    assert rpc.closed == 1
