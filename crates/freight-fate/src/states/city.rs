//! Terminal hub: dispatch board, garage, upgrades, trucks, and route
//! selection (port of `freight_fate/states/city.py`).
//!
//! The Python module was one 2000-line file; here it is split by screen:
//! [`CityMenuState`] lives in `city/terminal.rs`, the dispatch board and its
//! detail reader in `city/board.rs`, the terminal's Time and weather readout
//! in `city/weather.rs`, and the two small side menus (bobtail destination,
//! paying down a balance) in `city/extras.rs`. The free functions the tests
//! and the other screens reach for -- the cache key, opening the freight
//! market, the assigned reposition roll -- stay here, as do the re-exports
//! the Python module made (`from .city_pickup import ...`,
//! `from .city_business import ...`) so `states::city::X` resolves the way
//! `freight_fate.states.city.X` did.
//!
//! # Placeholders
//!
//! Screens owned by other ports (the driving state, the main menu and its
//! settings screen, career stats, the logbook, the setback notice) are not
//! on this branch yet. Every such hand-off goes through [`todo_state`], and
//! the one that matters most -- dispatch handing the wheel to
//! `DrivingState` -- goes through a single [`launch_driving`] so the lead
//! swaps one function when the driving port lands.

use std::collections::HashMap;
use std::sync::Mutex;

use once_cell::sync::Lazy;
use serde_json::{Map, Value};

use ff_core::data::world::World;
use ff_core::data::world_models::{HomeTerminal, Route};
use ff_core::models::business::{is_owner_operator, COMPANY_DRIVER, INDEPENDENT_AUTHORITY};
use ff_core::models::career_objectives::career_objective;
use ff_core::models::career_training::{
    is_company_training_profile, training_guidance, TrainingStage,
};
use ff_core::models::enforcement;
use ff_core::models::jobs::{
    board_offer_count, job_from_payload, job_payload, make_reposition_job, normalize_job_cities,
    Job, JobBoard, OfferOptions,
};
use ff_core::models::profile::Profile;
use ff_core::models::start_options::option_for_profile;
use ff_core::music::crc32;
use ff_core::playtest_levers::{forced_dispatch_destination, resolve_city_forgiving};
use ff_core::pyfmt::{fmt_grouped, py_int};
use ff_core::pyrandom::PyRandom;

use crate::app::{GameContext, Say};
use crate::states::base::{InputEvent, Key, Menu, MenuItem, SimpleMenuState};

mod board;
mod extras;
mod terminal;
mod weather;

pub use board::{
    describe_job, locked_reason, trailer_note, JobBoardState, JobDetailState,
    JOB_BOARD_INTRO_HELP,
};
pub use extras::{BobtailDestState, PayDebtState};
pub use terminal::CityMenuState;

// `from .city_pickup import ...` / `from .city_business import ...`: the
// Python module re-exported these, and the tests import them from here.
pub use crate::states::city_business::{
    BusinessStatusState, EndorsementCourseState, TrailerProgramState, TruckShopState,
    UpgradeShopState,
};
pub use crate::states::city_garage::GarageState;
pub use crate::states::city_pickup::{
    job_origin_exists, pickup_snapshot, route_planning_summary, PickupFacilityState,
    RouteSelectState, PICKUP_CHECK_IN_MIN, PICKUP_LOADING_MIN,
};

// -- the loaded career --------------------------------------------------------------

/// `ctx.profile` where the Python read it unguarded: every screen under the
/// terminal runs with a career loaded, and reaching one without is the same
/// programming error an `AttributeError` on `None` was.
pub(crate) fn profile(ctx: &GameContext) -> &Profile {
    ctx.profile
        .as_ref()
        .expect("the terminal screens run with a loaded career")
}

pub(crate) fn profile_mut(ctx: &mut GameContext) -> &mut Profile {
    ctx.profile
        .as_mut()
        .expect("the terminal screens run with a loaded career")
}

