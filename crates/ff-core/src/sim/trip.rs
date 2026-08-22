//! Trip simulation: progress along a route, grades, zones, stops, and events
//! (port of `freight_fate/sim/trip.py`).
//!
//! Python's `Trip` mixed in `TripRoadEventMixin`, `TripTrafficMixin` and
//! `EnforcementPostMixin`; here it is ONE struct defined in this file with
//! every field any of them touched, and `impl Trip` blocks in
//! `trip_road_events`, `trip_traffic` and `enforcement_posts` for the former
//! mixin methods. This file holds the struct, its construction and the clock;
//! the rest of `trip.py` is split by section into the `trip/` submodules
//! (`lookups`, `placement`, `zones`, `limits`, `update`).

use std::collections::{HashMap, HashSet};
use std::sync::Arc;

use crate::data::curves::RouteCurve;
use crate::data::world::{get_world, World};
use crate::data::world_models::{City, Leg, Route};
use crate::pyfmt::round_py_int;
use crate::pyrandom::PyRandom;
use crate::sim::enforcement_posts::EnforcementPost;
use crate::sim::road_event_pacing::RoadEventBreather;
use crate::sim::timezones::{appointment_text, city_zone, zone_for, HasLocation, TimeZone};
use crate::sim::traffic_manager::TrafficManager;
use crate::sim::trip_models::*;
use crate::sim::trip_route_helpers::stop_offset_for_direction;
use crate::sim::trip_traffic::TrafficProvider;
use crate::sim::truck_parking::TruckParkingProvider;
use crate::sim::vehicle::TruckState;
use crate::sim::weather::WeatherSystem;
use crate::units::{distance_unit, spoken_distance, spoken_gap, to_distance};

mod limits;
mod lookups;
mod placement;
mod update;
mod zones;

pub use lookups::LaneRun;

/// A stop is announced ("stop ahead") when it first comes within this many
/// miles ahead; `restore` seeds this SAME window as already-announced so a
/// resumed trip does not re-announce a stop called out before the save.
pub const STOP_AHEAD_LOOKAHEAD_MI: f64 = 5.0;
/// Street maneuvers announce at block scale, not highway scale.
pub const LOCAL_TURN_LOOKAHEAD_MI: f64 = 0.3;
/// A lane-count run shorter than this is collapsed into its neighbor.
pub const LANE_RUN_MIN_MI: f64 = 2.0;

// The reaction allowance covers hearing the call out loud, orienting by ear,
// and moving a foot to the brake -- audio-first reaction is slower than a
// sighted glance at a sign. Retuned from the owner's AZ-260 run (2026-07-19).
pub const PACENOTE_REACTION_S: f64 = 8.0;
pub const PACENOTE_BRAKE_MPH_PER_S: f64 = 2.5;
pub const PACENOTE_MARGIN_MPH: f64 = 3.0;
pub const PACENOTE_GENTLE_MARGIN_MPH: f64 = 8.0;
pub const PACENOTE_MIN_LEAD_MI: f64 = 0.33;
pub const PACENOTE_MAX_LEAD_MI: f64 = 1.5;
/// Never call a curve with less than this many seconds of travel at the
/// current speed.
pub const PACENOTE_LEAD_FLOOR_S: f64 = 30.0;
/// A follower starting within this gap after a called curve rides that
/// call's "then left/right" tail INSTEAD of getting its own call.
pub const PACENOTE_LINK_GAP_MI: f64 = 0.3;

/// A signalled exit gets the same real-time treatment as a hard bend, over
/// the road the truck genuinely needs to reach ramp speed, widened so the
/// clock is already real by the time anything has to start shedding.
pub const EXIT_APPROACH_DECOMPRESS_SLACK: f64 = 1.5;
/// And pacing climbs back over this many real seconds afterwards.
pub const EXIT_APPROACH_RELEASE_S: f64 = 3.0;

/// Only posted drops of at least this size get a warning.
pub const LIMIT_DROP_WARN_MIN_DELTA_MPH: f64 = 10.0;
/// The "drops to X in ..." pacenote lead, sized in REAL seconds at the
/// current pace (owner's live playtest, 2026-08-12).
pub const LIMIT_WARNING_REAL_S: f64 = 18.0;
pub const LIMIT_WARNING_MAX_LEAD_MI: f64 = 5.0;
/// A newly entered lower limit that ends within this span has its length
/// spoken ("for the next half a mile").
pub const LIMIT_SHORT_ZONE_MI: f64 = 2.5;
/// Below this there is no warning to give: the zone is already underfoot
/// (owner playtest, 2026-08-17).
pub const ZONE_WARNING_MIN_MI: f64 = 0.1;
/// A navigation lead closer than this is the near announcement's own moment.
pub const NAV_LEAD_MIN_MI: f64 = 0.1;
pub const LIMIT_SCAN_STRIDE_MI: f64 = 0.1;
pub const LIMIT_SCAN_MAX_MI: f64 = 3.0;

