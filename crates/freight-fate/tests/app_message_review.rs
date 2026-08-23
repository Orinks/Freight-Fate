//! Port of `tests/test_message_review.py`: regression coverage for the
//! speech-review controls.
//!
//! These drive `App::dispatch_to_state`, the one place key events reach a
//! state, so they cover the wiring a player actually presses rather than the
//! log in isolation -- the message-log tests cover the log itself.
//!
//! The Python tests pushed `MainMenuState`; until `states::main_menu` is
//! ported the menu here is a `SimpleMenuState`, which exercises the same
//! review path (a menu on top, not the driving state).

use ff_core::message_log::MessageCategory;
use freight_fate::app::testing::TestApp;
use freight_fate::app::GameContext;
use freight_fate::states::base::{InputEvent, Key, MenuItem, Mods, SimpleMenuState, State};
use freight_fate::states::text_entry::TextEntryState;

fn key_event(key: Key) -> InputEvent {
    InputEvent::key(key)
}

fn ctrl_key_event(key: Key) -> InputEvent {
    InputEvent::key_mods(key, Mods::CTRL)
}

fn menu() -> SimpleMenuState {
    SimpleMenuState::new(
        "Main menu",
        vec![
            MenuItem::new("New career", |_, _| {}),
            MenuItem::new("Continue career", |_, _| {}),
            MenuItem::new("Settings", |_, _| {}),
        ],
    )
}

/// A bare state speaks nothing on entry, so the log holds only what a test
/// puts in it.
struct BareState;
impl State for BareState {}

#[test]
#[ignore = "unblocked: states::driving exists; the case is simply not written yet"]
fn test_hazard_warning_and_outcome_replay_on_a_comma_and_period() {}

#[test]
#[ignore = "unblocked: states::driving exists; the case is simply not written yet"]
fn test_collision_outcome_replays_on_a_and_message_review() {}

#[test]
fn test_name_entry_keeps_punctuation_for_driver_names() {
    // `NameEntryState` is the driver-name `TextEntryState`; the field itself
    // is what keeps the punctuation.
    let mut app = TestApp::new();
    app.push_state(TextEntryState::new("New career", "Driver name", |_, _| {}));
    assert!(app.state().unwrap().borrow().captures_text_input());
    app.dispatch_to_state(&InputEvent::key_text(Key::Comma, ','));
    app.dispatch_to_state(&InputEvent::key_text(Key::Period, '.'));
    let state = app.state().unwrap();
    let state = state.borrow();
    let entry = state.as_any().downcast_ref::<TextEntryState>().unwrap();
    assert_eq!(entry.name(), ",.");
    drop(state);
    app.shutdown();
}

#[test]
fn test_review_works_outside_driving() {
    // The old review path was wired into the driving state alone.
    let mut app = TestApp::new();
    app.push_state(menu());
    app.ctx.say("Fuel is running low.");
    app.ctx.say("Weigh station ahead.");
    app.clear_speech();

    app.dispatch_to_state(&key_event(Key::Comma));
    assert_eq!(app.main_lines().last().unwrap(), "Weigh station ahead.");
    app.dispatch_to_state(&key_event(Key::Comma));
    assert_eq!(app.main_lines().last().unwrap(), "Fuel is running low.");
    app.shutdown();
}

#[test]
fn test_menu_navigation_stays_out_of_the_review_log() {
    let mut app = TestApp::new();
    app.push_state(menu());
    app.ctx.say("Fuel is running low.");
    app.dispatch_to_state(&key_event(Key::Down));
    app.dispatch_to_state(&key_event(Key::Down));

    let texts: Vec<String> = app
        .ctx
        .message_log
        .messages
        .iter()
        .map(|m| m.text.clone())
        .collect();
    assert_eq!(texts.last().unwrap(), "Fuel is running low.");
    app.shutdown();
}

#[test]
#[ignore = "unblocked: states::driving exists; the case is simply not written yet"]
fn test_pausing_mid_run_leaves_no_trace_in_the_history() {}

#[test]
fn test_review_jumps_to_first_and_last() {
    let mut app = TestApp::new();
    app.push_state(BareState);
    for text in ["One.", "Two.", "Three."] {
        app.ctx.say(text);
    }
    app.clear_speech();

    app.dispatch_to_state(&ctrl_key_event(Key::Comma));
    assert_eq!(app.main_lines().last().unwrap(), "One.");
    app.dispatch_to_state(&ctrl_key_event(Key::Period));
    assert_eq!(app.main_lines().last().unwrap(), "Three.");
    app.shutdown();
}

