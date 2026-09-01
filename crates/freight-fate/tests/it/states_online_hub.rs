//! Port of `tests/test_online_hub.py`: the Online hub, one main-menu home for
//! the board, account, and sharing.

use crate::states_main_menu_support as menus;
use crate::states_online_support::*;
use ff_core::achievements::ACHIEVEMENTS;
use freight_fate::app::testing::TestApp;
use freight_fate::net::testing::FakeTransport;
use freight_fate::states::account_achievements::AccountAchievementsState;
use freight_fate::states::base::Key;
use freight_fate::states::main_menu::MainMenuState;
use freight_fate::states::online_hub::OnlineHubState;
use freight_fate::states::online_states::DriversOnlineState;
use serde_json::{json, Map, Value};

fn hub(app: &mut TestApp) -> freight_fate::app::SharedState {
    let hub = OnlineHubState::new(&mut app.ctx);
    push(app, hub)
}

#[test]
fn test_main_menu_online_item_opens_the_hub() {
    let mut app = TestApp::new();
    let _board = install_transport(FakeTransport::replying(json!({"drivers": []})));
    app.push_state(MainMenuState::new());
    menus::move_to::<MainMenuState>(&mut app, "Online");
    // Spoken help text exists for F1.
    assert!(!menus::current_help::<MainMenuState>(&app).is_empty());
    menus::key(&mut app, Key::Return);
    assert!(menus::is::<OnlineHubState>(&app));

    let hub = app.state().expect("the hub is on the stack");
    // The board leads because viewing it shares nothing; the
    // online-enhancement master switch sits right under it.
    let rows = labels::<OnlineHubState>(&hub, &app.ctx);
    assert_eq!(rows[0], "Drivers on duty");
    assert_eq!(rows[1], "Account achievements");
    assert_eq!(rows[2], "Online services: on");
    let help = helps::<OnlineHubState>(&hub, &app.ctx);
    for (row, help) in rows.iter().zip(help.iter()).take(rows.len() - 1) {
        assert!(!help.is_empty(), "{row} has no help"); // every row but Back explains itself
    }
}

#[test]
fn test_hub_drivers_board_item_opens_the_board() {
    let mut app = TestApp::new();
    let _board = install_transport(FakeTransport::replying(json!({"drivers": []})));
    let hub = hub(&mut app);
    assert_eq!(
        current_label::<OnlineHubState>(&hub, &app.ctx),
        "Drivers on duty"
    );
    // The board leads because viewing it shares nothing; the
    // online-enhancement master switch sits right under it.
    let rows = labels::<OnlineHubState>(&hub, &app.ctx);
    assert_eq!(rows[0], "Drivers on duty");
    assert_eq!(rows[1], "Account achievements");
    assert_eq!(rows[2], "Online services: on");
    let help = helps::<OnlineHubState>(&hub, &app.ctx);
    for (row, help) in rows.iter().zip(help.iter()).take(rows.len() - 1) {
        assert!(!help.is_empty(), "{row} has no help"); // every row but Back explains itself
    }
    press(&mut app, Key::Return);
    assert!(is_state::<DriversOnlineState>(&app.state().unwrap()));
}

#[test]
fn test_hub_opens_account_achievements_in_catalog_order() {
    assert!(OnlineHubState::INTRO_HELP.contains("work without connecting"));
    let mut app = TestApp::new();
    app.ctx.account_achievements =
        freight_fate::account_achievements::AccountAchievements::empty(app.data_dir.path());
    app.ctx
        .account_achievements
        .record(ACHIEVEMENTS[1].id, None)
        .unwrap();
    let ledger_path = app.data_dir.path().join("account-achievements.json");
    let before = std::fs::read(&ledger_path).unwrap();
    let hub = hub(&mut app);

    move_to::<OnlineHubState>(&mut app, &hub, "Account achievements");
    press(&mut app, Key::Return);
    assert!(is_state::<AccountAchievementsState>(&app.state().unwrap()));

    let account = app.state().unwrap();
    let rows = labels::<AccountAchievementsState>(&account, &app.ctx);
    assert!(rows[0].starts_with(&format!("Locked: {}", ACHIEVEMENTS[0].name)));
    assert!(rows[1].starts_with(&format!("Earned: {}", ACHIEVEMENTS[1].name)));
    assert_eq!(std::fs::read(&ledger_path).unwrap(), before);
}

