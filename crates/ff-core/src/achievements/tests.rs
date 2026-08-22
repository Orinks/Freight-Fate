//! Ported from `tests/test_achievements.py` (the pure parts),
//! `tests/test_career_arc_achievements.py` (the catalog checks) and
//! `tests/test_achievement_flavor_relocated.py`. Everything that drove a
//! `DrivingState`/`ArrivalState` through `App()` is listed `#[ignore]` with
//! its Python body summarised, until the app shell lands.

use std::collections::HashSet;

use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

use super::*;
use crate::speech_text::achievement_announced;

/// The two profile attributes the module touches, as a bare test double.
#[derive(Default)]
struct TestProfile {
    achievements: Vec<String>,
    achievement_stats: Map<String, Value>,
}

impl AchievementProfile for TestProfile {
    fn achievements(&self) -> &[String] {
        &self.achievements
    }
    fn achievements_mut(&mut self) -> &mut Vec<String> {
        &mut self.achievements
    }
    fn achievement_stats_mut(&mut self) -> &mut Map<String, Value> {
        &mut self.achievement_stats
    }
}

/// The generator's framing: categories then badges, fields joined by
/// U+001F, records ended by U+001E, the two tables split by U+001D.
fn catalog_digest() -> String {
    let mut hasher = Sha256::new();
    for category in &CATEGORIES {
        hasher.update([category.id, category.title, category.description].join("\u{1f}"));
        hasher.update(b"\x1e");
    }
    hasher.update(b"\x1d");
    for achievement in &ACHIEVEMENTS {
        hasher.update(
            [
                achievement.id,
                achievement.name,
                achievement.description,
                achievement.category,
                achievement.inspiration,
                if achievement.hidden { "1" } else { "0" },
            ]
            .join("\u{1f}"),
        );
        hasher.update(b"\x1e");
    }
    hex::encode(hasher.finalize())
}

#[test]
fn the_generated_catalog_matches_the_python_source_digest() {
    assert_eq!(catalog_digest(), CATALOG_DIGEST);
    assert_eq!(ACHIEVEMENTS.len(), 173);
    assert_eq!(CATEGORIES.len(), 7);
}

#[test]
fn test_achievement_copy_is_allusive_and_speech_sized() {
    for achievement in &ACHIEVEMENTS {
        let (artist, _title) = achievement
            .inspiration
            .split_once(" - ")
            .unwrap_or_else(|| panic!("{} has no artist - title", achievement.id));
        let visible = format!("{} {}", achievement.name, achievement.description).to_lowercase();
        assert!(!achievement.description.contains('\n'));
        let length = achievement.description.chars().count();
        assert!((80..=220).contains(&length), "{}: {length}", achievement.id);
        assert!(
            achievement.description.matches('.').count() >= 2,
            "{}",
            achievement.id
        );
        assert!(!achievement.description.contains('"'), "{}", achievement.id);
        assert!(!achievement.inspiration.is_empty());
        // Artists stay out of player-facing text. Song titles are allowed to
        // appear (many are just place names, like Jackson or Abilene); the
        // no-lyrics rule lives in the catalog's copy note.
        assert!(
            !visible.contains(&artist.to_lowercase()),
            "{}: {artist}",
            achievement.id
        );
    }

    let mut profile = TestProfile::default();
    let message = award(&mut profile, ACHIEVEMENTS[0].id).unwrap().message;
    assert!(message.normal.starts_with("New achievement!"));
}

#[test]
fn test_catalog_tops_one_hundred_with_unique_ids() {
    let ids: Vec<&str> = ACHIEVEMENTS.iter().map(|a| a.id).collect();
    let unique: HashSet<&str> = ids.iter().copied().collect();
    assert_eq!(ids.len(), unique.len());
    assert!(ids.len() > 100);
}

#[test]
fn test_every_achievement_has_exactly_one_valid_category() {
    for achievement in &ACHIEVEMENTS {
        assert!(
            category_by_id(achievement.category).is_some(),
            "{}",
            achievement.id
        );
    }
}

#[test]
fn test_every_category_is_non_empty() {
    for category in &CATEGORIES {
        assert!(
            !achievements_in_category(category.id).is_empty(),
            "{}",
            category.id
        );
    }
}

