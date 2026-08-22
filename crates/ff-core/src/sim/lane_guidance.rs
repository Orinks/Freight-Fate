//! Lane-guidance director: pans the EXISTING road bed toward the steer.
//!
//! Pure logic, no audio calls -- the driving state feeds it the lane model and
//! the curve context each frame and applies the pan it returns to the road
//! noise loop. Keeping it a plain object keeps the cue logic testable headless.
//!
//! The design is the community-resolved one on the roadmap (JaceK's audiogames
//! ruling, owner concurring, 2026-07-17), plus the owner's wake/sleep contract
//! (2026-07-27):
//!
//! - Silence-is-centered: on a straight, centered and stable, guidance does
//!   nothing at all -- the road bed sits where it always sits.
//! - NO new steering tones, ever: continuous synthetic tones overwhelm the
//!   soundscape and hurt players with sensory or hearing issues. The guide is
//!   the EXISTING road/tire bed, panned along the arc.
//! - Pursuit, not error-nulling: the bed leans toward where the wheel should
//!   go -- follow the sound. In a bend it leads into the curve; in a drift it
//!   sits toward lane center. (Forza's audio steering guide panned
//!   engine+tires the same way; pursuit tracking beats error-nulling in the
//!   human-factors literature.)
//! - The guide wakes for exactly two reasons: drifting toward a lane line, or
//!   a curve inside its lead window (or underway). It slews home and sleeps
//!   on the straight.
//! - Drift cues stay underneath as the error backstop: the edge-boundary
//!   ladder (intermittent clip / periodic strip / aperiodic gravel) and the
//!   departure warnings, which grade by structure, not loudness.
//!
//! `boundary` names what is past the lane line on each side of the CURRENT
//! lane, so the edge sounds and spoken warnings can say the truth: `lane`
//! (another lane of same-direction traffic), `median` (a divided highway's
//! left edge), `oncoming` (an undivided road's centerline), or `shoulder`
//! (the right road edge).
//!
//! Port of `freight_fate/sim/lane_guidance.py`.

use super::lane::{LaneKeeping, LANE_EDGE, OFF_ROAD, RUMBLE_START};

/// The guide stays asleep inside this much of lane center: normal wander on a
/// straight never wakes it (WANDER_RATE drift stays well inside 0.35).
pub const DRIFT_WAKE: f64 = 0.45;
/// Hysteresis: once awake, sleep only after settling back inside this.
pub const DRIFT_SLEEP: f64 = 0.30;
/// A curve wakes the guide this many miles before its start.
pub const CURVE_LEAD_MI: f64 = 0.30;
/// The bed never pans fully into one ear: some road stays on both sides so
/// the soundscape keeps its floor under the guide.
pub const GUIDE_PAN_MAX: f64 = 0.8;
/// How fast the bed slews toward its target, pan units per second: quick
/// enough to lead a bend, slow enough to read as leaning, not jumping.
pub const PAN_SLEW_PER_S: f64 = 1.6;

// The edge-boundary ladder: three structural states (intermittent clip,
// periodic strip, aperiodic shoulder) so the rungs stay separable under
// engine and road noise. Offsets are lane-model units (see sim::lane).
pub const EDGE_CLIP_KEY: &str = "vehicle/edge_clip";
pub const EDGE_STRIP_KEY: &str = "vehicle/edge_strip";
pub const EDGE_SHOULDER_KEY: &str = "vehicle/edge_shoulder";
pub const EDGE_STRIP_AT: f64 = 1.0; // past this the whole tire is on the strip
pub const EDGE_VOLUME_MIN: f64 = 0.42;
pub const EDGE_VOLUME_MAX: f64 = 0.88;

/// The player picks how loud the lane and edge cues speak (owner call
/// 2026-07-27: the strip read too quiet on the first drive). Scales the
/// edge ladder, the lane locator, and the dead-man's-curve strips alike.
pub const CUE_LOUDNESS: [(&str, f64); 3] =
    [("subtle", 0.6), ("standard", 1.0), ("prominent", 1.35)];

/// `CUE_LOUDNESS[setting]`, or `None` for a value the table does not know.
pub fn cue_loudness(setting: &str) -> Option<f64> {
    CUE_LOUDNESS
        .iter()
        .find(|(name, _)| *name == setting)
        .map(|(_, level)| *level)
}

// Dead-man's-curve transverse strips: real DOTs cut grouped rumble bars
// ACROSS the lane ahead of curves that kill people. Hairpin class only --
// the wake-up means something because it is rare -- placed far enough up
// the road that braking after it still makes the curve.
pub const TRANSVERSE_KEY: &str = "vehicle/transverse_strips";
pub const HAIRPIN_ADVISORY_MPH: f64 = 25.0;
pub const STRIP_LEAD_MI: f64 = 0.25;

