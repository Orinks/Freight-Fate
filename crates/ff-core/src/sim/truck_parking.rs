//! Truck parking availability via TPIMS (Truck Parking Information Management System).
//!
//! Fetches real-time truck parking availability from state TPIMS APIs, which provide
//! live parking space counts at public and private truck stops. Wisconsin (511WI)
//! is the live implementation; Ohio (OHGO) keeps its keyless-era config on the
//! no_api bench until an API-key story exists. The architecture is designed for
//! easy addition of other TPIMS states (Kansas, Iowa, Minnesota, Missouri).
//!
//! Like the real_weather and real_traffic systems, this is non-blocking with caching
//! and graceful fallback to static parking data when APIs are unavailable.
//!
//! Port of `freight_fate/sim/truck_parking.py`; the network rides the
//! [`HttpTransport`] seam from `real_traffic`.

use std::collections::HashMap;
use std::io::Read;
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;

use serde_json::{json, Value};

use super::real_traffic::{
    haversine_distance, lock_unpoisoned, urlencode, wall_clock, wall_time, Clock, HttpTransport,
    NoTransport, TransportError, DEFAULT_USER_AGENT,
};
use super::real_traffic_parsers::pyval::{chain_str, py_str, str_or_empty, to_f64, to_i64, truthy};

/// One state's TPIMS configuration.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TpimsApi {
    pub base_url: &'static str,
    pub parking_endpoint: &'static str,
    pub icons_endpoint: Option<&'static str>,
    pub name: &'static str,
    pub parser: &'static str,
}

/// TPIMS API endpoints for supported states.
pub static TPIMS_APIS: &[(&str, TpimsApi)] = &[
    // publicapi.ohgo.com's keyless v1 endpoints are gone (404, checked
    // 2026-08-09; the replacement API answers 401 without a registered key),
    // so Ohio sits on no_api until a key story exists.  The endpoint stays
    // listed for when it does.
    (
        "ohio",
        TpimsApi {
            base_url: "https://publicapi.ohgo.com",
            parking_endpoint: "/v1/truck-parking",
            icons_endpoint: None,
            name: "Ohio OHGO TPIMS",
            parser: "no_api",
        },
    ),
    // 511wi.gov TPIMS sites (found 2026-08-09): live counts and site names
    // come from the list endpoint (POST /List/GetData/truckparking, a
    // DataTables-style form post), coordinates from the map icon layer
    // (GET /map/mapIcons/TruckParking); the parser joins the two by site id.
    (
        "wisconsin",
        TpimsApi {
            base_url: "https://511wi.gov",
            parking_endpoint: "/List/GetData/truckparking",
            icons_endpoint: Some("/map/mapIcons/TruckParking"),
            name: "Wisconsin 511WI TPIMS",
            parser: "wi511",
        },
    ),
    // Future TPIMS states can be added here:
    // ("kansas", TpimsApi { base_url: "https://...", parking_endpoint: "...", name: "Kansas TPIMS", .. }),
];

/// The registry entry for a lower-case state key.
pub fn tpims_api(state_key: &str) -> Option<&'static TpimsApi> {
    TPIMS_APIS
        .iter()
        .find(|(key, _)| *key == state_key)
        .map(|(_, api)| api)
}

// Cache settings
pub const FETCH_TIMEOUT_S: f64 = 8.0;
/// 5 minutes - parking changes moderately frequently
pub const CACHE_TTL_S: f64 = 5.0 * 60.0;
/// Serve stale data for 30 minutes if fetches fail
pub const STALE_AFTER_S: f64 = 30.0 * 60.0;
/// Wait 2 minutes before retrying failed state
pub const RETRY_AFTER_S: f64 = 120.0;

/// A truck parking location with availability data.
#[derive(Debug, Clone, PartialEq)]
pub struct TruckParkingLocation {
    pub id: String,
    pub name: String,
    /// Road or intersection description
    pub location: String,
    pub address: Option<String>,
    pub description: Option<String>,
    pub capacity: Option<i64>,
    pub available: Option<i64>,
    pub latitude: Option<f64>,
    pub longitude: Option<f64>,
    pub open: bool,
    pub last_reported: Option<String>,
}

impl Default for TruckParkingLocation {
    fn default() -> Self {
        Self {
            id: String::new(),
            name: String::new(),
            location: String::new(),
            address: None,
            description: None,
            capacity: None,
            available: None,
            latitude: None,
            longitude: None,
            open: true,
            last_reported: None,
        }
    }
}

