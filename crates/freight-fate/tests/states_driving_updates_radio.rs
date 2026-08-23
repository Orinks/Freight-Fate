//! `states/driving_updates.rs`, the radio half: engine power, the dial keys,
//! station rotation and the break slots, personal playlists, and the FM
//! fringe.
//!
//! Ported from `tests/test_radio_engine_power.py`, the drive-side cases of
//! `tests/test_radio_breaks.py` and `tests/test_music_selection.py`'s drive
//! rotation. The pure catalog/content halves of those files are already
//! covered by the `ff-core` radio and music suites.

use std::cell::{Cell, RefCell};
use std::rc::Rc;

use ff_core::data::world::get_world;
use ff_core::models::jobs::{Job, CARGO_CATALOG};
use ff_core::models::profile::Profile;
use ff_core::radio::{RadioStation, PERSONAL_PLAYLIST_SOURCE_TYPE};
use ff_core::radio_content::content_duration_s;

use freight_fate::app::testing::TestApp;
use freight_fate::audio::{Audio, AudioError, SustainLoopSpec, VolumeUpdate};
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::DRIVE_PHASE_DELIVERY;

// -- rigging -------------------------------------------------------------------------

/// `_drive_job()`: the Denver run every radio fixture in the Python suite uses.
fn a_denver_drive(app: &mut TestApp, trip_seed: i64) -> DrivingState {
    let world = get_world();
    app.ctx.profile = Some(Profile::named_in("Radio Power", "Denver"));
    let route = world
        .route_from_cities(&["Denver", "Salt Lake City"])
        .expect("Denver to Salt Lake City routes");
    let job = Job::new(
        &CARGO_CATALOG["general"],
        12.0,
        "Denver",
        "Denver Dry Warehouse",
        "Salt Lake City",
        520.0,
        2400.0,
        14.0,
    );
    let mut drive = DrivingState::new(
        &mut app.ctx,
        job,
        route,
        Some(trip_seed),
        DRIVE_PHASE_DELIVERY,
        Some(13.0),
    );
    drive.trip.set_npc_vehicles(Vec::new());
    drive
}

/// The music side of the facade: what was played, what stopped it, and the
/// music bus level `apply_radio_volume` writes.
#[derive(Default)]
struct MusicAudio {
    music: Rc<RefCell<Vec<(String, u32)>>>,
    stops: Rc<RefCell<Vec<u32>>>,
    volume: Rc<Cell<f64>>,
    playing: Rc<Cell<bool>>,
    engine_on: Rc<Cell<bool>>,
}

#[derive(Clone, Default)]
struct MusicTape {
    music: Rc<RefCell<Vec<(String, u32)>>>,
    stops: Rc<RefCell<Vec<u32>>>,
}

impl MusicTape {
    fn tracks(&self) -> Vec<String> {
        self.music
            .borrow()
            .iter()
            .map(|(track, _)| track.clone())
            .collect()
    }

    fn last(&self) -> (String, u32) {
        self.music.borrow().last().cloned().expect("music played")
    }

    fn is_empty(&self) -> bool {
        self.music.borrow().is_empty()
    }

    fn clear_stops(&self) {
        self.stops.borrow_mut().clear();
    }

    fn stopped(&self) -> Vec<u32> {
        self.stops.borrow().clone()
    }
}

impl MusicAudio {
    fn install(app: &mut TestApp) -> MusicTape {
        let audio = MusicAudio::default();
        let tape = MusicTape {
            music: Rc::clone(&audio.music),
            stops: Rc::clone(&audio.stops),
        };
        app.ctx.audio = Box::new(audio);
        tape
    }
}

