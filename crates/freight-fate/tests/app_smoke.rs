//! The headless `--smoke` run: `tests/test_smoke.py`'s app-level flows, from
//! the boot-and-five-frames check `main --smoke` does through the whole
//! new-career-to-delivery walk, plus the smoke verification of the baked
//! data.

mod states_city_support;

use ff_core::models::business::LEASED_OWNER_OPERATOR;
use ff_core::models::profile::Profile;
use freight_fate::app::testing::TestApp;
use freight_fate::app::{smoke_checks, version, CliOptions};
use freight_fate::states::base::{InputEvent, Key, Menu};
use freight_fate::states::city::{
    CityMenuState, GarageState, JobBoardState, TruckShopState, UpgradeShopState,
};
use freight_fate::states::city_pickup::PickupFacilityState;
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::{DRIVE_PHASE_DELIVERY, DRIVE_PHASE_PICKUP};
use freight_fate::states::driving_menu_states::{ArrivalState, FacilityArrivalState};
use freight_fate::states::driving_pause_states::{AbandonJobConfirmationState, PauseMenuState};
use freight_fate::states::main_menu::{
    CareerStartState, HomeCityState, HomeTerminalState, MainMenuState, NameEntryState,
};
use freight_fate::updater;
use states_city_support::*;

/// `accept_pickup_drive`'s head: New career through the four defaults, which
/// lands on the destination terminal's city hub.
fn new_career_to_city(app: &mut TestApp) {
    app.push_state(MainMenuState::new());
    select::<MainMenuState>(app, "New career");
    assert!(is::<NameEntryState>(app));
    key(app, Key::Return); // default name
    assert!(is::<CareerStartState>(app));
    key(app, Key::Return); // default start
    key(app, Key::Return); // default region
    key(app, Key::Return); // default home terminal
    assert!(is::<CityMenuState>(app));
}

/// ...and on through the assigned dispatch to the deadhead.
fn new_career_to_pickup_drive(app: &mut TestApp) {
    new_career_to_city(app);
    key(app, Key::Return); // job board
    assert!(with_state::<JobBoardState, _>(app, |b, _| b.assigned_mode()));
    key(app, Key::Return); // accept assigned job
    assert!(is::<DrivingState>(app));
}

#[test]
fn a_headless_smoke_run_boots_five_frames_and_exits_cleanly() {
    let mut app = TestApp::new();
    app.run(Some(5));
    assert!(!app.running());
    // The real main menu greets the player on entry, as it does in Python.
    let first = &app.main_lines()[0];
    assert!(
        first.starts_with("Welcome to Freight Fate, version "),
        "unexpected first line: {first}"
    );
    assert!(first.contains("An audio trucking adventure across America."));
}

#[test]
fn smoke_checks_find_every_baked_runtime_file() {
    // get_world, the sound assets, the buff catalog, a curve shard, the
    // facility approaches, the radio catalog, and the secret store.
    let _guard = freight_fate::app::testing::env_lock();
    freight_fate::app::testing::set_headless_env();
    if let Err(e) = smoke_checks() {
        // The secret store is the one check that depends on the machine
        // rather than the build; everything before it must pass.
        assert!(
            e.starts_with("Secret store unreachable"),
            "smoke check failed: {e}"
        );
    }
}

#[test]
fn cli_options_parse_the_three_switches() {
    let opts = CliOptions::parse(["--smoke".to_string(), "--headless".to_string()]);
    assert!(opts.smoke && opts.headless && !opts.controller_diagnostics);
    let opts = CliOptions::parse(["--controller-diagnostics".to_string()]);
    assert!(opts.controller_diagnostics);
    assert_eq!(
        CliOptions::parse(Vec::<String>::new()),
        CliOptions::default()
    );
}

#[test]
fn the_version_is_the_crate_version_from_source() {
    assert_eq!(version(), env!("CARGO_PKG_VERSION"));
}

// `test_garage_offers_partial_fuel_and_repairs_when_cash_is_short` is live in `crates/freight-fate/tests/states_city_shops.rs`.

#[test]
#[ignore = "unblocked, not written: the main-menu hand-off it waited on has landed; port the Python case"]
fn test_full_game_flow_headless() {}

