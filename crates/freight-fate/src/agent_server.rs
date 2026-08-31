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

use std::cell::RefCell;
use std::io::{BufRead, Write as _};
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
}

pub type SharedEars = Rc<RefCell<Ears>>;

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
        self.hear(format!("[sound bed] {key} starts"));
        self.inner.start_loop_with(channel, key, volume, fade_ms);
    }
    fn set_loop_volume(&mut self, channel: u32, volume: f64) {
        self.inner.set_loop_volume(channel, volume);
    }
    fn set_loop_pan(&mut self, channel: u32, pan: f64) {
        self.inner.set_loop_pan(channel, pan);
    }
    fn stop_loop_with(&mut self, channel: u32, fade_ms: u32) {
        self.inner.stop_loop_with(channel, fade_ms);
    }
    fn start_sustain_loop_with(
        &mut self,
        channel: u32,
        key: &str,
        spec: SustainLoopSpec,
        volume: f64,
    ) {
        self.hear(format!("[sound bed] {key} starts"));
        self.inner
            .start_sustain_loop_with(channel, key, spec, volume);
    }
    fn release_sustain_loop_with(&mut self, channel: u32, fade_ms: u32) {
        self.inner.release_sustain_loop_with(channel, fade_ms);
    }
    fn hold_alert_with(&mut self, key: &str, volume: f64, fade_ms: u32) {
        self.hear(format!("[alert] {key} holds"));
        self.inner.hold_alert_with(key, volume, fade_ms);
    }
    fn release_alert_with(&mut self, fade_ms: u32) {
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
        self.hear("[engine] starting".to_string());
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
        if let Some(key) = key {
            self.hear(format!("[ambience] {key}"));
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
        if self.weather_key.take().is_some() {
            self.hear("[weather] stopped".to_string());
        }
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
    let ears: SharedEars = Rc::new(RefCell::new(Ears::default()));
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

enum Command {
    Press {
        key: Key,
        text: Option<char>,
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

/// The per-frame policy servicing agent commands inside the real game loop.
pub struct AgentPolicy {
    requests: mpsc::Receiver<Request>,
    ears: SharedEars,
    waiting: Option<(f64, mpsc::Sender<Result<String, String>>)>,
    /// Keys the agent is holding. Re-asserted every frame, because the
    /// focus-lost safety wipe (built for real keyboards) otherwise drops
    /// them whenever the operator's screen reader moves window focus --
    /// which on a working desktop is constantly. Found live: the agent's
    /// first throttle hold worked (window still focused from launch) and
    /// every later one silently died.
    held: Vec<Key>,
    quit: bool,
}

impl AgentPolicy {
    /// One frame. Returns false to end the game loop.
    pub fn step(&mut self, input: &mut PlayerInputFrame<'_>, dt: f64) -> bool {
        if self.quit {
            return false;
        }
        for key in &self.held {
            input.assert_held(*key);
        }
        if let Some((remaining, reply)) = self.waiting.take() {
            let remaining = remaining - dt;
            if remaining > 0.0 {
                self.waiting = Some((remaining, reply));
                return true;
            }
            let _ = reply.send(Ok(drain_ears(&self.ears)));
        }
        while let Ok(request) = self.requests.try_recv() {
            let reply = request.reply;
            match request.command {
                Command::Press { key, text, times } => {
                    for _ in 0..times.clamp(1, 50) {
                        input.queue_player_input(InputEvent::KeyDown {
                            key,
                            mods: Mods::NONE,
                            text,
                        });
                        input.queue_player_input(InputEvent::KeyUp {
                            key,
                            mods: Mods::NONE,
                        });
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

fn respond_raw(value: &Value) {
    let mut out = std::io::stdout().lock();
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
             enter, escape, space, tab, backspace, home, end, comma, period. The game \
             starts at its real title menu; menus use arrows and enter, and the drive \
             uses the game's own key bindings. After pressing, wait a beat and listen.",
            json!({
                "key": {"type": "string"},
                "times": {"type": "integer", "description": "repeat count, default 1, max 50"},
            }),
            &["key"],
        ),
        tool(
            "hold",
            "Hold a key down (throttle, brake, steering are hold keys at the wheel). \
             Pair with release.",
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
    for line in stdin.lock().lines() {
        let Ok(line) = line else { break };
        if line.trim().is_empty() {
            continue;
        }
        let Ok(message) = serde_json::from_str::<Value>(&line) else {
            respond_raw(&json!({
                "jsonrpc": "2.0", "id": null,
                "error": {"code": -32700, "message": "parse error"}
            }));
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
                respond_raw(&json!({
                    "jsonrpc": "2.0", "id": id,
                    "error": {"code": -32601, "message": format!("unknown method {method}")}
                }));
                continue;
            }
        };
        respond_raw(&json!({"jsonrpc": "2.0", "id": id, "result": reply}));
    }
}

fn build_command(name: &str, args: &Map<String, Value>) -> Result<Command, String> {
    let key_arg = |args: &Map<String, Value>| -> Result<(Key, Option<char>), String> {
        let name = args.get("key").and_then(Value::as_str).unwrap_or("");
        parse_key(name).ok_or_else(|| format!("{name:?} is not a key this server knows"))
    };
    match name {
        "press" => {
            let (key, text) = key_arg(args)?;
            Ok(Command::Press {
                key,
                text,
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
    let hits = road::find_feature(world, &pairs, feature, &opts, opts.seed);
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

/// Build the policy and the sender its MCP thread feeds.
pub fn policy(ears: SharedEars) -> (AgentPolicy, mpsc::Sender<Request>) {
    let (tx, rx) = mpsc::channel();
    (
        AgentPolicy {
            requests: rx,
            ears,
            waiting: None,
            held: Vec::new(),
            quit: false,
        },
        tx,
    )
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
    let dir = sandbox::default_sandbox();
    let source = sandbox::real_saves();
    if let Err(e) = sandbox::prepare(&dir, reset, true, &source) {
        eprintln!("Could not prepare the agent sandbox: {e}");
        return 1;
    }
    let problems = sandbox::audit(&dir);
    if !problems.is_empty() {
        for problem in &problems {
            eprintln!("{problem}");
        }
        eprintln!("Refusing to serve: an agent must never reach the real account. Pass --reset.");
        return 1;
    }
    eprintln!("Agent sandbox: {}", dir.display());
    let mut guard = crate::single_instance::SingleInstanceGuard::new();
    if !guard.acquire() {
        eprintln!("Freight Fate is already running; one game at a time, agent or human.");
        return 1;
    }
    let log_path = ff_core::settings::game_root()
        .join("logs")
        .join("agent-session.log");
    sandbox::open_session(&dir, &log_path);
    let code = {
        let mut app = match App::new() {
            Ok(app) => app,
            Err(e) => {
                eprintln!("Fatal error: {e}");
                guard.release();
                sandbox::close_session();
                return 1;
            }
        };
        // Never let the operator's keyboard land in the game: a focused
        // game window turns their typing elsewhere into truck inputs.
        app.minimize_window();
        if let Some((hit, opts)) = staged {
            // The staged drive IS the first screen, exactly as the road
            // launcher does it; quitting reaches the real main menu.
            app.set_initial_state(Box::new(move |ctx| {
                let (driving, _start_mi) = crate::playtest::road::build_driving(ctx, &hit, &opts);
                crate::app::share(driving)
            }));
        }
        let ears = install_ears(&mut app);
        let (mut policy, requests) = policy(ears);
        std::thread::spawn(move || serve(requests));
        eprintln!("MCP serving on stdio; the game speaks aloud while the agent plays.");
        app.run_with_player_input(None, |input, dt| policy.step(input, dt));
        0
    };
    guard.release();
    sandbox::close_session();
    code
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
        }
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
