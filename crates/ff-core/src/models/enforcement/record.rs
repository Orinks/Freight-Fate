//! The licence file: `DrivingRecord` and the legacy-save seeding, split out
//! of `enforcement.py` by size only.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

use super::{
    FATIGUE_EVENTS_BEFORE_SERIOUS, HOURS_PER_DAY, MAJOR_FIRST_DISQUALIFICATION_DAYS,
    REPUTATION_FULL_BOARD, SERIOUS_SECOND_SUSPENSION_DAYS, SERIOUS_THIRD_SUSPENSION_DAYS,
    SERIOUS_WINDOW_DAYS, SUSPENSION_LIFETIME, SUSPENSION_MAJOR, SUSPENSION_SERIOUS,
};
use crate::models::save_migration::{json_f64, json_i64};

/// What the licence file remembers about this driver, for the whole career.
///
/// Times are career game hours -- the same clock `Profile.game_hours` runs
/// on -- so a suspension is served in game time and survives save and load.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(default)]
pub struct DrivingRecord {
    /// Career game hours at which each serious violation was recorded.
    pub serious_violations: Vec<f64>,
    /// Career game hours at which each major offense was recorded.
    pub major_offenses: Vec<f64>,
    /// Every spoken roadside citation, lifetime.
    pub citations: i64,
    /// Lifetime enforcement money, all sources.
    pub fines_paid: f64,
    /// Times this driver ran off the road asleep.
    pub fatigue_events: i64,
    /// The trust band the driver has already been told about, so a change is
    /// spoken once when it happens and never repeated on a timer.
    pub trust_band_heard: String,
    /// The debt warning the driver has already been given, on the same
    /// discipline: rungs are spoken when they move, never on a timer.
    pub debt_rung_heard: i64,
    /// Times a lender has taken an owner-operator's tractor back.
    pub repossessions: i64,
    /// A career-changing setback that has happened but not yet been read: the
    /// lines are composed when it lands and kept until the driver acknowledges
    /// them, so the longest and most consequential text in the game survives a
    /// keypress, a save, and a reload.
    /// `""` | `"termination"` | `"repossession"`.
    pub setback_notice_kind: String,
    pub setback_notice_lines: Vec<String>,
    /// Career game hours the CDL comes back.
    pub suspended_until_h: f64,
    /// `SUSPENSION_SERIOUS` / `SUSPENSION_MAJOR`.
    pub suspension_reason: String,
    pub lifetime_disqualified: bool,
    pub carrier_terminations: i64,
    /// A career that predates the record loaded with offenses already on it and
    /// has not yet heard the one-time explanation of where it now stands.
    pub notice_pending: bool,
}

impl DrivingRecord {
    pub fn new() -> Self {
        Self::default()
    }

    // -- reads --------------------------------------------------------------

    /// Serious violations still inside the three-year counting window.
    pub fn serious_in_window(&self, game_hours: f64) -> i64 {
        let cutoff = game_hours - SERIOUS_WINDOW_DAYS as f64 * HOURS_PER_DAY;
        self.serious_violations
            .iter()
            .filter(|&&at| at >= cutoff)
            .count() as i64
    }

    pub fn major_count(&self) -> i64 {
        self.major_offenses.len() as i64
    }

    pub fn suspended(&self, game_hours: f64) -> bool {
        self.lifetime_disqualified || game_hours < self.suspended_until_h
    }

    /// Hours of suspension left; infinite for a lifetime disqualification.
    pub fn hours_left(&self, game_hours: f64) -> f64 {
        if self.lifetime_disqualified {
            return f64::INFINITY;
        }
        (self.suspended_until_h - game_hours).max(0.0)
    }

    pub fn days_left(&self, game_hours: f64) -> f64 {
        let left = self.hours_left(game_hours);
        if left == f64::INFINITY {
            left
        } else {
            left / HOURS_PER_DAY
        }
    }

    /// No standing a player would want explained to them.
    pub fn clean(&self, game_hours: f64) -> bool {
        !self.lifetime_disqualified
            && !self.suspended(game_hours)
            && self.serious_in_window(game_hours) == 0
            && self.major_offenses.is_empty()
    }

    // -- writes -------------------------------------------------------------

    pub fn record_citation(&mut self, fine: f64) {
        self.citations += 1;
        self.fines_paid += fine.max(0.0);
    }

