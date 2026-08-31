//! What each settings row does when stepped: the toggles and cycles of
//! `SettingsCategoryState` in `main_menu.py`, plus the spoken value labels
//! the rows read.

use ff_core::pyfmt::{py_str_float, round_py_n};
use ff_core::settings::{
    acc_gap_seconds, Settings, ACC_GAP_CHOICES, ACC_GAP_DEFAULT, DRIVING_ASSIST_FIELDS,
    DRIVING_ASSIST_PRESETS, LANE_KEEPING_MODES, PLACE_CALLOUT_MODES, TIME_SCALES,
};
use ff_core::sim::hos::clock_text;
use ff_core::sim::season::{date_text, real_clock_game_hours};
use ff_core::speech_pacing::DRIVING_SPEECH_MODES;

use super::settings::{save_settings, SettingsCategoryState};
use super::settings_items::assist_flag;
use crate::app::{version, GameContext, Say};
use crate::audio::VolumeUpdate;
use crate::updater;

/// Python `f"{x:g}"` for the values these rows read (whole numbers bare,
/// otherwise the shortest round-trip digits).
fn fmt_g(x: f64) -> String {
    if x.fract() == 0.0 && x.abs() < 1e16 {
        format!("{}", x as i64)
    } else {
        py_str_float(x)
    }
}

/// `str.title()` for a one-word mode name.
fn title_case(word: &str) -> String {
    let mut chars = word.chars();
    match chars.next() {
        Some(first) => first.to_uppercase().collect::<String>() + &chars.as_str().to_lowercase(),
        None => String::new(),
    }
}

/// Step through `options` from `current` by `d`, wrapping; an unknown current
/// value starts from `fallback_index`.
fn cycle_index(options: &[&str], current: &str, d: i64, fallback_index: usize) -> usize {
    let i = options
        .iter()
        .position(|o| *o == current)
        .unwrap_or(fallback_index) as i64;
    (i + d).rem_euclid(options.len() as i64) as usize
}

pub(super) fn assist_preset_label(s: &Settings) -> &'static str {
    match s.driving_assistance_preset.as_str() {
        "realistic" => "Realistic",
        "balanced" => "Balanced",
        "all" => "All assists",
        _ => "Custom",
    }
}

pub(super) fn descent_level_label(s: &Settings) -> String {
    title_case(&s.descent_speed_control)
}

pub(super) fn pace_label(s: &Settings) -> String {
    let scale = s.time_scale;
    if scale == 10.0 {
        "relaxed".to_string()
    } else if scale == 20.0 {
        "standard".to_string()
    } else if scale == 1.0 {
        "real time".to_string()
    } else {
        format!("{} times", fmt_g(scale))
    }
}

pub(super) fn hos_label(s: &Settings) -> &'static str {
    match s.hos_mode.as_str() {
        "relaxed" => "relaxed",
        "debug_off" => "off (developer)",
        _ => "realistic",
    }
}

/// The choice, and the number that makes it mean something.
///
/// A sighted player could infer "close" from a picture of a road. This
/// one is read aloud and nothing else on the row says how much room any
/// of the words buys, so the seconds go in the label rather than being
/// left to the help text.
pub(super) fn acc_gap_label(s: &Settings) -> String {
    let choice = &s.acc_following_gap;
    let seconds = acc_gap_seconds(choice)
        .or_else(|| acc_gap_seconds(ACC_GAP_DEFAULT))
        .unwrap_or(3.0);
    let spoken = fmt_g(seconds).replace(".5", " and a half");
    format!("{choice}, {spoken} seconds")
}

/// The value carries its own meaning: a player cycling the row hears
/// what changes hands, not a bare difficulty word (owner ask
/// 2026-07-27). It has to, because "off" here means the hardest mode
/// while "off" on the rows around it means less help. The labels and
/// the loader's fallback share one source in settings.
pub(super) fn lane_keeping_label(s: &Settings) -> &'static str {
    s.lane_keeping_label()
}

