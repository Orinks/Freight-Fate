//! The per-frame advance of an armed exit or an active ramp, the destination
//! terminal loop-back, and the planned-stop stopping assist.

use ff_core::speech_pacing::SpeechCategory;

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

use super::pending::assist_servo_brake;

impl DrivingState {
    /// Advance an armed exit or an active ramp; opens the stop menu.
    pub fn update_exit(&mut self, ctx: &mut GameContext, moved_mi: f64, dt: f64) {
        // Real time from the gore to the terminal: while the ramp ends in
        // a live light or sign, the clock must not compress the seconds
        // the driver needs to brake for it.
        self.trip.controlled_ramp = self.ramp_mi.is_some()
            && matches!(
                self.ramp_control.as_str(),
                "signal" | "stop" | "yield" | "roundabout"
            )
            && !self.ramp_terminal_done;
        self.trip.dock_run_in = self.ramp_mi.is_some()
            && self
                .ramp_stop
                .as_ref()
                .is_some_and(|stop| stop.stop_type == "delivery_destination");
        // And the road left to an exit the driver has signalled for, which the
        // clock reads to decide whether the approach itself is close enough to
        // be driven in real time. None once the ramp is taken -- from there
        // `controlled_ramp` owns the clock -- or once the exit is behind.
        // A canceled signal is not an approach. The stop itself is kept until
        // the truck passes it, so the game can say the exit went by unused --
        // but reading THAT as "still approaching an exit" held the clock in
        // real time all the way to a stop the driver had already begged off,
        // which from the seat is the road refusing to speed back up (Shane P,
        // 2026-08-21).
        let ahead_to_exit = match (&self.exit_stop, self.ramp_mi, self.exit_signal_canceled) {
            (Some(stop), None, false) => Some(stop.at_mi - self.trip.position_mi),
            _ => None,
        };
        self.trip.exit_approach_mi = ahead_to_exit.filter(|ahead| *ahead > 0.0);
        if self.ramp_mi.is_some() {
            self.update_active_ramp(ctx, moved_mi, dt);
            return;
        }
        self.update_armed_exit(ctx);
    }

