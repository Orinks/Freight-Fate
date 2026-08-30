//! Catalog snapshot shared with the orinks.net cloud-save validator.
//!
//! Port of `freight_fate/profile_integrity_invariants.py`. This is a
//! source-tree-only export for the validator; never called by the game at
//! runtime, so frozen builds (which carry no world_data tree) are
//! unaffected.
//!
//! The Python module reads every figure straight off the models package
//! (`ACHIEVEMENTS`, `Career`, `Profile`, `TRUCK_CATALOG`, ...). The Rust
//! rendering takes those figures as a [`CatalogInputs`] argument so the
//! module itself stays free of the model layer; [`CatalogInputs::current`]
//! is the one that reads the real shipped catalogs, and it is what the
//! `ff-invariants` binary writes the file from. City labels are read from
//! the world data under the `data_root` the caller passes
//! ([`world_data_root`] resolves the shipped one).
//!
//! Anything that renders this file for the server must go through
//! `current()`: a hand-assembled `CatalogInputs` is a fixture, and a
//! fixture shipped to the validator is a validator that convicts honest
//! players (or acquits edited careers) the moment it disagrees with the
//! game.

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

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

/// One credential row: key, the carrier-sponsored level (None for a
/// credential only ever earned through its course -- the site must not
/// level-derive those), the spoken label, and the ladder tier.
#[derive(Debug, Clone, PartialEq)]
pub struct EndorsementRow {
    pub key: String,
    pub level: Option<i64>,
    pub label: String,
    pub tier: String,
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

impl CatalogInputs {
    /// The figures the shipped game actually awards, read off the live
    /// catalogs -- the Rust equivalent of the module-level imports at the top
    /// of `profile_integrity_invariants.py`.
    ///
    /// This is the only assembly the exporter may use. Every field below
    /// names the Python constant it stands in for, so a balance pass that
    /// moves a constant moves the export with it and the validator on
    /// orinks.net never falls behind the build players are running.
    pub fn current() -> Self {
        use crate::achievements::ACHIEVEMENTS;
        use crate::models::career::{
            Career, DELIVERY_COMPLETION_XP, LEVEL_XP, XP_CLEAN_BONUS, XP_PER_MILE_ON_TIME,
            XP_SPECIALTY_MULT, XP_STREAK_MAX_BONUS,
        };
        use crate::models::carrier_fleet::FLEET_TIERS;
        use crate::models::credentials::CREDENTIALS;
        use crate::models::economy::PAY_ADVANCE_LIMIT;
        use crate::models::market::MARKET_CARGO_KEYS;
        use crate::models::profile::{
            fresh_condition, PROFILE_FIELDS, SAVE_VERSION, STARTING_MONEY,
        };
        use crate::models::start_options::all_start_options;
        use crate::models::trucks::{TRUCK_CATALOG, UPGRADE_CATALOG};

        // `sorted(Career.__dataclass_fields__)`. The Rust dataclass is the
        // serde shape of the same struct -- serialising the default is what
        // guarantees the exported list is the key set a save actually
        // carries, rather than a second list that can drift from it.
        let career_json =
            serde_json::to_value(Career::default()).expect("Career serialises to a JSON object");
        let career_fields: Vec<String> = career_json
            .as_object()
            .expect("Career serialises to a JSON object")
            .keys()
            .cloned()
            .collect();

        let endorsements: Vec<EndorsementRow> = CREDENTIALS
            .iter()
            .map(|cred| EndorsementRow {
                key: cred.key.to_string(),
                level: cred.grant_level,
                label: cred.label.to_string(),
                tier: cred.tier.as_str().to_string(),
            })
            .collect();

        CatalogInputs {
            achievement_ids: ACHIEVEMENTS
                .iter()
                .map(|badge| badge.id.to_string())
                .collect(),
            starting_money: STARTING_MONEY,
            starting_money_max: all_start_options()
                .iter()
                .map(|option| option.starting_money)
                .fold(f64::NEG_INFINITY, f64::max),
            pay_advance_limit: PAY_ADVANCE_LIMIT,
            xp_per_mile_on_time: XP_PER_MILE_ON_TIME,
            xp_specialty_mult: XP_SPECIALTY_MULT,
            xp_streak_max_bonus: XP_STREAK_MAX_BONUS,
            xp_clean_bonus: XP_CLEAN_BONUS,
            delivery_completion_xp: DELIVERY_COMPLETION_XP,
            level_xp: LEVEL_XP.iter().map(|xp| *xp as i64).collect(),
            market_cargo_keys: MARKET_CARGO_KEYS
                .iter()
                .map(|key| key.to_string())
                .collect(),
            profile_fields: PROFILE_FIELDS
                .iter()
                .map(|field| field.to_string())
                .collect(),
            career_fields,
            endorsements,
            fleet_tiers: FLEET_TIERS
                .iter()
                .map(|tier| FleetTierRow {
                    min_level: tier.min_level,
                    label: tier.label.to_string(),
                })
                .collect(),
            // `sorted(_fresh_condition())` -- the keys off a record the game
            // really writes, not a second list beside it. The Python comment
            // on `truck_condition_fields` below is the whole reason: the
            // export once came off a dataclass that had stopped matching the
            // record, and told the server five legitimate keys were unknown.
            truck_condition_fields: fresh_condition(0.0).keys().cloned().collect(),
            source_save_version: SAVE_VERSION,
            trucks: TRUCK_CATALOG
                .iter()
                .map(|(key, truck)| (key.to_string(), truck.label.to_string(), truck.price))
                .collect(),
            upgrade_prices: UPGRADE_CATALOG
                .iter()
                .map(|upgrade| (upgrade.key.to_string(), upgrade.prices.to_vec()))
                .collect(),
        }
    }
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
        // A course-only credential carries no level at all: the site's
        // held-check is `level >= entry.level || purchased`, and a missing
        // key comparing false is what keeps a background-checked credential
        // from being credited to every driver of some level.
        if let Some(level) = row.level {
            entry.insert("level".to_string(), Value::from(level));
        }
        entry.insert("label".to_string(), Value::from(row.label.clone()));
        entry.insert("tier".to_string(), Value::from(row.tier.clone()));
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

/// The `world_data` tree the shipped export reads its city labels from.
///
/// Python resolves this as `Path(__file__).parent / "data" / "world_data"`;
/// here it hangs off the same [`data_root`](crate::data::data_resources::data_root)
/// every other data reader uses, so `FREIGHT_FATE_DATA_ROOT` points the
/// exporter at a checkout the same way it points the game at one.
pub fn world_data_root() -> PathBuf {
    crate::data::data_resources::data_root().join("world_data")
}

/// `invariant_data()` with no arguments: the shipped catalogs, the shipped
/// world data. This is the production path.
pub fn current_invariant_data() -> Result<Value, String> {
    invariant_data(&world_data_root(), &CatalogInputs::current())
}

/// `rendered_invariants()` with no arguments: the exact bytes
/// `tools/export_profile_integrity_invariants.py` writes, and the exact bytes
/// the orinks.net validator is built from.
pub fn current_rendered_invariants() -> Result<String, String> {
    rendered_invariants(&world_data_root(), &CatalogInputs::current())
}

#[cfg(test)]
mod tests {
    use super::*;

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
                    level: Some(2),
                    label: "refrigerated".into(),
                    tier: "certificate".into(),
                },
                EndorsementRow {
                    key: "heavy_haul".into(),
                    level: Some(3),
                    label: "heavy-haul".into(),
                    tier: "certificate".into(),
                },
                EndorsementRow {
                    key: "hazmat".into(),
                    level: None,
                    label: "hazmat".into(),
                    tier: "endorsement".into(),
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
        let data = current_invariant_data().unwrap();
        assert!(data["sourceSaveVersion"].as_i64().unwrap() >= 1);
        assert_eq!(data["cityLabels"]["new_york_ny_us"], "New York, New York");
        assert_eq!(data["truckLabels"]["rig"], "standard rig");
        assert_eq!(data["levelXp"][0], 0);
        assert!(current_rendered_invariants().unwrap().ends_with('\n'));
    }

