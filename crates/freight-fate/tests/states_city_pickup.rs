//! The pickup facility and route planning: the city-side ports of
//! `tests/test_pickup_loading.py`.
//!
//! The Python fixtures drove the deadhead to the shipper first; that drive
//! is the driving port's, so these build the pickup screen the arrival
//! would have built and pin what happens on it.

mod states_city_support;

use ff_core::models::business::LEASED_OWNER_OPERATOR;
use ff_core::models::jobs::{cargo_type, Job};
use ff_core::models::trailer_yard::{
    preloaded_trailer, DROP_HOOK_MIN, LIVE_LOAD_MIN, TRAILER_SWAP_MIN,
};
use freight_fate::app::testing::TestApp;
use freight_fate::states::base::{Key, TimedMessageState};
use freight_fate::states::city::CityMenuState;
use freight_fate::states::city_pickup::{
    job_origin_exists, pickup_snapshot, PickupFacilityState, PickupOptions, PickupSnapshotOptions,
    RouteSelectState,
};
use states_city_support::*;

/// A dispatch out of a facility that stages loaded trailers.
fn drop_yard_job(facility_id: &str, distance_mi: f64) -> Job {
    let mut job = Job::new(
        cargo_type("general").unwrap(),
        12.0,
        "Chicago",
        "Chicago Cross-Dock",
        "Milwaukee",
        distance_mi,
        1800.0,
        9.0,
    );
    job.origin_type = "cross_dock".to_string(); // a shipper that stages trailers
    job.origin_facility_id = facility_id.to_string();
    job
}

/// Search the deterministic yard for a job whose preloaded trailer does (or
/// does not) fail a walk-around. The condition is derived from the facility
/// and the run, so this picks a real one instead of patching the model.
fn job_with_trailer(defective: bool) -> Job {
    for i in 0..400 {
        let job = drop_yard_job(&format!("chicago-cross-dock-{i}"), 90.0 + i as f64);
        if let Some(trailer) = preloaded_trailer(&job) {
            if trailer.defect().is_some() == defective {
                return job;
            }
        }
    }
    panic!("no seeded drop yard produced a {defective} trailer");
}

fn push_pickup(app: &mut TestApp, job: Job, opts: PickupOptions) {
    let pickup = PickupFacilityState::new(&app.ctx, job, opts);
    app.push_state(pickup);
}

/// A checked-in, loaded pickup holding a trailer of a chosen condition
/// (`_pickup_with_trailer`).
fn pickup_with_trailer(app: &mut TestApp, defective: bool) -> Job {
    let job = job_with_trailer(defective);
    career(app, "Walker", "Chicago");
    push_pickup(
        app,
        job.clone(),
        PickupOptions {
            ..PickupOptions::default()
        },
    );
    key(app, Key::Return); // check in
    key(app, Key::Return); // drop and hook
    finish_timed_state(app);
    job
}

// -- the pickup screen itself ---------------------------------------------------------

#[test]
fn test_pickup_facility_walks_check_in_then_loading() {
    // The spine of the Python fixture, minus the drive that reaches it: the
    // first row is the check-in, the second the dock, and the clock and the
    // duty log move with each.
    let mut app = TestApp::new();
    career(&mut app, "Shipper Visit", "Chicago");
    let mut job = drop_yard_job("chicago-live-load", 92.0);
    job.origin_type = "mine_quarry".to_string(); // a shipper that loads at a dock
    push_pickup(&mut app, job, PickupOptions::default());

    assert_eq!(
        current_label::<PickupFacilityState>(&app),
        "Check in at shipping office"
    );
    key(&mut app, Key::Return);
    assert!(with_state::<PickupFacilityState, _>(&app, |p, _| p.checked_in));
    assert_eq!(
        current_label::<PickupFacilityState>(&app),
        "Load cargo at dock"
    );

    let hours_before = profile(&app).game_hours;
    let duty_before = profile(&app).hos.duty_min;
    key(&mut app, Key::Return);
    assert!(is::<TimedMessageState>(&app));
    finish_timed_state(&mut app);

    assert!(with_state::<PickupFacilityState, _>(&app, |p, _| p.loaded));
    assert!(profile(&app).game_hours > hours_before);
    assert!(profile(&app).hos.duty_min > duty_before);
    assert_eq!(
        current_label::<PickupFacilityState>(&app),
        "Depart for destination"
    );
}

