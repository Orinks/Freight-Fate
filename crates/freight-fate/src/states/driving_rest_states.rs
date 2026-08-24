//! Everywhere a drive stops and a menu takes over: route stops and their
//! fuel island, the loyalty desk, a full lot, the emergency shoulder, and
//! the three roadside enforcement outcomes (port of
//! `freight_fate/states/driving_rest_states.py`).
//!
//! # Python's two mixins
//!
//! * `_FuelPumpMixin` -- shared by `RestStopState` and `ParkingFullState`,
//!   because a lot filling up does not lock the pumps -- is the
//!   [`fuel_pump::FuelPump`] trait: four small accessors from the screen, the
//!   label, the purchase and the save as provided methods.
//! * `_RoadsideExitMixin` -- shared by the traffic stop and the enforcement
//!   stop -- is the [`roadside::RoadsideExit`] trait, same shape: the exit
//!   row, the suspended-exit wording, and closing the run out from the
//!   shoulder.
//!
//! Neither is a "mixin" in any Rust sense: a trait with provided methods and
//! no state, which is exactly what those two classes were.

mod fuel_pump;
mod loyalty;
mod parking_full;
mod rest_stop;
mod roadside;
mod shoulder;

pub use fuel_pump::FuelPump;
pub use loyalty::LoyaltyRewardsState;
pub use parking_full::ParkingFullState;
pub use rest_stop::RestStopState;
pub use roadside::{EnforcementStopState, FelonyStopState, RoadsideExit, TrafficStopState};
pub use shoulder::ShoulderSleepConfirmationState;

use ff_core::models::enforcement;
use ff_core::pyfmt::fmt_f;
use ff_core::sim::trip_models::RoadStop;

use crate::app::GameContext;
use crate::states::driving::DrivingState;
use crate::states::driving_core::{profile_mut_of, profile_of};
use crate::states::driving_menu_states::{push_over_drive, DriveRef};
use crate::states::driving_updates::pending::EnforcementStopParams;

/// Where the career clock stands right now, mid-trip included.
pub fn record_hours(ctx: &GameContext, driving: &DrivingState) -> f64 {
    profile_of(ctx).game_hours + driving.trip.game_minutes / 60.0
}

/// What a fresh timed suspension or disqualification means, and what still
/// works while it runs.
pub fn suspension_text(ctx: &GameContext, hours: f64, verb: &str) -> String {
    let profile = profile_of(ctx);
    let left = enforcement::days_text(profile.driving_record.days_left(hours));
    format!(
        "Your CDL is {verb} for {left}. Driving jobs are off the dispatch board until it clears, \
         {}. Your money and your truck are safe; rest, repairs, the garage, and the truck dealer \
         are still open.",
        enforcement::clears_text(profile)
    )
}

/// Spoken movement on the serious-violation ladder, consequence attached.
pub fn serious_violation_text(ctx: &GameContext, count: i64, hours: f64) -> String {
    if count <= 1 {
        return "That is a serious violation on your record. One more inside three years and your \
                CDL is suspended for 60 days, and driving jobs stop until it clears."
            .to_string();
    }
    let which = enforcement::ordinal_word(count);
    format!(
        "That is your {which} serious violation in three years. {}",
        suspension_text(ctx, hours, "suspended")
    )
}

/// The major-offense outcome, said as fact with the way forward.
pub fn major_offense_text(ctx: &GameContext, kind: &str, hours: f64) -> String {
    let raw_name = profile_of(ctx).name.clone();
    let name = if raw_name.is_empty() {
        "This driver".to_string()
    } else {
        raw_name
    };
    if kind == enforcement::SUSPENSION_LIFETIME {
        return format!(
            "That is your second major offense. Under federal rules a second major offense \
             disqualifies a commercial licence for life, so this driver will not drive \
             commercially again. Nothing is taken away: {name} keeps every dollar, the truck, \
             and the whole record, and you can open this career any time to look back over it. \
             Rest, repairs, the garage, and the truck dealer still work here, and the dispatch \
             board can still be read, but there is no driving work and no date this clears. When \
             you want the road again, start a new career from the title menu. Everything you \
             learned still applies."
        );
    }
    format!(
        "Running from a police stop in a commercial vehicle is a felony, and a major offense on \
         your CDL, which is a one-year disqualification. {} One more major offense is a lifetime \
         disqualification.",
        suspension_text(ctx, hours, "disqualified")
    )
}

/// Speak a repeat count the way a person would: 'twice now', 'three times
/// now' -- never frozen at the second occurrence's wording.
pub fn times_now_text(count: i64) -> String {
    if count == 2 {
        return "twice now".to_string();
    }
    format!("{} times now", enforcement::count_word(count))
}

// -- the record-keeping the roadside screens share ---------------------------------------
//
// The two blocks `driving_updates/pending.rs` held for this module, plus the
// three screens it pushes and the two `driving_events/pending.rs` held.

