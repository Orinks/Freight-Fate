"""Clipboard fallback behavior for the online setup paste items.

The macOS path matters most: creating a hidden Tk root inside a running SDL
app aborts the whole process at the C level, so on darwin the fallback must
be pbpaste and tkinter must never be touched.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

from freight_fate.settings import Settings
from freight_fate.states import online_states


def _no_scrap(monkeypatch):
    """Make the pygame scrap path fail so the platform fallback runs."""
    monkeypatch.setattr(online_states, "pygame", SimpleNamespace(scrap=None))


def test_mac_fallback_reads_pbpaste(monkeypatch):
    _no_scrap(monkeypatch)
    monkeypatch.setattr(online_states.sys, "platform", "darwin")
    calls: list[list[str]] = []

    def fake_run(cmd, capture_output, timeout, check):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout=b"  abc-driver-123\r\n\x00")

    monkeypatch.setattr(online_states.subprocess, "run", fake_run)
    assert online_states._clipboard_once() == "abc-driver-123"
    assert calls == [["pbpaste"]]


def test_mac_fallback_never_creates_tk(monkeypatch):
    _no_scrap(monkeypatch)
    monkeypatch.setattr(online_states.sys, "platform", "darwin")

    def fake_run(cmd, capture_output, timeout, check):
        raise FileNotFoundError("pbpaste missing")

    monkeypatch.setattr(online_states.subprocess, "run", fake_run)
    created: list[int] = []
    spy_tk = SimpleNamespace(Tk=lambda: created.append(1))
    monkeypatch.setitem(sys.modules, "tkinter", spy_tk)
    assert online_states._clipboard_once() is None
    assert created == []


def test_mac_fallback_empty_clipboard_is_none(monkeypatch):
    _no_scrap(monkeypatch)
    monkeypatch.setattr(online_states.sys, "platform", "darwin")

    def fake_run(cmd, capture_output, timeout, check):
        return SimpleNamespace(returncode=0, stdout=b"\x00\r\n ")

    monkeypatch.setattr(online_states.subprocess, "run", fake_run)
    assert online_states._clipboard_once() is None


def test_non_mac_still_uses_tk_fallback(monkeypatch):
    _no_scrap(monkeypatch)
    monkeypatch.setattr(online_states.sys, "platform", "win32")

    class FakeRoot:
        def withdraw(self):
            pass

        def clipboard_get(self):
            return "ffd_token\n"

        def destroy(self):
            pass

    spy_tk = SimpleNamespace(Tk=FakeRoot)
    monkeypatch.setitem(sys.modules, "tkinter", spy_tk)
    assert online_states._clipboard_once() == "ffd_token"


def test_mac_write_uses_pbcopy_and_never_creates_tk(monkeypatch):
    _no_scrap(monkeypatch)
    monkeypatch.setattr(online_states.sys, "platform", "darwin")
    sent: list[bytes] = []

    def fake_run(cmd, **kwargs):
        if cmd == ["pbcopy"]:
            sent.append(kwargs["input"])
            return SimpleNamespace(returncode=0)
        if cmd == ["pbpaste"]:
            return SimpleNamespace(returncode=0, stdout=sent[-1] if sent else b"")
        raise AssertionError(cmd)

    monkeypatch.setattr(online_states.subprocess, "run", fake_run)
    created: list[int] = []
    monkeypatch.setitem(sys.modules, "tkinter", SimpleNamespace(Tk=lambda: created.append(1)))
    assert online_states.write_clipboard_text("summary line one\nline two")
    assert sent == [b"summary line one\nline two"]
    assert created == []


def test_write_reports_failure_when_read_back_disagrees(monkeypatch):
    # "Copied" must never be optimistic: a write that claims success while
    # the clipboard holds something else is reported as a failure.
    _no_scrap(monkeypatch)
    monkeypatch.setattr(online_states.sys, "platform", "darwin")

    def fake_run(cmd, **kwargs):
        if cmd == ["pbcopy"]:
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=0, stdout=b"something else entirely")

    monkeypatch.setattr(online_states.subprocess, "run", fake_run)
    monkeypatch.setattr(online_states.time, "sleep", lambda _s: None)
    assert not online_states.write_clipboard_text("expected text")


def test_read_back_forgives_windows_crlf(monkeypatch):
    monkeypatch.setattr(online_states, "_clipboard_once", lambda: "line one\r\nline two")
    assert online_states._clipboard_holds("line one\nline two")


def test_token_paste_requires_the_site_prefix():
    # Site tokens are always "ffd_" plus 64 hex characters. Issue 63: an
    # 87-character wrong paste used to pass this check and reach the server,
    # which refused it with an HTTP 400 the player could not interpret.
    assert online_states.looks_like_token("ffd_" + "a" * 64)
    assert not online_states.looks_like_token("a" * 87)
    assert not online_states.looks_like_token("ffd_token with spaces")
    assert not online_states.looks_like_token("ffd_x")  # far too short


def test_account_setup_connects_with_both_sharing_toggles_off(monkeypatch):
    calls: list[tuple[str, object]] = []

    class ImmediateThread:
        def __init__(self, *, target, **_kwargs):
            self.target = target

        def start(self):
            self.target()

    settings = Settings(online_presence=True, cloud_saves=True)
    ctx = SimpleNamespace(
        settings=settings,
        audio=SimpleNamespace(play=lambda sound: calls.append(("sound", sound))),
        say=lambda text, interrupt=True: calls.append(("say", text)),
        pop_state=lambda: calls.append(("pop", None)),
        adopt_online_identity=lambda identity: calls.append(("identity", identity.driver_id)),
        apply_online_presence=lambda: calls.append(("profile", settings.online_presence)),
        apply_cloud_saves=lambda: calls.append(("cloud", settings.cloud_saves)),
    )
    monkeypatch.setattr(online_states.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(online_states.online_presence, "verify_identity", lambda _identity: "ok")

    def turn_public_sharing_off(_identity, enabled):
        calls.append(("server_profile", enabled))
        return "ok"

    monkeypatch.setattr(
        online_states.online_presence, "set_profile_sharing", turn_public_sharing_off
    )
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    state._driver_id = "road-star-abcd1234"
    state._token = "ffd_" + "a" * 64
    state._connect()
    state.update(0)

    assert settings.online_presence is False
    assert settings.cloud_saves is False
    assert ("server_profile", False) in calls
    assert ("profile", False) in calls
    assert ("cloud", False) in calls
