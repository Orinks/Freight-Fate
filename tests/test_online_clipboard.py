"""Clipboard fallback behavior underlying the activation-code review items.

The macOS path matters most: creating a hidden Tk root inside a running SDL
app aborts the whole process at the C level, so on darwin the fallback must
be pbpaste and tkinter must never be touched.

The X11 tests matter for the opposite reason: on Linux there is no fallback
worth having (tkinter is not installed on a stock desktop and is not in the
release build), so scrap itself has to succeed.

The clipboard is a write-only channel now (see ``write_clipboard_text`` and
``OnlineSetupState._copy_code`` in ``online_states.py``) -- the game no
longer parses anything a player pastes in, but the read path stays because
``write_clipboard_text`` verifies its own write by reading it back.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pygame

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


def _win32_with_scrap(monkeypatch, scrap):
    """Native Windows, or Wine standing in for it: scrap answers before any
    Tk fallback is ever tried."""
    monkeypatch.setattr(online_states, "pygame", SimpleNamespace(scrap=scrap))
    monkeypatch.setattr(online_states.sys, "platform", "win32")


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


def test_utf16_clipboard_payload_round_trips_on_windows(monkeypatch):
    """On Windows (native or under Wine), the charset=utf-8 scrap type is
    really CF_UNICODETEXT and answers in UTF-16LE despite its name, NUL
    -terminated like every Windows clipboard string. Decoding it as UTF-8
    silently eats every non-ASCII character -- this is the bug under test."""
    text = "Delivered to Montréal — 12 tonnes"

    class FakeScrap:
        @staticmethod
        def get_init():
            return True

        @staticmethod
        def get(scrap_type):
            if scrap_type == pygame.SCRAP_TEXT:
                return None  # what Wine yields when the owner offers only UTF8_STRING
            return text.encode("utf-16-le") + b"\x00\x00"  # Windows NUL-terminates

    _win32_with_scrap(monkeypatch, FakeScrap)
    assert online_states._clipboard_once() == text


def test_utf8_clipboard_payload_round_trips_on_linux(monkeypatch):
    """The identical scrap type is genuinely UTF8_STRING on X11 -- not
    UTF-16LE. If the per-platform encoding table were ever "simplified" into
    always treating that type as UTF-16, this would silently corrupt every
    non-ASCII paste on native Linux, the opposite of the Windows/Wine bug."""
    text = "Delivered to Montréal — 12 tonnes"
    _linux_with_scrap(monkeypatch, _X11Scrap(text.encode("utf-8")))
    assert online_states._clipboard_once() == text
