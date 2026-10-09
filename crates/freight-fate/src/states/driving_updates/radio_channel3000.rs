//! Channel 3000 on 87.7: playing the schedule `ff_core::channel3000` runs.
//!
//! The station is always on the air. Its schedule advances on the same
//! airtime clock as every other station (`advance_radio_airtime`), whether
//! the radio is on it, on another station or off, and it reads the truck's
//! local hour as it goes, so the daypart a programme comes from is the one
//! outside the cab when the clip before it ended. Tuning in drops the
//! driver into whatever is on, part way through, like the other stations;
//! while tuned, each new clip plays as the schedule reaches it.
//!
//! The clips come from `channel3000.pak`, opened the first time one is
//! played. A build without that pack keeps the station off the dial
//! altogether rather than tuning to dead air.
//!
//! Its own file because `radio` is already past the 1000-line limit.

use ff_core::assets_pack::channel3000_pack_available;
use ff_core::channel3000::{clip_asset_key, default_manifest, Schedule, CHANNEL_3000_ID};
use ff_core::radio::{default_radio_catalog, RadioStation};

use crate::app::GameContext;
use crate::states::driving::DrivingState;

/// The schedule this drive's Channel 3000 runs, signed on `airtime_s`
/// before the drive began (the head start every station gets) at the
/// drive's starting local hour. `None` when this build has no manifest.
pub fn channel3000_for_drive(trip_seed: i64, local_hour: f64, airtime_s: f64) -> Option<Schedule> {
    let manifest = default_manifest()?;
    let mut schedule = Schedule::new(manifest, &format!("{trip_seed}|{CHANNEL_3000_ID}"));
    schedule.advance(airtime_s, local_hour);
    Some(schedule)
}

/// Whether Channel 3000 can be heard in this build: a schedule and a pack.
pub fn channel3000_playable(schedule: Option<&Schedule>) -> bool {
    schedule.is_some() && channel3000_pack_available()
}

impl DrivingState {
    pub fn is_channel3000(station: &RadioStation) -> bool {
        station.id == CHANNEL_3000_ID
    }

    /// Put Channel 3000 on the dial, or take it off. The drive does this
    /// once at the start from what the build carries; a test does it to
    /// stand in for the pack. Never on without a schedule to play.
    pub fn set_channel3000_on_dial(&mut self, on: bool) {
        let on = on && self.channel3000.is_some();
        let listed = self.radio.catalog.iter().any(Self::is_channel3000);
        if on && !listed {
            if let Some(row) = default_radio_catalog()
                .iter()
                .find(|s| Self::is_channel3000(s))
            {
                let mut catalog = self.radio.catalog.clone();
                catalog.push(row.clone());
                self.radio.set_catalog(catalog);
            }
        } else if !on && listed {
            let catalog = self
                .radio
                .catalog
                .iter()
                .filter(|s| !Self::is_channel3000(s))
                .cloned()
                .collect();
            self.radio.set_catalog(catalog);
        }
    }

    /// Channel 3000's share of the airtime clock: `dt` real seconds at the
    /// truck's local hour now.
    pub fn advance_channel3000(&mut self, dt: f64) {
        let hour = self.trip.local_hour();
        if let Some(schedule) = self.channel3000.as_mut() {
            schedule.advance(dt, hour);
        }
    }

    /// Tune in: the clip on the air, from as far into it as the station has
    /// got. Every clip on this station is a programme or a short piece of
    /// its own glue, and a real dial lands mid-sentence on a TV channel as
    /// on anything else, so unlike a music station's spoken breaks nothing
    /// here is held back to play from the top.
    pub fn start_channel3000(&mut self, ctx: &mut GameContext, fade_ms: u32) {
        self.radio_station_id = CHANNEL_3000_ID.to_string();
        self.radio_playlist = Vec::new();
        self.radio_playing_key.clear();
        self.radio_break_queue = Vec::new();
        let hour = self.trip.local_hour();
        let Some(schedule) = self.channel3000.as_mut() else {
            return;
        };
        schedule.start(hour);
        let Some(clip) = schedule.on_air() else {
            return;
        };
        self.channel3000_serial = schedule.serial();
        self.radio_playing_key = clip_asset_key(&clip.key);
        ctx.audio
            .play_music_at(&self.radio_playing_key, fade_ms, schedule.elapsed_s());
    }

    /// While tuned: start each new clip as the schedule reaches it. The
    /// schedule itself has already advanced this frame.
    pub fn update_channel3000_playback(&mut self, ctx: &mut GameContext) {
        if self.radio_station_id != CHANNEL_3000_ID {
            self.start_channel3000(ctx, 2500);
            return;
        }
        let Some(schedule) = self.channel3000.as_ref() else {
            return;
        };
        if schedule.serial() == self.channel3000_serial {
            return;
        }
        let Some(clip) = schedule.on_air() else {
            return;
        };
        self.channel3000_serial = schedule.serial();
        self.radio_playing_key = clip_asset_key(&clip.key);
        ctx.audio
            .play_music_at(&self.radio_playing_key, 300, schedule.elapsed_s());
    }

    /// Shift+Y on Channel 3000: the title of what is on, from the schedule.
    /// `None` when `station` is not Channel 3000.
    pub fn channel3000_now_playing(&mut self, station: &RadioStation) -> Option<String> {
        if !Self::is_channel3000(station) {
            return None;
        }
        let hour = self.trip.local_hour();
        let schedule = self.channel3000.as_mut()?;
        schedule.start(hour);
        let title = schedule.on_air()?.title.trim();
        let name = station.display_name();
        // The station's own glue is titled with the station's name: saying
        // it twice in one line tells the driver nothing more.
        if title.is_empty() || title == name {
            return Some(format!("Now playing on {name}."));
        }
        // "Weigh In!" and "Are You Afraid of the Data?" end their own
        // sentences; the rest get a full stop.
        let stop = if title.ends_with(['.', '!', '?']) {
            ""
        } else {
            "."
        };
        Some(format!("Now playing on {name}: {title}{stop}"))
    }
}
