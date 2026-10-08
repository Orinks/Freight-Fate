//! The iPhone and iPad driving gestures (`bindings/touch.rs`,
//! `states/driving_controls/touch.rs`): a gesture at the wheel runs its
//! command directly, the same way the command's key does, and every other
//! screen still gets the key the gesture stands for.

use ff_core::sim::weather::WeatherKind;

use freight_fate::bindings::{Action, Chord, TouchCommand};
use freight_fate::playtest::harness::{PlaytestHarness, StartDelivery};
use freight_fate::states::base::{InputEvent, Key, Mods};
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_menu_states::DrivingCommandsState;
use freight_fate::states::driving_pause_states::PauseMenuState;
use freight_fate::states::main_menu::{
    TouchCommandPickerState, TouchGesturesState, TouchPracticeState,
};
use freight_fate::touch::{Gesture, TouchInput};

const MPH_PER_MPS: f64 = 2.236_936_292_054_402;

fn a_drive(name: &str) -> PlaytestHarness {
    let mut harness = PlaytestHarness::new();
    harness.start_delivery(StartDelivery::named(name));
    harness.with_drive(|drive, _| {
        drive.tutorial = None;
        drive.departure_checked = true;
        drive.trip.hazard_check_mi = 1e9;
        drive.trip.inspection_check_mi = 1e9;
        drive.trip.traffic_manager.rolling_bubble = false;
        drive.trip.set_npc_vehicles(Vec::new());
        drive.trip.traffic_pressures.clear();
        drive.trip.weather.current = WeatherKind::Clear;
    });
    harness.clear_speech();
    harness
}

fn rolling(harness: &mut PlaytestHarness, mph: f64) {
    harness.with_drive(|drive, _| {
        drive.trip.truck.start_engine();
        drive.trip.truck.parking_brake = false;
        drive.trip.truck.velocity_mps = mph / MPH_PER_MPS;
    });
    harness.clear_speech();
}

/// Feed native gestures through the same translator the iOS shell uses.
fn touch(harness: &mut PlaytestHarness, input: &mut TouchInput, gesture: Gesture) {
    for event in input.handle(gesture).events {
        harness.app.handle_event(&event);
    }
}

fn speed_control_on(harness: &mut PlaytestHarness) -> bool {
    harness.with_drive(|drive, _| drive.speed_authority_engaged() || drive.speed_control_armed)
}

/// What pressing `action`'s default key says, and what `read` finds after,
/// on a fresh drive set up by `setup`. Run it before the gesture's harness:
/// a thread holds one game at a time.
fn by_key<R>(
    name: &str,
    setup: impl Fn(&mut PlaytestHarness),
    action: Action,
    read: impl FnOnce(&mut PlaytestHarness) -> R,
) -> (Vec<String>, R) {
    let mut harness = a_drive(name);
    setup(&mut harness);
    let chord = action.default_chords()[0];
    harness.key(InputEvent::KeyDown {
        key: chord.key,
        mods: chord.mods,
        text: None,
        repeat: false,
    });
    let found = read(&mut harness);
    (harness.transcript(), found)
}

#[test]
fn hold_gas_then_tap_a_second_finger_sets_cruise_with_the_pedal_down() {
    let (expected, _) = by_key(
        "Touch Cruise Key",
        |h| rolling(h, 24.0),
        Action::Cruise,
        |_| (),
    );
    let mut harness = a_drive("Touch Cruise");
    rolling(&mut harness, 24.0);
    let mut input = TouchInput::new();
    touch(&mut harness, &mut input, Gesture::HoldUpperBegan);
    assert!(harness.app.ctx.input.physically_down(Key::Up));

    touch(&mut harness, &mut input, Gesture::UpperHoldTap);
    assert!(harness.state_is::<DrivingState>(), "no menu in between");
    assert!(
        speed_control_on(&mut harness),
        "{:#?}",
        harness.transcript()
    );
    assert!(
        harness.app.ctx.input.physically_down(Key::Up),
        "the tap must not lift the pedal"
    );
    assert_eq!(harness.transcript(), expected);

    touch(&mut harness, &mut input, Gesture::HoldEnded);
    assert!(!harness.app.ctx.input.physically_down(Key::Up));
}

#[test]
fn the_cruise_tap_below_the_minimum_answers_as_the_key_does() {
    let (expected, engaged) = by_key(
        "Touch Cruise Slow Key",
        |h| rolling(h, 8.0),
        Action::Cruise,
        speed_control_on,
    );
    let mut harness = a_drive("Touch Cruise Slow");
    rolling(&mut harness, 8.0);
    let mut input = TouchInput::new();
    touch(&mut harness, &mut input, Gesture::HoldUpperBegan);
    touch(&mut harness, &mut input, Gesture::UpperHoldTap);
    assert_eq!(harness.transcript(), expected);
    assert_eq!(speed_control_on(&mut harness), engaged);
}

