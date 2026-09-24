//! Company carriers loaded from `data/carriers.json` (Career 2.0 carrier scope).
//!
//! Start-flow UX (`START_OPTIONS`) still names the career opens; pay knobs,
//! dispatch biases, cargo bonuses, tier, terminals, hiring radius, and run
//! band live here. `home_time_policy` is stored but inert until the week/home
//! loop lands — never claim weekly home time in UI or speech.

use indexmap::IndexMap;
use once_cell::sync::OnceCell;
use serde::Deserialize;

use crate::data::data_resources::read_data_text;
use crate::data::world::get_world;
use crate::data::world_models::DataError;
use crate::models::start_options::{CompanyPayPlan, DispatchProfile, NORTHSTAR_PAY};

pub const CARRIER_TIERS: &[&str] = &["local", "regional", "national"];

#[derive(Debug, Clone, PartialEq)]
pub struct RunBand {
    pub min_mi: f64,
    pub max_mi: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Carrier {
    pub key: String,
    pub name: String,
    pub tier: String,
    pub terminal_city_keys: Vec<String>,
    /// `None` = nationwide (national tier).
    pub hiring_radius_mi: Option<f64>,
    /// Stored for later week/home work; must stay inert in speech/UI.
    pub home_time_policy: String,
    pub run_band: RunBand,
    pub company_pay: CompanyPayPlan,
    pub dispatch: DispatchProfile,
    pub cargo_weight_bonus: Vec<(String, f64)>,
    pub solvency_fallback: bool,
}

impl Carrier {
    pub fn cargo_weight_bonus_for(&self, cargo_key: &str) -> f64 {
        self.cargo_weight_bonus
            .iter()
            .find(|(k, _)| k == cargo_key)
            .map(|(_, bonus)| *bonus)
            .unwrap_or(0.0)
    }

    /// Effective board distance cap: tighter of the level cap and this
    /// carrier's run-band max.
    pub fn effective_distance_cap(&self, level_cap_mi: f64) -> f64 {
        level_cap_mi.min(self.run_band.max_mi)
    }

    pub fn run_band_allows(&self, miles: f64) -> bool {
        miles + f64::EPSILON >= self.run_band.min_mi && miles <= self.run_band.max_mi + f64::EPSILON
    }
}

#[derive(Deserialize)]
struct RawRunBand {
    min: f64,
    max: f64,
}

#[derive(Deserialize)]
struct RawPay {
    pay_share: f64,
    min_per_mile: f64,
    stop_pay: f64,
    on_time_bonus_share: f64,
}

#[derive(Deserialize)]
struct RawDispatch {
    #[serde(default)]
    short_haul_bias: f64,
    #[serde(default)]
    regional_bias: f64,
    #[serde(default)]
    long_haul_bias: f64,
    #[serde(default = "one")]
    deadline_slack: f64,
}

fn one() -> f64 {
    1.0
}

#[derive(Deserialize)]
struct RawCarrier {
    name: String,
    tier: String,
    terminal_city_keys: Vec<String>,
    #[serde(default)]
    hiring_radius_mi: Option<f64>,
    #[serde(default = "inert_policy")]
    home_time_policy: String,
    run_band_mi: RawRunBand,
    company_pay: RawPay,
    #[serde(default)]
    dispatch: RawDispatch,
    #[serde(default)]
    cargo_weight_bonus: IndexMap<String, f64>,
    #[serde(default)]
    solvency_fallback: bool,
}

fn inert_policy() -> String {
    "inert".into()
}

impl Default for RawDispatch {
    fn default() -> Self {
        RawDispatch {
            short_haul_bias: 0.0,
            regional_bias: 0.0,
            long_haul_bias: 0.0,
            deadline_slack: 1.0,
        }
    }
}

fn parse_catalog(text: &str) -> Result<IndexMap<String, Carrier>, DataError> {
    let raw: IndexMap<String, RawCarrier> = serde_json::from_str(text)
        .map_err(|err| DataError::value(format!("carriers.json: {err}")))?;
    let mut catalog = IndexMap::new();
    let mut fallbacks = 0usize;
    for (key, raw) in raw {
        if key.trim().is_empty() {
            return Err(DataError::value("carriers.json: empty carrier key"));
        }
        if !CARRIER_TIERS.contains(&raw.tier.as_str()) {
            return Err(DataError::value(format!(
                "carriers.json: carrier {key} has unknown tier {}",
                raw.tier
            )));
        }
        if raw.terminal_city_keys.is_empty() {
            return Err(DataError::value(format!(
                "carriers.json: carrier {key} needs at least one terminal city"
            )));
        }
        if raw.run_band_mi.min <= 0.0 || raw.run_band_mi.max < raw.run_band_mi.min {
            return Err(DataError::value(format!(
                "carriers.json: carrier {key} has invalid run_band_mi"
            )));
        }
        if raw.tier == "national" && raw.hiring_radius_mi.is_some() {
            return Err(DataError::value(format!(
                "carriers.json: national carrier {key} must leave hiring_radius_mi null"
            )));
        }
        if raw.tier != "national" && raw.hiring_radius_mi.is_none() {
            return Err(DataError::value(format!(
                "carriers.json: {tier} carrier {key} needs hiring_radius_mi",
                tier = raw.tier
            )));
        }
        if raw.solvency_fallback {
            fallbacks += 1;
        }
        let carrier = Carrier {
            key: key.clone(),
            name: raw.name,
            tier: raw.tier,
            terminal_city_keys: raw.terminal_city_keys,
            hiring_radius_mi: raw.hiring_radius_mi,
            home_time_policy: raw.home_time_policy,
            run_band: RunBand {
                min_mi: raw.run_band_mi.min,
                max_mi: raw.run_band_mi.max,
            },
            company_pay: CompanyPayPlan {
                pay_share: raw.company_pay.pay_share,
                min_per_mile: raw.company_pay.min_per_mile,
                stop_pay: raw.company_pay.stop_pay,
                on_time_bonus_share: raw.company_pay.on_time_bonus_share,
            },
            dispatch: DispatchProfile {
                short_haul_bias: raw.dispatch.short_haul_bias,
                regional_bias: raw.dispatch.regional_bias,
                long_haul_bias: raw.dispatch.long_haul_bias,
                deadline_slack: raw.dispatch.deadline_slack,
            },
            cargo_weight_bonus: raw.cargo_weight_bonus.into_iter().collect(),
            solvency_fallback: raw.solvency_fallback,
        };
        catalog.insert(key, carrier);
    }
    if fallbacks != 1 {
        return Err(DataError::value(format!(
            "carriers.json: exactly one solvency_fallback carrier required, found {fallbacks}"
        )));
    }
    Ok(catalog)
}

fn load_catalog() -> Result<IndexMap<String, Carrier>, DataError> {
    let text = read_data_text("carriers.json")
        .ok_or_else(|| DataError::io("carriers.json is missing from this build"))?;
    parse_catalog(&text)
}

static CATALOG: OnceCell<IndexMap<String, Carrier>> = OnceCell::new();

pub fn carrier_catalog() -> &'static IndexMap<String, Carrier> {
    CATALOG.get_or_init(|| load_catalog().expect("carriers.json loads and validates"))
}

