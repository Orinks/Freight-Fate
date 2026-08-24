//! Held keys as the driving loop should see them, screen reader or not.
//!
//! Driving reads the pedals and the wheel by polling: is Up down right now?
//! [`HeldKeys::is_pressed`] answers from the key events the app dispatched
//! (`pygame.key.get_pressed()`), and with no screen reader, or with NVDA,
//! that is the physical keyboard: a held key reads held until the finger
//! lifts.
//!
//! JAWS is different. It binds the arrow keys to its own scripts in every
//! application, so its keyboard hook swallows the physical press, runs the
//! script, and re-sends the key to the application as a synthetic
//! press-and-release pair. The game sees a tap that lasts zero frames, which
//! a poll never catches: menus react to the press event and work, driving
//! polls and does nothing until the player passes one key through with JAWS
//! Key+3. Holding the key does not help by itself, but the keyboard's
//! auto-repeat still runs underneath; every repeat goes through the same
//! hook and arrives as another pair. Measured on the owner's JAWS machine
//! (2026-08-24, `tools/key_probe.py`): the first repeat lands at the Windows
//! repeat delay (512 ms), the rest about 250 ms apart -- not the 33 ms
//! Windows rate, because JAWS's script takes that long per key and the
//! repeats queue behind it.
//!
//! The pulse layer here turns that train back into a hold. Every press
//! starts a pulse: a fresh press gets one long enough to reach the first
//! auto-repeat (the operating system's delay plus grace); a repeat gets one
//! just past the spacing the repeats are actually arriving at, which the
//! tracker learns from the pairs themselves (second repeat onward, synthetic
//! pairs only) and keeps for the rest of the session. Until it has learned
//! that spacing, repeats get the fresh pulse too, so the very first hold
//! never stutters. A release in the same frame as the press that began the
//! pair is synthetic -- nobody taps a key inside one frame -- and leaves the
//! pulse alone; a release in a later frame is the player's finger and ends
//! it. A key reads pressed when it is physically down OR a pulse is alive,
//! so the physical path is exactly what it always was and the re-injected
//! path reads as a hold that lapses one learned spacing plus grace after the
//! last pair.
//!
//! Two guards keep the physical path honest. SDL delivers the keyboard's own
//! auto-repeat as more `KeyDown`s of a key that is already down, so only a
//! press from the released state can begin a synthetic pair: a finger
//! lifting in the same frame as one of those repeats is a real release. And
//! the layer is inert until [`HeldKeys::begin_frame`] has clocked a frame --
//! the playtest harness and the tests feed keys straight in without a frame
//! loop, and they keep today's plain semantics.
//!
//! Two honest limits. A screen reader that re-injects keys never shows the
//! game how long a tap lasted, so under JAWS a tap reads as a hold for the
//! repeat delay (half a second at the Windows default), letting go reads
//! about a third of a second late, and a gesture built on tap length (the
//! pedal latch) cannot be seen. And the game cannot tell whether such a
//! screen reader is running, so the pulse logic is always on; on the
//! physical path it only ever adds a hold when a whole press-and-release
//! arrives inside one short frame, which a finger cannot do.

use std::collections::{HashMap, HashSet};

use crate::states::base::{Key, Mods};

/// Fallbacks when the operating system will not say: the Windows defaults
/// (delay setting 1 of 0..3 is 500 ms; rate setting 31 of 0..31 is about 30
/// repeats per second).
pub const DEFAULT_REPEAT_DELAY_MS: u64 = 500;
pub const DEFAULT_REPEAT_INTERVAL_MS: u64 = 33;

/// Grace on top of the measured timing. The fresh-press pulse has to outlast
/// the repeat delay plus the screen reader's script latency and a frame of
/// batching; the per-repeat pulse has to outlast one spacing plus jitter
/// (about 30 ms measured) and a frame, and it is how long after the finger
/// lifts the key still reads held, so it stays short.
pub const FRESH_GRACE_MS: u64 = 150;
pub const REPEAT_GRACE_MS: u64 = 100;

