//! `states/driving_facility_gate.rs`, `states/driving_pickup.rs`,
//! `states/driving_liquid.rs` and `states/driving_stops.rs`.
//!
//! Ported from `tests/test_facility_overshoot.py`, the drive-cue half of
//! `tests/test_tanker_surge.py`, and the pickup-gate half of
//! `tests/test_pickup_loading.py`. Cases that need a mixin this task did not
//! port keep their bodies behind `#[ignore]`.

use std::cell::RefCell;
use std::rc::Rc;

use ff_core::data::world::{get_world, World};
use ff_core::models::jobs::{Job, CARGO_CATALOG};
use ff_core::models::profile::Profile;
use ff_core::sim::surge::LiquidLoad;
use ff_core::sim::trip_models::FACILITY_GATE_LIMIT_MPH;
use ff_core::sim::vehicle::TruckState;

use freight_fate::app::testing::{FakeClock, TestApp};
use freight_fate::audio::{Audio, AudioError, SustainLoopSpec, VolumeUpdate, CH_SURGE};
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::*;
use freight_fate::states::driving_facility_gate::GATE_MISS_LOOP_MIN;
use freight_fate::states::driving_stops::{
    assist_full_decel_mps2, assist_servo_brake, bar_solid_zone_mi, bar_tick_range_mi,
};

// -- rigging -------------------------------------------------------------------------

/// `_driving(app)`: a Buffalo to Rochester delivery.
fn a_drive(app: &mut TestApp) -> DrivingState {
    let world = get_world();
    let mut profile = Profile::named_in("Gates", "Buffalo");
    profile.tutorial_done = true;
    app.ctx.profile = Some(profile);
    let route = world
        .supported_route("Buffalo", "Rochester", None)
        .expect("the world routes")
        .expect("Buffalo to Rochester has a route");
    let mut job = Job::new(
        &CARGO_CATALOG["general"],
        12.0,
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
        Some(0),
        DRIVE_PHASE_DELIVERY,
        Some(12.0),
    );
    drive.trip.set_npc_vehicles(Vec::new());
    drive
}

/// `(city, location_name)` of a facility with a tier-1 street chain, or None
/// when the shipped data has none.
fn a_turn_level_facility(world: &'static World) -> Option<(String, String)> {
    let mut keys: Vec<&String> = world.cities.keys().collect();
    keys.sort();
    for city in keys {
        let Some(entry) = world.cities.get(city) else {
            continue;
        };
        for location in &entry.locations {
            let Ok(route) = world.facility_approach_route(city, &location.name) else {
                continue;
            };
            if route.legs.len() >= 2 && route.legs.iter().any(|leg| leg.local_speed_mph > 0.0) {
                return Some((city.clone(), location.name.clone()));
            }
        }
    }
    None
}

/// A facility whose street chain turns a corner inside its first tenth of a
/// mile, or None when the shipped data has none.
fn a_facility_with_an_early_corner(world: &'static World) -> Option<(String, String)> {
    let mut keys: Vec<&String> = world.cities.keys().collect();
    keys.sort();
    for city in keys {
        let Some(entry) = world.cities.get(city) else {
            continue;
        };
        for location in &entry.locations {
            let Ok(route) = world.facility_approach_route(city, &location.name) else {
                continue;
            };
            if route.legs.len() > 1
                && route.legs[0].miles <= 0.1
                && route.legs.iter().any(|leg| leg.local_speed_mph > 0.0)
            {
                return Some((city.clone(), location.name.clone()));
            }
        }
    }
    None
}

/// `_at_gate`: put the truck right at the finished route end, rolling at
/// `mph`.
fn at_gate(d: &mut DrivingState, mph: f64, warned: bool) {
    d.destination_exit_taken = true;
    d.trip.position_mi = d.trip.total_miles();
    d.trip.finished = true;
    d.trip.truck.engine_on = true;
    d.trip.truck.velocity_mps = mph / 2.23694;
    d.gate_speed_warned = warned;
    d.gate_grace_s = 0.0;
}

/// Every event line so far that carries `needle`, newest last.
///
/// Python read `spoken[-1]` off a stubbed `say_event`. Here the real pacer is
/// in the path: an interrupting line purges the channel and hands the ROUTE
/// line it cut back to be requeued, so the rescued line legitimately lands
/// after the one that cut it. What each assertion is about is the line
/// itself, not its position behind a rescue.
fn lines_with(app: &TestApp, needle: &str) -> Vec<String> {
    app.event_lines()
        .into_iter()
        .filter(|line| line.contains(needle))
        .collect()
}

fn last_with(app: &TestApp, needle: &str) -> String {
    lines_with(app, needle)
        .pop()
        .unwrap_or_else(|| panic!("no event line carried {needle:?}: {:?}", app.event_lines()))
}

// -- the facility gate (tests/test_facility_overshoot.py) -----------------------------

#[test]
fn test_fast_crossing_misses_the_gate_and_loops_back() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    let minutes = d.trip.game_minutes;
    at_gate(&mut d, 70.0, true);
    d.handle_arrival_gate(&mut app.ctx);
    assert!(!d.trip.finished);
    assert!(d.trip.position_mi < d.trip.total_miles());
    assert_eq!(d.gate_miss_count, 1);
    assert_eq!(d.trip.game_minutes, minutes + GATE_MISS_LOOP_MIN);
    let text = last_with(&app, "safe turnaround");
    assert!(app
        .event_calls()
        .iter()
        .any(|(line, interrupt)| *line == text && *interrupt));
    assert!(text.to_lowercase().contains("slow to"));
}

