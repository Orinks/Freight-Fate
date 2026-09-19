//! The engine's lean, as the driving state chooses it: who owns the engine
//! while a turn is in play, which way the Steering guide row turns every
//! producer, when the drift half may speak, and what a fresh drive inherits
//! from the last one.
//!
//! `sim::turn_guide` pins the lean's own arithmetic. These cases are about the
//! seams around it in `driving_updates/cues.rs`, which is where the 2026-09-19
//! review found the driver being told "keep steering" for finishing a bend
//! (I3), the drift lean ignoring a warning the driver had turned off (I10), a
//! new drive starting with the last one's lean still on the engine (I7), and a
//! corner coasting out its tail keeping the next bend from leading (S5).

use std::cell::RefCell;
use std::rc::Rc;

use ff_core::data::curves::RouteCurve;
use ff_core::data::world::get_world;
use ff_core::models::jobs::{Job, CARGO_CATALOG};
use ff_core::models::profile::Profile;
use ff_core::sim::trip_models::NavigationCue;
use ff_core::sim::turn_guide::{TurnSide, LEAD_MI};
use ff_core::sim::weather::WeatherKind;

use freight_fate::app::testing::TestApp;
use freight_fate::audio::CH_LANE_GUIDE;
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::*;
use freight_fate::states::driving_turns::TURN_COMMIT_TAIL_MI;

use super::states_driving_engine_audio::{Calls, Log, TrackingAudio};

// -- rigging -------------------------------------------------------------------------

const DT: f64 = 1.0 / 60.0;

/// A Buffalo to Rochester delivery on an empty road, with the recording
/// backend on the app's audio so every pan the drive writes is on the log.
fn a_drive(app: &mut TestApp) -> (DrivingState, Log) {
    let world = get_world();
    let mut profile = Profile::named_in("Lean", "Buffalo");
    profile.tutorial_done = true;
    app.ctx.profile = Some(profile);
    let route = world
        .supported_route("Buffalo", "Rochester", None)
        .expect("the world routes")
        .expect("Buffalo to Rochester has a route");
    let job = Job::new(
        &CARGO_CATALOG["general"],
        12.0,
        "Buffalo",
        "company yard",
        "Rochester",
        route.miles(),
        1000.0,
        12.0,
    );
    let mut drive = DrivingState::new(
        &mut app.ctx,
        job,
        route,
        None,
        DRIVE_PHASE_DELIVERY,
        Some(12.0),
    );
    drive.trip.set_npc_vehicles(Vec::new());
    drive.trip.weather.current = WeatherKind::Clear;
    // The route's own bends and corners are not the subject: each case lays
    // its own road.
    drive.trip.curves.clear();
    drive.trip.navigation_cues.clear();
    drive.trip.position_mi = 30.0;
    drive.trip.truck.engine_on = true;
    drive.trip.truck.velocity_mps = 45.0 / 2.23694;
    let log: Log = Rc::new(RefCell::new(Calls::default()));
    app.ctx.audio = Box::new(TrackingAudio {
        log: Rc::clone(&log),
    });
    (drive, log)
}

/// A driver holding the lane themselves, with the warning on: the mode in
/// which every half of the lean may speak.
fn by_hand(app: &mut TestApp) {
    app.ctx.settings.lane_keeping = "off".into();
    app.ctx.settings.lane_departure_warning = true;
    app.ctx.settings.lane_guide_tone = false;
    app.ctx.settings.steering_guide_inverted = false;
}

/// A right-hand sweeper `length_mi` long starting at `start_mi`.
fn a_bend(start_mi: f64, length_mi: f64, direction: char) -> RouteCurve {
    RouteCurve {
        start_mi,
        apex_mi: start_mi + length_mi / 2.0,
        end_mi: start_mi + length_mi,
        direction,
        advisory_mph: 45,
        min_radius_ft: 800,
        deflection_deg: 40.0,
        connector: false,
    }
}

