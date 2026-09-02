//! The pull-over itself: its compliance tracker, the staged failure-to-stop
//! warnings, the roadside screens a settled stop pushes, and the deliberate
//! opt-in to run from one.

use ff_core::models::enforcement::FAILURE_TO_STOP_CITATION_FINE;
use ff_core::speech_pacing::SpeechCategory;

use crate::app::{GameContext, SayEvent};
use crate::states::base::Key;
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;
use crate::states::driving_updates::live;
use crate::states::driving_updates::pending::EnforcementStopParams;

impl DrivingState {
    /// Clear the compliance tracker on every stop-ending path so the next
    /// stop starts clean.
    pub fn reset_pull_over_tracker(&mut self) {
        self.pull_over_compliance = 0.0;
        self.pull_over_elapsed = 0.0;
        self.pull_over_prev_mph = 0.0;
        self.pull_over_coast_s = 0.0;
        self.pull_over_signal_boost = false;
        self.pull_over_nosignal_hit = false;
    }

    /// Judge the stop by behavior, and warn by distance. A compliance
    /// tracker (0..1) rises with braking and falls with accelerating,
    /// coasting, and failing to signal (deductions stack); a full stop opens
    /// the roadside stop and zeroing it out ends in a felony. On top of that,
    /// the staged failure-to-stop warnings still speak as the miles roll by,
    /// and simply driving miles on with the lights behind you is a felony
    /// regardless of the tracker.
    pub fn update_pull_over(&mut self, ctx: &mut GameContext, dt: f64, service_braking: bool) {
        if self.pull_over.is_none() {
            return;
        }
        if self.enforcement_bypassed(ctx) {
            self.pull_over = None;
            self.trip.pull_over_active = false;
            self.refresh_live_facts();
            self.end_stop_audio(ctx);
            return;
        }
        // Re-asserted every frame the cruiser is there, and released by its own
        // dead man's switch the moment this stops being called.
        self.hold_stop_siren(ctx);
        if self.trip.truck.speed_mph() <= DOCKING_MAX_MPH {
            self.open_traffic_stop(ctx);
            return;
        }
        // Nothing is judged until the instruction has finished being spoken
        // and the player has had real reaction seconds on top of it.
        if self.pull_over_grace_s > 0.0 {
            self.pull_over_grace_s = (self.pull_over_grace_s - dt).max(0.0);
            self.pull_over_prev_mph = self.trip.truck.speed_mph();
            self.pull_over_start_mi = self.trip.position_mi;
            return;
        }
        self.pull_over_elapsed += dt;
        let speed = self.trip.truck.speed_mph();
        let accel_mph_s = if dt > 0.0 {
            (speed - self.pull_over_prev_mph) / dt
        } else {
            0.0
        };
        self.pull_over_prev_mph = speed;
        let mut delta = 0.0;
        if service_braking {
            // Compliant deceleration. Method-agnostic: service, emergency, or
            // engine+service brake all read the same, and stacking earns no extra.
            delta += PULL_OVER_BRAKE_RATE * dt;
            self.pull_over_coast_s = 0.0;
        } else if accel_mph_s > PULL_OVER_ACCEL_EPS_MPH_S {
            // Genuinely speeding up (not jitter, not throttle-held-steady).
            delta -= PULL_OVER_ACCEL_RATE * dt;
            self.pull_over_coast_s = 0.0;
        } else {
            // Coasting, holding a steady speed, or slowing on the engine brake /
            // grade alone -- all treated the same, and only after a 3 s grace.
            self.pull_over_coast_s += dt;
            if self.pull_over_coast_s >= PULL_OVER_COAST_GRACE_S {
                delta -= PULL_OVER_COAST_RATE * dt;
            }
        }
        // Failing to signal past the grace: a one-time 1/4 hit, then a small
        // periodic drain. Stacks with any accelerating/coasting deduction above.
        if self.pull_over_elapsed > PULL_OVER_SIGNAL_GRACE_S && !self.pull_over_signaled {
            if !self.pull_over_nosignal_hit {
                self.pull_over_nosignal_hit = true;
                delta -= PULL_OVER_NOSIGNAL_HIT;
            }
            delta -= PULL_OVER_NOSIGNAL_RATE * dt;
        }
        self.pull_over_compliance = (self.pull_over_compliance + delta).clamp(0.0, 1.0);
        // Running is a choice, never a consequence of hesitating: only the
        // held opt-in below starts a pursuit.
        self.update_pursuit_optin(ctx, dt);
        if self.pull_over.is_none() {
            return; // the opt-in fired
        }
        // The warnings are on a real-time cadence now. They used to be keyed
        // to trip miles, which compression could burn through before the
        // first one could ever speak.
        let distance = self.trip.position_mi - self.pull_over_start_mi;
        if self.pull_over_elapsed >= PULL_OVER_FINAL_WARNING_S {
            self.warn_failure_to_stop(ctx, true);
        } else if self.pull_over_elapsed >= PULL_OVER_FIRST_WARNING_S {
            self.warn_failure_to_stop(ctx, false);
        }
        // Not stopping is not running. A zeroed tracker or two miles of
        // rolling ends in troopers boxing you in: a failure-to-stop citation
        // and a forced stop, which is expensive and goes on the record -- but
        // it is not a felony, and it cannot end a career by inattention.
        if self.pull_over_compliance <= 0.0 || distance >= PULL_OVER_IGNORE_MI {
            // Escalate through the warnings rather than jumping to the last
            // one: the player hears it getting worse before it is over.
            let final_warning = self.pull_over_warning_level >= 1;
            self.warn_failure_to_stop(ctx, final_warning);
            self.pull_over_forced_s += dt;
            if self.pull_over_forced_s >= PULL_OVER_FORCED_STOP_S {
                self.fail_to_stop(ctx);
            }
        } else {
            self.pull_over_forced_s = 0.0;
        }
    }

