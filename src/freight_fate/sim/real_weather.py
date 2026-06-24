"""Real-world weather via the Open-Meteo API (https://open-meteo.com).

Open-Meteo is free for non-commercial use and needs no API key. The provider
fetches current conditions for a city in a background thread and caches them,
so the game loop never blocks on the network. When a fetch fails or hasn't
landed yet, callers get ``None`` and the simulated weather carries on — the
game works identically offline.

WMO weather interpretation codes are mapped onto the game's
:class:`~freight_fate.sim.weather.WeatherKind` conditions.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Callable

from ..net import ssl_context
from .weather import WeatherKind

log = logging.getLogger(__name__)

API_URL = "https://api.open-meteo.com/v1/forecast"
FETCH_TIMEOUT_S = 8.0
CACHE_TTL_S = 15 * 60.0          # current weather is fresh enough for 15 min
RETRY_AFTER_S = 60.0             # wait before retrying a failed city
STRONG_WIND_KMH = 38.0

# WMO weather interpretation codes -> game weather.
# https://open-meteo.com/en/docs (weather_code documentation)
_WMO_MAP: dict[int, WeatherKind] = {
    0: WeatherKind.CLEAR,
    1: WeatherKind.CLEAR,
    2: WeatherKind.CLOUDY,
    3: WeatherKind.CLOUDY,
    45: WeatherKind.FOG,
    48: WeatherKind.FOG,
    51: WeatherKind.RAIN, 53: WeatherKind.RAIN, 55: WeatherKind.RAIN,
    56: WeatherKind.RAIN, 57: WeatherKind.RAIN,
    61: WeatherKind.RAIN, 63: WeatherKind.RAIN,
    65: WeatherKind.HEAVY_RAIN,
    66: WeatherKind.HEAVY_RAIN, 67: WeatherKind.HEAVY_RAIN,
    71: WeatherKind.SNOW, 73: WeatherKind.SNOW, 75: WeatherKind.SNOW,
    77: WeatherKind.SNOW,
    80: WeatherKind.RAIN, 81: WeatherKind.RAIN,
    82: WeatherKind.HEAVY_RAIN,
    85: WeatherKind.SNOW, 86: WeatherKind.SNOW,
    95: WeatherKind.THUNDERSTORM, 96: WeatherKind.THUNDERSTORM,
    99: WeatherKind.THUNDERSTORM,
}


def map_wmo(code: int, wind_kmh: float = 0.0) -> WeatherKind:
    """Map a WMO weather code (plus wind speed) to a game condition."""
    kind = _WMO_MAP.get(code, WeatherKind.CLOUDY)
    if kind in (WeatherKind.CLEAR, WeatherKind.CLOUDY) and wind_kmh >= STRONG_WIND_KMH:
        return WeatherKind.WIND
    return kind


def _default_fetch(lat: float, lon: float) -> tuple[int, float]:
    """Fetch (weather_code, wind_speed_kmh) from Open-Meteo. Raises on failure."""
    params = urllib.parse.urlencode({
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "current": "weather_code,wind_speed_10m",
        "wind_speed_unit": "kmh",
    })
    req = urllib.request.Request(
        f"{API_URL}?{params}",
        headers={"User-Agent": "FreightFate/1.1 (accessible trucking game)"},
    )
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S,
                                context=ssl_context()) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    current = data["current"]
    return int(current["weather_code"]), float(current.get("wind_speed_10m", 0.0))


class RealWeatherProvider:
    """Cached, non-blocking source of real current weather per city.

    ``request(city, lat, lon)`` kicks off a background fetch if needed;
    ``get(city)`` returns the last known :class:`WeatherKind` or ``None``.
    A custom ``fetch`` callable can be injected for tests.
    """

    def __init__(self, fetch: Callable[[float, float], tuple[int, float]] | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._fetch = fetch or _default_fetch
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[WeatherKind, float]] = {}
        self._failed_at: dict[str, float] = {}
        self._inflight: set[str] = set()

    def get(self, city: str) -> WeatherKind | None:
        with self._lock:
            entry = self._cache.get(city)
            if entry is None:
                return None
            kind, fetched_at = entry
            if self._clock() - fetched_at > CACHE_TTL_S * 2:
                return None  # too stale to trust
            return kind

    def unavailable(self, city: str) -> bool:
        """True when live data is not usable *and* a fetch has failed.

        Lets callers tell a still-loading first fetch (hold steady, no warm-up
        flicker) apart from a genuine offline state (fall back to simulated
        weather). False while a request is in flight or data is cached.
        """
        with self._lock:
            if city in self._cache or city in self._inflight:
                return False
            return city in self._failed_at

    def request(self, city: str, lat: float, lon: float) -> None:
        """Ensure fresh data for ``city`` is available or being fetched."""
        now = self._clock()
        with self._lock:
            if city in self._inflight:
                return
            entry = self._cache.get(city)
            if entry is not None and now - entry[1] < CACHE_TTL_S:
                return
            failed = self._failed_at.get(city)
            if failed is not None and now - failed < RETRY_AFTER_S:
                return
            self._inflight.add(city)
        thread = threading.Thread(target=self._worker, args=(city, lat, lon),
                                  name=f"weather-{city}", daemon=True)
        thread.start()

    def _worker(self, city: str, lat: float, lon: float) -> None:
        try:
            code, wind = self._fetch(lat, lon)
            kind = map_wmo(code, wind)
            with self._lock:
                self._cache[city] = (kind, self._clock())
                self._failed_at.pop(city, None)
            log.info("Real weather for %s: %s (WMO %s, wind %.0f km/h)",
                     city, kind.value, code, wind)
        except Exception:
            with self._lock:
                self._failed_at[city] = self._clock()
            log.warning("Real weather fetch failed for %s", city, exc_info=True)
        finally:
            with self._lock:
                self._inflight.discard(city)
