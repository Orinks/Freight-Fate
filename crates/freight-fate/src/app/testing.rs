//! Shared rigging for tests that build a headless [`App`]: the conftest of
//! the Python suite in one place, so every later state port reuses it.
//!
//! * [`env_lock`] serialises the process-global environment
//!   (`FREIGHT_FATE_DATA_DIR` above all) -- hold the guard for the life of
//!   the app, since `shutdown` writes settings into that directory.
//! * [`TestApp`] is `App()` under the conftest fixtures: headless drivers,
//!   an isolated data directory, the first-run online offer already seen,
//!   a `CaptureSpeech` in place of Prism, the null audio backend.
//! * [`RecordingAudio`] is the `monkeypatch.setattr(app.ctx.audio, "play",
//!   ...)` seam: an `Audio` that records `play` and `set_speech_duck`.

use std::cell::RefCell;
use std::rc::Rc;
use std::sync::{Mutex, MutexGuard};

use ff_core::settings::Settings;
use ff_core::speech_pacing::EventSpeechPacer;

use crate::audio::{Audio, AudioError, SustainLoopSpec, VolumeUpdate};
use crate::speech::{CaptureSpeech, SpeechSink};

use super::App;

static ENV_LOCK: Mutex<()> = Mutex::new(());
static DIR_COUNTER: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);

/// A fresh directory under the system temp dir, removed on drop (the
/// pytest `tmp_path`).
pub struct TempDir {
    path: std::path::PathBuf,
}

impl TempDir {
    pub fn new(prefix: &str) -> TempDir {
        let n = DIR_COUNTER.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        let path = std::env::temp_dir().join(format!(
            "{prefix}-{}-{n}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_nanos())
                .unwrap_or(0)
        ));
        std::fs::create_dir_all(&path).expect("a temp data dir");
        TempDir { path }
    }

    pub fn path(&self) -> &std::path::Path {
        &self.path
    }
}

impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.path);
    }
}

/// Take the environment lock (poison-tolerant: a failed test must not take
/// the rest of the file down with it).
pub fn env_lock() -> MutexGuard<'static, ()> {
    ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner())
}

/// The headless environment the Python conftest forced for every test.
pub fn set_headless_env() {
    std::env::set_var("SDL_VIDEODRIVER", "dummy");
    std::env::set_var("SDL_AUDIODRIVER", "dummy");
    std::env::set_var("FREIGHT_FATE_NO_SPEECH", "1");
}

/// A headless app over an isolated data directory, holding the environment
/// lock until dropped.
pub struct TestApp {
    pub app: App,
    pub data_dir: TempDir,
    capture: Rc<RefCell<CaptureSpeech>>,
    _guard: MutexGuard<'static, ()>,
}

impl std::ops::Deref for TestApp {
    type Target = App;
    fn deref(&self) -> &App {
        &self.app
    }
}

impl std::ops::DerefMut for TestApp {
    fn deref_mut(&mut self) -> &mut App {
        &mut self.app
    }
}

impl TestApp {
    /// `App()` under the conftest fixtures, speech captured.
    pub fn new() -> TestApp {
        Self::with_speech(CaptureSpeech::new())
    }

    /// `App()` with a particular capture (e.g. `CaptureSpeech::full_voice()`
    /// for a machine with a separate event voice).
    pub fn with_speech(speech: CaptureSpeech) -> TestApp {
        let guard = env_lock();
        set_headless_env();
        let data_dir = TempDir::new("ff-rust-app");
        std::env::set_var("FREIGHT_FATE_DATA_DIR", data_dir.path().join("data"));
        // Seed the one-time first-run orinks.net offer as already spent, so a
        // test that is not about the offer can drive a career through the
        // app without knowing it exists.
        let settings = Settings {
            online_offer_seen: true,
            ..Default::default()
        };
        let _ = settings.save();
        let capture = Rc::new(RefCell::new(speech));
        let app = App::new_headless(Box::new(SharedCapture(Rc::clone(&capture))));
        TestApp {
            app,
            data_dir,
            capture,
            _guard: guard,
        }
    }

