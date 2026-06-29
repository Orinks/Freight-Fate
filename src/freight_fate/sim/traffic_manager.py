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
        self.leg_starts = list(leg_starts)
        self.seed = seed
        self.start_hour = start_hour
        self.hazard_scale = hazard_scale
        self.imperial = imperial
        self.vehicles: list[TrafficVehicle] = []
        self.announced_vehicle_keys: set[str] = set()

    def _seed_key(self) -> str:
        route_key = "|".join(
            f"{city}:{leg.highway}:{leg.miles:.1f}"
            for city, leg in zip(self.route.cities, self.route.legs, strict=False)
        )
        return f"traffic-manager:{self.seed}:{route_key}"

    def _rng(self) -> random.Random:
        digest = hashlib.sha256(self._seed_key().encode("utf-8")).hexdigest()
        return random.Random(int(digest[:16], 16))

    def _rush_hour_traffic_bias(self, leg: Leg) -> float:
        if not any(start <= self.start_hour < end for start, end in RUSH_HOUR_WINDOWS):
            return 0.0
        return 0.14 if leg.checkpoints else 0.06

    def _leg_density(self, leg: Leg, night: bool) -> float:
        metro_bias = 0.18 if leg.checkpoints else 0.0
        night_bias = -0.08 if night else 0.0
        rush_bias = self._rush_hour_traffic_bias(leg)
        density = min(
            0.86,
            max(
                0.05,
                0.22
                + leg.miles / 900.0
                + metro_bias
                + night_bias
                + rush_bias,
            ),
        )
        return density * self.hazard_scale

    def _weather_slowdown(self) -> float:
        effects = self.weather.effects
        return max(
            0.0,
            min(
                14.0,
                (1.0 - effects.grip) * 20.0
                + max(0.0, 3.0 - effects.visibility_mi) * 1.4,
            ),
        )

    def spawn_initial_traffic(self) -> None:
        rng = self._rng()
        vehicles: list[TrafficVehicle] = []
        weather_slowdown = self._weather_slowdown()
        night = is_night(self.start_hour)
        for leg_index, (start, leg) in enumerate(
            zip(self.leg_starts, self.route.legs, strict=True)
        ):
            if leg.miles < 35.0:
                continue
            density = self._leg_density(leg, night)
            slots = max(1, int(leg.miles / 85.0))
            for slot in range(slots):
                if rng.random() > min(0.92, density + 0.18):
                    continue
                span = leg.miles / slots
                low = max(4.0, slot * span + 8.0)
                high = min(leg.miles - 6.0, (slot + 1) * span + 4.0)
                if high <= low:
                    continue
                intent = rng.choices(
                    ("cruising", "following", "merging", "braking", "passing"),
                    weights=(3.0, 1.5, 1.2, 1.0, 1.1),
                )[0]
                vehicle_class = rng.choices(
                    ("car", "box truck", "semi", "service vehicle"),
                    weights=(5.0, 1.4, 2.0, 0.3),
                )[0]
                base_speed = {
                    "cruising": rng.uniform(52.0, 64.0),
                    "following": rng.uniform(42.0, 55.0),
                    "merging": rng.uniform(38.0, 52.0),
                    "braking": rng.uniform(35.0, 48.0),
                    "passing": rng.uniform(62.0, 75.0),
                }[intent]
                rush_slowdown = (
                    rng.uniform(4.0, 10.0) if self._rush_hour_traffic_bias(leg) else 0.0
                )
                speed = max(25.0, base_speed - weather_slowdown - rush_slowdown)
                lane = -1 if intent == "passing" else 0
                if intent == "merging":
                    lane = 1
                vehicles.append(
                    TrafficVehicle(
                        key=f"traffic:{leg_index}:{slot}:{intent}",
                        position_mi=start + rng.uniform(low, high),
                        speed_mph=speed,
                        target_speed_mph=speed,
                        relative_lane=lane,
                        intent=intent,
                        vehicle_class=vehicle_class,
                    )
                )
        self.vehicles = sorted(vehicles, key=lambda vehicle: vehicle.position_mi)

    def lead_vehicle(
        self, position_mi: float, truck_speed_mph: float
    ) -> TrafficContext | None:
        # TrafficVehicle intentionally matches the NPCVehicle runtime surface
        # used by TrafficContext while the traffic bubble is split out.
        nearest: tuple[float, TrafficVehicle] | None = None
        for vehicle in self.vehicles:
            if vehicle.relative_lane != 0:
                continue
            gap_mi = vehicle.position_mi - position_mi
            if gap_mi < -vehicle.length_mi or gap_mi > TRAFFIC_LOOKAHEAD_MI:
                continue
            context_gap_mi = max(0.0, gap_mi)
            if nearest is None or context_gap_mi < nearest[0]:
                nearest = (context_gap_mi, vehicle)

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
