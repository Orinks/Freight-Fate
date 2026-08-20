# ruff: noqa: F403,F405
"""World model: cities, freight locations, and the highway network.

Loads indexed world data and exposes a graph with Dijkstra-based route finding.
Route options are produced by re-running the search with already-used legs
penalized, giving genuinely different alternatives (fastest vs. detour).
"""

from __future__ import annotations

import heapq
import json
import threading
from pathlib import Path

from .legacy_aliases import LEGACY_CITY_SLUGS
from .world_constants import *
from .world_corridor import raw_metadata_complete
from .world_loader import load_world_data
from .world_local_data import (
    load_city_service_data,
    load_facility_approaches,
    load_facility_endpoints,
    load_local_approaches,
    load_local_geometries,
)
from .world_models import *
from .world_parsing import (
    _expand_market_locations,
    _is_legacy_market_name,
    _market_tags_for_city,
    _merge_overlay,
    _parse_location,
    _parse_stop,
    _service_city_slug,
    _stable_facility_id,
)
from .world_parsing import (
    minimum_curated_pois as minimum_curated_pois,
)
from .world_parsing import (
    minimum_fuel_capable_pois as minimum_fuel_capable_pois,
)
from .world_services import WorldServiceMixin

WORLD_DATA_PATH = Path(__file__).parent / "world_data"
WORLD_INDEX_PATH = WORLD_DATA_PATH / "index.json"
# Alternate routes should feel like dispatch choices, not graph leftovers.
ALTERNATE_ROUTE_EXTRA_RATIO = 0.22
ALTERNATE_ROUTE_MIN_EXTRA_MILES = 75.0
ALTERNATE_ROUTE_MAX_EXTRA_MILES = 550.0


def _load_base_world_data(root: Path) -> dict:
    """Read the base world, preferring the baked-in module in frozen builds.

    Release builds compile the world into the executable via
    ``tools/bake_world.py`` and ship no ``world_data/`` files. Source
    checkouts have no baked module and read the editable tree. Explicit
    non-default roots (tests, tooling) always read files.
    """
    if root == WORLD_DATA_PATH:
        try:
            from . import _baked_world
        except ImportError:
            return load_world_data(root)
        return _baked_world.load()
    return load_world_data(root)


# Routing cost multiplier for a leg carrying a truck_advisory (see
# shortest_route). Calibrated, not tasted: carriers accept the ~1.7x
# distance detour through Cortez and Moab rather than run the warned
# US-550 passes, so any factor clearing that ratio encodes the observed
# decision; 2.5 clears it with margin while a pair of towns whose only
# road is the warned one still routes.
TRUCK_ADVISORY_COST_MULT = 2.5


