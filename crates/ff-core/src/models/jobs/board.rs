//! `JobBoard`: seeded job generation at a city (the board half of `jobs.py`).

use std::collections::HashMap;

use indexmap::IndexMap;
use once_cell::sync::Lazy;
use parking_lot::Mutex;

use crate::data::world::World;
use crate::data::world_models::{City, Location};
use crate::models::business_constants::DIRECT_FREIGHT_PAY_MULT;
use crate::models::jobs::{
    cargo_type, dispatch_deadline_hours, facility_cargo, market_tag_cargo_bonus,
    minimum_pay_for_level, plan_hos, CargoType, Job, CARGO_CATALOG, DEADLINE_DISPATCH_SLACK_RANGE,
    FACILITY_SELECTION_WEIGHTS, HOOKUP_FEE, LEVEL_DISTANCE_CAPS, LEVEL_DISTANCE_CAP_STEP_MI,
    LONG_HAUL_MILES, MAX_DISPATCH_DISTANCE_MI, MIN_JOB_DISTANCE_MI, PREMIUM_LANE_LEVEL,
    PREMIUM_LANE_LONG_HAUL_BIAS, SPECIALIZED_FREIGHT_LEVEL, SPECIALIZED_FREIGHT_WEIGHT,
};
use crate::models::market::Market;
use crate::models::start_options::{start_option, DEFAULT_START_KEY};
use crate::pyfmt::round_py_n;
use crate::pyrandom::PyRandom;
use crate::sim::hos::HosClock;
use crate::sim::vehicle::{combination_tare_kg, max_legal_cargo_tons, TruckSpecs};

/// `(destination, route miles, route leg count)`.
pub type Candidate = (String, f64, usize);

// Reachable-destination candidates depend only on the (static) world, not the
// board seed. Cache them once across all JobBoard instances, keyed by world:
// the city hub and the tests spin up many fresh boards, and recomputing a
// supported route to every city each time scaled terribly as the network grew
// to 160+.
type CandidateCache = HashMap<usize, HashMap<String, Vec<Candidate>>>;
static CANDIDATES_CACHE: Lazy<Mutex<CandidateCache>> = Lazy::new(|| Mutex::new(HashMap::new()));

/// The keyword arguments of `JobBoard.offers` / `offer_to`, each with its
/// Python default.
#[derive(Debug, Clone, Copy, Default)]
pub struct OfferOptions<'a> {
    /// `count=5` (`offers` only); 0 means the default.
    pub count: usize,
    /// `level=1`; 0 means the default.
    pub level: i64,
    pub market: Option<&'a Market>,
    pub carrier_key: Option<&'a str>,
    pub direct_freight: bool,
}

impl<'a> OfferOptions<'a> {
    /// `offers(..., level=level)`.
    pub fn level(level: i64) -> Self {
        OfferOptions {
            level,
            ..Self::default()
        }
    }

    fn count_or_default(&self) -> usize {
        if self.count == 0 {
            5
        } else {
            self.count
        }
    }

    fn level_or_default(&self) -> i64 {
        if self.level == 0 {
            1
        } else {
            self.level
        }
    }

    fn carrier(&self) -> &'a str {
        match self.carrier_key {
            Some(key) if !key.is_empty() => key,
            _ => DEFAULT_START_KEY,
        }
    }
}

/// Generates job offers at a city, filtered by the player's endorsements.
///
/// Destinations follow a career arc: low levels offer mostly single-leg hops
/// to neighboring cities, the distance cap grows with level, and every level
/// weights destination choice by proximity so freight follows plausible lanes
/// instead of teleporting across the country. New dispatches only use
/// metadata-supported corridors; the broad legacy graph remains available for
/// old saves while enrichment coverage expands.
pub struct JobBoard<'w> {
    pub world: &'w World,
    // The driver's live shift clock: deadlines plan around the hours already
    // burned, the way a real dispatcher asks what you have left.
    pub hos: Option<HosClock>,
    rng: PyRandom,
}

