//! A chain truck stop the map import typed as a service plaza.
//!
//! A service plaza in this game is on the highway: a toll road's own plaza,
//! entered from the mainline. A Love's or a Pilot is a travel center beside
//! an interchange, reached by an exit. The map import (an OpenStreetMap
//! amenity query) typed every `highway=services` feature a `service_plaza`,
//! and U.S. mappers draw that tag around truck-stop lots, so 1,400 of the
//! map's 1,819 service plazas carried nothing but a truck-stop chain's name.
//! A driver heard "service plaza: Love's Travel Stop" for a store on a county
//! road (roadmap, 2026-09-17).
//!
//! This screens the type at load and never edits the bake, so the rule can be
//! re-judged: the records still say `service_plaza` in the data.
//!
//! # The rule
//!
//! A record contradicts itself when its type says toll-road service plaza and
//! its name begins with a national truck-stop chain ([`TRUCK_STOP_CHAINS`]).
//! It is read as a `travel_center`, the type the chains' own locator records
//! carry. A record whose own name also says "service plaza" or "service
//! area" does not contradict itself, and stays: were a chain to hold the fuel
//! concession inside a turnpike plaza, that is how the record would read.
//!
//! "Travel Plaza" in a name does not count: it is what Flying J and Onvo
//! call their stores (7 records, none on a leg that charges a toll).
//!
//! # An independent that names itself a truck stop
//!
//! The same contradiction without a chain: the type says toll-road plaza and
//! the name says truck stop ([`TRUCK_STOP_NAME_PHRASES`]: "Flags West Truck
//! Stop", "Radford Travel Center"). It is read as a `travel_center` too, and
//! that value is also **derived** from the name. "Travel Plaza" is left out
//! on purpose, because the New York Thruway's own plazas are named that way
//! ("Clifton Springs Travel Plaza"), and so is every other word the name
//! alone cannot settle.
//!
//! Where OpenStreetMap had something to READ at the record's coordinate (a
//! toll authority as operator, HGV fuel lanes, a truck scale, nothing at
//! all), `tools/nonchain_plazas.py` corrected the data itself on 2026-09-17
//! and wrote what it read into the record's `source`. This screen is only for
//! what the name alone decides: 32 records on that day's map.
//!
//! The retyped value is **derived** (input: the record's name; rule: the one
//! above), not read. The chain list is the operator's knowledge of the
//! industry, as its own doc says.
//!
//! # What was measured
//!
//! On the map of 2026-09-17, after the twin screen ([`super::stop_twins`]):
//! 1,317 records retyped and none kept (Love's 396, Pilot 356, Flying J 212,
//! TA 137, Petro 117, Road Ranger 32, Sapp Brothers 32, ONE9 28, Stamart 3,
//! Onvo 3, Roady's 1). Every one of them is sourced to the amenity query; none
//! comes from a toll authority's plaza listing, and the 99 plazas that are on
//! the highway are separate records under their own names (Pembroke Service
//! Area, Sideling Hill Service Plaza). 29 of the retyped records sit on a leg
//! that charges a toll, and each is a store at an interchange (Petro in Gary,
//! Flying J in Emporia and Breezewood, Petro in Carlisle).
//!
//! The leg's toll status is deliberately not consulted. The corridor is the
//! lazy half of a leg and is not parsed when stops are, the router's tollway
//! flag is true for 199 legs including Phoenix to Los Angeles, and on this
//! map it would change no verdict.
//!
//! # What the type changes
//!
//! The spoken label and nothing else. Actions, assumed parking, vehicle
//! access, loyalty (which reads the name), the exit number and the ramp's
//! control (both found by mile marker for every stop) are the same for a
//! service plaza and a travel center.
//!
//! # Since the store import
//!
//! `tools/import_chain_locators.py` (2026-09-17) matched the chain records to
//! stores by coordinate and typed the matched ones `travel_center` in the
//! data. This screen stays as the net for the records no store was found
//! for, or whose store says nothing about serving trucks. The numbers above
//! are the map before that import; ROADMAP has the ones after.

use crate::data::stop_twins::chain_of;
use crate::data::world_models::Stop;

/// What a name says when the stop really is a toll road's own plaza.
const PLAZA_NAME_PHRASES: &[&str] = &["service plaza", "service area"];

/// What a name says when the stop is a truck stop beside an interchange.
/// `tools/nonchain_plazas.py` mirrors this list; change them together.
pub const TRUCK_STOP_NAME_PHRASES: &[&str] =
    &["truck", "travel center", "travel centre", "travel stop"];

