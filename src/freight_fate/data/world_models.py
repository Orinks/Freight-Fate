# ruff: noqa: F403,F405,F821
from __future__ import annotations

from dataclasses import dataclass

from .world_constants import *


@dataclass(frozen=True)
class Location:
    name: str
    type: str
    cargo: tuple[str, ...]
    id: str = ""
    city: str = ""
    locality: str = ""
    roles: tuple[str, ...] = ("shipper", "receiver")
    ships: tuple[str, ...] = ()
    receives: tuple[str, ...] = ()
    lat: float = 0.0
    lon: float = 0.0
    traits: tuple[str, ...] = ()
    source_note: str = ""
    spoken: str = ""
    template: bool = False
    min_level: int = 1

    @property
    def label(self) -> str:
        return LOCATION_TYPE_LABELS.get(self.type, self.type.replace("_", " "))

    @property
    def spoken_name(self) -> str:
        return self.spoken or f"{self.label}: {self.name}"

    @property
    def display_name(self) -> str:
        return self.name


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


@dataclass(frozen=True)
class CityService:
    key: str
    name: str
    city: str
    state: str
    kind: str
    source_note: str
    lat: float = 0.0
    lon: float = 0.0
    approach_miles: float = 0.0
    approach_road: str = ""
    source_type: str = "fallback"
    source_ref: str = ""
    fallback: bool = True
    fallback_reason: str = ""

    @property
    def label(self) -> str:
        return CITY_SERVICE_LABELS.get(self.kind, self.kind.replace("_", " "))

    @property
    def spoken_name(self) -> str:
        return f"{self.label}: {self.name}"


@dataclass(frozen=True)
class FacilityEndpoint:
    facility_id: str
    city: str
    state: str
    facility_name: str
    facility_type: str
    endpoint_name: str
    source_type: str
    source_note: str
    lat: float = 0.0
    lon: float = 0.0
    approach_miles: float = 0.0
    approach_road: str = ""
    source_ref: str = ""
    source_backed: bool = False
    fallback: bool = True
    fallback_reason: str = ""
    nearest_road_context: bool = False
    turn_level_geometry: bool = False
    gate_hint: bool = False
    yard_hint: bool = False
    dock_hint: bool = False
    mapping: str = ""


@dataclass(frozen=True)
class Stop:
    name: str
    at_mi: float
    type: str = "travel_center"
    source: str = ""
    actions: tuple[str, ...] = ()
    services: tuple[str, ...] = ()
    parking: str = "unknown"
    directions: tuple[str, ...] = ("both",)
    curation: str = "curated"

    @property
    def label(self) -> str:
        return STOP_TYPE_LABELS.get(self.type, "stop")

    @property
    def spoken_name(self) -> str:
        return f"{self.label}: {self.name}"

    @property
    def parking_label(self) -> str:
        return PARKING_CERTAINTY_LABELS[self.parking]

    @property
    def curated(self) -> bool:
        return self.curation == "curated"

    def applies_to_direction(self, forward: bool) -> bool:
        if "both" in self.directions:
            return True
        return ("forward" if forward else "reverse") in self.directions


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
class SpeedLimitSample:
    """A posted speed limit in effect from ``at_mi`` until the next sample.

    Baked from real OpenStreetMap ``maxspeed`` tags at build time (see
    ``tools/enrich_routes.py``) and stored already normalized to mph, so the
    runtime never sees a raw OSM string. The samples form a step function along
    the leg: the limit at any mile is the last sample whose ``at_mi`` is at or
    before it. ``hgv`` marks a truck-specific limit (``maxspeed:hgv``)."""

    at_mi: float
    mph: float
    source: str = ""
    hgv: bool = False


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
class TollEvent:
    name: str
    at_mi: float
    road: str
    authority: str
    method: str
    amount: float
    estimated: bool = True
    source: str = ""

    @property
    def method_label(self) -> str:
        return TOLL_METHOD_LABELS.get(self.method, self.method.replace("_", " "))

    @property
    def spoken_name(self) -> str:
        return f"toll point: {self.name}"


@dataclass(frozen=True)
class LocalApproach:
    target_id: str
    target_type: str
    city: str
    name: str
    approach_miles: float
    road: str
    source_type: str
    estimated: bool
    fallback: bool = False
    fallback_reason: str = ""
    distance_to_road_mi: float = 0.0
    turn_segments: tuple[str, ...] = ()


@dataclass(frozen=True)
class LocalGeometrySegment:
    road: str
    miles: float
    cue: str
    speed_mph: float = 25.0


