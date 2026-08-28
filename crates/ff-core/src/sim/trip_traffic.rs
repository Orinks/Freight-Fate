//! Traffic and patrol lookup helpers for trip simulation (port of
//! `freight_fate/sim/trip_traffic.py`, the former `TripTrafficMixin`).

use indexmap::IndexMap;
use regex::Regex;

use crate::data::world_models::Leg;
use crate::pyrandom::PyRandom;
use crate::sim::enforcement_posts::{
    post_seed, EnforcementPost, KIND_CHAIN, KIND_CMV, KIND_FIXED_SCALE, KIND_MEDIAN, KIND_ROVING,
    KIND_SCALE_APRON, KIND_URBAN, KIND_WORK_ZONE,
};
use crate::sim::real_traffic::RealTrafficProvider;
use crate::sim::real_traffic_parsers::TrafficEvent;
use crate::sim::trip::Trip;
use crate::sim::trip_models::*;
use crate::sim::trip_route_helpers::nearest_mile_on_leg;
use crate::speech_text::SpokenMessage;

/// Incident lookups filter the whole cached state feed by distance, so
/// re-check on a mile cadence rather than every simulation tick.
pub const REAL_TRAFFIC_CHECK_INTERVAL_MI: f64 = 1.0;
pub const REAL_TRAFFIC_RADIUS_MI: f64 = 50.0;

/// The duck-typed `traffic_provider` the Python trip asked two questions of.
/// The real provider answers from its cache; a test double answers from a
/// list. Python wrapped both calls in `try/except`; a Rust provider simply
/// returns an empty list where it cannot answer.
pub trait TrafficProvider {
    /// Incidents within `radius_mi` of a point in `state`.
    fn get_events_near(
        &self,
        state: &str,
        latitude: f64,
        longitude: f64,
        radius_mi: f64,
    ) -> Vec<TrafficEvent>;

    /// Construction events near a route's geometry on a named road.
    fn get_construction_near_route(
        &self,
        state: &str,
        route_points: &[(f64, f64)],
        road_name: Option<&str>,
        radius_mi: f64,
    ) -> Vec<TrafficEvent>;
}

impl TrafficProvider for RealTrafficProvider {
    fn get_events_near(
        &self,
        state: &str,
        latitude: f64,
        longitude: f64,
        radius_mi: f64,
    ) -> Vec<TrafficEvent> {
        RealTrafficProvider::get_events_near(self, state, latitude, longitude, radius_mi)
    }

    fn get_construction_near_route(
        &self,
        state: &str,
        route_points: &[(f64, f64)],
        road_name: Option<&str>,
        radius_mi: f64,
    ) -> Vec<TrafficEvent> {
        RealTrafficProvider::get_construction_near_route(
            self,
            state,
            route_points,
            road_name,
            radius_mi,
        )
    }
}

impl Trip {
    pub fn traffic_context(&self) -> Option<TrafficContext> {
        self.traffic_manager
            .lead_vehicle(self.position_mi, self.truck.speed_mph())
    }

    pub fn traffic_target_speed(&self) -> Option<f64> {
        self.traffic_context().map(|context| context.lead.speed_mph)
    }

    pub fn npc_traffic_status(&self) -> String {
        let Some(context) = self.traffic_context() else {
            return "Traffic: no close traffic ahead.".to_string();
        };
        let lead = &context.lead;
        format!(
            "Traffic: {} {} ahead in {}, moving {}.",
            lead.status_label(),
            self.gap_text(context.gap_mi),
            lead.lane_text(),
            self.speed_text(lead.speed_mph)
        )
    }

