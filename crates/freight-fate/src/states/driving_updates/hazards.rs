//! The braking budget, automatic emergency braking, hazard resolution, the
//! horn's one real power, the routine speed announcement, and the grade
//! advisory.

use ff_core::pyrandom::PyRandom;
use ff_core::sim::driving_modes::tuning_for_time_scale;
use ff_core::sim::trip_models::HAZARDS;
use ff_core::speech_pacing::{EventPriority, SpeechCategory};
use ff_core::speech_text::terse_silent;

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;
use crate::states::driving_updates::live;

impl DrivingState {
    pub fn update_announcements(&mut self, ctx: &mut GameContext, dt: f64) {
        if ctx.settings.renders_terse() {
            return;
        }
        self.speed_announce_timer += dt;
        let interval = tuning_for_time_scale(self.trip.time_scale).routine_speech_interval_s;
        if self.speed_announce_timer >= interval {
            self.speed_announce_timer = 0.0;
            let mph = self.trip.truck.speed_mph();
            if (mph - self.last_announced_mph).abs() >= 5.0 && mph > 1.0 {
                self.last_announced_mph = mph;
                ctx.say_event_with(
                    ctx.settings.speed_text(mph),
                    SayEvent::queued().category(SpeechCategory::Status),
                );
            }
        }
    }

    /// Seconds of full service braking to reach the given safe speed.
    ///
    /// Uses the braking the truck can actually deliver right now -- fade,
    /// wear, load, and grip -- helped uphill and hurt downhill. The rated
    /// spec number engaged the assist two seconds before a collision on
    /// hot brakes (playtest transcript, 2026-07-16).
    pub fn brake_budget_s(&self, target_mph: f64) -> f64 {
        let t = &self.trip.truck;
        let over_mps = 0.0f64.max((t.speed_mph() - target_mph) / MPH_PER_MPS);
        let decel = t.full_service_decel_mps2() + G * t.grade;
        over_mps / decel.max(0.5)
    }

    /// Time-to-hazard at which automatic braking has to take the truck.
    ///
    /// The physics budget plus its lead: braking heats the brakes, so the
    /// stop the budget just predicted gets slower while it happens.
    pub fn aeb_engage_s(&self, target_mph: f64) -> f64 {
        self.brake_budget_s(target_mph) * AEB_BUDGET_MARGIN + AEB_LEAD_S
    }

    /// Time-to-hazard that leaves the driver `window_s` of their own.
    ///
    /// Built forward from the moment the assist must act rather than back
    /// from raw braking physics. The old form -- budget plus slack -- made
    /// the driver's window a remainder: the assist's engage margin scales
    /// with the budget, so speed, grade, brake heat, wear and grip all came
    /// out of the driver's time instead of the truck's. At 65 mph on a
    /// traffic warning that remainder was half a second, and on hot brakes
    /// it was already spent when the words started (Munchkinbear, 2026-08-11).
    ///
    /// `dodgeable` defaults to the currently pending hazard's own flag, but
    /// a hazard arming while another is still live needs its OWN budget
    /// computed on ITS OWN dodgeable-ness -- before `hazard_dodgeable` is
    /// folded with the pending one -- so the caller can pass it explicitly.
    pub fn hazard_deadline_for(&self, window_s: f64, dodgeable: Option<bool>) -> f64 {
        let dodgeable = dodgeable.unwrap_or(self.hazard_dodgeable);
        let mut window = window_s.max(HAZARD_MIN_REACTION_S);
        if dodgeable {
            // The warning offers a lane change; leave room to actually make one.
            window += LANE_TAP_CHANGE_S;
        }
        self.aeb_engage_s(self.hazard_target_mph(Some(dodgeable))) + window
    }

    /// Whether a lane change already in progress will land in time.
    ///
    /// A driver mid-drift has answered the warning, and grabbing the truck
    /// out from under them is the assist overriding the very move it asked
    /// for. Only while the move can still land: a dodge that no longer
    /// beats the hazard is not a plan, and braking is what is left.
    pub fn dodge_still_beats_the_hazard(&self) -> bool {
        if self.lane_change_target.is_none() || !self.hazard_dodgeable {
            return false;
        }
        let Some(deadline) = self.hazard_deadline else {
            return false;
        };
        self.lane_change_timer <= deadline
    }

