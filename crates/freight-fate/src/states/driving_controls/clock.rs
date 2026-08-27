//! The clock key and the three Alt hours keys, plus the shoulder-sleep
//! question the pause menu and the rest key both ask.
//!
//! Alt A, Alt S, and Alt D split the three hours numbers a driver plans around
//! out of the C readout, one key each, left to right in the shape of a shift:
//! what is behind you, what stops you next, what ends the day. The Alt chord
//! keeps the right hand on the arrows, where the accelerator is, and a slipped
//! modifier lands on A, S, or D -- all spoken info, nothing that moves the
//! truck. Controllers keep the combined readout on D-pad right; a pad has
//! nowhere to put three more info buttons.

use ff_core::sim::trip_models::RoadStop;

use crate::app::GameContext;
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

impl DrivingState {
    /// `_calendar_phrase()`: calendar date and season for the spoken
    /// readouts; "" when unknown.
    pub fn calendar_phrase(&self, _ctx: &GameContext) -> String {
        let Some(date) = self.trip.weather.date_text() else {
            return String::new();
        };
        match self.trip.weather.season() {
            Some(season) => format!("{date}, {season}"),
            None => date,
        }
    }

    /// `_clock_phrase()`: "5:33 AM Eastern, March 21, spring." -- the time
    /// plus the calendar.
    pub fn clock_phrase(&self, ctx: &GameContext) -> String {
        let cal = self.calendar_phrase(ctx);
        let base = format!(
            "{} {}",
            clock_text(self.trip.local_hour()),
            self.trip.current_timezone().name
        );
        if cal.is_empty() {
            format!("{base}.")
        } else {
            format!("{base}, {cal}.")
        }
    }

    /// `_speak_clock(full_hours=False)`: C -- local time, then the delivery deadline
    /// verdict, then the nearest hours limit.
    ///
    /// Ordered for braille as much as speech: a display shows one short line
    /// at a time, so the clock and the on-schedule verdict must land in the
    /// first 40 cells, with detail behind them. Terse speech drops the
    /// calendar and the appointment restatement (Tab still carries both).
    ///
    /// The hours detail moved onto Alt A, Alt S, and Alt D, but C keeps one
    /// clause for whichever limit comes first: a driver can be on schedule and
    /// out of hours at the same time, and hearing only the schedule would be
    /// the wrong half of the answer.
    ///
    /// `full_hours` keeps the whole hours-of-service report in one press for
    /// the controller's D-pad right, which has nowhere to put three more info
    /// buttons. A pad player must not lose hours of service.
    pub fn speak_clock(&mut self, ctx: &mut GameContext, full_hours: bool) {
        let hours_used = self.trip.game_minutes / 60.0;
        let road_time = hos::duration_text_up(hours_used);
        let terse = self.terse_speech(ctx);
        let now = if terse {
            format!(
                "{} {}.",
                clock_text(self.trip.local_hour()),
                self.trip.current_timezone().name
            )
        } else {
            self.clock_phrase(ctx)
        };
        let tail = if full_hours {
            let mode = ctx.settings.hos_mode.clone();
            let mut clause = hos_of(ctx).summary(&mode);
            let route = if terse {
                String::new()
            } else {
                self.hos_route_context(ctx)
            };
            if !route.is_empty() {
                clause = format!("{clause} {route}");
            }
            format!(" {clause}")
        } else {
            let clause = self.hos_nearest_clause(ctx);
            let mut tail = if clause.is_empty() {
                String::new()
            } else {
                format!(" {clause}")
            };
            tail.push_str(&self.hos_key_notice(ctx));
            tail
        };
        if self.phase == DRIVE_PHASE_PICKUP {
            let facility = self.pickup_facility_text(ctx);
            let remaining = ctx
                .settings
                .distance_text(self.trip.remaining_miles(), false);
            ctx.say(&format!(
                "{now} Pickup at {facility}: {remaining} to go, {road_time} on the road.{tail}"
            ));
            return;
        }
        let remaining = self.job.deadline_game_h - hours_used;
        let eta = self.trip.eta_game_hours(self.trip.truck.speed_mph());
        if remaining <= 0.0 {
            ctx.say(&format!(
                "{now} {} past the delivery deadline. The pay is shrinking, but finish the \
                 delivery.{tail}",
                hos::duration_text_up(-remaining)
            ));
            return;
        }
        let verdict = if eta < remaining {
            "On schedule"
        } else {
            "Running behind"
        };
        let eta_text = hos::duration_text_up(eta);
        let delivery_due = hos::duration_text(remaining);
        if terse {
            ctx.say(&format!(
                "{now} {verdict}: arrival in {eta_text}, delivery due in {delivery_due}.{tail}"
            ));
            return;
        }
        let basis = if self.trip.truck.speed_mph() >= ff_core::sim::trip::ETA_MIN_MPH {
            "at this pace"
        } else {
            "at a typical highway pace"
        };
        let push = if verdict == "Running behind" {
            " Keep your speed up."
        } else {
            ""
        };
        let appointment = deadline_appointment(self, ctx);
        ctx.say(&format!(
            "{now} {verdict}: arrival in {eta_text} {basis}, delivery due in {delivery_due}, at \
             {appointment}.{push} {road_time} on the road.{tail}"
        ));
    }

