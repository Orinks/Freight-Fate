//! Working the pedals for a ramp terminal, and crossing it: honour the light
//! or the sign, or pay for it.

use ff_core::speech_pacing::SpeechCategory;

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

use super::pending::assist_servo_brake;
use super::ramp_terminal::CrossMeeting;

impl DrivingState {
    /// Route-transition assistance works the pedals for the terminal.
    ///
    /// Stopping a rig blind inside the bar's grace window while the light
    /// cycles in real time is a positioning task whose failure mode is
    /// trailer damage -- the 2026-07-22 playtest ended a clean run with cross
    /// traffic in the trailer. With route-transition assistance on, the assist
    /// brakes for a red (or a yellow it cannot legally beat), holds the stop
    /// at the bar, and keeps a green crossing under the clean-roll speed. The
    /// phases still speak, and pulling ahead when the light releases stays the
    /// driver's move.
    pub fn update_ramp_terminal_assist(&mut self, ctx: &mut GameContext) {
        if !ctx.settings.route_transition_assist {
            return;
        }
        let Some(ramp_mi) = self.ramp_mi else {
            return;
        };
        if self.ramp_terminal_done {
            return;
        }
        if !matches!(
            self.ramp_control.as_str(),
            "signal" | "stop" | "yield" | "roundabout"
        ) || !self.ramp_light_announced
        {
            return;
        }
        if self.ramp_waiting_at_light {
            // Holding for green: the assist keeps the brakes on.
            self.trip.truck.throttle = 0.0;
            self.trip.truck.brake = 1.0;
            return;
        }
        let gap_mi = ramp_mi - RAMP_ACCESS_MI;
        let speed = self.trip.truck.speed_mph();
        if self.ramp_control == "signal" {
            let phase = self.ramp_light_phase();
            let must_stop = phase == "red" || (phase == "yellow" && gap_mi > 0.0);
            if !must_stop {
                // A green (or a yellow already at the bar) is legal to roll,
                // but not at speed: hold the crossing under the clean-roll
                // threshold with room to spare.
                if gap_mi <= super::pending::bar_tick_range_mi(&self.trip.truck)
                    && speed > GREEN_ROLL_MPH - 5.0
                {
                    self.trip.truck.throttle = 0.0;
                    self.trip.truck.brake = self.trip.truck.brake.max(0.4);
                }
                return;
            }
        }
        if matches!(self.ramp_control.as_str(), "yield" | "roundabout") {
            let clear = self
                .cross_bubble
                .as_ref()
                .is_none_or(|bubble| bubble.clear_to_cross());
            if clear {
                // A clear yield is rolled, not stopped: the assist holds the
                // crossing at roll speed and the gap verdict lands at the
                // line. Braking to a dead stop on a clear yield is the
                // rear-end setup the roadmap warns the LEAD car will pull.
                if gap_mi <= super::pending::bar_tick_range_mi(&self.trip.truck)
                    && speed > YIELD_ROLL_MPH - 3.0
                {
                    self.trip.truck.throttle = 0.0;
                    self.trip.truck.brake = self.trip.truck.brake.max(0.4);
                }
                return;
            }
            // Not clear: fall through and brake for the line like a stop.
        }
        if speed <= RED_STOP_MPH && gap_mi <= RAMP_ASSIST_HOLD_MI {
            // At the bar with the truck stopped: the assist owns the hold.
            self.trip.truck.throttle = 0.0;
            self.trip.truck.brake = 1.0;
            self.ramp_assist_brake = 0.0;
            if matches!(self.ramp_control.as_str(), "stop" | "yield" | "roundabout") {
                // The assist holds the stop; the release now waits for the
                // bubble's gap, same as an unassisted stop. The hold above
                // keeps the brakes on through the wait.
                let noun = match self.ramp_control.as_str() {
                    "stop" => "sign",
                    "yield" => "yield",
                    _ => "roundabout entry",
                };
                let blocked = self
                    .cross_bubble
                    .as_ref()
                    .is_some_and(|bubble| !bubble.clear_to_cross());
                if blocked {
                    if !self.ramp_waiting_at_sign {
                        self.ramp_waiting_at_sign = true;
                        let what = self.crossing_description();
                        self.say_route_navigation(
                            ctx,
                            &format!(
                                "Stopped at the {noun}. {what}; assistance is holding for your gap."
                            ),
                        );
                    }
                    return;
                }
                self.ramp_terminal_done = true;
                let message = if self.ramp_waiting_at_sign {
                    "Gap in traffic. Clear; pull ahead to the entrance.".to_string()
                } else {
                    format!("Stopped at the {noun}. Clear; pull ahead to the entrance.")
                };
                self.ramp_waiting_at_sign = false;
                self.say_route_navigation(ctx, &message);
            } else if !self.ramp_waiting_at_light {
                self.ramp_waiting_at_light = true;
                // ROUTE, not the ambient default: names an automation (the ramp
                // assist) that just took the brakes, same as the stop-sign
                // sibling above (automation-handoff sweep, 2026-08-20, the
                // deferred 2026-08-15 audit).
                self.say_route_confirmation(
                    ctx,
                    "Stopped at the red light. Assistance is holding the brakes for green.",
                );
            }
            return;
        }
        if speed <= RED_STOP_MPH {
            // Already stopped, but short of the hold window: a driver braking
            // on their own on top of the assist lands here, and a standing
            // truck has nothing left to brake for. The assist must hand the
            // pedals back -- pinning throttle at zero and the brake at its
            // floor against a truck that is already stopped is a hold with no
            // release, and the driver cannot move again (playtest softlock,
            // 2026-07-24). The queue guidance is what tells them to close the
            // gap to the bar from here. Dropping the held application matters
            // for the same reason: a creep to the bar must start from an open
            // pedal, not from whatever the approach was holding.
            self.ramp_assist_brake = 0.0;
            return;
        }
        // Brake down the approach: needed deceleration to stop at the bar,
        // recomputed each tick, mapped onto brake application. As the gap
        // closes the demand rises and the pedal follows.
        let gap_m = 0.5f64.max(gap_mi * 1609.344);
        let v_mps = 0.0f64.max(self.trip.truck.velocity_mps);
        let needed = (v_mps * v_mps) / (2.0 * gap_m);
        let idle = self.ramp_assist_brake <= 0.0;
        if idle && needed < RAMP_ASSIST_DECEL_START_MPS2 && gap_m > 30.0 {
            return;
        }
        self.ramp_assist_brake =
            assist_servo_brake(self.ramp_assist_brake, needed, &self.trip.truck);
        self.trip.truck.throttle = 0.0;
        self.trip.truck.brake = self.trip.truck.brake.max(self.ramp_assist_brake);
        if !self.ramp_assist_said {
            self.ramp_assist_said = true;
            // A transit stop: the bar is honored and then driven away from, so
            // the session comes back on its own past it rather than waiting
            // for a departure that never happens on a ramp.
            self.pause_speed_control(ctx, true);
            let what = match self.ramp_control.as_str() {
                "signal" => "light",
                "stop" => "stop sign",
                "yield" => "yield",
                "roundabout" => "roundabout",
                _ => "stop sign",
            };
            self.say_route_confirmation(
                ctx,
                &format!("Route-transition assistance braking for the {what}."),
            );
        }
    }

