//! Ported from the profile half of `tests/test_models.py`,
//! `tests/test_per_truck_condition.py`, `tests/test_loyalty_integration.py`,
//! `tests/test_legacy_career_gate.py` (the gate; the menu cases are ignored)
//! and `tests/test_version.py`.
//!
//! `isolated_data_dir` is [`with_data_dir`]: a temp `FREIGHT_FATE_DATA_DIR`
//! under the crate-wide environment lock.

use std::path::{Path, PathBuf};

use serde_json::{json, Value};

use super::*;
use crate::models::business::{business_status_summary, LEASED_OWNER_OPERATOR};
use crate::models::career_ladder::STARTER_CARRIER_NAME;
use crate::models::loyalty::LoyaltyAccount;
use crate::settings::paths::ENV_LOCK;
use crate::sim::vehicle::TruckState;

struct EnvGuard {
    _lock: std::sync::MutexGuard<'static, ()>,
    previous: Option<std::ffi::OsString>,
    previous_skip: Option<std::ffi::OsString>,
    _tmp: tempfile::TempDir,
}

impl Drop for EnvGuard {
    fn drop(&mut self) {
        match self.previous.take() {
            Some(old) => std::env::set_var(DATA_DIR_ENV, old),
            None => std::env::remove_var(DATA_DIR_ENV),
        }
        match self.previous_skip.take() {
            Some(old) => std::env::set_var("FREIGHT_FATE_SKIP_SAVE_SIGNING", old),
            None => std::env::remove_var("FREIGHT_FATE_SKIP_SAVE_SIGNING"),
        }
    }
}

/// `isolated_data_dir`: keep saves and settings out of the real user data
/// directory, one test at a time (the variable is process-global).
pub(crate) fn with_data_dir<T>(body: impl FnOnce(&Path) -> T) -> T {
    let lock = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let tmp = tempfile::tempdir().expect("a temp dir");
    let dir = tmp.path().join("data");
    let guard = EnvGuard {
        _lock: lock,
        previous: std::env::var_os(DATA_DIR_ENV),
        previous_skip: std::env::var_os("FREIGHT_FATE_SKIP_SAVE_SIGNING"),
        _tmp: tmp,
    };
    std::env::set_var(DATA_DIR_ENV, &dir);
    std::env::remove_var("FREIGHT_FATE_SKIP_SAVE_SIGNING");
    let result = body(&dir);
    drop(guard);
    result
}

/// The profile dict inside a save file, packed or legacy.
pub(super) fn read_save(path: &Path) -> Map<String, Value> {
    decode_save_bytes(&std::fs::read(path).unwrap()).unwrap().0
}

pub(super) fn write_packed(path: &Path, data: &Map<String, Value>) {
    std::fs::write(path, encode_save_bytes(data)).unwrap();
}

pub(super) fn write_text(path: &Path, data: &Map<String, Value>) {
    std::fs::write(
        path,
        serde_json::to_string(&Value::Object(data.clone())).unwrap(),
    )
    .unwrap();
}

pub(super) fn with_suffix(path: &Path, suffix: &str) -> PathBuf {
    let mut text = path.to_string_lossy().to_string();
    if let Some(idx) = text.rfind(SAVE_SUFFIX) {
        text.truncate(idx);
    } else if let Some(idx) = text.rfind(".json") {
        text.truncate(idx);
    }
    PathBuf::from(format!("{text}{suffix}"))
}

pub(super) fn load(path: &Path) -> Profile {
    Profile::load(path).unwrap()
}

// -- tests/test_models.py: profile -----------------------------------------------

#[test]
fn test_profile_roundtrip() {
    with_data_dir(|_| {
        let mut p = Profile::named("Roundtrip Test");
        p.money = 1234.5;
        p.career.xp = 2600.0;
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.carrier_name = "Test Carrier".to_string();
        p.calendar_offset_days = 147;
        let path = p.save().unwrap();
        let loaded = load(&path);
        assert_eq!(loaded.money, 1234.5);
        assert_eq!(loaded.career.level(), 3);
        assert_eq!(loaded.business_status, LEASED_OWNER_OPERATOR);
        assert_eq!(loaded.carrier_name, "Test Carrier");
        assert_eq!(loaded.name, "Roundtrip Test");
        assert_eq!(loaded.calendar_offset_days, 147);
    });
}