    /// The exported ceiling must sit at or above what record_delivery awards.
    ///
    /// The server rejects a cloud backup whose XP exceeds
    /// `deliveries * xpFlatPerDelivery + total_miles * xpPerMileMax`. If a
    /// balance pass raises the game's rates past the exported figures, that
    /// check starts convicting the drivers who played best -- which is exactly
    /// how a hardcoded 1.2 per mile came to sit below the on-time rate. Drive
    /// a spread of careers through the real award path and hold the line.
    #[test]
    fn test_exported_xp_ceiling_bounds_every_honest_career() {
        use crate::models::career::{Career, XP_PREMIUM_MULT, XP_SPECIALTY_MULT};
        use crate::pyrandom::PyRandom;

        let data = current_invariant_data().unwrap();
        let per_mile = data["xpPerMileMax"].as_f64().unwrap();
        let flat = data["xpFlatPerDelivery"].as_f64().unwrap();
        let mut rng = PyRandom::new_from_i64(7);

        for _ in 0..2_000 {
            let mut career = Career::default();
            let deliveries = rng.randint(1, 40);
            for _ in 0..deliveries {
                let miles = rng.uniform(1.0, 900.0);
                let on_time = rng.random() < 0.9;
                let damage_pct = *rng.choice(&[0.0, 0.5, 30.0]);
                let cargo_class_mult = *rng.choice(&[1.0, XP_PREMIUM_MULT, XP_SPECIALTY_MULT]);
                career.record_delivery(miles, 0.0, on_time, damage_pct, cargo_class_mult, 1.0);
            }
            let ceiling = career.deliveries as f64 * flat + career.total_miles * per_mile;
            assert!(
                career.xp <= ceiling,
                "{} XP over {} miles in {} deliveries breaches the exported ceiling {ceiling}",
                career.xp,
                career.total_miles,
                career.deliveries
            );
        }
    }

