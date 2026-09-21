//! Shared rigging for the `test_driving_cruise_weather.py` port.
//!
//! # What replaced the monkeypatches
//!
//! The Python file reached a deterministic road by patching methods on the
//! live trip:
//!
//! | Python | here |
//! |---|---|
//! | `open_limits(driving)` -- `speed_limit_at -> (200, None)` | [`bench_road`] bakes a 200 mph `SpeedLimitSample` on the leg, which is the record `speed_limit_at` reads |
//! | `trip.speed_limit_at = lambda m: (L, "reason")` | a [`Zone`] over the whole road, which is how `speed_limit_at` returns a reason at all |
//! | `trip.grade_at = lambda m: g` | a baked `GradeSegment` over the whole leg |
//! | `trip.traffic_context = lambda: None` | an empty traffic manager with the rolling bubble off |
//! | `pygame.key.get_pressed` -> `NoKeys`/`Keys` | [`hold`] / [`release_keys`] writing the drive's real held-key set |
//!
//! Rust has no seam for an inherent method, so each of these builds the road
//! that ANSWERS the way the patch did. That is stricter than the patch was:
//! the whole trip is fixed rather than whatever route dispatch drew.
//!
//! # Where the transcript comes from
//!
//! Python patched `ctx.say`/`ctx.say_event` and so recorded every line the
//! states SUBMITTED. The harness here records at `ctx.speech`, below the
//! driving verbosity ladder and the event pacer, so [`spoken`] is what a
//! player actually hears. Where that changes an expectation the case says so
//! at the assertion.

#![allow(dead_code)]

use ff_core::data::world_models::{CorridorDetail, GradeSegment, Leg, Route, SpeedLimitSample};
use ff_core::sim::trip::{Trip, TripOptions};
use ff_core::sim::trip_models::NavigationCue;
use ff_core::sim::weather::{WeatherKind, WeatherSystem};
use freight_fate::playtest::harness::{PlaytestHarness, StartDelivery};
use freight_fate::states::base::{InputEvent, Key, Mods};
use freight_fate::states::driving::DrivingState;

pub const MPS_PER_MPH: f64 = 1.0 / 2.23694;
pub const MPH_PER_MPS: f64 = 2.23694;
pub const DT: f64 = 1.0 / 60.0;

/// `pytest.approx` at its default relative tolerance.
pub fn approx(a: f64, b: f64) -> bool {
    (a - b).abs() <= 1e-6 * b.abs().max(1.0)
}

/// `pytest.approx(b, abs=tol)`.
pub fn approx_abs(a: f64, b: f64, tol: f64) -> bool {
    (a - b).abs() <= tol
}

/// One long straight leg with a baked posted limit and a baked grade, and
/// nothing else on it.
pub fn bench_road(drive: &mut DrivingState, limit_mph: f64, grade_pct: f64, time_scale: f64) {
    bench_road_with(drive, &[(0.0, limit_mph)], grade_pct, time_scale);
}

/// [`bench_road`] with more than one posting: `(at_mi, mph)` in order, which
/// is how a road that CHANGES its number mid-leg is described to
/// `speed_limit_at` (Python patched it with a conditional lambda).
pub fn bench_road_with(
    drive: &mut DrivingState,
    limits: &[(f64, f64)],
    grade_pct: f64,
    time_scale: f64,
) {
    bench_road_segments(drive, limits, &[(0.0, BENCH_MILES, grade_pct)], time_scale);
}

/// How long the bench leg is. Long enough that its middle is clear of both
/// city ends, which is what makes `engine_brake_ban_at` answer None there --
/// the Python file monkeypatched that away.
pub const BENCH_MILES: f64 = 400.0;

