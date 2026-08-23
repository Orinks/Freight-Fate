//! The held siren, and the synthesized signature that leads it (port of
//! `freight_fate/states/driving_siren.py`). It lives in the driving prelude
//! because `DrivingState` owns a [`SirenLoop`] from construction; the
//! `driving_siren` module re-exports it.
//!
//! Two accessibility failures live here, and this module is both fixes.
//!
//! **The siren was a single shot.** `events/police_siren` played once, mono,
//! dead centre, at a fixed level, and never repeated -- and `_update_pull_over`
//! contained no audio at all. A player who missed that one wail had no ongoing
//! evidence a cruiser was behind them at any point in the entire stop. The siren
//! is now a held loop on its own reserved channel, panned and levelled to track
//! the cruiser as a real object. **The rise in level over the first few seconds
//! is the "he is coming up behind you" information**, and it is the single most
//! important cue in the whole enforcement system: a fixed-level siren says a
//! police car exists, a rising one says it is closing on you.
//!
//! **The radio made sirens ambiguous.** The station catalog ships around
//! thirty-eight always-available police and fire scanner streams, and nothing
//! ducked the radio for anything. A siren in the headphones could equally be the
//! programme. So enforcement leads with a signature the game synthesizes here:
//! two dry, hard-gated sine tones, no room, no noise floor, no codec artifacts.
//! That is not a claim that nothing could ever imitate it -- a station can in
//! principle broadcast anything. It is a shape that survives being heard against
//! programme material, and it is always played into a ducked radio (see
//! `_radio_cue_duck`), so it lands in a hole rather than on top of a mix. For a
//! pull-over the radio is CUT outright rather than ducked: the sudden silence is
//! itself an unambiguous cue that something has taken over the cab.
//!
//! The realistic siren stays layered underneath the signature. The signature says
//! "this is the game talking to you about enforcement"; the siren says what it is.

use std::f64::consts::PI;
use std::sync::Once;

use ff_core::assets_pack::register_generated_sound;
use ff_core::audio_loops::{LoopUnits, SustainLoopSpec};

use crate::audio::{Audio, CH_SIREN};

// -- the synthesized signature ----------------------------------------------

pub const SIGNATURE_KEY: &str = "enforcement/signature";
pub const SIGNATURE_RATE: u32 = 44100;
// A rising minor sixth. Deliberately musical and deliberately dry: two pure
// tones with hard gates and no tail are the opposite of everything else in the
// cab, which is all engine, air, tyre and weather noise.
pub const SIGNATURE_LOW_HZ: f64 = 660.0;
pub const SIGNATURE_HIGH_HZ: f64 = 1056.0;
pub const SIGNATURE_TONE_S: f64 = 0.13;
pub const SIGNATURE_GAP_S: f64 = 0.04;
pub const SIGNATURE_REPEATS: usize = 2;
pub const SIGNATURE_EDGE_S: f64 = 0.008; // raised-cosine edges, just enough to kill the click
pub const SIGNATURE_PEAK: f64 = 0.55;

// The marked-unit pass is a two-element signature: the marker LEADS the
// vehicle whoosh. A garnished whoosh -- one clip differing from the civilian
// pass only by a subtle chirp buried inside it -- disappears under engine,
// road, weather and radio. A marker at or above the whoosh's level, arriving
// first, survives where the garnish does not.
pub const PASS_MARKER_LEAD_S: f64 = 0.2;

// -- the held siren ----------------------------------------------------------

