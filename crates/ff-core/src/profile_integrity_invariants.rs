//! Catalog snapshot shared with the orinks.net cloud-save validator.
//!
//! Port of `freight_fate/profile_integrity_invariants.py`. This is a
//! source-tree-only export for the validator; never called by the game at
//! runtime, so frozen builds (which carry no world_data tree) are
//! unaffected.
//!
//! The Python module reads every figure straight off the models package
//! (`ACHIEVEMENTS`, `Career`, `Profile`, `TRUCK_CATALOG`, ...). Those are
//! ported in parallel with this file, so the model-side figures arrive
//! through [`CatalogInputs`] -- the lead wires `CatalogInputs::current()`
//! to the live catalogs once they exist -- while the city labels are read
//! from the world data under the `data_root` the caller passes.

use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

use serde_json::{Map, Value};

use crate::cloud_save_integrity::ascii_json_string;
use crate::pyfmt::py_str_float;

/// Signature keys ride inside the saved file but never inside a cloud
/// upload -- the upload strips them and the server signs its own revision
/// instead.
pub const LOCAL_ONLY_FIELDS: [&str; 2] = ["_signature", "_signature_version"];

/// `_json_number`: a whole float prints as an int in the export.
pub fn json_number(value: f64) -> Value {
    if value.is_finite() && value.fract() == 0.0 && value.abs() < 9.0e15 {
        Value::from(value as i64)
    } else {
        Value::from(value)
    }
}

/// One endorsement row: key, the carrier-sponsored level, the spoken label.
#[derive(Debug, Clone, PartialEq)]
pub struct EndorsementRow {
    pub key: String,
    pub level: i64,
    pub label: String,
}

/// One carrier fleet band: the first level it applies to and its label.
#[derive(Debug, Clone, PartialEq)]
pub struct FleetTierRow {
    pub min_level: i64,
    pub label: String,
}

/// The economy and catalog figures the export carries, read off the models
/// package. Field names follow the Python constants they come from.
#[derive(Debug, Clone, PartialEq)]
pub struct CatalogInputs {
    /// `achievement.id` for every entry of `ACHIEVEMENTS`.
    pub achievement_ids: Vec<String>,
    /// `STARTING_MONEY`.
    pub starting_money: f64,
    /// `max(option.starting_money for option in all_start_options())`.
    pub starting_money_max: f64,
    /// `PAY_ADVANCE_LIMIT`.
    pub pay_advance_limit: f64,
    /// `XP_PER_MILE_ON_TIME`.
    pub xp_per_mile_on_time: f64,
    /// `XP_SPECIALTY_MULT`.
    pub xp_specialty_mult: f64,
    /// `XP_STREAK_MAX_BONUS`.
    pub xp_streak_max_bonus: f64,
    /// `XP_CLEAN_BONUS`.
    pub xp_clean_bonus: f64,
    /// `DELIVERY_COMPLETION_XP`.
    pub delivery_completion_xp: f64,
    /// `LEVEL_XP`, one threshold per level.
    pub level_xp: Vec<i64>,
    /// `MARKET_CARGO_KEYS`.
    pub market_cargo_keys: Vec<String>,
    /// `Profile.__dataclass_fields__` (the `version` key is added here).
    pub profile_fields: Vec<String>,
    /// `Career.__dataclass_fields__`.
    pub career_fields: Vec<String>,
    /// `ENDORSEMENT_LEVELS` joined with `ENDORSEMENT_LABELS_SPOKEN`.
    pub endorsements: Vec<EndorsementRow>,
    /// `FLEET_TIERS`, in catalog order.
    pub fleet_tiers: Vec<FleetTierRow>,
    /// The keys of the record `_fresh_condition()` writes.
    pub truck_condition_fields: Vec<String>,
    /// `SAVE_VERSION`.
    pub source_save_version: i64,
    /// `TRUCK_CATALOG`: key, label, price, in catalog order.
    pub trucks: Vec<(String, String, f64)>,
    /// `UPGRADE_CATALOG`: key and per-tier prices, in catalog order.
    pub upgrade_prices: Vec<(String, Vec<f64>)>,
}

/// Every share bonus in `record_delivery` taken at once, at its best.
///
/// Both bonuses multiply the whole award, flat completion XP included, so
/// this factor belongs to both terms below.
pub fn xp_best_case_multiplier(inputs: &CatalogInputs) -> f64 {
    (1.0 + inputs.xp_streak_max_bonus) * (1.0 + inputs.xp_clean_bonus)
}

