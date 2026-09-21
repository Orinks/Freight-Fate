use super::*;
use serde_json::json;

fn map(value: Value) -> Map<String, Value> {
    value.as_object().unwrap().clone()
}

// --- TrafficEvent (test_real_traffic.py / test_real_construction_zones.py)

#[test]
fn test_traffic_event_serialization() {
    let event = TrafficEvent {
        latitude: Some(39.96),
        longitude: Some(-82.99),
        lanes_affected: Some("2 right lanes".into()),
        ..TrafficEvent::new(
            "test-123",
            "incident",
            "high",
            "Accident on I-70",
            "Franklin",
        )
    };
    let data = event.to_dict();
    assert_eq!(data["id"], "test-123");
    assert_eq!(data["event_type"], "incident");
    assert_eq!(data["severity"], "high");
    assert_eq!(data["description"], "Accident on I-70");

    let restored = TrafficEvent::from_dict(&data).unwrap();
    assert_eq!(restored.id, "test-123");
    assert_eq!(restored.event_type, "incident");
    assert_eq!(restored.latitude, Some(39.96));
}

#[test]
fn test_traffic_event_from_invalid_dict() {
    assert!(TrafficEvent::from_dict(&json!({})).is_none());
    assert!(TrafficEvent::from_dict(&Value::Null).is_none());
    assert!(TrafficEvent::from_dict(&json!([])).is_none());
    // With ID but missing other fields, should still create event with defaults
    let event = TrafficEvent::from_dict(&json!({"id": "test-123"})).unwrap();
    assert_eq!(event.id, "test-123");
    assert_eq!(event.event_type, "incident"); // Default
}

#[test]
fn test_construction_fields_default() {
    let event = TrafficEvent::new(
        "test-1",
        "construction",
        "medium",
        "Road work near milepost 45",
        "Franklin",
    );
    assert_eq!(event.road_name, "");
    assert_eq!(event.location_text, "");
    assert_eq!(event.work_type, "");
    assert_eq!(event.closure, "");
}

#[test]
fn test_construction_fields_set() {
    let event = TrafficEvent {
        road_name: "I-71".into(),
        location_text: "Between milepost 45 and 47".into(),
        work_type: "paving".into(),
        closure: "single lane".into(),
        ..TrafficEvent::new(
            "test-1",
            "construction",
            "medium",
            "Paving between exits 43 and 47",
            "Franklin",
        )
    };
    assert_eq!(event.road_name, "I-71");
    assert_eq!(event.location_text, "Between milepost 45 and 47");
    assert_eq!(event.work_type, "paving");
    assert_eq!(event.closure, "single lane");
}

#[test]
fn test_construction_event_to_dict() {
    let event = TrafficEvent {
        latitude: Some(39.8),
        longitude: Some(-83.0),
        road_name: "I-71".into(),
        location_text: "Between milepost 45 and 47".into(),
        work_type: "paving".into(),
        closure: "single lane".into(),
        ..TrafficEvent::new(
            "test-1",
            "construction",
            "medium",
            "Paving between exits",
            "Franklin",
        )
    };
    let d = event.to_dict();
    let restored = TrafficEvent::from_dict(&d).unwrap();
    assert_eq!(restored.road_name, "I-71");
    assert_eq!(restored.location_text, "Between milepost 45 and 47");
    assert_eq!(restored.work_type, "paving");
    assert_eq!(restored.closure, "single lane");
}

#[test]
fn test_severity_mapping() {
    assert_eq!(map_severity("low"), "low");
    assert_eq!(map_severity("minor"), "low");
    assert_eq!(map_severity("medium"), "medium");
    assert_eq!(map_severity("moderate"), "medium");
    assert_eq!(map_severity("high"), "high");
    assert_eq!(map_severity("major"), "high");
    assert_eq!(map_severity("severe"), "high");
    assert_eq!(map_severity("critical"), "high");
    assert_eq!(map_severity("unknown"), "low"); // Default
}

// --- TestRealTrafficProviderConstruction (parser half)