    /// Put the assist's held application back on the pedal before physics.
    ///
    /// The input pass ramps the service brake down every frame nobody is on
    /// it, and writes the emergency flag straight from the B key -- both
    /// before `truck.update()` runs, and both ahead of `update_hazard`,
    /// which is the frame's last word on the hazard. An assist that only
    /// wrote the pedal from there handed the drums an application a frame's
    /// ramp short of the full one its budget assumed, framerate-dependently
    /// so; its emergency flag never survived to be read at all; and the air
    /// system, which charges a whole brake application every time the pedal
    /// RISES, was billed for the difference again and again. Re-asserted here
    /// beside the other assists' floors, one held stop costs one application.
    pub fn apply_hazard_brake(&mut self) {
        if self.aeb_brake <= 0.0 {
            return;
        }
        // Never brake against our own throttle: a hazard assist that has taken
        // the truck has taken the throttle with it.
        self.trip.truck.throttle = 0.0;
        self.trip.truck.brake = self.trip.truck.brake.max(self.aeb_brake);
        if self.aeb_emergency {
            self.trip.truck.emergency_brake = true;
        }
    }

    /// Hand the pedal back, and forget what the last stop measured.
    ///
    /// The assist releases what the assist applied. The input pass also
    /// stomps the emergency flag from the B key every frame, but nothing says
    /// a frame of input runs between engage and clear -- and an application
    /// with no owner left the truck standing on everything for good. A
    /// driver-held B is untouched: only the assist's own flag is dropped.
    pub fn release_hazard_brake(&mut self) {
        if self.aeb_emergency {
            self.trip.truck.emergency_brake = false;
        }
        self.aeb_brake = 0.0;
        self.aeb_emergency = false;
        self.aeb_hold_s = 0.0;
        self.aeb_losing_s = 0.0;
        self.aeb_decel_mps2 = 0.0;
        self.aeb_last_speed_mps = None;
        self.automatic_braking_announced = false;
        self.automatic_braking_escalated = false;
    }

    /// Smooth the deceleration the truck is actually making right now.
    ///
    /// The budget answers what a full application ought to deliver. What the
    /// escalation needs is a different question nobody can predict: whether
    /// the stop already underway is going to get there. Measured off the
    /// truck's own speed and smoothed just enough that a shift, a gust or a
    /// single long frame is not read as a losing stop.
    pub fn track_assisted_deceleration(&mut self, dt: f64) {
        let speed = 0.0f64.max(self.trip.truck.velocity_mps);
        let last = self.aeb_last_speed_mps;
        self.aeb_last_speed_mps = Some(speed);
        let Some(last) = last else {
            return;
        };
        if self.aeb_brake <= 0.0 || dt <= 0.0 {
            return;
        }
        self.aeb_hold_s += dt;
        let sample = (last - speed) / dt;
        let blend = 1.0f64.min(dt / AEB_DECEL_SMOOTHING_S);
        self.aeb_decel_mps2 += (sample - self.aeb_decel_mps2) * blend;
    }

