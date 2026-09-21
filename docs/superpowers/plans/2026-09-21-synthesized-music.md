# Synthesized Music Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "Music source: Synthesized" setting that swaps menu music and the Roadhouse station for music the game composes itself from a seed, plus the three restored 1.5 synth tracks and any hand-made tracker modules.

**Architecture:** A headless `ff_core::music_synth` module composes a `Score` from a `Style` and a seed and renders it to 16-bit PCM; a worker thread (also in ff-core, no audio device) renders requested pieces off the game loop and publishes them with `register_generated_sound`. The game side substitutes synth keys into the existing menu rotation and Roadhouse playlist, falls back to a classic when a piece is not ready, and plays tracker modules through `BASS_MusicLoad`.

**Tech Stack:** Rust (pinned toolchain), ff-core / freight-fate crates, BASS via `bass-sys`. No new crates.

**Spec:** `docs/superpowers/specs/2026-09-21-synthesized-music-design.md`

**Deviation from spec, approved in the handoff:** the three classics are compiled into the executable with `include_bytes!` and registered as generated sounds at startup, instead of being repacked into `sounds.pak`. Repacking `sounds.pak` needs the licensed-sound overlay installed and risks shipping a pack without it; the classics are 1.9 MB total and already public in git history.

## Global Constraints

- Gameplay code is Rust. No Python gameplay changes, no new Python tests.
- `ff-core` gains no audio, window, network or screen-reader dependency. Threads are allowed; audio devices are not.
- Never block the game loop on a render. Bounded channels; define what is dropped.
- No `unwrap`/`expect` on fallible runtime data (files, player folder, BASS). Log and skip.
- Files stay at or under 1000 lines. Rust sources are CRLF: edit with the Edit tool, never perl/sed.
- Gates, in this order, at the end: `cargo fmt --all --check`, `cargo clippy --all-targets --locked -- -D warnings`, `cargo test -p ff-core -p freight-fate` (once, at the end, backgrounded), `cargo run -p freight-fate --bin freightfate -- --break-battery`.
- Focused tests while iterating: `cargo test -p ff-core music_synth` and `cargo test -p freight-fate --test it synth_music`.
- Exactly one cargo test run in flight at a time.
- Spoken strings, exact:
  - Source row label: `Music source: Original` / `Music source: Synthesized`
  - Source row help: `Synthesized plays menu music and the Roadhouse station made by the game itself, with no AI-made songs or voices. Original plays the full soundtrack.`
  - Seed row label: `Music seed: {seed}`
  - Seed row help: `Enter rolls a new seed. Every synthesized piece changes with it.`
  - Seed roll line: `New music seed, {seed}. Every synthesized piece is new.`
  - Synth piece title: `Synthesized: {style title}, number {n}` (n is 1-based track index)
  - Classic titles: `Headlights West, from Freight Fate 1.5`, `Open Road, from Freight Fate 1.5`, `Night Haul, from Freight Fate 1.5`
