//! The terminal hub and the dispatch board: ports of the app parts of
//! `tests/test_dispatch_autonomy.py`, `tests/test_dispatch_job_detail.py`,
//! `tests/test_stale_dispatch_board.py`, `tests/test_assigned_reposition.py`,
//! `tests/test_trailer_market_preview.py`, `tests/test_pay_advance.py`,
//! `tests/test_career_objectives.py`, the terminal cases of
//! `tests/test_debt_and_standing.py` and `tests/test_enforcement_record.py`,
//! and the board cases of `tests/test_career_unlocks.py`.
//!
//! Every flow that ends at the wheel now lands on the real `DrivingState`,
//! through `states::city::launch_driving`.

mod states_city_support;

use ff_core::models::business::{INDEPENDENT_AUTHORITY, LEASED_OWNER_OPERATOR};
use ff_core::models::career::LEVEL_XP;
use ff_core::models::dispatch_policy::{NEW_HIRE_DECLINE_BUDGET, SENIOR_LOAD_CHOICE_LEVEL};
use ff_core::models::economy::{PAY_ADVANCE_ELIGIBLE_BELOW, PAY_ADVANCE_LIMIT};
use ff_core::models::enforcement::{self, LAST_CHANCE_CARRIER_KEY};
use ff_core::models::jobs::{
    board_offer_count, cargo_type, job_payload, make_reposition_job, Job, JobBoard, OfferOptions,
    ASSIGNED_REPOSITION_PAY_FRACTION,
};
use ff_core::models::profile::Profile;
use ff_core::models::solvency;
use ff_core::models::start_options::pay_plan_for_key;
use freight_fate::app::testing::TestApp;
use freight_fate::states::base::{Key, Menu};
use freight_fate::states::career_setback::CareerSetbackNoticeState;
use freight_fate::states::city::{
    assigned_reposition_for_board, dispatch_cache_key, open_freight_market, CityMenuState,
    JobBoardState, JobDetailState, PayDebtState, RouteSelectState, JOB_BOARD_INTRO_HELP,
};
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_pause_states::{
    AbandonJobConfirmationState, PauseMenuState, ASSIGNED_REPOSITION_ABANDON_REPUTATION_PENALTY,
};
use freight_fate::states::main_menu::MainMenuState;
use serde_json::{json, Map, Value};
use states_city_support::*;

fn job(miles: f64) -> Job {
    job_with(miles, 900.0, 8.0)
}

fn job_with(miles: f64, pay: f64, deadline: f64) -> Job {
    Job::new(
        cargo_type("general").unwrap(),
        12.0,
        "Chicago",
        "Chicago yard",
        "Milwaukee",
        miles,
        pay,
        deadline,
    )
}

/// `_new_hire`: a company driver past the first-dispatch badge.
fn new_hire(app: &mut TestApp, name: &str) {
    career(app, name, "Chicago");
    profile_mut(app)
        .achievements
        .push("first_dispatch".to_string());
}

fn push_board(app: &mut TestApp, jobs: Vec<Job>) {
    let board = JobBoardState::new(&app.ctx, jobs);
    app.push_state(board);
}

/// What the player hears on entering a menu: `announce_entry` speaks the
/// context and the focused item as two events, so the listener hears one
/// announcement and that is what these tests read.
fn entry_announcement(app: &TestApp) -> String {
    let lines = app.main_lines();
    let tail = lines.len().saturating_sub(2);
    lines[tail..].join(" ")
}

// -- tests/test_dispatch_autonomy.py -------------------------------------------------

#[test]
fn test_new_hire_board_offers_single_assignment_with_decline() {
    let mut app = TestApp::new();
    new_hire(&mut app, "New Hire");
    profile_mut(&mut app).career.deliveries = 12; // past training stages

    push_board(&mut app, vec![job(180.0), job(70.0)]);

    assert!(with_state::<JobBoardState, _>(&app, |b, _| b.assigned_mode()));
    let labels = labels::<JobBoardState>(&app);
    assert!(labels[0].starts_with("Accept assigned dispatch:"));
    assert!(labels[0].contains("70 miles")); // the recommended (shortest) load
    assert!(labels[1].starts_with("Decline and request another load:"));
    assert!(labels[1].contains(&format!("{NEW_HIRE_DECLINE_BUDGET} declines left")));
    assert_eq!(labels.last().unwrap(), "Back to terminal");
    let said = app.main_lines().last().cloned().unwrap();
    assert!(said.contains("Dispatch assigns your load and route"));
    assert!(said.contains(&format!("level {SENIOR_LOAD_CHOICE_LEVEL}")));
}

#[test]
fn test_declining_assignment_costs_reputation_and_draws_next_load() {
    let mut app = TestApp::new();
    new_hire(&mut app, "Decliner");
    profile_mut(&mut app).career.deliveries = 12;
    let reputation_before = profile(&app).career.reputation;

    push_board(&mut app, vec![job(180.0), job(70.0)]);
    select::<JobBoardState>(&mut app, "Decline");

    assert_eq!(profile(&app).career.dispatch_declines_used, 1);
    assert!(profile(&app).career.reputation < reputation_before);
    let said = app.main_lines().last().cloned().unwrap();
    assert!(said.contains("Load declined"));
    assert!(said.contains("service record"));
    assert!(said.contains("180 miles")); // the next candidate was drawn
    let labels = labels::<JobBoardState>(&app);
    assert!(labels[0].starts_with("Accept assigned dispatch:"));
    assert!(labels[0].contains("180 miles"));
}

#[test]
fn test_exhausted_decline_budget_locks_board_to_accept_only() {
    let mut app = TestApp::new();
    new_hire(&mut app, "Out Of Declines");
    {
        let p = profile_mut(&mut app);
        p.career.deliveries = 12;
        p.career.dispatch_declines_used = NEW_HIRE_DECLINE_BUDGET;
    }

    push_board(&mut app, vec![job(180.0), job(70.0)]);

    let labels = labels::<JobBoardState>(&app);
    assert!(labels[0].starts_with("Accept assigned dispatch:"));
    assert!(!labels.iter().any(|l| l.starts_with("Decline")));
}

#[test]
fn test_single_candidate_assignment_offers_no_decline() {
    let mut app = TestApp::new();
    new_hire(&mut app, "One Load Town");

    push_board(&mut app, vec![job(70.0)]);

    let labels = labels::<JobBoardState>(&app);
    assert!(labels[0].starts_with("Accept assigned dispatch:"));
    assert!(!labels.iter().any(|l| l.starts_with("Decline")));
}

#[test]
fn test_accepting_assignment_starts_pickup_drive() {
    let mut app = TestApp::new();
    new_hire(&mut app, "Assigned Acceptor");
    let jobs = JobBoard::seeded(app.ctx.world, 7).offers(
        "Chicago",
        &[] as &[&str],
        OfferOptions {
            level: 1,
            ..OfferOptions::default()
        },
    );

    push_board(&mut app, jobs);
    assert!(with_state::<JobBoardState, _>(&app, |b, _| b.assigned_mode()));
    key(&mut app, Key::Return);

    assert!(is::<DrivingState>(&app));
    assert_eq!(
        with_state::<DrivingState, _>(&app, |d, _| d.phase.to_string()),
        freight_fate::states::driving_core::DRIVE_PHASE_PICKUP
    );
}

#[test]
fn test_senior_company_driver_gets_browsable_board() {
    let mut app = TestApp::new();
    new_hire(&mut app, "Senior Driver");
    {
        let p = profile_mut(&mut app);
        p.career.xp = LEVEL_XP[(SENIOR_LOAD_CHOICE_LEVEL - 1) as usize];
        p.career.deliveries = 20;
        p.career.reputation = 80.0;
    }

    push_board(&mut app, vec![job(180.0), job(70.0)]);

    assert!(!with_state::<JobBoardState, _>(&app, |b, _| b.assigned_mode()));
    assert!(labels::<JobBoardState>(&app)
        .iter()
        .any(|l| l.contains("Job 1 of 2")));
}

