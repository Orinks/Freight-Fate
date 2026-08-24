//! Grounded congestion: HPMS volume against capacity on a commuter clock
//! (port of `tests/test_congestion.py`).

use crate::sim_support::*;
use ff_core::data::world_models::{Leg, TrafficVolumeSample};
use ff_core::pyrandom::PyRandom;
use ff_core::sim::season::{day_of_week, is_weekend};
use ff_core::sim::trip::{Trip, TripOptions};
use ff_core::sim::trip_models::{
    congestion_limit_mph, congestion_ratio, daily_volume_factor, heuristic_aadt, leg_aadt_at,
    leg_lane_count, Zone, CONGESTION_JOIN_GAP_MI, DAILY_VOLUME_CV, DAILY_VOLUME_MAX,
    DAILY_VOLUME_MIN, HOURLY_SHARE_WEEKDAY, HOURLY_SHARE_WEEKEND, URBAN_RADIUS_MI, ZONE_MIN_GAP_MI,
};
use ff_core::sim::vehicle::TruckState;

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

// -- A jam is not waiting in the same place every single run ---------------------------
//
// AADT is an annual average, so the same stretch carries a different volume
// today than it did yesterday. The scatter goes into the volume model itself,
// so an oversaturated stretch still backs up every day while a marginal one
// flows on a quiet one (port of the traffic-variety fix on the Python side).

/// A trip with TWO baked stretches: an oversaturated metro one at the start
/// that no ordinary day clears, and a marginal one at mile 25 that only forms
/// when the day runs busy.
fn two_stretch_trip(seed: i64) -> Trip {
    let cached = first_route_option(world(), "Chicago", "Indianapolis");
    let leg = with_corridor(&cached.legs[0], |d| {
        d.traffic_volumes = vec![
            sample(0.0, 150000.0, 3), // ratio 1.1 at the peak share: always
            sample(12.0, 22000.0, 2), // open road
            sample(25.0, 66000.0, 2), // ratio 0.726: only on a busy day
            sample(35.0, 22000.0, 2), // open road again
        ];
    });
    let route = replace_leg(&cached, 0, leg);
    let mut truck = TruckState::default();
    truck.transmission.automatic = true;
    Trip::new(
        route,
        truck,
        weather("great_lakes", 1),
        TripOptions {
            seed: Some(seed),
            world: Some(world()),
            ..Default::default()
        },
    )
}

fn jam_layout(trip: &Trip) -> Vec<(i64, i64)> {
    trip.zones
        .iter()
        .filter(|z| z.reason == "heavy traffic")
        .map(|z| (z.start_mi.round() as i64, z.end_mi.round() as i64))
        .collect()
}

/// The draw is CPython's `random.Random(seed ^ 0x7A4FF1C).gauss(1.0, 0.10)`,
/// pinned bit for bit against `uv run python`. A jam that appears somewhere
/// else in Rust than in Python is a divergence, not a detail.
#[test]
fn test_daily_volume_factor_is_bit_exact_with_cpython() {
    // seed, then the first three draws off that trip's traffic stream.
    let expected: &[(i64, [f64; 3])] = &[
        (
            0,
            [0.9079243479966237, 0.8917668190659458, 0.9091544904027418],
        ),
        (
            1,
            [0.8068230770843152, 0.8164245213119394, 0.9410791141254146],
        ),
        (
            2,
            [0.9720557866273104, 0.8090336839788308, 0.910669582035381],
        ),
        (3, [1.03148282982157, 0.9080880294020052, 0.926526971879262]),
        (
            7,
            [0.9528586264306961, 1.0197091502938227, 1.0463462683384708],
        ),
        (
            42,
            [1.0453137728131197, 0.9925578334681889, 1.0292672663869584],
        ),
        (
            123,
            [0.9234083386963804, 0.8950883576202954, 1.0845713500278187],
        ),
        (
            999,
            [0.9537549331180128, 1.2047929550408785, 0.9261721467739259],
        ),
        (
            2026,
            [0.9057699170823577, 1.0708124303751771, 0.9559865848427177],
        ),
        (
            -5,
            [0.8737654585257424, 0.942223795772241, 1.13769598105499],
        ),
    ];
    for (seed, draws) in expected {
        let mut rng = PyRandom::new_from_i64(seed ^ 0x7A4FF1C);
        for (i, want) in draws.iter().enumerate() {
            let got = daily_volume_factor(&mut rng);
            assert_eq!(
                got.to_bits(),
                want.to_bits(),
                "seed {seed} draw {i}: {got:?} != CPython {want:?}"
            );
        }
    }
}

