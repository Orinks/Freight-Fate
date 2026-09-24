//! Rigging for the badge moment tests.
//!
//! `test_every_badge_is_awarded_somewhere_or_named_as_retired` proves a badge
//! is reachable; these prove it lands at the right moment. Each test puts one
//! career one step short of the badge, takes that step through the real code
//! path (a delivery settled by `ArrivalState`, a trip event handled by the
//! drive, a menu row selected), and checks the badge is not held; then takes
//! the step that meets the condition and checks it is.
#![allow(dead_code)]

use ff_core::data::world::get_world;
use ff_core::data::world_models::{City, Route};
use ff_core::models::jobs::{CargoType, Job, CARGO_CATALOG};
use ff_core::models::profile::Profile;
use ff_core::sim::season::date_text;
use freight_fate::app::testing::TestApp;
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::DRIVE_PHASE_DELIVERY;
use freight_fate::states::driving_menu_states::ArrivalState;

/// A fresh headless career parked in `city`.
pub fn career_in(city: &str) -> TestApp {
    let mut app = TestApp::new();
    app.ctx.profile = Some(Profile::named_in("Badge Moments", city));
    app
}

pub fn profile(app: &mut TestApp) -> &mut Profile {
    app.ctx.profile.as_mut().expect("a career")
}

/// Whether the career holds `id`.
pub fn earned(app: &TestApp, id: &str) -> bool {
    app.ctx
        .profile
        .as_ref()
        .expect("a career")
        .achievements
        .iter()
        .any(|a| a == id)
}

/// The supported route the game would plan between two city keys.
pub fn route(origin: &str, destination: &str) -> Route {
    get_world()
        .supported_route(origin, destination, None)
        .expect("the world routes")
        .unwrap_or_else(|| panic!("no supported route {origin} to {destination}"))
}

/// A one-leg supported route into `destination` from a city next door, so
/// an arrival badge can be driven without naming a corridor that may move.
pub fn route_into(destination: &str) -> Route {
    route_into_from(destination, |_| true)
}

/// [`route_into`], from a neighbour `from` accepts: a place badge needs a
/// run that really crosses into the place, not one that starts inside it.
pub fn route_into_from(destination: &str, from: impl Fn(&City) -> bool) -> Route {
    let world = get_world();
    world
        .neighbors(destination)
        .iter()
        .filter_map(|leg| {
            let other = if leg.a == destination { &leg.b } else { &leg.a };
            if !world.city(other).is_ok_and(&from) {
                return None;
            }
            world
                .supported_route(other, destination, None)
                .ok()
                .flatten()
        })
        .next()
        .unwrap_or_else(|| panic!("no supported route into {destination}"))
}

/// The same corridor driven the other way.
pub fn reversed(route: &Route) -> Route {
    self::route(
        route.cities.last().expect("an end"),
        route.cities.first().expect("a start"),
    )
}

/// The first cargo in the catalog that needs `credential`.
pub fn cargo_needing(credential: &str) -> &'static CargoType {
    CARGO_CATALOG
        .values()
        .find(|cargo| cargo.credentials.contains(&credential))
        .unwrap_or_else(|| panic!("no cargo needs {credential}"))
}

/// A drive along `route` that has just reached the gate: general freight,
/// twelve tons, an easy deadline, the truck at the end of the road with a
/// full tank, the clock started at noon and not yet run. Tests change what
/// their badge reads before settling it.
pub fn run_on(app: &mut TestApp, route: Route) -> DrivingState {
    run_job(app, route, &CARGO_CATALOG["general"], 12.0, 1000.0)
}

/// [`run_on`] hauling `weight_tons` of `cargo` for `pay`.
pub fn run_job(
    app: &mut TestApp,
    route: Route,
    cargo: &'static CargoType,
    weight_tons: f64,
    pay: f64,
) -> DrivingState {
    let origin = route.cities.first().cloned().expect("a start");
    let destination = route.cities.last().cloned().expect("an end");
    let miles = route.miles();
    let job = Job::new(
        cargo,
        weight_tons,
        &origin,
        "company yard",
        &destination,
        miles,
        pay,
        miles / 55.0 + 12.0,
    );
    let mut drive = DrivingState::new(
        &mut app.ctx,
        job,
        route,
        Some(4),
        DRIVE_PHASE_DELIVERY,
        Some(12.0),
    );
    drive.trip.position_mi = drive.trip.total_miles();
    drive.speeding_tickets = 0;
    drive
}

pub fn run(app: &mut TestApp, origin: &str, destination: &str) -> DrivingState {
    run_on(app, route(origin, destination))
}

/// Settle the drive the way reaching the gate does.
pub fn settle(app: &mut TestApp, drive: &mut DrivingState) {
    ArrivalState::new(&mut app.ctx, drive);
}

/// One ordinary on-time delivery, start to settlement.
pub fn deliver(app: &mut TestApp, origin: &str, destination: &str) {
    let mut drive = run(app, origin, destination);
    settle(app, &mut drive);
}

/// Start the drive's clock so the truck reaches the gate at `hour` on the
/// destination's own wall clock, which is what the timed badges read.
pub fn arrive_at_local_hour(drive: &mut DrivingState, hour: f64) {
    let offset = drive.trip.local_hour() - drive.trip.current_hour();
    drive.trip.start_hour = (hour - offset - drive.trip.game_minutes / 60.0).rem_euclid(24.0);
    assert!(
        (drive.trip.local_hour() - hour).abs() < 1e-6,
        "arrival clock {} is not {hour}",
        drive.trip.local_hour()
    );
}

/// Set the career clock so this drive's settlement lands at `hour` on
/// `date` ("April 1") of the career calendar. The settlement runs the clock
/// forward by the run's own hours before any badge reads it.
pub fn arrive_on(app: &mut TestApp, drive: &DrivingState, date: &str, hour: f64) {
    let elapsed = freight_fate::states::driving_menu_states::settlement_hours(drive);
    // The second lap of the calendar, so the start of the run is never
    // before the career began.
    let arrival = (365..730)
        .map(|day| f64::from(day) * 24.0 + hour)
        .find(|hours| date_text(*hours) == date)
        .unwrap_or_else(|| panic!("{date} is on the career calendar"));
    profile(app).game_hours = arrival - elapsed;
}
