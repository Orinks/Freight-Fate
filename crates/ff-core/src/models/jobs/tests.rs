//! Ported from the jobs half of `tests/test_models.py`, `tests/test_job_progression.py`,
//! the job cases of `tests/test_business_arc.py` / `tests/test_dispatch_job_detail.py`
//! and the board cases of `tests/test_playtest_levers.py`. The app-shell cases are
//! ignored with the reason and their bodies say what they checked.

use super::*;
use crate::data::world::{get_world, World};
use crate::data::world_models::{CorridorDetail, Leg, Route, SpeedLimitSample};
use crate::sim::hos::HosClock;

const NONE: &[&str] = &[];
const ALL: &[&str] = &["refrigerated", "heavy_haul", "high_value"];

fn world() -> &'static World {
    get_world()
}

fn board(seed: i64) -> JobBoard<'static> {
    JobBoard::seeded(world(), seed)
}

fn offers(seed: i64, city: &str, endorsements: &[&str], level: i64) -> Vec<Job> {
    board(seed).offers(city, endorsements, OfferOptions::level(level))
}

fn route_miles(job: &Job) -> Option<f64> {
    world()
        .supported_route(&job.origin, &job.destination, None)
        .ok()
        .flatten()
        .map(|r| r.miles())
}

fn supported(job: &Job) -> Option<Route> {
    world()
        .supported_route(&job.origin, &job.destination, None)
        .ok()
        .flatten()
}

fn required(job: &Job) -> f64 {
    let route = supported(job);
    required_hours(job.distance_mi, route.as_ref(), Some(world()), None)
}

fn general() -> &'static CargoType {
    cargo_type("general").unwrap()
}

// -- tests/test_models.py: jobs ---------------------------------------------------

#[test]
fn test_job_offers_have_real_route_distances() {
    let jobs = offers(3, "Chicago", NONE, 2);
    assert!(!jobs.is_empty());
    for job in &jobs {
        let miles = route_miles(job).expect("a supported route");
        assert!((miles - job.distance_mi).abs() < 1.0);
        assert!(job.pay > 0.0);
        assert!(job.deadline_game_h > job.distance_mi / 70.0);
    }
}

#[test]
fn test_deadlines_allow_legal_driving() {
    // A deadline must cover the driving at an achievable average plus the
    // HOS breaks and sleep the distance demands - no impossible 5-hour
    // San Antonio to Dallas dispatches.
    for (seed, level) in [(1, 1), (2, 3), (3, 6)] {
        for job in offers(seed, "San Antonio", NONE, level) {
            let needed = required(&job);
            assert!(
                job.deadline_game_h >= needed * 1.2,
                "{} to {}: {} mi needs {} h, deadline {} h",
                job.origin,
                job.destination,
                fmt_f(job.distance_mi, 0),
                fmt_f(needed, 1),
                fmt_f(job.deadline_game_h, 1)
            );
        }
    }
}

#[test]
fn test_required_hours_includes_breaks_and_sleep() {
    assert!(required_hours(275.0, None, None, None) < 6.0); // SA-Dallas: just driving
    let medium = required_hours(495.0, None, None, None); // 9 driving hours: one break
    assert!(medium > 495.0 / 55.0);
    let long_haul = required_hours(1150.0, None, None, None); // ~21 h driving: sleep required
    assert!(long_haul > 1150.0 / 55.0 + 10.0);
}

#[test]
fn test_hos_plan_reports_breaks_sleeps_and_route_stop_coverage() {
    let route = world()
        .supported_route("Chicago", "Indianapolis", None)
        .unwrap()
        .unwrap();
    let plan = plan_hos(route.miles(), Some(&route), Some(world()), None);
    assert!(plan.drive_h > route.miles() / 70.0);
    assert!(plan.break_stop_count >= 1);
    assert!(plan.summary().contains("Legal HOS plan"));
}

#[test]
fn test_northeast_short_corridor_deadline_uses_direct_route() {
    // Search seeds: map expansion (new nearby NJ/PA nodes) shifts any single
    // seed's offer mix, so pin the route invariant, not one seed's lottery.
    let ny_jobs: Vec<Job> = (0..40)
        .flat_map(|seed| offers(seed, "Philadelphia", NONE, 1))
        .filter(|job| job.destination == "new_york_ny_us")
        .collect();

    assert!(!ny_jobs.is_empty());
    assert!(ny_jobs.iter().all(|job| job.distance_mi == 107.0));
    assert!(ny_jobs
        .iter()
        .all(|job| (3.0..=5.0).contains(&job.deadline_game_h)));
    assert!(ny_jobs
        .iter()
        .all(|job| job.deadline_game_h >= required(job) * 1.2));
}

