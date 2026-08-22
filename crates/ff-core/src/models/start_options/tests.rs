//! Ported from `tests/test_career_start_options.py`: career start choices,
//! carrier benefits, and equipment semantics. The `Profile` cases run against
//! the career-side `FakeProfile` (its `StartProfile` impl mirrors the
//! `profile.py` fields); the business-settlement, job-board and app-shell
//! cases are ignored with the reason and their bodies say what they checked.

use super::*;
use crate::models::business_constants::{COMPANY_DRIVER, LEASED_OWNER_OPERATOR};
use crate::models::career::test_profile::FakeProfile;
use crate::models::trailer_yard::TrailerOwner;

#[test]
fn test_start_options_are_grounded_and_player_facing() {
    let options = all_start_options();
    let company = company_start_options();

    assert!(company.len() >= 3);
    assert_eq!(
        start_option(Some(DEFAULT_START_KEY)).carrier_name,
        "Northstar Freight Lines"
    );
    assert!(options
        .iter()
        .any(|option| option.mode == START_MODE_OWNER_OPERATOR));
    for option in options {
        assert!(!option.label.is_empty());
        assert!(!option.menu_summary.is_empty());
        assert!(!option.help_text.is_empty());
        if option.mode == START_MODE_COMPANY {
            assert!(option.company_pay.is_some());
            assert!(option.owned_trucks.is_empty());
            assert!(option.help_text.to_lowercase().contains("carrier"));
        } else {
            assert_eq!(option.mode, START_MODE_OWNER_OPERATOR);
            assert!(!option.owned_trucks.is_empty());
            assert!(option.starting_money > 0.0);
            assert!(option.help_text.contains("operating costs"));
        }
    }
}

#[test]
#[ignore = "needs models::business (company_driver_pay)"]
fn test_company_carrier_pay_plans_have_distinct_benefits() {
    // company_driver_pay on an 80-mile/600-dollar job pays more at
    // great_lakes_training than northstar; a 500-mile/500-dollar floor job
    // pays more at prairie_link; a 300-mile/3000-dollar job pays more at
    // summit_value. The plans themselves carry the knobs:
    let northstar = pay_plan_for_key(Some(DEFAULT_START_KEY));
    let training = pay_plan_for_key(Some("great_lakes_training"));
    let prairie = pay_plan_for_key(Some("prairie_link"));
    let summit = pay_plan_for_key(Some("summit_value"));
    assert!(training.stop_pay > northstar.stop_pay);
    assert!(prairie.min_per_mile > northstar.min_per_mile);
    assert!(summit.pay_share > northstar.pay_share);
    assert!(summit.on_time_bonus_share > northstar.on_time_bonus_share);
}

#[test]
#[ignore = "needs models::business (build_business_settlement)"]
fn test_carrier_key_changes_settlement_math() {
    // build_business_settlement(COMPANY_DRIVER, 80-mile job, on time, no
    // driver charges) nets more at great_lakes_training than northstar, and
    // carries no business charges.
    unimplemented!("needs build_business_settlement")
}

#[test]
#[ignore = "needs models::jobs (JobBoard._cargo_weight) and the world"]
fn test_carrier_key_can_bias_job_mix_weighting() {
    // JobBoard._cargo_weight(Kansas City, "grain") is higher for prairie_link
    // than northstar. The bonus it reads is here:
    assert!(
        start_option(Some("prairie_link")).cargo_weight_bonus_for("grain")
            > start_option(Some(DEFAULT_START_KEY)).cargo_weight_bonus_for("grain")
    );
}

#[test]
#[ignore = "needs models::jobs (JobBoard._destination_weight) and the world"]
fn test_company_carriers_have_distinct_dispatch_weighting() {
    // Short-lane ratio is higher for great_lakes_training, same-region ratio
    // higher for prairie_link, and summit_value weights a cap-distance lane up.
    // The dispatch profiles those read:
    assert!(
        start_option(Some("great_lakes_training"))
            .dispatch
            .short_haul_bias
            > 0.0
    );
    assert!(start_option(Some("prairie_link")).dispatch.regional_bias > 0.0);
    assert!(start_option(Some("summit_value")).dispatch.long_haul_bias > 0.0);
}