/// `(loop key, volume)` for a road-edge excursion, or `None` inside the lane.
///
/// `boundary` is what lies past this edge ([`classify_boundaries`]). The
/// gravel shoulder rung only exists where there IS gravel: past an
/// undivided centerline the pavement continues into the oncoming lane, so
/// the strip stays the outermost texture and the spoken warning carries
/// the danger.
pub fn edge_rung(excursion: f64, boundary: &str, loudness: f64) -> Option<(&'static str, f64)> {
    if excursion < RUMBLE_START {
        return None;
    }
    let span = (OFF_ROAD - RUMBLE_START).max(0.01);
    let level = ((excursion - RUMBLE_START) / span).min(1.0);
    let volume = EDGE_VOLUME_MIN + level * (EDGE_VOLUME_MAX - EDGE_VOLUME_MIN);
    let volume = (volume * loudness).min(1.0);
    if excursion >= OFF_ROAD && boundary != "oncoming" {
        return Some((EDGE_SHOULDER_KEY, (EDGE_VOLUME_MAX * loudness).min(1.0)));
    }
    if excursion >= EDGE_STRIP_AT {
        return Some((EDGE_STRIP_KEY, volume));
    }
    Some((EDGE_CLIP_KEY, volume))
}

/// `(left, right)` of the current lane: lane / median / oncoming / shoulder.
///
/// `divided` is the baked flag when the world has one; `None` falls back
/// to an honest inference: an interstate is divided by definition, and a
/// road with one lane per side is an undivided two-lane whose left line is
/// the centerline. The multilane middle ground defaults to divided until
/// the divided-flag bake (Track D2) says otherwise.
pub fn classify_boundaries(
    lane: i64,
    lane_count: i64,
    divided: Option<bool>,
    interstate: bool,
) -> (&'static str, &'static str) {
    let divided = divided.unwrap_or(interstate || lane_count >= 2);
    let mut left = if divided { "median" } else { "oncoming" };
    if lane < lane_count - 1 {
        left = "lane";
    }
    let right = if lane <= 0 { "shoulder" } else { "lane" };
    (left, right)
}

/// One frame of guidance output for the driving state to perform.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct GuidanceFrame {
    pub awake: bool,
    /// Road-bed pan, -1..1: the side the wheel should go toward.
    pub pan: f64,
    /// This frame ended a drift episode back at center.
    pub centered: bool,
}

/// Wake/sleep and pursuit-pan shaping. One instance per drive.
#[derive(Debug, Clone)]
pub struct LaneGuidance {
    awake: bool,
    episode_drifted: bool,
    /// Current slewed pan, applied to the road bed.
    pub pan: f64,
}

impl Default for LaneGuidance {
    fn default() -> Self {
        Self::new()
    }
}

impl LaneGuidance {
    pub fn new() -> Self {
        Self {
            awake: false,
            episode_drifted: false,
            pan: 0.0,
        }
    }

    pub fn awake(&self) -> bool {
        self.awake
    }

    /// Advance one frame.
    ///
    /// `curve_steer` is the signed steer the active bend asks for
    /// (-1 full left .. 1 full right, 0 when no bend is active);
    /// `curve_ahead_mi` is distance to the next curve's start (`None` when
    /// nothing is inside the lookahead).
    pub fn update(
        &mut self,
        lane: &LaneKeeping,
        dt: f64,
        assist_on: bool,
        curve_steer: f64,
        curve_ahead_mi: Option<f64>,
    ) -> GuidanceFrame {
        if !assist_on {
            self.awake = false;
            self.episode_drifted = false;
            self.pan = 0.0;
            return GuidanceFrame {
                awake: false,
                pan: 0.0,
                centered: false,
            };
        }

        let drift = lane.offset.abs();
        let in_curve_window =
            curve_steer != 0.0 || curve_ahead_mi.is_some_and(|mi| mi <= CURVE_LEAD_MI);
        let was_awake = self.awake;
        if self.awake {
            self.awake = in_curve_window || drift > DRIFT_SLEEP;
        } else {
            self.awake = in_curve_window || drift > DRIFT_WAKE;
        }
        if self.awake && drift > DRIFT_WAKE {
            self.episode_drifted = true;
        }

        // Pursuit target: lean into the bend, corrected toward lane center.
        // Asleep, the target is home -- the bed slews back where it lives.
        let target = if self.awake {
            (curve_steer - lane.offset / LANE_EDGE).clamp(-GUIDE_PAN_MAX, GUIDE_PAN_MAX)
        } else {
            0.0
        };
        let step = PAN_SLEW_PER_S * dt.max(0.0);
        if (target - self.pan).abs() <= step {
            self.pan = target;
        } else if target > self.pan {
            self.pan += step;
        } else {
            self.pan -= step;
        }

        if !self.awake {
            let centered = was_awake && self.episode_drifted;
            self.episode_drifted = false;
            return GuidanceFrame {
                awake: false,
                pan: self.pan,
                centered,
            };
        }
        GuidanceFrame {
            awake: true,
            pan: self.pan,
            centered: false,
        }
    }
}

