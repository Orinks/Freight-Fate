//! The exit ramp past the gore, piece by piece: the deceleration lane where
//! the truck sheds to the exit speed, the ramp curve that speed is for, and
//! the run down to the stop bar.
//!
//! Realistic exit redesign, owner-approved 2026-09-24. A deceleration lane
//! is a full lane beside the through lanes and exists so a driver leaves at
//! road speed and sheds inside it: the Green Book sizes it assuming no
//! deceleration in the through lanes, and TxDOT's manual says to assume all
//! of it happens in the speed-change lane. So the exit's braking lives HERE,
//! and the exit speed (the ramp's advisory, MUTCD W13-2, which stands along
//! this lane) governs the curve that follows it, not the gore.

use ff_core::data::curves::min_radius_ft;
use ff_core::speech_pacing::{EventPriority, SpeechCategory};

use crate::app::{GameContext, SayEvent};
use crate::bindings::Action;
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;
use crate::states::driving_stops::assist_servo_brake;

impl DrivingState {
    /// How far past the gore the truck has come on the ramp it took there.
    ///
    /// None off a laid-out ramp: no ramp, or a ramp the game put the truck on
    /// some other way (the loop-back to a missed terminal), which has no
    /// lane or curve behind it.
    pub fn ramp_travelled_mi(&self) -> Option<f64> {
        let layout = self.ramp_layout?;
        let left = self.ramp_mi?;
        Some(layout.length_mi() + RAMP_ACCESS_MI - left)
    }

    /// Road left in the deceleration lane, while the truck is in it.
    pub fn deceleration_lane_left_mi(&self) -> Option<f64> {
        let layout = self.ramp_layout?;
        let travelled = self.ramp_travelled_mi()?;
        let left = layout.decel_mi - travelled;
        (left > 0.0).then_some(left)
    }

    pub fn in_deceleration_lane(&self) -> bool {
        self.deceleration_lane_left_mi().is_some()
    }

    /// The radius of the ramp curve, in feet, while the truck is in it.
    ///
    /// DERIVED from the speed the ramp is built for through the same AASHTO
    /// point-mass control the curve bake uses (`min_radius_ft`), never a
    /// flat push. Only inside the curve's own length: the lane before it
    /// runs beside the mainline and the run to the bar is straight. This used
    /// to bend the whole half mile, gore to driveway -- two loops' worth of
    /// turning on every exit.
    pub fn ramp_curve_radius_ft(&self) -> Option<f64> {
        if self.surface_chain {
            return None;
        }
        let layout = self.ramp_layout?;
        let travelled = self.ramp_travelled_mi()?;
        let into_curve = travelled - layout.decel_mi;
        if !(0.0..layout.curve_mi).contains(&into_curve) {
            return None;
        }
        Some(min_radius_ft(layout.curve_mph).max(1.0))
    }

    /// Work the deceleration lane: publish the ramp's grade, and let the
    /// exit assists brake to the exit speed by the curve.
    ///
    /// Exit speed assistance and route-transition assistance both answer
    /// here, as one servo: they are the two settings that promise help with
    /// the exit's speed, and two servos on one lane would fight and speak
    /// twice. Runs ahead of the physics step, and its press is a pedal
    /// floor in the frame (`decel_lane_brake`), like the terminal's.
    pub fn update_deceleration_lane(&mut self, ctx: &mut GameContext) {
        // The lane runs beside the mainline and shares its grade; the ramp
        // proper has its own, ASSUMED level (see `ExitRampLayout::grade`).
        self.trip.ramp_grade = match (self.ramp_mi, self.ramp_layout) {
            (Some(_), Some(layout)) if !self.in_deceleration_lane() => Some(layout.grade),
            _ => None,
        };
        let assisting = ctx.settings.exit_speed_assist || ctx.settings.route_transition_assist;
        let Some(left_mi) = self.deceleration_lane_left_mi().filter(|_| assisting) else {
            self.decel_lane_brake = 0.0;
            return;
        };
        // The driver's own throttle overrides, as it does the terminal's.
        let accelerating = ctx.bindings.pressed(&ctx.input, Action::Accelerate)
            || (ctx.controller.active() && ctx.controller.throttle() > 0.05);
        if accelerating {
            self.decel_lane_brake = 0.0;
            return;
        }
        let target_mps = self.armed_ramp_mph(None) / MPH_PER_MPS;
        let v_mps = self.trip.truck.velocity_mps.max(0.0);
        let gap_m = 0.5f64.max(left_mi * METERS_PER_MILE);
        let needed = (v_mps * v_mps - target_mps * target_mps).max(0.0) / (2.0 * gap_m);
        let idle = self.decel_lane_brake <= 0.0;
        if needed < RAMP_ASSIST_DECEL_RELEASE_MPS2
            || (idle && needed < RAMP_ASSIST_DECEL_START_MPS2)
        {
            self.decel_lane_brake = 0.0;
            return;
        }
        self.decel_lane_brake = assist_servo_brake(self.decel_lane_brake, needed, &self.trip.truck);
        self.trip.truck.throttle = 0.0;
        self.trip.truck.brake = self.trip.truck.brake.max(self.decel_lane_brake);
        if self.decel_lane_assist_said {
            return;
        }
        self.decel_lane_assist_said = true;
        // ROUTE: an automation naming that it just took the brakes, the same
        // class as every other assist's slowing line.
        let who = if ctx.settings.exit_speed_assist {
            "Exit speed assistance"
        } else {
            "Route-transition assistance"
        };
        ctx.say_event_with(
            format!("{who} slowing for the ramp."),
            SayEvent::queued()
                .priority(EventPriority::Route)
                .category(SpeechCategory::Confirmation),
        );
    }
}