fn a_corner(at_mi: f64, direction: &str) -> NavigationCue {
    let mut cue = NavigationCue::new(
        "local:turn:1",
        "local_turn",
        at_mi,
        "Turn onto Main Street.",
        "",
    );
    cue.direction = direction.to_string();
    cue
}

/// Run the guidance director for `seconds` with the truck held where it is.
fn lean_for(app: &mut TestApp, drive: &mut DrivingState, seconds: f64) {
    for _ in 0..((seconds / DT) as i64) {
        drive.update_lane_guidance_audio(&mut app.ctx, DT);
    }
}

fn engine_pans(log: &Log) -> Vec<f64> {
    log.borrow().engine_pan.clone()
}

fn last_engine_pan(log: &Log) -> f64 {
    *engine_pans(log)
        .last()
        .expect("the engine was never panned")
}

fn clear(log: &Log) {
    log.borrow_mut().engine_pan.clear();
    log.borrow_mut().loop_pans.clear();
}

// -- who owns the engine ---------------------------------------------------------------

#[test]
fn test_a_bend_the_driver_has_steered_leaves_the_engine_centred_until_it_ends() {
    // Review I3. The engine used to carry the turn guide's pan only while it
    // was non-zero and the lane guide's otherwise -- and the lane guide leans
    // into a bend for the whole bend. So the reward for steering a bend
    // correctly was the engine snapping from centred straight back into the
    // bend: "keep steering", to the one driver who had just finished.
    let mut app = TestApp::new();
    by_hand(&mut app);
    let (mut drive, log) = a_drive(&mut app);
    drive.trip.curves = vec![a_bend(30.0, 0.4, 'R')];
    drive.trip.position_mi = 30.05;
    drive.lane.steering = 1.0; // full wheel into the right-hander
    drive.lane.offset = 0.0;

    // Hold the wheel until the guide reports the whole turn steered.
    let mut held = 0.0;
    while drive.turn_guide.steered() < 1.0 {
        drive.update_lane_guidance_audio(&mut app.ctx, DT);
        held += DT;
        assert!(held < 30.0, "the turn never counted as steered");
    }
    lean_for(&mut app, &mut drive, 1.0);
    assert_eq!(
        last_engine_pan(&log),
        0.0,
        "a steered bend must leave the engine centred"
    );

    // Ease off the wheel and roll on through the rest of the bend. Nothing
    // may move the engine off centre before the bend is behind the truck.
    clear(&log);
    drive.lane.steering = 0.0;
    for step in 1..=60 {
        drive.trip.position_mi = 30.05 + 0.34 * f64::from(step) / 60.0;
        drive.update_lane_guidance_audio(&mut app.ctx, DT);
    }
    let strays: Vec<f64> = engine_pans(&log)
        .into_iter()
        .filter(|pan| *pan != 0.0)
        .collect();
    assert!(
        strays.is_empty(),
        "the engine leaned again inside a bend already steered: {strays:?}"
    );
}

#[test]
fn test_an_exit_ramp_still_leans_the_engine_with_no_turn_in_play() {
    // The turn guide has no shape for a ramp; the lane guide's peel-right
    // lean is what covers it, and taking the fallback away for the sake of
    // I3 must not silence the one continuous cue through an exit.
    let mut app = TestApp::new();
    by_hand(&mut app);
    let (mut drive, log) = a_drive(&mut app);
    drive.ramp_mi = Some(0.4);
    lean_for(&mut app, &mut drive, 2.0);
    assert!(
        last_engine_pan(&log) > 0.2,
        "the ramp's lean never reached the engine: {}",
        last_engine_pan(&log)
    );
}

// -- one convention ----------------------------------------------------------------------