#[test]
fn test_parse_construction_ohgo_format() {
    let sample_data = json!({
        "construction": [
            {
                "id": "cz-1",
                "road": "I-71",
                "description": "Paving operations between MM 45 and MM 47",
                "county": "Franklin",
                "lat": 39.83,
                "lon": -83.01,
                "start_date": "2026-07-15",
                "end_date": "2026-08-15",
                "lanes_affected": "left lane closed",
                "closure_type": "single lane",
            }
        ]
    });
    let events = parse_construction_events(&sample_data, "ohio");
    assert_eq!(events.len(), 1);
    let event = &events[0];
    assert_eq!(event.event_type, "construction");
    assert_eq!(event.road_name, "I-71");
    assert_eq!(event.closure, "single lane");
    assert_eq!(event.latitude, Some(39.83));
    assert_eq!(event.longitude, Some(-83.01));
    assert_eq!(event.lanes_affected.as_deref(), Some("left lane closed"));
    assert_eq!(event.work_type, "paving");
    assert_eq!(event.severity, "medium");
}

#[test]
fn test_parse_construction_empty_response() {
    assert!(parse_construction_events(&json!({}), "ohio").is_empty());
    assert!(parse_construction_events(&json!({"incidents": []}), "ohio").is_empty());
}

#[test]
fn test_classify_work_type_from_description() {
    assert_eq!(
        classify_work_type(&map(json!({"description": "Bridge deck repair"}))),
        "bridge"
    );
    assert_eq!(
        classify_work_type(&map(json!({"description": "Paving I-71"}))),
        "paving"
    );
    assert_eq!(
        classify_work_type(&map(json!({"description": "Utility work"}))),
        "utility"
    );
    assert_eq!(
        classify_work_type(&map(json!({"description": "Road construction"}))),
        "construction"
    );
}

#[test]
fn test_construction_severity_mapping() {
    assert_eq!(construction_severity("full closure"), "high");
    assert_eq!(construction_severity("single lane"), "medium");
    assert_eq!(construction_severity("shoulder"), "low");
}

// --- TestIterisParser

#[test]
fn test_parse_iteris_events_basic() {
    let sample = json!([
        {
            "id": "evt-1",
            "event_type": "ACCIDENT",
            "severity": "moderate",
            "headline": "Crash on I-94 near Milwaukee",
            "road_name": "I-94",
            "lat": 43.0,
            "lon": -88.0,
            "county": "Milwaukee",
            "start_date": "2026-07-18T08:00:00",
        },
        {
            "id": "evt-2",
            "event_type": "CONSTRUCTION",
            "severity": "minor",
            "headline": "Road work on I-43 near Green Bay",
            "lat": 44.5,
            "lon": -88.0,
            "county": "Brown",
        },
    ]);
    let events = parse_iteris_events(&sample, "wisconsin");
    assert_eq!(events.len(), 2);
    // First event is an incident
    assert_eq!(events[0].event_type, "incident");
    assert_eq!(events[0].road_name, "I-94");
    assert_eq!(events[0].severity, "medium"); // moderate -> medium
    assert_eq!(events[0].latitude, Some(43.0));
    assert_eq!(events[0].county, "Milwaukee");
    // Second event is construction
    assert_eq!(events[1].event_type, "construction");
    assert_eq!(events[1].road_name, ""); // No road_name in the item
}

#[test]
fn test_parse_iteris_events_construction_only() {
    let sample = json!([
        {
            "id": "c1",
            "event_type": "CONSTRUCTION",
            "headline": "Road work on I-39",
            "lat": 44.0,
            "lon": -89.0,
        },
        {"id": "i1", "event_type": "ACCIDENT", "headline": "Crash", "lat": 43.5, "lon": -88.5},
        {
            "id": "c2",
            "event_type": "ROADWORK",
            "headline": "Paving I-94",
            "lat": 43.2,
            "lon": -87.9,
        },
    ]);
    let events = parse_iteris_construction_events(&sample, "wisconsin");
    assert_eq!(events.len(), 2); // c1 and c2 (construction + roadwork)
    let ids: Vec<&str> = events.iter().map(|e| e.id.as_str()).collect();
    assert!(ids.contains(&"c1"));
    assert!(ids.contains(&"c2"));
    // Enriched through the shared helpers (which read `description`, not
    // the Iteris `headline`, so the work type stays the default)
    assert_eq!(events[1].work_type, "construction");
    assert_eq!(events[0].closure, "single lane");
    assert_eq!(
        events[0].lanes_affected.as_deref(),
        Some("left lane closed")
    );
}

