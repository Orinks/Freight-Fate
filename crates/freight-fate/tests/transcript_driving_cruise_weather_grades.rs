//! Holding the set speed on a grade, predictive cruise, the retarder, the
//! keeper's air budget, the following gap and the weather cap (port of
//! `tests/test_driving_cruise_weather.py`, lines 2983-4023).
//!
//! Last of the split; see `transcript_driving_cruise_weather.rs` for why the
//! Python file is split and `transcript_cruise_support` for what replaced each
//! monkeypatch.
//!
//! Two more substitutions live here:
//!
//! * `trip.engine_brake_ban_at = lambda mile: None` -- the bench leg is 400
//!   miles long and every case starts the truck in its middle, which is clear
//!   of both city ends, so the ban really is absent.
//! * `_grade_hold`'s `trip.grade_at = lambda mile: grade` -- a baked
//!   `GradeSegment` over the whole leg; the loop still writes `t.grade` by
//!   hand each frame exactly as Python did.

mod transcript_cruise_support;

use ff_core::settings::ACC_GAP_CHOICES;
use ff_core::sim::enforcement_observe::TAILGATE_GAP_S;
use ff_core::sim::trip_models::Zone;
use ff_core::sim::trip_route_helpers::zone_key;
use ff_core::sim::weather::WeatherKind;
use freight_fate::playtest::harness::PlaytestHarness;
use freight_fate::states::base::Key;
use freight_fate::states::driving_core::{ACC_LIMIT_OFFSET_MPH, PCC_CREST_SAG_MPH};

use transcript_cruise_support::*;

/// Where every bench case parks the truck: the middle of the 400-mile leg,
/// clear of the urban radius at either end.
const START_MI: f64 = 200.0;

