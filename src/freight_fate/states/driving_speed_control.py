# ruff: noqa: F403,F405
"""Shared lifecycle helpers for the driving state's speed controllers."""

from __future__ import annotations

from ..sim.trip_models import (
    APPROACH_DECEL_MPS2,
    APPROACH_REACTION_S,
    APPROACH_SETTLE_S,
)
from ..speech_pacing import SpeechCategory
from .driving_core import (
    CRUISE_MIN_MPH,
    KEEPER_MIN_MPH,
    MPH_PER_MPS,
    RED_STOP_MPH,
    RESTRICTED_ZONE_REASONS,
)
from .driving_turns import TURN_COMMIT_TAIL_MI

# The keeper's ease and the arrival zones plan the same shed, so the three
# numbers under it have one definition, in the portable layer.
#
# How early the keeper starts shedding speed for something ahead, sized in
# REAL seconds rather than miles -- the same law the turn call and the zone
# warning already follow, because under time compression a fixed stretch of
# road passes before a truck can slow through it.
KEEPER_EASE_REAL_S = APPROACH_REACTION_S
# And down to the number this long BEFORE the point, never exactly on it: a
# corner reached at the advise speed with no margin is a corner taken at it,
# which is the tester report this exists to answer.
KEEPER_SETTLE_REAL_S = APPROACH_SETTLE_S
# What the keeper actually delivers at street speed, measured on the bench
# rather than assumed: it is capped at light brake and comes off the pedal
# inside its own deadband, so it sheds about 0.4 m/s2 down there (0.9 at
# highway speed, where drag does most of the work). Sized on a comfortable
# 0.8 instead, the window was honest for a corner but half what a 25-to-15
# drop needs, and the truck reached the sign still doing 17.
#
# Kept at 0.4 on purpose, even though the snub added a few hours after that
# measurement (7f46880b) now guarantees KEEPER_SNUB_DECEL_MPS2 -- 0.6, net of
# the grade, held until the truck is a mile an hour UNDER the number, so the
# real figure on the flat is better than this. Planning against 0.4 keeps a
# third of the window in hand, and that is the margin that still makes the
# corner on a downgrade, on warm drums, or with the pedal saturated at
# KEEPER_SNUB_MAX_BRAKE. The two failures do not cost the same: arriving early
# costs a stretch at the lower number, arriving late costs the corner, the
# loop-back, and the session with it.
KEEPER_EASE_DECEL_MPS2 = APPROACH_DECEL_MPS2
# Aim a hair under the number rather than exactly at it. The keeper closes
# the last mile an hour on engine drag alone -- below its braking deadband --
# so a target set right on the number is a number the truck only reaches AT
# the corner, which is the report all over again.
KEEPER_EASE_UNDERSHOOT_MPH = 1.0
# A ceiling, so a long access road is never crawled from one end.
KEEPER_EASE_MAX_MI = 0.75
# Scan step for the posted-limit look ahead. A city block is shorter than the
# tenth of a mile adaptive cruise steps by on the corridor.
KEEPER_LIMIT_PROBE_MI = 0.05
# The keeper works the drums in snubs, for the reason adaptive cruise already
# does (see CRUISE_SNUB_BRAKE): the air model charges a fresh application
# every time the pedal RISES, so a command that tracks the error up and down
# pays for a brake application several times a second. The keeper's old
# proportional trim sat right on its own deadband holding a zone speed down a
# mild grade and did exactly that -- 275 applications in eighteen seconds,
# 125 psi down to 41, spring brakes on, the truck stopped dead in a 15 mph
# zone with nothing said about why (bench trace, 2026-08-11). Apply once,
# hold it to the target, release, let it drift back up.
KEEPER_SNUB_OVER_MPH = 1.5  # this far over the target starts a snub
KEEPER_SNUB_UNDER_MPH = 1.0  # and it runs until this far back under it
# What the snub aims to take off, NET of whatever the grade is putting back
# in -- so the same application arrives on the flat and on a downgrade
# instead of settling wherever gravity happens to balance it.
KEEPER_SNUB_DECEL_MPS2 = 0.6
KEEPER_SNUB_MIN_BRAKE = 0.12  # a real application, not a drag
KEEPER_SNUB_MAX_BRAKE = 0.6  # zone speeds never need more than this
# Pressed this hard, this far over, for this long: the keeper is out of
# authority and has to say so rather than quietly ride the number down.
KEEPER_OVERRUN_MPH = 3.0
KEEPER_OVERRUN_S = 4.0


