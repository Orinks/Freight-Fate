//! Ported from `tests/test_career_objectives.py`. The pure `career_objective`
//! cases run against the career-side `FakeProfile`; the cases that drive the
//! app shell (`App`, `CityMenuState`, `JobBoardState`) are ignored with the
//! reason and their bodies say what they checked.

use super::*;
use crate::models::business_constants::LEASED_OWNER_OPERATOR;
use crate::models::career::test_profile::FakeProfile;
use crate::models::career::LEVEL_XP;

fn profile(name: &str) -> FakeProfile {
    FakeProfile::named(name)
}

#[test]
fn test_company_driver_objective_tapers_from_first_week_to_trust() {
    let mut profile = profile("Career Plan");
    profile.achievements.push("first_dispatch".to_string());

    let first_load = career_objective(&profile);
    assert_eq!(first_load.title, "First dispatch");
    assert!(first_load.terminal_text.contains("real freight"));
    assert!(first_load.dispatch_text.contains("short standard load"));
    assert!(!first_load
        .spoken_summary()
        .to_lowercase()
        .contains("probation"));

    profile.career.deliveries = 2;
    let reminder = career_objective(&profile);
    assert_eq!(reminder.title, "First-week service record");
    assert!(reminder
        .terminal_text
        .contains("steady service, not perfection"));

    profile.career.deliveries = 4;
    profile.career.reputation = 62.0;
    let trust = career_objective(&profile);
    assert_eq!(trust.title, "Build dispatcher trust");
    assert!(trust.terminal_text.contains("on-time service"));
    assert!(trust.dispatch_text.contains("reliable lanes"));
}

#[test]
fn test_low_reputation_company_driver_keeps_trust_objective_after_training() {
    let mut profile = profile("Trust Plan");
    profile.achievements.push("first_dispatch".to_string());
    profile.career.deliveries = 12;
    profile.career.reputation = 62.0;

    let objective = career_objective(&profile);

    assert_eq!(objective.title, "Build dispatcher trust");
    assert!(objective.terminal_text.contains("on-time service"));
    assert!(objective.dispatch_text.contains("reliable lanes"));
}

#[test]
fn test_company_driver_objective_uses_level_band_guidance_after_training() {
    let mut profile = profile("Regional Plan");
    profile.achievements.push("first_dispatch".to_string());
    profile.career.xp = LEVEL_XP[3];
    profile.career.deliveries = 12;
    profile.career.reputation = 82.0;

    let objective = career_objective(&profile);

    assert_eq!(objective.title, "Build a regional service record");
    assert!(objective.terminal_text.contains("broader company lanes"));
    assert_eq!(objective.recommendation, "reputation-building lane");
}

#[test]
fn test_ready_unlock_states_override_level_band_guidance() {
    let mut profile = profile("Buy In");
    profile.achievements.push("first_dispatch".to_string());
    profile.career.xp = LEVEL_XP[(OWNER_OPERATOR_LEVEL - 1) as usize];
    profile.career.deliveries = 35;
    profile.career.reputation = 82.0;
    profile.money = 60_000.0;

    let objective = career_objective(&profile);

    assert_eq!(objective.title, "Owner-operator buy-in ready");
    assert_eq!(objective.recommendation, "clean company load");
}

#[test]
fn test_owner_operator_objective_emphasizes_working_capital() {
    let mut profile = profile("Owner Plan");
    profile.business_status = LEASED_OWNER_OPERATOR.to_string();
    profile.owned_trucks = vec!["rig".to_string()];
    profile.money = 12_000.0;
    profile.achievements.push("first_dispatch".to_string());

    let objective = career_objective(&profile);

    assert_eq!(objective.title, "Protect working capital");
    assert!(objective
        .terminal_text
        .contains("Fuel, maintenance, insurance"));
    assert!(objective.dispatch_text.contains("take-home"));
}

#[test]
#[ignore = "needs freight_fate::app (App, CityMenuState)"]
fn test_terminal_career_plan_is_keyboard_reachable_and_spoken() {
    // On entering CityMenuState: something spoken contains "Career objective:",
    // a "Career plan" item exists; DOWN then RETURN speaks a line starting
    // "First dispatch." containing "short standard load".
    unimplemented!("needs the app shell")
}

#[test]
#[ignore = "needs freight_fate::app (App, CityMenuState)"]
fn test_terminal_career_plan_speaks_senior_company_level_guidance() {
    // Level 10, 20 deliveries, reputation 86: the Career plan item speaks a
    // line starting "Run like a senior company driver." with "premium lanes",
    // "premium freight" and "Senior company status is about consistency".
    unimplemented!("needs the app shell")
}

#[test]
#[ignore = "needs freight_fate::app (App, JobBoardState)"]
fn test_dispatch_board_speaks_objective_and_marks_recommended_job() {
    // Senior company driver on a two-job board: the entry announcement names
    // "Career objective: Run like a senior company driver", "pick your own
    // loads", "routing is still assigned", and the shorter job is marked
    // "Recommended dispatch, senior company lane: Job 2 of 2:".
    unimplemented!("needs the app shell")
}

#[test]
#[ignore = "needs freight_fate::app (App, JobBoardState)"]
fn test_dispatch_board_speaks_authority_level_recommendation() {
    // Independent authority at level 25: the board entry names "Career
    // objective: Grow a freight business", "direct freight" and "direct
    // freight with margin".
    unimplemented!("needs the app shell")
}