class World(WorldServiceMixin):
    def __init__(self, data: dict) -> None:
        geo = data.get("geo") if isinstance(data.get("geo"), dict) else {}
        countries = geo.get("countries") if isinstance(geo.get("countries"), dict) else {}
        self.cities: dict[str, City] = {}
        self._facilities_by_id: dict[str, Location] = {}
        for key, c in data["cities"].items():
            lat = float(c.get("lat", 0.0))
            lon = float(c.get("lon", 0.0))
            spoken_city, state_name, state_code, country_code, country_name = _city_identity(
                key, c, countries
            )
            explicit_locs = tuple(
                _parse_location(loc, key, spoken_city, lat, lon) for loc in c["locations"]
            )
            tags = _market_tags_for_city(key, state_code, c, explicit_locs)
            locs = _expand_market_locations(key, spoken_city, lat, lon, explicit_locs, tags)
            self._validate_city_locations(spoken_city, locs)
            self.cities[key] = City(
                spoken_city,
                state_name,
                c["region"],
                locs,
                lat,
                lon,
                tags,
                key=key,
                state_code=state_code,
                country=country_code,
                country_name=country_name,
            )
        self._city_aliases, self._ambiguous_spoken = _build_city_aliases(self.cities)
        self._legacy_names_by_key: dict[str, tuple[str, ...]] = {}
        for old_name, slug in LEGACY_CITY_SLUGS.items():
            if slug in self.cities and old_name != slug:
                self._legacy_names_by_key.setdefault(slug, ())
                self._legacy_names_by_key[slug] += (old_name,)
        self._legacy_facility_ids = _build_legacy_facility_ids(
            self.cities, self._legacy_names_by_key
        )
        # The checked-in local-driving data (city services, facility endpoints
        # and approaches, surface-street geometry) predates the slug migration
        # and is keyed by old display names and pre-slug facility ids; remap it
        # onto canonical keys once at load so every runtime lookup stays direct.
        self._service_city_keys = _build_service_city_keys(self.cities, self._legacy_names_by_key)
        # The nationwide local-driving data (city services, facility endpoints
        # and approaches, surface-street geometry) is ~31 MB of JSON that only
        # matters once a player is threading into a specific facility or city
        # service. Loading and remapping it at startup was pure latency; it is
        # built on first access instead. The remap keys off structures already
        # built above, so a lazy build is safe.
        self._local_data_lock = threading.RLock()
        self._city_service_data_cache: dict | None = None
        self._facility_approaches_cache: dict | None = None
        self._facility_endpoints_cache: dict | None = None
        self._local_approaches_cache: dict | None = None
        self._local_geometries_cache: dict | None = None

        self.legs: list[Leg] = []
        for leg in data["legs"]:
            # Endpoints resolve through the alias table so additive overlays
            # written against pre-slug names keep merging.
            leg_from = self.resolve_city_key(leg["from"])
            leg_to = self.resolve_city_key(leg["to"])
            miles = float(leg["miles"])
            highway = leg["highway"]
            stops = tuple(_parse_stop(s, miles, leg_from, leg_to) for s in leg.get("stops", ()))
            corridor = leg.get("corridor", {})
            from_state = self.cities[leg_from].state
            # Only the eager fields are built now; the heavy per-mile corridor
            # (grades, interchanges, landmarks, speed limits, ...) is parsed by
            # LazyLeg the first time a leg is driven. Dispatch completeness is
            # baked here from raw corridor counts so the route graph never has
            # to trigger that parse -- the counted fields parse one-for-one, so
            # this is identical to asking a fully built leg.
            meta_complete = raw_metadata_complete(corridor, from_state, self.cities[leg_to].state)
            self.legs.append(
                LazyLeg(
                    leg_from,
                    leg_to,
                    miles,
                    highway,
                    leg["terrain"],
                    stops,
                    lanes=max(0, int(leg.get("lanes", 0))),
                    local_cue="",
                    local_speed_mph=0.0,
                    divided=leg["divided"] if isinstance(leg.get("divided"), bool) else None,
                    truck_advisory=str(leg.get("truck_advisory", "")).strip(),
                    meta_complete=meta_complete,
                    detail_source=(corridor, miles, leg_from, leg_to, from_state, highway),
                )
            )
        self._adjacency: dict[str, list[Leg]] = {name: [] for name in self.cities}
        for leg in self.legs:
            self._adjacency[leg.a].append(leg)
            self._adjacency[leg.b].append(leg)
        self._supported_route_cache: dict[tuple[str, str], Route | None] = {}

    @property
    def _city_service_data(self) -> dict:
        if self._city_service_data_cache is None:
            with self._local_data_lock:
                if self._city_service_data_cache is None:
                    self._city_service_data_cache = {
                        self.resolve_city_key(name): services
                        for name, services in load_city_service_data().items()
                    }
        return self._city_service_data_cache

    @property
    def _facility_approaches(self) -> dict:
        if self._facility_approaches_cache is None:
            with self._local_data_lock:
                if self._facility_approaches_cache is None:
                    self._facility_approaches_cache = self._remap_facility_ids(
                        load_facility_approaches()
                    )
        return self._facility_approaches_cache

    @property
    def _facility_endpoints(self) -> dict:
        if self._facility_endpoints_cache is None:
            with self._local_data_lock:
                if self._facility_endpoints_cache is None:
                    self._facility_endpoints_cache = self._remap_facility_ids(
                        load_facility_endpoints()
                    )
        return self._facility_endpoints_cache

    @property
    def _local_approaches(self) -> dict:
        if self._local_approaches_cache is None:
            with self._local_data_lock:
                if self._local_approaches_cache is None:
                    self._local_approaches_cache = self._remap_local_ids(load_local_approaches())
        return self._local_approaches_cache

    @property
    def _local_geometries(self) -> dict:
        if self._local_geometries_cache is None:
            with self._local_data_lock:
                if self._local_geometries_cache is None:
                    self._local_geometries_cache = self._remap_local_ids(load_local_geometries())
        return self._local_geometries_cache

    def _remap_facility_ids(self, data: dict) -> dict:
        """Rekey a facility-id-keyed local-data dict onto current ids."""
        return {self._resolve_facility_id(key): value for key, value in data.items()}

    def _remap_local_ids(self, data: dict) -> dict:
        """Rekey local approach/geometry target ids onto canonical keys."""
        return {self._canonical_local_id(key): value for key, value in data.items()}

    def _canonical_local_id(self, target_id: str) -> str:
        if target_id.startswith("city_service:"):
            _, city_slug, service_key = target_id.split(":", 2)
            key = self._service_city_keys.get(city_slug)
            return f"city_service:{key}:{service_key}" if key else target_id
        if target_id.startswith("facility:"):
            facility_id = target_id[len("facility:") :]
            return f"facility:{self._resolve_facility_id(facility_id)}"
        return target_id

    def _validate_city_locations(self, city: str, locations: tuple[Location, ...]) -> None:
        if not locations:
            raise ValueError(f"{city} has no freight facilities")
        for location in locations:
            if location.type not in FREIGHT_LOCATION_TYPES:
                raise ValueError(
                    f"{city} facility {location.name!r} has unknown type {location.type!r}"
                )
            if not location.id:
                raise ValueError(f"{city} facility {location.name!r} has no stable id")
            if location.id in self._facilities_by_id:
                raise ValueError(f"Duplicate facility id {location.id!r}")
            if not location.spoken_name:
                raise ValueError(f"{city} facility {location.name!r} has no spoken name")
            if not location.source_note:
                raise ValueError(f"{city} facility {location.name!r} has no source note")
            if not location.ships and not location.receives:
                raise ValueError(f"{city} facility {location.name!r} has no cargo roles")
            self._facilities_by_id[location.id] = location

    @classmethod
    def load(cls, root: Path = WORLD_DATA_PATH, overlay: Path | None = None) -> World:
        """Load the world, optionally merging an additive overlay on top.

        The checked-in indexed world data is the deterministic source of truth.
        An optional ``overlay`` is merged additively: it can only add cities and
        legs the base does not already
        have, never override the base. With no overlay the result is exactly the
        base world, so the offline/deterministic path is unchanged. The runtime
        ``get_world`` deliberately does not pass an overlay yet; this is the
        loader capability the online tier will build on.
        """

        data = _load_base_world_data(root)
        if overlay is not None and overlay.exists():
            data = _merge_overlay(data, json.loads(overlay.read_text(encoding="utf-8")))
        return cls(data)

    def city_names(self) -> list[str]:
        return sorted(self.cities)

    def resolve_city_key(self, city: str) -> str:
        """Canonical key for any current or legacy city reference.

        Old saves persist bare display names ("Jackson") or qualified ones
        ("Jackson, Michigan"); both resolve through the alias table. Unknown
        text echoes back unchanged so callers keep their existing
        unknown-city behavior.
        """
        text = str(city or "").strip()
        if text in self.cities:
            return text
        return self._city_aliases.get(text, text)

    def city(self, city: str) -> City:
        """The City for a current or legacy reference; KeyError if unknown."""
        try:
            return self.cities[self.resolve_city_key(city)]
        except KeyError:
            raise KeyError(f"Unknown city: {city}") from None

    def spoken_city(self, city: str, qualified: bool | None = None) -> str:
        """Speakable name for a city reference; never the slug key.

        ``qualified=None`` appends the state exactly when the bare name is
        shared by more than one city (Jackson -> "Jackson, Mississippi").
        Unresolvable legacy text passes through unchanged -- old display
        names are already speakable.
        """
        key = self.resolve_city_key(city)
        city_obj = self.cities.get(key)
        if city_obj is None:
            return str(city)
        if qualified is None:
            qualified = key in self._ambiguous_spoken
        return city_obj.spoken_qualified if qualified else city_obj.name

    def neighbors(self, city: str) -> list[Leg]:
        return self._adjacency[self.resolve_city_key(city)]

    def facility_location(self, city: str, location_name: str) -> Location:
        key = self.resolve_city_key(city)
        if key not in self.cities:
            raise KeyError(f"Unknown city: {city}")
        city_obj = self.cities[key]
        normalized_name = str(location_name or "").strip()
        normalized_id = self._resolve_facility_id(normalized_name)
        # Legacy saves may name template facilities with the old display name
        # embedded ("Jackson, Michigan Regional Cross-Dock").
        name_candidates = {normalized_name}
        for old_name in self._legacy_names_by_key.get(key, ()):
            name_candidates.add(normalized_name.replace(old_name, city_obj.name))
        for location in city_obj.locations:
            if location.name in name_candidates or location.id in (
                normalized_name,
                normalized_id,
            ):
                return location
        if _is_legacy_market_name(
            (city_obj.name, *self._legacy_names_by_key.get(key, ())), normalized_name
        ):
            return self.default_facility(key)
        raise KeyError(f"Unknown facility in {city}: {location_name}")

    def facility_by_id(self, facility_id: str) -> Location:
        try:
            return self._facilities_by_id[self._resolve_facility_id(facility_id)]
        except KeyError:
            raise KeyError(f"Unknown facility id: {facility_id}") from None

    def _resolve_facility_id(self, facility_id: str) -> str:
        """Translate a pre-slug facility id to its current form when known."""
        if facility_id in self._facilities_by_id:
            return facility_id
        return self._legacy_facility_ids.get(facility_id, facility_id)

    def default_facility(self, city: str) -> Location:
        """Stable fallback for legacy jobs that only named a city."""
        city = self.resolve_city_key(city)
        if city not in self.cities:
            raise KeyError(f"Unknown city: {city}")
        locations = self.cities[city].locations
        preferred = (
            "company_yard",
            "terminal",
            "dry_warehouse",
            "warehouse",
            "distribution",
            "cross_dock",
        )
        for facility_type in preferred:
            for location in locations:
                if location.type == facility_type:
                    return location
        return locations[0]

    def home_terminal(self, city: str) -> HomeTerminal:
        """Return the player's dispatch yard for a service area.

        The world data mostly lists shippers and receivers rather than company
        yards, so explicit terminal facilities are preferred and every other
        city gets a stable fallback yard name. ``HomeTerminal.city`` carries the
        spoken city name -- the terminal object exists to be announced.
        """
        key = self.resolve_city_key(city)
        if key not in self.cities:
            raise KeyError(f"Unknown city: {city}")
        city_obj = self.cities[key]
        for location in city_obj.locations:
            if location.type == "terminal":
                return HomeTerminal(location.name, city_obj.name, city_obj.state, "terminal")
        for location in city_obj.locations:
            if location.type == "company_yard":
                return HomeTerminal(location.name, city_obj.name, city_obj.state, "company_yard")
        return HomeTerminal(
            f"{city_obj.name} Company Yard", city_obj.name, city_obj.state, "company_yard"
        )

    def shortest_route(
        self,
        start: str,
        end: str,
        penalties: dict[Leg, float] | None = None,
        require_metadata: bool = False,
    ) -> Route | None:
        """Dijkstra over leg miles, with optional per-leg penalty multipliers.

        ``require_metadata`` is for new dispatchable freight. The default keeps
        the historical full graph available for legacy saves and map integrity
        checks while supported freight routes are enriched lane by lane.
        """
        start = self.resolve_city_key(start)
        end = self.resolve_city_key(end)
        if start not in self.cities or end not in self.cities:
            raise KeyError(f"Unknown city: {start if start not in self.cities else end}")
        penalties = penalties or {}
        has_penalties = bool(penalties)
        dist: dict[str, float] = {start: 0.0}
        prev: dict[str, tuple[str, Leg]] = {}
        heap: list[tuple[float, str]] = [(0.0, start)]
        visited: set[str] = set()
        while heap:
            d, city = heapq.heappop(heap)
            if city in visited:
                continue
            visited.add(city)
            if city == end:
                break
            for leg in self._adjacency[city]:
                if require_metadata and not self.leg_metadata_complete(leg):
                    continue
                nxt = leg.other(city)
                cost = leg.miles * penalties.get(leg, 1.0) if has_penalties else leg.miles
                if leg.truck_advisory:
                    # Strong avoidance, never refusal. Calibrated against the
                    # decision real carriers make at Red Mountain Pass: they
                    # accept the ~1.7x-distance detour through Cortez and
                    # Moab rather than run a warned pass, so the multiplier
                    # only has to clear that ratio for the detour to win
                    # wherever one exists; 2.5 clears it with margin. A pair
                    # of towns whose ONLY road is the warned one still
                    # routes -- the advisory is a warning, not a wall.
                    cost *= TRUCK_ADVISORY_COST_MULT
                nd = d + cost
                if nd < dist.get(nxt, float("inf")):
                    dist[nxt] = nd
                    prev[nxt] = (city, leg)
                    heapq.heappush(heap, (nd, nxt))
        if end not in prev and start != end:
            return None
        cities = [end]
        legs: list[Leg] = []
        cur = end
        while cur != start:
            parent, leg = prev[cur]
            legs.append(leg)
            cities.append(parent)
            cur = parent
        cities.reverse()
        legs.reverse()
        return Route(cities, legs)

    def route_from_cities(self, cities: list[str]) -> Route | None:
        """Rebuild a route from its city sequence (used by saved trips).

        Returns None if any hop is missing, so callers can fall back
        gracefully when a save references a road that no longer exists. This is
        intentionally the legacy/full graph path; new freight uses supported
        route helpers so missing metadata cannot silently invent conditions.
        """
        if len(cities) < 2:
            return None
        cities = [self.resolve_city_key(c) for c in cities]
        legs: list[Leg] = []
        for a, b in zip(cities, cities[1:], strict=False):
            leg = next((x for x in self._adjacency.get(a, ()) if x.other(a) == b), None)
            if leg is None:
                return None
            legs.append(leg)
        return Route(list(cities), legs)

    def leg_metadata_complete(self, leg: Leg) -> bool:
        return leg.metadata_complete(self.cities[leg.a].state, self.cities[leg.b].state)

    def supported_route(
        self, start: str, end: str, penalties: dict[Leg, float] | None = None
    ) -> Route | None:
        if penalties:
            return self.shortest_route(start, end, penalties, require_metadata=True)
        start = self.resolve_city_key(start)
        end = self.resolve_city_key(end)
        key = (start, end)
        if key not in self._supported_route_cache:
            self._supported_route_cache[key] = self.shortest_route(
                start, end, require_metadata=True
            )
        route = self._supported_route_cache[key]
        if route is None:
            return None
        return Route(list(route.cities), list(route.legs))

    def supported_route_options(self, start: str, end: str, count: int = 3) -> list[Route]:
        return self.route_options(start, end, count, require_metadata=True)

    def route_options(
        self, start: str, end: str, count: int = 3, require_metadata: bool = False
    ) -> list[Route]:
        """Up to ``count`` distinct routes, fastest first."""
        routes: list[Route] = []
        penalties: dict[Leg, float] = {}
        seen: set[tuple[str, ...]] = set()
        best = self.shortest_route(start, end, require_metadata=require_metadata)
        if best is None:
            return routes
        max_miles = _max_alternate_miles(best.miles)
        for _ in range(count * 8):
            route = self.shortest_route(start, end, penalties, require_metadata=require_metadata)
            if route is None:
                break
            key = tuple(route.cities)
            if key not in seen and route.miles <= max_miles:
                seen.add(key)
                routes.append(route)
                if len(routes) >= count:
                    break
            for leg in route.legs:
                penalties[leg] = penalties.get(leg, 1.0) * 2.5
        routes.sort(key=lambda r: r.miles)
        return routes