#[test]
fn a_second_finger_on_the_brake_runs_the_parking_brake_and_the_engine() {
    let parked = |h: &mut PlaytestHarness| {
        h.with_drive(|drive, _| {
            drive.trip.truck.velocity_mps = 0.0;
        });
        h.clear_speech();
    };
    let (expected, engine_by_key) = by_key("Touch Engine Key", parked, Action::Engine, |h| {
        h.with_drive(|d, _| d.trip.truck.engine_on)
    });
    let mut harness = a_drive("Touch Engine");
    parked(&mut harness);
    let mut input = TouchInput::new();
    touch(&mut harness, &mut input, Gesture::HoldLowerBegan);
    assert!(harness.app.ctx.input.physically_down(Key::Down));
    let engine_before = harness.with_drive(|d, _| d.trip.truck.engine_on);
    touch(&mut harness, &mut input, Gesture::LowerHoldDoubleTap);
    // Same answer as the key, with the parking brake named as its gesture.
    let expected: Vec<String> = expected
        .iter()
        .map(|line| {
            line.replace(
                "P releases",
                "a second-finger tap while holding brake releases",
            )
        })
        .collect();
    assert_eq!(harness.transcript(), expected);
    let engine_after = harness.with_drive(|d, _| d.trip.truck.engine_on);
    assert_eq!(engine_after, engine_by_key);
    assert_ne!(engine_before, engine_after);

    assert!(harness.app.ctx.input.physically_down(Key::Down));
    assert!(harness.state_is::<DrivingState>());
    drop(harness);

    let (expected, brake_by_key) = by_key("Touch Brake Key", parked, Action::ParkingBrake, |h| {
        h.with_drive(|d, _| d.trip.truck.parking_brake)
    });
    let mut harness = a_drive("Touch Brake");
    parked(&mut harness);
    let mut input = TouchInput::new();
    touch(&mut harness, &mut input, Gesture::HoldLowerBegan);
    touch(&mut harness, &mut input, Gesture::LowerHoldTap);
    assert_eq!(harness.transcript(), expected);
    assert_eq!(
        harness.with_drive(|d, _| d.trip.truck.parking_brake),
        brake_by_key
    );
    assert!(harness.app.ctx.input.physically_down(Key::Down));
}

#[test]
fn magic_tap_pauses_the_drive() {
    let mut harness = a_drive("Touch Pause");
    let mut input = TouchInput::new();
    touch(&mut harness, &mut input, Gesture::MagicTap);
    assert!(harness.state_is::<PauseMenuState>());
}

#[test]
fn emergency_and_horn_holds_follow_rebound_keys() {
    let mut harness = a_drive("Touch held bindings");
    assert!(matches!(
        harness
            .app
            .ctx
            .bindings
            .set_chord(Action::EmergencyBrake, Chord::plain(Key::Z)),
        freight_fate::bindings::Rebind::Done
    ));
    let mut input = TouchInput::new();
    touch(&mut harness, &mut input, Gesture::EmergencyBrakeHoldBegan);
    assert!(harness.app.ctx.input.physically_down(Key::Z));
    touch(&mut harness, &mut input, Gesture::HoldEnded);
    assert!(!harness.app.ctx.input.physically_down(Key::Z));
    touch(&mut harness, &mut input, Gesture::HornHoldBegan);
    assert!(harness.app.ctx.input.physically_down(Key::H));
    touch(&mut harness, &mut input, Gesture::HoldEnded);
    assert!(!harness.app.ctx.input.physically_down(Key::H));
}

#[test]
fn touch_practice_takes_pedal_and_bound_holds_before_they_press_keys() {
    let mut harness = a_drive("Touch Practice Holds");
    assert!(matches!(
        harness
            .app
            .ctx
            .bindings
            .set_chord(Action::EmergencyBrake, Chord::plain(Key::Z)),
        freight_fate::bindings::Rebind::Done
    ));
    harness.app.push_state(TouchPracticeState::new());
    harness.clear_speech();

    harness.app.dispatch_gesture(Gesture::HoldUpperBegan);
    assert!(
        harness.transcript().iter().any(|line| line == "Gas."),
        "{:?}",
        harness.transcript()
    );
    assert!(!harness.app.ctx.input.physically_down(Key::Up));

    harness.clear_speech();
    harness
        .app
        .dispatch_gesture(Gesture::EmergencyBrakeHoldBegan);
    assert!(
        harness
            .transcript()
            .iter()
            .any(|line| line == "Emergency brake."),
        "{:?}",
        harness.transcript()
    );
    assert!(!harness.app.ctx.input.physically_down(Key::Z));
}

#[test]
fn gas_hold_swipe_left_changes_lanes_with_full_lane_keeping() {
    let mut harness = a_drive("Touch Lane Change");
    rolling(&mut harness, 55.0);
    harness.app.ctx.settings.lane_keeping = "full".to_string();
    harness.with_drive(|drive, _| {
        drive.lane.lane_count = 2;
        drive.lane.lane = 0;
    });
    let mut input = TouchInput::new();

    touch(&mut harness, &mut input, Gesture::HoldUpperBegan);
    touch(&mut harness, &mut input, Gesture::UpperHoldSwipeLeft);

    assert_eq!(
        harness.with_drive(|drive, _| drive.lane_change_target),
        Some(1)
    );
}