fn one_leg_route(highway: &str, mph: f64) -> Route {
    let leg = Leg::new("A", "B", 100.0, highway, "flat", Vec::new()).with_detail(CorridorDetail {
        speed_limits: vec![SpeedLimitSample {
            at_mi: 0.0,
            mph: Some(mph),
            source: "test".to_string(),
            hgv: false,
        }],
        ..Default::default()
    });
    Route::from_legs(vec!["A".to_string(), "B".to_string()], vec![leg])
}

#[test]
fn test_route_aware_deadline_estimate_uses_low_speed_segments() {
    let route = one_leg_route("US 1", 35.0);
    assert!(route_drive_hours(Some(&route), 0.0, None) > 100.0 / 55.0);
    assert!(
        required_hours(100.0, Some(&route), None, None) > required_hours(100.0, None, None, None)
    );
}

#[test]
fn test_route_deadline_uses_baked_limit_near_city() {
    let route = one_leg_route("I-1", 75.0);
    assert_eq!(
        route_planning_limit(
            &route,
            0,
            &route.legs[0],
            1.0,
            1.0,
            &[0.0, 100.0],
            false,
            None
        ),
        75.0 * DEADLINE_PLANNING_SPEED_FACTOR
    );
}

/// Every generated job's deadline must cover the honest HOS time (driving at
/// the planning pace plus mandatory breaks and 10-hour sleeps). This is the
/// achievability invariant the deadline formula guarantees; the test guards it
/// across the whole expanded network and all levels, including the corrected
/// ORS mileages.
#[test]
fn test_deadlines_cover_required_hos_time_across_the_network() {
    // Bounded, deterministic sample of origins rather than every city: this
    // scans city x seed x generated jobs and grew with the map; the
    // deadline-vs-HOS check is a formula invariant, so ~96 diverse origins
    // exercise the distance/route range without an O(cities) scan.
    let all_cities = world().city_names();
    let stride = (all_cities.len() / 96).max(1);
    for city in all_cities.iter().step_by(stride) {
        for seed in 0..3 {
            let jobs = board(seed).offers(
                city,
                ALL,
                OfferOptions {
                    count: 5,
                    level: 5,
                    ..Default::default()
                },
            );
            for job in jobs {
                assert!(
                    job.deadline_game_h >= required(&job),
                    "{city} -> {} ({} mi)",
                    job.destination,
                    job.distance_mi
                );
            }
        }
    }
}

#[test]
fn test_endorsement_gating() {
    let no_endorsements = board(4).offers(
        "Los Angeles",
        NONE,
        OfferOptions {
            count: 5,
            ..Default::default()
        },
    );
    let locked = no_endorsements
        .iter()
        .filter(|j| j.cargo.endorsement.is_some())
        .count();
    // at most the single "teaser" job may require an endorsement
    assert!(locked <= 1);
}

#[test]
fn test_payout_on_time_window_beats_late() {
    let job = Job::new(general(), 15.0, "A", "Loc", "B", 300.0, 700.0, 9.0);
    let early = job.payout_default(5.0, 0.0);
    let on_dot = job.payout_default(9.0, 0.0);
    let late = job.payout_default(12.0, 0.0);
    // Window model: any on-time arrival earns the same flat bonus; racing in
    // early pays no more than hitting the appointment.
    assert_eq!(early, on_dot);
    assert!(on_dot > 700.0 && 700.0 > late);
    assert!(late >= 700.0 * 0.4);
}

#[test]
fn test_payout_punishes_fragile_damage() {
    let fragile = Job::new(
        cargo_type("electronics").unwrap(),
        8.0,
        "A",
        "Loc",
        "B",
        300.0,
        1000.0,
        9.0,
    );
    let tough = Job::new(
        cargo_type("bulk").unwrap(),
        8.0,
        "A",
        "Loc",
        "B",
        300.0,
        1000.0,
        9.0,
    );
    assert!(fragile.payout_default(5.0, 30.0) < tough.payout_default(5.0, 30.0));
}

