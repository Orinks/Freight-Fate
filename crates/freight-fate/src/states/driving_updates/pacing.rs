//! The clock's pacing on the road: a pace change made mid-drive, the bound
//! on the merge handoff's real-time clock, and the session-log trace of
//! every real-time pin (issue 293).
//!
//! A tester drove a relaxed haul for three hours on the wall clock: the slow
//! merge out of the pickup yard pinned the clock to real time and only let
//! go at merge speed, which a driver settling below it never reached. The
//! pace change they tried was deferred until the truck stopped, silently,
//! and the log said nothing about any of it.

use ff_core::sim::driving_modes::mode_name;
use ff_core::sim::season::real_clock_game_hours;
use ff_core::sim::trip_models::{
    merge_traffic_target_mph, MERGE_RECOVERY_MAX_MI, MERGE_RECOVERY_MAX_REAL_S, PACE_CHANGE_MAX_MPH,
};
use ff_core::speech_pacing::SpeechCategory;
use ff_core::speech_text::SpokenMessage;

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

/// Said once per request when a Driving mode change made from the pause menu
/// has to wait for the truck to stop (`PACE_CHANGE_MAX_MPH`). "Driving mode"
/// is the row's own name (docs/ontology.md), never "pace" or "pacing".
pub const PACE_CHANGE_DEFERRED_TEXT: &str =
    "Driving mode change saved. It takes effect when you stop.";
/// The same line on the terse rungs.
pub const PACE_CHANGE_DEFERRED_TERSE: &str = "Driving mode changes when you stop.";

/// A real-time pin is written to the log once it has held this long, so a
/// condition that flickers for a frame or two (a curve assist crossing its
/// own number) is not a log line per frame.
pub const CLOCK_OVERRIDE_LOG_HOLD_S: f64 = 2.0;
/// A pin still on after this long is logged once as a warning: no
/// legitimate one (a light, a police stop, a dock run-in) lasts ten minutes
/// of real driving, so the line marks the next stuck clock straight away.
pub const CLOCK_OVERRIDE_LONG_S: f64 = 600.0;

/// The drive's pacing bookkeeping, kept together so the frame loop can ask
/// one place what the clock is doing and why.
#[derive(Debug, Default, Clone)]
pub struct ClockPacing {
    /// The pacing the driver asked for that is waiting for the truck to
    /// stop, once its cue has been said, with the real seconds it has waited.
    pub deferred_pace: Option<(f64, f64)>,
    /// Real seconds since the taper of a slow merge.
    pub merge_recovery_s: f64,
    /// Miles covered since the taper of a slow merge.
    pub merge_recovery_mi: f64,
    /// The real-time pin in force, by name.
    pub override_reason: Option<String>,
    /// Real seconds the pin above has held.
    pub override_held_s: f64,
    /// Odometer where the pin above began.
    pub override_start_odometer_mi: f64,
    /// Whether its start has been written to the log.
    pub override_logged: bool,
    /// Whether its long-hold warning has been written to the log.
    pub override_warned: bool,
}

impl ClockPacing {
    pub fn reset_merge_recovery(&mut self) {
        self.merge_recovery_s = 0.0;
        self.merge_recovery_mi = 0.0;
    }
}

/// `10 (relaxed)`: a pacing as the log writes it.
pub fn pace_text(scale: f64) -> String {
    format!("{scale} ({})", mode_name(scale))
}

