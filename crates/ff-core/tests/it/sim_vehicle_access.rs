//! Stops a rig cannot physically enter stay out of the player's ears (port of
//! `tests/test_vehicle_access.py`).
//!
//! The map carries car-scale fuel stops a 70-foot combination vehicle has no
//! way into. Announcing one is a promise: "press X to take the exit" means the
//! stop is usable. A false stop burns driving hours and can strand a player
//! with no legal alternative, which is worse than no stop at all. So
//! `vehicle_access` gates every surface that offers or counts a stop, and it
//! is a separate axis from parking certainty -- a lot can admit a rig for fuel
//! and still have nowhere to park it.


use std::collections::HashSet;

use ff_core::data::world_constants::{
    vehicle_access_allows, DEFAULT_VEHICLE_ACCESS, VEHICLE_ACCESS_LEVELS,
};
use ff_core::data::world_models::{Route, Stop};
use ff_core::data::world_parsing::parse_stop;
use ff_core::sim::trip::{Trip, TripOptions};
use ff_core::sim::trip_models::RoadStop;
use ff_core::sim::vehicle::TruckState;
use serde_json::{json, Value};
use crate::sim_support::*;

fn strings(items: &[&str]) -> Vec<String> {
    items.iter().map(|s| s.to_string()).collect()
}

/// `tests/test_vehicle_access.py::_stop_raw`.
fn stop_raw(overrides: Value) -> Value {
    let mut raw = json!({
        "name": "Kenosha Safety Rest Area",
        "type": "public_rest_area",
        "at_mi": 30.0,
        "parking": "confirmed",
        "source": "WisDOT rest-area page",
    });
    let map = raw.as_object_mut().expect("object");
    for (key, value) in overrides.as_object().expect("object") {
        map.insert(key.clone(), value.clone());
    }
    raw
}

/// Python's sorted `VEHICLE_ACCESS_LEVELS`.
fn sorted_levels() -> Vec<&'static str> {
    let mut levels = VEHICLE_ACCESS_LEVELS.to_vec();
    levels.sort_unstable();
    levels
}

// --- parsing ----------------------------------------------------------------

#[test]
fn test_parse_stop_defaults_to_tractor_trailer() {
    // Unclassified data keeps behaving exactly as it did before the sweep.
    let stop = parse_stop(&stop_raw(json!({})), 60.0, "a", "b").unwrap();
    assert_eq!(stop.vehicle_access, "tractor_trailer");
    assert_eq!(DEFAULT_VEHICLE_ACCESS, "tractor_trailer");
}

#[test]
fn test_parse_stop_reads_every_access_level() {
    for level in sorted_levels() {
        let stop = parse_stop(&stop_raw(json!({"vehicle_access": level})), 60.0, "a", "b").unwrap();
        assert_eq!(stop.vehicle_access, level);
    }
}

#[test]
fn test_parse_stop_rejects_unknown_access() {
    let err = parse_stop(
        &stop_raw(json!({"vehicle_access": "rv_only"})),
        60.0,
        "a",
        "b",
    )
    .unwrap_err();
    assert!(err.to_string().contains("vehicle_access"), "{err}");
}

#[test]
fn test_access_is_independent_of_parking() {
    // A site may admit a rig for fuel and have nowhere to park it.
    let stop = parse_stop(
        &stop_raw(json!({"parking": "none", "vehicle_access": "tractor_trailer"})),
        60.0,
        "a",
        "b",
    )
    .unwrap();
    assert_eq!(stop.parking, "none");
    assert!(stop.accessible_to(false));
}

// --- the shared rule --------------------------------------------------------

#[test]
fn test_tractor_trailer_is_usable_by_everyone() {
    assert!(vehicle_access_allows("tractor_trailer", false));
    assert!(vehicle_access_allows("tractor_trailer", true));
}

#[test]
fn test_bobtail_only_needs_a_bobtail() {
    assert!(!vehicle_access_allows("bobtail_only", false));
    assert!(vehicle_access_allows("bobtail_only", true));
}

#[test]
fn test_none_is_never_usable() {
    // Landmark only -- no rig configuration unlocks it.
    assert!(!vehicle_access_allows("none", false));
    assert!(!vehicle_access_allows("none", true));
}

#[test]
fn test_stop_and_road_stop_agree() {
    // The world model and the runtime stop must never disagree.
    for level in sorted_levels() {
        for bobtail in [false, true] {
            let world_stop = Stop {
                name: "X".to_string(),
                at_mi: 10.0,
                vehicle_access: level.to_string(),
                ..Default::default()
            };
            let road_stop = RoadStop {
                vehicle_access: level.to_string(),
                ..RoadStop::new("X", 10.0, "travel_center")
            };
            assert_eq!(
                world_stop.accessible_to(bobtail),
                road_stop.accessible_to(bobtail),
                "{level} bobtail={bobtail}"
            );
        }
    }
}

