//! `states/driving_rest_states.rs` and `states/driving_pause_states.rs`: the
//! route stop and its fuel island, the loyalty desk, a full lot, the
//! emergency shoulder, the three roadside enforcement outcomes, and the
//! pause menu.
//!
//! Ported from `tests/test_road_services.py`, the rest-stop half of
//! `tests/test_pay_advance.py`, the menu half of
//! `tests/test_rest_stop_assist.py`, and the pause/resume cases of
//! `tests/test_trip_resume.py`.

mod states_driving_menus_support;

use ff_core::models::business::{COMPANY_DRIVER, LEASED_OWNER_OPERATOR};
use ff_core::models::economy::{PAY_ADVANCE_ELIGIBLE_BELOW, PAY_ADVANCE_LIMIT};
use ff_core::sim::hos;
use ff_core::sim::trip_models::RoadStop;

use freight_fate::app::testing::TestApp;
use freight_fate::states::base::Menu;
use freight_fate::states::driving_core::{
    ROAD_BRAKE_COST_PER_PCT, ROAD_TIRE_COST_PER_PCT, ROAD_TIRE_SPECIALIST_COST_PER_PCT,
};
use freight_fate::states::driving_menu_states::DriveRef;
use freight_fate::states::driving_pause_states::{
    AbandonJobConfirmationState, PauseMenuState, ASSIGNED_REPOSITION_ABANDON_REPUTATION_PENALTY,
};
use freight_fate::states::driving_rest_states::{
    LoyaltyRewardsState, ParkingFullState, RestStopState, ShoulderSleepConfirmationState,
};

use states_driving_menus_support::*;

/// `_driving(app, business_status)` from `test_road_services.py`.
fn a_wear_drive(app: &mut TestApp, business_status: &str) -> freight_fate::app::SharedState {
    let drive = a_drive_between(app, "Denver", "Salt Lake City", "Road Wear");
    let profile = app.ctx.profile.as_mut().expect("a career");
    profile.business_status = business_status.to_string();
    if business_status != COMPANY_DRIVER {
        profile.owned_trucks = vec!["rig".to_string()];
    }
    drive
}

fn rest_stop_at(
    app: &mut TestApp,
    drive: &freight_fate::app::SharedState,
    stop: RoadStop,
) -> RestStopState {
    let _ = app;
    RestStopState::with_drive(DriveRef::of(drive), stop, false)
}

// -- which shop offers what --------------------------------------------------------------

#[test]
fn test_tire_brand_offers_tires_but_not_brakes() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| {
        d.trip.truck.tire_wear_pct = 20.0;
        d.trip.truck.brake_wear_pct = 20.0;
        d.trip.position_mi
    });
    let mut state = rest_stop_at(&mut app, &drive, travel_center("Love's Travel Stop", at));
    let rows = build_labels(&mut state, &mut app.ctx);
    assert!(
        rows.iter().any(|l| l.starts_with("Replace tires")),
        "{rows:?}"
    );
    assert!(!rows.iter().any(|l| l.starts_with("Brake job")), "{rows:?}");
}

#[test]
fn test_full_service_brand_offers_brakes_and_marked_up_tires() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| {
        d.trip.truck.tire_wear_pct = 20.0;
        d.trip.truck.brake_wear_pct = 30.0;
        d.trip.position_mi
    });
    let mut state = rest_stop_at(
        &mut app,
        &drive,
        travel_center("TA Petro Travel Center", at),
    );
    let rows = build_labels(&mut state, &mut app.ctx);
    let tire_cost = 20.0 * ROAD_TIRE_COST_PER_PCT;
    let brake_cost = 30.0 * ROAD_BRAKE_COST_PER_PCT;
    assert!(
        rows.contains(&format!(
            "Replace tires: 20 percent wear for {} dollars",
            ff_core::pyfmt::fmt_grouped(tire_cost, 0)
        )),
        "{rows:?}"
    );
    assert!(
        rows.contains(&format!(
            "Brake job: 30 percent wear for {} dollars",
            ff_core::pyfmt::fmt_grouped(brake_cost, 0)
        )),
        "{rows:?}"
    );
}