/// The engine's settled lean in each of the three producers' territory:
/// approaching a right-hander, inside it, and on an exit ramp.
fn settled_leans(inverted: bool) -> [f64; 3] {
    let mut app = TestApp::new();
    by_hand(&mut app);
    app.ctx.settings.steering_guide_inverted = inverted;
    let (mut drive, log) = a_drive(&mut app);
    drive.trip.curves = vec![a_bend(30.0, 0.4, 'R')];

    drive.trip.position_mi = 30.0 - LEAD_MI / 2.0;
    lean_for(&mut app, &mut drive, 2.0);
    let approach = last_engine_pan(&log);

    drive.trip.position_mi = 30.05;
    lean_for(&mut app, &mut drive, 2.0);
    let bend = last_engine_pan(&log);

    drive.trip.curves.clear();
    drive.ramp_mi = Some(0.4);
    lean_for(&mut app, &mut drive, 2.0);
    let ramp = last_engine_pan(&log);
    [approach, bend, ramp]
}

#[test]
fn test_the_inverted_guide_is_one_convention_across_approach_bend_and_ramp() {
    // Review I3: the Steering guide row reached only the turn guide, so an
    // inverted driver heard the bend one way round and the ramp the other,
    // on one channel. The sign is applied once now, to whatever the engine
    // carries.
    let toward = settled_leans(false);
    let away = settled_leans(true);
    for (what, (t, a)) in ["approach", "bend", "ramp"]
        .into_iter()
        .zip(toward.into_iter().zip(away))
    {
        assert!(
            t > 0.1,
            "{what}: a right-hander leans right by default; got {t}"
        );
        assert!(
            (t + a).abs() < 1e-9,
            "{what}: inverted must be the mirror of {t}; got {a}"
        );
    }
}

#[test]
fn test_the_inverted_guide_reverses_the_opt_in_tone_too() {
    // The setting did nothing at all with the tone on.
    let tone_pan = |inverted: bool| {
        let mut app = TestApp::new();
        by_hand(&mut app);
        app.ctx.settings.lane_guide_tone = true;
        app.ctx.settings.steering_guide_inverted = inverted;
        let (mut drive, log) = a_drive(&mut app);
        drive.trip.curves = vec![a_bend(30.0, 0.4, 'R')];
        drive.trip.position_mi = 30.05;
        lean_for(&mut app, &mut drive, 2.0);
        let engine = engine_pans(&log).into_iter().find(|pan| *pan != 0.0);
        assert_eq!(engine, None, "the tone leans INSTEAD of the engine");
        let pan = log
            .borrow()
            .loop_pans
            .iter()
            .filter(|(channel, _)| *channel == CH_LANE_GUIDE)
            .map(|(_, pan)| *pan)
            .next_back();
        pan.expect("the tone was never panned")
    };
    let toward = tone_pan(false);
    let away = tone_pan(true);
    assert!(
        toward > 0.1,
        "the tone leans into the right-hander: {toward}"
    );
    assert!(
        (toward + away).abs() < 1e-9,
        "{away} is not the mirror of {toward}"
    );
}

// -- turns yes, drift no ------------------------------------------------------------------

#[test]
fn test_with_the_warning_off_the_engine_leans_for_bends_but_not_for_drift() {
    // Owner ruling 2026-09-19 (review I10): a driver who switched the
    // lane-departure warning off asked not to be told about drift, and the
    // old road lean honoured that. The turn half is never gated.
    let mut app = TestApp::new();
    by_hand(&mut app);
    app.ctx.settings.lane_departure_warning = false;
    let (mut drive, log) = a_drive(&mut app);

    // Drifting well right on a straight: silence.
    drive.lane.offset = 0.8;
    lean_for(&mut app, &mut drive, 2.0);
    let drift: Vec<f64> = engine_pans(&log)
        .into_iter()
        .filter(|pan| *pan != 0.0)
        .collect();
    assert!(
        drift.is_empty(),
        "the warning is off; the engine must not lean for drift: {drift:?}"
    );

    // The same truck, centred, inside a right-hander: it leans.
    drive.lane.offset = 0.0;
    drive.trip.curves = vec![a_bend(30.0, 0.4, 'R')];
    drive.trip.position_mi = 30.05;
    lean_for(&mut app, &mut drive, 2.0);
    assert!(
        last_engine_pan(&log) > 0.3,
        "the bend must still lean with the warning off; got {}",
        last_engine_pan(&log)
    );
}

