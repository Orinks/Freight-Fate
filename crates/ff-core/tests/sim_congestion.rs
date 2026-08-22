//! Grounded congestion: HPMS volume against capacity on a commuter clock
//! (port of `tests/test_congestion.py`).

mod sim_support;

use ff_core::data::world_models::{Leg, TrafficVolumeSample};
use ff_core::sim::season::{day_of_week, is_weekend};
use ff_core::sim::trip::{Trip, TripOptions};
use ff_core::sim::trip_models::{
    congestion_limit_mph, congestion_ratio, heuristic_aadt, leg_aadt_at, leg_lane_count,
    HOURLY_SHARE_WEEKDAY, HOURLY_SHARE_WEEKEND, URBAN_RADIUS_MI,
};
use ff_core::sim::vehicle::TruckState;
use sim_support::*;

fn sample(at_mi: f64, aadt: f64, lanes: i64) -> TrafficVolumeSample {
    TrafficVolumeSample {
        at_mi,
        aadt,
        lanes,
        source: String::new(),
    }
}

/// A trip whose first leg carries a known HPMS profile: a genuinely
/// overloaded metro stretch for the first dozen miles, light rural volume
/// beyond. Independent of whatever the checked-in bake contains.
fn synthetic_trip(opts: TripOptions) -> Trip {
    let cached = first_route_option(world(), "Chicago", "Indianapolis");
    let leg = with_corridor(&cached.legs[0], |d| {
        d.traffic_volumes = vec![sample(0.0, 150000.0, 3), sample(12.0, 22000.0, 2)];
    });
    let route = replace_leg(&cached, 0, leg);
    let mut truck = TruckState::default();
    truck.transmission.automatic = true;
    Trip::new(
        route,
        truck,
        weather("great_lakes", 1),
        TripOptions {
            seed: Some(2),
            world: Some(world()),
            ..opts
        },
    )
}

fn approx(a: f64, b: f64) -> bool {
    (a - b).abs() < 1e-6
}

// -- The commuter curve and capacity math -------------------------------------------

#[test]
fn test_hourly_shares_cover_a_full_day() {
    assert_eq!(HOURLY_SHARE_WEEKDAY.len(), 24);
    assert_eq!(HOURLY_SHARE_WEEKEND.len(), 24);
    assert!((HOURLY_SHARE_WEEKDAY.iter().sum::<f64>() - 1.0).abs() <= 0.02);
    assert!((HOURLY_SHARE_WEEKEND.iter().sum::<f64>() - 1.0).abs() <= 0.02);
    // Weekday twin peaks; weekend has no AM commute spike.
    let (weekday, weekend) = (HOURLY_SHARE_WEEKDAY.to_vec(), HOURLY_SHARE_WEEKEND.to_vec());
    assert!(weekday[7] > weekday[11]);
    let peak = HOURLY_SHARE_WEEKDAY
        .iter()
        .cloned()
        .fold(f64::MIN, f64::max);
    assert_eq!(HOURLY_SHARE_WEEKDAY[17], peak);
    assert!(weekend[7] < weekday[7] / 2.0);
}

#[test]
fn test_urban_volumes_jam_at_rush_hour_and_rural_ones_do_not() {
    let urban = heuristic_aadt("I-90", true);
    let rural = heuristic_aadt("I-90", false);
    assert!(congestion_ratio(urban, 17.0, 2, false) > 0.9);
    assert!(congestion_ratio(urban, 3.0, 2, false) < 0.2);
    assert!(congestion_ratio(rural, 17.0, 2, false) < 0.5);
    // The same demand over more lanes flows better.
    assert!(congestion_ratio(urban, 17.0, 4, false) < congestion_ratio(urban, 17.0, 2, false));
}

#[test]
fn test_congestion_limit_buckets() {
    assert!(congestion_limit_mph(0.5, 70.0).is_none());
    assert!(approx(congestion_limit_mph(0.8, 70.0).unwrap(), 58.0));
    assert!(approx(congestion_limit_mph(0.95, 70.0).unwrap(), 38.0));
    assert!(approx(congestion_limit_mph(1.2, 70.0).unwrap(), 26.0));
}

// -- The career calendar knows its weekdays ------------------------------------------