/// A press and release in one frame is synthetic only when the frame was a
/// normal one. After a long hitch a whole real tap can land in one batch,
/// and then the honest answer is "not held", never a half-second hold. A
/// re-injected pair dropped this way costs nothing: the next repeat pair
/// re-establishes the hold a frame later.
pub const SYNTHETIC_FRAME_MAX_MS: u64 = 40;

/// A press this soon after its pulse train began cannot be the operating
/// system's first auto-repeat (which never fires early), so it is a new tap
/// of the same key and earns a fresh full pulse.
pub const REPEAT_EARLY_TOLERANCE_MS: u64 = 60;

/// The learned repeat spacing is the largest of this many recent spacings,
/// so one slow script run widens the window at once and a run of quick ones
/// narrows it again only once it has aged out.
pub const LEARNED_SPACINGS: usize = 8;

/// Windows keyboard delay setting (0..3) to milliseconds before the first
/// auto-repeat: 250 ms per step, so 0 is 250 ms and 3 is a second.
pub fn repeat_delay_ms(setting: u32) -> u64 {
    (u64::from(setting.min(3)) + 1) * 250
}

/// Windows keyboard speed setting (0..31) to milliseconds between
/// auto-repeats: 0 is about 2.5 repeats per second, 31 about 30.
pub fn repeat_interval_ms(setting: u32) -> u64 {
    let rate = 2.5 + 27.5 * f64::from(setting.min(31)) / 31.0;
    (1000.0 / rate).round() as u64
}

/// `(delay, interval)` in ms of the keyboard auto-repeat, from Windows when
/// it answers, else the defaults. Only Windows has JAWS, and only Windows
/// exposes the setting this cheaply, so nothing else is asked.
#[cfg(windows)]
pub fn os_repeat_timing() -> (u64, u64) {
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        SystemParametersInfoW, SPI_GETKEYBOARDDELAY, SPI_GETKEYBOARDSPEED,
    };
    let mut delay: u32 = 0;
    let mut speed: u32 = 0;
    // SAFETY: each call writes exactly one u32 into the local it is handed
    // and touches nothing else; the locals outlive the calls.
    let got_delay = unsafe {
        SystemParametersInfoW(SPI_GETKEYBOARDDELAY, 0, (&mut delay as *mut u32).cast(), 0)
    } != 0;
    let got_speed = unsafe {
        SystemParametersInfoW(SPI_GETKEYBOARDSPEED, 0, (&mut speed as *mut u32).cast(), 0)
    } != 0;
    (
        if got_delay {
            repeat_delay_ms(delay)
        } else {
            DEFAULT_REPEAT_DELAY_MS
        },
        if got_speed {
            repeat_interval_ms(speed)
        } else {
            DEFAULT_REPEAT_INTERVAL_MS
        },
    )
}

#[cfg(not(windows))]
pub fn os_repeat_timing() -> (u64, u64) {
    (DEFAULT_REPEAT_DELAY_MS, DEFAULT_REPEAT_INTERVAL_MS)
}

/// `pygame.key.get_pressed()` / `get_mods()`: the keys currently held, as
/// the app tracks them from the key events it dispatched, plus the pulse
/// layer that reads a screen reader's re-injected press-and-release train as
/// the hold it stands for (see the module docs).
#[derive(Debug)]
pub struct HeldKeys {
    held: HashSet<Key>,
    mods: Mods,
    delay_ms: u64,
    interval_ms: u64,
    /// Frames the app has clocked. Zero means no frame loop is running, and
    /// then the pulse layer stays out of the way entirely.
    frame: u64,
    now_ms: u64,
    frame_span_ms: u64,
    pulse_until: HashMap<Key, u64>,
    train_start: HashMap<Key, u64>,
    train_repeats: HashMap<Key, u32>,
    pressed_at: HashMap<Key, u64>,
    /// The frame of the last press that came from the released state: the
    /// only kind of press a synthetic pair can begin with.
    pair_frame: HashMap<Key, u64>,
    last_pair_synthetic: HashSet<Key>,
    spacings: Vec<u64>,
}