    /// "A semi crossing from the left", or "Cross traffic" with nothing near.
    fn crossing_description(&self) -> String {
        match self
            .cross_bubble
            .as_ref()
            .and_then(|bubble| bubble.approaching(8.0))
        {
            Some(nearest) => format!(
                "A {} crossing from the {}",
                nearest.vehicle_class, nearest.from_side
            ),
            None => "Cross traffic".to_string(),
        }
    }

    /// Crossing the terminal: honor the light or the sign, or pay for it.
    ///
    /// A driver still braking gets the length of the grace distance past the
    /// bar to finish the stop; carrying speed beyond it commits the run.
    pub fn update_ramp_terminal(&mut self, ctx: &mut GameContext) {
        let speed = self.trip.truck.speed_mph();
        let past_bar = self
            .ramp_mi
            .is_some_and(|ramp_mi| ramp_mi <= RAMP_ACCESS_MI - RAMP_TERMINAL_GRACE_MI);
        if self.ramp_control == "signal" {
            self.cross_traffic_light(ctx, speed, past_bar);
            return;
        }
        if self.ramp_control == "stop" {
            self.cross_stop_sign(ctx, speed, past_bar);
            return;
        }
        if matches!(self.ramp_control.as_str(), "yield" | "roundabout") {
            self.cross_yield(ctx, speed, past_bar);
            return;
        }
        self.ramp_terminal_done = true;
    }