#[test]
fn test_category_copy_is_speech_sized_and_quote_free() {
    let mut seen_ids = HashSet::new();
    for category in categories() {
        assert!(seen_ids.insert(category.id), "category ids must be unique");
        assert!(!category.title.contains('\n'));
        assert!(!category.description.contains('\n'));
        assert!(!category.title.contains('"'));
        assert!(!category.description.contains('"'));
        assert!(!category.title.is_empty());
        let length = category.description.chars().count();
        assert!((20..=120).contains(&length), "{}", category.id);
    }
}

#[test]
fn test_hidden_achievement_keeps_its_secret_until_earned() {
    let hidden: Vec<&Achievement> = ACHIEVEMENTS.iter().filter(|a| a.hidden).collect();
    // the deep-cuts bucket carries at least one hidden badge
    assert!(!hidden.is_empty());
    for achievement in hidden {
        let (locked_name, locked_detail) = entry_text(achievement, false);
        assert_eq!(locked_name, HIDDEN_NAME);
        assert_eq!(locked_detail, HIDDEN_HELP);
        let (earned_name, earned_detail) = entry_text(achievement, true);
        assert_eq!(earned_name, achievement.name);
        assert_eq!(earned_detail, achievement.description);
    }
}

#[test]
fn test_non_hidden_locked_achievement_speaks_its_own_title() {
    let visible = ACHIEVEMENTS.iter().find(|a| !a.hidden).unwrap();
    let (name, detail) = entry_text(visible, false);
    assert_eq!(name, visible.name);
    assert_eq!(detail, visible.description);
}

#[test]
fn test_increment_stat_counts_and_survives_bad_values() {
    let mut profile = TestProfile::default();
    assert_eq!(increment_stat(&mut profile, "inspections_passed"), 1);
    assert_eq!(increment_stat(&mut profile, "inspections_passed"), 2);
    profile
        .achievement_stats
        .insert("inspections_passed".into(), json!("corrupt"));
    assert_eq!(int_stat(&mut profile, "inspections_passed"), 0);
    assert_eq!(increment_stat(&mut profile, "inspections_passed"), 1);
}

#[test]
fn int_stat_reads_the_json_shapes_python_int_accepts() {
    let mut profile = TestProfile::default();
    for (value, expected) in [
        (json!(7), 7),
        (json!(3.9), 3),
        (json!(true), 1),
        (json!("12"), 12),
        (json!(" 12 "), 12),
        (json!("1_000"), 1000),
        (json!("3.5"), 0),
        (json!(null), 0),
        (json!([1]), 0),
        (json!({"a": 1}), 0),
    ] {
        profile.achievement_stats.insert("k".into(), value.clone());
        assert_eq!(int_stat(&mut profile, "k"), expected, "{value}");
    }
    assert_eq!(int_stat(&mut profile, "missing"), 0);
}

#[test]
fn list_stats_normalise_to_strings_and_count_unique_values() {
    let mut profile = TestProfile::default();
    profile
        .achievement_stats
        .insert("states".into(), json!(["Ohio", 7, true, null, 2.5]));
    assert_eq!(
        list_stat(&mut profile, "states"),
        vec!["Ohio", "7", "True", "None", "2.5"]
    );
    // The normalised list is written back, as the Python list_stat did.
    assert_eq!(
        profile.achievement_stats["states"],
        json!(["Ohio", "7", "True", "None", "2.5"])
    );
    assert_eq!(add_unique_stat(&mut profile, "states", "Ohio"), 5);
    assert_eq!(add_unique_stat(&mut profile, "states", "Indiana"), 6);
    profile
        .achievement_stats
        .insert("states".into(), json!("corrupt"));
    assert_eq!(list_stat(&mut profile, "states"), Vec::<String>::new());
    assert_eq!(add_unique_stat(&mut profile, "states", "Ohio"), 1);
}

#[test]
fn bool_stats_follow_python_truthiness() {
    let mut profile = TestProfile::default();
    assert!(!bool_stat(&mut profile, "seen"));
    set_bool_stat(&mut profile, "seen");
    assert!(bool_stat(&mut profile, "seen"));
    profile.achievement_stats.insert("seen".into(), json!(0));
    assert!(!bool_stat(&mut profile, "seen"));
    profile
        .achievement_stats
        .insert("seen".into(), json!("yes"));
    assert!(bool_stat(&mut profile, "seen"));
    reset_stat(&mut profile, "streak");
    assert_eq!(profile.achievement_stats["streak"], json!(0));
}

