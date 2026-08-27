//! The spoken manual: the drive's F1 keyboard and controller help
//! (`states/driving_controls/help.rs`), the main menu's How to play pages
//! (`states/main_menu_help.rs`), and the line the dispatch board must NOT
//! carry (`states/city/board.rs`).
//!
//! Ported from `tests/test_driving_features.py`:
//! `test_driving_help_explains_selected_automatic_direction_style`,
//! `test_driving_f1_describes_safe_shutdown_and_destination_parking`,
//! `test_how_to_play_documents_new_gameplay_systems` and
//! `test_dispatch_board_keeps_route_planning_out_of_load_offer`.

use ff_core::data::world::get_world;
use ff_core::models::jobs::{JobBoard, OfferOptions};
use ff_core::models::profile::Profile;
use ff_core::sim::weather::WeatherKind;

use freight_fate::app::testing::TestApp;
use freight_fate::playtest::harness::{key_event, PlaytestHarness, StartDelivery};
use freight_fate::states::base::{Key, Menu};
use freight_fate::states::city::JobBoardState;
use freight_fate::states::city_pickup::route_planning_summary;
use freight_fate::states::main_menu::HELP_PAGES;

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

/// Everything the last help call put on the main channel, joined -- the help
/// is spoken as one long block and Python read it as `spoken[-1]`.
fn last_help(harness: &PlaytestHarness) -> String {
    harness.app.main_lines().last().cloned().unwrap_or_default()
}

// -- the drive's own help ---------------------------------------------------------------

#[test]
fn test_driving_help_explains_selected_automatic_direction_style() {
    let mut harness = a_drive("Direction Help");

    harness.app.ctx.settings.automatic_direction_changes = "simple".to_string();
    harness.clear_speech();
    harness.with_drive(|drive, ctx| drive.speak_keyboard_help(ctx));
    let said = last_help(&harness);
    assert!(said.contains("simple direction changes"), "{said}");
    assert!(said.contains("press and hold it again"), "{said}");
    assert!(said.contains("holds the truck"), "{said}");
    assert!(
        said.contains("R progress, distance left, and where you are"),
        "{said}"
    );
    assert!(
        said.contains("T plans the next nearby sleep-capable stop while rolling"),
        "{said}"
    );
    assert!(
        said.contains("Fully stopped away from route points"),
        "{said}"
    );
    assert!(said.contains("emergency shoulder-sleep warning"), "{said}");

    harness.app.ctx.settings.automatic_direction_changes = "deliberate".to_string();
    harness.clear_speech();
    harness.with_drive(|drive, ctx| drive.speak_keyboard_help(ctx));
    let said = last_help(&harness);
    assert!(said.contains("deliberate direction changes"), "{said}");
    assert!(said.contains("press and hold it again"), "{said}");
    assert!(said.contains("A quick tap just brakes"), "{said}");

    harness.app.ctx.settings.automatic_direction_changes = "simple".to_string();
    harness.clear_speech();
    harness.with_drive(|drive, ctx| drive.speak_controller_help(ctx));
    let said = last_help(&harness);
    assert!(said.contains("simple direction changes"), "{said}");
    assert!(said.contains("press and hold it again"), "{said}");
    assert!(
        said.contains("D-pad up reads your route and current location"),
        "{said}"
    );
    assert!(
        said.contains("plans a nearby sleep stop while rolling"),
        "{said}"
    );
    assert!(
        said.contains("away from route points while fully stopped"),
        "{said}"
    );
    assert!(said.contains("opens emergency shoulder sleep"), "{said}");

    harness.app.ctx.settings.automatic_direction_changes = "deliberate".to_string();
    harness.clear_speech();
    harness.with_drive(|drive, ctx| drive.speak_controller_help(ctx));
    let said = last_help(&harness);
    assert!(said.contains("deliberate direction changes"), "{said}");
    assert!(
        said.contains("let the left trigger return to neutral"),
        "{said}"
    );
}

#[test]
fn test_driving_f1_describes_safe_shutdown_and_destination_parking() {
    let mut harness = a_drive("F1 Help");
    harness.clear_speech();

    harness.with_drive(|drive, ctx| drive.handle_key_event(ctx, &key_event(Key::F1, None)));

    let help_text = last_help(&harness);
    assert!(
        help_text.contains("stops it only below 5 miles per hour"),
        "{help_text}"
    );
    assert!(
        help_text.contains("stop, then dock and deliver"),
        "{help_text}"
    );
    assert!(
        help_text.contains("Left or Right Control stops the driving event voice"),
        "{help_text}"
    );
}

#[test]
fn test_hos_help_distinguishes_the_driving_clocks_and_delivery_deadline() {
    let mut harness = a_drive("HOS Help");
    harness.with_drive(|drive, ctx| drive.speak_keyboard_help(ctx));
    let driving_help = last_help(&harness);
    assert!(driving_help.contains("delivery deadline"), "{driving_help}");
    assert!(driving_help.contains("driving allowance"), "{driving_help}");
    assert!(
        driving_help.contains("legal driving cutoff"),
        "{driving_help}"
    );

    let hours_help = HELP_PAGES
        .iter()
        .find(|(title, _)| *title == "Hours and rest")
        .expect("hours help page")
        .1
        .join(" ");
    assert!(hours_help.contains("fourteen hour driving window"));
    assert!(hours_help.contains("Driving allowance decreases only while moving"));
    assert!(hours_help.contains("loading, fueling, inspections"));
    assert!(hours_help.contains("separate delivery deadline"));
    assert!(!hours_help.contains("duty window"));
}

