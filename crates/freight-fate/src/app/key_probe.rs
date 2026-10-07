//! What the keyboard looks like to the game, screen reader and all.
//!
//! The Rust successor to Noel Romey's `tools/key_probe.py`. A screen reader
//! that re-sends keys as instant press-and-release pairs (JAWS does) makes a
//! held arrow invisible to the driving loop's polling, and
//! [`HeldKeys`](super::held_keys::HeldKeys) rebuilds the hold from the pairs.
//! This records every key event with the frame it landed in, what the
//! keyboard's own state and the tracker each said at that moment, and how
//! long each frame took, so a player's report shows exactly what their screen
//! reader delivered and whether the tracker read it as a hold.
//!
//! It watches the real game's frame loop, so what it reports is what driving
//! would have seen. Two ways of running it: the `key_probe` tool of the agent
//! server (with the operator's keys let in, a person at a JAWS machine holds
//! the arrows and the agent reads the report), and `freightfate --key-probe`
//! for a tester with no agent at all.

use std::collections::BTreeMap;

use super::held_keys::{HeldKeys, SYNTHETIC_FRAME_MAX_MS};
use super::GameContext;
use crate::states::base::{InputEvent, Key, State};

/// A release this soon after its press is a re-sent key, not a finger: the
/// same line the tracker draws, mirrored for the verdict.
const SYNTHETIC_GAP_MS: u64 = SYNTHETIC_FRAME_MAX_MS;

/// Presses closer than this, each behind a re-sent pair, are one run.
const RUN_GAP_MS: u64 = 100;

/// The event lines kept for the report; the counts keep going past it.
const EVENT_LOG_MAX: usize = 400;

#[derive(Default)]
struct KeyStats {
    downs: u32,
    ups: u32,
    /// Presses SDL flagged as the keyboard's own auto-repeat. A re-sending
    /// screen reader shows none: each of its presses follows a release.
    repeats: u32,
    /// Release to the press before it, in milliseconds.
    gaps: Vec<u64>,
    /// Press to the press before it, in milliseconds.
    spacings: Vec<u64>,
    first_down_ms: Option<u64>,
    last_down_ms: Option<u64>,
    last_down_frame: Option<u64>,
    /// The last release closed a re-sent pair, and this press came right
    /// behind it: the middle of a run, which the log leaves out.
    prev_pair_resent: bool,
    down_in_run: bool,
    /// Press and release in one frame that the tracker takes for a re-send.
    pairs: u32,
    /// Press and release in one frame, but the frame ran long, so the tracker
    /// took it for a finger's tap and let the hold lapse.
    pairs_in_slow_frames: u32,
    /// Release in the very next frame, close enough to be a re-send that
    /// straddled a frame boundary; the tracker takes it for a finger.
    pairs_split_across_frames: u32,
    raw_since: Option<u64>,
    read_since: Option<u64>,
    os_since: Option<u64>,
    longest_raw: u64,
    longest_read: u64,
    /// The longest Windows itself said the key was down, asked directly each
    /// frame: a screen reader that swallows the key events may still leave
    /// this true, which would tell the game the finger is on the key.
    longest_os: u64,
    os_asked: bool,
}

/// Whether Windows reports `key` physically down right now, for the four
/// arrows; `None` for anything else and off Windows.
#[cfg(windows)]
fn os_key_down(key: Key) -> Option<bool> {
    use windows_sys::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState;
    let vk = match key {
        Key::Left => 0x25,
        Key::Up => 0x26,
        Key::Right => 0x27,
        Key::Down => 0x28,
        _ => return None,
    };
    // SAFETY: a pure query of the keyboard state; it takes an integer and
    // touches nothing of ours. The high bit of the result is "down now".
    Some(unsafe { GetAsyncKeyState(vk) } < 0)
}

#[cfg(not(windows))]
fn os_key_down(_key: Key) -> Option<bool> {
    None
}

/// One probe run's measurements.
#[derive(Default)]
pub struct KeyProbe {
    started_ms: u64,
    keys: BTreeMap<String, (Key, KeyStats)>,
    frames: u64,
    slowest_frame_ms: u64,
    slow_frames: u64,
    events: u64,
    log: Vec<String>,
    last_frame_ms: u64,
    escape_seen: bool,
    first: bool,
}

fn label(key: Key) -> String {
    format!("{key:?}")
}

