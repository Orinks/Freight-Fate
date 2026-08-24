//! A screen reader's press-and-release train through the real driving frame
//! (`test_driving_reads_a_jaws_held_accelerator_as_steady_throttle` in
//! `tests/test_held_keys.py`): the pairs JAWS delivers for a held Up arrow,
//! at the cadence measured on the owner's machine, drive the truck, the
//! throttle never stutters, and it comes off within a second of the pairs
//! stopping. The unit tests beside `app::held_keys` cover the tracker
//! itself; this is the wiring, clocked the way `App::frame` clocks it.

use ff_core::data::world::get_world;
use ff_core::models::jobs::{Job, CARGO_CATALOG};
use ff_core::models::profile::Profile;
use ff_core::sim::weather::WeatherKind;
use freight_fate::app::testing::TestApp;
use freight_fate::states::base::{Key, Mods, State};
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::DRIVE_PHASE_DELIVERY;

const DT: f64 = 1.0 / 60.0;
const FRAME_MS: u64 = 17; // what `begin_frame(DT)` rounds a frame to
/// The owner's JAWS log, 2026-08-24: first repeat at 512 ms, then these.
const JAWS_FIRST_REPEAT_MS: u64 = 512;
const JAWS_SPACINGS_MS: [u64; 14] = [
    263, 245, 269, 271, 242, 251, 270, 250, 244, 271, 249, 242, 254, 250,
];

/// `states_driving_controls::a_drive`: a delivery drive on a real short
/// corridor, built straight rather than driven up to, on an empty road
/// under a clear sky so nothing but the pedal moves the truck.
fn a_drive(app: &mut TestApp) -> DrivingState {
    let (origin, destination) = ("Buffalo", "Rochester");
    let world = get_world();
    app.ctx.profile = Some(Profile::named_in("Held Keys", origin));
    let route = world
        .supported_route(origin, destination, None)
        .expect("the world routes")
        .expect("the corridor is supported");
    let mut job = Job::new(
        &CARGO_CATALOG["general"],
        12.0,
        origin,
        "company yard",
        destination,
        route.miles(),
        1000.0,
        12.0,
    );
    job.destination_location = format!("{destination} freight market");
    let mut drive = DrivingState::new(&mut app.ctx, job, route, None, DRIVE_PHASE_DELIVERY, None);
    drive.trip.set_npc_vehicles(Vec::new());
    drive.trip.weather.current = WeatherKind::Clear;
    drive.trip.truck.set_air_ready(false);
    drive.trip.truck.engine_on = true;
    drive.trip.position_mi = drive.trip.total_miles() / 2.0;
    drive
}

/// When JAWS re-sends the pairs for a key held `seconds`, in ms from now.
fn jaws_pair_times(seconds: f64) -> Vec<u64> {
    let end = (seconds * 1000.0) as u64;
    let mut times = vec![0, JAWS_FIRST_REPEAT_MS];
    let mut i = 0;
    while *times.last().unwrap() < end {
        times.push(times.last().unwrap() + JAWS_SPACINGS_MS[i % JAWS_SPACINGS_MS.len()]);
        i += 1;
    }
    times.retain(|&t| t < end);
    times
}

#[test]
fn test_driving_reads_a_jaws_held_accelerator_as_steady_throttle() {
    let mut app = TestApp::new();
    let clock = app.fake_pacer_clock();
    let mut d = a_drive(&mut app);
    assert_eq!(d.trip.truck.throttle, 0.0);

    let mut pairs = jaws_pair_times(4.0);
    let mut now_ms = 0u64;
    let mut reached_full = false;
    let mut lowest_after_full = 1.0f64;
    while now_ms < 4000 {
        // Exactly what `App::frame` does: clock the frame, then its events.
        app.ctx.input.begin_frame(DT);
        now_ms += FRAME_MS;
        if pairs.first().is_some_and(|&t| now_ms >= t) {
            pairs.remove(0);
            app.ctx.input.press(Key::Up, Mods::NONE);
            app.ctx.input.release(Key::Up, Mods::NONE);
        }
        d.update_frame(&mut app.ctx, DT);
        clock.advance(DT);
        let throttle = d.trip.truck.throttle;
        if throttle > 0.95 {
            reached_full = true;
        } else if reached_full {
            lowest_after_full = lowest_after_full.min(throttle);
        }
    }
    assert!(reached_full, "the pairs never took the throttle to full");
    assert!(
        lowest_after_full >= 0.9,
        "throttle stuttered down to {lowest_after_full:.2}"
    );

    // The finger lifts: the pairs stop, and the throttle comes off.
    for _ in 0..60 {
        app.ctx.input.begin_frame(DT);
        d.update_frame(&mut app.ctx, DT);
        clock.advance(DT);
    }
    assert_eq!(d.trip.truck.throttle, 0.0);
}

#[test]
fn test_a_tap_fed_straight_in_keeps_its_plain_meaning() {
    // The harness and the other tests press and release without a frame
    // clock; that must still read as a tap, never as a half-second hold.
    let mut app = TestApp::new();
    app.ctx.input.press(Key::Down, Mods::NONE);
    assert!(app.ctx.input.is_pressed(Key::Down));
    app.ctx.input.release(Key::Down, Mods::NONE);
    assert!(!app.ctx.input.is_pressed(Key::Down));
}

#[test]
fn test_a_new_screen_never_inherits_the_last_screens_hold() {
    // A pulse the last screen left running is not the new screen's: the
    // pause menu must not open with the accelerator still down.
    let mut app = TestApp::new();
    app.ctx.input.begin_frame(DT);
    app.ctx.input.press(Key::Up, Mods::NONE);
    app.ctx.input.release(Key::Up, Mods::NONE);
    assert!(
        app.ctx.input.is_pressed(Key::Up),
        "the pair reads as a hold"
    );

    // Opening any screen is a state push, and it drops the pulse.
    struct Blank;
    impl State for Blank {}
    app.push_state(Blank);
    assert!(!app.ctx.input.is_pressed(Key::Up));
}