/// The stop type a record's own name supports.
///
/// Everything but a `service_plaza` named for a chain or as a truck stop is
/// returned as recorded.
pub fn screened_stop_type<'a>(name: &str, stop_type: &'a str) -> &'a str {
    if stop_type != "service_plaza" {
        return stop_type;
    }
    let lower = name.to_lowercase();
    if PLAZA_NAME_PHRASES
        .iter()
        .any(|phrase| lower.contains(phrase))
    {
        return stop_type;
    }
    let names_a_truck_stop = TRUCK_STOP_NAME_PHRASES
        .iter()
        .any(|phrase| lower.contains(phrase));
    if chain_of(name).is_some() || names_a_truck_stop {
        "travel_center"
    } else {
        stop_type
    }
}

/// A leg's stops with each chain truck stop typed as what it is.
pub fn screen_branded_plazas(mut stops: Vec<Stop>) -> Vec<Stop> {
    for stop in &mut stops {
        let screened = screened_stop_type(&stop.name, &stop.stop_type);
        if screened != stop.stop_type {
            log::debug!(
                "stop type screened: {} at mile {} is a {screened}, recorded {}",
                stop.name,
                stop.at_mi,
                stop.stop_type
            );
            stop.stop_type = screened.to_string();
        }
    }
    stops
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_a_chain_name_on_a_service_plaza_is_a_travel_center() {
        for name in [
            "Love's Travel Stop",
            "Love's",
            "Pilot Travel Center",
            "Flying J Travel Center",
            "Petro Stopping Centers",
            "TA",
            "TA Express",
            "Road Ranger",
            "ONE9 Travel Center",
            "Sapp Brothers Travel Center",
            // The chain's own word for a store, not a toll road's plaza.
            "Flying J Travel Plaza",
        ] {
            assert_eq!(
                screened_stop_type(name, "service_plaza"),
                "travel_center",
                "{name}"
            );
        }
    }

    #[test]
    fn test_an_independent_that_names_itself_a_truck_stop_is_a_travel_center() {
        for name in [
            "Flags West Truck Stop",
            "Baker Truck Corral",
            "Radford Travel Center",
            "Miller's Travel Centers",
            "Fred's State Line - Casino and Truck Stop",
        ] {
            assert_eq!(
                screened_stop_type(name, "service_plaza"),
                "travel_center",
                "{name}"
            );
        }
        // A plaza that parks trucks says so under its own name.
        assert_eq!(
            screened_stop_type("Sideling Hill Service Plaza Truck Parking", "service_plaza"),
            "service_plaza"
        );
    }

    #[test]
    fn test_a_plaza_that_names_itself_one_stays_a_service_plaza() {
        for name in [
            // No chain at the head of the name: never screened.
            "Pembroke Service Area",
            "Sideling Hill Service Plaza",
            "Clifton Springs Travel Plaza",
            "Eagles Landing Travel Plaza",
            // A chain's concession inside a plaza would say so in its own
            // name. Invented names: the map of 2026-09-17 holds none.
            "Pilot Service Plaza Eastbound",
            "Love's Service Area",
        ] {
            assert_eq!(
                screened_stop_type(name, "service_plaza"),
                "service_plaza",
                "{name}"
            );
        }
    }

    #[test]
    fn test_every_other_type_is_returned_as_recorded() {
        for stop_type in [
            "travel_center",
            "truck_stop",
            "fuel_station",
            "public_rest_area",
            "truck_parking",
            "weigh_station",
            "repair_shop",
        ] {
            assert_eq!(
                screened_stop_type("Love's Travel Stop", stop_type),
                stop_type
            );
        }
    }

    #[test]
    fn test_the_screen_changes_the_type_and_nothing_else() {
        let recorded = Stop {
            name: "Love's Travel Stop".to_string(),
            at_mi: 46.5,
            stop_type: "service_plaza".to_string(),
            parking: "likely".to_string(),
            ..Stop::default()
        };
        let plaza = Stop {
            name: "Pembroke Service Area".to_string(),
            at_mi: 22.0,
            stop_type: "service_plaza".to_string(),
            ..Stop::default()
        };
        let screened = screen_branded_plazas(vec![recorded.clone(), plaza.clone()]);
        assert_eq!(
            screened,
            vec![
                Stop {
                    stop_type: "travel_center".to_string(),
                    ..recorded
                },
                plaza
            ]
        );
        assert_eq!(
            screened[0].spoken_name(),
            "travel center: Love's Travel Stop"
        );
    }
}
