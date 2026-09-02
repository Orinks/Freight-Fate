//! Hours of service at the terminal: the bunk room, and the dispatch board's
//! warning about a load your current shift cannot legally cover.
//!
//! These are the `tests/test_hos.py` cases that drive `CityMenuState` and
//! `JobBoardState`. They spent the port as `#[ignore]`d stubs in
//! `crates/ff-core/src/sim/hos/tests.rs`, where they could never run:
//! `ff-core` cannot depend on the game crate, so neither screen is visible
//! from there.

use crate::states_city_support::*;
use ff_core::models::career::LEVEL_XP;
use ff_core::models::jobs::{Job, JobBoard, OfferOptions};
use ff_core::models::profile::Profile;
use ff_core::sim::hos::limits;
use freight_fate::app::testing::TestApp;
use freight_fate::states::base::{Key, Menu};
use freight_fate::states::city::{CityMenuState, JobBoardState};
use freight_fate::states::city_pickup::PickupFacilityState;

fn approx(a: f64, b: f64) -> bool {
    (a - b).abs() <= 1e-6 * b.abs().max(1.0)
}

/// `job_with_supported_route(world, city, level, jobs)`.
///
/// An offered `city` job at `level` whose route the world really supports.
/// Endorsement cargo is skipped: an unendorsed test career would be refused
/// for the endorsement, not for the hours these cases are about.
fn job_with_supported_route(app: &TestApp, city: &str, level: i64, jobs: &[Job]) -> Job {
    let acceptable = |job: &Job| {
        job.cargo.credentials.is_empty()
            && matches!(
                app.ctx
                    .world
                    .supported_route(&job.origin, &job.destination, None),
                Ok(Some(_))
            )
    };
    if let Some(job) = jobs.iter().find(|job| acceptable(job)) {
        return job.clone();
    }
    // A shifted job draw (which happens as the map grows) must not make this
    // StopIteration: the case needs a genuine acceptable job, not one seed's.
    for seed in 0..200 {
        let mut board = JobBoard::seeded(app.ctx.world, seed);
        let offers = board.offers(city, &[] as &[&str], OfferOptions::level(level));
        if let Some(job) = offers.iter().find(|job| acceptable(job)) {
            return job.clone();
        }
    }
    panic!("no offered {city} job with a supported route under any seed");
}

/// `JobBoard(ctx.world, seed=2).offers("Austin", set(), level=2)`.
fn austin_offers(app: &TestApp) -> Vec<Job> {
    let mut board = JobBoard::seeded(app.ctx.world, 2);
    board.offers("Austin", &[] as &[&str], OfferOptions::level(2))
}

// -- the terminal bunk room ------------------------------------------------------------

#[test]
fn test_city_sleep_resets_hours_and_advances_the_clock() {
    // A spent duty window used to follow you into the city with no way to
    // sleep it off short of driving (illegally) to a rest stop.
    let mut app = TestApp::new();
    career(&mut app, "Bunk Room", "Austin");
    let city = CityMenuState::new(&app.ctx, false);
    app.push_state(city);

    let before = {
        let p = profile_mut(&mut app);
        p.hos.drive(660.0); // a fully spent shift
        p.fatigue = 75.0;
        p.game_hours
    };

    select::<CityMenuState>(&mut app, "Sleep 10 hours");

    let p = profile(&app);
    assert!(approx(p.game_hours, before + 10.0), "{}", p.game_hours);
    assert_eq!(p.hos.driving_min, 0.0);
    assert_eq!(p.hos.duty_min, 0.0);
    assert_eq!(p.fatigue, 0.0);
}

#[test]
fn test_city_sleep_when_already_rested_needs_a_second_enter() {
    // Pressing Enter on Sleep right after a reset used to quietly burn another
    // 10 hours; a rested driver now gets a warning first.
    let mut app = TestApp::new();
    app.ctx.profile = Some(Profile::named_in("Rested", "Austin"));
    let city = CityMenuState::new(&app.ctx, false);
    app.push_state(city);
    let before = profile(&app).game_hours;

    select::<CityMenuState>(&mut app, "Sleep 10 hours"); // first Enter: warning only
    assert_eq!(profile(&app).game_hours, before);
    key(&mut app, Key::Return); // confirm
    assert!(approx(profile(&app).game_hours, before + 10.0));

    // Rested again after sleeping: the next Enter warns again, and moving off
    // the item cancels the pending confirmation.
    select::<CityMenuState>(&mut app, "Sleep 10 hours");
    assert!(approx(profile(&app).game_hours, before + 10.0));
    key(&mut app, Key::Down);
    key(&mut app, Key::Up);
    key(&mut app, Key::Return);
    assert!(
        approx(profile(&app).game_hours, before + 10.0),
        "warned, not slept"
    );

    // A tired driver sleeps on the first press, as before.
    {
        let p = profile_mut(&mut app);
        p.hos.drive(300.0);
        p.fatigue = 40.0;
    }
    key(&mut app, Key::Return);
    assert!(approx(profile(&app).game_hours, before + 20.0));
    assert_eq!(profile(&app).fatigue, 0.0);
}

// -- the dispatch board's hours warning --------------------------------------------------