/// [`bench_road_with`] over a road whose GRADE changes: `(start_mi, end_mi,
/// percent)` segments, which is the record `grade_at` reads.
pub fn bench_road_segments(
    drive: &mut DrivingState,
    limits: &[(f64, f64)],
    grades: &[(f64, f64, f64)],
    time_scale: f64,
) {
    let city = drive.trip.route.cities[0].clone();
    let miles = BENCH_MILES;
    let detail = CorridorDetail {
        speed_limits: limits
            .iter()
            .map(|(at_mi, mph)| SpeedLimitSample {
                at_mi: *at_mi,
                mph: Some(*mph),
                source: "test bench".to_string(),
                hgv: false,
            })
            .collect(),
        grade_segments: grades
            .iter()
            .map(|(start_mi, end_mi, pct)| {
                GradeSegment::new(*start_mi, *end_mi, *pct, "flat", "test bench")
            })
            .collect(),
        ..Default::default()
    };
    let leg = Leg::new(&city, &city, miles, "I 90", "flat", Vec::new()).with_detail(detail);
    let route = Route::from_legs(vec![city.clone(), city], vec![leg]);
    let truck = drive.trip.truck.clone();
    let mut weather = WeatherSystem::new("heartland", Some(3), None, None, true);
    weather.current = WeatherKind::Clear;
    let mut trip = Trip::new(
        route,
        truck,
        weather,
        TripOptions {
            seed: Some(3),
            time_scale,
            ..Default::default()
        },
    );
    quiet(&mut trip);
    // `driving.trip.zones = []` and `driving.trip.curves = []`: a real bend or
    // a posted zone rightly caps cruise, and neither is what the bench is for.
    // A street chain keeps ITS zones -- they are how the street's limit is
    // posted at all -- so this clearing lives here and not in `quiet`.
    trip.zones.clear();
    trip.curves.clear();
    drive.trip = trip;
    drive.reset_turn_state_for_trip();
    // `driving._destination_exit_taken = True`: isolate cruise from exit setup.
    drive.destination_exit_taken = true;
}

/// `quiet_trip(driving)` on a trip that is not yet the drive's.
pub fn quiet(trip: &mut Trip) {
    trip.set_npc_vehicles(Vec::new());
    trip.traffic_manager.rolling_bubble = false;
    trip.traffic_pressures.clear();
    trip.hazard_check_mi = 1e9;
    trip.inspection_check_mi = 1e9;
}

/// `start_drive(app)`: new career, accept the assigned dispatch, depart.
pub fn start_drive(profile_name: &str) -> PlaytestHarness {
    start_drive_scaled(profile_name, None)
}

/// [`start_drive`] with `app.ctx.settings.time_scale` set BEFORE the drive is
/// built, which is where the Python cases that care about it set it: the trip
/// takes its pacing at construction, so a later assignment lasts one tick.
pub fn start_drive_scaled(profile_name: &str, time_scale: Option<f64>) -> PlaytestHarness {
    let mut harness = PlaytestHarness::new();
    if let Some(scale) = time_scale {
        harness.app.ctx.settings.time_scale = scale;
    }
    harness.start_delivery(StartDelivery::named(profile_name));
    harness.with_drive(|d, _| {
        // The origin yard may carry a turn-level street chain; these feature
        // tests exercise highway machinery, so skip the departure chain.
        d.departure_checked = true;
        d.truck_mut().set_air_ready(false);
        d.trip.zones.retain(|zone| zone.aadt.is_none());
        d.weather_mut().current = WeatherKind::Clear;
    });
    harness
}

/// `start_drive` + `quiet_trip` + [`bench_road`]: the rig most cases here use.
pub fn bench_drive(profile_name: &str, limit_mph: f64, grade_pct: f64) -> PlaytestHarness {
    bench_drive_with(profile_name, &[(0.0, limit_mph)], grade_pct)
}

/// [`bench_drive`] over a road whose posted number changes.
pub fn bench_drive_with(
    profile_name: &str,
    limits: &[(f64, f64)],
    grade_pct: f64,
) -> PlaytestHarness {
    let mut harness = start_drive(profile_name);
    let limits = limits.to_vec();
    harness.with_drive(move |d, _| {
        bench_road_with(d, &limits, grade_pct, 1.0);
        d.truck_mut().set_air_ready(false);
    });
    harness.app.ctx.settings.time_scale = 1.0;
    harness
}

/// One frame of the drive (`driving.update(dt)`), with the pacer's clock kept
/// honest -- see `PlaytestHarness::advance_frame_clock`.
pub fn frame(harness: &mut PlaytestHarness, dt: f64) {
    harness.advance_clock(dt);
    harness.with_drive(move |d, ctx| d.update_frame(ctx, dt));
}

pub fn frames(harness: &mut PlaytestHarness, count: usize, dt: f64) {
    for _ in 0..count {
        frame(harness, dt);
    }
}

/// `keys.pressed = {...}`: exactly these keys held, nothing else.
pub fn hold(harness: &mut PlaytestHarness, keys: &[Key]) {
    for key in [
        Key::Up,
        Key::Down,
        Key::Left,
        Key::Right,
        Key::LShift,
        Key::Space,
    ] {
        harness.app.ctx.input.release(key, Mods::NONE);
    }
    for key in keys {
        harness.app.ctx.input.press(*key, Mods::NONE);
    }
}

/// `keys.pressed = set()`.
pub fn release_keys(harness: &mut PlaytestHarness) {
    hold(harness, &[]);
}

/// `key_event(key, unicode)` handed straight to the drive.
pub fn press(harness: &mut PlaytestHarness, key: Key, text: Option<char>) {
    harness.press_key(key, text);
}

