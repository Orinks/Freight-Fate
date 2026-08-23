//! The facility street chains (`tests/test_surface_chain.py`,
//! `tests/test_departure_chain.py`), plus the `driving_events` cases that
//! cannot run until another driving mixin lands -- those keep their ported
//! bodies behind `#[ignore]`.

use ff_core::data::world::{get_world, World};
use ff_core::models::jobs::make_reposition_job;
use ff_core::models::profile::Profile;
use ff_core::sim::trip_models::RoadStop;

use freight_fate::app::testing::TestApp;
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::*;

/// `(city, location_name)` of a facility with a tier-1 street chain, or None
/// when the shipped data has none (`_turn_level_facility`).
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

/// A delivery whose destination is `city` / `location_name`.
fn a_drive_to(app: &mut TestApp, city: &str, location_name: &str) -> Option<DrivingState> {
    let world = get_world();
    let mut profile = Profile::named_in("Chain", "Denver");
    profile.tutorial_done = true;
    app.ctx.profile = Some(profile);
    let route = world.shortest_route("Denver", city, None, false).ok()??;
    let mut job = make_reposition_job(world, "Denver", city, false, None)?;
    job.destination_location = location_name.to_string();
    let mut drive = DrivingState::new(
        &mut app.ctx,
        job,
        route,
        Some(0),
        DRIVE_PHASE_DELIVERY,
        Some(12.0),
    );
    drive.trip.set_npc_vehicles(Vec::new());
    Some(drive)
}

#[test]
fn test_chain_swaps_to_streets_and_keeps_the_clock() {
    let world = get_world();
    let Some((city, location)) = a_turn_level_facility(world) else {
        return; // no turn-level facility approaches in the shipped data
    };
    let mut app = TestApp::new();
    let Some(mut d) = a_drive_to(&mut app, &city, &location) else {
        return; // no corridor route from Denver to that city
    };
    d.trip.game_minutes = 123.0;
    let start_hour = d.trip.start_hour;
    let career_hours = d.trip.career_hours;
    d.destination_exit_taken = true;

    assert!(d.begin_surface_chain(&mut app.ctx, true));
    assert!(d.surface_chain);
    assert!(d.highway_trip.is_some());
    // Clock, weekday, and settlement continuity.
    assert_eq!(d.trip.game_minutes, 123.0);
    assert_eq!(d.trip.start_hour, start_hour);
    assert_eq!(d.trip.career_hours, career_hours);
    // The streets are real tier-1 segments with per-street zones.
    assert!(d.trip.route.legs.len() >= 2);
    assert!(d
        .trip
        .route
        .legs
        .iter()
        .any(|leg| leg.local_speed_mph > 0.0));
    assert!(d
        .trip
        .zones
        .iter()
        .any(|zone| zone.reason == "facility access road"));
    assert!(d
        .trip
        .zones
        .iter()
        .any(|zone| zone.reason == "facility gate"));
    // No random hazards on the last city miles.
    assert_eq!(d.trip.hazard_scale, 0.0);
}

#[test]
fn test_the_chain_takes_the_truck_and_the_weather_with_it() {
    // Python aliased one truck object from both trips; the Rust `Trip` owns
    // its truck and weather, so the swap has to carry them across.
    let world = get_world();
    let Some((city, location)) = a_turn_level_facility(world) else {
        return;
    };
    let mut app = TestApp::new();
    let Some(mut d) = a_drive_to(&mut app, &city, &location) else {
        return;
    };
    d.trip.truck.start_engine();
    d.trip.truck.damage_pct = 11.0;
    let weather = d.trip.weather.current;
    d.destination_exit_taken = true;

    assert!(d.begin_surface_chain(&mut app.ctx, false));

    assert_eq!(d.trip.truck.damage_pct, 11.0);
    assert!(d.trip.truck.engine_on);
    assert_eq!(d.trip.weather.current, weather);
}

#[test]
fn test_chain_declines_without_turn_level_data() {
    let world = get_world();
    // A facility WITHOUT a turn-level approach.
    let mut plain: Option<(String, String)> = None;
    let mut keys: Vec<&String> = world.cities.keys().collect();
    keys.sort();
    'outer: for city in keys {
        let Some(entry) = world.cities.get(city) else {
            continue;
        };
        for location in &entry.locations {
            let short = match world.facility_approach_route(city, &location.name) {
                Ok(route) => {
                    route.legs.len() < 2 || !route.legs.iter().any(|leg| leg.local_speed_mph > 0.0)
                }
                Err(_) => false,
            };
            if short {
                plain = Some((city.clone(), location.name.clone()));
                break 'outer;
            }
        }
    }
    let Some((city, location)) = plain else {
        return;
    };
    let mut app = TestApp::new();
    let Some(mut d) = a_drive_to(&mut app, &city, &location) else {
        return;
    };
    let generation = d.trip_generation;

    assert!(!d.begin_surface_chain(&mut app.ctx, false));
    assert_eq!(d.trip_generation, generation);
    assert!(!d.surface_chain);
}

