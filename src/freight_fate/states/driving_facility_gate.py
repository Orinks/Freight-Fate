# ruff: noqa: F403,F405
"""Missing the facility gate: too fast past the entrance means a loop-back.

The destination facility's gate ends the drive, and the trip model clamps the
odometer there -- which used to be an invisible treadmill: cross the gate at
highway speed and the miles simply stopped while the truck barreled on, no
overshoot, no consequence. A truck that crosses the gate above the gate
zone's own posted limit (``FACILITY_GATE_LIMIT_MPH``, the 15 the last half
mile is signed at) has missed the entrance.

The miss is the third instance of an existing pattern -- the blown ramp stop
and the missed destination exit both loop back -- and reuses its idioms: a
scripted reposition through the next safe turnaround, game time charged, and
the gate ahead again. The spoken cue is the only signage, so a pre-gate speed
warning with an explicit target speed always precedes the first possible
miss, and a real-time reaction window (``ramp_arrival_grace_seconds``, the
same rule the ramp uses) must expire before one latches -- under time
compression a distance alone is unbeatable. HOS, the clock, and fuel keep
running through every loop; the lost time is the consequence, never a fine.
"""

from __future__ import annotations

from ..sim.trip_models import (
    FACILITY_ACCESS_TAIL_MI,
    FACILITY_GATE_LIMIT_MPH,
    FACILITY_GATE_ZONE_MI,
)
from ..speech_pacing import EventPriority, SpeechCategory
from .driving_core import *

# Game minutes one loop through the safe turnaround costs -- the same charge
# as the missed-destination-exit loop, which is the same maneuver a road up.
GATE_MISS_LOOP_MIN = 20.0
# The pre-gate warning window, scaled for real reaction time like the exit
# window (EXIT_WARNING_REAL_S of hearing-and-braking time at the current
# pace), bounded by the road it lives on: never less than the signed gate
# zone, never more than the facility access-road tail.
GATE_WARNING_MIN_MI = FACILITY_GATE_ZONE_MI
GATE_WARNING_MAX_MI = FACILITY_ACCESS_TAIL_MI


