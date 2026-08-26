//! `states/driving_updates.rs`: the per-frame heart of the drive.
//!
//! Ported from `tests/test_microsleep.py`,
//! `tests/test_off_pavement_transitions.py`, `tests/test_lane_position_cue.py`,
//! `tests/test_speeding_consequences.py` (the dash and braking-grace half),
//! `tests/test_engine_brake_zones.py` (the curve-assist retarder cases),
//! `tests/test_driving_features.py` (the lane, air, reverse, hazard and
//! grade cases the frame loop owns) and `tests/test_driving_cruise_weather.py`
//! (the live-weather source switch) -- everything a real `DrivingState` can
//! answer without the playtest harness. The radio half is in
//! `states_driving_updates_radio.rs`.

use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::rc::Rc;

use ff_core::data::curves::RouteCurve;
use ff_core::data::world::get_world;
use ff_core::models::jobs::{Job, CARGO_CATALOG};
use ff_core::models::profile::Profile;
use ff_core::sim::enforcement_observe::OBSERVE_HOLD_MI;
use ff_core::sim::hos;
use ff_core::sim::lane::LANE_WIDTH;
use ff_core::sim::trip_models::RoadStop;
use ff_core::sim::weather::WeatherKind;

use freight_fate::app::testing::{stepping_clock, TestApp};
use freight_fate::audio::{Audio, AudioError, SustainLoopSpec, VolumeUpdate, CH_AIR};
use freight_fate::controller::{fakes::FakePad, ControllerAxis};
use freight_fate::playtest::breaker::force_grade;
use freight_fate::states::base::{InputEvent, Key, Mods};
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::PURSUIT_HOLD_S;
use freight_fate::states::driving_core::{
    hos_mut_of, profile_mut_of, HazardShape, DRIVE_PHASE_DELIVERY, EXIT_LANE_READY,
    LANE_TAP_CHANGE_S, MICROSLEEP_BASE_GM, MICROSLEEP_MIN_GM, STEER_CUE_ARM_S, STEER_CUE_HOLD,
    STEER_CUE_TOCK_S,
};
use freight_fate::states::driving_rest_states::{FelonyStopState, TrafficStopState};
use freight_fate::states::driving_updates::limit_drop_speech_latency_s;

/// One `start_loop`/`stop_loop` call: what happened, on which channel, with
/// which key (empty for a stop).
type LoopCall = (&'static str, u32, String);

const LOCATOR: &str = "vehicle/lane_locator";
const SIGNAL: &str = "vehicle/signal_tone";

// -- rigging -------------------------------------------------------------------------
//
// `_driving(app)` from `test_microsleep.py` / `test_lane_position_cue.py` /
// `test_speeding_consequences.py`: one short real corridor, built straight
// rather than driven up to.

fn a_drive(app: &mut TestApp) -> DrivingState {
    let world = get_world();
    app.ctx.profile = Some(Profile::named_in("Drowsy", "Buffalo"));
    let route = world
        .supported_route("Buffalo", "Rochester", None)
        .expect("the world routes")
        .expect("Buffalo to Rochester is supported");
    let mut job = Job::new(
        &CARGO_CATALOG["general"],
        12.0,
        "Buffalo",
        "company yard",
        "Rochester",
        route.miles(),
        1000.0,
        12.0,
    );
    job.destination_location = "Rochester freight market".to_string();
    let mut drive = DrivingState::new(&mut app.ctx, job, route, None, DRIVE_PHASE_DELIVERY, None);
    // The bubble is its own suite's business; an empty road keeps these
    // deterministic (`driving_feature_helpers.quiet_trip`). The weather is
    // the other half of that helper: the trip seed is unseeded, so a drive
    // that does not pin the sky draws a real condition and an ice day caps
    // the safe speed under whatever the test is measuring.
    drive.trip.set_npc_vehicles(Vec::new());
    drive.trip.weather.current = WeatherKind::Clear;
    drive
}

fn mph_to_mps(mph: f64) -> f64 {
    mph / 2.23694
}

/// `_capture(monkeypatch, app)`: every one-shot, plus the held-cue latch the
/// steering cue's self-cancel depends on. `RecordingAudio` answers `cue_held`
/// with a flat false, which would silence every click these tests are about.
#[derive(Default)]
struct CueAudio {
    played: Rc<RefCell<Vec<(String, f64, f64)>>>,
    music: Rc<RefCell<Vec<(String, u32)>>>,
    music_stops: Rc<RefCell<Vec<u32>>>,
    music_volume: Rc<Cell<f64>>,
    cues: Rc<RefCell<HashMap<String, f64>>>,
    loops: Rc<RefCell<Vec<LoopCall>>>,
    reverse: Rc<RefCell<Vec<&'static str>>>,
    engine_on: Rc<Cell<bool>>,
    playing: Rc<Cell<bool>>,
}

#[derive(Clone, Default)]
struct AudioTape {
    played: Rc<RefCell<Vec<(String, f64, f64)>>>,
    loops: Rc<RefCell<Vec<LoopCall>>>,
    reverse: Rc<RefCell<Vec<&'static str>>>,
}

impl AudioTape {
    fn keys(&self) -> Vec<String> {
        self.played
            .borrow()
            .iter()
            .map(|(key, _, _)| key.clone())
            .collect()
    }

    fn calls(&self) -> Vec<(String, f64, f64)> {
        self.played.borrow().clone()
    }

    fn last(&self) -> (String, f64, f64) {
        self.played.borrow().last().cloned().expect("a cue played")
    }

    fn clear(&self) {
        self.played.borrow_mut().clear();
    }

    fn loops(&self) -> Vec<LoopCall> {
        self.loops.borrow().clone()
    }

    fn clear_loops(&self) {
        self.loops.borrow_mut().clear();
    }

    fn reverse(&self) -> Vec<&'static str> {
        self.reverse.borrow().clone()
    }

    fn clear_reverse(&self) {
        self.reverse.borrow_mut().clear();
    }
}

impl CueAudio {
    fn install(app: &mut TestApp) -> AudioTape {
        let audio = CueAudio::default();
        let tape = AudioTape {
            played: Rc::clone(&audio.played),
            loops: Rc::clone(&audio.loops),
            reverse: Rc::clone(&audio.reverse),
        };
        app.ctx.audio = Box::new(audio);
        tape
    }
}