#[test]
fn test_profile_save_is_packed_and_versioned() {
    with_data_dir(|_| {
        let p = Profile::named("Atomic");
        let path = p.save().unwrap();
        assert_eq!(path.extension().unwrap(), "ffsave");
        assert!(std::fs::read(&path).unwrap().starts_with(SAVE_MAGIC));
        let data = read_save(&path);
        assert_eq!(data["version"], json!(SAVE_VERSION));
        assert!(data.contains_key(SIGNATURE_FIELD));
        assert!(!with_suffix(&path, ".ffsave.tmp").exists());
    });
}

#[test]
fn test_old_save_without_business_status_loads_as_company_driver() {
    with_data_dir(|_| {
        let p = Profile::named("Old Business");
        let mut data = p.to_dict();
        data.remove("business_status");
        data.remove(SIGNATURE_FIELD);
        let path = p.path();
        write_text(&path, &data);

        let loaded = load(&path);

        assert_eq!(loaded.business_status, COMPANY_DRIVER);
        assert!(business_status_summary(&loaded).contains(STARTER_CARRIER_NAME));
    });
}

#[test]
fn test_independent_authority_status_round_trips() {
    with_data_dir(|_| {
        let mut p = Profile::named("Authority Save");
        p.business_status = INDEPENDENT_AUTHORITY.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        p.owned_trailers = vec!["dry_van".to_string(), "reefer".to_string()];
        let path = p.save().unwrap();

        let loaded = load(&path);

        assert_eq!(loaded.business_status, INDEPENDENT_AUTHORITY);
        assert!(loaded.owns_equipment());
        assert_eq!(loaded.visible_owned_trailers(), vec!["dry_van", "reefer"]);
    });
}

#[test]
fn test_old_save_without_carrier_loads_with_starter_company() {
    with_data_dir(|_| {
        let p = Profile::named("Old Carrier");
        let mut data = p.to_dict();
        data.remove("carrier_name");
        data.remove(SIGNATURE_FIELD);
        let path = p.path();
        write_text(&path, &data);

        let loaded = load(&path);

        assert_eq!(loaded.carrier_name, STARTER_CARRIER_NAME);
    });
}

#[test]
fn test_old_owner_operator_save_without_trailer_programs_gets_basic_program() {
    with_data_dir(|_| {
        let mut p = Profile::named("Old Trailer Program");
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.owned_trucks = vec!["rig".to_string()];
        let mut data = p.to_dict();
        data.remove("trailer_programs");
        data.remove(SIGNATURE_FIELD);
        let path = p.path();
        write_text(&path, &data);

        let loaded = load(&path);

        assert_eq!(loaded.business_status, LEASED_OWNER_OPERATOR);
        assert_eq!(loaded.active_trailer_programs(), vec!["dry_van"]);
    });
}

#[test]
fn test_old_save_without_start_choice_fields_uses_northstar_company_start() {
    with_data_dir(|_| {
        let p = Profile::named("Old Start");
        let mut data = p.to_dict();
        data.remove("carrier_key");
        data.remove("start_mode");
        data.remove(SIGNATURE_FIELD);
        let path = p.path();
        write_text(&path, &data);

        let loaded = load(&path);

        assert_eq!(loaded.carrier_key, DEFAULT_START_KEY);
        assert_eq!(loaded.start_mode, START_MODE_COMPANY);
        assert_eq!(loaded.business_status, COMPANY_DRIVER);
    });
}

#[test]
fn test_old_save_without_authority_readiness_loads_with_default() {
    with_data_dir(|_| {
        let p = Profile::named("Old Authority");
        let mut data = p.to_dict();
        data.remove("authority_readiness");
        data.remove(SIGNATURE_FIELD);
        let path = p.path();
        write_text(&path, &data);

        let loaded = load(&path);

        assert!(!loaded.authority_readiness);
    });
}

