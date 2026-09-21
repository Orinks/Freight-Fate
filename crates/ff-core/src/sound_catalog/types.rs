/// One sounding inside a demo: what to play, how, and when.
///
/// `hold_s` above zero makes this a held loop rather than a one-shot: the
/// demo re-asserts it for that many seconds and then releases it. `delay_s`
/// is measured from the start of the whole demo, not from the previous cue.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Cue {
    pub key: &'static str,
    pub volume: f64,
    pub pan: f64,
    pub delay_s: f64,
    pub hold_s: f64,
    pub fallback: &'static str,
}

impl Cue {
    /// A centred one-shot at full volume, played at the start of the demo.
    pub const fn new(key: &'static str) -> Self {
        Self {
            key,
            volume: 1.0,
            pan: 0.0,
            delay_s: 0.0,
            hold_s: 0.0,
            fallback: "",
        }
    }

    pub const fn volume(mut self, volume: f64) -> Self {
        self.volume = volume;
        self
    }

    pub const fn pan(mut self, pan: f64) -> Self {
        self.pan = pan;
        self
    }

    pub const fn delay_s(mut self, delay_s: f64) -> Self {
        self.delay_s = delay_s;
        self
    }

    pub const fn hold_s(mut self, hold_s: f64) -> Self {
        self.hold_s = hold_s;
        self
    }

    pub const fn fallback(mut self, fallback: &'static str) -> Self {
        self.fallback = fallback;
        self
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct SoundEntry {
    /// the canonical spoken noun, from docs/ontology.md
    pub name: &'static str,
    pub plays: &'static [Cue],
    /// what it tells you, and what to do about it
    pub meaning: &'static str,
    /// the setting or situation that gates it, if any
    pub when: &'static str,
}

impl SoundEntry {
    pub const fn new(name: &'static str, plays: &'static [Cue], meaning: &'static str) -> Self {
        Self {
            name,
            plays,
            meaning,
            when: "",
        }
    }

    pub const fn when(mut self, when: &'static str) -> Self {
        self.when = when;
        self
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct SoundCategory {
    pub name: &'static str,
    pub entries: &'static [SoundEntry],
}
