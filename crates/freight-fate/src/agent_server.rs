//! `--agent-server`: an MCP server inside the real game, so an AI agent can
//! play Freight Fate the way a player does -- keys in, ears out.
//!
//! This is deliberately NOT built on the headless playtest harness. The
//! harness runs the game's own states, but not the game's own runtime: it
//! fakes the pacer clock, records audio instead of running BASS, captures
//! speech instead of speaking, and never executes the real startup path --
//! which is exactly where bugs like the deaf-for-sixteen-seconds menu live.
//! Here the agent connects to the game itself: the real window loop, real
//! wall-clock time, real audio engine, real speech through Prism (audible on
//! the operator's screen reader, so you can listen to your agent play), and
//! the real menus from the title screen on. Nothing is staged for it; it
//! presses New career like anyone else.
//!
//! The agent's capabilities are a player's, enforced by the same seam the
//! autonomous road observer uses: inputs go through
//! [`PlayerInputFrame::queue_player_input`], which "cannot bypass input
//! dispatch or drive physics", and observation is what came out of the
//! speakers -- both channels of speech, plus every earcon, cue, loop, and
//! engine pitch move, because quiet mode exists precisely so that sound
//! carries what speech does not. One inspector tool (`observe`) exposes the
//! same bounded [`DrivingObservation`] snapshot the observer gets, labeled
//! as ground truth rather than ears: an agent that NEEDS it to drive has
//! found an accessibility gap, and that is a finding.
//!
//! The session always runs in the playtest sandbox (prepared and audited by
//! the same code as `--playtest-sandbox`), so an agent can never touch the
//! operator's real careers, settings, or keyring. `SingleInstanceGuard`
//! still applies: one game at a time, agent or human.
//!
//! Transport: newline-delimited JSON-RPC 2.0 over stdio (the MCP stdio
//! transport). Stdout carries protocol messages only; everything else this
//! mode prints goes to stderr.
//!
//! The handshake needs no game. An MCP client spawns every server it knows
//! at startup just to ask for the tool list -- Claude Code does it for each
//! session in this repo -- and the first shipped server booted the real
//! game before it read a byte of stdin, so enabling it launched a game
//! window into every session and held the one-game-at-a-time lock against
//! the owner (found live, 2026-09-01). Now `initialize`, `tools/list` and
//! `ping` are answered from the serve thread alone; the sandbox, the lock,
//! the window, audio and speech all wait for the first play request, and a
//! client that hangs up takes the game down with it.

use std::cell::RefCell;
use std::collections::HashMap;
use std::io::{BufRead, Write};
use std::rc::Rc;
use std::sync::mpsc;

use serde_json::{json, Map, Value};

use crate::app::{App, PlayerInputFrame};
use crate::audio::{Audio, AudioError, SustainLoopSpec, VolumeUpdate};
use crate::speech::SpeechSink;
use crate::states::base::{InputEvent, Key, Mods};

const SERVER_NAME: &str = "freight-fate-agent";
const PROTOCOL_VERSION: &str = "2025-06-18";
/// One `wait` may hold the wheel for at most this much real time.
const MAX_WAIT_SECONDS: f64 = 300.0;
/// Sound lines per `listen` before the rest are summarized.
const MAX_SOUND_LINES: usize = 150;
/// A tool call must be answered by the game loop within this budget.
const REPLY_TIMEOUT_SECONDS: u64 = 330;

// -- ears -----------------------------------------------------------------------------

/// Everything audible, formatted at record time, drained by `listen`.
#[derive(Default)]
pub struct Ears {
    lines: Vec<String>,
    /// Engine pitch is set every frame; an ear notices where it went, not
    /// sixty samples a second of it. Cleared at each listen.
    engine_rpm: Vec<f64>,
    road_noise_mps: Option<f64>,
    /// The alert currently held, so a per-frame re-assert is heard once.
    held_alert: Option<String>,
}

pub type SharedEars = Rc<RefCell<Ears>>;

impl Ears {
    pub fn shared() -> SharedEars {
        Rc::new(RefCell::new(Ears::default()))
    }
}

fn pan_text(pan: f64) -> &'static str {
    if pan < -0.15 {
        " (left)"
    } else if pan > 0.15 {
        " (right)"
    } else {
        ""
    }
}

// -- the speech tee -------------------------------------------------------------------

/// Passes every call to the real sink (the words still reach the screen
/// reader) while recording what was said.
struct TeeSpeech {
    inner: Box<dyn SpeechSink>,
    ears: SharedEars,
}

impl SpeechSink for TeeSpeech {
    fn say(&mut self, text: &str, interrupt: bool) {
        let cut = if interrupt { " (interrupting)" } else { "" };
        self.ears
            .borrow_mut()
            .lines
            .push(format!("[spoken]{cut} {text}"));
        self.inner.say(text, interrupt);
    }
    fn say_event(&mut self, text: &str, interrupt: bool) {
        let cut = if interrupt { " (interrupting)" } else { "" };
        self.ears
            .borrow_mut()
            .lines
            .push(format!("[spoken:event]{cut} {text}"));
        self.inner.say_event(text, interrupt);
    }
    fn stop_main(&mut self) {
        self.inner.stop_main();
    }
    fn stop_event(&mut self) {
        self.inner.stop_event();
    }
    fn stop(&mut self) {
        self.inner.stop();
    }
    fn poll(&mut self, dt: f64) {
        self.inner.poll(dt);
    }
    fn request_refresh(&mut self) {
        self.inner.request_refresh();
    }
    fn available(&self) -> bool {
        self.inner.available()
    }
    fn backend_name(&self) -> String {
        self.inner.backend_name()
    }
    fn has_separate_event_voice(&self) -> bool {
        self.inner.has_separate_event_voice()
    }
    fn event_backend_name(&self) -> String {
        self.inner.event_backend_name()
    }
    fn supports_rate(&self) -> bool {
        self.inner.supports_rate()
    }
    fn supports_pitch(&self) -> bool {
        self.inner.supports_pitch()
    }
    fn supports_volume(&self) -> bool {
        self.inner.supports_volume()
    }
    fn event_supports_rate(&self) -> bool {
        self.inner.event_supports_rate()
    }
    fn event_backend_options(&self) -> Vec<String> {
        self.inner.event_backend_options()
    }
    fn select_event_backend(&mut self, name: Option<&str>) {
        self.inner.select_event_backend(name);
    }
    fn voice_names(&self) -> Vec<String> {
        self.inner.voice_names()
    }
    fn configure(
        &mut self,
        rate: Option<f64>,
        pitch: Option<f64>,
        volume: Option<f64>,
        voice: Option<&str>,
    ) {
        self.inner.configure(rate, pitch, volume, voice);
    }
    fn say_adjustment_preview(&mut self, setting: &str, text: &str, interrupt: bool) -> bool {
        self.inner.say_adjustment_preview(setting, text, interrupt)
    }
    fn refresh(&mut self, announce: bool) -> bool {
        self.inner.refresh(announce)
    }
    fn shutdown(&mut self) {
        self.inner.shutdown();
    }
}

