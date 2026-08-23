//! `states/driving_events.rs`: route events, exits and ramps, the destination
//! approach, and the cruise/keeper cues.
//!
//! Ported from `tests/test_ramp_terminals.py`, `test_driving_exits.py`,
//! `test_exit_recovery.py`, `test_destination_terminal_miss.py`,
//! `test_surface_chain.py`, `test_departure_chain.py`,
//! `test_facility_overshoot.py`, `test_trip_cues.py` (the event cases),
//! `test_roadside_chatter.py`, `test_village_callouts.py` and
//! `test_pacenotes.py` -- everything in them that a real `DrivingState` can
//! answer without the per-frame loop. The cases that need
//! `states::driving_updates`, `states::driving_controls`, or one of the menu
//! states are in `states_driving_events_pending.rs`, ignored with their
//! bodies ported.

use ff_core::data::world::get_world;
use ff_core::models::jobs::make_reposition_job;
use ff_core::models::profile::Profile;
use ff_core::sim::trip_models::{
    NavigationCue, RoadStop, TrafficPressure, TripEvent, TripEventData, TripEventKind, Zone,
};
use ff_core::speech_pacing::{EventPriority, SpeechCategory};
use ff_core::speech_text::SpokenMessage;

use freight_fate::app::testing::TestApp;
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::*;
use freight_fate::states::driving_events::ambient::Ambient;
use freight_fate::states::driving_events::ramp_terminal::CrossMeeting;

// -- rigging -------------------------------------------------------------------------

/// A drive on a real corridor at `trip_seed = 0`, the transcript suite's seed.
fn a_real_drive(app: &mut TestApp) -> DrivingState {
    let world = get_world();
    let mut profile = Profile::named_in("Ramps", "Denver");
    profile.tutorial_done = true;
    app.ctx.profile = Some(profile);
    let job = make_reposition_job(world, "Denver", "Cheyenne", false, None)
        .expect("Denver to Cheyenne is a supported reposition");
    let route = world
        .shortest_route("Denver", "Cheyenne", None, false)
        .expect("the world routes")
        .expect("Denver to Cheyenne has a route");
    let mut drive = DrivingState::new(
        &mut app.ctx,
        job,
        route,
        Some(0),
        DRIVE_PHASE_DELIVERY,
        Some(12.0),
    );
    // The bubble is its own suite's business; an empty road keeps these
    // deterministic (`driving_feature_helpers.quiet_trip`).
    drive.trip.set_npc_vehicles(Vec::new());
    drive
}

fn mph_to_mps(mph: f64) -> f64 {
    mph / 2.2369362920544
}

/// `_FakeStop`: a bare route point at a milepost.
fn a_stop(at_mi: f64) -> RoadStop {
    RoadStop::new("Test Plaza", at_mi, "travel_center")
}

/// `_on_ramp`: the truck mid-ramp at the terminal bar with a known light.
fn on_ramp(drive: &mut DrivingState, control: &str, red: bool, mph: f64) {
    drive.trip.truck.start_engine();
    drive.trip.truck.velocity_mps = mph_to_mps(mph);
    drive.ramp_mi = Some(RAMP_ACCESS_MI); // right at the terminal bar
    drive.ramp_control = control.to_string();
    drive.ramp_light_offset_s = if red { 0.0 } else { RAMP_LIGHT_RED_S }; // phase start
    drive.ramp_light_timer = 0.0;
    drive.ramp_light_announced = true;
    drive.ramp_light_last_phase = if red { "red" } else { "green" }.to_string();
    drive.ramp_terminal_done = false;
    drive.ramp_waiting_at_light = false;
    drive.ramp_stop = Some(a_stop(drive.trip.position_mi + 0.5));
}

fn an_event(kind: TripEventKind, text: &str, data: TripEventData) -> TripEvent {
    TripEvent {
        kind,
        message: SpokenMessage::new(text),
        data,
    }
}

// -- ramp terminals (test_ramp_terminals.py) -----------------------------------------

#[test]
fn test_heuristic_control_is_deterministic_and_valid() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    let stop = a_stop(30.0);

    d.begin_ramp_terminal(&app.ctx, &stop);
    let first = d.ramp_control.clone();
    d.begin_ramp_terminal(&app.ctx, &stop);
    assert_eq!(d.ramp_control, first);
    assert!(matches!(first.as_str(), "signal" | "stop" | "none"));
    // A different exit may differ, but stays valid.
    d.begin_ramp_terminal(&app.ctx, &a_stop(55.0));
    assert!(matches!(
        d.ramp_control.as_str(),
        "signal" | "stop" | "none"
    ));
}

#[test]
fn test_a_scale_ramp_never_grows_a_terminal_control() {
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    let scale = RoadStop::new("Scale", 30.0, "weigh_station");
    assert_eq!(d.ramp_control_for(&app.ctx, &scale, None), "none");
}

#[test]
fn test_red_light_holds_then_green_releases() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    on_ramp(&mut d, "signal", true, 0.0);

    d.update_ramp_terminal(&mut app.ctx);
    assert!(d.ramp_waiting_at_light);
    assert!(!d.ramp_terminal_done);

    // Sit through the rest of the red; the flip releases the wait.
    for _ in 0..(RAMP_LIGHT_RED_S * 10.0) as i32 + 5 {
        d.update_ramp_light(&mut app.ctx, 0.1);
        if d.ramp_terminal_done {
            break;
        }
    }
    assert!(d.ramp_terminal_done);
    assert!(!d.ramp_waiting_at_light);
    assert_eq!(d.trip.truck.damage_pct, 0.0);
}

#[test]
fn test_running_the_red_costs_damage() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    on_ramp(&mut d, "signal", true, 30.0);
    d.ramp_mi = Some(0.05); // well past the bar, still moving
    let before = d.trip.truck.damage_pct;

    d.update_ramp_terminal(&mut app.ctx);

    assert!(d.ramp_terminal_done);
    assert!(d.trip.truck.damage_pct > before);
}

#[test]
fn test_creeping_the_red_draws_horns_not_damage() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    on_ramp(&mut d, "signal", true, 8.0);
    d.ramp_mi = Some(0.05); // past the bar at a creep

    d.update_ramp_terminal(&mut app.ctx);

    assert!(d.ramp_terminal_done);
    assert_eq!(d.trip.truck.damage_pct, 0.0);
}

