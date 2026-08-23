//! The terminal's shops: business status, garage, trucks, upgrades, trailer
//! programs and endorsement courses. Ports of the app parts of
//! `tests/test_business_arc.py`, `tests/test_truck_dealer_menu.py`, the
//! garage cases of `tests/test_smoke.py`, and the truck-shop case of
//! `tests/test_save_migration.py`.

mod states_city_support;

use ff_core::models::business::{
    business_status_summary, has_authority_readiness, AUTHORITY_ACTIVATION_COST,
    AUTHORITY_ACTIVATION_DELIVERIES, AUTHORITY_ACTIVATION_LEVEL, AUTHORITY_ACTIVATION_REPUTATION,
    AUTHORITY_ACTIVATION_WORKING_CAPITAL, AUTHORITY_READY_DELIVERIES, AUTHORITY_READY_LEVEL,
    AUTHORITY_READY_REPUTATION, AUTHORITY_READY_RESERVE, AUTHORITY_READY_WORKING_CAPITAL,
    COMPANY_DRIVER, INDEPENDENT_AUTHORITY, LEASED_OWNER_OPERATOR, OWNER_OPERATOR_BUY_IN,
    OWNER_OPERATOR_DELIVERIES, OWNER_OPERATOR_LEVEL, OWNER_OPERATOR_REPUTATION,
    OWNER_OPERATOR_WORKING_CAPITAL, WEIGH_STATION_TRANSPONDER_SIGNUP_FEE,
};
use ff_core::models::career::LEVEL_XP;
use ff_core::models::carrier_fleet::assigned_truck_key;
use ff_core::models::profile::Profile;
use ff_core::models::trailers::{trailer_type, DEFAULT_TRAILER_PROGRAMS};
use ff_core::models::trucks::truck_model_or_panic;
use freight_fate::app::testing::TestApp;
use freight_fate::states::base::Key;
use freight_fate::states::city::{
    BusinessStatusState, CityMenuState, EndorsementCourseState, GarageState, TrailerProgramState,
    TruckShopState, UpgradeShopState,
};
use freight_fate::states::city_garage::{
    CHAIN_SET_COST, TIRE_SERVICE_COST_PER_PCT, WINTER_TIRE_PREMIUM,
};
use states_city_support::*;

fn approx(a: f64, b: f64) {
    assert!((a - b).abs() < 0.01, "{a} != {b}");
}

// -- tests/test_business_arc.py: business status --------------------------------------

#[test]
fn test_business_status_menu_unlocks_owner_operator_when_qualified() {
    let mut app = TestApp::new();
    career(&mut app, "Owner Path", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.career.xp = LEVEL_XP[(OWNER_OPERATOR_LEVEL - 1) as usize];
        p.career.deliveries = OWNER_OPERATOR_DELIVERIES;
        p.career.reputation = OWNER_OPERATOR_REPUTATION;
        p.money = OWNER_OPERATOR_BUY_IN + OWNER_OPERATOR_WORKING_CAPITAL + 500.0;
    }

    app.push_state(BusinessStatusState::new());
    let rows = labels::<BusinessStatusState>(&app);
    assert!(rows
        .iter()
        .any(|t| t.contains("Buy into leased-on owner-operator")));
    assert!(rows.iter().any(|t| t.contains("Carrier and rank")));
    assert!(rows.iter().any(|t| t.contains("Next business unlock")));
    select::<BusinessStatusState>(&mut app, "Buy into leased-on owner-operator");

    assert_eq!(profile(&app).business_status, LEASED_OWNER_OPERATOR);
    approx(
        profile(&app).money,
        OWNER_OPERATOR_WORKING_CAPITAL + 500.0,
    );
    assert!(profile(&app).dispatch_board_cache.is_none());
}

