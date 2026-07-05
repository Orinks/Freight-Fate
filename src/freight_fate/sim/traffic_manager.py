"""Small NPC traffic bubble around the player's truck."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from ..data.world import Leg, Route
from .hos import is_night
from .trip_models import (
    RUSH_HOUR_WINDOWS,
    TRAFFIC_LOOKAHEAD_MI,
    PatrolWindow,
    TrafficContext,
)


@dataclass
class TrafficVehicle:
    """One NPC in the traffic bubble.

    ``lane`` is the absolute lane index (0 = right lane, counting leftward),
    matching the player's ``LaneKeeping.lane``. ``relative_lane`` keeps the
    legacy spoken-text surface (negative = left of the player) and is
    recomputed against the player's lane every manager update."""

    key: str
    position_mi: float
    speed_mph: float
    target_speed_mph: float
    relative_lane: int
    intent: str
    vehicle_class: str
    length_mi: float = 0.25
    lane: int = 0

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
        return {
            "cruising": "steady_truck",
            "following": "slow_car",
            "merging": "merging_vehicle",
            "braking": "braking_traffic",
            "passing": "passing_vehicle",
        }.get(self.intent, self.intent)

    @property
    def reason(self) -> str:
        if self.vehicle_class == "state trooper":
            return "state trooper ahead"
        return {
            "cruising": "steady truck traffic",
            "following": "slow car ahead",
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
        # The driving state mirrors the player's discrete lane here each
        # frame so same-lane checks and spoken relative lanes stay honest.
        self.player_lane = 0

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
                0.22 + leg.miles / 900.0 + metro_bias + night_bias + rush_bias,
            ),
        )
        return density * self.hazard_scale

    def _weather_slowdown(self) -> float:
        effects = self.weather.effects
        return max(
            0.0,
            min(
                14.0,
                (1.0 - effects.grip) * 20.0 + max(0.0, 3.0 - effects.visibility_mi) * 1.4,
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
                rush_slowdown = rng.uniform(4.0, 10.0) if self._rush_hour_traffic_bias(leg) else 0.0
                speed = max(25.0, base_speed - weather_slowdown - rush_slowdown)
                # Passing traffic lives in the left lane; everyone else --
                # including vehicles merging in from a ramp -- holds the
                # right lane, where trucks are supposed to be.
                lane = 1 if intent == "passing" else 0
                vehicles.append(
                    TrafficVehicle(
                        key=f"traffic:{leg_index}:{slot}:{intent}",
                        position_mi=start + rng.uniform(low, high),
                        speed_mph=speed,
                        target_speed_mph=speed,
                        relative_lane=-lane,
                        intent=intent,
                        vehicle_class=vehicle_class,
                        lane=lane,
                    )
                )
        self.vehicles = sorted(vehicles, key=lambda vehicle: vehicle.position_mi)

    def add_patrol_traffic(self, patrols: list[PatrolWindow]) -> None:
        existing_keys = {vehicle.key for vehicle in self.vehicles}
        for patrol in patrols:
            key = f"trooper:{patrol.start_mi:.3f}:{patrol.end_mi:.3f}:{patrol.reason}"
            if key in existing_keys:
                continue
            span = max(0.1, patrol.end_mi - patrol.start_mi)
            position = patrol.start_mi + min(0.8, span / 3.0)
            speed = 50.0 if "work zone" in patrol.reason else 62.0
            self.vehicles.append(
                TrafficVehicle(
                    key=key,
                    position_mi=position,
                    speed_mph=speed,
                    target_speed_mph=speed,
                    relative_lane=0,
                    intent="cruising",
                    vehicle_class="state trooper",
                )
            )
            existing_keys.add(key)
        self.vehicles.sort(key=lambda vehicle: vehicle.position_mi)

    def lead_vehicle(self, position_mi: float, truck_speed_mph: float) -> TrafficContext | None:
        # TrafficVehicle intentionally matches the NPCVehicle runtime surface
        # used by TrafficContext while the traffic bubble is split out.
        nearest: tuple[float, TrafficVehicle] | None = None
        for vehicle in self.vehicles:
            if vehicle.lane != self.player_lane:
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

    def _gap_text(self, miles: float) -> str:
        if self.imperial:
            return f"{miles:.1f} miles"
        return f"{miles * 1.609344:.1f} kilometers"

    def _speed_value(self, mph: float) -> str:
        if self.imperial:
            return f"{mph:.0f} miles per hour"
        return f"{mph * 1.609344:.0f} kilometers per hour"

    def _vehicle_intent(self, vehicle) -> str:
        intent = getattr(vehicle, "intent", None)
        if intent is not None:
            return intent
        return {
            "steady_truck": "cruising",
            "slow_car": "following",
            "merging_vehicle": "merging",
            "braking_traffic": "braking",
            "passing_vehicle": "passing",
        }.get(getattr(vehicle, "behavior", ""), "cruising")

    def _vehicle_class(self, vehicle) -> str:
        return getattr(vehicle, "vehicle_class", "vehicle")

    def inject_congestion(self, zone, *, position_mi: float) -> None:
        """Fill an activating congestion zone with slow vehicles ahead.

        Both lanes get traffic pacing the zone's prevailing speed, so the jam
        is heard and felt through the existing lead-vehicle machinery -- and a
        dodge into the next lane over meets metal there too."""
        key_base = f"congestion:{zone.start_mi:.1f}"
        if any(vehicle.key.startswith(key_base) for vehicle in self.vehicles):
            return
        rng = random.Random(
            int(hashlib.sha256(f"{self.seed}:{key_base}".encode()).hexdigest()[:12], 16)
        )
        pace = max(10.0, float(zone.limit_mph))
        anchor = max(position_mi + 0.25, zone.start_mi + 0.2)
        added: list[TrafficVehicle] = []
        for i in range(rng.randint(3, 5)):
            lane = i % 2
            speed = max(6.0, pace + rng.uniform(-9.0, 4.0))
            added.append(
                TrafficVehicle(
                    key=f"{key_base}:{i}",
                    position_mi=anchor + i * rng.uniform(0.25, 0.6),
                    speed_mph=speed,
                    target_speed_mph=speed,
                    relative_lane=self.player_lane - lane,
                    intent="braking" if i == 0 else rng.choice(("following", "cruising")),
                    vehicle_class=rng.choice(("car", "car", "semi", "box truck")),
                    lane=lane,
                )
            )
        self.vehicles.extend(added)
        self.vehicles.sort(key=lambda vehicle: vehicle.position_mi)

    def vehicle_in_lane(
        self,
        position_mi: float,
        lane: int,
        *,
        ahead_mi: float = 0.35,
        behind_mi: float = 0.15,
    ) -> TrafficVehicle | None:
        """The nearest vehicle occupying ``lane`` beside or just ahead of the
        player -- the mirror check before a lane change or a hazard dodge."""
        nearest: TrafficVehicle | None = None
        nearest_gap = float("inf")
        for vehicle in self.vehicles:
            if vehicle.lane != lane:
                continue
            gap = vehicle.position_mi - position_mi
            if -behind_mi - vehicle.length_mi <= gap <= ahead_mi:
                distance = abs(max(0.0, gap))
                if distance < nearest_gap:
                    nearest, nearest_gap = vehicle, distance
        return nearest

    def update(self, *, dt: float, position_mi: float, time_scale: float) -> None:
        game_hours = dt * time_scale / 3600.0
        kept: list[TrafficVehicle] = []
        for vehicle in self.vehicles:
            gap = vehicle.position_mi - position_mi
            intent = self._vehicle_intent(vehicle)
            vehicle.relative_lane = self.player_lane - vehicle.lane
            if intent == "braking" and 0.0 <= gap <= 1.8:
                vehicle.target_speed_mph = max(30.0, vehicle.target_speed_mph - 8.0 * dt)
            delta = vehicle.target_speed_mph - vehicle.speed_mph
            vehicle.speed_mph += max(-6.0 * dt, min(4.0 * dt, delta))
            vehicle.position_mi += max(0.0, vehicle.speed_mph) * game_hours
            if vehicle.position_mi - position_mi >= -2.0:
                kept.append(vehicle)
        self.vehicles = sorted(kept, key=lambda vehicle: vehicle.position_mi)

    def next_situation(
        self, *, position_mi: float, truck_speed_mph: float
    ) -> TrafficSituation | None:
        context = self.lead_vehicle(
            position_mi=position_mi,
            truck_speed_mph=truck_speed_mph,
        )
        if context is None or context.gap_mi > 2.2:
            return None
        vehicle = context.lead
        if vehicle.key in self.announced_vehicle_keys:
            return None
        gap = self._gap_text(context.gap_mi)
        speed = self._speed_value(vehicle.speed_mph)
        intent = self._vehicle_intent(vehicle)
        vehicle_class = self._vehicle_class(vehicle)
        if intent == "merging":
            message = (
                f"Merging {vehicle_class} {gap} ahead. Hold your lane, "
                f"leave a gap, and be ready for {speed}."
            )
            kind = "merging"
        elif intent == "braking":
            message = f"Brake lights {gap} ahead. Ease down and leave room for {speed}."
            kind = "braking"
        elif intent == "following":
            message = f"Slow {vehicle_class} {gap} ahead. Be ready near {speed}."
            kind = "following"
        else:
            return None
        self.announced_vehicle_keys.add(vehicle.key)
        return TrafficSituation(kind, vehicle, message, interrupt=True)


__all__ = [
    "Leg",
    "PatrolWindow",
    "RUSH_HOUR_WINDOWS",
    "TrafficManager",
    "TrafficSituation",
    "TrafficVehicle",
    "hashlib",
    "is_night",
    "random",
]