#[test]
fn test_loading_at_pickup_uses_dock_sound() {
    let mut app = TestApp::new();
    career(&mut app, "Dock Sound", "Chicago");
    let mut job = drop_yard_job("chicago-live-load", 92.0);
    // This test is about the dock, so pin the pickup to a shipper that
    // loads at one: a drop yard would hand over a preloaded trailer and
    // never open a door (see tests/test_trailer_yard.py).
    job.origin_type = "mine_quarry".to_string();
    push_pickup(&mut app, job, PickupOptions::default());
    let played = app.record_audio();

    key(&mut app, Key::Return); // check in
    let plan = with_state::<PickupFacilityState, _>(&app, |p, ctx| p.pickup_plan(ctx));
    assert!(!plan.is_drop_hook());
    let hours_before = profile(&app).game_hours;
    let duty_before = profile(&app).hos.duty_min;
    key(&mut app, Key::Return); // load cargo
    assert_eq!(app.visible_lines()[0], "Loading cargo");
    finish_timed_state(&mut app);

    let keys: Vec<String> = played
        .borrow()
        .played
        .iter()
        .map(|(key, _, _)| key.clone())
        .collect();
    assert!(keys.iter().any(|k| k == "poi/dock_and_deliver"));
    assert!(keys.iter().any(|k| k == "ui/level_up"));
    assert_eq!(profile(&app).game_hours, hours_before + plan.minutes / 60.0);
    assert_eq!(profile(&app).hos.duty_min, duty_before + plan.minutes);
}

#[test]
fn test_drop_and_hook_gets_the_truck_out_in_a_fraction_of_the_time() {
    // A preloaded trailer means no dock and no hour standing at one.
    let mut app = TestApp::new();
    career(&mut app, "Drop Hook", "Chicago");
    let job = job_with_trailer(false);
    push_pickup(&mut app, job, PickupOptions::default());
    key(&mut app, Key::Return); // check in
    let plan = with_state::<PickupFacilityState, _>(&app, |p, ctx| p.pickup_plan(ctx));
    assert!(plan.is_drop_hook());
    assert_eq!(plan.minutes, DROP_HOOK_MIN);
    assert!(DROP_HOOK_MIN < LIVE_LOAD_MIN);
    // Check-in already says there is no dock coming.
    let said = app.main_lines().last().cloned().unwrap();
    assert!(said.contains("drop yard"));
    assert!(said.contains(&plan.trailer.as_ref().unwrap().number));

    let hours_before = profile(&app).game_hours;
    key(&mut app, Key::Return); // drop and hook
    assert_eq!(app.visible_lines()[0], "Hooking the loaded trailer");
    finish_timed_state(&mut app);

    assert_eq!(
        profile(&app).game_hours,
        hours_before + DROP_HOOK_MIN / 60.0
    );
    assert!(profile(&app).hos.duty_min > 0.0);
    // The driver is told which trailer they are pulling and what shape it
    // is in -- the whole risk of hooking somebody else's box.
    let lines = app.main_lines();
    let readout = lines[lines.len().saturating_sub(3)..].join(" ");
    assert!(readout.contains(&plan.trailer.as_ref().unwrap().number));
    assert!(readout.to_lowercase().contains("hooked to"));
}

// -- the walk-around, and refusing a trailer ---------------------------------------

#[test]
fn test_a_clean_trailer_walks_around_clean() {
    let mut app = TestApp::new();
    let job = pickup_with_trailer(&mut app, false);
    assert!(preloaded_trailer(&job).unwrap().defect().is_none());
    select::<PickupFacilityState>(&mut app, "Walk around the trailer");
    assert!(app.main_lines().last().unwrap().contains("checks out"));
    // Nothing to refuse, so no refusal offered.
    assert!(!labels::<PickupFacilityState>(&app)
        .iter()
        .any(|t| t == "Refuse this trailer"));
}

#[test]
fn test_walking_a_bad_trailer_finds_it_and_offers_the_refusal() {
    // The defect is something the driver goes and finds, not something that
    // happens to them at a scale house.
    let mut app = TestApp::new();
    let job = pickup_with_trailer(&mut app, true);
    let unit = preloaded_trailer(&job).unwrap();
    let defect = unit.defect().expect("a defective trailer");
    assert!(!labels::<PickupFacilityState>(&app)
        .iter()
        .any(|t| t == "Refuse this trailer"));

    select::<PickupFacilityState>(&mut app, "Walk around the trailer");
    let said = app.main_lines().last().cloned().unwrap();
    assert!(said.contains(defect));
    assert!(said.contains(&unit.number));
    // Only once the driver has actually looked does refusing become an option.
    assert!(labels::<PickupFacilityState>(&app)
        .iter()
        .any(|t| t == "Refuse this trailer"));
}

