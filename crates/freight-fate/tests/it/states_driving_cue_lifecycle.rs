use super::*;

#[test]
fn steering_blinker_releases_when_wheel_centers_but_exit_blinker_persists() {
    for exit_ready in [false, true] {
        let mut app = TestApp::new();
        let mut d = a_steering_drive(&mut app);
        let _tape = CueAudio::install(&mut app);
        if exit_ready {
            signal_for_the_exit(&mut d);
        }
        d.lane.offset = 0.2;
        arm(&mut d, &mut app, 1.0);
        assert!(app.ctx.audio.cue_held("vehicle/turn_signal"));
        if exit_ready {
            d.exit_lane_alignment = EXIT_LANE_READY;
        } else {
            d.lane.steering = 0.0;
        }
        d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
        assert_eq!(app.ctx.audio.cue_held("vehicle/turn_signal"), exit_ready);
    }
}

// -- the steering lane cue (test_lane_position_cue.py) --------------------------------

fn a_steering_drive(app: &mut TestApp) -> DrivingState {
    let mut d = a_drive(app);
    app.ctx.settings.lane_keeping = "off".to_string(); // the lane work is the driver's
    d.trip.truck.velocity_mps = 25.0; // rolling, well over the cue's floor
    d
}

/// `_arm(driving, direction)`: hold the wheel long enough that this is a
/// move, not a correction.
fn arm(d: &mut DrivingState, app: &mut TestApp, direction: f64) {
    d.lane.steering = direction;
    d.update_steering_lane_cue(&mut app.ctx, STEER_CUE_ARM_S);
}

/// `_signal_for_the_exit(driving)`: an armed route exit, without needing a
/// real stop on this leg.
fn signal_for_the_exit(d: &mut DrivingState) {
    d.exit_stop = Some(RoadStop::new("Test Exit", 30.0, "travel_center"));
    d.exit_signal_on = true;
    d.lane.lane = 0; // ramps peel off the right lane
}

#[test]
fn test_holding_the_arrow_plays_the_blinker_panned_to_the_lane() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    d.lane.offset = 0.6; // already right of centre and still going right
    d.lane.steering = 1.0;

    d.update_steering_lane_cue(&mut app.ctx, STEER_CUE_ARM_S - 0.1);
    assert!(tape.calls().is_empty()); // a nudge of the wheel is not a move

    d.update_steering_lane_cue(&mut app.ctx, 0.2);
    let (key, _, pan) = tape.last();
    assert_eq!(key, "vehicle/turn_signal");
    assert!((pan - 0.6).abs() < 1e-9);

    // It keeps time for as long as the wheel is held, and follows the truck.
    d.lane.offset = 0.95;
    d.update_steering_lane_cue(&mut app.ctx, STEER_CUE_TOCK_S);
    let (key, _, pan) = tape.last();
    assert_eq!(key, "vehicle/turn_signal");
    assert!((pan - 0.95).abs() < 1e-9);
}

#[test]
fn test_the_tock_scales_with_the_lane_cue_loudness_setting() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    app.ctx.settings.lane_cue_loudness = "subtle".to_string();
    arm(&mut d, &mut app, 1.0);
    let (key, volume, _) = tape.last();
    assert_eq!(key, "vehicle/turn_signal");
    assert!((volume - 0.5 * 0.6).abs() < 1e-9);

    d.lane.steering = 0.0;
    tape.clear();
    d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    let (key, volume, _) = tape.last();
    assert_eq!(key, SIGNAL);
    assert!((volume - 0.45 * 0.6).abs() < 1e-9);
}

#[test]
fn test_letting_go_of_the_wheel_cancels_the_signal() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    arm(&mut d, &mut app, 1.0);
    assert_eq!(
        tape.keys().first().map(String::as_str),
        Some("vehicle/turn_signal")
    );

    tape.clear();
    d.lane.steering = 0.0; // straightened out: the move is over
    d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    // centred, quieter
    assert_eq!(tape.calls(), vec![(SIGNAL.to_string(), 0.45, 0.0)]);
    assert!(!d.steer_cue_active);

    // And it stays over: no second click, no stray tocks.
    tape.clear();
    for _ in 0..120 {
        d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    }
    assert!(tape.calls().is_empty());
}