impl KeyProbe {
    pub fn new(input: &HeldKeys) -> Self {
        Self {
            started_ms: input.clock_ms(),
            first: true,
            ..Self::default()
        }
    }

    /// Whether Escape was pressed: the standalone probe ends on it.
    pub fn escape_seen(&self) -> bool {
        self.escape_seen
    }

    /// Milliseconds since the probe began, on the tracker's clock.
    pub fn elapsed_ms(&self, input: &HeldKeys) -> u64 {
        input.clock_ms().saturating_sub(self.started_ms)
    }

    /// Once per frame, after the tracker has clocked it and before its events.
    pub fn begin_frame(&mut self, input: &HeldKeys) {
        if std::mem::take(&mut self.first) {
            return; // the frame the probe was armed in is only partly ours
        }
        let span = input.frame_ms();
        self.frames += 1;
        self.slowest_frame_ms = self.slowest_frame_ms.max(span);
        if span > SYNTHETIC_FRAME_MAX_MS {
            self.slow_frames += 1;
        }
    }

    /// After the app has dispatched `event`, so the tracker's reading is the
    /// one driving would get.
    pub fn note(&mut self, input: &HeldKeys, event: &InputEvent) {
        let now = input.clock_ms();
        let frame = input.frame_number();
        let (key, down, repeat) = match event {
            InputEvent::KeyDown { key, repeat, .. } => (*key, true, *repeat),
            InputEvent::KeyUp { key, .. } => (*key, false, false),
            _ => return,
        };
        if down && key == Key::Escape {
            self.escape_seen = true;
        }
        self.events += 1;
        let name = label(key);
        let stats = &mut self
            .keys
            .entry(name.clone())
            .or_insert((key, KeyStats::default()))
            .1;
        let mut detail = String::new();
        let same_frame = stats.last_down_frame == Some(frame);
        if down {
            stats.downs += 1;
            if repeat {
                stats.repeats += 1;
            }
            stats.down_in_run = false;
            if let Some(previous) = stats.last_down_ms {
                let spacing = now.saturating_sub(previous);
                stats.spacings.push(spacing);
                detail = format!(", {spacing} ms after the last press");
                stats.down_in_run = stats.prev_pair_resent && spacing < RUN_GAP_MS;
            }
            stats.first_down_ms.get_or_insert(now);
            stats.last_down_ms = Some(now);
            stats.last_down_frame = Some(frame);
        } else {
            stats.ups += 1;
            if let Some(pressed) = stats.last_down_ms {
                let gap = now.saturating_sub(pressed);
                stats.gaps.push(gap);
                detail = format!(", {gap} ms after its press");
                if same_frame {
                    if input.frame_ms() <= SYNTHETIC_FRAME_MAX_MS {
                        stats.pairs += 1;
                        stats.prev_pair_resent = true;
                    } else {
                        stats.pairs_in_slow_frames += 1;
                    }
                } else if gap <= SYNTHETIC_GAP_MS {
                    stats.pairs_split_across_frames += 1;
                }
            }
            if !(same_frame && input.frame_ms() <= SYNTHETIC_FRAME_MAX_MS) {
                stats.prev_pair_resent = false;
            }
        }
        // The middle of a run of re-sent pairs adds nothing the counts and the
        // first and last press times do not say, and buries the events that
        // do matter: a lapse, a slow frame, a finger.
        let in_quiet_run = stats.down_in_run
            && (down || (same_frame && input.frame_ms() <= SYNTHETIC_FRAME_MAX_MS));
        if !in_quiet_run && self.log.len() < EVENT_LOG_MAX {
            self.log.push(format!(
                "{:>8} {} {name}{detail}{}{}; keyboard says {}, game reads {} (frame {} ms)",
                now.saturating_sub(self.started_ms),
                if down { "DOWN" } else { "UP  " },
                if repeat { " [keyboard repeat]" } else { "" },
                if !down && same_frame {
                    " [same frame]"
                } else {
                    ""
                },
                if input.physically_down(key) {
                    "down"
                } else {
                    "up"
                },
                if input.is_pressed(key) {
                    "held"
                } else {
                    "not held"
                },
                input.frame_ms(),
            ));
        }
    }

