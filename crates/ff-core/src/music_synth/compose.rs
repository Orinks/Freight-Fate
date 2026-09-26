//! A score from a style and a seed: sections, one chord per bar, a bass line,
//! a melody over the chords, drums where the style has them. The A section's
//! melody is written once and repeated, so a piece has a tune to come back to.
//! Each style layers its own extra voices (`Style::extras`) over that. They
//! draw on a separate RNG, so a seed still writes the notes it always wrote;
//! the reed only changes which voice plays the B sections' tune.

use super::rng::Rng;
use super::style::{style, Drums, Lead, Style, StyleId};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Voice {
    Pad,
    Pluck,
    Keys,
    Bass,
    Kick,
    Snare,
    Hat,
    /// Guitar chop: a strummed chord on beats two and four.
    Strum,
    /// Drawbar organ: held chords that lift the back half of each section.
    Organ,
    /// A bell answering the tune from above, every other bar.
    Bell,
    /// Harmonica-like reed: takes the B sections' tune from the lead.
    Reed,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Note {
    pub start_beat: f64,
    pub beats: f64,
    pub midi: i32,
    pub velocity: f32,
    pub voice: Voice,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Score {
    pub style: StyleId,
    pub bpm: f64,
    pub total_beats: f64,
    pub notes: Vec<Note>,
}

/// Release tail rendered after the last beat.
pub const TAIL_S: f64 = 2.5;
const BEATS_PER_BAR: f64 = 4.0;

/// One section of the plan: its bar-by-bar chords, an optional melody (beat
/// offset in section, beats, degree), and whether drums play under it.
type Section = (Vec<usize>, Option<Vec<(f64, f64, i32)>>, bool);

impl Score {
    pub fn duration_s(&self) -> f64 {
        self.total_beats * 60.0 / self.bpm + TAIL_S
    }
}

/// MIDI note of scale degree `degree` (any integer; wraps octaves) above `root`.
fn degree_midi(s: &Style, degree: i32) -> i32 {
    let iv = s.mode.intervals();
    let octave = degree.div_euclid(7);
    s.root + 12 * octave + iv[degree.rem_euclid(7) as usize]
}

/// The eight-bar melody over `chords`, as (beat offset in section, beats, degree).
fn write_melody(rng: &mut Rng, s: &Style, chords: &[usize]) -> Vec<(f64, f64, i32)> {
    let mut out = Vec::new();
    // Melody lives two octaves over the bass root: degrees 14..=24.
    let mut degree: i32 = 14 + 2 * chords[0] as i32 % 7;
    for (bar, chord) in chords.iter().enumerate() {
        let rhythm: &[f64] = match rng.below(4) {
            0 => &[1.0, 1.0, 1.0, 1.0],
            1 => &[1.5, 0.5, 1.0, 1.0],
            2 => &[0.5, 0.5, 1.0, 2.0],
            _ => &[2.0, 1.0, 1.0],
        };
        let mut beat = 0.0;
        for (i, len) in rhythm.iter().enumerate() {
            let strong = i == 0;
            if strong {
                // Land on a chord tone: root, third or fifth of this bar's chord.
                let tone = [0, 2, 4][rng.below(3)];
                let target = 14 + *chord as i32 + tone;
                degree = if (target - degree).abs() > 3 {
                    target
                } else {
                    degree + (target - degree).signum()
                };
            } else {
                degree += [-2, -1, -1, 1, 1, 2][rng.below(6)];
            }
            degree = degree.clamp(12, 24);
            if strong || !rng.chance(s.rest) {
                out.push((bar as f64 * BEATS_PER_BAR + beat, *len, degree));
            }
            beat += len;
        }
    }
    out
}

pub fn compose(id: StyleId, seed: u64) -> Score {
    let s = style(id);
    let mut rng = Rng::new(seed);
    let bpm = s.bpm.0 + (s.bpm.1 - s.bpm.0) * rng.unit();
    let bar_s = BEATS_PER_BAR * 60.0 / bpm;
    // Lengths vary piece to piece, 90 s to 5 min, weighted toward the middle
    // (the mean of two draws), so short interludes and long drives both turn up.
    let target_s = 90.0 + 210.0 * 0.5 * (rng.unit() + rng.unit());
    // intro 4, then 8-bar A/B sections alternating from A, outro 4.
    let body_bars = (((target_s - TAIL_S) / bar_s) as usize)
        .saturating_sub(8)
        .max(8);
    let sections = (body_bars / 8).max(1);

    let prog_a = s.progressions[rng.below(s.progressions.len())];
    let prog_b = s.progressions[rng.below(s.progressions.len())];
    let chords_of =
        |prog: &[usize]| -> Vec<usize> { (0..8).map(|i| prog[i % prog.len()]).collect() };
    let (chords_a, chords_b) = (chords_of(prog_a), chords_of(prog_b));
    let melody_a = write_melody(&mut rng, s, &chords_a);

    let mut plan: Vec<Section> = Vec::new();
    plan.push((chords_a[..4].to_vec(), None, false)); // intro: pad and bass only
    for i in 0..sections {
        if i % 2 == 0 {
            plan.push((chords_a.clone(), Some(melody_a.clone()), true));
        } else {
            let melody_b = write_melody(&mut rng, s, &chords_b);
            plan.push((chords_b.clone(), Some(melody_b), true));
        }
    }
    plan.push((vec![chords_a[0]; 4], None, false)); // outro: settle on the tonic

    let lead_voice = match s.lead {
        Lead::Pluck => Voice::Pluck,
        Lead::Keys => Voice::Keys,
    };
    let has = |v: Voice| s.extras.contains(&v);
    let mut extra_rng = Rng::new(seed ^ 0xE7_7A5_u64.rotate_left(32));
    let mut notes = Vec::new();
    let mut bar0 = 0.0;
    for (n, (chords, melody, drums_on)) in plan.iter().enumerate() {
        // plan[0] is the intro, then A, B, A, ...; the outro has no drums.
        let b_section = *drums_on && n % 2 == 0;
        for (bar, chord) in chords.iter().enumerate() {
            let at = bar0 + bar as f64 * BEATS_PER_BAR;
            let c = *chord as i32;
            for tone in [0, 2, 4] {
                notes.push(Note {
                    start_beat: at,
                    beats: BEATS_PER_BAR,
                    midi: degree_midi(s, 7 + c + tone),
                    velocity: 0.28,
                    voice: Voice::Pad,
                });
            }
            notes.push(Note {
                start_beat: at,
                beats: 1.5,
                midi: degree_midi(s, c),
                velocity: 0.7,
                voice: Voice::Bass,
            });
            notes.push(Note {
                start_beat: at + 2.0,
                beats: 1.5,
                midi: degree_midi(s, c + if rng.chance(0.5) { 4 } else { 0 }),
                velocity: 0.6,
                voice: Voice::Bass,
            });
            if *drums_on && s.drums != Drums::None {
                for beat in 0..4 {
                    let b = at + beat as f64;
                    if s.drums == Drums::Kit && beat % 2 == 0 {
                        notes.push(Note {
                            start_beat: b,
                            beats: 0.5,
                            midi: 36,
                            velocity: 0.8,
                            voice: Voice::Kick,
                        });
                    }
                    if beat % 2 == 1 {
                        notes.push(Note {
                            start_beat: b,
                            beats: 0.5,
                            midi: 38,
                            velocity: if s.drums == Drums::Kit { 0.6 } else { 0.35 },
                            voice: Voice::Snare,
                        });
                    }
                    notes.push(Note {
                        start_beat: b,
                        beats: 0.25,
                        midi: 42,
                        velocity: 0.25,
                        voice: Voice::Hat,
                    });
                    notes.push(Note {
                        start_beat: b + 0.5 + s.swing * 0.5,
                        beats: 0.25,
                        midi: 42,
                        velocity: 0.18,
                        voice: Voice::Hat,
                    });
                }
            }
            if *drums_on && has(Voice::Strum) {
                // Beats two and four, the three chord tones a few ms apart.
                for beat in [1.0, 3.0] {
                    for (k, tone) in [0, 2, 4].into_iter().enumerate() {
                        notes.push(Note {
                            start_beat: at + beat + 0.03 * k as f64,
                            beats: 0.4,
                            midi: degree_midi(s, 7 + c + tone),
                            velocity: 0.3,
                            voice: Voice::Strum,
                        });
                    }
                }
            }
            if *drums_on && bar >= 4 && has(Voice::Organ) {
                for tone in [0, 2, 4] {
                    notes.push(Note {
                        start_beat: at,
                        beats: BEATS_PER_BAR,
                        midi: degree_midi(s, 7 + c + tone),
                        velocity: 0.16,
                        voice: Voice::Organ,
                    });
                }
            }
            if *drums_on && bar % 2 == 1 && has(Voice::Bell) {
                // A chord tone an octave over the tune, on the bar's last beat.
                let tone = [0, 2, 4][extra_rng.below(3)];
                notes.push(Note {
                    start_beat: at + 3.0,
                    beats: 1.0,
                    midi: degree_midi(s, 21 + c + tone),
                    velocity: 0.22,
                    voice: Voice::Bell,
                });
            }
        }
        if let Some(melody) = melody {
            let voice = if b_section && has(Voice::Reed) {
                Voice::Reed
            } else {
                lead_voice
            };
            for (offset, len, degree) in melody {
                let velocity = 0.45 + 0.2 * rng.unit() as f32;
                notes.push(Note {
                    start_beat: bar0 + offset,
                    beats: *len,
                    midi: degree_midi(s, *degree),
                    velocity,
                    voice,
                });
            }
        }
        bar0 += chords.len() as f64 * BEATS_PER_BAR;
    }
    Score {
        style: id,
        bpm,
        total_beats: bar0,
        notes,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_seed_same_score() {
        assert_eq!(
            compose(StyleId::DayDrive, 99),
            compose(StyleId::DayDrive, 99)
        );
    }

    #[test]
    fn every_style_is_the_same_piece_for_the_same_seed() {
        for id in StyleId::ALL {
            assert_eq!(compose(id, 1234), compose(id, 1234), "{}", id.id());
        }
    }

    #[test]
    fn every_style_plays_at_least_two_extra_voices() {
        use std::collections::HashSet;
        for id in StyleId::ALL {
            let extras = style(id).extras;
            assert!(extras.len() >= 2, "{} has {extras:?}", id.id());
            for seed in 0..3 {
                let voices: HashSet<Voice> =
                    compose(id, seed).notes.iter().map(|n| n.voice).collect();
                for v in extras {
                    assert!(voices.contains(v), "{} lacks {v:?}", id.id());
                }
                // Pad, lead and bass, plus the extras.
                assert!(voices.len() >= 3 + extras.len(), "{}: {voices:?}", id.id());
            }
        }
    }

    #[test]
    fn different_seeds_differ() {
        assert_ne!(
            compose(StyleId::DayDrive, 1).notes,
            compose(StyleId::DayDrive, 2).notes
        );
    }

    #[test]
    fn every_style_lasts_ninety_seconds_to_five_minutes_in_its_tempo() {
        for id in StyleId::ALL {
            for seed in 0..4 {
                let score = compose(id, seed);
                let (lo, hi) = style(id).bpm;
                assert!(
                    (lo..=hi).contains(&score.bpm),
                    "{} bpm {}",
                    id.id(),
                    score.bpm
                );
                let d = score.duration_s();
                assert!((85.0..=310.0).contains(&d), "{} lasts {d}", id.id());
                assert!(score
                    .notes
                    .iter()
                    .all(|n| n.start_beat + n.beats <= score.total_beats + 1e-9));
            }
        }
    }

    #[test]
    fn lengths_vary_from_piece_to_piece() {
        let lengths: Vec<f64> = (0..20)
            .map(|seed| compose(StyleId::DayDrive, seed).duration_s())
            .collect();
        let (lo, hi) = lengths
            .iter()
            .fold((f64::MAX, 0.0f64), |(lo, hi), d| (lo.min(*d), hi.max(*d)));
        assert!(hi - lo > 90.0, "lengths only span {lo:.0} to {hi:.0} s");
    }

    #[test]
    fn drum_free_styles_have_no_drums_and_kit_styles_do() {
        let no_drums = compose(StyleId::NightDrive, 5);
        assert!(no_drums
            .notes
            .iter()
            .all(|n| !matches!(n.voice, Voice::Kick | Voice::Snare | Voice::Hat)));
        let kit = compose(StyleId::FleetOwner, 5);
        assert!(kit.notes.iter().any(|n| n.voice == Voice::Kick));
    }

    #[test]
    fn melody_stays_in_its_scale() {
        let score = compose(StyleId::Regional, 11);
        let s = style(StyleId::Regional);
        let scale: Vec<i32> = s.mode.intervals().to_vec();
        for n in score
            .notes
            .iter()
            .filter(|n| !matches!(n.voice, Voice::Kick | Voice::Snare | Voice::Hat))
        {
            assert!(
                scale.contains(&(n.midi - s.root).rem_euclid(12)),
                "{} out of scale",
                n.midi
            );
        }
    }
}
