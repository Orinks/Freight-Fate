//! The engine's lean through a turn: how much steering the driver still owes.
//!
//! Owner ruling, 2026-09-18, in his own words: "When taking a curve or a turn
//! at city streets, the engine should pan in the direction the player must
//! turn. When the player turns, the engine pans back to center as they go
//! through the turn and is centered once through."
//!
//! So the pan is a QUANTITY OF STEERING OUTSTANDING, not a position error.
//! It opens toward the turn while the turn is still to be made, closes as the
//! driver actually makes it, and is centred the moment the turn is done. A
//! driver follows it the same way either way -- steer toward the sound until
//! it goes quiet -- but what makes it go quiet is the wheel, not the truck
//! drifting back to the middle of the lane.
//!
//! That is the difference from [`super::lane_guidance`], which stays exactly
//! as it was and still owns DRIFT: its target is `curve_steer - offset`, it
//! answers to where the truck sits between the lines, and on a straight road
//! it is the only thing leaning. This module owns the turn itself, and the
//! driving state hands the engine to whichever has something to say.
//!
//! # How much steering a turn owes
//!
//! Read from the turn, never invented. A bend carries `deflection_deg` and
//! `min_radius_ft` from the curve bake; a street corner carries the turn angle
//! this branch started by baking (`local_turn_deg`) and takes its radius from
//! [`crate::data::corners`]. Together those give the arc the truck must travel
//! through, and the time it spends in it at the speed it is doing:
//!
//! ```text
//! arc_ft   = radius_ft * deflection_rad
//! needed_s = arc_ft / speed_fps
//! ```
//!
//! Holding the wheel fully into the turn for that whole time is exactly one
//! turn's worth of steering, so the lean closes over `needed_s` of full lock
//! and proportionally longer for anything gentler. Nothing here is tuned: the
//! only number that is not read off the road is [`MIN_NEEDED_S`], which keeps
//! a near-stationary truck from dividing by a speed of zero.

use super::lane_guidance::{DRIFT_SLEEP, DRIFT_WAKE};

/// Below this the lean is centred: a hair of residual demand is not worth
/// moving the engine for, and it would chatter around the null.
pub const DEADBAND: f64 = 0.02;
/// The lean never pans fully into one ear -- the engine still has to read as
/// the truck's engine, and a driver needs the other side of the stereo field
/// for the road and the edge cues.
pub const MAX_LEAN: f64 = 0.85;
/// How fast the lean may move, pan units per second. It has to open quickly
/// enough to lead a corner that arrives at street speed and close smoothly
/// enough that nulling it feels like steering rather than switching it off.
pub const SLEW_PER_S: f64 = 2.2;
/// A turn opens its lean this far ahead of its start, in miles, so it is
/// leading by the time the driver has to act on it.
pub const LEAD_MI: f64 = 0.12;
/// Floor on the time a turn is allowed to take, so a truck barely moving
/// cannot demand an infinite amount of steering.
pub const MIN_NEEDED_S: f64 = 1.5;
/// How much of the lean a full-lane-width error is worth.
///
/// The whole lean, because `offset` is 1.0 exactly at the lane line (see
/// [`super::lane`]) and a truck on the line has correcting as its entire job.
/// On a straight road, drift alone can therefore reach the cap.
pub const LANE_TERM: f64 = MAX_LEAN;
/// How much of the lean the TURN ITSELF may use, leaving the rest as headroom
/// for the driver's error to ride on.
///
/// The two share one channel, so the turn cannot have all of it: at the cap
/// the lean says exactly the same thing whether the driver is making the turn
/// or driving straight out of it, which is silence about the one mistake the
/// guide exists to catch. Seven tenths keeps the turn plainly the louder voice
/// while leaving a margin that is audible when it opens.
pub const TURN_LEAN: f64 = MAX_LEAN * 0.7;

/// Which way a turn goes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TurnSide {
    Left,
    Right,
}

impl TurnSide {
    /// `-1.0` left, `+1.0` right: the sign the pan carries.
    pub fn sign(self) -> f64 {
        match self {
            TurnSide::Left => -1.0,
            TurnSide::Right => 1.0,
        }
    }