// -- the audio tee --------------------------------------------------------------------

/// Passes every call to the real engine (the sounds still play) while
/// recording the audible facts an agent's ears should carry.
struct TeeAudio {
    inner: Box<dyn Audio>,
    ears: SharedEars,
    weather_key: Option<String>,
    ambient_key: Option<String>,
    loop_keys: HashMap<u32, String>,
}

impl TeeAudio {
    fn hear(&self, line: String) {
        self.ears.borrow_mut().lines.push(line);
    }
}

impl Audio for TeeAudio {
    fn enabled(&self) -> bool {
        self.inner.enabled()
    }
    fn backend_name(&self) -> &str {
        self.inner.backend_name()
    }
    fn take_silence_notice(&mut self) -> bool {
        self.inner.take_silence_notice()
    }
    fn master_volume(&self) -> f64 {
        self.inner.master_volume()
    }
    fn sfx_volume(&self) -> f64 {
        self.inner.sfx_volume()
    }
    fn music_volume(&self) -> f64 {
        self.inner.music_volume()
    }
    fn weather_volume(&self) -> f64 {
        self.inner.weather_volume()
    }
    fn engine_volume(&self) -> f64 {
        self.inner.engine_volume()
    }
    fn ui_volume(&self) -> f64 {
        self.inner.ui_volume()
    }
    fn engine_running(&self) -> bool {
        self.inner.engine_running()
    }
    fn engine_starting(&self) -> bool {
        self.inner.engine_starting()
    }
    fn voice_key(&self, key: &str) -> String {
        self.inner.voice_key(key)
    }
    fn play_with(&mut self, key: &str, volume: f64, pan: f64) {
        let soft = if volume < 0.4 { ", soft" } else { "" };
        self.hear(format!("[sound] {key}{}{soft}", pan_text(pan)));
        self.inner.play_with(key, volume, pan);
    }
    fn play_bank_with(&mut self, base: &str, fallback: &str, volume: f64, pan: f64) {
        let soft = if volume < 0.4 { ", soft" } else { "" };
        self.hear(format!("[sound] {base}{}{soft}", pan_text(pan)));
        self.inner.play_bank_with(base, fallback, volume, pan);
    }
    fn set_engine_duck(&mut self, duck: f64) {
        self.inner.set_engine_duck(duck);
    }
    fn set_speech_duck(&mut self, duck: f64) {
        self.inner.set_speech_duck(duck);
    }
    fn set_engine_voice(&mut self, classic: bool) {
        self.inner.set_engine_voice(classic);
    }
    fn set_jake_voice(&mut self, classic: bool) {
        self.inner.set_jake_voice(classic);
    }
    fn has_asset(&mut self, key: &str) -> bool {
        self.inner.has_asset(key)
    }
    fn start_loop_with(&mut self, channel: u32, key: &str, volume: f64, fade_ms: u32) {
        if self.loop_keys.get(&channel).map(String::as_str) != Some(key) {
            self.hear(format!("[sound bed] {key} starts"));
            self.loop_keys.insert(channel, key.to_string());
        }
        self.inner.start_loop_with(channel, key, volume, fade_ms);
    }
    fn set_loop_volume(&mut self, channel: u32, volume: f64) {
        self.inner.set_loop_volume(channel, volume);
    }
    fn set_loop_pan(&mut self, channel: u32, pan: f64) {
        self.inner.set_loop_pan(channel, pan);
    }
    fn stop_loop_with(&mut self, channel: u32, fade_ms: u32) {
        self.loop_keys.remove(&channel);
        self.inner.stop_loop_with(channel, fade_ms);
    }
    fn start_sustain_loop_with(
        &mut self,
        channel: u32,
        key: &str,
        spec: SustainLoopSpec,
        volume: f64,
    ) {
        if self.loop_keys.get(&channel).map(String::as_str) != Some(key) {
            self.hear(format!("[sound bed] {key} starts"));
            self.loop_keys.insert(channel, key.to_string());
        }
        self.inner
            .start_sustain_loop_with(channel, key, spec, volume);
    }
    fn release_sustain_loop_with(&mut self, channel: u32, fade_ms: u32) {
        self.loop_keys.remove(&channel);
        self.inner.release_sustain_loop_with(channel, fade_ms);
    }
    fn hold_alert_with(&mut self, key: &str, volume: f64, fade_ms: u32) {
        // Re-asserted every frame while it holds; an ear hears it start
        // once (a ramp-end stop flooded a listen with a hundred of these).
        let fresh = self.ears.borrow().held_alert.as_deref() != Some(key);
        if fresh {
            self.ears.borrow_mut().held_alert = Some(key.to_string());
            self.hear(format!("[alert] {key} holds"));
        }
        self.inner.hold_alert_with(key, volume, fade_ms);
    }
    fn release_alert_with(&mut self, fade_ms: u32) {
        self.ears.borrow_mut().held_alert = None;
        self.hear("[alert] released".to_string());
        self.inner.release_alert_with(fade_ms);
    }
    fn hold_cue(&mut self, name: &str) {
        self.hear(format!("[cue] {name} holds"));
        self.inner.hold_cue(name);
    }
    fn cue_held(&self, name: &str) -> bool {
        self.inner.cue_held(name)
    }
    fn release_cue(&mut self, name: &str) {
        self.hear(format!("[cue] {name} released"));
        self.inner.release_cue(name);
    }
    fn engine_start_with(&mut self, play_start_sound: bool) {
        // A silent start is the loop coming back after a menu or a resumed
        // trip: no crank plays, so the ear must not report one -- every
        // unpause read as an engine start (agent drive, 2026-09-01).
        if play_start_sound {
            self.hear("[engine] starting".to_string());
        } else {
            self.hear("[engine] running again, no crank".to_string());
        }
        self.inner.engine_start_with(play_start_sound);
    }
    fn engine_stop_with(&mut self, shutdown_sound: bool) {
        self.hear("[engine] shut down".to_string());
        self.inner.engine_stop_with(shutdown_sound);
    }
    fn update(&mut self, dt: f64) {
        self.inner.update(dt);
    }
    fn set_engine_rpm_with(&mut self, rpm: f64, throttle: f64) {
        self.ears.borrow_mut().engine_rpm.push(rpm);
        self.inner.set_engine_rpm_with(rpm, throttle);
    }
    fn set_road_noise(&mut self, speed_mps: f64) {
        self.ears.borrow_mut().road_noise_mps = Some(speed_mps);
        self.inner.set_road_noise(speed_mps);
    }
    fn set_weather_with(&mut self, key: Option<&str>, intensity: f64) {
        let audible_key = key.filter(|_| intensity > 0.0);
        if audible_key != self.weather_key.as_deref() {
            match audible_key {
                Some(key) => self.hear(format!("[weather] {key}")),
                None => self.hear("[weather] stopped".to_string()),
            }
            self.weather_key = audible_key.map(str::to_string);
        }
        self.inner.set_weather_with(key, intensity);
    }
    fn set_wind(&mut self, intensity: f64) {
        self.inner.set_wind(intensity);
    }
    fn set_ambient_with(&mut self, key: Option<&str>, volume: f64) {
        let audible_key = key.filter(|_| volume > 0.0);
        if audible_key != self.ambient_key.as_deref() {
            match audible_key {
                Some(key) => self.hear(format!("[ambience] {key}")),
                None => self.hear("[ambience] stopped".to_string()),
            }
            self.ambient_key = audible_key.map(str::to_string);
        }
        self.inner.set_ambient_with(key, volume);
    }
    fn horn_start(&mut self) {
        self.hear("[horn] on".to_string());
        self.inner.horn_start();
    }
    fn horn_stop(&mut self) {
        self.hear("[horn] off".to_string());
        self.inner.horn_stop();
    }
    fn reverse_start(&mut self) {
        self.hear("[reverse beeper] on".to_string());
        self.inner.reverse_start();
    }
    fn reverse_stop(&mut self) {
        self.hear("[reverse beeper] off".to_string());
        self.inner.reverse_stop();
    }
    fn stop_world(&mut self) {
        // The engine loop drops silently with the rest of the road (a pause,
        // an arrival) and comes back silently; say so, or the return reads
        // as a start out of nowhere.
        if self.inner.engine_running() {
            self.hear("[engine] quiet while the road is paused".to_string());
        }
        if self.weather_key.take().is_some() {
            self.hear("[weather] stopped".to_string());
        }
        if self.ambient_key.take().is_some() {
            self.hear("[ambience] stopped".to_string());
        }
        self.loop_keys.clear();
        self.inner.stop_world();
    }
    fn play_music_with(&mut self, track: &str, fade_ms: u32) {
        self.hear(format!("[radio] now playing {track}"));
        self.inner.play_music_with(track, fade_ms);
    }
    fn play_radio_stream_with(&mut self, url: &str, fade_ms: u32) -> Result<(), AudioError> {
        self.hear("[radio] live stream tuning".to_string());
        self.inner.play_radio_stream_with(url, fade_ms)
    }
    fn play_music_file_with(&mut self, path: &str, fade_ms: u32) -> Result<(), AudioError> {
        self.inner.play_music_file_with(path, fade_ms)
    }
    fn music_playing(&self) -> bool {
        self.inner.music_playing()
    }
    fn radio_now_playing(&self) -> Option<String> {
        self.inner.radio_now_playing()
    }
    fn stop_music_with(&mut self, fade_ms: u32) {
        self.inner.stop_music_with(fade_ms);
    }
    fn set_volumes(&mut self, volumes: &VolumeUpdate) {
        self.inner.set_volumes(volumes);
    }
    fn shutdown(&mut self) {
        self.inner.shutdown();
    }
}

