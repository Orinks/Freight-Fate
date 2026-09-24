//! Rollover in the cab: the warning before a bend costs anything, and what
//! going over does to the run.
//!
//! The physics is `ff_core::sim::vehicle` (`roll.rs`): one sideways pull
//! against one threshold, for a mapped bend and an exit ramp's curve alike.
//! This is the game layer around it.
//!
//! **The warning comes before the cost.** A bend starts costing the truck at
//! the first of two speeds: where the load starts working against its straps
//! (the roll model's warning share of this load's threshold) and, with the
//! lane work the driver's, where the tires can no longer hold the lane and the
//! truck runs wide. The warning names that speed and fires while slowing to
//! it is still possible -- inside the bend at once, or on the approach once
//! the road left is no more than the truck needs to shed to it. It used to be
//! a flat 15 mph over the sign, and a hot ramp curve could cost the load and
//! put the truck on the shoulder with nothing said (agent drive, 2026-09-24:
//! 47 into a 35 ramp curve, partial lane keeping, cargo already moving).
//!
//! **Going over reuses the catastrophic path the game already has.** Damage
//! runs to the out-of-service wall and the freight to scrap, the truck is
//! stopped where it lies, and `recover_out_of_service` does what it does for
//! any truck that may not be driven: road service and the bill for an owner-
//! operator, a grounded tractor and a yard spare for a company driver. The
//! receiver refuses the load at the dock, as it refuses any load in that state.

use ff_core::data::curves::{min_radius_ft, superelevation_at, RouteCurve, SUPERELEVATION_BUILT};
use ff_core::models::cargo_condition::{cargo_condition_text, CARGO_REJECT_PCT};
use ff_core::sim::lane::{MAX_CREDITED_BANK, MAX_ROAD_LATERAL_G, MAX_STEER_LATERAL_G};
use ff_core::sim::vehicle::{BrakeApplication, G, MPS_TO_MPH, M_PER_FT};
use ff_core::speech_pacing::SpeechCategory;

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;

/// Seconds between a warning and the brakes going on. READ: the brake
/// reaction time the Green Book's stopping sight distance is built on (AASHTO
/// 2018, 3.2.2.2), which covers the 90th percentile of drivers.
pub const CURVE_WARN_REACTION_S: f64 = 2.5;
/// The deceleration a warned driver is assumed to use, m/s2, where the truck
/// can deliver it. READ: 11.2 ft/s2, the Green Book's stopping sight distance
/// rate, "comfortable for most drivers" (AASHTO 2018, 3.2.2.3).
pub const CURVE_WARN_DECEL_MPS2: f64 = 11.2 * 0.3048;

/// The ramp curve's identity for the once-per-curve warning. Mapped bends go
/// by their start milepost, which is never negative.
const RAMP_CURVE_ID: f64 = -1.0;

/// A curve the truck is in or heading into, as the warning sees it.
struct CurveInPlay {
    id: f64,
    /// Road to its start, miles; 0 inside it.
    ahead_mi: f64,
    radius_ft: f64,
    /// The bank the roll model credits.
    roll_bank: f64,
    /// The bank the lane model credits.
    lane_bank: f64,
    phrase: String,
}

impl DrivingState {
    /// The bank a mapped bend is built with: the same `superelevation_at` the
    /// advisory was priced with and the lane model credits.
    pub fn bend_bank(&self, bend: &RouteCurve) -> f64 {
        superelevation_at(
            (bend.min_radius_ft as f64).max(1.0),
            self.trip.leg_design_speed_mph(),
        )
    }

    /// The ramp curve's radius and the bank the roll model credits it.
    ///
    /// The radius is the AASHTO minimum for the exit speed, which assumes the
    /// 8 percent bank the most permissive state builds; the roll model credits
    /// the 6 percent both cited manuals build to (`SUPERELEVATION_BUILT`), the
    /// cautious reading of the same geometry. The lane model credits the ramp
    /// no bank at all (`update_lane`), and the two are kept apart on purpose.
    pub fn ramp_curve_geometry(&self) -> Option<(f64, f64)> {
        let layout = self.ramp_layout?;
        Some((
            min_radius_ft(layout.curve_mph).max(1.0),
            SUPERELEVATION_BUILT,
        ))
    }

