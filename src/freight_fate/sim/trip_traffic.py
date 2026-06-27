"""Traffic and patrol lookup helpers for trip simulation."""

from __future__ import annotations

from ..data.world import Leg
from .trip_models import (
    RUSH_HOUR_WINDOWS,
    TRAFFIC_PRESSURE_LOOKAHEAD_MI,
    PatrolWindow,
    TrafficPressure,
)


class TripTrafficMixin:

    def next_patrol_within(self, within_mi: float) -> PatrolWindow | None:
        """Nearest active or upcoming patrol window inside the lookahead."""
        candidates = [
            p for p in self.patrols
            if p.end_mi >= self.position_mi
            and p.start_mi - self.position_mi <= within_mi
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
            pressure for pressure in self.traffic_pressures
            if pressure.start_mi <= sample <= pressure.end_mi
        ]
        if not active:
            return None
        return max(active, key=lambda pressure: pressure.intensity)

    def next_traffic_pressure_within(
        self, within_mi: float = TRAFFIC_PRESSURE_LOOKAHEAD_MI
    ) -> TrafficPressure | None:
        candidates = [
            pressure for pressure in self.traffic_pressures
            if pressure.end_mi >= self.position_mi
            and 0 <= pressure.start_mi - self.position_mi <= within_mi
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda pressure: pressure.start_mi)

