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
    let restored = AccountAchievements::load(temp.path());
    assert_eq!(restored.earned_at("midnight_delivery"), Some(100));
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
fn loaded_ledger_discards_invented_achievement_ids() {
    let temp = tempfile::tempdir().unwrap();
    std::fs::write(
        temp.path().join("account-achievements.json"),
        r#"{"version":1,"achievements":{"first_delivery":100,"invented_achievement":200}}"#,
    )
    .unwrap();

    let ledger = AccountAchievements::load(temp.path());

    assert_eq!(ledger.ids(), vec!["first_delivery"]);
}

#[test]
fn imported_career_discards_invented_achievement_ids() {
    let temp = tempfile::tempdir().unwrap();
    let mut ledger = AccountAchievements::empty(temp.path());
    let profile = profile_with_achievements(
        "Invented Badge",
        &["first_delivery", "invented_achievement"],
    );

    assert_eq!(ledger.merge_profile(&profile).unwrap(), 1);
    assert_eq!(ledger.ids(), vec!["first_delivery"]);
}

#[test]
fn failed_write_leaves_the_ledger_ready_for_a_successful_retry() {
    let temp = tempfile::tempdir().unwrap();
    let blocked_data_dir = temp.path().join("blocked-data-dir");
    std::fs::write(&blocked_data_dir, b"this is a file, not a directory").unwrap();
    let mut ledger = AccountAchievements::empty(&blocked_data_dir);

    assert!(ledger.record("first_delivery", Some(100)).is_err());
    assert!(ledger.ids().is_empty());

    std::fs::remove_file(&blocked_data_dir).unwrap();
    std::fs::create_dir(&blocked_data_dir).unwrap();
    assert!(ledger.record("first_delivery", Some(100)).unwrap());
    assert_eq!(
        AccountAchievements::load(&blocked_data_dir).ids(),
        vec!["first_delivery"]
    );
}

#[test]
fn startup_preserves_malformed_and_newer_ledger_files() {
    for (name, bytes) in [
        ("malformed", b"not JSON at all".as_slice()),
        (
            "newer",
            br#"{"version":2,"local_profile_migration_version":0,"achievements":{"first_delivery":100}}"#
                .as_slice(),
        ),
    ] {
        let temp = TempDir::new(&format!("account-achievements-{name}"));
        let data_dir = temp.path().join("data");
        std::fs::create_dir_all(&data_dir).unwrap();
        let ledger_path = data_dir.join("account-achievements.json");
        std::fs::write(&ledger_path, bytes).unwrap();
        let _data_dir = DataDirGuard::pin(data_dir);
        let capture = Rc::new(RefCell::new(CaptureSpeech::new()));
        let app = App::new_headless(Box::new(freight_fate::app::testing::SharedCapture(
            Rc::clone(&capture),
        )));

        assert_eq!(std::fs::read(&ledger_path).unwrap(), bytes, "{name}");
        assert!(app.ctx.account_achievements.ids().is_empty(), "{name}");
        assert!(capture.borrow().main_lines().is_empty(), "{name}");
        assert!(capture.borrow().event_lines().is_empty(), "{name}");
    }
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
