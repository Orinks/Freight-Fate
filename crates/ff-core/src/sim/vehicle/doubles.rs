//! What the hooked trailers are: one box, or a set of doubles. No saved
//! state -- the driving layer works it out from the job every time a drive
//! starts, the same way the tank's `liquid` is.
//!
//! A set of doubles changes three things on the truck (the numbers and their
//! sources live in `models::doubles`):
//!
//! - **gross weight**: both trailers and the converter dolly are tare, and
//!   the legal gross is the route's cap rather than always 80,000 lb;
//! - **the rear trailer**: a quick steer at speed swings it harder than the
//!   tractor (rearward amplification), and a crosswind pushes the set around
//!   more than a single box;
//! - **reverse**: a set of doubles is not backed.

use super::roll::ROLL_WARN_SHARE;
use super::{
    TruckState, CARGO_CORNER_PCT_PER_G_S, KG_PER_LB, LEGAL_GVW_KG, REFERENCE_CARGO_KG,
    TRAILER_TARE_KG,
};
use crate::data::world::World;
use crate::data::world_models::Route;
use crate::models::doubles::{
    doubles_trailer_for_cargo, legal_gvw_lb_for_route, rearward_amplification,
    trailer_set_extra_tare_kg, trailer_units, DOUBLES_NO_REVERSE_TEXT, REAR_TRAILER_FREIGHT_SHARE,
};
use crate::pyfmt::fmt_grouped;
use crate::sim::transmission::ShiftResult;

/// Below this the rear trailer's swing is not worth a word: yard and street
/// speeds, where a set is steered around corners, not whipped. ASSUMED; the
/// SAE J2179 lane-change test FHWA cites for rearward amplification is run
/// at 55 mph.
pub const REAR_WHIP_MIN_MPH: f64 = 40.0;

/// The trailers on the fifth wheel, as far as weight and handling go.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TrailerSet {
    /// 1 for a single trailer, 2 for doubles.
    pub units: u8,
    /// Empty weight of everything behind the tractor, kilograms.
    pub tare_kg: f64,
    /// Legal gross vehicle weight for this set on this route, kilograms.
    pub legal_gvw_kg: f64,
    /// Rear trailer's lateral acceleration over the tractor's in a quick
    /// lane change. 1.0 for a single trailer.
    pub rearward_amplification: f64,
}

impl Default for TrailerSet {
    fn default() -> Self {
        TrailerSet {
            units: 1,
            tare_kg: TRAILER_TARE_KG,
            legal_gvw_kg: LEGAL_GVW_KG,
            rearward_amplification: 1.0,
        }
    }
}

impl TrailerSet {
    /// The set a trailer program hooks, held to `legal_gvw_lb` on its route.
    pub fn for_trailer(trailer_key: &str, legal_gvw_lb: f64) -> Self {
        TrailerSet {
            units: trailer_units(trailer_key),
            tare_kg: TRAILER_TARE_KG + trailer_set_extra_tare_kg(trailer_key, TRAILER_TARE_KG),
            legal_gvw_kg: legal_gvw_lb * KG_PER_LB,
            rearward_amplification: rearward_amplification(trailer_key),
        }
    }

    /// What a load of this cargo hooks on this route: a set of doubles with
    /// the route's legal gross for doubles freight, the stock single
    /// otherwise. The legal gross reads the states of every city the route
    /// passes (`models::doubles::legal_gvw_lb_for_route`); no route, or a
    /// city the world does not know, holds turnpike doubles to 80,000 lb.
    pub fn for_cargo_on_route(cargo_key: &str, world: &World, route: Option<&Route>) -> Self {
        let Some(trailer_key) = doubles_trailer_for_cargo(cargo_key) else {
            return TrailerSet::default();
        };
        let states: Vec<&str> = route
            .map(|r| {
                r.cities
                    .iter()
                    .map(|key| world.cities.get(key).map_or("", |c| c.state_code.as_str()))
                    .collect()
            })
            .unwrap_or_default();
        TrailerSet::for_trailer(trailer_key, legal_gvw_lb_for_route(cargo_key, states))
    }

    pub fn is_doubles(&self) -> bool {
        self.units >= 2
    }

