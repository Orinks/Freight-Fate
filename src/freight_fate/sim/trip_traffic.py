"""Traffic and patrol lookup helpers for trip simulation."""

from __future__ import annotations

from ..data.world import Leg
from .trip_models import (
    RUSH_HOUR_WINDOWS,
    TRAFFIC_PRESSURE_LOOKAHEAD_MI,
    NavigationCue,
    PatrolWindow,
    TrafficContext,
    TrafficPressure,
    TripEventKind,
)


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
        situation = self.traffic_manager.next_situation(
            position_mi=self.position_mi,
            truck_speed_mph=self.truck.speed_mph,
        )
        if situation is None:
            return
        lead = situation.vehicle
        cue = NavigationCue(
            f"npc:{lead.key}", "traffic", lead.position_mi, lead.reason, speed_mph=lead.speed_mph
        )
        self._emit(TripEventKind.GPS_CUE, situation.message, cue=cue, npc_vehicle=lead)

    def cb_patrol_message(self, patrol: PatrolWindow, ahead_mi: float) -> str:
        """Player-facing CB chatter for enforcement presence."""
        distance = self._distance_text(max(0.0, ahead_mi))
        if "construction" in patrol.reason or "work zone" in patrol.reason:
            return (
                f"CB chatter in {distance}: drivers are talking about enforcement "
                "near the work zone. Ease back and check your speed."
            )
        return (
            f"CB chatter in {distance}: drivers report a bear ahead. "
            "Ease back and check your speed."
        )

    def cb_patrol_status(self, patrol: PatrolWindow, ahead_mi: float) -> str:
        distance = self._distance_text(max(0.0, ahead_mi))
        if ahead_mi <= 0:
            if "construction" in patrol.reason or "work zone" in patrol.reason:
                return "CB chatter says enforcement is active around this work zone"
            return "CB chatter says a bear may be watching this stretch"
        if "construction" in patrol.reason or "work zone" in patrol.reason:
            return f"CB chatter about work-zone enforcement in {distance}"
        return f"CB chatter reports a bear ahead in {distance}"

    def next_patrol_within(self, within_mi: float) -> PatrolWindow | None:
        """Nearest active or upcoming patrol window inside the lookahead."""
        candidates = [
            p
            for p in self.patrols
            if p.end_mi >= self.position_mi and p.start_mi - self.position_mi <= within_mi
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda p: max(0.0, p.start_mi - self.position_mi))

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
        """Check for real-time traffic events from state 511 APIs."""
        if self.traffic_provider is None:
            return

        # Get current state from the route
        current_leg = self._leg_at(self.position_mi)
        if current_leg is None:
            return

        # Try to determine state from the leg (this is a simplified approach)
        # In production, we'd need proper state/region mapping
        state = "ohio"  # Default to Ohio for now as reference implementation

        # Get nearby traffic events
        try:
            events = self.traffic_provider.get_events_near(
                state,
                latitude=40.0,  # Placeholder - need real coordinates
                longitude=-83.0,
                radius_mi=50.0,
            )

            # Filter for high-severity events that haven't been announced
            for event in events:
                if event.severity in ("high", "medium"):
                    event_key = f"real_traffic:{event.id}"
                    if event_key not in self._announced_real_traffic:
                        message = f"Traffic alert: {event.description}"
                        if event.lanes_affected:
                            message += f". {event.lanes_affected} affected."
                        self._emit(TripEventKind.GPS_CUE, message, real_traffic_event=event)
                        self._announced_real_traffic.add(event_key)
        except Exception:
            # Gracefully handle API failures - real traffic is optional
            pass

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
