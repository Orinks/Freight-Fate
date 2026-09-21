//! Playing one catalog entry, faithfully and without leaving anything ringing.
//!
//! A demo is a short script: fire each cue at its moment, hold the ones that are
//! loops for as long as they declare, and release everything the moment the demo
//! ends -- whether it ended on its own, was replaced by another, or the screen
//! was closed underneath it.
//!
//! Held cues go through `hold_alert`, which is a dead man's switch: it stops on
//! its own a fraction of a second after the re-assertions stop. A continuous tone
//! in a blind player's headphones must never be able to outlive the thing that
//! started it, and routing every held demo cue through that one mechanism is what
//! makes that true here without a second watchdog to get wrong.
//!
//! A one-shot is the opposite case: it is handed to the mixer and there is no
//! handle to take it back with. So the demo tracks how long its own cues will
//! sound for (`asset_length_s` measures the clips) and refuses to start the
//! same entry again while they are still sounding. Two copies of the yawn a
//! half-second apart teach a player a sound the road never makes.
//!
//! Port of `freight_fate/sound_demo.py`. The audio facade is reached through
//! [`DemoAudio`] (the five methods the demo uses) and the clip-length lookup
//! is injected, so this sequencer needs no audio device.

use super::{Cue, SoundEntry};

/// The alert channel: the one loop slot the demo holds cues on, so a held
/// cue's pan goes through `set_loop_pan(CH_ALERT, pan)`. Mirrors
/// `audio.CH_ALERT`; the game crate's channel table must agree.
pub const CH_ALERT: i32 = 16;

/// The slice of the audio facade a demo drives.
pub trait DemoAudio {
    /// Start or re-assert the held alert loop under `key` (dead man's switch).
    fn hold_alert(&mut self, key: &str, volume: f64);
    /// Release whatever `hold_alert` is holding.
    fn release_alert(&mut self);
    /// Pan one loop slot.
    fn set_loop_pan(&mut self, channel: i32, pan: f64);
    /// Fire a one-shot.
    fn play(&mut self, key: &str, volume: f64, pan: f64);
    /// Whether `key` resolves to anything this build can play.
    fn has_asset(&self, key: &str) -> bool;
}

/// Sequences one [`SoundEntry`]'s cues against an audio engine.
pub struct SoundDemo {
    /// How long the clip behind a key sounds for (`audio.asset_length_s`):
    /// zero when it resolves to nothing or cannot be measured.
    asset_length_s: Box<dyn Fn(&str) -> f64>,
    entry: Option<SoundEntry>,
    pending: Vec<Cue>,
    elapsed: f64,
    hold_key: String,
    hold_volume: f64,
    hold_until: f64,
    sounding_until: f64,
}

impl SoundDemo {
    pub fn new(asset_length_s: impl Fn(&str) -> f64 + 'static) -> Self {
        Self {
            asset_length_s: Box::new(asset_length_s),
            entry: None,
            pending: Vec::new(),
            elapsed: 0.0,
            hold_key: String::new(),
            hold_volume: 1.0,
            hold_until: 0.0,
            sounding_until: 0.0,
        }
    }

    pub fn running(&self) -> bool {
        self.entry.is_some()
    }

    /// Whether any cue of `entry` resolves to something audible here.
    pub fn can_play(&self, audio: &dyn DemoAudio, entry: &SoundEntry) -> bool {
        entry
            .plays
            .iter()
            .any(|cue| Self::resolve(audio, cue).is_some())
    }

    /// Play `entry` from the top, cancelling whatever was running.
    ///
    /// A repeat of the entry already sounding is ignored rather than layered
    /// on top of itself: the mixer gives back no handle for a one-shot, so
    /// the only way not to double it is not to start it.
    pub fn start(&mut self, audio: &mut dyn DemoAudio, entry: &SoundEntry) {
        if let Some(current) = &self.entry {
            // The Python compared by identity; catalog names are unique, so
            // the name is the same test here.
            if current.name == entry.name && self.elapsed < self.sounding_until {
                return;
            }
        }
        self.stop(audio);
        self.entry = Some(*entry);
        let mut pending: Vec<Cue> = entry.plays.to_vec();
        // Stable, like Python's sorted(): cues at one delay keep their order.
        pending.sort_by(|a, b| a.delay_s.partial_cmp(&b.delay_s).unwrap());
        self.pending = pending;
        self.elapsed = 0.0;
        self.sounding_until = self.sounding_span(audio, entry);
        self.fire_due(audio);
    }

