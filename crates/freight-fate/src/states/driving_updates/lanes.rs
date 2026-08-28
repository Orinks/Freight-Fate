//! Discrete lanes on top of the drift model: the per-frame lane pass, tap
//! changes, crossings, a road that narrows under the truck, coned-off lanes,
//! and keep-right pressure.

use ff_core::pyfmt::fmt_grouped;
use ff_core::sim::trip_models::Zone;
use ff_core::speech_pacing::{EventPriority, SpeechCategory};
use ff_core::speech_text::SpokenMessage;

use crate::app::{GameContext, SayEvent};
use crate::states::base::Key;
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;
use crate::states::driving_events::ambient::Ambient;
use crate::states::driving_updates::{
    lane_count_words, CURVE_ASSIST_JAKE_FULL_MPH, JAKE_MIN_RPM, LANE_CROSS_REPEAT_S,
    SIDESWIPE_REPEAT_S,
};

impl DrivingState {
    pub fn update_lane(&mut self, ctx: &mut GameContext, dt: f64) {
        let mode = ctx.settings.lane_keeping.clone();
        let mut steer = 0.0;
        if ctx.input.is_pressed(Key::Left) {
            steer -= 1.0;
        }
        if ctx.input.is_pressed(Key::Right) {
            steer += 1.0;
        }
        // The left stick provides analog steering when the keys are idle.
        if steer == 0.0 && ctx.controller.active() && ctx.controller.steering() != 0.0 {
            steer = ctx.controller.steering();
        }
        self.lane.steering = steer;
        // The exit ramp is a single lane; the mainline keeps its leg count.
        self.lane_before_narrow = Some(self.lane.lane);
        let count = if self.ramp_mi.is_some() {
            1
        } else {
            self.lane_count_here()
        };
        self.lane.set_lane_count(count);
        // A narrowing road renumbers the lanes under the truck, so this has to
        // run the moment the count changes and before anything polices where
        // the truck is.
        self.leave_a_lane_the_road_closed(ctx);
        // Use the real baked curve data when the truck is inside a curve.
        // The curve force pushes the lane offset outward proportionally to
        // how much the truck's speed exceeds the advisory speed, scaled by
        // load, grip, and the curve's tightness.
        let active = self.trip.curve_at(self.trip.position_mi);
        let route_transition_owns_ramp =
            ctx.settings.route_transition_assist && self.ramp_mi.is_some();
        let mut curve;
        match active.as_ref().filter(|c| !c.connector) {
            Some(bend) => {
                let excess = 0.0f64.max(self.trip.truck.speed_mph() - bend.advisory_mph as f64);
                let tightness = 0.2f64.max(1.0 - bend.min_radius_ft as f64 / 5000.0);
                // Curve push severity: around 1.0 at advisory in a tight bend,
                // ramping with excess speed. A heavier load pushes harder (more
                // inertia to pull wide); worn or icy grip means less resistance.
                let load =
                    1.5f64.min(self.trip.truck.gross_mass_kg() / self.trip.truck.specs.mass_kg);
                let grip_factor = 1.0f64.min(self.trip.truck.effective_grip());
                // Raw severity only: the lane model applies CURVE_RATE itself.
                // Scaling here too made every bend ~8x weaker than designed --
                // a 30-advisory curve at 45 could be no-hands (owner-caught on
                // Camp Verde-Payson: "didn't hear or have to turn").
                let curve_push = tightness * (1.0 + excess * 0.05) * load / 0.2f64.max(grip_factor);
                // Centrifugal force pushes the truck OUTSIDE the curve: a left
                // curve pushes right (positive offset), a right curve pushes left
                // (negative offset). The lane model's positive offset = rightward.
                let direction = if bend.direction == 'L' { 1.0 } else { -1.0 };
                curve = curve_push * direction;
                // Spoken slip warning: entering a curve well above advisory
                // pushes the truck toward the shoulder and the driver should
                // know why.
                if excess > 15.0 && !self.curve_slip_active {
                    self.curve_slip_active = true;
                    let phrase = self.pacenote_phrase(bend);
                    ctx.say_event_with(
                        format!("{phrase}: too fast, drifting to the outside."),
                        SayEvent::new().category(SpeechCategory::Safety),
                    );
                }
            }
            None => curve = 0.0,
        }
        if self.ramp_mi.is_some() {
            curve += 0.35;
        }
        if active.is_none() && self.curve_slip_active {
            self.curve_slip_active = false;
        }
        self.update_curve_run(ctx, active.as_ref());
        // Curve speed assist: use the real advisory speed when one is active
        // instead of the old terrain heuristic. Hysteresis both places:
        // engage above advisory + 5, but once slowing, hold until the truck
        // is within 2 of advisory. Deciding both ways at one threshold
        // flip-flopped against cruise seven times a second (playtest
        // 2026-07-22).
        let mut curve_assisting = false;
        let mut excess_now: Option<f64> = None;
        if ctx.settings.curve_speed_assist {
            match active.as_ref().filter(|c| !c.connector) {
                Some(bend) => {
                    let margin = if self.curve_assist_active { 2.0 } else { 5.0 };
                    curve_assisting =
                        self.trip.truck.speed_mph() > bend.advisory_mph as f64 + margin;
                    excess_now =
                        Some(0.0f64.max(self.trip.truck.speed_mph() - bend.advisory_mph as f64));
                }
                None => {
                    if curve != 0.0 && !route_transition_owns_ramp {
                        // Fallback: old terrain- or ramp-based heuristic
                        let mut heuristic = 50.0 - curve.abs() * 20.0;
                        if self.curve_assist_active {
                            heuristic -= 3.0;
                        }
                        curve_assisting = self.trip.truck.speed_mph() > heuristic;
                    }
                }
            }
        }
        // The corner is the DRUMS' work, always. The retarder appears here
        // only when the road is going downhill, and then it is the grade it is
        // answering, not the bend. See the block below for the reasoning and
        // the sources; the short version is that a corner needs a precise
        // target speed, which is what service brakes are for, and a retarder
        // drives only the tractor's rear wheels, which is the last axle you
        // want retarding mid-bend.
        let jake_capable = {
            let t = &self.trip.truck;
            t.engine_on
                && t.throttle < 0.05
                && !t.transmission.in_neutral()
                && !t.transmission.shifting()
                && t.transmission.clutch <= 0.5
                && t.grip >= 0.55
                && t.rpm >= JAKE_MIN_RPM
        };
        // A real downgrade is the retarder's own job -- holding a loaded
        // truck back on a grade is the one use every noise ordinance
        // leaves legal -- so the overspeed line does not apply there.
        // on_downgrade draws the same line the G readout and the
        // ordinance exemption already draw between level road and a
        // grade, and adaptive cruise now asks it too. Without this
        // carve-out the assist held a six percent descent on the drums
        // alone: past fade in four and a half minutes, 585 degrees at ten
        // (bench trace, 2026-08-11).
        //
        // Asked EVERY frame, not once when the assist engages. A bend is a
        // stretch of road, not a moment, and the grade under it changes
        // while the truck is in it: a corner that starts on a pitch and
        // finishes on the flat or on the way up used to keep whatever the
        // pitch bought for the whole corner, because the release below only
        // ever ran when the CORNER ended. Measured on the jake sweep,
        // 2026-08-24: 6.9 seconds barking on level road and 4.6 seconds
        // barking at a climb, per bend, which is the owner's "on uphill
        // ascents the truck should gain speed instead of using the engine
        // brakes". Asking per frame also subsumes the old latch-yield retry:
        // a yielded latch is still draining on the engage frame, so the
        // throttle test above fails once and passes as soon as it drains.
        let downhill = self.on_downgrade();
        // A GRADE is the only thing that raises the retarder here. Slowing
        // FOR a corner is the service brakes' job, however much speed the
        // corner wants off -- owner ruling 2026-08-11, narrowing the
        // jake-first ruling of 2026-07-22 to grades only.
        //
        // The training material is unambiguous and it is not about noise.
        // The CDL manual's rule for a curve is to reach a safe speed
        // BEFORE entering it and then pull through on gentle throttle,
        // because braking mid-corner is what locks a wheel and jackknifes
        // a trailer -- and a retarder drives only the tractor's rear
        // wheels, which is precisely the axle you do not want retarding
        // through a bend. Jacobs, who build the thing, draw the same line:
        // the engine brake is for SUSTAINED speed control and is "not a
        // substitute for a service braking system", because it cannot give
        // the precise control the drums give. A corner is a precise target
        // speed. A descent is sustained control. Only the descent qualifies.
        //
        // A bend ON a grade still retards, because that is the grade's
        // doing, not the corner's -- and it has to: without this the assist
        // held a six percent descent on the drums alone and went past fade
        // in four and a half minutes, 585 degrees at ten (bench trace,
        // 2026-08-11).
        //
        // Which grade, though. `on_downgrade` is geometry at two percent --
        // the spoken advisory's release edge, never a braking number -- so the
        // assist barked its way through every shallow dip that happened to
        // carry a bend ("the jake activates on every single descent it seems,
        // even shallow descent like 1-3 percent", owner, 2026-08-24). It comes
        // UP now only where `retarder_warranted` says the drums cannot hold
        // the hill on their own, which is grade against weight against speed
        // on the truck's own brake heat model. It stays up while the road is
        // still going down at all, so the pair is hysteresis rather than one
        // line decided twice -- the same shape the ramp cap below has, for the
        // same reason.
        let worth_the_bark = curve_assisting && excess_now.is_some() && downhill;
        let worth_raising = curve_assisting && excess_now.is_some() && self.retarder_warranted();
        // Town no-engine-brake zones close the jake to the assist as well
        // (real downgrades stay exempt); the service trim below answers.
        if worth_raising
            && !self.curve_assist_jake
            && jake_capable
            && !self.trip.truck.engine_brake()
            && self.assist_jake_allowed(ctx)
        {
            // Stage one is a token two cylinders: past this line it would
            // bark without taking off the speed that called for it.
            self.trip.truck.engine_brake_stage =
                if excess_now.unwrap_or(0.0) > CURVE_ASSIST_JAKE_FULL_MPH {
                    3
                } else {
                    2
                };
            self.curve_assist_jake = true;
        } else if self.curve_assist_jake && !worth_the_bark {
            // The corner ended, or the grade under it did. Either way the
            // reason is gone, so the retarder goes back at once. Release
            // only the jake WE engaged; the player's own selection (or
            // their mid-curve override) is never touched.
            if self.trip.truck.engine_brake() {
                self.trip.truck.engine_brake_stage = 0;
            }
            self.curve_assist_jake = false;
        }
        let jake_slowing = self.trip.truck.engine_brake()
            && self.trip.truck.throttle < 0.05
            && self.trip.truck.grip >= 0.55;
        let needs_service = !jake_slowing || excess_now.is_some_and(|excess| excess > 10.0);
        // The spoken cues get a cooldown on top: even a legitimate slow
        // cycle (cruise pulling back up to the engage line) must not chant.
        self.curve_assist_cue_s = (self.curve_assist_cue_s - dt).max(0.0);
        if curve_assisting && needs_service {
            self.trip.truck.brake = self.trip.truck.brake.max(0.35f64.min(curve.abs()));
        }
        // ON A RAMP, THE RAMP OWNS THE SPEECH. A ramp adds 0.35 of curve
        // weight above, so any exit taken over about 43 mph engages this
        // assist -- and route-transition assistance is already braking for
        // the sign or the light at the end of it and already says so. With
        // the realistic preset both are on by default, so every hot ramp
        // spoke twice, back to back (logged playtest of the four 1.9 assists,
        // 2026-07-15). The extra announcement goes, and the surviving line is
        // the more useful one because it names WHAT is slowing the truck. The
        // synthetic ramp weight remains for the lane model, but it is not a
        // corner. Asking the curve assist to brake for it made two held
        // service applications fight over the same descent (Joshua's ramp
        // drive, 2026-08-28).
        let on_ramp = self.ramp_mi.is_some();
        if curve_assisting {
            if !self.curve_assist_active && self.curve_assist_cue_s <= 0.0 && !on_ramp {
                self.curve_assist_cue_s = CURVE_ASSIST_CUE_COOLDOWN_S;
                self.curve_assist_spoke = true;
                // ROUTE, not the ambient default: names an automation taking
                // the pedals (automation-handoff sweep, 2026-08-20, the
                // deferred 2026-08-15 audit).
                ctx.say_event_with(
                    "Curve speed assistance slowing.",
                    SayEvent::queued()
                        .priority(EventPriority::Route)
                        .category(SpeechCategory::Confirmation),
                );
            }
        } else if self.curve_assist_active
            && self.curve_assist_cue_s <= 0.0
            && self.curve_assist_spoke
        {
            self.curve_assist_cue_s = CURVE_ASSIST_CUE_COOLDOWN_S;
            self.curve_assist_spoke = false;
            // ROUTE, not the ambient default: names the automation handing the
            // pedals back (automation-handoff sweep, 2026-08-20, the deferred
            // 2026-08-15 audit).
            ctx.say_event_with(
                "Curve speed assistance released.",
                SayEvent::queued()
                    .priority(EventPriority::Route)
                    .category(SpeechCategory::Confirmation),
            );
        } else if !curve_assisting {
            // Engagement that never spoke (the ramp case) simply ends.
            self.curve_assist_spoke = false;
        }
        self.curve_assist_active = curve_assisting;
        // Hysteresis on the ramp cap, for the same reason the curve assist has
        // it: decided both ways on the one threshold, a truck riding the ramp
        // limit announced itself slowing and released over and over down a
        // single ramp -- and re-made the brake application, and paid the air
        // for it, every time round (bench, 2026-08-11).
        let ramp_hold_mph = if self.transition_assist_active {
            self.armed_ramp_cruise_mph(None)
        } else {
            self.armed_ramp_mph(None)
        };
        let transition_assisting = ctx.settings.route_transition_assist
            && self.ramp_mi.is_some()
            && self.trip.truck.speed_mph() > ramp_hold_mph;
        if transition_assisting {
            // A ramp cap is sustained speed control, not the bar's stop.
            // Lift first and let drag shed the excess; holding a service
            // floor here spent air all the way down the ramp. The terminal
            // servo below still owns the real stop and its full hold.
            self.trip.truck.throttle = 0.0;
            if !self.transition_assist_active {
                // Cruise would otherwise put power straight back on after
                // this lane pass. Pausing it also keeps the lift from
                // chattering against its own target until the bar is honored.
                self.pause_speed_control(ctx, true);
                // ROUTE, not the ambient default: names an automation taking
                // the pedals (automation-handoff sweep, 2026-08-20, the
                // deferred 2026-08-15 audit).
                ctx.say_event_with(
                    "Route-transition assistance slowing.",
                    SayEvent::queued()
                        .priority(EventPriority::Route)
                        .category(SpeechCategory::Confirmation),
                );
            }
        } else if self.transition_assist_active {
            // ROUTE, not the ambient default: names the automation handing the
            // pedals back (automation-handoff sweep, 2026-08-20, the deferred
            // 2026-08-15 audit).
            ctx.say_event_with(
                "Route-transition assistance released.",
                SayEvent::queued()
                    .priority(EventPriority::Route)
                    .category(SpeechCategory::Confirmation),
            );
        }
        self.transition_assist_active = transition_assisting;
        let wind = self.trip.weather.effects().wind;
        let speed_mps = self.trip.truck.velocity_mps;
        let off_road_event = self.lane.update(dt, speed_mps, curve, wind, &mode);
        if off_road_event {
            if !ctx.settings.lane_departure_warning {
                return;
            }
            let pan = self.lane_pan();
            ctx.audio.play_with("vehicle/rumble_strip", 1.0, pan);
            self.trip.truck.add_damage(1.0, true);
            self.announce_off_pavement(ctx);
        } else if self.road_position_band.is_some() && !self.off_pavement() {
            // Back on the pavement: the standing condition ended, so its one
            // transition line speaks and the band resets (research doc R12).
            self.road_position_band = None;
            // review=True: STATUS goes SILENT at urgent_only, so this line
            // would otherwise reach no voice, no earcon, and (with the old
            // review=False here) no log either -- genuinely unreachable,
            // which breaks the ladder's own invariant that nothing it cuts
            // becomes invisible to the review keys.
            ctx.say_event_with(
                "Back on the pavement.",
                SayEvent::queued()
                    .review(true)
                    .category(SpeechCategory::Status),
            );
        }
        self.cross_repeat_s = (self.cross_repeat_s - dt).max(0.0);
        self.sideswipe_cooldown_s = (self.sideswipe_cooldown_s - dt).max(0.0);
        if self.lane.crossed != 0 {
            self.on_lane_crossed(ctx);
        }
        self.update_tap_lane_change(ctx, dt);
        self.update_merge(ctx, dt);
        self.update_keep_right(ctx, dt);
    }

