//! Real construction zones from state 511 APIs mapped onto the trip (the
//! Trip half of `tests/test_real_construction_zones.py`; the provider and
//! parser classes live with `sim::real_traffic`).

use std::sync::Arc;

use crate::sim_support::*;
use ff_core::data::world_models::{
    CorridorDetail, LaneSegment, Leg, Route, RoutePoint, StateMileage,
};
use ff_core::sim::real_traffic_parsers::TrafficEvent;
use ff_core::sim::trip::{Trip, TripOptions};
use ff_core::sim::trip_models::CONSTRUCTION_TAPER_MI;
use ff_core::sim::trip_route_helpers::nearest_mile_on_leg;
use ff_core::sim::trip_traffic::TrafficProvider;
use ff_core::sim::vehicle::{TruckSpecs, TruckState};

// --- Helpers ----------------------------------------------------------------

fn rp(at_mi: f64, lat: f64, lon: f64) -> RoutePoint {
    RoutePoint { at_mi, lat, lon }
}

fn default_points() -> Vec<RoutePoint> {
    // A simple set of route points along the highway
    vec![
        rp(0.0, 39.9612, -82.9988), // Columbus
        rp(15.0, 39.83, -83.01),
        rp(30.0, 39.70, -83.10),
        rp(45.0, 39.57, -83.18),
        rp(60.0, 39.45, -83.27),
        rp(75.0, 39.32, -83.35),
        rp(100.0, 39.1031, -84.5120), // Cincinnati
    ]
}

fn make_leg_with(miles: f64, route_points: Vec<RoutePoint>) -> Leg {
    Leg::new(
        "columbus_oh_us",
        "cincinnati_oh_us",
        miles,
        "I-71",
        "flat",
        Vec::new(),
    )
    .with_detail(CorridorDetail {
        route_points,
        state_miles: vec![StateMileage::new("Ohio", miles)],
        ..Default::default()
    })
}

fn make_leg() -> Leg {
    make_leg_with(100.0, default_points())
}

/// `MagicMock(spec=RealTrafficProvider)` with a fixed construction answer.
struct FakeProvider {
    construction: Vec<TrafficEvent>,
}

impl TrafficProvider for FakeProvider {
    fn get_events_near(&self, _: &str, _: f64, _: f64, _: f64) -> Vec<TrafficEvent> {
        Vec::new()
    }

    fn get_construction_near_route(
        &self,
        _: &str,
        _: &[(f64, f64)],
        _: Option<&str>,
        _: f64,
    ) -> Vec<TrafficEvent> {
        self.construction.clone()
    }
}

fn provider(construction: Vec<TrafficEvent>) -> Arc<dyn TrafficProvider> {
    Arc::new(FakeProvider { construction })
}

fn trip_for(route: Route, traffic_provider: Option<Arc<dyn TrafficProvider>>) -> Trip {
    Trip::new(
        route,
        TruckState::new(TruckSpecs::default()),
        default_weather(),
        TripOptions {
            time_scale: 1.0,
            seed: Some(42),
            traffic_provider,
            world: Some(world()),
            ..Default::default()
        },
    )
}

/// Create a minimal trip for testing.
fn make_trip(traffic_provider: Option<Arc<dyn TrafficProvider>>) -> Trip {
    let route = Route::from_legs(
        vec!["columbus_oh_us".to_string(), "cincinnati_oh_us".to_string()],
        vec![make_leg()],
    );
    trip_for(route, traffic_provider)
}

fn event(
    id: &str,
    lat: f64,
    lon: f64,
    location_text: &str,
    work_type: &str,
    closure: &str,
) -> TrafficEvent {
    TrafficEvent {
        id: id.to_string(),
        event_type: "construction".to_string(),
        severity: "medium".to_string(),
        description: "Paving".to_string(),
        county: "Franklin".to_string(),
        latitude: Some(lat),
        longitude: Some(lon),
        road_name: "I-71".to_string(),
        location_text: location_text.to_string(),
        work_type: work_type.to_string(),
        closure: closure.to_string(),
        ..Default::default()
    }
}

// --- TestNearestMileOnLeg ---------------------------------------------------

#[test]
fn test_snap_near_start() {
    let leg = make_leg();
    let mile = nearest_mile_on_leg(39.96, -83.0, &leg, true, 0.0).expect("on the route");
    assert!((0.0..=2.0).contains(&mile));
}

#[test]
fn test_snap_near_end() {
    let leg = make_leg_with(100.0, default_points());
    let mile = nearest_mile_on_leg(39.11, -84.51, &leg, true, 0.0).expect("on the route");
    assert!((95.0..=105.0).contains(&mile));
}

