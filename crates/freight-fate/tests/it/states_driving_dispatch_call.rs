//! Driver-initiated offline dispatch calls from the pause menu.

use freight_fate::app::testing::TestApp;
use freight_fate::states::base::Menu;
use freight_fate::states::driving_core::{FIELD_REPAIR_DAMAGE_PCT, MECHANIC_WAIT_MIN};
use freight_fate::states::driving_dispatch_call::{
    dispatch_request, local_dispatch_response, DispatchCallState, CALL_DELAY, CALL_LOAD, CALL_ROAD,
    CALL_TRUCK,
};
use freight_fate::states::driving_menu_states::DriveRef;
use freight_fate::states::driving_pause_states::PauseMenuState;

use crate::states_driving_menus_support::*;

#[test]
fn test_call_dispatch_is_available_only_while_stopped() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let mut pause = PauseMenuState::with_drive(DriveRef::of(&drive));
    let stopped = build_labels(&mut pause, &mut app.ctx);
    assert!(
        stopped.iter().any(|row| row == "Call dispatch"),
        "{stopped:?}"
    );

    with_drive(&drive, |driving| {
        driving.trip.truck.velocity_mps = 20.0;
    });
    let moving = build_labels(&mut pause, &mut app.ctx);
    assert!(
        !moving.iter().any(|row| row == "Call dispatch"),
        "{moving:?}"
    );
}

#[test]
fn test_dispatch_call_menu_covers_the_supported_request_categories() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let mut call = DispatchCallState::new(DriveRef::of(&drive));
    let rows = build_labels(&mut call, &mut app.ctx);
    assert_eq!(
        rows,
        vec![
            "Report a delay",
            "Ask about hours",
            "Ask about the road ahead",
            "Report truck trouble",
            "Report load trouble",
        ]
    );
}

#[test]
fn test_local_dispatch_uses_a_valid_shared_request_and_repeatable_decision() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    drive_and_ctx(&drive, &mut app, |driving, ctx| {
        driving.trip.game_minutes = 60.0;
        let request = dispatch_request(driving, ctx, CALL_DELAY);
        assert!(request.validate().is_empty(), "{:?}", request.validate());
        assert_eq!(request.kind, CALL_DELAY);
        assert_eq!(request.source_game, "freight_fate");
        assert!(request.context.contains_key("remaining_miles"));

        let first = local_dispatch_response(&request, driving, ctx);
        let second = local_dispatch_response(&request, driving, ctx);
        assert!(first.validate().is_empty(), "{:?}", first.validate());
        assert_eq!(first.decision, second.decision);
        assert_eq!(first.message, second.message);
        assert_eq!(first.effects, second.effects);
    });
}

#[test]
fn test_hours_call_answers_on_the_menu_speech_channel() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let mut call = DispatchCallState::new(DriveRef::of(&drive));
    Menu::enter(&mut call, &mut app.ctx);
    app.clear_speech();
    activate(&mut call, &mut app.ctx, "Ask about hours");
    assert!(last(&app).starts_with("Dispatch:"), "{}", last(&app));
    assert!(last(&app).contains("next limit"), "{}", last(&app));
}

#[test]
fn test_dispatch_authorizes_and_applies_a_needed_roadside_repair() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    let before = with_drive(&drive, |driving| {
        driving.trip.truck.damage_pct = 60.0;
        driving.trip.game_minutes
    });
    let mut call = DispatchCallState::new(DriveRef::of(&drive));
    app.clear_speech();
    activate(&mut call, &mut app.ctx, "Report truck trouble");

    with_drive(&drive, |driving| {
        assert_eq!(driving.trip.truck.damage_pct, FIELD_REPAIR_DAMAGE_PCT);
        assert_eq!(driving.trip.game_minutes, before + MECHANIC_WAIT_MIN);
    });
    assert!(
        last(&app).contains("Roadside repair is authorized"),
        "{}",
        last(&app)
    );
    assert!(
        last(&app).contains("mobile mechanic patched the truck"),
        "{}",
        last(&app)
    );
}

#[test]
fn test_load_call_reports_cargo_damage_not_condition() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    drive_and_ctx(&drive, &mut app, |driving, ctx| {
        driving.trip.truck.cargo_damage_pct = 12.4;
        let request = dispatch_request(driving, ctx, CALL_LOAD);
        assert_eq!(request.summary, "Cargo damage is 12 percent.");
        let response = local_dispatch_response(&request, driving, ctx);
        assert!(
            response.message.contains(", 12 percent damaged."),
            "{}",
            response.message
        );
        assert!(
            !response.message.contains("condition"),
            "{}",
            response.message
        );
    });
}

#[test]
fn test_request_summaries_round_hours_miles_and_damage() {
    let mut app = TestApp::new();
    let drive = a_drive(&mut app);
    drive_and_ctx(&drive, &mut app, |driving, ctx| {
        driving.trip.game_minutes = 100.0;
        driving.job.deadline_game_h = 7.0;
        driving.trip.truck.damage_pct = 33.333;
        let delay = dispatch_request(driving, ctx, CALL_DELAY).summary;
        assert_eq!(delay, "1.7 hours used of a 7.0 hour delivery window.");

        let road = dispatch_request(driving, ctx, CALL_ROAD).summary;
        let miles = road.strip_suffix(" miles remain.").expect(&road);
        let (_, decimals) = miles.split_once('.').expect(&road);
        assert_eq!(decimals.len(), 1, "{road}");

        let truck = dispatch_request(driving, ctx, CALL_TRUCK).summary;
        assert_eq!(truck, "Truck damage is 33 percent.");
    });
}