    pub fn check_npc_traffic_cues(&mut self) {
        // Gate BEFORE next_situation: returning a situation marks its vehicle
        // announced, so a gated call would burn the announcement without
        // speaking it (see road_event_pacing).
        if !self.event_breather.ready("traffic") {
            return;
        }
        let Some(situation) = self
            .traffic_manager
            .next_situation(self.position_mi, self.truck.speed_mph())
        else {
            return;
        };
        self.event_breather.spoke("traffic");
        let lead = situation.vehicle;
        let label = lead.status_label();
        let cue = NavigationCue::new(
            &format!("npc:{}", lead.key),
            "traffic",
            lead.position_mi,
            &label,
            "",
        )
        .with_speed(Some(lead.speed_mph));
        self.emit(
            TripEventKind::GpsCue,
            situation.message,
            TripEventData {
                cue: Some(cue),
                npc_vehicle: Some(lead),
                ..Default::default()
            },
        );
    }

    // -- CB chatter ----------------------------------------------------------
    // "Bear" is CB voice. It may appear only inside a clause the line
    // attributes to the CB, never in a warning, a menu, or a status readout,
    // where the word is "trooper".

    /// How firmly the channel is standing behind this report: a blind
    /// player cannot falsify a CB call, so an unreliable channel carries its
    /// unreliability in the words. Wrong in one direction only: it may call
    /// a post that turns out to be empty, never say the road is clear.
    pub fn cb_confidence(&self, post: &EnforcementPost) -> &'static str {
        let rolled =
            PyRandom::new_from_str(&post_seed(self.seed, &post.id(), "cb_confidence")).random();
        if post.staffed {
            if rolled < 0.55 {
                "strong"
            } else {
                "ordinary"
            }
        } else if rolled < 0.7 {
            "thin"
        } else {
            "ordinary"
        }
    }

    /// Where on the road the CB says it is. Words, never pan alone.
    pub fn cb_side(post: &EnforcementPost) -> &'static str {
        match post.kind.as_str() {
            KIND_MEDIAN => "in the median",
            KIND_ROVING => "working with traffic",
            KIND_WORK_ZONE => "in the work zone",
            KIND_SCALE_APRON => "on the scale apron",
            KIND_FIXED_SCALE => "at the scale",
            KIND_URBAN => "coming into town",
            KIND_CMV => "on the right shoulder",
            KIND_CHAIN => "at the chain-up area",
            _ => "up ahead",
        }
    }

    /// Player-facing CB chatter for one enforcement post. The confidence
    /// framing is the same for every kind; what differs is what the post
    /// actually is. Bear stays CB slang for a trooper on the open road,
    /// never for a fixed inspection facility or a chain checkpoint.
    pub fn cb_patrol_message(&self, post: &EnforcementPost, ahead_mi: f64) -> String {
        let distance = self.ahead_text(ahead_mi.max(0.0));
        let confidence = self.cb_confidence(post);
        let side = Self::cb_side(post);
        if post.kind == KIND_WORK_ZONE {
            return match confidence {
                "strong" => {
                    format!("CB chatter, {distance}: two drivers say troopers are working {side}.")
                }
                "ordinary" => {
                    format!("CB chatter, {distance}: a driver says troopers are working {side}.")
                }
                _ => {
                    format!("CB chatter: somebody said troopers were working {side} a while back.")
                }
            };
        }
        if post.kind == KIND_SCALE_APRON || post.kind == KIND_FIXED_SCALE {
            return match confidence {
                "strong" => {
                    format!("CB chatter, {distance}: two drivers say they're checking logs {side}.")
                }
                "ordinary" => {
                    format!("CB chatter, {distance}: a driver says they're checking logs {side}.")
                }
                _ => format!(
                    "CB chatter: somebody said they were checking logs {side} a while back."
                ),
            };
        }
        if post.kind == KIND_CMV {
            return match confidence {
                "strong" => format!(
                    "CB chatter, {distance}: two drivers say they're checking logs and equipment {side}."
                ),
                "ordinary" => format!(
                    "CB chatter, {distance}: a driver says they're checking logs and equipment {side}."
                ),
                _ => format!(
                    "CB chatter: somebody said they were checking logs and equipment {side} a while back."
                ),
            };
        }
        if post.kind == KIND_CHAIN {
            return match confidence {
                "strong" => format!(
                    "CB chatter, {distance}: two drivers say the chain control is checking rigs {side}."
                ),
                "ordinary" => format!(
                    "CB chatter, {distance}: a driver says the chain control is checking rigs {side}."
                ),
                _ => format!(
                    "CB chatter: somebody said the chain control was checking rigs {side} a while back."
                ),
            };
        }
        match confidence {
            "strong" => format!("CB chatter, {distance}: two drivers call a bear {side}."),
            "ordinary" => format!("CB chatter, {distance}: a driver reports a bear {side}."),
            _ => format!("CB chatter: somebody called a bear {side} a while back."),
        }
    }

    /// CB chatter for a bear who already has somebody else stopped.
    pub fn cb_tableau_message(&self, post: &EnforcementPost, ahead_mi: f64) -> String {
        let distance = self.ahead_text(ahead_mi.max(0.0));
        let confidence = self.cb_confidence(post);
        let side = Self::cb_side(post);
        match confidence {
            "strong" => format!(
                "CB chatter, {distance}: two drivers say a bear already has somebody stopped {side}."
            ),
            "ordinary" => format!(
                "CB chatter, {distance}: a driver says a bear already has somebody stopped {side}."
            ),
            _ => format!("CB chatter: somebody said a bear had somebody stopped {side} a while back."),
        }
    }

    /// The on-demand road-ahead readout's enforcement clause, at full detail
    /// whatever the presence setting is.
    pub fn cb_patrol_status(&self, post: &EnforcementPost, ahead_mi: f64) -> String {
        let distance = self.ahead_text(ahead_mi.max(0.0));
        let where_ = Self::cb_side(post);
        if ahead_mi <= 0.0 {
            return format!("an enforcement post {where_} on this stretch");
        }
        format!("an enforcement post {where_} in {distance}")
    }

    /// Nearest enforcement post at or ahead of the truck in the lookahead.
    pub fn next_patrol_within(&self, within_mi: f64) -> Option<&EnforcementPost> {
        self.next_post_within(within_mi)
    }

    /// The trip's own rush-hour bias, read at the DEPARTURE hour (the
    /// manager's reads the live clock).
    pub fn rush_hour_traffic_bias(&self, leg: &Leg) -> f64 {
        if !RUSH_HOUR_WINDOWS
            .iter()
            .any(|(start, end)| *start <= self.start_hour && self.start_hour < *end)
        {
            return 0.0;
        }
        if leg.checkpoints().is_empty() {
            0.06
        } else {
            0.14
        }
    }

    pub fn traffic_pressure_at(&self, mile: Option<f64>) -> Option<TrafficPressure> {
        let sample = mile.unwrap_or(self.position_mi);
        self.traffic_pressures
            .iter()
            .filter(|p| p.start_mi <= sample && sample <= p.end_mi)
            .max_by(|a, b| {
                a.intensity
                    .partial_cmp(&b.intensity)
                    .expect("finite intensities")
            })
            .cloned()
    }

    /// Announce nearby real-time incidents from the state 511 APIs.
    pub fn check_real_traffic_events(&mut self) {
        let Some(provider) = self.traffic_provider.clone() else {
            return;
        };
        if self.position_mi < self.next_real_traffic_check_mi {
            return;
        }
        self.next_real_traffic_check_mi = self.position_mi + REAL_TRAFFIC_CHECK_INTERVAL_MI;

        let (leg_i, leg_start) = self.leg_at_mile(self.position_mi);
        let leg = self.route.legs[leg_i].clone();
        if leg.route_points().is_empty() {
            return;
        }
        let forward = self.route.cities[leg_i] == leg.a;
        let route_offset = self.position_mi - leg_start;
        let leg_offset = if forward {
            route_offset
        } else {
            leg.miles - route_offset
        };

        let state = leg_state_at(&leg, leg_offset);
        if state.is_empty() {
            return;
        }
        let point = leg
            .route_points()
            .iter()
            .min_by(|a, b| {
                (a.at_mi - leg_offset)
                    .abs()
                    .partial_cmp(&(b.at_mi - leg_offset).abs())
                    .expect("finite mileposts")
            })
            .copied()
            .expect("route points are non-empty");

        let events = provider.get_events_near(&state, point.lat, point.lon, REAL_TRAFFIC_RADIUS_MI);

        for event in events {
            if event.severity != "high" && event.severity != "medium" {
                continue;
            }
            // Construction is spoken through the construction-zone system.
            if event.event_type == "construction" {
                continue;
            }
            let event_key = format!("real_traffic:{}", event.id);
            if self.announced_real_traffic.contains(&event_key) {
                continue;
            }
            // "Live road report", not "traffic alert": these describe the
            // REAL road today; the simulation does not act on them at all
            // (Brandon, 2026-08-21; owner call the same day).
            let mut message = format!("Live road report: {}", event.description);
            if let Some(lanes) = event.lanes_affected.as_ref().filter(|l| !l.is_empty()) {
                message += &format!(". {lanes} affected.");
            }
            self.emit(
                TripEventKind::GpsCue,
                SpokenMessage::new(message),
                TripEventData {
                    real_traffic_event: Some(event),
                    ..Default::default()
                },
            );
            self.announced_real_traffic.insert(event_key);
        }
    }

    pub fn next_traffic_pressure_within(&self, within_mi: f64) -> Option<TrafficPressure> {
        self.traffic_pressures
            .iter()
            .filter(|p| {
                p.end_mi >= self.position_mi
                    && 0.0 <= p.start_mi - self.position_mi
                    && p.start_mi - self.position_mi <= within_mi
            })
            .min_by(|a, b| {
                a.start_mi
                    .partial_cmp(&b.start_mi)
                    .expect("finite mileposts")
            })
            .cloned()
    }

    /// `{highway: (state, [(lat, lon), ...])}` from the route legs, so
    /// construction-zone snapping can check proximity in parallel.
    pub fn collect_route_geometry(&self) -> IndexMap<String, (String, Vec<(f64, f64)>)> {
        let mut geometry: IndexMap<String, (String, Vec<(f64, f64)>)> = IndexMap::new();
        for (i, leg) in self.route.legs.iter().enumerate() {
            let forward = self.route.cities[i] == leg.a;
            let mut state = String::new();
            for sc in leg.state_crossings() {
                state = if forward {
                    sc.from_state.clone()
                } else {
                    sc.state.clone()
                };
            }
            let state_miles = leg.state_miles();
            if !state_miles.is_empty() {
                let first = if forward {
                    &state_miles[0]
                } else {
                    &state_miles[state_miles.len() - 1]
                };
                if state.is_empty() {
                    state = first.state.clone();
                }
            }
            let points: Vec<(f64, f64)> = leg
                .route_points()
                .iter()
                .map(|rp| (rp.lat, rp.lon))
                .collect();
            let normalized = leg.highway.trim().to_uppercase();
            match geometry.get_mut(&normalized) {
                None => {
                    geometry.insert(normalized, (state, points));
                }
                Some((existing_state, existing_points)) => {
                    existing_points.extend(points);
                    if !state.is_empty() && existing_state.is_empty() {
                        *existing_state = state;
                    }
                }
            }
        }
        geometry
    }

    /// Query the traffic provider for real construction events and convert
    /// them into zones mapped to route miles. Empty when no provider is
    /// available, the route is a facility approach, or nothing is close.
    pub fn place_real_construction_zones(&self) -> Vec<Zone> {
        let Some(provider) = self.traffic_provider.as_ref() else {
            return Vec::new();
        };
        if self.is_facility_approach_route() {
            return Vec::new();
        }
        let mut real_zones: Vec<Zone> = Vec::new();
        let mut seen_spans: Vec<(f64, f64)> = Vec::new();
        let route_geo = self.collect_route_geometry();

        for (highway, (state, points)) in route_geo.iter() {
            if state.is_empty() || points.is_empty() {
                continue;
            }
            let events = provider.get_construction_near_route(state, points, Some(highway), 3.0);
            if events.is_empty() {
                continue;
            }
            for event in events {
                let (Some(latitude), Some(longitude)) = (event.latitude, event.longitude) else {
                    continue;
                };
                // Find the nearest leg and snap to route mile.
                let mut best_leg_mile: Option<f64> = None;
                for (i, (start, leg)) in self
                    .leg_starts
                    .iter()
                    .zip(self.route.legs.iter())
                    .enumerate()
                {
                    let forward = self.route.cities[i] == leg.a;
                    if let Some(snapped) =
                        nearest_mile_on_leg(latitude, longitude, leg, forward, *start)
                    {
                        best_leg_mile = Some(snapped);
                        break;
                    }
                }
                let Some(best_leg_mile) = best_leg_mile else {
                    continue;
                };
                let zone_length = Self::construction_zone_length(&event);
                let mut start_mi = (best_leg_mile - zone_length / 2.0).max(0.0);
                let end_mi = self.total_miles().min(start_mi + zone_length);
                start_mi = (end_mi - zone_length).max(0.0);

                // A work zone the driver cannot be warned about is one the
                // game must not place (owner report, 2026-08-16): the
                // warning has to fit.
                if start_mi < CONSTRUCTION_TAPER_MI {
                    continue;
                }
                if seen_spans.iter().any(|(s_start, s_end)| {
                    start_mi < s_end + ZONE_MIN_GAP_MI && end_mi > s_start - ZONE_MIN_GAP_MI
                }) {
                    continue;
                }
                let limit_mph = Self::construction_zone_speed(&event);
                let mut closed_side = Self::construction_closed_side(&event);
                let taper_start = (start_mi - CONSTRUCTION_TAPER_MI).max(0.0);
                // A reported closure still needs a lane to merge into.
                if closed_side.is_some() && !self.span_is_multilane(taper_start, end_mi) {
                    closed_side = None;
                }
                real_zones.push(
                    Zone::new(
                        taper_start,
                        start_mi,
                        CONSTRUCTION_TAPER_LIMIT_MPH,
                        "construction merge",
                    )
                    .with_closed_side(closed_side),
                );
                real_zones.push(
                    Zone::new(start_mi, end_mi, limit_mph, "construction")
                        .with_closed_side(closed_side),
                );
                seen_spans.push((taper_start, end_mi));
            }
        }
        real_zones.sort_by(|a, b| {
            a.start_mi
                .partial_cmp(&b.start_mi)
                .expect("finite mileposts")
        });
        real_zones
    }

    /// Determine the length of a construction zone from event data.
    pub fn construction_zone_length(event: &TrafficEvent) -> f64 {
        // Try to parse from location text (e.g., "Between milepost 45 and 47")
        let location = &event.location_text;
        if !location.is_empty() {
            let re = Regex::new(r"milepost (\d+(?:\.\d+)?) and (\d+(?:\.\d+)?)").expect("static");
            if let Some(caps) = re.captures(location) {
                let start: f64 = caps[1].parse().unwrap_or(0.0);
                let end: f64 = caps[2].parse().unwrap_or(0.0);
                let length = (end - start).abs();
                if (0.5..=20.0).contains(&length) {
                    return length;
                }
            }
        }
        // Default lengths based on work type
        match event.work_type.as_str() {
            "bridge" => 4.0,
            "paving" => 5.0,
            "utility" => 3.0,
            "maintenance" => 2.0,
            "construction" => 5.0,
            _ => 4.0,
        }
    }

    /// Determine the reduced speed limit for a construction zone.
    pub fn construction_zone_speed(event: &TrafficEvent) -> f64 {
        match event.closure.as_str() {
            "full closure" => 15.0,
            "alternating" => 35.0,
            "shoulder" => 55.0, // minimal reduction
            _ => 45.0,          // Single lane closure or default
        }
    }

    /// Which side of the road is coned off, or None if no closure.
    pub fn construction_closed_side(event: &TrafficEvent) -> Option<&'static str> {
        match event.closure.as_str() {
            "full closure" => Some("right"), // right lane closed as part of full closure
            "alternating" | "single lane" => Some("right"), // right lane (typically the closed one)
            "shoulder" => None,              // shoulder work doesn't close a travel lane
            _ => None,
        }
    }
}
