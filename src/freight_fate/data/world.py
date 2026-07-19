# ruff: noqa: F403,F405
"""World model: cities, freight locations, and the highway network.

Loads indexed world data and exposes a graph with Dijkstra-based route finding.
Route options are produced by re-running the search with already-used legs
penalized, giving genuinely different alternatives (fastest vs. detour).
"""

from __future__ import annotations

import heapq
import json
import re
import zlib
from pathlib import Path

from .legacy_aliases import LEGACY_CITY_SLUGS
from .world_constants import *
from .world_loader import load_world_data
from .world_models import *

WORLD_PATH = Path(__file__).parent / "world.json"
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


class World:
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

        self.legs: list[Leg] = []
        for leg in data["legs"]:
            # Endpoints resolve through the alias table so additive overlays
            # written against pre-slug names keep merging.
            leg_from = self.resolve_city_key(leg["from"])
            leg_to = self.resolve_city_key(leg["to"])
            miles = float(leg["miles"])
            stops = tuple(_parse_stop(s, miles, leg_from, leg_to) for s in leg.get("stops", ()))
            corridor = leg.get("corridor", {})
            route_points = tuple(
                _parse_route_point(p, miles, leg_from, leg_to)
                for p in corridor.get("route_points", ())
            )
            elevation_samples = tuple(
                _parse_elevation_sample(s, miles, leg_from, leg_to)
                for s in corridor.get("elevation_samples", ())
            )
            grade_segments = tuple(
                _parse_grade_segment(s, miles, leg_from, leg_to)
                for s in corridor.get("grade_segments", ())
            )
            state_crossings = tuple(
                _parse_state_crossing(c, miles, leg_from, leg_to, self.cities[leg_from].state)
                for c in corridor.get("state_crossings", ())
            )
            checkpoints = tuple(
                _parse_checkpoint(c, miles, leg_from, leg_to)
                for c in corridor.get("checkpoints", ())
            )
            state_miles = tuple(
                _parse_state_mileage(m, leg_from, leg_to) for m in corridor.get("state_miles", ())
            )
            toll_events = tuple(
                _parse_toll_event(e, miles, leg_from, leg_to, leg["highway"])
                for e in corridor.get("toll_events", ())
            )
            interchanges = tuple(
                _parse_interchange(x, miles, leg_from, leg_to, leg["highway"])
                for x in corridor.get("interchanges", ())
            )
            speed_limits = _parse_speed_limits(
                corridor.get("speed_limits", ()), miles, leg_from, leg_to
            )
            self.legs.append(
                Leg(
                    leg_from,
                    leg_to,
                    miles,
                    leg["highway"],
                    leg["terrain"],
                    stops,
                    route_points,
                    elevation_samples,
                    grade_segments,
                    state_crossings,
                    checkpoints,
                    state_miles,
                    toll_events,
                    interchanges,
                    speed_limits,
                )
            )
        self._adjacency: dict[str, list[Leg]] = {name: [] for name in self.cities}
        for leg in self.legs:
            self._adjacency[leg.a].append(leg)
            self._adjacency[leg.b].append(leg)
        self._supported_route_cache: dict[tuple[str, str], Route | None] = {}

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

    def facility_approach_route(self, city: str, location_name: str) -> Route:
        """A short, drivable local route from the company terminal to a facility."""
        key = self.resolve_city_key(city)
        location = self.facility_location(key, location_name)
        base_miles = FACILITY_APPROACH_MILES.get(location.type, 4.0)
        seed = zlib.crc32(f"{key}:{location.name}:{location.type}".encode())
        offset = (seed % 7) * 0.25
        miles = round(base_miles + offset, 1)
        road = FACILITY_APPROACH_ROADS.get(location.type, "facility access road")
        leg = Leg(key, key, miles, road, "flat", ())
        return Route([key, key], [leg])

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
            # Keep the leg in its native data orientation. Route.cities records
            # the travel direction, and Trip uses it to mirror directional
            # stops, interchanges, grades, and other milepost-backed metadata.
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