#[test]
fn test_slow_crossing_arrives_normally() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    at_gate(&mut d, 10.0, false);
    d.handle_arrival_gate(&mut app.ctx);
    assert!(d.trip.finished);
    assert_eq!(d.gate_miss_count, 0);
    assert!(!lines_with(&app, "Destination ahead").is_empty());
    d.trip.truck.velocity_mps = 0.3 / 2.23694;
    d.handle_arrival_gate(&mut app.ctx);
    assert!(d.arrival_menu_open);
}

#[test]
fn test_pre_gate_warning_names_a_target_speed() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    d.destination_exit_taken = true;
    d.trip.position_mi = d.trip.total_miles() - 0.3;
    d.trip.truck.engine_on = true;
    d.trip.truck.velocity_mps = 40.0 / 2.23694;
    d.check_gate_approach_warning(&mut app.ctx, 0.016);
    let spoken = app.event_lines();
    assert_eq!(spoken.len(), 1);
    assert!(spoken[0].contains("Facility gate in"));
    assert!(spoken[0].contains("15 miles per hour"));
    assert!(d.gate_grace_s > 0.0);
    d.check_gate_approach_warning(&mut app.ctx, 0.016);
    assert_eq!(app.event_lines().len(), 1); // said once, not every frame
}

#[test]
fn test_no_instant_miss_inside_the_reaction_window() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    d.destination_exit_taken = true;
    d.trip.position_mi = d.trip.total_miles() - 0.3;
    d.trip.truck.engine_on = true;
    d.trip.truck.velocity_mps = 40.0 / 2.23694;
    d.check_gate_approach_warning(&mut app.ctx, 0.016); // warning spoken, window opens
    let grace = d.gate_grace_s;
    assert!(grace > 0.0);
    d.trip.position_mi = d.trip.total_miles();
    d.trip.finished = true;
    d.handle_arrival_gate(&mut app.ctx);
    assert!(d.trip.finished); // still inside the reaction window
    assert_eq!(d.gate_miss_count, 0);
    assert!(!lines_with(&app, "Destination ahead").is_empty());
    d.check_gate_approach_warning(&mut app.ctx, grace + 1.0); // the window expires
    d.handle_arrival_gate(&mut app.ctx);
    assert!(!d.trip.finished);
    assert_eq!(d.gate_miss_count, 1);
}

#[test]
fn test_first_gate_contact_without_a_warning_still_gets_a_window() {
    // A resumed save can arrive at the gate cold: the miss clock must start
    // with the gate's own stop line, never latch on first contact.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    at_gate(&mut d, 40.0, false);
    d.handle_arrival_gate(&mut app.ctx);
    assert!(d.trip.finished);
    assert_eq!(d.gate_miss_count, 0);
    assert!(!lines_with(&app, "Destination ahead").is_empty());
    assert!(d.gate_speed_warned);
    assert!(d.gate_grace_s > 0.0);
}

#[test]
fn test_destination_approach_assist_never_misses() {
    let mut app = TestApp::new();
    app.ctx.settings.destination_approach_assist = true;
    let mut d = a_drive(&mut app);
    at_gate(&mut d, 40.0, true);
    d.handle_arrival_gate(&mut app.ctx);
    assert!(d.trip.finished);
    assert_eq!(d.gate_miss_count, 0);
    assert_eq!(d.trip.truck.brake, 1.0); // the assist is braking the truck itself
}

#[test]
fn test_hazard_braking_never_misses() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    at_gate(&mut d, 40.0, true);
    d.hazard_deadline = Some(5.0); // mid-hazard: braking hard is the right move
    d.handle_arrival_gate(&mut app.ctx);
    assert!(d.trip.finished);
    assert_eq!(d.gate_miss_count, 0);
}

#[test]
fn test_repeat_miss_appends_the_help_clause() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    at_gate(&mut d, 70.0, true);
    d.handle_arrival_gate(&mut app.ctx);
    let first = last_with(&app, "carried past the gate");
    assert!(!first.contains("Settings"));
    at_gate(&mut d, 70.0, true);
    d.handle_arrival_gate(&mut app.ctx);
    let second = lines_with(&app, "carried past the gate")
        .into_iter()
        .find(|line| line.contains("Brake with"))
        .expect("the repeat miss appends help");
    assert!(second.contains(&first)); // the core line stays identical, help is appended
    assert!(second.contains("Down arrow"));
    assert!(second.contains("Destination approach assist"));
}

#[test]
fn test_miss_resets_the_gate_latches() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    at_gate(&mut d, 70.0, true);
    d.arrival_stop_said = true;
    d.arrival_full_stop_said = true;
    d.gate_reminder_s = 5.0;
    d.handle_arrival_gate(&mut app.ctx);
    assert!(!d.arrival_stop_said);
    assert!(!d.arrival_full_stop_said);
    assert_eq!(d.gate_reminder_s, 0.0);
    assert!(!d.gate_speed_warned); // the next approach warns fresh
}

#[test]
fn test_reapproach_after_a_miss_arrives_normally() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    at_gate(&mut d, 70.0, true);
    d.handle_arrival_gate(&mut app.ctx); // the miss
                                         // Back at the gate at a sane speed this time.
    d.trip.position_mi = d.trip.total_miles();
    d.trip.finished = true;
    d.trip.truck.velocity_mps = 2.0 / 2.23694;
    d.handle_arrival_gate(&mut app.ctx);
    assert!(!lines_with(&app, "Stop to dock").is_empty());
    d.trip.truck.velocity_mps = 0.3 / 2.23694;
    d.handle_arrival_gate(&mut app.ctx);
    assert!(d.arrival_menu_open);
}

