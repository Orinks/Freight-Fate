//! The street detail of a facility chain, by route mile: each street's
//! posted limit with the kind of value it is, and the traffic controls OSM
//! reads along the way (`tools/street_chain.py` bakes both). Data only; what
//! the drive does with a limit or a control is the driving layer's call.

use crate::data::world_models::StreetLimit;

use super::Trip;

impl Trip {
    /// The posted limit of the facility street under a route mile, with its
    /// kind (`read`, `statutory` or `assumed`); None off a facility chain, or
    /// on a chain baked before the street detail was.
    pub fn street_limit_at(&self, route_mile: f64) -> Option<&StreetLimit> {
        let (i, _) = self.leg_at_mile(route_mile);
        self.route.legs.get(i)?.local_limit.as_ref()
    }

    /// The READ traffic controls from `from_mi` to `to_mi` inclusive, as
    /// (route mile, kind) in route order. A corner's control stands at the
    /// corner (the start of the street it turns onto). Where OSM is silent
    /// nothing is listed: an intersection missing here is unknown, not free.
    pub fn street_controls_between(&self, from_mi: f64, to_mi: f64) -> Vec<(f64, &str)> {
        let mut out = Vec::new();
        for (leg, start) in self.route.legs.iter().zip(&self.leg_starts) {
            for control in &leg.local_controls {
                let at = start + control.at_mi;
                if (from_mi..=to_mi).contains(&at) {
                    out.push((at, control.kind.as_str()));
                }
            }
        }
        out
    }
}
