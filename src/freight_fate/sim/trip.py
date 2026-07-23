# ruff: noqa: F403,F405
"""Trip simulation: progress along a route, grades, zones, stops, and events."""

from __future__ import annotations

import random
from dataclasses import replace

from ..data.curves import RouteCurve, route_curves
from ..data.world import Leg, Route, get_world
from ..units import spoken_distance
from .hos import clock_text, is_night
from .season import is_weekend
from .timezones import appointment_text, city_zone, zone_for
from .traffic_manager import TrafficManager
from .trip_models import *
from .trip_road_events import TripRoadEventMixin
from .trip_route_helpers import *
from .trip_traffic import TripTrafficMixin
from .vehicle import TruckState
from .weather import WeatherSystem

# A stop is announced ("stop ahead") when it first comes within this many miles
# ahead (_check_stops). restore() seeds this SAME window as already-announced so
# a resumed trip does not re-announce a stop that was called out before the save.
# Keep the two uses on one constant; letting them drift is what caused resumed
# trips to occasionally replay a STOP_AHEAD.
STOP_AHEAD_LOOKAHEAD_MI = 5.0
LOCAL_TURN_LOOKAHEAD_MI = 0.3  # street maneuvers announce at block scale, not highway scale

# The reaction allowance covers hearing the call out loud (the sentence
# itself takes several seconds through a screen reader), orienting by ear,
# and moving a foot to the brake -- audio-first reaction is slower than a
# sighted glance at a sign. The comfortable brake rate is a loaded rig's,
# not a car's. Retuned from the owner's AZ-260 run (2026-07-19): at the
# posted 55 the old floor left too little road.
PACENOTE_REACTION_S = 8.0
PACENOTE_BRAKE_MPH_PER_S = 2.5
PACENOTE_MARGIN_MPH = 3.0
PACENOTE_GENTLE_MARGIN_MPH = 8.0
PACENOTE_MIN_LEAD_MI = 0.33
PACENOTE_MAX_LEAD_MI = 1.5
# Adaptive floor: never call a curve with less than this many seconds of
# travel at the current speed. A fixed minimum distance shrinks, in time,
# exactly when speed makes the warning matter most.
PACENOTE_LEAD_FLOOR_S = 30.0
# A follower starting within this gap after a called curve rides that
# call's "then left/right" tail INSTEAD of getting its own call -- one
# read per S-chain, like a rally co-driver. Without the suppression every
# link also fired alone and chained bends flooded the driver with full
# calls seconds apart (owner's Payson run, 2026-07-19).
PACENOTE_LINK_GAP_MI = 0.3

# Speed-limit lookahead (the co-driver warns before a big posted drop, the
# same way she calls a curve): only drops of at least this size get a
# warning -- a 65-to-60 step needs no braking plan, a village 30 does.
LIMIT_DROP_WARN_MIN_DELTA_MPH = 10.0
# A newly entered lower limit that ends within this span has its length
# spoken ("for the next half a mile"), so a short village zone reads as a
# passing event, not a new cruising speed.
LIMIT_SHORT_ZONE_MI = 2.5
LIMIT_SCAN_STRIDE_MI = 0.1
LIMIT_SCAN_MAX_MI = 3.0


# One pluralization rule for every spoken distance in the game: the trip's own
# readouts and Settings.distance_text/speed_text all go through this.
_spoken_distance = spoken_distance


def _spoken_short_miles(miles: float, imperial: bool) -> str:
    """Colloquial short distance, mirroring ``Settings.short_distance_text``
    (quarter-mile steps, 100-meter steps) so the co-driver's limit calls
    sound like her curve calls in either unit. The phrasing source of truth
    stays in settings; keep the two in step."""
    if imperial:
        if miles > 1.125:
            return _spoken_distance(miles, "mile")
        quarters = max(1, round(miles * 4))
        return {
            1: "a quarter mile",
            2: "half a mile",
            3: "three quarters of a mile",
            4: "one mile",
        }.get(quarters, _spoken_distance(miles, "mile"))
    km = miles * 1.609344
    if km >= 0.95:
        return _spoken_distance(km, "kilometer")
    meters = max(1, round(km * 10)) * 100
    return f"{meters} meters"