impl DrivingState {
    /// Book a spoken roadside enforcement event onto the career record.
    ///
    /// Only enforcement the player actually heard reaches the record. The
    /// silent at-delivery settlement strike stays money-only, so a suspension
    /// can never materialise at a delivery summary with no warning behind it.
    pub fn log_enforcement(
        &mut self,
        ctx: &mut GameContext,
        fine: f64,
        serious: bool,
        major: bool,
    ) -> String {
        if ctx.profile.is_none() || self.enforcement_bypassed(ctx) {
            // the debug hours modes freeze the ladder as well as the stop
            return String::new();
        }
        profile_mut_of(ctx).driving_record.record_citation(fine);
        let hours = record_hours(ctx, self);
        let text = if major {
            let kind = profile_mut_of(ctx)
                .driving_record
                .record_major_offense(hours);
            major_offense_text(ctx, kind, hours)
        } else if serious {
            let count = profile_mut_of(ctx)
                .driving_record
                .record_serious_violation(hours);
            serious_violation_text(ctx, count, hours)
        } else {
            return String::new();
        };
        self.record_events.push(text.clone());
        text
    }

    /// Book running off the road asleep, and say what it just cost.
    pub fn log_fatigue_event(&mut self, ctx: &mut GameContext) -> String {
        let hours = record_hours(ctx, self);
        let hit = enforcement::FATIGUE_EVENT_REPUTATION_HIT;
        let (count, serious) = profile_mut_of(ctx)
            .driving_record
            .record_fatigue_event(hours);
        let text = if count < enforcement::FATIGUE_EVENTS_BEFORE_SERIOUS {
            format!(
                "Running off the road asleep is a preventable safety incident and it goes on \
                 your record: {} points off your reputation. Do it again and it becomes a \
                 fatigued-driving violation on your CDL.",
                fmt_f(hit, 0)
            )
        } else {
            format!(
                "That is {} that you have run off the road asleep. Driving impaired by fatigue \
                 is a federal violation, so this one counts against your licence as well as {} \
                 points off your reputation. {}",
                times_now_text(count),
                fmt_f(hit, 0),
                serious_violation_text(ctx, serious, hours)
            )
        };
        self.record_events.push(text.clone());
        text
    }

    /// `ctx.push_state(RestStopState(ctx, self, stop, prefer_sleep=...))`.
    pub fn push_rest_stop_state(
        &mut self,
        ctx: &mut GameContext,
        stop: &RoadStop,
        prefer_sleep: bool,
    ) {
        let mut state = RestStopState::new(ctx, stop.clone(), prefer_sleep);
        state.enter_over_drive(ctx, self);
        push_over_drive(ctx, state);
    }

    /// `ctx.push_state(ParkingFullState(ctx, self, stop))`.
    pub fn push_parking_full_state(&mut self, ctx: &mut GameContext, stop: &RoadStop) {
        let mut state = ParkingFullState::new(ctx, stop.clone());
        state.enter_over_drive(ctx, self);
        push_over_drive(ctx, state);
    }

    /// `ctx.push_state(ShoulderSleepConfirmationState(ctx, self, reason, mi))`.
    pub fn push_shoulder_sleep_confirmation(
        &mut self,
        ctx: &mut GameContext,
        reason: &str,
        anchor_mi: f64,
    ) {
        // Pushed from the drive's own handler, so it IS the direct-from-
        // driving case; nothing in this screen's entry reads the drive.
        let state = ShoulderSleepConfirmationState::new(
            DriveRef::active(ctx),
            reason,
            Some(anchor_mi),
            true,
        );
        ctx.push_state(state);
    }

    /// `ctx.push_state(TrafficStopState(...))`.
    #[allow(clippy::too_many_arguments)]
    pub fn push_traffic_stop_state(
        &mut self,
        ctx: &mut GameContext,
        signaled: bool,
        over: f64,
        limit: f64,
        clean_stop: bool,
        warned: bool,
        construction_zone: bool,
    ) {
        let state = TrafficStopState::new(
            ctx,
            self,
            signaled,
            over,
            limit,
            clean_stop,
            warned,
            construction_zone,
        );
        ctx.push_state(state);
    }

    /// `ctx.push_state(EnforcementStopState(...))`.
    pub fn push_enforcement_stop_state(
        &mut self,
        ctx: &mut GameContext,
        stop: EnforcementStopParams,
    ) {
        let state = EnforcementStopState::new(ctx, self, stop);
        ctx.push_state(state);
    }

    /// `ctx.push_state(FelonyStopState(ctx, self))`.
    pub fn push_felony_stop_state(&mut self, ctx: &mut GameContext) {
        let state = FelonyStopState::new(ctx, self);
        ctx.push_state(state);
    }
}
