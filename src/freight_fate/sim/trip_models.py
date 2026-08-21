# ruff: noqa: F401,F403,F405
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from enum import Enum

from ..data.world import (
    DEFAULT_VEHICLE_ACCESS,
    STOP_TYPE_LABELS,
    Leg,
    SpeedLimitSample,
    TollEvent,
    vehicle_access_allows,
)
from ..data.world_constants import FACILITY_APPROACH_TRUSTED_MAX_MI
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

# Jurisdictions whose statute holds heavy trucks below the general posted
# limit. Keyed by road class (from _highway_class) with a "default" fallback,
# because several splits are class-scoped and a flat number cannot say so.
# "max" is the highest truck speed the statute permits ANYWHERE in the state;
# it bounds how far a baked maxspeed:hgv tag may raise the limit (see
# _truck_capped_speed_limit). Omit "max" and it is inferred from the entries.
#
# Every entry verified against statute text 2026-07-19, replacing an aggregator
# table that proved wrong on 4 of its 10 rows. Full audit, per-state sources,
# and the states checked and found to have NO split are recorded in
# docs/truck-speed-limit-audit.md. DO NOT edit a number here without a citation
# and an access date -- the game speaks the state's name aloud when this table
# binds, so a stale row is the game attributing a false law to a real place.
STATE_TRUCK_MAX_MPH: dict[str, dict[str, float]] = {
    # A.R.S. 28-709: >26,000 lb declared GW, statewide. The general limit is 75
    # on rural interstates, so this binds hard and was MISSING before the audit
    # -- 33 Arizona legs were serving the car number.
    "Arizona": {"default": 65.0},
    # Ark. Code 27-51-201(b): CMV >=26,001 lb GVWR on rural divided
    # controlled-access highways.
    # NOTE: 27-51-201(c)(2) (Act 784 of 2019) reads 50 mph for trucks "in other
    # locations", i.e. every non-controlled-access road. Deliberately NOT
    # encoded: it uses a different vehicle test than (b), and it contradicts
    # observed practice on Arkansas US routes posted 65 for all traffic. The
    # audit could not resolve whether enforcement is discretionary or the
    # posted-limit path in (b)(3) supersedes. A 20 mph drop spoken with the
    # state's name attached needs better ground truth than a statute read cold
    # -- ask a driver who runs Arkansas.
    "Arkansas": {"default": 70.0},
    # CVC 22406: three or more axles, or any vehicle towing. Statewide, every
    # highway -- the widest split in the country, and the one players report as
    # a bug because the sign says 65.
    "California": {"default": 55.0},
    # IC 9-21-5-2(a)(4): declared GVW >26,000 lb, buses excluded. Rural
    # interstates and the Toll Road.
    "Indiana": {"default": 65.0},
    # MCL 257.627(4): GVW >=10,000 lb or any truck-tractor, on freeways and
    # state trunk lines.
    "Michigan": {"default": 65.0},
    # MCA 61-8-312: >1 ton rated capacity. 70 on interstates, 65 on all other
    # public highways -- a clean, sourced class split, and the reason this
    # table is keyed by class at all.
    "Montana": {"interstate": 70.0, "default": 65.0},
    # ORS 811.111(1)(b): >10,000 lb GVWR. 55 on ANY highway by default; 60 and
    # 65 are named-corridor exceptions in eastern Oregon (I-84 east, I-82,
    # US-95), which OSM already carries as maxspeed:hgv on 144 samples. Rather
    # than maintain a corridor list, the default holds I-5 at 55 and "max"
    # lets those tagged corridors run their real 65.
    "Oregon": {"default": 55.0, "max": 65.0},
    # RCW 46.61.410: >10,000 lb GVW and all combinations, statewide, while the
    # general limit may be posted as high as 75.
    "Washington": {"default": 60.0},
}
# Removed by the 2026-07-19 audit, each with a reason:
#   Idaho 70    -- REPEALED. Idaho Code 49-654(3) as amended by H664 (2026
#                  ch. 108, effective 2026-07-01) gives 5+ axle heavy vehicles
#                  the same limits as light vehicles.
#   Nevada 75   -- no split ever existed. NRS 484B.600 caps everyone at 80.
#   N. Dakota 75-- no split. NDCC 39-09-02(1)(i) is 80 for all traffic.
# Deliberately absent (real splits the state-keyed table must not flatten):
#   Illinois    -- 60/55 for >=8,001 lb, but ONLY in six Chicago-area counties.
#                  No county data is baked; approximating that boundary would
#                  be inventing a legal line, and this one gets enforced.
#   Virginia    -- a real 45/55 split, but on SECONDARY roads only. A flat
#                  entry would cap trucks at 45 on I-81.


