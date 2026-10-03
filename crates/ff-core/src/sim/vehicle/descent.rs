//! `TruckState::safe_descent_mph`: the speed this truck, at this weight, can
//! hold a downgrade at without cooking its drums.
//!
//! # Where the method comes from
//!
//! FHWA's Grade Severity Rating System (GSRS; Myers, Ashkenas and Johnson,
//! "Feasibility of a Grade Severity Rating System", FHWA-RD-79-116, and its
//! users' manual FHWA-IP-88-015) is what US highway
//! agencies use to put a number on a downgrade: for a gross weight and a
//! grade it finds the highest speed at which the service brakes, doing what
//! the engine and the air do not, stay under a brake-temperature limit. That
//! number is what a weight-specific speed sign at the top of a mountain pass
//! posts. The method is **read**; the numbers it runs on here are the
//! truck's own:
//!
//! * the force the drums must hold is gravity less drag and rolling less
//!   the full engine brake -- `resistance_force` and `jake_brake_force` on a
//!   copy of this truck, so there is one copy of that physics in the game;
//! * the engine brake works in the gear an automatic holds for it
//!   (`JAKE_MAX_RPM` with the snub band above the target on top, so the
//!   hold never spins the engine into the box's protective upshift);
//! * the drum temperature that force settles at comes from the same heat
//!   model `update_temps` runs (see `DrivingState::retarder_warranted` in
//!   the game crate for the derivation):
//!   `T = AMBIENT_C + F v / (C (BRAKE_COOL_BASE_PER_S + BRAKE_COOL_SPEED_PER_S sqrt v))`.
//!
//! What that gives the default truck (band 2.5 mph; "-" is no number needed
//! at [`DESCENT_SEARCH_TOP_MPH`]):
//!
//! ```text
//!   gross        4%   5%  5.8%  6%   7%   8%  10%
//!   40,000 lb    -    -    -    -    -    -    -
//!   60,000 lb    -    -    -    -    -   45   30
//!   76,000 lb    -    -   65   65   45   30   20
//!   80,000 lb    -    -   65   65   30   30   20
//! ```
//!
//! The steady state rather than GSRS's length-limited temperature, on
//! purpose: a speed the drums can hold indefinitely is safe on any length
//! of that grade, and a speed chosen at the top of the hill does not have
//! to be re-chosen halfway down. It is the conservative reading of the
//! same rule.

use super::{TruckState, AMBIENT_C, BRAKE_COOL_BASE_PER_S, BRAKE_COOL_SPEED_PER_S, JAKE_STAGES};
use crate::sim::transmission::JAKE_MAX_RPM;

/// GSRS's brake-temperature limit, 500 degrees Fahrenheit. **Read**: the
/// limit the Grade Severity Rating System rates every grade against,
/// chosen there as the point past which fade starts to take real braking
/// away. The game's own shoes start fading at 400 C new and cooler worn
/// (`brake_fade_onset_c`); the lower of the two applies, so a truck on worn
/// shoes gets a slower number.
pub const GSRS_BRAKE_LIMIT_C: f64 = 260.0;

/// Speeds are posted in multiples of five miles an hour. **Read**: MUTCD
/// (2009) Section 2B.13, which a weight-specific speed sign follows like
/// any other speed sign -- and it keeps the spoken number from wandering by
/// one as the weight burns off.
pub const DESCENT_SPEED_STEP_MPH: f64 = 5.0;

/// The fastest speed the search starts from. **Assumed**: above every truck
/// limit in the country (Texas posts 75 for trucks on its fastest roads), so
/// a grade that is safe here needs no descent speed at all.
pub const DESCENT_SEARCH_TOP_MPH: f64 = 80.0;

/// The slowest descent speed the search will name. **Assumed**: a grade the
/// truck cannot hold at ten is a runaway-ramp grade, and a lower number
/// would only postpone the warning that says so.
pub const DESCENT_SEARCH_FLOOR_MPH: f64 = 10.0;

const MPS_PER_MPH: f64 = 0.44704;

impl TruckState {
    /// The highest multiple of five mph at or under
    /// [`DESCENT_SEARCH_TOP_MPH`] at which this truck holds `grade` (a
    /// fraction, negative downhill) with full engine brake in the gear an
    /// automatic would hold, and the drums settling no hotter than
    /// [`GSRS_BRAKE_LIMIT_C`]. `band_mph` is how far over the target the
    /// controller lets the truck run before it snubs, so the chosen gear
    /// still has room under `JAKE_MAX_RPM` at the top of that band.
    ///
    /// None when the grade needs no descent speed at all: the truck holds
    /// it at the top of the search.
    pub fn safe_descent_mph(&self, grade: f64, band_mph: f64) -> Option<f64> {
        if grade >= 0.0 {
            return None;
        }
        let limit_c = GSRS_BRAKE_LIMIT_C.min(self.brake_fade_onset_c());
        let mut probe = self.clone();
        probe.grade = grade;
        probe.throttle = 0.0;
        probe.brake = 0.0;
        probe.engine_brake_stage = JAKE_STAGES;
        probe.engine_on = true;
        probe.transmission.shift_timer = 0.0;
        probe.transmission.clutch = 0.0;
        let mut mph = DESCENT_SEARCH_TOP_MPH;
        while mph > DESCENT_SEARCH_FLOOR_MPH {
            if probe.drums_settle_c(mph, band_mph) <= limit_c {
                return (mph < DESCENT_SEARCH_TOP_MPH).then_some(mph);
            }
            mph -= DESCENT_SPEED_STEP_MPH;
        }
        Some(DESCENT_SEARCH_FLOOR_MPH)
    }

