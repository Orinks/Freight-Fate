"""Cached, asynchronous nearby-radio discovery using approximate location."""

from __future__ import annotations

import json
import math
import os
import queue
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from .net import ssl_context
from .radio_browser import (
    USER_AGENT,
    DirectoryStation,
    RadioBrowserClient,
    filter_cached_stations,
    normalize_stations,
    sanitize_directory_text,
)

LOCATION_MODE_REAL = "real"
LOCATION_MODE_TRUCK = "truck"
LOCATION_MODES = (LOCATION_MODE_REAL, LOCATION_MODE_TRUCK)
LOCATION_ENDPOINT = (
    "https://ipwho.is/?fields=success,country_code,region,region_code,city,latitude,longitude"
)
LOCATION_TIMEOUT_S = 4.0
CACHE_TTL_S = 24 * 60 * 60
CACHE_DIR_NAME = "radio_cache"


@dataclass(frozen=True)
class ApproximateLocation:
    lat: float
    lon: float
    city: str
    state: str
    state_code: str
    country_code: str = "US"
    source: str = LOCATION_MODE_REAL

    @property
    def position(self) -> tuple[float, float]:
        return (self.lat, self.lon)

    @property
    def label(self) -> str:
        place = ", ".join(part for part in (self.city, self.state) if part)
        if self.source == LOCATION_MODE_TRUCK:
            return f"the simulated truck near {place}" if place else "the simulated truck"
        return f"your approximate location near {place}" if place else "your approximate location"


@dataclass(frozen=True)
class DiscoveryResult:
    generation: int
    key: str
    explicit: bool
    stations: tuple[DirectoryStation, ...]
    location: ApproximateLocation
    outcome: str
    used_truck_fallback: bool = False
    error: str = ""


@dataclass(frozen=True)
class _CacheValue:
    saved_at: float
    value: object

    def fresh(self, now: float) -> bool:
        return now - self.saved_at < CACHE_TTL_S