#[test]
fn test_owner_operator_board_stays_browsable() {
    let mut app = TestApp::new();
    new_hire(&mut app, "Owner Browser");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
    }

    push_board(&mut app, vec![job(180.0), job(70.0)]);

    assert!(!with_state::<JobBoardState, _>(&app, |b, _| b.assigned_mode()));
}

#[test]
fn test_company_departure_runs_dispatch_assigned_route() {
    // The Python asserted the loaded `DrivingState` and its route; with the
    // driving port outstanding this pins the half that is the point of the
    // test: dispatch routed it, and no route menu appeared.
    let mut app = TestApp::new();
    new_hire(&mut app, "Routed Driver");
    let pickup = loaded_pickup(&app, job(92.0));
    app.push_state(pickup);
    app.clear_speech();

    key(&mut app, Key::Return); // depart

    assert!(is::<DrivingState>(&app));
    let departure = app
        .main_lines()
        .into_iter()
        .find(|line| line.contains("Dispatch routed you to"))
        .expect("dispatch routed the load");
    // This fixture never starts the engine, so the line ends with the
    // start-up keys rather than announcing a departure the truck cannot
    // make. What matters here is that dispatch routed it and no route
    // menu appeared.
    assert!(departure.contains("Loaded trip is"));
    assert!(!app
        .main_lines()
        .iter()
        .any(|line| line.contains("Route planning to")));
}

#[test]
fn test_senior_company_departure_is_still_dispatch_routed() {
    let mut app = TestApp::new();
    new_hire(&mut app, "Senior Routed");
    profile_mut(&mut app).career.xp = LEVEL_XP[(SENIOR_LOAD_CHOICE_LEVEL - 1) as usize];
    let pickup = loaded_pickup(&app, job(92.0));
    app.push_state(pickup);

    key(&mut app, Key::Return); // depart

    assert!(is::<DrivingState>(&app));
    assert!(!stack_has::<RouteSelectState>(&app));
}

#[test]
fn test_owner_operator_departure_keeps_route_choice() {
    let mut app = TestApp::new();
    new_hire(&mut app, "Owner Router");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
    }
    let pickup = loaded_pickup(&app, job(92.0));
    app.push_state(pickup);

    key(&mut app, Key::Return); // depart

    assert!(is::<RouteSelectState>(&app));
    assert!(app
        .main_lines()
        .iter()
        .any(|line| line.contains("Route planning to")));
}

#[test]
fn test_declined_load_stays_declined_when_the_board_is_reopened() {
    let mut app = TestApp::new();
    new_hire(&mut app, "Board Returner");

    let city = CityMenuState::new(&app.ctx, false);
    app.push_state(city);
    key(&mut app, Key::Return); // dispatch board
    assert!(is::<JobBoardState>(&app));
    assert!(with_state::<JobBoardState, _>(&app, |b, _| b.assigned_mode()));
    let first_assignment =
        with_state::<JobBoardState, _>(&app, |b, _| b.assigned_job().describe_plain());

    let has_decline = labels::<JobBoardState>(&app)
        .iter()
        .any(|l| l.starts_with("Decline"));
    if !has_decline {
        return; // single-candidate board this seed: nothing to decline into
    }
    select::<JobBoardState>(&mut app, "Decline");
    let second_assignment =
        with_state::<JobBoardState, _>(&app, |b, _| b.assigned_job().describe_plain());
    assert_ne!(second_assignment, first_assignment);

    key(&mut app, Key::Escape); // back to terminal
    assert!(is::<CityMenuState>(&app));
    key(&mut app, Key::Return); // reopen board

    assert!(is::<JobBoardState>(&app));
    // dispatch does not put the refused load straight back on the driver
    assert_eq!(
        with_state::<JobBoardState, _>(&app, |b, _| b.assigned_job().describe_plain()),
        second_assignment
    );
}

#[test]
fn test_assigned_board_help_describes_accept_and_decline() {
    let mut app = TestApp::new();
    new_hire(&mut app, "Help Reader");

    push_board(&mut app, vec![job(70.0)]);

    let help = with_state::<JobBoardState, _>(&app, |b, _| b.intro_help().to_string());
    assert!(help.contains("Dispatch assigned this load"));
    assert!(help.contains("refusals cost reputation"));
    // the browsable class-level help is untouched for senior boards
    assert!(JOB_BOARD_INTRO_HELP.contains("Each entry is one dispatch"));
}

#[test]
fn test_assignment_board_offers_a_review_of_the_locked_pool() {
    // The pool widens with every level, and growth the driver cannot hear is
    // not a reward yet (owner design, 2026-07-24): an on-demand board review
    // speaks the other postings as flavor, never automatically.
    let mut app = TestApp::new();
    new_hire(&mut app, "New Hire");
    profile_mut(&mut app).career.deliveries = 12;

    push_board(&mut app, vec![job(180.0), job(70.0)]);
    assert!(with_state::<JobBoardState, _>(&app, |b, _| b.assigned_mode()));
    activate::<JobBoardState>(&mut app, "Review the rest of today's board");
    let said = app.main_lines().last().cloned().unwrap();
    assert!(said.starts_with("Dispatch also posted today:"));
    assert!(said.contains("180 miles"));
    assert!(said.contains(&format!("level {SENIOR_LOAD_CHOICE_LEVEL}")));

    // A one-job day has nothing to review: the option stays off the menu.
    app.pop_state();
    push_board(&mut app, vec![job(70.0)]);
    assert!(!labels::<JobBoardState>(&app)
        .iter()
        .any(|l| l == "Review the rest of today's board"));
}

// -- tests/test_dispatch_job_detail.py ------------------------------------------------

/// `_job_board`: a senior driver's seed-7 Buffalo board.
fn senior_job_board(app: &mut TestApp) {
    career(app, "Dispatch Detail", "Buffalo");
    // Senior driver: the seed-7 deal reshuffles whenever the world grows, and
    // a level-locked first job would strip the detail view of its accept item
    // (1.9 hardens this helper the same way).
    profile_mut(app).career.xp = *LEVEL_XP.last().unwrap();
    let jobs = JobBoard::seeded(app.ctx.world, 7).offers(
        "Buffalo",
        &["refrigerated", "heavy_haul", "high_value"],
        OfferOptions::level(5),
    );
    push_board(app, jobs);
}

#[test]
fn test_f1_on_dispatch_job_opens_structured_detail_view() {
    let mut app = TestApp::new();
    senior_job_board(&mut app);
    let focused =
        with_state::<JobBoardState, _>(&app, |b, _| b.jobs[b.menu().index].cargo.label.to_string());

    key(&mut app, Key::F1);

    assert!(is::<JobDetailState>(&app));
    let lines = app.visible_lines();
    let joined = lines.join(" ");
    assert_eq!(lines[0], "Job details");
    let rows = labels::<JobDetailState>(&app);
    assert_eq!(rows[0], format!("Cargo: {focused}."));
    assert!(lines.contains(&format!("> Cargo: {focused}.")));
    assert!(joined.contains("Origin:"));
    assert!(joined.contains("Destination:"));
    // The detail view always names the state, even for a unique city name,
    // so a player who does not know the geography can ask for it here.
    assert!(joined.contains("in Buffalo, New York"));
    assert!(joined.contains("Distance:"));
    assert!(joined.contains("Carrier gross:"));
    assert!(joined.contains("Dollars per mile:"));
    assert!(joined.contains("Route details happen after pickup"));
    assert_eq!(rows[rows.len() - 2], "Accept this dispatch");
    assert_eq!(rows[rows.len() - 1], "Back to dispatch board");
}

