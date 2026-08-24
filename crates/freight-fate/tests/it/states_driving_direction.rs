//! Which way the truck is geared, and the gesture that changes it:
//! `update_reverse_controls` in `states/driving_updates/air.rs`, the clutch
//! the shift key must not press on an automatic, and the two rescues that
//! sit beside them -- running dry and stopping the event voice.
//!
//! Ported from the direction-control block of
//! `tests/test_driving_features.py` (`test_shift_key_does_not_press_clutch_in_automatic`
//! through `test_accelerator_does_not_thrust_while_braking_in_reverse`, plus
//! `test_active_drive_applies_manual_setting_and_announces_it`,
//! `test_fuel_rescue_stops_the_truck_before_restart`,
//! `test_control_stops_event_voice_without_flushing_main_speech` and
//! `test_delivery_trip_carries_no_silent_arrival_zones`).
//!
//! `monkeypatch.setattr(pygame.key, "get_pressed", ...)` becomes
//! `ctx.input.press`, the held-key store the shipped input loop writes.
//! Python's `_update_reverse_controls` defaults `accel_held`/`brake_held` to
//! the ramped values; the Rust call takes all four, so [`reverse_controls`]
//! below restores that default and [`hold_direction_control`] is the same
//! `_hold_direction_control` helper.

use ff_core::sim::transmission::REVERSE;
use ff_core::sim::weather::WeatherKind;

use freight_fate::playtest::harness::{key_event, PlaytestHarness, StartDelivery};
use freight_fate::states::base::{Key, Mods};
use freight_fate::states::driving_core::DRIVE_PHASE_DELIVERY;

const DT: f64 = 1.0 / 60.0;
const MPH_PER_MPS: f64 = 2.2369362920544;

// -- rigging -------------------------------------------------------------------------

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
        drive.trip.zones.retain(|z| z.aadt.is_none());
        drive.trip.weather.current = WeatherKind::Clear;
    });
    harness.clear_speech();
    harness
}

/// `driving._update_reverse_controls(accelerating=..., braking_key=...)`:
/// the keyboard call, where the instantaneous press states are the ramped
/// ones.
fn reverse_controls(harness: &mut PlaytestHarness, accelerating: bool, braking_key: bool) -> bool {
    harness.with_drive(move |drive, ctx| {
        drive.update_reverse_controls(
            ctx,
            accelerating,
            braking_key,
            accelerating,
            braking_key,
            DT,
        )
    })
}

/// The controller call, where the unsmoothed trigger target is its own input.
fn reverse_controls_with(
    harness: &mut PlaytestHarness,
    accelerating: bool,
    braking_key: bool,
    accel_held: bool,
    brake_held: bool,
) -> bool {
    harness.with_drive(move |drive, ctx| {
        drive.update_reverse_controls(ctx, accelerating, braking_key, accel_held, brake_held, DT)
    })
}

/// `_hold_direction_control`: hold the direction control for the engage beat
/// and hand back the last result.
fn hold_direction_control(
    harness: &mut PlaytestHarness,
    accelerating: bool,
    braking_key: bool,
) -> bool {
    let mut result = false;
    for _ in 0..((0.75 * 60.0) as usize + 2) {
        result = reverse_controls(harness, accelerating, braking_key);
    }
    result
}

// -- the transmission setting -----------------------------------------------------------

#[test]
fn test_active_drive_applies_manual_setting_and_announces_it() {
    let mut harness = a_drive("Manual Switch");
    harness.app.ctx.input.press(Key::LShift, Mods::NONE);
    assert!(harness.read_drive(|d| d.truck().transmission.automatic));
    harness.app.ctx.settings.automatic_transmission = false;
    harness.clear_speech();

    harness.advance_clock(DT);
    harness.with_drive(|drive, ctx| drive.update_frame(ctx, DT));

    assert!(!harness.read_drive(|d| d.truck().transmission.automatic));
    assert_eq!(harness.read_drive(|d| d.truck().transmission.clutch), 1.0);
    assert!(
        harness
            .app
            .event_calls()
            .contains(&("Transmission changed to manual.".to_string(), true)),
        "{:#?}",
        harness.app.event_calls()
    );
}