class FacilityGateMixin:
    def _post_gate_zone(self) -> None:
        """Put the gate's 15 back on the map, now that the exit is behind.

        The arrival zones are stripped at trip start so nothing posts a silent
        low limit under a spoken 65 on the final freeway miles. That left the
        pre-gate warning naming a speed that was posted nowhere: it said "slow
        to 15" while the last half mile still read the corridor's 55, so every
        assist held 55 straight through the entrance and into the loop-back
        (owner playtest, 2026-08-21). Once the destination exit is taken the
        road under the truck IS the facility's own, so the 15 the warning names
        is the number in force -- and a facility with a street chain never
        reaches here, because its chain builds a gate zone of its own.
        """
        if any(zone.reason == "facility gate" for zone in self.trip.zones):
            return
        if self._surface_chain_route() is not None:
            # This facility's own streets are about to become the trip, and
            # that chain builds its own gate zone at the end of itself. Posting
            # one here as well would announce the same gate twice: once off the
            # ramp on the highway trip, once again on the streets.
            return
        self.trip.zones.append(self.trip.facility_gate_zone())
        self.trip.zones.sort(key=lambda zone: zone.start_mi)

    def _gate_warning_window_mi(self) -> float:
        """How far out the pre-gate speed warning fires, and how far back a
        miss repositions -- a full spoken window, so the retry is winnable."""
        speed = max(self.truck.speed_mph, FACILITY_GATE_LIMIT_MPH)
        miles = EXIT_WARNING_REAL_S * speed * self.trip.effective_time_scale / 3600.0
        return max(GATE_WARNING_MIN_MI, min(miles, GATE_WARNING_MAX_MI))

    def _gate_miss_grace_seconds(self, message: str) -> float:
        """Real reaction seconds after ``message``, the ramp-arrival rule."""
        speech_rate = (
            self.ctx.settings.speech_rate
            if self.ctx.settings.sapi_events
            and getattr(self.ctx.speech, "event_supports_rate", False)
            else 0.0
        )
        return ramp_arrival_grace_seconds(message, speech_rate)

    def _check_gate_approach_warning(self, dt: float) -> None:
        """Warn about gate speed while braking can still make the entrance.

        Without this the first "slow down" fired AT the gate, so under the
        miss rule the first cue would have been the failure. Runs every
        drive tick; it also keeps the reaction window's clock, which must
        tick whether or not the trip has finished.
        """
        if self._gate_grace_s > 0.0:
            self._gate_grace_s = max(0.0, self._gate_grace_s - dt)
        if (
            self.phase != DRIVE_PHASE_DELIVERY
            or not self._destination_exit_taken
            or self._ramp_mi is not None
            or self.trip.finished
            or self._gate_speed_warned
            or self.truck.speed_mph <= FACILITY_GATE_LIMIT_MPH
        ):
            return
        remaining = self.trip.total_miles - self.trip.position_mi
        if remaining > self._gate_warning_window_mi():
            return
        self._gate_speed_warned = True
        target = self.ctx.settings.speed_text(FACILITY_GATE_LIMIT_MPH)
        distance = self.ctx.settings.distance_text(remaining, precise=True)
        if self._terse_speech():
            message = f"Gate in {distance}. Slow to {target}."
        else:
            message = f"Facility gate in {distance}. Slow to {target} to make the entrance."
        self._gate_grace_s = self._gate_miss_grace_seconds(message)
        self.ctx.audio.play("ui/warning")
        # Never dropped: this line starts the gate miss clock, so losing it
        # costs the driver the gate itself.
        self.ctx.say_event(
            message,
            interrupt=False,
            priority=EventPriority.ROUTE,
            category=SpeechCategory.NAVIGATION,
        )

    def _seed_gate_grace_at_gate(self, message: str) -> None:
        """Open the reaction window at the gate itself when no pre-gate
        warning was heard -- a resumed save can arrive here cold. The miss
        clock starts with the gate's own stop line, never on first contact."""
        if self._gate_speed_warned or self.truck.speed_mph <= FACILITY_GATE_LIMIT_MPH:
            return
        self._gate_speed_warned = True
        self._gate_grace_s = self._gate_miss_grace_seconds(message)

    def _gate_miss_pending(self) -> bool:
        """Rolling past the gate has become a miss: warned, window expired,
        still above the gate zone's posted limit -- and no assist or
        emergency owns the speed. The destination approach assist is checked
        by the caller (its branch brakes the truck itself and returns first),
        so the game's own braking curve can never trigger a miss."""
        return (
            self.truck.speed_mph > FACILITY_GATE_LIMIT_MPH
            and self._gate_speed_warned
            and self._gate_grace_s <= 0.0
            and self._hazard_deadline is None
            and self._pull_over is None
            and not self._arrival_menu_open
        )

    def _charge_scripted_loop(self, minutes: float) -> None:
        """HOS, fatigue, and idle fuel for a scripted loop-back -- the spoken
        "the clock is still running" line must be literally true. The
        scripted reposition never passes through the per-frame loop that
        would otherwise apply these (``_update_hours_and_fatigue``,
        ``TruckState._update_fuel``), so it charges the same rate math
        directly against the loop's fixed minutes instead of duplicating
        the constants those apply. Shared by the missed facility gate and
        the missed destination exit, whose loops are the same maneuver.
        """
        p = self.ctx.profile
        # Self-serve bobtail is personal conveyance, off duty. A carrier-
        # ASSIGNED reposition is on-duty driving, same as any other move.
        if self.job.bobtail and not self.job.assigned:
            self.hos.off_duty(minutes)
        else:
            # The loop is a real, if slow, drive through the next safe
            # turnaround -- on-duty driving time, not a parked wait.
            self.hos.drive(minutes)
        fatigue_mult = tuning_for_time_scale(self.trip.time_scale).fatigue_rate
        night = is_night(self.trip.local_hour)
        now_h = self._absolute_game_hour()
        p.fatigue = min(
            100.0,
            p.fatigue
            + hos.fatigue_rate_per_min(night) * minutes * fatigue_mult * p.fatigue_buff_rate(now_h),
        )
        self.truck.burn_idle_fuel_over_game_time(minutes * 60.0)

    def _handle_missed_facility_gate(self) -> None:
        """The scripted loop-back through the next safe turnaround."""
        self.trip.finished = False
        self._gate_miss_count += 1
        self.trip.game_minutes += GATE_MISS_LOOP_MIN
        self._charge_scripted_loop(GATE_MISS_LOOP_MIN)
        # Drop back a full warning window, not a fixed distance: under time
        # compression a fixed stretch passes before it can be heard, making
        # the re-approach unwinnable (the missed-exit loop's lesson).
        self.trip.position_mi = max(0.0, self.trip.total_miles - self._gate_warning_window_mi())
        # The say-once latches must never swallow the reposition -- when the
        # missed-exit loop let them, a second miss stranded the trip pinned
        # at route end. The next approach warns and speaks fresh, and the
        # "still at the gate" reminder is unreachable until the trip ends
        # at the gate again.
        self._arrival_stop_said = False
        self._arrival_full_stop_said = False
        self._gate_reminder_s = 0.0
        self._gate_speed_warned = False
        self._gate_grace_s = 0.0
        self._cancel_cruise()
        target = self.ctx.settings.speed_text(FACILITY_GATE_LIMIT_MPH)
        if self._terse_speech():
            message = (
                f"Missed the gate: too fast. Safe turnaround. Gate ahead again; slow to {target}."
            )
        else:
            message = (
                f"You carried past the gate at {self._destination_facility_text()}, "
                "too fast to make the entrance. You continue to the next safe "
                "turnaround and loop back onto the approach. The gate is ahead "
                f"again; slow to {target} this time. The clock is still running."
            )
        if self._gate_miss_count >= 2:
            # The identical core line keeps the flow predictable by ear; a
            # repeat miss earns help, not scolding.
            message += f" Brake with {self.ctx.control_hint('brake')} well before the gate."
            if not self.ctx.settings.destination_approach_assist:
                message += (
                    " Destination approach assist in Settings, Gameplay, "
                    "can stop the truck for you."
                )
        self.ctx.audio.play("ui/warning")
        self._set_status("Missed the facility gate. Use the next safe turnaround.")
        # The mandatory destination gate, not an optional stop: names the
        # loop-back maneuver that still delivers the load, so it must survive
        # quiet/urgent_only as words, not an earcon blip.
        self.ctx.say_event(message, interrupt=True, category=SpeechCategory.NAVIGATION)