impl TruckParkingLocation {
    /// The three required dataclass fields; the rest keep their defaults.
    pub fn new(id: &str, name: &str, location: &str) -> Self {
        Self {
            id: id.to_string(),
            name: name.to_string(),
            location: location.to_string(),
            ..Self::default()
        }
    }

    /// Calculate occupancy percentage if capacity and available are known.
    pub fn occupancy_percentage(&self) -> Option<f64> {
        let (capacity, available) = (self.capacity?, self.available?);
        if capacity == 0 {
            return None;
        }
        Some(((capacity - available) as f64 / capacity as f64) * 100.0)
    }

    /// Get human-readable availability status.
    pub fn availability_status(&self) -> &'static str {
        if !self.open {
            return "closed";
        }
        let Some(available) = self.available else {
            return "unknown";
        };
        if available == 0 {
            return "full";
        }
        let occupancy = self.occupancy_percentage();
        if occupancy.is_some_and(|o| o > 90.0) {
            return "almost_full";
        }
        if occupancy.is_some_and(|o| o > 75.0) {
            return "mostly_full";
        }
        "available"
    }

    pub fn to_dict(&self) -> Value {
        json!({
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "address": self.address,
            "description": self.description,
            "capacity": self.capacity,
            "available": self.available,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "open": self.open,
            "last_reported": self.last_reported,
        })
    }

    pub fn from_dict(data: &Value) -> Option<TruckParkingLocation> {
        let data = data.as_object()?;
        if data.is_empty() {
            return None;
        }
        let location_id = chain_str(data, &["id"], "");
        if location_id.is_empty() {
            return None;
        }
        let raw_opt = |key: &str| -> Option<String> {
            match data.get(key) {
                None | Some(Value::Null) => None,
                Some(v) => Some(py_str(v)),
            }
        };
        // `int(data["capacity"]) if data.get("capacity") else None`
        let capacity = match data.get("capacity") {
            Some(v) if truthy(v) => Some(to_i64(v)?),
            _ => None,
        };
        // `int(data.get("reportedAvailable") or data.get("available"))`
        let reported = [data.get("reportedAvailable"), data.get("available")]
            .into_iter()
            .flatten()
            .find(|v| truthy(v));
        let available = match reported {
            Some(v) => Some(to_i64(v)?),
            None => None,
        };
        let coordinate = |key: &str| -> Option<Option<f64>> {
            match data.get(key) {
                Some(v) if truthy(v) => Some(Some(to_f64(v)?)),
                _ => Some(None),
            }
        };
        Some(TruckParkingLocation {
            id: location_id,
            name: chain_str(data, &["name"], ""),
            location: chain_str(data, &["location"], ""),
            address: raw_opt("address"),
            description: raw_opt("description"),
            capacity,
            available,
            latitude: coordinate("latitude")?,
            longitude: coordinate("longitude")?,
            open: data.get("open").map(truthy).unwrap_or(true),
            last_reported: raw_opt("lastReported"),
        })
    }
}

/// Current truck parking availability for a state or region.
#[derive(Debug, Clone, PartialEq)]
pub struct ParkingData {
    pub state: String,
    pub locations: Vec<TruckParkingLocation>,
    pub last_updated: f64,
    pub cache_time: f64,
    pub source: String,
}

impl ParkingData {
    pub fn new(
        state: &str,
        locations: Vec<TruckParkingLocation>,
        last_updated: f64,
        cache_time: f64,
        source: &str,
    ) -> Self {
        Self {
            state: state.to_string(),
            locations,
            last_updated,
            cache_time,
            source: source.to_string(),
        }
    }

    /// Check if data is still within cache TTL (against the wall clock).
    pub fn is_fresh(&self) -> bool {
        self.is_fresh_at(wall_time())
    }

    /// Check if data is still within cache TTL at `now`.
    pub fn is_fresh_at(&self, now: f64) -> bool {
        now - self.cache_time < CACHE_TTL_S
    }

    /// Check if data is beyond stale threshold (against the wall clock).
    pub fn is_stale(&self) -> bool {
        self.is_stale_at(wall_time())
    }

    /// Check if data is beyond stale threshold at `now`.
    pub fn is_stale_at(&self, now: f64) -> bool {
        now - self.cache_time > STALE_AFTER_S
    }