    pub fn warn_failure_to_stop(&mut self, ctx: &mut GameContext, final_warning: bool) {
        let level = if final_warning { 2 } else { 1 };
        if self.pull_over_warning_level >= level {
            return;
        }
        self.pull_over_warning_level = level;
        let message = if final_warning {
            "Final failure-to-stop warning. Stop now or troopers end it with spike strips and \
             felony charges."
                .to_string()
        } else if self.pull_over_signaled {
            "Signaled, but still moving with lights behind you. Stop on the shoulder.".to_string()
        } else {
            format!(
                "Failure-to-stop warning. Signal with {} and stop on the shoulder.",
                ctx.control_hint("take_exit")
            )
        };
        ctx.audio.play("ui/warning");
        self.refresh_live_facts();
        ctx.say_event_with(
            message,
            SayEvent::new()
                .category(SpeechCategory::Navigation)
                // Same rule as the stop instruction it escalates: a
                // failure-to-stop warning handed back after the driver HAS
                // stopped threatens spike strips over a stop they already made.
                .valid(live::pull_over_active),
        );
    }

    pub fn open_traffic_stop(&mut self, ctx: &mut GameContext) {
        let signaled = self.pull_over_signaled;
        let over = self.pull_over_over;
        let limit = self.pull_over_limit;
        let kind = self.pull_over_kind.clone();
        let title = self.pull_over_title.clone();
        let summary = self.pull_over_summary.clone();
        let fine = self.pull_over_fine;
        let reputation_hit = self.pull_over_reputation_hit;
        let return_message = self.pull_over_return.clone();
        let construction_zone = self.pull_over_construction_zone;
        // Read the tracker before the reset zeroes it.
        let clean_stop = self.pull_over_compliance >= PULL_OVER_FULL_COMPLIANCE;
        self.trip.pull_over_active = false;
        self.refresh_live_facts();
        self.end_stop_audio(ctx);
        self.settle_engine_to_idle(ctx);
        self.pursuit_hold_s = 0.0;
        // Rolling on through a spoken failure-to-stop warning before finally
        // pulling in is reckless-class behavior, and the record says so.
        let warned = self.pull_over_warning_level > 0;
        self.pull_over = None;
        self.reset_pull_over_tracker();
        if kind != "speeding" {
            self.push_enforcement_stop_state(
                ctx,
                EnforcementStopParams {
                    title,
                    summary,
                    fine,
                    reputation_hit,
                    signaled,
                    return_message,
                    out_of_service: kind == "hos_out_of_service",
                    warned,
                    construction_zone,
                    inspection_on_stop: kind == "weigh_station_bypass",
                },
            );
            self.commit_resolved_stop(ctx);
            return;
        }
        self.push_traffic_stop_state(
            ctx,
            signaled,
            over,
            limit,
            clean_stop,
            warned,
            construction_zone,
        );
        self.commit_resolved_stop(ctx);
    }

    /// Write a settled stop out of the save, the way arming wrote it in.
    ///
    /// `arm_pull_over` commits the encounter before a word of it is spoken so
    /// that nothing can make it never have happened. This is the other half:
    /// once the ticket is written, the save must stop saying a cruiser is
    /// sitting behind you. Without it every resume found the stop still armed
    /// against a parked truck, resolved it on the first frame, and charged
    /// for it again -- at the repeat-offender rate, so it cost more each
    /// time (tester log, 2026-08-10).
    pub fn commit_resolved_stop(&mut self, ctx: &mut GameContext) {
        let has_active_trip = ctx
            .profile
            .as_ref()
            .is_some_and(|profile| profile.active_trip.is_some());
        if !has_active_trip {
            return;
        }
        let snapshot = self.snapshot(ctx);
        profile_mut_of(ctx).active_trip = Some(snapshot);
        ctx.save_profile();
    }