    /// The legal gross, pounds.
    pub fn legal_gvw_lb(&self) -> f64 {
        self.legal_gvw_kg / KG_PER_LB
    }
}

impl TruckState {
    /// A set of doubles is on the fifth wheel.
    pub fn doubles_hooked(&self) -> bool {
        self.trailer_attached && self.trailer_set.is_doubles()
    }

    /// Reverse is refused with doubles hooked; None when it may go in.
    pub fn doubles_reverse_refusal(&self) -> Option<&'static str> {
        self.doubles_hooked().then_some(DOUBLES_NO_REVERSE_TEXT)
    }

    /// The same refusal as a gearbox answer: not engaged, nothing ground.
    pub(super) fn doubles_reverse_shift_result(&self) -> Option<ShiftResult> {
        self.doubles_reverse_refusal().map(|message| ShiftResult {
            ok: false,
            message: message.to_string(),
            grind: false,
        })
    }

    /// The rear trailer's lateral acceleration, g, for a steer that puts
    /// `steer_lateral_g` on the tractor. A single trailer tracks the tractor.
    pub fn rear_trailer_lateral_g(&self, steer_lateral_g: f64) -> f64 {
        if !self.doubles_hooked() {
            return steer_lateral_g.abs();
        }
        steer_lateral_g.abs() * self.trailer_set.rearward_amplification
    }

    /// How far past the roll model's warning share of this load's threshold
    /// the rear trailer is swinging, in g; zero or less is fine. The same
    /// ladder a bend uses (`vehicle/roll.rs`), applied to the swing a quick
    /// steer sends down a set of doubles. Always zero for a single trailer
    /// and below [`REAR_WHIP_MIN_MPH`].
    pub fn rear_trailer_whip_excess_g(&self, steer_lateral_g: f64) -> f64 {
        if !self.doubles_hooked() || self.speed_mph() < REAR_WHIP_MIN_MPH {
            return 0.0;
        }
        self.rear_trailer_lateral_g(steer_lateral_g) - ROLL_WARN_SHARE * self.roll_threshold_g()
    }

    /// Freight in the rear trailer works against its straps when a quick
    /// steer whips it past the warning share, at the rate a bend taken too
    /// fast would cost (`update_cargo`), on the rear trailer's share of the
    /// load. Returns whether it whipped this frame.
    pub fn update_rear_trailer(&mut self, dt: f64, steer_lateral_g: f64) -> bool {
        let excess = self.rear_trailer_whip_excess_g(steer_lateral_g);
        if excess <= 0.0 {
            return false;
        }
        if self.cargo_kg > 0.0 {
            self.add_cargo_damage(
                excess
                    * CARGO_CORNER_PCT_PER_G_S
                    * REAR_TRAILER_FREIGHT_SHARE
                    * self.cargo_fragility
                    * dt,
            );
        }
        true
    }

    /// How much harder a crosswind pushes this set than a single box.
    /// ASSUMED: the rear trailer's amplification is used as the factor; no
    /// published crosswind figure for doubles was found.
    pub fn crosswind_mult(&self) -> f64 {
        if self.doubles_hooked() {
            self.trailer_set.rearward_amplification
        } else {
            1.0
        }
    }

    /// The CAT Scale ticket. A single trailer is broken out by axle group
    /// ([`super::AxleLoads::ticket_text`]); a set of doubles stands on
    /// single axles the three-group split does not model, so its ticket
    /// gives the gross against this set's legal gross for the route and
    /// says the axles are not broken out.
    pub fn scale_ticket_text(&self) -> String {
        if !self.doubles_hooked() {
            return self.axle_loads().ticket_text();
        }
        let lb = |kg: f64| (kg / KG_PER_LB).round();
        let gross = lb(self.gross_mass_kg());
        let limit = self.trailer_set.legal_gvw_lb().round();
        let verdict = if gross > limit {
            format!(
                "{} pounds over the {} pound gross limit for this set on this route.",
                fmt_grouped(gross - limit, 0),
                fmt_grouped(limit, 0)
            )
        } else {
            format!(
                "Legal under the {} pound gross limit for this set on this route.",
                fmt_grouped(limit, 0)
            )
        };
        format!(
            "Gross {} pounds, both trailers and the converter dolly included. {verdict} \
             Axle groups on a set of doubles are not broken out on this ticket.",
            fmt_grouped(gross, 0)
        )
    }
}

