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
    "fuel_station": "truck fuel station",
    "service_plaza": "service plaza",
    "public_rest_area": "public rest area",
    "truck_parking": "truck parking",
    "weigh_station": "weigh station",
    "repair_shop": "repair shop",
}

POI_ACTIONS = {
    "park",
    "save",
    "break",
    "sleep",
    "fuel",
    "food",
    "repair",
    "roadside_assistance",
    "towing",
    "inspect",
}

RAW_POI_TEXT_MARKERS = (
    "osm_id",
    "openstreetmap id",
    "amenity=",
    "highway=",
    "operator=",
    "node/",
    "way/",
    "relation/",
)

DEFAULT_POI_ACTIONS = {
    "truck_stop": ("park", "save", "fuel", "food", "break", "sleep"),
    "travel_center": ("park", "save", "fuel", "food", "break", "sleep"),
    "fuel_station": ("park", "save", "fuel", "break"),
    "service_plaza": ("park", "save", "fuel", "food", "break"),
    "public_rest_area": ("park", "save", "break", "sleep"),
    "truck_parking": ("park", "save", "break", "sleep"),
    "weigh_station": ("inspect",),
    "repair_shop": ("park", "save", "repair"),
}

SOURCE_BACKED_POI_ACTIONS = {"repair", "roadside_assistance", "towing"}

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
    actions: tuple[str, ...] = ()
    services: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        return STOP_TYPE_LABELS.get(self.type, "stop")

    @property
    def spoken_name(self) -> str:
        return f"{self.label}: {self.name}"


@dataclass(frozen=True)
class RoutePoint:
    at_mi: float
    lat: float
    lon: float


@dataclass(frozen=True)
class ElevationSample:
    at_mi: float
    elevation_ft: float
    source: str = ""


@dataclass(frozen=True)
class GradeSegment:
    start_mi: float
    end_mi: float
    avg_grade_pct: float
    terrain: str
    source: str = ""


@dataclass(frozen=True)
class StateCrossing:
    at_mi: float
    from_state: str
    state: str
    place: str
    source: str = ""


@dataclass(frozen=True)
class RouteCheckpoint:
    name: str
    at_mi: float
    type: str = "place"
    state: str = ""
    highway: str = ""
    source: str = ""

    @property
    def label(self) -> str:
        if self.type == "highway_change":
            return "highway change"
        if self.type == "state_line":
            return "state line"
        return "corridor place"

    @property
    def spoken_name(self) -> str:
        return f"{self.label}: {self.name}"


@dataclass(frozen=True)
class StateMileage:
    state: str
    miles: float


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
    route_points: tuple[RoutePoint, ...] = ()
    elevation_samples: tuple[ElevationSample, ...] = ()
    grade_segments: tuple[GradeSegment, ...] = ()
    state_crossings: tuple[StateCrossing, ...] = ()
    checkpoints: tuple[RouteCheckpoint, ...] = ()
    state_miles: tuple[StateMileage, ...] = ()

    def other(self, city: str) -> str:
        return self.b if city == self.a else self.a

    def metadata_complete(self, from_state: str, to_state: str) -> bool:
        """True when a leg has enough real corridor data for new freight."""
        if len(self.route_points) < 2:
            return False
        if not self.checkpoints:
            return False
        if not self.state_miles:
            return False
        if len(self.elevation_samples) < 2 or not self.grade_segments:
            return False
        if not self.stops:
            return False
        if any(not stop.source or not stop.actions for stop in self.stops):
            return False
        return from_state == to_state or bool(self.state_crossings)


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
    def state_crossings(self) -> list[StateCrossing]:
        return [c for leg in self.legs for c in leg.state_crossings]

    @property
    def checkpoints(self) -> list[RouteCheckpoint]:
        return [c for leg in self.legs for c in leg.checkpoints]

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

    def metadata_complete(self, world: World) -> bool:
        return all(world.leg_metadata_complete(leg) for leg in self.legs)


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
                _parse_state_crossing(c, miles, leg["from"], leg["to"],
                                      self.cities[leg["from"]].state)
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
            self.legs.append(
                Leg(leg["from"], leg["to"], miles, leg["highway"],
                    leg["terrain"], stops, route_points, elevation_samples,
                    grade_segments, state_crossings, checkpoints, state_miles)
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
                       penalties: dict[Leg, float] | None = None,
                       require_metadata: bool = False) -> Route | None:
        """Dijkstra over leg miles, with optional per-leg penalty multipliers.

        ``require_metadata`` is for new dispatchable freight. The default keeps
        the historical full graph available for legacy saves and map integrity
        checks while supported freight routes are enriched lane by lane.
        """
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
                if require_metadata and not self.leg_metadata_complete(leg):
                    continue
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

    def supported_route(self, start: str, end: str,
                        penalties: dict[Leg, float] | None = None) -> Route | None:
        return self.shortest_route(start, end, penalties, require_metadata=True)

    def supported_route_options(self, start: str, end: str,
                                count: int = 3) -> list[Route]:
        return self.route_options(start, end, count, require_metadata=True)

    def route_options(self, start: str, end: str, count: int = 3,
                      require_metadata: bool = False) -> list[Route]:
        """Up to ``count`` distinct routes, fastest first."""
        routes: list[Route] = []
        penalties: dict[Leg, float] = {}
        seen: set[tuple[str, ...]] = set()
        best = self.shortest_route(start, end, require_metadata=require_metadata)
        if best is None:
            return routes
        max_miles = _max_alternate_miles(best.miles)
        for _ in range(count * 8):
            route = self.shortest_route(start, end, penalties,
                                        require_metadata=require_metadata)
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
    lowered_name = name.lower()
    if any(marker in lowered_name for marker in RAW_POI_TEXT_MARKERS):
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} exposes raw OSM/source text"
        )
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
    actions = tuple(str(action).strip() for action in raw.get(
        "actions", DEFAULT_POI_ACTIONS[stop_type]))
    if not actions:
        raise ValueError(f"{from_city} to {to_city} stop {name!r} has no actions")
    unknown = sorted(set(actions) - POI_ACTIONS)
    if unknown:
        raise ValueError(
            f"{from_city} to {to_city} stop {name!r} has unknown actions {unknown}"
        )
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
        str(service).strip()
        for service in raw.get("services", ())
        if str(service).strip()
    )
    for action in SOURCE_BACKED_POI_ACTIONS & set(actions):
        if action not in services:
            raise ValueError(
                f"{from_city} to {to_city} stop {name!r} action {action!r} "
                "requires matching source-backed service metadata"
            )
        if not source:
            raise ValueError(
                f"{from_city} to {to_city} stop {name!r} action {action!r} "
                "requires a source note"
            )
    return Stop(name, at_mi, stop_type, source, actions, services)


