//! The Roadhouse in Synthesized mode: synthesized music, no voiced breaks,
//! and a title on now playing. Its own file because `radio` is already past
//! the 1000-line limit. Every decision here goes through
//! [`DrivingState::synth_roadhouse`], so widening that one predicate widens
//! all of them.

use ff_core::music_synth::{select_synth_drive_sequence, track_title};
use ff_core::radio::RadioStation;
use ff_core::radio_content::content_duration_s;

use crate::app::GameContext;
use crate::states::driving::DrivingState;
use crate::states::driving_core::is_night;

impl DrivingState {
    /// The Roadhouse plays synthesized music, with no voiced breaks, when the
    /// Music source is Synthesized. No other station changes.
    pub fn synth_roadhouse(&self, ctx: &GameContext, station: &RadioStation) -> bool {
        ctx.settings.synth_music && station.playlist == "route"
    }

    /// The synthesized rotation for `station`, or `None` when it plays its
    /// ordinary pool.
    pub(crate) fn synth_roadhouse_pool(
        &self,
        ctx: &GameContext,
        station: &RadioStation,
        night: bool,
    ) -> Option<Vec<String>> {
        if !self.synth_roadhouse(ctx, station) {
            return None;
        }
        Some(select_synth_drive_sequence(
            night,
            ctx.settings.music_seed,
            self.trip_seed,
        ))
    }

    /// The playlist entry at `index`, resolved in place: an unrendered piece
    /// becomes its place's classic, so the length check reads what is really
    /// playing. The entry after it is queued for rendering -- asked for
    /// before this one, since this one already has a classic to fall back on
    /// and the worker's queue is small enough that the wrong order can starve
    /// the piece the next track change actually needs. Anything that is not
    /// a synthesized key passes through untouched. Shared by both
    /// `start_station_rotation` (tuning in) and `play_station_track` (a
    /// track change), so a rotation always keeps one piece ahead of itself.
    pub(crate) fn resolve_station_track(&mut self, ctx: &mut GameContext, index: usize) -> String {
        let len = self.radio_playlist.len();
        let Some(entry) = self.radio_playlist.get(index % len.max(1)).cloned() else {
            return String::new();
        };
        if let Some(next) = self.radio_playlist.get((index + 1) % len).cloned() {
            ctx.request_synth(&next);
        }
        let key = ctx.resolve_synth(&entry);
        self.radio_playlist[index % len] = key.clone();
        key
    }

    /// How long the playlist entry `current` runs. A synthesized piece's
    /// length means composing it, so it is looked up once per track and
    /// cached rather than every frame.
    pub(crate) fn station_track_len_s(
        &mut self,
        ctx: &GameContext,
        station: &RadioStation,
        current: &str,
    ) -> f64 {
        if !self.synth_roadhouse(ctx, station) {
            return content_duration_s(current);
        }
        if let Some((key, len)) = &self.radio_track_len {
            if key == current {
                return *len;
            }
        }
        let len = ctx.track_duration_s(current);
        self.radio_track_len = Some((current.to_string(), len));
        len
    }

    /// Now playing on the synthesized Roadhouse: the piece's title, or `None`
    /// when this is not the synthesized Roadhouse or the track has no title.
    pub(crate) fn synth_now_playing(
        &self,
        ctx: &GameContext,
        station: &RadioStation,
    ) -> Option<String> {
        if !self.synth_roadhouse(ctx, station) {
            return None;
        }
        let current = if self.radio_station_id == station.id && !self.radio_playlist.is_empty() {
            self.radio_playlist[self.radio_track_index % self.radio_playlist.len()].clone()
        } else {
            // The rotation has not started yet: name what the station is on.
            let pool = self
                .synth_roadhouse_pool(ctx, station, is_night(self.trip.current_hour()))
                .unwrap_or_default();
            self.station_cue(ctx, station, &pool).current_key(&pool)
        };
        let title = track_title(&current)?;
        Some(format!(
            "Now playing on {}: {title}.",
            station.display_name()
        ))
    }

    /// What a Roadhouse rotation started now would be built from: whether it
    /// is synthesized, and the seed when it is. The seed only matters while
    /// it is synthesized, so a roll in Original mode changes nothing.
    ///
    /// Read off the setting alone, never off `self.radio`: a rotation starts
    /// inside `with_radio_backend`, which has swapped `self.radio` for an
    /// empty stand-in, so looking the Roadhouse up there recorded Original
    /// under a Synthesized playlist. A switch to Original then compared equal
    /// and never restarted it (agent drive, 2026-09-23). The Roadhouse is the
    /// one route-playlist station, so the setting is the whole answer.
    pub(crate) fn roadhouse_synth_state(&self, ctx: &GameContext) -> (bool, i64) {
        let synth = ctx.settings.synth_music;
        (synth, if synth { ctx.settings.music_seed } else { 0 })
    }

    /// A Music source or seed change restarts the Roadhouse's rotation on the
    /// next playback tick, so the new music is heard at once. Nothing to do
    /// before any rotation has started.
    pub(crate) fn restart_roadhouse_on_synth_change(&mut self, ctx: &GameContext) {
        let now = self.roadhouse_synth_state(ctx);
        if self
            .synth_music_applied
            .is_none_or(|applied| applied == now)
        {
            return;
        }
        self.synth_music_applied = Some(now);
        if self.radio.current_station().playlist == "route" {
            self.radio_station_id.clear();
        }
    }
}