#[test]
fn test_green_light_rolls_through_clean() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    on_ramp(&mut d, "signal", false, GREEN_ROLL_MPH - 5.0);

    d.update_ramp_terminal(&mut app.ctx);

    assert!(d.ramp_terminal_done);
    assert_eq!(d.trip.truck.damage_pct, 0.0);
}

#[test]
fn test_still_braking_toward_the_bar_is_not_a_violation() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    // At the check line but before the grace distance, still slowing.
    on_ramp(&mut d, "signal", true, 20.0);
    d.update_ramp_terminal(&mut app.ctx);
    assert!(!d.ramp_terminal_done);
    assert_eq!(d.trip.truck.damage_pct, 0.0);

    on_ramp(&mut d, "stop", false, 20.0);
    d.update_ramp_terminal(&mut app.ctx);
    assert!(!d.ramp_terminal_done);
}

#[test]
fn test_transition_assist_brakes_for_the_red() {
    // Regression for the 2026-07-22 playtest: positioning a rig blind inside
    // the bar's grace window was a damage-or-nothing task; the run ended with
    // cross traffic in the trailer. The assist now works the pedals.
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    app.ctx.settings.route_transition_assist = true;
    on_ramp(&mut d, "signal", true, 35.0);
    d.ramp_mi = Some(RAMP_ACCESS_MI + 0.08); // ~420 feet short of the bar
    d.trip.truck.brake = 0.0;
    d.trip.truck.throttle = 0.5;

    d.update_ramp_terminal_assist(&mut app.ctx);

    assert!(d.trip.truck.brake > 0.0);
    assert_eq!(d.trip.truck.throttle, 0.0);
}

#[test]
fn test_transition_assist_holds_the_stop_at_the_bar() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    app.ctx.settings.route_transition_assist = true;
    on_ramp(&mut d, "signal", true, 1.0);
    d.ramp_mi = Some(RAMP_ACCESS_MI + RAMP_ASSIST_HOLD_MI / 2.0);

    d.update_ramp_terminal_assist(&mut app.ctx);

    assert!(d.ramp_waiting_at_light);
    assert_eq!(d.trip.truck.brake, 1.0);
    assert!(!d.ramp_terminal_done);
    assert_eq!(d.trip.truck.damage_pct, 0.0);

    // The green flip releases the wait exactly like a manual hold.
    for _ in 0..(RAMP_LIGHT_RED_S * 10.0) as i32 + 5 {
        d.update_ramp_light(&mut app.ctx, 0.1);
        if d.ramp_terminal_done {
            break;
        }
    }
    assert!(d.ramp_terminal_done);
    assert_eq!(d.trip.truck.damage_pct, 0.0);
}

#[test]
fn test_transition_assist_completes_the_stop_sign() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    app.ctx.settings.route_transition_assist = true;
    on_ramp(&mut d, "stop", false, 1.0);
    d.ramp_mi = Some(RAMP_ACCESS_MI + RAMP_ASSIST_HOLD_MI / 2.0);
    d.cross_bubble = None; // an empty crossroad: the gap is open

    d.update_ramp_terminal_assist(&mut app.ctx);

    assert!(d.ramp_terminal_done);
    assert_eq!(d.trip.truck.damage_pct, 0.0);
}

#[test]
fn test_transition_assist_releases_a_truck_stopped_short_of_the_hold() {
    // Regression for the 2026-07-24 playtest softlock: braking manually on
    // top of the assist parked the rig about 80 feet short of the bar -- past
    // the hold window that ends the stop, inside the 30-metre band that keeps
    // the assist working the pedals. With no speed left there was nothing to
    // brake for, so the assist held throttle at zero and the brake at its
    // floor every tick and the driver could never move again.
    for control in ["stop", "signal"] {
        let mut app = TestApp::new();
        let mut d = a_real_drive(&mut app);
        app.ctx.settings.route_transition_assist = true;
        on_ramp(&mut d, control, true, 0.0);
        d.ramp_mi = Some(RAMP_ACCESS_MI + 80.0 / 5280.0); // inside the dead band
        d.trip.truck.brake = 0.0;
        d.trip.truck.throttle = 0.5;

        d.update_ramp_terminal_assist(&mut app.ctx);

        // The pedals stay the driver's: they have to drive up to the bar.
        assert_eq!(d.trip.truck.throttle, 0.5, "{control}");
        assert_eq!(d.trip.truck.brake, 0.0, "{control}");
        // Short of the bar is not a completed stop, and not a light hold.
        assert!(!d.ramp_terminal_done, "{control}");
        assert!(!d.ramp_waiting_at_light, "{control}");
    }
}

#[test]
fn test_transition_assist_caps_a_hot_green_crossing() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    app.ctx.settings.route_transition_assist = true;
    on_ramp(&mut d, "signal", false, 40.0);
    d.ramp_mi = Some(RAMP_ACCESS_MI + 0.03);
    d.trip.truck.brake = 0.0;

    d.update_ramp_terminal_assist(&mut app.ctx);

    assert!(d.trip.truck.brake > 0.0);
}

#[test]
fn test_the_light_cycles_red_green_yellow_in_real_seconds() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    on_ramp(&mut d, "signal", true, 0.0);

    assert_eq!(d.ramp_light_phase(), "red");
    d.ramp_light_timer = RAMP_LIGHT_RED_S + 0.1;
    assert_eq!(d.ramp_light_phase(), "green");
    d.ramp_light_timer = RAMP_LIGHT_RED_S + RAMP_LIGHT_GREEN_S + 0.1;
    assert_eq!(d.ramp_light_phase(), "yellow");
    // Only true red punishes a crossing.
    assert!(!d.ramp_light_is_red());
}

#[test]
fn test_the_bar_tone_lapses_the_moment_the_terminal_is_done() {
    // The solid tone is a dead man's switch: it must never outlive the bar
    // it warns about (Shane, 2026-08-03).
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    on_ramp(&mut d, "signal", true, 20.0);
    d.ramp_mi = Some(RAMP_ACCESS_MI + 0.005);
    d.update_ramp_bar_ticks(&mut app.ctx, 0.1);
    assert!(d.bar_solid_on);

    d.ramp_terminal_done = true;
    d.update_ramp_bar_ticks(&mut app.ctx, 0.1);
    assert!(!d.bar_solid_on);
}

