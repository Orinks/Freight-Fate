# ruff: noqa: F403,F405
from __future__ import annotations

from ..audio_fades import curve as _resolve_curve
from .driving_core import *
from .driving_pacenotes import PACENOTE_MARGIN_MPH
from .driving_rest_states import EnforcementStopState, FelonyStopState, TrafficStopState

LANE_GUIDANCE_DRIFT_START = 0.3
LANE_GUIDANCE_CENTER_MAX = 0.18
LANE_GUIDANCE_PAN = 0.85

# Sustained redline quietly grinds the engine down (Truck._update_temps), so
# the player must hear about it while it is happening, not at the end screen.
# The grace period lets a shift's momentary flare pass unremarked.
OVERREV_GRACE_S = 1.5
OVERREV_REPEAT_S = 10.0

# An automatic shift caps audible engine load so the bed doesn't duck out.
SHIFT_LOAD_CAP = 0.45
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
        self.ctx.audio.play("ui/tick", volume=0.9, pan=pan)
        self.ctx.say_event(self._pacenote_text(curve, ahead, speed), interrupt=True)

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
        self._sync_weather_source()
        keys = pygame.key.get_pressed()
        ramp = dt * 2.2
        self._brake_lockout_cue_timer = max(0.0, self._brake_lockout_cue_timer - dt)
        self._lane_rumble_timer = max(0.0, self._lane_rumble_timer - dt)
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
        key_up, key_down = self._update_pedal_latches(
            key_up, key_down, pad_throttle, pad_brake, keys[pygame.K_b], dt
        )
        accelerating = key_up or pad_throttle > 0.05
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
        if key_up and not backing and not t.transmission.in_reverse:
            if t.engine_brake:
                t.engine_brake = False
                self.ctx.say_event("Engine brake off.", interrupt=False)
            t.throttle = min(1.0, t.throttle + ramp)
        elif backing:
            t.throttle = min(0.45, t.throttle + ramp)
        else:
            t.throttle = max(0.0, t.throttle - ramp * 2)
        if pad_throttle > 0.05 and not backing and not t.transmission.in_reverse:
            if t.engine_brake:
                t.engine_brake = False
                self.ctx.say_event("Engine brake off.", interrupt=False)
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
        emergency = keys[pygame.K_b]
        # A real truck drops cruise at the first tap of the service brake.
        # Only the player's own pedal cancels here; the sim's automatic brake
        # ramps (reverse arrest, hazard events) go through their own cancels.
        if self._cruise_mph is not None and (braking_key or emergency) and not backing:
            self._cancel_cruise()
            self.ctx.say_event("Cruise off.", interrupt=False)
        if emergency:
            # no ramp: slams to full application instantly, plus spring brakes
            if not t.emergency_brake and abs(t.velocity_mps) > 1:
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
        # Air hiss only on the rising edge of applying the brake. A hysteresis
        # flag (arm at 0.05, release below 0.02) keeps a steady analog trigger --
        # or a held key -- from retriggering the sound frame after frame. The
        # emergency brake plays its own louder cue, so it only arms the flag.
        if t.brake >= 0.05:
            if not self._brake_air_hissed and not emergency and abs(t.velocity_mps) > 1:
                self.ctx.audio.play("vehicle/brake_air", volume=0.6)
            self._brake_air_hissed = True
        elif t.brake < 0.02:
            self._brake_air_hissed = False
        desired_automatic = self.ctx.settings.automatic_transmission
        if t.transmission.automatic != desired_automatic:
            t.transmission.automatic = desired_automatic
            mode = "automatic" if desired_automatic else "manual"
            self.ctx.say_event(f"Transmission changed to {mode}.", interrupt=True)

        clutch_pressed = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        clutch_val = 1.0 if clutch_pressed else 0.0
        if pad_on:
            clutch_val = max(clutch_val, pad.clutch)
        t.transmission.clutch = clutch_val if not t.transmission.automatic else 0.0
        clutch_disengaged = t.transmission.clutch > 0.5 or t.transmission.shifting
        self._update_lane(keys, dt)
        self._update_exit_preparation(keys, dt)
        self._resume_speed_control_if_ready(braking=braking)
        self._update_cruise(dt, braking, accelerating, clutch_disengaged)
        self._update_keeper(dt, braking, accelerating, clutch_disengaged)

        if t.transmission.automatic and t.engine_on:
            new_gear = t.auto_shift()
            if new_gear is not None:
                self.ctx.audio.play("vehicle/gear_shift", volume=0.65)

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
        for event in self.trip.update(dt):
            self._handle_trip_event(event)
        self._check_weigh_station_enforcement(pos_before)
        self._check_unsafe_damage_enforcement()
        self._check_destination_exit()
        self._update_exit(self.trip.position_mi - pos_before)

        self._update_hours_and_fatigue(dt)
        self._update_audio(dt)
        self._update_announcements(dt)
        self._update_ambient_events(dt)
        self._update_ramp_light(dt)
        self._update_critical_respeak(dt)
        self._update_hazard(dt)
        self._update_microsleep(keys, dt)
        self._update_overrev(dt)
        self._update_speeding(dt, accelerator_held=accel_held)
        self._update_pull_over(dt)
        self._update_brake_heat_cue(dt)
        self._update_traction_cues()
        self._update_chain_law()
        if self.tutorial:
            self.tutorial.update(dt, t)
        if self.trip.finished:
            if self._departure_chain:
                # End of the origin's streets: merge onto the highway trip.
                self._finish_departure_chain()
            elif self.phase == DRIVE_PHASE_PICKUP:
                self._handle_pickup_gate()
            elif self.phase == DRIVE_PHASE_CITY_SERVICE:
                self._handle_city_service_gate()
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
        if not t.engine_on:
            self._set_status("Start the engine before releasing the brakes.")
            message = (
                "Engine off."
                if self._terse_speech()
                else "Start the engine first; air pressure cannot build with the engine off."
            )
            self.ctx.say_event(message, interrupt=False)
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
            self.ctx.say_event(message, interrupt=False)
        elif t.parking_brake:
            brake_hint = self.ctx.control_hint("parking_brake")
            self._set_status(f"Parking brake set. Press {brake_hint} to release it.")
            message = (
                "Parking brake set."
                if self._terse_speech()
                else f"Parking brake set. Press {brake_hint} to release it."
            )
            self.ctx.say_event(message, interrupt=False)

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

        if (
            t.air_low_warning
            and t.engine_on
            and (not was_low or not self._low_air_said or not was_engine_on)
        ):
            self._low_air_said = True
            self.ctx.audio.play("vehicle/low_air_buzzer", volume=0.7)
            self.ctx.controller.rumble.alert()
            message = (
                f"Low air: {t.air_pressure_psi:.0f} psi."
                if self._terse_speech()
                else (
                    f"Low air warning: {t.air_pressure_psi:.0f} psi. "
                    "Keep the parking brake set until pressure builds."
                )
            )
            self.ctx.say_event(message, interrupt=True)
        elif not t.air_low_warning:
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
            self.ctx.say_event(message, interrupt=True)
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
            self.ctx.say_event(message, interrupt=False)
            self.ctx.award_achievement("air_ready", event=True)
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
                self.ctx.audio.play("vehicle/gear_shift", volume=0.55)
                if want == "forward":
                    tr.gear = 1
                    self._set_status("Forward gear selected.")
                    self.ctx.say_event("Forward gear selected.", interrupt=False)
                    return False
                tr.gear = REVERSE
                self._cancel_cruise()
                self._set_status("Reverse selected. Backing slowly.")
                self.ctx.say_event("Reverse selected. Backing slowly.", interrupt=False)
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
                self.ctx.say_event(message, interrupt=hos.warning_is_urgent(message))
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
            self.ctx.say_event(text, interrupt=False)
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
            )
        elif fatigue >= hos.FATIGUE_DROWSY and not self._drowsy_said and alerts_clear:
            self._drowsy_said = True
            self._fatigue_cue_gm = 0.0
            self.ctx.audio.play("driver/yawn", volume=0.9)
            self.ctx.say_event(
                "You are getting drowsy. Take a break or sleep at a rest stop.", interrupt=False
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
        mode = self.ctx.settings.steering_assist
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
        # The trip's own route: after a surface chain swap the active trip
        # drives the street legs, not the highway legs.
        leg = self.trip.route.legs[self.trip.current_leg_index]
        # The exit ramp is a single lane; the mainline keeps its leg count.
        self.lane.set_lane_count(1 if self._ramp_mi is not None else leg_lane_count(leg))
        # Use the real baked curve data when the truck is inside a curve.
        # The curve force pushes the lane offset outward proportionally to
        # how much the truck's speed exceeds the advisory speed, scaled by
        # load, grip, and the curve's tightness.
        active = self.trip.curve_at(self.trip.position_mi)
        if active is not None and not active.connector:
            excess = max(0.0, self.truck.speed_mph - active.advisory_mph)
            tightness = max(0.2, 1.0 - active.min_radius_ft / 5000.0)
            # Curve push: full CURVE_RATE at advisory, ramping with excess.
            # A heavier load pushes harder (more inertia to pull wide);
            # worn or icy grip means less lateral resistance.
            load = min(1.5, self.truck.gross_mass_kg / self.truck.specs.mass_kg)
            grip_factor = min(1.0, self.truck.effective_grip)
            curve_push = (
                CURVE_RATE * tightness * (1.0 + excess * 0.05) * load / max(0.2, grip_factor)
            )
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
                )
        else:
            curve = 0.0
        if self._ramp_mi is not None:
            curve += 0.35
        if active is None and self._curve_slip_active:
            self._curve_slip_active = False
        # Curve speed assist: use the real advisory speed when one is active
        # instead of the old terrain heuristic.
        curve_assisting = False
        if self.ctx.settings.curve_speed_assist:
            if active is not None and not active.connector:
                # Approaching or inside a curve and going faster than advisory + margin
                curve_assisting = self.truck.speed_mph > active.advisory_mph + 5
            elif curve != 0.0:
                # Fallback: old terrain- or ramp-based heuristic
                curve_assisting = self.truck.speed_mph > 50 - abs(curve) * 20
        if curve_assisting:
            self.truck.brake = max(self.truck.brake, min(0.35, abs(curve)))
            if not self._curve_assist_active:
                self.ctx.say_event("Curve speed assistance slowing.", interrupt=False)
        elif self._curve_assist_active:
            self.ctx.say_event("Curve speed assistance released.", interrupt=False)
        self._curve_assist_active = curve_assisting
        transition_assisting = (
            self.ctx.settings.route_transition_assist
            and self._ramp_mi is not None
            and self.truck.speed_mph > RAMP_MAX_MPH
        )
        if transition_assisting:
            self.truck.brake = max(self.truck.brake, 0.4)
            if not self._transition_assist_active:
                self.ctx.say_event("Route-transition assistance slowing.", interrupt=False)
        elif self._transition_assist_active:
            self.ctx.say_event("Route-transition assistance released.", interrupt=False)
        self._transition_assist_active = transition_assisting
        wind = self.weather.effects.wind
        if self.lane.update(dt, self.truck.velocity_mps, curve=curve, wind=wind, assist=mode):
            if not self.ctx.settings.lane_departure_warning:
                return
            self.ctx.audio.play("vehicle/rumble_strip", volume=1.0, pan=self._lane_pan())
            self.truck.damage_pct = min(100.0, self.truck.damage_pct + 1.0)
            message = self.lane.describe()
            if not self._terse_speech():
                message += " Steer back toward the lane center."
            self.ctx.say_event(message, interrupt=True)
        if self.lane.crossed:
            # A held drift carried the truck across the line: the wheel was
            # the lane change. One signal click marks the commit.
            pan = -0.6 if self.lane.crossed > 0 else 0.6
            self.ctx.audio.play("vehicle/turn_signal", volume=0.6, pan=pan)
            self._finish_lane_change()
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
            self.ctx.audio.play("vehicle/turn_signal", volume=0.8, pan=pan)
        self._lane_change_timer -= dt
        if self._lane_change_timer <= 0:
            self._lane_change_target = None
            self.lane.lane = min(target, self.lane.lane_count - 1)
            self._finish_lane_change()

    def _finish_lane_change(self) -> None:
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
            self.ctx.audio.play("vehicle/collision")
            self.ctx.controller.rumble.impact(SIDESWIPE_DAMAGE)
            self.truck.apply_collision(SIDESWIPE_DAMAGE)
            self.ctx.say_event(
                f"You sideswiped a {other.vehicle_class} in the {lane.lane_name} "
                f"lane! The truck took damage, now {self.truck.damage_pct:.0f} "
                "percent. Check your mirrors before moving over.",
                interrupt=True,
            )
            return
        if (
            self._hazard_deadline is not None
            and self._hazard_dodgeable
            and lane.lane != self._hazard_lane
        ):
            self._hazard_deadline = None
            self.ctx.audio.play("events/hazard_clear", volume=0.75)
            self.ctx.controller.rumble.alert(intensity=0.4)
            self.ctx.say_event("You swerve around it. Well done.", interrupt=False)
            self.ctx.award_achievement("hazard_avoided", event=True)
            return
        self.ctx.say_event(f"In the {lane.lane_name} lane.", interrupt=False)

    def _update_merge(self, dt: float) -> None:
        """Riding a coned-off lane: one urgent warning, then the barrels win."""
        zone = self.trip.active_zone
        closed = zone.closed_lane if zone is not None and zone.reason == "construction" else None
        if closed is None or self.lane.lane != closed or self.truck.speed_mph < LANE_MIN_MPH:
            self._merge_deadline = None
            return
        open_lane = closed - 1 if closed > 0 else closed + 1
        open_name = lane_label(open_lane, self.lane.lane_count)
        if self._merge_deadline is None:
            self._merge_deadline = MERGE_WINDOW_S
            self.ctx.audio.play("ui/warning")
            self.ctx.controller.rumble.alert()
            self.ctx.say_event(
                f"You are in the closed {lane_label(closed, self.lane.lane_count)} "
                f"lane! Move to the {open_name} lane!",
                interrupt=True,
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
            )

    def _keep_right_justified(self) -> bool:
        """Left-lane time is legitimate while passing slower right-lane
        traffic, or while construction has the right lane coned off."""
        zone = self.trip.active_zone
        if zone is not None and zone.closed_lane == 0:
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

    def _lane_guidance_zone(self) -> str:
        offset = self.lane.offset
        if offset <= -LANE_GUIDANCE_DRIFT_START:
            return "left"
        if offset >= LANE_GUIDANCE_DRIFT_START:
            return "right"
        if abs(offset) <= LANE_GUIDANCE_CENTER_MAX:
            return "center"
        if self._lane_guidance_state in {"left", "right"}:
            return self._lane_guidance_state
        return "center"

    def _update_lane_guidance_audio(self) -> None:
        if not self.ctx.settings.lane_departure_warning:
            self._lane_guidance_state = "center"
            return
        zone = self._lane_guidance_zone()
        previous = self._lane_guidance_state
        if zone == previous:
            return
        self._lane_guidance_state = zone
        if zone == "left":
            self.ctx.audio.play("vehicle/lane_drift", volume=0.45, pan=-LANE_GUIDANCE_PAN)
        elif zone == "right":
            self.ctx.audio.play("vehicle/lane_drift", volume=0.45, pan=LANE_GUIDANCE_PAN)
        elif previous in {"left", "right"}:
            self.ctx.audio.play("vehicle/lane_centered", volume=0.45, pan=0.0)

    def _update_audio(self, dt: float = 0.0) -> None:
        t = self.truck
        audio = self.ctx.audio
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
        if t.transmission.automatic and t.transmission.shifting:
            self._shift_recover_t = 0.0
            cap = SHIFT_LOAD_CAP
        elif self._shift_recover_t < 1.0:
            step = dt / SHIFT_LOAD_RECOVERY_S if SHIFT_LOAD_RECOVERY_S > 0 else 1.0
            self._shift_recover_t = min(1.0, self._shift_recover_t + step)
            cap = SHIFT_LOAD_CAP + (1.0 - SHIFT_LOAD_CAP) * _shift_recovery_curve(
                self._shift_recover_t
            )
        else:
            cap = 1.0
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
        if t.engine_on and t.transmission.in_reverse:
            if not self._reverse_cue_active:
                audio.reverse_start()
                self._reverse_cue_active = True
        elif self._reverse_cue_active:
            audio.reverse_stop()
            self._reverse_cue_active = False
        eff = self.weather.effects
        audio.set_weather(eff.sound)
        audio.set_wind(eff.wind)
        self._update_lane_guidance_audio()
        rumble = self.lane.rumble_level()
        if (
            rumble > 0.0
            and self.ctx.settings.steering_assist != "off"
            and self._lane_rumble_timer <= 0.0
        ):
            self._lane_rumble_timer = 0.8
            audio.play("vehicle/rumble_strip", volume=0.25 + rumble * 0.45, pan=self._lane_pan())
        if rumble > 0.0 and self.ctx.settings.steering_assist != "off":
            # Harsh, continuous pad buzz while over the rumble strip; refreshed
            # each frame, it stops on its own once steered back off.
            self.ctx.controller.rumble.rumble_strip(rumble)
        night = is_night(self.trip.local_hour)
        if night:
            audio.set_ambient("ambient/night")
        else:
            audio.set_ambient(None)
        if self.radio.enabled:
            self._update_radio_reception(dt)
            self._update_radio_playback(night, dt)
        if self.weather.should_thunder():
            audio.play("weather/thunder")

    # -- radio reception and station rotation --------------------------------------

    def tick_covered_music(self, dt: float) -> None:
        """Keep the radio spinning while a menu covers the drive.

        A paused rig is still a cab with the radio on: the station keeps
        rotating songs and host breaks under the pause menu instead of going
        silent when the current bed runs out. Day/night flavor stays as it
        was when the menu opened; it catches up when driving resumes."""
        if self.radio.enabled:
            self._update_radio_playback(self._music_night, dt)

    def _update_radio_reception(self, dt: float) -> None:
        """Fade ranged stations with distance and retune when they drop out."""
        self._radio_signal_timer -= max(0.0, dt)
        if self._radio_signal_timer > 0.0:
            return
        self._radio_signal_timer = 1.5
        before = self.radio.current_station()
        self.radio.update_position(
            truck_position(self.route, self.trip.position_mi, self.ctx.world)
        )
        reception = self.radio.current_reception()
        if reception.station.id != before.id:
            # the tuned station fell past its range contour mid-drive
            self.ctx.audio.play("radio/static_burst", volume=0.5)
            action = self.radio.select_station(SAFE_ROUTE_PLAYLIST, self._radio_backend)
            self.radio.write_settings(self.ctx.settings)
            self.ctx.settings.save()
            self.ctx.say_event(
                f"{before.display_name} faded out of range. "
                f"Falling back to {action.station.display_name}.",
                interrupt=False,
            )
            return
        self._radio_signal_factor = signal_volume_factor(reception)
        self._apply_radio_volume()
        signal = reception.signal
        if 0.0 < signal < STATIC_SIGNAL_THRESHOLD and not reception.station.always_available:
            self._radio_static_timer -= 1.5
            if self._radio_static_timer <= 0.0:
                self._radio_static_timer = 6.0
                self.ctx.audio.play(
                    "radio/static_burst",
                    volume=0.08 + (STATIC_SIGNAL_THRESHOLD - signal) * 0.6,
                )

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
        self._radio_hosts = select_host_segments(station.host, f"{self.trip_seed}|{station.id}")
        self._radio_track_index = 0
        self._radio_host_index = 0
        self._radio_elapsed_s = 0.0
        self._radio_tracks_since_host = 0
        self._radio_playing_host = False
        if self._radio_playlist:
            self.ctx.audio.play_music(self._radio_playlist[0], fade_ms=fade_ms)

    def _update_radio_playback(self, night: bool, dt: float) -> None:
        station = self.radio.current_station()
        if station.real_stream or station.fallback:
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
        if self._radio_playing_host and self._radio_hosts:
            current = self._radio_hosts[self._radio_host_index % len(self._radio_hosts)]
        else:
            current = self._radio_playlist[self._radio_track_index % len(self._radio_playlist)]
        if self._radio_elapsed_s < music_track_duration_s(current):
            return
        self._radio_elapsed_s = 0.0
        if self._radio_playing_host:
            self._radio_playing_host = False
            self._radio_host_index += 1
            self._play_station_track(fade_ms=1200)
            return
        self._radio_track_index += 1
        self._radio_tracks_since_host += 1
        if self._radio_hosts and self._radio_tracks_since_host >= RADIO_TRACKS_PER_HOST_BREAK:
            self._radio_playing_host = True
            self._radio_tracks_since_host = 0
            key = self._radio_hosts[self._radio_host_index % len(self._radio_hosts)]
            self.ctx.audio.play_music(key, fade_ms=600)
            return
        self._play_station_track(fade_ms=2500)

    def _play_station_track(self, fade_ms: int) -> None:
        key = self._radio_playlist[self._radio_track_index % len(self._radio_playlist)]
        self.ctx.audio.play_music(key, fade_ms=fade_ms)

    def _sync_radio_settings(self) -> None:
        station_before = self.radio.station_id
        self.radio.apply_settings(self.ctx.settings)
        self.radio.update_position(
            truck_position(self.route, self.trip.position_mi, self.ctx.world)
        )
        self.radio.current_station()
        if self.radio.station_id != station_before:
            self.radio.write_settings(self.ctx.settings)
            self.ctx.settings.save()

    def _apply_radio_volume(self) -> None:
        factor = getattr(self, "_radio_signal_factor", 1.0)
        self.ctx.audio.set_volumes(music=self.ctx.settings.radio_volume * factor)

    def _play_radio_current(self) -> None:
        self._sync_radio_settings()
        if self.radio.enabled:
            self._apply_radio_volume()
            self.radio.play(self._radio_backend)
        else:
            self.ctx.audio.stop_music(600)

    def _finish_radio_action(self, action) -> None:
        self.radio.write_settings(self.ctx.settings)
        self.ctx.settings.save()
        self.ctx.say(action.message)

    def _toggle_radio(self) -> None:
        self._sync_radio_settings()
        action = self.radio.toggle(self._radio_backend)
        self._finish_radio_action(action)

    def _tune_radio(self, direction: int) -> None:
        self._sync_radio_settings()
        action = self.radio.tune(direction, self._radio_backend)
        self._finish_radio_action(action)

    def _speak_radio_status(self) -> None:
        self._sync_radio_settings()
        self.ctx.say(self.radio.status_text())

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
        if self.ctx.settings.speech_verbosity == 0:
            return
        self._speed_announce_timer += dt
        base_interval = tuning_for_time_scale(self.trip.time_scale).routine_speech_interval_s
        interval = base_interval if self.ctx.settings.speech_verbosity == 1 else 7.0
        if self._speed_announce_timer >= interval:
            self._speed_announce_timer = 0.0
            mph = self.truck.speed_mph
            if abs(mph - self._last_announced_mph) >= 5 and mph > 1:
                self._last_announced_mph = mph
                self.ctx.say_event(self.ctx.settings.speed_text(mph), interrupt=False)

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

    def _hazard_target_mph(self) -> float:
        """The speed that resolves the active hazard by brake alone.

        A fixed object in your lane (dodgeable) cannot be rolled over at the
        moving-hazard safe speed: it takes nearly a stop, then easing around.
        """
        return HAZARD_CREEP_MPH if self._hazard_dodgeable else HAZARD_SAFE_MPH

    def _update_hazard(self, dt: float) -> None:
        if self._hazard_deadline is None:
            return
        target = self._hazard_target_mph()
        if self.truck.speed_mph <= target:
            self._hazard_deadline = None
            self._automatic_braking_announced = False
            self._hazard_slow_hint_said = False
            self.ctx.audio.play("events/hazard_clear", volume=0.75)
            self.ctx.controller.rumble.alert(intensity=0.4)
            message = (
                "You slow nearly to a stop and ease around it. Well done."
                if self._hazard_dodgeable
                else "Hazard avoided. Well done."
            )
            self.ctx.say_event(message, interrupt=False)
            self.ctx.award_achievement("hazard_avoided", event=True)
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
            self.ctx.say_event(
                "It is still in your lane. Nearly stop, or change lanes.",
                interrupt=False,
            )
        self._hazard_deadline -= dt
        # The assist leads the budget: braking heats the brakes, so the stop
        # the budget just predicted gets slower while it happens. Engaging at
        # zero margin collided two seconds after "Emergency braking engaged."
        if (
            self.ctx.settings.automatic_emergency_braking
            and self._hazard_deadline
            <= self._brake_budget_s(target) * AEB_BUDGET_MARGIN + AEB_LEAD_S
        ):
            self.truck.brake = max(self.truck.brake, 1.0)
            if not self._automatic_braking_announced:
                self._automatic_braking_announced = True
                self.ctx.say_event("Emergency braking engaged.", interrupt=True)
            if self._cruise_mph is not None:
                self._cancel_cruise()
        if self._hazard_deadline <= 0:
            self._hazard_deadline = None
            self._automatic_braking_announced = False
            self.ctx.audio.play("vehicle/collision")
            severity = min(1.0, self.truck.speed_mph / 70.0)
            severity *= tuning_for_time_scale(self.trip.time_scale).collision_damage
            self.ctx.controller.rumble.impact(severity)
            self.truck.apply_collision(severity)
            self.ctx.say_event(
                f"Collision! The truck took damage. "
                f"Total damage {self.truck.damage_pct:.0f} percent.",
                interrupt=True,
            )

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
        self.ctx.say_event("You are nodding off. Steer or brake now to stay awake!", interrupt=True)

    def _update_microsleep(self, keys, dt: float) -> None:
        if self._microsleep_deadline is None:
            return
        # Already crawling: the nod passes without leaving the road.
        if self.truck.speed_mph <= HAZARD_SAFE_MPH:
            self._resolve_microsleep(silent=True)
            return
        reacted = (
            keys[pygame.K_LEFT] or keys[pygame.K_RIGHT] or keys[pygame.K_DOWN] or keys[pygame.K_b]
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
                "You caught it. Pull over and sleep before the next one.", interrupt=False
            )

    def _microsleep_drift_off_road(self) -> None:
        self._microsleep_misses += 1
        self._microsleep_cooldown_gm = MICROSLEEP_COOLDOWN_GM
        t = self.truck
        self.ctx.audio.play("vehicle/rumble_strip", volume=1.0)
        t.damage_pct = min(100.0, t.damage_pct + MICROSLEEP_SHOULDER_DAMAGE_PCT)
        t.velocity_mps *= 0.8  # wandering onto the shoulder scrubs speed
        if self._microsleep_misses >= MICROSLEEP_FORCE_STOP_MISSES:
            self._microsleep_misses = 0
            t.throttle = 0.0
            t.brake = 1.0
            self.ctx.audio.play("vehicle/tire_screech", volume=0.9)
            self.ctx.say_event(
                "You cannot stay awake. You drift onto the shoulder and jolt "
                "awake on the brakes. Stop and sleep before you wreck.",
                interrupt=True,
            )
        else:
            self.ctx.say_event(
                f"You nodded off and drifted onto the rumble strip. The truck "
                f"took damage, now {t.damage_pct:.0f} percent. Pull over and "
                "sleep.",
                interrupt=True,
            )

    def _update_overrev(self, dt: float) -> None:
        t = self.truck
        if not t.over_revving:
            self._overrev_s = 0.0
            self._overrev_warn_due = OVERREV_GRACE_S
            return
        self._overrev_s += dt
        if self._overrev_s < self._overrev_warn_due:
            return
        self._overrev_warn_due = self._overrev_s + OVERREV_REPEAT_S
        self.ctx.audio.play("ui/warning")
        self.ctx.controller.rumble.alert()
        message = (
            f"Redline. Damage {t.damage_pct:.0f} percent."
            if self._terse_speech()
            else (
                "The engine is screaming at redline and taking damage, now "
                f"{t.damage_pct:.0f} percent. Ease off and slow down."
            )
        )
        self.ctx.say_event(message, interrupt=True)

    def _update_speeding(self, dt: float, *, accelerator_held: bool = False) -> None:
        if self._ramp_mi is not None:
            return  # the ramp is off the highway and unpatrolled
        if self._missed_destination_exit_said and not self._destination_exit_taken:
            return  # recovery state: guide the player back to the missed exit
        if self._pull_over is not None:
            return  # already being pulled over; don't pile on strikes
        limit, _ = self.trip.speed_limit_at(self.trip.position_mi)
        self._update_overspeed_warning(dt, limit)
        # A dropped limit earns braking time before strikes accrue: real
        # enforcement tickets sustained disregard, not the transition, and a
        # loaded truck cannot shed 15 mph the instant a sign changes. About
        # 2 mph per second of comfortable braking sets the window, capped so
        # the grace cannot be used to coast through a whole restricted zone.
        if self._enforced_limit_prev is not None and limit < self._enforced_limit_prev:
            grace = (self.truck.speed_mph - limit) / 2.0
            self._limit_drop_grace_s = max(self._limit_drop_grace_s, min(15.0, grace))
        self._enforced_limit_prev = limit
        if self._limit_drop_grace_s > 0.0:
            self._limit_drop_grace_s = max(0.0, self._limit_drop_grace_s - dt)
            # Staying on the throttle through the drop is disregard, not
            # compliance: the grace collapses and the clock runs. Read the
            # current key/trigger position, not the smoothed truck throttle,
            # which is still ramping down just after the driver lifts off.
            if accelerator_held:
                self._limit_drop_grace_s = 0.0
            else:
                self._speeding_timer = 0.0
                return
        if self.truck.speed_mph > limit + SPEEDING_LEEWAY_MPH:
            if (
                self._cruise_mph is not None
                and self._acc_limit_capped
                and self.truck.brake > 0.0
                and self.truck.throttle <= 0.05
            ):
                self._speeding_timer = 0.0
                return
            self._speeding_timer += dt
            if self._speeding_timer > SPEEDING_HOLD_S:
                self._speeding_timer = 0.0
                # Caught by a patrol -> an immediate pull-over and ticket. Not
                # caught -> the silent at-delivery strike (the safety/insurance
                # cost of speeding nobody saw). Never both for one instance.
                if self._trooper_catches_speeder(limit):
                    self._begin_pull_over(limit)
                    return
                before = _speeding_settlement_fine(self.speeding_strikes)
                self.speeding_strikes += 1
                after = _speeding_settlement_fine(self.speeding_strikes)
                self.ctx.audio.play("ui/warning")
                self.ctx.controller.rumble.alert()
                # Surface the cost the moment the strike lands instead of only as a
                # silent deduction at delivery, so the price of speeding is felt now.
                if after > before:
                    self.ctx.say_event(
                        "Speeding strike. The limit is "
                        f"{self.ctx.settings.speed_text(limit)}. Speeding "
                        f"fines now total {after:,.0f} dollars, due at delivery.",
                        interrupt=True,
                    )
                else:
                    self.ctx.say_event(
                        "Speeding strike. The limit is "
                        f"{self.ctx.settings.speed_text(limit)}. Your speeding "
                        f"fines are already at the {after:,.0f}-dollar maximum.",
                        interrupt=True,
                    )
        else:
            self._speeding_timer = 0.0

    def _update_overspeed_warning(self, dt: float, limit: float) -> None:
        """The dash overspeed alert: speak once, then chime until compliant.

        Arms a few mph over the limit -- inside the enforcement leeway, so an
        attentive driver hears the dash before any strike clock matters. The
        first trigger speaks the limit; while the truck stays over, the chime
        repeats on its interval. Actively braking down quiets the nag (the
        driver is already complying), and settling back under the limit
        disarms it for the next episode.
        """
        mode = getattr(self.ctx.settings, "overspeed_warning", "on")
        if mode == "off" or mode is False:
            self._overspeed_active = False
            return
        urgent_only = mode == "urgent only"
        speed = self.truck.speed_mph
        # In urgent-only mode the alert arms only at runaway overspeed, and
        # disarms once the runaway is contained -- deliberate fast cruising
        # below the urgent line stays unjudged, exactly as requested.
        arm_over = OVERSPEED_URGENT_MPH if urgent_only else OVERSPEED_WARN_MPH
        reset_over = (OVERSPEED_URGENT_MPH - 2.0) if urgent_only else OVERSPEED_RESET_MPH
        if self._overspeed_active:
            if speed <= limit + reset_over:
                self._overspeed_active = False
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
            return
        if speed > limit + arm_over:
            self._overspeed_active = True
            self._overspeed_chime_timer = 0.0
            self.ctx.audio.play("vehicle/overspeed_chime", volume=0.65)
            self.ctx.say_event(
                f"Watch your speed. The limit is {self.ctx.settings.speed_text(limit)}.",
                interrupt=False,
            )

    def _trooper_catches_speeder(self, limit: float) -> bool:
        """Whether a patrol clocks this speeding strike, by patrol intensity."""
        if self.ctx.settings.hos_mode in hos.HOS_NON_ENFORCED_MODES:
            return False  # enforcement is bypassed in the debug mode
        patrol = self.trip.active_patrol_at(self.trip.position_mi)
        if patrol is None:
            return False
        return self._patrol_rng.random() < patrol.intensity

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
        self._pull_over_warning_level = 0
        patrol = self.trip.active_patrol_at(self.trip.position_mi)
        where = patrol.reason if patrol is not None else "patrol"
        self.ctx.audio.play("events/police_siren")
        self.ctx.controller.rumble.alert()
        self.ctx.say_event(
            f"Lights and siren behind you. A trooper on this {where} clocked you "
            f"at {self.ctx.settings.speed_text(self.truck.speed_mph)} in a "
            f"{self.ctx.settings.speed_text(limit)} zone. Signal with X and "
            "brake to a stop on the shoulder.",
            interrupt=True,
        )

    def _enforcement_bypassed(self) -> bool:
        return self.ctx.settings.hos_mode in hos.HOS_NON_ENFORCED_MODES

    def _weigh_station_key(self, stop) -> str:
        return f"weigh:{stop.name}:{stop.at_mi:.1f}"

    def _check_weigh_station_enforcement(self, previous_mi: float) -> None:
        if self._enforcement_bypassed() or self._pull_over is not None or self._ramp_mi is not None:
            return
        for stop in self.trip.stops:
            if stop.type != "weigh_station":
                continue
            ahead = stop.at_mi - self.trip.position_mi
            key = self._weigh_station_key(stop)
            if 0 < ahead <= WEIGH_STATION_NOTICE_MI and key != self._weigh_station_notice_key:
                self._weigh_station_notice_key = key
                self.ctx.audio.play("events/inspection_warning", volume=0.7)
                self.ctx.say_event(
                    f"Open weigh station ahead in {self.ctx.settings.distance_text(ahead)}: "
                    f"{stop.spoken_name}. Slow below {WEIGH_STATION_BYPASS_MPH:.0f} "
                    "and press T for inspection check-in.",
                    interrupt=False,
                )
            if key in self.enforcement_events:
                continue
            crossed = previous_mi < stop.at_mi <= self.trip.position_mi
            if crossed and self.truck.speed_mph > WEIGH_STATION_BYPASS_MPH:
                self.enforcement_events.add(key)
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
                        "signal with X and brake to a stop on the shoulder."
                    ),
                )

    def _check_unsafe_damage_enforcement(self) -> None:
        if self._enforcement_bypassed() or self._pull_over is not None or self._ramp_mi is not None:
            return
        if (
            self.truck.damage_pct < UNSAFE_DAMAGE_STOP_PCT
            or self.truck.speed_mph <= DOCKING_MAX_MPH
        ):
            return
        patrol = self.trip.active_patrol_at(self.trip.position_mi)
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
                "with X and brake to a stop on the shoulder."
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
        self._pull_over_warning_level = 0
        self.ctx.audio.play("events/police_siren")
        self.ctx.say_event(lights_message, interrupt=True)

    def _signal_pull_over(self) -> None:
        """X during a pull-over: signal and ease over (better demeanor)."""
        if self._pull_over == "lights":
            self._pull_over = "stopping"
            self._pull_over_signaled = True
            self.ctx.audio.play("vehicle/turn_signal", volume=0.7)
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
            self.ctx.say_event("Hydroplaning. The steering has gone light; ease off the speed.")
        self._hydro_active = planing
        slipping = t.jake_slipping and t.speed_mph > 5.0
        if slipping and not self._jake_slip_active:
            self.ctx.say_event(
                "The drive wheels are sliding under the engine brake. Ease off the jake."
            )
        self._jake_slip_active = slipping
        if t.chains_just_snapped:
            t.chains_just_snapped = False
            self.ctx.say_event(
                "A tire chain let go and hammered the fender on its way off. "
                "The set is scrap; you are running on rubber again."
            )
        chains_fast = t.chains_on and t.speed_mph > CHAIN_SAFE_MPH + 2.0
        if chains_fast and not self._chains_fast_active:
            self.ctx.say_event(
                "The chains are hammering the pavement at this speed. "
                f"Keep it under {CHAIN_SAFE_MPH:.0f} or they will not last."
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
                "Stop and chain up, or hope the checkpoint is unstaffed."
            )
        start, end = self.trip.chain_law_areas[area]
        if self.trip.position_mi < (start + end) / 2.0 or key in self._chain_law_cited:
            return
        self._chain_law_cited.add(key)
        roll = random.Random(f"{self.trip_seed}:chain-law:{area}:{level}").random()
        if roll >= CHAIN_LAW_CHECKPOINT_CHANCE:
            return
        p = self.ctx.profile
        p.money -= CHAIN_LAW_FINE
        self.ticket_fines_paid += CHAIN_LAW_FINE
        self.ctx.audio.play("ui/error")
        self.ctx.say_event(
            "Chain checkpoint. An officer waves you onto the scale apron and "
            f"writes a chain-law citation: {CHAIN_LAW_FINE:,.0f} dollars. "
            f"You have {p.money:,.0f} dollars."
        )

    def _update_pull_over(self, dt: float) -> None:
        if self._pull_over is None:
            return
        if self._enforcement_bypassed():
            self._pull_over = None
            return
        if self.truck.speed_mph <= DOCKING_MAX_MPH:
            self._open_traffic_stop()
            return
        distance = self.trip.position_mi - self._pull_over_start_mi
        if distance >= PULL_OVER_IGNORE_MI:
            self._evade_pull_over()
        elif distance >= FAILURE_TO_STOP_FINAL_WARNING_MI:
            self._warn_failure_to_stop(final=True)
        elif distance >= FAILURE_TO_STOP_WARNING_MI:
            self._warn_failure_to_stop(final=False)

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
                "Failure-to-stop warning. Signal with X and brake to a full stop on the shoulder."
            )
        self.ctx.audio.play("ui/warning")
        self.ctx.say_event(message, interrupt=True)

    def _open_traffic_stop(self) -> None:
        signaled = self._pull_over_signaled
        over, limit = self._pull_over_over, self._pull_over_limit
        kind = self._pull_over_kind
        title = self._pull_over_title
        summary = self._pull_over_summary
        fine = self._pull_over_fine
        reputation_hit = self._pull_over_reputation_hit
        return_message = self._pull_over_return
        self._pull_over = None
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
                )
            )
            return
        self.ctx.push_state(
            TrafficStopState(self.ctx, self, signaled=signaled, over=over, limit=limit)
        )

    def _evade_pull_over(self) -> None:
        """Drove on with the lights behind: spike strips end it, logged as a
        felony stop with a heavy fine, reputation hit, and load consequences."""
        self._pull_over = None
        self.ctx.audio.play("events/spike_strip")
        self.ctx.push_state(FelonyStopState(self.ctx, self))
