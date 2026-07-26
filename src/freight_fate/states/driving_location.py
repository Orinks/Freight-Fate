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
        trip = self.trip
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
