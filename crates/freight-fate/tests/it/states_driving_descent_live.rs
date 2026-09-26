//! Descent control on the real road it failed on: I-70 east from the
//! Eisenhower tunnel into Denver, a 76,000 lb truck, the Balanced preset,
//! cruise set at 85.
//!
//! Two live drives of that road on 2026-09-24. The owner's, cruise at 85 the
//! way he drives (the set speed high, the limit cap doing the work):
//!
//! ```text
//!   Grade 5.8 percent downhill for another 14 miles. ... Next, a 7.0
//!   percent downgrade in 4 miles, running 2 miles.
//!   [event] Descent control holding 85 miles per hour.
//!   [jake] stage 3 ... stage 0 ... stage 2 ... stage 1 ... stage 2 ... stage 1
//! ```
//!
//! and the agent's, with the J key's retarder manager armed and cruise at 45:
//! "Descent control holding 45", the truck at 55 a minute later on the seven
//! percent, the automatic upshifting on the downgrade, and the G key calling
//! the same pitch "running 2 miles" and then "for another 10 miles".
//!
//! On the bench the same run held 68 to 72 down the 5.8 and the 7.0 on a
//! tenth of the drums with the retarder never raised, the shoes past 300 C,
//! the box cycling nine and ten at the retarder's rev ceiling. These cases
//! pin what a driver would have done instead: a speed chosen for the hill
//! (`TruckState::safe_descent_mph`), full engine brake set at the top, the
//! gear held, the drums in snubs -- and each number said once.

use ff_core::sim::vehicle::{GSRS_BRAKE_LIMIT_C, JAKE_STAGES};
use ff_core::sim::weather::WeatherKind;

use freight_fate::playtest::harness::{PlaytestHarness, RouteSetup};
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::{CRUISE_BRAKE_OVER_MPH, CRUISE_JAKE_REVERSE_S};

use crate::transcript_cruise_support::{frame, quiet, release_keys, DT, MPS_PER_MPH};

/// 76,000 lb gross, the owner's load.
const GROSS_KG: f64 = 76_000.0 * 0.453_592;
/// A few miles above the Eisenhower-side descents on this leg.
const START_MI: f64 = 128.0;
/// Past the seven percent pitch and the grades below it.
const END_MI: f64 = 147.6;
const HOLDING: &str = "Descent control holding ";

fn owners_run(auto_jake: bool) -> PlaytestHarness {
    let mut harness = PlaytestHarness::new();
    harness.app.ctx.settings.time_scale = 10.0;
    harness
        .app
        .ctx
        .settings
        .apply_driving_assistance_preset("balanced");
    harness.start_route(
        "Glenwood Springs",
        "Denver",
        RouteSetup::seeded(4242).named("Descent Live").cities(&[
            "Glenwood Springs",
            "Edwards",
            "Silverthorne",
            "Denver",
        ]),
    );
    harness.with_drive(move |d, ctx| {
        d.departure_checked = true;
        d.destination_exit_taken = true;
        quiet(&mut d.trip);
        d.weather_mut().forced = Some(WeatherKind::Clear);
        d.weather_mut().current = WeatherKind::Clear;
        let tare = d.truck().tare_kg();
        d.truck_mut().cargo_kg = GROSS_KG - tare;
        d.trip.position_mi = START_MI;
        d.truck_mut().start_engine();
        d.truck_mut().set_air_ready(false);
        d.truck_mut().transmission.automatic = true;
        d.truck_mut().transmission.gear = d.truck().transmission.num_gears();
        d.truck_mut().velocity_mps = 60.0 * MPS_PER_MPH;
        d.engage_cruise(ctx, 85.0, false);
        d.auto_jake = auto_jake;
    });
    release_keys(&mut harness);
    harness
}

#[derive(Clone, Copy)]
struct Frame {
    t: f64,
    mile: f64,
    grade_pct: f64,
    speed_mph: f64,
    safe_mph: Option<f64>,
    stage: i32,
    gear: i32,
    air_psi: f64,
    drum_c: f64,
    downgrade: bool,
    jake_sounding: bool,
    brake: f64,
}

fn read(d: &DrivingState, t: f64) -> Frame {
    let truck = &d.trip.truck;
    Frame {
        t,
        mile: d.trip.position_mi,
        grade_pct: d.trip.grade_at(d.trip.position_mi) * 100.0,
        speed_mph: truck.speed_mph(),
        safe_mph: d.descent_safe_mph,
        stage: truck.engine_brake_stage,
        gear: truck.transmission.gear,
        air_psi: truck.air_pressure_psi(),
        drum_c: truck.brake_temp_c,
        downgrade: d.on_downgrade(),
        jake_sounding: d.jake_cue_key.is_some(),
        brake: truck.brake,
    }
}