    pub fn update(&mut self, audio: &mut dyn DemoAudio, dt: f64) {
        if self.entry.is_none() {
            return;
        }
        self.elapsed += dt;
        self.fire_due(audio);
        if !self.hold_key.is_empty() {
            // Expiry is absolute on the demo's own clock, not a countdown
            // decremented by whole frames: a coarse dt (a hitching frame, a
            // screen resuming, a stepped test) must never truncate or skip a
            // hold that a delayed cue just started this same update.
            if self.elapsed >= self.hold_until {
                self.release(audio);
            } else {
                // Re-assert every frame: the engine's own watchdog drops the
                // tone if this ever stops, which is the behaviour we want.
                audio.hold_alert(&self.hold_key, self.hold_volume);
            }
        }
        if self.pending.is_empty()
            && self.hold_key.is_empty()
            && self.elapsed >= self.sounding_until
        {
            self.entry = None;
        }
    }

    /// End the demo now and release anything it was holding.
    pub fn stop(&mut self, audio: &mut dyn DemoAudio) {
        self.release(audio);
        self.entry = None;
        self.pending.clear();
        self.elapsed = 0.0;
        self.sounding_until = 0.0;
    }

    // -- internals -------------------------------------------------------------

    /// When the last of `entry`'s cues stops making noise.
    ///
    /// A held cue is done when the demo releases it; a one-shot is done when
    /// its clip runs out, which is what the measured length is for. A clip
    /// the game cannot measure counts as zero -- it resolved to nothing, so
    /// there is nothing sounding to protect.
    fn sounding_span(&self, audio: &dyn DemoAudio, entry: &SoundEntry) -> f64 {
        let mut span: f64 = 0.0;
        for cue in entry.plays {
            let Some(key) = Self::resolve(audio, cue) else {
                continue;
            };
            let tail = if cue.hold_s > 0.0 {
                cue.hold_s
            } else {
                (self.asset_length_s)(key)
            };
            span = span.max(cue.delay_s + tail);
        }
        span
    }

    fn fire_due(&mut self, audio: &mut dyn DemoAudio) {
        while !self.pending.is_empty() && self.pending[0].delay_s <= self.elapsed {
            let cue = self.pending.remove(0);
            self.play(audio, &cue);
        }
    }

    fn play(&mut self, audio: &mut dyn DemoAudio, cue: &Cue) {
        let Some(key) = Self::resolve(audio, cue) else {
            return;
        };
        if cue.hold_s > 0.0 {
            self.release(audio); // one held cue at a time: the alert channel is one channel
            audio.hold_alert(key, cue.volume);
            audio.set_loop_pan(CH_ALERT, cue.pan);
            self.hold_key = key.to_string();
            self.hold_volume = cue.volume;
            self.hold_until = self.elapsed + cue.hold_s;
            return;
        }
        audio.play(key, cue.volume, cue.pan);
    }

    /// `cue.key` where it exists, else its fallback, else nothing.
    ///
    /// The licensed overlay carries cues a clean clone does not have. A demo
    /// that silently played nothing would teach a player that a real cue is
    /// silent, which is the worst thing this screen could do -- so the caller
    /// checks [`SoundDemo::can_play`] first and says so out loud instead.
    fn resolve(audio: &dyn DemoAudio, cue: &Cue) -> Option<&'static str> {
        if audio.has_asset(cue.key) {
            return Some(cue.key);
        }
        if !cue.fallback.is_empty() && audio.has_asset(cue.fallback) {
            return Some(cue.fallback);
        }
        None
    }

    fn release(&mut self, audio: &mut dyn DemoAudio) {
        if self.hold_key.is_empty() {
            return;
        }
        self.hold_key.clear();
        self.hold_until = 0.0;
        audio.release_alert();
    }
}

#[cfg(test)]
mod tests {
    //! Learn game sounds: the demo sequencer. (The screen that drives it --
    //! `LearnSoundsState` / `LearnSoundCategoryState` -- is an app-shell
    //! test in the game crate.)
    use super::*;

    /// Records what a demo asked for, in order.
    #[derive(Default)]
    struct FakeAudio {
        played: Vec<(String, f64, f64)>,
        holds: Vec<(String, f64)>,
        pans: Vec<(i32, f64)>,
        released: usize,
    }