    /// The `_ramp_mi is not None` half of `_update_exit`.
    fn update_active_ramp(&mut self, ctx: &mut GameContext, moved_mi: f64, dt: f64) {
        let ramp_mi = self.ramp_mi.expect("checked by the caller") - moved_mi;
        self.ramp_mi = Some(ramp_mi);
        if !self.ramp_light_announced && ramp_mi <= RAMP_CONTROL_ANNOUNCE_MI {
            self.announce_ramp_terminal(ctx);
        }
        self.update_ramp_terminal_assist(ctx);
        if self.update_selected_stop_assist(ctx) {
            return;
        }
        if !self.ramp_terminal_done && ramp_mi <= RAMP_ACCESS_MI {
            self.update_ramp_terminal(ctx);
        }
        if ramp_mi > 0.0 {
            return;
        }
        let stop = self
            .ramp_stop
            .clone()
            .expect("a ramp always carries a stop");
        if stop.stop_type == "delivery_destination"
            && self.ramp_terminal_done
            && self.begin_surface_chain(ctx, true)
        {
            // The street chain is a DRIVING continuation: hand off at
            // whatever legal speed the terminal let through. Gating the
            // handoff on docking speed marooned a green-light roll past
            // the end of the ramp -- the streets refused to start until
            // the driver stopped dead in the road (owner playtest,
            // 2026-07-24). The scripted dock-menu arrival below still
            // rightly waits for a crawl.
            self.ramp_mi = None;
            self.ramp_stop = None;
            self.ramp_control = String::new();
            return;
        }
        if self.trip.truck.speed_mph() <= DOCKING_MAX_MPH {
            self.ramp_mi = None;
            self.ramp_stop = None;
            self.ramp_control = String::new();
            if stop.stop_type == "delivery_destination" {
                if self.begin_surface_chain(ctx, true) {
                    return;
                }
                self.trip.position_mi = self.trip.total_miles();
                self.trip.finished = true;
                self.open_facility_arrival(ctx);
            } else {
                self.open_poi_stop(ctx, &stop, true, None);
            }
            return;
        }
        if stop.stop_type == "delivery_destination"
            && self.destination_arrival_active
            && self.trip.truck.speed_mph() <= DELIVERY_PARK_MPH
        {
            // The destination approach assist is walking the truck over
            // the point and its own full brake at the point lands it a
            // moment later, so "come to a complete stop" here would be an
            // instruction the truck is already carrying out -- and at the
            // quiet rung an interrupt for it. The dock line that follows
            // names the place. A truck that somehow keeps rolling still
            // meets the blown-stop rule below once it is clear past.
            return;
        }
        if !self.ramp_end_said {
            if stop.stop_type == "delivery_destination"
                && !self.surface_chain
                && self.surface_chain_route(ctx).is_some()
            {
                // The facility has a street chain, so "you are at X"
                // here is a lie by two miles: the driver was told they
                // had arrived and then handed turn-by-turn streets
                // (owner log, 2026-07-23, Sacramento Dry Warehouse).
                // The chain's own "off the ramp and onto city streets"
                // line follows and says it right. The said-latch stays
                // open so the blown-stop rule below can never fire on a
                // chain facility: the streets are still the way in.
                return;
            }
            self.ramp_end_said = true;
            let terse = self.terse_speech(ctx);
            let message = if stop.stop_type != "delivery_destination" {
                let place = stop.spoken_name();
                if terse {
                    format!("At {place}. Stop now.")
                } else {
                    format!("You are at {place}. Come to a complete stop.")
                }
            } else {
                let place = &stop.name;
                if terse {
                    format!("At {place}.")
                } else {
                    format!("You are at {place}. Come to a complete stop.")
                }
            };
            // Both kinds of ramp stop open the same real-time reaction
            // window. The destination opened none at all, so its grace sat
            // at zero forever and nothing downstream could ever read it as
            // spent (owner playtest, Buffalo to Albany, 2026-08-12).
            self.ramp_arrival_grace_s = self.ramp_arrival_grace_for(ctx, &message);
            let mut opts = SayEvent::new();
            opts.category = Some(SpeechCategory::Navigation);
            ctx.say_event_with(message, opts);
            return;
        }
        self.ramp_arrival_grace_s = 0.0f64.max(self.ramp_arrival_grace_s - dt);
        // Rolled clear past the end of the ramp without ever stopping. Both
        // the distance and the real-time grace must expire, so trip pacing
        // cannot consume the player's spoken-cue reaction window.
        if ramp_mi > -RAMP_OVERSHOOT_MI
            || self.ramp_arrival_grace_s > 0.0
            || self.trip.truck.parking_brake
        {
            return;
        }
        if stop.stop_type == "delivery_destination" {
            // The destination terminal used to be the one blown stop with
            // no consequence at all: the arrival line was spoken once, the
            // ramp counted down past it forever, and the player circled
            // with the route status frozen and nothing said until they quit
            // to the menu (owner playtest, Buffalo to Albany, 2026-08-12).
            self.loop_back_to_destination_terminal(ctx, &stop);
            return;
        }
        // A route POI is blown, so give the highway back instead of leaving
        // a stuck, unpatrolled ramp lingering for miles.
        self.ramp_mi = None;
        self.ramp_stop = None;
        self.ramp_end_said = false;
        self.ramp_arrival_grace_s = 0.0;
        let planned = self.trip.is_planned(&stop);
        if planned {
            self.trip.planned_stop_key = None;
        }
        if self.is_selected_stop(Some(&stop)) {
            self.clear_selected_stop_intent();
        }
        let exit_ref = if stop.exit_label.is_empty() {
            format!("the exit for {}", stop.spoken_name())
        } else {
            format!("{} for {}", stop.exit_label, stop.spoken_name())
        };
        let mut line = if self.terse_speech(ctx) {
            format!("Drove past {}; you never stopped.", stop.spoken_name())
        } else {
            format!("You never stopped and drove past {exit_ref}.")
        };
        if planned {
            line.push_str(" Plan cancelled.");
        }
        line.push_str(&format!(
            " Planned rest-stop stopping assistance is off. Continue safely and press {} to plan \
             the next sleep-capable stop.",
            ctx.control_hint("rest")
        ));
        self.say_confirmation_interrupt(ctx, &line);
    }