#[test]
fn test_menu_first_letter_navigation() {
    use freight_fate::states::base::{InputEvent, Key, Menu};
    use freight_fate::states::main_menu::MainMenuState;

    let mut app = TestApp::new();
    app.push_state(MainMenuState::new());
    let read = |app: &TestApp| -> (usize, usize, String) {
        let state = app.state().unwrap();
        let state = state.borrow();
        let menu = state.as_any().downcast_ref::<MainMenuState>().unwrap();
        let core = menu.menu();
        (
            core.index,
            core.items.len(),
            core.items[core.index].text(menu, &app.ctx),
        )
    };
    app.dispatch_to_state(&InputEvent::typed('s'));
    assert!(read(&app).2.to_lowercase().starts_with('s'));
    app.dispatch_to_state(&InputEvent::key(Key::End));
    let (index, len, _) = read(&app);
    assert_eq!(index, len - 1);
    app.dispatch_to_state(&InputEvent::key(Key::Home));
    assert_eq!(read(&app).0, 0);
    app.shutdown();
}

#[test]
#[ignore = "unblocked, not written: the main-menu hand-off it waited on has landed; port the Python case"]
fn test_garage_upgrade_and_truck_purchase_flow() {}

#[test]
#[ignore = "unblocked, not written: the main-menu hand-off it waited on has landed; port the Python case"]
fn test_discord_presence_toggle_is_accessible_and_wired() {}

// `test_upgrades_are_money_gated` is live in `crates/freight-fate/tests/states_city_shops.rs`.

// `test_garage_services_tires_and_wash` is live in `crates/freight-fate/tests/states_city_shops.rs`.

// `test_garage_services_brakes_and_engine` is live in `crates/freight-fate/tests/states_city_shops.rs`.

// `test_garage_partial_brake_service_when_broke` is live in `crates/freight-fate/tests/states_city_shops.rs`.

// `test_upgrade_f1_help_explains_player_benefits` is live in `crates/freight-fate/tests/states_city_shops.rs`.

#[test]
fn test_pause_and_abandon_returns_to_city() {
    let mut app = TestApp::new();
    new_career_to_pickup_drive(&mut app);
    assert_eq!(
        with_state::<DrivingState, _>(&app, |d, _| d.phase.to_string()),
        DRIVE_PHASE_PICKUP
    );
    with_state_mut::<DrivingState, _>(&mut app, |d, ctx| {
        d.trip.position_mi = d.trip.total_miles();
        d.trip.finished = true;
        d.trip.truck.velocity_mps = 0.0;
        d.update_frame(ctx, 1.0 / 60.0);
    });
    finish_timed_state(&mut app);
    assert!(is::<PickupFacilityState>(&app));
    key(&mut app, Key::Return); // check in at origin
    key(&mut app, Key::Return); // load at dock, or drop and hook
    finish_timed_state(&mut app);
    key(&mut app, Key::Return); // depart on assigned route
    assert!(is::<DrivingState>(&app));
    let (phase, origin) =
        with_state::<DrivingState, _>(&app, |d, _| (d.phase.to_string(), d.job.origin.clone()));
    assert_eq!(phase, DRIVE_PHASE_DELIVERY);

    key(&mut app, Key::Escape);
    assert!(is::<PauseMenuState>(&app));
    let money = profile(&app).money;
    select::<PauseMenuState>(&mut app, "Abandon job");
    // The abandon now needs a Yes/No confirmation that lands on No.
    assert!(is::<AbandonJobConfirmationState>(&app));
    assert_eq!(
        current_label::<AbandonJobConfirmationState>(&app),
        "No, keep driving"
    );
    key(&mut app, Key::Down); // arrow to Yes
    key(&mut app, Key::Return);
    assert!(is::<CityMenuState>(&app));
    assert_eq!(profile(&app).money, money - 500.0);
    assert_eq!(profile(&app).current_city, origin);
}

#[test]
fn test_abandon_prompt_no_returns_to_pause_menu() {
    let mut app = TestApp::new();
    new_career_to_pickup_drive(&mut app);

    key(&mut app, Key::Escape);
    assert!(is::<PauseMenuState>(&app));
    let pause = app.state().expect("the pause menu");
    let money = profile(&app).money;
    let active_trip = profile(&app).active_trip.clone();
    select::<PauseMenuState>(&mut app, "Abandon job");
    assert!(is::<AbandonJobConfirmationState>(&app));
    // Enter on the default "No" cancels and returns to the pause menu.
    key(&mut app, Key::Return);
    assert!(std::rc::Rc::ptr_eq(
        &app.state().expect("a state"),
        &pause
    ));
    assert_eq!(profile(&app).money, money);
    assert_eq!(profile(&app).active_trip, active_trip);
}