#[test]
fn test_the_gate_warning_names_a_limit_that_is_really_posted() {
    // "Slow to 15" has to be the number in force, not a number nothing posts.
    //
    // The arrival zones are dropped at trip start so no silent low limit writes
    // speeding fines under a spoken 65 on the final freeway miles. That left the
    // pre-gate warning naming 15 while the last half mile still read the
    // corridor's own limit, so every assist held the corridor number straight
    // through the entrance and into the loop-back (owner playtest, 2026-08-21).
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    // While the truck is still on the highway, nothing has changed: the
    // arrival zones stay off the map.
    assert!(!d.trip.zones.iter().any(|z| z.reason == "facility gate"));
    let end = d.trip.total_miles() - 0.3;
    let (corridor, _) = d.trip.speed_limit_at(end);
    assert!(corridor > FACILITY_GATE_LIMIT_MPH);

    // Taking the destination exit puts the driveway's own limit back.
    // This is the NO-CHAIN case: a facility whose own streets become the
    // trip posts its gate from that chain instead, and posting one here as
    // well would announce the same gate twice. (Python monkeypatched
    // `_surface_chain_route` to None; naming a location the world has no
    // approach for is the same thing without the patch.)
    d.job.destination_location = "no such facility".to_string();
    assert!(d.surface_chain_route(&app.ctx).is_none());
    d.destination_exit_taken = true;
    d.post_gate_zone(&app.ctx);
    let (posted, reason) = d.trip.speed_limit_at(end);
    assert_eq!(reason.as_deref(), Some("facility gate"));
    assert_eq!(posted, FACILITY_GATE_LIMIT_MPH);

    app.clear_speech();
    d.trip.position_mi = end;
    d.trip.truck.engine_on = true;
    d.trip.truck.velocity_mps = 40.0 / 2.23694;
    d.check_gate_approach_warning(&mut app.ctx, 0.016);
    // The spoken target and the posted limit are the same number.
    let target = app.ctx.settings.speed_text(posted);
    assert!(app.event_lines()[0].contains(&target));
    // Posting it twice would stack two gate zones on one driveway.
    d.post_gate_zone(&app.ctx);
    assert_eq!(
        d.trip
            .zones
            .iter()
            .filter(|z| z.reason == "facility gate")
            .count(),
        1
    );
}

#[test]
fn test_terse_mode_hears_the_essential_cues() {
    let mut app = TestApp::new();
    app.ctx.settings.driving_speech = "quiet".to_string();
    let mut d = a_drive(&mut app);
    app.clear_speech();
    d.destination_exit_taken = true;
    d.trip.position_mi = d.trip.total_miles() - 0.3;
    d.trip.truck.engine_on = true;
    d.trip.truck.velocity_mps = 40.0 / 2.23694;
    d.check_gate_approach_warning(&mut app.ctx, 0.016);
    let said = last_with(&app, "Gate in");
    assert!(said.contains("Slow to"));
    at_gate(&mut d, 70.0, true);
    d.handle_arrival_gate(&mut app.ctx);
    let said = last_with(&app, "Missed the gate");
    assert!(said.contains("Safe turnaround"));
    assert!(said.to_lowercase().contains("slow to"));
}

#[test]
fn test_time_is_charged_each_loop() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    let minutes = d.trip.game_minutes;
    for _ in 0..2 {
        at_gate(&mut d, 70.0, true);
        d.handle_arrival_gate(&mut app.ctx);
    }
    assert_eq!(d.trip.game_minutes, minutes + 2.0 * GATE_MISS_LOOP_MIN);
}

#[test]
fn test_missed_gate_loop_charges_hos_fatigue_and_fuel() {
    // The spoken "The clock is still running" line must be true: a gate
    // miss's scripted loop-back costs real HOS, fatigue, and fuel, not just
    // the game clock -- otherwise the loop is a free-time exploit.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    let driving_before = hos_of(&app.ctx).driving_min;
    let fatigue_before = profile_of(&app.ctx).fatigue;
    d.trip.truck.rpm = d.trip.truck.specs.idle_rpm;
    let fuel_before = d.trip.truck.fuel_gal;

    at_gate(&mut d, 70.0, true);
    d.handle_arrival_gate(&mut app.ctx);

    assert!((hos_of(&app.ctx).driving_min - (driving_before + GATE_MISS_LOOP_MIN)).abs() < 1e-6);
    assert!(profile_of(&app.ctx).fatigue > fatigue_before);
    assert!(d.trip.truck.fuel_gal < fuel_before);
    // Idle-rate honesty: ~0.8 gal/h floor, so twenty minutes is a small,
    // bounded sip, not a fraction of a highway-cruise burn.
    assert!(fuel_before - d.trip.truck.fuel_gal < 1.0);
}

#[test]
fn test_snapshot_round_trips_the_miss_count() {
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.gate_miss_count = 2;
    let snapshot = d.snapshot(&app.ctx);
    let resumed = DrivingState::from_snapshot(&mut app.ctx, &snapshot).expect("the drive resumes");
    assert_eq!(resumed.gate_miss_count, 2);
}

