//! The settings screens: port of the menu tests in
//! `tests/test_settings_menu.py` (the pure `Settings` tests live in
//! `ff_core::settings`).
//!
//! Where the Python wrote a settings file before `App()` to set
//! `settings_layout_notice_from`, these set the loaded field directly:
//! `TestApp` writes its own settings file on the way up, and the loader's
//! reading of an old file is pinned in the `ff_core` settings tests.

mod states_main_menu_support;

use ff_core::models::profile::Profile;
use ff_core::settings::{Settings, PACE_RETIRED_NOTICES};
use ff_core::sim::season::{date_text, real_clock_game_hours};
use freight_fate::app::testing::{env_lock, set_headless_env, TempDir, TestApp};
use freight_fate::app::App;
use freight_fate::speech::CaptureSpeech;
use freight_fate::states::base::{Key, Menu, State};
use freight_fate::states::main_menu::{
    GameplaySettingsState, MainMenuState, SettingsCategoryState, SettingsState,
};
use states_main_menu_support::*;

// Gameplay is now a category with its own submenu; these four screens live one
// level down from the Settings picker, under the "Gameplay" row.
const GAMEPLAY_SUBCATEGORIES: [&str; 4] = [
    "Driving assistance",
    "Difficulty and hours of service",
    "World and traffic",
    "Controls",
];

/// Open a settings screen by its spoken title.
///
/// Handles both the top-level categories (Audio, Speech, ...) and the four
/// Gameplay subcategories, routing through the Gameplay parent for the
/// latter.
fn open_settings_category(app: &mut TestApp, label: &str) {
    app.push_state(SettingsState::new());
    if GAMEPLAY_SUBCATEGORIES.contains(&label) {
        select::<SettingsState>(app, "Gameplay");
        assert!(is::<GameplaySettingsState>(app));
        select::<GameplaySettingsState>(app, label);
        assert!(is::<SettingsCategoryState>(app));
        return;
    }
    select::<SettingsState>(app, label);
    assert!(is::<SettingsCategoryState>(app));
}

/// Open Settings then the Gameplay parent.
fn open_gameplay_parent(app: &mut TestApp) {
    app.push_state(SettingsState::new());
    select::<SettingsState>(app, "Gameplay");
    assert!(is::<GameplaySettingsState>(app));
}

type Cat = SettingsCategoryState;

fn cat_rows(app: &mut TestApp, category: &str) -> Vec<(String, String)> {
    app.push_state(SettingsCategoryState::new(category));
    let rows = labels_and_help::<Cat>(app);
    app.pop_state();
    rows
}

#[test]
fn test_settings_menu_cycles_hours_of_service() {
    let mut app = TestApp::new();
    assert_eq!(app.ctx.settings.hos_mode, "realistic");
    open_settings_category(&mut app, "Difficulty and hours of service");
    move_to::<Cat>(&mut app, "Hours of service");
    key(&mut app, Key::Return);
    assert_eq!(app.ctx.settings.hos_mode, "relaxed");
    key(&mut app, Key::Return);
    assert_eq!(app.ctx.settings.hos_mode, "realistic");
    key(&mut app, Key::Left);
    assert_eq!(app.ctx.settings.hos_mode, "relaxed");
}

#[test]
fn test_settings_menu_cycles_lane_keeping() {
    let mut app = TestApp::new();
    assert_eq!(app.ctx.settings.lane_keeping, "off"); // the realistic default
    open_settings_category(&mut app, "Driving assistance");
    move_to::<Cat>(&mut app, "Lane keeping");
    key(&mut app, Key::Return);
    assert_eq!(app.ctx.settings.lane_keeping, "full");
    key(&mut app, Key::Return);
    assert_eq!(app.ctx.settings.lane_keeping, "partial");
    key(&mut app, Key::Left);
    assert_eq!(app.ctx.settings.lane_keeping, "full");
}

#[test]
fn test_lane_keeping_row_speaks_its_consequence_not_a_bare_value() {
    // A bare "off" would be read across from the rows around it, where off
    // means less help. Here it means the hardest mode.
    let mut app = TestApp::new();
    open_settings_category(&mut app, "Driving assistance");
    move_to::<Cat>(&mut app, "Lane keeping");
    assert_eq!(
        current_label::<Cat>(&app),
        "Lane keeping: off, you hold the lane and take your own exits"
    );
    key(&mut app, Key::Return);
    assert_eq!(
        current_label::<Cat>(&app),
        "Lane keeping: full, the truck holds the lane and takes your exits"
    );
    key(&mut app, Key::Return);
    assert!(current_label::<Cat>(&app).contains("you steer with help"));
}

