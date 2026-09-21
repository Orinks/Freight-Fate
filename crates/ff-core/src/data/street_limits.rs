//! Statutory street speed limits, per state, with the law behind each one
//! (port of `freight_fate/data/street_limits.py`).
//!
//! A city street is very rarely tagged in OpenStreetMap: measured across the
//! cached extracts, `service` ways carry a `maxspeed` on 0.2 to 1.3 percent of
//! their length and `residential` on 2 to 14 percent
//! (`tools/maxspeed_coverage.py`). So the last mile into a facility cannot be
//! READ, and for a long time the game filled the gap with a flat 25 that
//! nothing stood behind.
//!
//! What does stand behind it is the law. Every state's vehicle code sets a
//! default speed limit for business and residence districts that governs
//! precisely when no sign is posted -- which is the situation the map leaves
//! us in. That number is a reading from a published legal source, not a
//! guess, so this layer is `read` in the provenance sense even though no
//! surveyor measured the street.
//!
//! The curated table with its citations lives in `tools/statutory_limits.py`;
//! this module loads what that tool bakes and answers questions about it. A
//! state the table does not cover falls back to `FALLBACK_MPH`, which is
//! `assumed` and says so through `is_assumed`.

use std::path::{Path, PathBuf};

use indexmap::IndexMap;
use once_cell::sync::OnceCell;
use serde::Deserialize;
use serde_json::Value;

use super::data_resources::{data_path, read_text_at};
use super::world_models::DataError;
use crate::pyfmt::py_str_float;

/// The shipped table (Python `STREET_LIMITS_PATH`).
pub fn street_limits_path() -> PathBuf {
    data_path("street_limits.json")
}

/// Where the table is silent. Not a number anyone legislated: it is the old
/// blanket access-road speed, kept only so an uncovered state still drives.
pub const FALLBACK_MPH: f64 = 25.0;

/// Nothing in any state's code puts an ordinary street outside this band, so a
/// row beyond it is a transcription error rather than an unusual jurisdiction.
pub const MIN_PLAUSIBLE_MPH: f64 = 10.0;
pub const MAX_PLAUSIBLE_MPH: f64 = 45.0;

/// One state's default limits for unposted streets, and its citation.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct StatutoryLimit {
    pub state: String,
    pub business_mph: Option<f64>,
    pub residence_mph: Option<f64>,
    pub urban_mph: Option<f64>,
    pub citation: String,
    pub title: String,
    pub url: String,
    /// "absolute" or "prima facie"
    pub rule_type: String,
    pub signs_required: bool,
    pub truck_note: String,
    pub verified: bool,
    pub notes: String,
    /// True where the state's code genuinely writes no district default --
    /// a researched finding, not a missing row. Connecticut is the case: a
    /// limit there exists only where a traffic authority has established and
    /// SIGNED a zone, so the legally correct figure for an unposted street is
    /// the 55 ceiling, which is not a number to drive a yard approach at. The
    /// runtime falls back for these exactly as it does for an unknown state.
    pub no_district_default: bool,
}

impl StatutoryLimit {
    /// The number to post on the way in to a freight facility.
    ///
    /// A warehouse, terminal, or cross-dock stands in a business or
    /// industrial district, so the business-district figure is the one that
    /// governs. States that write a single urban-district limit instead
    /// answer with that, and the residence figure is the last resort -- some
    /// codes give only that one, and a residential street is still nearer to
    /// a yard approach than any highway default.
    ///
    /// None where the state's own figures do not reach an UNPOSTED street,
    /// which is the only situation this table exists for. Pennsylvania is the
    /// case that forced the check: 75 Pa.C.S. 3362(b)(1) makes its 35 mph
    /// urban and 25 mph residence limits ineffective unless signs stand at
    /// both ends of the zone and every half mile between, so on a street with
    /// no sign the enforceable maximum is the 55 ceiling instead. Reading
    /// Pennsylvania's 35 off the page and posting it would have been the
    /// exact failure this layer was built to stop -- a number that is real in
    /// the statute and false on the road.
    pub fn facility_street_mph(&self) -> Option<f64> {
        if self.signs_required {
            return None;
        }
        [self.business_mph, self.urban_mph, self.residence_mph]
            .into_iter()
            .flatten()
            .next()
    }
}