#[test]
fn test_snap_midpoint() {
    let leg = make_leg_with(100.0, default_points());
    let mile = nearest_mile_on_leg(39.569, -83.179, &leg, true, 0.0).expect("on the route");
    assert_eq!(mile, 45.0);
}

#[test]
fn test_off_route_returns_none() {
    let leg = make_leg();
    // Chicago, not on I-71
    assert!(nearest_mile_on_leg(41.0, -87.0, &leg, true, 0.0).is_none());
}

#[test]
fn test_no_route_points_returns_none() {
    let leg = make_leg_with(100.0, Vec::new());
    assert!(nearest_mile_on_leg(39.96, -83.0, &leg, true, 0.0).is_none());
}

#[test]
fn test_reverse_direction() {
    let leg = make_leg_with(100.0, default_points());
    assert!(nearest_mile_on_leg(39.11, -84.51, &leg, false, 0.0).is_some());
}

// --- TestPlaceRealConstructionZones -----------------------------------------

#[test]
fn test_no_provider_returns_empty() {
    let trip = make_trip(None);
    assert!(trip.place_real_construction_zones().is_empty());
}

#[test]
fn test_no_events_returns_empty() {
    let trip = make_trip(Some(provider(Vec::new())));
    assert!(trip.place_real_construction_zones().is_empty());
}

#[test]
fn test_event_converts_to_zone() {
    let trip = make_trip(Some(provider(vec![event(
        "cz-1",
        39.83,
        -83.01,
        "Near milepost 15",
        "paving",
        "single lane",
    )])));
    let zones = trip.place_real_construction_zones();
    // Should create a pair: construction merge taper + construction zone
    assert_eq!(zones.len(), 2);
    assert_eq!(zones[0].reason, "construction merge");
    assert_eq!(zones[1].reason, "construction");
    // Zone should have the right speed limit for single lane closure
    assert_eq!(zones[1].limit_mph, 45.0);
}

#[test]
fn test_multiple_events_separate_zones() {
    let trip = make_trip(Some(provider(vec![
        event("cz-1", 39.83, -83.01, "", "", "single lane"),
        event("cz-2", 39.31, -83.34, "", "", "alternating"),
    ])));
    let zones = trip.place_real_construction_zones();
    assert_eq!(zones.len(), 4);
    let reasons: Vec<&str> = zones.iter().map(|z| z.reason.as_str()).collect();
    assert_eq!(reasons.iter().filter(|r| **r == "construction").count(), 2);
    assert_eq!(
        reasons
            .iter()
            .filter(|r| **r == "construction merge")
            .count(),
        2
    );
    // The second zone (Cincinnati) should have alternating closure speed
    assert_eq!(zones.last().unwrap().limit_mph, 35.0);
}

#[test]
fn test_events_ignored_when_far_from_route() {
    // Cleveland - far from I-71 Columbus-Cincinnati
    let mut far = event("cz-far", 41.5, -81.7, "", "", "shoulder");
    far.road_name = "I-90".to_string();
    far.severity = "low".to_string();
    let trip = make_trip(Some(provider(vec![far])));
    assert!(trip.place_real_construction_zones().is_empty());
}

fn lane_route(lane_segment: LaneSegment) -> Route {
    let leg = with_corridor(&make_leg(), |d| d.lane_segments = vec![lane_segment]);
    Route::from_legs(
        vec!["columbus_oh_us".to_string(), "cincinnati_oh_us".to_string()],
        vec![leg],
    )
}

#[test]
fn test_single_lane_road_keeps_every_lane_open() {
    // A reported closure on a one-lane-each-way road is placed with no
    // coned-off lane: closing the only lane leaves nowhere legal to drive.
    let route = lane_route(LaneSegment {
        start_mi: 0.0,
        end_mi: 100.0,
        lanes: 2,
        oneway: false,
        ..Default::default()
    });
    let trip = trip_for(
        route,
        Some(provider(vec![event(
            "cz-narrow",
            39.83,
            -83.01,
            "",
            "",
            "single lane",
        )])),
    );
    let zones = trip.place_real_construction_zones();
    assert!(!zones.is_empty()); // the work zone is still announced
    assert!(zones.iter().all(|z| z.closed_lane.is_none()));
}

