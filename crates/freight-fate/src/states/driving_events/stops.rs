//! The rest key (`T`): planning a sleep stop, the selected-stop intent, and
//! opening a route point's own menu.

use ff_core::sim::hos;
use ff_core::sim::trip_models::RoadStop;
use ff_core::speech_pacing::SpeechCategory;

use crate::app::{GameContext, Say};
use crate::states::base::TimedMessageState;
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

use super::with_drive;

impl DrivingState {
    /// `_try_rest_stop()`: the rest key, wherever the truck happens to be.
    pub fn try_rest_stop(&mut self, ctx: &mut GameContext) {
        let rest_hint = ctx.control_hint("rest");
        let exit_hint = ctx.control_hint("take_exit");
        let status_hint = ctx.control_hint("status_menu");
        if self.pull_over.is_some() {
            self.set_status("Rest-stop planning unavailable during a police stop.");
            self.say_plain(
                ctx,
                format!(
                    "Resolve the police stop before planning a rest stop. Press {exit_hint} to \
                     signal the trooper stop."
                ),
            );
            return;
        }
        // An open scale ahead is not optional, so the rest key must not plan
        // a sleep stop past it -- the scale comes first, then the plan.
        if self.trip.truck.speed_mph() > DOCKING_MAX_MPH && self.scale_outranks_rest_planning(ctx) {
            return;
        }
        // ...and the scale's own RAMP claims the key too, at any speed. The
        // guard above only fires while the scale is still AHEAD, and a truck
        // on the ramp is already past its mile: the rest key fell straight
        // through to sleep planning and answered "the scale is behind you,
        // plan the next sleep-capable stop" to a driver doing exactly what
        // the scale had just told them to do -- press this key at the scale
        // (owner playtest, 2026-08-21). Jerry's 2026-08-12 report was the
        // same confusion one step earlier, before the ramp; that fix guarded
        // the approach and left the ramp itself open.
        // Stopped ON the scale falls through on purpose: the check-in below
        // is what the key means there.
        let on_scale_ramp = self
            .ramp_stop
            .as_ref()
            .is_some_and(|ramp| ramp.stop_type == "weigh_station");
        if on_scale_ramp && self.trip.truck.speed_mph() > DOCKING_MAX_MPH {
            let name = self
                .ramp_stop
                .as_ref()
                .expect("checked above")
                .spoken_name();
            self.say_plain(
                ctx,
                format!(
                    "On the ramp for {name}. Come to a full stop at the scale, then press \
                     {rest_hint} to check in."
                ),
            );
            return;
        }
        let stop = self.trip.nearest_stop_within(1.5).cloned();
        if self.trip.truck.speed_mph() <= DOCKING_MAX_MPH {
            let Some(stop) = stop else {
                if !secure_truck_for_stopped_menu(self, ctx) {
                    self.say_plain(ctx, "Come to a complete stop first.");
                    return;
                }
                let Some(reason) = self.emergency_shoulder_sleep_reason(ctx) else {
                    self.say_plain(
                        ctx,
                        "Emergency shoulder sleep is not available here. Use a route stop for \
                         normal breaks and sleep.",
                    );
                    return;
                };
                let anchor_mi = self.trip.position_mi;
                self.push_shoulder_sleep_confirmation(ctx, &reason, anchor_mi);
                return;
            };
            self.open_poi_stop(ctx, &stop, false, None);
            return;
        }

        if let Some(active) = self.ramp_stop.clone() {
            if self.is_selected_stop(Some(&active)) {
                let assist = if self.selected_stop_assist_armed && ctx.settings.selected_stop_assist
                {
                    "assistance is armed and will stop at the entrance after the ramp control is \
                     clear"
                } else {
                    "assistance is off; brake to a complete stop at the entrance"
                };
                let message = format!(
                    "On the selected ramp for {}; {assist}.",
                    active.spoken_name()
                );
                self.set_status(message.clone());
                // The cab confirming a control the player just worked. At the
                // quiet rung this becomes its earcon: you know you pressed K.
                ctx.say_with(message, Say::new().category(SpeechCategory::Confirmation));
                return;
            }
        }

        if let Some(selected) = self.selected_sleep_stop() {
            let ahead = selected.at_mi - self.trip.position_mi;
            if ahead <= 0.0 {
                self.say_plain(
                    ctx,
                    format!(
                        "{} is behind you. Assistance is off. Continue safely and plan the next \
                         sleep-capable stop with {rest_hint}. If you are already safely stopped \
                         at this route point, press {rest_hint} to open its menu.",
                        selected.spoken_name()
                    ),
                );
                return;
            }
            self.speak_selected_sleep_stop(ctx, &selected, true);
            return;
        }

        if let Some(stop) = stop.as_ref() {
            if stop.at_mi <= self.trip.position_mi {
                self.say_plain(
                    ctx,
                    format!(
                        "{} is behind you. Continue safely and plan the next sleep-capable stop \
                         with {rest_hint}. If you are already safely stopped at this route point, \
                         press {rest_hint} to open its menu.",
                        stop.spoken_name()
                    ),
                );
                return;
            }
        }

        if let Some(active) = self.exit_stop.clone() {
            if self.exit_signal_on {
                self.set_status(format!("Exit signal active for {}.", active.spoken_name()));
                self.say_plain(
                    ctx,
                    format!(
                        "The exit for {} is already selected. Press {exit_hint} to cancel it \
                         before planning a different sleep stop.",
                        active.spoken_name()
                    ),
                );
                return;
            }
        }

        // The NEXT sleep-capable stop ahead, however far. This used to look
        // only as far as the exit window -- the five-odd miles inside which an
        // exit can be SIGNALLED -- so T seven miles short of a rest area
        // answered "no sleep-capable route stop is close enough ahead to
        // plan", and worked a minute later with nothing changed but the
        // odometer (owner, Hanging Lake, 2026-08-22). Planning a stop is a
        // decision about hours, not about the turn signal; where the exit
        // window matters is what the confirmation tells the driver to do
        // next, below.
        let mut candidates: Vec<RoadStop> = self
            .trip
            .stops
            .iter()
            .filter(|candidate| {
                candidate.at_mi > self.trip.position_mi
                    && candidate.actions.iter().any(|action| action == "sleep")
                    && candidate.parking != "none"
            })
            .cloned()
            .collect();
        candidates.sort_by(|a, b| a.at_mi.total_cmp(&b.at_mi));
        let Some(candidate) = candidates.first().cloned() else {
            self.set_status("No sleep-capable route stop ahead on this route.");
            self.say_plain(
                ctx,
                format!(
                    "No sleep-capable route stop is ahead on this route. Open the driving status \
                     menu with {status_hint} and review upcoming route points. If you must rest, \
                     stop safely away from a route point and use emergency shoulder sleep."
                ),
            );
            return;
        };
        if let Some(current) = self.trip.planned_stop().cloned() {
            if current.key() != candidate.key() {
                self.set_status(format!("Planned stop remains {}.", current.spoken_name()));
                self.say_plain(
                    ctx,
                    format!(
                        "Your planned stop remains {}. {} is also ahead. Open the stop details \
                         from the route map to move the plan before selecting it.",
                        current.spoken_name(),
                        candidate.spoken_name()
                    ),
                );
                return;
            }
        }
        self.trip.planned_stop_key = Some(candidate.key());
        self.selected_stop_key = Some(candidate.key());
        self.selected_stop_assist_armed = false;
        self.selected_stop_assist_said = false;
        self.speak_selected_sleep_stop(ctx, &candidate, false);
    }

