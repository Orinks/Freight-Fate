mod states_driving_menus_support;
use ff_core::models::business::LEASED_OWNER_OPERATOR;
use ff_core::sim::trip_models::RoadStop;
use freight_fate::app::testing::TestApp;
use freight_fate::states::driving_menu_states::DriveRef;
use freight_fate::states::driving_rest_states::RestStopState;
use states_driving_menus_support::*;

#[test]
fn dbg_fuel() {
    let mut app = TestApp::new();
    let drive = a_drive_between(&mut app, "Denver", "Salt Lake City", "Buff Tester");
    app.ctx.profile.as_mut().unwrap().business_status = LEASED_OWNER_OPERATOR.to_string();
    with_drive(&drive, |d| d.trip.truck.fuel_gal = 40.0);
    let (f, cap) = with_drive(&drive, |d| (d.trip.truck.fuel_gal, d.trip.truck.specs.fuel_tank_gal));
    println!("fuel={f} cap={cap}");
    let at_mi = with_drive(&drive, |d| d.trip.position_mi);
    let mut stop = RoadStop::new("Pilot Travel Center", at_mi, "travel_center");
    stop.actions = vec!["fuel".into(), "break".into()];
    stop.parking = "limited".into();
    let dr = DriveRef::of(&drive);
    let probe = dr.with(&mut app.ctx, |d, _| d.trip.truck.fuel_gal);
    println!("PROBE {probe:?}");
    let mut state = RestStopState::with_drive(DriveRef::of(&drive), stop, false);
    for l in build_labels(&mut state, &mut app.ctx) { println!("ROW {l}"); }
}
