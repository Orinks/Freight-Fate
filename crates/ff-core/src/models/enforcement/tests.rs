//! Ported from `tests/test_enforcement_record.py`, plus the dispatch-trust
//! half of `tests/test_debt_and_standing.py`. Cases that drive the app shell,
//! a `Profile` save round trip, `dispatch_policy`, `business` or `career`
//! are ignored with the reason; their bodies say what they checked.

use serde_json::json;

use super::*;
use crate::models::solvency::test_profile::FakeProfile;
use crate::models::solvency::REPOSSESSION_FLOOR;

const DAY: f64 = 24.0;

fn record() -> DrivingRecord {
    DrivingRecord::new()
}

fn profile() -> FakeProfile {
    FakeProfile::new()
}

// --- money ------------------------------------------------------------------

#[test]
fn test_speeding_fine_climbs_with_how_far_over_the_limit() {
    let mild = speeding_citation_fine(8.0, 0, false);
    let serious = speeding_citation_fine(15.0, 0, false);
    let reckless = speeding_citation_fine(31.0, 0, false);
    assert!(mild < serious);
    assert!(serious < reckless);
    // The 15-mph step is where a citation also becomes a serious violation.
    assert!(serious >= 1_000.0);
}

#[test]
fn test_repeat_offenders_pay_more_up_to_the_cap() {
    // Priors compound the way real repeat offenders are charged "double, even
    // triple" a standard fine -- but the step stops at
    // CITATION_REPEAT_MAX_MULTIPLIER. Uncapped it reached 39,600 for a scale
    // bypass in roadwork, which reads as a broken game rather than a severe
    // one. See the constant for why solvency, not statute, sets the ceiling.
    let first = speeding_citation_fine(16.0, 0, false);
    let third = speeding_citation_fine(16.0, 2, false);
    assert!(third > first);
    // Beyond the cap the money stops climbing; the record keeps escalating.
    let many = speeding_citation_fine(35.0, 20, false);
    let plenty = speeding_citation_fine(35.0, 40, false);
    assert_eq!(plenty, many);
    assert_eq!(
        citation_fine(900.0, 99, false, None),
        900.0 * CITATION_REPEAT_MAX_MULTIPLIER
    );
}

#[test]
fn test_priors_climb_monotonically_and_then_hold() {
    let escalating: Vec<f64> = (0..12)
        .map(|n| speeding_citation_fine(16.0, n, false))
        .collect();
    let mut sorted = escalating.clone();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
    assert_eq!(escalating, sorted); // never cheaper for more priors
    let distinct: std::collections::BTreeSet<u64> =
        escalating.iter().map(|f| f.to_bits()).collect();
    assert!(distinct.len() > 1); // and it really does climb before holding

    // The same rule governs non-speeding citations.
    assert_eq!(
        citation_fine(900.0, 30, false, None),
        citation_fine(900.0, 5, false, None)
    );
    assert!(citation_fine(900.0, 2, false, None) > citation_fine(900.0, 0, false, None));
}

#[test]
fn test_no_single_citation_can_repossess_a_truck_on_its_own() {
    // The binding balance constraint, not a statutory one: the worst case the
    // game can actually produce -- the top speeding step, a habitual
    // offender, inside a construction zone -- stays under REPOSSESSION_FLOOR.
    let worst = speeding_citation_fine(99.0, 999, true);
    assert!(worst < REPOSSESSION_FLOOR);
    let flat = [
        UNSAFE_DAMAGE_FINE,
        WEIGH_STATION_BYPASS_FINE,
        FAILURE_TO_STOP_CITATION_FINE,
        WORK_ZONE_BARRELS_FINE,
    ]
    .into_iter()
    .map(|base| citation_fine(base, 999, true, None))
    .fold(f64::MIN, f64::max);
    assert!(flat < REPOSSESSION_FLOOR);
}