#[test]
fn single_gestures_run_their_default_commands() {
    for (gesture, action) in [
        (Gesture::Tap, Action::Speed),
        (Gesture::TwoFingerTap, Action::Status),
        (Gesture::ThreeFingerSwipeUp, Action::Route),
    ] {
        let (expected, _) = by_key("Touch Single Key", |h| rolling(h, 30.0), action, |_| ());
        let mut harness = a_drive("Touch Single");
        rolling(&mut harness, 30.0);
        let mut input = TouchInput::new();
        touch(&mut harness, &mut input, gesture);
        assert_eq!(harness.transcript(), expected, "{gesture:?}");
    }
    // The road ahead: each drive rolls its own ramp controls, so only the
    // readout itself is compared.
    let mut harness = a_drive("Touch Road Ahead");
    let mut input = TouchInput::new();
    touch(&mut harness, &mut input, Gesture::ThreeFingerSwipeDown);
    let said = harness.transcript();
    assert!(said.iter().any(|l| l.starts_with("Coming up")), "{said:?}");
}

#[test]
fn the_fixed_gestures_keep_their_keys_at_the_wheel() {
    let mut harness = a_drive("Touch Fixed");
    let mut input = TouchInput::new();
    touch(&mut harness, &mut input, Gesture::ThreeFingerTap);
    assert!(harness.state_is::<DrivingCommandsState>());
    // Back out with the two-finger swipe down, which is Escape.
    touch(&mut harness, &mut input, Gesture::TwoFingerSwipeDown);
    assert!(harness.state_is::<DrivingState>());
}

#[test]
fn a_gesture_moved_to_another_command_runs_that_one() {
    let (expected, _) = by_key("Touch Moved Key", |_| {}, Action::Fuel, |_| ());
    let mut harness = a_drive("Touch Moved");
    harness.app.ctx.settings.touch_bindings = "tap=fuel;magic_tap=none".to_string();
    harness.app.ctx.apply_bindings();
    let mut input = TouchInput::new();
    touch(&mut harness, &mut input, Gesture::Tap);
    assert_eq!(harness.transcript(), expected);

    harness.clear_speech();
    touch(&mut harness, &mut input, Gesture::MagicTap);
    assert!(harness.state_is::<DrivingState>(), "set to nothing");
    assert!(
        harness.transcript().is_empty(),
        "{:?}",
        harness.transcript()
    );
}

#[test]
fn off_the_road_a_gesture_is_still_its_key() {
    let mut harness = PlaytestHarness::new();
    harness.app.push_state(TouchGesturesState::new());
    harness.clear_speech();
    let mut input = TouchInput::new();
    // Magic tap is Space on a menu, not the pause menu.
    let events = input.handle(Gesture::MagicTap).events;
    assert_eq!(events, vec![InputEvent::Gesture(Gesture::MagicTap)]);
    let keys = Gesture::MagicTap.key_events();
    assert!(matches!(
        keys.first(),
        Some(InputEvent::KeyDown {
            key: Key::Space,
            mods: Mods::NONE,
            ..
        })
    ));
    let first = harness.focused_label();
    touch(&mut harness, &mut input, Gesture::SwipeDown);
    assert!(harness.state_is::<TouchGesturesState>());
    assert_ne!(
        harness.focused_label(),
        first,
        "swipe down is Down on a menu"
    );
    touch(&mut harness, &mut input, Gesture::SwipeUp);
    assert_eq!(harness.focused_label(), first);
}

#[test]
fn the_touch_gestures_screen_moves_a_gesture_and_saves_it() {
    let mut harness = PlaytestHarness::new();
    harness.app.push_state(TouchGesturesState::new());
    let labels = harness.menu_labels();
    for wanted in [
        "Tap: Speed",
        "Gas hold, tap with a second finger: Automatic speed control",
        "Brake hold, double tap with a second finger: Engine on or off",
        "Two-finger double tap: Pause",
        "Reset every touch gesture to its default",
    ] {
        assert!(
            labels.iter().any(|l| l == wanted),
            "{wanted:?} not in {labels:#?}"
        );
    }
    assert!(!labels.iter().any(|l| l.starts_with("Swipe left")));

    harness.select_menu_item("Tap: Speed");
    assert!(harness.state_is::<TouchCommandPickerState>());
    assert!(
        harness
            .menu_labels()
            .iter()
            .all(|l| l != Action::Accelerate.label()),
        "a held control cannot go on a tap"
    );
    harness.select_menu_item(Action::Fuel.label());
    assert!(harness.state_is::<TouchGesturesState>());
    assert_eq!(harness.app.ctx.settings.touch_bindings, "tap=fuel");
    assert_eq!(
        harness.app.ctx.bindings.touch_command(Gesture::Tap),
        Some(TouchCommand::Action(Action::Fuel))
    );
    assert!(harness
        .transcript()
        .iter()
        .any(|l| l == &format!("Tap now runs {}.", Action::Fuel.label())));

    harness.select_menu_item("Reset every touch gesture to its default");
    assert_eq!(harness.app.ctx.settings.touch_bindings, "");
}