    fn cross_traffic_light(&mut self, ctx: &mut GameContext, speed: f64, past_bar: bool) {
        if self.ramp_light_is_red() {
            if speed <= RED_STOP_MPH {
                if !self.ramp_waiting_at_light {
                    self.ramp_waiting_at_light = true;
                    self.say_route_navigation(
                        ctx,
                        "Stopped at the red light. Hold the brakes for green.",
                    );
                }
                return;
            }
            if !past_bar {
                return; // still braking down to the stop bar
            }
            self.ramp_terminal_done = true;
            self.ramp_waiting_at_light = false;
            // What the run actually meets is the bubble's answer now,
            // not the old certainty: cross traffic flows on the player's
            // red, so this usually finds a vehicle -- but a gambler who
            // threads a real gap gets away with it, exactly like the road.
            let (met, vehicle) = self.cross_violation_meets();
            let pan = if vehicle
                .as_ref()
                .is_none_or(|vehicle| vehicle.from_side == "left")
            {
                -0.4
            } else {
                0.4
            };
            let cue = Self::cross_vehicle_sound(vehicle.as_ref());
            if speed > STOP_ROLL_CLIP_MPH {
                match met {
                    CrossMeeting::Hit => {
                        ctx.audio.play_with(&cue, 1.0, pan);
                        ctx.audio.play("vehicle/collision");
                        ctx.controller.rumble.impact(RED_RUN_DAMAGE);
                        // A driver already hard on the brakes, carried through
                        // by the load, did not make a preventable mistake. The
                        // violation still stands; the discipline does not.
                        let preventable = !self.trip.truck.pushed_through_by_surge();
                        self.trip.truck.apply_collision(RED_RUN_DAMAGE, preventable);
                        let damage = self.trip.truck.damage_pct;
                        self.say_safety_interrupt(
                            ctx,
                            &format!(
                                "You ran the red light at the ramp end and cross traffic clipped \
                                 the trailer! Total damage {damage:.0} percent."
                            ),
                        );
                    }
                    CrossMeeting::Near => {
                        ctx.audio.play_with(&cue, 1.0, pan);
                        self.say_confirmation_interrupt(
                            ctx,
                            "You ran the red light at the ramp end. Cross traffic brakes hard and \
                             leans on the horn.",
                        );
                    }
                    CrossMeeting::Empty => {
                        self.say_confirmation_interrupt(
                            ctx,
                            "You ran the red light at the ramp end. Nothing was crossing; nothing \
                             will be next time.",
                        );
                    }
                }
            } else if met == CrossMeeting::Empty {
                self.say_confirmation_interrupt(
                    ctx,
                    "You crept through the red light. Nothing was crossing this time.",
                );
            } else {
                ctx.audio.play_with(&cue, 1.0, pan);
                self.say_confirmation_interrupt(
                    ctx,
                    "You crept through the red light. Cross traffic leans on the horn.",
                );
            }
            return;
        }
        self.ramp_terminal_done = true;
        self.ramp_waiting_at_light = false;
        ctx.audio.play_with("events/ramp_light_green", 0.7, 0.0);
        let on_yellow = self.ramp_light_phase() == "yellow";
        let message = if speed > GREEN_ROLL_MPH {
            "Through the light, but far too fast. Brake hard for the entrance."
        } else if on_yellow {
            "Through on the yellow; brake for the entrance."
        } else {
            "Green light. Through the intersection; brake for the entrance."
        };
        self.say_route_confirmation(ctx, message);
    }