#[test]
fn test_the_bar_milestones_stay_outside_the_tick_range() {
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    app.ctx.settings.imperial_units = true;

    let standard = d.ramp_bar_milestones(&app.ctx);
    assert!(!standard.is_empty());
    assert!(standard.len() <= 2);
    assert!(standard.contains(&RAMP_GAP_MILESTONES_FT[0]));
}

#[test]
fn test_quiet_keeps_the_far_call_and_the_handoff_to_the_tick() {
    // Owner, after driving it, 2026-08-21: "leave 300 in because that's when
    // the stop bar beeps come in, so the sound will do the guiding".
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    app.ctx.settings.imperial_units = true;
    app.ctx.settings.driving_speech = "quiet".to_string();

    let quiet = d.ramp_bar_milestones(&app.ctx);
    assert!(quiet.len() <= 2);
    assert_eq!(quiet[0], RAMP_GAP_MILESTONES_FT[0]);
    if quiet.len() == 2 {
        assert_eq!(quiet[1], 300);
    }
}

#[test]
fn test_a_ramp_onto_another_freeway_is_free_flow() {
    // 4,999 of the world's 18,011 exits lead to an interstate, and a stop
    // sign where an interstate meets an interstate does not exist (owner,
    // 2026-08-17).
    assert!(freeway_via_matches("I 20 WEST;I 59 SOUTH"));
    assert!(!freeway_via_matches("US 31 SOUTH;US 280"));
}

#[test]
fn test_the_cross_bubble_answers_an_empty_crossroad() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.cross_bubble = None;
    // With no bubble to consult (older saves mid-ramp) the old certainty
    // stands: the violation hits.
    let (met, vehicle) = d.cross_violation_meets();
    assert_eq!(met, CrossMeeting::Hit);
    assert!(vehicle.is_none());
    assert_eq!(DrivingState::cross_vehicle_sound(None), "traffic/car_cross");
}

// -- exits (test_driving_exits.py, test_exit_recovery.py) -----------------------------

#[test]
fn test_the_exit_window_grows_with_speed() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);

    d.trip.truck.velocity_mps = mph_to_mps(5.0);
    let slow = d.exit_window_mi();
    d.trip.truck.velocity_mps = mph_to_mps(74.0);
    let fast = d.exit_window_mi();

    assert!(slow >= EXIT_WINDOW_MI);
    assert!(fast >= slow);
    assert!(fast <= EXIT_WINDOW_MAX_MI);
}

#[test]
fn test_the_gore_accepts_road_speed_not_ramp_speed() {
    // A deceleration lane exists so a driver leaves at road speed and sheds
    // inside it (owner, 2026-08-21).
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    let stop = a_stop(d.trip.position_mi + 3.0);

    let accepted = d.gore_acceptance_mph(Some(&stop));
    let ramp = d.armed_ramp_mph(Some(&stop));

    assert!(accepted >= RAMP_MAX_MPH);
    assert!(accepted >= ramp);
}

#[test]
fn test_cruise_aims_a_little_under_the_ramps_own_number() {
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    let stop = a_stop(30.0);
    assert!(d.armed_ramp_cruise_mph(Some(&stop)) < d.armed_ramp_mph(Some(&stop)));
    assert!(d.armed_ramp_cruise_mph(Some(&stop)) >= RAMP_MIN_DESIGN_MPH);
}

#[test]
fn test_nothing_armed_falls_back_to_the_old_flat_ramp_speed() {
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    assert_eq!(d.armed_ramp_mph(None), RAMP_MAX_MPH);
}

#[test]
fn test_the_ramp_cap_holds_road_speed_until_there_is_road_to_shed_over() {
    // Shane, 2026-08-15: signalling nine miles out must not slow the truck.
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.cruise_mph = Some(65.0);
    d.cruise_exit_mph = Some(40.0);
    d.trip.truck.velocity_mps = mph_to_mps(65.0);
    let mut stop = a_stop(d.trip.position_mi + 9.0);
    d.exit_stop = Some(stop.clone());

    let far = d.ramp_approach_cap_mph().expect("a cap once armed");
    assert!(far > 60.0, "{far}");

    stop.at_mi = d.trip.position_mi + 0.05;
    d.exit_stop = Some(stop);
    let near = d.ramp_approach_cap_mph().expect("a cap once armed");
    assert!(near < far);
    assert!(near >= 40.0);
}

#[test]
fn test_the_ramp_cap_is_the_number_once_on_the_ramp() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.cruise_exit_mph = Some(40.0);
    d.ramp_mi = Some(0.3);
    assert_eq!(d.ramp_approach_cap_mph(), Some(40.0));
}

#[test]
fn test_the_exit_lane_is_never_ready_from_the_left_lane() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.exit_lane_alignment = 1.0;
    d.lane.lane = 1;
    d.lane_change_target = None;
    assert!(!d.exit_lane_ready());

    // A change already underway toward the right still counts.
    d.lane_change_target = Some(0);
    assert!(d.exit_lane_ready());
}

#[test]
fn test_resetting_the_exit_lane_clears_every_latch() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.exit_lane_alignment = 1.0;
    d.exit_lane_prompt_said = true;
    d.exit_lane_ready_said = true;
    d.exit_commit_said = true;
    d.exit_cancel_armed = true;
    d.exit_right_taps = 3;
    d.exit_countdown_said.push(2.0);

    d.reset_exit_lane_state();

    assert_eq!(d.exit_lane_alignment, 0.0);
    assert!(!d.exit_lane_prompt_said);
    assert!(!d.exit_lane_ready_said);
    assert!(!d.exit_commit_said);
    assert!(!d.exit_cancel_armed);
    assert_eq!(d.exit_right_taps, 0);
    assert!(d.exit_countdown_said.is_empty());
}

#[test]
fn test_x_arms_the_signal_and_a_second_press_near_the_gore_only_warns() {
    // Playtested: an X meant as "confirm" canceled the signal and cost the
    // exit, so the first press this close keeps it.
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    let stop = a_stop(d.trip.position_mi + 0.5);
    d.trip.stops.push(stop.clone());
    d.exit_stop = Some(stop);
    app.clear_speech();

    d.toggle_exit_signal(&mut app.ctx);
    assert!(d.exit_signal_on);

    d.toggle_exit_signal(&mut app.ctx);
    assert!(d.exit_signal_on, "the guard keeps the signal on");
    assert!(d.exit_cancel_armed);

    d.toggle_exit_signal(&mut app.ctx);
    assert!(!d.exit_signal_on, "a deliberate second press cancels");
    assert!(d.exit_signal_canceled);
    assert!(d.cruise_exit_mph.is_none());
}