#[test]
fn test_tab_repeats_only_the_market_watch() {
    let mut app = TestApp::new();
    senior_job_board(&mut app);
    app.clear_speech();

    let index_before = index::<JobBoardState>(&app); // the board may open on a recommended job
    key(&mut app, Key::Tab);

    // Exactly the market summary is spoken -- no job line, no HOS note.
    assert_eq!(app.main_lines(), vec![profile(&app).market.summary()]);
    assert_eq!(index::<JobBoardState>(&app), index_before); // Tab does not move the selection
}

#[test]
fn test_job_detail_lines_are_reviewable_before_accepting() {
    let mut app = TestApp::new();
    senior_job_board(&mut app);
    key(&mut app, Key::F1);
    let first_line = labels::<JobDetailState>(&app)[0].clone();
    app.clear_speech();

    key(&mut app, Key::Return);

    assert!(is::<JobDetailState>(&app));
    let states = app.states();
    let under = &states[states.len() - 2];
    assert!(under
        .borrow()
        .as_any()
        .downcast_ref::<JobBoardState>()
        .is_some());
    assert_eq!(app.main_lines().last().unwrap(), &first_line);
}

#[test]
fn test_job_detail_exposes_review_instructions() {
    let mut app = TestApp::new();
    senior_job_board(&mut app);

    key(&mut app, Key::F1);
    let entry_speech = app.main_lines().last().cloned().unwrap();
    key(&mut app, Key::F1);
    let help = app.main_lines().last().cloned().unwrap();

    assert!(entry_speech.contains("Use up and down arrows to review each job detail line"));
    assert!(help.contains("Home and End jump"));
    assert!(help.contains("Press Enter to repeat it"));
}

#[test]
fn test_locked_job_detail_does_not_sound_accept_available() {
    let mut app = TestApp::new();
    career(&mut app, "Locked Detail", "Buffalo");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.career.xp = LEVEL_XP[4]; // endorsements owned
    }
    let job = Job::new(
        cargo_type("refrigerated").unwrap(),
        12.0,
        "Buffalo",
        "cold storage",
        "Cleveland",
        180.0,
        1800.0,
        8.0,
    );
    push_board(&mut app, vec![job.clone()]);
    let locked_reason = with_state::<JobBoardState, _>(&app, |b, ctx| b.locked_reason(ctx, &job));
    assert!(locked_reason.contains("trailer program"));

    key(&mut app, Key::F1);
    let rows = labels::<JobDetailState>(&app);
    let locked_row = rows[rows.len() - 2].clone();
    app.clear_speech();
    activate::<JobDetailState>(&mut app, "Cannot accept this dispatch");

    assert_eq!(
        locked_row,
        format!("Cannot accept this dispatch: {locked_reason}")
    );
    assert_eq!(app.main_lines().last().unwrap(), &locked_reason);
}

#[test]
fn test_f1_on_back_item_does_not_crash() {
    let mut app = TestApp::new();
    senior_job_board(&mut app);
    // Move to the trailing "Back to terminal" item (past the last job).
    key(&mut app, Key::End);
    let jobs = with_state::<JobBoardState, _>(&app, |b, _| b.jobs.len());
    assert_eq!(index::<JobBoardState>(&app), jobs);
    assert_eq!(current_label::<JobBoardState>(&app), "Back to terminal");

    // F1 here must not index off the end of the jobs list.
    key(&mut app, Key::F1);

    assert!(is::<JobBoardState>(&app));
}

#[test]
fn test_job_detail_accept_command_accepts_and_escape_returns() {
    let mut app = TestApp::new();
    senior_job_board(&mut app);
    key(&mut app, Key::F1);
    key(&mut app, Key::Escape);
    assert!(is::<JobBoardState>(&app));

    key(&mut app, Key::F1);
    select::<JobDetailState>(&mut app, "Accept this dispatch");
    assert!(is::<DrivingState>(&app));
    assert!(!stack_has::<JobDetailState>(&app));
}

// -- tests/test_stale_dispatch_board.py -----------------------------------------------

const GONE: &str = "Buffalo Gone-Away Cold Storage";
const STALE_ENDORSEMENTS: [&str; 3] = ["refrigerated", "heavy_haul", "high_value"];

fn senior_profile(app: &mut TestApp) {
    career(app, "Stale board", "Buffalo");
    profile_mut(app).career.xp = *LEVEL_XP.last().unwrap();
}

/// Cache a board into the save, then retire one job's pickup facility.
fn cache_a_board_with_a_retired_pickup(app: &mut TestApp) -> Vec<Value> {
    let market = profile(app).market.clone();
    let jobs = JobBoard::seeded(app.ctx.world, 7).offers(
        "Buffalo",
        &STALE_ENDORSEMENTS,
        OfferOptions {
            level: 30,
            market: Some(&market),
            ..OfferOptions::default()
        },
    );
    let mut payloads: Vec<Value> = jobs
        .iter()
        .map(|job| Value::Object(job_payload(job)))
        .collect();
    let first = payloads[0].as_object_mut().unwrap();
    first.insert("origin_location".into(), json!(GONE));
    first.insert(
        "origin_facility_id".into(),
        json!("buffalo-gone-away-cold-storage"),
    );
    let key = dispatch_cache_key(profile(app));
    let mut cache = Map::new();
    cache.insert("key".into(), key);
    cache.insert("jobs".into(), Value::Array(payloads.clone()));
    profile_mut(app).dispatch_board_cache = Some(Value::Object(cache));
    payloads
}

#[test]
fn test_a_board_naming_a_retired_pickup_is_rebuilt_from_the_current_world() {
    let mut app = TestApp::new();
    senior_profile(&mut app);
    cache_a_board_with_a_retired_pickup(&mut app);

    open_freight_market(&mut app.ctx);
    app.ctx.run_deferred();

    let offered = with_state::<JobBoardState, _>(&app, |b, _| {
        b.jobs
            .iter()
            .map(|job| job.origin_location.clone())
            .collect::<Vec<_>>()
    });
    assert!(!offered.iter().any(|name| name == GONE));
    // Rebuilt, not merely filtered: the player still gets a full board.
    let level = profile(&app).career.level();
    assert_eq!(
        with_state::<JobBoardState, _>(&app, |b, _| b.jobs.len()),
        board_offer_count(level)
    );
    let cache = profile(&app).dispatch_board_cache.clone().unwrap();
    let jobs = cache["jobs"].as_array().unwrap().clone();
    assert!(jobs
        .iter()
        .all(|payload| payload["origin_location"] != json!(GONE)));
}

#[test]
fn test_accepting_a_retired_pickup_says_so_instead_of_crashing() {
    // The board rebuild above is the fix; this is the net under it.
    //
    // A JobDetailState opened before the board was rebuilt still holds the
    // old job, so the accept path has to refuse on its own rather than raise.
    let mut app = TestApp::new();
    senior_profile(&mut app);
    let payloads = cache_a_board_with_a_retired_pickup(&mut app);
    let stale_job = ff_core::models::jobs::job_from_payload(payloads[0].as_object().unwrap())
        .expect("a cached payload rebuilds");

    let board = JobBoardState::new(&app.ctx, vec![stale_job.clone()]);
    app.push_state_with(board, false);
    app.clear_speech();

    with_state_mut::<JobBoardState, _>(&mut app, |b, ctx| b.accept(ctx, 0));

    let said = app.main_lines().join(" ").to_lowercase();
    assert!(said.contains("no longer on the network"));
    assert!(said.contains("refresh"));
    // Plain player language: nothing about facilities, keys, or saves.
    for jargon in ["keyerror", "facility_location", "world data", "cache"] {
        assert!(!said.contains(jargon), "spoke maintainer jargon: {said}");
    }
    // The trip must not have started, the dead offer is off the board,
    // and the stale cache is forgotten so the next build is a current one.
    assert!(profile(&app).active_trip.is_none());
    assert!(with_state::<JobBoardState, _>(&app, |b, _| b
        .jobs
        .is_empty()));
    assert!(profile(&app).dispatch_board_cache.is_none());
}

