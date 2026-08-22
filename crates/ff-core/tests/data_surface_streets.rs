//! Surface-street segment driving: baked turn cues spoken at boundaries and
//! per-street speed zones, per docs/surface-roads-plan.md Phase 2 (port of
//! `tests/test_surface_streets.py`). The route-building half is live; the
//! Trip-driven assertions are ignored until `sim::trip` lands.

mod data_support;

use data_support::world;
use ff_core::data::world::World;
use ff_core::data::world_models::{Leg, LocalGeometry, Route};

/// Any tier-1 turn-level baked local geometry, built into a drivable
/// Route directly from the retained `local_geometry` data.
///
/// The drive-to-city-services feature (and its `city_service_route`/
/// `city_service_geometry` convenience wrappers) was retired, but the
/// turn-level street-chain bake it used to source test data from is still
/// shipped, so this rebuilds the same Route the wrapper used to hand back.
fn turn_level_route(world: &World) -> Option<(Route, LocalGeometry)> {
    let mut cities: Vec<&String> = world.cities.keys().collect();
    cities.sort();
    for city in cities {
        for service in world.city_services(city).unwrap() {
            let geometry = world
                .local_geometry(&format!("city_service:{city}:{}", service.key))
                .unwrap();
            if let Some(geometry) = geometry {
                if geometry.turn_level && geometry.segments.len() >= 3 {
                    let legs: Vec<Leg> = geometry
                        .segments
                        .iter()
                        .map(|segment| {
                            Leg::local(
                                city,
                                segment.miles,
                                &segment.road,
                                &segment.cue,
                                segment.speed_mph,
                            )
                        })
                        .collect();
                    let route = Route::from_legs(vec![city.clone(); legs.len() + 1], legs);
                    return Some((route, geometry.clone()));
                }
            }
        }
    }
    None
}

fn street_trip(route: Route) -> ff_core::sim::trip::Trip {
    use ff_core::sim::trip::{Trip, TripOptions};
    use ff_core::sim::vehicle::TruckState;
    use ff_core::sim::weather::WeatherSystem;

    let mut truck = TruckState::default();
    truck.transmission.automatic = true;
    Trip::new(
        route,
        truck,
        WeatherSystem::new("heartland", Some(1), None, None, true),
        TripOptions {
            seed: Some(2),
            world: Some(world()),
            ..Default::default()
        },
    )
}

#[test]
fn test_turn_level_route_carries_segment_cues_and_speeds() {
    let Some((route, geometry)) = turn_level_route(world()) else {
        return; // no turn-level city service geometry in the shipped data
    };
    assert_eq!(route.legs.len(), geometry.segments.len());
    for (leg, segment) in route.legs.iter().zip(geometry.segments.iter()) {
        assert_eq!(leg.highway, segment.road);
        assert_eq!(leg.local_cue, segment.cue);
        assert_eq!(leg.local_speed_mph, segment.speed_mph);
    }
}

#[test]
fn test_navigation_cues_speak_the_baked_maneuvers() {
    let Some((route, geometry)) = turn_level_route(world()) else {
        return; // no turn-level city service geometry in the shipped data
    };
    let trip = street_trip(route);
    let spoken = trip
        .navigation_cues
        .iter()
        .map(|cue| cue.near_text.as_str())
        .collect::<Vec<_>>()
        .join(" | ");
    // Every road-change maneuver from the baked data is announced verbatim
    // (same-road consecutive segments collapse into the previous cue).
    for pair in geometry.segments.windows(2) {
        let (prev, segment) = (&pair[0], &pair[1]);
        if segment.road != prev.road {
            assert!(spoken.contains(segment.cue.trim_end_matches('.')), "{spoken}");
        }
    }
    assert!(spoken.contains(geometry.segments[0].cue.trim_end_matches('.')));
}

#[test]
fn test_the_access_road_posts_one_limit_and_the_gate() {
    // One number for the chain, one change at the gate -- never a new posting
    // every few hundred feet (owner playtest, 2026-08-21).
    use ff_core::sim::trip_models::FACILITY_GATE_LIMIT_MPH;

    let Some((route, geometry)) = turn_level_route(world()) else {
        return;
    };
    let mut trip = street_trip(route);
    let street_zones: Vec<_> = trip
        .zones
        .iter()
        .filter(|z| z.reason == "facility access road")
        .cloned()
        .collect();
    assert_eq!(street_zones.len(), 1);
    assert_eq!(street_zones[0].start_mi, 0.0);
    assert!((street_zones[0].end_mi - trip.total_miles()).abs() < 1e-9);
    // It speaks a speed the baked street data actually holds, and never a
    // lower crawl than the best street on the chain offers.
    let baked_max = geometry
        .segments
        .iter()
        .map(|s| s.speed_mph)
        .fold(f64::MIN, f64::max);
    assert_eq!(street_zones[0].limit_mph, baked_max);
    assert!((5.0..=65.0).contains(&street_zones[0].limit_mph));
    // The gate zone still caps the final stretch.
    assert!(trip
        .zones
        .iter()
        .any(|z| z.reason == "facility gate" && z.limit_mph == FACILITY_GATE_LIMIT_MPH));
    // And walking the chain, the posted limit changes exactly once: at the
    // gate.
    let step = (trip.total_miles() / 400.0).max(0.001);
    let mut seen: Vec<f64> = Vec::new();
    let mut mile = 0.0;
    while mile <= trip.total_miles() {
        let (limit, _) = trip.speed_limit_at(mile);
        if seen.last().is_none_or(|last| *last != limit) {
            seen.push(limit);
        }
        mile += step;
    }
    assert_eq!(seen, vec![street_zones[0].limit_mph, FACILITY_GATE_LIMIT_MPH]);
}

#[test]
fn test_single_leg_approaches_keep_the_blanket_zone() {
    let world = world();
    let route = world
        .facility_approach_route("Chicago", &world.city("Chicago").unwrap().locations[0].name)
        .unwrap();
    if route.legs.iter().any(|leg| leg.local_speed_mph > 0.0) {
        return; // this facility gained turn-level data; blanket no longer applies
    }
    let trip = street_trip(route);
    let access: Vec<_> = trip
        .zones
        .iter()
        .filter(|z| z.reason == "facility access road")
        .collect();
    assert_eq!(access.len(), 1);
    assert_eq!(access[0].limit_mph, 25.0);
    assert!((access[0].end_mi - trip.total_miles()).abs() < 1e-9);
}