#[test]
fn award_records_once_and_refuses_an_unknown_id() {
    let mut profile = TestProfile::default();
    let first = award(&mut profile, "first_delivery").unwrap();
    assert_eq!(first.achievement.id, "first_delivery");
    assert_eq!(
        first.message,
        achievement_unlocked(first.achievement.name, first.achievement.description)
    );
    assert!(award(&mut profile, "first_delivery").is_none());
    assert_eq!(profile.achievements, vec!["first_delivery"]);
    assert_eq!(
        earned_ids(&profile),
        HashSet::from(["first_delivery".to_string()])
    );
    assert!(award(&mut profile, "no_such_badge").is_none());
}

#[test]
fn test_retired_first_run_badges_still_export_to_the_cloud_validator() {
    // Deleting an id breaks the allow-list for anyone who already earned it.
    // first_dispatch, first_pickup, and air_ready are retired as awards but
    // keep their catalog entries and ids for exactly this reason. (The
    // second half -- that the invariant bundle's achievementIds carries
    // them -- lives with profile_integrity_invariants, which takes the id
    // list as an input.)
    for badge_id in ["first_dispatch", "first_pickup", "air_ready"] {
        assert!(achievement_by_id(badge_id).is_some(), "{badge_id}");
    }
}

#[test]
fn test_the_funny_ones_are_actually_in_the_catalog() {
    // They are jokes, but they are shipped jokes and they follow the copy rules.
    for badge_id in [
        "sixty_nine_mph",
        "eighty_eight_mph",
        "sixteen_tons",
        "brake_smoke",
        "one_for_the_road",
    ] {
        let badge = achievement_by_id(badge_id).unwrap();
        // artist and title, both named
        assert!(badge.inspiration.matches(" - ").count() >= 1);
        assert!(!badge.description.trim().is_empty());
    }
}

#[test]
fn test_every_badge_cites_a_song() {
    // The catalog's whole voice rests on this; a new one must not break it.
    for badge in &ACHIEVEMENTS {
        let (artist, title) = badge.inspiration.split_once(" - ").unwrap();
        assert!(
            !artist.trim().is_empty() && !title.trim().is_empty(),
            "{}",
            badge.id
        );
    }
}

// -- tests/test_career_arc_achievements.py --------------------------------------

#[test]
fn test_new_arc_badges_exist_with_song_inspirations() {
    for badge_id in [
        "level_five",
        "level_ten",
        "level_fifteen",
        "level_twenty_five",
        "level_thirty",
        "fleet_upgrade",
        "fleet_flagship",
        "owner_operator_buyin",
        "authority_active",
        "three_trucks",
        "twenty_five_cities",
        "seventy_five_cities",
        "hundred_fifty_cities",
        "fifteen_states",
        "thirty_states",
        "dakota_delivery",
        "montana_delivery",
        "new_england_delivery",
        "self_paid_course",
    ] {
        assert!(achievement_by_id(badge_id).is_some(), "{badge_id}");
    }
    assert!(ACHIEVEMENTS.len() >= 130);
}

// -- tests/test_achievement_flavor_relocated.py ---------------------------------

#[test]
fn test_live_announce_is_name_only_in_both_modes() {
    let pair = achievement_unlocked("Night Owl", "You ran the small hours and kept it clean.");
    let live = achievement_announced("Night Owl");
    // The stored record keeps the flavor for the log and the menu...
    assert!(pair.normal.contains("kept it clean"));
    // ...but the live announce never speaks it, in either speech mode.
    assert_eq!(live.normal, "New achievement! Night Owl.");
    assert_eq!(live.render(true), "Night Owl.");
    assert!(!live.normal.contains("kept it clean"));
}

// -- App()-bound: the bodies drove DrivingState/ArrivalState/menus ---------------

/// Python: `app.ctx.award_achievement("first_delivery")` speaks
/// `achievement_announced(name)` on `say`, builds the full "New achievement!"
/// record, and lands that record in the message log.
#[test]
#[ignore = "needs app shell"]
fn test_award_speaks_the_short_line_and_logs_the_flavor() {
    unimplemented!("needs app shell: GameContext::award_achievement + message log");
}

/// Python: a second `award_achievement("first_delivery")` returns None, the
/// chime `ui/level_up` plays once, and `Profile.load` sees
/// `["first_delivery"]`.
#[test]
#[ignore = "needs app shell"]
fn test_award_achievement_persists_and_deduplicates_notification() {
    unimplemented!("needs app shell: GameContext::award_achievement + Profile::load");
}

