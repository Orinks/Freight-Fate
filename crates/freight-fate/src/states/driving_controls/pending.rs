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

// Nothing is pending any more: the one block that stood here -- the pause
// menu and the driving status screen -- has been deleted by the modules that
// took it over, `states/driving_pause_states.rs` and
// `states/driving_menu_states.rs`.
