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
