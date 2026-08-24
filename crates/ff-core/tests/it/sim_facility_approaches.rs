//! The trip side of the facility-approach layer: the status line names the
//! dock, and a long synthetic approach steps its posted speeds down (the sim
//! half of `tests/test_facility_approaches.py`).

use crate::sim_support::*;
use ff_core::data::world_models::{CorridorDetail, Leg, Route, StateMileage};
use ff_core::sim::trip::{Trip, TripOptions};
use ff_core::sim::vehicle::TruckState;
use ff_core::sim::weather::WeatherSystem;

#[test]
fn test_facility_approach_status_names_the_dock_not_the_town() {
    // Owner playtest 2026-07-19: 14 miles of "toward Camp Verde" while
    // pulling out of Camp Verde for its own warehouse read as a wrong turn.
    let leg = Leg::new(
        "camp_verde_az_us",
        "camp_verde_az_us",
        14.0,
        "South Quarterhorse Lane",
        "flat",
        Vec::new(),
    )
    .with_detail(CorridorDetail {
        state_miles: vec![StateMileage::new("Arizona", 14.0)],
        ..Default::default()
    });
    let route = Route::from_legs(
        vec![
            "camp_verde_az_us".to_string(),
            "camp_verde_az_us".to_string(),
        ],
        vec![leg],
    );
    let trip = Trip::new(
        route,
        TruckState::default(),
        WeatherSystem::new("desert_southwest", Some(1), None, None, true),
        TripOptions {
            seed: Some(2),
            destination_label: "dry warehouse Camp Verde Dry Warehouse".to_string(),
            world: Some(world()),
            ..Default::default()
        },
    );
    let status = trip.progress_summary(true);
    assert!(
        status.contains("toward dry warehouse Camp Verde Dry Warehouse"),
        "{status}"
    );
    assert!(!status.contains("toward Camp Verde,"), "{status}");
    assert!(
        status.contains("Destination dry warehouse Camp Verde Dry Warehouse ahead."),
        "{status}"
    );
}

#[test]
fn test_long_synthetic_approach_steps_down_45_25_15() {
    // Owner design 2026-07-24: a long local approach is an arterial before it
    // is an access road -- 45 wide out, 25 for the last two miles, 15 at the
    // gate. A blanket 25 for six-plus miles was a crawl no city posts.
    let w = world();
    let route = w
        .facility_approach_route("madison_wi_us", "Madison Cold Storage")
        .expect("Madison Cold Storage has an approach route");
    assert!(route.miles() > 3.0); // long synthetic approach (clamped to Josh's band)
    let mut truck = TruckState::default();
    truck.transmission.automatic = true;
    truck.start_engine();
    let trip = Trip::new(
        route,
        truck,
        weather("great_lakes", 1),
        TripOptions {
            seed: Some(2),
            world: Some(w),
            ..Default::default()
        },
    );

    let reasons: Vec<(String, f64)> = trip
        .zones
        .iter()
        .map(|z| (z.reason.clone(), z.limit_mph))
        .collect();
    assert!(
        reasons.contains(&("facility approach".to_string(), 45.0)),
        "{reasons:?}"
    );
    assert!(
        reasons.contains(&("facility access road".to_string(), 25.0)),
        "{reasons:?}"
    );
    assert!(
        reasons.contains(&("facility gate".to_string(), 15.0)),
        "{reasons:?}"
    );
    let arterial = trip
        .zones
        .iter()
        .find(|z| z.reason == "facility approach")
        .expect("an arterial zone");
    let access = trip
        .zones
        .iter()
        .find(|z| z.reason == "facility access road")
        .expect("an access-road zone");
    assert_eq!(arterial.end_mi, access.start_mi); // steps down, never overlaps up
}