/// Why a drop is happening, for the arrival line only.
pub const LIMIT_REASON_LOOKAHEAD_MI: f64 = 1.5;
/// The only RoadStop types that actually cause a lower posting.
pub fn limit_reason_by_stop_type(stop_type: &str) -> Option<&'static str> {
    match stop_type {
        "weigh_station" => Some(" for the weigh station ahead"),
        _ => None,
    }
}
/// A "real hill" by the grade advisory's bar, checked against the average
/// over a forward scan rather than a single sample.
pub const LIMIT_DOWNGRADE_PCT: f64 = -3.5;
pub const LIMIT_DOWNGRADE_MIN_MI: f64 = 0.5;

/// below this the truck is parked or crawling: estimate at highway pace
pub const ETA_MIN_MPH: f64 = 15.0;

/// Colloquial short distance, mirroring `Settings.short_distance_text`
/// (quarter-mile steps, 100-meter steps) so the co-driver's limit calls
/// sound like her curve calls in either unit.
pub fn spoken_short_miles(miles: f64, imperial: bool) -> String {
    if imperial {
        if miles > 1.125 {
            return spoken_distance(miles, "mile");
        }
        let quarters = 1.max(round_py_int(miles * 4.0));
        return match quarters {
            1 => "a quarter mile".to_string(),
            2 => "half a mile".to_string(),
            3 => "three quarters of a mile".to_string(),
            4 => "one mile".to_string(),
            _ => spoken_distance(miles, "mile"),
        };
    }
    let km = miles * 1.609344;
    if km >= 0.95 {
        return spoken_distance(km, "kilometer");
    }
    let meters = 1.max(round_py_int(km * 10.0)) * 100;
    format!("{meters} meters")
}

/// Turn direction for the earcon, read out of a baked maneuver cue;
/// directionless legacy cues ("Turn onto") return "" and stay speech-only.
pub fn cue_direction(text: &str) -> &'static str {
    let lowered = text.to_lowercase();
    if lowered.contains("left") {
        return "left";
    }
    if lowered.contains("right") {
        return "right";
    }
    if lowered.starts_with("continue") || lowered.starts_with("start") {
        return "ahead";
    }
    ""
}

impl HasLocation for City {
    fn lat(&self) -> f64 {
        self.lat
    }
    fn lon(&self) -> f64 {
        self.lon
    }
    fn state(&self) -> &str {
        &self.state
    }
}

/// The keyword arguments of Python's `Trip(...)`, with the same defaults.
pub struct TripOptions {
    pub time_scale: f64,
    pub seed: Option<i64>,
    pub start_hour: f64,
    pub imperial: bool,
    pub hazard_scale: f64,
    pub career_hours: Option<f64>,
    pub traffic_provider: Option<Arc<dyn TrafficProvider>>,
    pub parking_provider: Option<Arc<TruckParkingProvider>>,
    pub bobtail: bool,
    pub destination_label: String,
    pub destination_approach_mi: Option<f64>,
    pub local_state: String,
    pub outbound: bool,
    /// The world the route names its cities in; the session world when None.
    pub world: Option<&'static World>,
}

impl Default for TripOptions {
    fn default() -> Self {
        TripOptions {
            time_scale: 20.0,
            seed: None,
            start_hour: 12.0,
            imperial: true,
            hazard_scale: 1.0,
            career_hours: None,
            traffic_provider: None,
            parking_provider: None,
            bobtail: false,
            destination_label: String::new(),
            destination_approach_mi: None,
            local_state: String::new(),
            outbound: false,
            world: None,
        }
    }
}

impl TripOptions {
    /// `Trip(route, truck, weather, seed=seed)`: the commonest test shape.
    pub fn seeded(seed: i64) -> Self {
        TripOptions {
            seed: Some(seed),
            ..Default::default()
        }
    }
}