/// A Shift-modified press at the wheel (`mod=pygame.KMOD_LSHIFT`).
pub fn press_shift(harness: &mut PlaytestHarness, key: Key) {
    harness.with_drive(move |d, ctx| {
        d.handle_key_event(
            ctx,
            &InputEvent::KeyDown {
                key,
                mods: Mods::SHIFT,
                text: None,
            },
        )
    });
}

/// Every line said so far, both channels, in submission order.
pub fn spoken(harness: &PlaytestHarness) -> Vec<String> {
    harness.app.speech().lines()
}

pub fn last(harness: &PlaytestHarness) -> String {
    spoken(harness).last().cloned().unwrap_or_default()
}

pub fn said_any(harness: &PlaytestHarness, needle: &str) -> bool {
    spoken(harness).iter().any(|line| line.contains(needle))
}

/// `facility_street_chain(driving)`: swap the drive onto a deterministic
/// two-block facility street chain.
///
/// The deadhead shape a tester reported: 25 mph streets with a judged left
/// turn between them, which advises the trailer corner cap of 20. Both blocks
/// are long enough that the facility gate zone stays clear of the corner, so a
/// test can watch the corner on its own.
pub fn facility_street_chain(drive: &mut DrivingState, time_scale: f64) {
    let city = drive.trip.route.cities[0].clone();
    let legs = vec![
        Leg::local(
            &city,
            1.2,
            "East Navarre Street",
            "Start on East Navarre Street.",
            25.0,
        ),
        Leg::local(
            &city,
            1.2,
            "North Michigan Street",
            "Turn left onto North Michigan Street.",
            25.0,
        ),
    ];
    street_chain(
        drive,
        vec![city.clone(), city.clone(), city],
        legs,
        time_scale,
    );
}

/// `short_block_street_chain(driving, block_mi=0.08)`: a street chain whose
/// second corner arrives inside the first one's tail.
///
/// The other half of the tester's deadhead report: turns "coming up really
/// quickly". A 420-foot block is an ordinary city block and shorter than the
/// stretch one corner stays in play for, so the second corner is already in
/// front of the truck while the first is still being taken -- and it turns
/// onto an unnamed service way, which advises the 15 mph gate crawl rather
/// than the 20 a named street's corner gets.
///
/// Returns `(first_cue, second_cue)`.
pub fn short_block_street_chain(
    drive: &mut DrivingState,
    block_mi: f64,
    time_scale: f64,
) -> (NavigationCue, NavigationCue) {
    let city = drive.trip.route.cities[0].clone();
    let legs = vec![
        Leg::local(
            &city,
            1.2,
            "East Navarre Street",
            "Start on East Navarre Street.",
            25.0,
        ),
        Leg::local(
            &city,
            block_mi,
            "North Michigan Street",
            "Turn left onto North Michigan Street.",
            25.0,
        ),
        Leg::local(
            &city,
            1.2,
            "the service road",
            "Turn right onto the service road.",
            15.0,
        ),
    ];
    street_chain(
        drive,
        vec![city.clone(), city.clone(), city.clone(), city],
        legs,
        time_scale,
    );
    let turns = turn_cues(drive);
    assert_eq!(turns.len(), 2, "the short-block chain needs both corners");
    (turns[0].clone(), turns[1].clone())
}

/// The `local:turn:` navigation cues on the drive's trip, in order.
pub fn turn_cues(drive: &DrivingState) -> Vec<NavigationCue> {
    drive
        .trip
        .navigation_cues
        .iter()
        .filter(|cue| cue.key.starts_with("local:turn:"))
        .cloned()
        .collect()
}

fn street_chain(drive: &mut DrivingState, cities: Vec<String>, legs: Vec<Leg>, time_scale: f64) {
    let route = Route::from_legs(cities, legs);
    let truck = drive.trip.truck.clone();
    let mut weather = WeatherSystem::new("heartland", Some(3), None, None, true);
    weather.current = WeatherKind::Clear;
    let mut trip = Trip::new(
        route,
        truck,
        weather,
        TripOptions {
            seed: Some(3),
            time_scale,
            ..Default::default()
        },
    );
    // `trip.traffic_context = lambda: None` plus the hazard/inspection pushes.
    quiet(&mut trip);
    drive.trip = trip;
    drive.reset_turn_state_for_trip();
    drive.destination_exit_taken = true;
}

/// `roll_to(driving, mile)`: run frames until the truck reaches `mile`;
/// returns the `(mile, mph)` trace.
pub fn roll_to(harness: &mut PlaytestHarness, mile: f64, limit_frames: usize) -> Vec<(f64, f64)> {
    let mut trace = Vec::new();
    for _ in 0..limit_frames {
        if harness.read_drive(|d| d.trip.position_mi) >= mile {
            break;
        }
        frame(harness, DT);
        trace.push(harness.read_drive(|d| (d.trip.position_mi, d.truck().speed_mph())));
    }
    trace
}

