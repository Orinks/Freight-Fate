"""Current-location details for the on-demand route report."""

from __future__ import annotations

from ..sim.trip import _spoken_short_miles
from ..sim.trip_models import _leg_state_at
from ..sim.trip_route_helpers import _leg_heading
from ..units import (
    MILES_TO_KM,
    spoken_feet_or_meters,
)

# Where the quarter-mile ladder runs out of anything honest to say: its own
# floor is "a quarter mile", which at 200 feet from the gate overstates the
# gap six times over. Below these the answer is feet, or metres where the
# 100-metre ladder bottoms out.
CLOSING_FEET_MI = 0.125
CLOSING_METERS_KM = 0.15

# A town this close to the road, and this close along it, is the town the
# truck is in rather than one it can see: the baked villages sit within a
# few hundred feet of the corridor when the highway runs straight through.
IN_TOWN_OFF_MI = 1.0
IN_TOWN_ALONG_MI = 1.5
# Past this there is no town worth naming. The bake keeps places out to
# eleven miles off an empty interstate on purpose, so the window is wide;
# beyond it "no town near here" is the more useful answer than a name the
# driver could not reach.
NEAREST_TOWN_MI = 30.0


def spoken_closing_distance(miles: float, imperial: bool) -> str:
    """How far to something still ahead, worded so it is never zero.

    ``Trip._distance_text`` rounds to whole units, so anything under half a
    mile spoke as "0 miles" -- and on surface streets at 25 mph the last half
    mile takes over a minute, all of it spent hearing that the gate is zero
    miles away (owner report, 2026-08-15). Quarter-mile steps take over under
    a mile and a bit, feet or metres under a quarter mile: the same ladder
    the pacenotes and the stop-bar countdown already speak.
    """
    miles = max(0.0, miles)
    short = miles < CLOSING_FEET_MI if imperial else miles * MILES_TO_KM < CLOSING_METERS_KM
    if short:
        return spoken_feet_or_meters(miles, imperial)
    return _spoken_short_miles(miles, imperial)