/// The terminal the truck is parked at. An unknown current city is a data
/// bug the Python surfaced as `KeyError`; here it falls back to a plain
/// "Terminal" rather than taking the hub screen down.
pub(crate) fn home_terminal(ctx: &GameContext) -> HomeTerminal {
    let city = &profile(ctx).current_city;
    ctx.world
        .home_terminal(city)
        .unwrap_or_else(|_| HomeTerminal::new("Terminal", city, "", "yard"))
}

/// Python `str.capitalize()`: first character upper, the rest lower.
pub(crate) fn py_capitalize(text: &str) -> String {
    ff_core::data::world_models::py_capitalize(text)
}

pub(crate) fn record_city_duty(
    ctx: &mut GameContext,
    status: &str,
    start_hour: f64,
    end_hour: f64,
    note: &str,
) {
    if ctx.profile.is_none() {
        return;
    }
    let terminal = home_terminal(ctx);
    profile_mut(ctx)
        .duty_log
        .record(status, start_hour, end_hour, &terminal.name, note);
}

/// 10-hour sleeps required to cover `drive_h`, given the driving hours left
/// in the current shift and full-shift capacity after each sleep.
pub(crate) fn sleeps_needed(drive_h: f64, first_shift_h: f64, shift_h: f64) -> i64 {
    if drive_h <= first_shift_h + 1e-9 {
        return 0;
    }
    (((drive_h - first_shift_h) / shift_h - 1e-9).ceil() as i64).max(1)
}

// Empty-drive range for shopping another city's board.
pub const BOBTAIL_RANGE_MI: f64 = 400.0;

// Company drivers don't get to bobtail on a whim (that's the owner-operator
// menu item above); instead dispatch occasionally sends them empty to a
// nearby city where freight is thicker (ROADMAP: "Company drivers get
// ASSIGNED repositions"). Roughly one board in eight-to-ten -- often enough
// to matter, rare enough that it reads as an occasional dispatch call, not
// the norm.
pub const ASSIGNED_REPOSITION_BOARD_CHANCE: f64 = 1.0 / 9.0;
// How many of the nearest reachable cities are even considered as reposition
// destinations, before freight density narrows that down further.
pub const ASSIGNED_REPOSITION_CANDIDATE_COUNT: usize = 3;

// How long a manual "Save game" waits for its cloud backup result before
// handing the attempt back to the background retry. Long enough for a normal
// round trip, short enough that a dead network never holds the answer hostage.
pub const BACKUP_RESULT_WAIT_S: f64 = 10.0;

pub fn first_dispatch_done(profile: &Profile) -> bool {
    profile.achievements.iter().any(|a| a == "first_dispatch")
}

// Gated off the 1.9 release line (owner + Josh, 2026-07-27): the school is
// not finished and 1.9 is feature-frozen. The code stays -- reverting
// woven-in work mid-freeze invites regressions -- and the 2.0 line flips
// this flag to finish it properly.
pub const DRIVING_SCHOOL_ENABLED: bool = false;

pub fn first_day_guidance_active(profile: &Profile) -> bool {
    let deliveries = profile.career.deliveries;
    !first_dispatch_done(profile) && deliveries <= 0
}

pub fn first_day_orientation_message(ctx: &GameContext, prefix: &str) -> String {
    let p = profile(ctx);
    let terminal = home_terminal(ctx);
    let option = option_for_profile(p);
    let location = format!(
        "{} in the {} service area",
        terminal.spoken_name(),
        p.current_city
    );
    if option.is_owner_operator() {
        return format!(
            "{prefix}First-day briefing: you are leased to {} \
             and parked at {location}. You own a brand-new truck with a full \
             tank, have {} dollars of working capital, and \
             fuel, repairs, truck wear, trailer programs, and business \
             reserves come out of \
             your cash. Your first objective is to open the dispatch board, \
             choose an unlocked load with a deadline you can protect, and get \
             to the shipper without burning your cushion.",
            option.carrier_name,
            fmt_grouped(p.money, 0)
        );
    }
    format!(
        "{prefix}First-day briefing: welcome aboard {}. \
         Your assigned company tractor is parked at {location}; the carrier \
         covers normal fuel, repairs, insurance, and trailer support. Your \
         starter dispatch style is {}. As a new \
         hire, dispatch assigns your load and your route; you earn load \
         choice with seniority, and refusing an assignment goes on your \
         service record. Your first objective is to open the dispatch \
         board, accept the assigned load, deadhead to the shipper, and \
         deliver cleanly to start building your record with dispatch.",
        option.carrier_name,
        option.dispatch.summary()
    )
}

