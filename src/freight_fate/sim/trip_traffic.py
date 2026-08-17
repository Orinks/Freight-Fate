"""Traffic and patrol lookup helpers for trip simulation."""

from __future__ import annotations

import logging
import random
import re

from ..data.world import Leg
from .enforcement_posts import (
    KIND_CHAIN,
    KIND_CMV,
    KIND_FIXED_SCALE,
    KIND_MEDIAN,
    KIND_ROVING,
    KIND_SCALE_APRON,
    KIND_URBAN,
    KIND_WORK_ZONE,
    EnforcementPost,
    post_seed,
)
from .trip_models import (
    CONSTRUCTION_TAPER_LIMIT_MPH,
    CONSTRUCTION_TAPER_MI,
    RUSH_HOUR_WINDOWS,
    TRAFFIC_PRESSURE_LOOKAHEAD_MI,
    ZONE_MIN_GAP_MI,
    NavigationCue,
    TrafficContext,
    TrafficPressure,
    TripEventKind,
    Zone,
    _leg_state_at,
)
from .trip_route_helpers import _nearest_mile_on_leg

log = logging.getLogger(__name__)

# Incident lookups filter the whole cached state feed by distance, so re-check
# on a mile cadence rather than every simulation tick.
REAL_TRAFFIC_CHECK_INTERVAL_MI = 1.0
REAL_TRAFFIC_RADIUS_MI = 50.0


