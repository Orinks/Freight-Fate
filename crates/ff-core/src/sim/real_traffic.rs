//! Real-time traffic data via state 511 APIs.
//!
//! Fetches current traffic conditions, construction zones, and incidents from
//! state department of transportation APIs, with graceful fallback to simulated
//! traffic when APIs are unavailable.  Response parsing lives in
//! `real_traffic_parsers`; this module owns the endpoint registry, caching,
//! and background fetching.
//!
//! Parsers (full format notes in `real_traffic_parsers`):
//!   `ohgo`   — Ohio OHGO native JSON format.
//!   `iteris` — Shared Iteris/INRIX-platform `/Events` endpoint format
//!              (no active states; kept for the shared helpers).
//!   `wzdx`   — Work Zone Data Exchange standard (GeoJSON FeatureCollection),
//!              camelCase and v4.x snake_case `core_details` layouts.
//!   `cars`   — Castle Rock CARS GraphQL platform (`POST /api/graphql`).
//!   `list511` — The 511 sites' own list-page JSON (`POST
//!              /List/GetData/<layer>`) joined with the map-pin locations
//!              (`GET /map/mapIcons/<layer>`).  Fills the incident gap on
//!              WZDx-only sites; keyless.
//!   `no_api` — Stub for states without a working public 511 API.  Returns
//!              empty data so the simulation falls back to procedurally
//!              generated construction zones without log warnings.
//!
//! Like the real_weather system, this is non-blocking with caching and graceful
//! fallback to simulated traffic when APIs are unavailable.
//!
//! Port of `freight_fate/sim/real_traffic.py`. `ff_core` carries no HTTP
//! stack: the provider talks to the network through the [`HttpTransport`]
//! trait the game crate implements (and tests fake), reads the clock through
//! an injected [`Clock`], and runs its fetches on `std::thread` when
//! `threaded` (the Python daemon-thread shape) or inline when not.

use std::collections::HashMap;
use std::fmt;
use std::sync::{Arc, Mutex, MutexGuard};
use std::thread::JoinHandle;
use std::time::{SystemTime, UNIX_EPOCH};

use serde_json::{json, Value};

use super::real_traffic_list511::{
    parse_list511_events, parse_list511_icon_locations, PinLocations,
};
use super::real_traffic_parsers::pyval::to_i64;
pub use super::real_traffic_parsers::TrafficEvent;
use super::real_traffic_parsers::{
    parse_cars_events, parse_construction_events, parse_events, parse_iteris_construction_events,
    parse_iteris_events, parse_wzdx_construction_events, parse_wzdx_events,
};

// ---- The network seam ----------------------------------------------------

/// Anything that went wrong reaching or decoding a feed: the network, an
/// HTTP status, a JSON body that would not parse, or a registry entry the
/// fetch cannot use. One family, because the provider treats every failure
/// the same way (log, back off `RETRY_AFTER_S`, keep serving the cache).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransportError {
    pub message: String,
}

impl TransportError {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }
}

impl fmt::Display for TransportError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for TransportError {}

impl From<serde_json::Error> for TransportError {
    fn from(err: serde_json::Error) -> Self {
        Self::new(format!("invalid JSON: {err}"))
    }
}

/// `json.loads(resp.read().decode("utf-8"))`.
pub fn decode_json_body(body: &[u8]) -> Result<Value, TransportError> {
    let text = std::str::from_utf8(body).map_err(|err| TransportError::new(err.to_string()))?;
    Ok(serde_json::from_str(text)?)
}

