"""Shared HTTPS helpers: a TLS context that verifies everywhere, and
speakable descriptions of network failures.

Frozen builds can ship a Python whose OpenSSL looks for CA certificates
at paths baked in on the build machine; on macOS and Linux those usually
do not exist on the player's computer, so every HTTPS request fails
certificate verification. Loading certifi's bundle on top of the platform
defaults makes verification work on all three platforms while keeping
system-store extras (such as corporate proxy roots on Windows) trusted too.
"""

from __future__ import annotations

import socket
import ssl
import urllib.error
from functools import lru_cache


@lru_cache(maxsize=1)
def ssl_context() -> ssl.SSLContext:
    """The platform's default verification plus certifi's CA bundle."""
    ctx = ssl.create_default_context()
    try:
        import certifi

        ctx.load_verify_locations(cafile=certifi.where())
    except (ImportError, OSError):
        pass  # the platform store alone will have to do
    return ctx


def describe_error(e: BaseException) -> str:
    """A short, speakable reason for a failed HTTP request.

    Spoken to the player after lines like "Could not reach the update
    server", so each message is a complete plain sentence.
    """
    if isinstance(e, urllib.error.HTTPError):
        return f"The server answered with error {e.code}."
    if isinstance(e, urllib.error.URLError) and isinstance(e.reason, BaseException):
        return describe_error(e.reason)
    if isinstance(e, ssl.SSLCertVerificationError):
        return "The secure connection could not be verified."
    if isinstance(e, ssl.SSLError):
        return "The secure connection failed."
    if isinstance(e, socket.gaierror):
        return "The server address could not be found."
    if isinstance(e, TimeoutError):
        return "The connection timed out."
    if isinstance(e, ConnectionError):
        return "The connection was refused or dropped."
    text = str(e).strip()
    return f"{text}." if text else f"{type(e).__name__}."
