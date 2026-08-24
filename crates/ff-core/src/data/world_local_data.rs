//! Checked-in city service and local approach data loaders (port of
//! `freight_fate/data/world_local_data.py`).
//!
//! Five JSON files (~31 MB) keyed by pre-slug city names and facility ids;
//! `World` remaps them onto canonical keys on first use. Each loader reads
//! the file it is given (a missing file reads as empty), deserializes the
//! fixed record shape with serde, and then applies the same validation and
//! raw-text screens as the Python loader.

use std::path::Path;
use std::sync::Arc;

use indexmap::IndexMap;
use serde::Deserialize;

use super::baked::BakedData;
use super::data_resources::{baked_at, read_text_at};
use super::world_constants::{
    set_contains, CITY_SERVICE_ORDER, CITY_SERVICE_SOURCE_TYPES, RAW_POI_TEXT_MARKERS,
};
use super::world_models::{
    DataError, FacilityApproach, FacilityEndpoint, LocalApproach, LocalGeometry,
    LocalGeometrySegment,
};
use super::world_parsing::py_repr_str;
use crate::pyfmt::round_py_n;

fn exposes_raw(text: &str) -> bool {
    let lowered = text.to_lowercase();
    RAW_POI_TEXT_MARKERS.iter().any(|m| lowered.contains(m))
}

/// Parse a runtime data file: `None` when it does not exist.
fn read_runtime_json<T: serde::de::DeserializeOwned>(path: &Path) -> Result<Option<T>, DataError> {
    let Some(text) = read_text_at(path) else {
        return Ok(None);
    };
    // `json.loads(text.lstrip("﻿"))` -- a BOM from a Windows editor.
    let text = text.trim_start_matches('\u{feff}');
    serde_json::from_str(text)
        .map(Some)
        .map_err(|e| DataError::io(format!("{}: {e}", path.display())))
}

fn s(text: &str) -> String {
    text.trim().to_string()
}

/// The baked container standing in for a loose file that is not on disk.
///
/// A release ships `world.ffdata` and none of these five JSON files, so a
/// caller that names one by path -- the `--smoke` check does, and so does any
/// tool reaching past `World` -- would otherwise read an empty map and think
/// the data layer was simply thin. `None` whenever the file exists (the JSON
/// tree always wins) or there is no container beside it.
fn baked_stand_in(path: &Path, expected_name: &str) -> Result<Option<Arc<BakedData>>, DataError> {
    if path.exists() || path.file_name() != Some(std::ffi::OsStr::new(expected_name)) {
        return Ok(None);
    }
    match path.parent() {
        Some(dir) => baked_at(dir),
        None => Ok(None),
    }
}

// ---------------------------------------------------------------- city services

/// One raw city-service record from `city_services.json`, kept in its file
/// shape because `World::city_services` reads it with its own defaults (the
/// Python loader stored `dict(entry)`).
#[derive(Debug, Clone, Default, Deserialize, PartialEq)]
pub struct CityServiceEntry {
    #[serde(default)]
    pub key: String,
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub kind: Option<String>,
    #[serde(default)]
    pub source_note: String,
    #[serde(default)]
    pub lat: f64,
    #[serde(default)]
    pub lon: f64,
    #[serde(default)]
    pub approach_miles: f64,
    #[serde(default)]
    pub approach_road: String,
    #[serde(default)]
    pub source_type: Option<String>,
    #[serde(default)]
    pub source_ref: String,
    #[serde(default)]
    pub fallback: bool,
    #[serde(default)]
    pub fallback_reason: String,
    #[serde(default)]
    pub city: String,
    #[serde(default)]
    pub state: String,
}

#[derive(Deserialize)]
struct CityServicesFile {
    #[serde(default)]
    cities: IndexMap<String, Vec<CityServiceEntry>>,
}

/// city name -> service key -> raw entry.
pub type CityServiceData = IndexMap<String, IndexMap<String, CityServiceEntry>>;