#[test]
fn test_dispatch_warns_before_accepting_job_that_exceeds_current_hos() {
    let mut app = TestApp::new();
    app.record_audio();
    app.ctx.profile = Some(Profile::named_in("HOS Dispatch", "Austin"));
    app.ctx.settings.hos_mode = "realistic".to_string();
    let drive_limit = limits("realistic").expect("realistic has limits").0;
    profile_mut(&mut app).hos.drive(drive_limit - 30.0);
    let jobs = austin_offers(&app);
    let job = job_with_supported_route(&app, "Austin", 2, &jobs);
    let mut board = JobBoardState::new(&app.ctx, vec![job]);

    app.clear_speech();
    board.accept(&mut app.ctx, 0);
    app.ctx.run_deferred();

    assert!(
        app.main_lines()
            .last()
            .is_some_and(|line| line.contains("Hours warning")),
        "{:?}",
        app.main_lines()
    );
    assert!(profile(&app).active_trip.is_none());

    board.accept(&mut app.ctx, 0);
    app.ctx.run_deferred();

    assert!(profile(&app).active_trip.is_some());
}

#[test]
fn test_dispatch_board_warns_when_all_generated_jobs_exceed_current_hos() {
    let mut app = TestApp::new();
    app.record_audio();
    let mut p = Profile::named_in("All Risky", "Austin");
    p.career.xp = LEVEL_XP[7]; // senior: browsable board
    app.ctx.profile = Some(p);
    app.ctx.settings.hos_mode = "realistic".to_string();
    let drive_limit = limits("realistic").expect("realistic has limits").0;
    profile_mut(&mut app).hos.drive(drive_limit - 10.0);
    let jobs: Vec<Job> = austin_offers(&app).into_iter().take(5).collect();
    assert_eq!(jobs.len(), 5);
    let mut board = JobBoardState::new(&app.ctx, jobs.clone());

    app.clear_speech();
    Menu::announce_entry(&mut board, &mut app.ctx);
    app.ctx.run_deferred();

    assert!(
        app.main_lines()
            .iter()
            .any(|line| line.contains("every listed dispatch would need an extra legal rest")),
        "{:?}",
        app.main_lines()
    );
    for index in 0..jobs.len() {
        app.clear_speech();
        board.accept(&mut app.ctx, index);
        app.ctx.run_deferred();
        assert!(
            app.main_lines()
                .last()
                .is_some_and(|line| line.contains("Hours warning")),
            "job {index}: {:?}",
            app.main_lines()
        );
        assert!(profile(&app).active_trip.is_none());
    }

    board.accept(&mut app.ctx, jobs.len() - 1);
    app.ctx.run_deferred();

    assert!(profile(&app).active_trip.is_some());
}

#[test]
fn test_dispatch_does_not_warn_after_hours_reset() {
    // A full 10-hour reset must clear the dispatch hours warning, even for
    // multi-day runs: the route's own sleeps are budgeted into the deadline,
    // so only hours already spent this shift are worth warning about.
    let mut app = TestApp::new();
    app.record_audio();
    app.ctx.profile = Some(Profile::named_in("Rested", "Austin"));
    app.ctx.settings.hos_mode = "realistic".to_string();
    {
        let p = profile_mut(&mut app);
        p.hos.drive(600.0); // a nearly spent shift...
        p.hos.sleep(); // ...wiped by the 10-hour reset
    }
    let jobs: Vec<Job> = austin_offers(&app).into_iter().take(5).collect();
    let mut board = JobBoardState::new(&app.ctx, jobs.clone());

    app.clear_speech();
    Menu::announce_entry(&mut board, &mut app.ctx);
    app.ctx.run_deferred();

    assert!(
        !app.main_lines()
            .last()
            .is_some_and(|line| line.contains("extra legal rest")),
        "{:?}",
        app.main_lines()
    );

    let job = job_with_supported_route(&app, "Austin", 2, &jobs);
    let index = jobs
        .iter()
        .position(|listed| listed.destination == job.destination)
        .unwrap_or(0);
    app.clear_speech();
    board.accept(&mut app.ctx, index);
    app.ctx.run_deferred();

    assert!(
        !app.main_lines()
            .last()
            .is_some_and(|line| line.contains("Hours warning")),
        "{:?}",
        app.main_lines()
    );
    assert!(profile(&app).active_trip.is_some());
}

// -- a load staged at the home yard ----------------------------------------------------

#[test]
fn test_a_load_staged_at_the_home_yard_opens_the_pickup_without_a_deadhead() {
    // The home terminal is a facility in the city's own list, so dispatch
    // can hand out a load that ships from it -- and the first agent
    // playtest (2026-09-02) then drove a two-mile "deadhead from the
    // terminal to the terminal" on every assigned load. The shipping office
    // is a walk across the yard: the pickup opens here.
    let mut app = TestApp::new();
    app.record_audio();
    app.ctx.profile = Some(Profile::named_in("Yard Load", "Austin"));
    let terminal = app
        .ctx
        .world
        .home_terminal("Austin")
        .expect("Austin has a yard");
    let jobs = austin_offers(&app);
    let mut job = job_with_supported_route(&app, "Austin", 2, &jobs);
    job.origin_location = terminal.name.clone();
    let mut board = JobBoardState::new(&app.ctx, vec![job]);

    app.clear_speech();
    board.accept(&mut app.ctx, 0);
    app.ctx.run_deferred();

    let top = app.ctx.state().expect("a state");
    assert!(
        top.borrow().as_any().is::<PickupFacilityState>(),
        "the shipping office, not a drive to it"
    );
    assert!(
        profile(&app)
            .active_trip
            .as_ref()
            .is_some_and(|trip| trip["kind"] == "pickup"),
        "a save resumes at the pickup"
    );
    let said = app.main_lines().join(" ");
    assert!(said.contains("staged here in the yard"), "{said}");
    assert!(!said.contains("Deadhead"), "{said}");
}
