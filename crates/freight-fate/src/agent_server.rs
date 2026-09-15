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

use std::sync::mpsc;

use crate::app::{App, PlayerInputFrame};
use crate::bindings::{key_saved_name, Action, KeyBindings};
use crate::states::base::{InputEvent, Key, Mods};

/// One `wait` may hold the wheel for at most this much real time.
const MAX_WAIT_SECONDS: f64 = 300.0;
/// A `pedal` hold may last at most this long: a pedal is a gesture, and a
/// held throttle for a minute is what `hold` is for.
const MAX_PEDAL_SECONDS: f64 = 30.0;
/// How long after a pedal lifts before its reply is written, so the ears
/// carry what the truck did with the input, not only the input.
const PEDAL_SETTLE_SECONDS: f64 = 0.5;
/// How long `status` waits for the readouts it asked for before replying.
const STATUS_SETTLE_SECONDS: f64 = 3.0;
/// Frames between a K tap and reading what cruise captured, and after the
/// last dial tap before the reply: a tap is two frames, the drive answers
/// on the next.
const CRUISE_SETTLE_FRAMES: u32 = 8;
const CRUISE_REPLY_FRAMES: u32 = 30;
/// The dial is walked one mile per hour at a time (Ctrl with plus or
/// minus); no target is ever this far from what K captured.
const MAX_CRUISE_TAPS: i64 = 60;

mod ears;
mod protocol;

pub use ears::{install_ears, Ears, SharedEars};
pub use protocol::{build_command, serve_lines};

use ears::drain_ears;
use protocol::{discover, serve};
// -- commands between the MCP thread and the game loop --------------------------------

/// What a key tool was asked to press: a key by name, or a driving control
/// by its shortcut id, resolved against the player's own table when the
/// loop runs it (so a sandbox with moved keys is driven the way its player
/// would drive it).
#[derive(Clone, Debug, PartialEq)]
pub enum KeySpec {
    Key { key: Key, text: Option<char> },
    Action(Action),
}

impl KeySpec {
    /// The key, its typed character, and the modifiers the chord carries.
    /// A control the keyboard does not have (the pad-only ones) is refused.
    pub fn resolve(&self, bindings: &KeyBindings) -> Result<(Key, Option<char>, Mods), String> {
        match self {
            KeySpec::Key { key, text } => Ok((*key, *text, Mods::NONE)),
            KeySpec::Action(action) => {
                let chord = bindings
                    .chords(*action)
                    .into_iter()
                    .next()
                    .ok_or_else(|| format!("{} has no keyboard key", action.label()))?;
                let text = key_saved_name(chord.key)
                    .filter(|name| name.chars().count() == 1)
                    .and_then(|name| name.chars().next());
                Ok((chord.key, text, chord.mods))
            }
        }
    }
}