    /// Log a serious traffic violation; returns the count in the window.
    ///
    /// Applies the 383.51 Table 2 ladder: the second conviction inside three
    /// years suspends the CDL for 60 days, the third and every one after for
    /// 120 days.
    pub fn record_serious_violation(&mut self, game_hours: f64) -> i64 {
        self.serious_violations.push(game_hours);
        let count = self.serious_in_window(game_hours);
        if count == 2 {
            self.suspend(
                game_hours,
                SERIOUS_SECOND_SUSPENSION_DAYS,
                SUSPENSION_SERIOUS,
            );
        } else if count >= 3 {
            self.suspend(
                game_hours,
                SERIOUS_THIRD_SUSPENSION_DAYS,
                SUSPENSION_SERIOUS,
            );
        }
        count
    }

    /// Log running off the road asleep. Returns (fatigue events, serious).
    ///
    /// The first one is a preventable safety incident: it costs standing but
    /// not the licence. From the second on it is a 49 CFR 392.3 violation --
    /// operating a commercial vehicle impaired by fatigue -- and it joins the
    /// serious-violation ladder like any other.
    pub fn record_fatigue_event(&mut self, game_hours: f64) -> (i64, i64) {
        self.fatigue_events += 1;
        let mut serious = 0;
        if self.fatigue_events >= FATIGUE_EVENTS_BEFORE_SERIOUS {
            serious = self.record_serious_violation(game_hours);
        }
        (self.fatigue_events, serious)
    }

    /// Log a major offense; returns `SUSPENSION_MAJOR` or `SUSPENSION_LIFETIME`.
    ///
    /// Table 1: one year for the first, life for the second.
    pub fn record_major_offense(&mut self, game_hours: f64) -> &'static str {
        self.major_offenses.push(game_hours);
        if self.major_offenses.len() >= 2 {
            self.lifetime_disqualified = true;
            self.suspension_reason = SUSPENSION_LIFETIME.to_string();
            return SUSPENSION_LIFETIME;
        }
        self.suspend(
            game_hours,
            MAJOR_FIRST_DISQUALIFICATION_DAYS,
            SUSPENSION_MAJOR,
        );
        SUSPENSION_MAJOR
    }

    fn suspend(&mut self, game_hours: f64, days: i64, reason: &str) {
        // Suspensions run consecutively: a new one starts where the last one
        // ends, exactly as a state licensing agency stacks them.
        let start = game_hours.max(self.suspended_until_h);
        self.suspended_until_h = start + days as f64 * HOURS_PER_DAY;
        self.suspension_reason = reason.to_string();
    }

    /// Called when the career clock has been advanced past a suspension.
    pub fn serve_until(&mut self, game_hours: f64) {
        if !self.lifetime_disqualified && game_hours >= self.suspended_until_h {
            self.suspended_until_h = 0.0;
            self.suspension_reason = String::new();
        }
    }
}

// -- legacy careers ---------------------------------------------------------

/// Build a record for a career saved before the record existed.
///
/// No amnesty: every offense the save actually still holds is counted, and
/// the driver hears about it once. Offenses are read out of the mid-delivery
/// trip snapshot, which is the only place the old build kept them.
pub fn seed_record_from_save(data: &Map<String, Value>) -> DrivingRecord {
    let mut record = DrivingRecord::new();
    let game_hours = json_f64(data.get("game_hours"), 0.0);
    if let Some(trip) = data.get("active_trip").and_then(Value::as_object) {
        for _ in 0..json_i64(trip.get("failure_to_stop_count"), 0).max(0) {
            record.record_major_offense(game_hours);
        }
        for _ in 0..json_i64(trip.get("speeding_tickets"), 0).max(0) {
            record.record_citation(json_f64(trip.get("ticket_fines_paid"), 0.0));
        }
    }
    // `float((data.get("career") or {}).get("reputation", 50.0) or 50.0)`:
    // a missing career, a missing field and a falsy zero all read as 50.
    let reputation = match data
        .get("career")
        .and_then(Value::as_object)
        .map(|career| json_f64(career.get("reputation"), 50.0))
    {
        Some(rep) if rep != 0.0 => rep,
        _ => 50.0,
    };
    if !record.clean(game_hours) || reputation < REPUTATION_FULL_BOARD {
        record.notice_pending = true;
    }
    record
}
