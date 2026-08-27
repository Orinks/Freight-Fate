//! The ELD shift ledger: `HosEvent` and `HosClock`.

use serde_json::{json, Value};

use super::pyjson::{py_float_or, py_iter, py_max, py_repr_str, py_str, py_str_or};
use super::{
    duration_text, is_duty_status, limits, positive_minutes, BREAK_MIN, HOS_HISTORY_MAX,
    HOS_SPLIT_REST_HISTORY_MAX, SLEEP_MIN, SPLIT_LONG_ALT_MIN, SPLIT_LONG_MIN, SPLIT_SHORT_ALT_MIN,
    SPLIT_SHORT_MIN, WARNING_THRESHOLDS_MIN,
};
use crate::pyfmt::{fmt_f, py_str_float};

/// One duty-status entry in the shift ledger.
#[derive(Clone, Debug, PartialEq)]
pub struct HosEvent {
    pub status: String,
    pub minutes: f64,
    pub drive_before: f64,
    pub duty_before: f64,
    pub since_break_before: f64,
    pub source: String,
}

impl Default for HosEvent {
    fn default() -> Self {
        Self {
            status: "off_duty".to_string(),
            minutes: 0.0,
            drive_before: 0.0,
            duty_before: 0.0,
            since_break_before: 0.0,
            source: "normal".to_string(),
        }
    }
}

impl HosEvent {
    pub fn new(
        status: &str,
        minutes: f64,
        drive_before: f64,
        duty_before: f64,
        since_break_before: f64,
        source: &str,
    ) -> Self {
        Self {
            status: status.to_string(),
            minutes,
            drive_before,
            duty_before,
            since_break_before,
            source: source.to_string(),
        }
    }

    pub fn to_dict(&self) -> Value {
        json!({
            "status": self.status,
            "minutes": self.minutes,
            "drive_before": self.drive_before,
            "duty_before": self.duty_before,
            "since_break_before": self.since_break_before,
            "source": self.source,
        })
    }

    /// `None` for anything that is not a readable event.
    pub fn from_dict(data: &Value) -> Option<Self> {
        let obj = data.as_object()?;
        let status = py_str_or(obj.get("status"), "off_duty");
        if !is_duty_status(&status) {
            return None;
        }
        Some(Self {
            status,
            minutes: py_float_or(obj.get("minutes"), 0.0)?,
            drive_before: py_float_or(obj.get("drive_before"), 0.0)?,
            duty_before: py_float_or(obj.get("duty_before"), 0.0)?,
            since_break_before: py_float_or(obj.get("since_break_before"), 0.0)?,
            source: py_str_or(obj.get("source"), "normal"),
        })
    }
}

/// The nearest-limit answer of [`HosClock::next_limit`]: which rule, how many
/// game minutes are left on it, and the spoken "what is due" clause.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct HosLimit {
    pub kind: &'static str,
    pub remaining_min: f64,
    pub due: &'static str,
}

/// The Python `repr` of the two events' field tuples, which is what the
/// save stores as `split_credit_key`: strings single-quoted, floats as
/// Python prints them, `((...), (...))` with `", "` separators.
pub(super) fn split_event_key(first: &HosEvent, second: &HosEvent) -> String {
    fn event_key(event: &HosEvent) -> String {
        format!(
            "({}, {}, {}, {}, {}, {})",
            py_repr_str(&event.status),
            py_repr_str(&event.source),
            py_str_float(event.minutes),
            py_str_float(event.drive_before),
            py_str_float(event.duty_before),
            py_str_float(event.since_break_before),
        )
    }
    format!("({}, {})", event_key(first), event_key(second))
}

fn split_pair_qualifies(first: &HosEvent, second: &HosEvent) -> bool {
    if first.source == "full_reset"
        || second.source == "full_reset"
        || first.minutes >= SLEEP_MIN
        || second.minutes >= SLEEP_MIN
    {
        return false;
    }
    let total = first.minutes + second.minutes;
    if total < SLEEP_MIN {
        return false;
    }
    let (long_event, short_event) = if first.minutes >= second.minutes {
        (first, second)
    } else {
        (second, first)
    };
    if long_event.status != "sleeper_berth" {
        return false;
    }
    if long_event.minutes >= SPLIT_LONG_ALT_MIN && short_event.minutes >= SPLIT_SHORT_MIN {
        return true;
    }
    long_event.minutes >= SPLIT_LONG_MIN && short_event.minutes >= SPLIT_SHORT_ALT_MIN
}

