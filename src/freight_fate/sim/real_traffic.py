"""Real-time traffic data via state 511 APIs.

Fetches current traffic conditions, construction zones, and incidents from
state department of transportation APIs, with graceful fallback to simulated
traffic when APIs are unavailable.  Response parsing lives in
``real_traffic_parsers``; this module owns the endpoint registry, caching,
and background fetching.

Parsers (full format notes in ``real_traffic_parsers``):
  ``ohgo``   — Ohio OHGO native JSON format.
  ``iteris`` — Shared Iteris/INRIX-platform ``/Events`` endpoint format
               (no active states; kept for the shared helpers).
  ``wzdx``   — Work Zone Data Exchange standard (GeoJSON FeatureCollection),
               camelCase and v4.x snake_case ``core_details`` layouts.
  ``cars``   — Castle Rock CARS GraphQL platform (``POST /api/graphql``).
  ``list511`` — The 511 sites' own list-page JSON (``POST
               /List/GetData/<layer>``) joined with the map-pin locations
               (``GET /map/mapIcons/<layer>``).  Fills the incident gap on
               WZDx-only sites; keyless.
  ``no_api`` — Stub for states without a working public 511 API.  Returns
               empty data so the simulation falls back to procedurally
               generated construction zones without log warnings.

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
from .real_traffic_list511 import List511Parsers
from .real_traffic_parsers import TrafficEvent, TrafficEventParsers

log = logging.getLogger(__name__)

# API endpoints for all 50 US states.
#
# ``parser`` selects the response format handler:
#   "ohgo"    — Ohio OHGO native JSON format
#   "iteris"  — Iteris/INRIX-platform 511 websites (shared ``/Events`` format)
#   "wzdx"    — Work Zone Data Exchange (GeoJSON FeatureCollection)
#   "cars"    — Castle Rock CARS GraphQL platform.  ``events_endpoint`` and
#                ``construction_endpoint`` hold the deployment's layer slug
#                for each fetch (slugs vary per site), and ``bounds`` is the
#                statewide "south,west,north,east" query box.
#   "list511" — The 511 site's own list JSON.  ``events_endpoint`` holds the
#                list layer name (e.g. "Incidents"); text rides
#                POST /List/GetData/<layer> and coordinates come from
#                GET /map/mapIcons/<layer>, joined on the event id.
#   "no_api"  — No working public 511 API.  Returns empty data so the
#                simulation falls back to procedurally generated construction
#                zones without log warnings.
#
# ``construction_parser`` (optional) overrides ``parser`` for the
# construction fetch only, for sites whose incidents and work zones live on
# different platforms (Florida and New York: list511 incidents + WZDx zones).
#
# States with no working public 511 API are listed with ``parser: "no_api"`` so
# the coverage is explicit: unsupported states still return empty data gracefully.
# The whole registry was live-swept 2026-08-09; per-state notes below.
STATE_APIS: dict[str, dict[str, str]] = {
    # ── OHGO ──────────────────────────────────────────────────────────────
    # publicapi.ohgo.com's keyless v1 endpoints are gone (404) and the
    # current API answers 401 without a registered key (checked 2026-08-09).
    # no_api keeps Ohio silently on simulated traffic until a key story
    # exists; the endpoints stay listed for when it does.
    "ohio": {
        "base_url": "https://publicapi.ohgo.com",
        "events_endpoint": "/v1/incidents",
        "construction_endpoint": "/v1/construction",
        "name": "Ohio OHGO",
        "parser": "no_api",
    },
    # ── Castle Rock CARS GraphQL platform ────────────────────────────────
    # These sites serve their SPA shell for every REST path; the data rides
    # POST /api/graphql (MapFeatures query, verified live 2026-08-09).
    "indiana": {
        "base_url": "https://511in.org",
        "events_endpoint": "incidents",
        "construction_endpoint": "construction",
        "bounds": "37.7,-88.2,41.9,-84.6",
        "name": "Indiana 511IN",
        "parser": "cars",
    },
    "minnesota": {
        "base_url": "https://511mn.org",
        "events_endpoint": "incidents",
        "construction_endpoint": "workZones",
        "bounds": "43.4,-97.3,49.4,-89.4",
        "name": "Minnesota 511MN",
        "parser": "cars",
    },
    "colorado": {
        "base_url": "https://www.cotrip.org",
        "events_endpoint": "roadReports",
        "construction_endpoint": "roadWork",
        "bounds": "36.9,-109.1,41.1,-102.0",
        "name": "Colorado COtrip",
        "parser": "cars",
    },
    # ── WZDx standard (GeoJSON FeatureCollection) ────────────────────────
    # The old per-site /api/events endpoints are gone everywhere, but these
    # sites publish a live WZDx v4.x work-zone feed at /api/wzdx (verified
    # 2026-08-09), so both fetches read it; incidents simply don't appear.
    # Florida and New York (below) keep their WZDx work zones but now pull
    # incidents from the list511 endpoints instead.
    "arizona": {
        "base_url": "https://az511.com",
        "events_endpoint": "/api/wzdx",
        "construction_endpoint": "/api/wzdx",
        "name": "Arizona AZ511",
        "parser": "wzdx",
    },
    "connecticut": {
        "base_url": "https://ctroads.org",
        "events_endpoint": "/api/wzdx",
        "construction_endpoint": "/api/wzdx",
        "name": "Connecticut CTroads",
        "parser": "wzdx",
    },
    # ── list511: incidents from the site's list JSON, zones from WZDx ────
    # fl511.com and 511ny.org publish work zones at /api/wzdx but no
    # incidents there.  Their own list pages ride an open DataTables-style
    # JSON endpoint (POST /List/GetData/<layer>) carrying the full incident
    # text, and /map/mapIcons/<layer> supplies id -> [lat, lon] for the map
    # pins; the two join on the event id.  Both fetched keyless 2026-08-20:
    # FL 22 incidents, NY 105 incidents, shape {"recordsTotal": N,
    # "data": [{id, roadwayName, description, severity, isFullClosure,
    # laneDescription, county, ...}]}.  (Each site also documents a
    # developer API, but that one requires a registered key.)
    "florida": {
        "base_url": "https://fl511.com",
        "events_endpoint": "Incidents",
        "construction_endpoint": "/api/wzdx",
        "name": "Florida FL511",
        "parser": "list511",
        "construction_parser": "wzdx",
    },
    "georgia": {
        "base_url": "https://511ga.org",
        "events_endpoint": "/api/wzdx",
        "construction_endpoint": "/api/wzdx",
        "name": "Georgia 511GA",
        "parser": "wzdx",
    },
    "idaho": {
        "base_url": "https://511.idaho.gov",
        "events_endpoint": "/api/wzdx",
        "construction_endpoint": "/api/wzdx",
        "name": "Idaho 511",
        "parser": "wzdx",
    },
    "nevada": {
        "base_url": "https://nvroads.com",
        "events_endpoint": "/api/wzdx",
        "construction_endpoint": "/api/wzdx",
        "name": "Nevada NVRoads",
        "parser": "wzdx",
    },
    # See the florida note: same platform, verified keyless 2026-08-20.
    "new york": {
        "base_url": "https://511ny.org",
        "events_endpoint": "Incidents",
        "construction_endpoint": "/api/wzdx",
        "name": "New York 511NY",
        "parser": "list511",
        "construction_parser": "wzdx",
    },
    "north carolina": {
        "base_url": "https://drivenc.gov",
        "events_endpoint": "/api/wzdx",
        "construction_endpoint": "/api/wzdx",
        "name": "North Carolina DriveNC",
        "parser": "wzdx",
    },
    "pennsylvania": {
        "base_url": "https://511pa.com",
        "events_endpoint": "/api/wzdx",
        "construction_endpoint": "/api/wzdx",
        "name": "Pennsylvania 511PA",
        "parser": "wzdx",
    },
    "utah": {
        "base_url": "https://udottraffic.utah.gov",
        "events_endpoint": "/api/wzdx",
        "construction_endpoint": "/api/wzdx",
        "name": "Utah UDOT Traffic",
        "parser": "wzdx",
    },
    # 511wi.gov's old REST API is gone, but the site publishes a live WZDx
    # v4.2 feed at /api/wzdx (found 2026-08-09), so Wisconsin is back off
    # the no_api bench.
    "wisconsin": {
        "base_url": "https://511wi.gov",
        "events_endpoint": "/api/wzdx",
        "construction_endpoint": "/api/wzdx",
        "name": "Wisconsin 511WI",
        "parser": "wzdx",
    },
    # ── Dead APIs (live-swept 2026-08-09; fallback to simulated data) ────
    # california: 511.ca.gov no longer resolves in DNS; no statewide feed found.
    "california": {"name": "California Caltrans 511", "parser": "no_api"},
    # maryland: roads.maryland.gov 404s on /api/events and /api/wzdx.
    "maryland": {"name": "Maryland CHART", "parser": "no_api"},
    # michigan: michigan.gov/mdot answers 403 on every API-looking path.
    "michigan": {"name": "Michigan MDOT", "parser": "no_api"},
    # missouri: gatewayguide.com 404s on /api/events and /api/wzdx.
    "missouri": {"name": "Missouri Gateway Guide", "parser": "no_api"},
    # new jersey: 511nj.org fronts a WAF that answers 403 Access Denied.
    "new jersey": {"name": "New Jersey 511NJ", "parser": "no_api"},
    # oregon: tripcheck.com serves HTML for every path incl. the old
    # /WZDx_v4.json; TripCheck's real API requires a registered key.
    "oregon": {"name": "Oregon TripCheck", "parser": "no_api"},
    # tennessee: tnsmartway.com DNS is dead; smartway.tn.gov is an SPA with
    # no public JSON endpoint found.
    "tennessee": {"name": "Tennessee SmartWay", "parser": "no_api"},
    # texas: api.drivetexas.org answers 401 (key required) / HTML.
    "texas": {"name": "Texas DriveTexas", "parser": "no_api"},
    # virginia: 511virginia.org redirects to the 511.vdot.virginia.gov SPA;
    # no public JSON endpoint found.
    "virginia": {"name": "Virginia 511", "parser": "no_api"},
    # washington: wsdot.wa.gov's traveler API requires a registered access
    # code on every call.
    "washington": {"name": "Washington WSDOT", "parser": "no_api"},
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

# CARS GraphQL fetch shape.  Zoom 15 keeps the server from clustering the
# events (verified statewide against 511in.org: 484 uncollapsed events).
CARS_GRAPHQL_ENDPOINT = "/api/graphql"
CARS_GRAPHQL_ZOOM = 15
# list511 fetch shape.  The list endpoint is DataTables-style: it needs the
# paging fields and at least one column definition or it answers with an
# empty ``data`` array, and it caps a page at 100 rows regardless of the
# requested length (verified 2026-08-20 against 511ny.org: 107 incidents
# came back 100 + 7).  The page cap bounds a runaway feed, not a real state:
# the busiest live roster (NY) fits in two pages.
LIST511_LIST_ENDPOINT = "/List/GetData/{layer}"
LIST511_ICONS_ENDPOINT = "/map/mapIcons/{layer}"
LIST511_PAGE_LENGTH = 100
LIST511_MAX_PAGES = 10

CARS_MAP_FEATURES_QUERY = (
    "query MapFeatures($input: MapFeaturesArgs!) {"
    " mapFeaturesQuery(input: $input) {"
    " mapFeatures {"
    " bbox title tooltip uri"
    " features { id geometry properties }"
    " ... on Event { priority }"
    " __typename"
    " } error { message type } } }"
)


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


class RealTrafficProvider(TrafficEventParsers, List511Parsers):
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

        if state_key in self._failed_until and time.time() < self._failed_until[state_key]:
            log.debug(f"State {state} in retry cooldown, using cached data")
            return self._cache.get(state_key, self._empty_data(state_key))

        cached = self._cache.get(state_key)
        if cached and cached.is_fresh():
            return cached

        # no_api: never fetch, but honour any (test-seeded) cache entry
        if STATE_APIS[state_key].get("parser") == "no_api":
            return cached if cached else self._empty_data(state_key)

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

        if state_key in self._failed_until and time.time() < self._failed_until[state_key]:
            log.debug(f"State {state} in retry cooldown, using cached construction data")
            cached = self._cache.get(f"{state_key}:construction")
            return cached if cached else self._empty_data(state_key)

        cached = self._cache.get(f"{state_key}:construction")
        if cached and cached.is_fresh():
            return cached

        # no_api: never fetch, but honour any (test-seeded) cache entry
        if STATE_APIS[state_key].get("parser") == "no_api":
            return cached if cached else self._empty_data(state_key)

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
        """Fetch construction data from the state's construction endpoint.

        ``construction_parser`` overrides ``parser`` for states whose work
        zones live on a different platform than their incidents (the
        list511 states keep their WZDx work-zone feed)."""
        api_config = STATE_APIS[state]
        parser = api_config.get("construction_parser", api_config.get("parser", "ohgo"))

        if parser == "cars":
            events = self._fetch_cars_events(
                state, api_config["construction_endpoint"], construction=True
            )
        else:
            data = self._http_get_json(
                f"{api_config['base_url']}{api_config['construction_endpoint']}"
            )
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

    def _http_get_json(self, url: str) -> dict | list:
        """GET a JSON document with the standard headers and timeout."""
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self._default_user_agent,
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S, context=ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _fetch_cars_events(
        self, state: str, layer_slug: str, construction: bool
    ) -> list[TrafficEvent]:
        """Fetch one layer of events from a CARS GraphQL deployment.

        Issues the MapFeatures query over the state's bounding box for the
        given layer slug; the slug decides whether the batch parses as
        construction or incidents.
        """
        api_config = STATE_APIS[state]
        south, west, north, east = (float(v) for v in api_config["bounds"].split(","))
        payload = json.dumps(
            {
                "query": CARS_MAP_FEATURES_QUERY,
                "variables": {
                    "input": {
                        "north": north,
                        "south": south,
                        "east": east,
                        "west": west,
                        "zoom": CARS_GRAPHQL_ZOOM,
                        "layerSlugs": [layer_slug],
                    }
                },
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{api_config['base_url']}{CARS_GRAPHQL_ENDPOINT}",
            data=payload,
            headers={
                "User-Agent": self._default_user_agent,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S, context=ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return self._parse_cars_events(data, state, construction=construction)

    def _http_post_form_json(self, url: str, fields: dict[str, str]) -> dict | list:
        """POST a form-encoded body and decode the JSON response."""
        req = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(fields).encode("utf-8"),
            headers={
                "User-Agent": self._default_user_agent,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S, context=ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _fetch_list511_events(self, state: str, layer: str) -> list[TrafficEvent]:
        """Fetch one list layer from a list511 site and join in coordinates.

        Pages through ``POST /List/GetData/<layer>`` (the server caps a page
        at 100 rows), then reads ``GET /map/mapIcons/<layer>`` for the map
        pins' ``id -> [lat, lon]``.  A pin fetch failure degrades to events
        without coordinates rather than losing the batch; the distance
        filters simply skip those.
        """
        api_config = STATE_APIS[state]
        base = api_config["base_url"]

        rows: list[dict] = []
        for page in range(LIST511_MAX_PAGES):
            data = self._http_post_form_json(
                f"{base}{LIST511_LIST_ENDPOINT.format(layer=layer)}",
                {
                    "draw": str(page + 1),
                    "start": str(page * LIST511_PAGE_LENGTH),
                    "length": str(LIST511_PAGE_LENGTH),
                    "columns[0][data]": "description",
                    "columns[0][name]": "description",
                    "order[0][column]": "0",
                    "order[0][dir]": "asc",
                    "search[value]": "",
                    "search[regex]": "false",
                },
            )
            if not isinstance(data, dict):
                break
            page_rows = data.get("data")
            if not isinstance(page_rows, list) or not page_rows:
                break
            rows.extend(r for r in page_rows if isinstance(r, dict))
            try:
                total = int(data.get("recordsTotal", 0))
            except (TypeError, ValueError):
                total = 0
            if len(rows) >= total:
                break

        locations: dict[str, tuple[float, float]] = {}
        try:
            icons = self._http_get_json(f"{base}{LIST511_ICONS_ENDPOINT.format(layer=layer)}")
            locations = self._parse_list511_icon_locations(icons)
        except Exception as e:
            log.debug(f"list511 map pins unavailable for {state}/{layer}: {e}")

        return self._parse_list511_events(rows, locations, state)

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
        parser = api_config.get("parser", "ohgo")

        if parser == "cars":
            events = self._fetch_cars_events(
                state, api_config["events_endpoint"], construction=False
            )
        elif parser == "list511":
            events = self._fetch_list511_events(state, api_config["events_endpoint"])
        else:
            data = self._http_get_json(f"{api_config['base_url']}{api_config['events_endpoint']}")
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
