"""World model: cities, freight locations, and the highway network.

Loads ``world.json`` and exposes a graph with Dijkstra-based route finding.
Route options are produced by re-running the search with already-used legs
penalized, giving genuinely different alternatives (fastest vs. detour).
"""

from __future__ import annotations

import heapq
import json
import zlib
from dataclasses import dataclass
from pathlib import Path

WORLD_PATH = Path(__file__).parent / "world.json"

# Alternate routes should feel like real dispatch choices, not graph leftovers.
# A little extra mileage is fine for traffic, weather, grades, or avoiding a
# metro corridor; hundreds of out-of-direction miles on a short lane are not.
ALTERNATE_ROUTE_EXTRA_RATIO = 0.22
ALTERNATE_ROUTE_MIN_EXTRA_MILES = 75.0
ALTERNATE_ROUTE_MAX_EXTRA_MILES = 550.0


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


@dataclass(frozen=True)
class HomeTerminal:
    name: str
    city: str
    state: str
    kind: str

    @property
    def label(self) -> str:
        return "company terminal" if self.kind == "terminal" else "company yard"

    @property
    def spoken_name(self) -> str:
        return f"{self.label}: {self.name}"

    @property
    def service_area(self) -> str:
        return f"{self.city}, {self.state}"


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

FACILITY_APPROACH_MILES = {
    "air_cargo": 7.0,
    "distribution": 4.0,
    "food_terminal": 3.5,
    "industrial_park": 5.0,
    "intermodal": 6.0,
    "manufacturing": 4.5,
    "port": 8.0,
    "rail": 5.5,
    "retail_distribution": 4.0,
    "terminal": 3.0,
    "warehouse": 3.5,
}

FACILITY_APPROACH_ROADS = {
    "air_cargo": "airport cargo access road",
    "distribution": "distribution center access road",
    "food_terminal": "food terminal access road",
    "industrial_park": "industrial park access road",
    "intermodal": "intermodal yard access road",
    "manufacturing": "plant access road",
    "port": "port access road",
    "rail": "rail yard access road",
    "retail_distribution": "retail distribution access road",
    "terminal": "terminal access road",
    "warehouse": "warehouse access road",
}


@dataclass(frozen=True)
class Stop:
    name: str
    at_mi: float
    type: str = "travel_center"
    source: str = ""

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

        self.legs: list[Leg] = []
        for leg in data["legs"]:
            miles = float(leg["miles"])
            stops = tuple(_parse_stop(s, miles, leg["from"], leg["to"])
                          for s in leg.get("stops", ()))
            self.legs.append(
                Leg(leg["from"], leg["to"], miles, leg["highway"],
                    leg["terrain"], stops)
            )
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

    def facility_location(self, city: str, location_name: str) -> Location:
        if city not in self.cities:
            raise KeyError(f"Unknown city: {city}")
        for location in self.cities[city].locations:
            if location.name == location_name:
                return location
        raise KeyError(f"Unknown facility in {city}: {location_name}")

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
        return HomeTerminal(f"{city} Company Yard", city, city_obj.state, "company_yard")

    def facility_approach_route(self, city: str, location_name: str) -> Route:
        """A short, drivable local route from the company terminal to a facility."""
        location = self.facility_location(city, location_name)
        base_miles = FACILITY_APPROACH_MILES.get(location.type, 4.0)
        seed = zlib.crc32(f"{city}:{location.name}:{location.type}".encode())
        offset = (seed % 7) * 0.25
        miles = round(base_miles + offset, 1)
        road = FACILITY_APPROACH_ROADS.get(location.type, "facility access road")
        leg = Leg(city, city, miles, road, "flat", ())
        return Route([city, city], [leg])

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
        best = self.shortest_route(start, end)
        if best is None:
            return routes
        max_miles = _max_alternate_miles(best.miles)
        for _ in range(count * 8):
            route = self.shortest_route(start, end, penalties)
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


def _parse_stop(raw, leg_miles: float, from_city: str, to_city: str) -> Stop:
    if not isinstance(raw, dict):
        raise ValueError(
            f"{from_city} to {to_city} stop {raw!r} is missing explicit at_mi"
        )
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"{from_city} to {to_city} has a stop without a name")
    if "at_mi" not in raw:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} is missing explicit at_mi"
        )
    at_mi = float(raw["at_mi"])
    if not 0.0 < at_mi < leg_miles:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has at_mi {at_mi}, "
            f"outside leg mileage 0-{leg_miles}"
        )
    stop_type = str(raw.get("type", "")).strip() or _classify_stop(name)
    if stop_type not in STOP_TYPE_LABELS:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has unknown type {stop_type!r}"
        )
    source = str(raw.get("source", "")).strip()
    return Stop(name, at_mi, stop_type, source)


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


def _max_alternate_miles(best_miles: float) -> float:
    extra = best_miles * ALTERNATE_ROUTE_EXTRA_RATIO
    extra = max(ALTERNATE_ROUTE_MIN_EXTRA_MILES,
                min(ALTERNATE_ROUTE_MAX_EXTRA_MILES, extra))
    return best_miles + extra


def get_world() -> World:
    """Shared world instance (the data is immutable)."""
    global _world
    if _world is None:
        _world = World.load()
    return _world
