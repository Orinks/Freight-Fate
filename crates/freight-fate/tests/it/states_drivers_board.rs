//! The drivers board keeping itself up to date while a player reads it.
//!
//! The hazard these pin is the one OnlineSetupState already records: players
//! build positional memory of spoken menus, and `refresh()` preserves the row
//! NUMBER, not which driver is on that row. A list that re-checks on its own
//! therefore has to hold a player's place by person, stay in a stable order,
//! and never speak over them to do it.

use crate::states_online_support::*;
use freight_fate::app::testing::TestApp;
use freight_fate::app::SharedState;
use freight_fate::net::testing::FakeTransport;
use freight_fate::net::NetError;
use freight_fate::states::base::{Key, Menu};
use freight_fate::states::online_states::DriversOnlineState;
use serde_json::{json, Value};

const NOW_MS: f64 = 1_800_000_000_000.0;

fn driver(name: &str, activity: &str) -> Value {
    json!({
        "driverId": format!("{}-1234", name.to_lowercase().replace(' ', "-")),
        "displayName": name,
        "activity": activity,
        "detail": "",
        "updatedAt": NOW_MS,
        "changedAt": NOW_MS,
    })
}

/// The board on the stack, already answered once, with the clock seam open so
/// a re-check happens the moment `update` is called.
fn open_board(app: &mut TestApp) -> SharedState {
    let mut state = DriversOnlineState::new(&mut app.ctx);
    state.threaded = false; // the fetch runs inline, so no waiting on a worker
    state.poll_after_s = 0.0; // and every update() is due a re-check
    push(app, state)
}

fn tick(app: &mut TestApp, shared: &SharedState) {
    with_state::<DriversOnlineState, _>(shared, |s| Menu::update(s, &mut app.ctx, 0.0));
}

fn rows(app: &TestApp, shared: &SharedState) -> Vec<String> {
    labels::<DriversOnlineState>(shared, &app.ctx)
}

fn selected(app: &TestApp, shared: &SharedState) -> String {
    current_label::<DriversOnlineState>(shared, &app.ctx)
}

#[test]
fn test_board_checks_again_on_its_own_without_being_asked() {
    let mut app = TestApp::new();
    let transport = FakeTransport::replying(json!({"drivers": [driver("Road Star", "Driving")]}));
    let _guard = install_transport(transport.clone());
    let shared = open_board(&mut app);

    tick(&mut app, &shared);
    assert!(rows(&app, &shared).iter().any(|r| r.contains("Road Star")));
    let asked_once = transport.requests().len();

    // Another driver sets off. Nobody presses anything.
    transport.set_reply(Some(
        json!({"drivers": [driver("Road Star", "Driving"), driver("Night Owl", "Loading")]}),
    ));
    tick(&mut app, &shared);
    tick(&mut app, &shared);

    assert!(
        transport.requests().len() > asked_once,
        "the board asked again by itself"
    );
    let listed = rows(&app, &shared);
    assert!(listed.iter().any(|r| r.contains("Night Owl")), "{listed:?}");
}

#[test]
fn test_a_check_nobody_asked_for_says_nothing() {
    let mut app = TestApp::new();
    let transport = FakeTransport::replying(json!({"drivers": [driver("Road Star", "Driving")]}));
    let _guard = install_transport(transport.clone());
    let shared = open_board(&mut app);

    tick(&mut app, &shared);
    app.clear_speech();

    transport.set_reply(Some(
        json!({"drivers": [driver("Road Star", "Driving"), driver("Night Owl", "Loading")]}),
    ));
    tick(&mut app, &shared);
    tick(&mut app, &shared);

    // The list changed under the player and the game held its tongue. Speaking
    // here would talk over whatever they were reading, to report something
    // they did not ask about.
    assert!(app.main_lines().is_empty(), "{:?}", app.main_lines());
}

#[test]
fn test_the_cursor_stays_on_the_same_driver_not_the_same_row() {
    let mut app = TestApp::new();
    let transport = FakeTransport::replying(json!({"drivers": [
        driver("Mid Hauler", "Driving"),
        driver("Zeta Hauler", "Driving"),
    ]}));
    let _guard = install_transport(transport.clone());
    let shared = open_board(&mut app);
    tick(&mut app, &shared);

    move_to::<DriversOnlineState>(&mut app, &shared, "Zeta Hauler");
    assert!(selected(&app, &shared).starts_with("Zeta Hauler"));

    // A driver arrives whose name sorts above them, pushing every row down.
    transport.set_reply(Some(json!({"drivers": [
        driver("Mid Hauler", "Driving"),
        driver("Zeta Hauler", "Driving"),
        driver("Alpha Hauler", "Driving"),
    ]})));
    tick(&mut app, &shared);
    tick(&mut app, &shared);

    // Still on the same person. Keeping the row number would have moved them
    // onto Mid Hauler without a word.
    assert!(
        selected(&app, &shared).starts_with("Zeta Hauler"),
        "{}",
        selected(&app, &shared)
    );
}

