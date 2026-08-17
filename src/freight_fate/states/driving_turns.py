# ruff: noqa: F403,F405
"""Street corners cost speed, not reflex: be under the turn speed or loop back.

The sim carries no heading or yaw -- ``LaneKeeping`` has a lateral offset and
a discrete lane index and nothing else -- so a "manual turn" could only ever
have been a reaction-window quick-time event. That version was built and
withdrawn (2026-07-15) because a timed snap excludes players with slow
reaction or motor impairments. The owner's replacement is commitment, not
reflex: a corner is a speed you have to be under by the time you reach it,
announced far enough out to brake by ear, exactly the way the exit ramp
already demands ``RAMP_MAX_MPH`` and the facility gate demands
``FACILITY_GATE_LIMIT_MPH``. Braking to a spoken number is plannable; snapping
an arrow inside a second and a half is not.

The turn speed is anchored to the road, never invented: the street the truck
is turning ONTO carries a baked ``local_speed_mph`` (25 named, 15 unnamed
service ways), and the corner itself is capped at ``TURN_CORNER_MAX_MPH``. A
53-foot trailer off-tracks through a signalised city corner; CDL training
teaches completing one at 10 to 15, entering at no more than 20. Twenty also
sits honestly between the two speeds the game already posts -- a sweeping
ramp at 45 and the gate crawl at 15 -- so the ladder a player learns by ear
stays ordered.

The miss is the fourth instance of the shipped loop-back pattern (blown ramp
stop, missed destination exit, missed facility gate) and inherits the two
lessons that cost the most to learn:

- Drop back a FULL SPOKEN WINDOW, never a fixed distance. Under time
  compression a fixed stretch passes before it can be heard, so the retry is
  unwinnable.
- RESET EVERY say-once latch on the reposition, including the trip's own
  navigation announcements. When the missed-exit loop did not, the second
  miss stranded the trip.

Escalation ships on day one, because a loop with no escalation is a route
that can stop being finishable: the core sentence is identical every time so
the flow stays predictable by ear, help is appended from the second miss, and
the corner is completed for the player -- with the time still charged --
either on a repeat miss of the SAME corner or on the third miss anywhere.

Highway junctions are deliberately not judged here. Their cues carry no
direction, radius, or lane ordinal, and ``docs/nav-phrasing-brief.md`` forbids
speaking a lane ordinal that was never harvested.
"""

from __future__ import annotations

from ..sim.trip_models import FACILITY_ACCESS_LIMIT_MPH, FACILITY_GATE_LIMIT_MPH
from ..speech_pacing import SpeechCategory
from .driving_core import *

# The approach call is sized in REAL seconds of hearing-and-braking time, the
# same budget the exit callout gets, then converted to game miles at the
# current pace. LOCAL_TURN_LOOKAHEAD_MI alone is about 1.4 real seconds at
# street speed -- a reflex window, which is the thing this design refuses.
TURN_WARNING_REAL_S = 25.0
# Bounded by the road it lives on: a city block is short, and no corner call
# should arrive two miles of arterial before the corner exists.
TURN_WINDOW_MIN_MI = 0.25
TURN_WINDOW_MAX_MI = 2.0
# The corner ceiling for a tractor-trailer, whatever the street is posted at.
TURN_CORNER_MAX_MPH = 20.0
# Brake deadband: the truck may be a few mph over without failing, the same
# forgiveness the curve assist's hysteresis grants.
TURN_SPEED_MARGIN_MPH = 3.0
# Game minutes one loop through the safe turnaround costs. The gate and the
# destination exit charge 20 for a highway-scale turnaround -- miles of
# frontage road at 45 and back. A city corner is four right turns around one
# block at 20 with signals on two of them, so it costs a fraction of that.
TURN_MISS_LOOP_MIN = 8.0
# How far past the corner it stays the corner in play, and where a completed
# turn puts the truck back on the road.
TURN_COMMIT_TAIL_MI = 0.15
# The pursuit guide starts leaning into the corner this far out, reaching its
# full lean at the corner itself.
TURN_GUIDE_LEAD_MI = 0.2
TURN_GUIDE_DEMAND = 0.9
# An exit ramp peels right; the lane model already pushes the truck that way,
# so the road bed leans with it instead of sitting dead centre.
RAMP_GUIDE_DEMAND = 0.45