#[test]
fn test_shift_key_does_not_press_clutch_in_automatic() {
    let mut harness = a_drive("Auto Clutch");
    harness.app.ctx.input.press(Key::LShift, Mods::NONE);
    assert!(harness.read_drive(|d| d.truck().transmission.automatic));

    harness.advance_clock(DT);
    harness.with_drive(|drive, ctx| drive.update_frame(ctx, DT));

    assert_eq!(harness.read_drive(|d| d.truck().transmission.clutch), 0.0);
}

// -- selecting a direction ---------------------------------------------------------------

#[test]
fn test_automatic_reverse_selection_is_spoken() {
    let mut harness = a_drive("Reverse Select");
    harness.clear_speech();

    assert!(hold_direction_control(&mut harness, false, true));

    // Reverse says nothing: the beep is already running and keeps running the
    // whole time the truck is in reverse, which a one-shot sentence cannot do
    // (owner, 2026-08-21). The gear is the outcome to assert, and the status
    // readout still carries the words on request.
    assert!(harness.read_drive(|d| d.truck().transmission.in_reverse()));
    assert_eq!(
        harness.read_drive(|d| d.status_text.clone()),
        "Reverse selected. Backing slowly."
    );
    assert!(
        !harness
            .app
            .event_lines()
            .contains(&"Reverse selected. Backing slowly.".to_string()),
        "{:#?}",
        harness.app.event_lines()
    );
}

#[test]
fn test_simple_automatic_fresh_press_at_standstill_changes_direction() {
    let mut harness = a_drive("Simple Direction");
    assert_eq!(
        harness.app.ctx.settings.automatic_direction_changes,
        "simple"
    );

    harness.with_drive(|drive, _| drive.truck_mut().velocity_mps = 0.0);
    // A tap arms but does not engage; the deliberate hold does.
    reverse_controls(&mut harness, false, true);
    reverse_controls(&mut harness, false, false);
    assert!(!harness.read_drive(|d| d.truck().transmission.in_reverse()));
    assert!(hold_direction_control(&mut harness, false, true));
    assert!(harness.read_drive(|d| d.truck().transmission.in_reverse()));

    harness.with_drive(|drive, _| drive.truck_mut().velocity_mps = 0.0);
    reverse_controls(&mut harness, false, false);
    hold_direction_control(&mut harness, true, false);
    assert_ne!(harness.read_drive(|d| d.truck().transmission.gear), REVERSE);
}

#[test]
fn test_brake_hold_through_a_stop_never_selects_reverse() {
    // A held-brake stop must end held, in forward gear. The old behavior
    // dropped the truck into reverse the moment a held-brake stop finished --
    // including at the ramp light's own "hold the brakes for green" -- and the
    // flipped reverse controls then ate the driver's next input (owner-hit on
    // I-10, 2026-07-14).
    let mut harness = a_drive("Brake Hold");
    assert_eq!(
        harness.app.ctx.settings.automatic_direction_changes,
        "simple"
    );

    // Brake pressed while rolling: a stop in progress.
    harness.with_drive(|drive, _| drive.truck_mut().velocity_mps = 20.0);
    assert!(!reverse_controls(&mut harness, false, true));
    // Still holding as the truck reaches a standstill: stay in forward,
    // however long the hold -- the press never landed at a standstill.
    harness.with_drive(|drive, _| drive.truck_mut().velocity_mps = 0.0);
    for _ in 0..120 {
        assert!(!reverse_controls(&mut harness, false, true));
    }
    assert!(!harness.read_drive(|d| d.truck().transmission.in_reverse()));

    // A confirm-tap at the stop (screen-reader habit, owner-hit at the
    // Holbrook yard): arms, but a tap is not a hold -- still forward.
    reverse_controls(&mut harness, false, false);
    reverse_controls(&mut harness, false, true);
    reverse_controls(&mut harness, false, false);
    assert!(!harness.read_drive(|d| d.truck().transmission.in_reverse()));

    // A fresh press at the standstill HELD through the beat: the gesture.
    assert!(hold_direction_control(&mut harness, false, true));
    assert!(harness.read_drive(|d| d.truck().transmission.in_reverse()));

    // Mirror: brake the reverse roll with the accelerator and hold it through
    // the stop -- the truck must not lurch into forward gear.
    harness.with_drive(|drive, _| drive.truck_mut().velocity_mps = -2.5);
    assert!(reverse_controls(&mut harness, false, true));
    reverse_controls(&mut harness, false, false);
    assert!(!reverse_controls(&mut harness, true, false));
    harness.with_drive(|drive, _| drive.truck_mut().velocity_mps = 0.0);
    for _ in 0..120 {
        reverse_controls(&mut harness, true, false);
    }
    // Still reverse: the hold began moving.
    assert!(harness.read_drive(|d| d.truck().transmission.in_reverse()));
    // Release, then press and hold: a deliberate forward selection.
    reverse_controls(&mut harness, false, false);
    hold_direction_control(&mut harness, true, false);
    assert!(!harness.read_drive(|d| d.truck().transmission.in_reverse()));
}