def _overlay_city_key(name: str, cities: dict) -> str:
    """The key an overlay city name lands on: itself, or the slug it aliases.

    Overlays written before the slug migration name cities by display name;
    treating those as the base city they alias keeps the merge additive
    instead of duplicating the city under its old name.
    """
    if name in cities:
        return name
    slug = LEGACY_CITY_SLUGS.get(name)
    return slug if slug in cities else name


def _leg_pair_key(leg: dict, cities: dict) -> frozenset:
    return frozenset(
        (_overlay_city_key(leg.get("from"), cities), _overlay_city_key(leg.get("to"), cities))
    )


def _merge_overlay(base: dict, overlay: dict) -> dict:
    """Return ``base`` with overlay cities and legs added, never overridden.

    The merge is purely additive so the checked-in base stays authoritative:
    a city already present (by key, or by a pre-slug legacy name aliasing one)
    keeps its base definition, and a leg already present (by unordered endpoint
    pair) keeps its base definition. Only genuinely new cities and legs from
    the overlay are appended. The base dict is not mutated.
    """
    merged = dict(base)
    cities = dict(base.get("cities", {}))
    for name, city in overlay.get("cities", {}).items():
        if _overlay_city_key(name, cities) not in cities:
            cities[name] = city
    merged["cities"] = cities

    legs = list(base.get("legs", []))
    seen = {_leg_pair_key(leg, cities) for leg in legs}
    for leg in overlay.get("legs", []):
        key = _leg_pair_key(leg, cities)
        if key not in seen:
            seen.add(key)
            legs.append(leg)
    merged["legs"] = legs
    return merged


def _parse_location(
    raw: dict, city_key: str, spoken_city: str, city_lat: float, city_lon: float
) -> Location:
    if not isinstance(raw, dict):
        raise ValueError(f"{spoken_city} facility must be an object")
    name = _clean_facility_name(spoken_city, str(raw.get("name", "")).strip())
    facility_type = str(raw.get("type", "")).strip()
    if facility_type not in FREIGHT_LOCATION_TYPES:
        raise ValueError(f"{spoken_city} facility {name!r} has unknown type {facility_type!r}")
    default_roles = FACILITY_CARGO_ROLES.get(facility_type, {})
    raw_cargo = tuple(str(cargo).strip() for cargo in raw.get("cargo", ()) if str(cargo).strip())
    default_cargo = _dedupe(default_roles.get("ships", ()) + default_roles.get("receives", ()))
    cargo = raw_cargo or default_cargo
    ships = _role_cargo(raw, "ships", cargo, default_roles.get("ships", ()))
    receives = _role_cargo(raw, "receives", cargo, default_roles.get("receives", ()))
    roles = tuple(role for role, values in (("shipper", ships), ("receiver", receives)) if values)
    source_note = str(
        raw.get("source_note")
        or raw.get("source")
        or FACILITY_SOURCE_NOTES.get(facility_type, "Curated representative facility.")
    ).strip()
    spoken = str(raw.get("spoken_name") or raw.get("spoken") or "").strip()
    locality = str(raw.get("locality", "")).strip()
    traits = tuple(str(trait).strip() for trait in raw.get("traits", ()) if str(trait).strip())
    return Location(
        name=name,
        type=facility_type,
        cargo=cargo,
        id=str(raw.get("id") or _stable_facility_id(city_key, facility_type, name)).strip(),
        city=city_key,
        locality=locality,
        roles=roles,
        ships=ships,
        receives=receives,
        lat=float(raw.get("lat", city_lat)),
        lon=float(raw.get("lon", city_lon)),
        traits=traits,
        source_note=source_note,
        spoken=spoken,
        template=bool(raw.get("template", False)),
        min_level=int(raw.get("min_level", FACILITY_LEVEL_UNLOCKS.get(facility_type, 1))),
    )