#[test]
fn test_the_construction_zone_doubling_survives_the_repeat_cap() {
    // Capping the step, not the total -- so the spoken line stays true.
    for priors in [0, 1, 2, 5, 40] {
        let plain = citation_fine(1_800.0, priors, false, None);
        let zoned = citation_fine(1_800.0, priors, true, None);
        assert_eq!(zoned, round_py_n(plain * 2.0, 2));
    }
}

#[test]
fn test_every_fine_is_anchored_to_the_real_penalty_it_names() {
    // The amounts themselves, so a rebalance is a deliberate edit here too.
    assert_eq!(UNSAFE_DAMAGE_FINE, 2300.0); // FMCSA unsafe conditions: 2,304
    assert_eq!(WEIGH_STATION_BYPASS_FINE, 1800.0); // CA/NY pass 1,000 on a first offense
    assert_eq!(CHAIN_LAW_FINE, 580.0); // Colorado: 500 plus a 79-dollar surcharge
    assert_eq!(FOLLOWING_TOO_CLOSE_FINE, 600.0); // a 383.51 Table 2 serious violation
    assert_eq!(LANE_MISUSE_FINE, 500.0); // Virginia's highway safety corridor figure
    assert_eq!(LIGHTS_FINE, 350.0);
    assert_eq!(FAILURE_TO_STOP_CITATION_FINE, 1500.0);
    assert_eq!(FAILURE_TO_STOP_FINE, 5000.0); // already a felony-sized number
    assert_eq!(WORK_ZONE_BARRELS_FINE, 1000.0); // Missouri RSMo 304.585, top of range
    assert_eq!(SPEEDING_FINE_STEPS[0].1, 250.0);
    assert_eq!(SPEEDING_FINE_STEPS[SPEEDING_FINE_STEPS.len() - 1].1, 2500.0);
}

#[test]
fn test_the_shoulder_parking_ticket_moved_with_the_rest() {
    assert_eq!(crate::sim::hos::SHOULDER_FINE, 400.0);
}

#[test]
fn test_a_fine_earned_in_a_construction_zone_is_doubled() {
    assert_eq!(CONSTRUCTION_ZONE_FINE_MULTIPLIER, 2.0);
    let plain = citation_fine(WEIGH_STATION_BYPASS_FINE, 0, false, None);
    let in_zone = citation_fine(WEIGH_STATION_BYPASS_FINE, 0, true, None);
    assert_eq!(plain, 1_800.0);
    assert_eq!(in_zone, 3_600.0);
    // Speeding doubles the same way; it is not exempt for going through its
    // own schedule first.
    assert_eq!(
        speeding_citation_fine(16.0, 0, true),
        speeding_citation_fine(16.0, 0, false) * 2.0
    );
}

#[test]
fn test_priors_and_the_construction_zone_compound_rather_than_add() {
    // The owner's explicit call: 1,800 x 1.5 x 2 on a second offense.
    let second_offense_in_zone = citation_fine(WEIGH_STATION_BYPASS_FINE, 1, true, None);
    assert_eq!(second_offense_in_zone, 5_400.0);
    // Adding the two multipliers instead of compounding them would give 2.5x.
    assert_ne!(second_offense_in_zone, WEIGH_STATION_BYPASS_FINE * 2.5);
}

#[test]
fn test_a_missing_driving_record_reads_as_a_first_offender() {
    let mut bare = profile();
    bare.driving_record = None;
    assert_eq!(career_citations(&bare), 0);
    let mut three = profile();
    three.record_mut().citations = 3;
    assert_eq!(career_citations(&three), 3);
}

#[test]
fn test_the_doubled_fine_says_why_in_plain_player_language() {
    assert_eq!(construction_zone_fine_clause(false), "");
    let clause = construction_zone_fine_clause(true);
    assert!(clause.contains("doubled"));
    // The canonical spoken noun from docs/ontology.md, never "work zone".
    assert!(clause.contains("construction zone"));
    assert!(!clause.contains("work zone"));
}

