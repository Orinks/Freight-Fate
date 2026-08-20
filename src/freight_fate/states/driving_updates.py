# ruff: noqa: F403,F405
from __future__ import annotations

from .. import engine_audio
from ..audio import (
    CH_AIR,
    CH_BRAKE,
    CH_EDGE,
    CH_JAKE,
    CH_LANE_GUIDE,
    CH_RADIO_FX,
    CH_ROAD,
)
from ..audio_fades import curve as _resolve_curve
from ..lane_guide_tone import LANE_GUIDE_TONE_KEY
from ..models.enforcement import (
    CHAIN_LAW_FINE,
    FAILURE_TO_STOP_CITATION_FINE,
    UNSAFE_DAMAGE_FINE,
    WEIGH_STATION_BYPASS_FINE,
    WORK_ZONE_BARRELS_FINE,
)
from ..radio import effective_range_miles, is_stream_entry, truck_elevation_ft
from ..speech_pacing import EventSpeechPacer, SpeechCategory
from ..speech_text import overspeed_nag, terse_silent
from .driving_core import *
from .driving_pacenotes import PACENOTE_MARGIN_MPH
from .driving_rest_states import (
    EnforcementStopState,
    FelonyStopState,
    TrafficStopState,
    _log_enforcement,
)

# The zone-entry line rides ROUTE now (queued, willing to wait this long
# behind other speech before flushing). Until the line has had that long to
# actually be spoken, holding the accelerator is not yet disregard -- nobody
# has told the driver anything, and speech latency must never masquerade as
# defiance (the research doc's coupled invariant on the R1 demotion).
LIMIT_DROP_SPEECH_LATENCY_S = EventSpeechPacer.WAIT_BUDGET_S[EventPriority.ROUTE]

# Spoken word for a lane count, used by the road-narrows call
# (_leave_a_lane_the_road_closed): "one lane" reads better than "1 lane(s)".
_LANE_COUNT_WORDS = {1: "one lane", 2: "two lanes", 3: "three lanes", 4: "four lanes"}


def _lane_count_words(count: int) -> str:
    return _LANE_COUNT_WORDS.get(count, f"{count} lanes")


# Re-crossings inside this window are pinballing, not lane changes.
LANE_CROSS_REPEAT_S = 4.0
# One brush against a vehicle alongside is one contact, however many times
# the tires cross the line while it is happening.
SIDESWIPE_REPEAT_S = 3.0

# FM fringe rendering. The bed creeps in below full quieting
# (radio.SIGNAL_FULL_VOLUME) and deepens quadratically; pickets begin below
# the static threshold (radio.STATIC_SIGNAL_THRESHOLD). Both are references
# to the radio module's own constants, not copies -- a hardcoded copy of
# each drifted silently out of sync with radio.py's smear ruling once
# already (2026-08-13), so this system reads the numbers it must agree
# with instead of remembering them. PICKET_DUCK is the program level while
# a splash owns the channel -- capture lost, near-silent, restored sharply.
FRINGE_BED_SIGNAL = SIGNAL_FULL_VOLUME
# Peak bed level ~= where the program used to sit, never a wall of noise on
# top of it: the owner's smear ruling -- static takes the program's place.
FRINGE_BED_MAX_VOLUME = 0.35
PICKET_SIGNAL = STATIC_SIGNAL_THRESHOLD
PICKET_DUCK = 0.12

# Shift plus the dial keys steps radio_volume by this much -- the same
# 10-percent grid the Settings > Audio "In-cab radio volume" row uses
# (main_menu.py's _volume helper), so the wheel and the menu can never
# disagree about a reachable value.
RADIO_VOLUME_STEP = 0.1

# How far down the left trigger has to be before it counts as the emergency
# application rather than a hard service stop. The controller help, the input
# hints and the manual have all promised "press the left trigger fully for
# the hardest stop" since the pad shipped, and nothing implemented it: the
# emergency flag was read from the B key alone, so a pad driver got a full
# service application and none of what the emergency one carries (owner,
# 2026-08-16). Set high on purpose -- this is the pedal you stand on when
# something is about to happen, and it must not fire on a firm normal stop.
PAD_EMERGENCY_BRAKE = 0.97
# Flutter rate bounds: parked multipath barely moves (slow wander floor);
# the ceiling is perceptual -- past ~9 events a second it just reads as
# noise, and the one-shot mixer would thrash.
PICKET_MIN_RATE_HZ = 0.4
PICKET_MAX_RATE_HZ = 9.0
FM_DEFAULT_MHZ = 98.0  # mid-band; wavelength varies ~10 percent over 88-108

# Personal playlist pacing. A file starts playing the moment play_music_file
# returns, so it only needs long enough for the fade-in not to read as a
# finished track. A stream entry connects on a worker thread and is silent
# until it lands, so it gets the same order of grace the curated real streams
# get before a re-tune (_radio_reconnect_timer), and two attempts before the
# entry is written off and the playlist moves on.
PLAYLIST_FADE_HOLD_S = 1.5
PLAYLIST_CONNECT_HOLD_S = 9.0
PLAYLIST_CONNECT_TRIES = 2
PLAYLIST_RETRY_S = 30.0  # how often a playlist with nothing playable looks again

# Sustained redline quietly grinds the engine down (Truck._update_temps), so
# the player must hear about it while it is happening, not at the end screen.
# The grace period lets a shift's momentary flare pass unremarked.
OVERREV_GRACE_S = 1.5
OVERREV_REPEAT_S = 10.0

# An automatic shift caps audible engine load so the bed doesn't duck out.
SHIFT_LOAD_CAP = 0.45
# ...but the load floor (0.68) keeps a capped engine at 82 percent of full
# level -- the "undertone at the last rpm" the owner heard through every
# shift. The disengage duck drops the whole bed below that floor through
# the torque interrupt, then rides the same recovery curve back up: the
# engine genuinely falls away and returns, like a clutch actually opening.
SHIFT_DISENGAGE_DUCK = 0.35
# The gear taking at the end of an auto shift: a soft pick from the shift
# bank, quieter than the interrupt clunk (0.65) that opened the shift.
SHIFT_END_CLUNK_VOLUME = 0.4
# When the shift completes the cap eases from SHIFT_LOAD_CAP back to full over
# this window. The curve (a key into audio_fades.CURVES) shapes the return: an
# ease-out leaves the shift level quickly -- so the engine doesn't sit soft --
# while still arriving at full load gently instead of snapping. A plain "linear"
# ramp had to be stretched long to hide the snap, which sounded too soft.
SHIFT_LOAD_RECOVERY_S = 0.032
SHIFT_LOAD_RECOVERY_CURVE = "ease_out"
_shift_recovery_curve = _resolve_curve(SHIFT_LOAD_RECOVERY_CURVE)

# Low-pass raw throttle before it reaches the audible engine-load envelope.
ENGINE_LOAD_SMOOTH_S = 0.45

# The jake's voice: synthesized growl loops at fixed rpm points, picked by
# nearest engine speed. Retarding power goes as cylinders x rpm, so the
# level grows with both the selected stage and the revs; the loop cuts out
# through shifts and clutch (the stair-stepping signature: buzz, gap,
# resume higher -- jake_v3.py's design notes, owner-approved 2026-07-18).
JAKE_LOOP_RPMS = (1200, 1400, 1600, 1800, 2000, 2200)
# Two, four, six cylinders. Stage one stays modest twice over: the owner
# heard 0.45 as still too loud (2026-07-22), and no one has a verified
# recording of a real low stage -- do not dramatize what we cannot confirm.
JAKE_STAGE_GAIN = (0.25, 0.65, 1.0)
JAKE_MIN_RPM = 950.0

# How far over a curve's advisory speed the truck has to be before the curve
# assist reaches for the retarder. The engine brake is for shedding real
# speed; a bend the truck is a few mph over is a lift and a touch of the
# drums, which do it quietly and are legal in every town.
#
# This threshold no longer gates the curve assist at all: a corner never
# raises the retarder, whatever the overspeed (owner ruling 2026-08-11). It
# survives as the line the service trim below draws for "well over the
# advisory", which is what it always measured.
CURVE_ASSIST_JAKE_MIN_MPH = 10.0
# How hard the retarder works once a GRADE has called for it: past this much
# over the advisory it gets everything, otherwise the working setting, stage
# two. Reached only on a downgrade -- see _update_lane.
CURVE_ASSIST_JAKE_FULL_MPH = 15.0

# Auto jake (automatic box, owner design 2026-07-22): J arms retarder
# management the way a real AMT integrates it. The controller holds the
# engagement speed (or the descent-control target) by stepping the stage,
# rate-limited so the growl steps audibly like an ECU thinking, and never
# selects a stage whose retard the drive axle cannot hold.
AUTO_JAKE_STEP_S = 1.5  # seconds between stage steps
AUTO_JAKE_OVER_MPH = 1.0  # this far above target: step up
AUTO_JAKE_UNDER_MPH = 3.0  # this far below target: step down

# The air-fill loop re-arms only this far below governor release. air_ready
# flips at exactly 100 psi and normal service braking dips the reservoirs a
# few psi, so without hysteresis the fill hiss would flutter on and off every
# few seconds all drive long. A cold start (55) or a real low-air situation
# still brings it in; once playing it runs until the air is ready again.
AIR_FILL_REARM_PSI = 8.0
# A bed under the idle, not a foreground event (owner's ear, 2026-07-22).
AIR_FILL_VOLUME = 0.6