#[test]
fn test_lane_keeping_row_explains_its_rename_to_returning_players() {
    // A blind player cannot see a row change name. The row says it, built
    // from the value they actually ended up with, and only for a settings
    // file that really carried the old key.
    let mut app = TestApp::new();
    app.ctx.settings.lane_keeping = "full".to_string();
    app.ctx.settings.lane_keeping_rename_notice_left = 3;
    open_settings_category(&mut app, "Driving assistance");
    move_to::<Cat>(&mut app, "Lane keeping");
    let spoken = app.main_lines();
    let notice: Vec<&String> = spoken
        .iter()
        .filter(|line| line.contains("used to be Lane drift"))
        .collect();
    assert!(!notice.is_empty());
    let last = notice.last().unwrap();
    assert!(last.contains("yours read off"));
    assert!(last.contains("the truck still holds the lane and takes your exits"));
    assert_eq!(app.ctx.settings.lane_keeping_rename_notice_left, 2);
}

#[test]
fn test_an_unreadable_lane_value_is_announced_not_taken_in_silence() {
    // Falling back to full is right; falling back silently is not. It
    // deletes the destination-exit decision, and nothing later in the drive
    // would tell the player why their exits are being taken.
    let mut app = TestApp::new();
    app.ctx.settings.lane_keeping_unreadable = true;
    let mut menu = MainMenuState::new();
    menu.announce_entry(&mut app.ctx);
    let spoken = app.main_lines();
    assert!(spoken
        .iter()
        .any(|line| line.contains("lane keeping setting could not be read")));
    assert!(spoken
        .iter()
        .any(|line| line.contains("Settings, Gameplay, Driving assistance")));
    // Said once, not on every trip back to the main menu.
    app.clear_speech();
    MainMenuState::new().announce_entry(&mut app.ctx);
    assert!(!app
        .main_lines()
        .iter()
        .any(|line| line.contains("lane keeping setting could not be read")));
}

#[test]
fn test_the_rename_notice_stops_after_its_budget() {
    let mut app = TestApp::new();
    app.ctx.settings.lane_keeping_rename_notice_left = 0;
    open_settings_category(&mut app, "Driving assistance");
    move_to::<Cat>(&mut app, "Lane keeping");
    assert!(!app
        .main_lines()
        .iter()
        .any(|line| line.contains("used to be Lane drift")));
}

// -- the Variant B reorganization: the Gameplay submenu tree ------------------------

// The four Gameplay subcategories and the row each must own, by the leading
// words of the spoken label. This doubles as the membership spec: a setting in
// the wrong screen, or missing from every screen, fails here.
fn gameplay_subcategory_rows(category: &str) -> &'static [&'static str] {
    match category {
        "assistance" => &[
            "Driving assistance preset",
            "Automatic emergency braking",
            "Lane-departure warning",
            "Stop-and-go assistance",
            "Lane centering assistance",
            "Descent speed control",
            "Exit speed assistance",
            "Destination approach assistance",
            "Planned rest-stop stopping assistance",
            "Curve speed assistance",
            "Route-transition assistance",
            "Latching pedals",
            "Predictive cruise",
            "Curve callouts",
            "Speed keeper",
            "Lane keeping",
            "Following gap",
            "Back",
        ],
        "difficulty" => &["Driving mode", "Hours of service", "Back"],
        "world" => &[
            "Weather source",
            "Traffic source",
            "Parking source",
            "Live weather controls calendar",
            "Back",
        ],
        "controls" => &[
            "Units",
            "Transmission",
            "Automatic direction changes",
            "Controller",
            "Haptics",
            "Back",
        ],
        _ => unreachable!(),
    }
}

#[test]
fn test_gameplay_is_a_parent_of_four_subcategories() {
    let mut app = TestApp::new();
    open_gameplay_parent(&mut app);
    assert_eq!(
        labels::<GameplaySettingsState>(&app),
        vec![
            "Driving assistance",
            "Difficulty and hours of service",
            "World and traffic",
            "Controls",
            "Back",
        ]
    );
}

#[test]
fn test_each_gameplay_subcategory_has_exactly_its_rows() {
    let mut app = TestApp::new();
    for category in ["assistance", "controls", "difficulty", "world"] {
        let rows = cat_rows(&mut app, category);
        let expected = gameplay_subcategory_rows(category);
        assert_eq!(rows.len(), expected.len(), "{category}");
        for ((actual, _), prefix) in rows.iter().zip(expected) {
            assert!(
                actual.starts_with(prefix),
                "{category}: {actual} vs {prefix}"
            );
        }
        // Every non-Back screen stays short enough to hold in the ear.
        assert!(rows.len() <= 12 || category == "assistance");
    }
}

/// Every settings row reachable in the whole Settings tree, as
/// (screen, label, help) triples: the picker, the Gameplay parent, and each
/// category screen. The Online hub is its own menu and out of scope here.
fn all_settings_rows(app: &mut TestApp) -> Vec<(String, String, String)> {
    let mut rows = Vec::new();
    app.push_state(SettingsState::new());
    for (label, help) in labels_and_help::<SettingsState>(app) {
        rows.push(("picker".to_string(), label, help));
    }
    app.pop_state();
    app.push_state(GameplaySettingsState::new());
    for (label, help) in labels_and_help::<GameplaySettingsState>(app) {
        rows.push(("gameplay".to_string(), label, help));
    }
    app.pop_state();
    for category in [
        "assistance",
        "difficulty",
        "world",
        "controls",
        "audio",
        "speech",
        "updates",
        "reports",
    ] {
        for (label, help) in cat_rows(app, category) {
            rows.push((category.to_string(), label, help));
        }
    }
    rows
}

