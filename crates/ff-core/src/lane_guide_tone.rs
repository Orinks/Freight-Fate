//! The optional tone the lane guide can lean instead of the road bed.
//!
//! The guide normally pans the road bed the driver is already hearing -- the
//! community ruling from the audiogames.net thread (JaceK, 2026-07-17): a
//! continuous tone overwhelms the soundscape and hurts players with sensory or
//! hearing conditions, and Forza's blind driving assists reached the same
//! answer, panning the car's own engine and tires rather than adding anything.
//! That ruling stands and the bed is still the default.
//!
//! It fails one real case. `vehicle/road` sits at -33.3 dBFS RMS against the
//! engine loops' -18.7, and `set_road_noise` already runs the road channel at
//! full gain by highway speed, so there is no headroom left to give it. A bed
//! 15 dB under the engine carries no pan information, because you cannot hear
//! which side a sound went to if you cannot hear the sound. Darren reported
//! exactly that and was right.
//!
//! So this is offered as a choice rather than a replacement (owner, 2026-08-17):
//! off unless the driver turns it on, which is the shape the ruling actually
//! objects to -- a tone nobody asked for -- and which the steering-sound RFC
//! already asks of every cue ("individually toggleable, pitch- and
//! volume-adjustable, and previewable"). Regenerating the bed louder is still
//! the fix that helps everyone and is still on the roadmap for September.
//!
//! The pitch and level are Darren's, from the candidate he sent to the tester
//! Dropbox on 2026-08-17: a 291.6 Hz sine at -16 dBFS RMS, which puts it 2.6 dB
//! ABOVE the engine rather than 15 under. His file is a 1.45 s one-shot that
//! cannot loop -- no trailing silence, and mp3 noise at the seam that trimming
//! cannot remove -- and the harmonics sit 40 dB down, so there is nothing in it
//! but the tone. Synthesized here instead, the same way the ladder earcons and
//! the enforcement signature are: pure arithmetic, identical bytes from the
//! same build, nothing to add to LFS. The loop LENGTH is chosen as a whole
//! number of cycles rather than trimmed to one, so the wrap is seamless by
//! construction and not by tuning.
//!
//! Port of `freight_fate/lane_guide_tone.py`; the WAV bytes match the Python
//! build's (pinned by SHA-256 in the tests).

use std::f64::consts::PI;

use crate::assets_pack::register_generated_sound;
use crate::cab_filter::wav::write_wav_pcm16;
use crate::pyfmt::round_py;

/// Keyed under "guide/" rather than "vehicle/" for the same reason the
/// ladder earcons sit under "ladder/": the asset-scan test walks the
/// shipped folders looking for a file on disk, and a synthesized cue has
/// none.
pub const LANE_GUIDE_TONE_KEY: &str = "guide/lane_guide_tone";

const RATE: u32 = 44100;
/// Darren's tone, measured off his file.
pub const TONE_HZ: f64 = 291.620;
pub const TONE_RMS_DBFS: f64 = -16.0;
/// Cycles in one loop. 64 gives about 220 ms -- long enough that the loop is
/// not itself a rhythm, short enough to start and stop with the drift.
pub const TONE_CYCLES: u32 = 64;

/// One seamless loop of the guide tone.
///
/// The sample count comes first and the frequency follows from it, so the
/// loop holds a whole number of cycles exactly and the last sample runs
/// into the first with no step. Trimming a recording to length cannot do
/// this: it leaves a fraction of a cycle and a click on every wrap.
pub fn lane_guide_tone_wav() -> Vec<u8> {
    let frames = round_py(TONE_CYCLES as f64 * RATE as f64 / TONE_HZ) as i64;
    let peak = 10f64.powf(TONE_RMS_DBFS / 20.0) * 32767.0 * 2f64.sqrt();
    let mut samples = Vec::with_capacity(frames.max(0) as usize * 2);
    for i in 0..frames {
        let value =
            (peak * (2.0 * PI * TONE_CYCLES as f64 * i as f64 / frames as f64).sin()) as i64;
        let value = value.clamp(-32768, 32767) as i16;
        samples.push(value);
        samples.push(value); // centred: the guide's pan carries the side
    }
    write_wav_pcm16(RATE, 2, &samples)
}

static REGISTERED: std::sync::Once = std::sync::Once::new();

/// Publish the tone under its ordinary sound key.
///
/// Idempotent, mirroring `ladder_earcons::register_ladder_earcons`: safe to
/// call from the Learn screen every time it opens.
pub fn register_lane_guide_tone() {
    REGISTERED.call_once(|| {
        register_generated_sound(LANE_GUIDE_TONE_KEY, lane_guide_tone_wav(), "wav");
    });
}

