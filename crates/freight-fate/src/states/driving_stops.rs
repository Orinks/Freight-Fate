//! Where the stop cues live, derived from what the truck can actually do
//! (port of `freight_fate/states/driving_stops.py`).
//!
//! Every stop cue in the game used to be a fixed distance: the stop-bar tick
//! started at three hundred feet, the held tone began at sixty, and the
//! route-transition assist mapped its pedal against a nominal three metres per
//! second squared. Those numbers were right for a dry van on level tarmac and
//! quietly wrong for everything else -- hot brakes, worn shoes, ice, a
//! downgrade, a partly filled tank running forward under braking.
//!
//! That mattered more here than it would in a game you can look at. A blind
//! driver's entire model of *where do I stop* is the tick's rate accelerating
//! from one and a tenth seconds to a seventh of a second. Leave the range fixed
//! and the cue says exactly what it has always said while the truck needs half
//! as much road again -- so the driver does precisely what the instrument told
//! them and puts the tractor into the intersection. That is not difficulty. It
//! is an ambush built into the game's most trusted affordance.
//!
//! So the geometry is computed from `sim::vehicle`'s stopping distance instead,
//! which already knows about fade, wear, load, grip and grade, and now about
//! liquid surge as well. Every original constant survives as a floor: a truck
//! that can stop shorter than the old numbers hears the bar exactly where it
//! always did, and nothing changes for the freight that was already fine.

use ff_core::sim::vehicle::TruckState;

use crate::states::driving_core::{
    RAMP_ASSIST_DECEL_START_MPS2, RAMP_ASSIST_FULL_DECEL_MPS2, RAMP_ASSIST_RELEASE_BAND,
    RAMP_BAR_REACTION_S, RAMP_BAR_SOLID_MI, RAMP_BAR_TICK_RANGE_MI,
};

/// `bar_tick_range_mi(truck)`: how far out the stop-bar tick starts, for this
/// truck as it is now.
///
/// Carries a reaction allowance as well as the stopping distance: the bar is
/// the one place where the cue *is* the instrument, so its range has to pay
/// for the listening too.
pub fn bar_tick_range_mi(truck: &TruckState) -> f64 {
    let needed = truck.stopping_distance_mi(None, RAMP_BAR_REACTION_S, true) + RAMP_BAR_SOLID_MI;
    RAMP_BAR_TICK_RANGE_MI.max(needed)
}

/// `bar_solid_zone_mi(truck)`: where the ticks fuse into the held tone -- the
/// last of the leeway.
///
/// Sixty feet is an owner spec written into the manual, so unlike the tick
/// range this does not simply become "whatever this truck needs" -- deriving
/// it from speed would move the held tone for every dry van on a brisk
/// approach, and a continuous tone arriving earlier for everybody is exactly
/// the sensory load this game spends carefully.
///
/// It extends by one thing only: the extra road the *liquid* is asking for.
/// That is zero for every other load, so nothing else changes, and it is the
/// one case where sixty feet is a promise the truck cannot keep -- the wave
/// is still coming when the driver thinks the stop is made.
pub fn bar_solid_zone_mi(truck: &TruckState) -> f64 {
    RAMP_BAR_SOLID_MI + truck.surge_stopping_penalty_mi(None)
}

/// `assist_full_decel_mps2(truck)`: denominator for mapping needed
/// deceleration onto brake application.
///
/// Against a fixed nominal figure the assist under-brakes every truck that
/// cannot make that figure -- which is exactly the set of trucks that need the
/// pedal hardest. Taking the lower of nominal and achievable means the assist
/// can only ever press harder than it used to, never softer, so no load that
/// was already being handled correctly sees any change.
pub fn assist_full_decel_mps2(truck: &TruckState) -> f64 {
    0.5f64.max(RAMP_ASSIST_FULL_DECEL_MPS2.min(truck.full_service_decel_mps2()))
}

/// `arrival_servo_brake(applied, needed_mps2, truck)`: the application an
/// ARRIVAL should be holding -- the stop profile itself.
///
/// [`assist_servo_brake`] below is for a bar -- a stop sign, a light -- and it
/// floors the pedal at the assist's own start rate, because at a bar stopping
/// a little short is fine and the floor is what keeps the pedal from fanning
/// on a long approach. A facility gate is the opposite case: it opens AT the
/// point, a truck halted a length short of it never arrives, and the road in
/// is short. So this has no floor. It asks for exactly the deceleration that
/// brings the truck to rest at the point, from the moment the arrival begins,
/// and it rises the instant the demand does. Because the demand on a uniform
/// stop is monotone there is nothing to fan; the release band is kept only so
/// a demand that dips a hair under the pedal does not cost an application
/// coming back.
///
/// Floored at the start rate, the arrival waited until the road needed
/// 0.6 m/s2 -- about 35 metres out at street speed -- then chased a demand
/// that climbs faster than the pedal follows it, and crossed the gate at
/// 12 mph with the brake at full (bench, 2026-08-21).
pub fn arrival_servo_brake(applied: f64, needed_mps2: f64, truck: &TruckState) -> f64 {
    let full = assist_full_decel_mps2(truck);
    let wanted = 1.0f64.min(0.0f64.max(needed_mps2) / full);
    if wanted > applied {
        return wanted;
    }
    if wanted < applied - RAMP_ASSIST_RELEASE_BAND {
        return wanted;
    }
    applied
}

/// `assist_servo_brake(applied, needed_mps2, truck)`: the application a
/// stopping assist should be holding right now.
///
/// Two things keep it steady rather than fanning, which matters because the
/// air system charges a whole brake application every time the pedal RISES:
///
/// The floor is the assist's own trigger deceleration mapped through the same
/// denominator the demand is, so at the moment the assist first presses, floor
/// and demand agree. A flat floor of a third of the pedal against a trigger of
/// 0.6 m/s2 could not agree with anything: the floor took off two thirds more
/// speed than the trigger asked for, the demand collapsed under it, the assist
/// let go, the demand climbed back, and the pedal went round again -- 276
/// applications on one flat approach to a stop sign, 125 psi down to 40, the
/// spring brakes on and the truck stopped in the road short of the bar (bench
/// trace, 2026-08-11).
///
/// And the pedal follows a falling demand only once the fall is worth a
/// release. Easing off is free; it is coming back on that costs air.
pub fn assist_servo_brake(applied: f64, needed_mps2: f64, truck: &TruckState) -> f64 {
    let full = assist_full_decel_mps2(truck);
    let wanted = 1.0f64.min((RAMP_ASSIST_DECEL_START_MPS2 / full).max(needed_mps2 / full));
    if wanted > applied {
        return wanted;
    }
    if wanted < applied - RAMP_ASSIST_RELEASE_BAND {
        return wanted;
    }
    applied
}