fn line(f: &Frame) -> String {
    format!(
        "t {:.0}s mile {:.2} grade {:+.1}% {:.1} mph (safe {:?}) jake {} gear {} brake {:.2} \
         air {:.0} drums {:.0}",
        f.t,
        f.mile,
        f.grade_pct,
        f.speed_mph,
        f.safe_mph,
        f.stage,
        f.gear,
        f.brake,
        f.air_psi,
        f.drum_c
    )
}

/// Drive the run, returning every frame and every line spoken.
fn drive(harness: &mut PlaytestHarness) -> (Vec<Frame>, Vec<String>) {
    let mut frames = Vec::new();
    let mut t = 0.0;
    while t < 1500.0 {
        frame(harness, DT);
        t += DT;
        let f = harness.read_drive(|d| read(d, t));
        frames.push(f);
        if f.mile >= END_MI {
            break;
        }
    }
    (frames, harness.app.speech().lines())
}

fn held_numbers(lines: &[String]) -> Vec<f64> {
    lines
        .iter()
        .filter_map(|l| l.split(HOLDING).nth(1))
        .filter_map(|rest| rest.split(' ').next()?.parse::<f64>().ok())
        .collect()
}

fn check_run(auto_jake: bool) {
    let mut harness = owners_run(auto_jake);
    let (frames, lines) = drive(&mut harness);
    let who = if auto_jake {
        "retarder manager"
    } else {
        "cruise"
    };
    assert!(
        frames.last().is_some_and(|f| f.mile >= END_MI),
        "{who}: the run has to reach the bottom of the seven percent"
    );

    // The number: a hill's number, never the set speed or limit plus five.
    // Every number said is one the safe-descent rule gave for this run.
    let held = held_numbers(&lines);
    let hill_numbers: Vec<f64> = frames.iter().filter_map(|f| f.safe_mph).collect();
    assert!(
        held.iter().all(|mph| hill_numbers.contains(mph)),
        "{who}: descent control named a number that is not the hill's: {held:?}"
    );
    assert!(
        held.iter().any(|mph| *mph <= 50.0),
        "{who}: the seven percent never got a mountain speed: {held:?}"
    );
    // Once per number: never the same number twice in a row, and a mountain
    // is a handful of numbers, not a line per pitch.
    assert!(
        held.windows(2).all(|pair| pair[0] != pair[1]),
        "{who}: the same number said twice: {held:?}"
    );
    assert!(held.len() <= 5, "{who}: {held:?}");
    assert!(
        !lines.iter().any(|l| l.contains("cannot hold this grade")),
        "{who}: the hill beat the control"
    );

    let steep: Vec<&Frame> = frames.iter().filter(|f| f.grade_pct <= -6.5).collect();
    assert!(steep.len() > 100, "{who}: never reached the seven percent");
    let settled_from = steep[0].t + 10.0;
    for f in steep.iter().filter(|f| f.t >= settled_from) {
        let safe = f
            .safe_mph
            .expect("the seven percent has a safe descent speed");
        assert!(
            f.speed_mph <= safe + CRUISE_BRAKE_OVER_MPH + 1.5,
            "{who}: the truck ran past the speed it announced: {}",
            line(f)
        );
    }

    for f in &frames {
        assert!(f.air_psi >= 90.0, "{who}: the air ran down: {}", line(f));
        assert!(
            f.drum_c <= GSRS_BRAKE_LIMIT_C,
            "{who}: the drums went past the grade-severity limit: {}",
            line(f)
        );
    }

    // Engine brake first: wherever the drums are on to bring the truck down
    // to a hill's number on a downgrade, the retarder is already at full.
    // Between the 5.8 and the 7.0 the drums used to take it from 63 to 45
    // with the retarder down on a 2.4 percent stretch above the pitch. (On
    // level road, slowing to a number is the drums' job by design.)
    // (A frame onto the grade is the controller's first look at it.)
    for pair in frames.windows(2) {
        let f = &pair[1];
        let over_the_hill = f.safe_mph.is_some_and(|safe| f.speed_mph > safe + 1.0);
        if f.brake > 0.01 && over_the_hill && pair[0].downgrade && f.downgrade {
            assert_eq!(
                f.stage,
                JAKE_STAGES,
                "{who}: the drums braked for the hill before the engine brake: {}",
                line(f)
            );
        }
    }

    // The gear is held on the steep pitches: no automatic upshift.
    for pair in frames.windows(2) {
        let (a, b) = (&pair[0], &pair[1]);
        if a.grade_pct <= -4.0 && b.grade_pct <= -4.0 && b.gear > 0 && a.gear > 0 {
            assert!(
                b.gear <= a.gear,
                "{who}: upshifted on the downgrade: {} -> {}",
                line(a),
                line(b)
            );
        }
    }

    // The retarder does not hunt: no up-down-up or down-up-down inside the
    // reversal time, anywhere on a downgrade.
    let changes: Vec<(f64, i32)> = frames
        .windows(2)
        .filter(|p| p[1].downgrade && p[1].stage != p[0].stage)
        .map(|p| (p[1].t, (p[1].stage - p[0].stage).signum()))
        .collect();
    for w in changes.windows(3) {
        let hunting = w[0].1 != w[1].1 && w[1].1 != w[2].1;
        assert!(
            !(hunting && w[2].0 - w[0].0 < CRUISE_JAKE_REVERSE_S),
            "{who}: the retarder hunted: {w:?}"
        );
    }

    // And the growl is started once per stretch of downgrade, never
    // restarted by a stage change inside it.
    let mut starts_this_stretch = 0;
    for pair in frames.windows(2) {
        let (a, b) = (&pair[0], &pair[1]);
        if !b.downgrade {
            starts_this_stretch = 0;
            continue;
        }
        if b.jake_sounding && !a.jake_sounding {
            starts_this_stretch += 1;
            assert!(
                starts_this_stretch <= 1,
                "{who}: the engine-brake sound restarted mid-descent: {}",
                line(b)
            );
        }
    }
}