impl Audio for MusicAudio {
    fn enabled(&self) -> bool {
        false
    }
    fn backend_name(&self) -> &str {
        "music-test"
    }
    fn master_volume(&self) -> f64 {
        1.0
    }
    fn sfx_volume(&self) -> f64 {
        1.0
    }
    fn music_volume(&self) -> f64 {
        self.volume.get()
    }
    fn weather_volume(&self) -> f64 {
        1.0
    }
    fn engine_volume(&self) -> f64 {
        1.0
    }
    fn ui_volume(&self) -> f64 {
        1.0
    }
    fn engine_running(&self) -> bool {
        self.engine_on.get()
    }
    fn engine_starting(&self) -> bool {
        false
    }
    fn voice_key(&self, key: &str) -> String {
        key.to_string()
    }
    fn play_with(&mut self, _key: &str, _volume: f64, _pan: f64) {}
    fn play_bank_with(&mut self, _base: &str, _fallback: &str, _volume: f64, _pan: f64) {}
    fn set_engine_duck(&mut self, _duck: f64) {}
    fn set_speech_duck(&mut self, _duck: f64) {}
    fn set_engine_voice(&mut self, _classic: bool) {}
    fn set_jake_voice(&mut self, _classic: bool) {}
    fn has_asset(&mut self, _key: &str) -> bool {
        true
    }
    fn start_loop_with(&mut self, _channel: u32, _key: &str, _volume: f64, _fade_ms: u32) {}
    fn set_loop_volume(&mut self, _channel: u32, _volume: f64) {}
    fn set_loop_pan(&mut self, _channel: u32, _pan: f64) {}
    fn stop_loop_with(&mut self, _channel: u32, _fade_ms: u32) {}
    fn start_sustain_loop_with(
        &mut self,
        _channel: u32,
        _key: &str,
        _spec: SustainLoopSpec,
        _volume: f64,
    ) {
    }
    fn release_sustain_loop_with(&mut self, _channel: u32, _fade_ms: u32) {}
    fn hold_alert_with(&mut self, _key: &str, _volume: f64, _fade_ms: u32) {}
    fn release_alert_with(&mut self, _fade_ms: u32) {}
    fn hold_cue(&mut self, _name: &str) {}
    fn cue_held(&self, _name: &str) -> bool {
        false
    }
    fn release_cue(&mut self, _name: &str) {}
    fn engine_start_with(&mut self, _play_start_sound: bool) {
        self.engine_on.set(true);
    }
    fn engine_stop_with(&mut self, _shutdown_sound: bool) {
        self.engine_on.set(false);
    }
    fn update(&mut self, _dt: f64) {}
    fn set_engine_rpm_with(&mut self, _rpm: f64, _throttle: f64) {}
    fn set_road_noise(&mut self, _speed_mps: f64) {}
    fn set_weather_with(&mut self, _key: Option<&str>, _intensity: f64) {}
    fn set_wind(&mut self, _intensity: f64) {}
    fn set_ambient_with(&mut self, _key: Option<&str>, _volume: f64) {}
    fn horn_start(&mut self) {}
    fn horn_stop(&mut self) {}
    fn reverse_start(&mut self) {}
    fn reverse_stop(&mut self) {}
    fn stop_world(&mut self) {}
    fn play_music_with(&mut self, track: &str, fade_ms: u32) {
        self.music.borrow_mut().push((track.to_string(), fade_ms));
        self.playing.set(true);
    }
    fn play_radio_stream_with(&mut self, _url: &str, _fade_ms: u32) -> Result<(), AudioError> {
        self.playing.set(true);
        Ok(())
    }
    fn play_music_file_with(&mut self, path: &str, fade_ms: u32) -> Result<(), AudioError> {
        // A personal playlist entry that will not open is how the skip and
        // the "nothing would play" line are exercised.
        if path.contains("missing") {
            return Err(AudioError::new("no such file"));
        }
        self.music.borrow_mut().push((path.to_string(), fade_ms));
        self.playing.set(true);
        Ok(())
    }
    fn music_playing(&self) -> bool {
        self.playing.get()
    }
    fn radio_now_playing(&self) -> Option<String> {
        None
    }
    fn stop_music_with(&mut self, fade_ms: u32) {
        self.stops.borrow_mut().push(fade_ms);
        self.playing.set(false);
    }
    fn set_volumes(&mut self, volumes: &VolumeUpdate) {
        if let Some(music) = volumes.music {
            self.volume.set(music);
        }
    }
    fn shutdown(&mut self) {}
}

/// The last thing the main channel said.
fn last(app: &TestApp) -> String {
    app.main_lines().last().cloned().unwrap_or_default()
}

// -- engine power (test_radio_engine_power.py) ----------------------------------------

