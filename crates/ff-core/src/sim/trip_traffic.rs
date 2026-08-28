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

pub const REAL_TRAFFIC_CHECK_INTERVAL_MI: f64 = 1.0;
pub const REAL_TRAFFIC_RADIUS_MI: f64 = 50.0;

pub trait TrafficProvider {
    fn get_events_near(
        &self,
        state: &str,
        latitude: f64,
        longitude: f64,
        radius_mi: f64,
    ) -> Vec<TrafficEvent>;

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
        crate::speech_text::traffic_status(
            &lead.intent,
            &lead.vehicle_class,
            &self.gap_text(context.gap_mi),
            &self.speed_text(lead.speed_mph),
        )
    }

    pub fn check_npc_traffic_cues(&mut self) {
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
        let cue = NavigationCue::new(
            &format!("npc:{}", lead.key),
            "traffic",
            lead.position_mi,
            lead.reason(),
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
}