    /// The `_ramp_mi is None` half of `_update_exit`.
    fn update_armed_exit(&mut self, ctx: &mut GameContext) {
        let Some(stop) = self.exit_stop.clone() else {
            return;
        };
        if self.trip.position_mi < stop.at_mi {
            self.update_exit_countdown(ctx, &stop);
            return;
        }
        self.exit_stop = None;
        // The exit is settled either way now, so the ramp cap comes off:
        // taking it pauses the session for the ramp, and missing it must not
        // leave automatic control crawling at ramp speed down the open highway.
        self.cruise_exit_mph = None;
        if self.exit_signal_canceled {
            self.reset_exit_lane_state();
            self.exit_signal_canceled = false;
            let mut opts = SayEvent::new();
            opts.category = Some(SpeechCategory::Confirmation);
            ctx.say_event_with(
                "Exit signal was canceled, so you stayed on the highway.".to_string(),
                opts,
            );
            return;
        }
        self.exit_signal_canceled = false;
        if self.trip.position_mi > stop.at_mi + EXIT_COMMIT_WINDOW_MI {
            self.reset_exit_lane_state();
            self.exit_signal_on = false;
            if self.is_selected_stop(Some(&stop)) {
                self.clear_selected_stop_intent();
            }
            let pressure = self.active_exit_pressure(&stop);
            let message = if pressure.is_some_and(|pressure| pressure.intensity >= 0.35) {
                "You missed the exit window in heavy traffic and stayed on the highway."
            } else {
                "You missed the exit window and stayed on the highway."
            };
            self.say_confirmation_event(ctx, message);
            return;
        }
        if !self.exit_intent_ready(ctx, &stop) {
            self.reset_exit_lane_state();
            self.exit_signal_on = false;
            if self.is_selected_stop(Some(&stop)) {
                self.clear_selected_stop_intent();
            }
            let place = self.missed_exit_phrase(ctx, &stop);
            self.say_confirmation_event(
                ctx,
                &format!(
                    "You missed {place}: the turn signal was not set. Stay on the highway and \
                     recover at the next safe exit."
                ),
            );
            return;
        }
        if !self.exit_lane_ready() {
            self.reset_exit_lane_state();
            self.exit_signal_on = false;
            if self.is_selected_stop(Some(&stop)) {
                self.clear_selected_stop_intent();
            }
            let missed = self.missed_exit_phrase(ctx, &stop);
            let pressure = self.active_exit_pressure(&stop);
            if pressure.is_some() {
                self.say_confirmation_event(
                    ctx,
                    &format!(
                        "Traffic boxed you out of the exit lane at the gore, so you missed \
                         {missed}. Stay on the highway and recover at the next safe exit."
                    ),
                );
            } else {
                self.say_confirmation_event(
                    ctx,
                    &format!(
                        "You missed {missed}: you were not in the exit lane. Stay on the highway \
                         and recover at the next safe exit."
                    ),
                );
            }
            return;
        }
        // The stop goes in by hand: _exit_stop was cleared above, and without
        // it the gate fell back to the flat 45 and refused a truck doing the
        // road speed it had just been told was fine -- the third gate the
        // roadmap note said to look for (2026-08-21).
        if self.trip.truck.speed_mph() <= self.gore_acceptance_mph(Some(&stop)) {
            self.take_the_ramp(ctx, &stop);
        } else {
            let missed = self.missed_exit_phrase(ctx, &stop);
            let mut line = format!("You were going too fast for the ramp and missed {missed}.");
            if self.trip.is_planned(&stop) {
                // Fold the plan cancellation into this one line so the driver
                // hears a single cue, and clear it here so _check_stops doesn't
                // also emit a "drove past your planned stop" warning next tick.
                self.trip.planned_stop_key = None;
                line.push_str(" Plan cancelled.");
            }
            if self.is_selected_stop(Some(&stop)) {
                self.clear_selected_stop_intent();
            }
            self.say_confirmation_interrupt(ctx, &line);
            self.exit_signal_on = false;
            self.reset_exit_lane_state();
        }
    }