#[test]
fn test_profile_ignores_unknown_fields() {
    with_data_dir(|_| {
        let p = Profile::named("Future");
        let path = p.save().unwrap();
        let mut data = read_save(&path);
        data.insert("mystery_field".to_string(), json!(42));
        write_packed(&path, &data);
        let loaded = load(&path);
        assert_eq!(loaded.name, "Future");
        // v3 signs every key the file carries, so a hand-added unknown field is
        // an out-of-game edit like any other: the save still loads, but marks.
        assert!(loaded.integrity_modified);
    });
}

#[test]
fn test_tampered_money_loads_but_marks_profile_modified() {
    with_data_dir(|_| {
        let p = Profile::named("Tampered");
        let path = p.save().unwrap();
        let mut data = read_save(&path);
        data.insert("money".to_string(), json!(999_999.0));
        write_packed(&path, &data);

        let loaded = load(&path);
        assert!(loaded.integrity_modified);
        assert!(loaded.integrity_notice_pending);

        // The flag is signed into the rewritten save and survives a clean reload.
        let again = load(&path);
        assert!(again.integrity_modified);
    });
}

#[test]
fn test_modified_flag_is_sticky_against_hand_clearing() {
    with_data_dir(|_| {
        let p = Profile::named("Sticky");
        let path = p.save().unwrap();
        let mut data = read_save(&path);
        data.insert("money".to_string(), json!(999_999.0));
        write_packed(&path, &data);
        load(&path); // marks and re-signs

        let mut data = read_save(&path);
        data.insert("integrity_modified".to_string(), json!(false));
        data.insert("integrity_notice_pending".to_string(), json!(false));
        write_packed(&path, &data); // stale signature again

        assert!(load(&path).integrity_modified);
    });
}

#[test]
fn test_v2_save_signed_over_a_since_removed_field_still_validates() {
    // Saves from before 2026-07-20 carry road_grime_pct, which later left the
    // dataclass. v2 validation must use the field set those saves were signed
    // over, not today's -- recomputing without the departed field is how every
    // pre-grime-migration save got falsely flagged as changed outside the game.
    with_data_dir(|_| {
        let p = Profile::named("Grime Era");
        let path = p.save().unwrap();
        let mut data = read_save(&path);
        data.remove(SIGNATURE_FIELD);
        data.insert("road_grime_pct".to_string(), json!(12.5));
        data.insert(SIGNATURE_VERSION_FIELD.to_string(), json!(2));
        let signature = signature_for(&data, None);
        data.insert(SIGNATURE_FIELD.to_string(), json!(signature));
        write_packed(&path, &data);

        assert!(!load(&path).integrity_modified);
    });
}

#[test]
fn test_v3_signature_survives_future_field_removal() {
    // v3 signs what the file carries, so a key the current dataclass no longer
    // knows (a save written by a build whose field was since removed) can
    // never invalidate the signature again.
    with_data_dir(|_| {
        let p = Profile::named("Extinct Field");
        let path = p.save().unwrap();
        let mut data = read_save(&path);
        data.remove(SIGNATURE_FIELD);
        data.insert("some_retired_field".to_string(), json!("kept"));
        let signature = signature_for(&data, None);
        data.insert(SIGNATURE_FIELD.to_string(), json!(signature));
        write_packed(&path, &data);

        assert!(!load(&path).integrity_modified);
    });
}

#[test]
fn test_packed_save_with_stripped_signature_is_marked_modified() {
    with_data_dir(|_| {
        let p = Profile::named("Stripped");
        let path = p.save().unwrap();
        let mut data = read_save(&path);
        data.remove(SIGNATURE_FIELD);
        write_packed(&path, &data);

        assert!(load(&path).integrity_modified);
    });
}

#[test]
fn test_undecodable_save_is_quarantined() {
    with_data_dir(|_| {
        let p = Profile::named("Corrupt");
        let path = p.save().unwrap();
        std::fs::write(&path, [SAVE_MAGIC, b"not deflate data"].concat()).unwrap();

        assert!(matches!(Profile::load(&path), Err(LoadError::Integrity(_))));
        assert!(!path.exists());
        assert!(with_suffix(&path, ".ffsave.invalid").exists());
    });
}

