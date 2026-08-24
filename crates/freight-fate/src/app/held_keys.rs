//! Held keys as the driving loop should see them, screen reader or not
//! (`freight_fate/held_keys.py`).
//!
//! Driving reads the pedals and the wheel by polling: is Up down right now?
//! [`HeldKeys`] answers from the key events the app dispatched, and with no
//! screen reader, or with NVDA, that is the physical keyboard: a held key
//! reads held until the finger lifts.
//!
//! JAWS is different. It binds the arrow keys to its own scripts in every
//! application, so its keyboard hook swallows the physical press, runs the
//! script, and re-sends the key to the application as a synthetic
//! press-and-release pair. The game sees a tap that lasts zero frames, which
//! a poll never catches: menus react to the press event and work, driving
//! polls and does nothing until the player passes one key through with JAWS
//! Key+3. Holding the key does not help by itself, but the keyboard's
//! auto-repeat still runs underneath; every repeat goes through the same hook
//! and arrives as another press-and-release pair. Measured on the owner's
//! JAWS machine (2026-08-24): the first repeat lands at the Windows repeat
//! delay (512 ms), and the rest at about 250 ms apart -- not the 33 ms
//! Windows rate, because JAWS's script takes that long per key and the
//! repeats queue behind it.
//!
//! This tracker turns that train back into a hold. Every press starts a
//! pulse: a fresh press gets one long enough to reach the first auto-repeat
//! (the operating system's delay plus grace); a repeat gets one just past the
//! spacing the repeats are actually arriving at, which the tracker learns
//! from the pairs themselves (second repeat onward, synthetic pairs only) and
//! keeps for the rest of the session. Until it has learned that spacing,
//! repeats get the fresh pulse too, so the very first hold never stutters. A
//! release that lands in the same frame as its press (or the next one) is
//! synthetic -- nobody taps a key inside one frame -- and leaves the pulse
//! alone; a release any later is the player's finger and ends it. A key reads
//! as held when the raw key state says so OR a pulse is alive, so the
//! physical-keyboard path is exactly what it always was and the re-injected
//! path reads as a hold that lapses one learned spacing plus grace after the
//! last pair.
//!
//! Two honest limits. A screen reader that re-injects keys never shows the
//! game how long a tap lasted, so under JAWS a tap reads as a hold for the
//! repeat delay (half a second at the Windows default), letting go reads
//! about a third of a second late, and a gesture built on tap length cannot
//! be seen. And the game cannot tell whether such a screen reader is running,
//! so the pulse logic is always on; on the physical path it only ever adds a
//! hold when a whole press-and-release arrives inside one short frame, which
//! a finger cannot do.
//!
//! # The clock, and why a harness never sees a pulse
//!
//! Python kept the tracker beside SDL's own `key.get_pressed()`; this port
//! has no second source, so the raw held set and the pulses live in the same
//! struct. The pulses only run once something has called [`HeldKeys::begin_frame`]
//! -- the app loop does, once per frame. The playtest harness and the
//! adversarial breaker press and release keys straight onto the tracker with
//! no frame clock at all, and for them `press`/`release` stay exactly what
//! they always were: an immediate set and an immediate clear.

use std::collections::{HashMap, HashSet};

use crate::states::base::{Key, Mods};

/// Fallbacks when the operating system will not say: the Windows defaults
/// (delay setting 1 of 0..3 is 500 ms; rate setting 31 of 0..31 is about 30
/// repeats per second).
pub const DEFAULT_REPEAT_DELAY_MS: u32 = 500;
pub const DEFAULT_REPEAT_INTERVAL_MS: u32 = 33;

/// Grace on top of the measured timing. The fresh-press pulse has to outlast
/// the repeat delay plus the screen reader's script latency and a frame of
/// batching; the per-repeat pulse has to outlast one spacing plus jitter
/// (about 30 ms measured) and a frame, and it is how long after the finger
/// lifts the key still reads held, so it stays short.
pub const FRESH_GRACE_MS: u32 = 150;
pub const REPEAT_GRACE_MS: u32 = 100;

