//! The continuous soundscape: `update_audio` in
//! `states/driving_updates/engine_audio.rs` -- the engine voice through a
//! shift, the jake growl, the air-fill hiss, the reverse beeper, the
//! cold-start buzzer, and the two-way engine-loop mirror.
//!
//! Ported from the engine-audio block of `tests/test_driving_features.py`
//! (`test_engine_audio_load_eases_without_dropping_out_during_automatic_shift`
//! through `test_reverse_audio_loop_restarts_after_pause_resume` -- the two
//! loop cases inside that run, the reverse beeper and the air fill, already
//! live in `states_driving_updates.rs` and are not repeated here -- plus
//! `test_rest_menu_shutdown_also_stops_engine_audio` and
//! `test_engine_audio_mirror_sync_catches_any_out_of_band_stop`).
//!
//! Python monkeypatched one audio method per case. The equivalent seam here
//! is the audio BACKEND: [`TrackingBackend`] below is a real
//! `AudioBackend` behind a real `AudioEngine`, so every call still goes
//! through the shipped facade -- bank routing, voice keys, the engine
//! model's own book-keeping -- and what is recorded is what the backend was
//! actually asked to do. It also does what the null backend does not:
//! remembers whether the engine loop is running, which is the whole subject
//! of the two mirror cases.

use std::cell::RefCell;
use std::rc::Rc;

use ff_core::sim::transmission::REVERSE;
use ff_core::sim::weather::WeatherKind;

use freight_fate::audio::{
    engine_load_gain, Audio, AudioError, SustainLoopSpec, VolumeUpdate, CH_JAKE,
};
use freight_fate::playtest::harness::{PlaytestHarness, StartDelivery};
use freight_fate::states::driving_core::shut_down_engine;
use freight_fate::states::driving_updates::{SHIFT_END_CLUNK_VOLUME, SHIFT_LOAD_CAP};

// -- the recording backend --------------------------------------------------------------

/// What the backend was asked to do, in order.
#[derive(Default)]
struct Calls {
    played: Vec<(String, f64)>,
    /// `play_bank(base, volume)`, kept apart from `played` the way Python's
    /// two separate stubs did.
    banks: Vec<(String, f64)>,
    /// `("start", channel, key, volume)` / `("vol", channel, volume)` /
    /// `("stop", channel)`, flattened into one ordered log the way the Python
    /// cases collected them.
    loops: Vec<LoopCall>,
    reverse: Vec<&'static str>,
    engine_rpm: Vec<(f64, f64)>,
    engine_running: bool,
    /// The ignition crank still playing: settable, because that is exactly
    /// what the cold-start buzzer case has to hold the buzzer behind.
    engine_starting: bool,
}

#[derive(Debug, Clone, PartialEq)]
enum LoopCall {
    Start(u32, String, f64),
    Volume(u32, f64),
    Stop(u32),
}

type Log = Rc<RefCell<Calls>>;

struct TrackingAudio {
    log: Log,
}