/// Wrap the app's live speech and audio in recording tees.
pub fn install_ears(app: &mut App) -> SharedEars {
    use crate::audio::{AudioEngine, NullBackend};
    let ears = Ears::shared();
    let speech = std::mem::replace(&mut app.ctx.speech, Box::new(crate::speech::NullSpeech));
    app.ctx.speech = Box::new(TeeSpeech {
        inner: speech,
        ears: Rc::clone(&ears),
    });
    let audio = std::mem::replace(
        &mut app.ctx.audio,
        Box::new(AudioEngine::with_backend(Box::new(NullBackend::new()))),
    );
    app.ctx.audio = Box::new(TeeAudio {
        inner: audio,
        ears: Rc::clone(&ears),
        weather_key: None,
        ambient_key: None,
        loop_keys: HashMap::new(),
    });
    ears
}

fn drain_ears(ears: &SharedEars) -> String {
    let mut e = ears.borrow_mut();
    let mut lines: Vec<String> = Vec::new();
    let shown = e.lines.len().min(MAX_SOUND_LINES.max(64));
    lines.extend(e.lines.drain(..).take(shown));
    if let (Some(first), Some(last)) = (e.engine_rpm.first(), e.engine_rpm.last()) {
        let low = e.engine_rpm.iter().cloned().fold(f64::MAX, f64::min);
        let high = e.engine_rpm.iter().cloned().fold(0.0_f64, f64::max);
        if (high - low).abs() > 25.0 {
            lines.push(format!(
                "[engine] {first:.0} rpm -> {last:.0} rpm (ranged {low:.0} to {high:.0})"
            ));
        }
    }
    e.engine_rpm.clear();
    if let Some(mps) = e.road_noise_mps.take() {
        if mps > 1.0 {
            lines.push(format!(
                "[road] rolling at about {:.0} miles per hour by ear",
                mps * 2.236_936
            ));
        }
    }
    if lines.is_empty() {
        "(quiet -- nothing new to hear)".to_string()
    } else {
        lines.join("\n")
    }
}

// -- commands between the MCP thread and the game loop --------------------------------

pub enum Command {
    Press {
        key: Key,
        text: Option<char>,
        mods: Mods,
        times: i64,
    },
    Hold {
        key: Key,
        text: Option<char>,
    },
    Release {
        key: Key,
    },
    Wait {
        seconds: f64,
    },
    Listen,
    Menu,
    Observe,
    /// The hit is discovered on the serve thread (world data only) so the
    /// game loop never blocks on a search; the loop only builds the drive.
    StageHit {
        hit: Box<crate::playtest::road::Hit>,
        opts: Box<crate::playtest::road::RoadOptions>,
        found: usize,
        picked: usize,
    },
    Quit,
}

pub struct Request {
    command: Command,
    reply: mpsc::Sender<Result<String, String>>,
}

impl Request {
    pub fn command(&self) -> &Command {
        &self.command
    }

    /// Answer the tool call this request carries.
    pub fn answer(self, result: Result<String, String>) {
        let _ = self.reply.send(result);
    }
}