impl<'w> JobBoard<'w> {
    /// `JobBoard(world, seed=None, hos=None)`; `None` seeds from the OS.
    pub fn new(world: &'w World, seed: Option<i64>, hos: Option<&HosClock>) -> Self {
        JobBoard {
            world,
            hos: hos.cloned(),
            rng: match seed {
                Some(seed) => PyRandom::new_from_i64(seed),
                None => PyRandom::new_unseeded(),
            },
        }
    }

    /// `JobBoard(world, seed=seed)`.
    pub fn seeded(world: &'w World, seed: i64) -> Self {
        Self::new(world, Some(seed), None)
    }

    pub fn distance_cap(level: i64) -> f64 {
        if let Some((_, cap)) = LEVEL_DISTANCE_CAPS.iter().find(|(l, _)| *l == level) {
            return *cap;
        }
        let base = LEVEL_DISTANCE_CAPS
            .iter()
            .find(|(l, _)| *l == 5)
            .map(|(_, cap)| *cap)
            .unwrap_or(1200.0);
        MAX_DISPATCH_DISTANCE_MI.min(base + LEVEL_DISTANCE_CAP_STEP_MI * (level - 5) as f64)
    }

    /// `board.offers(city, endorsements, count=, level=, market=,
    /// carrier_key=, direct_freight=)`.
    pub fn offers<S: AsRef<str>>(
        &mut self,
        city: &str,
        endorsements: &[S],
        opts: OfferOptions<'_>,
    ) -> Vec<Job> {
        let count = opts.count_or_default();
        let level = opts.level_or_default();
        let carrier_key = opts.carrier();
        let mut jobs: Vec<Job> = Vec::new();
        let city = self.world.resolve_city_key(city);
        let Ok(city_obj) = self.world.city(&city) else {
            return jobs;
        };
        let candidates: Vec<Candidate> = self
            .candidates(&city)
            .into_iter()
            .filter(|c| c.1 >= MIN_JOB_DISTANCE_MI)
            .collect();
        let cap = Self::distance_cap(level);
        let mut reachable: Vec<Candidate> =
            candidates.iter().filter(|c| c.1 <= cap).cloned().collect();
        if reachable.is_empty() && !candidates.is_empty() {
            // remote terminals (long legs all around): offer the nearest few
            let mut sorted = candidates.clone();
            sorted.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
            sorted.truncate(4);
            reachable = sorted;
        }
        if reachable.is_empty() {
            return jobs;
        }
        // Pick a spread of DISTINCT destinations up front so the board never
        // collapses to one back-and-forth city (a start with a single nearby
        // neighbour used to be locked into one route). Nearer cities stay likelier.
        let dest_cycle = self.spread_destinations(&city, &reachable, level, count, carrier_key);
        let mut attempts = 0;
        while jobs.len() < count && attempts < count * 30 {
            attempts += 1;
            let location = self.choose_origin_location(city_obj, level, carrier_key);
            let cargo_key = self.choose_cargo_for_location(city_obj, location, level, carrier_key);
            let cargo = cargo_type(cargo_key).expect("a catalog cargo key");
            let locked = cargo
                .endorsement
                .is_some_and(|e| !endorsements.iter().any(|x| x.as_ref() == e));
            // a locked job may appear once in a while as a teaser, otherwise skip
            if locked && !(jobs.len() == count - 1 && self.rng.random() < 0.3) {
                continue;
            }
            let (destination, miles, _legs) = dest_cycle[jobs.len() % dest_cycle.len()].clone();
            let Some(dest_location) = self.destination_location(&destination, cargo, level) else {
                continue;
            };
            let dest_location = dest_location.clone();
            let origin_name = location.name.clone();
            let location = location.clone();
            jobs.push(self.make_job(
                cargo,
                &city,
                &origin_name,
                &destination,
                miles,
                opts.market,
                level,
                &location,
                &dest_location,
                carrier_key,
                opts.direct_freight,
            ));
        }
        jobs.sort_by(|a, b| {
            a.distance_mi
                .partial_cmp(&b.distance_mi)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        jobs
    }

    /// One offer to a specific destination, for the playtest lever.
    ///
    /// Ignores the level distance cap on purpose: a tester forcing a
    /// destination wants that run regardless of career progress. Returns
    /// None when no supported corridor reaches the destination or no
    /// unlocked cargo pairing exists.
    pub fn offer_to<S: AsRef<str>>(
        &mut self,
        city: &str,
        destination: &str,
        endorsements: &[S],
        opts: OfferOptions<'_>,
    ) -> Option<Job> {
        let level = opts.level_or_default();
        let carrier_key = opts.carrier();
        let city = self.world.resolve_city_key(city);
        let destination = self.world.resolve_city_key(destination);
        let city_obj = self.world.city(&city).ok()?;
        let matches: Vec<Candidate> = self
            .candidates(&city)
            .into_iter()
            .filter(|c| c.0 == destination)
            .collect();
        if matches.is_empty() {
            return None;
        }
        let (destination, miles, _legs) = matches
            .iter()
            .min_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal))?
            .clone();
        for _ in 0..30 {
            let location = self.choose_origin_location(city_obj, level, carrier_key);
            let cargo_key = self.choose_cargo_for_location(city_obj, location, level, carrier_key);
            let cargo = cargo_type(cargo_key).expect("a catalog cargo key");
            if cargo
                .endorsement
                .is_some_and(|e| !endorsements.iter().any(|x| x.as_ref() == e))
            {
                continue;
            }
            let Some(dest_location) = self.destination_location(&destination, cargo, level) else {
                continue;
            };
            let dest_location = dest_location.clone();
            let origin_name = location.name.clone();
            let location = location.clone();
            return Some(self.make_job(
                cargo,
                &city,
                &origin_name,
                &destination,
                miles,
                opts.market,
                level,
                &location,
                &dest_location,
                carrier_key,
                opts.direct_freight,
            ));
        }
        None
    }