/// Keep only the last `max` entries (Python `items[-max:]`).
fn keep_last<T>(items: &mut Vec<T>, max: usize) {
    if items.len() > max {
        let excess = items.len() - max;
        items.drain(..excess);
    }
}

fn threshold_phrase(threshold: f64) -> &'static str {
    if threshold == 120.0 {
        "2 hours"
    } else if threshold == 60.0 {
        "1 hour"
    } else if threshold == 30.0 {
        "30 minutes"
    } else {
        panic!("no phrase for HOS warning threshold {threshold}")
    }
}

/// One ELD-style shift ledger, in game minutes.
///
/// `duty_min` is the elapsed 14-hour window since the last qualifying
/// 10-hour reset, not just on-duty labor. FMCSA's 14-hour window is not
/// extended by short off-duty breaks, so short breaks keep advancing it.
#[derive(Clone, Debug, PartialEq)]
pub struct HosClock {
    /// time at the wheel this shift
    pub driving_min: f64,
    /// elapsed 14-hour duty window
    pub duty_min: f64,
    /// driving since the last 30-minute break
    pub since_break_min: f64,
    pub status: String,
    /// consecutive non-driving time
    pub non_driving_min: f64,
    /// consecutive off-duty/sleeper time
    pub off_duty_min: f64,
    /// thresholds already spoken
    pub warned: Vec<String>,
    pub history: Vec<HosEvent>,
    pub split_rest_history: Vec<HosEvent>,
    pub split_credit_key: Option<String>,
}

impl Default for HosClock {
    fn default() -> Self {
        Self {
            driving_min: 0.0,
            duty_min: 0.0,
            since_break_min: 0.0,
            status: "off_duty".to_string(),
            non_driving_min: 0.0,
            off_duty_min: 0.0,
            warned: Vec::new(),
            history: Vec::new(),
            split_rest_history: Vec::new(),
            split_credit_key: None,
        }
    }
}

impl HosClock {
    pub fn new() -> Self {
        Self::default()
    }

    // -- time accounting ------------------------------------------------------

    pub fn drive(&mut self, minutes: f64) {
        let minutes = positive_minutes(minutes);
        self.record_event("driving", minutes, "normal");
        self.driving_min += minutes;
        self.duty_min += minutes;
        self.since_break_min += minutes;
        self.status = "driving".to_string();
        self.non_driving_min = 0.0;
        self.off_duty_min = 0.0;
    }

    /// Work time away from the wheel: fueling, loading, inspections, service.
    pub fn on_duty(&mut self, minutes: f64) {
        let minutes = positive_minutes(minutes);
        self.record_event("on_duty_not_driving", minutes, "normal");
        self.duty_min += minutes;
        self.status = "on_duty_not_driving".to_string();
        self.off_duty_min = 0.0;
        self.record_non_driving(minutes);
    }

    /// Off-duty time. Short breaks do not extend the 14-hour window.
    pub fn off_duty(&mut self, minutes: f64) {
        let minutes = positive_minutes(minutes);
        self.record_event("off_duty", minutes, "normal");
        self.duty_min += minutes;
        self.status = "off_duty".to_string();
        self.record_non_driving(minutes);
        self.off_duty_min += minutes;
        if self.off_duty_min >= SLEEP_MIN {
            self.sleep_as("off_duty");
            return;
        }
        self.apply_split_credit();
    }

    /// Sleeper-berth time. A full 10 hours resets; shorter rests may split.
    pub fn sleeper(&mut self, minutes: f64) {
        let minutes = positive_minutes(minutes);
        self.record_event("sleeper_berth", minutes, "normal");
        self.duty_min += minutes;
        self.status = "sleeper_berth".to_string();
        self.record_non_driving(minutes);
        self.off_duty_min += minutes;
        if self.off_duty_min >= SLEEP_MIN {
            self.sleep_as("sleeper_berth");
            return;
        }
        self.apply_split_credit();
    }