/// `urllib.parse.urlencode`: `quote_plus` on each key and value, joined
/// with `&`. Unreserved characters pass through, space becomes `+`, and
/// everything else is a percent-escaped UTF-8 byte.
pub fn urlencode(fields: &[(&str, &str)]) -> String {
    fn quote_plus(text: &str, out: &mut String) {
        for byte in text.bytes() {
            match byte {
                b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'_' | b'.' | b'-' | b'~' => {
                    out.push(byte as char)
                }
                b' ' => out.push('+'),
                _ => out.push_str(&format!("%{byte:02X}")),
            }
        }
    }
    let mut out = String::new();
    for (index, (key, value)) in fields.iter().enumerate() {
        if index > 0 {
            out.push('&');
        }
        quote_plus(key, &mut out);
        out.push('=');
        quote_plus(value, &mut out);
    }
    out
}

/// The HTTP the real-data providers need: a GET and a POST with a body,
/// each returning the raw response bytes. The JSON helpers are provided
/// on top so fakes implement only the two primitives. `timeout_s` is the
/// whole-request timeout the Python passed to `urlopen`.
pub trait HttpTransport: Send + Sync {
    fn get(
        &self,
        url: &str,
        headers: &[(&str, &str)],
        timeout_s: f64,
    ) -> Result<Vec<u8>, TransportError>;

    fn post(
        &self,
        url: &str,
        body: &[u8],
        headers: &[(&str, &str)],
        timeout_s: f64,
    ) -> Result<Vec<u8>, TransportError>;

    /// GET and decode a JSON document.
    fn get_json(
        &self,
        url: &str,
        headers: &[(&str, &str)],
        timeout_s: f64,
    ) -> Result<Value, TransportError> {
        decode_json_body(&self.get(url, headers, timeout_s)?)
    }

    /// POST a JSON body and decode the JSON response. The caller supplies
    /// the `Content-Type` header, as the Python requests did.
    fn post_json(
        &self,
        url: &str,
        body: &Value,
        headers: &[(&str, &str)],
        timeout_s: f64,
    ) -> Result<Value, TransportError> {
        let payload = serde_json::to_vec(body)?;
        decode_json_body(&self.post(url, &payload, headers, timeout_s)?)
    }

    /// POST a form-encoded body and decode the JSON response.
    fn post_form_json(
        &self,
        url: &str,
        fields: &[(&str, &str)],
        headers: &[(&str, &str)],
        timeout_s: f64,
    ) -> Result<Value, TransportError> {
        let payload = urlencode(fields);
        decode_json_body(&self.post(url, payload.as_bytes(), headers, timeout_s)?)
    }
}

/// A transport with no network behind it: every request fails. The
/// provider then behaves exactly as it does offline -- empty data, a retry
/// cooldown, the simulation's own traffic.
#[derive(Debug, Default, Clone, Copy)]
pub struct NoTransport;

impl HttpTransport for NoTransport {
    fn get(&self, url: &str, _: &[(&str, &str)], _: f64) -> Result<Vec<u8>, TransportError> {
        Err(TransportError::new(format!(
            "no transport configured for {url}"
        )))
    }

    fn post(
        &self,
        url: &str,
        _: &[u8],
        _: &[(&str, &str)],
        _: f64,
    ) -> Result<Vec<u8>, TransportError> {
        Err(TransportError::new(format!(
            "no transport configured for {url}"
        )))
    }
}

/// `time.time()`: seconds since the Unix epoch, as a float.
pub fn wall_time() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

/// An injectable clock returning seconds.
pub type Clock = Arc<dyn Fn() -> f64 + Send + Sync>;

/// The wall clock as a [`Clock`].
pub fn wall_clock() -> Clock {
    Arc::new(wall_time)
}

/// Lock a mutex, recovering the data if a worker panicked while holding it.
pub(crate) fn lock_unpoisoned<T>(mutex: &Mutex<T>) -> MutexGuard<'_, T> {
    mutex
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

pub const DEFAULT_USER_AGENT: &str =
    "FreightFate/1.1 (accessible trucking game; https://orinks.net)";

// ---- The endpoint registry ------------------------------------------------
// Lives in `real_traffic/state_apis.rs`; re-exported here so the module's
// surface matches the Python file.
mod state_apis;
pub use state_apis::{state_api, StateApi, STATE_APIS};

