//! Synthesized earcons for the categories the S4 driving speech ladder
//! retires to sound (R14, `docs/ontology.md`'s "Terse speech grammar").
//!
//! `NAVIGATION_ADVISORY`, `COACHING`, `CONFIRMATION` and `STATUS` have no existing cue that means what an earcon
//! standing in for either needs to mean -- every candidate already carries a
//! meaning of its own (the overspeed chime says "you are speeding", not "here
//! was a tip"), and reusing one would teach a player two different things under
//! one sound. These two tones are synthesized rather than shipped, the same way
//! the enforcement signature is (`states/driving_siren.py`): pure arithmetic,
//! so the same build always produces the same bytes and nothing needs an LFS
//! entry.
//!
//! Deliberately plainer than the enforcement signature, which has to survive
//! being heard against radio static and repeats twice on purpose. These two only
//! need to be tellable apart from each other and from everything else already
//! playing: coaching is two rising notes (a tip offered), status is one short
//! low note (something changed, look at it later if you want to), and the road
//! ahead note is two falling notes (the road is about to do something) -- the
//! opposite contour to coaching's, so the pair cannot be confused at speed --
//! and confirmation is one short high note, an octave over status, so "that
//! worked" and "something changed" part on pitch alone.
//!
//! CONFIRMATION used to borrow the shipped "Hazard clear" chime rather than
//! have a tone of its own, which broke this module's own rule: that chime
//! already means "you got past the hazard". At quiet it fired for every
//! silenced confirmation, so the owner heard hazard-cleared while a hazard was
//! still live and the truck was braking for it (playtest, 2026-08-17).
//!
//! Port of `freight_fate/ladder_earcons.py`. The sample arithmetic keeps the
//! Python operation order (Python's `int()` truncation, `math.sin` per
//! sample), so the WAV bytes are identical to the Python build's -- pinned by
//! SHA-256 in the tests.

use std::f64::consts::PI;

use crate::assets_pack::register_generated_sound;
use crate::cab_filter::wav::write_wav_pcm16;

pub const CONFIRMATION_NOTE_KEY: &str = "ladder/confirmation_note";
pub const ROAD_AHEAD_NOTE_KEY: &str = "ladder/road_ahead_note";
pub const COACHING_NOTE_KEY: &str = "ladder/coaching_note";
pub const STATUS_NOTE_KEY: &str = "ladder/status_note";

const RATE: u32 = 44100;
const EDGE_S: f64 = 0.008; // raised-cosine edges, just enough to kill the click

/// Raised-cosine edges on a rectangular tone, matching the signature's.
fn envelope(index: i64, total: i64, edge: i64) -> f64 {
    if edge <= 0 {
        return 1.0;
    }
    if index < edge {
        return 0.5 - 0.5 * (PI * index as f64 / edge as f64).cos();
    }
    if index >= total - edge {
        return 0.5 - 0.5 * (PI * (total - 1 - index) as f64 / edge as f64).cos();
    }
    1.0
}

/// Interleaved stereo samples of one tone (the same value on both sides).
fn tone_samples(freq_hz: f64, dur_s: f64, peak: f64) -> Vec<i16> {
    let n = (dur_s * RATE as f64) as i64;
    let edge = (EDGE_S * RATE as f64) as i64;
    let step = 2.0 * PI * freq_hz / RATE as f64;
    let amp = (peak * 32767.0) as i64;
    let mut samples = Vec::with_capacity((n.max(0) as usize) * 2);
    for i in 0..n {
        // int(amp * env * sin): Python truncates toward zero, as `as i16` does
        // for in-range values (amp keeps it in range).
        let value = (amp as f64 * envelope(i, n, edge) * (step * i as f64).sin()) as i16;
        samples.push(value);
        samples.push(value);
    }
    samples
}

fn wav_bytes(samples: &[i16]) -> Vec<u8> {
    write_wav_pcm16(RATE, 2, samples)
}

/// One short, clear high note: the thing you asked for happened.
///
/// A single note like the status tock, an octave above it, so "something
/// changed, look later" and "that worked" are told apart by pitch alone
/// without either becoming a two-note phrase like the other two.
pub fn confirmation_note_wav() -> Vec<u8> {
    wav_bytes(&tone_samples(784.0, 0.06, 0.32))
}

/// Two short notes falling: the road is about to do something.
///
/// Falls where the coaching chime rises, so the two are tellable apart with
/// no context, and pitched between them so neither reads as the other's
/// louder cousin. Shorter than either, because it fires on a lookahead and
/// may land more than once on a winding stretch.
pub fn road_ahead_note_wav() -> Vec<u8> {
    let mut samples = tone_samples(587.33, 0.07, 0.38);
    samples.extend(tone_samples(466.16, 0.07, 0.38));
    wav_bytes(&samples)
}

