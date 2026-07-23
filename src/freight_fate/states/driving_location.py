"""Current-location details for the on-demand route report."""

from __future__ import annotations

from ..sim.trip_models import _leg_state_at
from ..sim.trip_route_helpers import _leg_heading, _stop_offset_for_direction


class DrivingLocationMixin:
    def _speak_route_status(self) -> None:
        trip = self.trip
        # A route that ended at a gate answers with the gate, not a highway
        # that no longer exists (same precedent as the S key's override).
        gate = self._arrival_gate_query_text()
        if gate is not None:
            self.ctx.say(f"Route status: {gate}")
            return
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
        place_text = self._nearest_named_place(leg_index, leg_start, forward)
        _, zone_reason = trip.speed_limit_at(trip.position_mi)
        zone_text = f" You are in a {zone_reason} zone." if zone_reason else ""

        next_context = trip.next_navigation_context(self.ctx.settings.imperial_units)
        self.ctx.say(
            f"Route status: on {road} in {state}, heading toward {toward}. "
            f"{place_text}{zone_text} "
            f"{trip._distance_text(trip.position_mi)} into the trip; "
            f"{trip._distance_text(trip.remaining_miles)} remaining of "
            f"{trip._distance_text(trip.total_miles)}. "
            f"{trip._current_grade_text()}. {next_context}"
        )

    def _approach_facility_text(self) -> str:
        from .driving_core import DRIVE_PHASE_PICKUP

        if self.phase == DRIVE_PHASE_PICKUP:
            return self._pickup_facility_text()
        return self._destination_facility_text()

    def _nearest_named_place(self, leg_index: int, leg_start: float, forward: bool) -> str:
        trip = self.trip
        route = trip.route
        leg = route.legs[leg_index]
        leg_end = leg_start + leg.miles
        world = self.ctx.world
        candidates = [
            (leg_start, world.spoken_city(route.cities[leg_index], qualified=True)),
            (leg_end, world.spoken_city(route.cities[leg_index + 1], qualified=True)),
        ]
        for checkpoint in leg.checkpoints:
            mile = leg_start + _stop_offset_for_direction(checkpoint.at_mi, leg.miles, forward)
            name = checkpoint.name
            if checkpoint.state and checkpoint.state.casefold() not in name.casefold():
                name = f"{name}, {checkpoint.state}"
            candidates.append((mile, name))
        for stop in trip.stops:
            if leg_start <= stop.at_mi <= leg_end:
                candidates.append((stop.at_mi, stop.spoken_name))

        place_mile, place = min(
            candidates,
            key=lambda candidate: abs(candidate[0] - trip.position_mi),
        )
        offset = place_mile - trip.position_mi
        if abs(offset) <= 1.0:
            return f"Near {place}."
        direction = "ahead" if offset > 0 else "behind"
        return f"Nearest named place is {place}, {trip._distance_text(abs(offset))} {direction}."
