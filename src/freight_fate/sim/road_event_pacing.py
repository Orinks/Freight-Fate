"""Real-seconds breathing gaps for the routine road talkers.

Time compression spends road 10-40x faster than a real cab, so systems
that announce on road distance -- posted-limit arrivals, traffic calls,
zone chatter -- pile their lines back to back in every driving mode
(owner report, 2026-08-13). The clock stays (career pacing is balanced
on it); the ANNOUNCEMENTS space out instead, in wall-clock seconds, the
same law the corner warnings and the keeper's ease already follow.

The gate lives at the SOURCE, before any state mutates: a caller that
finds its window shut simply does nothing, and the next natural check
after the window opens announces the CURRENT state. Superseding is free
-- nothing is held, so nothing goes stale.

Safety and action lines never come here: hazards, AEB, pacenotes, scale
and stop calls, maneuvers, enforcement, merge warnings, and every answer
to a player's key speak immediately, always.
"""

from __future__ import annotations

import time

LIMIT_GAP_REAL_S = 12.0  # posted-limit arrival lines
TRAFFIC_GAP_REAL_S = 10.0  # NPC traffic situation calls
ZONE_GAP_REAL_S = 15.0  # zone-entry colour

_GAPS = {
    "limit": LIMIT_GAP_REAL_S,
    "traffic": TRAFFIC_GAP_REAL_S,
    "zone": ZONE_GAP_REAL_S,
}


class RoadEventBreather:
    """One window per category, measured on the wall clock."""

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._last_spoke: dict[str, float] = {}

    def ready(self, category: str) -> bool:
        last = self._last_spoke.get(category)
        return last is None or self._clock() - last >= _GAPS[category]

    def spoke(self, category: str) -> None:
        self._last_spoke[category] = self._clock()