    /// Where the drums settle holding `mph` on `self.grade`, with the engine
    /// brake at `self.engine_brake_stage` in the lowest gear that keeps
    /// `mph + band_mph` under the engine-protection ceiling.
    fn drums_settle_c(&mut self, mph: f64, band_mph: f64) -> f64 {
        let v = mph * MPS_PER_MPH;
        self.velocity_mps = v;
        let top_rpm_at =
            |truck: &TruckState, gear: i32| truck.coupled_rpm(Some(gear)) * (mph + band_mph) / mph;
        let top = self.transmission.num_gears();
        let gear = (1..=top)
            .find(|&gear| top_rpm_at(self, gear) <= JAKE_MAX_RPM)
            .unwrap_or(top);
        self.transmission.gear = gear;
        self.rpm = self.coupled_rpm(Some(gear));
        let drum_force = -self.resistance_force() - self.jake_brake_force();
        if drum_force <= 0.0 {
            return AMBIENT_C; // the engine and the air hold it alone
        }
        let cooling_per_c = self.specs.brake_thermal_mass_j_per_c
            * (BRAKE_COOL_BASE_PER_S + BRAKE_COOL_SPEED_PER_S * v.sqrt());
        AMBIENT_C + drum_force * v / cooling_per_c
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn truck_at(gross_lb: f64) -> TruckState {
        let mut truck = TruckState::default();
        truck.start_engine();
        truck.transmission.automatic = true;
        truck.cargo_kg = gross_lb * 0.453_592 - truck.tare_kg();
        truck
    }

    /// The number is where the drums stop being able to take it: at the
    /// speed named they settle under the GSRS line, five faster they do not.
    #[test]
    fn the_named_speed_is_the_last_one_the_drums_hold() {
        for grade in [-0.058, -0.07, -0.08, -0.10] {
            let truck = truck_at(76_000.0);
            let mph = truck
                .safe_descent_mph(grade, 2.5)
                .expect("a steep grade has a number");
            let mut probe = truck.clone();
            probe.grade = grade;
            probe.throttle = 0.0;
            probe.engine_brake_stage = JAKE_STAGES;
            assert!(
                probe.drums_settle_c(mph, 2.5) <= GSRS_BRAKE_LIMIT_C,
                "{grade}: {mph}"
            );
            if mph + DESCENT_SPEED_STEP_MPH < DESCENT_SEARCH_TOP_MPH {
                assert!(
                    probe.drums_settle_c(mph + DESCENT_SPEED_STEP_MPH, 2.5) > GSRS_BRAKE_LIMIT_C,
                    "{grade}: {mph} is not the fastest safe step"
                );
            }
        }
    }

    /// A heavy truck on the Eisenhower side of I-70 gets a mountain number,
    /// never the highway's: 85 or 77 down seven percent is a runaway.
    #[test]
    fn seven_percent_heavy_is_a_mountain_speed() {
        let mph = truck_at(76_000.0)
            .safe_descent_mph(-0.07, 2.5)
            .expect("a number");
        assert!(
            (30.0..=55.0).contains(&mph),
            "7 percent at 76,000 lb: {mph}"
        );
        assert_eq!(mph % DESCENT_SPEED_STEP_MPH, 0.0);
    }

    /// Weight moves the number the way a weight-specific sign does; a
    /// shallow grade needs none; an empty truck needs less than a full one.
    #[test]
    fn heavier_is_slower_and_shallow_is_free() {
        let heavy = truck_at(80_000.0)
            .safe_descent_mph(-0.06, 2.5)
            .unwrap_or(99.0);
        let light = truck_at(50_000.0)
            .safe_descent_mph(-0.06, 2.5)
            .unwrap_or(99.0);
        assert!(heavy < light, "80k {heavy} against 50k {light}");
        assert_eq!(truck_at(80_000.0).safe_descent_mph(-0.02, 2.5), None);
        assert_eq!(truck_at(80_000.0).safe_descent_mph(0.03, 2.5), None);
    }

    /// Worn, hot-fading shoes get the slower of the two limits.
    #[test]
    fn worn_shoes_are_slower() {
        let fresh = truck_at(76_000.0);
        let mut worn = truck_at(76_000.0);
        worn.brake_wear_pct = 100.0;
        let fresh_mph = fresh.safe_descent_mph(-0.07, 2.5).unwrap_or(99.0);
        let worn_mph = worn.safe_descent_mph(-0.07, 2.5).unwrap_or(99.0);
        assert!(
            worn_mph <= fresh_mph,
            "worn {worn_mph} against fresh {fresh_mph}"
        );
    }
}