    /// After the frame's events: how long each key has been down, by the
    /// keyboard's own state and by the tracker.
    pub fn end_frame(&mut self, input: &HeldKeys) {
        let now = input.clock_ms();
        self.last_frame_ms = now.saturating_sub(self.started_ms);
        for (key, stats) in self.keys.values_mut() {
            let os = os_key_down(*key);
            stats.os_asked |= os.is_some();
            for (down, since, longest) in [
                (
                    input.physically_down(*key),
                    &mut stats.raw_since,
                    &mut stats.longest_raw,
                ),
                (
                    input.is_pressed(*key),
                    &mut stats.read_since,
                    &mut stats.longest_read,
                ),
                (
                    os.unwrap_or(false),
                    &mut stats.os_since,
                    &mut stats.longest_os,
                ),
            ] {
                match (down, *since) {
                    (true, None) => *since = Some(now),
                    (true, Some(start)) => *longest = (*longest).max(now.saturating_sub(start)),
                    (false, Some(start)) => {
                        *longest = (*longest).max(now.saturating_sub(start));
                        *since = None;
                    }
                    (false, None) => {}
                }
            }
        }
    }

    /// The findings as plain sentences, then the event log. The first block
    /// reads well aloud; the log is for the eye.
    pub fn report(&self) -> Report {
        let mut findings = Vec::new();
        if self.events == 0 {
            findings.push(
                "No key events arrived. The window probably never had focus, or the \
                 operator's keyboard is shut out."
                    .to_string(),
            );
            return Report {
                findings,
                events: Vec::new(),
            };
        }
        findings.push(format!(
            "{} frames measured; the slowest took {} ms and {} ran longer than {} ms.",
            self.frames, self.slowest_frame_ms, self.slow_frames, SYNTHETIC_FRAME_MAX_MS
        ));
        findings.push(format!(
            "The probe has run {} ms; times below are on that clock.",
            self.last_frame_ms
        ));
        let mut all_gaps = Vec::new();
        let (mut pairs, mut slow, mut split, mut repeats) = (0, 0, 0, 0);
        for (name, (_, s)) in &self.keys {
            let mut parts = vec![format!("{name}: {} presses, {} releases", s.downs, s.ups)];
            if !s.gaps.is_empty() {
                parts.push(format!(
                    "release a median {} ms after its press",
                    median(&s.gaps)
                ));
            }
            if !s.spacings.is_empty() {
                parts.push(format!("presses a median {} ms apart", median(&s.spacings)));
            }
            parts.push(format!(
                "longest hold the keyboard saw {} ms",
                s.longest_raw
            ));
            parts.push(format!("longest hold the game read {} ms", s.longest_read));
            if s.os_asked {
                parts.push(format!("longest hold Windows reported {} ms", s.longest_os));
            }
            if let (Some(first), Some(last)) = (s.first_down_ms, s.last_down_ms) {
                parts.push(format!(
                    "first press at {} ms, last at {} ms",
                    first.saturating_sub(self.started_ms),
                    last.saturating_sub(self.started_ms)
                ));
            }
            findings.push(parts.join("; ") + ".");
            all_gaps.extend(s.gaps.iter().copied());
            pairs += s.pairs;
            slow += s.pairs_in_slow_frames;
            split += s.pairs_split_across_frames;
            repeats += s.repeats;
        }
        let resends = !all_gaps.is_empty() && median(&all_gaps) <= SYNTHETIC_GAP_MS;
        if resends {
            findings.push(
                "Verdict: your screen reader re-sends each key as an instant press and \
                 release, so the game never sees a key held by itself and the tracker \
                 is what makes holding work."
                    .to_string(),
            );
            let lost = slow + split;
            let total = pairs + lost;
            if lost == 0 {
                findings.push(format!("All {total} pairs were read as re-sent keys."));
            } else {
                findings.push(format!(
                    "{lost} of {total} pairs were NOT read as re-sent keys: {slow} arrived \
                     in a frame longer than {} ms and {split} were split across two \
                     frames. Each one lets the hold lapse until the next pair.",
                    SYNTHETIC_FRAME_MAX_MS
                ));
            }
        } else if repeats > 0 || !all_gaps.is_empty() {
            findings.push(
                "Verdict: your keys reach the game as real holds. The release comes when \
                 your finger lifts, and the tracker changes nothing."
                    .to_string(),
            );
        }
        Report {
            findings,
            events: self.log.clone(),
        }
    }
}

fn median(values: &[u64]) -> u64 {
    let mut sorted = values.to_vec();
    sorted.sort_unstable();
    sorted[sorted.len() / 2]
}

/// [`KeyProbe::report`]'s two blocks.
pub struct Report {
    pub findings: Vec<String>,
    pub events: Vec<String>,
}