/// The most XP one mile can teach, taking every bonus at its best.
///
/// The validator's ceiling is `deliveries * flat + miles * this`. It has to
/// sit at or above what the game can actually award, because anything lower
/// convicts honest drivers -- a copied 1.2 here was below even the base
/// on-time rate on this line. Recompute it from the real constants whenever
/// the XP model grows a term.
pub fn xp_per_mile_max(inputs: &CatalogInputs) -> f64 {
    inputs.xp_per_mile_on_time * inputs.xp_specialty_mult * xp_best_case_multiplier(inputs)
}

/// XP a settled load teaches regardless of distance, at its best.
pub fn xp_flat_per_delivery(inputs: &CatalogInputs) -> f64 {
    inputs.delivery_completion_xp * xp_best_case_multiplier(inputs)
}

/// Top-level keys a cloud upload carries, straight off the dataclass.
///
/// The validator checks uploads against an exact field list. Hand-keeping
/// that list on the server means it silently falls behind the moment a field
/// is added or removed here -- and the failure is a flat schema rejection
/// that reads to the player as "your backup is broken", not as version skew.
/// Export it instead, so the two sides cannot drift.
pub fn profile_fields(inputs: &CatalogInputs) -> Vec<String> {
    let mut fields: Vec<String> = inputs
        .profile_fields
        .iter()
        .cloned()
        .chain(std::iter::once("version".to_string()))
        .filter(|field| !LOCAL_ONLY_FIELDS.contains(&field.as_str()))
        .collect();
    fields.sort();
    fields.dedup();
    fields
}

/// Keys inside one owned truck's condition record.
///
/// Same reason as `profile_fields`, one level down: the validator checks each
/// record against an exact list, and this record is where new per-truck state
/// lands (brake and engine wear, traction gear). A hand-kept copy on the
/// server would reject the next build's saves the moment one is added.
///
/// Read from the record the game actually writes, not from the TruckCondition
/// dataclass. On this line the records are plain dicts built by
/// `_fresh_condition`, and they outgrew that dataclass when the physics arc
/// added brake wear, engine wear, and traction gear -- it kept four fields
/// while a real record carries nine. Exporting the dataclass therefore told
/// the server that five legitimate keys were unknown, which would have failed
/// every 1.9 save on the exact-field check the moment the two sides met.
pub fn truck_condition_fields(inputs: &CatalogInputs) -> Vec<String> {
    let mut fields = inputs.truck_condition_fields.clone();
    fields.sort();
    fields
}

/// `"<spoken city>, <state name>"` per city slug, read from `us/cities.json`
/// and `geo.json` under `data_root` (the `world_data` tree).
pub fn city_labels(data_root: &Path) -> Result<BTreeMap<String, String>, String> {
    let read = |relative: &str| -> Result<Value, String> {
        let path = data_root.join(relative);
        let text = fs::read_to_string(&path)
            .map_err(|err| format!("cannot read {}: {err}", path.display()))?;
        serde_json::from_str(&text).map_err(|err| format!("cannot parse {relative}: {err}"))
    };
    let cities_doc = read("us/cities.json")?; // runtime-data-ok
    let geo_doc = read("geo.json")?; // runtime-data-ok
    let cities = cities_doc
        .get("cities")
        .and_then(Value::as_object)
        .ok_or("us/cities.json has no cities table")?;
    let states = geo_doc
        .pointer("/countries/US/states")
        .and_then(Value::as_object)
        .ok_or("geo.json has no US states table")?;
    let mut labels = BTreeMap::new();
    for (slug, city) in cities {
        let spoken = city
            .get("spoken_city")
            .and_then(Value::as_str)
            .ok_or_else(|| format!("city {slug} has no spoken_city"))?;
        let state_code = city.get("state").and_then(Value::as_str).unwrap_or("");
        let state_name = states
            .get(state_code)
            .and_then(Value::as_str)
            .unwrap_or(state_code);
        let label = format!("{spoken}, {state_name}");
        let label = label.trim_end_matches([',', ' ']).to_string();
        labels.insert(slug.clone(), label);
    }
    Ok(labels)
}