    /// Whether the stop actually underway is going to miss the hazard.
    ///
    /// Not a prediction. The time left, measured against the deceleration the
    /// truck is making with everything already on, and asked to keep the same
    /// fifth of the stop in hand that the engage point was given. A full
    /// service application that is delivering can never trip this: the assist
    /// engages with that margin and a delivering truck holds it, because road
    /// and air drag add to the budget rather than taking from it. What trips
    /// it is losing ground -- drums cooking under the very application meant
    /// to save the stop, a grade steepening under the wheels, grip that is not
    /// there. Then, and only then, the assist uses the hardest stop the rig
    /// has: the same one the B key gives the driver, and what the driver
    /// facing an unavoidable collision would do.
    pub fn service_braking_is_losing(&mut self, dt: f64) -> bool {
        if self.aeb_emergency {
            return true; // earned once, held to the end of the stop
        }
        let Some(deadline) = self.hazard_deadline else {
            self.aeb_losing_s = 0.0;
            return false;
        };
        if self.aeb_hold_s < AEB_DECEL_SMOOTHING_S {
            self.aeb_losing_s = 0.0;
            return false;
        }
        let over_mps =
            0.0f64.max((self.trip.truck.speed_mph() - self.hazard_target_mph(None)) / MPH_PER_MPS);
        let left_s = deadline.max(0.0);
        if self.aeb_decel_mps2 * left_s >= over_mps * AEB_BUDGET_MARGIN {
            self.aeb_losing_s = 0.0;
            return false;
        }
        self.aeb_losing_s += dt;
        self.aeb_losing_s >= AEB_ESCALATE_CONFIRM_S
    }

    /// The speed that resolves the active hazard by brake alone.
    ///
    /// A fixed object in your lane (dodgeable) cannot be rolled over at the
    /// moving-hazard safe speed: it takes nearly a stop, then easing around.
    /// Defaults to the currently pending hazard's own flag; see
    /// `hazard_deadline_for` for why a caller would pass one explicitly.
    ///
    /// A VEHICLE IS NOT A FIXED OBJECT. Brake lights ahead are emitted
    /// dodgeable too -- you can steer around them -- and that put a moving
    /// truck under the same near-stop rule as a tyre carcass. With automatic
    /// braking the truck obeys without the driver choosing it, so Brandon was
    /// dragged from 70 to nearly stopped sixteen times in ninety minutes on
    /// an open 75 interstate, each costing more than a minute to climb back:
    /// "cruise control still drops speed dramatically... and never comes back
    /// up" (2026-08-23). Matching the vehicle ahead is what a driver actually
    /// does, and it clears the hazard honestly -- you are no longer closing
    /// on it. Never below the creep floor, so a lead that has itself stopped
    /// still asks for a stop.
    pub fn hazard_target_mph(&self, dodgeable: Option<bool>) -> f64 {
        if !dodgeable.unwrap_or(self.hazard_dodgeable) {
            return HAZARD_SAFE_MPH;
        }
        match self.hazard_lead_mph {
            Some(lead_mph) => HAZARD_CREEP_MPH.max(lead_mph),
            None => HAZARD_CREEP_MPH,
        }
    }

    // -- grades ---------------------------------------------------------------------

    /// How to get down a hill, in terms of the controls this driver has.
    ///
    /// An automatic has no gear selection -- W, Q, N and Backspace are all
    /// manual-only -- so telling that driver to pick a gear names a control
    /// they do not have. What they do have is the same one a real automated
    /// box gives them: brake, and the transmission holds a lower gear for
    /// them (`auto_shift` picks the tallest gear landing in the 1050-1700
    /// band while braking, and never upshifts off the pedal).
    pub fn descend_advice(&self, ctx: &GameContext) -> String {
        let jake = ctx.control_hint("engine_brake");
        if self.trip.truck.transmission.automatic {
            return format!(
                "Set the engine brake with {jake} and brake down to speed before it starts; the \
                 transmission will hold a lower gear."
            );
        }
        format!("Pick your gear and set the engine brake with {jake} before it starts.")
    }

    /// How far a grade of this sign keeps its character from `start_mi`.
    ///
    /// Sampled at the stride the baked grade segments use, so the answer is
    /// the run the road data actually has rather than an interpolation of it.
    pub fn grade_run_mi(&self, start_mi: f64, sign: i32) -> f64 {
        let mut run = 0.0;
        let mut probe = start_mi;
        while run < GRADE_WARN_SCAN_MI {
            probe += GRADE_WARN_STEP_MI;
            if probe >= self.trip.total_miles() {
                break;
            }
            if self.trip.grade_at(probe) * sign as f64 * 100.0 < GRADE_WARN_CLEAR_PCT {
                break;
            }
            run += GRADE_WARN_STEP_MI;
        }
        run
    }