pub fn load_city_service_data(path: &Path) -> Result<CityServiceData, DataError> {
    let Some(raw) = read_runtime_json::<CityServicesFile>(path)? else {
        return match baked_stand_in(path, "city_services.json")? {
            Some(container) => container.city_service_data(),
            None => Ok(IndexMap::new()),
        };
    };
    let p = path.display();
    let mut out: CityServiceData = IndexMap::new();
    for (city, entries) in raw.cities {
        let rcity = py_repr_str(&city);
        let mut city_services: IndexMap<String, CityServiceEntry> = IndexMap::new();
        for entry in entries {
            let key = s(&entry.key);
            if !set_contains(CITY_SERVICE_ORDER, &key) {
                return Err(DataError::value(format!(
                    "{p} city {rcity} has unknown service key {}",
                    py_repr_str(&key)
                )));
            }
            if city_services.contains_key(&key) {
                return Err(DataError::value(format!(
                    "{p} city {rcity} repeats service key {}",
                    py_repr_str(&key)
                )));
            }
            let name = s(&entry.name);
            let rname = py_repr_str(&name);
            if name.is_empty() {
                return Err(DataError::value(format!(
                    "{p} city {rcity} service {} has no name",
                    py_repr_str(&key)
                )));
            }
            if exposes_raw(&name) {
                return Err(DataError::value(format!(
                    "{p} city {rcity} service {rname} exposes raw OSM/source text"
                )));
            }
            let source_type = s(entry.source_type.as_deref().unwrap_or("fallback"));
            if !set_contains(CITY_SERVICE_SOURCE_TYPES, &source_type) {
                return Err(DataError::value(format!(
                    "{p} city {rcity} service {rname} has unknown source_type {}",
                    py_repr_str(&source_type)
                )));
            }
            if s(&entry.source_note).is_empty() {
                return Err(DataError::value(format!(
                    "{p} city {rcity} service {rname} has no source note"
                )));
            }
            if entry.fallback && s(&entry.fallback_reason).is_empty() {
                return Err(DataError::value(format!(
                    "{p} city {rcity} service {rname} is fallback without a reason"
                )));
            }
            if entry.approach_miles <= 0.0 || entry.approach_miles > 50.0 {
                return Err(DataError::value(format!(
                    "{p} city {rcity} service {rname} has invalid approach miles"
                )));
            }
            if !(-90.0..=90.0).contains(&entry.lat) || !(-180.0..=180.0).contains(&entry.lon) {
                return Err(DataError::value(format!(
                    "{p} city {rcity} service {rname} has invalid coordinates"
                )));
            }
            if s(&entry.approach_road).is_empty() {
                return Err(DataError::value(format!(
                    "{p} city {rcity} service {rname} has no approach road"
                )));
            }
            city_services.insert(key, entry);
        }
        out.insert(city, city_services);
    }
    Ok(out)
}

// ---------------------------------------------------------------- local approaches

#[derive(Deserialize)]
struct LocalApproachEntry {
    #[serde(default)]
    name: String,
    #[serde(default)]
    road: String,
    #[serde(default)]
    target_type: String,
    #[serde(default)]
    city: String,
    #[serde(default)]
    source_type: String,
    #[serde(default)]
    approach_miles: f64,
    #[serde(default)]
    fallback: bool,
    #[serde(default)]
    fallback_reason: String,
    #[serde(default)]
    turn_segments: Vec<String>,
    #[serde(default = "default_true")]
    estimated: bool,
    #[serde(default)]
    distance_to_road_mi: f64,
}

fn default_true() -> bool {
    true
}

#[derive(Deserialize)]
struct LocalApproachesFile {
    #[serde(default)]
    approaches: IndexMap<String, LocalApproachEntry>,
}

pub fn load_local_approaches(path: &Path) -> Result<IndexMap<String, LocalApproach>, DataError> {
    let Some(raw) = read_runtime_json::<LocalApproachesFile>(path)? else {
        return match baked_stand_in(path, "local_approaches.json")? {
            Some(container) => container.local_approaches(),
            None => Ok(IndexMap::new()),
        };
    };
    let p = path.display();
    let mut out = IndexMap::new();
    for (target_id, entry) in raw.approaches {
        let rid = py_repr_str(&target_id);
        let name = s(&entry.name);
        let road = s(&entry.road);
        let target_type = s(&entry.target_type);
        let city = s(&entry.city);
        let source_type = s(&entry.source_type);
        if name.is_empty()
            || road.is_empty()
            || target_type.is_empty()
            || city.is_empty()
            || source_type.is_empty()
        {
            return Err(DataError::value(format!(
                "{p} local approach {rid} is missing required text"
            )));
        }
        if exposes_raw(&format!("{name} {road}")) {
            return Err(DataError::value(format!(
                "{p} local approach {rid} exposes raw OSM/source text"
            )));
        }
        if entry.approach_miles <= 0.0 || entry.approach_miles > 75.0 {
            return Err(DataError::value(format!(
                "{p} local approach {rid} has invalid mileage"
            )));
        }
        let fallback_reason = s(&entry.fallback_reason);
        if entry.fallback && fallback_reason.is_empty() {
            return Err(DataError::value(format!(
                "{p} local approach {rid} is fallback without reason"
            )));
        }
        let segments: Vec<String> = entry
            .turn_segments
            .iter()
            .map(|seg| s(seg))
            .filter(|seg| !seg.is_empty())
            .collect();
        for segment in &segments {
            if exposes_raw(segment) {
                return Err(DataError::value(format!(
                    "{p} local approach {rid} segment exposes raw source text"
                )));
            }
        }
        out.insert(
            target_id.clone(),
            LocalApproach {
                target_id,
                target_type,
                city,
                name,
                approach_miles: round_py_n(entry.approach_miles, 1),
                road,
                source_type,
                estimated: entry.estimated,
                fallback: entry.fallback,
                fallback_reason,
                distance_to_road_mi: round_py_n(entry.distance_to_road_mi, 2),
                turn_segments: segments,
            },
        );
    }
    Ok(out)
}

