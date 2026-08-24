//! The `TruckState` half of `tests/test_driving_damage_bands.py`: the bands
//! themselves, the derate, the governor, the runaway, and the reverse guard.
//!
//! These live here rather than in the game crate's
//! `tests/it/states_driving_damage.rs` for two reasons. They ask nothing of
//! the app -- Python builds a bare `TruckState()` for every one of them -- and
//! four of them step `update_wear` / `update_fuel` directly, which are
//! `pub(crate)` and reachable only from inside `ff-core`. Driving them
//! through the public `update()` instead would move the truck as well, which
//! is exactly what the Python cases isolate away from.
//!
//! Their own file rather than more of `vehicle/tests.rs`, which is already
//! 1786 lines against the repo's 1000-line guidance.
#![allow(clippy::field_reassign_with_default)]

use super::*;
use crate::sim::transmission::REVERSE;

const MPS_PER_MPH: f64 = 1.0 / 2.23694;
const DT: f64 = 1.0 / 60.0;

fn approx(a: f64, b: f64) -> bool {
    (a - b).abs() <= 1e-6 * b.abs().max(1.0)
}

// -- the band ladder ---------------------------------------------------------------

#[test]
fn test_damage_below_the_first_band_changes_nothing() {
    // A careful driver must see exactly the behaviour they saw before.
    let clean = TruckState::default();
    let mut worn = TruckState::default();
    worn.damage_pct = DAMAGE_DERATE_PCT - 1.0;

    assert_eq!(worn.damage_band(), DAMAGE_BAND_NONE);
    assert_eq!(worn.damage_derate_factor(), 1.0);
    assert_eq!(worn.damage_fuel_penalty(), 0.0);
    assert_eq!(worn.speed_cap_mph, None);
    assert!(!worn.out_of_service());
    assert_eq!(clean.damage_derate_factor(), 1.0);
}

#[test]
fn test_reduced_power_band_derates_torque_and_costs_fuel() {
    let mut t = TruckState::default();
    t.damage_pct = DAMAGE_DERATE_PCT;
    assert_eq!(t.damage_band(), DAMAGE_BAND_REDUCED);
    assert!(approx(t.damage_derate_factor(), 1.0));

    t.damage_pct = (DAMAGE_DERATE_PCT + DAMAGE_LIMP_PCT) / 2.0;
    let mid = t.damage_derate_factor();
    assert!(mid > 0.0 && mid < 1.0, "{mid}");
    assert!(t.damage_fuel_penalty() > 0.0);

    // Progressive, not a cliff: deeper damage always derates further.
    t.damage_pct = DAMAGE_LIMP_PCT;
    assert!(t.damage_derate_factor() < mid);
    assert_eq!(t.damage_band(), DAMAGE_BAND_LIMP);
}

#[test]
fn test_damage_bands_ladder_up_to_the_wall() {
    let mut t = TruckState::default();
    for (damage, band) in [
        (0.0, DAMAGE_BAND_NONE),
        (DAMAGE_DERATE_PCT, DAMAGE_BAND_REDUCED),
        (DAMAGE_LIMP_PCT, DAMAGE_BAND_LIMP),
        (DAMAGE_LAST_CALL_PCT, DAMAGE_BAND_LAST_CALL),
        (DAMAGE_OUT_OF_SERVICE_PCT, DAMAGE_BAND_OUT_OF_SERVICE),
        (DAMAGE_MAX_PCT, DAMAGE_BAND_OUT_OF_SERVICE),
    ] {
        t.damage_pct = damage;
        assert_eq!(t.damage_band(), band, "{damage}");
    }
}

#[test]
fn test_the_wall_sits_below_a_full_meter() {
    // The owner's rule: a wrecked truck stops while it still has paint on it.
    const { assert!(DAMAGE_OUT_OF_SERVICE_PCT < DAMAGE_MAX_PCT) };
    const { assert!(DAMAGE_LAST_CALL_PCT < DAMAGE_OUT_OF_SERVICE_PCT) };
}

// -- what the bands do to the truck ------------------------------------------------

#[test]
fn test_derate_reaches_the_engine_torque_the_truck_actually_makes() {
    let mut healthy = TruckState::default();
    let mut hurt = TruckState::default();
    hurt.damage_pct = DAMAGE_LIMP_PCT;
    for t in [&mut healthy, &mut hurt] {
        t.engine_on = true;
        t.throttle = 1.0;
        t.velocity_mps = 20.0;
        t.transmission.automatic = true;
        t.transmission.gear = 8;
    }

    assert!(hurt.drive_force() < healthy.drive_force());
}

#[test]
fn test_derated_engine_burns_more_fuel_for_the_same_work() {
    let mut burned = Vec::new();
    let mut healthy = TruckState::default();
    let mut hurt = TruckState::default();
    hurt.damage_pct = DAMAGE_LAST_CALL_PCT;
    for t in [&mut healthy, &mut hurt] {
        t.engine_on = true;
        t.throttle = 0.5;
        t.velocity_mps = 25.0;
        let before = t.fuel_gal;
        for _ in 0..120 {
            t.update_fuel(DT);
        }
        burned.push(before - t.fuel_gal);
    }

    assert!(burned[1] > burned[0], "{burned:?}");
}

