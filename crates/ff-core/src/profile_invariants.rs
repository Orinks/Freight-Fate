//! Hard integrity invariants a loadable profile must satisfy.
//!
//! This is the client half of the shared-profile integrity design
//! (docs/profile-invariants.md is the maintained list; this module is its
//! executable mirror). The server's validation gate owns the *plausibility*
//! heuristics -- money against career history, XP against miles -- because
//! those rules tighten over time and always know the current content set.
//! The client enforces only the invariants that are true in every version of
//! the game: ranges, counts, and relations that no honest save can break.
//!
//! Version tolerance is deliberate: a save written by a newer build may own
//! a truck, trailer, or buff this build has never heard of, and that is the
//! validator-version gate's problem, not grounds for rejection here. Unknown
//! catalog KEYS pass; impossible VALUES do not.
//!
//! Port of `freight_fate/profile_invariants.py`. The checks run over the
//! profile's dict form (`serde_json::Value`, the shape `Profile.to_dict`
//! writes and the cloud restore hands in), with missing fields read as the
//! dataclass defaults `Profile.from_dict` would fill in.

use std::fmt;

use serde_json::Value;

// Structural ceilings, far above anything an honest career reaches; these
// exist to reject NaN/absurd numbers, not to judge progress (the server's
// plausibility rules do that with real curves).
pub const MONEY_FLOOR: f64 = -1_000_000.0;
pub const MONEY_CEILING: f64 = 1_000_000_000.0;
pub const XP_CEILING: f64 = 100_000_000.0;
pub const ADVANCE_CEILING: f64 = 1_000_000.0;

// Catalog snapshots mirrored from the models package (`models.business`,
// `models.career.ENDORSEMENT_LEVELS`, `models.trucks`, `sim.vehicle`). The
// Rust models are being ported alongside this module; once they land these
// should read the live catalogs instead (lead's wiring). The snapshot errs
// in the lenient direction by construction: unknown truck and upgrade KEYS
// pass anyway, so a catalog that grows only makes the live check stricter.
const COMPANY_DRIVER: &str = "company_driver";
const LEASED_OWNER_OPERATOR: &str = "leased_owner_operator";
const INDEPENDENT_AUTHORITY: &str = "independent_authority";
const BUSINESS_STATUSES: [&str; 3] = [COMPANY_DRIVER, LEASED_OWNER_OPERATOR, INDEPENDENT_AUTHORITY];

const TIRE_ALL_SEASON: &str = "all_season";
const TIRE_WINTER: &str = "winter";
const TIRE_TYPES: [&str; 2] = [TIRE_ALL_SEASON, TIRE_WINTER];

/// Credential courses are a closed, stable set -- unlike trucks, new ones
/// are a design event, so an unknown one is an edit. Read off the ladder
/// itself (`models::credentials::CREDENTIALS`) so this list cannot drift.
fn endorsement_keys() -> Vec<&'static str> {
    crate::models::credentials::credential_keys().collect()
}

/// `UPGRADE_CATALOG` keys with their top tier (the length of each price
/// tuple).
const UPGRADE_MAX_TIERS: [(&str, i64); 4] = [
    ("engine_tune", 2),
    ("aero_kit", 1),
    ("long_range_tank", 1),
    ("reinforced_brakes", 1),
];

/// The roomiest tank the game can build: biggest catalog tank (250 gal)
/// plus the long-range upgrade (`TANK_EXTRA_GAL`, 50). A record claiming
/// more diesel than that is edited.
const MAX_FUEL_GAL: f64 = 250.0 + 50.0;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Violation {
    /// Stable machine label, for tests and server logs.
    pub code: String,
    /// Plain language, safe to speak.
    pub detail: String,
}

impl Violation {
    fn new(code: &str, detail: impl Into<String>) -> Self {
        Self {
            code: code.to_string(),
            detail: detail.into(),
        }
    }
}

impl fmt::Display for Violation {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.code, self.detail)
    }
}