- Canonical noun: "synthesized music" (add to `docs/ontology.md`).
- Commit messages: conventional prefix, `[skip changelog]` on every commit except the one that adds CHANGELOG bullets (Task 13), and the attribution line `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- Stage explicit paths only; never `git add -A` (licensed sound overlay).

## File Structure

| File | Responsibility |
|---|---|
| `crates/ff-core/src/music_synth.rs` | Module root: keys (`synth_<style>_<seed>`), titles, durations, sequence selection |
| `crates/ff-core/src/music_synth/rng.rs` | Stable SplitMix64 RNG and seed hashing |
| `crates/ff-core/src/music_synth/style.rs` | `StyleId`, `Style`, the 14-style table, rung ladder |
| `crates/ff-core/src/music_synth/compose.rs` | `Score`, `Note`, `Voice`, `compose(style, seed)` |
| `crates/ff-core/src/music_synth/render.rs` | `render(&Score) -> Vec<i16>` (22,050 Hz stereo) |
| `crates/ff-core/src/music_synth/worker.rs` | `SynthWorker`: bounded request channel, render thread, shutdown |
| `crates/ff-core/src/wav.rs` | Shared `pcm16_wav(samples, channels, rate)`; siren and ladder earcons switch to it |
| `crates/ff-core/src/music.rs` | `MenuMusicProfile::business_status`; runtime duration registry |
| `crates/ff-core/src/settings.rs` | `synth_music`, `music_seed` settings |
| `crates/freight-fate/assets/classic_music/*.ogg` | The three restored 1.5 tracks |
| `crates/freight-fate/src/audio/classic_music.rs` | Embeds and registers the classics |
| `crates/freight-fate/src/audio/hand_made.rs` | Scans shipped + player tracker modules, registers them per place |
| `crates/freight-fate/src/app/context.rs` | Owns `SynthWorker`; menu substitution; `restart_music` |
| `crates/freight-fate/src/states/driving_updates/radio.rs` | Roadhouse substitution, break suppression, now-playing title |
| `crates/ff-core/src/radio_rotation.rs` | `StationRotation::breaks` flag |
| `crates/bass-sys/src/{lib,loader,safe}.rs` | `BASS_MusicLoad` / `BASS_MusicFree` |
| `crates/freight-fate/src/audio/{bass.rs,assets.rs,bass_radio.rs}` | Module playback, module extensions, playing-length query |
| `crates/freight-fate/src/states/main_menu/{settings_items,settings_actions}.rs` | The two rows |

---

### Task 1: Stable RNG, styles and the career ladder

**Files:**
- Create: `crates/ff-core/src/music_synth.rs`, `crates/ff-core/src/music_synth/rng.rs`, `crates/ff-core/src/music_synth/style.rs`
- Modify: `crates/ff-core/src/lib.rs` (add `pub mod music_synth;` after `pub mod music;`)
- Modify: `crates/ff-core/src/music.rs:71-82` (trait gains `business_status`), test fake at `:269-324`
- Modify: `crates/ff-core/src/models/profile/traits.rs:298-323` (impl)

**Interfaces:**
- Produces: `music_synth::rng::Rng { fn new(seed: u64) -> Rng; fn next_u64(&mut self) -> u64; fn unit(&mut self) -> f64; fn below(&mut self, n: usize) -> usize; fn chance(&mut self, p: f64) -> bool }`, `rng::piece_seed(style: StyleId, music_seed: i64, index: usize) -> u64`
- Produces: `style::StyleId` (enum, 14 variants, `fn id(self) -> &'static str`, `fn from_id(&str) -> Option<StyleId>`, `const ALL: [StyleId; 14]`), `style::Style` (fields below), `style::style(StyleId) -> &'static Style`, `style::menu_style(profile: Option<&dyn MenuMusicProfile>) -> StyleId`
- Produces: `MenuMusicProfile::business_status(&self) -> String`

- [ ] **Step 1: Add `business_status` to the profile trait**

In `crates/ff-core/src/music.rs`, inside `pub trait MenuMusicProfile`, after `fn current_city(&self) -> String;`:

```rust
    /// `profile.business_status`: company driver, leased owner-operator or
    /// independent authority. The synthesized ladder splits on it.
    fn business_status(&self) -> String;
```

In the test `FakeProfile` add a `business_status: String` field, default it in `named()` to `crate::models::business_constants::COMPANY_DRIVER.to_string()`, and implement:

```rust
        fn business_status(&self) -> String {
            self.business_status.clone()
        }
```

In `crates/ff-core/src/models/profile/traits.rs`, inside `impl MenuMusicProfile for Profile`:

```rust
    fn business_status(&self) -> String {
        self.business_status.clone()
    }
```

- [ ] **Step 2: Write the RNG with a pinned-sequence test**

`crates/ff-core/src/music_synth/rng.rs`:

```rust
//! The synthesizer's own RNG. Deliberately not `pyrandom`: a piece must never
//! change once shipped, so this is a fixed SplitMix64 with no Python mirror to
//! stay in step with.

use super::style::StyleId;

#[derive(Debug, Clone)]
pub struct Rng(u64);

impl Rng {
    pub fn new(seed: u64) -> Self {
        Self(seed)
    }

    pub fn next_u64(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// Uniform in [0, 1).
    pub fn unit(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64
    }

    /// Uniform in 0..n; 0 when n is 0.
    pub fn below(&mut self, n: usize) -> usize {
        if n == 0 {
            return 0;
        }
        (self.next_u64() % n as u64) as usize
    }

    pub fn chance(&mut self, p: f64) -> bool {
        self.unit() < p
    }
}

/// The seed one piece is composed from: which place, which music seed, which
/// track in that place's rotation.
pub fn piece_seed(style: StyleId, music_seed: i64, index: usize) -> u64 {
    let mut rng = Rng::new(crate::music::crc32(style.id().as_bytes()) as u64);
    let mixed = rng.next_u64() ^ (music_seed as u64).rotate_left(21) ^ (index as u64).rotate_left(42);
    Rng::new(mixed).next_u64()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn splitmix_sequence_is_pinned() {
        let mut rng = Rng::new(1);
        let got: Vec<u64> = (0..3).map(|_| rng.next_u64()).collect();
        assert_eq!(got, vec![0x910A_2DEC_8902_5CC1, 0xBEEB_8DA1_658E_EC67, 0xF893_A2EE_FB32_555E]);
    }

    #[test]
    fn below_stays_in_range_and_zero_is_safe() {
        let mut rng = Rng::new(7);
        assert!((0..1000).all(|_| rng.below(5) < 5));
        assert_eq!(rng.below(0), 0);
    }

    #[test]
    fn piece_seed_changes_with_each_input() {
        let a = piece_seed(StyleId::DayDrive, 48213, 0);
        assert_ne!(a, piece_seed(StyleId::DayDrive, 48214, 0));
        assert_ne!(a, piece_seed(StyleId::DayDrive, 48213, 1));
        assert_ne!(a, piece_seed(StyleId::NightDrive, 48213, 0));
        assert_eq!(a, piece_seed(StyleId::DayDrive, 48213, 0));
    }
}
```

(The three pinned values are SplitMix64's published outputs for seed 1; if the assertion fails, the RNG is wrong, not the test.)

- [ ] **Step 3: Write the style table and ladder**

`crates/ff-core/src/music_synth/style.rs`:

```rust
//! One musical identity per place the synthesized music plays.

use crate::models::business_constants::is_owner_operator;
use crate::music::{is_night, MenuMusicProfile};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum StyleId {
    NewHire,
    FirstRun,
    Regional,
    SeniorCompany,
    TopHand,
    Trainer,
    MillionMile,
    FleetOwner,
    CoastToCoast,
    LegendaryHaul,
    RoadLegend,
    NightMenu,
    DayDrive,
    NightDrive,
}

impl StyleId {
    pub const ALL: [StyleId; 14] = [
        StyleId::NewHire,
        StyleId::FirstRun,
        StyleId::Regional,
        StyleId::SeniorCompany,
        StyleId::TopHand,
        StyleId::Trainer,
        StyleId::MillionMile,
        StyleId::FleetOwner,
        StyleId::CoastToCoast,
        StyleId::LegendaryHaul,
        StyleId::RoadLegend,
        StyleId::NightMenu,
        StyleId::DayDrive,
        StyleId::NightDrive,
    ];

    /// Stable id: used in asset keys and folder names. Never rename one.
    pub fn id(self) -> &'static str {
        style(self).id
    }

    pub fn from_id(id: &str) -> Option<StyleId> {
        Self::ALL.into_iter().find(|s| s.id() == id)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    Major,
    Minor,
    Dorian,
    Mixolydian,
}

impl Mode {
    /// Semitone offsets of the seven scale degrees.
    pub fn intervals(self) -> [i32; 7] {
        match self {
            Mode::Major => [0, 2, 4, 5, 7, 9, 11],
            Mode::Minor => [0, 2, 3, 5, 7, 8, 10],
            Mode::Dorian => [0, 2, 3, 5, 7, 9, 10],
            Mode::Mixolydian => [0, 2, 4, 5, 7, 9, 10],
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Lead {
    Pluck,
    Keys,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Drums {
    None,
    Brushes,
    Kit,
}

#[derive(Debug)]
pub struct Style {
    pub id: &'static str,
    /// Spoken in the synth piece title.
    pub title: &'static str,
    /// MIDI note of the tonic in the bass octave (e.g. 43 = G2).
    pub root: i32,
    pub mode: Mode,
    pub bpm: (f64, f64),
    /// Progressions as 0-based scale degrees, one chord per bar.
    pub progressions: &'static [&'static [usize]],
    pub lead: Lead,
    pub drums: Drums,
    /// 0 = straight eighths, up to ~0.3 = shuffled.
    pub swing: f64,
    /// Chance a melody slot is a rest; higher is sparser and calmer.
    pub rest: f64,
}

const WARM: &[&[usize]] = &[&[0, 4, 5, 3], &[0, 3, 4, 3], &[0, 5, 3, 4], &[0, 3, 0, 4]];
const OPEN: &[&[usize]] = &[&[0, 6, 3, 0], &[0, 4, 3, 0], &[0, 3, 6, 4], &[0, 6, 5, 4]];
const MOODY: &[&[usize]] = &[&[0, 5, 2, 6], &[0, 3, 4, 0], &[0, 5, 3, 4], &[0, 6, 5, 6]];

static STYLES: [Style; 14] = [
    Style { id: "new_hire", title: "New Hire", root: 43, mode: Mode::Major, bpm: (72.0, 80.0), progressions: WARM, lead: Lead::Pluck, drums: Drums::None, swing: 0.0, rest: 0.35 },
    Style { id: "first_run", title: "First Run", root: 45, mode: Mode::Major, bpm: (84.0, 92.0), progressions: WARM, lead: Lead::Pluck, drums: Drums::Brushes, swing: 0.1, rest: 0.3 },
    Style { id: "regional", title: "Regional", root: 38, mode: Mode::Mixolydian, bpm: (90.0, 98.0), progressions: OPEN, lead: Lead::Pluck, drums: Drums::Brushes, swing: 0.15, rest: 0.25 },
    Style { id: "company_senior", title: "Senior Driver", root: 41, mode: Mode::Major, bpm: (76.0, 84.0), progressions: WARM, lead: Lead::Keys, drums: Drums::Brushes, swing: 0.1, rest: 0.35 },
    Style { id: "company_top_hand", title: "Top Hand", root: 43, mode: Mode::Major, bpm: (80.0, 88.0), progressions: WARM, lead: Lead::Keys, drums: Drums::Brushes, swing: 0.2, rest: 0.3 },
    Style { id: "company_trainer", title: "Trainer", root: 40, mode: Mode::Dorian, bpm: (78.0, 86.0), progressions: MOODY, lead: Lead::Keys, drums: Drums::Brushes, swing: 0.15, rest: 0.35 },
    Style { id: "company_million_mile", title: "Million Mile", root: 45, mode: Mode::Major, bpm: (84.0, 92.0), progressions: OPEN, lead: Lead::Keys, drums: Drums::Kit, swing: 0.1, rest: 0.3 },
    Style { id: "owner_fleet", title: "Fleet Owner", root: 40, mode: Mode::Mixolydian, bpm: (96.0, 104.0), progressions: OPEN, lead: Lead::Pluck, drums: Drums::Kit, swing: 0.0, rest: 0.2 },
    Style { id: "owner_coast_to_coast", title: "Coast to Coast", root: 42, mode: Mode::Major, bpm: (100.0, 110.0), progressions: OPEN, lead: Lead::Pluck, drums: Drums::Kit, swing: 0.05, rest: 0.2 },
    Style { id: "owner_legendary_haul", title: "Legendary Haul", root: 38, mode: Mode::Dorian, bpm: (96.0, 106.0), progressions: MOODY, lead: Lead::Pluck, drums: Drums::Kit, swing: 0.0, rest: 0.2 },
    Style { id: "owner_road_legend", title: "Road Legend", root: 43, mode: Mode::Mixolydian, bpm: (104.0, 112.0), progressions: OPEN, lead: Lead::Keys, drums: Drums::Kit, swing: 0.1, rest: 0.18 },
    Style { id: "night_menu", title: "Midnight Terminal", root: 45, mode: Mode::Minor, bpm: (64.0, 72.0), progressions: MOODY, lead: Lead::Keys, drums: Drums::None, swing: 0.0, rest: 0.45 },
    Style { id: "drive_day", title: "Day Drive", root: 45, mode: Mode::Major, bpm: (88.0, 100.0), progressions: OPEN, lead: Lead::Pluck, drums: Drums::Brushes, swing: 0.1, rest: 0.25 },
    Style { id: "drive_night", title: "Night Drive", root: 45, mode: Mode::Minor, bpm: (66.0, 76.0), progressions: MOODY, lead: Lead::Keys, drums: Drums::None, swing: 0.0, rest: 0.4 },
];

pub fn style(id: StyleId) -> &'static Style {
    let index = StyleId::ALL.iter().position(|s| *s == id).unwrap_or(0);
    &STYLES[index]
}

/// The synthesized ladder: today's thresholds rung for rung, split on
/// business status from rung 3, and rung 1 earned by driving rather than by
/// the tractor (a company driver's carrier tractor is not a milestone).
pub fn menu_rung(profile: Option<&dyn MenuMusicProfile>) -> StyleId {
    let Some(p) = profile else {
        return StyleId::NewHire;
    };
    let (level, deliveries, miles) = (p.level(), p.deliveries(), p.total_miles());
    let owner = is_owner_operator(&p.business_status());
    let branch = |company: StyleId, owner_style: StyleId| if owner { owner_style } else { company };
    if level >= 21 || deliveries >= 75 || miles >= 40_000.0 {
        return branch(StyleId::MillionMile, StyleId::RoadLegend);
    }
    if level >= 9 || deliveries >= 40 || miles >= 20_000.0 {
        return branch(StyleId::Trainer, StyleId::LegendaryHaul);
    }
    if level >= 7 || miles >= 10_000.0 {
        return branch(StyleId::TopHand, StyleId::CoastToCoast);
    }
    if level >= 5 || p.owned_truck_count() >= 2 {
        return branch(StyleId::SeniorCompany, StyleId::FleetOwner);
    }
    if level >= 3 || miles >= 2_500.0 {
        return StyleId::Regional;
    }
    if level >= 2 || deliveries >= 3 {
        return StyleId::FirstRun;
    }
    StyleId::NewHire
}

/// The style a menu plays right now: the night menu after dark, else the rung.
pub fn menu_style(profile: Option<&dyn MenuMusicProfile>) -> StyleId {
    if profile.is_some_and(|p| is_night(p.game_hours() % 24.0)) {
        return StyleId::NightMenu;
    }
    menu_rung(profile)
}
```

Note the `#[rustfmt::skip]` is not used: run `cargo fmt` and accept its layout of the table.

`crates/ff-core/src/music_synth.rs` (module root for now):

```rust
//! Synthesized music: pieces the game composes itself from a seed, for the
//! no-AI music source. Headless -- composing and rendering touch no device.

pub mod rng;
pub mod style;

pub use style::{menu_rung, menu_style, style, StyleId};
```

- [ ] **Step 4: Write the ladder tests**

Append to `style.rs`:

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::business_constants::{COMPANY_DRIVER, INDEPENDENT_AUTHORITY, LEASED_OWNER_OPERATOR};

    struct P {
        level: i64,
        deliveries: i64,
        miles: f64,
        owned: usize,
        truck: &'static str,
        status: &'static str,
        hours: f64,
    }

    impl MenuMusicProfile for P {
        fn game_hours(&self) -> f64 { self.hours }
        fn level(&self) -> i64 { self.level }
        fn deliveries(&self) -> i64 { self.deliveries }
        fn total_miles(&self) -> f64 { self.miles }
        fn owned_truck_count(&self) -> usize { self.owned }
        fn active_truck_key(&self) -> String { self.truck.into() }
        fn name(&self) -> String { "T".into() }
        fn current_city(&self) -> String { "Denver".into() }
        fn business_status(&self) -> String { self.status.into() }
    }

    fn p(level: i64, status: &'static str) -> P {
        P { level, deliveries: 0, miles: 0.0, owned: 1, truck: "rig", status, hours: 12.0 }
    }

    #[test]
    fn ids_are_unique_and_round_trip() {
        for s in StyleId::ALL {
            assert_eq!(StyleId::from_id(s.id()), Some(s));
        }
        let mut ids: Vec<_> = StyleId::ALL.iter().map(|s| s.id()).collect();
        ids.sort();
        ids.dedup();
        assert_eq!(ids.len(), 14);
    }

    #[test]
    fn company_and_owner_branches_split_from_rung_three() {
        for (level, company, owner) in [
            (5, StyleId::SeniorCompany, StyleId::FleetOwner),
            (7, StyleId::TopHand, StyleId::CoastToCoast),
            (9, StyleId::Trainer, StyleId::LegendaryHaul),
            (21, StyleId::MillionMile, StyleId::RoadLegend),
        ] {
            assert_eq!(menu_rung(Some(&p(level, COMPANY_DRIVER))), company);
            assert_eq!(menu_rung(Some(&p(level, LEASED_OWNER_OPERATOR))), owner);
            assert_eq!(menu_rung(Some(&p(level, INDEPENDENT_AUTHORITY))), owner);
        }
        assert_eq!(menu_rung(Some(&p(3, COMPANY_DRIVER))), StyleId::Regional);
        assert_eq!(menu_rung(Some(&p(3, INDEPENDENT_AUTHORITY))), StyleId::Regional);
    }

    #[test]
    fn a_carrier_tractor_alone_is_not_the_first_run() {
        let mut fresh = p(1, COMPANY_DRIVER);
        fresh.truck = "carrier_cascadia";
        assert_eq!(menu_rung(Some(&fresh)), StyleId::NewHire);
        fresh.deliveries = 3;
        assert_eq!(menu_rung(Some(&fresh)), StyleId::FirstRun);
    }

    #[test]
    fn night_menu_leads_after_dark_and_no_profile_is_new_hire() {
        let mut night = p(21, COMPANY_DRIVER);
        night.hours = 23.0;
        assert_eq!(menu_style(Some(&night)), StyleId::NightMenu);
        assert_eq!(menu_style(None), StyleId::NewHire);
    }
}
```

- [ ] **Step 5: Run the tests**

Run: `cargo test -p ff-core music_synth`
Expected: all Task 1 tests PASS. (The `business_status` trait addition also compiles the existing `music.rs` tests; run `cargo test -p ff-core music::` to confirm they still pass.)

- [ ] **Step 6: Commit**

```bash
git add crates/ff-core/src/lib.rs crates/ff-core/src/music.rs crates/ff-core/src/music_synth.rs crates/ff-core/src/music_synth/rng.rs crates/ff-core/src/music_synth/style.rs crates/ff-core/src/models/profile/traits.rs
git commit -m "feat(music): synthesized styles and a career-path ladder

[skip changelog]

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Composing a score

**Files:**
- Create: `crates/ff-core/src/music_synth/compose.rs`
- Modify: `crates/ff-core/src/music_synth.rs` (add `pub mod compose;` and `pub use compose::{compose, Note, Score, Voice};`)

**Interfaces:**
- Consumes: `Rng`, `Style`, `StyleId`, `style()` from Task 1
- Produces: `Voice { Pad, Pluck, Keys, Bass, Kick, Snare, Hat }`, `Note { start_beat: f64, beats: f64, midi: i32, velocity: f32, voice: Voice }`, `Score { style: StyleId, bpm: f64, total_beats: f64, notes: Vec<Note> }`, `Score::duration_s(&self) -> f64` (includes a 2.5 s release tail), `compose(style: StyleId, seed: u64) -> Score`

- [ ] **Step 1: Write the failing tests**

`crates/ff-core/src/music_synth/compose.rs`, test module at the bottom:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_seed_same_score() {
        assert_eq!(compose(StyleId::DayDrive, 99), compose(StyleId::DayDrive, 99));
    }

    #[test]
    fn different_seeds_differ() {
        assert_ne!(compose(StyleId::DayDrive, 1).notes, compose(StyleId::DayDrive, 2).notes);
    }

    #[test]
    fn every_style_lasts_ninety_seconds_to_five_minutes_in_its_tempo() {
        for id in StyleId::ALL {
            for seed in 0..4 {
                let score = compose(id, seed);
                let (lo, hi) = style(id).bpm;
                assert!((lo..=hi).contains(&score.bpm), "{} bpm {}", id.id(), score.bpm);
                let d = score.duration_s();
                assert!((85.0..=310.0).contains(&d), "{} lasts {d}", id.id());
                assert!(score.notes.iter().all(|n| n.start_beat + n.beats <= score.total_beats + 1e-9));
            }
        }
    }

    #[test]
    fn lengths_vary_from_piece_to_piece() {
        let lengths: Vec<f64> = (0..20).map(|seed| compose(StyleId::DayDrive, seed).duration_s()).collect();
        let (lo, hi) = lengths.iter().fold((f64::MAX, 0.0f64), |(lo, hi), d| (lo.min(*d), hi.max(*d)));
        assert!(hi - lo > 90.0, "lengths only span {lo:.0} to {hi:.0} s");
    }

    #[test]
    fn drum_free_styles_have_no_drums_and_kit_styles_do() {
        let no_drums = compose(StyleId::NightDrive, 5);
        assert!(no_drums.notes.iter().all(|n| !matches!(n.voice, Voice::Kick | Voice::Snare | Voice::Hat)));
        let kit = compose(StyleId::FleetOwner, 5);
        assert!(kit.notes.iter().any(|n| n.voice == Voice::Kick));
    }

    #[test]
    fn melody_stays_in_its_scale() {
        let score = compose(StyleId::Regional, 11);
        let s = style(StyleId::Regional);
        let scale: Vec<i32> = s.mode.intervals().to_vec();
        for n in score.notes.iter().filter(|n| matches!(n.voice, Voice::Pluck | Voice::Keys)) {
            assert!(scale.contains(&(n.midi - s.root).rem_euclid(12)), "{} out of scale", n.midi);
        }
    }
}
```

- [ ] **Step 2: Run to see it fail**

Run: `cargo test -p ff-core music_synth::compose`
Expected: FAIL to compile (`compose` not defined).

- [ ] **Step 3: Implement**

Top of `compose.rs`:

```rust
//! A score from a style and a seed: sections, one chord per bar, a bass line,
//! a melody over the chords, drums where the style has them. The A section's
//! melody is written once and repeated, so a piece has a tune to come back to.

use super::rng::Rng;
use super::style::{style, Drums, Lead, Style, StyleId};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Voice {
    Pad,
    Pluck,
    Keys,
    Bass,
    Kick,
    Snare,
    Hat,
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
                degree = if (target - degree).abs() > 3 { target } else { degree + (target - degree).signum() };
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
    let body_bars = (((target_s - TAIL_S) / bar_s) as usize).saturating_sub(8).max(8);
    let sections = (body_bars / 8).max(1);

    let prog_a = s.progressions[rng.below(s.progressions.len())];
    let prog_b = s.progressions[rng.below(s.progressions.len())];
    let chords_of = |prog: &[usize]| -> Vec<usize> { (0..8).map(|i| prog[i % prog.len()]).collect() };
    let (chords_a, chords_b) = (chords_of(prog_a), chords_of(prog_b));
    let melody_a = write_melody(&mut rng, s, &chords_a);

    let mut plan: Vec<(Vec<usize>, Option<Vec<(f64, f64, i32)>>, bool)> = Vec::new();
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
    let mut notes = Vec::new();
    let mut bar0 = 0.0;
    for (chords, melody, drums_on) in &plan {
        for (bar, chord) in chords.iter().enumerate() {
            let at = bar0 + bar as f64 * BEATS_PER_BAR;
            let c = *chord as i32;
            for tone in [0, 2, 4] {
                notes.push(Note { start_beat: at, beats: BEATS_PER_BAR, midi: degree_midi(s, 7 + c + tone), velocity: 0.28, voice: Voice::Pad });
            }
            notes.push(Note { start_beat: at, beats: 1.5, midi: degree_midi(s, c), velocity: 0.7, voice: Voice::Bass });
            notes.push(Note { start_beat: at + 2.0, beats: 1.5, midi: degree_midi(s, c + if rng.chance(0.5) { 4 } else { 0 }), velocity: 0.6, voice: Voice::Bass });
            if *drums_on && s.drums != Drums::None {
                for beat in 0..4 {
                    let b = at + beat as f64;
                    if s.drums == Drums::Kit && beat % 2 == 0 {
                        notes.push(Note { start_beat: b, beats: 0.5, midi: 36, velocity: 0.8, voice: Voice::Kick });
                    }
                    if beat % 2 == 1 {
                        notes.push(Note { start_beat: b, beats: 0.5, midi: 38, velocity: if s.drums == Drums::Kit { 0.6 } else { 0.35 }, voice: Voice::Snare });
                    }
                    notes.push(Note { start_beat: b, beats: 0.25, midi: 42, velocity: 0.25, voice: Voice::Hat });
                    notes.push(Note { start_beat: b + 0.5 + s.swing * 0.5, beats: 0.25, midi: 42, velocity: 0.18, voice: Voice::Hat });
                }
            }
        }
        if let Some(melody) = melody {
            for (offset, len, degree) in melody {
                let velocity = 0.45 + 0.2 * rng.unit() as f32;
                notes.push(Note { start_beat: bar0 + offset, beats: *len, midi: degree_midi(s, *degree), velocity, voice: lead_voice });
            }
        }
        bar0 += chords.len() as f64 * BEATS_PER_BAR;
    }
    Score { style: id, bpm, total_beats: bar0, notes }
}
```

Add to `music_synth.rs`: `pub mod compose;` and `pub use compose::{compose, Note, Score, Voice};`.

- [ ] **Step 4: Run the tests**

Run: `cargo test -p ff-core music_synth::compose`
Expected: PASS. If the duration test fails for a slow style (sections round down to whole 8-bar blocks), adjust only `target_s`'s range in `compose`, not the test bounds.

- [ ] **Step 5: Commit**

```bash
git add crates/ff-core/src/music_synth.rs crates/ff-core/src/music_synth/compose.rs
git commit -m "feat(music): compose a synthesized score from a style and a seed

[skip changelog]

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Rendering to PCM, and one shared WAV writer

**Files:**
- Create: `crates/ff-core/src/music_synth/render.rs`, `crates/ff-core/src/wav.rs`
- Modify: `crates/ff-core/src/lib.rs` (`pub mod wav;`), `crates/ff-core/src/music_synth.rs` (`pub mod render; pub use render::{render, SAMPLE_RATE};`)
- Modify: `crates/freight-fate/src/states/driving_core/siren.rs:126-157` and `crates/ff-core/src/ladder_earcons.rs:78` to call `crate::wav::pcm16_wav` / `ff_core::wav::pcm16_wav` and delete their private `wav_bytes`

**Interfaces:**
- Consumes: `Score`, `Note`, `Voice` (Task 2), `Rng` (Task 1)
- Produces: `render::SAMPLE_RATE: u32 = 22_050`, `render(score: &Score) -> Vec<i16>` (interleaved stereo), `wav::pcm16_wav(samples: &[i16], channels: u16, rate: u32) -> Vec<u8>`

- [ ] **Step 1: Move the WAV writer**

Read the existing `wav_bytes` in `crates/freight-fate/src/states/driving_core/siren.rs:126` (it takes `channels` and `rate`) and move its body verbatim into `crates/ff-core/src/wav.rs` as:

```rust
//! A 16-bit PCM WAV container around interleaved samples -- what the
//! runtime-generated sounds (siren, earcons, synthesized music) publish.

pub fn pcm16_wav(samples: &[i16], channels: u16, rate: u32) -> Vec<u8> {
    let data_len = (samples.len() * 2) as u32;
    let mut out = Vec::with_capacity(44 + data_len as usize);
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&(36 + data_len).to_le_bytes());
    out.extend_from_slice(b"WAVEfmt ");
    out.extend_from_slice(&16u32.to_le_bytes());
    out.extend_from_slice(&1u16.to_le_bytes());
    out.extend_from_slice(&channels.to_le_bytes());
    out.extend_from_slice(&rate.to_le_bytes());
    out.extend_from_slice(&(rate * channels as u32 * 2).to_le_bytes());
    out.extend_from_slice(&(channels * 2).to_le_bytes());
    out.extend_from_slice(&16u16.to_le_bytes());
    out.extend_from_slice(b"data");
    out.extend_from_slice(&data_len.to_le_bytes());
    for s in samples {
        out.extend_from_slice(&s.to_le_bytes());
    }
    out
}

#[cfg(test)]
mod tests {
    #[test]
    fn header_describes_the_samples() {
        let wav = super::pcm16_wav(&[0, 1, 2, 3], 2, 22_050);
        assert_eq!(&wav[0..4], b"RIFF");
        assert_eq!(u32::from_le_bytes(wav[40..44].try_into().unwrap()), 8);
        assert_eq!(wav.len(), 52);
    }
}
```

If the moved siren body differs from the above (e.g. a different header field order), keep the siren's body: it is what ships today. Replace both private copies with calls to `ff_core::wav::pcm16_wav` (ladder earcons is mono at its own rate: pass its channel count and rate explicitly). Run `cargo test -p ff-core ladder_earcons` and `cargo test -p freight-fate --test it siren` -- both must still pass unchanged.

- [ ] **Step 2: Write the failing render tests**

In `render.rs`:

```rust
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
    fn starts_and_ends_quiet() {
        let pcm = render(&short(StyleId::FleetOwner, 9));
        assert!(pcm[..20].iter().all(|s| s.unsigned_abs() < 600));
        assert!(pcm[pcm.len() - 20..].iter().all(|s| s.unsigned_abs() < 600));
    }
}
```

- [ ] **Step 3: Run to see it fail**

Run: `cargo test -p ff-core music_synth::render`
Expected: FAIL to compile.

- [ ] **Step 4: Implement the renderer**

Top of `render.rs`:

```rust
//! Score to PCM with the 1.5 voice set: soft pad, plucked string, electric
//! keys, sine bass, noise brushes and a small kit, through a light reverb.
//! Pure and deterministic: the pluck's noise comes from the score's own seed.

use super::compose::{Note, Score, Voice};
use super::rng::Rng;
use std::f64::consts::TAU;

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
                    let env = (t / 0.4).min(1.0) * if t > dur_s { (1.0 - (t - dur_s) / release).max(0.0) } else { 1.0 };
                    let wave = (TAU * f * t).sin() + 0.35 * (TAU * f * 1.003 * 2.0 * t).sin() + 0.2 * (TAU * f * 0.997 * t).sin();
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
            let (len, decay, bright) = if note.voice == Voice::Snare { (0.25, 18.0, 0.5) } else { (0.08, 60.0, 0.9) };
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

/// Small Schroeder reverb on a mono send.
fn reverb(send: &[f64]) -> Vec<f64> {
    let combs = [1116usize, 1188, 1277, 1356].map(|d| d * SAMPLE_RATE as usize / 44_100);
    let mut out = vec![0.0; send.len()];
    for d in combs {
        let mut buf = vec![0.0; d];
        for (i, x) in send.iter().enumerate() {
            let y = buf[i % d];
            buf[i % d] = x + y * 0.78;
            out[i] += y * 0.25;
        }
    }
    for d in [556usize, 441].map(|d| d * SAMPLE_RATE as usize / 44_100) {
        let mut buf = vec![0.0; d];
        for (i, sample) in out.iter_mut().enumerate() {
            let input = *sample;
            let y = buf[i % d];
            buf[i % d] = input + y * 0.5;
            *sample = y - input * 0.5;
        }
    }
    out
}

pub fn render(score: &Score) -> Vec<i16> {
    let sr = SAMPLE_RATE as f64;
    let frames = (score.duration_s() * sr).ceil() as usize;
    let mut left = vec![0.0f64; frames];
    let mut right = vec![0.0f64; frames];
    let mut send = vec![0.0f64; frames];
    let beat_s = 60.0 / score.bpm;
    let mut rng = Rng::new(score.notes.len() as u64 ^ score.bpm.to_bits());
    for note in &score.notes {
        let start = (note.start_beat * beat_s * sr) as usize;
        let samples = voice_samples(note, note.beats * beat_s, &mut rng);
        let (gl, gr) = pan(note.voice);
        let wet = matches!(note.voice, Voice::Pad | Voice::Pluck | Voice::Keys);
        for (i, s) in samples.iter().enumerate() {
            let at = start + i;
            if at >= frames {
                break;
            }
            left[at] += s * gl;
            right[at] += s * gr;
            if wet {
                send[at] += s * 0.3;
            }
        }
    }
    let wet = reverb(&send);
    let peak = left
        .iter()
        .zip(&right)
        .zip(&wet)
        .map(|((l, r), w)| (l + w).abs().max((r + w).abs()))
        .fold(0.0f64, f64::max)
        .max(1e-9);
    let gain = PEAK / peak;
    let fade_in = (FADE_IN_S * sr) as usize;
    let fade_out = (FADE_OUT_S * sr) as usize;
    let mut pcm = Vec::with_capacity(frames * 2);
    for i in 0..frames {
        let mut env = 1.0;
        if i < fade_in {
            env *= i as f64 / fade_in as f64;
        }
        if i + fade_out > frames {
            env *= (frames - i) as f64 / fade_out as f64;
        }
        for x in [left[i] + wet[i], right[i] + wet[i]] {
            pcm.push((x * gain * env).clamp(i16::MIN as f64, i16::MAX as f64) as i16);
        }
    }
    pcm
}
```

- [ ] **Step 5: Run the tests**

Run: `cargo test -p ff-core music_synth::render wav`
Expected: PASS. Then time a full piece once in release to confirm the worker budget:

Run: `cargo test -p ff-core --release music_synth::render -- --ignored --nocapture` after adding this ignored test to `render.rs` tests:

```rust
    #[test]
    #[ignore = "timing probe, run in release by hand"]
    fn a_five_minute_piece_renders_in_under_four_seconds() {
        let score = (0..200)
            .map(|seed| crate::music_synth::compose(StyleId::FleetOwner, seed))
            .max_by(|a, b| a.duration_s().total_cmp(&b.duration_s()))
            .expect("scores");
        let t = std::time::Instant::now();
        let _ = render(&score);
        let s = t.elapsed().as_secs_f64();
        println!("rendered {:.0}s of music in {s:.2}s", score.duration_s());
        assert!(s < 4.0);
    }
```

Expected: under 4 seconds for the longest of 200 seeds. If not, profile `voice_samples` for pads (the largest count) before changing anything else.

- [ ] **Step 6: Commit**

```bash
git add crates/ff-core/src/lib.rs crates/ff-core/src/wav.rs crates/ff-core/src/music_synth.rs crates/ff-core/src/music_synth/render.rs crates/ff-core/src/ladder_earcons.rs crates/freight-fate/src/states/driving_core/siren.rs
git commit -m "feat(music): render synthesized scores; one shared WAV writer

[skip changelog]

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Keys, titles, durations and the synthesized sequences

**Files:**
- Modify: `crates/ff-core/src/music_synth.rs`
- Modify: `crates/ff-core/src/music.rs` (runtime duration registry; `music_track_duration_s` consults synth keys, classics and the registry)

**Interfaces:**
- Consumes: Tasks 1-2
- Produces (all in `ff_core::music_synth`):
  - `pub const CLASSIC_MENU: &str = "classic_menu_theme"; pub const CLASSIC_DAY: &str = "classic_open_road"; pub const CLASSIC_NIGHT: &str = "classic_night_haul";`
  - `pub struct SynthKey { pub style: StyleId, pub music_seed: i64, pub index: usize }` with `fn key(&self) -> String` (format `synth_<style id>_<music_seed>_<index>`) and `fn parse(key: &str) -> Option<SynthKey>`
  - `pub fn classic_for(style: StyleId) -> &'static str` (NightMenu/NightDrive -> CLASSIC_NIGHT, DayDrive -> CLASSIC_DAY, all menu rungs -> CLASSIC_MENU)
  - `pub fn track_title(key: &str) -> Option<String>` (synth and classic keys; None otherwise)
  - `pub fn select_synth_menu_sequence(profile: Option<&dyn MenuMusicProfile>, music_seed: i64, extras: &[String]) -> Vec<String>`
  - `pub fn select_synth_drive_sequence(night: bool, music_seed: i64, trip_seed: i64, extras: &[String]) -> Vec<String>`
  - `pub const PIECES_PER_ROTATION: usize = 6;`
- Produces (in `ff_core::music`): `pub fn register_track_duration(key: &str, seconds: f64)`, `pub fn known_track_duration_s(key: &str) -> Option<f64>`

- [ ] **Step 1: Write the failing tests** (append to `music_synth.rs`)

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keys_round_trip() {
        let k = SynthKey { style: StyleId::TopHand, music_seed: 48213, index: 3 };
        assert_eq!(k.key(), "synth_company_top_hand_48213_3");
        assert_eq!(SynthKey::parse(&k.key()), Some(k));
        assert_eq!(SynthKey::parse("open_road"), None);
        assert_eq!(SynthKey::parse("synth_nope_1_1"), None);
    }

    #[test]
    fn titles_are_spoken_text() {
        assert_eq!(track_title("synth_first_run_48213_2").as_deref(), Some("Synthesized: First Run, number 3"));
        assert_eq!(track_title(CLASSIC_MENU).as_deref(), Some("Headlights West, from Freight Fate 1.5"));
        assert_eq!(track_title("open_road"), None);
    }

    #[test]
    fn durations_are_known_without_rendering() {
        let key = SynthKey { style: StyleId::DayDrive, music_seed: 1, index: 0 }.key();
        let expected = compose(StyleId::DayDrive, rng::piece_seed(StyleId::DayDrive, 1, 0)).duration_s();
        assert_eq!(crate::music::music_track_duration_s(&key), expected);
        assert!((crate::music::music_track_duration_s(CLASSIC_DAY) - 61.41).abs() < 0.01);
        crate::music::register_track_duration("player_x", 42.0);
        assert_eq!(crate::music::music_track_duration_s("player_x"), 42.0);
    }

    #[test]
    fn a_new_career_opens_on_headlights_west_and_holds_only_synth_music() {
        let seq = select_synth_menu_sequence(None, 48213, &[]);
        assert_eq!(seq[0], CLASSIC_MENU);
        assert_eq!(seq.len(), 1 + PIECES_PER_ROTATION);
        assert!(seq[1..].iter().all(|k| SynthKey::parse(k).is_some_and(|s| s.style == StyleId::NewHire)));
    }

    #[test]
    fn extras_join_the_rotation_and_the_seed_changes_every_piece() {
        let extras = vec!["hand_made/new_hire/diesel_dawn".to_string()];
        let seq = select_synth_menu_sequence(None, 1, &extras);
        assert!(seq.contains(&extras[0]));
        let a = select_synth_drive_sequence(false, 1, 7, &[]);
        let b = select_synth_drive_sequence(false, 2, 7, &[]);
        assert!(a.contains(&CLASSIC_DAY.to_string()));
        assert!(a.iter().filter(|k| k.starts_with("synth_")).all(|k| !b.contains(k)));
        assert!(select_synth_drive_sequence(true, 1, 7, &[]).contains(&CLASSIC_NIGHT.to_string()));
    }
}
```

- [ ] **Step 2: Run to see it fail**

Run: `cargo test -p ff-core music_synth::tests`
Expected: FAIL to compile.

- [ ] **Step 3: Implement the registry in `music.rs`**

Near `music_track_duration_s`:

```rust
/// Lengths learned at run time: hand-made modules and player files, whose
/// length only BASS can read. Keyed like the catalog.
static RUNTIME_DURATIONS: once_cell::sync::Lazy<parking_lot::Mutex<HashMap<String, f64>>> =
    once_cell::sync::Lazy::new(|| parking_lot::Mutex::new(HashMap::new()));

pub fn register_track_duration(key: &str, seconds: f64) {
    if seconds.is_finite() && seconds > 0.0 {
        RUNTIME_DURATIONS.lock().insert(key.to_string(), seconds);
    }
}

/// The length of `key` if anything knows it: the shipped catalog, a
/// synthesized piece (composed, not rendered), or a registered run-time track.
pub fn known_track_duration_s(key: &str) -> Option<f64> {
    if let Some(info) = TRACKS_BY_KEY.get(key) {
        return Some(info.duration_s);
    }
    if let Some(d) = crate::music_synth::duration_s(key) {
        return Some(d);
    }
    RUNTIME_DURATIONS.lock().get(key).copied()
}
```

and change `music_track_duration_s` to `known_track_duration_s(track).unwrap_or(60.0)`. Add `use std::collections::HashMap;` if not present.

- [ ] **Step 4: Implement keys, titles and sequences in `music_synth.rs`**

```rust
pub use compose::{compose, Note, Score, Voice};
pub use render::{render, SAMPLE_RATE};

use crate::music::{crc32, MenuMusicProfile};

pub const CLASSIC_MENU: &str = "classic_menu_theme";
pub const CLASSIC_DAY: &str = "classic_open_road";
pub const CLASSIC_NIGHT: &str = "classic_night_haul";
/// Synthesized pieces per place in one rotation, before it laps.
pub const PIECES_PER_ROTATION: usize = 6;

/// Measured from the v1.5.0 files (ffprobe, 2026-09-21).
const CLASSICS: [(&str, &str, f64); 3] = [
    (CLASSIC_MENU, "Headlights West, from Freight Fate 1.5", 51.833),
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
        format!("synth_{}_{}_{}", self.style.id(), self.music_seed, self.index)
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
        return Some(format!("Synthesized: {}, number {}", style(k.style).title, k.index + 1));
    }
    CLASSICS.iter().find(|(k, _, _)| *k == key).map(|(_, title, _)| title.to_string())
}

/// Length of a synth or classic key without rendering anything.
pub fn duration_s(key: &str) -> Option<f64> {
    if let Some(k) = SynthKey::parse(key) {
        return Some(compose(k.style, k.seed()).duration_s());
    }
    CLASSICS.iter().find(|(k, _, _)| *k == key).map(|(_, _, d)| *d)
}

fn pieces(style_id: StyleId, music_seed: i64) -> impl Iterator<Item = String> {
    (0..PIECES_PER_ROTATION).map(move |index| SynthKey { style: style_id, music_seed, index }.key())
}

/// `crc_ordered` for plain keys: a stable shuffle by seed.
fn shuffled(mut keys: Vec<String>, seed_key: &str) -> Vec<String> {
    keys.sort_by_key(|k| crc32(format!("{seed_key}|{k}").as_bytes()));
    keys
}

/// The menu rotation: Headlights West first for a brand-new career, else the
/// place's first piece; then the rest of the pieces, the classic and any
/// hand-made extras in a stable order.
pub fn select_synth_menu_sequence(
    profile: Option<&dyn MenuMusicProfile>,
    music_seed: i64,
    extras: &[String],
) -> Vec<String> {
    let place = menu_style(profile);
    let mut all: Vec<String> = pieces(place, music_seed).collect();
    all.extend(extras.iter().cloned());
    let classic = classic_for(place).to_string();
    let lead = if place == StyleId::NewHire { classic.clone() } else { all.remove(0) };
    if lead != classic {
        all.push(classic);
    }
    let rest = shuffled(all, &format!("{music_seed}|{}", place.id()));
    std::iter::once(lead).chain(rest).collect()
}

/// The Roadhouse's day or night playlist in Synthesized mode.
pub fn select_synth_drive_sequence(night: bool, music_seed: i64, trip_seed: i64, extras: &[String]) -> Vec<String> {
    let place = if night { StyleId::NightDrive } else { StyleId::DayDrive };
    let mut all: Vec<String> = pieces(place, music_seed).collect();
    all.push(classic_for(place).to_string());
    all.extend(extras.iter().cloned());
    shuffled(all, &format!("{music_seed}|{trip_seed}|{}", place.id()))
}
```

- [ ] **Step 5: Run the tests**

Run: `cargo test -p ff-core music_synth` then `cargo test -p ff-core music::`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add crates/ff-core/src/music.rs crates/ff-core/src/music_synth.rs
git commit -m "feat(music): synthesized keys, titles, lengths and rotations

[skip changelog]

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: The render worker

**Files:**
- Create: `crates/ff-core/src/music_synth/worker.rs`
- Modify: `crates/ff-core/src/music_synth.rs` (`pub mod worker; pub use worker::SynthWorker;`)
- Modify: `crates/ff-core/src/assets_pack.rs` (add `pub fn unregister_generated_sound(key: &str)` beside `register_generated_sound` at `:590`)

**Interfaces:**
- Consumes: `SynthKey`, `compose`, `render`, `SAMPLE_RATE`, `pcm16_wav`, `register_generated_sound`
- Produces: `SynthWorker { fn start() -> SynthWorker; fn request(&self, key: &str) -> bool; fn is_ready(key: &str) -> bool; fn shutdown(&mut self, bound: Duration) }` -- `request` returns false when the key is not a synth key or the queue is full; `is_ready` is an associated fn that checks `generated_sound(&format!("music/{key}"))`. Keeps at most `KEEP_RENDERED = 3` pieces registered (the playing one, the next, and one spare), unregistering the oldest.

- [ ] **Step 1: Add `unregister_generated_sound`**

In `assets_pack.rs` after `register_generated_sound`:

```rust
/// Drop a generated sound, e.g. a synthesized piece that has played.
pub fn unregister_generated_sound(key: &str) {
    let removed = GENERATED.lock().unwrap_or_else(|e| e.into_inner()).remove(key).is_some();
    if removed {
        GENERATED_VERSION.fetch_add(1, Ordering::SeqCst);
    }
}
```

- [ ] **Step 2: Write the failing tests** (bottom of `worker.rs`)

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use crate::music_synth::{SynthKey, StyleId};
    use std::time::{Duration, Instant};

    fn wait_ready(key: &str) -> bool {
        let t = Instant::now();
        while t.elapsed() < Duration::from_secs(60) {
            if SynthWorker::is_ready(key) {
                return true;
            }
            std::thread::sleep(Duration::from_millis(20));
        }
        false
    }

    #[test]
    fn a_requested_piece_is_published_as_a_wav() {
        let mut worker = SynthWorker::start();
        let key = SynthKey { style: StyleId::NightMenu, music_seed: 777, index: 0 }.key();
        assert!(worker.request(&key));
        assert!(wait_ready(&key));
        let (bytes, ext) = crate::assets_pack::generated_sound(&format!("music/{key}")).expect("published");
        assert_eq!(ext, "wav");
        assert_eq!(&bytes[..4], b"RIFF");
        worker.shutdown(Duration::from_secs(5));
    }

    #[test]
    fn non_synth_keys_are_refused_and_shutdown_is_idempotent() {
        let mut worker = SynthWorker::start();
        assert!(!worker.request("open_road"));
        worker.shutdown(Duration::from_secs(5));
        worker.shutdown(Duration::from_secs(5));
        assert!(!worker.request(&SynthKey { style: StyleId::DayDrive, music_seed: 1, index: 0 }.key()));
    }
}
```

- [ ] **Step 3: Run to see it fail**

Run: `cargo test -p ff-core music_synth::worker`
Expected: FAIL to compile.

- [ ] **Step 4: Implement**

```rust
//! Renders synthesized pieces off the game loop.
//!
//! One thread, a bounded queue of two requests. A full queue drops the new
//! request -- the caller plays the classic and asks again next track -- so
//! the loop never waits here. A rendered piece is published as a generated
//! sound under `music/<key>`; at most KEEP_RENDERED stay registered.

use super::{compose, render, SynthKey, SAMPLE_RATE};
use crate::assets_pack::{generated_sound, register_generated_sound, unregister_generated_sound};
use std::collections::VecDeque;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{sync_channel, Receiver, SyncSender, TrySendError};
use std::sync::Arc;
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

const QUEUE: usize = 2;
const KEEP_RENDERED: usize = 3;

pub struct SynthWorker {
    tx: Option<SyncSender<SynthKey>>,
    cancel: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
}

impl SynthWorker {
    pub fn start() -> SynthWorker {
        let (tx, rx) = sync_channel::<SynthKey>(QUEUE);
        let cancel = Arc::new(AtomicBool::new(false));
        let flag = Arc::clone(&cancel);
        let handle = std::thread::Builder::new()
            .name("synth-music".into())
            .spawn(move || run(rx, flag))
            .map_err(|err| log::warn!("Synthesized music worker did not start ({err})"))
            .ok();
        SynthWorker { tx: handle.as_ref().map(|_| tx), cancel, handle }
    }

    /// Queue a render. False when `key` is not a synth key, is already
    /// published, the worker is shut down, or the queue is full.
    pub fn request(&self, key: &str) -> bool {
        let (Some(tx), Some(parsed)) = (&self.tx, SynthKey::parse(key)) else {
            return false;
        };
        if Self::is_ready(key) {
            return true;
        }
        match tx.try_send(parsed) {
            Ok(()) => true,
            Err(TrySendError::Full(_)) => false,
            Err(TrySendError::Disconnected(_)) => false,
        }
    }

    pub fn is_ready(key: &str) -> bool {
        generated_sound(&format!("music/{key}")).is_some()
    }

    /// Signal, stop accepting work, then wait at most `bound`.
    pub fn shutdown(&mut self, bound: Duration) {
        self.cancel.store(true, Ordering::SeqCst);
        self.tx = None; // disconnects the channel; the thread's recv ends
        let Some(handle) = self.handle.take() else {
            return;
        };
        log::info!("shutdown: synthesized music worker signalled");
        let started = Instant::now();
        while !handle.is_finished() && started.elapsed() < bound {
            std::thread::sleep(Duration::from_millis(10));
        }
        if handle.is_finished() {
            let _ = handle.join();
            log::info!("shutdown: synthesized music worker joined in {} ms", started.elapsed().as_millis());
        } else {
            log::warn!("shutdown: synthesized music worker still rendering after {} ms; leaving it", bound.as_millis());
        }
    }
}

impl Drop for SynthWorker {
    fn drop(&mut self) {
        // Signal only: never join in Drop.
        self.cancel.store(true, Ordering::SeqCst);
        self.tx = None;
    }
}

fn run(rx: Receiver<SynthKey>, cancel: Arc<AtomicBool>) {
    let mut published: VecDeque<String> = VecDeque::new();
    while let Ok(key) = rx.recv() {
        if cancel.load(Ordering::SeqCst) {
            break;
        }
        let name = format!("music/{}", key.key());
        if generated_sound(&name).is_some() {
            continue;
        }
        let score = compose(key.style, key.seed());
        let pcm = render(&score);
        if cancel.load(Ordering::SeqCst) {
            break;
        }
        register_generated_sound(&name, crate::wav::pcm16_wav(&pcm, 2, SAMPLE_RATE), "wav");
        published.push_back(name);
        while published.len() > KEEP_RENDERED {
            if let Some(old) = published.pop_front() {
                unregister_generated_sound(&old);
            }
        }
    }
}
```

The render is not interruptible mid-piece; a 5-minute piece is under 4 s in release, so the 2.5 s shutdown bound can expire mid-render -- that path logs and leaves the thread, which the process exit then ends. Acceptable because it never blocks the loop.

- [ ] **Step 5: Run the tests**

Run: `cargo test -p ff-core music_synth::worker`
Expected: PASS (debug render of one piece may take tens of seconds; the 60 s wait covers it).

- [ ] **Step 6: Commit**

```bash
git add crates/ff-core/src/assets_pack.rs crates/ff-core/src/music_synth.rs crates/ff-core/src/music_synth/worker.rs
git commit -m "feat(music): render synthesized pieces on a bounded worker

[skip changelog]

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Settings rows and vocabulary

**Files:**
- Modify: `crates/ff-core/src/settings.rs:493-495` (two new fields after `music_volume`)
- Modify: `crates/freight-fate/src/states/main_menu/settings_items.rs:782` (two rows after Music volume)
- Modify: `crates/freight-fate/src/states/main_menu/settings_actions.rs` (two actions near `toggle_jake_voice` at `:389`)
- Modify: `docs/ontology.md` (one row, in the audio/radio section near line 412)
- Test: `crates/freight-fate/tests/it/synth_music.rs` (new) and `crates/freight-fate/tests/it/main.rs` (`mod synth_music;`)

**Interfaces:**
- Produces: `Settings::synth_music: bool` (default false), `Settings::music_seed: i64` (default 48213); `SettingsCategoryState::toggle_music_source(&mut self, ctx, d)`, `SettingsCategoryState::roll_music_seed(&mut self, ctx, d)`; `GameContext::restart_music(&mut self)` is called by both (defined in Task 8 -- until then, call `ctx.apply_active_radio_settings()` only and leave a one-line call to `restart_music` added in Task 8).

- [ ] **Step 1: Add the settings**

In the settings macro, after `music_volume: f64 = 0.5 => level,`:

```rust
    /// Music source: false plays the full soundtrack; true swaps menu music
    /// and the Roadhouse for synthesized music -- pieces the game composes
    /// from `music_seed`, the restored 1.5 tracks and hand-made modules --
    /// for players who want no AI-made music (owner, 2026-09-21).
    synth_music: bool = false => bool_truthy,
    /// Seeds every synthesized piece. Global, not per career, so a seed a
    /// player likes sounds the same on any career and can be shared.
    music_seed: i64 = 48213 => int_lenient,
```

- [ ] **Step 2: Write the failing test**

`crates/freight-fate/tests/it/synth_music.rs`:

```rust
//! Synthesized music: the settings rows, menu and Roadhouse rotations, and
//! the fallback when a piece is not ready.

use freight_fate::app::testing::TestApp;

#[test]
fn defaults_are_original_and_a_fixed_seed() {
    let app = TestApp::new();
    assert!(!app.ctx.settings.synth_music);
    assert_eq!(app.ctx.settings.music_seed, 48213);
}
```

Add `mod synth_music;` to `crates/freight-fate/tests/it/main.rs` in alphabetical order.

Run: `cargo test -p freight-fate --test it synth_music`
Expected: PASS once Step 1 compiles (this pins the defaults). Then add a rows test modelled on the nearest existing settings-row test: run `grep -rn "Engine brake voice" crates/freight-fate/tests/it` and copy the harness that opens Settings, Audio and reads a row's spoken label, asserting these exact strings: `Music source: Original`, then after activating the row `Music source: Synthesized`; `Music seed: 48213`; and after activating the seed row, the transcript contains `New music seed, ` and `ctx.settings.music_seed` is in `10000..=99999` and differs from 48213. Run it and see it FAIL (rows missing).

- [ ] **Step 3: Add the rows**

In `settings_items.rs`, after the Music volume `row(...)`:

```rust
            row(
                dyn_label(|s| {
                    format!(
                        "Music source: {}",
                        if s.synth_music { "Synthesized" } else { "Original" }
                    )
                }),
                adjust(|s, ctx, d| s.toggle_music_source(ctx, d)),
                "Synthesized plays menu music and the Roadhouse station made by the \
                 game itself, with no AI-made songs or voices. Original plays the \
                 full soundtrack.",
            ),
            row(
                dyn_label(|s| format!("Music seed: {}", s.music_seed)),
                adjust(|s, ctx, d| s.roll_music_seed(ctx, d)),
                "Enter rolls a new seed. Every synthesized piece changes with it.",
            ),
```

If the audio rows are also indexed positionally in `adjust_actions` (`settings_items.rs:326`), add the two actions in the same positions there; check by reading `adjust_actions` before editing.

In `settings_actions.rs`, next to `toggle_jake_voice`:

```rust
    pub(super) fn toggle_music_source(&mut self, ctx: &mut GameContext, _d: i64) {
        ctx.settings.synth_music = !ctx.settings.synth_music;
        save_settings(&ctx.settings);
        ctx.restart_music();
        self.announce(ctx);
    }

    pub(super) fn roll_music_seed(&mut self, ctx: &mut GameContext, _d: i64) {
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos() as u64)
            .unwrap_or(0);
        let mut rng = ff_core::music_synth::rng::Rng::new(nanos ^ ctx.settings.music_seed as u64);
        let mut seed = ctx.settings.music_seed;
        while seed == ctx.settings.music_seed {
            seed = 10_000 + rng.below(90_000) as i64;
        }
        ctx.settings.music_seed = seed;
        save_settings(&ctx.settings);
        ctx.restart_music();
        ctx.say(&format!("New music seed, {seed}. Every synthesized piece is new."));
    }
```

Until Task 8 lands, add a stub to `GameContext` in `context.rs` so this compiles, with the body Task 8 replaces:

```rust
    /// Restart whatever music is playing so a music setting is heard at once.
    pub fn restart_music(&mut self) {
        self.apply_active_radio_settings();
    }
```

- [ ] **Step 4: Ontology row**

In `docs/ontology.md`, in the table holding the radio rows (around line 412), add:

```markdown
| synthesized music | Music the game composes itself, plus the restored 1.5 tracks and hand-made modules; what Music source: Synthesized plays in menus and on the Roadhouse | "no-AI music", "generated music", "procedural music" |
```

Match that table's column layout exactly (read its header first).

- [ ] **Step 5: Run the tests**

Run: `cargo test -p freight-fate --test it synth_music` and `cargo test -p ff-core settings`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add crates/ff-core/src/settings.rs crates/freight-fate/src/states/main_menu/settings_items.rs crates/freight-fate/src/states/main_menu/settings_actions.rs crates/freight-fate/src/app/context.rs docs/ontology.md crates/freight-fate/tests/it/main.rs crates/freight-fate/tests/it/synth_music.rs
git commit -m "feat(settings): Music source and Music seed rows

[skip changelog]

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: The restored 1.5 classics

**Files:**
- Create: `crates/freight-fate/assets/classic_music/classic_menu_theme.ogg`, `classic_open_road.ogg`, `classic_night_haul.ogg`
- Create: `crates/freight-fate/src/audio/classic_music.rs`
- Modify: `crates/freight-fate/src/audio.rs` (`pub mod classic_music;`), the startup path that calls `register_enforcement_sounds()` (find with `grep -rn "register_enforcement_sounds()" crates/freight-fate/src`) to also call `classic_music::register()`
- Modify: `src/freight_fate/assets/sounds/CREDITS.md` (three rows)
- Test: `crates/freight-fate/tests/it/synth_music.rs`

**Interfaces:**
- Produces: `freight_fate::audio::classic_music::register()`; after it, `asset_bytes("music/classic_menu_theme", MUSIC_EXTENSIONS)` returns the bytes with ext `ogg`.

- [ ] **Step 1: Restore the files byte for byte**

```bash
mkdir -p crates/freight-fate/assets/classic_music
git show v1.5.0:src/freight_fate/assets/sounds/music/menu_theme.ogg > crates/freight-fate/assets/classic_music/classic_menu_theme.ogg
git show v1.5.0:src/freight_fate/assets/sounds/music/open_road.ogg > crates/freight-fate/assets/classic_music/classic_open_road.ogg
git show v1.5.0:src/freight_fate/assets/sounds/music/night_haul.ogg > crates/freight-fate/assets/classic_music/classic_night_haul.ogg
git hash-object crates/freight-fate/assets/classic_music/*.ogg
```

Expected hashes, in order: `b59278afbad0b4697b04eebc07b730afc441bd3a`, `727a93583041980ac41320deb32a6afb7a8b0fec`, `3203da345c5e987167524924feb3883d7b53d257`. Stop if any differs. (Use Git Bash for the redirect; PowerShell `>` re-encodes binary.)

- [ ] **Step 2: Write the failing test** (append to `synth_music.rs`)

```rust
#[test]
fn the_three_classics_play_from_the_executable() {
    freight_fate::audio::classic_music::register();
    for key in ["classic_menu_theme", "classic_open_road", "classic_night_haul"] {
        let (bytes, ext) = freight_fate::audio::assets::asset_bytes(
            &format!("music/{key}"),
            freight_fate::audio::assets::MUSIC_EXTENSIONS,
        )
        .unwrap_or_else(|| panic!("{key} missing"));
        assert_eq!(ext, "ogg");
        assert_eq!(&bytes[..4], b"OggS");
    }
}
```

Run: `cargo test -p freight-fate --test it synth_music` -- Expected: FAIL to compile.

- [ ] **Step 3: Implement**

`crates/freight-fate/src/audio/classic_music.rs`:

```rust
//! The three synthesized tracks Freight Fate shipped with in 1.0 to 1.5,
//! made by the game's own generator (tools/generate_audio.py, removed in
//! e751db73) and restored byte for byte from v1.5.0. Compiled in rather than
//! packed so Synthesized music never depends on either sound pack.

use ff_core::assets_pack::register_generated_sound;

const CLASSICS: [(&str, &[u8]); 3] = [
    ("music/classic_menu_theme", include_bytes!("../../assets/classic_music/classic_menu_theme.ogg")),
    ("music/classic_open_road", include_bytes!("../../assets/classic_music/classic_open_road.ogg")),
    ("music/classic_night_haul", include_bytes!("../../assets/classic_music/classic_night_haul.ogg")),
];

pub fn register() {
    for (key, bytes) in CLASSICS {
        register_generated_sound(key, bytes.to_vec(), "ogg");
    }
}
```

Add `pub mod classic_music;` to `crates/freight-fate/src/audio.rs`, call `crate::audio::classic_music::register();` beside `register_enforcement_sounds()` at startup. If `assets` or `MUSIC_EXTENSIONS` is not reachable from the test, make `assets` `pub` (it already is: `pub mod assets;`) and `MUSIC_EXTENSIONS` is already `pub`.

CREDITS.md, in the music section, add:

```markdown
| `music/classic_menu_theme` | "Headlights West", Freight Fate 1.0-1.5 menu theme | Procedurally generated by the game's own `tools/generate_audio.py` (removed in e751db73); restored from v1.5.0 |
| `music/classic_open_road` | "Open Road", Freight Fate 1.0-1.5 day drive | same |
| `music/classic_night_haul` | "Night Haul", Freight Fate 1.0-1.5 night drive | same |
```

Match the section's existing column layout.

- [ ] **Step 4: Run the tests**

Run: `cargo test -p freight-fate --test it synth_music`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crates/freight-fate/assets/classic_music crates/freight-fate/src/audio/classic_music.rs crates/freight-fate/src/audio.rs src/freight_fate/assets/sounds/CREDITS.md crates/freight-fate/tests/it/synth_music.rs
git add <the startup file edited in Step 3>
git commit -m "feat(music): restore the three 1.5 synth tracks

[skip changelog]

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Menus play synthesized music

**Files:**
- Modify: `crates/freight-fate/src/app/context.rs` (field `synth_worker: SynthWorker`; construct where `GameContext` is built; shut down where the app shuts down; `effective_sequence`; `resolve_synth`; real `restart_music`; `update_music_rotation` duration)
- Test: `crates/freight-fate/tests/it/synth_music.rs`

**Interfaces:**
- Consumes: `SynthWorker`, `select_synth_menu_sequence`, `SynthKey`, `classic_for`, `known_track_duration_s`, `hand_made::extras_for` (Task 11 -- until then pass `&[]`)
- Produces: `GameContext::resolve_synth(&mut self, key: &str) -> String` (the key if ready or not a synth key; otherwise requests it and returns its classic), `GameContext::request_synth(&self, key: &str)`, `GameContext::restart_music(&mut self)`

- [ ] **Step 1: Write the failing tests**

```rust
use ff_core::music_synth::{SynthKey, CLASSIC_MENU};

#[test]
fn synthesized_menus_open_on_headlights_west_and_hold_no_pack_music() {
    let mut app = TestApp::new();
    app.ctx.settings.synth_music = true;
    let original = ff_core::music::select_menu_music_sequence(None);
    let refs: Vec<&str> = original.iter().map(String::as_str).collect();
    let track = app.ctx.play_music_sequence("menu", &refs);
    assert_eq!(track, CLASSIC_MENU);
}

#[test]
fn an_unready_piece_falls_back_to_its_classic_and_is_requested() {
    let mut app = TestApp::new();
    let key = SynthKey { style: ff_core::music_synth::StyleId::Regional, music_seed: 5, index: 0 }.key();
    assert_eq!(app.ctx.resolve_synth(&key), CLASSIC_MENU);
    // The worker was asked: within a bounded wait the piece is published.
    let t = std::time::Instant::now();
    while !ff_core::music_synth::SynthWorker::is_ready(&key) && t.elapsed().as_secs() < 60 {
        std::thread::sleep(std::time::Duration::from_millis(20));
    }
    assert_eq!(app.ctx.resolve_synth(&key), key);
}

#[test]
fn switching_back_to_original_restores_the_soundtrack() {
    let mut app = TestApp::new();
    let original = ff_core::music::select_menu_music_sequence(None);
    let refs: Vec<&str> = original.iter().map(String::as_str).collect();
    app.ctx.settings.synth_music = true;
    app.ctx.play_music_sequence("menu", &refs);
    app.ctx.settings.synth_music = false;
    app.ctx.restart_music();
    assert_eq!(app.ctx.music_rotation_track(), Some(original[0].as_str()));
}
```

Run: `cargo test -p freight-fate --test it synth_music` -- Expected: FAIL.

- [ ] **Step 2: Implement in `context.rs`**

Add the field `pub synth_worker: ff_core::music_synth::SynthWorker,` to `GameContext`, initialised with `SynthWorker::start()` in every constructor (grep `GameContext {` in `crates/freight-fate/src` for them, including `app/testing.rs`). In the shutdown path (`sdl_shell.rs:156` `shutdown_for_process_exit` and `testing.rs:337` `shutdown`), call `self.ctx.synth_worker.shutdown(Duration::from_millis(2500))` alongside the other worker shutdowns, matching their logging.

Then:

```rust
    /// The sequence a pool actually plays: in Synthesized mode the menu pool
    /// is the synthesized ladder, whatever the caller passed.
    fn effective_sequence(&self, pool_name: &str, sequence: &[&str]) -> Vec<String> {
        if pool_name == "menu" && self.settings.synth_music {
            let profile = self.profile.as_ref().map(|p| p as &dyn ff_core::music::MenuMusicProfile);
            let extras = crate::audio::hand_made::extras_for(ff_core::music_synth::menu_style(profile));
            return ff_core::music_synth::select_synth_menu_sequence(profile, self.settings.music_seed, &extras);
        }
        sequence.iter().map(|s| s.to_string()).collect()
    }

    pub fn request_synth(&self, key: &str) {
        let _ = self.synth_worker.request(key);
    }

    /// A synth key that is not rendered yet plays its place's classic now and
    /// is queued for later; anything else passes through.
    pub fn resolve_synth(&mut self, key: &str) -> String {
        let Some(parsed) = ff_core::music_synth::SynthKey::parse(key) else {
            return key.to_string();
        };
        if ff_core::music_synth::SynthWorker::is_ready(key) {
            return key.to_string();
        }
        self.request_synth(key);
        ff_core::music_synth::classic_for(parsed.style).to_string()
    }
```

In `play_music_sequence_with`: keep storing the CALLER's `sequence` in `music_rotation_pool` (so switching back works), but pick from the effective one:

```rust
        let effective = self.effective_sequence(pool_name, sequence);
        let effective_refs: Vec<&str> = effective.iter().map(String::as_str).collect();
        let track = self.next_music_track(pool_name, &effective_refs);
        // ... existing empty check ...
        let track = self.resolve_synth(&track);
        // Queue the piece after this one so it is ready when this ends.
        if let Some(pos) = effective.iter().position(|k| *k == track) {
            if let Some(next) = effective.get((pos + 1) % effective.len()) {
                self.request_synth(next);
            }
        }
```

(`next_music_track` keys its position memory by the sequence; passing the effective one keeps positions per mode.) In the non-advance early return, compare against the effective mode too: if `self.settings.synth_music` changed since the rotation started, fall through to a restart. Simplest correct rule: store `music_rotation_synth: bool` beside `music_rotation_pool` and treat a mismatch as `advance = true`.

`restart_music`:

```rust
    pub fn restart_music(&mut self) {
        if let Some((pool, sequence)) = self.music_rotation_pool.clone() {
            let refs: Vec<&str> = sequence.iter().map(String::as_str).collect();
            self.music_pool_positions.clear();
            self.music_pool_last.remove(&pool);
            self.play_music_sequence_with(&pool, &refs, 800, true);
        }
        self.apply_active_radio_settings();
    }
```

`update_music_rotation`: replace `music_track_duration_s(track)` with `self.track_duration_s(track)`:

```rust
    /// How long `track` runs: the catalog or synth length, else what the
    /// music stream itself reports (hand-made and player files), else 60 s.
    pub fn track_duration_s(&self, track: &str) -> f64 {
        ff_core::music::known_track_duration_s(track)
            .or_else(|| self.audio.music_length_s())
            .unwrap_or(60.0)
    }
```

`Audio::music_length_s` is added in Task 10; until then add it to the `Audio` trait in `crates/freight-fate/src/audio.rs:680` region with a default body `fn music_length_s(&self) -> Option<f64> { None }` so every backend and test fake compiles.

Until Task 11 exists, create `crates/freight-fate/src/audio/hand_made.rs` with:

```rust
//! Hand-made pieces (tracker modules and audio files) per synthesized place.
//! Filled in by the hand-made task; empty until then.

use ff_core::music_synth::StyleId;

pub fn extras_for(_place: StyleId) -> Vec<String> {
    Vec::new()
}
```

and `pub mod hand_made;` in `audio.rs`.

- [ ] **Step 3: Run the tests**

Run: `cargo test -p freight-fate --test it synth_music` then the existing menu-music tests: `cargo test -p freight-fate --test it music`
Expected: PASS, and no change to Original-mode tests.

- [ ] **Step 4: Commit**

```bash
git add crates/freight-fate/src/app/context.rs crates/freight-fate/src/app/testing.rs crates/freight-fate/src/app/sdl_shell.rs crates/freight-fate/src/audio.rs crates/freight-fate/src/audio/hand_made.rs crates/freight-fate/tests/it/synth_music.rs
git commit -m "feat(music): menus play synthesized music in Synthesized mode

[skip changelog]

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: The Roadhouse in Synthesized mode

**Files:**
- Modify: `crates/freight-fate/src/states/driving_updates/radio.rs` (`station_rotation_pool` at `:322`, `start_station_rotation` at `:342`, `update_radio_playback` break branch at `:413`, `play_station_track` at `:434`, `station_sends_song_info` at `:579`, `radio_now_playing_text` at `:1030`, `apply_radio_settings_to_drive` at `:848`)
- Modify: `crates/ff-core/src/radio_rotation.rs:19-25` (`StationRotation::breaks: bool`) and `cue_after`'s break branch at `:124-128`; every `StationRotation { .. }` literal (grep)
- Modify: `crates/freight-fate/src/states/driving.rs` (field `synth_music_applied: Option<(bool, i64)>`, init `None` in `driving/init.rs`)
- Test: `crates/freight-fate/tests/it/synth_music.rs`

**Interfaces:**
- Consumes: `select_synth_drive_sequence`, `resolve_synth`, `request_synth`, `track_title`, `hand_made::extras_for`
- Produces: `DrivingState::synth_roadhouse(&self, ctx: &GameContext, station: &RadioStation) -> bool`

- [ ] **Step 1: Write the failing tests**

Model the drive setup on the existing Roadhouse rotation tests: run `grep -rn "route_playlist\|station_rotation_pool" crates/freight-fate/tests/it | head` and reuse that file's drive constructor (copy it into `synth_music.rs` as a local helper). Then:

```rust
#[test]
fn the_synthesized_roadhouse_plays_synth_music_and_no_host_breaks() {
    let mut app = TestApp::new();
    app.ctx.settings.synth_music = true;
    let mut d = a_drive(&mut app); // helper copied per the note above
    let station = d.radio.current_station();
    assert_eq!(station.playlist, "route");
    let pool = d.station_rotation_pool(&app.ctx, &station, false);
    assert!(pool.iter().all(|k| k.starts_with("synth_drive_day_") || k == "classic_open_road" || k.starts_with("hand_made/")));
    // Play through more tracks than a break interval: nothing from a host break.
    d.start_station_rotation(&mut app.ctx, &station, 0);
    for _ in 0..(ff_core::radio::RADIO_TRACKS_PER_HOST_BREAK * 2) {
        d.radio_elapsed_s = 1.0e9;
        d.update_radio_playback(&mut app.ctx, false, 0.0);
        assert!(d.radio_break_queue.is_empty());
    }
}

#[test]
fn now_playing_names_a_synthesized_piece() {
    let mut app = TestApp::new();
    app.ctx.settings.synth_music = true;
    let mut d = a_drive(&mut app);
    d.trip.truck.start_engine();
    let text = d.radio_now_playing_text(&mut app.ctx);
    assert!(text.contains("Synthesized: Day Drive, number") || text.contains("Open Road, from Freight Fate 1.5"), "{text}");
}

#[test]
fn original_mode_roadhouse_is_unchanged() {
    let mut app = TestApp::new();
    let d = a_drive(&mut app);
    let station = d.radio.current_station();
    assert_eq!(d.station_rotation_pool(&app.ctx, &station, false), d.day_music_sequence);
}
```

Fix the import path of `RADIO_TRACKS_PER_HOST_BREAK` to wherever `radio.rs` imports it from. Run and see FAIL.

- [ ] **Step 2: Implement**

`StationRotation` gains `pub breaks: bool,`; in `cue_after`, the `plan_break` branch runs only when `rotation.breaks`. Every existing literal passes `breaks: true`.

In `radio.rs`:

```rust
    /// The Roadhouse plays synthesized music, with no voiced breaks, when the
    /// Music source is Synthesized. No other station changes.
    pub fn synth_roadhouse(&self, ctx: &GameContext, station: &RadioStation) -> bool {
        ctx.settings.synth_music && station.playlist == "route"
    }
```

`station_rotation_pool` takes `ctx: &GameContext` as its first argument after `&self`; for the route playlist in Synthesized mode:

```rust
        if station.playlist == "route" {
            if ctx.settings.synth_music {
                let place = if night { StyleId::NightDrive } else { StyleId::DayDrive };
                return select_synth_drive_sequence(
                    night,
                    ctx.settings.music_seed,
                    self.trip_seed,
                    &crate::audio::hand_made::extras_for(place),
                );
            }
            return if night { self.night_music_sequence.clone() } else { self.day_music_sequence.clone() };
        }
```

Update its callers (grep `station_rotation_pool(`). `station_cue` builds `StationRotation { .., breaks: !ctx.settings.synth_music || station.playlist != "route" }` -- give `station_cue` a `ctx: &GameContext` parameter too.

In `update_radio_playback`, guard the break planning: `if self.radio_tracks_since_break >= RADIO_TRACKS_PER_HOST_BREAK && !self.synth_roadhouse(ctx, &station) {`.

Resolve before every play of a playlist entry, substituting in place so the duration check reads what is actually playing:

```rust
    pub fn play_station_track(&mut self, ctx: &mut GameContext, fade_ms: u32) {
        let i = self.radio_track_index % self.radio_playlist.len();
        let key = ctx.resolve_synth(&self.radio_playlist[i]);
        self.radio_playlist[i] = key.clone();
        if let Some(next) = self.radio_playlist.get((i + 1) % self.radio_playlist.len()) {
            ctx.request_synth(next);
        }
        ctx.audio.play_music_with(&key, fade_ms);
    }
```

Do the same substitution for the `key` in `start_station_rotation` before `play_music_at`. Replace `content_duration_s(&current)` in `update_radio_playback` with `ff_core::music::known_track_duration_s(&current).map_or_else(|| ctx.track_duration_s(&current), |d| d)` only when `current` is not a break item -- simplest: `let len = if self.radio_break_queue.is_empty() { ctx.track_duration_s(&current) } else { content_duration_s(&current) };`.

Now playing: `station_sends_song_info` becomes a method with `ctx` access or checks a cached flag; the minimal change is in `radio_now_playing_text`, before the `station_sends_song_info` check:

```rust
        if self.synth_roadhouse(ctx, &station) {
            let current = self.radio_playlist.get(self.radio_track_index % self.radio_playlist.len().max(1)).cloned().unwrap_or_default();
            if let Some(title) = ff_core::music_synth::track_title(&current)
                .or_else(|| crate::audio::hand_made::title_for(&current))
            {
                return format!("Now playing on {}: {title}.", station.display_name());
            }
        }
```

(`hand_made::title_for` is added in Task 11; until then add `pub fn title_for(_key: &str) -> Option<String> { None }` to the stub.)

Settings changes reach the drive through `apply_radio_settings_to_drive`: at its top,

```rust
        let synth = (ctx.settings.synth_music, ctx.settings.music_seed);
        if self.synth_music_applied != Some(synth) {
            let restart = self.synth_music_applied.is_some();
            self.synth_music_applied = Some(synth);
            if restart && self.radio.current_station().playlist == "route" {
                self.radio_station_id.clear(); // next playback tick restarts the rotation
            }
        }
```

Add `pub synth_music_applied: Option<(bool, i64)>,` to `DrivingState` (`driving.rs`) and `synth_music_applied: None,` in `driving/init.rs`.

- [ ] **Step 3: Run the tests**

Run: `cargo test -p freight-fate --test it synth_music`, then `cargo test -p freight-fate --test it radio` and `cargo test -p ff-core radio_rotation`
Expected: PASS; Original-mode radio tests unchanged.

- [ ] **Step 4: Commit**

```bash
git add crates/ff-core/src/radio_rotation.rs crates/freight-fate/src/states/driving_updates/radio.rs crates/freight-fate/src/states/driving.rs crates/freight-fate/src/states/driving/init.rs crates/freight-fate/src/audio/hand_made.rs crates/freight-fate/tests/it/synth_music.rs
git commit -m "feat(radio): the Roadhouse plays synthesized music with no voiced breaks

[skip changelog]

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 10: Tracker modules through BASS

**Files:**
- Modify: `crates/bass-sys/src/lib.rs` (fn types + flags), `crates/bass-sys/src/loader.rs:126-160,274-287` (fields + `sym!`), `crates/bass-sys/src/safe.rs` (`music_load_mem_shared`, `Stream` frees by kind)
- Modify: `crates/freight-fate/src/audio/assets.rs:32` (`MUSIC_EXTENSIONS`), `crates/freight-fate/src/audio/bass.rs:356-373` (`make_stream` picks the loader by extension), `crates/freight-fate/src/audio/bass_radio.rs:104` and `play_music_with`'s equivalent (pass the extension), `bass_backend.rs` (`music_length_s`)
- Test: `crates/freight-fate/tests/it/synth_music.rs`

**Interfaces:**
- Produces: `bass_sys::safe::music_load_mem_shared(data: Arc<[u8]>, flags: u32) -> Result<Stream, BassError>`; `Stream` records whether it is a music handle and calls `BASS_MusicFree` for it; `MODULE_EXTENSIONS: &[&str] = &["it", "xm", "s3m", "mod", "mo3"]`; `Audio::music_length_s(&self) -> Option<f64>` on the BASS backend returns the playing music stream's length.

- [ ] **Step 1: Declare the BASS calls**

In `crates/bass-sys/src/lib.rs`, beside `FnStreamFree`:

```rust
/// `HMUSIC BASS_MusicLoad(BOOL mem, const void *file, QWORD offset, DWORD length, DWORD flags, DWORD freq)`
pub type FnMusicLoad = unsafe extern "system" fn(
    mem: BOOL,
    file: *const c_void,
    offset: QWORD,
    length: DWORD,
    flags: DWORD,
    freq: DWORD,
) -> DWORD;
/// `BOOL BASS_MusicFree(HMUSIC handle)`
pub type FnMusicFree = unsafe extern "system" fn(handle: DWORD) -> BOOL;

/// Volume ramping, to avoid clicks.
pub const BASS_MUSIC_RAMPS: DWORD = 0x400;
/// Sinc interpolation.
pub const BASS_MUSIC_SINCINTER: DWORD = 0x80_0000;
/// Calculate the length on load, so ChannelGetLength answers.
pub const BASS_MUSIC_PRESCAN: DWORD = 0x2_0000;
```

(`c_void` is already imported where `FnStreamCreateFile` takes `*const c_void`; reuse that import.) In `loader.rs`, add fields `pub music_load: FnMusicLoad, pub music_free: FnMusicFree,` after `stream_free`, and `music_load: sym!("BASS_MusicLoad"), music_free: sym!("BASS_MusicFree"),` after `stream_free: sym!(...)`.

- [ ] **Step 2: A safe wrapper**

In `safe.rs`, give `Stream` a `music: bool` field (set `false` in every existing constructor), and in its `Drop` call `(a.music_free)(self.handle)` when `self.music` else the existing `stream_free`. Then:

```rust
/// `BASS_MusicLoad(TRUE, ..)` over a shared buffer: a tracker module (IT, XM,
/// S3M, MOD, MO3) as a playable channel. BASS copies module data on load,
/// but the buffer is kept like a stream's for one ownership rule.
pub fn music_load_mem_shared(data: Arc<[u8]>, flags: u32) -> Result<Stream, BassError> {
    let a = lib()?;
    let len = DWORD::try_from(data.len()).map_err(|_| BassError::from_code(BASS_ERROR_FILEFORM))?;
    // SAFETY: `data` is a valid buffer of `len` bytes, alive for the call and
    // pinned in the returned Stream until MusicFree.
    let handle = unsafe { (a.music_load)(1, data.as_ptr().cast(), 0, len, flags, 0) };
    if handle == 0 {
        return Err(BassError::last());
    }
    Ok(Stream { handle, _buffer: Some(data), music: true })
}
```

If `BassError::from_code` / `BASS_ERROR_FILEFORM` do not exist, use whatever constructor `safe.rs` already uses for a synthetic error (read it) -- do not add a panic.

- [ ] **Step 3: Write the failing test**

A tiny valid module is needed as a fixture. Build a minimal 4-channel ProTracker MOD in the test (1084-byte header + one pattern of silence + one short sample) so no binary fixture is committed:

```rust
/// The smallest ProTracker MOD BASS will load: one 64-row pattern playing a
/// 32-sample square wave on channel 1, row 0. 1084 + 1024 + 32 bytes.
fn tiny_mod() -> Vec<u8> {
    let mut m = vec![0u8; 1084];
    m[..4].copy_from_slice(b"tiny");
    // Sample 1 header at offset 20: 22 name bytes, then length in words.
    m[20 + 22..20 + 24].copy_from_slice(&16u16.to_be_bytes()); // 32 bytes
    m[20 + 25] = 64; // volume
    m[20 + 28..20 + 30].copy_from_slice(&1u16.to_be_bytes()); // repeat length 1 word (no loop)
    m[950] = 1; // song length: 1 position
    m[951] = 127;
    m[952] = 0; // order 0 -> pattern 0
    m[1080..1084].copy_from_slice(b"M.K.");
    let mut pattern = vec![0u8; 1024];
    // Row 0 channel 0: sample 1, period 428 (C-2).
    pattern[0] = 0x01;
    pattern[1] = 0xAC;
    pattern[2] = 0x10;
    m.extend_from_slice(&pattern);
    m.extend((0..32).map(|i| if i < 16 { 0x40u8 } else { 0xC0u8 }));
    m
}

#[test]
fn a_tracker_module_plays_as_music_and_reports_its_length() {
    let Some(mut app) = TestApp::with_bass() else {
        eprintln!("BASS not installed; skipping");
        return;
    };
    ff_core::assets_pack::register_generated_sound("music/hand_made/test/tiny", tiny_mod(), "mod");
    app.ctx.audio.play_music_with("hand_made/test/tiny", 0);
    assert!(app.ctx.audio.music_playing());
    let len = app.ctx.audio.music_length_s().expect("module length");
    assert!(len > 0.5 && len < 30.0, "{len}");
}
```

If `TestApp::with_bass` does not exist, find how the existing audio tests reach the real BASS backend (`grep -rn "BassBackend::new\|with_bass\|fetch_bass" crates/freight-fate/tests/it | head`) and use that; keep the skip-when-missing behaviour those tests use. Run and see FAIL.

- [ ] **Step 4: Implement playback**

`assets.rs`:

```rust
pub const MODULE_EXTENSIONS: &[&str] = &["it", "xm", "s3m", "mod", "mo3"];
pub const MUSIC_EXTENSIONS: &[&str] = &["opus", "ogg", "wav", "mp3", "flac", "it", "xm", "s3m", "mod", "mo3"];
```

(Check `mp3`/`flac` are handled by the plugins BASS loads at startup -- `plugin_load` in `bass.rs`. If not, leave them out.)

`bass.rs` `make_stream` gains an `ext: &str` parameter:

```rust
        let opened = if MODULE_EXTENSIONS.contains(&ext) {
            safe::music_load_mem_shared(
                data,
                BASS_MUSIC_RAMPS | BASS_MUSIC_SINCINTER | BASS_MUSIC_PRESCAN | BASS_STREAM_AUTOFREE,
            )
        } else {
            safe::stream_create_mem_shared(data, BASS_STREAM_AUTOFREE)
        };
        let stream = match opened { /* existing Ok/Err arms */ };