    /// Advance an assist-off tap change: signal clicks, then the flip.
    pub fn update_tap_lane_change(&mut self, ctx: &mut GameContext, dt: f64) {
        let Some(mut target) = self.lane_change_target else {
            return;
        };
        let pan = if target > self.lane.lane { -0.6 } else { 0.6 };
        self.lane_signal_timer += dt;
        if self.lane_signal_timer >= LANE_SIGNAL_CLICK_S {
            self.lane_signal_timer = 0.0;
            ctx.audio.play_with("vehicle/signal_tone", 0.8, pan);
        }
        self.lane_change_timer -= dt;
        if self.lane_change_timer <= 0.0 {
            self.lane_change_target = None;
            target = target.min(self.lane.lane_count - 1);
            // Check the closure again on arrival, not just when the key was
            // pressed. A change takes seconds, and in those seconds the truck
            // can reach the cones or the road can narrow and renumber the
            // lanes -- either way the clamp above would otherwise land the
            // truck in the closed lane it was moving to avoid.
            if Some(target) == self.closed_lane_here() {
                ctx.audio.play("ui/error");
                let text = format!(
                    "The {} lane is closed. Staying in the {} lane.",
                    lane_label(target, self.lane.lane_count),
                    self.lane.lane_name()
                );
                ctx.say_event_with(text, SayEvent::new().category(SpeechCategory::Safety));
                return;
            }
            self.lane.lane = target;
            // The tap change crosses the same painted line: same marker roll.
            let volume = 1.0f64.min(0.7 * self.cue_loudness(ctx));
            ctx.audio.play_with("vehicle/lane_line_cross", volume, pan);
            self.finish_lane_change(ctx, false);
        }
    }