#[test]
fn test_a_facility_with_its_own_streets_does_not_get_a_second_gate_zone() {
    // One gate, one announcement.
    //
    // A facility whose approach is a real street chain drives those streets as a
    // trip of their own, and that trip builds a gate zone at its end. Posting one
    // on the highway trip as well put the same gate on the map twice, so the
    // driver heard it announced coming off the ramp and again on the streets
    // (owner, 2026-08-21).
    let world = get_world();
    let Some((city, location)) = a_turn_level_facility(world) else {
        return; // no turn-level facility approaches in the shipped data
    };
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    d.job.destination = city;
    d.job.destination_location = location;
    assert!(d.surface_chain_route(&app.ctx).is_some()); // this facility has streets
    d.destination_exit_taken = true;
    d.post_gate_zone(&app.ctx);
    assert!(!d.trip.zones.iter().any(|z| z.reason == "facility gate"));
}

#[test]
fn test_the_hold_prompt_does_not_come_back_once_the_menu_is_open() {
    // "Press Enter to continue" must not be handed back after Enter.
    //
    // The prompt speaks once -- the say-once flag sees to that, and a real
    // roll-in produces exactly one.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);
    app.ctx.settings.destination_approach_assist = true;
    app.clear_speech();
    at_gate(&mut d, 0.2, false);
    d.handle_arrival_gate(&mut app.ctx);
    let holds = |app: &TestApp| {
        app.event_lines()
            .into_iter()
            .filter(|line| line.contains("stopped and holding"))
            .count()
    };
    assert_eq!(holds(&app), 1);

    // Said once and only once, however long the driver sits there.
    for _ in 0..50 {
        d.handle_arrival_gate(&mut app.ctx);
    }
    assert_eq!(holds(&app), 1);
}

#[test]
#[ignore = "deferred: a hands-off end-to-end drive over baked chain data"]
fn test_the_approach_assist_stops_the_truck_on_a_facility_street_chain() {
    // Owner, Spokane, 2026-08-21: "it did not automatically stop at the
    // destination; I had to stop." Drives the whole frame loop hands off and
    // measures where the truck comes to rest relative to the gate.
}

#[test]
#[ignore = "deferred: a hands-off end-to-end drive over baked chain data"]
fn test_the_approach_assist_stops_within_a_truck_length_of_the_gate() {
    // The other half of the Spokane report: stopping means stopping AT the
    // gate, not a city block past it.
}

#[test]
fn test_the_ramp_is_not_the_arrival_when_a_street_chain_follows_it() {
    // Owner, Spokane, 2026-08-22: "it didn't stop where I can pull it in."
    //
    // With the pedal finally reaching the truck, the assist stopped it dead at
    // the bottom of the destination ramp -- a mile of city streets short of the
    // gate -- and left automatic speed control paused the arrival way for the
    // whole chain. The ramp's end is a driving continuation when a chain
    // follows; the arrival is the chain's own, a mile on.
    let world = get_world();
    let Some((city, location)) = a_turn_level_facility(world) else {
        return; // no baked facility street chain in the shipped data
    };
    let mut app = TestApp::new();
    app.ctx.settings.destination_approach_assist = true;
    let mut d = a_drive(&mut app);
    d.job.destination = city;
    d.job.destination_location = location;
    d.destination_chain_ahead = None;
    assert!(d.destination_street_chain_ahead(&app.ctx));

    // On the destination ramp, well inside the distance a 30 mph truck needs
    // to stop: exactly where the ramp-as-gate branch latched.
    let destination = d
        .destination_exit_stop(&mut app.ctx)
        .expect("a destination exit");
    d.ramp_stop = Some(destination);
    d.ramp_mi = Some(0.05);
    d.trip.truck.start_engine();
    d.trip.truck.transmission.automatic = true;
    d.trip.truck.transmission.gear = 6;
    d.trip.truck.velocity_mps = 30.0 / 2.23694;
    d.trip.truck.brake = 0.0;
    d.update_destination_approach_assist(&mut app.ctx);

    assert!(!d.destination_arrival_active);
    assert_eq!(d.trip.truck.brake, 0.0);
    assert_eq!(d.destination_assist_brake, 0.0);

    // And the same ramp IS the arrival when nothing follows it: the
    // ramp-to-dock delivery the 2026-08-19 fix was made for still stops.
    d.destination_chain_ahead = Some(false);
    d.ramp_mi = Some(RAMP_LENGTH_MI * 0.1);
    d.update_destination_approach_assist(&mut app.ctx);
    assert!(d.destination_arrival_active);
    assert!(d.trip.truck.brake > 0.0);
}

#[test]
#[ignore = "deferred: a hands-off end-to-end drive over baked chain data"]
fn test_the_approach_assist_delivers_the_truck_to_the_dock() {
    // Jerry, Hobbs Food Processing Plant, 2026-08-22: through the ramp light
    // on green, "Destination approach assistance slowing", 8 miles per hour,
    // 2 miles per hour -- and then nothing. Level, uphill, downhill, and from
    // the top of the ramp, the dock menu must open hands off.
}

#[test]
#[ignore = "deferred: a hands-off end-to-end drive over baked chain data"]
fn test_the_approach_assist_delivers_the_truck_to_a_street_chain_gate_uphill() {
    // The same promise on a facility street chain, with the gate at the top
    // of a grade: the road takes speed off for free there, which is exactly
    // where a brake-only profile stops short.
}

