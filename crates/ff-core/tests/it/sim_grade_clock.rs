//! A steep grade runs the clock at real time, so a hill pays and costs the
//! same at every pace (flight, 2026-09-23: descend at real time, climb
//! compressed, and the truck went a long way on almost no engine).

use crate::sim_support::*;
use ff_core::data::world_models::{CorridorDetail, GradeSegment, Leg, Route, StateMileage};
use ff_core::sim::trip::{Trip, TripOptions};
use ff_core::sim::vehicle::TruckState;

const DT: f64 = 1.0 / 60.0;

fn trip_with(grade_segments: Vec<GradeSegment>, time_scale: f64) -> Trip {
    let leg = Leg::new(
        "aberdeen_sd_us",
        "pierre_sd_us",
        100.0,
        "US-83",
        "flat",
        Vec::new(),
    )
    .with_detail(CorridorDetail {
        state_miles: vec![StateMileage::new("South Dakota", 100.0)],
        grade_segments,
        ..Default::default()
    });
    let route = Route::from_legs(
        vec!["aberdeen_sd_us".to_string(), "pierre_sd_us".to_string()],
        vec![leg],
    );
    let mut trip = Trip::new(
        route,
        TruckState {
            cargo_kg: 18_000.0,
            ..Default::default()
        },
        weather("upper_midwest", 1),
        TripOptions {
            seed: Some(2),
            world: Some(world()),
            ..Default::default()
        },
    );
    trip.time_scale = time_scale;
    trip
}

/// Coast a loaded truck over the crest at 40 mph and down a two-mile
/// six-percent grade, and
/// return its speed at the bottom.
fn coast_down(time_scale: f64) -> f64 {
    let mut trip = trip_with(
        vec![GradeSegment::new(10.0, 12.0, -6.0, "mountain", "")],
        time_scale,
    );
    trip.truck.transmission.automatic = true;
    trip.truck.start_engine();
    trip.truck.velocity_mps = 40.0 * 0.44704;
    trip.position_mi = 8.0;
    let mut real_s = 0.0;
    while trip.position_mi < 12.0 {
        assert!(real_s < 1200.0, "{time_scale}x never reached the bottom");
        if trip.position_mi < 10.0 {
            // Held at the crest speed until the descent begins.
            trip.truck.velocity_mps = 40.0 * 0.44704;
        }
        trip.truck.auto_shift();
        trip.truck.update(DT);
        trip.update(DT);
        real_s += DT;
    }
    trip.truck.speed_mph()
}

#[test]
fn test_a_steep_descent_gains_the_same_speed_at_every_pace() {
    let real = coast_down(1.0);
    assert!(
        real > 50.0,
        "the grade should carry the truck: {real:.1} mph"
    );
    for pace in [4.0, 20.0] {
        let paced = coast_down(pace);
        assert!(
            (paced - real).abs() < 3.0,
            "{pace}x reached the bottom at {paced:.1} mph where real time reaches {real:.1}"
        );
    }
}

#[test]
fn test_the_clock_eases_to_real_time_on_a_steep_grade_and_back_after() {
    let mut trip = trip_with(
        vec![
            GradeSegment::new(10.0, 12.0, 4.0, "mountain", ""),
            GradeSegment::new(12.0, 20.0, 1.0, "hills", ""),
        ],
        20.0,
    );
    trip.truck.velocity_mps = 55.0 * 0.44704;
    trip.position_mi = 5.0;
    trip.update(DT);
    assert_eq!(
        trip.effective_time_scale(),
        20.0,
        "a gentle road keeps the pace"
    );

    trip.position_mi = 10.5;
    trip.update(DT);
    let easing = trip.effective_time_scale();
    assert!(
        easing < 20.0 && easing > 1.0,
        "the clock slides, not snaps: {easing}"
    );
    for _ in 0..(4.0 / DT) as usize {
        trip.position_mi = 10.5;
        trip.update(DT);
    }
    assert_eq!(trip.effective_time_scale(), 1.0, "real time on the grade");

    for _ in 0..(4.0 / DT) as usize {
        trip.position_mi = 14.0;
        trip.update(DT);
    }
    assert_eq!(
        trip.effective_time_scale(),
        20.0,
        "pace returns past the grade"
    );
}