    /// Call out a steep grade before the truck is committed to it.
    ///
    /// A downgrade is the one piece of road a driver has to plan for -- gear
    /// and retarder chosen at the top, not halfway down -- and nothing spoke
    /// it. Cruise would quietly run well over the set speed and the first
    /// news of the hill was the speeding warning (playtest, 2026-07-27).
    /// One advisory per grade, cleared once the road flattens out.
    ///
    /// Terse speech gets none of them. A driver on terse has asked for the
    /// road to stay quiet, and the grade is available on demand from the G
    /// key any time they want it -- so this is exactly the kind of unrequested
    /// commentary the setting exists to remove. Cruise still speaks up when a
    /// grade has beaten it, terse or not: that one is not commentary, it is
    /// the controller reporting it has stopped doing its job.
    pub fn update_grade_advisory(&mut self, ctx: &mut GameContext) {
        if self.terse_speech(ctx) {
            return;
        }
        if self.trip.finished || self.trip.truck.speed_mph() < GRADE_WARN_MIN_MPH {
            return;
        }
        // Sampling the road profile is a scan over the leg's baked segments, so
        // it runs per tenth of a mile rather than per frame. The advisory looks
        // three quarters of a mile ahead; a tenth of that is no delay at all.
        if (self.trip.position_mi - self.grade_scan_mi).abs() < GRADE_WARN_RESCAN_MI {
            return;
        }
        self.grade_scan_mi = self.trip.position_mi;
        let here_pct = self.trip.grade_at(self.trip.position_mi) * 100.0;
        let ahead_mi = self.trip.position_mi + GRADE_WARN_LOOKAHEAD_MI;
        let ahead_pct = if ahead_mi < self.trip.total_miles() {
            self.trip.grade_at(ahead_mi) * 100.0
        } else {
            here_pct
        };
        // Take whichever of here and just-ahead is steeper, so a grade that
        // starts under the wheels is called out as promptly as one seen coming.
        let from_ahead = ahead_pct.abs() >= here_pct.abs();
        let pct = if from_ahead { ahead_pct } else { here_pct };
        if pct.abs() < GRADE_WARN_CLEAR_PCT {
            // Level both here and just ahead: between hills, so the next one
            // earns a cue. Clearing on the flat under the wheels alone re-armed
            // the advisory on every frame of the approach to a hill, which
            // spoke it over and over until the wheels reached the slope.
            self.grade_warned_sign = 0;
            return;
        }
        if pct.abs() < GRADE_WARN_PCT {
            return;
        }
        let sign = if pct > 0.0 { 1 } else { -1 };
        if self.grade_warned_sign == sign {
            return;
        }
        let run_mi = self.grade_run_mi(
            if from_ahead {
                ahead_mi
            } else {
                self.trip.position_mi
            },
            sign,
        );
        if run_mi < GRADE_WARN_MIN_RUN_MI {
            // A dip, not a hill. Deliberately without latching: a short blip
            // must not swallow the advisory for the real grade behind it.
            return;
        }
        self.grade_warned_sign = sign;
        // The scan gives up at its horizon, so say so rather than claiming the
        // grade ends exactly there.
        let about = if run_mi >= GRADE_WARN_SCAN_MI {
            "at least "
        } else {
            ""
        };
        let length = format!(" for {about}{}", self.trip.distance_text(run_mi));
        let direction = if sign > 0 { "upgrade" } else { "downgrade" };
        ctx.audio.play_with("ui/notify", 0.55, 0.0);
        let advice = if sign < 0 {
            self.descend_advice(ctx)
        } else {
            "Expect to lose speed.".to_string()
        };
        ctx.say_event_with(
            format!(
                "{:.1} percent {direction} ahead{length}. {advice}",
                pct.abs()
            ),
            SayEvent::queued()
                .priority(EventPriority::Route)
                .category(SpeechCategory::Navigation),
        );
    }

