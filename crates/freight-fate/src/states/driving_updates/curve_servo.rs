//! The proactive half of curve speed assistance: a servo armed by the curve
//! call that brakes the truck down to the bend's advisory ON THE APPROACH,
//! holds it through the chain, and lets go past the commit tail.
//!
//! Until this existed the assist had one proactive move, and only under
//! adaptive cruise: cap cruise's working target to the advisory. Everything
//! else was reactive -- `update_lane` braked once the truck was already
//! inside the bend and over the number, which is after the load has started
//! moving. Cruise's own easing is a bounded ramp of its set point, so a hot
//! bend still arrived early; the speed keeper knew about street turns but
//! not mapped bends; a manual driver got the words and nothing else. The
//! owner drove US-83 near Junction, Texas, with every assist on, and cruise
//! carried the truck into a 35 mph bend at 90 km/h: "Sharp left: too fast,
//! drifting to the outside", and the load shifted 12, then 31 percent over
//! two bends (2026-09-01). Ruling that night: assists should handle curves
//! better to avoid load shifting damage.
//!
//! The target is the advisory itself, not the advisory plus a margin. The
//! cargo model moves freight past 0.40 g of lateral pull, geometric from the
//! bend's own radius, and the shipped advisories bake out near 0.30 g -- so
//! on a typical bend the load starts moving about fifteen percent over the
//! sign, and on a bend tighter than its sign (the owner's, 197 feet at 35)
//! the sign IS the line. A chain's tightest number wins, exactly as cruise's
//! easing cap already reasons (Darren's NY-12 pair, 2026-08-23).
//!
//! The controller is the arrival assist's, not a new one: the uniform shed
//! `(v^2 - t^2) / 2d`, net of what the road already takes off, mapped onto
//! the pedal by `arrival_servo_brake`, which rises the instant the demand
//! does and releases only when the fall is worth an application. The brake
//! is applied by `max`, so a driver braking harder is never fought, and the
//! throttle is never touched. Their own brake key cancels the servo for the
//! bend, as it cancels every other assist.

use ff_core::speech_pacing::{EventPriority, SpeechCategory};

use crate::app::{GameContext, SayEvent};
use crate::states::driving::DrivingState;
use crate::states::driving_core::*;
use crate::states::driving_speed_control::KEEPER_SNUB_DECEL_MPS2;
use crate::states::driving_stops::arrival_servo_brake;

/// Inside the bend, the truck is over the number by this much before the
/// servo is asking for its whole snub; under it the demand tapers to nothing
/// at the number itself. Below the number the pedal is released and the
/// road's own drag holds the rest, except on a downgrade, where the hill is
/// held until the truck is this far under.
pub const CURVE_SERVO_HOLD_BAND_MPH: f64 = 1.0;

/// One bend's proactive speed job, from the curve call to the commit tail.
#[derive(Debug, Clone, PartialEq)]
pub struct CurveServo {
    /// The chain's tightest advisory: the speed the truck has to be doing
    /// by `start_mi` and hold to `hold_to_mi`.
    pub target_mph: f64,
    /// Where the first bend of the chain begins; the approach shed aims here.
    pub start_mi: f64,
    /// The chain's end plus the commit tail; past it the servo lets go.
    pub hold_to_mi: f64,
    /// The application the servo itself is holding, for the release band.
    pub brake: f64,
    /// Whether the call named the assist, so a release can be paired to it.
    pub spoke: bool,
}

impl DrivingState {
    /// Arm the servo for a bend the curve call just announced.
    ///
    /// A second call inside the first's hold -- a bend just past the link
    /// gap, so it earned its own words -- merges rather than replaces: the
    /// tighter number, the earlier start, the later end. Replacing would
    /// have released the first bend's hold in the middle of it.
    pub fn arm_curve_servo(
        &mut self,
        target_mph: f64,
        start_mi: f64,
        hold_to_mi: f64,
        spoke: bool,
    ) {
        let merged = match self.curve_servo.take() {
            Some(current) => CurveServo {
                target_mph: current.target_mph.min(target_mph),
                start_mi: current.start_mi.min(start_mi),
                hold_to_mi: current.hold_to_mi.max(hold_to_mi),
                brake: current.brake,
                spoke: current.spoke || spoke,
            },
            None => CurveServo {
                target_mph,
                start_mi,
                hold_to_mi,
                brake: 0.0,
                spoke,
            },
        };
        self.curve_servo = Some(merged);
    }

