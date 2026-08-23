//! Money: fuel prices, repairs, and running costs (port of
//! `freight_fate/models/economy.py`).

use crate::pyfmt::{fmt_grouped, round_py_n};
use crate::pyrandom::PyRandom;

/// Diesel $/gal by region, nudged by a per-session market wobble.
///
/// Kept in the Python dict's insertion order: [`Economy::new`] draws one
/// market wobble per region in this order, so the order is part of the seed.
pub const REGION_FUEL_PRICE: &[(&str, f64)] = &[
    ("northeast", 4.15),
    ("appalachia", 3.95),
    ("great_lakes", 3.75),
    ("upper_midwest", 3.55),
    ("corn_belt", 3.55),
    ("heartland", 3.60),
    ("southern_plains", 3.45),
    ("mid_south", 3.45),
    ("atlantic_southeast", 3.65),
    ("gulf_coast", 3.40),
    ("florida", 3.85),
    ("rockies", 3.95),
    ("great_basin", 4.10),
    ("desert_southwest", 4.00),
    ("california", 5.10),
    ("pacific_northwest", 4.45),
];

/// `REGION_FUEL_PRICE.get(region)`.
pub fn region_fuel_price(region: &str) -> Option<f64> {
    REGION_FUEL_PRICE
        .iter()
        .find(|(key, _)| *key == region)
        .map(|(_, price)| *price)
}

/// Diesel price assumed for a region the table does not know.
pub const DEFAULT_FUEL_PRICE: f64 = 3.80;

/// $ per percent of damage repaired.
pub const REPAIR_COST_PER_PCT: f64 = 85.0;
// Body damage does not price by the percent. Light damage is panels and
// lamps; deep damage is frame, driveline, and cooling package, and the labour
// to reach any of it goes up with everything else that has to come off first.
// So the bill curves: a truck at ninety percent is not three times the bill of
// one at thirty, it is closer to seven. The curve is negligible at the shallow
// end on purpose -- a careful driver's occasional scrape prices as it always
// did -- and only bites where the driver has been ignoring warnings.
pub const REPAIR_SEVERITY_CURVE: f64 = 2.0;
/// Flat cost of a rest stop visit (food, parking).
pub const REST_COST: f64 = 35.0;
/// A real bed near the lot: full-quality rest for money.
pub const MOTEL_COST: f64 = 95.0;

// Dispatcher pay advances: a recovery line for a driver who has run the
// balance negative and can no longer afford fuel. Cash now, drawn against
// the next settlement and repaid automatically at delivery. Offered only
// when cash is already low so it stays a safety net against a soft lock,
// not free liquidity. Mirrors how carriers and factoring services front a
// driver fuel money against a load in transit.
/// Most you can owe at once.
pub const PAY_ADVANCE_LIMIT: f64 = 1500.0;
/// Cash per request.
pub const PAY_ADVANCE_GRANT: f64 = 500.0;
/// Only offered at single-digit cash or worse.
pub const PAY_ADVANCE_ELIGIBLE_BELOW: f64 = 10.0;

/// How much dearer a percent of damage is at this depth. 1.0 at zero.
///
/// One curve, shared by the terminal garage and the road shops, so a driver
/// is never quoted two different theories of what their truck is worth.
pub fn damage_severity_mult(damage_pct: f64) -> f64 {
    let depth = (damage_pct / 100.0).clamp(0.0, 1.0);
    1.0 + REPAIR_SEVERITY_CURVE * depth * depth
}

/// Dollars a dispatcher will advance now, or 0 when none is available.
///
/// Available only while cash is low (a recovery tool) and only up to the
/// outstanding-advance ceiling, so it can never become a bottomless loan.
pub fn pay_advance_grant(money: f64, outstanding: f64, used_for_load: bool) -> f64 {
    if used_for_load || money >= PAY_ADVANCE_ELIGIBLE_BELOW {
        return 0.0;
    }
    let headroom = PAY_ADVANCE_LIMIT - outstanding.max(0.0);
    if headroom < 1.0 {
        return 0.0;
    }
    round_py_n(PAY_ADVANCE_GRANT.min(headroom), 2)
}

