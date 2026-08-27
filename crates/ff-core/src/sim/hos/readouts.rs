//! Concise player-facing HOS reports and route-arrival guidance.

use super::clock::HosClock;
use super::pyjson::py_max;
use super::{duration_text, duration_text_up, is_non_enforced, limits};

const ENFORCEMENT_OFF: &str =
    "Hours of service enforcement is off; the ELD clock still records time.";
const RESET_ADVICE: &str = "Sleep 10 hours at a rest stop to reset.";

impl HosClock {
    /// (driving allowance, legal driving cutoff, break) hours left.
    fn hours_left(&self, mode: &str) -> (f64, f64, f64) {
        let (drive_limit, duty_limit, break_after) =
            limits(mode).expect("HOS mode is realistic or relaxed");
        (
            py_max(0.0, drive_limit - self.driving_min) / 60.0,
            py_max(0.0, duty_limit - self.duty_min) / 60.0,
            py_max(0.0, break_after - self.since_break_min) / 60.0,
        )
    }

    fn driving_clock_over(&self, mode: &str) -> Option<&'static str> {
        let statuses = self.statuses(mode);
        let blown = |kind: &str| {
            statuses
                .iter()
                .any(|status| status.kind == kind && status.remaining_min <= 0.0)
        };
        if blown("drive") {
            Some("drive")
        } else if blown("duty") {
            Some("duty")
        } else {
            None
        }
    }

    /// Full ELD status: all clocks, followed by the nearest binding action.
    pub fn summary(&self, mode: &str) -> String {
        if is_non_enforced(mode) {
            return ENFORCEMENT_OFF.to_string();
        }
        if self.in_violation(mode) {
            let blown: Vec<&str> = self
                .statuses(mode)
                .iter()
                .filter(|status| status.remaining_min <= 0.0)
                .map(|status| status.kind)
                .collect();
            if blown == ["break"] {
                return "Hours of service: your 30-minute break is overdue. Take the required \
                        break before driving again."
                    .to_string();
            }
            if blown.contains(&"duty") {
                return "Hours of service: your legal driving cutoff has passed. Do not drive \
                        until a 10-hour reset."
                    .to_string();
            }
            return "Hours of service: your driving allowance is exhausted. Do not drive until \
                    a 10-hour reset."
                .to_string();
        }

        let status = self.status.replace('_', " ");
        let (drive_left, cutoff_left, break_left) = self.hours_left(mode);
        let drive = duration_text(drive_left);
        let cutoff = duration_text(cutoff_left);
        let rest = duration_text(break_left);
        let nearest = self.next_limit(mode).expect("enforced HOS has a limit");
        let body = if nearest.kind == "duty" {
            format!(
                "You have {drive} of driving available, but you must stop driving in {cutoff}. \
                 30-minute break due in {rest}. Plan to park within {cutoff}."
            )
        } else {
            let (action, within) = if nearest.kind == "break" {
                ("stop", rest.as_str())
            } else {
                ("park", drive.as_str())
            };
            format!(
                "{drive} of driving available. You must stop driving in {cutoff}. 30-minute \
                 break due in {rest}. Plan to {action} within {within}."
            )
        };
        let pending = self
            .split_pending_summary()
            .map(|text| format!(" {text}"))
            .unwrap_or_default();
        format!("ELD status {status}. Hours of service: {body}{pending}")
    }

    /// Alt A: driving time used and elapsed time since coming on duty.
    pub fn wheel_time_summary(&self, mode: &str, terse: bool) -> String {
        let fresh = self.driving_min <= 0.0;
        let driven = duration_text(self.driving_min / 60.0);
        let lead = if terse {
            if fresh {
                "At the wheel: no driving yet".to_string()
            } else {
                format!("At the wheel {driven}")
            }
        } else {
            let spent = if fresh {
                "no driving yet".to_string()
            } else {
                format!("{driven} driving")
            };
            format!(
                "At the wheel so far: {spent}, {} since coming on duty",
                duration_text(self.duty_min / 60.0)
            )
        };
        let note = if limits(mode).is_none() {
            ENFORCEMENT_OFF
        } else if self.driving_clock_over(mode).is_some() {
            "You may not drive until a 10-hour reset."
        } else if self.hours_left(mode).2 <= 0.0 {
            "Your 30-minute break is overdue."
        } else {
            ""
        };
        format!("{lead}. {note}").trim_end().to_string()
    }

    /// Alt S: the driving time until a required 30-minute break.
    pub fn break_summary(&self, mode: &str, terse: bool) -> String {
        if limits(mode).is_none() {
            return format!("Break: none required. {ENFORCEMENT_OFF}");
        }
        let (_drive_left, cutoff_left, break_left) = self.hours_left(mode);
        let mut answer = if break_left <= 0.0 {
            if terse {
                "Break overdue".to_string()
            } else {
                "Break overdue. Take a 30-minute break at a rest stop".to_string()
            }
        } else {
            format!(
                "Break due in {}{}",
                duration_text(break_left),
                if terse { "" } else { " of driving" }
            )
        };
        if let Some(kind) = self.driving_clock_over(mode) {
            let reason = if kind == "duty" {
                "your legal driving cutoff has passed"
            } else {
                "your driving allowance is exhausted"
            };
            return format!("{answer}, but {reason}. {RESET_ADVICE}");
        }
        if break_left > 0.0 && cutoff_left <= break_left {
            answer.push_str(&if terse {
                format!(", stop driving in {}", duration_text(cutoff_left))
            } else {
                format!(
                    ", but you must stop driving first, in {}",
                    duration_text(cutoff_left)
                )
            });
        }
        format!("{answer}.")
    }

    /// Alt D: driving allowance contrasted with the separate legal cutoff.
    pub fn drive_time_summary(&self, mode: &str, terse: bool) -> String {
        if limits(mode).is_none() {
            return format!(
                "Driving available: no limit. No legal driving cutoff. {ENFORCEMENT_OFF}"
            );
        }
        let (drive_left, cutoff_left, break_left) = self.hours_left(mode);
        if let Some(kind) = self.driving_clock_over(mode) {
            let lead = if kind == "duty" {
                "Legal driving cutoff passed. Do not drive."
            } else {
                "Driving allowance exhausted. Do not drive."
            };
            return format!("{lead} {RESET_ADVICE}");
        }
        let drive = duration_text(drive_left);
        let cutoff = duration_text(cutoff_left);
        let mut text = if cutoff_left <= drive_left {
            if terse {
                format!("Stop driving in {cutoff}, with {drive} available")
            } else {
                format!(
                    "Legal driving cutoff in {cutoff}. You must stop driving then, even with \
                     {drive} of driving available"
                )
            }
        } else {
            format!("Driving available: {drive}. You must stop driving in {cutoff}")
        };
        if break_left <= 0.0 {
            text.push_str(if terse {
                ", break overdue"
            } else {
                ". Your 30-minute break is overdue and comes first"
            });
        }
        match self.split_pending_summary() {
            Some(pending) => format!("{text}. {pending}"),
            None => format!("{text}."),
        }
    }

    /// Relate a stop ETA to the nearest limit, with an action when it is late.
    pub fn arrival_note(&self, mode: &str, eta_min: f64) -> String {
        if is_non_enforced(mode) || self.in_violation(mode) {
            return String::new();
        }
        let nearest = self.next_limit(mode).expect("enforced HOS has a limit");
        let limit = match nearest.kind {
            "drive" => "driving allowance",
            "duty" => "legal driving cutoff",
            _ => "30-minute break",
        };
        if eta_min < nearest.remaining_min {
            let margin = duration_text((nearest.remaining_min - eta_min) / 60.0);
            return format!(" You would arrive {margin} before your {limit}.");
        }
        let gap = duration_text_up((eta_min - nearest.remaining_min) / 60.0);
        let within = duration_text(nearest.remaining_min / 60.0);
        let action = if nearest.kind == "break" {
            "stop"
        } else {
            "park"
        };
        format!(
            " Your {limit} arrives {gap} before you would reach this stop. Plan to {action} \
             within {within}."
        )
    }
}