class SpeedControlStateMixin:
    def _clear_cruise(self, *, preserve_exit_cap: bool = False) -> None:
        self._cruise_mph = None
        self._cruise_working_mph = None
        self._cruise_throttle = 0.0
        self._cruise_applied = 0.0
        self._cruise_trim = 0.0
        if self._cruise_jake_stage > 0:
            # Hand the retarder back with the cruise session, but only the
            # stages cruise raised -- the driver's own jake switch stays put.
            self._cruise_jake_stage = 0
            self.truck.engine_brake_stage = 0
        if not preserve_exit_cap:
            self._cruise_exit_mph = None
        self._cruise_curve_mph = None
        self._cruise_curve_end_mi = None
        self._cruise_descent_mph = None
        self._cruise_snubbing = False
        self._pcc_phase = ""
        self._climb_cue_said = False
        self._limp_cruise_said = False
        self._acc_following = False
        self._acc_weather_gap_said = False
        self._acc_limit_capped = False
        self._acc_limit_cap_said = None
        self._construction_slowdown = None

    def _clear_keeper(self) -> None:
        self._keeper_mph = None
        self._keeper_throttle = 0.0
        self._keeper_zone = ""
        self._keeper_zone_limit = None
        self._keeper_ease_said = None
        self._keeper_ease_target = None
        self._keeper_snub = 0.0
        self._keeper_overrun_s = 0.0
        self._keeper_overrun_said = False

    def _disarm_speed_control(self) -> None:
        # Remember the open-road target across the cancel, like a car's
        # RESUME: braking drops the session, Shift+K brings the speed back.
        # A keeper-only cancel carries no target and must not clobber a
        # remembered one.
        remembered = self._speed_control_target_mph or self._cruise_mph
        if remembered:
            self._resume_target_mph = remembered
        self._clear_cruise()
        self._clear_keeper()
        self._speed_control_armed = False
        self._clear_stop_pause()
        self._speed_control_target_mph = None

    def _speed_authority_engaged(self) -> bool:
        """Whether an automatic speed system currently owns the pedal.

        This is the latch's whole priority rule: a LATCHED throttle is the
        lowest-priority speed input and contributes nothing while any of
        these is engaged (owner design 2026-08-13, after tester Brandon
        latched for the whole trip expecting the assists to drive). A
        hand-held key is a different thing entirely -- live manual
        override -- and never consults this.
        """
        return (
            self._cruise_mph is not None
            or self._keeper_mph is not None
            or self._curve_assist_active
        )

    def _resume_cruise(self) -> None:
        """Shift+K: re-arm the session at the last remembered set speed."""
        if (
            self._speed_control_armed
            or self._cruise_mph is not None
            or self._keeper_mph is not None
        ):
            self.ctx.say("Automatic speed control is already on.")
            return
        target = self._resume_target_mph
        if target is None:
            self.ctx.say("No remembered cruise speed yet. K sets one.")
            return
        if not self.truck.engine_on:
            self.ctx.say("Resume needs the engine running.")
            return
        self._restore_speed_control_session(armed=True, target_mph=target)
        self.ctx.say(f"Resuming automatic speed control at {self.ctx.settings.speed_text(target)}.")
        # The per-frame resume helper engages cruise or the keeper as soon
        # as the truck is rolling and off the brakes -- pressing resume
        # while still slowing arms it for the moment conditions clear.

    def _clear_stop_pause(self) -> None:
        """Forget a stop pause, whichever kind of stop made it."""
        self._speed_control_paused_at_stop = False
        self._speed_control_transit_pause = False
        self._speed_control_stop_honored = False

    def _pause_speed_control(self, *, resume_when_rolling: bool = False) -> bool:
        """Pause an armed session at a planned stop without forgetting it.

        Two kinds of stop wear this pause. An ARRIVAL -- a pickup or delivery
        gate, a planned rest stop -- is held until the player departs, and
        departure is the only thing that clears it. A TRANSIT stop -- the
        light or sign at the end of a ramp -- has no departure at all: the
        driver stops at the bar and drives on. Held the arrival way, taking an
        exit left adaptive cruise and the speed keeper dead for the rest of
        the run, and only pressing resume brought them back (Shane,
        2026-08-15). ``resume_when_rolling`` says this is a transit stop, and
        the pause lifts itself once the stop has been honored and the truck is
        rolling again.

        Clearing the controllers alone is never enough either way: the truck
        is still rolling toward the bar or the gate, so the resume check would
        re-engage the keeper on the very next frame and announce it -- right
        after telling the player it would wait.
        """
        if not self._speed_control_armed:
            return False
        was_active = self._cruise_mph is not None or self._keeper_mph is not None
        self._clear_cruise()
        self._clear_keeper()
        self._speed_control_paused_at_stop = True
        self._speed_control_transit_pause = resume_when_rolling
        self._speed_control_stop_honored = False
        return was_active

    def _lift_transit_pause(self, *, braking: bool) -> bool:
        """Whether a transit pause has run its course this frame.

        It ends where the stop it was made for ends: the truck honored the bar
        and is rolling again with the player off the brake. Running out of
        ramp AND out of armed exit counts as honoring it too -- a terminal
        with no control at all is honored by driving through it, a blown ramp
        hands the highway back at speed, and a cancelled exit leaves nothing
        to wait for. Both have to be clear: the exit assist pauses a mile and
        a half out, with the ramp still ahead and no bar taken yet. An arrival
        pause is never lifted here; only departure clears one.
        """
        if not self._speed_control_transit_pause:
            return False
        t = self.truck
        if t.speed_mph <= RED_STOP_MPH or (self._ramp_mi is None and self._exit_stop is None):
            self._speed_control_stop_honored = True
        if not self._speed_control_stop_honored or braking:
            return False
        # Rolling FORWARD: backing away from a bar is not driving on from it,
        # and speed_mph reads the same either way.
        if t.velocity_mps <= 0.0 or t.speed_mph < KEEPER_MIN_MPH:
            return False
        self._clear_stop_pause()
        return True

    def _restore_speed_control_session(self, *, armed: bool, target_mph: float | None) -> None:
        self._clear_cruise()
        self._clear_keeper()
        self._speed_control_armed = armed
        self._clear_stop_pause()
        self._speed_control_target_mph = target_mph if armed else None

    def _resume_speed_control_if_ready(self, *, braking: bool) -> None:
        """Resume a paused job-scoped session once the player is rolling again."""
        if (
            not self._speed_control_armed
            or self._cruise_mph is not None
            or self._keeper_mph is not None
        ):
            return
        if self._speed_control_paused_at_stop and not self._lift_transit_pause(braking=braking):
            return
        t = self.truck
        if t.emergency_brake:
            self._disarm_speed_control()
            self.ctx.say_event(
                "Automatic speed control canceled.",
                interrupt=False,
                category=SpeechCategory.CONFIRMATION,
            )
            return
        if self._ramp_mi is not None:
            # A ramp stop is in progress. Taking the exit hands the pedals
            # back, and the stop at the end of the ramp is the driver's to
            # make -- resuming here wound the truck back up and drove a player
            # straight past the destination terminal, silently, at 66 mph
            # (owner playtest, Buffalo to Albany, 2026-08-12). The whole ramp
            # counts, not just the stretch ``trip.controlled_ramp`` covers:
            # that flag drops the moment the light or sign is behind the
            # truck, which is exactly where the entrance still is. This, not
            # the pause above, is what keeps a transit pause from re-engaging
            # on the creep to the bar.
            return
        if (
            braking
            or t.air_brakes_holding
            or not t.engine_on
            or t.stalled
            # Backing is the driver's own low-speed manoeuvre and never an
            # open road to hand back to. ``speed_mph`` is unsigned, so without
            # this a truck reversing at dock speed reads as rolling.
            or t.transmission.in_reverse
            or t.velocity_mps <= 0.0
            or t.speed_mph < KEEPER_MIN_MPH
        ):
            return
        limit, zone_reason = self.trip.speed_limit_at(self.trip.position_mi)
        if zone_reason is not None:
            if not self.ctx.settings.speed_keeper:
                return
            self._engage_keeper(limit, zone_reason, target_mph=limit, announce=False)
            self.ctx.say_event(
                "Automatic speed control resuming. Speed keeper holding "
                f"{self.ctx.settings.speed_text(self._keeper_mph)} through the "
                f"{zone_reason} zone.",
                interrupt=False,
                category=SpeechCategory.CONFIRMATION,
            )
            return
        if t.speed_mph < CRUISE_MIN_MPH:
            # Open road, but not yet at cruise's holding speed. Wait to engage
            # rather than snapping cruise on at the full remembered error and
            # flooring the throttle to chase a high target from a crawl. A zone
            # bridges the low-speed regime with the keeper (above); on the open
            # road the truck simply has to be at road speed first -- which is
            # what makes Shift+K behave like the automatic resume the tester
            # already trusts.
            return
        self._engage_cruise(self._speed_control_target_mph or limit, transition=True)

    def _cancel_cruise(self, *, preserve_session: bool = False) -> None:
        if preserve_session:
            self._clear_cruise(preserve_exit_cap=True)
        else:
            self._disarm_speed_control()

    def _cancel_keeper(self, *, preserve_session: bool = False) -> None:
        if preserve_session:
            self._clear_keeper()
        else:
            self._disarm_speed_control()

    def _restricted_zone_limit_ahead(self) -> tuple[float, str] | None:
        """A lower restricted-zone limit inside the player's advance-warning window.

        Returns ``(limit_mph, zone_reason)`` for the nearest construction or
        heavy-traffic zone that is closer than the spoken advance-warning
        distance and whose limit is lower than the current corridor limit.
        Returns ``None`` when there is nothing to pre-brake for.
        """
        if not self._speed_control_armed or not self.ctx.settings.speed_keeper:
            self._construction_slowdown = None
            return None
        held = self._construction_slowdown
        if held is not None and self.trip.position_mi < held[0]:
            # Keep aiming at a zone already being slowed for. The warning
            # window is sized in real seconds, so it retracts as cruise slows:
            # without this the zone dropped back out of sight and cruise wound
            # the truck up again on the approach to the barrels.
            limit_mph, reason = held[1], held[2]
        else:
            self._construction_slowdown = None
            lookahead_mi = self.trip._zone_warning_lookahead_mi()
            # Aim at the zone itself, skipping the merge taper in front of a
            # work zone exactly as the spoken zone warning does. The taper
            # starts earlier and posts a higher limit: slowing to the taper's
            # number still reached the barrels too fast, and slowing on the
            # taper's position had cruise easing before the player was told
            # why. Heavy traffic posts no taper, so it is simply the zone.
            zone = min(
                (
                    z
                    for z in self.trip.zones
                    if z.reason in RESTRICTED_ZONE_REASONS
                    and 0 < z.start_mi - self.trip.position_mi <= lookahead_mi
                ),
                key=lambda z: z.start_mi,
                default=None,
            )
            if zone is None:
                return None
            # Not before the player hears why: cruise and the warning share a
            # window, so which one landed first was down to frame order.
            from ..sim.trip import _zone_key

            if _zone_key(zone) not in self.trip._announced_zone_warnings:
                return None
            limit_mph, reason = zone.limit_mph, zone.reason
            self._construction_slowdown = (zone.end_mi, limit_mph, reason)
        current_limit, _ = self.trip.speed_limit_at(self.trip.position_mi)
        return (limit_mph, reason) if limit_mph < current_limit else None

    def _keeper_ease_mi(self, target_mph: float, scale: float) -> float:
        """How much road the keeper needs to be down to ``target_mph`` in time.

        Sized in real seconds and converted to miles at ``scale``, so time
        compression cannot spend the window before the truck can use it. The
        physical shed time is the floor: a big drop buys more road however
        relaxed the clock is. A settling tail on top puts the truck at the
        number ahead of the point rather than exactly on it.

        Where the shed is what the window is for, its seconds are priced at
        the speed the truck is actually DOING through them -- the mean of the
        two ends -- and the settling tail down at the new number. Charging
        every one of them at the speed the truck came in at claimed 0.64 of a
        mile for a 25-to-15 drop that costs 0.45, and since the eased number
        became a held floor (7ff22b6e) each surplus yard is crawled at the low
        number instead of simply re-planned. The truck reaching a service
        way's 15 a third of a mile early and sitting there is the "does not
        hold speeds on access roads" report (tester, 2026-08).

        The reaction budget underneath is untouched, and stays priced at
        today's speed: those seconds are spent hearing and deciding, before
        any slowing starts, so that is the road they really cost.
        """
        speed = max(self.truck.speed_mph, 1.0)
        target = max(1.0, min(target_mph, speed))
        reaction_mi = (KEEPER_EASE_REAL_S + KEEPER_SETTLE_REAL_S) * speed * scale / 3600.0
        shed_s = (speed - target) / MPH_PER_MPS / KEEPER_EASE_DECEL_MPS2
        # The mean of the two ends through the shed, then the settling tail
        # down at the new number, because that is where the truck spends it.
        shed_mi = shed_s * (speed + target) / 2.0 * scale / 3600.0
        shed_mi += KEEPER_SETTLE_REAL_S * target * scale / 3600.0
        # The cap trims the discretionary reaction budget, never the physical
        # shed -- the docstring above promises the shed is a floor, and the
        # old min() clipped it anyway: on long-route draws the ramped time
        # scale pushes the shed past 0.75 mi, the window came back capped,
        # and the keeper started too late to make the number by the sign
        # (the 1-in-4 "15.47 against 15.0" flake, ROADMAP 2026-08-19 --
        # which was the game quietly overshooting posted drops on
        # high-compression trips, not a test artifact).
        return max(shed_mi, min(KEEPER_EASE_MAX_MI, max(reaction_mi, shed_mi)))

    def _keeper_turn_ease_scale(self) -> float:
        """The clock the keeper will actually ease a corner on.

        A corner in play decompresses the trip to real time so "Advise 20" is
        plannable, and that happens a full spoken window out -- always wider
        than this ease. Sizing the ease on the compressed clock instead read
        the corner as close from half a mile back and held the whole block at
        the corner speed, which is the sluggishness this fix must not trade
        the tester's problem for.
        """
        return min(self.trip.effective_time_scale, 1.0)

    def _keeper_speed_ahead(self) -> tuple[float, str] | None:
        """The lower number the keeper must already be shedding speed for.

        Returns ``(mph, reason)`` for the SLOWEST thing ahead the truck cannot
        arrive at over -- a judged street turn's advise speed, or a posted
        limit lower than the one under the wheels -- among those close enough
        that easing has to start. ``None`` when the road ahead asks for
        nothing the truck is not already doing.

        Adaptive cruise refuses to engage inside a zone, so on facility
        streets the keeper is the only automation there is, and it read only
        the limit under the wheels. It held the street's 25 into corners that
        advise 20 and straight through the safe turnaround (tester, 2026-08).
        """
        position = self.trip.position_mi
        # Keep aiming at the point already being slowed for. The window is
        # sized in real seconds, so it retracts as the truck slows: without
        # this the corner dropped back out of sight and the keeper wound the
        # truck up again on its approach -- the same trap the construction
        # hold above exists to close. It is a FLOOR on what to shed for, never
        # the whole answer: a held target that could also HIDE a lower one is
        # how the second corner of a short block went unbraked (below).
        held = self._keeper_ease_target
        if held is not None and position >= held[0]:
            held = None
        demand = held
        turn_scale = self._keeper_turn_ease_scale()
        for cue in self._turn_cues_in_play():
            ahead = cue.at_mi - position
            if ahead <= 0.0:
                continue
            advise = self._turn_speed_mph(cue)
            if ahead > self._keeper_ease_mi(advise, turn_scale):
                continue
            # Every corner whose window is open, not just the nearest, and the
            # slowest of them wins. A corner holds its target through its own
            # tail, and a city block is shorter than that tail -- so aiming at
            # the nearest corner alone left the keeper still holding 20 for the
            # corner behind it while a 15 mph service way came up, and the
            # truck arrived over the number with the loop-back charged
            # (tester, turns "coming up really quickly").
            #
            # Held through each corner itself, not up to it: releasing on the
            # milepost puts the throttle back on mid-turn, so a run of corners
            # at one number holds to the far side of the last of them.
            until = cue.at_mi + TURN_COMMIT_TAIL_MI
            if demand is None or advise < demand[1]:
                demand = (until, advise, "turn")
            elif advise == demand[1]:
                demand = (max(demand[0], until), advise, demand[2])
        limit, _ = self.trip.speed_limit_at(position)
        horizon = min(self.trip.total_miles, position + KEEPER_EASE_MAX_MI)
        probe = position + KEEPER_LIMIT_PROBE_MI
        scale = self.trip.effective_time_scale
        while probe <= horizon + 1e-6:
            posted, reason = self.trip.speed_limit_at(probe)
            if posted < limit and probe - position <= self._keeper_ease_mi(posted, scale):
                if demand is None or posted < demand[1]:
                    demand = (probe, posted, reason or "posted limit")
                break
            probe += KEEPER_LIMIT_PROBE_MI
        self._keeper_ease_target = demand
        return None if demand is None else (demand[1], demand[2])