def leg_lane_count(leg: Leg | None) -> int:
    """Driving lanes per direction on a leg, defaulting to a two-lane rural
    interstate. Honors a baked ``lanes`` field once OSM enrichment adds one."""
    if leg is None:
        return DEFAULT_LEG_LANES
    return max(1, int(getattr(leg, "lanes", 0) or DEFAULT_LEG_LANES))


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
    first sample, the first sample applies. A sample with ``mph`` of ``None``
    is a coverage-gap marker -- OSM tagging ends there, so the answer is
    ``None`` (fall back to the highway/region heuristic) rather than holding
    a stale town posting across miles of untagged highway."""
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


def _posted_sample_at(leg: Leg, offset_mi: float) -> SpeedLimitSample | None:
    """The last posting at or before a leg offset, or None where none is baked."""
    samples = leg.speed_limits
    if not samples:
        return None
    chosen = samples[0]
    for sample in samples:
        if sample.at_mi <= offset_mi:
            chosen = sample
        else:
            break
    return chosen


def _statutory_truck_caps(state: str, highway: str) -> tuple[float, float] | None:
    """(cap for this road class, highest cap the state permits anywhere), or
    None where the state holds trucks to the general limit."""
    table = STATE_TRUCK_MAX_MPH.get(state)
    if not table:
        return None
    classed = {k: v for k, v in table.items() if k != "max"}
    cap = classed.get(_highway_class(highway), classed.get("default"))
    if cap is None:
        return None
    # "max" defaults to this class's own cap, NOT the highest entry in the
    # table: a class-scoped split (Montana's 70 interstate / 65 elsewhere) must
    # not let a stray hgv tag license the interstate number on a back highway.
    # Only a state whose statute has genuine corridor exceptions above its
    # default -- Oregon -- declares "max" and opens that door.
    return cap, table.get("max", cap)


def _truck_capped_speed_limit(leg: Leg, offset_mi: float) -> float | None:
    chosen = _posted_sample_at(leg, offset_mi)
    if chosen is None or chosen.mph is None:
        # Inside a coverage gap: no posting is known here, so the caller's
        # highway/region heuristic answers, not the last town limit.
        return None
    caps = _statutory_truck_caps(_leg_state_at(leg, offset_mi), leg.highway)
    if caps is None:
        return chosen.mph
    cap, permitted = caps
    if chosen.hgv:
        # An explicit maxspeed:hgv is better evidence than a statewide default
        # -- it is how Oregon's eastern corridors carry their real 65 while
        # I-5 stays 55 -- but it is trusted only as far as the statute allows.
        # A stray tag CANNOT license an illegal speed: I-5 in California
        # carries a 60 mph hgv tag eleven miles south of the Oregon line, and
        # honouring it would have the game telling a driver they may do 60
        # where CVC 22406 says 55.
        return min(chosen.mph, permitted)
    return min(chosen.mph, cap)


def truck_limit_at(leg: Leg, offset_mi: float) -> tuple[bool, str | None]:
    """Whether the limit in force here is truck-specific, and the state to
    credit for it. ``(False, None)`` where the posting is simply the posting.

    Split-limit states are the most reported "wrong speed limit" in the map
    (California, 2026-07-19): the driver remembers a 65 shield and hears 55,
    because 65 is the car number and CVC 22406 caps three-axle rigs at 55. The
    data was right and said so silently, which is why it read as a bug.

    A stretch reaches 55 by either of two routes, and the driver must not be
    able to tell them apart: OSM carries an explicit ``maxspeed:hgv`` (US-395,
    the reported road) or it carries only the car number and the statutory cap
    pulls it down (I-80). Keying off the cap alone would stay silent on
    exactly the tagged roads, so the same 55 would explain itself on one mile
    and not the next."""
    chosen = _posted_sample_at(leg, offset_mi)
    if chosen is None or chosen.mph is None:
        return False, None
    state = _leg_state_at(leg, offset_mi)
    caps = _statutory_truck_caps(state, leg.highway)
    if caps is not None and caps[0] < chosen.mph:
        return True, state
    if chosen.hgv:
        # Tagged truck-specific. Credit the state only where it actually has a
        # statutory split; a one-off local truck posting is still a truck limit
        # but not the state's doing.
        return True, state if caps is not None else None
    return False, None


# A city's truck stops are baked onto every leg that meets that city, a mile
# out from the endpoint, so a route driving *through* the city collects the
# same facility twice -- a mile before and a mile after, exactly two miles
# apart. Same-name stops closer together than this are that one facility.
# Measured across eight coast-to-coast routes: every same-name pair within
# twelve miles was exactly 2.00, so this has wide margin either way.
SHARED_CITY_STOP_MERGE_MI = 3.0

FACILITY_ACCESS_LIMIT_MPH = 25.0
# Graduated synthetic approach: the wide-out portion of a long local
# approach is an arterial, not an access road (owner, 2026-07-24).
FACILITY_ARTERIAL_LIMIT_MPH = 45.0
FACILITY_ACCESS_TAIL_MI = 2.0
# The speed at or below which an off-ramp can actually be taken, and so the
# floor for anything the arrival zones cap. Defined here, in the portable
# layer, because both the zone builder and the driving state need the same
# number: ``states/driving_core`` imports it as ``RAMP_MAX_MPH``.
RAMP_MAX_MPH = 45.0
# The destination approach never caps below the speed the ramp needs. It used
# to be a flat 35 over the last three miles, which put a step change on the
# road a mile or two before the exit and dragged the truck down to a crawl
# while it was still on the freeway (tester report, Shane, 2026-08-15).
DESTINATION_APPROACH_LIMIT_MPH = RAMP_MAX_MPH
# ASSUMED, and it cannot be otherwise. The street outside takes its number
# from the state vehicle code (see data/street_limits.py, which cites the
# section for each state), but no vehicle code reaches inside a private
# facility: a yard's own road is the owner's to sign, and real distribution
# centers post anywhere from 5 to 15. So this is the game's number, chosen at
# the top of that observed range because it has to be slow enough to make the
# entrance and fast enough not to be a crawl -- not a limit anybody
# legislated. Labeled here rather than left looking like the statutory
# figures it now sits next to.
FACILITY_GATE_LIMIT_MPH = 15.0
FACILITY_GATE_ZONE_MI = 0.5
# ...but never more than this share of the approach. A gate zone longer
# than the road it sits on is how a blanket 15 came to override every
# 25 street on a quarter of all facility chains.
FACILITY_GATE_MAX_SHARE = 0.35
# Local approach road assumed when the destination facility has no usable
# approach record -- the stretch between the exit and the gate. Kept equal to
# the exit's own placement (``DESTINATION_EXIT_BEFORE_END_MI``), which imports
# it, so the synthetic approach and the synthetic exit describe one road.
DESTINATION_LOCAL_APPROACH_MI = 1.0
# The same ceiling the world's own approach lookup applies, kept here too
# because a Trip can be handed a mileage by a tool or a test that never went
# through that lookup.
DESTINATION_APPROACH_TRUSTED_MAX_MI = FACILITY_APPROACH_TRUSTED_MAX_MI

# -- How a loaded truck sheds speed for something ahead ------------------------
# One budget, shared by the arrival zones here and by the keeper's ease in
# ``states/driving_speed_control`` (which imports these): a comfortable rate the
# truck genuinely delivers on light brake, seconds spent hearing the call and
# getting to the pedal before any slowing starts, and a settling tail so the
# number is reached ahead of the point rather than exactly on it.
APPROACH_DECEL_MPS2 = 0.4
APPROACH_REACTION_S = 6.0
APPROACH_SETTLE_S = 2.0
MPH_PER_MPS = 2.23694
METERS_PER_MILE = 1609.344


def approach_shed_mi(from_mph: float, to_mph: float) -> float:
    """Road a loaded truck needs to come down from one speed to another.

    In route miles on the clock the road is measured in, so a zone built from
    it starts where a driver would really begin slowing. The seconds of the
    shed are priced at the speed the truck is doing through them -- the mean of
    the two ends -- while the reaction budget is priced at the speed it comes
    in at and the settling tail at the number it leaves on, exactly as
    ``_keeper_ease_mi`` prices the same three pieces."""
    if to_mph >= from_mph:
        return 0.0
    shed_s = (from_mph - to_mph) / MPH_PER_MPS / APPROACH_DECEL_MPS2
    shed_mi = shed_s * (from_mph + to_mph) / 2.0 / 3600.0
    return shed_mi + (APPROACH_REACTION_S * from_mph + APPROACH_SETTLE_S * to_mph) / 3600.0


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
RUSH_HOUR_WINDOWS = ((6.5, 9.0), (16.0, 18.5))
# -- Grounded congestion -------------------------------------------------------------
# Congestion comes from traffic volume against capacity, not a dice roll.
# Volume is FHWA HPMS AADT baked per leg where available (Leg.traffic_volumes)
# with a class/metro heuristic backstop; the hourly share of daily traffic
# follows the standard commuter shape (AM and PM weekday peaks, a flat
# late-morning weekend hump, near-empty small hours). Capacity is the
# textbook ~2,000 vehicles per hour per lane. The volume-to-capacity ratio
# then gates whether a traffic-prone stretch is actually jammed *right now*:
# metro stretches jam at rush hour and flow free at midnight.
LANE_CAPACITY_VPH = 2000.0  # per lane, per direction
DIRECTIONAL_SPLIT = 0.55  # peak-direction share of two-way volume
CONGESTION_MIN_RATIO = 0.72  # volume/capacity where slowdowns begin
CONGESTION_HEAVY_RATIO = 0.9  # dense, clearly slowed traffic
CONGESTION_JAM_RATIO = 1.05  # demand over capacity: stop and go
CONGESTION_SAMPLE_MI = 1.0  # stride when scanning a route for jam-prone stretches
CONGESTION_MIN_ZONE_MI = 1.0  # ignore blips shorter than this
CONGESTION_JOIN_GAP_MI = 2.0  # merge prone stretches separated by less

# Hourly share of daily traffic (indexed by clock hour). Sums to ~1.0.
# Shape follows FHWA/state-DOT urban hourly distributions: weekday twin
# peaks near 7-8 AM and 4-6 PM; weekends flatter with a midday hump.
# fmt: off
HOURLY_SHARE_WEEKDAY = (
    0.008, 0.005, 0.004, 0.005, 0.010, 0.025,  # 0-5
    0.050, 0.072, 0.068, 0.052, 0.048, 0.050,  # 6-11
    0.053, 0.054, 0.058, 0.068, 0.078, 0.080,  # 12-17
    0.062, 0.045, 0.035, 0.028, 0.022, 0.014,  # 18-23
)
HOURLY_SHARE_WEEKEND = (
    0.014, 0.010, 0.007, 0.006, 0.007, 0.012,  # 0-5
    0.024, 0.035, 0.048, 0.065, 0.073, 0.077,  # 6-11
    0.077, 0.075, 0.073, 0.071, 0.067, 0.060,  # 12-17
    0.052, 0.044, 0.037, 0.030, 0.023, 0.016,  # 18-23
)
# fmt: on

# Heuristic AADT for legs with no baked HPMS profile: typical two-way
# volumes by highway class, lifted near metros. Rural interstates run in
# the tens of thousands; urban interstates several times that.
HEURISTIC_AADT = {
    "interstate": (26000.0, 92000.0),  # (rural, near-metro)
    "us_highway": (11000.0, 34000.0),
    "state_route": (7000.0, 20000.0),
}


def hourly_volume_fraction(hour: float, weekend: bool) -> float:
    """Share of the day's traffic moving in this clock hour."""
    table = HOURLY_SHARE_WEEKEND if weekend else HOURLY_SHARE_WEEKDAY
    return table[int(hour) % 24]