/// Dispatch offers name places a player may never have heard of; the state
/// must always ride along ("McCall, Idaho"), not only when two cities share a
/// name (player request).
#[test]
fn test_job_spoken_names_always_carry_the_state() {
    let jobs = offers(5, "Chicago", NONE, 2);
    assert!(!jobs.is_empty());
    for job in &jobs {
        let origin_city = world().city(&job.origin).unwrap();
        let dest_city = world().city(&job.destination).unwrap();
        assert_eq!(job.spoken_origin(), origin_city.spoken_qualified());
        assert_eq!(job.spoken_destination(), dest_city.spoken_qualified());
        if !origin_city.state.is_empty() {
            assert!(job.spoken_origin().contains(&origin_city.state));
        }
        if !dest_city.state.is_empty() {
            assert!(job.spoken_destination().contains(&dest_city.state));
        }
    }
}

/// A load accepted mid-shift gets its mandatory sleep in the deadline.
///
/// Owner catch 2026-07-24: deadlines assumed a fresh clock, so a one-shift
/// load accepted six hours into a shift promised a delivery nobody could
/// legally make (the mid-trip 10-hour sleep ate it).
#[test]
fn test_deadline_plans_around_hours_already_on_the_clock() {
    let miles = 495.0; // ~9 driving hours: one shift for a fresh driver
    let fresh = plan_hos(miles, None, None, None);
    assert_eq!(fresh.sleeps, 0);

    let used = HosClock {
        driving_min: 6.0 * 60.0,
        duty_min: 7.0 * 60.0,
        since_break_min: 2.0 * 60.0,
        ..HosClock::new()
    };
    let mid_shift = plan_hos(miles, None, None, Some(&used));
    assert_eq!(mid_shift.sleeps, 1);

    let fresh_deadline = dispatch_deadline_hours(miles, 1.2, None, None, None);
    let tired_deadline = dispatch_deadline_hours(miles, 1.2, None, None, Some(&used));
    assert!(tired_deadline >= fresh_deadline + 10.0);
}

#[test]
fn test_fresh_clock_plans_are_unchanged_by_the_clock_parameter() {
    for miles in [110.0, 495.0, 1150.0] {
        assert_eq!(
            plan_hos(miles, None, None, Some(&HosClock::new())),
            plan_hos(miles, None, None, None)
        );
    }
}

#[test]
fn test_burned_duty_window_forces_the_sleep_even_with_drive_hours_left() {
    // 13 hours of window gone with only 3 driven: the 14-hour wall, not the
    // 11-hour driving cap, is what forces the reset.
    let window_burned = HosClock {
        driving_min: 3.0 * 60.0,
        duty_min: 13.0 * 60.0,
        ..HosClock::new()
    };
    let plan = plan_hos(495.0, None, None, Some(&window_burned));
    assert_eq!(plan.sleeps, 1);
}

#[test]
fn test_board_speaks_the_rest_the_deadline_covers() {
    let mut job = Job::new(general(), 15.0, "A", "Loc", "B", 300.0, 700.0, 24.0);
    job.deadline_covers_rest = true;
    assert!(job.describe_plain().contains("10-hour rest"));
    let plain = Job::new(general(), 15.0, "A", "Loc", "B", 300.0, 700.0, 9.0);
    assert!(!plain.describe_plain().contains("10-hour rest"));
}

// -- tests/test_job_progression.py -----------------------------------------------

#[test]
fn test_level_one_offers_are_short_regional_hops() {
    // Rookie reach is gated by the distance cap and proximity weighting, not by
    // leg count: jobs stay regional and lean short, but the board offers variety
    // (it is no longer locked to one back-and-forth destination).
    for city in ["Atlanta", "Philadelphia", "Chicago"] {
        let cap = level_distance_cap(1).unwrap();
        let mut near = 0usize;
        let mut total = 0usize;
        let mut destinations: std::collections::BTreeSet<String> = Default::default();
        for seed in 0..20 {
            let jobs = offers(seed, city, NONE, 1);
            assert!(!jobs.is_empty());
            for job in jobs {
                total += 1;
                assert!(job.distance_mi <= cap); // within the regional cap
                near += usize::from(job.distance_mi <= cap * 0.6); // proximity favors near cities
                destinations.insert(job.destination);
            }
        }
        assert!(near as f64 / total as f64 >= 0.5, "{city}"); // predominantly short hauls
        assert!(destinations.len() >= 3, "{city}"); // variety, not one repeated route
    }
}

#[test]
fn test_level_one_and_two_stay_within_the_regional_cap() {
    // The distance cap keeps rookie work regional; leg count no longer gates it.
    for seed in 0..10 {
        for level in [1, 2] {
            let cap = level_distance_cap(level).unwrap();
            for job in offers(seed, "Atlanta", NONE, level) {
                assert!(supported(&job).is_some());
                assert!(job.distance_mi <= cap);
            }
        }
    }
}