#[test]
fn test_exactly_one_speed_keeper_row_in_the_whole_tree() {
    let mut app = TestApp::new();
    let rows = all_settings_rows(&mut app);
    let speed_keeper_rows: Vec<_> = rows
        .iter()
        .filter(|(_, label, _)| label.starts_with("Speed keeper"))
        .collect();
    assert_eq!(speed_keeper_rows.len(), 1, "{speed_keeper_rows:?}");
    assert_eq!(speed_keeper_rows[0].0, "assistance");
}

#[test]
fn test_no_dead_pointer_stub_rows_remain() {
    let mut app = TestApp::new();
    let rows = all_settings_rows(&mut app);
    let stubs: Vec<_> = rows
        .iter()
        .filter(|(_, _, help)| help.to_lowercase().contains("has moved to"))
        .collect();
    assert!(stubs.is_empty(), "{stubs:?}");
    let lane_rows: Vec<_> = rows
        .iter()
        .filter(|(_, label, _)| label.starts_with("Lane keeping"))
        .collect();
    assert_eq!(lane_rows.len(), 1);
    assert_eq!(lane_rows[0].0, "assistance");
}

#[test]
fn test_every_gameplay_setting_stays_reachable_after_the_split() {
    let mut app = TestApp::new();
    let rows = all_settings_rows(&mut app);
    let reachable = |screen: &str, prefix: &str| {
        rows.iter()
            .any(|(s, label, _)| s == screen && label.starts_with(prefix))
    };
    // Moved out of flat Gameplay.
    assert!(reachable("controls", "Units"));
    assert!(reachable("controls", "Transmission"));
    assert!(reachable("controls", "Automatic direction changes"));
    assert!(reachable("controls", "Controller"));
    assert!(reachable("controls", "Haptics"));
    assert!(reachable("assistance", "Speed keeper"));
    assert!(!reachable("controls", "Speed keeper"));
    assert!(reachable("difficulty", "Driving mode"));
    assert!(reachable("difficulty", "Hours of service"));
    // The overspeed warning lost its row: it no longer fires at speeds
    // cruise itself picks, so there is nothing to turn off.
    assert!(!rows
        .iter()
        .any(|(_, label, _)| label.starts_with("Overspeed warning")));
    // Moved out of Speech and weather.
    assert!(reachable("world", "Weather source"));
    assert!(reachable("world", "Traffic source"));
    assert!(reachable("world", "Parking source"));
    assert!(reachable("world", "Live weather controls calendar"));
    // The world-data rows no longer appear in Speech.
    assert!(!reachable("speech", "Weather source"));
    assert!(!reachable("speech", "Traffic source"));
    assert!(!reachable("speech", "Parking source"));
    assert!(!reachable("speech", "Live weather controls calendar"));
}

#[test]
fn test_settings_menu_toggles_speed_keeper() {
    let mut app = TestApp::new();
    assert!(app.ctx.settings.speed_keeper);
    open_settings_category(&mut app, "Driving assistance");
    move_to::<Cat>(&mut app, "Speed keeper");
    key(&mut app, Key::Return);
    assert!(!app.ctx.settings.speed_keeper);
    key(&mut app, Key::Left);
    assert!(app.ctx.settings.speed_keeper);
}

#[test]
fn test_settings_menu_cycles_automatic_direction_changes() {
    let mut app = TestApp::new();
    assert_eq!(app.ctx.settings.automatic_direction_changes, "simple");
    open_settings_category(&mut app, "Controls");
    move_to::<Cat>(&mut app, "Automatic direction changes");
    assert!(
        current_help::<Cat>(&app).starts_with("Both styles change direction with a fresh press")
    );
    key(&mut app, Key::Return);
    assert_eq!(app.ctx.settings.automatic_direction_changes, "deliberate");
    assert_eq!(Settings::load().automatic_direction_changes, "deliberate");
    assert_eq!(
        current_label::<Cat>(&app),
        "Automatic direction changes: deliberate"
    );
    key(&mut app, Key::Left);
    assert_eq!(app.ctx.settings.automatic_direction_changes, "simple");
}

#[test]
fn test_settings_menu_toggles_jake_voice_and_persists() {
    let mut app = TestApp::new();
    assert_eq!(app.ctx.settings.jake_voice, "real");
    open_settings_category(&mut app, "Audio");
    move_to::<Cat>(&mut app, "Engine brake voice");
    assert_eq!(current_label::<Cat>(&app), "Engine brake voice: recorded");
    assert!(current_help::<Cat>(&app).starts_with("Recorded is the real engine brake growl"));
    key(&mut app, Key::Return);
    assert_eq!(app.ctx.settings.jake_voice, "classic");
    assert_eq!(Settings::load().jake_voice, "classic");
    assert_eq!(current_label::<Cat>(&app), "Engine brake voice: classic");
    key(&mut app, Key::Left);
    assert_eq!(app.ctx.settings.jake_voice, "real");
    assert_eq!(current_label::<Cat>(&app), "Engine brake voice: recorded");
}