#[test]
fn test_controller_trigger_edges_gate_direction_changes() {
    // The controller path reads the unsmoothed trigger target, so a full
    // release is observable even while the smoothed brake value lingers --
    // and only a fresh target press at a standstill, held through the beat,
    // shifts.
    let mut harness = a_drive("Trigger Edges");
    harness.with_drive(|drive, _| drive.truck_mut().velocity_mps = 0.0);

    // Trigger held coming into the stop: no edge, never engages.
    harness.with_drive(|drive, _| drive.reverse_brake_held = true);
    for _ in 0..60 {
        assert!(!reverse_controls_with(
            &mut harness,
            false,
            true,
            false,
            true
        ));
    }
    assert!(!harness.read_drive(|d| d.truck().transmission.in_reverse()));

    // The instantaneous target reaches neutral before the smoothed brake.
    assert!(!reverse_controls_with(
        &mut harness,
        false,
        true,
        false,
        false
    ));
    // Fresh target press, held through the beat: reverse engages.
    let mut result = false;
    for _ in 0..50 {
        result = reverse_controls_with(&mut harness, false, true, false, true);
    }
    assert!(result);
    assert!(harness.read_drive(|d| d.truck().transmission.in_reverse()));
}

#[test]
fn test_automatic_held_brake_does_not_engage_reverse() {
    // Braking to a stop and holding must not slip into reverse; only a fresh
    // press (release, then press again) engages it.
    let mut harness = a_drive("Held Brake");
    harness.app.ctx.settings.automatic_direction_changes = "deliberate".to_string();
    harness.with_drive(|drive, _| {
        drive.truck_mut().velocity_mps = 0.0;
        // Brake was already held coming into this frame, as after braking to
        // a stop -- no rising edge, so reverse must not engage, ever.
        drive.reverse_brake_held = true;
    });
    for _ in 0..120 {
        assert!(!reverse_controls(&mut harness, false, true));
    }
    assert!(!harness.read_drive(|d| d.truck().transmission.in_reverse()));

    // Release the brake, then a fresh press held through the beat.
    assert!(!reverse_controls(&mut harness, false, false));
    assert!(hold_direction_control(&mut harness, false, true));
    assert!(harness.read_drive(|d| d.truck().transmission.in_reverse()));
}

#[test]
fn test_automatic_held_accelerator_does_not_flip_out_of_reverse() {
    // Holding the accelerator to brake a reverse roll to a stop must not flip
    // to forward; a fresh press is required.
    let mut harness = a_drive("Held Accel");
    harness.app.ctx.settings.automatic_direction_changes = "deliberate".to_string();
    harness.with_drive(|drive, _| {
        drive.truck_mut().transmission.gear = REVERSE;
        drive.truck_mut().velocity_mps = 0.0;
        // Accelerator was held while it braked the reverse roll to a stop.
        drive.reverse_accel_held = true;
    });
    for _ in 0..120 {
        assert!(!reverse_controls(&mut harness, true, false));
    }
    assert!(harness.read_drive(|d| d.truck().transmission.in_reverse()));

    // Release, then a fresh press held through the beat flips to forward.
    reverse_controls(&mut harness, false, false);
    hold_direction_control(&mut harness, true, false);
    assert!(!harness.read_drive(|d| d.truck().transmission.in_reverse()));
}

#[test]
fn test_accelerator_does_not_thrust_while_braking_in_reverse() {
    // Pressing the accelerator to brake a backward roll must never command
    // reverse thrust -- throttle stays down while the service brake engages.
    let mut harness = a_drive("Reverse Thrust");
    harness.app.ctx.settings.automatic_direction_changes = "deliberate".to_string();
    harness.app.ctx.input.press(Key::Up, Mods::NONE);
    harness.with_drive(|drive, _| {
        drive.truck_mut().transmission.gear = REVERSE;
        drive.truck_mut().velocity_mps = -3.0;
        drive.truck_mut().throttle = 0.5;
        // Accelerator already held, so this is not a fresh press: no gear flip.
        drive.reverse_accel_held = true;
    });

    harness.advance_clock(DT);
    harness.with_drive(|drive, ctx| drive.update_frame(ctx, DT));

    assert!(harness.read_drive(|d| d.truck().transmission.in_reverse()));
    // Decays toward 0 rather than ramping up.
    assert!(harness.read_drive(|d| d.truck().throttle) < 0.5);
    // The service brake is what arrests the roll.
    assert!(harness.read_drive(|d| d.truck().brake) > 0.0);
}

