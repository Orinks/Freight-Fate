# ruff: noqa: F403,F405
"""Trip simulation: progress along a route, grades, zones, stops, and events."""

from __future__ import annotations

import random

from ..data.world import Leg, Route
from .traffic_manager import TrafficManager
from .trip_models import *
from .trip_road_events import TripRoadEventMixin
from .trip_route_helpers import *
from .trip_traffic import TripTrafficMixin
from .vehicle import TruckState
from .weather import WeatherSystem


def _spoken_distance(value: float, unit: str) -> str:
    """A whole-number distance with the unit pluralized for speech, so a
    screen reader never hears "in 1 miles"."""
    rounded = round(value)
    return f"{rounded:.0f} {unit if rounded == 1 else unit + 's'}"


def _rest_stop_cue_text(prefix: str, parking_label: str) -> str:
    parts = [prefix]
    if parking_label:
        parts.append(parking_label)
    parts.append("press X to signal for the exit.")
    return "; ".join(parts)


class Trip(TripRoadEventMixin, TripTrafficMixin):
    """One delivery run along a chosen route."""

    def __init__(
        self,
        route: Route,
        truck: TruckState,
        weather: WeatherSystem,
        time_scale: float = 20.0,
        seed: int | None = None,
        start_hour: float = 12.0,
        imperial: bool = True,
        hazard_scale: float = 1.0,
    ) -> None:
        self.route = route
        self.truck = truck
        self.weather = weather
        self.time_scale = time_scale
        self.hazard_scale = max(0.0, hazard_scale)
        self.start_hour = start_hour  # clock hour of day at departure
        self._imperial = imperial
        self.position_mi = 0.0
        self.game_minutes = 0.0
        self.finished = False
        # Deliberate waiting: armed when the player sets the parking brake
        # themselves, never by the auto-set at trip start or menu returns.
        self.waiting = False
        self.hos_violation = False  # set by the UI layer; gates inspections
        self._seed = seed
        self._rng = random.Random(seed)
        self._insp_rng = random.Random(None if seed is None else seed ^ 0x5EED)
        self._cond_rng = random.Random(None if seed is None else seed ^ 0xC0FFEE)
        self._events: list[TripEvent] = []
        self._leg_starts = self._compute_leg_starts()
        self._city_mileposts = list(self._leg_starts) + [self.total_miles]
        self.stops = self._place_stops()
        self.toll_charges: list[TollCharge] = []
        self.traffic_manager = TrafficManager(
            route=self.route,
            truck=self.truck,
            weather=self.weather,
            leg_starts=self._leg_starts,
            seed=self._seed,
            start_hour=self.start_hour,
            hazard_scale=self.hazard_scale,
            imperial=self.imperial,
        )
        self.traffic_manager.spawn_initial_traffic()
        self.zones = self._place_zones()
        self.traffic_pressures = self._place_traffic_pressures()
        self.navigation_cues = self._build_navigation_cues()
        self.patrols = self._place_patrols()
        self.traffic_manager.add_patrol_traffic(self.patrols)
        self._announced_stops: set[str] = set()
        self._announced_cities: set[int] = set()
        self._announced_navigation: set[str] = set()
        self._charged_tolls: set[str] = set()
        self._active_zone: Zone | None = None
        self._announced_speed_limit: float | None = None
        self._announced_zone_warnings: set[str] = set()
        self._announced_traffic_pressures: set[str] = set()
        self._announced_npc_traffic: set[str] = set()
        self._construction_zone_grace_start: dict[str, float] = {}
        self._announced_patrols: set[str] = set()
        self._hazard_check_mi = 5.0
        self._inspection_check_mi = 10.0
        self._conditions_check_mi = CONDITIONS_CHECK_MI
        self._traffic_warning_mi = 1.0
        self._announced_enforcement: set[str] = set()

    @property
    def effective_time_scale(self) -> float:
        """Clock compression for this frame: gentle while maneuvering, the
        full configured pacing at highway speed, and double pacing while
        parked with the brake set (deliberate waiting). Everything that
        converts real seconds to game time must read this, never
        ``time_scale``."""
        full = self.time_scale
        if self.waiting and self.truck.parking_brake and self.truck.speed_mph < 1.0:
            return full * PARKED_TIME_SCALE_MULT
        floor = min(LOW_SPEED_TIME_SCALE, full)
        ramp = min(1.0, self.truck.speed_mph / FULL_COMPRESSION_MPH)
        return floor + (full - floor) * ramp

    @property
    def imperial(self) -> bool:
        return self._imperial

    @imperial.setter
    def imperial(self, value: bool) -> None:
        if value == self._imperial:
            return
        self._imperial = value
        self.traffic_manager.imperial = value
        self.navigation_cues = self._build_navigation_cues()

    @property
    def npc_vehicles(self):
        return self.traffic_manager.vehicles

    @npc_vehicles.setter
    def npc_vehicles(self, vehicles) -> None:
        self.traffic_manager.vehicles = vehicles

    def _distance_text(self, miles: float) -> str:
        if self.imperial:
            return _spoken_distance(miles, "mile")
        return _spoken_distance(miles * 1.609344, "kilometer")

    def _gap_text(self, miles: float) -> str:
        if self.imperial:
            return f"{miles:.1f} miles"
        return f"{miles * 1.609344:.1f} kilometers"

    def _speed_value(self, mph: float) -> str:
        if self.imperial:
            return f"{mph:.0f}"
        return f"{mph * 1.609344:.0f}"

    def _speed_text(self, mph: float) -> str:
        units = "miles per hour" if self.imperial else "kilometers per hour"
        return f"{self._speed_value(mph)} {units}"

    def _compute_leg_starts(self) -> list[float]:
        starts, acc = [], 0.0
        for leg in self.route.legs:
            starts.append(acc)
            acc += leg.miles
        return starts

    def _place_stops(self) -> list[RoadStop]:
        out: list[RoadStop] = []
        for i, (start, leg) in enumerate(zip(self._leg_starts, self.route.legs, strict=True)):
            from_city = self.route.cities[i]
            leg_stops = sorted(
                leg.stops,
                key=lambda stop: _stop_offset_for_direction(
                    stop.at_mi, leg.miles, from_city == leg.a
                ),
            )
            for stop in leg_stops:
                if not stop.curated or not stop.applies_to_direction(from_city == leg.a):
                    continue
                offset = _stop_offset_for_direction(stop.at_mi, leg.miles, from_city == leg.a)
                at = start + offset
                exit_label = _nearest_exit_label(leg, stop.at_mi)
                out.append(
                    RoadStop(
                        stop.name,
                        at,
                        stop.type,
                        stop.actions,
                        stop.services,
                        stop.parking,
                        exit_label,
                    )
                )
        return out

    def _build_navigation_cues(self) -> list[NavigationCue]:
        cues: list[NavigationCue] = []
        for i, (start, leg) in enumerate(zip(self._leg_starts, self.route.legs, strict=True)):
            forward = self.route.cities[i] == leg.a
            toward = self.route.cities[i + 1]
            if self._is_facility_approach_route():
                if i == 0:
                    cues.append(
                        NavigationCue(
                            "local:start",
                            "local_turn",
                            start + 0.05,
                            f"start on {leg.highway}",
                            f"Start on {leg.highway}; {self._distance_text(leg.miles)}.",
                            direction="ahead",
                        )
                    )
                elif self.route.legs[i - 1].highway != leg.highway:
                    cues.append(
                        NavigationCue(
                            f"local:turn:{i}",
                            "local_turn",
                            start,
                            f"turn onto {leg.highway}",
                            f"Turn onto {leg.highway}; {self._distance_text(leg.miles)}.",
                        )
                    )
                continue
            heading = _leg_heading(leg.highway, self.route.cities[i], toward)
            shield = f"{leg.highway} {heading}".strip()
            segment_miles = leg.miles
            if i == 0:
                cues.append(
                    NavigationCue(
                        "onramp:0",
                        "onramp",
                        start + 0.05,
                        f"merge onto {shield} toward {toward}",
                        f"Merge onto {shield} toward {toward}; "
                        f"{self._distance_text(segment_miles)}.",
                    )
                )
            elif segment_miles >= 40.0:
                cues.append(
                    NavigationCue(
                        f"continue:{i}",
                        "continue",
                        start + 0.1,
                        f"Continue on {leg.highway} for "
                        f"{self._distance_text(segment_miles)} toward {toward}.",
                    )
                )
            if i > 0 and self.route.legs[i - 1].highway != leg.highway:
                cues.append(
                    NavigationCue(
                        f"maneuver:{i}",
                        "maneuver",
                        start,
                        f"keep right for {shield} toward {toward}",
                        f"Keep right now for {shield} toward {toward}.",
                    )
                )
            for crossing in leg.state_crossings:
                offset = _stop_offset_for_direction(crossing.at_mi, leg.miles, forward)
                into_state = crossing.state if forward else crossing.from_state
                from_state = crossing.from_state if forward else crossing.state
                place = crossing.place
                cues.append(
                    NavigationCue(
                        f"state:{i}:{crossing.at_mi}:{into_state}",
                        "state_crossing",
                        start + offset,
                        f"crossing from {from_state} into {into_state} near {place}",
                        f"Crossing into {into_state} near {place}.",
                    )
                )
            for checkpoint in leg.checkpoints:
                offset = _stop_offset_for_direction(checkpoint.at_mi, leg.miles, forward)
                place = checkpoint.name
                state = f", {checkpoint.state}" if checkpoint.state else ""
                highway = checkpoint.highway or leg.highway
                cues.append(
                    NavigationCue(
                        f"checkpoint:{i}:{checkpoint.at_mi}:{place}",
                        "checkpoint",
                        start + offset,
                        f"{place}{state} on {highway}",
                        f"Passing {place}{state} on {highway}.",
                    )
                )
            for toll in leg.toll_events:
                offset = _stop_offset_for_direction(toll.at_mi, leg.miles, forward)
                if toll.amount > 0:
                    estimate = "estimated " if toll.estimated else ""
                    toll_text = (
                        f"{estimate}toll {toll.amount:.0f} dollars will be "
                        "billed to carrier settlement."
                    )
                else:
                    toll_text = "entry will be recorded for carrier settlement."
                cues.append(
                    NavigationCue(
                        f"toll:{i}:{toll.at_mi}:{toll.name}",
                        "toll",
                        start + offset,
                        f"toll road ahead: {toll.road}",
                        f"{toll.method_label} toll point ahead: {toll.name}. {toll_text}",
                    )
                )
            for ix in leg.interchanges:
                offset = _stop_offset_for_direction(ix.at_mi, leg.miles, forward)
                cues.append(
                    NavigationCue(
                        f"interchange:{i}:{ix.at_mi}:{ix.exit_ref}",
                        "interchange",
                        start + offset,
                        ix.spoken_phrase,
                        ix.near_phrase,
                    )
                )
            for stop in leg.stops:
                if not stop.curated or not stop.applies_to_direction(forward):
                    continue
                offset = _stop_offset_for_direction(stop.at_mi, leg.miles, forward)
                exit_label = _nearest_exit_label(leg, stop.at_mi)
                at_part = f" at {exit_label}" if exit_label else ""
                cues.append(
                    NavigationCue(
                        f"rest_stop:{i}:{stop.at_mi}:{stop.name}",
                        "rest_stop",
                        start + offset,
                        f"{stop.label} ahead{at_part}",
                        _rest_stop_cue_text(
                            f"{stop.label.capitalize()}{at_part} ahead in "
                            f"{self._distance_text(1.0)}",
                            stop.parking_label,
                        ),
                    )
                )
        cues.sort(key=lambda cue: cue.at_mi)
        return cues

    def _place_zones(self) -> list[Zone]:
        night = is_night(self.start_hour)
        zones: list[Zone] = []
        total = self.route.miles
        n = max(0, int(total / 150))
        for _ in range(n):
            at = self._rng.uniform(15, max(16, total - 20))
            length = self._rng.uniform(3, 9)
            if self._rng.random() < 0.6:
                closed = (
                    self._rng.choice((0, 1))
                    if self._rng.random() < CONSTRUCTION_CLOSURE_CHANCE
                    else None
                )
                taper_start = max(0.0, at - CONSTRUCTION_TAPER_MI)
                zones.append(
                    Zone(
                        taper_start,
                        at,
                        CONSTRUCTION_TAPER_LIMIT_MPH,
                        "construction merge",
                        closed_lane=closed,
                    )
                )
                zones.append(Zone(at, at + length, 45, "construction", closed_lane=closed))
            elif not night or self._rng.random() < NIGHT_TRAFFIC_KEEP:
                zones.append(Zone(at, at + length, 50, "heavy traffic"))
        zones.extend(self._facility_speed_zones())
        zones.sort(key=lambda z: z.start_mi)
        return zones

    def _facility_speed_zones(self) -> list[Zone]:
        total = self.route.miles
        if total <= 0:
            return []
        gate_start = max(0.0, total - FACILITY_GATE_ZONE_MI)
        if self._is_facility_approach_route():
            return [
                Zone(0.0, total, FACILITY_ACCESS_LIMIT_MPH, "facility access road"),
                Zone(gate_start, total, FACILITY_GATE_LIMIT_MPH, "facility gate"),
            ]
        approach_start = max(0.0, total - DESTINATION_APPROACH_ZONE_MI)
        return [
            Zone(approach_start, total, DESTINATION_APPROACH_LIMIT_MPH, "destination approach"),
            Zone(gate_start, total, FACILITY_GATE_LIMIT_MPH, "facility gate"),
        ]

    def _is_facility_approach_route(self) -> bool:
        return len(self.route.cities) >= 2 and self.route.cities[0] == self.route.cities[-1]

    def _patrol_intensity_at(self, mile: float) -> float:
        leg_i, _ = self._leg_at_mile(mile)
        cls = _highway_class(self.route.legs[leg_i].highway)
        base = {"interstate": 0.5, "us_highway": 0.35}.get(cls, 0.25)
        region = self._region_at(mile)
        if region in _HOT_PATROL_REGIONS:
            base *= 1.3
        elif region in _COLD_PATROL_REGIONS:
            base *= 0.7
        if is_night(self.start_hour):
            base *= 1.15
        return base

    def _place_patrols(self) -> list[PatrolWindow]:
        patrols: list[PatrolWindow] = []
        total = self.route.miles
        n = max(0, int(total / 120.0 * min(1.0, self.hazard_scale)))
        for _ in range(n):
            at = self._insp_rng.uniform(10, max(11, total - 15))
            length = self._insp_rng.uniform(3, 8)
            intensity = self._patrol_intensity_at(at) * self.hazard_scale
            patrols.append(
                PatrolWindow(at, at + length, max(0.1, min(0.95, intensity)), "highway enforcement")
            )
        for zone in self.zones:
            if zone.reason == "construction":
                patrols.append(
                    PatrolWindow(
                        zone.start_mi,
                        zone.end_mi,
                        min(0.95, 0.9 * self.hazard_scale),
                        "work zone enforcement",
                    )
                )
        patrols.sort(key=lambda p: p.start_mi)
        return patrols

    def active_patrol_at(self, mile: float) -> PatrolWindow | None:
        active = [p for p in self.patrols if p.start_mi <= mile <= p.end_mi]
        return max(active, key=lambda p: p.intensity) if active else None

    def _leg_traffic_density(self, leg: Leg, bad_weather_bias: float, night: bool) -> float:
        metro_bias = 0.18 if leg.checkpoints else 0.0
        night_bias = -0.08 if night else 0.0
        rush_bias = self._rush_hour_traffic_bias(leg)
        density = min(
            0.86,
            max(
                0.05,
                0.22 + leg.miles / 900.0 + metro_bias + bad_weather_bias + night_bias + rush_bias,
            ),
        )
        return density * self.hazard_scale

    @property
    def total_miles(self) -> float:
        return self.route.miles

    @property
    def remaining_miles(self) -> float:
        return max(0.0, self.total_miles - self.position_mi)

    @property
    def current_hour(self) -> float:
        return (self.start_hour + self.game_minutes / 60.0) % 24.0

    @property
    def current_leg_index(self) -> int:
        for i in range(len(self.route.legs) - 1, -1, -1):
            if self.position_mi >= self._leg_starts[i]:
                return i
        return 0

    @property
    def current_target_city(self):
        name = self.route.cities[self.current_leg_index + 1]
        return get_world().cities[name]

    @property
    def current_region(self) -> str:
        return self.current_target_city.region

    def grade_at(self, mile: float) -> float:
        leg_i, leg_start = self._leg_at_mile(mile)
        leg = self.route.legs[leg_i]
        forward = self.route.cities[leg_i] == leg.a
        offset = max(0.0, min(leg.miles, mile - leg_start))
        sample_offset = offset if forward else leg.miles - offset
        for segment in leg.grade_segments:
            if segment.start_mi <= sample_offset <= segment.end_mi:
                grade = segment.avg_grade_pct / 100.0
                return grade if forward else -grade
        return _fallback_grade(leg.terrain, mile, leg.highway)

    def terrain_at(self, mile: float | None = None) -> str:
        sample_mile = self.position_mi if mile is None else mile
        leg_i, leg_start = self._leg_at_mile(sample_mile)
        leg = self.route.legs[leg_i]
        forward = self.route.cities[leg_i] == leg.a
        offset = max(0.0, min(leg.miles, sample_mile - leg_start))
        sample_offset = offset if forward else leg.miles - offset
        for segment in leg.grade_segments:
            if segment.start_mi <= sample_offset <= segment.end_mi:
                return segment.terrain
        return leg.terrain

    def _leg_at_mile(self, mile: float) -> tuple[int, float]:
        clamped = max(0.0, min(mile, self.total_miles))
        for i in range(len(self.route.legs) - 1, -1, -1):
            if clamped >= self._leg_starts[i]:
                return i, self._leg_starts[i]
        return 0, 0.0

    def speed_limit_at(self, mile: float) -> tuple[float, str | None]:
        zone = self._active_zone_at(mile)
        if zone is not None:
            return zone.limit_mph, zone.reason
        return self._corridor_limit_at(mile), None

    def _region_at(self, mile: float) -> str:
        leg_i, _ = self._leg_at_mile(mile)
        city = self.route.cities[min(leg_i + 1, len(self.route.cities) - 1)]
        return get_world().cities[city].region

    def _near_city(self, mile: float) -> bool:
        return any(abs(mile - mp) <= URBAN_RADIUS_MI for mp in self._city_mileposts)

    def _nearest_urban_city(self, mile: float) -> str | None:
        best, best_d = None, URBAN_RADIUS_MI
        for i, mp in enumerate(self._city_mileposts):
            d = abs(mile - mp)
            if d <= best_d and i < len(self.route.cities):
                best, best_d = self.route.cities[i], d
        return best

    def _corridor_limit_at(self, mile: float) -> float:
        leg_i, leg_start = self._leg_at_mile(mile)
        leg = self.route.legs[leg_i]
        forward = self.route.cities[leg_i] == leg.a
        route_offset = mile - leg_start
        leg_offset = route_offset if forward else leg.miles - route_offset
        baked = _truck_capped_speed_limit(leg, leg_offset)
        if baked is not None:
            return baked
        base = corridor_speed_limit(leg.highway, self._region_at(mile))
        if self._near_city(mile):
            return min(base, URBAN_LIMIT_MPH)
        return base

    def next_zone_within(self, within_mi: float) -> Zone | None:
        ahead = [z for z in self.zones if 0 < z.start_mi - self.position_mi <= within_mi]
        return min(ahead, key=lambda z: z.start_mi) if ahead else None

    @property
    def active_zone(self) -> Zone | None:
        """The reduced-limit zone the truck is currently inside, if any."""
        return self._active_zone_at(self.position_mi)

    def _active_zone_at(self, mile: float) -> Zone | None:
        active = [z for z in self.zones if z.start_mi <= mile <= z.end_mi]
        if not active:
            return None
        return min(active, key=lambda z: z.limit_mph)

    def nearest_stop_within(self, radius_mi: float = 1.5) -> RoadStop | None:
        for stop in self.stops:
            if abs(stop.at_mi - self.position_mi) <= radius_mi:
                return stop
        return None

    def upcoming_stop(self, within_mi: float = 5.0) -> RoadStop | None:
        """The next stop whose exit lies ahead within the given distance."""
        best: RoadStop | None = None
        for stop in self.stops:
            ahead = stop.at_mi - self.position_mi
            if 0 <= ahead <= within_mi and (best is None or stop.at_mi < best.at_mi):
                best = stop
        return best

    # below this the truck is parked or crawling: estimate at highway pace
    ETA_MIN_MPH = 15.0

    def eta_game_hours(self, fallback_mph: float = 55.0) -> float:
        """Hours to arrival at the current pace.

        Tracks the truck's actual speed once it is meaningfully rolling, so
        the estimate responds to how you are driving. Parked or crawling it
        assumes a typical highway pace instead of promising infinity.
        """
        mph = self.truck.speed_mph
        if mph < self.ETA_MIN_MPH:
            mph = max(1.0, fallback_mph)
        return self.remaining_miles / mph

    def progress_summary(self, imperial: bool = True) -> str:
        if imperial:
            dist = (
                f"{_spoken_distance(self.remaining_miles, 'mile')} "
                f"remaining of {self.total_miles:.0f}"
            )
        else:
            dist = (
                f"{_spoken_distance(self.remaining_miles * 1.609, 'kilometer')} "
                f"remaining of {self.total_miles * 1.609:.0f}"
            )
        leg = self.route.legs[self.current_leg_index]
        toward = self.route.cities[self.current_leg_index + 1]
        state = get_world().cities[toward].state
        next_context = self.next_navigation_context(imperial)
        terrain_text = self._current_grade_text()
        return f"{dist}. On {leg.highway} toward {toward}, {state}. {terrain_text}. {next_context}"

    def _current_grade_text(self) -> str:
        grade_pct = self.grade_at(self.position_mi) * 100.0
        if abs(grade_pct) < 0.05:
            return "Current grade 0.0 percent, level"
        direction = "uphill" if grade_pct > 0 else "downhill"
        terrain = self.terrain_at()
        terrain_text = "" if terrain == "flat" else f", terrain {terrain}"
        return f"Current grade {abs(grade_pct):.1f} percent {direction}{terrain_text}"

    def next_navigation_context(self, imperial: bool = True) -> str:
        cue = self.next_navigation_cue()
        if cue is None:
            return f"Destination {self.route.cities[-1]} ahead."
        ahead = max(0.0, cue.at_mi - self.position_mi)
        ahead_text = (
            _spoken_distance(ahead, "mile")
            if imperial
            else _spoken_distance(ahead * 1.609344, "kilometer")
        )
        if cue.kind == "rest_stop":
            return f"Next stop in {ahead_text}: {cue.text}."
        if cue.kind == "state_crossing":
            return f"Next state line in {ahead_text}: {cue.text}."
        if cue.kind in ("maneuver", "onramp"):
            return f"Next maneuver in {ahead_text}: {cue.text}."
        if cue.kind == "checkpoint":
            return f"Next place in {ahead_text}: {cue.text}."
        if cue.kind == "interchange":
            return f"Next exit in {ahead_text}: {cue.text}."
        if cue.kind == "traffic":
            speed = ""
            if cue.speed_mph is not None:
                speed = " at " + (
                    f"{cue.speed_mph:.0f} miles per hour"
                    if imperial
                    else f"{cue.speed_mph * 1.609344:.0f} kilometers per hour"
                )
            if ahead < 0.5:
                return f"Traffic just ahead: {cue.text}{speed}."
            return f"Traffic in {ahead_text}: {cue.text}{speed}."
        if cue.kind == "toll":
            return f"Toll point in {ahead_text}: {cue.text}."
        return f"Next guidance in {ahead_text}: {cue.text}."

    def next_navigation_cue(self) -> NavigationCue | None:
        for cue in self.navigation_cues:
            if cue.at_mi > self.position_mi + 0.05 and cue.kind not in ("continue", "interchange"):
                return cue
        return None

    def next_exit_context(self) -> str:
        cue = self.next_exit_cue()
        if cue is None:
            return "No listed highway exit ahead before the destination."
        ahead = max(0.0, cue.at_mi - self.position_mi)
        return f"Next listed exit in {self._distance_text(ahead)}: {cue.text}."

    def next_exit_cue(self) -> NavigationCue | None:
        for cue in self.navigation_cues:
            if cue.at_mi > self.position_mi + 0.05 and cue.kind == "interchange":
                return cue
        return None

    def restore(self, position_mi: float, game_minutes: float) -> None:
        """Jump to a saved point without re-announcing what is behind it."""
        self.position_mi = max(0.0, min(position_mi, self.total_miles))
        self.game_minutes = game_minutes
        # Seed the spoken limit at the resume point so it is not re-announced.
        self._announced_speed_limit = self._corridor_limit_at(self.position_mi)
        for stop in self.stops:
            if stop.at_mi <= self.position_mi:
                self._announced_stops.add(stop.name)
        for cue in self.navigation_cues:
            if cue.at_mi <= self.position_mi:
                self._announced_navigation.add(f"{cue.key}:advance")
                self._announced_navigation.add(f"{cue.key}:near")
        for patrol in self.patrols:
            if patrol.start_mi <= self.position_mi:
                self._announced_patrols.add(_patrol_key(patrol))
        for pressure in self.traffic_pressures:
            if pressure.start_mi <= self.position_mi:
                self._announced_traffic_pressures.add(_traffic_pressure_key(pressure))
        for i, (start, leg) in enumerate(zip(self._leg_starts, self.route.legs, strict=True)):
            forward = self.route.cities[i] == leg.a
            for toll in leg.toll_events:
                offset = _stop_offset_for_direction(toll.at_mi, leg.miles, forward)
                if start + offset <= self.position_mi:
                    self._charged_tolls.add(f"{i}:{toll.at_mi}:{toll.name}")
        for stop in self.stops:
            if stop.at_mi <= self.position_mi and stop.type == "weigh_station":
                self._announced_enforcement.add(f"weigh:{stop.name}:{stop.at_mi:.1f}")
        for i, start in enumerate(self._leg_starts):
            if i and self.position_mi >= start:
                self._announced_cities.add(i)
        self._active_zone = self._active_zone_at(self.position_mi)

    def restore_toll_charges(self, charges: list[dict]) -> None:
        """Restore settlement toll expenses from an active-drive snapshot."""
        by_name = {toll.name: toll for leg in self.route.legs for toll in leg.toll_events}
        self.toll_charges = []
        for raw in charges:
            name = str(raw.get("name", "")).strip()
            event = by_name.get(name)
            if event is None:
                continue
            amount = float(raw.get("amount", event.amount))
            self.toll_charges.append(TollCharge(event, amount))

    def update(self, dt: float) -> list[TripEvent]:
        """Advance the trip by real seconds; returns events for the UI layer."""
        self._events = []
        if self.finished:
            return self._events

        # Any release path disarms waiting; the effective-scale speed guard
        # already keeps a still-rolling truck at maneuvering pace.
        if self.waiting and not self.truck.parking_brake:
            self.waiting = False

        # weather drives truck grip and evolves over game time
        scale = self.effective_time_scale
        game_min = dt * scale / 60.0
        self.game_minutes += game_min
        target = self.current_target_city
        self.weather.set_region(target.region)
        self.weather.set_city(target.name, target.lat, target.lon)
        changed = self.weather.update(game_min)
        if changed is not None:
            self._emit(
                TripEventKind.WEATHER_CHANGE,
                f"Weather changing: {self.weather.describe()}",
                weather=changed,
            )
        self.truck.grip = self.weather.effects.grip
        self.truck.drag_mult = self.weather.effects.drag_mult
        self.truck.grade = self.grade_at(self.position_mi)
        self.truck.fuel_burn_mult = scale

        moved_mi = self.truck.velocity_mps * dt * scale / 1609.344
        self.position_mi += moved_mi
        if self.position_mi < 0.0:
            self.position_mi = 0.0
        elif self.position_mi > self.total_miles:
            self.position_mi = self.total_miles

        self.traffic_manager.update(
            dt=dt,
            position_mi=self.position_mi,
            time_scale=self.time_scale,
        )
        self._check_zones()
        self._check_speed_limit()
        self._check_stops()
        self._check_npc_traffic_cues()
        self._check_traffic_pressures()
        self._check_navigation_cues()
        self._check_tolls()
        self._check_cities()
        if moved_mi > 0.0:
            self._check_patrol_heads_up()
            self._check_hazards(moved_mi)
            self._check_conditions_speed(moved_mi)
            self._check_inspections(moved_mi)

        if self.position_mi >= self.total_miles:
            self.finished = True
            self._emit(TripEventKind.ARRIVED, f"You have arrived in {self.route.cities[-1]}.")
        return self._events

    # -- event checks ----------------------------------------------------------------

    def _emit(self, kind: TripEventKind, message: str, **data) -> None:
        self._events.append(TripEvent(kind, message, data))

    def _zone_warning_lookahead_mi(self) -> float:
        """Lead distance for a zone warning, scaled so the player gets roughly
        ``ZONE_WARNING_REAL_S`` of real time despite speed and time compression."""
        speed = max(self.truck.speed_mph, 1.0)
        miles = ZONE_WARNING_REAL_S * speed * self.effective_time_scale / 3600.0
        return max(ZONE_WARNING_LOOKAHEAD_MI, min(miles, ZONE_WARNING_MAX_MI))

    @staticmethod
    def _closure_phrases(zone: Zone) -> tuple[str, str]:
        """(closed lane name, direction to merge) for a zone's coned-off lane."""
        if zone.closed_lane == 0:
            return "right", "left"
        return "left", "right"

    def _zone_warning_message(self, zone: Zone, ahead: float) -> str:
        if zone.reason == "construction":
            if zone.closed_lane is not None:
                shut, keep = self._closure_phrases(zone)
                merge_part = f"The {shut} lane is closed; merge {keep} at the taper. "
            else:
                merge_part = "All lanes stay open through the work; hold your lane. "
            return (
                f"Brake now! In {self._distance_text(ahead)}, construction ahead. "
                f"{merge_part}Speed limit "
                f"{self._speed_value(CONSTRUCTION_TAPER_LIMIT_MPH)} at the taper, then "
                f"{self._speed_value(zone.limit_mph)} through the work zone."
            )
        return (
            f"In {self._distance_text(ahead)}, {zone.reason} ahead. "
            f"Speed limit {self._speed_value(zone.limit_mph)}."
        )

    def _zone_entry_message(self, zone: Zone) -> str:
        if zone.reason == "construction merge":
            if zone.closed_lane is not None:
                shut, keep = self._closure_phrases(zone)
                return (
                    f"Construction merge taper. The {shut} lane closes ahead; "
                    f"merge {keep} now. "
                    f"Speed limit {self._speed_value(zone.limit_mph)}."
                )
            return (
                "Construction merge taper. Follow the flagger through the cones. "
                f"Speed limit {self._speed_value(zone.limit_mph)}."
            )
        if zone.reason == "construction":
            if zone.closed_lane is not None:
                shut, keep = self._closure_phrases(zone)
                return (
                    f"Work zone active. The {shut} lane is closed; stay in the "
                    f"{keep} lane and watch the barrels. "
                    f"Speed limit {self._speed_value(zone.limit_mph)}."
                )
            return (
                "Work zone active. Stay in the lane and watch the barrels. "
                f"Speed limit {self._speed_value(zone.limit_mph)}."
            )
        return f"{zone.reason} ahead. Speed limit {self._speed_value(zone.limit_mph)}."

    def _check_zones(self) -> None:
        lookahead = self._zone_warning_lookahead_mi()
        for zone in self.zones:
            key = _zone_key(zone)
            ahead = zone.start_mi - self.position_mi
            if zone.reason == "construction merge":
                continue
            if 0 < ahead <= lookahead and key not in self._announced_zone_warnings:
                self._announced_zone_warnings.add(key)
                self._emit(
                    TripEventKind.GPS_CUE,
                    self._zone_warning_message(zone, ahead),
                    zone=zone,
                )
        zone = self._active_zone_at(self.position_mi)
        if zone is not self._active_zone:
            if zone is not None:
                if zone.reason == "construction":
                    self._construction_zone_grace_start[_zone_key(zone)] = zone.start_mi
                quiet = zone.reason == "construction" and any(
                    z.reason == "construction merge" and abs(z.end_mi - zone.start_mi) < 0.01
                    for z in self.zones
                )
                self._emit(
                    TripEventKind.ZONE_ENTER,
                    self._zone_entry_message(zone),
                    zone=zone,
                    suppress_sound=quiet,
                )
            elif self._active_zone is not None:
                self._construction_zone_grace_start.pop(_zone_key(self._active_zone), None)
                resumed = self._corridor_limit_at(self.position_mi)
                self._announced_speed_limit = resumed
                self._emit(
                    TripEventKind.ZONE_EXIT,
                    f"End of {self._active_zone.reason} zone. "
                    f"Speed limit {self._speed_value(resumed)}.",
                )
            self._active_zone = zone

    def _check_speed_limit(self) -> None:
        """Announce a changed posted limit on the open road (signs at a region
        or urban boundary). While a zone is active the zone owns the spoken
        limit, so this stays quiet until the zone clears."""
        if self._active_zone is not None:
            return
        limit = self._corridor_limit_at(self.position_mi)
        if self._announced_speed_limit is None:
            self._announced_speed_limit = limit  # seed at departure, no cue
            return
        if limit != self._announced_speed_limit:
            lowered = limit < self._announced_speed_limit
            self._announced_speed_limit = limit
            verb = "reduced to" if lowered else "raised to"
            city = self._nearest_urban_city(self.position_mi) if lowered else None
            where = f" approaching {city}" if city else ""
            self._emit(
                TripEventKind.GPS_CUE, f"Speed limit {verb} {self._speed_value(limit)}{where}."
            )

    def _check_stops(self) -> None:
        for stop in self.stops:
            ahead = stop.at_mi - self.position_mi
            if 0 < ahead <= 5.0 and stop.name not in self._announced_stops:
                self._announced_stops.add(stop.name)
                exit_part = f" at {stop.exit_label}" if stop.exit_label else ""
                parts = [f"{stop.spoken_name}{exit_part} in {self._distance_text(ahead)}."]
                if stop.parking_text:
                    parts.append(f"{stop.parking_text}.")
                parts.append("Press X to signal for the exit.")
                self._emit(TripEventKind.STOP_AHEAD, " ".join(parts), stop=stop)

    def _check_navigation_cues(self) -> None:
        for cue in self.navigation_cues:
            ahead = cue.at_mi - self.position_mi
            if cue.kind == "interchange":
                continue
            if cue.kind in ("continue", "onramp"):
                key = f"{cue.key}:near"
                if -0.5 <= ahead <= 0.5 and key not in self._announced_navigation:
                    self._announced_navigation.add(key)
                    self._emit(TripEventKind.GPS_CUE, cue.near_text or cue.text, cue=cue)
                continue
            if cue.kind == "rest_stop":
                key = f"{cue.key}:near"
                if 0 < ahead <= 1.2 and key not in self._announced_navigation:
                    self._announced_navigation.add(key)
                    self._emit(TripEventKind.GPS_CUE, cue.near_text, cue=cue)
                continue
            if cue.kind == "traffic":
                key = f"{cue.key}:advance"
                if 0 < ahead <= 2.0 and key not in self._announced_navigation:
                    self._announced_navigation.add(key)
                    speed = (
                        f" at {cue.speed_mph:.0f} miles per hour"
                        if cue.speed_mph is not None
                        else ""
                    )
                    self._emit(
                        TripEventKind.GPS_CUE,
                        f"Traffic slowing ahead in {self._distance_text(ahead)}; "
                        f"{cue.text}{speed}.",
                        cue=cue,
                    )
                continue
            if cue.kind == "toll":
                advance_key = f"{cue.key}:advance"
                if 0 < ahead <= 2.0 and advance_key not in self._announced_navigation:
                    self._announced_navigation.add(advance_key)
                    self._emit(TripEventKind.GPS_CUE, cue.near_text, cue=cue)
                continue
            advance_key = f"{cue.key}:advance"
            near_key = f"{cue.key}:near"
            lookahead = STATE_CROSSING_WARNING_LOOKAHEAD_MI if cue.kind == "state_crossing" else 2.0
            if 0 < ahead <= lookahead and advance_key not in self._announced_navigation:
                self._announced_navigation.add(advance_key)
                distance = self._distance_text(ahead)
                # Within rounding range of the cue the near announcement is
                # imminent; "In 0 miles, ..." reads as a bug, so skip the lead.
                if not distance.startswith("0 "):
                    message = f"In {distance}, {cue.text}."
                    self._emit(TripEventKind.GPS_CUE, message, cue=cue)
            if -0.1 <= ahead <= 0.1 and near_key not in self._announced_navigation:
                self._announced_navigation.add(near_key)
                if cue.kind == "state_crossing":
                    self._emit(TripEventKind.STATE_CROSSING, cue.near_text, cue=cue)
                elif cue.kind == "checkpoint":
                    self._emit(TripEventKind.CHECKPOINT, cue.near_text, cue=cue)
                else:
                    self._emit(TripEventKind.GPS_CUE, cue.near_text, cue=cue)

    def _traffic_pressure_message(self, pressure: TrafficPressure, ahead: float) -> str:
        distance = self._distance_text(ahead)
        speed = self._speed_value(pressure.target_speed_mph)
        if pressure.kind == "exit":
            return (
                f"Exit traffic building in {distance}. Signal early, hold the "
                f"{pressure.direction} exit lane, and be ready to slow near {speed}."
            )
        if pressure.kind == "construction_merge":
            return (
                f"Traffic squeezing at the construction taper in {distance}. "
                f"Merge {pressure.direction} early, leave a gap, and be ready "
                f"for {speed}."
            )
        if pressure.kind == "route_merge":
            return (
                f"Merging traffic in {distance}. Keep {pressure.direction}, "
                f"leave a gap, and be ready to adjust toward {speed}."
            )
        return f"Traffic pack in {distance}. Leave extra following room and be ready for {speed}."

    def _check_traffic_pressures(self) -> None:
        for pressure in self.traffic_pressures:
            key = _traffic_pressure_key(pressure)
            ahead = pressure.start_mi - self.position_mi
            if (
                0 < ahead <= TRAFFIC_PRESSURE_LOOKAHEAD_MI
                and key not in self._announced_traffic_pressures
            ):
                if pressure.kind == "construction_merge" and any(
                    zone.reason == "construction"
                    and abs(zone.start_mi - pressure.end_mi) < 0.01
                    and _zone_key(zone) in self._announced_zone_warnings
                    for zone in self.zones
                ):
                    self._announced_traffic_pressures.add(key)
                    continue
                self._announced_traffic_pressures.add(key)
                self._emit(
                    TripEventKind.GPS_CUE,
                    self._traffic_pressure_message(pressure, ahead),
                    traffic_pressure=pressure,
                )
                return

    def _check_patrol_heads_up(self) -> None:
        for patrol in self.patrols:
            key = _patrol_key(patrol)
            ahead = patrol.start_mi - self.position_mi
            if 0 < ahead <= CB_PATROL_LOOKAHEAD_MI and key not in self._announced_patrols:
                self._announced_patrols.add(key)
                self._emit(
                    TripEventKind.GPS_CUE,
                    self.cb_patrol_message(patrol, ahead),
                    cb_patrol=patrol,
                )
                return

    def _random_inspection_odds(self, leg: Leg) -> float:
        """Odds a random roadside log-check fires when the driver is in HOS
        violation, thinned by ``hazard_scale`` so relaxed mode pulls you over
        less often. Weigh-station and construction-zone checks are unaffected --
        a real violation at a fixed checkpoint still catches you."""
        base = 0.55 if leg.checkpoints else 0.25
        return base * self.hazard_scale

    def _check_inspections(self, moved_mi: float) -> None:
        """Route-backed inspections plus rare seeded patrols.

        The random stream is still separate so enforcement never changes
        hazard or zone layout, but every event now names route context and
        evidence instead of feeling like a generic dice roll.
        """
        previous_mi = self.position_mi - moved_mi
        for stop in self.stops:
            key = f"weigh:{stop.name}:{stop.at_mi:.1f}"
            if stop.type != "weigh_station" or key in self._announced_enforcement:
                continue
            if previous_mi < stop.at_mi <= self.position_mi:
                self._announced_enforcement.add(key)
                if self.hos_violation:
                    self._emit(
                        TripEventKind.INSPECTION,
                        f"{stop.spoken_name} is open. Officers wave you in for an ELD check.",
                        key=key,
                        context="weigh_station",
                        evidence=("HOS/ELD violation",),
                    )
                return

        limit, reason = self.speed_limit_at(self.position_mi)
        if reason == "construction" and self.truck.speed_mph > limit + 9:
            active_zone = self._active_zone
            if active_zone is not None and active_zone.reason == "construction":
                zone_key = _zone_key(active_zone)
                grace_start = self._construction_zone_grace_start.get(
                    zone_key, active_zone.start_mi
                )
                if self.position_mi - grace_start < CONSTRUCTION_ENFORCEMENT_GRACE_MI:
                    return
            key = f"construction:{round(self.position_mi)}"
            if key not in self._announced_enforcement:
                self._announced_enforcement.add(key)
                self._emit(
                    TripEventKind.INSPECTION,
                    "Trooper in the construction zone clocks your speed.",
                    key=key,
                    context="construction_zone",
                    evidence=("speeding in construction zone",),
                )
                return

        self._inspection_check_mi -= moved_mi
        if self._inspection_check_mi > 0:
            return
        self._inspection_check_mi = self._insp_rng.uniform(15, 40)
        if not self.hos_violation:
            return
        leg = self.route.legs[self.current_leg_index]
        context = "checkpoint corridor" if leg.checkpoints else "patrol corridor"
        if self._insp_rng.random() < self._random_inspection_odds(leg):
            key = f"patrol:{self.current_leg_index}:{round(self.position_mi)}"
            self._emit(
                TripEventKind.INSPECTION,
                f"CB reports a patrol on this {context}. A trooper stops you for a log check.",
                key=key,
                context=context,
                evidence=("HOS/ELD violation",),
            )
