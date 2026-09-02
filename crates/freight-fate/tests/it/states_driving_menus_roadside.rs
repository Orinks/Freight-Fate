//! The three roadside enforcement outcomes in `states/driving_rest_states.rs`:
//! a speeding stop, a non-speeding enforcement stop, and the felony stop that
//! ends a run.
//!
//! Python covered these through `driving_updates`' pull-over machinery, which
//! is another task's suite; what is pinned here is what the screens themselves
//! decide and say, which is where `_resolve` charges the money exactly once.

use ff_core::models::enforcement;
use ff_core::sim::hos;

use freight_fate::app::testing::TestApp;
use freight_fate::states::base::Menu;
use freight_fate::states::driving_core::{DRIVE_PHASE_DELIVERY, FAILURE_TO_STOP_DAMAGE_PCT};
use freight_fate::states::driving_rest_states::{
    EnforcementStopState, FelonyStopState, TrafficStopState,
};
use freight_fate::states::driving_updates::pending::EnforcementStopParams;

use crate::states_driving_menus_support::*;

fn params(title: &str, out_of_service: bool, inspection_on_stop: bool) -> EnforcementStopParams {
    EnforcementStopParams {
        title: title.to_string(),
        summary: "The inspector writes it up.".to_string(),
        fine: enforcement::LANE_MISUSE_FINE,
        reputation_hit: 2.0,
        signaled: true,
        return_message: "Back on the highway.".to_string(),
        out_of_service,
        warned: false,
        construction_zone: false,
        inspection_on_stop,
    }
}

// -- the speeding stop --------------------------------------------------------------------

#[test]
fn test_a_first_marginal_stop_is_a_warning_not_a_ticket() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let money_before = app.ctx.profile.as_ref().expect("a career").money;
    let state = drive_and_ctx(&drive, &mut app, |d, ctx| {
        TrafficStopState::new(ctx, d, true, 9.0, 65.0, false, false, false)
    });
    assert!(
        state.outcome_text().contains("lets you off with a warning"),
        "{}",
        state.outcome_text()
    );
    assert_eq!(
        app.ctx.profile.as_ref().expect("a career").money,
        money_before
    );
    assert_eq!(with_drive(&drive, |d| d.speeding_tickets), 0);
}

#[test]
fn test_a_serious_stop_writes_the_ticket_once_and_charges_it_on_the_spot() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let money_before = {
        let profile = app.ctx.profile.as_mut().expect("a career");
        profile.career.reputation = 40.0;
        profile.money
    };
    let expected = enforcement::speeding_citation_fine(24.0, 0, false);
    let state = drive_and_ctx(&drive, &mut app, |d, ctx| {
        TrafficStopState::new(ctx, d, false, 24.0, 65.0, false, false, false)
    });
    assert!(
        state.outcome_text().contains("Speeding ticket:"),
        "{}",
        state.outcome_text()
    );
    assert_eq!(
        app.ctx.profile.as_ref().expect("a career").money,
        money_before - expected
    );
    assert_eq!(with_drive(&drive, |d| d.speeding_tickets), 1);
    assert_eq!(with_drive(&drive, |d| d.ticket_fines_paid), expected);
}

#[test]
fn test_a_work_zone_ticket_says_so_and_costs_double() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    app.ctx
        .profile
        .as_mut()
        .expect("a career")
        .career
        .reputation = 40.0;
    let plain = enforcement::speeding_citation_fine(24.0, 0, false);
    let zone = enforcement::speeding_citation_fine(24.0, 0, true);
    assert_eq!(zone, plain * enforcement::CONSTRUCTION_ZONE_FINE_MULTIPLIER);
    let state = drive_and_ctx(&drive, &mut app, |d, ctx| {
        TrafficStopState::new(ctx, d, false, 24.0, 65.0, false, false, true)
    });
    assert!(
        state
            .outcome_text()
            .contains(enforcement::construction_zone_fine_clause(true).trim()),
        "{}",
        state.outcome_text()
    );
    assert_eq!(with_drive(&drive, |d| d.ticket_fines_paid), zone);
}

#[test]
fn test_the_traffic_stop_offers_one_way_back_onto_the_highway() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let mut state = drive_and_ctx(&drive, &mut app, |d, ctx| {
        TrafficStopState::new(ctx, d, true, 9.0, 65.0, false, false, false)
    });
    let rows = build_labels(&mut state, &mut app.ctx);
    assert_eq!(rows, vec!["Pull back onto the highway"]);
    app.ctx
        .push_shared_with(freight_fate::app::share(state), false);
    app.clear_speech();
    with_top_ctx::<TrafficStopState, _>(&mut app, |stop, ctx| stop.go_back(ctx));
    assert_eq!(last(&app), "Back on the highway. Watch your speed.");
}

