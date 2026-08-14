"""Small NPC traffic bubble around the player's truck."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from ..data.world import Leg, Route
from ..speech_text import brake_lights_cue, merging_traffic_cue, slow_lead_cue
from .hos import is_night
from .trip_models import (
    RUSH_HOUR_WINDOWS,
    TRAFFIC_LOOKAHEAD_MI,
    TrafficContext,
)

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
# How far a bubble vehicle runs before it leaves the highway, drawn per
# vehicle. Nobody shares a whole corridor with you, and the upper end is what
# bounds how long a slow one can hold the lane in front of the truck.
EXIT_AFTER_MIN_MI = 2.5
EXIT_AFTER_MAX_MI = 11.0


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
        # The driving state mirrors the player's discrete lane here each
        # frame so same-lane checks and spoken relative lanes stay honest.
        self.player_lane = 0

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

    def _leg_density(self, leg: Leg, night: bool) -> float:
        """How much of this road is carrying somebody, 0 to 1.

        Deliberately reads nothing from ``hazard_scale``, on the rule the
        enforcement layer already settled for police: presence is not
        difficulty, and the road has the traffic it has. That knob is
        ``hos.hazard_scale(mode)`` times the time-scale tuning's
        ``hazard_frequency`` -- a difficulty setting multiplied by a
        compression setting, neither of which is a statement about how many
        vehicles exist. Together they were landing at 0.11 on an ordinary
        run, cutting a busy interstate to a 5 percent chance of company per
        cell, and the compression half had it exactly backwards: at ten times
        pacing the truck covers ten times the ground in a real minute and
        should meet MORE traffic, not less.

        Difficulty still reaches the player where it belongs -- on random
        hazards, and on which vehicles are worth interrupting them about.
        """
        metro_bias = 0.18 if leg.checkpoints else 0.0
        night_bias = -0.08 if night else 0.0
        rush_bias = self._rush_hour_traffic_bias(leg)
        return min(
            0.86,
            max(
                0.05,
                0.22 + leg.miles / 900.0 + metro_bias + night_bias + rush_bias,
            ),
        )

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
                base_speed = {
                    "cruising": rng.uniform(52.0, 64.0),
                    "following": rng.uniform(42.0, 55.0),
                    "merging": rng.uniform(38.0, 52.0),
                    "braking": rng.uniform(35.0, 48.0),
                    "passing": rng.uniform(62.0, 75.0),
                }[intent]
                rush_slowdown = rng.uniform(4.0, 10.0) if self._rush_hour_traffic_bias(leg) else 0.0
                speed = max(25.0, base_speed - weather_slowdown - rush_slowdown)
                # Passing traffic lives in the left lane; everyone else --
                # including vehicles merging in from a ramp -- holds the
                # right lane, where trucks are supposed to be.
                lane = 1 if intent == "passing" else 0
                vehicles.append(
                    TrafficVehicle(
                        key=f"traffic:{leg_index}:{slot}:{intent}",
                        position_mi=start + rng.uniform(low, high),
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
            speed = 62.0
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
        nearest: tuple[float, TrafficVehicle] | None = None
        for vehicle in self.vehicles:
            if vehicle.lane != self.player_lane:
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
            if rng.random() > self._leg_density(leg, night):
                continue
            behind = mile < position_mi
            # Somebody behind you is somebody who is going to pass you, so the
            # draw back there favours the faster intents. Ahead keeps the old
            # spread, where slower vehicles are what you come up on.
            if behind:
                intent = rng.choices(("passing", "cruising"), weights=(3.0, 1.0))[0]
            else:
                intent = rng.choices(
                    ("cruising", "following", "merging", "braking", "passing"),
                    weights=(3.0, 1.5, 1.2, 1.0, 0.6),
                )[0]
            vehicle_class = rng.choices(
                ("car", "box truck", "semi", "service vehicle"),
                weights=(5.0, 1.4, 2.0, 0.3),
            )[0]
            base_speed = {
                "cruising": rng.uniform(52.0, 64.0),
                "following": rng.uniform(42.0, 55.0),
                "merging": rng.uniform(38.0, 52.0),
                "braking": rng.uniform(35.0, 48.0),
                "passing": rng.uniform(66.0, 78.0),
            }[intent]
            rush_slowdown = rng.uniform(4.0, 10.0) if self._rush_hour_traffic_bias(leg) else 0.0
            speed = max(25.0, base_speed - weather_slowdown - rush_slowdown)
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
        self, *, dt: float, position_mi: float, time_scale: float, hour: float | None = None
    ) -> None:
        if hour is not None:
            self.hour = hour
        game_hours = dt * time_scale / 3600.0
        kept: list[TrafficVehicle] = []
        for vehicle in self.vehicles:
            gap = vehicle.position_mi - position_mi
            intent = self._vehicle_intent(vehicle)
            vehicle.relative_lane = self.player_lane - vehicle.lane
            if intent == "braking" and 0.0 <= gap <= 1.8:
                vehicle.target_speed_mph = max(30.0, vehicle.target_speed_mph - 8.0 * dt)
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
            message = brake_lights_cue(gap, speed, bare)
            kind = "braking"
        elif intent == "following":
            message = slow_lead_cue(vehicle_class, gap, speed, bare)
            kind = "following"
        else:
            return None
        self.announced_vehicle_keys.add(vehicle.key)
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
