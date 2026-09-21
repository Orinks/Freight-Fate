//! Spoken menu readout: no doubled periods, optional "N of M" position
//! (port of `tests/test_menu_readout.py`).
//!
//! Python built the menu on a `SimpleNamespace` context carrying nothing but
//! `settings.announce_menu_position`. Rust menus read a real `GameContext`,
//! so the rig is a headless [`TestApp`] and the throwaway two-row screen is
//! a [`SimpleMenuState`] -- the same rows, read through the same
//! `current_text`.

use freight_fate::app::testing::TestApp;
use freight_fate::app::GameContext;
use freight_fate::states::base::{end_sentence, Menu, MenuItem, SimpleMenuState};

/// `_menu(announce_position)`: the two-row screen, items already built.
fn menu(ctx: &mut GameContext, announce_position: bool) -> SimpleMenuState {
    ctx.settings.announce_menu_position = announce_position;
    let mut state = SimpleMenuState::new(
        "Menu",
        vec![
            MenuItem::new("Delivered 16 tons to Boston.", |_, _| {}),
            MenuItem::new("Sleep 10 hours", |_, _| {}),
        ],
    );
    state.refresh(ctx, false);
    state
}

#[test]
fn test_end_sentence_adds_one_period_never_two() {
    assert_eq!(end_sentence("Sleep 10 hours"), "Sleep 10 hours.");
    assert_eq!(end_sentence("Delivered to Boston."), "Delivered to Boston.");
    assert_eq!(end_sentence("Ready?"), "Ready?");
    assert_eq!(end_sentence("Note:"), "Note:");
    assert_eq!(end_sentence("trailing space.  "), "trailing space.");
}

#[test]
fn test_menu_readout_never_doubles_the_period() {
    let mut app = TestApp::new();
    let mut m = menu(&mut app.ctx, true);
    // A sentence item keeps its single period before the counter.
    assert_eq!(
        m.current_text(&app.ctx),
        "Delivered 16 tons to Boston. 1 of 2."
    );
    // A plain label still gets its period added.
    m.menu_mut().index = 1;
    assert_eq!(m.current_text(&app.ctx), "Sleep 10 hours. 2 of 2.");
}

#[test]
fn test_menu_position_can_be_suppressed() {
    let mut app = TestApp::new();
    let mut m = menu(&mut app.ctx, false);
    // no "1 of 2"
    assert_eq!(m.current_text(&app.ctx), "Delivered 16 tons to Boston.");
    m.menu_mut().index = 1;
    assert_eq!(m.current_text(&app.ctx), "Sleep 10 hours.");
}