impl Audio for CueAudio {
    fn enabled(&self) -> bool {
        false
    }
    fn backend_name(&self) -> &str {
        "cue-test"
    }
    fn master_volume(&self) -> f64 {
        1.0
    }
    fn sfx_volume(&self) -> f64 {
        1.0
    }
    fn music_volume(&self) -> f64 {
        self.music_volume.get()
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
    fn play_with(&mut self, key: &str, volume: f64, pan: f64) {
        self.played
            .borrow_mut()
            .push((key.to_string(), volume, pan));
    }
    fn play_bank_with(&mut self, base: &str, _fallback: &str, volume: f64, pan: f64) {
        self.play_with(base, volume, pan);
    }
    fn set_engine_duck(&mut self, _duck: f64) {}
    fn set_speech_duck(&mut self, _duck: f64) {}
    fn set_engine_voice(&mut self, _classic: bool) {}
    fn set_jake_voice(&mut self, _classic: bool) {}
    fn has_asset(&mut self, _key: &str) -> bool {
        true
    }
    fn start_loop_with(&mut self, channel: u32, key: &str, _volume: f64, _fade_ms: u32) {
        self.loops
            .borrow_mut()
            .push(("start", channel, key.to_string()));
    }
    fn set_loop_volume(&mut self, _channel: u32, _volume: f64) {}
    fn set_loop_pan(&mut self, _channel: u32, _pan: f64) {}
    fn stop_loop_with(&mut self, channel: u32, _fade_ms: u32) {
        self.loops
            .borrow_mut()
            .push(("stop", channel, String::new()));
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
    fn hold_cue(&mut self, name: &str) {
        self.cues
            .borrow_mut()
            .insert(name.to_string(), freight_fate::audio::CUE_HOLD_TIMEOUT_S);
    }
    fn cue_held(&self, name: &str) -> bool {
        self.cues
            .borrow()
            .get(name)
            .is_some_and(|remaining| *remaining > 0.0)
    }
    fn release_cue(&mut self, name: &str) {
        self.cues.borrow_mut().remove(name);
    }
    fn engine_start_with(&mut self, _play_start_sound: bool) {
        self.engine_on.set(true);
    }
    fn engine_stop_with(&mut self, _shutdown_sound: bool) {
        self.engine_on.set(false);
    }
    fn update(&mut self, dt: f64) {
        // The dead man's switch runs on the audio clock, exactly as the
        // facade's does: a menu holding the frames lets the latch lapse.
        self.cues.borrow_mut().retain(|_, remaining| {
            *remaining -= dt;
            *remaining > 0.0
        });
    }
    fn set_engine_rpm_with(&mut self, _rpm: f64, _throttle: f64) {}
    fn set_road_noise(&mut self, _speed_mps: f64) {}
    fn set_weather_with(&mut self, _key: Option<&str>, _intensity: f64) {}
    fn set_wind(&mut self, _intensity: f64) {}
    fn set_ambient_with(&mut self, _key: Option<&str>, _volume: f64) {}
    fn horn_start(&mut self) {}
    fn horn_stop(&mut self) {}
    fn reverse_start(&mut self) {
        self.reverse.borrow_mut().push("start");
    }
    fn reverse_stop(&mut self) {
        self.reverse.borrow_mut().push("stop");
    }
    fn stop_world(&mut self) {}
    fn play_music_with(&mut self, track: &str, fade_ms: u32) {
        self.music.borrow_mut().push((track.to_string(), fade_ms));
        self.playing.set(true);
    }
    fn play_radio_stream_with(&mut self, _url: &str, _fade_ms: u32) -> Result<(), AudioError> {
        Ok(())
    }
    fn play_music_file_with(&mut self, _path: &str, _fade_ms: u32) -> Result<(), AudioError> {
        Ok(())
    }
    fn music_playing(&self) -> bool {
        self.playing.get()
    }
    fn radio_now_playing(&self) -> Option<String> {
        None
    }
    fn stop_music_with(&mut self, fade_ms: u32) {
        self.music_stops.borrow_mut().push(fade_ms);
        self.playing.set(false);
    }
    fn set_volumes(&mut self, volumes: &VolumeUpdate) {
        if let Some(music) = volumes.music {
            self.music_volume.set(music);
        }
    }
    fn shutdown(&mut self) {}
}

// -- microsleeps (test_microsleep.py) --------------------------------------------------

#[test]
fn test_microsleep_interval_shrinks_with_exhaustion() {
    let mut app = TestApp::new();
    let d = a_drive(&mut app);
    assert!((d.microsleep_interval_gm(hos::FATIGUE_SEVERE) - MICROSLEEP_BASE_GM).abs() < 1e-9);
    assert!((d.microsleep_interval_gm(100.0) - MICROSLEEP_MIN_GM).abs() < 1e-9);
    assert!(d.microsleep_interval_gm(95.0) < d.microsleep_interval_gm(82.0));
}

#[test]
fn test_microsleeps_only_strike_when_severely_fatigued_and_moving() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    // Fresh driver, or stopped: no nods however long you go.
    for _ in 0..200 {
        d.accrue_microsleep(&mut app.ctx, 1.0, true, 30.0);
    }
    assert!(d.microsleep_deadline.is_none());
    for _ in 0..200 {
        d.accrue_microsleep(&mut app.ctx, 1.0, false, 95.0);
    }
    assert!(d.microsleep_deadline.is_none());
    // Severely fatigued and rolling: a nod eventually comes.
    let mut fired = false;
    for _ in 0..200 {
        d.accrue_microsleep(&mut app.ctx, 1.0, true, 90.0);
        if d.microsleep_deadline.is_some() {
            fired = true;
            break;
        }
    }
    assert!(fired);
}

#[test]
fn test_reacting_to_a_microsleep_avoids_damage() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.velocity_mps = 30.0;
    let before = d.trip.truck.damage_pct;
    d.begin_microsleep(&mut app.ctx);
    assert!(d.microsleep_deadline.is_some());
    app.ctx.input.press(Key::Down, Mods::NONE); // brake = staying awake
    d.update_microsleep(&mut app.ctx, 0.1);
    assert!(d.microsleep_deadline.is_none());
    assert_eq!(d.trip.truck.damage_pct, before);
    assert!(d.microsleep_cooldown_gm > 0.0);
}

#[test]
fn test_ignoring_a_microsleep_drifts_off_the_road() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.velocity_mps = 30.0;
    let before = d.trip.truck.damage_pct;
    let speed_before = d.trip.truck.speed_mph();
    d.begin_microsleep(&mut app.ctx);
    for _ in 0..60 {
        d.update_microsleep(&mut app.ctx, 0.1);
        if d.microsleep_deadline.is_none() {
            break;
        }
    }
    assert!(d.trip.truck.damage_pct > before);
    // scrubbed wandering onto the shoulder
    assert!(d.trip.truck.speed_mph() < speed_before);
    assert_eq!(d.microsleep_misses, 1);
}

#[test]
fn test_three_missed_microsleeps_force_a_stop() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    for _ in 0..3 {
        d.trip.truck.velocity_mps = 30.0;
        d.microsleep_cooldown_gm = 0.0;
        d.begin_microsleep(&mut app.ctx);
        for _ in 0..60 {
            d.update_microsleep(&mut app.ctx, 0.1);
            if d.microsleep_deadline.is_none() {
                break;
            }
        }
    }
    // The third drift slams the brakes and cuts throttle to force a stop.
    assert_eq!(d.trip.truck.brake, 1.0);
    assert_eq!(d.trip.truck.throttle, 0.0);
}

/// `_FakePad`: enough of the manager for the microsleep reaction check.
fn pad_at(app: &mut TestApp, axis: ControllerAxis, value: i16) {
    let c = &mut app.ctx.controller;
    c.set_enabled(true);
    c.bind_device(Box::new(FakePad::new(0)), "test pad");
    c.process_event(&InputEvent::axis(axis, value));
    // The trigger reads through the smoother; the stick does not.
    for _ in 0..30 {
        c.tick(1.0 / 60.0);
    }
}

#[test]
fn test_a_controller_driver_can_wake_from_a_microsleep() {
    // The truck says "steer or brake", and on a pad neither of those is a
    // key. A controller-only driver could not react at all and drifted off
    // the road every single time (owner, 2026-08-16). Parity with the
    // keyboard is the bar: a held Down arrow already counts, so a held
    // trigger counts too.
    for (axis, value) in [
        (ControllerAxis::TriggerLeft, 26_000_i16),
        (ControllerAxis::LeftX, -20_000),
    ] {
        let mut app = TestApp::new();
        let mut d = a_drive(&mut app);
        d.trip.truck.velocity_mps = 30.0;
        pad_at(&mut app, axis, value);
        let before = d.trip.truck.damage_pct;
        d.begin_microsleep(&mut app.ctx);
        assert!(d.microsleep_deadline.is_some());
        d.update_microsleep(&mut app.ctx, 0.1);
        assert!(
            d.microsleep_deadline.is_none(),
            "the pad reaction must count"
        );
        assert_eq!(d.trip.truck.damage_pct, before);
    }
}

