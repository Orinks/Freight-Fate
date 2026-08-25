//! The frame loop itself (`DrivingUpdateMixin.update`), the safety-call
//! re-speak, and the retarder transcript trace.

use ff_core::speech_pacing::{EventPriority, SpeechCategory};

use crate::app::{GameContext, SayEvent, TRANSCRIPT_TARGET};
use crate::audio::CH_BRAKE;
use crate::states::base::Key;
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;
use crate::states::driving_pacenotes::PACENOTE_MARGIN_MPH;
use crate::states::driving_updates::{live, PAD_EMERGENCY_BRAKE};

impl DrivingState {
    /// Re-speak a safety call the player silenced before it finished.
    ///
    /// Ctrl is a screen-reader reflex and must always silence instantly --
    /// but a curve call cut mid-sentence is information the road still
    /// owes the driver (owner's worry, 2026-07-20: "how you gonna get it
    /// spoken?"). If Ctrl landed inside the call's speaking window, the
    /// call re-arms once and speaks again with a REFRESHED distance --
    /// provided the bend is still ahead and the truck is still above its
    /// advisory. Passed it, or slowed for it: stay quiet.
    pub fn update_critical_respeak(&mut self, ctx: &mut GameContext, dt: f64) {
        if self.critical_curve.is_none() {
            return;
        }
        self.critical_call_age_s += dt;
        let Some(respeak_at) = self.critical_respeak_at else {
            if self.critical_call_age_s > CRITICAL_CALL_WINDOW_S {
                self.critical_curve = None; // spoke to the end, most likely
            }
            return;
        };
        if self.critical_call_age_s < respeak_at {
            return;
        }
        let curve = self.critical_curve.take().expect("checked above");
        self.critical_respeak_at = None;
        let ahead = curve.start_mi - self.trip.position_mi;
        let speed = self.trip.truck.speed_mph();
        if ahead <= 0.0 || speed <= curve.advisory_mph as f64 + PACENOTE_MARGIN_MPH {
            return;
        }
        let pan = if curve.direction == 'L' {
            -PACENOTE_CUE_PAN
        } else {
            PACENOTE_CUE_PAN
        };
        ctx.audio.play_with("vehicle/curve_bink", 0.9, pan);
        let text = self.pacenote_text(ctx, &curve, ahead, speed);
        let mut opts = SayEvent::new().category(SpeechCategory::Navigation);
        // The refreshed call checks the bend before speaking; the rescue
        // path speaks it again later, so it has to check too.
        if let Some(valid) = self.curve_call_still_true(Some(&curve)) {
            self.refresh_live_facts();
            opts = opts.valid(move || valid.holds());
        }
        ctx.say_event_with(text, opts);
    }

    /// Called from the Ctrl handler: arm the one-shot refreshed re-speak
    /// when the silence landed inside a safety call's speaking window.
    pub fn note_critical_speech_stopped(&mut self) {
        if self.critical_curve.is_some()
            && self.critical_respeak_at.is_none()
            && self.critical_call_age_s < CRITICAL_CALL_WINDOW_S
        {
            self.critical_respeak_at = Some(self.critical_call_age_s + CRITICAL_RESPEAK_DELAY_S);
        }
    }

