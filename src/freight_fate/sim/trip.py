"""Trip simulation: progress along a route, grades, zones, stops, and events.

The truck physics run in real time; the trip layer compresses distance with a
configurable time scale (default 20x), so a 300-mile haul takes roughly
fifteen minutes at highway speed instead of five hours. The in-game clock
advances at the same rate, which keeps deadlines meaningful.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from enum import Enum

from ..data.world import STOP_TYPE_LABELS, Leg, Route, TollEvent, get_world
from .hos import is_night, time_of_day
from .vehicle import TruckState
from .weather import WeatherKind, WeatherSystem

BASE_SPEED_LIMIT_MPH = 70.0

# Posted speed limit by corridor. Where a leg carries a baked OSM ``maxspeed``
# profile (see ``Leg.speed_limits``), the runtime uses that real posted limit;
# otherwise it falls back to this heuristic, derived from the highway class
# (Interstate / US highway / state route) and region -- rural Interstates run
# faster out West -- and dropped to an urban limit near cities. The heuristic is
# a grounded approximation, the backstop for legs OSM has no maxspeed tag on.
URBAN_LIMIT_MPH = 55.0
URBAN_RADIUS_MI = 6.0     # urban speed reduction within this distance of a city
US_HIGHWAY_LIMIT_MPH = 65.0
STATE_ROUTE_LIMIT_MPH = 60.0

# Rural Interstate posted limit by region.
INTERSTATE_RURAL_LIMIT_MPH: dict[str, float] = {
    "great_basin": 80.0,
    "southern_plains": 75.0,
    "desert_southwest": 75.0,
    "rockies": 75.0,
    "gulf_coast": 75.0,
    "heartland": 70.0,
    "great_lakes": 70.0,
    "mid_south": 70.0,
    "atlantic_southeast": 70.0,
    "florida": 70.0,
    "appalachia": 70.0,
    "pacific_northwest": 70.0,
    "northeast": 65.0,
    "california": 65.0,
}


def _highway_class(highway: str) -> str:
    h = (highway or "").strip().upper()
    if h.startswith(("I-", "I ", "INTERSTATE")):
        return "interstate"
    if h.startswith("US"):
        return "us_highway"
    return "state_route"


def corridor_speed_limit(highway: str, region: str) -> float:
    """Open-road posted limit for a corridor from its highway class and region."""
    cls = _highway_class(highway)
    if cls == "interstate":
        return INTERSTATE_RURAL_LIMIT_MPH.get(region, BASE_SPEED_LIMIT_MPH)
    if cls == "us_highway":
        return US_HIGHWAY_LIMIT_MPH
    return STATE_ROUTE_LIMIT_MPH


def _leg_speed_limit_at(leg: Leg, offset_mi: float) -> float | None:
    """Baked OSM posted limit at a leg-relative offset, or ``None`` if unbaked.

    The samples are a step function (already sorted by ``at_mi`` at load time):
    the limit in effect is the last sample at or before the offset. Before the
    first sample, the first sample applies."""
    samples = leg.speed_limits
    if not samples:
        return None
    chosen = samples[0]
    for sample in samples:
        if sample.at_mi <= offset_mi:
            chosen = sample
        else:
            break
    return chosen.mph
FACILITY_ACCESS_LIMIT_MPH = 25.0
DESTINATION_APPROACH_LIMIT_MPH = 35.0
FACILITY_GATE_LIMIT_MPH = 15.0
DESTINATION_APPROACH_ZONE_MI = 3.0
FACILITY_GATE_ZONE_MI = 0.5
NIGHT_HAZARD_BONUS = 0.10          # extra hazard risk after dark
NIGHT_TRAFFIC_KEEP = 0.4           # chance a traffic zone still forms at night
TRAFFIC_LOOKAHEAD_MI = 2.5
TRAFFIC_WARNING_GAP_S = 2.2
ZONE_WARNING_LOOKAHEAD_MI = 2.0    # minimum distance heads-up for a zone
# Distance compression (time_scale) and speed eat into how much *real* time a
# fixed-distance warning gives -- 2 miles at 70 mph and 20x is only ~5 seconds.
# Scale the lead distance with speed and pacing for a roughly constant real-time
# heads-up, clamped between the base distance and a sane maximum.
ZONE_WARNING_REAL_S = 12.0         # target real seconds of warning
ZONE_WARNING_MAX_MI = 8.0
STATE_CROSSING_WARNING_LOOKAHEAD_MI = 10.0
CONSTRUCTION_ENFORCEMENT_GRACE_MI = 1.0

# Road hazards are grounded in what actually puts a tractor-trailer on the
# brakes on an interstate, and in *where and when* it happens. Each hazard is
# tagged with the conditions under which it is plausible; a hazard is only ever
# drawn when the current region, weather, terrain, and time of day all allow
# it. This replaces an earlier flat region pool that could, say, announce farm
# equipment merging onto a freeway or a dust devil on a clear calm day.

# Patrol density by region: dense, urbanized states run hot; wide-open country
# runs cold. Regions not listed sit at the neutral baseline.
_HOT_PATROL_REGIONS = ("northeast", "california", "great_lakes", "florida",
                       "atlantic_southeast", "mid_south")
_COLD_PATROL_REGIONS = ("great_basin", "southern_plains", "rockies",
                        "desert_southwest", "heartland")

# Open, exposed country where high wind genuinely shoves a loaded trailer.
_CROSSWIND_REGIONS = ("southern_plains", "heartland", "great_basin",
                      "desert_southwest", "rockies")
# Wet-road weather where standing water and hydroplaning are real risks.
_WET = (WeatherKind.RAIN, WeatherKind.HEAVY_RAIN, WeatherKind.THUNDERSTORM)
_HEAVY_WET = (WeatherKind.HEAVY_RAIN, WeatherKind.THUNDERSTORM)
# Times wildlife actually moves onto the road.
_WILDLIFE_TIMES = frozenset({"dawn", "dusk", "night"})


@dataclass(frozen=True)
class HazardDef:
    """One grounded road hazard and the conditions under which it can occur.

    A ``None`` on ``regions``/``weather``/``terrain`` means "no restriction on
    that axis". ``animal`` hazards are biased to dawn, dusk, and night, when
    wildlife is actually on the move. Selection weights by ``weight`` *after*
    the eligibility filter, so context shapes both which hazards are possible
    and how likely each one is.
    """

    text: str
    weight: float = 1.0
    regions: tuple[str, ...] | None = None
    weather: tuple[WeatherKind, ...] | None = None
    terrain: tuple[str, ...] | None = None
    animal: bool = False


HAZARDS: tuple[HazardDef, ...] = (
    # Nationwide staples: plausible on any interstate, in any conditions.
    HazardDef("debris on the road", 1.2),
    HazardDef("retread debris from a blown tire", 1.0),
    HazardDef("a vehicle stopped on the shoulder", 1.0),
    HazardDef("a slow vehicle ahead", 0.9),
    HazardDef("a sudden lane closure ahead", 0.8),
    HazardDef("stopped traffic around a fender bender", 0.9),
    # Wildlife: dawn/dusk/night, regional species.
    HazardDef("a deer crossing the road", 1.3, animal=True,
              regions=("northeast", "appalachia", "great_lakes", "heartland",
                       "mid_south", "atlantic_southeast", "southern_plains",
                       "gulf_coast", "florida", "california")),
    HazardDef("an elk crossing the road", 1.1, animal=True,
              regions=("rockies", "great_basin", "pacific_northwest")),
    HazardDef("an animal on the road", 0.7, animal=True),  # generic fallback
    # Wet weather only.
    HazardDef("standing water flooding the lane", 1.1, weather=_WET),
    HazardDef("the trailer hydroplaning on standing water", 1.0, weather=_HEAVY_WET),
    HazardDef("hail hammering the windshield", 0.7,
              weather=(WeatherKind.THUNDERSTORM,),
              regions=("southern_plains", "heartland", "mid_south", "rockies",
                       "great_lakes")),
    # Snow and ice only.
    HazardDef("a snow squall whiting out the lane", 1.0, weather=(WeatherKind.SNOW,)),
    HazardDef("ice on the bridge deck", 1.0, weather=(WeatherKind.SNOW,)),
    HazardDef("black ice on the shaded grade", 1.1, weather=(WeatherKind.SNOW,),
              terrain=("mountain", "hills")),
    # Dense fog only.
    HazardDef("brake lights looming in dense fog", 1.2, weather=(WeatherKind.FOG,)),
    # High wind: crosswind shove and blowing debris in open country.
    HazardDef("a crosswind gust shoving the trailer", 1.2,
              weather=(WeatherKind.WIND,), regions=_CROSSWIND_REGIONS),
    HazardDef("a dust storm dropping visibility", 0.9, weather=(WeatherKind.WIND,),
              regions=("desert_southwest", "southern_plains", "great_basin")),
    HazardDef("tumbleweeds piling in your lane", 0.5, weather=(WeatherKind.WIND,),
              regions=("desert_southwest", "great_basin", "southern_plains")),
    # Mountain terrain only.
    HazardDef("rockfall debris on the road", 1.0, terrain=("mountain",),
              regions=("rockies", "appalachia", "great_basin",
                       "pacific_northwest", "california")),
    HazardDef("a runaway truck on the grade ahead", 0.8, terrain=("mountain",)),
)


def eligible_hazards(region: str, weather: WeatherKind, terrain: str,
                     game_hours: float) -> list[tuple[str, float]]:
    """Hazards plausible for the current context, as ``(text, weight)`` pairs.

    Filters the catalog by region, weather, and terrain, then biases wildlife
    toward the dawn/dusk/night hours when animals are actually on the road.
    The nationwide staples have no restrictions, so the list is never empty.
    """
    nocturnal = time_of_day(game_hours) in _WILDLIFE_TIMES
    out: list[tuple[str, float]] = []
    for hazard in HAZARDS:
        if hazard.regions is not None and region not in hazard.regions:
            continue
        if hazard.weather is not None and weather not in hazard.weather:
            continue
        if hazard.terrain is not None and terrain not in hazard.terrain:
            continue
        weight = hazard.weight
        if hazard.animal:
            weight *= 2.2 if nocturnal else 0.25
        out.append((hazard.text, weight))
    return out


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
    TOLL_CHARGED = "toll_charged"
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
class PatrolWindow:
    """A stretch of road where a state trooper may be watching.

    ``intensity`` (0-1) is the chance a sustained speeding strike inside the
    window actually gets you pulled over -- higher on busy interstates, in
    construction, and at rush hour or night, lower out on empty plains. The
    ``reason`` is a short spoken label ("speed trap", "construction patrol")."""

    start_mi: float
    end_mi: float
    intensity: float
    reason: str


@dataclass
class RoadStop:
    name: str
    at_mi: float
    type: str = "travel_center"
    actions: tuple[str, ...] = ()
    services: tuple[str, ...] = ()
    parking: str = "unknown"
    exit_label: str = ""   # "exit 7" when a real OSM interchange sits here

    @property
    def label(self) -> str:
        return STOP_TYPE_LABELS.get(self.type, "stop")

    @property
    def spoken_name(self) -> str:
        return f"{self.label}: {self.name}"

    @property
    def parking_text(self) -> str:
        return {
            "confirmed": "confirmed truck parking",
            "likely": "likely truck parking",
            "limited": "limited truck parking",
            "unknown": "parking not verified",
            "none": "no truck parking",
        }.get(self.parking, "parking not verified")


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
class TollCharge:
    event: TollEvent
    amount: float

    @property
    def name(self) -> str:
        return self.event.name


@dataclass(frozen=True)
class NavigationCue:
    key: str
    kind: str
    at_mi: float
    text: str
    near_text: str = ""
    # Speed carried unformatted so display code can render it in the player's
    # chosen units. Only traffic cues set this; others leave it None.
    speed_mph: float | None = None


class Trip:
    """One delivery run along a chosen route."""

    def __init__(self, route: Route, truck: TruckState, weather: WeatherSystem,
                 time_scale: float = 20.0, seed: int | None = None,
                 start_hour: float = 12.0, imperial: bool = True,
                 hazard_scale: float = 1.0) -> None:
        self.route = route
        self.truck = truck
        self.weather = weather
        self.time_scale = time_scale
        # Multiplier on random road-hazard frequency (relaxed mode lowers it).
        self.hazard_scale = max(0.0, hazard_scale)
        self.start_hour = start_hour   # clock hour of day at departure
        # Spoken/listed navigation distances follow the player's unit choice.
        # Backing field set before cues are built below; the property setter
        # re-renders baked cues if the player changes units mid-trip.
        self._imperial = imperial
        self.position_mi = 0.0
        self.game_minutes = 0.0
        self.finished = False
        self.hos_violation = False     # set by the UI layer; gates inspections
        self._rng = random.Random(seed)
        # separate stream so inspections never disturb hazard/zone layout
        self._insp_rng = random.Random(None if seed is None else seed ^ 0x5EED)
        self._events: list[TripEvent] = []
        self._leg_starts = self._compute_leg_starts()
        # Mileposts of every city on the route (leg starts plus the final
        # destination), used to drop the speed limit for the urban stretch.
        self._city_mileposts = list(self._leg_starts) + [self.total_miles]
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
        self._announced_speed_limit: float | None = None  # last spoken corridor limit
        self._announced_zone_warnings: set[str] = set()
        self._construction_zone_grace_start: dict[str, float] = {}
        self._hazard_check_mi = 5.0
        self._inspection_check_mi = 10.0
        self._traffic_warning_mi = 1.0
        self._announced_enforcement: set[str] = set()

    @property
    def imperial(self) -> bool:
        return self._imperial

    @imperial.setter
    def imperial(self, value: bool) -> None:
        if value == self._imperial:
            return
        self._imperial = value
        # Re-render baked cue distances (onramp, continue, rest stop) so a
        # mid-trip unit change updates guidance already laid out on the route.
        # Cue keys are distance-independent, so announcement de-duplication
        # carries over unchanged.
        self.navigation_cues = self._build_navigation_cues()

    def _distance_text(self, miles: float) -> str:
        """Spoken distance in the player's units (miles or kilometers)."""
        if self.imperial:
            return f"{miles:.0f} miles"
        return f"{miles * 1.609344:.0f} kilometers"

    def _gap_text(self, miles: float) -> str:
        """Short following-gap distance (one decimal) in the player's units."""
        if self.imperial:
            return f"{miles:.1f} miles"
        return f"{miles * 1.609344:.1f} kilometers"

    def _speed_value(self, mph: float) -> str:
        """Bare speed-limit number in the player's units (no unit word)."""
        if self.imperial:
            return f"{mph:.0f}"
        return f"{mph * 1.609344:.0f}"

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
                if not stop.curated or not stop.applies_to_direction(from_city == leg.a):
                    continue
                offset = _stop_offset_for_direction(stop.at_mi, leg.miles,
                                                    from_city == leg.a)
                at = start + offset
                exit_label = _nearest_exit_label(leg, stop.at_mi)
                out.append(RoadStop(stop.name, at, stop.type,
                                    stop.actions, stop.services, stop.parking,
                                    exit_label))
        return out

    def _build_navigation_cues(self) -> list[NavigationCue]:
        cues: list[NavigationCue] = []
        for i, (start, leg) in enumerate(zip(self._leg_starts, self.route.legs,
                                             strict=True)):
            forward = self.route.cities[i] == leg.a
            toward = self.route.cities[i + 1]
            heading = _leg_heading(leg.highway, self.route.cities[i], toward)
            shield = f"{leg.highway} {heading}".strip()
            segment_miles = leg.miles
            if i == 0:
                # The onramp doubles as the first leg's "continue", carrying the
                # distance, so the two do not announce the same thing at launch.
                cues.append(NavigationCue(
                    "onramp:0",
                    "onramp",
                    start + 0.05,
                    f"merge onto {shield} toward {toward}",
                    f"Merge onto {shield} toward {toward}; "
                    f"{self._distance_text(segment_miles)}.",
                ))
            elif segment_miles >= 40.0:
                cues.append(NavigationCue(
                    f"continue:{i}",
                    "continue",
                    start + 0.1,
                    f"Continue on {leg.highway} for "
                    f"{self._distance_text(segment_miles)} toward {toward}.",
                ))
            if i > 0 and self.route.legs[i - 1].highway != leg.highway:
                cues.append(NavigationCue(
                    f"maneuver:{i}",
                    "maneuver",
                    start,
                    f"keep right for {shield} toward {toward}",
                    f"Keep right now for {shield} toward {toward}.",
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
                cues.append(NavigationCue(
                    f"toll:{i}:{toll.at_mi}:{toll.name}",
                    "toll",
                    start + offset,
                    f"toll road ahead: {toll.road}",
                    f"{toll.method_label} toll point ahead: {toll.name}. "
                    f"{toll_text}",
                ))
            for ix in leg.interchanges:
                offset = _stop_offset_for_direction(ix.at_mi, leg.miles, forward)
                cues.append(NavigationCue(
                    f"interchange:{i}:{ix.at_mi}:{ix.exit_ref}",
                    "interchange",
                    start + offset,
                    ix.spoken_phrase,
                    ix.near_phrase,
                ))
            for stop in leg.stops:
                if not stop.curated or not stop.applies_to_direction(forward):
                    continue
                offset = _stop_offset_for_direction(stop.at_mi, leg.miles, forward)
                exit_label = _nearest_exit_label(leg, stop.at_mi)
                at_part = f" at {exit_label}" if exit_label else ""
                cues.append(NavigationCue(
                    f"rest_stop:{i}:{stop.at_mi}:{stop.name}",
                    "rest_stop",
                    start + offset,
                    f"{stop.label} ahead{at_part}",
                    f"{stop.label.capitalize()}{at_part} ahead in "
                    f"{'1 mile' if self.imperial else self._distance_text(1.0)}; "
                    f"{stop.parking_label}; press X to take the exit.",
                ))
        for i, lead in enumerate(self.traffic_leads):
            cues.append(NavigationCue(
                f"traffic:{i}:{lead.at_mi:.1f}",
                "traffic",
                lead.at_mi,
                lead.reason,
                f"Traffic slowing ahead; target speed {lead.speed_mph:.0f}.",
                speed_mph=lead.speed_mph,
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
        zones.extend(self._facility_speed_zones())
        zones.sort(key=lambda z: z.start_mi)
        return zones

    def _facility_speed_zones(self) -> list[Zone]:
        """Low-speed facility access roads and final gate approaches."""
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
            Zone(approach_start, total, DESTINATION_APPROACH_LIMIT_MPH,
                 "destination approach"),
            Zone(gate_start, total, FACILITY_GATE_LIMIT_MPH, "facility gate"),
        ]

    def _is_facility_approach_route(self) -> bool:
        return len(self.route.cities) >= 2 and self.route.cities[0] == self.route.cities[-1]

    def _patrol_intensity_at(self, mile: float) -> float:
        """How heavily a stretch is patrolled (0-1), from highway, region, and
        time of day. Busy interstates and dense regions run hotter; empty plains
        run cold; night adds a DUI-patrol bump."""
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
        """Seed trooper patrol windows along the route, roughly one per 120
        miles, plus an always-hot window over every construction zone.

        Uses the inspection RNG so enforcement never perturbs hazard/zone
        layout, and scales the count by ``hazard_scale`` so relaxed mode stays
        relaxed. Deterministic for a given seed and departure hour."""
        patrols: list[PatrolWindow] = []
        total = self.route.miles
        n = max(0, int(total / 120.0 * min(1.0, self.hazard_scale)))
        for _ in range(n):
            at = self._insp_rng.uniform(10, max(11, total - 15))
            length = self._insp_rng.uniform(3, 8)
            intensity = self._patrol_intensity_at(at) * self.hazard_scale
            patrols.append(PatrolWindow(at, at + length,
                                        max(0.1, min(0.95, intensity)),
                                        "speed trap"))
        for zone in self.zones:
            if zone.reason == "construction":
                patrols.append(PatrolWindow(zone.start_mi, zone.end_mi,
                                            min(0.95, 0.9 * self.hazard_scale),
                                            "construction patrol"))
        patrols.sort(key=lambda p: p.start_mi)
        return patrols

    def active_patrol_at(self, mile: float) -> PatrolWindow | None:
        """The hottest patrol window covering a mile, or ``None``."""
        active = [p for p in self.patrols if p.start_mi <= mile <= p.end_mi]
        return max(active, key=lambda p: p.intensity) if active else None

    def _leg_traffic_density(self, leg: Leg, bad_weather_bias: float,
                             night: bool) -> float:
        """Probability a slow-traffic lead forms on ``leg``, scaled by
        ``hazard_scale`` so relaxed mode thins traffic the way it thins hazards
        and patrols. A no-op (x1.0) in realistic mode."""
        metro_bias = 0.18 if leg.checkpoints else 0.0
        night_bias = -0.08 if night else 0.0
        density = min(0.86, max(0.05,
                      0.22 + leg.miles / 900.0 + metro_bias
                      + bad_weather_bias + night_bias))
        return density * self.hazard_scale

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
            density = self._leg_traffic_density(leg, bad_weather_bias, night)
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
        zone = self._active_zone_at(mile)
        if zone is not None:
            return zone.limit_mph, zone.reason
        return self._corridor_limit_at(mile), None

    def _region_at(self, mile: float) -> str:
        """Region of the corridor at a mile (the leg's destination city)."""
        leg_i, _ = self._leg_at_mile(mile)
        city = self.route.cities[min(leg_i + 1, len(self.route.cities) - 1)]
        return get_world().cities[city].region

    def _near_city(self, mile: float) -> bool:
        return any(abs(mile - mp) <= URBAN_RADIUS_MI for mp in self._city_mileposts)

    def _nearest_urban_city(self, mile: float) -> str | None:
        """The route city within the urban radius of ``mile``, or None -- used to
        explain an urban speed-limit drop ('approaching Boston')."""
        best, best_d = None, URBAN_RADIUS_MI
        for i, mp in enumerate(self._city_mileposts):
            d = abs(mile - mp)
            if d <= best_d and i < len(self.route.cities):
                best, best_d = self.route.cities[i], d
        return best

    def _corridor_limit_at(self, mile: float) -> float:
        """Posted limit for the corridor, dropped to the urban limit on the city
        stretches.

        Prefers a real baked OSM ``maxspeed`` for the leg when present, falling
        back to the highway- and region-derived heuristic where OSM has no tag.
        """
        leg_i, leg_start = self._leg_at_mile(mile)
        leg = self.route.legs[leg_i]
        baked = _leg_speed_limit_at(leg, mile - leg_start)
        base = (baked if baked is not None
                else corridor_speed_limit(leg.highway, self._region_at(mile)))
        if self._near_city(mile):
            return min(base, URBAN_LIMIT_MPH)
        return base

    def next_zone_within(self, within_mi: float) -> Zone | None:
        """The nearest speed zone whose start lies ahead within the distance."""
        ahead = [z for z in self.zones
                 if 0 < z.start_mi - self.position_mi <= within_mi]
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
        next_context = self.next_navigation_context(imperial)
        terrain = self.terrain_at()
        terrain_text = "Grade level" if terrain == "flat" else f"Terrain {terrain}"
        return (f"{dist}. On {leg.highway} toward {toward}, {state}. "
                f"{terrain_text}. {next_context}")

    def next_navigation_context(self, imperial: bool = True) -> str:
        cue = self.next_navigation_cue()
        if cue is None:
            return f"Destination {self.route.cities[-1]} ahead."
        ahead = max(0.0, cue.at_mi - self.position_mi)
        ahead_text = (
            f"{ahead:.0f} miles" if imperial
            else f"{ahead * 1.609344:.0f} kilometers"
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
                    f"{cue.speed_mph:.0f} miles per hour" if imperial
                    else f"{cue.speed_mph * 1.609344:.0f} kilometers per hour"
                )
            return f"Traffic in {ahead_text}: {cue.text}{speed}."
        if cue.kind == "toll":
            return f"Toll point in {ahead_text}: {cue.text}."
        return f"Next guidance in {ahead_text}: {cue.text}."

    def next_navigation_cue(self) -> NavigationCue | None:
        for cue in self.navigation_cues:
            if (
                cue.at_mi > self.position_mi + 0.05
                and cue.kind not in ("continue", "interchange")
            ):
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
        for i, (start, leg) in enumerate(zip(self._leg_starts, self.route.legs,
                                             strict=True)):
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
        by_name = {
            toll.name: toll
            for leg in self.route.legs
            for toll in leg.toll_events
        }
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
        self._check_speed_limit()
        self._check_stops()
        self._check_navigation_cues()
        self._check_tolls()
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

    def _zone_warning_lookahead_mi(self) -> float:
        """Lead distance for a zone warning, scaled so the player gets roughly
        ``ZONE_WARNING_REAL_S`` of real time despite speed and time compression."""
        speed = max(self.truck.speed_mph, 30.0)
        miles = ZONE_WARNING_REAL_S * speed * self.time_scale / 3600.0
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
                self._emit(TripEventKind.ZONE_ENTER,
                           f"{zone.reason} ahead. "
                           f"Speed limit {self._speed_value(zone.limit_mph)}.",
                           zone=zone)
            elif self._active_zone is not None:
                self._construction_zone_grace_start.pop(
                    _zone_key(self._active_zone), None)
                resumed = self._corridor_limit_at(self.position_mi)
                self._announced_speed_limit = resumed
                self._emit(TripEventKind.ZONE_EXIT,
                           f"End of {self._active_zone.reason} zone. "
                           f"Speed limit {self._speed_value(resumed)}.")
            self._active_zone = zone

    def _check_speed_limit(self) -> None:
        """Announce a changed posted limit on the open road (signs at a region
        or urban boundary). While a zone is active the zone owns the spoken
        limit, so this stays quiet until the zone clears."""
        if self._active_zone is not None:
            return
        limit = self._corridor_limit_at(self.position_mi)
        if self._announced_speed_limit is None:
            self._announced_speed_limit = limit   # seed at departure, no cue
            return
        if limit != self._announced_speed_limit:
            lowered = limit < self._announced_speed_limit
            self._announced_speed_limit = limit
            verb = "reduced to" if lowered else "raised to"
            city = self._nearest_urban_city(self.position_mi) if lowered else None
            where = f" approaching {city}" if city else ""
            self._emit(TripEventKind.GPS_CUE,
                       f"Speed limit {verb} {self._speed_value(limit)}{where}.")

    def _check_stops(self) -> None:
        for stop in self.stops:
            ahead = stop.at_mi - self.position_mi
            if 0 < ahead <= 5.0 and stop.name not in self._announced_stops:
                self._announced_stops.add(stop.name)
                exit_part = f" at {stop.exit_label}" if stop.exit_label else ""
                self._emit(TripEventKind.STOP_AHEAD,
                           f"{stop.spoken_name}{exit_part} in "
                           f"{self._distance_text(ahead)}. "
                           f"{stop.parking_text}. "
                           "Press X to take the exit for it.",
                           stop=stop)

    def _check_navigation_cues(self) -> None:
        for cue in self.navigation_cues:
            ahead = cue.at_mi - self.position_mi
            if cue.kind == "interchange":
                continue
            if cue.kind in ("continue", "onramp"):
                key = f"{cue.key}:near"
                if -0.5 <= ahead <= 0.5 and key not in self._announced_navigation:
                    self._announced_navigation.add(key)
                    self._emit(TripEventKind.GPS_CUE, cue.near_text or cue.text,
                               cue=cue)
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
                    speed = (f" at {cue.speed_mph:.0f} miles per hour"
                             if cue.speed_mph is not None else "")
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
            lookahead = (
                STATE_CROSSING_WARNING_LOOKAHEAD_MI
                if cue.kind == "state_crossing" else 2.0
            )
            if 0 < ahead <= lookahead and advance_key not in self._announced_navigation:
                self._announced_navigation.add(advance_key)
                message = f"In {self._distance_text(ahead)}, {cue.text}."
                self._emit(TripEventKind.GPS_CUE, message, cue=cue)
            if -0.1 <= ahead <= 0.1 and near_key not in self._announced_navigation:
                self._announced_navigation.add(near_key)
                if cue.kind == "state_crossing":
                    self._emit(TripEventKind.STATE_CROSSING, cue.near_text, cue=cue)
                elif cue.kind == "checkpoint":
                    self._emit(TripEventKind.CHECKPOINT, cue.near_text, cue=cue)
                else:
                    self._emit(TripEventKind.GPS_CUE, cue.near_text, cue=cue)

    def _check_tolls(self) -> None:
        for i, (start, leg) in enumerate(zip(self._leg_starts, self.route.legs,
                                             strict=True)):
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
                crossing = (f"Crossing into {city_state}. "
                            if city_state != prev_state else "")
                self._emit(TripEventKind.CITY_REACHED,
                           f"{crossing}Passing {city}, {city_state}. "
                           f"Continuing on {leg.highway} toward {nxt}.")

    def _hazard_risk(self) -> float:
        """Chance of a hazard at each check; worse in fog and after dark.

        Scaled by ``hazard_scale`` so relaxed mode keeps hazards rare while
        weather and night still make the hazards that do occur likelier.
        """
        vis = self.weather.effects.visibility_mi
        risk = 0.25 + (0.25 if vis < 2 else 0.0)
        if is_night(self.current_hour):
            risk += NIGHT_HAZARD_BONUS
        return risk * self.hazard_scale

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
                self.current_region, self.weather.current,
                self.terrain_at(self.position_mi), self.current_hour)
            if not choices:
                return
            texts, weights = zip(*choices, strict=True)
            hazard = self._rng.choices(texts, weights)[0]
            # Lead with the action: the player can be on the brakes before
            # the sentence finishes. deadline_s is the reaction slack on top
            # of the braking time the driving state computes from speed.
            self._emit(TripEventKind.HAZARD,
                       f"Brake now! {hazard[0].upper()}{hazard[1:]}.",
                       deadline_s=self._rng.uniform(3.0, 4.5))

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
                grace_start = self._construction_zone_grace_start.get(zone_key, active_zone.start_mi)
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


def _stop_offset_for_direction(at_mi: float, leg_miles: float, forward: bool) -> float:
    return at_mi if forward else leg_miles - at_mi


def _leg_heading(highway: str, from_city: str, to_city: str) -> str:
    """Signed heading for onramp/merge framing ("Merge onto I-95 South...").

    Uses the US route-numbering convention -- odd routes are signed
    north/south, even routes east/west -- so the spoken direction matches real
    signage even where a leg runs diagonally (I-95 NY->Philadelphia is signed
    South though the geometry trends southwest). The sign comes from the
    endpoints' coordinates on the route's primary axis. Empty when the highway
    has no number or a city lacks coordinates."""
    match = re.search(r"\d+", highway)
    if not match:
        return ""
    cities = get_world().cities
    a, b = cities.get(from_city), cities.get(to_city)
    if a is None or b is None or (a.lat == 0.0 and a.lon == 0.0):
        return ""
    if int(match.group()) % 2 == 1:   # odd -> north/south route
        return "North" if b.lat >= a.lat else "South"
    return "East" if b.lon >= a.lon else "West"   # even -> east/west route


def _nearest_exit_label(leg, at_mi: float, tol_mi: float = 2.0) -> str:
    """Signed exit label of the interchange nearest a stop on the same leg, in
    the leg's native (a->b) frame. Empty when none is within ``tol_mi`` or the
    nearest junction carries no exit number -- stops then keep generic wording."""
    best_label = ""
    best_dist = tol_mi
    for ix in leg.interchanges:
        dist = abs(ix.at_mi - at_mi)
        if dist <= best_dist and ix.exit_label:
            best_dist = dist
            best_label = ix.exit_label
    return best_label


def _zone_key(zone: Zone) -> str:
    return f"{zone.reason}:{zone.start_mi:.3f}:{zone.end_mi:.3f}:{zone.limit_mph:.0f}"


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
