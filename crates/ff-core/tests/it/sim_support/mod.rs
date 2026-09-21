//! Shared helpers for the `sim_*` integration tests: the session world, the
//! `make_trip` fixture from `tests/test_weather_trip.py`, and the
//! `dataclasses.replace(leg, ...)` stand-in for editing one leg's corridor.
#![allow(dead_code)]

use std::sync::Arc;

use ff_core::data::world::{get_world, World};
use ff_core::data::world_models::{CorridorDetail, Leg, Route};
use ff_core::sim::enforcement_posts::{method_by_kind, EnforcementPost};
use ff_core::sim::trip::{Trip, TripOptions};
use ff_core::sim::trip_models::{RoadStop, TripEvent, TripEventKind};
use ff_core::sim::vehicle::TruckState;
use ff_core::sim::weather::WeatherSystem;

/// The shared world fixture (`conftest.world`).
pub fn world() -> &'static World {
    get_world()
}

/// `WeatherSystem(region, seed=seed)`.
pub fn weather(region: &str, seed: i64) -> WeatherSystem {
    WeatherSystem::new(region, Some(seed), None, None, true)
}

/// `WeatherSystem()` with every default.
pub fn default_weather() -> WeatherSystem {
    WeatherSystem::new("heartland", None, None, None, true)
}

/// `world.route_options(start, end)[0]`.
pub fn first_route_option(world: &World, start: &str, end: &str) -> Route {
    world
        .route_options(start, end, 3, false)
        .unwrap_or_else(|e| panic!("{start} -> {end}: {e}"))
        .into_iter()
        .next()
        .unwrap_or_else(|| panic!("{start} -> {end}: no route"))
}

/// `world.supported_route(a, b)` that must exist.
pub fn supported(world: &World, a: &str, b: &str) -> Route {
    world
        .supported_route(a, b, None)
        .unwrap_or_else(|e| panic!("{a} -> {b}: {e}"))
        .unwrap_or_else(|| panic!("{a} to {b} is not dispatch-supported"))
}

/// `world.route_from_cities([...])` that must exist.
pub fn route_from_cities(world: &World, cities: &[&str]) -> Route {
    world
        .route_from_cities(cities)
        .unwrap_or_else(|| panic!("no route through {cities:?}"))
}

/// `tests/test_weather_trip.py::make_trip`: a quiet Chicago-Indianapolis run
/// (rolling traffic bubble off) with an automatic, running truck.
pub fn make_trip(world: &'static World, start: &str, end: &str, seed: i64) -> Trip {
    make_trip_with(world, start, end, TripOptions::seeded(seed))
}

pub fn make_trip_with(world: &'static World, start: &str, end: &str, opts: TripOptions) -> Trip {
    let route = first_route_option(world, start, end);
    let mut truck = TruckState::default();
    truck.transmission.automatic = true;
    truck.start_engine();
    let weather = weather("great_lakes", 1);
    let mut trip = Trip::new(
        route,
        truck,
        weather,
        TripOptions {
            world: Some(world),
            ..opts
        },
    );
    trip.traffic_manager.rolling_bubble = false;
    trip
}

/// `dataclasses.replace(leg, <corridor field>=...)`: a copy of the leg with
/// its corridor detail edited.
pub fn with_corridor(leg: &Leg, edit: impl FnOnce(&mut CorridorDetail)) -> Leg {
    let mut detail = leg.corridor().clone();
    edit(&mut detail);
    leg.clone().with_detail(detail)
}

/// `route.legs[index] = replacement`.
pub fn replace_leg(route: &Route, index: usize, replacement: Leg) -> Route {
    let mut legs = route.legs.clone();
    legs[index] = Arc::new(replacement);
    Route::new(route.cities.clone(), legs)
}

/// GPS-cue events, excluding additive interchange/exit cues (the tests
/// target one specific cue and curated interchanges share the stream).
pub fn gps_events(events: &[TripEvent]) -> Vec<TripEvent> {
    events
        .iter()
        .filter(|e| {
            e.kind == TripEventKind::GpsCue
                && e.data
                    .cue
                    .as_ref()
                    .is_none_or(|cue| cue.kind != "interchange")
        })
        .cloned()
        .collect()
}

pub fn gps_messages(events: &[TripEvent]) -> Vec<String> {
    gps_events(events)
        .iter()
        .map(|e| e.text().to_string())
        .collect()
}

/// `tests/enforcement_helpers.py::always_observing_post`: a staffed,
/// already-heard post watching `reach_mi` up to `at_mi`.
pub fn always_observing_post(
    at_mi: f64,
    kind: &str,
    reach_mi: f64,
    notice: f64,
    leg_index: usize,
) -> EnforcementPost {
    EnforcementPost {
        method: method_by_kind(kind).to_string(),
        reach_mi,
        facing: "both".to_string(),
        staffed: true,
        notice,
        announced: true,
        leg_index,
        ..EnforcementPost::new(at_mi, kind)
    }
}

/// `tests/enforcement_helpers.py::open_scale_post`: an open weigh station
/// standing behind `stop`.
pub fn open_scale_post(stop: &RoadStop, leg_index: usize) -> EnforcementPost {
    EnforcementPost {
        method: method_by_kind("fixed_scale").to_string(),
        reach_mi: 0.5,
        facing: "with_traffic".to_string(),
        staffed: true,
        anchor: stop.key(),
        announced: true,
        leg_index,
        ..EnforcementPost::new(stop.at_mi, "fixed_scale")
    }
}

pub fn messages_of(events: &[TripEvent], kind: TripEventKind) -> Vec<String> {
    events
        .iter()
        .filter(|e| e.kind == kind)
        .map(|e| e.text().to_string())
        .collect()
}