/// A release this soon after its press is synthetic: the same frame, or the
/// next one at 60 frames per second. The fastest finger tap is far longer.
pub const SYNTHETIC_GAP_MS: u32 = 25;

/// ...but only when the frame was a normal one. After a long hitch a whole
/// real tap can land in one batch, and then the honest answer is "not held",
/// never a half-second hold. A re-injected pair dropped this way costs
/// nothing: the next repeat pair re-establishes the hold a frame later.
pub const SYNTHETIC_FRAME_MAX_MS: u32 = 40;

/// A press this soon after its pulse train began cannot be the operating
/// system's first auto-repeat (which never fires early), so it is a new tap
/// of the same key and earns a fresh full pulse.
pub const REPEAT_EARLY_TOLERANCE_MS: u32 = 60;

/// The learned repeat spacing is the largest of this many recent spacings, so
/// one slow script run widens the window at once and a run of quick ones
/// narrows it again only once it has aged out.
pub const LEARNED_SPACINGS: usize = 8;

/// Windows keyboard delay setting (0..3) to milliseconds before the first
/// auto-repeat: 250 ms per step, so 0 is 250 ms and 3 is a second.
pub fn repeat_delay_ms(setting: i32) -> u32 {
    (setting.clamp(0, 3) as u32 + 1) * 250
}

/// Windows keyboard speed setting (0..31) to milliseconds between
/// auto-repeats: 0 is about 2.5 repeats per second, 31 about 30.
pub fn repeat_interval_ms(setting: i32) -> u32 {
    let rate = 2.5 + 27.5 * f64::from(setting.clamp(0, 31)) / 31.0;
    (1000.0 / rate).round() as u32
}

/// `(delay, interval)` in ms of the keyboard auto-repeat, from Windows when
/// it answers, else the defaults. Only Windows has JAWS, and only Windows
/// exposes the setting this cheaply, so nothing else is asked.
#[cfg(windows)]
pub fn os_repeat_timing() -> (u32, u32) {
    // Declared here rather than through windows-sys so the crate's feature
    // set does not grow for two calls (as `online_activation` does).
    #[link(name = "user32")]
    extern "system" {
        fn SystemParametersInfoW(
            action: u32,
            param: u32,
            pv: *mut core::ffi::c_void,
            wini: u32,
        ) -> i32;
    }
    const SPI_GETKEYBOARDDELAY: u32 = 0x0016;
    const SPI_GETKEYBOARDSPEED: u32 = 0x000A;

    let mut delay: u32 = 0;
    let mut speed: u32 = 0;
    // SAFETY: both queries write exactly one DWORD into the buffer handed to
    // them and touch nothing else; a failure leaves the buffer alone and is
    // caught by the returned flag.
    let (got_delay, got_speed) = unsafe {
        (
            SystemParametersInfoW(
                SPI_GETKEYBOARDDELAY,
                0,
                std::ptr::addr_of_mut!(delay).cast(),
                0,
            ),
            SystemParametersInfoW(
                SPI_GETKEYBOARDSPEED,
                0,
                std::ptr::addr_of_mut!(speed).cast(),
                0,
            ),
        )
    };
    (
        if got_delay != 0 {
            repeat_delay_ms(delay as i32)
        } else {
            DEFAULT_REPEAT_DELAY_MS
        },
        if got_speed != 0 {
            repeat_interval_ms(speed as i32)
        } else {
            DEFAULT_REPEAT_INTERVAL_MS
        },
    )
}

#[cfg(not(windows))]
pub fn os_repeat_timing() -> (u32, u32) {
    (DEFAULT_REPEAT_DELAY_MS, DEFAULT_REPEAT_INTERVAL_MS)
}

