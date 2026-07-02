# ruff: noqa: F403,F405
"""World model: cities, freight locations, and the highway network.

Loads indexed world data and exposes a graph with Dijkstra-based route finding.
Route options are produced by re-running the search with already-used legs
penalized, giving genuinely different alternatives (fastest vs. detour).
"""

from __future__ import annotations

import heapq
import json
from pathlib import Path

from .world_constants import *
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
    _market_tags_for_city,
    _merge_overlay,
    _parse_checkpoint,
    _parse_elevation_sample,
    _parse_grade_segment,
    _parse_interchange,
    _parse_location,
    _parse_route_point,
    _parse_speed_limits,
    _parse_state_crossing,
    _parse_state_mileage,
    _parse_stop,
    _parse_toll_event,
)
from .world_parsing import (
    minimum_curated_pois as minimum_curated_pois,
)
from .world_parsing import (
    minimum_fuel_capable_pois as minimum_fuel_capable_pois,
)
from .world_services import WorldServiceMixin

WORLD_PATH = Path(__file__).parent / "world.json"
WORLD_DATA_PATH = Path(__file__).parent / "world_data"
WORLD_INDEX_PATH = WORLD_DATA_PATH / "index.json"
# Alternate routes should feel like dispatch choices, not graph leftovers.
ALTERNATE_ROUTE_EXTRA_RATIO = 0.22
ALTERNATE_ROUTE_MIN_EXTRA_MILES = 75.0
ALTERNATE_ROUTE_MAX_EXTRA_MILES = 550.0


class World(WorldServiceMixin):
    def __init__(self, data: dict) -> None:
        self.cities: dict[str, City] = {}
        self._facilities_by_id: dict[str, Location] = {}
        self._city_service_data = load_city_service_data()
        self._facility_approaches = load_facility_approaches()
        self._facility_endpoints = load_facility_endpoints()
        self._local_approaches = load_local_approaches()
        self._local_geometries = load_local_geometries()
        for name, c in data["cities"].items():
            lat = float(c.get("lat", 0.0))
            lon = float(c.get("lon", 0.0))
            explicit_locs = tuple(_parse_location(loc, name, lat, lon) for loc in c["locations"])
            tags = _market_tags_for_city(name, c, explicit_locs)
            locs = _expand_market_locations(name, lat, lon, explicit_locs, tags)
            self._validate_city_locations(name, locs)
            self.cities[name] = City(name, c["state"], c["region"], locs, lat, lon, tags)

        self.legs: list[Leg] = []
        for leg in data["legs"]:
            miles = float(leg["miles"])
            stops = tuple(
                _parse_stop(s, miles, leg["from"], leg["to"]) for s in leg.get("stops", ())
            )
            corridor = leg.get("corridor", {})
            route_points = tuple(
                _parse_route_point(p, miles, leg["from"], leg["to"])
                for p in corridor.get("route_points", ())
            )
            elevation_samples = tuple(
                _parse_elevation_sample(s, miles, leg["from"], leg["to"])
                for s in corridor.get("elevation_samples", ())
            )
            grade_segments = tuple(
                _parse_grade_segment(s, miles, leg["from"], leg["to"])
                for s in corridor.get("grade_segments", ())
            )
            state_crossings = tuple(
                _parse_state_crossing(
                    c, miles, leg["from"], leg["to"], self.cities[leg["from"]].state
                )
                for c in corridor.get("state_crossings", ())
            )
            checkpoints = tuple(
                _parse_checkpoint(c, miles, leg["from"], leg["to"])
                for c in corridor.get("checkpoints", ())
            )
            state_miles = tuple(
                _parse_state_mileage(m, leg["from"], leg["to"])
                for m in corridor.get("state_miles", ())
            )
            toll_events = tuple(
                _parse_toll_event(e, miles, leg["from"], leg["to"], leg["highway"])
                for e in corridor.get("toll_events", ())
            )
            interchanges = tuple(
                _parse_interchange(x, miles, leg["from"], leg["to"], leg["highway"])
                for x in corridor.get("interchanges", ())
            )
            speed_limits = _parse_speed_limits(
                corridor.get("speed_limits", ()), miles, leg["from"], leg["to"]
            )
            self.legs.append(
                Leg(
                    leg["from"],
                    leg["to"],
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

        data = load_world_data(root)
        if overlay is not None and overlay.exists():
            data = _merge_overlay(data, json.loads(overlay.read_text(encoding="utf-8")))
        return cls(data)

    def city_names(self) -> list[str]:
        return sorted(self.cities)

    def neighbors(self, city: str) -> list[Leg]:
        return self._adjacency[city]

    def facility_location(self, city: str, location_name: str) -> Location:
        if city not in self.cities:
            raise KeyError(f"Unknown city: {city}")
        normalized_name = str(location_name or "").strip()
        for location in self.cities[city].locations:
            if location.name == normalized_name or location.id == normalized_name:
                return location
        if _is_legacy_market_name(city, normalized_name):
            return self.default_facility(city)
        raise KeyError(f"Unknown facility in {city}: {location_name}")

    def facility_by_id(self, facility_id: str) -> Location:
        try:
            return self._facilities_by_id[facility_id]
        except KeyError:
            raise KeyError(f"Unknown facility id: {facility_id}") from None

    def default_facility(self, city: str) -> Location:
        """Stable fallback for legacy jobs that only named a city."""
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
        city gets a stable fallback yard name.
        """
        if city not in self.cities:
            raise KeyError(f"Unknown city: {city}")
        city_obj = self.cities[city]
        for location in city_obj.locations:
            if location.type == "terminal":
                return HomeTerminal(location.name, city, city_obj.state, "terminal")
        for location in city_obj.locations:
            if location.type == "company_yard":
                return HomeTerminal(location.name, city, city_obj.state, "company_yard")
        return HomeTerminal(f"{city} Company Yard", city, city_obj.state, "company_yard")

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