    pub fn to_dict(&self) -> Value {
        json!({
            "state": self.state,
            "locations": self.locations.iter().map(TruckParkingLocation::to_dict).collect::<Vec<_>>(),
            "last_updated": self.last_updated,
            "cache_time": self.cache_time,
            "source": self.source,
        })
    }
}

/// Read a JSON response body, gunzipping when the server compresses.
///
/// 511wi.gov gzips the map icon layer even without Accept-Encoding.
pub fn read_json_body(body: &[u8]) -> Result<Value, TransportError> {
    let mut body = body.to_vec();
    if body.starts_with(&[0x1f, 0x8b]) {
        let mut decoded = Vec::new();
        flate2::read::GzDecoder::new(&body[..])
            .read_to_end(&mut decoded)
            .map_err(|err| TransportError::new(format!("gzip: {err}")))?;
        body = decoded;
    }
    let text = std::str::from_utf8(&body).map_err(|err| TransportError::new(err.to_string()))?;
    Ok(serde_json::from_str(text)?)
}

/// Join 511wi.gov list rows with map icon coordinates by site id.
pub fn parse_wi511_locations(list_data: &Value, icons_data: &Value) -> Vec<TruckParkingLocation> {
    let mut coords: HashMap<String, (f64, f64)> = HashMap::new();
    if let Some(icon_items) = icons_data
        .as_object()
        .and_then(|icons| icons.get("item2"))
        .and_then(Value::as_array)
    {
        for item in icon_items {
            let Some(item) = item.as_object() else {
                continue;
            };
            let Some(location) = item.get("location").and_then(Value::as_array) else {
                continue;
            };
            if location.len() < 2 {
                continue;
            }
            if let (Some(lat), Some(lon)) = (to_f64(&location[0]), to_f64(&location[1])) {
                coords.insert(chain_str(item, &["itemId"], ""), (lat, lon));
            }
        }
    }

    let mut locations = Vec::new();
    let Some(rows) = list_data
        .as_object()
        .and_then(|list| list.get("data"))
        .and_then(Value::as_array)
    else {
        return locations;
    };
    for row in rows {
        let Some(row) = row.as_object() else {
            continue;
        };
        let location_id = str_or_empty(row.get("DT_RowId"));
        if location_id.is_empty() {
            continue;
        }
        let (latitude, longitude) = match coords.get(&location_id) {
            Some((lat, lon)) => (Some(*lat), Some(*lon)),
            None => (None, None),
        };
        // `int(capacity) if capacity is not None else None`: a count that
        // will not convert drops the row, as the Python except clause did.
        let count = |key: &str| -> Result<Option<i64>, ()> {
            match row.get(key) {
                None | Some(Value::Null) => Ok(None),
                Some(v) => to_i64(v).map(Some).ok_or(()),
            }
        };
        let (Ok(capacity), Ok(available)) =
            (count("totalParkingSpaces"), count("availableParkingSpaces"))
        else {
            log::debug!("Failed to parse WI truck parking row: bad count");
            continue;
        };
        let last_reported = match row.get("lastUpdated") {
            None | Some(Value::Null) => None,
            Some(v) => Some(py_str(v)),
        };
        locations.push(TruckParkingLocation {
            id: location_id,
            name: chain_str(row, &["name"], ""),
            location: chain_str(row, &["roadway"], ""),
            capacity,
            available,
            latitude,
            longitude,
            open: chain_str(row, &["open"], "Yes").to_lowercase() != "no",
            last_reported,
            ..TruckParkingLocation::default()
        });
    }
    locations
}

/// Parse parking locations from API response.
///
/// This is a reference implementation for Ohio OHGO TPIMS. Other states will
/// need their own parsers as API formats vary.
pub fn parse_locations(data: &Value, _state: &str) -> Vec<TruckParkingLocation> {
    // Ohio OHGO TPIMS format parsing
    data.get("truckParking")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(TruckParkingLocation::from_dict)
                .collect()
        })
        .unwrap_or_default()
}

#[derive(Default)]
struct ProviderState {
    cache: HashMap<String, ParkingData>,
    failed_until: HashMap<String, f64>,
}

#[derive(Clone)]
struct Fetcher {
    transport: Arc<dyn HttpTransport>,
    clock: Clock,
    user_agent: String,
}

impl Fetcher {
    fn now(&self) -> f64 {
        (self.clock)()
    }