/// One delivery run along a chosen route.
pub struct Trip {
    pub route: Route,
    pub truck: TruckState,
    pub weather: WeatherSystem,
    pub weather_source_status: &'static str,
    pub weather_location_refreshing: bool,
    pub weather_refresh_issue_announced: bool,
    pub time_scale: f64,
    pub hazard_scale: f64,
    /// clock hour of day at departure
    pub start_hour: f64,
    /// Absolute career clock at departure: carries the day of the week so
    /// commuter rush hour only forms on weekdays. None reads as a weekday.
    pub career_hours: Option<f64>,
    imperial: bool,
    pub traffic_provider: Option<Arc<dyn TrafficProvider>>,
    pub parking_provider: Option<Arc<TruckParkingProvider>>,
    /// Running tractor-only opens stops a combination vehicle cannot enter.
    pub bobtail: bool,
    /// On a facility-approach route the spoken facility name replaces the
    /// city in the status line.
    pub destination_label: String,
    /// Local approach road between the highway and this run's gate, from the
    /// destination facility's own approach record.
    pub destination_approach_mi: Option<f64>,
    /// Which state's vehicle code governs this run's local streets.
    pub local_state: String,
    /// Which END of a facility street chain the gate is at: driven outbound
    /// it is the FIRST thing you pass.
    pub outbound: bool,
    pub position_mi: f64,
    pub game_minutes: f64,
    pub finished: bool,
    /// The control the stop callout names for signalling an exit.
    pub exit_hint: String,
    /// Facilities named in full already this leg (research doc R6).
    pub facilities_named: HashSet<String>,
    pub facility_leg: usize,
    /// Deliberate waiting: armed when the player sets the parking brake.
    pub waiting: bool,
    /// set by the UI layer; gates inspections
    pub hos_violation: bool,
    pub seed: Option<i64>,
    pub rng: PyRandom,
    pub insp_rng: PyRandom,
    pub cond_rng: PyRandom,
    pub events: Vec<TripEvent>,
    pub leg_starts: Vec<f64>,
    pub city_mileposts: Vec<f64>,
    pub start_timezone: TimeZone,
    pub timezone_crossings: Vec<TimezoneCrossing>,
    /// The zone last announced (Python `_current_timezone`).
    pub last_timezone: TimeZone,
    pub stops: Vec<RoadStop>,
    pub toll_charges: Vec<TollCharge>,
    pub traffic_manager: TrafficManager,
    pub zones: Vec<Zone>,
    pub traffic_pressures: Vec<TrafficPressure>,
    pub navigation_cues: Vec<NavigationCue>,
    pub landmarks: Vec<RoadsideCallout>,
    pub billboards: Vec<RoadsideCallout>,
    pub chain_law_areas: Vec<(f64, f64)>,
    pub posts: Vec<EnforcementPost>,
    pub curves: Vec<RouteCurve>,
    /// True while the player is on an exit ramp that ends in a light or a
    /// stop sign; pins the clock to real time.
    pub controlled_ramp: bool,
    /// True while the ramp being driven ends at the delivery destination.
    pub dock_run_in: bool,
    /// A police stop is in progress: the clock stops compressing.
    pub pull_over_active: bool,
    /// True from a street corner's approach call until the corner resolves.
    pub controlled_turn: bool,
    /// Road left to an exit the driver has signalled for.
    pub exit_approach_mi: Option<f64>,
    pub exit_approach_release_s: f64,
    pub announced_chain_law: HashSet<String>,
    pub announced_curves: HashSet<String>,
    pub announced_lane_changes: HashSet<String>,
    /// lazily built, direction-aware
    pub lane_runs: Option<Vec<LaneRun>>,
    pub announced_landmarks: HashSet<String>,
    pub announced_billboards: HashSet<String>,
    /// RoadStop keys, never names.
    pub announced_stops: HashSet<String>,
    pub planned_stop_key: Option<String>,
    /// RoadStop key of the stop whose exit is currently signaled or being
    /// descended, published each tick by the driving state.
    pub exit_in_progress: Option<String>,
    /// While on an exit ramp the truck is off the highway: the mile marker
    /// holds and highway events pause.
    pub on_ramp: bool,
    pub last_moved_mi: f64,
    pub announced_cities: HashSet<usize>,
    pub announced_navigation: HashSet<String>,
    pub charged_tolls: HashSet<String>,
    /// The zone the truck was last known to be inside (Python
    /// `_active_zone`); compared by `zone_key`, the Rust stand-in for
    /// Python's object identity.
    pub entered_zone: Option<Zone>,
    /// Whether the current entered zone's ZONE_ENTER colour line has been
    /// spoken.
    pub zone_entry_spoken: bool,
    pub announced_speed_limit: Option<f64>,
    pub warned_limit_drops: Vec<f64>,
    /// Posted-limit values already spoken for the CURRENT posting.
    pub limit_drop_preannounced: Vec<f64>,
    pub event_breather: RoadEventBreather,
    pub announced_zone_warnings: HashSet<String>,
    /// Milepost of the zone the driver was last warned about.
    pub pending_zone_warning: Option<f64>,
    pub announced_traffic_pressures: HashSet<String>,
    pub announced_npc_traffic: HashSet<String>,
    pub announced_real_traffic: HashSet<String>,
    pub next_real_traffic_check_mi: f64,
    pub construction_zone_grace_start: HashMap<String, f64>,
    /// CB heads-ups are rationed to CB_CALLS_PER_RUN.
    pub cb_calls_made: usize,
    /// Posts that have already entered the lead window.
    pub heads_up_seen: HashSet<String>,
    pub hazard_check_mi: f64,
    pub inspection_check_mi: f64,
    pub conditions_check_mi: f64,
    pub traffic_warning_mi: f64,
    pub announced_enforcement: HashSet<String>,
    /// state name and code -> two-letter code, from the world's cities
    /// (Python built this lazily in `_region_at`).
    state_codes: HashMap<String, String>,
    pub world: &'static World,
}