/// What the terminal says about the first-day / career objective on entry
/// (the `first_day` clause of `CityMenuState.announce_entry`).
pub(crate) fn terminal_objective_clause(p: &Profile) -> String {
    if first_day_guidance_active(p) {
        let guidance = if is_company_training_profile(p) {
            Some(training_guidance(p))
        } else {
            None
        };
        if let Some(guidance) = guidance.filter(|g| g.stage == TrainingStage::FirstDispatch) {
            return format!(
                " First-day objective: open the dispatch board and accept \
                 your assigned {} load. \
                 Dispatch assigns both load and route while you are a \
                 new hire.",
                guidance.recommendation_label
            );
        }
        if !is_company_training_profile(p) {
            return " First-day objective: open the dispatch board and choose \
                    an unlocked load without burning your cash cushion."
                .to_string();
        }
        let objective = career_objective(p);
        return format!(
            " Career objective: {} Recommended dispatch: {}.",
            objective.terminal_text, objective.recommendation
        );
    }
    if !first_dispatch_done(p) && is_company_training_profile(p) {
        let objective = career_objective(p);
        return format!(
            " Career objective: {} Recommended dispatch: {}.",
            objective.terminal_text, objective.recommendation
        );
    }
    format!(" Career objective: {}", career_objective(p).terminal_text)
}

// -- the dispatch board cache -------------------------------------------------------

/// The cache key a stored board is valid under: a JSON object, because it
/// is stored beside the board in the save and compared whole on reopen.
pub fn dispatch_cache_key(p: &Profile) -> Value {
    let mut endorsements: Vec<String> = p
        .career
        .endorsements()
        .into_iter()
        .map(str::to_string)
        .collect();
    endorsements.sort();
    let mut trailer_programs = p.trailer_programs.clone();
    trailer_programs.sort();
    let mut key = Map::new();
    key.insert("city".into(), Value::from(p.current_city.clone()));
    key.insert("market_day".into(), Value::from(p.market_day()));
    key.insert("market_seed".into(), Value::from(p.market.seed));
    key.insert("market_state_day".into(), Value::from(p.market.day));
    key.insert(
        "business_status".into(),
        Value::from(p.business_status.clone()),
    );
    key.insert("carrier_key".into(), Value::from(p.carrier_key.clone()));
    key.insert(
        "authority_readiness".into(),
        Value::from(p.authority_readiness),
    );
    key.insert("trailer_programs".into(), Value::from(trailer_programs));
    key.insert("level".into(), Value::from(p.career.level()));
    key.insert("endorsements".into(), Value::from(endorsements));
    key.insert(
        "count".into(),
        Value::from(board_offer_count(p.career.level()) as i64),
    );
    // A board cached before dispatch lost faith in you must not outlive
    // the trust that built it.
    key.insert(
        "trust".into(),
        Value::from(enforcement::trust_band(p.career.reputation)),
    );
    key.insert(
        "force_dest".into(),
        Value::from(forced_dispatch_destination()),
    );
    Value::Object(key)
}