    // Alt A, Alt S, and Alt D split the three hours numbers a driver plans
    // around out of the C readout, one key each, left to right in the shape of
    // a shift: what is behind you, what stops you next, and the driving clocks. The
    // Alt chord keeps the right hand on the arrows, where the accelerator is,
    // and a slipped modifier lands on A, S, or D -- all spoken info, nothing
    // that moves the truck. Controllers keep the combined readout on D-pad
    // right; a pad has nowhere to put three more info buttons.

    /// `_hos_nearest_clause()`: one sentence for the HOS limit that comes
    /// first, or "" when off.
    pub fn hos_nearest_clause(&self, ctx: &GameContext) -> String {
        let Some(limit) = hos_of(ctx).next_limit(&ctx.settings.hos_mode) else {
            return String::new();
        };
        if limit.remaining_min <= 0.0 {
            return match limit.kind {
                "break" => "Break overdue.",
                "drive" => "Driving allowance exhausted. Do not drive.",
                _ => "Legal driving cutoff passed. Do not drive.",
            }
            .to_string();
        }
        let left = hos::duration_text(limit.remaining_min / 60.0);
        match limit.kind {
            "break" => format!("Break due in {left}."),
            "drive" => format!("Driving allowance ends in {left}."),
            _ => format!("You must stop driving in {left}."),
        }
    }

    /// `_hos_key_notice()`: where the hours detail went, for the first few
    /// clock presses only.
    ///
    /// Muscle memory says C, so the pointer has to ride C itself. Three
    /// presses is enough to learn it and few enough not to become noise.
    pub fn hos_key_notice(&self, ctx: &mut GameContext) -> String {
        let left = profile_of(ctx).hos_key_notice_left;
        if left <= 0 {
            return String::new();
        }
        profile_mut_of(ctx).hos_key_notice_left = left - 1;
        " Hours of service moved to Alt A, Alt S, and Alt D.".to_string()
    }

    /// `_speak_hos_wheel_time()`: Alt A -- how much of this shift is already
    /// behind you.
    pub fn speak_hos_wheel_time(&mut self, ctx: &mut GameContext) {
        let terse = self.terse_speech(ctx);
        let mode = ctx.settings.hos_mode.clone();
        let text = hos_of(ctx).wheel_time_summary(&mode, terse);
        ctx.say(&text);
    }

    /// `_speak_hos_break()`: Alt S -- when the 30-minute break comes due.
    pub fn speak_hos_break(&mut self, ctx: &mut GameContext) {
        let terse = self.terse_speech(ctx);
        let mode = ctx.settings.hos_mode.clone();
        let text = hos_of(ctx).break_summary(&mode, terse);
        ctx.say(&text);
    }

    /// `_speak_hos_drive_left()`: Alt D -- the two driving clocks, and where you
    /// can legally stop before it.
    pub fn speak_hos_drive_left(&mut self, ctx: &mut GameContext) {
        let terse = self.terse_speech(ctx);
        let mode = ctx.settings.hos_mode.clone();
        let mut text = hos_of(ctx).drive_time_summary(&mode, terse);
        if !terse {
            let route = self.hos_route_context(ctx);
            if !route.is_empty() {
                text = format!("{text} {route}");
            }
        }
        ctx.say(&text);
    }