#[test]
fn test_off_the_ramp_carries_the_first_corner_and_hands_speed_control_back() {
    // Owner, Spokane, 2026-08-22: "the assist did not stop and I had to
    // brake to start the turn onto city streets."
    //
    // The chain begins a few hundred feet before its first corner. Raised on
    // its own a frame after the swap, that corner's call queued as a
    // droppable lead behind the off-the-ramp line and the gate warning, went
    // stale, and was dropped -- twice, the second time after the loop-back --
    // so it was never heard. And the truck came off with nothing holding it:
    // the ramp's transit pause was still on, so the keeper that would have
    // eased for the corner had not come back.
    //
    // The first corner is spoken IN the handoff line, and the pause ends at
    // the handoff.
    let world = get_world();
    let Some((city, location)) = a_facility_with_an_early_corner(world) else {
        return; // no baked chain with a corner inside the first tenth of a mile
    };
    let mut app = TestApp::new();
    app.ctx.settings.destination_approach_assist = true;
    app.ctx.settings.speed_keeper = true;
    let mut d = a_drive(&mut app);
    d.job.destination = city;
    d.job.destination_location = location;
    d.destination_chain_ahead = None;

    // The ramp's transit pause, exactly as the terminal leaves it.
    d.speed_control_armed = true;
    d.pause_speed_control(&mut app.ctx, true);
    assert!(d.speed_control_paused_at_stop);

    d.trip.position_mi = d.trip.total_miles();
    d.trip.finished = true;
    app.clear_speech();
    assert!(d.begin_surface_chain(&mut app.ctx, true));

    let message = last_with(&app, "Off the ramp and onto city streets");
    let first_street = d.trip.route.legs[1].highway.clone();
    assert!(message.contains(&first_street), "{message}");
    assert!(message.to_lowercase().contains("turn"), "{message}");
    // Spoken here, so the commitment loop must not raise it again.
    let corner = d.turn_cue_in_play().expect("a corner is in play");
    assert!(d.turn_advised.contains(&corner.key));
    assert!(d.trip.controlled_turn);
    // And the pause is gone: the next frame may hand the streets to the
    // keeper without waiting on a driver who is off the brake.
    assert!(!d.speed_control_paused_at_stop);
}

// -- the pickup gate (tests/test_pickup_loading.py, drive half) -----------------------

#[test]
fn test_the_pickup_gate_asks_for_a_complete_stop_then_a_check_in() {
    let world = get_world();
    let mut app = TestApp::new();
    let mut profile = Profile::named_in("Deadhead", "Buffalo");
    profile.tutorial_done = true;
    app.ctx.profile = Some(profile);
    let route = world
        .supported_route("Buffalo", "Rochester", None)
        .expect("the world routes")
        .expect("a route");
    let mut job = Job::new(
        &CARGO_CATALOG["general"],
        12.0,
        "Buffalo",
        "company yard",
        "Rochester",
        route.miles(),
        1000.0,
        12.0,
    );
    job.destination_location = "Rochester freight market".to_string();
    let mut d = DrivingState::new(
        &mut app.ctx,
        job,
        route,
        Some(0),
        DRIVE_PHASE_PICKUP,
        Some(12.0),
    );
    d.trip.set_npc_vehicles(Vec::new());
    app.clear_speech();

    d.trip.truck.engine_on = true;
    d.trip.truck.velocity_mps = 20.0 / 2.23694;
    d.handle_pickup_gate(&mut app.ctx);
    let said = last_with(&app, "Pickup ahead: ");
    assert!(said.contains("come to a complete stop at the gate"));
    assert!(d.arrival_stop_said);

    // Creeping in: the gate asks for the check-in rather than repeating.
    d.trip.truck.velocity_mps = 2.0 / 2.23694;
    d.handle_pickup_gate(&mut app.ctx);
    let said = last_with(&app, "Stop to check in.");
    assert!(said.starts_with("At "));
    assert!(d.arrival_full_stop_said);
}

#[test]
fn test_the_pickup_progress_summary_speaks_the_players_unit() {
    // Spoken distances go through the unit setting; a player on metric must
    // not hear miles here just because this handler moved modules.
    let world = get_world();
    let mut app = TestApp::new();
    let mut profile = Profile::named_in("Deadhead", "Buffalo");
    profile.tutorial_done = true;
    app.ctx.profile = Some(profile);
    let route = world
        .supported_route("Buffalo", "Rochester", None)
        .expect("the world routes")
        .expect("a route");
    let mut job = Job::new(
        &CARGO_CATALOG["general"],
        12.0,
        "Buffalo",
        "company yard",
        "Rochester",
        route.miles(),
        1000.0,
        12.0,
    );
    job.destination_location = "Rochester freight market".to_string();
    let d = DrivingState::new(
        &mut app.ctx,
        job,
        route,
        Some(0),
        DRIVE_PHASE_PICKUP,
        Some(12.0),
    );
    let imperial = d.pickup_progress_summary(&app.ctx);
    assert!(imperial.contains("miles remaining of"));
    assert!(imperial.ends_with(&format!(
        "to pickup at {}.",
        d.pickup_facility_text(&app.ctx)
    )));

    app.ctx.settings.imperial_units = false;
    let metric = d.pickup_progress_summary(&app.ctx);
    assert!(metric.contains("kilometers remaining of"));
    assert!(!metric.contains("miles"));
}

// -- the tank load's cue layer (tests/test_tanker_surge.py, drive half) ---------------

/// What a [`SurgeAudio`] was asked to do. Python's `_Audio` recorded exactly
/// these four calls.
#[derive(Debug, Default)]
struct SurgeCalls {
    /// `start_loop(channel, key, volume)`.
    loops: Vec<(u32, String, f64)>,
    /// `set_loop_volume(channel, volume)`.
    volumes: Vec<(u32, f64)>,
    /// `stop_loop(channel)`.
    stops: Vec<u32>,
    /// `play(key, volume)`.
    played: Vec<(String, f64)>,
}

impl SurgeCalls {
    fn is_empty(&self) -> bool {
        self.loops.is_empty()
            && self.volumes.is_empty()
            && self.stops.is_empty()
            && self.played.is_empty()
    }
}

