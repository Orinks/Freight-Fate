//! Facility endpoint data (the data-layer half of
//! `tests/test_facility_endpoints.py`; the `tools/build_facility_endpoints.py`
//! cases stay Python).

use std::collections::HashSet;

use crate::data_support::{read_json, world};

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

    assert_eq!(coverage["facilities"], 4271);
    // After far-pin regeocode: 357 OSM rematches stayed source-backed; 419
    // unresolvable pins became estimated-near-city fallbacks (2779/2258).
    // The 2026-09-17 re-sweep with the matcher that reads an object's own
    // tags then filled 155 fallbacks (2934/2103) and replaced 1,224 endpoints
    // that were railway lines, substations and shops. What the screen says of
    // every sourced row is in the row: 1,939 are freight sites, 995 still are
    // not (nothing better within 6.4 miles), and 175 of the sites state no
    // trade, so the match to this facility's trade is assumed and says so.
    // The 2026-09-20 sweep added the four families that had no matcher rule
    // at all -- grain elevators, quarries, construction materials yards,
    // lumber and paper. All 419 of their rows were fallbacks; 129 now have a
    // sourced endpoint and every one of those passes the screen, which is the
    // whole of the +129 source_backed.
    // `passed` rose by only 110 because 19 rows correctly STOPPED passing: a
    // lumber mill, a quarry and a grain company had been standing in as
    // assumed cross-docks and company yards, and now that the matcher knows
    // what they are they no longer answer for a trade they do not state.
    // Four of the 19 are the same object re-homed to the right facility in
    // its own town (Columbia Forest Products to Klamath Falls lumber and
    // paper; Scoular Grain Co to the Salina grain elevator).
    assert_eq!(coverage["source_backed"], 2874);
    assert_eq!(coverage["fallback"], 1397);
    assert_eq!(coverage["screen"]["passed"], 2049);
    // Retiring 766 generated facilities from the 137 stand-in markets took only
    // refused and fallback rows with it: `passed` did not move, which is the
    // point -- not one of those towns had a surveyed endpoint to lose.
    assert_eq!(coverage["screen"]["refused"], 825);
    assert_eq!(coverage["screen"]["not_screened"], 0);
    assert_eq!(coverage["screen"]["trade_assumed"], 173);
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
            // The screen verdict rides in the row, so a railway line that
            // found no replacement is never mistaken for a yard gate.
            let verdict = record["endpoint_screen"].as_str().unwrap();
            assert!(verdict == "passed" || verdict == "refused");
            if verdict == "refused" {
                assert!(!record["endpoint_screen_reason"]
                    .as_str()
                    .unwrap()
                    .is_empty());
            }
            if let Some(kind) = record.get("match_kind") {
                assert!(kind == "read" || kind == "assumed");
            }
            assert!(record["approach_miles"].as_f64().unwrap() <= 8.0);
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
            let estimated = record
                .get("estimated")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            if estimated {
                // Estimated-near-city pins keep a real offset; they must not
                // claim source-backed OSM at zero miles.
                assert!(record["approach_miles"].as_f64().unwrap() > 0.0);
                assert!(record["source_note"]
                    .as_str()
                    .unwrap()
                    .contains("Estimated-near-city"));
                assert!(record["fallback_reason"]
                    .as_str()
                    .unwrap()
                    .to_lowercase()
                    .contains("estimated near city"));
            } else {
                assert_eq!(record["approach_miles"].as_f64().unwrap(), 0.0);
            }
        }
    }
}

#[test]
fn test_facility_route_prefers_source_backed_endpoint_when_available() {
    let world = world();
    // A sourced endpoint with NO street chain (it sits a few blocks from the
    // city anchor, under the chain floor). The Abilene energy terminal this
    // used to pin gained a chain in the 2026-09-17 re-sweep.
    let facility = world
        .facility_by_id("muncie-in-us:cross_dock:muncie-cross-dock")
        .unwrap();
    let endpoint = world
        .facility_endpoint("muncie_in_us", &facility.id)
        .unwrap()
        .expect("the Muncie cross-dock has an endpoint");
    let route = world
        .facility_approach_route("muncie_in_us", &facility.name)
        .unwrap();

    assert!(endpoint.source_backed);
    assert!((route.miles() - endpoint.approach_miles).abs() < 1e-9);
    let approach = world
        .facility_approach("muncie_in_us", &facility.name)
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