    /// The capture behind `ctx.speech`.
    pub fn speech(&self) -> std::cell::Ref<'_, CaptureSpeech> {
        self.capture.borrow()
    }

    pub fn speech_mut(&self) -> std::cell::RefMut<'_, CaptureSpeech> {
        self.capture.borrow_mut()
    }

    /// Drop everything said so far.
    pub fn clear_speech(&self) {
        self.capture.borrow_mut().clear();
    }

    /// Main-channel `(text, interrupt)` calls since the last clear.
    pub fn main_calls(&self) -> Vec<(String, bool)> {
        self.speech().calls(crate::speech::SpeechChannel::Main)
    }

    /// Event-channel `(text, interrupt)` calls since the last clear.
    pub fn event_calls(&self) -> Vec<(String, bool)> {
        self.speech().calls(crate::speech::SpeechChannel::Event)
    }

    /// Main-channel texts since the last clear.
    pub fn main_lines(&self) -> Vec<String> {
        self.speech().main_lines()
    }

    /// Event-channel texts since the last clear.
    pub fn event_lines(&self) -> Vec<String> {
        self.speech().event_lines()
    }

    /// Replace `ctx.audio` with a [`RecordingAudio`] and hand back its log.
    pub fn record_audio(&mut self) -> AudioLog {
        let audio = RecordingAudio::new();
        let log = audio.log();
        self.app.ctx.audio = Box::new(audio);
        log
    }

    /// Replace the event pacer with one on a [`FakeClock`] (`app.ctx._event_pacer
    /// = EventSpeechPacer(clock=clock)`).
    pub fn fake_pacer_clock(&mut self) -> FakeClock {
        let clock = FakeClock::new(100.0);
        self.app.ctx.event_pacer = EventSpeechPacer::with_clock(clock.boxed());
        clock
    }

    /// Shut the app down (also runs on drop).
    pub fn shutdown(&mut self) {
        self.app.shutdown();
    }
}

impl Default for TestApp {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for TestApp {
    fn drop(&mut self) {
        self.app.shutdown();
    }
}

/// A `SpeechSink` over a shared `CaptureSpeech`, so the test keeps a handle
/// to read what the app said while the app owns the sink.
pub struct SharedCapture(pub Rc<RefCell<CaptureSpeech>>);

impl SpeechSink for SharedCapture {
    fn say(&mut self, text: &str, interrupt: bool) {
        self.0.borrow_mut().say(text, interrupt)
    }
    fn say_event(&mut self, text: &str, interrupt: bool) {
        self.0.borrow_mut().say_event(text, interrupt)
    }
    fn stop_main(&mut self) {
        self.0.borrow_mut().stop_main()
    }
    fn stop_event(&mut self) {
        self.0.borrow_mut().stop_event()
    }
    fn stop(&mut self) {
        self.0.borrow_mut().stop()
    }
    fn poll(&mut self, dt: f64) {
        self.0.borrow_mut().poll(dt)
    }
    fn request_refresh(&mut self) {
        self.0.borrow_mut().request_refresh()
    }
    fn available(&self) -> bool {
        self.0.borrow().available()
    }
    fn backend_name(&self) -> String {
        self.0.borrow().backend_name()
    }
    fn has_separate_event_voice(&self) -> bool {
        self.0.borrow().has_separate_event_voice()
    }
    fn event_backend_name(&self) -> String {
        self.0.borrow().event_backend_name()
    }
    fn supports_rate(&self) -> bool {
        self.0.borrow().supports_rate()
    }
    fn supports_pitch(&self) -> bool {
        self.0.borrow().supports_pitch()
    }
    fn supports_volume(&self) -> bool {
        self.0.borrow().supports_volume()
    }
    fn event_supports_rate(&self) -> bool {
        self.0.borrow().event_supports_rate()
    }
    fn event_backend_options(&self) -> Vec<String> {
        self.0.borrow().event_backend_options()
    }
    fn select_event_backend(&mut self, name: Option<&str>) {
        self.0.borrow_mut().select_event_backend(name)
    }
    fn voice_names(&self) -> Vec<String> {
        self.0.borrow().voice_names()
    }
    fn configure(
        &mut self,
        rate: Option<f64>,
        pitch: Option<f64>,
        volume: Option<f64>,
        voice: Option<&str>,
    ) {
        self.0.borrow_mut().configure(rate, pitch, volume, voice)
    }
    fn say_adjustment_preview(&mut self, setting: &str, text: &str, interrupt: bool) -> bool {
        self.0
            .borrow_mut()
            .say_adjustment_preview(setting, text, interrupt)
    }
    fn refresh(&mut self, announce: bool) -> bool {
        self.0.borrow_mut().refresh(announce)
    }
    fn shutdown(&mut self) {
        self.0.borrow_mut().shutdown()
    }
}

/// A controllable clock for the pacer (`FakeClock` in the Python tests).
#[derive(Clone)]
pub struct FakeClock {
    now: Rc<RefCell<f64>>,
}

impl FakeClock {
    pub fn new(now: f64) -> Self {
        Self {
            now: Rc::new(RefCell::new(now)),
        }
    }