// -- the grade bench ------------------------------------------------------------

/// Where every bench case parks the truck: the middle of the 400-mile leg,
/// clear of the urban radius at either end.
pub const START_MI: f64 = 200.0;

/// `_cruising(app, set_mph)`: cruise engaged and holding on the bench road.
pub fn cruising(
    name: &str,
    set_mph: f64,
    limit_mph: f64,
    grades: &[(f64, f64, f64)],
) -> PlaytestHarness {
    let mut harness = start_drive(name);
    harness.app.ctx.settings.time_scale = 1.0;
    harness.app.ctx.settings.automatic_transmission = true;
    let grades = grades.to_vec();
    harness.with_drive(move |d, _| {
        bench_road_segments(d, &[(0.0, limit_mph)], &grades, 1.0);
        d.trip.position_mi = START_MI;
        assert!(
            d.trip.engine_brake_ban_at(START_MI).is_none(),
            "the bench road must have no engine-brake ban under the truck"
        );
        d.truck_mut().transmission.automatic = true;
        d.truck_mut().cargo_kg = 18_000.0;
        d.truck_mut().start_engine();
        d.truck_mut().set_air_ready(false);
        d.truck_mut().velocity_mps = set_mph * MPS_PER_MPH;
        d.truck_mut().transmission.gear = d.truck().transmission.num_gears();
    });
    harness.with_drive(move |d, ctx| d.engage_cruise(ctx, set_mph, false));
    harness
}

/// The keyword arguments of `_grade_hold`.
pub struct GradeHold {
    pub set_mph: f64,
    pub seconds: f64,
    pub descent: &'static str,
    pub advisory: Option<f64>,
}

impl Default for GradeHold {
    fn default() -> Self {
        GradeHold {
            set_mph: 62.0,
            seconds: 90.0,
            descent: "realistic",
            advisory: None,
        }
    }
}

/// `_grade_hold(app, grade, ...)`: run cruise at a set speed on a fixed grade;
/// returns the harness, the speed trace and the retarder-stage trace.
///
/// Mirrors the driving loop's own order for the pieces a grade exercises:
/// pedals decay when nothing is held, cruise runs, the retarder manager and
/// the automatic get their turn, then the physics steps.
pub fn grade_hold(
    name: &str,
    grade: f64,
    opts: GradeHold,
) -> (PlaytestHarness, Vec<f64>, Vec<i32>) {
    let mut harness = cruising(
        name,
        opts.set_mph,
        200.0,
        &[(0.0, BENCH_MILES, grade * 100.0)],
    );
    harness.app.ctx.settings.descent_speed_control = opts.descent.to_string();

    let dt = DT;
    let mut speeds = Vec::new();
    let mut stages = Vec::new();
    let settle = 20 * 60;
    let total = (opts.seconds * 60.0) as usize;
    for step in 0..total {
        // Settle on the flat first so the grade arrives at a steady truck.
        let frame_grade = if step < settle { 0.0 } else { grade };
        let advisory = opts.advisory;
        let start_advisory = advisory.is_some() && step == settle;
        harness.advance_clock(dt);
        let (speed, stage) = harness.with_drive(move |d, ctx| {
            d.truck_mut().grade = frame_grade;
            if start_advisory {
                // The bend's footprint outlasts the run, so the cap stays on.
                d.cruise_curve_mph = advisory;
                d.cruise_curve_end_mi = Some(d.trip.position_mi + 5.0);
            }
            let ramp = dt * 2.2;
            let throttle = d.truck().throttle;
            let brake = d.truck().brake;
            d.truck_mut().throttle = 0.0f64.max(throttle - ramp * 2.0);
            d.truck_mut().brake = 0.0f64.max(brake - ramp * 3.0);
            d.update_cruise(ctx, dt, false, false, false);
            d.update_auto_jake(ctx, dt);
            if d.truck().transmission.automatic && d.truck().engine_on {
                d.truck_mut().auto_shift();
            }
            d.truck_mut().update(dt);
            (d.truck().speed_mph(), d.truck().engine_brake_stage)
        });
        if step >= settle {
            speeds.push(speed);
            stages.push(stage);
        }
    }
    (harness, speeds, stages)
}

pub fn max_of(values: &[f64]) -> f64 {
    values.iter().cloned().fold(f64::NEG_INFINITY, f64::max)
}

pub fn min_of(values: &[f64]) -> f64 {
    values.iter().cloned().fold(f64::INFINITY, f64::min)
}