    /// `_hos_route_context()`.
    pub fn hos_route_context(&self, ctx: &GameContext) -> String {
        let mode = &ctx.settings.hos_mode;
        let Some(limit) = hos_of(ctx).next_limit(mode) else {
            return String::new();
        };
        if limit.remaining_min <= 0.0 {
            return "Nearest legal action: stop for a compliant break or 10-hour reset."
                .to_string();
        }
        let legal_miles = self.legal_miles_for_hos(limit.remaining_min);
        let (stop_action, plan_action, limit_name) = match limit.kind {
            "break" => ("break", "stop", "30-minute break"),
            "drive" => ("sleep", "park", "driving allowance"),
            _ => ("sleep", "park", "legal driving cutoff"),
        };
        let next_stop = self.upcoming_stop_with_action(stop_action, legal_miles);
        let Some(next_stop) = next_stop else {
            return format!(
                "No route stop is currently visible before your {limit_name} in {}. Plan to \
                 {plan_action} within that time. If you cannot reach a stop, come to a stop and you \
                 can sleep on the shoulder: poor rest, and a possible parking ticket.",
                hos::duration_text(limit.remaining_min / 60.0)
            );
        };
        let ahead = 0.0f64.max(next_stop.at_mi - self.trip.position_mi);
        let mut stop_text = format!(
            "Next legal stop: {}{} in {}",
            self.trip.planned_prefix(next_stop),
            next_stop.spoken_name(),
            ctx.settings.distance_text(ahead, false)
        );
        let parking_text = next_stop.parking_text();
        if !parking_text.is_empty() {
            stop_text.push_str(&format!(", {parking_text}"));
        }
        format!("{stop_text}, before your {limit_name}.")
    }

    /// `_legal_miles_for_hos(remaining_min)`.
    pub fn legal_miles_for_hos(&self, remaining_min: f64) -> f64 {
        let speed = self.trip.truck.speed_mph();
        let speed = if speed == 0.0 { 55.0 } else { speed };
        let pace = 35.0f64.max(62.0f64.min(speed));
        0.0f64.max(remaining_min / 60.0 * pace)
    }

    /// `_upcoming_stop_with_action(action, within_mi)`.
    pub fn upcoming_stop_with_action(&self, action: &str, within_mi: f64) -> Option<&RoadStop> {
        let mut best: Option<&RoadStop> = None;
        for stop in &self.trip.stops {
            let ahead = stop.at_mi - self.trip.position_mi;
            if !(0.0..=within_mi).contains(&ahead) {
                continue;
            }
            if !stop.actions.iter().any(|a| a == action) || stop.parking == "none" {
                continue;
            }
            if best.is_none_or(|b| stop.at_mi < b.at_mi) {
                best = Some(stop);
            }
        }
        best
    }

    /// `emergency_shoulder_sleep_reason()`: why shoulder sleep is offered
    /// now, or None when it is not.
    ///
    /// Available whenever the truck is stopped with no route POI to pull into
    /// -- a driver can always choose to pull over and rest, urgently or not.
    /// The wording escalates with urgency (severe fatigue, or an HOS limit
    /// closing in with no reachable stop) but the option itself is always
    /// there.
    pub fn emergency_shoulder_sleep_reason(&self, ctx: &GameContext) -> Option<String> {
        if self.trip.truck.speed_mph() > DOCKING_MAX_MPH {
            return None;
        }
        if self.trip.nearest_stop_within(1.5).is_some() {
            return None; // a POI is right here; use its rest menu instead
        }
        if profile_of(ctx).fatigue >= hos::FATIGUE_SEVERE {
            return Some("Fatigue is severe, and no route stop is nearby.".to_string());
        }
        let mode = &ctx.settings.hos_mode;
        if !hos::HOS_NON_ENFORCED_MODES.contains(&mode.as_str()) {
            if hos_of(ctx).in_violation(mode) {
                return Some(
                    "You are past your hours-of-service limit, and there is no route POI here."
                        .to_string(),
                );
            }
            if let Some(limit) = hos_of(ctx).next_limit(mode) {
                let (action, limit_name) = match limit.kind {
                    "break" => ("break", "30-minute break"),
                    "drive" => ("sleep", "driving allowance"),
                    _ => ("sleep", "legal driving cutoff"),
                };
                let legal_miles = self.legal_miles_for_hos(limit.remaining_min);
                if limit.remaining_min <= hos::SHOULDER_SLEEP_LIMIT_BUFFER_MIN
                    && self
                        .upcoming_stop_with_action(action, (legal_miles + 5.0).max(5.0))
                        .is_none()
                {
                    return Some(format!(
                        "Your {limit_name} arrives in {}, and no suitable route stop is visible \
                         before it.",
                        hos::duration_text(limit.remaining_min / 60.0)
                    ));
                }
            }
        }
        Some("No route stop is nearby. You can pull over and rest on the shoulder.".to_string())
    }
}