    pub fn now(&self) -> f64 {
        *self.now.borrow()
    }

    pub fn set(&self, now: f64) {
        *self.now.borrow_mut() = now;
    }

    pub fn advance(&self, seconds: f64) {
        *self.now.borrow_mut() += seconds;
    }

    /// The clock as the pacer takes it.
    pub fn boxed(&self) -> ff_core::speech_pacing::Clock {
        let now = Rc::clone(&self.now);
        Box::new(move || *now.borrow())
    }
}

/// A clock that jumps `step` seconds every time it is read (the Python
/// `_stepping_clock`), so a test can assert what the RUNG did with an
/// identical line without the pacer's repeat window deciding it.
pub fn stepping_clock(step: f64) -> ff_core::speech_pacing::Clock {
    let mut now = 0.0;
    Box::new(move || {
        now += step;
        now
    })
}

/// What a [`RecordingAudio`] was asked to do.
#[derive(Debug, Default)]
pub struct AudioCalls {
    /// `play(key, volume, pan)` in order.
    pub played: Vec<(String, f64, f64)>,
    /// `set_speech_duck(level)` in order.
    pub ducks: Vec<f64>,
    pub music: Vec<(String, u32)>,
}

pub type AudioLog = Rc<RefCell<AudioCalls>>;

/// An `Audio` that records the calls the app-shell tests watch and ignores
/// the rest.
#[derive(Default)]
pub struct RecordingAudio {
    log: AudioLog,
}

impl RecordingAudio {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn log(&self) -> AudioLog {
        Rc::clone(&self.log)
    }
}

impl Audio for RecordingAudio {
    fn enabled(&self) -> bool {
        false
    }
    fn backend_name(&self) -> &str {
        "recording"
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
        false
    }
    fn engine_starting(&self) -> bool {
        false
    }
    fn voice_key(&self, key: &str) -> String {
        key.to_string()
    }
    fn play_with(&mut self, key: &str, volume: f64, pan: f64) {
        self.log
            .borrow_mut()
            .played
            .push((key.to_string(), volume, pan));
    }
    fn play_bank_with(&mut self, base: &str, _fallback: &str, volume: f64, pan: f64) {
        self.play_with(base, volume, pan);
    }
    fn set_engine_duck(&mut self, _duck: f64) {}
    fn set_speech_duck(&mut self, duck: f64) {
        self.log.borrow_mut().ducks.push(duck);
    }
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
    fn engine_start_with(&mut self, _play_start_sound: bool) {}
    fn engine_stop_with(&mut self, _shutdown_sound: bool) {}
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
        self.log
            .borrow_mut()
            .music
            .push((track.to_string(), fade_ms));
    }
    fn play_radio_stream_with(&mut self, _url: &str, _fade_ms: u32) -> Result<(), AudioError> {
        Ok(())
    }
    fn play_music_file_with(&mut self, _path: &str, _fade_ms: u32) -> Result<(), AudioError> {
        Ok(())
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
