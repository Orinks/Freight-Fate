//! Arming and adjusting automatic speed control: the cruise dial, the speed
//! keeper, and the keeper's own snubs.

use ff_core::pyfmt::round_py;
use ff_core::speech_pacing::SpeechCategory;
use ff_core::speech_text::SpokenMessage;

use crate::app::{GameContext, Say, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

use crate::states::driving_stops::assist_full_decel_mps2;

use super::pending::{
    KEEPER_EASE_UNDERSHOOT_MPH, KEEPER_OVERRUN_MPH, KEEPER_OVERRUN_S, KEEPER_SNUB_DECEL_MPS2,
    KEEPER_SNUB_MAX_BRAKE, KEEPER_SNUB_MIN_BRAKE, KEEPER_SNUB_OVER_MPH, KEEPER_SNUB_UNDER_MPH,
};

impl DrivingState {
    /// `_toggle_cruise()`: the cruise control, or the fast-idle switch.
    pub fn toggle_cruise(&mut self, ctx: &mut GameContext) {
        // Parked with the brake set, the cruise button is the fast-idle
        // switch, exactly like a real electronic truck: latch a high idle
        // (warm-up, faster air build), press again to drop it. It also
        // cancels on its own the moment the parking brake releases.
        if self.trip.truck.high_idle_allowed() {
            if self.trip.truck.high_idle_rpm.is_none() {
                self.trip.truck.high_idle_rpm = Some(HIGH_IDLE_DEFAULT_RPM);
                let rpm = HIGH_IDLE_DEFAULT_RPM;
                self.say_plain(
                    ctx,
                    format!(
                        "High idle, {rpm:.0} RPM. Plus and minus adjust it; releasing the parking \
                         brake cancels."
                    ),
                );
            } else {
                self.trip.truck.high_idle_rpm = None;
                self.say_plain(ctx, "High idle off.");
            }
            return;
        }
        if self.speed_control_armed || self.keeper_mph.is_some() || self.cruise_mph.is_some() {
            self.disarm_speed_control(ctx);
            self.say_plain(ctx, "Automatic speed control off.");
            return;
        }
        let position = self.trip.position_mi;
        let (limit, zone_reason) = self.trip.speed_limit_at(position);
        if let Some(zone_reason) = zone_reason {
            // Adaptive cruise never runs on facility access roads, gates, work
            // zones, or heavy traffic. The speed keeper covers those low-speed
            // stretches instead, so nobody has to hold the accelerator down.
            self.engage_keeper(ctx, limit, &zone_reason, None, true);
            return;
        }
        if !self.trip.truck.engine_on || self.trip.truck.speed_mph() < CRUISE_MIN_MPH {
            let minimum = ctx.settings.speed_text(CRUISE_MIN_MPH);
            self.say_plain(
                ctx,
                format!("Adaptive cruise needs the engine running and at least {minimum}."),
            );
            return;
        }
        let speed = self.trip.truck.speed_mph();
        self.engage_cruise(ctx, speed, false);
    }

    /// Start adaptive cruise as part of the armed speed-control session.
    pub fn engage_cruise(&mut self, ctx: &mut GameContext, target_mph: f64, transition: bool) {
        let transition_label = transition.then_some("Open road");
        self.engage_cruise_with_transition(ctx, target_mph, transition_label);
    }

    fn engage_departure_cruise(&mut self, ctx: &mut GameContext, target_mph: f64) {
        self.engage_cruise_with_transition(ctx, target_mph, Some("Acceleration lane"));
    }

    fn engage_cruise_with_transition(
        &mut self,
        ctx: &mut GameContext,
        target_mph: f64,
        transition_label: Option<&str>,
    ) {
        self.speed_control_armed = true;
        self.speed_control_paused_at_stop = false;
        // Round to the whole mph the player actually hears (speed_text already
        // rounds the readout): a plain K-set otherwise captures the truck's
        // exact float speed (e.g. 59.95), and the first +/- tap would spend
        // itself just healing that invisible fraction onto the grid instead
        // of making an audible step.
        let set = round_py(target_mph).clamp(CRUISE_MIN_MPH, CRUISE_MAX_MPH);
        self.cruise_mph = Some(set);
        self.speed_control_target_mph = Some(set);
        // An armed exit still ahead keeps its cap across a cruise session.
        // Cancelling cruise clears _cruise_exit_mph, and on the Denver run the
        // descent cancelled it a mile before the ramp; the driver re-engaged
        // at 53 and the fresh session had forgotten the exit entirely, so
        // nothing ever eased for it. The cap is a property of the road ahead,
        // not of the cruise session that happened to be running when the exit
        // was announced -- so re-arming it here rather than leaving it to the
        // announcement, which has already been made and will not repeat.
        if self.cruise_exit_mph.is_none() {
            if let Some(stop) = self.exit_stop.clone() {
                let ahead = stop.at_mi - self.trip.position_mi;
                if ahead > 0.0 && (self.exit_signal_on || ctx.settings.lane_is_automated()) {
                    self.cruise_exit_mph = Some(set.min(self.armed_ramp_cruise_mph(None)));
                }
            }
        }
        // Chase a working setpoint that starts at road speed, so a big resume
        // error eases on rather than landing on the pedal at once. Engaging at
        // the current speed (a plain K-set) seeds it at the target, so there is
        // no ramp to feel.
        let speed = self.trip.truck.speed_mph();
        self.cruise_working_mph = Some(CRUISE_MIN_MPH.max(set.min(speed)));
        self.cruise_throttle = self.trip.truck.throttle;
        self.cruise_applied = self.trip.truck.throttle;
        // Engaging on a grade starts from the feed-forward, so the trim opens
        // at zero rather than carrying a stale wind-up into the new session.
        self.cruise_trim = 0.0;
        self.acc_following = false;
        self.acc_weather_gap_said = false;
        self.acc_limit_capped = false;
        self.acc_limit_cap_said = None;
        self.acc_weather_cap_said = None;
        let gap = self.acc_gap_seconds(ctx);
        let mut effective_mph = match self.cruise_exit_mph {
            Some(exit) => set.min(exit),
            None => set,
        };
        let mut exit_note = if self.cruise_exit_mph.is_some() {
            " for the ramp".to_string()
        } else {
            String::new()
        };
        // Name the number the truck will actually hold. The resume line used
        // to speak the SET speed while a zone cap silently pinned the working
        // target far below it: clear of the visible queue in a heavy-traffic
        // zone posting 20, cruise said "resuming at 70" and held 23 -- the
        // zone's 20 plus the ACC offset -- for the rest of the zone, minutes
        // of open-looking road with the announcement contradicting the truck
        // (Brandon, 2026-08-20). The queue ahead is real even when the bubble
        // happens to be showing empty road; the words just have to match.
        let (posted, limit_reason) = self.acc_posted_limit_ahead(ctx);
        let restricted = limit_reason
            .as_deref()
            .is_some_and(|reason| RESTRICTED_ZONE_REASONS.contains(&reason));
        let cap_mph = if restricted {
            posted
        } else {
            posted + ACC_LIMIT_OFFSET_MPH
        };
        if cap_mph < effective_mph {
            effective_mph = cap_mph;
            exit_note = match limit_reason.as_deref() {
                Some("construction") => " through the construction zone".to_string(),
                Some("heavy traffic") => " through the heavy traffic".to_string(),
                _ => " for the lower limit".to_string(),
            };
        }
        let effects = self.trip.weather.effects();
        if (effects.grip < 1.0 || effects.visibility_mi < 8.0)
            && effects.safe_speed_mph < effective_mph
        {
            effective_mph = effects.safe_speed_mph;
            exit_note = format!(" in the {}", self.trip.weather.current.value());
        }
        ctx.audio.play_with("ui/notify", 0.5, 0.0);
        let message = format!(
            "Adaptive cruise {} at {}{exit_note}. Following gap {gap:.0} seconds. K or braking \
             cancels.",
            if transition_label.is_some() {
                "resuming"
            } else {
                "set"
            },
            ctx.settings.speed_text(effective_mph)
        );
        if let Some(label) = transition_label {
            // ROUTE: automation retaking the pedals after a zone, the same
            // handoff as the keeper's resume line (driving_speed_control 291,
            // already ROUTE). The quiet rung still silences it by category;
            // ROUTE only stops a busy channel eating it at standard.
            self.say_route_confirmation(ctx, &format!("{label}. {message}"));
        } else {
            self.say_plain(ctx, message);
        }
    }

    /// Raise or lower the cruise set point -- the Accel/Coast (+/-) buttons.
    ///
    /// Plain taps walk the fives grid (an off-grid captured speed heals on
    /// the first press); Ctrl taps move by exactly one mile per hour. While
    /// the speed keeper is handling a restricted zone, the same buttons
    /// adjust the open-road target that adaptive cruise will resume. Parked
    /// with high idle latched, they step the idle setpoint instead.
    pub fn adjust_cruise(&mut self, ctx: &mut GameContext, direction: i32, fine: bool) {
        if let Some(rpm) = self.trip.truck.high_idle_rpm {
            if self.trip.truck.high_idle_allowed() {
                let step = if direction > 0 {
                    HIGH_IDLE_STEP_RPM
                } else {
                    -HIGH_IDLE_STEP_RPM
                };
                let rpm = (rpm + step).clamp(HIGH_IDLE_MIN_RPM, HIGH_IDLE_MAX_RPM);
                self.trip.truck.high_idle_rpm = Some(rpm);
                self.say_plain(ctx, format!("High idle {rpm:.0} RPM."));
                return;
            }
        }
        if self.cruise_mph.is_none() && self.keeper_mph.is_none() {
            self.say_plain(ctx, "Adaptive cruise is off. Press K to set it first.");
            return;
        }
        let base = match self.speed_control_target_mph {
            Some(base) => base,
            None => {
                let position = self.trip.position_mi;
                let (limit, _) = self.trip.speed_limit_at(position);
                CRUISE_MIN_MPH.max(limit)
            }
        };
        let target = cruise_step_target(base, direction, fine);
        self.speed_control_target_mph = Some(target);
        if self.cruise_mph.is_some() {
            self.cruise_mph = Some(target);
            if let Some(exit) = self.cruise_exit_mph {
                let ramp_target = target.min(exit);
                let message = SpokenMessage::with_terse(
                    format!(
                        "Open-road cruise target {}. Ramp approach target {}.",
                        ctx.settings.speed_text(target),
                        ctx.settings.speed_text(ramp_target)
                    ),
                    format!(
                        "{}, ramp {}.",
                        self.speed_number(ctx, target),
                        self.speed_number(ctx, ramp_target)
                    ),
                );
                ctx.say_with(message, Say::new().category(SpeechCategory::Confirmation));
            } else {
                // Terse is the number alone. Walking the dial is a rapid
                // sequence of presses and the player already knows which
                // control they are holding, so a sentence per press is the
                // unit repeated, not information (owner, 2026-08-17).
                let message = SpokenMessage::with_terse(
                    format!("Adaptive cruise {}.", ctx.settings.speed_text(target)),
                    format!("{}.", self.speed_number(ctx, target)),
                );
                ctx.say_with(message, Say::new().category(SpeechCategory::Confirmation));
            }
        } else {
            let message = SpokenMessage::with_terse(
                format!(
                    "Open-road cruise target {}.",
                    ctx.settings.speed_text(target)
                ),
                format!("{}.", self.speed_number(ctx, target)),
            );
            ctx.say_with(message, Say::new().category(SpeechCategory::Confirmation));
        }
    }

    /// Just the figure, in the player's units -- no unit word.
    ///
    /// What the dial answers with at quiet. The unit never changes between
    /// presses, so repeating it on every tap of the Accel/Coast buttons is
    /// the one part of the line carrying no information.
    pub fn speed_number(&self, ctx: &GameContext, mph: f64) -> String {
        ctx.settings
            .speed_text(mph)
            .split_whitespace()
            .next()
            .unwrap_or("")
            .to_string()
    }

    /// Hold the current speed through a low-speed zone (K in a zone).
    ///
    /// An input-accessibility aid: facility access roads, gate queues, work
    /// zones, and congestion otherwise demand a continuously held accelerator,
    /// which some players cannot sustain. The keeper caps at the zone's limit,
    /// follows queued traffic, and hands back on any brake input.
    pub fn engage_keeper(
        &mut self,
        ctx: &mut GameContext,
        limit_mph: f64,
        zone_reason: &str,
        target_mph: Option<f64>,
        announce: bool,
    ) {
        if !ctx.settings.speed_keeper {
            // Naming the way out matters more than the refusal: the keeper is
            // exactly the thing that holds speed here, and a driver who has
            // never turned it on hears only that cruise "is not available"
            // and concludes the ramp kills speed control (Shane, 2026-08-15).
            self.say_plain(
                ctx,
                format!(
                    "Adaptive cruise is not available in a {zone_reason} zone. The speed keeper \
                     holds your speed here instead; turn it on in Settings, Controls."
                ),
            );
            return;
        }
        let speed = self.trip.truck.speed_mph();
        if !self.trip.truck.engine_on || (target_mph.is_none() && speed < KEEPER_MIN_MPH) {
            self.say_plain(
                ctx,
                "The speed keeper needs the engine running and the truck rolling.",
            );
            return;
        }
        self.speed_control_armed = true;
        self.speed_control_paused_at_stop = false;
        // Same rounding as _engage_cruise: a plain K-set captures the truck's
        // exact float speed, which the player never hears -- only its rounded
        // form does.
        let captured_mph = target_mph.unwrap_or_else(|| round_py(speed));
        self.keeper_mph = Some(captured_mph.min(limit_mph));
        self.keeper_zone = zone_reason.to_string();
        self.keeper_zone_limit = Some(limit_mph);
        self.keeper_throttle = self.trip.truck.throttle;
        if announce {
            ctx.audio.play_with("ui/notify", 0.5, 0.0);
            let held = ctx.settings.speed_text(self.keeper_mph.unwrap_or(0.0));
            self.say_plain(
                ctx,
                format!(
                    "Automatic speed control on. Speed keeper holding {held} through the \
                     {zone_reason} zone. K or braking cancels."
                ),
            );
        }
    }

    /// Hold a low-speed zone, or build speed through an acceleration lane.
    pub fn update_keeper(
        &mut self,
        ctx: &mut GameContext,
        dt: f64,
        braking: bool,
        accelerating: bool,
        clutch_disengaged: bool,
    ) {
        if self.keeper_mph.is_none() {
            return;
        }
        let t = &self.trip.truck;
        if braking || t.emergency_brake || t.air_brakes_holding() || !t.engine_on || t.stalled {
            self.cancel_keeper(ctx, false);
            // ROUTE, not the ambient default: the automation just released the
            // throttle, and a driver who assumed it still held speed needs to
            // hear that (automation-handoff sweep, 2026-08-20, the deferred
            // 2026-08-15 audit).
            self.say_route_confirmation(ctx, "Speed keeper canceled; automatic speed control off.");
            return;
        }
        if accelerating {
            return; // manual override; the keeper resumes when the key lifts
        }
        if clutch_disengaged {
            self.trip.truck.throttle = 0.0;
            return;
        }
        let position = self.trip.position_mi;
        let (limit, mut zone_reason) = self.trip.speed_limit_at(position);
        if zone_reason.is_none() && self.departure_ramp_mi.is_some() {
            // The acceleration lane is a low-speed regime like a zone, and the
            // keeper is the tool for those -- it exists because holding an
            // accelerator down is exactly what some players cannot do. Handing
            // to cruise here handed to nothing: cruise refuses below its own
            // minimum holding speed, so a driver coming off yard streets at
            // twenty had no automation at all until they had got themselves
            // back up to road speed by hand (Brandon, 2026-08-21). The keeper
            // builds toward the road's own limit, then hands to cruise once
            // this truck reaches its capability-aware merge threshold.
            zone_reason = Some("acceleration lane".to_string());
        }
        let Some(zone_reason) = zone_reason else {
            let target_mph = self.speed_control_target_mph.unwrap_or(limit);
            self.cancel_keeper(ctx, true);
            self.engage_cruise(ctx, target_mph, true);
            return;
        };
        self.keeper_zone = zone_reason.clone();
        self.take_new_posted_limit(ctx, limit, &zone_reason);
        let mut target_mph = self.keeper_mph.unwrap_or(limit).min(limit);
        // The road ahead, not just the road under the wheels: a corner or a
        // lower posted limit close enough that the shedding has to start now.
        // A posted drop gets the same one-shot cue adaptive cruise gives it;
        // a corner does not, because its own approach call already names the
        // number and says the keeper is taking it.
        let ahead = self.keeper_speed_ahead(ctx);
        match ahead.as_ref() {
            Some((ahead_mph, ahead_reason)) if *ahead_mph < target_mph => {
                target_mph = KEEPER_MIN_MPH.max(*ahead_mph - KEEPER_EASE_UNDERSHOOT_MPH);
                let fresh = self
                    .keeper_ease_said
                    .is_none_or(|said| *ahead_mph < said - 0.5);
                if ahead_reason != "turn" && fresh {
                    self.keeper_ease_said = Some(*ahead_mph);
                    let reason = match ahead_reason.as_str() {
                        "construction" => "Construction zone ahead",
                        "heavy traffic" => "Heavy traffic ahead",
                        _ => "Posted limit lower",
                    };
                    // ROUTE, not the ambient default: same family as the adaptive
                    // cruise easing line below -- an assist saying it is about to
                    // change how fast the truck is going is a consequence, not
                    // colour, and this one governs the same class of
                    // dropped-stale incident (automation-handoff sweep,
                    // 2026-08-20, the deferred 2026-08-15 audit).
                    let eased = ctx.settings.speed_text(*ahead_mph);
                    self.say_route_confirmation(
                        ctx,
                        &format!("{reason}; speed keeper easing to {eased}."),
                    );
                    // This line already named the number for a plain posted-limit
                    // drop; the arrival "Speed limit reduced to X" would otherwise
                    // repeat it a moment later.
                    if !matches!(ahead_reason.as_str(), "construction" | "heavy traffic") {
                        self.trip.note_limit_preannounced(*ahead_mph);
                    }
                }
            }
            None => self.keeper_ease_said = None,
            _ => {}
        }
        let context = self.trip.traffic_context();
        if let Some(context) = context.as_ref() {
            let scale = self.trip.effective_time_scale();
            let ease_mi = self.keeper_ease_mi(context.lead.speed_mph, scale);
            if context.gap_seconds() <= KEEPER_GAP_SECONDS
                || (context.lead.speed_mph < target_mph
                    // Once there is a reason to shed for it, on the keeper's own
                    // ease law. Matching a slower vehicle the moment it is visible
                    // meant matching one two and a half miles off (the traffic
                    // bubble's whole reach), so a car doing 35 in a 45 work zone
                    // put the truck at 35 from the far end of the zone with
                    // nothing said. The stopped-queue case still lands here: a
                    // standstill lead prices out at zero, and the gap to it is
                    // inside anybody's window.
                    && context.gap_mi <= ease_mi)
            {
                // Creep along with the queue, all the way down to a stop, and roll
                // again when it moves -- gates and work zones are queue country.
                target_mph = target_mph.min(context.lead.speed_mph);
            }
        }
        let acceleration_lane = zone_reason == "acceleration lane";
        if acceleration_lane
            && self.departure_cruise_handoff_mph.is_some_and(|handoff| {
                target_mph + 0.5 >= handoff
                    && self.trip.truck.speed_mph() + 0.5 >= handoff
                    && self.trip.truck.speed_mph() >= CRUISE_MIN_MPH
            })
        {
            let target_mph = self.speed_control_target_mph.unwrap_or(limit);
            self.cancel_keeper(ctx, true);
            self.engage_departure_cruise(ctx, target_mph);
            return;
        }
        let error = target_mph - self.trip.truck.speed_mph();
        // Feed-forward first, exactly as adaptive cruise does: the truck's own
        // physics already knows which pedal balances the road under the
        // wheels, so the keeper answers a hill as the hill arrives. The trim
        // below only ever corrects from there.
        //
        // Without it the keeper was a bare integrator against a HALF-THROTTLE
        // ceiling, and the ceiling's premise -- "zone speeds never need more
        // than half throttle" -- is a claim about FLAT road. On a hill the
        // truck simply settled wherever half throttle happened to balance
        // gravity and stayed there, silently: a 55 zone held 49 on a one
        // percent pull and 34 on a two percent one, a 45 zone held 37 on two
        // percent, and a merge asked to build to 65 asymptoted at 58 and never
        // arrived (bench, 2026-08-24, the owner's "sometimes it doesn't hold
        // the posted speeds"). The trim keeps its own half-throttle limit --
        // that is the assist's gentleness and it is unchanged -- but it is now
        // a limit on what the keeper adds OVER the road's own demand rather
        // than on the whole pedal.
        let mut hold = self.trip.truck.hold_throttle();
        if error < 0.0 {
            // Over the number: come off the fuel across the same band the snub
            // starts at, so the feed-forward cannot hold the truck parked just
            // above its own target waiting for the drums.
            hold *= 0.0f64.max(1.0 + error / KEEPER_SNUB_OVER_MPH);
        }
        let trim = (self.keeper_throttle + error * 0.1 * dt).clamp(0.0, KEEPER_MAX_THROTTLE);
        // A restricted zone is a steady-speed job and keeps the keeper's
        // gentle trim. An acceleration lane is time-limited pavement: while
        // materially below its target, use the whole real drivetrain so the
        // truck does not throw away the lane at half demand.
        let demand = if acceleration_lane && error > KEEPER_SNUB_UNDER_MPH {
            1.0
        } else {
            hold + trim
        };
        // Anti-windup, the cruise loop's own rule: a grade the engine cannot
        // pull pins the pedal at the roof for as long as it lasts, and
        // integrating through that buries the trim at its limit and leaves the
        // truck overshooting for seconds after the road levels out.
        let saturated = (demand >= 1.0 && error > 0.0) || (trim <= 0.0 && error < 0.0);
        if !saturated {
            self.keeper_throttle = trim;
        }
        let mut applied = demand.clamp(0.0, 1.0);
        if let Some((ahead_mph, _)) = ahead.as_ref() {
            if self.trip.truck.speed_mph() >= *ahead_mph {
                // Easing toward a lower number: rebuild throttle under it freely,
                // never through it. The snub cycle deliberately rides a band
                // around the eased target (one application, held, released -- the
                // air model's price list), and on a compressed clock the
                // release-and-rebuild peak poked half a mile per hour over the
                // sign's own number right at the sign -- the keeper burning fuel
                // to defeat its own easing, and the 15.47-against-15 flake
                // (ROADMAP 2026-08-19). Coasting at the boundary caps the peak at
                // the number; the snub thresholds below it are untouched.
                self.keeper_throttle = 0.0;
                applied = 0.0;
            }
        }
        self.trip.truck.throttle = applied;
        self.say_keeper_out_of_truck(ctx, dt, error, applied, target_mph);
        self.keeper_snub_brakes(ctx, dt, -error, target_mph);
    }

    /// Say plainly when the hill has beaten the speed keeper.
    ///
    /// The keeper has warned about running OVER its number since the snub
    /// landed (`keeper_snub_brakes` below) and said nothing at all about
    /// running under it. A sighted driver reads a sagging speedo in a second;
    /// a blind driver has the engine note and the downshifts, which say the
    /// truck is working, not that it is losing -- and losing is the part that
    /// decides whether to take it over by hand. Adaptive cruise has said this
    /// for a while ("Cruise is flat out and still losing the grade"); this is
    /// the same sentence for the other controller.
    ///
    /// Only once the pedal is genuinely on the floor and the truck is still
    /// falling past the droop band, so an ordinary pull the keeper recovers
    /// from on its own stays quiet.
    pub fn say_keeper_out_of_truck(
        &mut self,
        ctx: &mut GameContext,
        dt: f64,
        error: f64,
        applied: f64,
        target_mph: f64,
    ) {
        self.keeper_droop_cue_s = 0.0f64.max(self.keeper_droop_cue_s - dt);
        let beaten = applied >= CRUISE_FLOORED_THROTTLE
            && self.trip.truck.grade * 100.0 >= CRUISE_GRADE_BEATEN_PCT
            && error > KEEPER_DROOP_MPH;
        if !beaten {
            self.keeper_droop_s = 0.0;
            if error < KEEPER_DROOP_MPH * 0.5 {
                self.keeper_droop_said = false; // back on its number: arm again
            }
            return;
        }
        if self.trip.truck.transmission.shifting() {
            return; // an open driveline is no evidence either way; hold the count
        }
        self.keeper_droop_s += dt;
        if self.keeper_droop_s < CRUISE_GRADE_BEATEN_S {
            return;
        }
        if self.keeper_droop_said || self.keeper_droop_cue_s > 0.0 || self.terse_speech(ctx) {
            return;
        }
        self.keeper_droop_said = true;
        self.keeper_droop_cue_s = CLIMB_CUE_COOLDOWN_S;
        let wanted = ctx.settings.speed_text(target_mph);
        let held = ctx.settings.speed_text(self.trip.truck.speed_mph());
        let mut opts = SayEvent::queued();
        opts.category = Some(SpeechCategory::Status);
        ctx.say_event_with(
            format!(
                "Speed keeper is flat out and cannot make {wanted} on this grade. Holding {held}."
            ),
            opts,
        );
    }

    /// Hand the keeper back up to street speed when the street changes.
    ///
    /// The keeper's number is the one it was given when it engaged, capped by
    /// the limit under the wheels -- so it comes DOWN with the road on its
    /// own, and used to have no way back UP. A facility approach is a chain of
    /// streets zoned one per leg (25 named, 15 unnamed service ways), so a
    /// session started on a service way held that crawl over every named
    /// street after it, for the whole chain, while the zone entry announced
    /// the higher number (tester report, access roads, 2026-08). The spoken
    /// promise is "holding X through the <reason> zone"; a new posted number
    /// is a new zone, and it takes it.
    ///
    /// Only ever upward, and only on a real change to the posted number: a
    /// driver who set a lower speed by hand keeps it as long as the street
    /// does, and coming down is already the cap's job.
    pub fn take_new_posted_limit(&mut self, ctx: &mut GameContext, limit: f64, zone_reason: &str) {
        let Some(keeper_mph) = self.keeper_mph else {
            return;
        };
        if self.keeper_zone_limit == Some(limit) {
            return;
        }
        self.keeper_zone_limit = Some(limit);
        if limit <= keeper_mph {
            return;
        }
        self.keeper_mph = Some(limit);
        if let Some(easing) = self.keeper_ease_target.as_ref() {
            if easing.1 < limit {
                // Already shedding for something lower up the road, on a street
                // short enough that both land together. The ease line names the
                // number the truck will actually be doing; "holding 25" on top of
                // it is a promise contradicted in the same breath.
                return;
            }
        }
        // An assist that speeds the truck up on its own has to say so: the
        // zone entry announced the law, not what the truck is about to do.
        // ROUTE, not the ambient default, for the same reason (automation-
        // handoff sweep, 2026-08-20, the deferred 2026-08-15 audit).
        let held = ctx.settings.speed_text(limit);
        let spoken = if zone_reason == "acceleration lane" {
            format!("Speed keeper building to {held} for the merge.")
        } else {
            format!("Speed keeper holding {held} through the {zone_reason} zone.")
        };
        self.say_route_confirmation(ctx, &spoken);
    }

    /// Work the drums in snubs to hold the keeper's target.
    ///
    /// One application, held until the truck is back under the number, then
    /// released -- never a trim that tracks the error up and down. The air
    /// model charges a whole application every time the pedal rises, so a
    /// hunting command is charged for hundreds of them; and a proportional
    /// term fades exactly as it approaches the target, so on a downgrade it
    /// settles wherever the fading command happens to balance gravity rather
    /// than ever arriving. Sizing the snub against the grade is what makes it
    /// arrive; holding it is what makes it affordable.
    pub fn keeper_snub_brakes(
        &mut self,
        ctx: &mut GameContext,
        dt: f64,
        over: f64,
        target_mph: f64,
    ) {
        // Net of the grade: on the level this is a light application, and on a
        // downgrade it is however much more it takes to still take
        // KEEPER_SNUB_DECEL_MPS2 off the truck. Read every frame and allowed to
        // firm up mid-snub -- a snub sized once, on the grade under the wheels
        // when it started, holds that pedal onto a steepening hill and simply
        // accelerates against it.
        let gravity_mps2 = 0.0f64.max(-self.trip.truck.grade) * G;
        let wanted = KEEPER_SNUB_MAX_BRAKE.min(KEEPER_SNUB_MIN_BRAKE.max(
            (KEEPER_SNUB_DECEL_MPS2 + gravity_mps2) / assist_full_decel_mps2(&self.trip.truck),
        ));
        if self.keeper_snub > 0.0 {
            if over <= -KEEPER_SNUB_UNDER_MPH {
                self.keeper_snub = 0.0; // under the number: let it go
            } else {
                // Only ever firmer while the snub lasts. Easing and re-pressing
                // is what the air system charges for.
                self.keeper_snub = self.keeper_snub.max(wanted);
            }
        } else if over > KEEPER_SNUB_OVER_MPH {
            self.keeper_snub = wanted;
        }
        if self.keeper_snub > 0.0 {
            self.trip.truck.throttle = 0.0; // never brake against our own throttle
            self.trip.truck.brake = self.trip.truck.brake.max(self.keeper_snub);
        }
        // Pressing everything it has and still riding well over the number:
        // say so. An assist that quietly holds the wrong speed is the one
        // thing a driver who cannot see the speedometer cannot catch.
        let maxed = self.keeper_snub >= KEEPER_SNUB_MAX_BRAKE - 1e-6;
        if maxed && over > KEEPER_OVERRUN_MPH {
            self.keeper_overrun_s += dt;
        } else {
            self.keeper_overrun_s = 0.0;
            if over <= 0.0 {
                self.keeper_overrun_said = false;
            }
        }
        if self.keeper_overrun_s >= KEEPER_OVERRUN_S && !self.keeper_overrun_said {
            self.keeper_overrun_said = true;
            // Name the grade only where there is one: hot drums or ice take the
            // same authority away on level road, and blaming a hill the driver
            // is not on would send them looking for the wrong thing.
            let because = if self.trip.truck.grade <= -0.01 {
                " on this grade"
            } else {
                ""
            };
            let held = ctx.settings.speed_text(target_mph);
            self.say_safety_interrupt(
                ctx,
                &format!("Speed keeper cannot hold {held}{because}. Apply service brakes."),
            );
        }
    }
}