    /// Write a transcript line whenever the retarder changes stage.
    ///
    /// The jake is audible and nothing else. It speaks no line of its own,
    /// so "did the engine brake just come up on level road?" -- an ordinary
    /// playtest question, asked mid-drive by the owner on 2026-08-20 -- had
    /// no answer anywhere: not in the transcript, not in the session log,
    /// not in the save. The only way to settle it was to rebuild the road
    /// on a bench and hope the conditions matched.
    ///
    /// One line per CHANGE, never per frame, carrying the road that
    /// explains it: a stage rising on a real downgrade is the retarder
    /// doing its job, and the same stage rising on the flat is the bug the
    /// question was about. Prefixed like the pacer and ladder lines so the
    /// transcript stays sortable into "what the driver heard" and "what the
    /// truck did".
    pub fn trace_engine_brake(&mut self) {
        let stage = self.trip.truck.engine_brake_stage;
        if stage == self.traced_jake_stage {
            return;
        }
        self.traced_jake_stage = stage;
        let grade_pct = self.trip.grade_at(self.trip.position_mi) * 100.0;
        log::info!(
            target: TRANSCRIPT_TARGET,
            "[jake] stage {} at mile {:.1}, {:.0} mph, grade {:+.1} percent",
            stage,
            self.trip.position_mi,
            self.trip.truck.speed_mph(),
            grade_pct,
        );
    }