#[test]
fn test_account_achievements_escape_returns_to_online_hub() {
    let mut app = TestApp::new();
    let hub = hub(&mut app);
    move_to::<OnlineHubState>(&mut app, &hub, "Account achievements");
    press(&mut app, Key::Return);
    assert!(is_state::<AccountAchievementsState>(&app.state().unwrap()));

    press(&mut app, Key::Escape);
    assert!(std::rc::Rc::ptr_eq(&app.state().unwrap(), &hub));
}

/// Right arrow on an action row does nothing; on a toggle row it flips that
/// row's own setting. Pins the adjust list against drifting out of step with
/// build_items when rows are added or reordered.
#[test]
fn test_hub_left_right_adjust_rows_align_with_items() {
    let mut app = TestApp::new();
    let hub = hub(&mut app);
    for label in [
        "Drivers on duty",
        "Open my driver setup page",
        "Restore a cloud backup",
        "Link a Mastodon account",
    ] {
        move_to::<OnlineHubState>(&mut app, &hub, label);
        let before = app.ctx.stack_len();
        press(&mut app, Key::Right);
        assert_eq!(app.ctx.stack_len(), before);
        assert!(std::rc::Rc::ptr_eq(&app.state().unwrap(), &hub));
    }
    move_to::<OnlineHubState>(&mut app, &hub, "Discord presence");
    let before = app.ctx.settings.discord_presence;
    press(&mut app, Key::Right);
    assert_ne!(app.ctx.settings.discord_presence, before);
    press(&mut app, Key::Left);
    assert_eq!(app.ctx.settings.discord_presence, before);
}

/// The path is not something anyone should have to remember.
///
/// Josh's ask, 2026-08-15: a player who needs to rename their driver or
/// sign a computer out has to get to /freight-fate/online/setup, and until
/// now the only way there was typing it. The row opens the address the
/// build actually talks to, staged host included.
#[test]
fn test_hub_opens_the_driver_setup_page_in_a_browser() {
    let mut app = TestApp::new();
    std::env::set_var("FREIGHT_FATE_ONLINE_URL", "https://dev.orinks.net");
    let browser = install_browser(true);
    let hub = hub(&mut app);
    move_to::<OnlineHubState>(&mut app, &hub, "Open my driver setup page");
    press(&mut app, Key::Return);

    assert_eq!(
        browser.opened(),
        vec!["https://dev.orinks.net/freight-fate/online/setup".to_string()]
    );
    // It stays on the hub: nothing to come back to in the game.
    assert!(std::rc::Rc::ptr_eq(&app.state().unwrap(), &hub));
    let said = said(&app);
    assert!(said.contains("driver setup page"));
    assert!(said.contains("computers signed in to your account"));
    std::env::remove_var("FREIGHT_FATE_ONLINE_URL");
}

/// A remote or streamed session is the normal case where the browser
/// never opens, and there is no review cursor to read an address out of.
#[test]
fn test_hub_setup_page_falls_back_to_the_clipboard() {
    let mut app = TestApp::new();
    std::env::set_var("FREIGHT_FATE_ONLINE_URL", "https://dev.orinks.net");
    let _browser = install_browser(false);
    let hub = hub(&mut app);
    move_to::<OnlineHubState>(&mut app, &hub, "Open my driver setup page");
    press(&mut app, Key::Return);
    assert!(said(&app).contains("clipboard"));
    std::env::remove_var("FREIGHT_FATE_ONLINE_URL");
}