impl Audio for TrackingAudio {
    fn enabled(&self) -> bool {
        true
    }
    fn backend_name(&self) -> &str {
        "tracking"
    }
    fn master_volume(&self) -> f64 {
        1.0
    }
    fn sfx_volume(&self) -> f64 {
        1.0
    }
    fn music_volume(&self) -> f64 {
        1.0
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
        self.log.borrow().engine_running
    }
    fn engine_starting(&self) -> bool {
        self.log.borrow().engine_starting
    }
    /// No jake A/B re-voicing: the band the drive picked is the subject of
    /// the growl case, and Python's stub saw it unrouted for the same reason.
    fn voice_key(&self, key: &str) -> String {
        key.to_string()
    }
    fn play_with(&mut self, key: &str, volume: f64, _pan: f64) {
        self.log.borrow_mut().played.push((key.to_string(), volume));
    }
    fn play_bank_with(&mut self, base: &str, _fallback: &str, volume: f64, _pan: f64) {
        self.log.borrow_mut().banks.push((base.to_string(), volume));
    }
    fn set_engine_duck(&mut self, _duck: f64) {}
    fn set_speech_duck(&mut self, _duck: f64) {}
    fn set_engine_voice(&mut self, _classic: bool) {}
    fn set_jake_voice(&mut self, _classic: bool) {}
    fn has_asset(&mut self, _key: &str) -> bool {
        true
    }
    fn start_loop_with(&mut self, channel: u32, key: &str, volume: f64, _fade_ms: u32) {
        self.log
            .borrow_mut()
            .loops
            .push(LoopCall::Start(channel, key.to_string(), volume));
    }
    fn set_loop_volume(&mut self, channel: u32, volume: f64) {
        self.log
            .borrow_mut()
            .loops
            .push(LoopCall::Volume(channel, volume));
    }
    fn set_loop_pan(&mut self, _channel: u32, _pan: f64) {}
    fn stop_loop_with(&mut self, channel: u32, _fade_ms: u32) {
        self.log.borrow_mut().loops.push(LoopCall::Stop(channel));
    }
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
        self.log.borrow_mut().engine_running = true;
    }
    fn engine_stop_with(&mut self, _shutdown_sound: bool) {
        // The shipped facade stops the reverse beeper with the engine loop
        // (`AudioEngine::engine_stop_with`), and `stop_world` -- what a pause
        // calls -- goes through here. A double that skipped it would make the
        // pause case pass or fail on the double's own shape.
        self.reverse_stop();
        self.log.borrow_mut().engine_running = false;
    }
    fn update(&mut self, _dt: f64) {}
    fn set_engine_rpm_with(&mut self, rpm: f64, throttle: f64) {
        self.log.borrow_mut().engine_rpm.push((rpm, throttle));
    }
    fn set_road_noise(&mut self, _speed_mps: f64) {}
    fn set_weather_with(&mut self, _key: Option<&str>, _intensity: f64) {}
    fn set_wind(&mut self, _intensity: f64) {}
    fn set_ambient_with(&mut self, _key: Option<&str>, _volume: f64) {}
    fn horn_start(&mut self) {}
    fn horn_stop(&mut self) {}
    fn reverse_start(&mut self) {
        self.log.borrow_mut().reverse.push("start");
    }
    fn reverse_stop(&mut self) {
        self.log.borrow_mut().reverse.push("stop");
    }
    fn stop_world(&mut self) {
        self.engine_stop_with(false);
    }
    fn play_music_with(&mut self, _track: &str, _fade_ms: u32) {}
    fn play_radio_stream_with(&mut self, _url: &str, _fade_ms: u32) -> Result<(), AudioError> {
        Err(AudioError::new("radio stream unavailable"))
    }
    fn play_music_file_with(&mut self, _path: &str, _fade_ms: u32) -> Result<(), AudioError> {
        Err(AudioError::new("no music files on the bench"))
    }
    fn music_playing(&self) -> bool {
        false
    }
    fn radio_now_playing(&self) -> Option<String> {
        None
    }
    fn stop_music_with(&mut self, _fade_ms: u32) {}
    fn set_volumes(&mut self, _volumes: &VolumeUpdate) {}
    fn shutdown(&mut self) {}
}

// -- rigging -------------------------------------------------------------------------

fn a_drive(name: &str) -> (PlaytestHarness, Log) {
    let mut harness = PlaytestHarness::new();
    harness.start_delivery(StartDelivery::named(name));
    harness.with_drive(|drive, _| {
        drive.tutorial = None;
        drive.departure_checked = true;
        drive.trip.hazard_check_mi = 1e9;
        drive.trip.inspection_check_mi = 1e9;
        drive.trip.traffic_manager.rolling_bubble = false;
        drive.trip.set_npc_vehicles(Vec::new());
        drive.trip.traffic_pressures.clear();
        drive.trip.zones.retain(|z| z.aadt.is_none());
        drive.trip.weather.current = WeatherKind::Clear;
    });
    let log: Log = Rc::new(RefCell::new(Calls::default()));
    harness.app.ctx.audio = Box::new(TrackingAudio {
        log: Rc::clone(&log),
    });
    harness.clear_speech();
    (harness, log)
}

/// `driving._update_audio(dt)`.
fn update_audio(harness: &mut PlaytestHarness, dt: f64) {
    harness.with_drive(move |drive, ctx| drive.update_audio(ctx, dt));
}

fn rpm_samples(log: &Log) -> Vec<(f64, f64)> {
    log.borrow().engine_rpm.clone()
}