#[test]
fn test_radio_is_silent_until_the_engine_starts() {
    let mut app = TestApp::new();
    let mut d = a_denver_drive(&mut app, 777);
    let tape = MusicAudio::install(&mut app);
    // The top of every load: radio enabled, engine off, and nothing plays.
    assert!(d.radio.enabled);
    assert!(tape.is_empty());

    d.trip.truck.start_engine();
    d.update_audio(&mut app.ctx, 0.0);

    assert!(
        !tape.is_empty(),
        "the radio comes back on its own with the engine"
    );
}

#[test]
fn test_engine_shutdown_cuts_the_radio() {
    let mut app = TestApp::new();
    let mut d = a_denver_drive(&mut app, 777);
    let tape = MusicAudio::install(&mut app);
    d.trip.truck.start_engine();
    d.update_audio(&mut app.ctx, 0.0);
    assert!(!tape.is_empty());
    tape.clear_stops();

    d.trip.truck.stop_engine();
    d.update_audio(&mut app.ctx, 0.0);

    assert!(
        !tape.stopped().is_empty(),
        "the radio loses power with the engine"
    );
}

#[test]
fn test_radio_keys_speak_the_no_power_line_with_the_engine_off() {
    let mut app = TestApp::new();
    let mut d = a_denver_drive(&mut app, 777);
    let tape = MusicAudio::install(&mut app);
    app.clear_speech();

    d.toggle_radio(&mut app.ctx);
    d.tune_radio(&mut app.ctx, 1);
    d.jump_radio_category(&mut app.ctx, 1);

    assert!(tape.is_empty());
    assert_eq!(
        app.main_lines()
            .iter()
            .filter(|line| *line == "The engine is off. The radio has no power.")
            .count(),
        3
    );
    // The player's wish is untouched: the radio is still on for ignition.
    assert!(d.radio.enabled);

    // The status key answers, but explains the silence.
    d.speak_radio_status(&mut app.ctx);
    let said = last(&app);
    assert!(said.starts_with("Radio on."));
    assert!(said.ends_with("The engine is off, so the radio has no power right now."));
}

#[test]
fn test_shift_page_up_raises_radio_volume_ten_percent() {
    let mut app = TestApp::new();
    let mut d = a_denver_drive(&mut app, 777);
    MusicAudio::install(&mut app);
    app.ctx.settings.radio_volume = 0.25;
    app.clear_speech();

    d.adjust_radio_volume(&mut app.ctx, 1);

    assert!((app.ctx.settings.radio_volume - 0.35).abs() < 1e-9);
    assert_eq!(last(&app), "Radio volume 35 percent.");
}

#[test]
fn test_shift_page_down_lowers_radio_volume_ten_percent() {
    let mut app = TestApp::new();
    let mut d = a_denver_drive(&mut app, 777);
    MusicAudio::install(&mut app);
    app.ctx.settings.radio_volume = 0.35;
    app.clear_speech();

    d.adjust_radio_volume(&mut app.ctx, -1);

    assert!((app.ctx.settings.radio_volume - 0.25).abs() < 1e-9);
    assert_eq!(last(&app), "Radio volume 25 percent.");
}

#[test]
fn test_shift_page_down_clamps_at_muted() {
    let mut app = TestApp::new();
    let mut d = a_denver_drive(&mut app, 777);
    MusicAudio::install(&mut app);
    app.ctx.settings.radio_volume = 0.05;
    app.clear_speech();

    d.adjust_radio_volume(&mut app.ctx, -1);
    assert_eq!(app.ctx.settings.radio_volume, 0.0);
    assert_eq!(last(&app), "Radio volume muted.");

    // A second press at the floor stays put, not negative.
    d.adjust_radio_volume(&mut app.ctx, -1);
    assert_eq!(app.ctx.settings.radio_volume, 0.0);
    assert_eq!(last(&app), "Radio volume muted.");
}

#[test]
fn test_shift_page_up_clamps_at_all_the_way_up() {
    let mut app = TestApp::new();
    let mut d = a_denver_drive(&mut app, 777);
    MusicAudio::install(&mut app);
    app.ctx.settings.radio_volume = 0.95;
    app.clear_speech();

    d.adjust_radio_volume(&mut app.ctx, 1);
    assert_eq!(app.ctx.settings.radio_volume, 1.0);
    assert_eq!(last(&app), "Radio volume all the way up.");

    // A second press at the ceiling stays put, not over 100.
    d.adjust_radio_volume(&mut app.ctx, 1);
    assert_eq!(app.ctx.settings.radio_volume, 1.0);
    assert_eq!(last(&app), "Radio volume all the way up.");
}

