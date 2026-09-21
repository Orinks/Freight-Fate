//! Synthesized music: the settings rows, menu and Roadhouse rotations, and
//! the fallback when a piece is not ready.

use crate::states_main_menu_support::*;
use freight_fate::app::testing::TestApp;
use freight_fate::states::base::Key;
use freight_fate::states::main_menu::{SettingsCategoryState, SettingsState};

type Cat = SettingsCategoryState;

fn open_audio(app: &mut TestApp) {
    app.push_state(SettingsState::new());
    select::<SettingsState>(app, "Audio");
    assert!(is::<Cat>(app));
}

#[test]
fn defaults_are_original_and_a_fixed_seed() {
    let app = TestApp::new();
    assert!(!app.ctx.settings.synth_music);
    assert_eq!(app.ctx.settings.music_seed, 48213);
}

#[test]
fn music_source_row_toggles_and_persists() {
    let mut app = TestApp::new();
    open_audio(&mut app);
    move_to::<Cat>(&mut app, "Music source");
    assert_eq!(current_label::<Cat>(&app), "Music source: Original");
    key(&mut app, Key::Return);
    assert_eq!(current_label::<Cat>(&app), "Music source: Synthesized");
    assert!(app.ctx.settings.synth_music);
}

#[test]
fn music_seed_row_rolls_a_new_seed_in_range() {
    let mut app = TestApp::new();
    open_audio(&mut app);
    move_to::<Cat>(&mut app, "Music seed");
    assert_eq!(current_label::<Cat>(&app), "Music seed: 48213");
    app.clear_speech();
    key(&mut app, Key::Return);
    let transcript = app.speech().transcript();
    assert!(transcript.contains("New music seed, "), "{transcript}");
    let seed = app.ctx.settings.music_seed;
    assert!((10_000..=99_999).contains(&seed), "{seed}");
    assert_ne!(seed, 48213);
}