#[test]
fn test_a_nudge_of_the_wheel_never_clicks() {
    // A drift correction is not a manoeuvre, so it gets no cue and no click.
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    d.lane.steering = -1.0;
    d.update_steering_lane_cue(&mut app.ctx, STEER_CUE_ARM_S - 0.2);
    d.lane.steering = 0.0;
    d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    assert!(tape.calls().is_empty());
}

#[test]
fn test_the_lane_change_ends_with_the_click_after_the_line_is_crossed() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    d.lane.lane = 0;
    arm(&mut d, &mut app, -1.0); // holding Left, moving toward the left lane
    d.lane.offset = -0.9;
    d.update_steering_lane_cue(&mut app.ctx, STEER_CUE_TOCK_S);
    assert!((tape.last().2 + 0.9).abs() < 1e-9); // heard sliding left

    // The tires roll the line, the lane model re-centres in the new lane,
    // and the cue follows the truck through the settle.
    d.lane.lane = 1;
    d.lane.offset = -0.9 + LANE_WIDTH;
    d.update_steering_lane_cue(&mut app.ctx, STEER_CUE_TOCK_S);
    let (key, volume, pan) = tape.last();
    assert_eq!(key, "vehicle/turn_signal");
    assert!((volume - 0.5).abs() < 1e-9);
    assert!((pan - 1.0).abs() < 1e-9);

    tape.clear();
    d.lane.steering = 0.0; // straightened up in the new lane
    d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    assert_eq!(tape.keys(), vec![SIGNAL.to_string()]);
}

#[test]
fn x_starts_blinker_instead_of_beep_and_guarded_cancel_stops_it() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    let stop = RoadStop::new("Test Exit", d.trip.position_mi + 0.5, "travel_center");
    d.trip.stops.push(stop.clone());
    d.exit_stop = Some(stop);
    d.take_exit(&mut app.ctx);
    assert!(d.exit_signal_on);
    assert!(tape.keys().contains(&"vehicle/turn_signal".to_string()));
    assert!(!tape.keys().contains(&SIGNAL.to_string()));
    d.take_exit(&mut app.ctx);
    assert!(d.exit_signal_on);
    assert!(app.ctx.audio.cue_held("vehicle/turn_signal"));
    d.take_exit(&mut app.ctx);
    assert!(!d.exit_signal_on);
    assert!(!app.ctx.audio.cue_held("vehicle/turn_signal"));
}

#[test]
fn tap_lane_change_completion_does_not_cut_off_the_exit_blinker() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    signal_for_the_exit(&mut d);
    d.update_steering_lane_cue(&mut app.ctx, 0.0);
    tape.clear();
    d.lane.lane_count = 2;
    d.lane_change_target = Some(0);
    d.lane_change_timer = 0.01;
    d.update_tap_lane_change(&mut app.ctx, 0.02);
    assert!(d.lane_change_target.is_none());
    assert!(app.ctx.audio.cue_held("vehicle/turn_signal"));
    assert!(!tape.keys().contains(&"vehicle/turn_signal".to_string()));
}

#[test]
fn exit_blinker_keeps_ticking_after_alignment_and_wheel_release() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    signal_for_the_exit(&mut d);
    d.update_steering_lane_cue(&mut app.ctx, 0.0);
    assert_eq!(tape.last(), ("vehicle/turn_signal".to_string(), 0.5, 0.6));
    for alignment in [0.4, EXIT_LANE_READY, 0.0] {
        tape.clear();
        d.exit_lane_alignment = alignment;
        d.lane.offset = -0.5;
        d.lane.steering = 0.0;
        d.update_steering_lane_cue(&mut app.ctx, STEER_CUE_TOCK_S);
        assert_eq!(tape.keys(), vec!["vehicle/turn_signal".to_string()]);
        assert_eq!(tape.last().2, 0.6);
        assert_eq!(d.steer_cue_timer, STEER_CUE_TOCK_S);
    }
}

