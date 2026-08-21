"""Small NPC traffic bubble around the player's truck."""

from __future__ import annotations

import hashlib
import logging
import math
import random
from dataclasses import dataclass

from ..data.world import Leg, Route
from ..speech_text import brake_lights_cue, merging_traffic_cue, slow_lead_cue
from .hos import is_night
from .trip_models import (
    DIRECTIONAL_SPLIT,
    RUSH_HOUR_WINDOWS,
    TRAFFIC_LOOKAHEAD_MI,
    TrafficContext,
    _leg_speed_limit_at,
    corridor_speed_limit,
    hourly_volume_fraction,
    leg_aadt_at,
)

log = logging.getLogger(__name__)

# -- the rolling bubble --------------------------------------------------------------
# Traffic used to be seeded once, for the whole route, at one candidate vehicle
# per 85 miles, and never replaced: everything was placed ahead of the truck and
# retired for good two miles behind it. Three consequences, all measured over
# 6.2 miles of interstate before this changed -- the bubble peaked at 0-3
# vehicles, it drained as the trip went on because nothing replaced what was
# retired, and the "passing" intent could never actually pass, because a
# vehicle doing 62-75 mph placed AHEAD of a 60 mph truck only ever recedes.
#
# So the bubble is now a window that travels with the truck. Vehicles are
# created as the road reaches them and retired behind, which bounds the
# population by the road around the player instead of by route length, and
# leaves room for the thing the old model could not express: somebody coming up
# from behind and going past.
SPAWN_CELL_MI = 0.4
# Far enough back that a faster vehicle has room to close and pass rather than
# appearing alongside; the cull at -2.0 mi is what it eventually leaves by.
BUBBLE_BEHIND_MI = 2.4
# A little past TRAFFIC_LOOKAHEAD_MI so a lead vehicle is already in place
# before it comes into announcing range.
BUBBLE_AHEAD_MI = 3.2
# Ceiling on the live population. Every vehicle is stepped each frame, and the
# road only has so many lanes; past this it is noise the player cannot resolve.
MAX_BUBBLE_VEHICLES = 28
# Clear air around the truck where nothing is created. Traffic has to enter
# the bubble at its edges and close from there; a vehicle drawn into being a
# few hundred feet ahead is one that appeared out of nowhere, and on a road
# the player reads by ear that is worse than an empty lane -- the lead-vehicle
# warning would announce a truck that did not exist a second earlier.
NO_SPAWN_AHEAD_MI = 1.1
NO_SPAWN_BEHIND_MI = 0.6
# How far into a run the bubble withholds the "merging" intent. Wide enough
# to clear the nearest spawn cell plus the distance a merge cue carries, so
# the opening line of a run is never somebody merging into a truck that has
# not got up to speed yet. Everything else about the draw is unchanged.
MERGE_FREE_START_MI = 3.0

# How far past an interchange a vehicle can still be merging into you. An
# on-ramp feeds traffic in over a taper of a few hundred yards, so this is
# generous rather than tight.
#
# WHY IT IS POSITIONAL AT ALL (owner, 2026-08-19: "why do we have to clear
# every single car? Have to swerve around every single one when most are just
# passing"). Merging was drawn UNIFORMLY along the leg at a weight of 1.2
# against 7.3 total -- one vehicle in six, anywhere, with no on-ramp in sight.
# Braking was another one in seven, equally unconditioned. So roughly a third
# of everything ahead demanded action, on a road where in reality almost
# everything is just travelling.
#
# Both are positional in life and both now have the data to be positional
# here: merges happen at interchanges (0.22 per mile on I-65, spaced two and
# a half to six miles), and hard braking happens in congestion, which is now
# placed from real HPMS volumes rather than a dice roll.
MERGE_WINDOW_MI = 0.45
# How far a bubble vehicle runs before it leaves the highway, drawn per
# vehicle. Nobody shares a whole corridor with you, and the upper end is what
# bounds how long a slow one can hold the lane in front of the truck.
EXIT_AFTER_MIN_MI = 2.5
EXIT_AFTER_MAX_MI = 11.0
# What each intent is doing relative to the road's posted limit. These were
# absolute mph bands (cruising 52-64, braking 35-48) tuned before real posted
# limits were baked per leg, and they never moved when the map did: on a 75 mph
# Texas corridor the entire population ran 20-40 mph slower than the road, so
# the truck kept announcing "leave room for 30" for a semi on an interstate
# (owner playtest, 2026-08-15). Relative bands hold on a 75 corridor, a 55
# two-lane and a 30 mph town street alike.
TRAFFIC_SPEED_OFFSETS_MPH = {
    "passing": (3.0, 10.0),
    "cruising": (-3.0, 5.0),
    "following": (-10.0, -3.0),
    "merging": (-18.0, -8.0),
    "braking": (-22.0, -10.0),
}
# The floor is a share of the limit, not one absolute number: 30 mph is a
# reasonable slowest-thing-on-the-road for an interstate and absurd for a town
# street, and the old flat floors did the same damage in miniature.
TRAFFIC_MIN_SPEED_SHARE = 0.45
TRAFFIC_MIN_SPEED_MPH = 15.0
# Used only where the route cannot answer for a mile at all (off the end of the
# last leg); every real spawn reads the leg it lands on.
DEFAULT_LIMIT_MPH = 65.0


