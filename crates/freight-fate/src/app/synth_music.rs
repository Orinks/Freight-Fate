//! Synthesized mode for the menu music rotation: which sequence a pool
//! really plays, the classic that stands in while a piece renders, and the
//! restart a music setting change asks for. Its own file because `context`
//! is already past the 1000-line limit.

use ff_core::music::MenuMusicProfile;
use ff_core::music_synth::{classic_for, select_synth_menu_sequence, SynthKey, SynthWorker};

use super::GameContext;

impl GameContext {
    /// The sequence a pool actually plays: in Synthesized mode the menu pool
    /// is the synthesized ladder, whatever the caller passed.
    pub(crate) fn effective_sequence(&self, pool_name: &str, sequence: &[&str]) -> Vec<String> {
        if pool_name == "menu" && self.settings.synth_music {
            let profile = self.profile.as_ref().map(|p| p as &dyn MenuMusicProfile);
            return select_synth_menu_sequence(profile, self.settings.music_seed);
        }
        sequence.iter().map(|s| s.to_string()).collect()
    }

    /// Ask the worker to render `key`; a no-op for anything not synthesized,
    /// and a full queue just means it is asked again next track.
    pub fn request_synth(&self, key: &str) {
        let _ = self.synth_worker.request(key);
    }

    /// A synth key that is not rendered yet plays its place's classic now and
    /// is queued for later; anything else passes through.
    pub fn resolve_synth(&mut self, key: &str) -> String {
        let Some(parsed) = SynthKey::parse(key) else {
            return key.to_string();
        };
        // Requesting even a ready piece marks it in use, so the worker cannot
        // evict it between this check and the play call.
        self.request_synth(key);
        if SynthWorker::is_ready(key) {
            return key.to_string();
        }
        classic_for(parsed.style).to_string()
    }

    /// How long `track` runs: the catalog or synth length, else what the
    /// music stream itself reports (hand-made and player files), else 60 s.
    pub fn track_duration_s(&self, track: &str) -> f64 {
        ff_core::music::known_track_duration_s(track)
            .or_else(|| self.audio.music_length_s())
            .unwrap_or(60.0)
    }

    /// Restart whatever music is playing so a music setting is heard at once:
    /// the menu rotation from the top of its (possibly now synthesized)
    /// sequence, and a drive's radio under the menus.
    pub fn restart_music(&mut self) {
        if let Some((pool, sequence)) = self.music_rotation_pool.clone() {
            let refs: Vec<&str> = sequence.iter().map(String::as_str).collect();
            self.music_pool_positions.clear();
            self.music_pool_last.remove(&pool);
            self.play_music_sequence_with(&pool, &refs, 800, true);
        }
        self.apply_active_radio_settings();
    }
}
