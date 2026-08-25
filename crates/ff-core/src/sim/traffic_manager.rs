//! Small NPC traffic bubble around the player's truck (port of
//! `freight_fate/sim/traffic_manager.py`).
//!
//! The bubble is a window that travels with the truck. Vehicles are created
//! as the road reaches them and retired behind, which bounds the population
//! by the road around the player instead of by route length, and leaves
//! room for somebody coming up from behind and going past. Every draw is
//! keyed on the route and the seed so the same trip replayed puts the same
//! vehicle in the same place.

use std::collections::HashSet;

use sha2::{Digest, Sha256};

use crate::data::world_models::{Leg, Route};
use crate::pyfmt::fmt_f;
use crate::pyrandom::PyRandom;
use crate::sim::enforcement_posts::{seed_text, EnforcementPost};
use crate::sim::hos::is_night;
use crate::sim::trip_models::{
    corridor_speed_limit, hourly_volume_fraction, leg_aadt_at, leg_lane_count, leg_speed_limit_at,
    TrafficContext, DEFAULT_LEG_LANES, DIRECTIONAL_SPLIT, MAX_DRIVABLE_LANES, RUSH_HOUR_WINDOWS,
    TRAFFIC_LOOKAHEAD_MI,
};
use crate::sim::vehicle::{AIR_DENSITY, G as GRAVITY_MPS2, MPS_TO_MPH};
use crate::sim::weather::{effects, WeatherEffects, WeatherKind};
use crate::speech_text::{brake_lights_cue, merging_traffic_cue, slow_lead_cue};

mod vehicle;
pub use vehicle::{
    braking_cause_line, BrakingZone, TrafficSituation, TrafficVehicle, BRAKING_CAUSE_LINES,
};

// -- the rolling bubble ---------------------------------------------------------
pub const SPAWN_CELL_MI: f64 = 0.4;
/// Far enough back that a faster vehicle has room to close and pass.
pub const BUBBLE_BEHIND_MI: f64 = 2.4;
/// A little past TRAFFIC_LOOKAHEAD_MI so a lead is in place before it is
/// announced.
pub const BUBBLE_AHEAD_MI: f64 = 3.2;
/// Ceiling on the live population.
pub const MAX_BUBBLE_VEHICLES: usize = 28;
/// Clear air around the truck where nothing is created: a vehicle drawn
/// into being a few hundred feet ahead appeared out of nowhere.
pub const NO_SPAWN_AHEAD_MI: f64 = 1.1;
pub const NO_SPAWN_BEHIND_MI: f64 = 0.6;
/// How far into a run the bubble withholds the "merging" intent.
pub const MERGE_FREE_START_MI: f64 = 3.0;
/// How far past an interchange a vehicle can still be merging into you.
/// Merging is POSITIONAL (owner, 2026-08-19): it happens at interchanges,
/// and hard braking happens in congestion placed from real volumes.
pub const MERGE_WINDOW_MI: f64 = 0.45;
/// How far a bubble vehicle runs before it leaves the highway, drawn per
/// vehicle: nobody shares a whole corridor with you.
pub const EXIT_AFTER_MIN_MI: f64 = 2.5;
pub const EXIT_AFTER_MAX_MI: f64 = 11.0;

/// What each intent is doing relative to the road's posted limit. Relative
/// bands hold on a 75 corridor, a 55 two-lane and a 30 mph town street alike
/// (owner playtest, 2026-08-15).
pub fn traffic_speed_offsets_mph(intent: &str) -> (f64, f64) {
    match intent {
        "passing" => (3.0, 10.0),
        "cruising" => (-3.0, 5.0),
        "following" => (-10.0, -3.0),
        "merging" => (-18.0, -8.0),
        "braking" => (-22.0, -10.0),
        other => panic!("unknown traffic intent {other:?}"),
    }
}
/// The floor is a share of the limit, not one absolute number.
pub const TRAFFIC_MIN_SPEED_SHARE: f64 = 0.45;
pub const TRAFFIC_MIN_SPEED_MPH: f64 = 15.0;
/// A heavy truck out there is governed, like the player's is (ATRI: ~85% of
/// fleets run limiters, most commonly at 65). 65 is the MODE, not the only
/// setting, so each truck carries its own governor drawn from a band.
pub const GOVERNED_TRUCK_BAND_MPH: (f64, f64) = (62.0, 68.0);
/// A box truck is not a tractor-trailer, and drawing it from the band above was
/// reusing a reading about one class of vehicle for another. ATRI surveys
/// for-hire fleets running class 8 tractors; a straight truck is a different
/// machine on a different job, and FMCSA's limiter rulemaking reaches CMVs over
/// 26,000 pounds, which is class 7 and up rather than the class 5 and 6 units
/// most box trucks are. The checkable numbers for these are published rental
/// and vocational governors: U-Haul states a 55 mph maximum for its trucks,
/// Penske governs its rental fleet at 65. So the band is those two, which puts
/// a typical box truck BELOW a typical semi rather than level with one.
///
/// The behaviour that motivated looking: a box truck drawn at semi speed sat
/// in the right lane pacing the player exactly, so a driver who moved left to
/// get around one never got around it -- "I'm in the left lane and have been
/// for quite a while and this box truck is still in the right lane and has not
/// cleared" (Brandon, 2026-08-22). The band is not tuned to make the pass feel
/// good; it is what the published governors say, and the pass follows from it.
pub const GOVERNED_BOX_TRUCK_BAND_MPH: (f64, f64) = (55.0, 65.0);
/// Which classes are governed, and out of which band. A service vehicle is a
/// pickup or a van and is not governed at all, whatever it is towing.
pub const GOVERNED_BANDS: [(&str, (f64, f64)); 2] = [
    ("semi", GOVERNED_TRUCK_BAND_MPH),
    ("box truck", GOVERNED_BOX_TRUCK_BAND_MPH),
];
/// `tuple(GOVERNED_BANDS)`: the governed classes in the mapping's own order.
pub const GOVERNED_CLASSES: [&str; 2] = ["semi", "box truck"];

/// `GOVERNED_BANDS.get(vehicle_class)`.
pub fn governed_band(vehicle_class: &str) -> Option<(f64, f64)> {
    GOVERNED_BANDS
        .iter()
        .find(|(class, _)| *class == vehicle_class)
        .map(|(_, band)| *band)
}

