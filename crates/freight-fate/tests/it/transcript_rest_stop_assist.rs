//! Transcript-backed rest-stop selection and stopping-assist regressions
//! (port of `tests/test_rest_stop_assist.py`).
//!
//! Python's fixture patched `ctx.say` AND `ctx.say_event` into one `spoken`
//! list. Here both channels land on `ctx.speech` in submission order, which
//! is the same list one rung lower: the driving verbosity ladder and the
//! event pacer now sit above the recording. Every line asserted below is
//! either a main-channel readout (the T and X answers, the menu rows) or a
//! navigation/safety event, so no rung silences one and none of the
//! expectations move.
//!
//! `start_drive(app)` -- new career, accept the assigned dispatch, depart --
//! is [`PlaytestHarness::start_delivery`], which walks the same menus.

use ff_core::sim::hos::parking_full_probability;
use ff_core::sim::trip_models::RoadStop;
use ff_core::sim::weather::WeatherKind;
use freight_fate::playtest::harness::{PlaytestHarness, StartDelivery};
use freight_fate::states::base::{Key, Menu};
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_core::RAMP_OVERSHOOT_MI;
use freight_fate::states::driving_rest_states::RestStopState;

const DT: f64 = 1.0 / 60.0;
const MPS_PER_MPH: f64 = 1.0 / 2.23694;

fn approx(a: f64, b: f64) -> bool {
    (a - b).abs() <= 1e-6 * b.abs().max(1.0)
}

/// The `driving_app` fixture: a real career at the wheel on a quiet road.
fn driving_app() -> PlaytestHarness {
    let mut harness = PlaytestHarness::new();
    harness.start_delivery(StartDelivery::named("Rest Assist"));
    // `quiet_trip(driving)`. `start_delivery` already pushes the random
    // hazard and inspection checks past the horizon and empties the rolling
    // bubble; the congestion zones it does not touch would re-inject slow NPC
    // traffic and steal the assist's attention.
    harness.with_drive(|d, _| {
        d.trip.zones.retain(|zone| zone.aadt.is_none());
        d.weather_mut().current = WeatherKind::Clear;
        // The origin yard may carry a turn-level street chain; these feature
        // tests exercise highway machinery, so skip the departure chain.
        d.departure_checked = true;
        d.truck_mut().set_air_ready(false);
        // Parking availability is deterministic in `(trip_seed, mile, clock,
        // spaces)` and only crunches after 8 PM. Python monkeypatched
        // `hos.parking_is_full` to False; parking the clock at midday is the
        // same answer through the real rule.
        d.trip.start_hour = 12.0;
    });
    harness.clear_speech();
    harness
}

/// `sleep_stop(driving, ahead=...)`.
fn sleep_stop(harness: &mut PlaytestHarness, ahead: f64) -> RoadStop {
    let at_mi = harness.read_drive(|d| d.trip.position_mi) + ahead;
    let mut stop = RoadStop::new("Prairie View Rest Area", at_mi, "public_rest_area");
    stop.actions = ["park", "save", "break", "sleep"]
        .iter()
        .map(|a| a.to_string())
        .collect();
    stop.parking = "confirmed".to_string();
    stop.exit_label = "exit 99".to_string();
    let staged = stop.clone();
    harness.with_drive(move |d, _| d.trip.stops = vec![staged]);
    stop
}

/// Every line said so far, both channels, in order (the fixture's `spoken`).
fn spoken(harness: &PlaytestHarness) -> Vec<String> {
    harness.app.speech().lines()
}

fn last(harness: &PlaytestHarness) -> String {
    spoken(harness).last().cloned().unwrap_or_default()
}

fn press_t(harness: &mut PlaytestHarness) {
    harness.press_key(Key::T, Some('t'));
}

fn press_x(harness: &mut PlaytestHarness) {
    harness.press_key(Key::X, None);
}

fn rolling(harness: &mut PlaytestHarness, mph: f64) {
    harness.with_drive(move |d, _| d.truck_mut().velocity_mps = mph * MPS_PER_MPH);
}

/// One frame of the drive itself, with the pacer's clock kept honest.
fn drive_frame(harness: &mut PlaytestHarness) {
    harness.advance_frame_clock();
    harness.with_drive(|d, ctx| d.update_frame(ctx, DT));
}

/// One frame of whatever screen is on top (`app.state.update(1/60)`).
fn top_frame(harness: &mut PlaytestHarness) {
    harness.advance_frame_clock();
    let Some(state) = harness.app.ctx.state() else {
        return;
    };
    state.borrow_mut().update(&mut harness.app.ctx, DT);
    harness.app.ctx.run_deferred();
}