impl Trip {
    pub fn new(
        route: Route,
        truck: TruckState,
        mut weather: WeatherSystem,
        opts: TripOptions,
    ) -> Self {
        let world = opts.world.unwrap_or_else(get_world);
        let weather_source_status = weather.source_status();
        let seed = opts.seed;
        let make_rng = |xor: Option<i64>| match seed {
            None => PyRandom::new_unseeded(),
            Some(s) => PyRandom::new_from_i64(match xor {
                None => s,
                Some(x) => s ^ x,
            }),
        };
        let leg_starts = compute_leg_starts(&route);
        let mut city_mileposts = leg_starts.clone();
        city_mileposts.push(route.miles());
        let mut state_codes = HashMap::new();
        for city in world.cities.values() {
            for name in [&city.state, &city.state_code] {
                if !name.is_empty() {
                    state_codes.insert(name.clone(), city.state_code.clone());
                }
            }
        }
        let start_hour = opts.start_hour;
        let hazard_scale = opts.hazard_scale.max(0.0);
        let traffic_manager = TrafficManager::new(
            &route,
            &leg_starts,
            seed,
            start_hour,
            hazard_scale,
            opts.imperial,
            truck.speed_mph(),
            weather.effects(),
        );
        let mut trip = Trip {
            route,
            truck,
            weather,
            weather_source_status,
            weather_location_refreshing: false,
            weather_refresh_issue_announced: false,
            time_scale: opts.time_scale,
            hazard_scale,
            start_hour,
            career_hours: opts.career_hours,
            imperial: opts.imperial,
            traffic_provider: opts.traffic_provider,
            parking_provider: opts.parking_provider,
            bobtail: opts.bobtail,
            destination_label: opts.destination_label,
            destination_approach_mi: opts.destination_approach_mi,
            local_state: opts.local_state,
            outbound: opts.outbound,
            position_mi: 0.0,
            game_minutes: 0.0,
            finished: false,
            exit_hint: "X".to_string(),
            facilities_named: HashSet::new(),
            facility_leg: 0,
            waiting: false,
            hos_violation: false,
            seed,
            rng: make_rng(None),
            insp_rng: make_rng(Some(0x5EED)),
            cond_rng: make_rng(Some(0xC0FFEE)),
            events: Vec::new(),
            leg_starts,
            city_mileposts,
            start_timezone: zone_for(0.0, 0.0, ""),
            timezone_crossings: Vec::new(),
            last_timezone: zone_for(0.0, 0.0, ""),
            stops: Vec::new(),
            toll_charges: Vec::new(),
            traffic_manager,
            zones: Vec::new(),
            traffic_pressures: Vec::new(),
            navigation_cues: Vec::new(),
            landmarks: Vec::new(),
            billboards: Vec::new(),
            chain_law_areas: Vec::new(),
            posts: Vec::new(),
            curves: Vec::new(),
            controlled_ramp: false,
            dock_run_in: false,
            pull_over_active: false,
            controlled_turn: false,
            exit_approach_mi: None,
            exit_approach_release_s: 0.0,
            announced_chain_law: HashSet::new(),
            announced_curves: HashSet::new(),
            announced_lane_changes: HashSet::new(),
            lane_runs: None,
            announced_landmarks: HashSet::new(),
            announced_billboards: HashSet::new(),
            announced_stops: HashSet::new(),
            planned_stop_key: None,
            exit_in_progress: None,
            on_ramp: false,
            last_moved_mi: 0.0,
            announced_cities: HashSet::new(),
            announced_navigation: HashSet::new(),
            charged_tolls: HashSet::new(),
            entered_zone: None,
            zone_entry_spoken: true,
            announced_speed_limit: None,
            warned_limit_drops: Vec::new(),
            limit_drop_preannounced: Vec::new(),
            event_breather: RoadEventBreather::new(),
            announced_zone_warnings: HashSet::new(),
            pending_zone_warning: None,
            announced_traffic_pressures: HashSet::new(),
            announced_npc_traffic: HashSet::new(),
            announced_real_traffic: HashSet::new(),
            next_real_traffic_check_mi: 0.0,
            construction_zone_grace_start: HashMap::new(),
            cb_calls_made: 0,
            heads_up_seen: HashSet::new(),
            hazard_check_mi: 5.0,
            inspection_check_mi: 10.0,
            conditions_check_mi: CONDITIONS_CHECK_MI,
            traffic_warning_mi: 1.0,
            announced_enforcement: HashSet::new(),
            state_codes,
            world,
        };
        // The same order as the Python constructor: every seeded draw below
        // happens in this sequence.
        let (start_timezone, crossings) = trip.compute_timezone_crossings();
        trip.start_timezone = start_timezone;
        trip.timezone_crossings = crossings;
        trip.last_timezone = start_timezone;
        trip.stops = trip.place_stops();
        trip.traffic_manager.spawn_initial_traffic();
        trip.zones = trip.place_zones();
        trip.traffic_pressures = trip.place_traffic_pressures();
        trip.navigation_cues = trip.build_navigation_cues();
        trip.landmarks = trip.place_landmarks();
        trip.billboards = trip.place_billboards();
        trip.chain_law_areas = trip.place_chain_law_areas();
        // Enforcement posts read the zones, the scales, the chain controls and
        // the city mileposts, so they are placed after all of them.
        trip.posts = trip.place_enforcement_posts();
        let posts = trip.posts.clone();
        trip.traffic_manager.add_enforcement_traffic(&posts);
        trip.curves = trip.place_curves();
        if trip.outbound {
            // Pulling OUT of a yard starts the truck already standing inside
            // the gate zone, and you do not "enter" a zone you begin in
            // (owner, 2026-08-21).
            trip.entered_zone = trip.active_zone_at(0.0);
        }
        // Start the first route cell's live-weather fetch now rather than on
        // the first update tick. Opportunistic only: a route whose cities are
        // not in the world cannot resolve a location yet.
        if let Some((weather_key, lat, lon)) = trip.weather_location() {
            trip.weather.set_city(&weather_key, lat, lon);
            if let Some(provider) = trip.weather.provider_mut() {
                provider.request(&weather_key, lat, lon);
            }
        }
        trip
    }

