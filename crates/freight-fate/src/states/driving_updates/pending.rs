//! TEMPORARY stubs for everything `driving_updates.py` reached for on a mixin
//! that has not been ported yet.
//!
//! Each block below names the module that owns it. When that module lands its
//! real `impl DrivingState` (or its module-level functions), it DELETES its
//! block here -- a duplicate method is a compile error that points straight at
//! the pair, exactly as `states/driving.rs`'s own `pending` module and
//! `driving_events/pending.rs` work.
//!
//! Signatures are the contract: keep them when porting. Bodies do the least
//! that keeps a drive coherent (a neutral answer, a no-op) and log once per
//! process.

use std::sync::Once;

use crate::app::GameContext;
use crate::states::driving::DrivingState;

macro_rules! pending_once {
    ($name:literal) => {{
        static ONCE: Once = Once::new();
        ONCE.call_once(|| log::warn!("driving_updates: {} is a pending stub", $name));
    }};
}

// -- provided by driving_rest_states.rs --------------------------------------------------
//
// The roadside screens a resolved stop pushes, and the two record-keeping
// helpers `driving_rest_states` exports as module functions.
impl DrivingState {
    /// `_log_enforcement(ctx, self, fine=..., serious=..., major=...)`: book a
    /// spoken roadside enforcement event onto the career record; the spoken
    /// ladder line, or "".
    pub fn log_enforcement(
        &mut self,
        _ctx: &mut GameContext,
        _fine: f64,
        _serious: bool,
        _major: bool,
    ) -> String {
        pending_once!("log_enforcement");
        String::new()
    }

    /// `_log_fatigue_event(ctx, self)`: book running off the road asleep, and
    /// say what it just cost.
    pub fn log_fatigue_event(&mut self, _ctx: &mut GameContext) -> String {
        pending_once!("log_fatigue_event");
        String::new()
    }

    /// `ctx.push_state(TrafficStopState(...))`.
    #[allow(clippy::too_many_arguments)]
    pub fn push_traffic_stop_state(
        &mut self,
        _ctx: &mut GameContext,
        _signaled: bool,
        _over: f64,
        _limit: f64,
        _clean_stop: bool,
        _warned: bool,
        _construction_zone: bool,
    ) {
        pending_once!("push_traffic_stop_state");
    }

    /// `ctx.push_state(EnforcementStopState(...))`.
    pub fn push_enforcement_stop_state(
        &mut self,
        _ctx: &mut GameContext,
        _stop: EnforcementStopParams,
    ) {
        pending_once!("push_enforcement_stop_state");
    }

    /// `ctx.push_state(FelonyStopState(ctx, self))`.
    pub fn push_felony_stop_state(&mut self, _ctx: &mut GameContext) {
        pending_once!("push_felony_stop_state");
    }
}

/// The keyword arguments of `EnforcementStopState`, which the two callers in
/// `driving_updates` fill in differently.
pub struct EnforcementStopParams {
    pub title: String,
    pub summary: String,
    pub fine: f64,
    pub reputation_hit: f64,
    pub signaled: bool,
    pub return_message: String,
    pub out_of_service: bool,
    pub warned: bool,
    pub construction_zone: bool,
    pub inspection_on_stop: bool,
}