/// Block until the client asks for something only a running game can do,
/// answering what needs no game on the way (a quit with nothing to quit).
/// `None` when the client hangs up first: the handshake alone never boots a
/// game, so a session that only asked for the tool list ends here, quietly.
pub fn await_play_request(requests: &mpsc::Receiver<Request>) -> Option<Request> {
    loop {
        let request = requests.recv().ok()?;
        match request.command {
            Command::Quit => request.answer(Ok(
                "The game is not running; nothing to quit. Any other tool call boots it."
                    .to_string(),
            )),
            _ => return Some(request),
        }
    }
}

/// The per-frame policy servicing agent commands inside the real game loop.
pub struct AgentPolicy {
    requests: mpsc::Receiver<Request>,
    /// The request that woke the game, served on the first frame.
    pending: Option<Request>,
    ears: SharedEars,
    waiting: Option<(f64, mpsc::Sender<Result<String, String>>)>,
    /// Keys the agent is holding. Re-asserted every frame, because the
    /// focus-lost safety wipe (built for real keyboards) otherwise drops
    /// them whenever the operator's screen reader moves window focus --
    /// which on a working desktop is constantly. Found live: the agent's
    /// first throttle hold worked (window still focused from launch) and
    /// every later one silently died.
    held: Vec<Key>,
    /// Key events scripted frame by frame, front first. A tap is two
    /// frames -- down, then up -- because the held-key tracker reads a
    /// press and release inside ONE frame as a screen reader's re-injected
    /// pair and holds the key for the repeat delay (half a second): a
    /// tapped brake became the reverse-selection hold and a tapped P
    /// toggled the parking brake against the approach assist (found live,
    /// 2026-09-01). No finger taps inside a frame, so the agent must not.
    scripted: std::collections::VecDeque<Vec<InputEvent>>,
    quit: bool,
}

impl AgentPolicy {
    fn next_request(&mut self) -> Result<Request, mpsc::TryRecvError> {
        match self.pending.take() {
            Some(request) => Ok(request),
            None => self.requests.try_recv(),
        }
    }

    /// One frame. Returns false to end the game loop.
    pub fn step(&mut self, input: &mut PlayerInputFrame<'_>, dt: f64) -> bool {
        if self.quit {
            return false;
        }
        for key in &self.held {
            input.assert_held(*key);
        }
        if let Some(frame) = self.scripted.pop_front() {
            for event in frame {
                input.queue_player_input(event);
            }
        }
        if let Some((remaining, reply)) = self.waiting.take() {
            let remaining = remaining - dt;
            if remaining > 0.0 {
                self.waiting = Some((remaining, reply));
                return true;
            }
            let _ = reply.send(Ok(drain_ears(&self.ears)));
        }
        loop {
            let request = match self.next_request() {
                Ok(request) => request,
                Err(mpsc::TryRecvError::Empty) => break,
                Err(mpsc::TryRecvError::Disconnected) => {
                    // The client hung up (stdin closed): nobody is left to
                    // play, and an idle game would hold the one-game-at-a-
                    // time lock against the operator until they found it.
                    eprintln!("The MCP client is gone; quitting the game.");
                    self.quit = true;
                    return false;
                }
            };
            let reply = request.reply;
            match request.command {
                Command::Press {
                    key,
                    text,
                    mods,
                    times,
                } => {
                    for _ in 0..times.clamp(1, 50) {
                        self.scripted
                            .push_back(vec![InputEvent::KeyDown { key, mods, text }]);
                        self.scripted
                            .push_back(vec![InputEvent::KeyUp { key, mods }]);
                    }
                    let _ = reply.send(Ok(
                        "pressed. Wait a moment (wait tool) then listen; the game \
                         speaks on its own time."
                            .to_string(),
                    ));
                }
                Command::Hold { key, text } => {
                    if !self.held.contains(&key) {
                        self.held.push(key);
                    }
                    input.queue_player_input(InputEvent::KeyDown {
                        key,
                        mods: Mods::NONE,
                        text,
                    });
                    let _ = reply.send(Ok("held down.".to_string()));
                }
                Command::Release { key } => {
                    self.held.retain(|held| *held != key);
                    input.queue_player_input(InputEvent::KeyUp {
                        key,
                        mods: Mods::NONE,
                    });
                    let _ = reply.send(Ok("released.".to_string()));
                }
                Command::Wait { seconds } => {
                    // Replied when the time has really passed; only one wait
                    // can be in flight because the MCP thread blocks on it.
                    self.waiting = Some((seconds.clamp(0.05, MAX_WAIT_SECONDS), reply));
                    break;
                }
                Command::Listen => {
                    let _ = reply.send(Ok(drain_ears(&self.ears)));
                }
                Command::Menu => {
                    let _ = reply.send(match input.menu_rows() {
                        Some((labels, focus)) => Ok(labels
                            .iter()
                            .enumerate()
                            .map(|(i, label)| {
                                let marker = if i == focus { " (focused)" } else { "" };
                                format!("{}. {label}{marker}", i + 1)
                            })
                            .collect::<Vec<_>>()
                            .join("\n")),
                        None => Err("No menu is on screen right now. If you are at the wheel, \
                             the driving keys and spoken readouts are the interface."
                            .to_string()),
                    });
                }
                Command::Observe => {
                    let _ = reply.send(Ok(match input.driving_observation() {
                        Some(o) => format!(
                            "INSPECTOR (ground truth, not ears): mile {:.2}. Air ready: {}. \
                             Parking brake: {}. Speed control armed: {}. Keeper: {}. \
                             Cruise: {}. Hazard active: {}. Pull-over active: {}. \
                             Off pavement: {}. Truck damage: {:.0}%. Cargo damage: {:.0}%.",
                            o.position_mi,
                            o.air_ready,
                            o.parking_brake,
                            o.speed_control_armed,
                            o.keeper_active,
                            o.cruise_active,
                            o.hazard_active,
                            o.pull_over_active,
                            o.off_pavement,
                            o.truck_damage_pct,
                            o.cargo_damage_pct,
                        ),
                        None => {
                            "INSPECTOR: not at the wheel (a menu or stop screen is up).".to_string()
                        }
                    }));
                }
                Command::StageHit {
                    hit,
                    opts,
                    found,
                    picked,
                } => {
                    // Dropping into a fresh drive: whatever the agent was
                    // holding belongs to the old screen.
                    self.held.clear();
                    let _ = reply.send(
                        input
                            .stage_road_hit(&hit, &opts)
                            .map(|text| format!("({found} match(es), took {picked}) {text}")),
                    );
                }
                Command::Quit => {
                    let _ = reply.send(Ok("Quitting the game.".to_string()));
                    self.quit = true;
                    return false;
                }
            }
        }
        true
    }
}

