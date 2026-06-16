"""Trip simulation: progress along a route, grades, zones, stops, and events.

The truck physics run in real time; the trip layer compresses distance with a
configurable time scale (default 20x), so a 300-mile haul takes roughly
fifteen minutes at highway speed instead of five hours. The in-game clock
advances at the same rate, which keeps deadlines meaningful.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum

from ..data.world import STOP_TYPE_LABELS, Route, get_world
from .hos import is_night
from .vehicle import TruckState
from .weather import WeatherSystem

BASE_SPEED_LIMIT_MPH = 70.0
NIGHT_HAZARD_BONUS = 0.10          # extra hazard risk after dark
NIGHT_TRAFFIC_KEEP = 0.4           # chance a traffic zone still forms at night
TRAFFIC_LOOKAHEAD_MI = 2.5
TRAFFIC_WARNING_GAP_S = 2.2

# Hazards that can appear anywhere in the country...
GENERIC_HAZARDS = ("debris on the road", "a slow vehicle ahead",
                   "an animal crossing")

# ...and the local flavor each region adds to the draw.
REGION_HAZARDS: dict[str, tuple[str, ...]] = {
    "northeast": ("a sudden lane closure ahead",
                  "stopped traffic around a fender bender"),
    "midwest": ("a deer crossing the road",
                "farm equipment pulling onto the highway"),
    "south": ("retread debris from a blown tire",
              "a sudden downpour flooding the right lane"),
    "plains": ("a combine convoy crawling ahead",
               "a crosswind gust shoving the trailer"),
    "rockies": ("rockfall debris on the road",
                "a runaway truck on the grade ahead"),
    "southwest": ("a dust devil crossing the interstate",
                  "tumbleweeds piling in your lane"),
    "west_coast": ("a fog bank rolling across the lanes",
                   "a stalled car jutting off the shoulder"),
    "northwest": ("an elk crossing the road",
                  "standing water in your lane"),
}


def hazard_choices(region: str) -> tuple[str, ...]:
    """The hazard pool for a region: nationwide staples plus local flavor."""
    return GENERIC_HAZARDS + REGION_HAZARDS.get(region, ())


class TripEventKind(Enum):
    ZONE_ENTER = "zone_enter"
    ZONE_EXIT = "zone_exit"
    STOP_AHEAD = "stop_ahead"
    STOP_REACHED = "stop_reached"
    CITY_REACHED = "city_reached"
    HAZARD = "hazard"
    WEATHER_CHANGE = "weather_change"
    INSPECTION = "inspection"
    GPS_CUE = "gps_cue"
    STATE_CROSSING = "state_crossing"
    CHECKPOINT = "checkpoint"
    ARRIVED = "arrived"


@dataclass
class TripEvent:
    kind: TripEventKind
    message: str
    data: dict = field(default_factory=dict)


@dataclass
class Zone:
    """A stretch of road with a reduced speed limit."""

    start_mi: float
    end_mi: float
    limit_mph: float
    reason: str


@dataclass
class RoadStop:
    name: str
    at_mi: float
    type: str = "travel_center"
    actions: tuple[str, ...] = ()
    services: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        return STOP_TYPE_LABELS.get(self.type, "stop")

    @property
    def spoken_name(self) -> str:
        return f"{self.label}: {self.name}"


@dataclass
class TrafficLead:
    """A simple lead vehicle or traffic pack on the current itinerary."""

    at_mi: float
    speed_mph: float
    reason: str
    length_mi: float = 5.0

    @property
    def end_mi(self) -> float:
        return self.at_mi + self.length_mi


@dataclass(frozen=True)
class TrafficContext:
    lead: TrafficLead
    gap_mi: float
    closing_mph: float

    @property
    def gap_seconds(self) -> float:
        speed = max(1.0, self.lead.speed_mph)
        return self.gap_mi / speed * 3600.0


@dataclass(frozen=True)
class NavigationCue:
    key: str
    kind: str
    at_mi: float
    text: str
    near_text: str = ""


class Trip:
    """One delivery run along a chosen route."""

    def __init__(self, route: Route, truck: TruckState, weather: WeatherSystem,
                 time_scale: float = 20.0, seed: int | None = None,
                 start_hour: float = 12.0) -> None:
        self.route = route
        self.truck = truck
        self.weather = weather
        self.time_scale = time_scale
        self.start_hour = start_hour   # clock hour of day at departure
        self.position_mi = 0.0
        self.game_minutes = 0.0
        self.finished = False
        self.hos_violation = False     # set by the UI layer; gates inspections
        self._rng = random.Random(seed)
        # separate stream so inspections never disturb hazard/zone layout
        self._insp_rng = random.Random(None if seed is None else seed ^ 0x5EED)
        self._events: list[TripEvent] = []
        self._leg_starts = self._compute_leg_starts()
        self.stops = self._place_stops()
        self.traffic_leads = self._place_traffic()
        self.navigation_cues = self._build_navigation_cues()
        self.zones = self._place_zones()
        self._announced_stops: set[str] = set()
        self._announced_cities: set[int] = set()
        self._announced_navigation: set[str] = set()
        self._active_zone: Zone | None = None
        self._hazard_check_mi = 5.0
        self._inspection_check_mi = 10.0
        self._traffic_warning_mi = 1.0

    # -- layout -----------------------------------------------------------------

    def _compute_leg_starts(self) -> list[float]:
        starts, acc = [], 0.0
        for leg in self.route.legs:
            starts.append(acc)
            acc += leg.miles
        return starts

    def _place_stops(self) -> list[RoadStop]:
        """Place each leg's named stops at its curated route mileage."""
        out: list[RoadStop] = []
        for i, (start, leg) in enumerate(zip(self._leg_starts, self.route.legs,
                                             strict=True)):
            from_city = self.route.cities[i]
            leg_stops = sorted(
                leg.stops,
                key=lambda stop: _stop_offset_for_direction(stop.at_mi, leg.miles,
                                                            from_city == leg.a),
            )
            for stop in leg_stops:
                offset = _stop_offset_for_direction(stop.at_mi, leg.miles,
                                                    from_city == leg.a)
                at = start + offset
                out.append(RoadStop(stop.name, at, stop.type,
                                    stop.actions, stop.services))
        return out

    def _build_navigation_cues(self) -> list[NavigationCue]:
        cues: list[NavigationCue] = []
        for i, (start, leg) in enumerate(zip(self._leg_starts, self.route.legs,
                                             strict=True)):
            forward = self.route.cities[i] == leg.a
            toward = self.route.cities[i + 1]
            segment_miles = leg.miles
            if segment_miles >= 40.0:
                cues.append(NavigationCue(
                    f"continue:{i}",
                    "continue",
                    start + 0.1,
                    f"Continue on {leg.highway} for {segment_miles:.0f} miles "
                    f"toward {toward}.",
                ))
            if i > 0 and self.route.legs[i - 1].highway != leg.highway:
                cues.append(NavigationCue(
                    f"maneuver:{i}",
                    "maneuver",
                    start,
                    f"keep right for {leg.highway} toward {toward}",
                    f"Keep right now for {leg.highway} toward {toward}.",
                ))
            for crossing in leg.state_crossings:
                offset = _stop_offset_for_direction(crossing.at_mi, leg.miles, forward)
                into_state = crossing.state if forward else crossing.from_state
                from_state = crossing.from_state if forward else crossing.state
                place = crossing.place
                cues.append(NavigationCue(
                    f"state:{i}:{crossing.at_mi}:{into_state}",
                    "state_crossing",
                    start + offset,
                    f"crossing from {from_state} into {into_state} near {place}",
                    f"Crossing into {into_state} near {place}.",
                ))
            for checkpoint in leg.checkpoints:
                offset = _stop_offset_for_direction(checkpoint.at_mi, leg.miles, forward)
                place = checkpoint.name
                state = f", {checkpoint.state}" if checkpoint.state else ""
                highway = checkpoint.highway or leg.highway
                cues.append(NavigationCue(
                    f"checkpoint:{i}:{checkpoint.at_mi}:{place}",
                    "checkpoint",
                    start + offset,
                    f"{place}{state} on {highway}",
                    f"Passing {place}{state} on {highway}.",
                ))
            for stop in leg.stops:
                offset = _stop_offset_for_direction(stop.at_mi, leg.miles, forward)
                cues.append(NavigationCue(
                    f"rest_stop:{i}:{stop.at_mi}:{stop.name}",
                    "rest_stop",
                    start + offset,
                    f"{stop.label} ahead",
                    f"{stop.label.capitalize()} ahead in 1 mile; press X to take the exit.",
                ))
        for i, lead in enumerate(self.traffic_leads):
            cues.append(NavigationCue(
                f"traffic:{i}:{lead.at_mi:.1f}",
                "traffic",
                lead.at_mi,
                f"{lead.reason} at {lead.speed_mph:.0f} miles per hour",
                f"Traffic slowing ahead; target speed {lead.speed_mph:.0f}.",
            ))
        cues.sort(key=lambda cue: cue.at_mi)
        return cues

    def _place_zones(self) -> list[Zone]:
        """Random construction/traffic zones, roughly one per 150 miles.

        At night most traffic zones never form: roads are sparse after dark,
        so a departure in the night band yields fewer heavy-traffic stretches.
        Deterministic for a given seed and departure hour.
        """
        night = is_night(self.start_hour)
        zones: list[Zone] = []
        total = self.route.miles
        n = max(0, int(total / 150))
        for _ in range(n):
            at = self._rng.uniform(15, max(16, total - 20))
            length = self._rng.uniform(3, 9)
            if self._rng.random() < 0.6:
                zones.append(Zone(at, at + length, 45, "construction"))
            elif not night or self._rng.random() < NIGHT_TRAFFIC_KEEP:
                zones.append(Zone(at, at + length, 50, "heavy traffic"))
        zones.sort(key=lambda z: z.start_mi)
        return zones

    def _place_traffic(self) -> list[TrafficLead]:
        leads: list[TrafficLead] = []
        effects = self.weather.effects
        bad_weather_bias = 0.0
        if effects.grip < 0.9:
            bad_weather_bias += (0.9 - effects.grip) * 0.45
        if effects.visibility_mi < 3.0:
            bad_weather_bias += (3.0 - effects.visibility_mi) * 0.05
        night = is_night(self.start_hour)
        for start, leg in zip(self._leg_starts, self.route.legs, strict=True):
            if leg.miles < 70.0:
                continue
            metro_bias = 0.18 if leg.checkpoints else 0.0
            night_bias = -0.08 if night else 0.0
            density = min(0.86, max(0.05,
                          0.22 + leg.miles / 900.0 + metro_bias
                          + bad_weather_bias + night_bias))
            if self._rng.random() > density:
                continue
            at = start + self._rng.uniform(25.0, max(26.0, leg.miles - 20.0))
            weather_slowdown = max(
                0.0,
                min(16.0, (1.0 - effects.grip) * 22.0
                    + max(0.0, 3.0 - effects.visibility_mi) * 1.5),
            )
            speed = max(28.0, self._rng.uniform(42.0, 58.0) - weather_slowdown)
            reason = self._rng.choice((
                "slow lead traffic",
                "traffic queue ahead",
                "merging traffic",
                "lane restriction",
            ))
            if bad_weather_bias and self._rng.random() < 0.45:
                reason = self._rng.choice((
                    "traffic slowing for wet roads",
                    "traffic slowing for low visibility",
                ))
            leads.append(TrafficLead(at, speed, reason, self._rng.uniform(3.0, 8.0)))
        leads.sort(key=lambda lead: lead.at_mi)
        return leads

    # -- queries -----------------------------------------------------------------

    @property
    def total_miles(self) -> float:
        return self.route.miles

    @property
    def remaining_miles(self) -> float:
        return max(0.0, self.total_miles - self.position_mi)

    @property
    def current_hour(self) -> float:
        """Clock hour of day right now (departure hour plus trip time)."""
        return (self.start_hour + self.game_minutes / 60.0) % 24.0

    @property
    def current_leg_index(self) -> int:
        for i in range(len(self.route.legs) - 1, -1, -1):
            if self.position_mi >= self._leg_starts[i]:
                return i
        return 0

    @property
    def current_target_city(self):
        """City object the current leg is heading toward; drives the weather."""
        name = self.route.cities[self.current_leg_index + 1]
        return get_world().cities[name]

    @property
    def current_region(self) -> str:
        return self.current_target_city.region

    def grade_at(self, mile: float) -> float:
        """Route-derived grade when available, conservative fallback otherwise."""
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
        """Terrain classification for the current route mile."""
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
        for z in self.zones:
            if z.start_mi <= mile <= z.end_mi:
                return z.limit_mph, z.reason
        return BASE_SPEED_LIMIT_MPH, None

    def traffic_context(self) -> TrafficContext | None:
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

    def traffic_target_speed(self) -> float | None:
        context = self.traffic_context()
        if context is None:
            return None
        return context.lead.speed_mph

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
            if 0 <= ahead <= within_mi and (
                    best is None or stop.at_mi < best.at_mi):
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
            dist = f"{self.remaining_miles:.0f} miles remaining of {self.total_miles:.0f}"
        else:
            dist = (f"{self.remaining_miles * 1.609:.0f} kilometers remaining "
                    f"of {self.total_miles * 1.609:.0f}")
        leg = self.route.legs[self.current_leg_index]
        toward = self.route.cities[self.current_leg_index + 1]
        state = get_world().cities[toward].state
        next_context = self.next_navigation_context()
        terrain = self.terrain_at()
        terrain_text = "Grade level" if terrain == "flat" else f"Terrain {terrain}"
        return (f"{dist}. On {leg.highway} toward {toward}, {state}. "
                f"{terrain_text}. {next_context}")

    def next_navigation_context(self) -> str:
        cue = self.next_navigation_cue()
        if cue is None:
            return f"Destination {self.route.cities[-1]} ahead."
        ahead = max(0.0, cue.at_mi - self.position_mi)
        if cue.kind == "rest_stop":
            return f"Next stop in {ahead:.0f} miles: {cue.text}."
        if cue.kind == "state_crossing":
            return f"Next state line in {ahead:.0f} miles: {cue.text}."
        if cue.kind == "maneuver":
            return f"Next maneuver in {ahead:.0f} miles: {cue.text}."
        if cue.kind == "checkpoint":
            return f"Next place in {ahead:.0f} miles: {cue.text}."
        if cue.kind == "traffic":
            return f"Traffic in {ahead:.0f} miles: {cue.text}."
        return f"Next guidance in {ahead:.0f} miles: {cue.text}."

    def next_navigation_cue(self) -> NavigationCue | None:
        for cue in self.navigation_cues:
            if cue.at_mi > self.position_mi + 0.05 and cue.kind != "continue":
                return cue
        return None

    def restore(self, position_mi: float, game_minutes: float) -> None:
        """Jump to a saved point without re-announcing what is behind it."""
        self.position_mi = max(0.0, min(position_mi, self.total_miles))
        self.game_minutes = game_minutes
        for stop in self.stops:
            if stop.at_mi <= self.position_mi:
                self._announced_stops.add(stop.name)
        for cue in self.navigation_cues:
            if cue.at_mi <= self.position_mi:
                self._announced_navigation.add(f"{cue.key}:advance")
                self._announced_navigation.add(f"{cue.key}:near")
        for i, start in enumerate(self._leg_starts):
            if i and self.position_mi >= start:
                self._announced_cities.add(i)
        for zone in self.zones:
            if zone.start_mi <= self.position_mi <= zone.end_mi:
                self._active_zone = zone
                break

    # -- main update ----------------------------------------------------------------

    def update(self, dt: float) -> list[TripEvent]:
        """Advance the trip by real seconds; returns events for the UI layer."""
        self._events = []
        if self.finished:
            return self._events

        # weather drives truck grip and evolves over game time
        game_min = dt * self.time_scale / 60.0
        self.game_minutes += game_min
        target = self.current_target_city
        self.weather.set_region(target.region)
        self.weather.set_city(target.name, target.lat, target.lon)
        changed = self.weather.update(game_min)
        if changed is not None:
            self._emit(TripEventKind.WEATHER_CHANGE,
                       f"Weather changing: {self.weather.describe()}",
                       weather=changed)
        self.truck.grip = self.weather.effects.grip
        self.truck.grade = self.grade_at(self.position_mi)
        self.truck.fuel_burn_mult = self.time_scale

        moved_mi = self.truck.velocity_mps * dt * self.time_scale / 1609.344
        self.position_mi += moved_mi
        if self.position_mi < 0.0:
            self.position_mi = 0.0

        self._check_zones()
        self._check_stops()
        self._check_navigation_cues()
        self._check_cities()
        if moved_mi > 0.0:
            self._check_hazards(moved_mi)
            self._check_inspections(moved_mi)

        if self.position_mi >= self.total_miles:
            self.position_mi = self.total_miles
            self.finished = True
            self._emit(TripEventKind.ARRIVED,
                       f"You have arrived in {self.route.cities[-1]}.")
        return self._events

    # -- event checks ----------------------------------------------------------------

    def _emit(self, kind: TripEventKind, message: str, **data) -> None:
        self._events.append(TripEvent(kind, message, data))

    def _check_zones(self) -> None:
        zone = None
        for z in self.zones:
            if z.start_mi <= self.position_mi <= z.end_mi:
                zone = z
                break
        if zone is not self._active_zone:
            if zone is not None:
                self._emit(TripEventKind.ZONE_ENTER,
                           f"{zone.reason} ahead. Speed limit {zone.limit_mph:.0f}.",
                           zone=zone)
            elif self._active_zone is not None:
                self._emit(TripEventKind.ZONE_EXIT,
                           f"End of {self._active_zone.reason} zone. "
                           f"Speed limit {BASE_SPEED_LIMIT_MPH:.0f}.")
            self._active_zone = zone

    def _check_stops(self) -> None:
        for stop in self.stops:
            ahead = stop.at_mi - self.position_mi
            if 0 < ahead <= 5.0 and stop.name not in self._announced_stops:
                self._announced_stops.add(stop.name)
                self._emit(TripEventKind.STOP_AHEAD,
                           f"{stop.spoken_name} in {ahead:.0f} miles. "
                           "Press X to take the exit for it.",
                           stop=stop)

    def _check_navigation_cues(self) -> None:
        for cue in self.navigation_cues:
            ahead = cue.at_mi - self.position_mi
            if cue.kind == "continue":
                key = f"{cue.key}:near"
                if -0.5 <= ahead <= 0.5 and key not in self._announced_navigation:
                    self._announced_navigation.add(key)
                    self._emit(TripEventKind.GPS_CUE, cue.text, cue=cue)
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
                    self._emit(
                        TripEventKind.GPS_CUE,
                        f"Traffic slowing ahead in {ahead:.0f} miles; {cue.text}.",
                        cue=cue,
                    )
                continue
            advance_key = f"{cue.key}:advance"
            near_key = f"{cue.key}:near"
            if 0 < ahead <= 2.0 and advance_key not in self._announced_navigation:
                self._announced_navigation.add(advance_key)
                if cue.kind == "maneuver":
                    message = f"In {ahead:.0f} miles, {cue.text}."
                else:
                    message = f"In {ahead:.0f} miles, {cue.text}."
                self._emit(TripEventKind.GPS_CUE, message, cue=cue)
            if -0.1 <= ahead <= 0.1 and near_key not in self._announced_navigation:
                self._announced_navigation.add(near_key)
                if cue.kind == "state_crossing":
                    self._emit(TripEventKind.STATE_CROSSING, cue.near_text, cue=cue)
                elif cue.kind == "checkpoint":
                    self._emit(TripEventKind.CHECKPOINT, cue.near_text, cue=cue)
                else:
                    self._emit(TripEventKind.GPS_CUE, cue.near_text, cue=cue)

    def _check_cities(self) -> None:
        for i, start in enumerate(self._leg_starts):
            if i == 0 or i in self._announced_cities:
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
                crossing = (f"Crossing into {city_state}. "
                            if city_state != prev_state else "")
                self._emit(TripEventKind.CITY_REACHED,
                           f"{crossing}Passing {city}, {city_state}. "
                           f"Continuing on {leg.highway} toward {nxt}.")

    def _hazard_risk(self) -> float:
        """Chance of a hazard at each check; worse in fog and after dark."""
        vis = self.weather.effects.visibility_mi
        risk = 0.25 + (0.25 if vis < 2 else 0.0)
        if is_night(self.current_hour):
            risk += NIGHT_HAZARD_BONUS
        return risk

    def _check_hazards(self, moved_mi: float) -> None:
        """Occasional road hazards that demand braking."""
        context = self.traffic_context()
        if (context is not None and context.closing_mph > 8.0
                and context.gap_seconds <= TRAFFIC_WARNING_GAP_S
                and self.position_mi >= self._traffic_warning_mi):
            self._traffic_warning_mi = self.position_mi + 8.0
            self._emit(
                TripEventKind.HAZARD,
                f"Brake now! {context.lead.reason.capitalize()} "
                f"{context.gap_mi:.1f} miles ahead.",
                deadline_s=2.5,
                traffic=context,
            )
            return
        self._hazard_check_mi -= moved_mi
        if self._hazard_check_mi > 0:
            return
        self._hazard_check_mi = self._rng.uniform(20, 60)
        if self._rng.random() < self._hazard_risk():
            hazard = self._rng.choice(hazard_choices(self.current_region))
            # Lead with the action: the player can be on the brakes before
            # the sentence finishes. deadline_s is the reaction slack on top
            # of the braking time the driving state computes from speed.
            self._emit(TripEventKind.HAZARD,
                       f"Brake now! {hazard[0].upper()}{hazard[1:]}.",
                       deadline_s=self._rng.uniform(3.0, 4.5))

    def _check_inspections(self, moved_mi: float) -> None:
        """Random roadside inspections while driving past an HOS limit.

        Uses its own random stream so enabling or violating hours of service
        never changes the hazard and zone layout of a seeded trip.
        """
        self._inspection_check_mi -= moved_mi
        if self._inspection_check_mi > 0:
            return
        self._inspection_check_mi = self._insp_rng.uniform(15, 40)
        if self.hos_violation and self._insp_rng.random() < 0.5:
            self._emit(TripEventKind.INSPECTION,
                       "Weigh station ahead. Officers wave you in for a log check.")


def _stop_offset_for_direction(at_mi: float, leg_miles: float, forward: bool) -> float:
    return at_mi if forward else leg_miles - at_mi


def _fallback_grade(terrain: str, mile: float, highway: str) -> float:
    """Auditable fallback for legs without elevation samples.

    Flat roads stay level. Hills and mountains get a small deterministic profile
    from the curated terrain label, but corridor metadata should replace this
    as routes are enriched.
    """
    amplitude = {"flat": 0.0, "hills": 0.012, "mountain": 0.035}.get(terrain, 0.0)
    if amplitude == 0.0:
        return 0.0
    wavelength = {"hills": 14.0, "mountain": 8.0}.get(terrain, 16.0)
    phase = (sum(ord(ch) for ch in highway) % 628) / 100.0
    return amplitude * math.sin(2 * math.pi * mile / wavelength + phase)