#[test]
fn test_settings_menu_saves_each_change() {
    let mut app = TestApp::new();
    open_settings_category(&mut app, "Controls");
    assert!(app.ctx.settings.imperial_units);
    move_to::<Cat>(&mut app, "Units");
    key(&mut app, Key::Return);
    assert!(!app.ctx.settings.imperial_units);
    assert!(!Settings::load().imperial_units);
}

#[test]
fn test_live_weather_calendar_setting_defaults_on_and_persists() {
    let mut app = TestApp::new();
    assert!(app.ctx.settings.live_weather_controls_calendar);
    open_settings_category(&mut app, "World and traffic");
    move_to::<Cat>(&mut app, "Live weather controls calendar");
    assert!(current_help::<Cat>(&app).contains("today's real date"));
    key(&mut app, Key::Return);
    assert!(!app.ctx.settings.live_weather_controls_calendar);
    assert!(!Settings::load().live_weather_controls_calendar);
    assert_eq!(
        current_label::<Cat>(&app),
        "Live weather controls calendar: off"
    );
}

#[test]
fn test_disabling_live_calendar_anchors_established_career_to_today() {
    let mut app = TestApp::new();
    let mut profile = Profile::named("Established Driver");
    profile.game_hours = 54.0;
    app.ctx.profile = Some(profile);
    let original_game_hours = 54.0;
    open_settings_category(&mut app, "World and traffic");
    move_to::<Cat>(&mut app, "Live weather controls calendar");
    key(&mut app, Key::Return);
    let target = real_clock_game_hours(None);
    let p = app.ctx.profile.as_ref().unwrap();
    assert!(!app.ctx.settings.live_weather_controls_calendar);
    assert_eq!(p.game_hours, original_game_hours);
    assert_eq!(date_text(p.calendar_game_hours()), date_text(target));
    assert_eq!(p.calendar_game_hours() % 24.0, original_game_hours % 24.0);
}

#[test]
fn test_disabling_live_calendar_keeps_new_career_on_march_21() {
    let mut app = TestApp::new();
    app.ctx.profile = Some(Profile::named("Brand New Driver"));
    open_settings_category(&mut app, "World and traffic");
    move_to::<Cat>(&mut app, "Live weather controls calendar");
    key(&mut app, Key::Return);
    let p = app.ctx.profile.as_ref().unwrap();
    assert_eq!(p.calendar_offset_days, 0);
    assert_eq!(p.calendar_game_hours(), 6.0);
}

#[test]
fn test_settings_menu_volume_survives_new_app_session() {
    // Two apps over one data directory, by hand: `TestApp` writes its own
    // settings file on the way up, which would erase the first session's.
    let _guard = env_lock();
    set_headless_env();
    let data_dir = TempDir::new("ff-rust-settings-session");
    std::env::set_var("FREIGHT_FATE_DATA_DIR", data_dir.path().join("data"));
    {
        let mut app = App::new_headless(Box::new(CaptureSpeech::new()));
        app.push_state(SettingsState::new());
        app.dispatch_to_state(&freight_fate::states::base::InputEvent::key(Key::Down));
        app.dispatch_to_state(&freight_fate::states::base::InputEvent::key(Key::Return));
        let audio = |app: &App| {
            let state = app.state().unwrap();
            let s = state.borrow();
            s.as_any()
                .downcast_ref::<Cat>()
                .map(|c| c.title().to_string())
        };
        assert_eq!(audio(&app).as_deref(), Some("Audio"));
        loop {
            let state = app.state().unwrap();
            let label = {
                let s = state.borrow();
                let c = s.as_any().downcast_ref::<Cat>().unwrap();
                c.menu().items[c.menu().index].text(c, &app.ctx)
            };
            if label.starts_with("Music volume") {
                break;
            }
            app.dispatch_to_state(&freight_fate::states::base::InputEvent::key(Key::Down));
        }
        app.dispatch_to_state(&freight_fate::states::base::InputEvent::key(Key::Right));
        assert_eq!(app.ctx.settings.music_volume, 0.6);
        assert_eq!(Settings::load().music_volume, 0.6);
        loop {
            let state = app.state().unwrap();
            let label = {
                let s = state.borrow();
                let c = s.as_any().downcast_ref::<Cat>().unwrap();
                c.menu().items[c.menu().index].text(c, &app.ctx)
            };
            if label.starts_with("Weather sounds volume") {
                break;
            }
            app.dispatch_to_state(&freight_fate::states::base::InputEvent::key(Key::Up));
        }
        app.dispatch_to_state(&freight_fate::states::base::InputEvent::key(Key::Right));
        assert_eq!(app.ctx.settings.weather_volume, 0.75);
        assert_eq!(Settings::load().weather_volume, 0.75);
        app.dispatch_to_state(&freight_fate::states::base::InputEvent::key(Key::Left));
        assert_eq!(app.ctx.settings.weather_volume, 0.65);
        assert_eq!(Settings::load().weather_volume, 0.65);
        app.shutdown();
    }
    let mut next_app = App::new_headless(Box::new(CaptureSpeech::new()));
    assert_eq!(next_app.ctx.settings.music_volume, 0.6);
    assert_eq!(next_app.ctx.audio.music_volume(), 0.6);
    assert_eq!(next_app.ctx.settings.weather_volume, 0.65);
    assert_eq!(next_app.ctx.audio.weather_volume(), 0.65);
    next_app.shutdown();
}