class DrivingUpdateMixin:
    def _update_critical_respeak(self, dt: float) -> None:
        """Re-speak a safety call the player silenced before it finished.

        Ctrl is a screen-reader reflex and must always silence instantly --
        but a curve call cut mid-sentence is information the road still
        owes the driver (owner's worry, 2026-07-20: "how you gonna get it
        spoken?"). If Ctrl landed inside the call's speaking window, the
        call re-arms once and speaks again with a REFRESHED distance --
        provided the bend is still ahead and the truck is still above its
        advisory. Passed it, or slowed for it: stay quiet."""
        if self._critical_curve is None:
            return
        self._critical_call_age_s += dt
        if self._critical_respeak_at is None:
            if self._critical_call_age_s > CRITICAL_CALL_WINDOW_S:
                self._critical_curve = None  # spoke to the end, most likely
            return
        if self._critical_call_age_s < self._critical_respeak_at:
            return
        curve = self._critical_curve
        self._critical_curve = None
        self._critical_respeak_at = None
        ahead = curve.start_mi - self.trip.position_mi
        speed = self.truck.speed_mph
        if ahead <= 0 or speed <= curve.advisory_mph + PACENOTE_MARGIN_MPH:
            return
        pan = -PACENOTE_CUE_PAN if curve.direction == "L" else PACENOTE_CUE_PAN
        self.ctx.audio.play("vehicle/curve_bink", volume=0.9, pan=pan)
        self.ctx.say_event(
            self._pacenote_text(curve, ahead, speed),
            interrupt=True,
            category=SpeechCategory.NAVIGATION,
        )

    def _note_critical_speech_stopped(self) -> None:
        """Called from the Ctrl handler: arm the one-shot refreshed re-speak
        when the silence landed inside a safety call's speaking window."""
        if (
            self._critical_curve is not None
            and self._critical_respeak_at is None
            and self._critical_call_age_s < CRITICAL_CALL_WINDOW_S
        ):
            self._critical_respeak_at = self._critical_call_age_s + CRITICAL_RESPEAK_DELAY_S

    def update(self, dt: float) -> None:
        t = self.truck
        # A fresh loaded run out of a chain-capable origin starts on the
        # facility's streets. Decided on the first tick, never on a resume:
        # from_snapshot marks the check done and re-enters a chain itself.
        if not self._departure_checked:
            self._departure_checked = True
            if not self.resumed:
                self._begin_departure_chain()
        # pacing can be changed from the pause menu mid-trip; keep the trip's
        # clock compression in step with the setting
        self.trip.time_scale = self.ctx.settings.time_scale
        tuning = tuning_for_time_scale(self.trip.time_scale)
        self.trip.hazard_scale = (
            hos.hazard_scale(self.ctx.settings.hos_mode) * tuning.hazard_frequency
        )
        self.trip.traffic_manager.hazard_scale = self.trip.hazard_scale
        self._sync_radio_settings()
        # A new leg is a fresh road, so a once-per-leg tip earns one more
        # telling (Disposition.FIRST_OCCURRENCE).
        leg = self.trip.current_leg_index
        if leg != self._ladder_leg_index:
            self._ladder_leg_index = leg
            self.ctx.reset_ladder_leg_memory()
        if self._destination_exit_response_s > 0.0:
            self._destination_exit_response_s = max(
                0.0,
                self._destination_exit_response_s - dt,
            )
            if self._destination_exit_response_s == 0.0 and self._exit_stop is None:
                # A driver who stopped after the early callout must still get a
                # fresh, closer instruction once the normal window reaches them.
                self._destination_exit_announced_key = ""
        self._sync_weather_source()
        keys = pygame.key.get_pressed()
        ramp = dt * 2.2
        self._brake_lockout_cue_timer = max(0.0, self._brake_lockout_cue_timer - dt)
        # Controller triggers/clutch are analog held positions blended in below;
        # the keyboard keys keep their ramped behavior so both devices work.
        pad = self.ctx.controller
        pad_on = pad.active
        pad_throttle = pad.throttle if pad_on else 0.0
        pad_brake = pad.brake if pad_on else 0.0
        key_up = keys[pygame.K_UP]
        key_down = keys[pygame.K_DOWN]
        # Latching pedals: after the double-tap-and-hold gesture a pedal
        # reads as held right here, so everything downstream -- the reverse
        # gesture, cruise cancel, the hazard's brake answer -- sees one
        # truth. Microsleeps stay on the raw keys: only a live reaction
        # proves the driver awake.
        # The latch releases on the emergency application, so it has to see the
        # pad's version of it too. Read raw here rather than gated on backing:
        # a trigger buried to the floor should drop a latched pedal whichever
        # direction the truck is going.
        hand_up, key_down, throttle_latched = self._update_pedal_latches(
            key_up,
            key_down,
            pad_throttle,
            pad_brake,
            keys[pygame.K_b] or pad_brake >= PAD_EMERGENCY_BRAKE,
            dt,
        )
        # The latch is the LOWEST-priority speed input in "assists first"
        # mode: while cruise, the keeper, or curve assist is engaged it
        # contributes nothing, and it ramps back in when the last of them
        # releases -- no re-gesture (owner design 2026-08-13). A hand-held
        # key stays a live manual override, which is why the assists are
        # handed hand_accelerating below rather than this blended value.
        # "latch first" is the original meaning: the latch is the driver
        # insisting on speed, so the assists see it as a hand and stand
        # down instead.
        latch_mode = self.ctx.settings.pedal_latch
        self._latch_yielding = (
            throttle_latched and latch_mode == "assists first" and self._speed_authority_engaged()
        )
        key_up = hand_up or (throttle_latched and not self._latch_yielding)
        accelerating = key_up or pad_throttle > 0.05
        assist_up = hand_up or (throttle_latched and latch_mode == "latch first")
        hand_accelerating = assist_up or pad_throttle > 0.05
        braking_key = key_down or pad_brake > 0.05
        # The shift gesture keys off a fresh press, so it reads the trigger's
        # instantaneous position rather than the smoothed accelerate/brake
        # values above -- otherwise the smoothing lag swallows a quick tap and
        # the release-then-press never registers as neutral in between.
        accel_held = key_up or (pad.throttle_target if pad_on else 0.0) > 0.05
        brake_held = key_down or (pad.brake_target if pad_on else 0.0) > 0.05
        backing = self._update_reverse_controls(
            accelerating, braking_key, accel_held, brake_held, dt
        )
        if accelerating and not backing and t.air_brakes_holding:
            self._maybe_say_air_brake_lockout()
        elif not t.air_brakes_holding:
            # The lockout actually cleared (parking brake released, spring
            # brakes recovered) -- not merely the player's foot off the
            # pedal, which must NOT drop the key or the next press would
            # re-announce an unchanged reason. The next time it arms is a
            # fresh instance of the condition and gets its warning again,
            # even with identical wording (mirrors _update_overrev's reset
            # of "engine_redline").
            self.ctx.reset_event_condition("air_brake_lockout")
        if key_up and not backing and not t.transmission.in_reverse:
            if t.engine_brake:
                t.engine_brake = False
                self.ctx.say_event(
                    "Jake off.", interrupt=False, category=SpeechCategory.CONFIRMATION
                )
            t.throttle = min(1.0, t.throttle + ramp)
        elif backing:
            t.throttle = min(0.45, t.throttle + ramp)
        else:
            t.throttle = max(0.0, t.throttle - ramp * 2)
        if pad_throttle > 0.05 and not backing and not t.transmission.in_reverse:
            if t.engine_brake:
                t.engine_brake = False
                self.ctx.say_event(
                    "Jake off.", interrupt=False, category=SpeechCategory.CONFIRMATION
                )
            t.throttle = max(t.throttle, pad_throttle)
        # Keyboard ramps the brake up and down; the analog trigger sets a direct
        # held floor on top of that.
        braking_ramp = (key_down and not backing) or (accelerating and t.velocity_mps < -0.1)
        if braking_ramp:
            t.brake = min(1.0, t.brake + ramp * 1.5)
        else:
            t.brake = max(0.0, t.brake - ramp * 3)
        if pad_brake > 0.05 and not backing:
            t.brake = max(t.brake, pad_brake)
        braking = braking_ramp or (pad_brake > 0.05 and not backing)
        # "not backing" matters more here than it looks: in automatic, holding
        # the left trigger from a stop is the gesture that shifts to reverse,
        # so without it every backing manoeuvre would slam the emergency
        # application on and flat-spot the tires for it.
        emergency = keys[pygame.K_b] or (pad_brake >= PAD_EMERGENCY_BRAKE and not backing)
        # A real truck drops cruise at the first tap of the service brake.
        # Only the player's own pedal cancels here; the sim's automatic brake
        # ramps (reverse arrest, hazard events) go through their own cancels.
        if self._cruise_mph is not None and (braking_key or emergency) and not backing:
            self._cancel_cruise()
            self.ctx.say_event("Cruise off.", interrupt=False, category=SpeechCategory.CONFIRMATION)
        if emergency:
            # no ramp: slams to full application instantly, plus spring brakes
            if not t.emergency_brake and abs(t.velocity_mps) > 1:
                if self.ctx.audio.has_asset("vehicle/ebrake"):
                    # The licensed cut: one big sustained air event.
                    self.ctx.audio.play("vehicle/ebrake", volume=0.9)
                else:
                    self.ctx.audio.play("vehicle/brake_air", volume=1.0)
            t.throttle = 0.0
            t.brake = 1.0
        t.emergency_brake = emergency
        # Hard braking (emergency or heavy service) shudders the pad while it
        # lasts; the engine's TTL lets it lapse a few frames after we stop. Only
        # while moving *forward*: rolling backward, the sim ramps the service
        # brake to full on its own to arrest the reverse before shifting to
        # drive, and that must not read as a hard stop and buzz the whole time.
        if t.velocity_mps > 1 and (emergency or t.brake >= 0.85):
            self.ctx.controller.rumble.hard_brake(1.0 if emergency else t.brake)
        # Brake sounds ride the application edges. A hysteresis flag (arm at
        # 0.05, release below 0.02) keeps a steady analog trigger -- or a held
        # key -- from retriggering frame after frame. The emergency brake
        # plays its own louder cue, so it only arms the flag.
        # PRESS: the mechanical clunk of the valve, leveled by press force
        # (locked spec 2026-07-21; the classic air chirp is the fallback).
        # RELEASE: the air bleeding back out -- the hiss bed held for a
        # length, and at a level, set by how hard the brakes were applied.
        # The release plays at any speed: braking to a halt then letting off
        # is exactly when a real rig gives its loudest pssht.
        if t.brake >= 0.05:
            if not self._brake_air_hissed and not emergency and abs(t.velocity_mps) > 1:
                force = max(0.0, min(1.0, t.brake))
                self.ctx.audio.play_bank(
                    "vehicle/brake_clunk", "vehicle/brake_air", volume=0.35 + 0.35 * force
                )
            self._brake_air_hissed = True
            self._brake_peak_application = max(self._brake_peak_application, t.brake)
        elif t.brake < 0.02:
            peak = self._brake_peak_application
            # Locked spec levels (0.07-0.12 mix, "all quiet under the
            # engine"): a light release is a barely-there sigh below the
            # road bed, not a foreground pssht -- shipped 4x hot at first
            # and the owner heard every tap on a twisty descent. Feather
            # releases under the floor stay silent entirely.
            if (
                self._brake_air_hissed
                and peak >= 0.15
                and not emergency
                and self.ctx.audio.has_asset("vehicle/brake_hiss_bed")
            ):
                # Road noise masks the release at speed, exactly as in a real
                # cab: rolling releases fade toward inaudible while the big
                # pssht after braking to a stop keeps its full voice.
                masking = max(0.25, 1.0 - abs(t.velocity_mps) / 20.0)
                self.ctx.audio.start_loop(
                    CH_BRAKE,
                    "vehicle/brake_hiss_bed",
                    volume=(0.10 + 0.15 * peak) * masking,
                    fade_ms=0,
                )
                self.ctx.audio.stop_loop(CH_BRAKE, fade_ms=int(160 + 800 * peak))
            self._brake_air_hissed = False
            self._brake_peak_application = 0.0
        desired_automatic = self.ctx.settings.automatic_transmission
        if t.transmission.automatic != desired_automatic:
            t.transmission.automatic = desired_automatic
            mode = "automatic" if desired_automatic else "manual"
            self.ctx.say_event(
                f"Transmission changed to {mode}.",
                interrupt=True,
                category=SpeechCategory.CONFIRMATION,
            )

        clutch_pressed = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        clutch_val = 1.0 if clutch_pressed else 0.0
        if pad_on:
            clutch_val = max(clutch_val, pad.clutch)
        t.transmission.clutch = clutch_val if not t.transmission.automatic else 0.0
        clutch_disengaged = t.transmission.clutch > 0.5 or t.transmission.shifting
        self._update_lane(keys, dt)
        self._update_exit_preparation(keys, dt)
        self._resume_speed_control_if_ready(braking=braking)
        self._update_cruise(dt, braking, hand_accelerating, clutch_disengaged)
        self._update_keeper(dt, braking, hand_accelerating, clutch_disengaged)
        # The hazard assist's held application belongs here with the other
        # assists' floors, ahead of the physics -- see _apply_hazard_brake.
        # _update_hazard, which decides it, runs at the end of the frame.
        self._apply_hazard_brake()
        self._update_horn_protection()

        self._update_auto_jake(dt)
        self._track_driving_badges(dt)
        if t.transmission.automatic and t.engine_on:
            new_gear = t.auto_shift()
            if new_gear is not None:
                self.ctx.audio.play_bank("vehicle/shift_auto", "vehicle/gear_shift", volume=0.65)

        was_on = t.engine_on
        was_air_ready = t.air_ready
        was_low_air = t.air_low_warning
        was_spring_brake = t.spring_brakes_active
        t.update(dt)
        self._update_air_brake_announcements(was_on, was_air_ready, was_low_air, was_spring_brake)
        if was_on and not t.engine_on:
            self.ctx.audio.engine_stop()
            if t.stalled:
                self.ctx.say_event(
                    f"The engine stalled. Press {self.ctx.control_hint('engine')} to restart, "
                    "and use a lower gear at low speed.",
                    interrupt=True,
                    category=SpeechCategory.SAFETY,
                )
            elif t.fuel_gal <= 0:
                self._handle_out_of_fuel()

        # Keep the trip's spoken-distance units in step with a live settings
        # change; the setter only re-renders cues when the choice actually flips.
        self.trip.imperial = self.ctx.settings.imperial_units
        pos_before = self.trip.position_mi
        # Same-lane traffic checks and spoken relative lanes follow the
        # player's discrete lane, so mirror it before the trip advances.
        self.trip.traffic_manager.player_lane = self.lane.lane
        # And while a tap-change is underway, lead selection follows the
        # lane it is moving into instead -- see TrafficManager.lead_vehicle.
        self.trip.traffic_manager.player_lane_target = self._lane_change_target
        # Tell the trip model which stop's exit is signaled or on the ramp so its
        # plan-cancelled warning can tell a driver who is taking the exit from one
        # who blew past it. Set before trip.update (which runs _check_stops) and
        # before _update_exit (which clears _exit_stop on a miss), so on the exact
        # crossing tick the flag still reflects the armed exit.
        active_exit = self._ramp_stop or self._exit_stop
        self.trip._exit_in_progress = active_exit.key if active_exit else None
        # On the ramp the highway odometer holds and the ramp consumes the
        # movement instead; the trip records how far the truck rolled either way.
        self.trip.on_ramp = self._ramp_mi is not None
        for event in self.trip.update(dt):
            self._handle_trip_event(event)
        if (
            self._selected_stop_key is not None
            and self.trip.planned_stop_key != self._selected_stop_key
            and self._ramp_stop is None
        ):
            # The trip model canceled a passed plan. Do not leave explicit
            # intent or its stopping assist armed for a later optional exit.
            self._clear_selected_stop_intent()
        self._check_weigh_station_enforcement(pos_before)
        self._check_unsafe_damage_enforcement()
        self._check_destination_exit()
        self._check_gate_approach_warning(dt)
        self._update_turn_commitment(dt)
        self._update_exit(self.trip.last_moved_mi, dt)
        # Immediately after the exit watch, which is what turns a signaled
        # scale exit into a ramp. Only now can a scale crossing be told apart
        # from a check-in.
        self._resolve_weigh_station_bypass()
        # Reads the same last_moved_mi the exit watch just used, so the
        # distance it counts back is the distance the trip actually lost.
        self._update_wrong_way(dt)
        # After the trip has moved the truck and stepped the bubble, so the
        # crossing this reads is the one that just happened.
        self._update_traffic_passes(dt)
        # Right after the passes, and for the same reason: the lane the driver
        # moved out of is only open once the bubble has been stepped.
        self._update_lane_gap(dt)

        self._update_hours_and_fatigue(dt)
        self._update_audio(dt)
        self._update_announcements(dt)
        self._update_ambient_events(dt)
        self._update_ramp_light(dt)
        self._update_critical_respeak(dt)
        self._update_hazard(dt)
        self._update_grade_advisory()
        self._update_microsleep(keys, dt)
        # Damage bands run before the over-rev warning, so a redline call in
        # the same frame already names the band the truck just entered.
        self._update_damage_bands(dt)
        self._update_cargo_condition(dt)
        # After the cargo pass, so the bend's advisory is already on the truck
        # for the lateral wave. Returns immediately on any non-tank load.
        self._update_liquid_cues(dt)
        self._update_overrev(dt)
        # The watch runs first on purpose. If an officer opens a pull-over
        # this frame, _update_speeding returns early on the live stop, so one
        # instance of speeding can never be charged twice -- once as a ticket
        # and again as a silent at-delivery strike.
        self._update_enforcement_watch(dt)
        self._update_speeding(dt, accelerator_held=accel_held)
        self._update_engine_brake_zone(dt)
        self._update_pull_over(dt, service_braking=braking or emergency)
        self._update_brake_heat_cue(dt)
        self._update_traction_cues()
        self._update_chain_law()
        # Before the trip.finished branch on purpose: the arrival gate below
        # only runs once the truck has ALREADY arrived, so it can hold the
        # brake but can never slow the approach. See the method.
        self._update_destination_approach_assist()
        if self.tutorial:
            self.tutorial.update(dt, t)
        if self.trip.finished:
            self._gate_reminder_s = max(0.0, self._gate_reminder_s - dt)
            if self._departure_chain:
                # End of the origin's streets: merge onto the highway trip.
                self._finish_departure_chain()
            elif self.phase == DRIVE_PHASE_PICKUP:
                self._handle_pickup_gate()
            elif self._ramp_mi is not None:
                return
            elif not self._destination_exit_taken:
                self._handle_missed_destination_exit()
            else:
                self._handle_arrival_gate()

    def _maybe_say_air_brake_lockout(self) -> None:
        if self._brake_lockout_cue_timer > 0:
            return
        self._brake_lockout_cue_timer = 4.0
        t = self.truck
        # One standing condition -- "why the truck will not roll yet" --
        # with three mutually exclusive descriptions. A player who holds the
        # accelerator against the lockout re-triggers this every 4 seconds;
        # sharing the key means an unchanged reason (still parked, still
        # building air at the same psi) speaks once, while a genuine change
        # (engine started, psi climbed, brake released then reset) speaks
        # again because the text itself differs.
        if not t.engine_on:
            self._set_status("Start the engine before releasing the brakes.")
            message = (
                "Engine off."
                if self._terse_speech()
                else "Start the engine first; air pressure cannot build with the engine off."
            )
            self.ctx.say_event(
                message,
                interrupt=False,
                # ROUTE, not the ambient default: this line is the reason the
                # truck will not move under the driver's own throttle. As
                # AMBIENT it was droppable as stale chatter, and the
                # adversarial battery caught it being dropped the moment real
                # traffic started appearing on the leg -- the AADT spawn
                # change put a brake-lights advisory and an achievement
                # ahead of it in the same channel, and the lockout lost a
                # race it had never been in. Same call as the toll charge and
                # the adaptive-cruise lines: a consequence is not colour.
                priority=EventPriority.ROUTE,
                key="air_brake_lockout",
                category=SpeechCategory.STATUS,
            )
        elif not t.air_ready:
            self._set_status("Waiting for air pressure before the truck can move.")
            message = (
                f"Air pressure {t.air_pressure_psi:.0f} psi."
                if self._terse_speech()
                else (
                    f"Air pressure {t.air_pressure_psi:.0f} psi. Wait for 100 psi, "
                    f"then press {self.ctx.control_hint('parking_brake')} "
                    "to release the parking brake."
                )
            )
            self.ctx.say_event(
                message,
                interrupt=False,
                # ROUTE, not the ambient default: this line is the reason the
                # truck will not move under the driver's own throttle. As
                # AMBIENT it was droppable as stale chatter, and the
                # adversarial battery caught it being dropped the moment real
                # traffic started appearing on the leg -- the AADT spawn
                # change put a brake-lights advisory and an achievement
                # ahead of it in the same channel, and the lockout lost a
                # race it had never been in. Same call as the toll charge and
                # the adaptive-cruise lines: a consequence is not colour.
                priority=EventPriority.ROUTE,
                key="air_brake_lockout",
                category=SpeechCategory.STATUS,
            )
        elif t.parking_brake:
            brake_hint = self.ctx.control_hint("parking_brake")
            self._set_status(f"Parking brake set. Press {brake_hint} to release it.")
            message = (
                "Parking brake set."
                if self._terse_speech()
                else f"Parking brake set. Press {brake_hint} to release it."
            )
            self.ctx.say_event(
                message,
                interrupt=False,
                # ROUTE, not the ambient default: this line is the reason the
                # truck will not move under the driver's own throttle. As
                # AMBIENT it was droppable as stale chatter, and the
                # adversarial battery caught it being dropped the moment real
                # traffic started appearing on the leg -- the AADT spawn
                # change put a brake-lights advisory and an achievement
                # ahead of it in the same channel, and the lockout lost a
                # race it had never been in. Same call as the toll charge and
                # the adaptive-cruise lines: a consequence is not colour.
                priority=EventPriority.ROUTE,
                key="air_brake_lockout",
                category=SpeechCategory.STATUS,
            )

    def _update_air_brake_announcements(
        self,
        was_engine_on: bool | None = None,
        was_ready: bool | None = None,
        was_low: bool | None = None,
        was_spring: bool | None = None,
    ) -> None:
        t = self.truck
        # Backward compatibility for older call sites/tests that pass
        # (was_ready, was_low, was_spring) positionally.
        if (
            was_spring is None
            and was_engine_on is not None
            and was_ready is not None
            and was_low is not None
        ):
            was_engine_on, was_ready, was_low, was_spring = (
                t.engine_on,
                bool(was_engine_on),
                bool(was_ready),
                bool(was_low),
            )
        if was_engine_on is None:
            was_engine_on = t.engine_on
        if was_ready is None:
            was_ready = t.air_ready
        if was_low is None:
            was_low = t.air_low_warning
        if was_spring is None:
            was_spring = t.spring_brakes_active

        if t.air_low_warning and t.engine_on and (not self._low_air_said or not was_engine_on):
            self._low_air_said = True
            self.ctx.audio.play("vehicle/low_air_buzzer", volume=0.7)
            self.ctx.controller.rumble.alert()
            # What to do about it depends on where the truck is. Parked, the
            # answer is to leave the parking brake alone. Rolling, that advice
            # is nonsense and the driver needs the real one: get stopped while
            # there is still air to stop with, because the spring brakes will
            # do it for them at 40 psi wherever they happen to be.
            rolling = abs(t.velocity_mps) > 0.3
            advice = (
                "Get stopped and let the compressor build; the spring brakes set at 40 psi."
                if rolling
                else "Keep the parking brake set until pressure builds."
            )
            message = (
                f"Low air: {t.air_pressure_psi:.0f} psi."
                if self._terse_speech()
                else f"Low air warning: {t.air_pressure_psi:.0f} psi. {advice}"
            )
            # Parked, this is a band readout; rolling, it is the last warning
            # before the spring brakes set on their own -- the same
            # urgency-decides-the-category shape as the HOS check above.
            self.ctx.say_event(
                message,
                interrupt=True,
                category=SpeechCategory.SAFETY if rolling else SpeechCategory.STATUS,
            )
        elif t.air_pressure_psi >= t.specs.air_low_warning_clear_psi:
            # Re-arm only once pressure has recovered clear of the warning
            # threshold (hysteresis), not merely ticked a fraction above it.
            # Heavy or repeated service braking otherwise leaves pressure
            # bouncing right around air_low_warning_psi while the compressor
            # catches up, and each bounce re-fired the full warning line.
            self._low_air_said = False

        if t.spring_brakes_active and not was_spring and not self._spring_brake_said:
            self._spring_brake_said = True
            self.ctx.audio.play("vehicle/low_air_buzzer", volume=0.9)
            self.ctx.controller.rumble.alert()
            message = (
                "Spring brakes applied."
                if self._terse_speech()
                else (
                    "Spring brakes applied from low air pressure. Stop and let the "
                    "compressor rebuild air before moving."
                )
            )
            # The low-air band is a STATUS readout; the spring brakes actually
            # setting is the emergency the band was warning about -- SAFETY.
            self.ctx.say_event(message, interrupt=True, category=SpeechCategory.SAFETY)
        elif not t.spring_brakes_active:
            self._spring_brake_said = False

        if t.air_ready and t.parking_brake and not was_ready and not self._air_ready_said:
            # The cue's whole job is "you can release the parking brake now", so
            # only announce while it is set. Once released (rolling, or braking to
            # a stop on arrival), a dip back across the threshold must not
            # re-announce it.
            self._air_ready_said = True
            self.ctx.audio.play("vehicle/air_dryer_purge", volume=0.65)
            brake_hint = self.ctx.control_hint("parking_brake")
            self._set_status(f"Air ready. Press {brake_hint} to release the parking brake.")
            message = (
                f"Air ready: {t.air_pressure_psi:.0f} psi."
                if self._terse_speech()
                else (
                    f"Air pressure ready at {t.air_pressure_psi:.0f} psi. "
                    f"Press {brake_hint} to release the parking brake."
                )
            )
            self.ctx.say_event(message, interrupt=False, category=SpeechCategory.STATUS)
            # air_ready is retired as an award (folded into "first_day" at
            # pickup completion, see city_pickup.py); the catalog entry and
            # id stay so the cloud validator's allow-list never sees a
            # removed id.
        elif t.air_low_warning:
            # Re-arm the ready cue only after a genuine depletion (low-air), not
            # the routine 100-125 psi compressor cycling: the parking-release
            # threshold sits at the cut-in pressure, so air_ready otherwise
            # flickers across it every cycle and re-announces back to back.
            self._air_ready_said = False

    def _update_reverse_controls(
        self,
        accelerating: bool,
        braking_key: bool,
        accel_held: bool | None = None,
        brake_held: bool | None = None,
        dt: float = 1 / 60.0,
    ) -> bool:
        """Return True when the current key state means backing up.

        ``accel_held``/``brake_held`` are the instantaneous (unsmoothed) press
        states used for the shift-gesture edge detection; they default to the
        ramped ``accelerating``/``braking_key`` for the keyboard, where the two
        are the same.
        """
        t = self.truck
        tr = t.transmission
        if accel_held is None:
            accel_held = accelerating
        if brake_held is None:
            brake_held = braking_key
        # Deliberate direction changes use a fresh press (rising edge). Simple
        # direction changes keep the familiar behavior of holding the control
        # through the stop. Track both edges in either mode so changing the
        # setting during a drive cannot leave stale input state behind.
        brake_edge = brake_held and not self._reverse_brake_held
        accel_edge = accel_held and not self._reverse_accel_held
        self._reverse_brake_held = brake_held
        self._reverse_accel_held = accel_held
        if not tr.automatic:
            self._direction_armed = ""
            self._direction_hold_s = 0.0
            return tr.in_reverse and braking_key and not accelerating
        # One safe gesture for every direction change: a FRESH press observed
        # at a standstill arms it, and the gear engages only after the
        # control is held through a short beat. A press that lands while
        # still rolling is part of a stop and never arms; a hold that
        # predates the stop never arms; a quick confirm-tap at a stop -- how
        # a screen-reader driver checks the truck is holding -- just brakes.
        # (Owner-hit three ways on 2026-07-14: held through the stop,
        # feathered to a stop, and confirm-tapped at the yard.)
        stopped = abs(t.velocity_mps) < 0.3
        want = "forward" if tr.in_reverse else "reverse"
        control_edge = accel_edge if tr.in_reverse else brake_edge
        control_held = accel_held if tr.in_reverse else brake_held
        other_held = brake_held if tr.in_reverse else accel_held
        if control_edge and stopped and not other_held:
            self._direction_armed = want
            self._direction_hold_s = 0.0
        if self._direction_armed == want and control_held and stopped and not other_held:
            self._direction_hold_s += dt
            if self._direction_hold_s >= DIRECTION_CHANGE_HOLD_S:
                self._direction_armed = ""
                self._direction_hold_s = 0.0
                tr._shift_timer = 0.0
                self.ctx.audio.play_bank("vehicle/shift_manual", "vehicle/gear_shift", volume=0.55)
                if want == "forward":
                    tr.gear = 1
                    self._set_status("Forward gear selected.")
                    self.ctx.say_event(
                        "Forward gear selected.",
                        interrupt=False,
                        category=SpeechCategory.CONFIRMATION,
                    )
                    return False
                tr.gear = REVERSE
                self._cancel_cruise()
                self._set_status("Reverse selected. Backing slowly.")
                self.ctx.say_event(
                    "Reverse selected. Backing slowly.",
                    interrupt=False,
                    category=SpeechCategory.CONFIRMATION,
                )
                return True
        else:
            self._direction_armed = ""
            self._direction_hold_s = 0.0
        if tr.in_reverse:
            return braking_key and not accelerating
        return False

    def _update_hours_and_fatigue(self, dt: float) -> None:
        """Advance the HOS shift clock and fatigue on game time, not wall time."""
        gm = dt * self.trip.effective_time_scale / 60.0  # game minutes this frame
        moving = self.truck.speed_mph > 5.0
        mode = self.ctx.settings.hos_mode
        p = self.ctx.profile

        if self.job.bobtail:
            self.hos.off_duty(gm)
        elif moving:
            self.hos.drive(gm)
        else:
            self.hos.on_duty(gm)  # the 14-hour window runs even while parked
        if mode not in hos.HOS_NON_ENFORCED_MODES and self._hazard_deadline is None:
            for message in self.hos.check_warnings(mode):
                self.ctx.audio.play("ui/warning")
                self.ctx.controller.rumble.alert()
                # The clock running down is the drive, not colour: even the
                # non-urgent countdown must not queue behind chatter, and if
                # something cuts it off it comes back.
                urgent = hos.warning_is_urgent(message)
                self.ctx.say_event(
                    message,
                    interrupt=urgent,
                    priority=EventPriority.CRITICAL if urgent else EventPriority.ROUTE,
                    category=SpeechCategory.SAFETY if urgent else SpeechCategory.STATUS,
                )
        self.trip.hos_violation = mode not in hos.HOS_NON_ENFORCED_MODES and self.hos.in_violation(
            mode
        )

        night = is_night(self.trip.local_hour)
        now_h = self._absolute_game_hour()
        if moving:
            # Pressure-mode tuning scales how fast the day wears on you, and
            # an active food/drink buff slows accrual (data/buffs.py); neither
            # touches the HOS duty clock above.
            fatigue_mult = tuning_for_time_scale(self.trip.time_scale).fatigue_rate
            p.fatigue = min(
                100.0,
                p.fatigue
                + hos.fatigue_rate_per_min(night) * gm * fatigue_mult * p.fatigue_buff_rate(now_h),
            )
        for worn in p.expire_buffs(now_h):
            text = worn.get("worn_off") or f"The {worn.get('label', 'buff').lower()} has worn off."
            self.ctx.say_event(text, interrupt=False, category=SpeechCategory.STATUS)
        self.truck.engine_wear_buff_mult = float(self.rig_buffs.get("engine", {}).get("rate", 1.0))
        self.truck.tire_wear_buff_mult = float(self.rig_buffs.get("tire", {}).get("rate", 1.0))
        fatigue = p.fatigue
        alerts_clear = self._hazard_deadline is None
        if fatigue >= hos.FATIGUE_SEVERE and not self._severe_said and alerts_clear:
            self._severe_said = True
            self._fatigue_cue_gm = 0.0
            self.ctx.audio.play("vehicle/rumble_strip", volume=0.8)
            self.ctx.say_event(
                "You are dangerously drowsy and drifting out of "
                "your lane. Sleep at the next rest stop.",
                interrupt=True,
                category=SpeechCategory.SAFETY,
            )
        elif fatigue >= hos.FATIGUE_DROWSY and not self._drowsy_said and alerts_clear:
            self._drowsy_said = True
            self._fatigue_cue_gm = 0.0
            self.ctx.audio.play("driver/yawn", volume=0.9)
            # An instruction to act, not roadside colour: ROUTE keeps it out
            # from behind chatter and brings it back if it gets talked over.
            self.ctx.say_event(
                "You are getting drowsy. Take a break or sleep at a rest stop.",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.SAFETY,
            )
        if fatigue < hos.FATIGUE_DROWSY:
            self._drowsy_said = False
        if fatigue < hos.FATIGUE_SEVERE:
            self._severe_said = False
        # periodic audio cues while drowsiness persists
        if moving and fatigue >= hos.FATIGUE_DROWSY:
            self._fatigue_cue_gm += gm
            if self._fatigue_cue_gm >= 15.0:
                self._fatigue_cue_gm = 0.0
                if fatigue >= hos.FATIGUE_SEVERE:
                    self.ctx.audio.play("vehicle/rumble_strip", volume=0.8)
                else:
                    self.ctx.audio.play("driver/yawn", volume=0.8)
        self._accrue_microsleep(gm, moving, fatigue)

    def _update_lane(self, keys, dt: float) -> None:
        mode = self.ctx.settings.lane_keeping
        steer = 0.0
        if keys[pygame.K_LEFT]:
            steer -= 1.0
        if keys[pygame.K_RIGHT]:
            steer += 1.0
        # The left stick provides analog steering when the keys are idle.
        if steer == 0.0:
            pad = self.ctx.controller
            if pad.active and pad.steering:
                steer = pad.steering
        self.lane.steering = steer
        # The exit ramp is a single lane; the mainline keeps its leg count.
        self._lane_before_narrow = self.lane.lane
        self.lane.set_lane_count(1 if self._ramp_mi is not None else self._lane_count_here())
        # A narrowing road renumbers the lanes under the truck, so this has to
        # run the moment the count changes and before anything polices where
        # the truck is.
        self._leave_a_lane_the_road_closed()
        # Use the real baked curve data when the truck is inside a curve.
        # The curve force pushes the lane offset outward proportionally to
        # how much the truck's speed exceeds the advisory speed, scaled by
        # load, grip, and the curve's tightness.
        active = self.trip.curve_at(self.trip.position_mi)
        if active is not None and not active.connector:
            excess = max(0.0, self.truck.speed_mph - active.advisory_mph)
            tightness = max(0.2, 1.0 - active.min_radius_ft / 5000.0)
            # Curve push severity: around 1.0 at advisory in a tight bend,
            # ramping with excess speed. A heavier load pushes harder (more
            # inertia to pull wide); worn or icy grip means less resistance.
            load = min(1.5, self.truck.gross_mass_kg / self.truck.specs.mass_kg)
            grip_factor = min(1.0, self.truck.effective_grip)
            # Raw severity only: the lane model applies CURVE_RATE itself.
            # Scaling here too made every bend ~8x weaker than designed --
            # a 30-advisory curve at 45 could be no-hands (owner-caught on
            # Camp Verde-Payson: "didn't hear or have to turn").
            curve_push = tightness * (1.0 + excess * 0.05) * load / max(0.2, grip_factor)
            # Centrifugal force pushes the truck OUTSIDE the curve: a left
            # curve pushes right (positive offset), a right curve pushes left
            # (negative offset). The lane model's positive offset = rightward.
            direction = 1.0 if active.direction == "L" else -1.0
            curve = curve_push * direction
            # Spoken slip warning: entering a curve well above advisory
            # pushes the truck toward the shoulder and the driver should
            # know why.
            if excess > 15 and not self._curve_slip_active:
                self._curve_slip_active = True
                self.ctx.say_event(
                    f"{self._pacenote_phrase(active)}: too fast, drifting to the outside.",
                    interrupt=True,
                    category=SpeechCategory.SAFETY,
                )
        else:
            curve = 0.0
        if self._ramp_mi is not None:
            curve += 0.35
        if active is None and self._curve_slip_active:
            self._curve_slip_active = False
        self._update_curve_run(active)
        # Curve speed assist: use the real advisory speed when one is active
        # instead of the old terrain heuristic. Hysteresis both places:
        # engage above advisory + 5, but once slowing, hold until the truck
        # is within 2 of advisory. Deciding both ways at one threshold
        # flip-flopped against cruise seven times a second (playtest
        # 2026-07-22).
        curve_assisting = False
        excess_now = None
        if self.ctx.settings.curve_speed_assist:
            if active is not None and not active.connector:
                margin = 2 if self._curve_assist_active else 5
                curve_assisting = self.truck.speed_mph > active.advisory_mph + margin
                excess_now = max(0.0, self.truck.speed_mph - active.advisory_mph)
            elif curve != 0.0:
                # Fallback: old terrain- or ramp-based heuristic
                heuristic = 50 - abs(curve) * 20
                if self._curve_assist_active:
                    heuristic -= 3
                curve_assisting = self.truck.speed_mph > heuristic
        # The corner is the DRUMS' work, always. The retarder appears here
        # only when the road is going downhill, and then it is the grade it is
        # answering, not the bend. See the block below for the reasoning and
        # the sources; the short version is that a corner needs a precise
        # target speed, which is what service brakes are for, and a retarder
        # drives only the tractor's rear wheels, which is the last axle you
        # want retarding mid-bend.
        t = self.truck
        tr = t.transmission
        if curve_assisting and (
            not self._curve_assist_active
            # A yielded latch is still draining on the engage frame, so the
            # jake_capable check below sees throttle above its threshold and
            # the corner would never get its grade retarder. Retry while the
            # latch is the reason -- a HAND on the throttle still means the
            # driver is overriding, and for them this engages on the
            # transition frame only, exactly as before.
            or (self._latch_yielding and not self._curve_assist_jake)
        ):
            jake_capable = (
                t.engine_on
                and t.throttle < 0.05
                and not tr.in_neutral
                and not tr.shifting
                and tr.clutch <= 0.5
                and t.grip >= 0.55
                and t.rpm >= JAKE_MIN_RPM
            )
            # A real downgrade is the retarder's own job -- holding a loaded
            # truck back on a grade is the one use every noise ordinance
            # leaves legal -- so the overspeed line does not apply there.
            # _on_downgrade draws the same line the G readout and the
            # ordinance exemption already draw between level road and a
            # grade, and adaptive cruise now asks it too. Without this
            # carve-out the assist held a six percent descent on the drums
            # alone: past fade in four and a half minutes, 585 degrees at ten
            # (bench trace, 2026-08-11).
            downhill = self._on_downgrade()
            # A GRADE is the only thing that raises the retarder here. Slowing
            # FOR a corner is the service brakes' job, however much speed the
            # corner wants off -- owner ruling 2026-08-11, narrowing the
            # jake-first ruling of 2026-07-22 to grades only.
            #
            # The training material is unambiguous and it is not about noise.
            # The CDL manual's rule for a curve is to reach a safe speed
            # BEFORE entering it and then pull through on gentle throttle,
            # because braking mid-corner is what locks a wheel and jackknifes
            # a trailer -- and a retarder drives only the tractor's rear
            # wheels, which is precisely the axle you do not want retarding
            # through a bend. Jacobs, who build the thing, draw the same line:
            # the engine brake is for SUSTAINED speed control and is "not a
            # substitute for a service braking system", because it cannot give
            # the precise control the drums give. A corner is a precise target
            # speed. A descent is sustained control. Only the descent qualifies.
            #
            # A bend ON a grade still retards, because that is the grade's
            # doing, not the corner's -- and it has to: without this the assist
            # held a six percent descent on the drums alone and went past fade
            # in four and a half minutes, 585 degrees at ten (bench trace,
            # 2026-08-11).
            worth_the_bark = excess_now is not None and downhill
            # Town no-engine-brake zones close the jake to the assist as well
            # (real downgrades stay exempt); the service trim below answers.
            if (
                jake_capable
                and worth_the_bark
                and not t.engine_brake
                and self._assist_jake_allowed()
            ):
                # Stage one is a token two cylinders: past this line it would
                # bark without taking off the speed that called for it.
                t.engine_brake_stage = 3 if excess_now > CURVE_ASSIST_JAKE_FULL_MPH else 2
                self._curve_assist_jake = True
        elif not curve_assisting and self._curve_assist_jake:
            # Release only the jake WE engaged; the player's own selection
            # (or their mid-curve override) is never touched.
            if t.engine_brake:
                t.engine_brake_stage = 0
            self._curve_assist_jake = False
        jake_slowing = t.engine_brake and t.throttle < 0.05 and t.grip >= 0.55
        needs_service = not jake_slowing or (excess_now is not None and excess_now > 10)
        # The spoken cues get a cooldown on top: even a legitimate slow
        # cycle (cruise pulling back up to the engage line) must not chant.
        self._curve_assist_cue_s = max(0.0, self._curve_assist_cue_s - dt)
        if curve_assisting and needs_service:
            self.truck.brake = max(self.truck.brake, min(0.35, abs(curve)))
        if curve_assisting:
            if not self._curve_assist_active and self._curve_assist_cue_s <= 0.0:
                self._curve_assist_cue_s = CURVE_ASSIST_CUE_COOLDOWN_S
                self.ctx.say_event(
                    "Curve speed assistance slowing.",
                    interrupt=False,
                    category=SpeechCategory.CONFIRMATION,
                )
        elif self._curve_assist_active and self._curve_assist_cue_s <= 0.0:
            self._curve_assist_cue_s = CURVE_ASSIST_CUE_COOLDOWN_S
            self.ctx.say_event(
                "Curve speed assistance released.",
                interrupt=False,
                category=SpeechCategory.CONFIRMATION,
            )
        self._curve_assist_active = curve_assisting
        # Hysteresis on the ramp cap, for the same reason the curve assist has
        # it: decided both ways on the one threshold, a truck riding the ramp
        # limit announced itself slowing and released over and over down a
        # single ramp -- and re-made the brake application, and paid the air
        # for it, every time round (bench, 2026-08-11).
        ramp_hold_mph = RAMP_CRUISE_TARGET_MPH if self._transition_assist_active else RAMP_MAX_MPH
        transition_assisting = (
            self.ctx.settings.route_transition_assist
            and self._ramp_mi is not None
            and self.truck.speed_mph > ramp_hold_mph
        )
        if transition_assisting:
            self.truck.brake = max(self.truck.brake, 0.4)
            if not self._transition_assist_active:
                self.ctx.say_event(
                    "Route-transition assistance slowing.",
                    interrupt=False,
                    category=SpeechCategory.CONFIRMATION,
                )
        elif self._transition_assist_active:
            self.ctx.say_event(
                "Route-transition assistance released.",
                interrupt=False,
                category=SpeechCategory.CONFIRMATION,
            )
        self._transition_assist_active = transition_assisting
        wind = self.weather.effects.wind
        off_road_event = self.lane.update(
            dt, self.truck.velocity_mps, curve=curve, wind=wind, assist=mode
        )
        if off_road_event:
            if not self.ctx.settings.lane_departure_warning:
                return
            self.ctx.audio.play("vehicle/rumble_strip", volume=1.0, pan=self._lane_pan())
            self.truck.add_damage(1.0)
            self._announce_off_pavement()
        elif self._road_position_band is not None and not self._off_pavement():
            # Back on the pavement: the standing condition ended, so its one
            # transition line speaks and the band resets (research doc R12).
            self._road_position_band = None
            # review=True: STATUS goes SILENT at urgent_only, so this line
            # would otherwise reach no voice, no earcon, and (with the old
            # review=False here) no log either -- genuinely unreachable,
            # which breaks the ladder's own invariant that nothing it cuts
            # becomes invisible to the review keys.
            self.ctx.say_event(
                "Back on the pavement.",
                interrupt=False,
                review=True,
                category=SpeechCategory.STATUS,
            )
        self._cross_repeat_s = max(0.0, self._cross_repeat_s - dt)
        self._sideswipe_cooldown_s = max(0.0, self._sideswipe_cooldown_s - dt)
        if self.lane.crossed:
            self._on_lane_crossed()
        self._update_tap_lane_change(dt)
        self._update_merge(dt)
        self._update_keep_right(dt)

    def _update_tap_lane_change(self, dt: float) -> None:
        """Advance an assist-off tap change: signal clicks, then the flip."""
        if self._lane_change_target is None:
            return
        target = self._lane_change_target
        pan = -0.6 if target > self.lane.lane else 0.6
        self._lane_signal_timer += dt
        if self._lane_signal_timer >= LANE_SIGNAL_CLICK_S:
            self._lane_signal_timer = 0.0
            self.ctx.audio.play("vehicle/signal_tone", volume=0.8, pan=pan)
        self._lane_change_timer -= dt
        if self._lane_change_timer <= 0:
            self._lane_change_target = None
            target = min(target, self.lane.lane_count - 1)
            # Check the closure again on arrival, not just when the key was
            # pressed. A change takes seconds, and in those seconds the truck
            # can reach the cones or the road can narrow and renumber the
            # lanes -- either way the clamp above would otherwise land the
            # truck in the closed lane it was moving to avoid.
            if target == self._closed_lane_here():
                self.ctx.audio.play("ui/error")
                self.ctx.say_event(
                    f"The {lane_label(target, self.lane.lane_count)} lane is "
                    f"closed. Staying in the {self.lane.lane_name} lane.",
                    interrupt=True,
                    category=SpeechCategory.SAFETY,
                )
                return
            self.lane.lane = target
            # The tap change crosses the same painted line: same marker roll.
            self.ctx.audio.play(
                "vehicle/lane_line_cross",
                volume=min(1.0, 0.7 * self._cue_loudness()),
                pan=pan,
            )
            self._finish_lane_change()

    def _on_lane_crossed(self) -> None:
        """A held drift carried the truck across a line: the wheel was the
        lane change. The tires roll the line's raised markers every time --
        physics does not rate-limit -- but the signal tone and the spoken
        lane name mark a DELIBERATE change only. Pinballing back and forth
        across the same line mid-bend repeats just the quieter thump
        (owner: "the thing dings at you as you're going")."""
        repeat = self._cross_repeat_s > 0.0
        self._cross_repeat_s = LANE_CROSS_REPEAT_S
        pan = -0.6 if self.lane.crossed > 0 else 0.6
        self.ctx.audio.play(
            "vehicle/lane_line_cross",
            volume=min(1.0, (0.4 if repeat else 0.7) * self._cue_loudness()),
            pan=pan,
        )
        if not repeat:
            self.ctx.audio.play("vehicle/signal_tone", volume=0.6, pan=pan)
        self._finish_lane_change(quiet=repeat)

    def _finish_lane_change(self, quiet: bool = False) -> None:
        """The truck has just arrived in a new lane: check the space it moved
        into, resolve any dodgeable hazard, and reset keep-right pressure."""
        self._left_lane_s = 0.0
        self._keep_right_nags = 0
        lane = self.lane
        other = self.trip.traffic_manager.vehicle_in_lane(
            self.trip.position_mi,
            lane.lane,
            ahead_mi=DODGE_CLEARANCE_AHEAD_MI,
            behind_mi=DODGE_CLEARANCE_BEHIND_MI,
        )
        if other is not None and self.truck.speed_mph > LANE_MIN_MPH:
            if self._sideswipe_cooldown_s > 0.0:
                # One contact, not three. A truck pinballing across the same
                # painted line ran this branch on every crossing, so a single
                # sideswipe was billed and announced repeatedly inside half a
                # second (tester transcript, 2026-08-11). The damage and the
                # warning both belong to the contact, and it happened once.
                return
            self._sideswipe_cooldown_s = SIDESWIPE_REPEAT_S
            self.ctx.audio.play("vehicle/collision")
            self.ctx.controller.rumble.impact(SIDESWIPE_DAMAGE)
            self.truck.apply_collision(SIDESWIPE_DAMAGE)
            self.ctx.say_event(
                f"You sideswiped a {other.vehicle_class} in the {lane.lane_name} "
                f"lane! The truck took damage, now {self.truck.damage_pct:.0f} "
                "percent. Check your mirrors before moving over.",
                interrupt=True,
                category=SpeechCategory.SAFETY,
            )
            return
        if (
            self._hazard_deadline is not None
            and self._hazard_dodgeable
            and lane.lane != self._hazard_lane
        ):
            # The swerve answered it, so the assist's application comes off
            # with the hazard rather than being left on a truck now clear of
            # it. Terse mode's whole confirmation is the hazard-clear earcon
            # that just played; failure is the collision sound and its
            # spoken damage line, so the outcome pair is never ambiguous
            # (R4, R14).
            names = self._hazard_names_text()
            self._finish_hazard_clear(f"You swerve around {names}. Well done.")
            return
        if not quiet:
            self.ctx.say_event(
                f"In {lane_phrase(lane.lane, lane.lane_count)}.",
                interrupt=False,
                category=SpeechCategory.CONFIRMATION,
            )

    def _closed_lane_here(self) -> int | None:
        """The coned-off lane index in the truck's own lane numbering.

        Asked of the trip, which reads the closure's side against the lanes
        the road has here, and told the count the truck is actually steering
        in -- the exit ramp is one lane whatever the mainline carries. This
        is the only place the driving state learns which lane is shut, so no
        two checks can answer differently.
        """
        return self.trip.closed_lane_at(lane_count=self.lane.lane_count)

    def _open_lane_beside(self, closed: int) -> int | None:
        """The nearest lane the truck may legally be in, or None if there is
        no such lane."""
        count = self.lane.lane_count
        if count < 2:
            return None
        candidate = closed - 1 if closed > 0 else closed + 1
        if not 0 <= candidate < count or candidate == closed:
            return None
        return candidate

    def _leave_a_lane_the_road_closed(self) -> None:
        """Move the truck out of a closure it never drove into, and say so
        whenever the road itself -- closure or not -- just forced a move.

        The road, not the driver, can put a truck in coned-off lanes: where a
        stretch narrows, the lane count renumbers the lanes under the truck
        and the count clamp drops it a lane over, which can be the closed one.
        Shane's Detroit-Mansfield run is what that sounds like -- told the
        right lane was closed, moved left, and then put back in the closed
        lane with nothing to do about it. Whenever the road moves the truck
        into a closure it is moved straight back out and told so; only a lane
        the driver steered into is theirs to answer for.

        A narrowing stretch with no work zone at all used to say nothing --
        ``LaneKeeping.set_lane_count`` clamps the lane index silently, so a
        driver in the soon-to-vanish lane was simply moved with no warning
        (Darren, 2026-08-14). That gets the same never-dropped treatment as
        the closure call above, just without "closed": the road narrowed, not
        a work zone. Skipped on the exit ramp, whose own single-lane count and
        its own announcements are a different situation entirely.
        """
        count = self.lane.lane_count
        was = self._lane_count_seen
        self._lane_count_seen = count
        if was is None or was == count:
            return  # the road did not change under the truck
        closed = self._closed_lane_here()
        if closed is not None and self.lane.lane == closed:
            open_lane = self._open_lane_beside(closed)
            if open_lane is None:
                return
            open_name = lane_label(open_lane, count)
            self.lane.lane = open_lane
            self.lane.offset = 0.0
            self._lane_change_target = None
            self._merge_deadline = None
            self.ctx.audio.play(
                "vehicle/lane_line_cross", volume=min(1.0, 0.7 * self._cue_loudness())
            )
            self.ctx.say_event(
                f"The {lane_label(closed, count)} lane is closed where the road "
                f"narrows. You are in the {open_name} lane.",
                interrupt=True,
                category=SpeechCategory.SAFETY,
            )
            return
        before_lane = self._lane_before_narrow
        if (
            self._ramp_mi is None
            and before_lane is not None
            and before_lane >= count
            and before_lane != self.lane.lane
        ):
            self.ctx.audio.play(
                "vehicle/lane_line_cross", volume=min(1.0, 0.7 * self._cue_loudness())
            )
            # Naming the lane is only worth saying while there is another one
            # it could have been. Narrowing to one lane already said which
            # lane you are in by saying there is only one.
            moved = (
                "You are moved over."
                if count <= 1
                else f"You are moved to the {lane_label(self.lane.lane, count)} lane."
            )
            self.ctx.say_event(
                f"The road narrows to {_lane_count_words(count)}. {moved}",
                interrupt=True,
                category=SpeechCategory.SAFETY,
            )

    def _update_merge(self, dt: float) -> None:
        """Riding a coned-off lane: one urgent warning, then the barrels win."""
        zone = self.trip.active_closure()
        closed = self._closed_lane_here()
        if closed is None or self.lane.lane != closed or self.truck.speed_mph < LANE_MIN_MPH:
            self._merge_deadline = None
            return
        if self.lane.lane_count < 2:
            # Nowhere to merge to: the road under this closure runs one lane
            # our side. Zone placement will not do this any more, but a saved
            # trip or a stretch that narrows mid-zone still can, and ordering
            # a driver into a lane that does not exist -- then charging them
            # for staying put -- is the worst thing this code could do.
            self._merge_deadline = None
            return
        open_lane = self._open_lane_beside(closed)
        if open_lane is None:
            self._merge_deadline = None
            return
        open_name = lane_label(open_lane, self.lane.lane_count)
        if zone is not None and zone.reason != "construction":
            # Still in the taper: the lane is closing, not closed. Say so
            # once, and leave the barrel clock for the work zone itself.
            taper_key = f"{zone.reason}:{zone.start_mi:.2f}"
            if self._merge_taper_warned != taper_key:
                self._merge_taper_warned = taper_key
                self.ctx.audio.play("ui/warning")
                self.ctx.say_event(
                    f"The {lane_label(closed, self.lane.lane_count)} lane closes "
                    f"at the work zone ahead. Move to the {open_name} lane.",
                    interrupt=True,
                    category=SpeechCategory.SAFETY,
                )
            return
        if self._merge_deadline is None:
            self._merge_deadline = MERGE_WINDOW_S
            self.ctx.audio.play("ui/warning")
            self.ctx.controller.rumble.alert()
            self.ctx.say_event(
                f"You are in the closed {lane_label(closed, self.lane.lane_count)} "
                f"lane! Move to the {open_name} lane!",
                interrupt=True,
                category=SpeechCategory.SAFETY,
            )
            return
        if self._lane_change_target is not None and self._lane_change_target != closed:
            return  # already moving over: hold the countdown
        self._merge_deadline -= dt
        if self._merge_deadline <= 0:
            self._merge_deadline = None
            self.lane.lane = open_lane
            self.lane.offset = 0.0
            self._lane_change_target = None
            self.ctx.audio.play("vehicle/collision")
            self.ctx.controller.rumble.impact(MERGE_BARRELS_DAMAGE)
            self.truck.apply_collision(MERGE_BARRELS_DAMAGE)
            self.ctx.say_event(
                "You plowed through the barrels and lurched into the "
                f"{open_name} lane. The truck took damage, now "
                f"{self.truck.damage_pct:.0f} percent.",
                interrupt=True,
                category=SpeechCategory.SAFETY,
            )
            self._cite_barrel_strike(zone)

    def _cite_barrel_strike(self, zone) -> None:
        """Charge the citation for knocking down work zone barrels.

        Charged where the chain-law citation is, and for the same reason:
        this is written on the spot, mid-drive, and asking a driver who has
        just taken a collision to also run a shoulder stop stacks two demands
        on one moment. The record entry is a serious violation, not just
        money -- the offense endangers the crew, not the truck.

        Charged once per work zone. The barrels can catch a truck several
        times over one closure (the tester's log has two strikes in eight
        seconds); that is one refusal to merge, so it is one citation. The
        damage still lands every time.
        """
        # An open lane is what makes this the driver's fault. A truck with
        # nowhere to merge cannot be charged for staying where it is -- the
        # merge update returns long before here in that case, and this second
        # reading is deliberate: no future edit above may make this reachable.
        if self.lane.lane_count < 2 or self._enforcement_bypassed():
            return
        key = f"barrels:{round(zone.start_mi, 1)}"
        if key in self.enforcement_events:
            return
        self.enforcement_events.add(key)
        p = self.ctx.profile
        if p is None:
            return
        # NOT doubled for the construction zone, unlike every other citation.
        # The zone multiplier exists because states double an ordinary moving
        # violation committed in roadwork. This offense only exists inside
        # roadwork, and its base is Missouri RSMo 304.585, which is already the
        # work-zone-specific penalty and caps a first offense at 1,000. Passing
        # construction_zone=True here would charge twice for the same
        # aggravating fact and put every first offense at double the statutory
        # maximum. Priors still escalate it.
        fine = citation_fine(WORK_ZONE_BARRELS_FINE, career_citations(p))
        p.money -= fine
        self.ticket_fines_paid += fine
        post = self.trip.active_post_at(self.trip.position_mi)
        saw_it = (
            f"A trooper working this {post.reason} saw it"
            if post is not None
            else "The work crew called it in"
        )
        ladder = _log_enforcement(self.ctx, self, fine=fine, serious=True)
        self.ctx.audio.play("ui/error")
        self.ctx.say_event(
            # No doubled-for-the-zone clause: this citation is not doubled,
            # because its amount is already the roadwork penalty.
            f"{saw_it}. Driving through the barrels is a citation: "
            f"{fine:,.0f} dollars, and it goes on your safety record. "
            f"You have {p.money:,.0f} dollars." + (f" {ladder}" if ladder else ""),
            interrupt=False,
            # Money rides ROUTE's never-dropped contract: a busy stretch must
            # not age a citation out of the queue.
            priority=EventPriority.ROUTE,
            category=SpeechCategory.MONEY,
        )

    def _keep_right_justified(self) -> bool:
        """Left-lane time is legitimate while passing slower right-lane
        traffic, or while construction has the right lane coned off."""
        if self._closed_lane_here() == 0:
            return True
        slower = self.trip.traffic_manager.vehicle_in_lane(
            self.trip.position_mi,
            0,
            ahead_mi=PASSING_LOOKAHEAD_MI,
            behind_mi=0.05,
        )
        return slower is not None and slower.speed_mph < self.truck.speed_mph + 3.0

    def _update_keep_right(self, dt: float) -> None:
        """Camping the left lane draws CB grumbling: keep right except to pass."""
        lane = self.lane
        if (
            lane.lane_count < 2
            or lane.lane != lane.lane_count - 1
            or self.truck.speed_mph < KEEP_RIGHT_MIN_MPH
            or self._ramp_mi is not None
        ):
            self._left_lane_s = 0.0
            self._keep_right_nags = 0
            return
        if self._keep_right_justified():
            self._left_lane_s = max(0.0, self._left_lane_s - dt)
            return
        self._left_lane_s += dt
        threshold = KEEP_RIGHT_NAG_S + self._keep_right_nags * KEEP_RIGHT_REPEAT_S
        if self._left_lane_s < threshold:
            return
        self._keep_right_nags += 1
        if self._keep_right_nags == 1:
            self._speak_ambient_event(
                "CB chatter: you have been riding the left lane a while. "
                "Keep right except to pass.",
                "events/cb_radio_chatter",
            )
        else:
            self.ctx.audio.play("traffic/car_pass", volume=0.9, pan=0.5)
            self._speak_ambient_event(
                "Traffic is stacking up and passing you on the right. Move back to the right lane.",
                "events/cb_radio_chatter",
            )

    def _lane_pan(self) -> float:
        """Stereo pan for the rumble strip: it comes from the side you have
        drifted toward (negative left, positive right), so the side you hear it
        on is the side to steer away from."""
        return max(-1.0, min(1.0, self.lane.offset))

    def _off_pavement(self) -> bool:
        from ..sim.lane import OFF_ROAD

        return self.lane.edge_excursion() >= OFF_ROAD

    def _off_pavement_band(self) -> int:
        """A severity band that rises as the truck goes deeper off and faster,
        so the transition speech fires again when the condition worsens
        (research doc R12). Zero to two."""
        depth = 0 if self.lane.edge_excursion() < 1.4 else 1
        fast = 1 if self.truck.speed_mph >= 45.0 else 0
        return depth + fast

    def _announce_off_pavement(self) -> None:
        """Speak the off-pavement condition at its transitions only: on entry,
        and again when it worsens. A steady or easing band stays silent -- the
        panned edge-rumble loop carries where the truck is (research doc R12)."""
        band = self._off_pavement_band()
        previous = self._road_position_band
        if previous is not None and band <= previous:
            # Still off, no worse: track the band so a later worsening speaks,
            # but say nothing now.
            self._road_position_band = band
            return
        self._road_position_band = band
        boundary = self._edge_boundary()
        if boundary == "oncoming":
            # Past an undivided centerline is not a shoulder: say the
            # real danger, on the side it lives.
            message = "Across the centerline, in the oncoming lane!"
        elif boundary == "median":
            message = "Off the pavement, into the median on the left!"
        else:
            message = self.lane.describe()
        if not self._terse_speech():
            message += " Steer back toward the lane center."
        # Position (the standing off-pavement condition) is STATUS; this
        # function only ever speaks on entry or worsening -- the transition
        # itself is the warning, so every line it emits is SAFETY.
        self.ctx.say_event(message, interrupt=True, category=SpeechCategory.SAFETY)

    def _edge_boundary(self) -> str:
        """What lies past the road edge the truck is drifting toward.

        The divided flag prefers the baked lane segment at the current mile,
        then the leg's carriageway-geometry flag (Track D2), then the
        classifier's honest inference (interstates are divided by
        definition; one lane per side means a centerline).
        """
        from ..sim.lane_guidance import classify_boundaries
        from ..sim.trip_models import _highway_class

        baked = self.trip.lanes_at()
        leg = self.trip.route.legs[self.trip.current_leg_index]
        divided = baked[1] if baked is not None else getattr(leg, "divided", None)
        left, right = classify_boundaries(
            self.lane.lane,
            self.lane.lane_count,
            divided=divided,
            interstate=_highway_class(getattr(leg, "highway", "")) == "interstate",
        )
        return left if self.lane.offset < 0 else right

    def _update_curve_run(self, active) -> None:
        """Close the loop the pacenote opens: a soft tick on the bend's side
        as the curve begins, and a spoken verdict once you are through --
        held your line, caught the edge, or through it hot. The windshield
        gives a sighted driver this for free; the co-driver owes it to ours
        (owner ask 2026-07-27: "nothing tells you that you made it through
        well"). Chained bends hold their verdict for the last link."""
        if active is not None and active.connector:
            active = None
        run = self._curve_run
        if active is not None:
            if run is None or run["curve"] is not active:
                limit, _ = self.trip.speed_limit_at(self.trip.position_mi)
                demanding = (
                    active.advisory_mph < limit and getattr(active, "severity", "") != "gentle"
                )
                touched = hot = False
                if run is not None:
                    # A chained link: carry what the earlier bends earned.
                    demanding = demanding or run["demanding"]
                    touched, hot = run["touched"], run["hot"]
                self._curve_run = run = {
                    "curve": active,
                    "demanding": demanding,
                    "touched": touched,
                    "hot": hot,
                }
                if demanding and self.ctx.settings.curve_callouts:
                    pan = -PACENOTE_CUE_PAN if active.direction == "L" else PACENOTE_CUE_PAN
                    self.ctx.audio.play(
                        "vehicle/curve_bink", volume=min(1.0, 0.65 * self._cue_loudness()), pan=pan
                    )
            if self.lane.rumble_level() > 0.0:
                run["touched"] = True
            if self.truck.speed_mph > run["curve"].advisory_mph + 15:
                run["hot"] = True
            return
        if run is None:
            return
        if self.trip.curve_ahead_mi(0.2) is not None:
            return  # linked "then right": the verdict waits for the last bend
        self._curve_run = None
        if not run["demanding"] or not self.ctx.settings.curve_callouts:
            return
        if self._terse_speech():
            self.ctx.audio.play("vehicle/lane_centered", volume=0.5, pan=0.0)
            return
        if run["touched"]:
            text = "Through the bend. You caught the edge."
        elif run["hot"]:
            text = "Through the bend, hot."
        elif self.ctx.settings.lane_is_manual():
            text = "Through the bend, held your line."
        else:
            text = "Through the bend."
        self.ctx.say_event(text, interrupt=False, category=SpeechCategory.CONFIRMATION)

    def _lane_count_here(self) -> int:
        """Lanes on our side at this mile.

        One answer, kept on the trip, so the lane the truck steers in and the
        lane a work zone may cone off can never disagree -- two readings of
        the road is how a closure landed on a one-lane stretch.
        """
        return self.trip.lane_count_at()

    def _cue_loudness(self) -> float:
        from ..sim.lane_guidance import CUE_LOUDNESS

        return CUE_LOUDNESS.get(self.ctx.settings.lane_cue_loudness, 1.0)

    def _update_transverse_strips(self) -> None:
        """Fixed dead-man's-curve bars ahead of hairpins: cross them, hear
        them -- at any speed, in any assist mode, because they are cut into
        the road. Louder when faster, like the real hits."""
        from ..sim.lane_guidance import TRANSVERSE_KEY

        if self.truck.speed_mph < 2.0:
            return
        position = self.trip.position_mi
        for strip_mi in self._transverse_strip_miles:
            if strip_mi in self._transverse_fired or position < strip_mi:
                continue
            if position - strip_mi > 0.5:
                self._transverse_fired.add(strip_mi)  # resumed past it; stay quiet
                continue
            self._transverse_fired.add(strip_mi)
            volume = min(1.0, (0.65 + self.truck.speed_mph / 150.0) * self._cue_loudness())
            self.ctx.audio.play(TRANSVERSE_KEY, volume=volume, pan=0.0)
            self.ctx.controller.rumble.impact(0.5)

    def _update_lane_locator_audio(self, dt: float) -> None:
        """The I-key locator: a soft tock every beat, panned to where the
        truck sits in its lane. Player-summoned, so it keeps ticking until
        they shut it off or lane keeping takes the lane over."""
        if not self._lane_locator_on:
            return
        if self.ctx.settings.lane_is_automated() or self.truck.speed_mph < 2.0:
            return
        self._lane_locator_timer -= dt
        if self._lane_locator_timer > 0.0:
            return
        self._lane_locator_timer = 0.9
        pan = max(-1.0, min(1.0, self.lane.offset))
        self.ctx.audio.play(
            "vehicle/lane_locator", volume=min(1.0, 0.5 * self._cue_loudness()), pan=pan
        )

    def _exit_alignment_progress(self) -> float:
        """How far along the exit-lane position is, 0 to 1.

        Either route to ready counts, the same two the exit itself accepts:
        the commitment built by holding Right, and simply sitting far enough
        over. Whichever is further along is what the driver is hearing.
        """
        if self._exit_stop is None or not self._exit_signal_on:
            return 0.0
        if self.lane.lane != 0 and self._lane_change_target != 0:
            return 0.0  # ramps peel off the right lane; in-lane position cannot help
        return max(
            0.0,
            min(
                1.0,
                max(
                    self._exit_lane_alignment / EXIT_LANE_READY,
                    self.lane.offset / EXIT_LANE_OFFSET_READY,
                ),
            ),
        )

    def _steering_lane_cue_armed(self, dt: float) -> bool:
        """Is a lane move underway that the driver should hear their position for?

        Two ways in. Holding a steering direction for ``STEER_CUE_ARM_S`` is a
        move rather than a drift correction, and lasts as long as the wheel is
        held. An armed exit takes the cue over for the whole line-up: it runs
        from the moment the driver starts moving over until the exit lane is
        set, so the wheel coming back afterwards cannot re-arm it.
        """
        if self.lane.steering != 0.0:
            self._steer_cue_hold_s += dt
        else:
            self._steer_cue_hold_s = 0.0
        if self._lane_locator_on:
            return False  # the driver already has this tock running; one is enough
        if self.ctx.settings.lane_is_automated():
            return False  # the truck holds the lane and takes the exit itself
        if self.truck.speed_mph < STEER_CUE_MIN_MPH:
            return False
        steered = self._steer_cue_hold_s >= STEER_CUE_ARM_S
        if self._exit_stop is not None and self._exit_signal_on and self._ramp_mi is None:
            if self._exit_lane_ready():
                return False
            return steered or self._exit_lane_alignment > 0.0
        return steered

    def _update_steering_lane_cue(self, dt: float) -> None:
        """Hear where you are in the lane while you steer across it.

        The lane locator answers "where am I" on demand. This answers it for
        the length of a move being made right now, with no key to remember:
        the same panned tock, keeping time from the moment the wheel goes
        over until the move is done. Taking an exit with the lane work yours
        means holding a position at the right of the lane, and that position
        was the one thing on the road a blind driver could not hear (owner,
        2026-08-15).

        The beat closes up as the exit-lane position fills, then stops dead
        and the signal cancels the instant the position is good -- a turn
        signal clicking off as the wheel comes back. The quickening says
        "nearly", the click says "set", and neither is a sentence.
        """
        audio = self.ctx.audio
        if not self._steering_lane_cue_armed(dt):
            if not self._steer_cue_active:
                return
            self._steer_cue_active = False
            self._steer_cue_timer = 0.0
            # Click off only if we still held the frame a moment ago. A menu
            # over the drive lets the latch lapse on the audio clock, and the
            # move ends in silence rather than a signal cancelling at the
            # pause screen -- the dead man's switch, same as a held alert.
            if audio.cue_held(STEER_CUE_HOLD):
                audio.release_cue(STEER_CUE_HOLD)
                audio.play(
                    "vehicle/signal_tone",
                    volume=min(1.0, STEER_CUE_CANCEL_VOL * self._cue_loudness()),
                    pan=0.0,  # centred and quieter: the signal off, not the signal on
                )
            return
        audio.hold_cue(STEER_CUE_HOLD)
        if not self._steer_cue_active:
            self._steer_cue_active = True
            self._steer_cue_timer = 0.0  # first tock lands on the frame the move starts
        self._steer_cue_timer -= dt
        if self._steer_cue_timer > 0.0:
            return
        span = STEER_CUE_TOCK_S - STEER_CUE_TOCK_FAST_S
        self._steer_cue_timer = STEER_CUE_TOCK_S - span * self._exit_alignment_progress()
        audio.play(
            "vehicle/lane_locator",
            volume=min(1.0, 0.5 * self._cue_loudness()),
            pan=max(-1.0, min(1.0, self.lane.offset)),
        )

    def _update_edge_ladder_audio(self, audio) -> None:
        """Run the edge-boundary ladder: structural loops, not louder beeps.

        Clipping the strip is intermittent, fully on it is periodic, off the
        pavement is aperiodic gravel -- states a driver can tell apart under
        engine noise. Panned to the drift side. Past an undivided centerline
        the strip stays the outermost texture (there is no gravel out there;
        the spoken warning carries the oncoming danger)."""
        from ..sim.lane_guidance import edge_rung

        if self.ctx.settings.lane_is_automated() or self.truck.speed_mph < 2.0:
            rung = None  # tires that are not rolling make no groove noise
        else:
            rung = edge_rung(
                self.lane.edge_excursion(),
                boundary=self._edge_boundary(),
                loudness=self._cue_loudness(),
            )
        if rung is None:
            if self._edge_loop_key is not None:
                audio.stop_loop(CH_EDGE, fade_ms=150)
                self._edge_loop_key = None
            return
        key, volume = rung
        audio.start_loop(CH_EDGE, key, volume=volume, fade_ms=120)
        audio.set_loop_volume(CH_EDGE, volume)
        audio.set_loop_pan(CH_EDGE, self._lane_pan())
        self._edge_loop_key = key

    def _curve_steer_demand(self) -> float:
        """Signed steer the active bend asks for, -1 full left .. 1 full right.

        Direction leads into the curve (a left bend wants left); magnitude
        follows the same tightness/overspeed shape the curve push uses, so
        the guide leans harder exactly when the bend pulls harder."""
        active = self.trip.curve_at(self.trip.position_mi)
        if active is None or active.connector:
            # Ramp connectors and street maneuvers carry no mainline curve
            # record, and returning 0.0 here left the panned road bed dead
            # centre through every exit and every turn. The maneuver demand
            # keeps the guide leaning (see driving_turns.py).
            return self._maneuver_steer_demand(active)
        tightness = max(0.2, 1.0 - active.min_radius_ft / 5000.0)
        excess = max(0.0, self.truck.speed_mph - active.advisory_mph)
        magnitude = min(1.0, tightness * (1.0 + excess * 0.04))
        return -magnitude if active.direction == "L" else magnitude

    def _update_lane_guidance_audio(self, dt: float) -> None:
        """Run the guidance director: the road bed leans toward where the
        wheel should go (pursuit guide -- follow the sound), wakes for drift
        or a bend, and slews home on the centered straight. Never a new
        tone: the community ruling keeps the guide on the existing bed."""
        from ..sim.lane_guidance import CURVE_LEAD_MI

        if not self.ctx.settings.lane_departure_warning:
            frame = self.lane_guidance.update(
                self.lane, dt, assist_on=False, curve_steer=0.0, curve_ahead_mi=None
            )
        else:
            frame = self.lane_guidance.update(
                self.lane,
                dt,
                assist_on=(
                    self.ctx.settings.lane_is_manual() and self.truck.speed_mph >= LANE_MIN_MPH
                ),
                curve_steer=self._curve_steer_demand(),
                curve_ahead_mi=self.trip.curve_ahead_mi(CURVE_LEAD_MI),
            )
        if self.ctx.settings.lane_guide_tone:
            self._lean_the_tone(frame)
        elif frame.pan != self._road_pan_applied:
            self.ctx.audio.set_loop_pan(CH_ROAD, frame.pan)
            self._road_pan_applied = frame.pan
        if frame.centered:
            # The drift settled: the old centered earcon still says so.
            self.ctx.audio.play("vehicle/lane_centered", volume=0.45, pan=0.0)

    # The asset is baked at Darren's -16 dBFS RMS, which is 2.6 dB over the
    # engine. That is the level that fixed being inaudible, and it is louder
    # than a cue needs to be once it is the only thing carrying the pan, so
    # the channel takes it back down and the loudness setting scales from
    # there like every other lane cue.
    LANE_GUIDE_TONE_VOLUME = 0.35

    def _lean_the_tone(self, frame) -> None:
        """The opt-in alternative: lean a tone of the guide's own.

        Same frame, same pan, same wake and sleep -- only the thing being
        panned differs. The bed is left flat while the tone is in use, or a
        driver who switched would get both leaning at once and the bed would
        stay wherever the last drift left it.

        Silence is still centered: the loop starts on the wake and stops on
        the settle, so a straight road is as quiet as it has always been.
        That is what keeps this inside the community ruling rather than
        merely beside it -- the objection was to a CONTINUOUS tone, and this
        one only exists while the truck is actually off center.
        """
        if self._road_pan_applied != 0.0:
            self.ctx.audio.set_loop_pan(CH_ROAD, 0.0)
            self._road_pan_applied = 0.0
        if frame.awake:
            if not self._lane_guide_tone_on:
                self.ctx.audio.start_loop(
                    CH_LANE_GUIDE,
                    LANE_GUIDE_TONE_KEY,
                    volume=LANE_GUIDE_TONE_VOLUME * self._cue_loudness(),
                    fade_ms=120,
                )
                self._lane_guide_tone_on = True
            if frame.pan != self._lane_guide_pan_applied:
                self.ctx.audio.set_loop_pan(CH_LANE_GUIDE, frame.pan)
                self._lane_guide_pan_applied = frame.pan
        elif self._lane_guide_tone_on:
            self.ctx.audio.stop_loop(CH_LANE_GUIDE, fade_ms=180)
            self._lane_guide_tone_on = False
            self._lane_guide_pan_applied = 0.0

    def _auto_jake_max_stage(self) -> int:
        """The highest stage the drive axle can hold right now (0..3).

        Per-stage retard scales linearly with cylinders, so the cap divides
        straight through the full-stage demand -- the same traction physics
        the pre-select gate uses, applied to stage selection.
        """
        t = self.truck
        stage_backup = t.engine_brake_stage
        t.engine_brake_stage = JAKE_STAGES
        full_demand = t._jake_force_demand()
        t.engine_brake_stage = stage_backup
        if full_demand <= 0.0:
            return JAKE_STAGES
        cap = t._jake_traction_cap()
        return max(0, min(JAKE_STAGES, int(JAKE_STAGES * cap / full_demand)))

    def _update_auto_jake(self, dt: float) -> None:
        """AMT retarder management: hold the target by stepping the stage."""
        t = self.truck
        if not (self._auto_jake and t.engine_brake and t.transmission.automatic and t.engine_on):
            return
        if t.throttle > 0.05:
            return  # a throttle blip cuts the retarder; hold the stage for the return
        target = self._auto_jake_hold_mph or t.speed_mph
        if self._descent_control_active and self._cruise_mph is not None:
            target = self._cruise_mph  # descent control owns the number
        self._auto_jake_cooldown_s = max(0.0, self._auto_jake_cooldown_s - dt)
        max_stage = self._auto_jake_max_stage()
        stage = t.engine_brake_stage
        desired = stage
        err = t.speed_mph - target
        if err > AUTO_JAKE_OVER_MPH:
            desired = stage + 1
        elif err < -AUTO_JAKE_UNDER_MPH:
            desired = stage - 1
        desired = max(1, min(desired, max_stage if max_stage >= 1 else 1, JAKE_STAGES))
        if desired != stage and self._auto_jake_cooldown_s <= 0.0:
            t.engine_brake_stage = desired
            self._auto_jake_cooldown_s = AUTO_JAKE_STEP_S
        elif stage > max_stage >= 1 and self._auto_jake_cooldown_s <= 0.0:
            # Traction shrank under the current stage (ice arrived): step
            # down immediately rather than grinding the drives loose.
            t.engine_brake_stage = max_stage
            self._auto_jake_cooldown_s = AUTO_JAKE_STEP_S

    def _update_audio(self, dt: float = 0.0) -> None:
        t = self.truck
        audio = self.ctx.audio
        self._sync_radio_power()
        if t.engine_on and not audio.engine_running:
            # Catch-up sync (resuming a running-engine trip, returning from a
            # menu): bring the loop up without replaying the ignition crank.
            audio.engine_start(play_start_sound=False)
        elif not t.engine_on and audio.engine_running:
            # The mirror sync: the engine went off outside this frame loop
            # (a rest-menu shutdown), so drop the loop without a second
            # shutdown clunk. Without this the loop plays on with the engine
            # off -- inaudible under the old RPM-weighted band volumes, but
            # plainly audible with the constant-volume BASS engine loop.
            audio.engine_stop(shutdown_sound=False)
        # A shift briefly unloads the engine, but the old 0.08 clamp cut loop
        # gain by roughly forty percent and made repeated shifts sound like the
        # engine was ducking or nearly dropping out. Cap the load to a
        # perceptible torque easing while shifting, then -- once the shift ends
        # -- ease the cap back to full over SHIFT_LOAD_RECOVERY_S along the
        # recovery curve, so the return "under load" is a shaped glide rather
        # than a single-frame snap.
        # A real shift is kachunk -- sigh -- kachunk: never a LOADED
        # glissando sliding through the change (the meow), but never a
        # frozen hang either (the owner's 2026-07-24 catch: the voice used
        # to hold the pre-shift rpm for the whole interrupt, then cliff).
        # Automatic: the voice follows the live physics rpm, which eases
        # unloaded toward the new gear's road speed -- ducked to 0.35 the
        # whole way, it reads as the real between-gears fall -- and the
        # engagement plays its own soft clunk as the load swells back.
        # Manual: the player owns the revs while the clutch is out (blips
        # and rev-matching stay audible, and the physics already sinks
        # toward idle), so only the load ducks -- the engine falls back
        # unloaded and swells back in when the clutch hooks up.
        manual_clutch_out = not t.transmission.automatic and t.transmission.clutch > 0.5
        if (t.transmission.automatic and t.transmission.shifting) or manual_clutch_out:
            self._shift_recover_t = 0.0
            cap = SHIFT_LOAD_CAP
            duck = SHIFT_DISENGAGE_DUCK
            if t.transmission.automatic:
                # Marker only: an auto shift is in flight. The voice follows
                # the live physics rpm, which already sighs down toward the
                # new gear's road speed through the interrupt (vehicle
                # _update_rpm) -- ducked and unloaded, it reads as the real
                # between-gears fall, not the old frozen hang (owner,
                # 2026-07-24).
                self._shift_hold_rpm = t.rpm
        elif self._shift_recover_t < 1.0:
            step = dt / SHIFT_LOAD_RECOVERY_S if SHIFT_LOAD_RECOVERY_S > 0 else 1.0
            self._shift_recover_t = min(1.0, self._shift_recover_t + step)
            recovered = _shift_recovery_curve(self._shift_recover_t)
            cap = SHIFT_LOAD_CAP + (1.0 - SHIFT_LOAD_CAP) * recovered
            duck = SHIFT_DISENGAGE_DUCK + (1.0 - SHIFT_DISENGAGE_DUCK) * recovered
            if self._shift_hold_rpm is not None:
                # Engagement: the gear takes. The interrupt's clunk played a
                # second ago at shift START, so without this the actual
                # moment the truck picks the load back up was silent.
                audio.play_bank(
                    "vehicle/shift_auto", "vehicle/gear_shift", volume=SHIFT_END_CLUNK_VOLUME
                )
                self._shift_hold_rpm = None
        else:
            cap = 1.0
            duck = 1.0
            self._shift_hold_rpm = None
        audio.set_engine_duck(duck)
        target_load = max(0.0, min(1.0, t.throttle))
        if dt <= 0.0:
            # Direct callers and tests use a zero-length update to request an
            # immediate audio sync.
            self._engine_audio_throttle = target_load
        else:
            blend = min(1.0, dt / ENGINE_LOAD_SMOOTH_S)
            self._engine_audio_throttle += (target_load - self._engine_audio_throttle) * blend
        engine_load = min(self._engine_audio_throttle, cap)
        audio.set_engine_rpm(t.rpm, engine_load)
        audio.set_road_noise(t.velocity_mps)

        # Road texture follows real wheel travel, not the trip model's compressed
        # route distance. Ramps are outside the highway soundscape.
        if dt > 0.0 and t.velocity_mps > 5.0 and not self.trip.on_ramp:
            self._road_joint_accumulator_m += t.velocity_mps * dt
            if self._road_joint_accumulator_m >= self._next_joint_distance_m:
                self._road_joint_accumulator_m %= self._next_joint_distance_m
                self._next_joint_distance_m = self._road_texture_rng.uniform(14.0, 18.0)

                vol = 0.015 * min(1.0, t.velocity_mps / 30.0)
                audio.play("vehicle/road_joint", volume=vol)
                self.ctx.controller.rumble.joint(min(1.0, t.velocity_mps / 30.0))

        if t.engine_on and t.transmission.in_reverse:
            if not self._reverse_cue_active:
                audio.reverse_start()
                self._reverse_cue_active = True
        elif self._reverse_cue_active:
            audio.reverse_stop()
            self._reverse_cue_active = False
        # Air-fill overlay: the compressor charging the tanks below governor
        # release, whatever idle or drive state plays over it. Ends -- with the
        # fast idle settling -- at the park_idle -> ready_idle flip. Hysteresis
        # (AIR_FILL_REARM_PSI) keeps routine brake dips just under the 100 psi
        # line from fluttering the hiss; a genuine low-air build still plays.
        voice = engine_audio.classify(engine_audio.reading_from_truck(t))
        deep_fill = t.air_pressure_psi <= t.specs.air_parking_release_psi - AIR_FILL_REARM_PSI
        if t.engine_on and voice.pressurizing and (self._air_cue_active or deep_fill):
            # The compressor spins with the engine: the fill hiss waits out
            # the ignition crank and starts once the engine is actually
            # running at idle, not the instant E is pressed.
            if not self._air_cue_active and not audio.engine_starting:
                audio.start_loop(
                    CH_AIR, "vehicle/air_pressurize", volume=AIR_FILL_VOLUME, fade_ms=400
                )
                self._air_cue_active = True
        elif self._air_cue_active:
            audio.stop_loop(CH_AIR, fade_ms=700)
            self._air_cue_active = False
        # The jake's growl: only while it genuinely retards -- engine on, off
        # throttle, coupled, rolling, revs up -- and never through a shift or
        # a pressed clutch (the real jake cuts out and resumes higher).
        tr = t.transmission
        jake_active = (
            t.engine_on
            and t.engine_brake
            and t.throttle < 0.05
            and not tr.in_neutral
            and not tr.shifting
            and tr.clutch <= 0.5
            and abs(t.velocity_mps) > 3.0
            and t.rpm >= JAKE_MIN_RPM
        )
        if jake_active:
            nearest = min(JAKE_LOOP_RPMS, key=lambda band: abs(band - t.rpm))
            stage = max(1, min(len(JAKE_STAGE_GAIN), t.engine_brake_stage))
            rpm_span = max(1.0, 2200.0 - JAKE_MIN_RPM)
            growth = 0.5 + 0.5 * min(1.0, (t.rpm - JAKE_MIN_RPM) / rpm_span)
            volume = JAKE_STAGE_GAIN[stage - 1] * growth
            key = f"engine/jake_{nearest}"
            # Compare what will really SOUND, not the band we asked for. On
            # the classic voice every band maps to one synth cut, so caching
            # the band key restarted that same file over itself every time
            # rpm crossed a boundary -- which on a grade is constantly.
            sounding = audio.voice_key(key)
            if sounding != self._jake_cue_key:
                audio.start_loop(CH_JAKE, key, volume=volume, fade_ms=120)
                self._jake_cue_key = sounding
            else:
                audio.set_loop_volume(CH_JAKE, volume)
        elif self._jake_cue_key is not None:
            audio.stop_loop(CH_JAKE, fade_ms=150)
            self._jake_cue_key = None
        # The cold-start low-air buzzer waits out the ignition crank so the
        # start itself stays audible; if the compressor has already built past
        # the warning line by handoff, there is nothing left to warn about.
        if self._pending_low_air_buzzer and not audio.engine_starting:
            self._pending_low_air_buzzer = False
            if t.engine_on and t.air_low_warning:
                audio.play("vehicle/low_air_buzzer", volume=0.55)
        eff = self.weather.effects
        audio.set_weather(eff.sound)
        audio.set_wind(eff.wind)
        self._update_lane_guidance_audio(dt)
        rumble = self.lane.rumble_level()
        self._update_edge_ladder_audio(audio)
        self._update_transverse_strips()
        self._update_lane_locator_audio(dt)
        # After the locator, which owns the tock whenever the driver asked for
        # it, and after _update_exit_preparation has settled this frame's
        # alignment -- so the click lands on the frame the exit lane is set.
        self._update_steering_lane_cue(dt)
        if rumble > 0.0 and self.ctx.settings.lane_is_manual():
            # Harsh, continuous pad buzz while over the rumble strip; refreshed
            # each frame, it stops on its own once steered back off.
            self.ctx.controller.rumble.rumble_strip(rumble)
        night = is_night(self.trip.local_hour)
        if night:
            audio.set_ambient("ambient/night")
        else:
            audio.set_ambient(None)
        if self.radio.enabled and self.truck.engine_on:
            self._update_radio_reception(dt)
            self._update_radio_playback(night, dt)
            self._update_radio_fringe(dt)
        else:
            self._stop_radio_fringe()
        if self.weather.should_thunder():
            audio.play("weather/thunder")

    # -- radio reception and station rotation --------------------------------------

    def tick_covered_music(self, dt: float) -> None:
        """Keep the radio spinning while a menu covers the drive.

        A paused rig is still a cab with the radio on: the station keeps
        rotating songs and host breaks under the pause menu instead of going
        silent when the current bed runs out. Day/night flavor stays as it
        was when the menu opened; it catches up when driving resumes."""
        self._sync_radio_power()  # a rest-menu shutdown kills the radio too
        if self.radio.enabled and self.truck.engine_on:
            self._update_radio_playback(self._music_night, dt)

    def _update_radio_reception(self, dt: float) -> None:
        """Fade ranged stations with distance and retune when they drop out."""
        self._radio_signal_timer -= max(0.0, dt)
        if self._radio_signal_timer > 0.0:
            return
        self._radio_signal_timer = 1.5
        before = self.radio.current_station()
        self.radio.update_position(
            truck_position(self.route, self.trip.position_mi, self.ctx.world),
            truck_elevation_ft(self.route, self.trip.position_mi),
        )
        reception = self.radio.current_reception()
        if reception.station.id != before.id:
            # the tuned station fell past its range contour mid-drive
            self.ctx.award_achievement("radio_faded_out", event=True)
            self._radio_states_held.clear()
            self.ctx.audio.play("radio/static_burst", volume=0.5)
            action = self.radio.select_station(SAFE_ROUTE_PLAYLIST, self._radio_backend)
            # The dead station's fringe must die with it: without this the
            # cached signal keeps the hiss bed and pickets crackling over
            # the fallback -- and its picket duck holding the volume down --
            # until the next reception tick.
            self._radio_fringe_signal = None
            self._stop_radio_fringe()
            self.radio.write_settings(self.ctx.settings)
            self.ctx.settings.save()
            self.ctx.say_event(
                f"{before.display_name} faded out of range. "
                f"Falling back to {action.station.display_name}.",
                interrupt=False,
                category=SpeechCategory.STATUS,
            )
            return
        self._radio_signal_factor = signal_volume_factor(reception)
        self._track_radio_badges(reception)
        self._apply_radio_volume()
        if reception.station.real_stream and not self.ctx.audio.music_playing():
            # A dead stream is a silent radio, not a fringe one -- no program,
            # so no crackle. Dock and menu beds borrow the music channel and
            # nothing restarts the stream afterward (a network stall ends the
            # same way), so quietly re-tune it here; if the station is truly
            # unreachable the radio's own fallback machinery speaks the switch.
            self._radio_reconnect_timer -= 1.5
            if self._radio_reconnect_timer <= 0.0:
                self._radio_reconnect_timer = 9.0
                action = self.radio.play(self._radio_backend)
                if action.fallback_used:
                    self.radio.write_settings(self.ctx.settings)
                    self.ctx.settings.save()
                    self.ctx.say_event(
                        action.message, interrupt=False, category=SpeechCategory.STATUS
                    )
            self._radio_fringe_signal = None
            return
        self._radio_reconnect_timer = 0.0
        # Cache what the per-frame fringe renderer needs: thinning signal and
        # the dial frequency (for the picket flutter rate). Satellite and
        # built-in stations have no fringe.
        signal = reception.signal
        if signal > 0.0 and not reception.station.always_available:
            self._radio_fringe_signal = signal
            self._radio_fringe_freq = reception.station.frequency_mhz
        else:
            self._radio_fringe_signal = None

    # -- FM fringe: hiss bed + picket-fence flutter ---------------------------
    #
    # The hiss bed creeps in below full quieting and deepens with distance;
    # pickets are sharp splashes of noise punching through the program (FM
    # capture is a threshold, so the gating is abrupt -- owner ruling
    # 2026-07-23). Their arrival is exponential around the physical Rayleigh
    # rate 2v/lambda, never metronomic: a fixed 18 Hz tremolo sounds like a
    # helicopter, not a fringe FM signal.

    def _update_radio_fringe(self, dt: float) -> None:
        audio = self.ctx.audio
        signal = self._radio_fringe_signal
        if signal is None or not audio.music_playing():
            # No station, satellite/built-in, or a dead stream: a silent
            # radio has no fringe (the Merced ghost-hiss lesson).
            self._stop_radio_fringe()
            return
        depth = max(0.0, min(1.0, (FRINGE_BED_SIGNAL - signal) / FRINGE_BED_SIGNAL))
        if depth <= 0.0:
            self._stop_radio_fringe()
            return
        # start_loop dedupes on a running key, so this doubles as the volume
        # update AND self-heals after anything stopped the channel. The radio
        # knob scales the hiss along with the program it degrades.
        audio.start_loop(
            CH_RADIO_FX,
            "radio/fm_hiss_loop",
            volume=FRINGE_BED_MAX_VOLUME * depth * depth * self.ctx.settings.radio_volume,
            fade_ms=600,
        )
        self._fringe_bed_active = True
        if self._picket_duck_s > 0.0:
            self._picket_duck_s -= dt
            if self._picket_duck_s <= 0.0 and self._radio_picket_duck != 1.0:
                self._radio_picket_duck = 1.0
                self._apply_radio_volume()
        if signal >= PICKET_SIGNAL:
            return
        picket_depth = (PICKET_SIGNAL - signal) / PICKET_SIGNAL
        self._picket_wait_s -= dt
        if self._picket_wait_s > 0.0:
            return
        freq = self._radio_fringe_freq or FM_DEFAULT_MHZ
        wavelength_m = 299.792458 / freq
        rate = 2.0 * abs(self.truck.velocity_mps) / wavelength_m
        rate = min(PICKET_MAX_RATE_HZ, max(PICKET_MIN_RATE_HZ, rate))
        rate *= 0.3 + 0.7 * picket_depth
        self._picket_wait_s = self._fringe_rng.expovariate(rate)
        # Owner's ear 2026-07-24: pickets sit UNDER the program at shallow
        # fringe (they play on the hotter sfx bus, so numbers here run low)
        # and only rival it deep in the noise.
        audio.play_bank(
            "radio/picket",
            "radio/static_burst",
            volume=(0.15 + 0.35 * picket_depth) * self.ctx.settings.radio_volume,
        )
        # Honors Settings > Audio the same as every other duck in the game.
        # This one is arguably signal simulation rather than an accessibility
        # step-back -- a picket IS the program dipping under multipath fade --
        # but "do not step my audio back" is one behavior with one name, and a
        # player who turned it off did not mean "except for this". The burst
        # still plays at full level; it just no longer digs itself a hole.
        if self.ctx.settings.duck_audio_for_speech:
            self._radio_picket_duck = PICKET_DUCK
            self._picket_duck_s = 0.05 + 0.08 * self._fringe_rng.random()
            self._apply_radio_volume()

    def _stop_radio_fringe(self) -> None:
        if self._fringe_bed_active:
            self.ctx.audio.stop_loop(CH_RADIO_FX, fade_ms=400)
            self._fringe_bed_active = False
        if self._radio_picket_duck != 1.0:
            self._radio_picket_duck = 1.0
            self._picket_duck_s = 0.0
            self._apply_radio_volume()

    def _station_rotation_pool(self, station: RadioStation, night: bool) -> tuple[str, ...]:
        if station.playlist == "route":
            return self._night_music_sequence if night else self._day_music_sequence
        if station.playlist:
            return select_station_playlist(station.playlist, f"{self.trip_seed}|{station.id}")
        if station.track_key:
            return (station.track_key,)
        return ()

    def _start_station_rotation(self, station: RadioStation, fade_ms: int = 900) -> None:
        night = is_night(self.trip.current_hour)
        self._music_night = night
        self._radio_station_id = station.id
        self._radio_playlist = self._station_rotation_pool(station, night)
        self._radio_track_index = 0
        self._radio_elapsed_s = 0.0
        self._radio_break_queue: tuple[str, ...] = ()
        self._radio_break_pos = 0
        self._radio_break_count = 0
        self._radio_tracks_since_break = 0
        if self._radio_playlist:
            self.ctx.audio.play_music(self._radio_playlist[0], fade_ms=fade_ms)

    def _update_radio_playback(self, night: bool, dt: float) -> None:
        station = self.radio.current_station()
        if station.real_stream or station.fallback:
            return
        if station.source_type == PERSONAL_PLAYLIST_SOURCE_TYPE:
            self._update_playlist_playback(station, dt)
            return
        if not station.playlist and not station.track_key:
            return
        if station.id != self._radio_station_id or (
            station.playlist == "route" and night != self._music_night
        ):
            self._start_station_rotation(station, fade_ms=2500)
            return
        if not self._radio_playlist:
            return
        self._radio_elapsed_s += max(0.0, dt)
        if self._radio_break_queue:
            current = self._radio_break_queue[self._radio_break_pos]
        else:
            current = self._radio_playlist[self._radio_track_index % len(self._radio_playlist)]
        if self._radio_elapsed_s < content_duration_s(current):
            return
        self._radio_elapsed_s = 0.0
        if self._radio_break_queue:
            self._radio_break_pos += 1
            if self._radio_break_pos < len(self._radio_break_queue):
                self.ctx.audio.play_music(
                    self._radio_break_queue[self._radio_break_pos], fade_ms=300
                )
                return
            self._radio_break_queue = ()
            self._play_station_track(fade_ms=1200)
            return
        self._radio_track_index += 1
        self._radio_tracks_since_break += 1
        if self._radio_tracks_since_break >= RADIO_TRACKS_PER_HOST_BREAK:
            queue = plan_break(
                station.id,
                station.host,
                station.playlist,
                f"{self.trip_seed}|{station.id}",
                self._radio_break_count,
            )
            self._radio_tracks_since_break = 0
            if queue:
                self._radio_break_queue = queue
                self._radio_break_pos = 0
                self._radio_break_count += 1
                self.ctx.audio.play_music(queue[0], fade_ms=600)
                return
        self._play_station_track(fade_ms=2500)

    def _play_station_track(self, fade_ms: int) -> None:
        key = self._radio_playlist[self._radio_track_index % len(self._radio_playlist)]
        self.ctx.audio.play_music(key, fade_ms=fade_ms)

    def _start_playlist_station(self, station, fade_ms: int = 900, advance: bool = False) -> None:
        """Play a personal playlist station from its remembered position.

        A file entry plays off disk; a stream entry tunes the same live
        connection the curated real streams use. Entries that will not open
        are skipped at play time rather than pruned at load: a NAS that was
        asleep when the drive started should not erase the tracks behind it.
        Raises RadioPlaybackError only when nothing in the whole playlist
        opens, so the radio's existing fallback machinery speaks the failure
        the same way it does a dead stream."""
        entries = station.playlist_entries
        if not entries:
            raise RadioPlaybackError("playlist is empty")
        start = self._playlist_positions.get(station.id, 0)
        if advance:
            start = (start + 1) % len(entries)
        for attempt in range(len(entries)):
            index = (start + attempt) % len(entries)
            entry = entries[index]
            stream = is_stream_entry(entry)
            try:
                if stream:
                    self.ctx.audio.play_radio_stream(entry, fade_ms=fade_ms)
                else:
                    self.ctx.audio.play_music_file(entry, fade_ms=fade_ms)
            except RuntimeError:
                continue
            self._playlist_positions[station.id] = index
            self._radio_station_id = station.id
            self._radio_playlist = []
            self._radio_break_queue = ()
            # A file's fade-in window would read as "finished" to
            # music_playing on some backends, and a stream has not even
            # connected yet; either way, hold the advance check off.
            self._playlist_wait_s = PLAYLIST_CONNECT_HOLD_S if stream else PLAYLIST_FADE_HOLD_S
            self._playlist_stream_tries = 0
            return
        raise RadioPlaybackError("no playable entry in this playlist")

    def _playlist_entry(self, station) -> str:
        """The entry this playlist is sitting on right now."""
        entries = station.playlist_entries
        if not entries:
            return ""
        return entries[self._playlist_positions.get(station.id, 0) % len(entries)]

    def _update_playlist_playback(self, station, dt: float) -> None:
        """Advance a personal playlist when the current entry ends.

        A live stream never ends: it holds the dial until the driver tunes
        away or the connection dies. Since play_radio_stream connects on a
        worker thread, a silent music channel right after tuning means
        "still connecting", never "finished" -- so a stream entry gets a
        connect hold and a re-tune before it is written off."""
        if station.id != self._radio_station_id:
            self._playlist_wait_s = 0.0
            self._playlist_stream_skips = 0
            try:
                self._start_playlist_station(station, fade_ms=2500)
            except RadioPlaybackError:
                self._playlist_nothing_plays(station)
                self._radio_station_id = station.id
            return
        self._playlist_wait_s = max(0.0, self._playlist_wait_s - max(0.0, dt))
        if self._playlist_wait_s > 0.0:
            return
        if self.ctx.audio.music_playing():
            self._playlist_stream_tries = 0
            self._playlist_stream_skips = 0
            self._playlist_silence_spoken.discard(station.id)
            return
        entry = self._playlist_entry(station)
        if is_stream_entry(entry) and self._playlist_stream_tries < PLAYLIST_CONNECT_TRIES:
            # Re-tune the same URL: one still connecting is a no-op, and one
            # whose connect already failed raises here -- which is exactly
            # when the entry gets skipped, the same as an unreadable file.
            self._playlist_stream_tries += 1
            try:
                self.ctx.audio.play_radio_stream(entry, fade_ms=600)
            except RuntimeError:
                pass
            else:
                self._playlist_wait_s = PLAYLIST_CONNECT_HOLD_S
                return
        try:
            self._start_playlist_station(station, fade_ms=1200, advance=True)
        except RadioPlaybackError:
            self._playlist_nothing_plays(station)
            return
        if is_stream_entry(self._playlist_entry(station)):
            # A stream cannot say up front whether it will play, so a
            # playlist of dead streams would otherwise cycle silently
            # forever. One lap of the entries with nothing ever heard is
            # the same answer as nothing opening at all.
            self._playlist_stream_skips += 1
            if self._playlist_stream_skips > len(station.playlist_entries):
                self._playlist_nothing_plays(station)
        else:
            self._playlist_stream_skips = 0

    def _playlist_nothing_plays(self, station) -> None:
        """Nothing in this playlist would play: say so once, then keep trying.

        Silence with no explanation is the bug this feature kept hitting.
        The line names the folder the player can go and fix, and it speaks
        once per station until something in it plays again -- a station that
        is simply between tracks says nothing at all."""
        self.ctx.audio.stop_music(600)
        self._playlist_wait_s = PLAYLIST_RETRY_S
        self._playlist_stream_tries = 0
        self._playlist_stream_skips = 0
        if station.id in self._playlist_silence_spoken:
            return
        self._playlist_silence_spoken.add(station.id)
        self.ctx.say_event(
            f"Nothing in {station.display_name} would play. "
            "Check the tracks in your Playlists folder.",
            interrupt=False,
            category=SpeechCategory.STATUS,
        )

    def _track_radio_badges(self, reception) -> None:
        """Badges for actually living on the dial rather than just switching it on.

        The catalog had nothing for the radio at all, which is a strange gap in
        a game with five hundred odd real stations and terrain-aware
        propagation: the interesting things a driver notices -- a signal held
        across three states, a station arriving from far outside its contour --
        went unremarked.
        """
        p = self.ctx.profile
        if p is None:
            return
        station = reception.station
        if add_unique_stat(p, "radio_stations_heard", station.id) >= 25:
            self.ctx.award_achievement("radio_dial_wanderer", event=True)
        # A genuine skip: audible past the station's flat contour, which only
        # height can do. Any station merely ridden into its own static must
        # not count -- that is Somewhere in the Static's territory, and this
        # badge used to pop on every ordinary fade-out drive. The flat
        # contour is effective_range_miles with no elevation term, i.e. the
        # reach-doubled contour (RADIO_REACH_MULT), not the raw published
        # range_miles.
        distance = reception.distance_miles
        if (
            distance is not None
            and station.range_miles > 0
            and distance >= effective_range_miles(station, None) * 1.1
        ):
            self.ctx.award_achievement("radio_fringe_catch", event=True)
        state = self.trip.state_at()
        if not state:
            return
        if self._radio_states_station != station.id:
            self._radio_states_station = station.id
            self._radio_states_held = {state}
            return
        self._radio_states_held.add(state)
        if len(self._radio_states_held) >= 3:
            self.ctx.award_achievement("radio_three_states", event=True)

    def _track_driving_badges(self, dt: float) -> None:
        """Badges for the driving itself: craft, and one or two bad ideas.

        Kept out of the physics so nothing here can change how the truck
        behaves -- these only ever read.
        """
        t = self.truck
        if self.ctx.profile is None or not t.engine_on:
            return
        speed = t.speed_mph
        # A mile held at exactly sixty-nine. It means nothing. It is also the
        # single most requested number in the history of odometers.
        if 68.5 <= speed <= 69.5:
            self._nice_speed_mi += speed * dt / 3600.0
            if self._nice_speed_mi >= 1.0:
                self.ctx.award_achievement("sixty_nine_mph", event=True)
        else:
            self._nice_speed_mi = 0.0
        if speed >= 88.0:
            self.ctx.award_achievement("eighty_eight_mph", event=True)
        if t.brake_temp_c >= t.brake_fade_onset_c:
            self.ctx.award_achievement("brake_smoke", event=True)
        # Two miles of real downgrade held on the engine alone. The service
        # brake touching at all resets it -- that is the whole point.
        if t.grade <= -0.04 and t.engine_brake and speed > 5.0:
            if t.brake > 0.01 or t.emergency_brake:
                self._jake_descent_mi = 0.0
            else:
                self._jake_descent_mi += speed * dt / 3600.0
                if self._jake_descent_mi >= 2.0:
                    self.ctx.award_achievement("jake_only_descent", event=True)
        elif t.grade > -0.02:
            self._jake_descent_mi = 0.0
        # Predictive cruise banking speed for a grade that would really have
        # taken it: the feature earning its keep, once, out loud.
        if (
            self._cruise_mph is not None
            and self._pcc_phase == "building"
            and self._grade_extremes_ahead()[0] >= 0.04
        ):
            self.ctx.award_achievement("predictive_crest", event=True)

    def _sync_radio_settings(self) -> None:
        station_before = self.radio.station_id
        self.radio.apply_settings(self.ctx.settings)
        self.radio.update_position(
            truck_position(self.route, self.trip.position_mi, self.ctx.world),
            truck_elevation_ft(self.route, self.trip.position_mi),
        )
        self.radio.current_station()
        if self.radio.station_id != station_before:
            self.radio.write_settings(self.ctx.settings)
            self.ctx.settings.save()

    def apply_radio_settings_now(self) -> None:
        """React to a radio settings flip while this drive owns the radio.

        Turning streamer-safe on is a promise about what is on the air
        right now. Before this, the playing stream was never stopped (the
        one thing the mode exists to do), the dial swapped to the SILENT
        fallback without a word, and flipping the mode back off left the
        radio parked on that silence. Now the station leaves the air the
        moment the row is toggled, the cab says so, and the radio lands on
        the Roadhouse like any other handover."""
        before = self.radio.current_station()
        self.radio.apply_settings(self.ctx.settings)
        if self.radio._station_allowed(before):
            return
        powered = self.radio.enabled and self.truck.engine_on
        action = self.radio.select_station(
            SAFE_ROUTE_PLAYLIST, self._radio_backend if powered else None
        )
        self.radio.write_settings(self.ctx.settings)
        self.ctx.settings.save()
        if powered:
            self.ctx.say_event(
                f"{before.display_name} left the dial: streamer-safe mode is on. "
                f"Tuned to {action.station.display_name}.",
                interrupt=False,
                category=SpeechCategory.STATUS,
            )

    def _apply_radio_volume(self) -> None:
        factor = getattr(self, "_radio_signal_factor", 1.0)
        duck = getattr(self, "_radio_picket_duck", 1.0)
        # A sibling of the picket duck, deliberately not the same field: the
        # picket duck self-heals on _stop_radio_fringe, which would drag an
        # enforcement duck away with it in the middle of a cue.
        duck *= getattr(self, "_radio_cue_duck", 1.0)
        self.ctx.audio.set_volumes(music=self.ctx.settings.radio_volume * factor * duck)

    def _play_radio_current(self) -> None:
        self._sync_radio_settings()
        # An explicit (re)start IS the power sync for this frame; without
        # this, resuming a running-engine trip would restart the song twice.
        self._radio_powered = self.truck.engine_on
        if self.radio.enabled and self.truck.engine_on:
            self._apply_radio_volume()
            self.radio.play(self._radio_backend)
        else:
            self.ctx.audio.stop_music(600)

    def _sync_radio_power(self) -> None:
        """The radio draws power from the engine.

        Every engine path funnels through here on the next frame -- the
        ignition key, a stall, a rest-menu shutdown -- so the radio falls
        silent with the engine and comes back on its own when the engine
        does (owner ruling, 2026-08-12: no radio in a dead cab, starting
        with the engine-off top of every load)."""
        powered = self.truck.engine_on
        if powered == self._radio_powered:
            return
        self._radio_powered = powered
        if not self.radio.enabled:
            return
        if powered:
            self._play_radio_current()
        else:
            self.ctx.audio.stop_music(600)
            self._stop_radio_fringe()

    def _finish_radio_action(self, action) -> None:
        self.radio.write_settings(self.ctx.settings)
        self.ctx.settings.save()
        self.ctx.say(action.message)

    def _radio_no_power(self) -> bool:
        """Speak the dead-cab line when a radio key lands with no engine."""
        if self.truck.engine_on:
            return False
        self.ctx.audio.play("ui/error")
        self.ctx.say("The engine is off. The radio has no power.")
        return True

    def _toggle_radio(self) -> None:
        if self._radio_no_power():
            return
        self._sync_radio_settings()
        action = self.radio.toggle(self._radio_backend)
        self._finish_radio_action(action)

    def _radio_switched_off(self) -> bool:
        """Tick and say so when a dial key lands on a radio that is off.

        Sibling of ``_radio_no_power``, and deliberately the same shape: the
        two "not right now" answers should feel identical, so a driver learns
        one response rather than two. Call it after the power check -- no
        power is the more basic reason and owns the reply.
        """
        if self.radio.enabled:
            return False
        self.ctx.audio.play("ui/error")
        self.ctx.say("Radio off.")
        return True

    def _tune_radio(self, direction: int) -> None:
        if self._radio_no_power():
            return
        self._sync_radio_settings()
        if self._radio_switched_off():
            return
        action = self.radio.tune(direction, self._radio_backend)
        self._finish_radio_action(action)

    def _jump_radio_category(self, direction: int) -> None:
        if self._radio_no_power():
            return
        self._sync_radio_settings()
        if self._radio_switched_off():
            return
        action = self.radio.tune_category(direction, self._radio_backend)
        self._finish_radio_action(action)

    def _speak_radio_status(self) -> None:
        self._sync_radio_settings()
        status = self.radio.status_text()
        if not self.truck.engine_on:
            # "Radio on" over a silent cab contradicts the player's ears;
            # the same explanation the Tab radio screen gives goes here too.
            status = f"{status} The engine is off, so the radio has no power right now."
        self.ctx.say(status)

    def _toggle_radio_favorite(self) -> None:
        self._sync_radio_settings()
        message = self.radio.toggle_favorite()
        if self.ctx.profile is not None:
            self.ctx.profile.radio_favorites = sorted(self.radio.favorite_ids)
            self.ctx.save_profile()
        self.ctx.say(message)

    def _adjust_radio_volume(self, direction: int) -> None:
        """Shift with the dial keys: 10-percent steps on the same grid and
        rounding as the Settings > Audio "In-cab radio volume" row, so the
        two controls never disagree about a reachable value. Unlike the
        plain tune and Ctrl category-jump keys, this works whether the
        radio is on or off and whether the engine is running: the setting
        is what it is regardless of power state."""
        s = self.ctx.settings
        value = max(0.0, min(1.0, round(s.radio_volume + RADIO_VOLUME_STEP * direction, 2)))
        s.radio_volume = value
        s.save()
        self._apply_radio_volume()
        pct = round(value * 100)
        if pct <= 0:
            self.ctx.say("Radio volume muted.")
        elif pct >= 100:
            self.ctx.say("Radio volume all the way up.")
        else:
            self.ctx.say(f"Radio volume {pct} percent.")

    def _sync_weather_source(self) -> None:
        real = self.ctx.settings.real_weather
        controls_calendar = self.ctx.settings.live_weather_controls_calendar
        if (
            real == self._weather_source_real
            and controls_calendar == self._live_weather_controls_calendar
        ):
            return
        self._weather_source_real = real
        self._live_weather_controls_calendar = controls_calendar
        self.weather.provider = self.ctx.real_weather_provider() if real else None
        self.weather.live_weather_controls_calendar = controls_calendar
        if not controls_calendar:
            # Include time already driven when the active trip switches back
            # to the independent in-game calendar.
            self.weather.game_hours = (
                self.ctx.profile.calendar_game_hours + self.trip.game_minutes / 60.0
            )
        if not real:
            self.weather.live = False
        self.ctx.audio.set_weather(self.weather.effects.sound)
        self.ctx.audio.set_wind(self.weather.effects.wind)

    def _sync_traffic_source(self) -> None:
        real = self.ctx.settings.real_traffic
        if real == self._traffic_source_real:
            return
        self._traffic_source_real = real
        self.trip.traffic_provider = self.ctx.real_traffic_provider() if real else None

    def _sync_parking_source(self) -> None:
        real = self.ctx.settings.real_parking
        if real == self._parking_source_real:
            return
        self._parking_source_real = real
        self.trip.parking_provider = self.ctx.truck_parking_provider() if real else None

    def _update_announcements(self, dt: float) -> None:
        if self.ctx.settings.renders_terse():
            return
        self._speed_announce_timer += dt
        interval = tuning_for_time_scale(self.trip.time_scale).routine_speech_interval_s
        if self._speed_announce_timer >= interval:
            self._speed_announce_timer = 0.0
            mph = self.truck.speed_mph
            if abs(mph - self._last_announced_mph) >= 5 and mph > 1:
                self._last_announced_mph = mph
                self.ctx.say_event(
                    self.ctx.settings.speed_text(mph),
                    interrupt=False,
                    category=SpeechCategory.STATUS,
                )

    def _brake_budget_s(self, target_mph: float = HAZARD_SAFE_MPH) -> float:
        """Seconds of full service braking to reach the given safe speed.

        Uses the braking the truck can actually deliver right now -- fade,
        wear, load, and grip -- helped uphill and hurt downhill. The rated
        spec number engaged the assist two seconds before a collision on
        hot brakes (playtest transcript, 2026-07-16).
        """
        t = self.truck
        over_mps = max(0.0, (t.speed_mph - target_mph) / MPH_PER_MPS)
        decel = t.full_service_decel_mps2() + G * t.grade
        return over_mps / max(decel, 0.5)

    def _aeb_engage_s(self, target_mph: float) -> float:
        """Time-to-hazard at which automatic braking has to take the truck.

        The physics budget plus its lead: braking heats the brakes, so the
        stop the budget just predicted gets slower while it happens.
        """
        return self._brake_budget_s(target_mph) * AEB_BUDGET_MARGIN + AEB_LEAD_S

    def _hazard_deadline_for(self, window_s: float, dodgeable: bool | None = None) -> float:
        """Time-to-hazard that leaves the driver ``window_s`` of their own.

        Built forward from the moment the assist must act rather than back
        from raw braking physics. The old form -- budget plus slack -- made
        the driver's window a remainder: the assist's engage margin scales
        with the budget, so speed, grade, brake heat, wear and grip all came
        out of the driver's time instead of the truck's. At 65 mph on a
        traffic warning that remainder was half a second, and on hot brakes
        it was already spent when the words started (Munchkinbear, 2026-08-11).

        ``dodgeable`` defaults to the currently pending hazard's own flag, but
        a hazard arming while another is still live needs its OWN budget
        computed on ITS OWN dodgeable-ness -- before ``_hazard_dodgeable`` is
        folded with the pending one -- so the caller can pass it explicitly.
        """
        if dodgeable is None:
            dodgeable = self._hazard_dodgeable
        window = max(window_s, HAZARD_MIN_REACTION_S)
        if dodgeable:
            # The warning offers a lane change; leave room to actually make one.
            window += LANE_TAP_CHANGE_S
        return self._aeb_engage_s(self._hazard_target_mph(dodgeable)) + window

    def _dodge_still_beats_the_hazard(self) -> bool:
        """Whether a lane change already in progress will land in time.

        A driver mid-drift has answered the warning, and grabbing the truck
        out from under them is the assist overriding the very move it asked
        for. Only while the move can still land: a dodge that no longer
        beats the hazard is not a plan, and braking is what is left.
        """
        if self._lane_change_target is None or not self._hazard_dodgeable:
            return False
        if self._hazard_deadline is None:
            return False
        return self._lane_change_timer <= self._hazard_deadline

    def _apply_hazard_brake(self) -> None:
        """Put the assist's held application back on the pedal before physics.

        The input pass ramps the service brake down every frame nobody is on
        it, and writes the emergency flag straight from the B key -- both
        before ``truck.update()`` runs, and both ahead of ``_update_hazard``,
        which is the frame's last word on the hazard. An assist that only
        wrote the pedal from there handed the drums an application a frame's
        ramp short of the full one its budget assumed, framerate-dependently
        so; its emergency flag never survived to be read at all; and the air
        system, which charges a whole brake application every time the pedal
        RISES, was billed for the difference again and again. Re-asserted here
        beside the other assists' floors, one held stop costs one application.
        """
        if self._aeb_brake <= 0.0:
            return
        # Never brake against our own throttle: a hazard assist that has taken
        # the truck has taken the throttle with it.
        self.truck.throttle = 0.0
        self.truck.brake = max(self.truck.brake, self._aeb_brake)
        if self._aeb_emergency:
            self.truck.emergency_brake = True

    def _release_hazard_brake(self) -> None:
        """Hand the pedal back, and forget what the last stop measured.

        The assist releases what the assist applied. The input pass also
        stomps the emergency flag from the B key every frame, but nothing says
        a frame of input runs between engage and clear -- and an application
        with no owner left the truck standing on everything for good. A
        driver-held B is untouched: only the assist's own flag is dropped.
        """
        if self._aeb_emergency:
            self.truck.emergency_brake = False
        self._aeb_brake = 0.0
        self._aeb_emergency = False
        self._aeb_hold_s = 0.0
        self._aeb_losing_s = 0.0
        self._aeb_decel_mps2 = 0.0
        self._aeb_last_speed_mps = None
        self._automatic_braking_announced = False
        self._automatic_braking_escalated = False

    def _track_assisted_deceleration(self, dt: float) -> None:
        """Smooth the deceleration the truck is actually making right now.

        The budget answers what a full application ought to deliver. What the
        escalation needs is a different question nobody can predict: whether
        the stop already underway is going to get there. Measured off the
        truck's own speed and smoothed just enough that a shift, a gust or a
        single long frame is not read as a losing stop.
        """
        speed = max(0.0, self.truck.velocity_mps)
        last = self._aeb_last_speed_mps
        self._aeb_last_speed_mps = speed
        if self._aeb_brake <= 0.0 or last is None or dt <= 0.0:
            return
        self._aeb_hold_s += dt
        sample = (last - speed) / dt
        blend = min(1.0, dt / AEB_DECEL_SMOOTHING_S)
        self._aeb_decel_mps2 += (sample - self._aeb_decel_mps2) * blend

    def _service_braking_is_losing(self, dt: float) -> bool:
        """Whether the stop actually underway is going to miss the hazard.

        Not a prediction. The time left, measured against the deceleration the
        truck is making with everything already on, and asked to keep the same
        fifth of the stop in hand that the engage point was given. A full
        service application that is delivering can never trip this: the assist
        engages with that margin and a delivering truck holds it, because road
        and air drag add to the budget rather than taking from it. What trips
        it is losing ground -- drums cooking under the very application meant
        to save the stop, a grade steepening under the wheels, grip that is not
        there. Then, and only then, the assist uses the hardest stop the rig
        has: the same one the B key gives the driver, and what the driver
        facing an unavoidable collision would do.
        """
        if self._aeb_emergency:
            return True  # earned once, held to the end of the stop
        if self._hazard_deadline is None or self._aeb_hold_s < AEB_DECEL_SMOOTHING_S:
            self._aeb_losing_s = 0.0
            return False
        over_mps = max(0.0, (self.truck.speed_mph - self._hazard_target_mph()) / MPH_PER_MPS)
        left_s = max(0.0, self._hazard_deadline)
        if self._aeb_decel_mps2 * left_s >= over_mps * AEB_BUDGET_MARGIN:
            self._aeb_losing_s = 0.0
            return False
        self._aeb_losing_s += dt
        return self._aeb_losing_s >= AEB_ESCALATE_CONFIRM_S

    def _hazard_target_mph(self, dodgeable: bool | None = None) -> float:
        """The speed that resolves the active hazard by brake alone.

        A fixed object in your lane (dodgeable) cannot be rolled over at the
        moving-hazard safe speed: it takes nearly a stop, then easing around.
        Defaults to the currently pending hazard's own flag; see
        ``_hazard_deadline_for`` for why a caller would pass one explicitly.
        """
        if dodgeable is None:
            dodgeable = self._hazard_dodgeable
        return HAZARD_CREEP_MPH if dodgeable else HAZARD_SAFE_MPH

    # -- grades ---------------------------------------------------------------------

    def _descend_advice(self) -> str:
        """How to get down a hill, in terms of the controls this driver has.

        An automatic has no gear selection -- W, Q, N and Backspace are all
        manual-only -- so telling that driver to pick a gear names a control
        they do not have. What they do have is the same one a real automated
        box gives them: brake, and the transmission holds a lower gear for
        them (``auto_shift`` picks the tallest gear landing in the 1050-1700
        band while braking, and never upshifts off the pedal).
        """
        jake = self.ctx.control_hint("engine_brake")
        if self.truck.transmission.automatic:
            return (
                f"Set the engine brake with {jake} and brake down to speed "
                "before it starts; the transmission will hold a lower gear."
            )
        return f"Pick your gear and set the engine brake with {jake} before it starts."

    def _grade_run_mi(self, start_mi: float, sign: int) -> float:
        """How far a grade of this sign keeps its character from ``start_mi``.

        Sampled at the stride the baked grade segments use, so the answer is
        the run the road data actually has rather than an interpolation of it.
        """
        run = 0.0
        probe = start_mi
        while run < GRADE_WARN_SCAN_MI:
            probe += GRADE_WARN_STEP_MI
            if probe >= self.trip.total_miles:
                break
            if self.trip.grade_at(probe) * sign * 100.0 < GRADE_WARN_CLEAR_PCT:
                break
            run += GRADE_WARN_STEP_MI
        return run

    def _update_grade_advisory(self) -> None:
        """Call out a steep grade before the truck is committed to it.

        A downgrade is the one piece of road a driver has to plan for -- gear
        and retarder chosen at the top, not halfway down -- and nothing spoke
        it. Cruise would quietly run well over the set speed and the first
        news of the hill was the speeding warning (playtest, 2026-07-27).
        One advisory per grade, cleared once the road flattens out.

        Terse speech gets none of them. A driver on terse has asked for the
        road to stay quiet, and the grade is available on demand from the G
        key any time they want it -- so this is exactly the kind of unrequested
        commentary the setting exists to remove. Cruise still speaks up when a
        grade has beaten it, terse or not: that one is not commentary, it is
        the controller reporting it has stopped doing its job.
        """
        t = self.truck
        if self._terse_speech():
            return
        if self.trip.finished or t.speed_mph < GRADE_WARN_MIN_MPH:
            return
        # Sampling the road profile is a scan over the leg's baked segments, so
        # it runs per tenth of a mile rather than per frame. The advisory looks
        # three quarters of a mile ahead; a tenth of that is no delay at all.
        if abs(self.trip.position_mi - self._grade_scan_mi) < GRADE_WARN_RESCAN_MI:
            return
        self._grade_scan_mi = self.trip.position_mi
        here_pct = self.trip.grade_at(self.trip.position_mi) * 100.0
        ahead_mi = self.trip.position_mi + GRADE_WARN_LOOKAHEAD_MI
        ahead_pct = (
            self.trip.grade_at(ahead_mi) * 100.0 if ahead_mi < self.trip.total_miles else here_pct
        )
        # Take whichever of here and just-ahead is steeper, so a grade that
        # starts under the wheels is called out as promptly as one seen coming.
        from_ahead = abs(ahead_pct) >= abs(here_pct)
        pct = ahead_pct if from_ahead else here_pct
        if abs(pct) < GRADE_WARN_CLEAR_PCT:
            # Level both here and just ahead: between hills, so the next one
            # earns a cue. Clearing on the flat under the wheels alone re-armed
            # the advisory on every frame of the approach to a hill, which
            # spoke it over and over until the wheels reached the slope.
            self._grade_warned_sign = 0
            return
        if abs(pct) < GRADE_WARN_PCT:
            return
        sign = 1 if pct > 0 else -1
        if self._grade_warned_sign == sign:
            return
        run_mi = self._grade_run_mi(ahead_mi if from_ahead else self.trip.position_mi, sign)
        if run_mi < GRADE_WARN_MIN_RUN_MI:
            # A dip, not a hill. Deliberately without latching: a short blip
            # must not swallow the advisory for the real grade behind it.
            return
        self._grade_warned_sign = sign
        # The scan gives up at its horizon, so say so rather than claiming the
        # grade ends exactly there.
        about = "at least " if run_mi >= GRADE_WARN_SCAN_MI else ""
        length = f" for {about}{self.trip._distance_text(run_mi)}"
        direction = "upgrade" if sign > 0 else "downgrade"
        self.ctx.audio.play("ui/notify", volume=0.55)
        advice = self._descend_advice() if sign < 0 else "Expect to lose speed."
        self.ctx.say_event(
            f"{abs(pct):.1f} percent {direction} ahead{length}. {advice}",
            interrupt=False,
            priority=EventPriority.ROUTE,
            category=SpeechCategory.NAVIGATION,
        )

    def _update_horn_protection(self) -> None:
        """The pressure protection valve, audibly: below its threshold the
        horn dies mid-blast and the brakes keep their air (FMVSS 121 -- see
        TruckState.HORN_PROTECTION_PSI). Say why once; the driver hearing
        the horn cut out otherwise reads as a broken speaker."""
        t = self.truck
        if t.horn_on and not t.horn_available:
            self.ctx.audio.horn_stop()
            t.horn_on = False
            self.ctx.say_event(
                "The horn cut out: air pressure is low, and the protection "
                "valve saves what is left for the brakes.",
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.STATUS,
            )

    def _horn_scare_animals(self) -> None:
        """The horn's one real power: moving an animal off the road.

        Shane's ask (2026-08-20), and it is what the air horn is FOR on a
        real highway -- but it works the way animals work, not the way a
        button works. Livestock, dogs, and coyotes mostly move; deer and
        elk freeze as often as they bolt, which is why braking stays the
        instruction and the horn is a bonus, never the plan. One attempt
        per hazard: an animal that ignored the first blast has decided.
        Seeded on the hazard so a save-scummed retry hears the same deer
        make the same choice.
        """
        if self._hazard_deadline is None or self._horn_scare_tried:
            return
        from ..sim.trip_models import HAZARDS

        freeze_prone = {h.name for h in HAZARDS if h.animal and h.name in ("the deer", "the elk")}
        movable = {h.name for h in HAZARDS if h.animal}
        names = [n for n in self._hazard_names if n in movable]
        if not names:
            return  # a ladder does not care how loud you are
        self._horn_scare_tried = True
        rng = random.Random((self.trip_seed << 8) ^ int(self.trip.position_mi * 50.0))
        cleared = all(rng.random() < (0.4 if name in freeze_prone else 0.7) for name in names)
        if not cleared or len(names) != len(self._hazard_names):
            # Frozen in the headlights, or something unscareable is out
            # there too. Say nothing: the hazard machinery's own countdown
            # is still the instruction, and a "it did not work" line would
            # talk over the braking the driver should be doing.
            return
        self._finish_hazard_clear(
            f"The horn does it: {self._hazard_names_text()} clears the road. Well done."
        )

    def _hazard_names_text(self) -> str:
        """The pending hazard(s), joined for a resolution line.

        Falls back to "it" when nothing was recorded -- a hazard armed by
        test or tool code that pokes ``_hazard_deadline`` directly rather
        than going through ``_handle_trip_event`` -- so the old generic
        wording still comes out rather than an empty name.
        """
        names = self._hazard_names
        if not names:
            return "it"
        if len(names) == 1:
            return names[0]
        if len(names) == 2:
            return f"{names[0]} and {names[1]}"
        return ", ".join(names[:-1]) + f", and {names[-1]}"

    def _hazard_resolution_text(self) -> str:
        names = self._hazard_names_text()
        if self._hazard_dodgeable:
            return f"You slow nearly to a stop and ease around {names}. Well done."
        if names == "it":
            return "Hazard avoided. Well done."
        return f"Past {names}. Well done."

    def _finish_hazard_clear(self, message_text: str) -> None:
        """Common tail of every way a pending hazard can resolve: brake,
        swerve, or an earlier hazard outrun before a new one armed."""
        self._hazard_deadline = None
        self._release_hazard_brake()
        self._hazard_slow_hint_said = False
        self.ctx.audio.play("events/hazard_clear", volume=0.75)
        self.ctx.controller.rumble.alert(intensity=0.4)
        message = terse_silent(message_text)
        self._last_event_message = message
        # ROUTE, not the ambient default: this is the outcome of a SAFETY
        # event the driver just acted on, and at AMBIENT it queued behind
        # the urgent call that preceded it and was dropped as stale -- in
        # STANDARD mode, where confirmations are supposed to speak in full
        # (Shane, Killeen-Del Rio run, 2026-08-20: found the swerve-clear
        # only in the review keys). Same promotion the creep guidance and
        # the ramp-light family already earned for the same failure.
        self.ctx.say_event(
            message,
            interrupt=False,
            priority=EventPriority.ROUTE,
            category=SpeechCategory.CONFIRMATION,
        )
        self.ctx.award_achievement("hazard_avoided", event=True)
        self._hazard_names = []

    def _clear_hazard(self) -> None:
        """Speak and reset the pending hazard(s) as cleared by braking.

        Shared by the per-frame resolution below and an early resolution
        triggered from ``_handle_trip_event`` when a fresh hazard arms
        while an earlier one was already outrun -- either way the driver
        gets exactly one clean "you made it" line naming what it was for.

        In terse the hazard-clear earcon IS the confirmation; the words are
        congratulation, and the failure outcome stays distinct as the
        collision sound plus its spoken damage line (R4, R14).
        """
        self._finish_hazard_clear(self._hazard_resolution_text())

    def _update_hazard(self, dt: float) -> None:
        if self._hazard_deadline is None:
            return
        target = self._hazard_target_mph()
        if self.truck.speed_mph <= target:
            self._clear_hazard()
            return
        # Old instinct says 25 clears everything; for a fixed object it no
        # longer does. Braking past the moving-hazard speed with the object
        # still in the lane earns the how-to once, so the quiet is never
        # read as an already-cleared hazard.
        if (
            self._hazard_dodgeable
            and not self._hazard_slow_hint_said
            and self.truck.speed_mph <= HAZARD_SAFE_MPH
        ):
            self._hazard_slow_hint_said = True
            # "Or change lanes" only names a maneuver this road offers; a
            # one-lane stretch, or a two-lane one with the other lane coned
            # off, gets nearly-stop as the whole answer.
            hint = (
                "It is still in your lane. Nearly stop, or change lanes."
                if self.trip.has_open_adjacent_lane_at()
                else "It is still in your lane. Nearly stop."
            )
            # ROUTE: not interrupting (it follows the hazard call rather
            # than cutting it) but never droppable. A live hazard still in
            # your lane telling you to nearly stop is the last line in the
            # game that may be binned as stale chatter -- and the stale-drop
            # branch tests PRIORITY, never category, so SAFETY at the ambient
            # default was droppable in exactly the busy moment it matters.
            self.ctx.say_event(
                hint,
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.SAFETY,
            )
        self._hazard_deadline -= dt
        self._track_assisted_deceleration(dt)
        assist_may_act = (
            self.ctx.settings.automatic_emergency_braking
            and not self._dodge_still_beats_the_hazard()
        )
        if not assist_may_act:
            # A driver mid-drift has answered the warning, and an assist the
            # driver has switched off has no truck to take.
            self._release_hazard_brake()
        elif self._aeb_brake > 0.0 or self._hazard_deadline <= self._aeb_engage_s(target):
            if self._aeb_brake <= 0.0:
                # Seed the measurement with the stop the budget has just
                # promised, so the smoothing starts from an honest prior
                # instead of climbing out of a standstill and reading the
                # first fifth of a second of a good stop as a failure.
                self._aeb_decel_mps2 = max(
                    0.0, self.truck.full_service_decel_mps2() + G * self.truck.grade
                )
                self._aeb_hold_s = 0.0
                self._aeb_losing_s = 0.0
            # Full SERVICE braking, and once it is on it stays on until the
            # hazard is answered. Deciding it afresh every frame is what fanned
            # the pedal: the assist's own braking retreats the very threshold
            # that engaged it, so it let go, the threshold came back, and the
            # air system was charged a whole brake application every time round
            # -- which is how ordinary assisted driving ran the tanks down.
            self._aeb_brake = 1.0
            # And the emergency application stays a genuine last resort, judged
            # on the deceleration the truck is actually making rather than on
            # the one a full application ought to deliver.
            if self._service_braking_is_losing(dt):
                self._aeb_emergency = True
            self._apply_hazard_brake()
            if not self._automatic_braking_announced:
                self._automatic_braking_announced = True
                # Kept out of the reviewable log: this line interrupts the
                # hazard warning, and the review keys exist to give that
                # warning back, not the assist that talked over it.
                self.ctx.say_event(
                    "Automatic braking.",
                    interrupt=True,
                    review=False,
                    # The assist reporting that IT acted, not a demand on the
                    # driver -- the braking is audible and the hazard warning
                    # that preceded it carried the action. At quiet, where the
                    # rule is "speak what the player must do something about"
                    # (owner, 2026-08-17), that makes it an earcon. The hazard
                    # call itself stays SAFETY and speaks at every rung.
                    category=SpeechCategory.CONFIRMATION,
                )
            elif self._aeb_emergency and not self._automatic_braking_escalated:
                self._automatic_braking_escalated = True
                self.ctx.say_event(
                    "Emergency braking engaged.",
                    interrupt=True,
                    review=False,
                    category=SpeechCategory.SAFETY,
                )
            if self._cruise_mph is not None:
                self._cancel_cruise()
        if self._hazard_deadline <= 0:
            self._hazard_deadline = None
            self._release_hazard_brake()
            self.ctx.audio.play("vehicle/collision")
            severity = min(1.0, self.truck.speed_mph / 70.0)
            severity *= tuning_for_time_scale(self.trip.time_scale).collision_damage
            self.ctx.controller.rumble.impact(severity)
            self.truck.apply_collision(severity)
            message = (
                f"Collision! The truck took damage. "
                f"Total damage {self.truck.damage_pct:.0f} percent."
            )
            # A dodgeable hazard's announcement leaves the session armed --
            # see ``_handle_trip_event`` -- on the promise that only braking
            # ends it: the driver's own, or AEB's (which already cancels the
            # instant it takes the pedal, above). With AEB off and no dodge
            # and no brake, neither of those ever fires, and the hazard rode
            # cruise straight into the collision with the session still
            # showing armed (reviewer-caught regression on the announce-time
            # fix, 2026-08-14). The deadline lapsing un-dodged is the third
            # way the promise ends, whatever the AEB setting -- the hazard
            # stopped being answerable the moment it hit the truck.
            if (
                self._speed_control_armed
                or self._cruise_mph is not None
                or self._keeper_mph is not None
            ):
                self._disarm_speed_control()
                message = f"{message} Automatic speed control canceled."
            self._last_event_message = message
            self.ctx.say_event(message, interrupt=True, category=SpeechCategory.SAFETY)

    # -- microsleeps (severe fatigue) ----------------------------------------------

    def _microsleep_interval_gm(self, fatigue: float) -> float:
        """Game-minutes between nods; shrinks from base toward the floor as
        exhaustion deepens past the severe threshold."""
        span = max(1.0, 100.0 - hos.FATIGUE_SEVERE)
        t = min(1.0, max(0.0, (fatigue - hos.FATIGUE_SEVERE) / span))
        return MICROSLEEP_BASE_GM + (MICROSLEEP_MIN_GM - MICROSLEEP_BASE_GM) * t

    def _accrue_microsleep(self, gm: float, moving: bool, fatigue: float) -> None:
        """Build toward the next involuntary nod-off while severely fatigued."""
        if self._microsleep_cooldown_gm > 0.0:
            self._microsleep_cooldown_gm = max(0.0, self._microsleep_cooldown_gm - gm)
        if not moving or fatigue < hos.FATIGUE_SEVERE:
            self._microsleep_gm = 0.0
            return
        # One demand on the driver at a time, and not right after the last nod.
        if (
            self._microsleep_deadline is not None
            or self._hazard_deadline is not None
            or self._microsleep_cooldown_gm > 0.0
        ):
            return
        self._microsleep_gm += gm
        if self._microsleep_gm >= self._microsleep_interval_gm(fatigue):
            self._microsleep_gm = 0.0
            self._begin_microsleep()

    def _begin_microsleep(self) -> None:
        self._cancel_cruise()  # the nod takes your hands off the wheel
        self._microsleep_deadline = MICROSLEEP_REACTION_S
        self.ctx.audio.play("vehicle/rumble_strip", volume=1.0)
        self.ctx.controller.rumble.alert()
        self.ctx.say_event(
            "You are nodding off. Steer or brake now to stay awake!",
            interrupt=True,
            category=SpeechCategory.SAFETY,
        )

    def _update_microsleep(self, keys, dt: float) -> None:
        if self._microsleep_deadline is None:
            return
        # Already crawling: the nod passes without leaving the road.
        if self.truck.speed_mph <= HAZARD_SAFE_MPH:
            self._resolve_microsleep(silent=True)
            return
        # The line the truck just spoke is "Steer or brake now to stay awake",
        # and on a pad both of those are the stick and the left trigger --
        # neither of which is a key. A controller-only driver could not wake
        # up at all and drifted off the road every time (owner, 2026-08-16).
        # Parity with the keyboard is the bar: a held Down arrow already
        # counts as a reaction, so a held trigger does too.
        pad = self.ctx.controller
        pad_reacted = pad.active and (abs(pad.steering) > 0.0 or pad.brake > 0.05)
        reacted = (
            keys[pygame.K_LEFT]
            or keys[pygame.K_RIGHT]
            or keys[pygame.K_DOWN]
            or keys[pygame.K_b]
            or pad_reacted
        )
        if reacted:
            self._resolve_microsleep()
            return
        self._microsleep_deadline -= dt
        if self._microsleep_deadline <= 0:
            self._microsleep_deadline = None
            self._microsleep_drift_off_road()

    def _resolve_microsleep(self, *, silent: bool = False) -> None:
        self._microsleep_deadline = None
        self._microsleep_cooldown_gm = MICROSLEEP_COOLDOWN_GM
        self._microsleep_misses = 0
        if not silent:
            self.ctx.say_event(
                "You caught it. Pull over and sleep before the next one.",
                interrupt=False,
                category=SpeechCategory.CONFIRMATION,
            )

    def _microsleep_drift_off_road(self) -> None:
        self._microsleep_misses += 1
        self._microsleep_cooldown_gm = MICROSLEEP_COOLDOWN_GM
        t = self.truck
        self.ctx.audio.play("vehicle/rumble_strip", volume=1.0)
        t.add_damage(MICROSLEEP_SHOULDER_DAMAGE_PCT)
        t.velocity_mps *= 0.8  # wandering onto the shoulder scrubs speed
        standing = self._record_fatigue_event()
        if self._microsleep_misses >= MICROSLEEP_FORCE_STOP_MISSES:
            self._microsleep_misses = 0
            t.throttle = 0.0
            t.brake = 1.0
            self.ctx.audio.play("vehicle/tire_screech", volume=0.9)
            self.ctx.say_event(
                "You cannot stay awake. You drift onto the shoulder and jolt "
                f"awake on the brakes. {standing} {self._fatigue_out_of_service()}",
                interrupt=True,
                category=SpeechCategory.SAFETY,
            )
        else:
            self.ctx.say_event(
                f"You nodded off and drifted onto the rumble strip. The truck "
                f"took damage, now {t.damage_pct:.0f} percent. {standing} "
                "Pull over and sleep.",
                interrupt=True,
                category=SpeechCategory.SAFETY,
            )

    def _record_fatigue_event(self) -> str:
        """Book a run-off-road fatigue event and say what it cost.

        Falling asleep at the wheel is not a scrape: 49 CFR 392.3 forbids
        driving impaired by fatigue, and to a carrier this is a preventable
        safety incident. The first one costs standing; from the second on it
        is a violation the licence answers for.
        """
        from ..models import enforcement
        from .driving_rest_states import _log_fatigue_event

        p = self.ctx.profile
        if p is None or self._enforcement_bypassed():
            return ""
        self.fatigue_events += 1
        hit = enforcement.FATIGUE_EVENT_REPUTATION_HIT
        p.career.reputation = max(0.0, p.career.reputation - hit)
        return _log_fatigue_event(self.ctx, self)

    def _fatigue_out_of_service(self) -> str:
        """The third miss in a row is the fatigue out-of-service order."""
        from ..models import enforcement

        if self._enforcement_bypassed():
            return "Stop and sleep before you wreck."
        self.truck.velocity_mps = 0.0
        self.truck.set_parking_brake()
        self._place_out_of_service()
        return (
            "You are out of service for fatigue: "
            f"{enforcement.FATIGUE_OUT_OF_SERVICE_HOURS:.0f} hours off duty "
            f"before you may roll. It is now {clock_text(self.trip.local_hour)}, "
            "your hours of service are reset, and the delivery deadline kept "
            "counting the whole time."
        )

    def _update_overrev(self, dt: float) -> None:
        t = self.truck
        if not t.over_revving:
            self._overrev_s = 0.0
            self._overrev_warn_due = OVERREV_GRACE_S
            # Off the limiter. The next time the engine goes there is a fresh
            # event and gets its warning again, even at the same wear number.
            self.ctx.reset_event_condition("engine_redline")
            return
        self._overrev_s += dt
        if self._overrev_s < self._overrev_warn_due:
            return
        self._overrev_warn_due = self._overrev_s + OVERREV_REPEAT_S
        self.ctx.audio.play("ui/warning")
        self.ctx.controller.rumble.alert()
        # Speak the meter that is actually moving. Over-revving has charged
        # ENGINE WEAR since the wear meters landed (see
        # ENGINE_WEAR_OVER_REV_PCT_PER_S, "was the damage_pct redline
        # penalty"), but this warning went on reading damage_pct -- which for
        # most drivers sits at zero. The line told the player nothing was
        # being harmed while real harm accumulated, and for a player who only
        # has the spoken word that is the whole readout, not a detail.
        # Where damage has separately put the truck in a band, name the band
        # too, so the number and its meaning never travel apart.
        band = self._damage_band_clause()
        band_clause = f" Truck is in {band}." if band else ""
        message = (
            f"Redline. Engine wear {t.engine_wear_pct:.0f} percent.{band_clause}"
            if self._terse_speech()
            else (
                "The engine is screaming at redline and wearing itself out, now "
                f"{t.engine_wear_pct:.0f} percent engine wear.{band_clause} "
                "Ease off and slow down."
            )
        )
        # A standing condition: the engine is still at redline and the driver
        # already knows. Repeating it earns the voice only when the wear
        # number it carries has actually moved.
        self.ctx.say_event(
            message, interrupt=True, key="engine_redline", category=SpeechCategory.STATUS
        )

    def _update_speeding(self, dt: float, *, accelerator_held: bool = False) -> None:
        """The dash alert, and the braking grace a dropped limit earns.

        This used to be where speeding was charged: hold nine over for six
        real seconds with no patrol anywhere on the route and the drive banked
        a silent "speeding strike", billed at the dock as a
        driver-responsibility charge. That was a fine from an officer who was
        never there, and it is gone. Speeding costs exactly what a trooper who
        saw it decides it costs, and nothing otherwise.

        What survives is the part that was always about fairness rather than
        money: a limit that drops under a loaded truck earns real braking
        seconds before anything counts, because enforcement tickets sustained
        disregard, not the transition. That grace now gates the enforcement
        watch's over-limit distance, which is the measure an officer actually
        reads.
        """
        if self._ramp_mi is not None:
            return  # the ramp is off the highway and unpatrolled
        if self._missed_destination_exit_said and not self._destination_exit_taken:
            return  # recovery state: guide the player back to the missed exit
        if self._pull_over is not None:
            return  # already stopped; the dash has nothing to add
        limit, _ = self.trip.speed_limit_at(self.trip.position_mi)
        self._update_overspeed_warning(dt, limit)
        # About 2 mph per second of comfortable braking sets the window,
        # capped so the grace cannot be used to coast through a whole
        # restricted zone.
        if self._enforced_limit_prev is not None and limit < self._enforced_limit_prev:
            grace = (self.truck.speed_mph - limit) / 2.0
            self._limit_drop_grace_s = max(self._limit_drop_grace_s, min(15.0, grace))
            # The zone-entry line is queued at ROUTE and may lag its boundary
            # by the ROUTE wait budget. A driver still on the throttle inside
            # that window has simply not been told yet, so the throttle
            # check must not arm until the line has had time to speak.
            self._limit_drop_throttle_exempt_s = LIMIT_DROP_SPEECH_LATENCY_S
        self._enforced_limit_prev = limit
        if self._limit_drop_grace_s > 0.0:
            self._limit_drop_grace_s = max(0.0, self._limit_drop_grace_s - dt)
            # Staying on the throttle through the drop is disregard, not
            # compliance: the grace collapses. Read the current key/trigger
            # position, not the smoothed truck throttle, which is still
            # ramping down just after the driver lifts off -- and only once
            # the announcement's speech-latency window above has passed.
            if self._limit_drop_throttle_exempt_s > 0.0:
                self._limit_drop_throttle_exempt_s = max(
                    0.0, self._limit_drop_throttle_exempt_s - dt
                )
            elif accelerator_held:
                self._limit_drop_grace_s = 0.0

    def _update_overspeed_warning(self, dt: float, limit: float) -> None:
        """The dash overspeed alert: speak once, then chime until compliant.

        Arms at OVERSPEED_WARN_MPH over the limit -- above the pace predictive
        cruise itself holds, and inside the enforcement leeway, so an attentive
        driver hears the dash before any strike clock matters and never hears
        it for a speed the truck chose. The first trigger speaks the limit;
        while the truck stays over, the chime repeats on its interval. Actively
        braking down quiets the nag (the driver is already complying), and
        settling back under the limit disarms it for the next episode.

        This had a setting -- on / urgent only / off -- and the setting existed
        because the alert armed at exactly cruise's own 5-over pace, so it
        chimed at drivers who had done nothing. With the threshold above that
        pace there is nothing left to turn off: it now speaks only when the
        driver is genuinely heading for a citation.
        """
        speed = self.truck.speed_mph
        if self._overspeed_active:
            if speed <= limit + OVERSPEED_WARN_MPH - OVERSPEED_RESET_MPH:
                self._overspeed_active = False
                self._log_overspeed("disarmed", speed, limit)
                return
            braking_down = self.truck.brake > 0.0 and self.truck.throttle <= 0.05
            # The further over, the faster the ding: cadence slides from
            # polite to urgent as the overage approaches OVERSPEED_URGENT_MPH.
            urgency = (speed - limit - OVERSPEED_WARN_MPH) / (
                OVERSPEED_URGENT_MPH - OVERSPEED_WARN_MPH
            )
            urgency = max(0.0, min(1.0, urgency))
            interval = OVERSPEED_CHIME_REPEAT_S - urgency * (
                OVERSPEED_CHIME_REPEAT_S - OVERSPEED_CHIME_FAST_S
            )
            self._overspeed_chime_timer += dt
            if self._overspeed_chime_timer >= interval and not braking_down:
                self._overspeed_chime_timer = 0.0
                self.ctx.audio.play("vehicle/overspeed_chime", volume=0.55)
                self._log_overspeed("chime", speed, limit)
            return
        if speed > limit + OVERSPEED_WARN_MPH:
            self._overspeed_active = True
            self._overspeed_chime_timer = 0.0
            self._log_overspeed("armed", speed, limit)
            self.ctx.audio.play("vehicle/overspeed_chime", volume=0.65)
            self.ctx.say_event(
                overspeed_nag(
                    self.ctx.settings.speed_text(limit),
                    self.ctx.settings.speed_value(limit),
                ),
                interrupt=False,
                priority=EventPriority.ROUTE,
                category=SpeechCategory.NAVIGATION,
            )

    def _log_overspeed(self, event: str, speed: float, limit: float) -> None:
        """Every arm, chime and disarm, with the numbers behind it.

        A driver who hears the alert cannot see which limit it is measuring
        against, and from a bug report neither can we: a tester reporting a
        chime at five over could be five over a number he never saw drop
        (Shane, 2026-08-15). The log carries the speed, the limit in force,
        the mile it came from and the zone that set it, so a session can be
        read back instead of argued about. Transitions and chimes only --
        three or four lines an episode, not a per-frame trace.
        """
        _, reason = self.trip.speed_limit_at(self.trip.position_mi)
        log.info(
            "overspeed %s: %.1f mph, limit %.0f (%+.1f over, arms at %+.0f), mile %.2f, %s",
            event,
            speed,
            limit,
            speed - limit,
            OVERSPEED_WARN_MPH,
            self.trip.position_mi,
            f"zone: {reason}" if reason else "no zone",
        )

    def _begin_pull_over(self, limit: float) -> None:
        """A trooper has lit you up: announce it and wait for the stop."""
        self._pull_over = "lights"
        self._pull_over_start_mi = self.trip.position_mi
        self._pull_over_signaled = False
        self._pull_over_limit = limit
        self._pull_over_over = max(0.0, self.truck.speed_mph - limit)
        self._pull_over_kind = "speeding"
        self._pull_over_title = "Traffic stop"
        self._pull_over_summary = ""
        self._pull_over_fine = 0.0
        self._pull_over_reputation_hit = 0.0
        self._pull_over_return = "Back on the highway. Watch your speed."
        # Where the violation happened, not where the truck finally stops: a
        # driver clocked in the cones does not get out of the doubled fine by
        # coasting past the last barrel before pulling over.
        self._pull_over_construction_zone = self.trip.in_construction_zone
        self._pull_over_warning_level = 0
        self._reset_pull_over_tracker()
        self._pull_over_compliance = PULL_OVER_START_COMPLIANCE
        self._pull_over_prev_mph = self.truck.speed_mph
        post = self.trip.active_post_at(self.trip.position_mi)
        where = post.reason if post is not None else "highway enforcement"
        signal_hint = self.ctx.control_hint("take_exit")
        message = (
            f"Lights and siren behind you. A trooper on this {where} clocked you "
            f"at {self.ctx.settings.speed_text(self.truck.speed_mph)} in a "
            f"{self.ctx.settings.speed_text(limit)} zone. Signal with "
            f"{signal_hint} and brake to a stop on the shoulder."
        )
        self._arm_pull_over(message)
        self.ctx.controller.rumble.alert()

    def _arm_pull_over(self, message: str) -> None:
        """Shared start for every stop: hands back on the wheel, real clock,
        and no judgement until the player has heard the whole instruction.

        The old code started draining compliance the instant the siren played.
        Holding a steady speed -- which is what cruise, the speed keeper, or
        simply listening looks like -- drained it to zero about five seconds
        in, while a thirty-four word instruction was still being spoken. That
        charged attentive drivers with a felony for doing nothing wrong.
        """
        self.trip.pull_over_active = True
        self._disarm_speed_control()  # hands back on the wheel to brake
        self._pull_over_grace_s = self._pull_over_grace_seconds(message)
        # Commit the encounter to the save before a word of it is spoken, so
        # neither a crash nor a quit-to-menu can make it never have happened.
        self.enforcement_events.add(f"stop:{round(self.trip.position_mi, 1)}")
        if self.ctx.profile is not None:
            self.ctx.profile.active_trip = self.snapshot()
            self.ctx.save_profile()
        # Cut the radio outright rather than ducking it. The catalog ships
        # dozens of always-available police and fire scanner streams, so a
        # siren over programme material is genuinely ambiguous -- and the
        # sudden silence is itself an unmistakable cue that something has
        # taken the cab over.
        self._cut_radio_for_stop()
        # Lead with the synthesized enforcement signature, then hold the real
        # siren underneath it. The signature says "this is the game telling
        # you about enforcement"; the siren says what it is.
        self._play_enforcement_marker(volume=0.9)
        self._hold_stop_siren()
        self.ctx.say_event(message, interrupt=True, category=SpeechCategory.NAVIGATION)
        # One demand at a time: an exit armed for a ramp must not keep
        # announcing and steering for it under the trooper's lights -- that
        # is how a scale bypass became a failure-to-stop cascade.
        if self._stand_down_exit_for_stop():
            self.ctx.say_event(
                "Exit approach canceled; plan it again after the stop.",
                interrupt=False,
                category=SpeechCategory.CONFIRMATION,
            )

    def _pull_over_grace_seconds(self, message: str) -> float:
        """Real seconds to hear the instruction and get a hand to the wheel."""
        speech_rate = (
            self.ctx.settings.speech_rate
            if self.ctx.settings.sapi_events
            and getattr(self.ctx.speech, "event_supports_rate", False)
            else 0.0
        )
        return ramp_arrival_grace_seconds(message, speech_rate)

    def _enforcement_bypassed(self) -> bool:
        return self.ctx.settings.hos_mode in hos.HOS_NON_ENFORCED_MODES

    def _weigh_station_key(self, stop) -> str:
        return f"weigh:{stop.name}:{stop.at_mi:.1f}"

    def _check_weigh_station_enforcement(self, previous_mi: float) -> None:
        # One demand on the driver at a time. This guarded on the stop and the
        # ramp but not on a running hazard deadline, so a scale could speak
        # over a braking window the player had two seconds to make.
        if self._enforcement_bypassed() or self._enforcement_busy():
            return
        for stop in self.trip.stops:
            if stop.type != "weigh_station":
                continue
            ahead = stop.at_mi - self.trip.position_mi
            key = self._weigh_station_key(stop)
            if (
                0 < ahead <= self._scale_notice_lookahead_mi()
                and key != self._weigh_station_notice_key
                and self._scale_is_open(stop)
            ):
                # Only an OPEN scale is spoken. A closed one gets the thinner,
                # drier approach bed and nothing said -- the swell says
                # "scale", and the absence of speech is what says "closed".
                self._weigh_station_notice_key = key
                # Its own earcon, not the shared inspection cue: testers
                # could not tell "the scale is ahead" apart from "you are
                # being looked at for something else" (owner ruling,
                # 2026-08-14). The low thump-then-beep reads as the scale on
                # its own, before a word is spoken.
                self.ctx.audio.play("events/weigh_station_warning", volume=0.7)
                # Action first, and both keys through control_hint. The old
                # line hard-coded "press T", and T at speed planned a sleep
                # stop past the scale -- the instruction itself marched a
                # tester into the bypass charge (report, 2026-08-12).
                self.ctx.say_event(
                    # short_distance_text, not distance_text: the plain form
                    # rounds to whole miles, so a scale first seen inside half
                    # a mile announced itself "in 0 miles" and the reminder
                    # that followed said "in half a mile" -- the distance
                    # appeared to run backwards while the scale was still
                    # ahead (gate harness, 2026-08-15). This is the same
                    # rounding that made the route key say "0 miles" to a
                    # gate; the colloquial form is what the reminder below
                    # already speaks, so the two now agree.
                    # No mainline speed demand: a real scale has its own
                    # deceleration ramp, and "slow below fifteen" spoken here
                    # had the owner crawling an open interstate at twenty for
                    # five miles, obeying the sentence to the letter
                    # (playtest, 2026-08-20). The bypass judgment never
                    # needed it -- taking the scale's exit is what counts --
                    # and the ramp glide owns the slowing.
                    f"Open weigh station ahead in "
                    f"{self.ctx.settings.short_distance_text(ahead)}: "
                    f"{stop.name}. All trucks must pull in. Signal for "
                    "the scale exit with "
                    f"{self.ctx.control_hint('take_exit')}; the ramp brings "
                    "you down to the scale. Once you are stopped at the "
                    f"scale, press {self.ctx.control_hint('rest')} to check in.",
                    interrupt=False,
                    priority=EventPriority.ROUTE,
                    category=SpeechCategory.NAVIGATION,
                )
            self._check_scale_reminder(stop, ahead, key)
            if key in self.enforcement_events:
                continue
            crossed = previous_mi < stop.at_mi <= self.trip.position_mi
            if (
                crossed
                and self._scale_is_open(stop)
                and self.truck.speed_mph > WEIGH_STATION_BYPASS_MPH
            ):
                if self._exit_is_armed_for(stop):
                    # Signaled for this scale's own ramp. Whether that is a
                    # check-in or a miss is not decided here: the exit watch
                    # settles it later in this same frame, and until it has,
                    # ramp speed over the bypass threshold proves nothing --
                    # the gore is crossed at ramp speed by definition. A
                    # tester was fined for blowing past a scale while he was
                    # on its ramp at eighteen (log, 2026-08-10).
                    self._weigh_station_pending = stop
                    continue
                self.enforcement_events.add(key)
                self._charge_weigh_station_bypass(stop)

    def _exit_is_armed_for(self, stop) -> bool:
        """Whether this stop's own exit is the one the driver is committed to."""
        active = self._ramp_stop or self._exit_stop
        return active is not None and active.key == stop.key

    def _resolve_weigh_station_bypass(self) -> None:
        """Judge a deferred scale crossing now that the exit watch has run.

        On the scale's own ramp, the driver pulled into the inspection lane
        and owes nothing. Anything else -- too fast for the ramp, out of the
        exit lane, the signal canceled at the gore -- is the same bypass it
        would have been with no signal at all, so arming the exit and then
        driving on buys nothing.
        """
        stop = self._weigh_station_pending
        if stop is None:
            return
        self._weigh_station_pending = None
        key = self._weigh_station_key(stop)
        if key in self.enforcement_events:
            return
        self.enforcement_events.add(key)
        if self._ramp_stop is not None and self._ramp_stop.key == stop.key:
            return  # pulled in; the scale gets its look at the check-in
        if self._pull_over is not None:
            return  # already stopped this frame; one demand on the driver
        self._charge_weigh_station_bypass(stop)

    def _charge_weigh_station_bypass(self, stop) -> None:
        # Caught, not certain -- steep, per WEIGH_STATION_BYPASS_CATCH_CHANCE.
        # Named, seeded, and settled once per scale: a reload cannot re-roll
        # whether the bypass unit got you. Missing it is silent by design --
        # getting away with it is part of the tension.
        key = self._weigh_station_key(stop)
        roll = random.Random(f"{self.trip_seed}:scale-bypass:{key}").random()
        if roll >= WEIGH_STATION_BYPASS_CATCH_CHANCE:
            return
        self._begin_enforcement_pull_over(
            kind="weigh_station_bypass",
            title="Weigh station bypass stop",
            summary=(
                f"Scale officers saw you blow past {stop.spoken_name} "
                "instead of pulling into the inspection lane."
            ),
            fine=WEIGH_STATION_BYPASS_FINE,
            reputation_hit=hos.HOS_REPUTATION_HIT,
            return_message="Back on the highway. Watch for the next open scale.",
            lights_message=(
                "Scale bypass enforcement. Lights and siren behind you: "
                f"signal with {self.ctx.control_hint('take_exit')} and "
                "brake to a stop on the shoulder."
            ),
        )

    def _check_unsafe_damage_enforcement(self) -> None:
        if self._enforcement_bypassed() or self._enforcement_busy():
            return
        if (
            self.truck.damage_pct < UNSAFE_DAMAGE_STOP_PCT
            or self.truck.speed_mph <= DOCKING_MAX_MPH
        ):
            return
        patrol = self.trip.active_post_at(self.trip.position_mi)
        if patrol is None:
            return
        key = f"unsafe_damage:{round(self.trip.position_mi, 1)}"
        if key == self._unsafe_damage_stop_key or key in self.enforcement_events:
            return
        self._unsafe_damage_stop_key = key
        self.enforcement_events.add(key)
        self._begin_enforcement_pull_over(
            kind="unsafe_damage",
            title="Unsafe equipment stop",
            summary=(
                f"A trooper in this {patrol.reason} saw visible truck damage "
                f"at {self.truck.damage_pct:.0f} percent and ordered a roadside "
                "safety inspection."
            ),
            fine=UNSAFE_DAMAGE_FINE,
            reputation_hit=hos.HOS_REPUTATION_HIT,
            return_message="Back on the highway. Repair the truck at the next safe stop.",
            lights_message=(
                "Unsafe equipment stop. Lights and siren behind you: signal "
                f"with {self.ctx.control_hint('take_exit')} and brake to a "
                "stop on the shoulder."
            ),
        )

    def _begin_enforcement_pull_over(
        self,
        *,
        kind: str,
        title: str,
        summary: str,
        fine: float,
        reputation_hit: float,
        return_message: str,
        lights_message: str,
    ) -> None:
        self._pull_over = "lights"
        self._pull_over_start_mi = self.trip.position_mi
        self._pull_over_signaled = False
        self._pull_over_limit = 0.0
        self._pull_over_over = 0.0
        self._pull_over_kind = kind
        self._pull_over_title = title
        self._pull_over_summary = summary
        self._pull_over_fine = fine
        self._pull_over_reputation_hit = reputation_hit
        self._pull_over_return = return_message
        # Captured with the observation, for the same reason as the speeding
        # stop: the zone that matters is the one the violation happened in.
        self._pull_over_construction_zone = self.trip.in_construction_zone
        self._pull_over_warning_level = 0
        self._reset_pull_over_tracker()
        self._pull_over_compliance = PULL_OVER_START_COMPLIANCE
        self._pull_over_prev_mph = self.truck.speed_mph
        self._arm_pull_over(lights_message)

    def _signal_pull_over(self) -> None:
        """X during a pull-over: signal and ease over (better demeanor)."""
        if self._pull_over == "lights":
            self._pull_over = "stopping"
            self._pull_over_signaled = True
            # A one-time compliance bump for signaling. Guarded so that if an
            # unsignal is ever added, toggling can never re-earn the boost.
            if not self._pull_over_signal_boost:
                self._pull_over_signal_boost = True
                self._pull_over_compliance = min(
                    1.0, self._pull_over_compliance + PULL_OVER_SIGNAL_BOOST
                )
            self.ctx.audio.play("vehicle/signal_tone", volume=0.7, pan=0.6)
            self.ctx.say("Signaling and easing onto the shoulder. Brake to a full stop.")
        else:
            self.ctx.say("Pulling over. Brake to a full stop on the shoulder.")

    def _update_brake_heat_cue(self, dt: float) -> None:
        """Squeal when hot brakes are worked past their fade temperature."""
        if self._brake_squeal_cooldown_s > 0.0:
            self._brake_squeal_cooldown_s = max(0.0, self._brake_squeal_cooldown_s - dt)
            return
        t = self.truck
        if t.brake >= 0.4 and t.speed_mph > 10.0 and t.brake_temp_c >= t.specs.brake_fade_temp_c:
            self.ctx.audio.play("vehicle/brake_squeal", volume=0.8)
            self._brake_squeal_cooldown_s = 4.0

    def _update_destination_approach_assist(self) -> None:
        """Ease the truck down so it ARRIVES stopped, not so it stops on arrival.

        The setting promises "slows and stops at the selected facility
        arrival point". Only the stopping half existed: the arrival gate
        applies full brake, and it runs inside ``if self.trip.finished`` --
        true only once the truck is AT the point. So the assist could hold a
        truck that had already stopped, and nothing more. The owner drove a
        delivery to Odessa, braked himself, and the assist announced "stopped
        and holding" as though it had done it (2026-08-19: "it did not stop
        me. I stopped").

        Priced like the exit assist's ramp glide rather than as a fixed
        trigger distance: road speed stands until the truck is inside the
        distance it needs to shed, then the cap follows the deceleration
        down. A driver already slower than the cap is left alone -- this only
        ever takes speed off, never adds it, and never steers.
        """
        if not self.ctx.settings.destination_approach_assist:
            return
        trip = self.trip
        # HOW FAR TO THE GATE -- which is not the same as how far to the end
        # of the route. trip.remaining_miles measures the route, and it stays
        # parked while the truck is on the ramp: the harness showed it reading
        # 3.200 mi with the truck crawling yards from the market, so the cap
        # came out at 215 mph and the assist waved the truck through. The
        # arrival lives on the ramp instead -- _ramp_mi counts down from
        # RAMP_LENGTH_MI to the stop, and the dock opens when it reaches zero
        # at docking speed; anything faster is a blown stop and the driver is
        # told they drove past (owner, three runs, 2026-08-19/20).
        #
        # A same-city street chain to a gate has no ramp, so that route shape
        # still measures off the route, which for it is the same thing.
        remaining_mi = None
        ramp_stop = getattr(self, "_ramp_stop", None)
        if self._ramp_mi is not None and getattr(ramp_stop, "type", "") == "delivery_destination":
            remaining_mi = self._ramp_mi
        elif not trip.finished and trip._is_facility_approach_route():
            remaining_mi = trip.remaining_miles
        if remaining_mi is None:
            return
        # No margin held back, deliberately. Stopping short is not a safer
        # version of stopping: the dock opens at the END of the ramp, so a
        # truck halted two hundred feet shy of it with the brake held is a
        # truck that never arrives -- which is what a reserve of exactly that
        # size did on the first run after the clock fix. The gentle rate below
        # is the margin.
        remaining_m = max(0.0, remaining_mi) * 1609.344
        if remaining_m <= 0.0:
            # At the point or past it: whatever is still on has to come off.
            if self.truck.speed_mph > DOCKING_MAX_MPH:
                self.truck.throttle = 0.0
                self.truck.brake = 1.0
                if self._cruise_mph is not None or self._keeper_mph is not None:
                    self._pause_speed_control(resume_when_rolling=False)
            return
        # v = sqrt(2 a d): the fastest this truck may still be doing and stop
        # in the road it has left, at a comfortable rate.
        cap_mph = (2.0 * APPROACH_ASSIST_DECEL_MPS2 * remaining_m) ** 0.5 * MPH_PER_MPS
        if self.truck.speed_mph <= cap_mph:
            return
        # Over the cap: shed, with the pedal MODULATED to how far over it is.
        # A fixed pressure overshoots -- 0.4 on a loaded rig is about
        # 1.5 m/s^2 against the 0.9 the curve is drawn for, so the truck shed
        # faster than the profile and came to rest 143 feet short of the gate,
        # where the cap is no longer binding and the assist lets go. Stopping
        # short and sitting there is its own failure: nothing arrives.
        #
        # Tracking the curve instead means easing off as the truck comes back
        # under it, so speed follows the profile down and reaches zero AT the
        # point rather than before it.
        self.truck.throttle = 0.0
        over = (self.truck.speed_mph - cap_mph) / max(cap_mph, 1.0)
        pressure = APPROACH_ASSIST_BRAKE * min(1.0, max(0.25, over * 3.0))
        self.truck.brake = max(self.truck.brake, pressure)
        if self._cruise_mph is not None or self._keeper_mph is not None:
            # The assist has the pedals for the arrival; automatic control
            # must not hold a speed against it. Paused rather than cancelled,
            # the way the exit assist pauses for a ramp.
            self._pause_speed_control(resume_when_rolling=False)

    def _update_traction_cues(self) -> None:
        """Speak the physical traction states once, on the edge they begin.

        Each warning names the state and the action that clears it: ease off
        the speed when the tires float, ease off the jake when the drive
        wheels slide. The flag resets when the state clears, so a second
        excursion warns again.
        """
        t = self.truck
        planing = t.hydroplaning
        if planing and not self._hydro_active:
            self.ctx.say_event(
                "Hydroplaning. The steering has gone light; ease off the speed.",
                category=SpeechCategory.SAFETY,
            )
        self._hydro_active = planing
        slipping = t.jake_slipping and t.speed_mph > 5.0
        if slipping and not self._jake_slip_active:
            self.ctx.say_event(
                "The drive wheels are sliding under the engine brake. Ease off the jake.",
                category=SpeechCategory.SAFETY,
            )
        self._jake_slip_active = slipping
        if t.chains_just_snapped:
            t.chains_just_snapped = False
            self.ctx.say_event(
                "A tire chain let go and hammered the fender on its way off. "
                "The set is scrap; you are running on rubber again.",
                category=SpeechCategory.MONEY,
            )
        chains_fast = t.chains_on and t.speed_mph > CHAIN_SAFE_MPH + 2.0
        if chains_fast and not self._chains_fast_active:
            self.ctx.say_event(
                "The chains are hammering the pavement at this speed. "
                f"Keep it under {CHAIN_SAFE_MPH:.0f} or they will not last.",
                category=SpeechCategory.COACHING,
            )
        self._chains_fast_active = chains_fast

    def _update_chain_law(self) -> None:
        """Warn once per area, then run the deterministic checkpoint.

        The physics is the real enforcement -- glare ice at 0.15 grip does not
        negotiate -- but the law adds the honest paper consequence: roll past
        the midpoint of an active control out of compliance and the checkpoint
        at the bottom of the grade may have your number. One citation per area
        per level; the roll is seeded, so a reload does not re-roll the dice.
        """
        t = self.truck
        level = self.trip.chain_law_level()
        if level == 0 or t.speed_mph < 3.0:
            return
        area = self.trip.chain_law_area_at(self.trip.position_mi)
        if area is None:
            return
        compliant = t.chains_on or (level == 1 and t.tire_type == TIRE_WINTER)
        if compliant:
            return
        key = (area, level)
        if key not in self._chain_law_warned:
            self._chain_law_warned.add(key)
            need = "chains" if level >= 2 else "winter-rated tires or chains"
            self.ctx.say_event(
                f"You are rolling into an active chain law without {need}. "
                "Stop and chain up, or hope the checkpoint is unstaffed.",
                category=SpeechCategory.NAVIGATION,
            )
        start, end = self.trip.chain_law_areas[area]
        if self.trip.position_mi < (start + end) / 2.0 or key in self._chain_law_cited:
            return
        self._chain_law_cited.add(key)
        roll = random.Random(f"{self.trip_seed}:chain-law:{area}:{level}").random()
        if roll >= CHAIN_LAW_CHECKPOINT_CHANCE:
            return
        p = self.ctx.profile
        zone = self.trip.in_construction_zone
        fine = citation_fine(CHAIN_LAW_FINE, career_citations(p), construction_zone=zone)
        p.money -= fine
        self.ticket_fines_paid += fine
        self.ctx.audio.play("ui/error")
        # A citation is money, not an act-now warning: ROUTE's never-dropped
        # queue instead of an interrupt that could erase one.
        self.ctx.say_event(
            "Chain checkpoint. An officer waves you onto the scale apron and "
            f"writes a chain-law citation: {fine:,.0f} dollars."
            f"{construction_zone_fine_clause(zone)} "
            f"You have {p.money:,.0f} dollars.",
            interrupt=False,
            priority=EventPriority.ROUTE,
            category=SpeechCategory.MONEY,
        )

    def _reset_pull_over_tracker(self) -> None:
        """Clear the compliance tracker on every stop-ending path so the next
        stop starts clean."""
        self._pull_over_compliance = 0.0
        self._pull_over_elapsed = 0.0
        self._pull_over_prev_mph = 0.0
        self._pull_over_coast_s = 0.0
        self._pull_over_signal_boost = False
        self._pull_over_nosignal_hit = False

    def _update_pull_over(self, dt: float, *, service_braking: bool = False) -> None:
        """Judge the stop by behavior, and warn by distance. A compliance
        tracker (0..1) rises with braking and falls with accelerating,
        coasting, and failing to signal (deductions stack); a full stop opens
        the roadside stop and zeroing it out ends in a felony. On top of that,
        the staged failure-to-stop warnings still speak as the miles roll by,
        and simply driving miles on with the lights behind you is a felony
        regardless of the tracker."""
        if self._pull_over is None:
            return
        if self._enforcement_bypassed():
            self._pull_over = None
            self.trip.pull_over_active = False
            self._end_stop_audio()
            return
        # Re-asserted every frame the cruiser is there, and released by its own
        # dead man's switch the moment this stops being called.
        self._hold_stop_siren()
        if self.truck.speed_mph <= DOCKING_MAX_MPH:
            self._open_traffic_stop()
            return
        # Nothing is judged until the instruction has finished being spoken
        # and the player has had real reaction seconds on top of it.
        if self._pull_over_grace_s > 0.0:
            self._pull_over_grace_s = max(0.0, self._pull_over_grace_s - dt)
            self._pull_over_prev_mph = self.truck.speed_mph
            self._pull_over_start_mi = self.trip.position_mi
            return
        self._pull_over_elapsed += dt
        speed = self.truck.speed_mph
        accel_mph_s = (speed - self._pull_over_prev_mph) / dt if dt > 0 else 0.0
        self._pull_over_prev_mph = speed
        delta = 0.0
        if service_braking:
            # Compliant deceleration. Method-agnostic: service, emergency, or
            # engine+service brake all read the same, and stacking earns no extra.
            delta += PULL_OVER_BRAKE_RATE * dt
            self._pull_over_coast_s = 0.0
        elif accel_mph_s > PULL_OVER_ACCEL_EPS_MPH_S:
            # Genuinely speeding up (not jitter, not throttle-held-steady).
            delta -= PULL_OVER_ACCEL_RATE * dt
            self._pull_over_coast_s = 0.0
        else:
            # Coasting, holding a steady speed, or slowing on the engine brake /
            # grade alone -- all treated the same, and only after a 3 s grace.
            self._pull_over_coast_s += dt
            if self._pull_over_coast_s >= PULL_OVER_COAST_GRACE_S:
                delta -= PULL_OVER_COAST_RATE * dt
        # Failing to signal past the grace: a one-time 1/4 hit, then a small
        # periodic drain. Stacks with any accelerating/coasting deduction above.
        if self._pull_over_elapsed > PULL_OVER_SIGNAL_GRACE_S and not self._pull_over_signaled:
            if not self._pull_over_nosignal_hit:
                self._pull_over_nosignal_hit = True
                delta -= PULL_OVER_NOSIGNAL_HIT
            delta -= PULL_OVER_NOSIGNAL_RATE * dt
        self._pull_over_compliance = max(0.0, min(1.0, self._pull_over_compliance + delta))
        # Running is a choice, never a consequence of hesitating: only the
        # held opt-in below starts a pursuit.
        self._update_pursuit_optin(dt)
        if self._pull_over is None:
            return  # the opt-in fired
        # The warnings are on a real-time cadence now. They used to be keyed
        # to trip miles, which compression could burn through before the
        # first one could ever speak.
        distance = self.trip.position_mi - self._pull_over_start_mi
        if self._pull_over_elapsed >= PULL_OVER_FINAL_WARNING_S:
            self._warn_failure_to_stop(final=True)
        elif self._pull_over_elapsed >= PULL_OVER_FIRST_WARNING_S:
            self._warn_failure_to_stop(final=False)
        # Not stopping is not running. A zeroed tracker or two miles of
        # rolling ends in troopers boxing you in: a failure-to-stop citation
        # and a forced stop, which is expensive and goes on the record -- but
        # it is not a felony, and it cannot end a career by inattention.
        if self._pull_over_compliance <= 0.0 or distance >= PULL_OVER_IGNORE_MI:
            # Escalate through the warnings rather than jumping to the last
            # one: the player hears it getting worse before it is over.
            self._warn_failure_to_stop(final=self._pull_over_warning_level >= 1)
            self._pull_over_forced_s += dt
            if self._pull_over_forced_s >= PULL_OVER_FORCED_STOP_S:
                self._fail_to_stop()
        else:
            self._pull_over_forced_s = 0.0

    def _warn_failure_to_stop(self, *, final: bool) -> None:
        level = 2 if final else 1
        if self._pull_over_warning_level >= level:
            return
        self._pull_over_warning_level = level
        if final:
            message = (
                "Final failure-to-stop warning. Brake to a full stop now or "
                "troopers will end the stop with spike strips and felony charges."
            )
        elif self._pull_over_signaled:
            message = (
                "You signaled for the stop, but you are still moving with lights "
                "behind you. Brake to a full stop on the shoulder."
            )
        else:
            message = (
                "Failure-to-stop warning. Signal with "
                f"{self.ctx.control_hint('take_exit')} and brake to a full "
                "stop on the shoulder."
            )
        self.ctx.audio.play("ui/warning")
        self.ctx.say_event(message, interrupt=True, category=SpeechCategory.NAVIGATION)

    def _settle_engine_to_idle(self) -> None:
        """Snap engine RPM and audio to idle for a menu-driven stop.

        You are stopped -- for a trooper, a dock, a scale, a pickup gate --
        not parked for the night: the engine keeps running, but it must not
        keep sounding like highway load. The frame loop that eases the rev
        down between frames stops running the instant a menu takes over the
        driving state, so whatever was left over from braking to the stop --
        a lagging throttle, RPM still catching up to idle -- would otherwise
        hang in the engine loop for the whole encounter. Set the engine band
        directly rather than through the full audio update, which also
        drives the radio, lane cues, and weather bed -- none of which belong
        in this one-off sync.
        """
        self.truck.throttle = 0.0
        self.truck.rpm = self.truck.specs.idle_rpm
        self.ctx.audio.set_engine_rpm(self.truck.rpm, throttle=0.0)

    def _open_traffic_stop(self) -> None:
        signaled = self._pull_over_signaled
        over, limit = self._pull_over_over, self._pull_over_limit
        kind = self._pull_over_kind
        title = self._pull_over_title
        summary = self._pull_over_summary
        fine = self._pull_over_fine
        reputation_hit = self._pull_over_reputation_hit
        return_message = self._pull_over_return
        construction_zone = self._pull_over_construction_zone
        # Read the tracker before the reset zeroes it.
        clean_stop = self._pull_over_compliance >= PULL_OVER_FULL_COMPLIANCE
        self.trip.pull_over_active = False
        self._end_stop_audio()
        self._settle_engine_to_idle()
        self._pursuit_hold_s = 0.0
        # Rolling on through a spoken failure-to-stop warning before finally
        # pulling in is reckless-class behavior, and the record says so.
        warned = self._pull_over_warning_level > 0
        self._pull_over = None
        self._reset_pull_over_tracker()
        if kind != "speeding":
            self.ctx.push_state(
                EnforcementStopState(
                    self.ctx,
                    self,
                    title=title,
                    summary=summary,
                    fine=fine,
                    reputation_hit=reputation_hit,
                    signaled=signaled,
                    return_message=return_message,
                    out_of_service=(kind == "hos_out_of_service"),
                    warned=warned,
                    construction_zone=construction_zone,
                    inspection_on_stop=(kind == "weigh_station_bypass"),
                )
            )
            self._commit_resolved_stop()
            return
        self.ctx.push_state(
            TrafficStopState(
                self.ctx,
                self,
                signaled=signaled,
                over=over,
                limit=limit,
                clean_stop=clean_stop,
                warned=warned,
                construction_zone=construction_zone,
            )
        )
        self._commit_resolved_stop()

    def _commit_resolved_stop(self) -> None:
        """Write a settled stop out of the save, the way arming wrote it in.

        _arm_pull_over commits the encounter before a word of it is spoken so
        that nothing can make it never have happened. This is the other half:
        once the ticket is written, the save must stop saying a cruiser is
        sitting behind you. Without it every resume found the stop still armed
        against a parked truck, resolved it on the first frame, and charged
        for it again -- at the repeat-offender rate, so it cost more each
        time (tester log, 2026-08-10).
        """
        profile = self.ctx.profile
        if profile is None or profile.active_trip is None:
            return
        profile.active_trip = self.snapshot()
        self.ctx.save_profile()

    def _pursuit_hold_required_s(self) -> float:
        """How long the run key must be held. A lifetime disqualification is
        the harshest outcome in the game, so it takes twice as long to choose."""
        record = getattr(self.ctx.profile, "driving_record", None)
        second = record is not None and record.major_count >= 1
        return PURSUIT_HOLD_S * (2.0 if second else 1.0)

    def _update_pursuit_optin(self, dt: float) -> None:
        """Running from a stop: an affirmative held choice, never an accident.

        A driver who is complying but disoriented -- holding a steady speed
        while the instruction is still being read out -- must never be able to
        reach a felony. So the tracker running out is a citation and a forced
        stop, and the only road to a pursuit is holding this key after being
        told exactly what it costs.
        """
        if self._enforcement_bypassed():
            return
        keys = pygame.key.get_pressed()
        mods = pygame.key.get_mods()
        holding = keys[pygame.K_x] and bool(mods & pygame.KMOD_SHIFT)
        if not holding:
            if self._pursuit_hold_s > 0.0:
                self._pursuit_hold_s = 0.0
                self.ctx.say_event(
                    "Not running. Brake to a stop on the shoulder.",
                    category=SpeechCategory.CONFIRMATION,
                )
            return
        required = self._pursuit_hold_required_s()
        if self._pursuit_hold_s <= 0.0:
            hint = self.ctx.control_hint("take_exit")
            record = self.ctx.profile.driving_record
            cost = (
                "This is your second major offense: it disqualifies your CDL "
                "for life, and this career will not drive again."
                if record.major_count >= 1
                else "It is a felony, it cancels this load, and it disqualifies "
                "your CDL for a year."
            )
            self.ctx.say_event(
                f"Hold shift {hint} for {required:.0f} seconds to run. {cost} "
                "Let go now to stop instead.",
                interrupt=True,
                category=SpeechCategory.SAFETY,
            )
        self._pursuit_hold_s += dt
        if self._pursuit_hold_s >= required:
            self._pursuit_hold_s = 0.0
            self._evade_pull_over()

    def _fail_to_stop(self) -> None:
        """Never pulled over, but never ran either: troopers force the stop.

        This is where a zeroed compliance tracker and two miles of rolling
        both end. It is expensive and it is a serious violation on the record,
        but it is not a felony -- that has its own deliberate opt-in.
        """
        signaled = self._pull_over_signaled
        self._pull_over = None
        self.trip.pull_over_active = False
        self._end_stop_audio()
        self._reset_pull_over_tracker()
        self._pursuit_hold_s = 0.0
        t = self.truck
        t.brake = 1.0
        t.velocity_mps = 0.0
        t.set_parking_brake()
        # Same reasoning as the ordinary pull-over: boxed in and stopped, the
        # engine keeps running but must read as idle for the whole stop, not
        # whatever rev it was carrying when the troopers closed in.
        self._settle_engine_to_idle()
        self.ctx.audio.play("ui/error")
        self.ctx.push_state(
            EnforcementStopState(
                self.ctx,
                self,
                title="Failure-to-stop stop",
                summary=(
                    "Troopers boxed you in and brought the truck to a stop. "
                    "Failing to pull over promptly for an officer is a serious "
                    "violation, and the citation says so."
                ),
                fine=FAILURE_TO_STOP_CITATION_FINE,
                reputation_hit=hos.HOS_REPUTATION_HIT * 2.0,
                signaled=signaled,
                return_message="Back on the highway. Pull over promptly next time.",
                warned=True,
                construction_zone=self._pull_over_construction_zone,
            )
        )
        self._commit_resolved_stop()

    def _evade_pull_over(self) -> None:
        """The player chose to run and held the key through the warning: spike
        strips end it, logged as a major offense with a heavy fine, reputation
        hit, and load consequences."""
        self._pull_over = None
        self.trip.pull_over_active = False
        self._end_stop_audio()
        self._reset_pull_over_tracker()
        self._pursuit_hold_s = 0.0
        self.ctx.audio.play("events/spike_strip")
        self.ctx.push_state(FelonyStopState(self.ctx, self))