/// Spoken explanation for why no advance is available right now.
pub fn pay_advance_unavailable_reason(money: f64, outstanding: f64, used_for_load: bool) -> String {
    let _ = outstanding;
    if used_for_load {
        return "You have already taken a pay advance for this load. Deliver it before drawing another."
            .to_string();
    }
    if money >= PAY_ADVANCE_ELIGIBLE_BELOW {
        return format!(
            "A pay advance is only for getting unstuck when cash is low. You have {} dollars.",
            fmt_grouped(money, 0)
        );
    }
    "You have reached your pay-advance limit. Deliver a load to pay it down before drawing more."
        .to_string()
}

/// The per-session fuel market: one wobble per region, drawn once.
#[derive(Debug, Clone, PartialEq)]
pub struct Economy {
    /// `(region, multiplier)` in [`REGION_FUEL_PRICE`] order.
    market: Vec<(&'static str, f64)>,
}

impl Economy {
    /// `Economy(seed)`. `None` is `random.Random(None)`: an unseeded,
    /// irreproducible market.
    pub fn new(seed: Option<i64>) -> Self {
        let mut rng = match seed {
            Some(seed) => PyRandom::new_from_i64(seed),
            None => PyRandom::new_unseeded(),
        };
        let market = REGION_FUEL_PRICE
            .iter()
            .map(|(region, _)| (*region, rng.uniform(0.92, 1.10)))
            .collect();
        Self { market }
    }

    /// This session's wobble for a region (1.0 when the region is unknown).
    fn market_mult(&self, region: &str) -> f64 {
        self.market
            .iter()
            .find(|(key, _)| *key == region)
            .map(|(_, mult)| *mult)
            .unwrap_or(1.0)
    }

    pub fn fuel_price(&self, region: &str) -> f64 {
        let base = region_fuel_price(region).unwrap_or(DEFAULT_FUEL_PRICE);
        round_py_n(base * self.market_mult(region), 2)
    }

    pub fn fuel_cost(&self, region: &str, gallons: f64) -> f64 {
        round_py_n(self.fuel_price(region) * gallons, 2)
    }

    pub fn repair_cost(damage_pct: f64) -> f64 {
        round_py_n(
            damage_pct * REPAIR_COST_PER_PCT * damage_severity_mult(damage_pct),
            2,
        )
    }
}

impl Default for Economy {
    fn default() -> Self {
        Self::new(None)
    }
}

#[cfg(test)]
mod tests {
    //! Ported from `tests/test_pay_advance.py` (the pure half),
    //! `tests/test_driving_damage_bands.py::test_repair_cost_curves_up_instead_of_scaling_by_the_percent`,
    //! and `tests/test_regions.py::test_every_region_covered_in_flavor_tables`
    //! for the fuel table.

    use super::*;

    // -- tests/test_pay_advance.py ------------------------------------------

    #[test]
    fn test_no_advance_when_cash_is_healthy() {
        assert_eq!(
            pay_advance_grant(PAY_ADVANCE_ELIGIBLE_BELOW, 0.0, false),
            0.0
        );
        assert_eq!(pay_advance_grant(10.0, 0.0, false), 0.0);
        assert_eq!(pay_advance_grant(400.0, 0.0, false), 0.0);
        assert_eq!(pay_advance_grant(5000.0, 0.0, false), 0.0);
    }

    #[test]
    fn test_advance_available_when_broke() {
        assert_eq!(pay_advance_grant(-300.0, 0.0, false), PAY_ADVANCE_GRANT);
        assert_eq!(pay_advance_grant(0.0, 0.0, false), PAY_ADVANCE_GRANT);
        assert_eq!(pay_advance_grant(9.99, 0.0, false), PAY_ADVANCE_GRANT);
    }

    #[test]
    fn test_advance_only_once_per_load() {
        assert_eq!(pay_advance_grant(0.0, 0.0, true), 0.0);
        assert!(pay_advance_unavailable_reason(0.0, 0.0, true).contains("already taken"));
    }

