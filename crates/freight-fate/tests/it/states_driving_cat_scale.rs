//! Weighing on a CAT Scale at a truck stop: the row, the price, the reweigh,
//! who pays, and the ticket the driver hears.

use crate::states_driving_menus_support::*;
use ff_core::models::business::{COMPANY_DRIVER, LEASED_OWNER_OPERATOR};
use ff_core::sim::trip_models::RoadStop;
use ff_core::sim::vehicle::{KG_PER_LB, LEGAL_GVW_KG};
use freight_fate::app::testing::TestApp;
use freight_fate::app::SharedState;
use freight_fate::states::driving_menu_states::DriveRef;
use freight_fate::states::driving_rest_states::RestStopState;

fn scale_drive(app: &mut TestApp, business_status: &str) -> SharedState {
    let drive = a_drive_between(app, "Denver", "Salt Lake City", "Scale Tester");
    let p = app.ctx.profile.as_mut().expect("a career");
    p.business_status = business_status.to_string();
    if business_status != COMPANY_DRIVER {
        p.owned_trucks = vec!["rig".to_string()];
    }
    p.set_money(100.0);
    drive
}

fn stop_with(drive: &SharedState, services: &[&str]) -> RestStopState {
    let at_mi = with_drive(drive, |d| d.trip.position_mi);
    let mut stop = RoadStop::new("Pilot Travel Center", at_mi, "travel_center");
    stop.actions = ["park", "fuel", "food", "break"]
        .iter()
        .map(|a| a.to_string())
        .collect();
    stop.services = services.iter().map(|s| s.to_string()).collect();
    RestStopState::with_drive(DriveRef::of(drive), stop, false)
}

fn money(app: &TestApp) -> f64 {
    app.ctx.profile.as_ref().expect("a career").money()
}

#[test]
fn test_owner_operator_weighs_hears_the_ticket_then_reweighs_cheaper() {
    let mut app = TestApp::new();
    let drive = scale_drive(&mut app, LEASED_OWNER_OPERATOR);
    let mut state = stop_with(&drive, &["diesel", "scale"]);
    let minutes = with_drive(&drive, |d| d.trip.game_minutes);
    app.clear_speech();

    activate(
        &mut state,
        &mut app.ctx,
        "Weigh on the CAT Scale: 15 dollars and 25 cents",
    );

    assert!((money(&app) - 84.75).abs() < 1e-9, "{}", money(&app));
    assert!((with_drive(&drive, |d| d.trip.game_minutes) - minutes - 10.0).abs() < 1e-9);
    let said = app.main_lines().join(" ");
    for part in [
        "CAT Scale ticket. Steer axle ",
        " pounds. Drive axles ",
        " pounds. Trailer axles ",
        " pounds. Gross ",
        "Legal on every axle. 15 dollars and 25 cents. You have 85 dollars.",
    ] {
        assert!(said.contains(part), "{part:?} not in {said:?}");
    }

    activate(
        &mut state,
        &mut app.ctx,
        "Reweigh on the CAT Scale: 5 dollars and 25 cents",
    );
    assert!((money(&app) - 79.5).abs() < 1e-9, "{}", money(&app));
}

#[test]
fn test_company_driver_weighs_on_the_carrier() {
    let mut app = TestApp::new();
    let drive = scale_drive(&mut app, COMPANY_DRIVER);
    let mut state = stop_with(&drive, &["scale"]);
    app.clear_speech();

    activate(
        &mut state,
        &mut app.ctx,
        "Weigh on the CAT Scale, carrier billed",
    );

    assert_eq!(money(&app), 100.0);
    assert!(app
        .main_lines()
        .join(" ")
        .contains("Legal on every axle. Billed to the carrier."));
}

#[test]
fn test_an_overweight_load_shows_on_the_ticket() {
    let mut app = TestApp::new();
    let drive = scale_drive(&mut app, LEASED_OWNER_OPERATOR);
    with_drive(&drive, |d| {
        let t = &mut d.trip.truck;
        t.cargo_kg = LEGAL_GVW_KG - t.tare_kg() + 2_000.0 * KG_PER_LB;
    });
    let mut state = stop_with(&drive, &["scale"]);
    app.clear_speech();

    activate(&mut state, &mut app.ctx, "Weigh on the CAT Scale");

    let said = app.main_lines().join(" ");
    assert!(
        said.contains("Drive axles") && said.contains("pounds over the 34,000 pound limit"),
        "{said}"
    );
    assert!(
        said.contains("Gross 2,000 pounds over the 80,000 pound limit"),
        "{said}"
    );
}

#[test]
fn test_no_scale_no_row_and_short_money_is_refused() {
    let mut app = TestApp::new();
    let drive = scale_drive(&mut app, LEASED_OWNER_OPERATOR);
    let mut plain = stop_with(&drive, &["diesel"]);
    assert!(!build_labels(&mut plain, &mut app.ctx)
        .iter()
        .any(|label| label.contains("CAT Scale")));

    app.ctx.profile.as_mut().expect("a career").set_money(10.0);
    let mut state = stop_with(&drive, &["scale"]);
    app.clear_speech();
    activate(&mut state, &mut app.ctx, "Weigh on the CAT Scale");
    assert_eq!(money(&app), 10.0);
    assert_eq!(
        app.main_lines().last().map(String::as_str),
        Some("A weigh costs 15 dollars and 25 cents and you have 10 dollars.")
    );
}