// -- the MCP stdio thread -------------------------------------------------------------

fn respond_raw(out: &mut dyn Write, value: &Value) {
    let _ = writeln!(out, "{value}");
    let _ = out.flush();
}

fn tool_text(text: String) -> Value {
    json!({"content": [{"type": "text", "text": text}]})
}

fn tool_error(text: String) -> Value {
    json!({"content": [{"type": "text", "text": text}], "isError": true})
}

fn parse_key(name: &str) -> Option<(Key, Option<char>)> {
    let lowered = name.to_ascii_lowercase();
    if lowered.chars().count() == 1 {
        let ch = lowered.chars().next().unwrap();
        if ch.is_ascii_alphanumeric() {
            return Some((Key::from_char(ch), Some(ch)));
        }
    }
    let key = match lowered.as_str() {
        "up" => Key::Up,
        "down" => Key::Down,
        "left" => Key::Left,
        "right" => Key::Right,
        "enter" | "return" => Key::Return,
        "escape" | "esc" => Key::Escape,
        "space" => Key::Space,
        "tab" => Key::Tab,
        "backspace" => Key::Backspace,
        "home" => Key::Home,
        "end" => Key::End,
        "pageup" => Key::PageUp,
        "pagedown" => Key::PageDown,
        "f1" => Key::F1,
        "f2" => Key::F2,
        "control" | "ctrl" => Key::LCtrl,
        "shift" => Key::LShift,
        "+" | "plus" => return Some((Key::Plus, Some('+'))),
        "-" | "minus" => return Some((Key::Minus, Some('-'))),
        "comma" => Key::Comma,
        "period" => Key::Period,
        _ => return None,
    };
    Some((key, None))
}

fn tools_list() -> Value {
    let tool = |name: &str, description: &str, properties: Value, required: &[&str]| {
        json!({
            "name": name,
            "description": description,
            "inputSchema": {"type": "object", "properties": properties, "required": required},
        })
    };
    json!({"tools": [
        tool(
            "press",
            "Tap a key, as a player would: letters a-z, digits, up, down, left, right, \
             enter, escape, space, tab, backspace, home, end, pageup, pagedown, f1, f2, \
             control, plus, minus, comma, period. Use modifiers for chords such as Alt+A, \
             Shift+K, or Ctrl+Plus. The game \
             starts at its real title menu; menus use arrows and enter, and the drive \
             uses the game's own key bindings. After pressing, wait a beat and listen.",
            json!({
                "key": {"type": "string"},
                "modifiers": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["shift", "ctrl", "alt"]},
                    "uniqueItems": true,
                    "description": "optional modifier keys held for this tap"
                },
                "times": {"type": "integer", "description": "repeat count, default 1, max 50"},
            }),
            &["key"],
        ),
        tool(
            "hold",
            "Hold a key down (throttle, brake, steering, and the manual-transmission Shift \
             clutch are hold keys at the wheel). Pair with release.",
            json!({"key": {"type": "string"}}),
            &["key"],
        ),
        tool(
            "release",
            "Release a key held with hold.",
            json!({"key": {"type": "string"}}),
            &["key"],
        ),
        tool(
            "wait",
            "Let the game run for this many real seconds (max 300) with the controls \
             as they stand, then hear everything from that stretch. This is how road \
             time passes.",
            json!({"seconds": {"type": "number"}}),
            &["seconds"],
        ),
        tool(
            "listen",
            "Everything audible since the last listen: spoken lines on both channels \
             (exactly what the verbosity setting allowed), earcons and cues with their \
             stereo side, sound beds, horn, radio, weather, and where the engine pitch \
             went. This is the whole game; there is no screen.",
            json!({}),
            &[],
        ),
        tool(
            "menu",
            "The rows of the menu currently on screen and which has focus, as a screen \
             reader user would arrow through them. Errors when no menu is up.",
            json!({}),
            &[],
        ),
        tool(
            "observe",
            "INSPECTOR, not ears: a bounded ground-truth snapshot of the drive (mile, \
             brakes, assists, hazard, damage). For judging and diagnosis. If you \
             needed this to drive, the spoken surface failed -- report that.",
            json!({}),
            &[],
        ),
        tool(
            "start_at",
            "Skip the menus: stage a drive at a discovered road feature and take the \
             wheel right there -- the same finder --playtest-road --find uses. \
             feature must be one of: downgrade, upgrade, zone, limit-drop, stop, \
             scale, curve, interchange, toll, chain-law, destination, departure. \
             Same seed, same road. pick chooses among multiple matches (1-based). \
             Listen after staging for the truck's actual starting condition.",
            json!({
                "feature": {"type": "string"},
                "origin": {"type": "string", "description": "search one corridor from this city (fast and thorough)"},
                "destination": {"type": "string", "description": "with origin: the corridor's far end"},
                "seed": {"type": "integer", "description": "default 7"},
                "pick": {"type": "integer", "description": "1-based match index, default 1"},
            }),
            &["feature"],
        ),
        tool(
            "quit_game",
            "Quit the game and end the session (the sandboxed career saves on the way \
             out, as a real quit does).",
            json!({}),
            &[],
        ),
    ]})
}

/// Serve MCP on stdin/stdout, forwarding tool calls into the game loop.
/// Runs on its own thread; returns when stdin closes or the game quits.
pub fn serve(requests: mpsc::Sender<Request>) {
    let stdin = std::io::stdin();
    let mut stdout = std::io::stdout().lock();
    serve_lines(stdin.lock(), &mut stdout, &requests);
}