    /// A weighted spread of distinct destinations (nearer = likelier).
    ///
    /// Aims for at least three distinct cities (or as many as the network
    /// allows) so the dispatch board offers real choices instead of repeating
    /// one destination. Rookies still lean toward short hauls.
    fn spread_destinations(
        &mut self,
        origin: &str,
        reachable: &[Candidate],
        level: i64,
        count: usize,
        carrier_key: &str,
    ) -> Vec<Candidate> {
        let mut best: IndexMap<String, Candidate> = IndexMap::new();
        for cand in reachable {
            match best.get(&cand.0) {
                Some(existing) if cand.1 >= existing.1 => {}
                _ => {
                    best.insert(cand.0.clone(), cand.clone());
                }
            }
        }
        let pool: Vec<Candidate> = best.into_values().collect();
        let target = pool.len().min(count.max(3));
        let exponent = if level <= 2 { 2.0 } else { 1.0 };
        let mut chosen: Vec<Candidate> = Vec::new();
        let mut available = pool.clone();
        while !available.is_empty() && chosen.len() < target {
            let weights: Vec<f64> = available
                .iter()
                .map(|cand| {
                    self.destination_weight(origin, cand, level, carrier_key, Some(exponent))
                })
                .collect();
            let idx = self.rng.choices_indices_weighted(&weights, 1)[0];
            let pick = available.remove(idx);
            chosen.push(pick);
        }
        if chosen.is_empty() {
            pool
        } else {
            chosen
        }
    }