#[test]
fn test_arming_an_exit_with_nothing_ahead_says_so() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.trip.stops.clear();
    d.destination_exit_taken = true; // no destination exit either
    app.clear_speech();

    d.toggle_exit_signal(&mut app.ctx);

    let spoken = app.main_lines().join(" ");
    assert!(
        spoken.contains("No route exit to signal for yet"),
        "{spoken}"
    );
    assert!(!d.exit_signal_on);
}

#[test]
fn test_arming_on_the_ramp_is_refused() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.ramp_mi = Some(0.4);
    app.clear_speech();

    d.toggle_exit_signal(&mut app.ctx);

    let spoken = app.main_lines().join(" ");
    assert!(spoken.contains("already on the exit ramp"), "{spoken}");
}

#[test]
fn test_capping_cruise_for_a_ramp_says_when_not_just_what() {
    // Owner playtest, 2026-08-21: "will ease to 40" heard five miles out
    // reads as "I am going to 40 now".
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    let stop = a_stop(d.trip.position_mi + 5.0);
    d.cruise_mph = Some(65.0);
    d.trip.truck.velocity_mps = mph_to_mps(65.0);

    let text = d.cap_cruise_for_ramp(&app.ctx, Some(&stop));
    assert!(text.contains("holds road speed, then eases to"), "{text}");

    // Already at the ramp number: the plain holding line.
    d.cruise_exit_mph = None;
    d.trip.truck.velocity_mps = mph_to_mps(20.0);
    let text = d.cap_cruise_for_ramp(&app.ctx, Some(&stop));
    assert!(text.contains("holding"), "{text}");
}

#[test]
fn test_the_cap_says_nothing_twice_for_one_exit() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    let stop = a_stop(d.trip.position_mi + 5.0);
    d.cruise_mph = Some(65.0);

    assert!(!d.cap_cruise_for_ramp(&app.ctx, Some(&stop)).is_empty());
    assert!(d.cap_cruise_for_ramp(&app.ctx, Some(&stop)).is_empty());
}

#[test]
fn test_a_paused_session_remembers_the_ramp_cap_silently() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    let stop = a_stop(d.trip.position_mi + 5.0);
    d.cruise_mph = None;
    d.speed_control_armed = true;
    d.speed_control_target_mph = Some(65.0);

    let text = d.cap_cruise_for_ramp(&app.ctx, Some(&stop));

    assert_eq!(text, "");
    assert!(d.cruise_exit_mph.is_some());
}

// -- the destination exit (test_driving_exits.py, test_exit_recovery.py) --------------

#[test]
fn test_the_destination_exit_key_names_the_mile_label_and_facility() {
    let mut stop = RoadStop::new("Acme Freight", 123.456_7, "delivery_destination");
    stop.exit_label = "exit 7".to_string();
    assert_eq!(
        DrivingState::destination_exit_key(&stop),
        "123.457:exit 7:Acme Freight"
    );
}

#[test]
fn test_the_destination_exit_sits_a_local_approach_short_of_route_end() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.trip.position_mi = 0.0;

    let stop = d
        .destination_exit_stop(&mut app.ctx)
        .expect("a delivery always has a destination exit");

    assert_eq!(stop.stop_type, "delivery_destination");
    assert!(stop.at_mi > 0.0);
    assert!(stop.at_mi <= d.trip.total_miles());
}

#[test]
fn test_no_destination_exit_once_it_is_taken() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.destination_exit_taken = true;
    assert!(d.destination_exit_stop(&mut app.ctx).is_none());
}

#[test]
fn test_no_destination_exit_while_the_departure_chain_runs() {
    // Still on the origin's streets: the end of the active trip is the
    // on-ramp merge, not the delivery exit.
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.departure_chain = true;
    assert!(d.destination_exit_stop(&mut app.ctx).is_none());
}

#[test]
fn test_the_destination_announcement_names_the_automation_once() {
    // Sarah A, 2026-08-15: lane keeping taking the exit must not read as the
    // exit taking itself.
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    app.ctx.settings.lane_keeping = "full".to_string();
    assert!(app.ctx.settings.lane_is_automated());
    let stop = d
        .destination_exit_stop(&mut app.ctx)
        .expect("a delivery always has a destination exit");

    let first = d.destination_exit_announcement(&mut app.ctx, &stop, 2.0);
    assert!(
        first.contains("Lane keeping will take this exit"),
        "{first}"
    );

    let second = d.destination_exit_announcement(&mut app.ctx, &stop, 1.0);
    assert!(
        !second.contains("Lane keeping will take this exit"),
        "said once per run: {second}"
    );
}

#[test]
fn test_inside_a_mile_the_announcement_uses_short_distances() {
    // Owner playtest, 2026-08-15: "In 0 miles, the destination exit" reads as
    // already missed while there is still road to use it.
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    let stop = d
        .destination_exit_stop(&mut app.ctx)
        .expect("a delivery always has a destination exit");

    let close = d.destination_exit_announcement(&mut app.ctx, &stop, 0.3);
    assert!(!close.contains("In 0 miles"), "{close}");
}

#[test]
fn test_the_exit_intent_needs_a_signal_or_full_lane_keeping() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    let plaza = a_stop(30.0);
    let destination = RoadStop::new("Acme", 30.0, "delivery_destination");

    assert!(!d.exit_intent_ready(&app.ctx, &plaza));
    d.exit_signal_on = true;
    assert!(d.exit_intent_ready(&app.ctx, &plaza));

    d.exit_signal_on = false;
    app.ctx.settings.lane_keeping = "full".to_string();
    assert!(d.exit_intent_ready(&app.ctx, &destination));
    assert!(!d.exit_intent_ready(&app.ctx, &plaza));

    // A cancelled signal is never intent, whatever the lane setting.
    d.exit_signal_canceled = true;
    assert!(!d.exit_intent_ready(&app.ctx, &destination));
}

