//! Whether the officer at a post actually notices you, and what they noticed
//! (port of `freight_fate/sim/enforcement_observe.py`).
//!
//! Observation is a scored decision with five inputs a player can feel:
//! geometry (how close you are relative to the method's reach), line of
//! sight (a crest or hard bend blocks lidar; radar hardly cares), weather
//! (fog and heavy rain gut lidar and eyesight), traffic cover (running in a
//! pack at the pack's speed lowers the odds you are the one picked), and
//! severity (five over is noticed and ignored; twenty over is a certainty).
//! A post using its eyes also sees visible damage, missing chains, an unlit
//! truck at night, tailgating and lane misuse.
//!
//! Nothing here rolls a number. `observe` returns a confidence; the caller
//! makes the named, seeded, position-quantised draw against it.

use crate::pyfmt::fmt_f;
use crate::sim::enforcement_posts::{
    EnforcementPost, METHOD_LIDAR, METHOD_PACING, METHOD_RADAR, METHOD_SCALE_SCREEN, METHOD_VISUAL,
    PACING_MIN_MI,
};

/// Tolerance before a speed is a speed at all; `driving_core.SPEEDING_LEEWAY_MPH`
/// is this constant, so the number lives in one place.
pub const OBSERVE_LEEWAY_MPH: f64 = 9.0;
/// At or past this far over the limit, any post that can see you has you.
pub const CERTAIN_OVER_MPH: f64 = 20.0;
/// Overage that reads as full severity short of the certainty line.
pub const SEVERE_OVER_MPH: f64 = 18.0;
/// A confidence under this is a shrug: "noticed and ignored" is a real state.
pub const IGNORE_FLOOR: f64 = 0.06;
/// How far the truck must have travelled while over the limit before a post
/// reads it as a speed rather than a blip. DISTANCE, not real seconds.
pub const OBSERVE_HOLD_MI: f64 = 0.08;
pub const COVER_RADIUS_MI: f64 = 0.30;
pub const COVER_SPEED_TOLERANCE_MPH: f64 = 4.0;
pub const COVER_FACTOR_PACK: f64 = 0.45; // two or more neighbours
pub const CLEAR_VISIBILITY_MI: f64 = 3.0;
pub const DAMAGE_NOTICE_PCT: f64 = 45.0;
pub const DAMAGE_SEVERE_PCT: f64 = 80.0;
/// A following distance no officer would let pass, in seconds of gap.
pub const TAILGATE_GAP_S: f64 = 1.2;

pub const WHAT_SPEEDING: &str = "speeding";
pub const WHAT_DAMAGE: &str = "unsafe equipment";
pub const WHAT_CHAINS: &str = "no chains";
pub const WHAT_LIGHTS: &str = "no lights";
pub const WHAT_FOLLOWING: &str = "following too close";
pub const WHAT_LANE: &str = "lane misuse";

/// Python `COVER_FACTOR = {0: 1.0, 1: 0.70}` with `COVER_FACTOR_PACK` beyond.
pub fn cover_factor_for(neighbours: i64) -> f64 {
    match neighbours.max(0) {
        0 => 1.0,
        1 => 0.70,
        _ => COVER_FACTOR_PACK,
    }
}

/// Line of sight: a crest or a hard bend between you and the post.
pub fn los_blocked_factor(method: &str) -> f64 {
    match method {
        METHOD_LIDAR => 0.15,
        METHOD_VISUAL => 0.25,
        METHOD_RADAR => 0.85,
        METHOD_PACING => 0.9,
        METHOD_SCALE_SCREEN => 1.0,
        _ => 0.5,
    }
}

fn clamp01(value: f64) -> f64 {
    value.clamp(0.0, 1.0)
}

/// Everything a post could possibly notice about the truck right now.
/// Optional fields default to the innocent reading.
#[derive(Debug, Clone, PartialEq)]
pub struct RoadSample {
    pub position_mi: f64,
    pub speed_mph: f64,
    pub limit_mph: f64,
    pub damage_pct: f64,
    pub visibility_mi: f64,
    pub night: bool,
    pub lights_on: bool,
    pub chains_required: bool,
    pub chains_on: bool,
    pub following_gap_s: Option<f64>,
    /// Road covered while the gap has been inside TAILGATE_GAP_S.
    pub closed_up_mi: f64,
    pub left_lane_restricted: bool,
    pub in_left_lane: bool,
    /// Neighbours inside COVER_RADIUS_MI holding within COVER_SPEED_TOLERANCE_MPH.
    pub pack_neighbours: i64,
    /// A crest or hard bend sits between the truck and the post.
    pub crest_between: bool,
    /// Road this post has been sitting behind the truck over (pacing only).
    pub paced_mi: f64,
    /// How far the truck has run continuously over the limit.
    pub over_limit_mi: f64,
}