#[test]
fn test_higher_level_reaches_farther_destinations() {
    // Level 2's larger cap lets it take jobs to cities level 1 cannot reach.
    let max_distance = |level: i64| -> f64 {
        (0..40)
            .flat_map(|seed| offers(seed, "Milwaukee", NONE, level))
            .map(|job| job.distance_mi)
            .fold(0.0, f64::max)
    };
    assert!(max_distance(2) > max_distance(1));
}

#[test]
#[ignore = "needs app shell (DrivingState / ArrivalState)"]
fn test_bobtail_relocates_to_a_nearby_city_without_pay() {
    // A Denver -> Cheyenne reposition is a bobtail with no pay; the arrival
    // relocates the profile to cheyenne_wy_us, pays nothing, counts no
    // delivery, and its summary names Cheyenne. The job half holds here:
    let job = make_reposition_job(world(), "Denver", "Cheyenne", false, None).unwrap();
    assert!(job.bobtail && job.pay == 0.0);
    assert_eq!(job.destination, "cheyenne_wy_us");
}

#[test]
#[ignore = "needs app shell (ArrivalState settlement)"]
fn test_bobtail_settlement_collects_fines_carried_over() {}

#[test]
#[ignore = "needs app shell (DrivingState._update_hours_and_fatigue)"]
fn test_bobtail_personal_conveyance_records_off_duty_hos_time() {}

#[test]
fn test_distance_cap_tops_out_at_a_real_coast_to_coast_run() {
    // haul length keeps progressing deep into the company arc...
    assert!(JobBoard::distance_cap(10) < JobBoard::distance_cap(15));
    // ...but never outgrows the longest supported U.S. corridor
    assert_eq!(JobBoard::distance_cap(20), MAX_DISPATCH_DISTANCE_MI);
    assert_eq!(JobBoard::distance_cap(30), MAX_DISPATCH_DISTANCE_MI);
}

#[test]
fn test_distance_cap_rises_with_level() {
    let caps: Vec<f64> = (1..9).map(JobBoard::distance_cap).collect();
    assert!(caps.windows(2).all(|w| w[0] <= w[1]));
    assert!(caps[0] <= 300.0);
    assert!(JobBoard::distance_cap(5) >= 1000.0);

    // the cap is honored by actual offers
    for seed in 0..10 {
        for job in offers(seed, "Chicago", NONE, 5) {
            assert!(job.distance_mi <= JobBoard::distance_cap(5));
        }
    }
}

#[test]
fn test_long_hauls_unlock_around_level_five() {
    let longest = |level: i64| -> f64 {
        (0..30)
            .flat_map(|seed| offers(seed, "Phoenix", NONE, level))
            .map(|job| job.distance_mi)
            .fold(0.0, f64::max)
    };
    assert!(longest(1) < LONG_HAUL_MILES);
    assert!(longest(5) >= LONG_HAUL_MILES);
}

#[test]
fn test_destination_weighting_prefers_near_cities() {
    // Milwaukee is 92 miles from Chicago; New York is ~880. Even at a high
    // level with everything in range, near cities must come up far more often.
    let mut near = 0;
    let mut far = 0;
    for seed in 0..60 {
        for job in offers(seed, "Chicago", NONE, 6) {
            near += i32::from(job.destination == "milwaukee_wi_us");
            far += i32::from(job.destination == "new_york_ny_us");
        }
    }
    assert!(near > far);
}

#[test]
fn test_board_never_offers_a_haul_below_the_minimum() {
    // Cities stand for whole freight areas, so trivial across-town hops are not
    // offered as dispatches, no matter how close two cities sit on the map.
    for city in [
        "New York",
        "Philadelphia",
        "Los Angeles",
        "Dallas",
        "Norfolk",
    ] {
        for seed in 0..20 {
            for level in [1, 6] {
                for job in offers(seed, city, NONE, level) {
                    assert!(
                        job.distance_mi >= MIN_JOB_DISTANCE_MI,
                        "{} -> {} is only {} mi",
                        job.origin,
                        job.destination,
                        fmt_f(job.distance_mi, 0)
                    );
                }
            }
        }
    }
}

