//! The mirror check a blind driver cannot make: when the lane you left is
//! open again (port of `freight_fate/states/driving_lane_gap.py`, the
//! `LaneGapMixin`).
//!
//! Passing is a two-part manoeuvre and the game only ever spoke the first
//! part. Moving over says "Changing to the left lane" and arriving says "In
//! the left lane", and from there the driver is on their own: the vehicle they
//! are passing makes no sound once it is beside the cab, and nothing says when
//! it is behind them. A sighted player glances at the mirror. A blind player
//! was left guessing, and guessing wrong is a sideswipe -- the collision
//! message even tells them to check mirrors they have no way to check (tester
//! Darren Duff, 1.9.0.dev0: "Not sure how you are supposed to know once you
//! are past vehicles and it's safe to switch lanes again").
//!
//! So the pass gets its closing half: one line, when the lane behind the
//! manoeuvre is genuinely open again.
//!
//! * **The same authority that judges the collision.** `_finish_lane_change`
//!   asks the traffic manager whether the lane it arrived in is occupied. This
//!   asks the same question of the lane the driver came from, through the same
//!   `vehicle_in_lane` call, over a window a margin WIDER than the collision
//!   test uses -- and swept forward over the real seconds a driver spends
//!   acting on the answer. A static margin was not enough: traffic moves on
//!   compressed game time, so at highway compression a cruise closing on
//!   slowed traffic ate half a mile between "Right lane open" and the drift
//!   landing, and the lane the cue had honestly called open sideswiped anyway
//!   (tester Jerry Jicha, 1.9.0.dev0: "if it says it is open, then it is
//!   open"). Open now means open until the driver is across.
//! * **Once per vehicle passed.** Latched on the vehicle's key, like the
//!   pass-by whoosh. A car riding the edge of the window must not chant.
//! * **Only while it is still true.** Back in that lane, out of it by a fresh
//!   change, stopped, or the road took the lane away, and the watch is dropped
//!   without a word. A closed lane is never called open.
//!
//! The same clearance reading answers the L key on demand, so a driver who
//! missed the line -- or who wants to know before committing -- can ask.

use ff_core::sim::traffic_manager::TrafficVehicle;
use ff_core::speech_pacing::SpeechCategory;

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

/// How much wider than the sideswipe test this cue looks. Positional slack for
/// what the look-ahead below cannot see -- a vehicle braking harder inside the
/// horizon than its current speed says. Every mile of it makes the cue
/// quieter, never more permissive.
pub const LANE_GAP_MARGIN_MI: f64 = 0.12;
/// The real seconds between hearing "open" and the truck being across: the
/// line finishing, the reach for the wheel, and the timed drift over the
/// painted line. The clearance read is swept this far forward through the
/// traffic's own motion -- converted to game time through the trip's effective
/// scale, because that is the clock the traffic actually moves on. Jerry's
/// collisions ran readout-to-contact in about four and a half real seconds.
pub const LANE_GAP_ACT_REAL_S: f64 = 6.0;
/// Real seconds between two of these lines. A queue of vehicles clearing one
/// after another is a real sequence of facts, but read out back to back it is
/// a chant over the top of whatever else the road is saying.
pub const LANE_GAP_CUE_MIN_GAP_S: f64 = 4.0;

impl DrivingState {
    pub fn reset_lane_gap(&mut self) {
        // The lane a completed change moved out of, and the vehicle that was
        // holding it. Per-stint, not saved: a reloaded trip is not mid-pass.
        self.lane_gap_watch = None;
        self.lane_gap_prev_lane = Some(self.lane.lane);
        self.lane_gap_blocker_key = None;
        self.lane_gap_blocker_class = String::new();
        self.lane_gap_said_keys.clear();
        self.lane_gap_cue_s = 0.0;
    }

    // -- clearance, read through the collision logic's own authority ----------

    /// The vehicle holding `lane_index` beside the truck, or None.
    ///
    /// The window is the sideswipe test's, widened by `LANE_GAP_MARGIN_MI` at
    /// both ends and swept `LANE_GAP_ACT_REAL_S` real seconds forward through
    /// the traffic's relative motion: whatever this call misses, the collision
    /// check misses too, so "open" can never be the more optimistic of the two
    /// answers -- not now, and not by the time the driver acting on it arrives
    /// in the lane.
    pub fn lane_gap_blocker(&self, lane_index: i64) -> Option<TrafficVehicle> {
        self.trip
            .traffic_manager
            .vehicle_in_lane(
                self.trip.position_mi,
                lane_index,
                DODGE_CLEARANCE_AHEAD_MI + LANE_GAP_MARGIN_MI,
                DODGE_CLEARANCE_BEHIND_MI + LANE_GAP_MARGIN_MI,
                LANE_GAP_ACT_REAL_S * self.trip.effective_time_scale() / 3600.0,
                self.trip.truck.speed_mph(),
            )
            .cloned()
    }

    /// Whether roadwork has this lane coned off where the truck is.
    pub fn lane_gap_closed_by_zone(&mut self, lane_index: i64) -> bool {
        let zone = self.trip.active_zone();
        zone.is_some_and(|zone| {
            zone.reason == "construction" && zone.closed_lane == Some(lane_index)
        })
    }

    /// Whether moving into `lane_index` right now is clear of traffic.
    pub fn lane_gap_open(&self, lane_index: i64) -> bool {
        self.lane_gap_blocker(lane_index).is_none()
    }

