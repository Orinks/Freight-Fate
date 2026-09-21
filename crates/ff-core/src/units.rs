//! Spoken measurement wording, shared by the settings layer and the trip sim.
//!
//! A leaf module on purpose: in the Python game `settings` and `sim.trip`
//! could not import each other (settings reaches the models package, which
//! loads the sim package), so the one pluralization rule for spoken
//! distances lives here where both can reach it.
//!
//! Port of `freight_fate/units.py`.

use crate::pyfmt::{fmt_f, round_py_int};

pub const MILES_TO_KM: f64 = 1.609344;

/// A whole-number distance with the unit pluralized for speech, so a
/// screen reader never hears "in 1 miles".
pub fn spoken_distance(value: f64, unit: &str) -> String {
    // Python's `round()` returns an int, so the spoken number never carries
    // a "-0"; round to the integer here for the same reason.
    let rounded = round_py_int(value);
    if rounded == 1 {
        format!("{rounded} {unit}")
    } else {
        format!("{rounded} {unit}s")
    }
}

/// An internal mileage as the number the player's unit setting asks for.
///
/// The sim measures everything in miles; this is the single conversion the
/// readouts go through, so a metric player never hears one screen's
/// kilometers next to another screen's raw miles.
pub fn to_distance(miles: f64, imperial: bool) -> f64 {
    if imperial {
        miles
    } else {
        miles * MILES_TO_KM
    }
}

/// The spoken name of the player's distance unit.
pub fn distance_unit(imperial: bool, plural: bool) -> &'static str {
    match (imperial, plural) {
        (true, true) => "miles",
        (true, false) => "mile",
        (false, true) => "kilometers",
        (false, false) => "kilometer",
    }
}

/// A very short distance in round feet or meters, never decimals.
///
/// The last few hundred of them before a stop bar, a gate, or a turn, where
/// every miles-based wording in the game has already bottomed out: 50-foot
/// steps down to 50 feet, 20-meter steps down to 20 meters.
pub fn spoken_feet_or_meters(miles: f64, imperial: bool) -> String {
    if imperial {
        let feet = (round_py_int(miles * 5280.0 / 50.0) * 50).max(50);
        return format!("{feet} feet");
    }
    let meters = (round_py_int(miles * MILES_TO_KM * 1000.0 / 20.0) * 20).max(20);
    format!("{meters} meters")
}

/// A one-decimal distance, for cues close enough that rounding to whole
/// units would hide the gap being announced.
pub fn spoken_gap(miles: f64, imperial: bool) -> String {
    format!(
        "{} {}",
        fmt_f(to_distance(miles, imperial), 1),
        distance_unit(imperial, true)
    )
}

/// Speed for the visual HUD, in the short written form.
pub fn hud_speed(mph: f64, imperial: bool) -> String {
    if imperial {
        format!("{} mph", fmt_f(mph, 0))
    } else {
        format!("{} km/h", fmt_f(to_distance(mph, imperial), 0))
    }
}

#[cfg(test)]
mod tests {
    //! Ported from the pure parts of `tests/test_metric_readouts.py` (the
    //! `Settings`-backed cases stay with the settings port) and the
    //! `_spoken_distance` check in `tests/test_driving_features.py`.
    use super::*;

    #[test]
    fn test_to_distance_leaves_imperial_alone_and_converts_metric() {
        assert_eq!(to_distance(100.0, true), 100.0);
        assert_eq!(to_distance(100.0, false), 100.0 * MILES_TO_KM);
    }

    #[test]
    fn test_distance_unit_names_both_settings_singular_and_plural() {
        assert_eq!(distance_unit(true, true), "miles");
        assert_eq!(distance_unit(true, false), "mile");
        assert_eq!(distance_unit(false, true), "kilometers");
        assert_eq!(distance_unit(false, false), "kilometer");
    }

    #[test]
    fn test_spoken_gap_keeps_one_decimal_in_both_units() {
        assert_eq!(spoken_gap(2.0, true), "2.0 miles");
        assert_eq!(spoken_gap(2.0, false), "3.2 kilometers");
    }

    #[test]
    fn test_hud_speed_uses_the_short_written_form() {
        assert_eq!(hud_speed(55.0, true), "55 mph");
        assert_eq!(hud_speed(55.0, false), "89 km/h");
    }

    #[test]
    fn test_spoken_distances_pluralize() {
        assert_eq!(spoken_distance(1.4, "mile"), "1 mile");
        assert_eq!(spoken_distance(0.6, "mile"), "1 mile");
        assert_eq!(spoken_distance(2.6, "kilometer"), "3 kilometers");
        assert_eq!(spoken_distance(0.2, "mile"), "0 miles");
        // Python's round() is half to even: 2.5 miles is "2 miles".
        assert_eq!(spoken_distance(2.5, "mile"), "2 miles");
    }

    #[test]
    fn test_spoken_feet_or_meters_steps_and_floors() {
        // 0.05 mi = 264 ft -> nearest 50 is 250.
        assert_eq!(spoken_feet_or_meters(0.05, true), "250 feet");
        assert_eq!(spoken_feet_or_meters(0.001, true), "50 feet");
        // 0.05 mi = 80.47 m -> nearest 20 is 80.
        assert_eq!(spoken_feet_or_meters(0.05, false), "80 meters");
        assert_eq!(spoken_feet_or_meters(0.001, false), "20 meters");
    }
}
