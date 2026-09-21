//! Surface-street turn-cue pacing and spoken road names (port of
//! `tests/test_street_turns.py`). The Trip-driven pacing cases are ignored
//! until `sim::trip` lands; `spoken_road_text` is tested inline in
//! `world_services.rs`.

use crate::data_support::{read_json, world};
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

fn street_trip() -> ff_core::sim::trip::Trip {
    use ff_core::sim::trip::{Trip, TripOptions};
    use ff_core::sim::vehicle::TruckState;
    use ff_core::sim::weather::WeatherSystem;

    let mut truck = TruckState::default();
    truck.transmission.automatic = true;
    truck.start_engine();
    let weather = WeatherSystem::new("great_lakes", Some(1), None, None, true);
    Trip::new(
        street_route(),
        truck,
        weather,
        TripOptions {
            seed: Some(3),
            world: Some(world()),
            ..Default::default()
        },
    )
}

fn local_turn_messages(events: &[ff_core::sim::trip_models::TripEvent]) -> Vec<String> {
    use ff_core::sim::trip_models::TripEventKind;

    events
        .iter()
        .filter(|e| {
            e.kind == TripEventKind::GpsCue
                && e.data
                    .cue
                    .as_ref()
                    .is_some_and(|cue| cue.kind == "local_turn")
        })
        .map(|e| e.text().to_string())
        .collect()
}

// -- one maneuver at a time ------------------------------------------------

#[test]
fn test_departure_tick_speaks_only_the_first_street_maneuver() {
    // Regression: a street chain used to read its whole itinerary on the
    // first tick -- start, turn, and continue cues all inside the generic
    // lookahead -- burying the maneuver that was actually next.
    let mut trip = street_trip();
    let spoken = local_turn_messages(&trip.update(1.0 / 60.0));
    assert_eq!(spoken.len(), 1, "{spoken:?}");
    assert!(spoken[0].contains("East Navarre Street"));
}

#[test]
fn test_next_street_maneuver_waits_for_the_previous_junction() {
    let mut trip = street_trip();
    trip.update(1.0 / 60.0); // announces the start cue only
                             // Still short of the first boundary: the turn stays quiet.
    trip.position_mi = 0.04;
    assert!(local_turn_messages(&trip.update(1.0 / 60.0)).is_empty());
    // Past it: the left turn becomes the nearest maneuver and speaks.
    trip.position_mi = 0.16;
    let spoken = local_turn_messages(&trip.update(1.0 / 60.0));
    assert_eq!(spoken.len(), 1, "{spoken:?}");
    assert!(spoken[0].contains("Turn left onto North Michigan Street"));
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

#[test]
fn test_no_facility_street_is_spoken_with_a_semicolon_anywhere_on_the_map() {
    // The check above builds five routes and stops, which is how 79 strings
    // with a list OUTSIDE the parentheses ("Continue onto I 70 BUS;US 6;US
    // 50.") got past it on 2026-09-17: the first five happened to be the
    // parenthetical kind. This one reads every street of every approach.
    let world = world();
    let mut lists = 0usize;
    for (location_id, approach) in world.facility_approaches().unwrap() {
        for segment in &approach.segments {
            for raw in [&segment.road, &segment.cue] {
                lists += usize::from(raw.contains(';'));
                let spoken = ff_core::data::world_services::spoken_road_text(raw);
                assert!(!spoken.contains(';'), "{location_id}: {raw} -> {spoken}");
            }
        }
    }
    assert!(lists > 0, "the source data still carries raw lists to trim");
}

#[test]
fn test_a_chain_that_begins_on_the_yards_own_road_speaks_it_as_a_service_road() {
    // Owner ruling 2026-09-17: a facility the public roads do not reach may
    // have a chain over its own `access=private` road, at the facility end
    // only. The bake marks such rows with a `yard_road` block. Driven, that
    // link is the last leg in and the first leg out, and it is spoken with
    // the canonical phrase for a nameless service way, never by the private
    // way's own name and never as "private" (docs/ontology.md).
    let w = world();
    let data = read_json("facility_approaches.json");
    let mut yard_chains = 0;
    for (facility_id, record) in data["approaches"].as_object().expect("approaches") {
        let Ok(facility) = w.facility_by_id(facility_id) else {
            continue;
        };
        let city = record["city"].as_str().expect("city").to_string();
        let name = facility.name.clone();
        let arrival = w
            .facility_approach_route(&city, &name)
            .expect("approach route");
        let departure = w
            .facility_departure_route(&city, &name)
            .expect("departure route");
        let legs: Vec<_> = arrival
            .legs
            .iter()
            .chain(departure.iter().flat_map(|route| route.legs.iter()))
            .collect();
        if record["yard_road"].is_null() {
            continue;
        }
        yard_chains += 1;
        // (Only on these rows: Hot Springs has a public street the map
        // really does call "Private Drive".)
        for leg in &legs {
            assert!(
                !leg.highway.to_lowercase().contains("private")
                    && !leg.local_cue.to_lowercase().contains("private"),
                "{facility_id}: {:?} / {:?}",
                leg.highway,
                leg.local_cue
            );
        }
        let last_in = arrival.legs.last().expect("a chain");
        assert_eq!(last_in.highway, "a service road", "{facility_id}");
        assert!(
            last_in.local_cue.ends_with("onto a service road."),
            "{facility_id}: {:?}",
            last_in.local_cue
        );
        let first_out = &departure.expect("a multi-leg chain").legs[0];
        assert_eq!(first_out.highway, "a service road", "{facility_id}");
        assert_eq!(
            first_out.local_cue, "Start on a service road.",
            "{facility_id}"
        );
    }
    // 89 after the 2026-09-17 yard-road re-route; 121 after the 2026-09-20
    // sweep, which gave the four unruled families and the six sibling types
    // their first sourced endpoints -- a yard reached only over its own road
    // is exactly the kind of site those families are.
    assert_eq!(yard_chains, 121, "the 2026-09-20 family and sibling sweep");
}