#[test]
fn test_chain_survives_save_and_resume() {
    let world = get_world();
    let Some((city, location)) = a_turn_level_facility(world) else {
        return;
    };
    let mut app = TestApp::new();
    let Some(mut d) = a_drive_to(&mut app, &city, &location) else {
        return;
    };
    d.destination_exit_taken = true;
    assert!(d.begin_surface_chain(&mut app.ctx, false));
    d.trip.position_mi = 1.0f64.min(d.trip.total_miles() / 2.0);
    let snap = d.snapshot(&app.ctx);
    assert_eq!(snap["surface_chain"], true);

    let resumed = DrivingState::from_snapshot(&mut app.ctx, &snap).expect("the snapshot resumes");
    assert!(resumed.surface_chain);
    assert!(resumed.destination_exit_taken);
    assert!(resumed
        .trip
        .route
        .legs
        .iter()
        .any(|leg| leg.local_speed_mph > 0.0));
    assert!((resumed.trip.position_mi - d.trip.position_mi).abs() < 1e-6);
    assert!((resumed.trip.game_minutes - d.trip.game_minutes).abs() < 1e-6);
}

#[test]
fn test_a_departure_chain_and_a_surface_chain_never_run_together() {
    let world = get_world();
    let Some((city, location)) = a_turn_level_facility(world) else {
        return;
    };
    let mut app = TestApp::new();
    let Some(mut d) = a_drive_to(&mut app, &city, &location) else {
        return;
    };
    d.surface_chain = true;
    assert!(!d.begin_departure_chain(&mut app.ctx, false));
}

// -- cases that wait on another driving mixin -----------------------------------------

#[test]
fn test_exit_missed_when_too_fast() {
    // `tests/test_driving_exits.py`: the gore refuses a truck carrying more
    // than road speed, and the exit is settled either way.
    let mut app = TestApp::new();
    let world = get_world();
    let mut profile = Profile::named_in("Exits", "Denver");
    profile.tutorial_done = true;
    app.ctx.profile = Some(profile);
    let job = make_reposition_job(world, "Denver", "Cheyenne", false, None).expect("a reposition");
    let route = world
        .shortest_route("Denver", "Cheyenne", None, false)
        .expect("the world routes")
        .expect("a route");
    let mut d = DrivingState::new(
        &mut app.ctx,
        job,
        route,
        Some(0),
        DRIVE_PHASE_DELIVERY,
        Some(12.0),
    );
    let stop: RoadStop = d.trip.stops[0].clone();
    d.trip.position_mi = stop.at_mi - 1.0;
    // Python used a flat 29 m/s (~65 mph) on the corridor a default new career
    // starts on. The gore's acceptance is corridor-aware (posted limit plus
    // the enforcement leeway), and this corridor is a fast one, so the speed
    // is taken from the gate itself: comfortably over whatever it will accept.
    let too_fast_mph = d.gore_acceptance_mph(Some(&stop)) + 10.0;
    d.trip.truck.velocity_mps = too_fast_mph / 2.2369362920544;
    d.toggle_exit_signal(&mut app.ctx);
    assert_eq!(d.exit_stop.as_ref().map(|s| s.key()), Some(stop.key()));
    d.exit_lane_alignment = 1.0;
    d.trip.position_mi = stop.at_mi;

    d.update_frame(&mut app.ctx, 1.0 / 60.0);

    assert!(d.ramp_mi.is_none(), "blew past it");
    assert!(d.exit_stop.is_none());
}

#[test]
fn test_taking_the_exit_puts_the_truck_on_the_ramp() {
    let mut app = TestApp::new();
    let world = get_world();
    let mut profile = Profile::named_in("Exits", "Denver");
    profile.tutorial_done = true;
    app.ctx.profile = Some(profile);
    let job = make_reposition_job(world, "Denver", "Cheyenne", false, None).expect("a reposition");
    let route = world
        .shortest_route("Denver", "Cheyenne", None, false)
        .expect("the world routes")
        .expect("a route");
    let mut d = DrivingState::new(
        &mut app.ctx,
        job,
        route,
        Some(0),
        DRIVE_PHASE_DELIVERY,
        Some(12.0),
    );
    let stop: RoadStop = d.trip.stops[0].clone();
    d.trip.position_mi = stop.at_mi - 1.0;
    d.trip.truck.velocity_mps = 13.0; // ~29 mph: inside gore acceptance
    d.toggle_exit_signal(&mut app.ctx);
    d.exit_lane_alignment = 1.0;
    d.trip.position_mi = stop.at_mi;

    d.update_frame(&mut app.ctx, 1.0 / 60.0);

    assert_eq!(d.ramp_mi, Some(RAMP_LENGTH_MI));
    assert!(d.ramp_stop.is_some());
}