#[test]
fn test_skip_signing_flag_loads_tampered_save_from_source() {
    with_data_dir(|_| {
        let p = Profile::named("Dev Tampered");
        let path = p.save().unwrap();
        let mut data = read_save(&path);
        data.insert("money".to_string(), json!(999_999.0));
        write_packed(&path, &data);

        std::env::set_var("FREIGHT_FATE_SKIP_SAVE_SIGNING", "1");
        let loaded = Profile::load_with(&path, false).unwrap();
        assert_eq!(loaded.money, 999_999.0);
        assert!(!loaded.integrity_modified);

        // The load re-signed the file, so it keeps working with the flag off.
        std::env::remove_var("FREIGHT_FATE_SKIP_SAVE_SIGNING");
        let reloaded = load(&path);
        assert_eq!(reloaded.money, 999_999.0);
        assert!(!reloaded.integrity_modified);
    });
}

#[test]
fn test_skip_signing_flag_is_ignored_in_frozen_builds() {
    with_data_dir(|_| {
        let p = Profile::named("Frozen Tampered");
        let path = p.save().unwrap();
        let mut data = read_save(&path);
        data.insert("money".to_string(), json!(999_999.0));
        write_packed(&path, &data);

        std::env::set_var("FREIGHT_FATE_SKIP_SAVE_SIGNING", "1");
        assert!(Profile::load_with(&path, true).unwrap().integrity_modified);
        std::env::remove_var("FREIGHT_FATE_SKIP_SAVE_SIGNING");
    });
}

#[test]
fn test_legacy_unsigned_json_save_keeps_amnesty_and_converts() {
    with_data_dir(|_| {
        let p = Profile::named("Unsigned");
        let mut data = p.to_dict();
        data.remove(SIGNATURE_FIELD);
        let legacy = p.path().with_extension("json");
        write_text(&legacy, &data);

        let loaded = load(&legacy);

        assert_eq!(loaded.name, "Unsigned");
        assert!(!loaded.integrity_modified);
        // Converted in place: packed and signed, old file kept as a rollback copy.
        let migrated = read_save(&p.path());
        assert!(migrated.contains_key(SIGNATURE_FIELD));
        assert!(!legacy.exists());
        assert!(legacy.with_extension("json.bak").exists());
    });
}

#[test]
fn test_list_saves_and_delete() {
    with_data_dir(|_| {
        let a = Profile::named("Driver A");
        a.save().unwrap();
        let b = Profile::named("Driver B");
        b.save().unwrap();
        let stems = || -> Vec<String> {
            Profile::list_saves()
                .iter()
                .map(|p| p.file_stem().unwrap().to_string_lossy().to_string())
                .collect()
        };
        let names = stems();
        assert!(names.contains(&"Driver A".to_string()));
        assert!(names.contains(&"Driver B".to_string()));
        a.delete();
        assert!(!stems().contains(&"Driver A".to_string()));
    });
}

#[test]
fn test_profile_name_sanitized_for_filesystem() {
    with_data_dir(|_| {
        let p = Profile::named("Sketchy/Name<>:\"|?*");
        let path = p.save().unwrap();
        assert!(path.exists());
    });
}

// -- tests/test_per_truck_condition.py -------------------------------------------

fn owner_operator_fleet() -> Profile {
    let mut p = Profile::named("Fleet");
    p.business_status = LEASED_OWNER_OPERATOR.to_string();
    p.truck = "rig".to_string();
    p.owned_trucks = vec!["rig".to_string(), "heavy_hauler".to_string()];
    p.provision_truck_condition("rig", Some(150.0));
    p.provision_truck_condition("heavy_hauler", Some(200.0));
    p
}

fn record_f64(p: &Profile, truck: &str, key: &str) -> f64 {
    p.truck_conditions[truck][key].as_f64().unwrap()
}

