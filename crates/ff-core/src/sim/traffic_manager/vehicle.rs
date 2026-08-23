//! The bubble's vehicles and the situations they raise (the data half of
//! `freight_fate/sim/traffic_manager.py`).

use crate::sim::trip_models::NPCVehicle;
use crate::speech_text::SpokenMessage;

/// One NPC in the traffic bubble.
///
/// `lane` is the absolute lane index (0 = right lane, counting leftward),
/// matching the player's `LaneKeeping.lane`. `relative_lane` keeps the
/// legacy spoken-text surface (negative = left of the player) and is
/// recomputed against the player's lane every manager update.
#[derive(Debug, Clone, PartialEq)]
pub struct TrafficVehicle {
    pub key: String,
    pub position_mi: f64,
    pub speed_mph: f64,
    pub target_speed_mph: f64,
    pub relative_lane: i64,
    pub intent: String,
    pub vehicle_class: String,
    pub length_mi: f64,
    pub lane: i64,
    /// The route mile this vehicle leaves the highway at, for bubble
    /// traffic: without it a slower vehicle ahead was permanent.
    pub exit_at_mi: Option<f64>,
}

impl TrafficVehicle {
    pub fn new(
        key: &str,
        position_mi: f64,
        speed_mph: f64,
        target_speed_mph: f64,
        relative_lane: i64,
        intent: &str,
        vehicle_class: &str,
    ) -> Self {
        TrafficVehicle {
            key: key.to_string(),
            position_mi,
            speed_mph,
            target_speed_mph,
            relative_lane,
            intent: intent.to_string(),
            vehicle_class: vehicle_class.to_string(),
            length_mi: 0.25,
            lane: 0,
            exit_at_mi: None,
        }
    }

    pub fn with_lane(mut self, lane: i64) -> Self {
        self.lane = lane;
        self
    }

    pub fn with_exit_at(mut self, exit_at_mi: Option<f64>) -> Self {
        self.exit_at_mi = exit_at_mi;
        self
    }

    pub fn at_mi(&self) -> f64 {
        self.position_mi
    }

    pub fn end_mi(&self) -> f64 {
        self.position_mi + self.length_mi
    }

    pub fn lane_text(&self) -> &'static str {
        if self.relative_lane < 0 {
            "left lane"
        } else if self.relative_lane > 0 {
            "right lane"
        } else {
            "your lane"
        }
    }

    /// The legacy NPC behavior name for this intent.
    pub fn behavior(&self) -> String {
        match self.intent.as_str() {
            "cruising" => "steady_truck",
            "following" => "slow_car",
            "merging" => "merging_vehicle",
            "braking" => "braking_traffic",
            "passing" => "passing_vehicle",
            "patrolling" => "marked_unit",
            other => other,
        }
        .to_string()
    }

    pub fn reason(&self) -> &'static str {
        if self.vehicle_class == "state trooper" {
            return "state trooper ahead";
        }
        match self.intent.as_str() {
            "cruising" => "steady truck traffic",
            "following" => "slow car ahead",
            "merging" => "merging traffic",
            "braking" => "brake lights ahead",
            "passing" => "passing traffic",
            "patrolling" => "marked unit ahead",
            _ => "traffic ahead",
        }
    }
}

impl From<NPCVehicle> for TrafficVehicle {
    /// The trip's legacy `NPCVehicle` on the bubble's runtime surface: the
    /// behavior maps back to an intent and there is no exit mile to read.
    fn from(npc: NPCVehicle) -> Self {
        TrafficVehicle {
            key: npc.key.clone(),
            position_mi: npc.position_mi,
            speed_mph: npc.speed_mph,
            target_speed_mph: npc.target_speed_mph,
            relative_lane: npc.relative_lane,
            intent: npc.intent().to_string(),
            vehicle_class: "vehicle".to_string(),
            length_mi: npc.length_mi,
            lane: npc.lane,
            exit_at_mi: None,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct TrafficSituation {
    pub kind: String,
    pub vehicle: TrafficVehicle,
    pub message: SpokenMessage,
    pub interrupt: bool,
}

/// Why traffic is braking, said in the driver's words, keyed by the Zone
/// reason the trip stamped on that mile. Empty for anything not mile-mapped:
/// phantom waves are real, and an invented crash would be worse than silence
/// (Brandon, 2026-08-20).
pub fn braking_cause_line(reason: &str) -> &'static str {
    BRAKING_CAUSE_LINES
        .iter()
        .find(|(key, _)| *key == reason)
        .map(|(_, line)| *line)
        .unwrap_or("")
}

/// The table [`braking_cause_line`] reads, as the Python `BRAKING_CAUSE_LINES`
/// dict is. A table rather than `match` arms so the KEYS can be enumerated:
/// the adversarial battery checks both directions against the real Zone
/// reasons -- a generated reason with no line here loses its explanation
/// silently, and a key here that no zone ever stamps is dead vocabulary that
/// looks like coverage. Neither direction is checkable against arms.
pub static BRAKING_CAUSE_LINES: &[(&str, &str)] = &[
    ("construction", "Road work is the cause."),
    ("construction merge", "Road work is the cause."),
    ("heavy traffic", "Traffic is backing up ahead."),
];

/// A (start, end, reason, pace) span where traffic has a reason to be on the
/// brakes, handed over by the trip. The Python tuples came in two-, three-
/// and four-element shapes; the missing slots read as no reason / no pace.
#[derive(Debug, Clone, PartialEq)]
pub struct BrakingZone {
    pub start_mi: f64,
    pub end_mi: f64,
    pub reason: String,
    pub pace_mph: Option<f64>,
}

impl BrakingZone {
    pub fn new(start_mi: f64, end_mi: f64, reason: &str, pace_mph: Option<f64>) -> Self {
        BrakingZone {
            start_mi,
            end_mi,
            reason: reason.to_string(),
            pace_mph,
        }
    }

    pub fn span(start_mi: f64, end_mi: f64) -> Self {
        BrakingZone::new(start_mi, end_mi, "", None)
    }
}