/// `isinstance(value, (int, float)) and math.isfinite(value)` -- a JSON
/// number (serde_json never carries NaN or infinity, so any number is
/// finite).
fn finite(value: &Value) -> Option<f64> {
    value.as_f64()
}

/// `isinstance(value, int)` -- a JSON integer (not a float, not a bool).
fn as_int(value: &Value) -> Option<i64> {
    match value {
        Value::Number(n) if n.is_i64() || n.is_u64() => n.as_i64(),
        _ => None,
    }
}

fn check_range(
    out: &mut Vec<Violation>,
    code: &str,
    label: &str,
    value: &Value,
    low: f64,
    high: f64,
) {
    let in_range = finite(value).is_some_and(|v| low <= v && v <= high);
    if !in_range {
        out.push(Violation::new(
            code,
            format!("{label} is outside the possible range."),
        ));
    }
}

/// A top-level field, or the dataclass default when the dict lacks it.
fn field<'a>(profile: &'a Value, key: &str, default: &'a Value) -> &'a Value {
    profile.get(key).unwrap_or(default)
}

fn check_condition_records(out: &mut Vec<Violation>, truck_conditions: &Value) {
    let Some(records) = truck_conditions.as_object() else {
        return;
    };
    for record in records.values() {
        let Some(record) = record.as_object() else {
            out.push(Violation::new(
                "condition_shape",
                "A truck condition record is malformed.",
            ));
            continue;
        };
        let zero = Value::from(0.0);
        for (field_name, label) in [
            ("tire_wear_pct", "tire wear"),
            ("brake_wear_pct", "brake wear"),
            ("engine_wear_pct", "engine wear"),
            ("damage_pct", "damage"),
            ("chain_wear_pct", "chain wear"),
        ] {
            let value = record.get(field_name).unwrap_or(&zero);
            if !finite(value).is_some_and(|v| (0.0..=100.0).contains(&v)) {
                out.push(Violation::new(
                    "condition_range",
                    format!("A truck's {label} is outside 0 to 100."),
                ));
            }
        }
        let fuel = record.get("fuel_gal").unwrap_or(&zero);
        if !finite(fuel).is_some_and(|v| (0.0..=MAX_FUEL_GAL).contains(&v)) {
            out.push(Violation::new(
                "fuel_range",
                "A truck carries an impossible amount of fuel.",
            ));
        }
        let tire_type = record
            .get("tire_type")
            .map(|v| v.as_str().unwrap_or(""))
            .unwrap_or(TIRE_ALL_SEASON);
        if !TIRE_TYPES.contains(&tire_type) {
            out.push(Violation::new(
                "tire_type",
                "A tire compound that does not exist.",
            ));
        }
    }
}

