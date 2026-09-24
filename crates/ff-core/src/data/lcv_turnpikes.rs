//! Permitted LCV turnpike corridors for `turnpike_doubles`.
//!
//! Real turnpike doubles (two long trailers) run only on specific toll roads
//! that authorize LCVs, and they make up / break down at staging lots at the
//! turnpike exits -- the combination itself stays on the permitted road.
//! World data does not tag "LCV permitted" on legs, so this module matches
//! highway IDs against the classic ISTEA-era turnpike systems in the states
//! that freeze those networks (23 CFR 658 Appendix C), plus short staging
//! stubs at either end of a route.
//!
//! Honesty debts:
//! * Florida's Turnpike is mostly not Interstate-numbered in world data, so
//!   FL turnpike doubles are not offered under this approximation.
//! * Western LCV corridors (Rocky Mountain doubles and similar) are not
//!   modeled; only the classic turnpike highway list counts.
//! * Staging lots are approximated as same-city locals / end `local_cue` /
//!   short end stubs, not curated break-bulk yards.

use crate::data::national_network::city_key_state_country;
use crate::data::world_models::{Leg, Route};

/// Soft staging-lot stub at a turnpike exit (miles). Same federal-floor
/// spirit as STAA reasonable access; not a claim about every state's yard.
pub const LCV_STAGING_ACCESS_MAX_MI: f64 = 1.0;

/// Spoken when no permitted turnpike lane remains for `turnpike_doubles`.
pub const LCV_TURNPIKE_ROUTE_REFUSAL: &str = "Dispatch only clears long doubles on the turnpike.";

/// Spoken when dispatch drops a non-turnpike option for long doubles.
pub const LCV_TURNPIKE_REROUTE_NOTE: &str = "Dispatch dropped a lane that leaves the turnpike.";

/// Classic LCV turnpike systems identifiable by Interstate (or spur) ID in
/// world data: `(state_code, highway)`.
///
/// NY Thruway (I-90), Massachusetts Turnpike (I-90), Ohio Turnpike (I-80 /
/// I-90), Indiana Toll Road (I-80 / I-90), Kansas Turnpike (I-35 / I-335 /
/// I-70). Florida's Turnpike is omitted -- it is not carried as an
/// Interstate highway ID in the shipped legs.
pub const LCV_TURNPIKE_HIGHWAYS: &[(&str, &str)] = &[
    ("NY", "I-90"),
    ("MA", "I-90"),
    ("OH", "I-80"),
    ("OH", "I-90"),
    ("IN", "I-80"),
    ("IN", "I-90"),
    ("KS", "I-35"),
    ("KS", "I-335"),
    ("KS", "I-70"),
];

fn normalize_highway(highway: &str) -> String {
    highway.trim().to_uppercase().replace(' ', "")
}

/// Whether `highway` is a listed LCV turnpike road inside `state_code`.
pub fn highway_is_lcv_turnpike(state_code: &str, highway: &str) -> bool {
    let state = state_code.trim().to_uppercase();
    let hwy = normalize_highway(highway);
    LCV_TURNPIKE_HIGHWAYS
        .iter()
        .any(|(st, listed)| *st == state && normalize_highway(listed) == hwy)
}

fn endpoint_states(leg: &Leg) -> Vec<String> {
    let mut out = Vec::new();
    for key in [&leg.a, &leg.b] {
        if let Some((state, country)) = city_key_state_country(key) {
            if country.eq_ignore_ascii_case("us") {
                let state = state.to_ascii_uppercase();
                if !out.iter().any(|s| s == &state) {
                    out.push(state);
                }
            }
        }
    }
    out
}

/// Whether a corridor leg sits on a listed LCV turnpike for one of its
/// endpoint states.
pub fn leg_on_lcv_turnpike(leg: &Leg) -> bool {
    let hwy = normalize_highway(&leg.highway);
    if hwy.is_empty() {
        return false;
    }
    endpoint_states(leg)
        .iter()
        .any(|state| highway_is_lcv_turnpike(state, &leg.highway))
}

fn leg_is_staging_access(leg: &Leg) -> bool {
    if leg.a == leg.b {
        return true;
    }
    if !leg.local_cue.is_empty() {
        return true;
    }
    leg.miles <= LCV_STAGING_ACCESS_MAX_MI
}

/// Whether every leg is on a permitted turnpike, or a first/last staging
/// access stub / same-city local.
pub fn route_allows_lcv_turnpike(route: &Route) -> bool {
    let n = route.legs.len();
    if n == 0 {
        return false;
    }
    route.legs.iter().enumerate().all(|(i, leg)| {
        if leg_on_lcv_turnpike(leg) {
            return true;
        }
        if leg.a == leg.b {
            return true;
        }
        let at_end = i == 0 || i + 1 == n;
        at_end && leg_is_staging_access(leg)
    })
}

/// Keep only routes long doubles may run on the turnpike approximation.
pub fn filter_lcv_turnpike_routes(routes: &[Route]) -> Vec<Route> {
    routes
        .iter()
        .filter(|route| route_allows_lcv_turnpike(route))
        .cloned()
        .collect()
}

