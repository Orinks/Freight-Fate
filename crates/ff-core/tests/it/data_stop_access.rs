//! Which stops a rig with a trailer can use, as the world data now reads
//! them: a convenience station the map typed as a travel center with only
//! assumed truck parking is bobtail-only, a truck-stop chain or a stop with
//! confirmed parking is not (`world_constants::screened_vehicle_access`).

use ff_core::data::world::get_world;

#[test]
fn test_convenience_stations_typed_as_travel_centers_hide_behind_a_trailer() {
    let world = get_world();
    let mut screened = 0usize;
    let mut kept_chain = 0usize;
    let mut quiktrip_hidden = 0usize;
    let mut quiktrip_total = 0usize;
    for leg in &world.legs {
        for stop in &leg.stops {
            let recorded = stop.vehicle_access.as_str();
            let effective = stop.effective_vehicle_access();
            if recorded == "tractor_trailer" && effective == "bobtail_only" {
                screened += 1;
                // A screened stop is exactly one a trailer cannot use and a
                // bobtail still can.
                assert!(!stop.accessible_to(false), "{}", stop.name);
                assert!(stop.accessible_to(true), "{}", stop.name);
                // Never a stop with confirmed parking, surveyed spaces, or a
                // truck facility in its services.
                assert_ne!(stop.parking, "confirmed", "{}", stop.name);
                assert_eq!(stop.parking_spaces, 0, "{}", stop.name);
                assert!(
                    !stop.services.iter().any(|s| s == "scale" || s == "showers"),
                    "{}",
                    stop.name
                );
            }
            let lower = stop.name.to_lowercase();
            if lower.starts_with("love's") || lower.starts_with("pilot") {
                assert_eq!(effective, recorded, "{}", stop.name);
                kept_chain += 1;
            }
            if lower.starts_with("quiktrip") {
                quiktrip_total += 1;
                if stop.accessible_to(false) {
                    // The only QuikTrip a trailer may still use is one whose
                    // own record vouches for trucks.
                    let evidence = stop.parking == "confirmed"
                        || stop.parking_spaces > 0
                        || stop.services.iter().any(|s| s == "scale" || s == "showers")
                        || lower.contains("truck")
                        || lower.contains("travel")
                        || recorded != "tractor_trailer";
                    assert!(evidence, "{} {:?} {}", stop.name, stop.parking, recorded);
                } else {
                    quiktrip_hidden += 1;
                }
            }
        }
    }
    // The survey that motivated the screen (2026-09-12): a good hundred
    // convenience stations typed as travel centers or service plazas, none
    // of them a truck-stop chain.
    assert!(screened >= 100, "{screened} screened");
    assert!(
        screened <= 400,
        "{screened} screened, more than the survey found"
    );
    assert!(kept_chain > 500, "{kept_chain} chain stops kept");
    assert!(quiktrip_total > 0);
    assert!(
        quiktrip_hidden * 10 >= quiktrip_total * 9,
        "{quiktrip_hidden} of {quiktrip_total} QuikTrips hide behind a trailer"
    );
}

// -- one truck stop, listed once (`data::stop_twins`) ---------------------------------

#[test]
fn test_the_corfu_flying_j_is_one_stop_in_both_directions() {
    // The pair the adversarial battery rolled through, 2026-09-17: the map
    // import's bare "Flying J Travel Center" 2.8 miles short of the locator's
    // "Flying J Travel Center Corfu" at exit 48A, on all three Thruway legs.
    let world = get_world();
    let mut legs_checked = 0usize;
    for leg in &world.legs {
        let flying_js: Vec<&str> = leg
            .stops
            .iter()
            .filter(|stop| stop.name.starts_with("Flying J"))
            .filter(|stop| stop.name.ends_with("Corfu") || stop.name == "Flying J Travel Center")
            .map(|stop| stop.name.as_str())
            .collect();
        if flying_js.iter().any(|name| name.ends_with("Corfu")) {
            legs_checked += 1;
            assert_eq!(
                flying_js,
                ["Flying J Travel Center Corfu"],
                "{} to {}",
                leg.a,
                leg.b
            );
        }
    }
    assert!(
        legs_checked >= 3,
        "the Thruway legs carry it: {legs_checked}"
    );
}

