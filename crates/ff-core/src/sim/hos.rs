//! Hours of service, ELD duty status, fatigue, and the day/night clock.
//!
//! Simplified FMCSA-style rules running entirely on the in-game clock (the
//! trip's `game_minutes`, never wall time): 11 hours of driving after a
//! 10-hour reset, a 14-hour duty window after coming on duty, and a
//! 30-minute break after 8 cumulative hours of driving. The break may be any
//! 30 consecutive non-driving minutes, including on-duty-not-driving work.
//!
//! The model includes 7/3 and 8/2 sleeper split credits but intentionally skips
//! 60/70-hour cycle limits for now; the save schema records explicit duty
//! statuses so those rules can be added without changing how drive, facility,
//! and POI time is classified.
//!
//! Everything here is deterministic and platform-free so the headless tests
//! can exercise the rules directly.
//!
//! Port of `freight_fate/sim/hos.py`. The shift ledger lives in `clock`,
//! the logbook in `duty_log`; the constants, fatigue model, day/night clock
//! and overnight parking rolls stay here.

mod clock;
mod duty_log;
mod pyjson;
#[cfg(test)]
mod tests;

pub use clock::{HosClock, HosEvent, HosLimit};
pub use duty_log::{DutyLog, DutySegment, DutyTotals};

use crate::pyfmt::{fmt_f, pct02, py_int, round_py_int};
use crate::pyrandom::PyRandom;

pub const HOS_MODES: [&str; 3] = ["realistic", "relaxed", "debug_off"];
pub const HOS_NON_ENFORCED_MODES: [&str; 2] = ["off", "debug_off"];
pub const DUTY_STATUSES: [&str; 4] = [
    "driving",
    "on_duty_not_driving",
    "off_duty",
    "sleeper_berth",
];
pub const RODS_WINDOW_HOURS: f64 = 8.0 * 24.0;
pub const SPLIT_SHORT_MIN: f64 = 120.0;
pub const SPLIT_SHORT_ALT_MIN: f64 = 180.0;
pub const SPLIT_LONG_MIN: f64 = 420.0;
pub const SPLIT_LONG_ALT_MIN: f64 = 480.0;
pub const HOS_HISTORY_MAX: usize = 96;
pub const HOS_SPLIT_REST_HISTORY_MAX: usize = 16;

/// minimum break that resets the 8-hour rule
pub const BREAK_MIN: f64 = 30.0;
/// a full 10-hour off-duty reset
pub const SLEEP_MIN: f64 = 600.0;

/// (drive limit, duty window, driving allowed before a 30-minute break),
/// all in game minutes.
pub const REALISTIC_LIMITS: (f64, f64, f64) = (11.0 * 60.0, 14.0 * 60.0, 8.0 * 60.0);
pub const RELAXED_LIMITS: (f64, f64, f64) = (
    REALISTIC_LIMITS.0 * 1.25,
    REALISTIC_LIMITS.1 * 1.25,
    REALISTIC_LIMITS.2 * 1.25,
);

/// `LIMITS[mode]`: the enforced limits of a mode, None for the modes that
/// enforce nothing.
pub fn limits(mode: &str) -> Option<(f64, f64, f64)> {
    match mode {
        "realistic" => Some(REALISTIC_LIMITS),
        "relaxed" => Some(RELAXED_LIMITS),
        _ => None,
    }
}

/// `mode in HOS_NON_ENFORCED_MODES`.
pub fn is_non_enforced(mode: &str) -> bool {
    HOS_NON_ENFORCED_MODES.contains(&mode)
}

/// `status in DUTY_STATUSES`.
pub fn is_duty_status(status: &str) -> bool {
    DUTY_STATUSES.contains(&status)
}

/// The spoken name of a duty status.
pub fn duty_status_label(status: &str) -> String {
    match status {
        "driving" => "driving".to_string(),
        "on_duty_not_driving" => "on duty, not driving".to_string(),
        "off_duty" => "off duty".to_string(),
        "sleeper_berth" => "sleeper berth".to_string(),
        other => other.replace('_', " "),
    }
}

// Relaxed mode keeps random road hazards rare so the player can focus on
// driver responsibility -- hours of service, fueling, repairs, fatigue --
// instead of constant emergency braking. Realistic and debug modes leave
// hazard frequency untouched.
pub const RELAXED_HAZARD_SCALE: f64 = 0.2;