// -- tests/test_pickup_loading.py (board cases) ---------------------------------------

#[test]
fn test_job_board_help_names_drivable_pickup_before_route_planning() {
    assert!(JOB_BOARD_INTRO_HELP.contains("local deadhead pickup drive from your terminal"));
    assert!(!JOB_BOARD_INTRO_HELP.contains("route planning"));
}

#[test]
fn test_accepting_stale_cached_offer_drops_it_instead_of_crashing() {
    // A cached dispatch board can outlive its facilities: a data update may
    // retire one (e.g. a template gated out by geography). Accepting such an
    // offer must pull it and refresh, never crash.
    let mut app = TestApp::new();
    career(&mut app, "Stale Board", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.dispatch_board_cache = Some(json!({"stale": true}));
    }
    let dead = Job::new(
        cargo_type("general").unwrap(),
        12.0,
        "Chicago",
        "Chicago Retired Facility",
        "Milwaukee",
        92.0,
        1800.0,
        7.0,
    );
    push_board(&mut app, vec![dead]);

    key(&mut app, Key::Return);

    assert!(is::<JobBoardState>(&app));
    assert!(profile(&app).active_trip.is_none());
    assert!(profile(&app).dispatch_board_cache.is_none());
    assert!(with_state::<JobBoardState, _>(&app, |b, _| b
        .jobs
        .is_empty()));
    assert!(app
        .main_lines()
        .iter()
        .any(|line| line.contains("no longer on the network")));
}

#[test]
fn test_dispatch_board_stays_stable_when_reopened() {
    // The Python walked the new-career flow to the terminal; the terminal
    // hub itself is what this pins, so it starts there.
    let mut app = TestApp::new();
    career(&mut app, "Board Stability", "Chicago");
    let city = CityMenuState::new(&app.ctx, false);
    app.push_state(city);

    key(&mut app, Key::Return); // dispatch board
    assert!(is::<JobBoardState>(&app));
    let first_board = with_state::<JobBoardState, _>(&app, |b, _| {
        b.jobs
            .iter()
            .map(|j| j.describe_plain())
            .collect::<Vec<_>>()
    });
    assert!(!first_board.is_empty());
    assert!(profile(&app).dispatch_board_cache.is_some());

    key(&mut app, Key::Escape); // back to terminal
    assert!(is::<CityMenuState>(&app));
    key(&mut app, Key::Return); // dispatch board again
    assert!(is::<JobBoardState>(&app));
    let second_board = with_state::<JobBoardState, _>(&app, |b, _| {
        b.jobs
            .iter()
            .map(|j| j.describe_plain())
            .collect::<Vec<_>>()
    });

    assert_eq!(second_board, first_board);
}

// -- tests/test_trailer_market_preview.py ---------------------------------------------

fn bulk_job() -> Job {
    let mut job = Job::new(
        cargo_type("bulk").unwrap(),
        20.0,
        "Chicago",
        "Chicago Bulk Terminal",
        "Indianapolis",
        180.0,
        1400.0,
        8.0,
    );
    job.origin_type = "mine_quarry".to_string();
    job.destination_location = "Indianapolis Construction Yard".to_string();
    job.destination_type = "construction_materials_yard".to_string();
    job
}

#[test]
fn test_company_driver_bulk_job_uses_carrier_trailer_support() {
    let mut app = TestApp::new();
    career(&mut app, "Company Driver", "Chicago");
    push_board(&mut app, vec![bulk_job()]);

    // New company hires get the load as a dispatch assignment.
    let row = labels::<JobBoardState>(&app)[0].clone();
    assert!(row.starts_with("Accept assigned dispatch:"));
    assert!(row.contains("Carrier trailer provided"));
    assert!(row.contains("Estimated driver pay before advances"));
    assert!(!row.contains("Locked job"));
}

#[test]
fn test_owner_operator_hears_missing_trailer_gate_and_preview() {
    let mut app = TestApp::new();
    career(&mut app, "Leased Owner", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.trailer_programs = vec!["dry_van".to_string()];
    }
    push_board(&mut app, vec![bulk_job()]);

    let row = labels::<JobBoardState>(&app)[0].clone();
    assert!(row.starts_with("Locked job 1 of 1"));
    assert!(row.contains("Needs Bulk trailer program"));
    assert!(row.contains("Gross revenue"));
    assert!(row.contains("Estimated take-home before advances"));
    assert!(row.contains("business costs"));
}

#[test]
fn test_own_authority_owned_trailer_row_shows_direct_market_fit() {
    let mut app = TestApp::new();
    career(&mut app, "Authority Driver", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = INDEPENDENT_AUTHORITY.to_string();
        p.trailer_programs = vec!["dry_van".to_string()];
        p.owned_trailers = vec!["bulk".to_string()];
    }
    push_board(&mut app, vec![bulk_job()]);

    let row = labels::<JobBoardState>(&app)[0].clone();
    assert!(row.starts_with("Job 1 of 1"));
    assert!(row.contains("Owned trailer: Bulk"));
    assert!(row.contains("Direct gross"));
    assert!(row.contains("owned-trailer reserve"));
    assert!(!row.contains("Locked job"));
}

// -- tests/test_assigned_reposition.py ------------------------------------------------

/// Walk seeded profiles/cities until the board's own deterministic roll
/// turns up a reposition, mirroring how tests elsewhere search seeds for a
/// property instead of hand-picking one fragile value.
fn find_reposition(
    app: &mut TestApp,
    owner_operator: bool,
    trials: usize,
) -> Option<(Profile, Job)> {
    let cities: Vec<String> = app.ctx.world.cities.keys().cloned().collect();
    for i in 0..trials {
        let mut p = Profile::named_in(&format!("Seed{i}"), &cities[i % cities.len()]);
        p.market.seed = i as i64;
        // One run behind them: a brand-new hire's FIRST dispatch is always
        // freight (see the deliveries gate in assigned_reposition_for_board).
        p.career.deliveries = 1;
        if owner_operator {
            p.business_status = LEASED_OWNER_OPERATOR.to_string();
        }
        app.ctx.profile = Some(p.clone());
        let key = dispatch_cache_key(&p);
        let board = JobBoard::new(app.ctx.world, None, None);
        if let Some(job) = assigned_reposition_for_board(&app.ctx, &board, &key) {
            return Some((p, job));
        }
    }
    None
}

#[test]
fn test_assigned_reposition_shows_for_company_driver_never_for_owner_operator() {
    let mut app = TestApp::new();
    let (p, job) = find_reposition(&mut app, false, 600)
        .expect("no seeded board produced a reposition in the trial budget");
    assert!(job.bobtail && job.assigned);
    assert_ne!(job.destination, job.origin);
    assert!(app
        .ctx
        .world
        .supported_route(&job.origin, &job.destination, None)
        .unwrap()
        .is_some());
    // Pays something, but strictly less than the loaded per-mile floor.
    let plan = pay_plan_for_key(Some(&p.carrier_key));
    assert!(job.pay > 0.0 && job.pay < job.distance_mi * plan.min_per_mile);

    // The same search never turns one up for an owner-operator: the
    // gate is unconditional, not just an unlucky roll.
    assert!(find_reposition(&mut app, true, 600).is_none());
}