#[test]
fn test_no_leg_lists_a_bare_chain_record_beside_the_named_one() {
    use ff_core::data::stop_twins::TWIN_STOP_MILES;
    let world = get_world();
    let bare = |name: &str| {
        matches!(
            name,
            "Flying J Travel Center" | "Pilot Travel Center" | "Love's Travel Stop" | "Love's"
        )
    };
    let chain = |name: &str| name.split(' ').next().unwrap_or_default().to_lowercase();
    for leg in &world.legs {
        for a in leg.stops.iter().filter(|stop| bare(&stop.name)) {
            for b in leg.stops.iter().filter(|stop| !bare(&stop.name)) {
                let twin = chain(&a.name) == chain(&b.name)
                    && (a.at_mi - b.at_mi).abs() <= TWIN_STOP_MILES
                    && (a.directions.iter().any(|d| d == "both")
                        || b.directions.iter().any(|d| d == "both"));
                assert!(
                    !twin,
                    "{} to {}: {} at {} beside {} at {}",
                    leg.a, leg.b, a.name, a.at_mi, b.name, b.at_mi
                );
            }
        }
    }
}

// -- a chain truck stop is a travel center (`data::branded_plazas`) -------------------

#[test]
fn test_no_chain_truck_stop_announces_as_a_service_plaza() {
    use ff_core::data::world_constants::TRUCK_STOP_CHAINS;
    let world = get_world();
    let chain_named = |name: &str| {
        let lower = name.trim().to_lowercase();
        TRUCK_STOP_CHAINS
            .iter()
            .any(|chain| lower.starts_with(chain) || lower == chain.trim())
    };
    let mut chain_travel_centers = 0usize;
    let mut plazas_by_name = 0usize;
    for leg in &world.legs {
        for stop in &leg.stops {
            let lower = stop.name.to_lowercase();
            let names_a_plaza = lower.contains("service plaza") || lower.contains("service area");
            if names_a_plaza && stop.stop_type == "service_plaza" {
                plazas_by_name += 1;
            }
            if !chain_named(&stop.name) {
                continue;
            }
            if stop.stop_type == "travel_center" {
                chain_travel_centers += 1;
            }
            assert!(
                stop.stop_type != "service_plaza" || names_a_plaza,
                "{} to {}: {} at {} is typed {}",
                leg.a,
                leg.b,
                stop.name,
                stop.at_mi,
                stop.stop_type
            );
            assert!(
                !stop.spoken_name().starts_with("service plaza: ") || names_a_plaza,
                "{}",
                stop.spoken_name()
            );
        }
    }
    // Measured 2026-09-17: 1,317 chain records retyped on top of the 802 the
    // map already typed as travel centers, and the 99 toll-road plazas that
    // name themselves left as they were.
    assert!(
        chain_travel_centers >= 2_000,
        "{chain_travel_centers} chain travel centers"
    );
    assert!(
        plazas_by_name >= 90,
        "{plazas_by_name} named service plazas"
    );
}

#[test]
fn test_a_retyped_chain_stop_keeps_everything_but_its_label() {
    // The bare "Love's Travel Stop" records are the map import's: 444 of them
    // recorded as service plazas, with assumed parking and the default actions.
    let world = get_world();
    let stop = world
        .legs
        .iter()
        .flat_map(|leg| leg.stops.iter())
        .find(|stop| stop.name == "Love's Travel Stop")
        .expect("the map has a bare Love's record");
    assert_eq!(stop.stop_type, "travel_center");
    assert_eq!(stop.spoken_name(), "travel center: Love's Travel Stop");
    assert!(stop.accessible_to(false));
    for action in ["park", "fuel", "sleep"] {
        assert!(stop.actions.iter().any(|a| a == action), "{action}");
    }
}