#[test]
fn test_refusing_a_trailer_costs_time_and_gets_a_sound_one() {
    let mut app = TestApp::new();
    let job = pickup_with_trailer(&mut app, true);
    let unit = preloaded_trailer(&job).unwrap();
    select::<PickupFacilityState>(&mut app, "Walk around the trailer");
    let hours_before = profile(&app).game_hours;

    select::<PickupFacilityState>(&mut app, "Refuse this trailer");

    assert_eq!(
        profile(&app).game_hours,
        hours_before + TRAILER_SWAP_MIN / 60.0
    );
    let hooked = with_state::<PickupFacilityState, _>(&app, |p, ctx| p.hooked_trailer(ctx))
        .expect("a hooked trailer");
    assert!(hooked.defect().is_none());
    assert_ne!(hooked.number, unit.number);
    assert!(app
        .main_lines()
        .last()
        .unwrap()
        .contains("yard brings another"));
    // Walking it again reports the sound one, not the box that went back.
    select::<PickupFacilityState>(&mut app, "Walk around the trailer");
    assert!(app.main_lines().last().unwrap().contains("checks out"));
}

// -- saving and resuming the pickup objective ------------------------------------------

#[test]
fn test_pickup_arrival_state_and_loaded_planning_resume() {
    // The Python round-tripped through the main menu's Continue; the part
    // the pickup screen owns is the snapshot it writes and rebuilds from.
    let mut app = TestApp::new();
    career(&mut app, "Resume Pickup", "Chicago");
    let mut job = drop_yard_job("chicago-live-load", 92.0);
    job.origin_type = "mine_quarry".to_string();
    push_pickup(&mut app, job.clone(), PickupOptions::default());
    key(&mut app, Key::Return); // check in

    let snapshot = profile(&app)
        .active_trip
        .clone()
        .expect("a saved objective");
    assert_eq!(snapshot["kind"], "pickup");
    assert_eq!(snapshot["checked_in"], true);
    assert_eq!(snapshot["loaded"], false);
    let resumed = PickupFacilityState::from_snapshot(&app.ctx, &snapshot).expect("it rebuilds");
    assert!(resumed.checked_in);
    assert!(!resumed.loaded);
    app.pop_state();
    app.push_state(resumed);

    key(&mut app, Key::Return); // load
    finish_timed_state(&mut app);
    assert!(with_state::<PickupFacilityState, _>(&app, |p, _| p.loaded));
    assert_eq!(profile(&app).active_trip.as_ref().unwrap()["loaded"], true);

    let snapshot = profile(&app).active_trip.clone().unwrap();
    let resumed = PickupFacilityState::from_snapshot(&app.ctx, &snapshot).expect("it rebuilds");
    assert!(resumed.loaded);
    app.pop_state();
    app.push_state(resumed);
    assert_eq!(
        current_label::<PickupFacilityState>(&app),
        "Depart for destination"
    );
}

#[test]
fn test_pickup_save_and_departure_keep_speed_control_session() {
    let mut app = TestApp::new();
    career(&mut app, "Speed Session", "Chicago");
    let mut job = drop_yard_job("chicago-live-load", 92.0);
    job.origin_type = "mine_quarry".to_string();
    push_pickup(
        &mut app,
        job,
        PickupOptions {
            speed_control_armed: true,
            speed_control_target_mph: Some(47.0),
            announce_speed_control_status: true,
            ..PickupOptions::default()
        },
    );

    assert!(with_state::<PickupFacilityState, _>(&app, |p, _| p.speed_control_armed));
    assert!(app.main_lines().iter().any(|line| line
        .contains("Automatic speed control is paused; open-road target 47 miles per hour")));

    with_state_mut::<PickupFacilityState, _>(&mut app, |p, ctx| p.status(ctx));
    assert!(app
        .main_lines()
        .last()
        .unwrap()
        .contains("open-road target 47 miles per hour"));

    key(&mut app, Key::Return); // check in
    let snapshot = profile(&app).active_trip.clone().unwrap();
    assert_eq!(snapshot["speed_control_armed"], true);
    assert_eq!(snapshot["speed_control_target_mph"], 47.0);
    let resumed = PickupFacilityState::from_snapshot(&app.ctx, &snapshot).expect("it rebuilds");
    assert!(resumed.speed_control_armed);
    assert_eq!(resumed.speed_control_target_mph, Some(47.0));
}