impl Report {
    /// Findings, a blank line, then the event log.
    pub fn text(&self) -> String {
        let mut out = self.findings.join("\n");
        if !self.events.is_empty() {
            out.push_str("\n\nevents (ms since the probe began):\n");
            out.push_str(&self.events.join("\n"));
        }
        out
    }

    /// The findings as one spoken passage.
    pub fn spoken(&self) -> String {
        self.findings.join(" ").replace(" ms", " milliseconds")
    }
}

/// The one screen of `freightfate --key-probe`: inert, so a held arrow is
/// only measured and never moves a menu.
pub struct KeyProbeState {
    seconds: u64,
}

impl KeyProbeState {
    pub fn new(seconds: u64) -> Self {
        Self { seconds }
    }
}

impl State for KeyProbeState {
    fn enter(&mut self, ctx: &mut GameContext) {
        ctx.say(&format!(
            "Key probe ready. Hold each arrow key for a few seconds. It finishes by \
             itself in {} seconds; Escape ends it early.",
            self.seconds
        ));
    }

    fn lines(&self, _ctx: &GameContext) -> Vec<String> {
        vec![
            "Freight Fate key probe".to_string(),
            "Hold each arrow key for a few seconds; it finishes by itself.".to_string(),
        ]
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::states::base::Mods;

    const DT: f64 = 1.0 / 60.0;

    fn keys() -> HeldKeys {
        let mut keys = HeldKeys::with_timing(500, 33);
        keys.begin_frame(DT);
        keys
    }

    fn frame(keys: &mut HeldKeys, probe: &mut KeyProbe, dt: f64) {
        keys.begin_frame(dt);
        probe.begin_frame(keys);
    }

    fn feed(keys: &mut HeldKeys, probe: &mut KeyProbe, event: InputEvent) {
        match &event {
            InputEvent::KeyDown { key, mods, .. } => keys.press(*key, *mods),
            InputEvent::KeyUp { key, mods } => keys.release(*key, *mods),
            _ => {}
        }
        probe.note(keys, &event);
    }

    fn down(key: Key) -> InputEvent {
        InputEvent::KeyDown {
            key,
            mods: Mods::NONE,
            text: None,
            repeat: false,
        }
    }

    fn up(key: Key) -> InputEvent {
        InputEvent::KeyUp {
            key,
            mods: Mods::NONE,
        }
    }

    fn resend_train(frame_dt: f64, pairs: usize) -> KeyProbe {
        let mut keys = keys();
        let mut probe = KeyProbe::new(&keys);
        for _ in 0..pairs {
            for _ in 0..15 {
                frame(&mut keys, &mut probe, DT);
                probe.end_frame(&keys);
            }
            frame(&mut keys, &mut probe, frame_dt);
            feed(&mut keys, &mut probe, down(Key::Up));
            feed(&mut keys, &mut probe, up(Key::Up));
            probe.end_frame(&keys);
        }
        probe
    }

    #[test]
    fn a_re_sent_train_is_reported_as_one_and_read_whole() {
        let report = resend_train(DT, 6).report().text();
        assert!(report.contains("re-sends each key"), "{report}");
        assert!(report.contains("All 6 pairs were read"), "{report}");
    }

    #[test]
    fn pairs_landing_in_slow_frames_are_counted_as_lost() {
        let report = resend_train(0.08, 5).report().text();
        assert!(report.contains("5 of 5 pairs were NOT read"), "{report}");
        assert!(
            report.contains("5 arrived in a frame longer than 40 ms"),
            "{report}"
        );
    }

    #[test]
    fn a_real_tap_is_not_mistaken_for_a_re_send() {
        let mut keys = keys();
        let mut probe = KeyProbe::new(&keys);
        for _ in 0..4 {
            frame(&mut keys, &mut probe, DT);
            feed(&mut keys, &mut probe, down(Key::Down));
            for _ in 0..8 {
                frame(&mut keys, &mut probe, DT);
                probe.end_frame(&keys);
            }
            feed(&mut keys, &mut probe, up(Key::Down));
            probe.end_frame(&keys);
        }
        let report = probe.report().text();
        assert!(report.contains("real holds"), "{report}");
        assert!(!report.contains("re-sends"), "{report}");
    }

    #[test]
    fn no_events_says_so() {
        let keys = keys();
        let probe = KeyProbe::new(&keys);
        assert!(probe.report().text().starts_with("No key events arrived"));
    }
}