    /// `_selected_sleep_stop()`.
    pub fn selected_sleep_stop(&self) -> Option<RoadStop> {
        let key = self.selected_stop_key.as_ref()?;
        self.trip
            .stops
            .iter()
            .find(|stop| &stop.key() == key)
            .cloned()
    }

    /// `_is_selected_stop(stop)`.
    pub fn is_selected_stop(&self, stop: Option<&RoadStop>) -> bool {
        match (&self.selected_stop_key, stop) {
            (Some(key), Some(stop)) => *key == stop.key(),
            _ => false,
        }
    }

    /// `_speak_selected_sleep_stop(stop, *, repeated)`.
    pub fn speak_selected_sleep_stop(
        &mut self,
        ctx: &mut GameContext,
        stop: &RoadStop,
        repeated: bool,
    ) {
        let ahead = 0.0f64.max(stop.at_mi - self.trip.position_mi);
        let distance = ctx.settings.distance_text(ahead, true);
        let exit_text = if stop.exit_label.is_empty() {
            String::new()
        } else {
            format!(" at {}", stop.exit_label)
        };
        let assist = if ctx.settings.selected_stop_assist {
            "Planned rest-stop stopping assistance is on; after you signal and set the exit lane, \
             it will stop at the entrance."
        } else {
            "Planned rest-stop stopping assistance is off; brake to a complete stop at the \
             entrance."
        };
        let prefix = if repeated {
            "Still selected"
        } else {
            "Planned sleep stop selected"
        };
        // Inside the exit window the signal is the next thing to do; beyond
        // it the exit cannot be signalled yet, and saying "press X" to a
        // driver twenty miles out asks for a press that does nothing.
        let next_step = if ahead <= self.exit_window_mi() {
            format!(
                "Press {} to signal for this exit.",
                ctx.control_hint("take_exit")
            )
        } else {
            format!(
                "You will be told when its exit comes up; press {} to signal then.",
                ctx.control_hint("take_exit")
            )
        };
        let message = format!(
            "{prefix}: {}, {distance} ahead{exit_text}. {next_step} {assist}",
            stop.spoken_name()
        );
        self.set_status(message.clone());
        self.say_plain(ctx, message);
    }

