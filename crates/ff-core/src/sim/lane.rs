//! Lane model for the 1-D driving view: a discrete lane index plus a
//! continuous position within the current lane.
//!
//! `lane` counts from the rightmost driving lane (0) leftward; a rural
//! two-lane interstate is lanes 0 (right) and 1 (left). `offset` is centered
//! at 0.0 within the current lane. Absolute 1.0 means the tires are touching
//! the lane line, and larger values mean the truck is leaving the lane: across
//! a line with a neighboring lane that becomes a lane change, across the
//! outside edge it becomes the shoulder or the median.
//!
//! Port of `freight_fate/sim/lane.py`.

use crate::pyrandom::PyRandom;

pub const MPH_PER_MPS: f64 = 2.23694;

/// Mirrors `settings.LANE_KEEPING_MODES`: how much lane-holding the truck
/// does. "full" holds the lane outright, so no drift model runs at all.
pub const ASSIST_LEVELS: [&str; 3] = ["full", "partial", "off"];
pub const LANE_EDGE: f64 = 1.0;
pub const LANE_WIDTH: f64 = 2.0; // offset units from one lane center to the next
pub const CROSS_AT: f64 = 1.12; // straddling the line this far commits the lane change
pub const OFF_ROAD: f64 = 1.3;
pub const MAX_OFFSET: f64 = 1.5;
pub const RUMBLE_START: f64 = 0.85;
pub const RUMBLE_FULL: f64 = 1.15;
/// Inside this offset the truck is truthfully centered, matching
/// [`LaneKeeping::describe`].
pub const CENTERED_MAX: f64 = 0.25;
pub const OFF_ROAD_GRACE_S: f64 = 2.0;
pub const OFF_ROAD_REPEAT_S: f64 = 3.0;
pub const WANDER_RATE: f64 = 0.05;
pub const CURVE_RATE: f64 = 0.12;
pub const WIND_RATE: f64 = 0.10;
pub const STEER_RATE: f64 = 0.55;

/// Only the modes where the driver does the lane work have a drift model.
/// "full" is absent on purpose: it pins the offset to lane centre.
/// `(drift multiplier, steer multiplier)`.
pub fn assist_tuning(assist: &str) -> Option<(f64, f64)> {
    match assist {
        "partial" => Some((0.45, 1.35)),
        "off" => Some((1.0, 1.0)),
        _ => None,
    }
}

pub const DEFAULT_LANE_COUNT: i64 = 2;

/// Spoken name for a lane index: right, left, or middle.
///
/// A single-lane road has no sides to name. Calling it "the right lane"
/// invites the driver to wonder what is in the left one when there is no
/// left one (Cary, 2026-08-15), so it answers to the road itself. Callers
/// that build "the {label} lane" get "the single lane"; the readouts that
/// want a bare noun use [`lane_phrase`] below.
pub fn lane_label(index: i64, count: i64) -> &'static str {
    if count <= 1 {
        return "single";
    }
    if index <= 0 {
        return "right";
    }
    if index >= count - 1 {
        return "left";
    }
    "middle"
}

/// How a readout names the lane the truck is in, article included.
///
/// "In the right lane" reads naturally; "In the single lane" does not, so
/// a one-lane road simply says "In the lane".
pub fn lane_phrase(index: i64, count: i64) -> String {
    if count <= 1 {
        return "the lane".to_string();
    }
    format!("the {} lane", lane_label(index, count))
}

/// Small deterministic lane simulation for audio-only steering cues.
#[derive(Debug, Clone)]
pub struct LaneKeeping {
    rng: PyRandom,
    pub offset: f64,
    pub steering: f64,
    pub lane: i64, // everyone starts in the right lane
    pub lane_count: i64,
    pub crossed: i64, // last update's lane change: +1 left, -1 right
    wander: f64,
    wander_target: f64,
    wander_timer: f64,
    gust: f64,
    gust_target: f64,
    gust_timer: f64,
    off_road_timer: f64,
    event_cooldown: f64,
}

impl Default for LaneKeeping {
    fn default() -> Self {
        Self::new(None)
    }
}

impl LaneKeeping {
    /// `LaneKeeping(seed)`: `None` draws from entropy, as `random.Random()` did.
    pub fn new(seed: Option<i64>) -> Self {
        let rng = match seed {
            Some(seed) => PyRandom::new_from_i64(seed),
            None => PyRandom::new_unseeded(),
        };
        Self {
            rng,
            offset: 0.0,
            steering: 0.0,
            lane: 0,
            lane_count: DEFAULT_LANE_COUNT,
            crossed: 0,
            wander: 0.0,
            wander_target: 0.0,
            wander_timer: 0.0,
            gust: 0.0,
            gust_target: 0.0,
            gust_timer: 0.0,
            off_road_timer: 0.0,
            event_cooldown: 0.0,
        }
    }

