"""Clipboard fallback behavior for the online setup paste items.

The macOS path matters most: creating a hidden Tk root inside a running SDL
app aborts the whole process at the C level, so on darwin the fallback must
be pbpaste and tkinter must never be touched.

The X11 tests matter for the opposite reason: on Linux there is no fallback
worth having (tkinter is not installed on a stock desktop and is not in the
release build), so scrap itself has to succeed.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pygame
from speech_capture import speech_stub

from freight_fate.settings import Settings
from freight_fate.states import online_states


def _no_scrap(monkeypatch):
    """Make the pygame scrap path fail so the platform fallback runs."""
    monkeypatch.setattr(online_states, "pygame", SimpleNamespace(scrap=None))


class _X11Scrap:
    """pygame's X11 scrap, which the Windows one does not resemble.

    A scrap type on X11 is the selection target the clipboard owner really
    advertises. Desktop apps and browsers advertise "text/plain;charset=utf-8";
    none of them advertise the bare "text/plain" that pygame.SCRAP_TEXT is. So
    a read for SCRAP_TEXT comes back empty and a write for it is refused.
    """

    TYPE = "text/plain;charset=utf-8"

    def __init__(self, held: bytes | None = None):
        self.held = held

    def get_init(self) -> bool:
        return True

    def init(self) -> None:
        pass

    def get(self, scrap_type: str) -> bytes | None:
        return self.held if scrap_type == self.TYPE else None

    def put(self, scrap_type: str, data: bytes) -> None:
        if scrap_type != self.TYPE:
            # pygame.error, which subclasses RuntimeError.
            raise RuntimeError("content could not be placed in clipboard.")
        self.held = data


def _linux_with_scrap(monkeypatch, scrap):
    """A stock Linux desktop: scrap works, and there is no Tk to fall back to."""
    monkeypatch.setattr(online_states, "pygame", SimpleNamespace(scrap=scrap))
    monkeypatch.setattr(online_states.sys, "platform", "linux")
    monkeypatch.setitem(sys.modules, "tkinter", None)  # import tkinter -> ImportError


def test_x11_read_uses_the_type_the_clipboard_actually_offers(monkeypatch):
    _linux_with_scrap(monkeypatch, _X11Scrap(b"road-star-abcd1234\n"))
    assert online_states._clipboard_once() == "road-star-abcd1234"


def test_x11_write_uses_the_type_x11_accepts(monkeypatch):
    scrap = _X11Scrap()
    _linux_with_scrap(monkeypatch, scrap)
    assert online_states.write_clipboard_text("ffd_" + "a" * 64)
    assert scrap.held == b"ffd_" + b"a" * 64


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


def test_utf16_clipboard_payload_round_trips(monkeypatch):
    """The charset=utf-8 scrap type is CF_UNICODETEXT on Windows and answers
    in UTF-16LE. Decoding it as UTF-8 silently eats every non-ASCII character."""
    text = "Delivered to Montréal — 12 tonnes"

    class FakeScrap:
        @staticmethod
        def get_init():
            return True

        @staticmethod
        def get(scrap_type):
            if scrap_type == pygame.SCRAP_TEXT:
                return None  # what Wine yields when the owner offers only UTF8_STRING
            return text.encode("utf-16-le")

    monkeypatch.setattr(pygame, "scrap", FakeScrap)
    assert online_states._clipboard_once() == text


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
        say=speech_stub(calls, tag="say"),
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


def test_account_setup_saves_the_exact_verified_credentials(monkeypatch):
    pending = []
    saved = []

    class DeferredThread:
        def __init__(self, *, target, **_kwargs):
            pending.append(target)

        def start(self):
            return None

    settings = Settings()
    ctx = SimpleNamespace(
        settings=settings,
        audio=SimpleNamespace(play=lambda _sound: None),
        say=lambda *_args, **_kwargs: None,
        pop_state=lambda: None,
        adopt_online_identity=lambda identity: saved.append(identity),
        apply_online_presence=lambda: None,
        apply_cloud_saves=lambda: None,
    )
    monkeypatch.setattr(online_states.threading, "Thread", DeferredThread)
    monkeypatch.setattr(online_states.online_presence, "verify_identity", lambda _identity: "ok")
    monkeypatch.setattr(
        online_states.online_presence,
        "set_profile_sharing",
        lambda _identity, _enabled: "ok",
    )
    monkeypatch.setattr(online_states.OnlineIdentity, "save", lambda identity: None)
    state = online_states.OnlineSetupState(ctx)
    state.enter()
    verified = online_states.OnlineIdentity(
        driver_id="road-star-abcd1234", driver_token="ffd_" + "a" * 64
    )
    state._driver_id = verified.driver_id
    state._token = verified.driver_token

    state._connect()
    state._driver_id = "road-star-replaced"
    state._token = "ffd_" + "b" * 64
    pending[0]()
    state.update(0)

    assert saved == [verified]