    /// A held drift carried the truck across a line: the wheel was the
    /// lane change. The tires roll the line's raised markers every time --
    /// physics does not rate-limit -- but the signal tone and the spoken
    /// lane name mark a DELIBERATE change only. Pinballing back and forth
    /// across the same line mid-bend repeats just the quieter thump
    /// (owner: "the thing dings at you as you're going").
    pub fn on_lane_crossed(&mut self, ctx: &mut GameContext) {
        let repeat = self.cross_repeat_s > 0.0;
        self.cross_repeat_s = LANE_CROSS_REPEAT_S;
        let pan = if self.lane.crossed > 0 { -0.6 } else { 0.6 };
        let volume = 1.0f64.min((if repeat { 0.4 } else { 0.7 }) * self.cue_loudness(ctx));
        ctx.audio.play_with("vehicle/lane_line_cross", volume, pan);
        if !repeat {
            ctx.audio.play_with("vehicle/signal_tone", 0.6, pan);
        }
        self.finish_lane_change(ctx, repeat);
    }

    /// The truck has just arrived in a new lane: check the space it moved
    /// into, resolve any dodgeable hazard, and reset keep-right pressure.
    pub fn finish_lane_change(&mut self, ctx: &mut GameContext, quiet: bool) {
        self.left_lane_s = 0.0;
        self.keep_right_nags = 0;
        let lane_index = self.lane.lane;
        let lane_count = self.lane.lane_count;
        let other = self
            .trip
            .traffic_manager
            .vehicle_in_lane(
                self.trip.position_mi,
                lane_index,
                DODGE_CLEARANCE_AHEAD_MI,
                DODGE_CLEARANCE_BEHIND_MI,
                0.0,
                0.0,
            )
            .map(|vehicle| vehicle.vehicle_class.clone());
        if let Some(vehicle_class) = other {
            if self.trip.truck.speed_mph() > LANE_MIN_MPH {
                if self.sideswipe_cooldown_s > 0.0 {
                    // One contact, not three. A truck pinballing across the same
                    // painted line ran this branch on every crossing, so a single
                    // sideswipe was billed and announced repeatedly inside half a
                    // second (tester transcript, 2026-08-11). The damage and the
                    // warning both belong to the contact, and it happened once.
                    return;
                }
                self.sideswipe_cooldown_s = SIDESWIPE_REPEAT_S;
                ctx.audio.play("vehicle/collision");
                ctx.controller.rumble.impact(SIDESWIPE_DAMAGE);
                self.trip.truck.apply_collision(SIDESWIPE_DAMAGE, true);
                let text = format!(
                    "You sideswiped a {vehicle_class} in the {} lane! The truck took damage, now \
                     {:.0} percent. Check your mirrors before moving over.",
                    self.lane.lane_name(),
                    self.trip.truck.damage_pct
                );
                ctx.say_event_with(text, SayEvent::new().category(SpeechCategory::Safety));
                return;
            }
        }
        if self.hazard_deadline.is_some() && self.hazard_dodgeable && lane_index != self.hazard_lane
        {
            // The swerve answered it, so the assist's application comes off
            // with the hazard rather than being left on a truck now clear of
            // it. Terse mode's whole confirmation is the hazard-clear earcon
            // that just played; failure is the collision sound and its
            // spoken damage line, so the outcome pair is never ambiguous
            // (R4, R14).
            let names = self.hazard_names_text();
            self.finish_hazard_clear(ctx, &format!("You swerve around {names}. Well done."));
            return;
        }
        if !quiet {
            // ROUTE, not the ambient default: the driver's only confirmation
            // of where a lane change landed, same class as the lane-open
            // precedent in driving_lane_gap.py (automation-handoff sweep,
            // 2026-08-20, the deferred 2026-08-15 audit).
            ctx.say_event_with(
                format!("In {}.", lane_phrase(lane_index, lane_count)),
                SayEvent::queued()
                    .priority(EventPriority::Route)
                    .category(SpeechCategory::Confirmation),
            );
        }
    }

