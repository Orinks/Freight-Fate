//! Shared business constants that must not create model import cycles
//! (port of `freight_fate/models/business_constants.py`).
//!
//! The Rust port also hoists the business-status keys and the
//! owner-operator test here. In Python they live in `business.py`, which
//! `enforcement` and `solvency` reach through deferred in-function imports;
//! `business.rs` should re-export them (`pub use`) so callers keep the Python
//! spelling `business::COMPANY_DRIVER`.

pub const DIRECT_FREIGHT_PAY_MULT: f64 = 1.18;

// -- hoisted from business.py ---------------------------------------------------

/// A driver on a carrier's payroll, in a carrier tractor.
pub const COMPANY_DRIVER: &str = "company_driver";
/// An owner-operator leased on to a carrier: their tractor, the carrier's
/// freight and trailers.
pub const LEASED_OWNER_OPERATOR: &str = "leased_owner_operator";
/// An owner-operator running under their own operating authority.
pub const INDEPENDENT_AUTHORITY: &str = "independent_authority";

/// `business.is_owner_operator`: the two statuses that own the tractor.
pub fn is_owner_operator(status: &str) -> bool {
    status == LEASED_OWNER_OPERATOR || status == INDEPENDENT_AUTHORITY
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn owner_operator_statuses() {
        assert!(!is_owner_operator(COMPANY_DRIVER));
        assert!(is_owner_operator(LEASED_OWNER_OPERATOR));
        assert!(is_owner_operator(INDEPENDENT_AUTHORITY));
        assert!(!is_owner_operator(""));
    }
}