    /// The enforcement posts under the older name (the info key, the
    /// road-ahead readout and the traffic bubble still ask for patrols).
    pub fn patrols(&self) -> &[EnforcementPost] {
        &self.posts
    }

    pub fn set_patrols(&mut self, value: Vec<EnforcementPost>) {
        self.posts = value;
    }

    /// Clock compression for this frame: gentle while maneuvering, the full
    /// configured pacing at highway speed, and double pacing while parked
    /// with the brake set. Everything that converts real seconds to game
    /// time must read this, never `time_scale`.
    pub fn effective_time_scale(&self) -> f64 {
        let full = self.time_scale;
        if self.waiting && self.truck.parking_brake && self.truck.speed_mph() < 1.0 {
            // Deliberate waiting fast-forwards the compressed pacings. Real
            // time promises the wall clock, parked included.
            return if full > 1.0 {
                full * PARKED_TIME_SCALE_MULT
            } else {
                full
            };
        }
        if self.pull_over_active {
            // Lights behind you: the whole encounter runs on the real clock.
            return full.min(1.0);
        }
        if self.controlled_ramp || self.controlled_turn || self.dock_run_in {
            // A ramp ending in a light or a sign, a street corner, or the
            // dock run-in plays out in real time: the warning must buy human
            // reaction seconds, not compressed ones.
            return full.min(1.0);
        }
        if self.severe_curve_decompression() {
            // Same law for a hard bend (owner, 2026-07-24).
            return full.min(1.0);
        }
        if self.armed_exit_decompression() {
            // And for a signalled exit (Shane, 2026-08-15).
            return full.min(1.0);
        }
        if self.exit_approach_release_s > 0.0 {
            // Coming back up to pace after an approach, not snapping to it.
            let real = full.min(1.0);
            let eased = 1.0 - self.exit_approach_release_s / EXIT_APPROACH_RELEASE_S;
            return real + (full - real) * eased;
        }
        let floor = LOW_SPEED_TIME_SCALE.min(full);
        let ramp = (self.truck.speed_mph() / FULL_COMPRESSION_MPH).min(1.0);
        floor + (full - floor) * ramp
    }