type SurgeLog = Rc<RefCell<SurgeCalls>>;

#[derive(Default)]
struct SurgeAudio {
    log: SurgeLog,
}

impl Audio for SurgeAudio {
    fn enabled(&self) -> bool {
        false
    }
    fn backend_name(&self) -> &str {
        "surge-recording"
    }
    fn master_volume(&self) -> f64 {
        1.0
    }
    fn sfx_volume(&self) -> f64 {
        1.0
    }
    fn music_volume(&self) -> f64 {
        1.0
    }
    fn weather_volume(&self) -> f64 {
        1.0
    }
    fn engine_volume(&self) -> f64 {
        1.0
    }
    fn ui_volume(&self) -> f64 {
        1.0
    }
    fn engine_running(&self) -> bool {
        false
    }
    fn engine_starting(&self) -> bool {
        false
    }
    fn voice_key(&self, key: &str) -> String {
        key.to_string()
    }
    fn play_with(&mut self, key: &str, volume: f64, _pan: f64) {
        self.log.borrow_mut().played.push((key.to_string(), volume));
    }
    fn play_bank_with(&mut self, base: &str, _fallback: &str, volume: f64, pan: f64) {
        self.play_with(base, volume, pan);
    }
    fn set_engine_duck(&mut self, _duck: f64) {}
    fn set_speech_duck(&mut self, _duck: f64) {}
    fn set_engine_voice(&mut self, _classic: bool) {}
    fn set_jake_voice(&mut self, _classic: bool) {}
    fn has_asset(&mut self, _key: &str) -> bool {
        true
    }
    fn start_loop_with(&mut self, channel: u32, key: &str, volume: f64, _fade_ms: u32) {
        self.log
            .borrow_mut()
            .loops
            .push((channel, key.to_string(), volume));
    }
    fn set_loop_volume(&mut self, channel: u32, volume: f64) {
        self.log.borrow_mut().volumes.push((channel, volume));
    }
    fn set_loop_pan(&mut self, _channel: u32, _pan: f64) {}
    fn stop_loop_with(&mut self, channel: u32, _fade_ms: u32) {
        self.log.borrow_mut().stops.push(channel);
    }
    fn start_sustain_loop_with(
        &mut self,
        _channel: u32,
        _key: &str,
        _spec: SustainLoopSpec,
        _volume: f64,
    ) {
    }
    fn release_sustain_loop_with(&mut self, _channel: u32, _fade_ms: u32) {}
    fn hold_alert_with(&mut self, _key: &str, _volume: f64, _fade_ms: u32) {}
    fn release_alert_with(&mut self, _fade_ms: u32) {}
    fn hold_cue(&mut self, _name: &str) {}
    fn cue_held(&self, _name: &str) -> bool {
        false
    }
    fn release_cue(&mut self, _name: &str) {}
    fn engine_start_with(&mut self, _play_start_sound: bool) {}
    fn engine_stop_with(&mut self, _shutdown_sound: bool) {}
    fn update(&mut self, _dt: f64) {}
    fn set_engine_rpm_with(&mut self, _rpm: f64, _throttle: f64) {}
    fn set_road_noise(&mut self, _speed_mps: f64) {}
    fn set_weather_with(&mut self, _key: Option<&str>, _intensity: f64) {}
    fn set_wind(&mut self, _intensity: f64) {}
    fn set_ambient_with(&mut self, _key: Option<&str>, _volume: f64) {}
    fn horn_start(&mut self) {}
    fn horn_stop(&mut self) {}
    fn reverse_start(&mut self) {}
    fn reverse_stop(&mut self) {}
    fn stop_world(&mut self) {}
    fn play_music_with(&mut self, _track: &str, _fade_ms: u32) {}
    fn play_radio_stream_with(&mut self, _url: &str, _fade_ms: u32) -> Result<(), AudioError> {
        Ok(())
    }
    fn play_music_file_with(&mut self, _path: &str, _fade_ms: u32) -> Result<(), AudioError> {
        Ok(())
    }
    fn music_playing(&self) -> bool {
        false
    }
    fn radio_now_playing(&self) -> Option<String> {
        None
    }
    fn stop_music_with(&mut self, _fade_ms: u32) {}
    fn set_volumes(&mut self, _volumes: &VolumeUpdate) {}
    fn shutdown(&mut self) {}
}

const CARGO_KG: f64 = 20_000.0;

/// `_truck(liquid, speed_mps)`.
fn a_tank_truck(liquid: Option<LiquidLoad>, speed_mps: f64) -> TruckState {
    let mut t = TruckState {
        cargo_kg: CARGO_KG,
        velocity_mps: speed_mps,
        liquid,
        ..Default::default()
    };
    t.set_air_ready(false);
    t
}

/// A drive whose truck is the one handed in, with a recording audio in place.
///
/// The event pacer runs on a fake clock the frame loop below advances: sixty
/// simulated seconds pass in microseconds of real time here, and without that
/// the pacer projects the first line as still in the air and drops the
/// settling line as chatter that would start stale.
fn a_tank_drive(
    app: &mut TestApp,
    truck: TruckState,
    terse: bool,
) -> (DrivingState, SurgeLog, FakeClock) {
    if terse {
        app.ctx.settings.driving_speech = "quiet".to_string();
    }
    let mut d = a_drive(app);
    d.trip.truck = truck;
    let audio = SurgeAudio::default();
    let log = Rc::clone(&audio.log);
    app.ctx.audio = Box::new(audio);
    let clock = app.fake_pacer_clock();
    app.clear_speech();
    (d, log, clock)
}