    /// Weighted lane fit for a carrier's modest dispatch tendencies.
    pub fn destination_weight(
        &self,
        origin: &str,
        candidate: &Candidate,
        level: i64,
        carrier_key: &str,
        exponent: Option<f64>,
    ) -> f64 {
        let (destination, miles, _legs) = candidate;
        let miles = *miles;
        let exponent = exponent.unwrap_or(if level <= 2 { 2.0 } else { 1.0 });
        let mut weight = 1.0 / miles.powf(exponent);
        let option = start_option(Some(carrier_key));
        let cap = Self::distance_cap(level).max(1.0);
        if option.dispatch.short_haul_bias != 0.0 {
            let short_factor = (1.0 - miles.min(cap) / cap).max(0.0);
            weight *= 1.0 + option.dispatch.short_haul_bias * short_factor;
        }
        if option.dispatch.long_haul_bias != 0.0 {
            let long_factor = (miles / cap).min(1.0);
            weight *= 1.0 + option.dispatch.long_haul_bias * long_factor;
        }
        if level >= PREMIUM_LANE_LEVEL {
            // Premium-lane seniority: dispatch shows the long freight first.
            weight *= 1.0 + PREMIUM_LANE_LONG_HAUL_BIAS * (miles / cap).min(1.0);
        }
        if option.dispatch.regional_bias != 0.0 {
            let origin_region = self.world.cities.get(origin).map(|c| c.region.as_str());
            let dest_region = self
                .world
                .cities
                .get(destination)
                .map(|c| c.region.as_str());
            if origin_region.is_some() && dest_region == origin_region {
                weight *= 1.0 + option.dispatch.regional_bias;
            }
        }
        weight.max(1e-12)
    }

    /// `(destination, route miles, route leg count)` for every other city.
    fn candidates(&self, city: &str) -> Vec<Candidate> {
        let world_id = self.world as *const World as usize;
        {
            let cache = CANDIDATES_CACHE.lock();
            if let Some(cached) = cache.get(&world_id).and_then(|per| per.get(city)) {
                return cached.clone();
            }
        }
        let mut computed: Vec<Candidate> = Vec::new();
        for dest in self.world.city_names() {
            if dest == city {
                continue;
            }
            if let Ok(Some(route)) = self.world.supported_route(city, &dest, None) {
                computed.push((dest, route.miles(), route.legs.len()));
            }
        }
        CANDIDATES_CACHE
            .lock()
            .entry(world_id)
            .or_default()
            .insert(city.to_string(), computed.clone());
        computed
    }

    /// `_choose_destination`: kept for parity; the board spreads destinations
    /// up front instead.
    pub fn choose_destination(&mut self, candidates: &[Candidate], level: i64) -> Candidate {
        let mut pool: Vec<&Candidate> = candidates.iter().collect();
        if level >= 4 {
            // seasoned drivers see a dedicated cross-country slot now and then
            let long_hauls: Vec<&Candidate> = candidates
                .iter()
                .filter(|c| c.1 >= LONG_HAUL_MILES)
                .collect();
            if !long_hauls.is_empty() && self.rng.random() < 0.35 {
                pool = long_hauls;
            }
        }
        // Nearer destinations are likelier, and rookies lean harder toward short
        // hauls (squared distance falloff). Crucially the pool is never narrowed
        // to a single-leg-only set -- that locked sparse start cities into one
        // back-and-forth route. Leg count no longer gates which cities appear.
        let exponent = if level <= 2 { 2.0 } else { 1.0 };
        let weights: Vec<f64> = pool.iter().map(|c| 1.0 / c.1.powf(exponent)).collect();
        let idx = self.rng.choices_indices_weighted(&weights, 1)[0];
        pool[idx].clone()
    }

