"""Real-time traffic data via state 511 APIs.

Fetches current traffic conditions, construction zones, and incidents from
state department of transportation APIs. Covers 30+ states across four API
formats with graceful fallback to simulated traffic when APIs are unavailable:

Parsers:
  ``ohgo``   — Ohio OHGO native JSON format (``/v1/construction``)
  ``iteris`` — Shared Iteris/INRIX-platform 511 websites that serve the
               ``/Events`` endpoint mixing incidents and construction.
               (AZ, CT, GA, NY, WI)
  ``wzdx``   — Work Zone Data Exchange v4.0 standard (GeoJSON FeatureCollection
               with namespaced properties).  Adopted by 18+ states.
  ``no_api`` — Stub for states without a known public 511 API.  Returns empty
               data so the simulation falls back to procedurally generated
               construction zones without log warnings.

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

# API endpoints for all 50 US states.
#
# ``parser`` selects the response format handler:
#   "ohgo"    — Ohio OHGO native JSON format
#   "iteris"  — Iteris/INRIX-platform 511 websites.  Uses the shared ``/Events``
#                endpoint format; the construction fetch filters by event type.
#   "wzdx"    — Work Zone Data Exchange v4.0 (GeoJSON FeatureCollection with
#                namespaced ``wzdx:`` properties).  Adopted by 18+ states.
#   "no_api"  — No known public 511 API.  Returns empty data so the simulation
#                falls back to procedurally generated construction zones without
#                log warnings.
#
# States with no known public 511 API are listed with ``parser: "no_api"`` so
# the coverage is explicit: unsupported states still return empty data gracefully.
STATE_APIS: dict[str, dict[str, str]] = {
    # ── OHGO ──────────────────────────────────────────────────────────────
    "ohio": {
        "base_url": "https://publicapi.ohgo.com",
        "events_endpoint": "/v1/incidents",
        "construction_endpoint": "/v1/construction",
        "name": "Ohio OHGO",
        "parser": "ohgo",
    },
    # ── Iteris platform ──────────────────────────────────────────────────
    "wisconsin": {
        "base_url": "https://511wi.gov",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/events",
        "name": "Wisconsin 511WI",
        "parser": "iteris",
    },
    "new york": {
        "base_url": "https://511ny.org",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/events",
        "name": "New York 511NY",
        "parser": "iteris",
    },
    "georgia": {
        "base_url": "https://511ga.org",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/events",
        "name": "Georgia 511GA",
        "parser": "iteris",
    },
    "arizona": {
        "base_url": "https://az511.com",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/events",
        "name": "Arizona AZ511",
        "parser": "iteris",
    },
    "connecticut": {
        "base_url": "https://ctroads.org",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/events",
        "name": "Connecticut CTroads",
        "parser": "iteris",
    },
    # ── WZDx standard (GeoJSON FeatureCollection) ────────────────────────
    "california": {
        "base_url": "https://511.ca.gov",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/wzdx",
        "name": "California Caltrans 511",
        "parser": "wzdx",
    },
    "colorado": {
        "base_url": "https://cotrip.org",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/wzdx",
        "name": "Colorado COtrip",
        "parser": "wzdx",
    },
    "florida": {
        "base_url": "https://fl511.com",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/wzdx",
        "name": "Florida FL511",
        "parser": "wzdx",
    },
    "idaho": {
        "base_url": "https://511.idaho.gov",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/wzdx",
        "name": "Idaho 511",
        "parser": "wzdx",
    },
    # 511in.org serves its SPA shell for every REST-looking path (checked
    # 2026-07-22: /api/events and /api/v2/get/event both return HTML); the
    # real data rides a GraphQL endpoint we have no client for yet. no_api
    # keeps Indiana silently on simulated traffic instead of warning-spamming
    # every fetch cycle.
    "indiana": {
        "base_url": "https://511in.org",
        "events_endpoint": "",
        "construction_endpoint": "",
        "name": "Indiana 511IN",
        "parser": "no_api",
    },
    "maryland": {
        "base_url": "https://roads.maryland.gov",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/wzdx",
        "name": "Maryland CHART",
        "parser": "wzdx",
    },
    "michigan": {
        "base_url": "https://michigan.gov/mdot",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/wzdx",
        "name": "Michigan MDOT",
        "parser": "wzdx",
    },
    "minnesota": {
        "base_url": "https://511mn.org",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/wzdx",
        "name": "Minnesota 511MN",
        "parser": "wzdx",
    },
    "missouri": {
        "base_url": "https://gatewayguide.com",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/wzdx",
        "name": "Missouri Gateway Guide",
        "parser": "wzdx",
    },
    "nevada": {
        "base_url": "https://nvroads.com",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/wzdx",
        "name": "Nevada NVRoads",
        "parser": "wzdx",
    },
    "new jersey": {
        "base_url": "https://511nj.org",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/wzdx",
        "name": "New Jersey 511NJ",
        "parser": "wzdx",
    },
    "north carolina": {
        "base_url": "https://drivenc.gov",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/wzdx",
        "name": "North Carolina DriveNC",
        "parser": "wzdx",
    },
    "oregon": {
        "base_url": "https://tripcheck.com",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/WZDx_v4.json",
        "name": "Oregon TripCheck",
        "parser": "wzdx",
    },
    "pennsylvania": {
        "base_url": "https://511pa.com",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/wzdx",
        "name": "Pennsylvania 511PA",
        "parser": "wzdx",
    },
    "tennessee": {
        "base_url": "https://tnsmartway.com",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/wzdx",
        "name": "Tennessee SmartWay",
        "parser": "wzdx",
    },
    "texas": {
        "base_url": "https://api.drivetexas.org",
        "events_endpoint": "/v1/incidents",
        "construction_endpoint": "/api/wzdx",
        "name": "Texas DriveTexas",
        "parser": "wzdx",
    },
    "utah": {
        "base_url": "https://udottraffic.utah.gov",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/wzdx",
        "name": "Utah UDOT Traffic",
        "parser": "wzdx",
    },
    "virginia": {
        "base_url": "https://511virginia.org",
        "events_endpoint": "/api/events",
        "construction_endpoint": "/api/wzdx",
        "name": "Virginia 511",
        "parser": "wzdx",
    },
    "washington": {
        "base_url": "https://wsdot.wa.gov",
        "events_endpoint": "/api/traffic",
        "construction_endpoint": "/api/wzdx",
        "name": "Washington WSDOT",
        "parser": "wzdx",
    },
    # ── No known public 511 API (fallback to simulated data) ─────────────
    "alabama": {"name": "Alabama", "parser": "no_api"},
    "alaska": {"name": "Alaska", "parser": "no_api"},
    "arkansas": {"name": "Arkansas", "parser": "no_api"},
    "delaware": {"name": "Delaware", "parser": "no_api"},
    "hawaii": {"name": "Hawaii", "parser": "no_api"},
    "illinois": {"name": "Illinois", "parser": "no_api"},
    "iowa": {"name": "Iowa", "parser": "no_api"},
    "kansas": {"name": "Kansas", "parser": "no_api"},
    "kentucky": {"name": "Kentucky", "parser": "no_api"},
    "louisiana": {"name": "Louisiana", "parser": "no_api"},
    "maine": {"name": "Maine", "parser": "no_api"},
    "massachusetts": {"name": "Massachusetts", "parser": "no_api"},
    "mississippi": {"name": "Mississippi", "parser": "no_api"},
    "montana": {"name": "Montana", "parser": "no_api"},
    "nebraska": {"name": "Nebraska", "parser": "no_api"},
    "new hampshire": {"name": "New Hampshire", "parser": "no_api"},
    "new mexico": {"name": "New Mexico", "parser": "no_api"},
    "north dakota": {"name": "North Dakota", "parser": "no_api"},
    "oklahoma": {"name": "Oklahoma", "parser": "no_api"},
    "rhode island": {"name": "Rhode Island", "parser": "no_api"},
    "south carolina": {"name": "South Carolina", "parser": "no_api"},
    "south dakota": {"name": "South Dakota", "parser": "no_api"},
    "vermont": {"name": "Vermont", "parser": "no_api"},
    "west virginia": {"name": "West Virginia", "parser": "no_api"},
    "wyoming": {"name": "Wyoming", "parser": "no_api"},
    # DC is not a state but is a distinct region on the map
    "district of columbia": {"name": "District of Columbia", "parser": "no_api"},
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
    road_name: str = ""  # highway/road name for construction events
    location_text: str = ""  # "near milepost 45" or "between exits 43 and 47"
    work_type: str = ""  # "construction", "maintenance", "utility", "bridge", "paving"
    closure: str = ""  # "alternating", "single lane", "shoulder", "full closure"

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
            "road_name": self.road_name,
            "location_text": self.location_text,
            "work_type": self.work_type,
            "closure": self.closure,
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
                road_name=str(data.get("road_name", "")),
                location_text=str(data.get("location_text", "")),
                work_type=str(data.get("work_type", "")),
                closure=str(data.get("closure", "")),
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
        state_key = state.lower().strip()
        if state_key not in STATE_APIS:
            log.debug(f"State {state} not in STATE_APIS, returning empty data")
            return self._empty_data(state_key)

        api_config = STATE_APIS[state_key]
        # no_api: return empty immediately, no fetch or warning
        if api_config.get("parser") == "no_api":
            return self._empty_data(state_key)

        if state_key in self._failed_until and time.time() < self._failed_until[state_key]:
            log.debug(f"State {state} in retry cooldown, using cached data")
            return self._cache.get(state_key, self._empty_data(state_key))

        cached = self._cache.get(state_key)
        if cached and cached.is_fresh():
            return cached

        self._fetch_background(state_key)
        return cached if cached else self._empty_data(state_key)

    def fetch_construction(self, state: str) -> TrafficData:
        """Request construction-specific data for a state.

        Returns cached data immediately; spawns a background fetch to the
        construction endpoint if stale. Like ``request()``, never blocks.
        """
        state_key = state.lower().strip()
        if state_key not in STATE_APIS:
            log.debug(f"State {state} not in STATE_APIS, returning empty data")
            return self._empty_data(state_key)

        api_config = STATE_APIS[state_key]
        # no_api: return empty immediately, no fetch or warning
        if api_config.get("parser") == "no_api":
            return self._empty_data(state_key)

        if state_key in self._failed_until and time.time() < self._failed_until[state_key]:
            log.debug(f"State {state} in retry cooldown, using cached construction data")
            cached = self._cache.get(f"{state_key}:construction")
            return cached if cached else self._empty_data(state_key)

        cached = self._cache.get(f"{state_key}:construction")
        if cached and cached.is_fresh():
            return cached

        self._fetch_construction_background(state_key)
        return cached if cached else self._empty_data(state_key)

    def _fetch_construction_background(self, state: str) -> None:
        """Spawn a background thread to fetch construction data."""

        def fetch():
            try:
                data = self._fetch_construction_from_api(state)
                with self._get_lock(state):
                    self._cache[f"{state}:construction"] = data
                    self._failed_until.pop(state, None)
            except Exception as e:
                log.warning(f"Failed to fetch construction data for {state}: {e}")
                with self._get_lock(state):
                    self._failed_until[state] = time.time() + RETRY_AFTER_S

        thread = threading.Thread(target=fetch, daemon=True)
        thread.start()

    def _fetch_construction_from_api(self, state: str) -> TrafficData:
        """Fetch construction data from the state's construction endpoint."""
        api_config = STATE_APIS[state]
        base_url = api_config["base_url"]
        construction_endpoint = api_config["construction_endpoint"]
        parser = api_config.get("parser", "ohgo")

        url = f"{base_url}{construction_endpoint}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self._default_user_agent,
                "Accept": "application/json",
            },
        )

        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S, context=ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if parser == "iteris":
            events = self._parse_iteris_construction_events(data, state)
        elif parser == "wzdx":
            events = self._parse_wzdx_construction_events(data, state)
        else:
            events = self._parse_construction_events(data, state)
        return TrafficData(
            state=state,
            events=events,
            last_updated=time.time(),
            cache_time=time.time(),
            source=api_config["name"],
        )

    def _parse_construction_events(self, data: dict, state: str) -> list[TrafficEvent]:
        """Parse construction work zone events from API response.

        This is the reference parser for Ohio OHGO. Iteris-platform states
        use ``_parse_iteris_construction_events`` instead.
        """
        events: list[TrafficEvent] = []

        raw_events = data.get("construction", data.get("events", data.get("results", [])))
        if isinstance(raw_events, dict):
            raw_events = [raw_events]
        if not isinstance(raw_events, list):
            return events

        for construction in raw_events:
            if not isinstance(construction, dict):
                continue
            try:
                event_id = str(construction.get("id", "") or "")
                if not event_id:
                    continue

                lat, lon = self._extract_construction_coordinates(construction)
                location_text = self._build_construction_location_text(construction)
                closure = self._determine_closure_type(construction)
                lanes = self._describe_lanes_affected(construction)
                work_type = self._classify_work_type(construction)
                severity = self._construction_severity(closure)

                road_name = str(construction.get("road", construction.get("route", "")))
                description = str(construction.get("description", construction.get("details", "")))
                county = str(construction.get("county", ""))
                start_time = str(construction.get("start_date", construction.get("start_time", "")))
                estimated_end = str(construction.get("end_date", construction.get("end_time", "")))

                event = TrafficEvent(
                    id=event_id,
                    event_type="construction",
                    severity=severity,
                    description=description,
                    county=county,
                    latitude=lat,
                    longitude=lon,
                    start_time=start_time,
                    estimated_end=estimated_end,
                    lanes_affected=lanes,
                    road_name=road_name,
                    location_text=location_text,
                    work_type=work_type,
                    closure=closure,
                )
                events.append(event)
            except (TypeError, ValueError, KeyError) as e:
                log.debug(f"Failed to parse construction event: {e}")
                continue

        return events

    # ---- Shared Iteris-platform parser ------------------------------------

    def _parse_iteris_events(self, data: dict | list, state: str) -> list[TrafficEvent]:
        """Parse general traffic incidents from an Iteris-platform API response.

        The Iteris platform (used by Wisconsin 511WI, New York 511NY, Georgia
        511GA, Arizona AZ511, and Connecticut CTroads) returns an array of
        event objects with ``id``, ``event_type``, ``severity``, ``headline``,
        ``location``, ``road_name``, and date fields.
        """
        events: list[TrafficEvent] = []

        raw = data if isinstance(data, list) else data.get("events", data.get("results", []))
        if isinstance(raw, dict):
            raw = [raw]
        if not isinstance(raw, list):
            return events

        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                event_id = str(item.get("id", item.get("event_id", "")))
                if not event_id:
                    continue

                # Determine event type (only incidents here)
                api_type = str(item.get("event_type", item.get("type", "incident"))).lower()
                event_type = (
                    "construction"
                    if api_type in ("construction", "roadwork", "work_zone")
                    else "incident"
                )

                # Coordinates: Iteris puts lat/lon in a sub-object or top-level fields
                lat, lon = self._parse_iteris_coordinates(item)

                # Severity
                severity = self._map_severity(str(item.get("severity", "low")))

                # Road name
                road_name = str(item.get("road_name", item.get("road", item.get("route", ""))))

                description = str(
                    item.get("headline", item.get("description", item.get("event_text", "")))
                )
                county = str(item.get("county", item.get("region", "")))
                start_time = str(item.get("start_date", item.get("start_time", "")))
                estimated_end = str(item.get("end_date", item.get("end_time", "")))
                lanes = str(item.get("lanes_affected", item.get("lanes", "")))

                event = TrafficEvent(
                    id=event_id,
                    event_type=event_type,
                    severity=severity,
                    description=description,
                    county=county,
                    latitude=lat,
                    longitude=lon,
                    start_time=start_time,
                    estimated_end=estimated_end,
                    lanes_affected=lanes,
                    road_name=road_name,
                )
                events.append(event)
            except (TypeError, ValueError, KeyError) as e:
                log.debug(f"Failed to parse Iteris event: {e}")
                continue

        return events

    def _parse_iteris_construction_events(
        self, data: dict | list, state: str
    ) -> list[TrafficEvent]:
        """Parse construction work-zone events from an Iteris-platform API.

        The Iteris-platform ``/Events`` endpoint mixes incidents and
        construction events.  This parser filters to construction-type events
        only, then applies the same enrichment helpers
        (``_determine_closure_type``, ``_classify_work_type``, …) used by the
        Ohio parser so downstream zone conversion behaves identically.
        """
        all_events = self._parse_iteris_events(data, state)

        construction_events: list[TrafficEvent] = []
        for event in all_events:
            if event.event_type != "construction":
                continue

            # Re-parse with construction-specific enrichment
            # We need the raw dict item again for richer field access.
            raw = data if isinstance(data, list) else data.get("events", data.get("results", []))
            if isinstance(raw, dict):
                raw = [raw]
            if not isinstance(raw, list):
                continue

            matching = [
                r
                for r in raw
                if isinstance(r, dict) and str(r.get("id", r.get("event_id", ""))) == event.id
            ]
            if not matching:
                log.debug(f"No raw Iteris item for event {event.id}, appending unenriched")
                construction_events.append(event)
                continue

            item = matching[0]

            # Enrich with construction-specific fields using the shared helpers
            location_text = self._build_iteris_location_text(item)
            closure = self._determine_iteris_closure(item, event.description)
            lanes = self._describe_lanes_affected(item)  # Uses the same logic
            work_type = self._classify_work_type(item)
            severity = self._construction_severity(closure)

            enriched = TrafficEvent(
                id=event.id,
                event_type="construction",
                severity=severity,
                description=event.description,
                county=event.county,
                latitude=event.latitude,
                longitude=event.longitude,
                start_time=event.start_time,
                estimated_end=event.estimated_end,
                lanes_affected=lanes or event.lanes_affected or "",
                road_name=event.road_name,
                location_text=location_text,
                work_type=work_type,
                closure=closure,
            )
            construction_events.append(enriched)

        return construction_events

    def _parse_iteris_coordinates(self, item: dict) -> tuple[float | None, float | None]:
        """Extract coordinates from an Iteris-platform event.

        Iteris puts ``lat``/``lon`` directly on the object, or inside a
        ``location`` sub-object."""
        # Direct top-level fields
        lat = item.get("lat", item.get("latitude"))
        lon = item.get("lon", item.get("lng", item.get("longitude")))
        if lat is not None and lon is not None:
            try:
                return float(lat), float(lon)
            except (TypeError, ValueError):
                pass

        # Sub-object (location: {lat: ..., lon: ...})
        loc = item.get("location", {})
        if isinstance(loc, dict):
            lat = loc.get("lat", loc.get("latitude"))
            lon = loc.get("lon", loc.get("lng", loc.get("longitude")))
            if lat is not None and lon is not None:
                try:
                    return float(lat), float(lon)
                except (TypeError, ValueError):
                    pass

        return None, None

    def _build_iteris_location_text(self, item: dict) -> str:
        """Build a location description from Iteris fields."""
        # Direct location text
        text = str(item.get("location_text", item.get("location", "")))
        if text:
            return text

        # Cross streets / intersection
        cross = item.get("cross_street", "")
        if cross:
            return f"At {cross}"

        # Milepost / mile range
        start = item.get("start_milepost", item.get("milepost", ""))
        end = item.get("end_milepost", "")
        if start and end:
            return f"Between milepost {start} and {end}"
        if start:
            return f"Near milepost {start}"

        return ""

    def _determine_iteris_closure(self, item: dict, description: str) -> str:
        """Determine closure type from Iteris fields."""
        # Direct field
        closure = str(item.get("closure", item.get("closure_type", ""))).lower()
        if closure:
            return closure

        # Check the description for closure keywords
        desc = description.lower()
        if any(w in desc for w in ("full closure", "road closed", "detour")):
            return "full closure"
        if any(w in desc for w in ("alternating", "flag", "one-way")):
            return "alternating"
        if "shoulder" in desc:
            return "shoulder"
        if any(w in desc for w in ("lane closure", "right lane", "left lane")):
            return "single lane"

        return "single lane"

    # ---- WZDx v4.0 standard parser (GeoJSON FeatureCollection) ----------

    def _parse_wzdx_events(self, data: dict | list, state: str) -> list[TrafficEvent]:
        """Parse incidents from a WZDx v4.0 GeoJSON FeatureCollection.

        The WZDx standard (Work Zone Data Exchange) is a USDOT-specified format
        used by 18+ states.  Responses are GeoJSON FeatureCollections where
        each feature's ``properties`` carry ``wzdx:``-namespaced keys
        (``wzdx:roadName``, ``wzdx:vehicleImpact``, …).  Some implementations
        omit the namespace prefix.
        """
        events: list[TrafficEvent] = []

        features = data
        if isinstance(data, dict):
            # GeoJSON FeatureCollection
            features = data.get("features", data.get("events", data.get("results", [])))
            if isinstance(features, dict):
                features = [features]
        if not isinstance(features, list):
            return events

        for feature in features:
            if not isinstance(feature, dict):
                continue
            try:
                event_id = str(feature.get("id", feature.get("feature_id", "")))
                if not event_id:
                    continue

                # Extract coordinates from GeoJSON Point geometry
                lat, lon = self._extract_wzdx_coordinates(feature)

                # Properties may be namespaced (wzdx:roadName) or flat (roadName)
                props = feature.get("properties", feature)
                if not isinstance(props, dict):
                    props = feature

                road_name = self._wzdx_prop(props, "roadName", "")
                event_type = self._wzdx_prop(props, "workZoneType", "construction").lower()
                # Normalize to our standard types
                if event_type in ("construction", "maintenance", "bridge", "paving"):
                    mapped_type = "construction"
                else:
                    mapped_type = "incident"

                description = self._wzdx_prop(props, "description", "") or self._wzdx_prop(
                    props, "workZoneName", ""
                )
                county = self._wzdx_prop(props, "county", "")
                start_time = self._wzdx_prop(props, "startDate", "")
                estimated_end = self._wzdx_prop(props, "endDate", "")

                # Vehicle impact → closure type
                vehicle_impact = self._wzdx_prop(props, "vehicleImpact", "").lower()
                closure = self._wzdx_impact_to_closure(vehicle_impact)
                severity = self._construction_severity(closure)

                # Lane info
                lanes = self._wzdx_prop(props, "lanesAffected", "")
                if not lanes:
                    lanes = self._describe_lanes_affected({"closure": closure})

                # Location text
                location_text = self._build_wzdx_location_text(props)

                event = TrafficEvent(
                    id=event_id,
                    event_type=mapped_type,
                    severity=severity,
                    description=description,
                    county=county,
                    latitude=lat,
                    longitude=lon,
                    start_time=start_time,
                    estimated_end=estimated_end,
                    lanes_affected=lanes,
                    road_name=road_name,
                    location_text=location_text,
                    closure=closure,
                    work_type="construction",
                )
                events.append(event)
            except (TypeError, ValueError, KeyError) as e:
                log.debug(f"Failed to parse WZDx feature: {e}")
                continue

        return events

    def _parse_wzdx_construction_events(self, data: dict | list, state: str) -> list[TrafficEvent]:
        """Parse construction work-zone events from a WZDx feed.

        Most WZDx feeds are construction-specific (the standard is designed for
        work zones), but we still filter to ``event_type == 'construction'``
        for safety.
        """
        all_events = self._parse_wzdx_events(data, state)
        return [e for e in all_events if e.event_type == "construction"]

    def _extract_wzdx_coordinates(self, feature: dict) -> tuple[float | None, float | None]:
        """Extract lat/lon from a WZDx GeoJSON feature."""
        # Point geometry: {"type": "Point", "coordinates": [lon, lat]}
        geometry = feature.get("geometry", {})
        if isinstance(geometry, dict):
            coords = geometry.get("coordinates")
            if isinstance(coords, list) and len(coords) >= 2:
                try:
                    return float(coords[1]), float(coords[0])  # [lon, lat]
                except (TypeError, ValueError):
                    pass
            # LineString: take the midpoint
            if (
                geometry.get("type") == "LineString"
                and isinstance(coords, list)
                and len(coords) > 0
            ):
                mid = coords[len(coords) // 2]
                if isinstance(mid, list) and len(mid) >= 2:
                    try:
                        return float(mid[1]), float(mid[0])
                    except (TypeError, ValueError):
                        pass

        # Fall back to properties lat/lon (uncommon but possible)
        props = feature.get("properties", {})
        if isinstance(props, dict):
            lat = props.get("lat", props.get("latitude"))
            lon = props.get("lon", props.get("lng", props.get("longitude")))
            if lat is not None and lon is not None:
                try:
                    return float(lat), float(lon)
                except (TypeError, ValueError):
                    pass

        return None, None

    def _wzdx_prop(self, props: dict, key: str, default: str) -> str:
        """Read a WZDx property, trying both namespaced and flat keys."""
        # Try with namespace first
        value = props.get(f"wzdx:{key}", props.get(key, default))
        if value is None:
            return default
        return str(value)

    def _wzdx_impact_to_closure(self, impact: str) -> str:
        """Map WZDx vehicleImpact enum to closure type string."""
        mapping = {
            "all-lanes-closed": "full closure",
            "some-lanes-closed": "single lane",
            "shoulder-closed": "shoulder",
            "alternating-one-way": "alternating",
            "flow-of-traffic": "single lane",
            "no-impact": "single lane",
            "": "single lane",
        }
        return mapping.get(impact, "single lane")

    def _build_wzdx_location_text(self, props: dict) -> str:
        """Build a location description from WZDx properties."""
        loc = self._wzdx_prop(props, "locationDescription", "")
        if loc:
            return loc

        begin = self._wzdx_prop(props, "beginningMilepost", "")
        end = self._wzdx_prop(props, "endingMilepost", "")
        if begin and end:
            return f"Between milepost {begin} and {end}"
        if begin:
            return f"Near milepost {begin}"

        return ""

    def _extract_construction_coordinates(
        self, construction: dict
    ) -> tuple[float | None, float | None]:
        """Extract lat/lon from a construction event, handling various API formats."""
        # Direct lat/lon fields (OHGO format)
        lat = construction.get("lat", construction.get("latitude"))
        lon = construction.get("lon", construction.get("lng", construction.get("longitude")))
        if lat is not None and lon is not None:
            try:
                return float(lat), float(lon)
            except (TypeError, ValueError):
                pass

        # Geometry object with coordinates array (GeoJSON format used by some 511 APIs)
        geometry = construction.get("geometry", {})
        if isinstance(geometry, dict):
            coords = geometry.get("coordinates")
            if isinstance(coords, list) and len(coords) >= 2:
                try:
                    return float(coords[1]), float(coords[0])  # [lon, lat] GeoJSON convention
                except (TypeError, ValueError):
                    pass

        # Start/end point objects
        start_point = construction.get("start_point", {})
        end_point = construction.get("end_point", {})
        for point in (start_point, end_point):
            slat = point.get("lat", point.get("latitude"))
            slon = point.get("lon", point.get("lng", point.get("longitude")))
            if slat is not None and slon is not None:
                try:
                    return float(slat), float(slon)
                except (TypeError, ValueError):
                    pass

        return None, None

    def _build_construction_location_text(self, construction: dict) -> str:
        """Build a human-readable location reference from construction data."""
        # Direct location text field
        text = str(construction.get("location", construction.get("location_text", "")))
        if text:
            return text

        # Milepost range
        start_mile = construction.get("start_milepost", construction.get("beg_mm", ""))
        end_mile = construction.get("end_milepost", construction.get("end_mm", ""))
        if start_mile and end_mile:
            return f"Between milepost {start_mile} and {end_mile}"
        if start_mile:
            return f"Near milepost {start_mile}"

        # Street/intersection reference
        cross = construction.get("cross_street", construction.get("intersection", ""))
        if cross:
            return f"At {cross}"

        return ""

    def _determine_closure_type(self, construction: dict) -> str:
        """Determine the type of lane or road closure."""
        # Direct closure field
        closure = str(construction.get("closure", construction.get("closure_type", ""))).lower()
        if closure:
            return closure

        # Look for closure keywords in description
        desc = str(construction.get("description", "")).lower()
        if "full closure" in desc or "road closed" in desc or "detour" in desc:
            return "full closure"
        if "alternating" in desc or "flag" in desc or "one-way" in desc:
            return "alternating"
        if "shoulder" in desc:
            return "shoulder"
        if "lane closure" in desc:
            return "single lane"

        # Default: implied lane restriction for construction
        return "single lane"

    def _describe_lanes_affected(self, construction: dict) -> str:
        """Build a description of which lanes are affected."""
        # Direct lanes affected field
        lanes = construction.get("lanes_affected", construction.get("lanes", ""))
        if lanes:
            return str(lanes)

        # Infer from closure type
        closure = self._determine_closure_type(construction)
        if closure == "full closure":
            return "all lanes closed"
        if closure == "alternating":
            return "alternating single lane"
        if closure == "shoulder":
            return "right shoulder closed"
        return "left lane closed"

    def _classify_work_type(self, construction: dict) -> str:
        """Classify the type of work being performed."""
        work_type = str(construction.get("work_type", construction.get("type", ""))).lower()
        if work_type:
            return work_type

        # Infer from description keywords
        desc = str(construction.get("description", "")).lower()
        if any(w in desc for w in ("bridge", "overpass", "structure")):
            return "bridge"
        if any(w in desc for w in ("pave", "paving", "resurface", "mill")):
            return "paving"
        if any(w in desc for w in ("utility", "pipe", "gas")):
            return "utility"
        if any(w in desc for w in ("inspect", "repair", "maintain")):
            return "maintenance"

        return "construction"

    def _construction_severity(self, closure: str) -> str:
        """Map construction closure type to severity."""
        if closure in ("full closure",):
            return "high"
        if closure in ("alternating", "single lane"):
            return "medium"
        return "low"

    def get_construction_near_route(
        self,
        state: str,
        route_points: list[tuple[float, float]],
        road_name: str | None = None,
        radius_mi: float = 3.0,
    ) -> list[TrafficEvent]:
        """Get construction events near a route's geometry.

        Filters construction events to those within ``radius_mi`` of any
        route point, and optionally matching the given road name.
        """
        construction_data = self.fetch_construction(state)
        if not construction_data or not construction_data.events:
            return []

        if not route_points:
            return []

        # Only consider construction-type events
        construction_events = [
            e for e in construction_data.events if e.event_type == "construction"
        ]
        if not construction_events:
            return []

        nearby: list[TrafficEvent] = []
        for event in construction_events:
            if event.latitude is None or event.longitude is None:
                continue

            # Check if this event is on the requested road
            if (
                road_name
                and event.road_name
                and not self._road_name_matches(event.road_name, road_name)
            ):
                continue

            # Check proximity to any route point
            for rlat, rlon in route_points:
                distance = self._haversine_distance(rlat, rlon, event.latitude, event.longitude)
                if distance <= radius_mi:
                    nearby.append(event)
                    break

        return nearby

    def _road_name_matches(self, api_road: str, route_road: str) -> bool:
        """Check if an API road name matches a route's highway designation.

        Handles formats like "I-77" vs "I 77" vs "Interstate 77" vs "77".
        """
        import re

        def normalize_road(r: str) -> str:
            r = r.strip().upper()
            # Remove spaces and dashes
            r = re.sub(r"[\s-]+", "", r)
            # Standardize prefixes
            if r.startswith("INTERSTATE"):
                r = "I" + r[10:]
            if r.startswith("US"):
                r = "US" + r[2:]
            return r

        return normalize_road(api_road) == normalize_road(route_road)

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
        parser = api_config.get("parser", "ohgo")

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

        if parser == "iteris":
            events = self._parse_iteris_events(data, state)
        elif parser == "wzdx":
            events = self._parse_wzdx_events(data, state)
        else:
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