def congestion_ratio(aadt: float, hour: float, lanes: int, weekend: bool) -> float:
    """Peak-direction volume-to-capacity ratio for an hour of the day."""
    vph = aadt * hourly_volume_fraction(hour, weekend) * DIRECTIONAL_SPLIT
    return vph / (max(1, lanes) * LANE_CAPACITY_VPH)


def congestion_limit_mph(ratio: float, posted: float) -> float | None:
    """Prevailing traffic speed for a volume-to-capacity ratio, or ``None``
    when traffic still moves at the posted limit."""
    if ratio < CONGESTION_MIN_RATIO:
        return None
    if ratio < CONGESTION_HEAVY_RATIO:
        return max(45.0, min(posted, posted - 12.0))
    if ratio < CONGESTION_JAM_RATIO:
        return 38.0
    return 26.0


def leg_aadt_at(leg: Leg, offset_mi: float) -> tuple[float, int] | None:
    """Baked (AADT, per-direction lanes) at a leg-relative offset, or ``None``
    when the leg carries no HPMS profile. Step function like speed limits."""
    samples = leg.traffic_volumes
    if not samples:
        return None
    chosen = samples[0]
    for sample in samples:
        if sample.at_mi <= offset_mi:
            chosen = sample
        else:
            break
    return chosen.aadt, chosen.lanes