    pub fn lane_name(&self) -> &'static str {
        lane_label(self.lane, self.lane_count)
    }

    pub fn set_lane_count(&mut self, count: i64) {
        self.lane_count = count.max(1);
        self.lane = self.lane.min(self.lane_count - 1);
    }

    /// How far past center toward a road *edge* -- a side with no
    /// neighboring lane. Drifting toward another lane never rumbles; the
    /// rumble strip lives on the shoulder and the median.
    fn edge_excursion_inner(&self) -> f64 {
        if self.offset > 0.0 && self.lane == 0 {
            return self.offset;
        }
        if self.offset < 0.0 && self.lane >= self.lane_count - 1 {
            return -self.offset;
        }
        0.0
    }

    /// Advance the lane model.
    ///
    /// Returns true when the truck has been off the road edge long enough to
    /// fire a warning/damage event. A completed drift across an interior lane
    /// line is reported through `crossed` (+1 moved left, -1 moved right)
    /// for the frame it happens. `assist == "full"` is lane keeping doing the
    /// whole job: the truck stays centered and no drift accrues. The discrete
    /// `lane` is still honored there, driven by tap-to-change controls.
    pub fn update(&mut self, dt: f64, speed_mps: f64, curve: f64, wind: f64, assist: &str) -> bool {
        self.crossed = 0;
        let Some((drift_mult, steer_mult)) = assist_tuning(assist) else {
            self.offset = 0.0;
            self.off_road_timer = 0.0;
            return false;
        };

        let mph = speed_mps * MPH_PER_MPS;
        if mph < 2.0 {
            self.off_road_timer = 0.0;
            return false;
        }
        let speed_factor = (mph / 55.0).min(1.2);

        self.wander_timer -= dt;
        if self.wander_timer <= 0.0 {
            self.wander_timer = self.rng.uniform(10.0, 25.0);
            self.wander_target = self.rng.uniform(-1.0, 1.0) * WANDER_RATE;
        }
        self.wander += (self.wander_target - self.wander) * (dt / 3.0).min(1.0);

        self.gust_timer -= dt;
        if self.gust_timer <= 0.0 {
            self.gust_timer = self.rng.uniform(3.0, 8.0);
            self.gust_target = self.rng.uniform(-1.0, 1.0);
        }
        self.gust += (self.gust_target - self.gust) * (dt / 1.5).min(1.0);

        let drift = (self.wander + curve * CURVE_RATE + wind * self.gust * WIND_RATE)
            * drift_mult
            * speed_factor;
        let authority = STEER_RATE * steer_mult * (mph / 25.0).min(1.0);
        self.offset += (drift + self.steering * authority) * dt;

        // Straddle an interior line far enough and the truck is in the next
        // lane over: re-center the offset relative to the new lane so the
        // player finishes the change by straightening out.
        if self.offset <= -CROSS_AT && self.lane < self.lane_count - 1 {
            self.lane += 1;
            self.offset += LANE_WIDTH;
            self.crossed = 1;
        } else if self.offset >= CROSS_AT && self.lane > 0 {
            self.lane -= 1;
            self.offset -= LANE_WIDTH;
            self.crossed = -1;
        }
        self.offset = self.offset.clamp(-MAX_OFFSET, MAX_OFFSET);

        self.event_cooldown = (self.event_cooldown - dt).max(0.0);
        if self.edge_excursion_inner() >= OFF_ROAD {
            self.off_road_timer += dt;
            if self.off_road_timer >= OFF_ROAD_GRACE_S && self.event_cooldown <= 0.0 {
                self.event_cooldown = OFF_ROAD_REPEAT_S;
                return true;
            }
        } else {
            self.off_road_timer = 0.0;
        }
        false
    }

    /// 0..1 rumble-strip cue level at the road edge (shoulder or median).
    pub fn rumble_level(&self) -> f64 {
        ((self.edge_excursion_inner() - RUMBLE_START) / (RUMBLE_FULL - RUMBLE_START))
            .clamp(0.0, 1.0)
    }

    /// Public read of how far past center toward a true road edge.
    pub fn edge_excursion(&self) -> f64 {
        self.edge_excursion_inner()
    }

    pub fn describe(&self) -> String {
        let lane_part = format!("In {}", lane_phrase(self.lane, self.lane_count));
        let side = if self.offset < 0.0 { "left" } else { "right" };
        let away = self.offset.abs();
        if away < CENTERED_MAX {
            return format!("{lane_part}, centered.");
        }
        if away < 0.7 {
            return format!("{lane_part}, drifting {side}.");
        }
        if self.edge_excursion_inner() >= OFF_ROAD {
            return format!("Off the road on the {side}!");
        }
        if away < CROSS_AT {
            return format!("{lane_part}, at the {side} edge of the lane.");
        }
        format!("{lane_part}, crossing the {side} lane line.")
    }
}

#[cfg(test)]
mod tests {
    //! Ported from `tests/test_lane_keeping.py` (the Settings-backed cases
    //! belong to the settings port) and the `LaneKeeping` section of
    //! `tests/test_lane_discrete.py` (the DrivingState cases belong to the
    //! app-shell bucket).
    use super::*;

    fn run_lane(lane: &mut LaneKeeping, seconds: f64, curve: f64, wind: f64, assist: &str) -> i64 {
        let dt = 0.1;
        let mut events = 0;
        for _ in 0..((seconds / dt) as i64) {
            if lane.update(dt, 29.0, curve, wind, assist) {
                events += 1;
            }
        }
        events
    }