/// `pygame.key.get_pressed()` / `get_mods()`: the keys currently held, as
/// the app tracks them from the key events it dispatched -- plus the pulses
/// that keep a key held through the press-and-release pairs a screen reader
/// such as JAWS re-sends in place of the physical key (see the module docs).
#[derive(Debug)]
pub struct HeldKeys {
    held: HashSet<Key>,
    mods: Mods,
    delay_ms: u32,
    interval_ms: u32,
    /// The app loop's frame time. `None` until someone begins a frame, and
    /// while it is `None` no pulse is ever started (the harness path).
    now: Option<u32>,
    frame_span_ms: u32,
    pulse_until: HashMap<Key, u32>,
    train_start: HashMap<Key, u32>,
    train_repeats: HashMap<Key, u32>,
    pressed_at: HashMap<Key, u32>,
    last_pair_synthetic: HashMap<Key, bool>,
    spacings: Vec<u32>,
}

impl Default for HeldKeys {
    fn default() -> Self {
        let (delay_ms, interval_ms) = os_repeat_timing();
        HeldKeys::with_repeat_timing(delay_ms, interval_ms)
    }
}

impl HeldKeys {
    /// A tracker with the repeat timing pinned, for tests and the probe.
    pub fn with_repeat_timing(delay_ms: u32, interval_ms: u32) -> Self {
        HeldKeys {
            held: HashSet::new(),
            mods: Mods::NONE,
            delay_ms,
            interval_ms,
            now: None,
            frame_span_ms: 0,
            pulse_until: HashMap::new(),
            train_start: HashMap::new(),
            train_repeats: HashMap::new(),
            pressed_at: HashMap::new(),
            last_pair_synthetic: HashMap::new(),
            spacings: Vec::new(),
        }
    }

    // -- timing ---------------------------------------------------------------------

    pub fn repeat_delay_ms(&self) -> u32 {
        self.delay_ms
    }

    pub fn repeat_interval_ms(&self) -> u32 {
        self.interval_ms
    }

    /// The spacing re-injected repeats are actually arriving at, once seen.
    pub fn learned_spacing_ms(&self) -> Option<u32> {
        self.spacings.iter().copied().max()
    }

    /// How long a lone press reads held: to the first auto-repeat, plus grace.
    pub fn fresh_pulse_ms(&self) -> u32 {
        self.delay_ms + FRESH_GRACE_MS
    }

    /// How long each repeat extends the hold: one spacing, plus grace.
    ///
    /// The spacing is the learned one when there is one (never shorter than
    /// the operating system's own rate); before anything is learned it is the
    /// fresh pulse, so the first hold of a session cannot stutter.
    pub fn repeat_pulse_ms(&self) -> u32 {
        match self.learned_spacing_ms() {
            None => self.fresh_pulse_ms(),
            Some(learned) => learned.max(self.interval_ms) + REPEAT_GRACE_MS,
        }
    }

    /// Re-read the operating system's repeat timing (on window focus, so a
    /// player who changed the keyboard settings gets them without a restart).
    pub fn refresh_repeat_timing(&mut self) {
        let (delay_ms, interval_ms) = os_repeat_timing();
        self.delay_ms = delay_ms;
        self.interval_ms = interval_ms;
    }

    // -- feeding --------------------------------------------------------------------

    /// Start a frame at `now_ms`. The app loop calls this before it hands the
    /// frame's events over; until it has, presses and releases are the plain
    /// set-and-clear they were before pulses existed.
    pub fn begin_frame(&mut self, now_ms: u32) {
        self.frame_span_ms = match self.now {
            Some(previous) => now_ms.saturating_sub(previous),
            None => 0,
        };
        self.now = Some(now_ms);
        self.prune_pulses(now_ms);
    }

    pub fn is_pressed(&self, key: Key) -> bool {
        self.held.contains(&key) || self.pulse_alive(key)
    }