/// Python: `award_achievement(..., event=True)` still speaks on the screen
/// reader channel, never on `say_event`.
#[test]
#[ignore = "needs app shell"]
fn test_event_achievement_speaks_through_screen_reader() {
    unimplemented!("needs app shell: GameContext::award_achievement(event=True)");
}

/// Python: the previous delivery ran the exact reverse lane; `ArrivalState`
/// awards `return_trip`, rewrites `last_route`, and pins `home_city`.
#[test]
#[ignore = "needs app shell"]
fn test_return_trip_badge_needs_the_reverse_of_the_last_route() {
    unimplemented!("needs app shell: DrivingState + ArrivalState");
}

/// Python: Main menu -> Achievements -> career picker -> category menu ->
/// "Out on the Road" holds "Earned: Signed..." and "Career and Rank" holds
/// "Locked: Breaker, Breaker".
#[test]
#[ignore = "needs app shell"]
fn test_main_menu_achievement_path_is_keyboard_accessible() {
    unimplemented!("needs app shell: main_menu achievement states");
}

/// Python: the Deep Cuts category with nothing earned announces
/// "Deep Cuts. 0 of N earned." and every row reads the hidden name.
#[test]
#[ignore = "needs app shell"]
fn test_category_with_nothing_earned_still_reads_naturally() {
    unimplemented!("needs app shell: AchievementCategoryState");
}

/// Python: a first-ever `ArrivalState` earns first_delivery alone; the
/// settlement names it without its flavor paragraph.
#[test]
#[ignore = "needs app shell"]
fn test_delivery_settlement_awards_only_first_delivery_on_a_first_run() {
    unimplemented!("needs app shell: ArrivalState settlement");
}

/// Python: first_on_time/clean_delivery/speed_limit_saint land on runs
/// 2/3/4; five_deliveries on run 5.
#[test]
#[ignore = "needs app shell"]
fn test_rookie_chain_achievements_clear_their_delivery_floors() {
    unimplemented!("needs app shell: repeated ArrivalState deliveries");
}

/// Python: completing the pickup awards the merged first_day badge.
#[test]
#[ignore = "needs app shell"]
fn test_pickup_completion_awards_the_merged_first_day_badge() {
    unimplemented!("needs app shell: PickupFacilityState");
}

/// Python: eastbound_delivery fires only when the destination lies east.
#[test]
#[ignore = "needs app shell"]
fn test_eastbound_badge_fires_only_on_an_eastbound_delivery() {
    unimplemented!("needs app shell: ArrivalState");
}

/// Python: a suppressed award collects without the chime or speech.
#[test]
#[ignore = "needs app shell"]
fn test_suppressed_award_collects_without_chime_or_speech() {
    unimplemented!("needs app shell: GameContext::award_achievement(suppress)");
}

/// Python: the state-line crossing keeps its gameplay prompt ahead of the
/// achievement announce.
#[test]
#[ignore = "needs app shell"]
fn test_state_crossing_keeps_gameplay_prompt_before_achievement() {
    unimplemented!("needs app shell: DrivingState trip events");
}

/// Python: sixty-nine has to be HELD for a mile, not passed through.
#[test]
#[ignore = "needs app shell"]
fn test_the_number_that_means_nothing_takes_a_whole_mile() {
    unimplemented!("needs app shell: DrivingState::_track_driving_badges");
}

#[test]
#[ignore = "needs app shell"]
fn test_eighty_eight_miles_an_hour_is_noticed() {
    unimplemented!("needs app shell: DrivingState::_track_driving_badges");
}

/// Python: one touch of the service brake restarts the jake-only descent.
#[test]
#[ignore = "needs app shell"]
fn test_a_jake_only_descent_is_ruined_by_one_touch_of_the_brake() {
    unimplemented!("needs app shell: DrivingState::_track_driving_badges");
}

#[test]
#[ignore = "needs app shell"]
fn test_cooking_the_drums_is_its_own_badge() {
    unimplemented!("needs app shell: DrivingState::_track_driving_badges");
}

/// Python: holding a station across three states, and a catch past 1.3x
/// the flat contour; 1.05x is not a fringe catch.
#[test]
#[ignore = "needs app shell"]
fn test_the_radio_badges_follow_the_signal() {
    unimplemented!("needs app shell: DrivingState::_track_radio_badges");
}

#[test]
#[ignore = "needs app shell"]
fn test_a_new_station_restarts_the_three_state_tally() {
    unimplemented!("needs app shell: DrivingState::_track_radio_badges");
}
