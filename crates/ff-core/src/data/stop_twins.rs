//! One truck stop, listed twice on the same leg.
//!
//! The map import typed a good many chain truck stops as service plazas under
//! the chain's bare name ("Flying J Travel Center"), and the curated pass
//! later added the same stores from the chains' own locators under their full
//! names ("Flying J Travel Center Corfu"), with the exit and the ramp's
//! control. Both records stayed, a mile or three apart by mile marker, because
//! each mile marker is a projection onto simplified route geometry. Copying
//! stops onto opposite-direction legs (2026-09-16) then carried the pairs to
//! legs that had only had one of them.
//!
//! A driver pays for the twin. Signalling for the Flying J seven miles out
//! arms the nearer record, the bare one: no exit number, no stop sign for
//! route-transition assistance to brake for, and the truck rolls through a
//! stop it was told to make (the adversarial battery's
//! `ramp_speed_control_handback`, Buffalo to Rochester, 2026-09-17).
//!
//! This screens the pair at load and never edits the bake, so the rule can be
//! re-judged: the records are still in the data.
//!
//! # The rule
//!
//! On one leg, two records of the same chain ([`TRUCK_STOP_CHAINS`]) within
//! [`TWIN_STOP_MILES`] of each other, serving a common direction, are one
//! facility when at least one of them carries nothing but the chain's name,
//! or when both name the same place. Two records that name DIFFERENT places
//! are left alone however close they sit. The better-documented record stays:
//! a named one over a bare one, a travel center over a service plaza,
//! confirmed or surveyed parking over none, a leg's own record over one
//! copied from its opposite-direction partner.
//!
//! # Where four miles comes from
//!
//! Calibrated against the map, 2026-09-17. For every bare record with a named
//! record of the same chain on the same leg, the gap between them falls in two
//! groups: 77 pairs inside three miles (36 under one, 29 at one to two, 12 at
//! two to three), then a trough of 8 at three to four, then a second rise that
//! keeps going (27 at four to six, 31 at six to ten) -- real neighbours, one
//! interchange and more apart. Four is the bottom of the trough. The errors
//! are not symmetric: a false merge hides one of two stores of the same chain
//! that are under four miles apart, and the driver still has the other; a
//! missed twin is a phantom exit. At four miles the screen drops 90 records
//! on 61 legs.
//!
//! # Since the store import
//!
//! `tools/import_chain_locators.py` (2026-09-17) matched the chain records to
//! stores by coordinate, named the bare ones and deleted the twins in the
//! data, so most of what is measured above is no longer on the map. This
//! screen stays as the net for the records no store was found for. The
//! numbers above are the map before that import; ROADMAP has the ones after.

use crate::data::world_constants::TRUCK_STOP_CHAINS;
use crate::data::world_models::Stop;

/// Two same-chain records this close on one leg are read as one facility.
pub const TWIN_STOP_MILES: f64 = 4.0;

/// The source note the opposite-direction copy leaves on what it copies.
const OPPOSITE_DIRECTION_COPY: &str = "Opposite-direction copy";

/// Words a chain puts in every store's name, which therefore name no place.
const GENERIC_NAME_WORDS: &[&str] = &[
    "travel",
    "center",
    "centre",
    "centers",
    "travelcenter",
    "travelcenters",
    "stop",
    "stopping",
    "plaza",
    "truck",
    "the",
    "service",
    "area",
    "station",
    "store",
    "country",
    "dealer",
    "of",
    "america",
    "and",
    "express",
    "fuel",
    "shopping",
];

/// The chain at the head of a stop's name, if any.
pub(crate) fn chain_of(name: &str) -> Option<&'static str> {
    let lower = name.trim().to_lowercase();
    TRUCK_STOP_CHAINS
        .iter()
        .find(|chain| lower.starts_with(**chain) || lower == chain.trim())
        .copied()
}

/// What a stop's name says beyond its chain: the town, the exit, the store.
fn place_words(name: &str, chain: &str) -> Vec<String> {
    let lower = name.trim().to_lowercase();
    let rest = lower.strip_prefix(chain.trim()).unwrap_or(&lower);
    let mut words: Vec<String> = rest
        .split(|c: char| !c.is_alphanumeric())
        .filter(|word| word.len() > 1)
        .filter(|word| !word.chars().all(|c| c.is_ascii_digit()))
        .filter(|word| !GENERIC_NAME_WORDS.contains(word))
        .map(str::to_string)
        .collect();
    words.sort();
    words.dedup();
    words
}

fn serves_a_common_direction(a: &Stop, b: &Stop) -> bool {
    let both =
        |stop: &Stop| stop.directions.is_empty() || stop.directions.iter().any(|d| d == "both");
    both(a) || both(b) || a.directions.iter().any(|d| b.directions.contains(d))
}

fn same_facility(a: &Stop, b: &Stop, chain: &str) -> bool {
    if (a.at_mi - b.at_mi).abs() > TWIN_STOP_MILES || !serves_a_common_direction(a, b) {
        return false;
    }
    let (place_a, place_b) = (place_words(&a.name, chain), place_words(&b.name, chain));
    place_a.is_empty() || place_b.is_empty() || place_a == place_b
}