@dataclass
class TrafficVehicle:
    """One NPC in the traffic bubble.

    ``lane`` is the absolute lane index (0 = right lane, counting leftward),
    matching the player's ``LaneKeeping.lane``. ``relative_lane`` keeps the
    legacy spoken-text surface (negative = left of the player) and is
    recomputed against the player's lane every manager update."""

    key: str
    position_mi: float
    speed_mph: float
    target_speed_mph: float
    relative_lane: int
    intent: str
    vehicle_class: str
    length_mi: float = 0.25
    lane: int = 0
    # The route mile this vehicle leaves the highway at, for bubble traffic.
    # Nobody drives the whole corridor beside you: they take an exit, and
    # without that a slower vehicle ahead was permanent. The truck would
    # settle in behind a 45 mph car and never see the front of it again,
    # which turned an adaptive-cruise feature into a pin -- a speed-control
    # segment that used to finish stopped dead at the same mile however long
    # it was given.
    exit_at_mi: float | None = None

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
    def behavior(self) -> str:
        return {
            "cruising": "steady_truck",
            "following": "slow_car",
            "merging": "merging_vehicle",
            "braking": "braking_traffic",
            "passing": "passing_vehicle",
            "patrolling": "marked_unit",
        }.get(self.intent, self.intent)

    @property
    def reason(self) -> str:
        if self.vehicle_class == "state trooper":
            return "state trooper ahead"
        return {
            "cruising": "steady truck traffic",
            "following": "slow car ahead",
            "merging": "merging traffic",
            "braking": "brake lights ahead",
            "passing": "passing traffic",
            "patrolling": "marked unit ahead",
        }.get(self.intent, "traffic ahead")


@dataclass(frozen=True)
class TrafficSituation:
    kind: str
    vehicle: TrafficVehicle
    message: str
    interrupt: bool = False


# Why traffic is braking, said in the driver's words, keyed by the Zone
# reason the trip stamped on that mile. A module constant rather than an
# inline dict so the vocabulary can be checked against the reasons the
# generator actually produces: a zone kind the table has never heard of
# silently loses its explanation, and a table key nothing produces is dead
# vocabulary that reads like coverage. Both are invisible in play.
#
# Absent on purpose: anything not mile-mapped. A slowdown with nothing
# behind it says nothing about cause -- phantom waves are real, and an
# invented crash would be worse than silence (Brandon, 2026-08-20).
BRAKING_CAUSE_LINES = {
    "construction": "Road work is the cause.",
    "construction merge": "Road work is the cause.",
    "heavy traffic": "Traffic is backing up ahead.",
}


