//! TEMPORARY stubs for everything `driving_events.py` reached for on a mixin
//! that has not been ported yet (T4.4b landed first of the driving mixins).
//!
//! Each block below names the module that owns it. When that module lands its
//! real `impl DrivingState` (or its module-level functions), it DELETES its
//! block here -- a duplicate method is a compile error that points straight at
//! the pair, exactly as `states/driving.rs`'s own `pending` module works.
//!
//! Signatures are the contract: keep them when porting. Bodies do the least
//! that keeps a drive coherent (a neutral answer, a no-op) and log once per
//! process, except where the Python function is pure and short enough that the
//! faithful body IS the stub -- the `driving_speed_control` constants below
//! are exact ports, kept here only so this file's callers behave correctly
//! before their owner lands.

use std::sync::Once;

use ff_core::sim::trip_models::RoadStop;

use crate::app::GameContext;
use crate::states::driving::DrivingState;

macro_rules! pending_once {
    ($name:literal) => {{
        static ONCE: Once = Once::new();
        ONCE.call_once(|| log::warn!("driving_events: {} is a pending stub", $name));
    }};
}

// -- provided by driving_speed_control.rs (module constants) -----------------------------

pub const KEEPER_EASE_UNDERSHOOT_MPH: f64 = 1.0;
pub const KEEPER_SNUB_OVER_MPH: f64 = 1.5; // this far over the target starts a snub
pub const KEEPER_SNUB_UNDER_MPH: f64 = 1.0; // and it runs until this far back under it
pub const KEEPER_SNUB_DECEL_MPS2: f64 = 0.6;
pub const KEEPER_SNUB_MIN_BRAKE: f64 = 0.12; // a real application, not a drag
pub const KEEPER_SNUB_MAX_BRAKE: f64 = 0.6; // zone speeds never need more than this
pub const KEEPER_OVERRUN_MPH: f64 = 3.0;
pub const KEEPER_OVERRUN_S: f64 = 4.0;

// -- provided by driving_menu_states.rs / driving_rest_states.rs -------------------------
//
// The screens `driving_events.py` pushes. Each is `ctx.push_state(X::new(...))`
// (or `replace_state`) once its module lands; the stub does nothing so a drive
// keeps running headlessly.
impl DrivingState {
    /// `ctx.push_state(RestStopState(ctx, self, stop, prefer_sleep=...))`.
    pub fn push_rest_stop_state(
        &mut self,
        _ctx: &mut GameContext,
        _stop: &RoadStop,
        _prefer_sleep: bool,
    ) {
        pending_once!("push_rest_stop_state");
    }

    /// `ctx.push_state(ParkingFullState(ctx, self, stop))`.
    pub fn push_parking_full_state(&mut self, _ctx: &mut GameContext, _stop: &RoadStop) {
        pending_once!("push_parking_full_state");
    }

    /// `ctx.push_state(ShoulderSleepConfirmationState(ctx, self, reason, mi))`.
    pub fn push_shoulder_sleep_confirmation(
        &mut self,
        _ctx: &mut GameContext,
        _reason: &str,
        _anchor_mi: f64,
    ) {
        pending_once!("push_shoulder_sleep_confirmation");
    }

    /// `ctx.replace_state(ArrivalState(ctx, self))`.
    pub fn replace_with_arrival_state(&mut self, _ctx: &mut GameContext) {
        pending_once!("replace_with_arrival_state");
    }

    /// `ctx.replace_state(FacilityArrivalState(ctx, self))`.
    pub fn replace_with_facility_arrival_state(&mut self, _ctx: &mut GameContext) {
        pending_once!("replace_with_facility_arrival_state");
    }
}