    /// The fastest the truck takes a curve before it costs anything, in mph:
    /// the roll model's safe speed for this load and, with the lane work the
    /// driver's, the speed past which the lane model cannot hold the curve and
    /// the truck runs wide.
    ///
    /// That second speed is the lane model's own ceiling, read rather than
    /// restated: the tires' `MAX_ROAD_LATERAL_G` plus the credited bank when
    /// curve assistance supplies the wheel the curve wants, and the steering
    /// cap `MAX_STEER_LATERAL_G` when only the driver and lane keeping's
    /// correction steer; both scaled by grip (`LaneKeeping::update`).
    pub fn curve_safe_mph(
        &self,
        ctx: &GameContext,
        radius_ft: f64,
        roll_bank: f64,
        lane_bank: f64,
    ) -> f64 {
        let truck = &self.trip.truck;
        let roll = truck.roll_safe_mph(radius_ft, roll_bank);
        if !ctx.settings.lane_is_manual() {
            return roll;
        }
        let grip = truck.effective_grip().clamp(0.0, 1.0);
        let road_g = MAX_ROAD_LATERAL_G + lane_bank.clamp(0.0, MAX_CREDITED_BANK);
        let steer_g = if ctx.settings.curve_speed_assist {
            road_g
        } else {
            MAX_STEER_LATERAL_G.min(road_g)
        };
        let hold_g = steer_g * grip;
        let drift = (hold_g * G * radius_ft.max(0.0) * M_PER_FT).sqrt() * MPS_TO_MPH;
        roll.min(drift)
    }

    /// [`Self::curve_safe_mph`] for a mapped bend.
    pub fn bend_safe_mph(&self, ctx: &GameContext, bend: &RouteCurve) -> f64 {
        let bank = self.bend_bank(bend);
        self.curve_safe_mph(ctx, bend.min_radius_ft as f64, bank, bank)
    }

    /// [`Self::curve_safe_mph`] for the ramp curve, or None off a laid-out
    /// ramp.
    pub fn ramp_curve_safe_mph(&self, ctx: &GameContext) -> Option<f64> {
        let (radius, bank) = self.ramp_curve_geometry()?;
        Some(self.curve_safe_mph(ctx, radius, bank, 0.0))
    }

    /// Road the truck needs to come down to `target_mph` once warned, miles:
    /// the reaction, then the Green Book rate or what this truck's brakes can
    /// do on this grade with this load, whichever is less.
    fn curve_warn_reach_mi(&self, target_mph: f64) -> f64 {
        let truck = &self.trip.truck;
        let v = truck.velocity_mps.max(0.0);
        let target = (target_mph / MPS_TO_MPH).clamp(0.0, v);
        let can = truck.braking_decel_mps2(BrakeApplication::Service(1.0)) + G * truck.grade
            - truck.surge_decel_penalty_mps2();
        let decel = CURVE_WARN_DECEL_MPS2.min(can).max(0.1);
        let metres = v * CURVE_WARN_REACTION_S + (v * v - target * target) / (2.0 * decel);
        // The road passes `scale` times faster than the truck slows.
        metres * self.trip.effective_time_scale().max(1.0) / METERS_PER_MILE
    }

    /// The curve the warning is about: the one under the truck, else the next
    /// inside the truck's own braking reach.
    ///
    /// On the approach, only a curve nothing else is already slowing for: a
    /// mapped bend once its call has gone out (the call names it first, and
    /// from the call on the clock runs real) and not while curve assistance
    /// has it; the ramp curve not while an assist is braking the lane down to
    /// the exit speed, unless the driver's foot is overriding it. Inside the
    /// curve, whatever is driving.
    fn curve_in_play(&self, ctx: &GameContext) -> Option<CurveInPlay> {
        if self.ramp_mi.is_some() {
            let (radius_ft, roll_bank) = self.ramp_curve_geometry()?;
            let ahead_mi = if self.ramp_curve_radius_ft().is_some() {
                0.0
            } else {
                let assisted = Self::ramp_speed_assisted(ctx) && !Self::driver_accelerating(ctx);
                self.deceleration_lane_left_mi().filter(|_| !assisted)?
            };
            return Some(CurveInPlay {
                id: RAMP_CURVE_ID,
                ahead_mi,
                radius_ft,
                roll_bank,
                lane_bank: 0.0,
                phrase: "Ramp curve".to_string(),
            });
        }
        let position = self.trip.position_mi;
        let (ahead_mi, bend) = match self.trip.curve_at(position).filter(|c| !c.connector) {
            Some(bend) => (0.0, bend),
            None => {
                // Look as far as the truck needs to shed to a crawl; anything
                // further has time left to be warned about later.
                if ctx.settings.curve_speed_assist {
                    return None;
                }
                let reach = self.curve_warn_reach_mi(0.0);
                let (ahead, bend) = self.trip.next_curve_within(reach)?;
                if bend.connector || !self.trip.curve_called(&bend) {
                    return None;
                }
                (ahead, bend)
            }
        };
        let bank = self.bend_bank(&bend);
        Some(CurveInPlay {
            id: bend.start_mi,
            ahead_mi,
            radius_ft: bend.min_radius_ft as f64,
            roll_bank: bank,
            lane_bank: bank,
            phrase: self.pacenote_phrase(&bend),
        })
    }