def _expand_market_locations(
    city_key: str,
    spoken_city: str,
    lat: float,
    lon: float,
    explicit_locations: tuple[Location, ...],
    market_tags: tuple[str, ...],
) -> tuple[Location, ...]:
    locations = list(explicit_locations)
    existing_types = {location.type for location in locations}
    existing_names = {location.name.lower() for location in locations}
    desired_types = list(BASE_MARKET_FACILITY_TYPES)
    for tag in market_tags:
        desired_types.extend(MARKET_TAG_FACILITY_TYPES.get(tag, ()))
    for facility_type in _dedupe(desired_types):
        if facility_type in existing_types:
            continue
        location = _template_location(city_key, spoken_city, lat, lon, facility_type, market_tags)
        if location.name.lower() in existing_names:
            location = _template_location(
                city_key,
                spoken_city,
                lat,
                lon,
                facility_type,
                market_tags,
                name_suffix=" Facility",
            )
        locations.append(location)
        existing_types.add(location.type)
        existing_names.add(location.name.lower())
    return tuple(locations)


def _template_location(
    city_key: str,
    spoken_city: str,
    lat: float,
    lon: float,
    facility_type: str,
    market_tags: tuple[str, ...],
    name_suffix: str = "",
) -> Location:
    template = FACILITY_NAME_TEMPLATES[facility_type]
    name = template.format(city=spoken_city) + name_suffix
    roles = FACILITY_CARGO_ROLES[facility_type]
    cargo = _dedupe(roles["ships"] + roles["receives"])
    source_note = (
        f"{FACILITY_SOURCE_NOTES[facility_type]} Generated offline as a "
        f"representative {spoken_city} metro-market facility; not a claim about a "
        "specific real-world shipper."
    )
    jitter_lat, jitter_lon = _jittered_coordinates(city_key, facility_type, lat, lon)
    return Location(
        name=name,
        type=facility_type,
        cargo=cargo,
        id=_stable_facility_id(city_key, facility_type, name),
        city=city_key,
        roles=("shipper", "receiver"),
        ships=roles["ships"],
        receives=roles["receives"],
        lat=jitter_lat,
        lon=jitter_lon,
        traits=("representative", "template") + market_tags,
        source_note=source_note,
        template=True,
        min_level=FACILITY_LEVEL_UNLOCKS.get(facility_type, 1),
    )


def _market_tags_for_city(
    city_key: str, state_code: str, raw_city: dict, locations: tuple[Location, ...]
) -> tuple[str, ...]:
    tags: set[str] = set(REGION_MARKET_TAGS.get(str(raw_city.get("region", "")), ()))
    tags.update(STATE_MARKET_TAGS.get(state_code, ()))
    tags.update(CITY_MARKET_TAGS.get(city_key, ()))
    for location in locations:
        tags.update(_tags_for_facility_type(location.type))
    return tuple(sorted(tags))


def _tags_for_facility_type(facility_type: str) -> tuple[str, ...]:
    return {
        "air_cargo": ("air",),
        "distribution": ("retail",),
        "food_terminal": ("food", "cold_chain"),
        "industrial_park": ("industrial",),
        "intermodal": ("intermodal",),
        "manufacturing": ("manufacturing",),
        "port": ("port",),
        "rail": ("intermodal",),
        "retail_distribution": ("retail",),
        "terminal": ("cross_dock",),
        "warehouse": ("retail",),
    }.get(facility_type, ())


def _role_cargo(
    raw: dict, key: str, cargo: tuple[str, ...], defaults: tuple[str, ...]
) -> tuple[str, ...]:
    values = tuple(str(value).strip() for value in raw.get(key, ()) if str(value).strip())
    if values:
        return values
    plausible = tuple(value for value in cargo if value in defaults)
    return plausible or tuple(value for value in cargo if value)


def _clean_facility_name(city: str, name: str) -> str:
    if not name:
        raise ValueError(f"{city} has a facility without a name")
    lowered = name.lower()
    if any(marker in lowered for marker in RAW_FACILITY_TEXT_MARKERS):
        raise ValueError(f"{city} facility {name!r} exposes raw source text")
    return name


def _stable_facility_id(city: str, facility_type: str, name: str) -> str:
    return f"{_slug(city)}:{facility_type}:{_slug(name)}"