#[test]
fn test_daily_volume_factor_clamps_the_tails() {
    // CPython seeds whose first gauss(1.0, 0.10) falls outside the band:
    // 906 draws 1.3213375338391706, 261 draws 0.6951622740071852.
    let mut over = PyRandom::new_from_i64(906);
    assert_eq!(daily_volume_factor(&mut over), DAILY_VOLUME_MAX);
    let mut under = PyRandom::new_from_i64(261);
    assert_eq!(daily_volume_factor(&mut under), DAILY_VOLUME_MIN);
    assert_eq!(DAILY_VOLUME_CV, 0.10);
}

#[test]
fn test_the_trip_draws_todays_volume_off_its_own_stream() {
    // One draw per trip, off `seed ^ 0x7A4FF1C`, so adding it does not move
    // where the work zones land for a given seed.
    let trip = synthetic_trip(TripOptions::default()); // seed 2
    let jam = trip
        .zones
        .iter()
        .find(|z| z.reason == "heavy traffic")
        .expect("the overloaded stretch");
    assert_eq!(jam.day_factor.to_bits(), 0.9720557866273104_f64.to_bits());
    // Every congestion zone on the run shares the one draw, and a non-traffic
    // zone is untouched by it.
    assert!(trip
        .zones
        .iter()
        .filter(|z| z.reason == "heavy traffic")
        .all(|z| z.day_factor == jam.day_factor));
    assert!(trip
        .zones
        .iter()
        .filter(|z| z.reason != "heavy traffic")
        .all(|z| z.day_factor == 1.0));
}

#[test]
fn test_the_same_seed_runs_the_same_day_twice() {
    // A run has to be consistent with itself: the factor the zone formed
    // under is the one it is judged by.
    let first = two_stretch_trip(11);
    let second = two_stretch_trip(11);
    assert_eq!(jam_layout(&first), jam_layout(&second));
    assert_eq!(
        first
            .zones
            .iter()
            .find(|z| z.reason == "heavy traffic")
            .map(|z| z.day_factor.to_bits()),
        second
            .zones
            .iter()
            .find(|z| z.reason == "heavy traffic")
            .map(|z| z.day_factor.to_bits()),
    );
}

#[test]
fn test_the_jam_layout_varies_but_the_oversaturated_stretch_always_backs_up() {
    // The whole point: not a "chance of traffic" dial. The stretch far enough
    // over the line shows up on every run; the marginal one comes and goes.
    let mut layouts: std::collections::HashSet<Vec<(i64, i64)>> = std::collections::HashSet::new();
    let mut marginal_seen = 0;
    for seed in 0..60 {
        let trip = two_stretch_trip(seed);
        let layout = jam_layout(&trip);
        assert!(
            layout.iter().any(|(s, _)| *s == 0),
            "seed {seed}: the oversaturated stretch cleared, which no ordinary day does"
        );
        if layout.iter().any(|(s, _)| *s == 25) {
            marginal_seen += 1;
        }
        layouts.insert(layout);
    }
    assert!(
        layouts.len() > 1,
        "every seed produced the same jam layout, which is the bug"
    );
    assert!(
        (1..60).contains(&marginal_seen),
        "the marginal stretch appeared on {marginal_seen} runs in 60: it should sometimes form and sometimes not"
    );
}

#[test]
fn test_two_busy_stretches_inside_the_open_road_rule_are_one_jam() {
    // DERIVED, not chosen: two busy stretches closer together than the open
    // road guaranteed between zones cannot both stand, or the driver is told
    // to get back up to speed for four miles and then to slow again.
    assert_eq!(CONGESTION_JOIN_GAP_MI, ZONE_MIN_GAP_MI);
    let cached = first_route_option(world(), "Chicago", "Indianapolis");
    // Two loaded stretches with a five-mile breather between them.
    let leg = with_corridor(&cached.legs[0], |d| {
        d.traffic_volumes = vec![
            sample(0.0, 150000.0, 3),
            sample(10.0, 22000.0, 2),
            sample(15.0, 150000.0, 3),
            sample(25.0, 22000.0, 2),
        ];
    });
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
    let jams: Vec<_> = trip
        .zones
        .iter()
        .filter(|z| z.reason == "heavy traffic")
        .collect();
    assert_eq!(
        jams.len(),
        1,
        "a five-mile breather is shorter than the guaranteed open road, so it is one jam"
    );
    assert!(jams[0].start_mi <= 1.0 && jams[0].end_mi >= 25.0);
}

