from __future__ import annotations

import ctypes

from freight_fate.single_instance import (
    ERROR_ALREADY_EXISTS,
    SINGLE_INSTANCE_MUTEX_NAME,
    SingleInstanceGuard,
)


class _FakeKernel32:
    def __init__(self, *, handle: int = 1234, last_error: int = 0) -> None:
        self.handle = handle
        self.last_error = last_error
        self.create_mutex_calls: list[tuple[object, bool, str]] = []
        self.closed_handles: list[int] = []

    def CreateMutexW(self, security_attributes, initial_owner, name):
        self.create_mutex_calls.append((security_attributes, initial_owner, name))
        return self.handle

    def CloseHandle(self, handle):
        self.closed_handles.append(handle)
        return True


def _patch_windows(monkeypatch, kernel32: _FakeKernel32) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    # ctypes.WinDLL only exists on Windows; raising=False lets this test mock
    # the Windows mutex path on Linux/macOS CI runners too.
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel32, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: kernel32.last_error)


def test_windows_mutex_uses_stable_name(monkeypatch):
    kernel32 = _FakeKernel32()
    _patch_windows(monkeypatch, kernel32)

    guard = SingleInstanceGuard()

    assert guard.acquire() is True
    assert guard.acquired is True
    assert kernel32.create_mutex_calls == [(None, False, SINGLE_INSTANCE_MUTEX_NAME)]

    guard.release()
    assert kernel32.closed_handles == [1234]
    assert guard.acquired is False


def test_second_windows_launch_is_rejected(monkeypatch):
    kernel32 = _FakeKernel32(last_error=ERROR_ALREADY_EXISTS)
    _patch_windows(monkeypatch, kernel32)

    guard = SingleInstanceGuard()

    assert guard.acquire() is False
    assert guard.acquired is False
    assert kernel32.closed_handles == [1234]


def test_non_windows_single_instance_is_non_blocking(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")

    guard = SingleInstanceGuard()

    assert guard.acquire() is True
    assert guard.acquired is True
    guard.release()
    assert guard.acquired is False