/// Python `repr(sorted(key.items()))` for the cache key above: the string
/// the reposition roll is seeded from, so the same board rolls the same way
/// here as it did there.
fn py_repr_sorted_items(key: &Value) -> String {
    fn repr_str(s: &str) -> String {
        if s.contains('\'') && !s.contains('"') {
            format!("\"{s}\"")
        } else {
            format!("'{}'", s.replace('\\', "\\\\").replace('\'', "\\'"))
        }
    }
    fn repr_value(v: &Value) -> String {
        match v {
            Value::Bool(true) => "True".to_string(),
            Value::Bool(false) => "False".to_string(),
            Value::Null => "None".to_string(),
            Value::Number(n) => n.to_string(),
            Value::String(s) => repr_str(s),
            Value::Array(items) => {
                let parts: Vec<String> = items.iter().map(repr_value).collect();
                format!("[{}]", parts.join(", "))
            }
            Value::Object(map) => {
                let parts: Vec<String> = map
                    .iter()
                    .map(|(k, v)| format!("{}: {}", repr_str(k), repr_value(v)))
                    .collect();
                format!("{{{}}}", parts.join(", "))
            }
        }
    }
    let Some(map) = key.as_object() else {
        return repr_value(key);
    };
    let mut items: Vec<(&String, &Value)> = map.iter().collect();
    items.sort_by(|a, b| a.0.cmp(b.0));
    let parts: Vec<String> = items
        .iter()
        .map(|(k, v)| format!("({}, {})", repr_str(k), repr_value(v)))
        .collect();
    format!("[{}]", parts.join(", "))
}

/// Open the dispatch board: restore the cached board when it is still
/// current, else build a fresh one and cache it. Pushes the board and
/// returns its jobs.
pub fn open_freight_market(ctx: &mut GameContext) -> Vec<Job> {
    let world = ctx.world;
    let (key, cache, hos) = {
        let p = profile_mut(ctx);
        let market_changed = p.market.advance_to(p.market_day());
        let key = dispatch_cache_key(p);
        let cache = if market_changed {
            None
        } else {
            p.dispatch_board_cache.clone()
        };
        (key, cache, p.hos.clone())
    };
    let mut board = JobBoard::new(world, None, Some(&hos));
    let mut lever_note = String::new();
    let mut jobs: Option<Vec<Job>> = None;
    if let Some(cache) = cache.as_ref().and_then(Value::as_object) {
        if !cache.is_empty() && cache.get("key") == Some(&key) {
            // Cached payloads may predate the slug migration; normalize their
            // city references so a restored board keeps resolving.
            let restored: Option<Vec<Job>> = cache
                .get("jobs")
                .and_then(Value::as_array)
                .map(|payloads| {
                    payloads
                        .iter()
                        .map(|payload| {
                            let mut job = job_from_payload(payload.as_object()?)?;
                            normalize_job_cities(&mut job, world);
                            Some(job)
                        })
                        .collect::<Option<Vec<Job>>>()
                })
                .unwrap_or(Some(Vec::new()));
            // A board cached into the save can outlive the world it was built
            // from: an update that retires a pickup facility leaves an offer
            // nobody can be sent to, and accepting it is where that fails. One
            // stale offer retires the whole cached board.
            if let Some(restored) = restored {
                if restored.iter().all(|job| job_origin_exists(job, world)) {
                    jobs = Some(restored);
                }
            }
        }
    }
    let jobs = match jobs {
        Some(jobs) => jobs,
        None => {
            let mut fresh = {
                let p = profile(ctx);
                let endorsements: Vec<&str> = p.career.endorsements().into_iter().collect();
                board.offers(
                    &p.current_city,
                    &endorsements,
                    OfferOptions {
                        // How much freight dispatch will show you is a matter of
                        // trust, and trust slides with reputation the whole way
                        // down.
                        count: enforcement::board_offers_for_reputation(
                            board_offer_count(p.career.level()) as i64,
                            p.career.reputation,
                        )
                        .max(0) as usize,
                        level: p.career.level(),
                        market: Some(&p.market),
                        carrier_key: Some(&p.carrier_key),
                        direct_freight: p.business_status == INDEPENDENT_AUTHORITY,
                    },
                )
            };
            let reposition = assigned_reposition_for_board(ctx, &board, &key);
            if let Some(reposition) = reposition {
                if !fresh.is_empty() {
                    // Replaces a slot rather than adding one: the board still shows
                    // exactly as many entries as the player's level and trust earn.
                    // The farthest ordinary offer goes -- the one least likely to be
                    // what a driver actually wanted -- and the list is re-sorted by
                    // distance the same way board.offers() leaves it.
                    let last = fresh.len() - 1;
                    fresh[last] = reposition;
                    sort_by_distance(&mut fresh);
                }
            }
            lever_note = add_forced_board_job(ctx, &mut board, &mut fresh);
            let payloads: Vec<Value> = fresh
                .iter()
                .map(|job| Value::Object(job_payload(job)))
                .collect();
            let mut cache = Map::new();
            cache.insert("key".into(), key.clone());
            cache.insert("jobs".into(), Value::Array(payloads));
            profile_mut(ctx).dispatch_board_cache = Some(Value::Object(cache));
            ctx.save_profile();
            fresh
        }
    };
    ctx.push_state(JobBoardState::new(ctx, jobs.clone()));
    if !lever_note.is_empty() {
        // Queued behind the board announcement, which interrupts.
        ctx.say_with(lever_note, Say::queued());
    }
    jobs
}