impl RoadSample {
    pub fn new(position_mi: f64, speed_mph: f64, limit_mph: f64) -> Self {
        RoadSample {
            position_mi,
            speed_mph,
            limit_mph,
            damage_pct: 0.0,
            visibility_mi: 10.0,
            night: false,
            lights_on: true,
            chains_required: false,
            chains_on: true,
            following_gap_s: None,
            closed_up_mi: 0.0,
            left_lane_restricted: false,
            in_left_lane: false,
            pack_neighbours: 0,
            crest_between: false,
            paced_mi: 0.0,
            over_limit_mi: 0.0,
        }
    }

    pub fn mph_over(&self) -> f64 {
        (self.speed_mph - self.limit_mph).max(0.0)
    }
}

/// One thing one post noticed, and how sure they are.
#[derive(Debug, Clone, PartialEq)]
pub struct Observation {
    pub post: EnforcementPost,
    pub confidence: f64,
    pub method: String,
    pub what: String,
    pub detail: String,
}

impl Observation {
    pub fn certain(&self) -> bool {
        self.confidence >= 1.0
    }
}

/// 0 where the overage is inside the leeway, 1 at a flagrant speed.
pub fn speeding_severity(mph_over: f64) -> f64 {
    let over = mph_over;
    if over <= OBSERVE_LEEWAY_MPH {
        return 0.0;
    }
    if over >= CERTAIN_OVER_MPH {
        return 1.0;
    }
    let span = (SEVERE_OVER_MPH - OBSERVE_LEEWAY_MPH).max(1e-6);
    clamp01((over - OBSERVE_LEEWAY_MPH) / span)
}

/// (what, severity, detail) for everything this post could notice.
fn candidates(post: &EnforcementPost, sample: &RoadSample) -> Vec<(&'static str, f64, String)> {
    let mut found = Vec::new();
    let speed_sev = speeding_severity(sample.mph_over());
    if speed_sev > 0.0 && sample.over_limit_mi >= OBSERVE_HOLD_MI {
        found.push((
            WHAT_SPEEDING,
            speed_sev,
            format!("{} over", fmt_f(sample.mph_over(), 0)),
        ));
    }
    if post.method != METHOD_VISUAL && post.method != METHOD_SCALE_SCREEN {
        // Radar, lidar, and a pacing unit are looking at speed. Everything
        // below needs eyes on the truck.
        return found;
    }
    let damage = sample.damage_pct;
    if damage >= DAMAGE_NOTICE_PCT {
        let span = (DAMAGE_SEVERE_PCT - DAMAGE_NOTICE_PCT).max(1e-6);
        found.push((
            WHAT_DAMAGE,
            clamp01((damage - DAMAGE_NOTICE_PCT) / span),
            format!("{} percent", fmt_f(damage, 0)),
        ));
    }
    if sample.chains_required && !sample.chains_on {
        found.push((WHAT_CHAINS, 1.0, "chain control in force".to_string()));
    }
    if sample.night && !sample.lights_on {
        found.push((WHAT_LIGHTS, 0.9, "running dark".to_string()));
    }
    if let Some(gap) = sample.following_gap_s {
        // Held, not glimpsed -- exactly the rule speeding has had all along.
        // Without the hold, one sampled frame inside the gap was a citation
        // (tester Darren, I-75, 2026-08-18, fined 1,200 dollars while
        // adaptive cruise was easing him down for a work-zone taper).
        if 0.0 < gap && gap < TAILGATE_GAP_S && sample.closed_up_mi >= OBSERVE_HOLD_MI {
            found.push((
                WHAT_FOLLOWING,
                clamp01((TAILGATE_GAP_S - gap) / TAILGATE_GAP_S),
                "closed up".to_string(),
            ));
        }
    }
    if sample.left_lane_restricted && sample.in_left_lane {
        found.push((WHAT_LANE, 0.4, "left lane".to_string()));
    }
    found
}

/// How well the post's method reaches this piece of road: full strength at
/// the post, tailing off to half at the edge of its reach, zero once past.
pub fn geometry_factor(post: &EnforcementPost, sample: &RoadSample) -> f64 {
    let ahead = post.at_mi - sample.position_mi;
    if post.method == METHOD_PACING {
        // A pacing unit is behind you: it needs to have been there long
        // enough to hold a speed.
        if sample.paced_mi < PACING_MIN_MI {
            return 0.0;
        }
        return clamp01(0.5 + 0.5 * (sample.paced_mi / (2.0 * PACING_MIN_MI)).min(1.0));
    }
    if ahead < -0.3 || ahead > post.reach_mi {
        return 0.0;
    }
    let closeness = 1.0 - clamp01(ahead.max(0.0) / post.reach_mi.max(1e-6));
    0.5 + 0.5 * closeness
}