def _parse_route_point(raw, leg_miles: float, from_city: str, to_city: str) -> RoutePoint:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} route point must be an object")
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, "route point",
                         allow_endpoints=True)
    lat = float(raw["lat"])
    lon = float(raw["lon"])
    if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
        raise ValueError(f"{from_city} to {to_city} route point has invalid coordinates")
    return RoutePoint(at_mi, lat, lon)


def _parse_elevation_sample(raw, leg_miles: float, from_city: str,
                            to_city: str) -> ElevationSample:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} elevation sample must be an object")
    at_mi = _parse_at_mi(raw, leg_miles, from_city, to_city, "elevation sample",
                         allow_endpoints=True)
    elevation_ft = float(raw["elevation_ft"])
    if not -300.0 <= elevation_ft <= 20_500.0:
        raise ValueError(
            f"{from_city} to {to_city} elevation sample has invalid elevation"
        )
    source = str(raw.get("source", "")).strip()
    return ElevationSample(at_mi, elevation_ft, source)


def _parse_grade_segment(raw, leg_miles: float, from_city: str,
                         to_city: str) -> GradeSegment:
    if not isinstance(raw, dict):
        raise ValueError(f"{from_city} to {to_city} grade segment must be an object")
    if "start_mi" not in raw:
        raise ValueError(
            f"{from_city} to {to_city} grade segment is missing explicit start_mi"
        )
    start_mi = float(raw["start_mi"])
    if not 0.0 <= start_mi <= leg_miles:
        raise ValueError(
            f"{from_city} to {to_city} grade segment start has start_mi {start_mi}, "
            f"outside leg mileage 0-{leg_miles}"
        )
    end_mi = float(raw["end_mi"])
    if not 0.0 <= end_mi <= leg_miles or end_mi <= start_mi:
        raise ValueError(
            f"{from_city} to {to_city} grade segment has invalid range "
            f"{start_mi}-{end_mi}"
        )
    avg_grade_pct = float(raw["avg_grade_pct"])
    if not -15.0 <= avg_grade_pct <= 15.0:
        raise ValueError(
            f"{from_city} to {to_city} grade segment has unrealistic grade "
            f"{avg_grade_pct}"
        )
    terrain = str(raw.get("terrain", "")).strip() or "flat"
    if terrain not in {"flat", "hills", "mountain"}:
        raise ValueError(
            f"{from_city} to {to_city} grade segment has unknown terrain {terrain!r}"
        )
    source = str(raw.get("source", "")).strip()
    return GradeSegment(start_mi, end_mi, avg_grade_pct, terrain, source)


def _parse_state_crossing(raw, leg_miles: float, from_city: str, to_city: str,
                          default_from_state: str) -> StateCrossing:
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


def _parse_checkpoint(raw, leg_miles: float, from_city: str,
                      to_city: str) -> RouteCheckpoint:
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


def _parse_at_mi(raw: dict, leg_miles: float, from_city: str, to_city: str,
                 label: str, *, allow_endpoints: bool = False) -> float:
    if "at_mi" not in raw:
        raise ValueError(f"{from_city} to {to_city} {label} is missing explicit at_mi")
    at_mi = float(raw["at_mi"])
    in_range = 0.0 <= at_mi <= leg_miles if allow_endpoints else 0.0 < at_mi < leg_miles
    if not in_range:
        raise ValueError(
            f"{from_city} to {to_city} {label} has at_mi {at_mi}, "
            f"outside leg mileage 0-{leg_miles}"
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