impl Default for HeldKeys {
    fn default() -> Self {
        let (delay, interval) = os_repeat_timing();
        Self::with_timing(delay, interval)
    }
}

impl HeldKeys {
    /// A tracker with a known repeat delay and interval (tests; the default
    /// asks the operating system).
    pub fn with_timing(repeat_delay_ms: u64, repeat_interval_ms: u64) -> Self {
        Self {
            held: HashSet::new(),
            mods: Mods::NONE,
            delay_ms: repeat_delay_ms,
            interval_ms: repeat_interval_ms,
            frame: 0,
            now_ms: 0,
            frame_span_ms: 0,
            pulse_until: HashMap::new(),
            train_start: HashMap::new(),
            train_repeats: HashMap::new(),
            pressed_at: HashMap::new(),
            pair_frame: HashMap::new(),
            last_pair_synthetic: HashSet::new(),
            spacings: Vec::new(),
        }
    }

    // -- reading ------------------------------------------------------------------

    /// Physically down, or held by a live pulse from a re-injected train.
    pub fn is_pressed(&self, key: Key) -> bool {
        self.held.contains(&key) || self.pulsed(key)
    }

    /// Held only by a pulse, not by SDL's own key state.
    pub fn pulsed(&self, key: Key) -> bool {
        self.pulse_until
            .get(&key)
            .is_some_and(|&until| until > self.now_ms)
    }

    pub fn mods(&self) -> Mods {
        self.mods
    }

    // -- timing -------------------------------------------------------------------

    pub fn repeat_delay_ms(&self) -> u64 {
        self.delay_ms
    }

    pub fn repeat_interval_ms(&self) -> u64 {
        self.interval_ms
    }

    /// The spacing re-injected repeats are actually arriving at, once seen.
    pub fn learned_spacing_ms(&self) -> Option<u64> {
        self.spacings.iter().copied().max()
    }

    /// How long a lone press reads held: to the first auto-repeat, plus grace.
    pub fn fresh_pulse_ms(&self) -> u64 {
        self.delay_ms + FRESH_GRACE_MS
    }

    /// How long each repeat extends the hold: one spacing, plus grace.
    ///
    /// The spacing is the learned one when there is one (never shorter than
    /// the operating system's own rate); before anything is learned it is
    /// the fresh pulse, so the first hold of a session cannot stutter.
    pub fn repeat_pulse_ms(&self) -> u64 {
        match self.learned_spacing_ms() {
            Some(learned) => learned.max(self.interval_ms) + REPEAT_GRACE_MS,
            None => self.fresh_pulse_ms(),
        }
    }

    /// Re-read the operating system's repeat timing (on window focus, so a
    /// player who changed the keyboard settings gets them without a restart).
    pub fn refresh_repeat_timing(&mut self) {
        let (delay, interval) = os_repeat_timing();
        self.delay_ms = delay;
        self.interval_ms = interval;
    }

    // -- feeding ------------------------------------------------------------------

    /// Once per frame from the app's loop, before that frame's events, with
    /// the frame's real duration. This is the clock the pulses run on; until
    /// it has ticked, presses and releases keep their plain meaning.
    pub fn begin_frame(&mut self, dt_seconds: f64) {
        let span = (dt_seconds.max(0.0) * 1000.0).round() as u64;
        self.frame += 1;
        self.frame_span_ms = span;
        self.now_ms += span;
    }

    pub fn press(&mut self, key: Key, mods: Mods) {
        let was_held = !self.held.insert(key);
        self.mods = mods;
        if self.frame > 0 {
            self.pulse_press(key, was_held);
        }
    }