    /// The truck makes the gore: onto the ramp.
    fn take_the_ramp(&mut self, ctx: &mut GameContext, stop: &ff_core::sim::trip_models::RoadStop) {
        self.reset_exit_lane_state();
        self.exit_signal_on = false;
        self.ramp_mi = Some(RAMP_LENGTH_MI);
        self.ramp_stop = Some(stop.clone());
        self.ramp_end_said = false;
        self.ramp_arrival_grace_s = 0.0;
        self.destination_exit_taken = stop.stop_type == "delivery_destination";
        if self.destination_exit_taken {
            self.post_gate_zone();
        }
        // The ramp is a single lane peeling off the right side.
        self.lane.lane = 0;
        self.lane.offset = 0.0;
        self.lane_change_target = None;
        self.merge_deadline = None;
        self.begin_ramp_terminal(ctx, stop);
        // The ramp takes the pedals back, but the SESSION rides along: a
        // ramp terminal is a transit stop, so automatic speed control
        // returns on its own once the bar is honored and the ramp is
        // behind the truck. Disarming here is why both controllers stayed
        // dead until the player pressed resume (Shane, 2026-08-15). The
        // resume helper still refuses the whole ramp, so nothing
        // re-engages between here and the bar.
        //
        // A destination exit is the exception: that ramp ends at the gate,
        // and winding the truck back up on it is exactly what drove a
        // playtest past the terminal at 66 mph. It holds like any other
        // arrival, until the player departs with the next load.
        let transit = stop.stop_type != "delivery_destination";
        self.pause_speed_control(ctx, transit);
        ctx.audio.play_with("ui/notify", 0.7, 0.0);
        let take = if stop.stop_type == "delivery_destination" {
            let phrase = self.exit_phrase_of(ctx, stop);
            let labeled = if phrase.is_empty() {
                stop.exit_label.clone()
            } else {
                phrase
            };
            if labeled.is_empty() {
                format!("You take the destination exit for {}.", stop.name)
            } else {
                format!("You take {labeled}, destination exit for {}.", stop.name)
            }
        } else if stop.exit_label.is_empty() {
            format!("You take the exit for {}.", stop.spoken_name())
        } else {
            format!("You take {} for {}.", stop.exit_label, stop.spoken_name())
        };
        let scale_ramp = stop.stop_type == "weigh_station";
        let message = if self.terse_speech(ctx) {
            let mut terminal = match self.ramp_control.as_str() {
                "signal" => " Traffic light at the end.",
                "stop" => " Stop sign at the end.",
                _ => "",
            };
            if scale_ramp {
                terminal = " The scale is at the end.";
            }
            format!("{take} Half a mile of ramp.{terminal}")
        } else {
            let mut ending = match self.ramp_control.as_str() {
                "signal" => "traffic light at the end, then brake to a stop at the entrance",
                "stop" => "stop sign at the end, then brake to a stop at the entrance",
                _ => "brake to a stop at the end",
            };
            if scale_ramp {
                ending = "roll down to the scale and stop at the bar";
            }
            format!("{take} Half a mile of ramp; {ending}.")
        };
        let mut opts = SayEvent::new();
        opts.category = Some(SpeechCategory::Navigation);
        ctx.say_event_with(message, opts);
    }

    /// Real reaction seconds after `message` at the player's own rate.
    ///
    /// A screen-reader-owned voice reads at a rate the game cannot see, so
    /// the slowest assumption stands in for it.
    pub fn ramp_arrival_grace_for(&self, ctx: &GameContext, message: &str) -> f64 {
        let speech_rate = if ctx.settings.sapi_events && ctx.speech.event_supports_rate() {
            ctx.settings.speech_rate
        } else {
            0.0
        };
        ramp_arrival_grace_seconds(message, speech_rate)
    }

    /// How much road a loop-back puts back in front of the entrance.
    ///
    /// Sized in real seconds at the current pace, never a fixed stretch: once
    /// the terminal is behind the truck the ramp runs on the compressed clock
    /// again, and a fixed retry distance would be gone before the fresh cue
    /// could be heard -- the lesson the missed-exit and missed-gate loops both
    /// already carry. Bounded by the road it lives on: never shorter than the
    /// terminal-to-driveway stretch, never longer than the ramp itself.
    pub fn destination_terminal_retry_mi(&self) -> f64 {
        let speed = self.trip.truck.speed_mph().max(self.armed_ramp_mph(None));
        let miles = EXIT_WARNING_REAL_S * speed * self.trip.effective_time_scale() / 3600.0;
        RAMP_ACCESS_MI.max(miles.min(RAMP_LENGTH_MI))
    }