#[test]
fn test_shift_volume_works_with_the_engine_off_and_radio_off() {
    // The setting is what it is regardless of power state: no "engine is off"
    // line, unlike the plain tune and category keys.
    let mut app = TestApp::new();
    let mut d = a_denver_drive(&mut app, 777);
    MusicAudio::install(&mut app);
    assert!(!d.trip.truck.engine_on);
    d.radio.enabled = false;
    app.ctx.settings.radio_volume = 0.25;
    app.clear_speech();

    d.adjust_radio_volume(&mut app.ctx, 1);

    assert!((app.ctx.settings.radio_volume - 0.35).abs() < 1e-9);
    assert_eq!(last(&app), "Radio volume 35 percent.");
    assert!(!last(&app).to_lowercase().contains("no power"));
}

#[test]
fn test_shift_volume_applies_live_while_the_radio_plays() {
    let mut app = TestApp::new();
    let mut d = a_denver_drive(&mut app, 777);
    let tape = MusicAudio::install(&mut app);
    d.trip.truck.start_engine();
    d.update_audio(&mut app.ctx, 0.0);
    assert!(!tape.is_empty());
    app.ctx.settings.radio_volume = 0.25;

    d.adjust_radio_volume(&mut app.ctx, 1);

    assert!((app.ctx.audio.music_volume() - 0.35).abs() < 1e-9);
}

// -- station rotation and break slots (test_radio_breaks.py) ---------------------------

/// Put one built-in station on the dial and tune to it.
fn tune_to_fixture(d: &mut DrivingState, app: &mut TestApp, id: &str, host: &str) {
    let station = RadioStation {
        playlist: "country".to_string(),
        host: host.to_string(),
        ..RadioStation::new(id, "Fixture", "KFX", "country", "test fixture")
    };
    let mut catalog = d.radio.catalog.clone();
    catalog.push(station);
    d.radio.set_catalog(catalog);
    let id = id.to_string();
    d.with_radio_backend(app_ctx(app), |radio, backend| {
        radio.select_station(&id, Some(backend))
    });
}

fn app_ctx(app: &mut TestApp) -> &mut freight_fate::app::GameContext {
    &mut app.ctx
}

/// `_play_next(driving, played)`: run the current entry out.
fn play_next(d: &mut DrivingState, app: &mut TestApp, tape: &MusicTape) {
    let dt = content_duration_s(&tape.last().0) + 0.1;
    d.update_radio_playback(&mut app.ctx, false, dt);
}

#[test]
fn test_break_queue_delivers_host_id_ad_slots_in_order() {
    // The Python case swapped fixture pools in by monkeypatching the module
    // tables; the Rust tables are `static`, so this runs on the shipped
    // Roadhouse pools instead and asserts the SHAPE of the pattern -- two
    // songs, a break, back to music, at the same fades.
    let mut app = TestApp::new();
    let mut d = a_denver_drive(&mut app, 42);
    let tape = MusicAudio::install(&mut app);
    tune_to_fixture(&mut d, &mut app, "brk-fixture", "roadhouse");
    assert!(tape.last().0.starts_with("radio_country_"));

    play_next(&mut d, &mut app, &tape); // song 2
    assert!(tape.last().0.starts_with("radio_country_"));
    play_next(&mut d, &mut app, &tape); // after 2 songs: a host break
    let (track, fade) = tape.last();
    assert!(track.starts_with("host_roadhouse_"));
    assert_eq!(fade, 600); // fade into a break

    play_next(&mut d, &mut app, &tape); // break ends, music resumes (song 3)
    let (track, fade) = tape.last();
    assert!(track.starts_with("radio_country_"));
    assert_eq!(fade, 1200); // fade back to music

    play_next(&mut d, &mut app, &tape); // song 4
    play_next(&mut d, &mut app, &tape); // after 4 songs: an id break
    let (track, fade) = tape.last();
    assert!(track.starts_with("id_") || track.starts_with("host_"));
    assert_eq!(fade, 600);
}

