//! The street detail of a facility chain, by route mile: each street's
//! posted limit with the kind of value it is, and the traffic controls OSM
//! reads along the way (`tools/street_chain.py` bakes both), and the zones
//! the drive posts from them.

use crate::data::world_models::StreetLimit;
use crate::sim::trip_models::{Zone, FACILITY_ACCESS_LIMIT_MPH, YARD_LIMIT_MPH};

use super::Trip;

/// The zone reason for a public street of a facility chain.
pub const STREET_ZONE: &str = "facility access road";
/// The zone reason for the facility's own way past the driveway.
pub const YARD_ZONE: &str = "yard";

/// Whether a zone reason is the stretch the gate stands at the end of: the
/// yard on a chain with a driveway, the old signed gate zone everywhere else.
pub fn is_gate_zone_reason(reason: &str) -> bool {
    reason == "facility gate" || reason == YARD_ZONE
}

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

    /// Whether this route is a facility chain that carries the street detail
    /// (a posted limit per street, or a driveway).
    pub fn has_street_detail(&self) -> bool {
        self.is_facility_approach_route()
            && self
                .route
                .legs
                .iter()
                .any(|leg| leg.local_limit.is_some() || leg.local_yard)
    }

    /// The route mile the yard begins at, inbound: where the chain leaves the
    /// public street at its driveway. None without a driveway, and outbound.
    pub fn driveway_mi(&self) -> Option<f64> {
        if self.outbound {
            return None;
        }
        self.route
            .legs
            .iter()
            .position(|leg| leg.local_yard)
            .and_then(|i| self.leg_starts.get(i).copied())
    }

    /// The zones of a chain with street detail: each public street at its own
    /// posted limit -- READ from OSM where the map has one, else the state's
    /// statutory district limit, else assumed, as the bake recorded it (MUTCD
    /// 11th ed. 2B.21 para 01 and 14: a statutory limit, or a speed zone
    /// posted at its points of change) -- joined where neighbours agree, and
    /// the yard from the driveway at the yard limit. The kind of value stays
    /// in the data; the drive only ever speaks the number.
    ///
    /// No gate zone on a public street: the street keeps its limit to the
    /// driveway, the driveway is a turn at corner speed, and the check-in
    /// stop is at the end of the yard. A chain that ends on the public street
    /// has its gate there and no yard.
    pub fn street_zones(&self) -> Vec<Zone> {
        let fallback = self
            .statutory_street_mph()
            .unwrap_or(FACILITY_ACCESS_LIMIT_MPH);
        let mut zones: Vec<Zone> = Vec::new();
        for (leg, start) in self.route.legs.iter().zip(&self.leg_starts) {
            let end = start + leg.miles;
            if end <= *start {
                continue;
            }
            let (reason, limit) = if leg.local_yard {
                (YARD_ZONE, YARD_LIMIT_MPH)
            } else {
                (STREET_ZONE, leg.street_limit_mph().unwrap_or(fallback))
            };
            match zones.last_mut() {
                Some(last)
                    if last.reason == reason
                        && last.limit_mph == limit
                        && (last.end_mi - start).abs() < 1e-9 =>
                {
                    last.end_mi = end;
                }
                _ => zones.push(Zone::new(*start, end, limit, reason)),
            }
        }
        zones
    }

    /// The street zone that ends where `zone` begins: the street before it on
    /// the same chain, when `zone` is a change of limit along the streets
    /// rather than the start of them.
    pub fn street_zone_before(&self, zone: &Zone) -> Option<&Zone> {
        if zone.reason != STREET_ZONE {
            return None;
        }
        self.zones
            .iter()
            .find(|z| z.reason == STREET_ZONE && (z.end_mi - zone.start_mi).abs() < 1e-6)
    }

    /// The stretch the gate stands at the end of, once posted: the yard, or
    /// the old signed gate zone. None on a chain whose gate is on the street.
    pub fn gate_zone(&self) -> Option<&Zone> {
        self.zones
            .iter()
            .find(|zone| is_gate_zone_reason(&zone.reason))
    }
}