def _is_judged_turn(cue) -> bool:
    """A baked street maneuver with a real side to it.

    ``local:start`` is where the chain begins, not a corner, and an "ahead"
    or "straight" maneuver has nothing to steer through.
    """
    return (
        getattr(cue, "kind", "") == "local_turn"
        and str(getattr(cue, "key", "")).startswith("local:turn:")
        and str(getattr(cue, "direction", "") or "").strip().lower() in ("left", "right")
    )


class TurnCommitmentMixin:
    # -- the corner in play ---------------------------------------------------

    def _reset_turn_state_for_trip(self) -> None:
        """Cue keys belong to one trip's route; a surface-chain swap builds a
        new one, so the latches start clean with it."""
        self._turn_trip_id = id(self.trip)
        self._turn_advised: set[str] = set()
        self._turn_missed: set[str] = set()
        self._turn_resolved: set[str] = set()
        self._turn_grace_s = 0.0
        self.trip.controlled_turn = False

    def _turn_cues_in_play(self) -> list:
        """Every unsettled corner from here on, nearest first.

        The commitment loop only ever judges one corner at a time, so it asks
        for the first of these. A planner that has to BRAKE for corners needs
        the whole run: city blocks are shorter than one corner's own tail, so
        the next corner is regularly already in front of the truck while this
        one is still being taken.
        """
        if getattr(self, "_turn_trip_id", None) != id(self.trip):
            self._reset_turn_state_for_trip()
        position = self.trip.position_mi
        cues = [
            cue
            for cue in self.trip.navigation_cues
            if _is_judged_turn(cue)
            and cue.key not in self._turn_resolved
            and cue.at_mi - position >= -TURN_COMMIT_TAIL_MI
        ]
        cues.sort(key=lambda cue: cue.at_mi)
        return cues

    def _turn_cue_in_play(self):
        """The corner currently being approached or judged, or None."""
        cues = self._turn_cues_in_play()
        return cues[0] if cues else None

    def _turn_leg_index(self, cue) -> int:
        try:
            return int(str(cue.key).rsplit(":", 1)[1])
        except (IndexError, ValueError):
            return 0

    def _turn_street_text(self, cue) -> str:
        """The street being turned onto, in the world's own spoken name."""
        index = self._turn_leg_index(cue)
        legs = self.trip.route.legs
        if 0 <= index < len(legs) and legs[index].highway:
            return legs[index].highway
        return "the next street"

    def _turn_speed_mph(self, cue) -> float:
        """The speed the corner has to be taken under: the street's own
        posted limit, capped at what a trailer can turn, floored at the
        gate crawl so the gate stays the slowest thing on the route."""
        index = self._turn_leg_index(cue)
        legs = self.trip.route.legs
        posted = 0.0
        if 0 <= index < len(legs):
            posted = float(getattr(legs[index], "local_speed_mph", 0.0) or 0.0)
        street = posted or FACILITY_ACCESS_LIMIT_MPH
        return max(FACILITY_GATE_LIMIT_MPH, min(street, TURN_CORNER_MAX_MPH))

    def _turn_window_mi(self) -> float:
        """How far out the corner is called, and how far back a miss drops --
        a full spoken window, so the retry is winnable."""
        speed = max(self.truck.speed_mph, TURN_CORNER_MAX_MPH)
        miles = TURN_WARNING_REAL_S * speed * self.trip.effective_time_scale / 3600.0
        return max(TURN_WINDOW_MIN_MI, min(miles, TURN_WINDOW_MAX_MI))

    def _turn_grace_seconds(self, message: str) -> float:
        """Real reaction seconds after ``message``, the ramp-arrival rule: a
        corner is never failed while its own cue is still being spoken."""
        speech_rate = (
            self.ctx.settings.speech_rate
            if self.ctx.settings.sapi_events
            and getattr(self.ctx.speech, "event_supports_rate", False)
            else 0.0
        )
        return ramp_arrival_grace_seconds(message, speech_rate)

    def _turn_miss_suspended(self) -> bool:
        """Something else owns the wheel: a hazard swerve, a microsleep, a
        traffic stop, or an open arrival menu must never read as a miss."""
        return (
            self._hazard_deadline is not None
            or self._microsleep_deadline is not None
            or self._pull_over is not None
            or self._arrival_menu_open
        )

    # -- spoken text ----------------------------------------------------------

    def _turn_approach_text(self, cue, ahead_mi: float) -> str:
        """The approach call, in the pacenote grammar: side, street, distance,
        advisory. Terse drops the advisory tail but keeps everything a driver
        needs to place the corner -- and always says the verb, because a bare
        "Right now" reads as a direction or as timing, never reliably one."""
        settings = self.ctx.settings
        direction = str(cue.direction).strip().lower()
        street = self._turn_street_text(cue)
        target = settings.speed_text(self._turn_speed_mph(cue))
        if ahead_mi <= 0.05:
            call = f"Turn {direction} now onto {street}."
        else:
            distance = settings.short_distance_text(ahead_mi)
            call = f"{direction.capitalize()} turn onto {street}, {distance}."
        if self._terse_speech():
            return call
        call = f"{call} Advise {target}."
        if self._keeper_mph is not None and self.truck.speed_mph > self._turn_speed_mph(cue):
            # The keeper sheds this corner's speed itself, so say so here
            # rather than as a second utterance on top of the corner call --
            # and so nobody reaches for the brake, which cancels the session.
            call = f"{call} Speed keeper easing."
        return call

    # -- the frame ------------------------------------------------------------

    def _update_turn_commitment(self, dt: float) -> None:
        """Call the corner, hold the clock through it, judge it once."""
        cue = self._turn_cue_in_play()
        if self._turn_grace_s > 0.0:
            self._turn_grace_s = max(0.0, self._turn_grace_s - dt)
        if cue is None:
            self.trip.controlled_turn = False
            return
        ahead = cue.at_mi - self.trip.position_mi
        if cue.key not in self._turn_advised:
            if self.truck.speed_mph <= self._turn_speed_mph(cue):
                # Already slow enough to make it: the route's own maneuver cue
                # is the whole story, and an advisory a crawling truck cannot
                # fail is noise. The gate's speed warning works the same way.
                if ahead <= 0:
                    self._resolve_turn(cue)
                return
            if ahead > self._turn_window_mi():
                return
            # Either the window opened, or a resumed save arrived at the
            # corner cold. Both start the clock with the corner's own advice;
            # neither may latch a miss on first contact.
            self._turn_advised.add(cue.key)
            self.trip.controlled_turn = True
            message = self._turn_approach_text(cue, max(0.0, ahead))
            self._turn_grace_s = self._turn_grace_seconds(message)
            sound = _local_turn_sound(cue)
            if sound:
                pan = -TURN_CUE_PAN if cue.direction == "left" else TURN_CUE_PAN
                self.ctx.audio.play(sound, pan=pan)
            self.ctx.say_event(message, interrupt=False, category=SpeechCategory.NAVIGATION)
            return
        if ahead > 0:
            return
        if self._turn_grace_s > 0.0:
            return  # the corner's own cue is still speaking
        if self._turn_miss_suspended():
            self._resolve_turn(cue)
            return
        if self.truck.speed_mph > self._turn_speed_mph(cue) + TURN_SPEED_MARGIN_MPH:
            self._handle_missed_turn(cue)
        else:
            self._resolve_turn(cue)

    def _resolve_turn(self, cue) -> None:
        """This corner is settled; the clock goes back to trip pacing."""
        self._turn_resolved.add(cue.key)
        self._turn_grace_s = 0.0
        self.trip.controlled_turn = False

    def _reposition_for_turn(self, cue) -> None:
        """Drop back a full spoken window onto the approach, and clear every
        say-once latch the re-approach has to speak through again."""
        floor = 0.0
        for other in self.trip.navigation_cues:
            if _is_judged_turn(other) and other.at_mi < cue.at_mi:
                floor = max(floor, other.at_mi + TURN_COMMIT_TAIL_MI)
        self.trip.position_mi = max(floor, cue.at_mi - self._turn_window_mi())
        self._turn_advised.discard(cue.key)
        self._turn_grace_s = 0.0
        self.trip.controlled_turn = False
        # The trip's own GPS maneuver announcements latch per cue key; without
        # this the loop-back would run in silence (the missed-exit lesson).
        self.trip._announced_navigation.discard(f"{cue.key}:advance")
        self.trip._announced_navigation.discard(f"{cue.key}:near")

    def _handle_missed_turn(self, cue) -> None:
        """The scripted loop-back, or the corner completed for the player."""
        self._turn_miss_count += 1
        self.trip.game_minutes += TURN_MISS_LOOP_MIN
        self._cancel_cruise()
        terse = self._terse_speech()
        street = self._turn_street_text(cue)
        target = self.ctx.settings.speed_text(self._turn_speed_mph(cue))
        # One loop-back per corner, and never a fourth miss on one run: a
        # route must never become unfinishable. The time is still charged.
        completed = cue.key in self._turn_missed or self._turn_miss_count >= 3
        core = "Missed the turn." if terse else f"You missed the turn onto {street}."
        if completed:
            self._resolve_turn(cue)
            self.trip.position_mi = max(self.trip.position_mi, cue.at_mi + TURN_COMMIT_TAIL_MI)
            tail = (
                "Turn made for you."
                if terse
                else f"The turn is made for you and you are on {street}. "
                "The clock is still running."
            )
            status = "Turn missed again. The turn was made for you."
        else:
            self._turn_missed.add(cue.key)
            self._reposition_for_turn(cue)
            tail = (
                "Safe turnaround. Turn ahead again."
                if terse
                else "You continue to the next safe turnaround and loop back onto "
                "the approach. The turn is ahead again."
            )
            status = "Missed the turn. Use the next safe turnaround."
        message = f"{core} {tail}"
        if self._turn_miss_count >= 2:
            # The identical core line keeps the flow predictable by ear; a
            # repeat miss earns help, not scolding.
            message += f" Brake to {target} with {self.ctx.control_hint('brake')} on the approach."
        self.ctx.audio.play("ui/warning")
        self._set_status(status)
        # A mandatory turn on the route, not an optional stop: names the
        # loop-back (or the auto-turn) that still delivers the load, so it
        # must survive quiet/urgent_only as words, not an earcon blip.
        self.ctx.say_event(message, interrupt=True, category=SpeechCategory.NAVIGATION)

    # -- the pursuit guide ----------------------------------------------------

    def _maneuver_steer_demand(self, connector=None) -> float:
        """Signed steer for the maneuvers that carry no mainline curve record.

        Connector arcs are excluded from the curve PUSH and from the pacenotes
        on purpose (ramps carry their own speech), and street legs carry baked
        maneuvers instead of curve geometry. Excluding them from the GUIDE as
        well silenced the panned road bed -- the only continuous directional
        audio the game has -- through every exit ramp and every turn, which is
        exactly where a blind driver needs it. This feeds the existing bed a
        synthetic demand; it never adds a tone (sim/lane_guidance.py).
        """
        if connector is not None:
            tightness = max(0.2, 1.0 - connector.min_radius_ft / 5000.0)
            excess = max(0.0, self.truck.speed_mph - connector.advisory_mph)
            magnitude = min(1.0, tightness * (1.0 + excess * 0.04))
            return -magnitude if connector.direction == "L" else magnitude
        if self._ramp_mi is not None:
            return RAMP_GUIDE_DEMAND
        cue = self._turn_cue_in_play()
        if cue is None:
            return 0.0
        ahead = cue.at_mi - self.trip.position_mi
        if ahead > TURN_GUIDE_LEAD_MI:
            return 0.0
        if ahead <= 0.0:
            magnitude = TURN_GUIDE_DEMAND
        else:
            magnitude = TURN_GUIDE_DEMAND * (1.0 - ahead / TURN_GUIDE_LEAD_MI)
        return -magnitude if str(cue.direction).lower() == "left" else magnitude