    pub fn release(&mut self, key: Key, mods: Mods) {
        self.held.remove(&key);
        self.mods = mods;
        if self.frame > 0 {
            self.pulse_release(key);
        }
    }

    /// Forget everything held, physical and pulsed.
    pub fn clear(&mut self) {
        self.held.clear();
        self.mods = Mods::NONE;
        self.clear_pulses();
    }

    /// Forget the pulses only (the app calls this when the state stack
    /// changes, so a screen never inherits the last screen's held keys); what
    /// the tracker has learned about the repeat spacing survives.
    pub fn clear_pulses(&mut self) {
        self.pulse_until.clear();
        self.train_start.clear();
        self.train_repeats.clear();
    }

    fn pulse_press(&mut self, key: Key, was_held: bool) {
        let now = self.now_ms;
        let until = self.pulse_until.get(&key).copied().unwrap_or(0);
        let repeat_after = self.delay_ms.saturating_sub(REPEAT_EARLY_TOLERANCE_MS);
        let repeating = until > now
            && self
                .train_start
                .get(&key)
                .is_some_and(|&start| now.saturating_sub(start) >= repeat_after);
        let window = if repeating {
            let repeats = self.train_repeats.entry(key).or_insert(0);
            *repeats += 1;
            let repeats = *repeats;
            // The first repeat sits at the delay, not the rate; from the
            // second on, the gap to the previous pair is the real spacing --
            // but only synthetic pairs teach it, a finger's rhythm never does.
            let previous = self.pressed_at.get(&key).copied();
            if repeats >= 2 && self.last_pair_synthetic.contains(&key) {
                if let Some(previous) = previous {
                    let spacing = now.saturating_sub(previous);
                    if spacing < repeat_after {
                        self.learn_spacing(spacing);
                    }
                }
            }
            self.repeat_pulse_ms()
        } else {
            self.train_start.insert(key, now);
            self.train_repeats.insert(key, 0);
            self.fresh_pulse_ms()
        };
        self.pulse_until.insert(key, until.max(now + window));
        self.pressed_at.insert(key, now);
        self.last_pair_synthetic.remove(&key);
        // Only a press from the released state can begin a synthetic pair:
        // SDL's own auto-repeat arrives as more presses of a key that is
        // already down, and a finger lifting in the same frame as one of
        // those is a real release.
        if was_held {
            self.pair_frame.remove(&key);
        } else {
            self.pair_frame.insert(key, self.frame);
        }
    }

    fn pulse_release(&mut self, key: Key) {
        let synthetic = self.pair_frame.get(&key) == Some(&self.frame)
            && self.frame_span_ms <= SYNTHETIC_FRAME_MAX_MS;
        if synthetic {
            self.last_pair_synthetic.insert(key);
            return;
        }
        self.pulse_until.remove(&key);
        self.train_start.remove(&key);
        self.train_repeats.remove(&key);
    }

