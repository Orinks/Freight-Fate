//! Score to PCM with the 1.5 voice set: soft pad, plucked string, electric
//! keys, sine bass, noise brushes and a small kit, through a light reverb.
//! Pure and deterministic: the pluck's noise comes from the score's own seed.

use super::compose::{Note, Score, Voice};
use super::rng::Rng;
use std::f64::consts::TAU;
use std::sync::atomic::{AtomicBool, Ordering};

pub const SAMPLE_RATE: u32 = 22_050;
const PEAK: f64 = 0.85 * i16::MAX as f64;
const FADE_IN_S: f64 = 1.5;
const FADE_OUT_S: f64 = 3.0;

fn hz(midi: i32) -> f64 {
    440.0 * 2f64.powf((midi - 69) as f64 / 12.0)
}

/// (left gain, right gain) for a voice: bass and kick centred, the rest spread.
fn pan(voice: Voice) -> (f64, f64) {
    match voice {
        Voice::Pad => (0.8, 0.8),
        Voice::Pluck => (0.65, 0.95),
        Voice::Keys => (0.95, 0.65),
        Voice::Bass | Voice::Kick | Voice::Snare => (0.9, 0.9),
        Voice::Hat => (0.6, 0.9),
    }
}

/// One note into a mono scratch buffer starting at frame 0.
fn voice_samples(note: &Note, dur_s: f64, rng: &mut Rng) -> Vec<f64> {
    let sr = SAMPLE_RATE as f64;
    let f = hz(note.midi);
    let v = note.velocity as f64;
    match note.voice {
        Voice::Pad => {
            let release = 0.8;
            let n = ((dur_s + release) * sr) as usize;
            (0..n)
                .map(|i| {
                    let t = i as f64 / sr;
                    let env = (t / 0.4).min(1.0)
                        * if t > dur_s {
                            (1.0 - (t - dur_s) / release).max(0.0)
                        } else {
                            1.0
                        };
                    let wave = (TAU * f * t).sin()
                        + 0.35 * (TAU * f * 1.003 * 2.0 * t).sin()
                        + 0.2 * (TAU * f * 0.997 * t).sin();
                    v * env * wave * 0.5
                })
                .collect()
        }
        Voice::Pluck => {
            // Karplus-Strong: a noise burst in a delay line, averaged each pass.
            let period = (sr / f).max(2.0) as usize;
            let mut line: Vec<f64> = (0..period).map(|_| rng.unit() * 2.0 - 1.0).collect();
            let n = ((dur_s + 0.6) * sr) as usize;
            let mut out = Vec::with_capacity(n);
            for i in 0..n {
                let a = line[i % period];
                let b = line[(i + 1) % period];
                let next = 0.996 * 0.5 * (a + b);
                line[i % period] = next;
                out.push(v * a * 0.8);
            }
            out
        }
        Voice::Keys => {
            let n = ((dur_s + 0.8) * sr) as usize;
            (0..n)
                .map(|i| {
                    let t = i as f64 / sr;
                    let decay = (-t * 2.2).exp();
                    let index = 1.8 * (-t * 6.0).exp();
                    v * decay * (TAU * f * t + index * (TAU * f * t).sin()).sin() * 0.6
                })
                .collect()
        }
        Voice::Bass => {
            let n = ((dur_s + 0.2) * sr) as usize;
            (0..n)
                .map(|i| {
                    let t = i as f64 / sr;
                    let env = (t / 0.01).min(1.0) * (-t * 1.6).exp();
                    v * env * ((TAU * f * t).sin() + 0.25 * (TAU * 2.0 * f * t).sin()) * 0.8
                })
                .collect()
        }
        Voice::Kick => {
            let n = (0.35 * sr) as usize;
            let mut phase = 0.0;
            (0..n)
                .map(|i| {
                    let t = i as f64 / sr;
                    let freq = 50.0 + 90.0 * (-t * 30.0).exp();
                    phase += TAU * freq / sr;
                    v * (-t * 9.0).exp() * phase.sin()
                })
                .collect()
        }
        Voice::Snare | Voice::Hat => {
            let (len, decay, bright) = if note.voice == Voice::Snare {
                (0.25, 18.0, 0.5)
            } else {
                (0.08, 60.0, 0.9)
            };
            let n = (len * sr) as usize;
            let mut prev = 0.0;
            (0..n)
                .map(|i| {
                    let t = i as f64 / sr;
                    let white = rng.unit() * 2.0 - 1.0;
                    // One-pole high-pass: brighter for the hat.
                    let hp = white - bright * prev;
                    prev = white;
                    v * (-t * decay).exp() * hp * 0.5
                })
                .collect()
        }
    }
}

