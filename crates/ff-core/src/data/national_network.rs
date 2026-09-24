//! National Network access for STAA twin 28-foot doubles (`parcel_doubles`).
//!
//! Real US twin pups have federally guaranteed access only on the National
//! Network (23 CFR 658: the Interstate System plus designated federal-aid
//! primary routes) and on reasonable access off that network to terminals
//! and to food, fuel, repair, and rest (typically about a mile; state rules
//! vary). World data does not yet carry NN designation flags, so this module
//! uses an honest conservative approximation:
//!
//! * **National Network** ≈ Interstate designation (`I-n` via
//!   [`crate::data::grades::road_class`]). Designated US and state primary
//!   routes that are also on the real NN are **not** counted yet.
//! * **Reasonable access** ≈ surface / facility approach legs (`local_cue`
//!   set, or same-city local), plus a short first or last corridor leg at
//!   either end of the route (terminal approach), capped at
//!   [`REASONABLE_ACCESS_MAX_MI`].
//!
//! Honesty debt: under-includes real NN mileage; does not model per-state
//! access distance or off-NN state doubles bans beyond the federal floor.

use crate::data::grades::road_class;
use crate::data::world_models::{Leg, Route};

/// Soft cap for a terminal-approach corridor stub treated as reasonable
/// access. Real rules are often about one mile and vary by state; this is
/// the game's conservative stand-in until junction-distance data exists.
pub const REASONABLE_ACCESS_MAX_MI: f64 = 1.5;

/// Spoken when no twin-legal route remains for a `parcel_doubles` load.
pub const STAA_DOUBLES_ROUTE_REFUSAL: &str = "Dispatch can't clear twin trailers on that run. It \
     leaves the National Network.";

/// Spoken when dispatch drops one or more lanes that leave the NN.
pub const STAA_DOUBLES_REROUTE_NOTE: &str =
    "Dispatch dropped a lane that leaves the National Network.";

/// Whether a leg's highway designation is treated as National Network under
/// the Interstate-only approximation.
pub fn leg_on_national_network(leg: &Leg) -> bool {
    road_class(&leg.highway) == "interstate"
}

/// Whether a leg is treated as reasonable access (terminal / facility /
/// surface approach), not a through corridor off the NN.
pub fn leg_is_reasonable_access(leg: &Leg) -> bool {
    if !leg.local_cue.is_empty() {
        return true;
    }
    // Same-city local chain segments from `Leg::local`.
    leg.a == leg.b
}

/// Whether STAA twin trailers may legally use this single leg under the
/// game's approximation (NN or reasonable access).
pub fn leg_allows_staa_doubles(leg: &Leg) -> bool {
    leg_on_national_network(leg) || leg_is_reasonable_access(leg)
}

/// Whether every leg of a route is STAA-legal: Interstate (NN approx), a
/// facility/surface approach, or a short terminal stub at either end.
pub fn route_allows_staa_doubles(route: &Route) -> bool {
    let n = route.legs.len();
    if n == 0 {
        return false;
    }
    route.legs.iter().enumerate().all(|(i, leg)| {
        if leg_allows_staa_doubles(leg) {
            return true;
        }
        // Short first/last corridor stub into or out of a terminal yard.
        (i == 0 || i + 1 == n) && leg.miles <= REASONABLE_ACCESS_MAX_MI
    })
}

/// Keep only routes STAA doubles may run. Empty means refuse the load.
pub fn filter_staa_doubles_routes(routes: &[Route]) -> Vec<Route> {
    routes
        .iter()
        .filter(|route| route_allows_staa_doubles(route))
        .cloned()
        .collect()
}