    /// The money rule's floor is this figure; a new profile must equal it.
    #[test]
    fn test_exported_starting_money_matches_a_fresh_career() {
        let data = current_invariant_data().unwrap();
        assert_eq!(
            data["startingMoney"].as_f64().unwrap(),
            crate::models::profile::Profile::new().money
        );
    }

    /// The server's money ceiling credits the richest career start.
    ///
    /// The owner-operator option opens with more cash than the company-driver
    /// default; a ceiling built on the default rejected every honest
    /// owner-operator backup as impossible_money until earnings outgrew the gap.
    #[test]
    fn test_exported_starting_money_max_covers_every_start_option() {
        use crate::models::start_options::all_start_options;

        let data = current_invariant_data().unwrap();
        let exported = data["startingMoneyMax"].as_f64().unwrap();
        let mut richest = f64::MIN;
        for option in all_start_options() {
            assert!(option.starting_money <= exported, "{}", option.key);
            richest = richest.max(option.starting_money);
        }
        assert_eq!(exported, richest);
    }

    /// The export must describe the record the game actually writes.
    ///
    /// The server checks every truck_conditions record against this list and
    /// rejects a save carrying a key it does not know. The list used to come
    /// off the TruckCondition dataclass, which this line stopped using --
    /// records are plain dicts, and they grew brake wear, engine wear and
    /// traction gear while the dataclass kept four fields.
    #[test]
    fn test_exported_condition_fields_match_a_real_record() {
        let mut profile = crate::models::profile::Profile::new();
        profile.provision_truck_condition("rig", None);
        let mut written: Vec<String> = profile.truck_conditions["rig"].keys().cloned().collect();
        written.sort();
        let data = current_invariant_data().unwrap();
        let exported: Vec<String> = data["truckConditionFields"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_str().unwrap().to_string())
            .collect();
        assert_eq!(exported, written);
    }

    #[test]
    fn test_exported_profile_fields_include_the_created_on_marker() {
        // The 1.9 cutover regen must teach the server allow-list `created_line`.
        // Every 1.9 upload carries the marker, so a validator built from an
        // export without it would reject every honest backup on the schema check.
        let data = current_invariant_data().unwrap();
        let fields = data["profileFields"].as_array().unwrap();
        assert!(fields.contains(&Value::from("created_line")));
        // The local-only signature keys never ride the export.
        assert!(!fields.contains(&Value::from("_signature")));
        assert!(fields.contains(&Value::from("version")));
    }