    /// The coned-off lane index in the truck's own lane numbering.
    ///
    /// Asked of the trip, which reads the closure's side against the lanes
    /// the road has here, and told the count the truck is actually steering
    /// in -- the exit ramp is one lane whatever the mainline carries. This
    /// is the only place the driving state learns which lane is shut, so no
    /// two checks can answer differently.
    pub fn closed_lane_here(&self) -> Option<i64> {
        self.trip.closed_lane_at(None, Some(self.lane.lane_count))
    }

    /// The nearest lane the truck may legally be in, or None if there is
    /// no such lane.
    pub fn open_lane_beside(&self, closed: i64) -> Option<i64> {
        let count = self.lane.lane_count;
        if count < 2 {
            return None;
        }
        let candidate = if closed > 0 { closed - 1 } else { closed + 1 };
        if !(0..count).contains(&candidate) || candidate == closed {
            return None;
        }
        Some(candidate)
    }

    /// Move the truck out of a closure it never drove into, and say so
    /// whenever the road itself -- closure or not -- just forced a move.
    ///
    /// The road, not the driver, can put a truck in coned-off lanes: where a
    /// stretch narrows, the lane count renumbers the lanes under the truck
    /// and the count clamp drops it a lane over, which can be the closed one.
    /// Shane's Detroit-Mansfield run is what that sounds like -- told the
    /// right lane was closed, moved left, and then put back in the closed
    /// lane with nothing to do about it. Whenever the road moves the truck
    /// into a closure it is moved straight back out and told so; only a lane
    /// the driver steered into is theirs to answer for.
    ///
    /// A narrowing stretch with no work zone at all used to say nothing --
    /// `LaneKeeping::set_lane_count` clamps the lane index silently, so a
    /// driver in the soon-to-vanish lane was simply moved with no warning
    /// (Darren, 2026-08-14). That gets the same never-dropped treatment as
    /// the closure call above, just without "closed": the road narrowed, not
    /// a work zone. Skipped on the exit ramp, whose own single-lane count and
    /// its own announcements are a different situation entirely.
    pub fn leave_a_lane_the_road_closed(&mut self, ctx: &mut GameContext) {
        let count = self.lane.lane_count;
        let was = self.lane_count_seen;
        self.lane_count_seen = Some(count);
        let Some(was) = was else {
            return; // the road did not change under the truck
        };
        if was == count {
            return;
        }
        let closed = self.closed_lane_here();
        if let Some(closed) = closed {
            if self.lane.lane == closed {
                let Some(open_lane) = self.open_lane_beside(closed) else {
                    return;
                };
                let open_name = lane_label(open_lane, count);
                self.lane.lane = open_lane;
                self.lane.offset = 0.0;
                self.lane_change_target = None;
                self.merge_deadline = None;
                let volume = 1.0f64.min(0.7 * self.cue_loudness(ctx));
                ctx.audio.play_with("vehicle/lane_line_cross", volume, 0.0);
                let text = format!(
                    "The {} lane is closed where the road narrows. You are in the {open_name} lane.",
                    lane_label(closed, count)
                );
                ctx.say_event_with(text, SayEvent::new().category(SpeechCategory::Safety));
                return;
            }
        }
        let before_lane = self.lane_before_narrow;
        if self.ramp_mi.is_none()
            && before_lane.is_some_and(|before| before >= count && before != self.lane.lane)
        {
            let volume = 1.0f64.min(0.7 * self.cue_loudness(ctx));
            ctx.audio.play_with("vehicle/lane_line_cross", volume, 0.0);
            // Naming the lane is only worth saying while there is another one
            // it could have been. Narrowing to one lane already said which
            // lane you are in by saying there is only one.
            let moved = if count <= 1 {
                "You are moved over.".to_string()
            } else {
                format!(
                    "You are moved to the {} lane.",
                    lane_label(self.lane.lane, count)
                )
            };
            let text = format!("The road narrows to {}. {moved}", lane_count_words(count));
            ctx.say_event_with(text, SayEvent::new().category(SpeechCategory::Safety));
        }
    }