    /// `update(dt)`: one frame of driving.
    pub fn update_frame(&mut self, ctx: &mut GameContext, dt: f64) {
        // The Python `State.update` this mixin overrode advanced the menu
        // music bed; a drive clears the rotation on entry, so the call is a
        // no-op here and stays only because every `State::update` owes it.
        ctx.update_music_rotation(dt);
        self.refresh_live_facts();
        self.trace_engine_brake();
        // A fresh loaded run out of a chain-capable origin starts on the
        // facility's streets. Decided on the first tick, never on a resume:
        // from_snapshot marks the check done and re-enters a chain itself.
        if !self.departure_checked {
            self.departure_checked = true;
            if !self.resumed {
                self.begin_departure_chain(ctx, true);
            }
        }
        // pacing can be changed from the pause menu mid-trip; keep the trip's
        // clock compression in step with the setting
        self.trip.time_scale = ctx.settings.time_scale;
        let tuning = tuning_for_time_scale(self.trip.time_scale);
        self.trip.hazard_scale =
            hos::hazard_scale(&ctx.settings.hos_mode) * tuning.hazard_frequency;
        self.trip.traffic_manager.hazard_scale = self.trip.hazard_scale;
        self.sync_radio_settings(ctx);
        // A new leg is a fresh road, so a once-per-leg tip earns one more
        // telling (Disposition.FIRST_OCCURRENCE).
        let leg = self.trip.current_leg_index() as i64;
        if leg != self.ladder_leg_index {
            self.ladder_leg_index = leg;
            ctx.reset_ladder_leg_memory();
        }
        if self.destination_exit_response_s > 0.0 {
            self.destination_exit_response_s = (self.destination_exit_response_s - dt).max(0.0);
            if self.destination_exit_response_s == 0.0 && self.exit_stop.is_none() {
                // A driver who stopped after the early callout must still get a
                // fresh, closer instruction once the normal window reaches them.
                self.destination_exit_announced_key = String::new();
            }
        }
        self.sync_weather_source(ctx);
        let ramp = dt * 2.2;
        self.brake_lockout_cue_timer = (self.brake_lockout_cue_timer - dt).max(0.0);
        // Controller triggers/clutch are analog held positions blended in below;
        // the keyboard keys keep their ramped behavior so both devices work.
        let pad_on = ctx.controller.active();
        let pad_throttle = if pad_on {
            ctx.controller.throttle()
        } else {
            0.0
        };
        let pad_brake = if pad_on { ctx.controller.brake() } else { 0.0 };
        let mut key_up = ctx.input.is_pressed(Key::Up);
        let mut key_down = ctx.input.is_pressed(Key::Down);
        let b_held = ctx.input.is_pressed(Key::B);
        // Latching pedals: after the double-tap-and-hold gesture a pedal
        // reads as held right here, so everything downstream -- the reverse
        // gesture, cruise cancel, the hazard's brake answer -- sees one
        // truth. Microsleeps stay on the raw keys: only a live reaction
        // proves the driver awake.
        // The latch releases on the emergency application, so it has to see the
        // pad's version of it too. Read raw here rather than gated on backing:
        // a trigger buried to the floor should drop a latched pedal whichever
        // direction the truck is going.
        let (hand_up, latched_key_down, throttle_latched) = self.update_pedal_latches(
            ctx,
            key_up,
            key_down,
            pad_throttle,
            pad_brake,
            b_held || pad_brake >= PAD_EMERGENCY_BRAKE,
            dt,
        );
        key_down = latched_key_down;
        // The latch is the LOWEST-priority speed input in "assists first"
        // mode: while cruise, the keeper, or curve assist is engaged it
        // contributes nothing, and it ramps back in when the last of them
        // releases -- no re-gesture (owner design 2026-08-13). A hand-held
        // key stays a live manual override, which is why the assists are
        // handed hand_accelerating below rather than this blended value.
        // "latch first" is the original meaning: the latch is the driver
        // insisting on speed, so the assists see it as a hand and stand
        // down instead.
        let latch_mode = ctx.settings.pedal_latch.clone();
        self.latch_yielding =
            throttle_latched && latch_mode == "assists first" && self.speed_authority_engaged();
        key_up = hand_up || (throttle_latched && !self.latch_yielding);
        let accelerating = key_up || pad_throttle > 0.05;
        let assist_up = hand_up || (throttle_latched && latch_mode == "latch first");
        let hand_accelerating = assist_up || pad_throttle > 0.05;
        let braking_key = key_down || pad_brake > 0.05;
        // The shift gesture keys off a fresh press, so it reads the trigger's
        // instantaneous position rather than the smoothed accelerate/brake
        // values above -- otherwise the smoothing lag swallows a quick tap and
        // the release-then-press never registers as neutral in between.
        let accel_held = key_up
            || (if pad_on {
                ctx.controller.throttle_target()
            } else {
                0.0
            }) > 0.05;
        let brake_held = key_down
            || (if pad_on {
                ctx.controller.brake_target()
            } else {
                0.0
            }) > 0.05;
        let backing = self.update_reverse_controls(
            ctx,
            accelerating,
            braking_key,
            accel_held,
            brake_held,
            dt,
        );
        if accelerating && !backing && self.trip.truck.air_brakes_holding() {
            self.maybe_say_air_brake_lockout(ctx);
        } else if !self.trip.truck.air_brakes_holding() {
            // The lockout actually cleared (parking brake released, spring
            // brakes recovered) -- not merely the player's foot off the
            // pedal, which must NOT drop the key or the next press would
            // re-announce an unchanged reason. The next time it arms is a
            // fresh instance of the condition and gets its warning again,
            // even with identical wording (mirrors update_overrev's reset
            // of "engine_redline").
            ctx.reset_event_condition("air_brake_lockout");
        }
        if key_up && !backing && !self.trip.truck.transmission.in_reverse() {
            if self.trip.truck.engine_brake() {
                self.trip.truck.set_engine_brake(false);
                // And the AMT manager with it, or "Jake off" is a lie: auto
                // mode is allowed to sit at stage zero now, so an armed
                // manager left behind here would quietly bring the retarder
                // back a moment after the cab said it was off.
                self.auto_jake = false;
                // ROUTE, not the ambient default: an automation (the engine
                // brake) just released, and a driver who assumed it still held
                // needs to hear that (automation-handoff sweep, 2026-08-20,
                // the deferred 2026-08-15 audit).
                ctx.say_event_with(
                    "Jake off.",
                    SayEvent::queued()
                        .priority(EventPriority::Route)
                        .category(SpeechCategory::Confirmation),
                );
            }
            let t = &mut self.trip.truck;
            t.throttle = 1.0f64.min(t.throttle + ramp);
        } else if backing {
            let t = &mut self.trip.truck;
            t.throttle = 0.45f64.min(t.throttle + ramp);
        } else {
            let t = &mut self.trip.truck;
            t.throttle = 0.0f64.max(t.throttle - ramp * 2.0);
        }
        if pad_throttle > 0.05 && !backing && !self.trip.truck.transmission.in_reverse() {
            if self.trip.truck.engine_brake() {
                self.trip.truck.set_engine_brake(false);
                self.auto_jake = false; // see the keyboard branch above
                                        // ROUTE, not the ambient default: same as the keyboard branch
                                        // above (automation-handoff sweep, 2026-08-20, the deferred
                                        // 2026-08-15 audit).
                ctx.say_event_with(
                    "Jake off.",
                    SayEvent::queued()
                        .priority(EventPriority::Route)
                        .category(SpeechCategory::Confirmation),
                );
            }
            let t = &mut self.trip.truck;
            t.throttle = t.throttle.max(pad_throttle);
        }
        // Keyboard ramps the brake up and down; the analog trigger sets a direct
        // held floor on top of that.
        let braking_ramp =
            (key_down && !backing) || (accelerating && self.trip.truck.velocity_mps < -0.1);
        {
            let t = &mut self.trip.truck;
            if braking_ramp {
                t.brake = 1.0f64.min(t.brake + ramp * 1.5);
            } else {
                t.brake = 0.0f64.max(t.brake - ramp * 3.0);
            }
            if pad_brake > 0.05 && !backing {
                t.brake = t.brake.max(pad_brake);
            }
        }
        let braking = braking_ramp || (pad_brake > 0.05 && !backing);
        // "not backing" matters more here than it looks: in automatic, holding
        // the left trigger from a stop is the gesture that shifts to reverse,
        // so without it every backing manoeuvre would slam the emergency
        // application on and flat-spot the tires for it.
        let emergency = b_held || (pad_brake >= PAD_EMERGENCY_BRAKE && !backing);
        // A real truck drops cruise at the first tap of the service brake.
        // Only the player's own pedal cancels here; the sim's automatic brake
        // ramps (reverse arrest, hazard events) go through their own cancels.
        if self.cruise_mph.is_some() && (braking_key || emergency) && !backing {
            self.cancel_cruise(ctx, false);
            // ROUTE, not the ambient default: the automation just released the
            // throttle (automation-handoff sweep, 2026-08-20, the deferred
            // 2026-08-15 audit).
            ctx.say_event_with(
                "Cruise off.",
                SayEvent::queued()
                    .priority(EventPriority::Route)
                    .category(SpeechCategory::Confirmation),
            );
        }
        if emergency {
            // no ramp: slams to full application instantly, plus spring brakes
            if !self.trip.truck.emergency_brake && self.trip.truck.velocity_mps.abs() > 1.0 {
                if ctx.audio.has_asset("vehicle/ebrake") {
                    // The licensed cut: one big sustained air event.
                    ctx.audio.play_with("vehicle/ebrake", 0.9, 0.0);
                } else {
                    ctx.audio.play_with("vehicle/brake_air", 1.0, 0.0);
                }
            }
            let t = &mut self.trip.truck;
            t.throttle = 0.0;
            t.brake = 1.0;
        }
        self.trip.truck.emergency_brake = emergency;
        // Hard braking (emergency or heavy service) shudders the pad while it
        // lasts; the engine's TTL lets it lapse a few frames after we stop. Only
        // while moving *forward*: rolling backward, the sim ramps the service
        // brake to full on its own to arrest the reverse before shifting to
        // drive, and that must not read as a hard stop and buzz the whole time.
        if self.trip.truck.velocity_mps > 1.0 && (emergency || self.trip.truck.brake >= 0.85) {
            let level = if emergency {
                1.0
            } else {
                self.trip.truck.brake
            };
            ctx.controller.rumble.hard_brake(level);
        }
        // Brake sounds ride the application edges. A hysteresis flag (arm at
        // 0.05, release below 0.02) keeps a steady analog trigger -- or a held
        // key -- from retriggering frame after frame. The emergency brake
        // plays its own louder cue, so it only arms the flag.
        // PRESS: the mechanical clunk of the valve, leveled by press force
        // (locked spec 2026-07-21; the classic air chirp is the fallback).
        // RELEASE: the air bleeding back out -- the hiss bed held for a
        // length, and at a level, set by how hard the brakes were applied.
        // The release plays at any speed: braking to a halt then letting off
        // is exactly when a real rig gives its loudest pssht.
        if self.trip.truck.brake >= 0.05 {
            if !self.brake_air_hissed && !emergency && self.trip.truck.velocity_mps.abs() > 1.0 {
                let force = self.trip.truck.brake.clamp(0.0, 1.0);
                ctx.audio.play_bank_with(
                    "vehicle/brake_clunk",
                    "vehicle/brake_air",
                    0.35 + 0.35 * force,
                    0.0,
                );
            }
            self.brake_air_hissed = true;
            self.brake_peak_application = self.brake_peak_application.max(self.trip.truck.brake);
        } else if self.trip.truck.brake < 0.02 {
            let peak = self.brake_peak_application;
            // Locked spec levels (0.07-0.12 mix, "all quiet under the
            // engine"): a light release is a barely-there sigh below the
            // road bed, not a foreground pssht -- shipped 4x hot at first
            // and the owner heard every tap on a twisty descent. Feather
            // releases under the floor stay silent entirely.
            if self.brake_air_hissed
                && peak >= 0.15
                && !emergency
                && ctx.audio.has_asset("vehicle/brake_hiss_bed")
            {
                // Road noise masks the release at speed, exactly as in a real
                // cab: rolling releases fade toward inaudible while the big
                // pssht after braking to a stop keeps its full voice.
                let masking = 0.25f64.max(1.0 - self.trip.truck.velocity_mps.abs() / 20.0);
                ctx.audio.start_loop_with(
                    CH_BRAKE,
                    "vehicle/brake_hiss_bed",
                    (0.10 + 0.15 * peak) * masking,
                    0,
                );
                ctx.audio
                    .stop_loop_with(CH_BRAKE, (160.0 + 800.0 * peak) as u32);
            }
            self.brake_air_hissed = false;
            self.brake_peak_application = 0.0;
        }
        let desired_automatic = ctx.settings.automatic_transmission;
        if self.trip.truck.transmission.automatic != desired_automatic {
            self.trip.truck.transmission.automatic = desired_automatic;
            let mode = if desired_automatic {
                "automatic"
            } else {
                "manual"
            };
            ctx.say_event_with(
                format!("Transmission changed to {mode}."),
                SayEvent::new().category(SpeechCategory::Confirmation),
            );
        }

        let clutch_pressed = ctx.input.is_pressed(Key::LShift) || ctx.input.is_pressed(Key::RShift);
        let mut clutch_val: f64 = if clutch_pressed { 1.0 } else { 0.0 };
        if pad_on {
            clutch_val = clutch_val.max(ctx.controller.clutch());
        }
        self.trip.truck.transmission.clutch = if !self.trip.truck.transmission.automatic {
            clutch_val
        } else {
            0.0
        };
        let clutch_disengaged =
            self.trip.truck.transmission.clutch > 0.5 || self.trip.truck.transmission.shifting();
        self.update_lane(ctx, dt);
        self.update_exit_preparation(ctx, dt);
        self.resume_speed_control_if_ready(ctx, braking);
        self.update_cruise(ctx, dt, braking, hand_accelerating, clutch_disengaged);
        self.update_keeper(ctx, dt, braking, hand_accelerating, clutch_disengaged);
        // The hazard assist's held application belongs here with the other
        // assists' floors, ahead of the physics -- see apply_hazard_brake.
        // update_hazard, which decides it, runs at the end of the frame.
        self.apply_hazard_brake();
        // The destination arrival's pedals, for the same reason, and it is
        // the reason that cost three reports: this ran AFTER the physics
        // step, so the brake it set was never integrated -- the keyboard ramp
        // at the top of the next frame decayed it to nothing before
        // t.update() ran, and the physics saw 0.00 the whole way to the gate
        // while the assist's own bookkeeping said 0.40. Every earlier fix to
        // this assist tuned a number against a pedal the truck never felt.
        self.update_destination_approach_assist(ctx);
        self.update_horn_protection(ctx);

        self.update_auto_jake(ctx, dt);
        self.track_driving_badges(ctx, dt);
        if self.trip.truck.transmission.automatic && self.trip.truck.engine_on {
            let new_gear = self.trip.truck.auto_shift();
            if new_gear.is_some() {
                ctx.audio
                    .play_bank_with("vehicle/shift_auto", "vehicle/gear_shift", 0.65, 0.0);
            }
        }

        let was_on = self.trip.truck.engine_on;
        let was_air_ready = self.trip.truck.air_ready();
        let was_low_air = self.trip.truck.air_low_warning();
        let was_spring_brake = self.trip.truck.spring_brakes_active();
        self.trip.truck.update(dt);
        self.update_air_brake_announcements(
            ctx,
            was_on,
            was_air_ready,
            was_low_air,
            was_spring_brake,
        );
        if was_on && !self.trip.truck.engine_on {
            ctx.audio.engine_stop();
            if self.trip.truck.stalled {
                let text = format!(
                    "The engine stalled. Press {} to restart, and use a lower gear at low speed.",
                    ctx.control_hint("engine")
                );
                ctx.say_event_with(text, SayEvent::new().category(SpeechCategory::Safety));
            } else if self.trip.truck.fuel_gal <= 0.0 {
                self.handle_out_of_fuel(ctx);
            }
        }

        // Keep the trip's spoken-distance units in step with a live settings
        // change; the setter only re-renders cues when the choice actually flips.
        self.trip.set_imperial(ctx.settings.imperial_units);
        let pos_before = self.trip.position_mi;
        // Same-lane traffic checks and spoken relative lanes follow the
        // player's discrete lane, so mirror it before the trip advances.
        self.trip.traffic_manager.player_lane = self.lane.lane;
        // And while a tap-change is underway, lead selection follows the
        // lane it is moving into instead -- see TrafficManager.lead_vehicle.
        self.trip.traffic_manager.player_lane_target = self.lane_change_target;
        // Tell the trip model which stop's exit is signaled or on the ramp so its
        // plan-cancelled warning can tell a driver who is taking the exit from one
        // who blew past it. Set before trip.update (which runs check_stops) and
        // before update_exit (which clears exit_stop on a miss), so on the exact
        // crossing tick the flag still reflects the armed exit.
        let active_exit = self.ramp_stop.clone().or_else(|| self.exit_stop.clone());
        self.trip.exit_in_progress = active_exit.as_ref().map(|stop| stop.key());
        // On the ramp the highway odometer holds and the ramp consumes the
        // movement instead; the trip records how far the truck rolled either way.
        self.trip.on_ramp = self.ramp_mi.is_some();
        for event in self.trip.update(dt) {
            self.handle_trip_event(ctx, &event);
        }
        if self.selected_stop_key.is_some()
            && self.trip.planned_stop_key != self.selected_stop_key
            && self.ramp_stop.is_none()
        {
            // The trip model canceled a passed plan. Do not leave explicit
            // intent or its stopping assist armed for a later optional exit.
            self.clear_selected_stop_intent();
        }
        self.check_weigh_station_enforcement(ctx, pos_before);
        self.check_unsafe_damage_enforcement(ctx);
        self.check_destination_exit(ctx);
        self.check_gate_approach_warning(ctx, dt);
        self.update_turn_commitment(ctx, dt);
        let moved_mi = self.trip.last_moved_mi;
        self.update_exit(ctx, moved_mi, dt);
        self.update_departure_ramp(ctx, moved_mi);
        // Immediately after the exit watch, which is what turns a signaled
        // scale exit into a ramp. Only now can a scale crossing be told apart
        // from a check-in.
        self.resolve_weigh_station_bypass(ctx);
        // Reads the same last_moved_mi the exit watch just used, so the
        // distance it counts back is the distance the trip actually lost.
        self.update_wrong_way(ctx, dt);
        // After the trip has moved the truck and stepped the bubble, so the
        // crossing this reads is the one that just happened.
        self.update_traffic_passes(ctx, dt);
        // Right after the passes, and for the same reason: the lane the driver
        // moved out of is only open once the bubble has been stepped.
        self.update_lane_gap(ctx, dt);

        self.update_hours_and_fatigue(ctx, dt);
        self.update_audio(ctx, dt);
        self.update_announcements(ctx, dt);
        self.update_ambient_events(ctx, dt);
        self.update_ramp_light(ctx, dt);
        self.update_critical_respeak(ctx, dt);
        self.update_hazard(ctx, dt);
        self.update_grade_advisory(ctx);
        self.update_microsleep(ctx, dt);
        // Damage bands run before the over-rev warning, so a redline call in
        // the same frame already names the band the truck just entered.
        self.update_damage_bands(ctx, dt);
        self.update_cargo_condition(ctx, dt);
        // After the cargo pass, so the bend's advisory is already on the truck
        // for the lateral wave. Returns immediately on any non-tank load.
        self.update_liquid_cues(ctx, dt);
        self.update_overrev(ctx, dt);
        // The watch runs first on purpose. If an officer opens a pull-over
        // this frame, update_speeding returns early on the live stop, so one
        // instance of speeding can never be charged twice -- once as a ticket
        // and again as a silent at-delivery strike.
        self.update_enforcement_watch(ctx, dt);
        self.update_speeding(ctx, dt, accel_held);
        self.update_engine_brake_zone(ctx, dt);
        self.update_pull_over(ctx, dt, braking || emergency);
        self.update_brake_heat_cue(ctx, dt);
        self.update_traction_cues(ctx);
        self.update_chain_law(ctx);
        // The destination approach assist used to run here -- after the
        // physics step, which is why its brake never reached the truck. It
        // now runs with the other assists' pedal floors, ahead of t.update().
        if let Some(tutorial) = self.tutorial.as_mut() {
            tutorial.update(ctx, dt, &self.trip.truck);
        }
        if self.trip.finished {
            self.gate_reminder_s = (self.gate_reminder_s - dt).max(0.0);
            if self.departure_chain {
                // End of the origin's streets: merge onto the highway trip.
                self.finish_departure_chain(ctx);
            } else if self.phase == DRIVE_PHASE_PICKUP {
                self.handle_pickup_gate(ctx);
            } else if self.ramp_mi.is_some() {
                // The ramp watch owns the arrival, so a trip that finishes
                // under the truck here is not the gate (Python `return`).
            } else if !self.destination_exit_taken {
                self.handle_missed_destination_exit(ctx);
            } else {
                self.handle_arrival_gate(ctx);
            }
        }
    }

    /// Mirror the readings a `say_event(valid=...)` gate needs (see
    /// [`crate::states::driving_updates::live`]).
    ///
    /// Public because a test that moves the truck by hand has to stand in for
    /// the frame that would otherwise have carried the reading across.
    pub fn refresh_live_facts(&self) {
        live::set_overspeed_active(self.overspeed_active);
        live::set_pull_over_active(self.trip.pull_over_active);
        live::set_damage_pct(self.trip.truck.damage_pct);
        live::set_position_mi(self.trip.position_mi);
        live::set_speed_mph(self.trip.truck.speed_mph());
        live::set_hazard_active(self.hazard_deadline.is_some());
        live::set_arrival_menu_open(self.arrival_menu_open);
    }
}
