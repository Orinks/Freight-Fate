//! Save-format migrations: upgrade older save dicts to the current shape
//! (port of `freight_fate/models/save_migration.py`).
//!
//! `Profile::from_dict` runs [`migrate_save_data`] on every raw save dict
//! before parsing, so all entry points -- disk loads, cloud restores -- see the
//! current schema. Each migration works on the plain dict, never on a Profile
//! instance, and must tolerate missing or malformed fields: an old save that
//! survived loading before must keep loading after.

use serde_json::{Map, Value};

/// Flat per-profile condition fields written by save versions 4 and earlier,
/// before each owned truck kept its own record.
pub const LEGACY_TRUCK_FIELDS: [&str; 4] = [
    "truck_fuel_gal",
    "truck_damage_pct",
    "tire_wear_pct",
    "road_grime_pct",
];

/// `float(value or default)` over a raw save field: numbers, bools and
/// numeric strings coerce; anything else (missing, null, an object) is the
/// default. Shared by the save-reading models (`loyalty`, `enforcement`).
pub(crate) fn json_f64(value: Option<&Value>, default: f64) -> f64 {
    match value {
        Some(Value::Number(n)) => n.as_f64().unwrap_or(default),
        Some(Value::Bool(b)) => {
            if *b {
                1.0
            } else {
                0.0
            }
        }
        Some(Value::String(s)) => s.trim().parse().unwrap_or(default),
        _ => default,
    }
}

/// `int(value or default)` over a raw save field, truncating a float the way
/// `int()` does.
pub(crate) fn json_i64(value: Option<&Value>, default: i64) -> i64 {
    match value {
        Some(Value::Number(n)) => n
            .as_i64()
            .or_else(|| n.as_f64().map(|f| f.trunc() as i64))
            .unwrap_or(default),
        Some(Value::Bool(b)) => i64::from(*b),
        Some(Value::String(s)) => s.trim().parse().unwrap_or(default),
        _ => default,
    }
}

/// A JSON number that Python would have read as an `int` (not a float, not
/// a bool).
fn int_version(value: Option<&Value>) -> Option<i64> {
    match value {
        Some(Value::Number(n)) if n.is_i64() || n.is_u64() => n.as_i64(),
        _ => None,
    }
}

/// Return `(data upgraded to the current shape, whether anything changed)`.
pub fn migrate_save_data(data: Map<String, Value>) -> (Map<String, Value>, bool) {
    if let Some(version) = int_version(data.get("version")) {
        if version >= 5 {
            return (data, false);
        }
    }
    (migrate_to_per_truck_conditions(data), true)
}

/// Pre-per-truck save: flag the conversion, and leave the records to the
/// profile.
///
/// The fan-out itself lives in `profile._migrate_flat_conditions`, which is
/// the authority on a condition record's shape on this line -- it also carries
/// brake wear, engine wear and traction gear, which this module's older
/// four-field record knew nothing about. Building the records here would
/// satisfy the profile's "already migrated?" check with a record missing those
/// fields, and the wear would be lost on every legacy save. The flat fields are
/// deliberately left in place for that fan-out to read.
fn migrate_to_per_truck_conditions(mut data: Map<String, Value>) -> Map<String, Value> {
    data.insert("migration_notice_pending".to_string(), Value::Bool(true));
    data
}

#[cfg(test)]
mod tests {
    //! Ported from the pure cases of `tests/test_save_migration.py`; the rest
    //! of that file drives Profile.load, the truck shop and the notice
    //! screens.

    use super::*;
    use serde_json::json;

    fn map(value: Value) -> Map<String, Value> {
        value.as_object().expect("an object").clone()
    }

    #[test]
    fn test_migration_respects_long_range_tank_upgrade() {
        // The save_migration half: a version-4 save is flagged for conversion
        // and its flat fields are left for the profile's fan-out to read. The
        // fan-out assertions themselves need models::profile and trucks.
        let data = map(json!({
            "version": 4,
            "truck": "heavy_hauler",
            "business_status": "leased_owner_operator",
            "owned_trucks": ["rig", "heavy_hauler"],
            "upgrades": {"long_range_tank": 1},
            "truck_fuel_gal": 240.0,
        }));
        let (migrated, changed) = migrate_save_data(data);
        assert!(changed);
        assert_eq!(migrated["migration_notice_pending"], Value::Bool(true));
        assert_eq!(migrated["truck_fuel_gal"], 240.0);
        assert_eq!(migrated["version"], 4);
        // Nothing is stripped here; the profile reads and removes the flat
        // fields itself.
        assert!(LEGACY_TRUCK_FIELDS.contains(&"truck_fuel_gal"));
        assert!(migrated.contains_key("truck_fuel_gal"));
    }

    #[test]
    fn test_current_saves_pass_through_unchanged() {
        let data = map(json!({"version": 11, "name": "Modern"}));
        let (migrated, changed) = migrate_save_data(data.clone());
        assert!(!changed);
        assert_eq!(migrated, data);
        let (five, changed) = migrate_save_data(map(json!({"version": 5})));
        assert!(!changed);
        assert!(!five.contains_key("migration_notice_pending"));
    }

    #[test]
    fn a_missing_or_non_integer_version_migrates() {
        // `isinstance(version, int)`: a float, a string, a bool or nothing at
        // all is not a current save.
        for version in [json!(null), json!("11"), json!(11.0), json!(true)] {
            let mut data = Map::new();
            if !version.is_null() {
                data.insert("version".to_string(), version.clone());
            }
            let (migrated, changed) = migrate_save_data(data);
            assert!(changed, "{version:?}");
            assert_eq!(migrated["migration_notice_pending"], Value::Bool(true));
        }
    }

    #[test]
    #[ignore = "needs models::profile (Profile.load)"]
    fn test_pre_condition_1_9_save_converts_to_per_truck_records() {}

    #[test]
    #[ignore = "needs models::profile (Profile.load)"]
    fn test_pre_condition_1_9_save_is_rewritten_to_disk_on_load() {}

    #[test]
    #[ignore = "needs models::profile (Profile.load)"]
    fn test_signed_flat_condition_save_is_not_quarantined() {}

    #[test]
    #[ignore = "needs models::profile (Profile.load)"]
    fn test_migration_clamps_impossible_legacy_values() {}

    #[test]
    #[ignore = "needs states::save_notice and the app shell"]
    fn test_migration_notice_shows_once_then_enters_world() {}

    #[test]
    #[ignore = "needs states::save_notice and the app shell"]
    fn test_migration_notice_escape_also_acknowledges() {}

    #[test]
    #[ignore = "needs states::save_notice and the app shell"]
    fn test_modified_notice_shows_once_then_enters_world() {}

    #[test]
    #[ignore = "needs states::city (TruckShopState) and the app shell"]
    fn test_bought_truck_starts_fresh_and_each_keeps_its_own_condition() {}

    #[test]
    #[ignore = "needs models::profile and profile_invariants"]
    fn test_invariants_flag_bad_per_truck_records() {}

    #[test]
    #[ignore = "needs models::profile (save/load)"]
    fn test_condition_round_trips_through_save_and_load() {}

    #[test]
    #[ignore = "needs models::profile (save/load)"]
    fn test_unknown_truck_key_condition_is_preserved() {}
}