def _cue_direction(text: str) -> str:
    """Turn direction for the earcon, read out of a baked maneuver cue.

    The local-geometry builders bake directional maneuvers ("Turn right
    onto Palm Street", "Continue onto Main Street"), so the panned earcon
    follows the spoken cue; directionless legacy cues ("Turn onto") return
    "" and stay speech-only."""
    lowered = text.lower()
    if "left" in lowered:
        return "left"
    if "right" in lowered:
        return "right"
    if lowered.startswith(("continue", "start")):
        return "ahead"
    return ""


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
        career_hours: float | None = None,
        traffic_provider=None,
        parking_provider=None,
        bobtail: bool = False,
        destination_label: str = "",
    ) -> None:
        self.route = route
        self.truck = truck
        self.weather = weather
        self.time_scale = time_scale
        self.hazard_scale = max(0.0, hazard_scale)
        self.start_hour = start_hour  # clock hour of day at departure
        # Absolute career clock at departure: carries the day of the week so
        # commuter rush hour only forms on weekdays. None (older callers and
        # tests) reads as a weekday, the more demanding default.
        self.career_hours = career_hours
        self._imperial = imperial
        self.traffic_provider = traffic_provider
        self.parking_provider = parking_provider
        # Running tractor-only opens stops a combination vehicle cannot enter.
        # Fixed for the run: it is a property of the job, not of the moment.
        # Defaults to False, the cautious read -- an unclassified caller never
        # gets promised a stop it might not fit into.
        self.bobtail = bobtail
        # On a facility-approach route the destination is a dock, not a town:
        # "toward Camp Verde" while pulling out of Camp Verde for its own
        # warehouse read as a wrong turn (owner playtest, 2026-07-19). The
        # spoken facility name replaces the city in the status line there.
        self.destination_label = destination_label
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
        self.start_timezone, self.timezone_crossings = self._compute_timezone_crossings()
        self._current_timezone = self.start_timezone
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
        self.landmarks = self._place_landmarks()
        self.billboards = self._place_billboards()
        self.patrols = self._place_patrols()
        self.traffic_manager.add_patrol_traffic(self.patrols)
        self.chain_law_areas = self._place_chain_law_areas()
        # Curve data: baked real-world curve records per leg, resolved to trip
        # miles so the driving state can query active curves and approach them.
        self.curves = self._place_curves()
        # True while the player is on an exit ramp that ends in a light or a
        # stop sign; the driving state maintains it every frame. It pins the
        # clock to real time (see effective_time_scale).
        self.controlled_ramp = False
        self._announced_chain_law: set[str] = set()
        self._announced_curves: set[str] = set()
        self._announced_landmarks: set[str] = set()
        self._announced_billboards: set[str] = set()
        self._announced_stops: set[str] = set()  # RoadStop.key, never the name
        self.planned_stop_key: str | None = None  # RoadStop.key, never the name
        # RoadStop.key of the stop whose exit is currently signaled or being
        # descended, published each tick by the driving state. Lets _check_stops
        # tell a driver who is taking the exit from one who blew past it. A key,
        # not a name: signaling for one Love's must not read as taking the exit
        # for the Love's you planned 300 miles further on. Recomputed every
        # frame, so it is never persisted.
        self._exit_in_progress: str | None = None
        # While on an exit ramp the truck is off the highway: the ramp consumes
        # its movement instead of the highway odometer, so the mile marker holds
        # and highway events pause. Both are republished every frame by the
        # driving state (on_ramp) or recomputed here (last_moved_mi), never saved.
        self.on_ramp: bool = False
        self.last_moved_mi: float = 0.0
        self._announced_cities: set[int] = set()
        self._announced_navigation: set[str] = set()
        self._charged_tolls: set[str] = set()
        self._active_zone: Zone | None = None
        self._announced_speed_limit: float | None = None
        self._warned_limit_drops: set[float] = set()
        self._announced_zone_warnings: set[str] = set()
        self._announced_traffic_pressures: set[str] = set()
        self._announced_npc_traffic: set[str] = set()
        self._announced_real_traffic: set[str] = set()
        self._next_real_traffic_check_mi = 0.0
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
        if self.controlled_ramp:
            # A ramp ending in a light or a sign plays out in real time
            # from the gore: the stop-sign warning must buy human reaction
            # seconds, not compressed ones. A hot entry used to burn the
            # whole half mile in a few real seconds.
            return min(full, 1.0)
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

    def _stop_is_real(self, stop, forward: bool) -> bool:
        """Whether this stop belongs on the run at all.

        One gate for the two places that read a leg's stops -- the placed
        road stops and the navigation cues -- so a stop can never be
        announced by one path after the other has ruled it out. A stop is
        real when it is curated, faces the direction of travel, and the rig
        being driven can physically get into it.
        """
        return (
            stop.curated
            and stop.applies_to_direction(forward)
            and stop.accessible_to(bobtail=self.bobtail)
        )

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
                if not self._stop_is_real(stop, from_city == leg.a):
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
                        parking_spaces=stop.parking_spaces,
                        vehicle_access=stop.vehicle_access,
                    )
                )
        return self._merge_shared_city_stops(out)

    def _merge_shared_city_stops(self, stops: list[RoadStop]) -> list[RoadStop]:
        """One entry per facility, not one per leg that lists it.

        Driving through a city picks its stops up twice, once from the leg
        arriving and once from the leg leaving, two miles apart -- the truck
        passes a single building, so announcing it twice sounds like a stutter
        and makes "which one did I plan?" meaningless. Keep the one reached
        first and let it borrow the twin's exit label if it has none.
        """
        merged: list[RoadStop] = []
        for stop in stops:
            twin = next(
                (
                    kept
                    for kept in reversed(merged)
                    if kept.name == stop.name
                    and abs(stop.at_mi - kept.at_mi) <= SHARED_CITY_STOP_MERGE_MI
                ),
                None,
            )
            if twin is None:
                merged.append(stop)
            elif not twin.exit_label and stop.exit_label:
                twin.exit_label = stop.exit_label
        return merged

    def _surface_distance_tail(self, miles: float) -> str:
        """Distance phrase for a surface segment: city blocks never say
        "0 miles"; longer streets read like the highway cues."""
        if miles < 0.2:
            return ""
        if self.imperial:
            if miles < 0.4:
                return "; a quarter mile"
            if miles < 0.75:
                return "; half a mile"
            return f"; {_spoken_distance(miles, 'mile')}"
        km = miles * 1.609344
        if km < 0.65:
            return "; 500 meters"
        if km < 1.2:
            return "; 1 kilometer"
        return f"; {_spoken_distance(km, 'kilometer')}"

    def _build_navigation_cues(self) -> list[NavigationCue]:
        cues: list[NavigationCue] = []
        for i, (start, leg) in enumerate(zip(self._leg_starts, self.route.legs, strict=True)):
            forward = self.route.cities[i] == leg.a
            toward_key = self.route.cities[i + 1]
            toward = get_world().spoken_city(toward_key)
            if self._is_facility_approach_route():
                # Tier-1 surface segments carry their baked maneuver; speak
                # it verbatim with the segment distance. Legs without one
                # keep the generic phrasing. Lookahead text lowercases only
                # the verb, never the street name.
                if i == 0:
                    text = (leg.local_cue or f"Start on {leg.highway}.").rstrip(".")
                    cues.append(
                        NavigationCue(
                            "local:start",
                            "local_turn",
                            start + 0.05,
                            text[:1].lower() + text[1:],
                            f"{text}{self._surface_distance_tail(leg.miles)}.",
                            direction=_cue_direction(text) or "ahead",
                        )
                    )
                elif self.route.legs[i - 1].highway != leg.highway:
                    text = (leg.local_cue or f"Turn onto {leg.highway}.").rstrip(".")
                    cues.append(
                        NavigationCue(
                            f"local:turn:{i}",
                            "local_turn",
                            start,
                            text[:1].lower() + text[1:],
                            f"{text}{self._surface_distance_tail(leg.miles)}.",
                            direction=_cue_direction(text),
                        )
                    )
                continue
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
            for restriction in leg.restrictions:
                offset = _stop_offset_for_direction(restriction.at_mi, leg.miles, forward)
                cues.append(
                    NavigationCue(
                        f"restriction:{i}:{restriction.at_mi}:{restriction.kind}",
                        "restriction",
                        start + offset,
                        restriction.spoken_ahead,
                        restriction.spoken_near,
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
                if not self._stop_is_real(stop, forward):
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
        cues.sort(key=lambda cue: cue.at_mi)
        return cues

    def _place_landmarks(self) -> list[RoadsideCallout]:
        """Schedule the baked roadside landmarks along this route.

        Direction-resolved to trip miles and thinned to the minimum spacing so
        a river cluster (three crossings in a mile is real geography) speaks
        once instead of stacking. City-street approaches stay quiet.

        Villages are baked wide and displayed tight: only the ones the route
        actually runs through or skirts are scheduled here (see
        ``VILLAGE_PASS_OFF_MI``), and they are thinned among themselves first
        so a dense corridor names a few places instead of chanting every one.
        The rest stay in the map for orientation answers rather than being
        announced as places you arrived at."""
        if self._is_facility_approach_route():
            return []
        callouts: list[RoadsideCallout] = []
        villages: list[tuple[float, float, RoadsideCallout]] = []
        for i, (start, leg) in enumerate(zip(self._leg_starts, self.route.legs, strict=True)):
            forward = self.route.cities[i] == leg.a
            for landmark in leg.landmarks:
                offset = _stop_offset_for_direction(landmark.at_mi, leg.miles, forward)
                callout = RoadsideCallout(
                    f"landmark:{i}:{landmark.at_mi}:{landmark.name}",
                    start + offset,
                    landmark.category,
                    f"{landmark.spoken}.",
                )
                if landmark.category == "village":
                    if landmark.off_mi > VILLAGE_PASS_OFF_MI:
                        continue
                    if self._village_explains_drop(callout.at_mi):
                        callout = replace(callout, explains_limit=True)
                    villages.append((callout.at_mi, landmark.off_mi, callout))
                    continue
                callouts.append(callout)
        # Town names are placed first and scenery fills the gaps around them. A
        # forest boundary and a village can land on the same mile (Tonto
        # National Forest and Pine, Arizona both sit at mile 41.9), and the name
        # of the town is the cue that orients the driver and explains the speed
        # limit about to drop -- ambient colour should yield to it, not win by
        # being first in the list.
        spaced = self._thin_villages(villages)
        for callout in sorted(callouts, key=lambda c: c.at_mi):
            if any(abs(callout.at_mi - kept.at_mi) < LANDMARK_MIN_SPACING_MI for kept in spaced):
                continue
            spaced.append(callout)
            spaced.sort(key=lambda c: c.at_mi)
        return spaced

    @staticmethod
    def _thin_villages(villages) -> list[RoadsideCallout]:
        """Keep one village per spacing window, nearest the road winning.

        Ordering by distance-off-route rather than by mile is what makes the
        choice honest: in a cluster of five, the one the highway actually runs
        through is the one a driver would use to place themselves, and it beats
        whichever happened to come first.

        A village that explains a limit change is never thinned away: its name
        is the reason the feature exists (Strawberry and Pine sit 2.7 miles
        apart, inside one spacing window, and both own a 35), so limit
        explainers are seated first and spacing applies to the rest."""
        chosen: list[tuple[float, RoadsideCallout]] = []
        for at_mi, _off_mi, callout in sorted(villages, key=lambda v: (v[1], v[0])):
            if callout.explains_limit:
                chosen.append((at_mi, callout))
        for at_mi, _off_mi, callout in sorted(villages, key=lambda v: (v[1], v[0])):
            if callout.explains_limit:
                continue
            if any(abs(at_mi - taken) < VILLAGE_MIN_SPACING_MI for taken, _ in chosen):
                continue
            chosen.append((at_mi, callout))
        return [callout for _, callout in sorted(chosen, key=lambda c: c[0])]

    def _village_explains_drop(self, at_mi: float) -> bool:
        """Whether a town-scale limit takes effect just past this callout.

        Probes the baked corridor limit only -- random work zones must not
        promote a village to limit-explainer on one trip and not the next.
        Mirrors the bake rule that placed paired callouts shortly before
        their zone starts."""
        here = self._corridor_limit_at(at_mi)
        mi = at_mi + LIMIT_SCAN_STRIDE_MI
        end = min(at_mi + VILLAGE_PAIR_WINDOW_MI, self.total_miles)
        while mi <= end:
            there = self._corridor_limit_at(mi)
            if there < here and there <= VILLAGE_PAIR_MAX_LIMIT_MPH:
                return True
            mi += LIMIT_SCAN_STRIDE_MI
        return False

    def _place_billboards(self) -> list[RoadsideCallout]:
        """Schedule parody billboards along the highway, seeded per trip.

        Corridor-keyed signs (the real roadside culture of that highway) are
        preferred where the route has them; the generic Americana pool fills
        the rest. Deterministic for a seeded trip, and each sign text appears
        at most once per trip -- repetition kills the joke."""
        from ..data.billboards import corridor_billboards, random_billboard

        if self._is_facility_approach_route():
            return []
        rng = random.Random(None if self._seed is None else self._seed ^ 0xB111B0A2)
        callouts: list[RoadsideCallout] = []
        used: set[str] = set()
        at = BILLBOARD_LEAD_IN_MI + rng.uniform(0.0, BILLBOARD_MIN_GAP_MI)
        while at < self.total_miles - 5.0:
            leg_i, _ = self._leg_at_mile(at)
            pool = corridor_billboards(self.route.legs[leg_i].highway)
            fresh_corridor = [text for text in pool if text not in used]
            if fresh_corridor and rng.random() < 0.5:
                text = rng.choice(fresh_corridor)
            else:
                text = random_billboard(rng)
                for _ in range(6):
                    if text not in used:
                        break
                    text = random_billboard(rng)
            if text not in used:
                used.add(text)
                callouts.append(
                    RoadsideCallout(f"billboard:{at:.1f}", at, "billboard", f"Billboard: {text}")
                )
            at += rng.uniform(BILLBOARD_MIN_GAP_MI, BILLBOARD_MAX_GAP_MI)
        return callouts

    # -- curves -----------------------------------------------------------------

    def _place_curves(self) -> list[RouteCurve]:
        """Every baked curve on the route in trip-mile coordinates.

        ``route_curves`` resolves the per-leg (A->B frame) records into the
        trip's position coordinate, mirroring reversed legs. Connector
        ramps are kept in the list for curve physics but filtered from the
        spoken layers -- ramps carry their own speech.
        """
        if self._is_facility_approach_route():
            return []
        return list(route_curves(self.route, self.route.cities, mainline_only=False))

    def curve_at(self, mile: float) -> RouteCurve | None:
        """The curve whose footprint contains this milepost, or None.

        After direction resolution, some baked curves may have their start_mi
        slightly past their end_mi on the trip coordinate frame (a curve that
        was oriented backward in the leg data). Check both orderings.
        """
        for cr in self.curves:
            lo, hi = min(cr.start_mi, cr.end_mi), max(cr.start_mi, cr.end_mi)
            if lo <= mile <= hi:
                return cr
        return None

    def _next_curve_approach(self) -> RouteCurve | None:
        """The next curve ahead that deserves a spoken approach warning.

        Connector ramps use their own cues. Mainline bends stay silent when
        the truck is already slow enough, and speak only once they enter the
        reaction-plus-comfortable-braking window.
        """
        speed = self.truck.speed_mph
        for cr in self.curves:
            ahead = cr.start_mi - self.position_mi
            if ahead <= 0:
                continue
            if ahead > PACENOTE_MAX_LEAD_MI:
                break
            if cr.connector:
                continue
            margin = PACENOTE_GENTLE_MARGIN_MPH if cr.severity == "gentle" else PACENOTE_MARGIN_MPH
            if speed <= cr.advisory_mph + margin:
                continue
            if ahead > self._curve_pacenote_lead_mi(speed, cr.advisory_mph):
                continue
            return cr
        return None

    @staticmethod
    def _curve_pacenote_lead_mi(speed_mph: float, advisory_mph: float) -> float:
        over = max(0.0, speed_mph - advisory_mph)
        react_mi = speed_mph * PACENOTE_REACTION_S / 3600.0
        brake_s = over / PACENOTE_BRAKE_MPH_PER_S
        brake_mi = (speed_mph + advisory_mph) / 2.0 * brake_s / 3600.0
        floor_mi = max(PACENOTE_MIN_LEAD_MI, speed_mph * PACENOTE_LEAD_FLOOR_S / 3600.0)
        return min(PACENOTE_MAX_LEAD_MI, max(floor_mi, react_mi + brake_mi))

    def _check_curves(self) -> None:
        """Emit a CURVE event when approaching a meaningful curve."""
        if self._is_facility_approach_route():
            return
        cr = self._next_curve_approach()
        if cr is None:
            return
        ahead = cr.start_mi - self.position_mi
        key = f"curve:{cr.start_mi:.3f}:{cr.direction}"
        if key in self._announced_curves:
            return
        self._announced_curves.add(key)
        # The immediate follower rides this call's "then ..." tail; marking
        # it announced here is what makes the tail a replacement instead of
        # a preview of a second full call three seconds later.
        linked = next(
            (
                c
                for c in self.curves
                if not c.connector
                and c.start_mi > cr.end_mi
                and c.start_mi <= cr.end_mi + PACENOTE_LINK_GAP_MI
            ),
            None,
        )
        if linked is not None:
            self._announced_curves.add(f"curve:{linked.start_mi:.3f}:{linked.direction}")
        # Build pacenote: "sharp curve left, half mile, advisory 35"
        direction = "left" if cr.direction == "L" else "right"
        prefix = "sharp " if cr.severity in ("hairpin", "sharp") else ""
        distance = self._distance_text(ahead)
        self._emit(
            TripEventKind.CURVE,
            f"{prefix}curve {direction}, {distance}, advisory {cr.advisory_mph:.0f}.",
            curve=cr,
            advisory_mph=cr.advisory_mph,
            ahead_mi=ahead,
        )

    def _check_roadside_callouts(self) -> None:
        self._check_callout_list(self.landmarks, self._announced_landmarks, TripEventKind.LANDMARK)
        self._check_callout_list(
            self.billboards, self._announced_billboards, TripEventKind.BILLBOARD
        )

    def _check_callout_list(self, callouts, announced: set[str], kind) -> None:
        for callout in callouts:
            if callout.key in announced:
                continue
            behind = self.position_mi - callout.at_mi
            if behind < 0:
                break  # sorted by mile; nothing further along is due yet
            announced.add(callout.key)
            # A callout overshot by more than a mile (a resumed save, a menu
            # jump) is stale scenery; note it silently rather than narrate
            # the past.
            if behind <= 1.0:
                self._emit(
                    kind,
                    callout.spoken,
                    category=callout.category,
                    explains_limit=callout.explains_limit,
                )

    def _place_zones(self) -> list[Zone]:
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
                zones.append(Zone(at, end, 45, "construction", closed_lane=closed))
                # Claim the whole signed footprint, taper included, so the
                # next draw cannot land a second work zone inside this one.
                spans.append((taper_start, end))
        # Real construction zones from state 511 APIs: when available, these
        # replace simulated zones on overlapping stretches so the player hears
        # real work zone locations instead of procedurally generated ones.
        real_construction = self._place_real_construction_zones()
        if real_construction:
            # Remove any simulated zones that overlap with real construction
            real_spans = [
                (z.start_mi, z.end_mi) for z in real_construction if z.reason == "construction"
            ]
            filtered: list[Zone] = []
            for z in zones:
                if z.reason not in ("construction", "construction merge"):
                    filtered.append(z)
                    continue
                overlaps = any(
                    z.start_mi < r_end + ZONE_MIN_GAP_MI and z.end_mi > r_start - ZONE_MIN_GAP_MI
                    for r_start, r_end in real_spans
                )
                if not overlaps:
                    filtered.append(z)
            zones = filtered
            zones.extend(real_construction)
        # Congestion zones are always added regardless of construction data.
        zones.extend(self._place_congestion_zones())
        zones.extend(self._facility_speed_zones())
        zones.sort(key=lambda z: z.start_mi)
        return zones

    def _route_aadt_at(self, mile: float) -> tuple[float, int]:
        """(two-way AADT, per-direction lanes) at a route mile: the baked HPMS
        profile where the leg has one, else the class/metro heuristic."""
        leg_i, leg_start = self._leg_at_mile(mile)
        leg = self.route.legs[leg_i]
        forward = self.route.cities[leg_i] == leg.a
        offset = mile - leg_start
        leg_offset = offset if forward else leg.miles - offset
        baked = leg_aadt_at(leg, leg_offset)
        if baked is not None:
            return baked
        near = self._near_city(mile)
        # Urban interstates run three or more lanes per direction, so the
        # metro heuristic rarely jams on its own -- real HPMS profiles are
        # what put a specific overloaded stretch over the line.
        lanes = 3 if near and _highway_class(leg.highway) == "interstate" else leg_lane_count(leg)
        return heuristic_aadt(leg.highway, near), lanes

    def _place_congestion_zones(self) -> list[Zone]:
        """Stretches where peak-hour demand approaches capacity.

        The zones are fixed in space; whether each one is *active*, and how
        slow it runs, is recomputed from the clock as the trip progresses
        (see ``_zone_is_active``). A stretch that jams at 5 PM is open road
        at midnight."""
        total = self.route.miles
        if self._is_facility_approach_route() or total < 10.0:
            return []
        peak_share = max(HOURLY_SHARE_WEEKDAY)
        prone: list[Zone] = []
        run_start: float | None = None
        run_samples: list[tuple[float, int]] = []

        def flush(end_mile: float) -> None:
            nonlocal run_start, run_samples
            if run_start is not None and end_mile - run_start >= CONGESTION_MIN_ZONE_MI:
                aadts = sorted(sample[0] for sample in run_samples)
                prone.append(
                    Zone(
                        run_start,
                        end_mile,
                        50.0,  # placeholder; refreshed from the clock when active
                        "heavy traffic",
                        aadt=aadts[len(aadts) // 2],
                        lanes=min(sample[1] for sample in run_samples),
                    )
                )
            run_start, run_samples = None, []

        mile = 0.0
        while mile <= total:
            aadt, lanes = self._route_aadt_at(mile)
            peak_ratio = aadt * peak_share * DIRECTIONAL_SPLIT / (max(1, lanes) * LANE_CAPACITY_VPH)
            if peak_ratio >= CONGESTION_MIN_RATIO:
                if run_start is None:
                    run_start = mile
                run_samples.append((aadt, lanes))
            else:
                flush(mile)
            mile += CONGESTION_SAMPLE_MI
        flush(min(mile, total))

        merged: list[Zone] = []
        for zone in prone:
            if merged and zone.start_mi - merged[-1].end_mi <= CONGESTION_JOIN_GAP_MI:
                prev = merged[-1]
                merged[-1] = Zone(
                    prev.start_mi,
                    zone.end_mi,
                    50.0,
                    "heavy traffic",
                    aadt=max(prev.aadt or 0.0, zone.aadt or 0.0),
                    lanes=min(prev.lanes, zone.lanes),
                )
            else:
                merged.append(zone)
        return merged

    def _current_career_hours(self) -> float | None:
        if self.career_hours is None:
            return None
        return self.career_hours + self.game_minutes / 60.0

    def _is_weekend_now(self) -> bool:
        hours = self._current_career_hours()
        return False if hours is None else is_weekend(hours)

    def _zone_is_active(self, zone: Zone) -> bool:
        """Whether a zone applies right now. Fixed zones always do; congestion
        zones follow the clock, and an active one gets its effective traffic
        speed refreshed here so announcements and limits stay current."""
        if zone.aadt is None:
            return True
        ratio = congestion_ratio(zone.aadt, self.current_hour, zone.lanes, self._is_weekend_now())
        limit = congestion_limit_mph(ratio, self._corridor_limit_at(zone.start_mi))
        if limit is None:
            return False
        zone.limit_mph = limit
        return True

    def _facility_speed_zones(self) -> list[Zone]:
        total = self.route.miles
        if total <= 0:
            return []
        gate_start = max(0.0, total - FACILITY_GATE_ZONE_MI)
        if self._is_facility_approach_route():
            # Tier-1 surface routes zone each street at its own baked speed
            # (25 named, 15 unnamed service ways); the blanket access-road
            # limit remains the fallback for single-leg approaches.
            if any(leg.local_speed_mph > 0 for leg in self.route.legs):
                zones: list[Zone] = []
                for leg_start, leg in zip(self._leg_starts, self.route.legs, strict=True):
                    speed = leg.local_speed_mph or FACILITY_ACCESS_LIMIT_MPH
                    if zones and zones[-1].limit_mph == speed:
                        # Same street speed continues: one zone, one callout.
                        zones[-1] = Zone(
                            zones[-1].start_mi,
                            leg_start + leg.miles,
                            speed,
                            "facility access road",
                        )
                    else:
                        zones.append(
                            Zone(leg_start, leg_start + leg.miles, speed, "facility access road")
                        )
                zones.append(Zone(gate_start, total, FACILITY_GATE_LIMIT_MPH, "facility gate"))
                return zones
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

    def _place_chain_law_areas(self) -> list[tuple[float, float]]:
        """Stretches under a winter chain law: sustained steep grade, fixed in
        space at trip build. Whether the law is *active* follows the live
        weather (``chain_law_level``), so the same pass is open road in July
        and a Level 2 control in an ice storm."""
        if self._is_facility_approach_route():
            return []
        total = self.route.miles
        areas: list[tuple[float, float]] = []
        run_start: float | None = None
        mile = 0.0
        while mile <= total:
            steep = abs(self.grade_at(mile)) >= CHAIN_LAW_MIN_GRADE
            if steep and run_start is None:
                run_start = mile
            elif not steep and run_start is not None:
                if mile - run_start >= CHAIN_LAW_MIN_RUN_MI:
                    areas.append((max(0.0, run_start - CHAIN_LAW_LEAD_MI), mile))
                run_start = None
            mile += CHAIN_LAW_SAMPLE_MI
        if run_start is not None and total - run_start >= CHAIN_LAW_MIN_RUN_MI:
            areas.append((max(0.0, run_start - CHAIN_LAW_LEAD_MI), total))
        merged: list[tuple[float, float]] = []
        for area in areas:
            if merged and area[0] - merged[-1][1] <= CHAIN_LAW_JOIN_GAP_MI:
                merged[-1] = (merged[-1][0], area[1])
            else:
                merged.append(area)
        return merged

    def chain_law_level(self) -> int:
        """0 = no law, 1 = winter-rated tires or chains, 2 = chains required.
        The tiers follow the real shape of Colorado's commercial levels."""
        surface = self.weather.effects.surface
        if surface == "ice":
            return 2
        if surface == "snow":
            return 1
        return 0

    def chain_law_area_at(self, mile: float) -> int | None:
        """Index of the chain-law area containing this milepost, or None."""
        for i, (start, end) in enumerate(self.chain_law_areas):
            if start <= mile <= end:
                return i
        return None

    def _check_chain_law(self) -> None:
        level = self.chain_law_level()
        if level == 0 or not self.chain_law_areas:
            return
        lookahead = max(self._zone_warning_lookahead_mi(), 1.0)
        for i, (start, end) in enumerate(self.chain_law_areas):
            key = f"chain-law:{i}:{level}"
            if key in self._announced_chain_law:
                continue
            ahead = start - self.position_mi
            inside = start <= self.position_mi <= end
            if not inside and not 0 < ahead <= lookahead:
                continue
            self._announced_chain_law.add(key)
            if level >= 2:
                rule = "Level 2: chains required on all commercial vehicles"
            else:
                rule = "Level 1: winter-rated tires or chains required on commercial vehicles"
            if inside:
                where = "on this grade"
                pullout = ""
            else:
                where = "on the grade ahead"
                pullout = " Chain-up area on the right shoulder."
            self._emit(
                TripEventKind.GPS_CUE,
                f"Flashing sign: chain law in effect {where}. {rule}.{pullout}",
                chain_law=level,
                chain_law_area=i,
            )

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

    def truck_limit_at(self, mile: float) -> tuple[bool, str | None]:
        """Whether a truck-specific limit is in force here, and the state to
        credit for it.

        A zone answers first: inside construction the cone is the reason the
        number dropped, not the state line, and saying otherwise would explain
        the wrong thing."""
        if self._active_zone_at(mile) is not None:
            return False, None
        leg_i, leg_start = self._leg_at_mile(mile)
        leg = self.route.legs[leg_i]
        forward = self.route.cities[leg_i] == leg.a
        route_offset = mile - leg_start
        leg_offset = route_offset if forward else leg.miles - route_offset
        return truck_limit_at(leg, leg_offset)

    def _region_at(self, mile: float) -> str:
        leg_i, _ = self._leg_at_mile(mile)
        city = self.route.cities[min(leg_i + 1, len(self.route.cities) - 1)]
        return get_world().cities[city].region

    def _near_city(self, mile: float) -> bool:
        return any(abs(mile - mp) <= URBAN_RADIUS_MI for mp in self._city_mileposts)

    def _nearest_urban_city(self, mile: float) -> tuple[str, float] | None:
        """The nearest route city within the urban radius, with its milepost --
        the milepost tells callers whether the city is ahead or behind."""
        best, best_mp, best_d = None, 0.0, URBAN_RADIUS_MI
        for i, mp in enumerate(self._city_mileposts):
            d = abs(mile - mp)
            if d <= best_d and i < len(self.route.cities):
                best, best_mp, best_d = self.route.cities[i], mp, d
        return None if best is None else (best, best_mp)

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

    def curves_within(self, within_mi: float) -> list[RouteCurve]:
        """Mainline curves whose entry lies ahead within the window.

        Connector arcs stay out: the spoken layers (pacenotes, U, S, D)
        are this method's consumers, and ramps carry their own speech."""
        return [
            c
            for c in self.curves
            if not c.connector and 0 < c.start_mi - self.position_mi <= within_mi
        ]

    def next_zone_within(self, within_mi: float) -> Zone | None:
        ahead = [
            z
            for z in self.zones
            if 0 < z.start_mi - self.position_mi <= within_mi and self._zone_is_active(z)
        ]
        return min(ahead, key=lambda z: z.start_mi) if ahead else None

    @property
    def active_zone(self) -> Zone | None:
        """The reduced-limit zone the truck is currently inside, if any."""
        return self._active_zone_at(self.position_mi)

    def ramp_control_at(self, route_mile: float, tol_mi: float = 2.0) -> str:
        """Baked OSM ramp-terminal control at the interchange nearest a route
        mile: ``signal``/``stop``/``none``, or ``""`` when no interchange
        within ``tol_mi`` carries one (the caller then uses its heuristic)."""
        best = ""
        best_dist = tol_mi
        for i, (start, leg) in enumerate(zip(self._leg_starts, self.route.legs, strict=True)):
            forward = self.route.cities[i] == leg.a
            for ix in leg.interchanges:
                if not ix.ramp_control:
                    continue
                offset = _stop_offset_for_direction(ix.at_mi, leg.miles, forward)
                dist = abs(start + offset - route_mile)
                if dist <= best_dist:
                    best_dist = dist
                    best = ix.ramp_control
        return best

    def _active_zone_at(self, mile: float) -> Zone | None:
        active = [
            z for z in self.zones if z.start_mi <= mile <= z.end_mi and self._zone_is_active(z)
        ]
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

    @property
    def planned_stop(self) -> RoadStop | None:
        """The stop the player planned for, or None if the plan is stale."""
        key = self.planned_stop_key
        if key is None:
            return None
        return next((stop for stop in self.stops if stop.key == key), None)

    @property
    def planned_stop_label(self) -> str:
        """The planned stop's spoken name, even if the stop itself is gone."""
        key = self.planned_stop_key
        if key is None:
            return ""
        stop = self.planned_stop
        return stop.name if stop is not None else RoadStop.name_from_key(key)

    def resolve_stop_key(self, name: str) -> str | None:
        """The key of the first stop with this name at or ahead of the truck.

        Only for restoring a save written before plans carried a key; a bare
        name cannot say which of a route's four Love's Travel Stops was meant,
        so take the soonest one the driver could still reach.
        """
        ahead = [s for s in self.stops if s.name == name and s.at_mi >= self.position_mi]
        if ahead:
            return min(ahead, key=lambda s: s.at_mi).key
        return next((s.key for s in self.stops if s.name == name), None)

    def is_planned(self, stop: RoadStop) -> bool:
        return self.planned_stop_key is not None and stop.key == self.planned_stop_key

    def planned_prefix(self, stop: RoadStop) -> str:
        """'Planned stop, ' when this is the stop the player planned for."""
        return "Planned stop, " if self.is_planned(stop) else ""

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
        next_context = self.next_navigation_context(imperial)
        terrain_text = self._current_grade_text()
        if self._is_facility_approach_route() and self.destination_label:
            toward_text = self.destination_label
        else:
            toward = self.route.cities[self.current_leg_index + 1]
            world = get_world()
            toward_name = world.spoken_city(toward, qualified=False)
            toward_text = f"{toward_name}, {world.cities[toward].state}"
        return f"{dist}. On {leg.highway} toward {toward_text}. {terrain_text}. {next_context}"

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
            if self._is_facility_approach_route() and self.destination_label:
                return f"Destination {self.destination_label} ahead."
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
        if cue.kind == "restriction":
            return f"Posted restriction in {ahead_text}: {cue.text}."
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
                self._announced_stops.add(stop.key)
        for cue in self.navigation_cues:
            if cue.at_mi <= self.position_mi:
                self._announced_navigation.add(f"{cue.key}:advance")
                self._announced_navigation.add(f"{cue.key}:near")
        for callout in (*self.landmarks, *self.billboards):
            if callout.at_mi <= self.position_mi:
                if callout.category == "billboard":
                    self._announced_billboards.add(callout.key)
                else:
                    self._announced_landmarks.add(callout.key)
        # Only curves already passed are certainly history. A curve still
        # ahead may not have entered the speed-dependent call window before
        # the save, so leave it eligible after resume rather than suppressing
        # a safety cue the player never heard.
        for cr in self.curves:
            if cr.start_mi <= self.position_mi:
                self._announced_curves.add(f"curve:{cr.start_mi:.3f}:{cr.direction}")
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
            if self.weather.live:
                source = f"Live weather near {target.spoken_qualified}"
            elif self.weather.provider is not None:
                source = "Simulated fallback weather"
            else:
                source = "Weather"
            self._emit(
                TripEventKind.WEATHER_CHANGE,
                f"{source} changing: {self.weather.describe(self.imperial)}",
                weather=changed,
            )
        self.truck.grip = self.weather.effects.grip
        self.truck.water_mm = self.weather.effects.water_mm
        self.truck.surface = self.weather.effects.surface
        self.truck.drag_mult = self.weather.effects.drag_mult
        self.truck.grade = self.grade_at(self.position_mi)
        self.truck.fuel_burn_mult = scale

        moved_mi = self.truck.velocity_mps * dt * scale / 1609.344
        self.last_moved_mi = moved_mi
        if self.on_ramp:
            # Off the highway on the exit ramp: hand this movement to the ramp
            # (DrivingState._update_exit) rather than the highway odometer, and
            # pause highway events until the truck rejoins the road. Weather and
            # the game clock above still advance while the driver brakes to a stop.
            return self._events
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
        self._check_chain_law()
        self._check_speed_limit()
        self._check_limit_drop_ahead()
        # Navigation before stop notices: when both fire on the same tick --
        # departure is the big one, where the onramp merge cue and a nearby
        # travel plaza announce together -- the actionable instruction must
        # reach the event voice first.
        self._check_navigation_cues()
        self._check_npc_traffic_cues()
        self._check_traffic_pressures()
        self._check_real_traffic_events()
        self._check_curves()
        self._check_stops()
        self._check_roadside_callouts()
        self._check_tolls()
        self._check_cities()
        self._check_timezone()
        if moved_mi > 0.0:
            self._check_patrol_heads_up()
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
        if zone.reason == "heavy traffic" and zone.aadt is not None:
            return (
                f"In {self._distance_text(ahead)}, {self._congestion_phrase()} ahead. "
                f"Traffic slowing to {self._speed_value(zone.limit_mph)}."
            )
        return (
            f"In {self._distance_text(ahead)}, {zone.reason} ahead. "
            f"Speed limit {self._speed_value(zone.limit_mph)}."
        )

    def _congestion_phrase(self) -> str:
        """What to call a live jam: rush hour gets named when it is one."""
        hour = self.current_hour % 24.0
        in_rush = any(start <= hour < end for start, end in RUSH_HOUR_WINDOWS)
        if in_rush and not self._is_weekend_now():
            return "rush hour congestion"
        return "heavy traffic"

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
        if zone.reason == "heavy traffic" and zone.aadt is not None:
            return (
                f"{self._congestion_phrase().capitalize()}. Traffic slowing to "
                f"{self._speed_value(zone.limit_mph)}; hold your gap."
            )
        # Say you are *in* it, not that it is ahead: the advance warning used
        # "ahead" with the same limit, and identical wording here left the
        # driver hearing "speed limit 15" twice, miles apart, with no way to
        # tell which one had taken effect. Pairs with the "End of ... zone" exit.
        return f"Entering {zone.reason} zone. Speed limit {self._speed_value(zone.limit_mph)} now."

    def _check_zones(self) -> None:
        lookahead = self._zone_warning_lookahead_mi()
        for zone in self.zones:
            key = _zone_key(zone)
            ahead = zone.start_mi - self.position_mi
            if zone.reason == "construction merge":
                continue
            if not self._zone_is_active(zone):
                continue  # a quiet congestion stretch may still wake up later
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
                if zone.reason == "heavy traffic" and zone.aadt is not None:
                    # Fill the jam with slow metal: the existing lead-vehicle,
                    # ACC, and hazard machinery turn it into stop-and-go.
                    self.traffic_manager.inject_congestion(zone, position_mi=self.position_mi)
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
            near = self._nearest_urban_city(self.position_mi) if lowered else None
            where = ""
            if near is not None:
                city, city_mp = near
                # A drop while pulling AWAY from town is the road's doing, not
                # the town's -- "approaching Sedona" with Sedona in the mirror
                # reads as a wrong turn (owner-found live, 2026-07-20).
                direction = "approaching" if city_mp >= self.position_mi else "leaving"
                where = f" {direction} {get_world().spoken_city(city)}"
            # A short lower zone (a village main street) is a passing event,
            # not a new cruising speed: say how long it lasts so the player
            # is not left guessing when the road opens back up.
            span = ""
            if lowered:
                length = self._limit_zone_length(limit)
                if length is not None and length <= LIMIT_SHORT_ZONE_MI:
                    span = f" for {_spoken_short_miles(length, self.imperial)}"
            self._emit(
                TripEventKind.GPS_CUE,
                f"Speed limit {verb} {self._speed_value(limit)}{where}{span}.",
            )

    def _limit_zone_length(self, limit: float) -> float | None:
        """How far the just-entered corridor limit holds from the current
        position, or ``None`` when it outlasts the scan cap."""
        mi = self.position_mi
        end = min(self.total_miles, mi + LIMIT_SCAN_MAX_MI)
        while mi < end:
            mi = min(end, mi + LIMIT_SCAN_STRIDE_MI)
            if self._corridor_limit_at(mi) != limit:
                return mi - self.position_mi
        return None

    def _next_limit_drop(self) -> tuple[float, float] | None:
        """The next corridor limit change ahead, when it is a warn-worthy drop.

        Returns ``(boundary_mi, new_limit)`` for the FIRST change inside the
        pacenote window -- never warning across an intermediate change -- and
        only when the drop is big enough to need a braking plan. The boundary
        is refined to a fine stride so its dedup key stays stable no matter
        where inside a tick the scan starts."""
        current = self._corridor_limit_at(self.position_mi)
        prev = self.position_mi
        end = min(self.total_miles, self.position_mi + PACENOTE_MAX_LEAD_MI)
        while prev < end:
            mi = min(end, prev + LIMIT_SCAN_STRIDE_MI)
            limit = self._corridor_limit_at(mi)
            if limit != current:
                if current - limit < LIMIT_DROP_WARN_MIN_DELTA_MPH:
                    return None
                boundary = mi
                probe = prev
                while probe < mi:
                    probe += 0.01
                    if self._corridor_limit_at(probe) != current:
                        boundary = probe
                        break
                return round(boundary, 2), limit
            prev = mi
        return None

    def _check_limit_drop_ahead(self) -> None:
        """Warn before a big posted-limit drop, like a curve pacenote: far
        enough out to brake a loaded rig comfortably, silent when already
        slow enough that the sign is no event."""
        if self._active_zone is not None or self._is_facility_approach_route():
            return
        nxt = self._next_limit_drop()
        if nxt is None:
            return
        boundary_mi, limit = nxt
        key = boundary_mi
        if key in self._warned_limit_drops:
            return
        speed = self.truck.speed_mph
        if speed <= limit + PACENOTE_MARGIN_MPH:
            return
        ahead = boundary_mi - self.position_mi
        if ahead > self._curve_pacenote_lead_mi(speed, limit):
            return
        self._warned_limit_drops.add(key)
        self._emit(
            TripEventKind.GPS_CUE,
            f"Speed limit drops to {self._speed_value(limit)} in "
            f"{_spoken_short_miles(ahead, self.imperial)}.",
        )

    def _check_stops(self) -> None:
        if self.planned_stop_key is not None:
            planned = self.planned_stop
            if self._exit_in_progress == self.planned_stop_key:
                # Signaled and taking the exit (armed or on the ramp): the plan
                # is fulfilled quietly when the stop opens, or the too-fast miss
                # cancels it with its own line. Either way, don't warn here.
                pass
            elif planned is None or planned.at_mi < self.position_mi:
                # Past the exit marker with no exit in progress: the ramp is no
                # longer takeable, so the planned stop is genuinely missed.
                name = self.planned_stop_label
                self.planned_stop_key = None
                self._emit(
                    TripEventKind.GPS_CUE,
                    f"You drove past your planned stop, {name}. Plan cancelled.",
                )
        for stop in self.stops:
            ahead = stop.at_mi - self.position_mi
            if 0 < ahead <= STOP_AHEAD_LOOKAHEAD_MI and stop.key not in self._announced_stops:
                self._announced_stops.add(stop.key)
                exit_part = f" at {stop.exit_label}" if stop.exit_label else ""
                parts = [
                    f"{self.planned_prefix(stop)}{stop.spoken_name}{exit_part} "
                    f"in {self._distance_text(ahead)}."
                ]
                if stop.parking_text:
                    parts.append(f"{stop.parking_text}.")
                parts.append("Press X to signal for the exit.")
                self._emit(TripEventKind.STOP_AHEAD, " ".join(parts), stop=stop)

    def _check_navigation_cues(self) -> None:
        # One maneuver at a time on street chains: several block-scale
        # boundaries sit inside the generic lookahead, so a departure tick
        # would otherwise read the whole itinerary at once. Only the nearest
        # not-yet-passed local turn may speak each tick.
        next_turn_key = None
        next_turn_ahead = None
        for cue in self.navigation_cues:
            if cue.kind != "local_turn":
                continue
            ahead = cue.at_mi - self.position_mi
            if ahead >= -0.1 and (next_turn_ahead is None or ahead < next_turn_ahead):
                next_turn_key, next_turn_ahead = cue.key, ahead
        for cue in self.navigation_cues:
            ahead = cue.at_mi - self.position_mi
            if cue.kind == "interchange":
                continue
            if cue.kind == "local_turn" and cue.key != next_turn_key:
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
            # Street maneuvers use a block-scale lookahead; the highway-scale
            # default would put a whole surface chain "ahead" at departure.
            lookahead = LOCAL_TURN_LOOKAHEAD_MI if cue.kind == "local_turn" else 2.0
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
                if cue.kind == "checkpoint":
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
