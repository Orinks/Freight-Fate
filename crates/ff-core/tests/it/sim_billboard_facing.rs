//! A placed billboard faces the traffic it was written for.
//!
//! Its copy says "ahead" or "next exit", so heard from the other side of the
//! road it is false: the Wall Drug countdown used to play after the exit to
//! anyone driving east from Rapid City, and "Meridian is ahead" played just
//! after leaving Meridian. These drive each direction through the two
//! countdowns and check every sign is read on the way to its attraction.

use ff_core::sim::trip::{Trip, TripOptions};
use ff_core::sim::vehicle::TruckState;

use crate::sim_support::{route_from_cities, weather, world};

fn trip_through(cities: &[&str]) -> Trip {
    let world = world();
    let mut truck = TruckState::default();
    truck.transmission.automatic = true;
    Trip::new(
        route_from_cities(world, cities),
        truck,
        weather("great_lakes", 1),
        TripOptions {
            world: Some(world),
            ..TripOptions::seeded(1)
        },
    )
}

/// The placed signs whose name starts with `series`, in the order heard.
fn countdown(trip: &Trip, series: &str) -> Vec<(f64, String, String)> {
    let mut signs: Vec<_> = trip
        .landmarks
        .iter()
        .filter(|c| c.category == "billboard_sign" && c.key.contains(series))
        .map(|c| (c.at_mi, c.key.clone(), c.spoken.clone()))
        .collect();
    signs.sort_by(|a, b| a.0.total_cmp(&b.0));
    signs
}

fn assert_counts_down(cities: &[&str], signs: &[(f64, String, String)]) {
    let order: Vec<_> = signs
        .iter()
        .map(|(_, key, _)| {
            ["sign one", "sign two", "sign three"]
                .into_iter()
                .find(|n| key.contains(n))
                .unwrap_or(key)
        })
        .collect();
    assert_eq!(
        order,
        ["sign one", "sign two", "sign three"],
        "{cities:?}: {signs:?}"
    );
    assert!(signs[2].2.contains("next exit"), "{cities:?}: {signs:?}");
}

#[test]
fn test_wall_drug_counts_down_to_the_exit_from_either_side() {
    for cities in [
        ["mitchell_sd_us", "rapid_city_sd_us"],
        ["rapid_city_sd_us", "mitchell_sd_us"],
        ["sioux_falls_sd_us", "rapid_city_sd_us"],
        ["rapid_city_sd_us", "sioux_falls_sd_us"],
    ] {
        let trip = trip_through(&cities);
        let wall = trip
            .stops
            .iter()
            .find(|s| s.name == "Wall Drug")
            .unwrap_or_else(|| panic!("{cities:?}: no Wall Drug stop"))
            .at_mi;
        let signs = countdown(&trip, "Wall Drug (");
        assert_counts_down(&cities, &signs);
        let (next_exit, _, _) = &signs[2];
        assert!(
            *next_exit < wall && wall - next_exit < 3.0,
            "{cities:?}: next exit read at mile {next_exit:.1}, Wall Drug at {wall:.1}"
        );
    }
}

#[test]
fn test_south_of_the_border_counts_down_both_ways() {
    for cities in [
        [
            "savannah_ga_us",
            "florence_sc_us",
            "lumberton_nc_us",
            "fayetteville_nc_us",
        ],
        [
            "fayetteville_nc_us",
            "lumberton_nc_us",
            "florence_sc_us",
            "savannah_ga_us",
        ],
    ] {
        let trip = trip_through(&cities);
        assert_counts_down(&cities, &countdown(&trip, "South of the Border ("));
    }
}

#[test]
fn test_a_placed_sign_is_not_read_from_the_far_side_of_the_road() {
    let meridian_ahead = |trip: &Trip| {
        trip.landmarks
            .iter()
            .any(|c| c.spoken.contains("Meridian is ahead"))
    };
    assert!(meridian_ahead(&trip_through(&[
        "mobile_al_us",
        "meridian_ms_us"
    ])));
    assert!(!meridian_ahead(&trip_through(&[
        "meridian_ms_us",
        "mobile_al_us"
    ])));

    // Written westbound, on a leg stored eastbound: heard leaving Amarillo,
    // a mile and a half before the ranch, not on the far side of the state.
    let trip = trip_through(&["amarillo_tx_us", "tucumcari_nm_us"]);
    let ranch = countdown(&trip, "Cadillac Ranch");
    assert_eq!(ranch.len(), 1, "{ranch:?}");
    assert!(ranch[0].0 < 10.0, "{ranch:?}");
}