def heuristic_aadt(highway: str, near_city: bool) -> float:
    rural, metro = HEURISTIC_AADT.get(_highway_class(highway), HEURISTIC_AADT["state_route"])
    return metro if near_city else rural


# Lanes: chance a construction zone actually closes one side of the road
# (most interstate work zones do), and the per-direction lane count. The
# count is a Phase-1 default; an OSM ``lanes=`` enrichment pass can bake a
# real per-leg count onto ``Leg`` later and ``leg_lane_count`` will use it.
CONSTRUCTION_CLOSURE_CHANCE = 0.65
DEFAULT_LEG_LANES = 2
# The most lanes per direction the game can put a driver in, and it is a
# SPEECH limit before it is a driving one: ``lane.lane_label`` has exactly
# three names -- right, left, middle -- so on a road of four or more every
# interior lane is announced as "the middle lane" and a player working by
# ear cannot tell which one they are in, or which one just came open. Real
# HPMS counts run to six on urban freeways and the bake records them
# honestly; this clamps what the DRIVER is offered, not what the road is
# recorded as carrying. Traffic capacity still divides by the real count
# (``leg_aadt_at``), because how much road there is for traffic and how many
# lanes the player can occupy are different questions -- clamping the
# capacity too would invent jams on freeways that flow.
MAX_DRIVABLE_LANES = 3
TRAFFIC_LOOKAHEAD_MI = 2.5
TRAFFIC_WARNING_GAP_S = 2.2
TRAFFIC_PRESSURE_LOOKAHEAD_MI = 2.5
TRAFFIC_PRESSURE_MIN_INTENSITY = 0.12
CONSTRUCTION_TAPER_MI = 1.0
CONSTRUCTION_TAPER_LIMIT_MPH = 55.0
# One signed roadwork footprint is both zones: the work itself and the merge
# taper that leads into it. Enforcement treats the pair as one place (see
# Trip.in_construction_zone) because the cones, the crew and the doubled-fine
# sign all start at the taper, not at the first barrel.
CONSTRUCTION_ZONE_REASONS = frozenset({"construction", "construction merge"})
# How finely a work zone footprint is sampled before a lane may be coned off.
# Baked lane runs shorter than this are already collapsed for the spoken lane
# callouts (LANE_RUN_MIN_MI), so a quarter mile resolves every stretch a
# driver is told about.
LANE_CLOSURE_SAMPLE_MI = 0.25
CORRIDOR_HAZARD_MIN_FACTOR = 0.75
CORRIDOR_HAZARD_MAX_FACTOR = 1.45
CB_PATROL_LOOKAHEAD_MI = 5.0  # floor for the enforcement lead, never the whole answer
# Enforcement cues get the same real-time treatment zone warnings already get
# (ZONE_WARNING_REAL_S below). A fixed five miles is 13.8 real seconds at
# relaxed pacing and 6.9 at standard, and the CB call itself takes about
# seven seconds to speak -- so at the faster pacing the player used to pass
# the post mid-sentence. (It was 3.5 seconds at the retired Realistic 40x,
# which is where the problem was first seen.)
ENFORCEMENT_WARNING_REAL_S = 18.0
ENFORCEMENT_WARNING_MAX_MI = 12.0
# An open scale costs money and time, so its call gets a longer lead than a
# heads-up does.
SCALE_WARNING_REAL_S = 20.0
# Spoken enforcement lines are capped for a whole run. Presence is carried by
# earcons; speech is spent only where an action follows.
CB_CALLS_PER_RUN = 2
ZONE_WARNING_LOOKAHEAD_MI = 2.0  # minimum distance heads-up for a zone
# Distance compression (time_scale) and speed eat into how much *real* time a
# fixed-distance warning gives -- 2 miles at 70 mph and 20x is only ~5 seconds.
# Scale the lead distance with speed and pacing for a roughly constant real-time
# heads-up, clamped between the base distance and a sane maximum.
ZONE_WARNING_REAL_S = 18.0  # target real seconds of warning
ZONE_WARNING_MAX_MI = 10.0
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
# pacing setting keeps its relative feel (relaxed 20x, standard 40x).
# Releasing the brake returns to the speed ramp instantly.
PARKED_TIME_SCALE_MULT = 2.0
CONSTRUCTION_ENFORCEMENT_GRACE_MI = 1.5
# Chain-law areas sit over sustained steep grade -- the real trigger for
# CDOT/Caltrans chain controls. The areas are fixed in space at trip build;
# whether the law is ACTIVE follows the live weather: snow puts the signs at
# Level 1 (winter-rated tires or chains), freezing rain at Level 2 (chains on
# all commercial vehicles). The lead mile stands in for the chain-up pullout
# just before the grade.
CHAIN_LAW_MIN_GRADE = 0.05
CHAIN_LAW_MIN_RUN_MI = 1.0
CHAIN_LAW_JOIN_GAP_MI = 2.0
CHAIN_LAW_LEAD_MI = 0.5
CHAIN_LAW_SAMPLE_MI = 0.25
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

    ``dodgeable`` marks hazards a quick lane change clears: something fixed in
    one lane (debris, a stopped or slow vehicle). Anything moving across the
    road, sweeping every lane, or degrading the whole surface is brake-only.

    ``name`` is the short noun phrase a resolution line names this hazard
    by ("the deer"), so a driver who cleared it, or two of them stacked back
    to back, hears exactly what was cleared instead of a generic "it".
    """

    text: str
    weight: float = 1.0
    regions: tuple[str, ...] | None = None
    weather: tuple[WeatherKind, ...] | None = None
    terrain: tuple[str, ...] | None = None
    animal: bool = False
    dodgeable: bool = False
    name: str = ""


HAZARDS: tuple[HazardDef, ...] = (
    # Nationwide staples: plausible on any interstate, in any conditions.
    # Named debris, not "debris": a driver clearing a lane blind needs to
    # know WHAT is in it -- a ladder and a mattress are different dodges
    # (Brandon, 2026-08-20). The split's weights sum to the 1.2 the one
    # generic entry carried, so debris is exactly as common as before; the
    # types and their rough mix follow AAA's road-debris studies (ladders,
    # lumber, and furniture leading the non-tire counts). A thin generic
    # entry survives as the honest fallback for the unidentifiable.
    HazardDef("a ladder fallen from a truck in the lane", 0.25, dodgeable=True, name="the ladder"),
    HazardDef("loose lumber dropped across the lane", 0.25, dodgeable=True, name="the lumber"),
    HazardDef("a mattress lying in the lane", 0.2, dodgeable=True, name="the mattress"),
    HazardDef("spilled cargo boxes across the lane", 0.2, dodgeable=True, name="the boxes"),
    HazardDef("a shredded truck tarp in the lane", 0.15, dodgeable=True, name="the tarp"),
    HazardDef("debris on the road", 0.15, dodgeable=True, name="the debris"),
    HazardDef("retread debris from a blown tire", 1.0, dodgeable=True, name="the tire debris"),
    # The move-over law in action: shift a lane away from the shoulder.
    HazardDef("a vehicle stopped on the shoulder", 1.0, dodgeable=True, name="the stopped vehicle"),
    # "A slow vehicle ahead" is deliberately NOT here any more (owner call,
    # 2026-08-20, from Brandon's report): a slow vehicle in the flow is the
    # traffic bubble's job -- real NPCs with real speeds, spoken by the
    # slow-lead/merging/brake-lights cues and handled by the following
    # machinery -- not a scripted phantom that is slow to be slow. The
    # scripted staples that remain are genuine incidents, not flow traffic.
    HazardDef("a sudden lane closure ahead", 0.8, dodgeable=True, name="the lane closure"),
    HazardDef("stopped traffic around a fender bender", 0.9, name="the stopped traffic"),
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
        name="the deer",
    ),
    HazardDef(
        "an elk crossing the road",
        1.1,
        animal=True,
        regions=("rockies", "great_basin", "pacific_northwest"),
        name="the elk",
    ),
    # Named animals for the generic slot, same rule as the debris split
    # above: the brake call should say WHAT is in the road (Brandon,
    # 2026-08-20). Deer and elk keep their regional entries; these are the
    # nationwide commoners, weights summing to the 0.7 the one generic
    # entry carried. Dogs lead -- the most common domestic animal struck
    # on highways -- and loose livestock is the rural West's staple.
    HazardDef("a dog loose on the road", 0.2, animal=True, name="the dog"),
    HazardDef("a coyote crossing the road", 0.15, animal=True, name="the coyote"),
    HazardDef("loose livestock on the road", 0.15, animal=True, name="the livestock"),
    HazardDef("a raccoon in the lane", 0.1, animal=True, name="the raccoon"),
    HazardDef("an animal on the road", 0.1, animal=True, name="the animal"),  # honest fallback
    # Wet weather only.
    HazardDef(
        "standing water flooding the lane",
        1.1,
        weather=_WET,
        dodgeable=True,
        name="the standing water",
    ),
    HazardDef(
        "the trailer hydroplaning on standing water",
        1.0,
        weather=_HEAVY_WET,
        name="the hydroplaning",
    ),
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
        name="the hail",
    ),
    # Snow and ice only.
    HazardDef(
        "a snow squall whiting out the lane",
        1.0,
        weather=(WeatherKind.SNOW,),
        name="the snow squall",
    ),
    HazardDef(
        "ice on the bridge deck", 1.0, weather=(WeatherKind.SNOW, WeatherKind.ICE), name="the ice"
    ),
    HazardDef(
        "black ice on the shaded grade",
        1.1,
        weather=(WeatherKind.SNOW, WeatherKind.ICE),
        terrain=("mountain", "hills"),
        name="the black ice",
    ),
    # Freezing rain only: the whole road is finding out at the same time.
    HazardDef(
        "glaze ice sheeting the whole lane",
        1.3,
        weather=(WeatherKind.ICE,),
        name="the glaze ice",
    ),
    HazardDef(
        "a car spun out on the glaze ahead",
        1.1,
        weather=(WeatherKind.ICE,),
        dodgeable=True,
        name="the spun-out car",
    ),
    # Dense fog only.
    HazardDef(
        "brake lights looming in dense fog",
        1.2,
        weather=(WeatherKind.FOG,),
        name="the brake lights",
    ),
    # High wind: crosswind shove and blowing debris in open country.
    HazardDef(
        "a crosswind gust shoving the trailer",
        1.2,
        weather=(WeatherKind.WIND,),
        regions=_CROSSWIND_REGIONS,
        name="the crosswind gust",
    ),
    HazardDef(
        "a dust storm dropping visibility",
        0.9,
        weather=(WeatherKind.WIND,),
        regions=("desert_southwest", "southern_plains", "great_basin"),
        name="the dust storm",
    ),
    HazardDef(
        "tumbleweeds piling in your lane",
        0.5,
        weather=(WeatherKind.WIND,),
        regions=("desert_southwest", "great_basin", "southern_plains"),
        dodgeable=True,
        name="the tumbleweeds",
    ),
    # Mountain terrain only.
    HazardDef(
        "rockfall debris on the road",
        1.0,
        terrain=("mountain",),
        regions=("rockies", "appalachia", "great_basin", "pacific_northwest", "california"),
        dodgeable=True,
        name="the rockfall",
    ),
    HazardDef(
        "a runaway truck on the grade ahead",
        0.8,
        terrain=("mountain",),
        name="the runaway truck",
    ),
)


# Text-keyed lookups so hazard consumers can stay on the (text, weight) shape
# of ``eligible_hazards`` and still learn whether a lane change clears a
# hazard, and what short noun phrase names it once it does.
DODGEABLE_HAZARD_TEXTS = frozenset(h.text for h in HAZARDS if h.dodgeable)
HAZARD_NAMES: dict[str, str] = {h.text: h.name for h in HAZARDS}


def hazard_is_dodgeable(text: str) -> bool:
    return text in DODGEABLE_HAZARD_TEXTS


def hazard_name(text: str) -> str:
    """The short noun phrase a resolution line names this hazard by.

    Falls back to "it" for a hazard text that somehow is not in the table
    (should not happen -- every ``HAZARDS`` entry carries one) rather than
    ever raising mid-drive.
    """
    return HAZARD_NAMES.get(text, "it")


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


@dataclass(frozen=True)
class RoadsideCallout:
    """One scheduled ambient roadside line: a landmark or a billboard.

    ``at_mi`` is the trip mile (direction-resolved), ``category`` is the
    landmark category or ``"billboard"`` -- the roadside-chatter settings
    filter on it at speak time, so the schedule itself stays deterministic
    regardless of settings."""

    key: str
    at_mi: float
    category: str
    spoken: str
    # True when this place name explains a speed limit change just ahead
    # (a village whose 35 zone starts within the pairing window). Sparse
    # place callouts speak exactly these and nothing else.
    explains_limit: bool = False


# Ambient roadside lines keep their distance so river clusters and museum
# rows never stack into a wall of speech; safety cues are never spaced.
LANDMARK_MIN_SPACING_MI = 2.0
# Billboards pace like the real interstate genre: one every half hour or so
# of highway driving, never in the first miles of a trip.
# Villages are baked out to a wide catchment so the map can answer "what is
# near me" at any distance, but the ride-along names only the ones the driver
# genuinely reaches: "Entering" where the road runs through the place, and
# "Passing" out to the width of a town an interstate skirts rather than enters.
# Anything farther is real data that would be a false promise spoken aloud.
VILLAGE_ENTER_OFF_MI = 0.5
VILLAGE_PASS_OFF_MI = 1.5
# Villages thin on the same spacing as the rest of the roadside, but by a
# different rule: within a window the place nearest the road wins, so a town the
# route runs through outranks one it only skirts. The northeast corridor really
# does string a named place along every mile (the Wilmington approach to
# Philadelphia passes thirty), and reading that list aloud is a chant rather
# than orientation. Widening this instead was tried and rejected: at five miles
# it deleted Strawberry, which sits under three miles from Pine and is half the
# reason the feature exists. Real towns are allowed to be close together.
VILLAGE_MIN_SPACING_MI = LANDMARK_MIN_SPACING_MI
# A village "explains" a limit change when a town-scale limit (<= the max
# below) takes effect within this window past the callout. Mirrors the bake
# rule that placed paired callouts just before their zone start.
VILLAGE_PAIR_WINDOW_MI = 1.5
VILLAGE_PAIR_MAX_LIMIT_MPH = 45.0
BILLBOARD_MIN_GAP_MI = 35.0
BILLBOARD_MAX_GAP_MI = 65.0
BILLBOARD_LEAD_IN_MI = 15.0


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
    LANDMARK = "landmark"
    BILLBOARD = "billboard"
    CURVE = "curve"
    LANE = "lane"
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
    """A stretch of road with a reduced speed limit.

    ``closed_side`` is which SIDE of the road is coned off through the zone,
    "right" or "left", and it is the authoritative fact: the road can carry a
    different number of lanes at either end of one work zone, so a stored lane
    index means different lanes at different miles, while the side does not.
    Everything spoken about a closure, and everything that decides which lane
    the truck may be in, reads the side (through ``Trip.closed_lane_at``), so
    the lane the player is told about and the lane that is actually shut can
    never be two readings of the same number.

    ``closed_lane`` is the nominal index on an ordinary two-lane-each-way
    stretch (0 = right), kept because saves, tests and the placement code
    speak in indexes. The two are derived from each other on construction.
    Construction sets the closure; the taper zone ahead of the work carries
    the same one so the merge callout can say which way to move.

    Congestion zones ("heavy traffic") carry ``aadt`` and per-direction
    ``lanes`` instead of a fixed schedule: whether the zone is active and how
    slow it runs are recomputed from the clock hour, so the same stretch jams
    at rush hour and flows free at midnight. ``limit_mph`` on those zones is
    the current effective traffic speed, refreshed by the trip."""

    start_mi: float
    end_mi: float
    limit_mph: float
    reason: str
    closed_lane: int | None = None
    aadt: float | None = None
    lanes: int = 2
    closed_side: str | None = None

    def __post_init__(self) -> None:
        if self.closed_side is None and self.closed_lane is not None:
            self.closed_side = "right" if self.closed_lane == 0 else "left"
        elif self.closed_side is not None and self.closed_lane is None:
            self.closed_lane = 0 if self.closed_side == "right" else 1


@dataclass
class RoadStop:
    name: str
    at_mi: float
    type: str = "travel_center"
    actions: tuple[str, ...] = ()
    services: tuple[str, ...] = ()
    parking: str = "unknown"
    exit_label: str = ""  # "exit 7" when a real OSM interchange sits here
    # Surveyed truck-parking spot count (FHWA Jason's Law via BTS NTAD);
    # 0 means unsurveyed and the spoken cue stays capacity-silent.
    parking_spaces: int = 0
    # Whether a combination vehicle can physically get in (see world_constants).
    vehicle_access: str = DEFAULT_VEHICLE_ACCESS

    def accessible_to(self, *, bobtail: bool) -> bool:
        return vehicle_access_allows(self.vehicle_access, bobtail=bobtail)

    @property
    def key(self) -> str:
        """Identity of this stop on this route, for tracking rather than speech.

        Names repeat constantly -- a coast-to-coast route carries six stops
        called "Love's Travel Stop" -- so anything that remembers *which* stop
        (announced already, planned, exit in progress) has to key on the
        milepost too, or one stop stands in for all its namesakes.
        """
        return f"{self.at_mi:.2f}:{self.name}"

    @staticmethod
    def name_from_key(key: str) -> str:
        """The speakable name back out of a key, for a plan whose stop is gone."""
        return key.split(":", 1)[-1]

    @property
    def label(self) -> str:
        return STOP_TYPE_LABELS.get(self.type, "stop")

    @property
    def spoken_name(self) -> str:
        # Drop the type prefix when the proper name already carries it
        # ("cross-dock: Chicago Cross-Dock" -> "Chicago Cross-Dock"); the
        # prefix stays where the name does not name its type (research doc R6).
        from ..speech_text import typed_name

        return typed_name(self.label, self.name, sep=": ")

    @property
    def parking_text(self) -> str:
        text = {
            "confirmed": "confirmed truck parking",
            "likely": "",
            "limited": "limited truck parking",
            "unknown": "parking not verified",
            "none": "no truck parking",
        }.get(self.parking, "parking not verified")
        if text and self.parking_spaces > 0 and self.parking in {"confirmed", "limited"}:
            return f"{text}, {self.parking_spaces} spaces"
        return text


@dataclass
class NPCVehicle:
    """A simulated nearby road user that can affect traffic flow.

    ``lane`` is the absolute lane index (0 = right), mirroring
    ``TrafficVehicle``; ``relative_lane`` keeps the spoken-text surface."""

    key: str
    position_mi: float
    speed_mph: float
    target_speed_mph: float
    relative_lane: int
    behavior: str
    length_mi: float = 0.25
    lane: int = 0

    @property
    def at_mi(self) -> float:
        return self.position_mi

    @property
    def end_mi(self) -> float:
        return self.position_mi + self.length_mi

    @property
    def lane_text(self) -> str:
        if self.relative_lane < 0:
            return "left lane"
        if self.relative_lane > 0:
            return "right lane"
        return "your lane"

    @property
    def reason(self) -> str:
        return {
            "steady_truck": "steady truck traffic",
            "slow_car": "slow car ahead",
            "merging_vehicle": "merging traffic",
            "braking_traffic": "brake lights ahead",
            "passing_vehicle": "passing traffic",
        }.get(self.behavior, "traffic ahead")


@dataclass(frozen=True)
class TrafficContext:
    lead: NPCVehicle
    gap_mi: float
    closing_mph: float

    @property
    def gap_seconds(self) -> float:
        speed = max(1.0, self.lead.speed_mph)
        return self.gap_mi / speed * 3600.0


@dataclass(frozen=True)
class TrafficPressure:
    """A short stretch where merging or exiting needs extra spacing."""

    start_mi: float
    end_mi: float
    kind: str
    direction: str
    intensity: float
    target_speed_mph: float
    reason: str


def _traffic_pressure_key(pressure: TrafficPressure) -> str:
    return f"{pressure.kind}:{pressure.start_mi:.3f}:{pressure.end_mi:.3f}:{pressure.reason}"


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
    # Optional local-road maneuver direction used only for non-speech earcons.
    direction: str = ""


# -- Getting onto the highway: the acceleration lane -------------------------
#
# Two different questions, two different sources, and they disagree on purpose.
#
# HOW LONG IS THE LANE is a question about concrete that already exists, so it
# comes from the design standard the interchange was built to: AASHTO Green
# Book Table 10-3, reproduced as Table 3-13 of TxDOT's Roadway Design Manual
# (May 2022), which is free to read. Feet of acceleration lane needed from a
# STOP, by the highway's design speed.
#
# HOW FAST THE TRUCK GETS is a question about a loaded rig, and the AASHTO
# figures cannot answer it -- they were derived from passenger cars, which the
# Mack-Blackwell review (MBTC FR 2094/3003, 2008) says plainly while showing
# every truck-based study landing "substantially longer". So the truck's own
# curve comes from Long, TRR 1737 (2000), for a loaded 200 lb/hp WB-15.
#
# Keeping both is the point. The lane is sized for a car and the truck is a
# truck, so a loaded rig reaches the taper BELOW highway speed -- and that is
# the real outcome, not a fault to design away. The Green Book's own target is
# only 75 percent of highway speed, and the CDL manual answers slow
# acceleration with a BIGGER GAP rather than more speed: "Because of slow
# acceleration and the space large vehicles require, you may need a much
# larger gap to enter traffic than you would in a car."
ACCELERATION_LANE_FT: dict[float, float] = {
    40.0: 360.0,
    50.0: 720.0,
    55.0: 960.0,
    60.0: 1200.0,
    65.0: 1410.0,
    70.0: 1620.0,
    75.0: 1790.0,
}

# Long's model: a = ALPHA - BETA * v, feet and feet per second. Asymptotic top
# speed is ALPHA / BETA, about 65 mph, which is why a loaded truck stops
# gaining meaningfully long before an empty one would.
TRUCK_ACCEL_ALPHA_FPS2 = 1.90
TRUCK_ACCEL_BETA = 0.0199

# Grade term, applied as -G*g. Trustworthy only over this band: past it the
# model claims a loaded truck cannot climb 6 percent at all, which is false --
# it climbs, slowly. Outside the band the flat figure stands and the grade is
# left to the physics the truck already has.
GRADE_MODEL_MIN_PCT = -4.0
GRADE_MODEL_MAX_PCT = 2.0

# AASHTO's own grade multipliers on the lane length (TxDOT Table 3-14), for
# the uphill ramp that actually hurts. Upgrades need more room; downgrades
# need less.
ACCELERATION_LANE_GRADE_FACTOR: tuple[tuple[float, float], ...] = (
    (-3.0, 0.6),  # 3 to 4 percent down
    (-5.0, 0.55),
    (3.0, 1.5),  # 3 to 4 percent up
    (5.0, 2.2),  # 5 to 6 percent up
)


def acceleration_lane_mi(highway_mph: float, grade_pct: float = 0.0) -> float:
    """Miles of acceleration lane an entrance at ``highway_mph`` really has.

    Interpolated between the table's design speeds, then adjusted for grade.
    Never shorter than the 40 mph entry, because no built ramp is.
    """
    speeds = sorted(ACCELERATION_LANE_FT)
    if highway_mph <= speeds[0]:
        feet = ACCELERATION_LANE_FT[speeds[0]]
    elif highway_mph >= speeds[-1]:
        feet = ACCELERATION_LANE_FT[speeds[-1]]
    else:
        lo = max(s for s in speeds if s <= highway_mph)
        hi = min(s for s in speeds if s >= highway_mph)
        if lo == hi:
            feet = ACCELERATION_LANE_FT[lo]
        else:
            span = (highway_mph - lo) / (hi - lo)
            feet = ACCELERATION_LANE_FT[lo] + span * (
                ACCELERATION_LANE_FT[hi] - ACCELERATION_LANE_FT[lo]
            )
    factor = 1.0
    for threshold, value in ACCELERATION_LANE_GRADE_FACTOR:
        downhill_enough = threshold < 0 and grade_pct <= threshold
        uphill_enough = threshold > 0 and grade_pct >= threshold
        if downhill_enough or uphill_enough:
            factor = value
    return feet * factor / 5280.0


def truck_merge_speed_mph(highway_mph: float, entry_mph: float, lane_mi: float) -> float:
    """What a loaded truck is really doing at the end of that lane.

    Long's curve integrated over the lane, capped at the highway's own limit:
    a truck that had a running start does not keep accelerating past the sign
    just because the lane is long.
    """
    v = max(0.0, entry_mph) * 5280.0 / 3600.0  # feet per second
    top = TRUCK_ACCEL_ALPHA_FPS2 / TRUCK_ACCEL_BETA
    remaining = max(0.0, lane_mi) * 5280.0
    # Step the curve rather than solve it: the closed form is awkward in
    # distance and this runs once per departure, not per frame.
    step = 10.0
    while remaining > 0.0 and v < top:
        accel = TRUCK_ACCEL_ALPHA_FPS2 - TRUCK_ACCEL_BETA * v
        if accel <= 0.0:
            break
        # v dv = a dx
        v = math.sqrt(max(0.0, v * v + 2.0 * accel * min(step, remaining)))
        remaining -= step
    return min(highway_mph, v * 3600.0 / 5280.0)


__all__ = [name for name in globals() if not name.startswith("__")]