/// `_cruising(app, set_mph)`: cruise engaged and holding on the bench road.
fn cruising(
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
struct GradeHold {
    set_mph: f64,
    seconds: f64,
    descent: &'static str,
    advisory: Option<f64>,
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
fn grade_hold(name: &str, grade: f64, opts: GradeHold) -> (PlaytestHarness, Vec<f64>, Vec<i32>) {
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

fn max_of(values: &[f64]) -> f64 {
    values.iter().cloned().fold(f64::NEG_INFINITY, f64::max)
}

fn min_of(values: &[f64]) -> f64 {
    values.iter().cloned().fold(f64::INFINITY, f64::min)
}

// -- holding the set speed on a grade -------------------------------------------

#[test]
fn test_cruise_does_not_run_away_down_a_grade() {
    // Cutting fuel is not speed control on a downgrade.
    //
    // Cruise had no authority over the truck from above unless a lead or a
    // lower posted limit was already pulling the target down, so gravity
    // simply carried it: a 2 percent descent settled nine mph past the set
    // speed and a 6 percent descent accelerated without limit (bench trace,
    // 2026-07-25: 62 set, 100 mph and still climbing). The retarder now stages
    // against the overspeed, and the drums snub when it is not enough.
    for (grade, ceiling) in [(-0.02, 63.5), (-0.04, 66.0), (-0.06, 66.0)] {
        let (_harness, speeds, _stages) = grade_hold("Runaway", grade, GradeHold::default());
        assert!(max_of(&speeds) <= ceiling, "{grade} {}", max_of(&speeds));
        // And it is holding a speed, not braking the truck to a stop: the jake
        // used to be pinned wide open the moment the grade passed 2.5 percent,
        // which dragged the truck well under its own target.
        let tail = &speeds[speeds.len().saturating_sub(600)..];
        assert!(min_of(tail) >= 58.0, "{grade} {}", min_of(tail));
    }
}

#[test]
fn test_cruise_answers_a_climb_before_it_costs_twenty_mph() {
    // Feed-forward plus the pull downshift, instead of a slow integrator.
    //
    // Cruise used to walk the throttle up at 0.08 per mph-second with no idea
    // what the grade was asking for, and the automatic held top gear because
    // the revs were not lugging yet. A 2 percent climb bled six mph and never
    // got them back; a 4 percent climb lost thirty (bench trace, 2026-07-25).
    let (harness, speeds, _stages) = grade_hold("Climb Two", 0.02, GradeHold::default());
    // A 2 percent pull is well inside what the truck has: hold it.
    assert!(min_of(&speeds) >= 59.0, "{}", min_of(&speeds));
    assert!(
        *speeds.last().expect("a trace") >= 60.0,
        "{:?}",
        speeds.last()
    );
    let (gear, top, throttle) = harness.read_drive(|d| {
        (
            d.truck().transmission.gear,
            d.truck().transmission.num_gears(),
            d.truck().throttle,
        )
    });
    assert!(gear < top || throttle < 1.0);
    drop(harness);

    let (harness, speeds, _stages) = grade_hold("Climb Four", 0.04, GradeHold::default());
    // A 4 percent pull genuinely costs a loaded truck speed -- but it must
    // cost it in a lower gear making real torque, not at full throttle in
    // overdrive watching the hill win.
    assert!(
        *speeds.last().expect("a trace") >= 40.0,
        "{:?}",
        speeds.last()
    );
    let (gear, top) = harness.read_drive(|d| {
        (
            d.truck().transmission.gear,
            d.truck().transmission.num_gears(),
        )
    });
    assert!(gear < top);
}

#[test]
fn test_interactive_descent_control_caps_the_target_without_rewriting_it() {
    // The safe descent ceiling lasts as long as the grade, not the career.
    //
    // It used to assign straight into the cruise set speed, so one downgrade
    // on a 65 road knocked cruise to 55 permanently -- on the flat, uphill,
    // the rest of the run.
    let (mut harness, _speeds, _stages) = grade_hold(
        "Interactive Descent",
        -0.06,
        GradeHold {
            seconds: 25.0,
            descent: "interactive",
            ..Default::default()
        },
    );
    assert!(approx(
        harness.read_drive(|d| d.cruise_mph).expect("cruise"),
        62.0
    ));
    assert!(approx(
        harness
            .read_drive(|d| d.cruise_descent_mph)
            .expect("a ceiling"),
        55.0
    ));

    // Back on the level: the ceiling lifts and the driver's number returns.
    harness.with_drive(|d, _| {
        bench_road_segments(d, &[(0.0, 200.0)], &[(0.0, BENCH_MILES, 0.0)], 1.0);
        d.trip.position_mi = START_MI;
        d.truck_mut().grade = 0.0;
    });
    for _ in 0..120 {
        harness.advance_clock(DT);
        harness.with_drive(|d, ctx| {
            d.update_cruise(ctx, DT, false, false, false);
            d.truck_mut().update(DT);
        });
    }
    assert!(harness.read_drive(|d| d.cruise_descent_mph).is_none());
    assert!(approx(
        harness.read_drive(|d| d.cruise_mph).expect("cruise"),
        62.0
    ));
}

#[test]
fn test_cruise_snubs_the_drums_instead_of_dragging_them_down_a_grade() {
    // A held application empties the air tanks and fades the shoes.
    //
    // Cruise trimmed the service brake proportionally, which on a long grade
    // settled into a permanent light application: the compressor lost ground
    // until the spring brakes set and stopped the truck dead on a downhill
    // (bench trace, 2026-07-25: 125 psi to 74 in twenty-two seconds).
    let (harness, speeds, _stages) = grade_hold(
        "Snub Drums",
        -0.06,
        GradeHold {
            seconds: 80.0,
            ..Default::default()
        },
    );
    // The grade is held, and held without the drums paying for it: full tanks,
    // cool shoes, no spring brakes.
    assert!(max_of(&speeds) <= 66.0, "{}", max_of(&speeds));
    assert!(min_of(&speeds) > 30.0, "{}", min_of(&speeds));
    assert!(!harness.read_drive(|d| d.truck().air_brakes_holding()));
    let psi = harness.read_drive(|d| d.truck().air_pressure_psi());
    assert!(psi >= 100.0, "{psi}");
    let (temp, onset) =
        harness.read_drive(|d| (d.truck().brake_temp_c, d.truck().brake_fade_onset_c()));
    assert!(temp < onset, "{temp} {onset}");
}

#[test]
fn test_cruise_leaves_the_drivers_own_jake_alone() {
    // Cruise releases only the retarder stages it raised itself.
    let mut harness = cruising("Driver Jake", 62.0, 200.0, &[(0.0, BENCH_MILES, 0.0)]);
    harness.with_drive(|d, _| {
        d.truck_mut().grade = 0.0;
        d.truck_mut().engine_brake_stage = 2; // the driver's own selection
    });

    for _ in 0..60 {
        harness.advance_clock(DT);
        harness.with_drive(|d, ctx| d.update_cruise(ctx, DT, false, false, false));
    }

    assert_eq!(harness.read_drive(|d| d.truck().engine_brake_stage), 2);
    assert_eq!(harness.read_drive(|d| d.cruise_jake_stage), 0);
}

// -- predictive cruise ------------------------------------------------------------

/// `_hill_road(driving, flat_mi=, grade=, climb_mi=)`: flat, then a sustained
/// climb, then flat, anchored where the truck is.
fn hill_road(harness: &mut PlaytestHarness, flat_mi: f64, grade: f64, climb_mi: f64) -> f64 {
    let start = harness.read_drive(|d| d.trip.position_mi);
    harness.with_drive(move |d, _| {
        bench_road_segments(
            d,
            &[(0.0, 200.0)],
            // A baked segment's range is CLOSED and the lookup takes the
            // first that contains the mile, so each boundary is nudged a hair
            // to keep the half-open shape Python's `offset < flat + climb`
            // had: the foot of the hill reads the climb, the crest reads the
            // flat beyond it. Without that the preview sees one extra
            // tenth-mile of hill and a 0.2-mile pull never reads as a crest.
            &[
                (0.0, (start + flat_mi - 1e-9).max(0.0), 0.0),
                (
                    start + flat_mi,
                    start + flat_mi + climb_mi - 1e-9,
                    grade * 100.0,
                ),
                (start + flat_mi + climb_mi - 1e-9, BENCH_MILES, 0.0),
            ],
            1.0,
        );
        d.trip.position_mi = start;
    });
    start
}

#[test]
fn test_predictive_cruise_banks_speed_before_a_climb() {
    // The preview reads the grade profile and enters the pull carrying more.
    //
    // Momentum banked on the flat is speed the truck keeps most of the way up,
    // which is the whole point of a predictive system reading a stored road
    // profile.
    let mut harness = cruising("Bank Climb", 62.0, 200.0, &[(0.0, BENCH_MILES, 0.0)]);
    hill_road(&mut harness, 0.5, 0.04, 1.0);
    harness.with_drive(|d, _| d.truck_mut().grade = 0.0);
    harness.app.ctx.settings.predictive_cruise = true;
    assert!(harness.with_drive(|d, ctx| d.predictive_cruise_bias(ctx, 62.0)) > 1.0);

    // Turned off, cruise plans nothing and holds the number it was given.
    harness.app.ctx.settings.predictive_cruise = false;
    assert!(approx(
        harness.with_drive(|d, ctx| d.predictive_cruise_bias(ctx, 62.0)),
        0.0
    ));
}

#[test]
fn test_predictive_cruise_cue_names_the_grade_it_is_building_for() {
    // "The grade ahead" sounded like a steep one, and the G key disagreed.
    //
    // The cue fires from one and a half percent up, under the bar the steep
    // advisory uses, so a driver who pressed G heard that nothing steep was
    // coming for fifteen miles (tester report, Cary, 2026-08-15). Naming the
    // number makes the two answers describe one road.
    let mut harness = cruising("Name The Grade", 62.0, 200.0, &[(0.0, BENCH_MILES, 0.0)]);
    hill_road(&mut harness, 0.5, 0.02, 1.0);
    harness.with_drive(|d, _| d.truck_mut().grade = 0.0);
    harness.app.ctx.settings.predictive_cruise = true;
    harness.clear_speech();
    let bias = harness.with_drive(|d, ctx| d.predictive_cruise_bias(ctx, 62.0));
    assert!(bias > 0.5, "{bias}");
    harness.with_drive(move |d, ctx| d.say_predictive_cruise(ctx, 0.0, bias));
    assert!(
        said_any(&harness, "2.0 percent upgrade"),
        "{:#?}",
        spoken(&harness)
    );
}

#[test]
fn test_predictive_cruise_finds_a_short_hill() {
    // A half-mile hill must not average away inside the preview.
    //
    // Averaging the whole preview, a half-mile four percent pull came out at
    // 1.3 percent -- under the threshold -- so the hills that gain the most
    // from banked momentum were exactly the ones the preview skipped (bench,
    // 2026-07-25). The windowed reading finds them.
    let mut harness = cruising("Short Hill", 62.0, 200.0, &[(0.0, BENCH_MILES, 0.0)]);
    hill_road(&mut harness, 0.3, 0.04, 0.5);
    harness.with_drive(|d, _| d.truck_mut().grade = 0.0);
    harness.app.ctx.settings.predictive_cruise = true;
    let (climb_ahead, _descent) = harness.read_drive(|d| d.grade_extremes_ahead());
    assert!(climb_ahead >= 0.03, "{climb_ahead}");
    assert!(harness.with_drive(|d, ctx| d.predictive_cruise_bias(ctx, 62.0)) > 1.0);
}

#[test]
fn test_predictive_cruise_holds_at_a_crest_but_never_slows_the_truck() {
    // Near the top it stops reaching for speed; it does not give speed away.
    //
    // An earlier cut returned a flat four mph giveaway and cost a 2 percent
    // pull three mph it had been holding comfortably (bench, 2026-07-25).
    let mut harness = cruising("Crest", 62.0, 200.0, &[(0.0, BENCH_MILES, 0.0)]);
    let start = hill_road(&mut harness, 0.0, 0.04, 0.2);
    harness.app.ctx.settings.predictive_cruise = true;
    harness.with_drive(move |d, _| {
        d.trip.position_mi = start;
        d.truck_mut().grade = 0.04;
        d.truck_mut().velocity_mps = 55.0 * MPS_PER_MPH;
    });
    let bias = harness.with_drive(|d, ctx| d.predictive_cruise_bias(ctx, 62.0));
    assert!(bias < 0.0, "{bias}");
    // It brings the target down to the speed on the clock, no further.
    assert!(62.0 + bias >= harness.read_drive(|d| d.truck().speed_mph()) - 0.01);
    assert!(bias >= -PCC_CREST_SAG_MPH, "{bias}");

    // A truck still holding its number at a crest is left alone.
    harness.with_drive(|d, _| d.truck_mut().velocity_mps = 62.0 * MPS_PER_MPH);
    assert!(approx(
        harness.with_drive(|d, ctx| d.predictive_cruise_bias(ctx, 62.0)),
        0.0
    ));
}

#[test]
fn test_predictive_cruise_shaves_before_a_descent() {
    // Speed added just before a downgrade comes back out through the brakes.
    let mut harness = cruising("Shave Descent", 62.0, 200.0, &[(0.0, BENCH_MILES, 0.0)]);
    hill_road(&mut harness, 0.4, -0.05, 1.0);
    harness.with_drive(|d, _| d.truck_mut().grade = 0.0);
    harness.app.ctx.settings.predictive_cruise = true;
    assert!(harness.with_drive(|d, ctx| d.predictive_cruise_bias(ctx, 62.0)) < 0.0);
}

#[test]
fn test_predictive_cruise_never_banks_past_the_posted_limit() {
    // Momentum for a hill is not a licence to speed.
    let mut harness = cruising("Bank Limit", 55.0, 55.0, &[(0.0, BENCH_MILES, 0.0)]);
    harness.app.ctx.settings.predictive_cruise = true;
    let start = harness.read_drive(|d| d.trip.position_mi);
    harness.with_drive(move |d, _| {
        bench_road_segments(
            d,
            &[(0.0, 55.0)],
            &[
                (0.0, start + 0.5, 0.0),
                (start + 0.5, start + 1.5, 6.0),
                (start + 1.5, BENCH_MILES, 0.0),
            ],
            1.0,
        );
        d.trip.position_mi = start;
        d.truck_mut().grade = 0.0;
    });
    for _ in 0..240 {
        harness.advance_clock(DT);
        harness.with_drive(|d, ctx| {
            d.update_cruise(ctx, DT, false, false, false);
            d.truck_mut().update(DT);
        });
    }
    assert!(
        harness.read_drive(|d| d.truck().speed_mph()) <= 55.0 + ACC_LIMIT_OFFSET_MPH + 0.5,
        "{}",
        harness.read_drive(|d| d.truck().speed_mph())
    );
}

#[test]
fn test_cruise_says_when_a_climb_has_beaten_it() {
    // The climb side owes the driver the same honesty the descent side gives.
    //
    // Terse speech keeps it: the engine note and the downshifts already say
    // the truck is working, and a terse player asked for less.
    for (driving_speech, expected) in [("standard", true), ("quiet", false)] {
        let mut harness = cruising("Beaten Climb", 62.0, 200.0, &[(0.0, BENCH_MILES, 7.0)]);
        harness.app.ctx.settings.driving_speech = driving_speech.to_string();
        harness.clear_speech();
        for _ in 0..(90 * 60) {
            harness.advance_clock(DT);
            harness.with_drive(|d, ctx| {
                d.truck_mut().grade = 0.07;
                d.update_cruise(ctx, DT, false, false, false);
                if d.truck().transmission.automatic {
                    d.truck_mut().auto_shift();
                }
                d.truck_mut().update(DT);
            });
        }
        let said = spoken(&harness)
            .iter()
            .filter(|e| e.contains("still losing the grade"))
            .count();
        assert_eq!(said > 0, expected, "{driving_speech}: {said}");
        if expected {
            assert_eq!(said, 1); // once a hill, not once a second
        }
    }
}

#[test]
fn test_climb_cue_stays_quiet_when_cruise_is_winning() {
    // The ported dev guards (f23a97ec): a limit rise that jumps the target
    // well above current speed floors the throttle on near-level road -- that
    // is acceleration toward the number, not defeat, and it must stay silent
    // (71-and-climbing-to-77 was announced as losing the grade; playtest
    // transcript 2026-07-27).
    let mut harness = cruising("Winning Climb", 62.0, 200.0, &[(0.0, BENCH_MILES, 0.5)]);
    harness.app.ctx.settings.driving_speech = "standard".to_string();
    // The target sits well above the truck -- the limit-rise shape -- so
    // cruise floors the pedal while genuinely accelerating.
    harness.with_drive(|d, _| d.truck_mut().velocity_mps = 50.0 * MPS_PER_MPH);
    harness.clear_speech();
    for _ in 0..(30 * 60) {
        harness.advance_clock(DT);
        harness.with_drive(|d, ctx| {
            // Road the G key calls level: below the beaten-grade floor.
            d.truck_mut().grade = 0.005;
            d.update_cruise(ctx, DT, false, false, false);
            if d.truck().transmission.automatic {
                d.truck_mut().auto_shift();
            }
            d.truck_mut().update(DT);
        });
    }
    assert!(
        !said_any(&harness, "still losing the grade"),
        "{:#?}",
        spoken(&harness)
    );
}

#[test]
fn test_cruise_leaves_the_retarder_alone_when_descent_control_is_off() {
    // The stalk decides. The drums still hold the speed either way.
    //
    // Turning descent control off is the driver saying they manage grades
    // themselves, and a real truck's cruise does not flip the engine brake on
    // for you. It must cost the quiet retarder, never the ability to hold the
    // set speed -- that was the runaway this whole area started with.
    let mut harness = cruising("Descent Off", 62.0, 200.0, &[(0.0, BENCH_MILES, -6.0)]);
    harness.app.ctx.settings.descent_speed_control = "off".to_string();
    let mut speeds = Vec::new();
    for _ in 0..(60 * 60) {
        harness.advance_clock(DT);
        let speed = harness.with_drive(|d, ctx| {
            d.truck_mut().grade = -0.06;
            let ramp = DT * 2.2;
            let throttle = d.truck().throttle;
            let brake = d.truck().brake;
            d.truck_mut().throttle = 0.0f64.max(throttle - ramp * 2.0);
            d.truck_mut().brake = 0.0f64.max(brake - ramp * 3.0);
            d.update_cruise(ctx, DT, false, false, false);
            if d.truck().transmission.automatic {
                d.truck_mut().auto_shift();
            }
            d.truck_mut().update(DT);
            d.truck().speed_mph()
        });
        speeds.push(speed);
    }
    assert_eq!(harness.read_drive(|d| d.cruise_jake_stage), 0);
    assert_eq!(harness.read_drive(|d| d.truck().engine_brake_stage), 0);
    assert!(max_of(&speeds) <= 68.0, "{}", max_of(&speeds));
    assert!(!harness.read_drive(|d| d.truck().air_brakes_holding()));
}

// -- the retarder answers grades, not corners -----------------------------------

#[test]
fn test_cruise_slows_for_a_level_bend_on_the_drums_not_the_retarder() {
    // A corner is a target speed, and target speeds belong to the drums.
    //
    // Adaptive cruise capped its working target to the bend's advisory and
    // then reached for the retarder against the resulting overspeed, at three
    // quarters of a mile per hour over, on flat road -- a tester heard the
    // engine brake in corners three times running. The CDL rule is to reach a
    // safe speed BEFORE a bend and pull through, because braking mid-corner is
    // what locks a wheel and jackknifes a trailer, and a retarder drives the
    // tractor's rear wheels alone. Jacobs say the same: sustained speed
    // control, "not a substitute for a service braking system".
    //
    // Bench, level road, 62 set against a 45 advisory: the retarder was up for
    // 350 of 1200 frames at stage three, once per bend over a route of five
    // (2026-08-11). It must be silent, and cruise must still arrive.
    let (_harness, speeds, stages) = grade_hold(
        "Level Bend",
        0.0,
        GradeHold {
            seconds: 60.0,
            advisory: Some(45.0),
            ..Default::default()
        },
    );
    let peak = stages.iter().cloned().max().unwrap_or(0);
    assert_eq!(peak, 0, "{peak}");
    // And it genuinely slows for the bend -- silence must not mean cruise
    // simply carried the set speed through the corner.
    let last = *speeds.last().expect("a trace");
    assert!(last <= 48.0, "{last}");
    assert!(last >= 38.0, "{last}");
}

#[test]
fn test_cruise_still_retards_for_a_bend_on_a_downgrade() {
    // A bend on a grade retards -- that is the grade's doing, not the bend's.
    //
    // Removing the retarder here would put a six percent descent on the drums
    // alone: past fade onset in four and a half minutes (bench, 2026-08-11).
    let (_harness, speeds, stages) = grade_hold(
        "Bend Downgrade",
        -0.06,
        GradeHold {
            seconds: 60.0,
            advisory: Some(45.0),
            ..Default::default()
        },
    );
    let peak = stages.iter().cloned().max().unwrap_or(0);
    assert!(peak >= 1, "{peak}");
    // Holding the advisory, not running away down the hill.
    let tail = &speeds[speeds.len().saturating_sub(600)..];
    assert!(max_of(tail) <= 55.0, "{}", max_of(tail));
}

#[test]
fn test_cruise_holds_a_sustained_grade_on_the_retarder() {
    // The descent case, pinned: a plain downgrade is the retarder's own job.
    let (harness, speeds, stages) = grade_hold(
        "Sustained Grade",
        -0.06,
        GradeHold {
            seconds: 60.0,
            ..Default::default()
        },
    );
    let peak = stages.iter().cloned().max().unwrap_or(0);
    assert!(peak >= 1, "{peak}");
    let (temp, onset) =
        harness.read_drive(|d| (d.truck().brake_temp_c, d.truck().brake_fade_onset_c()));
    assert!(temp < onset, "{temp} {onset}");
    assert!(max_of(&speeds) <= 66.0, "{}", max_of(&speeds));
}

#[test]
fn test_cruise_gives_the_retarder_back_when_the_grade_runs_out_in_a_bend() {
    // The grade ends under the corner: the retarder goes with it.
    //
    // Handing the number to the drums used to leave whatever stage cruise had
    // raised on the hill still barking, all the way through the level bend --
    // 182 of 600 frames at stage three (bench, 2026-08-11). Only the stage
    // cruise raised itself is released; the driver's own switch is untouched.
    let mut harness = cruising("Grade Then Bend", 62.0, 200.0, &[(0.0, BENCH_MILES, -6.0)]);
    harness.app.ctx.settings.descent_speed_control = "realistic".to_string();
    for _ in 0..(12 * 60) {
        harness.advance_clock(DT);
        harness.with_drive(|d, ctx| {
            d.truck_mut().grade = -0.06;
            let ramp = DT * 2.2;
            let throttle = d.truck().throttle;
            let brake = d.truck().brake;
            d.truck_mut().throttle = 0.0f64.max(throttle - ramp * 2.0);
            d.truck_mut().brake = 0.0f64.max(brake - ramp * 3.0);
            d.update_cruise(ctx, DT, false, false, false);
            d.truck_mut().auto_shift();
            d.truck_mut().update(DT);
        });
    }
    assert!(
        harness.read_drive(|d| d.cruise_jake_stage) >= 1,
        "{}",
        harness.read_drive(|d| d.cruise_jake_stage)
    );

    // The bend arrives and the road levels out underneath it.
    harness.with_drive(|d, _| {
        d.cruise_curve_mph = Some(45.0);
        d.cruise_curve_end_mi = Some(d.trip.position_mi + 5.0);
        let at = d.trip.position_mi;
        bench_road_segments(d, &[(0.0, 200.0)], &[(0.0, BENCH_MILES, 0.0)], 1.0);
        d.trip.position_mi = at;
    });
    let mut stages = Vec::new();
    for _ in 0..(10 * 60) {
        harness.advance_clock(DT);
        let stage = harness.with_drive(|d, ctx| {
            d.truck_mut().grade = 0.0;
            let ramp = DT * 2.2;
            let throttle = d.truck().throttle;
            let brake = d.truck().brake;
            d.truck_mut().throttle = 0.0f64.max(throttle - ramp * 2.0);
            d.truck_mut().brake = 0.0f64.max(brake - ramp * 3.0);
            d.update_cruise(ctx, DT, false, false, false);
            d.truck_mut().auto_shift();
            d.truck_mut().update(DT);
            d.truck().engine_brake_stage
        });
        stages.push(stage);
    }
    let peak = stages.iter().cloned().max().unwrap_or(0);
    assert_eq!(peak, 0, "{peak}");
    assert_eq!(harness.read_drive(|d| d.cruise_jake_stage), 0);
}

#[test]
fn test_auto_jake_does_not_chase_a_bend_advisory() {
    // The AMT retarder manager holds the driver's number, not the corner's.
    //
    // The third retarder path: the driver armed the stalk with J, so auto mode
    // owns the stage. It targets the speed it was armed at (or descent
    // control's ceiling on a grade) and never reads a curve advisory, so a
    // bend cannot step it up. Pinned because it is the one path that would
    // otherwise reintroduce the corner bark by another route.
    let mut harness = cruising("Auto Jake", 62.0, 200.0, &[(0.0, BENCH_MILES, 0.0)]);
    harness.app.ctx.settings.descent_speed_control = "realistic".to_string();
    harness.with_drive(|d, ctx| {
        d.cancel_cruise(ctx, false);
        d.truck_mut().grade = 0.0;
        d.truck_mut().throttle = 0.0;
        d.auto_jake = true;
        d.auto_jake_hold_mph = Some(5.0f64.max(d.truck().speed_mph()));
        d.truck_mut().engine_brake_stage = 1; // the controller climbs from here
        d.cruise_curve_mph = Some(45.0);
        d.cruise_curve_end_mi = Some(d.trip.position_mi + 5.0);
    });

    let mut stages = Vec::new();
    for _ in 0..(20 * 60) {
        harness.advance_clock(DT);
        let stage = harness.with_drive(|d, ctx| {
            d.truck_mut().grade = 0.0;
            d.truck_mut().throttle = 0.0;
            d.update_auto_jake(ctx, DT);
            d.truck_mut().auto_shift();
            d.truck_mut().update(DT);
            d.truck().engine_brake_stage
        });
        stages.push(stage);
    }
    let peak = stages.iter().cloned().max().unwrap_or(0);
    assert_eq!(peak, 1, "{peak}");
}

#[test]
fn test_descent_control_cue_does_not_chant_through_rolling_country() {
    // Every dip crosses the trigger; the announcement needs its own clock.
    //
    // Python's rolling country was a sine wave on `grade_at`. A baked profile
    // is a step function, so the same road is baked as alternating half-mile
    // segments of the same amplitude: every dip still crosses the trigger.
    let mut segments = Vec::new();
    let mut mile = 0.0;
    let mut up = true;
    while mile < BENCH_MILES {
        segments.push((mile, mile + 0.5, if up { 5.0 } else { -5.0 }));
        mile += 0.5;
        up = !up;
    }
    let mut harness = cruising("Rolling Country", 62.0, 200.0, &segments);
    harness.clear_speech();
    for _ in 0..(6 * 60 * 60) {
        harness.advance_clock(DT);
        harness.with_drive(|d, ctx| {
            let grade = d.trip.grade_at(d.trip.position_mi);
            d.truck_mut().grade = grade;
            let ramp = DT * 2.2;
            let throttle = d.truck().throttle;
            let brake = d.truck().brake;
            d.truck_mut().throttle = 0.0f64.max(throttle - ramp * 2.0);
            d.truck_mut().brake = 0.0f64.max(brake - ramp * 3.0);
            d.update_cruise(ctx, DT, false, false, false);
            if d.truck().transmission.automatic {
                d.truck_mut().auto_shift();
            }
            d.truck_mut().update(DT);
            d.trip.position_mi += d.truck().speed_mph() / 60.0 / 3600.0;
        });
    }
    let holding = spoken(&harness)
        .iter()
        .filter(|e| e.contains("Descent control holding"))
        .count();
    assert!(holding <= 3, "{holding}");
}

// -- the speed keeper's air budget ----------------------------------------------

/// `_keeper_on_a_grade(app, grade_pct=, limit_mph=)`: speed keeper holding a
/// zone limit down a steady grade.
fn keeper_on_a_grade(name: &str, grade_pct: f64, limit_mph: f64) -> PlaytestHarness {
    let mut harness = start_drive(name);
    harness.app.ctx.settings.time_scale = 1.0;
    release_keys(&mut harness);
    harness.with_drive(move |d, _| {
        bench_road_segments(d, &[(0.0, 200.0)], &[(0.0, BENCH_MILES, grade_pct)], 1.0);
        d.trip.position_mi = START_MI;
        d.trip.zones = vec![Zone::new(0.0, 1e6, limit_mph, "facility access road")];
    });
    press(&mut harness, Key::E, None);
    harness.with_drive(|d, _| {
        d.truck_mut().cargo_kg = 15_000.0;
        d.truck_mut().velocity_mps = 25.0 * MPS_PER_MPH;
    });
    press(&mut harness, Key::K, None);
    assert!(harness.read_drive(|d| d.keeper_mph).is_some());
    harness
}

#[test]
fn test_speed_keeper_holds_a_zone_speed_without_emptying_the_tanks() {
    // The report this exists for: the assist ran the truck out of air.
    //
    // A mild downgrade put the old proportional trim right on its own braking
    // deadband, so it made and released a brake application several times a
    // second. The air system charges a whole application on every rise, so the
    // tanks went 125 psi to 41 in eighteen seconds, the spring brakes set, and
    // the truck stopped dead in a 15 mph zone.
    //
    // Python counted applications by patching `TruckState._consume_brake_air`.
    // Here the same rising edges are read from outside, off
    // `last_service_air_application`, which is the very number that patch
    // compared against.
    let mut harness = keeper_on_a_grade("Keeper Air", -2.0, 15.0);
    let mut applications = 0;
    let mut previous = harness.read_drive(|d| d.truck().last_service_air_application);
    for _ in 0..(60 * 60) {
        frame(&mut harness, DT);
        let application = harness.read_drive(|d| d.truck().last_service_air_application);
        if application - previous > 1e-9 {
            applications += 1;
        }
        previous = application;
    }
    assert!(!harness.read_drive(|d| d.truck().spring_brakes_active()));
    let psi = harness.read_drive(|d| d.truck().air_pressure_psi());
    assert!(
        !harness.read_drive(|d| d.truck().air_low_warning()),
        "{psi}"
    );
    assert!(psi > 100.0, "{psi}");
    // Still driving the zone a minute later, not parked in it.
    assert!(harness.read_drive(|d| d.keeper_mph).is_some());
    assert!(harness.read_drive(|d| d.truck().speed_mph()) > 5.0);
    // A snub is one application held to the number, so a minute of holding
    // costs a handful of them rather than one per frame.
    assert!(applications <= 20, "{applications}");
}

#[test]
fn test_speed_keeper_says_when_it_cannot_hold_the_speed() {
    // Hot brakes on a real grade: the keeper is out of pedal and says so.
    //
    // An assist that quietly holds the wrong speed is the one failure a driver
    // who cannot see the speedometer has no way to catch.
    let mut harness = keeper_on_a_grade("Keeper Beaten", -6.0, 15.0);
    harness.clear_speech();
    for _ in 0..(60 * 30) {
        harness.with_drive(|d, _| {
            let temp = d.truck().brake_temp_c;
            d.truck_mut().brake_temp_c = temp.max(750.0); // faded past any authority
        });
        frame(&mut harness, DT);
    }
    let said = spoken(&harness)
        .iter()
        .filter(|e| {
            *e == "Speed keeper cannot hold 15 miles per hour on this grade. \
                   Apply service brakes."
        })
        .count();
    assert_eq!(said, 1, "{:#?}", spoken(&harness));
}

// -- driver-selectable following gap ----------------------------------------

#[test]
fn test_the_closest_gap_offered_is_still_well_clear_of_a_citation() {
    // The floor under the whole setting.
    //
    // Tester Darren was fined 1,200 dollars for a following gap adaptive
    // cruise was managing and he had no say in (I-75, 2026-08-18). Giving him
    // a say is worth nothing if the closest choice is itself ticketable, so
    // every offered gap has to sit clear of TAILGATE_GAP_S -- and clear by
    // enough that closing on a slower vehicle does not walk straight into it.
    assert!(!ACC_GAP_CHOICES.is_empty());
    for (name, seconds) in ACC_GAP_CHOICES {
        assert!(
            seconds >= TAILGATE_GAP_S + 1.0,
            "{name} leaves only {seconds}s"
        );
    }
}

#[test]
fn test_weather_opens_the_chosen_gap_and_never_shortens_it() {
    // Close means close on a clear day, not on ice.
    //
    // The driver's choice is the floor and weather only ever adds to it, so
    // picking the shortest cushion cannot cancel the wet-road opening, and
    // picking the longest one cannot be quietly pulled back to the middle.
    let mut harness = start_drive("Gap Weather");
    // Effects are derived from the condition, so drive the condition --
    // forcing a grip number would test a state the weather cannot be in.
    for (name, seconds) in ACC_GAP_CHOICES {
        harness.app.ctx.settings.acc_following_gap = name.to_string();
        harness.with_drive(|d, _| d.weather_mut().current = WeatherKind::Clear);
        assert!(
            approx(harness.with_drive(|d, ctx| d.acc_gap_seconds(ctx)), seconds),
            "{name}"
        );

        harness.with_drive(|d, _| d.weather_mut().current = WeatherKind::Snow);
        let wet = harness.with_drive(|d, ctx| d.acc_gap_seconds(ctx));
        assert!(wet > seconds, "{name} did not open up for snow");
    }
}

#[test]
fn test_the_gap_row_speaks_the_seconds_not_just_the_word() {
    // A word alone tells a player working by ear nothing about how much road
    // "close" actually buys. The number is in the label, not buried in the
    // help text.
    //
    // Python read `SettingsCategoryState._acc_gap_label()`. That helper is
    // `pub(super)` here, so the row is read the way a player hears it: off the
    // assistance settings screen itself.
    use freight_fate::states::main_menu::SettingsCategoryState;

    let mut harness = PlaytestHarness::new();
    harness.app.ctx.settings.acc_following_gap = "close".to_string();
    harness
        .app
        .ctx
        .push_state(SettingsCategoryState::new("assistance"));
    harness.app.ctx.run_deferred();
    let row = harness
        .menu_labels()
        .into_iter()
        .find(|row| row.to_lowercase().contains("following gap"))
        .expect("a following-gap row");
    assert!(row.contains("close, 2 and a half seconds"), "{row}");

    harness.app.ctx.settings.acc_following_gap = "normal".to_string();
    harness.app.ctx.pop_state();
    harness
        .app
        .ctx
        .push_state(SettingsCategoryState::new("assistance"));
    harness.app.ctx.run_deferred();
    let row = harness
        .menu_labels()
        .into_iter()
        .find(|row| row.to_lowercase().contains("following gap"))
        .expect("a following-gap row");
    assert!(row.contains("normal, 3 seconds"), "{row}");
}

// -- the retarder in weather, and the weather cap -------------------------------

#[test]
fn test_cruise_leaves_the_jake_alone_on_a_slick_flat_road() {
    // A storm ease is drums-only: the jake retards the drive axle, which on
    // soaked pavement is how a tractor swaps ends, so a driver shuts it off in
    // rain and cruise must hold itself to the same rule. The thunderstorm
    // safe-speed ease from 65 to 40 used to play the jake on flat, soaked I-24
    // (owner playtest, 2026-08-20).
    let mut harness = cruising("Slick Flat", 62.0, 200.0, &[(0.0, BENCH_MILES, 0.0)]);
    harness.app.ctx.settings.descent_speed_control = "realistic".to_string();
    harness.with_drive(|d, _| d.weather_mut().current = WeatherKind::Thunderstorm);
    assert!(
        harness.read_drive(|d| d.weather().effects().grip) < 0.7,
        "the premise: a storm is slick"
    );
    // The storm ease: cruise target far below the truck's speed, level road.
    harness.with_drive(|d, _| d.cruise_mph = Some(40.0));
    let mut stages = Vec::new();
    for _ in 0..(12 * 60) {
        harness.advance_clock(DT);
        let stage = harness.with_drive(|d, ctx| {
            d.truck_mut().grade = 0.0;
            d.truck_mut().throttle = 0.0;
            d.update_cruise(ctx, DT, false, false, false);
            d.truck_mut().auto_shift();
            d.truck_mut().update(DT);
            d.truck().engine_brake_stage
        });
        stages.push(stage);
    }
    let peak = stages.iter().cloned().max().unwrap_or(0);
    assert_eq!(
        peak, 0,
        "cruise raised jake stage {peak} on slick flat road"
    );
    assert!(
        harness.read_drive(|d| d.truck().speed_mph()) < 55.0,
        "the drums still have to do the slowing"
    );
}

#[test]
fn test_cruise_keeps_the_retarder_on_a_slick_downgrade() {
    // The exception is a real grade: dropping a retarder that is holding the
    // hill puts the whole descent onto the drums, the greater evil the release
    // branch's own comment records. Slick flat road gets the drums; a slick
    // grade keeps the retarder.
    let mut harness = cruising("Slick Grade", 62.0, 200.0, &[(0.0, BENCH_MILES, -6.0)]);
    harness.app.ctx.settings.descent_speed_control = "realistic".to_string();
    harness.with_drive(|d, _| d.weather_mut().current = WeatherKind::Thunderstorm);
    for _ in 0..(12 * 60) {
        harness.advance_clock(DT);
        harness.with_drive(|d, ctx| {
            d.truck_mut().grade = -0.06;
            let ramp = DT * 2.2;
            let throttle = d.truck().throttle;
            let brake = d.truck().brake;
            d.truck_mut().throttle = 0.0f64.max(throttle - ramp * 2.0);
            d.truck_mut().brake = 0.0f64.max(brake - ramp * 3.0);
            d.update_cruise(ctx, DT, false, false, false);
            d.truck_mut().auto_shift();
            d.truck_mut().update(DT);
        });
    }
    assert!(
        harness.read_drive(|d| d.cruise_jake_stage) >= 1,
        "a held grade keeps its retarder, storm or not"
    );
}

#[test]
fn test_the_resume_line_names_the_zone_cap_it_will_actually_hold() {
    // Clear of the queue inside a heavy-traffic zone posting 20, the resume
    // line used to say the SET speed while the zone cap silently held the
    // working target at 23 -- minutes of open-looking road with the words
    // contradicting the truck (Brandon, 2026-08-20). The line now names the
    // capped number and why.
    //
    // Python patched `_acc_posted_limit_ahead` to answer (20, "heavy
    // traffic"). Here a real heavy-traffic zone is put on the road ahead, the
    // way `test_cruise_pre_brakes_for_heavy_traffic_like_a_work_zone` does, so
    // the same answer comes out of the real lookahead.
    let mut harness = cruising("Zone Resume", 70.0, 200.0, &[(0.0, BENCH_MILES, 0.0)]);
    let start = harness.read_drive(|d| d.trip.position_mi) + 0.5;
    let zone = Zone::new(start, start + 3.0, 20.0, "heavy traffic");
    harness.with_drive(move |d, _| {
        d.trip.zones.push(zone.clone());
        d.trip.announced_zone_warnings.insert(zone_key(&zone));
    });
    assert_eq!(
        harness.with_drive(|d, ctx| d.acc_posted_limit_ahead(ctx)),
        (20.0, Some("heavy traffic".to_string()))
    );
    harness.clear_speech();
    harness.with_drive(|d, ctx| d.engage_cruise(ctx, 70.0, true));
    let line = spoken(&harness)
        .into_iter()
        .find(|s| s.contains("Open road"))
        .unwrap_or_else(|| panic!("no resume line\n{:#?}", spoken(&harness)));
    assert!(
        line.contains("resuming at 20 miles per hour through the heavy traffic"),
        "{line}"
    );
    assert!(!line.contains("70"), "{line}");
}

#[test]
fn test_cruise_never_raises_the_jake_on_a_climb() {
    // Overspeed carried into an upgrade is the hill's to eat: a real driver
    // powers up a grade, never barks the retarder at it (Brandon,
    // 2026-08-20). The raise path now honors `on_downgrade`'s own doctrine.
    let mut harness = cruising("Jake Climb", 55.0, 200.0, &[(0.0, BENCH_MILES, 3.0)]);
    harness.app.ctx.settings.descent_speed_control = "realistic".to_string();
    harness.with_drive(|d, _| {
        d.truck_mut().velocity_mps = 70.0 * MPS_PER_MPH; // fifteen over, uphill
    });
    let mut stages = Vec::new();
    for _ in 0..(10 * 60) {
        harness.advance_clock(DT);
        let stage = harness.with_drive(|d, ctx| {
            d.truck_mut().grade = 0.03;
            d.truck_mut().throttle = 0.0;
            d.update_cruise(ctx, DT, false, false, false);
            d.truck_mut().auto_shift();
            d.truck_mut().update(DT);
            d.truck().engine_brake_stage
        });
        stages.push(stage);
    }
    let peak = stages.iter().cloned().max().unwrap_or(0);
    assert_eq!(peak, 0, "cruise raised jake stage {peak} on an upgrade");
}

#[test]
fn test_cruise_eases_to_the_weather_safe_speed_and_says_so_once() {
    // A real adaptive system treats the weather like any other road fact: the
    // safe speed was computed and spoken as guidance since live weather
    // shipped, and enforced by nothing -- cruise held a set seventy through a
    // thunderstorm until the driver tapped it down (Brandon's suggestion,
    // 2026-08-20; owner-approved same day).
    let mut harness = cruising("Storm Ease", 70.0, 200.0, &[(0.0, BENCH_MILES, 0.0)]);
    harness.clear_speech();
    harness.with_drive(|d, _| d.weather_mut().current = WeatherKind::Thunderstorm);
    for _ in 0..(20 * 60) {
        harness.advance_clock(DT);
        harness.with_drive(|d, ctx| {
            d.truck_mut().grade = 0.0;
            d.update_cruise(ctx, DT, false, false, false);
            d.truck_mut().auto_shift();
            d.truck_mut().update(DT);
        });
    }
    let speed = harness.read_drive(|d| d.truck().speed_mph());
    assert!(speed <= 40.0 + 2.0, "held {speed:.1} in a thunderstorm");
    let eased: Vec<String> = spoken(&harness)
        .into_iter()
        .filter(|e| e.contains("adaptive cruise easing to 40"))
        .collect();
    assert_eq!(
        eased,
        vec!["Thunderstorm; adaptive cruise easing to 40 miles per hour.".to_string()],
        "{:#?}",
        spoken(&harness)
    );
}

#[test]
fn test_the_weather_cap_lifts_with_the_weather() {
    let mut harness = cruising("Cap Lifts", 70.0, 200.0, &[(0.0, BENCH_MILES, 0.0)]);
    harness.clear_speech();
    harness.with_drive(|d, _| d.weather_mut().current = WeatherKind::Thunderstorm);
    for _ in 0..(20 * 60) {
        harness.advance_clock(DT);
        harness.with_drive(|d, ctx| {
            d.truck_mut().grade = 0.0;
            d.update_cruise(ctx, DT, false, false, false);
            d.truck_mut().auto_shift();
            d.truck_mut().update(DT);
        });
    }
    assert!(harness.read_drive(|d| d.truck().speed_mph()) <= 42.0);

    harness.with_drive(|d, _| d.weather_mut().current = WeatherKind::Clear);
    for _ in 0..(40 * 60) {
        harness.advance_clock(DT);
        harness.with_drive(|d, ctx| {
            d.truck_mut().grade = 0.0;
            let ramp = DT * 2.2;
            let brake = d.truck().brake;
            d.truck_mut().brake = 0.0f64.max(brake - ramp * 3.0);
            d.update_cruise(ctx, DT, false, false, false);
            d.truck_mut().auto_shift();
            d.truck_mut().update(DT);
        });
    }
    let speed = harness.read_drive(|d| d.truck().speed_mph());
    assert!(
        speed > 55.0,
        "never climbed back after the storm: {speed:.1}"
    );

    // The next front is news again.
    harness.with_drive(|d, _| d.weather_mut().current = WeatherKind::HeavyRain);
    for _ in 0..(5 * 60) {
        harness.advance_clock(DT);
        harness.with_drive(|d, ctx| {
            d.truck_mut().grade = 0.0;
            let brake = d.truck().brake;
            d.truck_mut().brake = 0.0f64.max(brake - DT * 2.2 * 3.0);
            d.update_cruise(ctx, DT, false, false, false);
            d.truck_mut().auto_shift();
            d.truck_mut().update(DT);
        });
    }
    assert!(
        said_any(&harness, "Heavy rain; adaptive cruise easing to 45"),
        "{:#?}",
        spoken(&harness)
    );
}

#[test]
fn test_the_resume_line_names_the_weather_cap() {
    // Python patched `_acc_posted_limit_ahead` to (75, None); here the bench
    // road really posts 75, which is the same answer through the real
    // lookahead.
    let mut harness = cruising("Weather Resume", 70.0, 75.0, &[(0.0, BENCH_MILES, 0.0)]);
    assert_eq!(
        harness.with_drive(|d, ctx| d.acc_posted_limit_ahead(ctx)),
        (75.0, None)
    );
    harness.with_drive(|d, _| d.weather_mut().current = WeatherKind::Snow);
    harness.clear_speech();
    harness.with_drive(|d, ctx| d.engage_cruise(ctx, 70.0, true));
    let line = spoken(&harness)
        .into_iter()
        .find(|s| s.contains("Open road"))
        .unwrap_or_else(|| panic!("no resume line\n{:#?}", spoken(&harness)));
    assert!(
        line.contains("resuming at 35 miles per hour in the snow"),
        "{line}"
    );
}