#[test]
fn a_statutory_ceiling_is_the_last_word() {
    assert_eq!(citation_fine(1_800.0, 5, true, Some(2_000.0)), 2_000.0);
    assert_eq!(citation_fine(1_800.0, 0, false, Some(2_000.0)), 1_800.0);
    assert!(is_serious_speed(15.0));
    assert!(!is_serious_speed(14.9));
}

// --- the serious-violation ladder ------------------------------------------

#[test]
fn test_first_serious_violation_does_not_suspend() {
    let mut r = record();
    assert_eq!(r.record_serious_violation(100.0), 1);
    assert!(!r.suspended(100.0));
}

#[test]
fn test_second_serious_violation_suspends_the_cdl_for_sixty_days() {
    let mut r = record();
    r.record_serious_violation(100.0);
    assert_eq!(r.record_serious_violation(200.0), 2);
    assert!(r.suspended(200.0));
    assert_eq!(
        round_py_int(r.days_left(200.0)),
        SERIOUS_SECOND_SUSPENSION_DAYS
    );
}

#[test]
fn test_third_serious_violation_suspends_for_a_hundred_and_twenty_days() {
    let mut r = record();
    for at in [100.0, 200.0] {
        r.record_serious_violation(at);
    }
    // Serve the 60 days out, then earn a third.
    let later = r.suspended_until_h + 1.0;
    assert_eq!(r.record_serious_violation(later), 3);
    assert_eq!(
        round_py_int(r.days_left(later)),
        SERIOUS_THIRD_SUSPENSION_DAYS
    );
}

#[test]
fn test_violations_older_than_three_years_stop_counting() {
    let mut r = record();
    r.record_serious_violation(0.0);
    let much_later = (SERIOUS_WINDOW_DAYS + 10) as f64 * DAY;
    assert_eq!(r.serious_in_window(much_later), 0);
    // So the next one is a first offense again, not a suspension.
    assert_eq!(r.record_serious_violation(much_later), 1);
    assert!(!r.suspended(much_later));
}

// --- major offenses: Jerry's case ------------------------------------------

#[test]
fn test_first_major_offense_disqualifies_the_cdl_for_a_year() {
    let mut r = record();
    assert_eq!(r.record_major_offense(50.0), SUSPENSION_MAJOR);
    assert!(r.suspended(50.0));
    assert_eq!(
        round_py_int(r.days_left(50.0)),
        MAJOR_FIRST_DISQUALIFICATION_DAYS
    );
    assert!(!r.lifetime_disqualified);
}

#[test]
fn test_second_major_offense_is_a_lifetime_disqualification() {
    let mut r = record();
    r.record_major_offense(50.0);
    assert_eq!(r.record_major_offense(60.0), SUSPENSION_LIFETIME);
    assert!(r.lifetime_disqualified);
    // There is no date this clears, at any point on the career clock.
    assert!(r.suspended(999_999.0));
    assert_eq!(r.days_left(999_999.0), f64::INFINITY);
}

#[test]
fn test_a_served_suspension_gives_the_licence_back() {
    let mut r = record();
    r.record_major_offense(50.0);
    let cleared = r.suspended_until_h + 1.0;
    assert!(!r.suspended(cleared));
    r.serve_until(cleared);
    assert_eq!(r.suspended_until_h, 0.0);
    assert_eq!(r.suspension_reason, "");
}

// --- fatigue (49 CFR 392.3) -------------------------------------------------

#[test]
fn test_first_run_off_road_asleep_costs_standing_not_the_licence() {
    let mut r = record();
    let (count, serious) = r.record_fatigue_event(100.0);
    assert_eq!((count, serious), (1, 0));
    assert!(!r.suspended(100.0));
}