// -- the manual --------------------------------------------------------------------------

#[test]
fn test_how_to_play_documents_new_gameplay_systems() {
    let help_text: String = HELP_PAGES
        .iter()
        .flat_map(|(_title, lines)| lines.iter())
        .cloned()
        .collect::<Vec<_>>()
        .join(" ")
        .to_lowercase();

    for phrase in [
        "air brakes need pressure",
        "wait for air pressure to reach 100 psi",
        "press p to release or set the parking brake",
        "low air",
        "tab opens a driving status menu",
        "driver apps",
        "slow below 5 miles per hour",
        "destination facility",
        "local deadhead moves to the origin facility",
        "company terminal or yard",
        "pickup gate",
        "loading requires the truck to be stopped",
        "loaded and sealed",
        "company drivers depart on dispatch's assigned route",
        "pick from the route options",
        "real highway corridors",
        "gps announces state lines",
        "grades and terrain come from the route",
        "weather, traffic, and construction still vary",
        "rush hours can make metro corridors busier",
        "slow lead vehicles",
        "settings are grouped into categories",
        "open a category to see its settings",
        "driving mode changes trip pacing and pressure",
        "relaxed gives more time to respond, wider hazard windows",
        "standard keeps balanced timing and consequences",
        "real time keeps standard's pressure and runs the driving clock",
        "changed mid-drive from the pause menu",
        "real violations keep their normal consequences",
        "adaptive cruise",
        "three second clear-weather gap",
        "increase the following gap",
        "keypad keys",
        "active speed-control mode",
        "open-road target",
        "sharp posted-limit drops",
        "highway stops use clear place names",
        "list the actions available there",
        "call for help",
        "tolls and approved company charges",
        "fines an earlier load could not cover",
        // The removed silent charge must not creep back into the help either.
        "speeding nobody saw costs nothing at all",
        "already paid on",
        "gross pay, carrier-paid or reimbursed charges",
        "net driver pay",
        "touch the brakes to cancel",
        "save",
        "dock and deliver",
        "wider freight area with many possible shippers",
        "rail and intermodal ramps",
        "parcel hubs",
        "farms and grain elevators",
        "chemical terminals",
        "not every market supports every cargo equally",
        "major freight areas instead of every town",
        "routes with enough stops",
        // The tank endorsement is level 16 and buyable, so it is listed too.
        "refrigerated, heavy-haul, high-value, and liquid bulk freight",
        "full tank or full repair",
        "engine tune gives more pulling power",
        "aerodynamic kit burns less fuel",
        "same tank, fewer gallons per mile",
        "long-range tank carries fifty more gallons",
        "more fuel onboard, not better efficiency",
        "emergency stops",
        "emergency shoulder sleep",
        "parking ticket or minor damage",
        // Always-available sleep, and the 1.8.0 systems, are documented in-game.
        "sleep 10 hours in the lot",
        "fully-rested ten-hour sleep",
        "risks losing traction",
        "low visibility shortens",
        "career runs on a calendar that starts in spring",
        "enforcement posts sit along the road",
        // The graded observation, and the tactic it gives back.
        "five over is seen and",
        "running in a pack",
        "cb chatter passes on what other drivers have seen",
        "never claims the road is clear",
        "review that chatter",
        // The presence control has to promise, in the help, what it does not do.
        "enforcement presence control",
        "getting caught is",
        // The speed keeper takes low-speed local roads and hands back to cruise.
        "speed keeper handles low-speed local roads",
        "in-cab radio",
        "streamer-safe status",
        "receivable stations",
    ] {
        assert!(
            help_text.contains(phrase),
            "How to play never says {phrase:?}"
        );
    }
}

// -- the dispatch board --------------------------------------------------------------------

#[test]
fn test_dispatch_board_keeps_route_planning_out_of_load_offer() {
    let mut app = TestApp::new();
    app.ctx.profile = Some(Profile::named_in("Dispatch Test", "New York"));
    let world = get_world();
    let mut board = JobBoard::new(world, Some(2), None);
    let jobs = board.offers(
        "New York",
        &["refrigerated", "heavy_haul", "high_value"],
        OfferOptions::level(5),
    );
    assert!(!jobs.is_empty());
    let mut state = JobBoardState::new(&app.ctx, jobs);
    let items = state.build_items(&mut app.ctx);
    let rows: Vec<String> = items
        .iter()
        .map(|item| item.text(&state, &app.ctx))
        .collect();

    assert!(
        rows.iter().any(|row| row.contains("Equipment:")),
        "{rows:#?}"
    );
    assert!(
        rows.iter().all(|row| !row.contains("Legal HOS plan")),
        "{rows:#?}"
    );
    assert!(
        rows.iter().all(|row| !row.contains("Route has")),
        "{rows:#?}"
    );
    assert!(
        rows.iter().all(|row| !row.contains("Fuel-capable stops")),
        "{rows:#?}"
    );
    let first_help = items[0].help_text(&state, &app.ctx);
    assert!(
        first_help.contains("Route inspection after pickup covers rest, fuel, toll"),
        "{first_help}"
    );

    let toll_route = world
        .route_from_cities(&["New York", "Philadelphia"])
        .expect("New York to Philadelphia is a route");
    let summary = route_planning_summary(&toll_route);
    assert!(summary.contains("Legal HOS plan"), "{summary}");
    assert!(summary.contains("Fuel-capable stops:"), "{summary}");
    assert!(
        summary.contains("Estimated carrier-paid toll exposure"),
        "{summary}"
    );
    assert!(summary.contains("not a guaranteed open space"), "{summary}");
}