#[test]
#[ignore = "needs models::jobs (JobBoard._make_job) and the world"]
fn test_training_carrier_adds_modest_deadline_slack() {
    // The same 92-mile Chicago to Milwaukee job gets a later deadline_game_h
    // at great_lakes_training than at northstar.
    assert!(
        start_option(Some("great_lakes_training"))
            .dispatch
            .deadline_slack
            > 1.0
    );
}

#[test]
fn test_apply_company_start_keeps_assigned_equipment() {
    let mut p = FakeProfile::named("Company Choice");
    apply_start_option(&mut p, start_option(Some("great_lakes_training")));

    assert_eq!(p.carrier_name, "Great Lakes Training Transport");
    assert_eq!(p.carrier_key, "great_lakes_training");
    assert_eq!(p.start_mode, START_MODE_COMPANY);
    assert_eq!(p.business_status, COMPANY_DRIVER);
    assert!(p.owned_trucks.is_empty());
    assert!(p.visible_owned_trucks().is_empty());
    assert!(!p.owns_equipment());
}

#[test]
fn test_owner_operator_start_applies_owned_equipment_and_costs() {
    let mut p = FakeProfile::named("Owner Start");
    apply_start_option(&mut p, start_option(Some(OWNER_OPERATOR_START_KEY)));

    assert_eq!(p.start_mode, START_MODE_OWNER_OPERATOR);
    assert_eq!(p.business_status, LEASED_OWNER_OPERATOR);
    assert!(p.owns_equipment());
    assert_eq!(p.visible_owned_trucks(), vec!["rig".to_string()]);
    assert_eq!(p.active_trailer_programs(), vec!["dry_van".to_string()]);
    assert!((p.money - 18_000.0).abs() < 1e-9);
    // The truck is brand new, not a hand-me-down: full tank, no damage.
    assert!((p.truck_damage_pct() - 0.0).abs() < 1e-9);
    assert!((p.truck_fuel_gal() - p.truck_specs().fuel_tank_gal).abs() < 1e-9);
    // The start buys you equipment and costs, never progress: the career
    // begins at zero and climbs the same ladder as a company hire. It used
    // to open at level 18 with 35 deliveries and 42,000 miles behind it.
    assert_eq!(p.career.level(), 1);
    assert_eq!(p.career.deliveries, 0);
    assert_eq!(p.career.total_miles, 0.0);
    assert!(p.career.level() < 18); // the buy-in gate is still ahead
}

#[test]
#[ignore = "needs models::profile (_fresh_condition: nine condition dimensions)"]
fn test_owner_operator_start_truck_is_pristine_on_every_condition_dimension() {
    // The owner-operator buys a brand-new truck, so nothing starts worn:
    // truck_conditions["rig"] equals _fresh_condition(tank) on every key, and
    // the spoken-side properties read full tank, zero damage/tire/brake/
    // engine/grime/chain wear, all_season tires, no chains. The four-field
    // record the fake carries is pristine:
    let mut p = FakeProfile::named("Pristine Start");
    apply_start_option(&mut p, start_option(Some(OWNER_OPERATOR_START_KEY)));
    let tank = p.truck_specs().fuel_tank_gal;
    let record = &p.truck_conditions["rig"];
    assert_eq!(record.fuel_gal, tank);
    assert_eq!(record.damage_pct, 0.0);
    assert_eq!(record.tire_wear_pct, 0.0);
    assert_eq!(record.grime_pct, 0.0);
}

#[test]
fn test_owner_operator_start_text_describes_a_new_truck() {
    let option = start_option(Some(OWNER_OPERATOR_START_KEY));
    let blurb = format!("{} {}", option.menu_summary, option.help_text).to_lowercase();

    assert!(blurb.contains("brand-new"));
    assert!(!blurb.contains("starter tractor"));
    // The difficulty still has to come across: the costs and the thin cushion
    // are what make this the hardest start, not a worn-out truck.
    assert!(option.help_text.contains("operating costs"));
    assert!(blurb.contains("working capital"));
    assert!(blurb.contains("hardest"));
}