    /// A short off-duty rest. Kept for old callers and explicit break actions.
    pub fn take_break(&mut self, minutes: f64) {
        self.off_duty(minutes);
    }

    /// A full 10-hour off-duty reset: a fresh shift (`sleep()` in Python,
    /// which defaults the status to the sleeper berth).
    pub fn sleep(&mut self) {
        self.sleep_as("sleeper_berth");
    }

    /// A full 10-hour off-duty reset recorded under `status`.
    pub fn sleep_as(&mut self, status: &str) {
        self.record_event(status, SLEEP_MIN, "full_reset");
        self.driving_min = 0.0;
        self.duty_min = 0.0;
        self.since_break_min = 0.0;
        self.status = if is_duty_status(status) {
            status.to_string()
        } else {
            "sleeper_berth".to_string()
        };
        self.non_driving_min = SLEEP_MIN;
        self.off_duty_min = SLEEP_MIN;
        self.split_credit_key = None;
        self.warned.clear();
    }

    fn record_non_driving(&mut self, minutes: f64) {
        self.non_driving_min += minutes;
        if self.non_driving_min >= BREAK_MIN {
            self.since_break_min = 0.0;
            self.warned.retain(|w| !w.starts_with("break:"));
        }
    }

    fn record_event(&mut self, status: &str, minutes: f64, source: &str) {
        let event = HosEvent::new(
            status,
            minutes,
            self.driving_min,
            self.duty_min,
            self.since_break_min,
            source,
        );
        self.history.push(event.clone());
        keep_last(&mut self.history, HOS_HISTORY_MAX);
        if source == "full_reset" {
            self.split_rest_history.clear();
        } else if source == "normal"
            && (status == "off_duty" || status == "sleeper_berth")
            && minutes >= SPLIT_SHORT_MIN
        {
            self.split_rest_history.push(event);
            keep_last(&mut self.split_rest_history, HOS_SPLIT_REST_HISTORY_MAX);
        }
    }

    fn key_is_credited(&self, first: usize, second: usize) -> bool {
        match &self.split_credit_key {
            Some(key) => {
                *key == split_event_key(
                    &self.split_rest_history[first],
                    &self.split_rest_history[second],
                )
            }
            None => false,
        }
    }

    /// The Python walks `(first, second)` object pairs and compares them by
    /// identity; the same events are addressed here by their positions in
    /// `split_rest_history`, which is what identity meant there.
    fn qualifying_split_pair(&self) -> Option<(usize, usize)> {
        let n = self.split_rest_history.len();
        let last_first = n.saturating_sub(1);
        let mut start = 0;
        if self.split_credit_key.is_some() {
            for i in 0..last_first {
                if self.key_is_credited(i, i + 1) {
                    start = i + 1;
                    break;
                }
            }
        }
        for i in (start..last_first).rev() {
            if self.key_is_credited(i, i + 1) {
                continue;
            }
            if split_pair_qualifies(&self.split_rest_history[i], &self.split_rest_history[i + 1]) {
                return Some((i, i + 1));
            }
        }
        None
    }

    fn apply_split_credit(&mut self) {
        let Some((first, second)) = self.qualifying_split_pair() else {
            return;
        };
        let key = split_event_key(
            &self.split_rest_history[first],
            &self.split_rest_history[second],
        );
        if self.split_credit_key.as_deref() == Some(key.as_str()) {
            return;
        }
        let second_event = &self.split_rest_history[second];
        self.driving_min = second_event.drive_before - self.split_drive_after_rest(first);
        self.duty_min = second_event.duty_before - self.split_duty_after_rest(first);
        self.since_break_min = 0.0;
        self.split_credit_key = Some(key);
        self.warned.retain(|w| {
            !(w.starts_with("drive:") || w.starts_with("duty:") || w.starts_with("break:"))
        });
    }

    fn split_drive_after_rest(&self, event: usize) -> f64 {
        if let Some((first, second)) = self.previous_qualifying_split_pair(event) {
            return self.split_rest_history[second].drive_before
                - self.split_drive_after_rest(first);
        }
        self.split_rest_history[event].drive_before
    }

