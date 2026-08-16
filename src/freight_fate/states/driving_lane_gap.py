# ruff: noqa: F403,F405
"""The mirror check a blind driver cannot make: when the lane you left is
open again.

Passing is a two-part manoeuvre and the game only ever spoke the first part.
Moving over says "Changing to the left lane" and arriving says "In the left
lane", and from there the driver is on their own: the vehicle they are
passing makes no sound once it is beside the cab, and nothing says when it
is behind them. A sighted player glances at the mirror. A blind player was
left guessing, and guessing wrong is a sideswipe -- the collision message
even tells them to check mirrors they have no way to check (tester Darren
Duff, 1.9.0.dev0: "Not sure how you are supposed to know once you are past
vehicles and it's safe to switch lanes again").

So the pass gets its closing half: one line, when the lane behind the
manoeuvre is genuinely open again.

* **The same authority that judges the collision.** ``_finish_lane_change``
  asks the traffic manager whether the lane it arrived in is occupied. This
  asks the same question of the lane the driver came from, through the same
  ``vehicle_in_lane`` call, over a window a margin WIDER than the collision
  test uses -- and swept forward over the real seconds a driver spends
  acting on the answer. A static margin was not enough: traffic moves on
  compressed game time, so at highway compression a cruise closing on
  slowed traffic ate half a mile between "Right lane open" and the drift
  landing, and the lane the cue had honestly called open sideswiped anyway
  (tester Jerry Jicha, 1.9.0.dev0: "if it says it is open, then it is
  open"). Open now means open until the driver is across.
* **Once per vehicle passed.** Latched on the vehicle's key, like the pass-by
  whoosh. A car riding the edge of the window must not chant.
* **Only while it is still true.** Back in that lane, out of it by a fresh
  change, stopped, or the road took the lane away, and the watch is dropped
  without a word. A closed lane is never called open.

The same clearance reading answers the L key on demand, so a driver who
missed the line -- or who wants to know before committing -- can ask.
"""

from __future__ import annotations

from ..speech_pacing import SpeechCategory
from .driving_core import *

# How much wider than the sideswipe test this cue looks. Positional slack for
# what the look-ahead below cannot see -- a vehicle braking harder inside the
# horizon than its current speed says. Every mile of it makes the cue quieter,
# never more permissive.
LANE_GAP_MARGIN_MI = 0.12
# The real seconds between hearing "open" and the truck being across: the
# line finishing, the reach for the wheel, and the timed drift over the
# painted line. The clearance read is swept this far forward through the
# traffic's own motion -- converted to game time through the trip's effective
# scale, because that is the clock the traffic actually moves on. Jerry's
# collisions ran readout-to-contact in about four and a half real seconds.
LANE_GAP_ACT_REAL_S = 6.0
# Real seconds between two of these lines. A queue of vehicles clearing one
# after another is a real sequence of facts, but read out back to back it is
# a chant over the top of whatever else the road is saying.
LANE_GAP_CUE_MIN_GAP_S = 4.0


