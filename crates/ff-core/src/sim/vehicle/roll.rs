//! Rollover: one model for every bend the truck takes, mapped bend or ramp
//! curve alike.
//!
//! A bend pulls the truck sideways with `v^2 / gR`, less the share its bank
//! carries. The truck rolls over when that pull reaches its static rollover
//! threshold: "the maximum value of lateral acceleration required to bring a
//! vehicle to the point of initiating roll instability", reached on a
//! five-axle combination "when the inside wheels of the semitrailer begin to
//! lift" (NTSB HAR-11/01 2.3.1, READ). A loaded truck meets that before its
//! tires let go on a ramp curve (TRB CTBSSP Synthesis 3, READ), which is why
//! the pull is compared with the threshold and not with grip.
//!
//! **The threshold** is `data::corners::rollover_threshold_g`: 0.35 g for a
//! full trailer (NHTSA DOT HS 811 734, READ; NTSB gives the same 0.35 g for a
//! full petroleum tank) up to 0.70 g empty, along UMTRI-83-10's payload
//! centre-of-gravity line (DERIVED there). A bobtail tractor is priced empty.
//!
//! **A tank is priced full whatever its fill in a steady bend.** READ, NTSB
//! HAR-11/01 2.3.4, citing UMTRI-85-35/2: "the rollover thresholds of cargo
//! tank motor vehicles with fill levels of 80 and 100 percent would not differ
//! significantly while negotiating a steady-state curve" -- the liquid running
//! to the outside gives back the lower centre of gravity. Below 80 percent the
//! report is silent, so the same price is ASSUMED there; it is the cautious
//! reading, since a solid load of the same weight would be priced steadier.
//!
//! **The wave is what makes a part-filled tank worse.** Same paragraph: in a
//! transient the liquid swings "twice the level of the steady-state
//! amplitude", so an 80 percent tank can roll "despite a lower CG height" where
//! a full one would not. The steady shift already costs the part-filled tank
//! the stability its lower load would have bought -- `rollover_threshold_g(fill)`
//! less the full price -- so a wave run past its steady place costs that much
//! again in proportion (DERIVED; `LiquidLoad::lateral_overshoot` is the
//! proportion, 0 to 1). A nearly full tank has almost nothing to give back and
//! a half-full one the most, which is the tank endorsement's warning.
//!
//! **The ladder** is shares of that threshold, so it follows the load:
//!
//! - below [`ROLL_WARN_SHARE`], nothing: the bend asks no more of this load
//!   than the most any advisory is ever set at would ask of a full one;
//! - from there, the freight works against its straps (`update_cargo`) and
//!   the driver is warned;
//! - at the threshold itself, the truck goes over.
//!
//! **The margin over the number the cab speaks** is pinned per load in
//! `tests::the_margin_over_the_spoken_advisory`. The game's signs are priced
//! at 0.30 g plus bank (`data::curves::ADVISORY_LATERAL_G`), so a full trailer
//! at its advisory sits at this warning share and goes over a few miles an
//! hour past it; the cab never speaks a number above the load's own safe
//! speed (the game layer's `spoken_advisory_mph`).

use super::{TruckState, G, MPS_TO_MPH, M_PER_FT};
use crate::data::corners::{rollover_threshold_g, TRUCK_ROLLOVER_G};
use crate::data::curves::ADVISORY_ACCEPTABLE_MAX_G;
use crate::sim::lane::{MAX_CREDITED_BANK, MAX_ROAD_LATERAL_G, MAX_STEER_LATERAL_G};
use crate::sim::surge::lateral_accel_mps2;

/// The share of its rollover threshold a bend may ask of the load before it
/// costs anything. DERIVED from two readings: 0.30 g is the most lateral any
/// advisory is established at (FHWA-SA-11-22 3.7), and 0.35 g is where a full
/// trailer goes over, so a full load starts to pay exactly where it is being
/// taken faster than any sign would ever have posted. The same share of any
/// other load's threshold is that point for it.
pub const ROLL_WARN_SHARE: f64 = ADVISORY_ACCEPTABLE_MAX_G / TRUCK_ROLLOVER_G;