    fn split_duty_after_rest(&self, event: usize) -> f64 {
        if let Some((first, second)) = self.previous_qualifying_split_pair(event) {
            return self.split_rest_history[second].duty_before - self.split_duty_after_rest(first);
        }
        let event = &self.split_rest_history[event];
        event.duty_before + event.minutes
    }

    /// The pair whose second event IS this one: the one ending at `event`.
    fn previous_qualifying_split_pair(&self, event: usize) -> Option<(usize, usize)> {
        if event >= 1
            && split_pair_qualifies(
                &self.split_rest_history[event - 1],
                &self.split_rest_history[event],
            )
        {
            return Some((event - 1, event));
        }
        None
    }

    fn credited_split_pair(&self) -> Option<(usize, usize)> {
        self.split_credit_key.as_ref()?;
        let n = self.split_rest_history.len();
        (0..n.saturating_sub(1))
            .find(|&i| self.key_is_credited(i, i + 1))
            .map(|i| (i, i + 1))
    }

    /// A sleeper-berth rest that may complete a split; `true` when it
    /// credited one (`sleeper_split_rest(minutes)` in Python).
    pub fn sleeper_split_rest(&mut self, minutes: f64) -> bool {
        self.sleeper_split_rest_from(minutes, "normal")
    }

    /// [`Self::sleeper_split_rest`] recorded under an explicit event source.
    pub fn sleeper_split_rest_from(&mut self, minutes: f64, source: &str) -> bool {
        let minutes = positive_minutes(minutes);
        self.record_event("sleeper_berth", minutes, source);
        self.duty_min += minutes;
        self.status = "sleeper_berth".to_string();
        self.record_non_driving(minutes);
        self.off_duty_min += minutes;
        if self.off_duty_min >= SLEEP_MIN {
            self.sleep_as("sleeper_berth");
            return false;
        }
        let before_key = self.split_credit_key.clone();
        self.apply_split_credit();
        self.split_credit_key != before_key
    }

    // -- rule queries ----------------------------------------------------------

    /// (kind, minutes remaining, what is due) per enforced limit.
    pub(super) fn statuses(&self, mode: &str) -> Vec<HosLimit> {
        let Some((drive_limit, duty_limit, break_after)) = limits(mode) else {
            return Vec::new();
        };
        vec![
            HosLimit {
                kind: "break",
                remaining_min: break_after - self.since_break_min,
                due: "your 30-minute break is due",
            },
            HosLimit {
                kind: "drive",
                remaining_min: drive_limit - self.driving_min,
                due: "your driving allowance ends",
            },
            HosLimit {
                kind: "duty",
                remaining_min: duty_limit - self.duty_min,
                due: "you must stop driving",
            },
        ]
    }

    /// Game minutes until the nearest limit, or None when not enforced.
    pub fn remaining_min(&self, mode: &str) -> Option<f64> {
        self.next_limit(mode).map(|limit| limit.remaining_min)
    }

    /// Nearest enforced HOS limit as (kind, minutes, due_text); the first
    /// one on a tie, as Python's `min` picks it.
    pub fn next_limit(&self, mode: &str) -> Option<HosLimit> {
        let mut best: Option<HosLimit> = None;
        for status in self.statuses(mode) {
            let nearer = match best {
                Some(b) => status.remaining_min < b.remaining_min,
                None => true,
            };
            if nearer {
                best = Some(status);
            }
        }
        best
    }

    pub fn in_violation(&self, mode: &str) -> bool {
        self.statuses(mode).iter().any(|s| s.remaining_min <= 0.0)
    }

    /// Plain spoken phrases for every limit currently blown.
    ///
    /// The roadside out-of-service stop uses these BEFORE the reset wipes
    /// the ledger, so the officer can say exactly why the order stands.
    pub fn violation_causes(&self, mode: &str) -> Vec<String> {
        self.statuses(mode)
            .iter()
            .filter(|s| s.remaining_min <= 0.0)
            .filter_map(|s| match s.kind {
                "drive" => Some("you had driven past the 11-hour driving limit"),
                "duty" => Some("you had driven past the 14-hour driving window"),
                "break" => Some("you were past the 30-minute break requirement"),
                _ => None,
            })
            .map(str::to_string)
            .collect()
    }

