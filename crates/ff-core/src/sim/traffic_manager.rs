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
    corridor_speed_limit, hourly_volume_fraction, leg_aadt_at, leg_speed_limit_at, TrafficContext,
    DIRECTIONAL_SPLIT, RUSH_HOUR_WINDOWS, TRAFFIC_LOOKAHEAD_MI,
};
use crate::sim::weather::{effects, WeatherEffects, WeatherKind};
use crate::speech_text::{brake_lights_cue, merging_traffic_cue, slow_lead_cue};

mod vehicle;
pub use vehicle::{braking_cause_line, BrakingZone, TrafficSituation, TrafficVehicle};

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
pub const GOVERNED_CLASSES: [&str; 2] = ["semi", "box truck"];
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
        let weather_slowdown = self.weather_slowdown();
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
                let intent = choose(
                    &mut rng,
                    &["cruising", "following", "merging", "braking", "passing"],
                    &[3.0, 1.5, 1.2, 1.0, 1.1],
                );
                let vehicle_class = choose(
                    &mut rng,
                    &["car", "box truck", "semi", "service vehicle"],
                    &[5.0, 1.4, 2.0, 0.3],
                );
                let position_mi = start + rng.uniform(low, high);
                let limit_mph = self.posted_limit_at(position_mi);
                let base_speed = Self::intent_speed(intent, limit_mph, &mut rng, vehicle_class);
                let rush_slowdown = if self.rush_hour_traffic_bias(leg) != 0.0 {
                    rng.uniform(4.0, 10.0)
                } else {
                    0.0
                };
                let speed = self
                    .floor_speed(limit_mph)
                    .max(base_speed - weather_slowdown - rush_slowdown);
                // Passing traffic lives in the left lane; everyone else holds
                // the right lane, where trucks are supposed to be.
                let lane = if intent == "passing" { 1 } else { 0 };
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
                    .with_lane(lane),
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

    /// The leg a route mile falls in, and how far into that leg it is
    /// (leg-relative and direction-aware).
    pub fn leg_and_offset_at(&self, mile: f64) -> Option<(&Leg, f64)> {
        let mut found: Option<(&Leg, f64)> = None;
        for (index, (start, leg)) in self
            .leg_starts
            .iter()
            .zip(self.route.legs.iter())
            .enumerate()
        {
            if mile + 1e-9 >= *start {
                let offset = (mile - start).clamp(0.0, leg.miles.max(0.0));
                let forward = self.route.cities.get(index).is_some_and(|c| *c == leg.a);
                found = Some((leg, if forward { offset } else { leg.miles - offset }));
            } else {
                break;
            }
        }
        found
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

    /// The slowest a moving vehicle gets here from speed draws alone.
    pub fn floor_speed(&self, limit_mph: f64) -> f64 {
        TRAFFIC_MIN_SPEED_MPH.max(limit_mph * TRAFFIC_MIN_SPEED_SHARE)
    }

    /// A speed for this intent on a road posted at `limit_mph`. A governed
    /// class never comes out above its limiter, whatever the intent.
    pub fn intent_speed(
        intent: &str,
        limit_mph: f64,
        rng: &mut PyRandom,
        vehicle_class: &str,
    ) -> f64 {
        let (low, high) = traffic_speed_offsets_mph(intent);
        let speed = limit_mph + rng.uniform(low, high);
        if GOVERNED_CLASSES.contains(&vehicle_class) {
            let governor = rng.uniform(GOVERNED_TRUCK_BAND_MPH.0, GOVERNED_TRUCK_BAND_MPH.1);
            return speed.min(governor);
        }
        speed
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
        let weather_slowdown = self.weather_slowdown();
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
                // (owner report, 2026-08-16).
                choose(
                    &mut rng,
                    &["cruising", "following", "braking", "passing"],
                    &[3.0, 1.5, 1.0, 0.6],
                )
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
            let limit_mph = self.posted_limit_at(mile);
            let base_speed = Self::intent_speed(intent, limit_mph, &mut rng, vehicle_class);
            let rush_slowdown = if self.rush_hour_traffic_bias(leg) != 0.0 {
                rng.uniform(4.0, 10.0)
            } else {
                0.0
            };
            let speed = self
                .floor_speed(limit_mph)
                .max(base_speed - weather_slowdown - rush_slowdown);
            let lane = if intent == "passing" { 1 } else { 0 };
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
                .with_exit_at(Some(exit_at)),
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
            vehicle.relative_lane = self.player_lane - vehicle.lane;
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
                // done, capped at the zone's own pace inside a jam.
                let cruise = match self.zone_pace_at(vehicle.position_mi) {
                    Some(pace) => pace,
                    None => self.posted_limit_at(vehicle.position_mi) + 1.0,
                };
                if vehicle.target_speed_mph < cruise {
                    vehicle.target_speed_mph = cruise.min(vehicle.target_speed_mph + 4.0 * dt);
                }
            }
            let delta = vehicle.target_speed_mph - vehicle.speed_mph;
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