// Cache settings
pub const FETCH_TIMEOUT_S: f64 = 8.0;
/// 10 minutes - traffic changes faster than weather
pub const CACHE_TTL_S: f64 = 10.0 * 60.0;
/// Serve stale data for 30 minutes if fetches fail
pub const STALE_AFTER_S: f64 = 30.0 * 60.0;
/// Wait 2 minutes before retrying failed state
pub const RETRY_AFTER_S: f64 = 120.0;

// CARS GraphQL fetch shape.  Zoom 15 keeps the server from clustering the
// events (verified statewide against 511in.org: 484 uncollapsed events).
pub const CARS_GRAPHQL_ENDPOINT: &str = "/api/graphql";
pub const CARS_GRAPHQL_ZOOM: i64 = 15;
// list511 fetch shape.  The list endpoint is DataTables-style: it needs the
// paging fields and at least one column definition or it answers with an
// empty `data` array, and it caps a page at 100 rows regardless of the
// requested length (verified 2026-08-20 against 511ny.org: 107 incidents
// came back 100 + 7).  The page cap bounds a runaway feed, not a real state:
// the busiest live roster (NY) fits in two pages.
pub const LIST511_PAGE_LENGTH: usize = 100;
pub const LIST511_MAX_PAGES: usize = 10;

/// `LIST511_LIST_ENDPOINT = "/List/GetData/{layer}"`
pub fn list511_list_endpoint(layer: &str) -> String {
    format!("/List/GetData/{layer}")
}

/// `LIST511_ICONS_ENDPOINT = "/map/mapIcons/{layer}"`
pub fn list511_icons_endpoint(layer: &str) -> String {
    format!("/map/mapIcons/{layer}")
}

pub const CARS_MAP_FEATURES_QUERY: &str = concat!(
    "query MapFeatures($input: MapFeaturesArgs!) {",
    " mapFeaturesQuery(input: $input) {",
    " mapFeatures {",
    " bbox title tooltip uri",
    " features { id geometry properties }",
    " ... on Event { priority }",
    " __typename",
    " } error { message type } } }"
);

/// Current traffic conditions for a state or region.
#[derive(Debug, Clone, PartialEq)]
pub struct TrafficData {
    pub state: String,
    pub events: Vec<TrafficEvent>,
    pub last_updated: f64,
    pub cache_time: f64,
    pub source: String,
}

impl TrafficData {
    pub fn new(
        state: &str,
        events: Vec<TrafficEvent>,
        last_updated: f64,
        cache_time: f64,
        source: &str,
    ) -> Self {
        Self {
            state: state.to_string(),
            events,
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
            "events": self.events.iter().map(TrafficEvent::to_dict).collect::<Vec<_>>(),
            "last_updated": self.last_updated,
            "cache_time": self.cache_time,
            "source": self.source,
        })
    }
}

#[derive(Default)]
struct ProviderState {
    cache: HashMap<String, TrafficData>,
    failed_until: HashMap<String, f64>,
}