// What actually separates trucks on a real interstate is the hills. A limiter
// is a ceiling, and on the flat every governed truck sits on its ceiling, so
// nothing overtakes anything -- the elephant race drivers complain about, and
// what Brandon met. On a grade the ceiling stops mattering: a loaded tractor
// has a fixed amount of power to spend on lifting 80,000 pounds, and its speed
// falls to whatever that buys. Trucks then string out by weight and power, and
// the light ones climb past the heavy ones. Modelling the limiter without
// modelling the hill leaves the road permanently flat-feeling even in the
// mountains, which is the realism gap under the complaint rather than the
// band being a few miles per hour off.
//
// Derived, not tabulated: the balance point where a truck's wheel power equals
// what drag, rolling resistance and the grade are taking from it, using the
// SAME physics and the same constants as the player's own truck
// (`vehicle::resistance_force` -- air density, Cd times frontal area, and a
// 0.0065 rolling coefficient). Weight and power are the class's real numbers:
// 80,000 lb at 450 hp for a loaded class 8, 26,000 lb at 300 hp for a class 6
// straight truck, both through 85 percent driveline efficiency.
//
// It lands where the road says it should -- a loaded semi at about 26 mph on a
// sustained 6 percent, in the 25-to-35 band a driver would expect, and 44 on a
// 3 percent -- which is the check on the model rather than a target it was
// fitted to.
pub const CLIMB_MODEL: [(&str, (f64, f64)); 2] = [
    // class: (gross kg, wheel kilowatts)
    ("semi", (36_287.0, 450.0 * 0.7457 * 0.85)),
    ("box truck", (11_793.0, 300.0 * 0.7457 * 0.85)),
];
/// The player truck's own aero and rolling numbers (`TruckSpecs` defaults).
pub const CLIMB_DRAG_CD: f64 = 0.65;
pub const CLIMB_FRONTAL_AREA_M2: f64 = 10.0;
pub const CLIMB_ROLLING: f64 = 0.0065;
/// Below this the hill is not what is holding the truck back -- the limiter is.
pub const CLIMB_MIN_GRADE_PCT: f64 = 0.5;

/// Steady climbing speed for a heavy class on a sustained grade.
///
/// The speed at which the class's wheel power exactly covers drag, rolling
/// resistance and the climb. Downgrades and the flat return a number well
/// above any limiter, so the caller's `min` leaves the governor in charge
/// and only a real hill ever binds.
///
/// (Python memoises this with `lru_cache`; the bisection is sixty float
/// iterations, so the Rust side simply recomputes it.)
pub fn climb_speed_mph(vehicle_class: &str, grade_pct: f64) -> f64 {
    let model = CLIMB_MODEL
        .iter()
        .find(|(class, _)| *class == vehicle_class)
        .map(|(_, model)| *model);
    let Some((mass_kg, power_kw)) = model.filter(|_| grade_pct >= CLIMB_MIN_GRADE_PCT) else {
        return f64::INFINITY;
    };
    let power_w = power_kw * 1000.0;
    let grade = grade_pct / 100.0;

    // Watts to hold `v` metres per second against drag, rolling and the
    // climb -- the same three terms as `vehicle::resistance_force`.
    let power_needed_at = |v: f64| -> f64 {
        let force = 0.5 * AIR_DENSITY * CLIMB_DRAG_CD * CLIMB_FRONTAL_AREA_M2 * v * v
            + mass_kg * GRAVITY_MPS2 * CLIMB_ROLLING
            + mass_kg * GRAVITY_MPS2 * grade.atan().sin();
        force * v
    };

    let (mut low, mut high) = (0.5, 45.0); // m/s; bisection, monotonic in v
    for _ in 0..60 {
        let mid = (low + high) / 2.0;
        if power_needed_at(mid) > power_w {
            high = mid;
        } else {
            low = mid;
        }
    }
    low * MPS_TO_MPH
}

/// Used only where the route cannot answer for a mile at all.
pub const DEFAULT_LIMIT_MPH: f64 = 65.0;

pub struct TrafficManager {
    pub route: Route,
    pub leg_starts: Vec<f64>,
    pub seed: Option<i64>,
    pub start_hour: f64,
    pub hazard_scale: f64,
    pub imperial: bool,
    /// The player's road speed, mirrored by the trip before every call (the
    /// Python manager read it off the shared `truck` object).
    pub truck_speed_mph: f64,
    /// The weather's physics modifiers, mirrored the same way.
    pub weather_effects: WeatherEffects,
    pub vehicles: Vec<TrafficVehicle>,
    pub announced_vehicle_keys: HashSet<String>,
    /// Spawn cells the rolling bubble has already drawn for; used once.
    pub spawned_cells: HashSet<i64>,
    /// Whether `update` tops the window up. Off for a test or tool that
    /// assigns `vehicles` directly.
    pub rolling_bubble: bool,
    /// Time of day the density model should read, set from the trip each
    /// frame.
    pub hour: f64,
    /// Weekday or weekend, for the hourly volume curve.
    pub weekend: bool,
    /// Spans where traffic has a reason to be braking, set by the trip.
    pub braking_zones: Vec<BrakingZone>,
    /// The driving state mirrors the player's discrete lane here each frame.
    pub player_lane: i64,
    /// The lane a tap-change is moving INTO, or None the rest of the time.
    pub player_lane_target: Option<i64>,
}

