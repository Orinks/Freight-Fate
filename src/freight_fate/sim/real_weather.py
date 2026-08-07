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
:class:`~freight_fate.sim.weather.WeatherKind` conditions. Because the NWS
reports "Fog/Mist" or "Haze" for anything under about 7 miles of visibility --
ordinary muggy summer air -- the fog mapping is gated on the station's measured
visibility, so only genuinely low visibility becomes the game's fog.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from ..net import ssl_context
from .weather import WeatherKind

log = logging.getLogger(__name__)

API_ROOT = "https://api.weather.gov"
# NWS asks every client to identify itself; a contact URL is recommended.
USER_AGENT = "FreightFate/1.1 (accessible trucking game; https://orinks.net)"
FETCH_TIMEOUT_S = 8.0
# Refresh every 5 min -- about as fast as api.weather.gov's own response cache
# turns over, and quick enough to catch off-schedule SPECI observations.
CACHE_TTL_S = 5 * 60.0
STALE_AFTER_S = 30 * 60.0  # keep serving cached data this long if refreshes fail
RETRY_AFTER_S = 60.0  # wait before retrying a failed city
STRONG_WIND_KMH = 38.0
# The game's fog is a sub-half-mile, 40-mph event with fog horns, but NWS
# stations report "Fog/Mist" (METAR mist) or "Haze" for any visibility under
# about 7 miles -- conditions that can blanket a whole region for hours on a
# humid night. Only a measured visibility below this maps to the game's fog;
# hazier-but-drivable air reads as cloudy instead.
FOG_VISIBILITY_MI = 2.0

# Keyword groups for mapping NWS condition text onto game weather. Checked in
# priority order: the first group whose keyword appears in the text wins, so
# precipitation and storms beat plain cloud cover. NWS phrases are title-cased
# (e.g. "Chance Light Rain", "Patchy Fog"); matching is case-insensitive.
_CONDITION_RULES: tuple[tuple[WeatherKind, tuple[str, ...]], ...] = (
    (WeatherKind.THUNDERSTORM, ("thunder", "t-storm", "tstorm", "squall")),
    # Glaze conditions before snow and rain: "Freezing Rain" must land on ice,
    # not match the plain rain group below.
    (WeatherKind.ICE, ("freezing", "sleet", "ice", "icy", "glaze")),
    (
        WeatherKind.SNOW,
        ("snow", "flurr", "blizzard", "wintry", "frost"),
    ),
    (WeatherKind.HEAVY_RAIN, ("heavy rain", "heavy shower")),
    (WeatherKind.RAIN, ("rain", "shower", "drizzle", "spray")),
    (WeatherKind.FOG, ("fog", "mist", "haze", "smoke", "ash", "dust", "sand")),
    (WeatherKind.WIND, ("wind", "breez", "blust", "gale")),
    (WeatherKind.CLOUDY, ("cloud", "overcast")),
    (WeatherKind.CLEAR, ("clear", "sunny", "fair", "sun")),
)


def map_condition(
    text: str, wind_kmh: float = 0.0, visibility_mi: float | None = None
) -> WeatherKind:
    """Map an NWS condition phrase (plus wind and visibility) to a game condition.

    Unrecognized or empty text falls back to cloudy -- a safe neutral that the
    next fetch can refine. A fog-family phrase only becomes fog when the
    station's measured visibility is genuinely low (below
    :data:`FOG_VISIBILITY_MI`); with no measurement the text is trusted as-is.
    Strong wind promotes an otherwise clear or cloudy sky to high winds, but
    never overrides precipitation.
    """
    lowered = (text or "").lower()
    kind = WeatherKind.CLOUDY
    for candidate, keywords in _CONDITION_RULES:
        if any(word in lowered for word in keywords):
            kind = candidate
            break
    if kind is WeatherKind.FOG and visibility_mi is not None and visibility_mi >= FOG_VISIBILITY_MI:
        kind = WeatherKind.CLOUDY
    if kind in (WeatherKind.CLEAR, WeatherKind.CLOUDY) and wind_kmh >= STRONG_WIND_KMH:
        return WeatherKind.WIND
    return kind


