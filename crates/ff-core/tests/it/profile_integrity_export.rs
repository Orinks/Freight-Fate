//! Cross-language parity for the file the orinks.net validator is built from.
//!
//! `profile_integrity_invariants.json` beside this test is the output of the
//! reference implementation, `tools/export_profile_integrity_invariants.py`,
//! stored with LF endings (the Python exporter writes CRLF when it runs on
//! Windows; the JSON is the same either way, and the Rust exporter always
//! writes LF so the artifact does not depend on who produced it).
//!
//! This surface decides whether a submitted career is arithmetically
//! possible. An export that drifts from what the game awards makes the
//! validator either reject honest players or accept impossible careers, so
//! the bytes are pinned rather than the shape: any change at all has to be a
//! change someone chose.
//!
//! When this test fails, that is the finding. Re-run one of
//!
//! ```text
//! uv run python tools/export_profile_integrity_invariants.py \
//!     crates/ff-core/tests/profile_integrity_invariants.json
//! cargo run -p ff-core --bin ff-invariants -- \
//!     crates/ff-core/tests/profile_integrity_invariants.json
//! ```
//!
//! and read the diff before committing it: a moved catalog key means
//! orinks.net needs the fresh export before the next build reaches players.

use std::path::{Path, PathBuf};
use std::process::Command;

use ff_core::profile_integrity_invariants::{
    current_rendered_invariants, invariant_data, CatalogInputs,
};
use serde_json::Value;

/// The Python exporter's output, committed beside this file.
const PYTHON_EXPORT: &str = include_str!("../profile_integrity_invariants.json");

/// `include_str!` keeps whatever the checkout has; a repo cloned with
/// `core.autocrlf=true` hands back CRLF for a file stored as LF.
fn fixture() -> String {
    PYTHON_EXPORT.replace("\r\n", "\n")
}

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("the repo root is two levels above crates/ff-core")
}

/// The whole point of the port: the Rust rendering is the Python rendering.
#[test]
fn the_rust_export_is_byte_for_byte_the_python_export() {
    let rust = current_rendered_invariants().expect("the shipped catalogs render");
    let python = fixture();
    if rust == python {
        return;
    }
    // Name the key that moved rather than dumping 37 kB of JSON at the
    // reader: a catalog key is a balance pass the validator has not heard
    // about, `cityLabels` alone is a world-data edit.
    let left: Value = serde_json::from_str(&python).expect("the fixture is JSON");
    let right: Value = serde_json::from_str(&rust).expect("the rendering is JSON");
    let (left, right) = (
        left.as_object().expect("an object"),
        right.as_object().expect("an object"),
    );
    let mut moved: Vec<&str> = left
        .keys()
        .chain(right.keys())
        .filter(|key| left.get(*key) != right.get(*key))
        .map(String::as_str)
        .collect();
    moved.sort_unstable();
    moved.dedup();
    assert!(
        moved.is_empty(),
        "the Rust export differs from the Python export under {moved:?} -- \
         see the header of this file before re-generating the fixture"
    );
    // Same values, different bytes: a rendering difference (float repr,
    // escaping, indent), which is the harder kind of drift to spot.
    assert_eq!(
        rust, python,
        "the Rust and Python exports hold the same values but render \
         different bytes"
    );
}

/// The catalogs the export names are the ones the export was built from.
///
/// Cheap insurance that the fixture was not generated from a stale checkout:
/// the figures the validator does arithmetic with are re-derived here.
#[test]
fn the_fixture_carries_the_live_catalog_figures() {
    let fixture: Value = serde_json::from_str(&fixture()).expect("the fixture is JSON");
    let live = ff_core::profile_integrity_invariants::current_invariant_data()
        .expect("the shipped catalogs render");
    for key in [
        "startingMoney",
        "startingMoneyMax",
        "payAdvanceLimit",
        "xpPerMileMax",
        "xpFlatPerDelivery",
        "levelXp",
        "profileFields",
        "careerFields",
        "truckConditionFields",
        "sourceSaveVersion",
        "achievementIds",
        "achievementLabels",
        "careerTitles",
        "carrierLabels",
        "trailerCatalog",
        "truckPrices",
        "upgradePrices",
        "endorsements",
        "fleetTiers",
        "marketCargoKeys",
    ] {
        assert_eq!(fixture[key], live[key], "{key} moved");
    }
}

