"""Real-world weather via the U.S. National Weather Service API
(https://api.weather.gov).

The NWS API is a free, public government service that needs no API key (it
only asks for an identifying ``User-Agent``). The provider resolves a city's
nearest observation station once, then fetches the latest observation in a
background thread and caches it, so the game loop never blocks on the network.
When a fetch fails or hasn't landed yet, callers get ``None`` and the simulated
weather carries on -- the game works identically offline.

The NWS only covers the United States and its territories, which is exactly the
game's map. Each observation's free-text condition (e.g. "Mostly Cloudy",
"Light Rain", "Fog") is mapped onto the game's
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

API_ROOT = "https://api.weather.gov"
# NWS asks every client to identify itself; a contact URL is recommended.
USER_AGENT = "FreightFate/1.1 (accessible trucking game; https://orinks.net)"
FETCH_TIMEOUT_S = 8.0
CACHE_TTL_S = 15 * 60.0          # current weather is fresh enough for 15 min
RETRY_AFTER_S = 60.0             # wait before retrying a failed city
STRONG_WIND_KMH = 38.0

# Keyword groups for mapping NWS condition text onto game weather. Checked in
# priority order: the first group whose keyword appears in the text wins, so
# precipitation and storms beat plain cloud cover. NWS phrases are title-cased
# (e.g. "Chance Light Rain", "Patchy Fog"); matching is case-insensitive.
_CONDITION_RULES: tuple[tuple[WeatherKind, tuple[str, ...]], ...] = (
    (WeatherKind.THUNDERSTORM, ("thunder", "t-storm", "tstorm", "squall")),
    (WeatherKind.SNOW, ("snow", "sleet", "flurr", "blizzard", "wintry",
                        "ice", "icy", "freezing", "frost")),
    (WeatherKind.HEAVY_RAIN, ("heavy rain", "heavy shower")),
    (WeatherKind.RAIN, ("rain", "shower", "drizzle", "spray")),
    (WeatherKind.FOG, ("fog", "mist", "haze", "smoke", "ash", "dust", "sand")),
    (WeatherKind.WIND, ("wind", "breez", "blust", "gale")),
    (WeatherKind.CLOUDY, ("cloud", "overcast")),
    (WeatherKind.CLEAR, ("clear", "sunny", "fair", "sun")),
)


def map_condition(text: str, wind_kmh: float = 0.0) -> WeatherKind:
    """Map an NWS condition phrase (plus wind speed) to a game condition.

    Unrecognized or empty text falls back to cloudy -- a safe neutral that the
    next fetch can refine. Strong wind promotes an otherwise clear or cloudy
    sky to high winds, but never overrides precipitation.
    """
    lowered = (text or "").lower()
    kind = WeatherKind.CLOUDY
    for candidate, keywords in _CONDITION_RULES:
        if any(word in lowered for word in keywords):
            kind = candidate
            break
    if kind in (WeatherKind.CLEAR, WeatherKind.CLOUDY) and wind_kmh >= STRONG_WIND_KMH:
        return WeatherKind.WIND
    return kind


def _get_json(url: str) -> dict:
    """Fetch and decode a JSON document from the NWS API. Raises on failure."""
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json",
    })
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S,
                                context=ssl_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


# Resolving a city's nearest observation station is stable, so cache it across
# refreshes (keyed by coarse coordinates) to avoid repeating the two lookups.
_station_cache: dict[tuple[float, float], str] = {}
_station_lock = threading.Lock()


def _resolve_station_obs_url(lat: float, lon: float) -> str:
    """Return the 'latest observation' URL for the station nearest a point.

    Walks the NWS discovery chain: ``/points`` yields the station list URL, and
    that list yields the nearest station. The result is cached per location.
    """
    key = (round(lat, 2), round(lon, 2))
    with _station_lock:
        cached = _station_cache.get(key)
    if cached is not None:
        return cached

    point = _get_json(f"{API_ROOT}/points/{lat:.4f},{lon:.4f}")
    stations_url = point["properties"]["observationStations"]
    stations = _get_json(stations_url)
    station_urls = stations.get("observationStations") or []
    if not station_urls:
        raise ValueError(f"no observation stations near {lat:.4f},{lon:.4f}")
    obs_url = f"{station_urls[0]}/observations/latest"

    with _station_lock:
        _station_cache[key] = obs_url
    return obs_url


def _wind_to_kmh(wind: dict | None) -> float:
    """Convert an NWS windSpeed measurement to km/h, tolerating null values."""
    if not wind or wind.get("value") is None:
        return 0.0
    value = float(wind["value"])
    unit = str(wind.get("unitCode", ""))
    if "m_s" in unit or "m/s" in unit:        # metres per second
        return value * 3.6
    if "mi_h" in unit or "mph" in unit:       # miles per hour
        return value * 1.609344
    return value                              # already km/h (wmoUnit:km_h-1)


def _default_fetch(lat: float, lon: float) -> tuple[str, float]:
    """Fetch (condition_text, wind_speed_kmh) from NWS. Raises on failure."""
    obs_url = _resolve_station_obs_url(lat, lon)
    data = _get_json(obs_url)
    props = data["properties"]
    text = props.get("textDescription") or ""
    wind_kmh = _wind_to_kmh(props.get("windSpeed"))
    return text, wind_kmh


class RealWeatherProvider:
    """Cached, non-blocking source of real current weather per city.

    ``request(city, lat, lon)`` kicks off a background fetch if needed;
    ``get(city)`` returns the last known :class:`WeatherKind` or ``None``.
    A custom ``fetch`` callable can be injected for tests.
    """

    def __init__(self, fetch: Callable[[float, float], tuple[str, float]] | None = None,
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
            text, wind = self._fetch(lat, lon)
            kind = map_condition(text, wind)
            with self._lock:
                self._cache[city] = (kind, self._clock())
                self._failed_at.pop(city, None)
            log.info("Real weather for %s: %s (NWS %r, wind %.0f km/h)",
                     city, kind.value, text, wind)
        except Exception:
            with self._lock:
                self._failed_at[city] = self._clock()
            log.warning("Real weather fetch failed for %s", city, exc_info=True)
        finally:
            with self._lock:
                self._inflight.discard(city)
