//! Synthesized music: pieces the game composes itself from a seed, for the
//! no-AI music source. Headless -- composing and rendering touch no device.

pub mod compose;
pub mod render;
pub mod rng;
pub mod style;
pub mod worker;

pub use compose::{compose, Note, Score, Voice};
pub use render::{render, SAMPLE_RATE};
pub use style::{menu_rung, menu_style, style, StyleId};
pub use worker::SynthWorker;

use crate::music::{crc32, MenuMusicProfile};

pub const CLASSIC_MENU: &str = "classic_menu_theme";
pub const CLASSIC_DAY: &str = "classic_open_road";
pub const CLASSIC_NIGHT: &str = "classic_night_haul";
/// Synthesized pieces per place in one rotation, before it laps.
pub const PIECES_PER_ROTATION: usize = 6;

/// Measured from the v1.5.0 files (ffprobe, 2026-09-21).
const CLASSICS: [(&str, &str, f64); 3] = [
    (
        CLASSIC_MENU,
        "Headlights West, from Freight Fate 1.5",
        51.833,
    ),
    (CLASSIC_DAY, "Open Road, from Freight Fate 1.5", 61.409),
    (CLASSIC_NIGHT, "Night Haul, from Freight Fate 1.5", 62.0),
];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SynthKey {
    pub style: StyleId,
    pub music_seed: i64,
    pub index: usize,
}

impl SynthKey {
    pub fn key(&self) -> String {
        format!(
            "synth_{}_{}_{}",
            self.style.id(),
            self.music_seed,
            self.index
        )
    }

    pub fn parse(key: &str) -> Option<SynthKey> {
        let rest = key.strip_prefix("synth_")?;
        let (head, index) = rest.rsplit_once('_')?;
        let (style, seed) = head.rsplit_once('_')?;
        Some(SynthKey {
            style: StyleId::from_id(style)?,
            music_seed: seed.parse().ok()?,
            index: index.parse().ok()?,
        })
    }

    pub fn seed(&self) -> u64 {
        rng::piece_seed(self.style, self.music_seed, self.index)
    }
}

pub fn classic_for(style: StyleId) -> &'static str {
    match style {
        StyleId::NightMenu | StyleId::NightDrive => CLASSIC_NIGHT,
        StyleId::DayDrive => CLASSIC_DAY,
        _ => CLASSIC_MENU,
    }
}

pub fn track_title(key: &str) -> Option<String> {
    if let Some(k) = SynthKey::parse(key) {
        return Some(format!(
            "Synthesized: {}, number {}",
            style(k.style).title,
            k.index + 1
        ));
    }
    CLASSICS
        .iter()
        .find(|(k, _, _)| *k == key)
        .map(|(_, title, _)| title.to_string())
}

/// Length of a synth or classic key without rendering anything.
pub fn duration_s(key: &str) -> Option<f64> {
    if let Some(k) = SynthKey::parse(key) {
        return Some(compose(k.style, k.seed()).duration_s());
    }
    CLASSICS
        .iter()
        .find(|(k, _, _)| *k == key)
        .map(|(_, _, d)| *d)
}

fn pieces(style_id: StyleId, music_seed: i64) -> impl Iterator<Item = String> {
    (0..PIECES_PER_ROTATION).map(move |index| {
        SynthKey {
            style: style_id,
            music_seed,
            index,
        }
        .key()
    })
}

/// `crc_ordered` for plain keys: a stable shuffle by seed.
fn shuffled(mut keys: Vec<String>, seed_key: &str) -> Vec<String> {
    keys.sort_by_key(|k| crc32(format!("{seed_key}|{k}").as_bytes()));
    keys
}

/// The menu rotation: Headlights West first for a brand-new career, else the
/// place's first piece; then the rest of the pieces and the classic in a
/// stable order.
pub fn select_synth_menu_sequence(
    profile: Option<&dyn MenuMusicProfile>,
    music_seed: i64,
) -> Vec<String> {
    let place = menu_style(profile);
    let mut all: Vec<String> = pieces(place, music_seed).collect();
    let classic = classic_for(place).to_string();
    let lead = if place == StyleId::NewHire {
        classic.clone()
    } else {
        all.remove(0)
    };
    if lead != classic {
        all.push(classic);
    }
    let rest = shuffled(all, &format!("{music_seed}|{}", place.id()));
    std::iter::once(lead).chain(rest).collect()
}

/// The Roadhouse's day or night playlist in Synthesized mode.
pub fn select_synth_drive_sequence(night: bool, music_seed: i64, trip_seed: i64) -> Vec<String> {
    let place = if night {
        StyleId::NightDrive
    } else {
        StyleId::DayDrive
    };
    let mut all: Vec<String> = pieces(place, music_seed).collect();
    all.push(classic_for(place).to_string());
    shuffled(all, &format!("{music_seed}|{trip_seed}|{}", place.id()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keys_round_trip() {
        let k = SynthKey {
            style: StyleId::TopHand,
            music_seed: 48213,
            index: 3,
        };
        assert_eq!(k.key(), "synth_company_top_hand_48213_3");
        assert_eq!(SynthKey::parse(&k.key()), Some(k));
        assert_eq!(SynthKey::parse("open_road"), None);
        assert_eq!(SynthKey::parse("synth_nope_1_1"), None);
    }

    #[test]
    fn titles_are_spoken_text() {
        assert_eq!(
            track_title("synth_first_run_48213_2").as_deref(),
            Some("Synthesized: First Run, number 3")
        );
        assert_eq!(
            track_title(CLASSIC_MENU).as_deref(),
            Some("Headlights West, from Freight Fate 1.5")
        );
        assert_eq!(track_title("open_road"), None);
    }

    #[test]
    fn durations_are_known_without_rendering() {
        let key = SynthKey {
            style: StyleId::DayDrive,
            music_seed: 1,
            index: 0,
        }
        .key();
        let expected =
            compose(StyleId::DayDrive, rng::piece_seed(StyleId::DayDrive, 1, 0)).duration_s();
        assert_eq!(crate::music::music_track_duration_s(&key), expected);
        assert!((crate::music::music_track_duration_s(CLASSIC_DAY) - 61.41).abs() < 0.01);
        assert_eq!(crate::music::known_track_duration_s("player_x"), None);
    }

    #[test]
    fn a_new_career_opens_on_headlights_west_and_holds_only_synth_music() {
        let seq = select_synth_menu_sequence(None, 48213);
        assert_eq!(seq[0], CLASSIC_MENU);
        assert_eq!(seq.len(), 1 + PIECES_PER_ROTATION);
        assert!(seq[1..]
            .iter()
            .all(|k| SynthKey::parse(k).is_some_and(|s| s.style == StyleId::NewHire)));
    }

    #[test]
    fn the_seed_changes_every_piece() {
        let a = select_synth_drive_sequence(false, 1, 7);
        let b = select_synth_drive_sequence(false, 2, 7);
        assert!(a.contains(&CLASSIC_DAY.to_string()));
        assert!(a
            .iter()
            .filter(|k| k.starts_with("synth_"))
            .all(|k| !b.contains(k)));
        assert!(select_synth_drive_sequence(true, 1, 7).contains(&CLASSIC_NIGHT.to_string()));
    }
}