// -- what a drive inherits ---------------------------------------------------------------

#[test]
fn test_a_drive_hands_the_engine_back_centred_and_the_next_one_writes_its_first_frame() {
    // Review I7. The backend keeps the engine's pan across stops and drives,
    // and the pan was written only on change from a tracker that started at
    // 0.0 -- so a drive that ended leaning left the next one's engine panned
    // down a straight road, on the channel that means "steer this way".
    let mut app = TestApp::new();
    by_hand(&mut app);
    let (mut first, log) = a_drive(&mut app);
    first.lane.offset = 0.8;
    lean_for(&mut app, &mut first, 2.0);
    assert!(last_engine_pan(&log) < -0.1, "the first drive never leaned");

    // Leaving the drive centres the engine.
    first.exit_drive(&mut app.ctx);
    assert_eq!(
        last_engine_pan(&log),
        0.0,
        "leaving a drive must hand the engine back centred"
    );

    // And a fresh drive on a straight road writes centre on its very first
    // frame rather than assuming it, so whatever the backend was left at is
    // overwritten before the driver can hear it.
    let (mut second, log) = a_drive(&mut app);
    second.lane.offset = 0.0;
    second.update_lane_guidance_audio(&mut app.ctx, DT);
    assert_eq!(
        engine_pans(&log),
        vec![0.0],
        "a new drive's first frame must write the engine pan"
    );
}

// -- which turn leads ----------------------------------------------------------------------

#[test]
fn test_a_corner_coasting_out_its_tail_does_not_keep_the_next_bend_from_leading() {
    // Review S5. Ranking by signed distance to the start put a corner in its
    // commit tail (negative, and falling) ahead of a bend fifty yards on, so
    // the bend's lead lean never opened.
    let mut app = TestApp::new();
    by_hand(&mut app);
    let (mut drive, _log) = a_drive(&mut app);
    // A left corner most of the way through its tail...
    let corner_mi = 30.0;
    drive.trip.navigation_cues.push(a_corner(corner_mi, "left"));
    drive.trip.position_mi = corner_mi + TURN_COMMIT_TAIL_MI * 0.9;
    // ...and a right-hander a third of a lead ahead.
    drive.trip.curves = vec![a_bend(drive.trip.position_mi + LEAD_MI / 3.0, 0.4, 'R')];

    let input = drive.turn_guide_input(true);
    let shape = input.shape.expect("a turn is in play");
    assert_eq!(
        shape.side,
        TurnSide::Right,
        "the bend ahead must own the engine, not the spent corner"
    );
    assert!(
        input.to_start_mi > 0.0,
        "got the corner's distance: {input:?}"
    );
}

#[test]
fn test_a_bend_still_being_taken_keeps_the_engine_from_the_bend_after_it() {
    // The other side of the same rule: a bend with most of itself still to
    // come is louder by road than the one only just inside its lead.
    let mut app = TestApp::new();
    by_hand(&mut app);
    let (mut drive, _log) = a_drive(&mut app);
    drive.trip.curves = vec![a_bend(30.0, 0.4, 'L'), a_bend(30.4, 0.4, 'R')];
    drive.trip.position_mi = 30.3; // three quarters through the left-hander
    let input = drive.turn_guide_input(true);
    assert_eq!(input.shape.map(|s| s.side), Some(TurnSide::Left));

    // Near its end, the right-hander -- now most of the way into its lead --
    // takes over, with its OWN identity, so the guide starts it from a full
    // lean rather than the left-hander's progress.
    drive.trip.position_mi = 30.39;
    let handed = drive.turn_guide_input(true);
    assert_eq!(handed.shape.map(|s| s.side), Some(TurnSide::Right));
    assert_ne!(handed.turn_id, input.turn_id);
}