// ---------------------------------------------------------------- local geometry

#[derive(Deserialize)]
struct RawSegment {
    #[serde(default)]
    road: String,
    #[serde(default)]
    cue: String,
    #[serde(default)]
    miles: f64,
    #[serde(default = "default_speed")]
    speed_mph: f64,
}

fn default_speed() -> f64 {
    25.0
}

#[derive(Deserialize)]
struct LocalGeometryEntry {
    #[serde(default)]
    name: String,
    #[serde(default)]
    target_type: String,
    #[serde(default)]
    city: String,
    #[serde(default)]
    source_type: String,
    #[serde(default)]
    fallback: bool,
    #[serde(default)]
    turn_level: bool,
    #[serde(default)]
    fallback_reason: String,
    #[serde(default)]
    segments: Vec<RawSegment>,
    #[serde(default)]
    total_miles: f64,
    #[serde(default = "default_true")]
    estimated: bool,
}

#[derive(Deserialize)]
struct LocalGeometriesFile {
    #[serde(default)]
    geometries: IndexMap<String, LocalGeometryEntry>,
}

pub fn load_local_geometries(path: &Path) -> Result<IndexMap<String, LocalGeometry>, DataError> {
    let Some(raw) = read_runtime_json::<LocalGeometriesFile>(path)? else {
        return match baked_stand_in(path, "local_geometry.json")? {
            Some(container) => container.local_geometries(),
            None => Ok(IndexMap::new()),
        };
    };
    let p = path.display();
    let mut out = IndexMap::new();
    for (target_id, entry) in raw.geometries {
        let rid = py_repr_str(&target_id);
        let name = s(&entry.name);
        let target_type = s(&entry.target_type);
        let city = s(&entry.city);
        let source_type = s(&entry.source_type);
        if name.is_empty() || target_type.is_empty() || city.is_empty() || source_type.is_empty() {
            return Err(DataError::value(format!(
                "{p} local geometry {rid} is missing required text"
            )));
        }
        if exposes_raw(&name) {
            return Err(DataError::value(format!(
                "{p} local geometry {rid} exposes raw source text"
            )));
        }
        let fallback_reason = s(&entry.fallback_reason);
        if entry.fallback && fallback_reason.is_empty() {
            return Err(DataError::value(format!(
                "{p} local geometry {rid} is fallback without reason"
            )));
        }
        let mut segments = Vec::with_capacity(entry.segments.len());
        for raw_segment in &entry.segments {
            let road = s(&raw_segment.road);
            let cue = s(&raw_segment.cue);
            if road.is_empty() || cue.is_empty() || raw_segment.miles <= 0.0 {
                return Err(DataError::value(format!(
                    "{p} local geometry {rid} has invalid segment"
                )));
            }
            if exposes_raw(&format!("{road} {cue}")) {
                return Err(DataError::value(format!(
                    "{p} local geometry {rid} segment exposes raw source text"
                )));
            }
            segments.push(LocalGeometrySegment {
                road,
                miles: round_py_n(raw_segment.miles, 2),
                cue,
                speed_mph: raw_segment.speed_mph,
            });
        }
        let total_miles = round_py_n(entry.total_miles, 2);
        if entry.turn_level {
            if segments.is_empty() {
                return Err(DataError::value(format!(
                    "{p} local geometry {rid} has no segments"
                )));
            }
            if total_miles <= 0.0 {
                return Err(DataError::value(format!(
                    "{p} local geometry {rid} has invalid mileage"
                )));
            }
        }
        out.insert(
            target_id.clone(),
            LocalGeometry {
                target_id,
                target_type,
                city,
                name,
                turn_level: entry.turn_level,
                source_type,
                estimated: entry.estimated,
                fallback: entry.fallback,
                fallback_reason,
                total_miles,
                segments,
            },
        );
    }
    Ok(out)
}

