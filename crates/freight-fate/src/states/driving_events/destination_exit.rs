//! The destination exit: finding it on the baked interchanges, naming it, and
//! announcing it while there is still road to take it with.

use ff_core::sim::trip_models::RoadStop;
use ff_core::speech_pacing::{EventPriority, SpeechCategory};

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

impl DrivingState {
    /// `_destination_exit_stop()`.
    pub fn destination_exit_stop(&mut self, ctx: &mut GameContext) -> Option<RoadStop> {
        if self.phase != DRIVE_PHASE_DELIVERY || self.destination_exit_taken {
            return None;
        }
        if self.departure_chain {
            // Still on the origin's streets: the end of the active trip is
            // the on-ramp merge, not the delivery exit.
            return None;
        }
        let details = self.destination_exit_details(ctx, false);
        let (at_mi, exit_label) = match details {
            None => (
                0.0f64.max(self.trip.total_miles() - DESTINATION_EXIT_BEFORE_END_MI),
                String::new(),
            ),
            Some((at_mi, exit_label, _)) => (at_mi, exit_label),
        };
        if at_mi <= self.trip.position_mi + 0.05 {
            return None;
        }
        let mut stop = RoadStop::new(
            &self.destination_facility_text(ctx),
            at_mi,
            "delivery_destination",
        );
        stop.actions = vec!["deliver".to_string()];
        stop.exit_label = exit_label;
        Some(stop)
    }

    /// `_destination_exit_label()`.
    pub fn destination_exit_label(&mut self, ctx: &mut GameContext) -> String {
        self.destination_exit_details(ctx, false)
            .map(|details| details.1)
            .unwrap_or_default()
    }

    /// `_destination_exit_key(stop)`.
    pub fn destination_exit_key(stop: &RoadStop) -> String {
        format!("{:.3}:{}:{}", stop.at_mi, stop.exit_label, stop.name)
    }

    /// The interchange phrase a destination-exit stop carries.
    ///
    /// Python hung `exit_phrase` on the `RoadStop` instance; the Rust
    /// `RoadStop` has a fixed shape, so the phrase is looked back up from the
    /// same scan that produced the stop. `include_past` so an exit taken this
    /// frame still names itself.
    pub fn exit_phrase_of(&mut self, ctx: &mut GameContext, stop: &RoadStop) -> String {
        if stop.stop_type != "delivery_destination" {
            return String::new();
        }
        match self.destination_exit_details(ctx, true) {
            Some((at_mi, _, phrase)) if (at_mi - stop.at_mi).abs() <= 0.001 => phrase,
            _ => String::new(),
        }
    }

    /// `_destination_exit_phrase(stop)`.
    pub fn destination_exit_phrase(&mut self, ctx: &mut GameContext, stop: &RoadStop) -> String {
        let phrase = self.exit_phrase_of(ctx, stop);
        if !phrase.is_empty() {
            return phrase;
        }
        if !stop.exit_label.is_empty() {
            return format!("{} for {}", stop.exit_label, stop.name);
        }
        format!("the exit for {}", stop.name)
    }

    /// `_missed_exit_phrase(stop)`.
    pub fn missed_exit_phrase(&mut self, ctx: &mut GameContext, stop: &RoadStop) -> String {
        if stop.stop_type == "delivery_destination" {
            // The exit phrase already carries its own label; naming both
            // would speak the same exit twice in one sentence.
            return self.destination_exit_phrase(ctx, stop);
        }
        if !stop.exit_label.is_empty() {
            return format!("{} for {}", stop.exit_label, stop.spoken_name());
        }
        format!("the exit for {}", stop.spoken_name())
    }

    /// `_destination_exit_announcement(stop, ahead)`.
    pub fn destination_exit_announcement(
        &mut self,
        ctx: &mut GameContext,
        stop: &RoadStop,
        ahead: f64,
    ) -> String {
        let phrase = self.exit_phrase_of(ctx, stop);
        let labeled = if phrase.is_empty() {
            stop.exit_label.clone()
        } else {
            phrase
        };
        // Quarter-mile steps once inside a mile: the whole-mile form rounds a
        // third of a mile to nothing, so the last call before the gore was "In
        // 0 miles, the destination exit" -- which reads as already-missed while
        // there is still road to use it (owner playtest, 2026-08-15). Whole
        // miles still answer from a mile out, because "In 5.0 miles" is worse
        // than "In 5 miles" for the calls that come early.
        let distance = if ahead < 1.0 {
            ctx.settings.short_distance_text(ahead)
        } else {
            ctx.settings.distance_text(ahead, false)
        };
        let core = if labeled.is_empty() {
            format!("In {distance}, the destination exit for {}.", stop.name)
        } else {
            format!("In {distance}, {labeled}, destination exit.")
        };
        if !ctx.settings.lane_is_automated() {
            if self.terse_speech(ctx) {
                return core;
            }
            return format!("{core} Move right for the exit lane and slow down.");
        }
        // Lane keeping takes this exit with no signal and no lane work, so
        // the one thing the driver must not have to infer is that it is
        // happening at all. Said once per run, and terse keeps it: a
        // consequence is exactly what terse verbosity holds on to.
        if self.lane_keeping_takes_exit_said {
            return if self.terse_speech(ctx) {
                core
            } else {
                format!("{core} Slow down for the ramp.")
            };
        }
        self.lane_keeping_takes_exit_said = true;
        if self.terse_speech(ctx) {
            return format!("{core} Lane keeping will take this exit.");
        }
        format!("{core} Lane keeping will take this exit. Slow down for the ramp.")
    }

