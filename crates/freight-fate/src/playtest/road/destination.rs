//! The `--find destination` finder: the off-ramp that leaves the highway for
//! the delivery, and the run-in that reaches it with the callout still ahead.
//!
//! Every other finder in [`super`] points at something mid-route. The one
//! place two reported defects lived -- the destination exit itself (issues
//! #155 and #169) -- had no finder at all, so reaching it meant taking a job
//! and driving the whole route, or guessing a mile with `--at` and hearing
//! nothing when the guess was wrong.
//!
//! The search does not re-derive which interchange is the destination exit.
//! It calls the drive's own scan
//! ([`scan_destination_exit`][crate::states::driving_events::destination_exit::scan_destination_exit]),
//! so the mile the tool promises is the mile
//! [`DrivingState::check_destination_exit`][crate::states::driving::DrivingState]
//! will announce. A second ranking here would be a second answer.

use ff_core::sim::trip::Trip;

use crate::states::driving_core::{
    DESTINATION_EXIT_BEFORE_END_MI, EXIT_WARNING_REAL_S, EXIT_WINDOW_MAX_MI, EXIT_WINDOW_MI,
};
use crate::states::driving_events::destination_exit::scan_destination_exit;

use super::{lead_for_seconds, Hit, DEFAULT_LEAD_MI, LEAD_REAL_SECONDS};

/// The delivery exit on this route: one hit, or none if the route is too
/// short to have an approach at all.
///
/// A rural approach carries no baked interchange, and the drive answers that
/// with a synthetic exit a local-approach road before the end. That is still
/// the destination exit a player takes, and still announces itself, so it is
/// offered -- ranked below a real signed one, the way a closed weigh station
/// ranks below an open one.
pub fn destination_hits(trip: &mut Trip, origin: &str, destination: &str) -> Vec<Hit> {
    let world = ff_core::data::world::get_world();
    let total = trip.total_miles();
    // `include_past` because the search reads a trip parked at mile zero and
    // the flag only excludes exits already behind the truck; passing it keeps
    // the scan honest on a short route whose exit sits near the start.
    let found = scan_destination_exit(world, trip, true);
    let (at_mi, label, signed) = match found {
        Some((at_mi, exit_label, phrase)) => {
            let named = if phrase.is_empty() {
                exit_label
            } else {
                phrase
            };
            (at_mi, format!("destination exit: {named}"), true)
        }
        None => (
            0.0f64.max(total - DESTINATION_EXIT_BEFORE_END_MI),
            "destination exit (end of route, no signed interchange)".to_string(),
            false,
        ),
    };
    if at_mi <= 0.0 {
        return Vec::new();
    }
    let (limit, _) = trip.speed_limit_at((at_mi - DEFAULT_LEAD_MI).max(0.0));
    vec![Hit {
        origin: origin.to_string(),
        destination: destination.to_string(),
        at_mi,
        total_mi: total,
        // Rank exactly like the scale finder does: the sort reads magnitude,
        // and a real signed exit is the one worth driving to.
        magnitude: if signed { 1.0 } else { 0.0 },
        run_mi: 0.0,
        limit_mph: limit,
        label,
        trip_seed: None,
        origin_location: None,
    }]
}

/// How far back the destination drive starts, in route miles.
///
/// Derived from the callout's own trigger, not picked. The first destination
/// exit call fires when the ramp is inside
/// [`DrivingState::exit_window_mi`][crate::states::driving::DrivingState] --
/// `EXIT_WARNING_REAL_S` of REAL time from callout to gore, floored at
/// `EXIT_WINDOW_MI` and capped at `EXIT_WINDOW_MAX_MI`. Starting the truck at
/// exactly that distance fires the call on the first frame, before the driver
/// has the wheel.
///
/// So: one exit window, plus the run-in every other finder gives
/// (`LEAD_REAL_SECONDS`). The driver rolls for the tool's usual twenty-five
/// real seconds, THEN hears the approach open, and has the drive's own
/// twenty-five to answer it.
pub fn destination_lead_mi(trip: &Trip, speed_mph: f64) -> f64 {
    let window = EXIT_WINDOW_MI
        .max(lead_for_seconds(trip, speed_mph, EXIT_WARNING_REAL_S).min(EXIT_WINDOW_MAX_MI));
    window + lead_for_seconds(trip, speed_mph, LEAD_REAL_SECONDS)
}
