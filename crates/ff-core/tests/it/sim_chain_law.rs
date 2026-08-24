//! Chain laws: areas over sustained steep grade, levels from the live
//! weather and the spoken sign (the trip half of `tests/test_chain_law.py`;
//! the seeded checkpoint and its citation live in
//! `crates/freight-fate/tests/states_driving_chain_law.rs`).
//!
//! The physics (grip multipliers, chain wear, the snap) is pinned in
//! `test_vehicle.py` and `test_physics_bench.py`; these tests cover the law
//! layer that sits on top of it.


use ff_core::data::world_models::GradeSegment;
use ff_core::sim::trip::{Trip, TripOptions};
use ff_core::sim::vehicle::TruckState;
use ff_core::sim::weather::WeatherKind;
use crate::sim_support::*;

/// A Chicago-Indianapolis trip; optionally with a synthetic grade profile
/// baked onto leg 0 before construction so chain-law placement sees it.
///
/// Python monkeypatched `Trip.grade_at`; here the same shape comes from real
/// grade segments on the leg, which is the only input `grade_at` reads before
/// its flat-terrain fallback.
fn trip(grade: Option<(f64, f64)>) -> Trip {
    let w = world();
    let mut route = first_route_option(w, "Chicago", "Indianapolis");
    if let Some((start, end)) = grade {
        let edited = with_corridor(&route.legs[0], |detail| {
            detail.grade_segments = vec![GradeSegment {
                start_mi: start,
                end_mi: end,
                avg_grade_pct: 6.0,
                terrain: "mountain".to_string(),
                source: "test fixture".to_string(),
            }];
        });
        route = replace_leg(&route, 0, edited);
    }
    let mut truck = TruckState::default();
    truck.transmission.automatic = true;
    Trip::new(
        route,
        truck,
        weather("great_lakes", 1),
        TripOptions {
            seed: Some(2),
            world: Some(w),
            ..Default::default()
        },
    )
}

/// Flat, except a sustained 6 percent between miles 10 and 14.
fn mountain_grade() -> Option<(f64, f64)> {
    Some((10.0, 14.0))
}

#[test]
fn test_chain_law_areas_sit_over_sustained_steep_grade() {
    let trip = trip(mountain_grade());
    assert_eq!(trip.chain_law_areas.len(), 1);
    let (start, end) = trip.chain_law_areas[0];
    // The area leads the grade by the chain-up pullout and covers the run.
    assert!((start - 9.5).abs() <= 0.3, "{start}");
    assert!(end >= 14.0, "{end}");
    assert_eq!(trip.chain_law_area_at(12.0), Some(0));
    assert_eq!(trip.chain_law_area_at(5.0), None);
}

#[test]
fn test_short_pitches_do_not_make_a_chain_law() {
    // A half-mile 6 percent pitch is a hill, not a chain-control pass.
    let trip = trip(Some((10.0, 10.5)));
    assert!(
        trip.chain_law_areas.is_empty(),
        "{:?}",
        trip.chain_law_areas
    );
}

#[test]
fn test_chain_law_level_follows_the_surface() {
    let mut trip = trip(None);
    trip.weather.current = WeatherKind::Clear;
    assert_eq!(trip.chain_law_level(), 0);
    trip.weather.current = WeatherKind::Rain;
    assert_eq!(trip.chain_law_level(), 0);
    trip.weather.current = WeatherKind::Snow;
    assert_eq!(trip.chain_law_level(), 1);
    trip.weather.current = WeatherKind::Ice;
    assert_eq!(trip.chain_law_level(), 2);
}

#[test]
fn test_chain_law_sign_speaks_on_approach_and_escalates() {
    let mut trip = trip(mountain_grade());
    trip.weather.current = WeatherKind::Snow;
    trip.position_mi = 9.0; // inside the lookahead of the area at 9.5
    trip.check_chain_law();
    let signs = |trip: &Trip| -> Vec<String> {
        trip.events
            .iter()
            .filter(|e| e.text().contains("chain law in effect"))
            .map(|e| e.text().to_string())
            .collect()
    };
    let spoken = signs(&trip);
    assert_eq!(spoken.len(), 1, "{spoken:?}");
    assert!(spoken[0].contains("Level 1"), "{}", spoken[0]);
    assert!(spoken[0].contains("Chain-up area"), "{}", spoken[0]);
    // The same sign does not repeat, but an escalation to ice speaks again.
    trip.check_chain_law();
    trip.weather.current = WeatherKind::Ice;
    trip.check_chain_law();
    let spoken = signs(&trip);
    assert_eq!(spoken.len(), 2, "{spoken:?}");
    assert!(spoken[1].contains("Level 2"), "{}", spoken[1]);

    // No law, no sign: the areas are silent infrastructure in clear weather.
    let mut trip2 = trip_clear();
    trip2.check_chain_law();
    assert!(
        !trip2.events.iter().any(|e| e.text().contains("chain law")),
        "clear weather spoke a chain law"
    );
}

fn trip_clear() -> Trip {
    let mut trip = trip(None);
    trip.weather.current = WeatherKind::Clear;
    trip
}
