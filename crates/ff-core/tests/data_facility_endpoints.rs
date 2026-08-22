//! Facility endpoint data (the data-layer half of
//! `tests/test_facility_endpoints.py`; the `tools/build_facility_endpoints.py`
//! cases stay Python).

mod data_support;

use std::collections::HashSet;

use data_support::{read_json, world};

const RAW_MARKERS: &[&str] = &[
    "osm_id",
    "amenity=",
    "highway=",
    "operator=",
    "node/",
    "way/",
    "source_ref",
];

#[test]
fn test_facility_endpoint_data_covers_supported_facilities() {
    let world = world();
    let data = read_json("facility_endpoints.json");
    let coverage = &data["coverage"];

    assert_eq!(coverage["facilities"], 5037);
    assert_eq!(coverage["source_backed"], 3198);
    assert_eq!(coverage["fallback"], 1839);
    assert_eq!(coverage["nearest_road_context"], 0);
    assert_eq!(coverage["turn_level_geometry"], 0);
    assert_eq!(coverage["gate_yard_dock_hints"], 0);

    // The sweep predates the slug migration and the map expansion: its
    // records must keep resolving onto today's facilities (legacy-id
    // translation), while facilities added since the sweep are simply not
    // covered yet. A few records retire when map growth replaces a template
    // facility with a real one (Gulfport/Mobile), never more than a handful.
    let facilities: HashSet<String> = world
        .city_names()
        .iter()
        .flat_map(|city| world.cities[city].locations.iter().map(|l| l.id.clone()))
        .collect();
    let mut resolved: HashSet<String> = HashSet::new();
    let mut missing: Vec<String> = Vec::new();
    for facility_id in data["endpoints"].as_object().unwrap().keys() {
        match world.facility_by_id(facility_id) {
            Ok(location) => {
                resolved.insert(location.id.clone());
            }
            Err(_) => missing.push(facility_id.clone()),
        }
    }
    assert!(resolved.is_subset(&facilities));
    assert!(
        resolved.len() as i64 >= coverage["facilities"].as_i64().unwrap() - 8,
        "{:?}",
        &missing[..missing.len().min(10)]
    );
}

#[test]
fn test_facility_endpoint_records_are_clean_and_honest() {
    let world = world();
    let data = read_json("facility_endpoints.json");

    for (facility_id, record) in data["endpoints"].as_object().unwrap() {
        if world.facility_by_id(facility_id).is_err() {
            continue; // facility retired by map growth; record is inert
        }
        let endpoint = world
            .facility_endpoint(record["city"].as_str().unwrap(), facility_id)
            .unwrap();
        assert!(endpoint.is_some());
        let spoken = format!(
            "{} {} {}",
            record["facility_name"].as_str().unwrap(),
            record["endpoint_name"].as_str().unwrap(),
            record["approach_road"].as_str().unwrap()
        )
        .to_lowercase();
        assert!(!RAW_MARKERS.iter().any(|m| spoken.contains(m)));
        assert!(!record["source_note"].as_str().unwrap().is_empty());
        assert!(!record["gate_hint"].as_bool().unwrap());
        assert!(!record["yard_hint"].as_bool().unwrap());
        assert!(!record["dock_hint"].as_bool().unwrap());
        assert!(!record["turn_level_geometry"].as_bool().unwrap());
        if record["source_backed"].as_bool().unwrap() {
            assert!(!record["fallback"].as_bool().unwrap());
            assert_eq!(record["source_type"], "osm_facility_endpoint");
            assert!(record["approach_miles"].as_f64().unwrap() > 0.0);
            assert_eq!(record["approach_road"], "local facility access road");
            assert!(record["source_note"]
                .as_str()
                .unwrap()
                .contains("not claimed by this layer"));
        } else {
            assert!(record["fallback"].as_bool().unwrap());
            assert!(!record["fallback_reason"].as_str().unwrap().is_empty());
            assert_eq!(record["source_type"], "representative_fallback");
            assert_eq!(record["approach_miles"].as_f64().unwrap(), 0.0);
        }
    }
}

#[test]
fn test_facility_route_prefers_source_backed_endpoint_when_available() {
    let world = world();
    let facility = world
        .facility_by_id("abilene:chemical_petroleum_terminal:abilene-energy-terminal")
        .unwrap();
    let endpoint = world
        .facility_endpoint("Abilene", &facility.id)
        .unwrap()
        .expect("the Abilene energy terminal has an endpoint");
    let route = world
        .facility_approach_route("Abilene", &facility.name)
        .unwrap();

    assert!(endpoint.source_backed);
    assert!((route.miles() - endpoint.approach_miles).abs() < 1e-9);
    let approach = world
        .facility_approach("Abilene", &facility.name)
        .unwrap()
        .unwrap();
    assert_eq!(route.highways(), vec![approach.road.clone()]);
}

#[test]
fn test_facility_route_falls_back_to_local_approach_for_representative_endpoint() {
    let world = world();
    let facility = world
        .facility_by_id("abilene:grocery_retail_dc:abilene-grocery-distribution-center")
        .unwrap();
    let endpoint = world
        .facility_endpoint("Abilene", &facility.id)
        .unwrap()
        .expect("the Abilene grocery DC has an endpoint");
    let approach = world
        .facility_approach("Abilene", &facility.name)
        .unwrap()
        .expect("the Abilene grocery DC has a local approach");
    let route = world
        .facility_approach_route("Abilene", &facility.name)
        .unwrap();

    assert!(endpoint.fallback);
    assert!((route.miles() - approach.approach_miles).abs() < 1e-9);
    assert_eq!(route.highways(), vec![approach.road.clone()]);
}

#[test]
#[ignore = "tools/build_facility_endpoints.py stays Python (needs osmium)"]
fn test_build_tool_classifies_tiny_osm_fixture() {}

#[test]
#[ignore = "tools/build_facility_endpoints.py stays Python (needs osmium)"]
fn test_build_tool_marks_missing_extracts_as_fallback() {}