/// The export document, keyed exactly as the validator reads it.
pub fn invariant_data(data_root: &Path, inputs: &CatalogInputs) -> Result<Value, String> {
    let mut achievement_ids = inputs.achievement_ids.clone();
    achievement_ids.sort();
    let mut market_cargo_keys = inputs.market_cargo_keys.clone();
    market_cargo_keys.sort();
    let mut career_fields = inputs.career_fields.clone();
    career_fields.sort();

    let mut endorsements = Map::new();
    let mut rows: Vec<&EndorsementRow> = inputs.endorsements.iter().collect();
    rows.sort_by(|a, b| a.key.cmp(&b.key));
    for row in rows {
        let mut entry = Map::new();
        entry.insert("level".to_string(), Value::from(row.level));
        entry.insert("label".to_string(), Value::from(row.label.clone()));
        endorsements.insert(row.key.clone(), Value::Object(entry));
    }

    let fleet_tiers: Vec<Value> = inputs
        .fleet_tiers
        .iter()
        .map(|tier| {
            let mut entry = Map::new();
            entry.insert("minLevel".to_string(), Value::from(tier.min_level));
            entry.insert("label".to_string(), Value::from(tier.label.clone()));
            Value::Object(entry)
        })
        .collect();

    let mut truck_labels = Map::new();
    let mut truck_prices = Map::new();
    for (key, label, price) in &inputs.trucks {
        truck_labels.insert(key.clone(), Value::from(label.clone()));
        truck_prices.insert(key.clone(), json_number(*price));
    }
    let mut upgrade_prices = Map::new();
    for (key, prices) in &inputs.upgrade_prices {
        upgrade_prices.insert(
            key.clone(),
            Value::Array(prices.iter().map(|p| json_number(*p)).collect()),
        );
    }

    let labels = city_labels(data_root)?;
    let city_labels: Map<String, Value> = labels
        .into_iter()
        .map(|(slug, label)| (slug, Value::from(label)))
        .collect();

    let mut out = Map::new();
    out.insert("achievementIds".into(), Value::from(achievement_ids));
    out.insert("cityLabels".into(), Value::Object(city_labels));
    // The economy terms the cloud-save validator needs to tell an edited
    // career from an honest one. They ship as data for the same reason the
    // field lists do: a copy kept on the server falls behind the next
    // balance pass, and every honest player on the new build then hears
    // that their backup was rejected. See the money and XP checks in
    // convex/freightFateSharedProfileValidation.ts.
    out.insert("startingMoney".into(), json_number(inputs.starting_money));
    // The most cash any career-start option hands over. The money ceiling
    // must credit this, not the company-driver default: the owner-operator
    // start opens with 18,000 dollars, and a ceiling built on 5,000
    // rejected every honest owner-operator backup until their earnings
    // eventually outgrew the gap. Wrong in the generous direction is the
    // survivable wrong here, so the validator uses the maximum rather
    // than a per-carrier lookup that would break on a start option the
    // server has not heard of yet.
    out.insert(
        "startingMoneyMax".into(),
        json_number(inputs.starting_money_max),
    );
    out.insert(
        "payAdvanceLimit".into(),
        json_number(inputs.pay_advance_limit),
    );
    out.insert("xpPerMileMax".into(), json_number(xp_per_mile_max(inputs)));
    out.insert(
        "xpFlatPerDelivery".into(),
        json_number(xp_flat_per_delivery(inputs)),
    );
    out.insert("levelXp".into(), Value::from(inputs.level_xp.clone()));
    out.insert("marketCargoKeys".into(), Value::from(market_cargo_keys));
    out.insert("profileFields".into(), Value::from(profile_fields(inputs)));
    out.insert("careerFields".into(), Value::from(career_fields));
    // Public-profile display data: orinks.net derives each driver's
    // endorsements (level-earned plus self-paid courses) and, for company
    // drivers, the carrier fleet tier straight from the validated career.
    // Exported rather than copied so the site's projection moves with the
    // next balance pass instead of drifting behind it.
    out.insert("endorsements".into(), Value::Object(endorsements));
    out.insert("fleetTiers".into(), Value::Array(fleet_tiers));
    out.insert(
        "truckConditionFields".into(),
        Value::from(truck_condition_fields(inputs)),
    );
    out.insert(
        "sourceSaveVersion".into(),
        Value::from(inputs.source_save_version),
    );
    out.insert("truckLabels".into(), Value::Object(truck_labels));
    out.insert("truckPrices".into(), Value::Object(truck_prices));
    out.insert("upgradePrices".into(), Value::Object(upgrade_prices));
    Ok(Value::Object(out))
}

