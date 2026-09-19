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
use ff_core::sim::turn_guide::{TurnShape, TurnSide, LEAD_MI, MIN_TURN_LEAN};
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

/// How deep a bend's lean opens, so the thresholds below can say "most of what
/// this bend is worth" rather than a flat number. An eight-hundred-foot bend
/// is a mild one and leans like one since the depth started coming off the
/// road (2026-09-19); the cases here are about WHICH WAY and WHO OWNS the
/// engine, so they ask for the bend's own depth and not a fixed lean.
fn bend_depth(curve: &RouteCurve) -> f64 {
    TurnShape {
        side: TurnSide::parse(&curve.direction.to_string()).expect("a bend has a side"),
        deflection_deg: curve.deflection_deg,
        radius_ft: curve.min_radius_ft as f64,
    }
    .lean_depth()
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
    // Half a lead out the approach has opened half the bend's depth; an eighth
    // of the way in, most of it. The ramp's lean is the lane guide's and is
    // not scaled by any turn's shape.
    let depth = bend_depth(&a_bend(30.0, 0.4, 'R'));
    let floors = [depth * 0.4, depth * 0.8, 0.1];
    for (what, (floor, (t, a))) in ["approach", "bend", "ramp"]
        .into_iter()
        .zip(floors.into_iter().zip(toward.into_iter().zip(away)))
    {
        assert!(
            t > floor,
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
    let bend = a_bend(30.0, 0.4, 'R');
    drive.trip.curves = vec![bend];
    drive.trip.position_mi = 30.05;
    lean_for(&mut app, &mut drive, 2.0);
    assert!(
        last_engine_pan(&log) > bend_depth(&bend) * 0.8,
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

// -- a road that never stops bending ------------------------------------------------------

/// The drive the owner reported, on the real map: AZ-260 from Camp Verde to
/// Payson at thirty-seven miles an hour, nobody touching the wheel, and the
/// assists a fresh install ships with.
///
/// The route's own bends are the whole subject here, so unlike [`a_drive`]
/// nothing is cleared: what this pins is what fifty-eight miles of baked
/// mountain highway do to the lean.
fn on_az260(app: &mut TestApp, start_mi: f64) -> (DrivingState, Log) {
    app.ctx.settings.lane_keeping = "partial".into();
    app.ctx.settings.lane_departure_warning = true;
    app.ctx.settings.curve_speed_assist = true;
    app.ctx.settings.lane_guide_tone = false;
    app.ctx.settings.steering_guide_inverted = false;

    let world = get_world();
    let mut profile = Profile::named_in("Lean", "Camp Verde");
    profile.tutorial_done = true;
    app.ctx.profile = Some(profile);
    let route = world
        .supported_route("Camp Verde", "Payson", None)
        .expect("the world routes")
        .expect("Camp Verde to Payson has a route");
    let job = Job::new(
        &CARGO_CATALOG["general"],
        12.0,
        "Camp Verde",
        "company yard",
        "Payson",
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
    drive.trip.position_mi = start_mi;
    drive.trip.truck.engine_on = true;
    let log: Log = Rc::new(RefCell::new(Calls::default()));
    app.ctx.audio = Box::new(TrackingAudio {
        log: Rc::clone(&log),
    });
    (drive, log)
}

/// Roll `seconds` of real time down the road with the wheel untouched, and
/// hand back the engine's pan on every frame.
///
/// Miles come off the clock the way `Trip::update` spends them -- velocity
/// times `dt` times `effective_time_scale` -- because the compression is part
/// of what the driver hears. The map arrives eight times faster than the lean
/// slews, so a chain of bends a quarter of a mile apart reaches the ears as a
/// wobble a couple of seconds wide.
fn roll(app: &mut TestApp, drive: &mut DrivingState, log: &Log, seconds: f64) -> Vec<f64> {
    let mut pans = Vec::new();
    let mut applied = 0.0;
    for _ in 0..((seconds / DT) as i64) {
        drive.trip.truck.velocity_mps = 37.0 / 2.23694;
        let scale = drive.trip.effective_time_scale();
        drive.trip.position_mi += drive.trip.truck.velocity_mps * DT * scale / 1609.344;
        drive.update_lane(&mut app.ctx, DT);
        clear(log);
        drive.update_lane_guidance_audio(&mut app.ctx, DT);
        applied = engine_pans(log).last().copied().unwrap_or(applied);
        pans.push(applied);
    }
    pans
}

#[test]
fn test_a_corridor_of_sweepers_leaves_the_engine_at_rest() {
    // Agent drive, AZ-260, 2026-09-19: with no steering input at all the lean
    // swung hard left, hard right, hard left and never once settled, while the
    // road bed -- which reports where the truck actually sits -- stayed put.
    // The truck was fine; the instrument was not. Mile 25 to 27 is nine baked
    // bends, every one of them posted at or above the speed of the road, and
    // the guide opened its full lean for each in turn because the lean's depth
    // did not depend on how much wheel the bend asked for.
    let mut app = TestApp::new();
    let (mut drive, log) = on_az260(&mut app, 25.0);
    let pans = roll(&mut app, &mut drive, &log, 20.0);

    let worst = pans.iter().fold(0.0f64, |held, pan| held.max(pan.abs()));
    assert!(
        worst < 0.1,
        "twenty seconds of sweepers leaned the engine to {worst}"
    );
    // And the truck really was holding its lane, so nothing here was the
    // drift half honestly reporting a wandering truck.
    assert!(
        drive.lane.offset.abs() < 0.1,
        "the truck left its lane; this case proves nothing: {}",
        drive.lane.offset
    );
}

#[test]
fn test_a_bend_the_road_warns_about_still_takes_the_engine_and_gives_it_back() {
    // The other side of the gate, on the same road. Mile 31.7 is a
    // ninety-two-degree, 475-foot right-hander posted well under the corridor:
    // a bend any state would sign, and the one kind the lean exists for. It
    // has to lead, open to its full depth, and then hand the engine back --
    // because a lean that never returns to centre is the metronome again.
    let mut app = TestApp::new();
    let (mut drive, log) = on_az260(&mut app, 31.2);
    let pans = roll(&mut app, &mut drive, &log, 12.0);

    // A 475-foot bend is worth about twice the floor a barely-signed sweeper
    // gets, which is the depth rule doing its job on real baked geometry.
    let deepest = pans.iter().fold(0.0f64, |held, pan| held.max(*pan));
    assert!(
        deepest > MIN_TURN_LEAN * 2.0,
        "the signed right-hander never opened the lean: {deepest}"
    );
    assert!(
        pans.iter().all(|pan| *pan > -0.05),
        "nothing on this stretch should have leaned left"
    );
    let tail = &pans[pans.len() - 60 * 3..];
    assert!(
        tail.iter().all(|pan| *pan == 0.0),
        "the engine never came back to centre after the bend: {:?}",
        tail.last()
    );
}