#[test]
fn test_no_host_station_chains_songs_without_break() {
    let mut app = TestApp::new();
    let mut d = a_denver_drive(&mut app, 42);
    let tape = MusicAudio::install(&mut app);
    tune_to_fixture(&mut d, &mut app, "brk-nohost", "");
    assert!(tape.last().0.starts_with("radio_country_"));

    for _ in 0..6 {
        play_next(&mut d, &mut app, &tape);
        assert!(tape.last().0.starts_with("radio_country_"));
    }
    assert!(d.radio_break_queue.is_empty());
}

#[test]
fn test_the_route_station_swaps_its_pool_at_nightfall() {
    // `_station_rotation_pool`: the route playlist is the drive's own
    // day/night sequence, and the rotation restarts when the flag flips.
    let mut app = TestApp::new();
    let mut d = a_denver_drive(&mut app, 42);
    let route_station = RadioStation {
        playlist: "route".to_string(),
        ..RadioStation::new("route-fixture", "Route", "", "mixed", "test fixture")
    };
    let day = d.station_rotation_pool(&route_station, false);
    let night = d.station_rotation_pool(&route_station, true);
    assert_eq!(day, d.day_music_sequence);
    assert_eq!(night, d.night_music_sequence);
    assert_ne!(day, night);
    let _ = &mut d;
}

// -- personal playlists ---------------------------------------------------------------

fn a_playlist_station(id: &str, entries: &[&str]) -> RadioStation {
    RadioStation {
        source_type: PERSONAL_PLAYLIST_SOURCE_TYPE.to_string(),
        playlist_entries: entries.iter().map(|entry| entry.to_string()).collect(),
        ..RadioStation::new(id, "My Playlist", "", "playlist", "personal")
    }
}

#[test]
fn test_a_playlist_entry_that_will_not_open_is_skipped_not_pruned() {
    // A NAS that was asleep when the drive started must not erase the tracks
    // behind it: entries are skipped at play time.
    let mut app = TestApp::new();
    let mut d = a_denver_drive(&mut app, 5);
    let tape = MusicAudio::install(&mut app);
    let station = a_playlist_station("pl-1", &["C:/music/missing.ogg", "C:/music/good.ogg"]);
    d.start_playlist_station(&mut app.ctx, &station, 900, false);
    assert_eq!(tape.tracks(), vec!["C:/music/good.ogg".to_string()]);
    // The dead entry is still in the playlist, just not the one playing.
    assert_eq!(station.playlist_entries.len(), 2);
    assert_eq!(d.playlist_entry(&station), "C:/music/good.ogg");
}

#[test]
fn test_a_dead_playlist_reaches_the_dials_fallback() {
    // `RadioState.play` only marks a station unplayable and speaks the
    // handover when the backend REFUSES. Python raised RadioPlaybackError
    // straight through `play_station`; a Rust wrapper that swallowed it left
    // the player parked on a silent station with nothing said about it.
    let mut app = TestApp::new();
    let mut d = a_denver_drive(&mut app, 5);
    let _tape = MusicAudio::install(&mut app);
    let station = a_playlist_station("pl-dead-refuses", &["C:/music/gone.ogg"]);
    let refused = d.with_radio_backend(&mut app.ctx, |_radio, backend| {
        backend.play_station(&station, 1.0)
    });
    assert!(
        refused.is_err(),
        "a playlist with nothing playable must refuse so the dial can fall back"
    );

    // A playlist that does open is still accepted.
    let good = a_playlist_station("pl-good", &["C:/music/good.ogg"]);
    let played = d.with_radio_backend(&mut app.ctx, |_radio, backend| {
        backend.play_station(&good, 1.0)
    });
    assert!(played.is_ok());
}

#[test]
fn test_a_playlist_with_nothing_playable_says_so_once() {
    let mut app = TestApp::new();
    let mut d = a_denver_drive(&mut app, 5);
    let tape = MusicAudio::install(&mut app);
    let station = a_playlist_station(
        "pl-dead",
        &["C:/music/missing-a.ogg", "C:/music/missing-b.ogg"],
    );
    app.clear_speech();
    d.playlist_nothing_plays(&mut app.ctx, &station);
    let said = app.event_lines();
    assert_eq!(said.len(), 1);
    assert!(said[0].contains("Check the tracks in your Playlists folder."));
    // Once per station until something in it plays again.
    d.playlist_nothing_plays(&mut app.ctx, &station);
    assert_eq!(app.event_lines().len(), 1);
    assert!(!tape.stopped().is_empty());
}