    pub fn mods(&self) -> Mods {
        self.mods
    }

    pub fn press(&mut self, key: Key, mods: Mods) {
        self.held.insert(key);
        self.mods = mods;
        if let Some(now) = self.now {
            self.note_press(key, now);
        }
    }

    pub fn release(&mut self, key: Key, mods: Mods) {
        self.held.remove(&key);
        self.mods = mods;
        if let Some(now) = self.now {
            self.note_release(key, now);
        }
    }

    /// Forget every pulse, keeping the raw key state and what has been
    /// learned about the repeat spacing. The app calls this when the state
    /// stack changes, so a screen never inherits the last screen's held keys.
    pub fn clear_pulses(&mut self) {
        self.pulse_until.clear();
        self.train_start.clear();
        self.train_repeats.clear();
    }

    /// Everything down: the raw key state, the modifiers, and the pulses.
    /// The app calls this when the window loses focus, where SDL releases
    /// every key, so alt-tabbing away never leaves a pedal down.
    pub fn clear(&mut self) {
        self.held.clear();
        self.mods = Mods::NONE;
        self.clear_pulses();
    }

    // -- pulses ---------------------------------------------------------------------

    fn pulse_alive(&self, key: Key) -> bool {
        match (self.now, self.pulse_until.get(&key)) {
            (Some(now), Some(&until)) => until > now,
            _ => false,
        }
    }

    fn prune_pulses(&mut self, now: u32) {
        let dead: Vec<Key> = self
            .pulse_until
            .iter()
            .filter(|(_, &until)| until <= now)
            .map(|(key, _)| *key)
            .collect();
        for key in dead {
            self.pulse_until.remove(&key);
            self.train_start.remove(&key);
            self.train_repeats.remove(&key);
        }
    }

    fn note_press(&mut self, key: Key, now: u32) {
        let until = self.pulse_until.get(&key).copied().unwrap_or(0);
        // The window a repeat cannot land before: the first auto-repeat
        // never fires early, so anything sooner is a fresh tap.
        let earliest_repeat = self.delay_ms.saturating_sub(REPEAT_EARLY_TOLERANCE_MS);
        let repeating = until > now
            && self
                .train_start
                .get(&key)
                .is_some_and(|&start| now.saturating_sub(start) >= earliest_repeat);
        let window = if repeating {
            let repeats = self.train_repeats.entry(key).or_insert(0);
            *repeats += 1;
            let repeats = *repeats;
            // The first repeat sits at the delay, not the rate; from the
            // second on, the gap to the previous pair is the real spacing --
            // but only synthetic pairs teach it, a finger's rhythm never does.
            let previous = self.pressed_at.get(&key).copied();
            if let Some(previous) = previous {
                let spacing = now.saturating_sub(previous);
                if repeats >= 2
                    && spacing < earliest_repeat
                    && self.last_pair_synthetic.get(&key).copied().unwrap_or(false)
                {
                    self.learn_spacing(spacing);
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
        self.last_pair_synthetic.insert(key, false);
    }

    fn note_release(&mut self, key: Key, now: u32) {
        let synthetic = self
            .pressed_at
            .get(&key)
            .is_some_and(|&pressed_at| now.saturating_sub(pressed_at) <= SYNTHETIC_GAP_MS)
            && self.frame_span_ms <= SYNTHETIC_FRAME_MAX_MS;
        if synthetic {
            self.last_pair_synthetic.insert(key, true);
            return;
        }
        self.pulse_until.remove(&key);
        self.train_start.remove(&key);
        self.train_repeats.remove(&key);
    }

    fn learn_spacing(&mut self, spacing_ms: u32) {
        self.spacings.push(spacing_ms);
        if self.spacings.len() > LEARNED_SPACINGS {
            let excess = self.spacings.len() - LEARNED_SPACINGS;
            self.spacings.drain(..excess);
        }
    }
}