fn last_rpm(log: &Log) -> (f64, f64) {
    *rpm_samples(log).last().expect("the engine voice was set")
}

fn loops(log: &Log) -> Vec<LoopCall> {
    log.borrow().loops.clone()
}

fn played_keys(log: &Log) -> Vec<String> {
    log.borrow()
        .played
        .iter()
        .map(|(key, _)| key.clone())
        .collect()
}

fn close(a: f64, b: f64) -> bool {
    (a - b).abs() < 1e-6
}

// -- the engine voice through a shift ------------------------------------------------

#[test]
fn test_engine_audio_load_eases_without_dropping_out_during_automatic_shift() {
    let (mut harness, log) = a_drive("Shift Load");
    harness.with_drive(|drive, _| {
        let truck = drive.truck_mut();
        truck.throttle = 1.0;
        truck.rpm = 1700.0;
        truck.transmission.automatic = true;
        truck.transmission.gear = 4;
        truck.transmission.shift_timer = 0.5;
    });
    log.borrow_mut().engine_rpm.clear();

    update_audio(&mut harness, 0.0);

    let (rpm, load) = last_rpm(&log);
    assert_eq!(rpm, 1700.0);
    assert!(close(load, 0.45), "{load}");
    assert!(engine_load_gain(load) >= 0.75);
}

#[test]
fn test_auto_shift_voice_sighs_with_physics_and_clunks_on_engagement() {
    // A real AMT shift is kachunk -- sigh -- kachunk: the ducked voice
    // follows the physics rpm falling toward the new gear through the
    // interrupt (never a frozen hang), and the moment the gear takes plays
    // its own soft clunk (the engagement used to be silent).
    let (mut harness, log) = a_drive("Shift Voice");
    harness.with_drive(|drive, _| {
        let truck = drive.truck_mut();
        truck.transmission.automatic = true;
        truck.transmission.gear = 4;
        truck.rpm = 1400.0;
        truck.transmission.shift_timer = 0.5; // mid-shift
    });
    log.borrow_mut().banks.clear();

    update_audio(&mut harness, 0.0);
    harness.with_drive(|drive, _| drive.truck_mut().rpm = 1150.0); // sighs down
    update_audio(&mut harness, 0.0);
    assert_eq!(last_rpm(&log).0, 1150.0, "the voice rides the fall");
    assert!(
        log.borrow().banks.is_empty(),
        "no engagement clunk while still shifting: {:#?}",
        log.borrow().banks
    );

    harness.with_drive(|drive, _| {
        drive.truck_mut().transmission.shift_timer = 0.0; // the gear takes
        drive.truck_mut().rpm = 950.0;
    });
    update_audio(&mut harness, 0.0);
    assert_eq!(last_rpm(&log).0, 950.0);
    assert!(
        log.borrow()
            .banks
            .iter()
            .any(|(key, volume)| key == "vehicle/shift_auto"
                && close(*volume, SHIFT_END_CLUNK_VOLUME)),
        "{:#?}",
        log.borrow().banks
    );

    log.borrow_mut().banks.clear();
    update_audio(&mut harness, 0.0); // recovery continues: clunk fires only once
    assert!(log.borrow().banks.is_empty(), "{:#?}", log.borrow().banks);
}

#[test]
fn test_manual_clutch_out_ducks_load_but_keeps_live_revs() {
    // Manual shifting: the player owns the engine while the clutch is out --
    // a throttle blip must stay audible (rev-matching is a skill) -- but the
    // engine unloads to the shift cap and swells back on engagement.
    let (mut harness, log) = a_drive("Clutch Out");
    harness.with_drive(|drive, _| {
        let truck = drive.truck_mut();
        truck.transmission.automatic = false;
        truck.transmission.gear = 5;
        truck.transmission.clutch = 1.0; // pedal down
        truck.throttle = 1.0; // a blip while the clutch is out
        truck.rpm = 1400.0;
    });

    update_audio(&mut harness, 0.0);
    let (rpm, load) = last_rpm(&log);
    assert_eq!(rpm, 1400.0);
    assert!(close(load, SHIFT_LOAD_CAP), "live revs, ducked load: {load}");

    harness.with_drive(|drive, _| drive.truck_mut().rpm = 1650.0); // the blip climbs
    update_audio(&mut harness, 0.0);
    let (rpm, load) = last_rpm(&log);
    assert_eq!(rpm, 1650.0, "the voice must follow, not hold");
    assert!(close(load, SHIFT_LOAD_CAP), "{load}");

    harness.with_drive(|drive, _| drive.truck_mut().transmission.clutch = 0.0); // hooked back up
    update_audio(&mut harness, 0.1); // recovery ramps with real time, not a sync
    let (rpm, load) = last_rpm(&log);
    assert_eq!(rpm, 1650.0);
    assert!(
        load > SHIFT_LOAD_CAP,
        "the engine speaks under load again: {load}"
    );
}