#[cfg(test)]
mod tests {
    //! The opt-in lane guide tone (owner call, 2026-08-17).
    //!
    //! The community ruled against steering tones on the audiogames.net thread
    //! (JaceK, 2026-07-17): a continuous tone overwhelms the soundscape and hurts
    //! players with sensory or hearing conditions. That ruling stands -- what is
    //! added here is a CHOICE, off unless a driver turns it on, because the bed it
    //! replaces genuinely fails some of them.
    //!
    //! The Settings-default tests of the Python file
    //! (`test_the_default_is_the_road_bed_not_the_tone`,
    //! `test_an_unreadable_setting_falls_to_the_bed`) belong with the
    //! `settings` port; the catalog test sits in `sound_catalog`.
    use super::*;
    use crate::cab_filter::wav::WavPcm16;
    use sha2::{Digest, Sha256};

    fn samples() -> (Vec<f64>, u32) {
        let wav = WavPcm16::parse(&lane_guide_tone_wav()).unwrap();
        assert_eq!(wav.channels, 2);
        let mono = wav.samples.iter().step_by(2).map(|s| *s as f64).collect();
        (mono, wav.sample_rate)
    }

    #[test]
    fn test_the_loop_wraps_with_no_step() {
        // Seamless by construction, not by trimming.
        //
        // Darren's recording could not be cut into a loop -- no trailing silence
        // and mp3 noise at the seam that no amount of crossfading removed (three
        // attempts, best was -35 dBFS, plainly audible on a cue that wraps four
        // times a second). Choosing the sample count so a whole number of cycles
        // fits exactly makes the wrap error zero instead of small.
        let (mono, rate) = samples();
        let n = mono.len();
        assert!(
            (n as f64 / rate as f64 * 1000.0 - 219.5).abs() < 1.0,
            "loop length drifted"
        );

        // The sample that would follow the last one is the first one.
        let period = n as f64 / TONE_CYCLES as f64;
        let nxt = (2.0 * PI * TONE_CYCLES as f64 * n as f64 / n as f64).sin();
        assert!((nxt - 0f64.sin()).abs() < 1e-9);
        assert!(
            (n as f64 / period - TONE_CYCLES as f64).abs() < 1e-9,
            "not a whole number of cycles"
        );

        // And the real samples agree: end and start sit within a quantisation step
        // of each other, which is what a listener would hear as no click.
        let step = (mono[0] - mono[n - 1]).abs();
        let peak = mono.iter().fold(0.0_f64, |acc, x| acc.max(x.abs()));
        assert!(step < peak * 0.05, "seam step {step} against peak {peak}");
    }

    #[test]
    fn test_the_level_is_darrens_number() {
        // -16 dBFS RMS, which is 2.6 dB ABOVE the engine loops' -18.7.
        //
        // That figure is the whole reason this exists: vehicle/road sits at -33.3
        // and already runs at full gain by highway speed, so the bed is 15 dB
        // under the engine and carries no pan at all.
        let (mono, _) = samples();
        let rms = (mono.iter().map(|x| x * x).sum::<f64>() / mono.len() as f64).sqrt();
        assert!((20.0 * (rms / 32768.0).log10() - TONE_RMS_DBFS).abs() < 0.2);
    }

    #[test]
    fn test_the_tone_is_centred_so_the_guide_carries_the_side() {
        let wav = WavPcm16::parse(&lane_guide_tone_wav()).unwrap();
        let left: Vec<i16> = wav.samples.iter().step_by(2).cloned().collect();
        let right: Vec<i16> = wav.samples.iter().skip(1).step_by(2).cloned().collect();
        assert_eq!(left, right, "a pre-panned asset would fight the guide");
    }

    #[test]
    fn test_the_tone_is_byte_identical_to_the_python_build() {
        // SHA-256 of the Python build's WAV (scratchpad/gen_audio_fixtures.py
        // with the venv Python, 2026-08-22).
        let data = lane_guide_tone_wav();
        assert_eq!(data.len(), 38756);
        assert_eq!(
            hex::encode(Sha256::digest(&data)),
            "ac086347c99133bf0c2cc04617c2f377c89b49d99b2084bc25b22d4809d73c21"
        );
    }

    #[test]
    fn test_register_lane_guide_tone_is_idempotent() {
        register_lane_guide_tone();
        register_lane_guide_tone();
        let (data, ext) = crate::assets_pack::generated_sound(LANE_GUIDE_TONE_KEY).unwrap();
        assert_eq!(ext, "wav");
        assert_eq!(data.len(), 38756);
    }
}