def _slug(text: str) -> str:
    out: list[str] = []
    pending_dash = False
    for char in text.lower():
        if char.isalnum():
            if pending_dash and out:
                out.append("-")
            out.append(char)
            pending_dash = False
        else:
            pending_dash = True
    return "".join(out).strip("-") or "facility"


def _dedupe(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return tuple(out)


def _jittered_coordinates(
    city: str, facility_type: str, lat: float, lon: float
) -> tuple[float, float]:
    if lat == 0.0 and lon == 0.0:
        return lat, lon
    seed = zlib.crc32(f"{city}:{facility_type}".encode())
    lat_offset = ((seed & 0xFF) - 128) / 5000.0
    lon_offset = (((seed >> 8) & 0xFF) - 128) / 5000.0
    return round(lat + lat_offset, 5), round(lon + lon_offset, 5)


def _is_legacy_market_name(city_names: tuple[str, ...], name: str) -> bool:
    """True when ``name`` is one of the old whole-city market placeholders.

    Checked against every name the city has answered to (current spoken plus
    frozen legacy display names) so pre-slug saves keep resolving."""
    normalized = name.strip().lower()
    if not normalized:
        return True
    for city_name in city_names:
        city_lower = city_name.lower()
        if normalized in {
            city_lower,
            f"{city_lower} freight market",
            f"{city_lower} metro freight market",
        }:
            return True
    return False


def _parse_stop(raw, leg_miles: float, from_city: str, to_city: str) -> Stop:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} stop {raw!r} is missing explicit at_mi")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"{from_city} to {to_city} has a stop without a name")
    lowered_name = name.lower()
    if any(marker in lowered_name for marker in RAW_POI_TEXT_MARKERS):
        raise ValueError(f"{from_city} to {to_city} stop {name!r} exposes raw OSM/source text")
    if "at_mi" not in raw:
        raise ValueError(f"{from_city} to {to_city} stop {name!r} is missing explicit at_mi")
    at_mi = float(raw["at_mi"])
    if not 0.0 < at_mi < leg_miles:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has at_mi {at_mi}, "
            f"outside leg mileage 0-{leg_miles}"
        )
    stop_type = str(raw.get("type", "")).strip() or _classify_stop(name)
    if stop_type not in STOP_TYPE_LABELS:
        raise ValueError(f"{from_city} to {to_city} stop {name!r} has unknown type {stop_type!r}")
    source = str(raw.get("source", "")).strip()
    actions = tuple(
        str(action).strip() for action in raw.get("actions", DEFAULT_POI_ACTIONS[stop_type])
    )
    if not actions:
        raise ValueError(f"{from_city} to {to_city} stop {name!r} has no actions")
    unknown = sorted(set(actions) - POI_ACTIONS)
    if unknown:
        raise ValueError(f"{from_city} to {to_city} stop {name!r} has unknown actions {unknown}")
    default_actions = set(DEFAULT_POI_ACTIONS[stop_type])
    disallowed = sorted(set(actions) - default_actions)
    if disallowed:
        source_backed = set(disallowed) <= SOURCE_BACKED_POI_ACTIONS
        if not source_backed:
            raise ValueError(
                f"{from_city} to {to_city} stop {name!r} actions {disallowed} "
                f"do not match type {stop_type!r}"
            )
    services = tuple(
        str(service).strip() for service in raw.get("services", ()) if str(service).strip()
    )
    parking = str(raw.get("parking", "")).strip() or _default_parking_certainty(
        stop_type, services, actions
    )
    if parking not in PARKING_CERTAINTY_LABELS:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has unknown parking certainty {parking!r}"
        )
    directions = tuple(
        str(direction).strip()
        for direction in raw.get("directions", ("both",))
        if str(direction).strip()
    )
    if not directions:
        raise ValueError(f"{from_city} to {to_city} stop {name!r} has no directions")
    unknown_directions = sorted(set(directions) - STOP_DIRECTIONS)
    if unknown_directions:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has unknown directions {unknown_directions}"
        )
    if "both" in directions and len(directions) > 1:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} mixes 'both' with "
            "direction-specific applicability"
        )
    curation = str(raw.get("curation", "")).strip() or _infer_stop_curation(name, source)
    if curation not in STOP_CURATION_LEVELS:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has unknown curation {curation!r}"
        )
    if curation == "curated" and _infer_stop_curation(name, source) == "placeholder":
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} looks synthetic but is marked curated"
        )
    for action in SOURCE_BACKED_POI_ACTIONS & set(actions):
        if action not in services:
            raise ValueError(
                f"{from_city} to {to_city} stop {name!r} action {action!r} "
                "requires matching source-backed service metadata"
            )
        if not source:
            raise ValueError(
                f"{from_city} to {to_city} stop {name!r} action {action!r} requires a source note"
            )
    return Stop(name, at_mi, stop_type, source, actions, services, parking, directions, curation)