@dataclass(frozen=True)
class LocalGeometry:
    target_id: str
    target_type: str
    city: str
    name: str
    turn_level: bool
    source_type: str
    estimated: bool
    fallback: bool
    fallback_reason: str
    total_miles: float
    segments: tuple[LocalGeometrySegment, ...] = ()


@dataclass(frozen=True)
class Interchange:
    """A highway exit/junction along a leg, sourced from OpenStreetMap."""

    at_mi: float
    exit_ref: str = ""
    name: str = ""
    destinations: tuple[str, ...] = ()
    via: str = ""
    highway: str = ""
    source: str = ""

    @property
    def spoken_phrase(self) -> str:
        """Lower-case lead phrase for GPS announcements."""
        head = f"exit {self.exit_ref}" if self.exit_ref else "exit"
        parts = [head]
        via = _format_route_ref(self.via)
        if via:
            parts.append(f"for {via}")
        dest = _join_destinations(_destinations_without_via(self.via, self.destinations))
        if dest:
            parts.append(f"toward {dest}")
        elif self.name and not self.exit_ref:
            parts.append(f"for {self.name}")
        return " ".join(parts)

    @property
    def near_phrase(self) -> str:
        phrase = self.spoken_phrase
        return f"{phrase[0].upper()}{phrase[1:]} now."

    @property
    def exit_label(self) -> str:
        return f"exit {self.exit_ref}" if self.exit_ref else ""


def _format_route_ref(value: str) -> str:
    out: list[str] = []
    for chunk in str(value).split(";"):
        ref = " ".join(chunk.split())
        if not ref:
            continue
        parts = ref.split(" ")
        if len(parts) >= 2 and parts[1][:1].isdigit():
            parts[0:2] = [f"{parts[0]}-{parts[1]}"]
        out.append(" ".join(parts))
    return " and ".join(out)


def _route_token(value: str) -> str:
    import re

    match = re.match(r"\s*((?:I|US|[A-Za-z]{2})[-\s]?\d+)", str(value).strip())
    return re.sub(r"[-\s]", "", match.group(1)).upper() if match else ""


def _destinations_without_via(via: str, destinations: tuple[str, ...]) -> tuple[str, ...]:
    token = _route_token(via)
    if not token:
        return destinations
    return tuple(d for d in destinations if _route_token(d) != token)


def _join_destinations(destinations: tuple[str, ...]) -> str:
    items = [d for d in destinations if d]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"



@dataclass(frozen=True)
class City:
    name: str
    state: str
    region: str
    locations: tuple[Location, ...]
    lat: float = 0.0
    lon: float = 0.0
    market_tags: tuple[str, ...] = ()


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
    toll_events: tuple[TollEvent, ...] = ()
    interchanges: tuple[Interchange, ...] = ()
    speed_limits: tuple[SpeedLimitSample, ...] = ()

    def other(self, city: str) -> str:
        return self.b if city == self.a else self.a

    def metadata_complete(self, from_state: str, to_state: str) -> bool:
        """True when a leg has enough real corridor data to be dispatchable.

        Dispatch gates on *routing* completeness: route geometry, elevation and
        grade, state mileage, and a state crossing when the endpoints differ --
        all of which the ORS driving-hgv pipeline produces automatically, so the
        map can scale without hand work. Curated truck-stop POIs are an additive
        quality layer (auto-sourced; see the coverage report's POI/fuel
        advisory), not a dispatch requirement: a stop-less leg stays playable via
        the HOS fallbacks (roadside fuel rescue, emergency shoulder sleep). POI
        data that *is* present is still validated at load by ``_parse_stop``.
        """
        if len(self.route_points) < 2:
            return False
        if not self.checkpoints:
            return False
        if not self.state_miles:
            return False
        if len(self.elevation_samples) < 2 or not self.grade_segments:
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
        return [s.name for leg in self.legs for s in leg.stops if s.curated]

    @property
    def stop_details(self) -> list[Stop]:
        return [s for leg in self.legs for s in leg.stops if s.curated]

    @property
    def raw_stop_details(self) -> list[Stop]:
        return [s for leg in self.legs for s in leg.stops]

    @property
    def state_crossings(self) -> list[StateCrossing]:
        return [c for leg in self.legs for c in leg.state_crossings]

    @property
    def toll_events(self) -> list[TollEvent]:
        return [event for leg in self.legs for event in leg.toll_events]

    @property
    def estimated_tolls(self) -> float:
        return sum(event.amount for event in self.toll_events)

    @property
    def checkpoints(self) -> list[RouteCheckpoint]:
        return [c for leg in self.legs for c in leg.checkpoints]

    @property
    def interchanges(self) -> list[Interchange]:
        return [x for leg in self.legs for x in leg.interchanges]

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


__all__ = [name for name in globals() if not name.startswith("__")]