#[test]
fn test_parse_iteris_events_empty() {
    assert!(parse_iteris_events(&json!([]), "wisconsin").is_empty());
    assert!(parse_iteris_events(&json!({}), "wisconsin").is_empty());
}

#[test]
fn test_parse_iteris_coordinates_direct() {
    let (lat, lon) = parse_iteris_coordinates(&map(json!({"lat": 43.0, "lon": -88.0})));
    assert_eq!(lat, Some(43.0));
    assert_eq!(lon, Some(-88.0));
}

#[test]
fn test_parse_iteris_coordinates_sub_object() {
    let (lat, lon) =
        parse_iteris_coordinates(&map(json!({"location": {"lat": 43.0, "lon": -88.0}})));
    assert_eq!(lat, Some(43.0));
    assert_eq!(lon, Some(-88.0));
}

#[test]
fn test_parse_iteris_coordinates_missing() {
    let (lat, lon) = parse_iteris_coordinates(&map(json!({})));
    assert_eq!(lat, None);
    assert_eq!(lon, None);
}

#[test]
fn test_build_iteris_location_text_direct() {
    let text = build_iteris_location_text(&map(json!({
        "location_text": "Between milepost 45 and 47",
    })));
    assert_eq!(text, "Between milepost 45 and 47");
}

#[test]
fn test_build_iteris_location_text_milepost() {
    let text = build_iteris_location_text(&map(json!({
        "start_milepost": "45",
        "end_milepost": "47",
    })));
    assert!(text.contains("milepost 45") && text.contains("47"));
}

#[test]
fn test_build_iteris_location_text_cross_street() {
    let text = build_iteris_location_text(&map(json!({"cross_street": "Main St"})));
    assert_eq!(text, "At Main St");
}

#[test]
fn test_build_iteris_location_text_empty() {
    assert_eq!(build_iteris_location_text(&map(json!({}))), "");
    assert_eq!(
        build_iteris_location_text(&map(json!({"cross_street": ""}))),
        ""
    );
}

#[test]
fn test_determine_iteris_closure_direct() {
    let result = determine_iteris_closure(&map(json!({"closure": "full closure"})), "");
    assert_eq!(result, "full closure");
}

#[test]
fn test_determine_iteris_closure_from_description() {
    let empty = map(json!({}));
    assert_eq!(
        determine_iteris_closure(&empty, "road closed for construction"),
        "full closure"
    );
    assert_eq!(
        determine_iteris_closure(&empty, "alternating one-way traffic"),
        "alternating"
    );
    assert_eq!(
        determine_iteris_closure(&empty, "right shoulder closed"),
        "shoulder"
    );
    assert_eq!(
        determine_iteris_closure(&empty, "left lane closed"),
        "single lane"
    );
}

// --- TestWZDxParser

#[test]
fn test_parse_wzdx_feature_collection() {
    let sample = json!({
        "type": "FeatureCollection",
        "features": [
            {
                "id": "wz-1",
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-122.0, 45.0]},
                "properties": {
                    "wzdx:roadName": "I-5",
                    "wzdx:workZoneName": "Bridge repair near Portland",
                    "wzdx:workZoneType": "construction",
                    "wzdx:vehicleImpact": "some-lanes-closed",
                    "wzdx:startDate": "2026-07-15",
                    "wzdx:endDate": "2026-08-15",
                    "wzdx:county": "Multnomah",
                },
            }
        ],
    });
    let events = parse_wzdx_events(&sample, "oregon");
    assert_eq!(events.len(), 1);
    let event = &events[0];
    assert_eq!(event.event_type, "construction");
    assert_eq!(event.road_name, "I-5");
    assert_eq!(event.closure, "single lane");
    assert_eq!(event.latitude, Some(45.0));
    assert_eq!(event.longitude, Some(-122.0));
    assert_eq!(event.county, "Multnomah");
    assert_eq!(event.description, "Bridge repair near Portland");
    assert_eq!(event.lanes_affected.as_deref(), Some("left lane closed"));
}

