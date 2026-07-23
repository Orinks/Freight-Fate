import socket
from email.message import Message

import pytest

from freight_fate.radio_url_safety import (
    UnsafeStreamURL,
    probe_stream_url,
    validate_stream_url,
)


def _resolver(address: str):
    return lambda host, port: [
        (
            socket.AF_INET6 if ":" in address else socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            (address, port),
        )
    ]


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/music",
        "https://user:secret@example.com/stream",
        "https://localhost/stream",
        "https://radio.local/stream",
        "https://127.0.0.1/stream",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/stream",
        "http://224.0.0.1/stream",
        "http://0.0.0.0/stream",
    ],
)
def test_stream_url_rejects_unsafe_destinations(url):
    with pytest.raises(UnsafeStreamURL):
        validate_stream_url(url, resolver=_resolver("93.184.216.34"))


def test_stream_url_rejects_hostname_resolving_to_private_address():
    with pytest.raises(UnsafeStreamURL, match="non-public"):
        validate_stream_url("https://radio.example/stream", resolver=_resolver("10.0.0.7"))


def test_stream_url_accepts_public_http_and_https():
    resolver = _resolver("93.184.216.34")
    assert validate_stream_url("HTTPS://Radio.Example/live", resolver=resolver) == (
        "https://radio.example/live"
    )
    assert validate_stream_url("http://radio.example:8000/stream", resolver=resolver) == (
        "http://radio.example:8000/stream"
    )


class _Response:
    def __init__(self, url: str):
        self._url = url
        self.headers = Message()
        self.headers["Content-Type"] = "audio/mpeg"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self._url

    def read(self, size):
        return b"x"[:size]


class _Opener:
    def __init__(self, final_url):
        self.final_url = final_url
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return _Response(self.final_url)


def test_probe_revalidates_redirect_target():
    resolver = _resolver("93.184.216.34")
    opener = _Opener("http://127.0.0.1/admin")
    with pytest.raises(UnsafeStreamURL):
        probe_stream_url(
            "https://radio.example/live",
            user_agent="Freight-Fate/test",
            resolver=resolver,
            opener_factory=lambda *handlers: opener,
        )


def test_probe_returns_validated_final_url_and_is_bounded():
    resolver = _resolver("93.184.216.34")
    opener = _Opener("https://cdn.example/audio")
    result = probe_stream_url(
        "https://radio.example/live",
        user_agent="Freight-Fate/test",
        resolver=resolver,
        timeout=1.25,
        opener_factory=lambda *handlers: opener,
    )
    assert result.url == "https://cdn.example/audio"
    assert result.content_type == "audio/mpeg"
    request, timeout = opener.calls[0]
    assert timeout == 1.25
    assert request.headers["User-agent"] == "Freight-Fate/test"