    pub fn imperial(&self) -> bool {
        self.imperial
    }

    /// Python's `imperial` setter: the manager follows and the navigation
    /// cues are rebuilt in the new units.
    pub fn set_imperial(&mut self, value: bool) {
        if value == self.imperial {
            return;
        }
        self.imperial = value;
        self.traffic_manager.imperial = value;
        self.navigation_cues = self.build_navigation_cues();
    }

    pub fn npc_vehicles(&self) -> &[crate::sim::traffic_manager::TrafficVehicle] {
        &self.traffic_manager.vehicles
    }

    pub fn set_npc_vehicles(&mut self, vehicles: Vec<crate::sim::traffic_manager::TrafficVehicle>) {
        self.traffic_manager.vehicles = vehicles;
    }

    pub fn distance_text(&self, miles: f64) -> String {
        spoken_distance(
            to_distance(miles, self.imperial),
            distance_unit(self.imperial, false),
        )
    }

    /// How far to something still in front of the truck, never "0 miles":
    /// quarter-mile steps, or hundred-metre steps in metric (owner playtest,
    /// 2026-08-17).
    pub fn ahead_text(&self, miles: f64) -> String {
        spoken_short_miles(miles, self.imperial)
    }

    pub fn gap_text(&self, miles: f64) -> String {
        spoken_gap(miles, self.imperial)
    }

    pub fn speed_value(&self, mph: f64) -> String {
        crate::pyfmt::fmt_f(to_distance(mph, self.imperial), 0)
    }

    pub fn speed_text(&self, mph: f64) -> String {
        let units = if self.imperial {
            "miles per hour"
        } else {
            "kilometers per hour"
        };
        format!("{} {units}", self.speed_value(mph))
    }

    /// Linear lat/lon along a leg's route points at an A-to-B offset.
    pub fn leg_latlon_at(leg: &Leg, at_mi: f64) -> (f64, f64) {
        let pts = leg.route_points();
        if pts.is_empty() {
            return (0.0, 0.0);
        }
        let mut prev = &pts[0];
        for pt in pts {
            if pt.at_mi >= at_mi {
                let span = pt.at_mi - prev.at_mi;
                let fraction = if span > 0.0 {
                    (at_mi - prev.at_mi) / span
                } else {
                    0.0
                };
                return (
                    prev.lat + (pt.lat - prev.lat) * fraction,
                    prev.lon + (pt.lon - prev.lon) * fraction,
                );
            }
            prev = pt;
        }
        (prev.lat, prev.lon)
    }

    /// Interpolated road coordinate at a trip position.
    pub fn latlon_at(&self, mile: Option<f64>) -> (f64, f64) {
        let sample_mile = mile.unwrap_or(self.position_mi);
        let (leg_i, leg_start) = self.leg_at_mile(sample_mile);
        let leg = &self.route.legs[leg_i];
        let route_offset = (sample_mile - leg_start).clamp(0.0, leg.miles.max(0.0));
        let forward = self.route.cities[leg_i] == leg.a;
        let native_offset = if forward {
            route_offset
        } else {
            leg.miles - route_offset
        };
        if leg.route_points().len() >= 2 {
            return Self::leg_latlon_at(leg, native_offset);
        }
        // A leg with no baked geometry falls back to interpolating between
        // its two city coordinates -- but a synthetic route names cities the
        // world has never heard of. Answering "no coordinate" is right there.
        let (Some(start), Some(end)) = (
            self.route
                .cities
                .get(leg_i)
                .and_then(|c| self.world.cities.get(c)),
            self.route
                .cities
                .get(leg_i + 1)
                .and_then(|c| self.world.cities.get(c)),
        ) else {
            return (0.0, 0.0);
        };
        let fraction = if leg.miles > 0.0 {
            route_offset / leg.miles
        } else {
            0.0
        };
        (
            start.lat + (end.lat - start.lat) * fraction,
            start.lon + (end.lon - start.lon) * fraction,
        )
    }