#[test]
fn test_a_missed_optional_exit_names_its_label() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    let mut stop = a_stop(30.0);
    stop.exit_label = "exit 12".to_string();
    assert_eq!(
        d.missed_exit_phrase(&mut app.ctx, &stop),
        "exit 12 for travel center: Test Plaza"
    );
    stop.exit_label = String::new();
    assert_eq!(
        d.missed_exit_phrase(&mut app.ctx, &stop),
        "the exit for travel center: Test Plaza"
    );
}

// -- the ambient queue (test_roadside_chatter.py) --------------------------------------

#[test]
fn test_an_ambient_line_speaks_straight_away_on_a_quiet_road() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    app.clear_speech();

    d.speak_ambient_event(
        &mut app.ctx,
        SpokenMessage::new("Crossing into Wyoming."),
        Ambient::new(),
    );

    assert!(d.pending_ambient_events.is_empty());
    assert!(app
        .event_lines()
        .iter()
        .any(|line| line.contains("Wyoming")));
    assert!(d.ambient_event_cooldown_s > 0.0);
}

#[test]
fn test_a_busy_road_queues_rather_than_dropping() {
    // On an interstate a mapped state line was lost every single time the
    // one-deep slot was overwritten.
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.ambient_event_cooldown_s = 5.0;

    d.speak_ambient_event(
        &mut app.ctx,
        SpokenMessage::new("Crossing into Wyoming."),
        Ambient::new(),
    );
    d.speak_ambient_event(
        &mut app.ctx,
        SpokenMessage::new("Two lanes each way."),
        Ambient::new(),
    );

    assert_eq!(d.pending_ambient_events.len(), 2);
}

#[test]
fn test_a_keyed_line_supersedes_the_one_already_waiting() {
    // "CB chatter in 5 miles" then "in 4": the nearer wording replaces the
    // further one instead of both being read out.
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.ambient_event_cooldown_s = 5.0;

    d.speak_ambient_event(
        &mut app.ctx,
        SpokenMessage::new("CB chatter in 5 miles."),
        Ambient::new().key(Some("cb:1".to_string())),
    );
    d.speak_ambient_event(
        &mut app.ctx,
        SpokenMessage::new("CB chatter in 4 miles."),
        Ambient::new().key(Some("cb:1".to_string())),
    );

    assert_eq!(d.pending_ambient_events.len(), 1);
    assert_eq!(
        d.pending_ambient_events[0].message,
        "CB chatter in 4 miles."
    );
}

#[test]
fn test_the_queue_drops_the_oldest_past_its_bound() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.ambient_event_cooldown_s = 5.0;

    for i in 0..8 {
        d.speak_ambient_event(
            &mut app.ctx,
            SpokenMessage::new(format!("Line {i}.")),
            Ambient::new(),
        );
    }

    assert_eq!(d.pending_ambient_events.len(), 4);
    assert_eq!(d.pending_ambient_events[0].message, "Line 4.");
}

#[test]
fn test_a_line_that_waited_too_long_is_dropped_not_performed_late() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.ambient_event_cooldown_s = 5.0;
    d.speak_ambient_event(
        &mut app.ctx,
        SpokenMessage::new("Crossing into Wyoming."),
        Ambient::new(),
    );
    app.clear_speech();

    d.ambient_event_cooldown_s = 0.0;
    d.update_ambient_events(&mut app.ctx, 13.0);

    assert!(d.pending_ambient_events.is_empty());
    assert!(app.event_lines().is_empty(), "aged out, not spoken late");
}

#[test]
fn test_a_hazard_blocks_the_drain_but_no_longer_discards_it() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.ambient_event_cooldown_s = 5.0;
    d.speak_ambient_event(
        &mut app.ctx,
        SpokenMessage::new("Crossing into Wyoming."),
        Ambient::new(),
    );
    d.hazard_deadline = Some(4.0);
    app.clear_speech();

    d.ambient_event_cooldown_s = 0.0;
    d.update_ambient_events(&mut app.ctx, 0.5);

    assert_eq!(d.pending_ambient_events.len(), 1);
    assert!(app.event_lines().is_empty());
}

#[test]
fn test_a_queued_countdown_re_renders_at_delivery() {
    // Brandon, 2026-08-20: "Pilot in 5 miles" was performed with two left.
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.ambient_event_cooldown_s = 5.0;
    d.speak_ambient_event(
        &mut app.ctx,
        SpokenMessage::new("Pilot in 5 miles."),
        Ambient::new().render(Some(std::rc::Rc::new(|_d: &DrivingState, _c: &_| {
            Some("Pilot in 2 miles.".to_string())
        }))),
    );
    app.clear_speech();

    d.ambient_event_cooldown_s = 0.0;
    d.update_ambient_events(&mut app.ctx, 0.1);

    let spoken = app.event_lines().join(" ");
    assert!(spoken.contains("Pilot in 2 miles."), "{spoken}");
}

#[test]
fn test_a_moment_that_passed_is_dropped_rather_than_spoken() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.ambient_event_cooldown_s = 5.0;
    d.speak_ambient_event(
        &mut app.ctx,
        SpokenMessage::new("Pilot in 5 miles."),
        Ambient::new().render(Some(std::rc::Rc::new(|_d: &DrivingState, _c: &_| {
            None::<String>
        }))),
    );
    app.clear_speech();

    d.ambient_event_cooldown_s = 0.0;
    d.update_ambient_events(&mut app.ctx, 0.1);

    assert!(app.event_lines().is_empty());
}

#[test]
fn test_the_weather_is_one_standing_condition() {
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    let event = an_event(
        TripEventKind::WeatherChange,
        "Rain starting.",
        TripEventData::default(),
    );
    assert_eq!(d.ambient_key(&event).as_deref(), Some("weather"));
}

#[test]
fn test_a_landmark_keeps_its_place_in_the_queue() {
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    let event = an_event(
        TripEventKind::Landmark,
        "Big Buck's.",
        TripEventData::default(),
    );
    assert!(d.ambient_key(&event).is_none());
    assert!(!d.should_space_ambient_event(&event));
}

#[test]
fn test_a_planned_stop_never_rides_the_ambient_channel() {
    // Tester Darren, 2026-08-11: the stop the player PLANNED is the drive,
    // not a notice.
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    let notice = an_event(
        TripEventKind::StopAhead,
        "Pilot in 5 miles.",
        TripEventData::default(),
    );
    assert!(d.should_space_ambient_event(&notice));

    let planned = an_event(
        TripEventKind::StopAhead,
        "Your planned stop, Pilot, in 5 miles.",
        TripEventData {
            planned: Some(true),
            ..Default::default()
        },
    );
    assert!(!d.should_space_ambient_event(&planned));
}