    /// Speak the countdown again after a rest that did NOT reset the shift.
    ///
    /// Warnings fire once per threshold per shift -- correct while driving,
    /// but a long non-qualifying sleep (a pending sleeper split) left the
    /// marks in place, so the driver woke to silence and drove straight
    /// into a window violation with no countdown (owner, 2026-07-24).
    pub fn re_arm_warnings(&mut self) {
        self.warned.retain(|w| {
            !(w.starts_with("drive:") || w.starts_with("duty:") || w.starts_with("break:"))
        });
    }

    /// Newly crossed warning messages; each threshold fires once.
    ///
    /// Call this every frame while driving. Crossing several thresholds at
    /// once (a long menu action, say) speaks only the most urgent one, but
    /// marks them all so nothing fires late.
    pub fn check_warnings(&mut self, mode: &str) -> Vec<String> {
        let mut candidates: Vec<(i32, f64, String)> = Vec::new();
        let binding_kind = self.next_limit(mode).map(|limit| limit.kind);
        let drive_available = limits(mode)
            .map(|(drive_limit, _, _)| {
                duration_text(py_max(0.0, drive_limit - self.driving_min) / 60.0)
            })
            .unwrap_or_default();
        for HosLimit {
            kind,
            remaining_min: rem,
            due,
        } in self.statuses(mode)
        {
            if rem <= 0.0 {
                let key = format!("{kind}:violation");
                if !self.warned.contains(&key) {
                    self.warned.push(key);
                    for t in WARNING_THRESHOLDS_MIN {
                        // swallow the lead-up ones
                        let k = format!("{kind}:{}", fmt_f(t, 0));
                        if !self.warned.contains(&k) {
                            self.warned.push(k);
                        }
                    }
                    let priority = match kind {
                        "drive" => 0,
                        "duty" => 1,
                        "break" => 2,
                        _ => 9,
                    };
                    let message = match kind {
                        "break" => "Hours of service violation: Your 30-minute break is overdue. \
                                    Take the required break before driving again."
                            .to_string(),
                        "drive" => "Hours of service violation: Your driving allowance is \
                                    exhausted. Do not drive until a 10-hour reset."
                            .to_string(),
                        "duty" => "Hours of service violation: Your legal driving cutoff has \
                                   passed. Do not drive until a 10-hour reset."
                            .to_string(),
                        _ => format!("Hours of service violation: {due}."),
                    };
                    candidates.push((priority, rem, message));
                }
                continue;
            }
            let crossed: Vec<f64> = WARNING_THRESHOLDS_MIN
                .iter()
                .copied()
                .filter(|t| rem <= *t && !self.warned.contains(&format!("{kind}:{}", fmt_f(*t, 0))))
                .collect();
            if !crossed.is_empty() {
                for t in &crossed {
                    self.warned.push(format!("{kind}:{}", fmt_f(*t, 0)));
                }
                if binding_kind != Some(kind) {
                    continue;
                }
                let smallest = crossed.iter().copied().fold(f64::INFINITY, f64::min);
                let phrase = threshold_phrase(smallest);
                let message = match kind {
                    "break" => format!(
                        "Hours of service: 30-minute break due in {phrase}. Plan to stop within \
                         {phrase}."
                    ),
                    "drive" => format!(
                        "Hours of service: Driving allowance ends in {phrase}. Plan to park \
                         within {phrase}."
                    ),
                    "duty" => format!(
                        "Hours of service: You have {drive_available} of driving available, but \
                         you must stop driving in {phrase}. Plan to park within {phrase}."
                    ),
                    _ => format!("Hours of service: {phrase} until {due}."),
                };
                candidates.push((10, rem, message));
            }
        }
        if candidates.is_empty() {
            return Vec::new();
        }
        // Python's min over (priority, remaining) tuples: the first on a tie.
        let mut best = 0;
        for i in 1..candidates.len() {
            let (p, r, _) = &candidates[i];
            let (bp, br, _) = &candidates[best];
            if p < bp || (p == bp && r < br) {
                best = i;
            }
        }
        vec![candidates.swap_remove(best).2]
    }

