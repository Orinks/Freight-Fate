//! Ported from `tests/test_dispatch_policy.py`: dispatch autonomy bands,
//! assigned freight is earned away with seniority. The `Profile(...)` of the
//! Python tests is the career-side `FakeProfile`.

use super::*;
use crate::models::business_constants::{INDEPENDENT_AUTHORITY, LEASED_OWNER_OPERATOR};
use crate::models::career::test_profile::FakeProfile;
use crate::models::career::{Career, LEVEL_XP};

fn company_profile(level: usize) -> FakeProfile {
    let mut profile = FakeProfile::named("Policy Band");
    profile.career.xp = LEVEL_XP[level - 1];
    assert_eq!(profile.career.level(), level as i64);
    profile
}

#[test]
fn test_new_hire_company_driver_is_assigned_load_and_route() {
    let policy = dispatch_policy(&company_profile(1));

    assert!(policy.assigns_load);
    assert!(policy.assigns_route);
    assert!(policy.decline_budget > 0);
}

#[test]
fn test_last_new_hire_level_is_still_assigned_loads() {
    let policy = dispatch_policy(&company_profile((SENIOR_LOAD_CHOICE_LEVEL - 1) as usize));

    assert!(policy.assigns_load);
    assert!(policy.assigns_route);
}

#[test]
fn test_senior_company_driver_chooses_load_but_runs_assigned_route() {
    let policy = dispatch_policy(&company_profile(SENIOR_LOAD_CHOICE_LEVEL as usize));

    assert!(!policy.assigns_load);
    assert!(policy.assigns_route);
}

#[test]
fn test_leased_owner_operator_chooses_load_and_route() {
    let mut profile = company_profile(18);
    profile.business_status = LEASED_OWNER_OPERATOR.to_string();

    let policy = dispatch_policy(&profile);

    assert!(!policy.assigns_load);
    assert!(!policy.assigns_route);
    assert_eq!(policy.decline_budget, 0);
}

#[test]
fn test_independent_authority_chooses_load_and_route() {
    let mut profile = company_profile(25);
    profile.business_status = INDEPENDENT_AUTHORITY.to_string();

    let policy = dispatch_policy(&profile);

    assert!(!policy.assigns_load);
    assert!(!policy.assigns_route);
    assert_eq!(policy.decline_budget, 0);
}

#[test]
fn test_regional_regulars_earn_an_extra_decline() {
    // Level 5 is the "Regional Regular" rank: dispatch tolerates one more
    // assigned-load refusal from a proven driver.
    assert_eq!(
        dispatch_policy(&company_profile(4)).decline_budget,
        NEW_HIRE_DECLINE_BUDGET
    );
    assert_eq!(
        dispatch_policy(&company_profile(5)).decline_budget,
        NEW_HIRE_DECLINE_BUDGET + 1
    );
    assert_eq!(
        dispatch_policy(&company_profile(7)).decline_budget,
        NEW_HIRE_DECLINE_BUDGET + 1
    );
}

#[test]
fn test_decline_budget_counts_down_and_clamps_at_zero() {
    let mut profile = company_profile(1);
    assert_eq!(declines_remaining(&profile), NEW_HIRE_DECLINE_BUDGET);

    profile.career.dispatch_declines_used = 2;
    assert_eq!(declines_remaining(&profile), NEW_HIRE_DECLINE_BUDGET - 2);

    profile.career.dispatch_declines_used = NEW_HIRE_DECLINE_BUDGET + 5;
    assert_eq!(declines_remaining(&profile), 0);
}

#[test]
fn test_level_up_refills_the_decline_budget() {
    let mut career = Career::with_xp(LEVEL_XP[1] - 100.0);
    career.dispatch_declines_used = NEW_HIRE_DECLINE_BUDGET;

    let messages = career.record_delivery(200.0, 900.0, true, 0.0, 1.0, 1.0);

    assert!(messages.iter().any(|message| message.contains("Level up")));
    assert_eq!(career.dispatch_declines_used, 0);
}

#[test]
fn test_delivery_without_level_up_keeps_declines_spent() {
    let mut career = Career::new();
    career.dispatch_declines_used = 2;

    career.record_delivery(10.0, 100.0, true, 0.0, 1.0, 1.0);

    assert_eq!(career.dispatch_declines_used, 2);
}

#[test]
fn test_old_save_without_decline_field_round_trips() {
    // `Profile.to_dict()` / `from_dict` ride serde; the career half of that
    // round trip is what this pins: a save missing the field loads as 0, and
    // a value written survives a second trip.
    let profile_career = Career::new();
    let mut data = serde_json::to_value(&profile_career).unwrap();
    data.as_object_mut()
        .unwrap()
        .remove("dispatch_declines_used");

    let mut loaded: Career = serde_json::from_value(data).unwrap();

    assert_eq!(loaded.dispatch_declines_used, 0);

    loaded.dispatch_declines_used = 2;
    let reloaded: Career = serde_json::from_value(serde_json::to_value(&loaded).unwrap()).unwrap();
    assert_eq!(reloaded.dispatch_declines_used, 2);
}