// -- categories and priorities (test_trip_cues.py's event cases) ----------------------

#[test]
fn test_every_event_kind_is_classified_or_deliberately_flavour() {
    for kind in [
        TripEventKind::Hazard,
        TripEventKind::Inspection,
        TripEventKind::ZoneEnter,
        TripEventKind::ZoneExit,
        TripEventKind::StopAhead,
        TripEventKind::StopReached,
        TripEventKind::Checkpoint,
        TripEventKind::GpsCue,
        TripEventKind::Arrived,
        TripEventKind::Curve,
        TripEventKind::TollCharged,
        TripEventKind::WeatherChange,
        TripEventKind::Lane,
    ] {
        let event = an_event(kind, "x", TripEventData::default());
        assert!(
            DrivingState::event_category(&event).is_some(),
            "{kind:?} has no category"
        );
    }
    for kind in freight_fate::states::driving_events::FLAVOR_EVENT_KINDS {
        let event = an_event(kind, "x", TripEventData::default());
        assert!(
            DrivingState::event_category(&event).is_none(),
            "{kind:?} answers to the chatter switches, never the rung"
        );
    }
}

#[test]
fn test_a_limit_change_cue_is_the_roads_state_not_a_turn() {
    let event = an_event(
        TripEventKind::GpsCue,
        "Speed limit raised to 55.",
        TripEventData {
            limit_change: Some(true),
            ..Default::default()
        },
    );
    assert_eq!(
        DrivingState::event_category(&event),
        Some(SpeechCategory::Status)
    );
}

#[test]
fn test_the_advance_half_of_a_cue_is_only_an_advisory() {
    let event = an_event(
        TripEventKind::GpsCue,
        "In a mile, take exit 42.",
        TripEventData {
            advance: Some(true),
            ..Default::default()
        },
    );
    assert_eq!(
        DrivingState::event_category(&event),
        Some(SpeechCategory::NavigationAdvisory)
    );
}

#[test]
fn test_the_hazard_is_the_only_critical_event_left() {
    // Speech priority research, R1: every interrupt is a chance to erase a
    // warning the player still needed.
    let hazard = an_event(TripEventKind::Hazard, "Deer!", TripEventData::default());
    assert!(DrivingState::is_critical_event(&hazard));
    for kind in [TripEventKind::ZoneEnter, TripEventKind::Checkpoint] {
        let event = an_event(kind, "x", TripEventData::default());
        assert!(!DrivingState::is_critical_event(&event));
        assert!(DrivingState::demoted_from_interrupt(&event));
    }
}

#[test]
fn test_the_act_soon_kinds_ride_routes_never_dropped_queue() {
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    for kind in [
        TripEventKind::ZoneEnter,
        TripEventKind::Checkpoint,
        TripEventKind::TollCharged,
        TripEventKind::StopAhead,
    ] {
        let event = an_event(kind, "x", TripEventData::default());
        assert_eq!(d.event_priority(&event), EventPriority::Route, "{kind:?}");
    }
}

#[test]
fn test_a_direction_cue_may_never_age_out() {
    // "Merge onto I-70 West toward Silverthorne" was dropped as stale chatter
    // on the owner's Denver playtest.
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    for cue_kind in ["onramp", "maneuver", "local_turn"] {
        let event = an_event(
            TripEventKind::GpsCue,
            "Merge onto I-70 West.",
            TripEventData {
                cue: Some(NavigationCue::new("k", cue_kind, 1.0, "t", "n")),
                ..Default::default()
            },
        );
        assert_eq!(d.event_priority(&event), EventPriority::Route, "{cue_kind}");
    }
}

#[test]
fn test_a_construction_taper_merge_is_a_lane_closure() {
    let event = an_event(
        TripEventKind::GpsCue,
        "Right lane closed ahead.",
        TripEventData {
            traffic_pressure: Some(TrafficPressure {
                start_mi: 1.0,
                end_mi: 2.0,
                kind: "construction_merge".to_string(),
                direction: "right".to_string(),
                intensity: 0.5,
                target_speed_mph: 45.0,
                reason: "construction".to_string(),
            }),
            ..Default::default()
        },
    );
    assert!(DrivingState::is_lane_closure_pressure(&event));
    assert!(DrivingState::demoted_from_interrupt(&event));
}

#[test]
fn test_the_gate_zone_heads_up_is_dropped_before_the_exit_is_taken() {
    // Playtest transcript, 2026-07-20: the driver slowed for a sign that
    // never came.
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    for reason in [
        "destination approach",
        "facility access road",
        "facility gate",
    ] {
        let event = an_event(
            TripEventKind::GpsCue,
            "Speed limit 15 ahead.",
            TripEventData {
                zone: Some(Zone::new(1.0, 2.0, 15.0, reason)),
                ..Default::default()
            },
        );
        assert!(
            d.should_ignore_untaken_destination_facility_event(&event),
            "{reason}"
        );
    }
}

#[test]
fn test_exit_traffic_is_news_only_to_a_driver_taking_that_exit() {
    // Owner, 2026-08-15: a corridor thick with truck stops narrated the
    // traffic at exit after exit the driver had no intention of using.
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    let event = an_event(
        TripEventKind::GpsCue,
        "Traffic crowding the exit lane.",
        TripEventData {
            traffic_pressure: Some(TrafficPressure {
                start_mi: 10.0,
                end_mi: 12.0,
                kind: "exit".to_string(),
                direction: "right".to_string(),
                intensity: 0.5,
                target_speed_mph: 45.0,
                reason: "exit".to_string(),
            }),
            ..Default::default()
        },
    );
    assert!(d.should_ignore_unsignalled_exit_pressure(&app.ctx, &event));

    let mut stop = a_stop(11.0);
    stop.exit_label = "exit 11".to_string();
    d.exit_stop = Some(stop);
    d.exit_signal_on = true;
    assert!(!d.should_ignore_unsignalled_exit_pressure(&app.ctx, &event));
}

// -- cruise and the keeper (test_driving_exits.py's cruise cases) ---------------------

