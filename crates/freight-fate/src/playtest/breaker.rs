//! Adversarial breaker battery: drive the sim in unreasonable ways, on
//! purpose (port of `tools/playtest_break.py`).
//!
//! Every scenario does something no sensible driver would do -- reverse down
//! the interstate, slam reverse at highway speed, coast a mountain in
//! neutral, dynamite the parking brake at 60 -- and then CHECKS the
//! invariants programmatically: does physics stay sane, does money/XP/HOS/rep
//! stay honest, and does the spoken text still tell a blind player the truth.
//! Run it after any feature lands to see what newly breaks.
//!
//! Scenarios are deterministic (fixed trip seed, pinned weather, no random
//! hazards or patrols unless the scenario is about them) and self-contained:
//! each builds its own app and [`DrivingState`] the way the tests do, drives
//! real `update_frame` frames, and returns CLEAN or ODD with a one-line note.
//! ODD means "a discrepancy a human should look at", not necessarily a bug --
//! the point is that the battery notices when the answer CHANGES.
//!
//! # Shape of the port
//!
//! Python registered scenarios with a decorator into a module-level dict.
//! Rust has no import side effects to rely on, so [`scenarios`] is one
//! explicit table built in [`super::break_scenarios`]. The registry order is
//! the table's order, which is the battery's run order.
//!
//! Held keys were `pygame.key.get_pressed` monkeypatched with a set; here
//! they are the app's own [`HeldKeys`][crate::app::HeldKeys], which is the
//! same thing the real loop fills in.

use crate::app::testing::TestApp;
use crate::states::base::{InputEvent, Key, Mods};
use crate::states::driving::DrivingState;
use crate::states::driving_core::DRIVE_PHASE_DELIVERY;

use ff_core::data::curves::RouteCurve;
use ff_core::models::jobs::{cargo_type, Job};
use ff_core::models::profile::Profile;
use ff_core::sim::weather::WeatherKind;

use super::harness::key_event;
use super::MPH_PER_MPS;

/// Coarse-but-stable frame step; halves the battery's wall time.
pub const DT: f64 = 1.0 / 30.0;

/// How a scenario came out.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Verdict {
    Clean,
    Odd,
    Error,
}

impl Verdict {
    pub fn as_str(self) -> &'static str {
        match self {
            Verdict::Clean => "CLEAN",
            Verdict::Odd => "ODD",
            Verdict::Error => "ERROR",
        }
    }
}

#[derive(Debug, Clone)]
pub struct Outcome {
    pub name: String,
    pub verdict: Verdict,
    pub note: String,
    pub findings: Vec<String>,
    pub transcript: Vec<String>,
}

/// One registered scenario: its name, its one-line summary, and the closure
/// that runs it.
pub struct Scenario {
    pub name: &'static str,
    pub description: &'static str,
    pub run: fn() -> Outcome,
}

/// Every scenario, in run order.
pub fn scenarios() -> &'static [Scenario] {
    super::break_scenarios::SCENARIOS
}

pub fn scenario_names() -> Vec<&'static str> {
    scenarios().iter().map(|s| s.name).collect()
}

/// Run one scenario by name; `None` when the name is unknown.
pub fn run_scenario(name: &str) -> Option<Outcome> {
    let scenario = scenarios().iter().find(|s| s.name == name)?;
    // A scenario that panics is an ERROR, not a dead battery.
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(scenario.run));
    Some(result.unwrap_or_else(|payload| Outcome {
        name: name.to_string(),
        verdict: Verdict::Error,
        note: "scenario crashed".to_string(),
        findings: vec![panic_text(&payload)],
        transcript: Vec::new(),
    }))
}

fn panic_text(payload: &Box<dyn std::any::Any + Send>) -> String {
    if let Some(text) = payload.downcast_ref::<&str>() {
        return (*text).to_string();
    }
    if let Some(text) = payload.downcast_ref::<String>() {
        return text.clone();
    }
    "panicked".to_string()
}

/// Fold rig invariant problems into the findings and pick the verdict.
pub fn outcome(name: &str, rig: &Rig, mut findings: Vec<String>, clean_note: &str) -> Outcome {
    findings.extend(rig.problems.iter().map(|p| format!("invariant: {p}")));
    let verdict = if findings.is_empty() {
        Verdict::Clean
    } else {
        Verdict::Odd
    };
    let note = findings
        .first()
        .cloned()
        .unwrap_or_else(|| clean_note.to_string());
    Outcome {
        name: name.to_string(),
        verdict,
        note,
        findings,
        transcript: rig.transcript(),
    }
}