/// The half of the provider a background fetch needs: transport, clock and
/// the identifying User-Agent.
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

    /// GET a JSON document with the standard headers and timeout.
    fn http_get_json(&self, url: &str) -> Result<Value, TransportError> {
        self.transport.get_json(
            url,
            &[
                ("User-Agent", self.user_agent.as_str()),
                ("Accept", "application/json"),
            ],
            FETCH_TIMEOUT_S,
        )
    }

    /// POST a form-encoded body and decode the JSON response.
    fn http_post_form_json(
        &self,
        url: &str,
        fields: &[(&str, &str)],
    ) -> Result<Value, TransportError> {
        self.transport.post_form_json(
            url,
            fields,
            &[
                ("User-Agent", self.user_agent.as_str()),
                ("Accept", "application/json"),
                ("Content-Type", "application/x-www-form-urlencoded"),
            ],
            FETCH_TIMEOUT_S,
        )
    }

    /// Fetch one layer of events from a CARS GraphQL deployment.
    ///
    /// Issues the MapFeatures query over the state's bounding box for the
    /// given layer slug; the slug decides whether the batch parses as
    /// construction or incidents.
    fn fetch_cars_events(
        &self,
        state: &str,
        layer_slug: &str,
        construction: bool,
    ) -> Result<Vec<TrafficEvent>, TransportError> {
        let api_config = state_api(state).ok_or_else(|| TransportError::new("unknown state"))?;
        let bounds = api_config
            .bounds
            .ok_or_else(|| TransportError::new(format!("{state} has no CARS bounds")))?;
        let parsed: Vec<f64> = bounds
            .split(',')
            .map(|v| v.trim().parse::<f64>())
            .collect::<Result<_, _>>()
            .map_err(|err| TransportError::new(format!("bad CARS bounds: {err}")))?;
        let [south, west, north, east] = parsed[..] else {
            return Err(TransportError::new("CARS bounds need four numbers"));
        };
        let payload = json!({
            "query": CARS_MAP_FEATURES_QUERY,
            "variables": {
                "input": {
                    "north": north,
                    "south": south,
                    "east": east,
                    "west": west,
                    "zoom": CARS_GRAPHQL_ZOOM,
                    "layerSlugs": [layer_slug],
                }
            },
        });
        let base = api_config.base_url.unwrap_or("");
        let data = self.transport.post_json(
            &format!("{base}{CARS_GRAPHQL_ENDPOINT}"),
            &payload,
            &[
                ("User-Agent", self.user_agent.as_str()),
                ("Accept", "application/json"),
                ("Content-Type", "application/json"),
            ],
            FETCH_TIMEOUT_S,
        )?;
        Ok(parse_cars_events(&data, state, construction))
    }

    /// Fetch one list layer from a list511 site and join in coordinates.
    ///
    /// Pages through `POST /List/GetData/<layer>` (the server caps a page
    /// at 100 rows), then reads `GET /map/mapIcons/<layer>` for the map
    /// pins' `id -> [lat, lon]`.  A pin fetch failure degrades to events
    /// without coordinates rather than losing the batch; the distance
    /// filters simply skip those.
    fn fetch_list511_events(
        &self,
        state: &str,
        layer: &str,
    ) -> Result<Vec<TrafficEvent>, TransportError> {
        let api_config = state_api(state).ok_or_else(|| TransportError::new("unknown state"))?;
        let base = api_config.base_url.unwrap_or("");

        let mut rows: Vec<Value> = Vec::new();
        for page in 0..LIST511_MAX_PAGES {
            let draw = (page + 1).to_string();
            let start = (page * LIST511_PAGE_LENGTH).to_string();
            let length = LIST511_PAGE_LENGTH.to_string();
            let data = self.http_post_form_json(
                &format!("{base}{}", list511_list_endpoint(layer)),
                &[
                    ("draw", draw.as_str()),
                    ("start", start.as_str()),
                    ("length", length.as_str()),
                    ("columns[0][data]", "description"),
                    ("columns[0][name]", "description"),
                    ("order[0][column]", "0"),
                    ("order[0][dir]", "asc"),
                    ("search[value]", ""),
                    ("search[regex]", "false"),
                ],
            )?;
            let Some(data) = data.as_object() else {
                break;
            };
            let Some(page_rows) = data.get("data").and_then(Value::as_array) else {
                break;
            };
            if page_rows.is_empty() {
                break;
            }
            rows.extend(page_rows.iter().filter(|r| r.is_object()).cloned());
            let total = data
                .get("recordsTotal")
                .and_then(to_i64)
                .unwrap_or(0)
                .max(0) as usize;
            if rows.len() >= total {
                break;
            }
        }

        let mut locations = PinLocations::new();
        match self.http_get_json(&format!("{base}{}", list511_icons_endpoint(layer))) {
            Ok(icons) => locations = parse_list511_icon_locations(&icons),
            Err(err) => {
                log::debug!("list511 map pins unavailable for {state}/{layer}: {err}");
            }
        }

        Ok(parse_list511_events(&rows, &locations, state))
    }

    /// Fetch traffic data from the state's API.
    fn fetch_from_api(&self, state: &str) -> Result<TrafficData, TransportError> {
        let api_config = state_api(state).ok_or_else(|| TransportError::new("unknown state"))?;
        let parser = api_config.parser;
        let events = if parser == "cars" {
            self.fetch_cars_events(state, api_config.events_endpoint.unwrap_or(""), false)?
        } else if parser == "list511" {
            self.fetch_list511_events(state, api_config.events_endpoint.unwrap_or(""))?
        } else {
            let url = format!(
                "{}{}",
                api_config.base_url.unwrap_or(""),
                api_config.events_endpoint.unwrap_or("")
            );
            let data = self.http_get_json(&url)?;
            if parser == "iteris" {
                parse_iteris_events(&data, state)
            } else if parser == "wzdx" {
                parse_wzdx_events(&data, state)
            } else {
                parse_events(&data, state)
            }
        };
        let now = self.now();
        Ok(TrafficData::new(state, events, now, now, api_config.name))
    }

    /// Fetch construction data from the state's construction endpoint.
    ///
    /// `construction_parser` overrides `parser` for states whose work
    /// zones live on a different platform than their incidents (the
    /// list511 states keep their WZDx work-zone feed).
    fn fetch_construction_from_api(&self, state: &str) -> Result<TrafficData, TransportError> {
        let api_config = state_api(state).ok_or_else(|| TransportError::new("unknown state"))?;
        let parser = api_config.construction_parser.unwrap_or(api_config.parser);
        let events = if parser == "cars" {
            self.fetch_cars_events(state, api_config.construction_endpoint.unwrap_or(""), true)?
        } else {
            let url = format!(
                "{}{}",
                api_config.base_url.unwrap_or(""),
                api_config.construction_endpoint.unwrap_or("")
            );
            let data = self.http_get_json(&url)?;
            if parser == "iteris" {
                parse_iteris_construction_events(&data, state)
            } else if parser == "wzdx" {
                parse_wzdx_construction_events(&data, state)
            } else {
                parse_construction_events(&data, state)
            }
        };
        let now = self.now();
        Ok(TrafficData::new(state, events, now, now, api_config.name))
    }
}

