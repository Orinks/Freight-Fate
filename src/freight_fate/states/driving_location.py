"""Current-location details for the on-demand route report."""

from __future__ import annotations

from ..sim.trip_models import _leg_state_at
from ..sim.trip_route_helpers import _leg_heading


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
            leg_index, _ = trip._leg_at_mile(trip.position_mi)
            street = trip.route.legs[leg_index].highway
            self.ctx.say(
                f"Route status: on city streets, {street}, in "
                f"{self.ctx.world.spoken_city(trip.route.cities[-1], qualified=True)}. "
                f"{trip._distance_text(trip.remaining_miles)} to the gate at "
                f"{self._approach_facility_text()}. "
                f"{trip.next_navigation_context(self.ctx.settings.imperial_units)}"
            )
            return
        if self._destination_exit_taken:
            self.ctx.say(
                "Route status: off the highway, on the facility approach. "
                f"{trip._distance_text(trip.remaining_miles)} to "
                f"{self._approach_facility_text()}. "
                f"{trip.next_navigation_context(self.ctx.settings.imperial_units)}"
            )
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
            ahead = trip._distance_text(planned.at_mi - trip.position_mi)
            lead = f"{trip.progress_percent} percent there, {ahead} to {planned.spoken_name}."
        else:
            lead = f"{trip.progress_percent} percent there, {trip._distance_text(trip.remaining_miles)} left."
        self.ctx.say(f"{lead} On {road} in {state}, toward {toward}.")

    def _approach_facility_text(self) -> str:
        from .driving_core import DRIVE_PHASE_PICKUP

        if self.phase == DRIVE_PHASE_PICKUP:
            return self._pickup_facility_text()
        return self._destination_facility_text()