#[test]
fn test_parse_wzdx_no_namespace() {
    let sample = json!({
        "features": [
            {
                "id": "wz-2",
                "geometry": {"type": "Point", "coordinates": [-90.0, 35.0]},
                "properties": {
                    "roadName": "I-40",
                    "workZoneType": "maintenance",
                    "vehicleImpact": "shoulder-closed",
                    "county": "Shelby",
                },
            }
        ],
    });
    let events = parse_wzdx_events(&sample, "tennessee");
    assert_eq!(events.len(), 1);
    assert_eq!(events[0].road_name, "I-40");
    assert_eq!(events[0].closure, "shoulder");
}

#[test]
fn test_parse_wzdx_line_string_geometry() {
    let sample = json!({
        "features": [
            {
                "id": "wz-3",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-122.1, 45.0],
                        [-122.0, 45.1],
                        [-121.9, 45.2],  // midpoint
                    ],
                },
                "properties": {
                    "wzdx:roadName": "I-84",
                    "wzdx:workZoneType": "construction",
                    "wzdx:vehicleImpact": "all-lanes-closed",
                },
            }
        ],
    });
    let events = parse_wzdx_events(&sample, "oregon");
    assert_eq!(events.len(), 1);
    // Midpoint: [-122.0, 45.1] -> lat=45.1, lon=-122.0
    assert_eq!(events[0].latitude, Some(45.1));
    assert_eq!(events[0].longitude, Some(-122.0));
    assert_eq!(events[0].closure, "full closure");
}

#[test]
fn test_parse_wzdx_construction_filter() {
    let sample = json!({
        "features": [
            {
                "id": "wz-1",
                "geometry": {"type": "Point", "coordinates": [-80.0, 40.0]},
                "properties": {
                    "wzdx:roadName": "I-79",
                    "wzdx:workZoneType": "construction",
                    "wzdx:vehicleImpact": "some-lanes-closed",
                },
            },
            {
                "id": "inc-1",
                "geometry": {"type": "Point", "coordinates": [-80.0, 40.5]},
                "properties": {
                    "wzdx:roadName": "I-79",
                    "wzdx:workZoneType": "accident",
                    "wzdx:vehicleImpact": "flow-of-traffic",
                },
            },
        ],
    });
    let events = parse_wzdx_construction_events(&sample, "pennsylvania");
    assert_eq!(events.len(), 1);
    assert_eq!(events[0].id, "wz-1");
}

#[test]
fn test_wzdx_empty_data() {
    assert!(parse_wzdx_events(&json!({}), "oregon").is_empty());
    assert!(parse_wzdx_events(&json!({"features": []}), "oregon").is_empty());
    assert!(parse_wzdx_events(&json!([]), "oregon").is_empty());
}

#[test]
fn test_wzdx_missing_coordinates() {
    let sample = json!({
        "features": [
            {
                "id": "wz-nogeo",
                "geometry": null,
                "properties": {
                    "wzdx:roadName": "US-101",
                    "wzdx:workZoneType": "construction",
                },
            }
        ],
    });
    let events = parse_wzdx_events(&sample, "california");
    assert_eq!(events.len(), 1);
    assert_eq!(events[0].latitude, None);
}

#[test]
fn test_wzdx_impact_mapping() {
    assert_eq!(wzdx_impact_to_closure("all-lanes-closed"), "full closure");
    assert_eq!(wzdx_impact_to_closure("some-lanes-closed"), "single lane");
    assert_eq!(wzdx_impact_to_closure("shoulder-closed"), "shoulder");
    assert_eq!(wzdx_impact_to_closure("alternating-one-way"), "alternating");
    assert_eq!(wzdx_impact_to_closure(""), "single lane");
}

#[test]
fn test_build_wzdx_location_text() {
    assert_eq!(
        build_wzdx_location_text(&map(json!({
            "wzdx:locationDescription": "Between exits 45 and 47",
        }))),
        "Between exits 45 and 47"
    );
    assert_eq!(
        build_wzdx_location_text(&map(json!({
            "wzdx:beginningMilepost": "45",
            "wzdx:endingMilepost": "47",
        }))),
        "Between milepost 45 and 47"
    );
    assert_eq!(build_wzdx_location_text(&map(json!({}))), "");
}

// --- TestWZDxV4Parser
//
// The fixture is a real feature recorded 2026-08-09 from
// https://511wi.gov/api/wzdx (v4.2), trimmed to what the parser reads.