def _parse_route_point(raw, leg_miles: float, from_city: str, to_city: str) -> RoutePoint:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} route point must be an object")
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, "route point", allow_endpoints=True)
    lat = float(raw["lat"])
    lon = float(raw["lon"])
    if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
        raise ValueError(f"{from_city} to {to_city} route point has invalid coordinates")
    return RoutePoint(at_mi, lat, lon)


def _parse_elevation_sample(raw, leg_miles: float, from_city: str, to_city: str) -> ElevationSample:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} elevation sample must be an object")
    at_mi = _parse_at_mi(
        raw, leg_miles, from_city, to_city, "elevation sample", allow_endpoints=True
    )
    elevation_ft = float(raw["elevation_ft"])
    if not -300.0 <= elevation_ft <= 20_500.0:
        raise ValueError(f"{from_city} to {to_city} elevation sample has invalid elevation")
    source = str(raw.get("source", "")).strip()
    return ElevationSample(at_mi, elevation_ft, source)


def _parse_grade_segment(raw, leg_miles: float, from_city: str, to_city: str) -> GradeSegment:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} grade segment must be an object")
    if "start_mi" not in raw:
        raise ValueError(f"{from_city} to {to_city} grade segment is missing explicit start_mi")
    start_mi = float(raw["start_mi"])
    if not 0.0 <= start_mi <= leg_miles:
        raise ValueError(
            f"{from_city} to {to_city} grade segment start has start_mi {start_mi}, "
            f"outside leg mileage 0-{leg_miles}"
        )
    end_mi = float(raw["end_mi"])
    if not 0.0 <= end_mi <= leg_miles or end_mi <= start_mi:
        raise ValueError(
            f"{from_city} to {to_city} grade segment has invalid range {start_mi}-{end_mi}"
        )
    avg_grade_pct = float(raw["avg_grade_pct"])
    if not -15.0 <= avg_grade_pct <= 15.0:
        raise ValueError(
            f"{from_city} to {to_city} grade segment has unrealistic grade {avg_grade_pct}"
        )
    terrain = str(raw.get("terrain", "")).strip() or "flat"
    if terrain not in {"flat", "hills", "mountain"}:
        raise ValueError(f"{from_city} to {to_city} grade segment has unknown terrain {terrain!r}")
    source = str(raw.get("source", "")).strip()
    return GradeSegment(start_mi, end_mi, avg_grade_pct, terrain, source)


def _parse_speed_limit(raw, leg_miles: float, from_city: str, to_city: str) -> SpeedLimitSample:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} speed limit must be an object")
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, "speed limit", allow_endpoints=True)
    mph = float(raw["mph"])
    if not 5.0 <= mph <= 85.0:
        raise ValueError(f"{from_city} to {to_city} speed limit has unrealistic mph {mph}")
    source = str(raw.get("source", "")).strip()
    return SpeedLimitSample(at_mi, mph, source, bool(raw.get("hgv", False)))


def _parse_speed_limits(
    raw_samples, leg_miles: float, from_city: str, to_city: str
) -> tuple[SpeedLimitSample, ...]:
    """Parse the baked maxspeed profile, ordered along the leg.

    Sorting by ``at_mi`` lets the runtime treat it as a step function without
    trusting the order the samples happen to be stored in."""
    samples = tuple(_parse_speed_limit(s, leg_miles, from_city, to_city) for s in raw_samples)
    return tuple(sorted(samples, key=lambda s: s.at_mi))