#[test]
fn test_tire_specialist_beats_general_travel_center_price() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| {
        d.trip.truck.tire_wear_pct = 20.0;
        d.trip.position_mi
    });
    let mut specialist = rest_stop_at(&mut app, &drive, travel_center("Speedco Truck Service", at));
    let mut general = rest_stop_at(&mut app, &drive, travel_center("Pilot Travel Center", at));
    let cheap = 20.0 * ROAD_TIRE_SPECIALIST_COST_PER_PCT;
    let marked_up = 20.0 * ROAD_TIRE_COST_PER_PCT;
    assert!(
        build_labels(&mut specialist, &mut app.ctx).contains(&format!(
            "Replace tires: 20 percent wear for {} dollars",
            ff_core::pyfmt::fmt_grouped(cheap, 0)
        ))
    );
    assert!(build_labels(&mut general, &mut app.ctx).contains(&format!(
        "Replace tires: 20 percent wear for {} dollars",
        ff_core::pyfmt::fmt_grouped(marked_up, 0)
    )));
}

#[test]
fn test_generic_stop_and_big_bucks_offer_no_wear_service() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| {
        d.trip.truck.tire_wear_pct = 40.0;
        d.trip.truck.brake_wear_pct = 40.0;
        d.trip.position_mi
    });
    for name in ["Cactus Flats Truck Stop", "Big Buck's Travel Center"] {
        let mut state = rest_stop_at(&mut app, &drive, travel_center(name, at));
        let rows = build_labels(&mut state, &mut app.ctx);
        assert!(
            !rows.iter().any(|l| l.starts_with("Replace tires")),
            "{name}: {rows:?}"
        );
        assert!(
            !rows.iter().any(|l| l.starts_with("Brake job")),
            "{name}: {rows:?}"
        );
    }
}

// -- paying for the work -----------------------------------------------------------------

#[test]
fn test_road_tire_service_charges_and_clears_wear() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    app.ctx.profile.as_mut().expect("a career").money = 5_000.0;
    let (at, minutes_before) = with_drive(&drive, |d| {
        d.trip.truck.tire_wear_pct = 20.0;
        (d.trip.position_mi, d.trip.game_minutes)
    });
    let mut state = rest_stop_at(&mut app, &drive, travel_center("Love's Travel Stop", at));
    app.clear_speech();
    activate(&mut state, &mut app.ctx, "Replace tires");

    assert_eq!(with_drive(&drive, |d| d.trip.truck.tire_wear_pct), 0.0);
    let profile = app.ctx.profile.as_ref().expect("a career");
    // synced through store_truck_condition
    assert_eq!(profile.tire_wear_pct(), 0.0);
    assert!(
        (profile.money - (5_000.0 - 20.0 * ROAD_TIRE_SPECIALIST_COST_PER_PCT)).abs() < 0.01,
        "{}",
        profile.money
    );
    assert!(with_drive(&drive, |d| d.trip.game_minutes) > minutes_before);
    assert!(last(&app).contains("Tires replaced"), "{}", last(&app));
}

#[test]
fn test_road_brake_job_is_all_or_nothing_when_broke() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    app.ctx.profile.as_mut().expect("a career").money = 100.0;
    let at = with_drive(&drive, |d| {
        d.trip.truck.brake_wear_pct = 30.0;
        d.trip.position_mi
    });
    let mut state = rest_stop_at(&mut app, &drive, travel_center("Petro Stopping Center", at));
    app.clear_speech();
    activate(&mut state, &mut app.ctx, "Brake job");

    assert_eq!(with_drive(&drive, |d| d.trip.truck.brake_wear_pct), 30.0);
    assert_eq!(app.ctx.profile.as_ref().expect("a career").money, 100.0);
    assert!(last(&app).contains("cannot afford"), "{}", last(&app));
}

#[test]
fn test_company_driver_road_wear_service_is_carrier_billed() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, COMPANY_DRIVER);
    let money_before = app.ctx.profile.as_ref().expect("a career").money;
    let at = with_drive(&drive, |d| {
        d.trip.truck.brake_wear_pct = 30.0;
        d.trip.position_mi
    });
    let mut state = rest_stop_at(&mut app, &drive, travel_center("TA Travel Center", at));
    app.clear_speech();
    activate(&mut state, &mut app.ctx, "Brake job");

    assert_eq!(with_drive(&drive, |d| d.trip.truck.brake_wear_pct), 0.0);
    assert_eq!(
        app.ctx.profile.as_ref().expect("a career").money,
        money_before
    );
    assert!(last(&app).contains("carrier account"), "{}", last(&app));
}