#[test]
fn test_engine_audio_load_tracks_manual_throttle_smoothly() {
    let (mut harness, log) = a_drive("Throttle Filter");
    harness.with_drive(|drive, _| {
        drive.truck_mut().transmission.shift_timer = 0.0;
        drive.engine_audio_throttle = 0.5;
        drive.truck_mut().throttle = 0.75;
    });
    update_audio(&mut harness, 0.1);
    let rising = last_rpm(&log).1;
    harness.with_drive(|drive, _| drive.truck_mut().throttle = 0.25);
    update_audio(&mut harness, 0.1);
    let falling = last_rpm(&log).1;

    // Raw throttle still controls audible load, but the 450-millisecond
    // filter prevents an immediate gain step for a cruise correction.
    assert!(
        close(rising, 0.5 + (0.75 - 0.5) * (0.1 / 0.45)),
        "{rising}"
    );
    assert!(
        close(falling, rising + (0.25 - rising) * (0.1 / 0.45)),
        "{falling}"
    );
    assert!(0.25 < falling && falling < rising && rising < 0.75);
}

// -- the loops ------------------------------------------------------------------------

#[test]
fn test_jake_growl_follows_stage_rpm_and_cuts_through_shifts() {
    let (mut harness, log) = a_drive("Jake Growl");
    harness.with_drive(|drive, _| {
        let truck = drive.truck_mut();
        truck.set_air_ready(false);
        truck.start_engine();
        truck.transmission.automatic = true;
        truck.transmission.gear = 8;
        truck.velocity_mps = 20.0;
        truck.throttle = 0.0;
        truck.engine_brake_stage = 3;
        truck.rpm = 1850.0;
    });
    log.borrow_mut().loops.clear();

    update_audio(&mut harness, 0.0);
    let jake_key = jake_start(&log).expect("the jake growl started");
    assert_eq!(jake_key, "engine/jake_1800", "nearest loop to 1850");

    // Mid-shift the jake cuts out -- the stair-step signature.
    harness.with_drive(|drive, _| drive.truck_mut().transmission.shift_timer = 0.5);
    update_audio(&mut harness, 0.0);
    assert!(
        loops(&log).contains(&LoopCall::Stop(CH_JAKE)),
        "{:#?}",
        loops(&log)
    );

    // Back in gear at higher revs: it resumes on the higher loop.
    log.borrow_mut().loops.clear();
    harness.with_drive(|drive, _| {
        drive.truck_mut().transmission.shift_timer = 0.0;
        drive.truck_mut().rpm = 2150.0;
    });
    update_audio(&mut harness, 0.0);
    assert_eq!(
        jake_start(&log).expect("the growl resumed"),
        "engine/jake_2200"
    );

    // Throttle on: a jake never sounds under power.
    log.borrow_mut().loops.clear();
    harness.with_drive(|drive, _| drive.truck_mut().throttle = 0.5);
    update_audio(&mut harness, 0.0);
    assert!(
        loops(&log).contains(&LoopCall::Stop(CH_JAKE)),
        "{:#?}",
        loops(&log)
    );
}

/// The key the jake channel was last started on, if it was started.
fn jake_start(log: &Log) -> Option<String> {
    loops(log).into_iter().find_map(|call| match call {
        LoopCall::Start(CH_JAKE, key, _) => Some(key),
        _ => None,
    })
}