    fn learn_spacing(&mut self, spacing_ms: u64) {
        self.spacings.push(spacing_ms);
        if self.spacings.len() > LEARNED_SPACINGS {
            let excess = self.spacings.len() - LEARNED_SPACINGS;
            self.spacings.drain(..excess);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const DT: f64 = 1.0 / 60.0;
    const FRAME_MS: u64 = 17; // what a 60 fps frame rounds to
    const DELAY_MS: u64 = 500;
    const INTERVAL_MS: u64 = 33;
    /// The owner's JAWS log, 2026-08-24: first repeat at 512 ms, then these.
    const JAWS_FIRST_REPEAT_MS: u64 = 512;
    const JAWS_SPACINGS_MS: [u64; 14] = [
        263, 245, 269, 271, 242, 251, 270, 250, 244, 271, 249, 242, 254, 250,
    ];

    /// Advance the tracker frame by frame with a fake clock.
    struct Sim {
        keys: HeldKeys,
        now_ms: u64,
    }

    impl Sim {
        fn new() -> Self {
            let mut keys = HeldKeys::with_timing(DELAY_MS, INTERVAL_MS);
            keys.begin_frame(DT);
            Self { keys, now_ms: 0 }
        }

        fn frame(&mut self) {
            self.frame_of(DT);
        }

        fn frame_of(&mut self, dt: f64) {
            self.keys.begin_frame(dt);
            self.now_ms += (dt * 1000.0).round() as u64;
        }

        fn pair(&mut self, key: Key) {
            self.keys.press(key, Mods::NONE);
            self.keys.release(key, Mods::NONE);
        }

        /// When a screen reader re-sends pairs for a key held `seconds`.
        fn pair_times(&self, seconds: f64, first_repeat: u64, spacings: &[u64]) -> Vec<u64> {
            let start = self.now_ms;
            let end = start + (seconds * 1000.0) as u64;
            let mut times = vec![start, start + first_repeat];
            let mut i = 0;
            while *times.last().unwrap() < end {
                times.push(times.last().unwrap() + spacings[i % spacings.len()]);
                i += 1;
            }
            times.retain(|&t| t < end);
            times
        }

        /// Deliver the pairs for a hold, frame by frame; return each frame's
        /// reading from the first pair on.
        fn screen_reader_hold(
            &mut self,
            key: Key,
            seconds: f64,
            first_repeat: u64,
            spacings: &[u64],
        ) -> Vec<bool> {
            let mut pairs = self.pair_times(seconds, first_repeat, spacings);
            let end = self.now_ms + (seconds * 1000.0) as u64;
            let mut readings = Vec::new();
            while self.now_ms < end {
                self.frame();
                if pairs.first().is_some_and(|&t| self.now_ms >= t) {
                    pairs.remove(0);
                    self.pair(key);
                }
                readings.push(self.keys.is_pressed(key));
            }
            readings
        }

        fn ms_until_released(&mut self, key: Key) -> u64 {
            let start = self.now_ms;
            while self.keys.is_pressed(key) {
                self.frame();
                assert!(
                    self.now_ms - start <= 2000,
                    "still held {} ms after the pairs stopped",
                    self.now_ms - start
                );
            }
            self.now_ms - start
        }
    }

    fn first_gap(readings: &[bool]) -> Option<usize> {
        readings.iter().position(|&held| !held)
    }

    #[test]
    fn physical_hold_still_reads_straight_from_the_key_state() {
        let mut sim = Sim::new();
        sim.keys.press(Key::Up, Mods::NONE);
        assert!(sim.keys.is_pressed(Key::Up));
        assert!(!sim.keys.is_pressed(Key::Down));
        for _ in 0..5 {
            sim.frame();
            assert!(sim.keys.is_pressed(Key::Up));
        }
        sim.keys.release(Key::Up, Mods::NONE);
        assert!(!sim.keys.is_pressed(Key::Up));
    }

    #[test]
    fn without_a_frame_clock_the_pulse_layer_is_inert() {
        // The harness and the tests feed keys straight in; a tap through
        // press and release must keep meaning exactly that.
        let mut keys = HeldKeys::with_timing(DELAY_MS, INTERVAL_MS);
        keys.press(Key::Up, Mods::NONE);
        assert!(keys.is_pressed(Key::Up));
        keys.release(Key::Up, Mods::NONE);
        assert!(!keys.is_pressed(Key::Up));
        assert!(!keys.pulsed(Key::Up));
    }

    #[test]
    fn a_re_injected_pair_reads_held_until_the_first_repeat_would_come() {
        let mut sim = Sim::new();
        sim.pair(Key::Up);
        assert!(sim.keys.is_pressed(Key::Up));
        assert!(sim.keys.pulsed(Key::Up));
        let pressed_at = sim.now_ms;
        while sim.now_ms < pressed_at + DELAY_MS {
            sim.frame();
            assert!(
                sim.keys.is_pressed(Key::Up),
                "lapsed {} ms after the press",
                sim.now_ms - pressed_at
            );
        }
        while sim.now_ms < pressed_at + DELAY_MS + FRESH_GRACE_MS + FRAME_MS {
            sim.frame();
        }
        assert!(!sim.keys.is_pressed(Key::Up));
    }

    #[test]
    fn the_owners_jaws_train_is_one_continuous_hold_from_the_first_pair() {
        let mut sim = Sim::new();
        let readings =
            sim.screen_reader_hold(Key::Up, 4.0, JAWS_FIRST_REPEAT_MS, &JAWS_SPACINGS_MS);
        assert_eq!(first_gap(&readings), None, "the hold broke");
        // Letting go reads late by one spacing plus grace: the price of a
        // screen reader that only re-sends the key four times a second.
        let max_spacing = *JAWS_SPACINGS_MS.iter().max().unwrap();
        let lag = sim.ms_until_released(Key::Up);
        assert!(lag <= max_spacing + REPEAT_GRACE_MS + 2 * FRAME_MS, "{lag}");
        // The fake clock lands pairs on frame boundaries, so the learned
        // spacing can sit one frame off the nominal value.
        let learned = sim.keys.learned_spacing_ms().expect("learned");
        assert!(learned.abs_diff(max_spacing) <= FRAME_MS, "{learned}");
        // The next hold, on another key, starts with the spacing known.
        let readings =
            sim.screen_reader_hold(Key::Down, 3.0, JAWS_FIRST_REPEAT_MS, &JAWS_SPACINGS_MS);
        assert_eq!(first_gap(&readings), None);
        let lag = sim.ms_until_released(Key::Down);
        assert!(lag <= max_spacing + REPEAT_GRACE_MS + 2 * FRAME_MS, "{lag}");
    }

    #[test]
    fn a_fast_repeat_train_lapses_quickly_once_its_spacing_is_learned() {
        let mut sim = Sim::new();
        let readings = sim.screen_reader_hold(Key::Up, 2.0, DELAY_MS, &[INTERVAL_MS]);
        assert_eq!(first_gap(&readings), None);
        let learned = sim.keys.learned_spacing_ms().expect("learned");
        assert!(learned.abs_diff(INTERVAL_MS) <= FRAME_MS, "{learned}");
        let lag = sim.ms_until_released(Key::Up);
        assert!(lag <= INTERVAL_MS + REPEAT_GRACE_MS + 3 * FRAME_MS, "{lag}");
        // Once a hold has lapsed, a fresh press earns the full fresh pulse.
        sim.pair(Key::Up);
        let pressed_at = sim.now_ms;
        while sim.now_ms < pressed_at + DELAY_MS {
            sim.frame();
            assert!(sim.keys.is_pressed(Key::Up));
        }
    }

    #[test]
    fn a_fingers_rhythm_never_teaches_the_repeat_spacing() {
        // Real taps, released a few frames later, at a steady 200 ms.
        let mut sim = Sim::new();
        for _ in 0..6 {
            sim.keys.press(Key::Down, Mods::NONE);
            for _ in 0..3 {
                sim.frame();
            }
            sim.keys.release(Key::Down, Mods::NONE);
            assert!(!sim.keys.is_pressed(Key::Down));
            for _ in 0..8 {
                sim.frame();
            }
        }
        assert_eq!(sim.keys.learned_spacing_ms(), None);
        assert_eq!(sim.keys.repeat_pulse_ms(), sim.keys.fresh_pulse_ms());
    }

    #[test]
    fn sdl_auto_repeat_of_a_held_key_never_makes_a_pair() {
        // The keyboard's own repeat arrives as more presses of a key that is
        // already down; the finger lifting in the same frame as one of those
        // is a real release, not a screen reader's pair.
        let mut sim = Sim::new();
        sim.keys.press(Key::Up, Mods::NONE);
        for _ in 0..40 {
            sim.frame();
            sim.keys.press(Key::Up, Mods::NONE); // SDL repeat, every frame
            assert!(sim.keys.is_pressed(Key::Up));
        }
        sim.frame();
        sim.keys.press(Key::Up, Mods::NONE); // one more repeat...
        sim.keys.release(Key::Up, Mods::NONE); // ...and the finger lifts
        assert!(!sim.keys.is_pressed(Key::Up));
        for _ in 0..3 {
            sim.frame();
            assert!(!sim.keys.is_pressed(Key::Up));
        }
        assert_eq!(sim.keys.learned_spacing_ms(), None);
    }

    #[test]
    fn a_pair_that_lands_after_a_hitch_is_not_a_hold() {
        // A whole real tap can arrive in one batch after a long frame; the
        // honest answer is "not held", not a half-second of brake.
        let mut sim = Sim::new();
        sim.frame_of((SYNTHETIC_FRAME_MAX_MS + 100) as f64 / 1000.0);
        sim.pair(Key::Down);
        assert!(!sim.keys.is_pressed(Key::Down));
    }

    #[test]
    fn a_second_tap_before_the_delay_is_a_fresh_press_not_a_repeat() {
        let mut sim = Sim::new();
        sim.pair(Key::Down);
        for _ in 0..9 {
            sim.frame(); // about 150 ms later: a double tap
        }
        sim.pair(Key::Down);
        let second_at = sim.now_ms;
        while sim.now_ms < second_at + DELAY_MS {
            sim.frame();
            assert!(sim.keys.is_pressed(Key::Down));
        }
    }

    #[test]
    fn each_key_keeps_its_own_hold() {
        let mut sim = Sim::new();
        sim.pair(Key::Up);
        sim.frame();
        sim.pair(Key::Left);
        assert!(sim.keys.is_pressed(Key::Up) && sim.keys.is_pressed(Key::Left));
        assert!(!sim.keys.is_pressed(Key::Right));
        sim.frame();
        sim.keys.release(Key::Up, Mods::NONE); // a later release: the finger
        assert!(!sim.keys.is_pressed(Key::Up));
        assert!(sim.keys.is_pressed(Key::Left));
    }

    #[test]
    fn clearing_the_pulses_keeps_the_learning_and_clear_drops_it_all() {
        let mut sim = Sim::new();
        sim.screen_reader_hold(Key::Up, 1.5, JAWS_FIRST_REPEAT_MS, &JAWS_SPACINGS_MS);
        assert!(sim.keys.learned_spacing_ms().is_some());
        sim.keys.clear_pulses();
        assert!(!sim.keys.is_pressed(Key::Up));
        assert!(sim.keys.learned_spacing_ms().is_some());
        sim.pair(Key::Up);
        sim.keys.press(Key::B, Mods::NONE);
        sim.keys.clear();
        assert!(!sim.keys.is_pressed(Key::Up));
        assert!(!sim.keys.is_pressed(Key::B));
        assert_eq!(sim.keys.mods(), Mods::NONE);
    }

    #[test]
    fn windows_repeat_settings_decode_to_the_documented_timing() {
        assert_eq!(repeat_delay_ms(0), 250);
        assert_eq!(repeat_delay_ms(1), 500);
        assert_eq!(repeat_delay_ms(3), 1000);
        assert_eq!(repeat_delay_ms(99), 1000); // clamped, never a runaway pulse
        assert_eq!(repeat_interval_ms(31), 33);
        assert_eq!(repeat_interval_ms(0), 400);
        let keys = HeldKeys::with_timing(1000, 400);
        assert_eq!(keys.fresh_pulse_ms(), 1000 + FRESH_GRACE_MS);
        assert_eq!(keys.repeat_pulse_ms(), keys.fresh_pulse_ms()); // nothing learned yet
    }
}