#[test]
fn test_a_weigh_station_offers_no_bed_and_no_motel() {
    // Nobody sleeps in an active inspection facility, and there is no motel
    // on the far side of the platform. The scale menu was the generic
    // truck-stop template -- lot sleep, a 95 dollar motel room, a loyalty
    // readout -- at an open scale (owner playtest, 2026-08-20).
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| d.trip.position_mi);
    let mut scale = travel_center("I-24 Weigh Station", at);
    scale.stop_type = "weigh_station".to_string();
    scale.actions = Vec::new();
    let mut state = rest_stop_at(&mut app, &drive, scale);
    let rows = build_labels(&mut state, &mut app.ctx);
    assert!(!rows.iter().any(|l| l.contains("Sleep")), "{rows:?}");
    assert!(!rows.iter().any(|l| l.contains("Motel")), "{rows:?}");
    assert!(!rows.iter().any(|l| l.contains("Loyalty")), "{rows:?}");
}

#[test]
fn test_a_motel_bed_is_not_five_by_two() {
    // The badge is ten hours in the bunk; a motel room is the night you
    // specifically did not spend in it. Every sleep path used to award it
    // (owner report, 2026-08-20). The cramped-lot sleep keeps it -- the stop
    // has no beds, so a lot night is a bunk night.
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| d.trip.position_mi);
    let mut stop = travel_center("Roadside Stop", at);
    // no sleeper facility: motel and lot offered
    stop.actions = vec!["break".to_string()];
    let mut state = rest_stop_at(&mut app, &drive, stop);
    app.ctx.profile.as_mut().expect("a career").money = 10_000.0;

    // A tired driver beds down in the truck's own bunk in the lot: that
    // night counts (the guard refuses a fresh driver an emergency sleep).
    {
        let profile = app.ctx.profile.as_mut().expect("a career");
        profile.hos.drive(600.0);
        profile.fatigue = 80.0;
        profile.achievements.clear();
    }
    activate(&mut state, &mut app.ctx, "Sleep 10 hours in the lot");
    assert!(
        app.ctx
            .profile
            .as_ref()
            .expect("a career")
            .achievements
            .iter()
            .any(|id| id == "slept_on_route"),
        "the lot night is a bunk night"
    );

    // A day later, the motel night must not award it.
    {
        let profile = app.ctx.profile.as_mut().expect("a career");
        profile.hos.drive(600.0);
        profile.fatigue = 80.0;
        profile.achievements.retain(|id| id != "slept_on_route");
    }
    activate(&mut state, &mut app.ctx, "Motel room");
    assert!(
        !app.ctx
            .profile
            .as_ref()
            .expect("a career")
            .achievements
            .iter()
            .any(|id| id == "slept_on_route"),
        "a motel bed is the night you did not spend in the bunk"
    );
}

// -- the sleep guard ----------------------------------------------------------------------

#[test]
fn test_a_rested_driver_is_warned_once_before_a_pointless_sleep() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| d.trip.position_mi);
    let stop = sleep_stop(at);
    let mut state = rest_stop_at(&mut app, &drive, stop);
    {
        let profile = app.ctx.profile.as_mut().expect("a career");
        profile.fatigue = 0.0;
    }
    let before = with_drive(&drive, |d| d.trip.game_minutes);
    app.clear_speech();
    activate(&mut state, &mut app.ctx, "Sleep 10 hours");
    assert!(
        last(&app).starts_with("You are already rested"),
        "{}",
        last(&app)
    );
    assert_eq!(with_drive(&drive, |d| d.trip.game_minutes), before);

    // Pressing Enter again goes through. The sleep line is not necessarily
    // last: waking rested can earn a badge, which announces after it.
    app.clear_speech();
    activate(&mut state, &mut app.ctx, "Sleep 10 hours");
    assert!(with_drive(&drive, |d| d.trip.game_minutes) > before);
    let lines = app.main_lines();
    assert!(
        lines.iter().any(|line| line.contains("You slept 10 hours")),
        "{lines:?}"
    );
}