pub(crate) fn sort_by_distance(jobs: &mut [Job]) {
    jobs.sort_by(|a, b| {
        a.distance_mi
            .partial_cmp(&b.distance_mi)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
}

/// `(city key, miles, leg count)` for every city reachable from `city` on a
/// supported route, the way `JobBoard._candidates` computed it.
// TODO(lead): belongs in ff_core::models::jobs::JobBoard -- `candidates` is
// private there; make it pub and delete this copy.
pub(crate) fn board_candidates(world: &World, city: &str) -> Vec<(String, f64, usize)> {
    type CandidateCache = HashMap<usize, HashMap<String, Vec<(String, f64, usize)>>>;
    static CACHE: Lazy<Mutex<CandidateCache>> = Lazy::new(|| Mutex::new(HashMap::new()));
    let city = world.resolve_city_key(city);
    let world_id = world as *const World as usize;
    if let Some(cached) = CACHE
        .lock()
        .unwrap_or_else(|e| e.into_inner())
        .get(&world_id)
        .and_then(|per| per.get(&city))
    {
        return cached.clone();
    }
    let mut computed: Vec<(String, f64, usize)> = Vec::new();
    for dest in world.city_names() {
        if dest == city {
            continue;
        }
        if let Ok(Some(route)) = world.supported_route(&city, &dest, None) {
            computed.push((dest, route.miles(), route.legs.len()));
        }
    }
    CACHE
        .lock()
        .unwrap_or_else(|e| e.into_inner())
        .entry(world_id)
        .or_default()
        .insert(city, computed.clone());
    computed
}

/// Occasionally slot a carrier-ASSIGNED reposition onto a company
/// driver's board (ROADMAP: "Company drivers get ASSIGNED repositions").
///
/// Owner-operators already have the self-serve "Bobtail to a nearby city"
/// menu item for repositioning on their own dime; this is dispatch doing it
/// TO a company driver instead, so it only ever fires for company drivers.
/// Seeded off the board's own cache key so the same board shows (or does
/// not show) the same reposition every time it is reopened, exactly like
/// the rest of the cached offers -- see dispatch_cache_key and
/// ASSIGNED_REPOSITION_BOARD_CHANCE.
pub fn assigned_reposition_for_board(
    ctx: &GameContext,
    _board: &JobBoard<'_>,
    key: &Value,
) -> Option<Job> {
    let p = profile(ctx);
    let status = if p.business_status.is_empty() {
        COMPANY_DRIVER
    } else {
        p.business_status.as_str()
    };
    if is_owner_operator(status) {
        return None;
    }
    if p.career.deliveries < 1 {
        // A brand-new hire's first dispatch is freight, never a deadhead --
        // no yard repositions a driver it has not yet put a load behind.
        // This also keeps the new-career flow deterministic: the roll below
        // hashes the market seed, so without this gate roughly one new
        // career in nine started on a reposition instead of a pickup.
        return None;
    }
    let seed = crc32(py_repr_sorted_items(key).as_bytes());
    let mut rng = PyRandom::new_from_u64(u64::from(seed));
    if rng.random() >= ASSIGNED_REPOSITION_BOARD_CHANCE {
        return None;
    }
    let world = ctx.world;
    let mut candidates = board_candidates(world, &p.current_city);
    candidates.sort_by(|a, b| {
        a.1.partial_cmp(&b.1)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    let mut nearby: Vec<(String, f64, usize)> = candidates
        .iter()
        .filter(|c| c.1 <= BOBTAIL_RANGE_MI)
        .cloned()
        .collect();
    if nearby.is_empty() {
        // never strand a remote start: offer the nearest few
        nearby = candidates
            .iter()
            .take(ASSIGNED_REPOSITION_CANDIDATE_COUNT)
            .cloned()
            .collect();
    }
    if nearby.is_empty() {
        return None;
    }
    // Cheap proxy for "the board there would have more jobs": how many
    // freight locations that city has, without actually generating a
    // second board's worth of offers just to compare counts.
    let freight_density = |city_key: &str| -> i64 {
        world
            .city(city_key)
            .map(|c| c.locations.len() as i64)
            .unwrap_or(0)
    };
    nearby.sort_by(|a, b| {
        (-freight_density(&a.0))
            .cmp(&-freight_density(&b.0))
            .then(a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal))
    });
    let thickest: Vec<(String, f64, usize)> = nearby
        .into_iter()
        .take(ASSIGNED_REPOSITION_CANDIDATE_COUNT)
        .collect();
    let destination = rng.choice(&thickest).0.clone();
    make_reposition_job(
        world,
        &p.current_city,
        &destination,
        true,
        Some(&p.carrier_key),
    )
}

/// FREIGHT_FATE_FORCE_DEST playtest lever: guarantee one load to the
/// forced destination on a freshly built board. Returns the spoken note.
fn add_forced_board_job(
    ctx: &GameContext,
    board: &mut JobBoard<'_>,
    jobs: &mut Vec<Job>,
) -> String {
    let dest = forced_dispatch_destination();
    if dest.is_empty() {
        return String::new();
    }
    let world = ctx.world;
    let p = profile(ctx);
    let key = resolve_city_forgiving(world, &dest);
    if !world.cities.contains_key(&key) {
        return format!("Playtest lever: no city called {dest} to dispatch to.");
    }
    if key == world.resolve_city_key(&p.current_city) {
        return String::new();
    }
    let spoken = world.spoken_city(&key, Some(true));
    if jobs
        .iter()
        .any(|job| world.resolve_city_key(&job.destination) == key)
    {
        return format!("Playtest lever: the board already offers {spoken}.");
    }
    let endorsements: Vec<&str> = p.career.endorsements().into_iter().collect();
    let job = board.offer_to(
        &p.current_city,
        &key,
        &endorsements,
        OfferOptions {
            count: 0,
            level: p.career.level(),
            market: Some(&p.market),
            carrier_key: Some(&p.carrier_key),
            direct_freight: p.business_status == INDEPENDENT_AUTHORITY,
        },
    );
    let Some(job) = job else {
        return format!("Playtest lever: no supported dispatch from here to {spoken}.");
    };
    jobs.push(job);
    sort_by_distance(jobs);
    format!("Playtest lever: added a load to {spoken} to the board.")
}

// -- hand-offs to screens other ports own ---------------------------------------------

/// A stand-in for a screen another port owns (main menu, settings, career
/// stats, the logbook, the setback notice, the driving school, the driving
/// state). One row, Escape pops it, so every flow through the terminal still
/// lands somewhere that speaks and can be left.
pub fn todo_state(name: &str) -> SimpleMenuState {
    SimpleMenuState::new(
        name,
        vec![
            MenuItem::new("Back", |s: &mut SimpleMenuState, ctx| s.go_back(ctx))
                .help("This screen arrives with its own port."),
        ],
    )
}

// TODO(lead): DRIVE_PHASE_* belong in states::driving_core; replace these
// with the real constants when that port lands.
pub const DRIVE_PHASE_PICKUP: &str = "pickup";
pub const DRIVE_PHASE_DELIVERY: &str = "delivery";

/// What a loaded departure carries onto the road (`start_loaded_drive`):
/// the air-brake snapshot, the engine state, the speed-control session and
/// the refused trailer, restored onto the new `DrivingState` so the truck
/// leaves the dock exactly as it sat there.
#[derive(Debug, Clone, Default)]
pub struct LoadedDepartureResume {
    pub air_brake: Option<Value>,
    pub engine_on: bool,
    pub speed_control_armed: bool,
    pub speed_control_target_mph: Option<f64>,
    pub trailer_refused: bool,
}

/// The line spoken (interrupting) once the trip snapshot is saved, just
/// before the driving state takes the screen.
pub enum LaunchAnnouncement {
    /// Spoken as-is.
    Line(String),
    /// `start_loaded_drive`: `lead` + `route_departure_summary` +
    /// `driving.trip.next_navigation_context()` + the engine tail; see
    /// [`loaded_departure_line`].
    LoadedDeparture { lead: String },
}

/// Everything dispatch hands the driving state: the Python
/// `DrivingState(ctx, job, route, phase=..., trip_seed=...)` call plus the
/// snapshot-and-announce that followed it at every call site.
pub struct DrivingLaunch {
    pub job: Job,
    pub route: Route,
    pub trip_seed: Option<i64>,
    /// `DRIVE_PHASE_PICKUP` for the deadhead to the shipper,
    /// `DRIVE_PHASE_DELIVERY` otherwise.
    pub phase: &'static str,
    pub start_hour: Option<f64>,
    /// Set only by `start_loaded_drive`.
    pub resume: Option<LoadedDepartureResume>,
    pub announcement: LaunchAnnouncement,
}

impl DrivingLaunch {
    pub fn new(
        job: Job,
        route: Route,
        phase: &'static str,
        announcement: LaunchAnnouncement,
    ) -> Self {
        DrivingLaunch {
            job,
            route,
            trip_seed: None,
            phase,
            start_hour: None,
            resume: None,
            announcement,
        }
    }
}

/// The departure line of `start_loaded_drive`: `lead`, the route summary,
/// the trip's first navigation context, and either "Departing now." or the
/// start-up instructions.
pub fn loaded_departure_line(
    ctx: &GameContext,
    lead: &str,
    route: &Route,
    engine_on: bool,
    next_context: &str,
) -> String {
    // Never "Departing now" over a dead engine: a driver who shut down at the
    // shipper leaves on a real start-up, and the line has to say so or the
    // truck simply sits there in silence.
    let tail = if engine_on {
        "Departing now.".to_string()
    } else {
        format!(
            "The engine is off. Press {} to start it, \
             wait for air pressure, then press {} \
             to release the parking brake.",
            ctx.control_hint("engine"),
            ctx.control_hint("parking_brake")
        )
    };
    format!(
        "{lead}{} {next_context} {tail}",
        crate::states::city_pickup::route_departure_summary(route, &ctx.settings)
    )
}

/// Hand the wheel to the driving state.
///
/// Python, at every call site: build the `DrivingState`, restore what
/// `resume` carries onto it, `profile.active_trip = driving.snapshot()`,
/// `save_profile()`, speak the announcement with `interrupt=True`, push the
/// state. Until the driving port lands this saves, speaks, and pushes a
/// placeholder; the caller has already cleared `dispatch_board_cache`
/// where the Python did.
// TODO(lead): swap the body for `DrivingState::new(ctx, launch.job,
// launch.route, launch.phase, launch.trip_seed, launch.start_hour)` plus the
// resume/snapshot/say/push sequence above; nothing else in the city screens
// needs to change.
pub fn launch_driving(ctx: &mut GameContext, launch: DrivingLaunch) {
    ctx.save_profile();
    let line = match launch.announcement {
        LaunchAnnouncement::Line(line) => line,
        LaunchAnnouncement::LoadedDeparture { lead } => {
            let engine_on = launch.resume.as_ref().is_some_and(|r| r.engine_on);
            loaded_departure_line(ctx, &lead, &launch.route, engine_on, "")
        }
    };
    ctx.say(&line);
    ctx.push_state(todo_state("Driving"));
}

// -- menu plumbing --------------------------------------------------------------------

/// The base `MenuState.handle_event`, for screens that take a key of their
/// own first (F1 on the dispatch board, W on route planning) and hand the
/// rest back. A trait default cannot be called from its own override, so the
/// fall-through lives here.
// TODO(lead): belongs in states::base::menu as a free function the Menu
// default delegates to, so an override can fall through without a copy.
pub(crate) fn base_menu_handle_event<S: Menu>(
    menu: &mut S,
    ctx: &mut GameContext,
    event: &InputEvent,
) {
    let Some((key, _mods, text)) = event.key_down() else {
        return;
    };
    match key {
        Key::Down => menu.move_by(ctx, 1),
        Key::Up => menu.move_by(ctx, -1),
        Key::Home => menu.jump(ctx, 0),
        Key::End => {
            let last = menu.menu().items.len().saturating_sub(1);
            menu.jump(ctx, last);
        }
        Key::Return | Key::Space | Key::KpEnter => menu.activate(ctx),
        Key::Escape => menu.go_back(ctx),
        Key::F1 => {
            let help = menu.current_help(ctx);
            ctx.say(&help);
        }
        Key::LCtrl | Key::RCtrl => ctx.stop_speech(),
        _ => {
            if let Some(ch) = text.filter(|ch| ch.is_alphanumeric()) {
                let lower: String = ch.to_lowercase().collect();
                menu.first_letter_jump(ctx, &lower);
            }
        }
    }
}

/// The base `MenuState.enter`: rebuild the rows keeping the cursor, play
/// the open sound, announce. For screens whose `enter` does work first.
pub(crate) fn base_menu_enter<S: Menu>(menu: &mut S, ctx: &mut GameContext) {
    menu.refresh(ctx, true);
    if let Some(key) = menu.menu().open_sound_key.clone() {
        ctx.audio.play(&key);
    }
    menu.announce_entry(ctx);
}

/// The base `MenuState.current_help`, for screens that prefix it.
pub(crate) fn base_menu_current_help<S: Menu>(menu: &S, ctx: &GameContext) -> String {
    let core = menu.menu();
    if core.items.is_empty() {
        return core.intro_help.clone();
    }
    let item = &core.items[core.index];
    let help = item.help_text(menu, ctx);
    if help.is_empty() {
        format!("{}.", item.text(menu, ctx))
    } else {
        help
    }
}

/// Python `int(x)` for a game-hours float, for the weather seed.
pub(crate) fn game_hours_int(hours: f64) -> i64 {
    py_int(hours)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sleeps_needed_counts_whole_rests() {
        assert_eq!(sleeps_needed(5.0, 11.0, 11.0), 0);
        assert_eq!(sleeps_needed(12.0, 11.0, 11.0), 1);
        assert_eq!(sleeps_needed(25.0, 3.0, 11.0), 2);
    }

    #[test]
    fn cache_key_repr_matches_python() {
        let mut key = Map::new();
        key.insert("city".into(), Value::from("chicago_il_us"));
        key.insert("authority_readiness".into(), Value::from(false));
        key.insert("endorsements".into(), Value::Array(vec![]));
        key.insert("level".into(), Value::from(1));
        assert_eq!(
            py_repr_sorted_items(&Value::Object(key)),
            "[('authority_readiness', False), ('city', 'chicago_il_us'), ('endorsements', []), ('level', 1)]"
        );
    }
}