pub enum Command {
    Press {
        key: KeySpec,
        mods: Mods,
        times: i64,
    },
    Hold {
        key: KeySpec,
    },
    Release {
        key: KeySpec,
    },
    /// Put the sandbox career in any situation and reopen the terminal on
    /// it (`playtest::scenario`). Scenario staging, not play.
    Scenario(Box<crate::playtest::scenario::Scenario>),
    Wait {
        seconds: f64,
    },
    /// Hold a key for a bounded stretch and let the LOOP release it. A
    /// hold-then-release through the client is a second or more of round
    /// trip, and at standard pacing that is twenty seconds of road: every
    /// throttle tap overshot the limit and every brake landed late (agent
    /// drive, 2026-09-02). Replies after the release with what was heard.
    Pedal {
        key: KeySpec,
        seconds: f64,
    },
    /// Run until a line carrying `text` is heard, or a menu opens, or the
    /// clock runs out -- whichever first. Replies with what was heard.
    WaitFor {
        text: Option<String>,
        menu: bool,
        seconds: f64,
    },
    /// Choose a menu row by (part of) its label: Home, Down to it, Enter.
    Select {
        label: String,
    },
    /// Engage adaptive cruise and walk the dial to a number, the posted
    /// limit, or off -- K and the Ctrl plus/minus taps a player would use.
    Cruise {
        target: CruiseTarget,
    },
    /// The wheel's readouts in one call: speed, limit, grade, what is ahead,
    /// the route, the clock, fuel.
    Status,
    /// Hand the keyboard to the operator or take it back (see
    /// [`PlayerInputFrame::set_operator_keys`]).
    OperatorKeys {
        live: bool,
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

/// Where the cruise tool is asked to put the dial.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum CruiseTarget {
    Mph(f64),
    /// The limit enforcement is holding the truck to right now.
    Limit,
    Off,
}

type Reply = mpsc::Sender<Result<String, String>>;

/// What a deferred reply is waiting on.
enum Until {
    /// The clock alone.
    Elapsed,
    /// Any ear line carrying this (lower-cased) text, or the clock.
    Heard(String),
    /// A menu on screen, or the clock.
    Menu,
}

struct Waiting {
    remaining: f64,
    until: Until,
    /// Where in the ears the scan for `Heard` resumes.
    scanned: usize,
    /// False for a plain `wait`; true for the tools whose reply should say
    /// when the clock, not the thing waited for, ended the wait.
    reports_timeout: bool,
    reply: Reply,
}

enum CruiseStage {
    /// Tap K if nothing is holding speed, then settle.
    Engage,
    /// Frames until the captured set point is read and the dial walked.
    Settle(u32),
    /// Frames until the reply, once the dial taps are scripted.
    Trim(u32),
}

struct CruisePlan {
    target: CruiseTarget,
    stage: CruiseStage,
    reply: Reply,
}

pub struct Request {
    command: Command,
    reply: Reply,
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
    waiting: Option<Waiting>,
    /// Keys the agent is holding. Re-asserted every frame, because the
    /// focus-lost safety wipe (built for real keyboards) otherwise drops
    /// them whenever the operator's screen reader moves window focus --
    /// which on a working desktop is constantly. Found live: the agent's
    /// first throttle hold worked (window still focused from launch) and
    /// every later one silently died.
    held: Vec<Key>,
    /// A `pedal`: the key and the real seconds left before the loop lifts
    /// it. Asserted every frame like a hold; released here, never by the
    /// client.
    timed_hold: Option<(Key, f64)>,
    /// A `cruise` call in progress across frames.
    cruise_plan: Option<CruisePlan>,
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

    /// Script a finger tap: down on one frame, up on the next.
    fn tap(&mut self, key: Key, text: Option<char>, mods: Mods) {
        self.scripted
            .push_back(vec![InputEvent::KeyDown { key, mods, text }]);
        self.scripted
            .push_back(vec![InputEvent::KeyUp { key, mods }]);
    }

    /// Park a reply until the clock, a line, or a menu releases it.
    fn wait_until(&mut self, seconds: f64, until: Until, reports_timeout: bool, reply: Reply) {
        // Scanned from the start of the unreported ears, not from the
        // moment the call arrived: the line waited for is often spoken
        // during the round trip that follows the key that caused it (a
        // menu row after Enter), and a wait that began scanning after it
        // ran its whole clock out and then reported the line anyway
        // (first live use, 2026-09-02).
        self.waiting = Some(Waiting {
            remaining: seconds.clamp(0.05, MAX_WAIT_SECONDS),
            until,
            scanned: 0,
            reports_timeout,
            reply,
        });
    }