#[test]
fn test_second_run_off_road_asleep_is_a_serious_violation() {
    let mut r = record();
    r.record_fatigue_event(100.0);
    let (count, serious) = r.record_fatigue_event(200.0);
    assert_eq!(count, 2);
    assert_eq!(serious, 1);
    assert_eq!(r.serious_in_window(200.0), 1);
}

// --- dispatch trust ---------------------------------------------------------

#[test]
fn test_a_clean_driver_sees_the_board_they_have_always_seen() {
    assert_eq!(board_offers_for_reputation(6, 50.0), 6);
    assert_eq!(board_offers_for_reputation(6, 100.0), 6);
    assert_eq!(trust_band(50.0), TRUST_FULL); // where every new career starts
}

#[test]
fn test_dispatch_trust_slides_the_whole_way_down() {
    let steps: Vec<i64> = [50.0, 40.0, 25.0, 5.0]
        .into_iter()
        .map(|rep| board_offers_for_reputation(6, rep))
        .collect();
    let mut sorted = steps.clone();
    sorted.sort_by(|a, b| b.cmp(a));
    assert_eq!(steps, sorted);
    assert!(steps[0] > steps[steps.len() - 1]);
    assert_eq!(steps[steps.len() - 1], 1);
}

#[test]
#[ignore = "needs models::dispatch_policy and models::profile"]
fn test_losing_trust_takes_back_the_right_to_pick_your_own_loads() {
    // A senior driver past the load-choice level goes back to assigned loads
    // at reputation 18 and loses every refusal at 10.
}

#[test]
fn the_trust_ladder_matches_the_python_tables() {
    assert!(trust_revokes_load_choice(20.0));
    assert!(trust_revokes_load_choice(5.0));
    assert!(!trust_revokes_load_choice(30.0));
    assert_eq!(trust_decline_penalty(50.0), 0);
    assert_eq!(trust_decline_penalty(30.0), 1);
    assert_eq!(trust_decline_penalty(20.0), 2);
    assert_eq!(trust_decline_penalty(10.0), 99);
    assert_eq!(board_offers_for_reputation(4, 30.0), 3);
    assert_eq!(
        trust_text(50.0),
        "Dispatch trust: full. You get the whole board."
    );
    assert_eq!(
        trust_text(30.0),
        "Dispatch trust: guarded. Dispatch is holding back some of the freight and \
         fewer refusals. Clean on-time runs rebuild it."
    );
    assert_eq!(board_reputation_note(50.0), "");
    assert_eq!(board_reputation_note(20.0), trust_text(20.0));
    assert_eq!(
        worst_band(&[TRUST_FULL, TRUST_POOR, TRUST_GUARDED]),
        TRUST_POOR
    );
    assert_eq!(worst_band(&[TRUST_FULL]), TRUST_FULL);
}

// --- persistence and retroactivity -----------------------------------------