/// Random road-hazard frequency multiplier for a difficulty mode.
pub fn hazard_scale(mode: &str) -> f64 {
    if mode == "relaxed" {
        RELAXED_HAZARD_SCALE
    } else {
        1.0
    }
}

pub const WARNING_THRESHOLDS_MIN: [f64; 3] = [120.0, 60.0, 30.0];

pub fn warning_is_urgent(message: &str) -> bool {
    message.starts_with("Hours of service violation:")
}

/// The Python raised `ValueError` here; the ledger methods panic with the
/// same message, since a negative or non-finite increment is a programming
/// error upstream, never player input.
fn positive_minutes(minutes: f64) -> f64 {
    if !minutes.is_finite() || minutes < 0.0 {
        panic!("HOS time increments must be finite positive minutes");
    }
    minutes
}

pub fn duration_text(hours: f64) -> String {
    let minutes = pyjson::py_max(0.0, hours * 60.0);
    if minutes < 60.0 {
        return format!("{} minutes", fmt_f(minutes, 0));
    }
    format!("{} hours", fmt_f(minutes / 60.0, 1))
}

// ---------------------------------------------------------------------------
// Fatigue
// ---------------------------------------------------------------------------

/// yawns and a spoken warning
pub const FATIGUE_DROWSY: f64 = 60.0;
/// rumble strip drift, urgent warning
pub const FATIGUE_SEVERE: f64 = 80.0;

/// Escalating fines for failed roadside inspections while over hours.
pub const HOS_FINES: [f64; 4] = [200.0, 500.0, 1000.0, 2000.0];
pub const HOS_REPUTATION_HIT: f64 = 3.0;
pub const FATIGUE_COFFEE_RELIEF: f64 = 8.0;
pub const FATIGUE_BREAK_RELIEF: f64 = 35.0;
pub const FATIGUE_SHOULDER_FLOOR: f64 = 30.0;
/// How long before a sleep/duty limit the shoulder-sleep option opens up, paired
/// with a reachability check (no stop you can legally reach before the limit).
/// A real driver starts hunting for parking a couple of hours out, not in the
/// last half hour -- 30 min left you stranded with no action available.
pub const SHOULDER_SLEEP_LIMIT_BUFFER_MIN: f64 = 120.0;
pub const SHOULDER_FINE_CHANCE: f64 = 0.15;
/// Base only: models/enforcement.citation_fine scales it for priors and zone.
pub const SHOULDER_FINE: f64 = 400.0;
pub const SHOULDER_DAMAGE_CHANCE: f64 = 0.10;
pub const SHOULDER_DAMAGE_PCT: f64 = 3.0;

/// Fatigue points per game minute of continuous driving.
///
/// About 8 daytime hours to the drowsy threshold; night driving gets
/// there in under 6.
pub fn fatigue_rate_per_min(night: bool) -> f64 {
    if night {
        0.17
    } else {
        0.115
    }
}

/// Scale factor for hazard reaction windows: 1.0 fresh, 0.6 exhausted.
pub fn reaction_window_mult(fatigue: f64) -> f64 {
    if fatigue <= FATIGUE_DROWSY {
        return 1.0;
    }
    let t = pyjson::py_min(1.0, (fatigue - FATIGUE_DROWSY) / (100.0 - FATIGUE_DROWSY));
    1.0 - 0.4 * t
}

/// Fatigue after a 30-minute break.
pub fn rest_break(fatigue: f64) -> f64 {
    pyjson::py_max(0.0, fatigue - FATIGUE_BREAK_RELIEF)
}

/// Fatigue after a short food and coffee stop.
pub fn rest_coffee_break(fatigue: f64) -> f64 {
    pyjson::py_max(0.0, fatigue - FATIGUE_COFFEE_RELIEF)
}

/// Fatigue after a proper 10-hour sleep.
pub fn rest_sleep(_fatigue: f64) -> f64 {
    0.0
}

/// Shoulder parking is poor rest: fatigue never drops below 30.
pub fn rest_shoulder(fatigue: f64) -> f64 {
    pyjson::py_min(fatigue, FATIGUE_SHOULDER_FLOOR)
}

pub fn rest_sleeper_split(fatigue: f64, minutes: f64, completed: bool) -> f64 {
    let relief = if minutes <= 180.0 { 18.0 } else { 55.0 };
    let floor = if completed { 10.0 } else { 20.0 };
    pyjson::py_max(floor, pyjson::py_max(0.0, fatigue - relief))
}