/// The MCP loop over any reader and writer: the handshake (`initialize`,
/// `tools/list`, `ping`) is answered right here; only a `tools/call` goes
/// through `requests` to the game loop, and the first one is what boots it.
pub fn serve_lines<R: BufRead, W: Write>(reader: R, out: &mut W, requests: &mpsc::Sender<Request>) {
    for line in reader.lines() {
        let Ok(line) = line else { break };
        if line.trim().is_empty() {
            continue;
        }
        let Ok(message) = serde_json::from_str::<Value>(&line) else {
            respond_raw(
                out,
                &json!({
                    "jsonrpc": "2.0", "id": null,
                    "error": {"code": -32700, "message": "parse error"}
                }),
            );
            continue;
        };
        let method = message.get("method").and_then(Value::as_str).unwrap_or("");
        let params = message.get("params").cloned().unwrap_or(Value::Null);
        let Some(id) = message.get("id").cloned() else {
            continue; // notification
        };
        let reply = match method {
            "initialize" => json!({
                "protocolVersion": params
                    .get("protocolVersion")
                    .and_then(Value::as_str)
                    .unwrap_or(PROTOCOL_VERSION),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": env!("CARGO_PKG_VERSION")},
                "instructions": "Freight Fate, played by ear. No game is running yet: the \
                    first tool call other than quit_game boots the real game in its \
                    playtest sandbox (a few seconds), then answers. One game at a \
                    time, so a human already playing makes that first call fail; \
                    try again once they quit.",
            }),
            "ping" => json!({}),
            "tools/list" => tools_list(),
            "tools/call" => {
                let name = params.get("name").and_then(Value::as_str).unwrap_or("");
                let args = params
                    .get("arguments")
                    .and_then(Value::as_object)
                    .cloned()
                    .unwrap_or_default();
                match build_command(name, &args) {
                    Err(text) => tool_error(text),
                    Ok(command) => {
                        let (reply_tx, reply_rx) = mpsc::channel();
                        if requests
                            .send(Request {
                                command,
                                reply: reply_tx,
                            })
                            .is_err()
                        {
                            tool_error("The game has exited.".to_string())
                        } else {
                            match reply_rx
                                .recv_timeout(std::time::Duration::from_secs(REPLY_TIMEOUT_SECONDS))
                            {
                                Ok(Ok(text)) => tool_text(text),
                                Ok(Err(text)) => tool_error(text),
                                Err(_) => {
                                    tool_error("The game loop did not answer in time.".to_string())
                                }
                            }
                        }
                    }
                }
            }
            _ => {
                respond_raw(
                    out,
                    &json!({
                        "jsonrpc": "2.0", "id": id,
                        "error": {"code": -32601, "message": format!("unknown method {method}")}
                    }),
                );
                continue;
            }
        };
        respond_raw(out, &json!({"jsonrpc": "2.0", "id": id, "result": reply}));
    }
}

fn build_command(name: &str, args: &Map<String, Value>) -> Result<Command, String> {
    let key_arg = |args: &Map<String, Value>| -> Result<(Key, Option<char>), String> {
        let name = args.get("key").and_then(Value::as_str).unwrap_or("");
        parse_key(name).ok_or_else(|| format!("{name:?} is not a key this server knows"))
    };
    let modifiers = |args: &Map<String, Value>| -> Result<Mods, String> {
        let mut mods = Mods::NONE;
        let Some(values) = args.get("modifiers") else {
            return Ok(mods);
        };
        let values = values
            .as_array()
            .ok_or_else(|| "modifiers must be an array".to_string())?;
        for value in values {
            let name = value.as_str().unwrap_or("").to_ascii_lowercase();
            match name.as_str() {
                "shift" => mods.shift = true,
                "control" | "ctrl" => mods.ctrl = true,
                "alt" => mods.alt = true,
                _ => return Err(format!("{name:?} is not a modifier this server knows")),
            }
        }
        Ok(mods)
    };
    match name {
        "press" => {
            let (key, text) = key_arg(args)?;
            Ok(Command::Press {
                key,
                text,
                mods: modifiers(args)?,
                times: args.get("times").and_then(Value::as_i64).unwrap_or(1),
            })
        }
        "hold" => {
            let (key, text) = key_arg(args)?;
            Ok(Command::Hold { key, text })
        }
        "release" => {
            let (key, _) = key_arg(args)?;
            Ok(Command::Release { key })
        }
        "wait" => {
            let seconds = args.get("seconds").and_then(Value::as_f64).unwrap_or(0.0);
            if seconds <= 0.0 {
                return Err("wait needs a positive number of seconds".to_string());
            }
            Ok(Command::Wait { seconds })
        }
        "listen" => Ok(Command::Listen),
        "menu" => Ok(Command::Menu),
        "observe" => Ok(Command::Observe),
        "start_at" => {
            let feature = args
                .get("feature")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let seed = args.get("seed").and_then(Value::as_i64).unwrap_or(7);
            let pick = args.get("pick").and_then(Value::as_u64).unwrap_or(1) as usize;
            let origin = args
                .get("origin")
                .and_then(Value::as_str)
                .map(str::to_string);
            let destination = args
                .get("destination")
                .and_then(Value::as_str)
                .map(str::to_string);
            let (hit, opts, found, picked) = discover(&feature, origin, destination, seed, pick)?;
            Ok(Command::StageHit {
                hit: Box::new(hit),
                found,
                picked,
                opts: Box::new(opts),
            })
        }
        "quit_game" => Ok(Command::Quit),
        other => Err(format!("unknown tool {other}")),
    }
}

/// Find one road feature, bounded so it answers in seconds. Runs against
/// world data alone -- safe on any thread, never inside the game loop
/// (an in-frame search froze the whole game, found live 2026-08-30).
/// With no endpoints the sweep is sampled; with endpoints it is capped at
/// thirty corridors, because an origin alone still fans out to every
/// reachable city and a full fan is minutes of search (that is
/// `--playtest-road --scan`'s job).
fn discover(
    feature: &str,
    origin: Option<String>,
    destination: Option<String>,
    seed: i64,
    pick: usize,
) -> Result<
    (
        crate::playtest::road::Hit,
        crate::playtest::road::RoadOptions,
        usize,
        usize,
    ),
    String,
> {
    use crate::playtest::road;
    // An unknown term would "search" and find nothing every time; name the
    // real vocabulary instead ("steep grade" cost a session to this).
    if !road::FEATURES.contains(&feature) {
        return Err(format!(
            "{feature:?} is not a road feature the finder knows. The features are: {}.",
            road::FEATURES.join(", ")
        ));
    }
    let opts = road::RoadOptions {
        feature: feature.to_string(),
        origin: origin.clone(),
        destination,
        seed: Some(seed),
        trip_seed: Some(seed),
        pick,
        sandbox: false, // the whole server already runs sandboxed
        ..Default::default()
    };
    let world = ff_core::data::world::get_world();
    let mut pairs = if opts.origin.is_some() || opts.destination.is_some() {
        road::route_pairs(world, &opts)
    } else {
        road::sampled_world_pairs(world, 30)
    };
    // Nearest corridors first when an origin anchors the search: they are
    // the likeliest to be wanted and the fastest to walk, so the cap keeps
    // the search local instead of taking thirty alphabetical strangers.
    if let Some(anchor) = opts
        .origin
        .as_deref()
        .and_then(|name| world.cities.get(&world.resolve_city_key(name)))
        .map(|c| (c.lat, c.lon))
    {
        let distance = |key: &str| -> f64 {
            world
                .cities
                .get(&world.resolve_city_key(key))
                .map_or(f64::MAX, |c| {
                    ((c.lat - anchor.0).powi(2) + (c.lon - anchor.1).powi(2)).sqrt()
                })
        };
        pairs.sort_by(|x, y| {
            distance(&x.1)
                .partial_cmp(&distance(&y.1))
                .unwrap_or(std::cmp::Ordering::Equal)
        });
    }
    pairs.truncate(30);
    if pairs.is_empty() {
        return Err("No routes matched those options.".to_string());
    }
    eprintln!(
        "[agent-server] searching {} corridor(s) for {feature:?}...",
        pairs.len()
    );
    let started = std::time::Instant::now();
    let hits = road::find_feature_seeded(world, &pairs, feature, &opts);
    eprintln!(
        "[agent-server] search finished in {:.1}s: {} match(es)",
        started.elapsed().as_secs_f64(),
        hits.len()
    );
    if hits.is_empty() {
        return Err(format!(
            "No road feature matching {feature:?} was found in the sampled \
             routes; try another term, another seed, or name an origin \
             city to search a specific corridor."
        ));
    }
    let index = pick.saturating_sub(1).min(hits.len() - 1);
    let hit = hits[index].clone();
    let found = hits.len();
    Ok((hit, opts, found, index + 1))
}