```

Pass the extension from every caller (`asset_bytes` already returns it; callers currently bind it as `_ext`). `BASS_STREAM_AUTOFREE` equals `BASS_MUSIC_AUTOFREE` (0x40000) in BASS, so the flag is valid for both.

`music_length_s` on the BASS backend:

```rust
    fn music_length_s(&self) -> Option<f64> {
        let stream = self.music_stream.as_ref()?;
        let bytes = safe::channel_get_length_bytes(stream.handle()).ok()?;
        safe::bytes_to_seconds(stream.handle(), bytes).ok().filter(|s| *s > 0.0)
    }
```

Use the existing `safe` helpers for `BASS_ChannelGetLength` and `BASS_ChannelBytes2Seconds` (grep `channel_get_length` and `seconds_to_bytes` in `safe.rs`; add the `bytes2seconds` symbol in the loader the same way as Step 1 if it is missing). Route `BassBackend`'s `Audio` impl to it.

- [ ] **Step 5: Run the tests**

Run: `uv run python tools/fetch_bass.py` if BASS is not present, then `cargo test -p freight-fate --test it synth_music` and `cargo test -p bass-sys`
Expected: PASS (the module test must actually run, not skip -- check its output with `-- --nocapture`).

- [ ] **Step 6: Commit**

```bash
git add crates/bass-sys/src/lib.rs crates/bass-sys/src/loader.rs crates/bass-sys/src/safe.rs crates/freight-fate/src/audio/assets.rs crates/freight-fate/src/audio/bass.rs crates/freight-fate/src/audio/bass_radio.rs crates/freight-fate/src/audio/bass_backend.rs crates/freight-fate/src/audio.rs crates/freight-fate/tests/it/synth_music.rs
git commit -m "feat(audio): play tracker modules as music through BASS