/// Lower sorts first: the record worth keeping.
fn documentation_rank(stop: &Stop, chain: &str) -> (u8, u8, u8, u8) {
    (
        u8::from(place_words(&stop.name, chain).is_empty()),
        u8::from(stop.stop_type != "travel_center"),
        u8::from(stop.parking != "confirmed" && stop.parking_spaces <= 0),
        u8::from(stop.source.contains(OPPOSITE_DIRECTION_COPY)),
    )
}

/// A leg's stops with each chain facility listed once, in their original
/// order.
pub fn screen_twin_stops(stops: Vec<Stop>) -> Vec<Stop> {
    let chains: Vec<Option<&'static str>> = stops.iter().map(|s| chain_of(&s.name)).collect();
    // Best-documented first, mile marker breaking ties so the result never
    // depends on the order the records were written in.
    let mut order: Vec<usize> = (0..stops.len()).filter(|&i| chains[i].is_some()).collect();
    order.sort_by(|&a, &b| {
        let chain_a = chains[a].unwrap_or_default();
        let chain_b = chains[b].unwrap_or_default();
        documentation_rank(&stops[a], chain_a)
            .cmp(&documentation_rank(&stops[b], chain_b))
            .then(stops[a].at_mi.total_cmp(&stops[b].at_mi))
            .then(a.cmp(&b))
    });
    let mut kept: Vec<usize> = Vec::new();
    let mut dropped = vec![false; stops.len()];
    for index in order {
        let chain = chains[index].unwrap_or_default();
        let twin_of = kept.iter().find(|&&k| {
            chains[k] == chains[index] && same_facility(&stops[k], &stops[index], chain)
        });
        match twin_of {
            Some(&k) => {
                log::debug!(
                    "stop twin screened: {} at mile {} is {} at mile {}",
                    stops[index].name,
                    stops[index].at_mi,
                    stops[k].name,
                    stops[k].at_mi
                );
                dropped[index] = true;
            }
            None => kept.push(index),
        }
    }
    stops
        .into_iter()
        .zip(dropped)
        .filter_map(|(stop, gone)| (!gone).then_some(stop))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn stop(name: &str, at_mi: f64, stop_type: &str) -> Stop {
        Stop {
            name: name.to_string(),
            at_mi,
            stop_type: stop_type.to_string(),
            ..Stop::default()
        }
    }

    fn names(stops: &[Stop]) -> Vec<&str> {
        stops.iter().map(|s| s.name.as_str()).collect()
    }

    #[test]
    fn test_the_bare_record_beside_the_named_one_is_the_same_store() {
        // Buffalo to Rochester, as shipped 2026-09-16.
        let screened = screen_twin_stops(vec![
            stop("Pembroke Service Area", 22.0, "service_plaza"),
            stop("Flying J Travel Center", 25.1, "service_plaza"),
            stop("Flying J Travel Center Corfu", 27.9, "travel_center"),
        ]);
        assert_eq!(
            names(&screened),
            ["Pembroke Service Area", "Flying J Travel Center Corfu"]
        );
    }

    #[test]
    fn test_two_stores_that_name_different_towns_are_two_stores() {
        let screened = screen_twin_stops(vec![
            stop("Love's Travel Stop Harlingen", 30.4, "travel_center"),
            stop("Love's Travel Stop San Benito", 27.0, "travel_center"),
        ]);
        assert_eq!(screened.len(), 2);
    }

    #[test]
    fn test_the_next_interchange_over_is_a_neighbour_not_a_twin() {
        let screened = screen_twin_stops(vec![
            stop("Pilot Travel Center", 40.0, "service_plaza"),
            stop("Pilot Travel Center Stanfield", 44.5, "travel_center"),
        ]);
        assert_eq!(screened.len(), 2);
    }

    #[test]
    fn test_another_chain_at_the_same_exit_is_left_alone() {
        let screened = screen_twin_stops(vec![
            stop("Pilot Travel Center", 10.0, "service_plaza"),
            stop("Love's Travel Stop Gretna", 10.4, "travel_center"),
            stop("Joe's Diner", 10.2, "travel_center"),
            stop("Joe's Diner", 10.3, "travel_center"),
        ]);
        assert_eq!(screened.len(), 4, "only chain truck stops are screened");
    }

    #[test]
    fn test_a_leg_keeps_its_own_record_over_a_copy_of_it() {
        let mut copy = stop("Flying J Travel Center", 35.5, "travel_center");
        copy.source = "OpenStreetMap. Opposite-direction copy onto partner.".to_string();
        let own = stop("Flying J Travel Center", 34.9, "travel_center");
        let screened = screen_twin_stops(vec![copy, own.clone()]);
        assert_eq!(screened, vec![own]);
    }

    #[test]
    fn test_opposite_carriageway_plazas_are_not_merged() {
        let mut east = stop("Petro Stopping Center", 50.0, "travel_center");
        east.directions = vec!["eastbound".to_string()];
        let mut west = stop("Petro Stopping Center", 50.6, "travel_center");
        west.directions = vec!["westbound".to_string()];
        assert_eq!(screen_twin_stops(vec![east, west]).len(), 2);
    }
}