// ---------------------------------------------------------------- facility endpoints

#[derive(Deserialize)]
struct FacilityEndpointEntry {
    #[serde(default)]
    endpoint_name: String,
    #[serde(default)]
    facility_name: String,
    #[serde(default)]
    approach_road: String,
    #[serde(default)]
    source_type: String,
    #[serde(default)]
    source_note: String,
    #[serde(default)]
    city: String,
    #[serde(default)]
    state: String,
    #[serde(default)]
    facility_type: String,
    #[serde(default = "default_true")]
    fallback: bool,
    #[serde(default)]
    fallback_reason: String,
    #[serde(default)]
    approach_miles: f64,
    #[serde(default)]
    lat: f64,
    #[serde(default)]
    lon: f64,
    #[serde(default)]
    source_ref: String,
    #[serde(default)]
    source_backed: bool,
    #[serde(default)]
    nearest_road_context: bool,
    #[serde(default)]
    turn_level_geometry: bool,
    #[serde(default)]
    gate_hint: bool,
    #[serde(default)]
    yard_hint: bool,
    #[serde(default)]
    dock_hint: bool,
    #[serde(default)]
    mapping: String,
}

#[derive(Deserialize)]
struct FacilityEndpointsFile {
    #[serde(default)]
    endpoints: IndexMap<String, FacilityEndpointEntry>,
}

pub fn load_facility_endpoints(
    path: &Path,
) -> Result<IndexMap<String, FacilityEndpoint>, DataError> {
    let Some(raw) = read_runtime_json::<FacilityEndpointsFile>(path)? else {
        return match baked_stand_in(path, "facility_endpoints.json")? {
            Some(container) => container.facility_endpoints(),
            None => Ok(IndexMap::new()),
        };
    };
    let p = path.display();
    let mut out = IndexMap::new();
    for (facility_id, entry) in raw.endpoints {
        let rid = py_repr_str(&facility_id);
        let name = s(&entry.endpoint_name);
        let facility_name = s(&entry.facility_name);
        let road = s(&entry.approach_road);
        let source_type = s(&entry.source_type);
        let source_note = s(&entry.source_note);
        if name.is_empty()
            || facility_name.is_empty()
            || source_type.is_empty()
            || source_note.is_empty()
        {
            return Err(DataError::value(format!(
                "{p} facility endpoint {rid} is missing text"
            )));
        }
        if exposes_raw(&format!("{name} {facility_name} {road}")) {
            return Err(DataError::value(format!(
                "{p} facility endpoint {rid} exposes raw source text"
            )));
        }
        let fallback_reason = s(&entry.fallback_reason);
        if entry.fallback && fallback_reason.is_empty() {
            return Err(DataError::value(format!(
                "{p} facility endpoint {rid} is fallback without reason"
            )));
        }
        if !entry.fallback
            && (entry.approach_miles <= 0.0 || entry.approach_miles > 50.0 || road.is_empty())
        {
            return Err(DataError::value(format!(
                "{p} facility endpoint {rid} has invalid approach"
            )));
        }
        if !(-90.0..=90.0).contains(&entry.lat) || !(-180.0..=180.0).contains(&entry.lon) {
            return Err(DataError::value(format!(
                "{p} facility endpoint {rid} has invalid coordinates"
            )));
        }
        out.insert(
            facility_id.clone(),
            FacilityEndpoint {
                facility_id,
                city: s(&entry.city),
                state: s(&entry.state),
                facility_name,
                facility_type: s(&entry.facility_type),
                endpoint_name: name,
                source_type,
                source_note,
                lat: entry.lat,
                lon: entry.lon,
                approach_miles: round_py_n(entry.approach_miles, 1),
                approach_road: road,
                source_ref: s(&entry.source_ref),
                source_backed: entry.source_backed,
                fallback: entry.fallback,
                fallback_reason,
                nearest_road_context: entry.nearest_road_context,
                turn_level_geometry: entry.turn_level_geometry,
                gate_hint: entry.gate_hint,
                yard_hint: entry.yard_hint,
                dock_hint: entry.dock_hint,
                mapping: s(&entry.mapping),
            },
        );
    }
    Ok(out)
}

// ---------------------------------------------------------------- facility approaches