/// The spoken value, in the words a volume row uses.
///
/// The saved values are unchanged -- "subtle", "standard", "prominent" --
/// so nobody's choice resets. What changes is that the row now says
/// quieter or louder, which is what a player is actually choosing
/// between. "Prominence" described the row to whoever wrote it, not to
/// whoever hears it.
pub(super) fn cue_loudness_label(s: &Settings) -> &'static str {
    match s.lane_cue_loudness.as_str() {
        "subtle" => "quieter",
        "prominent" => "louder",
        _ => "standard",
    }
}

pub(super) fn event_voice_label(s: &Settings) -> String {
    if !s.sapi_events {
        return "main voice".to_string();
    }
    match s.event_backend.as_str() {
        "OneCore" => "Windows OneCore".to_string(),
        other => other.to_string(),
    }
}

/// `_channel`: the effective update channel.
pub(super) fn update_channel(s: &Settings) -> String {
    updater::resolve_channel(
        &s.update_channel,
        updater::load_build_info(version()).as_ref(),
    )
}

impl SettingsCategoryState {
    pub(super) fn cycle_assist_preset(&mut self, ctx: &mut GameContext, direction: i64) {
        let presets: Vec<&str> = DRIVING_ASSIST_PRESETS
            .iter()
            .map(|(name, _)| *name)
            .collect();
        let current = ctx.settings.driving_assistance_preset.clone();
        let index = presets
            .iter()
            .position(|p| *p == current)
            .map(|i| i as i64)
            .unwrap_or(if direction > 0 { -1 } else { 0 });
        let lane_before = ctx.settings.lane_keeping.clone();
        let next = (index + direction).rem_euclid(presets.len() as i64) as usize;
        ctx.settings.apply_driving_assistance_preset(presets[next]);
        self.announce(ctx);
        if ctx.settings.lane_keeping != lane_before {
            let note = if ctx.settings.lane_is_automated() {
                "Lane keeping full: the truck holds the lane, tap Left or Right to change lanes."
                    .to_string()
            } else {
                format!(
                    "Lane keeping back to {}.",
                    lane_keeping_label(&ctx.settings)
                )
            };
            ctx.say_with(note, Say::queued());
        }
    }

    pub(super) fn toggle_driving_assist(
        &mut self,
        ctx: &mut GameContext,
        field: &str,
        direction: i64,
    ) {
        if field == "pedal_latch" {
            let modes = ["on", "off"];
            let i = cycle_index(&modes, &ctx.settings.pedal_latch, direction, 0);
            ctx.settings.pedal_latch = modes[i].to_string();
            self.announce(ctx);
            return;
        }
        if matches!(
            field,
            "curve_callouts" | "destination_approach_assist" | "predictive_cruise" | "speed_keeper"
        ) {
            // Input-accessibility aids and information layers, not realism
            // choices: they live outside the presets, so toggling one never
            // reads as Custom.
            let s = &mut ctx.settings;
            match field {
                "curve_callouts" => s.curve_callouts = !s.curve_callouts,
                "destination_approach_assist" => {
                    s.destination_approach_assist = !s.destination_approach_assist
                }
                "predictive_cruise" => s.predictive_cruise = !s.predictive_cruise,
                _ => s.speed_keeper = !s.speed_keeper,
            }
            self.announce(ctx);
            return;
        }
        if !DRIVING_ASSIST_FIELDS.contains(&field) {
            return;
        }
        let was_custom = ctx.settings.driving_assistance_preset == "custom";
        if field == "descent_speed_control" {
            let levels = ["off", "realistic", "balanced", "interactive"];
            let i = cycle_index(&levels, &ctx.settings.descent_speed_control, direction, 0);
            ctx.settings.descent_speed_control = levels[i].to_string();
        } else {
            let flipped = !assist_flag(&ctx.settings, field);
            ctx.settings
                .set_assist_value(field, ff_core::settings::AssistValue::Flag(flipped));
        }
        ctx.settings.refresh_driving_assistance_preset();
        self.announce(ctx);
        // Queue the preset note behind the toggle announcement (an interrupting
        // say here would cut off the new on/off state the player just changed),
        // and only on the change into Custom -- repeating it on every later
        // toggle is noise the preset row already answers.
        if ctx.settings.driving_assistance_preset == "custom" && !was_custom {
            ctx.say_with("Driving assistance preset: Custom.", Say::queued());
        }
    }

