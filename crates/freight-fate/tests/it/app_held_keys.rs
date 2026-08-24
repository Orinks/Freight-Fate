//! The held-key tracker: driving must read a held arrow under JAWS.
//!
//! Ported from `tests/test_held_keys.py`.
//!
//! JAWS swallows the physical arrow key and re-sends it to the game as an
//! instant press-and-release pair: one at the press, one at the Windows
//! repeat delay, then one per repeat at whatever spacing its script manages
//! (about 250 ms on the owner's machine, measured 2026-08-24, not the 33 ms
//! Windows rate). Driving polls whether a key is held, and never sees it.
//! The tracker turns the train of pairs back into one hold, without changing
//! what the physical keyboard path (no screen reader, NVDA) reads.
//!
//! Python's tracker sat beside SDL's own `key.get_pressed()`, which the tests
//! there faked; this port has one store, so the physical path is arranged for
//! real -- a press with no release is a finger still on the key.

use freight_fate::app::held_keys::{
    repeat_delay_ms, repeat_interval_ms, HeldKeys, FRESH_GRACE_MS, REPEAT_GRACE_MS,
    SYNTHETIC_FRAME_MAX_MS,
};
use freight_fate::playtest::harness::{key_event, PlaytestHarness, StartDelivery};
use freight_fate::states::base::{Key, Mods};

const FRAME_MS: u32 = 16; // 60 frames per second, as the game runs
const DELAY_MS: u32 = 500; // the Windows default auto-repeat delay
const INTERVAL_MS: u32 = 33; // ...and rate (about 30 per second)
                             // The owner's JAWS log, 2026-08-24: first repeat at 512 ms, then these.
const JAWS_FIRST_REPEAT_MS: u32 = 512;
const JAWS_SPACINGS_MS: [u32; 14] = [
    263, 245, 269, 271, 242, 251, 270, 250, 244, 271, 249, 242, 254, 250,
];

/// Advance a tracker frame by frame with a fake clock.
struct Sim<'a> {
    keys: &'a mut HeldKeys,
    now: u32,
}