/// Whether a cargo class must stay on permitted LCV turnpike corridors.
pub fn cargo_requires_lcv_turnpike(cargo_key: &str) -> bool {
    cargo_key == "turnpike_doubles"
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::data::world_models::Leg;

    fn ohio_turnpike_leg() -> Leg {
        Leg::new(
            "cleveland_oh_us",
            "toledo_oh_us",
            100.0,
            "I-80",
            "flat",
            Vec::new(),
        )
    }

    fn plain_interstate_leg() -> Leg {
        Leg::new(
            "columbus_oh_us",
            "cincinnati_oh_us",
            100.0,
            "I-71",
            "flat",
            Vec::new(),
        )
    }

    #[test]
    fn listed_turnpike_highways_match_by_state() {
        assert!(highway_is_lcv_turnpike("OH", "I-80"));
        assert!(highway_is_lcv_turnpike("NY", "I-90"));
        assert!(highway_is_lcv_turnpike("KS", "I-335"));
        assert!(!highway_is_lcv_turnpike("OH", "I-71"));
        assert!(!highway_is_lcv_turnpike("CA", "I-5"));
        assert!(!highway_is_lcv_turnpike("FL", "I-95"));
    }

    #[test]
    fn turnpike_leg_is_allowed_and_non_turnpike_is_refused() {
        assert!(leg_on_lcv_turnpike(&ohio_turnpike_leg()));
        assert!(!leg_on_lcv_turnpike(&plain_interstate_leg()));
    }

    #[test]
    fn non_permitted_road_route_is_refused() {
        let route = Route::from_legs(
            vec!["columbus_oh_us".into(), "cincinnati_oh_us".into()],
            vec![plain_interstate_leg()],
        );
        assert!(!route_allows_lcv_turnpike(&route));
    }

    #[test]
    fn turnpike_route_with_staging_stub_is_allowed() {
        let stub = Leg::local(
            "cleveland_oh_us",
            0.6,
            "Staging Lot Road",
            "right onto Staging Lot Road",
            25.0,
        );
        let route = Route::from_legs(
            vec![
                "cleveland_oh_us".into(),
                "cleveland_oh_us".into(),
                "toledo_oh_us".into(),
            ],
            vec![stub, ohio_turnpike_leg()],
        );
        assert!(route_allows_lcv_turnpike(&route));
    }

    #[test]
    fn mid_route_connector_never_counts_as_staging() {
        let route = Route::from_legs(
            vec![
                "cleveland_oh_us".into(),
                "mid_oh_us".into(),
                "elmore_oh_us".into(),
                "toledo_oh_us".into(),
            ],
            vec![
                Leg::new(
                    "cleveland_oh_us",
                    "mid_oh_us",
                    40.0,
                    "I-80",
                    "flat",
                    Vec::new(),
                ),
                Leg::new(
                    "mid_oh_us",
                    "elmore_oh_us",
                    0.5,
                    "Frontage Rd",
                    "flat",
                    Vec::new(),
                ),
                Leg::new(
                    "elmore_oh_us",
                    "toledo_oh_us",
                    40.0,
                    "I-80",
                    "flat",
                    Vec::new(),
                ),
            ],
        );
        // Middle leg is not a turnpike highway and is not an end stub.
        assert!(!route_allows_lcv_turnpike(&route));
    }

    #[test]
    fn filter_keeps_turnpike_options_only() {
        let ok = Route::from_legs(
            vec!["cleveland_oh_us".into(), "toledo_oh_us".into()],
            vec![ohio_turnpike_leg()],
        );
        let bad = Route::from_legs(
            vec!["columbus_oh_us".into(), "cincinnati_oh_us".into()],
            vec![plain_interstate_leg()],
        );
        let kept = filter_lcv_turnpike_routes(&[bad, ok.clone()]);
        assert_eq!(kept.len(), 1);
        assert!(route_allows_lcv_turnpike(&kept[0]));
    }

    #[test]
    fn only_turnpike_doubles_requires_the_turnpike() {
        assert!(cargo_requires_lcv_turnpike("turnpike_doubles"));
        assert!(!cargo_requires_lcv_turnpike("parcel_doubles"));
        assert!(!cargo_requires_lcv_turnpike("general"));
    }

    #[test]
    fn refusal_line_is_distinct_from_staa_lines() {
        use crate::data::national_network::{
            STAA_DOUBLES_CORRIDOR_REFUSAL, STAA_DOUBLES_ROUTE_REFUSAL,
        };
        assert_eq!(
            LCV_TURNPIKE_ROUTE_REFUSAL,
            "Dispatch only clears long doubles on the turnpike."
        );
        assert_ne!(LCV_TURNPIKE_ROUTE_REFUSAL, STAA_DOUBLES_ROUTE_REFUSAL);
        assert_ne!(LCV_TURNPIKE_ROUTE_REFUSAL, STAA_DOUBLES_CORRIDOR_REFUSAL);
    }
}