#[test]
fn test_cold_start_buzzer_waits_out_the_crank() {
    let (mut harness, log) = a_drive("Cold Buzzer");
    harness.with_drive(|drive, _| {
        drive.truck_mut().set_cold_air_start();
        drive.truck_mut().start_engine();
        drive.pending_low_air_buzzer = true; // what the E-key start path arms
    });
    log.borrow_mut().played.clear();

    // While the ignition crank still plays, the buzzer must hold.
    log.borrow_mut().engine_starting = true;
    update_audio(&mut harness, 0.0);
    assert!(
        !played_keys(&log).iter().any(|k| k == "vehicle/low_air_buzzer"),
        "{:#?}",
        played_keys(&log)
    );
    assert!(harness.read_drive(|d| d.pending_low_air_buzzer));

    // Crank handed off with the air still low (55 psi): now it may sound.
    log.borrow_mut().engine_starting = false;
    update_audio(&mut harness, 0.0);
    assert!(
        played_keys(&log).iter().any(|k| k == "vehicle/low_air_buzzer"),
        "{:#?}",
        played_keys(&log)
    );
    assert!(!harness.read_drive(|d| d.pending_low_air_buzzer));

    // And if the compressor had already built past the warning line, the
    // pending buzzer dissolves silently.
    log.borrow_mut().played.clear();
    harness.with_drive(|drive, _| {
        drive.pending_low_air_buzzer = true;
        drive.truck_mut().set_air_pressure_psi(80.0); // above the 60 psi warning
    });
    update_audio(&mut harness, 0.0);
    assert!(
        !played_keys(&log).iter().any(|k| k == "vehicle/low_air_buzzer"),
        "{:#?}",
        played_keys(&log)
    );
    assert!(!harness.read_drive(|d| d.pending_low_air_buzzer));
}

#[test]
fn test_reverse_audio_loop_restarts_after_pause_resume() {
    let (mut harness, log) = a_drive("Reverse Pause");
    harness.with_drive(|drive, _| {
        drive.truck_mut().start_engine();
        drive.truck_mut().transmission.gear = REVERSE;
    });
    log.borrow_mut().reverse.clear();
    update_audio(&mut harness, 0.0);
    assert_eq!(log.borrow().reverse, vec!["start"]);

    harness.with_drive(|drive, ctx| drive.push_pause_menu(ctx));
    assert_eq!(log.borrow().reverse, vec!["start", "stop"]);
    harness.select_menu_item("Resume driving");

    log.borrow_mut().reverse.clear();
    update_audio(&mut harness, 0.0);

    assert_eq!(log.borrow().reverse, vec!["start"]);
}

// -- the two-way engine mirror ----------------------------------------------------------

#[test]
fn test_rest_menu_shutdown_also_stops_engine_audio() {
    // Sleeping shuts the truck's engine down from a rest menu, outside the
    // driving frame loop. Regression: the audio loop was left running --
    // masked while band volumes tracked RPM, plainly audible once the BASS
    // engine model kept constant volume.
    let (mut harness, _log) = a_drive("Rest Shutdown");
    assert!(harness.with_drive(|drive, _| drive.truck_mut().start_engine()));
    update_audio(&mut harness, 0.0);
    assert!(harness.app.ctx.audio.engine_running());

    let prefix = harness.with_drive(|drive, ctx| shut_down_engine(drive, ctx));

    assert_eq!(prefix, "You shut down the engine. ");
    assert!(!harness.read_drive(|d| d.truck().engine_on));
    assert!(!harness.app.ctx.audio.engine_running());

    // Already off: no double narration, audio stays off.
    assert_eq!(
        harness.with_drive(|drive, ctx| shut_down_engine(drive, ctx)),
        ""
    );
    assert!(!harness.app.ctx.audio.engine_running());
}

#[test]
fn test_engine_audio_mirror_sync_catches_any_out_of_band_stop() {
    // The frame-loop audio sync must work in both directions: any path that
    // turns the truck's engine off without telling the audio engine is
    // corrected on the next frame, silently.
    let (mut harness, _log) = a_drive("Mirror Sync");
    assert!(harness.with_drive(|drive, _| drive.truck_mut().start_engine()));
    update_audio(&mut harness, 0.0);
    assert!(harness.app.ctx.audio.engine_running());

    harness.with_drive(|drive, _| drive.truck_mut().stop_engine()); // off-path stop
    update_audio(&mut harness, 0.0);

    assert!(!harness.app.ctx.audio.engine_running());
}
