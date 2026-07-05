# ruff: noqa: F403,F405
"""Recurring road-event checks for trip simulation."""

from __future__ import annotations

from ..data.world import get_world
from .hos import is_night
from .trip_models import *
from .trip_route_helpers import *
from .weather import WeatherKind


class TripRoadEventMixin:
    def _traffic_pressure_intensity(self, mile: float, kind: str) -> float:
        leg_i, _ = self._leg_at_mile(mile)
        leg = self.route.legs[leg_i]
        intensity = 0.18
        if kind == "exit":
            intensity += 0.16
        elif kind == "route_merge":
            intensity += 0.20
        elif kind == "construction_merge":
            intensity += 0.34
        if self._near_city(mile):
            intensity += 0.22
        if leg.checkpoints:
            intensity += 0.12
        if self._rush_hour_traffic_bias(leg):
            intensity += 0.14
        if is_night(self.start_hour):
            intensity -= 0.06
        effects = self.weather.effects
        if effects.grip < 0.9:
            intensity += (0.9 - effects.grip) * 0.35
        if effects.visibility_mi < 3.0:
            intensity += (3.0 - effects.visibility_mi) * 0.04
        return max(0.0, min(0.95, intensity * self.hazard_scale))

    def _traffic_pressure_speed(self, mile: float, intensity: float) -> float:
        posted = self._corridor_limit_at(mile)
        return max(30.0, min(posted, posted - intensity * 26.0))

    def _place_traffic_pressures(self) -> list[TrafficPressure]:
        if self._is_facility_approach_route():
            # Merge/exit spacing pressure is highway language; city streets
            # get their pacing from per-street speed zones instead.
            return []
        pressures: list[TrafficPressure] = []

        def add(start: float, end: float, kind: str, direction: str, reason: str) -> None:
            start = max(0.0, start)
            end = min(self.total_miles, max(start + 0.2, end))
            intensity = self._traffic_pressure_intensity(start, kind)
            if intensity < TRAFFIC_PRESSURE_MIN_INTENSITY:
                return
            pressures.append(
                TrafficPressure(
                    start,
                    end,
                    kind,
                    direction,
                    intensity,
                    self._traffic_pressure_speed(start, intensity),
                    reason,
                )
            )

        for stop in self.stops:
            label = stop.exit_label or stop.spoken_name
            add(stop.at_mi - 2.0, stop.at_mi + 0.4, "exit", "right", f"exit traffic for {label}")
        for i, start in enumerate(self._leg_starts[1:], start=1):
            if self.route.legs[i - 1].highway != self.route.legs[i].highway:
                add(
                    start - 1.5,
                    start + 0.6,
                    "route_merge",
                    "right",
                    f"traffic merging for {self.route.legs[i].highway}",
                )
        for zone in self.zones:
            if zone.reason == "construction merge":
                add(
                    zone.start_mi,
                    zone.end_mi,
                    "construction_merge",
                    "left",
                    "construction taper traffic",
                )
        pressures.sort(key=lambda pressure: pressure.start_mi)
        return pressures

    def _check_tolls(self) -> None:
        for i, (start, leg) in enumerate(zip(self._leg_starts, self.route.legs, strict=True)):
            forward = self.route.cities[i] == leg.a
            for toll in leg.toll_events:
                offset = _stop_offset_for_direction(toll.at_mi, leg.miles, forward)
                at_mi = start + offset
                key = f"{i}:{toll.at_mi}:{toll.name}"
                if self.position_mi < at_mi or key in self._charged_tolls:
                    continue
                self._charged_tolls.add(key)
                if toll.amount <= 0:
                    self._emit(
                        TripEventKind.GPS_CUE,
                        f"{toll.method_label} entry recorded at {toll.name}; "
                        "toll will be billed at carrier settlement.",
                        toll=toll,
                    )
                    continue
                charge = TollCharge(toll, toll.amount)
                self.toll_charges.append(charge)
                estimate = "Estimated " if toll.estimated else ""
                self._emit(
                    TripEventKind.TOLL_CHARGED,
                    f"{toll.method_label} toll charged at {toll.name}: "
                    f"{estimate}{toll.amount:.0f} dollars, billed to carrier settlement.",
                    toll=toll,
                    amount=toll.amount,
                )

    @property
    def toll_expense(self) -> float:
        return sum(charge.amount for charge in self.toll_charges)

    def _check_cities(self) -> None:
        for i, start in enumerate(self._leg_starts):
            if i == 0 or i in self._announced_cities:
                continue
            if self.route.cities[i] == self.route.cities[i - 1]:
                # A same-city boundary is a surface-street segment change,
                # not a city passage; the turn cue already covers it.
                self._announced_cities.add(i)
                continue
            if self.position_mi >= start:
                self._announced_cities.add(i)
                prev = self.route.cities[i - 1]
                city = self.route.cities[i]
                nxt = self.route.cities[i + 1]
                leg = self.route.legs[i]
                world = get_world()
                city_state = world.cities[city].state
                prev_state = world.cities[prev].state
                crossing = f"Crossing into {city_state}. " if city_state != prev_state else ""
                self._emit(
                    TripEventKind.CITY_REACHED,
                    f"{crossing}Passing {city}, {city_state}. "
                    f"Continuing on {leg.highway} toward {nxt}.",
                )

    def _hazard_risk(self) -> float:
        """Chance of a hazard at each check; worse in fog and after dark."""
        vis = self.weather.effects.visibility_mi
        risk = 0.25 + (0.25 if vis < 2 else 0.0)
        if is_night(self.current_hour):
            risk += NIGHT_HAZARD_BONUS
        return risk * self.hazard_scale

    def _corridor_hazard_factor_at(self, mile: float) -> float:
        """Relative hazard-check frequency for the current corridor."""
        leg_i, _ = self._leg_at_mile(mile)
        leg = self.route.legs[leg_i]
        cls = _highway_class(leg.highway)
        factor = {"interstate": 1.05, "us_highway": 0.92}.get(cls, 0.82)
        factor += min(0.18, len(leg.checkpoints) * 0.06)
        region = self._region_at(mile)
        if region in _HOT_PATROL_REGIONS:
            factor += 0.12
        elif region in _COLD_PATROL_REGIONS:
            factor -= 0.12
        if self._near_city(mile):
            factor += 0.18
        return max(CORRIDOR_HAZARD_MIN_FACTOR, min(CORRIDOR_HAZARD_MAX_FACTOR, factor))

    def _next_hazard_check_interval_mi(self) -> float:
        base = self._rng.uniform(20, 60)
        return base / self._corridor_hazard_factor_at(self.position_mi)

    def _check_hazards(self, moved_mi: float) -> None:
        """Occasional road hazards that demand braking."""
        context = self.traffic_context()
        if (
            context is not None
            and context.closing_mph > 8.0
            and context.gap_seconds <= TRAFFIC_WARNING_GAP_S
            and self.position_mi >= self._traffic_warning_mi
        ):
            self._traffic_warning_mi = self.position_mi + 8.0
            # A lead vehicle blocks one lane: braking always works, and a
            # clear neighboring lane lets the player pass around it instead.
            # Reasons often end in "ahead" already, and a sub-tenth-mile gap
            # is spoken as "right ahead", not "0.0 miles ahead".
            reason = context.lead.reason.removesuffix(" ahead")
            where = (
                "right ahead" if context.gap_mi < 0.1 else f"{self._gap_text(context.gap_mi)} ahead"
            )
            self._emit(
                TripEventKind.HAZARD,
                f"Brake or change lanes! {reason.capitalize()} {where}.",
                deadline_s=2.5,
                traffic=context,
                dodgeable=True,
            )
            return
        self._hazard_check_mi -= moved_mi
        if self._hazard_check_mi > 0:
            return
        self._hazard_check_mi = self._next_hazard_check_interval_mi()
        if self._rng.random() < self._hazard_risk():
            choices = eligible_hazards(
                self.current_region,
                self.weather.current,
                self.terrain_at(self.position_mi),
                self.current_hour,
            )
            if not choices:
                return
            texts, weights = zip(*choices, strict=True)
            hazard = self._rng.choices(texts, weights)[0]
            dodgeable = hazard_is_dodgeable(hazard)
            call = "Brake or change lanes!" if dodgeable else "Brake now!"
            self._emit(
                TripEventKind.HAZARD,
                f"{call} {hazard[0].upper()}{hazard[1:]}.",
                deadline_s=(self._rng.uniform(3.0, 4.5) * self._visibility_reaction_factor()),
                dodgeable=dodgeable,
            )

    def _visibility_reaction_factor(self) -> float:
        """Low visibility shortens the normal hazard reaction slack."""
        vis = self.weather.effects.visibility_mi
        if vis >= 3.0:
            return 1.0
        return max(0.4, vis / 3.0)

    def _conditions_incident_text(self) -> str:
        """The traction-loss phrase for the current conditions."""
        kind = self.weather.current
        if kind == WeatherKind.SNOW:
            return "The trailer is sliding on the snow, too fast for the conditions."
        if kind in (WeatherKind.RAIN, WeatherKind.HEAVY_RAIN, WeatherKind.THUNDERSTORM):
            return "Hydroplaning on the wet road, too fast for the conditions."
        return "Losing traction, too fast for the conditions."

    def _check_conditions_speed(self, moved_mi: float) -> None:
        """Risk a traction-loss incident when driving too fast for slick roads."""
        eff = self.weather.effects
        over = self.truck.speed_mph - eff.safe_speed_mph
        if over <= CONDITIONS_SPEED_MARGIN_MPH or eff.grip >= CONDITIONS_GRIP_CEILING:
            self._conditions_check_mi = CONDITIONS_CHECK_MI
            return
        self._conditions_check_mi -= moved_mi
        if self._conditions_check_mi > 0:
            return
        self._conditions_check_mi = CONDITIONS_CHECK_MI
        severity = min(1.0, (over - CONDITIONS_SPEED_MARGIN_MPH) / 25.0)
        risk = severity * (1.0 - eff.grip) * CONDITIONS_INCIDENT_RISK * self.hazard_scale
        if self._cond_rng.random() < risk:
            self._emit(
                TripEventKind.HAZARD,
                f"Brake now! {self._conditions_incident_text()}",
                deadline_s=max(1.5, 2.5 * self._visibility_reaction_factor()),
            )