#[test]
fn test_close_neighbors_are_not_dispatched() {
    // The nearest neighbor sits under the minimum, so it must never be offered,
    // yet the board still fills from farther destinations.
    for (city, too_close) in [("Norfolk", "Virginia Beach"), ("Bridgeport", "New Haven")] {
        for seed in 0..30 {
            let jobs = offers(seed, city, NONE, 1);
            assert!(!jobs.is_empty());
            assert!(jobs.iter().all(|job| job.destination != too_close));
        }
    }
}

#[test]
fn test_remote_terminal_still_gets_a_full_board() {
    // Salt Lake City's nearest neighbor is beyond the level-1 cap; the board
    // must fall back to the nearest cities instead of coming up empty.
    let jobs = offers(7, "Salt Lake City", NONE, 1);
    assert!(!jobs.is_empty());
    assert!(jobs.iter().all(|job| job.distance_mi <= 600.0));
}

#[test]
fn test_short_hauls_still_pay_for_fuel() {
    // ~6 mpg at roughly $4/gallon is ~$0.67 per mile; rookie jobs must clear
    // that with room for repairs and profit.
    for seed in 0..10 {
        for job in offers(seed, "Atlanta", NONE, 1) {
            assert!(job.pay >= job.distance_mi * 1.5);
        }
    }
}

#[test]
fn test_rookie_boards_have_rewarding_minimum_pay() {
    for city in [
        "Chicago",
        "Atlanta",
        "Philadelphia",
        "San Antonio",
        "Los Angeles",
    ] {
        for seed in 0..15 {
            for job in offers(seed, city, NONE, 1) {
                // pay is rounded to cents, so compare against the floor to cents
                assert!(job.pay >= round_py_n(minimum_pay_for_level(job.distance_mi, 1), 2));
            }
        }
    }
}

#[test]
fn test_long_haul_boards_have_rewarding_minimum_pay() {
    let long_jobs: Vec<Job> = ["Chicago", "Atlanta", "Dallas", "Los Angeles"]
        .iter()
        .flat_map(|city| (0..30).flat_map(move |seed| offers(seed, city, ALL, 5)))
        .filter(|job| job.distance_mi >= 600.0)
        .collect();

    assert!(!long_jobs.is_empty());
    for job in long_jobs {
        assert!(job.pay / job.distance_mi >= 5.25);
    }
}

#[test]
fn test_short_haul_premium_tapers_instead_of_cliffing() {
    // The old flat $700-1050 floors paid a 50-mile hop ~$23 a mile -- four to
    // five times any long haul, at every level -- so grinding short hops was
    // strictly optimal. The guaranteed rate must decline gently with distance
    // and the shortest hops must stay within about twice the long-haul rate.
    for level in [1, 3, 5, 12] {
        let rates: Vec<f64> = [50.0, 100.0, 200.0, 300.0, 500.0, 599.0]
            .iter()
            .map(|miles| minimum_pay_for_level(*miles, level) / miles)
            .collect();
        assert!(rates.windows(2).all(|w| w[0] >= w[1]), "{rates:?}");
        assert!(rates[0] <= 2.0 * 5.25); // short premium, not a jackpot
    }
}

#[test]
fn test_representative_boards_use_truck_plausible_locations() {
    for city in [
        "Chicago",
        "Atlanta",
        "Philadelphia",
        "San Antonio",
        "Los Angeles",
    ] {
        let jobs = offers(3, city, NONE, 2);
        assert!(!jobs.is_empty());
        let locations = &world().city(city).unwrap().locations;
        assert!(jobs
            .iter()
            .all(|job| locations.iter().any(|loc| job.origin_location == loc.name)));
        assert!(jobs.iter().all(|job| !job.origin_facility_id.is_empty()));
    }
}

#[test]
fn test_facility_type_filters_available_cargo() {
    for seed in 0..40 {
        for job in offers(seed, "Chicago", ALL, 4) {
            let allowed = facility_cargo(&job.origin_type).expect("a known facility type");
            assert!(allowed.contains(&job.cargo.key));
        }
    }
}

#[test]
fn test_jobs_match_shipper_and_receiver_roles() {
    for city in ["Chicago", "Fresno", "Houston", "Memphis", "Detroit"] {
        for seed in 0..12 {
            let jobs = offers(seed, city, ALL, 5);
            assert!(!jobs.is_empty());
            for job in jobs {
                let origin = world()
                    .facility_location(&job.origin, &job.origin_facility_id)
                    .unwrap();
                let destination = world()
                    .facility_location(&job.destination, &job.destination_facility_id)
                    .unwrap();
                assert!(origin.ships.iter().any(|k| k == job.cargo.key));
                assert!(destination.receives.iter().any(|k| k == job.cargo.key));
                let text = job.describe_plain();
                assert!(text.contains(&origin.name));
                assert!(text.contains(&destination.name));
            }
        }
    }
}