impl TruckState {
    /// The static rollover threshold of the load aboard, in g: a steady bend.
    pub fn roll_threshold_g(&self) -> f64 {
        let load = if self.trailer_attached {
            self.roll_load_fraction()
        } else {
            0.0
        };
        rollover_threshold_g(load)
    }

    /// What a part-filled tank's wave can take off the threshold at worst, g.
    fn tank_roll_penalty_g(&self) -> f64 {
        match &self.liquid {
            Some(liquid) if self.trailer_attached && self.cargo_kg > 0.0 => {
                (rollover_threshold_g(liquid.fill_fraction) - rollover_threshold_g(1.0)).max(0.0)
            }
            _ => 0.0,
        }
    }

    /// The threshold this moment, in g: the static one, less what the tank's
    /// sideways wave is costing right now.
    pub fn live_roll_threshold_g(&self) -> f64 {
        // The pull the bend under the truck asks this moment, on the wave's
        // own scale -- the same one `update_liquid` drives it with.
        let pull = lateral_accel_mps2(self.speed_mph(), self.corner_advisory_mph);
        let overshoot = self
            .liquid
            .as_ref()
            .map_or(0.0, |l| l.lateral_overshoot(pull));
        self.roll_threshold_g() - self.tank_roll_penalty_g() * overshoot
    }

    /// The threshold a bend should be planned against, in g: the static one,
    /// less what the wave keeps after a bend entered along its transition and
    /// what it still carries from the last one (`planning_overshoot`). The
    /// assists and the warning price a bend ahead with this.
    pub fn planning_roll_threshold_g(&self) -> f64 {
        let overshoot = self.liquid.as_ref().map_or(0.0, |l| l.planning_overshoot());
        self.roll_threshold_g() - self.tank_roll_penalty_g() * overshoot
    }

    /// The bend's pull in the truck's own frame, in g: geometric, less what
    /// the bank carries. Zero on a straight.
    pub fn roll_lateral_g(&self) -> f64 {
        let lateral = self.corner_lateral_g();
        if lateral <= 0.0 {
            return 0.0;
        }
        (lateral - self.corner_bank.max(0.0)).max(0.0)
    }

    /// How much of its rollover threshold the bend is asking of the truck
    /// right now: 1.0 is over.
    pub fn roll_share(&self) -> f64 {
        self.roll_lateral_g() / self.live_roll_threshold_g().max(1e-6)
    }

    /// The fastest this load takes a bend of `radius_ft` built with `bank`
    /// before the bend costs it anything, in mph: [`ROLL_WARN_SHARE`] of the
    /// planning threshold, bank on top.
    pub fn roll_safe_mph(&self, radius_ft: f64, bank: f64) -> f64 {
        let lateral_g = ROLL_WARN_SHARE * self.planning_roll_threshold_g() + bank.max(0.0);
        (lateral_g * G * radius_ft.max(0.0) * M_PER_FT).sqrt() * MPS_TO_MPH
    }