#[test]
fn test_a_new_hires_first_dispatch_is_never_a_reposition() {
    // Before the first delivery the roll never runs: every new career's
    // first assignment is freight, deterministically -- the roll hashes the
    // random market seed, so without the gate one new career in nine started
    // on a deadhead and every new-career test flow flaked with it.
    let mut app = TestApp::new();
    let cities: Vec<String> = app.ctx.world.cities.keys().cloned().collect();
    for i in 0..200 {
        let mut p = Profile::named_in(&format!("Fresh{i}"), &cities[i % cities.len()]);
        p.market.seed = i as i64;
        assert_eq!(p.career.deliveries, 0);
        let key = dispatch_cache_key(&p);
        app.ctx.profile = Some(p);
        let board = JobBoard::new(app.ctx.world, None, None);
        assert!(
            assigned_reposition_for_board(&app.ctx, &board, &key).is_none(),
            "seed {i}: a first dispatch offered a reposition"
        );
    }
}

#[test]
fn test_assigned_reposition_replaces_a_board_slot_for_company_driver() {
    // The reposition takes an ordinary offer's place rather than adding a
    // ninth entry, so the board still shows exactly as many jobs as the
    // player's level and trust earn -- the same invariant a stale board
    // rebuild relies on (see test_stale_dispatch_board.py).
    let mut app = TestApp::new();
    let (p, _job) = find_reposition(&mut app, false, 600).expect("a seeded reposition");
    app.ctx.profile = Some(p.clone());
    open_freight_market(&mut app.ctx);
    app.ctx.run_deferred();

    assert!(with_state::<JobBoardState, _>(&app, |b, _| b
        .jobs
        .iter()
        .any(|j| j.bobtail && j.assigned)));
    let expected = enforcement::board_offers_for_reputation(
        board_offer_count(p.career.level()) as i64,
        p.career.reputation,
    ) as usize;
    assert_eq!(
        with_state::<JobBoardState, _>(&app, |b, _| b.jobs.len()),
        expected
    );
}

#[test]
fn test_assigned_reposition_pays_reduced_rate_and_awards_mileage_xp() {
    // The settlement half needs ArrivalState; the pay the board offers is
    // what the city screens own, so that is what is pinned here.
    let app = TestApp::new();
    let p = Profile::named_in("Assigned Reposition", "Denver");
    let job = make_reposition_job(
        app.ctx.world,
        "Denver",
        "Cheyenne",
        true,
        Some(&p.carrier_key),
    )
    .expect("Denver to Cheyenne is on the network");
    assert!(job.bobtail && job.assigned);
    let plan = pay_plan_for_key(Some(&p.carrier_key));
    let expected_pay = ff_core::pyfmt::round_py_n(
        job.distance_mi * plan.min_per_mile * ASSIGNED_REPOSITION_PAY_FRACTION,
        2,
    );
    assert_eq!(job.pay, expected_pay);
}

/// Walking away from an ASSIGNED reposition is walking away from a dispatch
/// assignment: reputation drops, no dollar penalty -- unlike a real load
/// (five hundred dollars and reputation) and unlike a self-serve bobtail
/// (nothing at all, `test_abandoning_a_bobtail_costs_nothing`).
#[test]
fn test_abandoning_assigned_reposition_costs_reputation_only() {
    let mut app = TestApp::new();
    app.ctx.profile = Some(Profile::named_in("Assigned Reposition Abandon", "Denver"));
    let carrier_key = profile(&app).carrier_key.clone();
    let job = make_reposition_job(
        app.ctx.world,
        "Denver",
        "Cheyenne",
        true,
        Some(&carrier_key),
    )
    .expect("Denver to Cheyenne is on the network");
    let route = app
        .ctx
        .world
        .supported_route("Denver", "Cheyenne", None)
        .expect("the world routes")
        .expect("the corridor is supported");
    let driving = DrivingState::new(
        &mut app.ctx,
        job,
        route,
        None,
        freight_fate::states::driving_core::DRIVE_PHASE_DELIVERY,
        None,
    );
    let money_before = profile(&app).money;
    let reputation_before = profile(&app).career.reputation;

    app.push_state(driving);
    key(&mut app, Key::Escape);
    assert!(is::<PauseMenuState>(&app));
    select::<PauseMenuState>(&mut app, "Abandon job");
    assert!(is::<AbandonJobConfirmationState>(&app));
    assert!(with_state::<AbandonJobConfirmationState, _>(
        &app,
        |c, _| c.is_bobtail()
    ));
    assert!(with_state::<AbandonJobConfirmationState, _>(
        &app,
        |c, _| c.is_assigned_reposition()
    ));

    key(&mut app, Key::Down); // arrow to Yes
    key(&mut app, Key::Return);

    assert!(is::<CityMenuState>(&app));
    assert_eq!(profile(&app).money, money_before); // no dollar penalty
    assert_eq!(
        profile(&app).career.reputation,
        reputation_before - ASSIGNED_REPOSITION_ABANDON_REPUTATION_PENALTY
    );
}

// -- tests/test_career_unlocks.py (board parts) ---------------------------------------

#[test]
fn test_seniority_boards_actually_offer_more_jobs() {
    let app = TestApp::new();
    let mut board = JobBoard::seeded(app.ctx.world, 7);
    let rookie = board.offers(
        "Chicago",
        &[] as &[&str],
        OfferOptions {
            count: board_offer_count(1),
            level: 1,
            ..OfferOptions::default()
        },
    );
    let senior = board.offers(
        "Chicago",
        &["refrigerated", "heavy_haul", "high_value"],
        OfferOptions {
            count: board_offer_count(12),
            level: 12,
            ..OfferOptions::default()
        },
    );
    assert_eq!(rookie.len(), 5);
    assert_eq!(senior.len(), 8);
}

// -- tests/test_pay_advance.py (terminal) ---------------------------------------------

#[test]
fn test_terminal_pay_advance_option_only_appears_when_available() {
    let mut app = TestApp::new();
    career(&mut app, "Advance Test", "New York");
    let mut state = CityMenuState::new(&app.ctx, false);

    profile_mut(&mut app).money = PAY_ADVANCE_ELIGIBLE_BELOW;
    assert!(!built_labels(&mut app, &mut state)
        .iter()
        .any(|t| t.starts_with("Request pay advance")));

    profile_mut(&mut app).money = PAY_ADVANCE_ELIGIBLE_BELOW - 1.0;
    assert!(built_labels(&mut app, &mut state)
        .iter()
        .any(|t| t.starts_with("Request pay advance")));

    state.request_pay_advance(&mut app.ctx);
    assert!(profile(&app).pay_advance_used_for_load);
    assert!(!built_labels(&mut app, &mut state)
        .iter()
        .any(|t| t.starts_with("Request pay advance")));

    {
        let p = profile_mut(&mut app);
        p.pay_advance_used_for_load = false;
        p.pay_advance = PAY_ADVANCE_LIMIT;
    }
    assert!(!built_labels(&mut app, &mut state)
        .iter()
        .any(|t| t.starts_with("Request pay advance")));
}

// -- tests/test_debt_and_standing.py (terminal) ---------------------------------------

fn payer(app: &mut TestApp, money: f64, owed: f64) {
    career(app, "Dale", "Buffalo");
    let p = profile_mut(app);
    p.money = money;
    p.fines_owed = owed;
}

#[test]
fn test_the_terminal_stops_offering_an_advance_under_collection() {
    let mut app = TestApp::new();
    career(&mut app, "Dale", "Buffalo");
    profile_mut(&mut app).money = 2.0;
    let mut state = CityMenuState::new(&app.ctx, false);
    assert!(CityMenuState::pay_advance_available(&app.ctx));
    profile_mut(&mut app).fines_owed = 3_000.0;
    assert!(!CityMenuState::pay_advance_available(&app.ctx));
    assert!(!built_labels(&mut app, &mut state)
        .iter()
        .any(|t| t.to_lowercase().contains("pay advance")));
}

