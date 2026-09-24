//! The street detail of a facility chain, by route mile: each street's
//! posted limit with the kind of value it is, and the traffic controls OSM
//! reads along the way (`tools/street_chain.py` bakes both). Data only; what
//! the drive does with a limit or a control is the driving layer's call.

use crate::data::world_models::{Route, StreetLimit};
use crate::data::world_services::local_chain_route;
use crate::sim::trip_models::RoadStop;

use super::Trip;

impl Trip {
    /// The streets from the ramp terminal of the exit serving a road stop,
    /// for this trip's direction of travel, to the stop's driveway; None for
    /// a stop with no decided exit, one on the mainline, or an exit with no
    /// chain baked from its terminal this way.
    pub fn stop_approach_route(&self, stop: &RoadStop) -> Option<Route> {
        let terminal = self.ramp_terminal_node_at(stop.interchange_mi?)?;
        self.route.legs.iter().find_map(|leg| {
            leg.stops
                .iter()
                .filter(|record| record.name == stop.name)
                .flat_map(|record| &record.approach_chains)
                .find(|chain| chain.terminal_node == terminal)
                .map(|chain| local_chain_route(&leg.a, &chain.segments))
        })
    }

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
