//! The agent server's `scenario` tool (`playtest::scenario`): any situation
//! for the sandbox career, applied in place, checked before anything moves.

use serde_json::{json, Map, Value};

use ff_core::models::business_constants::{COMPANY_DRIVER, LEASED_OWNER_OPERATOR};
use ff_core::models::profile::Profile;

use freight_fate::app::testing::TestApp;
use freight_fate::playtest::scenario::{apply, Scenario};

fn scenario(json: Value) -> Scenario {
    let Value::Object(args) = json else {
        panic!("an object")
    };
    Scenario::from_json(&args).expect("a valid scenario")
}

#[test]
fn test_a_scenario_creates_a_bench_career_and_sets_every_part_asked_for() {
    let mut app = TestApp::new();
    assert!(app.ctx.profile.is_none());
    let notes = apply(
        &mut app.ctx,
        &scenario(json!({
            "city": "Tonopah",
            "level": 5,
            "deliveries": 12,
            "money": 42_000,
            "reputation": 70,
            "business": "leased",
            "endorsements": ["hazmat"],
            "fuel_pct": 25,
            "damage_pct": 10,
            "rested": true,
            "market_seed": 99,
            "board_seed": 3,
            "settings": {"real_traffic": true, "time_scale": 1.0}
        })),
    )
    .expect("the scenario applies");
    let world = app.ctx.world;
    let p = app.ctx.profile.as_ref().expect("a career was created");
    assert_eq!(p.name, "Playtest");
    assert_eq!(p.current_city, world.resolve_city_key("Tonopah"));
    assert_eq!(p.career.level(), 5);
    assert_eq!(p.career.deliveries, 12);
    assert_eq!(p.money, 42_000.0);
    assert_eq!(p.career.reputation, 70.0);
    assert_eq!(p.business_status, LEASED_OWNER_OPERATOR);
    assert!(p.career.endorsements().contains("hazmat"));
    assert!(p.tutorial_done);
    assert_eq!(p.market.seed, 99);
    assert_eq!(app.ctx.dispatch_board_seed, Some(3));
    assert!(app.ctx.settings.real_traffic);
    assert_eq!(app.ctx.settings.time_scale, 1.0);
    let mut truck = ff_core::sim::vehicle::TruckState::new(p.truck_specs());
    p.load_truck_condition(&mut truck);
    assert!((truck.fuel_gal - truck.specs.fuel_tank_gal * 0.25).abs() < 0.01);
    assert_eq!(truck.damage_pct, 10.0);
    assert!(p.dispatch_board_cache.is_none());
    let said = notes.join(" ");
    assert!(said.contains("Level 5."), "{said}");
    assert!(said.contains("Fuel 25 percent."), "{said}");
    assert!(said.contains("real_traffic"), "{said}");
}

#[test]
fn test_a_move_with_a_load_in_progress_needs_clear_load() {
    let mut app = TestApp::new();
    let mut p = Profile::named_in("Loaded", "Chicago");
    p.active_trip = Some(Value::Object(Map::new()));
    app.ctx.profile = Some(p);
    let refused = apply(&mut app.ctx, &scenario(json!({"city": "Denver"})))
        .expect_err("a move over a live load is refused");
    assert!(refused.contains("clear_load"), "{refused}");
    let notes = apply(
        &mut app.ctx,
        &scenario(json!({"city": "Denver", "clear_load": true, "business": "company"})),
    )
    .expect("dropping the load first is allowed");
    let p = app.ctx.profile.as_ref().unwrap();
    assert!(p.active_trip.is_none());
    assert_eq!(p.current_city, app.ctx.world.resolve_city_key("Denver"));
    assert_eq!(p.business_status, COMPANY_DRIVER);
    assert!(notes.iter().any(|n| n.contains("dropped")), "{notes:?}");
}

#[test]
fn test_unknown_places_and_settings_are_refused_by_name() {
    let mut app = TestApp::new();
    let refused =
        apply(&mut app.ctx, &scenario(json!({"city": "Atlantis"}))).expect_err("no such city");
    assert!(refused.contains("Atlantis"), "{refused}");
    app.ctx.profile = Some(Profile::named_in("Settings", "Chicago"));
    let refused = apply(
        &mut app.ctx,
        &scenario(json!({"settings": {"warp_drive": true}})),
    )
    .expect_err("no such setting");
    assert!(refused.contains("warp_drive"), "{refused}");
}

#[test]
fn test_staging_leaves_the_title_screen_under_the_terminal_and_the_game_running() {
    // The first live scenario emptied the whole screen stack before pushing
    // the terminal, and an empty stack is how the loop knows the game is
    // over: the game quit on the frame it was staged (2026-09-12).
    let mut app = TestApp::new();
    let staged = scenario(json!({"city": "Tonopah", "level": 3, "business": "company"}));
    let mut depth: Option<(usize, bool)> = None;
    let mut text = String::new();
    app.run_with_player_input(Some(2), |input, _dt| {
        if depth.is_none() {
            text = input.stage_scenario(&staged).expect("the scenario stages");
            depth = Some(input.screen_depth());
        }
        true
    });
    assert_eq!(
        depth,
        Some((2, true)),
        "title screen, then the terminal, game running"
    );
    assert!(text.contains("Tonopah, Nevada terminal"), "{text}");
    assert!(text.contains("level 3"), "{text}");
}