/// A drive to boot the session straight into, skipping every menu.
pub struct LaunchAt {
    pub feature: String,
    pub origin: Option<String>,
    pub destination: Option<String>,
    pub seed: i64,
}

/// Build the policy over the receiver the MCP thread feeds. `first` is the
/// request that woke the game; it is served on the first frame, once the
/// title screen (or the staged drive) exists to receive it.
pub fn policy(
    ears: SharedEars,
    requests: mpsc::Receiver<Request>,
    first: Option<Request>,
) -> AgentPolicy {
    AgentPolicy {
        requests,
        pending: first,
        ears,
        waiting: None,
        held: Vec::new(),
        scripted: std::collections::VecDeque::new(),
        quit: false,
    }
}

/// The whole `--agent-server` mode: sandbox, real game, MCP on stdio.
/// With `launch`, the session boots straight into a staged drive at the
/// found feature -- no menu ever exists.
pub fn run(reset: bool, launch: Option<LaunchAt>) -> i32 {
    // Discover BEFORE the window opens: pure world data, and a failed
    // search should refuse cleanly rather than boot a game.
    let staged = match launch {
        None => None,
        Some(at) => match discover(&at.feature, at.origin, at.destination, at.seed, 1) {
            Ok((hit, opts, found, _)) => {
                eprintln!("Launching at ({found} match(es)): {}", hit.describe());
                Some((hit, opts))
            }
            Err(refusal) => {
                eprintln!("{refusal}");
                return 1;
            }
        },
    };
    run_with_staged(reset, staged)
}

fn run_with_staged(
    reset: bool,
    staged: Option<(
        crate::playtest::road::Hit,
        crate::playtest::road::RoadOptions,
    )>,
) -> i32 {
    use crate::playtest::sandbox;
    let (requests, rx) = mpsc::channel();
    std::thread::spawn(move || serve(requests));
    eprintln!("MCP serving on stdio; the game boots at the first play request.");
    let mut staged = staged;
    loop {
        // Only a play request boots anything. A client that asked for the
        // tool list and hung up gets its answers and never a game window.
        let Some(first) = await_play_request(&rx) else {
            return 0;
        };
        let (mut app, mut guard) = match boot(reset) {
            Ok(booted) => booted,
            Err(text) => {
                // Answered, not fatal: "already running" clears when the
                // human quits, and the next call tries again.
                eprintln!("{text}");
                first.answer(Err(text));
                continue;
            }
        };
        // Never let the operator's keyboard land in the game: a focused
        // game window turns their typing elsewhere into truck inputs.
        app.minimize_window();
        if let Some((hit, opts)) = staged.take() {
            // The staged drive IS the first screen, exactly as the road
            // launcher does it; quitting reaches the real main menu.
            app.set_initial_state(Box::new(move |ctx| {
                let (driving, _start_mi) = crate::playtest::road::build_driving(ctx, &hit, &opts);
                crate::app::share(driving)
            }));
        }
        let ears = install_ears(&mut app);
        let mut policy = policy(ears, rx, Some(first));
        eprintln!("Game up; it speaks aloud while the agent plays.");
        app.run_with_player_input(None, |input, dt| policy.step(input, dt));
        guard.release();
        sandbox::close_session();
        return 0;
    }
}