    /// `'L'` / `'R'` as the curve bake spells it, or a spoken "left"/"right".
    pub fn parse(value: &str) -> Option<Self> {
        match value.trim().to_lowercase().as_str() {
            "l" | "left" => Some(TurnSide::Left),
            "r" | "right" => Some(TurnSide::Right),
            _ => None,
        }
    }
}

/// The turn the guide is currently leaning for.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TurnShape {
    pub side: TurnSide,
    /// How far the road's heading swings through the turn.
    pub deflection_deg: f64,
    /// The radius the truck tracks through it.
    pub radius_ft: f64,
}

impl TurnShape {
    /// Seconds of full-lock steering this turn is worth at `speed_mph`.
    pub fn needed_s(&self, speed_mph: f64) -> f64 {
        let arc_ft = self.radius_ft.max(1.0) * self.deflection_deg.max(0.0).to_radians();
        let speed_fps = (speed_mph.max(0.0) * 5280.0) / 3600.0;
        if speed_fps <= 0.1 {
            return f64::MAX;
        }
        MIN_NEEDED_S.max(arc_ft / speed_fps)
    }
}

/// What the driving state feeds the guide each frame.
#[derive(Debug, Clone, Copy)]
pub struct TurnInput {
    /// The turn being approached or driven, or `None` when there is none.
    pub shape: Option<TurnShape>,
    /// Miles to the turn's start; negative once inside it.
    pub to_start_mi: f64,
    /// True once the turn is behind the truck.
    pub past: bool,
    /// The driver's own steering, -1.0 (full left) to 1.0 (full right).
    pub steering: f64,
    pub speed_mph: f64,
    /// How far through the turn's own footprint the truck is, 0.0 at its
    /// start to 1.0 at its end.
    ///
    /// The second way the lean closes, and the only one that works when the
    /// truck is steering itself. With lane keeping on full the driver never
    /// touches the wheel, so nothing would ever null a lean that waited on
    /// their input -- and the owner's ruling is that the engine still pans
    /// there, because the shape of the road is worth hearing whether or not
    /// you are the one answering it (2026-09-18).
    pub progress: f64,
    /// Where the truck sits in its lane, -1.0 (left line) to 1.0 (right).
    ///
    /// Folded into the lean so turning the WRONG way is audible: steering
    /// left through a right-hander pushes the truck left, and the correction
    /// that error needs points the same way the turn already does, so the lean
    /// deepens instead of sitting still. Without this the guide went quiet
    /// about the one mistake it exists to catch.
    pub lane_offset: f64,
    /// Steer AWAY from the lean rather than toward it.
    ///
    /// The house convention is pursuit -- follow the sound -- but audio racing
    /// games have taught a lot of players the opposite, and a driver who has
    /// that reflex will fight a guide built the other way round. Flipping the
    /// sign is the whole difference; everything above it is unchanged.
    pub inverted: bool,
}

/// The engine's lean through turns.
#[derive(Debug, Clone, Default)]
pub struct TurnGuide {
    /// Pan actually being applied, slewed toward the target.
    pan: f64,
    /// How much of this turn's steering the driver has put in, 0 to 1.
    steered: f64,
    /// Set while a turn is open, cleared when it ends, so a new turn starts
    /// from a full lean rather than inheriting the last one's progress.
    open: bool,
    /// Whether the DRIFT half of the lean is currently speaking.
    ///
    /// Gated on the same wake and sleep thresholds `lane_guidance` uses, and
    /// for the reason its header gives: silence is centred. Without this the
    /// correction chased ordinary lane wander and the engine stepped about
    /// once a second the whole length of a straight road -- heard on AZ-260,
    /// 2026-09-18, which is what driving it was for.
    drift_awake: bool,
}

impl TurnGuide {
    pub fn new() -> Self {
        Self::default()
    }

    /// The pan to apply to the engine this frame.
    pub fn pan(&self) -> f64 {
        if self.pan.abs() < DEADBAND {
            0.0
        } else {
            self.pan
        }
    }

    /// How much of the current turn the driver has steered, 0 to 1. Exposed
    /// for the readouts and the tests; the pan is what the driver hears.
    pub fn steered(&self) -> f64 {
        self.steered
    }