#[test]
fn test_rolling_t_plans_exact_sleep_stop_without_silently_selecting_exit() {
    let mut harness = driving_app();
    let stop = sleep_stop(&mut harness, 2.0);
    rolling(&mut harness, 40.0);

    press_t(&mut harness);

    assert!(harness.state_is::<DrivingState>());
    assert_eq!(
        harness.read_drive(|d| d.trip.planned_stop_key.clone()),
        Some(stop.key())
    );
    assert_eq!(
        harness.read_drive(|d| d.selected_stop_key.clone()),
        Some(stop.key())
    );
    assert!(harness.read_drive(|d| d.exit_stop.is_none()));
    assert!(!harness.read_drive(|d| d.exit_signal_on));
    let said = last(&harness);
    assert!(
        said.contains("Planned sleep stop selected: public rest area: Prairie View Rest Area"),
        "{said}"
    );
    assert!(said.contains("Press X to signal for this exit"), "{said}");
    assert!(!said.contains("Come to a complete stop first"), "{said}");
    assert!(harness
        .read_drive(|d| d.status_text.clone())
        .contains("Press X to signal for this exit"));

    press_t(&mut harness);
    let said = last(&harness);
    assert!(
        said.starts_with("Still selected: public rest area: Prairie View Rest Area"),
        "{said}"
    );
    assert_eq!(
        harness.read_drive(|d| d.selected_stop_key.clone()),
        Some(stop.key())
    );
}

#[test]
fn test_selected_stop_assist_does_nothing_without_t_and_x() {
    let mut harness = driving_app();
    let stop = sleep_stop(&mut harness, 0.2);
    harness.app.ctx.settings.selected_stop_assist = true;
    rolling(&mut harness, 35.0);

    for _ in 0..20 {
        drive_frame(&mut harness);
    }

    assert!(harness.state_is::<DrivingState>());
    assert!(harness.read_drive(|d| d.trip.planned_stop_key.is_none()));
    assert!(harness.read_drive(|d| d.selected_stop_key.is_none()));
    assert!(harness.read_drive(|d| d.exit_stop.is_none()));
    assert!(harness.read_drive(|d| d.ramp_stop.is_none()));
    assert!(!harness.read_drive(|d| d.selected_stop_assist_armed));
    assert!(approx(harness.read_drive(|d| d.truck().brake), 0.0));
    assert!(!spoken(&harness)
        .iter()
        .any(|line| line.contains("stopping assistance braking")));
    assert!(stop.at_mi > harness.read_drive(|d| d.trip.position_mi));
}

#[test]
fn test_x_cancel_clears_explicit_assist_but_keeps_route_plan() {
    let mut harness = driving_app();
    let stop = sleep_stop(&mut harness, 2.0);
    harness.app.ctx.settings.selected_stop_assist = true;
    rolling(&mut harness, 35.0);

    press_t(&mut harness);
    press_x(&mut harness);
    assert!(harness.read_drive(|d| d.selected_stop_assist_armed));

    press_x(&mut harness);

    assert!(!harness.read_drive(|d| d.exit_signal_on));
    assert!(harness.read_drive(|d| d.selected_stop_key.is_none()));
    assert!(!harness.read_drive(|d| d.selected_stop_assist_armed));
    assert_eq!(
        harness.read_drive(|d| d.trip.planned_stop_key.clone()),
        Some(stop.key())
    );
    let said = last(&harness);
    assert!(
        said.contains("Signal canceled. Keep following the highway."),
        "{said}"
    );
    assert!(
        said.to_lowercase().contains("planned stop remains"),
        "{said}"
    );
    assert!(
        said.to_lowercase().contains("stopping assistance disarmed"),
        "{said}"
    );

    press_t(&mut harness);
    assert_eq!(
        harness.read_drive(|d| d.selected_stop_key.clone()),
        Some(stop.key())
    );
    let said = last(&harness);
    assert!(said.contains("Press X to signal"), "{said}");
    assert!(!said.contains("Press X to cancel"), "{said}");
    press_x(&mut harness);
    assert!(harness.read_drive(|d| d.exit_signal_on));
    assert!(harness.read_drive(|d| d.selected_stop_assist_armed));
}