#[test]
fn test_wear_accrues_per_truck_not_across_the_fleet() {
    let mut p = owner_operator_fleet();

    p.set_tire_wear_pct(25.0); // wear the rig we're driving
    assert_eq!(p.active_truck_key(), "rig");
    assert_eq!(p.tire_wear_pct(), 25.0);

    p.truck = "heavy_hauler".to_string(); // switch tractors at the dealer
    assert_eq!(p.tire_wear_pct(), 0.0); // the other truck is untouched

    p.truck = "rig".to_string();
    assert_eq!(p.tire_wear_pct(), 25.0); // rig kept its wear
}

#[test]
fn test_switching_trucks_does_not_teleport_fuel_or_damage() {
    let mut p = owner_operator_fleet();
    p.set_truck_fuel_gal(40.0);
    p.set_truck_damage_pct(12.0);

    p.truck = "heavy_hauler".to_string();
    assert_eq!(p.truck_fuel_gal(), 200.0); // its own full tank, not the rig's 40
    assert_eq!(p.truck_damage_pct(), 0.0); // its own condition, not the rig's damage
}

#[test]
fn test_servicing_the_active_truck_leaves_parked_trucks_worn() {
    let mut p = owner_operator_fleet();
    p.truck_conditions["heavy_hauler"].insert("tire_wear_pct".into(), json!(40.0));
    p.set_tire_wear_pct(60.0);

    p.set_tire_wear_pct(0.0); // the garage services the truck we drove in

    assert_eq!(p.tire_wear_pct(), 0.0);
    assert_eq!(record_f64(&p, "heavy_hauler", "tire_wear_pct"), 40.0);
}

/// Tire compound and the chain set bolt to the truck: they follow a swap like
/// wear does, and records saved before the fields existed read as the
/// all-season, no-chains defaults.
#[test]
fn test_traction_equipment_rides_the_truck_record() {
    let mut p = owner_operator_fleet();
    p.set_tire_type("winter");
    p.set_chains_owned(true);
    p.set_chain_wear_pct(30.0);

    p.truck = "heavy_hauler".to_string(); // the other tractor has its own equipment
    assert_eq!(p.tire_type(), "all_season");
    assert!(!p.chains_owned());
    assert_eq!(p.chain_wear_pct(), 0.0);

    p.truck = "rig".to_string();
    assert_eq!(p.tire_type(), "winter");
    assert!(p.chains_owned());
    assert_eq!(p.chain_wear_pct(), 30.0);

    // A record written before the equipment fields existed: defaults apply.
    for key in ["tire_type", "chains_owned", "chain_wear_pct"] {
        p.truck_conditions["rig"].remove(key);
    }
    assert_eq!(p.tire_type(), "all_season");
    assert!(!p.chains_owned());
    assert_eq!(p.chain_wear_pct(), 0.0);
}

/// load/store round-trip: the compound reaches the TruckState, chain wear
/// accrued on the road comes back, and the compound choice stays garage-only.
#[test]
fn test_equipment_flows_through_the_truck_condition_funnel() {
    let mut p = owner_operator_fleet();
    p.set_tire_type("winter");
    p.set_chains_owned(true);

    let mut truck = TruckState::default();
    p.load_truck_condition(&mut truck);
    assert_eq!(truck.tire_type, "winter");
    assert_eq!(truck.chain_wear_pct, 0.0);

    truck.chain_wear_pct = 45.0; // a pass worth of chained miles
    p.store_truck_condition(&truck);
    assert_eq!(p.chain_wear_pct(), 45.0);
    assert_eq!(p.tire_type(), "winter");
    assert!(p.chains_owned()); // ownership is profile equipment, not physics state
}

#[test]
fn test_company_driver_condition_keys_under_the_assigned_rig() {
    let mut p = Profile::named("Company");
    p.business_status = COMPANY_DRIVER.to_string();
    p.truck = "heavy_hauler".to_string(); // stray value; company drivers still run "rig"

    assert_eq!(p.active_truck_key(), "rig");
    p.set_brake_wear_pct(12.0);

    assert_eq!(record_f64(&p, "rig", "brake_wear_pct"), 12.0);
    assert!(!p.truck_conditions.contains_key("heavy_hauler"));
}