    // -- the spoken cue -------------------------------------------------------

    pub fn arm_lane_gap_watch(&mut self, lane_index: i64) {
        self.lane_gap_watch = Some(lane_index);
        self.lane_gap_blocker_key = None;
        self.lane_gap_blocker_class = String::new();
        // A fresh manoeuvre is owed a fresh answer, even about a vehicle an
        // earlier one already called: the driver is passing it again.
        self.lane_gap_said_keys.clear();
    }

    pub fn drop_lane_gap_watch(&mut self) {
        self.lane_gap_watch = None;
        self.lane_gap_blocker_key = None;
        self.lane_gap_blocker_class = String::new();
        self.lane_gap_said_keys.clear();
    }

    /// Watch the lane the truck moved out of, and say when it is open.
    pub fn update_lane_gap(&mut self, ctx: &mut GameContext, dt: f64) {
        let current = self.lane.lane;
        let previous = self.lane_gap_prev_lane;
        self.lane_gap_prev_lane = Some(current);
        self.lane_gap_cue_s = (self.lane_gap_cue_s - dt).max(0.0);
        if let Some(previous) = previous {
            if previous != current {
                // The truck just changed lanes: the lane it left is the way back.
                self.arm_lane_gap_watch(previous);
            }
        }
        let Some(watch) = self.lane_gap_watch else {
            return;
        };
        if watch == current || watch >= self.lane.lane_count || watch < 0 {
            // Already back in it, or the road no longer has it.
            self.drop_lane_gap_watch();
            return;
        }
        if self.lane_gap_closed_by_zone(watch) {
            // Never call a coned-off lane open. The merge warning owns this
            // stretch of road and it is telling the driver the opposite.
            self.drop_lane_gap_watch();
            return;
        }
        if self.trip.truck.speed_mph() <= LANE_MIN_MPH {
            return; // nothing is being passed at a crawl; keep watching
        }
        if self.lane_change_target.is_some() {
            return; // a change is already underway, in some direction
        }
        if let Some(blocker) = self.lane_gap_blocker(watch) {
            self.lane_gap_blocker_key = Some(blocker.key.clone());
            self.lane_gap_blocker_class = if blocker.vehicle_class.is_empty() {
                "vehicle".to_string()
            } else {
                blocker.vehicle_class.clone()
            };
            return;
        }
        let Some(key) = self.lane_gap_blocker_key.clone() else {
            return; // nobody was ever alongside
        };
        if self.lane_gap_said_keys.contains(&key) {
            return; // this one has been called
        }
        // Marked spoken either way. A cue held back by the spacing and let out
        // later would be describing a gap that has moved on since.
        self.lane_gap_said_keys.insert(key);
        if self.lane_gap_cue_s > 0.0 {
            return;
        }
        self.lane_gap_cue_s = LANE_GAP_CUE_MIN_GAP_S;
        let name = lane_label(watch, self.lane.lane_count);
        let vehicle = if self.lane_gap_blocker_class.is_empty() {
            "vehicle".to_string()
        } else {
            self.lane_gap_blocker_class.clone()
        };
        let capitalized = capitalize(name);
        let message = if self.terse_speech(ctx) {
            format!("{capitalized} lane open.")
        } else {
            format!("Clear of the {vehicle}. {capitalized} lane open.")
        };
        ctx.audio.play_with("ui/notify", 0.45, 0.0);
        // ROUTE priority: "the lane you were boxed out of is open" is the
        // transition a driver is actively waiting on to merge back, and at
        // the ambient default it was dropped as stale behind the very
        // traffic flurry that boxed them out (Shane, 2026-08-20). Category
        // stays STATUS so the verbosity ladder still governs HOW it speaks.
        ctx.say_event_with(
            message,
            SayEvent::queued()
                .priority(EventPriority::Route)
                .category(SpeechCategory::Status),
        );
    }

    // -- the on-demand readout ------------------------------------------------

    /// The L key: where the truck sits, and whether the next lane over is
    /// open. The driver who missed the spoken line, or who wants to know
    /// before they commit, asks for the same reading it speaks from.
    pub fn lane_status_text(&mut self) -> String {
        let lane_count = self.lane.lane_count;
        let mut parts = vec![self.lane.describe()];
        for neighbour in [self.lane.lane - 1, self.lane.lane + 1] {
            if !(0..lane_count).contains(&neighbour) {
                continue;
            }
            let name = capitalize(lane_label(neighbour, lane_count));
            if self.lane_gap_closed_by_zone(neighbour) {
                parts.push(format!("{name} lane closed for construction."));
                continue;
            }
            match self.lane_gap_blocker(neighbour) {
                None => parts.push(format!("{name} lane open.")),
                Some(blocker) => {
                    let vehicle = if blocker.vehicle_class.is_empty() {
                        "vehicle".to_string()
                    } else {
                        blocker.vehicle_class.clone()
                    };
                    parts.push(format!("{name} lane blocked by a {vehicle}."));
                }
            }
        }
        parts.join(" ")
    }
}

/// Python's `str.capitalize()`: upper-case the first character, lower-case the
/// rest. The lane labels are already lower-case words, so this only lifts the
/// first letter.
fn capitalize(text: &str) -> String {
    let mut chars = text.chars();
    match chars.next() {
        None => String::new(),
        Some(first) => first.to_uppercase().collect::<String>() + &chars.as_str().to_lowercase(),
    }
}