class LaneGapMixin:
    def _reset_lane_gap(self) -> None:
        # The lane a completed change moved out of, and the vehicle that was
        # holding it. Per-stint, not saved: a reloaded trip is not mid-pass.
        self._lane_gap_watch: int | None = None
        self._lane_gap_prev_lane: int | None = self.lane.lane
        self._lane_gap_blocker_key: str | None = None
        self._lane_gap_blocker_class = ""
        self._lane_gap_said_keys: set[str] = set()
        self._lane_gap_cue_s = 0.0

    # -- clearance, read through the collision logic's own authority ----------

    def _lane_gap_blocker(self, lane_index: int):
        """The vehicle holding ``lane_index`` beside the truck, or None.

        The window is the sideswipe test's, widened by ``LANE_GAP_MARGIN_MI``
        at both ends and swept ``LANE_GAP_ACT_REAL_S`` real seconds forward
        through the traffic's relative motion: whatever this call misses, the
        collision check misses too, so "open" can never be the more
        optimistic of the two answers -- not now, and not by the time the
        driver acting on it arrives in the lane.
        """
        manager = getattr(self.trip, "traffic_manager", None)
        if manager is None:
            return None
        return manager.vehicle_in_lane(
            self.trip.position_mi,
            lane_index,
            ahead_mi=DODGE_CLEARANCE_AHEAD_MI + LANE_GAP_MARGIN_MI,
            behind_mi=DODGE_CLEARANCE_BEHIND_MI + LANE_GAP_MARGIN_MI,
            horizon_hr=LANE_GAP_ACT_REAL_S * self.trip.effective_time_scale / 3600.0,
            speed_mph=self.truck.speed_mph,
        )

    def _lane_gap_closed_by_zone(self, lane_index: int) -> bool:
        """Whether roadwork has this lane coned off where the truck is."""
        zone = self.trip.active_zone
        return zone is not None and zone.reason == "construction" and zone.closed_lane == lane_index

    def _lane_gap_open(self, lane_index: int) -> bool:
        """Whether moving into ``lane_index`` right now is clear of traffic."""
        return self._lane_gap_blocker(lane_index) is None

    # -- the spoken cue -------------------------------------------------------

    def _arm_lane_gap_watch(self, lane_index: int) -> None:
        self._lane_gap_watch = lane_index
        self._lane_gap_blocker_key = None
        self._lane_gap_blocker_class = ""
        # A fresh manoeuvre is owed a fresh answer, even about a vehicle an
        # earlier one already called: the driver is passing it again.
        self._lane_gap_said_keys.clear()

    def _drop_lane_gap_watch(self) -> None:
        self._lane_gap_watch = None
        self._lane_gap_blocker_key = None
        self._lane_gap_blocker_class = ""
        self._lane_gap_said_keys.clear()

    def _update_lane_gap(self, dt: float) -> None:
        """Watch the lane the truck moved out of, and say when it is open."""
        lane = self.lane
        current = lane.lane
        previous = self._lane_gap_prev_lane
        self._lane_gap_prev_lane = current
        self._lane_gap_cue_s = max(0.0, self._lane_gap_cue_s - dt)
        if previous is not None and previous != current:
            # The truck just changed lanes: the lane it left is the way back.
            self._arm_lane_gap_watch(previous)
        watch = self._lane_gap_watch
        if watch is None:
            return
        if watch == current or watch >= lane.lane_count or watch < 0:
            # Already back in it, or the road no longer has it.
            self._drop_lane_gap_watch()
            return
        if self._lane_gap_closed_by_zone(watch):
            # Never call a coned-off lane open. The merge warning owns this
            # stretch of road and it is telling the driver the opposite.
            self._drop_lane_gap_watch()
            return
        if self.truck.speed_mph <= LANE_MIN_MPH:
            return  # nothing is being passed at a crawl; keep watching
        if self._lane_change_target is not None:
            return  # a change is already underway, in some direction
        blocker = self._lane_gap_blocker(watch)
        if blocker is not None:
            self._lane_gap_blocker_key = blocker.key
            self._lane_gap_blocker_class = str(getattr(blocker, "vehicle_class", "") or "vehicle")
            return
        key = self._lane_gap_blocker_key
        if key is None or key in self._lane_gap_said_keys:
            return  # nobody was ever alongside, or this one has been called
        # Marked spoken either way. A cue held back by the spacing and let out
        # later would be describing a gap that has moved on since.
        self._lane_gap_said_keys.add(key)
        if self._lane_gap_cue_s > 0.0:
            return
        self._lane_gap_cue_s = LANE_GAP_CUE_MIN_GAP_S
        name = lane_label(watch, lane.lane_count)
        vehicle = self._lane_gap_blocker_class or "vehicle"
        if self._terse_speech():
            message = f"{name.capitalize()} lane open."
        else:
            message = f"Clear of the {vehicle}. {name.capitalize()} lane open."
        self.ctx.audio.play("ui/notify", volume=0.45)
        self.ctx.say_event(message, interrupt=False, category=SpeechCategory.STATUS)

    # -- the on-demand readout ------------------------------------------------

    def _lane_status_text(self) -> str:
        """The L key: where the truck sits, and whether the next lane over is
        open. The driver who missed the spoken line, or who wants to know
        before they commit, asks for the same reading it speaks from."""
        lane = self.lane
        parts = [lane.describe()]
        for neighbour in (lane.lane - 1, lane.lane + 1):
            if not 0 <= neighbour < lane.lane_count:
                continue
            name = lane_label(neighbour, lane.lane_count).capitalize()
            if self._lane_gap_closed_by_zone(neighbour):
                parts.append(f"{name} lane closed for construction.")
                continue
            blocker = self._lane_gap_blocker(neighbour)
            if blocker is None:
                parts.append(f"{name} lane open.")
            else:
                vehicle = str(getattr(blocker, "vehicle_class", "") or "vehicle")
                parts.append(f"{name} lane blocked by a {vehicle}.")
        return " ".join(parts)
