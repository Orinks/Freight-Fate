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

from ..data.world import Route
from .vehicle import TruckState
from .weather import WeatherSystem

BASE_SPEED_LIMIT_MPH = 70.0


class TripEventKind(Enum):
    ZONE_ENTER = "zone_enter"
    ZONE_EXIT = "zone_exit"
    STOP_AHEAD = "stop_ahead"
    STOP_REACHED = "stop_reached"
    CITY_REACHED = "city_reached"
    HAZARD = "hazard"
    WEATHER_CHANGE = "weather_change"
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


class Trip:
    """One delivery run along a chosen route."""

    def __init__(self, route: Route, truck: TruckState, weather: WeatherSystem,
                 time_scale: float = 20.0, seed: int | None = None) -> None:
        self.route = route
        self.truck = truck
        self.weather = weather
        self.time_scale = time_scale
        self.position_mi = 0.0
        self.game_minutes = 0.0
        self.finished = False
        self._rng = random.Random(seed)
        self._events: list[TripEvent] = []
        self._leg_starts = self._compute_leg_starts()
        self.stops = self._place_stops()
        self.zones = self._place_zones()
        self._announced_stops: set[str] = set()
        self._announced_cities: set[int] = set()
        self._active_zone: Zone | None = None
        self._hazard_check_mi = 5.0

    # -- layout -----------------------------------------------------------------

    def _compute_leg_starts(self) -> list[float]:
        starts, acc = [], 0.0
        for leg in self.route.legs:
            starts.append(acc)
            acc += leg.miles
        return starts

    def _place_stops(self) -> list[RoadStop]:
        """Spread each leg's named stops evenly along that leg."""
        out: list[RoadStop] = []
        for start, leg in zip(self._leg_starts, self.route.legs, strict=True):
            n = len(leg.stops)
            for i, name in enumerate(leg.stops):
                at = start + leg.miles * (i + 1) / (n + 1)
                out.append(RoadStop(name, at))
        return out

    def _place_zones(self) -> list[Zone]:
        """Random construction/traffic zones, roughly one per 150 miles."""
        zones: list[Zone] = []
        total = self.route.miles
        n = max(0, int(total / 150))
        for _ in range(n):
            at = self._rng.uniform(15, max(16, total - 20))
            length = self._rng.uniform(3, 9)
            if self._rng.random() < 0.6:
                zones.append(Zone(at, at + length, 45, "construction"))
            else:
                zones.append(Zone(at, at + length, 50, "heavy traffic"))
        zones.sort(key=lambda z: z.start_mi)
        return zones

    # -- queries -----------------------------------------------------------------

    @property
    def total_miles(self) -> float:
        return self.route.miles

    @property
    def remaining_miles(self) -> float:
        return max(0.0, self.total_miles - self.position_mi)

    @property
    def current_leg_index(self) -> int:
        for i in range(len(self.route.legs) - 1, -1, -1):
            if self.position_mi >= self._leg_starts[i]:
                return i
        return 0

    @property
    def current_target_city(self):
        """City object the current leg is heading toward; drives the weather."""
        from ..data.world import get_world

        name = self.route.cities[self.current_leg_index + 1]
        return get_world().cities[name]

    @property
    def current_region(self) -> str:
        return self.current_target_city.region

    def grade_at(self, mile: float) -> float:
        """Deterministic rolling grade profile from the leg's terrain."""
        leg_i = self.current_leg_index
        leg = self.route.legs[leg_i]
        amplitude = {"flat": 0.008, "hills": 0.035, "mountain": 0.06}.get(leg.terrain, 0.01)
        wavelength = {"flat": 18.0, "hills": 9.0, "mountain": 6.0}.get(leg.terrain, 12.0)
        phase = (hash(leg.highway) % 628) / 100.0
        return amplitude * math.sin(2 * math.pi * mile / wavelength + phase)

    def speed_limit_at(self, mile: float) -> tuple[float, str | None]:
        for z in self.zones:
            if z.start_mi <= mile <= z.end_mi:
                return z.limit_mph, z.reason
        return BASE_SPEED_LIMIT_MPH, None

    def nearest_stop_within(self, radius_mi: float = 1.5) -> RoadStop | None:
        for stop in self.stops:
            if abs(stop.at_mi - self.position_mi) <= radius_mi:
                return stop
        return None

    def eta_game_hours(self, avg_mph: float = 55.0) -> float:
        return self.remaining_miles / max(1.0, avg_mph)

    def progress_summary(self, imperial: bool = True) -> str:
        if imperial:
            dist = f"{self.remaining_miles:.0f} miles remaining of {self.total_miles:.0f}"
        else:
            dist = (f"{self.remaining_miles * 1.609:.0f} kilometers remaining "
                    f"of {self.total_miles * 1.609:.0f}")
        leg = self.route.legs[self.current_leg_index]
        toward = self.route.cities[self.current_leg_index + 1]
        return f"{dist}. On {leg.highway} toward {toward}."

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

        self._check_zones()
        self._check_stops()
        self._check_cities()
        self._check_hazards(moved_mi)

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
                           f"{stop.name} in {ahead:.0f} miles. "
                           "Press T while stopped there to refuel and rest.",
                           stop=stop)

    def _check_cities(self) -> None:
        for i, start in enumerate(self._leg_starts):
            if i == 0 or i in self._announced_cities:
                continue
            if self.position_mi >= start:
                self._announced_cities.add(i)
                city = self.route.cities[i]
                nxt = self.route.cities[i + 1]
                leg = self.route.legs[i]
                self._emit(TripEventKind.CITY_REACHED,
                           f"Passing {city}. Continuing on {leg.highway} toward {nxt}.")

    def _check_hazards(self, moved_mi: float) -> None:
        """Occasional road hazards that demand braking."""
        self._hazard_check_mi -= moved_mi
        if self._hazard_check_mi > 0:
            return
        self._hazard_check_mi = self._rng.uniform(20, 60)
        vis = self.weather.effects.visibility_mi
        risk = 0.25 + (0.25 if vis < 2 else 0.0)
        if self._rng.random() < risk:
            hazard = self._rng.choice(["debris on the road", "a slow vehicle ahead",
                                       "an animal crossing"])
            self._emit(TripEventKind.HAZARD,
                       f"Caution: {hazard}! Brake now!",
                       deadline_s=self._rng.uniform(3.0, 4.5))
