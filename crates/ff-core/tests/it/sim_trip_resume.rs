//! Mid-trip save and resume: the one case of `tests/test_trip_resume.py` that
//! is world-data work rather than app-shell work.
//!
//! The other twenty-one cases drive the App shell -- `DrivingState`, the pause
//! menu, the title screen -- which `ff-core` cannot see. They ran here as
//! `#[ignore]`d stubs, which is no coverage at all, and now run for real in
//! `crates/freight-fate/tests/states_driving_trip_resume.rs`.


use crate::sim_support::*;

#[test]
fn test_route_from_cities_roundtrip() {
    let w = world();
    let route = w
        .shortest_route("Chicago", "Denver", None, false)
        .unwrap()
        .expect("a route");
    let rebuilt = w
        .route_from_cities(&route.cities)
        .expect("the same cities rebuild the route");
    assert_eq!(rebuilt.cities, route.cities);
    let ids = |r: &ff_core::data::world_models::Route| {
        r.legs
            .iter()
            .map(|l| (l.a.clone(), l.b.clone(), l.miles))
            .collect::<Vec<_>>()
    };
    assert_eq!(ids(&rebuilt), ids(&route));
    assert!(w.route_from_cities(&["Chicago"]).is_none());
    assert!(w.route_from_cities(&["Chicago", "Not A City"]).is_none());
}