#[cfg(test)]
mod tests {
    //! Ported from `tests/test_lane_guidance.py` and the pure `edge_rung`
    //! case in `tests/test_lane_pan.py` (its DrivingState cases belong to the
    //! app-shell bucket).
    use super::*;

    fn lane(offset: f64) -> LaneKeeping {
        let mut lane = LaneKeeping::new(Some(1));
        lane.offset = offset;
        lane
    }

    fn frame(g: &mut LaneGuidance, lane: &LaneKeeping) -> GuidanceFrame {
        g.update(lane, 1.0, true, 0.0, None)
    }

    fn frame_curve(
        g: &mut LaneGuidance,
        lane: &LaneKeeping,
        curve_steer: f64,
        curve_ahead_mi: Option<f64>,
    ) -> GuidanceFrame {
        g.update(lane, 1.0, true, curve_steer, curve_ahead_mi)
    }

    #[test]
    fn test_centered_straight_leaves_the_bed_home() {
        let mut g = LaneGuidance::new();
        let frame = frame(&mut g, &lane(0.0));
        assert!(!frame.awake);
        assert_eq!(frame.pan, 0.0);
    }

    #[test]
    fn test_drift_wakes_and_hysteresis_holds() {
        let mut g = LaneGuidance::new();
        assert!(!frame(&mut g, &lane(DRIFT_WAKE - 0.05)).awake);
        assert!(frame(&mut g, &lane(DRIFT_WAKE + 0.05)).awake);
        // Back inside the wake line but above the sleep line: still awake.
        assert!(frame(&mut g, &lane(DRIFT_SLEEP + 0.05)).awake);
        assert!(!frame(&mut g, &lane(DRIFT_SLEEP - 0.05)).awake);
    }

    #[test]
    fn test_pursuit_pan_leans_toward_the_correction() {
        // Drifting RIGHT: the wheel should go left, so the bed leans LEFT --
        // follow the sound back to center.
        let mut g = LaneGuidance::new();
        let f = frame(&mut g, &lane(0.7));
        assert!(f.awake);
        assert!(f.pan < 0.0);
        let mut g2 = LaneGuidance::new();
        let f = frame(&mut g2, &lane(-0.7));
        assert!(f.pan > 0.0);
    }

    #[test]
    fn test_curve_leads_into_the_bend_even_centered() {
        // A left bend wants a left steer: the bed leans left while centered.
        let mut g = LaneGuidance::new();
        let f = frame_curve(&mut g, &lane(0.0), -0.6, None);
        assert!(f.awake);
        assert!(f.pan < 0.0);
        // And the lean never exceeds the cap -- some road stays in both ears.
        let mut g2 = LaneGuidance::new();
        let mut f = GuidanceFrame {
            awake: false,
            pan: 0.0,
            centered: false,
        };
        for _ in 0..5 {
            f = frame_curve(&mut g2, &lane(0.9), -1.0, None);
        }
        assert!(f.pan.abs() <= GUIDE_PAN_MAX + 1e-9);
    }

    #[test]
    fn test_upcoming_curve_arms_inside_the_lead_window() {
        let mut g = LaneGuidance::new();
        assert!(!frame_curve(&mut g, &lane(0.0), 0.0, Some(CURVE_LEAD_MI * 2.0)).awake);
        assert!(frame_curve(&mut g, &lane(0.0), 0.0, Some(CURVE_LEAD_MI * 0.5)).awake);
    }

    #[test]
    fn test_pan_slews_home_after_sleep() {
        let mut g = LaneGuidance::new();
        frame(&mut g, &lane(0.9)); // deep drift: bed leans well left
        assert!(g.pan < 0.0);
        let mut f = frame(&mut g, &lane(0.0)); // settled: asleep, slewing home
        assert!(!f.awake);
        for _ in 0..4 {
            f = frame(&mut g, &lane(0.0));
        }
        assert_eq!(f.pan, 0.0);
    }