/// Tractor, the program's trailing units and a full tank for these specs.
/// The doubles counterpart of [`super::combination_tare_kg`].
pub fn combination_tare_for_trailer_kg(specs: &super::TruckSpecs, trailer_key: &str) -> f64 {
    (specs.mass_kg - REFERENCE_CARGO_KG).max(0.0)
        + trailer_set_extra_tare_kg(trailer_key, TRAILER_TARE_KG)
}

#[cfg(test)]
mod tests {
    use super::super::{TruckSpecs, REVERSE_ENGAGE_MAX_MPH};
    use super::*;
    use crate::models::doubles::{
        PUP_TRAILER_TARE_LB, SINGLE_AXLE_DOLLY_TARE_LB, TURNPIKE_DOUBLE_EXTRA_OVER_SINGLE_LB,
    };
    use crate::sim::transmission::REVERSE;

    fn pups() -> TruckState {
        TruckState {
            trailer_set: TrailerSet::for_trailer("double_van", 80_000.0),
            ..TruckState::default()
        }
    }

    fn turnpike(cap_lb: f64) -> TruckState {
        TruckState {
            trailer_set: TrailerSet::for_trailer("turnpike_double", cap_lb),
            ..TruckState::default()
        }
    }

    #[test]
    fn gross_counts_both_trailers_and_the_dolly() {
        let single = TruckState::default();
        let set = pups();
        let extra_lb = (set.tare_kg() - single.tare_kg()) / KG_PER_LB;
        // Two pups and a dolly, less the stock van they replace.
        let want =
            2.0 * PUP_TRAILER_TARE_LB + SINGLE_AXLE_DOLLY_TARE_LB - TRAILER_TARE_KG / KG_PER_LB;
        assert!((extra_lb - want).abs() < 0.01, "{extra_lb} vs {want}");
        let lcv = turnpike(127_400.0);
        let lcv_extra_lb = (lcv.tare_kg() - single.tare_kg()) / KG_PER_LB;
        assert!((lcv_extra_lb - TURNPIKE_DOUBLE_EXTRA_OVER_SINGLE_LB).abs() < 0.01);
        // Same cargo, heavier gross.
        assert!(lcv.gross_mass_kg() > single.gross_mass_kg());
        // The dispatch tare agrees with the live truck at a full tank.
        let specs = TruckSpecs::default();
        let dispatch = combination_tare_for_trailer_kg(&specs, "turnpike_double");
        assert!((dispatch - lcv.tare_kg()).abs() < 1e-6);
        // Dropping the set takes all of it off, not just one van's worth.
        let mut bobtail = turnpike(127_400.0);
        bobtail.trailer_attached = false;
        assert!((bobtail.tare_kg() - (single.tare_kg() - TRAILER_TARE_KG)).abs() < 1e-6);
    }

    #[test]
    fn the_legal_gross_is_the_route_cap() {
        let mut lcv = turnpike(127_400.0);
        // 100,000 lb gross: over 80,000, under the Ohio/Indiana/Mass cap.
        lcv.cargo_kg = 100_000.0 * KG_PER_LB - lcv.tare_kg();
        assert!(!lcv.is_over_legal_gvw());
        assert!(lcv.gross_weight_margin_kg() > 0.0);
        // The same load under Kansas's 120,000 is still legal; at 125,000 lb
        // it is over Kansas but under the Thruway's 143,000.
        let mut ks = turnpike(120_000.0);
        ks.cargo_kg = 125_000.0 * KG_PER_LB - ks.tare_kg();
        assert!(ks.is_over_legal_gvw());
        let mut ny = turnpike(143_000.0);
        ny.cargo_kg = 125_000.0 * KG_PER_LB - ny.tare_kg();
        assert!(!ny.is_over_legal_gvw());
        // Twin 28s at 80,001 lb are over: they never get the turnpike cap.
        let mut staa = pups();
        staa.cargo_kg = 80_001.0 * KG_PER_LB - staa.tare_kg();
        assert!(staa.is_over_legal_gvw());
        assert!(staa.gross_weight_margin_kg() < 0.0);
    }