#[test]
fn test_regional_specialization_shapes_generated_freight() {
    let cargo_of = |city: &str| -> std::collections::BTreeSet<&'static str> {
        (0..25)
            .flat_map(|seed| offers(seed, city, ALL, 5))
            .map(|job| job.cargo.key)
            .collect()
    };
    let chicago_cargo = cargo_of("Chicago");
    let fresno_cargo = cargo_of("Fresno");
    let houston_types: std::collections::BTreeSet<String> = (0..25)
        .flat_map(|seed| offers(seed, "Houston", ALL, 5))
        .map(|job| job.origin_type)
        .collect();

    assert!(chicago_cargo.contains("container") || chicago_cargo.contains("parcel"));
    assert!(
        fresno_cargo.contains("grain")
            || fresno_cargo.contains("food")
            || fresno_cargo.contains("refrigerated")
    );
    assert!(houston_types.contains("chemical_petroleum_terminal"));
}

#[test]
fn test_higher_levels_unlock_more_facility_and_cargo_variety() {
    let low_jobs: Vec<Job> = (0..20)
        .flat_map(|seed| offers(seed, "Chicago", NONE, 1))
        .collect();
    let high_jobs: Vec<Job> = (0..20)
        .flat_map(|seed| offers(seed, "Chicago", ALL, 5))
        .collect();

    assert!(!low_jobs.is_empty() && !high_jobs.is_empty());
    let cargo_kinds = |jobs: &[Job]| {
        jobs.iter()
            .map(|j| j.cargo.key)
            .collect::<std::collections::BTreeSet<_>>()
            .len()
    };
    let type_kinds = |jobs: &[Job]| {
        jobs.iter()
            .map(|j| j.origin_type.clone())
            .collect::<std::collections::BTreeSet<_>>()
            .len()
    };
    assert!(cargo_kinds(&high_jobs) > cargo_kinds(&low_jobs));
    assert!(type_kinds(&high_jobs) > type_kinds(&low_jobs));
    assert!(high_jobs
        .iter()
        .any(|job| job.cargo.min_level > 1 || job.cargo.endorsement.is_some()));
}

#[test]
fn test_jobs_carry_destination_facility_metadata() {
    let jobs = offers(8, "Los Angeles", ALL, 5);
    assert!(!jobs.is_empty());
    for job in jobs {
        assert!(!job.destination_location.is_empty());
        assert!(!job.destination_type.is_empty());
        assert!(world().cities[&job.destination]
            .locations
            .iter()
            .any(|loc| loc.name == job.destination_location));
        let text = job.describe_plain();
        assert!(text.contains(&job.origin_location));
        assert!(text.contains(&job.destination_location));
    }
}

#[test]
fn test_job_offer_avoids_repeating_facility_type_in_generated_names() {
    let mut job = Job::new(
        general(),
        12.0,
        "South Bend",
        "South Bend Grocery Distribution Center",
        "Fort Wayne",
        85.0,
        833.0,
        4.0,
    );
    job.origin_type = "grocery_retail_dc".to_string();
    job.destination_location = "Fort Wayne Dry Warehouse".to_string();
    job.destination_type = "dry_warehouse".to_string();

    let text = job.describe_numbered(1, 5);

    assert!(text.contains("from South Bend Grocery Distribution Center in South Bend"));
    assert!(text.contains("to Fort Wayne Dry Warehouse in Fort Wayne"));
    assert!(!text.contains("grocery and retail distribution center South Bend"));
    assert!(!text.contains("dry warehouse Fort Wayne Dry Warehouse"));
}

#[test]
fn test_representative_stops_are_real_world_grounded() {
    let expected = [
        (("Atlanta", "Birmingham"), "Pilot Travel Center Lincoln"),
        (("Memphis", "Little Rock"), "Forrest City I-40 Rest Area"),
        (("San Antonio", "Dallas"), "Road Ranger Waco"),
        (
            ("Los Angeles", "San Diego"),
            "San Onofre Safety Roadside Rest Area",
        ),
        (("Des Moines", "Chicago"), "Iowa 80 Truckstop"),
        (("Houston", "Dallas"), "Pilot Travel Center Huntsville"),
        (("Los Angeles", "Fresno"), "Pilot Travel Center Bakersfield"),
        (("Fresno", "Sacramento"), "Flying J Travel Center Ripon"),
    ];
    for ((start, end), stop_name) in expected {
        let route = world()
            .shortest_route(start, end, None, false)
            .unwrap()
            .unwrap();
        assert!(
            route.stops().iter().any(|s| s == stop_name),
            "{start}-{end}"
        );
    }
}

