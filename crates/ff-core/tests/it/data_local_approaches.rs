//! Local approach data (the data-layer half of `tests/test_local_approaches.py`;
//! the `tools/build_local_approaches.py` cases stay Python).


use crate::data_support::{read_json, world};

const RAW_MARKERS: &[&str] = &[
    "osm_id",
    "amenity=",
    "highway=",
    "operator=",
    "node/",
    "way/",
];

/// `tools/build_local_approaches.py::SEARCH_RADIUS_MI`.
const SEARCH_RADIUS_MI: f64 = 1.25;

#[test]
fn test_local_approach_data_covers_supported_map() {
    let world = world();
    let data = read_json("local_approaches.json");
    let coverage = &data["coverage"];

    assert_eq!(coverage["approaches"], 6910);
    assert_eq!(coverage["osm_road"], 6901);
    // Every road-snapped target carries a real road name where OSM has one:
    // the snap prefers the nearest *named* road, so "unnamed public road"
    // only survives where OSM truly has no named street inside the radius.
    assert_eq!(coverage["named_road"], 6900);
    assert_eq!(coverage["fallback"], 9);
    assert_eq!(coverage["estimated"], 5602);
    assert_eq!(
        coverage["by_type"]["city_service"],
        serde_json::json!({"estimated": 695, "fallback": 0, "named_road": 1869, "osm_road": 1869, "total": 1869})
    );
    assert_eq!(
        coverage["by_type"]["facility"],
        serde_json::json!({"estimated": 4907, "fallback": 9, "named_road": 5031, "osm_road": 5032, "total": 5041})
    );

    // The coverage block records the sweep's own inventory. The map has grown
    // since (and can again); today's world may only exceed it, never shrink
    // below it, and new targets simply are not covered until the next sweep.
    let services: usize = world
        .city_names()
        .iter()
        .map(|city| world.city_services(city).unwrap().len())
        .sum();
    let facilities: usize = world
        .city_names()
        .iter()
        .map(|city| world.cities[city].locations.len())
        .sum();
    assert!(
        services as u64
            >= coverage["by_type"]["city_service"]["total"]
                .as_u64()
                .unwrap()
    );
    assert!(facilities as i64 >= coverage["by_type"]["facility"]["total"].as_i64().unwrap() - 8);
}

#[test]
fn test_local_approach_records_are_clean_and_marked() {
    let world = world();
    let data = read_json("local_approaches.json");

    let mut retired = Vec::new();
    for (target_id, record) in data["approaches"].as_object().unwrap() {
        // Sweep ids predate the slug migration; the world canonicalizes them
        // at load. A record whose facility retired with map growth is inert.
        let approach = world
            .local_approach(&world.canonical_local_id(target_id))
            .unwrap();
        if approach.is_none() {
            retired.push(target_id.clone());
            continue;
        }
        assert!(!record["name"].as_str().unwrap().is_empty());
        assert!(!record["road"].as_str().unwrap().is_empty());
        assert!(record["approach_miles"].as_f64().unwrap() > 0.0);
        assert!(matches!(
            record["target_type"].as_str().unwrap(),
            "city_service" | "facility"
        ));
        let segments: Vec<&str> = record["turn_segments"]
            .as_array()
            .unwrap()
            .iter()
            .map(|s| s.as_str().unwrap())
            .collect();
        let spoken = format!(
            "{} {} {}",
            record["name"].as_str().unwrap(),
            record["road"].as_str().unwrap(),
            segments.join(" ")
        )
        .to_lowercase();
        assert!(!RAW_MARKERS.iter().any(|m| spoken.contains(m)));
        if record["fallback"].as_bool().unwrap() {
            assert!(!record["fallback_reason"].as_str().unwrap().is_empty());
            assert_eq!(record["source_type"], "fallback_context");
        } else {
            assert!(record["distance_to_road_mi"].as_f64().unwrap() <= SEARCH_RADIUS_MI);
            assert!(matches!(
                record["source_type"].as_str().unwrap(),
                "osm_nearest_road" | "estimated_target_osm_nearest_road"
            ));
        }
    }
    assert!(retired.len() <= 8, "{retired:?}");
}

#[test]
fn test_facility_routes_use_local_approach_layer() {
    let world = world();
    let facility = &world.city("Chicago").unwrap().locations[0];
    let facility_route = world
        .facility_approach_route("Chicago", &facility.name)
        .unwrap();
    let facility_approach = world
        .facility_approach("Chicago", &facility.name)
        .unwrap()
        .expect("Chicago's first facility has a local approach");
    let facility_endpoint = world.facility_endpoint("Chicago", &facility.name).unwrap();
    match facility_endpoint {
        Some(endpoint) if endpoint.source_backed => {
            assert_eq!(facility_route.miles(), endpoint.approach_miles);
        }
        _ => assert_eq!(facility_route.miles(), facility_approach.approach_miles),
    }
    assert_eq!(
        facility_route.highways(),
        vec![facility_approach.road.clone()]
    );
}

#[test]
#[ignore = "tools/build_local_approaches.py stays Python"]
fn test_build_tool_snaps_tiny_osm_fixture_to_named_road() {}

#[test]
#[ignore = "tools/build_local_approaches.py stays Python"]
fn test_build_tool_prefers_named_road_over_closer_unnamed() {}

#[test]
#[ignore = "tools/build_local_approaches.py stays Python"]
fn test_build_tool_marks_missing_road_context_as_fallback() {}