#[test]
fn the_public_profile_catalogs_are_derived_from_live_game_catalogs() {
    use ff_core::achievements::ACHIEVEMENTS;
    use ff_core::models::career_ladder::CAREER_RANKS;
    use ff_core::models::start_options::all_start_options;
    use ff_core::models::trailers::TRAILER_CATALOG;

    let exported = ff_core::profile_integrity_invariants::current_invariant_data()
        .expect("the shipped catalogs render");

    let titles: Vec<&str> = CAREER_RANKS.iter().map(|rank| rank.title).collect();
    assert_eq!(exported["careerTitles"], serde_json::json!(titles));

    for option in all_start_options() {
        assert_eq!(
            exported["carrierLabels"][option.key], option.carrier_name,
            "{} carrier label moved",
            option.key
        );
    }
    for trailer in TRAILER_CATALOG {
        assert_eq!(
            exported["trailerCatalog"][trailer.key]["label"],
            trailer.label
        );
        assert_eq!(
            exported["trailerCatalog"][trailer.key]["purchasePrice"],
            trailer.purchase_price
        );
    }
    for achievement in ACHIEVEMENTS {
        assert_eq!(
            exported["achievementLabels"][achievement.id], achievement.name,
            "{} achievement label moved",
            achievement.id
        );
    }
}

/// The shipped code path, end to end: the binary writes the file, and its
/// `--check` form passes on it and fails on drift.
#[test]
fn ff_invariants_writes_and_checks_the_export() {
    let dir = tempfile::tempdir().expect("a temp dir");
    let out = dir.path().join("profile_integrity_invariants.json");
    let data_dir = repo_root().join("src/freight_fate/data");

    let exporter = || {
        let mut command = Command::new(env!("CARGO_BIN_EXE_ff-invariants"));
        command
            .arg(&out)
            .arg("--data-dir")
            .arg(&data_dir)
            .arg("--quiet");
        command
    };

    let wrote = exporter().status().expect("ff-invariants runs");
    assert!(wrote.success(), "ff-invariants failed to write the export");
    assert_eq!(
        std::fs::read_to_string(&out).expect("the export was written"),
        fixture(),
        "ff-invariants wrote something other than the Python export"
    );

    let checked = exporter()
        .arg("--check")
        .status()
        .expect("ff-invariants runs");
    assert!(checked.success(), "--check called a fresh export stale");

    // A file the Python exporter wrote on Windows: same JSON, CRLF endings.
    // --check is looking for a catalog that moved, not for line endings.
    std::fs::write(&out, fixture().replace('\n', "\r\n")).expect("rewrite the export");
    let crlf = exporter()
        .arg("--check")
        .status()
        .expect("ff-invariants runs");
    assert!(
        crlf.success(),
        "--check called a CRLF copy of the same export stale"
    );

    // One moved figure is drift, and --check has to catch it.
    let drifted = fixture().replace("\"startingMoney\": 5000", "\"startingMoney\": 5001");
    assert_ne!(drifted, fixture(), "the drift edit found nothing to change");
    std::fs::write(&out, &drifted).expect("rewrite the export");
    let stale = exporter()
        .arg("--check")
        .status()
        .expect("ff-invariants runs");
    assert!(
        !stale.success(),
        "--check passed an export with drifted money"
    );
}

/// A hand-assembled `CatalogInputs` renders something the validator must
/// never be built from -- which is why the exporter only uses `current()`.
///
/// Not a style point: the audit that found this gap found four tests passing
/// against fixture numbers, two of them a false green. The fixture and the
/// live catalogs have to be visibly different things.
#[test]
fn a_fixture_input_is_not_the_live_export() {
    let live = CatalogInputs::current();
    let mut fixture_inputs = live.clone();
    fixture_inputs.starting_money_max = 5_000.0;
    let root = ff_core::profile_integrity_invariants::world_data_root();
    assert_ne!(
        invariant_data(&root, &fixture_inputs).unwrap(),
        invariant_data(&root, &live).unwrap()
    );
}
