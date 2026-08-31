use std::cell::RefCell;
use std::io;
use std::rc::Rc;

use ff_core::models::profile::Profile;
use freight_fate::account_achievements::AccountAchievements;
use freight_fate::app::testing::{DataDirGuard, TempDir};
use freight_fate::app::App;
use freight_fate::speech::CaptureSpeech;

fn profile_with_achievements(name: &str, achievements: &[&str]) -> Profile {
    let mut profile = Profile::named(name);
    profile.achievements = achievements.iter().map(|id| (*id).to_string()).collect();
    profile
}

#[test]
fn account_collection_persists_valid_achievements_and_their_times() {
    let temp = tempfile::tempdir().unwrap();
    let mut ledger = AccountAchievements::empty(temp.path());

    assert!(ledger.record("first_delivery", Some(200)).unwrap());

    let restored = AccountAchievements::load(temp.path());
    assert_eq!(restored.ids(), vec!["first_delivery"]);
    assert_eq!(restored.earned_at("first_delivery"), Some(200));
}

#[test]
fn account_collection_unions_careers_without_changing_them() {
    let temp = tempfile::tempdir().unwrap();
    let mut ledger = AccountAchievements::empty(temp.path());
    let first = profile_with_achievements("one", &["first_delivery"]);
    let second = profile_with_achievements("two", &["first_delivery", "midnight_delivery"]);

    assert_eq!(ledger.merge_profile(&first).unwrap(), 1);
    assert_eq!(ledger.merge_profile(&second).unwrap(), 1);
    assert_eq!(ledger.ids(), vec!["first_delivery", "midnight_delivery"]);
    assert_eq!(first.achievements, vec!["first_delivery"]);
    assert_eq!(
        second.achievements,
        vec!["first_delivery", "midnight_delivery"]
    );
}

#[test]
fn duplicate_recording_returns_false_without_adding_a_second_id() {
    let temp = tempfile::tempdir().unwrap();
    let mut ledger = AccountAchievements::empty(temp.path());

    assert!(ledger.record("midnight_delivery", Some(200)).unwrap());
    assert!(!ledger.record("midnight_delivery", None).unwrap());
    assert_eq!(ledger.ids(), vec!["midnight_delivery"]);
}

#[test]
fn duplicate_recording_keeps_the_earliest_known_time() {
    let temp = tempfile::tempdir().unwrap();
    let mut ledger = AccountAchievements::empty(temp.path());

    assert!(ledger.record("midnight_delivery", Some(200)).unwrap());
    assert!(!ledger.record("midnight_delivery", Some(100)).unwrap());
    assert_eq!(ledger.earned_at("midnight_delivery"), Some(100));
}

#[test]
fn invalid_achievement_ids_are_rejected_without_being_retained() {
    let temp = tempfile::tempdir().unwrap();
    let mut ledger = AccountAchievements::empty(temp.path());

    let error = ledger
        .record("invented_achievement", Some(200))
        .unwrap_err();

    assert_eq!(error.kind(), io::ErrorKind::InvalidInput);
    assert!(ledger.ids().is_empty());
    assert!(!temp.path().join("account-achievements.json").exists());
}

#[test]
fn startup_migration_is_silent_non_mutating_and_skips_unreadable_careers() {
    let temp = TempDir::new("account-achievements-startup");
    let _data_dir = DataDirGuard::pin(temp.path().join("data"));
    let profile = profile_with_achievements("Migration Driver", &["first_delivery"]);
    profile.save().unwrap();
    std::fs::write(
        ff_core::models::profile::profiles_dir().join("Unreadable.ffsave"),
        b"not a Freight Fate save",
    )
    .unwrap();

    let capture = Rc::new(RefCell::new(CaptureSpeech::new()));
    let app = App::new_headless(Box::new(freight_fate::app::testing::SharedCapture(
        Rc::clone(&capture),
    )));

    assert_eq!(app.ctx.account_achievements.ids(), vec!["first_delivery"]);
    assert!(capture.borrow().main_lines().is_empty());
    assert!(capture.borrow().event_lines().is_empty());
    assert!(app.ctx.services.journal.items().is_empty());
    assert_eq!(
        Profile::load(&profile.path()).unwrap().achievements,
        vec!["first_delivery"]
    );
    drop(app);

    profile_with_achievements("Later Career", &["midnight_delivery"])
        .save()
        .unwrap();
    let second_capture = Rc::new(RefCell::new(CaptureSpeech::new()));
    let second_app = App::new_headless(Box::new(freight_fate::app::testing::SharedCapture(
        Rc::clone(&second_capture),
    )));
    assert_eq!(
        second_app.ctx.account_achievements.ids(),
        vec!["first_delivery"]
    );
    assert!(second_capture.borrow().main_lines().is_empty());
    assert!(second_capture.borrow().event_lines().is_empty());
    assert!(second_app.ctx.services.journal.items().is_empty());
}