#[test]
fn test_a_pulled_licence_ends_the_run_from_the_shoulder() {
    // A stop that just pulled the licence cannot offer the highway: the
    // driver is not allowed to move the truck.
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    {
        let profile = app.ctx.profile.as_mut().expect("a career");
        profile.career.reputation = 40.0;
        profile.driving_record.lifetime_disqualified = true;
    }
    let mut state = drive_and_ctx(&drive, &mut app, |d, ctx| {
        TrafficStopState::new(ctx, d, false, 24.0, 65.0, false, false, false)
    });
    let rows = build_labels(&mut state, &mut app.ctx);
    assert_eq!(rows, vec!["Return to terminal"]);
    assert!(
        state.outcome_text().contains("You are released to"),
        "{}",
        state.outcome_text()
    );
}

#[test]
fn test_a_pulled_licence_names_the_load_dispatch_takes_back() {
    // The stop is resolved while the drive that pushed it is still held, so
    // the outcome has to be told from the drive it was handed rather than
    // reaching for the drive again. It used to reach, the second borrow
    // failed, and a loaded run was told there was no trailer to hand back.
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    {
        let profile = app.ctx.profile.as_mut().expect("a career");
        profile.career.reputation = 40.0;
        profile.driving_record.lifetime_disqualified = true;
    }
    let state = drive_and_ctx(&drive, &mut app, |d, ctx| {
        assert_eq!(d.phase, DRIVE_PHASE_DELIVERY, "a loaded delivery run");
        assert!(!d.job.bobtail, "with a trailer on");
        TrafficStopState::new(ctx, d, false, 24.0, 65.0, false, false, false)
    });
    let cargo = with_drive(&drive, |d| d.job.cargo.label.to_string());
    assert!(
        state
            .outcome_text()
            .contains(&format!("Dispatch takes the {cargo} load back")),
        "{}",
        state.outcome_text()
    );
    assert!(
        !state.outcome_text().contains("no loaded trailer"),
        "{}",
        state.outcome_text()
    );
}

#[test]
fn test_a_bobtail_pulled_licence_says_there_is_no_trailer() {
    // The other side of the same branch, so the fix cannot be "always say
    // there is a load".
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    with_drive(&drive, |d| d.job.bobtail = true);
    {
        let profile = app.ctx.profile.as_mut().expect("a career");
        profile.career.reputation = 40.0;
        profile.driving_record.lifetime_disqualified = true;
    }
    let state = drive_and_ctx(&drive, &mut app, |d, ctx| {
        TrafficStopState::new(ctx, d, false, 24.0, 65.0, false, false, false)
    });
    assert!(
        state
            .outcome_text()
            .contains("There is no loaded trailer to hand back"),
        "{}",
        state.outcome_text()
    );
}

// -- the enforcement stop ------------------------------------------------------------------

#[test]
fn test_an_enforcement_stop_charges_once_and_reads_back_as_history() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let money_before = app.ctx.profile.as_ref().expect("a career").money;
    let expected = enforcement::citation_fine(enforcement::LANE_MISUSE_FINE, 0, false, None);
    let mut state = drive_and_ctx(&drive, &mut app, |d, ctx| {
        EnforcementStopState::new(ctx, d, params("Lane misuse", false, false))
    });
    assert_eq!(
        app.ctx.profile.as_ref().expect("a career").money,
        money_before - expected
    );

    app.clear_speech();
    state.announce_entry(&mut app.ctx);
    let first = last(&app);
    assert!(
        first.starts_with("You stop on the shoulder for an enforcement inspection."),
        "{first}"
    );

    // Re-reading the stop must not sound like a second charge.
    app.clear_speech();
    state.announce_entry(&mut app.ctx);
    let second = last(&app);
    assert!(second.starts_with("Stop already settled."), "{second}");
    assert_eq!(
        app.ctx.profile.as_ref().expect("a career").money,
        money_before - expected,
        "the money moved exactly once"
    );
}