    /// The horn's one real power: moving an animal off the road.
    ///
    /// Shane's ask (2026-08-20), and it is what the air horn is FOR on a
    /// real highway -- but it works the way animals work, not the way a
    /// button works. Livestock, dogs, and coyotes mostly move; deer and
    /// elk freeze as often as they bolt, which is why braking stays the
    /// instruction and the horn is a bonus, never the plan. One attempt
    /// per hazard: an animal that ignored the first blast has decided.
    /// Seeded on the hazard so a save-scummed retry hears the same deer
    /// make the same choice.
    pub fn horn_scare_animals(&mut self, ctx: &mut GameContext) {
        if self.hazard_deadline.is_none() || self.horn_scare_tried {
            return;
        }
        let names: Vec<String> = self
            .hazard_names
            .iter()
            .filter(|name| {
                HAZARDS
                    .iter()
                    .any(|hazard| hazard.animal && hazard.name == name.as_str())
            })
            .cloned()
            .collect();
        if names.is_empty() {
            return; // a ladder does not care how loud you are
        }
        self.horn_scare_tried = true;
        let mut rng =
            PyRandom::new_from_i64((self.trip_seed << 8) ^ (self.trip.position_mi * 50.0) as i64);
        let mut cleared = true;
        for name in &names {
            let freeze_prone = name == "the deer" || name == "the elk";
            let threshold = if freeze_prone { 0.4 } else { 0.7 };
            if rng.random() >= threshold {
                cleared = false;
            }
        }
        if !cleared || names.len() != self.hazard_names.len() {
            // Frozen in the headlights, or something unscareable is out
            // there too. Say nothing: the hazard machinery's own countdown
            // is still the instruction, and a "it did not work" line would
            // talk over the braking the driver should be doing.
            return;
        }
        let text = format!(
            "The horn does it: {} clears the road. Well done.",
            self.hazard_names_text()
        );
        self.finish_hazard_clear(ctx, &text);
    }

    /// The pending hazard(s), joined for a resolution line.
    ///
    /// Falls back to "it" when nothing was recorded -- a hazard armed by
    /// test or tool code that pokes `hazard_deadline` directly rather
    /// than going through `handle_trip_event` -- so the old generic
    /// wording still comes out rather than an empty name.
    pub fn hazard_names_text(&self) -> String {
        let names = &self.hazard_names;
        match names.len() {
            0 => "it".to_string(),
            1 => names[0].clone(),
            2 => format!("{} and {}", names[0], names[1]),
            _ => format!(
                "{}, and {}",
                names[..names.len() - 1].join(", "),
                names[names.len() - 1]
            ),
        }
    }

    pub fn hazard_resolution_text(&self) -> String {
        let names = self.hazard_names_text();
        if self.hazard_dodgeable {
            return format!("You slow nearly to a stop and ease around {names}. Well done.");
        }
        if names == "it" {
            return "Hazard avoided. Well done.".to_string();
        }
        format!("Past {names}. Well done.")
    }

    /// Common tail of every way a pending hazard can resolve: brake,
    /// swerve, or an earlier hazard outrun before a new one armed.
    pub fn finish_hazard_clear(&mut self, ctx: &mut GameContext, message_text: &str) {
        self.hazard_deadline = None;
        // The lead belonged to the hazard that just ended; a fresh one must
        // not inherit it, or a tyre carcass would clear at the speed of a
        // truck that is long gone.
        self.hazard_lead_mph = None;
        // Everything below here can offer the hazard call its rescue -- the
        // clear line's own flush, or any urgent line that lands before the
        // next tick. That gate asks whether a hazard is still armed, so the
        // reading has to move with the deadline rather than wait for the next
        // frame: judged on last tick's answer it replays "Change lanes or
        // brake!" for a hazard that has just been dodged.
        self.refresh_live_facts();
        self.release_hazard_brake();
        self.hazard_slow_hint_said = false;
        ctx.audio.play_with("events/hazard_clear", 0.75, 0.0);
        ctx.controller
            .rumble
            .alert_with(0.4, ff_core::rumble::ALERT_DURATION_MS);
        let message = terse_silent(message_text);
        self.last_event_message = message.normal.clone();
        // ROUTE, not the ambient default: this is the outcome of a SAFETY
        // event the driver just acted on, and at AMBIENT it queued behind
        // the urgent call that preceded it and was dropped as stale -- in
        // STANDARD mode, where confirmations are supposed to speak in full
        // (Shane, Killeen-Del Rio run, 2026-08-20: found the swerve-clear
        // only in the review keys). Same promotion the creep guidance and
        // the ramp-light family already earned for the same failure.
        ctx.say_event_with(
            message,
            SayEvent::queued()
                .priority(EventPriority::Route)
                .category(SpeechCategory::Confirmation),
        );
        ctx.award_achievement("hazard_avoided");
        self.hazard_names.clear();
    }