// Loop the interior of the four-second siren asset, letting the attack play
// once and the tail ring out on release.
pub const SIREN_LOOP_START_S: f64 = 0.6;
pub const SIREN_LOOP_END_S: f64 = 3.4;
// The level the siren starts at when a cruiser first lights up, and how long
// it takes to reach full. This ramp is the cue.
pub const SIREN_START_LEVEL: f64 = 0.25;
pub const SIREN_RISE_S: f64 = 4.0;
pub const SIREN_FULL_LEVEL: f64 = 1.0;
pub const SIREN_RELEASE_FADE_MS: u32 = 400;
// A held sound in a blind player's headphones must never outlive the thing it
// is about. Same dead man's switch as the held alert tone: the owner
// re-asserts it every frame, and it stops on its own the moment that stops.
pub const SIREN_HOLD_TIMEOUT_S: f64 = 0.4;

/// Raised-cosine edges on a rectangular tone.
fn envelope(index: usize, total: usize, edge: usize) -> f64 {
    if edge == 0 {
        return 1.0;
    }
    if index < edge {
        return 0.5 - 0.5 * (PI * index as f64 / edge as f64).cos();
    }
    if index + edge >= total {
        return 0.5 - 0.5 * (PI * (total - 1 - index) as f64 / edge as f64).cos();
    }
    1.0
}

/// Deterministic 16-bit stereo WAV bytes for the enforcement signature.
///
/// Pure arithmetic, no random source, no floating-point ordering hazard: the
/// same build always produces the same bytes, so the sound is as reproducible
/// as any shipped asset and needs no place in the sound pack.
pub fn enforcement_signature_wav() -> Vec<u8> {
    let mut samples: Vec<i16> = Vec::new();
    let tone_n = (SIGNATURE_TONE_S * SIGNATURE_RATE as f64) as usize;
    let gap_n = (SIGNATURE_GAP_S * SIGNATURE_RATE as f64) as usize;
    let edge_n = (SIGNATURE_EDGE_S * SIGNATURE_RATE as f64) as usize;
    let peak = (SIGNATURE_PEAK * 32767.0) as i32;
    for _ in 0..SIGNATURE_REPEATS {
        for freq in [SIGNATURE_LOW_HZ, SIGNATURE_HIGH_HZ] {
            let step = 2.0 * PI * freq / SIGNATURE_RATE as f64;
            for i in 0..tone_n {
                // Python's int() truncates toward zero, as `as i16` does.
                let value =
                    (peak as f64 * envelope(i, tone_n, edge_n) * (step * i as f64).sin()) as i16;
                samples.push(value);
                samples.push(value);
            }
            for _ in 0..gap_n {
                samples.push(0);
                samples.push(0);
            }
        }
    }
    wav_bytes(&samples, 2, SIGNATURE_RATE)
}

/// A canonical RIFF/WAVE container around 16-bit PCM frames (what Python's
/// `wave` module writes).
fn wav_bytes(samples: &[i16], channels: u16, rate: u32) -> Vec<u8> {
    let data_len = (samples.len() * 2) as u32;
    let block_align = channels * 2;
    let mut out = Vec::with_capacity(44 + data_len as usize);
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&(36 + data_len).to_le_bytes());
    out.extend_from_slice(b"WAVE");
    out.extend_from_slice(b"fmt ");
    out.extend_from_slice(&16u32.to_le_bytes());
    out.extend_from_slice(&1u16.to_le_bytes()); // PCM
    out.extend_from_slice(&channels.to_le_bytes());
    out.extend_from_slice(&rate.to_le_bytes());
    out.extend_from_slice(&(rate * block_align as u32).to_le_bytes());
    out.extend_from_slice(&block_align.to_le_bytes());
    out.extend_from_slice(&16u16.to_le_bytes());
    out.extend_from_slice(b"data");
    out.extend_from_slice(&data_len.to_le_bytes());
    for sample in samples {
        out.extend_from_slice(&sample.to_le_bytes());
    }
    out
}

static REGISTERED: Once = Once::new();

/// Publish the synthesized signature under an ordinary sound key.
///
/// Idempotent, and cheap enough to call from a driving state's constructor.
pub fn register_enforcement_sounds() {
    REGISTERED.call_once(|| {
        register_generated_sound(SIGNATURE_KEY, enforcement_signature_wav(), "wav");
    });
}