#[test]
fn test_moving_off_a_sleep_row_withdraws_the_pending_confirmation() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| d.trip.position_mi);
    let mut state = rest_stop_at(&mut app, &drive, sleep_stop(at));
    app.ctx.profile.as_mut().expect("a career").fatigue = 0.0;
    Menu::enter(&mut state, &mut app.ctx);
    activate(&mut state, &mut app.ctx, "Sleep 10 hours");
    let before = with_drive(&drive, |d| d.trip.game_minutes);
    // Arrowing away and back re-arms the warning rather than sleeping.
    state.move_by(&mut app.ctx, 1);
    app.clear_speech();
    activate(&mut state, &mut app.ctx, "Sleep 10 hours");
    assert!(
        last(&app).starts_with("You are already rested"),
        "{}",
        last(&app)
    );
    assert_eq!(with_drive(&drive, |d| d.trip.game_minutes), before);
}

#[test]
fn test_prefer_sleep_lands_the_cursor_on_the_first_sleep_row() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| d.trip.position_mi);
    let mut state = RestStopState::with_drive(DriveRef::of(&drive), sleep_stop(at), true);
    Menu::enter(&mut state, &mut app.ctx);
    let rows = labels(&state, &app.ctx);
    assert_eq!(rows[state.menu().index], "Sleep 2 hours in sleeper berth");
    for hours in [2, 3, 7, 8] {
        assert!(
            rows.contains(&format!("Sleep {hours} hours in sleeper berth")),
            "{rows:?}"
        );
    }
    assert!(rows.contains(&"Sleep 10 hours".to_string()), "{rows:?}");
}

// -- the loyalty desk ----------------------------------------------------------------------

#[test]
fn test_the_loyalty_row_opens_the_rewards_desk() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| d.trip.position_mi);
    let mut state = rest_stop_at(&mut app, &drive, travel_center("Love's Travel Stop", at));
    let rows = build_labels(&mut state, &mut app.ctx);
    assert!(rows[0].starts_with("Loyalty program"), "{rows:?}");
    activate(&mut state, &mut app.ctx, "Loyalty program");
    assert!(top_is::<LoyaltyRewardsState>(&app));
    let desk_rows = with_top_ctx::<LoyaltyRewardsState, _>(&mut app, build_labels);
    assert_eq!(
        desk_rows,
        vec![
            "No rewards available - need more points",
            "Back to truck stop",
        ]
    );
}

// -- the pay advance ------------------------------------------------------------------------

#[test]
fn test_rest_stop_pay_advance_option_only_appears_when_available() {
    let mut app = TestApp::new();
    let drive = a_drive_between(&mut app, "New York", "Philadelphia", "Advance Test");
    let at = with_drive(&drive, |d| d.trip.position_mi);
    let mut stop = RoadStop::new("Example Service Plaza", at + 10.0, "service_plaza");
    stop.actions = ["park", "save"].iter().map(|a| a.to_string()).collect();
    stop.services = vec!["parking".to_string()];
    let mut state = rest_stop_at(&mut app, &drive, stop);

    app.ctx.profile.as_mut().expect("a career").money = PAY_ADVANCE_ELIGIBLE_BELOW;
    assert!(!build_labels(&mut state, &mut app.ctx)
        .iter()
        .any(|t| t.starts_with("Request pay advance")));

    app.ctx.profile.as_mut().expect("a career").money = PAY_ADVANCE_ELIGIBLE_BELOW - 1.0;
    assert!(build_labels(&mut state, &mut app.ctx)
        .iter()
        .any(|t| t.starts_with("Request pay advance")));

    activate(&mut state, &mut app.ctx, "Request pay advance");
    assert!(
        app.ctx
            .profile
            .as_ref()
            .expect("a career")
            .pay_advance_used_for_load
    );
    assert!(!build_labels(&mut state, &mut app.ctx)
        .iter()
        .any(|t| t.starts_with("Request pay advance")));

    {
        let profile = app.ctx.profile.as_mut().expect("a career");
        profile.pay_advance_used_for_load = false;
        profile.pay_advance = PAY_ADVANCE_LIMIT;
    }
    assert!(!build_labels(&mut state, &mut app.ctx)
        .iter()
        .any(|t| t.starts_with("Request pay advance")));
}

// -- the full lot -----------------------------------------------------------------------------