#[test]
#[ignore = "needs freight_fate::app (App, CareerStartState)"]
fn test_new_career_start_menu_lists_company_and_owner_operator() {
    // CareerStartState lists Northstar Freight Lines, Great Lakes Training
    // Transport and an "Owner-operator start" item; its intro help names
    // "assigned carrier equipment" and "higher risk".
    unimplemented!("needs the app shell")
}

#[test]
#[ignore = "needs freight_fate::app (App, CareerStartState, HomeCityState, CityMenuState)"]
fn test_new_company_career_choice_creates_company_profile() {
    // Choosing Prairie Link Regional creates a company-driver profile whose
    // first-day briefing names the carrier and "same-region lanes".
    unimplemented!("needs the app shell")
}

#[test]
#[ignore = "needs freight_fate::app (App, TruckShopState, UpgradeShopState)"]
fn test_owner_operator_start_unlocks_equipment_systems() {
    // The owner-operator start leaves a LEASED_OWNER_OPERATOR profile that
    // owns "rig"; the truck shop says "currently driving" and "buy for", and
    // the upgrade shop is not locked.
    unimplemented!("needs the app shell")
}

#[test]
#[ignore = "needs freight_fate::app (App, CityMenuState, first_day_orientation_message)"]
fn test_first_day_briefing_names_owner_operator_costs() {
    // The orientation names "leased to Northstar Freight Lines", "own a
    // brand-new truck", "working capital", "fuel, repairs, truck wear"; the
    // briefing item gives way to "Career plan" after the first dispatch.
    unimplemented!("needs the app shell")
}

// --- the catalogue, spoken ----------------------------------------------------------

#[test]
fn test_start_option_lookup_falls_back_to_northstar() {
    assert_eq!(start_option(None).key, DEFAULT_START_KEY);
    assert_eq!(start_option(Some("")).key, DEFAULT_START_KEY);
    assert_eq!(start_option(Some("no_such_carrier")).key, DEFAULT_START_KEY);
    assert_eq!(start_option(Some("summit_value")).default_city, "Denver");
    let keys: Vec<&str> = START_OPTIONS.iter().map(|o| o.key).collect();
    assert_eq!(
        keys,
        [
            "northstar",
            "great_lakes_training",
            "prairie_link",
            "summit_value",
            OWNER_OPERATOR_START_KEY
        ]
    );
    assert_eq!(
        pay_plan_for_key(Some(OWNER_OPERATOR_START_KEY)),
        NORTHSTAR_PAY
    );
}

#[test]
fn test_pay_plan_and_dispatch_summaries_are_spoken_plainly() {
    assert_eq!(
        NORTHSTAR_PAY.summary(),
        "36 percent pay share, 0.82 dollars per mile floor, 175 dollar stop pay, 4 percent on-time bonus"
    );
    assert_eq!(
        start_option(Some("great_lakes_training"))
            .dispatch
            .summary(),
        "more short training loads, more appointment slack"
    );
    assert_eq!(start_option(None).dispatch.summary(), "balanced dispatch");
    assert_eq!(DispatchProfile::default(), DispatchProfile::BALANCED);
}

#[test]
fn test_option_for_profile_recovers_an_old_save_from_its_carrier_name() {
    // A save from before carrier keys carries only the carrier's name.
    assert_eq!(
        option_for_carrier("", "Prairie Link Regional").key,
        "prairie_link"
    );
    assert_eq!(
        option_for_carrier("summit_value", "Anything").key,
        "summit_value"
    );
    assert_eq!(option_for_carrier("", "").key, DEFAULT_START_KEY);
    assert_eq!(
        option_for_carrier("", "Unknown Carrier").key,
        DEFAULT_START_KEY
    );
    let mut p = FakeProfile::named("Old Save");
    p.carrier_key = String::new();
    p.carrier_name = "Great Lakes Training Transport".to_string();
    assert_eq!(option_for_profile(&p).key, "great_lakes_training");
}