/// The loaded table. Lookup is by the spoken state name the world uses.
#[derive(Debug, Clone, Default)]
pub struct StreetLimits {
    rows: IndexMap<String, StatutoryLimit>,
    /// The bake's own summary (`states`, `verified`, `unverified`, `source`).
    pub meta: serde_json::Map<String, Value>,
}

impl StreetLimits {
    pub fn new(
        rows: IndexMap<String, StatutoryLimit>,
        meta: serde_json::Map<String, Value>,
    ) -> Self {
        StreetLimits { rows, meta }
    }

    pub fn get(&self, state: &str) -> Option<&StatutoryLimit> {
        self.rows.get(state.trim())
    }

    /// The number the law really gives for an unposted street here, or None.
    ///
    /// THE one rule, so that every view of this table agrees. It said
    /// different things in two places for an afternoon: this accessor handed
    /// back an unverified state's figure while `is_assumed` called the same
    /// state assumed, and only the trip's own separate `verified` check kept
    /// an unconfirmed number off the road. Three views, one rule, no third
    /// place to forget.
    ///
    /// None when the state is unknown, when its code writes no district
    /// default, when its figures only bind once signs are posted, or when
    /// nobody could confirm the reading.
    pub fn statutory_mph(&self, state: &str) -> Option<f64> {
        let row = self.get(state)?;
        if !row.verified {
            return None;
        }
        row.facility_street_mph()
    }

    /// The number to drive by: the law where there is one, else the
    /// fallback. Never fails.
    pub fn facility_street_mph(&self, state: &str) -> f64 {
        self.statutory_mph(state).unwrap_or(FALLBACK_MPH)
    }

    /// True when the answer for `state` is the fallback rather than law.
    pub fn is_assumed(&self, state: &str) -> bool {
        self.statutory_mph(state).is_none()
    }

    pub fn len(&self) -> usize {
        self.rows.len()
    }

    pub fn is_empty(&self) -> bool {
        self.rows.is_empty()
    }

    pub fn contains(&self, state: &str) -> bool {
        self.rows.contains_key(state.trim())
    }

    /// The states in the table, in file order.
    pub fn states(&self) -> impl Iterator<Item = &str> {
        self.rows.keys().map(String::as_str)
    }
}

fn limit(
    value: Option<&Value>,
    path: &Path,
    state: &str,
    field: &str,
) -> Result<Option<f64>, DataError> {
    let Some(value) = value.filter(|v| !v.is_null()) else {
        return Ok(None);
    };
    let number = super::world_parsing::py_float(value)?;
    if !(MIN_PLAUSIBLE_MPH..=MAX_PLAUSIBLE_MPH).contains(&number) {
        return Err(DataError::value(format!(
            "{} {state} {field} is {}, outside the plausible street band {}-{}",
            path.display(),
            py_str_float(number),
            py_str_float(MIN_PLAUSIBLE_MPH),
            py_str_float(MAX_PLAUSIBLE_MPH)
        )));
    }
    Ok(Some(number))
}

#[derive(Deserialize, Default)]
struct RawRow {
    #[serde(default)]
    business_mph: Option<Value>,
    #[serde(default)]
    residence_mph: Option<Value>,
    #[serde(default)]
    urban_mph: Option<Value>,
    #[serde(default)]
    citation: String,
    #[serde(default)]
    title: String,
    #[serde(default)]
    url: String,
    #[serde(default)]
    rule_type: String,
    #[serde(default)]
    signs_required: bool,
    #[serde(default)]
    truck_note: String,
    #[serde(default)]
    verified: bool,
    #[serde(default)]
    notes: String,
    #[serde(default)]
    no_district_default: bool,
}

#[derive(Deserialize, Default)]
struct RawTable {
    #[serde(default)]
    limits: IndexMap<String, RawRow>,
    #[serde(default)]
    meta: serde_json::Map<String, Value>,
}

