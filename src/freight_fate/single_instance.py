"""Single-instance launch guard for the game process."""

from __future__ import annotations

import contextlib
import ctypes
import logging
import sys

log = logging.getLogger(__name__)

SINGLE_INSTANCE_MUTEX_NAME = "Local\\FreightFate.SingleInstance"
ERROR_ALREADY_EXISTS = 183


def _configure_kernel32_signatures(kernel32) -> None:
    with contextlib.suppress(Exception):
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_bool,
            ctypes.c_wchar_p,
        ]
        kernel32.CloseHandle.restype = ctypes.c_bool
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]


class SingleInstanceGuard:
    """Coordinates one running Freight Fate instance per Windows session."""

    def __init__(self, mutex_name: str = SINGLE_INSTANCE_MUTEX_NAME) -> None:
        self.mutex_name = mutex_name
        self._mutex_handle: int | None = None
        self._acquired = False

    def acquire(self) -> bool:
        if sys.platform != "win32":
            self._acquired = True
            return True

        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            _configure_kernel32_signatures(kernel32)
            handle = kernel32.CreateMutexW(None, False, self.mutex_name)
            if not handle:
                log.warning("CreateMutexW failed; allowing startup to continue")
                return True

            if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
                kernel32.CloseHandle(handle)
                self._mutex_handle = None
                self._acquired = False
                return False

            self._mutex_handle = handle
            self._acquired = True
            return True
        except Exception:
            log.exception("Single-instance check failed; allowing startup to continue")
            return True

    def release(self) -> None:
        if not self._mutex_handle:
            self._acquired = False
            return

        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            _configure_kernel32_signatures(kernel32)
            kernel32.CloseHandle(self._mutex_handle)
        except Exception:
            log.debug("Failed to close single-instance mutex", exc_info=True)
        finally:
            self._mutex_handle = None
            self._acquired = False

    def __enter__(self) -> SingleInstanceGuard:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    @property
    def acquired(self) -> bool:
        return self._acquired
