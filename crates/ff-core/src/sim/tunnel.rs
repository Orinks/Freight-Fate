//! Data-led gates for roads that share a one-lane tunnel with rail traffic.

use chrono::{Duration, NaiveDate, NaiveDateTime, NaiveTime, Timelike};

use crate::data::world_models::TunnelData;
use crate::sim::hos::HosClock;
use crate::sim::trip::Trip;
use crate::sim::trip_models::{TripEventData, TripEventKind};
use crate::sim::vehicle::KG_PER_LB;
use crate::speech_text::SpokenMessage;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TunnelDirection {
    ToWhittier,
    FromWhittier,
}

#[derive(Debug, Clone, PartialEq)]
pub enum TunnelDecision {
    Cross,
    Wait { minutes: i64, spoken: String },
    Closed { minutes: i64, spoken: String },
    HoursNotPublished { spoken: String },
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct RigForTunnel {
    pub length_ft: f64,
    pub width_ft: f64,
    pub height_ft: f64,
    pub placarded_hazmat: bool,
    pub hazmat_lb: u32,
}

/// Size is always evaluated before hazardous material and the gate state.
pub fn refusal(data: &TunnelData, rig: RigForTunnel) -> Option<String> {
    let l = &data.limits;
    if rig.length_ft > l.length_ft {
        return Some(l.length_text.replace("{n}", &format_number(rig.length_ft)));
    }
    if rig.width_ft > l.width_ft || rig.width_ft > l.normal_width_ft {
        return Some(l.width_text.clone());
    }
    if rig.height_ft > l.height_ft || rig.height_ft > l.normal_height_ft {
        return Some(l.height_text.clone());
    }
    if rig.placarded_hazmat {
        return Some(l.placarded_text.clone());
    }
    if rig.hazmat_lb > l.non_placarded_hazmat_lb {
        return Some(l.non_placarded_text.clone());
    }
    None
}

fn format_number(n: f64) -> String {
    if n.fract() == 0.0 {
        format!("{n:.0}")
    } else {
        format!("{n:.1}")
    }
}

fn record_at(
    data: &TunnelData,
    at: NaiveDateTime,
) -> Option<&crate::data::world_models::TunnelHours> {
    data.hours.iter().find(|h| {
        let from = chrono::NaiveDate::parse_from_str(&h.valid_from, "%Y-%m-%d").ok();
        let to = chrono::NaiveDate::parse_from_str(&h.valid_to, "%Y-%m-%d").ok();
        matches!((from, to), (Some(from), Some(to)) if from <= at.date() && at.date() <= to)
    })
}

fn opens_for(data: &TunnelData, at: NaiveDateTime, direction: TunnelDirection) -> bool {
    let Some(hours) = record_at(data, at) else {
        return false;
    };
    let Ok(open) = NaiveTime::parse_from_str(&hours.opens, "%H:%M") else {
        return false;
    };
    let Ok(close) = NaiveTime::parse_from_str(&hours.closes, "%H:%M") else {
        return false;
    };
    let time = at.time();
    if time < open || time >= close {
        return false;
    }
    let opening_minute =
        (time.minute() / data.schedule.interval_minutes) * data.schedule.interval_minutes;
    if time.minute() - opening_minute >= data.schedule.opening_minutes {
        return false;
    }
    let bv = opening_minute == 30;
    matches!(
        (bv, direction),
        (true, TunnelDirection::ToWhittier) | (false, TunnelDirection::FromWhittier)
    )
}

fn next_opening(
    data: &TunnelData,
    at: NaiveDateTime,
    direction: TunnelDirection,
) -> Option<NaiveDateTime> {
    let mut cursor = at.with_second(0)?.with_nanosecond(0)?;
    // Openings start on interval marks.  Move to the next mark strictly after
    // the arrival minute, so a :20 arrival catches the :30 opening.
    let interval = i64::from(data.schedule.interval_minutes);
    let past_mark = i64::from(cursor.time().minute()) % interval;
    cursor += Duration::minutes(interval - past_mark);
    for _ in 0..(366 * 48) {
        if opens_for(data, cursor, direction) {
            return Some(cursor);
        }
        cursor += Duration::minutes(30);
    }
    None
}

fn clock_text(at: NaiveDateTime) -> String {
    at.format("%-I:%M %p").to_string()
}

fn within_operating_hours(data: &TunnelData, at: NaiveDateTime) -> bool {
    let Some(hours) = record_at(data, at) else {
        return false;
    };
    match (
        NaiveTime::parse_from_str(&hours.opens, "%H:%M"),
        NaiveTime::parse_from_str(&hours.closes, "%H:%M"),
    ) {
        (Ok(open), Ok(close)) => at.time() >= open && at.time() < close,
        _ => false,
    }
}

/// Speak a wait in minutes below an hour and in hours and minutes above it.
pub fn wait_text(minutes: i64) -> String {
    let unit = |n: i64, word: &str| {
        if n == 1 {
            format!("{n} {word}")
        } else {
            format!("{n} {word}s")
        }
    };
    if minutes < 60 {
        return unit(minutes, "minute");
    }
    let (h, m) = (minutes / 60, minutes % 60);
    if m == 0 {
        unit(h, "hour")
    } else {
        format!("{} {}", unit(h, "hour"), unit(m, "minute"))
    }
}

pub fn gate_decision(
    data: &TunnelData,
    at: NaiveDateTime,
    direction: TunnelDirection,
) -> TunnelDecision {
    if record_at(data, at).is_none() {
        return TunnelDecision::HoursNotPublished {
            spoken: data.hours_not_published_text.clone(),
        };
    }
    if opens_for(data, at, direction) {
        return TunnelDecision::Cross;
    }
    let Some(next) = next_opening(data, at, direction) else {
        return TunnelDecision::HoursNotPublished {
            spoken: data.hours_not_published_text.clone(),
        };
    };
    let minutes = (next - at).num_minutes();
    if next.date() != at.date() || !within_operating_hours(data, at) {
        return TunnelDecision::Closed {
            minutes,
            spoken: format!(
                "The tunnel is closed for the night. The next opening is at {}.",
                clock_text(next)
            ),
        };
    }
    let target = match direction {
        TunnelDirection::ToWhittier => "Whittier",
        TunnelDirection::FromWhittier => "the staging area",
    };
    TunnelDecision::Wait {
        minutes,
        spoken: format!(
            "Next opening toward {target} at {}. You wait about {}.",
            clock_text(next),
            wait_text(minutes)
        ),
    }
}

/// Translate the career calendar into a dated schedule lookup.  Tunnel
/// schedules are published for the 2026 season, while the career calendar is
/// cyclic, so retain the game's month/day and use the published season year.
pub fn career_datetime(
    career_hours: Option<f64>,
    start_hour: f64,
    game_minutes: f64,
) -> NaiveDateTime {
    let hours = career_hours.unwrap_or(0.0) + game_minutes / 60.0;
    let day = crate::sim::season::day_of_year(hours).floor() as u32 + 1;
    let date = NaiveDate::from_yo_opt(2026, day.min(365)).expect("valid calendar day");
    let minute = ((start_hour + game_minutes / 60.0).rem_euclid(24.0) * 60.0).floor() as u32;
    date.and_hms_opt(minute / 60, minute % 60, 0)
        .expect("valid clock time")
}

/// A short gate wait in the staging line is duty time.  A closure for the
/// night is logged as sleeper-berth time; a wait of ten hours or more
/// completes the 10-hour reset.  Overnight staging parking is unverified, so
/// the log is a modelling choice recorded in the roadmap.
pub fn log_wait_to_hos(clock: &mut HosClock, wait_minutes: i64, closed: bool) {
    if wait_minutes <= 0 {
        return;
    }
    if closed {
        clock.sleeper(wait_minutes as f64);
    } else {
        clock.on_duty(wait_minutes as f64);
    }
}

/// Placarding and regulated weight for the load on the truck.  Chemicals of
/// any weight are hazardous only by weight, so over 400 lb count as placarded.
pub fn hazmat_for_cargo(cargo_key: &str, cargo_lb: u32, truck_placarded: bool) -> (bool, u32) {
    let regulated = matches!(cargo_key, "hazardous" | "fuel_bulk" | "chemicals");
    let lb = if regulated { cargo_lb } else { 0 };
    let placarded = truck_placarded || (cargo_key == "chemicals" && lb > 400);
    (placarded, lb)
}

impl Trip {
    /// Process a controlled tunnel at its staging-end boundary.  The gate is
    /// part of the route, not a UI prompt: it advances the game clock and
    /// reports through ordinary trip events, so headless drives and the live
    /// driving screen hear the exact same result.
    pub fn process_tunnel_gate(&mut self, leg_index: usize) -> bool {
        if self.processed_tunnel_gates.contains(&leg_index) {
            return self.refused_tunnel_gates.contains(&leg_index);
        }
        let Some(leg) = self.route.legs.get(leg_index) else {
            return false;
        };
        let Some(data) = leg.corridor().tunnel.clone() else {
            return false;
        };
        let leg_from = leg.a.clone();
        self.processed_tunnel_gates.insert(leg_index);
        self.emit(
            TripEventKind::GpsCue,
            SpokenMessage::new(data.planning_text.clone()),
            TripEventData::default(),
        );
        let cargo_lb = (self.truck.cargo_kg / KG_PER_LB).round().max(0.0) as u32;
        let (placarded_hazmat, hazmat_lb) = hazmat_for_cargo(
            self.truck.cargo_key.as_str(),
            cargo_lb,
            self.truck.placarded_hazmat,
        );
        let rig = RigForTunnel {
            length_ft: if self.truck.trailer_attached {
                self.truck.rig_length_ft
            } else {
                crate::sim::cross_traffic::TRACTOR_LENGTH_FT
            },
            width_ft: self.truck.rig_width_ft,
            height_ft: self.truck.rig_height_ft,
            placarded_hazmat,
            hazmat_lb,
        };
        if let Some(spoken) = refusal(&data, rig) {
            self.refused_tunnel_gates.insert(leg_index);
            self.emit(
                TripEventKind::GpsCue,
                SpokenMessage::new(spoken),
                TripEventData::default(),
            );
            return true;
        }
        let forward = self.route.cities.get(leg_index) == Some(&leg_from);
        let direction = if forward {
            TunnelDirection::ToWhittier
        } else {
            TunnelDirection::FromWhittier
        };
        match gate_decision(
            &data,
            career_datetime(self.career_hours, self.start_hour, self.game_minutes),
            direction,
        ) {
            TunnelDecision::Cross => false,
            TunnelDecision::HoursNotPublished { spoken } => {
                self.refused_tunnel_gates.insert(leg_index);
                self.emit(
                    TripEventKind::GpsCue,
                    SpokenMessage::new(spoken),
                    TripEventData::default(),
                );
                true
            }
            TunnelDecision::Wait { minutes, spoken } => {
                self.game_minutes += minutes as f64;
                self.emit(
                    TripEventKind::GpsCue,
                    SpokenMessage::new(spoken),
                    TripEventData {
                        amount: Some(minutes as f64),
                        context: Some("tunnel_wait".to_string()),
                        ..Default::default()
                    },
                );
                false
            }
            TunnelDecision::Closed { minutes, spoken } => {
                self.game_minutes += minutes as f64;
                self.emit(
                    TripEventKind::GpsCue,
                    SpokenMessage::new(spoken),
                    TripEventData {
                        amount: Some(minutes as f64),
                        context: Some("tunnel_closed".to_string()),
                        ..Default::default()
                    },
                );
                false
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn data() -> TunnelData {
        serde_json::from_str(r#"{"source_url":"x","access_date":"2026-10-09","planning_text":"p","toll_text":"t","closed_text":"c","hours_not_published_text":"Hours not published","hours":[{"valid_from":"2026-05-01","valid_to":"2026-09-30","opens":"05:30","closes":"23:15","source_url":"x","access_date":"2026-10-09"}],"schedule":{"opening_minutes":15,"interval_minutes":30,"source_url":"x","access_date":"2026-10-09"},"limits":{"length_ft":75,"width_ft":11,"normal_width_ft":10,"height_ft":15,"normal_height_ft":14,"placarded_hazmat_banned":true,"non_placarded_hazmat_lb":400,"source_url":"x","access_date":"2026-10-09","length_text":"The tunnel limit is 75 feet. Your rig is {n} feet.","width_text":"Over 10 feet wide needs a permit.","height_text":"Over 14 feet high needs a permit.","placarded_text":"Placarded hazardous materials cannot go through the tunnel. They move by Alaska Railroad.","non_placarded_text":"Non-placarded hazardous materials are limited to 400 pounds."},"speed_mph":25,"length_mi":2.5,"speed_source_url":"x","speed_access_date":"2026-10-09","length_source_url":"x","length_access_date":"2026-10-09"}"#).unwrap()
    }
    #[test]
    fn schedule_edges_and_refusals() {
        let d = data();
        let t = NaiveDateTime::parse_from_str("2026-05-01 05:35", "%F %R").unwrap();
        assert_eq!(
            gate_decision(&d, t, TunnelDirection::ToWhittier),
            TunnelDecision::Cross
        );
        let edge = NaiveDateTime::parse_from_str("2026-05-01 05:45", "%F %R").unwrap();
        assert!(matches!(
            gate_decision(&d, edge, TunnelDirection::ToWhittier),
            TunnelDecision::Wait { .. }
        ));
        assert!(refusal(
            &d,
            RigForTunnel {
                length_ft: 75.1,
                width_ft: 8.5,
                height_ft: 13.5,
                placarded_hazmat: false,
                hazmat_lb: 0
            }
        )
        .unwrap()
        .contains("75.1"));
        assert!(refusal(
            &d,
            RigForTunnel {
                length_ft: 75.,
                width_ft: 8.5,
                height_ft: 13.5,
                placarded_hazmat: false,
                hazmat_lb: 400
            }
        )
        .is_none());
    }
    #[test]
    fn hours_and_hos_are_accounted() {
        let mut d = data();
        d.hours.push(crate::data::world_models::TunnelHours {
            valid_from: "2026-10-01".into(),
            valid_to: "2027-04-30".into(),
            opens: "07:00".into(),
            closes: "22:45".into(),
            source_url: "x".into(),
            access_date: "2026-10-09".into(),
        });
        let may = NaiveDateTime::parse_from_str("2026-05-01 05:30", "%F %R").unwrap();
        let oct = NaiveDateTime::parse_from_str("2026-10-01 07:00", "%F %R").unwrap();
        assert_eq!(
            gate_decision(&d, may, TunnelDirection::ToWhittier),
            TunnelDecision::Cross
        );
        assert_eq!(
            gate_decision(&d, oct, TunnelDirection::FromWhittier),
            TunnelDecision::Cross
        );
        let outside = NaiveDateTime::parse_from_str("2027-05-01 07:00", "%F %R").unwrap();
        assert!(matches!(
            gate_decision(&d, outside, TunnelDirection::FromWhittier),
            TunnelDecision::HoursNotPublished { .. }
        ));
        let mut hos = HosClock::new();
        log_wait_to_hos(&mut hos, 22, false);
        hos.drive(d.length_mi / d.speed_mph * 60.0);
        assert_eq!(hos.status, "driving");
        assert!(hos.driving_min > 5.9 && hos.driving_min < 6.1);
        assert!(hos.duty_min > 27.9 && hos.duty_min < 28.1);
    }
    #[test]
    fn missing_hours_or_source_fails_validation() {
        let mut d = data();
        d.hours.clear();
        assert!(d.validate("test").is_err());
        let mut d = data();
        d.limits.source_url.clear();
        assert!(d.validate("test").is_err());
    }
    fn at(s: &str) -> NaiveDateTime {
        NaiveDateTime::parse_from_str(s, "%F %R").unwrap()
    }
    fn wait_of(d: &TunnelDecision) -> i64 {
        match d {
            TunnelDecision::Wait { minutes, .. } | TunnelDecision::Closed { minutes, .. } => {
                *minutes
            }
            other => panic!("expected a wait, got {other:?}"),
        }
    }
    #[test]
    fn next_opening_uses_the_half_hour_mark() {
        // Official summer table: Bear Valley to Whittier opens at :30,
        // Whittier to Bear Valley at :00.
        let d = data();
        let to = TunnelDirection::ToWhittier;
        let from = TunnelDirection::FromWhittier;
        assert_eq!(wait_of(&gate_decision(&d, at("2026-06-01 10:10"), to)), 20);
        assert_eq!(wait_of(&gate_decision(&d, at("2026-06-01 10:20"), to)), 10);
        // :10 is inside the away-from-Whittier opening that starts at :00.
        assert_eq!(
            gate_decision(&d, at("2026-06-01 10:10"), from),
            TunnelDecision::Cross
        );
        assert_eq!(
            wait_of(&gate_decision(&d, at("2026-06-01 10:20"), from)),
            40
        );
        // :40 is inside the toward-Whittier opening that starts at :30.
        assert_eq!(
            gate_decision(&d, at("2026-06-01 10:40"), to),
            TunnelDecision::Cross
        );
        assert_eq!(wait_of(&gate_decision(&d, at("2026-06-01 10:50"), to)), 40);
        assert_eq!(
            wait_of(&gate_decision(&d, at("2026-06-01 10:40"), from)),
            20
        );
        assert_eq!(wait_of(&gate_decision(&d, at("2026-06-01 05:20"), to)), 10);
        assert_eq!(wait_of(&gate_decision(&d, at("2026-06-01 06:05"), to)), 25);
        assert_eq!(wait_of(&gate_decision(&d, at("2026-06-01 06:29"), to)), 1);
        match gate_decision(&d, at("2026-06-01 10:20"), to) {
            TunnelDecision::Wait { spoken, .. } => assert_eq!(
                spoken,
                "Next opening toward Whittier at 10:30 AM. You wait about 10 minutes."
            ),
            other => panic!("{other:?}"),
        }
    }
    #[test]
    fn night_arrivals_are_closed_not_long_waits() {
        let d = data();
        for t in ["2026-06-01 23:15", "2026-06-02 00:30", "2026-06-02 03:00"] {
            match gate_decision(&d, at(t), TunnelDirection::ToWhittier) {
                TunnelDecision::Closed { spoken, .. } => assert_eq!(
                    spoken,
                    "The tunnel is closed for the night. The next opening is at 5:30 AM."
                ),
                other => panic!("{t}: {other:?}"),
            }
        }
        assert_eq!(wait_text(45), "45 minutes");
        assert_eq!(wait_text(60), "1 hour");
        assert_eq!(wait_text(150), "2 hours 30 minutes");
    }
    #[test]
    fn overnight_closure_is_sleeper_and_short_waits_are_duty() {
        let d = data();
        let decision = gate_decision(&d, at("2026-06-01 23:15"), TunnelDirection::ToWhittier);
        let TunnelDecision::Closed { minutes, .. } = decision else {
            panic!("expected closed");
        };
        assert_eq!(minutes, 375);
        let mut hos = HosClock::new();
        log_wait_to_hos(&mut hos, minutes, true);
        assert!(hos
            .history
            .iter()
            .any(|e| e.status == "sleeper_berth" && (e.minutes - 375.0).abs() < 0.1));
        assert!(!hos
            .history
            .iter()
            .any(|e| e.status == "on_duty_not_driving"));
        let mut short = HosClock::new();
        log_wait_to_hos(&mut short, 20, false);
        assert_eq!(short.status, "on_duty_not_driving");
        let mut long = HosClock::new();
        long.drive(300.0);
        log_wait_to_hos(&mut long, 650, true);
        assert_eq!(long.driving_min, 0.0);
    }
    #[test]
    fn chemicals_over_400_lb_are_placarded() {
        let d = data();
        let (placarded, lb) = hazmat_for_cargo("chemicals", 40_000, false);
        let rig = RigForTunnel {
            length_ft: 73.5,
            width_ft: 8.5,
            height_ft: 13.5,
            placarded_hazmat: placarded,
            hazmat_lb: lb,
        };
        assert_eq!(
            refusal(&d, rig).as_deref(),
            Some("Placarded hazardous materials cannot go through the tunnel. They move by Alaska Railroad.")
        );
        let (placarded, lb) = hazmat_for_cargo("chemicals", 400, false);
        assert!(!placarded);
        assert_eq!(lb, 400);
        assert!(hazmat_for_cargo("chemicals", 0, true).0);
    }
    #[test]
    fn height_refusal_reads_as_a_permit() {
        let d = data();
        let rig = RigForTunnel {
            length_ft: 70.0,
            width_ft: 8.5,
            height_ft: 14.5,
            placarded_hazmat: false,
            hazmat_lb: 0,
        };
        assert_eq!(
            refusal(&d, rig).as_deref(),
            Some("Over 14 feet high needs a permit.")
        );
    }
}