/// Every hard invariant the profile breaks, empty when it is sound.
pub fn check_profile_invariants(profile: &Value) -> Vec<Violation> {
    let mut out: Vec<Violation> = Vec::new();
    let default_money = Value::from(5000.0);
    let zero_f = Value::from(0.0);
    let zero_i = Value::from(0);
    let empty_map = Value::Object(Default::default());
    let empty_list = Value::Array(Vec::new());
    let falsy = Value::Bool(false);

    check_range(
        &mut out,
        "money",
        "The bank balance",
        field(profile, "money", &default_money),
        MONEY_FLOOR,
        MONEY_CEILING,
    );
    check_range(
        &mut out,
        "fatigue",
        "Fatigue",
        field(profile, "fatigue", &zero_f),
        0.0,
        100.0,
    );
    check_range(
        &mut out,
        "pay_advance",
        "The pay advance",
        field(profile, "pay_advance", &zero_f),
        0.0,
        ADVANCE_CEILING,
    );
    let calendar_ok = as_int(field(profile, "calendar_offset_days", &zero_i))
        .is_some_and(|days| (0..365).contains(&days));
    if !calendar_ok {
        out.push(Violation::new(
            "calendar_offset",
            "The calendar offset is not possible.",
        ));
    }
    // Per-truck condition records. Unknown truck KEYS pass (a newer build may
    // sell trucks this one has never heard of); impossible VALUES do not.
    // Records are plain dicts on this line, and carry brake, engine and chain
    // wear as well as tyres and damage; road grime stays on the profile.
    let truck_conditions = field(profile, "truck_conditions", &empty_map);
    check_condition_records(&mut out, truck_conditions);

    let career = field(profile, "career", &empty_map);
    let default_reputation = Value::from(50.0);
    check_range(
        &mut out,
        "xp",
        "Career experience",
        field(career, "xp", &zero_f),
        0.0,
        XP_CEILING,
    );
    check_range(
        &mut out,
        "reputation",
        "Reputation",
        field(career, "reputation", &default_reputation),
        0.0,
        100.0,
    );
    let deliveries = as_int(field(career, "deliveries", &zero_i));
    let on_time_deliveries = as_int(field(career, "on_time_deliveries", &zero_i));
    let on_time_streak = as_int(field(career, "on_time_streak", &zero_i));
    let dispatch_declines = as_int(field(career, "dispatch_declines_used", &zero_i));
    for (code, label, value) in [
        ("deliveries", "The delivery count", deliveries),
        (
            "on_time_deliveries",
            "The on-time delivery count",
            on_time_deliveries,
        ),
        ("on_time_streak", "The on-time streak", on_time_streak),
        (
            "dispatch_declines",
            "The dispatch refusal count",
            dispatch_declines,
        ),
    ] {
        if value.is_none_or(|v| v < 0) {
            out.push(Violation::new(
                code,
                format!("{label} is not a possible count."),
            ));
        }
    }
    if !finite(field(career, "total_miles", &zero_f)).is_some_and(|v| v >= 0.0) {
        out.push(Violation::new(
            "total_miles",
            "The career mileage is not possible.",
        ));
    }
    if !finite(field(career, "total_earnings", &zero_f)).is_some_and(|v| v >= 0.0) {
        out.push(Violation::new(
            "total_earnings",
            "The career earnings are not possible.",
        ));
    }
    if let (Some(deliveries), Some(on_time)) = (deliveries, on_time_deliveries) {
        if on_time > deliveries && deliveries >= 0 {
            out.push(Violation::new(
                "on_time_exceeds",
                "More on-time deliveries than deliveries driven.",
            ));
        }
    }
    if let (Some(on_time), Some(streak)) = (on_time_deliveries, on_time_streak) {
        if streak > on_time && on_time >= 0 {
            out.push(Violation::new(
                "streak_exceeds",
                "An on-time streak longer than the record.",
            ));
        }
    }
    if let Some(endorsements) = field(career, "purchased_endorsements", &empty_list).as_array() {
        let known_keys = endorsement_keys();
        for endorsement in endorsements {
            // Credential courses are a closed, stable set -- unlike trucks,
            // new ones are a design event, so an unknown one is an edit.
            let known = endorsement
                .as_str()
                .is_some_and(|key| known_keys.contains(&key));
            if !known {
                out.push(Violation::new(
                    "endorsement",
                    "An endorsement that does not exist.",
                ));
                break;
            }
        }
    }

    let default_status = Value::from(COMPANY_DRIVER);
    let status_known = field(profile, "business_status", &default_status)
        .as_str()
        .is_some_and(|status| BUSINESS_STATUSES.contains(&status));
    if !status_known {
        out.push(Violation::new(
            "business_status",
            "A business standing that does not exist.",
        ));
    }

    if let Some(achievements) = field(profile, "achievements", &empty_list).as_array() {
        let mut seen: Vec<&Value> = Vec::with_capacity(achievements.len());
        let mut duplicated = false;
        for achievement in achievements {
            if seen.contains(&achievement) {
                duplicated = true;
                break;
            }
            seen.push(achievement);
        }
        if duplicated {
            out.push(Violation::new(
                "achievement_dupes",
                "The same achievement recorded twice.",
            ));
        }
    }

    // The Python module runs the condition-record pass a second time here
    // (the same checks, the same violations); kept so the violation list --
    // and therefore the first spoken problem -- matches it entry for entry.
    check_condition_records(&mut out, truck_conditions);

    // The local tamper mark must be a real boolean; anything else is an edit.
    for flag_code in ["integrity_modified", "integrity_notice_pending"] {
        if !field(profile, flag_code, &falsy).is_boolean() {
            out.push(Violation::new(
                flag_code,
                "The save's integrity mark is not possible.",
            ));
        }
    }

    if let Some(upgrades) = field(profile, "upgrades", &empty_map).as_object() {
        for (key, tier) in upgrades {
            let Some(tier) = as_int(tier).filter(|t| *t >= 1) else {
                out.push(Violation::new(
                    "upgrade_tier",
                    "An upgrade tier that is not possible.",
                ));
                continue;
            };
            // Unknown upgrade keys pass (a newer build may have added one); a
            // KNOWN upgrade past its top tier can only be an edit.
            let max_tier = UPGRADE_MAX_TIERS
                .iter()
                .find(|(known, _)| known == key)
                .map(|(_, max)| *max);
            if max_tier.is_some_and(|max| tier > max) {
                out.push(Violation::new(
                    "upgrade_tier",
                    "An upgrade pushed past its top tier.",
                ));
            }
        }
    }

    out
}