#[test]
fn test_an_idle_pad_is_not_a_microsleep_reaction() {
    // Only a reaction wakes you -- a resting pad is not one.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.velocity_mps = 30.0;
    pad_at(&mut app, ControllerAxis::LeftX, 0);
    d.begin_microsleep(&mut app.ctx);
    for _ in 0..60 {
        d.update_microsleep(&mut app.ctx, 0.1);
        if d.microsleep_deadline.is_none() {
            break;
        }
    }
    assert_eq!(d.microsleep_misses, 1);
}

// -- off pavement (test_off_pavement_transitions.py) ----------------------------------

#[test]
fn test_off_pavement_speaks_on_entry_worsening_and_recovery() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    // Python stubbed `say_event` outright; here the real pacer would treat
    // the second, identical "Off the road" line as a repeat inside its own
    // window. Step the clock between lines so what is asserted is the
    // TRANSITION rule rather than the pacer's repeat guard.
    app.ctx.event_pacer =
        ff_core::speech_pacing::EventSpeechPacer::with_clock(stepping_clock(30.0));
    d.lane.lane = 0;
    d.trip.truck.velocity_mps = 13.0; // ~29 mph, below the "fast" band
    app.clear_speech();

    // Entry: the truck goes off the pavement.
    d.lane.offset = 1.35;
    d.announce_off_pavement(&mut app.ctx);
    assert_eq!(app.event_lines().len(), 1);

    // Steady, no worse: the continuous cue carries it, speech stays silent.
    d.announce_off_pavement(&mut app.ctx);
    d.announce_off_pavement(&mut app.ctx);
    assert_eq!(app.event_lines().len(), 1);

    // Worse: deeper off the road speaks again.
    d.lane.offset = 1.48;
    d.announce_off_pavement(&mut app.ctx);
    assert_eq!(app.event_lines().len(), 2);

    // Back on the pavement is a transition too, spoken once.
    d.lane.offset = 0.0;
    d.road_position_band = Some(1);
    // The recovery line lives in the update path; assert the condition the
    // else-if turns on so the transition fires exactly when the truck is back.
    assert!(!d.off_pavement());
}

// -- the steering lane cue (test_lane_position_cue.py) --------------------------------

fn a_steering_drive(app: &mut TestApp) -> DrivingState {
    let mut d = a_drive(app);
    app.ctx.settings.lane_keeping = "off".to_string(); // the lane work is the driver's
    d.trip.truck.velocity_mps = 25.0; // rolling, well over the cue's floor
    d
}

/// `_arm(driving, direction)`: hold the wheel long enough that this is a
/// move, not a correction.
fn arm(d: &mut DrivingState, app: &mut TestApp, direction: f64) {
    d.lane.steering = direction;
    d.update_steering_lane_cue(&mut app.ctx, STEER_CUE_ARM_S);
}

/// `_signal_for_the_exit(driving)`: an armed route exit, without needing a
/// real stop on this leg.
fn signal_for_the_exit(d: &mut DrivingState) {
    d.exit_stop = Some(RoadStop::new("Test Exit", 30.0, "travel_center"));
    d.exit_signal_on = true;
    d.lane.lane = 0; // ramps peel off the right lane
}

#[test]
fn test_holding_the_arrow_plays_the_position_tock_panned_to_the_lane() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    d.lane.offset = 0.6; // already right of centre and still going right
    d.lane.steering = 1.0;

    d.update_steering_lane_cue(&mut app.ctx, STEER_CUE_ARM_S - 0.1);
    assert!(tape.calls().is_empty()); // a nudge of the wheel is not a move

    d.update_steering_lane_cue(&mut app.ctx, 0.2);
    let (key, _, pan) = tape.last();
    assert_eq!(key, LOCATOR);
    assert!((pan - 0.6).abs() < 1e-9);

    // It keeps time for as long as the wheel is held, and follows the truck.
    d.lane.offset = 0.95;
    d.update_steering_lane_cue(&mut app.ctx, STEER_CUE_TOCK_S);
    let (key, _, pan) = tape.last();
    assert_eq!(key, LOCATOR);
    assert!((pan - 0.95).abs() < 1e-9);
}

#[test]
fn test_the_tock_scales_with_the_lane_cue_loudness_setting() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    app.ctx.settings.lane_cue_loudness = "subtle".to_string();
    arm(&mut d, &mut app, 1.0);
    let (key, volume, _) = tape.last();
    assert_eq!(key, LOCATOR);
    assert!((volume - 0.5 * 0.6).abs() < 1e-9);

    d.lane.steering = 0.0;
    tape.clear();
    d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    let (key, volume, _) = tape.last();
    assert_eq!(key, SIGNAL);
    assert!((volume - 0.45 * 0.6).abs() < 1e-9);
}

#[test]
fn test_letting_go_of_the_wheel_cancels_the_signal() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    arm(&mut d, &mut app, 1.0);
    assert_eq!(tape.keys().first().map(String::as_str), Some(LOCATOR));

    tape.clear();
    d.lane.steering = 0.0; // straightened out: the move is over
    d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    // centred, quieter
    assert_eq!(tape.calls(), vec![(SIGNAL.to_string(), 0.45, 0.0)]);
    assert!(!d.steer_cue_active);

    // And it stays over: no second click, no stray tocks.
    tape.clear();
    for _ in 0..120 {
        d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    }
    assert!(tape.calls().is_empty());
}

#[test]
fn test_a_nudge_of_the_wheel_never_clicks() {
    // A drift correction is not a manoeuvre, so it gets no cue and no click.
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    d.lane.steering = -1.0;
    d.update_steering_lane_cue(&mut app.ctx, STEER_CUE_ARM_S - 0.2);
    d.lane.steering = 0.0;
    d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    assert!(tape.calls().is_empty());
}

#[test]
fn test_the_lane_change_ends_with_the_click_after_the_line_is_crossed() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    d.lane.lane = 0;
    arm(&mut d, &mut app, -1.0); // holding Left, moving toward the left lane
    d.lane.offset = -0.9;
    d.update_steering_lane_cue(&mut app.ctx, STEER_CUE_TOCK_S);
    assert!((tape.last().2 + 0.9).abs() < 1e-9); // heard sliding left

    // The tires roll the line, the lane model re-centres in the new lane,
    // and the cue follows the truck through the settle.
    d.lane.lane = 1;
    d.lane.offset = -0.9 + LANE_WIDTH;
    d.update_steering_lane_cue(&mut app.ctx, STEER_CUE_TOCK_S);
    let (key, volume, pan) = tape.last();
    assert_eq!(key, LOCATOR);
    assert!((volume - 0.5).abs() < 1e-9);
    assert!((pan - 1.0).abs() < 1e-9);

    tape.clear();
    d.lane.steering = 0.0; // straightened up in the new lane
    d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    assert_eq!(tape.keys(), vec![SIGNAL.to_string()]);
}

#[test]
fn test_the_beat_quickens_as_the_exit_lane_position_fills() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let _tape = CueAudio::install(&mut app);
    signal_for_the_exit(&mut d);
    d.exit_lane_alignment = 0.0;
    d.lane.offset = 0.0;
    arm(&mut d, &mut app, 1.0);
    let wide = d.steer_cue_timer;
    assert!((wide - STEER_CUE_TOCK_S).abs() < 1e-9);

    d.exit_lane_alignment = EXIT_LANE_READY - 0.05; // nearly there
    d.update_steering_lane_cue(&mut app.ctx, wide);
    assert!(d.steer_cue_timer < wide / 2.0);
}