pub fn carrier(key: &str) -> Option<&'static Carrier> {
    carrier_catalog().get(key)
}

pub fn solvency_fallback_carrier() -> &'static Carrier {
    carrier_catalog()
        .values()
        .find(|c| c.solvency_fallback)
        .expect("carriers.json names exactly one solvency fallback")
}

/// Validate terminal cities exist and host a real company_yard or terminal.
pub fn validate_carrier_terminals() -> Result<(), DataError> {
    let world = get_world();
    for carrier in carrier_catalog().values() {
        for city_key in &carrier.terminal_city_keys {
            let city = world.city(city_key).map_err(|_| {
                DataError::value(format!(
                    "carriers.json: carrier {} terminal city {city_key} is unknown",
                    carrier.key
                ))
            })?;
            let ok = city
                .locations
                .iter()
                .any(|loc| matches!(loc.facility_type.as_str(), "company_yard" | "terminal"));
            if !ok {
                return Err(DataError::value(format!(
                    "carriers.json: carrier {} terminal {city_key} has no company_yard/terminal",
                    carrier.key
                )));
            }
        }
    }
    Ok(())
}

/// Pay plan for a carrier key; unknown keys fall back to Northstar wages.
pub fn pay_plan_for_carrier(key: &str) -> CompanyPayPlan {
    carrier(key).map(|c| c.company_pay).unwrap_or(NORTHSTAR_PAY)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::enforcement::LAST_CHANCE_CARRIER_KEY;

    #[test]
    fn test_carriers_json_loads_and_retiers() {
        let catalog = carrier_catalog();
        assert_eq!(catalog.len(), 4);
        let northstar = carrier("northstar").expect("northstar");
        assert_eq!(northstar.tier, "national");
        assert_eq!(northstar.run_band.min_mi, 400.0);
        assert_eq!(northstar.run_band.max_mi, 3000.0);
        assert!(northstar.hiring_radius_mi.is_none());

        let gl = carrier("great_lakes_training").expect("great lakes");
        assert_eq!(gl.tier, "national");
        assert!(gl.solvency_fallback);
        assert_eq!(solvency_fallback_carrier().key, LAST_CHANCE_CARRIER_KEY);

        let prairie = carrier("prairie_link").expect("prairie");
        assert_eq!(prairie.tier, "regional");
        assert_eq!(prairie.hiring_radius_mi, Some(250.0));
        assert_eq!(prairie.run_band.min_mi, 150.0);
        assert_eq!(prairie.run_band.max_mi, 600.0);
        assert_eq!(
            prairie.terminal_city_keys,
            vec![
                "kansas_city_mo_us".to_string(),
                "omaha_ne_us".to_string(),
                "wichita_ks_us".to_string(),
            ]
        );

        let summit = carrier("summit_value").expect("summit");
        assert_eq!(summit.tier, "national");
        assert_eq!(summit.home_time_policy, "inert");
    }

    #[test]
    fn test_carrier_terminals_are_real_yards() {
        validate_carrier_terminals().expect("terminals validate");
    }

    #[test]
    fn test_effective_distance_cap_takes_the_tighter_limit() {
        let prairie = carrier("prairie_link").unwrap();
        assert_eq!(prairie.effective_distance_cap(1200.0), 600.0);
        assert_eq!(prairie.effective_distance_cap(400.0), 400.0);
        assert!(prairie.run_band_allows(150.0));
        assert!(prairie.run_band_allows(600.0));
        assert!(!prairie.run_band_allows(149.0));
        assert!(!prairie.run_band_allows(601.0));
    }
}