#[test]
fn test_the_dial_answers_with_the_figure_alone_at_quiet() {
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    app.ctx.settings.imperial_units = true;
    assert_eq!(d.speed_number(&app.ctx, 62.0), "62");
}

#[test]
fn test_engaging_cruise_rounds_to_the_number_the_player_hears() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.trip.truck.start_engine();
    d.trip.truck.velocity_mps = mph_to_mps(59.95);

    d.engage_cruise(&mut app.ctx, 59.95, false);

    assert_eq!(d.cruise_mph, Some(60.0));
    assert_eq!(d.speed_control_target_mph, Some(60.0));
    assert!(d.speed_control_armed);
    // The working setpoint starts at road speed, so a resume eases on.
    assert!(d.cruise_working_mph.unwrap() <= 60.0);
}

#[test]
fn test_cruise_clamps_to_its_own_bounds() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.trip.truck.start_engine();

    d.engage_cruise(&mut app.ctx, 200.0, false);
    assert_eq!(d.cruise_mph, Some(CRUISE_MAX_MPH));

    d.engage_cruise(&mut app.ctx, 1.0, false);
    assert_eq!(d.cruise_mph, Some(CRUISE_MIN_MPH));
}

#[test]
fn test_the_accel_coast_buttons_walk_the_fives_grid() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.trip.truck.start_engine();
    d.engage_cruise(&mut app.ctx, 62.0, false);
    app.clear_speech();

    d.adjust_cruise(&mut app.ctx, 1, false);
    assert_eq!(d.cruise_mph, Some(65.0));
    d.adjust_cruise(&mut app.ctx, -1, true);
    assert_eq!(d.cruise_mph, Some(64.0));
}

#[test]
fn test_the_dial_with_cruise_off_says_where_the_switch_is() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    app.clear_speech();

    d.adjust_cruise(&mut app.ctx, 1, false);

    let spoken = app.main_lines().join(" ");
    assert!(spoken.contains("Adaptive cruise is off"), "{spoken}");
}

#[test]
fn test_the_keeper_refuses_politely_when_it_is_switched_off() {
    // Shane, 2026-08-15: naming the way out matters more than the refusal.
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    app.ctx.settings.speed_keeper = false;
    app.clear_speech();

    d.engage_keeper(&mut app.ctx, 25.0, "construction", None, true);

    let spoken = app.main_lines().join(" ");
    assert!(
        spoken.contains("The speed keeper holds your speed here"),
        "{spoken}"
    );
    assert!(d.keeper_mph.is_none());
}

#[test]
fn test_the_keeper_caps_at_the_zones_limit() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    app.ctx.settings.speed_keeper = true;
    d.trip.truck.start_engine();
    d.trip.truck.velocity_mps = mph_to_mps(40.0);

    d.engage_keeper(&mut app.ctx, 25.0, "construction", None, true);

    assert_eq!(d.keeper_mph, Some(25.0));
    assert_eq!(d.keeper_zone, "construction");
    assert!(d.speed_control_armed);
}

#[test]
fn test_a_new_posted_number_hands_the_keeper_back_up_to_street_speed() {
    // A session started on a service way held that crawl over every named
    // street after it (tester report, access roads, 2026-08).
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    app.ctx.settings.speed_keeper = true;
    d.trip.truck.start_engine();
    d.trip.truck.velocity_mps = mph_to_mps(15.0);
    d.engage_keeper(&mut app.ctx, 15.0, "facility access road", None, false);
    assert_eq!(d.keeper_mph, Some(15.0));

    d.take_new_posted_limit(&mut app.ctx, 25.0, "facility access road");

    assert_eq!(d.keeper_mph, Some(25.0));
}

#[test]
fn test_the_keeper_never_takes_a_lower_number_from_a_new_street() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    app.ctx.settings.speed_keeper = true;
    d.trip.truck.start_engine();
    d.trip.truck.velocity_mps = mph_to_mps(25.0);
    d.engage_keeper(&mut app.ctx, 25.0, "facility access road", None, false);

    d.take_new_posted_limit(&mut app.ctx, 15.0, "facility access road");

    assert_eq!(d.keeper_mph, Some(25.0), "coming down is the cap's job");
}

#[test]
fn test_the_keeper_snubs_the_drums_rather_than_dragging_them() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.trip.truck.start_engine();
    d.trip.truck.brake = 0.0;

    // Well over the number: the snub goes on.
    d.keeper_snub_brakes(&mut app.ctx, 1.0 / 60.0, 4.0, 25.0);
    assert!(d.keeper_snub > 0.0);
    let held = d.keeper_snub;

    // Still over: only ever firmer, never eased and re-pressed.
    d.keeper_snub_brakes(&mut app.ctx, 1.0 / 60.0, 2.0, 25.0);
    assert!(d.keeper_snub >= held);

    // Back under the number: let it go.
    d.keeper_snub_brakes(&mut app.ctx, 1.0 / 60.0, -2.0, 25.0);
    assert_eq!(d.keeper_snub, 0.0);
}

#[test]
fn test_the_keeper_owns_up_when_it_cannot_hold_the_number() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.trip.truck.start_engine();
    d.trip.truck.grade = -0.2; // steep enough that a full snub still loses
    app.clear_speech();

    for _ in 0..(KEEPER_OVERRUN_TICKS) {
        d.keeper_snub_brakes(&mut app.ctx, 1.0, 6.0, 25.0);
    }

    assert!(d.keeper_overrun_said);
    let spoken = app.event_lines().join(" ");
    assert!(spoken.contains("Speed keeper cannot hold"), "{spoken}");
    assert!(spoken.contains("on this grade"), "{spoken}");
}

const KEEPER_OVERRUN_TICKS: i32 = 6;

#[test]
fn test_the_following_gap_only_ever_opens_for_weather() {
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    let chosen = acc_gap_seconds(&app.ctx.settings.acc_following_gap)
        .expect("the default gap is a real choice");
    assert!(d.acc_gap_seconds(&app.ctx) >= chosen);
    assert!(d.acc_gap_seconds(&app.ctx) <= 6.0);
}

#[test]
fn test_the_limit_lookahead_grows_with_the_speed_to_shed() {
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    let short = d.acc_limit_lookahead_mi(30.0, 25.0);
    let long = d.acc_limit_lookahead_mi(70.0, 25.0);
    assert!(long > short);
    assert!(long <= ACC_LIMIT_LOOKAHEAD_MAX_MI);
    // Nothing to shed: the floor.
    assert_eq!(
        d.acc_limit_lookahead_mi(30.0, 45.0),
        ACC_LIMIT_LOOKAHEAD_MIN_MI
    );
}