/// A hand-built bend, for scenarios that need one at a known mile.
pub fn fabricated_curve(start_mi: f64, advisory: i64, direction: char) -> RouteCurve {
    RouteCurve {
        start_mi,
        apex_mi: start_mi + 0.1,
        end_mi: start_mi + 0.22,
        direction,
        advisory_mph: advisory,
        min_radius_ft: 250,
        deflection_deg: 130.0,
        connector: false,
    }
}

/// The keyword arguments of the Python `Rig.__init__`.
pub struct RigOptions {
    pub automatic: bool,
    pub business: Option<String>,
    pub tons: f64,
    pub seed: i64,
    pub keep_patrols: bool,
}

impl Default for RigOptions {
    fn default() -> Self {
        RigOptions {
            automatic: true,
            business: None,
            tons: 12.0,
            seed: 4242,
            keep_patrols: false,
        }
    }
}

/// One disposable app plus drive, wired for deterministic abuse.
///
/// Mirrors the test idiom: a real headless app, a fresh profile, a supported
/// route, and direct `update_frame` frames with speech captured and the
/// held-key set faked.
pub struct Rig {
    pub app: TestApp,
    pub drive: DrivingState,
    last_game_minutes: f64,
    pub problems: Vec<String>,
    problem_keys: std::collections::HashSet<String>,
}

impl Rig {
    pub fn new(opts: RigOptions) -> Rig {
        let mut app = TestApp::new();
        app.ctx.settings.automatic_transmission = opts.automatic;
        // No station machinery, no network.
        app.ctx.settings.radio_enabled = false;
        // A career's current_city is a slug ("buffalo_ny_us"). The world
        // resolves the old display name for routing, so a label here drives
        // fine and only shows up later, when a save made from this harness is
        // refused by cloud backup as an unknown city.
        let origin = app.ctx.world.resolve_city_key("Buffalo");
        let mut profile = Profile::named_in("Breaker", &origin);
        if let Some(business) = &opts.business {
            profile.business_status = business.clone();
        }
        app.ctx.profile = Some(profile);
        let route = app
            .ctx
            .world
            .supported_route("Buffalo", "Rochester", None)
            .ok()
            .flatten()
            .expect("Buffalo to Rochester is a supported route");
        let mut job = Job::new(
            cargo_type("general").expect("general freight is in the catalog"),
            opts.tons,
            "Buffalo",
            "company yard",
            "Rochester",
            route.miles(),
            1000.0,
            12.0,
        );
        job.destination_location = "Rochester freight market".to_string();
        let mut drive = DrivingState::new(
            &mut app.ctx,
            job,
            route,
            Some(opts.seed),
            DRIVE_PHASE_DELIVERY,
            None,
        );
        drive.tutorial = None;
        // Stay on the highway trip, no street chain.
        drive.departure_checked = true;
        drive.trip.hazard_check_mi = 1e18;
        drive.trip.inspection_check_mi = 1e18;
        drive.trip.conditions_check_mi = 1e18;
        drive.trip.traffic_manager.vehicles.clear();
        drive.trip.traffic_pressures.clear();
        if !opts.keep_patrols {
            drive.trip.set_patrols(Vec::new());
        }
        // Pin the weather: current stays whatever the scenario sets.
        // `forced` is the lock the Python rig faked by replacing
        // `weather.update`: the condition stays whatever the scenario sets.
        drive.weather_mut().forced = Some(WeatherKind::Clear);
        drive.weather_mut().current = WeatherKind::Clear;
        Rig {
            app,
            drive,
            last_game_minutes: 0.0,
            problems: Vec::new(),
            problem_keys: std::collections::HashSet::new(),
        }
    }

    // -- speech ------------------------------------------------------------------

    /// Everything the cab has said, event lines marked.
    ///
    /// The capture sits at the VOICE layer, not on `ctx.say`: the driving
    /// verbosity ladder's gate and the event pacer's repeat/backlog handling
    /// both live inside `GameContext::say`/`say_event`, and a rig that
    /// replaced those (the old approach) showed what the game would say with
    /// no rung applied and no repeat suppression running, not what a player
    /// actually hears.
    pub fn transcript(&self) -> Vec<String> {
        self.app.speech().transcript_lines()
    }

    pub fn said(&self, phrase: &str) -> usize {
        self.transcript()
            .iter()
            .filter(|line| line.contains(phrase))
            .count()
    }

    pub fn lines_with(&self, phrase: &str) -> Vec<String> {
        self.transcript()
            .into_iter()
            .filter(|line| line.contains(phrase))
            .collect()
    }

    // -- driving -----------------------------------------------------------------