    pub(super) fn cycle_acc_gap(&mut self, ctx: &mut GameContext, d: i64) {
        let order: Vec<&str> = ACC_GAP_CHOICES.iter().map(|(name, _)| *name).collect();
        let fallback = order
            .iter()
            .position(|o| *o == ACC_GAP_DEFAULT)
            .unwrap_or(0);
        let i = cycle_index(&order, &ctx.settings.acc_following_gap, d, fallback);
        ctx.settings.acc_following_gap = order[i].to_string();
        self.announce(ctx);
    }

    pub(super) fn toggle_units(&mut self, ctx: &mut GameContext, _d: i64) {
        ctx.settings.imperial_units = !ctx.settings.imperial_units;
        self.announce(ctx);
    }

    pub(super) fn toggle_transmission(&mut self, ctx: &mut GameContext, _d: i64) {
        ctx.settings.automatic_transmission = !ctx.settings.automatic_transmission;
        self.announce(ctx);
    }

    pub(super) fn cycle_automatic_direction_changes(&mut self, ctx: &mut GameContext, d: i64) {
        let modes = ["simple", "deliberate"];
        let i = cycle_index(&modes, &ctx.settings.automatic_direction_changes, d, 0);
        ctx.settings.automatic_direction_changes = modes[i].to_string();
        self.announce(ctx);
    }

    pub(super) fn cycle_pace(&mut self, ctx: &mut GameContext, d: i64) {
        let previous = ctx.settings.time_scale;
        let i = TIME_SCALES
            .iter()
            .position(|s| *s == ctx.settings.time_scale)
            .unwrap_or(1) as i64;
        let next = (i + d).rem_euclid(TIME_SCALES.len() as i64) as usize;
        ctx.settings.time_scale = TIME_SCALES[next];
        let mut aligned_clock = None;
        if ctx.settings.time_scale == 1.0 && previous != 1.0 {
            if let Some(profile) = ctx.profile.as_mut() {
                if profile.has_started_career() {
                    profile.sync_calendar_to(real_clock_game_hours(None));
                    aligned_clock = Some(profile.calendar_game_hours());
                    if let Err(e) = profile.save() {
                        log::error!("Could not save the profile: {e}");
                    }
                }
            }
        }
        self.announce(ctx);
        if let Some(hours) = aligned_clock {
            ctx.say_with(
                format!(
                    "Clock aligned to {}, {}.",
                    date_text(hours),
                    clock_text(hours)
                ),
                Say::queued(),
            );
        }
    }