    pub fn split_pending_summary(&self) -> Option<&'static str> {
        let rest_events = &self.split_rest_history;
        if let Some((_, second)) = self.credited_split_pair() {
            if second + 1 == rest_events.len() {
                return None;
            }
        }
        if let Some((first, second)) = self.qualifying_split_pair() {
            if self.key_is_credited(first, second) {
                return None;
            }
        }
        let last = rest_events.last()?;
        if last.status == "sleeper_berth" && last.minutes >= SPLIT_LONG_ALT_MIN {
            return Some(
                "Sleeper split pending: pair this with 2 more hours at sleep-capable parking.",
            );
        }
        if last.status == "sleeper_berth" && last.minutes >= SPLIT_LONG_MIN {
            return Some(
                "Sleeper split pending: pair this with 3 more hours at sleep-capable parking.",
            );
        }
        if last.minutes >= SPLIT_SHORT_ALT_MIN {
            return Some(
                "Sleeper split pending: pair this with 7 more hours in the sleeper berth.",
            );
        }
        if last.minutes >= SPLIT_SHORT_MIN {
            return Some(
                "Sleeper split pending: pair this with 8 more hours in the sleeper berth.",
            );
        }
        None
    }

    // -- serialization -----------------------------------------------------------

    pub fn to_dict(&self) -> Value {
        json!({
            "driving_min": self.driving_min,
            "duty_min": self.duty_min,
            "since_break_min": self.since_break_min,
            "status": self.status,
            "non_driving_min": self.non_driving_min,
            "off_duty_min": self.off_duty_min,
            "warned": self.warned,
            "history": self.history.iter().map(HosEvent::to_dict).collect::<Vec<_>>(),
            "split_rest_history": self.split_rest_history.iter().map(HosEvent::to_dict).collect::<Vec<_>>(),
            "split_credit_key": self.split_credit_key,
        })
    }

    /// Tolerant load: anything unreadable becomes a fresh clock.
    pub fn from_dict(data: &Value) -> Self {
        Self::try_from_dict(data).unwrap_or_default()
    }

    fn try_from_dict(data: &Value) -> Option<Self> {
        let obj = data.as_object()?;
        let mut status = py_str_or(obj.get("status"), "off_duty");
        if !is_duty_status(&status) {
            status = "off_duty".to_string();
        }
        let mut history = Vec::new();
        for raw_event in py_iter(obj.get("history"))? {
            if let Some(event) = HosEvent::from_dict(&raw_event) {
                history.push(event);
            }
        }
        let mut split_rest_history = Vec::new();
        match obj.get("split_rest_history") {
            Some(Value::Array(raw_split_rest_history)) => {
                for raw_event in raw_split_rest_history {
                    if let Some(event) = HosEvent::from_dict(raw_event) {
                        split_rest_history.push(event);
                    }
                }
            }
            _ => {
                split_rest_history = history
                    .iter()
                    .filter(|event| {
                        event.source == "normal"
                            && (event.status == "off_duty" || event.status == "sleeper_berth")
                            && event.minutes >= SPLIT_SHORT_MIN
                            && event.minutes < SLEEP_MIN
                    })
                    .cloned()
                    .collect();
            }
        }
        let warned: Vec<String> = py_iter(obj.get("warned"))?.iter().map(py_str).collect();
        let split_credit_key = match obj.get("split_credit_key") {
            None | Some(Value::Null) => None,
            Some(value) => Some(py_str(value)),
        };
        keep_last(&mut history, HOS_HISTORY_MAX);
        keep_last(&mut split_rest_history, HOS_SPLIT_REST_HISTORY_MAX);
        Some(Self {
            driving_min: py_float_or(obj.get("driving_min"), 0.0)?,
            duty_min: py_float_or(obj.get("duty_min"), 0.0)?,
            since_break_min: py_float_or(obj.get("since_break_min"), 0.0)?,
            status,
            non_driving_min: py_float_or(obj.get("non_driving_min"), 0.0)?,
            off_duty_min: py_float_or(obj.get("off_duty_min"), 0.0)?,
            warned,
            history,
            split_rest_history,
            split_credit_key,
        })
    }
}
