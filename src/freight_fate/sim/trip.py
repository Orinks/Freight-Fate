# ruff: noqa: F403,F405
"""Trip simulation: progress along a route, grades, zones, stops, and events."""

from __future__ import annotations

import math
import random
from dataclasses import replace

from ..data.curves import RouteCurve, route_curves
from ..data.regions import classify_region
from ..data.world import Leg, Route, get_world, lane_word
from ..speech_text import SpokenMessage, stop_callout, terse_silent
from ..units import distance_unit, spoken_distance, spoken_gap, to_distance
from .enforcement_posts import (
    KIND_FIXED_SCALE,
    KIND_SCALE_APRON,
    EnforcementPost,
    EnforcementPostMixin,
)
from .hos import clock_text
from .road_event_pacing import RoadEventBreather
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
# A lane-count run shorter than this is collapsed into its neighbor, so a
# fleeting widen/narrow (data noise, a short passing lane) is not announced.
LANE_RUN_MIN_MI = 2.0

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

# A signalled exit gets the same real-time treatment as a hard bend, over the
# road the truck genuinely needs to reach ramp speed (``approach_shed_mi``),
# widened the way the pacenote window is so the clock is already real by the
# time anything has to start shedding for it.
EXIT_APPROACH_DECOMPRESS_SLACK = 1.5
# And pacing climbs back over this many real seconds afterwards rather than
# snapping from real time to full compression the instant the exit resolves.
EXIT_APPROACH_RELEASE_S = 3.0

# Speed-limit lookahead (the co-driver warns before a big posted drop, the
# same way she calls a curve): only drops of at least this size get a
# warning -- a 65-to-60 step needs no braking plan, a village 30 does.
LIMIT_DROP_WARN_MIN_DELTA_MPH = 10.0
# The "drops to X in ..." pacenote lead, sized in REAL seconds of
# hearing-and-braking time at the current pace rather than a fixed game-mile
# distance -- the same law _zone_warning_lookahead_mi and EXIT_WARNING_REAL_S
# apply. A fixed lead (the old curve-pacenote braking distance) shrank to a
# couple of real seconds under time compression: the drop landed before the
# call finished (owner's live playtest, 2026-08-12). Capped so a slow leg
# under heavy compression does not call a drop from absurdly far out.
LIMIT_WARNING_REAL_S = 18.0
LIMIT_WARNING_MAX_LEAD_MI = 5.0
# A newly entered lower limit that ends within this span has its length
# spoken ("for the next half a mile"), so a short village zone reads as a
# passing event, not a new cruising speed.
LIMIT_SHORT_ZONE_MI = 2.5
# Below this there is no warning to give: the zone is already underfoot and
# the number it names is not yet the one in force, so it contradicts the limit
# S answers with. The "Entering ... zone" line is the announcement for
# anything this close (owner playtest, 2026-08-17). The wording of everything
# above it is the ladder's job -- see Trip._ahead_text -- so this is only
# about whether a warning is worth giving, not about how it reads.
ZONE_WARNING_MIN_MI = 0.1
# A navigation lead closer than this is the near announcement's own
# moment: both would speak in one breath. Matches the +/-0.1 window the
# near cue fires in.
NAV_LEAD_MIN_MI = 0.1
LIMIT_SCAN_STRIDE_MI = 0.1
LIMIT_SCAN_MAX_MI = 3.0

# Why a drop is happening, for the arrival line only ("Speed limit reduced
# to X ...") -- never the advance "drops to X in ..." pacenote, which stays
# a plain distance call. A named city is the first and existing reason; when
# there is none, a road stop close ahead or a real downgrade close ahead can
# still honestly explain the number, checked in that order. Bare when
# neither applies -- a guessed reason is worse than none.
LIMIT_REASON_LOOKAHEAD_MI = 1.5
# The only RoadStop types this maps are the ones that actually cause a lower
# posting (weigh stations slow traffic for the scale approach); a rest area
# or fuel stop never lowers the limit, so they carry no entry here.
LIMIT_REASON_BY_STOP_TYPE = {
    "weigh_station": " for the weigh station ahead",
}
# A "real hill" by the same bar the grade advisory uses for a steep call
# (GRADE_WARN_PCT in states/driving_updates.py is 3.0%); this is checked
# against the average over a forward scan rather than a single sample, and
# set a little steeper since it is standing in for the road's whole reason.
LIMIT_DOWNGRADE_PCT = -3.5
LIMIT_DOWNGRADE_MIN_MI = 0.5


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