#[test]
fn test_late_company_driver_plan_points_to_owner_operator_prep() {
    let mut profile = profile("Prep Plan");
    profile.achievements.push("first_dispatch".to_string());
    profile.career.xp = LEVEL_XP[(OWNER_OPERATOR_LEVEL - 4) as usize];
    profile.career.deliveries = 25;
    profile.career.reputation = 75.0;

    let objective = career_objective(&profile);

    assert_eq!(objective.title, "Owner-operator preparation");
    assert!(objective.terminal_text.contains("cash cushion"));
    assert!(objective.dispatch_text.contains("protects reputation"));
    assert_eq!(
        objective.terminal_text,
        "Work toward level 18, 35 deliveries, 80 reputation, and a cash cushion."
    );
}

#[test]
#[ignore = "needs freight_fate::app (App, CityMenuState)"]
fn test_first_day_terminal_entry_speaks_training_arc_without_tutorial_language() {
    // A fresh profile's city-menu entry names "First-day objective" and
    // "trainer-recommended" and never "probation".
    unimplemented!("needs the app shell")
}

#[test]
#[ignore = "needs freight_fate::app (App, CityMenuState)"]
fn test_out_of_sync_company_terminal_entry_uses_first_week_guidance() {
    // One delivery, no first_dispatch badge: the entry says "Career
    // objective:" (not "First-day objective"), "steady service, not
    // perfection", "good first-week run", "trainer notes still close by";
    // the menu lists "Career plan" and not "First-day briefing".
    unimplemented!("needs the app shell")
}

#[test]
#[ignore = "needs freight_fate::app (App, JobBoardState)"]
fn test_dispatch_board_recommendation_label_is_spoken_and_visible() {
    // Senior company driver, two jobs where the first is recommended: the
    // entry announcement and item 0 start "Recommended dispatch, senior
    // company lane: Job 1 of 2:" and the label is never doubled.
    unimplemented!("needs the app shell")
}

#[test]
#[ignore = "needs freight_fate::app (App, CityMenuState)"]
fn test_owner_operator_first_day_terminal_keeps_cash_cushion_guidance() {
    // Leased owner-operator on day one: "First-day objective" with "cash
    // cushion" and never "trainer-recommended".
    unimplemented!("needs the app shell")
}

#[test]
#[ignore = "needs freight_fate::app (App, CityMenuState, JobBoardState)"]
fn test_out_of_sync_owner_operator_uses_career_guidance() {
    // Owner-operator start past day one: the city menu says "Career
    // objective:" with "Fuel, maintenance, insurance" and lists "Career plan";
    // the board entry says "cash-positive load".
    unimplemented!("needs the app shell")
}

#[test]
#[ignore = "needs freight_fate::app (App, JobBoardState)"]
fn test_owner_operator_first_day_dispatch_board_keeps_business_cost_guidance() {
    // Owner-operator day-one board: "owner-operator gross revenue", "cash
    // cushion", no "trainer-recommended", item 0 starts "Job 1 of 2:" and no
    // item starts "Recommended dispatch, trainer-recommended:".
    unimplemented!("needs the app shell")
}

// --- the owner-operator and authority branches the Python suite reaches
// --- only through the app shell -----------------------------------------------

#[test]
fn test_owner_operator_objective_moves_from_capital_to_authority_prep() {
    let mut profile = profile("Owner Arc");
    profile.business_status = LEASED_OWNER_OPERATOR.to_string();
    profile.owned_trucks = vec!["rig".to_string()];
    profile.money = 80_000.0;
    profile.career.xp = LEVEL_XP[18];
    profile.career.deliveries = 40;
    profile.career.reputation = 85.0;

    let prep = career_objective(&profile);
    assert_eq!(prep.title, "Authority preparation");
    assert_eq!(
        prep.terminal_text,
        "Build reputation, deliveries, and at least 25,000 dollars in working capital."
    );
    assert_eq!(prep.recommendation, "owner-operator margin load");

    profile.career.xp = LEVEL_XP[20];
    profile.career.deliveries = 60;
    profile.career.reputation = 90.0;
    let ready = career_objective(&profile);
    assert_eq!(ready.title, "Authority prep ready");
    assert_eq!(ready.recommendation, "reserve-safe load");

    profile.authority_readiness = true;
    profile.career.xp = LEVEL_XP[17];
    let level_band = career_objective(&profile);
    assert_eq!(level_band.title, "Protect owner-operator margin");
    assert_eq!(
        level_band.milestone_text,
        "Owner-operator progress depends on margin discipline."
    );
    assert!(level_band
        .spoken_summary()
        .ends_with(" Owner-operator progress depends on margin discipline."));
}

#[test]
fn test_independent_authority_objective_grows_then_follows_the_level_band() {
    use crate::models::business_constants::INDEPENDENT_AUTHORITY;
    let mut profile = profile("Independent");
    profile.business_status = INDEPENDENT_AUTHORITY.to_string();
    profile.owned_trucks = vec!["rig".to_string()];
    profile.money = 90_000.0;
    profile.career.xp = LEVEL_XP[21];
    profile.career.deliveries = 80;
    profile.career.reputation = 94.0;

    let growing = career_objective(&profile);
    assert_eq!(growing.title, "Grow direct freight reputation");
    assert_eq!(growing.recommendation, "direct freight with margin");

    profile.career.xp = LEVEL_XP[24];
    let band = career_objective(&profile);
    assert_eq!(band.title, "Grow a freight business");
    assert_eq!(band.recommendation, "direct freight with margin");
}