    /// Stable 20-mile route cell, cut short at a state line: the state is
    /// part of the key, so crossing a line asks the provider afresh, and
    /// when the crossing happened INSIDE the current cell the truck's own
    /// position is used instead (Brandon, 2026-08-18). None for a route the
    /// world cannot place.
    pub fn weather_location(&self) -> Option<(String, f64, f64)> {
        if self.route.legs.is_empty() {
            return None;
        }
        let (leg_i, leg_start) = self.leg_at_mile(self.position_mi);
        let leg = &self.route.legs[leg_i];
        let route_offset = (self.position_mi - leg_start).clamp(0.0, leg.miles.max(0.0));
        let cell = (route_offset / 20.0).floor() as i64;
        let mut sample_mile = (leg_start + cell as f64 * 20.0).min(leg_start + leg.miles);
        let state = self.state_at(Some(self.position_mi));
        if !state.is_empty() && self.state_at(Some(sample_mile)) != state {
            sample_mile = self.position_mi;
        }
        let (lat, lon) = self.latlon_at(Some(sample_mile));
        let from = self.route.cities.get(leg_i)?;
        let to = self.route.cities.get(leg_i + 1)?;
        Some((format!("route:{from}:{to}:{cell}:{state}"), lat, lon))
    }

    /// (trip mile, zone) along the route, from city and route-point geometry.
    /// State crossings are sampled AT their exact mileposts (owner caught the
    /// Arizona-to-California flip ten miles late, 2026-07-22).
    pub fn timezone_samples(&self) -> Vec<(f64, TimeZone)> {
        let world = self.world;
        let mut samples: Vec<(f64, TimeZone)> = Vec::new();
        for (i, (start, leg)) in self
            .leg_starts
            .iter()
            .zip(self.route.legs.iter())
            .enumerate()
        {
            let forward = self.route.cities[i] == leg.a;
            if let Some(city) = world.cities.get(&self.route.cities[i]) {
                if city.lat != 0.0 || city.lon != 0.0 {
                    samples.push((*start, city_zone(city)));
                }
            }
            for pt in leg.route_points() {
                let offset = stop_offset_for_direction(pt.at_mi, leg.miles, forward);
                let zone = zone_for(pt.lat, pt.lon, &leg_state_at(leg, pt.at_mi));
                samples.push((start + offset, zone));
            }
            for crossing in leg.state_crossings() {
                let offset = stop_offset_for_direction(crossing.at_mi, leg.miles, forward);
                let (lat, lon) = Self::leg_latlon_at(leg, crossing.at_mi);
                let mut before = zone_for(lat, lon, &crossing.from_state);
                let mut after = zone_for(lat, lon, &crossing.state);
                // Traversed backward, the truck meets the crossing from the
                // other side: the A-to-B "to" state is what it is leaving.
                if !forward {
                    std::mem::swap(&mut before, &mut after);
                }
                samples.push(((start + offset - 0.05).max(0.0), before));
                samples.push((start + offset, after));
            }
        }
        if let Some(last) = self.route.cities.last().and_then(|c| world.cities.get(c)) {
            if last.lat != 0.0 || last.lon != 0.0 {
                samples.push((self.total_miles(), city_zone(last)));
            }
        }
        samples.sort_by(|a, b| a.0.partial_cmp(&b.0).expect("finite mileposts"));
        samples
    }

    /// Start zone plus the deduped clock-change mileposts for the route. A
    /// flip that reverts within `TIMEZONE_DWELL_MI` is a road hugging the
    /// boundary, not a crossing, and is dropped.
    pub fn compute_timezone_crossings(&self) -> (TimeZone, Vec<TimezoneCrossing>) {
        let samples = self.timezone_samples();
        if samples.is_empty() {
            return (zone_for(0.0, 0.0, ""), Vec::new());
        }
        let mut current = samples[0].1;
        let start = current;
        let mut crossings = Vec::new();
        for (i, &(mile, zone)) in samples.iter().enumerate() {
            if zone.key == current.key {
                continue;
            }
            let mut settled = true;
            for &(later_mile, later_zone) in &samples[i + 1..] {
                if later_mile - mile > TIMEZONE_DWELL_MI {
                    break;
                }
                if later_zone.key == current.key {
                    settled = false;
                    break;
                }
            }
            if settled {
                crossings.push(TimezoneCrossing {
                    at_mi: mile,
                    from_zone: current,
                    to_zone: zone,
                });
                current = zone;
            }
        }
        (start, crossings)
    }