    /// The cruise tool's frame: K, then read what it captured, then walk
    /// the dial, then answer with what was heard.
    fn advance_cruise_plan(&mut self, input: &mut PlayerInputFrame<'_>) {
        let Some(mut plan) = self.cruise_plan.take() else {
            return;
        };
        let Some(observed) = input.driving_observation() else {
            let _ = plan.reply.send(Err(
                "Not at the wheel: cruise needs the drive on screen.".to_string()
            ));
            return;
        };
        let holding = observed.cruise_set_mph.is_some() || observed.keeper_mph.is_some();
        match plan.stage {
            CruiseStage::Engage => {
                if plan.target == CruiseTarget::Off {
                    if holding {
                        self.tap(Key::K, Some('k'), Mods::NONE);
                    }
                    let _ = plan.reply.send(Ok(if holding {
                        "Cancelling with K. Wait a moment, then listen.".to_string()
                    } else {
                        "Nothing was holding speed; cruise is already off.".to_string()
                    }));
                    return;
                }
                if !holding {
                    self.tap(Key::K, Some('k'), Mods::NONE);
                    plan.stage = CruiseStage::Settle(CRUISE_SETTLE_FRAMES);
                } else {
                    plan.stage = CruiseStage::Settle(0);
                }
            }
            CruiseStage::Settle(0) => {
                let Some(set) = observed.cruise_set_mph else {
                    let _ = plan.reply.send(Ok(if observed.keeper_mph.is_some() {
                        format!(
                            "The speed keeper has this zone, so adaptive cruise is not \
                             available here; the dial is not walked.\n{}",
                            drain_ears(&self.ears)
                        )
                    } else {
                        format!(
                            "Adaptive cruise did not engage; listen for why (engine, air, \
                             speed, or the zone).\n{}",
                            drain_ears(&self.ears)
                        )
                    }));
                    return;
                };
                let wanted = match plan.target {
                    CruiseTarget::Mph(mph) => Some(mph),
                    CruiseTarget::Limit => observed.speed_limit_mph,
                    CruiseTarget::Off => None,
                };
                let Some(wanted) = wanted else {
                    let _ = plan.reply.send(Ok(format!(
                        "Cruise is set at {set:.0}; no posted limit has been read yet, so \
                         the dial was left there.\n{}",
                        drain_ears(&self.ears)
                    )));
                    return;
                };
                let steps =
                    ((wanted - set).round() as i64).clamp(-MAX_CRUISE_TAPS, MAX_CRUISE_TAPS);
                let (key, text) = if steps > 0 {
                    (Key::Plus, Some('+'))
                } else {
                    (Key::Minus, Some('-'))
                };
                // A plain tap walks the fives grid and a Ctrl tap one mile
                // per hour, so a set point already on the grid takes the
                // fives first: 30 to 55 was twenty-five spoken steps on the
                // first live use, and is five this way.
                let fine = Mods {
                    ctrl: true,
                    ..Mods::NONE
                };
                let mut taps = 0u32;
                let mut left = steps.unsigned_abs();
                if set.rem_euclid(5.0) < 0.01 {
                    while left >= 5 {
                        self.tap(key, text, Mods::NONE);
                        left -= 5;
                        taps += 1;
                    }
                }
                for _ in 0..left {
                    self.tap(key, text, fine);
                    taps += 1;
                }
                plan.stage = CruiseStage::Trim(taps * 2 + CRUISE_REPLY_FRAMES);
            }
            CruiseStage::Settle(frames) => plan.stage = CruiseStage::Settle(frames - 1),
            CruiseStage::Trim(0) => {
                let _ = plan.reply.send(Ok(drain_ears(&self.ears)));
                return;
            }
            CruiseStage::Trim(frames) => plan.stage = CruiseStage::Trim(frames - 1),
        }
        self.cruise_plan = Some(plan);
    }

