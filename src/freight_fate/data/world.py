"""World model: cities, freight locations, and the highway network.

Loads ``world.json`` and exposes a graph with Dijkstra-based route finding.
Route options are produced by re-running the search with already-used legs
penalized, giving genuinely different alternatives (fastest vs. detour).
"""

from __future__ import annotations

import heapq
import json
from dataclasses import dataclass
from pathlib import Path

WORLD_PATH = Path(__file__).parent / "world.json"


@dataclass(frozen=True)
class Location:
    name: str
    type: str
    cargo: tuple[str, ...]

    @property
    def label(self) -> str:
        return LOCATION_TYPE_LABELS.get(self.type, self.type.replace("_", " "))

    @property
    def spoken_name(self) -> str:
        return f"{self.label}: {self.name}"


STOP_TYPE_LABELS = {
    "truck_stop": "truck stop",
    "travel_center": "travel center",
    "service_plaza": "service plaza",
    "public_rest_area": "public rest area",
    "truck_parking": "truck parking",
    "weigh_station": "weigh station",
}

FREIGHT_LOCATION_TYPES = {
    "air_cargo",
    "distribution",
    "food_terminal",
    "industrial_park",
    "intermodal",
    "manufacturing",
    "port",
    "rail",
    "retail_distribution",
    "terminal",
    "warehouse",
}

LOCATION_TYPE_LABELS = {
    "air_cargo": "air cargo area",
    "distribution": "distribution center",
    "food_terminal": "food terminal",
    "industrial_park": "industrial park",
    "intermodal": "intermodal yard",
    "manufacturing": "manufacturing plant",
    "port": "port",
    "rail": "rail yard",
    "retail_distribution": "retail distribution hub",
    "terminal": "freight terminal",
    "warehouse": "warehouse",
}


@dataclass(frozen=True)
class Stop:
    name: str
    type: str = "travel_center"

    @property
    def label(self) -> str:
        return STOP_TYPE_LABELS.get(self.type, "stop")

    @property
    def spoken_name(self) -> str:
        return f"{self.label}: {self.name}"


@dataclass(frozen=True)
class City:
    name: str
    state: str
    region: str
    locations: tuple[Location, ...]
    lat: float = 0.0
    lon: float = 0.0


@dataclass(frozen=True)
class Leg:
    a: str
    b: str
    miles: float
    highway: str
    terrain: str  # flat | hills | mountain
    stops: tuple[Stop, ...]

    def other(self, city: str) -> str:
        return self.b if city == self.a else self.a


@dataclass
class Route:
    """An ordered chain of legs from start to end."""

    cities: list[str]
    legs: list[Leg]

    @property
    def miles(self) -> float:
        return sum(leg.miles for leg in self.legs)

    @property
    def highways(self) -> list[str]:
        out: list[str] = []
        for leg in self.legs:
            if not out or out[-1] != leg.highway:
                out.append(leg.highway)
        return out

    @property
    def stops(self) -> list[str]:
        return [s.name for leg in self.legs for s in leg.stops]

    @property
    def stop_details(self) -> list[Stop]:
        return [s for leg in self.legs for s in leg.stops]

    @property
    def terrain_summary(self) -> str:
        kinds = {leg.terrain for leg in self.legs}
        if kinds == {"flat"}:
            return "flat"
        if "mountain" in kinds:
            return "mountainous in places"
        return "rolling hills"

    def describe(self) -> str:
        via = " then ".join(self.highways)
        return (f"{self.miles:.0f} miles via {via}, "
                f"{len(self.legs)} leg{'s' if len(self.legs) != 1 else ''}, "
                f"terrain {self.terrain_summary}")


class World:
    def __init__(self, data: dict) -> None:
        self.cities: dict[str, City] = {}
        for name, c in data["cities"].items():
            locs = tuple(Location(loc["name"], loc["type"], tuple(loc["cargo"]))
                         for loc in c["locations"])
            self.cities[name] = City(name, c["state"], c["region"], locs,
                                     float(c.get("lat", 0.0)), float(c.get("lon", 0.0)))

        self.legs: list[Leg] = [
            Leg(leg["from"], leg["to"], float(leg["miles"]), leg["highway"],
                leg["terrain"], tuple(_parse_stop(s) for s in leg.get("stops", ())))
            for leg in data["legs"]
        ]
        self._adjacency: dict[str, list[Leg]] = {name: [] for name in self.cities}
        for leg in self.legs:
            self._adjacency[leg.a].append(leg)
            self._adjacency[leg.b].append(leg)

    @classmethod
    def load(cls, path: Path = WORLD_PATH) -> World:
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    def city_names(self) -> list[str]:
        return sorted(self.cities)

    def neighbors(self, city: str) -> list[Leg]:
        return self._adjacency[city]

    def shortest_route(self, start: str, end: str,
                       penalties: dict[Leg, float] | None = None) -> Route | None:
        """Dijkstra over leg miles, with optional per-leg penalty multipliers."""
        if start not in self.cities or end not in self.cities:
            raise KeyError(f"Unknown city: {start if start not in self.cities else end}")
        penalties = penalties or {}
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
                nxt = leg.other(city)
                cost = leg.miles * penalties.get(leg, 1.0)
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
        gracefully when a save references a road that no longer exists.
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

    def route_options(self, start: str, end: str, count: int = 3) -> list[Route]:
        """Up to ``count`` distinct routes, fastest first."""
        routes: list[Route] = []
        penalties: dict[Leg, float] = {}
        seen: set[tuple[str, ...]] = set()
        for _ in range(count * 2):
            route = self.shortest_route(start, end, penalties)
            if route is None:
                break
            key = tuple(route.cities)
            if key not in seen:
                seen.add(key)
                routes.append(route)
                if len(routes) >= count:
                    break
            for leg in route.legs:
                penalties[leg] = penalties.get(leg, 1.0) * 2.5
        routes.sort(key=lambda r: r.miles)
        return routes


_world: World | None = None


def _parse_stop(raw) -> Stop:
    if isinstance(raw, dict):
        name = str(raw.get("name", "")).strip()
        stop_type = str(raw.get("type", "")).strip() or _classify_stop(name)
        return Stop(name, stop_type)
    name = str(raw)
    return Stop(name, _classify_stop(name))


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


def get_world() -> World:
    """Shared world instance (the data is immutable)."""
    global _world
    if _world is None:
        _world = World.load()
    return _world