fn wi_feature() -> Value {
    json!({
        "id": "ca261ca8-7974-6058-ab4d-25b80def22e6",
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [-87.938228, 43.381435],
                [-87.93815776899706, 43.381493952295386],
                [-87.93795762587283, 43.381571379674995],
            ],
        },
        "properties": {
            "core_details": {
                "event_type": "work-zone",
                "data_source_id": "ATMS-ExtEvent",
                "road_names": ["WIS 33 EB"],
                "direction": "eastbound",
                "name": "WisLCS-273413-1",
                "description": "Mainline Right Lane Closed on WIS 33 EB from MILWAUKEE RIVER OVERFLOW (BRIDGE CROSSING) to WIS 33 WB (END DIVIDED)",
            },
            "start_date": "2026-06-15T11:00:00+00:00",
            "end_date": "2026-09-03T04:59:59+00:00",
            "vehicle_impact": "some-lanes-closed",
            "lanes": [
                {"order": 1, "type": "shoulder", "status": "open"},
                {"order": 2, "type": "general", "status": "open"},
                {"order": 3, "type": "general", "status": "closed"},
                {"order": 4, "type": "shoulder", "status": "closed"},
            ],
            "beginning_cross_street": "MILWAUKEE RIVER OVERFLOW (BRIDGE CROSSING)",
            "ending_cross_street": "WIS 33 WB (END DIVIDED)",
        },
    })
}

#[test]
fn test_parse_v4_work_zone() {
    let sample = json!({"type": "FeatureCollection", "features": [wi_feature()]});
    let events = parse_wzdx_events(&sample, "wisconsin");
    assert_eq!(events.len(), 1);
    let event = &events[0];
    assert_eq!(event.id, "ca261ca8-7974-6058-ab4d-25b80def22e6");
    assert_eq!(event.event_type, "construction");
    assert_eq!(event.road_name, "WIS 33 EB");
    assert!(event
        .description
        .starts_with("Mainline Right Lane Closed on WIS 33 EB"));
    assert_eq!(event.closure, "single lane");
    assert_eq!(event.severity, "medium");
    assert_eq!(
        event.start_time.as_deref(),
        Some("2026-06-15T11:00:00+00:00")
    );
    assert_eq!(
        event.estimated_end.as_deref(),
        Some("2026-09-03T04:59:59+00:00")
    );
    // LineString midpoint
    assert_eq!(event.latitude, Some(43.381493952295386));
    assert_eq!(event.longitude, Some(-87.93815776899706));
}

#[test]
fn test_v4_lane_description_counts_general_lanes() {
    let events = parse_wzdx_events(&json!({"features": [wi_feature()]}), "wisconsin");
    assert_eq!(
        events[0].lanes_affected.as_deref(),
        Some("1 of 2 lanes closed")
    );
}

#[test]
fn test_v4_shoulder_only_closure() {
    let feature = json!({
        "id": "wz-shoulder",
        "geometry": {"type": "Point", "coordinates": [-88.0, 43.0]},
        "properties": {
            "core_details": {"event_type": "work-zone", "road_names": ["I-94"]},
            "vehicle_impact": "shoulder-closed",
            "lanes": [
                {"order": 1, "type": "shoulder", "status": "closed"},
                {"order": 2, "type": "general", "status": "open"},
            ],
        },
    });
    let events = parse_wzdx_events(&json!({"features": [feature]}), "wisconsin");
    assert_eq!(events[0].lanes_affected.as_deref(), Some("shoulder closed"));
    assert_eq!(events[0].closure, "shoulder");
    assert_eq!(events[0].severity, "low");
}

#[test]
fn test_v4_cross_street_location_text() {
    let events = parse_wzdx_events(&json!({"features": [wi_feature()]}), "wisconsin");
    assert_eq!(
        events[0].location_text,
        "Between MILWAUKEE RIVER OVERFLOW (BRIDGE CROSSING) and WIS 33 WB (END DIVIDED)"
    );
}

#[test]
fn test_v4_construction_filter_keeps_work_zones() {
    let events = parse_wzdx_construction_events(&json!({"features": [wi_feature()]}), "wisconsin");
    assert_eq!(events.len(), 1);
}