// --- the driving surfaces ---------------------------------------------------

/// `tests/test_vehicle_access.py::_stops`.
fn stops() -> Vec<Stop> {
    vec![
        Stop {
            name: "Big Rig Plaza".to_string(),
            at_mi: 20.0,
            stop_type: "travel_center".to_string(),
            source: "note".to_string(),
            actions: strings(&["fuel", "sleep"]),
            services: strings(&["diesel"]),
            ..Default::default()
        },
        Stop {
            name: "Corner Mart".to_string(),
            at_mi: 40.0,
            stop_type: "fuel_station".to_string(),
            source: "note".to_string(),
            actions: strings(&["fuel"]),
            services: strings(&["diesel"]),
            vehicle_access: "bobtail_only".to_string(),
            ..Default::default()
        },
        Stop {
            name: "Scenic Overlook".to_string(),
            at_mi: 60.0,
            stop_type: "public_rest_area".to_string(),
            source: "note".to_string(),
            actions: strings(&["break"]),
            services: Vec::new(),
            vehicle_access: "none".to_string(),
            ..Default::default()
        },
    ]
}

/// The Chicago-Indianapolis route with the synthetic stop set on leg 0.
fn route_with_stops() -> Route {
    let cached = first_route_option(world(), "Chicago", "Indianapolis");
    let mut leg = (*cached.legs[0]).clone();
    leg.stops = stops();
    replace_leg(&cached, 0, leg)
}

fn access_trip(bobtail: bool) -> Trip {
    Trip::new(
        route_with_stops(),
        TruckState::default(),
        weather("great_lakes", 1),
        TripOptions {
            seed: Some(2),
            bobtail,
            world: Some(world()),
            ..Default::default()
        },
    )
}

fn placed_names(trip: &Trip) -> HashSet<String> {
    trip.stops.iter().map(|s| s.name.clone()).collect()
}

#[test]
fn test_pulling_a_trailer_hides_stops_a_rig_cannot_enter() {
    let names = placed_names(&access_trip(false));
    assert!(names.contains("Big Rig Plaza"));
    assert!(!names.contains("Corner Mart"));
    assert!(!names.contains("Scenic Overlook"));
}

#[test]
fn test_bobtailing_unlocks_bobtail_only_stops() {
    let names = placed_names(&access_trip(true));
    assert!(names.contains("Big Rig Plaza"));
    assert!(names.contains("Corner Mart"));
    // Landmark-only stays landmark-only even tractor-first.
    assert!(!names.contains("Scenic Overlook"));
}

#[test]
fn test_trip_defaults_to_the_cautious_read() {
    // A caller that never says lands on the trailer case, not the open one.
    let trip = Trip::new(
        route_with_stops(),
        TruckState::default(),
        weather("great_lakes", 1),
        TripOptions {
            seed: Some(2),
            world: Some(world()),
            ..Default::default()
        },
    );
    assert!(!trip.bobtail);
    assert!(!placed_names(&trip).contains("Corner Mart"));
}

#[test]
fn test_navigation_cues_hide_the_same_stops() {
    // The cue path reads legs directly -- it must not re-announce what the
    // placed stops ruled out.
    let trip = access_trip(false);
    let cue_texts = trip
        .navigation_cues
        .iter()
        .filter(|c| c.kind == "rest_stop")
        .map(|c| c.text.clone())
        .collect::<Vec<_>>()
        .join(" ");
    assert!(!cue_texts.contains("Corner Mart"), "{cue_texts}");
    assert!(!cue_texts.contains("Scenic Overlook"), "{cue_texts}");
}

#[test]
fn test_exit_arming_never_offers_an_unusable_stop() {
    // upcoming_stop backs the X-arming path and the HOS next-legal-stop line.
    let mut trip = access_trip(false);
    trip.position_mi = 35.0;
    let stop = trip.upcoming_stop(20.0);
    assert!(stop.is_none_or(|s| s.name != "Corner Mart"));
}

// --- pre-trip planning ------------------------------------------------------

#[test]
fn test_route_planning_counts_only_usable_stops() {
    let cached = first_route_option(world(), "Chicago", "Indianapolis");
    let mut leg = (*cached.legs[0]).clone();
    leg.stops = stops();
    let route = Route::from_legs(cached.cities[..2].to_vec(), vec![leg]);

    let usable: Vec<&str> = route
        .accessible_stop_details(false)
        .iter()
        .map(|s| s.name.as_str())
        .collect();
    assert_eq!(usable, ["Big Rig Plaza"]);
    // The unfiltered view still sees everything, for tooling and data review.
    assert_eq!(route.stop_details().len(), 3);

    let bobtailing: Vec<&str> = route
        .accessible_stop_details(true)
        .iter()
        .map(|s| s.name.as_str())
        .collect();
    assert_eq!(bobtailing, ["Big Rig Plaza", "Corner Mart"]);
}
