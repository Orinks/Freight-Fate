//! Lane keeping on full passes a slow vehicle the hazard call names, and
//! comes back to the right lane once it is behind (owner ruling,
//! 2026-10-01). The pass itself is pinned beside the call it replaces, in
//! `transcript_driving_cruise_weather_hazards`; this is the rest of it.

use ff_core::sim::traffic_manager::TrafficVehicle;
use ff_core::sim::trip_models::{
    OpenSide, RoadStop, TrafficContext, TripEvent, TripEventData, TripEventKind,
};
use ff_core::speech_text::{in_lane_hazard_call, passing_hazard_call};
use freight_fate::playtest::harness::PlaytestHarness;

use crate::transcript_cruise_support::*;
use crate::transcript_driving_cruise_weather_hazards::{meet_a_slow_car, the_call};

#[test]
fn after_the_pass_lane_keeping_returns_right_once_the_car_is_behind() {
    let mut harness = meet_a_slow_car("Pass Return", "full", 2, 0, &[], false);
    assert!(the_call(&harness).ends_with("Passing on the left."));

    // Over in the left lane, and held there while the car it is passing is
    // still ahead of or beside the cab.
    let mut elapsed = 0.0;
    while harness.read_drive(|d| d.lane.lane) == 0 && elapsed < 5.0 {
        frame(&mut harness, DT);
        elapsed += DT;
    }
    assert_eq!(harness.read_drive(|d| d.lane.lane), 1);
    let behind_by = |h: &PlaytestHarness| {
        h.read_drive(|d| {
            let car = d
                .trip
                .traffic_manager
                .vehicles
                .iter()
                .find(|v| v.key == "bench:lead")
                .map_or(f64::INFINITY, |v| v.position_mi);
            d.trip.position_mi - car
        })
    };
    while harness.read_drive(|d| d.lane.lane == 1 && d.lane_change_target.is_none())
        && elapsed < 180.0
    {
        frame(&mut harness, DT);
        elapsed += DT;
    }
    assert!(
        behind_by(&harness) > 0.0,
        "moved back in ahead of the car it was passing\n{}",
        harness.transcript_text()
    );
    assert_eq!(harness.read_drive(|d| d.lane_change_target), Some(0));

    while harness.read_drive(|d| d.lane.lane) != 0 && elapsed < 190.0 {
        frame(&mut harness, DT);
        elapsed += DT;
    }
    assert_eq!(harness.read_drive(|d| d.lane.lane), 0);
    assert!(harness.read_drive(|d| d.passing.is_none()));
    assert!(
        said_any(&harness, "In the right lane."),
        "{:#?}",
        spoken(&harness)
    );
    assert!(!said_any(&harness, "sideswiped"), "{:#?}", spoken(&harness));
    // The lane it comes back to is not announced as open first: the truck
    // takes it, and the arrival says so.
    assert!(
        !said_any(&harness, "Right lane open."),
        "{:#?}",
        spoken(&harness)
    );
}

/// The slow-car call as the trip raises it with the left lane open.
fn slow_car_call(at_mi: f64) -> TripEvent {
    let lead = TrafficVehicle::new(
        "bench:raised",
        at_mi + 0.02,
        45.0,
        45.0,
        0,
        "following",
        "car",
    )
    .with_lane(0);
    TripEvent {
        kind: TripEventKind::Hazard,
        message: in_lane_hazard_call("Slow car right ahead.", OpenSide::Left),
        data: TripEventData {
            deadline_s: Some(2.5),
            traffic: Some(TrafficContext {
                lead,
                gap_mi: 0.02,
                closing_mph: 20.0,
            }),
            dodgeable: Some(true),
            in_lane: Some(true),
            open_side: Some(OpenSide::Left),
            pass_message: passing_hazard_call("Slow car right ahead.", OpenSide::Left),
            name: Some("the slow car".to_string()),
            ..Default::default()
        },
    }
}

#[test]
fn lining_up_for_an_exit_the_call_stays_the_drivers() {
    // Inside the two miles where lane keeping is heading for the right lane
    // for its own exit, it does not pull out to pass: the call is the one a
    // driver answers, and braking is what the assist does about it. A semi
    // alongside keeps the rig's own call from passing first.
    let mut harness = meet_a_slow_car("Pass Near Exit", "full", 2, 0, &[1], false);
    let raise = |harness: &mut PlaytestHarness, exit_ahead: Option<f64>| {
        harness.clear_speech();
        harness.with_drive(move |d, ctx| {
            d.hazard_deadline = None;
            let at = d.trip.position_mi;
            d.exit_stop = exit_ahead
                .map(|ahead| RoadStop::new("Test Receiver", at + ahead, "delivery_destination"));
            d.handle_trip_event(ctx, &slow_car_call(at));
        });
    };

    raise(&mut harness, Some(1.5));
    assert_eq!(
        the_call(&harness),
        "Change lanes or brake! Slow car right ahead. Left lane open."
    );
    assert!(harness.read_drive(|d| d.lane_change_target).is_none());

    // The same call with the exit still five miles off is passed.
    raise(&mut harness, Some(5.0));
    assert_eq!(
        the_call(&harness),
        "Slow car right ahead. Passing on the left."
    );
    assert_eq!(harness.read_drive(|d| d.lane_change_target), Some(1));
}