#[test]
fn test_settings_menu_f1_has_help_for_every_item() {
    let mut app = TestApp::new();
    app.push_state(SettingsState::new());
    let rows = labels_and_help::<SettingsState>(&app);
    for (i, (label, help)) in rows.iter().enumerate() {
        set_index::<SettingsState>(&mut app, i);
        let text = current_help::<SettingsState>(&app);
        let expected = if help.is_empty() {
            format!("{label}.")
        } else {
            help.clone()
        };
        assert_eq!(text, expected);
    }
    app.pop_state();
    app.push_state(GameplaySettingsState::new());
    let rows = labels_and_help::<GameplaySettingsState>(&app);
    for (i, (label, help)) in rows.iter().enumerate() {
        set_index::<GameplaySettingsState>(&mut app, i);
        let text = current_help::<GameplaySettingsState>(&app);
        let expected = if help.is_empty() {
            format!("{label}.")
        } else {
            help.clone()
        };
        assert_eq!(text, expected);
    }
    app.pop_state();
    for category in [
        "assistance",
        "difficulty",
        "world",
        "controls",
        "audio",
        "speech",
        "updates",
        "reports",
    ] {
        app.push_state(SettingsCategoryState::new(category));
        let rows = labels_and_help::<Cat>(&app);
        for (i, (label, help)) in rows.iter().enumerate() {
            set_index::<Cat>(&mut app, i);
            let text = current_help::<Cat>(&app);
            let expected = if help.is_empty() {
                format!("{label}.")
            } else {
                help.clone()
            };
            assert_eq!(text, expected);
            let intro = with_state::<Cat, _>(&app, |c, _| c.menu().intro_help.clone());
            assert!(!text.contains(&intro));
        }
        app.pop_state();
    }
}

#[test]
fn test_haptics_help_explains_road_seam_feedback() {
    let mut app = TestApp::new();
    open_settings_category(&mut app, "Controls");
    move_to::<Cat>(&mut app, "Haptics");
    app.clear_speech();
    key(&mut app, Key::F1);
    assert!(app
        .main_lines()
        .iter()
        .any(|text| text.contains("road seams")));
}

#[test]
fn test_settings_menu_uses_category_submenus() {
    let mut app = TestApp::new();
    app.push_state(SettingsState::new());
    assert_eq!(
        labels::<SettingsState>(&app),
        vec![
            "Gameplay",
            "Audio",
            "Speech",
            "Online",
            "Updates",
            "Problem reports",
            "Back",
        ]
    );
    select::<SettingsState>(&mut app, "Audio");
    assert!(is::<Cat>(&app));
    assert_eq!(
        with_state::<Cat, _>(&app, |c, _| c.title().to_string()),
        "Audio"
    );
    assert!(current_label::<Cat>(&app).starts_with("Master volume"));
    key(&mut app, Key::Escape);
    assert!(is::<SettingsState>(&app));
    app.clear_speech();
    key(&mut app, Key::Escape);
    assert!(app
        .main_lines()
        .iter()
        .any(|line| line == "Settings saved."));
}

#[test]
fn test_driving_assistance_preset_keyboard_path_and_custom_transition() {
    let mut app = TestApp::new();
    open_settings_category(&mut app, "Driving assistance");
    // The shipped defaults now ARE the realistic preset, field for field,
    // so the row can finally say so honestly rather than reading Custom
    // over a combination no preset described.
    assert_eq!(
        labels::<Cat>(&app)[0],
        "Driving assistance preset: Realistic"
    );
    assert_eq!(app.ctx.settings.lane_keeping, "off");
    key(&mut app, Key::Right);
    assert_eq!(app.ctx.settings.driving_assistance_preset, "balanced");
    assert!(app.ctx.settings.lane_centering_assist);
    assert_eq!(app.ctx.settings.time_scale, 10.0);
    assert_eq!(app.ctx.settings.hos_mode, "realistic");
    key(&mut app, Key::Down);
    key(&mut app, Key::Return);
    assert_eq!(app.ctx.settings.driving_assistance_preset, "custom");
    assert_eq!(labels::<Cat>(&app)[0], "Driving assistance preset: Custom");
    assert_eq!(Settings::load().driving_assistance_preset, "custom");
    let spoken = app.main_lines();
    assert!(spoken
        .iter()
        .any(|line| line.contains("Automatic emergency braking: off")));
    assert!(spoken
        .iter()
        .any(|line| line == "Driving assistance preset: Custom."));
    let original_index = index::<Cat>(&app);
    key(&mut app, Key::Home);
    key(&mut app, Key::Left);
    assert_eq!(app.ctx.settings.driving_assistance_preset, "all");
    assert_eq!(
        current_label::<Cat>(&app),
        "Driving assistance preset: All assists"
    );
    key(&mut app, Key::Right);
    assert_eq!(app.ctx.settings.driving_assistance_preset, "realistic");
    assert_eq!(original_index, 1);

    // A toggle that lands on Custom queues the preset note after the
    // spoken on/off state instead of interrupting it, and later toggles
    // while already Custom do not repeat the note.
    app.clear_speech();
    key(&mut app, Key::Down);
    key(&mut app, Key::Return);
    assert_eq!(app.ctx.settings.driving_assistance_preset, "custom");
    let calls = app.main_calls();
    let state_line = calls
        .iter()
        .position(|(line, _)| line.contains("Automatic emergency braking: off"))
        .unwrap();
    let note = calls
        .iter()
        .position(|(line, _)| line == "Driving assistance preset: Custom.")
        .unwrap();
    assert!(state_line < note);
    assert!(!calls[note].1);
    app.clear_speech();
    key(&mut app, Key::Down);
    key(&mut app, Key::Return);
    assert_eq!(app.ctx.settings.driving_assistance_preset, "custom");
    let spoken = app.main_lines();
    assert!(spoken
        .iter()
        .any(|line| line.contains("Lane-departure warning: off")));
    assert!(!spoken
        .iter()
        .any(|line| line == "Driving assistance preset: Custom."));
}