class DrivingLocationMixin:
    def _speak_route_status(self) -> None:
        # Deliberately short: how far along you are, how far to the thing you
        # are actually driving at, and where you are. Grade, zones, and the
        # next maneuver each have their own key, so repeating them here just
        # made drivers wait through a paragraph to hear where they were.
        #
        # Once the trip has ended at a facility gate, the leg readout below
        # would recite the abandoned route with a frozen countdown -- "3
        # miles remaining" that never move (playtest 2026-07-22). The only
        # honest route status left is the gate.
        gate = self._arrival_gate_query_text()
        if gate is not None:
            self.ctx.say(f"Route status: you have arrived. {gate}")
            return
        trip = self.trip
        # On the facility approach, the highway framing is a lie: the driver
        # heard "on I-90 West, 3 miles remaining" with a frozen countdown
        # while rolling city streets toward the gate (playtest 2026-07-22).
        # Both approach shapes answer with the gate distance instead.
        if self._surface_chain:
            self._say_local_status(f"the gate at {self._approach_facility_text()}")
            return
        if self._destination_exit_taken:
            self._say_local_status(
                self._approach_facility_text(),
                where="off the highway, on the facility approach",
            )
            return
        # Pulling out of the origin gate is city streets too, and the highway
        # readout below was just as wrong there: it read the two-mile street
        # chain's percent as the run's progress and pointed the driver
        # "toward" the city they were standing in (owner report, 2026-08-15).
        # What is actually ahead on that chain is the on-ramp.
        if self._departure_chain:
            self._say_local_status(self._departure_ramp_text())
            return
        # The pickup drive is a local approach from end to end -- there is no
        # highway leg under it to frame, and its route starts and ends in the
        # one city, so "toward" it says nothing.
        if trip._is_facility_approach_route():
            self._say_local_status(f"the gate at {self._approach_facility_text()}")
            return
        route = trip.route
        leg_index, leg_start = trip._leg_at_mile(trip.position_mi)
        leg = route.legs[leg_index]
        from_city = route.cities[leg_index]
        toward_city = route.cities[leg_index + 1]
        forward = from_city == leg.a
        leg_offset = max(0.0, min(leg.miles, trip.position_mi - leg_start))
        native_offset = leg_offset if forward else leg.miles - leg_offset

        heading = _leg_heading(leg.highway, from_city, toward_city)
        road = f"{leg.highway} {heading}".strip()
        world = self.ctx.world
        state = _leg_state_at(leg, native_offset) or world.cities[toward_city].state
        toward = world.spoken_city(toward_city, qualified=True)

        # Progress leads so a one-line braille display gets it without panning,
        # and the percent is the same figure the online drivers board shows.
        # A planned stop is the next place you actually mean to be, so it takes
        # the distance slot from the destination until you have passed it.
        planned = trip.planned_stop
        if planned is not None and planned.at_mi > trip.position_mi:
            ahead = self._closing_text(planned.at_mi - trip.position_mi)
            lead = f"{trip.progress_percent} percent there, {ahead} to {planned.spoken_name}."
        else:
            lead = (
                f"{trip.progress_percent} percent there, "
                f"{self._closing_text(trip.remaining_miles)} left."
            )
        self.ctx.say(f"{lead} On {road} in {state}, toward {toward}.")

    # --- One fact per key (Tim K., 2026-08-16) -------------------------
    #
    # R answers all of this in one sentence, which is the right shape when
    # you are orienting yourself and the wrong one when you want a single
    # fact at 65 miles an hour: you sit through the progress, the road and
    # the destination to hear the state. These four keys each speak one
    # thing and stop, so they are cheap to press twice and cheap to press
    # by mistake. They read the same data R does -- there is no second
    # source of truth for where the truck is.

    def _local_route_city(self) -> str:
        """The city a street route runs inside, or the run's destination."""
        cities = self.trip.route.cities
        return cities[0] if cities else ""

    def _on_local_streets(self) -> bool:
        """Whether the truck is on a street chain rather than a highway leg."""
        return bool(
            self._surface_chain
            or self._departure_chain
            or self._destination_exit_taken
            or self.trip._is_facility_approach_route()
        )

    def _highway_frame(self):
        """The leg under the wheels and where the truck sits in its native frame.

        Returns ``(leg, from_city, toward_city, native_offset)``, or None on a
        street chain or a route with no legs -- the callers each have their own
        honest answer for that case rather than a shared fallback sentence.
        """
        trip = self.trip
        route = trip.route
        if self._on_local_streets() or not route.legs:
            return None
        leg_index, leg_start = trip._leg_at_mile(trip.position_mi)
        leg = route.legs[leg_index]
        from_city = route.cities[leg_index]
        toward_city = route.cities[leg_index + 1]
        forward = from_city == leg.a
        leg_offset = max(0.0, min(leg.miles, trip.position_mi - leg_start))
        native_offset = leg_offset if forward else leg.miles - leg_offset
        return leg, from_city, toward_city, native_offset

    def _speak_current_state(self) -> None:
        """Alt+1: the state the truck is in, and nothing else."""
        world = self.ctx.world
        frame = self._highway_frame()
        if frame is None:
            city = self._local_route_city()
            state = world.cities[city].state if city in world.cities else ""
        else:
            leg, _from_city, toward_city, native_offset = frame
            state = _leg_state_at(leg, native_offset) or world.cities[toward_city].state
        self.ctx.say(f"In {state}." if state else "No state known here.")

    def _speak_current_road(self) -> None:
        """Alt+2: the road under the wheels, signed the way you would read it.

        On a street chain this is the street name, which is what "the road you
        are on" means there; where the approach has only generic access-road
        geometry there is no name to speak and saying so beats inventing one.
        """
        frame = self._highway_frame()
        if frame is None:
            street = self._street_under_the_wheels()
            self.ctx.say(f"On {street}." if street else "On the facility approach. No road name.")
            return
        leg, from_city, toward_city, _native_offset = frame
        heading = _leg_heading(leg.highway, from_city, toward_city)
        road = f"{leg.highway} {heading}".strip()
        self.ctx.say(f"On {road}." if road else "No road name here.")

    def _speak_current_town(self) -> None:
        """Alt+3: the town the truck is in, or the nearest one worth naming.

        The villages baked along each leg carry how far off the corridor they
        sit, which is what separates "you are in Pine" from "Fairfield is six
        miles off to your right" -- and the honest answer on an empty stretch
        is that there is no town, said out loud rather than left as silence.
        """
        frame = self._highway_frame()
        if frame is None:
            city = self._local_route_city()
            spoken = self.ctx.world.spoken_city(city, qualified=True) if city else ""
            self.ctx.say(f"In {spoken}." if spoken else "No town known here.")
            return
        leg, from_city, _toward_city, native_offset = frame
        forward = from_city == leg.a
        # Ranked by how far the town actually is, not by how far along the
        # road it sits: a place 200 feet ahead and five miles off is further
        # away than one two miles up the road and right on it, and "nearest"
        # has to mean nearest.
        nearest = None
        for landmark in leg.landmarks:
            if landmark.category != "village":
                continue
            along = landmark.at_mi - native_offset
            away = (along**2 + landmark.off_mi**2) ** 0.5
            if nearest is None or away < nearest[0]:
                nearest = (away, along, landmark)
        if nearest is None or nearest[0] > NEAREST_TOWN_MI:
            self.ctx.say("No town near here.")
            return
        _away, along, landmark = nearest
        off_road = landmark.off_mi
        if abs(along) <= IN_TOWN_ALONG_MI and off_road <= IN_TOWN_OFF_MI:
            self.ctx.say(f"In {landmark.name}.")
            return
        off = f"{self._closing_text(off_road)} off the road" if off_road >= 0.1 else ""
        if abs(along) <= IN_TOWN_ALONG_MI:
            # Level with it: "two miles ahead" would be a distance the driver
            # covers in seconds and then still not be there.
            where = off or "right beside the road"
        else:
            # Ahead or behind is read in the direction of travel, not the
            # leg's native frame: on a leg driven b-to-a those are opposites,
            # and the word has to match the mirror.
            past = along < 0 if forward else along > 0
            where = f"{self._closing_text(abs(along))} {'back' if past else 'ahead'}"
            if off:
                where = f"{where}, {off}"
        self.ctx.say(f"Nearest town, {landmark.name}: {where}.")

    def _speak_current_direction(self) -> None:
        """Alt+4: the direction of travel, worded the way the shields are.

        The signed direction, not a compass bearing: I-95 out of New York is
        signed South while the geometry trends southwest, and the driver is
        placing themselves against the signs. A street chain has no signed
        direction at all, and saying so is better than rounding one up.
        """
        frame = self._highway_frame()
        if frame is None:
            self.ctx.say("On city streets. No signed direction here.")
            return
        leg, from_city, toward_city, _native_offset = frame
        heading = _leg_heading(leg.highway, from_city, toward_city)
        self.ctx.say(f"{heading}bound." if heading else "No signed direction here.")

    def _say_local_status(self, target: str, where: str | None = None) -> None:
        """One route report for a local street route: where the truck is,
        what it is actually driving at, and the next maneuver if one is
        left. Sentences that come up empty are dropped rather than spoken
        as a gap."""
        # No next-maneuver clause. On streets the event voice announces every
        # turn as it arrives, so including it here meant R re-read, on the
        # screen reader, the line the event voice had just delivered (owner,
        # 2026-08-17). The highway readout above dropped the maneuver for
        # exactly this reason and said so in its own comment; the street
        # readout kept it, and that inconsistency is the bug.
        parts = (
            f"Route status: {self._local_where_text() if where is None else where}.",
            f"{self._closing_text(self.trip.remaining_miles)} to {target}.",
        )
        self.ctx.say(" ".join(part for part in parts if part))

    def _closing_text(self, miles: float) -> str:
        """A distance to something the truck has not reached yet."""
        return spoken_closing_distance(miles, self.trip.imperial)

    def _street_under_the_wheels(self) -> str:
        """The road the truck is on right now, when that road is a street.

        Read at the truck's own position rather than off the chain's first
        leg, so a report taken three turns in names the street being driven
        and not the one the chain started on. Empty on a route with no baked
        street geometry -- a synthetic one-leg approach has only the generic
        "facility access road", which is not a street name and must not be
        spoken as one.
        """
        trip = self.trip
        if not trip.route.legs:
            return ""
        leg_index, _ = trip._leg_at_mile(trip.position_mi)
        leg = trip.route.legs[leg_index]
        if leg.local_speed_mph <= 0 and not leg.local_cue:
            return ""
        return leg.highway

    def _local_where_text(self) -> str:
        """Where the truck is on a local street route, spoken."""
        city = self.ctx.world.spoken_city(self.trip.route.cities[0], qualified=True)
        street = self._street_under_the_wheels()
        if street:
            return f"on city streets, {street}, in {city}"
        return f"on the facility approach in {city}"

    def _departure_ramp_text(self) -> str:
        """What the departure chain is actually driving at: its on-ramp.

        Named the same way the chain's own opening line names it, so the two
        do not read as two different places.
        """
        highway = self._highway_trip
        legs = highway.route.legs if highway is not None else ()
        if legs:
            return f"the {legs[0].highway} on-ramp"
        return "the highway on-ramp"

    def _approach_facility_text(self) -> str:
        from .driving_core import DRIVE_PHASE_PICKUP

        if self.phase == DRIVE_PHASE_PICKUP:
            return self._pickup_facility_text()
        return self._destination_facility_text()