impl DrivingState {
    /// Pacing can be changed from the pause menu mid-trip, and takes effect
    /// once the truck is stopped (`PACE_CHANGE_MAX_MPH`). Entering Real time
    /// also moves the independent spoken clock to now, while the career,
    /// deadline, and HOS clocks keep their elapsed totals.
    ///
    /// A request made while moving is said once, so the driver knows the
    /// key worked and why the clock has not changed yet; a second, different
    /// request is a new request and is said again.
    pub fn update_pace_change(&mut self, ctx: &mut GameContext, dt: f64) {
        let requested = ctx.settings.time_scale;
        if requested == self.trip.time_scale {
            if let Some((withdrawn, _)) = self.clock_pacing.deferred_pace.take() {
                log::info!(
                    "pace change withdrawn: {} no longer requested, trip stays {}",
                    pace_text(withdrawn),
                    pace_text(self.trip.time_scale),
                );
            }
            return;
        }
        let speed = self.trip.truck.speed_mph().abs();
        if speed >= PACE_CHANGE_MAX_MPH {
            match self.clock_pacing.deferred_pace.as_mut() {
                Some((pending, waited)) if *pending == requested => *waited += dt,
                _ => {
                    log::info!(
                        "pace change requested: trip {} -> {} at {:.1} mph, mile {:.2}; \
                         deferred until the truck stops",
                        pace_text(self.trip.time_scale),
                        pace_text(requested),
                        speed,
                        self.trip.position_mi,
                    );
                    self.clock_pacing.deferred_pace = Some((requested, 0.0));
                    ctx.say_event_with(
                        SpokenMessage::with_terse(
                            PACE_CHANGE_DEFERRED_TEXT,
                            PACE_CHANGE_DEFERRED_TERSE,
                        ),
                        SayEvent::queued().category(SpeechCategory::Confirmation),
                    );
                }
            }
            return;
        }
        let deferred = self.clock_pacing.deferred_pace.take();
        if deferred.is_none() {
            log::info!(
                "pace change requested: trip {} -> {} at {:.1} mph, mile {:.2}",
                pace_text(self.trip.time_scale),
                pace_text(requested),
                speed,
                self.trip.position_mi,
            );
        }
        if requested == 1.0 {
            let elapsed_h = self.trip.game_minutes / 60.0;
            let real_hours = real_clock_game_hours(None);
            profile_mut_of(ctx).sync_calendar_to(real_hours - elapsed_h);
            ctx.save_profile();
            let local_hour = real_hours.rem_euclid(24.0);
            let reference_now = local_hour - self.trip.current_timezone().offset_h;
            let start_hour = (reference_now - elapsed_h).rem_euclid(24.0);
            self.trip.start_hour = start_hour;
            self.trip.traffic_manager.start_hour = start_hour;
            if self.trip.weather.game_hours.is_some() {
                self.trip.weather.game_hours =
                    Some(profile_of(ctx).calendar_game_hours() + elapsed_h);
            }
        }
        let waited = deferred
            .map(|(_, waited)| format!(" after waiting {waited:.0} s for the stop"))
            .unwrap_or_default();
        log::info!(
            "pace change applied: trip {} -> {} at mile {:.2}{waited}",
            pace_text(self.trip.time_scale),
            pace_text(requested),
            self.trip.position_mi,
        );
        self.trip.time_scale = requested;
    }

    /// The slow-merge handoff's start: the truck reached the taper of the
    /// acceleration lane at `speed`, under the `limit` traffic is running.
    pub fn start_departure_merge_recovery(&mut self, speed: f64, limit: f64) {
        self.departure_merge_recovery = true;
        self.clock_pacing.reset_merge_recovery();
        log::info!(
            "departure merge recovery started: taper at {speed:.0} mph, road {limit:.0}, \
             merge speed {:.0}; real time for at most {MERGE_RECOVERY_MAX_REAL_S:.0} s \
             or {MERGE_RECOVERY_MAX_MI} mi",
            merge_traffic_target_mph(limit),
        );
    }

    /// The slow-merge handoff's end, with why.
    pub fn end_departure_merge_recovery(&mut self, why: &str) {
        if !self.departure_merge_recovery {
            return;
        }
        self.departure_merge_recovery = false;
        log::info!(
            "departure merge recovery ended: {why} after {:.0} s and {:.2} mi, at {:.0} mph",
            self.clock_pacing.merge_recovery_s,
            self.clock_pacing.merge_recovery_mi,
            self.trip.truck.speed_mph(),
        );
        self.clock_pacing.reset_merge_recovery();
        // The pin itself is decided by the exit watch, which has run this
        // frame already; let go of it now rather than a frame late.
        self.trip.controlled_ramp = self.controlled_ramp_reason().is_some();
    }