#[test]
fn test_selected_stop_assist_reaches_full_stop_and_sleep_menu() {
    let mut harness = driving_app();
    let stop = sleep_stop(&mut harness, 1.0);
    harness.app.ctx.settings.selected_stop_assist = true;
    harness.app.ctx.settings.lane_keeping = "full".to_string();
    // Python patched `hos.parking_is_full` to False. The rule is deterministic
    // and quiet outside the evening crunch, so the midday clock the fixture
    // sets answers the same way -- asserted, not assumed.
    let local_hour = harness.read_drive(|d| d.trip.local_hour());
    assert!(
        approx(
            parking_full_probability(local_hour, stop.parking_spaces),
            0.0
        ),
        "the lot must not be full for this case"
    );
    harness.with_drive(|d, _| {
        d.truck_mut().start_engine();
        d.truck_mut().set_air_ready(false);
        d.truck_mut().transmission.automatic = true;
        d.truck_mut().transmission.gear = 8;
        d.truck_mut().velocity_mps = 40.0 * MPS_PER_MPH;
    });

    press_t(&mut harness);
    press_x(&mut harness);
    assert!(harness.read_drive(|d| d.selected_stop_assist_armed));
    assert!(harness.read_drive(|d| d.exit_signal_on));
    assert!(spoken(&harness)
        .iter()
        .any(|line| line.contains("stopping assistance armed")));
    assert!(harness
        .read_drive(|d| d.status_text.clone())
        .contains("stopping assistance armed"));

    let at_mi = stop.at_mi;
    harness.with_drive(move |d, _| d.trip.position_mi = at_mi);
    drive_frame(&mut harness);
    assert_eq!(
        harness.read_drive(|d| d.ramp_stop.as_ref().map(|s| s.key())),
        Some(stop.key())
    );
    // Isolate the entrance stop from the independently tested light/sign flow.
    harness.with_drive(|d, _| {
        d.ramp_control = "none".to_string();
        d.ramp_terminal_done = true;
    });

    let mut opened = false;
    for _ in 0..4_000 {
        top_frame(&mut harness);
        if harness.state_is::<RestStopState>() {
            opened = true;
            break;
        }
    }
    assert!(
        opened,
        "selected-stop assistance did not open the rest menu\n{}",
        harness.transcript_text()
    );

    assert!(harness.read_drive(|d| d.truck().speed_mph()) <= 0.5);
    assert!(harness.read_drive(|d| d.truck().parking_brake));
    assert!(harness.read_drive(|d| d.selected_stop_key.is_none()));
    assert!(harness.read_drive(|d| d.trip.planned_stop_key.is_none()));
    assert!(spoken(&harness)
        .iter()
        .any(|line| line.contains("stopping assistance braking")));
    assert!(spoken(&harness)
        .iter()
        .any(|line| line.contains("Stopped at public rest area: Prairie View Rest Area")));
    assert_eq!(
        harness.with_state::<RestStopState, _>(|state, _| state.menu().title.clone()),
        "public rest area: Prairie View Rest Area"
    );
    assert_eq!(
        harness.focused_label().unwrap_or_default(),
        "Sleep 2 hours in sleeper berth"
    );
    assert!(spoken(&harness)
        .iter()
        .any(|line| line.contains("Sleep 2 hours in sleeper berth")));
    let labels = harness.menu_labels();
    for hours in [2, 3, 7, 8] {
        assert!(
            labels
                .iter()
                .any(|l| l == &format!("Sleep {hours} hours in sleeper berth")),
            "{labels:?}"
        );
    }
    assert!(labels.iter().any(|l| l == "Sleep 10 hours"), "{labels:?}");

    let lines = spoken(&harness);
    let index_of = |needle: &str| {
        lines
            .iter()
            .position(|line| line.contains(needle))
            .unwrap_or_else(|| panic!("no line contains {needle:?}\n{lines:#?}"))
    };
    let selected_i = index_of("Planned sleep stop selected");
    let armed_i = index_of("stopping assistance armed");
    let braking_i = index_of("stopping assistance braking");
    let stopped_i = index_of("Stopped at public rest area");
    let menu_i = index_of("Sleep 2 hours in sleeper berth");
    assert!(
        selected_i < armed_i && armed_i < braking_i && braking_i < stopped_i && stopped_i < menu_i,
        "{selected_i} {armed_i} {braking_i} {stopped_i} {menu_i}"
    );

    harness.key(freight_fate::playtest::harness::key_event(Key::Down, None));
    assert_eq!(
        harness.focused_label().unwrap_or_default(),
        "Sleep 3 hours in sleeper berth"
    );
    assert!(
        last(&harness).contains("Sleep 3 hours in sleeper berth"),
        "{}",
        last(&harness)
    );

    harness.key(freight_fate::playtest::harness::key_event(Key::Home, None));
    assert!(harness
        .focused_label()
        .unwrap_or_default()
        .starts_with("Loyalty program"));
    harness.key(freight_fate::playtest::harness::key_event(
        Key::Return,
        None,
    ));
    assert!(!harness.state_is::<DrivingState>());
    harness.key(freight_fate::playtest::harness::key_event(
        Key::Escape,
        None,
    ));
    assert!(harness.state_is::<RestStopState>());
    assert!(harness
        .focused_label()
        .unwrap_or_default()
        .starts_with("Loyalty program"));
    assert!(
        last(&harness).contains("Loyalty program"),
        "{}",
        last(&harness)
    );

    harness.key(freight_fate::playtest::harness::key_event(
        Key::Escape,
        None,
    ));
    assert!(harness.state_is::<DrivingState>());
    assert!(harness.read_drive(|d| d.truck().parking_brake));
}