#[test]
fn test_new_dispatches_only_use_metadata_supported_routes() {
    for city in [
        "Chicago",
        "Atlanta",
        "Philadelphia",
        "San Antonio",
        "Los Angeles",
    ] {
        for seed in 0..12 {
            for job in offers(seed, city, NONE, 6) {
                let route = supported(&job).expect("a supported route");
                assert!(route.metadata_complete(world()));
            }
        }
    }
}

#[test]
fn test_whole_board_never_offers_unsupported_route_legs() {
    // Spot-check board generation across a bounded, deterministic sample of
    // origin cities (x4 seeds) rather than every city.
    let all_cities = world().city_names();
    let stride = (all_cities.len() / 96).max(1);
    let mut routes: std::collections::HashMap<(String, String), Option<Route>> = Default::default();
    for city in all_cities.iter().step_by(stride) {
        for seed in 0..4 {
            for job in offers(seed, city, ALL, 6) {
                let key = (job.origin.clone(), job.destination.clone());
                let route = routes
                    .entry(key)
                    .or_insert_with(|| supported(&job))
                    .clone()
                    .unwrap_or_else(|| panic!("{} to {}", job.origin, job.destination));
                assert!(
                    route.metadata_complete(world()),
                    "{} to {}",
                    job.origin,
                    job.destination
                );
                assert!(route
                    .legs
                    .iter()
                    .all(|leg| world().leg_metadata_complete(leg)));
                assert!(route.stop_details().iter().all(|stop| stop.curated()));
            }
        }
    }
}

#[test]
fn test_former_legacy_routes_are_now_metadata_supported_for_dispatch() {
    let route = world()
        .supported_route("Chicago", "St. Louis", None)
        .unwrap()
        .unwrap();
    assert!(route.metadata_complete(world()));
    let jobs = offers(9, "Chicago", NONE, 6);
    assert!(!jobs.is_empty());
    assert!(jobs.iter().all(|job| supported(job).is_some()));
}

#[test]
fn test_former_placeholder_only_routes_are_metadata_supported() {
    let route = world()
        .supported_route("Memphis", "Nashville", None)
        .unwrap()
        .unwrap();
    assert!(route.metadata_complete(world()));
    assert!(route.stop_details().iter().all(|stop| stop.curated()));

    let supported_route = world()
        .supported_route("Memphis", "Little Rock", None)
        .unwrap()
        .unwrap();
    assert!(supported_route.metadata_complete(world()));

    let jobs = offers(4, "Memphis", NONE, 1);
    assert!(!jobs.is_empty());
    assert!(jobs.iter().all(|job| supported(job).is_some()));
}

// -- tests/test_business_arc.py: the job half -----------------------------------

#[test]
fn test_company_driver_dispatch_uses_carrier_trailer_support() {
    let job = Job::new(
        cargo_type("refrigerated").unwrap(),
        10.0,
        "Chicago",
        "cold storage",
        "Milwaukee",
        92.0,
        1200.0,
        5.0,
    );

    assert_eq!(job.locked_reason(&["refrigerated"], 4, None, true), "");
    assert!(job
        .locked_reason(
            &["refrigerated"],
            4,
            Some(crate::models::trailers::DEFAULT_TRAILER_PROGRAMS),
            false
        )
        .contains("Requires Reefer trailer program"));
}

#[test]
fn test_direct_freight_board_pays_more_and_uses_direct_label() {
    let base = board(44).offers("Chicago", ALL, OfferOptions::level(25));
    let direct = board(44).offers(
        "Chicago",
        ALL,
        OfferOptions {
            level: 25,
            direct_freight: true,
            ..Default::default()
        },
    );
    assert!(!base.is_empty());
    assert!(!direct.is_empty());
    assert!(direct[0].pay > base[0].pay);
    // The JobBoardState half ("Direct gross" on the board rows) needs the
    // app shell.
}

// -- tests/test_playtest_levers.py: the board half ------------------------------

#[test]
fn test_offer_to_builds_job_to_forced_destination() {
    let job = board(7)
        .offer_to(
            "denver_co_us",
            "silverthorne_co_us",
            NONE,
            OfferOptions::default(),
        )
        .expect("a forced offer");
    assert_eq!(
        world().resolve_city_key(&job.destination),
        "silverthorne_co_us"
    );
    assert!(job.distance_mi > 0.0);
    assert!(job.pay > 0.0);
}