#[test]
fn test_a_setback_only_ever_fires_at_the_terminal() {
    // Both of these take the tractor the driver is sitting in.
    let mut app = TestApp::new();
    career(&mut app, "Dale", "Buffalo");
    {
        let p = profile_mut(&mut app);
        p.career.xp = 152_000.0;
        p.money = -solvency::company_debt_ceiling(p) - 1.0;
    }
    // Walking into the terminal is what fires it, and the notice takes the
    // screen ahead of everything else the terminal had to say.
    let city = CityMenuState::new(&app.ctx, false);
    app.push_state(city);
    assert!(is::<CareerSetbackNoticeState>(&app));
    assert_eq!(profile(&app).carrier_key, "great_lakes_training");

    with_state_mut::<CareerSetbackNoticeState, _>(&mut app, |s, ctx| {
        freight_fate::states::base::Menu::go_back(s, ctx)
    });
    assert!(is::<CityMenuState>(&app));
    assert!(!solvency::setback_pending(profile(&app)));
}

#[test]
fn test_the_terminal_only_offers_payoff_when_something_is_owed() {
    let mut app = TestApp::new();
    payer(&mut app, 5_000.0, 1_000.0);
    let mut state = CityMenuState::new(&app.ctx, false);
    assert!(built_labels(&mut app, &mut state)
        .iter()
        .any(|t| t == "Pay down what you owe: 1,000 dollars owed"));

    profile_mut(&mut app).fines_owed = 0.0;
    assert!(!built_labels(&mut app, &mut state)
        .iter()
        .any(|t| t.starts_with("Pay down what you owe")));
}

#[test]
fn test_paying_it_all_off_clears_the_balance_and_says_so() {
    let mut app = TestApp::new();
    payer(&mut app, 5_000.0, 1_000.0);
    app.push_state(PayDebtState::new());
    activate::<PayDebtState>(&mut app, "Pay it all");

    assert_eq!(profile(&app).fines_owed, 0.0);
    assert_eq!(solvency::debt_owed(profile(&app)), 0.0);
    assert_eq!(profile(&app).money, 4_000.0);
    assert!(app
        .main_lines()
        .iter()
        .any(|line| line.contains("your account is clear")));
}

#[test]
fn test_paying_it_all_off_speaks_the_clear_confirmation_last() {
    // Popping back to the terminal fires the parent menu's own interrupt=True
    // entry announcement. The clear confirmation must be spoken after that
    // pop, so it survives as the last thing heard instead of being cut off.
    let mut app = TestApp::new();
    payer(&mut app, 5_000.0, 1_000.0);
    let city = CityMenuState::new(&app.ctx, false);
    app.push_state(city);
    app.push_state(PayDebtState::new());
    app.clear_speech(); // only the pay-it-all action's own speech matters here
    activate::<PayDebtState>(&mut app, "Pay it all");

    let calls = app.main_calls();
    assert!(!calls.is_empty(), "expected the clear confirmation spoken");
    let (last_text, last_interrupt) = calls.last().cloned().unwrap();
    assert!(last_text.contains("your account is clear"));
    assert!(last_interrupt);
}

#[test]
fn test_paying_half_leaves_the_rest_owed_and_says_the_remainder() {
    let mut app = TestApp::new();
    payer(&mut app, 5_000.0, 1_000.0);
    app.push_state(PayDebtState::new());
    activate::<PayDebtState>(&mut app, "Pay half");

    assert_eq!(profile(&app).fines_owed, 500.0);
    assert_eq!(solvency::debt_owed(profile(&app)), 500.0);
    assert_eq!(profile(&app).money, 4_500.0);
    assert!(app
        .main_lines()
        .iter()
        .any(|line| line.contains("500") && line.contains("still owed")));
}

// -- tests/test_enforcement_record.py (terminal and board) ----------------------------

fn suspended_driver(app: &mut TestApp, name: &str) {
    career(app, name, "Buffalo");
    let hours = profile(app).game_hours;
    let p = profile_mut(app);
    p.driving_record.record_serious_violation(hours);
    p.driving_record.record_serious_violation(hours);
}

#[test]
fn test_a_clean_driver_hears_and_pays_nothing_new() {
    // The economy guardrail: nothing here reaches a driver who runs clean.
    let mut app = TestApp::new();
    career(&mut app, "Jerry", "Buffalo");
    let city = CityMenuState::new(&app.ctx, false);
    app.push_state(city);
    let said = app.main_lines().join(" ");
    assert!(!said.contains("CDL"));
    assert!(!said.contains("Dispatch trust"));
    assert!(!labels::<CityMenuState>(&app)
        .iter()
        .any(|t| t.starts_with("Wait out")));
    assert_eq!(profile(&app).driving_record.citations, 0);
}

#[test]
fn test_the_board_says_the_suspension_before_it_lists_anything() {
    let mut app = TestApp::new();
    suspended_driver(&mut app, "Jerry");
    app.clear_speech();
    push_board(&mut app, vec![job(92.0)]);
    let said = app.main_lines();
    assert!(said[0].starts_with("Dispatch board. Your CDL is suspended"));
    assert!(said[0].to_lowercase().contains("driving jobs return"));
}

#[test]
fn test_taking_a_job_while_suspended_is_refused_with_the_clear_date() {
    let mut app = TestApp::new();
    career(&mut app, "Jerry", "Buffalo");
    let hours = profile(&app).game_hours;
    profile_mut(&mut app)
        .driving_record
        .record_major_offense(hours);
    push_board(&mut app, vec![job(92.0)]);
    app.clear_speech();
    with_state_mut::<JobBoardState, _>(&mut app, |b, ctx| b.accept(ctx, 0));
    assert!(profile(&app).active_trip.is_none());
    let said = app.main_lines().last().cloned().unwrap();
    assert!(said.contains("disqualified"));
    assert!(said.contains("clears"));
}

#[test]
fn test_waiting_out_the_suspension_gives_the_licence_back() {
    let mut app = TestApp::new();
    suspended_driver(&mut app, "Jerry");
    let hours = profile(&app).game_hours;
    assert!(profile(&app).driving_record.suspended(hours));
    let mut state = CityMenuState::new(&app.ctx, false);
    assert!(built_labels(&mut app, &mut state)
        .iter()
        .any(|t| t == "Wait out the CDL suspension"));
    app.clear_speech();
    state.wait_out_suspension(&mut app.ctx);
    let hours = profile(&app).game_hours;
    assert!(!profile(&app).driving_record.suspended(hours));
    assert!(app
        .main_lines()
        .iter()
        .any(|line| line.contains("clear again")));
}

#[test]
fn test_a_floor_reputation_company_driver_loses_the_carrier() {
    let mut app = TestApp::new();
    career(&mut app, "Jerry", "Buffalo");
    let former = profile(&app).carrier_name.clone();
    profile_mut(&mut app).career.reputation = 4.0;
    let mut state = CityMenuState::new(&app.ctx, false);
    app.clear_speech();
    state.check_carrier_termination(&mut app.ctx);
    assert_eq!(profile(&app).carrier_key, LAST_CHANCE_CARRIER_KEY);
    assert_eq!(profile(&app).driving_record.carrier_terminations, 1);
    // "Ended your employment", never "let you go": the ontology settled on
    // the plain factual verb over the softening one.
    assert!(app
        .main_lines()
        .iter()
        .any(|line| line.contains(&former) && line.contains("ended your employment")));
    // Nothing is taken away but the seat.
    assert!(profile(&app).money > 0.0 || profile(&app).career.level() >= 1);
}

// -- tests/test_career_objectives.py (terminal and board) -----------------------------