#[test]
fn test_cancelling_the_pickup_returns_to_the_terminal() {
    let mut app = TestApp::new();
    career(&mut app, "Cancel Pickup", "Chicago");
    let job = drop_yard_job("chicago-live-load", 92.0);
    push_pickup(&mut app, job, PickupOptions::default());

    select::<PickupFacilityState>(&mut app, "Cancel pickup and return to terminal");

    assert!(is::<CityMenuState>(&app));
    assert!(profile(&app).active_trip.is_none());
    assert!(profile(&app).dispatch_board_cache.is_none());
}

// -- route planning ---------------------------------------------------------------------

#[test]
fn test_owner_operator_route_menu_lists_routes_and_starts_one() {
    let mut app = TestApp::new();
    career(&mut app, "Route Picker", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
    }
    let job = Job::new(
        cargo_type("general").unwrap(),
        12.0,
        "Chicago",
        "Chicago yard",
        "Milwaukee",
        92.0,
        1800.0,
        9.0,
    );
    let pickup = loaded_pickup(&app, job);
    app.push_state(pickup);
    key(&mut app, Key::Return); // depart

    assert!(is::<RouteSelectState>(&app));
    let rows = labels::<RouteSelectState>(&app);
    assert!(rows[0].starts_with("Route 1:"));
    assert!(rows[0].contains("Fuel-capable stops:"));
    assert_eq!(rows.last().unwrap(), "Back to pickup facility");
    // W speaks a forecast rather than moving the cursor.
    let index_before = index::<RouteSelectState>(&app);
    app.clear_speech();
    key(&mut app, Key::W);
    assert_eq!(index::<RouteSelectState>(&app), index_before);
    assert!(app
        .main_lines()
        .last()
        .unwrap()
        .starts_with("Forecast along the route."));

    key(&mut app, Key::Home);
    key(&mut app, Key::Return);
    assert!(is_placeholder(&app, "Driving"));
    assert!(app
        .main_lines()
        .iter()
        .any(|line| line.contains("Navigation set for")));
}

// -- the stale-facility guard ------------------------------------------------------------

#[test]
fn test_job_origin_exists_reads_the_current_world() {
    let app = TestApp::new();
    let world = app.ctx.world;
    let mut job = Job::new(
        cargo_type("general").unwrap(),
        12.0,
        "Chicago",
        "Chicago Retired Facility",
        "Milwaukee",
        92.0,
        1800.0,
        7.0,
    );
    assert!(!job_origin_exists(&job, world));
    job.bobtail = true; // a reposition's origin is a synthetic company yard
    assert!(job_origin_exists(&job, world));
}

#[test]
fn test_pickup_snapshot_carries_the_resume_fields() {
    let job = drop_yard_job("chicago-live-load", 92.0);
    let snapshot = pickup_snapshot(
        &job,
        &PickupSnapshotOptions {
            checked_in: true,
            loaded: true,
            speed_control_armed: true,
            speed_control_target_mph: Some(52.0),
            trailer_refused: true,
            ..PickupSnapshotOptions::default()
        },
    );
    assert_eq!(snapshot["kind"], "pickup");
    assert_eq!(snapshot["checked_in"], true);
    assert_eq!(snapshot["loaded"], true);
    assert_eq!(snapshot["trailer_refused"], true);
    assert_eq!(snapshot["speed_control_target_mph"], 52.0);
    assert!(snapshot.contains_key("job"));
}

// -- what still needs the drive ----------------------------------------------------------

#[test]
#[ignore = "needs states::driving (the deadhead that reaches the shipper)"]
fn test_accepting_job_starts_drivable_pickup_leg() {}

#[test]
#[ignore = "needs states::driving (the approach and its stop gate)"]
fn test_pickup_facility_waits_for_full_stop() {}

#[test]
#[ignore = "needs states::driving (engine settling on arrival)"]
fn test_pickup_arrival_settles_the_engine_to_idle() {}

#[test]
#[ignore = "needs states::driving (PauseMenuState)"]
fn test_quit_during_pickup_drive_resumes_from_the_last_stop() {}

#[test]
#[ignore = "needs states::driving (the loaded drive that keeps the idle)"]
fn test_departing_loaded_trip_keeps_idling_engine() {}

#[test]
#[ignore = "needs states::driving (the trailer the scale house finds)"]
fn test_a_refused_trailer_does_not_follow_the_driver_onto_the_road() {}

#[test]
#[ignore = "needs states::driving (the inspector's write-up)"]
fn test_an_unrefused_defect_is_what_the_inspector_finds() {}

#[test]
#[ignore = "needs states::driving (speed control at the gate)"]
fn test_speed_control_stays_paused_until_departure() {}

#[test]
#[ignore = "needs states::driving (speed control at the gate)"]
fn test_arming_by_hand_at_the_gate_still_works() {}