#[test]
fn test_career_clock_weekdays() {
    // Careers start Wednesday, March 21, 2001.
    assert_eq!(day_of_week(0.0), 2);
    assert!(!is_weekend(0.0));
    assert_eq!(day_of_week(3.0 * 24.0), 5); // Saturday
    assert!(is_weekend(3.0 * 24.0));
    assert!(is_weekend(4.0 * 24.0)); // Sunday
    assert!(!is_weekend(5.0 * 24.0)); // Monday
}

// -- Placement: prone stretches sit at the metros ------------------------------------

#[test]
fn test_congestion_zones_sit_on_the_overloaded_stretch() {
    let trip = synthetic_trip(TripOptions::default());
    let jams: Vec<_> = trip
        .zones
        .iter()
        .filter(|z| z.reason == "heavy traffic")
        .collect();
    assert!(
        !jams.is_empty(),
        "an overloaded metro stretch should be congestion-prone"
    );
    let zone = jams[0];
    assert!(zone.aadt.is_some_and(|a| a >= 100000.0));
    assert!(zone.start_mi <= 1.0); // covers the loaded miles...
    assert!(zone.end_mi <= 12.0 + URBAN_RADIUS_MI); // ...not the rural ones
                                                    // The light rural remainder of the leg spawns no jam.
    assert!(jams.iter().all(|z| z.end_mi <= 20.0));
}

#[test]
fn test_weekend_mornings_do_not_jam() {
    // Saturday (career day 3) at the 7 AM weekday peak hour.
    let weekday = synthetic_trip(TripOptions {
        start_hour: 7.0,
        career_hours: Some(0.0),
        ..Default::default()
    });
    let weekend = synthetic_trip(TripOptions {
        start_hour: 7.0,
        career_hours: Some(3.0 * 24.0),
        ..Default::default()
    });
    let mut weekday_jam = weekday
        .zones
        .iter()
        .find(|z| z.reason == "heavy traffic")
        .unwrap()
        .clone();
    let mut weekend_jam = weekend
        .zones
        .iter()
        .find(|z| z.reason == "heavy traffic")
        .unwrap()
        .clone();
    assert!(weekday.zone_is_active(&mut weekday_jam));
    assert!(!weekend.zone_is_active(&mut weekend_jam));
}

#[test]
fn test_active_jam_sets_the_prevailing_speed() {
    let mut trip = synthetic_trip(TripOptions {
        start_hour: 17.0,
        ..Default::default()
    });
    let mut jam = trip
        .zones
        .iter()
        .find(|z| z.reason == "heavy traffic")
        .unwrap()
        .clone();
    assert!(trip.zone_is_active(&mut jam));
    let (limit, reason) = trip.speed_limit_at((jam.start_mi + jam.end_mi) / 2.0);
    assert_eq!(reason.as_deref(), Some("heavy traffic"));
    assert!(limit < 55.0);
    // The same spot at 3 AM is open road at the corridor limit.
    let mut night = synthetic_trip(TripOptions {
        start_hour: 3.0,
        ..Default::default()
    });
    let (night_limit, night_reason) = night.speed_limit_at((jam.start_mi + jam.end_mi) / 2.0);
    assert_ne!(night_reason.as_deref(), Some("heavy traffic"));
    assert!(night_limit > limit);
}

