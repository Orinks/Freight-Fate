"""Network-destination safety for community radio streams.

Directory metadata is untrusted.  Validation happens before a station reaches
the dial and again during the bounded stream probe, including every redirect.
This cannot prevent DNS from changing after validation, but it keeps ordinary
SSRF targets and local-file tricks away from the desktop audio backend.
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

from .net import ssl_context

Resolver = Callable[[str, int | None], Iterable[tuple]]
MAX_REDIRECTS = 5
PROBE_TIMEOUT_S = 4.0
PROBE_BYTES = 1


class UnsafeStreamURL(ValueError):
    """Raised when a stream could contact a non-public destination."""


@dataclass(frozen=True)
class StreamProbe:
    url: str
    content_type: str


def _default_resolver(host: str, port: int | None) -> Iterable[tuple]:
    return socket.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)


def _resolved_addresses(records: Iterable[tuple]) -> tuple[str, ...]:
    addresses = []
    for record in records:
        try:
            address = str(record[4][0])
        except (IndexError, TypeError):
            continue
        if address not in addresses:
            addresses.append(address)
    return tuple(addresses)


def _is_public_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return bool(
        address.is_global
        and not address.is_multicast
        and not address.is_unspecified
        and not address.is_reserved
        and not address.is_link_local
        and not address.is_loopback
        and not address.is_private
    )


def validate_stream_url(url: str, *, resolver: Resolver = _default_resolver) -> str:
    """Return a normalized public HTTP(S) URL or raise ``UnsafeStreamURL``."""

    if not isinstance(url, str) or len(url) > 2048:
        raise UnsafeStreamURL("invalid URL")
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"}:
        raise UnsafeStreamURL("unsupported URL scheme")
    if not parts.hostname or parts.username is not None or parts.password is not None:
        raise UnsafeStreamURL("credentials or hostname are invalid")
    try:
        port = parts.port
    except ValueError as exc:
        raise UnsafeStreamURL("invalid port") from exc
    if port is not None and not 1 <= port <= 65535:
        raise UnsafeStreamURL("invalid port")
    host = parts.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise UnsafeStreamURL("local hostname")
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise UnsafeStreamURL("invalid hostname") from exc

    literal = None
    with suppress(ValueError):
        literal = ipaddress.ip_address(ascii_host)
    if literal is not None:
        addresses = (str(literal),)
    else:
        try:
            addresses = _resolved_addresses(resolver(ascii_host, port))
        except OSError as exc:
            raise UnsafeStreamURL("hostname did not resolve") from exc
    if not addresses or any(not _is_public_address(address) for address in addresses):
        raise UnsafeStreamURL("non-public destination")

    netloc_host = f"[{ascii_host}]" if ":" in ascii_host else ascii_host
    netloc = f"{netloc_host}:{port}" if port is not None else netloc_host
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, ""))


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, resolver: Resolver) -> None:
        super().__init__()
        self.resolver = resolver
        self.redirects = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirects += 1
        if self.redirects > MAX_REDIRECTS:
            raise UnsafeStreamURL("too many redirects")
        safe = validate_stream_url(urljoin(req.full_url, newurl), resolver=self.resolver)
        return super().redirect_request(req, fp, code, msg, headers, safe)


def probe_stream_url(
    url: str,
    *,
    user_agent: str,
    resolver: Resolver = _default_resolver,
    timeout: float = PROBE_TIMEOUT_S,
    opener_factory: Callable[..., urllib.request.OpenerDirector] = urllib.request.build_opener,
) -> StreamProbe:
    """Validate redirects and read one byte from a stream with a bounded wait."""

    safe = validate_stream_url(url, resolver=resolver)
    handler = _SafeRedirectHandler(resolver)
    opener = opener_factory(handler, urllib.request.HTTPSHandler(context=ssl_context()))
    request = urllib.request.Request(
        safe,
        headers={
            "User-Agent": user_agent,
            "Accept": "audio/*, application/ogg, application/vnd.apple.mpegurl, */*;q=0.2",
            "Range": f"bytes=0-{PROBE_BYTES - 1}",
            "Icy-MetaData": "0",
        },
    )
    try:
        with opener.open(request, timeout=max(0.1, timeout)) as response:
            final_url = validate_stream_url(response.geturl(), resolver=resolver)
            response.read(PROBE_BYTES)
            content_type = response.headers.get_content_type()
    except (OSError, urllib.error.URLError) as exc:
        raise ConnectionError("stream probe failed") from exc
    return StreamProbe(final_url, content_type)