#[test]
fn test_an_out_of_service_order_passes_the_ten_hours_on_the_shoulder() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    // Past the 11-hour drive: that is a full reset, not a missed-break park.
    app.ctx
        .profile
        .as_mut()
        .expect("a career")
        .hos
        .drive(11.0 * 60.0 + 1.0);
    let before = with_drive(&drive, |d| d.trip.game_minutes);
    let state = drive_and_ctx(&drive, &mut app, |d, ctx| {
        EnforcementStopState::new(ctx, d, params("Hours violation", true, false))
    });
    assert!(
        state
            .outcome_text()
            .contains("Out of service: ten hours parked on the shoulder"),
        "{}",
        state.outcome_text()
    );
    assert_eq!(
        with_drive(&drive, |d| d.trip.game_minutes),
        before + hos::SLEEP_MIN
    );
    assert_eq!(
        app.ctx.profile.as_ref().expect("a career").hos.driving_min,
        0.0
    );
}

#[test]
fn test_a_missed_break_is_thirty_minutes_out_of_service() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    app.ctx.profile.as_mut().expect("a career").hos.drive(481.0);
    let before = with_drive(&drive, |d| d.trip.game_minutes);
    let state = drive_and_ctx(&drive, &mut app, |d, ctx| {
        EnforcementStopState::new(ctx, d, params("Hours violation", true, false))
    });
    assert!(
        state
            .outcome_text()
            .contains("Out of service: thirty minutes parked on the shoulder"),
        "{}",
        state.outcome_text()
    );
    assert!(
        !state.outcome_text().contains("ten hours"),
        "{}",
        state.outcome_text()
    );
    assert_eq!(
        with_drive(&drive, |d| d.trip.game_minutes),
        before + hos::BREAK_MIN
    );
    assert_eq!(
        app.ctx.profile.as_ref().expect("a career").hos.driving_min,
        481.0
    );
    assert_eq!(
        app.ctx
            .profile
            .as_ref()
            .expect("a career")
            .hos
            .since_break_min,
        0.0
    );
}

#[test]
fn test_a_scale_bypass_is_inspected_on_the_shoulder_instead() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let before = with_drive(&drive, |d| d.trip.game_minutes);
    let state = drive_and_ctx(&drive, &mut app, |d, ctx| {
        EnforcementStopState::new(ctx, d, params("Weigh station bypass", false, true))
    });
    assert!(
        state
            .outcome_text()
            .contains("full inspection runs here on the shoulder"),
        "{}",
        state.outcome_text()
    );
    assert!(with_drive(&drive, |d| d.trip.game_minutes) > before);
}

// -- the felony stop -------------------------------------------------------------------------

#[test]
fn test_the_felony_stop_cancels_the_load_and_releases_to_the_terminal() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let money_before = app.ctx.profile.as_ref().expect("a career").money;
    let damage_before = with_drive(&drive, |d| d.trip.truck.damage_pct);
    let mut state = drive_and_ctx(&drive, &mut app, |d, ctx| FelonyStopState::new(ctx, d));

    assert!(
        state.summary().contains("Troopers laid spike strips"),
        "{}",
        state.summary()
    );
    assert!(
        state.summary().contains("You are released back to"),
        "{}",
        state.summary()
    );
    assert!(app.ctx.profile.as_ref().expect("a career").money < money_before);
    assert!(
        with_drive(&drive, |d| d.trip.truck.damage_pct)
            >= damage_before + FAILURE_TO_STOP_DAMAGE_PCT - 0.001
    );
    assert!(with_drive(&drive, |d| d.trip.truck.parking_brake));
    assert!(app
        .ctx
        .profile
        .as_ref()
        .expect("a career")
        .active_trip
        .is_none());
    assert_eq!(with_drive(&drive, |d| d.failure_to_stop_count), 1);

    let rows = build_labels(&mut state, &mut app.ctx);
    assert_eq!(rows, vec!["Return to terminal"]);
}

#[test]
fn test_fleeing_a_stop_is_a_major_offense_on_the_licence() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let state = drive_and_ctx(&drive, &mut app, |d, ctx| FelonyStopState::new(ctx, d));
    assert!(
        state.summary().contains("a major offense on your CDL"),
        "{}",
        state.summary()
    );
    let record = &app.ctx.profile.as_ref().expect("a career").driving_record;
    assert!(record.suspended(app.ctx.profile.as_ref().expect("a career").game_hours));
    // The line is restated at settlement, so it goes on the trip record too.
    assert_eq!(with_drive(&drive, |d| d.record_events.len()), 1);
}
