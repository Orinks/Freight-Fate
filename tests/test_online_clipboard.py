"""Clipboard fallback behavior for the online setup paste items.

The macOS path matters most: creating a hidden Tk root inside a running SDL
app aborts the whole process at the C level, so on darwin the fallback must
be pbpaste and tkinter must never be touched.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

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
