//! A career copied from another computer records where it came from; anything
//! that could be an edit forgets it.

use std::sync::{Arc, Mutex};

use serde_json::{json, Map, Value};

use super::origin::{cloud_content, forget_origin, origin_for, record_origin};
use super::tests::{load, read_save, with_data_dir, write_packed};
use super::*;

/// Move to "another computer": the same data directory, a different key.
fn switch_computers() {
    std::fs::write(signing::secret_path(), "ab".repeat(32)).unwrap();
}

fn upload_hash(dict: &Map<String, Value>) -> String {
    cloud_content(&Value::Object(dict.clone())).1
}

/// A career with floats, nested maps, unicode and a trip under way, so any
/// JSON round-trip difference between the upload and the file would show.
fn busy_career(name: &str) -> Profile {
    let mut p = Profile::named(name);
    p.set_money(12_345.678_9);
    p.career.total_earnings = 98_765.432_1;
    p.achievements = vec!["first_delivery".into(), "night_owl".into()];
    p.active_trip = Some(json!({
        "origin": "Amarillo, TX",
        "note": "Caf\u{e9} stop \u{1f69a}",
        "odometer": 0.1,
        "tiny": 1e-7,
        "big": 123_456_789.123_456_7,
        "whole": 5.0,
        "legs": [{"id": 3, "grade": -0.035}, {"id": 4, "grade": 2.5e-3}],
    }));
    p
}

#[test]
fn test_a_copied_career_records_the_hash_the_old_computer_uploaded() {
    with_data_dir(|_| {
        // What the old computer's save listener hands the cloud backup.
        let uploaded: Arc<Mutex<Vec<Map<String, Value>>>> = Arc::default();
        let sink = uploaded.clone();
        set_save_listener(Some(Arc::new(move |p: &Profile| {
            sink.lock().unwrap().push(p.to_dict());
        })));
        let original = busy_career("Road Star");
        let path = original.save().unwrap();
        set_save_listener(None);
        let expected = upload_hash(&uploaded.lock().unwrap()[0]);
        assert_eq!(expected, upload_hash(&original.to_dict()));

        switch_computers();
        let loaded = load(&path);

        assert!(loaded.integrity_modified);
        assert_eq!(origin_for("Road Star"), Some(expected));
        // Reloading the now locally signed copy keeps the record.
        let _ = load(&path);
        assert!(origin_for("Road Star").is_some());
    });
}

#[test]
fn test_nothing_is_recorded_for_an_unsigned_file() {
    with_data_dir(|_| {
        let path = busy_career("Unsigned").save().unwrap();
        let mut data = read_save(&path);
        data.remove(SIGNATURE_FIELD);
        data.remove(SIGNATURE_VERSION_FIELD);
        write_packed(&path, &data);

        assert!(load(&path).integrity_modified);
        assert_eq!(origin_for("Unsigned"), None);
    });
}

#[test]
fn test_nothing_is_recorded_for_impossible_money() {
    with_data_dir(|_| {
        let mut p = busy_career("Fortune");
        p.career.total_earnings = 338.36;
        p.set_money(999_999_999_999.0);
        let path = p.save().unwrap();
        switch_computers();

        assert!(load(&path).integrity_modified);
        assert_eq!(origin_for("Fortune"), None);
    });
}

#[test]
fn test_nothing_is_recorded_for_a_file_already_marked() {
    with_data_dir(|_| {
        let mut p = busy_career("Marked");
        p.integrity_modified = true;
        let path = p.save().unwrap();
        switch_computers();

        assert!(load(&path).integrity_modified);
        assert_eq!(origin_for("Marked"), None);
    });
}

#[test]
fn test_an_edit_after_the_copy_forgets_the_origin() {
    with_data_dir(|_| {
        let path = busy_career("Copied").save().unwrap();
        switch_computers();
        let _ = load(&path);
        assert!(origin_for("Copied").is_some());

        // Hand-edit the copy: it already carries the mark, so nothing new is
        // recorded, and the old record must not vouch for the edit.
        let mut data = read_save(&path);
        data.insert("money".into(), json!(20_000.0));
        write_packed(&path, &data);
        let _ = load(&path);
        assert_eq!(origin_for("Copied"), None);
    });
}

#[test]
fn test_a_money_guard_divergence_forgets_the_origin() {
    with_data_dir(|_| {
        let path = busy_career("Guarded").save().unwrap();
        switch_computers();
        let mut loaded = load(&path);
        assert!(origin_for("Guarded").is_some());

        // Written behind the guard's back, then a transaction audits it.
        loaded.money = 50_000.0;
        loaded.earn(10.0);
        assert_eq!(origin_for("Guarded"), None);

        // The save path catches it too, before any transaction.
        record_origin("Guarded", &"0".repeat(64));
        loaded.money = 60_000.0;
        loaded.save().unwrap();
        assert_eq!(origin_for("Guarded"), None);
    });
}

#[test]
fn test_absolution_and_delete_forget_the_origin() {
    with_data_dir(|_| {
        let path = busy_career("Absolved").save().unwrap();
        switch_computers();
        let mut loaded = load(&path);
        assert!(origin_for("Absolved").is_some());

        loaded.absolve();
        assert!(!loaded.integrity_modified);
        assert_eq!(origin_for("Absolved"), None);

        record_origin("Absolved", &"1".repeat(64));
        loaded.delete();
        assert_eq!(origin_for("Absolved"), None);
        forget_origin("never recorded");
    });
}