class TripTrafficMixin:
    def traffic_context(self) -> TrafficContext | None:
        return self.traffic_manager.lead_vehicle(
            position_mi=self.position_mi,
            truck_speed_mph=self.truck.speed_mph,
        )

    def traffic_target_speed(self) -> float | None:
        context = self.traffic_context()
        if context is None:
            return None
        return context.lead.speed_mph

    def npc_traffic_status(self) -> str:
        context = self.traffic_context()
        if context is None:
            return "Traffic: no close traffic ahead."
        lead = context.lead
        lane = getattr(lead, "lane_text", "your lane")
        return (
            f"Traffic: {lead.reason} {self._gap_text(context.gap_mi)} ahead "
            f"in {lane}, moving {self._speed_text(lead.speed_mph)}."
        )

    def _check_npc_traffic_cues(self) -> None:
        # Gate BEFORE next_situation: returning a situation marks its vehicle
        # announced, so a gated call would burn the announcement without
        # speaking it and the vehicle would stay silent forever (see
        # road_event_pacing.py).
        if not self._event_breather.ready("traffic"):
            return
        situation = self.traffic_manager.next_situation(
            position_mi=self.position_mi,
            truck_speed_mph=self.truck.speed_mph,
        )
        if situation is None:
            return
        self._event_breather.spoke("traffic")
        lead = situation.vehicle
        cue = NavigationCue(
            f"npc:{lead.key}", "traffic", lead.position_mi, lead.reason, speed_mph=lead.speed_mph
        )
        self._emit(TripEventKind.GPS_CUE, situation.message, cue=cue, npc_vehicle=lead)

    # -- CB chatter ----------------------------------------------------------
    # "Bear" is CB voice. It may appear only inside a clause the line
    # attributes to the CB, never in a warning, a menu, or a status readout,
    # where the word is "trooper". tests/test_enforcement_presence.py asserts
    # this over every player-facing string in src/.

    def _cb_confidence(self, post: EnforcementPost) -> str:
        """How firmly the channel is standing behind this report.

        A blind player cannot look out of the window and falsify a CB call, so
        an unreliable channel has to carry its unreliability in the words --
        a silently wrong report is indistinguishable from a bug, and the
        rational response to that is to stop trusting the channel at all.
        Confidence rides the attribution verb and the corroboration count, and
        nothing else: no percentages, no meta-commentary.

        Wrong in one direction only. The CB may call a post that turns out to
        be empty; that costs a needless lift off the throttle. It may never
        say the road is clear, because silence is the only honest way to
        report nothing heard.
        """
        rolled = random.Random(post_seed(self._seed, post.id, "cb_confidence")).random()
        if post.staffed:
            return "strong" if rolled < 0.55 else "ordinary"
        return "thin" if rolled < 0.7 else "ordinary"

    @staticmethod
    def _cb_side(post: EnforcementPost) -> str:
        """Where on the road the CB says it is. Words, never pan alone."""
        return {
            KIND_MEDIAN: "in the median",
            KIND_ROVING: "working with traffic",
            KIND_WORK_ZONE: "in the work zone",
            KIND_SCALE_APRON: "on the scale apron",
            KIND_FIXED_SCALE: "at the scale",
            KIND_URBAN: "coming into town",
            KIND_CMV: "on the right shoulder",
            KIND_CHAIN: "at the chain-up area",
        }.get(post.kind, "up ahead")

    def cb_patrol_message(self, post: EnforcementPost, ahead_mi: float) -> str:
        """Player-facing CB chatter for one enforcement post.

        Terse speech keeps the fact, the distance and the side, and drops the
        advice tail -- that tail is what made the old line eighteen words, and
        therefore longer than the window it had to be heard in.

        The confidence framing (two drivers / one driver / somebody a while
        back) is the same for every post kind -- that is what the channel's
        reliability rides on. What differs is what the post actually is: a
        patrol or speed post still calls a bear, a work zone is drivers
        talking about enforcement working the zone rather than a trooper
        sighting, a scale or a commercial-vehicle unit is chatter about
        logs (and, for the commercial-vehicle unit, equipment) being
        checked, and a chain control is chatter about chains being
        checked at the grade. Bear stays CB slang for a trooper on the
        open road, never for a fixed inspection facility or a chain
        checkpoint (docs/ontology.md).
        """
        distance = self._ahead_text(max(0.0, ahead_mi))
        confidence = self._cb_confidence(post)
        side = self._cb_side(post)
        if post.kind == KIND_WORK_ZONE:
            if confidence == "strong":
                return f"CB chatter, {distance}: two drivers say troopers are working {side}."
            if confidence == "ordinary":
                return f"CB chatter, {distance}: a driver says troopers are working {side}."
            return f"CB chatter: somebody said troopers were working {side} a while back."
        if post.kind in (KIND_SCALE_APRON, KIND_FIXED_SCALE):
            if confidence == "strong":
                return f"CB chatter, {distance}: two drivers say they're checking logs {side}."
            if confidence == "ordinary":
                return f"CB chatter, {distance}: a driver says they're checking logs {side}."
            return f"CB chatter: somebody said they were checking logs {side} a while back."
        if post.kind == KIND_CMV:
            if confidence == "strong":
                return (
                    f"CB chatter, {distance}: two drivers say they're checking "
                    f"logs and equipment {side}."
                )
            if confidence == "ordinary":
                return (
                    f"CB chatter, {distance}: a driver says they're checking "
                    f"logs and equipment {side}."
                )
            return f"CB chatter: somebody said they were checking logs and equipment {side} a while back."
        if post.kind == KIND_CHAIN:
            if confidence == "strong":
                return (
                    f"CB chatter, {distance}: two drivers say the chain control "
                    f"is checking rigs {side}."
                )
            if confidence == "ordinary":
                return (
                    f"CB chatter, {distance}: a driver says the chain control "
                    f"is checking rigs {side}."
                )
            return f"CB chatter: somebody said the chain control was checking rigs {side} a while back."
        if confidence == "strong":
            return f"CB chatter, {distance}: two drivers call a bear {side}."
        if confidence == "ordinary":
            return f"CB chatter, {distance}: a driver reports a bear {side}."
        return f"CB chatter: somebody called a bear {side} a while back."

    def cb_tableau_message(self, post: EnforcementPost, ahead_mi: float) -> str:
        """CB chatter for a bear who already has somebody else stopped.

        Same confidence framing and distance/side slots as
        ``cb_patrol_message`` -- only the fact reported differs. Real CB
        wisdom, now mechanically true: see
        ``EnforcementPost.tableau_busy_at``, which stops this post's own
        catches for as long as the trooper is busy with the stop this line
        reports.
        """
        distance = self._ahead_text(max(0.0, ahead_mi))
        confidence = self._cb_confidence(post)
        side = self._cb_side(post)
        if confidence == "strong":
            return (
                f"CB chatter, {distance}: two drivers say a bear already has "
                f"somebody stopped {side}."
            )
        if confidence == "ordinary":
            return (
                f"CB chatter, {distance}: a driver says a bear already has somebody stopped {side}."
            )
        return f"CB chatter: somebody said a bear had somebody stopped {side} a while back."

    def cb_patrol_status(self, post: EnforcementPost, ahead_mi: float) -> str:
        """The on-demand road-ahead readout's enforcement clause.

        Reported at full detail whatever the enforcement-presence setting is.
        Presence governs ambience; it never withholds information the player
        asked a key for.
        """
        distance = self._ahead_text(max(0.0, ahead_mi))
        where = self._cb_side(post)
        if ahead_mi <= 0:
            return f"an enforcement post {where} on this stretch"
        return f"an enforcement post {where} in {distance}"

    def next_patrol_within(self, within_mi: float) -> EnforcementPost | None:
        """Nearest enforcement post at or ahead of the truck in the lookahead."""
        return self.next_post_within(within_mi)

    def _rush_hour_traffic_bias(self, leg: Leg) -> float:
        if not any(start <= self.start_hour < end for start, end in RUSH_HOUR_WINDOWS):
            return 0.0
        return 0.14 if leg.checkpoints else 0.06

    def traffic_pressure_at(self, mile: float | None = None) -> TrafficPressure | None:
        sample = self.position_mi if mile is None else mile
        active = [
            pressure
            for pressure in self.traffic_pressures
            if pressure.start_mi <= sample <= pressure.end_mi
        ]
        if not active:
            return None
        return max(active, key=lambda pressure: pressure.intensity)

    def _check_real_traffic_events(self) -> None:
        """Announce nearby real-time incidents from the state 511 APIs."""
        if self.traffic_provider is None:
            return
        if self.position_mi < self._next_real_traffic_check_mi:
            return
        self._next_real_traffic_check_mi = self.position_mi + REAL_TRAFFIC_CHECK_INTERVAL_MI

        leg_i, leg_start = self._leg_at_mile(self.position_mi)
        leg = self.route.legs[leg_i]
        if not leg.route_points:
            return
        forward = self.route.cities[leg_i] == leg.a
        route_offset = self.position_mi - leg_start
        leg_offset = route_offset if forward else leg.miles - route_offset

        state = _leg_state_at(leg, leg_offset)
        if not state:
            return
        point = min(leg.route_points, key=lambda rp: abs(rp.at_mi - leg_offset))

        try:
            events = self.traffic_provider.get_events_near(
                state,
                latitude=point.lat,
                longitude=point.lon,
                radius_mi=REAL_TRAFFIC_RADIUS_MI,
            )
        except Exception:
            # Gracefully handle API failures - real traffic is optional
            return

        for event in events:
            if event.severity not in ("high", "medium"):
                continue
            # Construction is spoken through the construction-zone system;
            # announcing it here too would flood the driver now that the
            # WZDx states return their whole work-zone feed from request().
            if event.event_type == "construction":
                continue
            event_key = f"real_traffic:{event.id}"
            if event_key in self._announced_real_traffic:
                continue
            message = f"Traffic alert: {event.description}"
            if event.lanes_affected:
                message += f". {event.lanes_affected} affected."
            self._emit(TripEventKind.GPS_CUE, message, real_traffic_event=event)
            self._announced_real_traffic.add(event_key)

    def next_traffic_pressure_within(
        self, within_mi: float = TRAFFIC_PRESSURE_LOOKAHEAD_MI
    ) -> TrafficPressure | None:
        candidates = [
            pressure
            for pressure in self.traffic_pressures
            if pressure.end_mi >= self.position_mi
            and 0 <= pressure.start_mi - self.position_mi <= within_mi
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda pressure: pressure.start_mi)

    def _collect_route_geometry(self) -> dict[str, tuple[str, list[tuple[float, float]]]]:
        """Build a dict of {highway: (state, [(lat, lon), ...])} from the route
        legs, so construction-zone snapping can check proximity in parallel."""
        geometry: dict[str, tuple[str, list[tuple[float, float]]]] = {}
        for i, (_, leg) in enumerate(zip(self._leg_starts, self.route.legs, strict=True)):
            forward = self.route.cities[i] == leg.a
            state = ""
            for sc in leg.state_crossings:
                state = sc.from_state if forward else sc.state
            state_miles = [sm for sm in leg.state_miles]
            if state_miles:
                first = state_miles[0] if forward else state_miles[-1]
                state = state or first.state

            points: list[tuple[float, float]] = []
            for rp in leg.route_points:
                points.append((rp.lat, rp.lon))

            normalized = leg.highway.strip().upper()
            if normalized not in geometry:
                geometry[normalized] = (state or "", points)
            else:
                existing_state, existing_points = geometry[normalized]
                existing_points.extend(points)
                if state and not existing_state:
                    geometry[normalized] = (state, existing_points)

        return geometry

    def _place_real_construction_zones(self) -> list[Zone]:
        """Query the traffic provider for real construction events and convert
        them into Zone objects mapped to route miles.

        Returns an empty list when no provider is available, the route is a
        facility approach, or no construction events are close enough to the
        route geometry.
        """
        if self.traffic_provider is None:
            return []
        if self._is_facility_approach_route():
            return []

        real_zones: list[Zone] = []
        seen_spans: list[tuple[float, float]] = []

        route_geo = self._collect_route_geometry()

        for highway, (state, points) in route_geo.items():
            if not state or not points:
                continue

            try:
                events = self.traffic_provider.get_construction_near_route(
                    state=state,
                    route_points=points,
                    road_name=highway,
                    radius_mi=3.0,
                )
            except Exception:
                log.debug(f"Failed to query construction for {highway} in {state}")
                events = []

            if not events:
                continue

            # Convert each construction event to a Zone
            for event in events:
                if event.latitude is None or event.longitude is None:
                    continue

                # Find the nearest leg and snap to route mile
                best_leg_mile: float | None = None
                for i, (start, leg) in enumerate(
                    zip(self._leg_starts, self.route.legs, strict=True)
                ):
                    forward = self.route.cities[i] == leg.a
                    snapped = _nearest_mile_on_leg(
                        event.latitude, event.longitude, leg, forward, start
                    )
                    if snapped is not None:
                        best_leg_mile = snapped
                        break

                if best_leg_mile is None:
                    continue

                # Determine zone length from API data or default
                zone_length = self._construction_zone_length(event)
                start_mi = max(0.0, best_leg_mile - zone_length / 2.0)
                end_mi = min(self.total_miles, start_mi + zone_length)
                start_mi = max(0.0, end_mi - zone_length)

                # A work zone the driver cannot be warned about is one the
                # game must not place. Invented zones draw from mile 15 and
                # so always have room for their taper; a real 511 event near
                # the start of the corridor used to clamp to zero, which put
                # the truck INSIDE the cones before it moved, with the taper
                # behind it where no announcement could ever reach (owner
                # report, 2026-08-16). This is not a no-hazard zone at the
                # start of a run: a zone at mile 5 signed from mile 4 is
                # untouched. The rule is only that the warning has to fit.
                if start_mi < CONSTRUCTION_TAPER_MI:
                    continue

                # Check overlap with previously placed real zones
                if any(
                    start_mi < s_end + ZONE_MIN_GAP_MI and end_mi > s_start - ZONE_MIN_GAP_MI
                    for s_start, s_end in seen_spans
                ):
                    continue

                # Determine speed limit for the construction zone
                limit_mph = self._construction_zone_speed(event)

                # Determine lane closure
                closed_side = self._construction_closed_side(event)

                # Create the zone pair (taper + work zone)
                taper_start = max(0.0, start_mi - CONSTRUCTION_TAPER_MI)
                # A reported closure still needs a lane to merge into. Where
                # the road runs one lane our side anywhere under the zone, the
                # work is announced with every lane open rather than pinning
                # the truck in a lane it cannot leave.
                if closed_side is not None and not self._span_is_multilane(taper_start, end_mi):
                    closed_side = None
                real_zones.append(
                    Zone(
                        taper_start,
                        start_mi,
                        CONSTRUCTION_TAPER_LIMIT_MPH,
                        "construction merge",
                        closed_side=closed_side,
                    )
                )
                real_zones.append(
                    Zone(
                        start_mi,
                        end_mi,
                        limit_mph,
                        "construction",
                        closed_side=closed_side,
                    )
                )
                seen_spans.append((taper_start, end_mi))

        real_zones.sort(key=lambda z: z.start_mi)
        return real_zones

    def _construction_zone_length(self, event) -> float:
        """Determine the length of a construction zone from event data."""
        # Try to parse from location text (e.g., "Between milepost 45 and 47")

        location = event.location_text
        if location:
            match = re.search(r"milepost (\d+(?:\.\d+)?) and (\d+(?:\.\d+)?)", location)
            if match:
                start = float(match.group(1))
                end = float(match.group(2))
                length = abs(end - start)
                if 0.5 <= length <= 20.0:
                    return length

        # Default lengths based on work type
        type_lengths = {
            "bridge": 4.0,
            "paving": 5.0,
            "utility": 3.0,
            "maintenance": 2.0,
            "construction": 5.0,
        }
        return type_lengths.get(event.work_type, 4.0)

    def _construction_zone_speed(self, event) -> float:
        """Determine the reduced speed limit for a construction zone."""
        closure = event.closure
        if closure == "full closure":
            return 15.0
        if closure == "alternating":
            return 35.0
        if closure == "shoulder":
            return 55.0  # minimal reduction
        # Single lane closure or default
        return 45.0

    def _construction_closed_side(self, event) -> str | None:
        """Which side of the road is coned off, or None if no closure.

        A side rather than a lane index: the feeds report the work, and the
        lane it lands on depends on how wide the road is where the truck
        reaches it (see ``Trip.closed_lane_at``).
        """
        closure = event.closure
        if closure == "full closure":
            return "right"  # right lane closed as part of full closure
        if closure in ("alternating", "single lane"):
            return "right"  # right lane (typically the closed one)
        if closure == "shoulder":
            return None  # shoulder work doesn't close a travel lane
        return None