class TrafficManager:
    def __init__(
        self,
        *,
        route: Route,
        truck,
        weather,
        leg_starts: list[float],
        seed: int,
        start_hour: float,
        hazard_scale: float,
        imperial: bool,
    ) -> None:
        self.route = route
        self.truck = truck
        self.weather = weather
        self.leg_starts = list(leg_starts)
        self.seed = seed
        self.start_hour = start_hour
        self.hazard_scale = hazard_scale
        self.imperial = imperial
        self.vehicles: list[TrafficVehicle] = []
        self.announced_vehicle_keys: set[str] = set()
        # Spawn cells the rolling bubble has already drawn for. A cell is used
        # once and never again, so a vehicle the truck has passed cannot pop
        # back into existence when the truck slows and the window catches up.
        self._spawned_cells: set[int] = set()
        # Whether ``update`` tops the window up. On for real driving; a test
        # or a tool that assigns ``vehicles`` directly wants the road it put
        # there and nothing else, and topping up behind its back would make
        # the list it just set unreproducible.
        self.rolling_bubble = True
        # Time of day the density model should read. Set from the trip each
        # frame; without it a ten-hour run kept its departure hour's traffic
        # all night, which is the case a player driving with live weather and
        # a real clock notices first.
        self.hour = start_hour
        # Weekday or weekend, for the hourly volume curve. Set from the trip
        # beside ``hour``; the weekday curve is the safe default because it is
        # the busier of the two.
        self._weekend = False
        # (start_mi, end_mi) spans where traffic has a reason to be braking:
        # the congestion zones the trip placed from real volumes. Set by the
        # trip, because the manager does not own zone placement.
        self._braking_zones: tuple[tuple[float, float], ...] = ()
        # The driving state mirrors the player's discrete lane here each
        # frame so same-lane checks and spoken relative lanes stay honest.
        self.player_lane = 0
        # Mirrored alongside player_lane: the lane a tap-change is moving
        # INTO, or None the rest of the time. Lead selection reads this while
        # it is set -- mid-change, the origin lane is the one being left, and
        # cruise/the follow cue matching its slow lead is what used to make
        # the truck ease off for traffic it was passing.
        self.player_lane_target: int | None = None

    def _seed_key(self) -> str:
        route_key = "|".join(
            f"{city}:{leg.highway}:{leg.miles:.1f}"
            for city, leg in zip(self.route.cities, self.route.legs, strict=False)
        )
        return f"traffic-manager:{self.seed}:{route_key}"

    def _rng(self) -> random.Random:
        digest = hashlib.sha256(self._seed_key().encode("utf-8")).hexdigest()
        return random.Random(int(digest[:16], 16))

    def _rush_hour_traffic_bias(self, leg: Leg) -> float:
        # self.hour, not start_hour: a run that departs at 04:00 drives into
        # the morning rush, and one that departs at 16:00 drives out of the
        # evening one. Reading the departure hour for the whole trip made the
        # road outside the cab disagree with the clock inside it.
        hour = self.hour % 24.0
        if not any(start <= hour < end for start, end in RUSH_HOUR_WINDOWS):
            return 0.0
        return 0.14 if leg.checkpoints else 0.06

    def _leg_density(self, leg: Leg, night: bool, mile: float | None = None) -> float:
        """How much of this road is carrying somebody, 0 to 1.

        Read from the road's real traffic where the HPMS bake covers it. The
        chain is the same one congestion already runs on: annual average
        daily traffic, times this hour's share of the day, times the peak
        direction's share, over the speed traffic is moving -- which gives
        vehicles per mile in your direction, and times the cell width gives
        the expected number in a cell.

        The cell either has somebody in it or it does not, so the expectation
        becomes a probability the honest way: arrivals along a road are
        Poisson, and P(at least one) is ``1 - exp(-lambda)``. That saturates
        by itself on a road that really does carry a vehicle every four
        tenths of a mile, which is most interstates at five in the afternoon.

        WHAT THIS CANNOT DO, and it is worth being plain about it: the bubble
        holds ``MAX_BUBBLE_VEHICLES`` over its width, about five vehicles a
        mile, while a median road at peak wants thirteen in your direction
        alone. So the ORDER is now real -- a quiet rural highway is
        measurably sparser than a busy freeway, at the hour it is actually
        quieter -- but the absolute count still cannot be. Fixing that means
        several vehicles per cell and a much larger bubble, which is a
        different change with a performance question attached.

        Deliberately reads nothing from ``hazard_scale``: presence is not
        difficulty, and the road has the traffic it has. Difficulty reaches
        the player on random hazards and on which vehicles are worth
        interrupting them about.
        """
        volume = self._aadt_at(leg, mile)
        if volume is None:
            # No bake here. The old class/metro shape, kept intact so an
            # uncovered leg drives exactly as it did rather than falling to
            # some new default.
            metro_bias = 0.18 if leg.checkpoints else 0.0
            night_bias = -0.08 if night else 0.0
            rush_bias = self._rush_hour_traffic_bias(leg)
            return min(
                0.86,
                max(0.05, 0.22 + leg.miles / 900.0 + metro_bias + night_bias + rush_bias),
            )
        aadt, _lanes = volume
        share = hourly_volume_fraction(self.hour, self._weekend)
        moving_mph = max(25.0, min(70.0, abs(self.truck.speed_mph) or 60.0))
        per_mile = aadt * share * DIRECTIONAL_SPLIT / moving_mph
        expected_in_cell = per_mile * SPAWN_CELL_MI
        occupied = 1.0 - math.exp(-expected_in_cell)
        # Same floor and ceiling as before: the floor keeps an empty road from
        # being literally empty, and the ceiling is what the bubble can hold.
        return min(0.86, max(0.05, occupied))

    def _aadt_at(self, leg: Leg, mile: float | None) -> tuple[float, int] | None:
        """Baked (AADT, lanes) under a route mile, or None where none exists."""
        if mile is None:
            return leg_aadt_at(leg, 0.0) if getattr(leg, "traffic_volumes", ()) else None
        found = self._leg_and_offset_at(mile)
        if found is None:
            return None
        at_leg, offset = found
        if not getattr(at_leg, "traffic_volumes", ()):
            return None
        return leg_aadt_at(at_leg, offset)

    def _weather_slowdown(self) -> float:
        effects = self.weather.effects
        return max(
            0.0,
            min(
                14.0,
                (1.0 - effects.grip) * 20.0 + max(0.0, 3.0 - effects.visibility_mi) * 1.4,
            ),
        )

    def spawn_initial_traffic(self) -> None:
        rng = self._rng()
        vehicles: list[TrafficVehicle] = []
        weather_slowdown = self._weather_slowdown()
        night = is_night(self.start_hour)
        for leg_index, (start, leg) in enumerate(
            zip(self.leg_starts, self.route.legs, strict=True)
        ):
            if leg.miles < 35.0:
                continue
            density = self._leg_density(leg, night)
            slots = max(1, int(leg.miles / 85.0))
            for slot in range(slots):
                if rng.random() > min(0.92, density + 0.18):
                    continue
                span = leg.miles / slots
                low = max(4.0, slot * span + 8.0)
                high = min(leg.miles - 6.0, (slot + 1) * span + 4.0)
                if high <= low:
                    continue
                intent = rng.choices(
                    ("cruising", "following", "merging", "braking", "passing"),
                    weights=(3.0, 1.5, 1.2, 1.0, 1.1),
                )[0]
                vehicle_class = rng.choices(
                    ("car", "box truck", "semi", "service vehicle"),
                    weights=(5.0, 1.4, 2.0, 0.3),
                )[0]
                position_mi = start + rng.uniform(low, high)
                limit_mph = self._posted_limit_at(position_mi)
                base_speed = self._intent_speed(intent, limit_mph, rng)
                rush_slowdown = rng.uniform(4.0, 10.0) if self._rush_hour_traffic_bias(leg) else 0.0
                speed = max(
                    self._floor_speed(limit_mph), base_speed - weather_slowdown - rush_slowdown
                )
                # Passing traffic lives in the left lane; everyone else --
                # including vehicles merging in from a ramp -- holds the
                # right lane, where trucks are supposed to be.
                lane = 1 if intent == "passing" else 0
                vehicles.append(
                    TrafficVehicle(
                        key=f"traffic:{leg_index}:{slot}:{intent}",
                        position_mi=position_mi,
                        speed_mph=speed,
                        target_speed_mph=speed,
                        relative_lane=-lane,
                        intent=intent,
                        vehicle_class=vehicle_class,
                        lane=lane,
                    )
                )
        self.vehicles = sorted(vehicles, key=lambda vehicle: vehicle.position_mi)

    def add_enforcement_traffic(self, posts) -> None:
        """Give the roving posts a body in the traffic bubble.

        Only ``roving_patrol`` posts get one: those are the units that move
        with traffic, and the traffic bubble is what moving traffic is for. A
        median crossover, a scale apron and a work-zone detail are parked --
        they belong to the enforcement layer's own cues, not to the bubble,
        and spawning a "cruising" vehicle for each of them is what used to
        put phantom troopers into the lead-vehicle lookups.

        The intent is ``patrolling``, not ``cruising``: ``next_situation``
        returned ``None`` for cruising, which is why the shipped, credited,
        unit-tested trooper pass-by sound never once played in the game.
        """
        existing_keys = {vehicle.key for vehicle in self.vehicles}
        for post in posts:
            if getattr(post, "kind", "") != "roving_patrol" or not getattr(post, "staffed", False):
                continue
            key = f"trooper:{post.id}"
            if key in existing_keys:
                continue
            # A roving patrol runs with traffic, which is the posted number
            # here rather than a fixed 62 that reads as slow on a 75 corridor
            # and as reckless through a town.
            speed = self._posted_limit_at(post.at_mi)
            self.vehicles.append(
                TrafficVehicle(
                    key=key,
                    position_mi=post.at_mi,
                    speed_mph=speed,
                    target_speed_mph=speed,
                    relative_lane=0,
                    intent="patrolling",
                    vehicle_class="state trooper",
                )
            )
            existing_keys.add(key)
        self.vehicles.sort(key=lambda vehicle: vehicle.position_mi)

    def lead_vehicle(self, position_mi: float, truck_speed_mph: float) -> TrafficContext | None:
        # TrafficVehicle intentionally matches the NPCVehicle runtime surface
        # used by TrafficContext while the traffic bubble is split out.
        # Mid-change, reason about the lane being entered, not the one being
        # left -- otherwise a lead in the origin lane keeps capping the
        # target for the whole maneuver, exactly when the driver wants to
        # accelerate into the open lane.
        lane = self.player_lane if self.player_lane_target is None else self.player_lane_target
        nearest: tuple[float, TrafficVehicle] | None = None
        for vehicle in self.vehicles:
            if vehicle.lane != lane:
                continue
            gap_mi = vehicle.position_mi - position_mi
            if gap_mi < -vehicle.length_mi or gap_mi > TRAFFIC_LOOKAHEAD_MI:
                continue
            context_gap_mi = max(0.0, gap_mi)
            if nearest is None or context_gap_mi < nearest[0]:
                nearest = (context_gap_mi, vehicle)

        if nearest is None:
            return None

        gap_mi, vehicle = nearest
        closing_mph = max(0.0, truck_speed_mph - vehicle.speed_mph)
        return TrafficContext(lead=vehicle, gap_mi=gap_mi, closing_mph=closing_mph)

    def _gap_text(self, miles: float) -> str:
        if self.imperial:
            return f"{miles:.1f} miles"
        return f"{miles * 1.609344:.1f} kilometers"

    def _speed_value(self, mph: float) -> str:
        if self.imperial:
            return f"{mph:.0f} miles per hour"
        return f"{mph * 1.609344:.0f} kilometers per hour"

    def _speed_bare(self, mph: float) -> str:
        """The number alone, for the terse slot grammar's trailing speed."""
        if self.imperial:
            return f"{mph:.0f}"
        return f"{mph * 1.609344:.0f}"

    def _merge_plausible_at(self, mile: float) -> bool:
        """Whether a vehicle here could be merging in from a ramp."""
        found = self._leg_and_offset_at(mile)
        if found is None:
            return False
        leg, offset = found
        for interchange in getattr(leg, "interchanges", ()) or ():
            at = getattr(interchange, "at_mi", None)
            if at is None:
                continue
            if 0.0 <= offset - at <= MERGE_WINDOW_MI:
                return True
        return False

    def _braking_plausible_at(self, mile: float) -> bool:
        """Whether traffic here has a reason to be stopping hard.

        Congestion is placed from real volumes now, so "somebody is on the
        brakes" can follow the jam instead of being sprinkled evenly down an
        empty interstate. A ramp is the other honest place for it: that is
        where traffic slows to leave.
        """
        for zone in getattr(self, "_braking_zones", ()) or ():
            if zone[0] <= mile <= zone[1]:
                return True
        return self._merge_plausible_at(mile)

    def _braking_reason_at(self, mile: float) -> str:
        """Why traffic is braking here, when the road knows: the zone's own
        reason. Empty when nothing mile-mapped explains it -- which is
        honest, because phantom waves are real; the cue then says nothing
        about cause rather than inventing one (Brandon, 2026-08-20, asking
        WHY the brake lights). Live 511 incidents are announced separately
        and are not yet mile-mapped; attributing them lands with the
        incident-feed expansion on ROADMAP."""
        for zone in getattr(self, "_braking_zones", ()) or ():
            if zone[0] <= mile <= zone[1]:
                return str(zone[2]) if len(zone) > 2 else ""
        return ""

    def _zone_pace_at(self, mile: float) -> float | None:
        """The prevailing speed of the braking zone covering this mile, when
        the trip handed one over. Older two- and three-element tuples carry
        no pace and answer None."""
        for zone in getattr(self, "_braking_zones", ()) or ():
            if zone[0] <= mile <= zone[1] and len(zone) > 3 and zone[3]:
                return float(zone[3])
        return None

    def _vehicle_intent(self, vehicle) -> str:
        intent = getattr(vehicle, "intent", None)
        if intent is not None:
            return intent
        return {
            "steady_truck": "cruising",
            "slow_car": "following",
            "merging_vehicle": "merging",
            "braking_traffic": "braking",
            "passing_vehicle": "passing",
        }.get(getattr(vehicle, "behavior", ""), "cruising")

    def _vehicle_class(self, vehicle) -> str:
        return getattr(vehicle, "vehicle_class", "vehicle")

    def inject_congestion(self, zone, *, position_mi: float) -> None:
        """Fill an activating congestion zone with slow vehicles ahead.

        Both lanes get traffic pacing the zone's prevailing speed, so the jam
        is heard and felt through the existing lead-vehicle machinery -- and a
        dodge into the next lane over meets metal there too."""
        key_base = f"congestion:{zone.start_mi:.1f}"
        if any(vehicle.key.startswith(key_base) for vehicle in self.vehicles):
            return
        rng = random.Random(
            int(hashlib.sha256(f"{self.seed}:{key_base}".encode()).hexdigest()[:12], 16)
        )
        pace = max(10.0, float(zone.limit_mph))
        anchor = max(position_mi + 0.25, zone.start_mi + 0.2)
        added: list[TrafficVehicle] = []
        for i in range(rng.randint(3, 5)):
            lane = i % 2
            speed = max(6.0, pace + rng.uniform(-9.0, 4.0))
            added.append(
                TrafficVehicle(
                    key=f"{key_base}:{i}",
                    position_mi=anchor + i * rng.uniform(0.25, 0.6),
                    speed_mph=speed,
                    target_speed_mph=speed,
                    relative_lane=self.player_lane - lane,
                    intent="braking" if i == 0 else rng.choice(("following", "cruising")),
                    vehicle_class=rng.choice(("car", "car", "semi", "box truck")),
                    lane=lane,
                )
            )
        self.vehicles.extend(added)
        self.vehicles.sort(key=lambda vehicle: vehicle.position_mi)

    def vehicle_in_lane(
        self,
        position_mi: float,
        lane: int,
        *,
        ahead_mi: float = 0.35,
        behind_mi: float = 0.15,
        horizon_hr: float = 0.0,
        speed_mph: float = 0.0,
    ) -> TrafficVehicle | None:
        """The nearest vehicle occupying ``lane`` beside or just ahead of the
        player -- the mirror check before a lane change or a hazard dodge.

        With ``horizon_hr`` the check also sweeps each vehicle's relative
        motion against the player's ``speed_mph`` over that much game time:
        a vehicle outside the window now but inside it before the horizon
        runs out holds the lane. This is how a clearance read stays true for
        the seconds a driver spends acting on it -- traffic keeps moving on
        compressed game time the whole while."""
        nearest: TrafficVehicle | None = None
        nearest_gap = float("inf")
        for vehicle in self.vehicles:
            if vehicle.lane != lane:
                continue
            gap = vehicle.position_mi - position_mi
            later = gap + (vehicle.speed_mph - speed_mph) * horizon_hr
            if min(gap, later) <= ahead_mi and max(gap, later) >= -behind_mi - vehicle.length_mi:
                distance = abs(max(0.0, gap))
                if distance < nearest_gap:
                    nearest, nearest_gap = vehicle, distance
        return nearest

    def pack_neighbours(
        self,
        position_mi: float,
        speed_mph: float,
        *,
        radius_mi: float,
        tolerance_mph: float,
    ) -> int:
        """Civilian vehicles close by and holding roughly the truck's speed.

        This is traffic cover. A truck alone on an empty road is the only
        thing to look at; a truck in the middle of a pack all doing the same
        speed is one of several, and real speed enforcement picks one. Marked
        units do not count as cover, for reasons that should not need saying.
        """
        count = 0
        for vehicle in self.vehicles:
            if getattr(vehicle, "vehicle_class", "") == "state trooper":
                continue
            if abs(vehicle.position_mi - position_mi) > radius_mi:
                continue
            if abs(vehicle.speed_mph - speed_mph) <= tolerance_mph:
                count += 1
        return count

    def _leg_at(self, mile: float) -> Leg | None:
        """The leg the given route mile falls in."""
        found: Leg | None = None
        for start, leg in zip(self.leg_starts, self.route.legs, strict=False):
            if mile + 1e-9 >= start:
                found = leg
            else:
                break
        return found

    def _leg_and_offset_at(self, mile: float) -> tuple[Leg, float] | None:
        """The leg a route mile falls in, and how far into that leg it is.

        The offset is leg-relative and direction-aware, because a leg driven
        from b to a reads its baked samples from the far end.
        """
        found: tuple[Leg, float] | None = None
        for index, (start, leg) in enumerate(zip(self.leg_starts, self.route.legs, strict=False)):
            if mile + 1e-9 >= start:
                offset = max(0.0, min(leg.miles, mile - start))
                forward = self.route.cities[index] == leg.a
                found = (leg, offset if forward else leg.miles - offset)
            else:
                break
        return found

    def _posted_limit_at(self, mile: float) -> float:
        """The posted limit for a car here.

        Deliberately the posted number rather than the truck cap: in a split
        limit state the cars going by a rig held to 55 are doing the legal 65,
        and that difference is the traffic the player hears.
        """
        found = self._leg_and_offset_at(mile)
        if found is None:
            return DEFAULT_LIMIT_MPH
        leg, offset = found
        baked = _leg_speed_limit_at(leg, offset)
        if baked is not None:
            return baked
        return corridor_speed_limit(leg.highway, "")

    def _floor_speed(self, limit_mph: float) -> float:
        """The slowest a moving vehicle gets here from speed draws alone."""
        return max(TRAFFIC_MIN_SPEED_MPH, limit_mph * TRAFFIC_MIN_SPEED_SHARE)

    def _intent_speed(self, intent: str, limit_mph: float, rng: random.Random) -> float:
        """A speed for this intent on a road posted at ``limit_mph``."""
        low, high = TRAFFIC_SPEED_OFFSETS_MPH[intent]
        return limit_mph + rng.uniform(low, high)

    def _cell_rng(self, cell: int) -> random.Random:
        """A generator belonging to one cell of road.

        Keyed on the route and seed like every other draw here, plus the cell
        index, so the same trip replayed puts the same vehicle in the same
        place -- the world has to load offline and behave identically twice.
        """
        digest = hashlib.sha256(f"{self._seed_key()}:cell:{cell}".encode()).hexdigest()
        return random.Random(int(digest[:16], 16))

    def _replenish(self, position_mi: float) -> None:
        """Fill the window around the truck, ahead and behind.

        Behind matters as much as ahead. The old model only ever placed
        vehicles in front, so the road could overtake nobody -- and being
        overtaken is most of what traffic sounds like from a truck holding 60
        in the right lane.
        """
        if not self.rolling_bubble or len(self.vehicles) >= MAX_BUBBLE_VEHICLES:
            return
        low = max(0.0, position_mi - BUBBLE_BEHIND_MI)
        high = min(self.route.miles, position_mi + BUBBLE_AHEAD_MI)
        occupied = {int(vehicle.position_mi / SPAWN_CELL_MI) for vehicle in self.vehicles}
        night = is_night(self.hour)
        weather_slowdown = self._weather_slowdown()
        for cell in range(int(low / SPAWN_CELL_MI), int(high / SPAWN_CELL_MI) + 1):
            if cell in self._spawned_cells:
                continue
            self._spawned_cells.add(cell)
            if cell in occupied or len(self.vehicles) >= MAX_BUBBLE_VEHICLES:
                continue
            rng = self._cell_rng(cell)
            # Draw the place inside the cell BEFORE the clear-air test. Testing
            # the cell's own mile and then offsetting by up to a cell width put
            # vehicles back inside the zone the test was meant to keep empty.
            mile = cell * SPAWN_CELL_MI + rng.uniform(0.0, SPAWN_CELL_MI)
            if -NO_SPAWN_BEHIND_MI < mile - position_mi < NO_SPAWN_AHEAD_MI:
                continue
            leg = self._leg_at(mile)
            if leg is None:
                continue
            # Density is a share of road, so it reads directly as the chance
            # this cell of it is carrying somebody.
            if rng.random() > self._leg_density(leg, night, mile):
                continue
            behind = mile < position_mi
            # Somebody behind you is somebody who is going to pass you, so the
            # draw back there favours the faster intents. Ahead keeps the old
            # spread, where slower vehicles are what you come up on.
            if behind:
                intent = rng.choices(("passing", "cruising"), weights=(3.0, 1.0))[0]
            elif mile < MERGE_FREE_START_MI:
                # Pulling out of a gate, the bubble's nearest cell is 1.1
                # miles ahead, and a merging vehicle drawn there made a merge
                # warning the first thing a driver heard on a run they had
                # not started moving on (owner report, 2026-08-16). The
                # vehicle still spawns; it is just not merging into you
                # before you are up to speed. Keyed off the mile rather than
                # the truck's position so it covers the on-ramp handback
                # too, which rejoins the highway trip at mile zero.
                intent = rng.choices(
                    ("cruising", "following", "braking", "passing"),
                    weights=(3.0, 1.5, 1.0, 0.6),
                )[0]
            else:
                # Merging and braking only where the road gives a reason for
                # them; their weight goes back to plain travelling elsewhere,
                # which is what almost everything on a highway is doing.
                options = ["cruising", "following", "passing"]
                weights = [3.0, 1.5, 0.6]
                if self._merge_plausible_at(mile):
                    options.append("merging")
                    weights.append(1.2)
                if self._braking_plausible_at(mile):
                    options.append("braking")
                    weights.append(1.0)
                intent = rng.choices(options, weights=weights)[0]
            vehicle_class = rng.choices(
                ("car", "box truck", "semi", "service vehicle"),
                weights=(5.0, 1.4, 2.0, 0.3),
            )[0]
            limit_mph = self._posted_limit_at(mile)
            base_speed = self._intent_speed(intent, limit_mph, rng)
            rush_slowdown = rng.uniform(4.0, 10.0) if self._rush_hour_traffic_bias(leg) else 0.0
            speed = max(self._floor_speed(limit_mph), base_speed - weather_slowdown - rush_slowdown)
            lane = 1 if intent == "passing" else 0
            self.vehicles.append(
                TrafficVehicle(
                    key=f"bubble:{cell}",
                    position_mi=mile,
                    speed_mph=speed,
                    target_speed_mph=speed,
                    relative_lane=-lane,
                    intent=intent,
                    vehicle_class=vehicle_class,
                    lane=lane,
                    exit_at_mi=mile + rng.uniform(EXIT_AFTER_MIN_MI, EXIT_AFTER_MAX_MI),
                )
            )

    def update(
        self,
        *,
        dt: float,
        position_mi: float,
        time_scale: float,
        hour: float | None = None,
        weekend: bool | None = None,
    ) -> None:
        if hour is not None:
            self.hour = hour
        if weekend is not None:
            self._weekend = weekend
        game_hours = dt * time_scale / 3600.0
        kept: list[TrafficVehicle] = []
        for vehicle in self.vehicles:
            gap = vehicle.position_mi - position_mi
            intent = self._vehicle_intent(vehicle)
            vehicle.relative_lane = self.player_lane - vehicle.lane
            if intent == "braking" and 0.0 <= gap <= 1.8:
                # Inside a zone the pace is the zone's own prevailing speed,
                # not the generic 45-percent-of-posted floor. The generic
                # floor sits at 25 on a 55 corridor whose heavy-traffic zone
                # posts 45 -- so the injected braking lead, which never takes
                # an exit, ratcheted down to 25 and parked the speed keeper
                # there for the rest of a zone that had just announced
                # "traffic slowing to 45" (Brandon, 2026-08-20). The zone's
                # number is what its own AADT math says traffic is doing
                # here, so a braking vehicle converges on it from either
                # side.
                pace = self._zone_pace_at(vehicle.position_mi)
                if pace is not None:
                    vehicle.target_speed_mph = pace
                else:
                    vehicle.target_speed_mph = max(
                        self._floor_speed(self._posted_limit_at(vehicle.position_mi)),
                        vehicle.target_speed_mph - 8.0 * dt,
                    )
            elif intent in ("merging", "braking"):
                # Merging and braking are TRANSIENT states, not careers. The
                # spawn-time target (8 to 22 under the limit) used to be
                # permanent, so a semi "getting onto the highway" ran ramp
                # speed for the rest of its life -- a rolling blockade on
                # the open road (Brandon, 2026-08-20). A real merger builds
                # to road speed once the lane change is done; a braking car
                # recovers when whatever it braked for has passed. Inside a
                # heavy-traffic zone the recovery caps at the zone's own
                # pace, never the posted limit.
                pace = self._zone_pace_at(vehicle.position_mi)
                cruise = (
                    pace if pace is not None else self._posted_limit_at(vehicle.position_mi) + 1.0
                )
                if vehicle.target_speed_mph < cruise:
                    vehicle.target_speed_mph = min(cruise, vehicle.target_speed_mph + 4.0 * dt)
            delta = vehicle.target_speed_mph - vehicle.speed_mph
            vehicle.speed_mph += max(-6.0 * dt, min(4.0 * dt, delta))
            vehicle.position_mi += max(0.0, vehicle.speed_mph) * game_hours
            # getattr, for the reason lead_vehicle already gives: the harness
            # and the trip's own NPCVehicle share this runtime surface without
            # carrying the dataclass, so they have no exit mile to read.
            exit_at = getattr(vehicle, "exit_at_mi", None)
            if exit_at is not None and vehicle.position_mi >= exit_at:
                continue  # took its exit
            if vehicle.position_mi - position_mi >= -2.0:
                kept.append(vehicle)
        self.vehicles = kept
        self._replenish(position_mi)
        self.vehicles.sort(key=lambda vehicle: vehicle.position_mi)

    def next_situation(
        self, *, position_mi: float, truck_speed_mph: float
    ) -> TrafficSituation | None:
        context = self.lead_vehicle(
            position_mi=position_mi,
            truck_speed_mph=truck_speed_mph,
        )
        if context is None or context.gap_mi > 2.2:
            return None
        vehicle = context.lead
        if vehicle.key in self.announced_vehicle_keys:
            return None
        # getattr, not attribute access: the playtest harness and the trip's
        # own NPCVehicle share this runtime surface without carrying a class.
        if getattr(vehicle, "vehicle_class", "") == "state trooper":
            # A marked unit is a fact about the road, not an instruction: no
            # action follows from hearing it, so it is carried by an earcon
            # (see the driving layer's marked-unit pass) and never by a
            # sentence. The whole run's spoken enforcement budget is two
            # lines, and they are owed to things that cost money.
            return None
        gap = self._gap_text(context.gap_mi)
        speed = self._speed_value(vehicle.speed_mph)
        bare = self._speed_bare(vehicle.speed_mph)
        intent = self._vehicle_intent(vehicle)
        vehicle_class = self._vehicle_class(vehicle)
        if intent == "merging":
            message = merging_traffic_cue(vehicle_class, gap)
            kind = "merging"
        elif intent == "braking":
            cause = BRAKING_CAUSE_LINES.get(self._braking_reason_at(vehicle.position_mi), "")
            message = brake_lights_cue(gap, speed, bare, cause)
            kind = "braking"
        elif intent == "following":
            message = slow_lead_cue(vehicle_class, gap, speed, bare)
            kind = "following"
        else:
            return None
        self.announced_vehicle_keys.add(vehicle.key)
        # The number in a traffic cue is the lead's own speed, and from the
        # seat there is no way to check it: a cue that says "leave room for
        # 30" is either a vehicle really doing 30 or a cue quoting the wrong
        # thing, and they sound identical (playtest, 2026-08-15). Log what the
        # line was built from so the next one can be read back.
        log.info(
            "traffic cue %s: %s doing %.1f mph, gap %.2f mi, truck %.1f mph, mile %.2f",
            kind,
            vehicle_class,
            vehicle.speed_mph,
            context.gap_mi,
            truck_speed_mph,
            position_mi,
        )
        return TrafficSituation(kind, vehicle, message, interrupt=True)


__all__ = [
    "Leg",
    "RUSH_HOUR_WINDOWS",
    "TrafficManager",
    "TrafficSituation",
    "TrafficVehicle",
    "hashlib",
    "is_night",
    "random",
]
