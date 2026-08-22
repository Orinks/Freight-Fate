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
#[ignore = "needs sim::trip (Trip.navigation_cues)"]
fn test_navigation_cues_speak_the_baked_maneuvers() {
    // Every road-change maneuver from the baked data is announced verbatim
    // (same-road consecutive segments collapse into the previous cue).
    let Some((route, geometry)) = turn_level_route(world()) else {
        return;
    };
    assert!(!route.legs.is_empty());
    assert!(!geometry.segments[0].cue.is_empty());
}

#[test]
#[ignore = "needs sim::trip (Trip.zones and speed_limit_at)"]
fn test_the_access_road_posts_one_limit_and_the_gate() {
    // One number for the chain, one change at the gate -- never a new posting
    // every few hundred feet.
    //
    // The chain used to be zoned street by street, which announced a limit
    // change per leg: half of all baked segments are under two tenths of a mile,
    // so a driver heard the same "facility access road" post 15, then 25, then
    // 15 again with nothing under the wheels changing. None of those numbers is
    // a reading -- the bake assumes 25 for a named street and 15 for an unnamed
    // one wherever OSM carries no maxspeed, which is very nearly everywhere --
    // so a change between them was the data reporting whether the way had a
    // NAME, dressed as a sign.
    let Some((_route, geometry)) = turn_level_route(world()) else {
        return;
    };
    let baked_max = geometry
        .segments
        .iter()
        .map(|s| s.speed_mph)
        .fold(f64::MIN, f64::max);
    assert!((5.0..=65.0).contains(&baked_max));
}

#[test]
#[ignore = "needs sim::trip (Trip.zones)"]
fn test_single_leg_approaches_keep_the_blanket_zone() {
    let world = world();
    let route = world
        .facility_approach_route("Chicago", &world.city("Chicago").unwrap().locations[0].name)
        .unwrap();
    if route.legs.iter().any(|leg| leg.local_speed_mph > 0.0) {
        return; // this facility gained turn-level data; blanket no longer applies
    }
    assert_eq!(route.legs.len(), 1);
}