class ApproximateLocationProvider:
    """No-key, HTTPS approximate IP location with bounded requests."""

    def __init__(self, *, opener=urllib.request.urlopen, timeout: float = LOCATION_TIMEOUT_S):
        self._opener = opener
        self.timeout = timeout

    def lookup(self) -> ApproximateLocation:
        request = urllib.request.Request(
            LOCATION_ENDPOINT,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        try:
            with self._opener(request, timeout=self.timeout, context=ssl_context()) as response:
                value = json.loads(response.read().decode("utf-8"))
        except (OSError, UnicodeError, ValueError, urllib.error.URLError) as exc:
            raise ConnectionError("approximate location lookup failed") from exc
        if not isinstance(value, dict) or value.get("success") is not True:
            raise ValueError("approximate location response failed")
        if sanitize_directory_text(value.get("country_code"), limit=4).upper() != "US":
            raise ValueError("approximate location is outside the US")
        try:
            lat = float(value["latitude"])
            lon = float(value["longitude"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("approximate location has no coordinates") from exc
        if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90):
            raise ValueError("approximate location coordinates are invalid")
        if not -180 <= lon <= 180:
            raise ValueError("approximate location coordinates are invalid")
        state = sanitize_directory_text(value.get("region"), limit=60)
        state_code = sanitize_directory_text(value.get("region_code"), limit=8).upper()
        if not state or not re.fullmatch(r"[A-Z]{2}", state_code):
            raise ValueError("approximate location has no US state")
        return ApproximateLocation(
            lat=lat,
            lon=lon,
            city=sanitize_directory_text(value.get("city"), limit=60),
            state=state,
            state_code=state_code,
        )


class RadioDiscoveryCache:
    def __init__(self, directory: Path | None = None) -> None:
        if directory is None:
            from .models.profile import data_dir

            directory = data_dir() / CACHE_DIR_NAME
        self.directory = directory

    def _read(self, path: Path) -> _CacheValue | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return _CacheValue(float(value["saved_at"]), value["value"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _write(self, path: Path, value: object, *, now: float) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(f".{os.getpid()}.tmp")
            temp.write_text(
                json.dumps({"saved_at": now, "value": value}, ensure_ascii=False),
                encoding="utf-8",
            )
            temp.replace(path)
        except OSError:
            return

    def load_location(self) -> _CacheValue | None:
        return self._read(self.directory / "location.json")

    def save_location(self, location: ApproximateLocation, *, now: float) -> None:
        self._write(self.directory / "location.json", asdict(location), now=now)

    def load_state(self, state_code: str) -> _CacheValue | None:
        safe = re.sub(r"[^A-Z0-9-]", "", state_code.upper()) or "unknown"
        return self._read(self.directory / f"stations-{safe}.json")

    def save_state(
        self,
        state_code: str,
        stations: tuple[DirectoryStation, ...],
        *,
        now: float,
    ) -> None:
        safe = re.sub(r"[^A-Z0-9-]", "", state_code.upper()) or "unknown"
        self._write(
            self.directory / f"stations-{safe}.json",
            [station.to_cache() for station in stations],
            now=now,
        )


def _cached_location(value: _CacheValue | None) -> ApproximateLocation | None:
    if value is None or not isinstance(value.value, dict):
        return None
    try:
        return ApproximateLocation(**value.value)
    except (TypeError, ValueError):
        return None


def _cached_stations(value: _CacheValue | None) -> tuple[DirectoryStation, ...]:
    if value is None or not isinstance(value.value, list):
        return ()
    stations = []
    for row in value.value:
        if not isinstance(row, dict):
            continue
        try:
            stations.append(DirectoryStation.from_cache(row))
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(stations)


class RadioDiscoveryManager:
    """Workers perform network I/O; the driving thread polls immutable results."""

    def __init__(
        self,
        *,
        location_provider: ApproximateLocationProvider | None = None,
        directory_client: RadioBrowserClient | None = None,
        cache: RadioDiscoveryCache | None = None,
        clock=time.time,
    ) -> None:
        self.location_provider = location_provider or ApproximateLocationProvider()
        self.directory_client = directory_client or RadioBrowserClient()
        self.cache = cache or RadioDiscoveryCache()
        self.clock = clock
        self._generation = 0
        self._active: set[int] = set()
        self._latest_key = ""
        self._results: queue.SimpleQueue[DiscoveryResult] = queue.SimpleQueue()
        self._lock = threading.Lock()

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._generation in self._active

    def cancel(self) -> None:
        with self._lock:
            self._generation += 1
            self._latest_key = ""

    def request(
        self,
        *,
        mode: str,
        truck_location: ApproximateLocation,
        market_key: str,
        explicit: bool,
        force: bool = False,
    ) -> str:
        mode = mode if mode in LOCATION_MODES else LOCATION_MODE_REAL
        key = f"{mode}:{market_key}"
        with self._lock:
            if self._generation in self._active and key == self._latest_key:
                return "already"
            self._generation += 1
            generation = self._generation
            self._latest_key = key
            self._active.add(generation)
        thread = threading.Thread(
            target=self._worker,
            args=(generation, key, mode, truck_location, explicit, force),
            name=f"radio-discovery-{generation}",
            daemon=True,
        )
        thread.start()
        return "started"

    def _worker(
        self,
        generation: int,
        key: str,
        mode: str,
        truck_location: ApproximateLocation,
        explicit: bool,
        force: bool,
    ) -> None:
        now = self.clock()
        used_truck_fallback = False
        location_cache = self.cache.load_location()
        cached_real = _cached_location(location_cache)
        location = truck_location
        if mode == LOCATION_MODE_REAL:
            if cached_real is not None and location_cache is not None and location_cache.fresh(now):
                location = cached_real
            else:
                try:
                    location = self.location_provider.lookup()
                    self.cache.save_location(location, now=now)
                except (OSError, TypeError, ValueError, ConnectionError):
                    if cached_real is not None:
                        location = cached_real
                    else:
                        location = truck_location
                        used_truck_fallback = True

        state_cache = self.cache.load_state(location.state_code)
        cached = _cached_stations(state_cache)
        if state_cache is not None and state_cache.fresh(now) and not force:
            stations = filter_cached_stations(cached, position=location.position)
            result = DiscoveryResult(
                generation,
                key,
                explicit,
                stations,
                location,
                "cached" if stations else "empty",
                used_truck_fallback,
            )
            self._finish(result)
            return

        try:
            rows, _host = self.directory_client.stations_for_state(location.state)
            state_stations = normalize_stations(
                rows,
                state_name=location.state,
                state_code=location.state_code,
                position=location.position,
                distance_cap_miles=5000.0,
                limit=300,
            )
            self.cache.save_state(location.state_code, state_stations, now=now)
            stations = filter_cached_stations(state_stations, position=location.position)
            outcome = "updated" if stations else "empty"
            result = DiscoveryResult(
                generation,
                key,
                explicit,
                stations,
                location,
                outcome,
                used_truck_fallback,
            )
        except (OSError, TypeError, ValueError, ConnectionError):
            stations = filter_cached_stations(cached, position=location.position)
            result = DiscoveryResult(
                generation,
                key,
                explicit,
                stations,
                location,
                "stale" if stations else "failed",
                used_truck_fallback,
                "directory unavailable",
            )
        self._finish(result)

    def _finish(self, result: DiscoveryResult) -> None:
        with self._lock:
            self._active.discard(result.generation)
        self._results.put(result)

    def poll(self) -> DiscoveryResult | None:
        latest = None
        while True:
            try:
                candidate = self._results.get_nowait()
            except queue.Empty:
                break
            with self._lock:
                current = (
                    candidate.generation == self._generation and candidate.key == self._latest_key
                )
            if current:
                latest = candidate
        return latest

    def record_click(self, station_uuid: str) -> None:
        threading.Thread(
            target=self._record_click,
            args=(station_uuid,),
            name="radio-browser-click",
            daemon=True,
        ).start()

    def _record_click(self, station_uuid: str) -> None:
        try:
            self.directory_client.record_click(station_uuid)
        except (OSError, TypeError, ValueError, ConnectionError):
            return