_world: World | None = None


def _city_identity(key: str, raw: dict, countries: dict) -> tuple[str, str, str, str, str]:
    """(spoken city, spoken state, state code, country code, spoken country).

    Migrated cities carry ``spoken_city`` plus 2-letter ``state``/``country``
    codes resolved through the geo lookup. Pre-slug shapes (bare-name key,
    full state name, no country) still compose sensibly so overlays and small
    test fixtures keep loading.
    """
    spoken_city = str(raw.get("spoken_city", "")).strip() or key
    raw_state = str(raw.get("state", "")).strip()
    country_code = str(raw.get("country", "")).strip() or "US"
    country_info = countries.get(country_code) if isinstance(countries, dict) else None
    country_info = country_info if isinstance(country_info, dict) else {}
    states = country_info.get("states") if isinstance(country_info.get("states"), dict) else {}
    country_name = str(country_info.get("name", "")).strip() or country_code
    if raw_state in states:
        return spoken_city, str(states[raw_state]), raw_state, country_code, country_name
    code = next((c for c, name in states.items() if name == raw_state), "")
    return spoken_city, raw_state, code, country_code, country_name


def _build_city_aliases(cities: dict[str, City]) -> tuple[dict[str, str], frozenset[str]]:
    """(alias text -> key) plus the keys whose bare spoken name is shared.

    Bare spoken names alias only while globally unique; qualified forms
    ("Jackson, Michigan" / "Jackson, MI") always alias. The frozen
    ``LEGACY_CITY_SLUGS`` map wins every conflict: an old save's name must
    keep meaning the city it meant when the save was written, even after a
    later map expansion reuses the name.
    """
    spoken_count: dict[str, int] = {}
    for city in cities.values():
        folded = city.name.casefold()
        spoken_count[folded] = spoken_count.get(folded, 0) + 1
    ambiguous = frozenset(
        city.key for city in cities.values() if spoken_count[city.name.casefold()] > 1
    )
    aliases: dict[str, str] = {}
    for key, city in cities.items():
        if spoken_count[city.name.casefold()] == 1:
            aliases.setdefault(city.name, key)
        if city.state:
            aliases.setdefault(f"{city.name}, {city.state}", key)
        if city.state_code:
            aliases.setdefault(f"{city.name}, {city.state_code}", key)
    for old_name, slug in LEGACY_CITY_SLUGS.items():
        if slug in cities:
            aliases[old_name] = slug
    return aliases, ambiguous