    /// The servo's pedal for this frame. Runs with the other assists' floors,
    /// after cruise and the keeper and ahead of the physics step, so the
    /// application it sets is the one the truck integrates.
    pub fn update_curve_speed_servo(&mut self, ctx: &GameContext) {
        let Some(servo) = self.curve_servo.as_ref() else {
            self.trip.curve_shed_active = false;
            return;
        };
        let position = self.trip.position_mi;
        if position > servo.hold_to_mi || self.trip.finished || !ctx.settings.curve_speed_assist {
            // Past the tail: let go silently, the way cruise's cap climbs
            // back silently -- a release line on every bend of a cluster
            // would chant.
            self.curve_servo = None;
            self.trip.curve_shed_active = false;
            return;
        }
        let v = self.trip.truck.velocity_mps;
        let target = servo.target_mph / MPH_PER_MPS;
        // What the road takes off on its own, m/s2: positive when it slows
        // the truck, negative when gravity is pushing it into the bend.
        let road = self.trip.truck.resistance_force() / self.trip.truck.gross_mass_kg();
        // The road passes `scale` times faster than the truck slows: the
        // trip moves the milepost by speed times dt times the compression,
        // and the physics sheds speed at real dt. A warned bend runs the
        // clock real (the pacenote's decompression) down to the advisory
        // plus its margin, so this is 1 for nearly the whole shed -- but
        // the last few miles an hour, and the hold through the bend, are
        // back on the compressed clock, and a profile priced in real
        // metres there arrives over the number. The keeper prices its ease
        // the same way (`keeper_ease_mi`).
        //
        // Set the flag FIRST, then read the scale, because the flag is one of
        // the things `effective_time_scale` answers with. Read the other way
        // round it reported last frame's clock, and on the one frame the
        // truck crossed back over the number -- flag still false, the
        // pacenote's own decompression already let go -- the demand was
        // priced seventeen times too high and the pedal took the rise
        // (review finding, 2026-09-19). The clock stays real while there is
        // still speed to take off, so the shed is priced in the same seconds
        // the truck slows in; see `Trip::effective_time_scale`.
        self.trip.curve_shed_active = v > target;
        let scale = self.trip.effective_time_scale().max(1.0);
        let band = CURVE_SERVO_HOLD_BAND_MPH / MPH_PER_MPS;
        let shed: Option<f64> = if position < servo.start_mi {
            // The approach: the uniform shed that lands the truck ON the
            // number at the bend's start. Recomputed every frame against the
            // road left, so a truck coasting slower than the profile sees
            // its demand climb and the pedal follow.
            let remaining_m = ((servo.start_mi - position) * METERS_PER_MILE).max(0.5);
            // Plus what the surge will take back. A tank the liquid can
            // move in cannot hold the dry-van rate, so the demand has to ask
            // for the shortfall as well or the bend arrives over its number
            // (owner, 2026-09-20).
            let surge = self.trip.truck.surge_decel_penalty_mps2();
            (v > target).then(|| (v * v - target * target) * scale / (2.0 * remaining_m) + surge)
        } else if v > target {
            // Inside the chain and over the number: the keeper's own snub
            // rate, net of the grade like everything else here. A profile to
            // the chain's END would let the truck ride the whole corner over
            // its advisory and only arrive at the number where it no longer
            // matters.
            //
            // FEATHERED across the band, not switched at its edge: nothing at
            // the number, the full snub a band over it, and a straight line
            // between. Switched, the snub took the truck a hair under the
            // edge, the hold below kept it there, and anything that nudged it
            // back -- adaptive cruise holds this same bend, on this same edge
            // -- made the whole snub again: 0.16 to 0.36 and back every other
            // frame, 125 psi to the spring brakes with cruise on (agent
            // drive, AZ-260, 2026-09-18). Latched down to the number it
            // still came round every five seconds. A pedal that answers how
            // far over the truck is settles where the push on it is met and
            // stays there, which is what a foot does.
            Some(KEEPER_SNUB_DECEL_MPS2 * scale * ((v - target) / band).min(1.0))
        } else {
            None
        };
        // What the pedal has to answer, net of the road: the shed, less what
        // the road takes off by itself -- or, with nothing left to shed and
        // GRAVITY pushing, the hill.
        //
        // "The road's own drag holds the rest" is only true where the road is
        // taking speed off. On a downgrade it is adding it, so letting go at
        // the number handed the truck straight back to the hill, which
        // carried it over again within a few frames, and the snub came back
        // as a fresh application each time -- ten a second down the 6.1
        // percent pitch into the AZ-260 hairpin, 125 psi to the spring brakes
        // in one bend (owner's drive, 2026-09-18; bench trace: 0.364,
        // released, 0.364, released, six frames apart). The approach did the
        // same at the mouth of the bend, twenty clunks in a row.
        //
        // So under the number the hill is still held, tapering to nothing a
        // band below it. Tapered and not switched for the same reason the
        // snub is: the pedal is mapped a little strong on purpose, so a held
        // hill drifts the truck down, and a hold that let go at an edge let
        // the hill bring it straight back -- a fresh application every four
        // seconds. On the taper the truck settles where the pedal and the
        // hill agree and the application is made once.
        let demand = match shed {
            Some(shed) => Some(shed - road),
            None if road < 0.0 && v > target - band => {
                Some(-road * ((v - (target - band)) / band).min(1.0))
            }
            None => None,
        };
        let applied = demand.map_or(0.0, |demand| {
            arrival_servo_brake(servo.brake, demand, &self.trip.truck)
        });
        if let Some(servo) = self.curve_servo.as_mut() {
            servo.brake = applied;
        }
        self.trip.truck.brake = self.trip.truck.brake.max(applied);
    }

    /// The driver's own brake during the servo: the bend is theirs again,
    /// said the way every other assist says it -- and only if the servo had
    /// spoken, so a run that stayed quiet (curve callouts off, or cruise's
    /// easing line already covering it) never leaves a lone release hanging.
    pub fn cancel_curve_servo(&mut self, ctx: &mut GameContext) {
        let Some(servo) = self.curve_servo.take() else {
            return;
        };
        if !servo.spoke {
            return;
        }
        // ROUTE, not the ambient default: an automation just released the
        // pedals (the automation-handoff rule, 2026-08-20).
        ctx.say_event_with(
            "Curve assistance released.",
            SayEvent::queued()
                .priority(EventPriority::Route)
                .category(SpeechCategory::Confirmation),
        );
    }
}