    fn cross_stop_sign(&mut self, ctx: &mut GameContext, speed: f64, past_bar: bool) {
        if speed > RED_STOP_MPH && !past_bar {
            return; // still braking down to the stop bar
        }
        if speed <= RED_STOP_MPH {
            // Stopped at the sign: the clear call now waits for a real
            // gap in the cross bubble instead of arriving with the stop.
            // The crossing cues are the information -- each one is a
            // vehicle in the ear it comes from -- and "clear" is spoken
            // only when the window is genuinely open.
            let blocked = self
                .cross_bubble
                .as_ref()
                .is_some_and(|bubble| !bubble.clear_to_cross());
            if blocked {
                if !self.ramp_waiting_at_sign {
                    self.ramp_waiting_at_sign = true;
                    let what = self.crossing_description();
                    self.say_route_navigation(
                        ctx,
                        &format!("Stopped at the sign. {what}; wait for your gap."),
                    );
                }
                return;
            }
            self.ramp_terminal_done = true;
            let message = if self.ramp_waiting_at_sign {
                "Gap in traffic. Clear; pull ahead to the entrance."
            } else {
                "Stopped at the sign. Clear; pull ahead to the entrance."
            };
            self.ramp_waiting_at_sign = false;
            self.say_route_navigation(ctx, message);
            return;
        }
        self.ramp_terminal_done = true;
        // Same honesty as the light: the bubble says what the blown sign
        // actually met. A stop-sign crossroad is often empty -- that is
        // what makes rolling one tempting, and what makes the day a
        // semi IS crossing the lesson it should be.
        let (met, vehicle) = self.cross_violation_meets();
        let pan = if vehicle
            .as_ref()
            .is_none_or(|vehicle| vehicle.from_side == "right")
        {
            0.4
        } else {
            -0.4
        };
        let cue = Self::cross_vehicle_sound(vehicle.as_ref());
        if speed > STOP_ROLL_CLIP_MPH {
            match met {
                CrossMeeting::Hit => {
                    ctx.audio.play_with(&cue, 1.0, pan);
                    ctx.audio.play("vehicle/collision");
                    ctx.controller.rumble.impact(STOP_ROLL_DAMAGE);
                    let preventable = !self.trip.truck.pushed_through_by_surge();
                    self.trip
                        .truck
                        .apply_collision(STOP_ROLL_DAMAGE, preventable);
                    let damage = self.trip.truck.damage_pct;
                    self.say_safety_interrupt(
                        ctx,
                        &format!(
                            "You blew the stop sign at the ramp end and clipped cross traffic! \
                             Total damage {damage:.0} percent."
                        ),
                    );
                }
                CrossMeeting::Near => {
                    ctx.audio.play_with(&cue, 1.0, pan);
                    self.say_confirmation_interrupt(
                        ctx,
                        "You blew the stop sign at the ramp end. Cross traffic brakes hard and \
                         leans on the horn.",
                    );
                }
                CrossMeeting::Empty => {
                    self.say_confirmation_interrupt(
                        ctx,
                        "You blew the stop sign at the ramp end. The crossroad was empty; it will \
                         not always be.",
                    );
                }
            }
        } else if met == CrossMeeting::Empty {
            self.say_confirmation_interrupt(
                ctx,
                "You rolled the stop sign at the ramp end. Nothing was crossing this time.",
            );
        } else {
            ctx.audio.play_with(&cue, 1.0, pan);
            self.say_confirmation_interrupt(
                ctx,
                "You rolled the stop sign at the ramp end. Cross traffic leans on the horn.",
            );
        }
    }