/// The owner's drive: cruise at 85, the posted cap doing the work.
#[test]
fn descent_control_holds_a_safe_speed_down_the_owners_run() {
    check_run(false);
}

/// The agent's drive: the J key's retarder manager armed as well.
#[test]
fn descent_control_holds_a_safe_speed_with_the_retarder_manager_armed() {
    check_run(true);
}

/// One pitch, one length: the G key on the seven percent names the same
/// run the look-ahead named from above it.
#[test]
fn the_seven_percent_has_one_length_from_above_and_on_it() {
    let mut harness = owners_run(false);
    let top = harness.read_drive(|d| {
        let mut mile = 140.0;
        while d.trip.grade_at(mile) * 100.0 > -6.5 {
            mile += 0.05;
            assert!(mile < 150.0, "no seven percent pitch on this leg");
        }
        mile
    });
    let g_at = |harness: &mut PlaytestHarness, mile: f64| {
        harness.with_drive(move |d, _| {
            d.trip.position_mi = mile;
            let grade = d.trip.grade_at(mile);
            d.truck_mut().grade = grade;
            d.truck_mut().velocity_mps = 45.0 * MPS_PER_MPH;
        });
        let before = harness.app.speech().lines().len();
        harness.with_drive(|d, ctx| d.speak_grade(ctx));
        harness.app.speech().lines()[before].clone()
    };
    let miles_after = |text: &str, key: &str| -> f64 {
        let rest = text
            .split(key)
            .nth(1)
            .unwrap_or_else(|| panic!("no '{key}' in: {text}"));
        let word = rest.split(' ').next().unwrap_or_default();
        word.parse::<f64>().unwrap_or_else(|_| {
            if word == "a" || word == "one" {
                1.0
            } else {
                panic!("{text}")
            }
        })
    };
    let above = g_at(&mut harness, top - 0.3);
    let running = miles_after(&above, "running ");
    let on_it = g_at(&mut harness, top + 0.1);
    assert!(on_it.contains("7.0 percent downhill"), "{on_it}");
    let remaining = if on_it.contains("for another ") {
        miles_after(&on_it, "for another ")
    } else {
        0.0 // under a mile left: the readout names no length
    };
    assert!(
        remaining <= running,
        "the pitch grew under the truck: from above \"{above}\", on it \"{on_it}\""
    );
    assert!(
        running - remaining <= 1.0,
        "the two readouts disagree about one pitch: \"{above}\" / \"{on_it}\""
    );

    // And D, the one safe-speed number, is the hill's number here -- the
    // one descent control holds -- not the posted limit.
    let before = harness.app.speech().lines().len();
    harness.with_drive(|d, ctx| d.speak_safe_speed(ctx));
    let d_key = harness.app.speech().lines()[before].clone();
    let expected = harness
        .read_drive(|d| d.safe_descent_here_mph())
        .expect("a safe descent speed on the seven percent");
    assert!(expected <= 50.0, "{expected}");
    assert_eq!(
        d_key,
        format!("Safe speed {expected:.0} miles per hour for the grade.")
    );
}