#[test]
fn test_terminal_career_plan_is_keyboard_reachable_and_spoken() {
    let mut app = TestApp::new();
    career(&mut app, "Keyboard Plan", "Chicago");
    profile_mut(&mut app)
        .achievements
        .push("first_dispatch".to_string());

    let city = CityMenuState::new(&app.ctx, false);
    app.push_state(city);

    assert!(app
        .main_lines()
        .iter()
        .any(|line| line.contains("Career objective:")));
    assert!(labels::<CityMenuState>(&app)
        .iter()
        .any(|t| t == "Career plan"));

    key(&mut app, Key::Down);
    key(&mut app, Key::Return);

    let said = app.main_lines().last().cloned().unwrap();
    assert!(said.starts_with("First dispatch."));
    assert!(said.contains("short standard load"));
}

#[test]
fn test_terminal_career_plan_speaks_senior_company_level_guidance() {
    let mut app = TestApp::new();
    career(&mut app, "Senior Driver", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.achievements.push("first_dispatch".to_string());
        p.career.xp = LEVEL_XP[9];
        p.career.deliveries = 20;
        p.career.reputation = 86.0;
    }

    let city = CityMenuState::new(&app.ctx, false);
    app.push_state(city);
    select::<CityMenuState>(&mut app, "Career plan");

    let said = app.main_lines().last().cloned().unwrap();
    assert!(said.starts_with("Run like a senior company driver."));
    assert!(said.contains("premium lanes"));
    assert!(said.contains("premium freight"));
    assert!(said.contains("Senior company status is about consistency"));
}

#[test]
fn test_dispatch_board_speaks_objective_and_marks_recommended_job() {
    // Senior company drivers browse the board; new hires get an assignment,
    // covered by test_dispatch_autonomy.
    let mut app = TestApp::new();
    career(&mut app, "Board Plan", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.achievements.push("first_dispatch".to_string());
        p.career.xp = LEVEL_XP[9];
        p.career.deliveries = 12;
        p.career.reputation = 86.0;
    }

    push_board(
        &mut app,
        vec![job_with(180.0, 1200.0, 8.0), job_with(70.0, 700.0, 8.0)],
    );

    let entry = entry_announcement(&app);
    assert!(entry.contains("Career objective: Run like a senior company driver"));
    assert!(entry.contains("pick your own loads"));
    assert!(entry.contains("routing is still assigned"));
    let rows = labels::<JobBoardState>(&app);
    let recommended = rows
        .iter()
        .find(|row| row.starts_with("Recommended dispatch"))
        .expect("a recommended row");
    assert!(recommended.starts_with("Recommended dispatch, senior company lane: Job 2 of 2:"));
    assert!(!rows[0].starts_with("Recommended dispatch"));
}

#[test]
fn test_dispatch_board_speaks_authority_level_recommendation() {
    let mut app = TestApp::new();
    career(&mut app, "Independent", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.achievements.push("first_dispatch".to_string());
        p.business_status = INDEPENDENT_AUTHORITY.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.money = 90_000.0;
        p.career.xp = LEVEL_XP[24];
        p.career.deliveries = 80;
        p.career.reputation = 94.0;
    }

    push_board(&mut app, vec![job_with(120.0, 1800.0, 8.0)]);

    let entry = entry_announcement(&app);
    assert!(entry.contains("Career objective: Grow a freight business"));
    assert!(entry.contains("direct freight"));
    assert!(entry.contains("direct freight with margin"));
}

#[test]
fn test_first_day_terminal_entry_speaks_training_arc_without_tutorial_language() {
    let mut app = TestApp::new();
    career(&mut app, "First Day", "Chicago");

    let city = CityMenuState::new(&app.ctx, false);
    app.push_state(city);

    let entry = entry_announcement(&app);
    assert!(entry.contains("First-day objective"));
    assert!(entry.contains("trainer-recommended"));
    assert!(!entry.to_lowercase().contains("probation"));
}

#[test]
fn test_out_of_sync_company_terminal_entry_uses_first_week_guidance() {
    let mut app = TestApp::new();
    career(&mut app, "First Week", "Chicago");
    profile_mut(&mut app).career.deliveries = 1;

    let city = CityMenuState::new(&app.ctx, false);
    app.push_state(city);

    let entry = entry_announcement(&app);
    assert!(!entry.contains("First-day objective"));
    assert!(entry.contains("Career objective:"));
    assert!(entry.contains("steady service, not perfection"));
    assert!(entry.contains("good first-week run"));
    assert!(entry.contains("trainer notes still close by"));
    let rows = labels::<CityMenuState>(&app);
    assert!(!rows.iter().any(|t| t == "First-day briefing"));
    assert!(rows.iter().any(|t| t == "Career plan"));
}

#[test]
fn test_dispatch_board_recommendation_label_is_spoken_and_visible() {
    let mut app = TestApp::new();
    career(&mut app, "Board Plan", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.achievements.push("first_dispatch".to_string());
        p.career.xp = LEVEL_XP[9];
        p.career.deliveries = 12;
        p.career.reputation = 86.0;
    }

    push_board(
        &mut app,
        vec![job_with(45.0, 900.0, 1.0), job_with(120.0, 900.0, 12.0)],
    );

    let entry = entry_announcement(&app);
    assert!(entry.contains("Career objective: Run like a senior company driver"));
    assert!(!entry.contains("First-day objective"));
    assert!(entry.contains("senior company lane"));
    assert!(!entry.contains("Recommended dispatch: senior company lane"));
    assert!(entry.contains("Recommended dispatch, senior company lane: Job 1 of 2:"));
    assert!(!entry.contains("Recommended dispatch is Recommended dispatch"));
    assert_eq!(index::<JobBoardState>(&app), 0);
    assert!(current_text::<JobBoardState>(&app)
        .starts_with("Recommended dispatch, senior company lane: Job 1 of 2:"));
    let rows = labels::<JobBoardState>(&app);
    let recommended: Vec<&String> = rows
        .iter()
        .filter(|row| row.starts_with("Recommended dispatch, senior company lane:"))
        .collect();
    assert_eq!(recommended, vec![&rows[0]]);
}

#[test]
fn test_owner_operator_first_day_terminal_keeps_cash_cushion_guidance() {
    let mut app = TestApp::new();
    career(&mut app, "Owner Day", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.money = 12_000.0;
    }

    let city = CityMenuState::new(&app.ctx, false);
    app.push_state(city);

    let entry = entry_announcement(&app);
    assert!(entry.contains("First-day objective"));
    assert!(entry.contains("cash cushion"));
    assert!(!entry.contains("trainer-recommended"));
}

#[test]
fn test_owner_operator_first_day_dispatch_board_keeps_business_cost_guidance() {
    let mut app = TestApp::new();
    career(&mut app, "Owner Board", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.money = 12_000.0;
    }

    push_board(
        &mut app,
        vec![job_with(180.0, 1200.0, 8.0), job_with(70.0, 1800.0, 8.0)],
    );

    let entry = entry_announcement(&app);
    assert!(entry.contains("owner-operator gross revenue"));
    assert!(entry.contains("cash cushion"));
    assert!(!entry.contains("trainer-recommended"));
    assert_eq!(index::<JobBoardState>(&app), 0);
    assert!(current_text::<JobBoardState>(&app).starts_with("Job 1 of 2:"));
    assert!(!labels::<JobBoardState>(&app)
        .iter()
        .any(|row| row.starts_with("Recommended dispatch, trainer-recommended:")));
}

// -- tests/test_home_terminal.py (the terminal's Escape) ------------------------------

#[test]
fn test_escape_at_terminal_leaves_for_main_menu_without_lecturing() {
    // Fix A: Escape at the city terminal used to lecture ("Use Quit to main
    // menu...") instead of acting. It must now take the same quit-to-menu
    // path as the Quit to main menu item -- no confirmation, progress
    // autosaves.
    let mut app = TestApp::new();
    career(&mut app, "Esc Driver", "Denver");
    let city = CityMenuState::new(&app.ctx, false);
    app.push_state(city);
    assert!(is::<CityMenuState>(&app));

    key(&mut app, Key::Escape);

    assert!(is::<MainMenuState>(&app));
}

