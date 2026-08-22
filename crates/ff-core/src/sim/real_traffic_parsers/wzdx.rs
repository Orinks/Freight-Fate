//! WZDx (Work Zone Data Exchange) parsers: the GeoJSON FeatureCollection
//! feeds every live state publishes today, in both the older camelCase
//! layout and the v4.x snake_case `core_details` layout. Split out of
//! `real_traffic_parsers` to keep that file under the thousand-line mark.

use serde_json::{Map, Value};

use super::pyval::{as_map, chain, chain_str, py_str, str_or_empty, to_f64, truthy};
use super::{construction_severity, describe_lanes_affected, event_list, float_pair, TrafficEvent};

// ---- WZDx standard parser (GeoJSON FeatureCollection) ----------------

/// Parse incidents from a WZDx GeoJSON FeatureCollection.
///
/// The WZDx standard (Work Zone Data Exchange) is a USDOT-specified
/// format.  Responses are GeoJSON FeatureCollections; older feeds carry
/// camelCase properties (optionally `wzdx:`-namespaced), while the
/// v4.x feeds every live state publishes today move the shared fields
/// into a snake_case `core_details` object.
pub fn parse_wzdx_events(data: &Value, _state: &str) -> Vec<TrafficEvent> {
    let mut events = Vec::new();
    let Some(features) = event_list(data, &["features", "events", "results"]) else {
        return events;
    };
    for feature in &features {
        let Some(feature_map) = feature.as_object() else {
            continue;
        };
        let event_id = chain_str(feature_map, &["id", "feature_id"], "");
        if event_id.is_empty() {
            continue;
        }
        // Extract coordinates from GeoJSON Point geometry
        let (lat, lon) = extract_wzdx_coordinates(feature_map);
        // Properties may be namespaced (wzdx:roadName) or flat (roadName)
        let props = match feature_map.get("properties") {
            Some(Value::Object(props)) => props,
            _ => feature_map,
        };
        // WZDx v4.x: shared fields moved into core_details
        if let Some(core) = as_map(props.get("core_details")) {
            if let Some(event) = build_wzdx_v4_event(&event_id, core, props, lat, lon) {
                events.push(event);
            }
            continue;
        }
        let road_name = wzdx_prop(props, "roadName", "");
        let event_type = wzdx_prop(props, "workZoneType", "construction").to_lowercase();
        // Normalize to our standard types
        let mapped_type =
            if ["construction", "maintenance", "bridge", "paving"].contains(&event_type.as_str()) {
                "construction"
            } else {
                "incident"
            };
        let mut description = wzdx_prop(props, "description", "");
        if description.is_empty() {
            description = wzdx_prop(props, "workZoneName", "");
        }
        let county = wzdx_prop(props, "county", "");
        let start_time = wzdx_prop(props, "startDate", "");
        let estimated_end = wzdx_prop(props, "endDate", "");
        // Vehicle impact → closure type
        let vehicle_impact = wzdx_prop(props, "vehicleImpact", "").to_lowercase();
        let closure = wzdx_impact_to_closure(&vehicle_impact);
        let severity = construction_severity(closure);
        // Lane info
        let mut lanes = wzdx_prop(props, "lanesAffected", "");
        if lanes.is_empty() {
            let mut closure_map = Map::new();
            closure_map.insert("closure".into(), Value::from(closure));
            lanes = describe_lanes_affected(&closure_map);
        }
        // Location text
        let location_text = build_wzdx_location_text(props);
        events.push(TrafficEvent {
            id: event_id,
            event_type: mapped_type.into(),
            severity: severity.into(),
            description,
            county,
            latitude: lat,
            longitude: lon,
            start_time: Some(start_time),
            estimated_end: Some(estimated_end),
            lanes_affected: Some(lanes),
            road_name,
            location_text,
            closure: closure.into(),
            work_type: "construction".into(),
        });
    }
    events
}

/// Build a TrafficEvent from a WZDx v4.x feature.
///
/// v4.x renamed everything to snake_case and nested the shared fields
/// under `core_details` (checked 2026-08-09: 511wi.gov, az511.com,
/// 511ny.org, and fl511.com all publish v4.2 this way).
pub fn build_wzdx_v4_event(
    event_id: &str,
    core: &Map<String, Value>,
    props: &Map<String, Value>,
    lat: Option<f64>,
    lon: Option<f64>,
) -> Option<TrafficEvent> {
    let road_name = match core.get("road_names").and_then(Value::as_array) {
        Some(names) if !names.is_empty() => py_str(&names[0]),
        _ => String::new(),
    };
    let event_type = chain_str(core, &["event_type"], "work-zone").to_lowercase();
    let mapped_type = if ["work-zone", "detour"].contains(&event_type.as_str()) {
        "construction"
    } else {
        "incident"
    };
    let description = {
        let first = core.get("description").filter(|v| truthy(v));
        match first {
            Some(v) => py_str(v),
            None => chain_str(core, &["name"], ""),
        }
    };
    let start_time = str_or_empty(props.get("start_date"));
    let estimated_end = str_or_empty(props.get("end_date"));

    let vehicle_impact = chain_str(props, &["vehicle_impact"], "").to_lowercase();
    let closure = wzdx_impact_to_closure(&vehicle_impact);
    let severity = construction_severity(closure);

    let mut lanes = describe_wzdx_v4_lanes(props.get("lanes").unwrap_or(&Value::Null));
    if lanes.is_empty() {
        let mut closure_map = Map::new();
        closure_map.insert("closure".into(), Value::from(closure));
        lanes = describe_lanes_affected(&closure_map);
    }

    let begin = str_or_empty(props.get("beginning_cross_street"));
    let end = str_or_empty(props.get("ending_cross_street"));
    let location_text = if !begin.is_empty() && !end.is_empty() {
        format!("Between {begin} and {end}")
    } else if !begin.is_empty() {
        format!("Near {begin}")
    } else {
        let begin_mp = props.get("beginning_milepost").filter(|v| truthy(v));
        let end_mp = props.get("ending_milepost").filter(|v| truthy(v));
        match (begin_mp, end_mp) {
            (Some(b), Some(e)) => format!("Between milepost {} and {}", py_str(b), py_str(e)),
            (Some(b), None) => format!("Near milepost {}", py_str(b)),
            _ => String::new(),
        }
    };

    Some(TrafficEvent {
        id: event_id.to_string(),
        event_type: mapped_type.into(),
        severity: severity.into(),
        description,
        county: String::new(),
        latitude: lat,
        longitude: lon,
        start_time: Some(start_time),
        estimated_end: Some(estimated_end),
        lanes_affected: Some(lanes),
        road_name,
        location_text,
        closure: closure.into(),
        work_type: if mapped_type == "construction" {
            "construction".into()
        } else {
            String::new()
        },
    })
}