// -- the rescues -------------------------------------------------------------------------

#[test]
fn test_fuel_rescue_stops_the_truck_before_restart() {
    let mut harness = a_drive("Fuel Rescue");
    harness.with_drive(|drive, _| {
        let truck = drive.truck_mut();
        truck.start_engine();
        truck.set_air_ready(false);
        truck.transmission.gear = 10;
        truck.velocity_mps = 65.0 / MPH_PER_MPS;
        truck.throttle = 0.8;
        truck.brake = 0.4;
        truck.set_engine_brake(true);
        truck.emergency_brake = true;
        truck.fuel_gal = 0.0;
    });

    harness.advance_clock(DT);
    harness.with_drive(|drive, ctx| drive.update_frame(ctx, DT));

    harness.read_drive(|d| {
        let truck = d.truck();
        assert!((truck.fuel_gal - 30.0).abs() < 1e-6, "{}", truck.fuel_gal);
        assert_eq!(truck.speed_mph(), 0.0);
        assert!(!truck.engine_on);
        assert_eq!(truck.rpm, 0.0);
        assert!(truck.parking_brake);
        assert_eq!(truck.throttle, 0.0);
        assert_eq!(truck.brake, 0.0);
        assert!(!truck.engine_brake());
        assert!(!truck.emergency_brake);
        assert!(truck.transmission.in_neutral());
    });

    harness.with_drive(|drive, ctx| drive.handle_key_event(ctx, &key_event(Key::E, None)));

    assert!(harness.read_drive(|d| d.truck().engine_on));
    assert_eq!(harness.read_drive(|d| d.truck().speed_mph()), 0.0);
}

#[test]
fn test_control_stops_event_voice_without_flushing_main_speech() {
    let mut harness = a_drive("Ctrl Stop");
    harness.clear_speech();

    harness.with_drive(|drive, ctx| drive.handle_key_event(ctx, &key_event(Key::LCtrl, None)));

    let capture = harness.app.speech();
    assert_eq!(capture.stop_event_calls(), 1);
    assert_eq!(capture.stop_main_calls(), 0);
    drop(capture);
    // Python read `driving.lines()[-1]`, the drive's rendered readout; the
    // port's equivalent is the status line the key sets.
    let status = harness.read_drive(|d| d.status_text.clone());
    assert!(status.contains("Event voice stopped"), "{status}");
}

// -- the delivery trip's own zones --------------------------------------------------------

#[test]
fn test_delivery_trip_carries_no_silent_arrival_zones() {
    // The legacy last-miles arrival zones (destination approach 35, gate 15)
    // were silenced as freeway chatter but still enforced -- a speeding strike
    // citing "the limit is 35" on open interstate with 65 spoken (owner-hit on
    // I-10). The exit, ramp terminal, and street chain own arrival speeds; the
    // delivery trip must not carry the silent zones at all.
    let mut harness = PlaytestHarness::new();
    harness.start_delivery(StartDelivery::named("Arrival Zones"));

    assert_eq!(
        harness.read_drive(|d| d.phase.clone()),
        DRIVE_PHASE_DELIVERY
    );
    let reasons = harness.read_drive(|d| {
        d.trip
            .zones
            .iter()
            .map(|z| z.reason.clone())
            .collect::<Vec<_>>()
    });
    assert!(
        !reasons.iter().any(|r| r == "destination approach"),
        "{reasons:#?}"
    );
    assert!(
        !reasons.iter().any(|r| r == "facility gate"),
        "{reasons:#?}"
    );
    let reason = harness.with_drive(|d, _| {
        let at = d.trip.total_miles() - 0.5;
        d.trip.speed_limit_at(at).1
    });
    assert_ne!(reason.as_deref(), Some("destination approach"));
    assert_ne!(reason.as_deref(), Some("facility gate"));
}
