import json
import threading

import pytest

from freight_fate.radio_browser import DirectoryStation
from freight_fate.radio_discovery import (
    CACHE_TTL_S,
    ApproximateLocation,
    ApproximateLocationProvider,
    RadioDiscoveryCache,
    RadioDiscoveryManager,
)


def _location(source="real"):
    return ApproximateLocation(42.88, -78.87, "Buffalo", "New York", "NY", source=source)


def _station(uuid="12345678-1234-1234-1234-123456789abc"):
    return DirectoryStation(
        uuid,
        "KTEST",
        "community; MP3, 128 kilobits",
        "MP3",
        128,
        "https://1.1.1.1/live",
        42.9,
        -78.8,
        4.0,
        "New York",
    )


class _LocationProvider:
    def __init__(self, value=None, error=None):
        self.value = value or _location()
        self.error = error
        self.calls = 0

    def lookup(self):
        self.calls += 1
        if self.error:
            raise self.error
        return self.value


class _Directory:
    def __init__(self, rows=None, error=None, started=None, release=None):
        self.rows = rows if rows is not None else []
        self.error = error
        self.calls = []
        self.started = started
        self.release = release

    def stations_for_state(self, state):
        self.calls.append(state)
        if self.started:
            self.started.set()
        if self.release:
            assert self.release.wait(2)
        if self.error:
            raise self.error
        return self.rows, "mirror"

    def record_click(self, uuid):
        pass


def _row():
    return {
        "stationuuid": "12345678-1234-1234-1234-123456789abc",
        "name": "KTEST",
        "countrycode": "US",
        "state": "New York",
        "iso_3166_2": "US-NY",
        "lastcheckok": 1,
        "codec": "MP3",
        "bitrate": 128,
        "geo_lat": 42.9,
        "geo_long": -78.8,
        "url_resolved": "https://1.1.1.1/live",
        "tags": "community",
    }


def _poll_after(manager, event):
    assert event.wait(2)
    result = manager.poll()
    assert result is not None
    return result


class _LocationResponse:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.value).encode()


def test_approximate_location_provider_uses_no_key_and_normalizes_us_market():
    calls = []

    def opener(request, **kwargs):
        calls.append((request, kwargs))
        return _LocationResponse(
            {
                "success": True,
                "country_code": "US",
                "region": "New York",
                "region_code": "ny",
                "city": "Buffalo\n",
                "latitude": 42.88,
                "longitude": -78.87,
            }
        )

    location = ApproximateLocationProvider(opener=opener, timeout=1.5).lookup()
    assert location.city == "Buffalo"
    assert location.state_code == "NY"
    assert location.source == "real"
    request, kwargs = calls[0]
    assert "key=" not in request.full_url
    assert request.headers["User-agent"].startswith("Freight-Fate/")
    assert kwargs["timeout"] == 1.5


@pytest.mark.parametrize(
    "updates",
    [
        {"success": False},
        {"country_code": "CA"},
        {"region_code": "not-a-state"},
        {"latitude": float("nan")},
    ],
)
def test_approximate_location_provider_rejects_unusable_responses(updates):
    value = {
        "success": True,
        "country_code": "US",
        "region": "New York",
        "region_code": "NY",
        "city": "Buffalo",
        "latitude": 42.88,
        "longitude": -78.87,
    }
    value.update(updates)
    provider = ApproximateLocationProvider(opener=lambda *args, **kwargs: _LocationResponse(value))
    with pytest.raises((ValueError, ConnectionError)):
        provider.lookup()


