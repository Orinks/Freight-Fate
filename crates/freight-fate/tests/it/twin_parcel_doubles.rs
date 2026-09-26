//! Sets of doubles at the hook, at the wheel and on the scale: the second
//! hook-up and longer walk-around, the refused reverse, and the gross cap
//! with both trailers and the converter dolly.

use crate::states_city_support::*;
use ff_core::data::world::get_world;
use ff_core::models::doubles::{
    doubles_hook_text, DOUBLES_NO_REVERSE_TEXT, DOUBLES_SECOND_HOOK_MIN,
    DOUBLES_WALK_AROUND_EXTRA_MIN,
};
use ff_core::models::jobs::{cargo_type, Job, CARGO_CATALOG};
use ff_core::models::profile::Profile;
use ff_core::models::trailer_yard::LIVE_LOAD_MIN;
use ff_core::sim::transmission::REVERSE;
use ff_core::sim::vehicle::KG_PER_TON;
use freight_fate::app::testing::TestApp;
use freight_fate::states::base::Key;
use freight_fate::states::city_pickup::{PickupFacilityState, PickupOptions};
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::{DRIVE_PHASE_DELIVERY, WALK_AROUND_MIN};
use freight_fate::states::driving_rest_states::walk_around_minutes;

fn drive(
    app: &mut TestApp,
    cargo: &str,
    origin: &str,
    destination: &str,
    tons: f64,
) -> DrivingState {
    let world = get_world();
    app.ctx.profile = Some(Profile::named_in("Doubles", origin));
    let route = world
        .supported_route(origin, destination, None)
        .expect("the world routes")
        .expect("the corridor is supported");
    let job = Job::new(
        &CARGO_CATALOG[cargo],
        tons,
        origin,
        "company yard",
        destination,
        route.miles(),
        1000.0,
        12.0,
    );
    let mut drive = DrivingState::new(&mut app.ctx, job, route, None, DRIVE_PHASE_DELIVERY, None);
    drive.trip.set_npc_vehicles(Vec::new());
    drive
}

#[test]
fn a_set_of_doubles_takes_two_hook_ups_and_a_longer_walk_around_at_the_shipper() {
    let mut app = TestApp::new();
    career(&mut app, "Pup Hook", "Chicago");
    let mut job = Job::new(
        cargo_type("parcel_doubles").unwrap(),
        10.0,
        "Chicago",
        "Chicago Cross-Dock",
        "Milwaukee",
        92.0,
        1800.0,
        9.0,
    );
    job.origin_type = "mine_quarry".to_string(); // loads at a dock
    let pickup = PickupFacilityState::new(&app.ctx, job, PickupOptions::default());
    app.push_state(pickup);

    key(&mut app, Key::Return); // check in
    let said = app.main_lines().last().cloned().unwrap();
    let hook = doubles_hook_text("parcel_doubles");
    assert!(!hook.is_empty());
    assert!(
        said.contains(&hook),
        "check-in must speak the doubles time: {said}"
    );
    assert!(
        app.visible_lines()
            .iter()
            .any(|l| l.starts_with("Doubles: two hook-ups")),
        "the doubles time must be on screen too"
    );

    let plan = with_state::<PickupFacilityState, _>(&app, |p, ctx| p.pickup_plan(ctx));
    let extra = DOUBLES_SECOND_HOOK_MIN + DOUBLES_WALK_AROUND_EXTRA_MIN;
    assert_eq!(plan.minutes, LIVE_LOAD_MIN + extra);
    let hours_before = profile(&app).game_hours;
    let duty_before = profile(&app).hos.duty_min;
    key(&mut app, Key::Return); // load
    finish_timed_state(&mut app);
    assert_eq!(profile(&app).game_hours, hours_before + plan.minutes / 60.0);
    assert_eq!(profile(&app).hos.duty_min, duty_before + plan.minutes);
}

#[test]
fn a_single_trailer_pickup_says_nothing_about_doubles() {
    assert!(doubles_hook_text("general").is_empty());
}

#[test]
fn reverse_is_refused_and_spoken_with_doubles_hooked() {
    let mut app = TestApp::new();
    let mut d = drive(&mut app, "parcel_doubles", "Buffalo", "Rochester", 10.0);
    assert!(d.trip.truck.doubles_hooked());
    let damage = d.trip.truck.damage_pct;
    let gear = d.trip.truck.transmission.gear;
    d.manual_shift(&mut app.ctx, REVERSE);
    assert_eq!(d.trip.truck.transmission.gear, gear);
    assert_eq!(d.trip.truck.damage_pct, damage, "a refusal breaks nothing");
    assert_eq!(app.main_lines().last().unwrap(), DOUBLES_NO_REVERSE_TEXT);

    // A single trailer is not refused.
    let mut single = drive(&mut app, "general", "Buffalo", "Rochester", 10.0);
    assert!(!single.trip.truck.doubles_hooked());
    single.manual_shift(&mut app.ctx, REVERSE);
    assert_ne!(app.main_lines().last().unwrap(), DOUBLES_NO_REVERSE_TEXT);
}

#[test]
fn the_walk_around_on_the_road_covers_both_trailers_and_the_dolly() {
    let mut app = TestApp::new();
    let d = drive(&mut app, "parcel_doubles", "Buffalo", "Rochester", 10.0);
    assert_eq!(
        walk_around_minutes(&d),
        WALK_AROUND_MIN + DOUBLES_WALK_AROUND_EXTRA_MIN
    );
    let single = drive(&mut app, "general", "Buffalo", "Rochester", 10.0);
    assert_eq!(walk_around_minutes(&single), WALK_AROUND_MIN);
}

#[test]
fn a_turnpike_double_runs_under_its_turnpike_cap_and_pups_under_eighty_thousand() {
    let mut app = TestApp::new();
    let turnpike = drive(&mut app, "turnpike_doubles", "Toledo", "Elkhart", 25.0);
    let set = &turnpike.trip.truck.trailer_set;
    assert_eq!(set.units, 2);
    assert_eq!(set.legal_gvw_lb().round(), 127_400.0);
    assert!(!turnpike.trip.truck.is_over_legal_gvw());
    let ticket = turnpike.trip.truck.scale_ticket_text();
    assert!(
        ticket.contains("both trailers and the converter dolly"),
        "{ticket}"
    );
    assert!(ticket.contains("127,400"), "{ticket}");

    let pups = drive(&mut app, "parcel_doubles", "Buffalo", "Rochester", 10.0);
    assert_eq!(pups.trip.truck.trailer_set.legal_gvw_lb().round(), 80_000.0);
    // The same pups loaded past what 80,000 lb leaves after both trailers
    // and the dolly read overweight.
    let mut heavy = drive(&mut app, "parcel_doubles", "Buffalo", "Rochester", 10.0);
    heavy.trip.truck.cargo_kg = 30.0 * KG_PER_TON;
    assert!(heavy.trip.truck.is_over_legal_gvw());
}