#[test]
fn test_legacy_flat_condition_fans_out_to_every_owned_truck() {
    let value = json!({
        "name": "Legacy Fleet",
        "business_status": LEASED_OWNER_OPERATOR,
        "truck": "rig",
        "owned_trucks": ["rig", "heavy_hauler"],
        "tire_wear_pct": 30.0,
        "brake_wear_pct": 20.0,
        "engine_wear_pct": 10.0,
        "truck_damage_pct": 15.0,
        "truck_fuel_gal": 60.0,
    });
    let Value::Object(data) = value else {
        unreachable!()
    };

    let p = Profile::from_dict(&data);

    // The active truck inherits the whole flat set, fuel included.
    assert_eq!(p.active_truck_key(), "rig");
    assert_eq!(p.tire_wear_pct(), 30.0);
    assert_eq!(p.brake_wear_pct(), 20.0);
    assert_eq!(p.engine_wear_pct(), 10.0);
    assert_eq!(p.truck_damage_pct(), 15.0);
    assert_eq!(p.truck_fuel_gal(), 60.0);

    // The parked truck inherits the wear and damage (no free pristine spare)
    // but gets a full tank rather than the active truck's 60 gallons.
    assert_eq!(record_f64(&p, "heavy_hauler", "tire_wear_pct"), 30.0);
    assert_eq!(record_f64(&p, "heavy_hauler", "brake_wear_pct"), 20.0);
    assert_eq!(record_f64(&p, "heavy_hauler", "engine_wear_pct"), 10.0);
    assert_eq!(record_f64(&p, "heavy_hauler", "damage_pct"), 15.0);
    assert!(record_f64(&p, "heavy_hauler", "fuel_gal") > 60.0);
}

#[test]
fn test_per_truck_conditions_round_trip_and_stay_signed() {
    with_data_dir(|_| {
        let mut p = owner_operator_fleet();
        p.set_tire_wear_pct(22.0);
        p.truck_conditions["heavy_hauler"].insert("engine_wear_pct".into(), json!(5.0));

        let path = p.save().unwrap();
        let loaded = load(&path);

        assert_eq!(loaded.tire_wear_pct(), 22.0);
        assert_eq!(record_f64(&loaded, "heavy_hauler", "fuel_gal"), 200.0);
        assert_eq!(record_f64(&loaded, "heavy_hauler", "engine_wear_pct"), 5.0);
    });
}

/// Scrubbing wear out of a packed save does not go unnoticed.
///
/// Per-truck conditions are inside the signed payload, so a hand-edited
/// container fails its signature. Such a save is no longer quarantined -- it
/// loads and carries a sticky `integrity_modified` mark instead.
#[test]
fn test_tampering_per_truck_wear_marks_the_profile_modified() {
    with_data_dir(|_| {
        let mut p = Profile::named("Cheater Fleet");
        p.set_tire_wear_pct(50.0);
        let path = p.save().unwrap();

        let mut data = read_save(&path);
        data["truck_conditions"]["rig"]["tire_wear_pct"] = json!(0.0); // scrub the wear
        write_packed(&path, &data);

        let loaded = load(&path);
        assert!(loaded.integrity_modified);
        assert!(loaded.integrity_notice_pending);
        assert!(path.exists()); // marked, not quarantined
        assert!(!with_suffix(&path, ".ffsave.invalid").exists());

        // The mark is signed into the rewritten save and survives a clean reload.
        assert!(load(&path).integrity_modified);

        // Stripping the signature instead of re-signing is caught the same way.
        let mut stripped = read_save(&path);
        stripped["truck_conditions"]["rig"]["tire_wear_pct"] = json!(0.0);
        stripped.remove(SIGNATURE_FIELD);
        write_packed(&path, &stripped);
        assert!(load(&path).integrity_modified);
    });
}