#[test]
fn test_overshoot_clears_assist_then_stopped_t_recovers() {
    let mut harness = driving_app();
    let stop = sleep_stop(&mut harness, 1.0);
    harness.app.ctx.settings.selected_stop_assist = true;
    rolling(&mut harness, 35.0);
    press_t(&mut harness);
    press_x(&mut harness);
    assert!(harness.read_drive(|d| d.selected_stop_assist_armed));

    let staged = stop.clone();
    harness.with_drive(move |d, ctx| {
        d.ramp_stop = Some(staged);
        d.ramp_mi = Some(-RAMP_OVERSHOOT_MI - 0.1);
        d.ramp_terminal_done = true;
        d.ramp_end_said = true;
        d.ramp_arrival_grace_s = 0.0;
        d.truck_mut().velocity_mps = 10.0 * MPS_PER_MPH;
        d.update_exit(ctx, 0.0, 0.0);
    });

    assert!(harness.read_drive(|d| d.ramp_stop.is_none()));
    assert!(harness.read_drive(|d| d.selected_stop_key.is_none()));
    assert!(!harness.read_drive(|d| d.selected_stop_assist_armed));
    assert!(harness.read_drive(|d| d.trip.planned_stop_key.is_none()));
    assert!(approx(harness.read_drive(|d| d.truck().brake), 0.0));
    assert!(spoken(&harness)
        .iter()
        .any(|line| line.to_lowercase().contains("never stopped")));
    assert!(spoken(&harness)
        .iter()
        .any(|line| line.contains("Continue safely")));

    let at_mi = stop.at_mi;
    harness.with_drive(move |d, _| {
        d.trip.position_mi = at_mi + 0.7;
        d.truck_mut().velocity_mps = 0.0;
    });
    press_t(&mut harness);
    assert!(harness.state_is::<RestStopState>());
}

#[test]
fn test_rolling_t_without_sleep_stop_gives_recovery_guidance() {
    let mut harness = driving_app();
    harness.with_drive(|d, _| d.trip.stops.clear());
    rolling(&mut harness, 30.0);

    press_t(&mut harness);

    assert!(harness.state_is::<DrivingState>());
    assert!(harness.read_drive(|d| d.selected_stop_key.is_none()));
    let said = last(&harness);
    assert!(
        said.contains("No sleep-capable route stop is ahead on this route"),
        "{said}"
    );
    assert!(said.contains("driving status menu"), "{said}");
}

#[test]
fn test_unselected_stop_passes_without_braking_or_menu() {
    let mut harness = driving_app();
    let stop = sleep_stop(&mut harness, 0.01);
    harness.app.ctx.settings.selected_stop_assist = true;
    rolling(&mut harness, 35.0);

    let at_mi = stop.at_mi;
    harness.with_drive(move |d, _| d.trip.position_mi = at_mi + 0.2);
    drive_frame(&mut harness);

    assert!(harness.state_is::<DrivingState>());
    assert!(approx(harness.read_drive(|d| d.truck().brake), 0.0));
    assert!(harness.read_drive(|d| d.ramp_stop.is_none()));
    assert!(!spoken(&harness)
        .iter()
        .any(|line| line.contains("stopping assistance braking")));
}

#[test]
fn test_selected_stop_outranks_unsignaled_destination_exit() {
    let mut harness = driving_app();
    let stop = sleep_stop(&mut harness, 1.0);
    let mut destination = RoadStop::new("Warehouse", stop.at_mi + 0.1, "delivery_destination");
    destination.actions = vec!["deliver".to_string()];
    destination.parking = "confirmed".to_string();
    destination.exit_label = "exit 100".to_string();
    let staged = destination.clone();
    harness.with_drive(move |d, _| {
        d.trip.stops.push(staged.clone());
        d.exit_stop = Some(staged);
        d.truck_mut().velocity_mps = 35.0 * MPS_PER_MPH;
    });

    press_t(&mut harness);
    press_x(&mut harness);

    assert_eq!(
        harness.read_drive(|d| d.exit_stop.as_ref().map(|s| s.key())),
        Some(stop.key())
    );
    assert!(harness.read_drive(|d| d.exit_signal_on));
    let said = last(&harness);
    assert!(said.contains("Prairie View Rest Area"), "{said}");
    assert!(!said.contains("Warehouse"), "{said}");
}

