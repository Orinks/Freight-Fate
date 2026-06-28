"""Traffic and patrol lookup helpers for trip simulation."""

from __future__ import annotations

import hashlib
import random

from ..data.world import Leg
from .hos import is_night
from .trip_models import (
    RUSH_HOUR_WINDOWS,
    TRAFFIC_LOOKAHEAD_MI,
    TRAFFIC_PRESSURE_LOOKAHEAD_MI,
    NavigationCue,
    NPCVehicle,
    PatrolWindow,
    TrafficContext,
    TrafficPressure,
    TripEventKind,
)

NPC_TRAFFIC_LOOKAHEAD_MI = 2.2


class TripTrafficMixin:
    def _npc_seed_key(self) -> str:
        route_key = "|".join(
            f"{city}:{leg.highway}:{leg.miles:.1f}"
            for city, leg in zip(self.route.cities, self.route.legs, strict=False)
        )
        return (
            f"npc:{getattr(self, '_seed', None)}:{route_key}:"
            f"{self.start_hour:.1f}:{self.weather.current.value}"
        )

    def _npc_rng(self) -> random.Random:
        digest = hashlib.sha256(self._npc_seed_key().encode("utf-8")).hexdigest()
        return random.Random(int(digest[:16], 16))

    def _place_npc_traffic(self) -> list[NPCVehicle]:
        rng = self._npc_rng()
        vehicles: list[NPCVehicle] = []
        effects = self.weather.effects
        weather_slowdown = max(
            0.0,
            min(14.0, (1.0 - effects.grip) * 20.0
                + max(0.0, 3.0 - effects.visibility_mi) * 1.4),
        )
        night = is_night(self.start_hour)
        for leg_index, (start, leg) in enumerate(
            zip(self._leg_starts, self.route.legs, strict=True)
        ):
            if leg.miles < 35.0:
                continue
            density = self._leg_traffic_density(leg, weather_slowdown / 100.0, night)
            slots = max(1, int(leg.miles / 85.0))
            for slot in range(slots):
                if rng.random() > min(0.92, density + 0.18):
                    continue
                span = leg.miles / slots
                low = max(4.0, slot * span + 8.0)
                high = min(leg.miles - 6.0, (slot + 1) * span + 4.0)
                if high <= low:
                    continue
                behavior = rng.choices(
                    (
                        "steady_truck",
                        "slow_car",
                        "merging_vehicle",
                        "braking_traffic",
                        "passing_vehicle",
                    ),
                    weights=(3.0, 1.5, 1.2, 1.0, 1.1),
                )[0]
                base_speed = {
                    "steady_truck": rng.uniform(52.0, 64.0),
                    "slow_car": rng.uniform(42.0, 55.0),
                    "merging_vehicle": rng.uniform(38.0, 52.0),
                    "braking_traffic": rng.uniform(35.0, 48.0),
                    "passing_vehicle": rng.uniform(62.0, 75.0),
                }[behavior]
                speed = max(25.0, base_speed - weather_slowdown)
                lane = -1 if behavior == "passing_vehicle" else 0
                if behavior == "merging_vehicle":
                    lane = 1
                vehicles.append(NPCVehicle(
                    key=f"npc:{leg_index}:{slot}:{behavior}",
                    position_mi=start + rng.uniform(low, high),
                    speed_mph=speed,
                    target_speed_mph=speed,
                    relative_lane=lane,
                    behavior=behavior,
                ))
        vehicles.sort(key=lambda vehicle: vehicle.position_mi)
        return vehicles

    def _update_npc_traffic(self, dt: float) -> None:
        if not self.npc_vehicles:
            return
        game_hours = dt * self.time_scale / 3600.0
        for vehicle in self.npc_vehicles:
            gap = vehicle.position_mi - self.position_mi
            if vehicle.behavior == "merging_vehicle" and 0.0 <= gap <= 1.4:
                vehicle.relative_lane = 0
            if vehicle.behavior == "braking_traffic" and 0.0 <= gap <= 1.8:
                vehicle.target_speed_mph = max(30.0, vehicle.target_speed_mph - 8.0 * dt)
            delta = vehicle.target_speed_mph - vehicle.speed_mph
            vehicle.speed_mph += max(-6.0 * dt, min(4.0 * dt, delta))
            vehicle.position_mi += max(0.0, vehicle.speed_mph) * game_hours
        self.npc_vehicles.sort(key=lambda vehicle: vehicle.position_mi)

    def _npc_context(self) -> TrafficContext | None:
        best: TrafficContext | None = None
        for vehicle in self.npc_vehicles:
            if vehicle.relative_lane != 0:
                continue
            gap = vehicle.position_mi - self.position_mi
            if gap < -vehicle.length_mi or gap > TRAFFIC_LOOKAHEAD_MI:
                continue
            closing = max(0.0, self.truck.speed_mph - vehicle.speed_mph)
            context = TrafficContext(vehicle, max(0.0, gap), closing)
            if best is None or context.gap_mi < best.gap_mi:
                best = context
        return best

    def _legacy_traffic_context(self) -> TrafficContext | None:
        best: TrafficContext | None = None
        for lead in self.traffic_leads:
            gap = lead.at_mi - self.position_mi
            if gap < -lead.length_mi or gap > TRAFFIC_LOOKAHEAD_MI:
                continue
            closing = max(0.0, self.truck.speed_mph - lead.speed_mph)
            context = TrafficContext(lead, max(0.0, gap), closing)
            if best is None or context.gap_mi < best.gap_mi:
                best = context
        return best

    def traffic_context(self) -> TrafficContext | None:
        return self._npc_context() or self._legacy_traffic_context()

    def traffic_target_speed(self) -> float | None:
        context = self.traffic_context()
        if context is None:
            return None
        return context.lead.speed_mph

    def npc_traffic_status(self) -> str:
        context = self.traffic_context()
        if context is None:
            return "Traffic: no close traffic ahead."
        lead = context.lead
        lane = getattr(lead, "lane_text", "your lane")
        return (
            f"Traffic: {lead.reason} {self._gap_text(context.gap_mi)} ahead "
            f"in {lane}, moving {self._speed_value(lead.speed_mph)}."
        )

    def _npc_warning_message(self, context: TrafficContext) -> str:
        lead = context.lead
        if not isinstance(lead, NPCVehicle):
            return ""
        speed = self._speed_value(lead.speed_mph)
        gap = self._gap_text(context.gap_mi)
        if lead.behavior == "merging_vehicle":
            return (
                f"Merging vehicle {gap} ahead. Hold your lane, leave a gap, "
                f"and be ready for {speed}."
            )
        if lead.behavior == "braking_traffic":
            return f"Brake lights {gap} ahead. Ease down and leave room for {speed}."
        if lead.behavior == "slow_car":
            return f"Slow car {gap} ahead. Be ready to settle in near {speed}."
        return ""

    def _check_npc_traffic_cues(self) -> None:
        context = self._npc_context()
        if context is None or context.gap_mi > NPC_TRAFFIC_LOOKAHEAD_MI:
            return
        lead = context.lead
        if not isinstance(lead, NPCVehicle) or lead.key in self._announced_npc_traffic:
            return
        message = self._npc_warning_message(context)
        if not message:
            return
        self._announced_npc_traffic.add(lead.key)
        cue = NavigationCue(
            f"npc:{lead.key}", "traffic", lead.position_mi,
            lead.reason, speed_mph=lead.speed_mph)
        self._emit(TripEventKind.GPS_CUE, message, cue=cue, npc_vehicle=lead)

    def next_patrol_within(self, within_mi: float) -> PatrolWindow | None:
        """Nearest active or upcoming patrol window inside the lookahead."""
        candidates = [
            p for p in self.patrols
            if p.end_mi >= self.position_mi
            and p.start_mi - self.position_mi <= within_mi
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda p: max(0.0, p.start_mi - self.position_mi))

    def _rush_hour_traffic_bias(self, leg: Leg) -> float:
        if not any(start <= self.start_hour < end for start, end in RUSH_HOUR_WINDOWS):
            return 0.0
        return 0.14 if leg.checkpoints else 0.06

    def traffic_pressure_at(self, mile: float | None = None) -> TrafficPressure | None:
        sample = self.position_mi if mile is None else mile
        active = [
            pressure for pressure in self.traffic_pressures
            if pressure.start_mi <= sample <= pressure.end_mi
        ]
        if not active:
            return None
        return max(active, key=lambda pressure: pressure.intensity)

    def next_traffic_pressure_within(
        self, within_mi: float = TRAFFIC_PRESSURE_LOOKAHEAD_MI
    ) -> TrafficPressure | None:
        candidates = [
            pressure for pressure in self.traffic_pressures
            if pressure.end_mi >= self.position_mi
            and 0 <= pressure.start_mi - self.position_mi <= within_mi
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda pressure: pressure.start_mi)