/// A save signed by a pre-per-truck build must validate, not quarantine.
///
/// v1 signed the flat condition fields; the current build must recognize that
/// older field set from `_signature_version` and re-sign on the next save. v1
/// saves were plain JSON on disk, so the fixture lives at the legacy `.json`
/// path and load converts it into the packed container.
#[test]
fn test_v1_signed_legacy_save_loads_and_migrates_without_quarantine() {
    with_data_dir(|_| {
        let mut p = Profile::named("V1 Signed");
        p.business_status = LEASED_OWNER_OPERATOR.to_string();
        p.truck = "rig".to_string();
        p.owned_trucks = vec!["rig".to_string()];
        let mut data = p.to_dict();

        // Rewrite in the old flat shape and sign it the way a v1 build would.
        data.remove("truck_conditions");
        data.insert("truck_damage_pct".into(), json!(9.0));
        data.insert("tire_wear_pct".into(), json!(18.0));
        data.insert("brake_wear_pct".into(), json!(7.0));
        data.insert("engine_wear_pct".into(), json!(3.0));
        data.insert("truck_fuel_gal".into(), json!(70.0));
        data.insert(SIGNATURE_VERSION_FIELD.into(), json!(1));
        let signature = signature_for(&data, Some(1));
        data.insert(SIGNATURE_FIELD.into(), json!(signature));
        let legacy = p.path().with_extension("json");
        write_text(&legacy, &data);

        let loaded = load(&legacy); // must not fail the integrity check

        assert_eq!(loaded.tire_wear_pct(), 18.0);
        assert_eq!(loaded.brake_wear_pct(), 7.0);
        assert_eq!(loaded.engine_wear_pct(), 3.0);
        assert_eq!(loaded.truck_damage_pct(), 9.0);
        assert_eq!(loaded.truck_fuel_gal(), 70.0);
        // A validly signed legacy save is neither quarantined nor flagged.
        assert!(!loaded.integrity_modified);
        assert!(!with_suffix(&legacy, ".json.invalid").exists());

        // The load upgraded both the on-disk shape and the signature version.
        let resaved = read_save(&p.path());
        assert_eq!(resaved[SIGNATURE_VERSION_FIELD], json!(SIGNATURE_VERSION));
        assert!(resaved
            .get("truck_conditions")
            .is_some_and(Value::is_object));
        let reloaded = load(&p.path());
        assert_eq!(reloaded.tire_wear_pct(), 18.0); // still valid under v2
        assert!(!reloaded.integrity_modified);
    });
}

// -- tests/test_loyalty_integration.py ------------------------------------------

#[test]
fn test_profile_has_loyalty_account() {
    let profile = Profile::new();
    assert_eq!(profile.loyalty, LoyaltyAccount::new());
    assert_eq!(profile.loyalty.total_points, 0.0);
    assert_eq!(profile.loyalty.shower_credits, 0);
}

#[test]
fn test_profile_serialization_includes_loyalty() {
    with_data_dir(|_| {
        let mut profile = Profile::new();
        profile
            .loyalty
            .add_fueling(50.0, None, "Pilot Travel Center", "Springfield, IL");

        let data = profile.to_dict();
        assert!(data.contains_key("loyalty"));
        assert_eq!(data["loyalty"]["total_points"], json!(50.0));
        assert_eq!(data["loyalty"]["shower_credits"], json!(1));
    });
}

#[test]
fn test_profile_deserialization_restores_loyalty() {
    with_data_dir(|_| {
        let mut profile = Profile::new();
        profile
            .loyalty
            .add_fueling(75.0, None, "Flying J Travel Center", "Columbus, OH");

        let data = profile.to_dict();
        let restored = Profile::from_dict(&data);

        assert_eq!(restored.loyalty.total_points, 75.0);
        assert_eq!(restored.loyalty.shower_credits, 1);
        assert_eq!(restored.loyalty.total_gallons_fueled, 75.0);
    });
}

#[test]
fn test_profile_from_dict_without_loyalty() {
    let value = json!({
        "name": "Test Driver",
        "money": 5000.0,
        "current_city": "chicago_il_us",
        "version": 11,
        "_signature": "test",
        "_signature_version": 2,
    });
    let Value::Object(data) = value else {
        unreachable!()
    };

    let profile = Profile::from_dict(&data);
    assert_eq!(profile.loyalty, LoyaltyAccount::new());
    assert_eq!(profile.loyalty.total_points, 0.0);
}