/// `json.dumps(value, indent=2, sort_keys=True)`: two-space indent, keys
/// sorted, non-ASCII escaped, floats in Python repr.
fn dump_sorted(value: &Value, indent: usize, out: &mut String) {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                out.push_str(&i.to_string());
            } else if let Some(u) = n.as_u64() {
                out.push_str(&u.to_string());
            } else {
                out.push_str(&py_str_float(n.as_f64().unwrap_or(0.0)));
            }
        }
        Value::String(s) => out.push_str(&ascii_json_string(s)),
        Value::Array(items) => {
            if items.is_empty() {
                out.push_str("[]");
                return;
            }
            out.push('[');
            for (index, item) in items.iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                out.push('\n');
                out.push_str(&" ".repeat(indent + 2));
                dump_sorted(item, indent + 2, out);
            }
            out.push('\n');
            out.push_str(&" ".repeat(indent));
            out.push(']');
        }
        Value::Object(map) => {
            if map.is_empty() {
                out.push_str("{}");
                return;
            }
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            out.push('{');
            for (index, key) in keys.iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                out.push('\n');
                out.push_str(&" ".repeat(indent + 2));
                out.push_str(&ascii_json_string(key));
                out.push_str(": ");
                dump_sorted(&map[*key], indent + 2, out);
            }
            out.push('\n');
            out.push_str(&" ".repeat(indent));
            out.push('}');
        }
    }
}