#[test]
fn test_a_full_lot_still_offers_the_pumps_first() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| d.trip.position_mi);
    let mut state =
        ParkingFullState::with_drive(DriveRef::of(&drive), travel_center("Prairie Plaza", at));
    let rows = build_labels(&mut state, &mut app.ctx);
    assert!(
        rows[0].starts_with("Refuel ") || rows[0].starts_with("Fuel:"),
        "{rows:?}"
    );
    assert_eq!(rows[1], "Drive on to the next stop");
    assert!(rows[2].starts_with("Motel room:"), "{rows:?}");
    assert_eq!(rows[3], "Park on the shoulder and sleep");
}

#[test]
fn test_a_lot_with_no_pumps_leads_with_driving_on() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| d.trip.position_mi);
    let mut stop = travel_center("Prairie Plaza", at);
    stop.actions = vec!["park".to_string()];
    let mut state = ParkingFullState::with_drive(DriveRef::of(&drive), stop);
    let rows = build_labels(&mut state, &mut app.ctx);
    assert_eq!(rows[0], "Drive on to the next stop");
}

#[test]
fn test_the_shoulder_row_asks_before_it_sleeps() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| d.trip.position_mi);
    let mut state =
        ParkingFullState::with_drive(DriveRef::of(&drive), travel_center("Prairie Plaza", at));
    activate(&mut state, &mut app.ctx, "Park on the shoulder");
    assert!(top_is::<ShoulderSleepConfirmationState>(&app));
    let rows = with_top_ctx::<ShoulderSleepConfirmationState, _>(&mut app, |confirm, ctx| {
        build_labels(confirm, ctx)
    });
    assert_eq!(rows[0], "Cancel and keep looking for a safe stop");
    assert_eq!(rows[1], "Sleep on the shoulder anyway");
}

#[test]
fn test_shoulder_sleep_advances_ten_hours_and_resets_the_clock() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| {
        d.trip.truck.velocity_mps = 0.0;
        d.trip.position_mi
    });
    {
        let profile = app.ctx.profile.as_mut().expect("a career");
        profile.hos.drive(600.0);
        profile.fatigue = 90.0;
    }
    let before = with_drive(&drive, |d| d.trip.game_minutes);
    let mut state = ShoulderSleepConfirmationState::from_menu(
        DriveRef::of(&drive),
        "Nowhere to park.",
        Some(at),
    );
    app.clear_speech();
    activate(&mut state, &mut app.ctx, "Sleep on the shoulder anyway");

    assert_eq!(
        with_drive(&drive, |d| d.trip.game_minutes),
        before + hos::SLEEP_MIN
    );
    let profile = app.ctx.profile.as_ref().expect("a career");
    assert_eq!(profile.hos.driving_min, 0.0);
    // Poor rest: the shoulder floor, never fully fresh.
    assert_eq!(profile.fatigue, hos::FATIGUE_SHOULDER_FLOOR);
    assert!(
        last(&app).contains("You sleep poorly on the shoulder"),
        "{}",
        last(&app)
    );
}

// -- the pause menu -----------------------------------------------------------------------------

#[test]
fn test_pause_menu_lists_the_drive_controls() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let mut state = PauseMenuState::with_drive(DriveRef::of(&drive));
    let rows = build_labels(&mut state, &mut app.ctx);
    assert_eq!(rows[0], "Resume driving");
    for expected in [
        "Trip status",
        "Controls and help",
        "Learn game sounds",
        "Settings",
        "Drivers board",
        "Abandon job",
        "Quit to main menu",
    ] {
        assert!(
            rows.iter().any(|row| row == expected),
            "{expected:?} missing from {rows:?}"
        );
    }
}

#[test]
fn test_pausing_clears_the_queued_road_lines() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    with_drive(&drive, |d| {
        d.pending_ambient_events.push_back(
            freight_fate::states::driving_core::PendingAmbient::new("a line from a mile back"),
        );
        d.reverse_cue_active = true;
        d.air_cue_active = true;
        d.jake_cue_key = Some("engine/jake_1".to_string());
    });
    let mut state = PauseMenuState::with_drive(DriveRef::of(&drive));
    Menu::enter(&mut state, &mut app.ctx);
    with_drive(&drive, |d| {
        assert!(d.pending_ambient_events.is_empty());
        assert!(!d.reverse_cue_active);
        assert!(!d.air_cue_active);
        assert_eq!(d.jake_cue_key, None);
    });
}