#[test]
fn test_loyalty_persists_across_saves() {
    with_data_dir(|_| {
        let mut profile = Profile::new();
        profile
            .loyalty
            .add_fueling(100.0, None, "Love's Travel Stop", "Atlanta, GA");

        // Serialize and deserialize
        let data = profile.to_dict();
        let restored = Profile::from_dict(&data);

        assert_eq!(restored.loyalty.total_points, 100.0);
        assert_eq!(restored.loyalty.shower_credits, 1); // 100 gallons = 1 shower credit (50+ threshold)
        assert_eq!(restored.loyalty.fueling_history.len(), 1);
    });
}

// -- the rest of the profile surface ----------------------------------------------

#[test]
fn buffs_calendar_and_lanes_behave_like_the_dataclass() {
    let mut p = Profile::new();
    assert!(!p.has_started_career());
    assert_eq!(p.market_day(), 0);
    p.game_hours = 50.0;
    assert_eq!(p.market_day(), 2);
    assert!(p.has_started_career());
    p.anchor_calendar_to(24.0 * 100.0);
    assert_eq!(p.calendar_offset_days, 98);
    assert_eq!(p.calendar_game_hours(), 50.0 + 98.0 * 24.0);

    p.add_timed_buff(json!({"group": "fatigue", "rate": 0.5, "expires_h": 60.0}));
    p.add_timed_buff(json!({"group": "fatigue", "rate": 0.7, "expires_h": 55.0}));
    assert_eq!(p.active_buffs.len(), 1);
    assert_eq!(p.fatigue_buff_rate(50.0), 0.7);
    assert_eq!(p.fatigue_buff_rate(56.0), 1.0);
    let expired = p.expire_buffs(55.0);
    assert_eq!(expired.len(), 1);
    assert!(p.active_buffs.is_empty());

    for lane in ["a:b", "b:c", "a:b", "c:d", "d:e", "e:f", "f:g", "g:h"] {
        p.remember_lane(lane);
    }
    assert_eq!(p.recent_lanes.len(), RECENT_LANES_KEPT);
    assert_eq!(p.recent_lanes[0], "g:h");
    p.remember_lane("");
    assert_eq!(p.recent_lanes.len(), RECENT_LANES_KEPT);

    // The save listener hears every successful save, and a failing one
    // never breaks the save.
    with_data_dir(|_| {
        let heard = std::sync::Arc::new(std::sync::Mutex::new(Vec::new()));
        let sink = heard.clone();
        set_save_listener(Some(std::sync::Arc::new(move |profile: &Profile| {
            sink.lock().unwrap().push(profile.name.clone());
            if profile.name == "Boom" {
                panic!("listener failure");
            }
        })));
        Profile::named("Heard").save().unwrap();
        Profile::named("Boom").save().unwrap();
        set_save_listener(None);
        assert_eq!(*heard.lock().unwrap(), vec!["Heard", "Boom"]);
    });
}

// -- tests/test_dispatch_variety.py (the profile half) ---------------------------
//
// Owner playtest 2026-07-15: level-1 assigned dispatch bounced the same two
// cities forever (Winslow to Holbrook, again and again). The profile now
// remembers the last few delivered from:to lanes; the queue half of that file
// lives with the dispatch board.

#[test]
fn test_remember_lane_dedupes_and_caps() {
    let mut p = Profile::named("Variety");
    for i in 0..10 {
        p.remember_lane(&format!("a_{i}:b_{i}"));
    }
    assert_eq!(p.recent_lanes.len(), RECENT_LANES_KEPT);
    assert_eq!(p.recent_lanes[0], "a_9:b_9");

    // re-running a lane moves it up, not in twice
    p.remember_lane("a_9:b_9");
    assert_eq!(p.recent_lanes.iter().filter(|l| *l == "a_9:b_9").count(), 1);
    p.remember_lane(""); // never records an empty lane
    assert!(!p.recent_lanes.iter().any(|l| l.is_empty()));
}

#[test]
fn test_recent_lanes_survive_a_save_round_trip() {
    let mut p = Profile::named_in("Variety", "denver_co_us");
    p.remember_lane("denver_co_us:silverthorne_co_us");
    let restored = Profile::from_dict(&p.to_dict());
    assert_eq!(restored.recent_lanes, ["denver_co_us:silverthorne_co_us"]);
}
