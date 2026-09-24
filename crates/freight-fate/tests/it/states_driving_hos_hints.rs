//! Opt-in early stop planning, using the same legal-reach route as Alt D.

use ff_core::sim::trip_models::RoadStop;
use freight_fate::app::testing::TestApp;

use super::states_driving_menus_support::{a_drive_between, drive_and_ctx};

fn stop(name: &str, mile: f64, action: &str) -> RoadStop {
    let mut stop = RoadStop::new(name, mile, "travel_center");
    stop.actions = vec![action.into()];
    stop.parking = "confirmed".into();
    stop
}

fn setup(action: &str) -> (TestApp, freight_fate::app::SharedState) {
    let mut app = TestApp::new();
    let drive = a_drive_between(&mut app, "Buffalo", "Albany", "Hint Driver");
    drive_and_ctx(&drive, &mut app, |d, ctx| {
        d.departure_checked = true;
        d.trip.position_mi = 10.0;
        d.trip.stops = vec![stop("First", 12.0, action), stop("Last", 15.0, action)];
        ctx.profile.as_mut().unwrap().hos.duty_min = 650.0;
    });
    app.clear_speech();
    (app, drive)
}

#[test]
fn driving_frame_uses_the_opt_in_and_keeps_required_warnings_without_it() {
    let (mut app, drive) = setup("sleep");
    drive_and_ctx(&drive, &mut app, |d, ctx| {
        d.trip.truck.velocity_mps = 25.0;
        d.trip.stops = vec![stop("Early", 25.0, "sleep"), stop("Last", 30.0, "sleep")];
        ctx.profile.as_mut().unwrap().hos.duty_min = 660.0;
        d.update_hours_and_fatigue(ctx, 0.0);
    });
    assert!(!app
        .event_lines()
        .join(" ")
        .contains("Plan your next sleep stop"));
    app.ctx.settings.hos_planning_hints = true;
    drive_and_ctx(&drive, &mut app, |d, ctx| {
        d.update_hours_and_fatigue(ctx, 0.0)
    });
    assert!(app
        .event_lines()
        .join(" ")
        .contains("Plan your next sleep stop"));

    app.ctx.stop_event_speech();
    app.clear_speech();
    app.ctx.settings.hos_planning_hints = false;
    app.ctx.profile.as_mut().unwrap().hos.duty_min = 780.0;
    drive_and_ctx(&drive, &mut app, |d, ctx| {
        d.update_hours_and_fatigue(ctx, 0.0)
    });
    assert!(app.event_lines().join(" ").contains("Hours of service"));
}

#[test]
fn optional_hint_waits_until_three_hours_and_speaks_once() {
    let (mut app, drive) = setup("sleep");
    let clock = app.fake_pacer_clock();
    drive_and_ctx(&drive, &mut app, |d, ctx| d.maybe_hos_planning_hint(ctx));
    assert!(app.event_lines().is_empty());
    app.ctx.settings.hos_planning_hints = true;
    drive_and_ctx(&drive, &mut app, |d, ctx| d.maybe_hos_planning_hint(ctx));
    assert!(
        app.event_lines().is_empty(),
        "too early for a 190-minute limit"
    );

    app.ctx.profile.as_mut().unwrap().hos.duty_min = 660.0;
    drive_and_ctx(&drive, &mut app, |d, ctx| d.maybe_hos_planning_hint(ctx));
    let heard = app.event_lines().join(" ");
    assert!(heard.contains("Plan your next sleep stop"), "{heard}");
    assert!(heard.contains("Last"), "{heard}");
    assert!(heard.contains("last reachable one"), "{heard}");
    drive_and_ctx(&drive, &mut app, |d, ctx| d.maybe_hos_planning_hint(ctx));
    assert_eq!(
        app.event_lines()
            .iter()
            .filter(|line| line.contains("Plan your next sleep stop"))
            .count(),
        1
    );
    let first_key = app.ctx.profile.as_ref().unwrap().hos.warned.clone();

    app.clear_speech();
    app.ctx.stop_event_speech();
    clock.advance(120.0);
    app.ctx.profile.as_mut().unwrap().hos.sleep();
    app.ctx.profile.as_mut().unwrap().hos.duty_min = 660.0;
    drive_and_ctx(&drive, &mut app, |d, ctx| {
        d.trip.game_minutes += 600.0;
        d.maybe_hos_planning_hint(ctx);
    });
    let pending = app.ctx.event_delivery_pending();
    assert!(
        app.event_lines()
            .join(" ")
            .contains("Plan your next sleep stop"),
        "events={:?}, first={first_key:?}, warned={:?}, pending={}",
        app.event_lines(),
        app.ctx.profile.as_ref().unwrap().hos.warned,
        pending
    );
}

#[test]
fn early_hint_names_when_no_stop_can_be_reached() {
    let (mut app, drive) = setup("sleep");
    app.ctx.settings.hos_planning_hints = true;
    app.ctx.profile.as_mut().unwrap().hos.duty_min = 660.0;
    drive_and_ctx(&drive, &mut app, |d, ctx| {
        d.trip.stops.clear();
        d.maybe_hos_planning_hint(ctx);
    });
    let heard = app.event_lines().join(" ");
    assert!(heard.contains("No reachable sleep stop remains"), "{heard}");
    assert!(heard.contains("Find a safe place to stop"), "{heard}");
}

