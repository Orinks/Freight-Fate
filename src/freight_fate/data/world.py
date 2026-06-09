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


@dataclass(frozen=True)
class City:
    name: str
    state: str
    region: str
    locations: tuple[Location, ...]


@dataclass(frozen=True)
class Leg:
    a: str
    b: str
    miles: float
    highway: str
    terrain: str  # flat | hills | mountain
    stops: tuple[str, ...]

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
            self.cities[name] = City(name, c["state"], c["region"], locs)

        self.legs: list[Leg] = [
            Leg(leg["from"], leg["to"], float(leg["miles"]), leg["highway"],
                leg["terrain"], tuple(leg.get("stops", ())))
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


def get_world() -> World:
    """Shared world instance (the data is immutable)."""
    global _world
    if _world is None:
        _world = World.load()
    return _world