#[test]
fn test_two_lane_road_still_closes_a_lane() {
    // Where there is a lane to merge into, the reported closure stands.
    let route = lane_route(LaneSegment {
        start_mi: 0.0,
        end_mi: 100.0,
        lanes: 2,
        oneway: true,
        ..Default::default()
    });
    let trip = trip_for(
        route,
        Some(provider(vec![event(
            "cz-wide",
            39.83,
            -83.01,
            "",
            "",
            "single lane",
        )])),
    );
    let zones = trip.place_real_construction_zones();
    let closed: Vec<Option<i64>> = zones.iter().map(|z| z.closed_lane).collect();
    assert_eq!(closed, vec![Some(0), Some(0)]);
}

#[test]
fn test_facility_approach_route_returns_empty() {
    // Facility approach routes skip real construction zones.
    let route = Route::from_legs(
        vec!["columbus_oh_us".to_string(), "columbus_oh_us".to_string()],
        vec![make_leg_with(2.0, Vec::new())],
    );
    let trip = trip_for(route, Some(provider(Vec::new())));
    assert!(trip.place_real_construction_zones().is_empty());
}

// --- TestConstructionZoneIntegration ---------------------------------------

#[test]
fn test_simulated_zones_when_no_provider() {
    // Without a traffic provider, the trip still builds zones (congestion,
    // facility approach) -- simulated construction is 1 per 150 miles.
    let trip = make_trip(None);
    let _ = trip.zones.len();
}

#[test]
fn test_real_zones_replace_simulated() {
    let trip = make_trip(Some(provider(vec![event(
        "cz-1",
        39.83,
        -83.01,
        "",
        "",
        "single lane",
    )])));
    let real_zones = trip
        .zones
        .iter()
        .filter(|z| z.reason == "construction")
        .count();
    let real_merge = trip
        .zones
        .iter()
        .filter(|z| z.reason == "construction merge")
        .count();
    assert!(real_zones >= 1);
    assert!(real_merge >= 1);
}

#[test]
fn test_route_state_identification() {
    let trip = make_trip(None);
    let geometry = trip.collect_route_geometry();
    let (state, points) = geometry.get("I-71").expect("our highway");
    assert_eq!(state, "Ohio");
    assert!(points.len() >= 7); // We defined 7 route points
}

#[test]
fn test_construction_zone_speed_single_lane() {
    let ev = event("test", 39.83, -83.01, "", "", "single lane");
    assert_eq!(Trip::construction_zone_speed(&ev), 45.0);
}

#[test]
fn test_construction_zone_speed_full_closure() {
    let ev = event("test", 39.83, -83.01, "", "", "full closure");
    assert_eq!(Trip::construction_zone_speed(&ev), 15.0);
}

#[test]
fn test_construction_zone_length_from_location() {
    let ev = event(
        "test",
        39.83,
        -83.01,
        "Between milepost 45 and 47",
        "",
        "single lane",
    );
    assert_eq!(Trip::construction_zone_length(&ev), 2.0); // 47 - 45 = 2
}

#[test]
fn test_construction_zone_length_default() {
    let ev = event("test", 39.83, -83.01, "", "", "single lane");
    // Default when no work_type matches: 4.0 miles
    assert_eq!(Trip::construction_zone_length(&ev), 4.0);
}

// --- TestZoneNeedsRoomForItsTaper -------------------------------------------
// Owner report, 2026-08-16: departing a facility could drop the truck inside
// the cones before it had moved.

fn zones_for_event_at(lat: f64, lon: f64) -> Vec<ff_core::sim::trip_models::Zone> {
    let trip = make_trip(Some(provider(vec![event(
        "cz-start",
        lat,
        lon,
        "Near milepost 0",
        "paving",
        "single lane",
    )])));
    trip.place_real_construction_zones()
}

#[test]
fn test_a_zone_at_the_very_start_is_dropped() {
    // The first route point is mile 0 itself; a zone centred there cannot
    // fit a taper ahead of the driver, so nothing is placed at all.
    assert!(zones_for_event_at(39.9612, -82.9988).is_empty());
}

#[test]
fn test_a_zone_with_room_still_gets_its_full_taper() {
    // The guard is about the warning fitting, not about a quiet start.
    let zones = zones_for_event_at(39.83, -83.01); // ~mile 15
    assert_eq!(zones.len(), 2);
    let (taper, work) = (&zones[0], &zones[1]);
    assert_eq!(taper.reason, "construction merge");
    assert_eq!(work.reason, "construction");
    // The taper is on the route, ahead of the start, and full length.
    assert!(taper.start_mi >= 0.0);
    assert!(work.start_mi >= CONSTRUCTION_TAPER_MI);
    assert_eq!(work.start_mi - taper.start_mi, CONSTRUCTION_TAPER_MI);
}
