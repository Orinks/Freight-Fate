//! Holding the set speed on a grade, and predictive cruise (port of
//! `tests/test_driving_cruise_weather.py`, lines 2983-3458).
//!
//! Fifth of the split; see `transcript_driving_cruise_weather.rs` for why the
//! Python file is split and `transcript_cruise_support` for what replaced each
//! monkeypatch, including the two this half adds:
//!
//! * `trip.engine_brake_ban_at = lambda mile: None` -- the bench leg is 400
//!   miles long and every case starts the truck in its middle, which is clear
//!   of both city ends, so the ban really is absent.
//! * `_grade_hold`'s `trip.grade_at = lambda mile: grade` -- a baked
//!   `GradeSegment` over the whole leg; the loop still writes `t.grade` by
//!   hand each frame exactly as Python did.

use freight_fate::playtest::harness::PlaytestHarness;
use freight_fate::states::driving_core::{
    ACC_LIMIT_OFFSET_MPH, DESCENT_SAFE_MAX_MPH, MPH_PER_MPS, PCC_CREST_SAG_MPH,
};

use crate::transcript_cruise_support::*;

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

// -- the driver's own brake on a grade -----------------------------------------

#[test]
fn test_braking_on_a_grade_caps_it_without_rewriting_the_set_speed() {
    // The same correction the interactive path already carries.
    //
    // Brandon drove a whole run pinned at "forty nine mph or lower and losing
    // speed instead of getting back up to highway speed" (2026-08-23).
    // Braking on a downgrade assigned straight into the cruise set speed, so
    // it was permanent AND cumulative: 65 becomes 55 on one hill, 49 on the
    // next, and cruise never climbs back on the flat because 49 IS the set
    // speed by then. A ratchet that only ever turns down.
    //
    // `test_interactive_descent_control_caps_the_target_without_rewriting_it`
    // above pins the identical rule one branch over. This one was missed out
    // of it.
    let mut harness = bench_drive("Grade Brake Ratchet", 200.0, 0.0);
    harness.app.ctx.settings.descent_speed_control = "balanced".to_string();
    harness.with_drive(|d, _| {
        quiet(&mut d.trip);
        d.truck_mut().start_engine();
        d.truck_mut().velocity_mps = 65.0 / MPH_PER_MPS;
        d.cruise_mph = Some(65.0);
        d.cruise_working_mph = Some(65.0);
    });

    // Two hills, braking lower on the second one.
    for slowed_to in [55.0_f64, 49.0] {
        harness.with_drive(move |d, ctx| {
            d.truck_mut().grade = -0.05;
            d.truck_mut().velocity_mps = slowed_to / MPH_PER_MPS;
            d.update_cruise(ctx, DT, true, false, false);
        });
        // The driver's number is untouched, and the grade carries the cap.
        assert!(approx(
            harness.read_drive(|d| d.cruise_mph).expect("cruise"),
            65.0
        ));
        assert!(approx_abs(
            harness
                .read_drive(|d| d.cruise_descent_mph)
                .expect("a grade cap"),
            slowed_to,
            0.01
        ));
    }

    // Back on the level: the cap lifts and highway speed comes back.
    harness.with_drive(|d, _| {
        bench_road_segments(d, &[(0.0, 200.0)], &[(0.0, BENCH_MILES, 0.0)], 1.0);
        d.truck_mut().grade = 0.0;
    });
    for _ in 0..600 {
        harness.with_drive(|d, ctx| {
            d.truck_mut().grade = 0.0;
            d.update_cruise(ctx, DT, false, false, false);
        });
    }
    assert!(harness.read_drive(|d| d.cruise_descent_mph).is_none());
    assert!(approx(
        harness.read_drive(|d| d.cruise_mph).expect("cruise"),
        65.0
    ));
    assert!(approx(
        harness
            .read_drive(|d| d.cruise_working_mph)
            .expect("a working target"),
        65.0
    ));
}

#[test]
fn test_the_automatic_grade_cap_never_undoes_the_drivers_own_brake() {
    // Capture is an instruction; the automatic ceiling must not raise it.
    //
    // Both write `cruise_descent_mph`, and on the frame after a deliberate
    // brake the interactive ceiling would otherwise hand the speed straight
    // back.
    let mut harness = bench_drive("Grade Brake Instruction", 200.0, 0.0);
    harness.app.ctx.settings.descent_speed_control = "interactive".to_string();
    harness.with_drive(|d, _| {
        quiet(&mut d.trip);
        d.truck_mut().start_engine();
        d.cruise_mph = Some(65.0);
        d.cruise_working_mph = Some(65.0);
    });

    let slowed_to = DESCENT_SAFE_MAX_MPH - 10.0;
    harness.with_drive(move |d, ctx| {
        d.truck_mut().grade = -0.05;
        d.truck_mut().velocity_mps = slowed_to / MPH_PER_MPS;
        d.update_cruise(ctx, DT, true, false, false);
    });
    assert!(approx_abs(
        harness
            .read_drive(|d| d.cruise_descent_mph)
            .expect("a grade cap"),
        slowed_to,
        0.01
    ));

    // Still on the grade, no brake: the automatic ceiling runs and must
    // leave the lower, deliberate cap alone.
    for _ in 0..60 {
        harness.with_drive(|d, ctx| {
            d.truck_mut().grade = -0.05;
            d.update_cruise(ctx, DT, false, false, false);
        });
    }
    assert!(harness.read_drive(|d| d.cruise_descent_mph).expect("a cap") <= slowed_to + 0.01);
    assert!(approx(
        harness.read_drive(|d| d.cruise_mph).expect("cruise"),
        65.0
    ));
}

#[test]
fn test_the_status_readout_names_the_grade_cap_and_leaves_the_set_speed_alone() {
    // The two halves of the grade fix have to compose.
    //
    // The cap is only honest if the driver can hear it as a cap: Space and Tab
    // read what the loop published after every ceiling, so a grade brake must
    // come back as the HELD number with the driver's own set speed still
    // beside it. Before the fix the brake rewrote `cruise_mph`, so the two
    // numbers were the same one and the readout fell through to "adaptive
    // cruise set at 55" -- the truck changing its own target and saying
    // nothing about it.
    let mut harness = bench_drive("Grade Cap Readout", 200.0, 0.0);
    harness.app.ctx.settings.descent_speed_control = "balanced".to_string();
    harness.with_drive(|d, _| {
        quiet(&mut d.trip);
        d.truck_mut().start_engine();
        d.cruise_mph = Some(65.0);
        d.cruise_working_mph = Some(65.0);
    });

    // The driver brakes on the grade, then comes off the pedal still on it.
    harness.with_drive(|d, ctx| {
        d.truck_mut().grade = -0.05;
        d.truck_mut().velocity_mps = 55.0 / MPH_PER_MPS;
        d.update_cruise(ctx, DT, true, false, false);
    });
    harness.with_drive(|d, ctx| {
        d.truck_mut().grade = -0.05;
        d.update_cruise(ctx, DT, false, false, false);
    });

    let readout = harness.with_drive(|d, ctx| d.cruise_holding_text(ctx));
    assert_eq!(
        readout, "adaptive cruise holding 55 miles per hour for the grade, set 65 miles per hour",
        "{readout}"
    );
    // And the driver's own number is still the set speed, not the cap.
    assert!(approx(
        harness.read_drive(|d| d.cruise_mph).expect("cruise"),
        65.0
    ));
}