    /// Blown the destination terminal at speed: the scripted loop-back.
    ///
    /// The fourth instance of a pattern the blown ramp POI, the missed
    /// destination exit, and the missed facility gate already share, and the
    /// one place it was missing. Only the no-chain terminal reaches here: a
    /// facility with a street chain hands off at legal speed and never blows.
    ///
    /// The turnaround comes back to the facility, not back up the ramp, so
    /// the light or sign the driver already honored is not re-run -- only the
    /// entrance is ahead again. The clock keeps running through every loop;
    /// the lost time is the consequence, never a fine.
    pub fn loop_back_to_destination_terminal(
        &mut self,
        ctx: &mut GameContext,
        stop: &ff_core::sim::trip_models::RoadStop,
    ) {
        self.ramp_terminal_miss_count += 1;
        self.trip.game_minutes += RAMP_TERMINAL_MISS_LOOP_MIN;
        self.ramp_mi = Some(self.destination_terminal_retry_mi());
        // The say-once latch must never swallow the reposition: when the
        // missed-exit loop let it, a second miss stranded the trip with
        // nothing left to aim at. The arrival line speaks fresh instead.
        self.ramp_end_said = false;
        self.ramp_arrival_grace_s = 0.0;
        // Automatic speed control is what drove this miss, so the whole
        // session goes -- not just the active controller. Left armed, the
        // resume helper would wind the truck straight back up to speed on the
        // re-approach and blow the same entrance again.
        self.cancel_cruise(ctx, false);
        self.cancel_keeper(ctx, false);
        let place = stop.name.clone();
        let mut message = if self.terse_speech(ctx) {
            format!(
                "Drove past {place}; you never stopped. Safe turnaround. {place} ahead again; \
                 stop this time."
            )
        } else {
            format!(
                "You drove past {place} without stopping. You continue to the next safe \
                 turnaround and loop back onto the approach. {place} is ahead again; slow to a \
                 stop this time. The clock is still running."
            )
        };
        if self.ramp_terminal_miss_count >= 2 {
            // The identical core line keeps the flow predictable by ear; a
            // repeat miss earns help, not scolding.
            message.push_str(&format!(
                " Brake with {} well before it.",
                ctx.control_hint("brake")
            ));
        }
        ctx.audio.play("ui/warning");
        self.set_status(format!("Drove past {place}. Use the next safe turnaround."));
        // The mandatory destination terminal, not an optional stop: names the
        // loop-back maneuver that still delivers the load, so it must survive
        // quiet/urgent_only as words.
        let mut opts = SayEvent::new();
        opts.category = Some(SpeechCategory::Navigation);
        ctx.say_event_with(message, opts);
    }

    /// Brake an explicitly selected optional stop at its entrance.
    pub fn update_selected_stop_assist(&mut self, ctx: &mut GameContext) -> bool {
        let Some(stop) = self.ramp_stop.clone() else {
            return false;
        };
        if !self.selected_stop_assist_armed
            || !self.is_selected_stop(Some(&stop))
            || !ctx.settings.selected_stop_assist
            || !self.ramp_terminal_done
        {
            return false;
        }
        if self.ramp_mi.is_some_and(|mi| mi <= -RAMP_OVERSHOOT_MI) {
            return false;
        }
        let gap_mi = 0.0f64.max(self.ramp_mi.unwrap_or(0.0));
        let speed = self.trip.truck.speed_mph();
        if speed <= DOCKING_MAX_MPH && gap_mi <= 0.08 {
            self.trip.truck.throttle = 0.0;
            self.trip.truck.brake = 1.0;
            self.trip.truck.set_parking_brake();
            self.ramp_mi = None;
            self.ramp_stop = None;
            self.ramp_control = String::new();
            self.exit_signal_on = false;
            self.cruise_exit_mph = None;
            self.reset_exit_lane_state();
            self.open_poi_stop(ctx, &stop, true, None);
            return true;
        }
        if speed <= DOCKING_MAX_MPH {
            // Stopped short of the entrance: never trap the driver in a brake
            // hold. The ramp guidance tells them to pull ahead.
            self.trip.truck.brake = 0.0;
            return false;
        }
        let gap_m = 0.5f64.max(gap_mi * 1609.344);
        let v_mps = 0.0f64.max(self.trip.truck.velocity_mps);
        let needed = (v_mps * v_mps) / (2.0 * gap_m);
        if self.selected_stop_assist_brake <= 0.0
            && needed < RAMP_ASSIST_DECEL_START_MPS2
            && gap_mi > 0.08
        {
            return false;
        }
        self.trip.truck.throttle = 0.0;
        self.selected_stop_assist_brake =
            assist_servo_brake(self.selected_stop_assist_brake, needed, &self.trip.truck);
        self.trip.truck.brake = self.trip.truck.brake.max(self.selected_stop_assist_brake);
        if !self.selected_stop_assist_said {
            self.selected_stop_assist_said = true;
            self.pause_speed_control(ctx, false);
            // ROUTE, not the ambient default: an automation naming that it just
            // took the brakes, same class as the ramp assist's own braking-for
            // line (automation-handoff sweep, 2026-08-20, the deferred
            // 2026-08-15 audit).
            self.say_route_confirmation(
                ctx,
                &format!(
                    "Planned rest-stop stopping assistance braking for the entrance to {}.",
                    stop.spoken_name()
                ),
            );
        }
        false
    }

    /// One interrupting CONFIRMATION line at the default priority.
    fn say_confirmation_event(&self, ctx: &mut GameContext, message: &str) {
        let mut opts = SayEvent::new();
        opts.category = Some(SpeechCategory::Confirmation);
        ctx.say_event_with(message.to_string(), opts);
    }
}