def _build_legacy_facility_ids(
    cities: dict[str, City], legacy_names_by_key: dict[str, tuple[str, ...]]
) -> dict[str, str]:
    """Map pre-slug facility ids to current ones.

    Old ids embedded a slug of the display name (``jackson-michigan:...``);
    template facility names embedded the display name too, so both parts can
    differ. Rebuilt per legacy name so every persisted job facility id keeps
    resolving.
    """
    legacy_ids: dict[str, str] = {}
    for key, old_names in legacy_names_by_key.items():
        city = cities[key]
        for old_name in old_names:
            for location in city.locations:
                old_facility_name = (
                    location.name.replace(city.name, old_name)
                    if location.template
                    else location.name
                )
                old_id = _stable_facility_id(old_name, location.type, old_facility_name)
                legacy_ids.setdefault(old_id, location.id)
    return legacy_ids


def _build_service_city_keys(
    cities: dict[str, City], legacy_names_by_key: dict[str, tuple[str, ...]]
) -> dict[str, str]:
    """Map the city slug embedded in local city-service ids to the city key.

    The checked-in local approach and geometry ids were generated from
    pre-slug display names (``city_service:sault-ste-marie:garage``); current
    spoken names map too so future data keyed either way keeps resolving.
    """
    service_keys: dict[str, str] = {}
    for key, city in cities.items():
        service_keys.setdefault(_service_city_slug(city.name), key)
    for key, old_names in legacy_names_by_key.items():
        for old_name in old_names:
            service_keys[_service_city_slug(old_name)] = key
    return service_keys


def _max_alternate_miles(best_miles: float) -> float:
    extra = best_miles * ALTERNATE_ROUTE_EXTRA_RATIO
    extra = max(ALTERNATE_ROUTE_MIN_EXTRA_MILES, min(ALTERNATE_ROUTE_MAX_EXTRA_MILES, extra))
    return best_miles + extra


def get_world() -> World:
    """Shared world instance (the data is immutable)."""
    global _world
    if _world is None:
        _world = World.load()
    return _world