#[test]
fn test_t_during_police_stop_names_the_trooper_action() {
    let mut harness = driving_app();
    sleep_stop(&mut harness, 2.0);
    harness.with_drive(|d, _| {
        d.pull_over = Some("lights".to_string());
        d.truck_mut().velocity_mps = 35.0 * MPS_PER_MPH;
    });

    press_t(&mut harness);

    assert!(harness.read_drive(|d| d.selected_stop_key.is_none()));
    let said = last(&harness);
    assert!(said.contains("Resolve the police stop"), "{said}");
    assert!(
        said.contains("Press X to signal the trooper stop"),
        "{said}"
    );
}

#[test]
fn test_t_on_selected_ramp_reports_live_assist_state() {
    let mut harness = driving_app();
    let stop = sleep_stop(&mut harness, 2.0);
    harness.app.ctx.settings.selected_stop_assist = true;
    let staged = stop.clone();
    harness.with_drive(move |d, _| {
        d.selected_stop_key = Some(staged.key());
        d.selected_stop_assist_armed = true;
        d.ramp_stop = Some(staged);
        d.ramp_mi = Some(0.4);
        d.truck_mut().velocity_mps = 20.0 * MPS_PER_MPH;
    });

    press_t(&mut harness);

    let said = last(&harness);
    assert!(said.contains("On the selected ramp"), "{said}");
    assert!(said.contains("assistance is armed"), "{said}");
    assert!(!said.contains("behind you"), "{said}");

    harness.app.ctx.settings.selected_stop_assist = false;
    press_t(&mut harness);
    let said = last(&harness);
    assert!(said.contains("assistance is off"), "{said}");
    assert!(!said.contains("will stop"), "{said}");
}

#[test]
#[ignore = "needs a controller seam: Python patched `ctx.control_hint` to return \
            gamepad labels. `GameContext::control_hint` forwards to \
            `Controller::hint(action)`, which reads the bound SDL device, and a \
            headless test has no pad to bind."]
fn test_controller_rest_planning_names_controller_exit_control() {
    // With a pad bound, planning a rest stop must name the pad's own exit
    // control -- "Press D-pad down to signal" -- and never the keyboard X.
    //
    //   driving.try_rest_stop(ctx);
    //   assert last(&harness).contains("Press D-pad down to signal");
    //   assert !last(&harness).contains("Press X");
}

#[test]
fn test_t_plans_a_sleep_stop_well_beyond_the_exit_window() {
    // Owner, Hanging Lake, 2026-08-22: T seven miles out answered "no
    // sleep-capable route stop is close enough ahead to plan", and worked a
    // minute later with nothing changed but the odometer. Planning was bounded
    // by the exit window -- the five-odd miles inside which an exit can be
    // SIGNALLED -- which has nothing to do with deciding where to sleep.
    //
    // T plans the next sleep-capable stop however far ahead it is. Inside the
    // window it says press X; beyond it, it says you will be told when the
    // exit comes up, because X does nothing out there yet.
    let mut harness = driving_app();
    let stop = sleep_stop(&mut harness, 20.0);
    assert!(harness.read_drive(|d| d.exit_window_mi()) < 20.0);
    rolling(&mut harness, 60.0);

    press_t(&mut harness);

    assert_eq!(
        harness.read_drive(|d| d.trip.planned_stop_key.clone()),
        Some(stop.key())
    );
    assert_eq!(
        harness.read_drive(|d| d.selected_stop_key.clone()),
        Some(stop.key())
    );
    let said = last(&harness);
    assert!(
        said.contains("Planned sleep stop selected: public rest area: Prairie View Rest Area"),
        "{said}"
    );
    assert!(
        said.contains("20 miles ahead") || said.contains("20.0 miles ahead"),
        "{said}"
    );
    assert!(
        said.contains("You will be told when its exit comes up; press X to signal then."),
        "{said}"
    );
    assert!(!said.contains("Press X to signal for this exit."), "{said}");
    // Nothing is armed or signalled by the plan itself.
    assert!(harness.read_drive(|d| d.exit_stop.is_none()));
    assert!(!harness.read_drive(|d| d.exit_signal_on));
}