// -- tests/test_business_arc.py (the terminal's truck status) -------------------------

#[test]
fn test_company_driver_truck_status_says_assigned_not_owned() {
    let mut app = TestApp::new();
    career(&mut app, "Assigned Tractor", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.owned_trucks = vec!["rig".to_string(), "heavy_hauler".to_string()]; // legacy save data
        p.truck = "heavy_hauler".to_string();
        p.upgrades.insert("engine_tune".to_string(), 2);
    }
    let mut menu = CityMenuState::new(&app.ctx, false);
    app.clear_speech();
    menu.truck_status(&mut app.ctx);

    let said = app.main_lines().last().cloned().unwrap();
    assert!(said.contains("Assigned Northstar Freight Lines tractor"));
    assert!(!said.contains("Owned tractor"));
    assert!(said.contains("standard rig"));
    assert_eq!(
        profile(&app).truck_specs().max_torque_nm,
        ff_core::sim::vehicle::TruckSpecs::default().max_torque_nm
    );
}

#[test]
fn test_company_driver_board_labels_carrier_gross() {
    let mut app = TestApp::new();
    career(&mut app, "Board Labels", "Chicago");
    let city = CityMenuState::new(&app.ctx, false);
    app.push_state(city);
    key(&mut app, Key::Return);

    assert!(is::<JobBoardState>(&app));
    assert!(with_state::<JobBoardState, _>(&app, |b, _| !b
        .jobs
        .is_empty()));
    assert!(labels::<JobBoardState>(&app)[0].contains("Carrier gross"));
}

#[test]
fn test_owner_operator_job_board_labels_missing_trailer_program() {
    let mut app = TestApp::new();
    career(&mut app, "Trailer Board", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
    }
    let job = Job::new(
        cargo_type("refrigerated").unwrap(),
        12.0,
        "Chicago",
        "cold storage",
        "Milwaukee",
        92.0,
        1800.0,
        7.0,
    );
    push_board(&mut app, vec![job]);

    assert!(labels::<JobBoardState>(&app)[0].contains("Needs Reefer trailer program"));
    assert!(labels::<JobBoardState>(&app)[0].contains("Gross revenue"));
    key(&mut app, Key::Return);
    assert!(profile(&app).active_trip.is_none());
}

#[test]
fn test_owner_operator_job_board_accepts_matching_trailer_program() {
    let mut app = TestApp::new();
    career(&mut app, "Trailer Board Ready", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.trailer_programs = vec!["dry_van".to_string(), "reefer".to_string()];
    }
    let job = Job::new(
        cargo_type("refrigerated").unwrap(),
        12.0,
        "Chicago",
        "cold storage",
        "Milwaukee",
        92.0,
        1800.0,
        7.0,
    );
    push_board(&mut app, vec![job]);

    assert!(labels::<JobBoardState>(&app)[0].contains("Trailer program: Reefer"));
}

#[test]
fn test_own_authority_job_board_labels_owned_trailer_and_program_charge() {
    let job = || {
        Job::new(
            cargo_type("refrigerated").unwrap(),
            12.0,
            "Chicago",
            "cold storage",
            "Milwaukee",
            92.0,
            1800.0,
            7.0,
        )
    };
    let mut app = TestApp::new();
    career(&mut app, "Direct Owned Trailer", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = INDEPENDENT_AUTHORITY.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.trailer_programs = vec!["dry_van".to_string(), "reefer".to_string()];
        p.owned_trailers = vec!["reefer".to_string()];
    }
    push_board(&mut app, vec![job()]);
    let row = labels::<JobBoardState>(&app)[0].clone();
    assert!(row.contains("Direct gross"));
    assert!(row.contains("Owned trailer: Reefer"));
    assert!(row.contains("owned-trailer reserve"));
    app.pop_state();

    career(&mut app, "Direct Program Trailer", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = INDEPENDENT_AUTHORITY.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.trailer_programs = vec!["dry_van".to_string(), "reefer".to_string()];
    }
    push_board(&mut app, vec![job()]);
    let row = labels::<JobBoardState>(&app)[0].clone();
    assert!(row.contains("Trailer program: Reefer"));
    assert!(row.contains("program charge"));
}

#[test]
fn test_direct_freight_board_pays_more_and_uses_direct_label() {
    let app = TestApp::new();
    let world = app.ctx.world;
    let endorsements = ["refrigerated", "heavy_haul", "high_value"];
    let base = JobBoard::seeded(world, 44).offers(
        "Chicago",
        &endorsements,
        OfferOptions {
            level: 25,
            ..OfferOptions::default()
        },
    );
    let direct = JobBoard::seeded(world, 44).offers(
        "Chicago",
        &endorsements,
        OfferOptions {
            level: 25,
            direct_freight: true,
            ..OfferOptions::default()
        },
    );
    assert!(!base.is_empty());
    assert!(!direct.is_empty());
    assert!(direct[0].pay > base[0].pay);
    drop(app);

    let mut app = TestApp::new();
    career(&mut app, "Direct Board", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = INDEPENDENT_AUTHORITY.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.trailer_programs = ["dry_van", "reefer", "flatbed", "bulk"]
            .iter()
            .map(|s| s.to_string())
            .collect();
    }
    push_board(&mut app, vec![direct[0].clone()]);
    let row = labels::<JobBoardState>(&app)[0].clone();
    assert!(row.contains("Direct gross"));
    assert!(row.contains("Trailer program:"));
}

// -- tests/test_dispatch_variety.py (the dispatch-queue half) -------------------------
//
// Owner playtest 2026-07-15: level-1 assigned dispatch bounced the same two
// cities forever (Winslow to Holbrook, again and again). The assignment queue
// stable-partitions fresh candidates so an unseen lane goes first -- score
// order still rules inside each group, and an all-recent board changes
// nothing, so the nudge can delay a repeat but never block dispatch.
// (`remember_lane` itself is pinned by the profile's own tests.)

#[test]
fn test_assignment_prefers_a_lane_not_recently_run() {
    use ff_core::models::jobs::{lane_key, JobBoard, OfferOptions};

    let mut app = TestApp::new();
    career(&mut app, "Variety", "denver_co_us");
    let world = app.ctx.world;
    let jobs = JobBoard::seeded(world, 11).offers(
        "denver_co_us",
        &[] as &[&str],
        OfferOptions {
            count: 4,
            level: 1,
            ..OfferOptions::default()
        },
    );
    let lanes: std::collections::BTreeSet<String> =
        jobs.iter().map(|job| lane_key(world, job)).collect();
    assert!(lanes.len() >= 2, "need lane variety to test");

    let baseline = JobBoardState::new(&app.ctx, jobs.clone());
    let baseline_queue = baseline.assigned_queue().to_vec();
    let first = jobs[baseline_queue[0]].clone();

    // The driver just ran the would-be assignment's lane: dispatch now leads
    // with a different one.
    profile_mut(&mut app).remember_lane(&lane_key(world, &first));
    let varied = JobBoardState::new(&app.ctx, jobs.clone());
    assert_ne!(
        lane_key(world, &jobs[varied.assigned_queue()[0]]),
        lane_key(world, &first)
    );

    // Every candidate recently run: order falls back to plain score order.
    for job in &jobs {
        let lane = lane_key(world, job);
        profile_mut(&mut app).remember_lane(&lane);
    }
    let saturated = JobBoardState::new(&app.ctx, jobs);
    assert_eq!(saturated.assigned_queue(), baseline_queue);
}
