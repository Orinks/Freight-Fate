//! The headless `--smoke` run (`tests/test_smoke.py`'s app-level flows need
//! the city and driving states; what can run today is the boot-and-five-
//! frames check `main --smoke` does, plus the smoke verification of the
//! baked data).

use freight_fate::app::testing::TestApp;
use freight_fate::app::{smoke_checks, version, CliOptions};

#[test]
fn a_headless_smoke_run_boots_five_frames_and_exits_cleanly() {
    let mut app = TestApp::new();
    app.run(Some(5));
    assert!(!app.running());
    // The placeholder first screen spoke its title and row, as a menu does.
    assert_eq!(app.main_lines()[0], "Freight Fate.");
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

#[test]
#[ignore = "needs states::city (garage)"]
fn test_garage_offers_partial_fuel_and_repairs_when_cash_is_short() {}

#[test]
#[ignore = "needs states::driving (the career-to-delivery flow; the main-menu half is states_main_menu.rs)"]
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
#[ignore = "needs states::city"]
fn test_garage_upgrade_and_truck_purchase_flow() {}

#[test]
#[ignore = "needs states::online_hub (the Discord row lives on the Online menu)"]
fn test_discord_presence_toggle_is_accessible_and_wired() {}

#[test]
#[ignore = "needs states::city"]
fn test_upgrades_are_money_gated() {}

#[test]
#[ignore = "needs states::city"]
fn test_garage_services_tires_and_wash() {}

#[test]
#[ignore = "needs states::city"]
fn test_garage_services_brakes_and_engine() {}

#[test]
#[ignore = "needs states::city"]
fn test_garage_partial_brake_service_when_broke() {}

#[test]
#[ignore = "needs states::city"]
fn test_upgrade_f1_help_explains_player_benefits() {}

#[test]
#[ignore = "needs states::driving"]
fn test_pause_and_abandon_returns_to_city() {}

#[test]
#[ignore = "needs states::driving"]
fn test_abandon_prompt_no_returns_to_pause_menu() {}