/// The export as the validator's JSON file: `json.dumps(..., indent=2,
/// sort_keys=True)` plus a trailing newline.
pub fn rendered_invariants(data_root: &Path, inputs: &CatalogInputs) -> Result<String, String> {
    let data = invariant_data(data_root, inputs)?;
    let mut out = String::new();
    dump_sorted(&data, 0, &mut out);
    out.push('\n');
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    /// The repo's `src/freight_fate/data/world_data` tree.
    fn world_data_root() -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../src/freight_fate/data/world_data")
    }

    /// A snapshot of the model constants as of 2026-08-22 (the Python
    /// `invariant_data()` output), standing in until the models land.
    fn inputs() -> CatalogInputs {
        CatalogInputs {
            achievement_ids: vec!["first_delivery".into(), "antler_polisher".into()],
            starting_money: 5000.0,
            starting_money_max: 18000.0,
            pay_advance_limit: 1500.0,
            xp_per_mile_on_time: 1.6,
            xp_specialty_mult: 1.5,
            xp_streak_max_bonus: 0.45,
            xp_clean_bonus: 0.15,
            delivery_completion_xp: 150.0,
            level_xp: vec![0, 1000, 2500, 4500, 7000],
            market_cargo_keys: vec!["retail".into(), "general".into()],
            profile_fields: vec![
                "name".into(),
                "money".into(),
                "created_line".into(),
                "business_status".into(),
                "_signature".into(),
                "_signature_version".into(),
            ],
            career_fields: vec![
                "xp".into(),
                "deliveries".into(),
                "purchased_endorsements".into(),
            ],
            endorsements: vec![
                EndorsementRow {
                    key: "refrigerated".into(),
                    level: 2,
                    label: "refrigerated".into(),
                },
                EndorsementRow {
                    key: "heavy_haul".into(),
                    level: 3,
                    label: "heavy-haul".into(),
                },
            ],
            fleet_tiers: vec![
                FleetTierRow {
                    min_level: 1,
                    label: "yard standard".into(),
                },
                FleetTierRow {
                    min_level: 4,
                    label: "regional fleet".into(),
                },
            ],
            truck_condition_fields: vec![
                "tire_wear_pct".into(),
                "brake_wear_pct".into(),
                "chain_wear_pct".into(),
                "chains_owned".into(),
                "damage_pct".into(),
                "engine_wear_pct".into(),
                "fuel_gal".into(),
                "grime_pct".into(),
                "tire_type".into(),
            ],
            source_save_version: 11,
            trucks: vec![("rig".into(), "standard rig".into(), 80_000.0)],
            upgrade_prices: vec![("engine_tune".into(), vec![12_000.0, 26_000.0])],
        }
    }

    #[test]
    fn test_integrity_invariants_include_public_projection_labels() {
        let data = invariant_data(&world_data_root(), &inputs()).unwrap();
        assert!(data["sourceSaveVersion"].as_i64().unwrap() >= 1);
        assert_eq!(data["cityLabels"]["new_york_ny_us"], "New York, New York");
        assert_eq!(data["truckLabels"]["rig"], "standard rig");
        assert_eq!(data["levelXp"][0], 0);
        assert!(rendered_invariants(&world_data_root(), &inputs())
            .unwrap()
            .ends_with('\n'));
    }

    #[test]
    #[ignore = "needs models::career (Career.record_delivery and the XP constants)"]
    fn test_exported_xp_ceiling_bounds_every_honest_career() {}

    #[test]
    #[ignore = "needs models::profile (Profile().money)"]
    fn test_exported_starting_money_matches_a_fresh_career() {}

    #[test]
    #[ignore = "needs models::start_options (all_start_options)"]
    fn test_exported_starting_money_max_covers_every_start_option() {}

    #[test]
    #[ignore = "needs models::profile (provision_truck_condition)"]
    fn test_exported_condition_fields_match_a_real_record() {}

    #[test]
    fn test_exported_profile_fields_include_the_created_on_marker() {
        // The 1.9 cutover regen must teach the server allow-list `created_line`.
        // Every 1.9 upload carries the marker, so a validator built from an
        // export without it would reject every honest backup on the schema check.
        let data = invariant_data(&world_data_root(), &inputs()).unwrap();
        let fields = data["profileFields"].as_array().unwrap();
        assert!(fields.contains(&Value::from("created_line")));
        // The local-only signature keys never ride the export.
        assert!(!fields.contains(&Value::from("_signature")));
        assert!(fields.contains(&Value::from("version")));
    }

    #[test]
    fn test_exported_public_profile_fields_ride_the_allow_lists() {
        let data = invariant_data(&world_data_root(), &inputs()).unwrap();
        assert!(data["profileFields"]
            .as_array()
            .unwrap()
            .contains(&Value::from("business_status")));
        assert!(data["careerFields"]
            .as_array()
            .unwrap()
            .contains(&Value::from("purchased_endorsements")));
    }

    #[test]
    #[ignore = "needs models::career (Career.level / Career.endorsements)"]
    fn test_exported_endorsements_match_what_the_career_actually_unlocks() {}

    #[test]
    #[ignore = "needs models::carrier_fleet (fleet_tier_for_level)"]
    fn test_exported_fleet_tiers_match_the_carrier_fleet_bands() {}

    #[test]
    fn the_xp_ceiling_terms_follow_the_python_arithmetic() {
        // Python invariant_data() on 2026-08-22: xpPerMileMax 4.002,
        // xpFlatPerDelivery 250.12499999999997.
        let data = invariant_data(&world_data_root(), &inputs()).unwrap();
        assert_eq!(data["xpPerMileMax"], 4.002);
        assert_eq!(data["xpFlatPerDelivery"], 250.12499999999997);
        assert_eq!(data["startingMoney"], 5000);
        assert_eq!(data["startingMoneyMax"], 18000);
    }

    #[test]
    fn city_labels_drop_a_missing_state() {
        let dir = tempfile::tempdir().unwrap();
        fs::create_dir_all(dir.path().join("us")).unwrap();
        fs::write(
            dir.path().join("us/cities.json"),
            r#"{"cities": {"nowhere_us": {"spoken_city": "Nowhere"}, "austin_tx_us": {"spoken_city": "Austin", "state": "TX"}}}"#,
        )
        .unwrap();
        fs::write(
            dir.path().join("geo.json"),
            r#"{"countries": {"US": {"name": "United States", "states": {"TX": "Texas"}}}}"#,
        )
        .unwrap();
        let labels = city_labels(dir.path()).unwrap();
        assert_eq!(labels["nowhere_us"], "Nowhere");
        assert_eq!(labels["austin_tx_us"], "Austin, Texas");
    }

    #[test]
    fn rendered_invariants_are_sorted_two_space_json() {
        let text = rendered_invariants(&world_data_root(), &inputs()).unwrap();
        assert!(text.starts_with("{\n  \"achievementIds\": [\n    \"antler_polisher\",\n"));
        assert!(text.contains("\n  \"endorsements\": {\n    \"heavy_haul\": {\n      \"label\": \"heavy-haul\",\n      \"level\": 3\n    },"));
        assert!(text.ends_with("}\n"));
    }
}