#[test]
fn exit_blinker_works_with_assistance_locator_and_at_a_stop() {
    for mode in ["off", "partial", "full"] {
        let mut app = TestApp::new();
        let mut d = a_steering_drive(&mut app);
        let tape = CueAudio::install(&mut app);
        app.ctx.settings.lane_keeping = mode.to_string();
        d.lane_locator_on = true;
        d.trip.truck.velocity_mps = 0.0;
        signal_for_the_exit(&mut d);
        d.update_steering_lane_cue(&mut app.ctx, 0.0);
        assert_eq!(tape.keys(), vec!["vehicle/turn_signal".to_string()]);
        if mode == "off" {
            d.trip.truck.velocity_mps = 25.0;
            d.update_lane_locator_audio(&mut app.ctx, 0.9);
            assert_eq!(tape.last().0, LOCATOR);
        }
    }
}

#[test]
fn exit_blinker_stops_on_ramp_cancel_or_miss_and_resumes_after_pause() {
    for end in ["ramp", "cancel", "miss"] {
        let mut app = TestApp::new();
        let mut d = a_steering_drive(&mut app);
        let tape = CueAudio::install(&mut app);
        signal_for_the_exit(&mut d);
        d.update_steering_lane_cue(&mut app.ctx, 0.0);
        app.ctx.audio.update(0.5);
        assert!(!app.ctx.audio.cue_held("vehicle/turn_signal"));
        tape.clear();
        d.update_steering_lane_cue(&mut app.ctx, 0.0);
        assert_eq!(tape.keys(), vec!["vehicle/turn_signal".to_string()]);
        match end {
            "ramp" => {
                d.ramp_mi = Some(0.5);
                d.lane.steering = 1.0;
            }
            "cancel" => d.exit_signal_on = false,
            _ => d.exit_stop = None,
        }
        d.lane.steering = 1.0;
        d.update_steering_lane_cue(&mut app.ctx, 0.0);
        assert!(!app.ctx.audio.cue_held("vehicle/turn_signal"));
        tape.clear();
        d.update_steering_lane_cue(&mut app.ctx, STEER_CUE_TOCK_S);
        assert!(tape.calls().is_empty());
        d.lane.steering = 0.0;
        d.update_steering_lane_cue(&mut app.ctx, 0.0);
        assert!(!d.exit_blinker_active);
    }
}

#[test]
fn ordinary_steering_cue_is_suppressed_by_locator_assistance_or_low_speed() {
    for condition in ["locator", "assist", "slow"] {
        let mut app = TestApp::new();
        let mut d = a_steering_drive(&mut app);
        let tape = CueAudio::install(&mut app);
        match condition {
            "locator" => d.lane_locator_on = true,
            "assist" => app.ctx.settings.lane_keeping = "full".to_string(),
            _ => d.trip.truck.velocity_mps = 0.5,
        }
        arm(&mut d, &mut app, 1.0);
        assert!(tape.calls().is_empty());
    }
}

#[test]
fn test_the_cue_cannot_survive_the_drive_losing_the_frame() {
    // A menu over the drive lets the latch lapse, and the move ends in
    // silence -- never a signal cancelling over the pause screen.
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let tape = CueAudio::install(&mut app);
    arm(&mut d, &mut app, 1.0);
    assert!(app.ctx.audio.cue_held(STEER_CUE_HOLD));

    // A menu owns the frames now: the driving state stops updating while
    // the audio clock keeps running.
    app.ctx.audio.update(0.5);
    assert!(!app.ctx.audio.cue_held(STEER_CUE_HOLD));

    tape.clear();
    d.lane.steering = 0.0;
    d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    assert!(tape.calls().is_empty());
    assert!(!d.steer_cue_active);
}

#[test]
fn test_the_whole_manoeuvre_adds_no_speech() {
    let mut app = TestApp::new();
    let mut d = a_steering_drive(&mut app);
    let _tape = CueAudio::install(&mut app);
    signal_for_the_exit(&mut d);
    d.exit_lane_alignment = 0.3;
    app.clear_speech();
    for _ in 0..240 {
        d.lane.steering = 1.0;
        d.exit_lane_alignment = 1.0f64.min(d.exit_lane_alignment + 1.0 / 60.0);
        d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    }
    d.lane.steering = 0.0;
    d.update_steering_lane_cue(&mut app.ctx, 1.0 / 60.0);
    assert!(app.main_lines().is_empty());
    assert!(app.event_lines().is_empty());
}