    #[test]
    fn test_full_lane_keeping_preserves_centered_lane() {
        let mut lane = LaneKeeping::new(Some(1));
        lane.offset = 0.9;
        assert_eq!(run_lane(&mut lane, 30.0, 1.0, 1.0, "full"), 0);
        assert_eq!(lane.offset, 0.0);
    }

    #[test]
    fn test_drift_and_steering_correction() {
        let mut lane = LaneKeeping::new(Some(7));
        run_lane(&mut lane, 12.0, 1.0, 0.0, "off");
        assert!(lane.offset.abs() > 0.4);
        for _ in 0..100 {
            lane.steering = (-lane.offset * 2.0).clamp(-1.0, 1.0);
            lane.update(0.1, 29.0, 0.0, 0.0, "off");
        }
        assert!(lane.offset.abs() < 0.25);
    }

    #[test]
    fn test_off_road_event_repeats_after_grace() {
        let mut lane = LaneKeeping::new(Some(1));
        let fired = run_lane(&mut lane, 40.0, 1.0, 0.0, "off");
        assert!(lane.offset.abs() >= OFF_ROAD);
        assert!(lane.offset.abs() <= MAX_OFFSET);
        assert!(fired >= 2);
    }

    // -- LaneKeeping: the discrete layer under the drift model (test_lane_discrete.py)

    #[test]
    fn test_lane_labels() {
        assert_eq!(lane_label(0, 2), "right");
        assert_eq!(lane_label(1, 2), "left");
        assert_eq!(lane_label(1, 3), "middle");
        assert_eq!(lane_label(2, 3), "left");
    }

    #[test]
    fn test_steering_across_the_line_changes_lanes() {
        let mut lane = LaneKeeping::new(Some(3));
        lane.steering = -1.0; // hold left
        let mut crossed = 0;
        for _ in 0..200 {
            lane.update(0.1, 29.0, 0.0, 0.0, "off");
            if lane.crossed != 0 {
                crossed = lane.crossed;
                break;
            }
        }
        assert_eq!(crossed, 1);
        assert_eq!(lane.lane, 1);
        // Entered the new lane from its right side, still drifting across it.
        assert!(lane.offset > 0.0);
    }

    #[test]
    fn test_no_lane_to_the_left_means_the_median() {
        let mut lane = LaneKeeping::new(Some(3));
        lane.lane = 1; // already in the left lane
        lane.steering = -1.0;
        let mut fired = false;
        for _ in 0..400 {
            if lane.update(0.1, 29.0, 0.0, 0.0, "off") {
                fired = true;
                break;
            }
        }
        assert!(fired); // off-road event, not a lane change
        assert_eq!(lane.lane, 1);
        assert_eq!(lane.crossed, 0);
    }

    #[test]
    fn test_interior_lane_line_does_not_rumble() {
        let mut lane = LaneKeeping::new(Some(1));
        lane.offset = -1.0; // straddling the line toward the left lane
        assert_eq!(lane.rumble_level(), 0.0);
        lane.offset = 1.0; // drifting onto the shoulder
        assert!(lane.rumble_level() > 0.0);
        assert!(lane_label(1, 2).contains("left"));
    }

    #[test]
    fn test_describe_names_the_lane() {
        let mut lane = LaneKeeping::new(Some(1));
        assert_eq!(lane.describe(), "In the right lane, centered.");
        lane.lane = 1;
        lane.offset = -0.5;
        assert_eq!(lane.describe(), "In the left lane, drifting left.");
    }

    #[test]
    fn test_a_single_lane_road_has_no_side_to_name() {
        // "The right lane" on a one-lane road invites the driver to wonder what
        // is in the left one, when there is no left one (Cary, 2026-08-15).
        let mut lane = LaneKeeping::new(Some(1));
        lane.set_lane_count(1);
        lane.offset = 0.0;
        assert_eq!(lane.describe(), "In the lane, centered.");
        lane.offset = -0.5;
        assert_eq!(lane.describe(), "In the lane, drifting left.");
        assert_eq!(lane_phrase(0, 1), "the lane");
        // Two lanes and up still name the side, which is the whole point there.
        assert_eq!(lane_phrase(0, 2), "the right lane");
    }

    #[test]
    fn test_set_lane_count_clamps_the_lane() {
        let mut lane = LaneKeeping::new(Some(1));
        lane.lane = 1;
        lane.set_lane_count(1);
        assert_eq!(lane.lane, 0);
        const { assert!(CROSS_AT > 1.0) }; // crossing requires actually straddling the line
    }

    #[test]
    fn test_describe_reads_edges_and_crossings() {
        let mut lane = LaneKeeping::new(Some(1));
        lane.offset = 0.9;
        assert_eq!(
            lane.describe(),
            "In the right lane, at the right edge of the lane."
        );
        lane.offset = 1.4;
        assert_eq!(lane.describe(), "Off the road on the right!");
        lane.offset = -1.2;
        assert_eq!(
            lane.describe(),
            "In the right lane, crossing the left lane line."
        );
    }
}