    /// `_check_destination_exit()`.
    pub fn check_destination_exit(&mut self, ctx: &mut GameContext) {
        let Some(stop) = self.destination_exit_stop(ctx) else {
            return;
        };
        let ahead = stop.at_mi - self.trip.position_mi;
        if !(ahead > 0.0 && ahead <= self.exit_window_mi()) {
            return;
        }
        let key = Self::destination_exit_key(&stop);
        if key != self.destination_exit_announced_key {
            self.destination_exit_announced_key = key;
            // The exact exit stays answerable for a human reaction window even
            // if coasting or automatic braking shrinks the dynamic one.
            self.destination_exit_response_s = DESTINATION_EXIT_RESPONSE_GRACE_S;
            // Cruise stays engaged down the ramp approach, capped at the ramp
            // target, rather than handing the pedal back cold.
            let announcement = self.destination_exit_announcement(ctx, &stop, ahead);
            let cap = self.cap_cruise_for_ramp(ctx, Some(&stop));
            ctx.audio.play_with("ui/notify", 0.7, 0.0);
            // ROUTE: this line carries "lane keeping will take this exit",
            // which is the only warning the driver gets that the truck is
            // about to leave the highway without them touching anything. Left
            // at the AMBIENT default it was dropped whenever another line
            // landed in the same moment, and the exit read as taking itself --
            // reported twice now (Sarah A, 2026-08-15; and the report the
            // attribution was written for in the first place).
            let mut opts = SayEvent::queued().priority(EventPriority::Route);
            opts.category = Some(SpeechCategory::Navigation);
            ctx.say_event_with(format!("{announcement}{cap}"), opts);
        }
        if self.exit_stop.is_none() {
            self.exit_stop = Some(stop);
            self.exit_signal_canceled = false;
            self.reset_exit_lane_state();
            if ctx.settings.lane_is_automated() {
                self.exit_lane_alignment = EXIT_LANE_READY;
                self.exit_lane_ready_said = true;
            }
        }
    }

    /// `_destination_exit_details(*, include_past=False)`.
    pub fn destination_exit_details(
        &mut self,
        ctx: &GameContext,
        include_past: bool,
    ) -> Option<(f64, String, String)> {
        if include_past {
            return self.scan_destination_exit_details(ctx, true);
        }
        // This runs every frame from _check_destination_exit, and the scan
        // walks every interchange on the route building spoken phrases -- far
        // too much churn to redo per tick on a coast-to-coast route. The
        // winning exit only changes when the truck passes it, so reuse the
        // last answer until then. A backward position move (missed-exit
        // rewind, rescue) invalidates the cache wholesale, because exits
        // behind the compute position come back into play.
        let pos = self.trip.position_mi;
        let stale = match self.destination_exit_cache.as_ref() {
            None => true,
            Some((at, found)) => {
                pos < *at || found.as_ref().is_some_and(|found| found.0 <= pos + 0.05)
            }
        };
        if stale {
            let found = self.scan_destination_exit_details(ctx, false);
            self.destination_exit_cache = Some((pos, found));
        }
        self.destination_exit_cache
            .as_ref()
            .and_then(|(_, found)| found.clone())
    }

    /// `_scan_destination_exit_details(*, include_past=False)`.
    pub fn scan_destination_exit_details(
        &self,
        ctx: &GameContext,
        include_past: bool,
    ) -> Option<(f64, String, String)> {
        if self.route.legs.is_empty() {
            return None;
        }
        // Matched against real interchange sign text, so compare the spoken
        // city name ("Nashville"), never the slug key.
        let destination = ctx
            .world
            .spoken_city(
                self.route.cities.last().map(String::as_str).unwrap_or(""),
                Some(false),
            )
            .to_lowercase();
        let scan_floor = self.trip.total_miles() - DESTINATION_EXIT_SCAN_WINDOW_MI;
        // (legs from the end, distance from the leg's destination end, whether
        // the sign does NOT name the destination, route mile, label, phrase)
        let mut candidates: Vec<(usize, f64, bool, f64, String, String)> = Vec::new();
        for i in (0..self.route.legs.len()).rev() {
            let leg = &self.route.legs[i];
            if self.trip.leg_starts[i] + leg.miles < scan_floor {
                // This leg ends before the final approach; every earlier leg
                // is farther out still.
                break;
            }
            let forward = self.route.cities.get(i).map(String::as_str) == Some(leg.a.as_str());
            let target = if forward { leg.miles } else { 0.0 };
            for ix in leg.interchanges() {
                let exit_label = ix.exit_label();
                if exit_label.is_empty() {
                    continue;
                }
                let offset = if forward {
                    ix.at_mi
                } else {
                    leg.miles - ix.at_mi
                };
                let route_mile = self.trip.leg_starts[i] + offset;
                if route_mile < scan_floor {
                    continue;
                }
                if !include_past && route_mile <= self.trip.position_mi + 0.05 {
                    continue;
                }
                let dist_from_destination = (ix.at_mi - target).abs();
                let matches_destination = ix
                    .destinations
                    .iter()
                    .any(|part| part.to_lowercase().contains(&destination));
                candidates.push((
                    self.route.legs.len() - 1 - i,
                    dist_from_destination,
                    !matches_destination,
                    route_mile,
                    exit_label,
                    ix.spoken_phrase(),
                ));
            }
        }
        if candidates.is_empty() {
            return None;
        }
        candidates.sort_by(|a, b| {
            a.0.cmp(&b.0)
                .then(a.1.total_cmp(&b.1))
                .then(a.2.cmp(&b.2))
                .then(a.3.total_cmp(&b.3))
                .then(a.4.cmp(&b.4))
                .then(a.5.cmp(&b.5))
        });
        let winner = &candidates[0];
        Some((winner.3, winner.4.clone(), winner.5.clone()))
    }
}