    impl DemoAudio for FakeAudio {
        fn hold_alert(&mut self, key: &str, volume: f64) {
            self.holds.push((key.to_string(), volume));
        }
        fn release_alert(&mut self) {
            self.released += 1;
        }
        fn set_loop_pan(&mut self, channel: i32, pan: f64) {
            self.pans.push((channel, pan));
        }
        fn play(&mut self, key: &str, volume: f64, pan: f64) {
            self.played.push((key.to_string(), volume, pan));
        }
        fn has_asset(&self, key: &str) -> bool {
            !key.starts_with("missing/")
        }
    }

    impl FakeAudio {
        fn played_keys(&self) -> Vec<&str> {
            self.played.iter().map(|(k, _, _)| k.as_str()).collect()
        }
    }

    /// `audio.asset_length_s` as the real assets measure: the yawn is the
    /// longest one-shot in the catalog at 3.8 seconds; everything else in
    /// these fixtures is short.
    fn demo() -> SoundDemo {
        SoundDemo::new(|key| if key == "driver/yawn" { 3.8 } else { 0.5 })
    }

    /// Test entries are built at runtime; `SoundEntry.plays` is `'static`
    /// because the catalog is, so the fixture cues are leaked (tests only).
    fn entry(name: &'static str, plays: Vec<Cue>) -> SoundEntry {
        SoundEntry::new(name, Box::leak(plays.into_boxed_slice()), "why")
    }

    #[test]
    fn test_a_one_shot_entry_plays_once_with_its_volume_and_pan() {
        let mut audio = FakeAudio::default();
        let mut demo = demo();
        demo.start(
            &mut audio,
            &entry("X", vec![Cue::new("a/one").volume(0.5).pan(-0.6)]),
        );
        assert_eq!(audio.played, vec![("a/one".to_string(), 0.5, -0.6)]);
        demo.update(&mut audio, 0.1);
        assert_eq!(
            audio.played,
            vec![("a/one".to_string(), 0.5, -0.6)],
            "a one-shot must not repeat"
        );
    }

    #[test]
    fn test_a_delayed_cue_waits_for_its_moment() {
        let mut audio = FakeAudio::default();
        let mut demo = demo();
        demo.start(
            &mut audio,
            &entry(
                "X",
                vec![
                    Cue::new("a/left").pan(-0.8),
                    Cue::new("a/right").pan(0.8).delay_s(1.0),
                ],
            ),
        );
        assert_eq!(audio.played_keys(), vec!["a/left"]);
        demo.update(&mut audio, 0.5);
        assert_eq!(audio.played_keys(), vec!["a/left"]);
        demo.update(&mut audio, 0.6);
        assert_eq!(audio.played_keys(), vec!["a/left", "a/right"]);
    }

    #[test]
    fn test_a_held_cue_is_reasserted_every_frame_then_released() {
        let mut audio = FakeAudio::default();
        let mut demo = demo();
        demo.start(
            &mut audio,
            &entry(
                "X",
                vec![Cue::new("a/loop").volume(0.7).pan(0.3).hold_s(1.0)],
            ),
        );
        assert_eq!(audio.holds, vec![("a/loop".to_string(), 0.7)]);
        assert!(!audio.pans.is_empty() && audio.pans.last().unwrap().1 == 0.3);
        demo.update(&mut audio, 0.5);
        assert!(
            audio.holds.len() > 1,
            "a held cue must be re-asserted while it runs"
        );
        assert_eq!(audio.released, 0);
        demo.update(&mut audio, 0.6);
        assert_eq!(audio.released, 1);
        assert!(!demo.running());
    }

    #[test]
    fn test_starting_a_new_demo_cancels_the_running_one() {
        let mut audio = FakeAudio::default();
        let mut demo = demo();
        demo.start(
            &mut audio,
            &entry("X", vec![Cue::new("a/loop").hold_s(5.0)]),
        );
        demo.start(&mut audio, &entry("Y", vec![Cue::new("b/one")]));
        assert_eq!(audio.released, 1);
        demo.update(&mut audio, 0.1);
        assert_eq!(audio.released, 1, "the second demo has nothing to release");
    }

    #[test]
    fn test_stop_releases_a_held_cue_and_ends_the_demo() {
        let mut audio = FakeAudio::default();
        let mut demo = demo();
        demo.start(
            &mut audio,
            &entry("X", vec![Cue::new("a/loop").hold_s(5.0)]),
        );
        demo.stop(&mut audio);
        assert_eq!(audio.released, 1);
        assert!(!demo.running());
    }

