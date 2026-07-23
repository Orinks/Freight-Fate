import json
import socket

import pytest

from freight_fate.radio_browser import (
    NEARBY_DIAL_LIMIT,
    RadioBrowserClient,
    discover_mirrors,
    normalize_stations,
    sanitize_directory_text,
)

PUBLIC_RECORDS = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def _resolver(host, port):
    return PUBLIC_RECORDS


def _row(**updates):
    value = {
        "stationuuid": "12345678-1234-1234-1234-123456789abc",
        "name": "KTEST Community",
        "countrycode": "US",
        "state": "New York",
        "iso_3166_2": "US-NY",
        "lastcheckok": 1,
        "codec": "MP3",
        "bitrate": 128,
        "geo_lat": 42.9,
        "geo_long": -78.8,
        "url_resolved": "https://stream.example/live",
        "tags": "community, jazz",
    }
    value.update(updates)
    return value


def test_mirror_discovery_uses_dns_reverse_names_and_randomizes():
    addresses = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("2.2.2.2", 443)),
    ]
    reverse_names = {
        "1.1.1.1": ("us1.api.radio-browser.info", [], []),
        "2.2.2.2": ("de1.api.radio-browser.info", [], []),
    }
    shuffled = []
    mirrors = discover_mirrors(
        lookup=lambda *args, **kwargs: addresses,
        reverse=lambda address: reverse_names[address],
        shuffle=lambda hosts: (hosts.reverse(), shuffled.extend(hosts)),
    )
    assert mirrors == ("de1.api.radio-browser.info", "us1.api.radio-browser.info")
    assert shuffled == list(mirrors)


class _Response:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.value).encode()


def test_client_queries_state_with_mirror_failover_and_descriptive_agent():
    calls = []

    def opener(request, **kwargs):
        calls.append((request, kwargs))
        if "bad." in request.full_url:
            raise OSError("down")
        return _Response([_row()])

    client = RadioBrowserClient(
        mirrors=lambda: ("bad.api.radio-browser.info", "good.api.radio-browser.info"),
        opener=opener,
    )
    rows, host = client.stations_for_state("New York")
    assert rows[0]["stationuuid"].startswith("1234")
    assert host == "good.api.radio-browser.info"
    assert len(calls) == 2
    request = calls[-1][0]
    assert "state=New+York" in request.full_url
    assert "countrycode=US" in request.full_url
    assert "hidebroken=true" in request.full_url
    assert request.headers["User-agent"].startswith("Freight-Fate/")


def test_normalization_filters_distance_codec_bitrate_geo_and_region():
    rows = [
        _row(),
        _row(stationuuid="22345678-1234-1234-1234-123456789abc", codec="WMA"),
        _row(stationuuid="32345678-1234-1234-1234-123456789abc", bitrate=8),
        _row(stationuuid="42345678-1234-1234-1234-123456789abc", geo_lat=None),
        _row(
            stationuuid="52345678-1234-1234-1234-123456789abc",
            state="California",
            iso_3166_2="US-CA",
        ),
        _row(stationuuid="62345678-1234-1234-1234-123456789abc", lastcheckok=0),
        _row(
            stationuuid="72345678-1234-1234-1234-123456789abc",
            geo_lat=40.7,
            geo_long=-74.0,
        ),
    ]
    result = normalize_stations(
        rows,
        state_name="New York",
        state_code="NY",
        position=(42.88, -78.87),
        resolver=_resolver,
        distance_cap_miles=100,
    )
    assert [station.uuid for station in result] == ["12345678-1234-1234-1234-123456789abc"]


def test_normalization_sanitizes_metadata_and_rejects_unsafe_or_duplicate_urls():
    rows = [
        _row(
            name="  KTEST\n<script>\x00" + "x" * 100,
            tags="jazz,\ncommunity,\x07local",
        ),
        _row(
            stationuuid="22345678-1234-1234-1234-123456789abc",
            url_resolved="https://stream.example/live",
        ),
        _row(
            stationuuid="32345678-1234-1234-1234-123456789abc",
            url_resolved="http://127.0.0.1/private",
        ),
    ]
    result = normalize_stations(
        rows,
        state_name="New York",
        state_code="NY",
        position=(42.88, -78.87),
        resolver=_resolver,
    )
    assert len(result) == 1
    assert "\n" not in result[0].name and "\x00" not in result[0].name
    assert len(result[0].name) <= 60
    assert "community" in result[0].format


def test_normalization_deduplicates_uuid_and_has_stable_bounded_order():
    rows = []
    for index in range(NEARBY_DIAL_LIMIT + 10):
        rows.append(
            _row(
                stationuuid=f"{index:08x}-1234-1234-1234-123456789abc",
                name=f"Station {index:02}",
                geo_lat=42.88 + index * 0.001,
                url_resolved=f"https://stream{index}.example/live",
            )
        )
    rows.append(dict(rows[0]))
    result = normalize_stations(
        list(reversed(rows)),
        state_name="New York",
        state_code="NY",
        position=(42.88, -78.87),
        resolver=_resolver,
    )
    assert len(result) == NEARBY_DIAL_LIMIT
    assert result[0].name == "Station 00"
    assert len({station.uuid for station in result}) == len(result)


def test_sanitizer_removes_control_characters_and_limits_length():
    assert sanitize_directory_text(" Hello\n\tworld\x00 " + "x" * 20, limit=12) == "Hello world"


@pytest.mark.parametrize("codec", ["MP3", "AAC", "AAC+", "OGG", "OPUS"])
def test_supported_codecs(codec):
    result = normalize_stations(
        [_row(codec=codec)],
        state_name="New York",
        state_code="NY",
        position=(42.88, -78.87),
        resolver=_resolver,
    )
    assert result and result[0].codec == codec