#[test]
fn test_offer_to_unknown_destination_returns_none() {
    assert!(board(7)
        .offer_to("denver_co_us", "atlantis", NONE, OfferOptions::default())
        .is_none());
}

#[test]
#[ignore = "needs app shell (states::city._add_forced_board_job)"]
fn test_forced_board_job_lands_on_the_board() {}

#[test]
#[ignore = "needs app shell (states::city._add_forced_board_job)"]
fn test_forced_board_job_skips_when_already_offered() {}

#[test]
#[ignore = "needs app shell (states::city.JobBoardState)"]
fn test_assigned_dispatch_hands_out_the_forced_load_first() {}

// -- tests/test_dispatch_job_detail.py ------------------------------------------

#[test]
#[ignore = "needs app shell (JobDetailState)"]
fn test_f1_on_dispatch_job_opens_structured_detail_view() {
    // The board the detail view opens on: a level-5 Buffalo deal at seed 7.
    let jobs = offers(7, "Buffalo", ALL, 5);
    assert!(!jobs.is_empty());
}

#[test]
#[ignore = "needs app shell (JobBoardState Tab)"]
fn test_tab_repeats_only_the_market_watch() {}

#[test]
#[ignore = "needs app shell (JobDetailState)"]
fn test_job_detail_lines_are_reviewable_before_accepting() {}

#[test]
#[ignore = "needs app shell (JobDetailState)"]
fn test_job_detail_exposes_review_instructions() {}

#[test]
#[ignore = "needs app shell (JobBoardState._locked_reason)"]
fn test_locked_job_detail_does_not_sound_accept_available() {}

#[test]
#[ignore = "needs app shell (JobBoardState)"]
fn test_f1_on_back_item_does_not_crash() {}

#[test]
#[ignore = "needs app shell (JobDetailState accept)"]
fn test_job_detail_accept_command_accepts_and_escape_returns() {}

// -- payload round trip -----------------------------------------------------------

#[test]
fn job_payload_round_trips_and_legacy_payloads_fill_in() {
    let mut job = Job::new(
        general(),
        12.5,
        "chicago_il_us",
        "Yard",
        "milwaukee_wi_us",
        92.0,
        800.0,
        6.0,
    );
    job.origin_spoken = "Chicago, Illinois".to_string();
    job.destination_location = "Milwaukee Cross-Dock".to_string();
    job.bobtail = true;
    let payload = job_payload(&job);
    let back = job_from_payload(&payload).unwrap();
    assert_eq!(back, job);

    let mut legacy = Map::new();
    legacy.insert("cargo".into(), Value::from("general"));
    legacy.insert("weight_tons".into(), Value::from(10));
    legacy.insert("origin".into(), Value::from("Chicago"));
    legacy.insert("destination".into(), Value::from("Milwaukee"));
    legacy.insert("distance_mi".into(), Value::from(92.0));
    legacy.insert("pay".into(), Value::from(800.0));
    legacy.insert("deadline_game_h".into(), Value::from(6.0));
    let old = job_from_payload(&legacy).unwrap();
    assert_eq!(old.origin_location, "Chicago freight market");
    assert_eq!(old.origin_type, "metro_market");
    assert_eq!(old.describe_plain().split(' ').next(), Some("10"));
    assert!(old
        .origin_facility_text()
        .starts_with("the Chicago metro freight market"));
    let mut cityless = legacy.clone();
    cityless.remove("origin");
    assert!(job_from_payload(&cityless).is_none());
}

#[test]
fn make_reposition_job_pays_assigned_empty_miles_only() {
    let bobtail = make_reposition_job(world(), "Denver", "Cheyenne", false, None).unwrap();
    assert!(bobtail.bobtail && !bobtail.assigned);
    assert_eq!(bobtail.pay, 0.0);
    assert_eq!(bobtail.origin_spoken, "Denver, Colorado");
    let assigned = make_reposition_job(world(), "Denver", "Cheyenne", true, None).unwrap();
    assert!(assigned.assigned);
    assert!(assigned.pay > 0.0);
    assert!(make_reposition_job(world(), "Denver", "atlantis", false, None).is_none());
    assert_eq!(board_offer_count(1), 5);
    assert_eq!(board_offer_count(12), 8);
    assert_eq!(lane_key(world(), &bobtail), "denver_co_us:cheyenne_wy_us");
}