    #[test]
    fn test_a_cue_falls_back_when_its_key_is_missing() {
        let mut audio = FakeAudio::default();
        let mut demo = demo();
        demo.start(
            &mut audio,
            &entry("X", vec![Cue::new("missing/thing").fallback("a/real")]),
        );
        assert_eq!(audio.played_keys(), vec!["a/real"]);
    }

    #[test]
    fn test_a_delayed_held_cue_holds_for_its_full_duration_even_across_a_big_step() {
        // The road lean is exactly this shape: Cue(..., delay_s=2.4, hold_s=2.0).
        //
        // A hold that starts mid-frame must not lose that frame from its duration --
        // a coarse `dt` (a hitching frame, a screen resuming, a stepped test) must
        // never truncate or skip the hold.
        let mut audio = FakeAudio::default();
        let mut demo = demo();
        demo.start(
            &mut audio,
            &entry("X", vec![Cue::new("a/loop").hold_s(2.0).delay_s(1.0)]),
        );
        assert!(audio.holds.is_empty());
        demo.update(&mut audio, 3.0); // spans the 1.0s delay and lands inside the 2.0s hold
        assert!(!audio.holds.is_empty(), "the delayed hold must have fired");
        assert_eq!(
            audio.released, 0,
            "must not be released in the same update that started it"
        );
        assert!(demo.running());
        demo.update(&mut audio, 3.0); // now past elapsed 5.0 (1.0 delay + 2.0 hold)
        assert_eq!(audio.released, 1);
        assert!(!demo.running());
    }

    #[test]
    fn test_a_cue_with_no_playable_key_plays_and_holds_nothing() {
        // Missing key, missing fallback: play nothing, hold nothing, do not raise.
        let mut audio = FakeAudio::default();
        let mut demo = demo();
        demo.start(
            &mut audio,
            &entry(
                "X",
                vec![Cue::new("missing/thing").fallback("missing/other")],
            ),
        );
        assert!(audio.played.is_empty());
        assert!(audio.holds.is_empty());
        assert_eq!(audio.released, 0);
        demo.update(&mut audio, 0.1);
        assert!(audio.played.is_empty());
        assert!(audio.holds.is_empty());
        assert_eq!(audio.released, 0);
        assert!(!demo.running());
    }

    #[test]
    fn test_a_one_shot_is_not_layered_over_a_copy_of_itself() {
        // Enter twice on the yawn used to play two yawns a moment apart.
        //
        // A one-shot handed to the mixer comes back with no handle, so the demo
        // cannot cut the first copy short; the only way not to double it is not to
        // start it. `driver/yawn` is the longest one-shot in the catalog at 3.8
        // seconds, which is long enough that a player mashing Enter really did hear
        // a sound the road never makes.
        let mut audio = FakeAudio::default();
        let mut demo = demo();
        let yawn = entry("Yawn", vec![Cue::new("driver/yawn").volume(0.9)]);

        demo.start(&mut audio, &yawn);
        demo.update(&mut audio, 0.2);
        demo.start(&mut audio, &yawn); // Enter again, well inside the clip
        assert_eq!(
            audio.played_keys(),
            vec!["driver/yawn"],
            "the yawn must not double"
        );

        demo.update(&mut audio, 4.0); // past the end of the clip
        demo.start(&mut audio, &yawn);
        assert_eq!(
            audio.played.len(),
            2,
            "once it has finished, Enter plays it again"
        );
    }

    #[test]
    fn test_a_different_entry_still_interrupts_a_sounding_one() {
        // The guard is per entry: arrowing on and playing the next cue must work.
        let mut audio = FakeAudio::default();
        let mut demo = demo();
        demo.start(&mut audio, &entry("Yawn", vec![Cue::new("driver/yawn")]));
        demo.update(&mut audio, 0.2);
        demo.start(
            &mut audio,
            &entry("Other", vec![Cue::new("events/spike_strip")]),
        );
        assert_eq!(
            audio.played_keys(),
            vec!["driver/yawn", "events/spike_strip"]
        );
    }

    #[test]
    fn test_a_cue_with_nothing_to_play_reports_itself_unplayable() {
        let audio = FakeAudio::default();
        let demo = demo();
        assert!(demo.can_play(&audio, &entry("X", vec![Cue::new("a/real")])));
        assert!(demo.can_play(
            &audio,
            &entry("X", vec![Cue::new("missing/thing").fallback("a/real")])
        ));
        assert!(!demo.can_play(&audio, &entry("X", vec![Cue::new("missing/thing")])));
    }
}