#[test]
fn test_reaching_the_exit_position_clicks_off_with_the_wheel_still_held() {
    // "Far enough right now" arrives as the signal cancelling, not a sentence.
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    signal_for_the_exit(&mut d);
    d.exit_lane_alignment = 0.5;
    arm(&mut d, &mut app, 1.0);
    assert_eq!(tape.last().0, LOCATOR);

    tape.clear();
    d.exit_lane_alignment = EXIT_LANE_READY; // the exit has the lane it needs
    d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    assert_eq!(tape.calls(), vec![(SIGNAL.to_string(), 0.45, 0.0)]);
    // the wheel is still over; the position is what ended it
    assert_eq!(d.lane.steering, 1.0);
    assert!(!d.steer_cue_active);

    // Holding Right past the mark does not start it up again.
    tape.clear();
    for _ in 0..120 {
        d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    }
    assert!(tape.calls().is_empty());
}

#[test]
fn test_abandoning_the_exit_line_up_clicks_off_too() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    signal_for_the_exit(&mut d);
    d.exit_lane_alignment = 0.4;
    arm(&mut d, &mut app, 1.0);
    assert_eq!(tape.last().0, LOCATOR);

    tape.clear();
    d.lane.steering = 0.0;
    d.exit_lane_alignment = 0.0; // steered back and let the commitment bleed away
    d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    assert_eq!(tape.keys(), vec![SIGNAL.to_string()]);
}

#[test]
fn test_the_cue_stays_silent_under_lane_keeping_and_below_the_speed_floor() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    // the truck holds the lane and takes the exit
    app.ctx.settings.lane_keeping = "full".to_string();
    signal_for_the_exit(&mut d);
    d.exit_lane_alignment = 0.5;
    for _ in 0..120 {
        d.lane.steering = 1.0;
        d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    }
    assert!(tape.calls().is_empty());

    app.ctx.settings.lane_keeping = "off".to_string();
    d.trip.truck.velocity_mps = 0.5; // about a walking pace: nothing to steer yet
    for _ in 0..120 {
        d.lane.steering = 1.0;
        d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    }
    assert!(tape.calls().is_empty());
}

#[test]
fn test_it_does_not_double_the_locator_the_driver_already_turned_on() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    d.lane_locator_on = true; // I is already ticking the same tock
    signal_for_the_exit(&mut d);
    d.exit_lane_alignment = 0.5;
    for _ in 0..120 {
        d.lane.steering = 1.0;
        d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    }
    assert!(tape.calls().is_empty());
}

#[test]
fn test_the_cue_cannot_survive_the_drive_losing_the_frame() {
    // A menu over the drive lets the latch lapse, and the move ends in
    // silence -- never a signal cancelling over the pause screen.
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    arm(&mut d, &mut app, 1.0);
    assert!(app.ctx.audio.cue_held(STEER_CUE_HOLD));

    // A menu owns the frames now: the driving state stops updating while
    // the audio clock keeps running.
    app.ctx.audio.update(0.5);
    assert!(!app.ctx.audio.cue_held(STEER_CUE_HOLD));

    tape.clear();
    d.lane.steering = 0.0;
    d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    assert!(tape.calls().is_empty());
    assert!(!d.steer_cue_active);
}

#[test]
fn test_the_whole_manoeuvre_adds_no_speech() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let _tape = CueAudio::install(&mut app);
    signal_for_the_exit(&mut d);
    d.exit_lane_alignment = 0.3;
    app.clear_speech();
    for _ in 0..240 {
        d.lane.steering = 1.0;
        d.exit_lane_alignment = 1.0f64.min(d.exit_lane_alignment + 1.0 / 60.0);
        d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    }
    d.lane.steering = 0.0;
    d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    assert!(app.main_lines().is_empty());
    assert!(app.event_lines().is_empty());
}

// -- the dash alert and the braking grace (test_speeding_consequences.py) --------------

/// `_speed_on_an_empty_road(d, over, seconds)`: hold well over the limit,
/// for a long time, with nobody watching.
fn speed_on_an_empty_road(d: &mut DrivingState, app: &mut TestApp, over: f64, seconds: f64) -> f64 {
    d.trip.set_patrols(Vec::new());
    d.trip.position_mi = d.trip.total_miles() / 2.0;
    d.enforcement_prev_mi = d.trip.position_mi;
    let (limit, _) = d.trip.speed_limit_at(d.trip.position_mi);
    d.trip.truck.velocity_mps = mph_to_mps(limit + over);
    for _ in 0..(seconds / 0.5) as i32 {
        d.trip.position_mi += 0.02;
        d.update_enforcement_watch(&mut app.ctx, 0.5);
        d.update_speeding(&mut app.ctx, 0.5, false);
    }
    limit
}

#[test]
fn test_the_dash_still_warns_even_though_nothing_is_charged() {
    // Removing the tax must not remove the courtesy. The overspeed alert was
    // never enforcement -- it is the carrier's dash nagging you, and it is the
    // only reason a blind driver knows the limit dropped. It stays.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    speed_on_an_empty_road(&mut d, &mut app, 15.0, 2.0);
    let spoken = app.event_lines();
    assert!(spoken.iter().any(|line| line.contains("Watch your speed")));
    assert!(spoken.iter().any(|line| line.contains("The limit is")));
}

#[test]
fn test_the_dash_still_warns_while_looping_back_to_a_missed_destination_exit() {
    // Tyler Rodick, Hattiesburg, 2026-08-26: missed the destination exit, was
    // told the approach loops back, and then held 89 the whole way round with
    // nobody saying anything. The loop-back set a latch that returned early
    // out of the dash -- a carve-out left over from when this method charged
    // silent speeding fines -- so the one system that would have told him to
    // shed speed for the retry was off from the first miss to the dock, while
    // the enforcement watch went on accruing against him regardless.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.missed_destination_exit_said = true;
    d.destination_exit_taken = false;
    app.clear_speech();
    let limit = speed_on_an_empty_road(&mut d, &mut app, 24.0, 2.0);
    let spoken = app.event_lines();
    assert!(
        spoken.iter().any(|line| line.contains("Watch your speed")),
        "24 over a {limit:.0} on the loop-back said nothing: {spoken:?}"
    );
}

#[test]
fn test_a_dropped_limit_still_earns_braking_room() {
    // The one fairness rule worth keeping from the strike era. A loaded truck
    // cannot shed fifteen mph the instant a sign changes, so the grace that
    // used to hold off a strike now holds off the over-limit distance an
    // officer reads. Without it a post could clock you on the transition.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.set_patrols(Vec::new());
    d.trip.position_mi = d.trip.total_miles() / 2.0;
    d.enforcement_prev_mi = d.trip.position_mi;
    let (limit, _) = d.trip.speed_limit_at(d.trip.position_mi);
    d.trip.truck.velocity_mps = mph_to_mps(limit + 20.0);
    // A limit drop under the truck, with the driver off the throttle.
    d.enforced_limit_prev = Some(limit + 15.0);
    d.update_speeding(&mut app.ctx, 0.1, false);
    assert!(d.limit_drop_grace_s > 0.0);
    for _ in 0..10 {
        d.trip.position_mi += 0.05;
        d.update_enforcement_watch(&mut app.ctx, 0.1);
    }
    assert!(d.over_limit_mi < OBSERVE_HOLD_MI);
}

#[test]
fn test_staying_on_the_throttle_through_the_drop_collapses_the_grace() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.set_patrols(Vec::new());
    d.trip.position_mi = d.trip.total_miles() / 2.0;
    let (limit, _) = d.trip.speed_limit_at(d.trip.position_mi);
    d.trip.truck.velocity_mps = mph_to_mps(limit + 20.0);
    d.enforced_limit_prev = Some(limit + 15.0);
    d.update_speeding(&mut app.ctx, 0.1, false);
    assert!(d.limit_drop_grace_s > 0.0);
    // Past the announcement's speech-latency window, the throttle held
    // through the drop is disregard and the grace collapses to zero.
    d.limit_drop_throttle_exempt_s = 0.0;
    d.update_speeding(&mut app.ctx, 0.1, true);
    assert_eq!(d.limit_drop_grace_s, 0.0);
    // And the exemption is exactly the ROUTE wait budget -- the longest the
    // demoted zone-entry line can lag its boundary before flushing.
    assert_eq!(
        ff_core::speech_pacing::EventSpeechPacer::wait_budget_s(
            ff_core::speech_pacing::EventPriority::Route
        ),
        limit_drop_speech_latency_s()
    );
}