/// Cached, non-blocking source of real-time traffic data per state.
///
/// `request(state)` kicks off a background fetch for the specified state.
/// The current cached data (possibly stale or empty) is returned immediately
/// so the game never blocks on network I/O.
pub struct RealTrafficProvider {
    state: Arc<Mutex<ProviderState>>,
    fetcher: Fetcher,
    threaded: bool,
    workers: Mutex<Vec<JoinHandle<()>>>,
}

impl RealTrafficProvider {
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

    /// A provider with no network behind it and inline (synchronous)
    /// fetches -- what `RealTrafficProvider()` means in the tests.
    pub fn offline() -> Self {
        Self::new(Arc::new(NoTransport)).with_threaded(false)
    }

    /// Replace the clock (`time.time()` in the Python).
    pub fn with_clock(mut self, clock: Clock) -> Self {
        self.fetcher.clock = clock;
        self
    }

    /// Run fetches on a `std::thread` (true, the Python daemon-thread shape)
    /// or inline on the calling thread (false, for deterministic tests).
    pub fn with_threaded(mut self, threaded: bool) -> Self {
        self.threaded = threaded;
        self
    }

    /// The provider's idea of now.
    pub fn now(&self) -> f64 {
        self.fetcher.now()
    }

    /// A snapshot of the cache (`provider._cache`).
    pub fn cache(&self) -> HashMap<String, TrafficData> {
        lock_unpoisoned(&self.state).cache.clone()
    }