#[test]
fn test_v4_multipoint_geometry() {
    // Trimmed from a real feature recorded 2026-08-09 from
    // https://511ny.org/api/wzdx.
    let feature = json!({
        "id": "ny-1",
        "geometry": {"type": "MultiPoint", "coordinates": [[-73.797869, 41.019265]]},
        "properties": {
            "core_details": {"event_type": "work-zone", "road_names": ["NY 100"]},
            "vehicle_impact": "some-lanes-closed",
        },
    });
    let events = parse_wzdx_events(&json!({"features": [feature]}), "new york");
    assert_eq!(events[0].latitude, Some(41.019265));
    assert_eq!(events[0].longitude, Some(-73.797869));
}

// --- TestCarsParser
//
// Fixtures are real map features recorded 2026-08-09 from
// https://511in.org/api/graphql and https://511mn.org/api/graphql,
// trimmed to what the parser reads.

fn in_lane_closed() -> Value {
    json!({
        "bbox": [-86.84936, 41.68731, -86.84715, 41.68742],
        "title": "US 20 (Mile Point 42.5 - 42.61): Lane closed.",
        "tooltip": "US 20: Lane closed.",
        "uri": "event/CARSy-30",
        "features": [
            {
                "id": "CARSy-30-1184291760",
                "geometry": {"type": "Point", "coordinates": [-86.84825, 41.68732]},
                "properties": {},
            }
        ],
        "priority": 5,
        "__typename": "Event",
    })
}

fn in_road_closed() -> Value {
    json!({
        "bbox": [-86.1268, 38.08214, -85.82829, 38.30399],
        "title": "IN 11 (Mile Point 12.4 - 12.34): Road closed.",
        "tooltip": "IN 11: Road closed, see map for detour(s).",
        "uri": "event/CARSy-34",
        "features": [
            {
                "id": "CARSy-34-2192814423",
                "geometry": {"type": "Point", "coordinates": [-86.03935, 38.08253]},
                "properties": {},
            }
        ],
        "priority": 2,
        "__typename": "Event",
    })
}

fn mn_crash() -> Value {
    json!({
        "bbox": [-93.03416, 45.21468, -93.03416, 45.21468],
        "title": "I-35W southbound: Crash.",
        "tooltip": "I-35W southbound: Crash.",
        "uri": "event/MSPCAD-129052",
        "features": [
            {
                "id": "MSPCAD-129052-2307205820",
                "geometry": {"type": "Point", "coordinates": [-93.03416, 45.21468]},
                "properties": {},
            }
        ],
        "priority": 5,
        "__typename": "Event",
    })
}

fn mn_future() -> Value {
    json!({
        "bbox": [-92.48837, 43.88284, -92.23476, 43.97919],
        "title": "STARTS FRIDAY. I-90 eastbound: Bridge construction.",
        "tooltip": "STARTS FRIDAY. I-90 eastbound: Bridge construction.",
        "uri": "event/CARSx-128079",
        "features": [
            {
                "id": "CARSx-128079-132200140",
                "geometry": {"type": "Point", "coordinates": [-92.35459, 43.95132]},
                "properties": {},
            }
        ],
        "priority": 5,
        "__typename": "Event",
    })
}

fn response(features: Vec<Value>) -> Value {
    json!({"data": {"mapFeaturesQuery": {"mapFeatures": features, "error": null}}})
}

#[test]
fn test_parse_cars_construction() {
    let events = parse_cars_events(&response(vec![in_lane_closed()]), "indiana", true);
    assert_eq!(events.len(), 1);
    let event = &events[0];
    assert_eq!(event.id, "CARSy-30");
    assert_eq!(event.event_type, "construction");
    assert_eq!(event.road_name, "US 20");
    assert_eq!(event.location_text, "Mile Point 42.5 - 42.61");
    assert_eq!(
        event.description,
        "US 20 (Mile Point 42.5 - 42.61): Lane closed."
    );
    assert_eq!(event.latitude, Some(41.68732));
    assert_eq!(event.longitude, Some(-86.84825));
}