    /// How long the run key must be held. A lifetime disqualification is
    /// the harshest outcome in the game, so it takes twice as long to choose.
    pub fn pursuit_hold_required_s(&self, ctx: &GameContext) -> f64 {
        let second = ctx
            .profile
            .as_ref()
            .is_some_and(|profile| profile.driving_record.major_count() >= 1);
        PURSUIT_HOLD_S * if second { 2.0 } else { 1.0 }
    }

    /// Running from a stop: an affirmative held choice, never an accident.
    ///
    /// A driver who is complying but disoriented -- holding a steady speed
    /// while the instruction is still being read out -- must never be able to
    /// reach a felony. So the tracker running out is a citation and a forced
    /// stop, and the only road to a pursuit is holding this key after being
    /// told exactly what it costs.
    pub fn update_pursuit_optin(&mut self, ctx: &mut GameContext, dt: f64) {
        if self.enforcement_bypassed(ctx) {
            return;
        }
        let holding = ctx.input.is_pressed(Key::X) && ctx.input.mods().shift;
        if !holding {
            if self.pursuit_hold_s > 0.0 {
                self.pursuit_hold_s = 0.0;
                ctx.say_event_with(
                    "Not running. Stop on the shoulder.",
                    SayEvent::new().category(SpeechCategory::Confirmation),
                );
            }
            return;
        }
        let required = self.pursuit_hold_required_s(ctx);
        if self.pursuit_hold_s <= 0.0 {
            let hint = ctx.control_hint("take_exit");
            let major_count = profile_of(ctx).driving_record.major_count();
            let cost = if major_count >= 1 {
                "A second major offense disqualifies your CDL for life, and this career will not \
                 drive again."
            } else {
                "It is a felony, it cancels this load, and it disqualifies your CDL for a year."
            };
            ctx.say_event_with(
                format!(
                    "Hold shift {hint} for {required:.0} seconds to run. {cost} Let go now to \
                     stop instead."
                ),
                SayEvent::new().category(SpeechCategory::Safety),
            );
        }
        self.pursuit_hold_s += dt;
        if self.pursuit_hold_s >= required {
            self.pursuit_hold_s = 0.0;
            self.evade_pull_over(ctx);
        }
    }

    /// Never pulled over, but never ran either: troopers force the stop.
    ///
    /// This is where a zeroed compliance tracker and two miles of rolling
    /// both end. It is expensive and it is a serious violation on the record,
    /// but it is not a felony -- that has its own deliberate opt-in.
    pub fn fail_to_stop(&mut self, ctx: &mut GameContext) {
        let signaled = self.pull_over_signaled;
        self.pull_over = None;
        self.trip.pull_over_active = false;
        self.refresh_live_facts();
        self.end_stop_audio(ctx);
        self.reset_pull_over_tracker();
        self.pursuit_hold_s = 0.0;
        self.trip.truck.brake = 1.0;
        self.trip.truck.velocity_mps = 0.0;
        self.trip.truck.set_parking_brake();
        // Same reasoning as the ordinary pull-over: boxed in and stopped, the
        // engine keeps running but must read as idle for the whole stop, not
        // whatever rev it was carrying when the troopers closed in.
        self.settle_engine_to_idle(ctx);
        ctx.audio.play("ui/error");
        let construction_zone = self.pull_over_construction_zone;
        self.push_enforcement_stop_state(
            ctx,
            EnforcementStopParams {
                title: "Failure-to-stop stop".to_string(),
                summary: "Troopers boxed you in and stopped the truck. Failing to pull over \
                          promptly for an officer is a serious violation."
                    .to_string(),
                fine: FAILURE_TO_STOP_CITATION_FINE,
                reputation_hit: hos::HOS_REPUTATION_HIT * 2.0,
                signaled,
                return_message: "Back on the highway. Pull over promptly next time.".to_string(),
                out_of_service: false,
                warned: true,
                construction_zone,
                inspection_on_stop: false,
            },
        );
        self.commit_resolved_stop(ctx);
    }

    /// The player chose to run and held the key through the warning: spike
    /// strips end it, logged as a major offense with a heavy fine, reputation
    /// hit, and load consequences.
    pub fn evade_pull_over(&mut self, ctx: &mut GameContext) {
        self.pull_over = None;
        self.trip.pull_over_active = false;
        self.refresh_live_facts();
        self.end_stop_audio(ctx);
        self.reset_pull_over_tracker();
        self.pursuit_hold_s = 0.0;
        ctx.audio.play("events/spike_strip");
        self.push_felony_stop_state(ctx);
    }
}