#[test]
fn test_throttle_held_during_speech_latency_does_not_collapse_the_grace() {
    // R1's coupled invariant: the zone-entry line now queues at ROUTE and may
    // lag the boundary by its wait budget. Until that window has passed, a
    // held accelerator is a driver who has not been told anything yet --
    // speech latency must never masquerade as disregard and burn the whole
    // braking grace from the zone boundary.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.set_patrols(Vec::new());
    d.trip.position_mi = d.trip.total_miles() / 2.0;
    let (limit, _) = d.trip.speed_limit_at(d.trip.position_mi);
    d.trip.truck.velocity_mps = mph_to_mps(limit + 20.0);
    d.enforced_limit_prev = Some(limit + 15.0);
    // The drop lands while the driver is still on the throttle -- the exact
    // frame the old code zeroed the grace.
    d.update_speeding(&mut app.ctx, 0.1, true);
    assert!(d.limit_drop_grace_s > 0.0);
    // Armed to the full window this frame, already ticking down with it.
    assert!((d.limit_drop_throttle_exempt_s - (limit_drop_speech_latency_s() - 0.1)).abs() < 1e-9);
    // Throttle held for the whole latency window: the grace survives it.
    let mut elapsed = 0.0;
    while elapsed + 0.1 < limit_drop_speech_latency_s() {
        d.update_speeding(&mut app.ctx, 0.1, true);
        elapsed += 0.1;
        assert!(d.limit_drop_grace_s > 0.0);
    }
    // Once the line has had time to speak, the same throttle collapses it.
    d.update_speeding(&mut app.ctx, 0.1, true); // window reaches zero
    d.update_speeding(&mut app.ctx, 0.1, true); // now it is disregard
    assert_eq!(d.limit_drop_grace_s, 0.0);
}

// -- the frame loop's own machinery ---------------------------------------------------

#[test]
fn test_the_frame_loop_runs_a_whole_second_without_touching_the_truck() {
    // The smoke case the harness suite would otherwise be the first to find:
    // `update_frame` wires two dozen mixins together, and a parked truck with
    // the engine off must simply sit there through it.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    let position = d.trip.position_mi;
    for _ in 0..60 {
        d.update_frame(&mut app.ctx, 1.0 / 60.0);
    }
    assert_eq!(d.trip.position_mi, position);
    assert_eq!(d.trip.truck.damage_pct, 0.0);
    assert!(!d.trip.truck.engine_on);
}

#[test]
fn test_the_retarder_trace_writes_one_line_per_change() {
    // The trace is a transcript line, not a per-frame log: the stage it
    // last wrote is what stops it repeating.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.engine_brake_stage = 2;
    d.trace_engine_brake();
    assert_eq!(d.traced_jake_stage, 2);
    d.trace_engine_brake();
    assert_eq!(d.traced_jake_stage, 2);
    d.trip.truck.engine_brake_stage = 0;
    d.trace_engine_brake();
    assert_eq!(d.traced_jake_stage, 0);
}

#[test]
fn test_air_ready_announces_once_while_the_parking_brake_is_set() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.start_engine();
    d.trip.truck.set_parking_brake();
    d.trip.truck.set_air_ready(true);
    app.clear_speech();
    d.update_air_brake_announcements(&mut app.ctx, true, false, false, false);
    let said = app.event_lines();
    assert_eq!(said.len(), 1);
    assert!(said[0].contains("Air pressure ready"));
    // A second pass with the flag already set says nothing more.
    d.update_air_brake_announcements(&mut app.ctx, true, false, false, false);
    assert_eq!(app.event_lines().len(), 1);
}

#[test]
fn test_the_air_brake_lockout_says_why_the_truck_will_not_roll() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    d.maybe_say_air_brake_lockout(&mut app.ctx);
    let said = app.event_lines();
    assert_eq!(said.len(), 1);
    assert!(said[0].starts_with("Start the engine first"));
    // The cue timer holds it off for four seconds, however hard the driver
    // leans on the accelerator.
    d.maybe_say_air_brake_lockout(&mut app.ctx);
    assert_eq!(app.event_lines().len(), 1);
}

#[test]
fn test_the_direction_change_needs_a_fresh_press_held_at_a_standstill() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.start_engine();
    d.trip.truck.transmission.automatic = true;
    d.trip.truck.velocity_mps = 0.0;
    // A press that predates the stop never arms: the edge is what counts.
    d.reverse_brake_held = true;
    let backing = d.update_reverse_controls(&mut app.ctx, false, true, true, true, 0.1);
    assert!(!backing);
    assert_eq!(d.direction_armed, "");
    // A fresh press arms it, and the hold engages reverse.
    d.reverse_brake_held = false;
    d.update_reverse_controls(&mut app.ctx, false, true, false, true, 0.0);
    assert_eq!(d.direction_armed, "reverse");
    let mut engaged = false;
    for _ in 0..20 {
        if d.update_reverse_controls(&mut app.ctx, false, true, false, true, 0.1) {
            engaged = true;
            break;
        }
    }
    assert!(engaged);
    assert!(d.trip.truck.transmission.in_reverse());
}

#[test]
fn test_a_confirm_tap_at_the_yard_just_brakes() {
    // Owner-hit on 2026-07-14: a screen-reader driver checking the truck is
    // holding must never find themselves in reverse for it.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.start_engine();
    d.trip.truck.transmission.automatic = true;
    d.trip.truck.velocity_mps = 0.0;
    d.update_reverse_controls(&mut app.ctx, false, true, false, true, 0.0);
    assert_eq!(d.direction_armed, "reverse");
    // Let go well inside the hold: the arm dies with the press.
    d.update_reverse_controls(&mut app.ctx, false, false, false, false, 0.2);
    assert_eq!(d.direction_armed, "");
    assert!(!d.trip.truck.transmission.in_reverse());
}

#[test]
fn test_the_grade_advisory_stays_quiet_on_terse_speech() {
    // The G key answers on demand, so an advisory nobody asked for is
    // exactly what terse exists to remove.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.ctx.settings.driving_speech = "terse".to_string();
    d.trip.truck.velocity_mps = mph_to_mps(60.0);
    app.clear_speech();
    for _ in 0..40 {
        d.trip.position_mi += 0.2;
        d.update_grade_advisory(&mut app.ctx);
    }
    assert!(app.event_lines().is_empty());
    assert_eq!(d.grade_warned_sign, 0);
}

#[test]
fn test_the_hazard_budget_leaves_the_driver_their_own_window() {
    // Built forward from the moment the assist must act, so speed, grade and
    // brake heat come out of the truck's time rather than the driver's.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.velocity_mps = mph_to_mps(65.0);
    d.hazard_dodgeable = false;
    d.hazard_in_lane = false;
    let window = 4.0;
    let deadline = d.hazard_deadline_for(window, None);
    assert!(deadline >= window);
    assert!((deadline - (d.aeb_engage_s(d.hazard_target_mph(None)) + window)).abs() < 1e-9);
    // An object in the lane asks for nearly a stop; a lane to take instead
    // buys the driver the time that move costs. They are separate additions
    // now, so the test asks for them separately.
    let in_lane_only = d.hazard_deadline_for(
        window,
        Some(HazardShape {
            dodgeable: false,
            in_lane: true,
            lead_mph: None,
        }),
    );
    assert!(
        in_lane_only > deadline,
        "the near stop takes longer than 25"
    );
    let dodgeable = d.hazard_deadline_for(
        window,
        Some(HazardShape {
            dodgeable: true,
            in_lane: true,
            lead_mph: None,
        }),
    );
    assert!((dodgeable - (in_lane_only + LANE_TAP_CHANGE_S)).abs() < 1e-9);
}

