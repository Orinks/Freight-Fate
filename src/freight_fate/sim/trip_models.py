# ruff: noqa: F401,F403,F405
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from enum import Enum

from ..data.world import STOP_TYPE_LABELS, Leg, TollEvent
from .hos import is_night, time_of_day
from .timezones import TimeZone
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
URBAN_RADIUS_MI = 6.0  # urban speed reduction within this distance of a city
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
    "upper_midwest": 70.0,
    "corn_belt": 70.0,
    "mid_south": 70.0,
    "atlantic_southeast": 70.0,
    "florida": 70.0,
    "appalachia": 70.0,
    "pacific_northwest": 70.0,
    "northeast": 65.0,
    "california": 65.0,
}

# States where heavy trucks have a lower maximum open-road limit than the
# general posted limit commonly tagged in OSM. Source checked against Trucker
# Country's state speed-limit table, accessed 2026-06-30.
STATE_TRUCK_MAX_MPH: dict[str, float] = {
    "Arkansas": 70.0,
    "California": 55.0,
    "Idaho": 70.0,
    "Indiana": 65.0,
    "Michigan": 65.0,
    "Montana": 70.0,
    "Nevada": 75.0,
    "North Dakota": 75.0,
    "Oregon": 65.0,
    "Washington": 60.0,
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


def _leg_state_at(leg: Leg, offset_mi: float) -> str:
    """State in effect at a leg-relative offset in the leg's A-to-B direction."""
    if not leg.state_crossings:
        return leg.state_miles[0].state if len(leg.state_miles) == 1 else ""
    state = leg.state_crossings[0].from_state
    for crossing in leg.state_crossings:
        if crossing.at_mi <= offset_mi:
            state = crossing.state
        else:
            break
    return state


def _truck_capped_speed_limit(leg: Leg, offset_mi: float) -> float | None:
    samples = leg.speed_limits
    if not samples:
        return None
    chosen = samples[0]
    for sample in samples:
        if sample.at_mi <= offset_mi:
            chosen = sample
        else:
            break
    cap = STATE_TRUCK_MAX_MPH.get(_leg_state_at(leg, offset_mi))
    return min(chosen.mph, cap) if cap is not None else chosen.mph


FACILITY_ACCESS_LIMIT_MPH = 25.0
DESTINATION_APPROACH_LIMIT_MPH = 35.0
FACILITY_GATE_LIMIT_MPH = 15.0
DESTINATION_APPROACH_ZONE_MI = 3.0
FACILITY_GATE_ZONE_MI = 0.5
NIGHT_HAZARD_BONUS = 0.10  # extra hazard risk after dark
# A zone flip that flips back within this distance is boundary noise from a
# road hugging the line (the state-crossing dwell filter's lesson), not a
# crossing the driver should reset a watch for.
TIMEZONE_DWELL_MI = 10.0
NIGHT_TRAFFIC_KEEP = 0.4  # chance a traffic zone still forms at night
# Open road guaranteed between generated slow zones: without it, independent
# placement could drop one construction zone inside another, or chain them
# back to back with no gap (player-reported on the 2026-07-09 snapshot).
ZONE_MIN_GAP_MI = 8.0
TRAFFIC_LOOKAHEAD_MI = 2.5
TRAFFIC_WARNING_GAP_S = 2.2
ZONE_WARNING_LOOKAHEAD_MI = 2.0  # minimum distance heads-up for a zone
# Distance compression (time_scale) and speed eat into how much *real* time a
# fixed-distance warning gives -- 2 miles at 70 mph and 20x is only ~5 seconds.
# Scale the lead distance with speed and pacing for a roughly constant real-time
# heads-up, clamped between the base distance and a sane maximum.
ZONE_WARNING_REAL_S = 12.0  # target real seconds of warning
ZONE_WARNING_MAX_MI = 8.0
# Truck dynamics run in real time so shifting and braking stay playable, but
# the clock bills every real second at the pacing multiplier -- which made the
# couple of real minutes a loaded rig needs to reach highway speed cost most of
# a game hour. Compression now ramps with road speed: near real-time pacing
# while maneuvering, the full configured scale once at cruise. Distance, fuel,
# and the HOS clock all share the effective value, so the sim stays coherent.
LOW_SPEED_TIME_SCALE = 4.0  # clock multiplier when stopped or crawling
FULL_COMPRESSION_MPH = 50.0  # road speed where full pacing resumes
# Setting the parking brake says "I'm staying put": nothing needs real-time
# reactions, so waiting runs at double the configured pacing -- weather,
# daylight, and dock time pass without dropping into real time, and each
# pacing setting keeps its relative feel (relaxed 20x, standard 40x, fast
# 80x). Releasing the brake returns to the speed ramp instantly.
PARKED_TIME_SCALE_MULT = 2.0
CONSTRUCTION_ENFORCEMENT_GRACE_MI = 1.0
# Driving faster than the weather's safe speed risks a traction-loss incident,
# so the safe-speed readout has teeth. Risk scales with how far over you are and
# how little grip the conditions leave; only adverse grip counts.
CONDITIONS_SPEED_MARGIN_MPH = 8.0  # slack over the safe speed before any risk
CONDITIONS_GRIP_CEILING = 0.85  # only weather this slick can spin you out
CONDITIONS_CHECK_MI = 1.5  # mileage between incident rolls while overspeed
CONDITIONS_INCIDENT_RISK = 0.5  # peak per-roll chance at full severity

# Road hazards are grounded in what actually puts a tractor-trailer on the
# brakes on an interstate, and in *where and when* it happens. Each hazard is
# tagged with the conditions under which it is plausible; a hazard is only ever
# drawn when the current region, weather, terrain, and time of day all allow
# it. This replaces an earlier flat region pool that could, say, announce farm
# equipment merging onto a freeway or a dust devil on a clear calm day.

# Patrol density by region: dense, urbanized states run hot; wide-open country
# runs cold. Regions not listed sit at the neutral baseline.
_HOT_PATROL_REGIONS = (
    "northeast",
    "california",
    "great_lakes",
    "florida",
    "atlantic_southeast",
    "mid_south",
)
_COLD_PATROL_REGIONS = (
    "great_basin",
    "southern_plains",
    "rockies",
    "desert_southwest",
    "heartland",
)

# Open, exposed country where high wind genuinely shoves a loaded trailer.
_CROSSWIND_REGIONS = ("southern_plains", "heartland", "great_basin", "desert_southwest", "rockies")
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
    HazardDef(
        "a deer crossing the road",
        1.3,
        animal=True,
        regions=(
            "northeast",
            "appalachia",
            "great_lakes",
            "upper_midwest",
            "corn_belt",
            "heartland",
            "mid_south",
            "atlantic_southeast",
            "southern_plains",
            "gulf_coast",
            "florida",
            "california",
        ),
    ),
    HazardDef(
        "an elk crossing the road",
        1.1,
        animal=True,
        regions=("rockies", "great_basin", "pacific_northwest"),
    ),
    HazardDef("an animal on the road", 0.7, animal=True),  # generic fallback
    # Wet weather only.
    HazardDef("standing water flooding the lane", 1.1, weather=_WET),
    HazardDef("the trailer hydroplaning on standing water", 1.0, weather=_HEAVY_WET),
    HazardDef(
        "hail hammering the windshield",
        0.7,
        weather=(WeatherKind.THUNDERSTORM,),
        regions=(
            "southern_plains",
            "heartland",
            "corn_belt",
            "mid_south",
            "rockies",
            "great_lakes",
        ),
    ),
    # Snow and ice only.
    HazardDef("a snow squall whiting out the lane", 1.0, weather=(WeatherKind.SNOW,)),
    HazardDef("ice on the bridge deck", 1.0, weather=(WeatherKind.SNOW,)),
    HazardDef(
        "black ice on the shaded grade",
        1.1,
        weather=(WeatherKind.SNOW,),
        terrain=("mountain", "hills"),
    ),
    # Dense fog only.
    HazardDef("brake lights looming in dense fog", 1.2, weather=(WeatherKind.FOG,)),
    # High wind: crosswind shove and blowing debris in open country.
    HazardDef(
        "a crosswind gust shoving the trailer",
        1.2,
        weather=(WeatherKind.WIND,),
        regions=_CROSSWIND_REGIONS,
    ),
    HazardDef(
        "a dust storm dropping visibility",
        0.9,
        weather=(WeatherKind.WIND,),
        regions=("desert_southwest", "southern_plains", "great_basin"),
    ),
    HazardDef(
        "tumbleweeds piling in your lane",
        0.5,
        weather=(WeatherKind.WIND,),
        regions=("desert_southwest", "great_basin", "southern_plains"),
    ),
    # Mountain terrain only.
    HazardDef(
        "rockfall debris on the road",
        1.0,
        terrain=("mountain",),
        regions=("rockies", "appalachia", "great_basin", "pacific_northwest", "california"),
    ),
    HazardDef("a runaway truck on the grade ahead", 0.8, terrain=("mountain",)),
)


def eligible_hazards(
    region: str, weather: WeatherKind, terrain: str, game_hours: float
) -> list[tuple[str, float]]:
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
    TIMEZONE_CROSSING = "timezone_crossing"
    CHECKPOINT = "checkpoint"
    TOLL_CHARGED = "toll_charged"
    ARRIVED = "arrived"


@dataclass
class TripEvent:
    kind: TripEventKind
    message: str
    data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TimezoneCrossing:
    """The trip milepost where the route passes into another time zone."""

    at_mi: float
    from_zone: TimeZone
    to_zone: TimeZone


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
    exit_label: str = ""  # "exit 7" when a real OSM interchange sits here

    @property
    def key(self) -> str:
        """Identity of this stop on this route, for tracking rather than speech.

        Names repeat constantly -- a coast-to-coast route carries six stops
        called "Love's Travel Stop" -- so anything that remembers *which* stop
        (announced already, planned, exit in progress) has to key on the
        milepost too, or one stop stands in for all its namesakes.
        """
        return f"{self.at_mi:.2f}:{self.name}"

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
            "likely": "",
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


__all__ = [name for name in globals() if not name.startswith("__")]
