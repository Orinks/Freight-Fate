"""Truck parking availability via TPIMS (Truck Parking Information Management System).

Fetches real-time truck parking availability from state TPIMS APIs, which provide
live parking space counts at public and private truck stops. Wisconsin (511WI)
is the live implementation; Ohio (OHGO) keeps its keyless-era config on the
no_api bench until an API-key story exists. The architecture is designed for
easy addition of other TPIMS states (Kansas, Iowa, Minnesota, Missouri).

Like the real_weather and real_traffic systems, this is non-blocking with caching
and graceful fallback to static parking data when APIs are unavailable.
"""

from __future__ import annotations

import gzip
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

# TPIMS API endpoints for supported states
TPIMS_APIS = {
    # publicapi.ohgo.com's keyless v1 endpoints are gone (404, checked
    # 2026-08-09; the replacement API answers 401 without a registered key),
    # so Ohio sits on no_api until a key story exists.  The endpoint stays
    # listed for when it does.
    "ohio": {
        "base_url": "https://publicapi.ohgo.com",
        "parking_endpoint": "/v1/truck-parking",
        "name": "Ohio OHGO TPIMS",
        "parser": "no_api",
    },
    # 511wi.gov TPIMS sites (found 2026-08-09): live counts and site names
    # come from the list endpoint (POST /List/GetData/truckparking, a
    # DataTables-style form post), coordinates from the map icon layer
    # (GET /map/mapIcons/TruckParking); the parser joins the two by site id.
    "wisconsin": {
        "base_url": "https://511wi.gov",
        "parking_endpoint": "/List/GetData/truckparking",
        "icons_endpoint": "/map/mapIcons/TruckParking",
        "name": "Wisconsin 511WI TPIMS",
        "parser": "wi511",
    },
    # Future TPIMS states can be added here:
    # "kansas": {"base_url": "https://...", "parking_endpoint": "...", "name": "Kansas TPIMS"},
}

# Cache settings
FETCH_TIMEOUT_S = 8.0
CACHE_TTL_S = 5 * 60.0  # 5 minutes - parking changes moderately frequently
STALE_AFTER_S = 30 * 60.0  # Serve stale data for 30 minutes if fetches fail
RETRY_AFTER_S = 120.0  # Wait 2 minutes before retrying failed state


@dataclass(frozen=True)
class TruckParkingLocation:
    """A truck parking location with availability data."""

    id: str
    name: str
    location: str  # Road or intersection description
    address: str | None = None
    description: str | None = None
    capacity: int | None = None
    available: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    open: bool = True
    last_reported: str | None = None

    @property
    def occupancy_percentage(self) -> float | None:
        """Calculate occupancy percentage if capacity and available are known."""
        if self.capacity is None or self.available is None:
            return None
        if self.capacity == 0:
            return None
        return ((self.capacity - self.available) / self.capacity) * 100

    @property
    def availability_status(self) -> str:
        """Get human-readable availability status."""
        if not self.open:
            return "closed"
        if self.available is None:
            return "unknown"
        if self.available == 0:
            return "full"
        if self.occupancy_percentage is not None and self.occupancy_percentage > 90:
            return "almost_full"
        if self.occupancy_percentage is not None and self.occupancy_percentage > 75:
            return "mostly_full"
        return "available"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "address": self.address,
            "description": self.description,
            "capacity": self.capacity,
            "available": self.available,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "open": self.open,
            "last_reported": self.last_reported,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TruckParkingLocation | None:
        try:
            if not data or not isinstance(data, dict):
                return None

            location_id = str(data.get("id", ""))
            if not location_id:
                return None

            return cls(
                id=location_id,
                name=str(data.get("name", "")),
                location=str(data.get("location", "")),
                address=data.get("address"),
                description=data.get("description"),
                capacity=int(data["capacity"]) if data.get("capacity") else None,
                available=int(data.get("reportedAvailable") or data.get("available"))
                if data.get("reportedAvailable") or data.get("available")
                else None,
                latitude=float(data["latitude"]) if data.get("latitude") else None,
                longitude=float(data["longitude"]) if data.get("longitude") else None,
                open=bool(data.get("open", True)),
                last_reported=data.get("lastReported"),
            )
        except (TypeError, ValueError, KeyError):
            return None