#[test]
fn test_a_blown_destination_terminal_loops_back() {
    // `tests/test_destination_terminal_miss.py`: the terminal used to be the
    // one blown stop with no consequence at all (owner playtest, Buffalo to
    // Albany, 2026-08-12).
    let mut app = TestApp::new();
    let world = get_world();
    let mut profile = Profile::named_in("Miss", "Denver");
    profile.tutorial_done = true;
    app.ctx.profile = Some(profile);
    let job = make_reposition_job(world, "Denver", "Cheyenne", false, None).expect("a reposition");
    let route = world
        .shortest_route("Denver", "Cheyenne", None, false)
        .expect("the world routes")
        .expect("a route");
    let mut d = DrivingState::new(
        &mut app.ctx,
        job,
        route,
        Some(0),
        DRIVE_PHASE_DELIVERY,
        Some(12.0),
    );
    let stop = RoadStop::new("Acme Freight", d.trip.total_miles(), "delivery_destination");
    d.ramp_stop = Some(stop.clone());
    d.ramp_mi = Some(-RAMP_OVERSHOOT_MI - 0.1);
    d.ramp_end_said = true;
    d.ramp_arrival_grace_s = 0.0;
    let minutes = d.trip.game_minutes;

    d.loop_back_to_destination_terminal(&mut app.ctx, &stop);

    assert_eq!(d.ramp_terminal_miss_count, 1);
    assert!(d.trip.game_minutes >= minutes + RAMP_TERMINAL_MISS_LOOP_MIN);
    assert!(d.ramp_mi.unwrap() >= RAMP_ACCESS_MI);
    assert!(!d.ramp_end_said, "the arrival line speaks fresh");
    assert!(d.status_text.contains("Drove past"));
}

#[test]
fn test_the_missed_destination_exit_loops_back_a_whole_window() {
    // `tests/test_exit_recovery.py`: under time compression one mile passes
    // in a few real seconds, making the re-approach unwinnable before it was
    // heard.
    let mut app = TestApp::new();
    let world = get_world();
    let mut profile = Profile::named_in("Recovery", "Denver");
    profile.tutorial_done = true;
    app.ctx.profile = Some(profile);
    let job = make_reposition_job(world, "Denver", "Cheyenne", false, None).expect("a reposition");
    let route = world
        .shortest_route("Denver", "Cheyenne", None, false)
        .expect("the world routes")
        .expect("a route");
    let mut d = DrivingState::new(
        &mut app.ctx,
        job,
        route,
        Some(0),
        DRIVE_PHASE_DELIVERY,
        Some(12.0),
    );
    d.trip.position_mi = d.trip.total_miles();
    d.trip.finished = true;
    let minutes = d.trip.game_minutes;

    d.handle_missed_destination_exit(&mut app.ctx);

    assert!(!d.trip.finished);
    assert!(d.missed_destination_exit_said);
    assert!(d.trip.game_minutes >= minutes + EXIT_MISS_LOOP_MIN);
    assert!(d.trip.position_mi < d.trip.total_miles() - 1.0);
    assert_eq!(d.destination_exit_announced_key, "");
    assert!(d.destination_exit_cache.is_none());
}

#[test]
#[ignore = "unblocked: states::driving_rest_states exists; the case is not written yet"]
fn test_the_rest_key_opens_a_route_points_menu() {
    // `tests/test_driving_exits.py`: T at a standstill beside a stop opens
    // that stop's own menu.
    let mut app = TestApp::new();
    let world = get_world();
    let mut profile = Profile::named_in("Rest", "Denver");
    profile.tutorial_done = true;
    app.ctx.profile = Some(profile);
    let job = make_reposition_job(world, "Denver", "Cheyenne", false, None).expect("a reposition");
    let route = world
        .shortest_route("Denver", "Cheyenne", None, false)
        .expect("the world routes")
        .expect("a route");
    let mut d = DrivingState::new(
        &mut app.ctx,
        job,
        route,
        Some(0),
        DRIVE_PHASE_DELIVERY,
        Some(12.0),
    );
    let stop = d.trip.stops[0].clone();
    d.trip.position_mi = stop.at_mi;
    d.trip.truck.velocity_mps = 0.0;

    d.try_rest_stop(&mut app.ctx);

    assert!(app.ctx.stack_len() > 0, "the stop menu is on the stack");
}