    /// Advance the guide one frame and return the pan to apply.
    pub fn update(&mut self, input: TurnInput, dt: f64) -> f64 {
        let target = self.target(input, dt);
        let step = SLEW_PER_S * dt.max(0.0);
        if (target - self.pan).abs() <= step {
            self.pan = target;
        } else if target > self.pan {
            self.pan += step;
        } else {
            self.pan -= step;
        }
        self.pan()
    }

    /// The drift half of the lean, asleep until the wander is a real drift.
    ///
    /// Hysteresis, not a single threshold: woken at `DRIFT_WAKE` and only
    /// quiet again back inside `DRIFT_SLEEP`, so a truck sitting on the wake
    /// line does not switch the correction on and off.
    fn drift_correction(&mut self, lane_offset: f64) -> f64 {
        let offset = lane_offset.clamp(-1.0, 1.0);
        let away = offset.abs();
        if self.drift_awake {
            if away < DRIFT_SLEEP {
                self.drift_awake = false;
            }
        } else if away >= DRIFT_WAKE {
            self.drift_awake = true;
        }
        if self.drift_awake {
            -offset * LANE_TERM
        } else {
            0.0
        }
    }

    /// Where the lean wants to be, before slewing.
    fn target(&mut self, input: TurnInput, dt: f64) -> f64 {
        let Some(shape) = input.shape.filter(|_| !input.past) else {
            // No turn, so the lean is the driver's lane error alone -- which
            // on a straight road with a centred truck is silence.
            self.open = false;
            self.steered = 0.0;
            let correction = self
                .drift_correction(input.lane_offset)
                .clamp(-MAX_LEAN, MAX_LEAN);
            return if input.inverted {
                -correction
            } else {
                correction
            };
        };
        if !self.open {
            self.open = true;
            self.steered = 0.0;
        }
        // Inside the turn, the driver's own wheel is what closes the lean.
        // Steering the WRONG way never opens it further than the turn asks:
        // the guide reports what the turn still needs, and a driver steering
        // away from it has simply not done any of it yet.
        if input.to_start_mi <= 0.0 {
            let needed = shape.needed_s(input.speed_mph);
            if needed.is_finite() && needed > 0.0 {
                let into_turn = (input.steering * shape.side.sign()).clamp(0.0, 1.0);
                self.steered = (self.steered + into_turn * dt / needed).clamp(0.0, 1.0);
            }
        }
        // Opening: full lean by the time the turn starts.
        let approach = if input.to_start_mi <= 0.0 {
            1.0
        } else if input.to_start_mi >= LEAD_MI {
            0.0
        } else {
            1.0 - input.to_start_mi / LEAD_MI
        };
        // Whichever has got further through the turn closes the lean: the
        // driver's wheel, or the turn simply going by underneath. A driver
        // doing the steering nulls it early and hears it go quiet as a
        // reward; one being driven hears it close as the corner is used up.
        let by_wheel = (1.0 - self.steered).clamp(0.0, 1.0);
        let by_road = (1.0 - input.progress.clamp(0.0, 1.0)).clamp(0.0, 1.0);
        let remaining = by_wheel.min(by_road);
        let owed = shape.side.sign() * TURN_LEAN * approach * remaining;
        // The lane error rides on top, pointing the way that corrects it --
        // once the drift is worth reporting at all.
        let correction = self.drift_correction(input.lane_offset);
        let target = (owed + correction).clamp(-MAX_LEAN, MAX_LEAN);
        if input.inverted {
            -target
        } else {
            target
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn a_corner(side: TurnSide) -> TurnShape {
        TurnShape {
            side,
            deflection_deg: 90.0,
            radius_ft: 65.0, // the square city corner from data::corners
        }
    }

    fn approaching(shape: TurnShape, to_start_mi: f64, steering: f64) -> TurnInput {
        TurnInput {
            shape: Some(shape),
            to_start_mi,
            past: false,
            steering,
            speed_mph: 9.0,
            lane_offset: 0.0,
            inverted: false,
            progress: 0.0,
        }
    }

    /// Run the guide for `seconds` and return the final pan.
    fn run(guide: &mut TurnGuide, input: TurnInput, seconds: f64) -> f64 {
        let dt = 1.0 / 60.0;
        let mut pan = 0.0;
        for _ in 0..((seconds / dt) as i64) {
            pan = guide.update(input, dt);
        }
        pan
    }

    #[test]
    fn the_lean_opens_toward_the_turn_the_driver_must_make() {
        let mut left = TurnGuide::new();
        let pan = run(
            &mut left,
            approaching(a_corner(TurnSide::Left), 0.0, 0.0),
            1.0,
        );
        assert!(pan < -0.5, "a left turn must lean left; got {pan}");

        let mut right = TurnGuide::new();
        let pan = run(
            &mut right,
            approaching(a_corner(TurnSide::Right), 0.0, 0.0),
            1.0,
        );
        assert!(pan > 0.5, "a right turn must lean right; got {pan}");
    }

    #[test]
    fn steering_into_the_turn_brings_the_lean_back_to_centre() {
        // The owner's sentence, as a test: pan toward the turn, and as the
        // player turns, it pans back to centre.
        let shape = a_corner(TurnSide::Left);
        let mut guide = TurnGuide::new();
        let opened = run(&mut guide, approaching(shape, 0.0, 0.0), 1.0);
        assert!(opened < -0.5, "the lean never opened: {opened}");

        // Now hold the wheel into it. `needed_s` for a 90-degree, 65 ft corner
        // at 9 mph is about 7.7 seconds, so ten is comfortably a whole turn.
        let closed = run(&mut guide, approaching(shape, -0.01, -1.0), 10.0);
        assert_eq!(closed, 0.0, "holding the wheel into it must null the lean");
        assert!(guide.steered() >= 1.0);
    }

    #[test]
    fn a_half_steered_turn_keeps_half_its_lean() {
        let shape = a_corner(TurnSide::Right);
        let mut guide = TurnGuide::new();
        run(&mut guide, approaching(shape, 0.0, 0.0), 1.0);
        let needed = shape.needed_s(9.0);
        let half = run(&mut guide, approaching(shape, -0.01, 1.0), needed / 2.0);
        // Half the TURN's share of the lean -- stated against the constant so
        // it keeps meaning "half" if the share is ever re-split.
        assert!(
            ((TURN_LEAN * 0.4)..(TURN_LEAN * 0.6)).contains(&half),
            "half a turn's steering should leave about half of {TURN_LEAN}; got {half}"
        );
    }

    #[test]
    fn steering_the_wrong_way_is_not_progress_through_the_turn() {
        let shape = a_corner(TurnSide::Left);
        let mut guide = TurnGuide::new();
        run(&mut guide, approaching(shape, -0.01, 1.0), 6.0);
        assert_eq!(guide.steered(), 0.0, "wrong-way steering is not progress");
    }

    #[test]
    fn turning_the_wrong_way_deepens_the_lean_as_the_truck_goes_wrong() {
        // The owner's question: does the pan reflect it? It has to -- a guide
        // that says the same thing whether you are making the turn or driving
        // out of it is silent about the one mistake it exists to catch.
        //
        // Steering right through a LEFT-hander pushes the truck right, and
        // correcting that error points left, which is the way the turn already
        // leans. So the lean deepens toward its cap rather than sitting still.
        let shape = a_corner(TurnSide::Left);
        let mut held = TurnGuide::new();
        let on_line = run(
            &mut held,
            TurnInput {
                lane_offset: 0.0,
                ..approaching(shape, -0.01, 1.0)
            },
            4.0,
        );
        let mut wrong = TurnGuide::new();
        let drifting = run(
            &mut wrong,
            TurnInput {
                lane_offset: 0.6, // pushed right, out of a left-hander
                ..approaching(shape, -0.01, 1.0)
            },
            4.0,
        );
        assert!(
            drifting < on_line,
            "going wrong must lean harder: {drifting} against {on_line}"
        );
        assert!(drifting >= -(MAX_LEAN + 1e-9), "past the cap: {drifting}");
    }

    #[test]
    fn the_inverted_guide_is_the_same_lean_the_other_way_round() {
        // For drivers whose reflex from other audio racing games is to steer
        // AWAY from the sound. Nothing else about the guide changes.
        let shape = a_corner(TurnSide::Right);
        let mut normal = TurnGuide::new();
        let toward = run(&mut normal, approaching(shape, 0.0, 0.0), 1.0);
        let mut flipped = TurnGuide::new();
        let away = run(
            &mut flipped,
            TurnInput {
                inverted: true,
                ..approaching(shape, 0.0, 0.0)
            },
            1.0,
        );
        assert!(
            toward > 0.0,
            "a right turn leans right by default: {toward}"
        );
        assert!(
            (away + toward).abs() < 1e-9,
            "{away} is not the mirror of {toward}"
        );
    }

    #[test]
    fn a_truck_being_steered_for_still_hears_the_turn_close() {
        // Owner, 2026-09-18: with every assist on, the curve and turn assists
        // take the turns and the engine STILL pans. The driver's wheel never
        // moves there, so the turn going by underneath is what closes it.
        let shape = a_corner(TurnSide::Right);
        let mut guide = TurnGuide::new();
        let opened = run(
            &mut guide,
            TurnInput {
                progress: 0.0,
                ..approaching(shape, 0.0, 0.0)
            },
            1.0,
        );
        assert!(opened > 0.3, "the lean never opened: {opened}");

        let half = run(
            &mut guide,
            TurnInput {
                progress: 0.5,
                ..approaching(shape, -0.01, 0.0)
            },
            1.0,
        );
        assert!(
            half < opened && half > 0.05,
            "halfway through it should be part closed, not gone: {half}"
        );

        let done = run(
            &mut guide,
            TurnInput {
                progress: 1.0,
                ..approaching(shape, -0.02, 0.0)
            },
            1.0,
        );
        assert_eq!(
            done, 0.0,
            "the corner was used up; the lean must be centred"
        );
    }

    #[test]
    fn ordinary_lane_wander_leaves_the_engine_alone() {
        // Silence is centred. Driven on AZ-260 the correction had no wake
        // threshold at all, so it chased the wander model and the engine
        // stepped about once a second down a dead straight road -- which for
        // a driver listening to it for hours is the opposite of help.
        let mut guide = TurnGuide::new();
        for offset in [0.0, 0.1, -0.2, 0.3, -0.35, 0.2] {
            let pan = run(
                &mut guide,
                TurnInput {
                    shape: None,
                    to_start_mi: f64::INFINITY,
                    past: false,
                    steering: 0.0,
                    speed_mph: 55.0,
                    lane_offset: offset,
                    inverted: false,
                    progress: 0.0,
                },
                0.5,
            );
            assert_eq!(pan, 0.0, "wander of {offset} woke the lean");
        }
    }

    #[test]
    fn a_real_drift_wakes_the_lean_and_holds_it_until_the_truck_is_back() {
        let mut guide = TurnGuide::new();
        let straight = TurnInput {
            shape: None,
            to_start_mi: f64::INFINITY,
            past: false,
            steering: 0.0,
            speed_mph: 55.0,
            lane_offset: 0.0,
            inverted: false,
            progress: 0.0,
        };
        // Past the wake line, it speaks.
        let woken = run(
            &mut guide,
            TurnInput {
                lane_offset: 0.5,
                ..straight
            },
            1.0,
        );
        assert!(woken < -0.1, "a real drift must lean; got {woken}");
        // Coming back but not yet centred, it KEEPS speaking -- hysteresis,
        // or a truck sitting on the line would switch it on and off.
        let recovering = run(
            &mut guide,
            TurnInput {
                lane_offset: 0.35,
                ..straight
            },
            1.0,
        );
        assert!(recovering < 0.0, "it let go too early: {recovering}");
        // Back inside the centred band, it sleeps again.
        let settled = run(
            &mut guide,
            TurnInput {
                lane_offset: 0.1,
                ..straight
            },
            1.0,
        );
        assert_eq!(settled, 0.0);
    }

    #[test]
    fn a_drifting_truck_leans_toward_the_correction_with_no_turn_at_all() {
        // The turn guide owns the straight road too now, because the lane
        // error term does not need a turn to mean something.
        let mut guide = TurnGuide::new();
        let pan = run(
            &mut guide,
            TurnInput {
                shape: None,
                to_start_mi: f64::INFINITY,
                past: false,
                steering: 0.0,
                speed_mph: 55.0,
                lane_offset: 0.5, // drifted right
                inverted: false,
                progress: 0.0,
            },
            2.0,
        );
        assert!(pan < -0.1, "drifting right must lean left; got {pan}");
    }

    #[test]
    fn the_lean_is_centred_once_the_turn_is_behind_the_truck() {
        let shape = a_corner(TurnSide::Right);
        let mut guide = TurnGuide::new();
        run(&mut guide, approaching(shape, 0.0, 0.0), 1.0);
        let done = run(
            &mut guide,
            TurnInput {
                shape: Some(shape),
                to_start_mi: -0.2,
                past: true,
                steering: 0.0,
                speed_mph: 9.0,
                lane_offset: 0.0,
                inverted: false,
                progress: 0.0,
            },
            2.0,
        );
        assert_eq!(done, 0.0, "a finished turn must leave the engine centred");
    }

    #[test]
    fn a_straight_road_is_silent() {
        let mut guide = TurnGuide::new();
        let pan = run(
            &mut guide,
            TurnInput {
                shape: None,
                to_start_mi: f64::INFINITY,
                past: false,
                steering: 0.0,
                speed_mph: 55.0,
                lane_offset: 0.0,
                inverted: false,
                progress: 0.0,
            },
            2.0,
        );
        assert_eq!(pan, 0.0);
    }

    #[test]
    fn the_lean_leads_the_turn_rather_than_arriving_with_it() {
        // Half a lead-distance out it is already leaning, so the driver has
        // road in which to act on it.
        let shape = a_corner(TurnSide::Left);
        let mut guide = TurnGuide::new();
        let early = run(&mut guide, approaching(shape, LEAD_MI / 2.0, 0.0), 1.0);
        assert!(early < -0.2, "the lean must lead the turn; got {early}");
        // And a turn still well beyond the lead window says nothing at all.
        let mut far = TurnGuide::new();
        let quiet = run(&mut far, approaching(shape, LEAD_MI * 3.0, 0.0), 1.0);
        assert_eq!(quiet, 0.0);
    }

    #[test]
    fn a_sharper_turn_asks_for_more_steering_than_a_gentle_one() {
        // Read from the road: the arc is radius times deflection, so a
        // switchback owes more wheel than a sweeping bend at the same speed.
        let sweeping = TurnShape {
            side: TurnSide::Left,
            deflection_deg: 60.0,
            radius_ft: 100.0,
        };
        let square = a_corner(TurnSide::Left);
        let hairpin = TurnShape {
            side: TurnSide::Left,
            deflection_deg: 150.0,
            radius_ft: 45.0,
        };
        assert!(sweeping.needed_s(9.0) > square.needed_s(9.0));
        assert!(hairpin.needed_s(9.0) > square.needed_s(9.0));
    }

    #[test]
    fn the_same_turn_taken_faster_needs_the_wheel_for_less_time() {
        let shape = a_corner(TurnSide::Right);
        assert!(shape.needed_s(20.0) < shape.needed_s(9.0));
        // And a stopped truck is never asked for an impossible amount.
        assert!(shape.needed_s(0.0).is_infinite() || shape.needed_s(0.0) > 1e6);
    }

    #[test]
    fn a_new_turn_starts_from_a_full_lean() {
        // Progress through one corner must not carry into the next, or the
        // second corner of a city block would open already half-nulled.
        let shape = a_corner(TurnSide::Left);
        let mut guide = TurnGuide::new();
        run(&mut guide, approaching(shape, 0.0, 0.0), 1.0);
        run(&mut guide, approaching(shape, -0.01, -1.0), 10.0);
        assert_eq!(guide.pan(), 0.0);

        // The road goes straight for a moment, then the next corner arrives.
        run(
            &mut guide,
            TurnInput {
                shape: None,
                to_start_mi: f64::INFINITY,
                past: false,
                steering: 0.0,
                speed_mph: 9.0,
                lane_offset: 0.0,
                inverted: false,
                progress: 0.0,
            },
            0.5,
        );
        let next = run(
            &mut guide,
            approaching(a_corner(TurnSide::Right), 0.0, 0.0),
            1.5,
        );
        assert!(next > 0.5, "the next corner opened only to {next}");
    }

    #[test]
    fn side_parses_both_the_bake_and_the_spoken_spelling() {
        assert_eq!(TurnSide::parse("L"), Some(TurnSide::Left));
        assert_eq!(TurnSide::parse("right"), Some(TurnSide::Right));
        assert_eq!(TurnSide::parse("ahead"), None);
    }
}