    /// Riding a coned-off lane: one urgent warning, then the barrels win.
    pub fn update_merge(&mut self, ctx: &mut GameContext, dt: f64) {
        let zone = self.trip.active_closure(None);
        let closed = self.closed_lane_here();
        let Some(closed) = closed else {
            self.merge_deadline = None;
            return;
        };
        if self.lane.lane != closed || self.trip.truck.speed_mph() < LANE_MIN_MPH {
            self.merge_deadline = None;
            return;
        }
        if self.lane.lane_count < 2 {
            // Nowhere to merge to: the road under this closure runs one lane
            // our side. Zone placement will not do this any more, but a saved
            // trip or a stretch that narrows mid-zone still can, and ordering
            // a driver into a lane that does not exist -- then charging them
            // for staying put -- is the worst thing this code could do.
            self.merge_deadline = None;
            return;
        }
        let Some(open_lane) = self.open_lane_beside(closed) else {
            self.merge_deadline = None;
            return;
        };
        let open_name = lane_label(open_lane, self.lane.lane_count);
        if let Some(zone) = zone.as_ref() {
            if zone.reason != "construction" {
                // Still in the taper: the lane is closing, not closed. Say so
                // once, and leave the barrel clock for the work zone itself.
                let taper_key = format!("{}:{:.2}", zone.reason, zone.start_mi);
                if self.merge_taper_warned.as_deref() != Some(taper_key.as_str()) {
                    self.merge_taper_warned = Some(taper_key);
                    ctx.audio.play("ui/warning");
                    let text = format!(
                        "The {} lane closes at the work zone ahead. Move to the {open_name} lane.",
                        lane_label(closed, self.lane.lane_count)
                    );
                    ctx.say_event_with(text, SayEvent::new().category(SpeechCategory::Safety));
                }
                return;
            }
        }
        if self.merge_deadline.is_none() {
            self.merge_deadline = Some(MERGE_WINDOW_S);
            ctx.audio.play("ui/warning");
            ctx.controller.rumble.alert();
            let text = format!(
                "You are in the closed {} lane! Move to the {open_name} lane!",
                lane_label(closed, self.lane.lane_count)
            );
            ctx.say_event_with(text, SayEvent::new().category(SpeechCategory::Safety));
            return;
        }
        if self
            .lane_change_target
            .is_some_and(|target| target != closed)
        {
            return; // already moving over: hold the countdown
        }
        let left = self.merge_deadline.unwrap_or(0.0) - dt;
        self.merge_deadline = Some(left);
        if left <= 0.0 {
            self.merge_deadline = None;
            self.lane.lane = open_lane;
            self.lane.offset = 0.0;
            self.lane_change_target = None;
            ctx.audio.play("vehicle/collision");
            ctx.controller.rumble.impact(MERGE_BARRELS_DAMAGE);
            self.trip.truck.apply_collision(MERGE_BARRELS_DAMAGE, true);
            let text = format!(
                "You plowed through the barrels and lurched into the {open_name} lane. The truck \
                 took damage, now {:.0} percent.",
                self.trip.truck.damage_pct
            );
            ctx.say_event_with(text, SayEvent::new().category(SpeechCategory::Safety));
            if let Some(zone) = zone.as_ref() {
                self.cite_barrel_strike(ctx, zone);
            }
        }
    }