def test_cache_ttl_uses_fresh_data_without_network(tmp_path, monkeypatch):
    cache = RadioDiscoveryCache(tmp_path)
    cache.save_location(_location(), now=100.0)
    cache.save_state("NY", (_station(),), now=100.0)
    directory = _Directory(error=AssertionError("network should not run"))
    manager = RadioDiscoveryManager(
        location_provider=_LocationProvider(error=AssertionError("location should not run")),
        directory_client=directory,
        cache=cache,
        clock=lambda: 100.0 + CACHE_TTL_S - 1,
    )
    done = threading.Event()
    original = manager._finish

    def finish(result):
        original(result)
        done.set()

    monkeypatch.setattr(manager, "_finish", finish)
    assert (
        manager.request(
            mode="real",
            truck_location=_location("truck"),
            market_key="Buffalo:NY",
            explicit=False,
        )
        == "started"
    )
    result = _poll_after(manager, done)
    assert result.outcome == "cached"
    assert result.stations[0].uuid == _station().uuid
    assert directory.calls == []


def test_stale_cache_is_used_when_refresh_fails(tmp_path, monkeypatch):
    cache = RadioDiscoveryCache(tmp_path)
    cache.save_location(_location(), now=1.0)
    cache.save_state("NY", (_station(),), now=1.0)
    manager = RadioDiscoveryManager(
        location_provider=_LocationProvider(error=ConnectionError()),
        directory_client=_Directory(error=ConnectionError()),
        cache=cache,
        clock=lambda: CACHE_TTL_S + 10,
    )
    done = threading.Event()
    original = manager._finish
    monkeypatch.setattr(manager, "_finish", lambda result: (original(result), done.set()))
    manager.request(
        mode="real",
        truck_location=_location("truck"),
        market_key="Buffalo:NY",
        explicit=True,
        force=True,
    )
    result = _poll_after(manager, done)
    assert result.outcome == "stale"
    assert result.stations
    assert not result.used_truck_fallback


def test_location_failure_falls_back_to_truck_without_blocking(tmp_path, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    manager = RadioDiscoveryManager(
        location_provider=_LocationProvider(error=ConnectionError()),
        directory_client=_Directory(rows=[], started=started, release=release),
        cache=RadioDiscoveryCache(tmp_path),
    )
    done = threading.Event()
    original = manager._finish
    monkeypatch.setattr(manager, "_finish", lambda result: (original(result), done.set()))
    assert (
        manager.request(
            mode="real",
            truck_location=_location("truck"),
            market_key="Buffalo:NY",
            explicit=True,
            force=True,
        )
        == "started"
    )
    assert started.wait(2), "request returned while worker continued in background"
    assert manager.busy
    release.set()
    result = _poll_after(manager, done)
    assert result.used_truck_fallback
    assert result.location.source == "truck"
    assert result.outcome == "empty"


def test_network_failure_without_cache_returns_clean_failure(tmp_path, monkeypatch):
    manager = RadioDiscoveryManager(
        location_provider=_LocationProvider(),
        directory_client=_Directory(error=ConnectionError()),
        cache=RadioDiscoveryCache(tmp_path),
    )
    done = threading.Event()
    original = manager._finish
    monkeypatch.setattr(manager, "_finish", lambda result: (original(result), done.set()))
    manager.request(
        mode="real",
        truck_location=_location("truck"),
        market_key="Buffalo:NY",
        explicit=True,
        force=True,
    )
    result = _poll_after(manager, done)
    assert result.outcome == "failed"
    assert result.stations == ()


def test_duplicate_request_is_coalesced_and_stale_generation_ignored(tmp_path, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    directory = _Directory(rows=[], started=started, release=release)
    manager = RadioDiscoveryManager(
        location_provider=_LocationProvider(),
        directory_client=directory,
        cache=RadioDiscoveryCache(tmp_path),
    )
    done = threading.Event()
    original = manager._finish
    monkeypatch.setattr(manager, "_finish", lambda result: (original(result), done.set()))
    kwargs = dict(
        mode="real",
        truck_location=_location("truck"),
        market_key="Buffalo:NY",
        explicit=True,
        force=True,
    )
    assert manager.request(**kwargs) == "started"
    assert started.wait(2)
    assert manager.request(**kwargs) == "already"
    manager.cancel()
    release.set()
    assert done.wait(2)
    assert manager.poll() is None