pub fn line_of_sight_factor(post: &EnforcementPost, sample: &RoadSample) -> f64 {
    if !sample.crest_between {
        return 1.0;
    }
    los_blocked_factor(&post.method)
}

/// Fog and heavy rain gut the optical methods and barely touch radar.
pub fn weather_factor(post: &EnforcementPost, sample: &RoadSample) -> f64 {
    let vis = sample.visibility_mi.max(0.0);
    let clarity = clamp01(vis / CLEAR_VISIBILITY_MI);
    if post.method == METHOD_LIDAR || post.method == METHOD_VISUAL {
        return (0.15 + 0.85 * clarity).clamp(0.15, 1.0);
    }
    if post.method == METHOD_SCALE_SCREEN {
        return 1.0; // the truck drives onto the scale; nobody is squinting
    }
    (0.9 + 0.1 * clarity).clamp(0.9, 1.0)
}

/// Running in a pack at the pack's speed is real cover, and a real tactic.
pub fn cover_factor(sample: &RoadSample) -> f64 {
    cover_factor_for(sample.pack_neighbours)
}

/// What this post notices about the truck right now, and how sure it is.
///
/// `None` when there is nothing worth noticing, when the post is empty,
/// when it cannot see this piece of road, when it has already had its look
/// and let it go, or when the player was never told it was there -- that
/// last gate is an accessibility rule: a post the player had no cue for is
/// not allowed to cost them anything.
pub fn observe(post: &EnforcementPost, sample: &RoadSample) -> Option<Observation> {
    if !post.staffed || post.declined || !post.announced {
        return None;
    }
    let geometry = geometry_factor(post, sample);
    if geometry <= 0.0 {
        return None;
    }
    let candidates = candidates(post, sample);
    if candidates.is_empty() {
        return None;
    }
    let los = line_of_sight_factor(post, sample);
    let weather = weather_factor(post, sample);
    let visibility_product = geometry * los * weather;
    let mut best: Option<Observation> = None;
    for (what, severity, detail) in candidates {
        // Speed is the one thing a pack hides. Damage, chains, and lights
        // are visible on your truck whoever else is around.
        let cover = if what == WHAT_SPEEDING {
            cover_factor(sample)
        } else {
            1.0
        };
        let mut confidence = severity * visibility_product * cover * post.notice;
        if what == WHAT_SPEEDING
            && sample.mph_over() >= CERTAIN_OVER_MPH
            && visibility_product >= 0.2
        {
            // Flagrant speed at a post that can see the road at all is not a
            // question. No pack, no weather, no luck.
            confidence = 1.0;
        }
        confidence = clamp01(confidence);
        if confidence < IGNORE_FLOOR {
            continue;
        }
        if best.as_ref().is_none_or(|b| confidence > b.confidence) {
            best = Some(Observation {
                post: post.clone(),
                confidence,
                method: post.method.clone(),
                what: what.to_string(),
                detail,
            });
        }
    }
    best
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::sim::enforcement_posts::{method_by_kind, KIND_MEDIAN, KIND_URBAN};

    fn post(kind: &str) -> EnforcementPost {
        EnforcementPost {
            method: method_by_kind(kind).to_string(),
            facing: "both".to_string(),
            staffed: true,
            notice: 1.0,
            announced: true,
            ..EnforcementPost::new(10.0, kind)
        }
    }

    #[test]
    fn severity_ladder() {
        assert_eq!(speeding_severity(5.0), 0.0);
        assert_eq!(speeding_severity(25.0), 1.0);
        assert!((speeding_severity(13.5) - 0.5).abs() < 1e-9);
    }

    #[test]
    fn five_over_is_ignored_and_twenty_over_is_certain() {
        let p = post(KIND_MEDIAN);
        let mut sample = RoadSample::new(9.5, 70.0, 65.0);
        sample.over_limit_mi = 1.0;
        assert!(observe(&p, &sample).is_none());
        let sample = RoadSample {
            speed_mph: 90.0,
            ..sample
        };
        let seen = observe(&p, &sample).expect("flagrant speed is seen");
        assert!(seen.certain());
        assert_eq!(seen.what, WHAT_SPEEDING);
    }

    #[test]
    fn a_crest_blocks_lidar_more_than_radar() {
        let radar = post(KIND_MEDIAN);
        let lidar = post(KIND_URBAN);
        let mut sample = RoadSample::new(9.8, 80.0, 65.0);
        sample.over_limit_mi = 1.0;
        sample.crest_between = true;
        assert!(line_of_sight_factor(&lidar, &sample) < line_of_sight_factor(&radar, &sample));
    }
}