#[test]
fn test_the_list_is_alphabetical_however_the_site_orders_it() {
    let mut app = TestApp::new();
    let transport = FakeTransport::replying(json!({"drivers": [
        driver("Zeta Hauler", "Driving"),
        driver("Alpha Hauler", "Driving"),
        driver("Mid Hauler", "Driving"),
    ]}));
    let _guard = install_transport(transport);
    let shared = open_board(&mut app);
    tick(&mut app, &shared);

    let listed = rows(&app, &shared);
    let names: Vec<&str> = listed
        .iter()
        .filter(|r| r.contains("Hauler"))
        .map(|r| r.as_str())
        .collect();
    assert!(names[0].starts_with("Alpha Hauler"), "{names:?}");
    assert!(names[1].starts_with("Mid Hauler"), "{names:?}");
    assert!(names[2].starts_with("Zeta Hauler"), "{names:?}");
}

#[test]
fn test_a_driver_signing_off_under_the_cursor_is_kept_until_the_player_moves() {
    let mut app = TestApp::new();
    let transport = FakeTransport::replying(json!({"drivers": [
        driver("Alpha Hauler", "Driving"),
        driver("Zeta Hauler", "Driving"),
    ]}));
    let _guard = install_transport(transport.clone());
    let shared = open_board(&mut app);
    tick(&mut app, &shared);

    move_to::<DriversOnlineState>(&mut app, &shared, "Zeta Hauler");

    // They park up and sign off while the player is standing on their row.
    transport.set_reply(Some(
        json!({"drivers": [driver("Alpha Hauler", "Driving")]}),
    ));
    tick(&mut app, &shared);
    tick(&mut app, &shared);

    // The row is still there, still under the cursor, and honest about it --
    // taking it away would have slid Alpha Hauler silently underneath, and the
    // next Enter would have opened a driver the player never chose.
    let current = selected(&app, &shared);
    assert!(current.starts_with("Zeta Hauler"), "{current}");
    assert!(current.contains("went off duty"), "{current}");

    // Once they move off it, it goes.
    press(&mut app, Key::Up);
    tick(&mut app, &shared);
    let listed = rows(&app, &shared);
    assert!(
        !listed.iter().any(|r| r.starts_with("Zeta Hauler")),
        "{listed:?}"
    );
}

#[test]
fn test_a_player_parked_on_refresh_is_not_slid_onto_back() {
    let mut app = TestApp::new();
    let transport = FakeTransport::replying(json!({"drivers": [
        driver("Alpha Hauler", "Driving"),
        driver("Zeta Hauler", "Driving"),
    ]}));
    let _guard = install_transport(transport.clone());
    let shared = open_board(&mut app);
    tick(&mut app, &shared);

    move_to::<DriversOnlineState>(&mut app, &shared, "Refresh");

    // Both drivers sign off, so the list loses two rows from above the cursor.
    transport.set_reply(Some(json!({"drivers": []})));
    tick(&mut app, &shared);
    tick(&mut app, &shared);

    // Refresh is keyed like the drivers are, so the cursor is still on it.
    // Going by row number would have put the player on Back -- and Enter on
    // Back leaves the screen, which is not what they were about to press.
    assert_eq!(selected(&app, &shared), "Refresh");
}

#[test]
fn test_a_failed_quiet_check_leaves_the_drivers_on_screen() {
    let mut app = TestApp::new();
    let transport = FakeTransport::replying(json!({"drivers": [driver("Road Star", "Driving")]}));
    let _guard = install_transport(transport.clone());
    let shared = open_board(&mut app);
    tick(&mut app, &shared);
    assert!(rows(&app, &shared).iter().any(|r| r.contains("Road Star")));

    // The next check nobody asked for cannot reach the site.
    transport.set_reply(None);
    transport.set_error(Some(NetError::other("OSError", "")));
    tick(&mut app, &shared);
    tick(&mut app, &shared);

    // The player keeps the drivers they had. Emptying the list to report a
    // failed answer to a question they never asked would be worse than saying
    // nothing.
    let listed = rows(&app, &shared);
    assert!(listed.iter().any(|r| r.contains("Road Star")), "{listed:?}");
    assert!(
        !listed.iter().any(|r| r.contains("could not be reached")),
        "{listed:?}"
    );
}

#[test]
fn test_refresh_still_answers_the_player_out_loud() {
    let mut app = TestApp::new();
    let transport = FakeTransport::replying(json!({"drivers": [driver("Road Star", "Driving")]}));
    let _guard = install_transport(transport);
    let shared = open_board(&mut app);
    tick(&mut app, &shared);

    move_to::<DriversOnlineState>(&mut app, &shared, "Refresh");
    app.clear_speech();
    press(&mut app, Key::Return);

    // A check the player DID ask for still says so -- silence is only right
    // for the ones they did not.
    assert!(
        app.main_lines()
            .iter()
            .any(|line| line.contains("Checking the drivers board")),
        "{:?}",
        app.main_lines()
    );
}
