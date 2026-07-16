"""Real-time traffic data via state 511 APIs.

Fetches current traffic conditions, construction zones, and incidents from
state department of transportation APIs. Currently supports Ohio (OHGO) as
the reference implementation, with the architecture designed for easy addition
of other state 511 APIs.

Like the real_weather system, this is non-blocking with caching and graceful
fallback to simulated traffic when APIs are unavailable.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from ..net import ssl_context

log = logging.getLogger(__name__)

# API endpoints for supported states
STATE_APIS = {
    "ohio": {
        "base_url": "https://publicapi.ohgo.com",
        "events_endpoint": "/v1/incidents",
        "construction_endpoint": "/v1/construction",
        "name": "Ohio OHGO",
    },
    # Future states can be added here:
    # "kansas": {"base_url": "https://www.kandrive.org", ...},
    # "wisconsin": {"base_url": "https://www.511wi.gov", ...},
}

# Cache settings
FETCH_TIMEOUT_S = 8.0
CACHE_TTL_S = 10 * 60.0  # 10 minutes - traffic changes faster than weather
STALE_AFTER_S = 30 * 60.0  # Serve stale data for 30 minutes if fetches fail
RETRY_AFTER_S = 120.0  # Wait 2 minutes before retrying failed state


@dataclass(frozen=True)
class TrafficEvent:
    """A traffic incident or construction event."""

    id: str
    event_type: str  # "incident", "construction", "weather"
    severity: str  # "low", "medium", "high"
    description: str
    county: str
    latitude: float | None = None
    longitude: float | None = None
    start_time: str | None = None
    estimated_end: str | None = None
    lanes_affected: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "severity": self.severity,
            "description": self.description,
            "county": self.county,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "start_time": self.start_time,
            "estimated_end": self.estimated_end,
            "lanes_affected": self.lanes_affected,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TrafficEvent | None:
        try:
            # Require at least basic identification
            if not data or not isinstance(data, dict):
                return None

            event_id = str(data.get("id", ""))
            if not event_id:
                return None

            return cls(
                id=event_id,
                event_type=str(data.get("event_type", "incident")),
                severity=str(data.get("severity", "low")),
                description=str(data.get("description", "")),
                county=str(data.get("county", "")),
                latitude=float(data["latitude"]) if data.get("latitude") else None,
                longitude=float(data["longitude"]) if data.get("longitude") else None,
                start_time=data.get("start_time"),
                estimated_end=data.get("estimated_end"),
                lanes_affected=data.get("lanes_affected"),
            )
        except (TypeError, ValueError, KeyError):
            return None


@dataclass
class TrafficData:
    """Current traffic conditions for a state or region."""

    state: str
    events: list[TrafficEvent]
    last_updated: float
    cache_time: float
    source: str = "api"

    def is_fresh(self) -> bool:
        """Check if data is still within cache TTL."""
        return time.time() - self.cache_time < CACHE_TTL_S

    def is_stale(self) -> bool:
        """Check if data is beyond stale threshold."""
        return time.time() - self.cache_time > STALE_AFTER_S

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "events": [event.to_dict() for event in self.events],
            "last_updated": self.last_updated,
            "cache_time": self.cache_time,
            "source": self.source,
        }


class RealTrafficProvider:
    """Cached, non-blocking source of real-time traffic data per state.

    ``request(state)`` kicks off a background fetch for the specified state.
    The current cached data (possibly stale or empty) is returned immediately
    so the game never blocks on network I/O.
    """

    def __init__(self) -> None:
        self._cache: dict[str, TrafficData] = {}
        self._failed_until: dict[str, float] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._default_user_agent = "FreightFate/1.1 (accessible trucking game; https://orinks.net)"

    def _get_lock(self, state: str) -> threading.Lock:
        """Get or create a lock for the specified state."""
        if state not in self._locks:
            self._locks[state] = threading.Lock()
        return self._locks[state]

    def request(self, state: str) -> TrafficData:
        """Request traffic data for a state, returning cached data immediately.

        Spawns a background fetch if the cache is stale or empty. Returns the
        current cache entry (which may be empty on first request).
        """
        # Normalize state key
        state_key = state.lower().strip()
        if state_key not in STATE_APIS:
            log.warning(f"State {state} not supported for real-time traffic")
            return TrafficData(
                state=state_key, events=[], last_updated=0, cache_time=0, source="unsupported"
            )

        # Check if we're in a retry cooldown period
        if state_key in self._failed_until and time.time() < self._failed_until[state_key]:
            log.debug(f"State {state} in retry cooldown, using cached data")
            return self._cache.get(state_key, self._empty_data(state_key))

        # Check cache freshness
        cached = self._cache.get(state_key)
        if cached and cached.is_fresh():
            return cached

        # Spawn background fetch
        self._fetch_background(state_key)

        # Return current cache (possibly stale or empty)
        return cached if cached else self._empty_data(state_key)

    def _empty_data(self, state: str) -> TrafficData:
        """Create an empty traffic data object for a state."""
        return TrafficData(state=state, events=[], last_updated=0, cache_time=0, source="empty")

    def _fetch_background(self, state: str) -> None:
        """Spawn a background thread to fetch traffic data."""

        def fetch():
            try:
                data = self._fetch_from_api(state)
                with self._get_lock(state):
                    self._cache[state] = data
                    self._failed_until.pop(state, None)  # Clear retry cooldown
            except Exception as e:
                log.warning(f"Failed to fetch traffic data for {state}: {e}")
                with self._get_lock(state):
                    self._failed_until[state] = time.time() + RETRY_AFTER_S

        thread = threading.Thread(target=fetch, daemon=True)
        thread.start()

    def _fetch_from_api(self, state: str) -> TrafficData:
        """Fetch traffic data from the state's API."""
        api_config = STATE_APIS[state]
        base_url = api_config["base_url"]
        events_endpoint = api_config["events_endpoint"]

        url = f"{base_url}{events_endpoint}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self._default_user_agent,
                "Accept": "application/json",
            },
        )

        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S, context=ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        events = self._parse_events(data, state)
        return TrafficData(
            state=state,
            events=events,
            last_updated=time.time(),
            cache_time=time.time(),
            source=api_config["name"],
        )

    def _parse_events(self, data: dict, state: str) -> list[TrafficEvent]:
        """Parse traffic events from API response.

        This is a reference implementation for Ohio OHGO. Other states will
        need their own parsers as API formats vary.
        """
        events = []

        # Ohio OHGO format parsing
        if "incidents" in data:
            for incident in data["incidents"]:
                try:
                    event = TrafficEvent(
                        id=str(incident.get("id", "")),
                        event_type="incident",
                        severity=self._map_severity(incident.get("severity", "low")),
                        description=str(incident.get("description", "")),
                        county=str(incident.get("county", "")),
                        latitude=float(incident["lat"]) if incident.get("lat") else None,
                        longitude=float(incident["lon"]) if incident.get("lon") else None,
                        start_time=incident.get("start_time"),
                        estimated_end=incident.get("estimated_end"),
                        lanes_affected=incident.get("lanes_affected"),
                    )
                    events.append(event)
                except (TypeError, ValueError, KeyError) as e:
                    log.debug(f"Failed to parse incident: {e}")
                    continue

        return events

    def _map_severity(self, api_severity: str) -> str:
        """Map API severity to our standard severity levels."""
        severity_map = {
            "low": "low",
            "minor": "low",
            "medium": "medium",
            "moderate": "medium",
            "high": "high",
            "major": "high",
            "severe": "high",
            "critical": "high",
        }
        return severity_map.get(api_severity.lower(), "low")

    def get_events_near(
        self, state: str, latitude: float, longitude: float, radius_mi: float = 50.0
    ) -> list[TrafficEvent]:
        """Get traffic events within a specified radius of a point.

        This is a simple distance filter. For production use, consider using
        proper geospatial queries.
        """
        traffic_data = self.request(state)
        nearby_events = []

        for event in traffic_data.events:
            if event.latitude is None or event.longitude is None:
                continue

            # Simple distance calculation (approximate)
            distance = self._haversine_distance(
                latitude, longitude, event.latitude, event.longitude
            )
            if distance <= radius_mi:
                nearby_events.append(event)

        return nearby_events

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate the great circle distance between two points in miles."""
        from math import asin, cos, radians, sin, sqrt

        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        r = 3956  # Earth's radius in miles

        return c * r


__all__ = [
    "STATE_APIS",
    "TrafficEvent",
    "TrafficData",
    "RealTrafficProvider",
]