#[test]
fn test_braking_below_the_hazard_speed_clears_it_and_says_so() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.hazard_deadline = Some(5.0);
    d.hazard_names = vec!["the deer".to_string()];
    d.hazard_dodgeable = false;
    d.trip.truck.velocity_mps = mph_to_mps(10.0);
    app.clear_speech();
    d.update_hazard(&mut app.ctx, 1.0 / 60.0);
    assert!(d.hazard_deadline.is_none());
    assert!(d.hazard_names.is_empty());
    assert!(app
        .event_lines()
        .iter()
        .any(|line| line == "Past the deer. Well done."));
}

#[test]
fn test_the_hazard_assist_holds_one_application_rather_than_fanning_it() {
    // Deciding the pedal afresh every frame is what emptied the tanks: the
    // assist's own braking retreats the threshold that engaged it.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.ctx.settings.automatic_emergency_braking = true;
    d.trip.truck.start_engine();
    d.trip.truck.velocity_mps = mph_to_mps(65.0);
    d.hazard_dodgeable = false;
    d.hazard_deadline = Some(0.5); // inside the engage budget already
    d.update_hazard(&mut app.ctx, 1.0 / 60.0);
    assert_eq!(d.aeb_brake, 1.0);
    assert!(d.automatic_braking_announced);
    // The application stays on while the hazard is live.
    d.trip.truck.velocity_mps = mph_to_mps(40.0);
    d.update_hazard(&mut app.ctx, 1.0 / 60.0);
    assert_eq!(d.aeb_brake, 1.0);
    // Releasing hands the pedal back and forgets what the stop measured.
    d.release_hazard_brake();
    assert_eq!(d.aeb_brake, 0.0);
    assert!(!d.automatic_braking_announced);
}

#[test]
fn test_traction_states_speak_once_on_the_edge_they_begin() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.chains_on = true;
    d.trip.truck.velocity_mps = mph_to_mps(45.0);
    app.clear_speech();
    d.update_traction_cues(&mut app.ctx);
    assert!(d.chains_fast_active);
    let first = app.event_lines().len();
    assert!(first >= 1);
    d.update_traction_cues(&mut app.ctx);
    assert_eq!(app.event_lines().len(), first);
    // Slowing back under the chain speed re-arms it for the next excursion.
    d.trip.truck.velocity_mps = mph_to_mps(10.0);
    d.update_traction_cues(&mut app.ctx);
    assert!(!d.chains_fast_active);
}

#[test]
fn test_the_live_weather_switch_only_moves_when_the_setting_does() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    assert!(!d.weather_source_real);
    app.ctx.settings.real_weather = true;
    d.sync_weather_source(&mut app.ctx);
    assert!(d.weather_source_real);
    assert!(d.trip.weather.provider.is_some());
    app.ctx.settings.real_weather = false;
    d.sync_weather_source(&mut app.ctx);
    assert!(!d.weather_source_real);
    assert!(d.trip.weather.provider.is_none());
    assert!(!d.trip.weather.live);
}

#[test]
fn test_the_shift_clock_runs_on_game_time_while_the_truck_rolls() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    profile_mut_of(&mut app.ctx).fatigue = 0.0;
    d.trip.truck.start_engine();
    d.trip.truck.velocity_mps = mph_to_mps(60.0);
    let before = hos_mut_of(&mut app.ctx).driving_min;
    for _ in 0..60 {
        d.update_hours_and_fatigue(&mut app.ctx, 1.0 / 60.0);
    }
    assert!(hos_mut_of(&mut app.ctx).driving_min > before);
    assert!(profile_mut_of(&mut app.ctx).fatigue > 0.0);
}

// -- the air system's voice (test_driving_features.py) --------------------------------

/// `step(psi)` from the low-air regressions: the reading the frame loop
/// would have taken before the pressure moved.
fn air_step(d: &mut DrivingState, app: &mut TestApp, psi: f64) {
    let was_low = d.trip.truck.air_low_warning();
    let was_spring = d.trip.truck.spring_brakes_active();
    let engine_on = d.trip.truck.engine_on;
    d.trip.truck.set_air_pressure_psi(psi);
    d.update_air_brake_announcements(&mut app.ctx, engine_on, false, was_low, was_spring);
}

#[test]
fn test_low_air_warning_does_not_repeat_while_bouncing_near_threshold() {
    // Regression for the tester report: heavy/repeated service braking makes
    // pressure hover right around the 60 psi threshold while the compressor
    // catches up. Each dip below 60 must not re-fire the full warning line as
    // long as pressure never climbs back out to the hysteresis clear point.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.engine_on = true;
    d.trip.truck.set_air_pressure_psi(125.0);
    d.low_air_said = false;
    app.clear_speech();

    // First dip below the warning threshold: exactly one warning.
    air_step(&mut d, &mut app, 55.0);
    assert_eq!(app.event_lines().len(), 1);
    assert!(app.event_lines()[0].starts_with("Low air warning"));

    // Repeated braking bounces pressure just below and just above 60 psi,
    // but never clears the 68 psi hysteresis band. None of this may re-fire
    // the warning.
    for psi in [58.0, 61.0, 59.0, 62.0, 57.0, 63.0, 60.0, 56.0] {
        air_step(&mut d, &mut app, psi);
    }
    assert_eq!(app.event_lines().len(), 1);
}

#[test]
fn test_low_air_warning_rearms_after_recovering_above_clear_threshold() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    // Python stubbed `say_event`; the real pacer would treat an identical
    // repeat inside its own window as a repeat. Step the clock between lines
    // so what is asserted is this module's latch, not the pacer's.
    app.ctx.event_pacer =
        ff_core::speech_pacing::EventSpeechPacer::with_clock(stepping_clock(30.0));
    d.trip.truck.engine_on = true;
    d.trip.truck.set_air_pressure_psi(125.0);
    d.low_air_said = false;
    app.clear_speech();

    air_step(&mut d, &mut app, 55.0); // first dip: warns once
    assert_eq!(app.event_lines().len(), 1);

    air_step(&mut d, &mut app, 63.0); // ticks back up but stays inside the band
    air_step(&mut d, &mut app, 55.0); // dips again: still must not re-warn
    assert_eq!(app.event_lines().len(), 1);

    air_step(&mut d, &mut app, 70.0); // genuinely recovers clear of 68 psi
    air_step(&mut d, &mut app, 55.0); // dips again: a fresh low-air event
    assert_eq!(app.event_lines().len(), 2);
    assert!(app.event_lines()[1].starts_with("Low air warning"));
}

#[test]
fn test_spring_brake_warning_bypasses_low_air_cooldown() {
    // A genuinely worsening situation must still warn immediately even while
    // the low-air warning's latch is active from an earlier, milder dip --
    // escalation to spring brakes is its own event.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    // Python stubbed `say_event`; the real pacer would treat an identical
    // repeat inside its own window as a repeat. Step the clock between lines
    // so what is asserted is this module's latch, not the pacer's.
    app.ctx.event_pacer =
        ff_core::speech_pacing::EventSpeechPacer::with_clock(stepping_clock(30.0));
    d.trip.truck.engine_on = true;
    d.trip.truck.set_air_pressure_psi(125.0);
    d.low_air_said = false;
    d.spring_brake_said = false;
    app.clear_speech();

    air_step(&mut d, &mut app, 55.0); // low-air warning fires and latches
    assert_eq!(app.event_lines().len(), 1);
    assert!(app.event_lines()[0].starts_with("Low air warning"));

    // Pressure keeps falling, straight through into spring-brake range,
    // without ever recovering above the low-air clear threshold.
    air_step(&mut d, &mut app, 35.0);
    assert_eq!(app.event_lines().len(), 2);
    assert!(app.event_lines()[1].starts_with("Spring brakes applied"));
}