def _parse_state_crossing(
    raw, leg_miles: float, from_city: str, to_city: str, default_from_state: str
) -> StateCrossing:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} state crossing must be an object")
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, "state crossing")
    state = str(raw.get("state", "")).strip()
    if not state:
        raise ValueError(f"{from_city} to {to_city} has a state crossing without a state")
    from_state = str(raw.get("from_state", "")).strip() or default_from_state
    place = str(raw.get("place", "")).strip() or "state line"
    source = str(raw.get("source", "")).strip()
    return StateCrossing(at_mi, from_state, state, place, source)


def _parse_checkpoint(raw, leg_miles: float, from_city: str, to_city: str) -> RouteCheckpoint:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} checkpoint must be an object")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"{from_city} to {to_city} has a checkpoint without a name")
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, f"checkpoint {name!r}")
    checkpoint_type = str(raw.get("type", "")).strip() or "place"
    state = str(raw.get("state", "")).strip()
    highway = str(raw.get("highway", "")).strip()
    source = str(raw.get("source", "")).strip()
    return RouteCheckpoint(name, at_mi, checkpoint_type, state, highway, source)


def _parse_state_mileage(raw, from_city: str, to_city: str) -> StateMileage:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} state mileage must be an object")
    state = str(raw.get("state", "")).strip()
    if not state:
        raise ValueError(f"{from_city} to {to_city} has state mileage without a state")
    miles = float(raw["miles"])
    if miles <= 0.0:
        raise ValueError(f"{from_city} to {to_city} state mileage must be positive")
    return StateMileage(state, miles)


def _parse_toll_event(
    raw, leg_miles: float, from_city: str, to_city: str, default_road: str
) -> TollEvent:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} toll event must be an object")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"{from_city} to {to_city} toll event has no name")
    lowered_name = name.lower()
    if any(marker in lowered_name for marker in RAW_POI_TEXT_MARKERS):
        raise ValueError(
            f"{from_city} to {to_city} toll event {name!r} exposes raw OSM/source text"
        )
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, f"toll event {name!r}")
    road = str(raw.get("road", "")).strip() or default_road
    authority = str(raw.get("authority", "")).strip()
    method = str(raw.get("method", "")).strip()
    source = str(raw.get("source", "")).strip()
    if not authority:
        raise ValueError(f"{from_city} to {to_city} toll event {name!r} has no authority")
    if method not in TOLL_METHOD_LABELS:
        raise ValueError(
            f"{from_city} to {to_city} toll event {name!r} has unknown method {method!r}"
        )
    amount = float(raw["amount"])
    if amount < 0.0 or amount > 500.0:
        raise ValueError(f"{from_city} to {to_city} toll event {name!r} has invalid amount")
    if not source:
        raise ValueError(f"{from_city} to {to_city} toll event {name!r} has no source")
    return TollEvent(
        name=name,
        at_mi=at_mi,
        road=road,
        authority=authority,
        method=method,
        amount=amount,
        estimated=bool(raw.get("estimated", True)),
        source=source,
    )


def _parse_interchange(
    raw, leg_miles: float, from_city: str, to_city: str, default_highway: str
) -> Interchange:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} interchange must be an object")
    # OSM exit refs occasionally carry stray internal spaces ("103 B"); a real
    # exit number never does, so collapse them ("103 B" -> "103B").
    exit_ref = re.sub(r"\s+", "", str(raw.get("exit_ref", "")).strip())
    name = str(raw.get("name", "")).strip()
    via = str(raw.get("via", "")).strip()
    raw_dests = raw.get("destinations", ())
    if isinstance(raw_dests, str):
        raw_dests = [raw_dests]
    destinations = tuple(d for d in (str(item).strip() for item in raw_dests) if d)
    label = f"interchange {exit_ref or name or '(unnamed)'!r}"
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, label)
    # An interchange must carry *something* sayable beyond a milepost.
    if not (exit_ref or destinations or name):
        raise ValueError(
            f"{from_city} to {to_city} interchange at {at_mi} has no exit ref, "
            "destinations, or name"
        )
    blob = " ".join((name, via, *destinations)).lower()
    if any(marker in blob for marker in RAW_POI_TEXT_MARKERS):
        raise ValueError(f"{from_city} to {to_city} {label} exposes raw OSM/source text")
    highway = str(raw.get("highway", "")).strip() or default_highway
    source = str(raw.get("source", "")).strip()
    if not source:
        raise ValueError(f"{from_city} to {to_city} {label} has no source")
    return Interchange(
        at_mi=at_mi,
        exit_ref=exit_ref,
        name=name,
        destinations=destinations,
        via=via,
        highway=highway,
        source=source,
    )