    pub fn prepare(&mut self, speed_mph: f64, gear: Option<i32>) {
        self.drive.truck_mut().start_engine();
        self.drive.truck_mut().set_air_ready(false);
        self.drive.truck_mut().velocity_mps = speed_mph / MPH_PER_MPS;
        match gear {
            Some(gear) => self.drive.truck_mut().transmission.gear = gear,
            None => {
                if self.drive.truck().transmission.automatic && speed_mph > 5.0 {
                    self.drive.truck_mut().transmission.gear = 8;
                }
            }
        }
    }

    pub fn press(&mut self, key: Key) {
        let event: InputEvent = key_event(key, None);
        self.drive.handle_key_event(&mut self.app.ctx, &event);
        self.app.ctx.run_deferred();
    }

    pub fn hold(&mut self, key: Key) {
        self.app.ctx.input.press(key, Mods::NONE);
    }

    pub fn release(&mut self, key: Key) {
        self.app.ctx.input.release(key, Mods::NONE);
    }

    /// Run full `update_frame` frames; returns frames actually run. `until`
    /// stops early the first time it answers true.
    pub fn step(&mut self, frames: usize, dt: f64, until: Option<&dyn Fn(&Rig) -> bool>) -> usize {
        for i in 0..frames {
            self.drive.update_frame(&mut self.app.ctx, dt);
            self.app.ctx.run_deferred();
            if i % 10 == 0 {
                self.check_invariants();
            }
            if until.is_some_and(|f| f(self)) {
                self.check_invariants();
                return i + 1;
            }
        }
        self.check_invariants();
        frames
    }

    /// `step(frames)` at the battery's default step, no early exit.
    pub fn run_frames(&mut self, frames: usize) -> usize {
        self.step(frames, DT, None)
    }

    // -- invariants ----------------------------------------------------------------

    fn problem(&mut self, key: &str, text: String) {
        if self.problem_keys.insert(key.to_string()) {
            self.problems.push(text);
        }
    }

    pub fn check_invariants(&mut self) {
        let speed = self.drive.truck().velocity_mps;
        if !speed.is_finite() {
            self.problem("speed", format!("speed went non-finite: {speed}"));
        }
        let (money, fatigue) = match &self.app.ctx.profile {
            Some(profile) => (profile.money, profile.fatigue),
            None => (0.0, 0.0),
        };
        if !money.is_finite() {
            self.problem("money", format!("money went non-finite: {money}"));
        }
        let position = self.drive.trip.position_mi;
        let total = self.drive.trip.total_miles();
        if !(0.0..=total + 1e-6).contains(&position) {
            self.problem(
                "pos",
                format!("position {position:.2} outside [0, {total:.2}]"),
            );
        }
        let minutes = self.drive.trip.game_minutes;
        if minutes < self.last_game_minutes - 1e-9 {
            self.problem("clock", "trip clock ran backward".to_string());
        }
        self.last_game_minutes = minutes;
        let truck = self.drive.truck();
        let bands = [
            ("damage", truck.damage_pct),
            ("tire wear", truck.tire_wear_pct),
            ("brake wear", truck.brake_wear_pct),
            ("engine wear", truck.engine_wear_pct),
        ];
        for (label, value) in bands {
            if !(0.0..=100.0 + 1e-6).contains(&value) {
                self.problem(label, format!("{label} out of range: {value}"));
            }
        }
        let (fuel, tank) = {
            let truck = self.drive.truck();
            (truck.fuel_gal, truck.specs.fuel_tank_gal)
        };
        if !(0.0..=tank + 1e-6).contains(&fuel) {
            self.problem("fuel", format!("fuel out of range: {fuel}"));
        }
        if !(0.0..=100.0 + 1e-6).contains(&fatigue) {
            self.problem("fatigue", format!("fatigue out of range: {fatigue}"));
        }
    }
}

/// Print the battery's summary table the way the Python CLI did.
pub fn print_summary(outcomes: &[Outcome]) {
    println!();
    println!("{}", "=".repeat(100));
    println!("{:<34} {:<8} note", "scenario", "verdict");
    println!("{}", "-".repeat(100));
    for outcome in outcomes {
        let note = outcome.note.replace('\n', " ");
        let note: String = note.chars().take(120).collect();
        println!(
            "{:<34} {:<8} {note}",
            outcome.name,
            outcome.verdict.as_str()
        );
    }
    println!("{}", "=".repeat(100));
    let odd = outcomes
        .iter()
        .filter(|o| o.verdict == Verdict::Odd)
        .count();
    let err = outcomes
        .iter()
        .filter(|o| o.verdict == Verdict::Error)
        .count();
    println!(
        "{} scenarios: {} clean, {odd} odd, {err} errors",
        outcomes.len(),
        outcomes.len() - odd - err
    );
}