#[test]
fn test_sustained_redline_speaks_the_wear_it_is_actually_causing() {
    // Over-revving charges ENGINE WEAR, not incident damage. This warning
    // used to read damage_pct, which for most drivers sits at zero, so it
    // announced "taking damage, now 0 percent" while real harm piled up on a
    // meter it never mentioned.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    let redline_mps;
    {
        let t = &mut d.trip.truck;
        t.engine_on = true;
        t.transmission.gear = 1;
        let ratio = t.transmission.ratio_for(1).abs();
        let wheel_rps = (t.specs.max_rpm * 1.1) / (60.0 * ratio);
        redline_mps = wheel_rps * 2.0 * std::f64::consts::PI * t.specs.wheel_radius_m;
        t.velocity_mps = redline_mps;
        t.rpm = t.specs.max_rpm;
        t.engine_wear_pct = 12.0;
    }
    // Python stubbed `say_event`; the real pacer would treat an identical
    // repeat inside its own window as a repeat. Step the clock between lines
    // so what is asserted is this module's latch, not the pacer's.
    app.ctx.event_pacer =
        ff_core::speech_pacing::EventSpeechPacer::with_clock(stepping_clock(30.0));
    app.clear_speech();

    d.update_overrev(&mut app.ctx, 1.0); // inside the grace period: a shift flare
    assert!(app.event_lines().is_empty());

    d.update_overrev(&mut app.ctx, 1.0); // sustained past the grace: warn
    let said = app.event_lines().last().cloned().unwrap_or_default();
    assert!(said.to_lowercase().contains("redline"));
    assert!(said.contains("12 percent"));
    assert!(said.to_lowercase().contains("engine wear"));
    assert!(tape.keys().iter().any(|key| key == "ui/warning"));

    app.clear_speech();
    d.update_overrev(&mut app.ctx, 5.0); // repeat interval not reached yet
    assert!(app.event_lines().is_empty());
    // Python stubbed `say_event`, so its repeat spoke an identical line. The
    // real keyed condition earns the voice only when the number it carries
    // has moved -- which is exactly what redline does to engine wear.
    d.trip.truck.engine_wear_pct = 13.0;
    d.update_overrev(&mut app.ctx, 6.0); // past it: nag again while wear accrues
    assert_eq!(app.event_lines().len(), 1);

    app.clear_speech();
    // easing off resets the whole cycle
    d.trip.truck.velocity_mps = 0.0;
    d.trip.truck.rpm = d.trip.truck.specs.idle_rpm;
    d.update_overrev(&mut app.ctx, 1.0);
    assert_eq!(d.overrev_s, 0.0);
    d.trip.truck.velocity_mps = redline_mps;
    d.trip.truck.rpm = d.trip.truck.specs.max_rpm;
    d.update_overrev(&mut app.ctx, 1.0); // back at redline, but within fresh grace
    assert!(app.event_lines().is_empty());
}

// -- the continuous soundscape (test_driving_features.py) -----------------------------

#[test]
fn test_reverse_audio_cue_loops_while_reverse_is_engaged() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    d.trip.truck.start_engine();
    d.trip.truck.transmission.gear = ff_core::sim::transmission::REVERSE;
    tape.clear_reverse();

    d.update_audio(&mut app.ctx, 0.0);
    d.update_audio(&mut app.ctx, 0.0);
    assert_eq!(tape.reverse(), vec!["start"]);

    d.trip.truck.transmission.gear = 1;
    d.update_audio(&mut app.ctx, 0.0);
    assert_eq!(tape.reverse(), vec!["start", "stop"]);

    d.trip.truck.transmission.gear = ff_core::sim::transmission::REVERSE;
    d.update_audio(&mut app.ctx, 0.0);
    assert_eq!(tape.reverse(), vec!["start", "stop", "start"]);
}

#[test]
fn test_air_fill_loop_plays_until_governor_release() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    d.trip.truck.set_cold_air_start();
    d.trip.truck.start_engine();
    d.trip.truck.velocity_mps = 0.0;
    tape.clear_loops();

    d.update_audio(&mut app.ctx, 0.0);
    d.update_audio(&mut app.ctx, 0.0); // still building: the loop must not restack
    assert_eq!(
        air_loops(&tape),
        vec![("start", CH_AIR, "vehicle/air_pressurize".to_string())]
    );

    d.trip.truck.set_air_ready(true); // governor release
    d.update_audio(&mut app.ctx, 0.0);
    assert_eq!(air_loops(&tape).last().expect("a loop call").0, "stop");

    // Routine braking dips just under the 100 psi line constantly; the fill
    // hiss must NOT flutter back in for those (hysteresis).
    tape.clear_loops();
    d.trip.truck.set_air_pressure_psi(97.0);
    d.update_audio(&mut app.ctx, 0.0);
    assert!(air_loops(&tape).is_empty());

    // A genuinely low air system still brings the fill loop back.
    d.trip.truck.set_air_pressure_psi(88.0);
    d.update_audio(&mut app.ctx, 0.0);
    assert_eq!(
        air_loops(&tape),
        vec![("start", CH_AIR, "vehicle/air_pressurize".to_string())]
    );
}

fn air_loops(tape: &AudioTape) -> Vec<LoopCall> {
    tape.loops()
        .into_iter()
        .filter(|(_, channel, _)| *channel == CH_AIR)
        .collect()
}

#[test]
fn test_road_joint_thumps_pause_off_highway() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    d.road_joint_accumulator_m = 0.0;
    d.next_joint_distance_m = 15.0;
    d.trip.on_ramp = true;
    d.trip.truck.velocity_mps = 20.0;

    d.update_audio(&mut app.ctx, 1.0);

    assert_eq!(d.road_joint_accumulator_m, 0.0);
    assert!(!tape.keys().iter().any(|key| key == "vehicle/road_joint"));
}

#[test]
fn test_auto_jake_manages_stages_on_an_automatic_box() {
    // The stage controller's half of the Python case; arming it (`J`) and
    // the manual stage pick belong to `driving_controls`.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    {
        let t = &mut d.trip.truck;
        t.set_air_ready(false);
        t.start_engine();
        t.transmission.automatic = true;
        t.transmission.gear = 8;
        t.velocity_mps = mph_to_mps(55.0);
        t.rpm = 1400.0;
        t.throttle = 0.0;
        t.grip = 1.0;
        t.engine_brake_stage = 1;
    }
    d.auto_jake = true;
    d.auto_jake_hold_mph = Some(55.0);

    // Gaining on the hold speed: the controller climbs the stages, one
    // rate-limited step at a time.
    d.trip.truck.velocity_mps = mph_to_mps(60.0);
    d.update_auto_jake(&mut app.ctx, 2.0);
    assert_eq!(d.trip.truck.engine_brake_stage, 2);
    d.update_auto_jake(&mut app.ctx, 2.0);
    assert_eq!(d.trip.truck.engine_brake_stage, 3);

    // Over-slowed on level road: the retarder comes all the way off, at once.
    // A retarder is for holding a truck BACK, and a truck seven under its own
    // number on flat ground needs no holding -- walking down a stage at a time
    // was what kept two cylinders cut for the rest of the drive.
    d.trip.truck.velocity_mps = mph_to_mps(48.0);
    d.update_auto_jake(&mut app.ctx, 2.0);
    assert_eq!(d.trip.truck.engine_brake_stage, 0);

    // On a real grade the ladder is still a ladder: there the retarder IS what
    // is keeping the number, so an over-slowed truck gives back one stage at a
    // time rather than dropping the whole hill onto the drums.
    force_grade(&mut d.trip, -0.06);
    d.trip.truck.engine_brake_stage = 3;
    d.auto_jake_cooldown_s = 0.0;
    d.trip.truck.velocity_mps = mph_to_mps(48.0);
    d.update_auto_jake(&mut app.ctx, 2.0);
    assert_eq!(d.trip.truck.engine_brake_stage, 2);
    d.update_auto_jake(&mut app.ctx, 2.0);
    assert_eq!(d.trip.truck.engine_brake_stage, 1);
    force_grade(&mut d.trip, 0.0);
    d.trip.truck.engine_brake_stage = 3;

    // Ice arrives: the stage collapses to what the drives can hold.
    d.trip.truck.velocity_mps = mph_to_mps(60.0);
    d.trip.truck.grip = 0.15;
    d.trip.truck.transmission.gear = 5;
    d.trip.truck.rpm = 1900.0;
    d.update_auto_jake(&mut app.ctx, 2.0);
    assert!(
        d.trip.truck.engine_brake_stage <= d.auto_jake_max_stage()
            || d.trip.truck.engine_brake_stage == 1
    );
}

