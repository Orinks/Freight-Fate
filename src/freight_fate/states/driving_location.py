"""Current-location details for the on-demand route report."""

from __future__ import annotations

from ..sim.trip import _spoken_short_miles
from ..sim.trip_models import _leg_state_at
from ..sim.trip_route_helpers import _leg_heading
from ..units import (
    MILES_TO_KM,
    distance_unit,
    spoken_distance,
    spoken_feet_or_meters,
    to_distance,
)

# Where the quarter-mile ladder runs out of anything honest to say: its own
# floor is "a quarter mile", which at 200 feet from the gate overstates the
# gap six times over. Below these the answer is feet, or metres where the
# 100-metre ladder bottoms out.
CLOSING_FEET_MI = 0.125
CLOSING_METERS_KM = 0.15


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

    def _say_local_status(self, target: str, where: str | None = None) -> None:
        """One route report for a local street route: where the truck is,
        what it is actually driving at, and the next maneuver if one is
        left. Sentences that come up empty are dropped rather than spoken
        as a gap."""
        parts = (
            f"Route status: {self._local_where_text() if where is None else where}.",
            f"{self._closing_text(self.trip.remaining_miles)} to {target}.",
            self._navigation_context(),
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

    def _navigation_context(self) -> str:
        """``Trip.next_navigation_context`` with its distance re-spoken.

        The trip's own wording rounds to whole units, so a turn 300 feet out
        announced itself as "in 0 miles" -- the same complaint that started
        this, one clause later. This swaps the exact substring the trip built
        for the closing-ladder form, which keeps one formatter for the whole
        sentence and quietly becomes a no-op the day the trip layer speaks
        short distances itself.
        """
        imperial = self.ctx.settings.imperial_units
        cue = self.trip.next_navigation_cue()
        if cue is None:
            # Out of maneuvers on the way OUT of a gate, the trip's fallback
            # names the city as the destination -- "Destination Rochester
            # ahead" while pulling out of Rochester. The sentence before this
            # one has already named the on-ramp, which is the true answer.
            if self._departure_chain:
                return ""
            return self.trip.next_navigation_context(imperial)
        text = self.trip.next_navigation_context(imperial)
        ahead = max(0.0, cue.at_mi - self.trip.position_mi)
        rounded = spoken_distance(
            to_distance(ahead, imperial), distance_unit(imperial, plural=False)
        )
        closing = spoken_closing_distance(ahead, imperial)
        return text.replace(rounded, closing, 1) if closing != rounded else text

    def _approach_facility_text(self) -> str:
        from .driving_core import DRIVE_PHASE_PICKUP

        if self.phase == DRIVE_PHASE_PICKUP:
            return self._pickup_facility_text()
        return self._destination_facility_text()