    /// Charge the citation for knocking down work zone barrels.
    ///
    /// Charged where the chain-law citation is, and for the same reason:
    /// this is written on the spot, mid-drive, and asking a driver who has
    /// just taken a collision to also run a shoulder stop stacks two demands
    /// on one moment. The record entry is a serious violation, not just
    /// money -- the offense endangers the crew, not the truck.
    ///
    /// Charged once per work zone. The barrels can catch a truck several
    /// times over one closure (the tester's log has two strikes in eight
    /// seconds); that is one refusal to merge, so it is one citation. The
    /// damage still lands every time.
    pub fn cite_barrel_strike(&mut self, ctx: &mut GameContext, zone: &Zone) {
        // An open lane is what makes this the driver's fault. A truck with
        // nowhere to merge cannot be charged for staying where it is -- the
        // merge update returns long before here in that case, and this second
        // reading is deliberate: no future edit above may make this reachable.
        if self.lane.lane_count < 2 || self.enforcement_bypassed(ctx) {
            return;
        }
        let key = format!("barrels:{:.1}", zone.start_mi);
        if self.enforcement_events.contains(&key) {
            return;
        }
        self.enforcement_events.insert(key);
        if ctx.profile.is_none() {
            return;
        }
        // NOT doubled for the construction zone, unlike every other citation.
        // The zone multiplier exists because states double an ordinary moving
        // violation committed in roadwork. This offense only exists inside
        // roadwork, and its base is Missouri RSMo 304.585, which is already the
        // work-zone-specific penalty and caps a first offense at 1,000. Passing
        // construction_zone=True here would charge twice for the same
        // aggravating fact and put every first offense at double the statutory
        // maximum. Priors still escalate it.
        let fine = citation_fine(
            ff_core::models::enforcement::WORK_ZONE_BARRELS_FINE,
            career_citations(profile_of(ctx)),
            false,
            None,
        );
        let money = {
            let p = profile_mut_of(ctx);
            p.money -= fine;
            p.money
        };
        self.ticket_fines_paid += fine;
        let saw_it = match self.trip.active_post_at(self.trip.position_mi) {
            Some(post) => format!("A trooper working this {} saw it", post.reason()),
            None => "The work crew called it in".to_string(),
        };
        let ladder = self.log_enforcement(ctx, fine, true, false);
        ctx.audio.play("ui/error");
        let tail = if ladder.is_empty() {
            String::new()
        } else {
            format!(" {ladder}")
        };
        ctx.say_event_with(
            // No doubled-for-the-zone clause: this citation is not doubled,
            // because its amount is already the roadwork penalty.
            format!(
                "{saw_it}. Driving through the barrels is a citation: {} dollars, and it goes on \
                 your safety record. You have {} dollars.{tail}",
                fmt_grouped(fine, 0),
                fmt_grouped(money, 0)
            ),
            // Money rides ROUTE's never-dropped contract: a busy stretch must
            // not age a citation out of the queue.
            SayEvent::queued()
                .priority(EventPriority::Route)
                .category(SpeechCategory::Money),
        );
    }