    /// Say once per curve that it is being taken too fast for this load,
    /// while there is still road to fix it.
    pub fn update_curve_warning(&mut self, ctx: &mut GameContext) {
        let Some(curve) = self.curve_in_play(ctx) else {
            self.curve_warned_mi = None;
            return;
        };
        if self.curve_warned_mi == Some(curve.id) {
            return;
        }
        let safe = self.curve_safe_mph(ctx, curve.radius_ft, curve.roll_bank, curve.lane_bank);
        if self.trip.truck.speed_mph() <= safe {
            return;
        }
        if curve.ahead_mi > 0.0 && curve.ahead_mi > self.curve_warn_reach_mi(safe) {
            return;
        }
        self.curve_warned_mi = Some(curve.id);
        let slow_to = ctx.settings.speed_text(safe.floor().max(1.0));
        ctx.say_event_with(
            format!("{}, too fast. Slow to {slow_to}.", curve.phrase),
            SayEvent::new().category(SpeechCategory::Safety),
        );
    }

    /// Put the truck over if the bend is asking more than its threshold.
    /// Runs after the bend's geometry is on the truck for this frame.
    pub fn update_rollover(&mut self, ctx: &mut GameContext) {
        if self.recovering || self.trip.truck.roll_share() < 1.0 {
            return;
        }
        self.roll_over(ctx);
    }

    /// The truck goes over: the freight is scrap, the truck may not be
    /// driven, and the run carries on the way it does after any other
    /// out-of-service event.
    pub fn roll_over(&mut self, ctx: &mut GameContext) {
        let on_ramp = self.ramp_mi.is_some();
        ctx.audio.play("vehicle/collision");
        ctx.controller.rumble.impact(1.0);
        self.curve_servo = None;
        self.disarm_speed_control(ctx);
        {
            let truck = &mut self.trip.truck;
            truck.velocity_mps = 0.0;
            truck.throttle = 0.0;
            let to_the_wall = (DAMAGE_OUT_OF_SERVICE_PCT - truck.damage_pct).max(0.0);
            truck.add_damage(to_the_wall, true);
            truck.add_cargo_damage(100.0);
        }
        // This line names what happened to the load, so the condition cue
        // must not say it again a frame later.
        self.cargo_cue_at = self.cargo_cue_at.max(CARGO_REJECT_PCT);
        let liquid = self.trip.truck.liquid.is_some();
        let words = cargo_condition_text(self.trip.truck.cargo_damage_pct, liquid);
        let place = if on_ramp { "ramp curve" } else { "bend" };
        let message = if self.terse_speech(ctx) {
            format!("Rolled over in the {place}. Load {words}.")
        } else {
            format!(
                "The truck rolled over in the {place}. The load is {words}, and the receiver \
                 will refuse it."
            )
        };
        ctx.say_event_with(message, SayEvent::new().category(SpeechCategory::Safety));
        // The wall is reached here, not by the band watcher: settlement
        // grades the run by the deepest band, and the recovery line below is
        // the announcement for where the truck lands.
        self.worst_damage_band = self.worst_damage_band.max(DAMAGE_BAND_OUT_OF_SERVICE);
        self.damage_band = DAMAGE_BAND_OUT_OF_SERVICE;
        self.recover_out_of_service(ctx);
    }
}