#[test]
fn test_resuming_says_so_and_brings_the_facility_names_back() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let mut state = PauseMenuState::with_drive(DriveRef::of(&drive));
    Menu::enter(&mut state, &mut app.ctx);
    app.ctx
        .push_shared_with(freight_fate::app::share(state), false);
    app.clear_speech();
    with_top_ctx::<PauseMenuState, _>(&mut app, |pause, ctx| {
        activate(pause, ctx, "Resume driving")
    });
    assert_eq!(last(&app), "Resumed.");
    // The pause menu is off the stack; the drive is back on top.
    assert!(top_is::<freight_fate::states::driving::DrivingState>(&app));
}

#[test]
fn test_abandon_confirmation_lands_on_no() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let mut state = AbandonJobConfirmationState::new(DriveRef::of(&drive));
    let rows = build_labels(&mut state, &mut app.ctx);
    assert_eq!(rows[0], "No, keep driving");
    assert_eq!(rows[1], "Yes, abandon the job");
}

#[test]
fn test_abandoning_a_load_costs_five_hundred_and_reputation() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let (money_before, rep_before) = {
        let profile = app.ctx.profile.as_mut().expect("a career");
        profile.money = 4_000.0;
        (profile.money, profile.career.reputation)
    };
    let mut state = AbandonJobConfirmationState::new(DriveRef::of(&drive));
    app.clear_speech();
    activate(&mut state, &mut app.ctx, "Yes, abandon the job");
    let profile = app.ctx.profile.as_ref().expect("a career");
    assert_eq!(profile.money, money_before - 500.0);
    assert_eq!(profile.career.reputation, (rep_before - 5.0).max(0.0));
    assert!(profile.active_trip.is_none());
    assert!(last(&app).starts_with("Job abandoned."), "{}", last(&app));
}

#[test]
fn test_abandoning_an_assigned_reposition_costs_standing_not_money() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    with_drive(&drive, |d| {
        d.job.bobtail = true;
        d.job.assigned = true;
    });
    let (money_before, rep_before) = {
        let profile = app.ctx.profile.as_mut().expect("a career");
        profile.money = 4_000.0;
        (profile.money, profile.career.reputation)
    };
    let mut state = AbandonJobConfirmationState::new(DriveRef::of(&drive));
    app.clear_speech();
    activate(&mut state, &mut app.ctx, "Yes, abandon the job");
    let profile = app.ctx.profile.as_ref().expect("a career");
    assert_eq!(profile.money, money_before, "no fine on an empty run");
    assert_eq!(
        profile.career.reputation,
        (rep_before - ASSIGNED_REPOSITION_ABANDON_REPUTATION_PENALTY).max(0.0)
    );
    assert!(
        last(&app).starts_with("Dispatch assignment abandoned."),
        "{}",
        last(&app)
    );
}

// -- not portable without the harness --------------------------------------------------------

#[test]
#[ignore = "needs the playtest harness: the assist drives the truck into the menu"]
fn test_selected_stop_assist_reaches_full_stop_and_sleep_menu() {
    // T then X, 4,000 frames of the real loop, and the drive parks itself at
    // the stop: the rest menu opens on "Sleep 2 hours in sleeper berth", and
    // the spoken order is selected -> armed -> braking -> stopped -> the row.
}

#[test]
#[ignore = "needs the playtest harness: the overshoot path runs in _update_exit"]
fn test_overshoot_clears_assist_then_stopped_t_recovers() {
    // Blowing past the ramp clears the plan and the assist, and a stopped T
    // at the stop still opens the rest menu.
}

#[test]
#[ignore = "needs states::driving_updates fatigue frames to force the stop"]
fn test_three_missed_microsleeps_force_a_stop() {
    // Three drifted nods put the truck out of service on the shoulder.
}

#[test]
fn test_calling_the_mechanic_leaves_the_pause_menu_with_its_rows() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    with_drive(&drive, |d| d.trip.truck.damage_pct = 60.0);
    let mut state = PauseMenuState::with_drive(DriveRef::of(&drive));
    Menu::enter(&mut state, &mut app.ctx);
    assert!(!labels(&state, &app.ctx).is_empty());

    activate(&mut state, &mut app.ctx, "Call a roadside mechanic");

    let rows = labels(&state, &app.ctx);
    assert!(
        rows.iter().any(|row| row == "Resume driving"),
        "the pause menu lost its rows: {rows:?}"
    );
    assert!(
        rows.iter()
            .any(|row| row == "Call a roadside mechanic: not needed yet"),
        "the mechanic row did not re-read the repaired truck: {rows:?}"
    );
}

