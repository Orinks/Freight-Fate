//! TEMPORARY stubs for everything `driving_controls.py` and
//! `driving_speed_control.py` reach for on a mixin that has not been ported
//! yet (T4.4d landed alongside the other driving mixins).
//!
//! Each block names the module that owns it. When that module lands its real
//! `impl DrivingState`, it DELETES its block here -- a duplicate method is a
//! compile error that points straight at the pair, exactly as
//! `states/driving.rs`'s and `driving_events::pending`'s own stub modules work.
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
        ONCE.call_once(|| log::warn!("driving_controls: {} is a pending stub", $name));
    }};
}

// -- provided by driving_pause_states.rs / driving_menu_states.rs ------------------------
//
// The two screens the control surface pushes. Each becomes
// `ctx.push_state(X::new(ctx, self))` once its module lands; the stub does
// nothing so a drive keeps running headlessly.
impl DrivingState {
    /// `ctx.push_state(PauseMenuState(ctx, self))`: Escape, Start, and the
    /// controller-disconnect pause.
    pub fn push_pause_menu(&mut self, _ctx: &mut GameContext) {
        pending_once!("push_pause_menu");
    }

    /// `ctx.push_state(DrivingStatusState(ctx, self))`: Tab, and the pad's
    /// modifier plus Start.
    pub fn push_driving_status(&mut self, _ctx: &mut GameContext) {
        pending_once!("push_driving_status");
    }
}
