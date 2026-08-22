//! Latching pedals: double-tap-and-hold keeps a pedal held hands-free.
//!
//! A free input-accessibility accommodation (owner design, playtest
//! 2026-07-15): some players cannot keep a key held down through a long pull
//! or a steady descent snub, and pumping taps tires everyone's fingers
//! eventually. The latched accelerator is the old hand-throttle knob, a real
//! cab control; a latched service brake on a long grade cooks the drums
//! exactly like the brake-fire physics says it should.
//!
//! The gesture lives on the pedal keys themselves, no chord to learn. A bare
//! double-tap would false-trigger on feathering (players pump the throttle in
//! taps), so the catch is DOUBLE-TAP-AND-HOLD: tap, then press again and keep
//! holding about half a second. The caller plays a catch click (its own
//! sound, distinct from the gear click) and speaks the state both ways.
//! Release is any fresh press of the same key, which returns the pedal to the
//! hand; the caller also force-releases on the opposite pedal and on safety
//! overrides (hazards, emergency braking, the overspeed alarm).
//!
//! The machine is polled with the pedal's held state each frame, so it works
//! identically for keyboard keys and anything mapped onto them.
//!
//! Port of `freight_fate/sim/pedal_latch.py`.

pub const TAP_MAX_S: f64 = 0.35; // a first press longer than this is driving, not a gesture
pub const GAP_MAX_S: f64 = 0.35; // tap release to second press; longer and the tap expires
pub const CATCH_HOLD_S: f64 = 0.5; // the second press must hold this long to catch

/// A transition the caller clicks and speaks.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LatchEvent {
    /// The catch: the pedal is now held hands-free.
    Latched,
    /// A fresh press of the same key returned the pedal to the hand.
    Released,
}

impl LatchEvent {
    /// The Python string the machine returned: `"latched"` / `"released"`.
    pub fn as_str(self) -> &'static str {
        match self {
            LatchEvent::Latched => "latched",
            LatchEvent::Released => "released",
        }
    }
}

/// Where the gesture is.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum State {
    /// Pedal up, ready for a gesture.
    Idle,
    /// First press in progress.
    Tap,
    /// Tapped, waiting for the second press.
    Gap,
    /// Second press held, timing toward the catch.
    Arming,
    /// Latched, the catching press not yet released.
    Engaging,
    /// Latched, pedal keys up.
    Resting,
    /// A plain sustained hold; wait for a full release before any gesture.
    Manual,
}

/// One pedal's latch: poll [`update`](PedalLatch::update) every frame with
/// the held state.
///
/// `latched` is the output the caller blends into the pedal's effective
/// state. `update` returns `Some(Latched)` on the catch, `Some(Released)`
/// when a fresh press of the same key returns the pedal to the hand, and
/// `None` otherwise, so the caller can click and speak the transitions.
#[derive(Debug, Clone)]
pub struct PedalLatch {
    pub latched: bool,
    state: State,
    timer: f64,
}

impl Default for PedalLatch {
    fn default() -> Self {
        Self::new()
    }
}

impl PedalLatch {
    pub fn new() -> Self {
        Self {
            latched: false,
            state: State::Idle,
            timer: 0.0,
        }
    }

    pub fn update(&mut self, held: bool, dt: f64) -> Option<LatchEvent> {
        self.timer += dt;
        if self.latched {
            if self.state == State::Engaging {
                if !held {
                    self.state = State::Resting;
                }
            } else if held {
                // resting + a fresh press: back to the hand
                self.latched = false;
                self.state = State::Manual;
                return Some(LatchEvent::Released);
            }
            return None;
        }
        match self.state {
            State::Idle => {
                if held {
                    self.state = State::Tap;
                    self.timer = 0.0;
                }
            }
            State::Tap => {
                if !held {
                    self.state = if self.timer <= TAP_MAX_S {
                        State::Gap
                    } else {
                        State::Idle
                    };
                    self.timer = 0.0;
                } else if self.timer > TAP_MAX_S {
                    self.state = State::Manual;
                }
            }
            State::Gap => {
                if held {
                    self.state = State::Arming;
                    self.timer = 0.0;
                } else if self.timer > GAP_MAX_S {
                    self.state = State::Idle;
                }
            }
            State::Arming => {
                if !held {
                    // Released before the catch: just feathering. The release
                    // counts as a fresh tap so pumping can roll into a catch.
                    self.state = State::Gap;
                    self.timer = 0.0;
                } else if self.timer >= CATCH_HOLD_S {
                    self.latched = true;
                    self.state = State::Engaging;
                    return Some(LatchEvent::Latched);
                }
            }
            State::Manual => {
                if !held {
                    self.state = State::Idle;
                }
            }
            // Unreachable while not latched; kept explicit so the machine
            // reads the same as the Python elif chain.
            State::Engaging | State::Resting => {}
        }
        None
    }

