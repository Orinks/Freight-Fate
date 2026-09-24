//! Real rest-menu choices against a live drive and its delivery clock.

use ff_core::sim::hos;
use freight_fate::app::testing::TestApp;
use freight_fate::states::base::Menu;
use freight_fate::states::driving_menu_states::DriveRef;
use freight_fate::states::driving_rest_states::RestStopState;

use super::states_driving_menus_support::{a_drive, activate, sleep_stop, with_drive};

fn setup() -> (TestApp, freight_fate::app::SharedState, RestStopState) {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let at = with_drive(&drive, |d| d.trip.position_mi);
    let state = RestStopState::with_drive(DriveRef::of(&drive), sleep_stop(at), false);
    with_drive(&drive, |d| {
        d.trip.game_minutes = 0.0;
        d.job.deadline_game_h = 12.0;
    });
    let p = app.ctx.profile.as_mut().expect("a career");
    p.hos.drive(300.0);
    p.fatigue = 70.0;
    (app, drive, state)
}

#[test]
fn break_then_three_hours_preserves_the_short_rest_cost() {
    let (mut app, drive, mut state) = setup();
    Menu::enter(&mut state, &mut app.ctx);
    activate(&mut state, &mut app.ctx, "Take a 30-minute break");
    let p = app.ctx.profile.as_ref().expect("a career");
    assert_eq!(p.hos.since_break_min, 0.0);
    assert_eq!(p.hos.duty_min, 330.0);
    assert_eq!(p.fatigue, hos::rest_break(70.0));
    assert_eq!(with_drive(&drive, |d| d.trip.game_minutes), 30.0);
    assert!(app
        .main_lines()
        .join(" ")
        .contains("11.5 hours left to deliver"));

    app.clear_speech();
    activate(&mut state, &mut app.ctx, "Sleep 3 hours in sleeper berth");
    let preview = app.main_lines().join(" ");
    assert!(
        preview.contains("This sleep alone does not restore driving time"),
        "{preview}"
    );
    assert!(
        preview.contains("legal driving window closes in 5.5 hours"),
        "{preview}"
    );
    assert!(
        preview.contains("The delivery deadline will be in 8.5 hours"),
        "{preview}"
    );
    assert_eq!(with_drive(&drive, |d| d.trip.game_minutes), 30.0);
    assert_eq!(app.ctx.profile.as_ref().unwrap().hos.duty_min, 330.0);

    app.clear_speech();
    activate(&mut state, &mut app.ctx, "Sleep 3 hours in sleeper berth");
    let p = app.ctx.profile.as_ref().unwrap();
    assert_eq!(p.hos.driving_min, 300.0);
    assert_eq!(p.hos.duty_min, 510.0);
    assert_eq!(
        p.fatigue,
        hos::rest_sleeper_split(hos::rest_break(70.0), 180.0, false)
    );
    assert_eq!(with_drive(&drive, |d| d.trip.game_minutes), 210.0);
    let woke = app.main_lines().join(" ");
    assert!(woke.contains("did NOT reset your hours"), "{woke}");
    assert!(woke.contains("8.5 hours left to deliver"), "{woke}");
}

#[test]
fn both_orders_of_seven_three_credit_only_after_the_pair() {
    for (first, second) in [(3, 7), (7, 3)] {
        let (mut app, drive, mut state) = setup();
        Menu::enter(&mut state, &mut app.ctx);
        let first_row = format!("Sleep {first} hours in sleeper berth");
        let second_row = format!("Sleep {second} hours in sleeper berth");
        let before = with_drive(&drive, |d| d.trip.game_minutes);
        app.clear_speech();
        activate(&mut state, &mut app.ctx, &first_row);
        let preview = app.main_lines().join(" ");
        assert!(preview.contains("Preview: sleep"), "{preview}");
        assert_eq!(with_drive(&drive, |d| d.trip.game_minutes), before);
        activate(&mut state, &mut app.ctx, &first_row);
        let p = app.ctx.profile.as_ref().unwrap();
        assert!(p.hos.split_pending_summary().is_some());
        assert_eq!(p.hos.duty_min, 300.0 + if first == 3 { 180.0 } else { 0.0 });
        assert_eq!(
            with_drive(&drive, |d| d.trip.game_minutes),
            first as f64 * 60.0
        );

        app.ctx.profile.as_mut().unwrap().hos.drive(60.0);
        let before = with_drive(&drive, |d| d.trip.game_minutes);
        app.clear_speech();
        activate(&mut state, &mut app.ctx, &second_row);
        let preview = app.main_lines().join(" ");
        assert!(preview.contains("completes a sleeper split"), "{preview}");
        assert!(
            preview.contains("driving allowance is 10.0 hours"),
            "{preview}"
        );
        assert!(
            preview.contains("legal driving window closes in 13.0 hours"),
            "{preview}"
        );
        assert_eq!(with_drive(&drive, |d| d.trip.game_minutes), before);
        activate(&mut state, &mut app.ctx, &second_row);
        let p = app.ctx.profile.as_ref().unwrap();
        assert_eq!(p.hos.driving_min, 60.0);
        assert_eq!(p.hos.duty_min, 60.0);
        assert_eq!(p.hos.split_pending_summary(), None);
        assert_eq!(with_drive(&drive, |d| d.trip.game_minutes), 600.0);
        assert!(app
            .main_lines()
            .join(" ")
            .contains("Sleeper split credited"));
    }
}

#[test]
fn full_sleep_resets_hos_but_spends_ten_delivery_hours() {
    let (mut app, drive, mut state) = setup();
    Menu::enter(&mut state, &mut app.ctx);
    app.clear_speech();
    activate(&mut state, &mut app.ctx, "Sleep 10 hours");
    let preview = app.main_lines().join(" ");
    assert!(preview.contains("resets your driving hours"), "{preview}");
    assert!(
        preview.contains("driving allowance is 11.0 hours"),
        "{preview}"
    );
    assert!(
        preview.contains("legal driving window closes in 14.0 hours"),
        "{preview}"
    );
    assert!(
        preview.contains("The delivery deadline will be in 2.0 hours"),
        "{preview}"
    );
    assert_eq!(with_drive(&drive, |d| d.trip.game_minutes), 0.0);
    activate(&mut state, &mut app.ctx, "Sleep 10 hours");
    let p = app.ctx.profile.as_ref().unwrap();
    assert_eq!(p.hos.driving_min, 0.0);
    assert_eq!(p.hos.duty_min, 0.0);
    assert_eq!(p.fatigue, 0.0);
    assert_eq!(with_drive(&drive, |d| d.trip.game_minutes), 600.0);
    assert!(app
        .main_lines()
        .join(" ")
        .contains("2.0 hours left to deliver"));
}