class Trip(TripRoadEventMixin, TripTrafficMixin, EnforcementPostMixin):
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
        destination_approach_mi: float | None = None,
    ) -> None:
        self.route = route
        self.truck = truck
        self.weather = weather
        self._weather_source_status = weather.source_status
        self._weather_location_refreshing = False
        self._weather_refresh_issue_announced = False
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
        # How much local approach road stands between the highway and this
        # run's gate, from the destination facility's own approach record.
        # None where the facility has no usable record, or where its street
        # chain is driven as a route of its own after this one -- the arrival
        # zones then size the approach from the synthetic exit instead.
        self.destination_approach_mi = destination_approach_mi
        self.position_mi = 0.0
        self.game_minutes = 0.0
        self.finished = False
        # The control the stop callout names for signalling an exit. The
        # driving layer overrides it to the device-correct hint, or to "" once
        # the player has demonstrated the exit signal enough times that the
        # instruction has retired (research doc R7). The literal default keeps
        # standalone Trip callers (tests, tools) speaking the keyboard key.
        self.exit_hint = "X"
        # Facilities named in full already this leg, so a repeat mention within
        # the leg speaks the proper name alone (research doc R6). Cleared on a
        # new leg here, and on resume-from-pause by the driving layer; a resume
        # from a save rebuilds the Trip, so it starts empty there too.
        self._facilities_named: set[str] = set()
        self._facility_leg = 0
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
        self.chain_law_areas = self._place_chain_law_areas()
        # Enforcement posts read the zones, the scales, the chain controls and
        # the city mileposts, so they are placed after all of them.
        self.posts = self._place_enforcement_posts()
        self.traffic_manager.add_enforcement_traffic(self.posts)
        # Curve data: baked real-world curve records per leg, resolved to trip
        # miles so the driving state can query active curves and approach them.
        self.curves = self._place_curves()
        # True while the player is on an exit ramp that ends in a light or a
        # stop sign; the driving state maintains it every frame. It pins the
        # clock to real time (see effective_time_scale).
        self.controlled_ramp = False
        # A police stop is in progress: the clock stops compressing until it
        # resolves, so the distance the stop is judged by is honest miles.
        self.pull_over_active = False
        # True from a street corner's approach call until the corner resolves;
        # the driving state maintains it. Same clock rule as the ramp: the
        # advisory has to be brakeable in real seconds, and at 40x it is not.
        self.controlled_turn = False
        # Road left to an exit the driver has signalled for, or None when no
        # exit is armed or the truck is already on the ramp. The driving state
        # reports it every frame; the clock is the only thing that reads it.
        self.exit_approach_mi: float | None = None
        self._exit_approach_release_s = 0.0
        self._announced_chain_law: set[str] = set()
        self._announced_curves: set[str] = set()
        self._announced_lane_changes: set[str] = set()
        self._lane_runs: list[list] | None = None  # lazily built, direction-aware
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
        # Whether the current _active_zone's ZONE_ENTER colour line has been
        # spoken. A gated entry (see _check_zones) leaves this False so the
        # next open window speaks for whichever zone is actually current --
        # a gated entry is held back, never dropped for good.
        self._zone_entry_spoken: bool = True
        self._announced_speed_limit: float | None = None
        self._warned_limit_drops: set[float] = set()
        # Posted-limit values already spoken for the CURRENT posting -- by the
        # advance "drops to X" pacenote, or by an assist's own "easing to X"
        # line -- so the plain arrival confirmation doesn't repeat the same
        # number a moment (or, under compression, an instant) later.
        self._limit_drop_preannounced: set[float] = set()
        # Real-seconds breathing gap for routine road talkers (posted-limit
        # arrivals here; traffic and zone chatter reuse it in later work) --
        # see road_event_pacing for why the clock stays but the narration
        # spaces out.
        self._event_breather = RoadEventBreather()
        self._announced_zone_warnings: set[str] = set()
        # Milepost of the zone the driver was last warned about. A new
        # warning waits until they have reached it, so a surface chain
        # carrying a zone per street cannot fire them all at once.
        self._pending_zone_warning: float | None = None
        self._announced_traffic_pressures: set[str] = set()
        self._announced_npc_traffic: set[str] = set()
        self._announced_real_traffic: set[str] = set()
        self._next_real_traffic_check_mi = 0.0
        self._construction_zone_grace_start: dict[str, float] = {}
        # CB heads-ups are rationed (see _check_enforcement_heads_up): the
        # spoken budget for a whole run is two lines, so this counts them.
        self._cb_calls_made = 0
        # Posts that have already entered the lead window. Separate from
        # EnforcementPost.announced, which is the accessibility gate (this
        # post made a sound, so it is allowed to observe you): a post can be
        # audible without having spent one of the run's two spoken lines.
        self._heads_up_seen: set[str] = set()
        self._hazard_check_mi = 5.0
        self._inspection_check_mi = 10.0
        self._conditions_check_mi = CONDITIONS_CHECK_MI
        self._traffic_warning_mi = 1.0
        self._announced_enforcement: set[str] = set()
        # Start the first route cell's live-weather fetch now rather than on
        # the first update tick: the drive-start speech overlaps the network
        # instead of the player holding "loading" into the drive, and after a
        # warmed city menu the observation is already cached station-side.
        # Opportunistic only: a route whose cities are not in the world (test
        # fixtures, tooling) cannot resolve a location yet -- the first update
        # tick repeats this authoritatively.
        try:
            weather_key, weather_lat, weather_lon = self._weather_location()
        except Exception:
            pass
        else:
            self.weather.set_city(weather_key, weather_lat, weather_lon)
            if self.weather.provider is not None:
                self.weather.provider.request(weather_key, weather_lat, weather_lon)

    @property
    def patrols(self) -> list[EnforcementPost]:
        """The enforcement posts on this route, under the older name.

        A post is a point, not a window, so ``start_mi``/``end_mi`` on one
        answer with the stretch it watches. Kept because the info key, the
        road-ahead readout and the traffic bubble all still ask for patrols.
        """
        return self.posts

    @patrols.setter
    def patrols(self, value: list[EnforcementPost]) -> None:
        self.posts = value

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
        if self.pull_over_active:
            # Lights behind you: the whole encounter runs on the real clock.
            # PULL_OVER_IGNORE_MI is 2 raw trip miles, but braking takes real
            # seconds and compression spent them at 40x -- a textbook stop
            # from 74 mph consumed 2.18 miles and tripped the felony line
            # before the truck had slowed to 50.
            return min(full, 1.0)
        if self.controlled_ramp or self.controlled_turn:
            # A ramp ending in a light or a sign plays out in real time
            # from the gore: the stop-sign warning must buy human reaction
            # seconds, not compressed ones. A hot entry used to burn the
            # whole half mile in a few real seconds. A street corner is the
            # same bargain -- "Advise 20" is only plannable if the miles to
            # the corner take real seconds to pass.
            return min(full, 1.0)
        if self._severe_curve_decompression():
            # Same law for a hard bend: the pacenote lead is sized in real
            # reaction-plus-braking seconds, but compression spent them in
            # a blink -- "Hairpin right, a quarter mile" did not finish
            # speaking before the braking point (owner, 2026-07-24). From
            # inside the warning window to the end of the curve, the clock
            # runs real.
            return min(full, 1.0)
        if self._armed_exit_decompression():
            # And for a signalled exit, which is the same bargain again: the
            # shed to ramp speed is sized in real reaction-plus-braking
            # seconds. Compressed, the road ran out before the truck could
            # use it, so automatic control started easing nine miles from a
            # truck stop just to be sure of the gore (Shane, 2026-08-15).
            # Real seconds over the approach mean the glide only has to bite
            # where a driver would really lift.
            return min(full, 1.0)
        if self._exit_approach_release_s > 0.0:
            # Coming back up to pace after an approach, not snapping to it:
            # the truck is accelerating away from an exit it took, cancelled,
            # or missed, and the clock climbs with it.
            real = min(full, 1.0)
            eased = 1.0 - self._exit_approach_release_s / EXIT_APPROACH_RELEASE_S
            return real + (full - real) * eased
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
        return _spoken_distance(
            to_distance(miles, self.imperial),
            distance_unit(self.imperial, plural=False),
        )

    def _ahead_text(self, miles: float) -> str:
        """How far to something still in front of the truck, never "0 miles".

        ``_distance_text`` rounds to whole units, so everything inside half a
        mile announced itself as zero -- "In 0 miles, facility access road
        ahead" while the road was already under the wheels (owner playtest,
        2026-08-17, and the same rounding the R key was fixed for in July).
        Quarter-mile steps, or hundred-metre steps in metric, which is what
        the limit calls already speak.
        """
        return _spoken_short_miles(miles, self.imperial)

    def _gap_text(self, miles: float) -> str:
        return spoken_gap(miles, self.imperial)

    def _speed_value(self, mph: float) -> str:
        return f"{to_distance(mph, self.imperial):.0f}"

    def _speed_text(self, mph: float) -> str:
        units = "miles per hour" if self.imperial else "kilometers per hour"
        return f"{self._speed_value(mph)} {units}"

    def _compute_leg_starts(self) -> list[float]:
        starts, acc = [], 0.0
        for leg in self.route.legs:
            starts.append(acc)
            acc += leg.miles
        return starts

    @staticmethod
    def _leg_latlon_at(leg, at_mi: float) -> tuple[float, float]:
        """Linear lat/lon along a leg's route points at an A-to-B offset."""
        pts = leg.route_points
        if not pts:
            return 0.0, 0.0
        prev = pts[0]
        for pt in pts:
            if pt.at_mi >= at_mi:
                span = pt.at_mi - prev.at_mi
                fraction = (at_mi - prev.at_mi) / span if span > 0 else 0.0
                return (
                    prev.lat + (pt.lat - prev.lat) * fraction,
                    prev.lon + (pt.lon - prev.lon) * fraction,
                )
            prev = pt
        return prev.lat, prev.lon

    def latlon_at(self, mile: float | None = None) -> tuple[float, float]:
        """Interpolated road coordinate at a trip position."""
        sample_mile = self.position_mi if mile is None else mile
        leg_i, leg_start = self._leg_at_mile(sample_mile)
        leg = self.route.legs[leg_i]
        route_offset = max(0.0, min(leg.miles, sample_mile - leg_start))
        forward = self.route.cities[leg_i] == leg.a
        native_offset = route_offset if forward else leg.miles - route_offset
        if len(leg.route_points) >= 2:
            return self._leg_latlon_at(leg, native_offset)
        world = get_world()
        # A leg with no baked geometry falls back to interpolating between its
        # two city coordinates -- but a synthetic route (a test fixture, a
        # hand-built leg) names cities the world has never heard of. Answering
        # "no coordinate" is right there: every caller already guards on a
        # falsy pair, and a coordinate lookup must not be able to take the
        # whole trip down. Enforcement-post placement made this reachable by
        # asking for the region of every mile it considers.
        try:
            start = world.cities[self.route.cities[leg_i]]
            end = world.cities[self.route.cities[leg_i + 1]]
        except (KeyError, IndexError):
            return (0.0, 0.0)
        fraction = route_offset / leg.miles if leg.miles > 0 else 0.0
        return (
            start.lat + (end.lat - start.lat) * fraction,
            start.lon + (end.lon - start.lon) * fraction,
        )

    def _weather_location(self) -> tuple[str, float, float]:
        """Stable 20-mile route cell, cut short at a state line.

        The cell alone was too coarse across a border. A state line almost
        never falls on a 20-mile mark, so the previous state's conditions
        carried up to 20 miles past it -- at highway speed, a quarter hour of
        rain that had already stopped in the real world (Brandon, tester
        report 2026-08-18).

        The state is part of the key, so crossing a line changes it at the
        line and asks the provider afresh. And when the crossing happened
        INSIDE the current cell, the cell's own start coordinate is still in
        the state behind us, so the request would fetch the weather we are
        leaving; the truck's own position is used instead.

        The same fix the clock already had: state crossings are baked with
        exact mileposts, which is how the timezone change lands at the line
        rather than ten miles past it (owner, 2026-07-22).
        """
        leg_i, leg_start = self._leg_at_mile(self.position_mi)
        leg = self.route.legs[leg_i]
        route_offset = max(0.0, min(leg.miles, self.position_mi - leg_start))
        cell = int(route_offset // 20.0)
        sample_mile = min(leg_start + cell * 20.0, leg_start + leg.miles)
        state = self.state_at(self.position_mi)
        if state and self.state_at(sample_mile) != state:
            sample_mile = self.position_mi
        lat, lon = self.latlon_at(sample_mile)
        direction = f"{self.route.cities[leg_i]}:{self.route.cities[leg_i + 1]}"
        return f"route:{direction}:{cell}:{state}", lat, lon

    def _timezone_samples(self) -> list[tuple[float, TimeZone]]:
        """(trip mile, zone) along the route, from city and route-point geometry.

        City endpoints are sampled too, so a leg with no baked geometry still
        lands its clock change somewhere between two cities in different
        zones. State crossings are sampled AT their exact mileposts: route
        points can sit thirty miles apart on a desert interstate, and
        sampling only there put the Arizona-to-California clock change ten
        miles past the Colorado River (owner caught it at the wheel,
        2026-07-22). The border milepost the leg already carries pins the
        flip to the line the welcome sign announces.
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
            for crossing in leg.state_crossings:
                offset = _stop_offset_for_direction(crossing.at_mi, leg.miles, forward)
                lat, lon = self._leg_latlon_at(leg, crossing.at_mi)
                before = zone_for(lat, lon, crossing.from_state)
                after = zone_for(lat, lon, crossing.state)
                # Traversed backward, the truck meets the crossing from the
                # other side: the A-to-B "to" state is what it is leaving.
                if not forward:
                    before, after = after, before
                samples.append((max(0.0, start + offset - 0.05), before))
                samples.append((start + offset, after))
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
        their zone starts.

        A name also explains the number already under the wheels. Strawberry's
        callout sits two miles inside the 40 that Strawberry is the reason for,
        and the road opens back up to 50 just past the town -- so the drop is
        behind the name rather than ahead of it, and looking only forward left
        the town unexplained and, on the sparse tier, unspoken."""
        here = self._corridor_limit_at(at_mi)
        mi = at_mi + LIMIT_SCAN_STRIDE_MI
        end = min(at_mi + VILLAGE_PAIR_WINDOW_MI, self.total_miles)
        inside_town_limit = here <= VILLAGE_PAIR_MAX_LIMIT_MPH
        while mi <= end:
            there = self._corridor_limit_at(mi)
            if there < here and there <= VILLAGE_PAIR_MAX_LIMIT_MPH:
                return True  # the town's zone starts just ahead of its name
            if inside_town_limit and there > here:
                return True  # the name is inside the town's zone, which ends here
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

    def curve_ahead_mi(self, lead_mi: float) -> float | None:
        """Distance to the next mainline curve start inside ``lead_mi``, or
        None. Connector ramps have their own cues and never arm guidance."""
        for cr in self.curves:
            ahead = cr.start_mi - self.position_mi
            if ahead <= 0:
                continue
            if ahead > lead_mi:
                break
            if cr.connector:
                continue
            return ahead
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

    def _severe_curve_decompression(self) -> bool:
        """True while a warning-worthy bend is inside its reaction window.

        Demand-based, not severity-based: any curve the pacenote would
        speak for (same margin rules) gets real seconds to act on -- a
        40-advisory bend from 55 went 'half a mile' to 'too fast' in
        three real seconds under compression because the first cut only
        covered hairpin and sharp (owner, 2026-07-24). Uses the pacenote
        lead widened a little so the call itself lands in real time, and
        holds until the curve's end so the bend is DRIVEN in real time.
        """
        speed = self.truck.speed_mph
        for cr in self.curves:
            if cr.end_mi < self.position_mi:
                continue
            ahead = cr.start_mi - self.position_mi
            if ahead > PACENOTE_MAX_LEAD_MI:
                break
            if cr.connector:
                continue
            margin = PACENOTE_GENTLE_MARGIN_MPH if cr.severity == "gentle" else PACENOTE_MARGIN_MPH
            if speed <= cr.advisory_mph + margin:
                continue
            window = self._curve_pacenote_lead_mi(speed, cr.advisory_mph) * 1.5
            if ahead <= window:
                return True
        return False

    def _armed_exit_decompression(self) -> bool:
        """True while a signalled exit is inside the road the truck must shed.

        Shaped like ``_severe_curve_decompression``: from inside the window
        the approach needs until the exit is behind the truck, the clock runs
        real. The window is the shed budget the ramp cap and the arrival zones
        already share -- reaction seconds plus a comfortable rate down to the
        speed the gore accepts -- so it widens on its own with road speed. A
        truck doing 80 starts its approach earlier than one doing 60, which is
        the tester's own caveat, and nothing here is a fixed number of miles.
        """
        ahead = self.exit_approach_mi
        if ahead is None or ahead <= 0.0:
            return False
        speed = self.truck.speed_mph
        if speed <= RAMP_MAX_MPH:
            return False  # already slow enough for the gore: nothing to shed
        window = approach_shed_mi(speed, RAMP_MAX_MPH) * EXIT_APPROACH_DECOMPRESS_SLACK
        return ahead <= window

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
        distance = self._ahead_text(ahead)
        self._emit(
            TripEventKind.CURVE,
            f"{prefix}curve {direction}, {distance}, advisory {cr.advisory_mph:.0f}.",
            curve=cr,
            advisory_mph=cr.advisory_mph,
            ahead_mi=ahead,
        )

    def _build_lane_runs(self) -> list[list]:
        """Direction-aware lane runs across the whole route in travel order:
        ``[route_start_mi, route_end_mi, lanes_your_side, divided]``. Adjacent
        equal runs merge; runs shorter than ``LANE_RUN_MIN_MI`` are absorbed
        into the value before them so a brief widen/narrow is not announced."""
        runs: list[list] = []
        for i, leg in enumerate(self.route.legs):
            leg_start = self._leg_starts[i]
            forward = self.route.cities[i] == leg.a
            segs = list(leg.lane_segments if forward else reversed(leg.lane_segments))
            for seg in segs:
                if forward:
                    s, e = leg_start + seg.start_mi, leg_start + seg.end_mi
                else:
                    s, e = (
                        leg_start + (leg.miles - seg.end_mi),
                        leg_start + (leg.miles - seg.start_mi),
                    )
                runs.append([s, e, seg.your_side(forward), seg.divided])
        if not runs:
            return []
        runs.sort(key=lambda r: r[0])

        def _coalesce(rows: list[list]) -> list[list]:
            out: list[list] = []
            for r in rows:
                if out and r[2] == out[-1][2] and r[3] == out[-1][3] and r[0] - out[-1][1] <= 0.3:
                    out[-1][1] = r[1]
                else:
                    out.append([r[0], r[1], r[2], r[3]])
            return out

        merged = _coalesce(runs)
        # Absorb short runs into the previous value (a leading short run is kept,
        # since there is no earlier value to inherit), then re-merge.
        collapsed: list[list] = []
        for r in merged:
            if collapsed and (r[1] - r[0]) < LANE_RUN_MIN_MI:
                collapsed[-1][1] = r[1]
            else:
                collapsed.append(r)
        return _coalesce(collapsed)

    def _check_lane_changes(self) -> None:
        """Announce when the lane count in the travel direction changes, once
        per boundary. Divided-only changes (same count) stay quiet -- the count
        is the story a driver acts on."""
        if self._lane_runs is None:
            self._lane_runs = self._build_lane_runs()
            # Seed everything already behind the starting position so a resumed
            # trip does not re-announce a change it passed before the save.
            for run in self._lane_runs:
                if run[0] <= self.position_mi:
                    self._announced_lane_changes.add(f"lane:{run[0]:.2f}")
        for idx in range(1, len(self._lane_runs)):
            boundary = self._lane_runs[idx][0]
            key = f"lane:{boundary:.2f}"
            if key in self._announced_lane_changes:
                continue
            behind = self.position_mi - boundary
            if behind < 0:
                break  # sorted; nothing further along is due yet
            self._announced_lane_changes.add(key)
            prev_side = self._lane_runs[idx - 1][2]
            new_side = self._lane_runs[idx][2]
            if new_side == prev_side:
                continue
            if behind <= 1.0:  # not a stale, overshot boundary from a jump/resume
                self._emit(
                    TripEventKind.LANE,
                    self._lane_change_message(prev_side, new_side),
                    lanes=new_side,
                )

    @staticmethod
    def _lane_change_message(prev_side: int, new_side: int) -> str:
        if new_side > prev_side:
            return f"Road widens to {lane_word(new_side)} lanes your side."
        return f"Down to {lane_word(new_side)} lane{'s' if new_side != 1 else ''} your side."

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
                # A side, not a lane number: crews cone off the outside of the
                # road, and a side still names a real lane where the stretch
                # runs three wide -- an index of 1 would be the middle lane
                # there while every callout called it the left one.
                side = (
                    self._rng.choice(("right", "left"))
                    if self._rng.random() < CONSTRUCTION_CLOSURE_CHANCE
                    else None
                )
                taper_start = max(0.0, at - CONSTRUCTION_TAPER_MI)
                # Only cone off a lane where the driver has another one to
                # move into for the whole signed stretch. Elsewhere the work
                # still happens, with every lane open through it.
                if side is not None and not self._span_is_multilane(taper_start, end):
                    side = None
                zones.append(
                    Zone(
                        taper_start,
                        at,
                        CONSTRUCTION_TAPER_LIMIT_MPH,
                        "construction merge",
                        closed_side=side,
                    )
                )
                zones.append(Zone(at, end, 45, "construction", closed_side=side))
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
        # The gate zone is the yard entrance, and on a real chain that is its
        # LAST STREET -- not a fixed distance back from the end. A flat half
        # mile is longer than a quarter of all approach chains: the median is
        # 1.0 mile and 234 of 1,415 facilities run 0.5 or less, so on those
        # the "last half mile" swallowed the entire approach. Because
        # _active_zone_at takes the LOWEST limit among overlapping zones, that
        # blanket 15 then overrode every 25 street underneath it while the
        # per-leg zones went on announcing 25 -- the truck pinned at 15 and
        # told it was holding 25 (owner report, 2026-08-17; root cause found
        # 2026-08-18). Per-leg chains take the last leg below; the synthetic
        # fallback keeps a distance but can no longer exceed its own road.
        gate_start = max(0.0, total - min(FACILITY_GATE_ZONE_MI, total * FACILITY_GATE_MAX_SHARE))
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
                # The last street IS the gate approach. Never earlier than the
                # leg it belongs to, so it can never reach back over streets
                # the driver is still meant to be doing 25 on.
                last_leg_start = self._leg_starts[-1] if self._leg_starts else gate_start
                zones.append(
                    Zone(
                        max(gate_start, last_leg_start),
                        total,
                        FACILITY_GATE_LIMIT_MPH,
                        "facility gate",
                    )
                )
                return zones
            # Graduated fallback (owner design, 2026-07-24): a long
            # synthetic approach is an arterial before it is an access
            # road -- 45 out wide, 25 for the last stretch, 15 at the
            # gate. A blanket 25 for a 6-mile approach was a crawl no
            # real city posts. Short approaches stay all-access-road.
            zones = []
            access_start = max(0.0, total - FACILITY_ACCESS_TAIL_MI)
            if access_start > 0.5:
                zones.append(
                    Zone(0.0, access_start, FACILITY_ARTERIAL_LIMIT_MPH, "facility approach")
                )
                zones.append(
                    Zone(access_start, total, FACILITY_ACCESS_LIMIT_MPH, "facility access road")
                )
            else:
                zones.append(Zone(0.0, total, FACILITY_ACCESS_LIMIT_MPH, "facility access road"))
            zones.append(Zone(gate_start, total, FACILITY_GATE_LIMIT_MPH, "facility gate"))
            return zones
        # Everything else ends on the highway, comes off at the destination
        # exit, and finishes on the facility's own local road. Two bands, the
        # same two callouts this has always spoken:
        #
        #   * the local approach, capped at the speed the ramp can be taken at
        #     and no lower, running back from the gate for as much road as the
        #     facility's own approach record says it really has;
        #   * the gate itself, unchanged.
        #
        # Ahead of the local road the corridor's own limit stands, right up to
        # the point a driver has to start shedding for the ramp -- that point
        # comes out of the deceleration, not out of a round number. The flat
        # three-mile 35 this replaces landed as a step change a mile or two
        # before the exit and read to testers as the truck giving up on the
        # freeway (Shane, 2026-08-15).
        local_mi = self.destination_approach_mi or DESTINATION_LOCAL_APPROACH_MI
        local_mi = min(max(local_mi, FACILITY_GATE_ZONE_MI), DESTINATION_APPROACH_TRUSTED_MAX_MI)
        local_start = max(0.0, total - local_mi)
        entry_mph = self._corridor_limit_at(max(0.0, local_start - 0.05))
        approach_start = max(
            0.0, local_start - approach_shed_mi(entry_mph, DESTINATION_APPROACH_LIMIT_MPH)
        )
        return [
            Zone(approach_start, total, DESTINATION_APPROACH_LIMIT_MPH, "destination approach"),
            Zone(gate_start, total, FACILITY_GATE_LIMIT_MPH, "facility gate"),
        ]

    def _is_facility_approach_route(self) -> bool:
        """A street chain to a gate, never a same-city highway dispatch.

        Endpoints alone lied: a yard-to-cross-dock job inside one city
        rides the interstate loop and still starts and ends at the same
        city key -- which blanketed 17 miles of I-80 in the 25 mph
        facility-access zone and silenced its curve and limit warnings
        (owner, 2026-07-24, Fernley). A real approach chain is BUILT
        from streets (baked local speeds or cues) or is gate-shot short.
        """
        if len(self.route.cities) < 2 or self.route.cities[0] != self.route.cities[-1]:
            return False
        if any(leg.local_speed_mph > 0 or leg.local_cue for leg in self.route.legs):
            return True
        # The synthetic single-leg approach carries no baked route geometry;
        # a real same-city HIGHWAY dispatch always does (route_points come
        # from the corridor bake). That geometry, not mileage, is what
        # separates a 6-mile synthetic dock approach from a 17-mile I-80
        # loop job.
        return all(len(leg.route_points) < 2 for leg in self.route.legs)

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

    def lanes_at(self, mile: float | None = None) -> tuple[int, bool] | None:
        """(lanes in the direction of travel, divided) at a route mile, or None
        where the lane bake found no tag -- honest absence, speak nothing."""
        sample_mile = self.position_mi if mile is None else mile
        leg_i, leg_start = self._leg_at_mile(sample_mile)
        leg = self.route.legs[leg_i]
        forward = self.route.cities[leg_i] == leg.a
        offset = max(0.0, min(leg.miles, sample_mile - leg_start))
        sample_offset = offset if forward else leg.miles - offset
        for seg in leg.lane_segments:
            if seg.start_mi <= sample_offset <= seg.end_mi:
                return seg.your_side(forward), seg.divided
        return None

    def lane_count_at(self, mile: float | None = None) -> int:
        """Lanes on our side at a route mile, from the best data available.

        The baked lane segments (real OSM counts) rule where they exist; else
        an undivided leg (carriageway-geometry flag) is one lane our side, and
        the HPMS leg count is the last word. This is the same answer the
        driving state steers by, so anything that reasons about how many lanes
        the driver has -- lane closures above all -- asks here.

        Capped at ``MAX_DRIVABLE_LANES``: the spoken vocabulary has three
        lane names, so a fourth lane is one the driver cannot be told apart
        from the third. The cap lives here rather than in the bakes so the
        recorded road stays true -- and deliberately NOT in ``leg_aadt_at``,
        whose lane count is traffic capacity rather than a lane anyone
        drives in.
        """
        baked = self.lanes_at(mile)
        if baked is not None:
            return max(1, min(MAX_DRIVABLE_LANES, baked[0]))
        leg_i, _ = self._leg_at_mile(self.position_mi if mile is None else mile)
        leg = self.route.legs[leg_i]
        if getattr(leg, "divided", None) is False:
            return 1
        return min(MAX_DRIVABLE_LANES, leg_lane_count(leg))

    def active_closure(self, mile: float | None = None) -> Zone | None:
        """The roadwork zone whose cones cover this mile, taper included.

        Not ``active_zone``: that answers with the SLOWEST zone at the mile,
        so a jam laid over the roadwork hid the closure from everything that
        asks which lane is shut -- the driver was still told the right lane
        was closed while the lane-change check believed nothing was. The work
        zone answers ahead of its own taper where the two overlap, because
        that is where the barrels are.
        """
        sample = self.position_mi if mile is None else mile
        covering = [
            z
            for z in self.zones
            if z.reason in CONSTRUCTION_ZONE_REASONS
            and z.closed_side is not None
            and z.start_mi <= sample <= z.end_mi
        ]
        if not covering:
            return None
        return min(covering, key=lambda z: (z.reason != "construction", z.start_mi))

    def closed_lane_at(
        self, mile: float | None = None, *, lane_count: int | None = None
    ) -> int | None:
        """Which lane index is coned off at a mile, or ``None`` for none.

        Derived from the closure's SIDE and the lanes the road has here, so
        it follows a stretch that widens or narrows instead of pointing at
        whichever lane happened to carry that index where the zone was
        placed. ``lane_count`` overrides the road's count for a caller that
        steers by its own (the exit ramp is one lane whatever the mainline
        does). One lane our side means there is nowhere to send anybody, so
        nothing is closed.
        """
        zone = self.active_closure(mile)
        if zone is None or zone.closed_side is None:
            return None
        count = self.lane_count_at(mile) if lane_count is None else lane_count
        if count < 2:
            return None
        return 0 if zone.closed_side == "right" else count - 1

    def has_open_adjacent_lane_at(self, mile: float | None = None) -> bool:
        """Whether there is anywhere on this side to swerve into right now.

        The same two facts a lane change already answers to: how many lanes
        our side has (``lane_count_at``, the same count ``_tap_lane_change``
        refuses against with "There is no lane to your left/right here"), and
        which one a work zone has coned off (``closed_lane_at``). One lane
        our side, or a two-lane stretch with the other lane shut, leaves
        nowhere to send a dodge -- a hazard warning must not offer a lane
        change nobody can make.
        """
        count = self.lane_count_at(mile)
        if count < 2:
            return False
        if self.closed_lane_at(mile, lane_count=count) is not None:
            count -= 1
        return count >= 2

    def _span_is_multilane(self, start_mi: float, end_mi: float) -> bool:
        """True when every mile of a work zone footprint -- taper included --
        has a second lane our side.

        A closure needs somewhere to send the driver. Where the road narrows
        to one lane there is no such place, and coning that lane off pinned
        the truck in a lane it was ordered out of and could not leave (tester
        report, Detroit-Mansfield, 2026-08-11). Checking only the start mile
        is not enough: a zone that begins on two lanes and ends on one is the
        same trap a few miles later.
        """
        stop = min(self.total_miles, max(start_mi, end_mi))
        mile = max(0.0, min(start_mi, stop))
        while mile < stop:
            if self.lane_count_at(mile) < 2:
                return False
            mile += LANE_CLOSURE_SAMPLE_MI
        return self.lane_count_at(stop) >= 2

    def state_at(self, mile: float | None = None) -> str:
        """The state the truck is in, or empty where the bake is silent.

        Baked per leg segment, so it follows the road rather than the endpoint
        cities -- a leg that clips a corner of a third state answers with that
        state while the wheels are in it.
        """
        sample_mile = self.position_mi if mile is None else mile
        leg_i, leg_start = self._leg_at_mile(sample_mile)
        leg = self.route.legs[leg_i]
        forward = self.route.cities[leg_i] == leg.a
        offset = max(0.0, min(leg.miles, sample_mile - leg_start))
        return _leg_state_at(leg, offset if forward else leg.miles - offset) or ""

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
        state = self.state_at(mile)
        lat, lon = self.latlon_at(mile)
        if state and (lat or lon):
            world = get_world()
            state_codes = getattr(self, "_state_codes_for_weather", None)
            if state_codes is None:
                state_codes = {
                    name: city.state_code
                    for city in world.cities.values()
                    for name in (city.state, city.state_code)
                    if name
                }
                self._state_codes_for_weather = state_codes
            code = state_codes.get(state, state)
            if len(code) == 2:
                return classify_region(code, lat, lon)
        leg_i, leg_start = self._leg_at_mile(mile)
        leg = self.route.legs[leg_i]
        nearer = leg_i if mile - leg_start < leg.miles / 2 else leg_i + 1
        # Same reason as latlon_at: a synthetic route names cities the world
        # does not carry, and no caller of this is worth crashing a trip for.
        # Region only tunes how thick enforcement and weather are; an unknown
        # road simply gets the neutral default.
        try:
            return get_world().cities[self.route.cities[nearer]].region
        except (KeyError, IndexError):
            return ""

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

    def engine_brake_ban_at(self, mile: float) -> str | None:
        """The route city whose no-engine-brake ordinance covers this mile.

        There is no state or federal law against engine braking; towns ban it
        by local noise ordinance, posted at the city limits. The ban rides the
        same urban radius that lowers the speed limit near a route city.
        """
        if not self._near_city(mile):
            return None
        nearest = self._nearest_urban_city(mile)
        return None if nearest is None else nearest[0]

    def next_engine_brake_ban(self, within_mi: float) -> tuple[float, str] | None:
        """Start mile and city of the next ban zone ahead, inside the window."""
        pos = self.position_mi
        best: tuple[float, str] | None = None
        for i, mp in enumerate(self._city_mileposts):
            start = mp - URBAN_RADIUS_MI
            if pos < start <= pos + within_mi and (best is None or start < best[0]):
                best = (start, self.route.cities[min(i, len(self.route.cities) - 1)])
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

    @property
    def in_construction_zone(self) -> bool:
        """Inside the signed footprint of roadwork -- taper included.

        Not ``active_zone.reason``: that returns the slowest zone at this
        mile, so a jam laid over the roadwork would hide it. Enforcement asks
        whether any construction zone covers the truck, and the merge taper
        counts as one -- it is the same closure, the same crew, and it is
        where the barrels are.
        """
        return any(
            z.reason in CONSTRUCTION_ZONE_REASONS
            and z.start_mi <= self.position_mi <= z.end_mi
            and self._zone_is_active(z)
            for z in self.zones
        )

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

    def interchange_at(self, route_mile: float, tol_mi: float = 2.0):
        """The baked interchange nearest a route mile, or None.

        Sibling of ``ramp_control_at``, walking the same legs the same way.
        The control heuristic needs more than the control field: where the
        ramp GOES decides what can be at the end of it, and that lives in the
        interchange's ``via`` and ``destinations``.
        """
        best = None
        best_dist = tol_mi
        for i, (start, leg) in enumerate(zip(self._leg_starts, self.route.legs, strict=True)):
            forward = self.route.cities[i] == leg.a
            for ix in leg.interchanges:
                offset = _stop_offset_for_direction(ix.at_mi, leg.miles, forward)
                dist = abs(start + offset - route_mile)
                if dist <= best_dist:
                    best_dist = dist
                    best = ix
        return best

    def _active_zone_at(self, mile: float) -> Zone | None:
        active = [
            z for z in self.zones if z.start_mi <= mile <= z.end_mi and self._zone_is_active(z)
        ]
        if not active:
            return None
        return min(active, key=lambda z: z.limit_mph)

    def nearest_stop_within(self, radius_mi: float = 1.5) -> RoadStop | None:
        """The stop closest to the truck, not the first one listed.

        First-in-list-order stood in for nearest here, so stopping at a scale
        with a travel plaza also inside the radius could open the plaza's
        menu -- whichever the leg data happened to list first.
        """
        best: RoadStop | None = None
        best_dist = radius_mi
        for stop in self.stops:
            dist = abs(stop.at_mi - self.position_mi)
            if dist <= best_dist and (best is None or dist < best_dist):
                best = stop
                best_dist = dist
        return best

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

    @property
    def progress_percent(self) -> int:
        """Whole-percent trip progress, the figure the drivers board shows."""
        total = self.total_miles or 1.0
        return max(0, min(100, round(100.0 * self.position_mi / total)))

    def progress_summary(self, imperial: bool = True) -> str:
        remaining = _spoken_distance(
            to_distance(self.remaining_miles, imperial),
            distance_unit(imperial, plural=False),
        )
        dist = f"{remaining} remaining of {to_distance(self.total_miles, imperial):.0f}"
        leg = self.route.legs[self.current_leg_index]
        next_context = self.next_navigation_context(imperial)
        terrain_text = self._current_grade_text()
        lane_text = self._current_lane_text()
        lane_part = f" {lane_text.capitalize()}." if lane_text else ""
        if self._is_facility_approach_route() and self.destination_label:
            toward_text = self.destination_label
        else:
            toward = self.route.cities[self.current_leg_index + 1]
            world = get_world()
            toward_name = world.spoken_city(toward, qualified=False)
            toward_text = f"{toward_name}, {world.cities[toward].state}"
        return f"{dist}. On {leg.highway} toward {toward_text}.{lane_part} {terrain_text}. {next_context}"

    def _current_lane_text(self) -> str:
        """Lane count in plain words for the road-status readout, or empty where
        the bake is silent here."""
        info = self.lanes_at()
        if info is None:
            return ""
        n, divided = info
        lanes = f"{lane_word(n)} lane{'s' if n != 1 else ''} your side"
        return f"divided, {lanes}" if divided else lanes

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
        ahead_text = _spoken_distance(
            to_distance(ahead, imperial), distance_unit(imperial, plural=False)
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
            # The cue text is a full clause ("a low bridge, signed 13 feet
            # 6 inches. Your route clears it"), so the wrapper only places
            # it on the road -- the old "Posted restriction in X: ... posted
            # Y" double-header read as word salad (owner, 2026-08-13).
            return f"In {ahead_text}, {cue.text}."
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
        return f"Next listed exit in {self._ahead_text(ahead)}: {cue.text}."

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
        for post in self.posts:
            # A post whose watch the truck has already entered was heard
            # before the save; one still ahead has not been, and must get its
            # cue again -- a resumed trip may not silently skip an
            # announcement the post then observes the driver on.
            if post.watch_start_mi <= self.position_mi:
                post.announced = True
                self._heads_up_seen.add(post.id)
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

        # Arm or run down the approach's release tail before the scale is
        # read, so pacing eases back over real seconds instead of snapping the
        # frame an exit is taken, cancelled, or missed.
        if self._armed_exit_decompression():
            self._exit_approach_release_s = EXIT_APPROACH_RELEASE_S
        else:
            self._exit_approach_release_s = max(0.0, self._exit_approach_release_s - dt)

        # weather drives truck grip and evolves over game time
        scale = self.effective_time_scale
        game_min = dt * scale / 60.0
        self.game_minutes += game_min
        self.weather.set_region(self._region_at(self.position_mi))
        weather_key, weather_lat, weather_lon = self._weather_location()
        previous_weather_key = self.weather.city
        location_changed = weather_key != previous_weather_key
        if location_changed and previous_weather_key is not None:
            self._weather_location_refreshing = True
        self.weather.set_city(weather_key, weather_lat, weather_lon)
        changed = self.weather.update(game_min)
        source_status = self.weather.source_status
        if changed is not None:
            source_details = self.weather.source_conditions(self.imperial)
            if source_status == "live":
                source_details += f". {self.weather.live_observation_notice()}"
            elif source_status == "last_known":
                source_details += f". {self.weather.last_known_notice()}"
            self._emit(
                TripEventKind.WEATHER_CHANGE,
                f"{self.weather.event_source_label()} changing: {source_details}",
                weather=changed,
            )
            if source_status in ("live", "fallback"):
                self._weather_location_refreshing = False
        else:
            refresh_failure_started = (
                source_status == "last_known"
                and self.weather.live_weather_refresh_failed
                and not self._weather_refresh_issue_announced
            )
            source_changed = source_status != self._weather_source_status
            if source_changed or refresh_failure_started:
                suppress_location_refresh = self._weather_location_refreshing and source_status in (
                    "live",
                    "last_known",
                )
                suppress_routine_refresh = (
                    source_status == "last_known" and self.weather.live_weather_refreshing
                ) or (
                    source_status == "live"
                    and self._weather_source_status == "last_known"
                    and not self._weather_refresh_issue_announced
                )
                if (
                    not suppress_location_refresh
                    and source_status in ("live", "last_known", "fallback")
                    and not suppress_routine_refresh
                ):
                    message = {
                        "live": (
                            "Live weather is ready for your current route position. "
                            f"{self.weather.live_observation_notice()}."
                        ),
                        "last_known": (
                            f"{self.weather.last_known_notice()}. "
                            "Last-known conditions remain in use."
                        ),
                        "fallback": (
                            "Live weather is unavailable. Simulated fallback weather is now in use."
                        ),
                    }[source_status]
                    self._emit(
                        TripEventKind.WEATHER_CHANGE,
                        message,
                        weather=self.weather.current,
                    )
                    self._weather_refresh_issue_announced = (
                        source_status == "last_known" and self.weather.live_weather_refresh_failed
                    )
                if source_status in ("live", "fallback"):
                    self._weather_location_refreshing = False
                    self._weather_refresh_issue_announced = False
        self._weather_source_status = source_status
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
            # effective_time_scale, not time_scale: the manager turns real
            # seconds into game hours to move its vehicles, and that is
            # exactly the conversion effective_time_scale exists to own. On
            # the raw figure the traffic ran at full compression while the
            # truck was maneuvering at reduced pacing, so the NPCs slid
            # relative to the player instead of holding station with them --
            # a truck you were slowly gaining on would jump away.
            time_scale=self.effective_time_scale,
            # Local, not the departure hour: the density model is about the
            # road the truck is on right now, and a long run crosses rush
            # hours and empties out overnight while it drives.
            hour=self.local_hour,
            # The hourly volume curve has a quieter weekend shape, and the
            # density model reads the same curve congestion does.
            weekend=self._is_weekend_now(),
        )
        self._check_zones()
        self._check_chain_law()
        self._check_speed_limit()
        self._check_limit_drop_ahead()
        # Navigation before stop notices: when both fire on the same tick --
        # departure is the big one, where the onramp merge cue and a nearby
        # travel plaza announce together -- the actionable instruction must
        # reach the event voice first.
        self._check_facility_leg_reset()
        self._check_navigation_cues()
        self._check_npc_traffic_cues()
        self._check_traffic_pressures()
        self._check_real_traffic_events()
        self._check_curves()
        self._check_lane_changes()
        self._check_stops()
        self._check_roadside_callouts()
        self._check_tolls()
        self._check_cities()
        self._check_timezone()
        if moved_mi > 0.0:
            self._check_enforcement_heads_up()
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
        """(closed lane name, direction to merge) for a zone's coned-off lane.

        Read off the side the zone stores rather than worked out from a lane
        index, so the side the player is told is the side that is shut on any
        road, however many lanes it has.
        """
        shut = zone.closed_side or ("right" if zone.closed_lane == 0 else "left")
        return shut, ("left" if shut == "right" else "right")

    def _zone_warning_message(self, zone: Zone, ahead: float) -> str:
        if zone.reason == "construction":
            if zone.closed_side is not None:
                shut, keep = self._closure_phrases(zone)
                merge_part = f"The {shut} lane is closed; merge {keep} at the taper. "
            else:
                merge_part = "All lanes stay open through the work; hold your lane. "
            return (
                f"Brake now! In {self._ahead_text(ahead)}, construction ahead. "
                f"{merge_part}Speed limit "
                f"{self._speed_value(CONSTRUCTION_TAPER_LIMIT_MPH)} at the taper, then "
                f"{self._speed_value(zone.limit_mph)} through the work zone."
            )
        if zone.reason == "heavy traffic" and zone.aadt is not None:
            return (
                f"In {self._ahead_text(ahead)}, {self._congestion_phrase()} ahead. "
                f"Traffic slowing to {self._speed_value(zone.limit_mph)}."
            )
        return (
            f"In {self._ahead_text(ahead)}, {zone.reason} ahead. "
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
            if zone.closed_side is not None:
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
            if zone.closed_side is not None:
                shut, keep = self._closure_phrases(zone)
                # "Stay in the left lane" was only ever the whole truth on a
                # road two lanes wide; three lanes across it named a lane the
                # driver had no reason to be in. "Keep left" is the same
                # instruction on a two-lane stretch and still true on a wider
                # one.
                return (
                    f"Work zone active. The {shut} lane is closed; keep {keep} "
                    "and watch the barrels. "
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
        # The NEXT zone only, not every zone inside the lookahead. A facility
        # approach zones each street at its own baked speed, so a one-mile
        # surface chain can hold four or five of them -- and warning about all
        # of them at once fired five contradictory lines inside sixty
        # milliseconds, "access road ahead, speed limit 15" hard against
        # "access road ahead, speed limit 25", neither of them the number then
        # in force (owner playtest, 2026-08-17). One warning, for the one the
        # driver reaches next; the rest become eligible as it is passed.
        due = [
            (zone.start_mi - self.position_mi, zone)
            for zone in self.zones
            if zone.reason != "construction merge"
            and _zone_key(zone) not in self._announced_zone_warnings
            and ZONE_WARNING_MIN_MI < zone.start_mi - self.position_mi <= lookahead
            and self._zone_is_active(zone)
        ]
        # One warning OUTSTANDING at a time, not one per frame: the loop runs
        # every tick, so capping it per call still fired four lines inside
        # three milliseconds. The next zone is not announced until the truck
        # has actually reached the one it was last warned about.
        pending = self._pending_zone_warning
        if pending is not None and self.position_mi < pending:
            return
        if due:
            ahead, zone = min(due, key=lambda pair: pair[0])
            self._announced_zone_warnings.add(_zone_key(zone))
            self._pending_zone_warning = zone.start_mi
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
                # _active_zone below tracks the truck's real position on
                # every call regardless of what narrates: the posted limit
                # and every mechanic that reads it (cruise cancel, the zone
                # earcon, achievements -- all keyed off the ZONE_ENTER event
                # itself) stay correct even when the colour line is held
                # back for pacing.
                #
                # But holding it back is only safe when the number is not
                # changing for the worse. A zone entry that CUTS the limit
                # currently in force -- most often the merge taper's posted
                # 55 giving way to the work zone's real 45 -- never waits:
                # _check_speed_limit stays silent for as long as any zone is
                # active, so this is the only line that will ever say the
                # lower number, and the taper already told the driver a
                # number that is no longer true. A same-or-higher-limit
                # entry (a second cosmetic zone, a shoulder closure at the
                # same posted speed) is cosmetic and free to breathe.
                old_limit = (
                    self._active_zone.limit_mph
                    if self._active_zone is not None
                    else self._announced_speed_limit
                )
                urgent = old_limit is not None and zone.limit_mph < old_limit
                if urgent or self._event_breather.ready("zone"):
                    self._speak_zone_entry(zone)
                else:
                    # Gated, not dropped: the next open window speaks for
                    # whichever zone is actually current (see the
                    # self-supersede branch below), never a stale catch-up
                    # for this one specifically.
                    self._zone_entry_spoken = False
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
                self._zone_entry_spoken = True
            self._active_zone = zone
        elif (
            zone is not None and not self._zone_entry_spoken and self._event_breather.ready("zone")
        ):
            # Self-supersede: this zone is still the one actually governing
            # the truck (nothing newer has taken its place), and its own
            # entry was gated when it started. The window is open now, so
            # it is spoken for the CURRENT zone rather than staying silent
            # forever.
            self._speak_zone_entry(zone)

    def _speak_zone_entry(self, zone: Zone) -> None:
        quiet = zone.reason == "construction" and any(
            z.reason == "construction merge" and abs(z.end_mi - zone.start_mi) < 0.01
            for z in self.zones
        )
        self._event_breather.spoke("zone")
        self._emit(
            TripEventKind.ZONE_ENTER,
            self._zone_entry_message(zone),
            zone=zone,
            suppress_sound=quiet,
        )
        self._zone_entry_spoken = True

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
            # Routine changes breathe (see road_event_pacing); a serious
            # unannounced drop does not wait -- it is ticket-relevant now.
            urgent = (
                lowered
                and self._announced_speed_limit - limit > 10.0
                and round(limit, 1) not in self._limit_drop_preannounced
            )
            if not urgent and not self._event_breather.ready("limit"):
                return  # untouched state; the next check self-supersedes
            self._announced_speed_limit = limit
            if lowered:
                # The advance pacenote or an assist's "easing to X" line may
                # already have named this exact number for this posting --
                # the arrival line repeating it a moment (or, under
                # compression, an instant) later was the owner's live-playtest
                # complaint (2026-08-12). Consumed once: an unannounced drop
                # right after still gets its own "reduced to".
                key = round(limit, 1)
                if key in self._limit_drop_preannounced:
                    self._limit_drop_preannounced.discard(key)
                    return
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
            elif lowered:
                where = self._lowered_limit_reason()
            # A short lower zone (a village main street) is a passing event,
            # not a new cruising speed: say how long it lasts so the player
            # is not left guessing when the road opens back up.
            span = ""
            if lowered:
                length = self._limit_zone_length(limit)
                if length is not None and length <= LIMIT_SHORT_ZONE_MI:
                    span = f" for {_spoken_short_miles(length, self.imperial)}"
            self._event_breather.spoke("limit")
            self._emit(
                TripEventKind.GPS_CUE,
                f"Speed limit {verb} {self._speed_value(limit)}{where}{span}.",
                # The road's state, not a turn to act on. Marked so the
                # driving speech ladder can tell it from the GPS_CUE that
                # says "merge onto I-90 East", which must never go quiet.
                limit_change=True,
            )

    def _lowered_limit_reason(self) -> str:
        """Why a drop with no city to blame is happening, checked in the
        order the trip can actually back it up: a road stop just ahead, then
        a real downgrade just ahead. Bare when neither applies."""
        stop_reason = self._lowered_limit_stop_reason()
        if stop_reason:
            return stop_reason
        if self._lowered_limit_downgrade_ahead():
            return " for the downgrade"
        return ""

    def _lowered_limit_stop_reason(self) -> str:
        """A road stop that plausibly explains a lower posting, scanning a
        short lookahead ahead of the truck only -- a stop just passed does
        not explain a limit dropping now."""
        end = self.position_mi + LIMIT_REASON_LOOKAHEAD_MI
        for stop in self.stops:
            if self.position_mi <= stop.at_mi <= end:
                reason = LIMIT_REASON_BY_STOP_TYPE.get(stop.type)
                if reason:
                    return reason
        return ""

    def _lowered_limit_downgrade_ahead(self) -> bool:
        """Whether a sustained downgrade starts here -- steep enough on
        average over the next half mile to be the road's own reason for the
        lower number, not one steep sample the profile flattens out again a
        tenth later."""
        mi = self.position_mi
        end = min(self.total_miles, mi + LIMIT_DOWNGRADE_MIN_MI)
        if end - mi < LIMIT_DOWNGRADE_MIN_MI:
            return False  # not enough road left to call the downgrade sustained
        samples = []
        probe = mi
        while probe <= end:
            samples.append(self.grade_at(probe) * 100.0)
            probe += LIMIT_SCAN_STRIDE_MI
        return (sum(samples) / len(samples)) <= LIMIT_DOWNGRADE_PCT

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

    def _limit_drop_warning_lead_mi(self, speed: float) -> float:
        """Lead distance for the "drops to X" pacenote, scaled so the player
        gets roughly ``LIMIT_WARNING_REAL_S`` of real hearing-and-braking time
        despite speed and time compression -- see ``LIMIT_WARNING_REAL_S``."""
        speed = max(speed, 1.0)
        miles = LIMIT_WARNING_REAL_S * speed * self.effective_time_scale / 3600.0
        return max(PACENOTE_MIN_LEAD_MI, min(miles, LIMIT_WARNING_MAX_LEAD_MI))

    def note_limit_preannounced(self, limit_mph: float) -> None:
        """Record that an assist just spoke the incoming posted limit itself
        (speed keeper / adaptive cruise "easing to X"), so the plain arrival
        confirmation does not repeat the same number a moment later."""
        self._limit_drop_preannounced.add(round(limit_mph, 1))

    def _next_limit_drop(self) -> tuple[float, float] | None:
        """The next corridor limit change ahead, when it is a warn-worthy drop.

        Returns ``(boundary_mi, new_limit)`` for the FIRST change inside the
        pacenote window -- never warning across an intermediate change -- and
        only when the drop is big enough to need a braking plan. The boundary
        is refined to a fine stride so its dedup key stays stable no matter
        where inside a tick the scan starts."""
        current = self._corridor_limit_at(self.position_mi)
        prev = self.position_mi
        end = min(self.total_miles, self.position_mi + LIMIT_WARNING_MAX_LEAD_MI)
        while prev < end:
            mi = min(end, prev + LIMIT_SCAN_STRIDE_MI)
            limit = self._corridor_limit_at(mi)
            if limit != current:
                if current - limit < LIMIT_DROP_WARN_MIN_DELTA_MPH:
                    return None
                boundary = mi
                # Anchor the fine probe to ABSOLUTE hundredth-mile marks, not
                # to wherever this tick's position landed: a position-anchored
                # grid shifted every frame, the boundary rounded to a
                # different hundredth, and the dedup key changed -- the same
                # drop warned twice 16 ms apart (owner log, 2026-07-23).
                probe = math.floor(prev * 100.0) / 100.0
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
        if ahead > self._limit_drop_warning_lead_mi(speed):
            return
        self._warned_limit_drops.add(key)
        self._limit_drop_preannounced.add(round(limit, 1))
        self._emit(
            TripEventKind.GPS_CUE,
            f"Speed limit drops to {self._speed_value(limit)} in "
            f"{_spoken_short_miles(ahead, self.imperial)}.",
            # A posting, like the arrival line it precedes: S answers it on
            # demand and the speed control acts on it unasked.
            limit_change=True,
        )

    def name_facility(self, plain_name: str, full_name: str) -> str:
        """Full form on the first mention of a facility this leg, the proper
        name alone after (research doc R6). Marking is a side effect: the
        caller is about to speak the returned name."""
        key = plain_name.strip().lower()
        if key in self._facilities_named:
            return plain_name
        self._facilities_named.add(key)
        return full_name

    def reset_facility_mentions(self) -> None:
        """Bring the full form back once -- a resume from a pause, where the
        player may have lost the thread (research doc R6)."""
        self._facilities_named.clear()

    def _check_facility_leg_reset(self) -> None:
        """A new leg brings every facility's full form back once."""
        leg = 0
        for i, start in enumerate(self._leg_starts):
            if self.position_mi >= start:
                leg = i
        if leg != self._facility_leg:
            self._facility_leg = leg
            self._facilities_named.clear()

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
                    planned=True,
                )
        for stop in self.stops:
            ahead = stop.at_mi - self.position_mi
            if 0 < ahead <= STOP_AHEAD_LOOKAHEAD_MI and stop.key not in self._announced_stops:
                self._announced_stops.add(stop.key)
                # The plan flag rides the event so the driving layer can rank
                # the stop the player chose above ambient roadside chatter.
                self._emit(
                    TripEventKind.STOP_AHEAD,
                    stop_callout(
                        planned_prefix=self.planned_prefix(stop),
                        typed_name=self.name_facility(stop.name, stop.spoken_name),
                        plain_name=stop.name,
                        exit_label=stop.exit_label,
                        distance=self._ahead_text(ahead),
                        parking_normal=stop.parking_text,
                        parking_certainty=stop.parking,
                        exit_hint=self.exit_hint,
                    ),
                    stop=stop,
                    planned=self.is_planned(stop),
                )

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
                        f"Traffic slowing ahead in {self._ahead_text(ahead)}; {cue.text}{speed}.",
                        cue=cue,
                    )
                continue
            if cue.kind == "toll":
                advance_key = f"{cue.key}:advance"
                if 0 < ahead <= 2.0 and advance_key not in self._announced_navigation:
                    self._announced_navigation.add(advance_key)
                    # The heads-up is a preview: terse drops it whole, since
                    # the charged line itself is guaranteed (ROUTE, R1) and
                    # is what carries the cost.
                    self._emit(TripEventKind.GPS_CUE, terse_silent(cue.near_text), cue=cue)
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
            # The near announcement fires from 0.1 mile out, so a lead any
            # closer than that says the same thing twice in a breath -- which
            # is what the old "skip it if it renders as 0 miles" guard was
            # really protecting against. Expressed as the distance it always
            # was, so the wording is free to improve without silently
            # resurrecting the double.
            if (
                NAV_LEAD_MIN_MI < ahead <= lookahead
                and advance_key not in self._announced_navigation
            ):
                self._announced_navigation.add(advance_key)
                # Was rendered with _distance_text and then suppressed when it
                # came out as "0 ...", which lost the lead announcement
                # entirely inside half a mile rather than wording it. The
                # ladder never says zero, so the cue is spoken with a real
                # distance instead of dropped.
                message = f"In {self._ahead_text(ahead)}, {cue.text}."
                # Marked as the lead rather than the turn: the near call
                # below is the one you cannot recover from, and it always
                # speaks. This one is a heads-up and retires to a tone at
                # urgent_only (see SpeechCategory.NAVIGATION_ADVISORY).
                self._emit(TripEventKind.GPS_CUE, message, cue=cue, advance=True)
            if -0.1 <= ahead <= 0.1 and near_key not in self._announced_navigation:
                self._announced_navigation.add(near_key)
                if cue.kind == "checkpoint":
                    self._emit(TripEventKind.CHECKPOINT, cue.near_text, cue=cue)
                else:
                    self._emit(TripEventKind.GPS_CUE, cue.near_text, cue=cue)

    def _traffic_pressure_message(self, pressure: TrafficPressure, ahead: float) -> SpokenMessage:
        """A traffic advisory, with the terse half these were shipped without.

        These returned a plain ``str``, which the ladder treats as its own
        terse rendering -- so at quiet "Exit traffic building in 2 miles.
        Signal early, hold the right exit lane, and be ready to slow near
        45" was spoken in full, the longest line on the drive. Terse keeps
        what the player acts on (which side, how far, and the number when
        there is one) and drops the coaching around it.
        """
        distance = self._ahead_text(ahead)
        speed = self._speed_value(pressure.target_speed_mph)
        side = pressure.direction
        if pressure.kind == "exit":
            return SpokenMessage(
                f"Exit traffic building in {distance}. Signal early, hold the "
                f"{side} exit lane, and be ready to slow near {speed}.",
                f"Exit traffic, {distance}. Hold {side}, {speed}.",
            )
        if pressure.kind == "construction_merge":
            # No target speed: the taper's actual posted limit is spoken
            # separately by the zone warning/entry lines (a real sign, not a
            # traffic-behavior guess). This advisory is merge-only, same
            # rule as merging_traffic_cue below -- see docs/ontology.md.
            return SpokenMessage(
                f"Traffic squeezing at the construction taper in {distance}. "
                f"Merge {side} early and leave a gap.",
                f"Taper squeezing, {distance}. Merge {side}.",
            )
        if pressure.kind == "route_merge":
            return SpokenMessage(
                f"Merging traffic in {distance}. Keep {side} and leave a gap.",
                f"Merging traffic, {distance}. Keep {side}.",
            )
        return SpokenMessage(
            f"Traffic pack in {distance}. Leave extra following room and be ready for {speed}.",
            f"Traffic pack, {distance}. {speed}.",
        )

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

    def _enforcement_warning_lookahead_mi(self) -> float:
        """Lead distance for an enforcement cue, in miles, sized in real time.

        A flat five miles was five miles of *game* road: at the faster
        pacing the player passed the post before an eighteen-word CB call
        had finished speaking. Scale it with speed and pacing the way zone
        warnings already are, and clamp it so it is never shorter than the
        old distance and never absurd.
        """
        speed = max(self.truck.speed_mph, 1.0)
        miles = ENFORCEMENT_WARNING_REAL_S * speed * self.effective_time_scale / 3600.0
        return max(CB_PATROL_LOOKAHEAD_MI, min(miles, ENFORCEMENT_WARNING_MAX_MI))

    def _check_enforcement_heads_up(self) -> None:
        """Mark posts heard, and spend the run's small CB speech budget well.

        Two things happen here, and only the first one is unconditional.
        Every post inside the lead window is marked announced, because a post
        the player was never cued for is not allowed to observe them -- the
        cue itself is the marked-unit pass earcon and the scale swell, which
        the driving layer plays. The CB heads-up on top of that is speech, and
        speech is rationed: at most CB_CALLS_PER_RUN for a whole delivery,
        spent on the posts the driver's current speed actually exposes them
        to. Candidates are sorted by urgency rather than by mile order, so a
        cluster around a work zone cannot push a nearer post's call past its
        own window.
        """
        lookahead = self._enforcement_warning_lookahead_mi()
        candidates: list[tuple[float, EnforcementPost, float]] = []
        for post in self.posts:
            ahead = post.watch_start_mi - self.position_mi
            if not (0 < ahead <= lookahead) or post.id in self._heads_up_seen:
                continue
            self._heads_up_seen.add(post.id)
            post.announced = True
            if post.kind in (KIND_FIXED_SCALE, KIND_SCALE_APRON):
                continue  # the scale has its own approach cue; the CB stays out of it
            candidates.append((ahead, post, self._cb_urgency(post)))
        if not candidates or self._cb_calls_made >= CB_CALLS_PER_RUN:
            return
        # Urgency first, then whichever is nearest: a post the truck's speed
        # would walk it into outranks a post it would coast past.
        ahead, post, urgency = max(candidates, key=lambda c: (c[2], -c[0]))
        if urgency <= 0.0:
            return
        if post.tableau and (self.pull_over_active or post.declined):
            # The tableau line waits its turn: not while the player's own
            # stop is running (their own trooper owns the CB right now), and
            # not for a post that already had its own look at the player --
            # "a bear has somebody stopped" makes no sense from the trooper
            # who just personally wrote them up. Dropped, not spoken later:
            # this candidate already consumed its slot in ``_heads_up_seen``.
            return
        self._cb_calls_made += 1
        # A post already working a tableau gets its own line -- a bear with a
        # customer, not a bear on the hunt -- but rides the same rationed
        # budget and urgency selection as every other heads-up.
        message = (
            self.cb_tableau_message(post, ahead)
            if post.tableau
            else self.cb_patrol_message(post, ahead)
        )
        self._emit(
            TripEventKind.GPS_CUE,
            message,
            cb_patrol=post,
        )

    def _cb_urgency(self, post: EnforcementPost) -> float:
        """How much this post matters to how the truck is being driven now.

        Never zero for a staffed post: the ration decides whether the call is
        spoken, and a report the player cannot check must not be withheld
        because they happen to be legal in this instant. Speed only raises
        the priority.
        """
        limit, _ = self.speed_limit_at(post.at_mi)
        over = max(0.0, self.truck.speed_mph - limit)
        base = 1.0 if post.staffed else 0.35
        return base + min(2.0, over / 10.0)

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