    #[test]
    fn test_advance_is_capped_by_the_outstanding_limit() {
        // Almost at the ceiling: only the remaining headroom is offered.
        let near_limit = PAY_ADVANCE_LIMIT - 100.0;
        assert_eq!(pay_advance_grant(-50.0, near_limit, false), 100.0);
        // At the ceiling: nothing more until a delivery pays it down.
        assert_eq!(pay_advance_grant(-50.0, PAY_ADVANCE_LIMIT, false), 0.0);
    }

    #[test]
    fn test_unavailable_reason_distinguishes_healthy_cash_from_the_limit() {
        assert!(pay_advance_unavailable_reason(5000.0, 0.0, false).contains("cash is low"));
        assert!(pay_advance_unavailable_reason(-50.0, PAY_ADVANCE_LIMIT, false).contains("limit"));
    }

    #[test]
    fn healthy_cash_reason_spells_the_money_grouped() {
        assert_eq!(
            pay_advance_unavailable_reason(5000.0, 0.0, false),
            "A pay advance is only for getting unstuck when cash is low. You have 5,000 dollars."
        );
    }

    // `test_terminal_pay_advance_option_only_appears_when_available` is live in `crates/freight-fate/tests/states_city.rs`.

    // `test_rest_stop_pay_advance_option_only_appears_when_available` is live in `crates/freight-fate/tests/states_driving_menus_rest.rs`.

    // -- tests/test_driving_damage_bands.py ---------------------------------

    #[test]
    fn test_repair_cost_curves_up_instead_of_scaling_by_the_percent() {
        // A truck at ninety is far more than three times the bill of one at thirty.
        assert_eq!(Economy::repair_cost(0.0), 0.0);
        let shallow = Economy::repair_cost(30.0);
        let deep = Economy::repair_cost(90.0);
        assert!(deep / shallow > 5.0);
        // The shallow end stays close to the old flat rate: a careful driver's
        // occasional scrape must not suddenly cost more than it used to.
        assert!(Economy::repair_cost(10.0) < 10.0 * REPAIR_COST_PER_PCT * 1.05);
    }

    #[test]
    fn road_shops_share_the_garage_severity_curve() {
        // The pure half of test_road_shops_share_the_garage_severity_curve;
        // the road_repair_cost comparison needs states::driving_core.
        assert!(damage_severity_mult(80.0) > damage_severity_mult(20.0));
        assert!(damage_severity_mult(20.0) > 1.0);
        assert_eq!(damage_severity_mult(0.0), 1.0);
    }

    // -- the fuel market ----------------------------------------------------

    #[test]
    fn test_every_region_covered_in_flavor_tables() {
        // tests/test_regions.py, the REGION_FUEL_PRICE row.
        let missing: Vec<&str> = crate::data::regions::REGIONS
            .iter()
            .copied()
            .filter(|region| region_fuel_price(region).is_none())
            .collect();
        assert!(
            missing.is_empty(),
            "REGION_FUEL_PRICE is missing regions: {missing:?}"
        );
    }

    #[test]
    fn seeded_economy_is_deterministic_and_bounded() {
        let a = Economy::new(Some(7));
        let b = Economy::new(Some(7));
        assert_eq!(a, b);
        for (region, base) in REGION_FUEL_PRICE {
            let price = a.fuel_price(region);
            assert!(price >= round_py_n(base * 0.92, 2) - 0.01);
            assert!(price <= round_py_n(base * 1.10, 2) + 0.01);
        }
        assert_eq!(a.fuel_price("nowhere"), DEFAULT_FUEL_PRICE);
        assert_eq!(a.fuel_cost("nowhere", 10.0), 38.0);
    }

    #[test]
    fn seeded_economy_matches_cpython() {
        // python: Economy(seed=42).fuel_price("northeast") with the same
        // draw order (first uniform(0.92, 1.10) of Random(42) is
        // 0.92 + 0.18 * 0.6394267984578837).
        let e = Economy::new(Some(42));
        let expected = round_py_n(4.15 * (0.92 + 0.18 * 0.639_426_798_457_883_7), 2);
        assert_eq!(e.fuel_price("northeast"), expected);
    }
}
