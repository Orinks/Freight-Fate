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

#[test]
fn the_three_classics_play_from_the_executable() {
    freight_fate::audio::classic_music::register();
    for key in [
        "classic_menu_theme",
        "classic_open_road",
        "classic_night_haul",
    ] {
        let (bytes, ext) = freight_fate::audio::assets::asset_bytes(
            &format!("music/{key}"),
            freight_fate::audio::assets::MUSIC_EXTENSIONS,
        )
        .unwrap_or_else(|| panic!("{key} missing"));
        assert_eq!(ext, "ogg");
        assert_eq!(&bytes[..4], b"OggS");
    }
}

/// A brand-new career sits at the title screen -- which plays
/// `classic_menu_theme` before any drive exists -- so app startup itself,
/// not just a driving-state constructor, must register the classics. Unlike
/// the test above, this one never calls `classic_music::register()` by
/// hand: it removes the registration first, so it can only pass if
/// `TestApp::new()` (which goes through the same `App::build()` real
/// launches use) put it back on its own.
#[test]
fn the_menu_theme_is_registered_by_app_startup_alone() {
    ff_core::assets_pack::unregister_generated_sound("music/classic_menu_theme");
    let _app = TestApp::new();
    let (bytes, ext) = freight_fate::audio::assets::asset_bytes(
        "music/classic_menu_theme",
        freight_fate::audio::assets::MUSIC_EXTENSIONS,
    )
    .expect("classic_menu_theme missing after a fresh TestApp::new()");
    assert_eq!(ext, "ogg");
    assert_eq!(&bytes[..4], b"OggS");
}

#[test]
fn synthesized_menus_open_on_headlights_west_and_hold_no_pack_music() {
    let mut app = TestApp::new();
    app.ctx.settings.synth_music = true;
    let original = ff_core::music::select_menu_music_sequence(None);
    let refs: Vec<&str> = original.iter().map(String::as_str).collect();
    let track = app.ctx.play_music_sequence("menu", &refs);
    assert_eq!(track, ff_core::music_synth::CLASSIC_MENU);
}

#[test]
fn an_unready_piece_falls_back_to_its_classic_and_is_requested() {
    use ff_core::music_synth::{StyleId, SynthKey, SynthWorker, CLASSIC_MENU};
    let mut app = TestApp::new();
    let key = SynthKey {
        style: StyleId::Regional,
        music_seed: 5,
        index: 0,
    }
    .key();
    assert_eq!(app.ctx.resolve_synth(&key), CLASSIC_MENU);
    // The worker was asked: within a bounded wait the piece is published.
    let t = std::time::Instant::now();
    while !SynthWorker::is_ready(&key) && t.elapsed().as_secs() < 60 {
        std::thread::sleep(std::time::Duration::from_millis(20));
    }
    assert_eq!(app.ctx.resolve_synth(&key), key);
}

#[test]
fn switching_back_to_original_restores_the_soundtrack() {
    let mut app = TestApp::new();
    let original = ff_core::music::select_menu_music_sequence(None);
    let refs: Vec<&str> = original.iter().map(String::as_str).collect();
    app.ctx.settings.synth_music = true;
    app.ctx.play_music_sequence("menu", &refs);
    app.ctx.settings.synth_music = false;
    app.ctx.restart_music();
    assert_eq!(app.ctx.music_rotation_track(), Some(original[0].as_str()));
}