#[test]
fn test_selected_stop_assist_keyboard_toggle_persists_outside_presets() {
    let mut app = TestApp::new();
    assert!(!app.ctx.settings.selected_stop_assist);
    open_settings_category(&mut app, "Driving assistance");
    move_to::<Cat>(&mut app, "Planned rest-stop stopping assistance");
    assert!(current_label::<Cat>(&app).ends_with(": off"));
    key(&mut app, Key::Return);
    assert!(app.ctx.settings.selected_stop_assist);
    assert!(current_label::<Cat>(&app).ends_with(": on"));
    assert!(app
        .main_lines()
        .last()
        .unwrap()
        .contains("Planned rest-stop stopping assistance: on."));
    assert!(Settings::load().selected_stop_assist);
    key(&mut app, Key::Home);
    key(&mut app, Key::Right);
    assert!(app.ctx.settings.selected_stop_assist);
}

#[test]
fn test_lane_keeping_row_updates_the_preset_row() {
    let mut app = TestApp::new();
    app.ctx.settings.apply_driving_assistance_preset("all");
    open_settings_category(&mut app, "Driving assistance");
    move_to::<Cat>(&mut app, "Lane keeping");
    key(&mut app, Key::Return);
    assert_ne!(app.ctx.settings.lane_keeping, "full");
    assert_eq!(app.ctx.settings.driving_assistance_preset, "custom");
}

#[test]
fn test_exactly_one_driving_assistance_preset_selector() {
    let mut app = TestApp::new();
    let rows = cat_rows(&mut app, "assistance");
    assert_eq!(
        rows.iter()
            .filter(|(label, _)| label.starts_with("Driving assistance preset:"))
            .count(),
        1
    );
    assert!(!rows.iter().any(|(label, _)| {
        let lower = label.to_lowercase();
        lower.contains("player style") || lower.contains("descent preset")
    }));
}

#[test]
fn test_settings_saved_is_heard_and_not_cancelled_by_the_main_menu_welcome() {
    // Backing all the way out of Settings must not swallow "Settings saved.":
    // it must be the last line spoken and the one that wins, not the one
    // cut off.
    let mut app = TestApp::new();
    app.push_state(MainMenuState::new());
    select::<MainMenuState>(&mut app, "Settings");
    assert!(is::<SettingsState>(&app));
    app.clear_speech();
    key(&mut app, Key::Escape);
    let calls = app.main_calls();
    assert!(
        !calls.is_empty(),
        "nothing was spoken on the way out of Settings"
    );
    let (text, interrupt) = calls.last().unwrap();
    assert_eq!(text, "Settings saved.");
    assert!(*interrupt);
}

#[test]
fn test_speech_setting_adjustment_previews_adjusted_voice() {
    let mut app = TestApp::with_speech(CaptureSpeech::full_voice());
    app.push_state(SettingsCategoryState::new("speech"));
    move_to::<Cat>(&mut app, "Speech rate");
    app.clear_speech();
    key(&mut app, Key::Right);
    let previews = app.speech().previews().to_vec();
    assert!(!previews.is_empty());
    let (setting, text, interrupt) = previews.last().unwrap();
    assert_eq!(setting, "speech_rate");
    assert!(text.starts_with("Speech rate:"));
    assert!(*interrupt);
    // The preview spoke it; the main channel did not need to.
    assert!(!app
        .main_lines()
        .iter()
        .any(|line| line.starts_with("Speech rate:")));
}