    fn level_field<'a>(s: &'a mut Settings, attr: &str) -> Option<&'a mut f64> {
        Some(match attr {
            "master_volume" => &mut s.master_volume,
            "sfx_volume" => &mut s.sfx_volume,
            "music_volume" => &mut s.music_volume,
            "radio_volume" => &mut s.radio_volume,
            "weather_volume" => &mut s.weather_volume,
            "engine_volume" => &mut s.engine_volume,
            "ui_volume" => &mut s.ui_volume,
            "speech_rate" => &mut s.speech_rate,
            "speech_pitch" => &mut s.speech_pitch,
            "speech_volume" => &mut s.speech_volume,
            _ => return None,
        })
    }

    /// `max(0.0, min(1.0, round(value + delta, 2)))` onto a level field.
    fn step_level(s: &mut Settings, attr: &str, delta: f64) {
        if let Some(value) = Self::level_field(s, attr) {
            *value = round_py_n(*value + delta, 2).clamp(0.0, 1.0);
        }
    }

    pub(super) fn volume(&mut self, ctx: &mut GameContext, attr: &str, delta: f64) {
        Self::step_level(&mut ctx.settings, attr, delta);
        save_settings(&ctx.settings);
        self.apply_audio_volumes(ctx);
        self.announce(ctx);
    }

    fn apply_audio_volumes(&mut self, ctx: &mut GameContext) {
        ctx.apply_volumes();
        if ctx.driving_radio_active() {
            let radio = ctx.settings.radio_volume;
            ctx.audio.set_volumes(&VolumeUpdate::default().music(radio));
        }
    }

    pub(super) fn cycle_hos(&mut self, ctx: &mut GameContext, d: i64) {
        let modes = ["realistic", "relaxed"];
        let i = cycle_index(&modes, &ctx.settings.hos_mode, d, 0);
        ctx.settings.hos_mode = modes[i].to_string();
        self.announce(ctx);
    }

    pub(super) fn toggle_lane_guide_tone(&mut self, ctx: &mut GameContext, _d: i64) {
        ctx.settings.lane_guide_tone = !ctx.settings.lane_guide_tone;
        save_settings(&ctx.settings);
        self.announce(ctx);
    }

    pub(super) fn cycle_cue_loudness(&mut self, ctx: &mut GameContext, d: i64) {
        let levels = ["subtle", "standard", "prominent"];
        let i = cycle_index(&levels, &ctx.settings.lane_cue_loudness, d, 1);
        ctx.settings.lane_cue_loudness = levels[i].to_string();
        self.announce(ctx);
    }

    pub(super) fn cycle_lane_keeping(&mut self, ctx: &mut GameContext, d: i64) {
        let i = cycle_index(&LANE_KEEPING_MODES, &ctx.settings.lane_keeping, d, 0);
        ctx.settings.lane_keeping = LANE_KEEPING_MODES[i].to_string();
        // Lane keeping is a preset field, so a hand-picked value is answered
        // by the preset row the same way any other assist is.
        ctx.settings.refresh_driving_assistance_preset();
        self.announce(ctx);
    }

    /// Flip between the recorded engine and the classic loop, live.
    pub(super) fn toggle_engine_voice(&mut self, ctx: &mut GameContext, _d: i64) {
        let s = &mut ctx.settings;
        s.engine_voice = if s.engine_voice == "real" {
            "classic".to_string()
        } else {
            "real".to_string()
        };
        ctx.apply_volumes(); // re-voices a running engine in place
        self.announce(ctx);
    }

    /// Flip between the recorded jake and the classic synth, live.
    pub(super) fn toggle_jake_voice(&mut self, ctx: &mut GameContext, _d: i64) {
        let s = &mut ctx.settings;
        s.jake_voice = if s.jake_voice == "real" {
            "classic".to_string()
        } else {
            "real".to_string()
        };
        ctx.apply_volumes(); // re-voices a sounding jake growl in place
        self.announce(ctx);
    }

    pub(super) fn toggle_radio_streamer_safe(&mut self, ctx: &mut GameContext, _d: i64) {
        ctx.settings.radio_streamer_safe = !ctx.settings.radio_streamer_safe;
        ctx.apply_active_radio_settings();
        self.announce(ctx);
    }

    pub(super) fn toggle_duck_for_speech(&mut self, ctx: &mut GameContext, _d: i64) {
        ctx.settings.duck_audio_for_speech = !ctx.settings.duck_audio_for_speech;
        save_settings(&ctx.settings);
        if !ctx.settings.duck_audio_for_speech {
            // A duck held at the moment of the flip must not stick.
            ctx.audio.set_speech_duck(1.0);
        }
        self.announce(ctx);
    }

    pub(super) fn toggle_controller(&mut self, ctx: &mut GameContext, _d: i64) {
        ctx.settings.controller_enabled = !ctx.settings.controller_enabled;
        ctx.apply_controller();
        self.announce(ctx);
    }

    pub(super) fn toggle_haptics(&mut self, ctx: &mut GameContext, _d: i64) {
        ctx.settings.haptics_enabled = !ctx.settings.haptics_enabled;
        ctx.apply_haptics();
        self.announce(ctx);
    }

    pub(super) fn cycle_driving_speech(&mut self, ctx: &mut GameContext, d: i64) {
        let i = cycle_index(&DRIVING_SPEECH_MODES, &ctx.settings.driving_speech, d, 0);
        ctx.settings.driving_speech = DRIVING_SPEECH_MODES[i].to_string();
        self.announce(ctx);
    }

    pub(super) fn cycle_place_callouts(&mut self, ctx: &mut GameContext, d: i64) {
        let i = cycle_index(&PLACE_CALLOUT_MODES, &ctx.settings.place_callouts, d, 0);
        ctx.settings.place_callouts = PLACE_CALLOUT_MODES[i].to_string();
        self.announce(ctx);
    }

    pub(super) fn set_all_chatter(&mut self, ctx: &mut GameContext, d: i64) {
        // The master switch is directional like every other Left/Right
        // control: Right (or Enter) turns every chatter kind on, Left turns
        // every kind off.
        ctx.settings.set_all_chatter(d >= 0);
        self.announce(ctx);
    }

    pub(super) fn toggle_chatter(&mut self, ctx: &mut GameContext, field: &str) {
        let current = ctx.settings.chatter_field(field).unwrap_or(true);
        ctx.settings.set_chatter_field(field, !current);
        self.announce(ctx);
    }

    pub(super) fn toggle_menu_position(&mut self, ctx: &mut GameContext, _d: i64) {
        ctx.settings.announce_menu_position = !ctx.settings.announce_menu_position;
        self.announce(ctx);
    }

    pub(super) fn cycle_event_voice(&mut self, ctx: &mut GameContext, d: i64) {
        // None = the main voice; the rest are the available separate voices.
        let mut options: Vec<Option<String>> = vec![None];
        options.extend(ctx.speech.event_backend_options().into_iter().map(Some));
        let current = if ctx.settings.sapi_events {
            Some(ctx.settings.event_backend.clone())
        } else {
            None
        };
        let i = options.iter().position(|o| *o == current).unwrap_or(0) as i64;
        let choice = options[(i + d).rem_euclid(options.len() as i64) as usize].clone();
        match choice {
            None => ctx.settings.sapi_events = false,
            Some(backend) => {
                ctx.settings.sapi_events = true;
                ctx.settings.event_backend = backend;
            }
        }
        save_settings(&ctx.settings);
        ctx.apply_speech();
        self.announce(ctx);
    }

    pub(super) fn adjust_speech(&mut self, ctx: &mut GameContext, attr: &str, delta: f64) {
        Self::step_level(&mut ctx.settings, attr, delta);
        save_settings(&ctx.settings);
        ctx.apply_speech();
        self.announce_speech_preview(ctx, attr);
    }

    pub(super) fn cycle_voice(&mut self, ctx: &mut GameContext, d: i64) {
        let voices = ctx.speech.voice_names();
        if voices.is_empty() {
            return;
        }
        let current = ctx.settings.speech_voice.clone();
        let i = match voices.iter().position(|v| *v == current) {
            Some(i) => (i as i64 + d).rem_euclid(voices.len() as i64) as usize,
            None if d >= 0 => 0,
            None => voices.len() - 1,
        };
        ctx.settings.speech_voice = voices[i].clone();
        save_settings(&ctx.settings);
        ctx.apply_speech();
        self.announce_speech_preview(ctx, "speech_voice");
    }

    pub(super) fn toggle_real_weather(&mut self, ctx: &mut GameContext, _d: i64) {
        ctx.settings.real_weather = !ctx.settings.real_weather;
        save_settings(&ctx.settings);
        self.announce(ctx);
    }

    pub(super) fn toggle_real_traffic(&mut self, ctx: &mut GameContext, _d: i64) {
        ctx.settings.real_traffic = !ctx.settings.real_traffic;
        save_settings(&ctx.settings);
        self.announce(ctx);
    }

    pub(super) fn toggle_real_parking(&mut self, ctx: &mut GameContext, _d: i64) {
        ctx.settings.real_parking = !ctx.settings.real_parking;
        save_settings(&ctx.settings);
        self.announce(ctx);
    }

    pub(super) fn toggle_live_weather_calendar(&mut self, ctx: &mut GameContext, _d: i64) {
        let turning_off = ctx.settings.live_weather_controls_calendar;
        ctx.settings.live_weather_controls_calendar = !ctx.settings.live_weather_controls_calendar;
        if turning_off {
            if let Some(profile) = ctx.profile.as_mut() {
                if profile.has_started_career() {
                    profile.anchor_calendar_to(real_clock_game_hours(None));
                    if let Err(e) = profile.save() {
                        log::error!("Could not save the profile: {e}");
                    }
                }
            }
        }
        self.announce(ctx);
    }

    pub(super) fn toggle_update_channel(&mut self, ctx: &mut GameContext, _d: i64) {
        ctx.settings.update_channel = if update_channel(&ctx.settings) == "dev" {
            "stable".to_string()
        } else {
            "dev".to_string()
        };
        self.announce(ctx);
    }
}