/// Neither browser nor clipboard: the address itself has to be spoken,
/// because it is the only way the player can reach the page at all.
#[test]
fn test_hub_setup_page_reads_the_address_out_when_nothing_else_works() {
    let mut app = TestApp::new();
    std::env::set_var("FREIGHT_FATE_ONLINE_URL", "https://dev.orinks.net");
    let _browser = install_browser(false);
    app.ctx.clipboard = Box::new(RefusingClipboard);
    let hub = hub(&mut app);
    move_to::<OnlineHubState>(&mut app, &hub, "Open my driver setup page");
    press(&mut app, Key::Return);
    assert!(said(&app).contains("https://dev.orinks.net/freight-fate/online/setup"));
    std::env::remove_var("FREIGHT_FATE_ONLINE_URL");
}

/// `build_items()` rather than the pushed rows: the rows are only populated
/// on enter(), and these cases are about the label, not the screen.
fn hub_row(app: &mut TestApp, needle: &str) -> (String, String) {
    let mut hub = OnlineHubState::new(&mut app.ctx);
    built_rows(&mut hub, &mut app.ctx)
        .into_iter()
        .find(|(text, _)| text.contains(needle))
        .expect("the row")
}

fn record_conflict(app: &TestApp, name: &str) {
    let mut latest = Map::new();
    latest.insert("latestRevision".to_string(), Value::from(4));
    app.ctx
        .cloud_saves_service()
        .sync_state()
        .record_conflict(name, &latest);
}

/// Brandon (armstrong445), 2026-08-15: a conflict parked his backups at
/// revision 2 against the cloud's 4, and the recovery line told him to open
/// "Restore a cloud backup". He landed on that row five times across twenty
/// minutes and never opened it -- then signed out of every computer and
/// re-activated instead, which cannot clear a conflict. Under the bare name
/// the row promises to REPLACE the career he has just played, which is the
/// opposite of what he wanted, so the waiting decision has to say itself
/// here rather than wait to be discovered.
#[test]
fn test_the_restore_row_says_when_a_career_is_waiting_on_a_choice() {
    let mut app = TestApp::new();
    record_conflict(&app, "armstrong45");
    let (text, help) = hub_row(&mut app, "Restore a cloud backup");

    assert!(text.contains("armstrong45"));
    assert!(text.contains("which copy to keep"));
    // The reason to open a row named "Restore" when you mean to keep your
    // own save has to reach the player, or the name wins the argument.
    assert!(help.contains("not backing up at all until you pick"));
    assert!(help.contains("keeps what you have played"));
    assert!(help.contains("nothing is overwritten until you choose"));
}

/// The warning is only worth anything if it is absent the rest of the
/// time; a row that always claims something needs attention is noise.
#[test]
fn test_the_restore_row_is_its_plain_self_when_nothing_is_waiting() {
    let mut app = TestApp::new();
    let (text, help) = hub_row(&mut app, "Restore a cloud backup");
    assert_eq!(text, "Restore a cloud backup");
    assert!(!help.contains("waiting"));
}

#[test]
fn test_several_waiting_careers_are_counted_not_listed() {
    let mut app = TestApp::new();
    for name in ["a", "b", "c"] {
        record_conflict(&app, name);
    }
    let (text, _) = hub_row(&mut app, "Restore a cloud backup");
    assert!(text.contains("3 careers are waiting"));
}

/// This label is built on every pass through the Online menu. A cloud
/// service that is off, missing or still starting must not take the whole
/// screen down with it. (The Python test made the service accessor raise;
/// `GameContext::cloud_saves_service` cannot fail here, so this pins the
/// nearest real case: a service that is off, with no sync state on disk.)
#[test]
fn test_a_broken_cloud_service_costs_the_row_its_warning_not_the_menu() {
    let mut app = TestApp::new();
    install_cloud(&mut app, FakeTransport::new(), false);
    let (text, _) = hub_row(&mut app, "Restore a cloud backup");
    assert_eq!(text, "Restore a cloud backup");
}