#[test]
fn test_parse_cars_road_closure_is_high_severity() {
    let events = parse_cars_events(&response(vec![in_road_closed()]), "indiana", true);
    assert_eq!(events[0].closure, "full closure");
    assert_eq!(events[0].severity, "high");
    assert_eq!(
        events[0].lanes_affected.as_deref(),
        Some("all lanes closed")
    );
}

#[test]
fn test_parse_cars_incident() {
    let events = parse_cars_events(&response(vec![mn_crash()]), "minnesota", false);
    assert_eq!(events.len(), 1);
    let event = &events[0];
    assert_eq!(event.id, "MSPCAD-129052");
    assert_eq!(event.event_type, "incident");
    assert_eq!(event.road_name, "I-35W"); // direction suffix stripped
    assert_eq!(event.description, "I-35W southbound: Crash.");
    assert_eq!(event.severity, "medium"); // priority 5
}

#[test]
fn test_cars_priority_severity_mapping() {
    assert_eq!(cars_priority_severity(&json!(1)), "high");
    assert_eq!(cars_priority_severity(&json!(2)), "high");
    assert_eq!(cars_priority_severity(&json!(3)), "medium");
    assert_eq!(cars_priority_severity(&json!(5)), "medium");
    assert_eq!(cars_priority_severity(&json!(8)), "low");
    assert_eq!(cars_priority_severity(&Value::Null), "low");
}

#[test]
fn test_cars_skips_scheduled_events() {
    let events = parse_cars_events(&response(vec![mn_future(), mn_crash()]), "minnesota", false);
    let ids: Vec<&str> = events.iter().map(|e| e.id.as_str()).collect();
    assert_eq!(ids, vec!["MSPCAD-129052"]);
}

#[test]
fn test_cars_skips_non_event_features() {
    let cluster = json!({
        "bbox": [-86.9, 41.0, -86.8, 41.1],
        "title": "12 events",
        "uri": "cluster/1",
        "features": [],
        "__typename": "Cluster",
    });
    let events = parse_cars_events(&response(vec![cluster, in_lane_closed()]), "indiana", true);
    let ids: Vec<&str> = events.iter().map(|e| e.id.as_str()).collect();
    assert_eq!(ids, vec!["CARSy-30"]);
}

#[test]
fn test_cars_bbox_fallback_coordinates() {
    let mut item = in_lane_closed();
    item["features"] = json!([]);
    let events = parse_cars_events(&response(vec![item]), "indiana", true);
    assert_eq!(events[0].latitude, Some((41.68731 + 41.68742) / 2.0));
    assert_eq!(events[0].longitude, Some((-86.84936 + -86.84715) / 2.0));
}

#[test]
fn test_cars_empty_and_malformed_responses() {
    assert!(parse_cars_events(&json!({}), "indiana", true).is_empty());
    assert!(parse_cars_events(&json!({"data": {}}), "indiana", true).is_empty());
    assert!(parse_cars_events(
        &json!({"data": {"mapFeaturesQuery": {"mapFeatures": null, "error": null}}}),
        "indiana",
        true,
    )
    .is_empty());
}

#[test]
fn split_cars_title_handles_notes_and_directions() {
    assert_eq!(
        split_cars_title("Ends Friday. I-70 in both directions: Bridge work."),
        ("I-70".into(), "".into(), "Bridge work.".into())
    );
    assert_eq!(
        split_cars_title("No colon here"),
        ("".into(), "".into(), "No colon here".into())
    );
}

// --- pyval

#[test]
fn py_str_matches_python_str_for_json_scalars() {
    assert_eq!(py_str(&Value::Null), "None");
    assert_eq!(py_str(&json!(true)), "True");
    assert_eq!(py_str(&json!(45)), "45");
    assert_eq!(py_str(&json!(45.0)), "45.0");
    assert_eq!(py_str(&json!(1e16)), "1e+16");
    assert_eq!(py_str(&json!("x")), "x");
}

#[test]
fn present_null_is_a_value_not_a_miss() {
    // `d.get("a", d.get("b", ""))` takes a present null over a fallback.
    let m = map(json!({"a": null, "b": "fallback"}));
    assert_eq!(chain_str(&m, &["a", "b"], ""), "None");
    assert_eq!(chain_str(&m, &["c", "b"], ""), "fallback");
    assert_eq!(chain_str(&m, &["c"], "dflt"), "dflt");
}