#[test]
fn test_problem_reports_is_honest_when_no_log_is_being_written() {
    // A source checkout writes no file; the screen must not name one anyway.
    let mut app = TestApp::new();
    app.push_state(SettingsCategoryState::new("reports"));
    assert_eq!(
        with_state::<Cat, _>(&app, |c, _| c.title().to_string()),
        "Problem reports"
    );
    assert_eq!(
        labels::<Cat>(&app),
        vec!["Where the game log is saved", "Back"]
    );
    let said = with_state::<Cat, _>(&app, |c, _| c.log_location_lines().join(" "));
    assert!(said.contains("not writing a log file"));
    assert!(said.contains("Packaged downloads always write one"));
    // Left and right are for stepping values; this row has none to step.
    key(&mut app, Key::Right);
    key(&mut app, Key::Left);
    assert_eq!(current_label::<Cat>(&app), "Where the game log is saved");
}

#[test]
#[ignore = "needs a test seam to point `app::active_log_path` at a file; the headless test binary writes no log"]
fn test_problem_reports_reads_out_the_active_log_file() {}

// -- the one-shot "where your settings moved" notice ------------------------------

#[test]
fn test_gameplay_reorg_notice_fires_once_for_a_pre_reorg_settings_file() {
    // A returning player cannot see the menu change shape, so the Gameplay
    // submenu says once where their settings moved -- then never again.
    let mut app = TestApp::new();
    // No settings_version on disk reads as layout 0 (pinned in ff_core), so
    // every notice is owed -- the Gameplay split and the later row moves.
    app.ctx.settings.settings_layout_notice_from = 0;
    open_gameplay_parent(&mut app);
    let spoken = app.main_lines();
    assert!(spoken
        .iter()
        .any(|line| line.contains("Gameplay is now a category")));
    assert!(spoken
        .iter()
        .any(|line| line.contains("Weather, traffic, and parking sources moved")));
    assert!(spoken
        .iter()
        .any(|line| line.contains("Nothing about your settings changed")));
    assert!(spoken
        .iter()
        .any(|line| line.contains("Speed keeper is now in Driving assistance")));
    let first = spoken
        .iter()
        .position(|s| s.contains("Gameplay is now a category"))
        .unwrap();
    let second = spoken
        .iter()
        .position(|s| s.contains("Speed keeper is now in"))
        .unwrap();
    assert!(first < second, "{spoken:?}");
    // Cleared, and persisted so a restart does not replay it.
    assert_eq!(app.ctx.settings.settings_layout_notice_from, -1);
    assert_eq!(Settings::load().settings_layout_notice_from, -1);

    app.clear_speech();
    with_state_mut::<GameplaySettingsState, _>(&mut app, State::enter);
    assert!(!app
        .main_lines()
        .iter()
        .any(|line| line.contains("Gameplay is now a category")));
}

#[test]
fn test_a_fresh_install_hears_no_gameplay_reorg_notice() {
    let mut app = TestApp::new();
    assert_eq!(app.ctx.settings.settings_layout_notice_from, -1);
    open_gameplay_parent(&mut app);
    assert!(!app
        .main_lines()
        .iter()
        .any(|line| line.contains("Gameplay is now a category")));
}

#[test]
fn test_a_player_one_layout_behind_hears_only_the_newer_notice() {
    let mut app = TestApp::new();
    app.ctx.settings.settings_layout_notice_from = 1;
    open_gameplay_parent(&mut app);
    let spoken = app.main_lines();
    assert!(spoken
        .iter()
        .any(|line| line.contains("Speed keeper is now in Driving assistance")));
    assert!(!spoken
        .iter()
        .any(|line| line.contains("Gameplay is now a category")));
}

#[test]
fn test_a_player_two_layouts_behind_hears_the_driving_speech_notice() {
    let mut app = TestApp::new();
    app.ctx.settings.settings_layout_notice_from = 2;
    open_gameplay_parent(&mut app);
    let spoken = app.main_lines();
    let notice: Vec<_> = spoken
        .iter()
        .filter(|line| line.contains("Driving speech"))
        .collect();
    assert!(!notice.is_empty());
    assert!(!notice[0].trim().is_empty());
    // Only the version-3 notice was owed; the earlier ones must not replay.
    assert!(!spoken
        .iter()
        .any(|line| line.contains("Gameplay is now a category")));
    assert!(!spoken
        .iter()
        .any(|line| line.contains("Speed keeper is now in")));
}

#[test]
fn test_lane_centering_help_does_not_promise_steering_help() {
    let mut app = TestApp::new();
    let rows = cat_rows(&mut app, "assistance");
    let (_, help) = rows
        .iter()
        .find(|(label, _)| label.starts_with("Lane centering assistance"))
        .unwrap();
    assert!(help.contains("does not do yet"));
    assert!(help.contains("makes no difference"));
}