/// A siren that tracks a cruiser, on its own channel and its own bus.
///
/// Assert it every frame with [`SirenLoop::hold`] for as long as the cruiser
/// is there, and call [`SirenLoop::service`] every frame unconditionally. If
/// the holds stop -- a menu opening over the drive, the stop resolving, an
/// owner that lost the frame -- it releases itself within a fraction of a
/// second.
#[derive(Debug, Clone)]
pub struct SirenLoop {
    pub active: bool,
    pub elapsed_s: f64,
    hold_s: f64,
    pan: f64,
}

impl Default for SirenLoop {
    fn default() -> Self {
        Self::new()
    }
}

impl SirenLoop {
    pub fn new() -> Self {
        Self {
            active: false,
            elapsed_s: 0.0,
            hold_s: 0.0,
            pan: 0.0,
        }
    }

    /// Current siren level: the rise, which is the information.
    pub fn level(&self) -> f64 {
        if !self.active {
            return 0.0;
        }
        let ramp = (self.elapsed_s / SIREN_RISE_S.max(1e-6)).min(1.0);
        SIREN_START_LEVEL + (SIREN_FULL_LEVEL - SIREN_START_LEVEL) * ramp
    }

    /// Sound the siren for the next moment only. Call every frame.
    pub fn hold(&mut self, audio: &mut dyn Audio, pan: f64) {
        self.hold_s = SIREN_HOLD_TIMEOUT_S;
        self.pan = pan.clamp(-1.0, 1.0);
        if !self.active {
            self.active = true;
            self.elapsed_s = 0.0;
            audio.start_sustain_loop_with(
                CH_SIREN,
                "events/police_siren",
                SustainLoopSpec {
                    loop_start: SIREN_LOOP_START_S,
                    loop_end: SIREN_LOOP_END_S,
                    units: LoopUnits::Seconds,
                },
                self.level(),
            );
        }
        audio.set_loop_volume(CH_SIREN, self.level());
        audio.set_loop_pan(CH_SIREN, self.pan);
    }

    /// Advance the ramp and release the loop if the holds stopped.
    pub fn service(&mut self, audio: &mut dyn Audio, dt: f64) {
        if !self.active {
            return;
        }
        self.elapsed_s += dt;
        self.hold_s -= dt;
        if self.hold_s <= 0.0 {
            self.stop(audio);
        }
    }

    pub fn stop(&mut self, audio: &mut dyn Audio) {
        if !self.active {
            return;
        }
        self.active = false;
        self.elapsed_s = 0.0;
        self.hold_s = 0.0;
        audio.release_sustain_loop_with(CH_SIREN, SIREN_RELEASE_FADE_MS);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_signature_is_a_deterministic_stereo_wav() {
        let a = enforcement_signature_wav();
        let b = enforcement_signature_wav();
        assert_eq!(a, b);
        assert_eq!(&a[0..4], b"RIFF");
        assert_eq!(&a[8..12], b"WAVE");
        // channels = 2 at offset 22, rate at 24
        assert_eq!(u16::from_le_bytes([a[22], a[23]]), 2);
        assert_eq!(
            u32::from_le_bytes([a[24], a[25], a[26], a[27]]),
            SIGNATURE_RATE
        );
        let frames =
            2 * 2 * ((SIGNATURE_TONE_S + SIGNATURE_GAP_S) * SIGNATURE_RATE as f64) as usize;
        assert_eq!(a.len(), 44 + frames * 4);
    }

    #[test]
    fn the_level_rises_from_the_start_level_to_full() {
        let mut siren = SirenLoop::new();
        assert_eq!(siren.level(), 0.0);
        siren.active = true;
        assert_eq!(siren.level(), SIREN_START_LEVEL);
        siren.elapsed_s = SIREN_RISE_S;
        assert_eq!(siren.level(), SIREN_FULL_LEVEL);
    }
}