/// `_drive(driver, steps, decel, brake_steps)`.
fn drive_liquid(
    d: &mut DrivingState,
    app: &mut TestApp,
    clock: &FakeClock,
    steps: i32,
    decel: f64,
    brake_steps: i32,
) {
    for step in 0..steps {
        clock.advance(0.02);
        d.trip.truck.brake = if step < brake_steps { 1.0 } else { 0.0 };
        let accel = if step < brake_steps { -decel } else { 0.0 };
        if let Some(liquid) = d.trip.truck.liquid.as_mut() {
            liquid.update(0.02, accel, 0.0);
        }
        d.update_liquid_cues(&mut app.ctx, 0.02);
    }
}

#[test]
fn test_the_cue_layer_is_completely_silent_for_other_freight() {
    let mut app = TestApp::new();
    let (mut d, log, clock) = a_tank_drive(&mut app, a_tank_truck(None, 24.6), false);
    drive_liquid(&mut d, &mut app, &clock, 400, 4.0, 100);
    assert!(log.borrow().is_empty());
    assert!(app.event_lines().is_empty());
}

#[test]
fn test_the_wash_is_silent_on_steady_cruise_and_alive_once_the_load_runs() {
    let mut app = TestApp::new();
    let (mut d, log, clock) = a_tank_drive(
        &mut app,
        a_tank_truck(Some(LiquidLoad::new(0.5, false)), 24.6),
        false,
    );
    // Steady: nothing moving, nothing sounding.
    drive_liquid(&mut d, &mut app, &clock, 50, 0.0, 0);
    assert!(log.borrow().is_empty());
    // Braking: the bed comes up.
    drive_liquid(&mut d, &mut app, &clock, 200, 4.0, 100);
    let log = log.borrow();
    assert!(
        !log.loops.is_empty(),
        "the wash should sound while the liquid is running"
    );
    assert!(log.loops.iter().all(|c| c.1 == "vehicle/liquid_wash"));
    assert!(log.loops.iter().all(|c| c.0 == CH_SURGE));
}

#[test]
fn test_the_hit_fires_when_the_wave_arrives_and_is_the_loudest_thing_here() {
    let mut app = TestApp::new();
    let (mut d, log, clock) = a_tank_drive(
        &mut app,
        a_tank_truck(Some(LiquidLoad::new(0.5, false)), 24.6),
        false,
    );
    drive_liquid(&mut d, &mut app, &clock, 400, 4.0, 100);
    let log = log.borrow();
    assert!(
        !log.played.is_empty(),
        "the arriving wave should be a one-shot hit"
    );
    assert!(log.played.iter().any(|c| c.0 == "vehicle/liquid_hit"));
    let loudest_hit = log.played.iter().map(|c| c.1).fold(f64::MIN, f64::max);
    let loudest_wash = log.loops.iter().map(|c| c.2).fold(0.0, f64::max);
    assert!(loudest_hit > loudest_wash);
}

#[test]
fn test_the_lateral_hit_has_its_own_voice() {
    let mut app = TestApp::new();
    let mut truck = a_tank_truck(Some(LiquidLoad::new(0.5, false)), 20.0);
    truck.corner_advisory_mph = 25.0;
    let (mut d, log, clock) = a_tank_drive(&mut app, truck, false);
    for _ in 0..500 {
        clock.advance(0.02);
        d.trip.truck.update(0.02);
        d.update_liquid_cues(&mut app.ctx, 0.02);
    }
    let log = log.borrow();
    assert!(log
        .played
        .iter()
        .any(|c| c.0 == "vehicle/liquid_hit_lateral"));
}

#[test]
fn test_the_load_running_and_the_load_settling_are_both_spoken() {
    // A downward line is required: silence is otherwise ambiguous between
    // "settled" and "the cue layer stopped working".
    //
    // Python ran this at both verbosities against a stub context. Here the
    // real ladder is in the path, and at `quiet` it retires STATUS and
    // CONFIRMATION to earcons by design (`DRIVING_SPEECH_DISPOSITIONS`), so
    // the terse WORDING is asserted directly rather than through the voice.
    let mut app = TestApp::new();
    let (mut d, _log, clock) = a_tank_drive(
        &mut app,
        a_tank_truck(Some(LiquidLoad::new(0.5, true)), 24.6),
        false,
    );
    drive_liquid(&mut d, &mut app, &clock, 3000, 4.0, 100);
    let said = app.event_lines().join(" ").to_lowercase();
    assert!(said.contains("running forward"), "{said}");
    assert!(said.contains("settled"), "{said}");
}

#[test]
fn test_the_terse_load_lines_still_say_running_forward_and_settled() {
    // The terse half of the pair above, read off the mixin: at `quiet` the
    // ladder carries these two categories as earcons, so the words never
    // reach the capture -- but they still have to BE the short forms.
    let mut app = TestApp::new();
    app.ctx.settings.driving_speech = "quiet".to_string();
    let (mut d, _log, clock) = a_tank_drive(
        &mut app,
        a_tank_truck(Some(LiquidLoad::new(0.5, true)), 24.6),
        false,
    );
    assert!(d.terse_speech(&app.ctx));
    drive_liquid(&mut d, &mut app, &clock, 3000, 4.0, 100);
    let review = app
        .app
        .ctx
        .message_log
        .filtered_messages()
        .iter()
        .map(|message| message.text.to_lowercase())
        .collect::<Vec<_>>()
        .join(" ");
    assert!(review.contains("load running forward"), "{review}");
    assert!(review.contains("load settled"), "{review}");
}