#[test]
fn test_speed_cap_cuts_fuel_like_a_road_speed_governor() {
    let mut t = TruckState::default();
    t.engine_on = true;
    t.throttle = 1.0;
    t.transmission.automatic = true;
    t.transmission.gear = 8;
    t.velocity_mps = DAMAGE_LIMP_CAP_MPH * MPS_PER_MPH;
    assert!(t.drive_force() > 0.0);

    t.speed_cap_mph = Some(DAMAGE_LIMP_CAP_MPH);
    assert_eq!(t.drive_force(), 0.0);
    assert_eq!(t.hold_throttle(), 0.0);

    // Under the cap the engine still pulls: this is a governor, not a brake.
    t.velocity_mps = (DAMAGE_LIMP_CAP_MPH - 10.0) * MPS_PER_MPH;
    assert!(t.drive_force() > 0.0);
}

#[test]
fn test_out_of_service_leaves_the_engine_alone() {
    // The wall is not a dead engine: a stricken truck must be able to crawl
    // out of a live lane rather than sit in one.
    let mut t = TruckState::default();
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT;
    assert!(t.out_of_service());
    t.engine_on = true;
    t.velocity_mps = 20.0;

    t.update(DT);

    assert!(t.engine_on);
    t.stop_engine();
    assert!(t.start_engine());
}

#[test]
fn test_roadside_repair_leaves_the_truck_stopped_and_restartable() {
    let mut t = TruckState::default();
    t.damage_pct = DAMAGE_OUT_OF_SERVICE_PCT;
    t.velocity_mps = 20.0;

    // 60 percent, the level the road crew's patch reaches (the game layer's
    // BREAKDOWN_REPAIR_DAMAGE_PCT, which `ff-core` cannot see from here).
    t.recover_from_breakdown(60.0);

    assert_eq!(t.damage_pct, 60.0);
    assert_eq!(t.velocity_mps, 0.0);
    assert_eq!(t.speed_cap_mph, None);
    assert!(!t.out_of_service());
    t.parking_brake = false;
    assert!(t.start_engine());
}

// -- the runaway -------------------------------------------------------------------

#[test]
fn test_a_runaway_destroys_the_truck_instead_of_just_chiming() {
    // Coasting out of gear down a grade used to reach 128 mph with nothing
    // but an overspeed chime. It now wrecks the truck, and the bands own it.
    let mut t = TruckState::default();
    t.transmission.gear = 0; // neutral, no driveline to hold anything back
    t.velocity_mps = 128.0 * MPS_PER_MPH;

    for _ in 0..(60 * 30) {
        t.update_wear(DT);
        if t.out_of_service() {
            break;
        }
    }

    assert!(t.out_of_service());
}

#[test]
fn test_below_the_runaway_threshold_nothing_accrues() {
    let mut t = TruckState::default();
    t.velocity_mps = (RUNAWAY_SPEED_MPH - 5.0) * MPS_PER_MPH;

    for _ in 0..600 {
        t.update_wear(DT);
    }

    assert_eq!(t.damage_pct, 0.0);
}

// -- the reverse guard -------------------------------------------------------------

#[test]
fn test_reverse_at_speed_is_refused_and_costs_the_driveline() {
    let mut t = TruckState::default();
    t.transmission.automatic = false;
    t.transmission.clutch = 1.0;
    t.velocity_mps = 60.0 * MPS_PER_MPH;

    let result = t.request_gear(REVERSE);

    assert!(!result.ok);
    assert!(result.grind);
    assert!(!t.transmission.in_reverse());
    assert!(approx(t.damage_pct, REVERSE_CRASH_DAMAGE_PCT));
}

#[test]
fn test_reverse_still_engages_at_a_standstill() {
    let mut t = TruckState::default();
    t.transmission.automatic = false;
    t.transmission.clutch = 1.0;
    t.velocity_mps = (REVERSE_ENGAGE_MAX_MPH - 1.0) * MPS_PER_MPH;

    assert!(t.request_gear(REVERSE).ok);
    assert!(t.transmission.in_reverse());
    assert_eq!(t.damage_pct, 0.0);
}

// -- the preventable share ---------------------------------------------------------

#[test]
fn test_preventable_damage_is_counted_apart_from_the_rest() {
    let mut t = TruckState::default();
    t.add_damage(10.0, true); // preventable by default: nearly everything is
    t.add_damage(6.0, false); // reacting correctly to a hazard

    assert!(approx(t.damage_pct, 16.0));
    assert!(approx(t.preventable_damage_pct, 10.0));
}

#[test]
fn test_collisions_and_runaways_count_as_preventable() {
    let mut t = TruckState::default();
    t.velocity_mps = 20.0;
    t.apply_collision(0.5, true);
    assert!(t.preventable_damage_pct > 0.0);

    let mut runaway = TruckState::default();
    runaway.velocity_mps = 120.0 * MPS_PER_MPH;
    for _ in 0..120 {
        runaway.update_wear(DT);
    }
    assert!(runaway.damage_pct > 0.0);
    assert!(approx(runaway.preventable_damage_pct, runaway.damage_pct));
}