/// Small Schroeder reverb on a mono send. Takes the send by value so it is
/// freed as soon as the combs have read it.
fn reverb(send: Vec<f32>) -> Vec<f32> {
    let combs = [1116usize, 1188, 1277, 1356].map(|d| d * SAMPLE_RATE as usize / 44_100);
    let mut out = vec![0.0f32; send.len()];
    for d in combs {
        let mut buf = vec![0.0f32; d];
        for (i, x) in send.iter().enumerate() {
            let y = buf[i % d];
            buf[i % d] = x + y * 0.78;
            out[i] += y * 0.25;
        }
    }
    drop(send);
    for d in [556usize, 441].map(|d| d * SAMPLE_RATE as usize / 44_100) {
        let mut buf = vec![0.0f32; d];
        for (i, sample) in out.iter_mut().enumerate() {
            let input = *sample;
            let y = buf[i % d];
            buf[i % d] = input + y * 0.5;
            *sample = y - input * 0.5;
        }
    }
    out
}

/// Notes mixed between cancel checks: a long piece has a few thousand.
const NOTES_PER_CANCEL_CHECK: usize = 64;

/// Stereo f32 with the reverb folded in, and the gain that brings its peak
/// to PEAK.
struct Mix {
    left: Vec<f32>,
    right: Vec<f32>,
    gain: f64,
}

/// Mix `score`. None when `cancel` is raised part way.
///
/// Peak memory for a 5-minute piece at 22.05 kHz (6.6 M frames) is four
/// f32 buffers while the reverb combs run, about 106 MB; the output buffer
/// is only allocated after the send and the wet signal are gone.
fn mix(score: &Score, cancel: &AtomicBool) -> Option<Mix> {
    let sr = SAMPLE_RATE as f64;
    let frames = (score.duration_s() * sr).ceil() as usize;
    let mut left = vec![0.0f32; frames];
    let mut right = vec![0.0f32; frames];
    let mut send = vec![0.0f32; frames];
    let beat_s = 60.0 / score.bpm;
    let mut rng = Rng::new(score.notes.len() as u64 ^ score.bpm.to_bits());
    for (n, note) in score.notes.iter().enumerate() {
        if n % NOTES_PER_CANCEL_CHECK == 0 && cancel.load(Ordering::Relaxed) {
            return None;
        }
        let start = (note.start_beat * beat_s * sr) as usize;
        let samples = voice_samples(note, note.beats * beat_s, &mut rng);
        let (gl, gr) = pan(note.voice);
        let wet = matches!(note.voice, Voice::Pad | Voice::Pluck | Voice::Keys);
        for (i, s) in samples.iter().enumerate() {
            let at = start + i;
            if at >= frames {
                break;
            }
            left[at] += (s * gl) as f32;
            right[at] += (s * gr) as f32;
            if wet {
                send[at] += (s * 0.3) as f32;
            }
        }
    }
    if cancel.load(Ordering::Relaxed) {
        return None;
    }
    let wet = reverb(send);
    let mut peak = 1e-9f64;
    for ((l, r), w) in left.iter_mut().zip(right.iter_mut()).zip(&wet) {
        *l += w;
        *r += w;
        peak = peak.max(l.abs().max(r.abs()) as f64);
    }
    Some(Mix {
        left,
        right,
        gain: PEAK / peak,
    })
}