    /// Drop the latch from outside: opposite pedal or a safety override.
    ///
    /// Returns true when there was a latch to drop, so the caller speaks
    /// only real transitions. Lands in `Manual` so a key still physically
    /// held keeps driving the pedal without starting a new gesture.
    pub fn release(&mut self) -> bool {
        if !self.latched {
            return false;
        }
        self.latched = false;
        self.state = State::Manual;
        true
    }
}

#[cfg(test)]
mod tests {
    //! Ported from the pure parts of `tests/test_pedal_latch.py`. The
    //! App-driven cases (the latch on the real pedal keys, the settings
    //! rows, the direction-change gesture ordering) belong to the app-shell
    //! bucket.
    use super::*;

    const DT: f64 = 1.0 / 60.0;

    /// Poll the latch at frame rate; return the events it emitted.
    fn run(latch: &mut PedalLatch, held: bool, seconds: f64) -> Vec<&'static str> {
        let mut events = Vec::new();
        let mut t = 0.0;
        while t < seconds {
            if let Some(event) = latch.update(held, DT) {
                events.push(event.as_str());
            }
            t += DT;
        }
        events
    }

    #[test]
    fn test_double_tap_and_hold_latches() {
        let mut latch = PedalLatch::new();
        assert!(run(&mut latch, true, 0.2).is_empty()); // tap
        assert!(run(&mut latch, false, 0.2).is_empty()); // release
        let events = run(&mut latch, true, CATCH_HOLD_S + 0.1); // press and hold
        assert_eq!(events, ["latched"]);
        assert!(latch.latched);
        // Releasing the key keeps the pedal latched: that is the whole point.
        assert!(run(&mut latch, false, 1.0).is_empty());
        assert!(latch.latched);
    }

    #[test]
    fn test_bare_double_tap_never_latches() {
        let mut latch = PedalLatch::new();
        for _ in 0..4 {
            // feathering: tap tap tap tap
            run(&mut latch, true, 0.15);
            run(&mut latch, false, 0.15);
        }
        assert!(!latch.latched);
    }

    #[test]
    fn test_a_long_first_press_is_driving_not_a_gesture() {
        let mut latch = PedalLatch::new();
        run(&mut latch, true, 2.0); // a plain sustained hold
        run(&mut latch, false, 0.1);
        let events = run(&mut latch, true, 2.0); // another plain hold, right after
        assert!(events.is_empty());
        assert!(!latch.latched);
    }

    #[test]
    fn test_a_slow_second_press_does_not_latch() {
        let mut latch = PedalLatch::new();
        run(&mut latch, true, 0.2);
        run(&mut latch, false, GAP_MAX_S + 0.2); // too slow: the tap expired
        let events = run(&mut latch, true, CATCH_HOLD_S + 0.5);
        assert!(events.is_empty());
        assert!(!latch.latched);
    }

    #[test]
    fn test_a_fresh_press_of_the_same_key_releases() {
        let mut latch = PedalLatch::new();
        run(&mut latch, true, 0.2);
        run(&mut latch, false, 0.2);
        run(&mut latch, true, CATCH_HOLD_S + 0.1);
        run(&mut latch, false, 1.0);
        assert!(latch.latched);

        let events = run(&mut latch, true, 0.1);
        assert_eq!(events, ["released"]);
        assert!(!latch.latched);
        // The releasing press acts as the pedal itself; holding it through the
        // tap window must not start a new gesture from mid-press.
        let events = run(&mut latch, true, CATCH_HOLD_S + 1.0);
        assert!(events.is_empty());
        assert!(!latch.latched);
    }

    #[test]
    fn test_outside_release_reports_only_a_real_drop() {
        let mut latch = PedalLatch::new();
        assert!(!latch.release());
        run(&mut latch, true, 0.2);
        run(&mut latch, false, 0.2);
        run(&mut latch, true, CATCH_HOLD_S + 0.1);
        assert!(latch.latched);
        assert!(latch.release());
        assert!(!latch.latched);
    }

    #[test]
    fn test_tap_gesture_constants_are_gentler_than_the_catch() {
        // The catch must demand a deliberate hold, clearly longer than a tap,
        // or feathering players will latch by accident.
        const { assert!(CATCH_HOLD_S > TAP_MAX_S) };
    }
}