#[test]
fn test_the_bed_is_dropped_on_the_way_out() {
    let mut app = TestApp::new();
    let (mut d, log, clock) = a_tank_drive(
        &mut app,
        a_tank_truck(Some(LiquidLoad::new(0.5, false)), 24.6),
        false,
    );
    drive_liquid(&mut d, &mut app, &clock, 200, 4.0, 100);
    log.borrow_mut().stops.clear();
    d.stop_liquid_cues(&mut app.ctx);
    assert!(log.borrow().stops.contains(&CH_SURGE));
}

#[test]
fn test_the_status_screen_can_be_asked_what_the_tank_will_do() {
    // One app for all three: `TestApp` holds the process-wide environment
    // lock, so a second one built while the first is alive would deadlock.
    let mut app = TestApp::new();
    let mut d = a_drive(&mut app);

    d.trip.truck = a_tank_truck(Some(LiquidLoad::new(0.5, false)), 24.6);
    let clause = d.liquid_status_clause();
    assert!(clause.contains("smooth bore"));
    assert!(clause.contains("half full"));
    assert!(!clause.to_lowercase().contains("outage"));

    d.trip.truck = a_tank_truck(Some(LiquidLoad::new(0.5, true)), 24.6);
    assert!(d.liquid_status_clause().contains("baffled"));

    d.trip.truck = a_tank_truck(None, 24.6);
    assert_eq!(d.liquid_status_clause(), "");
}

// -- the stop cues measure against what the truck can do (driving_stops.rs) ------------

#[test]
fn test_the_stop_bar_tick_range_is_unchanged_for_ordinary_freight() {
    // The floor is the promise: a truck that stops inside the old three
    // hundred feet hears the bar exactly where it always did.
    let truck = a_tank_truck(None, 13.4); // 30 mph, a normal bar approach
    assert!((bar_tick_range_mi(&truck) - RAMP_BAR_TICK_RANGE_MI).abs() < 1e-9);
    assert!((bar_solid_zone_mi(&truck) - RAMP_BAR_SOLID_MI).abs() < 1e-9);
}

#[test]
fn test_the_stop_bar_tick_starts_earlier_when_the_truck_needs_more_road() {
    // A blind driver's whole model of where the bar is, is the tick's rate.
    // It has to be measured against a range this truck can stop inside.
    let dry = a_tank_truck(None, 24.6);
    let wet = a_tank_truck(Some(LiquidLoad::new(0.5, false)), 24.6);
    assert!(bar_tick_range_mi(&wet) > bar_tick_range_mi(&dry));

    // And the same is true of every other reason a truck stops long, which is
    // the point: this was owed work independent of any tank.
    let mut icy = a_tank_truck(None, 24.6);
    icy.grip = 0.3;
    assert!(bar_tick_range_mi(&icy) > bar_tick_range_mi(&dry));

    let mut downhill = a_tank_truck(None, 24.6);
    downhill.grade = -0.06;
    assert!(bar_tick_range_mi(&downhill) > bar_tick_range_mi(&dry));

    let mut faded = a_tank_truck(None, 24.6);
    faded.brake_temp_c = 600.0;
    faded.brake_wear_pct = 90.0;
    assert!(bar_tick_range_mi(&faded) > bar_tick_range_mi(&dry));
}

#[test]
fn test_the_held_tone_comes_in_early_when_sixty_feet_is_not_enough() {
    let close = a_tank_truck(Some(LiquidLoad::new(0.5, false)), 13.4);
    assert!(bar_solid_zone_mi(&close) > RAMP_BAR_SOLID_MI);
}

#[test]
fn test_the_stopping_assist_can_only_ever_press_harder_than_it_used_to() {
    for truck in [
        a_tank_truck(None, 24.6),
        a_tank_truck(Some(LiquidLoad::new(0.5, false)), 24.6),
        a_tank_truck(Some(LiquidLoad::new(0.5, true)), 24.6),
    ] {
        assert!(assist_full_decel_mps2(&truck) <= RAMP_ASSIST_FULL_DECEL_MPS2);
        assert!(assist_full_decel_mps2(&truck) > 0.0);
    }
}

#[test]
fn test_the_servo_rises_at_once_and_releases_only_past_the_band() {
    // Easing off is free; it is coming back on that costs air, so the pedal
    // follows a falling demand only once the fall is worth a release (bench
    // trace, 2026-08-11: 276 applications on one flat approach).
    let truck = a_tank_truck(None, 24.6);
    let full = assist_full_decel_mps2(&truck);
    let floor = RAMP_ASSIST_DECEL_START_MPS2 / full;
    // The floor and the trigger demand agree at first press.
    assert!((assist_servo_brake(0.0, RAMP_ASSIST_DECEL_START_MPS2, &truck) - floor).abs() < 1e-9);
    // A rising demand is taken at once.
    let harder = assist_servo_brake(floor, full * 0.8, &truck);
    assert!(harder > floor);
    // A demand that dips a hair under the pedal costs no application.
    let dip = full * (harder - RAMP_ASSIST_RELEASE_BAND / 2.0);
    assert_eq!(assist_servo_brake(harder, dip, &truck), harder);
    // Past the band it does let go.
    let real_fall = full * (harder - RAMP_ASSIST_RELEASE_BAND * 2.0);
    assert!(assist_servo_brake(harder, real_fall, &truck) < harder);
    // And it never asks for more pedal than there is.
    assert_eq!(assist_servo_brake(0.0, 99.0, &truck), 1.0);
}