#[test]
fn test_every_row_answers_the_arrow_keys() {
    // The rows and the left/right action list are two hand-kept lists, and a
    // row moved out of one but not the other leaves the arrows landing on the
    // wrong setting -- silently, for a player who cannot see the mismatch.
    let mut app = TestApp::new();
    for category in ["assistance", "difficulty", "world", "controls", "audio"] {
        app.push_state(SettingsCategoryState::new(category));
        let rows: Vec<String> = labels::<Cat>(&app)
            .into_iter()
            .filter(|label| label != "Back")
            .collect();
        let mut deaf = Vec::new();
        for (i, row) in rows.iter().enumerate() {
            set_index::<Cat>(&mut app, i);
            let mut answered = false;
            for direction in [1, -1] {
                let before = labels::<Cat>(&app)[i].clone();
                with_state_mut::<Cat, _>(&mut app, |c, ctx| c.adjust(ctx, direction));
                with_state_mut::<Cat, _>(&mut app, |c, ctx| c.refresh(ctx, true));
                if labels::<Cat>(&app)[i] != before {
                    answered = true;
                    break;
                }
            }
            if !answered {
                deaf.push(row.clone());
            }
        }
        assert!(deaf.is_empty(), "{category}: {deaf:?}");
        app.pop_state();
    }
}

// -- the driving speech ladder settings row -----------------------------------------

#[test]
fn test_the_driving_speech_row_names_the_rung_without_underscores() {
    let mut app = TestApp::new();
    app.ctx.settings.driving_speech = "urgent_only".to_string();
    let rows = cat_rows(&mut app, "speech");
    let (label, _) = rows
        .iter()
        .find(|(label, _)| label.starts_with("Driving speech"))
        .unwrap();
    assert_eq!(label, "Driving speech: urgent only");
    assert!(!label.contains('_'));
}

#[test]
fn test_driving_speech_row_cycles_all_three_rungs_and_wraps() {
    let mut app = TestApp::new();
    assert_eq!(app.ctx.settings.driving_speech, "standard"); // the shipped default
    open_settings_category(&mut app, "Speech");
    move_to::<Cat>(&mut app, "Driving speech");
    key(&mut app, Key::Return);
    assert_eq!(app.ctx.settings.driving_speech, "quiet");
    key(&mut app, Key::Return);
    assert_eq!(app.ctx.settings.driving_speech, "urgent_only");
    key(&mut app, Key::Return);
    assert_eq!(app.ctx.settings.driving_speech, "standard"); // wrapped
    key(&mut app, Key::Left);
    assert_eq!(app.ctx.settings.driving_speech, "urgent_only");
}

#[test]
fn test_the_driving_mode_row_explains_the_retired_pacing() {
    let mut app = TestApp::new();
    app.ctx.settings.time_scale = 20.0;
    app.ctx.settings.pace_retired_notice_left = PACE_RETIRED_NOTICES;
    // Driving mode is the row this category lands on, so entry speaks it
    // and spends one of the three.
    open_settings_category(&mut app, "Difficulty and hours of service");
    assert!(current_label::<Cat>(&app).starts_with("Driving mode"));
    let spoken = app.main_lines();
    let notice: Vec<_> = spoken
        .iter()
        .filter(|line| line.contains("used to offer Realistic"))
        .collect();
    assert!(!notice.is_empty());
    assert!(notice.last().unwrap().contains("half the speed"));
    assert_eq!(
        app.ctx.settings.pace_retired_notice_left,
        PACE_RETIRED_NOTICES - 1
    );

    // And it stops once the budget is spent.
    app.ctx.settings.pace_retired_notice_left = 0;
    app.clear_speech();
    open_settings_category(&mut app, "Difficulty and hours of service");
    with_state_mut::<Cat, _>(&mut app, |c, ctx| {
        c.announce_entry(ctx);
        c.speak_current(ctx);
    });
    assert!(!app
        .main_lines()
        .iter()
        .any(|line| line.contains("used to offer Realistic")));
}

#[test]
fn test_the_driving_mode_row_cycles_relaxed_standard_and_real_time() {
    let mut app = TestApp::new();
    app.ctx.settings.time_scale = 10.0;
    open_settings_category(&mut app, "Difficulty and hours of service");
    move_to::<Cat>(&mut app, "Driving mode");
    let mut seen = Vec::new();
    for _ in 0..6 {
        seen.push(current_label::<Cat>(&app));
        key(&mut app, Key::Right);
    }
    assert_eq!(
        seen,
        vec![
            "Driving mode: relaxed",
            "Driving mode: standard",
            "Driving mode: real time",
            "Driving mode: relaxed",
            "Driving mode: standard",
            "Driving mode: real time",
        ]
    );
    // Real time is the 1x clock, and Left walks the row back the same way.
    key(&mut app, Key::Left);
    assert_eq!(app.ctx.settings.time_scale, 1.0);
    key(&mut app, Key::Left);
    assert_eq!(app.ctx.settings.time_scale, 20.0);
}

#[test]
fn test_a_row_notice_is_heard_when_that_row_is_the_one_you_land_on() {
    // Entry speaks the landing row through ctx.say, not speak_current.
    let mut app = TestApp::new();
    app.ctx.settings.time_scale = 20.0;
    app.ctx.settings.pace_retired_notice_left = PACE_RETIRED_NOTICES;
    open_settings_category(&mut app, "Difficulty and hours of service");
    assert!(current_label::<Cat>(&app).starts_with("Driving mode"));
    with_state_mut::<Cat, _>(&mut app, |c, ctx| c.announce_entry(ctx));
    assert!(app
        .main_lines()
        .iter()
        .any(|line| line.contains("used to offer Realistic")));
}
