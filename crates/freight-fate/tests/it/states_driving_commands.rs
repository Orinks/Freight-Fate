//! The driving command list (`states/driving_menu_states/commands.rs`): F2 at
//! the wheel, and three-finger tap on a touch screen. Each row runs its
//! control the way the key does, after handing the drive back.

use ff_core::sim::weather::WeatherKind;

use freight_fate::bindings::{reserved_key_reason, Action, Chord};
use freight_fate::playtest::harness::{key_event, PlaytestHarness, StartDelivery};
use freight_fate::states::base::Key;
use freight_fate::states::driving::DrivingState;
use freight_fate::states::driving_menu_states::{DrivingCommandsState, DrivingStatusState};

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

fn press(harness: &mut PlaytestHarness, key: Key) {
    harness.key(key_event(key, None));
}

fn last_main(harness: &PlaytestHarness) -> String {
    harness.app.main_lines().last().cloned().unwrap_or_default()
}

#[test]
fn f2_lists_the_one_shot_controls_and_not_the_held_ones() {
    let mut harness = a_drive("Command List");
    press(&mut harness, Key::F2);
    assert!(harness.state_is::<DrivingCommandsState>());
    let labels = harness.menu_labels();
    for wanted in [
        Action::Speed.label(),
        Action::SpeedLimit.label(),
        Action::Engine.label(),
        Action::TakeExit.label(),
        "Raise the cruise target",
        "Next radio station",
        "Driving help",
        "Back to driving",
    ] {
        assert!(
            labels.iter().any(|l| l == wanted),
            "{wanted:?} not in {labels:#?}"
        );
    }
    for held in [
        Action::Accelerate,
        Action::Brake,
        Action::EmergencyBrake,
        Action::SteerLeft,
        Action::SteerRight,
        Action::Horn,
    ] {
        assert!(
            !labels.iter().any(|l| l == held.label()),
            "{:?} is held, yet listed: {labels:#?}",
            held
        );
    }
    assert_eq!(labels.last().map(String::as_str), Some("Back to driving"));
}

#[test]
fn a_row_returns_to_the_drive_and_answers_as_its_key_does() {
    let mut harness = a_drive("Command Speed");
    press(&mut harness, Key::Space);
    let by_key = last_main(&harness);
    assert!(!by_key.is_empty());

    harness.clear_speech();
    press(&mut harness, Key::F2);
    harness.select_menu_item(Action::Speed.label());
    assert!(harness.state_is::<DrivingState>());
    assert_eq!(last_main(&harness), by_key);
}

#[test]
fn a_row_that_opens_a_screen_opens_it_over_the_drive() {
    let mut harness = a_drive("Command Status");
    press(&mut harness, Key::F2);
    harness.select_menu_item(Action::Status.label());
    assert!(harness.state_is::<DrivingStatusState>());
    press(&mut harness, Key::Escape);
    assert!(harness.state_is::<DrivingState>());
}

#[test]
fn escape_closes_the_list_without_a_command() {
    let mut harness = a_drive("Command Escape");
    press(&mut harness, Key::F2);
    harness.clear_speech();
    press(&mut harness, Key::Escape);
    assert!(harness.state_is::<DrivingState>());
    assert_eq!(last_main(&harness), "Back to driving.");
}

#[test]
fn f2_cannot_be_given_to_another_control() {
    assert!(reserved_key_reason(&Chord::plain(Key::F2)).is_some());
    assert!(reserved_key_reason(&Chord::alt(Key::F2)).is_some());
}