#[test]
fn test_roadworks_move_aside_for_a_jam_instead_of_being_deleted() {
    // The jam's footprint is claimed BEFORE the work zones are drawn, so a
    // draw that lands in it relocates. Deleting it afterwards spent exactly
    // the part of a slow zone that is supposed to differ between runs.
    let mut with_roadworks = 0;
    for seed in 0..60 {
        let trip = synthetic_trip(TripOptions {
            seed: Some(seed),
            ..Default::default()
        });
        let jams: Vec<(f64, f64)> = trip
            .zones
            .iter()
            .filter(|z| z.reason == "heavy traffic")
            .map(|z| (z.start_mi, z.end_mi))
            .collect();
        assert!(!jams.is_empty(), "seed {seed}: the loaded stretch vanished");
        let works: Vec<&Zone> = trip
            .zones
            .iter()
            .filter(|z| z.reason == "construction")
            .collect();
        if !works.is_empty() {
            with_roadworks += 1;
        }
        for work in works {
            for (start, end) in &jams {
                assert!(
                    work.start_mi > end + ZONE_MIN_GAP_MI || work.end_mi < start - ZONE_MIN_GAP_MI,
                    "seed {seed}: roadworks at {:.1}-{:.1} sit inside the jam at {start:.1}-{end:.1}",
                    work.start_mi,
                    work.end_mi
                );
            }
        }
    }
    assert!(
        with_roadworks >= 20,
        "only {with_roadworks} runs in 60 carried roadworks at all; the check is vacuous"
    );
}

/// Twenty seeds of the two-stretch fixture, taken from `uv run python` on the
/// Python `Trip` with the identical baked profile: the jam layout, today's
/// volume factor, and where the roadworks ended up. If any of the three drifts
/// the Rust port is putting a jam somewhere Python does not.
///
/// Columns: seed | jam layout | day factor | simulated construction spans.
type JamRun = (i64, &'static [(i64, i64)], f64, &'static [&'static str]);

const CPYTHON_TWO_STRETCH: &[JamRun] = &[
    (0, &[(0, 12)], 0.9079243479966237, &["141.663-149.211"]),
    (1, &[(0, 12)], 0.8068230770843152, &[]),
    (2, &[(0, 12)], 0.9720557866273104, &["158.405-167.092"]),
    (
        3,
        &[(0, 12), (25, 35)],
        1.03148282982157,
        &["50.695-56.960"],
    ),
    (
        4,
        &[(0, 12), (25, 35)],
        1.1466253101475237,
        &["50.407-54.026"],
    ),
    (5, &[(0, 12)], 0.8737654585257424, &[]),
    (
        6,
        &[(0, 12), (25, 35)],
        1.0969212202872545,
        &["134.001-141.933"],
    ),
    (7, &[(0, 12)], 0.9528586264306961, &[]),
    (8, &[(0, 12)], 0.9690141396060761, &["49.006-57.780"]),
    (9, &[(0, 12)], 0.8238860110110311, &["84.451-89.691"]),
    (
        10,
        &[(0, 12), (25, 35)],
        1.0929467723747042,
        &["100.710-106.284"],
    ),
    (11, &[(0, 12)], 0.8179831123957315, &[]),
    (12, &[(0, 12), (25, 35)], 1.2215774837602331, &[]),
    (13, &[(0, 12)], 0.9788710147882698, &[]),
    (
        14,
        &[(0, 12), (25, 35)],
        1.0366783969350148,
        &["112.806-121.448"],
    ),
    (15, &[(0, 12)], 0.9720559111071957, &[]),
    (
        16,
        &[(0, 12), (25, 35)],
        1.1276559182784096,
        &["69.228-75.111"],
    ),
    (17, &[(0, 12)], 0.8645512406605352, &[]),
    (18, &[(0, 12)], 0.9298016721762428, &["42.190-49.158"]),
    (19, &[(0, 12)], 0.9314757691220429, &["116.569-124.278"]),
];

#[test]
fn test_jam_layouts_match_cpython_seed_for_seed() {
    for (seed, layout, factor, works) in CPYTHON_TWO_STRETCH {
        let trip = two_stretch_trip(*seed);
        assert_eq!(
            jam_layout(&trip),
            layout.to_vec(),
            "seed {seed}: jam layout"
        );
        let jam = trip
            .zones
            .iter()
            .find(|z| z.reason == "heavy traffic")
            .unwrap_or_else(|| panic!("seed {seed}: no jam at all"));
        assert_eq!(
            jam.day_factor.to_bits(),
            factor.to_bits(),
            "seed {seed}: today's volume {:?} != CPython {factor:?}",
            jam.day_factor
        );
        let placed: Vec<String> = trip
            .zones
            .iter()
            .filter(|z| z.reason == "construction")
            .map(|z| format!("{:.3}-{:.3}", z.start_mi, z.end_mi))
            .collect();
        assert_eq!(placed, works.to_vec(), "seed {seed}: roadworks");
    }
}