    /// The time zone in effect at a trip milepost.
    pub fn timezone_at(&self, mile: f64) -> TimeZone {
        let mut zone = self.start_timezone;
        for crossing in &self.timezone_crossings {
            if crossing.at_mi <= mile {
                zone = crossing.to_zone;
            } else {
                break;
            }
        }
        zone
    }

    pub fn current_timezone(&self) -> TimeZone {
        self.timezone_at(self.position_mi)
    }

    pub fn destination_timezone(&self) -> TimeZone {
        self.timezone_at(self.total_miles())
    }

    /// The wall clock where the truck is right now; what the player hears.
    /// `current_hour` stays on the absolute (Eastern-reference) timeline for
    /// durations and deadlines; only speech and day/night feel go local.
    pub fn local_hour(&self) -> f64 {
        (self.current_hour() + self.current_timezone().offset_h).rem_euclid(24.0)
    }

    /// The local wall clock at departure, for day/night placement.
    pub fn local_start_hour(&self) -> f64 {
        (self.start_hour + self.start_timezone.offset_h).rem_euclid(24.0)
    }

    /// The delivery appointment as a receiver would quote it: the wall clock
    /// in the destination's zone. `zone` overrides where the appointment is
    /// read (a pickup drive's caller passes the delivery city's zone).
    pub fn deadline_clock_text(&self, deadline_game_h: f64, zone: Option<TimeZone>) -> String {
        let now = self.start_hour + self.game_minutes / 60.0;
        let remaining = deadline_game_h - self.game_minutes / 60.0;
        appointment_text(
            now,
            remaining,
            zone.unwrap_or_else(|| self.destination_timezone()),
        )
    }

    pub fn total_miles(&self) -> f64 {
        self.route.miles()
    }

    pub fn remaining_miles(&self) -> f64 {
        (self.total_miles() - self.position_mi).max(0.0)
    }

    pub fn current_hour(&self) -> f64 {
        (self.start_hour + self.game_minutes / 60.0).rem_euclid(24.0)
    }

    pub fn current_leg_index(&self) -> usize {
        for i in (0..self.route.legs.len()).rev() {
            if self.position_mi >= self.leg_starts[i] {
                return i;
            }
        }
        0
    }

    /// The world city the current leg heads toward; panics (Python:
    /// `KeyError`) for a synthetic city the world does not carry.
    pub fn current_target_city(&self) -> &City {
        let name = &self.route.cities[self.current_leg_index() + 1];
        self.world
            .cities
            .get(name)
            .unwrap_or_else(|| panic!("KeyError: {name:?}"))
    }

    pub fn current_region(&self) -> &str {
        &self.current_target_city().region
    }

    pub fn current_career_hours(&self) -> Option<f64> {
        self.career_hours
            .map(|hours| hours + self.game_minutes / 60.0)
    }

    pub fn is_weekend_now(&self) -> bool {
        match self.current_career_hours() {
            None => false,
            Some(hours) => crate::sim::season::is_weekend(hours),
        }
    }

    pub fn emit(
        &mut self,
        kind: TripEventKind,
        message: impl Into<crate::speech_text::SpokenMessage>,
        data: TripEventData,
    ) {
        self.events.push(TripEvent {
            kind,
            message: message.into(),
            data,
        });
    }
}

fn compute_leg_starts(route: &Route) -> Vec<f64> {
    let mut starts = Vec::new();
    let mut acc = 0.0;
    for leg in &route.legs {
        starts.push(acc);
        acc += leg.miles;
    }
    starts
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_spoken_short_miles_units() {
        assert_eq!(spoken_short_miles(0.2, true), "a quarter mile");
        assert_eq!(spoken_short_miles(0.5, true), "half a mile");
        assert_eq!(spoken_short_miles(0.5, false), "800 meters");
        assert_eq!(spoken_short_miles(1.0, true), "one mile");
        assert_eq!(spoken_short_miles(5.0, true), "5 miles");
    }

    #[test]
    fn cue_direction_reads_the_verb() {
        assert_eq!(cue_direction("Turn right onto Palm Street"), "right");
        assert_eq!(cue_direction("Continue onto Main Street"), "ahead");
        assert_eq!(cue_direction("Turn onto Elm"), "");
    }
}