#[test]
fn break_hint_uses_break_stops_and_stays_ahead_of_the_hour_warning() {
    let (mut app, drive) = setup("break");
    app.ctx.settings.hos_planning_hints = true;
    {
        let hos = &mut app.ctx.profile.as_mut().unwrap().hos;
        hos.duty_min = 0.0;
        hos.driving_min = 300.0;
        hos.since_break_min = 300.0;
    }
    drive_and_ctx(&drive, &mut app, |d, ctx| d.maybe_hos_planning_hint(ctx));
    let heard = app.event_lines().join(" ");
    assert!(heard.contains("Plan your next break stop"), "{heard}");
    assert!(!heard.contains("Hours of service:"), "{heard}");
}

#[test]
fn quiet_and_urgent_only_suppress_optional_words_without_spending_the_hint() {
    for rung in ["quiet", "urgent_only"] {
        let (mut app, drive) = setup("sleep");
        app.ctx.settings.hos_planning_hints = true;
        app.ctx.settings.driving_speech = rung.into();
        app.ctx.profile.as_mut().unwrap().hos.duty_min = 660.0;
        drive_and_ctx(&drive, &mut app, |d, ctx| d.maybe_hos_planning_hint(ctx));
        assert!(
            app.event_lines().is_empty(),
            "{rung}: {:?}",
            app.event_lines()
        );
        assert!(!app
            .ctx
            .profile
            .as_ref()
            .unwrap()
            .hos
            .warned
            .iter()
            .any(|key| key.contains("plan-hint")));
        app.ctx.settings.driving_speech = "standard".into();
        drive_and_ctx(&drive, &mut app, |d, ctx| d.maybe_hos_planning_hint(ctx));
        assert!(app
            .event_lines()
            .join(" ")
            .contains("Plan your next sleep stop"));
    }
}

#[test]
fn reachable_destination_can_become_unreachable_after_a_delay() {
    let (mut app, drive) = setup("sleep");
    app.ctx.settings.hos_planning_hints = true;
    app.ctx.profile.as_mut().unwrap().hos.duty_min = 660.0;
    drive_and_ctx(&drive, &mut app, |d, ctx| {
        d.trip.position_mi = d.trip.total_miles() - 60.0;
        assert!(d.hos_stop_advice(ctx).unwrap().destination_reachable);
        d.maybe_hos_planning_hint(ctx);
    });
    assert!(app.event_lines().is_empty());
    assert!(app.ctx.profile.as_ref().unwrap().hos.warned.is_empty());

    drive_and_ctx(&drive, &mut app, |d, ctx| {
        let travel_min = d.hos_stop_advice(ctx).unwrap().destination_travel_min;
        assert!((60.0..=180.0).contains(&travel_min));
        ctx.profile.as_mut().unwrap().hos.duty_min = 840.0 - travel_min - 2.0;
        assert!(!d.hos_stop_advice(ctx).unwrap().destination_reachable);
        d.maybe_hos_planning_hint(ctx);
    });
    assert!(app
        .event_lines()
        .join(" ")
        .contains("No reachable sleep stop"));
}

#[test]
fn interrupted_hint_is_retried_until_delivery_completes() {
    let (mut app, drive) = setup("sleep");
    let clock = app.fake_pacer_clock();
    app.ctx.settings.hos_planning_hints = true;
    app.ctx.profile.as_mut().unwrap().hos.duty_min = 660.0;
    drive_and_ctx(&drive, &mut app, |d, ctx| d.maybe_hos_planning_hint(ctx));
    assert!(app
        .event_lines()
        .join(" ")
        .contains("Plan your next sleep stop"));
    assert!(app.ctx.profile.as_ref().unwrap().hos.warned.is_empty());

    app.ctx.stop_event_speech();
    app.clear_speech();
    clock.advance(120.0);
    drive_and_ctx(&drive, &mut app, |d, ctx| d.maybe_hos_planning_hint(ctx));
    assert!(app
        .event_lines()
        .join(" ")
        .contains("Plan your next sleep stop"));
    assert!(app.ctx.profile.as_ref().unwrap().hos.warned.is_empty());

    clock.advance(120.0);
    drive_and_ctx(&drive, &mut app, |d, ctx| d.maybe_hos_planning_hint(ctx));
    assert!(app
        .ctx
        .profile
        .as_ref()
        .unwrap()
        .hos
        .warned
        .iter()
        .any(|key| key.contains("plan-hint")));
}

#[test]
fn selected_stop_and_earlier_stop_warning_suppress_late_planning_advice() {
    let (mut app, drive) = setup("sleep");
    app.ctx.settings.hos_planning_hints = true;
    app.ctx.profile.as_mut().unwrap().hos.duty_min = 660.0;
    drive_and_ctx(&drive, &mut app, |d, ctx| {
        d.selected_stop_key = Some("planned-stop".to_string());
        d.maybe_hos_planning_hint(ctx);
    });
    assert!(app.event_lines().is_empty());
    assert!(app.ctx.profile.as_ref().unwrap().hos.warned.is_empty());

    drive_and_ctx(&drive, &mut app, |d, ctx| {
        d.selected_stop_key = None;
        let kind = ctx
            .profile
            .as_ref()
            .unwrap()
            .hos
            .next_limit(&ctx.settings.hos_mode)
            .unwrap()
            .kind;
        ctx.profile
            .as_mut()
            .unwrap()
            .hos
            .warned
            .push(format!("{kind}:hos-stop:planned-stop"));
        d.maybe_hos_planning_hint(ctx);
    });
    assert!(app.event_lines().is_empty());
    assert!(!app
        .ctx
        .profile
        .as_ref()
        .unwrap()
        .hos
        .warned
        .iter()
        .any(|key| key.contains("plan-hint")));
}