#[test]
fn test_descent_control_holds_the_set_speed_under_the_safe_ceiling() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.cruise_mph = Some(65.0);
    assert_eq!(d.descent_hold_mph(), 65.0);
    d.cruise_descent_mph = Some(DESCENT_SAFE_MAX_MPH);
    assert_eq!(d.descent_hold_mph(), DESCENT_SAFE_MAX_MPH);
}

#[test]
fn test_the_grade_preview_reads_the_road_ahead() {
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    let samples = d.grade_samples(PCC_PREVIEW_MI);
    assert!(!samples.is_empty());
    let (climb, descent) = d.grade_extremes_ahead();
    assert!(climb >= descent);
}

// -- the surface and departure chains (test_surface_chain.py, test_departure_chain.py)

#[test]
fn test_the_city_answers_for_a_street_chains_vehicle_code() {
    let mut app = TestApp::new();
    let d = a_real_drive(&mut app);
    assert!(!d.city_state(&app.ctx, "Denver").is_empty());
    assert_eq!(d.city_state(&app.ctx, "not-a-city"), "");
}

#[test]
fn test_a_chain_answer_is_memoised_for_the_job() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    let first = d.destination_street_chain_ahead(&app.ctx);
    assert_eq!(d.destination_chain_ahead, Some(first));
    assert_eq!(d.destination_street_chain_ahead(&app.ctx), first);
}

#[test]
fn test_a_surface_chain_never_starts_twice() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.surface_chain = true;
    assert!(!d.begin_surface_chain(&mut app.ctx, false));
}

#[test]
fn test_a_departure_chain_never_runs_on_a_pickup_deadhead() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.phase = DRIVE_PHASE_PICKUP;
    assert!(d.departure_chain_route(&app.ctx).is_none());
    assert!(!d.begin_departure_chain(&mut app.ctx, false));
}

#[test]
fn test_the_acceleration_lane_closes_with_a_merge_line() {
    // Brandon, 2026-08-21: a loaded truck under the limit has not failed at
    // anything, so the line names the gap you need.
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.departure_ramp_mi = Some(0.05);
    d.trip.truck.start_engine();
    d.trip.truck.velocity_mps = mph_to_mps(20.0);
    app.clear_speech();

    d.update_departure_ramp(&mut app.ctx, 0.10);

    assert!(d.departure_ramp_mi.is_none());
    let spoken = app.event_lines().join(" ");
    assert!(spoken.contains("Lane ending"), "{spoken}");
    assert!(spoken.contains("take a big gap"), "{spoken}");
}

#[test]
fn test_a_truck_up_to_speed_gets_the_plain_merge_line() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.departure_ramp_mi = Some(0.05);
    d.trip.truck.start_engine();
    let position = d.trip.position_mi;
    let (limit, _) = d.trip.speed_limit_at(position);
    d.trip.truck.velocity_mps = mph_to_mps(limit);
    app.clear_speech();

    d.update_departure_ramp(&mut app.ctx, 0.10);

    let spoken = app.event_lines().join(" ");
    assert!(
        spoken.contains("Lane ending. Merge left when clear."),
        "{spoken}"
    );
}

// -- arrival and the gate (test_facility_overshoot.py) --------------------------------

#[test]
fn test_the_gate_query_answers_only_at_a_finished_trip() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    assert!(d.arrival_gate_query_text(&app.ctx).is_none());

    d.trip.finished = true;
    d.destination_exit_taken = true;
    let text = d
        .arrival_gate_query_text(&app.ctx)
        .expect("a finished delivery is at its gate");
    assert!(text.contains("Stop to dock"), "{text}");

    // The dock menu already open answers nothing.
    d.arrival_menu_open = true;
    assert!(d.arrival_gate_query_text(&app.ctx).is_none());
}

#[test]
fn test_the_creep_line_names_the_place_once() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    app.clear_speech();

    d.handle_arrival_creep(&mut app.ctx);
    assert!(d.arrival_full_stop_said);
    let first = app.event_lines().len();

    app.clear_speech();
    d.handle_arrival_creep(&mut app.ctx);
    assert!(app.event_lines().is_empty(), "said once ({first} before)");
}

#[test]
fn test_running_out_of_fuel_brings_a_bill_and_an_instruction() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.trip.truck.fuel_gal = 0.0;
    app.clear_speech();

    d.handle_out_of_fuel(&mut app.ctx);

    let spoken = app.event_lines().join(" ");
    assert!(spoken.contains("You ran out of fuel"), "{spoken}");
    assert!(spoken.contains("plan your fuel stops"), "{spoken}");
    assert!(d.trip.truck.fuel_gal > 0.0);
}

#[test]
fn test_the_status_line_is_what_the_window_shows() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.set_status("Destination ahead.");
    let lines = d.visible_lines(&app.ctx);
    assert_eq!(lines.last().map(String::as_str), Some("Destination ahead."));
    assert!(lines[0].contains("Driving loaded to"));
    assert!(lines.iter().any(|line| line.starts_with("Speed:")));
    assert!(lines.iter().any(|line| line.starts_with("Remaining:")));
}

#[test]
fn test_the_drivers_board_line_adds_the_radio_and_discord_does_not() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    d.radio.enabled = true;
    d.radio_now_playing = Some("Usher - U Remind Me".to_string());

    let discord = d.presence_state(&app.ctx).expect("a drive has presence");
    let board = d
        .online_presence_state(&app.ctx)
        .expect("an on-duty drive is on the board");

    assert!(!discord.detail.contains("listening to"));
    assert!(board.detail.contains("listening to"), "{}", board.detail);

    d.radio.enabled = false;
    let quiet = d
        .online_presence_state(&app.ctx)
        .expect("still on the board");
    assert!(!quiet.detail.contains("listening to"));
}

#[test]
fn test_the_objective_names_the_phase() {
    let mut app = TestApp::new();
    let mut d = a_real_drive(&mut app);
    assert!(d.objective_text(&app.ctx).starts_with("deliver to "));
    d.phase = DRIVE_PHASE_PICKUP;
    assert!(d.objective_text(&app.ctx).starts_with("pickup at "));
}