    /// Left-lane time is legitimate while passing slower right-lane
    /// traffic, or while construction has the right lane coned off.
    pub fn keep_right_justified(&self) -> bool {
        if self.closed_lane_here() == Some(0) {
            return true;
        }
        let speed = self.trip.truck.speed_mph();
        self.trip
            .traffic_manager
            .vehicle_in_lane(
                self.trip.position_mi,
                0,
                PASSING_LOOKAHEAD_MI,
                0.05,
                0.0,
                0.0,
            )
            .is_some_and(|slower| slower.speed_mph < speed + 3.0)
    }

    /// Camping the left lane draws CB grumbling: keep right except to pass.
    pub fn update_keep_right(&mut self, ctx: &mut GameContext, dt: f64) {
        if self.lane.lane_count < 2
            || self.lane.lane != self.lane.lane_count - 1
            || self.trip.truck.speed_mph() < KEEP_RIGHT_MIN_MPH
            || self.ramp_mi.is_some()
        {
            self.left_lane_s = 0.0;
            self.keep_right_nags = 0;
            return;
        }
        if self.keep_right_justified() {
            self.left_lane_s = (self.left_lane_s - dt).max(0.0);
            return;
        }
        self.left_lane_s += dt;
        let threshold = KEEP_RIGHT_NAG_S + self.keep_right_nags as f64 * KEEP_RIGHT_REPEAT_S;
        if self.left_lane_s < threshold {
            return;
        }
        self.keep_right_nags += 1;
        if self.keep_right_nags == 1 {
            let grumble = "CB chatter: you have been riding the left lane a while. Keep right \
                           except to pass.";
            // Repeatable with Alt C like any other CB call. No post and no
            // distance in it, so the repeat says it back word for word.
            self.last_cb_chatter = Some(CbChatterRecall {
                text: grumble.to_string(),
                post: None,
            });
            self.speak_ambient_event(
                ctx,
                SpokenMessage::new(grumble),
                Ambient::new().sound(Some("events/cb_radio_chatter")),
            );
        } else {
            ctx.audio.play_with("traffic/car_pass", 0.9, 0.5);
            self.speak_ambient_event(
                ctx,
                SpokenMessage::new(
                    "Traffic is stacking up and passing you on the right. Move back to the right \
                     lane.",
                ),
                Ambient::new().sound(Some("events/cb_radio_chatter")),
            );
        }
    }
}