/// Whether a cargo class must stay on the National Network approximation.
pub fn cargo_requires_national_network(cargo_key: &str) -> bool {
    cargo_key == "parcel_doubles"
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::data::world_models::Leg;

    fn interstate_leg() -> Leg {
        Leg::new("A", "B", 40.0, "I-80", "flat", Vec::new())
    }

    fn us_leg() -> Leg {
        Leg::new("A", "B", 40.0, "US-50", "flat", Vec::new())
    }

    fn state_leg() -> Leg {
        Leg::new("A", "B", 40.0, "CA-99", "flat", Vec::new())
    }

    fn approach_leg() -> Leg {
        Leg::local(
            "denver_co_us",
            0.8,
            "Dock Road",
            "right onto Dock Road",
            25.0,
        )
    }

    fn short_connector() -> Leg {
        Leg::new("yard", "A", 1.0, "Frontage Rd", "flat", Vec::new())
    }

    #[test]
    fn interstate_leg_is_national_network() {
        assert!(leg_on_national_network(&interstate_leg()));
        assert!(leg_allows_staa_doubles(&interstate_leg()));
    }

    #[test]
    fn us_and_state_legs_are_not_national_network_yet() {
        // Honesty: real NN includes many designated US/state primaries; we
        // do not count them without designation data.
        assert!(!leg_on_national_network(&us_leg()));
        assert!(!leg_allows_staa_doubles(&us_leg()));
        assert!(!leg_on_national_network(&state_leg()));
        assert!(!leg_allows_staa_doubles(&state_leg()));
    }

    #[test]
    fn facility_approach_leg_is_reasonable_access() {
        let approach = approach_leg();
        assert!(leg_is_reasonable_access(&approach));
        assert!(leg_allows_staa_doubles(&approach));
    }

    #[test]
    fn doubles_job_on_nn_route_is_allowed() {
        let route = Route::from_legs(
            vec!["A".into(), "B".into(), "C".into()],
            vec![
                Leg::new("A", "B", 50.0, "I-70", "flat", Vec::new()),
                Leg::new("B", "C", 60.0, "I-25", "hills", Vec::new()),
            ],
        );
        assert!(route_allows_staa_doubles(&route));
    }

    #[test]
    fn non_nn_leg_is_refused() {
        let route = Route::from_legs(vec!["A".into(), "B".into()], vec![us_leg()]);
        assert!(!route_allows_staa_doubles(&route));
    }

    #[test]
    fn reasonable_access_approach_on_nn_route_is_allowed() {
        let route = Route::from_legs(
            vec!["dock".into(), "A".into(), "B".into()],
            vec![
                approach_leg(),
                Leg::new("A", "B", 80.0, "I-80", "flat", Vec::new()),
            ],
        );
        assert!(route_allows_staa_doubles(&route));
    }

    #[test]
    fn short_terminal_stub_at_either_end_is_allowed() {
        let out = Route::from_legs(
            vec!["yard".into(), "A".into(), "B".into()],
            vec![
                short_connector(),
                Leg::new("A", "B", 90.0, "I-5", "flat", Vec::new()),
            ],
        );
        assert!(route_allows_staa_doubles(&out));

        let into = Route::from_legs(
            vec!["A".into(), "B".into(), "yard".into()],
            vec![
                Leg::new("A", "B", 90.0, "I-5", "flat", Vec::new()),
                short_connector(),
            ],
        );
        assert!(route_allows_staa_doubles(&into));
    }

    #[test]
    fn long_non_nn_mid_leg_is_refused_even_beside_interstate() {
        let route = Route::from_legs(
            vec!["A".into(), "B".into(), "C".into()],
            vec![
                Leg::new("A", "B", 40.0, "I-80", "flat", Vec::new()),
                Leg::new("B", "C", 40.0, "US-50", "flat", Vec::new()),
            ],
        );
        assert!(!route_allows_staa_doubles(&route));
    }

    #[test]
    fn filter_drops_non_nn_options_and_keeps_nn() {
        let nn = Route::from_legs(vec!["A".into(), "B".into()], vec![interstate_leg()]);
        let off = Route::from_legs(vec!["A".into(), "B".into()], vec![us_leg()]);
        let kept = filter_staa_doubles_routes(&[off, nn.clone()]);
        assert_eq!(kept.len(), 1);
        assert!(route_allows_staa_doubles(&kept[0]));
    }

    #[test]
    fn only_parcel_doubles_requires_the_network() {
        assert!(cargo_requires_national_network("parcel_doubles"));
        assert!(!cargo_requires_national_network("general"));
        assert!(!cargo_requires_national_network("turnpike_doubles"));
        assert!(!cargo_requires_national_network("parcel"));
    }
}