#[test]
fn test_owner_operator_buy_in_records_first_owned_tractor() {
    let mut app = TestApp::new();
    career(&mut app, "Buy In Equipment", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.career.xp = LEVEL_XP[(OWNER_OPERATOR_LEVEL - 1) as usize];
        p.career.deliveries = OWNER_OPERATOR_DELIVERIES;
        p.career.reputation = OWNER_OPERATOR_REPUTATION;
        p.money = OWNER_OPERATOR_BUY_IN + OWNER_OPERATOR_WORKING_CAPITAL;
    }

    app.push_state(BusinessStatusState::new());
    select::<BusinessStatusState>(&mut app, "Buy into leased-on owner-operator");

    assert_eq!(profile(&app).business_status, LEASED_OWNER_OPERATOR);
    // The buy-in takes over the tractor dispatch had you in: at the
    // level-18 gate that is a first-pick fleet unit, not the starter rig.
    let assigned = assigned_truck_key::<Profile, ff_core::models::carrier_fleet::NoJob>(
        profile(&app),
        None,
    );
    assert_eq!(profile(&app).truck, assigned);
    assert_eq!(profile(&app).visible_owned_trucks(), vec![assigned]);
    assert_eq!(
        profile(&app).active_trailer_programs(),
        DEFAULT_TRAILER_PROGRAMS
            .iter()
            .map(|s| s.to_string())
            .collect::<Vec<_>>()
    );
}

#[test]
fn test_business_status_menu_sets_authority_readiness_reserve() {
    let mut app = TestApp::new();
    career(&mut app, "Authority Ready", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.career.xp = LEVEL_XP[(AUTHORITY_READY_LEVEL - 1) as usize];
        p.career.deliveries = AUTHORITY_READY_DELIVERIES;
        p.career.reputation = AUTHORITY_READY_REPUTATION;
        p.money = AUTHORITY_READY_RESERVE + AUTHORITY_READY_WORKING_CAPITAL + 500.0;
        p.dispatch_board_cache = Some(serde_json::json!({"old": true}));
    }

    app.push_state(BusinessStatusState::new());
    select::<BusinessStatusState>(&mut app, "Commit 12,500 dollars to authority prep");

    assert!(has_authority_readiness(profile(&app)));
    approx(
        profile(&app).money,
        AUTHORITY_READY_WORKING_CAPITAL + 500.0,
    );
    assert!(profile(&app).dispatch_board_cache.is_none());
    assert!(business_status_summary(profile(&app)).contains("Authority prep reserve is set"));
    assert!(labels::<BusinessStatusState>(&app)
        .iter()
        .any(|t| t.contains("Authority prep reserve: set")));
}

#[test]
fn test_business_status_menu_activates_own_authority() {
    let mut app = TestApp::new();
    career(&mut app, "Own Authority", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.trailer_programs = vec!["dry_van".to_string(), "reefer".to_string()];
        p.authority_readiness = true;
        p.career.xp = LEVEL_XP[(AUTHORITY_ACTIVATION_LEVEL - 1) as usize];
        p.career.deliveries = AUTHORITY_ACTIVATION_DELIVERIES;
        p.career.reputation = AUTHORITY_ACTIVATION_REPUTATION;
        p.money = AUTHORITY_ACTIVATION_COST + AUTHORITY_ACTIVATION_WORKING_CAPITAL + 750.0;
        p.dispatch_board_cache = Some(serde_json::json!({"old": true}));
    }

    app.push_state(BusinessStatusState::new());
    select::<BusinessStatusState>(&mut app, "Activate own authority");

    assert_eq!(profile(&app).business_status, INDEPENDENT_AUTHORITY);
    approx(
        profile(&app).money,
        AUTHORITY_ACTIVATION_WORKING_CAPITAL + 750.0,
    );
    assert!(profile(&app).dispatch_board_cache.is_none());
    assert!(business_status_summary(profile(&app)).contains("Direct freight"));
    assert!(labels::<BusinessStatusState>(&app)
        .iter()
        .any(|t| t.contains("Own authority active")));
}