/// Validate and build the table from its parsed JSON.
pub fn parse_street_limits(raw: &Value, path: &Path) -> Result<StreetLimits, DataError> {
    if raw.get("limits").is_some_and(|l| !l.is_object()) {
        return Err(DataError::value(format!(
            "{} must contain a limits object",
            path.display()
        )));
    }
    let table: RawTable = serde_json::from_value(raw.clone())
        .map_err(|e| DataError::io(format!("{}: {e}", path.display())))?;
    let p = path.display();
    let mut rows: IndexMap<String, StatutoryLimit> = IndexMap::new();
    for (state, entry) in table.limits {
        let citation = entry.citation.trim().to_string();
        let url = entry.url.trim().to_string();
        let verified = entry.verified;
        // A verified row is a claim about the law, so it has to carry the
        // section that says so. Unverified rows are allowed to be thin --
        // that is what unverified MEANS -- but they may never be silent
        // about it, which is why `notes` is required there instead.
        if verified && citation.is_empty() {
            return Err(DataError::value(format!(
                "{p} {state} is verified with no citation"
            )));
        }
        if !verified && entry.notes.trim().is_empty() {
            return Err(DataError::value(format!(
                "{p} {state} is unverified without saying why"
            )));
        }
        let business = limit(entry.business_mph.as_ref(), path, &state, "business_mph")?;
        let residence = limit(entry.residence_mph.as_ref(), path, &state, "residence_mph")?;
        let urban = limit(entry.urban_mph.as_ref(), path, &state, "urban_mph")?;
        if business.is_none()
            && residence.is_none()
            && urban.is_none()
            && !entry.no_district_default
        {
            return Err(DataError::value(format!(
                "{p} {state} carries no district figure and does not declare \
                 no_district_default -- an empty row must say whether that is a \
                 finding or an omission"
            )));
        }
        let rule_type = entry.rule_type.trim().to_string();
        if !matches!(rule_type.as_str(), "absolute" | "prima facie" | "") {
            return Err(DataError::value(format!(
                "{p} {state} has unknown rule_type {}",
                super::world_parsing::py_repr_str(&rule_type)
            )));
        }
        let key = state.trim().to_string();
        rows.insert(
            key.clone(),
            StatutoryLimit {
                state: key,
                business_mph: business,
                residence_mph: residence,
                urban_mph: urban,
                citation,
                title: entry.title.trim().to_string(),
                url,
                rule_type,
                signs_required: entry.signs_required,
                truck_note: entry.truck_note.trim().to_string(),
                verified,
                notes: entry.notes.trim().to_string(),
                no_district_default: entry.no_district_default,
            },
        );
    }
    Ok(StreetLimits::new(rows, table.meta))
}

/// Read and parse a table from disk. Missing file reads as empty, so the
/// game still drives on the fallback rather than refusing to start.
pub fn load_street_limits_from(path: &Path) -> Result<StreetLimits, DataError> {
    let Some(text) = read_text_at(path) else {
        return Ok(StreetLimits::default());
    };
    let raw: Value = serde_json::from_str(&text)
        .map_err(|e| DataError::io(format!("{}: {e}", path.display())))?;
    parse_street_limits(&raw, path)
}

static CACHE: OnceCell<StreetLimits> = OnceCell::new();

/// The shipped table, read once per process. A table that fails to parse is
/// fatal, as the Python import-time exception was.
pub fn load_street_limits() -> &'static StreetLimits {
    CACHE.get_or_init(|| {
        load_street_limits_from(&street_limits_path()).expect("street_limits.json parses")
    })
}

/// Module-level convenience for the one caller that matters.
pub fn facility_street_mph(state: &str) -> f64 {
    load_street_limits().facility_street_mph(state)
}

#[cfg(test)]
mod tests {
    //! Port of `tests/test_street_limits.py`.
    use super::*;
    use serde_json::json;

    fn row() -> StatutoryLimit {
        StatutoryLimit {
            state: "Testland".into(),
            business_mph: Some(25.0),
            residence_mph: Some(25.0),
            urban_mph: None,
            citation: "Test Code Sec. 1".into(),
            title: "Speed limits in districts".into(),
            url: "https://example.gov/1".into(),
            rule_type: "absolute".into(),
            signs_required: false,
            truck_note: String::new(),
            verified: true,
            notes: String::new(),
            no_district_default: false,
        }
    }

    fn parse(raw: Value) -> Result<StreetLimits, DataError> {
        parse_street_limits(&raw, &street_limits_path())
    }

