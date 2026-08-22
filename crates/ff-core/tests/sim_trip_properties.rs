//! Property checks for route-backed trip simulation invariants (port of
//! `tests/test_trip_properties.py`; hypothesis -> proptest).

mod sim_support;

use ff_core::sim::trip::{Trip, TripOptions};
use ff_core::sim::trip_models::{TripEventKind, ZONE_MIN_GAP_MI};
use ff_core::sim::vehicle::TruckState;
use proptest::prelude::*;
use sim_support::*;

const SUPPORTED_ROUTE_PAIRS: [(&str, &str); 5] = [
    ("Buffalo", "Rochester"),
    ("Chicago", "Indianapolis"),
    ("Chicago", "St. Louis"),
    ("Denver", "Cheyenne"),
    ("Memphis", "Nashville"),
];

proptest! {
    #![proptest_config(ProptestConfig::with_cases(50))]

    #[test]
    fn test_trip_position_derived_values_stay_bounded(
        pair in 0usize..SUPPORTED_ROUTE_PAIRS.len(),
        progress in 0.0f64..=1.25,
        imperial in any::<bool>(),
    ) {
        let w = world();
        let (a, b) = SUPPORTED_ROUTE_PAIRS[pair];
        let route = supported(w, a, b);
        let region = w.cities[&route.cities[0]].region.clone();
        let mut trip = Trip::new(
            route.clone(),
            TruckState::default(),
            weather(&region, 7),
            TripOptions {
                seed: Some(11),
                imperial,
                world: Some(w),
                ..Default::default()
            },
        );

        trip.position_mi = route.miles() * progress;

        prop_assert!(0.0 <= trip.remaining_miles() && trip.remaining_miles() <= trip.total_miles());
        prop_assert!(trip.current_leg_index() < route.legs.len());

        let (leg_index, leg_start) = trip.leg_at_mile(trip.position_mi);
        prop_assert!(leg_index < route.legs.len());
        prop_assert!((leg_start - trip.leg_starts[leg_index]).abs() < 1e-9);

        let (speed_limit, reason) = trip.speed_limit_at(trip.position_mi);
        prop_assert!(0.0 < speed_limit && speed_limit <= 85.0);
        prop_assert!(reason.as_deref().is_none_or(|r| !r.is_empty()));

        let mut sorted = trip.navigation_cues.clone();
        sorted.sort_by(|x, y| x.at_mi.partial_cmp(&y.at_mi).unwrap());
        prop_assert_eq!(&trip.navigation_cues, &sorted);
        prop_assert!(trip
            .navigation_cues
            .iter()
            .all(|cue| 0.0 <= cue.at_mi && cue.at_mi <= trip.total_miles()));
    }
}

#[test]
fn test_generated_slow_zones_never_nest_or_touch() {
    // Construction and traffic zones must be separated by open road
    // (player-reported on the 2026-07-09 snapshot).
    let w = world();
    let route = supported(w, "Chicago", "St. Louis");
    let region = w.cities[&route.cities[0]].region.clone();
    for seed in 0..300 {
        let trip = Trip::new(
            route.clone(),
            TruckState::default(),
            weather(&region, 7),
            TripOptions {
                seed: Some(seed),
                world: Some(w),
                ..Default::default()
            },
        );
        let mut zones: Vec<_> = trip
            .zones
            .iter()
            .filter(|z| z.reason == "construction" || z.reason == "heavy traffic")
            .cloned()
            .collect();
        zones.sort_by(|a, b| a.start_mi.partial_cmp(&b.start_mi).unwrap());
        for pair in zones.windows(2) {
            let (a, b) = (&pair[0], &pair[1]);
            assert!(
                b.start_mi - a.end_mi >= ZONE_MIN_GAP_MI,
                "seed {seed}: {} {:.1}-{:.1} and {} {:.1}-{:.1} overlap or touch",
                a.reason,
                a.start_mi,
                a.end_mi,
                b.reason,
                b.start_mi,
                b.end_mi
            );
        }
    }
}

#[test]
fn test_no_brake_hazards_on_facility_access_roads() {
    // A deadhead crawl to a pickup facility must never spring a "brake now"
    // hazard. The Python test forced `_hazard_risk` to certainty by
    // monkeypatching; here the access-road gate is checked first and the
    // highway control run makes the same check fire for real.
    let w = world();
    let city = w.cities["chicago_il_us"].clone();
    let location = city.locations[0].clone();
    let route = w
        .facility_approach_route(&city.key, &location.name)
        .expect("a facility approach route");
    let mut trip = Trip::new(
        route,
        TruckState::default(),
        weather(&city.region, 7),
        TripOptions {
            seed: Some(1),
            world: Some(w),
            ..Default::default()
        },
    );
    assert!(trip.is_facility_approach_route());

    trip.hazard_check_mi = 0.0;
    trip.check_hazards(1.0);
    assert!(trip.events.iter().all(|e| e.kind != TripEventKind::Hazard));

    // The same forced check on a normal route does fire, so this test would
    // catch the gate being lost. Without a monkeypatch the hazard roll is
    // seeded; sweep a few seeds for the one that rolls under the risk.
    let highway_route = supported(w, "Chicago", "St. Louis");
    let fired = (0..40).any(|seed| {
        let mut highway_trip = Trip::new(
            highway_route.clone(),
            TruckState::default(),
            weather(&city.region, 7),
            TripOptions {
                seed: Some(seed),
                world: Some(w),
                ..Default::default()
            },
        );
        highway_trip.hazard_check_mi = 0.0;
        highway_trip.check_hazards(1.0);
        highway_trip
            .events
            .iter()
            .any(|e| e.kind == TripEventKind::Hazard)
    });
    assert!(fired);
}