    /// Seed a cache entry directly (`provider._cache[key] = data`); the
    /// construction cache for a state lives under `"<state>:construction"`.
    pub fn seed_cache(&self, key: &str, data: TrafficData) {
        lock_unpoisoned(&self.state)
            .cache
            .insert(key.to_string(), data);
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

    /// Wait for every background fetch spawned so far (a test aid; the game
    /// never blocks on these).
    pub fn join_background(&self) {
        let handles: Vec<JoinHandle<()>> = lock_unpoisoned(&self.workers).drain(..).collect();
        for handle in handles {
            let _ = handle.join();
        }
    }

    /// Request traffic data for a state, returning cached data immediately.
    ///
    /// Spawns a background fetch if the cache is stale or empty. Returns the
    /// current cache entry (which may be empty on first request).
    pub fn request(&self, state: &str) -> TrafficData {
        let state_key = state.to_lowercase().trim().to_string();
        let Some(api) = state_api(&state_key) else {
            log::debug!("State {state} not in STATE_APIS, returning empty data");
            return self.empty_data(&state_key);
        };
        let now = self.now();
        let cached = {
            let shared = lock_unpoisoned(&self.state);
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
        self.spawn_fetch(state_key.clone(), false);
        cached.unwrap_or_else(|| self.empty_data(&state_key))
    }

    /// Request construction-specific data for a state.
    ///
    /// Returns cached data immediately; spawns a background fetch to the
    /// construction endpoint if stale. Like `request()`, never blocks.
    pub fn fetch_construction(&self, state: &str) -> TrafficData {
        let state_key = state.to_lowercase().trim().to_string();
        let Some(api) = state_api(&state_key) else {
            log::debug!("State {state} not in STATE_APIS, returning empty data");
            return self.empty_data(&state_key);
        };
        let cache_key = format!("{state_key}:construction");
        let now = self.now();
        let cached = {
            let shared = lock_unpoisoned(&self.state);
            if let Some(until) = shared.failed_until.get(&state_key) {
                if now < *until {
                    log::debug!("State {state} in retry cooldown, using cached construction data");
                    return shared
                        .cache
                        .get(&cache_key)
                        .cloned()
                        .unwrap_or_else(|| self.empty_data(&state_key));
                }
            }
            let cached = shared.cache.get(&cache_key).cloned();
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
        self.spawn_fetch(state_key.clone(), true);
        cached.unwrap_or_else(|| self.empty_data(&state_key))
    }

    /// Spawn a background fetch (or run it inline when not threaded).
    fn spawn_fetch(&self, state: String, construction: bool) {
        let fetcher = self.fetcher.clone();
        let shared = Arc::clone(&self.state);
        let job = move || run_fetch(&fetcher, &shared, &state, construction);
        if self.threaded {
            let handle = std::thread::spawn(job);
            lock_unpoisoned(&self.workers).push(handle);
        } else {
            job();
        }
    }

    /// Get construction events near a route's geometry.
    ///
    /// Filters construction events to those within `radius_mi` of any
    /// route point, and optionally matching the given road name.
    pub fn get_construction_near_route(
        &self,
        state: &str,
        route_points: &[(f64, f64)],
        road_name: Option<&str>,
        radius_mi: f64,
    ) -> Vec<TrafficEvent> {
        let construction_data = self.fetch_construction(state);
        if construction_data.events.is_empty() || route_points.is_empty() {
            return Vec::new();
        }
        // Only consider construction-type events
        let mut nearby = Vec::new();
        for event in construction_data
            .events
            .into_iter()
            .filter(|e| e.event_type == "construction")
        {
            let (Some(lat), Some(lon)) = (event.latitude, event.longitude) else {
                continue;
            };
            // Check if this event is on the requested road
            if let Some(road_name) = road_name.filter(|r| !r.is_empty()) {
                if !event.road_name.is_empty() && !road_name_matches(&event.road_name, road_name) {
                    continue;
                }
            }
            // Check proximity to any route point
            if route_points
                .iter()
                .any(|(rlat, rlon)| haversine_distance(*rlat, *rlon, lat, lon) <= radius_mi)
            {
                nearby.push(event);
            }
        }
        nearby
    }

    /// Create an empty traffic data object for a state.
    pub fn empty_data(&self, state: &str) -> TrafficData {
        TrafficData::new(state, Vec::new(), 0.0, 0.0, "empty")
    }

    /// Get traffic events within a specified radius of a point.
    ///
    /// This is a simple distance filter. For production use, consider using
    /// proper geospatial queries.
    pub fn get_events_near(
        &self,
        state: &str,
        latitude: f64,
        longitude: f64,
        radius_mi: f64,
    ) -> Vec<TrafficEvent> {
        let traffic_data = self.request(state);
        traffic_data
            .events
            .into_iter()
            .filter(|event| match (event.latitude, event.longitude) {
                (Some(lat), Some(lon)) => {
                    // Simple distance calculation (approximate)
                    haversine_distance(latitude, longitude, lat, lon) <= radius_mi
                }
                _ => false,
            })
            .collect()
    }
}

/// One fetch, run on a worker thread or inline: on success the cache entry
/// replaces the old one and the cooldown clears; on failure the state goes
/// into `RETRY_AFTER_S` cooldown.
fn run_fetch(fetcher: &Fetcher, shared: &Mutex<ProviderState>, state: &str, construction: bool) {
    let (result, cache_key, what) = if construction {
        (
            fetcher.fetch_construction_from_api(state),
            format!("{state}:construction"),
            "construction data",
        )
    } else {
        (
            fetcher.fetch_from_api(state),
            state.to_string(),
            "traffic data",
        )
    };
    match result {
        Ok(data) => {
            let mut guard = lock_unpoisoned(shared);
            guard.cache.insert(cache_key, data);
            guard.failed_until.remove(state); // Clear retry cooldown
        }
        Err(err) => {
            log::warn!("Failed to fetch {what} for {state}: {err}");
            let mut guard = lock_unpoisoned(shared);
            guard
                .failed_until
                .insert(state.to_string(), fetcher.now() + RETRY_AFTER_S);
        }
    }
}

/// Check if an API road name matches a route's highway designation.
///
/// Handles formats like "I-77" vs "I 77" vs "Interstate 77" vs "77".
pub fn road_name_matches(api_road: &str, route_road: &str) -> bool {
    fn normalize_road(r: &str) -> String {
        // Remove spaces and dashes
        let mut r: String = r
            .trim()
            .to_uppercase()
            .chars()
            .filter(|c| !c.is_whitespace() && *c != '-')
            .collect();
        // Standardize prefixes
        if let Some(rest) = r.strip_prefix("INTERSTATE") {
            r = format!("I{rest}");
        }
        r
    }
    normalize_road(api_road) == normalize_road(route_road)
}

/// Calculate the great circle distance between two points in miles.
pub fn haversine_distance(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    // Convert to radians
    let (lat1, lon1, lat2, lon2) = (
        lat1.to_radians(),
        lon1.to_radians(),
        lat2.to_radians(),
        lon2.to_radians(),
    );
    // Haversine formula
    let dlat = lat2 - lat1;
    let dlon = lon2 - lon1;
    let a = (dlat / 2.0).sin().powi(2) + lat1.cos() * lat2.cos() * (dlon / 2.0).sin().powi(2);
    let c = 2.0 * a.sqrt().asin();
    let r = 3956.0; // Earth's radius in miles
    c * r
}

#[cfg(test)]
mod tests;