#[derive(Deserialize)]
struct FacilityApproachEntry {
    #[serde(default)]
    facility_name: String,
    #[serde(default)]
    endpoint_name: String,
    #[serde(default)]
    approach_road: String,
    #[serde(default)]
    source_type: String,
    #[serde(default = "default_true")]
    fallback: bool,
    #[serde(default)]
    fallback_reason: String,
    #[serde(default)]
    segments: Vec<RawSegment>,
    #[serde(default)]
    turn_level: bool,
    #[serde(default)]
    city: String,
    #[serde(default)]
    state: String,
    #[serde(default)]
    facility_type: String,
    #[serde(default)]
    endpoint_source_backed: bool,
    #[serde(default)]
    road_snapped: bool,
    #[serde(default = "default_true")]
    estimated: bool,
    #[serde(default)]
    nearest_road_context: bool,
    #[serde(default = "default_true")]
    representative_fallback: bool,
    #[serde(default)]
    total_miles: f64,
    #[serde(default)]
    gate_hint: bool,
    #[serde(default)]
    yard_hint: bool,
    #[serde(default)]
    dock_hint: bool,
    #[serde(default)]
    final_hint: String,
    #[serde(default)]
    source_note: String,
}

#[derive(Deserialize)]
struct FacilityApproachesFile {
    #[serde(default)]
    approaches: IndexMap<String, FacilityApproachEntry>,
}

pub fn load_facility_approaches(
    path: &Path,
) -> Result<IndexMap<String, FacilityApproach>, DataError> {
    let Some(raw) = read_runtime_json::<FacilityApproachesFile>(path)? else {
        return match baked_stand_in(path, "facility_approaches.json")? {
            Some(container) => container.facility_approaches(),
            None => Ok(IndexMap::new()),
        };
    };
    let p = path.display();
    let mut out = IndexMap::new();
    for (facility_id, entry) in raw.approaches {
        let rid = py_repr_str(&facility_id);
        let facility_name = s(&entry.facility_name);
        let endpoint_name = s(&entry.endpoint_name);
        let road = s(&entry.approach_road);
        let source_type = s(&entry.source_type);
        if facility_name.is_empty()
            || endpoint_name.is_empty()
            || road.is_empty()
            || source_type.is_empty()
        {
            return Err(DataError::value(format!(
                "{p} facility approach {rid} is missing text"
            )));
        }
        if exposes_raw(&format!("{facility_name} {endpoint_name} {road}")) {
            return Err(DataError::value(format!(
                "{p} facility approach {rid} exposes raw source text"
            )));
        }
        let fallback_reason = s(&entry.fallback_reason);
        if entry.fallback && fallback_reason.is_empty() {
            return Err(DataError::value(format!(
                "{p} facility approach {rid} is fallback without reason"
            )));
        }
        let mut segments = Vec::with_capacity(entry.segments.len());
        for raw_segment in &entry.segments {
            let segment_road = s(&raw_segment.road);
            let cue = s(&raw_segment.cue);
            if segment_road.is_empty() || cue.is_empty() || raw_segment.miles <= 0.0 {
                return Err(DataError::value(format!(
                    "{p} facility approach {rid} has invalid segment"
                )));
            }
            if exposes_raw(&format!("{segment_road} {cue}")) {
                return Err(DataError::value(format!(
                    "{p} facility approach {rid} segment exposes raw text"
                )));
            }
            segments.push(LocalGeometrySegment {
                road: segment_road,
                miles: round_py_n(raw_segment.miles, 2),
                cue,
                speed_mph: raw_segment.speed_mph,
            });
        }
        if entry.turn_level && segments.is_empty() {
            return Err(DataError::value(format!(
                "{p} facility approach {rid} has no turn segments"
            )));
        }
        out.insert(
            facility_id.clone(),
            FacilityApproach {
                facility_id,
                city: s(&entry.city),
                state: s(&entry.state),
                facility_name,
                facility_type: s(&entry.facility_type),
                endpoint_name,
                endpoint_source_backed: entry.endpoint_source_backed,
                road_snapped: entry.road_snapped,
                turn_level: entry.turn_level,
                source_type,
                estimated: entry.estimated,
                fallback: entry.fallback,
                fallback_reason,
                nearest_road_context: entry.nearest_road_context,
                representative_fallback: entry.representative_fallback,
                total_miles: round_py_n(entry.total_miles, 2),
                approach_road: road,
                segments,
                gate_hint: entry.gate_hint,
                yard_hint: entry.yard_hint,
                dock_hint: entry.dock_hint,
                final_hint: s(&entry.final_hint),
                source_note: s(&entry.source_note),
            },
        );
    }
    Ok(out)
}
