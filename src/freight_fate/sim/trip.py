# ruff: noqa: F403,F405
"""Trip simulation: progress along a route, grades, zones, stops, and events."""

from __future__ import annotations

import random

from ..data.world import Leg, Route, get_world
from .hos import clock_text, is_night
from .timezones import appointment_text, city_zone, zone_for
from .trip_models import *
from .trip_route_helpers import *
from .vehicle import TruckState
from .weather import WeatherKind, WeatherSystem

# A stop is announced ("stop ahead") when it first comes within this many miles
# ahead (_check_stops). restore() seeds this SAME window as already-announced so
# a resumed trip does not re-announce a stop that was called out before the save.
# Keep the two uses on one constant; letting them drift is what caused resumed
# trips to occasionally replay a STOP_AHEAD.
STOP_AHEAD_LOOKAHEAD_MI = 5.0


def _spoken_distance(value: float, unit: str) -> str:
    """A whole-number distance with the unit pluralized for speech, so a
    screen reader never hears "in 1 miles"."""
    rounded = round(value)
    return f"{rounded:.0f} {unit if rounded == 1 else unit + 's'}"


class Trip:
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
        self._rng = random.Random(seed)
        self._insp_rng = random.Random(None if seed is None else seed ^ 0x5EED)
        self._cond_rng = random.Random(None if seed is None else seed ^ 0xC0FFEE)
        self._events: list[TripEvent] = []
        self._leg_starts = self._compute_leg_starts()
        self._city_mileposts = list(self._leg_starts) + [self.total_miles]
        self.start_timezone, self.timezone_crossings = self._compute_timezone_crossings()
        self._current_timezone = self.start_timezone
        self.stops = self._place_stops()
        self.traffic_leads = self._place_traffic()
        self.navigation_cues = self._build_navigation_cues()
        self.toll_charges: list[TollCharge] = []
        self.zones = self._place_zones()
        self.patrols = self._place_patrols()
        self._announced_stops: set[str] = set()
        self._announced_cities: set[int] = set()
        self._announced_navigation: set[str] = set()
        self._charged_tolls: set[str] = set()
        self._active_zone: Zone | None = None
        self._announced_speed_limit: float | None = None
        self._announced_zone_warnings: set[str] = set()
        self._construction_zone_grace_start: dict[str, float] = {}
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
        self.navigation_cues = self._build_navigation_cues()

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

    def _compute_leg_starts(self) -> list[float]:
        starts, acc = [], 0.0
        for leg in self.route.legs:
            starts.append(acc)
            acc += leg.miles
        return starts

    def _timezone_samples(self) -> list[tuple[float, TimeZone]]:
        """(trip mile, zone) along the route, from city and route-point geometry.

        City endpoints are sampled too, so a leg with no baked geometry still
        lands its clock change somewhere between two cities in different zones.
        """
        world = get_world()
        samples: list[tuple[float, TimeZone]] = []
        for i, (start, leg) in enumerate(zip(self._leg_starts, self.route.legs, strict=True)):
            forward = self.route.cities[i] == leg.a
            city = world.cities.get(self.route.cities[i])
            if city is not None and (city.lat or city.lon):
                samples.append((start, city_zone(city)))
            for pt in leg.route_points:
                offset = _stop_offset_for_direction(pt.at_mi, leg.miles, forward)
                zone = zone_for(pt.lat, pt.lon, _leg_state_at(leg, pt.at_mi))
                samples.append((start + offset, zone))
        last = world.cities.get(self.route.cities[-1])
        if last is not None and (last.lat or last.lon):
            samples.append((self.total_miles, city_zone(last)))
        samples.sort(key=lambda s: s[0])
        return samples

    def _compute_timezone_crossings(self) -> tuple[TimeZone, list[TimezoneCrossing]]:
        """Start zone plus the deduped clock-change mileposts for the route.

        A flip that reverts within ``TIMEZONE_DWELL_MI`` is a road hugging the
        boundary, not a crossing, and is dropped -- same idea as the state
        crossing sanitizer.
        """
        samples = self._timezone_samples()
        if not samples:
            return zone_for(0.0, 0.0), []
        current = samples[0][1]
        start = current
        crossings: list[TimezoneCrossing] = []
        for i, (mile, zone) in enumerate(samples):
            if zone.key == current.key:
                continue
            settled = True
            for later_mile, later_zone in samples[i + 1 :]:
                if later_mile - mile > TIMEZONE_DWELL_MI:
                    break
                if later_zone.key == current.key:
                    settled = False
                    break
            if settled:
                crossings.append(TimezoneCrossing(mile, current, zone))
                current = zone
        return start, crossings

    def timezone_at(self, mile: float) -> TimeZone:
        """The time zone in effect at a trip milepost."""
        zone = self.start_timezone
        for crossing in self.timezone_crossings:
            if crossing.at_mi <= mile:
                zone = crossing.to_zone
            else:
                break
        return zone

    @property
    def current_timezone(self) -> TimeZone:
        return self.timezone_at(self.position_mi)

    @property
    def destination_timezone(self) -> TimeZone:
        return self.timezone_at(self.total_miles)

    @property
    def local_hour(self) -> float:
        """The wall clock where the truck is right now; what the player hears.

        ``current_hour`` stays on the absolute (Eastern-reference) timeline
        for durations and deadlines; only speech and day/night feel go local.
        """
        return (self.current_hour + self.current_timezone.offset_h) % 24.0

    @property
    def local_start_hour(self) -> float:
        """The local wall clock at departure, for day/night placement."""
        return (self.start_hour + self.start_timezone.offset_h) % 24.0

    def deadline_clock_text(self, deadline_game_h: float, zone: TimeZone | None = None) -> str:
        """The delivery appointment as a receiver would quote it: the wall
        clock in the destination's zone, e.g. '6 PM Central Time tomorrow'.

        ``zone`` overrides where the appointment is read -- a pickup drive's
        trip ends at the origin facility, so its caller passes the delivery
        city's zone instead of this trip's endpoint.
        """
        now = self.start_hour + self.game_minutes / 60.0
        remaining = deadline_game_h - self.game_minutes / 60.0
        return appointment_text(now, remaining, zone or self.destination_timezone)

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
            toward_key = self.route.cities[i + 1]
            toward = get_world().spoken_city(toward_key)
            heading = _leg_heading(leg.highway, self.route.cities[i], toward_key)
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
                        "",
                    )
                )
        for i, lead in enumerate(self.traffic_leads):
            cues.append(
                NavigationCue(
                    f"traffic:{i}:{lead.at_mi:.1f}",
                    "traffic",
                    lead.at_mi,
                    lead.reason,
                    f"Traffic slowing ahead; target speed {lead.speed_mph:.0f}.",
                    speed_mph=lead.speed_mph,
                )
            )
        cues.sort(key=lambda cue: cue.at_mi)
        return cues

    def _place_zones(self) -> list[Zone]:
        night = is_night(self.local_start_hour)
        zones: list[Zone] = []
        total = self.route.miles
        n = max(0, int(total / 150))
        # Spans already claimed by placed zones. Real work zones are signed
        # well apart; without this, independent draws could nest one zone
        # inside another or butt two together with no open road between.
        spans: list[tuple[float, float]] = []
        for _ in range(n):
            for _attempt in range(8):
                at = self._rng.uniform(15, max(16, total - 20))
                end = at + self._rng.uniform(3, 9)
                if all(
                    at > s_end + ZONE_MIN_GAP_MI or end < s_start - ZONE_MIN_GAP_MI
                    for s_start, s_end in spans
                ):
                    break
            else:
                continue  # the route is crowded; place fewer zones instead
            if self._rng.random() < 0.6:
                zones.append(Zone(at, end, 45, "construction"))
                spans.append((at, end))
            elif not night or self._rng.random() < NIGHT_TRAFFIC_KEEP:
                zones.append(Zone(at, end, 50, "heavy traffic"))
                spans.append((at, end))
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
        if is_night(self.local_start_hour):
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
                PatrolWindow(at, at + length, max(0.1, min(0.95, intensity)), "speed trap")
            )
        for zone in self.zones:
            if zone.reason == "construction":
                patrols.append(
                    PatrolWindow(
                        zone.start_mi,
                        zone.end_mi,
                        min(0.95, 0.9 * self.hazard_scale),
                        "construction patrol",
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
        density = min(
            0.86, max(0.05, 0.22 + leg.miles / 900.0 + metro_bias + bad_weather_bias + night_bias)
        )
        return density * self.hazard_scale

    def _place_traffic(self) -> list[TrafficLead]:
        leads: list[TrafficLead] = []
        effects = self.weather.effects
        bad_weather_bias = 0.0
        if effects.grip < 0.9:
            bad_weather_bias += (0.9 - effects.grip) * 0.45
        if effects.visibility_mi < 3.0:
            bad_weather_bias += (3.0 - effects.visibility_mi) * 0.05
        night = is_night(self.local_start_hour)
        for start, leg in zip(self._leg_starts, self.route.legs, strict=True):
            if leg.miles < 70.0:
                continue
            density = self._leg_traffic_density(leg, bad_weather_bias, night)
            if self._rng.random() > density:
                continue
            at = start + self._rng.uniform(25.0, max(26.0, leg.miles - 20.0))
            weather_slowdown = max(
                0.0,
                min(
                    16.0, (1.0 - effects.grip) * 22.0 + max(0.0, 3.0 - effects.visibility_mi) * 1.5
                ),
            )
            speed = max(28.0, self._rng.uniform(42.0, 58.0) - weather_slowdown)
            reason = self._rng.choice(
                (
                    "slow lead traffic",
                    "traffic queue ahead",
                    "merging traffic",
                    "lane restriction",
                )
            )
            if bad_weather_bias and self._rng.random() < 0.45:
                reason = self._rng.choice(
                    (
                        "traffic slowing for wet roads",
                        "traffic slowing for low visibility",
                    )
                )
            leads.append(TrafficLead(at, speed, reason, self._rng.uniform(3.0, 8.0)))
        leads.sort(key=lambda lead: lead.at_mi)
        return leads

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

    def _active_zone_at(self, mile: float) -> Zone | None:
        active = [z for z in self.zones if z.start_mi <= mile <= z.end_mi]
        if not active:
            return None
        return min(active, key=lambda z: z.limit_mph)

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
        world = get_world()
        toward_name = world.spoken_city(toward, qualified=False)
        state = world.cities[toward].state
        next_context = self.next_navigation_context(imperial)
        terrain_text = self._current_grade_text()
        return (
            f"{dist}. On {leg.highway} toward {toward_name}, {state}. "
            f"{terrain_text}. {next_context}"
        )

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
            return f"Destination {get_world().spoken_city(self.route.cities[-1])} ahead."
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
            # Seed passed stops AND stops already inside the "stop ahead" window;
            # both were announced before the save, so a resume must not re-fire them.
            if stop.at_mi <= self.position_mi + STOP_AHEAD_LOOKAHEAD_MI:
                self._announced_stops.add(stop.name)
        for cue in self.navigation_cues:
            if cue.at_mi <= self.position_mi:
                self._announced_navigation.add(f"{cue.key}:advance")
                self._announced_navigation.add(f"{cue.key}:near")
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
        self._current_timezone = self.timezone_at(self.position_mi)

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

    # -- main update ----------------------------------------------------------------

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
        # Identity for the live-weather cache: cities sharing a spoken name
        # ("Jackson") are still different places with different skies.
        self.weather.set_city(target.key, target.lat, target.lon)
        changed = self.weather.update(game_min)
        if changed is not None:
            self._emit(
                TripEventKind.WEATHER_CHANGE,
                f"Weather changing: {self.weather.describe(self.imperial)}",
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

        self._check_zones()
        self._check_speed_limit()
        self._check_stops()
        self._check_navigation_cues()
        self._check_tolls()
        self._check_cities()
        self._check_timezone()
        if moved_mi > 0.0:
            self._check_hazards(moved_mi)
            self._check_conditions_speed(moved_mi)
            self._check_inspections(moved_mi)

        if self.position_mi >= self.total_miles:
            self.finished = True
            self._emit(
                TripEventKind.ARRIVED,
                f"You have arrived in {get_world().spoken_city(self.route.cities[-1])}.",
            )
        return self._events

    # -- event checks ----------------------------------------------------------------

    def _emit(self, kind: TripEventKind, message: str, **data) -> None:
        self._events.append(TripEvent(kind, message, data))

    def _zone_warning_lookahead_mi(self) -> float:
        """Lead distance for a zone warning, scaled so the player gets roughly
        ``ZONE_WARNING_REAL_S`` of real time despite speed and time compression."""
        speed = max(self.truck.speed_mph, 30.0)
        miles = ZONE_WARNING_REAL_S * speed * self.effective_time_scale / 3600.0
        return max(ZONE_WARNING_LOOKAHEAD_MI, min(miles, ZONE_WARNING_MAX_MI))

    def _check_zones(self) -> None:
        lookahead = self._zone_warning_lookahead_mi()
        for zone in self.zones:
            key = _zone_key(zone)
            ahead = zone.start_mi - self.position_mi
            if 0 < ahead <= lookahead and key not in self._announced_zone_warnings:
                self._announced_zone_warnings.add(key)
                self._emit(
                    TripEventKind.GPS_CUE,
                    f"In {self._distance_text(ahead)}, {zone.reason} ahead. "
                    f"Speed limit {self._speed_value(zone.limit_mph)}.",
                    zone=zone,
                )
        zone = self._active_zone_at(self.position_mi)
        if zone is not self._active_zone:
            if zone is not None:
                if zone.reason == "construction":
                    self._construction_zone_grace_start[_zone_key(zone)] = zone.start_mi
                self._emit(
                    TripEventKind.ZONE_ENTER,
                    f"{zone.reason} ahead. Speed limit {self._speed_value(zone.limit_mph)}.",
                    zone=zone,
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

    def _check_timezone(self) -> None:
        """Announce a clock change the moment the truck passes a zone boundary.

        The message carries the new local time, so it is composed here at
        crossing time rather than baked into a static cue at trip start.
        """
        zone = self.timezone_at(self.position_mi)
        if zone.key == self._current_timezone.key:
            return
        previous = self._current_timezone
        self._current_timezone = zone
        # The new local time is the whole message: it shows which way the
        # clock jumped without spelling out an instruction the game already
        # handles, and it stays short on routes that cross often.
        self._emit(
            TripEventKind.TIMEZONE_CROSSING,
            f"Crossing into {zone.name}. It is now {clock_text(self.local_hour)}.",
            from_zone=previous,
            to_zone=zone,
        )

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
            where = f" approaching {get_world().spoken_city(city)}" if city else ""
            self._emit(
                TripEventKind.GPS_CUE, f"Speed limit {verb} {self._speed_value(limit)}{where}."
            )

    def _check_stops(self) -> None:
        for stop in self.stops:
            ahead = stop.at_mi - self.position_mi
            if 0 < ahead <= STOP_AHEAD_LOOKAHEAD_MI and stop.name not in self._announced_stops:
                self._announced_stops.add(stop.name)
                exit_part = f" at {stop.exit_label}" if stop.exit_label else ""
                parts = [f"{stop.spoken_name}{exit_part} in {self._distance_text(ahead)}."]
                if stop.parking_text:
                    parts.append(f"{stop.parking_text}.")
                parts.append("Press X to take the exit for it.")
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
                # Road stops already receive one actionable announcement from
                # _check_stops at five miles.  A second one-mile reminder made
                # busy routes needlessly repetitive.
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
            if cue.kind == "state_crossing":
                if ahead <= 0 and near_key not in self._announced_navigation:
                    self._announced_navigation.add(near_key)
                    self._emit(TripEventKind.STATE_CROSSING, cue.near_text, cue=cue)
                continue
            lookahead = 2.0
            if 0 < ahead <= lookahead and advance_key not in self._announced_navigation:
                self._announced_navigation.add(advance_key)
                message = f"In {self._distance_text(ahead)}, {cue.text}."
                self._emit(TripEventKind.GPS_CUE, message, cue=cue)
            if -0.1 <= ahead <= 0.1 and near_key not in self._announced_navigation:
                self._announced_navigation.add(near_key)
                if cue.kind == "checkpoint":
                    self._emit(TripEventKind.CHECKPOINT, cue.near_text, cue=cue)
                else:
                    self._emit(TripEventKind.GPS_CUE, cue.near_text, cue=cue)

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
                    f"{crossing}Passing {world.spoken_city(city, qualified=False)}, "
                    f"{city_state}. "
                    f"Continuing on {leg.highway} toward {world.spoken_city(nxt)}.",
                )

    def _hazard_risk(self) -> float:
        """Chance of a hazard at each check; worse in fog and after dark.

        Scaled by ``hazard_scale`` so relaxed mode keeps hazards rare while
        weather and night still make the hazards that do occur likelier.
        """
        vis = self.weather.effects.visibility_mi
        risk = 0.25 + (0.25 if vis < 2 else 0.0)
        if is_night(self.local_hour):
            risk += NIGHT_HAZARD_BONUS
        return risk * self.hazard_scale

    def _check_hazards(self, moved_mi: float) -> None:
        """Occasional road hazards that demand braking."""
        if self._is_facility_approach_route():
            # A deadhead crawl down a facility access road is minutes long at
            # yard speeds; a "brake now" ambush there is noise, not driving.
            return
        context = self.traffic_context()
        if (
            context is not None
            and context.closing_mph > 8.0
            and context.gap_seconds <= TRAFFIC_WARNING_GAP_S
            and self.position_mi >= self._traffic_warning_mi
        ):
            self._traffic_warning_mi = self.position_mi + 8.0
            self._emit(
                TripEventKind.HAZARD,
                f"Brake now! {context.lead.reason.capitalize()} "
                f"{self._gap_text(context.gap_mi)} ahead.",
                deadline_s=2.5,
                traffic=context,
            )
            return
        self._hazard_check_mi -= moved_mi
        if self._hazard_check_mi > 0:
            return
        self._hazard_check_mi = self._rng.uniform(20, 60)
        if self._rng.random() < self._hazard_risk():
            choices = eligible_hazards(
                self.current_region,
                self.weather.current,
                self.terrain_at(self.position_mi),
                self.local_hour,
            )
            if not choices:
                return
            texts, weights = zip(*choices, strict=True)
            hazard = self._rng.choices(texts, weights)[0]
            # Lead with the action: the player can be on the brakes before
            # the sentence finishes. deadline_s is the reaction slack on top
            # of the braking time the driving state computes from speed, cut
            # short in low visibility -- you see the hazard later in fog/rain.
            self._emit(
                TripEventKind.HAZARD,
                f"Brake now! {hazard[0].upper()}{hazard[1:]}.",
                deadline_s=(self._rng.uniform(3.0, 4.5) * self._visibility_reaction_factor()),
            )

    def _visibility_reaction_factor(self) -> float:
        """Fraction of the normal hazard reaction slack you get: low visibility
        means you see a hazard later, so less time to react. 1.0 in clear air,
        floored so a hazard is never physically impossible to answer."""
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
        """Driving well over the weather's safe speed risks a traction-loss
        incident, so the safe-speed readout has teeth instead of being flavor.
        Risk scales with how far over you are and how slick the road is."""
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