    #[test]
    fn the_scale_ticket_for_doubles_reads_the_route_limit() {
        let mut lcv = turnpike(127_400.0);
        lcv.cargo_kg = 100_000.0 * KG_PER_LB - lcv.tare_kg();
        let text = lcv.scale_ticket_text();
        assert!(text.starts_with("Gross 100,000 pounds"), "{text}");
        assert!(
            text.contains("Legal under the 127,400 pound gross limit"),
            "{text}"
        );
        lcv.cargo_kg = 128_400.0 * KG_PER_LB - lcv.tare_kg();
        let text = lcv.scale_ticket_text();
        assert!(
            text.contains("1,000 pounds over the 127,400 pound gross limit"),
            "{text}"
        );
        // A single keeps the axle-group ticket.
        let single = TruckState::default();
        assert_eq!(
            single.scale_ticket_text(),
            single.axle_loads().ticket_text()
        );
    }

    #[test]
    fn reverse_is_refused_with_doubles_hooked() {
        let mut set = pups();
        set.velocity_mps = 0.0;
        let result = set.request_gear(REVERSE);
        assert!(!result.ok);
        assert!(!result.grind);
        assert_eq!(result.message, DOUBLES_NO_REVERSE_TEXT);
        assert!(!set.transmission.in_reverse());
        // A single trailer and a bobtail are not refused for doubles (the
        // gearbox may still want the clutch; that is its own answer).
        let mut single = TruckState::default();
        assert!(single.speed_mph() <= REVERSE_ENGAGE_MAX_MPH);
        assert_ne!(
            single.request_gear(REVERSE).message,
            DOUBLES_NO_REVERSE_TEXT
        );
        let mut dropped = pups();
        dropped.trailer_attached = false;
        assert_ne!(
            dropped.request_gear(REVERSE).message,
            DOUBLES_NO_REVERSE_TEXT
        );
    }

    #[test]
    fn a_quick_steer_swings_the_rear_pup_harder() {
        let mut set = pups();
        set.velocity_mps = 60.0 / 2.23694;
        let single = TruckState {
            velocity_mps: set.velocity_mps,
            ..TruckState::default()
        };
        // The driver's steering cap at highway speed is 0.2 g on the tractor.
        let steer_g = 0.2;
        assert!((set.rear_trailer_lateral_g(steer_g) - 0.34).abs() < 1e-9);
        assert_eq!(single.rear_trailer_lateral_g(steer_g), steer_g);
        // Full load: the pup passes the warning share a single never reaches.
        assert!(set.rear_trailer_whip_excess_g(steer_g) > 0.0);
        assert!(single.rear_trailer_whip_excess_g(steer_g) <= 0.0);
        // A gentle lane change is fine even on pups.
        assert!(set.rear_trailer_whip_excess_g(0.1) <= 0.0);
        // Turnpike doubles amplify less: the same steer stays under.
        let mut lcv = turnpike(127_400.0);
        lcv.velocity_mps = set.velocity_mps;
        assert!(lcv.rear_trailer_whip_excess_g(steer_g) <= 0.0);
        // At street speed nothing is said.
        set.velocity_mps = 25.0 / 2.23694;
        assert_eq!(set.rear_trailer_whip_excess_g(steer_g), 0.0);
    }

    #[test]
    fn a_whip_costs_the_rear_trailer_freight_and_a_single_nothing() {
        let mut set = pups();
        set.velocity_mps = 60.0 / 2.23694;
        assert!(set.update_rear_trailer(1.0, 0.2));
        assert!(set.cargo_damage_pct > 0.0);
        let mut single = TruckState {
            velocity_mps: set.velocity_mps,
            ..TruckState::default()
        };
        assert!(!single.update_rear_trailer(1.0, 0.2));
        assert_eq!(single.cargo_damage_pct, 0.0);
    }

    #[test]
    fn a_crosswind_pushes_doubles_more() {
        assert_eq!(TruckState::default().crosswind_mult(), 1.0);
        assert_eq!(pups().crosswind_mult(), 1.7);
        let lcv = turnpike(127_400.0).crosswind_mult();
        assert!(lcv > 1.0 && lcv < 1.7);
    }
}