    /// Speak and reset the pending hazard(s) as cleared by braking.
    ///
    /// Shared by the per-frame resolution below and an early resolution
    /// triggered from `handle_trip_event` when a fresh hazard arms
    /// while an earlier one was already outrun -- either way the driver
    /// gets exactly one clean "you made it" line naming what it was for.
    ///
    /// In terse the hazard-clear earcon IS the confirmation; the words are
    /// congratulation, and the failure outcome stays distinct as the
    /// collision sound plus its spoken damage line (R4, R14).
    pub fn clear_hazard(&mut self, ctx: &mut GameContext) {
        let text = self.hazard_resolution_text();
        self.finish_hazard_clear(ctx, &text);
    }

    pub fn update_hazard(&mut self, ctx: &mut GameContext, dt: f64) {
        if self.hazard_deadline.is_none() {
            return;
        }
        let target = self.hazard_target_mph(None);
        if self.trip.truck.speed_mph() <= target {
            self.clear_hazard(ctx);
            return;
        }
        // Old instinct says 25 clears everything; for a fixed object it no
        // longer does. Braking past the moving-hazard speed with the object
        // still in the lane earns the how-to once, so the quiet is never
        // read as an already-cleared hazard.
        if self.hazard_dodgeable
            && !self.hazard_slow_hint_said
            && self.trip.truck.speed_mph() <= HAZARD_SAFE_MPH
        {
            self.hazard_slow_hint_said = true;
            // "Or change lanes" only names a maneuver this road offers; a
            // one-lane stretch, or a two-lane one with the other lane coned
            // off, gets nearly-stop as the whole answer.
            let hint = if self.trip.has_open_adjacent_lane_at(None) {
                "It is still in your lane. Nearly stop, or change lanes."
            } else {
                "It is still in your lane. Nearly stop."
            };
            // ROUTE: not interrupting (it follows the hazard call rather
            // than cutting it) but never droppable. A live hazard still in
            // your lane telling you to nearly stop is the last line in the
            // game that may be binned as stale chatter -- and the stale-drop
            // branch tests PRIORITY, never category, so SAFETY at the ambient
            // default was droppable in exactly the busy moment it matters.
            ctx.say_event_with(
                hint,
                SayEvent::queued()
                    .priority(EventPriority::Route)
                    .category(SpeechCategory::Safety),
            );
        }
        let deadline = self.hazard_deadline.unwrap_or(0.0) - dt;
        self.hazard_deadline = Some(deadline);
        self.track_assisted_deceleration(dt);
        let assist_may_act =
            ctx.settings.automatic_emergency_braking && !self.dodge_still_beats_the_hazard();
        if !assist_may_act {
            // A driver mid-drift has answered the warning, and an assist the
            // driver has switched off has no truck to take.
            self.release_hazard_brake();
        } else if self.aeb_brake > 0.0 || deadline <= self.aeb_engage_s(target) {
            if self.aeb_brake <= 0.0 {
                // Seed the measurement with the stop the budget has just
                // promised, so the smoothing starts from an honest prior
                // instead of climbing out of a standstill and reading the
                // first fifth of a second of a good stop as a failure.
                self.aeb_decel_mps2 = 0.0f64
                    .max(self.trip.truck.full_service_decel_mps2() + G * self.trip.truck.grade);
                self.aeb_hold_s = 0.0;
                self.aeb_losing_s = 0.0;
            }
            // Full SERVICE braking, and once it is on it stays on until the
            // hazard is answered. Deciding it afresh every frame is what fanned
            // the pedal: the assist's own braking retreats the very threshold
            // that engaged it, so it let go, the threshold came back, and the
            // air system was charged a whole brake application every time round
            // -- which is how ordinary assisted driving ran the tanks down.
            self.aeb_brake = 1.0;
            // And the emergency application stays a genuine last resort, judged
            // on the deceleration the truck is actually making rather than on
            // the one a full application ought to deliver.
            if self.service_braking_is_losing(dt) {
                self.aeb_emergency = true;
            }
            self.apply_hazard_brake();
            if !self.automatic_braking_announced {
                self.automatic_braking_announced = true;
                // Kept out of the reviewable log: this line interrupts the
                // hazard warning, and the review keys exist to give that
                // warning back, not the assist that talked over it.
                ctx.say_event_with(
                    "Automatic braking.",
                    SayEvent::new()
                        .review(false)
                        // The assist reporting that IT acted, not a demand on
                        // the driver -- the braking is audible and the hazard
                        // warning that preceded it carried the action. At
                        // quiet, where the rule is "speak what the player must
                        // do something about" (owner, 2026-08-17), that makes
                        // it an earcon. The hazard call itself stays SAFETY
                        // and speaks at every rung.
                        .category(SpeechCategory::Confirmation),
                );
            } else if self.aeb_emergency && !self.automatic_braking_escalated {
                self.automatic_braking_escalated = true;
                ctx.say_event_with(
                    "Emergency braking engaged.",
                    SayEvent::new()
                        .review(false)
                        .category(SpeechCategory::Safety),
                );
            }
            if self.cruise_mph.is_some() {
                self.cancel_cruise(ctx, false);
            }
        }
        if self.hazard_deadline.unwrap_or(0.0) <= 0.0 {
            self.hazard_deadline = None;
            self.refresh_live_facts(); // same reason as `finish_hazard_clear`
            self.release_hazard_brake();
            ctx.audio.play("vehicle/collision");
            let mut severity = 1.0f64.min(self.trip.truck.speed_mph() / 70.0);
            severity *= tuning_for_time_scale(self.trip.time_scale).collision_damage;
            ctx.controller.rumble.impact(severity);
            self.trip.truck.apply_collision(severity, true);
            let mut message = format!(
                "Collision! The truck took damage. Total damage {:.0} percent.",
                self.trip.truck.damage_pct
            );
            // A dodgeable hazard's announcement leaves the session armed --
            // see `handle_trip_event` -- on the promise that only braking
            // ends it: the driver's own, or AEB's (which already cancels the
            // instant it takes the pedal, above). With AEB off and no dodge
            // and no brake, neither of those ever fires, and the hazard rode
            // cruise straight into the collision with the session still
            // showing armed (reviewer-caught regression on the announce-time
            // fix, 2026-08-14). The deadline lapsing un-dodged is the third
            // way the promise ends, whatever the AEB setting -- the hazard
            // stopped being answerable the moment it hit the truck.
            if self.speed_control_armed || self.cruise_mph.is_some() || self.keeper_mph.is_some() {
                self.disarm_speed_control(ctx);
                message = format!("{message} Automatic speed control canceled.");
            }
            self.last_event_message = message.clone();
            // valid: a damage total is only true at the moment it was
            // computed. A rescue replaying it after ANOTHER collision stated
            // a percentage the truck had already left behind (adversarial
            // battery: "spoke 44% while the truck was at 51%").
            let spoken_pct = self.trip.truck.damage_pct;
            self.refresh_live_facts();
            ctx.say_event_with(
                message,
                SayEvent::new()
                    .category(SpeechCategory::Safety)
                    .valid(move || (live::damage_pct() - spoken_pct).abs() < 0.5),
            );
        }
    }
}