    /// `_clear_selected_stop_intent()`.
    pub fn clear_selected_stop_intent(&mut self) {
        if self.selected_stop_assist_brake > 0.0 {
            if self.trip.truck.brake <= self.selected_stop_assist_brake + 1e-6 {
                self.trip.truck.brake = 0.0;
            }
            self.selected_stop_assist_brake = 0.0;
        }
        self.selected_stop_key = None;
        self.selected_stop_assist_armed = false;
        self.selected_stop_assist_said = false;
    }

    /// `_open_poi_stop(stop, *, settle=False, prefer_sleep=None)`.
    pub fn open_poi_stop(
        &mut self,
        ctx: &mut GameContext,
        stop: &RoadStop,
        settle: bool,
        prefer_sleep: Option<bool>,
    ) {
        // Secure the truck before handing off to the stop menu: zero the
        // throttle, apply the service brake, and set the parking brake. A truck
        // that rolled in just under the docking threshold (or idled in gear)
        // would otherwise keep creeping while the driver rests -- napping while
        // the rig drifts down the freeway. Mirrors the pickup/delivery arrivals.
        if !secure_truck_for_stopped_menu(self, ctx) {
            self.say_plain(ctx, "Come to a complete stop first.");
            return;
        }
        let selected_sleep_intent = self.is_selected_stop(Some(stop));
        let prefer_sleep = prefer_sleep.unwrap_or(selected_sleep_intent);
        if selected_sleep_intent {
            self.clear_selected_stop_intent();
        }
        if self.trip.is_planned(stop) {
            // Plan fulfilled; the stop menu announces itself.
            self.trip.planned_stop_key = None;
        }

        if settle {
            // A POI stop that pulls in through this wait is a menu-driven
            // stop like a roadside inspection: the frame loop that eases
            // revs down between frames stops the instant the wait state
            // takes over, so without this the engine audio froze at
            // whatever rev the approach left it at for the whole stop.
            self.settle_engine_to_idle(ctx);
            advance_rest_clock(self, ctx, STOP_PULL_IN_MIN, None, "");
            hos_mut_of(ctx).on_duty(STOP_PULL_IN_MIN);
            let snapshot = self.snapshot(ctx);
            profile_mut_of(ctx).active_trip = Some(snapshot);
            ctx.save_profile();

            let name = stop.spoken_name();
            let stop = stop.clone();
            ctx.push_state(
                TimedMessageState::new(
                    "Pulling into stop",
                    &format!("Stopped at {name}. Brakes set; menu opening in a moment."),
                    &format!("Stopped at {name}; menu opening. Please wait."),
                    STOP_PULL_IN_WAIT_S,
                    move |ctx: &mut GameContext| {
                        ctx.pop_state();
                        with_drive(ctx, |drive, ctx| {
                            drive.open_poi_stop(ctx, &stop, false, Some(prefer_sleep));
                        });
                    },
                )
                .sound_key(Some("ui/notify")),
            );
            return;
        }

        let can_sleep = stop.actions.iter().any(|action| action == "sleep");
        if can_sleep
            && hos::parking_is_full(
                self.trip_seed,
                stop.at_mi,
                self.trip.local_hour(),
                stop.parking_spaces,
            )
        {
            self.push_parking_full_state(ctx, stop);
            return;
        }
        self.push_rest_stop_state(ctx, stop, prefer_sleep);
        ctx.award_achievement("first_rest_stop");
    }
}