#[test]
fn test_hanging_chains_leaves_the_pause_menu_with_its_rows() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    {
        let profile = app.ctx.profile.as_mut().expect("a career");
        profile.set_chains_owned(true);
    }
    let mut state = PauseMenuState::with_drive(DriveRef::of(&drive));
    Menu::enter(&mut state, &mut app.ctx);
    assert!(labels(&state, &app.ctx)
        .iter()
        .any(|row| row.starts_with("Install snow chains")));

    activate(&mut state, &mut app.ctx, "Install snow chains");

    let rows = labels(&state, &app.ctx);
    assert!(
        rows.iter().any(|row| row == "Resume driving"),
        "the pause menu lost its rows: {rows:?}"
    );
    assert!(
        rows.iter().any(|row| row.starts_with("Remove snow chains")),
        "the chain row did not turn around: {rows:?}"
    );

    activate(&mut state, &mut app.ctx, "Remove snow chains");

    let rows = labels(&state, &app.ctx);
    assert!(
        rows.iter().any(|row| row == "Resume driving"),
        "the pause menu lost its rows: {rows:?}"
    );
    assert!(
        rows.iter()
            .any(|row| row.starts_with("Install snow chains")),
        "the chain row did not turn back: {rows:?}"
    );
}

// -- a rebuild that cannot reach the drive ----------------------------------------------------
//
// When a rebuild misses the drive, these screens used to show nothing at all,
// which the menu speaks as "No options available." A player who has only the
// speech is then standing in a screen that says it has no rows and no way off
// it, mid-drive. They keep what they were already showing instead: at worst
// one label is an action out of date, and any keypress recovers from that.
//
// `unreachable_drive` explains why the miss here is not the nested borrow
// itself.

#[test]
fn test_the_route_stop_keeps_its_rows_when_a_rebuild_misses_the_drive() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| d.trip.position_mi);
    let stop = travel_center("Pilot Travel Center", at);

    let mut state = rest_stop_at(&mut app, &drive, stop.clone());
    let showing = state.build_items(&mut app.ctx);
    assert!(!showing.is_empty());

    let mut stranded = RestStopState::with_drive(unreachable_drive(), stop, false);
    let rows = rows_with_the_drive_out_of_reach(&mut stranded, showing, &mut app.ctx);
    assert!(
        rows.iter().any(|row| row == "Back to the road"),
        "the route stop lost the row that leaves it: {rows:?}"
    );
}

#[test]
fn test_a_full_lot_keeps_its_rows_when_a_rebuild_misses_the_drive() {
    let mut app = TestApp::new();
    let drive = a_wear_drive(&mut app, LEASED_OWNER_OPERATOR);
    let at = with_drive(&drive, |d| d.trip.position_mi);
    let stop = travel_center("Prairie Plaza", at);

    let mut state = ParkingFullState::with_drive(DriveRef::of(&drive), stop.clone());
    let showing = state.build_items(&mut app.ctx);
    assert!(!showing.is_empty());

    let mut stranded = ParkingFullState::with_drive(unreachable_drive(), stop);
    let rows = rows_with_the_drive_out_of_reach(&mut stranded, showing, &mut app.ctx);
    assert!(
        rows.iter().any(|row| row == "Drive on to the next stop"),
        "the full lot lost the row that leaves it: {rows:?}"
    );
}

#[test]
fn test_the_pause_menu_keeps_its_rows_when_a_rebuild_misses_the_drive() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);

    let mut state = PauseMenuState::with_drive(DriveRef::of(&drive));
    let showing = state.build_items(&mut app.ctx);
    assert!(!showing.is_empty());

    let mut stranded = PauseMenuState::with_drive(unreachable_drive());
    let rows = rows_with_the_drive_out_of_reach(&mut stranded, showing, &mut app.ctx);
    assert!(
        rows.iter().any(|row| row == "Resume driving"),
        "the pause menu lost the row that returns to the wheel: {rows:?}"
    );
}