    /// Fetch parking data from the state's TPIMS API.
    fn fetch_from_api(&self, state: &str) -> Result<ParkingData, TransportError> {
        let api_config = tpims_api(state).ok_or_else(|| TransportError::new("unknown state"))?;
        let locations = if api_config.parser == "wi511" {
            self.fetch_wi511_locations(state)?
        } else {
            let url = format!("{}{}", api_config.base_url, api_config.parking_endpoint);
            let data = self.transport.get_json(
                &url,
                &[
                    ("User-Agent", self.user_agent.as_str()),
                    ("Accept", "application/json"),
                ],
                FETCH_TIMEOUT_S,
            )?;
            parse_locations(&data, state)
        };
        let now = self.now();
        Ok(ParkingData::new(
            state,
            locations,
            now,
            now,
            api_config.name,
        ))
    }

    /// Fetch and join the two 511wi.gov TPIMS endpoints.
    ///
    /// The list endpoint is a DataTables-style form post that returns site
    /// names and live counts but no coordinates; the map icon layer returns
    /// the coordinates keyed by the same site ids.
    fn fetch_wi511_locations(
        &self,
        state: &str,
    ) -> Result<Vec<TruckParkingLocation>, TransportError> {
        let api_config = tpims_api(state).ok_or_else(|| TransportError::new("unknown state"))?;
        let base_url = api_config.base_url;
        let body = urlencode(&[
            ("draw", "1"),
            ("start", "0"),
            ("length", "500"),
            ("lang", "en"),
        ]);
        let list_bytes = self.transport.post(
            &format!("{base_url}{}", api_config.parking_endpoint),
            body.as_bytes(),
            &[
                ("User-Agent", self.user_agent.as_str()),
                ("Accept", "application/json"),
                ("Content-Type", "application/x-www-form-urlencoded"),
            ],
            FETCH_TIMEOUT_S,
        )?;
        let list_data = read_json_body(&list_bytes)?;
        let icons_bytes = self.transport.get(
            &format!("{base_url}{}", api_config.icons_endpoint.unwrap_or("")),
            &[
                ("User-Agent", self.user_agent.as_str()),
                ("Accept", "application/json"),
            ],
            FETCH_TIMEOUT_S,
        )?;
        let icons_data = read_json_body(&icons_bytes)?;
        Ok(parse_wi511_locations(&list_data, &icons_data))
    }
}

/// Cached, non-blocking source of real-time truck parking data per state.
///
/// `request(state)` kicks off a background fetch for the specified state.
/// The current cached data (possibly stale or empty) is returned immediately
/// so the game never blocks on network I/O.
pub struct TruckParkingProvider {
    state: Arc<Mutex<ProviderState>>,
    fetcher: Fetcher,
    threaded: bool,
    workers: Mutex<Vec<JoinHandle<()>>>,
}

impl TruckParkingProvider {
    /// A provider over the given transport: wall clock, background threads.
    pub fn new(transport: Arc<dyn HttpTransport>) -> Self {
        Self {
            state: Arc::new(Mutex::new(ProviderState::default())),
            fetcher: Fetcher {
                transport,
                clock: wall_clock(),
                user_agent: DEFAULT_USER_AGENT.to_string(),
            },
            threaded: true,
            workers: Mutex::new(Vec::new()),
        }
    }

    /// A provider with no network behind it and inline fetches -- what
    /// `TruckParkingProvider()` means in the tests.
    pub fn offline() -> Self {
        Self::new(Arc::new(NoTransport)).with_threaded(false)
    }

    pub fn with_clock(mut self, clock: Clock) -> Self {
        self.fetcher.clock = clock;
        self
    }

    pub fn with_threaded(mut self, threaded: bool) -> Self {
        self.threaded = threaded;
        self
    }

    pub fn now(&self) -> f64 {
        self.fetcher.now()
    }

    /// A snapshot of the cache (`provider._cache`).
    pub fn cache(&self) -> HashMap<String, ParkingData> {
        lock_unpoisoned(&self.state).cache.clone()
    }

    /// Seed a cache entry directly (`provider._cache[state] = data`).
    pub fn seed_cache(&self, state: &str, data: ParkingData) {
        lock_unpoisoned(&self.state)
            .cache
            .insert(state.to_string(), data);
    }

    /// A snapshot of the retry cooldowns (`provider._failed_until`).
    pub fn failed_until(&self) -> HashMap<String, f64> {
        lock_unpoisoned(&self.state).failed_until.clone()
    }