    /// The fastest the truck takes a curve before it costs anything, in mph:
    /// [`Self::roll_safe_mph`] and, with the lane work the driver's
    /// (`lane_steers` Some), the speed past which the lane model cannot hold
    /// the curve and the truck runs wide.
    ///
    /// That second speed is the lane model's own ceiling, read rather than
    /// restated: the tires' `MAX_ROAD_LATERAL_G` plus the credited bank when
    /// something supplies the wheel the curve wants (`lane_steers` true:
    /// curve assistance or partial lane keeping), and the steering cap
    /// `MAX_STEER_LATERAL_G` when only the driver steers; both scaled by grip
    /// (`LaneKeeping::update`).
    pub fn curve_safe_mph(
        &self,
        radius_ft: f64,
        roll_bank: f64,
        lane_bank: f64,
        lane_steers: Option<bool>,
    ) -> f64 {
        let roll = self.roll_safe_mph(radius_ft, roll_bank);
        let Some(road_steers) = lane_steers else {
            return roll;
        };
        let grip = self.effective_grip().clamp(0.0, 1.0);
        let road_g = MAX_ROAD_LATERAL_G + lane_bank.clamp(0.0, MAX_CREDITED_BANK);
        let steer_g = if road_steers {
            road_g
        } else {
            MAX_STEER_LATERAL_G.min(road_g)
        };
        let hold_g = steer_g * grip;
        let drift = (hold_g * G * radius_ft.max(0.0) * M_PER_FT).sqrt() * MPS_TO_MPH;
        roll.min(drift)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::sim::surge::{LiquidLoad, SPIRAL_TRANSITION_S};
    use crate::sim::vehicle::REFERENCE_CARGO_KG;

    const MPS_PER_MPH: f64 = 1.0 / MPS_TO_MPH;

    fn truck(load_fraction: f64) -> TruckState {
        TruckState {
            trailer_attached: true,
            cargo_kg: REFERENCE_CARGO_KG * load_fraction,
            ..TruckState::default()
        }
    }

    fn tanker(fill: f64) -> TruckState {
        TruckState {
            liquid: Some(LiquidLoad::new(fill, false)),
            ..truck(fill)
        }
    }

    #[test]
    fn the_threshold_follows_the_load() {
        // READ at the ends, DERIVED between: 0.35 full, 0.70 empty.
        for (load, want) in [(1.0, 0.35), (0.5, 0.525), (0.0, 0.70)] {
            let got = truck(load).roll_threshold_g();
            assert!((got - want).abs() < 1e-9, "{load} load: {got}");
        }
        // A tractor with no trailer is priced empty whatever the job says.
        let bobtail = TruckState {
            trailer_attached: false,
            ..truck(1.0)
        };
        assert!((bobtail.roll_threshold_g() - 0.70).abs() < 1e-9);
        assert!((ROLL_WARN_SHARE - 0.30 / 0.35).abs() < 1e-12);
    }

    #[test]
    fn a_tank_in_a_steady_bend_is_priced_full_at_any_fill() {
        // NTSB HAR-11/01 2.3.4: 80 and 100 percent do not differ in a steady
        // curve. Below 80 the same price is the assumed, cautious reading.
        for fill in [0.3, 0.5, 0.8, 0.97] {
            let tank = tanker(fill);
            assert!((tank.roll_threshold_g() - 0.35).abs() < 1e-9, "{fill}");
            // At rest the wave costs nothing.
            assert!((tank.live_roll_threshold_g() - 0.35).abs() < 1e-9, "{fill}");
        }
    }

    #[test]
    fn a_half_full_tank_plans_lower_than_a_full_one() {
        // The wave a transition leaves behind costs the half-full tank the
        // most: it has the most stability to give back.
        let half = tanker(0.5).planning_roll_threshold_g();
        let full = tanker(0.97).planning_roll_threshold_g();
        let van = truck(1.0).planning_roll_threshold_g();
        assert!(
            half < full && full < van + 1e-12,
            "half {half}, full {full}, van {van}"
        );
        // Pinned, so a change to the wave or the transition is deliberate.
        assert!((half - 0.3228).abs() < 0.001, "half-full plans at {half}");
        assert!((full - 0.3482).abs() < 0.001, "full plans at {full}");
    }

    /// Drive a tank at `mph` through a bend signed `advisory` (0: a straight)
    /// for `seconds`, the way `update_liquid` feeds the wave.
    fn hold_bend(t: &mut TruckState, mph: f64, advisory: f64, seconds: f64) {
        const DT: f64 = 0.02;
        t.velocity_mps = mph * MPS_PER_MPH;
        t.corner_advisory_mph = advisory;
        let pull = lateral_accel_mps2(mph, advisory);
        let mut time = 0.0;
        while time < seconds {
            t.liquid.as_mut().unwrap().update(DT, 0.0, pull);
            time += DT;
        }
    }

    #[test]
    fn a_tank_between_two_bends_is_priced_by_the_next_bends_pull() {
        // Bend sweep, 2026-09-24. A half-full tank carried the last bend's
        // swing into the next and was priced at its floor on the first foot:
        // the wave judged against a drive only just begun (Siskiyou, went
        // over at 50), and against a gentle bend's tiny steady shift after a
        // tight one (US-62, went over at 23). A leftover swing costs what the
        // liquid is really carrying past where this bend holds it.
        let floor = |t: &TruckState| t.roll_threshold_g() - t.tank_roll_penalty_g();
        // Out of a 50 bend, a second on the straight, into the next.
        let mut t = tanker(0.5);
        hold_bend(&mut t, 50.0, 50.0, 10.0);
        hold_bend(&mut t, 50.0, 0.0, 1.0);
        t.corner_advisory_mph = 50.0;
        let live = t.live_roll_threshold_g();
        assert!(
            live > floor(&t) + 0.5 * t.tank_roll_penalty_g(),
            "next bend's first foot priced at {live:.3} g, floor {:.3}",
            floor(&t)
        );
        // Out of a 35 bend at 20 and straight into a 60 bend.
        let mut t = tanker(0.5);
        hold_bend(&mut t, 20.0, 35.0, 10.0);
        hold_bend(&mut t, 20.0, 60.0, 0.02);
        let live = t.live_roll_threshold_g();
        assert!(
            live > floor(&t) + 0.5 * t.tank_roll_penalty_g(),
            "gentle bend after a tight one priced at {live:.3} g, floor {:.3}",
            floor(&t)
        );
    }

    #[test]
    fn a_swing_carried_out_of_a_bend_lowers_the_next_plan_without_breathing() {
        // Bend sweep, 2026-09-24: priced from rest, a half-full tank held
        // under its number on Lookout Pass came within 0.98 of rolling with
        // the swing of the bend before, and nothing was said. The plan counts
        // the swing -- but by its energy, so it eases as the wave settles and
        // never rises and falls with it, which is what made the assists pump
        // the brake when the swing's position was tried instead.
        let mut t = tanker(0.5);
        let from_rest = t.planning_roll_threshold_g();
        hold_bend(&mut t, 50.0, 50.0, 10.0);
        // Out of the bend: the pull let go over its transition, then a
        // straight.
        hold_bend(&mut t, 50.0, 0.0, SPIRAL_TRANSITION_S);
        let mut plan = t.planning_roll_threshold_g();
        assert!(
            plan < from_rest - 0.01,
            "out of the bend plans at {plan:.4} g, from rest {from_rest:.4}"
        );
        // Two wave periods of straight: the plan only eases back up, to
        // within the integrator's own wobble (a thousandth of a g; the swing
        // it carries costs ten times that).
        for _ in 0..200 {
            hold_bend(&mut t, 50.0, 0.0, 0.02);
            let next = t.planning_roll_threshold_g();
            assert!(
                next >= plan - 1e-3,
                "the plan fell from {plan:.4} to {next:.4}"
            );
            plan = next;
        }
        assert!(plan <= from_rest + 1e-12);
    }

    /// The slowest speed at which a bend of `radius_ft` puts a tank filled to
    /// `fill` over, entered from a straight and held for `hold_s`; and the
    /// same once the wave has long settled. Wave only: speed is held.
    fn tank_rolls_at(fill: f64, radius_ft: f64) -> (f64, f64) {
        const DT: f64 = 0.02;
        const ADVISORY: f64 = 30.0;
        let worst_share = |mph: f64, from_s: f64, hold_s: f64| {
            let mut t = tanker(fill);
            t.velocity_mps = mph * MPS_PER_MPH;
            t.corner_radius_ft = radius_ft;
            t.corner_advisory_mph = ADVISORY;
            let mut worst: f64 = 0.0;
            let mut time = 0.0;
            while time < hold_s {
                let pull = crate::sim::surge::lateral_accel_mps2(mph, ADVISORY);
                t.liquid.as_mut().unwrap().update(DT, 0.0, pull);
                if time >= from_s {
                    worst = worst.max(t.roll_share());
                }
                time += DT;
            }
            worst
        };
        let first = |from_s: f64, hold_s: f64| {
            let mut mph = 10.0;
            while worst_share(mph, from_s, hold_s) < 1.0 {
                mph += 0.1;
            }
            mph
        };
        (first(0.0, 15.0), first(120.0, 125.0))
    }

    #[test]
    fn a_half_full_tank_rolls_at_a_lower_speed_than_a_full_one() {
        // The roadmap question, answered from the reading: in a steady bend
        // the two go over at the same speed (NTSB HAR-11/01 2.3.4); entering
        // one, the half-full tank's wave runs past its steady place and takes
        // it over first. Pinned so a change to either is deliberate. The half
        // figure was 34.6 until the wave was judged against the bend's own
        // pull rather than the drive still building toward it (2026-09-24):
        // while the pull is being built the liquid sits short of where the
        // bend holds it, which is steadier than the steady price, not less.
        let radius = 250.0;
        let (half_entry, half_steady) = tank_rolls_at(0.5, radius);
        let (full_entry, full_steady) = tank_rolls_at(0.97, radius);
        assert!(
            half_entry < full_entry - 0.3,
            "half full {half_entry:.1} mph, full {full_entry:.1} mph"
        );
        assert!(
            (half_steady - full_steady).abs() <= 0.1,
            "steady: half {half_steady:.1}, full {full_steady:.1}"
        );
        assert!(
            (half_entry - 35.1).abs() <= 0.3,
            "half full entered at {half_entry:.1}"
        );
        assert!(
            (full_entry - 36.2).abs() <= 0.3,
            "full entered at {full_entry:.1}"
        );
    }

    /// How far over the number the cab speaks each load goes over, in mph, on
    /// a bend whose sign is priced the way the game prices it (0.30 g plus
    /// bank). The spoken number is the sign's, or the load's own safe speed
    /// where that is lower (the cab rounds that down to a 5 mph step, so the
    /// real margin is at least this). Recorded so a change to the pricing or
    /// the ladder is deliberate; these are the "few mph" of the lead's check
    /// (2026-09-24).
    #[test]
    fn the_margin_over_the_spoken_advisory() {
        use crate::data::curves::ADVISORY_LATERAL_G;
        let speed =
            |lateral: f64, radius_ft: f64| (lateral * G * radius_ft * M_PER_FT).sqrt() * MPS_TO_MPH;
        let over = |t: &TruckState, advisory: f64, bank: f64| {
            let radius_ft = advisory * advisory / (15.0 * (ADVISORY_LATERAL_G + bank));
            let threshold = t.planning_roll_threshold_g();
            let spoken = advisory.min(speed(ROLL_WARN_SHARE * threshold + bank, radius_ft));
            speed(threshold + bank, radius_ft) - spoken
        };
        let loads = [
            ("empty", truck(0.0)),
            ("half load", truck(0.5)),
            ("full trailer", truck(1.0)),
            ("tank half full", tanker(0.5)),
            ("tank nearly full", tanker(0.97)),
        ];
        // (advisory, bank, [roll margin per load]): low-speed bends are on
        // unbanked roads, and 35 and up carry the 6 percent roads are built to.
        let pinned: [(f64, f64, [f64; 5]); 4] = [
            (15.0, 0.0, [7.9, 4.8, 1.2, 1.2, 1.2]),
            (25.0, 0.0, [13.1, 8.0, 2.0, 1.9, 2.0]),
            (45.0, 0.06, [20.3, 12.3, 3.0, 2.9, 3.0]),
            (65.0, 0.06, [29.3, 17.8, 4.4, 4.2, 4.3]),
        ];
        for (advisory, bank, rolls) in pinned {
            for ((name, t), want) in loads.iter().zip(rolls) {
                let roll = over(t, advisory, bank);
                assert!(roll > 0.0, "{name} goes over at the spoken {advisory}");
                assert!(
                    (roll - want).abs() <= 0.2,
                    "{name} at a {advisory} sign rolls {roll:.1} over the spoken number, \
                     pinned {want}"
                );
            }
        }
    }

    #[test]
    fn the_bank_carries_its_share() {
        let mut t = truck(1.0);
        t.velocity_mps = 45.0 * MPS_PER_MPH;
        t.corner_radius_ft = 400.0;
        let flat = t.roll_lateral_g();
        t.corner_bank = 0.06;
        assert!((flat - t.roll_lateral_g() - 0.06).abs() < 1e-12);
        t.corner_radius_ft = 0.0;
        assert_eq!(t.roll_lateral_g(), 0.0, "a straight pulls nothing");
    }

    #[test]
    fn the_safe_speed_sits_at_the_warning_share() {
        for load in [0.0, 0.5, 1.0] {
            let mut t = truck(load);
            t.corner_radius_ft = 300.0;
            t.corner_bank = 0.04;
            let safe = t.roll_safe_mph(300.0, 0.04);
            t.velocity_mps = safe * MPS_PER_MPH;
            assert!(
                (t.roll_share() - ROLL_WARN_SHARE).abs() < 1e-3,
                "{load} load at {safe} mph asks {}",
                t.roll_share()
            );
        }
    }
}