    /// Per frame, after the acceleration lane's own watch: the merge
    /// handoff holds the clock at real time only while the truck is still
    /// merging. It lets go at merge speed (`update_departure_ramp`), and
    /// also -- whatever the driver does -- once the join is over by time or
    /// by road (`MERGE_RECOVERY_MAX_REAL_S`, `MERGE_RECOVERY_MAX_MI`), or
    /// the truck has left the road it joined. Before the bound, a driver
    /// who settled below merge speed kept the whole haul on the wall clock.
    pub fn bound_departure_merge_recovery(&mut self, moved_mi: f64, dt: f64) {
        if !self.departure_merge_recovery || self.departure_ramp_mi.is_some() {
            return;
        }
        self.clock_pacing.merge_recovery_s += dt.max(0.0);
        self.clock_pacing.merge_recovery_mi += moved_mi.max(0.0);
        let why = if self.trip.finished {
            Some("trip finished")
        } else if self.ramp_mi.is_some()
            || self.stop_chain.is_some()
            || self.surface_chain
            || self.departure_chain
        {
            Some("left the highway")
        } else if self.clock_pacing.merge_recovery_mi >= MERGE_RECOVERY_MAX_MI {
            Some("distance bound")
        } else if self.clock_pacing.merge_recovery_s >= MERGE_RECOVERY_MAX_REAL_S {
            Some("time bound")
        } else {
            None
        };
        if let Some(why) = why {
            self.end_departure_merge_recovery(why);
        }
    }

    /// The real-time pin in force, by name: the trip's own reason, with the
    /// ramp law the driving state set it for.
    pub fn clock_override_reason(&self) -> Option<String> {
        let reason = self.trip.real_time_override()?;
        if reason == "controlled ramp" {
            if let Some(ramp) = self.controlled_ramp_reason() {
                return Some(format!("{reason}: {ramp}"));
            }
        }
        Some(reason.to_string())
    }

    /// Per frame: write the clock's real-time pins to the session log, the
    /// start and the end of each with its name, never a line per frame. Only
    /// a compressed pacing has anything to pin; at real time there is none.
    pub fn trace_clock_override(&mut self, dt: f64) {
        let reason = if self.trip.time_scale > 1.0 {
            self.clock_override_reason()
        } else {
            None
        };
        let odometer = self.trip.truck.odometer_mi;
        if reason != self.clock_pacing.override_reason {
            let pacing = &self.clock_pacing;
            if let (Some(old), true) = (&pacing.override_reason, pacing.override_logged) {
                log::info!(
                    "clock override ended: {old} after {:.0} s and {:.2} mi, back to pacing {}",
                    pacing.override_held_s,
                    odometer - pacing.override_start_odometer_mi,
                    pace_text(self.trip.time_scale),
                );
            }
            let pacing = &mut self.clock_pacing;
            pacing.override_reason = reason;
            pacing.override_held_s = 0.0;
            pacing.override_start_odometer_mi = odometer;
            pacing.override_logged = false;
            pacing.override_warned = false;
        }
        let Some(name) = self.clock_pacing.override_reason.clone() else {
            return;
        };
        self.clock_pacing.override_held_s += dt.max(0.0);
        let held = self.clock_pacing.override_held_s;
        if !self.clock_pacing.override_logged && held >= CLOCK_OVERRIDE_LOG_HOLD_S {
            self.clock_pacing.override_logged = true;
            log::info!(
                "clock override started: {name}, real time instead of pacing {} at mile {:.2}, \
                 {:.0} mph",
                pace_text(self.trip.time_scale),
                self.trip.position_mi,
                self.trip.truck.speed_mph(),
            );
        }
        if !self.clock_pacing.override_warned && held >= CLOCK_OVERRIDE_LONG_S {
            self.clock_pacing.override_warned = true;
            log::warn!(
                "clock override still on after {held:.0} s: {name}, at mile {:.2}, {:.0} mph",
                self.trip.position_mi,
                self.trip.truck.speed_mph(),
            );
        }
    }

    /// The pacing at the start of a drive, written to the session log once:
    /// what Settings says and what this trip is running, which differ only
    /// when a pace change is still waiting.
    pub fn log_pace_configuration(&self, ctx: &GameContext) {
        log::info!(
            "drive pace: settings time scale {}, trip time scale {}, effective {:.2}{}",
            pace_text(ctx.settings.time_scale),
            pace_text(self.trip.time_scale),
            self.trip.effective_time_scale(),
            if self.resumed { ", resumed" } else { "" },
        );
    }
}