#[test]
fn test_the_record_survives_save_and_load() {
    // The record half: the DrivingRecord's save shape round-trips. The
    // Profile.to_dict / from_dict path needs models::profile.
    let mut r = record();
    let game_hours = 500.0;
    r.record_major_offense(game_hours);
    r.record_citation(1_000.0);
    let text = serde_json::to_string(&r).unwrap();
    let restored: DrivingRecord = serde_json::from_str(&text).unwrap();
    assert_eq!(restored.major_count(), 1);
    assert_eq!(restored.citations, 1);
    assert!(restored.suspended(game_hours));
    assert_eq!(restored, r);
    // A save from before a field existed still loads, with the default.
    let partial: DrivingRecord = serde_json::from_str(r#"{"citations": 2}"#).unwrap();
    assert_eq!(partial.citations, 2);
    assert!(partial.serious_violations.is_empty());
    assert!(!partial.lifetime_disqualified);
}

#[test]
fn test_a_legacy_save_counts_the_felonies_it_still_holds() {
    // Exactly what the old build wrote: the felony count lived on the trip.
    let data = json!({
        "active_trip": {"failure_to_stop_count": 2, "speeding_tickets": 1},
        "game_hours": 400.0,
    });
    let record = seed_record_from_save(data.as_object().unwrap());
    assert_eq!(record.major_count(), 2);
    assert!(record.lifetime_disqualified); // no amnesty
    assert!(record.notice_pending);
    assert_eq!(record.citations, 1);
}

#[test]
fn test_a_clean_legacy_save_gets_a_clean_record_and_no_notice() {
    let data = json!({"name": "Clean", "game_hours": 6.0, "career": {"reputation": 50.0}});
    let record = seed_record_from_save(data.as_object().unwrap());
    assert!(record.clean(6.0));
    assert!(!record.notice_pending);
    // A low reputation alone earns the one-time explanation.
    let low = json!({"game_hours": 6.0, "career": {"reputation": 20.0}});
    assert!(seed_record_from_save(low.as_object().unwrap()).notice_pending);
    // No career block at all reads as the neutral 50.
    let none = json!({"game_hours": 6.0});
    assert!(!seed_record_from_save(none.as_object().unwrap()).notice_pending);
}

// --- spoken surfaces --------------------------------------------------------

#[test]
fn test_standing_is_said_plainly_and_names_the_next_consequence() {
    let mut p = profile();
    p.game_hours = 100.0;
    assert_eq!(standing_text(&p), "Record: clean.");
    p.record_mut().record_serious_violation(100.0);
    let text = standing_text(&p);
    assert!(text.contains("one serious violation"));
    assert!(text.contains("60 days"));
    assert!(!text.to_lowercase().contains("strike")); // that noun belongs to the per-trip counter
    assert_eq!(
        text,
        "Record: one serious violation. One more before your CDL is suspended for 60 days."
    );
}

#[test]
fn test_a_suspended_record_says_when_it_clears() {
    let mut p = profile();
    p.game_hours = 100.0;
    // The ladder suspends; a major offense disqualifies. Two nouns, two things.
    p.record_mut().record_serious_violation(100.0);
    p.record_mut().record_serious_violation(100.0);
    assert!(career_menu_status(&p).contains("suspended"));
    assert!(standing_text(&p).contains("60 days"));

    let mut q = profile();
    q.game_hours = 100.0;
    q.record_mut().record_major_offense(100.0);
    assert!(career_menu_status(&q).contains("disqualified"));
    let text = standing_text(&q);
    assert!(text.contains("365 days"));
    assert!(text.contains("clears"));
    assert!(!text.contains("hours")); // served in game days, never raw hours
}

#[test]
#[ignore = "needs states::driving_rest_states (_major_offense_text)"]
fn test_the_lifetime_line_states_the_facts_and_the_way_forward() {}

#[test]
fn the_spoken_standing_lines_match_the_python_f_strings() {
    let mut p = profile();
    p.game_hours = 100.0;
    p.record_mut().record_major_offense(100.0);
    // 100 h + 365 days lands on a weekday and date from the career calendar.
    let clears = clears_text(&p);
    assert!(clears.contains(", "));
    assert_eq!(
        standing_text(&p),
        format!("Record: CDL disqualified, 365 days remaining. It clears {clears}.")
    );
    assert_eq!(
        career_menu_status(&p),
        "CDL: disqualified, 365 days remaining"
    );
    assert_eq!(
        suspension_board_line(&p),
        format!("Dispatch board. Your CDL is disqualified; driving jobs return {clears}.")
    );
    assert_eq!(
        suspension_refusal_line(&p),
        format!(
            "You cannot take this job while your CDL is disqualified. It clears {clears}. \
             Escape goes back to the board."
        )
    );
    // A calendar offset moves the spoken date.
    p.calendar_offset_days = 3.0;
    assert_ne!(clears_text(&p), clears);

    p.record_mut().record_major_offense(200.0);
    assert_eq!(clears_text(&p), "");
    assert_eq!(
        standing_text(&p),
        "Record: your CDL is disqualified for life. You cannot take driving work."
    );
    assert_eq!(career_menu_status(&p), "CDL: disqualified for life");
    assert_eq!(
        suspension_board_line(&p),
        "Dispatch board. Your CDL is disqualified for life, so there is no driving work \
         here. The board is listed for reference only."
    );
    assert_eq!(
        suspension_refusal_line(&p),
        "You cannot take driving work with a lifetime CDL disqualification. Escape goes \
         back to the terminal."
    );

    let mut clean = profile();
    clean.game_hours = 100.0;
    assert_eq!(career_menu_status(&clean), "CDL: clear");
    // Served violations and a major offense, off suspension.
    clean.record_mut().major_offenses.push(0.0);
    clean.record_mut().serious_violations.push(0.0);
    clean.record_mut().serious_violations.push(0.0);
    assert_eq!(
        standing_text(&clean),
        "Record: two serious violations, one major offense. One more major offense \
         disqualifies your CDL for life."
    );
}

#[test]
fn count_and_ordinal_words_and_days_text() {
    assert_eq!(count_word(0), "no");
    assert_eq!(count_word(9), "nine");
    assert_eq!(count_word(10), "10");
    assert_eq!(ordinal_word(1), "first");
    assert_eq!(ordinal_word(7), "seventh");
    assert_eq!(ordinal_word(0), "0th");
    assert_eq!(ordinal_word(8), "8th");
    assert_eq!(days_text(0.2), "1 day");
    assert_eq!(days_text(1.4), "1 day");
    assert_eq!(days_text(2.5), "2 days"); // round half to even, like Python
    assert_eq!(days_text(59.6), "60 days");
}

// --- the whole picture (tests/test_debt_and_standing.py) -------------------

#[test]
fn test_debt_alone_holds_the_iron_back_even_with_a_spotless_record() {
    // The standing half; equipment_held_back / assigned_fleet_tier need
    // models::carrier_fleet.
    let mut p = profile();
    p.reputation = 100.0;
    p.money = -5_000.0; // square on service, deep on money
    assert_eq!(trust_band(p.reputation), TRUST_FULL);
    assert_ne!(standing_band(&p), TRUST_FULL);
    assert_eq!(standing_cause(&p), CAUSE_DEBT);
}

#[test]
fn test_a_suspended_licence_holds_the_seat_but_an_old_violation_does_not() {
    // Violations reach the band through reputation; only a suspension pins it.
    let mut p = profile();
    let hours = p.game_hours;
    p.record_mut().record_serious_violation(hours);
    assert!(!p.record().suspended(hours));
    assert_eq!(licence_band(&p), TRUST_FULL);
    assert_eq!(standing_band(&p), TRUST_FULL);

    p.record_mut().record_serious_violation(hours); // second: suspended
    assert!(p.record().suspended(hours));
    assert_eq!(standing_band(&p), TRUST_LAST_CHANCE);
    assert_eq!(standing_cause(&p), CAUSE_LICENCE);
    assert!(standing_way_back(&p).contains("clears"));
}

#[test]
fn test_the_way_back_names_the_cause_rather_than_promising_clean_runs() {
    // "Clean on-time runs rebuild it" is a lie to a driver whose debt is the problem.
    let mut p = profile();
    p.money = -5_000.0;
    let way_back = standing_way_back(&p);
    assert!(way_back.contains("owe") && way_back.contains("Paying it down"));
    assert_ne!(way_back, "Clean on-time runs rebuild it.");
    assert_eq!(
        way_back,
        "You owe 5,000 dollars, and that is what is holding it. Paying it down brings it back."
    );

    let mut q = profile();
    q.reputation = 20.0;
    assert_eq!(standing_way_back(&q), "Clean on-time runs rebuild it.");

    // Debt and poor service together name both.
    let mut both = profile();
    both.money = -5_000.0;
    both.reputation = 20.0;
    assert_eq!(standing_cause(&both), CAUSE_DEBT);
    assert!(standing_way_back(&both).ends_with("and clean on-time runs help too."));

    // The whole line, with the trust clause and the slower-experience clause.
    let line = dispatch_trust_line(&both);
    assert!(line.starts_with(trust_band_text(standing_band(&both))));
    assert!(line.contains("career experience comes in more slowly"));
    assert_eq!(dispatch_trust_line(&profile()), trust_text(50.0));
    // A hold clause from the fleet rides between the way back and the rate.
    let mut held = profile();
    held.money = -5_000.0;
    held.hold_clause = "The yard is holding your truck.".to_string();
    assert!(dispatch_trust_line(&held)
        .contains("The yard is holding your truck. While your dispatch trust is"));
}

#[test]
fn a_low_reputation_company_driver_is_due_for_termination() {
    let mut p = profile();
    p.reputation = 4.0;
    assert!(carrier_termination_due(&p));
    p.carrier_key = LAST_CHANCE_CARRIER_KEY.to_string();
    assert!(!carrier_termination_due(&p)); // nowhere further down
    let mut owner = profile();
    owner.reputation = 4.0;
    owner.business_status = crate::models::business_constants::LEASED_OWNER_OPERATOR.to_string();
    assert!(!carrier_termination_due(&owner));
}

#[test]
#[ignore = "needs models::carrier_fleet"]
fn test_the_yard_hands_over_the_lower_of_level_and_standing() {}

#[test]
#[ignore = "needs models::carrier_fleet"]
fn test_a_held_back_truck_names_the_earned_tier_the_cause_and_the_way_out() {}

#[test]
#[ignore = "needs models::career (STANDING_XP_RATE)"]
fn test_experience_slows_by_band_and_never_reaches_zero() {
    // STANDING_XP_RATE is keyed by exactly TRUST_FULL / GUARDED / POOR /
    // LAST_CHANCE, descends, stays above 0.5, and is 1.0 for a clean driver.
}

#[test]
#[ignore = "needs models::career (Career.record_delivery)"]
fn test_a_slowed_career_still_levels_up() {}

#[test]
#[ignore = "needs models::career (xp_rate_clause)"]
fn test_the_slowdown_is_said_in_words_and_never_as_a_number() {}

#[test]
#[ignore = "needs models::career and profile_integrity_invariants"]
fn test_slowed_experience_stays_under_the_exported_cloud_ceiling() {}

// --- the road, the stops, the board: app-shell cases ------------------------

#[test]
#[ignore = "needs states::driving (FelonyStopState) and the app shell"]
fn test_running_from_the_stop_writes_a_major_offense_on_the_career() {}

#[test]
#[ignore = "needs states::driving (FelonyStopState) and the app shell"]
fn test_a_second_pursuit_ends_this_career_driving_for_good() {}

#[test]
#[ignore = "needs states::driving (TrafficStopState) and the app shell"]
fn test_a_stop_that_suspends_the_cdl_does_not_send_you_back_out_driving() {}

#[test]
#[ignore = "needs states::driving (TrafficStopState) and the app shell"]
fn test_an_ordinary_ticket_still_pulls_back_onto_the_highway() {}

#[test]
#[ignore = "needs states::driving (TrafficStopState) and the app shell"]
fn test_the_suspended_stop_says_the_run_is_over_and_why() {}

#[test]
#[ignore = "needs states::driving (EnforcementStopState) and the app shell"]
fn test_an_enforcement_stop_that_suspends_also_ends_the_run() {}

#[test]
#[ignore = "needs states::driving (TrafficStopState) and the app shell"]
fn test_a_serious_speeding_ticket_moves_the_ladder_and_says_so() {}

#[test]
#[ignore = "needs states::driving (TrafficStopState) and the app shell"]
fn test_a_mild_speeding_ticket_is_money_only() {}

#[test]
#[ignore = "needs states::driving (_update_enforcement_watch) and the app shell"]
fn test_speeding_nobody_saw_never_touches_the_licence() {}

#[test]
#[ignore = "needs states::driving (FelonyStopState) and the app shell"]
fn test_debug_hours_mode_freezes_the_ladder() {}

#[test]
#[ignore = "needs states::driving (_microsleep_drift_off_road) and the app shell"]
fn test_running_off_the_road_asleep_costs_reputation_and_is_spoken() {}

#[test]
#[ignore = "needs states::driving (_microsleep_drift_off_road) and the app shell"]
fn test_terse_speech_still_hears_every_consequence() {}

#[test]
#[ignore = "needs states::driving (_microsleep_drift_off_road) and the app shell"]
fn test_repeat_fatigue_events_speak_the_real_count() {}

#[test]
#[ignore = "needs states::city (CityMenuState) and the app shell"]
fn test_a_clean_driver_hears_and_pays_nothing_new() {}

#[test]
#[ignore = "needs states::driving (_update_pursuit_optin) and the app shell"]
fn test_holding_the_run_key_states_the_cost_before_it_counts() {}

#[test]
#[ignore = "needs states::driving (_update_pursuit_optin) and the app shell"]
fn test_holding_the_run_key_through_the_warning_lands_the_full_offense() {}

#[test]
#[ignore = "needs states::driving (_update_pursuit_optin) and the app shell"]
fn test_the_second_pursuit_takes_twice_as_long_to_choose() {}

#[test]
#[ignore = "needs states::driving (snapshot) and the app shell"]
fn test_reloading_mid_stop_does_not_cancel_the_stop() {}

#[test]
#[ignore = "needs states::driving (EnforcementStopState) and the app shell"]
fn test_a_paid_stop_is_not_charged_again_on_the_next_resume() {}

#[test]
#[ignore = "needs states::driving_engine_brake and the app shell"]
fn test_toggling_the_jake_cannot_farm_warnings_forever() {}

#[test]
#[ignore = "needs states::driving (_microsleep_drift_off_road) and the app shell"]
fn test_the_fatigue_out_of_service_actually_holds_the_truck() {}

#[test]
fn test_a_fine_a_load_cannot_cover_stays_owed_and_is_said_so() {
    use crate::models::business::build_business_settlement_basic;
    use crate::models::jobs::{cargo_type, Job};
    let job = Job::new(
        cargo_type("general").unwrap(),
        5.0,
        "Buffalo",
        "yard",
        "Rochester",
        40.0,
        120.0,
        8.0,
    );
    let settled = build_business_settlement_basic("company_driver", &job, 120.0, true, 2_000.0);
    assert_eq!(settled.net_before_advance, 0.0);
    // The shortfall is owed, not quietly forgiven.
    assert!(settled.uncollected_charges > 0.0);
    assert!(settled.uncollected_charges < 2_000.0);
}

#[test]
#[ignore = "needs states::city (JobBoardState) and the app shell"]
fn test_the_board_says_the_suspension_before_it_lists_anything() {}

#[test]
#[ignore = "needs states::city (JobBoardState) and the app shell"]
fn test_taking_a_job_while_suspended_is_refused_with_the_clear_date() {}

#[test]
#[ignore = "needs states::city (CityMenuState) and the app shell"]
fn test_waiting_out_the_suspension_gives_the_licence_back() {}

#[test]
#[ignore = "needs states::city (CityMenuState) and the app shell"]
fn test_a_floor_reputation_company_driver_loses_the_carrier() {}

#[test]
#[ignore = "needs states::driving_rest_states (EnforcementStopState) and the app shell"]
fn test_a_settled_stop_is_read_back_as_history_not_as_a_fresh_charge() {}