#[test]
fn test_review_replay_stops_the_event_voice() {
    let mut app = TestApp::new();
    app.push_state(menu());
    app.ctx.say_event("Hazard warning.");
    let before = app.speech().stop_event_calls();
    app.dispatch_to_state(&key_event(Key::Comma));
    assert_eq!(app.speech().stop_event_calls(), before + 1);
    app.shutdown();
}

#[test]
#[ignore = "unblocked: states::driving exists; the case is simply not written yet"]
fn test_a_replay_stops_the_event_voice() {}

#[test]
fn test_a_filter_says_what_it_is_holding_back() {
    // The filter keeps the driver's choice, so it must never keep a secret.
    //
    // Tim S sets the category to Event because it makes the cab navigable,
    // and that preference now survives a lapse instead of dropping back to
    // All. The bug that used to be prevented by dropping it -- a settlement
    // sitting invisible behind a filter, with nothing to say it was there --
    // is prevented instead by counting it out loud (2026-08-21).
    let mut app = TestApp::new();
    app.push_state(menu());
    app.ctx
        .message_log
        .add("Brake now! Debris on the road.", MessageCategory::Event);
    app.clear_speech();

    // Wind the filter round to Event, the way the brackets do.
    app.dispatch_to_state(&key_event(Key::RightBracket));
    app.dispatch_to_state(&key_event(Key::RightBracket));
    assert_eq!(app.main_lines().last().unwrap(), "Event messages.");

    // The settlement lands in a category the filter hides.
    app.ctx.message_log.add(
        "Delivery complete. You earned 900 dollars.",
        MessageCategory::General,
    );

    // Stepping to the newest thing the filter shows says what is beyond it.
    app.dispatch_to_state(&key_event(Key::Comma));
    assert_eq!(
        app.main_lines().last().unwrap(),
        "Brake now! Debris on the road. 1 newer message outside this filter."
    );

    // And pressing forward at the end of the list does not answer in silence.
    app.dispatch_to_state(&key_event(Key::Period));
    assert_eq!(
        app.main_lines().last().unwrap(),
        "1 newer message outside this filter."
    );

    // Winding back to All reaches it, and the notice stops.
    app.dispatch_to_state(&key_event(Key::LeftBracket));
    app.dispatch_to_state(&key_event(Key::LeftBracket));
    assert_eq!(app.main_lines().last().unwrap(), "All messages.");
    app.dispatch_to_state(&key_event(Key::Comma));
    assert_eq!(
        app.main_lines().last().unwrap(),
        "Delivery complete. You earned 900 dollars."
    );
    app.shutdown();
}

#[test]
fn test_an_unfiltered_review_never_mentions_a_filter() {
    // The common case stays exactly as quiet as it was.
    let mut app = TestApp::new();
    app.push_state(menu());
    app.ctx.say("Fuel is running low.");
    app.clear_speech();

    app.dispatch_to_state(&key_event(Key::Comma));
    assert_eq!(app.main_lines().last().unwrap(), "Fuel is running low.");
    app.dispatch_to_state(&key_event(Key::Period));
    assert_eq!(app.main_lines().last().unwrap(), "Fuel is running low.");
    app.shutdown();
}

/// Ctrl+C puts the reviewed message on the clipboard and says so.
#[test]
fn ctrl_c_copies_the_message_in_review() {
    let mut app = TestApp::new();
    app.push_state(BareState);
    app.ctx.say("Weigh station ahead.");
    app.dispatch_to_state(&key_event(Key::Comma));
    app.clear_speech();
    app.dispatch_to_state(&ctrl_key_event(Key::C));
    assert_eq!(
        app.ctx.clipboard.get_text().as_deref(),
        Some("Weigh station ahead.")
    );
    assert_eq!(app.main_lines(), vec!["Message copied to clipboard."]);
    app.shutdown();
}

/// A state that takes typed text keeps every review key for itself.
#[test]
fn text_capture_declines_the_review_keys() {
    struct Field;
    impl State for Field {
        fn captures_text_input(&self) -> bool {
            true
        }
        fn handle_event(&mut self, ctx: &mut GameContext, _event: &InputEvent) {
            ctx.say("field got it");
        }
    }
    let mut app = TestApp::new();
    app.push_state(Field);
    app.ctx.say("One.");
    app.clear_speech();
    app.dispatch_to_state(&key_event(Key::Comma));
    assert_eq!(app.main_lines(), vec!["field got it"]);
    app.shutdown();
}