@dataclass
class ParkingData:
    """Current truck parking availability for a state or region."""

    state: str
    locations: list[TruckParkingLocation]
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
            "locations": [loc.to_dict() for loc in self.locations],
            "last_updated": self.last_updated,
            "cache_time": self.cache_time,
            "source": self.source,
        }


class TruckParkingProvider:
    """Cached, non-blocking source of real-time truck parking data per state.

    ``request(state)`` kicks off a background fetch for the specified state.
    The current cached data (possibly stale or empty) is returned immediately
    so the game never blocks on network I/O.
    """

    def __init__(self) -> None:
        self._cache: dict[str, ParkingData] = {}
        self._failed_until: dict[str, float] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._default_user_agent = "FreightFate/1.1 (accessible trucking game; https://orinks.net)"

    def _get_lock(self, state: str) -> threading.Lock:
        """Get or create a lock for the specified state."""
        if state not in self._locks:
            self._locks[state] = threading.Lock()
        return self._locks[state]

    def request(self, state: str) -> ParkingData:
        """Request parking data for a state, returning cached data immediately.

        Spawns a background fetch if the cache is stale or empty. Returns the
        current cache entry (which may be empty on first request).
        """
        # Normalize state key
        state_key = state.lower().strip()
        if state_key not in TPIMS_APIS:
            log.warning(f"State {state} not supported for truck parking data")
            return ParkingData(
                state=state_key, locations=[], last_updated=0, cache_time=0, source="unsupported"
            )

        # Check if we're in a retry cooldown period
        if state_key in self._failed_until and time.time() < self._failed_until[state_key]:
            log.debug(f"State {state} in retry cooldown, using cached data")
            return self._cache.get(state_key, self._empty_data(state_key))

        # Check cache freshness
        cached = self._cache.get(state_key)
        if cached and cached.is_fresh():
            return cached

        # no_api: never fetch, but honour any (test-seeded) cache entry
        if TPIMS_APIS[state_key].get("parser") == "no_api":
            return cached if cached else self._empty_data(state_key)

        # Spawn background fetch
        self._fetch_background(state_key)

        # Return current cache (possibly stale or empty)
        return cached if cached else self._empty_data(state_key)

    def _empty_data(self, state: str) -> ParkingData:
        """Create an empty parking data object for a state."""
        return ParkingData(state=state, locations=[], last_updated=0, cache_time=0, source="empty")

    def _fetch_background(self, state: str) -> None:
        """Spawn a background thread to fetch parking data."""

        def fetch():
            try:
                data = self._fetch_from_api(state)
                with self._get_lock(state):
                    self._cache[state] = data
                    self._failed_until.pop(state, None)  # Clear retry cooldown
            except Exception as e:
                log.warning(f"Failed to fetch parking data for {state}: {e}")
                with self._get_lock(state):
                    self._failed_until[state] = time.time() + RETRY_AFTER_S

        thread = threading.Thread(target=fetch, daemon=True)
        thread.start()

    def _fetch_from_api(self, state: str) -> ParkingData:
        """Fetch parking data from the state's TPIMS API."""
        api_config = TPIMS_APIS[state]
        base_url = api_config["base_url"]
        parking_endpoint = api_config["parking_endpoint"]

        if api_config.get("parser") == "wi511":
            locations = self._fetch_wi511_locations(state)
        else:
            url = f"{base_url}{parking_endpoint}"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self._default_user_agent,
                    "Accept": "application/json",
                },
            )

            with urllib.request.urlopen(
                req, timeout=FETCH_TIMEOUT_S, context=ssl_context()
            ) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            locations = self._parse_locations(data, state)
        return ParkingData(
            state=state,
            locations=locations,
            last_updated=time.time(),
            cache_time=time.time(),
            source=api_config["name"],
        )

    def _fetch_wi511_locations(self, state: str) -> list[TruckParkingLocation]:
        """Fetch and join the two 511wi.gov TPIMS endpoints.

        The list endpoint is a DataTables-style form post that returns site
        names and live counts but no coordinates; the map icon layer returns
        the coordinates keyed by the same site ids.
        """
        api_config = TPIMS_APIS[state]
        base_url = api_config["base_url"]

        list_req = urllib.request.Request(
            f"{base_url}{api_config['parking_endpoint']}",
            data=urllib.parse.urlencode(
                {"draw": 1, "start": 0, "length": 500, "lang": "en"}
            ).encode("ascii"),
            headers={
                "User-Agent": self._default_user_agent,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(
            list_req, timeout=FETCH_TIMEOUT_S, context=ssl_context()
        ) as resp:
            list_data = self._read_json_body(resp)

        icons_req = urllib.request.Request(
            f"{base_url}{api_config['icons_endpoint']}",
            headers={
                "User-Agent": self._default_user_agent,
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(
            icons_req, timeout=FETCH_TIMEOUT_S, context=ssl_context()
        ) as resp:
            icons_data = self._read_json_body(resp)

        return self._parse_wi511_locations(list_data, icons_data)

    def _read_json_body(self, resp) -> dict:
        """Read a JSON response body, gunzipping when the server compresses.

        511wi.gov gzips the map icon layer even without Accept-Encoding."""
        body = resp.read()
        if body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)
        return json.loads(body.decode("utf-8"))

    def _parse_wi511_locations(
        self, list_data: dict, icons_data: dict
    ) -> list[TruckParkingLocation]:
        """Join 511wi.gov list rows with map icon coordinates by site id."""
        coords: dict[str, tuple[float, float]] = {}
        icon_items = icons_data.get("item2", []) if isinstance(icons_data, dict) else []
        if isinstance(icon_items, list):
            for item in icon_items:
                if not isinstance(item, dict):
                    continue
                location = item.get("location")
                if not (isinstance(location, list) and len(location) >= 2):
                    continue
                try:
                    coords[str(item.get("itemId", ""))] = (
                        float(location[0]),
                        float(location[1]),
                    )
                except (TypeError, ValueError):
                    continue

        locations: list[TruckParkingLocation] = []
        rows = list_data.get("data", []) if isinstance(list_data, dict) else []
        if not isinstance(rows, list):
            return locations
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                location_id = str(row.get("DT_RowId", "") or "")
                if not location_id:
                    continue
                latitude, longitude = coords.get(location_id, (None, None))
                capacity = row.get("totalParkingSpaces")
                available = row.get("availableParkingSpaces")
                locations.append(
                    TruckParkingLocation(
                        id=location_id,
                        name=str(row.get("name", "")),
                        location=str(row.get("roadway", "")),
                        capacity=int(capacity) if capacity is not None else None,
                        available=int(available) if available is not None else None,
                        latitude=latitude,
                        longitude=longitude,
                        open=str(row.get("open", "Yes")).lower() != "no",
                        last_reported=row.get("lastUpdated"),
                    )
                )
            except (TypeError, ValueError, KeyError) as e:
                log.debug(f"Failed to parse WI truck parking row: {e}")
                continue
        return locations

    def _parse_locations(self, data: dict, state: str) -> list[TruckParkingLocation]:
        """Parse parking locations from API response.

        This is a reference implementation for Ohio OHGO TPIMS. Other states will
        need their own parsers as API formats vary.
        """
        locations = []

        # Ohio OHGO TPIMS format parsing
        if "truckParking" in data:
            for location_data in data["truckParking"]:
                try:
                    location = TruckParkingLocation.from_dict(location_data)
                    if location:
                        locations.append(location)
                except Exception as e:
                    log.debug(f"Failed to parse parking location: {e}")
                    continue

        return locations

    def get_locations_near(
        self, state: str, latitude: float, longitude: float, radius_mi: float = 50.0
    ) -> list[TruckParkingLocation]:
        """Get parking locations within a specified radius of a point."""
        parking_data = self.request(state)
        nearby_locations = []

        for location in parking_data.locations:
            if location.latitude is None or location.longitude is None:
                continue

            # Simple distance calculation (approximate)
            distance = self._haversine_distance(
                latitude, longitude, location.latitude, location.longitude
            )
            if distance <= radius_mi:
                nearby_locations.append(location)

        return nearby_locations

    def get_available_locations_near(
        self, state: str, latitude: float, longitude: float, radius_mi: float = 50.0
    ) -> list[TruckParkingLocation]:
        """Get available parking locations within a specified radius of a point.

        Filters for locations that are open and have available spaces.
        """
        all_nearby = self.get_locations_near(state, latitude, longitude, radius_mi)
        return [
            loc
            for loc in all_nearby
            if loc.open and loc.available is not None and loc.available > 0
        ]

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
    "TPIMS_APIS",
    "TruckParkingLocation",
    "ParkingData",
    "TruckParkingProvider",
]