impl TrafficManager {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        route: &Route,
        leg_starts: &[f64],
        seed: Option<i64>,
        start_hour: f64,
        hazard_scale: f64,
        imperial: bool,
        truck_speed_mph: f64,
        weather_effects: WeatherEffects,
    ) -> Self {
        TrafficManager {
            route: route.clone(),
            leg_starts: leg_starts.to_vec(),
            seed,
            start_hour,
            hazard_scale,
            imperial,
            truck_speed_mph,
            weather_effects,
            vehicles: Vec::new(),
            announced_vehicle_keys: HashSet::new(),
            spawned_cells: HashSet::new(),
            rolling_bubble: true,
            hour: start_hour,
            weekend: false,
            braking_zones: Vec::new(),
            player_lane: 0,
            player_lane_target: None,
        }
    }

    /// A manager over an empty road with default clear weather, the shape
    /// the Python tests built with `TrafficManager.__new__` for the pure
    /// helpers.
    pub fn bare(route: &Route, leg_starts: &[f64]) -> Self {
        TrafficManager::new(
            route,
            leg_starts,
            Some(0),
            8.0,
            1.0,
            true,
            0.0,
            effects(WeatherKind::Clear),
        )
    }

    /// Refresh the mirrored truck speed and weather before a call.
    pub fn sync_environment(&mut self, truck_speed_mph: f64, weather_effects: WeatherEffects) {
        self.truck_speed_mph = truck_speed_mph;
        self.weather_effects = weather_effects;
    }

    pub fn seed_key(&self) -> String {
        let route_key = self
            .route
            .cities
            .iter()
            .zip(self.route.legs.iter())
            .map(|(city, leg)| format!("{city}:{}:{}", leg.highway, fmt_f(leg.miles, 1)))
            .collect::<Vec<_>>()
            .join("|");
        format!("traffic-manager:{}:{route_key}", seed_text(self.seed))
    }

    pub fn rng(&self) -> PyRandom {
        PyRandom::new_from_sha256_prefix16(&self.seed_key())
    }

    pub fn rush_hour_traffic_bias(&self, leg: &Leg) -> f64 {
        // self.hour, not start_hour: a run that departs at 04:00 drives into
        // the morning rush.
        let hour = self.hour.rem_euclid(24.0);
        if !RUSH_HOUR_WINDOWS
            .iter()
            .any(|(start, end)| *start <= hour && hour < *end)
        {
            return 0.0;
        }
        if leg.checkpoints().is_empty() {
            0.06
        } else {
            0.14
        }
    }

    /// How much of this road is carrying somebody, 0 to 1.
    ///
    /// Read from the road's real traffic where the HPMS bake covers it:
    /// AADT, times this hour's share of the day, times the peak direction's
    /// share, over the speed traffic is moving -- vehicles per mile in your
    /// direction, times the cell width. Arrivals along a road are Poisson, so
    /// P(at least one) is `1 - exp(-lambda)`. Deliberately reads nothing
    /// from `hazard_scale`: presence is not difficulty.
    pub fn leg_density(&self, leg: &Leg, night: bool, mile: Option<f64>) -> f64 {
        let Some((aadt, _lanes)) = self.aadt_at(leg, mile) else {
            // No bake here. The old class/metro shape, kept intact so an
            // uncovered leg drives exactly as it did.
            let metro_bias = if leg.checkpoints().is_empty() {
                0.0
            } else {
                0.18
            };
            let night_bias = if night { -0.08 } else { 0.0 };
            let rush_bias = self.rush_hour_traffic_bias(leg);
            return 0.86_f64
                .min(0.05_f64.max(0.22 + leg.miles / 900.0 + metro_bias + night_bias + rush_bias));
        };
        let share = hourly_volume_fraction(self.hour, self.weekend);
        let speed = self.truck_speed_mph.abs();
        let moving_mph = 25.0_f64.max(70.0_f64.min(if speed == 0.0 { 60.0 } else { speed }));
        let per_mile = aadt * share * DIRECTIONAL_SPLIT / moving_mph;
        let expected_in_cell = per_mile * SPAWN_CELL_MI;
        let occupied = 1.0 - (-expected_in_cell).exp();
        // Same floor and ceiling as before.
        0.86_f64.min(0.05_f64.max(occupied))
    }

    /// Baked (AADT, lanes) under a route mile, or None where none exists.
    pub fn aadt_at(&self, leg: &Leg, mile: Option<f64>) -> Option<(f64, i64)> {
        match mile {
            None => leg_aadt_at(leg, 0.0),
            Some(mile) => {
                let (at_leg, offset) = self.leg_and_offset_at(mile)?;
                leg_aadt_at(at_leg, offset)
            }
        }
    }

    pub fn weather_slowdown(&self) -> f64 {
        let effects = self.weather_effects;
        0.0_f64.max(
            14.0_f64
                .min((1.0 - effects.grip) * 20.0 + (3.0 - effects.visibility_mi).max(0.0) * 1.4),
        )
    }

    pub fn spawn_initial_traffic(&mut self) {
        let mut rng = self.rng();
        let mut vehicles: Vec<TrafficVehicle> = Vec::new();
        let night = is_night(self.start_hour);
        for (leg_index, (start, leg)) in self
            .leg_starts
            .iter()
            .zip(self.route.legs.iter())
            .enumerate()
        {
            if leg.miles < 35.0 {
                continue;
            }
            let density = self.leg_density(leg, night, None);
            let slots = 1.max((leg.miles / 85.0) as i64);
            for slot in 0..slots {
                if rng.random() > 0.92_f64.min(density + 0.18) {
                    continue;
                }
                let span = leg.miles / slots as f64;
                let low = 4.0_f64.max(slot as f64 * span + 8.0);
                let high = (leg.miles - 6.0).min((slot + 1) as f64 * span + 4.0);
                if high <= low {
                    continue;
                }
                // Where it is has to be settled BEFORE what it is doing:
                // merging and braking are positional (see MERGE_WINDOW_MI),
                // and this spawner used to hand them out anywhere on the
                // route. A vehicle on the brakes where nothing on the road
                // explains it has no cause line to give the driver either --
                // `braking_cause_line` answers with silence -- so the warning
                // came out as "Brake lights right ahead." and stopped there,
                // which is the invented phantom wave the bubble is supposed
                // to refuse.
                let position_mi = start + rng.uniform(low, high);
                let mut options = vec!["cruising", "following", "passing"];
                let mut weights = vec![3.0, 1.5, 1.1];
                if self.merge_plausible_at(position_mi) {
                    options.push("merging");
                    weights.push(1.2);
                }
                if self.braking_plausible_at(position_mi) {
                    options.push("braking");
                    weights.push(1.0);
                }
                let intent = choose(&mut rng, &options, &weights);
                let vehicle_class = choose(
                    &mut rng,
                    &["car", "box truck", "semi", "service vehicle"],
                    &[5.0, 1.4, 2.0, 0.3],
                );
                let (limit_offset, governor) =
                    Self::intent_speed_draw(intent, &mut rng, vehicle_class);
                let rush_slowdown = if self.rush_hour_traffic_bias(leg) != 0.0 {
                    rng.uniform(4.0, 10.0)
                } else {
                    0.0
                };
                let speed = self.road_speed_mph(position_mi, limit_offset, governor, rush_slowdown);
                // Passing traffic lives in the left lane where the road has
                // one; everyone else holds the right lane, where trucks are
                // supposed to be.
                let lane = self.intent_lane_at(intent, position_mi);
                // Nobody shares a whole corridor with you -- the same rule the
                // rolling bubble already applied. Without it the route's
                // opening population was permanent: a slow vehicle placed at
                // mile 300 was still in front of you at mile 400, and on a
                // one-lane road it never turned off and never could be passed.
                let exit_at = position_mi + rng.uniform(EXIT_AFTER_MIN_MI, EXIT_AFTER_MAX_MI);
                vehicles.push(
                    TrafficVehicle::new(
                        &format!("traffic:{leg_index}:{slot}:{intent}"),
                        position_mi,
                        speed,
                        speed,
                        -lane,
                        intent,
                        vehicle_class,
                    )
                    .with_lane(lane)
                    .with_exit_at(Some(exit_at))
                    .with_speed_draw(limit_offset, governor, rush_slowdown),
                );
            }
        }
        sort_by_position(&mut vehicles);
        self.vehicles = vehicles;
    }

    /// Give the roving posts a body in the traffic bubble. Only
    /// `roving_patrol` posts get one; a parked kind belongs to the
    /// enforcement layer's own cues. The intent is `patrolling`, not
    /// `cruising`, so the trooper pass-by sound can actually play.
    pub fn add_enforcement_traffic(&mut self, posts: &[EnforcementPost]) {
        let mut existing_keys: HashSet<String> =
            self.vehicles.iter().map(|v| v.key.clone()).collect();
        for post in posts {
            if post.kind != "roving_patrol" || !post.staffed {
                continue;
            }
            let key = format!("trooper:{}", post.id());
            if existing_keys.contains(&key) {
                continue;
            }
            // A roving patrol runs with traffic, which is the posted number.
            let speed = self.posted_limit_at(post.at_mi);
            self.vehicles.push(TrafficVehicle::new(
                &key,
                post.at_mi,
                speed,
                speed,
                0,
                "patrolling",
                "state trooper",
            ));
            existing_keys.insert(key);
        }
        sort_by_position(&mut self.vehicles);
    }

    pub fn lead_vehicle(&self, position_mi: f64, truck_speed_mph: f64) -> Option<TrafficContext> {
        // Mid-change, reason about the lane being entered, not the one being
        // left -- otherwise a lead in the origin lane keeps capping the
        // target for the whole maneuver.
        let lane = self.player_lane_target.unwrap_or(self.player_lane);
        let mut nearest: Option<(f64, &TrafficVehicle)> = None;
        for vehicle in &self.vehicles {
            if vehicle.lane != lane {
                continue;
            }
            let gap_mi = vehicle.position_mi - position_mi;
            if gap_mi < -vehicle.length_mi || gap_mi > TRAFFIC_LOOKAHEAD_MI {
                continue;
            }
            let context_gap_mi = gap_mi.max(0.0);
            if nearest.is_none_or(|(gap, _)| context_gap_mi < gap) {
                nearest = Some((context_gap_mi, vehicle));
            }
        }
        let (gap_mi, vehicle) = nearest?;
        let closing_mph = (truck_speed_mph - vehicle.speed_mph).max(0.0);
        Some(TrafficContext {
            lead: vehicle.clone(),
            gap_mi,
            closing_mph,
        })
    }

    pub fn gap_text(&self, miles: f64) -> String {
        if self.imperial {
            format!("{} miles", fmt_f(miles, 1))
        } else {
            format!("{} kilometers", fmt_f(miles * 1.609344, 1))
        }
    }

    pub fn speed_value(&self, mph: f64) -> String {
        if self.imperial {
            format!("{} miles per hour", fmt_f(mph, 0))
        } else {
            format!("{} kilometers per hour", fmt_f(mph * 1.609344, 0))
        }
    }

    /// The number alone, for the terse slot grammar's trailing speed.
    pub fn speed_bare(&self, mph: f64) -> String {
        if self.imperial {
            fmt_f(mph, 0)
        } else {
            fmt_f(mph * 1.609344, 0)
        }
    }

    /// Whether a vehicle here could be merging in from a ramp.
    pub fn merge_plausible_at(&self, mile: f64) -> bool {
        let Some((leg, offset)) = self.leg_and_offset_at(mile) else {
            return false;
        };
        leg.interchanges()
            .iter()
            .any(|ix| 0.0 <= offset - ix.at_mi && offset - ix.at_mi <= MERGE_WINDOW_MI)
    }

    /// Whether traffic here has a reason to be stopping hard: congestion
    /// placed from real volumes, or a ramp.
    pub fn braking_plausible_at(&self, mile: f64) -> bool {
        if self
            .braking_zones
            .iter()
            .any(|z| z.start_mi <= mile && mile <= z.end_mi)
        {
            return true;
        }
        self.merge_plausible_at(mile)
    }

    /// Why traffic is braking here, when the road knows: the zone's own
    /// reason, else empty.
    pub fn braking_reason_at(&self, mile: f64) -> String {
        for zone in &self.braking_zones {
            if zone.start_mi <= mile && mile <= zone.end_mi {
                return zone.reason.clone();
            }
        }
        String::new()
    }

    /// The prevailing speed of the braking zone covering this mile, when the
    /// trip handed one over.
    pub fn zone_pace_at(&self, mile: f64) -> Option<f64> {
        for zone in &self.braking_zones {
            if zone.start_mi <= mile && mile <= zone.end_mi {
                // Python: `len(zone) > 3 and zone[3]` -- a zero pace is falsy.
                if let Some(pace) = zone.pace_mph.filter(|p| *p != 0.0) {
                    return Some(pace);
                }
            }
        }
        None
    }

    /// Fill an activating congestion zone with slow vehicles ahead, in both
    /// lanes, so the jam is heard and felt through the lead-vehicle machinery.
    pub fn inject_congestion(&mut self, zone_start_mi: f64, zone_limit_mph: f64, position_mi: f64) {
        let key_base = format!("congestion:{}", fmt_f(zone_start_mi, 1));
        if self.vehicles.iter().any(|v| v.key.starts_with(&key_base)) {
            return;
        }
        let digest = Sha256::digest(format!("{}:{key_base}", seed_text(self.seed)).as_bytes());
        let hex = hex::encode(digest);
        let seed = u64::from_str_radix(&hex[..12], 16).expect("12 hex digits fit a u64");
        let mut rng = PyRandom::new_from_u64(seed);
        let pace = 10.0_f64.max(zone_limit_mph);
        let anchor = (position_mi + 0.25).max(zone_start_mi + 0.2);
        let mut added = Vec::new();
        let count = rng.randint(3, 5);
        for i in 0..count {
            let lane = i % 2;
            let speed = 6.0_f64.max(pace + rng.uniform(-9.0, 4.0));
            let position = anchor + i as f64 * rng.uniform(0.25, 0.6);
            let intent = if i == 0 {
                "braking"
            } else {
                *rng.choice(&["following", "cruising"])
            };
            let vehicle_class = *rng.choice(&["car", "car", "semi", "box truck"]);
            added.push(
                TrafficVehicle::new(
                    &format!("{key_base}:{i}"),
                    position,
                    speed,
                    speed,
                    self.player_lane - lane,
                    intent,
                    vehicle_class,
                )
                .with_lane(lane),
            );
        }
        self.vehicles.extend(added);
        sort_by_position(&mut self.vehicles);
    }

    /// The nearest vehicle occupying `lane` beside or just ahead of the
    /// player -- the mirror check before a lane change or a hazard dodge.
    /// With `horizon_hr` the check also sweeps each vehicle's relative motion
    /// against the player's `speed_mph` over that much game time.
    pub fn vehicle_in_lane(
        &self,
        position_mi: f64,
        lane: i64,
        ahead_mi: f64,
        behind_mi: f64,
        horizon_hr: f64,
        speed_mph: f64,
    ) -> Option<&TrafficVehicle> {
        let mut nearest: Option<&TrafficVehicle> = None;
        let mut nearest_gap = f64::INFINITY;
        for vehicle in &self.vehicles {
            if vehicle.lane != lane {
                continue;
            }
            let gap = vehicle.position_mi - position_mi;
            let later = gap + (vehicle.speed_mph - speed_mph) * horizon_hr;
            if gap.min(later) <= ahead_mi && gap.max(later) >= -behind_mi - vehicle.length_mi {
                let distance = gap.max(0.0).abs();
                if distance < nearest_gap {
                    nearest = Some(vehicle);
                    nearest_gap = distance;
                }
            }
        }
        nearest
    }

    /// Civilian vehicles close by and holding roughly the truck's speed:
    /// traffic cover. Marked units do not count.
    pub fn pack_neighbours(
        &self,
        position_mi: f64,
        speed_mph: f64,
        radius_mi: f64,
        tolerance_mph: f64,
    ) -> i64 {
        let mut count = 0;
        for vehicle in &self.vehicles {
            if vehicle.vehicle_class == "state trooper" {
                continue;
            }
            if (vehicle.position_mi - position_mi).abs() > radius_mi {
                continue;
            }
            if (vehicle.speed_mph - speed_mph).abs() <= tolerance_mph {
                count += 1;
            }
        }
        count
    }

    /// The leg the given route mile falls in.
    pub fn leg_at(&self, mile: f64) -> Option<&Leg> {
        let mut found: Option<&Leg> = None;
        for (start, leg) in self.leg_starts.iter().zip(self.route.legs.iter()) {
            if mile + 1e-9 >= *start {
                found = Some(leg);
            } else {
                break;
            }
        }
        found
    }

    /// The leg a route mile falls in, how far into that leg it is
    /// (leg-relative and direction-aware), and which way the route runs
    /// along it.
    ///
    /// The one walk the lane, limit and grade lookups all read, so they
    /// cannot come to different answers about which leg a mile is on.
    pub fn leg_offset_forward_at(&self, mile: f64) -> Option<(&Leg, f64, bool)> {
        let mut found: Option<(&Leg, f64, bool)> = None;
        for (index, (start, leg)) in self
            .leg_starts
            .iter()
            .zip(self.route.legs.iter())
            .enumerate()
        {
            if mile + 1e-9 >= *start {
                let offset = (mile - start).clamp(0.0, leg.miles.max(0.0));
                let forward = self.route.cities.get(index).is_some_and(|c| *c == leg.a);
                found = Some((
                    leg,
                    if forward { offset } else { leg.miles - offset },
                    forward,
                ));
            } else {
                break;
            }
        }
        found
    }

    /// The leg a route mile falls in, and how far into that leg it is
    /// (leg-relative and direction-aware).
    pub fn leg_and_offset_at(&self, mile: f64) -> Option<(&Leg, f64)> {
        self.leg_offset_forward_at(mile)
            .map(|(leg, offset, _)| (leg, offset))
    }

    /// Lanes in the direction of travel at a route mile.
    ///
    /// Mirrors `Trip::lane_count_at`, which is the answer the driving state
    /// steers by, because the bubble cannot reach the trip and has to place
    /// vehicles in the lanes the road actually has. Without it "passing"
    /// traffic went into lane 1 on every road, including the two-lane US
    /// routes that have no lane 1: the vehicle sat in a lane that does not
    /// exist, where it could never be the lead the driver has to deal with
    /// and where its pass-by whoosh panned to a side of a road with no side.
    pub fn lane_count_at(&self, mile: f64) -> i64 {
        let Some((leg, offset, forward)) = self.leg_offset_forward_at(mile) else {
            return DEFAULT_LEG_LANES;
        };
        for seg in leg.lane_segments() {
            if seg.start_mi <= offset && offset <= seg.end_mi {
                return 1.max(MAX_DRIVABLE_LANES.min(seg.your_side(forward)));
            }
        }
        if leg.divided == Some(false) {
            return 1;
        }
        MAX_DRIVABLE_LANES.min(leg_lane_count(Some(leg)))
    }

    /// The lane a vehicle with this intent takes here. Passing traffic lives
    /// in the left lane where the road has one, and in the only lane there is
    /// where it does not.
    pub fn intent_lane_at(&self, intent: &str, mile: f64) -> i64 {
        if intent != "passing" {
            return 0;
        }
        (self.lane_count_at(mile) - 1).clamp(0, 1)
    }

    /// The posted limit for a car here -- the posted number rather than the
    /// truck cap, because the cars going by a rig held to 55 are doing 65.
    pub fn posted_limit_at(&self, mile: f64) -> f64 {
        let Some((leg, offset)) = self.leg_and_offset_at(mile) else {
            return DEFAULT_LIMIT_MPH;
        };
        if let Some(baked) = leg_speed_limit_at(leg, offset) {
            return baked;
        }
        corridor_speed_limit(&leg.highway, "")
    }

    /// Signed grade at a route mile, positive uphill in the direction of
    /// travel. Mirrors `Trip::grade_at`: a leg driven from b to a reads its
    /// baked segments from the far end and climbs what the other way
    /// descends. Zero where the bake has nothing to say, so an unsurveyed
    /// stretch simply leaves the limiter in charge.
    pub fn grade_pct_at(&self, mile: f64) -> f64 {
        let Some((leg, sample_offset, forward)) = self.leg_offset_forward_at(mile) else {
            return 0.0;
        };
        for segment in leg.grade_segments() {
            if segment.start_mi <= sample_offset && sample_offset <= segment.end_mi {
                return if forward {
                    segment.avg_grade_pct
                } else {
                    -segment.avg_grade_pct
                };
            }
        }
        0.0
    }

    /// The slowest a moving vehicle gets here from speed draws alone.
    pub fn floor_speed(&self, limit_mph: f64) -> f64 {
        TRAFFIC_MIN_SPEED_MPH.max(limit_mph * TRAFFIC_MIN_SPEED_SHARE)
    }

    /// A speed for this intent on a road posted at `limit_mph`.
    ///
    /// A governed class never comes out above its limiter, whatever the
    /// posting and whatever the intent -- a "passing" semi passes by using
    /// the whole of its governor, not by exceeding it. Each governed class
    /// draws from its OWN band: a box truck is not a class 8 tractor and
    /// must not inherit the tractor's limiter.
    pub fn intent_speed(
        intent: &str,
        limit_mph: f64,
        rng: &mut PyRandom,
        vehicle_class: &str,
    ) -> f64 {
        let (offset_mph, governor_mph) = Self::intent_speed_draw(intent, rng, vehicle_class);
        let speed = limit_mph + offset_mph;
        match governor_mph {
            Some(governor) => speed.min(governor),
            None => speed,
        }
    }

    /// The two draws behind [`TrafficManager::intent_speed`], kept apart.
    ///
    /// A speed is not a property of a vehicle -- it is what this driver does
    /// on the road they are on, and the number posted changes under them all
    /// the way along a leg. What IS a property of the vehicle is how far off
    /// the posting they run and what limiter their machine carries, so those
    /// are what the bubble stores; the speed is re-read from the road every
    /// update (see [`TrafficManager::road_speed_mph`]).
    ///
    /// Draws in the same order as `intent_speed` always has, so a seeded run
    /// puts the same vehicle in the same place as before.
    pub fn intent_speed_draw(
        intent: &str,
        rng: &mut PyRandom,
        vehicle_class: &str,
    ) -> (f64, Option<f64>) {
        let (low, high) = traffic_speed_offsets_mph(intent);
        let offset_mph = rng.uniform(low, high);
        let governor_mph = governed_band(vehicle_class).map(|band| rng.uniform(band.0, band.1));
        (offset_mph, governor_mph)
    }

    /// What a driver with this habit would be doing on the road under them.
    ///
    /// The posting where the vehicle IS, plus the driver's own offset from
    /// it, under their machine's limiter, with the conditions off the top and
    /// never below the road's own floor. This is the whole reason the offset
    /// is stored rather than the speed: a car drawn on a town's thirty and
    /// kept at thirty used to carry that number out onto a sixty-five, where
    /// it was a wall nothing on the road explained.
    pub fn road_speed_mph(
        &self,
        mile: f64,
        limit_offset_mph: f64,
        governor_mph: Option<f64>,
        slowdown_mph: f64,
    ) -> f64 {
        let posted = self.posted_limit_at(mile);
        let mut speed = posted + limit_offset_mph;
        if let Some(governor) = governor_mph {
            speed = speed.min(governor);
        }
        self.floor_speed(posted)
            .max(speed - self.weather_slowdown() - slowdown_mph)
    }

    /// [`TrafficManager::road_speed_mph`] for a vehicle that carries a draw,
    /// or `None` for one that does not.
    pub fn vehicle_road_speed_mph(&self, vehicle: &TrafficVehicle) -> Option<f64> {
        vehicle.limit_offset_mph.map(|offset| {
            self.road_speed_mph(
                vehicle.position_mi,
                offset,
                vehicle.governor_mph,
                vehicle.slowdown_mph,
            )
        })
    }

    /// A generator belonging to one cell of road, keyed on the route and
    /// seed plus the cell index.
    pub fn cell_rng(&self, cell: i64) -> PyRandom {
        PyRandom::new_from_sha256_prefix16(&format!("{}:cell:{cell}", self.seed_key()))
    }

    /// Fill the window around the truck, ahead and behind. Behind matters as
    /// much as ahead: being overtaken is most of what traffic sounds like
    /// from a truck holding 60 in the right lane.
    pub fn replenish(&mut self, position_mi: f64) {
        if !self.rolling_bubble || self.vehicles.len() >= MAX_BUBBLE_VEHICLES {
            return;
        }
        let low = (position_mi - BUBBLE_BEHIND_MI).max(0.0);
        let high = self.route.miles().min(position_mi + BUBBLE_AHEAD_MI);
        let occupied: HashSet<i64> = self
            .vehicles
            .iter()
            .map(|v| (v.position_mi / SPAWN_CELL_MI) as i64)
            .collect();
        let night = is_night(self.hour);
        let first = (low / SPAWN_CELL_MI) as i64;
        let last = (high / SPAWN_CELL_MI) as i64;
        for cell in first..=last {
            if self.spawned_cells.contains(&cell) {
                continue;
            }
            self.spawned_cells.insert(cell);
            if occupied.contains(&cell) || self.vehicles.len() >= MAX_BUBBLE_VEHICLES {
                continue;
            }
            let mut rng = self.cell_rng(cell);
            // Draw the place inside the cell BEFORE the clear-air test.
            let mile = cell as f64 * SPAWN_CELL_MI + rng.uniform(0.0, SPAWN_CELL_MI);
            if -NO_SPAWN_BEHIND_MI < mile - position_mi && mile - position_mi < NO_SPAWN_AHEAD_MI {
                continue;
            }
            let Some(leg) = self.leg_at(mile) else {
                continue;
            };
            // Density is a share of road, so it reads directly as the chance
            // this cell of it is carrying somebody.
            if rng.random() > self.leg_density(leg, night, Some(mile)) {
                continue;
            }
            let behind = mile < position_mi;
            let intent = if behind {
                // Somebody behind you is somebody who is going to pass you.
                choose(&mut rng, &["passing", "cruising"], &[3.0, 1.0])
            } else if mile < MERGE_FREE_START_MI {
                // Not merging into a truck that has not got up to speed yet
                // (owner report, 2026-08-16). Braking still needs the road's
                // permission here, exactly as it does everywhere else: the
                // exemption is about MERGING into a truck still accelerating,
                // and letting braking through with it put a phantom wave in
                // the first three miles of every single run.
                let mut options = vec!["cruising", "following", "passing"];
                let mut weights = vec![3.0, 1.5, 0.6];
                if self.braking_plausible_at(mile) {
                    options.push("braking");
                    weights.push(1.0);
                }
                choose(&mut rng, &options, &weights)
            } else {
                // Merging and braking only where the road gives a reason.
                let mut options = vec!["cruising", "following", "passing"];
                let mut weights = vec![3.0, 1.5, 0.6];
                if self.merge_plausible_at(mile) {
                    options.push("merging");
                    weights.push(1.2);
                }
                if self.braking_plausible_at(mile) {
                    options.push("braking");
                    weights.push(1.0);
                }
                choose(&mut rng, &options, &weights)
            };
            let vehicle_class = choose(
                &mut rng,
                &["car", "box truck", "semi", "service vehicle"],
                &[5.0, 1.4, 2.0, 0.3],
            );
            let (limit_offset, governor) = Self::intent_speed_draw(intent, &mut rng, vehicle_class);
            let rush_slowdown = if self.rush_hour_traffic_bias(leg) != 0.0 {
                rng.uniform(4.0, 10.0)
            } else {
                0.0
            };
            let speed = self.road_speed_mph(mile, limit_offset, governor, rush_slowdown);
            let lane = self.intent_lane_at(intent, mile);
            let exit_at = mile + rng.uniform(EXIT_AFTER_MIN_MI, EXIT_AFTER_MAX_MI);
            self.vehicles.push(
                TrafficVehicle::new(
                    &format!("bubble:{cell}"),
                    mile,
                    speed,
                    speed,
                    -lane,
                    intent,
                    vehicle_class,
                )
                .with_lane(lane)
                .with_exit_at(Some(exit_at))
                .with_speed_draw(limit_offset, governor, rush_slowdown),
            );
        }
    }

    pub fn update(
        &mut self,
        dt: f64,
        position_mi: f64,
        time_scale: f64,
        hour: Option<f64>,
        weekend: Option<bool>,
    ) {
        if let Some(hour) = hour {
            self.hour = hour;
        }
        if let Some(weekend) = weekend {
            self.weekend = weekend;
        }
        let game_hours = dt * time_scale / 3600.0;
        let mut kept = Vec::new();
        let vehicles = std::mem::take(&mut self.vehicles);
        for mut vehicle in vehicles {
            let gap = vehicle.position_mi - position_mi;
            // The lane follows the road for the same reason the speed does:
            // a vehicle drawn in the left lane of a divided stretch drives on
            // into the two-lane US route beyond it, where there is no left
            // lane to be in. Held to the lanes the road has under it, the
            // same clamp `LaneKeeping::set_lane_count` puts on the player.
            vehicle.lane = vehicle
                .lane
                .min(self.lane_count_at(vehicle.position_mi) - 1)
                .max(0);
            vehicle.relative_lane = self.player_lane - vehicle.lane;
            // What this driver would be doing on the road UNDER THEM, which
            // is not what they were doing where they were drawn: a US route
            // drops to thirty through every town it passes and climbs back to
            // sixty-five on the far side, and a speed drawn once and kept
            // forever crossed those boundaries without noticing. A car drawn
            // on the town's thirty was a thirty-mile-an-hour wall out on the
            // open road; one drawn on the open road held sixty-five through
            // the town. Measured over five thousand seeded route miles
            // (`states_driving_traffic_rate.rs`): most of the traffic that
            // forced the truck to brake was carrying a number from a slower
            // piece of road, and one bubble vehicle in seventy was running
            // slower than any speed its own road could have drawn for it.
            let road_mph = self.vehicle_road_speed_mph(&vehicle);
            // Braking ends when the REASON does, and the reason is on the
            // ROAD -- so the question has to be asked BEFORE the near-gap jam
            // branch below, not only after it. That branch holds a braking
            // vehicle down at the zone pace, or at the 45-percent floor where
            // there is no zone, for as long as it stays within 1.8 miles of
            // the truck; and 1.8 miles is inside the 2.2 the cue announces
            // in. So the one braking vehicle a driver could actually hear
            // about was the one whose label could never expire: it crawled at
            // 45 percent of the posting with no jam anywhere under it, while
            // "Brake lights ahead" named no cause because `braking_cause_line`
            // had none to name. That is the invented phantom wave the bubble
            // is supposed to refuse.
            if vehicle.intent == "braking" && !self.braking_plausible_at(vehicle.position_mi) {
                vehicle.intent = "cruising".to_string();
            }
            if vehicle.intent == "braking" && (0.0..=1.8).contains(&gap) {
                // Inside a zone the pace is the zone's own prevailing speed,
                // not the generic 45-percent-of-posted floor (Brandon,
                // 2026-08-20).
                match self.zone_pace_at(vehicle.position_mi) {
                    Some(pace) => vehicle.target_speed_mph = pace,
                    None => {
                        vehicle.target_speed_mph = self
                            .floor_speed(self.posted_limit_at(vehicle.position_mi))
                            .max(vehicle.target_speed_mph - 8.0 * dt);
                    }
                }
            } else if vehicle.intent == "merging" || vehicle.intent == "braking" {
                // Merging and braking are TRANSIENT states, not careers: a
                // real merger builds to road speed once the lane change is
                // done, capped at the zone's own pace inside a jam. Road speed
                // is what the ROAD posts here, under this machine's limiter --
                // a governed semi finishing a merge onto a seventy-five does
                // not build to seventy-six.
                let cruise = match self.zone_pace_at(vehicle.position_mi) {
                    Some(pace) => pace,
                    None => {
                        let mut open = self.posted_limit_at(vehicle.position_mi) + 1.0;
                        if let Some(governor) = vehicle.governor_mph {
                            open = open.min(governor);
                        }
                        open
                    }
                };
                if vehicle.target_speed_mph < cruise {
                    vehicle.target_speed_mph = cruise.min(vehicle.target_speed_mph + 4.0 * dt);
                } else {
                    // And back DOWN when the road slows under them: the ramp
                    // above only ever climbed, so a merger that had built to
                    // highway speed took it into the next town.
                    vehicle.target_speed_mph = cruise;
                }
                // The LABEL is as transient as the speed, and only the speed
                // used to recover. A vehicle that braked once inside a jam and
                // then drove out of it, back up to road speed, kept "braking"
                // for the rest of its life -- so the cue for it was still
                // "Brake lights ahead" while it ran sixty-eight on a seventy,
                // with no cause to name because the road no longer had one.
                // Once the reason is behind it and it is back up to the pace,
                // it is just traffic.
                // A merge ENDS when the vehicle is up with the traffic it
                // merged into; that is what finishing a merge means, and it
                // is also the only reading that leaves a merger announceable
                // for the couple of miles the cue reaches, since the window a
                // merger is created in is under half a mile long.
                //
                // Braking is settled above, at every gap rather than only at
                // this one: anything still labelled braking by the time it
                // gets here has a jam under it, so there is nothing left to
                // ask.
                if vehicle.intent == "merging" && vehicle.speed_mph >= cruise - 2.0 {
                    vehicle.intent = "cruising".to_string();
                }
            } else if let Some(road_mph) = road_mph {
                vehicle.target_speed_mph = road_mph;
            }
            // The hill has the last word. A limiter is a ceiling the truck
            // sits on when the road lets it; a climb takes the choice away,
            // and this is what strings heavy traffic out into something a
            // driver can pass instead of a wall all doing the same speed.
            // Python reads the class through `getattr(..., "")` for the
            // reason the exit mile below already gives: the harness and the
            // trip's own NPCVehicle share this runtime surface without
            // carrying the dataclass. Here they arrive through
            // `From<NPCVehicle>` carrying the class `"vehicle"`, which is
            // just as unmodelled -- and an unknown class is not
            // climb-modelled, which is what a car is.
            let climb = climb_speed_mph(
                &vehicle.vehicle_class,
                self.grade_pct_at(vehicle.position_mi),
            );
            let target = vehicle.target_speed_mph.min(climb);
            let delta = target - vehicle.speed_mph;
            vehicle.speed_mph += (-6.0 * dt).max((4.0 * dt).min(delta));
            vehicle.position_mi += vehicle.speed_mph.max(0.0) * game_hours;
            if vehicle
                .exit_at_mi
                .is_some_and(|exit_at| vehicle.position_mi >= exit_at)
            {
                continue; // took its exit
            }
            if vehicle.position_mi - position_mi >= -2.0 {
                kept.push(vehicle);
            }
        }
        self.vehicles = kept;
        self.replenish(position_mi);
        sort_by_position(&mut self.vehicles);
    }

    pub fn next_situation(
        &mut self,
        position_mi: f64,
        truck_speed_mph: f64,
    ) -> Option<TrafficSituation> {
        let context = self.lead_vehicle(position_mi, truck_speed_mph)?;
        if context.gap_mi > 2.2 {
            return None;
        }
        let vehicle = context.lead.clone();
        if self.announced_vehicle_keys.contains(&vehicle.key) {
            return None;
        }
        if vehicle.vehicle_class == "state trooper" {
            // A marked unit is a fact about the road, not an instruction: it
            // is carried by an earcon and never by a sentence.
            return None;
        }
        let gap = self.gap_text(context.gap_mi);
        let speed = self.speed_value(vehicle.speed_mph);
        let bare = self.speed_bare(vehicle.speed_mph);
        let intent = vehicle.intent.clone();
        let vehicle_class = vehicle.vehicle_class.clone();
        let (message, kind) = match intent.as_str() {
            "merging" => (merging_traffic_cue(&vehicle_class, &gap), "merging"),
            "braking" => {
                let cause = braking_cause_line(&self.braking_reason_at(vehicle.position_mi));
                (brake_lights_cue(&gap, &speed, &bare, cause), "braking")
            }
            "following" => (
                slow_lead_cue(&vehicle_class, &gap, &speed, &bare),
                "following",
            ),
            _ => return None,
        };
        self.announced_vehicle_keys.insert(vehicle.key.clone());
        // The number in a traffic cue is the lead's own speed, and from the
        // seat there is no way to check it: log what the line was built from.
        log::info!(
            "traffic cue {}: {} doing {:.1} mph, gap {:.2} mi, truck {:.1} mph, mile {:.2}",
            kind,
            vehicle_class,
            vehicle.speed_mph,
            context.gap_mi,
            truck_speed_mph,
            position_mi
        );
        Some(TrafficSituation {
            kind: kind.to_string(),
            vehicle,
            message,
            interrupt: true,
        })
    }
}