    /// Put a state into retry cooldown until `until`.
    pub fn set_failed_until(&self, state: &str, until: f64) {
        lock_unpoisoned(&self.state)
            .failed_until
            .insert(state.to_string(), until);
    }

    /// Wait for every background fetch spawned so far (a test aid).
    pub fn join_background(&self) {
        let handles: Vec<JoinHandle<()>> = lock_unpoisoned(&self.workers).drain(..).collect();
        for handle in handles {
            let _ = handle.join();
        }
    }

    /// Request parking data for a state, returning cached data immediately.
    ///
    /// Spawns a background fetch if the cache is stale or empty. Returns the
    /// current cache entry (which may be empty on first request).
    pub fn request(&self, state: &str) -> ParkingData {
        // Normalize state key
        let state_key = state.to_lowercase().trim().to_string();
        let Some(api) = tpims_api(&state_key) else {
            // Most states have no TPIMS feed; rest-stop entries ask about
            // wherever the truck is, so this is routine rather than warning-worthy.
            log::debug!("State {state} not supported for truck parking data");
            return ParkingData::new(&state_key, Vec::new(), 0.0, 0.0, "unsupported");
        };
        let now = self.now();
        let cached = {
            let shared = lock_unpoisoned(&self.state);
            // Check if we're in a retry cooldown period
            if let Some(until) = shared.failed_until.get(&state_key) {
                if now < *until {
                    log::debug!("State {state} in retry cooldown, using cached data");
                    return shared
                        .cache
                        .get(&state_key)
                        .cloned()
                        .unwrap_or_else(|| self.empty_data(&state_key));
                }
            }
            // Check cache freshness
            let cached = shared.cache.get(&state_key).cloned();
            if let Some(cached) = &cached {
                if cached.is_fresh_at(now) {
                    return cached.clone();
                }
            }
            // no_api: never fetch, but honour any (test-seeded) cache entry
            if api.parser == "no_api" {
                return cached.unwrap_or_else(|| self.empty_data(&state_key));
            }
            cached
        };
        // Spawn background fetch
        self.spawn_fetch(state_key.clone());
        // Return current cache (possibly stale or empty)
        cached.unwrap_or_else(|| self.empty_data(&state_key))
    }

    /// Create an empty parking data object for a state.
    pub fn empty_data(&self, state: &str) -> ParkingData {
        ParkingData::new(state, Vec::new(), 0.0, 0.0, "empty")
    }

    /// Spawn a background fetch (or run it inline when not threaded).
    fn spawn_fetch(&self, state: String) {
        let fetcher = self.fetcher.clone();
        let shared = Arc::clone(&self.state);
        let job = move || {
            match fetcher.fetch_from_api(&state) {
                Ok(data) => {
                    let mut guard = lock_unpoisoned(&shared);
                    guard.cache.insert(state.clone(), data);
                    guard.failed_until.remove(&state); // Clear retry cooldown
                }
                Err(err) => {
                    log::warn!("Failed to fetch parking data for {state}: {err}");
                    let mut guard = lock_unpoisoned(&shared);
                    guard
                        .failed_until
                        .insert(state.clone(), fetcher.now() + RETRY_AFTER_S);
                }
            }
        };
        if self.threaded {
            let handle = std::thread::spawn(job);
            lock_unpoisoned(&self.workers).push(handle);
        } else {
            job();
        }
    }

    /// Get parking locations within a specified radius of a point.
    pub fn get_locations_near(
        &self,
        state: &str,
        latitude: f64,
        longitude: f64,
        radius_mi: f64,
    ) -> Vec<TruckParkingLocation> {
        let parking_data = self.request(state);
        parking_data
            .locations
            .into_iter()
            .filter(|location| match (location.latitude, location.longitude) {
                (Some(lat), Some(lon)) => {
                    // Simple distance calculation (approximate)
                    haversine_distance(latitude, longitude, lat, lon) <= radius_mi
                }
                _ => false,
            })
            .collect()
    }

    /// Get available parking locations within a specified radius of a point.
    ///
    /// Filters for locations that are open and have available spaces.
    pub fn get_available_locations_near(
        &self,
        state: &str,
        latitude: f64,
        longitude: f64,
        radius_mi: f64,
    ) -> Vec<TruckParkingLocation> {
        self.get_locations_near(state, latitude, longitude, radius_mi)
            .into_iter()
            .filter(|loc| loc.open && loc.available.is_some_and(|a| a > 0))
            .collect()
    }
}

#[cfg(test)]
mod tests;