/// A soft two-note rising chime: a tip offered, not an alarm.
pub fn coaching_note_wav() -> Vec<u8> {
    let mut samples = tone_samples(523.25, 0.09, 0.4);
    samples.extend(tone_samples(659.25, 0.09, 0.4));
    wav_bytes(&samples)
}

/// A single short, low tock: a state changed, nothing to act on now.
pub fn status_note_wav() -> Vec<u8> {
    wav_bytes(&tone_samples(392.0, 0.08, 0.35))
}

static REGISTERED: std::sync::Once = std::sync::Once::new();

/// Publish the synthesized earcons under their ordinary sound keys.
///
/// Idempotent, mirroring `driving_siren.register_enforcement_sounds`:
/// safe to call from the Learn screen every time it opens, and cheap enough
/// that nothing needs to remember whether it already ran.
pub fn register_ladder_earcons() {
    REGISTERED.call_once(|| {
        register_generated_sound(CONFIRMATION_NOTE_KEY, confirmation_note_wav(), "wav");
        register_generated_sound(ROAD_AHEAD_NOTE_KEY, road_ahead_note_wav(), "wav");
        register_generated_sound(COACHING_NOTE_KEY, coaching_note_wav(), "wav");
        register_generated_sound(STATUS_NOTE_KEY, status_note_wav(), "wav");
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::assets_pack::{generated_sound, generated_sound_keys};
    use sha2::{Digest, Sha256};

    fn sha(data: &[u8]) -> String {
        hex::encode(Sha256::digest(data))
    }

    // SHA-256 of each WAV as the Python build produces it
    // (scratchpad/gen_audio_fixtures.py with the venv Python, 2026-08-22).
    const PYTHON_HASHES: &[(&str, usize, &str)] = &[
        (
            "confirmation",
            10628,
            "70e54e0028bd82a6bf9bbf11cdee68dee7f1765d9eed62d3a94c7b9cc8526e6a",
        ),
        (
            "road_ahead",
            24740,
            "6a74ac1340e1a5c91a8bd93ba91740611c3a2e335ea6877a333fe052a88bf0f4",
        ),
        (
            "coaching",
            31796,
            "6e4fcdabc8cb914968b61ef2df891d67bc07b938dc4425f505d9f5833a31bcd7",
        ),
        (
            "status",
            14156,
            "9095c5ebd0e329471b1dbd03b1e9f923dbd6dd9ff6f1b06a5fd50357e958148f",
        ),
    ];

    fn wav_for(name: &str) -> Vec<u8> {
        match name {
            "confirmation" => confirmation_note_wav(),
            "road_ahead" => road_ahead_note_wav(),
            "coaching" => coaching_note_wav(),
            "status" => status_note_wav(),
            _ => unreachable!(),
        }
    }

    #[test]
    fn test_every_earcon_is_byte_identical_to_the_python_build() {
        for (name, len, hash) in PYTHON_HASHES {
            let data = wav_for(name);
            assert_eq!(data.len(), *len, "{name} length");
            assert_eq!(
                sha(&data),
                *hash,
                "{name} bytes differ from the Python build"
            );
        }
    }

    #[test]
    fn test_the_contours_are_as_documented() {
        // Coaching rises, road-ahead falls, confirmation sits an octave over
        // status: pinned by the frequencies each recipe uses.
        let one_note = |wav: &[u8]| {
            let samples = crate::cab_filter::wav::WavPcm16::parse(wav).unwrap();
            samples.frames()
        };
        assert_eq!(
            one_note(&confirmation_note_wav()),
            (0.06 * 44100.0) as usize
        );
        assert_eq!(one_note(&status_note_wav()), (0.08 * 44100.0) as usize);
        assert_eq!(
            one_note(&coaching_note_wav()),
            2 * ((0.09 * 44100.0) as usize)
        );
        assert_eq!(
            one_note(&road_ahead_note_wav()),
            2 * ((0.07 * 44100.0) as usize)
        );
    }

    #[test]
    fn test_register_ladder_earcons_publishes_all_four_once() {
        register_ladder_earcons();
        register_ladder_earcons();
        let keys = generated_sound_keys();
        for key in [
            CONFIRMATION_NOTE_KEY,
            ROAD_AHEAD_NOTE_KEY,
            COACHING_NOTE_KEY,
            STATUS_NOTE_KEY,
        ] {
            assert!(keys.contains(&key.to_string()), "{key}");
            let (data, ext) = generated_sound(key).unwrap();
            assert_eq!(ext, "wav");
            assert!(data.starts_with(b"RIFF"));
        }
    }
}
