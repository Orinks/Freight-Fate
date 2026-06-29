# ruff: noqa: F403,F405
from __future__ import annotations

from .driving_core import *
from .driving_rest_states import TrafficStopState


class DrivingUpdateMixin:
    def update(self, dt: float) -> None:
        t = self.truck
        # pacing can be changed from the pause menu mid-trip; keep the trip's
        # clock compression in step with the setting
        self.trip.time_scale = self.ctx.settings.time_scale
        self._sync_weather_source()
        keys = pygame.key.get_pressed()
        ramp = dt * 2.2
        self._brake_lockout_cue_timer = max(0.0, self._brake_lockout_cue_timer - dt)
        self._lane_rumble_timer = max(0.0, self._lane_rumble_timer - dt)
        accelerating = keys[pygame.K_UP]
        braking_key = keys[pygame.K_DOWN]
        backing = self._update_reverse_controls(accelerating, braking_key)
        if accelerating and not backing and t.air_brakes_holding:
            self._maybe_say_air_brake_lockout()
        if accelerating and not backing:
            if t.engine_brake:
                t.engine_brake = False
                self.ctx.say_event("Engine brake off.", interrupt=False)
            t.throttle = min(1.0, t.throttle + ramp)
        elif backing:
            t.throttle = min(0.45, t.throttle + ramp)
        else:
            t.throttle = max(0.0, t.throttle - ramp * 2)
        braking = (braking_key and not backing) or (accelerating and t.velocity_mps < -0.1)
        if braking:
            new_brake = min(1.0, t.brake + ramp * 1.5)
            if t.brake < 0.05 and new_brake >= 0.05 and abs(t.velocity_mps) > 1:
                self.ctx.audio.play("vehicle/brake_air", volume=0.6)
            t.brake = new_brake
        else:
            t.brake = max(0.0, t.brake - ramp * 3)
        emergency = keys[pygame.K_b]
        if emergency:
            # no ramp: slams to full application instantly, plus spring brakes
            if not t.emergency_brake and abs(t.velocity_mps) > 1:
                self.ctx.audio.play("vehicle/brake_air", volume=1.0)
            t.throttle = 0.0
            t.brake = 1.0
        t.emergency_brake = emergency
        clutch_pressed = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        t.transmission.clutch = (
            1.0 if clutch_pressed and not t.transmission.automatic else 0.0
        )
        self._update_lane(keys, dt)
        self._update_cruise(dt, braking, accelerating)

        if t.transmission.automatic and t.engine_on:
            new_gear = t.auto_shift()
            if new_gear is not None:
                self.ctx.audio.play("vehicle/gear_shift", volume=0.65)

        was_on = t.engine_on
        was_air_ready = t.air_ready
        was_low_air = t.air_low_warning
        was_spring_brake = t.spring_brakes_active
        t.update(dt)
        self._update_air_brake_announcements(
            was_air_ready, was_low_air, was_spring_brake)
        if was_on and not t.engine_on:
            self.ctx.audio.engine_stop()
            if t.stalled:
                self.ctx.say_event("The engine stalled. Press E to restart, and "
                                   "use a lower gear at low speed.")
            elif t.fuel_gal <= 0:
                self._handle_out_of_fuel()

        # Keep the trip's spoken-distance units in step with a live settings
        # change; the setter only re-renders cues when the choice actually flips.
        self.trip.imperial = self.ctx.settings.imperial_units
        pos_before = self.trip.position_mi
        for event in self.trip.update(dt):
            self._handle_trip_event(event)
        self._check_destination_exit()
        self._update_exit(self.trip.position_mi - pos_before)

        self._update_hours_and_fatigue(dt)
        self._update_audio(dt)
        self._update_announcements(dt)
        self._update_hazard(dt)
        self._update_microsleep(keys, dt)
        self._update_speeding(dt)
        self._update_pull_over(dt)
        if self.tutorial:
            self.tutorial.update(dt, t)
        if self.trip.finished:
            if self.phase == DRIVE_PHASE_PICKUP:
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
        if not t.engine_on:
            self._set_status("Start the engine before releasing the brakes.")
            self.ctx.say_event("Start the engine first; air pressure cannot build "
                               "with the engine off.", interrupt=False)
        elif not t.air_ready:
            self._set_status("Waiting for air pressure before the truck can move.")
            self.ctx.say_event(
                f"Air pressure {t.air_pressure_psi:.0f} psi. Wait for 100 psi, "
                "then press P to release the parking brake.",
                interrupt=False)
        elif t.parking_brake:
            self._set_status("Parking brake set. Press P to release it.")
            self.ctx.say_event("Parking brake set. Press P to release it.",
                               interrupt=False)

    def _update_air_brake_announcements(
            self, was_ready: bool, was_low: bool, was_spring: bool) -> None:
        t = self.truck
        if t.air_low_warning and t.engine_on and (not was_low or not self._low_air_said):
            self._low_air_said = True
            self.ctx.audio.play("vehicle/low_air_buzzer", volume=0.7)
            self.ctx.say_event(
                f"Low air warning: {t.air_pressure_psi:.0f} psi. "
                "Keep the parking brake set until pressure builds.",
                interrupt=False)
        elif not t.air_low_warning:
            self._low_air_said = False

        if t.spring_brakes_active and not was_spring and not self._spring_brake_said:
            self._spring_brake_said = True
            self.ctx.audio.play("vehicle/low_air_buzzer", volume=0.9)
            self.ctx.say_event(
                "Spring brakes applied from low air pressure. Stop and let the "
                "compressor rebuild air before moving.",
                interrupt=True)
        elif not t.spring_brakes_active:
            self._spring_brake_said = False

        if (t.air_ready and t.parking_brake and not was_ready
                and not self._air_ready_said):
            # The cue's whole job is "you can release the parking brake now", so
            # only announce while it is set. Once released (rolling, or braking to
            # a stop on arrival), a dip back across the threshold must not
            # re-announce it.
            self._air_ready_said = True
            self.ctx.audio.play("vehicle/air_dryer_purge", volume=0.65)
            self._set_status("Air ready. Press P to release the parking brake.")
            self.ctx.say_event(
                f"Air pressure ready at {t.air_pressure_psi:.0f} psi. "
                "Press P to release the parking brake.", interrupt=False)
            self.ctx.award_achievement("air_ready", event=True)
        elif t.air_low_warning:
            # Re-arm the ready cue only after a genuine depletion (low-air), not
            # the routine 100-125 psi compressor cycling: the parking-release
            # threshold sits at the cut-in pressure, so air_ready otherwise
            # flickers across it every cycle and re-announces back to back.
            self._air_ready_said = False

    def _update_reverse_controls(self, accelerating: bool, braking_key: bool) -> bool:
        """Return True when the current key state means backing up."""
        t = self.truck
        tr = t.transmission
        if not tr.automatic:
            return tr.in_reverse and braking_key and not accelerating
        if tr.in_reverse:
            if accelerating and abs(t.velocity_mps) < 0.3:
                tr.gear = 1
                tr._shift_timer = 0.0
                self.ctx.audio.play("vehicle/gear_shift", volume=0.55)
                self._set_status("Forward gear selected.")
                return False
            return braking_key and not accelerating
        if braking_key and not accelerating and t.speed_mph < 0.5:
            tr.gear = REVERSE
            tr._shift_timer = 0.0
            self._cancel_cruise()
            self.ctx.audio.play("vehicle/gear_shift", volume=0.55)
            self._set_status("Reverse selected. Backing slowly.")
            return True
        return False

    def _update_hours_and_fatigue(self, dt: float) -> None:
        """Advance the HOS shift clock and fatigue on game time, not wall time."""
        gm = dt * self.trip.time_scale / 60.0   # game minutes this frame
        moving = self.truck.speed_mph > 5.0
        mode = self.ctx.settings.hos_mode
        p = self.ctx.profile

        if self.job.bobtail:
            self.hos.off_duty(gm)
        elif moving:
            self.hos.drive(gm)
        else:
            self.hos.on_duty(gm)   # the 14-hour window runs even while parked
        if mode not in hos.HOS_NON_ENFORCED_MODES:
            for message in self.hos.check_warnings(mode):
                self.ctx.audio.play("ui/warning")
                self.ctx.say_event(message, interrupt=hos.warning_is_urgent(message))
        self.trip.hos_violation = (
            mode not in hos.HOS_NON_ENFORCED_MODES and self.hos.in_violation(mode)
        )

        night = is_night(self.trip.current_hour)
        if moving:
            p.fatigue = min(100.0, p.fatigue + hos.fatigue_rate_per_min(night) * gm)
        fatigue = p.fatigue
        if fatigue >= hos.FATIGUE_SEVERE and not self._severe_said:
            self._severe_said = True
            self._fatigue_cue_gm = 0.0
            self.ctx.audio.play("vehicle/rumble_strip", volume=0.8)
            self.ctx.say_event("You are dangerously drowsy and drifting out of "
                               "your lane. Sleep at the next rest stop.",
                               interrupt=False)
        elif fatigue >= hos.FATIGUE_DROWSY and not self._drowsy_said:
            self._drowsy_said = True
            self._fatigue_cue_gm = 0.0
            self.ctx.audio.play("driver/yawn", volume=0.9)
            self.ctx.say_event("You are getting drowsy. Take a break or sleep "
                               "at a rest stop.", interrupt=False)
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
        self.lane.steering = steer
        leg = self.route.legs[self.trip.current_leg_index]
        curve = 0.0
        if leg.terrain == "hills":
            curve = 0.25
        elif leg.terrain == "mountain":
            curve = 0.55
        if self._ramp_mi is not None:
            curve += 0.35
        wind = self.weather.effects.wind
        if self.lane.update(dt, self.truck.velocity_mps, curve=curve, wind=wind, assist=mode):
            self.ctx.audio.play("vehicle/rumble_strip", volume=1.0,
                                pan=self._lane_pan())
            self.truck.damage_pct = min(100.0, self.truck.damage_pct + 1.0)
            self.ctx.say_event(
                f"{self.lane.describe()} Steer back toward the lane center.",
                interrupt=False,
            )

    def _lane_pan(self) -> float:
        """Stereo pan for the rumble strip: it comes from the side you have
        drifted toward (negative left, positive right), so the side you hear it
        on is the side to steer away from."""
        return max(-1.0, min(1.0, self.lane.offset))

    def _update_audio(self, dt: float = 0.0) -> None:
        t = self.truck
        audio = self.ctx.audio
        if t.engine_on and not audio.engine_running:
            audio.engine_start()
        engine_load = t.throttle
        if t.transmission.automatic and t.transmission.shifting:
            engine_load = min(engine_load, 0.08)
        audio.set_engine_rpm(t.rpm, engine_load)
        audio.set_road_noise(t.velocity_mps)
        eff = self.weather.effects
        audio.set_weather(eff.sound)
        audio.set_wind(eff.wind)
        rumble = self.lane.rumble_level()
        if (
            rumble > 0.0
            and self.ctx.settings.steering_assist != "off"
            and self._lane_rumble_timer <= 0.0
        ):
            self._lane_rumble_timer = 0.8
            audio.play("vehicle/rumble_strip", volume=0.25 + rumble * 0.45,
                       pan=self._lane_pan())
        night = is_night(self.trip.current_hour)
        if night:
            audio.set_ambient("ambient/night")
        else:
            audio.set_ambient(None)
        self._update_music_rotation(night, dt)
        if self.weather.should_thunder():
            audio.play("weather/thunder")

    def _current_music_track(self) -> str:
        if self._music_night:
            return self._night_music_sequence[self._night_music_index]
        return self._day_music_sequence[self._day_music_index]

    def _play_current_music(self, fade_ms: int = 4000) -> None:
        self.ctx.audio.play_music(self._current_music_track(), fade_ms=fade_ms)

    def _update_music_rotation(self, night: bool, dt: float) -> None:
        if night != self._music_night:
            self._music_night = night
            self._music_elapsed_s = 0.0
            self._play_current_music(fade_ms=4000)
            return
        self._music_elapsed_s += max(0.0, dt)
        current = self._current_music_track()
        if self._music_elapsed_s < music_track_duration_s(current):
            return
        self._music_elapsed_s = 0.0
        if night:
            self._night_music_index = (
                self._night_music_index + 1
            ) % len(self._night_music_sequence)
        else:
            self._day_music_index = (
                self._day_music_index + 1
            ) % len(self._day_music_sequence)
        self._play_current_music(fade_ms=4000)

    def _sync_weather_source(self) -> None:
        real = self.ctx.settings.real_weather
        if real == self._weather_source_real:
            return
        self._weather_source_real = real
        self.weather.provider = self.ctx.real_weather_provider() if real else None
        if not real:
            self.weather.live = False
        self.ctx.audio.set_weather(self.weather.effects.sound)
        self.ctx.audio.set_wind(self.weather.effects.wind)

    def _update_announcements(self, dt: float) -> None:
        if self.ctx.settings.speech_verbosity == 0:
            return
        self._speed_announce_timer += dt
        interval = 12.0 if self.ctx.settings.speech_verbosity == 1 else 7.0
        if self._speed_announce_timer >= interval:
            self._speed_announce_timer = 0.0
            mph = self.truck.speed_mph
            if abs(mph - self._last_announced_mph) >= 5 and mph > 1:
                self._last_announced_mph = mph
                self.ctx.say_event(self.ctx.settings.speed_text(mph),
                                   interrupt=False)

    def _brake_budget_s(self) -> float:
        """Seconds of full service braking to reach the hazard-safe speed.

        Uses the truck's rated deceleration on the current surface, helped
        uphill and hurt downhill, so a warning at 65 in the snow allows the
        stop it actually takes there.
        """
        t = self.truck
        over_mps = max(0.0, (t.speed_mph - HAZARD_SAFE_MPH) / MPH_PER_MPS)
        decel = G * (t.specs.max_brake_decel_g * t.grip + t.grade)
        return over_mps / max(decel, 0.5)

    def _update_hazard(self, dt: float) -> None:
        if self._hazard_deadline is None:
            return
        if self.truck.speed_mph <= HAZARD_SAFE_MPH:
            self._hazard_deadline = None
            self.ctx.say_event("Hazard avoided. Well done.", interrupt=False)
            self.ctx.award_achievement("hazard_avoided", event=True)
            return
        self._hazard_deadline -= dt
        if self._hazard_deadline <= 0:
            self._hazard_deadline = None
            self.ctx.audio.play("vehicle/collision")
            severity = min(1.0, self.truck.speed_mph / 70.0)
            self.truck.apply_collision(severity)
            self.ctx.say_event(f"Collision! The truck took damage. "
                               f"Total damage {self.truck.damage_pct:.0f} percent.")

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
        if (self._microsleep_deadline is not None
                or self._hazard_deadline is not None
                or self._microsleep_cooldown_gm > 0.0):
            return
        self._microsleep_gm += gm
        if self._microsleep_gm >= self._microsleep_interval_gm(fatigue):
            self._microsleep_gm = 0.0
            self._begin_microsleep()

    def _begin_microsleep(self) -> None:
        self._cancel_cruise()   # the nod takes your hands off the wheel
        self._microsleep_deadline = MICROSLEEP_REACTION_S
        self.ctx.audio.play("vehicle/rumble_strip", volume=1.0)
        self.ctx.say_event(
            "You are nodding off. Steer or brake now to stay awake!",
            interrupt=True)

    def _update_microsleep(self, keys, dt: float) -> None:
        if self._microsleep_deadline is None:
            return
        # Already crawling: the nod passes without leaving the road.
        if self.truck.speed_mph <= HAZARD_SAFE_MPH:
            self._resolve_microsleep(silent=True)
            return
        reacted = (keys[pygame.K_LEFT] or keys[pygame.K_RIGHT]
                   or keys[pygame.K_DOWN] or keys[pygame.K_b])
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
            self.ctx.say_event("You caught it. Pull over and sleep before the "
                               "next one.", interrupt=False)

    def _microsleep_drift_off_road(self) -> None:
        self._microsleep_misses += 1
        self._microsleep_cooldown_gm = MICROSLEEP_COOLDOWN_GM
        t = self.truck
        self.ctx.audio.play("vehicle/rumble_strip", volume=1.0)
        t.damage_pct = min(100.0, t.damage_pct + MICROSLEEP_SHOULDER_DAMAGE_PCT)
        t.velocity_mps *= 0.8   # wandering onto the shoulder scrubs speed
        if self._microsleep_misses >= MICROSLEEP_FORCE_STOP_MISSES:
            self._microsleep_misses = 0
            t.throttle = 0.0
            t.brake = 1.0
            self.ctx.say_event(
                "You cannot stay awake. You drift onto the shoulder and jolt "
                "awake on the brakes. Stop and sleep before you wreck.",
                interrupt=True)
        else:
            self.ctx.say_event(
                f"You nodded off and drifted onto the rumble strip. The truck "
                f"took damage, now {t.damage_pct:.0f} percent. Pull over and "
                "sleep.", interrupt=True)

    def _update_speeding(self, dt: float) -> None:
        if self._ramp_mi is not None:
            return   # the ramp is off the highway and unpatrolled
        if self._missed_destination_exit_said and not self._destination_exit_taken:
            return   # recovery state: guide the player back to the missed exit
        if self._pull_over is not None:
            return   # already being pulled over; don't pile on strikes
        limit, _ = self.trip.speed_limit_at(self.trip.position_mi)
        if self.truck.speed_mph > limit + SPEEDING_LEEWAY_MPH:
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
                # Surface the cost the moment the strike lands instead of only as a
                # silent deduction at delivery, so the price of speeding is felt now.
                if after > before:
                    self.ctx.say_event(
                        "Speeding strike. The limit is "
                        f"{self.ctx.settings.speed_text(limit)}. Speeding "
                        f"fines now total {after:,.0f} dollars, due at delivery.",
                        interrupt=False)
                else:
                    self.ctx.say_event(
                        "Speeding strike. The limit is "
                        f"{self.ctx.settings.speed_text(limit)}. Your speeding "
                        f"fines are already at the {after:,.0f}-dollar maximum.",
                        interrupt=False)
        else:
            self._speeding_timer = 0.0

    def _trooper_catches_speeder(self, limit: float) -> bool:
        """Whether a patrol clocks this speeding strike, by patrol intensity."""
        if self.ctx.settings.hos_mode in hos.HOS_NON_ENFORCED_MODES:
            return False   # enforcement is bypassed in the debug mode
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
        patrol = self.trip.active_patrol_at(self.trip.position_mi)
        where = patrol.reason if patrol is not None else "patrol"
        self.ctx.audio.play("events/police_siren")
        self.ctx.say_event(
            f"Lights and siren behind you. A trooper on this {where} clocked you "
            f"at {self.ctx.settings.speed_text(self.truck.speed_mph)} in a "
            f"{self.ctx.settings.speed_text(limit)} zone. Signal with X and "
            "brake to a stop on the shoulder.",
            interrupt=True)

    def _signal_pull_over(self) -> None:
        """X during a pull-over: signal and ease over (better demeanor)."""
        if self._pull_over == "lights":
            self._pull_over = "stopping"
            self._pull_over_signaled = True
            self.ctx.audio.play("ui/notify", volume=0.5)
            self.ctx.say("Signaling and easing onto the shoulder. Brake to a "
                         "full stop.")
        else:
            self.ctx.say("Pulling over. Brake to a full stop on the shoulder.")

    def _update_pull_over(self, dt: float) -> None:
        if self._pull_over is None:
            return
        if self.truck.speed_mph <= DOCKING_MAX_MPH:
            self._open_traffic_stop()
            return
        if self.trip.position_mi - self._pull_over_start_mi >= PULL_OVER_IGNORE_MI:
            self._evade_pull_over()

    def _open_traffic_stop(self) -> None:
        signaled = self._pull_over_signaled
        over, limit = self._pull_over_over, self._pull_over_limit
        self._pull_over = None
        self.ctx.push_state(
            TrafficStopState(self.ctx, self, signaled=signaled, over=over,
                             limit=limit))

    def _evade_pull_over(self) -> None:
        """Drove on with the lights behind: spike strips end it, logged as a
        felony stop with a heavy fine and reputation hit."""
        self._pull_over = None
        p = self.ctx.profile
        fine = SPEEDING_TICKET_FINES[-1] * 1.5
        self.speeding_tickets += 1
        self.ticket_fines_paid += fine
        p.money -= fine
        p.career.reputation = max(0.0, p.career.reputation
                                  - hos.HOS_REPUTATION_HIT * 2.0)
        self.ctx.audio.play("events/spike_strip")
        self.ctx.say_event(
            f"You ran from the traffic stop, so troopers laid spike strips across "
            f"the lane. That is a felony stop: a {fine:,.0f} dollar fine and a "
            "serious reputation hit.",
            interrupt=True)


