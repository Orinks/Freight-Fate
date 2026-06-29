"""Small NPC traffic bubble around the player's truck."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from ..data.world import Leg, Route
from .hos import is_night
from .trip_models import RUSH_HOUR_WINDOWS, TRAFFIC_LOOKAHEAD_MI, TrafficContext


@dataclass
class TrafficVehicle:
    key: str
    position_mi: float
    speed_mph: float
    target_speed_mph: float
    relative_lane: int
    intent: str
    vehicle_class: str
    length_mi: float = 0.25

    @property
    def at_mi(self) -> float:
        return self.position_mi

    @property
    def end_mi(self) -> float:
        return self.position_mi + self.length_mi

    @property
    def lane_text(self) -> str:
        if self.relative_lane < 0:
            return "left lane"
        if self.relative_lane > 0:
            return "right lane"
        return "your lane"

    @property
    def behavior(self) -> str:
        return self.intent

    @property
    def reason(self) -> str:
        return {
            "following": "steady traffic",
            "merging": "merging traffic",
            "braking": "brake lights ahead",
            "passing": "passing traffic",
        }.get(self.intent, "traffic ahead")


@dataclass(frozen=True)
class TrafficSituation:
    kind: str
    vehicle: TrafficVehicle
    message: str
    interrupt: bool = False


class TrafficManager:
    def __init__(
        self,
        *,
        route: Route,
        truck,
        weather,
        leg_starts: list[float],
        seed: int,
        start_hour: float,
        hazard_scale: float,
        imperial: bool,
    ) -> None:
        self.route = route
        self.truck = truck
        self.weather = weather
        self.leg_starts = leg_starts
        self.seed = seed
        self.start_hour = start_hour
        self.hazard_scale = hazard_scale
        self.imperial = imperial
        self.vehicles: list[TrafficVehicle] = []
        self.announced_vehicle_keys: set[str] = set()

    def lead_vehicle(
        self, position_mi: float, truck_speed_mph: float
    ) -> TrafficContext | None:
        nearest: tuple[float, TrafficVehicle] | None = None
        for vehicle in self.vehicles:
            if vehicle.relative_lane != 0:
                continue
            gap_mi = vehicle.position_mi - position_mi
            if gap_mi < 0 or gap_mi > TRAFFIC_LOOKAHEAD_MI:
                continue
            if nearest is None or gap_mi < nearest[0]:
                nearest = (gap_mi, vehicle)

        if nearest is None:
            return None

        gap_mi, vehicle = nearest
        closing_mph = max(0.0, truck_speed_mph - vehicle.speed_mph)
        return TrafficContext(lead=vehicle, gap_mi=gap_mi, closing_mph=closing_mph)


__all__ = [
    "Leg",
    "RUSH_HOUR_WINDOWS",
    "TrafficManager",
    "TrafficSituation",
    "TrafficVehicle",
    "hashlib",
    "is_night",
    "random",
]