    #[test]
    fn test_sleep_after_drift_flags_the_centered_earcon() {
        let mut g = LaneGuidance::new();
        frame(&mut g, &lane(0.7));
        let f = frame(&mut g, &lane(0.05));
        assert!(!f.awake);
        assert!(f.centered);
        // A curve-only episode ends without the earcon: nothing drifted.
        frame_curve(&mut g, &lane(0.0), 0.4, None);
        let f = frame(&mut g, &lane(0.0));
        assert!(!f.centered);
    }

    #[test]
    fn test_assist_off_is_inert() {
        let mut g = LaneGuidance::new();
        let f = g.update(&lane(0.9), 1.0, false, -0.8, None);
        assert!(!f.awake);
        assert_eq!(f.pan, 0.0);
    }

    #[test]
    fn test_edge_rungs_grade_by_structure() {
        assert!(edge_rung(RUMBLE_START - 0.1, "shoulder", 1.0).is_none());
        let (key, vol_clip) = edge_rung(RUMBLE_START + 0.05, "shoulder", 1.0).unwrap();
        assert_eq!(key, EDGE_CLIP_KEY);
        let (key, vol_strip) = edge_rung(1.05, "shoulder", 1.0).unwrap();
        assert_eq!(key, EDGE_STRIP_KEY);
        assert!(vol_strip > vol_clip); // louder as well as structurally different
        let (key, _) = edge_rung(OFF_ROAD + 0.05, "shoulder", 1.0).unwrap();
        assert_eq!(key, EDGE_SHOULDER_KEY);
        // Past an undivided centerline there is no gravel: the strip stays the
        // outermost texture and the spoken warning carries the danger.
        let (key, _) = edge_rung(OFF_ROAD + 0.05, "oncoming", 1.0).unwrap();
        assert_eq!(key, EDGE_STRIP_KEY);
    }

    #[test]
    fn test_boundaries_divided_and_undivided() {
        // Rightmost lane of a divided 3-lane: another lane left, shoulder right.
        assert_eq!(
            classify_boundaries(0, 3, Some(true), true),
            ("lane", "shoulder")
        );
        // Leftmost lane of the same road: the median is past the left line.
        assert_eq!(
            classify_boundaries(2, 3, Some(true), true),
            ("median", "lane")
        );
        // Undivided two-lane: the left line is the centerline with oncoming.
        assert_eq!(
            classify_boundaries(0, 1, Some(false), false),
            ("oncoming", "shoulder")
        );
        // No baked flag: interstates infer divided...
        assert_eq!(classify_boundaries(1, 2, None, true), ("median", "lane"));
        // ...and a one-lane-per-side road infers the centerline.
        assert_eq!(
            classify_boundaries(0, 1, None, false),
            ("oncoming", "shoulder")
        );
    }

    #[test]
    fn test_no_new_tone_ever() {
        // The community ruling (roadmap, 2026-07-17): the guide is the existing
        // road bed, never a new synthetic tone. The Python test pinned the
        // module against a `BED_KEY` attribute quietly coming back; here the
        // only loop keys the module names are the edge ladder and the
        // transverse strips.
        let keys = [
            EDGE_CLIP_KEY,
            EDGE_STRIP_KEY,
            EDGE_SHOULDER_KEY,
            TRANSVERSE_KEY,
        ];
        assert!(keys
            .iter()
            .all(|k| !k.contains("bed") && !k.contains("tone")));
    }

    #[test]
    fn test_edge_rung_accepts_every_boundary() {
        for boundary in ["shoulder", "median", "oncoming", "lane"] {
            assert!(edge_rung(1.4, boundary, 1.0).is_some());
        }
    }

    // tests/test_lane_pan.py
    #[test]
    fn test_cue_loudness_scales_the_edge_rung() {
        let (_, standard) = edge_rung(1.05, "shoulder", 1.0).unwrap();
        let (_, subtle) = edge_rung(1.05, "shoulder", 0.6).unwrap();
        let (_, prominent) = edge_rung(1.05, "shoulder", 1.35).unwrap();
        assert!(subtle < standard && standard < prominent && prominent <= 1.0);
    }

    #[test]
    fn test_cue_loudness_table_matches_the_settings_row() {
        assert_eq!(cue_loudness("subtle"), Some(0.6));
        assert_eq!(cue_loudness("standard"), Some(1.0));
        assert_eq!(cue_loudness("prominent"), Some(1.35));
        assert_eq!(cue_loudness("loud"), None);
    }
}