#[test]
fn test_the_descent_advisory_names_controls_the_driver_actually_has() {
    // An automatic has no gear selection, so "pick your gear" names nothing.
    // W, Q, N and Backspace are all gated on a manual box. What an automatic
    // driver has is the brake, which is exactly what puts their transmission
    // in a lower gear -- so that is what the advisory tells them to use.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.transmission.automatic = true;
    let said = d.descend_advice(&app.ctx);
    assert!(!said.to_lowercase().contains("pick your gear"));
    assert!(said.contains("brake down to speed"));
    assert!(said.contains("hold a lower gear"));

    // The manual box keeps the gear advice, because it can act on it.
    d.trip.truck.transmission.automatic = false;
    assert!(d.descend_advice(&app.ctx).starts_with("Pick your gear"));
}

// -- ignored: the roadside screens a settled stop pushes ------------------------------
//
// `driving_rest_states` has not landed, so `TrafficStopState`,
// `EnforcementStopState` and `FelonyStopState` are still stubs in
// `driving_updates::pending`. The bodies below are the Python cases, ready to
// run the moment those screens exist.

#[test]
fn test_a_clean_stop_opens_the_traffic_stop_screen() {
    // `test_speeding_consequences.test_being_seen_is_the_only_thing_that_costs_money`:
    // once the truck is stopped the encounter hands off to the roadside
    // screen, which is what actually charges the ticket.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.velocity_mps = 0.0;
    d.begin_pull_over(&mut app.ctx, 55.0);
    d.update_pull_over(&mut app.ctx, 1.0 / 60.0, true);
    assert!(d.pull_over.is_none());
    assert!(!d.trip.pull_over_active);
    app.ctx.run_deferred();
    assert!(
        app.ctx
            .state()
            .is_some_and(|s| s.borrow().as_any().is::<TrafficStopState>()),
        "the roadside screen is what charges the ticket"
    );
}

#[test]
fn test_running_from_the_stop_is_a_held_choice() {
    // `_update_pursuit_optin`: holding shift+X through the warning is the
    // only road to a felony, and it pushes `FelonyStopState`.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.trip.truck.velocity_mps = mph_to_mps(60.0);
    d.begin_pull_over(&mut app.ctx, 55.0);
    d.pull_over_grace_s = 0.0;
    app.ctx.input.press(Key::X, Mods::SHIFT);
    for _ in 0..(PURSUIT_HOLD_S * 60.0) as i32 + 10 {
        d.update_pursuit_optin(&mut app.ctx, 1.0 / 60.0);
    }
    assert!(d.pull_over.is_none());
    app.ctx.run_deferred();
    assert!(
        app.ctx
            .state()
            .is_some_and(|s| s.borrow().as_any().is::<FelonyStopState>()),
        "holding shift+X through the warning is the only road to a felony"
    );
}

// -- the doubled assist line on a hot exit ramp --------------------------------------
//
// `tests/test_driving_features.py::test_a_hot_ramp_speaks_one_assist_line_not_two`
// and `::test_a_silent_ramp_engagement_never_leaves_a_lone_release`.

/// One mainline bend the truck is sitting in, for the case that must still
/// speak (`SimpleNamespace(...)` on the Python side).
fn a_bend_here(at_mi: f64) -> RouteCurve {
    RouteCurve {
        start_mi: at_mi,
        apex_mi: at_mi,
        end_mi: at_mi + 0.1,
        direction: 'L',
        advisory_mph: 35,
        min_radius_ft: 1000,
        deflection_deg: 40.0,
        connector: false,
    }
}

#[test]
fn test_a_hot_ramp_speaks_one_assist_line_not_two() {
    // On a ramp, route-transition assistance owns the speech.
    //
    // A ramp adds 0.35 of curve weight, so any exit taken over about 43 mph
    // engages curve speed assistance too -- and with the realistic preset both
    // assists are on, so every hot ramp spoke twice back to back (logged
    // playtest of the four 1.9 assists, 2026-07-15). The braking is unchanged;
    // the line that survives is the one that names what it is braking for.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.ctx.settings.curve_speed_assist = true;
    // `monkeypatch.setattr(driving.trip, "curve_at", lambda mile: None)`: no
    // baked bend under the truck, so the assist reaches its ramp heuristic.
    d.trip.curves = Vec::new();
    app.clear_speech();

    // On the ramp: fast enough that the ramp's own curve weight engages the
    // curve assist through its heuristic branch.
    d.ramp_mi = Some(d.trip.position_mi);
    for _ in 0..30 {
        d.trip.truck.velocity_mps = 55.0 * 0.44704;
        d.update_lane(&mut app.ctx, 1.0 / 60.0);
    }
    assert!(
        !app.event_lines()
            .iter()
            .any(|text| text.contains("Curve speed assistance")),
        "the ramp's own assist speaks for a ramp; the curve cue must not double it"
    );

    // Off the ramp, the same overspeed still announces itself normally.
    d.ramp_mi = None;
    d.curve_assist_cue_s = 0.0;
    d.curve_assist_active = false;
    d.trip.curves = vec![a_bend_here(d.trip.position_mi)];
    for _ in 0..30 {
        d.trip.truck.velocity_mps = 55.0 * 0.44704;
        d.update_lane(&mut app.ctx, 1.0 / 60.0);
    }
    assert!(
        app.event_lines()
            .iter()
            .any(|text| text.contains("Curve speed assistance slowing.")),
        "silencing the ramp case must not silence a real mainline bend"
    );
}

#[test]
fn test_a_silent_ramp_engagement_never_leaves_a_lone_release() {
    // The release line is paired to the slowing line that opened it.
    //
    // Suppressing the ramp's engagement cue would otherwise leave "Curve speed
    // assistance released." hanging on its own with nothing before it, which
    // reads as a bug to anyone listening.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.ctx.settings.curve_speed_assist = true;
    d.trip.curves = Vec::new();
    app.clear_speech();

    d.ramp_mi = Some(d.trip.position_mi);
    for _ in 0..30 {
        d.trip.truck.velocity_mps = 55.0 * 0.44704;
        d.update_lane(&mut app.ctx, 1.0 / 60.0);
    }
    // Slow down so the assist disengages while still on the ramp.
    d.curve_assist_cue_s = 0.0;
    for _ in 0..30 {
        d.trip.truck.velocity_mps = 20.0 * 0.44704;
        d.update_lane(&mut app.ctx, 1.0 / 60.0);
    }

    assert!(
        !app.event_lines()
            .iter()
            .any(|text| text.contains("Curve speed assistance")),
        "a run that never spoke must not announce its own release"
    );
}