    /// The yield rule, straight from the sign: a gap taken at roll speed is
    /// the clean crossing, stopping is always legal, and an occupied window is
    /// the clip machinery -- at THEIR closing speed, because you rolled under
    /// their bumper.
    fn cross_yield(&mut self, ctx: &mut GameContext, speed: f64, past_bar: bool) {
        let noun = if self.ramp_control == "roundabout" {
            "roundabout"
        } else {
            "yield"
        };
        if speed <= RED_STOP_MPH {
            // Stopped: exactly the stop sign's wait, spoken for a yield.
            let blocked = self
                .cross_bubble
                .as_ref()
                .is_some_and(|bubble| !bubble.clear_to_cross());
            if blocked {
                if !self.ramp_waiting_at_sign {
                    self.ramp_waiting_at_sign = true;
                    let what = self.crossing_description();
                    self.say_route_navigation(
                        ctx,
                        &format!("Stopped at the {noun}. {what}; wait for your gap."),
                    );
                }
                return;
            }
            self.ramp_terminal_done = true;
            self.ramp_waiting_at_sign = false;
            self.say_route_navigation(ctx, "Gap in traffic. Clear; pull ahead to the entrance.");
            return;
        }
        if !past_bar {
            return; // still rolling down to the line; the gap decides there
        }
        self.ramp_terminal_done = true;
        let (met, vehicle) = self.cross_violation_meets();
        let pan = if vehicle
            .as_ref()
            .is_none_or(|vehicle| vehicle.from_side == "right")
        {
            0.4
        } else {
            -0.4
        };
        let cue = Self::cross_vehicle_sound(vehicle.as_ref());
        if met == CrossMeeting::Hit {
            ctx.audio.play_with(&cue, 1.0, pan);
            ctx.audio.play("vehicle/collision");
            ctx.controller.rumble.impact(STOP_ROLL_DAMAGE);
            let preventable = !self.trip.truck.pushed_through_by_surge();
            self.trip
                .truck
                .apply_collision(STOP_ROLL_DAMAGE, preventable);
            let damage = self.trip.truck.damage_pct;
            self.say_safety_interrupt(
                ctx,
                &format!(
                    "You rolled the {noun} into cross traffic and it clipped the trailer! Total \
                     damage {damage:.0} percent."
                ),
            );
        } else if met == CrossMeeting::Near {
            ctx.audio.play_with(&cue, 1.0, pan);
            self.say_confirmation_interrupt(
                ctx,
                &format!(
                    "You forced the gap at the {noun}. Cross traffic brakes hard and leans on the \
                     horn."
                ),
            );
        } else if speed > YIELD_ROLL_MPH {
            self.say_route_confirmation(
                ctx,
                &format!("Through the {noun}, but far too fast. Brake hard for the entrance."),
            );
        } else {
            self.say_route_confirmation(
                ctx,
                &format!("Through the {noun} in a gap. Pull ahead to the entrance."),
            );
        }
    }

    /// One interrupting SAFETY line.
    pub(crate) fn say_safety_interrupt(&self, ctx: &mut GameContext, message: &str) {
        let mut opts = SayEvent::new();
        opts.category = Some(SpeechCategory::Safety);
        ctx.say_event_with(message.to_string(), opts);
    }

    /// One interrupting CONFIRMATION line.
    pub(crate) fn say_confirmation_interrupt(&self, ctx: &mut GameContext, message: &str) {
        let mut opts = SayEvent::new();
        opts.category = Some(SpeechCategory::Confirmation);
        ctx.say_event_with(message.to_string(), opts);
    }
}