def _get_json(url: str) -> dict:
    """Fetch and decode a JSON document from the NWS API. Raises on failure."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/geo+json",
        },
    )
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S, context=ssl_context()) as resp:
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
    if "m_s" in unit or "m/s" in unit:  # metres per second
        return value * 3.6
    if "mi_h" in unit or "mph" in unit:  # miles per hour
        return value * 1.609344
    return value  # already km/h (wmoUnit:km_h-1)


def _temp_to_c(temp: dict | None) -> float | None:
    """Convert an NWS temperature measurement to Celsius, or None when absent.

    NWS observations report Celsius (``wmoUnit:degC``); Fahrenheit is handled
    defensively in case a station ever reports it. A null value (the station
    has no current reading) yields None so callers fall back to the model."""
    if not temp or temp.get("value") is None:
        return None
    value = float(temp["value"])
    unit = str(temp.get("unitCode", ""))
    if "degF" in unit:
        return (value - 32.0) * 5.0 / 9.0
    return value  # degC (the NWS default)


def _visibility_to_mi(vis: dict | None) -> float | None:
    """Convert an NWS visibility measurement to statute miles, or None when
    absent -- the fog gate then falls back to trusting the condition text."""
    if not vis or vis.get("value") is None:
        return None
    value = float(vis["value"])
    unit = str(vis.get("unitCode", ""))
    if "km" in unit:
        return value / 1.609344
    return value / 1609.344  # metres (wmoUnit:m, the NWS default)


def _default_fetch(
    lat: float, lon: float
) -> tuple[str, float, float | None, float | None, float | None]:
    """Fetch (condition, wind, temperature, visibility, observation time)
    from NWS.

    The temperature and visibility are None when the station reports no
    current value. Raises on network failure."""
    obs_url = _resolve_station_obs_url(lat, lon)
    data = _get_json(obs_url)
    props = data["properties"]
    text = props.get("textDescription") or ""
    wind_kmh = _wind_to_kmh(props.get("windSpeed"))
    temp_c = _temp_to_c(props.get("temperature"))
    visibility_mi = _visibility_to_mi(props.get("visibility"))
    timestamp = props.get("timestamp")
    observed_at = None
    if timestamp:
        try:
            observed_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            log.warning("NWS observation carried an invalid timestamp: %r", timestamp)
    return text, wind_kmh, temp_c, visibility_mi, observed_at


@dataclass(frozen=True)
class _CachedObservation:
    kind: WeatherKind
    temperature_c: float | None
    fetched_at: float
    observed_at: float


class RealWeatherProvider:
    """Cached, non-blocking source of real current weather per city.

    ``request(city, lat, lon)`` kicks off a background fetch if needed;
    ``get(city)`` returns the last known :class:`WeatherKind` or ``None``.
    A custom ``fetch`` callable can be injected for tests.
    """

    def __init__(
        self,
        fetch: Callable[[float, float], tuple[str, float, float | None, float | None]]
        | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self._fetch = fetch or _default_fetch
        self._clock = clock
        self._wall_clock = wall_clock
        self._lock = threading.Lock()
        self._cache: dict[str, _CachedObservation] = {}
        self._failed_at: dict[str, float] = {}
        self._inflight: set[str] = set()

    def get(self, city: str) -> WeatherKind | None:
        with self._lock:
            entry = self._cache.get(city)
            if entry is None or not self._usable(entry):
                return None
            return entry.kind

    def get_temperature(self, city: str) -> float | None:
        """The last real observed temperature in Celsius, or None when there is
        no fresh reading -- still loading, offline, too stale, or the station
        omitted it. Callers fall back to the seasonal model on None."""
        with self._lock:
            entry = self._cache.get(city)
            if entry is None or not self._usable(entry):
                return None
            return entry.temperature_c

    def stale(self, city: str) -> bool:
        """Whether usable cached data is due for a network refresh.

        Refresh cadence follows when the response was fetched. The station's
        observation timestamp is reported separately and does not make a
        freshly fetched, still-usable response last-known.
        """
        with self._lock:
            entry = self._cache.get(city)
            return (
                entry is not None
                and self._usable(entry)
                and self._clock() - entry.fetched_at >= CACHE_TTL_S
            )

    def refreshing(self, city: str) -> bool:
        """Whether a network request for this location is actually in flight."""
        with self._lock:
            return city in self._inflight

    def observation_age_s(self, city: str) -> float | None:
        """Age of the cached station observation, separate from fetch activity."""
        with self._lock:
            entry = self._cache.get(city)
            if entry is None:
                return None
            return max(0.0, self._wall_clock() - entry.observed_at)

    def refresh_failed(self, city: str) -> bool:
        """Whether the most recent completed refresh attempt failed."""
        with self._lock:
            return city not in self._inflight and city in self._failed_at

    def _usable(self, entry: _CachedObservation) -> bool:
        return (
            self._clock() - entry.fetched_at <= STALE_AFTER_S
            and self._wall_clock() - entry.observed_at <= STALE_AFTER_S
        )

    def unavailable(self, city: str) -> bool:
        """True when live data is not usable *and* a fetch has failed.

        Lets callers tell a still-loading first fetch (hold steady, no warm-up
        flicker) apart from a genuine offline state (fall back to simulated
        weather). False while a request is in flight or data is cached.
        """
        with self._lock:
            if city in self._inflight:
                return False
            entry = self._cache.get(city)
            if entry is not None and self._usable(entry):
                return False
            return city in self._failed_at

    def request(self, city: str, lat: float, lon: float) -> None:
        """Ensure fresh data for ``city`` is available or being fetched."""
        now = self._clock()
        with self._lock:
            if city in self._inflight:
                return
            entry = self._cache.get(city)
            if entry is not None and self._usable(entry) and now - entry.fetched_at < CACHE_TTL_S:
                return
            failed = self._failed_at.get(city)
            if failed is not None and now - failed < RETRY_AFTER_S:
                return
            self._inflight.add(city)
        thread = threading.Thread(
            target=self._worker, args=(city, lat, lon), name=f"weather-{city}", daemon=True
        )
        thread.start()

    def _worker(self, city: str, lat: float, lon: float) -> None:
        try:
            fetched = self._fetch(lat, lon)
            text, wind, temp_c, visibility_mi = fetched[:4]
            observed_at = fetched[4] if len(fetched) > 4 else None
            if observed_at is None:
                observed_at = self._wall_clock()
            if self._wall_clock() - float(observed_at) > STALE_AFTER_S:
                raise ValueError("NWS observation is too old to use")
            kind = map_condition(text, wind, visibility_mi)
            with self._lock:
                self._cache[city] = _CachedObservation(
                    kind, temp_c, self._clock(), float(observed_at)
                )
                self._failed_at.pop(city, None)
            log.info(
                "Real weather for %s: %s (NWS %r, wind %.0f km/h, temp %s, vis %s)",
                city,
                kind.value,
                text,
                wind,
                f"{temp_c:.0f}C" if temp_c is not None else "n/a",
                f"{visibility_mi:.1f}mi" if visibility_mi is not None else "n/a",
            )
        except Exception:
            with self._lock:
                self._failed_at[city] = self._clock()
            log.warning("Real weather fetch failed for %s", city, exc_info=True)
        finally:
            with self._lock:
                self._inflight.discard(city)
