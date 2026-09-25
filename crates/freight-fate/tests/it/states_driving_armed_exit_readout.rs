//! How far to the exit the signal is on for, on demand (owner, driving,
//! 2026-09-24: "When the signal is on for the exit, I should be able to see
//! how far away from the exit I am"). Space ends with it and U leads with it;
//! nothing new is said unasked, and on the ramp both drop it.

use freight_fate::playtest::harness::{PlaytestHarness, StartDelivery};
use freight_fate::states::base::Key;

use crate::states_driving_decel_lane::{drive_to_the_gore, exit_rig_with, Rig};

fn last_main(harness: &PlaytestHarness) -> String {
    harness.app.main_lines().last().cloned().unwrap_or_default()
}

fn press(harness: &mut PlaytestHarness, key: Key) -> String {
    harness.clear_speech();
    harness.press_key(key, None);
    last_main(harness)
}

#[test]
fn test_space_and_u_name_the_signalled_stop_exit_and_its_distance() {
    // Signal on for a truck stop's exit 1.3 miles ahead, through the X key.
    let (mut harness, stop) = exit_rig_with(70.0, 0.0, 1.3, 62.0, false, Rig::default());
    harness.app.ctx.settings.imperial_units = true;

    let space = press(&mut harness, Key::Space);
    assert!(
        space.ends_with(" Signal on for exit 42, Prairie Travel Center, 1.3 miles."),
        "{space}"
    );

    let upcoming = press(&mut harness, Key::U);
    assert!(
        upcoming
            .starts_with("Coming up: signal on for exit 42, Prairie Travel Center, in 1.3 miles"),
        "{upcoming}"
    );
    // Named once, not again as the next stop.
    assert_eq!(
        upcoming.matches("Prairie Travel Center").count(),
        1,
        "{upcoming}"
    );

    // The answer is all the key said.
    assert_eq!(harness.transcript(), vec![upcoming.clone()]);

    // On the ramp, the ramp readouts take over.
    drive_to_the_gore(&mut harness, &stop);
    assert!(harness.read_drive(|d| d.ramp_mi.is_some()));
    let space = press(&mut harness, Key::Space);
    assert!(!space.contains("Signal on"), "{space}");
    let upcoming = press(&mut harness, Key::U);
    assert!(!upcoming.contains("signal on"), "{upcoming}");
}

#[test]
fn test_space_and_u_name_the_signalled_destination_exit() {
    let mut harness = PlaytestHarness::new();
    harness.start_delivery(StartDelivery::named("Armed Destination"));
    let (at_mi, name) = harness.with_drive(|d, ctx| {
        d.tutorial = None;
        d.departure_checked = true;
        d.trip.zones.clear();
        d.trip.curves.clear();
        let exit = d
            .destination_exit_stop(ctx)
            .expect("a delivery has a destination exit");
        let phrase = d.exit_phrase_of(ctx, &exit);
        let name = if !phrase.is_empty() {
            phrase
        } else if !exit.exit_label.is_empty() {
            exit.exit_label.clone()
        } else {
            format!("the destination exit for {}", exit.name)
        };
        d.trip.position_mi = exit.at_mi - 1.3;
        d.exit_stop = Some(exit.clone());
        (exit.at_mi, name)
    });
    harness.app.ctx.settings.imperial_units = true;

    // Signal on through the X key.
    press(&mut harness, Key::X);
    assert!(
        harness.read_drive(
            |d| d.exit_signal_on && d.exit_stop.as_ref().is_some_and(|s| s.at_mi == at_mi)
        )
    );

    let space = press(&mut harness, Key::Space);
    assert!(
        space.ends_with(&format!(" Signal on for {name}, 1.3 miles.")),
        "{space}"
    );
    let upcoming = press(&mut harness, Key::U);
    assert!(
        upcoming.starts_with(&format!("Coming up: signal on for {name}, in 1.3 miles")),
        "{upcoming}"
    );
    // The destination clause does not name the same exit a second time.
    assert!(!upcoming.contains("the destination exit, "), "{upcoming}");
}

#[test]
fn test_nothing_armed_leaves_both_readouts_as_they_were() {
    let mut harness = PlaytestHarness::new();
    harness.start_delivery(StartDelivery::named("Nothing Armed"));
    harness.with_drive(|d, _| {
        d.tutorial = None;
        d.departure_checked = true;
    });
    assert!(!harness.read_drive(|d| d.exit_signal_on));

    let space = press(&mut harness, Key::Space);
    assert!(!space.is_empty());
    assert!(!space.contains("Signal on"), "{space}");
    let upcoming = press(&mut harness, Key::U);
    assert!(!upcoming.is_empty());
    assert!(!upcoming.contains("signal on"), "{upcoming}");
}