[skip changelog]

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 11: DROPPED (owner, 2026-09-21)

Hand-made pieces and a player music folder are not built: personal radio
playlists already cover a player's own music, and Task 10 lets a playlist
entry be a tracker module (`play_music_file` opens through `make_stream`
with the file's extension). Task 12 removes the empty `audio::hand_made`
stub and the `extras` parameters it fed.

---

### Task 12: The radio dial in Synthesized mode

Owner rulings, 2026-09-21:
- **Music source Original:** the radio behaves exactly as today, with streamer-safe on or off. Nothing in this task changes Original mode.
- **Synthesized, streamer-safe on:** the synthesized Roadhouse is the only station. Station commands do not change the station and say so; the radio key is just on/off.
- **Synthesized, streamer-safe off:** the fictional Freight Fate stations are gone from the dial (every station in dial group 1 -- `source_type == "built_in"` or playlist-backed non-stream stations -- except the Roadhouse, which is group 0). The dial and the category key cycle the synthesized Roadhouse, terrestrial stations, web streams and personal playlists, as today.
- Menus play synthesized music whenever Music source is Synthesized (Task 8 already does this).

**Files:**
- Modify: `crates/ff-core/src/radio/state.rs` (`station_allowed` ~`:956`, `tune` ~`:642`, `tune_category` ~`:736`, `select_station` ~`:772`, `toggle_favorite` ~`:1045`, and every other public station-changing entry point: read the whole `impl RadioState`), and the settings view trait at ~`:35` (`radio_streamer_safe`) to also carry the Music source
- Modify: `crates/ff-core/src/radio.rs` (`dial_group` ~`:584` is read, not changed; the constant goes here)
- Modify: `crates/freight-fate/src/states/driving_core.rs` (~`:885`, `:905`: the `RadioSettingsView` impls gain the new method)
- Modify: `crates/freight-fate/src/states/driving_updates/radio.rs` (`station_allowed` ~`:823`) and `radio_synth.rs` (Task 9's `synth_roadhouse`)
- Modify: every game-side handler that changes station or opens the station browser, radio app, favorites or playlists (find them from the controls bindings table: `grep -rn "radio" crates/freight-fate/src/states/driving_controls/`)
- Modify: `crates/freight-fate/src/states/main_menu/settings_items.rs` (the streamer-safe row's help, ~`:812`; the Music source row's help from Task 6)
- Test: `crates/ff-core/src/radio/tests.rs`, `crates/freight-fate/tests/it/synth_music.rs`

**Interfaces:**
- Consumes: `DrivingState::synth_roadhouse` (Task 9), `SAFE_ROUTE_PLAYLIST`, `dial_group`
- Produces: `pub const STREAMER_SAFE_LOCKED: &str = "Streamer-safe mode keeps the radio on the Roadhouse.";` in `ff_core::radio`; `RadioSettingsView::synth_music(&self) -> bool`; `RadioState::synth_music: bool` (set from the view in both places `streamer_safe` is set, ~`:153` and ~`:199`)

**Required behaviour:**
- `station_allowed` (both the ff-core `RadioState` gate and the driving state's copy), when Music source is Synthesized:
  - streamer-safe on: only `SAFE_ROUTE_PLAYLIST` is allowed;
  - streamer-safe off: a station in dial group 1 (Freight Fate's own stations) is not allowed; the Roadhouse, terrestrial stations, web streams and personal playlists follow today's rules.
  - Original: today's rules, unchanged.
- `synth_roadhouse` is unchanged in meaning (Roadhouse and Music source Synthesized); this task does not widen it.
- Changing Music source or streamer-safe mid-drive moves the radio off a station that is no longer allowed onto the Roadhouse (the existing `apply_radio_settings_to_drive` path already moves off a disallowed station to `SAFE_ROUTE_PLAYLIST`; confirm it does for both new rules, with a test), and the settings restart from Task 9 still fires.
- In Synthesized + streamer-safe, every station-changing command (tune up/down, seek/scan, category tune, select by name or number, favorites, the station browser or radio app, personal playlists) leaves the station unchanged and speaks `STREAMER_SAFE_LOCKED` on the channel that command already uses. Never silent. The radio power key still turns the radio on and off; volume and now playing still work.
- In Synthesized with streamer-safe off, the plain dial and the category key simply skip Freight Fate's own stations because they are not allowed; the category key cycles only categories that still have an allowed station (it already builds its group list from receivable stations -- confirm the filtered stations drop out of `receivable_stations`).
- **Also in this task (Task 11 was dropped):** delete `crates/freight-fate/src/audio/hand_made.rs` and its `pub mod hand_made;`; remove the `extras` parameter from `ff_core::music_synth::select_synth_menu_sequence` and `select_synth_drive_sequence` and every caller (app/synth_music.rs, states/driving_updates/radio_synth.rs); drop the `hand_made::title_for` fallback in the Roadhouse now-playing; update the ff-core test `extras_join_the_rotation_and_the_seed_changes_every_piece` to keep only its seed and classic assertions (rename it `the_seed_changes_every_piece`), and the game test's `hand_made/` allowance in the Roadhouse pool assertion. The `hand_made/test/...` keys in the Task 10 module tests are just test asset names; leave them.
- Settings help strings, exactly:
  - streamer-safe row: `Off plays the full dial, including real public streams and personal playlists. On keeps the radio to built-in safe stations, for streaming or recording. With Music source set to Synthesized, On keeps the radio on the Roadhouse and station keys do nothing.`
  - Music source row: `Synthesized plays menu music and the Roadhouse station made by the game itself, with no AI-made songs or voices, and takes Freight Fate's other stations off the dial. Original plays the full soundtrack.`

- [ ] **Step 1: Write the failing tests**

In `crates/ff-core/src/radio/tests.rs`, build `RadioState`s the way the neighbouring streamer-safe tests do (read them first; give the settings view the new `synth_music` answer), then write one test per rule:

```rust
#[test]
fn synthesized_streamer_safe_allows_only_the_roadhouse() {
    let mut radio = radio_with(/* synth_music */ true, /* streamer_safe */ true);
    let allowed: Vec<String> = radio
        .receivable_stations()
        .into_iter()
        .filter(|r| !r.fallback)
        .map(|r| r.station.id)
        .collect();
    assert_eq!(allowed, vec![SAFE_ROUTE_PLAYLIST.to_string()]);
}

#[test]
fn synthesized_dial_drops_freight_fate_stations_but_keeps_the_rest() {
    let mut radio = radio_with(true, false);
    let groups: Vec<i32> = radio.receivable_stations().iter().map(|r| dial_group(&r.station)).collect();
    assert!(!groups.contains(&1), "a Freight Fate station is still on the dial");
    assert!(groups.contains(&0), "the Roadhouse is gone");
    // And at least one terrestrial or web station remains, whichever the
    // fixture catalog provides (assert on the fixture's known ids).
}

#[test]
fn original_mode_dial_is_unchanged() {
    // With synth_music false, receivable_stations is identical, id for id,
    // to what it was before this task for both streamer-safe settings.
    // Build both and compare against a radio with the view answering false
    // for synth_music -- or against the fixture's pinned list if the file
    // pins one.
}

#[test]
fn synthesized_streamer_safe_refuses_every_station_command_out_loud() {
    let mut radio = radio_with(true, true);
    let before = radio.current_station().id;
    // One call per station-changing method: tune (both directions),
    // tune_category, select_station, toggle_favorite, and any other found.
    // After each: the station is unchanged and the spoken text carries
    // STREAMER_SAFE_LOCKED.
    assert_eq!(radio.current_station().id, before);
}
```

Write `radio_with` as a small local helper; fill in the assertions the comments describe with the real method names and fixture ids from `state.rs` and `tests.rs`. In `synth_music.rs`, using the `a_drive` helper from Task 9: with Synthesized + streamer-safe, pressing each station-changing driving control (through the same key path the existing radio control tests use) leaves the station on the Roadhouse and puts `Streamer-safe mode keeps the radio on the Roadhouse.` in the transcript, and the radio power key turns the radio off and back on; with Synthesized and streamer-safe off, stepping the dial through every station never lands on a Freight Fate station; with Original, stepping the dial reaches a Freight Fate station exactly as before; tuned to a Freight Fate station in Original, switching Music source to Synthesized moves the radio to the Roadhouse.

- [ ] **Step 2: Run to see them fail**

Run: `cargo test -p ff-core radio` and `cargo test -p freight-fate --test it synth_music`
Expected: the new tests FAIL.

- [ ] **Step 3: Implement**

Add the constant to `ff_core::radio` (re-exported with the other radio constants). Add `fn synth_music(&self) -> bool;` to the radio settings view trait and implement it in both driving-core views (`self.0.synth_music`) and every test fake of that trait (grep the implementors). Store it on `RadioState` alongside `streamer_safe` in both places `streamer_safe` is set. In both `station_allowed` gates, before the existing real-stream check:

```rust
        if self.synth_music {
            if self.streamer_safe && station.id != SAFE_ROUTE_PLAYLIST {
                return false;
            }
            if station.id != SAFE_ROUTE_PLAYLIST && dial_group(station) == 1 {
                return false;
            }
        }
```

(driving copy: `self.radio.synth_music` / `self.radio.streamer_safe`). At the top of each station-changing `RadioState` method, when `self.synth_music && self.streamer_safe`, return that method's normal "nothing changed" result carrying `STREAMER_SAFE_LOCKED` as its spoken text. Game-side handlers that bypass `RadioState` (station browser, playlists) check `ctx.settings.synth_music && ctx.settings.radio_streamer_safe` and speak the constant instead of opening. Update the two help strings. Keep every existing radio test passing unchanged: they run in Original mode.

- [ ] **Step 4: Run the tests**

Run: `cargo test -p ff-core radio`, `cargo test -p freight-fate --test it synth_music`, `cargo test -p freight-fate --test it radio`, `cargo test -p freight-fate --test it settings`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add <each file you changed, explicitly>
git commit -m "feat(radio): Synthesized mode takes Freight Fate's stations off the dial; streamer-safe keeps it on the Roadhouse

[skip changelog]

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 13: Docs, gates, and a real listen

**Files:**
- Modify: `CHANGELOG.md` (`## Unreleased`, `### Added`), `ROADMAP.md` (1.9 line), the player manual's audio settings section (find with `grep -rln "Music volume" docs/`)

- [ ] **Step 1: Changelog** (follow `.claude/skills/writing-changelog-entries`; run the avoid-ai-writing skill on the result)

Under `### Added`:

```markdown
- **Music source can be set to Synthesized, for music with no AI.** Menus and the Roadhouse play music the game composes itself, with no voiced breaks.

- **A music seed changes every synthesized piece.** Settings, Audio, Music seed rolls a new one and says it, so you can share one you like.

- **The original 1.5 soundtrack is back in Synthesized mode.** Headlights West, Open Road and Night Haul return.

- **Synthesized mode takes Freight Fate's own stations off the radio.** The dial keeps the synthesized Roadhouse, local and web stations, and your playlists.

- **In Synthesized mode, streamer-safe keeps the radio on the Roadhouse.** Station keys stay put and say so; the radio key turns it on and off.

- **Radio playlists can play tracker modules.** Music made in OpenMPT and similar trackers plays like any other file in your playlist.
```

- [ ] **Step 2: Roadmap and manual**

ROADMAP.md, current 1.9 section: a checked bullet "Synthesized music source (no AI): seeded composer, 14 styles on a career-path ladder, restored 1.5 tracks, tracker modules and a player music folder", and unchecked follow-ups: "Typed-in music seeds", "More synth voices per style", "Compose shipped hand-made modules for each place", "Export generated pieces as XM sketches for OpenMPT". Manual: the two rows, the folder layout (`music/<place>/`), the list of place folder names from `StyleId::ALL` ids, and supported formats.

- [ ] **Step 3: Gates**

Run in the background, one at a time, redirecting to files and reading the counts (never pipe to `tail`):

```bash
cargo fmt --all --check
cargo clippy --all-targets --locked -- -D warnings
cargo test -p ff-core -p freight-fate
cargo run -p freight-fate --bin freightfate -- --break-battery
```

Expected: fmt clean, clippy clean, all tests pass, every battery scenario CLEAN.

- [ ] **Step 4: Listen through the agent server**

Build first: `cargo build --release -p freight-fate --bin freightfate` (kill any idle `--agent-server` process holding the exe). Then with the freight-fate MCP tools: `scenario` with `settings: {"synth_music": true}` at level 1 company driver, `listen` at the terminal (expect the classic, then a `Synthesized: New Hire` piece on the next track); `scenario` with `business: "independent"`, `level: 7` (expect `Coast to Coast` pieces); `start_at` `feature: "departure"`, drive two tracks on the Roadhouse and press the now-playing key (expect `Now playing on ...: Synthesized: Day Drive, number N.` and no host break); open Settings from the pause menu, roll the seed (expect `New music seed, ...` and the music restarting). `quit_game` at the end. Record anything a driver needed but could not hear.

- [ ] **Step 5: Commit and push**

```bash
git add CHANGELOG.md ROADMAP.md <manual file>
git commit -m "docs: synthesized music source, seed, classics and hand-made modules

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

Then ask the owner for a listening pass: menus on each branch, a Roadhouse night drive, and a module of his own in `music/drive_day/`.
