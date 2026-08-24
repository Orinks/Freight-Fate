//! City slug keys, the composed spoken layer, and legacy-save aliases (port
//! of `tests/test_city_keys.py`).
//!
//! The slug migration separated city identity (`jackson_ms_us`) from speech
//! ("Jackson" / "Jackson, Mississippi"). These tests pin the three contracts
//! it introduced: keys are well-formed and unique, spoken names compose from
//! the geo lookup and never leak a slug, and everything a pre-slug save
//! persisted (bare city names, "City, State" names, facility ids) still
//! resolves.


use crate::data_support::world;
use ff_core::data::legacy_aliases::LEGACY_CITY_SLUGS;
use regex::Regex;

#[test]
fn test_every_city_key_is_a_well_formed_slug() {
    let world = world();
    let slug_pattern = Regex::new(r"^[a-z0-9_]+_[a-z]{2}_[a-z]{2}$").unwrap();
    for (key, city) in &world.cities {
        assert!(slug_pattern.is_match(key), "malformed city key {key:?}");
        assert_eq!(&city.key, key);
        assert!(key.ends_with(&format!(
            "_{}_{}",
            city.state_code.to_lowercase(),
            city.country.to_lowercase()
        )));
    }
}

#[test]
fn test_spoken_layer_composes_from_geo_codes() {
    let world = world();
    let jackson = &world.cities["jackson_ms_us"];
    assert_eq!(jackson.name, "Jackson");
    assert_eq!(jackson.state, "Mississippi");
    assert_eq!(jackson.state_code, "MS");
    assert_eq!(jackson.country, "US");
    assert_eq!(jackson.country_name, "United States");
    assert_eq!(jackson.spoken_qualified(), "Jackson, Mississippi");
}

#[test]
fn test_spoken_city_never_speaks_a_slug() {
    let world = world();
    for key in world.cities.keys() {
        let spoken = world.spoken_city(key, None);
        assert_ne!(&spoken, key);
        assert!(!spoken.contains('_'));
    }
}

#[test]
fn test_ambiguous_spoken_names_auto_qualify() {
    let world = world();
    // Two Jacksons share a bare spoken name, so both qualify by default.
    assert_eq!(
        world.spoken_city("jackson_ms_us", None),
        "Jackson, Mississippi"
    );
    assert_eq!(
        world.spoken_city("jackson_mi_us", None),
        "Jackson, Michigan"
    );
    // A unique name stays bare unless qualification is asked for.
    assert_eq!(world.spoken_city("chicago_il_us", None), "Chicago");
    assert_eq!(
        world.spoken_city("chicago_il_us", Some(true)),
        "Chicago, Illinois"
    );
    assert_eq!(world.spoken_city("jackson_ms_us", Some(false)), "Jackson");
}

#[test]
fn test_spoken_city_passes_legacy_and_unknown_text_through() {
    let world = world();
    // A legacy display name resolves to its city's spoken form.
    assert_eq!(world.spoken_city("Chicago", None), "Chicago");
    assert_eq!(
        world.spoken_city("Jackson, Michigan", None),
        "Jackson, Michigan"
    );
    // Unknown text comes back unchanged -- it is already the best speakable form.
    assert_eq!(world.spoken_city("Atlantis", None), "Atlantis");
}

#[test]
fn test_every_legacy_name_resolves_to_a_live_city() {
    let world = world();
    for (old_name, slug) in LEGACY_CITY_SLUGS {
        assert!(
            world.cities.contains_key(*slug),
            "{old_name:?} aliases missing city {slug:?}"
        );
        assert_eq!(world.resolve_city_key(old_name), *slug);
    }
}

#[test]
fn test_frozen_legacy_map_wins_name_collisions() {
    // Bare "Jackson" belonged to Jackson MS before Jackson MI joined the map;
    // old saves that say "Jackson" must keep meaning Mississippi forever.
    assert_eq!(world().resolve_city_key("Jackson"), "jackson_ms_us");
}

#[test]
fn test_qualified_city_state_forms_resolve() {
    let world = world();
    assert_eq!(
        world.resolve_city_key("Jackson, Mississippi"),
        "jackson_ms_us"
    );
    assert_eq!(world.resolve_city_key("Jackson, MS"), "jackson_ms_us");
    assert_eq!(
        world.resolve_city_key("Springfield, Illinois"),
        "springfield_il_us"
    );
}

#[test]
fn test_legacy_facility_ids_still_resolve() {
    // Pre-slug facility ids embedded a slug of the display name
    // ("chicago:cross_dock:..."). Every location must stay reachable through
    // its old id, including template facilities of comma-disambiguated cities
    // whose names embedded the old display name too.
    let world = world();
    let chicago = &world.cities["chicago_il_us"];
    for location in &chicago.locations {
        let old_id = format!("chicago:{}", location.id.split_once(':').unwrap().1);
        assert_eq!(world.facility_by_id(&old_id).unwrap().id, location.id);
        assert_eq!(
            world.facility_location("Chicago", &old_id).unwrap().id,
            location.id
        );
    }

    let jackson_mi = &world.cities["jackson_mi_us"];
    let template = jackson_mi
        .locations
        .iter()
        .find(|loc| loc.template)
        .unwrap();
    let old_name = template.name.replace("Jackson", "Jackson, Michigan");
    let old_suffix: Vec<&str> = template.id.splitn(3, ':').collect();
    let old_id = format!(
        "jackson-michigan:{}:{}",
        old_suffix[1],
        legacy_slug(&old_name)
    );
    assert_eq!(world.facility_by_id(&old_id).unwrap().id, template.id);
    assert_eq!(
        world
            .facility_location("Jackson, Michigan", &old_name)
            .unwrap()
            .id,
        template.id
    );
}

#[test]
fn test_legacy_market_names_fall_back_to_default_facility() {
    // Old jobs that only named the whole-city market keep resolving, under
    // both the current spoken name and the pre-slug display name.
    let world = world();
    let default = world.default_facility("jackson_mi_us").unwrap();
    assert_eq!(
        world
            .facility_location("jackson_mi_us", "Jackson freight market")
            .unwrap()
            .id,
        default.id
    );
    assert_eq!(
        world
            .facility_location("Jackson, Michigan", "Jackson, Michigan freight market")
            .unwrap()
            .id,
        default.id
    );
}

#[test]
fn test_geo_lookup_covers_every_state_code_in_use() {
    let world = world();
    for city in world.cities.values() {
        assert!(
            !city.state_code.is_empty(),
            "{} has no state code",
            city.key
        );
        assert!(
            !city.state.is_empty() && city.state != city.state_code,
            "{} state code {:?} did not resolve to a spoken name",
            city.key,
            city.state_code
        );
    }
}

/// The pre-slug facility-id slug: lowercase, non-alphanumerics to dashes.
fn legacy_slug(text: &str) -> String {
    let mut out = String::new();
    let mut pending = false;
    for ch in text.to_lowercase().chars() {
        if ch.is_alphanumeric() {
            if pending && !out.is_empty() {
                out.push('-');
            }
            out.push(ch);
            pending = false;
        } else {
            pending = true;
        }
    }
    out.trim_matches('-').to_string()
}