// --- the transponder row an owner-operator cannot afford yet -----------------
//
// It used to appear only once the fee was already in the bank, so the driver
// with most to gain from knowing the transponder exists was the one told
// nothing about it -- and the eligibility reasons were computed at that call
// site and discarded (owner, 2026-08-21).

fn owner_operator_in_business_menu(app: &mut TestApp, money: f64) {
    career(app, "Lease Op", "Chicago");
    {
        let p = profile_mut(app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.career.xp = LEVEL_XP[(OWNER_OPERATOR_LEVEL - 1) as usize];
        p.money = money;
    }
    app.push_state(BusinessStatusState::new());
}

#[test]
fn test_transponder_shows_as_locked_when_the_fee_is_out_of_reach() {
    let mut app = TestApp::new();
    owner_operator_in_business_menu(&mut app, WEIGH_STATION_TRANSPONDER_SIGNUP_FEE - 1.0);
    let rows = labels::<BusinessStatusState>(&app);
    assert!(
        rows.iter()
            .any(|t| t.contains("Weigh station transponder locked")),
        "no locked transponder row: {rows:?}"
    );
    assert!(!rows
        .iter()
        .any(|t| t.contains("Subscribe to weigh station transponder")));
}

#[test]
fn test_the_locked_transponder_row_says_what_it_is_waiting_on() {
    let mut app = TestApp::new();
    owner_operator_in_business_menu(&mut app, WEIGH_STATION_TRANSPONDER_SIGNUP_FEE - 1.0);
    app.clear_speech();
    activate::<BusinessStatusState>(&mut app, "Weigh station transponder locked");

    let spoken = app.main_lines();
    assert!(!spoken.is_empty(), "the locked row answered with silence");
    let said = spoken.last().unwrap();
    // The money reason, not the generic next-business-unlock answer: a
    // locked row that answers a different question teaches nothing.
    assert!(
        said.contains(&ff_core::pyfmt::fmt_grouped(
            WEIGH_STATION_TRANSPONDER_SIGNUP_FEE,
            0
        )),
        "{said}"
    );
}

#[test]
fn test_the_subscribe_row_returns_once_the_fee_is_affordable() {
    let mut app = TestApp::new();
    owner_operator_in_business_menu(&mut app, WEIGH_STATION_TRANSPONDER_SIGNUP_FEE + 1.0);
    let rows = labels::<BusinessStatusState>(&app);
    assert!(rows
        .iter()
        .any(|t| t.contains("Subscribe to weigh station transponder")));
    assert!(!rows
        .iter()
        .any(|t| t.contains("Weigh station transponder locked")));
}

// -- tests/test_business_arc.py: the garage -------------------------------------------

#[test]
fn test_company_driver_garage_service_is_carrier_billed() {
    let mut app = TestApp::new();
    career(&mut app, "Company Service", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = COMPANY_DRIVER.to_string();
        p.money = 25.0;
        p.set_truck_fuel_gal(0.0);
        p.set_truck_damage_pct(12.0);
    }
    app.push_state(GarageState::new());

    assert!(profile(&app).visible_owned_trucks().is_empty());
    let rows = labels::<GarageState>(&app);
    assert!(rows[0].contains("assigned company tractor"));
    assert!(rows[0].contains("carrier billed"));
    key(&mut app, Key::Return);
    approx(
        profile(&app).truck_fuel_gal(),
        profile(&app).truck_specs().fuel_tank_gal,
    );
    approx(profile(&app).money, 25.0);

    with_state_mut::<GarageState, _>(&mut app, |g, _| {
        freight_fate::states::base::Menu::menu_mut(g).index = 1
    });
    key(&mut app, Key::Return);
    approx(profile(&app).truck_damage_pct(), 0.0);
    approx(profile(&app).money, 25.0);
}

#[test]
fn test_garage_sells_the_traction_equipment_ladder() {
    let mut app = TestApp::new();
    career(&mut app, "Equipment", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.money = 20_000.0;
        p.set_tire_wear_pct(30.0);
    }
    app.push_state(GarageState::new());

    // Winter swap: a fresh set at the premium, compound on the record.
    with_state_mut::<GarageState, _>(&mut app, |g, ctx| g.swap_tire_compound(ctx));
    let winter_cost =
        ff_core::pyfmt::round_py_n(100.0 * TIRE_SERVICE_COST_PER_PCT * WINTER_TIRE_PREMIUM, 2);
    assert_eq!(profile(&app).tire_type(), "winter");
    assert_eq!(profile(&app).tire_wear_pct(), 0.0);
    approx(profile(&app).money, 20_000.0 - winter_cost);

    // Chains go in the side box for a flat set price.
    let money_before = profile(&app).money;
    with_state_mut::<GarageState, _>(&mut app, |g, ctx| g.buy_chains(ctx));
    assert!(profile(&app).chains_owned());
    assert_eq!(profile(&app).chain_wear_pct(), 0.0);
    approx(profile(&app).money, money_before - CHAIN_SET_COST);

    // A fresh set aboard is not sold twice.
    let money_before = profile(&app).money;
    with_state_mut::<GarageState, _>(&mut app, |g, ctx| g.buy_chains(ctx));
    approx(profile(&app).money, money_before);
}

#[test]
fn test_company_driver_gets_carrier_chains_but_carrier_rubber() {
    let mut app = TestApp::new();
    career(&mut app, "Company Equip", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = COMPANY_DRIVER.to_string();
        p.money = 50.0;
    }
    app.push_state(GarageState::new());

    // The carrier specs the rubber: no compound swap on the assigned rig.
    with_state_mut::<GarageState, _>(&mut app, |g, ctx| g.swap_tire_compound(ctx));
    assert_eq!(profile(&app).tire_type(), "all_season");
    approx(profile(&app).money, 50.0);

    // Chains are required equipment: carrier billed, never out of pocket.
    with_state_mut::<GarageState, _>(&mut app, |g, ctx| g.buy_chains(ctx));
    assert!(profile(&app).chains_owned());
    approx(profile(&app).money, 50.0);
}

// -- tests/test_smoke.py: the garage ---------------------------------------------------

#[test]
fn test_garage_offers_partial_fuel_and_repairs_when_cash_is_short() {
    let mut app = TestApp::new();
    career(&mut app, "Partial Garage", "Chicago");
    profile_mut(&mut app).business_status = LEASED_OWNER_OPERATOR.to_string();
    app.push_state(GarageState::new());

    {
        let p = profile_mut(&mut app);
        p.money = 100.0;
        p.set_truck_fuel_gal(0.0);
    }
    select::<GarageState>(&mut app, "Refuel");
    let tank = profile(&app).truck_specs().fuel_tank_gal;
    assert!(profile(&app).truck_fuel_gal() >= 1.0 && profile(&app).truck_fuel_gal() < tank);
    approx(profile(&app).money, 0.0);

    {
        let p = profile_mut(&mut app);
        p.money = 170.0;
        p.set_truck_damage_pct(10.0);
    }
    with_state_mut::<GarageState, _>(&mut app, |g, ctx| {
        freight_fate::states::base::Menu::refresh(g, ctx, true)
    });
    select::<GarageState>(&mut app, "Repair");
    // Repairs price on the damage-severity curve, so a short wallet buys
    // a little under the two percent the old flat rate would have sold.
    let damage = profile(&app).truck_damage_pct();
    assert!((8.0..8.5).contains(&damage), "{damage}");
    approx(profile(&app).money, 0.0);
}

#[test]
fn test_garage_services_tires_and_wash() {
    let mut app = TestApp::new();
    career(&mut app, "Maintenance", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.money = 1_000.0;
        p.set_tire_wear_pct(10.0);
        p.set_road_grime_pct(25.0);
    }
    app.push_state(GarageState::new());

    let rows = labels::<GarageState>(&app);
    assert!(rows.iter().any(|t| t.contains("Replace all-season tires")));
    assert!(rows.iter().any(|t| t.contains("Wash truck")));

    with_state_mut::<GarageState, _>(&mut app, |g, ctx| g.service_tires(ctx));
    assert_eq!(profile(&app).tire_wear_pct(), 0.0);
    assert_eq!(profile(&app).money, 550.0);

    with_state_mut::<GarageState, _>(&mut app, |g, ctx| g.wash_truck(ctx));
    assert_eq!(profile(&app).road_grime_pct(), 0.0);
    assert_eq!(profile(&app).money, 515.0);
}

#[test]
fn test_garage_services_brakes_and_engine() {
    let mut app = TestApp::new();
    career(&mut app, "Maintenance", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.money = 10_000.0;
        p.set_brake_wear_pct(20.0);
        p.set_engine_wear_pct(30.0);
    }
    app.push_state(GarageState::new());

    let rows = labels::<GarageState>(&app);
    assert!(rows.iter().any(|t| t.contains("Brake job")));
    assert!(rows.iter().any(|t| t.contains("Engine overhaul")));

    with_state_mut::<GarageState, _>(&mut app, |g, ctx| g.service_brakes(ctx));
    assert_eq!(profile(&app).brake_wear_pct(), 0.0);
    assert_eq!(profile(&app).money, 10_000.0 - 20.0 * 40.0);

    with_state_mut::<GarageState, _>(&mut app, |g, ctx| g.service_engine(ctx));
    assert_eq!(profile(&app).engine_wear_pct(), 0.0);
    assert_eq!(
        profile(&app).money,
        10_000.0 - 20.0 * 40.0 - 30.0 * 120.0
    );
}

#[test]
fn test_garage_partial_brake_service_when_broke() {
    let mut app = TestApp::new();
    career(&mut app, "Broke", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.money = 200.0; // 5 percent of brake service at 40 dollars per percent
        p.set_brake_wear_pct(50.0);
    }
    app.push_state(GarageState::new());

    with_state_mut::<GarageState, _>(&mut app, |g, ctx| g.service_brakes(ctx));
    approx(profile(&app).brake_wear_pct(), 45.0);
    approx(profile(&app).money, 0.0);
}

// -- tests/test_business_arc.py and test_smoke.py: trucks and upgrades ------------------

#[test]
fn test_company_driver_shops_hide_owned_truck_language() {
    let mut app = TestApp::new();
    career(&mut app, "No Ownership", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.owned_trucks = vec!["rig".to_string(), "heavy_hauler".to_string()]; // old save values stay hidden
        p.money = 200_000.0;
    }

    app.push_state(TruckShopState::new(false));
    assert!(labels::<TruckShopState>(&app)[0].contains("carrier-assigned tractor"));
    assert!(!labels::<TruckShopState>(&app)
        .iter()
        .any(|t| t.to_lowercase().contains("owned")));
    key(&mut app, Key::Return);
    assert_eq!(profile(&app).truck, "rig");
    approx(profile(&app).money, 200_000.0);
    assert!(app.main_lines().last().unwrap().contains("carrier-assigned"));

    app.pop_state();
    app.push_state(UpgradeShopState::new());
    assert!(labels::<UpgradeShopState>(&app)[0].contains("carrier-assigned tractor"));
    assert!(!labels::<UpgradeShopState>(&app)
        .iter()
        .any(|t| t.to_lowercase().contains("owned")));
    key(&mut app, Key::Return);
    assert!(profile(&app).upgrades.is_empty());
    approx(profile(&app).money, 200_000.0);
    assert!(app.main_lines().last().unwrap().contains("carrier-assigned"));
}

#[test]
fn test_owner_operator_can_buy_switch_and_upgrade_owned_equipment() {
    let mut app = TestApp::new();
    career(&mut app, "Owned Equipment", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.money = 200_000.0;
    }

    app.push_state(UpgradeShopState::new());
    key(&mut app, Key::Return);
    assert!(!profile(&app).upgrades.is_empty());
    assert!(profile(&app).money < 200_000.0);

    app.pop_state();
    let money_after_upgrade = profile(&app).money;
    app.push_state(TruckShopState::new(false));
    select::<TruckShopState>(&mut app, "Heavy hauler");
    assert_eq!(profile(&app).truck, "heavy_hauler");
    assert!(profile(&app)
        .visible_owned_trucks()
        .iter()
        .any(|k| k == "heavy_hauler"));
    approx(profile(&app).money, money_after_upgrade - 52_000.0);

    let money_before_switch = profile(&app).money;
    select::<TruckShopState>(&mut app, "Standard rig");
    assert_eq!(profile(&app).truck, "rig");
    approx(profile(&app).money, money_before_switch);
}

#[test]
fn test_upgrades_are_money_gated() {
    let mut app = TestApp::new();
    career(&mut app, "Broke", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.money = 10.0;
    }
    app.push_state(UpgradeShopState::new());
    key(&mut app, Key::Return);
    assert!(profile(&app).upgrades.is_empty());
    assert_eq!(profile(&app).money, 10.0);
}

#[test]
fn test_upgrade_f1_help_explains_player_benefits() {
    let mut app = TestApp::new();
    career(&mut app, "Helper", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
    }
    app.push_state(UpgradeShopState::new());
    let mut help_by_label = std::collections::HashMap::new();
    for (label, help) in labels_and_help::<UpgradeShopState>(&app) {
        let key = label
            .split(':')
            .next()
            .unwrap()
            .split(',')
            .next()
            .unwrap()
            .to_lowercase();
        help_by_label.insert(key, help.to_lowercase());
    }

    let engine = &help_by_label["engine tune"];
    assert!(engine.contains("more pulling power"));
    assert!(engine.contains("heavy freight"));
    let aero = &help_by_label["aerodynamic kit"];
    assert!(aero.contains("burn less fuel at highway speed"));
    assert!(aero.contains("same tank last longer"));
    let tank = &help_by_label["long-range tank"];
    assert!(tank.contains("fifty gallons"));
    assert!(tank.contains("carry more fuel"));
    assert!(tank.contains("more distance between fuel stops"));
    let brakes = &help_by_label["reinforced brakes"];
    assert!(brakes.contains("emergency stops"));
    assert!(brakes.contains("downhill control"));
}

#[test]
fn test_bought_truck_starts_fresh_and_each_keeps_its_own_condition() {
    let mut app = TestApp::new();
    career(&mut app, "Fleet Condition", "Chicago");
    {
        // Only an owner-operator buys or switches tractors; a company driver
        // sees a locked shop with nothing to pick.
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.money = 60_000.0;
        p.set_truck_fuel_gal(40.0);
        p.set_truck_damage_pct(30.0);
        p.set_tire_wear_pct(12.0);
        p.set_road_grime_pct(55.0);
    }
    app.push_state(TruckShopState::new(false));
    select::<TruckShopState>(&mut app, "Heavy hauler");

    assert_eq!(profile(&app).truck, "heavy_hauler");
    assert_eq!(
        profile(&app).truck_fuel_gal(),
        truck_model_or_panic("heavy_hauler").specs.fuel_tank_gal
    );
    assert_eq!(profile(&app).truck_damage_pct(), 0.0);
    assert_eq!(profile(&app).tire_wear_pct(), 0.0);
    // Grime belongs to the truck that earned it, so a tractor off the lot
    // is clean no matter how filthy the one it replaces was.
    assert_eq!(profile(&app).road_grime_pct(), 0.0);

    // The rig kept its own condition and gets it back on switch.
    select::<TruckShopState>(&mut app, "Standard rig");
    assert_eq!(profile(&app).truck, "rig");
    assert_eq!(profile(&app).truck_fuel_gal(), 40.0);
    assert_eq!(profile(&app).truck_damage_pct(), 30.0);
    assert_eq!(profile(&app).tire_wear_pct(), 12.0);
    // ...including the grime it was parked with.
    assert_eq!(profile(&app).road_grime_pct(), 55.0);

    let path = profile(&app).path();
    let loaded = Profile::load(&path).expect("the save reloads");
    assert_eq!(loaded.truck_conditions["rig"]["fuel_gal"], 40.0);
    assert_eq!(loaded.truck_conditions["rig"]["grime_pct"], 55.0);
    assert_eq!(loaded.truck_conditions["heavy_hauler"]["damage_pct"], 0.0);
    assert_eq!(loaded.truck_conditions["heavy_hauler"]["grime_pct"], 0.0);
}

// -- tests/test_truck_dealer_menu.py ---------------------------------------------------

#[test]
fn test_the_terminal_menu_offers_truck_dealer_directly() {
    let mut app = TestApp::new();
    career(&mut app, "Dale", "Buffalo");
    let mut menu = CityMenuState::new(&app.ctx, false);
    let rows = built_labels(&mut app, &mut menu);

    assert!(rows.iter().any(|t| t == "Truck dealer"));
    assert!(!rows.iter().any(|t| t == "Drive to city services"));
}

#[test]
fn test_the_truck_dealer_item_pushes_truck_shop_state() {
    let mut app = TestApp::new();
    career(&mut app, "Dale", "Buffalo");
    let city = CityMenuState::new(&app.ctx, false);
    app.push_state(city);
    activate::<CityMenuState>(&mut app, "Truck dealer");

    assert!(is::<TruckShopState>(&app));
}

#[test]
fn test_truck_shop_entry_names_the_source_backed_dealer() {
    // Opened from the terminal's "Truck dealer" row (at_dealer=True), the
    // entry names the source-backed dealer the player is actually standing in.
    let mut app = TestApp::new();
    career(&mut app, "Dale", "Indianapolis");
    let dealer = app
        .ctx
        .world
        .city_service("Indianapolis", "truck_dealer")
        .expect("Indianapolis has a dealer");
    assert!(!dealer.fallback);
    app.clear_speech();

    app.push_state(TruckShopState::new(true));

    let spoken = app.main_lines();
    assert!(spoken.iter().any(|line| line.contains(&dealer.name)));
    assert!(spoken
        .iter()
        .any(|line| line.starts_with(&format!("Inside {}. Trucks.", dealer.name))));
}

#[test]
fn test_truck_shop_entry_stays_plain_for_a_fallback_city() {
    let mut app = TestApp::new();
    career(&mut app, "Dale", "Erie");
    let dealer = app
        .ctx
        .world
        .city_service("Erie", "truck_dealer")
        .expect("Erie has a service row");
    assert!(dealer.fallback);
    app.clear_speech();

    app.push_state(TruckShopState::new(true));

    let spoken = app.main_lines();
    assert!(spoken.iter().any(|line| line.starts_with("Trucks. You have")));
    assert!(!spoken.iter().any(|line| line.contains("Inside")));
}

#[test]
fn test_truck_shop_entry_stays_plain_from_the_garage() {
    // Opened from the terminal garage's "Trucks" row (no at_dealer flag),
    // the entry never names the dealer -- even in a city with a real
    // source-backed one -- because the player is standing in the garage, not
    // the dealership, and naming it would contradict where they actually are.
    let mut app = TestApp::new();
    career(&mut app, "Dale", "Indianapolis");
    let dealer = app
        .ctx
        .world
        .city_service("Indianapolis", "truck_dealer")
        .expect("Indianapolis has a dealer");
    assert!(!dealer.fallback);

    app.push_state(GarageState::new());
    app.clear_speech();
    activate::<GarageState>(&mut app, "Trucks");

    assert!(is::<TruckShopState>(&app));
    assert!(!with_state::<TruckShopState, _>(&app, |s, _| s.at_dealer));
    let spoken = app.main_lines();
    assert!(!spoken.iter().any(|line| line.contains("Inside")));
    assert!(!spoken.iter().any(|line| line.contains(&dealer.name)));
}

// -- tests/test_business_arc.py: trailer programs --------------------------------------

#[test]
fn test_owner_operator_can_add_specialty_trailer_program() {
    let mut app = TestApp::new();
    career(&mut app, "Trailer Lease", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.money = 20_000.0;
    }

    app.push_state(TrailerProgramState::new());
    assert!(labels::<TrailerProgramState>(&app)[0].contains("Dry van: included carrier trailer program"));
    select::<TrailerProgramState>(&mut app, "Reefer");

    assert!(profile(&app)
        .active_trailer_programs()
        .iter()
        .any(|k| k == "reefer"));
    approx(profile(&app).money, 12_000.0);
    assert!(profile(&app).dispatch_board_cache.is_none());
}

#[test]
fn test_own_authority_can_buy_owned_trailer() {
    let mut app = TestApp::new();
    career(&mut app, "Trailer Owner", "Chicago");
    let reefer = trailer_type("reefer").unwrap();
    {
        let p = profile_mut(&mut app);
        p.business_status = INDEPENDENT_AUTHORITY.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.trailer_programs = vec!["dry_van".to_string(), "reefer".to_string()];
        p.money = reefer.purchase_price + 2_000.0;
        p.dispatch_board_cache = Some(serde_json::json!({"old": true}));
    }

    app.push_state(TrailerProgramState::new());
    move_to::<TrailerProgramState>(&mut app, "Reefer");
    assert!(current_label::<TrailerProgramState>(&app).contains("buy trailer"));
    key(&mut app, Key::Return);

    assert_eq!(profile(&app).visible_owned_trailers(), vec!["reefer"]);
    assert!(profile(&app)
        .active_trailer_programs()
        .iter()
        .any(|k| k == "reefer"));
    approx(profile(&app).money, 2_000.0);
    assert!(profile(&app).dispatch_board_cache.is_none());
    assert!(current_label::<TrailerProgramState>(&app).contains("owned trailer"));
}

#[test]
fn test_leased_on_owner_operator_does_not_see_trailer_purchase() {
    let mut app = TestApp::new();
    career(&mut app, "Leased Trailer", "Chicago");
    {
        let p = profile_mut(&mut app);
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.money = 200_000.0;
    }

    app.push_state(TrailerProgramState::new());

    let rows = labels::<TrailerProgramState>(&app);
    assert!(rows.iter().any(|t| t.contains("lease program")));
    assert!(!rows.iter().any(|t| t.contains("buy trailer")));
    assert!(profile(&app).visible_owned_trailers().is_empty());
}

#[test]
fn test_company_driver_trailer_program_menu_stays_carrier_provided() {
    let mut app = TestApp::new();
    career(&mut app, "Company Trailers", "Chicago");
    app.push_state(TrailerProgramState::new());

    let rows = labels::<TrailerProgramState>(&app);
    assert!(rows[0].contains("carrier-provided trailers"));
    assert!(!rows.iter().any(|t| t.contains("lease program for")));
}

// -- the endorsement course screen ------------------------------------------------------

#[test]
fn endorsement_courses_price_each_unearned_endorsement() {
    // No Python test of its own: the screen is exercised through the
    // terminal, and this pins the rows it offers a level-one driver.
    let mut app = TestApp::new();
    career(&mut app, "Course Buyer", "Chicago");
    profile_mut(&mut app).money = 50_000.0;
    app.push_state(EndorsementCourseState::new());

    let rows = labels::<EndorsementCourseState>(&app);
    assert!(rows
        .iter()
        .any(|t| t.starts_with("Refrigerated course:") && t.contains("carrier-sponsored free at level")));
    let before = profile(&app).money;
    select::<EndorsementCourseState>(&mut app, "Refrigerated course:");
    assert!(profile(&app).money < before);
    assert!(profile(&app)
        .career
        .purchased_endorsements
        .iter()
        .any(|k| k == "refrigerated"));
    assert!(labels::<EndorsementCourseState>(&app)
        .iter()
        .any(|t| t.contains("earned, self-paid course")));
}
