//! The discrete control surface at the wheel (port of
//! `freight_fate/states/driving_controls.py`, the `DrivingControlsMixin`).
//!
//! Continuous controls -- throttle, brake, clutch, steering -- are polled from
//! held keys and the pad's axes by `driving_updates`. Everything here is a
//! DISCRETE press: a key or a pad button the player deliberately hit, answered
//! immediately. Every answer is spoken inside `ctx.player_asked(...)`, so a
//! readout somebody asked for may cut the line in progress even though
//! unasked-for lines queue at the wheel (see `GameContext::player_asked`).
//!
//! Submodules follow the Python file's own sections:
//!
//! * [`keys`] -- `handle_event` / `_handle_key`, the whole keyboard table,
//!   and the assist-off tap lane change.
//! * [`pad`] -- `handle_controller`, the modified (right-bumper) layer, and
//!   the disconnect that pauses the drive.
//! * [`vehicle`] -- the controls that move metal: the engine, the parking
//!   brake, the jake stalk and its stages, and the manual gearbox.
//! * [`info`] -- the road and speed keys (Space, S, D, A, G, U, F, V, I).
//! * [`clock`] -- C and the three Alt hours keys, plus the shoulder-sleep
//!   question the rest key and the pause menu both ask.
//! * [`status`] -- the Tab status screen's lines, the gear name and the
//!   air-brake sentence.
//! * [`help`] -- F1: the keyboard layout, or the pad's, following the device.
//! * [`latches`] -- `_update_pedal_latches`, called once per frame by
//!   `driving_updates` with the raw pedal inputs.
//! * [`pending`] -- TEMPORARY stubs for everything this file calls on a mixin
//!   that has not been ported yet, exactly as `driving_events::pending` works.
//!   `driving_speed_control` shares them.

pub mod clock;
pub mod help;
pub mod info;
pub mod keys;
pub mod latches;
pub mod pad;
pub mod pending;
pub mod status;
pub mod vehicle;

use crate::states::base::Key;

/// Wear meters join the status readout once they're worth planning around.
pub const WEAR_STATUS_PCT: f64 = 50.0;

/// An armed exit owns the D safe-speed answer once it is this close: past
/// here the ramp speed is the number that matters, not the mainline's.
pub const SAFE_SPEED_EXIT_MI: f64 = 2.0;
/// D looks this far ahead for a bend: about the pacenote call distance, so
/// the one number never contradicts the call you just heard.
pub const SAFE_SPEED_CURVE_MI: f64 = 0.5;

/// The most clauses the U readout may ever speak: the ramp control ahead,
/// the next imposed limit, the next stop, and the next demanding bend.
pub const UPCOMING_MAX_CLAUSES: usize = 4;

/// One fact about where the truck is, answered by Alt with a number
/// (`PLACE_KEYS`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PlaceFact {
    State,
    Road,
    Town,
    Direction,
}

/// `PLACE_KEYS`: Alt with a number speaks one fact about where the truck is
/// and stops (Tim K., 2026-08-16). Four keys in the order he asked for them,
/// keypad included so the number row is not the only way in.
pub fn place_fact(key: Key) -> Option<PlaceFact> {
    match key {
        Key::Num1 | Key::Kp1 => Some(PlaceFact::State),
        Key::Num2 | Key::Kp2 => Some(PlaceFact::Road),
        Key::Num3 | Key::Kp3 => Some(PlaceFact::Town),
        Key::Num4 | Key::Kp4 => Some(PlaceFact::Direction),
        _ => None,
    }
}