/// Everything a running game needs, in the order it can be refused:
/// the sandbox prepared and audited, the one-game-at-a-time lock, the
/// session file for the watcher, then the real window, audio and speech.
/// An error leaves nothing held, so the next play request can try again.
fn boot(reset: bool) -> Result<(App, crate::single_instance::SingleInstanceGuard), String> {
    use crate::playtest::sandbox;
    let dir = sandbox::default_sandbox();
    let source = sandbox::real_saves();
    sandbox::prepare(&dir, reset, true, &source)
        .map_err(|e| format!("Could not prepare the agent sandbox: {e}"))?;
    let problems = sandbox::audit(&dir);
    if !problems.is_empty() {
        return Err(format!(
            "{}\nRefusing to boot: an agent must never reach the real account. \
             Restart the server with --reset.",
            problems.join("\n")
        ));
    }
    eprintln!("Agent sandbox: {}", dir.display());
    let mut guard = crate::single_instance::SingleInstanceGuard::new();
    if !guard.acquire() {
        return Err(
            "Freight Fate is already running; one game at a time, agent or human. \
             Call again once it has quit."
                .to_string(),
        );
    }
    let log_path = ff_core::settings::game_root()
        .join("logs")
        .join("agent-session.log");
    // The session file names this log for the watcher, so it has to exist:
    // the other playtest modes configure logging in `main`, but this mode
    // returns before that, and its first sessions wrote nothing at all.
    if let Some(parent) = log_path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    std::env::set_var("FREIGHT_FATE_LOG_FILE", &log_path);
    if std::env::var_os("FREIGHT_FATE_LOG").is_none() {
        std::env::set_var("FREIGHT_FATE_LOG", "INFO");
    }
    crate::app::configure_logging();
    sandbox::open_session(&dir, &log_path);
    match App::new() {
        Ok(app) => Ok((app, guard)),
        Err(e) => {
            guard.release();
            sandbox::close_session();
            Err(format!("The game could not start: {e}"))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::audio::{AudioEngine, NullBackend};

    fn tee_audio(ears: &SharedEars) -> TeeAudio {
        TeeAudio {
            inner: Box::new(AudioEngine::with_backend(Box::new(NullBackend::new()))),
            ears: Rc::clone(ears),
            weather_key: None,
            ambient_key: None,
            loop_keys: HashMap::new(),
        }
    }

    #[test]
    fn press_parser_reaches_the_function_key_help_surface() {
        assert_eq!(parse_key("f1"), Some((Key::F1, None)));
        assert_eq!(parse_key("F2"), Some((Key::F2, None)));
    }

    #[test]
    fn press_parser_reaches_speech_stop_and_speed_adjustment_keys() {
        assert_eq!(parse_key("control"), Some((Key::LCtrl, None)));
        assert_eq!(parse_key("ctrl"), Some((Key::LCtrl, None)));
        assert_eq!(parse_key("shift"), Some((Key::LShift, None)));
        assert_eq!(parse_key("plus"), Some((Key::Plus, Some('+'))));
        assert_eq!(parse_key("minus"), Some((Key::Minus, Some('-'))));
    }

    #[test]
    fn press_command_carries_modifier_chords_to_the_game() {
        let args = serde_json::from_value(json!({
            "key": "a",
            "modifiers": ["alt", "shift"]
        }))
        .unwrap();

        let command = build_command("press", &args).unwrap();

        let Command::Press {
            key,
            text,
            mods,
            times,
        } = command
        else {
            panic!("press tool did not build a press command");
        };
        assert_eq!(key, Key::A);
        assert_eq!(text, Some('a'));
        assert_eq!(
            mods,
            Mods {
                shift: true,
                ctrl: false,
                alt: true,
            }
        );
        assert_eq!(times, 1);
    }

    #[test]
    fn press_command_rejects_unknown_modifiers() {
        let args = serde_json::from_value(json!({
            "key": "a",
            "modifiers": ["meta"]
        }))
        .unwrap();

        let error = match build_command("press", &args) {
            Ok(_) => panic!("unknown modifier was accepted"),
            Err(error) => error,
        };
        assert_eq!(error, "\"meta\" is not a modifier this server knows");
    }

    #[test]
    fn scale_discovery_only_stages_scales_open_in_the_built_drive() {
        let (hit, _opts, found, picked) = discover("scale", None, None, 83, usize::MAX).unwrap();

        assert!(found > 0);
        assert_eq!(picked, found);
        assert!(hit.label.starts_with("OPEN scale:"), "{}", hit.label);
    }

    #[test]
    fn ears_tell_a_silent_engine_return_from_a_crank() {
        // Unpausing brings the engine loop back without the ignition
        // one-shot; the ear used to call both "[engine] starting".
        let ears: SharedEars = Rc::new(RefCell::new(Ears::default()));
        let mut audio = tee_audio(&ears);

        audio.engine_start();
        audio.stop_world();
        audio.engine_start_with(false);

        assert_eq!(
            drain_ears(&ears)
                .lines()
                .filter(|line| line.starts_with("[engine]"))
                .collect::<Vec<_>>(),
            vec!["[engine] starting", "[engine] running again, no crank"]
        );
    }

    #[test]
    fn ears_report_a_continuing_sound_bed_once_until_it_stops() {
        let ears: SharedEars = Rc::new(RefCell::new(Ears::default()));
        let mut audio = tee_audio(&ears);

        audio.start_loop_with(4, "poi/weigh_station_lane", 0.5, 0);
        audio.start_loop_with(4, "poi/weigh_station_lane", 0.6, 0);
        assert_eq!(
            drain_ears(&ears)
                .lines()
                .filter(|line| *line == "[sound bed] poi/weigh_station_lane starts")
                .count(),
            1
        );

        audio.stop_loop_with(4, 0);
        audio.start_loop_with(4, "poi/weigh_station_lane", 0.5, 0);
        assert_eq!(
            drain_ears(&ears),
            "[sound bed] poi/weigh_station_lane starts"
        );
    }

    #[test]
    fn ears_report_ambient_transitions_without_frame_by_frame_repeats() {
        let ears: SharedEars = Rc::new(RefCell::new(Ears::default()));
        let mut audio = tee_audio(&ears);

        audio.set_ambient_with(Some("ambience/night"), 0.4);
        audio.set_ambient_with(Some("ambience/night"), 0.5);
        audio.set_ambient_with(None, 0.0);
        audio.set_ambient_with(Some("ambience/night"), 0.4);

        assert_eq!(
            drain_ears(&ears).lines().collect::<Vec<_>>(),
            vec![
                "[ambience] ambience/night",
                "[ambience] stopped",
                "[ambience] ambience/night",
            ]
        );
    }

    #[test]
    fn stopping_world_allows_the_same_sound_bed_to_be_reported_again() {
        let ears: SharedEars = Rc::new(RefCell::new(Ears::default()));
        let mut audio = tee_audio(&ears);

        audio.start_loop_with(4, "poi/weigh_station_lane", 0.5, 0);
        audio.stop_world();
        audio.start_loop_with(4, "poi/weigh_station_lane", 0.5, 0);

        assert_eq!(
            drain_ears(&ears)
                .lines()
                .filter(|line| *line == "[sound bed] poi/weigh_station_lane starts")
                .count(),
            2
        );
    }

    #[test]
    fn ears_report_a_continuing_weather_bed_once() {
        let ears: SharedEars = Rc::new(RefCell::new(Ears::default()));
        let mut audio = tee_audio(&ears);

        audio.set_weather_with(Some("weather/rain_light"), 0.7);
        audio.set_weather_with(Some("weather/rain_light"), 0.7);

        assert_eq!(
            drain_ears(&ears)
                .lines()
                .filter(|line| *line == "[weather] weather/rain_light")
                .count(),
            1
        );
    }

    #[test]
    fn ears_report_weather_stopping_and_restarting() {
        let ears: SharedEars = Rc::new(RefCell::new(Ears::default()));
        let mut audio = tee_audio(&ears);

        audio.set_weather_with(Some("weather/rain_light"), 0.7);
        audio.set_weather_with(None, 0.0);
        audio.set_weather_with(Some("weather/rain_light"), 0.7);

        assert_eq!(
            drain_ears(&ears).lines().collect::<Vec<_>>(),
            vec![
                "[weather] weather/rain_light",
                "[weather] stopped",
                "[weather] weather/rain_light",
            ]
        );
    }

    #[test]
    fn stopping_world_allows_the_same_weather_to_be_reported_again() {
        let ears: SharedEars = Rc::new(RefCell::new(Ears::default()));
        let mut audio = tee_audio(&ears);

        audio.set_weather_with(Some("weather/rain_light"), 0.7);
        audio.stop_world();
        audio.set_weather_with(Some("weather/rain_light"), 0.7);

        assert_eq!(
            drain_ears(&ears)
                .lines()
                .filter(|line| *line == "[weather] weather/rain_light")
                .count(),
            2
        );
    }
}