    fn shipped_states() -> Vec<String> {
        let text = read_text_at(&street_limits_path()).expect("street_limits.json");
        let raw: Value = serde_json::from_str(&text).unwrap();
        let mut states: Vec<String> = raw["limits"].as_object().unwrap().keys().cloned().collect();
        states.sort();
        states
    }

    #[test]
    fn test_the_facility_street_number_prefers_the_business_district() {
        // A warehouse stands in a business district, so that figure governs --
        // then a single urban-district figure, then residence as the last resort.
        assert_eq!(
            StatutoryLimit {
                business_mph: Some(30.0),
                residence_mph: Some(25.0),
                ..row()
            }
            .facility_street_mph(),
            Some(30.0)
        );
        assert_eq!(
            StatutoryLimit {
                business_mph: None,
                urban_mph: Some(20.0),
                residence_mph: Some(25.0),
                ..row()
            }
            .facility_street_mph(),
            Some(20.0)
        );
        assert_eq!(
            StatutoryLimit {
                business_mph: None,
                urban_mph: None,
                residence_mph: Some(25.0),
                ..row()
            }
            .facility_street_mph(),
            Some(25.0)
        );
        assert_eq!(
            StatutoryLimit {
                business_mph: None,
                urban_mph: None,
                residence_mph: None,
                ..row()
            }
            .facility_street_mph(),
            None
        );
    }

    #[test]
    fn test_an_uncovered_state_falls_back_and_says_so() {
        let table = load_street_limits();
        assert_eq!(table.facility_street_mph("Nowhere"), FALLBACK_MPH);
        assert!(table.is_assumed("Nowhere"));
        assert_eq!(table.facility_street_mph(""), FALLBACK_MPH);
    }

    #[test]
    fn test_a_verified_row_without_a_citation_is_refused() {
        // The point of the layer is the citation. A row claiming to be law with
        // nothing to check it against is worse than an honest blank.
        let raw =
            json!({"limits": {"Testland": {"business_mph": 25, "verified": true, "citation": ""}}});
        let err = parse(raw).unwrap_err();
        assert!(
            err.to_string().contains("verified with no citation"),
            "{err}"
        );
    }

    #[test]
    fn test_an_unverified_row_must_say_why() {
        let raw =
            json!({"limits": {"Testland": {"business_mph": 25, "verified": false, "notes": ""}}});
        let err = parse(raw).unwrap_err();
        assert!(
            err.to_string().contains("unverified without saying why"),
            "{err}"
        );
    }

    #[test]
    fn test_a_number_outside_the_street_band_is_refused() {
        // No state's code puts an ordinary street at 70. A row that says so is a
        // transcription error, and it must fail loudly rather than be driven.
        let raw = json!({"limits": {"Testland": {"business_mph": 70, "verified": true, "citation": "Test Code Sec. 1"}}});
        let err = parse(raw).unwrap_err();
        assert!(
            err.to_string()
                .contains("outside the plausible street band"),
            "{err}"
        );
    }

    #[test]
    fn test_every_shipped_row_is_plausible_and_carries_its_source() {
        let table = load_street_limits();
        if table.is_empty() {
            return; // the statutory table has not been baked yet
        }
        for state in shipped_states() {
            let row = table.get(&state).unwrap();
            for value in [row.business_mph, row.residence_mph, row.urban_mph]
                .into_iter()
                .flatten()
            {
                assert!(
                    (MIN_PLAUSIBLE_MPH..=MAX_PLAUSIBLE_MPH).contains(&value),
                    "{state}"
                );
            }
            if row.verified {
                assert!(!row.citation.is_empty(), "{state}");
                assert!(!row.url.is_empty(), "{state}");
                assert!(
                    matches!(row.rule_type.as_str(), "absolute" | "prima facie"),
                    "{state}"
                );
            } else {
                assert!(!row.notes.is_empty(), "{state}");
            }
        }
    }

