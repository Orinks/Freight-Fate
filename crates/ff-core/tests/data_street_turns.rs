//! Surface-street turn-cue pacing and spoken road names (port of
//! `tests/test_street_turns.py`). The Trip-driven pacing cases are ignored
//! until `sim::trip` lands; `spoken_road_text` is tested inline in
//! `world_services.rs`.

mod data_support;

use data_support::world;
use ff_core::data::world_models::{Leg, Route};

/// A synthetic three-block facility street chain (same-city route).
fn street_route() -> Route {
    let city = "south_bend_in_us";
    let legs = vec![
        Leg::local(
            city,
            0.15,
            "East Navarre Street",
            "Start on East Navarre Street.",
            25.0,
        ),
        Leg::local(
            city,
            0.2,
            "North Michigan Street",
            "Turn left onto North Michigan Street.",
            25.0,
        ),
        Leg::local(
            city,
            0.5,
            "South Michigan Street",
            "Continue onto South Michigan Street.",
            30.0,
        ),
    ];
    Route::from_legs(vec![city.to_string(); legs.len() + 1], legs)
}

// -- one maneuver at a time ------------------------------------------------

#[test]
#[ignore = "needs sim::trip (Trip.update GPS_CUE events)"]
fn test_departure_tick_speaks_only_the_first_street_maneuver() {
    // Regression: a street chain used to read its whole itinerary on the
    // first tick -- start, turn, and continue cues all inside the generic
    // lookahead -- burying the maneuver that was actually next.
    let route = street_route();
    assert_eq!(route.legs.len(), 3);
    // Python: spoken = _local_turn_messages(trip.update(1 / 60)); len == 1 and
    // "East Navarre Street" in spoken[0].
}

#[test]
#[ignore = "needs sim::trip (Trip.update GPS_CUE events)"]
fn test_next_street_maneuver_waits_for_the_previous_junction() {
    let route = street_route();
    assert_eq!(
        route.legs[1].local_cue,
        "Turn left onto North Michigan Street."
    );
    // Python: at position 0.04 the turn stays quiet; at 0.16 exactly one cue
    // speaks and it is "Turn left onto North Michigan Street".
}

// -- spoken road names -------------------------------------------------------

#[test]
fn test_facility_street_chains_speak_no_ref_lists() {
    // Every turn-level facility approach in the shipped data reads clean:
    // no semicolon ref lists survive into spoken cues or road names.
    let world = world();
    let mut checked = 0;
    for (location_id, approach) in world.facility_approaches().unwrap() {
        if !approach.turn_level || approach.segments.is_empty() {
            continue;
        }
        if !approach
            .segments
            .iter()
            .any(|s| s.cue.contains(';') || s.road.contains(';'))
        {
            continue;
        }
        let city_key = location_id.split(':').next().unwrap().replace('-', "_");
        let Some(city) = world.cities.get(&city_key) else {
            continue;
        };
        let Some(location) = city.locations.iter().find(|loc| loc.id == *location_id) else {
            continue;
        };
        let route = world
            .facility_approach_route(&city_key, &location.name)
            .unwrap();
        for leg in &route.legs {
            assert!(!leg.highway.contains(';'), "{location_id} {}", leg.highway);
            assert!(
                !leg.local_cue.contains(';'),
                "{location_id} {}",
                leg.local_cue
            );
        }
        checked += 1;
        if checked >= 5 {
            break;
        }
    }
    assert!(
        checked > 0,
        "expected at least one raw ref list in source data"
    );
}
