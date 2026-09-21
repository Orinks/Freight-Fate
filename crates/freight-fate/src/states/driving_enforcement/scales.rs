//! Weigh stations: whether one is open, how far out its notice reads, the
//! half-mile reminder, who owns the exit key, and the screening draw at the
//! scale house.

use ff_core::models::safety_record::{
    inspection_selection_chance, refresh_selection_score, safety_record_text,
};
use ff_core::pyrandom::PyRandom;
use ff_core::sim::enforcement_posts::{post_seed, KIND_FIXED_SCALE};
use ff_core::sim::trip_models::{RoadStop, ENFORCEMENT_WARNING_MAX_MI, SCALE_WARNING_REAL_S};
use ff_core::speech_pacing::SpeechCategory;

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;
use crate::states::driving_updates::live;

use super::{SCALE_NOTICE_SAMPLE, WEIGH_STATION_REMINDER_MI};

impl DrivingState {
    /// Whether this weigh station is open today.
    ///
    /// Settled once when the trip was built, from a named seeded draw over the
    /// stop's own key, so a reload cannot reopen a dark scale.
    pub fn scale_is_open(&self, stop: &RoadStop) -> bool {
        let key = stop.key();
        for post in &self.trip.posts {
            if post.anchor == key {
                return post.kind == KIND_FIXED_SCALE;
            }
        }
        false
    }

    /// Lead distance for the open-scale call, sized in real seconds.
    ///
    /// An open scale costs money and time, so it gets a longer lead than a
    /// heads-up does -- and the lead is derived from the actual sentence, not a
    /// constant, because enforcement lines differ a lot in length.
    pub fn scale_notice_lookahead_mi(&self, ctx: &GameContext) -> f64 {
        let speed = self.trip.truck.speed_mph().max(1.0);
        let seconds =
            SCALE_WARNING_REAL_S.max(self.pull_over_grace_seconds(ctx, SCALE_NOTICE_SAMPLE));
        let miles = seconds * speed * self.trip.effective_time_scale() / 3600.0;
        WEIGH_STATION_NOTICE_MI.max(miles.min(ENFORCEMENT_WARNING_MAX_MI))
    }

    /// The nearest open weigh station strictly ahead, or None.
    ///
    /// Returns `(stop, ahead_mi)`. A closed scale never matches -- its guards
    /// must stay inert so the silence-means-closed rule holds.
    pub fn open_scale_ahead(&self, within_mi: f64) -> Option<(RoadStop, f64)> {
        let mut best: Option<(RoadStop, f64)> = None;
        for stop in &self.trip.stops {
            if stop.stop_type != "weigh_station" {
                continue;
            }
            let ahead = stop.at_mi - self.trip.position_mi;
            if 0.0 < ahead
                && ahead <= within_mi
                && self.scale_is_open(stop)
                && best
                    .as_ref()
                    .is_none_or(|(_, best_ahead)| ahead < *best_ahead)
            {
                best = Some((stop.clone(), ahead));
            }
        }
        best
    }

    /// One short line before the bypass point, if nothing has changed.
    ///
    /// The full notice latches miles out; between it and the gore the old
    /// build said nothing at all, so a driver who mis-read the instruction
    /// crossed at speed in silence. Fires once per scale, only while the truck
    /// is still over the bypass speed with no scale exit armed.
    pub fn check_scale_reminder(
        &mut self,
        ctx: &mut GameContext,
        stop: &RoadStop,
        ahead: f64,
        key: &str,
    ) {
        if !(0.0 < ahead && ahead <= WEIGH_STATION_REMINDER_MI) {
            return;
        }
        if key != self.weigh_station_notice_key || key == self.weigh_station_reminder_key {
            return;
        }
        if self.trip.truck.speed_mph() <= WEIGH_STATION_BYPASS_MPH {
            return;
        }
        if self.exit_is_armed_for(stop) {
            return;
        }
        if self
            .weigh_station_transponder_verdict
            .get(key)
            .map(String::as_str)
            == Some("green")
        {
            // A weigh-in-motion green light already told this driver they
            // need no exit for this scale. "Signal for the scale exit" would
            // contradict that, so the reminder stays silent rather than
            // reintroducing an instruction the verdict just retired.
            return;
        }
        self.weigh_station_reminder_key = key.to_string();
        // The distance was hard-coded to the threshold, so a reminder that
        // fired at two hundred yards still announced "half a mile" -- and
        // after the approach line above was fixed to speak a real short
        // distance, the pair read as the scale moving further away while the
        // truck closed on it (gate harness, 2026-08-15). Speak the road that
        // is actually left.
        // valid: an instruction to signal for an exit dies the moment the
        // exit is behind the truck. Without this, a rescue after a chain of
        // failure-to-stop warnings replayed "Signal for the scale exit" when
        // there was no exit left to take (21 August build note).
        //
        // Rust: `valid` outlives the borrow of `self`, so it reads the drive
        // through `live`, exactly as the red-light line beside it does. It
        // used to project the road left onto the wall clock instead, which
        // answered "still ahead" for a truck that had sped up past the gore
        // (and for the whole of any run the wall clock outpaces) -- the
        // adversarial battery heard the reminder replayed after the bypass
        // charge had already been written.
        let scale_mi = stop.at_mi;
        let text = format!(
            "Weigh station in {}. Signal for the scale exit.",
            ctx.settings.short_distance_text(ahead)
        );
        self.refresh_live_facts();
        ctx.say_event_with(
            text,
            SayEvent::queued()
                .priority(EventPriority::Route)
                .category(SpeechCategory::Navigation)
                .valid(move || live::position_mi() < scale_mi),
        );
    }