    /// One frame. Returns false to end the game loop.
    pub fn step(&mut self, input: &mut PlayerInputFrame<'_>, dt: f64) -> bool {
        if self.quit {
            return false;
        }
        for key in &self.held {
            input.assert_held(*key);
        }
        if let Some((key, remaining)) = self.timed_hold.take() {
            let remaining = remaining - dt;
            if remaining > 0.0 {
                input.assert_held(key);
                self.timed_hold = Some((key, remaining));
            } else {
                input.queue_player_input(InputEvent::KeyUp {
                    key,
                    mods: Mods::NONE,
                });
            }
        }
        if let Some(frame) = self.scripted.pop_front() {
            for event in frame {
                input.queue_player_input(event);
            }
        }
        self.advance_cruise_plan(input);
        if let Some(mut waiting) = self.waiting.take() {
            waiting.remaining -= dt;
            let out_of_time = waiting.remaining <= 0.0;
            let released = match &waiting.until {
                Until::Elapsed => out_of_time,
                Until::Heard(needle) => {
                    let ears = self.ears.borrow();
                    let from = waiting.scanned.min(ears.lines.len());
                    let heard = ears.lines[from..]
                        .iter()
                        .any(|line| line.to_lowercase().contains(needle.as_str()));
                    waiting.scanned = ears.lines.len();
                    heard || out_of_time
                }
                Until::Menu => input.menu_rows().is_some() || out_of_time,
            };
            if !released {
                self.waiting = Some(waiting);
                return true;
            }
            let mut text = drain_ears(&self.ears);
            if out_of_time && waiting.reports_timeout && !matches!(waiting.until, Until::Elapsed) {
                text.push_str("\n(the clock ran out before that arrived)");
            }
            let _ = waiting.reply.send(Ok(text));
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
                Command::Press { key, mods, times } => {
                    let (key, text, chord_mods) = match key.resolve(input.bindings()) {
                        Ok(resolved) => resolved,
                        Err(text) => {
                            let _ = reply.send(Err(text));
                            continue;
                        }
                    };
                    let mods = Mods {
                        shift: mods.shift || chord_mods.shift,
                        ctrl: mods.ctrl || chord_mods.ctrl,
                        alt: mods.alt || chord_mods.alt,
                    };
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
                Command::Hold { key } => {
                    let (key, text, _) = match key.resolve(input.bindings()) {
                        Ok(resolved) => resolved,
                        Err(text) => {
                            let _ = reply.send(Err(text));
                            continue;
                        }
                    };
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
                    let (key, _, _) = match key.resolve(input.bindings()) {
                        Ok(resolved) => resolved,
                        Err(text) => {
                            let _ = reply.send(Err(text));
                            continue;
                        }
                    };
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
                    self.wait_until(seconds, Until::Elapsed, false, reply);
                    break;
                }
                Command::Pedal { key, seconds } => {
                    let (key, text, _) = match key.resolve(input.bindings()) {
                        Ok(resolved) => resolved,
                        Err(text) => {
                            let _ = reply.send(Err(text));
                            continue;
                        }
                    };
                    if self.timed_hold.is_some() {
                        let _ = reply.send(Err(
                            "A pedal is already down; its reply arrives when it lifts.".to_string(),
                        ));
                        continue;
                    }
                    // A client hold of the same key would fight the release.
                    self.held.retain(|held| *held != key);
                    input.queue_player_input(InputEvent::KeyDown {
                        key,
                        mods: Mods::NONE,
                        text,
                    });
                    let seconds = seconds.clamp(0.05, MAX_PEDAL_SECONDS);
                    self.timed_hold = Some((key, seconds));
                    self.wait_until(seconds + PEDAL_SETTLE_SECONDS, Until::Elapsed, false, reply);
                    break;
                }
                Command::WaitFor {
                    text,
                    menu,
                    seconds,
                } => {
                    let until = if menu {
                        Until::Menu
                    } else {
                        match text {
                            Some(text) => Until::Heard(text.to_lowercase()),
                            None => Until::Elapsed,
                        }
                    };
                    self.wait_until(seconds, until, true, reply);
                    break;
                }
                Command::Select { label } => {
                    let _ = reply.send(match input.menu_rows() {
                        None => Err("No menu is on screen right now.".to_string()),
                        Some((labels, _focus)) => {
                            let needle = label.to_lowercase();
                            match labels
                                .iter()
                                .position(|row| row.to_lowercase().contains(&needle))
                            {
                                None => Err(format!(
                                    "No row carries {label:?}. The rows are:\n{}",
                                    labels
                                        .iter()
                                        .enumerate()
                                        .map(|(i, row)| format!("{}. {row}", i + 1))
                                        .collect::<Vec<_>>()
                                        .join("\n")
                                )),
                                Some(index) => {
                                    // Home first, so the focus row never matters.
                                    self.tap(Key::Home, None, Mods::NONE);
                                    for _ in 0..index {
                                        self.tap(Key::Down, None, Mods::NONE);
                                    }
                                    self.tap(Key::Return, None, Mods::NONE);
                                    Ok(format!(
                                        "Selecting row {}: {}. Wait a moment, then listen.",
                                        index + 1,
                                        labels[index]
                                    ))
                                }
                            }
                        }
                    });
                }
                Command::Cruise { target } => {
                    if self.cruise_plan.is_some() {
                        let _ =
                            reply.send(Err("A cruise call is still walking the dial.".to_string()));
                        continue;
                    }
                    self.cruise_plan = Some(CruisePlan {
                        target,
                        stage: CruiseStage::Engage,
                        reply,
                    });
                    break;
                }
                Command::Status => {
                    for (key, text) in [
                        (Key::Space, None),
                        (Key::S, Some('s')),
                        (Key::G, Some('g')),
                        (Key::U, Some('u')),
                        (Key::R, Some('r')),
                        (Key::C, Some('c')),
                        (Key::F, Some('f')),
                    ] {
                        self.tap(key, text, Mods::NONE);
                    }
                    self.wait_until(STATUS_SETTLE_SECONDS, Until::Elapsed, false, reply);
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
                            "INSPECTOR (ground truth, not ears): mile {:.2}. Speed {:.0} mph, \
                             limit {}. Air ready: {}. Parking brake: {}. Speed control armed: \
                             {}. Keeper: {}. Cruise: {}. Hazard active: {}. Pull-over active: \
                             {}. Off pavement: {}. Truck damage: {:.0}%. Cargo damage: {:.0}%.",
                            o.position_mi,
                            o.speed_mph,
                            o.speed_limit_mph
                                .map_or("not read yet".to_string(), |mph| format!("{mph:.0}")),
                            o.air_ready,
                            o.parking_brake,
                            o.speed_control_armed,
                            o.keeper_mph
                                .map_or("off".to_string(), |mph| format!("holding {mph:.0}")),
                            o.cruise_set_mph
                                .map_or("off".to_string(), |mph| format!("set {mph:.0}")),
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
                    self.timed_hold = None;
                    let _ = reply.send(
                        input
                            .stage_road_hit(&hit, &opts)
                            .map(|text| format!("({found} match(es), took {picked}) {text}")),
                    );
                }
                Command::Scenario(scenario) => {
                    // A new situation: whatever the agent was holding belongs
                    // to the old screen, the same as a staged drive.
                    self.held.clear();
                    self.timed_hold = None;
                    let _ = reply.send(input.stage_scenario(&scenario));
                }
                Command::OperatorKeys { live } => {
                    let _ = reply.send(Ok(input.set_operator_keys(live)));
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
        timed_hold: None,
        cruise_plan: None,
        scripted: std::collections::VecDeque::new(),
        quit: false,
    }
}

/// The whole `--agent-server` mode: sandbox, real game, MCP on stdio.
/// With `launch`, the session boots straight into a staged drive at the
/// found feature -- no menu ever exists. With `operator_keys`, the window
/// stays up and the operator's keyboard reaches the game, so a human can
/// take the wheel alongside the agent; off, the keys are dropped at the
/// door (see [`run_with_staged`]).
pub fn run(reset: bool, launch: Option<LaunchAt>, operator_keys: bool) -> i32 {
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
    run_with_staged(reset, staged, operator_keys)
}

fn run_with_staged(
    reset: bool,
    staged: Option<(
        crate::playtest::road::Hit,
        crate::playtest::road::RoadOptions,
    )>,
    operator_keys: bool,
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
        // game window turns their typing elsewhere into truck inputs -- and
        // minimizing alone did not hold (the owner's typing in the next
        // window arrived as readouts mid-run, 2026-09-01), so the keys are
        // dropped at the door as well. `--operator-keys` is the owner's
        // opt-in to play alongside the agent (asked for 2026-09-11): the
        // window stays up and every key counts, so the keyboard belongs to
        // the game for the whole session.
        if operator_keys {
            eprintln!("Operator keys are live: the keyboard reaches the game.");
        } else {
            app.minimize_window();
            app.ignore_operator_keys();
        }
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
