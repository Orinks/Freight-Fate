//! Per-truck condition records and the legacy flat-field migrations
//! (`_fresh_condition`, `_truck_tank_gal`, `_migrate_flat_conditions`,
//! `_migrate_profile_wide_grime` of `profile.py`).

use indexmap::IndexMap;
use serde_json::{json, Map, Value};

use super::{ConditionRecord, DEFAULT_FUEL_GAL};
use crate::models::business_constants::{is_owner_operator, COMPANY_DRIVER};
use crate::models::jobs::py_str;
use crate::models::save_migration::json_f64;
use crate::models::trucks::{build_truck_specs, truck_model, UpgradeTiers};

/// The keys `_fresh_condition()` writes, in order.
pub const CONDITION_FIELDS: &[&str] = &[
    "tire_wear_pct",
    "brake_wear_pct",
    "engine_wear_pct",
    "damage_pct",
    "grime_pct",
    "fuel_gal",
    "tire_type",
    "chains_owned",
    "chain_wear_pct",
];

/// A brand-new truck's condition record: no wear, no damage, given fuel.
///
/// Traction equipment rides in the same record -- tire compound, whether a
/// chain set is aboard, and how worn that set is -- because it bolts to the
/// truck, not the driver. Older records missing these keys read as the
/// defaults through the accessor `get` calls.
pub fn fresh_condition(fuel_gal: f64) -> ConditionRecord {
    let value = json!({
        "tire_wear_pct": 0.0,
        "brake_wear_pct": 0.0,
        "engine_wear_pct": 0.0,
        "damage_pct": 0.0,
        "grime_pct": 0.0,
        "fuel_gal": fuel_gal,
        "tire_type": "all_season",
        "chains_owned": false,
        "chain_wear_pct": 0.0,
    });
    match value {
        Value::Object(map) => map,
        _ => unreachable!("json! object"),
    }
}

/// A truck's full-tank capacity, or the default if its specs won't build.
///
/// Upgrades matter here: a long-range tank is a truck's capacity, so a career
/// that bought one must not be migrated back down to the base tank.
pub fn truck_tank_gal<U: UpgradeTiers + ?Sized>(key: &str, upgrades: &U) -> f64 {
    if truck_model(key).is_none() {
        return DEFAULT_FUEL_GAL;
    }
    build_truck_specs(key, upgrades).fuel_tank_gal
}

/// `profile.upgrades` as the Python `dict[str, int]` read off a raw save:
/// non-dict values are an empty dict, non-integer tiers are dropped.
pub fn upgrades_from_value(value: Option<&Value>) -> IndexMap<String, i64> {
    let mut out = IndexMap::new();
    if let Some(Value::Object(map)) = value {
        for (key, tier) in map {
            if let Some(tier) = tier.as_i64() {
                out.insert(key.clone(), tier);
            } else if let Some(tier) = tier.as_f64() {
                out.insert(key.clone(), tier.trunc() as i64);
            }
        }
    }
    out
}

/// Build per-truck condition records from a pre-migration flat profile.
///
/// Every owned truck (and the active/assigned key) inherits the profile's one
/// saved wear and damage set -- no free pristine spares from a swap. The
/// active truck also inherits the saved fuel; other parked trucks start with
/// full tanks (they were sitting still, and a fuel windfall is worth cents,
/// not an exploit).
pub fn migrate_flat_conditions(data: &Map<String, Value>) -> IndexMap<String, ConditionRecord> {
    // Clamped, not trusted. A save carrying an impossible wear figure is
    // repaired on the way in; loading it verbatim would leave an old career
    // failing its own invariant check the moment it opened, which reads to
    // the player as a tampered save rather than an old one.
    let pct = |key: &str| json_f64(data.get(key), 0.0).clamp(0.0, 100.0);

    let tire = pct("tire_wear_pct");
    let brake = pct("brake_wear_pct");
    let engine = pct("engine_wear_pct");
    let damage = pct("truck_damage_pct");

    let status = data
        .get("business_status")
        .and_then(Value::as_str)
        .unwrap_or(COMPANY_DRIVER);
    let owns = is_owner_operator(status);
    let active = if owns {
        data.get("truck")
            .map(py_str)
            .unwrap_or_else(|| "rig".to_string())
    } else {
        "rig".to_string()
    };
    let mut keys: Vec<String> = Vec::new();
    if let Some(Value::Array(owned)) = data.get("owned_trucks") {
        for key in owned {
            let key = py_str(key);
            if !keys.contains(&key) {
                keys.push(key);
            }
        }
    }
    if !keys.contains(&active) {
        keys.push(active.clone());
    }

    // Tanks are sized with the career's upgrades applied, so a driver who paid
    // for a long-range tank keeps it through the migration on every truck.
    let upgrades = upgrades_from_value(data.get("upgrades"));
    let active_tank = truck_tank_gal(&active, &upgrades);
    let fuel = json_f64(data.get("truck_fuel_gal"), DEFAULT_FUEL_GAL).clamp(0.0, active_tank);

    let grime = pct("road_grime_pct");

    let mut conditions: IndexMap<String, ConditionRecord> = IndexMap::new();
    for key in keys {
        let fuel_gal = if key == active {
            fuel
        } else {
            truck_tank_gal(&key, &upgrades)
        };
        let record = json!({
            "tire_wear_pct": tire,
            "brake_wear_pct": brake,
            "engine_wear_pct": engine,
            "damage_pct": damage,
            "grime_pct": grime,
            "fuel_gal": fuel_gal,
        });
        if let Value::Object(map) = record {
            conditions.insert(key, map);
        }
    }
    conditions
}

/// Move a profile-wide `road_grime_pct` into each truck's record.
///
/// Grime followed the driver on this line while every other kind of wear had
/// already moved onto the truck -- an alpha-only gap left when the mainline's
/// per-truck accessors were dropped as duplicates during a merge. A save
/// written before this fix carries the flat field and condition records with
/// no `grime_pct`, so match on that shape rather than on a save version: the
/// records were already fanned out, so there is no version to key off.
///
/// Every truck inherits the one saved figure, the same rule the original
/// fan-out uses -- a parked truck was as dirty as the career said it was, and
/// handing out clean spares would wash a fleet for free.
pub fn migrate_profile_wide_grime(data: &mut Map<String, Value>) -> bool {
    let flat = data.remove("road_grime_pct");
    let Some(Value::Object(conditions)) = data.get_mut("truck_conditions") else {
        return flat.is_some();
    };
    let grime = match &flat {
        Some(value) => json_f64(Some(value), 0.0).clamp(0.0, 100.0),
        None => 0.0,
    };
    let mut moved = false;
    for record in conditions.values_mut() {
        if let Value::Object(record) = record {
            if !record.contains_key("grime_pct") {
                record.insert("grime_pct".to_string(), json!(grime));
                moved = true;
            }
        }
    }
    moved || flat.is_some()
}