/// `rng.choices(options, weights=weights)[0]`.
fn choose<'a>(rng: &mut PyRandom, options: &[&'a str], weights: &[f64]) -> &'a str {
    let idx = rng.choices_indices_weighted(weights, 1)[0];
    options[idx]
}

/// `sorted(vehicles, key=position_mi)`, stable like Python's.
fn sort_by_position(vehicles: &mut [TrafficVehicle]) {
    vehicles.sort_by(|a, b| {
        a.position_mi
            .partial_cmp(&b.position_mi)
            .expect("finite vehicle positions")
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_traffic_vehicle_keeps_npc_compatibility_properties() {
        let vehicle = TrafficVehicle::new("traffic:test", 12.5, 44.0, 40.0, 1, "merging", "car");
        assert_eq!(vehicle.at_mi(), 12.5);
        assert!(vehicle.end_mi() > vehicle.at_mi());
        assert_eq!(vehicle.lane_text(), "right lane");
        assert_eq!(vehicle.behavior(), "merging_vehicle");
        assert_eq!(vehicle.reason(), "merging traffic");
    }

    #[test]
    fn test_state_trooper_vehicle_has_clear_status_reason() {
        let vehicle = TrafficVehicle::new(
            "trooper:test",
            12.5,
            62.0,
            62.0,
            0,
            "cruising",
            "state trooper",
        );
        assert_eq!(vehicle.reason(), "state trooper ahead");
    }

    #[test]
    fn test_traffic_vehicle_maps_new_intents_to_legacy_behavior_and_reason() {
        let expected = [
            ("cruising", "steady_truck", "steady truck traffic"),
            ("following", "slow_car", "slow car ahead"),
            ("merging", "merging_vehicle", "merging traffic"),
            ("braking", "braking_traffic", "brake lights ahead"),
            ("passing", "passing_vehicle", "passing traffic"),
        ];
        for (intent, behavior, reason) in expected {
            let vehicle = TrafficVehicle::new(
                &format!("traffic:{intent}"),
                10.0,
                45.0,
                45.0,
                0,
                intent,
                "car",
            );
            assert_eq!(vehicle.behavior(), behavior);
            assert_eq!(vehicle.reason(), reason);
        }
    }

    #[test]
    fn test_a_semi_out_there_is_governed_like_a_real_one() {
        let mut rng = PyRandom::new_from_i64(11);
        let top = GOVERNED_TRUCK_BAND_MPH.1;
        for limit in [65.0, 70.0, 75.0, 80.0] {
            for intent in ["cruising", "passing", "following"] {
                for vehicle_class in GOVERNED_CLASSES {
                    for _ in 0..60 {
                        let speed =
                            TrafficManager::intent_speed(intent, limit, &mut rng, vehicle_class);
                        assert!(speed <= top, "{vehicle_class} {intent} {limit} {speed}");
                    }
                }
            }
        }
        let fast: Vec<f64> = (0..60)
            .map(|_| TrafficManager::intent_speed("passing", 75.0, &mut rng, "car"))
            .collect();
        assert!(fast.iter().cloned().fold(f64::MIN, f64::max) > top);
        let governed: Vec<f64> = (0..200)
            .map(|_| TrafficManager::intent_speed("cruising", 80.0, &mut rng, "semi"))
            .collect();
        let lo = governed.iter().cloned().fold(f64::MAX, f64::min);
        let hi = governed.iter().cloned().fold(f64::MIN, f64::max);
        assert!(lo >= GOVERNED_TRUCK_BAND_MPH.0);
        assert!(hi - lo > 2.0);
    }

    #[test]
    fn test_hard_braking_follows_the_congestion_not_the_dice() {
        let mut manager = TrafficManager::bare(&Route::default(), &[]);
        manager.braking_zones = vec![BrakingZone::span(10.0, 14.0)];
        assert!(manager.braking_plausible_at(12.0));
        assert!(!manager.braking_plausible_at(40.0));
    }

    #[test]
    fn braking_reason_reads_the_zone() {
        let mut mgr = TrafficManager::bare(&Route::default(), &[]);
        mgr.braking_zones = vec![
            BrakingZone::new(10.0, 14.0, "construction", None),
            BrakingZone::new(20.0, 25.0, "heavy traffic", None),
        ];
        assert_eq!(mgr.braking_reason_at(12.0), "construction");
        assert_eq!(mgr.braking_reason_at(22.0), "heavy traffic");
        assert_eq!(mgr.braking_reason_at(50.0), "");
        assert_eq!(
            braking_cause_line("construction"),
            "Road work is the cause."
        );
    }
}