/// One plain sentence for the speech layer when an import is refused.
pub fn spoken_rejection(violations: &[Violation]) -> String {
    match violations.first() {
        None => String::new(),
        Some(first) => format!(
            "This profile fails the game's integrity checks and was not \
             loaded. First problem: {}",
            first.detail
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::collections::BTreeSet;

    /// The dict `Profile(name=...).to_dict()` writes, trimmed to the fields
    /// the invariants read (plus the name).
    fn profile(name: &str) -> Value {
        json!({
            "name": name,
            "money": 5000.0,
            "integrity_modified": false,
            "integrity_notice_pending": false,
            "calendar_offset_days": 0,
            "truck": "rig",
            "owned_trucks": [],
            "truck_conditions": {},
            "upgrades": {},
            "fatigue": 0.0,
            "active_buffs": [],
            "pay_advance": 0.0,
            "business_status": "company_driver",
            "career": {
                "xp": 0.0,
                "reputation": 50.0,
                "deliveries": 0,
                "on_time_deliveries": 0,
                "total_miles": 0.0,
                "total_earnings": 0.0,
                "dispatch_declines_used": 0,
                "on_time_streak": 0,
                "purchased_endorsements": [],
            },
            "achievements": [],
        })
    }

    fn codes(profile: &Value) -> BTreeSet<String> {
        check_profile_invariants(profile)
            .into_iter()
            .map(|v| v.code)
            .collect()
    }

    fn has_all(found: &BTreeSet<String>, wanted: &[&str]) -> bool {
        wanted.iter().all(|code| found.contains(*code))
    }

    #[test]
    fn test_fresh_profile_passes_clean() {
        assert_eq!(check_profile_invariants(&profile("Honest Norm")), vec![]);
    }

    #[test]
    fn test_played_profile_passes_clean() {
        let mut p = profile("Veteran");
        p["money"] = json!(84_000.0);
        p["fatigue"] = json!(62.0);
        p["career"]["xp"] = json!(32_000.0);
        p["career"]["deliveries"] = json!(41);
        p["career"]["on_time_deliveries"] = json!(39);
        p["career"]["on_time_streak"] = json!(12);
        p["career"]["total_miles"] = json!(21_500.0);
        p["career"]["total_earnings"] = json!(96_000.0);
        p["career"]["purchased_endorsements"] = json!(["heavy_haul"]);
        p["truck_conditions"]["rig"] = json!({
            "tire_wear_pct": 34.0,
            "brake_wear_pct": 12.5,
            "engine_wear_pct": 8.0,
            "damage_pct": 3.0,
            "fuel_gal": 180.0,
            "tire_type": "winter",
            "chains_owned": true,
            "chain_wear_pct": 22.0,
        });
        p["upgrades"]["engine_tune"] = json!(1);
        assert_eq!(check_profile_invariants(&p), vec![]);
    }

    #[test]
    fn test_range_edits_are_caught() {
        let mut p = profile("Edited");
        // JSON cannot carry NaN (serde_json refuses it at parse time), so the
        // non-number branch of the money check stands in for float("nan").
        p["money"] = json!("nan");
        p["fatigue"] = json!(-5.0);
        p["career"]["xp"] = json!(-1.0);
        p["career"]["reputation"] = json!(1000.0);
        let found = codes(&p);
        assert!(has_all(&found, &["money", "fatigue", "xp", "reputation"]));
    }

    #[test]
    fn test_calendar_offset_edits_are_caught() {
        // Python parametrizes over -1, 365, 1.5 and float("nan"); JSON has no
        // NaN, so null stands in for the non-int case.
        for value in [json!(-1), json!(365), json!(1.5), Value::Null] {
            let mut p = profile("Edited Calendar");
            p["calendar_offset_days"] = value.clone();
            assert!(codes(&p).contains("calendar_offset"), "{value}");
        }
    }

    #[test]
    fn test_condition_edits_are_caught() {
        // Profile.tire_wear_pct and friends write through to the active
        // truck's condition record; the record itself is what the dict carries.
        let mut p = profile("Edited");
        p["truck_conditions"]["rig"] = json!({
            "tire_wear_pct": -20.0,  // fresher than new
            "damage_pct": 250.0,
            "fuel_gal": 9_000.0,  // tanker, not a tank
        });
        let violations = check_profile_invariants(&p);
        assert!(violations.iter().any(|v| v.code == "fuel_range"));
        // Out-of-range wear meters all report under one condition_range code, with
        // the meter named in the detail, rather than a code per meter. Read the
        // details so this still proves the tyre edit AND the damage edit were each
        // caught, not merely that something was.
        let condition_details: Vec<&str> = violations
            .iter()
            .filter(|v| v.code == "condition_range")
            .map(|v| v.detail.as_str())
            .collect();
        let condition_details = condition_details.join(" ");
        assert!(condition_details.contains("tire wear"));
        assert!(condition_details.contains("damage"));
    }

    #[test]
    fn test_counter_relations_are_caught() {
        let mut p = profile("Edited");
        p["career"]["deliveries"] = json!(3);
        p["career"]["on_time_deliveries"] = json!(9);
        p["career"]["on_time_streak"] = json!(40);
        assert!(codes(&p).contains("on_time_exceeds"));
        let mut p2 = profile("Edited");
        p2["career"]["deliveries"] = json!(9);
        p2["career"]["on_time_deliveries"] = json!(3);
        p2["career"]["on_time_streak"] = json!(7);
        assert!(codes(&p2).contains("streak_exceeds"));
    }

    #[test]
    fn test_condition_record_edits_are_caught() {
        let mut p = profile("Edited");
        p["truck_conditions"]["rig"] = json!({
            "tire_wear_pct": -20.0,  // fresher than new
            "fuel_gal": 9_000.0,  // tanker, not a tank
            "tire_type": "slicks",
            "chain_wear_pct": 250.0,
        });
        let found = codes(&p);
        assert!(has_all(
            &found,
            &["condition_range", "fuel_range", "tire_type"]
        ));
    }

    #[test]
    fn test_closed_sets_and_upgrade_tiers_are_caught() {
        let mut p = profile("Edited");
        p["business_status"] = json!("fleet_emperor");
        p["career"]["purchased_endorsements"] = json!(["rocket_fuel"]);
        p["upgrades"]["engine_tune"] = json!(99);
        p["achievements"] = json!(["first_delivery", "first_delivery"]);
        let found = codes(&p);
        assert!(has_all(
            &found,
            &[
                "business_status",
                "endorsement",
                "upgrade_tier",
                "achievement_dupes"
            ]
        ));
    }

    #[test]
    fn test_unknown_keys_from_newer_builds_pass() {
        // Version tolerance: a newer build's truck, buff, upgrade, or
        // achievement key is not an edit -- values are judged, keys are not.
        let mut p = profile("From The Future");
        p["owned_trucks"] = json!(["cabover_classic_2027"]);
        p["truck_conditions"]["cabover_classic_2027"] = json!({
            "tire_wear_pct": 10.0,
            "fuel_gal": 100.0,
        });
        p["upgrades"]["chrome_stacks"] = json!(2);
        p["achievements"] = json!(["antler_polisher"]);
        p["active_buffs"] =
            json!([{"key": "mystery_meat", "label": "Mystery meat", "expires_h": 4.0}]);
        assert_eq!(check_profile_invariants(&p), vec![]);
    }

    #[test]
    fn test_spoken_rejection_is_plain_language() {
        let mut p = profile("Edited");
        p["career"]["reputation"] = json!(555.0);
        let text = spoken_rejection(&check_profile_invariants(&p));
        assert!(text.starts_with("This profile fails the game's integrity checks"));
        assert!(text.contains("Reputation"));
        // no jargon before the reason
        let before = text.split("First problem:").next().unwrap();
        assert!(!before.contains("0 to"));
    }

    #[test]
    fn missing_fields_read_as_the_dataclass_defaults() {
        // The cloud restore hands in Profile.to_dict(); a dict missing a field
        // is judged by the default from_dict would fill in, not refused.
        assert_eq!(check_profile_invariants(&json!({"name": "Bare"})), vec![]);
    }

    #[test]
    fn integrity_marks_must_be_real_booleans() {
        let mut p = profile("Edited");
        p["integrity_modified"] = json!(1);
        p["integrity_notice_pending"] = json!("no");
        let found = codes(&p);
        assert!(has_all(
            &found,
            &["integrity_modified", "integrity_notice_pending"]
        ));
    }

    // -- the defense-in-depth hook in verify_cloud_revision -------------------

    mod cloud_hook {
        use super::*;
        use crate::cloud_save_integrity::{canonical_profile, verify_cloud_revision};
        use base64::Engine as _;
        use ed25519_dalek::{Signer, SigningKey};
        use std::collections::BTreeMap;

        const KEY_ID: &str = "invariant-test";

        fn private_key() -> SigningKey {
            SigningKey::from_bytes(&[11u8; 32])
        }

        fn public_keys() -> BTreeMap<String, Vec<u8>> {
            let mut keys = BTreeMap::new();
            keys.insert(
                KEY_ID.to_string(),
                private_key().verifying_key().to_bytes().to_vec(),
            );
            keys
        }

        fn signed_envelope(payload: &Value) -> Value {
            let signature = private_key().sign(&canonical_profile(payload).unwrap());
            json!({
                "keyId": KEY_ID,
                "validatorVersion": 1,
                "sig": base64::engine::general_purpose::STANDARD.encode(signature.to_bytes()),
                "signedAt": "2026-07-13T00:00:00Z",
            })
        }

        #[test]
        fn test_signed_honest_payload_restores() {
            let payload = profile("Honest Norm");
            let signed_bytes = canonical_profile(&payload).unwrap();
            let keys = public_keys();
            let restored =
                verify_cloud_revision(&payload, &signed_envelope(&payload), Some(&keys)).unwrap();
            assert_eq!(restored["name"], json!("Honest Norm"));
            assert_eq!(canonical_profile(&payload).unwrap(), signed_bytes);
        }

        #[test]
        fn test_signed_but_impossible_payload_is_refused() {
            // A valid signature is not a pardon: a payload blessed by an older or
            // compromised validator still has to obey the invariants.
            let mut p = profile("Signed Cheater");
            p["money"] = json!(500_000_000_000.0);
            let keys = public_keys();
            let caught = verify_cloud_revision(&p, &signed_envelope(&p), Some(&keys)).unwrap_err();
            assert_eq!(caught.code, "invalid_profile");
            assert!(caught.message.contains("integrity checks"));
        }
    }
}