def _route_token(value: str) -> str:
    """Leading route shield of a string, normalized for comparison:
    'I 70 East' -> 'I70', 'US 1 North' -> 'US1', 'Trenton' -> ''."""
    match = re.match(r"\s*((?:I|US|[A-Za-z]{2})[-\s]?\d+)", str(value).strip())
    return re.sub(r"[-\s]", "", match.group(1)).upper() if match else ""


def _destinations_without_via(via: str, destinations: tuple[str, ...]) -> tuple[str, ...]:
    """Drop destinations that merely restate the via route (via 'I 70' with a
    destination of 'I 70 East'), so the spoken phrase never says it twice. The
    via itself still carries the route, so emptying the list reads cleanly
    ('exit 101A for I-70')."""
    token = _route_token(via)
    if not token:
        return destinations
    return tuple(d for d in destinations if _route_token(d) != token)


def _join_destinations(destinations: tuple[str, ...]) -> str:
    """['Trenton', 'New York'] -> 'Trenton and New York'; Oxford-comma 3+."""
    items = [d for d in destinations if d]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _parse_at_mi(
    raw: dict,
    leg_miles: float,
    from_city: str,
    to_city: str,
    label: str,
    *,
    allow_endpoints: bool = False,
) -> float:
    if "at_mi" not in raw:
        raise ValueError(f"{from_city} to {to_city} {label} is missing explicit at_mi")
    at_mi = float(raw["at_mi"])
    in_range = 0.0 <= at_mi <= leg_miles if allow_endpoints else 0.0 < at_mi < leg_miles
    if not in_range:
        raise ValueError(
            f"{from_city} to {to_city} {label} has at_mi {at_mi}, outside leg mileage 0-{leg_miles}"
        )
    return at_mi


def _classify_stop(name: str) -> str:
    lower = name.lower()
    if "weigh" in lower:
        return "weigh_station"
    if "parking" in lower:
        return "truck_parking"
    if "rest area" in lower:
        return "public_rest_area"
    if "service plaza" in lower:
        return "service_plaza"
    if "truck" in lower:
        return "truck_stop"
    if any(word in lower for word in ("travel", "fuel", "plaza", "center")):
        return "travel_center"
    return "travel_center"


def _default_parking_certainty(
    stop_type: str,
    services: tuple[str, ...],
    actions: tuple[str, ...],
) -> str:
    if "parking" not in services and "park" not in actions:
        return "none"
    if stop_type in {"truck_stop", "travel_center", "service_plaza"}:
        return "likely"
    if stop_type in {"public_rest_area", "truck_parking"}:
        return "limited"
    return "unknown"


def _infer_stop_curation(name: str, source: str) -> str:
    text = f"{name} {source}".lower()
    synthetic_markers = (
        "corridor rest area",
        "corridor truck parking",
        "corridor fuel stop",
        "descriptive gameplay stop seeded",
        "seeded for offline route coverage",
        "no actionable overpass poi candidate",
    )
    return "placeholder" if any(marker in text for marker in synthetic_markers) else "curated"


def minimum_curated_pois(miles: float) -> int:
    if miles < POI_DENSITY_SHORT_LEG_MILES:
        return 1
    if miles <= POI_DENSITY_MEDIUM_LEG_MILES:
        return 2
    return 3


def minimum_fuel_capable_pois(miles: float) -> int:
    if miles < POI_DENSITY_SHORT_LEG_MILES:
        return 0
    return 1


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
