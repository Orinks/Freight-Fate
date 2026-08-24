//! Small route-geometry helpers shared by the trip and its former mixins
//! (port of `freight_fate/sim/trip_route_helpers.py`).

use std::f64::consts::PI;

use regex::Regex;

use crate::data::world::World;
use crate::data::world_models::Leg;
use crate::pyfmt::fmt_f;
use crate::sim::trip_models::Zone;

/// A leg-native (A-to-B) milepost as an offset in the direction of travel.
pub fn stop_offset_for_direction(at_mi: f64, leg_miles: f64, forward: bool) -> f64 {
    if forward {
        at_mi
    } else {
        leg_miles - at_mi
    }
}

/// Signed heading for onramp/merge framing ("Merge onto I-95 South...").
///
/// Uses the US route-numbering convention -- odd routes are signed
/// north/south, even routes east/west -- so the spoken direction matches
/// real signage even where a leg runs diagonally. The sign comes from the
/// endpoints' coordinates on the route's primary axis. Empty when the
/// highway has no number or a city lacks coordinates.
pub fn leg_heading(world: &World, highway: &str, from_city: &str, to_city: &str) -> &'static str {
    let digits = Regex::new(r"\d+").expect("static regex");
    let Some(m) = digits.find(highway) else {
        return "";
    };
    let (Some(a), Some(b)) = (world.cities.get(from_city), world.cities.get(to_city)) else {
        return "";
    };
    if a.lat == 0.0 && a.lon == 0.0 {
        return "";
    }
    // Python `int(match.group()) % 2`: a very long digit run still parses
    // there; here a parse failure reads as even, which no real shield hits.
    let number: u128 = m.as_str().parse().unwrap_or(0);
    if number % 2 == 1 {
        // odd -> north/south route
        return if b.lat >= a.lat { "North" } else { "South" };
    }
    if b.lon >= a.lon {
        "East"
    } else {
        "West"
    } // even -> east/west route
}

/// Signed exit label of the interchange nearest a stop on the same leg, in
/// the leg's native (a->b) frame. Empty when none is within `tol_mi` or the
/// nearest junction carries no exit number.
pub fn nearest_exit_label(leg: &Leg, at_mi: f64, tol_mi: f64) -> String {
    let mut best_label = String::new();
    let mut best_dist = tol_mi;
    for ix in leg.interchanges() {
        let dist = (ix.at_mi - at_mi).abs();
        let label = ix.exit_label();
        if dist <= best_dist && !label.is_empty() {
            best_dist = dist;
            best_label = label;
        }
    }
    best_label
}

/// Keyed by place and reason only: a congestion zone's limit_mph is the live
/// traffic speed and changes with the clock, and a re-keyed zone would
/// re-announce itself every time the jam deepened a notch.
pub fn zone_key(zone: &Zone) -> String {
    format!(
        "{}:{}:{}",
        zone.reason,
        fmt_f(zone.start_mi, 3),
        fmt_f(zone.end_mi, 3)
    )
}

/// Auditable fallback for legs without elevation samples: flat roads stay
/// level, hills and mountains get a small deterministic profile from the
/// curated terrain label.
pub fn fallback_grade(terrain: &str, mile: f64, highway: &str) -> f64 {
    let amplitude = match terrain {
        "flat" => 0.0,
        "hills" => 0.012,
        "mountain" => 0.035,
        _ => 0.0,
    };
    if amplitude == 0.0 {
        return 0.0;
    }
    let wavelength = match terrain {
        "hills" => 14.0,
        "mountain" => 8.0,
        _ => 16.0,
    };
    let code_sum: u64 = highway.chars().map(|ch| ch as u64).sum();
    let phase = (code_sum % 628) as f64 / 100.0;
    amplitude * (2.0 * PI * mile / wavelength + phase).sin()
}

/// Snap a (lat, lon) coordinate to the nearest route point on a leg,
/// returning the trip-absolute milepost, or None when the leg has no route
/// points or the coordinate is more than 2 miles from any of them (the
/// construction event is on a cross street, not the highway itself).
pub fn nearest_mile_on_leg(
    lat: f64,
    lon: f64,
    leg: &Leg,
    forward: bool,
    leg_start_mi: f64,
) -> Option<f64> {
    let points = leg.route_points();
    if points.is_empty() {
        return None;
    }
    let mut best = None;
    let mut best_dist_mi = f64::INFINITY;
    for rp in points {
        let d = haversine_distance_mi(lat, lon, rp.lat, rp.lon);
        if d < best_dist_mi {
            best_dist_mi = d;
            best = Some(rp);
        }
    }
    let best = best?;
    if best_dist_mi > 2.0 {
        return None;
    }
    let offset = stop_offset_for_direction(best.at_mi, leg.miles, forward);
    Some(leg_start_mi + offset)
}

/// Great-circle distance in miles between two coordinates.
pub fn haversine_distance_mi(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    let (lat1, lon1, lat2, lon2) = (
        lat1.to_radians(),
        lon1.to_radians(),
        lat2.to_radians(),
        lon2.to_radians(),
    );
    let dlat = lat2 - lat1;
    let dlon = lon2 - lon1;
    let a = (dlat / 2.0).sin().powi(2) + lat1.cos() * lat2.cos() * (dlon / 2.0).sin().powi(2);
    2.0 * a.sqrt().asin() * 3956.0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fallback_grade_is_level_on_flat_ground() {
        assert_eq!(fallback_grade("flat", 10.0, "I-80"), 0.0);
        assert!(fallback_grade("mountain", 3.0, "I-70").abs() <= 0.035);
    }

    #[test]
    fn haversine_known_distance() {
        // Chicago to Indianapolis is about 165 miles.
        let d = haversine_distance_mi(41.8781, -87.6298, 39.7684, -86.1581);
        assert!((160.0..170.0).contains(&d), "{d}");
    }
}