#[test]
fn test_jam_traffic_settles_at_the_zone_speed_not_the_generic_floor() {
    // Brandon, 2026-08-20: a heavy-traffic zone posting 45 dropped the truck
    // to 25 and held it there. Braking traffic in a zone settles at the
    // zone's number, so the keeper's target does too.
    // 1 PM puts the synthetic jam in the light band: prevailing exactly 45.
    let mut trip = synthetic_trip(TripOptions {
        start_hour: 13.0,
        ..Default::default()
    });
    let mut jam = trip
        .zones
        .iter()
        .find(|z| z.reason == "heavy traffic")
        .unwrap()
        .clone();
    assert!(trip.zone_is_active(&mut jam));
    assert!(approx(jam.limit_mph, 45.0));
    trip.traffic_manager.vehicles = Vec::new();
    trip.traffic_manager.rolling_bubble = false;
    trip.position_mi = jam.start_mi + 0.1;
    trip.check_zones(); // entering the live jam injects the queue
    let lead = trip
        .traffic_manager
        .vehicles
        .iter()
        .find(|v| v.key.starts_with("congestion:") && v.intent == "braking")
        .cloned()
        .expect("an injected braking lead");
    // The trap this pins: the generic floor sits under the zone's number.
    let floor = trip
        .traffic_manager
        .floor_speed(trip.traffic_manager.posted_limit_at(lead.position_mi));
    assert!(floor < jam.limit_mph);
    trip.update(0.01); // publishes the braking zones, pace included
                       // Ride just behind the lead long enough for the old ratchet to have
                       // reached its floor; time_scale zero freezes positions so the gap holds.
    for _ in 0..8 {
        trip.traffic_manager
            .update(1.0, lead.position_mi - 0.5, 0.0, None, None);
    }
    let lead_now = trip
        .traffic_manager
        .vehicles
        .iter()
        .find(|v| v.key == lead.key)
        .expect("the lead stays in the bubble");
    assert!(approx(lead_now.target_speed_mph, jam.limit_mph));
}

#[test]
fn test_entering_a_live_jam_fills_it_with_slow_traffic() {
    let mut trip = synthetic_trip(TripOptions {
        start_hour: 17.0,
        ..Default::default()
    });
    let jam = trip
        .zones
        .iter()
        .find(|z| z.reason == "heavy traffic")
        .unwrap()
        .clone();
    trip.traffic_manager.vehicles = Vec::new();
    trip.position_mi = jam.start_mi + 0.1;
    trip.check_zones();
    let injected: Vec<_> = trip
        .traffic_manager
        .vehicles
        .iter()
        .filter(|v| v.key.starts_with("congestion:"))
        .cloned()
        .collect();
    assert!(injected.len() >= 3);
    let lanes: std::collections::HashSet<i64> = injected.iter().map(|v| v.lane).collect();
    assert_eq!(lanes, [0, 1].into_iter().collect()); // both lanes are full of metal
    assert!(injected.iter().all(|v| v.speed_mph <= jam.limit_mph + 5.0));
    // Re-entering does not stack duplicates.
    trip.entered_zone = None;
    trip.check_zones();
    let again = trip
        .traffic_manager
        .vehicles
        .iter()
        .filter(|v| v.key.starts_with("congestion:"))
        .count();
    assert_eq!(again, injected.len());
}

// -- Baked HPMS profiles override the heuristic ---------------------------------------

#[test]
fn test_baked_leg_profile_wins_over_the_heuristic() {
    let cached = first_route_option(world(), "Chicago", "Indianapolis");
    let leg = with_corridor(&cached.legs[0], |d| {
        d.traffic_volumes = vec![sample(0.0, 150000.0, 4), sample(60.0, 18000.0, 2)];
    });
    assert_eq!(leg_aadt_at(&leg, 10.0), Some((150000.0, 4)));
    assert_eq!(leg_aadt_at(&leg, 90.0), Some((18000.0, 2)));

    let route = replace_leg(&cached, 0, leg);
    let mut truck = TruckState::default();
    truck.transmission.automatic = true;
    let trip = Trip::new(
        route,
        truck,
        weather("great_lakes", 1),
        TripOptions {
            seed: Some(2),
            world: Some(world()),
            ..Default::default()
        },
    );
    assert_eq!(trip.route_aadt_at(10.0), (150000.0, 4));
}

#[test]
fn test_unbaked_leg_reads_none() {
    let leg = Leg::new("A", "B", 100.0, "I-99", "flat", Vec::new());
    assert!(leg_aadt_at(&leg, 10.0).is_none());
}

#[test]
#[ignore = "data::world_parsing owns _parse_traffic_volumes; covered by the data tests"]
fn test_traffic_volume_parser_orders_and_validates() {}

#[test]
fn test_baked_lanes_feed_the_lane_count() {
    let unbaked = Leg::new("A", "B", 100.0, "I-99", "flat", Vec::new());
    assert_eq!(leg_lane_count(Some(&unbaked)), 2);
    let mut baked = unbaked.clone();
    baked.lanes = 3;
    assert_eq!(leg_lane_count(Some(&baked)), 3);
}