    #[test]
    fn test_the_table_covers_every_state_the_map_delivers_to() {
        // A state on the map with no row is a facility approach still driving on
        // the old blanket 25. The gap is allowed -- it just has to be visible.
        let table = load_street_limits();
        if table.is_empty() {
            return;
        }
        let text =
            read_text_at(&data_path("facility_approaches.json")).expect("facility_approaches.json");
        let raw: Value = serde_json::from_str(text.trim_start_matches('\u{feff}')).unwrap();
        let mut on_the_map: std::collections::BTreeSet<String> = raw["approaches"]
            .as_object()
            .unwrap()
            .values()
            .map(|entry| {
                entry
                    .get("state")
                    .and_then(Value::as_str)
                    .unwrap_or("")
                    .trim()
                    .to_string()
            })
            .collect();
        on_the_map.remove("");
        let missing: Vec<&String> = on_the_map
            .iter()
            .filter(|state| !table.contains(state))
            .collect();
        assert!(
            missing.is_empty(),
            "facility states with no statutory row: {missing:?}"
        );
    }

    #[test]
    fn test_the_meta_says_how_much_of_the_layer_is_actually_law() {
        // A bake that mostly assumed has to say so loudly (CLAUDE.md). Here the
        // ratio that matters is how many rows are verified law.
        let table = load_street_limits();
        if table.is_empty() {
            return;
        }
        assert!(table.meta.contains_key("verified"));
        assert!(table.meta.contains_key("unverified"));
        let n = |key: &str| table.meta[key].as_i64().unwrap();
        assert_eq!(n("verified") + n("unverified"), n("states"));
    }

    #[test]
    fn test_a_state_with_no_district_default_is_a_finding_not_a_gap() {
        // Connecticut writes no district default at all: a limit exists there
        // only where a traffic authority has established and signed a zone, which
        // makes 55 the legally correct figure for an unposted street -- not a speed
        // to drive a yard approach at. The row has to be able to say "checked,
        // there is none" so it reads differently from a row nobody filled in.
        let raw = json!({"limits": {"Testland": {
            "business_mph": null, "residence_mph": null, "urban_mph": null,
            "no_district_default": true, "citation": "Test Code Sec. 1",
            "rule_type": "absolute", "verified": true,
        }}});
        let table = parse(raw).unwrap();
        assert!(table.get("Testland").unwrap().no_district_default);
        // And it drives on the fallback rather than on the statutory ceiling.
        assert_eq!(table.facility_street_mph("Testland"), FALLBACK_MPH);
        assert!(table.is_assumed("Testland"));
    }

    #[test]
    fn test_an_empty_row_that_does_not_declare_itself_is_refused() {
        let raw =
            json!({"limits": {"Testland": {"verified": true, "citation": "Test Code Sec. 1"}}});
        let err = parse(raw).unwrap_err();
        assert!(err.to_string().contains("no_district_default"), "{err}");
    }

    #[test]
    fn test_a_limit_that_only_applies_when_posted_is_not_used_for_an_unposted_street() {
        // Pennsylvania writes a 35 mph urban district figure and then makes it
        // ineffective without signs at both ends of the zone and every half mile.
        // On the streets this table is for -- the ones with no sign at all -- that
        // 35 is not the law, so it must not be posted. The statute is real; its
        // application to an unsigned street is not.
        let pa = StatutoryLimit {
            business_mph: None,
            urban_mph: Some(35.0),
            residence_mph: Some(25.0),
            signs_required: true,
            ..row()
        };
        assert_eq!(pa.facility_street_mph(), None);
        let raw = json!({"limits": {"Testland": {
            "urban_mph": 35, "residence_mph": 25, "signs_required": true,
            "citation": "Test Code Sec. 1", "rule_type": "absolute", "verified": true,
        }}});
        let table = parse(raw).unwrap();
        assert_eq!(table.facility_street_mph("Testland"), FALLBACK_MPH);
        assert!(table.is_assumed("Testland"));
    }

    #[test]
    fn test_an_unverified_row_is_not_driven_on() {
        // A state nobody could confirm falls back, and every view of the table
        // agrees that it did. These three answers drifted apart once already: the
        // number accessor handed back an unconfirmed figure while is_assumed called
        // the same state assumed.
        let raw = json!({"limits": {"Testland": {
            "business_mph": 30, "verified": false, "rule_type": "absolute",
            "notes": "official code not fetchable; read from a secondary source",
        }}});
        let table = parse(raw).unwrap();
        assert_eq!(table.statutory_mph("Testland"), None);
        assert_eq!(table.facility_street_mph("Testland"), FALLBACK_MPH);
        assert!(table.is_assumed("Testland"));
    }
}