impl<'a> Sim<'a> {
    fn new(keys: &'a mut HeldKeys) -> Sim<'a> {
        let sim = Sim { keys, now: 1000 };
        sim.keys.begin_frame(sim.now);
        sim
    }

    fn frame(&mut self) {
        self.frame_of(FRAME_MS);
    }

    fn frame_of(&mut self, span_ms: u32) {
        self.now += span_ms;
        self.keys.begin_frame(self.now);
    }

    /// What a screen reader delivers in place of the key: press and release
    /// in the same frame.
    fn pair(&mut self, key: Key) {
        self.keys.press(key, Mods::NONE);
        self.keys.release(key, Mods::NONE);
    }

    fn held(&self, key: Key) -> bool {
        self.keys.is_pressed(key)
    }

    /// When a screen reader re-sends pairs for a key held `seconds`.
    fn pair_times(&self, seconds: f64, first_repeat: u32, spacings: &[u32]) -> Vec<u32> {
        let end = self.now + (seconds * 1000.0) as u32;
        let mut times = vec![self.now, self.now + first_repeat];
        let mut i = 0;
        while *times.last().expect("seeded above") < end {
            times.push(times.last().expect("seeded above") + spacings[i % spacings.len()]);
            i += 1;
        }
        times.retain(|t| *t < end);
        times
    }

    /// Deliver the pairs for a hold, frame by frame; return each frame's held
    /// reading from the first pair on.
    fn screen_reader_hold(
        &mut self,
        key: Key,
        seconds: f64,
        first_repeat: u32,
        spacings: &[u32],
    ) -> Vec<bool> {
        let mut pairs = self.pair_times(seconds, first_repeat, spacings);
        pairs.reverse(); // pop from the back: the next pair due
        let end = self.now + (seconds * 1000.0) as u32;
        let mut readings = Vec::new();
        while self.now < end {
            let due = pairs.last().is_some_and(|next| self.now >= *next);
            if due {
                pairs.pop();
                self.pair(key);
            }
            self.frame();
            readings.push(self.held(key));
        }
        readings
    }

    /// How long after the pairs stop the key still reads held.
    fn ms_until_released(&mut self, key: Key) -> u32 {
        let start = self.now;
        while self.held(key) {
            self.frame();
            assert!(
                self.now - start <= 2000,
                "still held {} ms after the pairs stopped",
                self.now - start
            );
        }
        self.now - start
    }
}

fn tracker() -> HeldKeys {
    HeldKeys::with_repeat_timing(DELAY_MS, INTERVAL_MS)
}

fn first_false(readings: &[bool]) -> Option<usize> {
    readings.iter().position(|held| !held)
}

// -- the physical keyboard, unchanged --------------------------------------------------

#[test]
fn test_a_physical_hold_reads_held_until_the_finger_lifts() {
    let mut keys = tracker();
    let mut sim = Sim::new(&mut keys);
    sim.keys.press(Key::Up, Mods::NONE);
    // Far past any pulse: the raw key state is what answers, as it always did.
    for _ in 0..180 {
        sim.frame();
        assert!(sim.held(Key::Up), "let go at {} ms", sim.now);
    }
    assert!(!sim.held(Key::Down));
    sim.keys.release(Key::Up, Mods::NONE);
    assert!(!sim.held(Key::Up));
}

#[test]
fn test_the_finger_lifting_ends_the_hold_at_once() {
    let mut keys = tracker();
    let mut sim = Sim::new(&mut keys);
    sim.keys.press(Key::Down, Mods::NONE);
    for _ in 0..5 {
        sim.frame();
        assert!(sim.held(Key::Down));
    }
    sim.frame();
    sim.keys.release(Key::Down, Mods::NONE);
    assert!(!sim.held(Key::Down));
}

#[test]
fn test_a_fingers_rhythm_never_teaches_the_repeat_spacing() {
    // Real taps (release in a later frame) at a steady 200 ms: physical
    // keyboards never produce repeat pairs, so nothing is learned from them.
    let mut keys = tracker();
    let mut sim = Sim::new(&mut keys);
    for _ in 0..6 {
        sim.keys.press(Key::Down, Mods::NONE);
        for _ in 0..3 {
            sim.frame();
        }
        sim.keys.release(Key::Down, Mods::NONE);
        assert!(!sim.held(Key::Down));
        for _ in 0..8 {
            sim.frame();
        }
    }
    assert_eq!(sim.keys.learned_spacing_ms(), None);
    assert_eq!(sim.keys.repeat_pulse_ms(), sim.keys.fresh_pulse_ms());
}

// -- the re-injected train --------------------------------------------------------------

#[test]
fn test_a_re_injected_pair_reads_held_until_the_first_repeat_would_come() {
    let mut keys = tracker();
    let mut sim = Sim::new(&mut keys);
    sim.pair(Key::Up);
    assert!(sim.held(Key::Up));
    let pressed_at = sim.now;
    while sim.now < pressed_at + DELAY_MS {
        sim.frame();
        assert!(
            sim.held(Key::Up),
            "lapsed {} ms after the press",
            sim.now - pressed_at
        );
    }
    while sim.now < pressed_at + DELAY_MS + FRESH_GRACE_MS + FRAME_MS {
        sim.frame();
    }
    assert!(!sim.held(Key::Up));
}

#[test]
fn test_the_owners_jaws_train_is_one_continuous_hold_from_the_first_pair() {
    // Replays the measured log: no learned spacing yet, 250 ms repeats.
    let mut keys = tracker();
    let mut sim = Sim::new(&mut keys);
    let readings = sim.screen_reader_hold(Key::Up, 4.0, JAWS_FIRST_REPEAT_MS, &JAWS_SPACINGS_MS);
    assert!(
        first_false(&readings).is_none(),
        "the hold broke at frame {:?} of {}",
        first_false(&readings),
        readings.len()
    );
    // Letting go reads late by one spacing plus grace: the price of a screen
    // reader that only re-sends the key four times a second.
    let slowest = *JAWS_SPACINGS_MS.iter().max().expect("not empty");
    let lag = sim.ms_until_released(Key::Up);
    assert!(lag <= slowest + REPEAT_GRACE_MS + 2 * FRAME_MS, "{lag} ms");
    // The fake clock delivers pairs on frame boundaries, so the learned
    // spacing can sit one frame off the nominal value.
    let learned = sim.keys.learned_spacing_ms().expect("the train taught it");
    assert!(learned.abs_diff(slowest) <= FRAME_MS, "{learned} ms");
    // The next hold, on another key, starts with the spacing already known.
    let readings = sim.screen_reader_hold(Key::Down, 3.0, JAWS_FIRST_REPEAT_MS, &JAWS_SPACINGS_MS);
    assert!(first_false(&readings).is_none(), "{readings:?}");
    let lag = sim.ms_until_released(Key::Down);
    assert!(lag <= slowest + REPEAT_GRACE_MS + 2 * FRAME_MS, "{lag} ms");
}

#[test]
fn test_a_fast_repeat_train_lapses_quickly_once_its_spacing_is_learned() {
    let mut keys = tracker();
    let mut sim = Sim::new(&mut keys);
    let readings = sim.screen_reader_hold(Key::Up, 2.0, DELAY_MS, &[INTERVAL_MS]);
    assert!(
        first_false(&readings).is_none(),
        "the hold broke at frame {:?} of {}",
        first_false(&readings),
        readings.len()
    );
    let learned = sim.keys.learned_spacing_ms().expect("the train taught it");
    assert!(learned.abs_diff(INTERVAL_MS) <= FRAME_MS, "{learned} ms");
    let lag = sim.ms_until_released(Key::Up);
    assert!(
        lag <= INTERVAL_MS + REPEAT_GRACE_MS + 3 * FRAME_MS,
        "{lag} ms"
    );
    // Once a hold has lapsed, a fresh press earns the full fresh pulse again.
    sim.pair(Key::Up);
    let pressed_at = sim.now;
    while sim.now < pressed_at + DELAY_MS {
        sim.frame();
        assert!(sim.held(Key::Up));
    }
}

#[test]
fn test_a_pair_that_lands_after_a_hitch_is_not_a_hold() {
    // A whole real tap can arrive in one batch after a long frame; the honest
    // answer is "not held", not a half-second of brake.
    let mut keys = tracker();
    let mut sim = Sim::new(&mut keys);
    sim.frame_of(SYNTHETIC_FRAME_MAX_MS + 100);
    sim.pair(Key::Down);
    assert!(!sim.held(Key::Down));
}

#[test]
fn test_a_second_tap_before_the_delay_is_a_fresh_press_not_a_repeat() {
    let mut keys = tracker();
    let mut sim = Sim::new(&mut keys);
    sim.pair(Key::Down);
    for _ in 0..9 {
        // about 150 ms later: a double tap
        sim.frame();
    }
    sim.pair(Key::Down);
    let second_at = sim.now;
    while sim.now < second_at + DELAY_MS {
        sim.frame();
        assert!(sim.held(Key::Down));
    }
}

#[test]
fn test_each_key_keeps_its_own_hold() {
    let mut keys = tracker();
    let mut sim = Sim::new(&mut keys);
    sim.pair(Key::Up);
    sim.frame();
    sim.pair(Key::Left);
    assert!(sim.held(Key::Up) && sim.held(Key::Left));
    assert!(!sim.held(Key::Right));
    sim.frame(); // a later release: the finger, not the pair
    sim.keys.release(Key::Up, Mods::NONE);
    assert!(!sim.held(Key::Up));
    assert!(sim.held(Key::Left));
}

#[test]
fn test_clearing_drops_every_pulse_but_keeps_the_learning() {
    let mut keys = tracker();
    let mut sim = Sim::new(&mut keys);
    sim.screen_reader_hold(Key::Up, 1.5, JAWS_FIRST_REPEAT_MS, &JAWS_SPACINGS_MS);
    assert!(sim.keys.learned_spacing_ms().is_some());
    sim.keys.clear_pulses();
    assert!(!sim.held(Key::Up));
    sim.pair(Key::Up);
    assert!(sim.held(Key::Up));
    sim.keys.clear(); // what losing the window does
    assert!(!sim.held(Key::Up));
    assert!(sim.keys.learned_spacing_ms().is_some());
}

#[test]
fn test_windows_repeat_settings_decode_to_the_documented_timing() {
    assert_eq!(repeat_delay_ms(0), 250);
    assert_eq!(repeat_delay_ms(1), 500);
    assert_eq!(repeat_delay_ms(3), 1000);
    assert_eq!(repeat_delay_ms(99), 1000); // clamped, never a runaway pulse
    assert_eq!(repeat_interval_ms(31), 33);
    assert_eq!(repeat_interval_ms(0), 400);
    assert_eq!(repeat_interval_ms(-5), 400);
    let keys = HeldKeys::with_repeat_timing(1000, 400);
    assert_eq!(keys.fresh_pulse_ms(), 1000 + FRESH_GRACE_MS);
    assert_eq!(keys.repeat_pulse_ms(), keys.fresh_pulse_ms()); // nothing learned yet
}

// -- the app around it -------------------------------------------------------------------

#[test]
fn test_without_a_frame_clock_a_press_and_release_is_the_plain_pair_it_always_was() {
    // The playtest harness and the adversarial breaker poke the tracker
    // directly and never begin a frame. Nothing about them may change: a
    // press holds until its release, and the release is obeyed at once.
    let mut keys = tracker();
    keys.press(Key::Up, Mods::NONE);
    assert!(keys.is_pressed(Key::Up));
    keys.release(Key::Up, Mods::NONE);
    assert!(!keys.is_pressed(Key::Up));
    assert_eq!(keys.learned_spacing_ms(), None);
}

#[test]
fn test_a_new_screen_never_inherits_the_last_screens_hold() {
    let mut harness = a_drive("Held Keys Stack");
    harness.app.ctx.input.begin_frame(1000);
    harness.app.ctx.input.press(Key::Up, Mods::NONE);
    harness.app.ctx.input.release(Key::Up, Mods::NONE);
    assert!(harness.app.ctx.input.is_pressed(Key::Up));

    // The pause menu opening is a state push, and it drops the pulse.
    harness.with_drive(|drive, ctx| drive.handle_key_event(ctx, &key_event(Key::Escape, None)));
    assert!(!harness.app.ctx.input.is_pressed(Key::Up));
}

#[test]
fn test_driving_reads_a_jaws_held_accelerator_as_steady_throttle() {
    // End to end, at the measured JAWS cadence: the pairs for a held Up
    // arrow drive the truck, the throttle never stutters, and it comes off
    // within a second of the pairs stopping.
    let mut harness = a_drive("Held Keys Drive");
    harness.with_drive(|drive, ctx| {
        // `driving_feature_helpers.release_air_brakes`: off the spring
        // brakes, or the throttle has nothing to pull against.
        drive.truck_mut().set_air_ready(false);
        drive.handle_key_event(ctx, &key_event(Key::E, None)); // engine on
    });
    assert_eq!(harness.with_drive(|drive, _| drive.truck().throttle), 0.0);

    let mut now = 1000u32;
    harness.app.ctx.input.begin_frame(now);
    let end = now + 4000;
    let mut pairs = vec![now, now + JAWS_FIRST_REPEAT_MS];
    let mut i = 0;
    while *pairs.last().expect("seeded") < end {
        pairs.push(pairs.last().expect("seeded") + JAWS_SPACINGS_MS[i % JAWS_SPACINGS_MS.len()]);
        i += 1;
    }
    pairs.retain(|t| *t < end);
    pairs.reverse();

    let mut reached_full = false;
    let mut lowest_after_full = 1.0f64;
    while now < end {
        if pairs.last().is_some_and(|next| now >= *next) {
            pairs.pop();
            harness.app.ctx.input.press(Key::Up, Mods::NONE);
            harness.app.ctx.input.release(Key::Up, Mods::NONE);
        }
        now += FRAME_MS;
        harness.app.ctx.input.begin_frame(now);
        harness.advance_clock(f64::from(FRAME_MS) / 1000.0);
        harness.with_drive(|drive, ctx| drive.update_frame(ctx, f64::from(FRAME_MS) / 1000.0));
        let throttle = harness.with_drive(|drive, _| drive.truck().throttle);
        if throttle > 0.95 {
            reached_full = true;
        } else if reached_full {
            lowest_after_full = lowest_after_full.min(throttle);
        }
    }
    assert!(reached_full, "the throttle never came up");
    assert!(
        lowest_after_full >= 0.9,
        "throttle stuttered down to {lowest_after_full:.2}"
    );

    // The finger lifts: the pairs stop, and the throttle comes off.
    for _ in 0..60 {
        now += FRAME_MS;
        harness.app.ctx.input.begin_frame(now);
        harness.advance_clock(f64::from(FRAME_MS) / 1000.0);
        harness.with_drive(|drive, ctx| drive.update_frame(ctx, f64::from(FRAME_MS) / 1000.0));
    }
    assert_eq!(harness.with_drive(|drive, _| drive.truck().throttle), 0.0);
}

/// `start_drive(app)` plus `quiet_trip(driving)`: a loaded delivery on an
/// empty road under a clear sky, with the walkthrough already finished.
fn a_drive(name: &str) -> PlaytestHarness {
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
        drive.trip.weather.current = ff_core::sim::weather::WeatherKind::Clear;
    });
    harness.clear_speech();
    harness
}