/// Describe closed lanes from a WZDx v4 `lanes` array.
pub fn describe_wzdx_v4_lanes(lanes: &Value) -> String {
    let Some(lanes) = lanes.as_array().filter(|l| !l.is_empty()) else {
        return String::new();
    };
    let field = |lane: &Map<String, Value>, key: &str| chain_str(lane, &[key], "").to_lowercase();
    let closed: Vec<&Map<String, Value>> = lanes
        .iter()
        .filter_map(Value::as_object)
        .filter(|lane| field(lane, "status") == "closed")
        .collect();
    let closed_general: Vec<&&Map<String, Value>> = closed
        .iter()
        .filter(|lane| field(lane, "type") != "shoulder")
        .collect();
    if !closed_general.is_empty() {
        let total_general = lanes
            .iter()
            .filter_map(Value::as_object)
            .filter(|lane| field(lane, "type") != "shoulder")
            .count();
        return format!("{} of {} lanes closed", closed_general.len(), total_general);
    }
    if !closed.is_empty() {
        return "shoulder closed".into();
    }
    String::new()
}

/// Parse construction work-zone events from a WZDx feed.
///
/// Most WZDx feeds are construction-specific (the standard is designed for
/// work zones), but we still filter to `event_type == 'construction'`
/// for safety.
pub fn parse_wzdx_construction_events(data: &Value, state: &str) -> Vec<TrafficEvent> {
    parse_wzdx_events(data, state)
        .into_iter()
        .filter(|e| e.event_type == "construction")
        .collect()
}

/// Extract lat/lon from a WZDx GeoJSON feature.
pub fn extract_wzdx_coordinates(feature: &Map<String, Value>) -> (Option<f64>, Option<f64>) {
    // Point geometry: {"type": "Point", "coordinates": [lon, lat]}
    // LineString/MultiPoint nest the pairs one level deeper (511ny.org
    // publishes MultiPoint, checked 2026-08-09); take the midpoint pair.
    if let Some(geometry) = as_map(feature.get("geometry")) {
        if let Some(coords) = geometry
            .get("coordinates")
            .and_then(Value::as_array)
            .filter(|c| !c.is_empty())
        {
            let pair: &Value = if coords[0].is_array() {
                &coords[coords.len() / 2]
            } else {
                geometry.get("coordinates").unwrap()
            };
            if let Some(pair) = pair.as_array().filter(|p| p.len() >= 2) {
                if let (Some(lat), Some(lon)) = (to_f64(&pair[1]), to_f64(&pair[0])) {
                    return (Some(lat), Some(lon)); // [lon, lat]
                }
            }
        }
    }
    // Fall back to properties lat/lon (uncommon but possible)
    if let Some(props) = as_map(feature.get("properties")) {
        let lat = chain(props, &["lat", "latitude"]);
        let lon = chain(props, &["lon", "lng", "longitude"]);
        if let Some((lat, lon)) = float_pair(lat, lon) {
            return (Some(lat), Some(lon));
        }
    }
    (None, None)
}

/// Read a WZDx property, trying both namespaced and flat keys.
pub fn wzdx_prop(props: &Map<String, Value>, key: &str, default: &str) -> String {
    // Try with namespace first
    let namespaced = format!("wzdx:{key}");
    match chain(props, &[namespaced.as_str(), key]) {
        None | Some(Value::Null) => default.to_string(),
        Some(value) => py_str(value),
    }
}

/// Map WZDx vehicleImpact enum to closure type string.
pub fn wzdx_impact_to_closure(impact: &str) -> &'static str {
    match impact {
        "all-lanes-closed" => "full closure",
        "some-lanes-closed" => "single lane",
        "shoulder-closed" => "shoulder",
        "alternating-one-way" => "alternating",
        "flow-of-traffic" => "single lane",
        "no-impact" => "single lane",
        "" => "single lane",
        _ => "single lane",
    }
}

/// Build a location description from WZDx properties.
pub fn build_wzdx_location_text(props: &Map<String, Value>) -> String {
    let loc = wzdx_prop(props, "locationDescription", "");
    if !loc.is_empty() {
        return loc;
    }
    let begin = wzdx_prop(props, "beginningMilepost", "");
    let end = wzdx_prop(props, "endingMilepost", "");
    if !begin.is_empty() && !end.is_empty() {
        return format!("Between milepost {begin} and {end}");
    }
    if !begin.is_empty() {
        return format!("Near milepost {begin}");
    }
    String::new()
}
