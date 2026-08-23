//! The baked facility-approach layer: coverage, honest records, and the
//! fallback that survives where no source geometry exists (the data half of
//! `tests/test_facility_approaches.py`).
//!
//! `test_build_tool_routes_tiny_facility_fixture` covers
//! `tools/build_facility_approaches.py`, which stays Python by design, and
//! `test_facility_route_prefers_turn_level_source_approach` needs the driving
//! layer's earcon map -- it lives in
//! `crates/freight-fate/tests/states_driving_facility_approaches.rs`.

mod data_support;

use std::collections::HashSet;

use data_support::{read_json, world};

const RAW_MARKERS: [&str; 7] = [
    "osm_id",
    "amenity=",
    "highway=",
    "operator=",
    "node/",
    "way/",
    "source_ref",
];

#[test]
fn test_facility_approach_data_covers_full_facility_set() {
    let w = world();
    let data = read_json("facility_approaches.json");
    let coverage = &data["coverage"];

    assert_eq!(coverage["facilities"], 5037);
    assert_eq!(coverage["source_backed_endpoints"], 3198);
    assert_eq!(coverage["road_snapped"], 1579);
    assert_eq!(coverage["turn_level"], 1415);
    assert_eq!(coverage["nearest_road_fallback"], 1619);
    assert_eq!(coverage["representative_fallback"], 1839);
    assert_eq!(coverage["gate_yard_dock_hints"], 0);

    // The 2026-07-14 regen keys records by current slug facility ids and
    // covers every facility the endpoint/local-approach sweeps know about;
    // facilities added by map growth since those sweeps are simply absent
    // until the next data expansion pass (see ROADMAP).
    let facilities: HashSet<String> = w
        .city_names()
        .iter()
        .flat_map(|city| w.cities[city].locations.iter().map(|l| l.id.clone()))
        .collect();
    let mut resolved: HashSet<String> = HashSet::new();
    let mut missing: Vec<String> = Vec::new();
    for facility_id in data["approaches"].as_object().expect("approaches").keys() {
        match w.facility_by_id(facility_id) {
            Ok(location) => {
                resolved.insert(location.id.clone());
            }
            Err(_) => missing.push(facility_id.clone()),
        }
    }
    assert!(resolved.is_subset(&facilities));
    assert!(
        missing.is_empty(),
        "{:?}",
        &missing[..missing.len().min(10)]
    );
    assert_eq!(
        resolved.len() as u64,
        coverage["facilities"].as_u64().unwrap()
    );
}

#[test]
fn test_facility_approach_records_are_clean_and_honest() {
    let w = world();
    let data = read_json("facility_approaches.json");

    for (facility_id, record) in data["approaches"].as_object().expect("approaches") {
        if w.facility_by_id(facility_id).is_err() {
            continue; // facility retired by map growth; record is inert
        }
        let city = record["city"].as_str().expect("city");
        let approach = w
            .facility_source_approach(city, facility_id)
            .expect("source approach lookup");
        assert!(approach.is_some(), "{facility_id}");

        let mut parts: Vec<String> = vec![
            record["facility_name"].as_str().unwrap_or("").to_string(),
            record["endpoint_name"].as_str().unwrap_or("").to_string(),
            record["approach_road"].as_str().unwrap_or("").to_string(),
        ];
        let segments = record["segments"].as_array().expect("segments");
        parts.extend(
            segments
                .iter()
                .map(|s| s["road"].as_str().unwrap_or("").to_string()),
        );
        parts.extend(
            segments
                .iter()
                .map(|s| s["cue"].as_str().unwrap_or("").to_string()),
        );
        let spoken = parts.join(" ").to_lowercase();
        assert!(
            !RAW_MARKERS.iter().any(|marker| spoken.contains(marker)),
            "{facility_id}: {spoken}"
        );
        assert!(
            !record["gate_hint"].as_bool().unwrap_or(false),
            "{facility_id}"
        );
        assert!(
            !record["yard_hint"].as_bool().unwrap_or(false),
            "{facility_id}"
        );
        assert!(
            !record["dock_hint"].as_bool().unwrap_or(false),
            "{facility_id}"
        );

        if record["turn_level"].as_bool().unwrap_or(false) {
            assert!(
                record["road_snapped"].as_bool().unwrap_or(false),
                "{facility_id}"
            );
            assert!(
                record["nearest_road_context"].as_bool().unwrap_or(false),
                "{facility_id}"
            );
            assert_eq!(
                record["source_type"], "osm_local_road_graph",
                "{facility_id}"
            );
            assert!(
                !record["fallback"].as_bool().unwrap_or(true),
                "{facility_id}"
            );
            assert!(
                record["total_miles"].as_f64().unwrap_or(0.0) > 0.0,
                "{facility_id}"
            );
            assert!(!segments.is_empty(), "{facility_id}");
        } else {
            assert!(
                record["fallback"].as_bool().unwrap_or(false),
                "{facility_id}"
            );
            assert!(
                !record["fallback_reason"].as_str().unwrap_or("").is_empty(),
                "{facility_id}"
            );
            assert_eq!(
                record["source_type"], "facility_approach_fallback",
                "{facility_id}"
            );
        }
    }
}

#[test]
fn test_facility_route_keeps_existing_fallback_when_no_source_geometry() {
    let w = world();
    let facility = w
        .facility_by_id("abilene:grocery_retail_dc:abilene-grocery-distribution-center")
        .expect("the Abilene grocery DC is on the map");
    let name = facility.name.clone();
    let source_approach = w
        .facility_source_approach("Abilene", &name)
        .expect("source approach lookup");
    let fallback_approach = w
        .facility_approach("Abilene", &name)
        .expect("local approach lookup");
    let route = w
        .facility_approach_route("Abilene", &name)
        .expect("approach route");

    let source_approach = source_approach.expect("a source approach record");
    assert!(source_approach.fallback);
    let fallback_approach = fallback_approach.expect("a local approach record");
    assert!((route.miles() - fallback_approach.approach_miles).abs() < 1e-9);
    assert_eq!(route.highways(), vec![fallback_approach.road.clone()]);
}