// ---------------------------------------------------------------------------
// Day/night clock
// ---------------------------------------------------------------------------

pub const DAWN_START: f64 = 5.0;
pub const DAY_START: f64 = 7.0;
pub const DUSK_START: f64 = 19.0;
pub const NIGHT_START: f64 = 21.0;

/// Python `game_hours % 24.0`: the result carries the divisor's sign.
pub fn clock_hour(game_hours: f64) -> f64 {
    game_hours.rem_euclid(24.0)
}

pub fn time_of_day(game_hours: f64) -> &'static str {
    let h = clock_hour(game_hours);
    if (DAWN_START..DAY_START).contains(&h) {
        return "dawn";
    }
    if (DAY_START..DUSK_START).contains(&h) {
        return "day";
    }
    if (DUSK_START..NIGHT_START).contains(&h) {
        return "dusk";
    }
    "night"
}

pub fn is_night(game_hours: f64) -> bool {
    time_of_day(game_hours) == "night"
}

/// Spoken 12-hour clock: '6 AM', '11:24 PM'.
pub fn clock_text(game_hours: f64) -> String {
    let h = clock_hour(game_hours);
    let mut hour = py_int(h);
    let mut minute = round_py_int((h - py_int(h) as f64) * 60.0);
    if minute == 60 {
        hour = (hour + 1) % 24;
        minute = 0;
    }
    let ampm = if hour < 12 { "AM" } else { "PM" };
    let h12 = match hour % 12 {
        0 => 12,
        rest => rest,
    };
    if minute == 0 {
        return format!("{h12} {ampm}");
    }
    format!("{h12}:{} {ampm}", pct02(minute))
}

// ---------------------------------------------------------------------------
// Overnight truck parking
// ---------------------------------------------------------------------------

/// 8 PM .. 4 AM
pub const PARKING_CRUNCH_START: f64 = 20.0;
pub const PARKING_CRUNCH_END: f64 = 4.0;

/// Chance the lot is full, rising through the evening; 0 outside 8 PM-4 AM.
///
/// `spaces` is the surveyed truck-parking capacity (FHWA Jason's Law via BTS
/// NTAD) when known: a handful of spots fills earlier than a big travel-center
/// lot. 0 (unsurveyed) keeps the flat baseline.
pub fn parking_full_probability(game_hours: f64, spaces: i64) -> f64 {
    let h = clock_hour(game_hours);
    if (PARKING_CRUNCH_END..PARKING_CRUNCH_START).contains(&h) {
        return 0.0;
    }
    let hours_past_8pm = (h - PARKING_CRUNCH_START).rem_euclid(24.0);
    let p = pyjson::py_min(0.8, 0.2 + 0.1 * hours_past_8pm);
    if spaces <= 0 {
        return p;
    }
    if spaces <= 15 {
        return pyjson::py_min(0.9, p + 0.15);
    }
    if spaces >= 100 {
        return p * 0.6;
    }
    if spaces >= 40 {
        return p * 0.85;
    }
    p
}

/// Deterministic per trip seed and stop, so saves and tests reproduce it.
pub fn parking_is_full(trip_seed: i64, stop_mi: f64, game_hours: f64, spaces: i64) -> bool {
    let p = parking_full_probability(game_hours, spaces);
    if p <= 0.0 {
        return false;
    }
    let mut rng = PyRandom::new_from_str(&format!(
        "parking:{trip_seed}:{}",
        round_py_int(stop_mi * 10.0)
    ));
    rng.random() < p
}

/// Deterministic 15 percent chance of a fine for shoulder parking.
pub fn shoulder_fine_due(trip_seed: i64, stop_mi: f64) -> bool {
    let mut rng = PyRandom::new_from_str(&format!(
        "shoulder:{trip_seed}:{}",
        round_py_int(stop_mi * 10.0)
    ));
    rng.random() < SHOULDER_FINE_CHANCE
}

/// Deterministic small chance of minor damage while sleeping on the shoulder.
pub fn shoulder_damage_due(trip_seed: i64, stop_mi: f64) -> bool {
    let mut rng = PyRandom::new_from_str(&format!(
        "shoulder-damage:{trip_seed}:{}",
        round_py_int(stop_mi * 10.0)
    ));
    rng.random() < SHOULDER_DAMAGE_CHANCE
}