    #[test]
    fn test_exported_public_profile_fields_ride_the_allow_lists() {
        let data = current_invariant_data().unwrap();
        assert!(data["profileFields"]
            .as_array()
            .unwrap()
            .contains(&Value::from("business_status")));
        assert!(data["careerFields"]
            .as_array()
            .unwrap()
            .contains(&Value::from("purchased_endorsements")));
    }

    /// The site derives each driver's endorsements from this table.
    ///
    /// Hold it to the real unlock path: a career levelled to each exported
    /// threshold must hold exactly the endorsements the export promises at
    /// that level, or the public profile starts crediting training the carrier
    /// never sponsored (or hiding training it did).
    #[test]
    fn test_exported_endorsements_match_what_the_career_actually_unlocks() {
        use crate::models::career::{Career, LEVEL_XP};
        use std::collections::BTreeSet;

        let data = current_invariant_data().unwrap();
        let endorsements = data["endorsements"].as_object().unwrap();
        for level in 1..=LEVEL_XP.len() as i64 {
            let career = Career {
                xp: LEVEL_XP[level as usize - 1],
                ..Career::default()
            };
            assert_eq!(career.level(), level);
            // A row without a level is course-only: the site must never
            // level-derive it, and neither does the career.
            let expected: BTreeSet<&str> = endorsements
                .iter()
                .filter(|(_, entry)| {
                    entry
                        .get("level")
                        .and_then(Value::as_i64)
                        .is_some_and(|lvl| level >= lvl)
                })
                .map(|(key, _)| key.as_str())
                .collect();
            let held: BTreeSet<&str> = career.endorsements().into_iter().collect();
            assert_eq!(held, expected, "level {level}");
        }

        // A self-paid course unlocks ahead of the sponsored level, which is
        // why purchased_endorsements has to reach the server at all.
        let early = Career {
            xp: 0.0,
            purchased_endorsements: vec!["heavy_haul".to_string()],
            ..Career::default()
        };
        assert!(early.endorsements().contains("heavy_haul"));
    }

    /// The site names a company driver's fleet tier from these bands.
    #[test]
    fn test_exported_fleet_tiers_match_the_carrier_fleet_bands() {
        use crate::models::carrier_fleet::fleet_tier_for_level;

        let data = current_invariant_data().unwrap();
        let tiers = data["fleetTiers"].as_array().unwrap();
        // every level maps to a band
        assert_eq!(tiers[0]["minLevel"].as_i64().unwrap(), 1);
        let min_levels: Vec<i64> = tiers
            .iter()
            .map(|t| t["minLevel"].as_i64().unwrap())
            .collect();
        let mut sorted = min_levels.clone();
        sorted.sort_unstable();
        assert_eq!(min_levels, sorted);
        for level in 1..31 {
            let expected = fleet_tier_for_level(level).label;
            let banded = tiers
                .iter()
                .rfind(|t| level >= t["minLevel"].as_i64().unwrap())
                .unwrap()["label"]
                .as_str()
                .unwrap();
            assert_eq!(banded, expected, "level {level}");
        }
    }

    #[test]
    fn the_xp_ceiling_terms_follow_the_python_arithmetic() {
        // Python invariant_data() on 2026-08-22: xpPerMileMax 4.002,
        // xpFlatPerDelivery 250.12499999999997. Against the live catalogs,
        // not the fixture: the point is that Rust's float arithmetic lands on
        // Python's exact repr, and a fixture that copies the same constants
        // would pass without ever asking the game.
        let data = current_invariant_data().unwrap();
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
        assert!(text.contains("\n  \"endorsements\": {\n    \"hazmat\": {\n      \"label\": \"hazmat\",\n      \"tier\": \"endorsement\"\n    },\n    \"heavy_haul\": {\n      \"label\": \"heavy-haul\",\n      \"level\": 3,\n      \"tier\": \"certificate\"\n    },"));
        assert!(text.ends_with("}\n"));
    }
}