    fn choose_origin_location<'c>(
        &mut self,
        city: &'c City,
        level: i64,
        carrier_key: &str,
    ) -> &'c Location {
        let mut plausible: Vec<&Location> = city
            .locations
            .iter()
            .filter(|location| {
                location.min_level <= level
                    && !Self::cargo_for_location(location, "ships", Some(level)).is_empty()
            })
            .collect();
        if plausible.is_empty() {
            plausible = city.locations.iter().collect();
        }
        let weights: Vec<f64> = plausible
            .iter()
            .map(|location| Self::facility_weight(city, location, carrier_key))
            .collect();
        let idx = self.rng.choices_indices_weighted(&weights, 1)[0];
        plausible[idx]
    }

    fn choose_cargo_for_location(
        &mut self,
        city: &City,
        location: &Location,
        level: i64,
        carrier_key: &str,
    ) -> &'static str {
        let mut cargo_keys = Self::cargo_for_location(location, "ships", Some(level));
        if cargo_keys.is_empty() {
            cargo_keys = CARGO_CATALOG
                .values()
                .filter(|cargo| cargo.min_level <= level)
                .map(|cargo| cargo.key)
                .collect();
        }
        let weights: Vec<f64> = cargo_keys
            .iter()
            .map(|key| Self::cargo_weight(city, key, carrier_key, level))
            .collect();
        let idx = self.rng.choices_indices_weighted(&weights, 1)[0];
        cargo_keys[idx]
    }

    /// `_cargo_for_location(location, role, level)`.
    pub fn cargo_for_location(
        location: &Location,
        role: &str,
        level: Option<i64>,
    ) -> Vec<&'static str> {
        let role_values: Vec<String> = if role == "ships" {
            location.ships.clone()
        } else {
            location.receives.clone()
        };
        let role_values = if role_values.is_empty() {
            let typed: Vec<String> = facility_cargo(&location.facility_type)
                .unwrap_or_default()
                .into_iter()
                .map(str::to_string)
                .collect();
            if typed.is_empty() {
                location.cargo.clone()
            } else {
                typed
            }
        } else {
            role_values
        };
        let mut allowed: Vec<&'static str> = Vec::new();
        for key in &role_values {
            let Some(cargo) = cargo_type(key) else {
                continue;
            };
            if level.is_some_and(|level| cargo.min_level > level) {
                continue;
            }
            allowed.push(cargo.key);
        }
        allowed
    }

    fn destination_location(
        &mut self,
        city: &str,
        cargo: &CargoType,
        level: i64,
    ) -> Option<&'w Location> {
        let city_obj = self.world.cities.get(city)?;
        let locations = &city_obj.locations;
        let mut plausible: Vec<&'w Location> = locations
            .iter()
            .filter(|loc| {
                loc.min_level <= level
                    && Self::cargo_for_location(loc, "receives", Some(level)).contains(&cargo.key)
            })
            .collect();
        if plausible.is_empty() {
            plausible = locations
                .iter()
                .filter(|loc| Self::cargo_for_location(loc, "receives", None).contains(&cargo.key))
                .collect();
        }
        if plausible.is_empty() {
            return None;
        }
        let weights: Vec<f64> = plausible
            .iter()
            .map(|loc| Self::facility_weight(city_obj, loc, DEFAULT_START_KEY))
            .collect();
        let idx = self.rng.choices_indices_weighted(&weights, 1)[0];
        Some(plausible[idx])
    }

    fn facility_weight(city: &City, location: &Location, carrier_key: &str) -> f64 {
        let mut weight = FACILITY_SELECTION_WEIGHTS
            .iter()
            .find(|(k, _)| *k == location.facility_type)
            .map(|(_, w)| *w)
            .unwrap_or(0.85);
        let handled = |key: &str| {
            location.ships.iter().any(|k| k == key) || location.receives.iter().any(|k| k == key)
        };
        for tag in &city.market_tags {
            let boosted = market_tag_cargo_bonus(tag);
            if boosted.iter().any(|key| handled(key)) {
                weight += 0.25;
            }
        }
        if location.template {
            weight *= 0.9;
        }
        let option = start_option(Some(carrier_key));
        if !option.cargo_weight_bonus.is_empty()
            && option
                .cargo_weight_bonus
                .iter()
                .any(|(key, _)| handled(key))
        {
            weight += 0.2;
        }
        weight.max(0.1)
    }

    /// `_cargo_weight(city, cargo_key, carrier_key, level)`.
    pub fn cargo_weight(city: &City, cargo_key: &str, carrier_key: &str, level: i64) -> f64 {
        let mut weight = 1.0;
        for tag in &city.market_tags {
            if market_tag_cargo_bonus(tag).contains(&cargo_key) {
                weight += 0.65;
            }
        }
        let cargo = cargo_type(cargo_key).expect("a catalog cargo key");
        if cargo.endorsement.is_some() {
            // Specialized company drivers see endorsement freight favored
            // instead of rationed; junior boards keep it occasional.
            weight *= if level >= SPECIALIZED_FREIGHT_LEVEL {
                SPECIALIZED_FREIGHT_WEIGHT
            } else {
                0.8
            };
        }
        weight += start_option(Some(carrier_key)).cargo_weight_bonus_for(cargo_key);
        weight
    }

    #[allow(clippy::too_many_arguments)]
    fn make_job(
        &mut self,
        cargo: &'static CargoType,
        origin: &str,
        origin_location: &str,
        destination: &str,
        miles: f64,
        market: Option<&Market>,
        level: i64,
        origin_facility: &Location,
        destination_facility: &Location,
        carrier_key: &str,
        direct_freight: bool,
    ) -> Job {
        // Clamp to 80,000 lb GVW for a stock tractor + trailer. Heavier
        // catalog ranges exist, but a dispatched load that starts illegal
        // is a lie; the live overweight check still red-lights a truck
        // that ends up over (a heavier tractor, a test load).
        let max_tons = max_legal_cargo_tons(combination_tare_kg(&TruckSpecs::default()));
        let hi = cargo.weight_tons.1.min(max_tons);
        let lo = cargo.weight_tons.0.min(hi);
        let weight = self.rng.uniform(lo, hi);
        let rate = cargo.rate_per_mile * self.rng.uniform(0.9, 1.15);
        let mult = market.map(|m| m.multiplier(cargo.key)).unwrap_or(1.0);
        let base_pay = HOOKUP_FEE + miles * rate * (1.0 + weight / 120.0);
        let direct_mult = if direct_freight {
            DIRECT_FREIGHT_PAY_MULT
        } else {
            1.0
        };
        let pay = round_py_n(
            base_pay.max(minimum_pay_for_level(miles, level)) * mult * direct_mult,
            2,
        );
        // deadline: the honest HOS-compliant hours (driving, breaks, sleep),
        // shipper slack on top, plus a flat hour for fuel and the unexpected
        let route = self
            .world
            .supported_route(origin, destination, None)
            .ok()
            .flatten();
        let slack = self.rng.uniform(
            DEADLINE_DISPATCH_SLACK_RANGE.0,
            DEADLINE_DISPATCH_SLACK_RANGE.1,
        );
        let deadline = dispatch_deadline_hours(
            miles,
            slack,
            route.as_ref(),
            Some(self.world),
            self.hos.as_ref(),
        ) * start_option(Some(carrier_key)).dispatch.deadline_slack;
        // Speak the stretch when the driver's current clock forces a sleep a
        // fresh clock would not have needed -- the long number is the law.
        let covers_rest = match &self.hos {
            Some(hos) => {
                plan_hos(miles, route.as_ref(), Some(self.world), Some(hos)).sleeps
                    > plan_hos(miles, route.as_ref(), Some(self.world), None).sleeps
            }
            None => false,
        };
        let mut job = Job::new(
            cargo,
            weight,
            origin,
            origin_location,
            destination,
            round_py_n(miles, 1),
            pay,
            round_py_n(deadline, 1),
        );
        job.market_mult = mult;
        job.origin_type = origin_facility.facility_type.clone();
        job.destination_location = destination_facility.name.clone();
        job.destination_type = destination_facility.facility_type.clone();
        job.origin_facility_id = origin_facility.id.clone();
        job.destination_facility_id = destination_facility.id.clone();
        job.origin_locality = origin_facility.locality.clone();
        job.destination_locality = destination_facility.locality.clone();
        job.deadline_covers_rest = covers_rest;
        job.origin_spoken = self.world.spoken_city(origin, Some(true));
        job.destination_spoken = self.world.spoken_city(destination, Some(true));
        job
    }
}
