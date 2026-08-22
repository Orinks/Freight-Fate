//! Region taxonomy: derivation, coverage, and stored-equals-derived guard
//! (the world-backed and cross-module half of `tests/test_regions.py`; the
//! classifier cases live inline in `regions.rs`).

mod data_support;

use data_support::world;
use ff_core::data::regions::{classify_region, REGIONS};

#[test]
fn test_stored_region_matches_derived() {
    // Every city's baked region must equal classify_region for its coords.
    //
    // This is the guard that keeps a misclassification (such as Reno being tagged
    // the Rockies) from ever recurring as the map grows.
    let world = world();
    let mut mismatches = Vec::new();
    for (name, city) in &world.cities {
        let derived = classify_region(&city.state_code, city.lat, city.lon).unwrap();
        if city.region != derived {
            mismatches.push(format!(
                "{name}: stored {:?} != derived {derived:?}",
                city.region
            ));
        }
    }
    assert!(
        mismatches.is_empty(),
        "Stored regions out of sync with classifier:\n{}",
        mismatches.join("\n")
    );
}

#[test]
fn test_every_stored_region_is_canonical() {
    for (name, city) in &world().cities {
        assert!(
            REGIONS.contains(&city.region.as_str()),
            "{name} has non-canonical region {:?}",
            city.region
        );
    }
}

#[test]
fn test_reno_is_great_basin_not_rockies() {
    // The bug this work fixed: Reno is Great Basin / eastern Sierra, not Rockies.
    let world = world();
    assert_eq!(world.cities["reno_nv_us"].region, "great_basin");
    assert_eq!(world.cities["boise_id_us"].region, "great_basin");
}

#[test]
#[ignore = "needs sim::weather::REGION_WEIGHTS and models::economy::REGION_FUEL_PRICE"]
fn test_every_region_covered_in_flavor_tables() {
    // The REGION_MARKET_TAGS and REGION_LABELS halves are live in regions.rs;
    // the weather-weight and fuel-price tables belong to other modules.
}

#[test]
fn test_every_region_has_local_hazard_flavor() {
    // Every canonical region is named by at least one region-specific hazard,
    // so no region falls back to only the nationwide staples.
    use ff_core::sim::trip_models::HAZARDS;

    let tagged: std::collections::HashSet<&str> = HAZARDS
        .iter()
        .filter_map(|hazard| hazard.regions)
        .flat_map(|regions| regions.iter().copied())
        .collect();
    let missing: Vec<&str> = REGIONS
        .iter()
        .copied()
        .filter(|region| !tagged.contains(region))
        .collect();
    assert!(
        missing.is_empty(),
        "regions with no local hazard flavor: {missing:?}"
    );
}

#[test]
fn test_hazard_region_tags_are_canonical() {
    use ff_core::sim::trip_models::HAZARDS;

    for hazard in HAZARDS {
        for region in hazard.regions.unwrap_or(&[]) {
            assert!(
                REGIONS.contains(region),
                "{:?} tags unknown region {region:?}",
                hazard.text
            );
        }
    }
}