/// Every interleaved sample of `mix`, faded in and out, to `emit`.
fn emit_samples(mix: &Mix, mut emit: impl FnMut(i16)) {
    let sr = SAMPLE_RATE as f64;
    let frames = mix.left.len();
    let gain = mix.gain;
    let fade_in = (FADE_IN_S * sr) as usize;
    let fade_out = (FADE_OUT_S * sr) as usize;
    for (i, (l, r)) in mix.left.iter().zip(&mix.right).enumerate() {
        let mut env = 1.0;
        if i < fade_in {
            env *= i as f64 / fade_in as f64;
        }
        if i + fade_out > frames {
            env *= (frames - i) as f64 / fade_out as f64;
        }
        for x in [*l as f64, *r as f64] {
            emit((x * gain * env).clamp(i16::MIN as f64, i16::MAX as f64) as i16);
        }
    }
}

/// Interleaved 16-bit stereo PCM for `score`.
pub fn render(score: &Score) -> Vec<i16> {
    let Some(mix) = mix(score, &AtomicBool::new(false)) else {
        return Vec::new();
    };
    let mut pcm = Vec::with_capacity(mix.left.len() * 2);
    emit_samples(&mix, |s| pcm.push(s));
    pcm
}

/// `score` as a 16-bit stereo WAV, header and samples written in one pass
/// into one buffer. None when `cancel` is raised part way.
pub fn render_wav(score: &Score, cancel: &AtomicBool) -> Option<Vec<u8>> {
    let mix = mix(score, cancel)?;
    let mut wav = crate::wav::pcm16_header(mix.left.len() * 2, 2, SAMPLE_RATE);
    emit_samples(&mix, |s| wav.extend_from_slice(&s.to_le_bytes()));
    Some(wav)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::music_synth::{compose, StyleId};

    fn short(id: StyleId, seed: u64) -> Score {
        let mut score = compose(id, seed);
        score.total_beats = 16.0;
        score.notes.retain(|n| n.start_beat + n.beats <= 16.0);
        score
    }

    #[test]
    fn render_is_deterministic_and_stereo_length_matches() {
        let score = short(StyleId::DayDrive, 3);
        let a = render(&score);
        assert_eq!(a, render(&score));
        let frames = (score.duration_s() * SAMPLE_RATE as f64).ceil() as usize;
        assert_eq!(a.len(), frames * 2);
    }

    #[test]
    fn every_style_is_audible_and_never_clips() {
        for id in StyleId::ALL {
            let pcm = render(&short(id, 1));
            let peak = pcm.iter().map(|s| s.unsigned_abs()).max().unwrap_or(0);
            assert!(peak > 3_000, "{} is near silent", id.id());
            assert!(peak <= 29_000, "{} peaks at {peak}", id.id());
        }
    }

    #[test]
    fn the_wav_carries_exactly_the_rendered_samples() {
        let score = short(StyleId::NightDrive, 5);
        let pcm = render(&score);
        let wav = render_wav(&score, &AtomicBool::new(false)).expect("not cancelled");
        assert_eq!(wav, crate::wav::pcm16_wav(&pcm, 2, SAMPLE_RATE));
    }

    #[test]
    fn a_cancelled_render_returns_nothing() {
        let score = short(StyleId::DayDrive, 2);
        assert!(render_wav(&score, &AtomicBool::new(true)).is_none());
    }

    #[test]
    fn starts_and_ends_quiet() {
        let pcm = render(&short(StyleId::FleetOwner, 9));
        assert!(pcm[..20].iter().all(|s| s.unsigned_abs() < 600));
        assert!(pcm[pcm.len() - 20..].iter().all(|s| s.unsigned_abs() < 600));
    }

    #[test]
    #[ignore = "timing probe, run in release by hand"]
    fn a_five_minute_piece_renders_in_under_four_seconds() {
        let score = (0..200)
            .map(|seed| crate::music_synth::compose(StyleId::FleetOwner, seed))
            .max_by(|a, b| a.duration_s().total_cmp(&b.duration_s()))
            .expect("scores");
        let t = std::time::Instant::now();
        let _ = render_wav(&score, &AtomicBool::new(false));
        let s = t.elapsed().as_secs_f64();
        println!("rendered {:.0}s of music in {s:.2}s", score.duration_s());
        assert!(s < 4.0);
    }
}