    /// An open scale ahead owns the next exit; rest planning waits.
    ///
    /// The old announcement told the driver to press the rest key, and the
    /// rest key at speed planned a sleep stop PAST the scale -- two
    /// instructions marching the player into a bypass charge. Says what comes
    /// first and changes nothing; repeats dedupe in the pacer.
    pub fn scale_outranks_rest_planning(&mut self, ctx: &mut GameContext) -> bool {
        if self.enforcement_bypassed(ctx) || self.ramp_mi.is_some() {
            return false;
        }
        let window = self
            .scale_notice_lookahead_mi(ctx)
            .max(self.exit_window_mi());
        let Some((stop, ahead)) = self.open_scale_ahead(window) else {
            return false;
        };
        let distance = ctx.settings.distance_text(ahead, true);
        let text = format!(
            "Weigh station first, {}, {distance} ahead. All trucks must stop. Signal for the \
             scale exit with {}. Rest planning waits until you are past the scale.",
            stop.name,
            ctx.control_hint("take_exit")
        );
        ctx.say_event_with(
            text,
            SayEvent::queued()
                .priority(EventPriority::Route)
                .category(SpeechCategory::Navigation),
        );
        true
    }

    /// The open scale that outranks `stop` for the exit key, or None.
    ///
    /// An exit press with an open scale nearer than the chosen stop belongs to
    /// the scale: arming the farther ramp is exactly the move that carried a
    /// tester past the inspection lane unarmed.
    pub fn scale_claiming_exit(
        &mut self,
        ctx: &mut GameContext,
        stop: Option<&RoadStop>,
    ) -> Option<RoadStop> {
        if self.enforcement_bypassed(ctx) {
            return None;
        }
        let (scale, _) = self.open_scale_ahead(self.exit_window_mi())?;
        match stop {
            // nothing outranked; the normal arming handles it
            None => None,
            Some(stop) if stop.key() == scale.key() => None,
            // the chosen stop comes first anyway
            Some(stop) if stop.at_mi <= scale.at_mi => None,
            Some(_) => Some(scale),
        }
    }

    /// One demand at a time: a beginning pull-over owns the road.
    ///
    /// An exit armed for a ramp kept announcing and steering for it while the
    /// trooper stop was running, which turned one mistake into a
    /// failure-to-stop cascade. Returns True when something actually stood
    /// down; the plan itself stays on the route map.
    pub fn stand_down_exit_for_stop(&mut self, _ctx: &mut GameContext) -> bool {
        let had_exit = self.exit_signal_on || self.exit_stop.is_some();
        if !had_exit {
            return false;
        }
        let stop = self.exit_stop.take();
        self.exit_signal_on = false;
        self.exit_signal_canceled = false;
        self.cruise_exit_mph = None;
        self.destination_exit_response_s = 0.0;
        self.reset_exit_lane_state();
        if stop.is_some() && self.is_selected_stop(stop.as_ref()) {
            self.clear_selected_stop_intent();
        }
        true
    }

    // -- scale screening -----------------------------------------------------

    /// Whether an open scale sends this truck to the inspection lane.
    ///
    /// The safety record is the dial. A clean career is waved through nearly
    /// every time; a career carrying citations, out-of-service history and a
    /// damaged truck is pulled in at every open scale, which is what makes a
    /// dirty record feel relentless without the game inventing bad luck.
    pub fn scale_selects_driver(&self, ctx: &mut GameContext, stop: &RoadStop) -> bool {
        let damage_pct = self.trip.truck.damage_pct;
        let relaxed = ctx.settings.hos_mode == "relaxed";
        let Some(profile) = ctx.profile.as_mut() else {
            return false;
        };
        let score = refresh_selection_score(profile, damage_pct);
        let mut chance = inspection_selection_chance(score);
        if relaxed {
            chance *= hos::RELAXED_INSPECTION_SCALE;
        }
        let key = post_seed(
            Some(self.trip_seed),
            &format!("scale:{}", stop.key()),
            "select",
        );
        PyRandom::new_from_str(&key).random() < chance
    }

    /// The spoken safety-record line, for the driver's own status readout.
    pub fn safety_record_line(&self, ctx: &mut GameContext) -> String {
        let damage_pct = self.trip.truck.damage_pct;
        let Some(profile) = ctx.profile.as_mut() else {
            return "Safety record: clean. Inspectors have no reason to pull you in.".to_string();
        };
        let score = refresh_selection_score(profile, damage_pct);
        safety_record_text(score).to_string()
    }
}
