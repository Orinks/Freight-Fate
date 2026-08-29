//! A billboard that names a place must only be read near that place.
//!
//! Billboards are one of the few things that tell a driver who cannot see the
//! road WHERE they are. A sign naming Oklahoma City while the truck is in
//! Tennessee is not flavour gone wrong -- it is the game asserting something
//! false about the player's position, in the channel they are using to build a
//! mental map. So this file is a sweep, not a spot check: it drives seeded
//! deliveries down every mapped corridor, collects every billboard the trip
//! schedules together with the state the truck is in at that milepost, and
//! fails on any sign whose place claim is untrue there.
//!
//! THE ORACLE IS INDEPENDENT OF THE PLACEMENT CODE. `PLACE_CLAIMS` below is
//! written from real United States geography -- where the named town, region,
//! road or attraction actually is, plus the neighbouring states a driver could
//! honestly be in while approaching it. It never consults the anchor table the
//! runtime uses, so a placement bug cannot make its own test pass.

use std::collections::{HashMap, HashSet};

use ff_core::sim::trip::TripOptions;

use crate::sim_support::{make_trip_with, world};

/// A place a sign names, and every state in which that claim is honest.
///
/// The allowance is deliberately generous -- a real billboard is read on the
/// approach, so the state before the line counts too. What it must never
/// contain is a state the sign's subject is nowhere near, which is exactly the
/// failure being tested. Sources are ordinary United States road geography:
/// the town's own state, plus the states the corridor enters it from.
const PLACE_CLAIMS: &[(&str, &[&str])] = &[
    // -- Interstate 90 -----------------------------------------------------
    // Wall, South Dakota. Minnesota is the I-90 approach from the east;
    // Wyoming is the neighbouring approach from the west. Montana is too
    // far west -- a tester hit there is a fail. Placement itself keeps the
    // boards on SD and MN only.
    ("Wall Drug", &["SD", "MN"]),
    ("Boston ahead", &["MA", "NY", "CT", "RI", "NH"]),
    ("Wyoming, Land of the Buffalo", &["WY", "MT", "SD"]),
    ("Idaho panhandle", &["ID", "WA", "MT"]),
    // -- Interstate 95 -----------------------------------------------------
    ("sombrero tower", &["SC", "NC"]),
    ("South of the Border", &["SC", "NC"]),
    ("New Jersey: more state", &["NJ", "NY", "PA", "DE"]),
    ("Jacksonville ahead", &["FL", "GA"]),
    // -- Interstate 10 -----------------------------------------------------
    ("The Thing?", &["AZ", "NM"]),
    ("Dinosaurs, next exit", &["CA"]),
    ("Phoenix ahead", &["AZ", "NM", "CA"]),
    ("Houston ahead", &["TX", "LA"]),
    ("Baton Rouge ahead", &["LA", "MS", "TX"]),
    ("Biloxi", &["MS", "LA", "AL"]),
    ("El Paso, out past the haze", &["TX", "NM"]),
    ("Big Thicket", &["TX", "LA"]),
    // -- Interstate 15 -----------------------------------------------------
    ("Alien jerky", &["CA", "NV"]),
    ("The Mad Greek", &["CA", "NV"]),
    ("Las Vegas ahead", &["NV", "AZ", "UT", "CA"]),
    // -- Interstate 40 -----------------------------------------------------
    (
        "Route sixty-six",
        &["CA", "AZ", "NM", "TX", "OK", "MO", "KS", "IL"],
    ),
    (
        "Route Sixty-Six",
        &["CA", "AZ", "NM", "TX", "OK", "MO", "KS", "IL"],
    ),
    // Meramec Caverns is Stanton, Missouri, on Interstate 44. Arkansas,
    // Tennessee, and Kentucky were the I-40 misplacement.
    ("caverns ahead", &["MO"]),
    ("Winslow, Arizona", &["AZ", "NM", "CA"]),
    ("Memphis, on down the road", &["TN", "AR", "MS"]),
    ("Muskogee, Oklahoma", &["OK", "AR"]),
    ("Okemah, Oklahoma", &["OK"]),
    ("East Tennessee", &["TN", "NC", "VA"]),
    // -- Interstate 80 -----------------------------------------------------
    ("largest porch swing", &["NE", "KS", "IA"]),
    ("Little America", &["WY", "UT", "NE"]),
    // Otis Redding's dock is the San Francisco bay, not the Humboldt.
    ("Dock of the Bay", &["CA"]),
    // -- Interstate 70 -----------------------------------------------------
    ("The Rockies, straight ahead", &["CO", "KS", "UT"]),
    ("Kansas City ahead", &["MO", "KS", "IL"]),
    // -- Interstate 44 -----------------------------------------------------
    ("Franklin County, Missouri", &["MO"]),
    ("Tulsa ahead", &["OK", "MO", "TX", "KS"]),
    // -- Interstate 35 -----------------------------------------------------
    ("Abbott, Texas", &["TX"]),
    ("Waco ahead", &["TX"]),
    ("Austin ahead", &["TX"]),
    ("San Antonio, down the road", &["TX"]),
    ("Flattest stretch in Kansas", &["KS", "OK", "MO", "NE"]),
    // -- Interstate 5 ------------------------------------------------------
    ("Bakersfield Sound", &["CA"]),
    ("The Grapevine", &["CA"]),
    ("Redwood country", &["CA", "OR"]),
    // -- Interstate 55 -----------------------------------------------------
    ("Arkansas Delta", &["AR", "TN", "MO", "MS"]),
    ("old rail line to New Orleans", &["LA", "MS", "TN", "AR"]),
    // -- Interstate 65 -----------------------------------------------------
    (
        "Hank Williams's home state",
        &["AL", "TN", "MS", "GA", "FL"],
    ),
    ("Birmingham by eight thirty", &["AL", "TN", "MS", "GA"]),
    ("Nashville ahead", &["TN", "KY", "AL"]),
    // -- Interstate 59 -----------------------------------------------------
    ("Fort Payne, Alabama", &["AL", "GA", "TN", "MS"]),
    // -- Interstate 75 -----------------------------------------------------
    ("Detroit City ahead", &["MI", "OH", "IN"]),
    ("Saginaw, Michigan", &["MI"]),
    ("Macon, Georgia", &["GA", "FL", "TN"]),
    // -- Interstate 85 -----------------------------------------------------
    ("Atlanta ahead", &["GA", "TN", "AL", "SC", "NC"]),
    ("Newnan, Georgia", &["GA", "AL"]),
    // -- Interstate 24 -----------------------------------------------------
    ("Chattanooga ahead", &["TN", "GA", "AL", "KY"]),
    // -- Interstate 94 -----------------------------------------------------
    ("Wisconsin made Dave Dudley", &["WI", "MN", "IL", "MI"]),
    ("Motown assembly line", &["MI", "OH", "IN"]),
    ("it built Bob Seger", &["MI", "OH", "IN"]),
    // -- Interstate 77 -----------------------------------------------------
    ("Charleston, West Virginia", &["WV", "VA", "OH", "KY"]),
    ("Kathy Mattea", &["WV", "VA", "OH", "KY"]),
    // -- Interstate 81 -----------------------------------------------------
    ("Foggy Mountain Breakdown", &["VA", "TN", "WV", "NC", "KY"]),
    // -- Interstate 64 -----------------------------------------------------
    ("Eastern Kentucky", &["KY", "WV", "VA", "OH"]),
    ("Sixteen Tons", &["KY", "WV", "VA", "OH", "PA"]),
    // -- Interstate 30 -----------------------------------------------------
    ("Hope, Arkansas", &["AR", "TX"]),
    // -- Interstate 78 -----------------------------------------------------
    ("Nazareth, Pennsylvania", &["PA", "NJ", "NY"]),
    // -- Interstate 20 -----------------------------------------------------
    ("West Texas cotton flats", &["TX", "NM"]),
    ("Lubbock, Texas", &["TX", "NM", "OK"]),
    ("Abilene ahead", &["TX"]),
    // -- the Appalachian hollows -------------------------------------------
    (
        "called hollers",
        &["WV", "VA", "KY", "TN", "NC", "PA", "OH", "MD", "GA", "AL"],
    ),
];

/// Seeded deliveries covering every mapped corridor, both directions of the
/// country and every region. Unroutable pairs are skipped, but the sweep
/// asserts a floor on how many trips actually built, so a routing change that
/// quietly empties the sweep fails instead of passing vacuously.
const SWEEP_RUNS: &[(&str, &str)] = &[
    ("seattle_wa_us", "boston_ma_us"),
    ("boston_ma_us", "seattle_wa_us"),
    ("miami_fl_us", "portland_me_us"),
    ("portland_me_us", "miami_fl_us"),
    ("los_angeles_ca_us", "jacksonville_fl_us"),
    ("jacksonville_fl_us", "los_angeles_ca_us"),
    ("san_diego_ca_us", "great_falls_mt_us"),
    ("barstow_ca_us", "wilmington_nc_us"),
    ("wilmington_nc_us", "barstow_ca_us"),
    ("san_francisco_ca_us", "chicago_il_us"),
    ("grand_junction_co_us", "baltimore_md_us"),
    ("st_louis_mo_us", "lawton_ok_us"),
    ("laredo_tx_us", "duluth_mn_us"),
    ("duluth_mn_us", "laredo_tx_us"),
    ("san_diego_ca_us", "bellingham_wa_us"),
    ("new_orleans_la_us", "chicago_il_us"),
    ("mobile_al_us", "gary_in_us"),
    ("new_orleans_la_us", "chattanooga_tn_us"),
    ("miami_fl_us", "sault_ste_marie_mi_us"),
    ("montgomery_al_us", "petersburg_va_us"),
    ("st_louis_mo_us", "atlanta_ga_us"),
    ("billings_mt_us", "detroit_mi_us"),
    ("muskegon_mi_us", "detroit_mi_us"),
    ("louisville_ky_us", "cleveland_oh_us"),
    ("savannah_ga_us", "cleveland_oh_us"),
    ("bristol_tn_us", "watertown_ny_us"),
    ("norfolk_va_us", "mount_vernon_il_us"),
    ("dallas_tx_us", "little_rock_ar_us"),
    ("san_diego_ca_us", "phoenix_az_us"),
    ("new_york_ny_us", "harrisburg_pa_us"),
    ("odessa_tx_us", "florence_sc_us"),
    // The reported bug, driven directly: Interstate 40 inside Tennessee,
    // where the Oklahoma signs were turning up.
    ("nashville_tn_us", "knoxville_tn_us"),
    ("memphis_tn_us", "knoxville_tn_us"),
    ("knoxville_tn_us", "memphis_tn_us"),
    ("tucson_az_us", "el_paso_tx_us"),
    ("denver_co_us", "kansas_city_mo_us"),
];

const SWEEP_SEEDS: &[i64] = &[1, 2, 3, 4, 5, 6, 7, 8];

struct Shown {
    spoken: String,
    at_mi: f64,
    state: String,
    run: String,
}

/// Every billboard every seeded run schedules, with the state the truck is in
/// where it is read.
fn sweep() -> (Vec<Shown>, usize) {
    let world = world();
    let mut codes: HashMap<String, String> = HashMap::new();
    for city in world.cities.values() {
        if !city.state.is_empty() && !city.state_code.is_empty() {
            codes.insert(city.state.clone(), city.state_code.clone());
        }
    }

    let mut shown = Vec::new();
    let mut built = 0usize;
    for (start, end) in SWEEP_RUNS {
        if world.route_options(start, end, 3, false).is_err() {
            continue;
        }
        for seed in SWEEP_SEEDS {
            // Weather pinned inside `make_trip_with`; the seed pins the route
            // draw and the billboard RNG, so a run is reproducible.
            let trip = make_trip_with(world, start, end, TripOptions::seeded(*seed));
            built += 1;
            for callout in &trip.billboards {
                let name = trip.state_at(Some(callout.at_mi));
                let code = codes.get(&name).cloned().unwrap_or(name);
                shown.push(Shown {
                    spoken: callout.spoken.clone(),
                    at_mi: callout.at_mi,
                    state: code,
                    run: format!("{start} -> {end} seed {seed}"),
                });
            }
        }
    }
    (shown, built)
}

/// Every place claim a line makes, as (phrase, honest states).
fn claims(spoken: &str) -> Vec<(&'static str, &'static [&'static str])> {
    PLACE_CLAIMS
        .iter()
        .filter(|(phrase, _)| spoken.contains(phrase))
        .map(|(phrase, states)| (*phrase, *states))
        .collect()
}

/// The report, driven: Interstate 40 across Tennessee used to read Oklahoma
/// signs, because the corridor pool was keyed on the shield and Interstate 40
/// runs through both states.
#[test]
fn test_the_tennessee_run_reads_no_oklahoma_sign() {
    let world = world();
    let mut seen_any = false;
    for seed in 1..=40i64 {
        for (a, b) in [
            ("nashville_tn_us", "knoxville_tn_us"),
            ("knoxville_tn_us", "nashville_tn_us"),
            ("memphis_tn_us", "knoxville_tn_us"),
        ] {
            let trip = make_trip_with(world, a, b, TripOptions::seeded(seed));
            for callout in &trip.billboards {
                seen_any = true;
                for claim in ["Okemah", "Muskogee", "Tulsa", "Winslow", "Wall Drug"] {
                    assert!(
                        !callout.spoken.contains(claim),
                        "{a} -> {b} seed {seed}: read \"{claim}\" at mile {:.1}",
                        callout.at_mi
                    );
                }
            }
        }
    }
    assert!(seen_any, "the Tennessee runs scheduled no billboard at all");
}

/// The other half of the reported mess: the same runs must still get the signs
/// that ARE true in Tennessee, or the fix has traded a wrong sign for silence.
#[test]
fn test_the_tennessee_run_still_gets_its_own_corridor_signs() {
    let world = world();
    let mut local = 0usize;
    for seed in 1..=40i64 {
        let trip = make_trip_with(
            world,
            "memphis_tn_us",
            "knoxville_tn_us",
            TripOptions::seeded(seed),
        );
        local += trip
            .billboards
            .iter()
            .filter(|c| {
                c.spoken.contains("East Tennessee")
                    || c.spoken.contains("Memphis, on down the road")
            })
            .count();
    }
    assert!(local > 0, "no Tennessee sign survived on a Tennessee run");
}

/// The approach window is a road distance, so a named city must actually be
/// ahead of the sign, not behind it.
#[test]
fn test_a_named_city_is_always_still_ahead_when_its_sign_is_read() {
    let world = world();
    let mut checked = 0usize;
    for seed in 1..=12i64 {
        let trip = make_trip_with(
            world,
            "miami_fl_us",
            "portland_me_us",
            TripOptions::seeded(seed),
        );
        let jacksonville = trip
            .route
            .cities
            .iter()
            .position(|c| c == "jacksonville_fl_us")
            .map(|i| trip.city_mileposts[i]);
        let Some(milepost) = jacksonville else {
            continue;
        };
        for callout in &trip.billboards {
            if !callout.spoken.contains("Jacksonville ahead") {
                continue;
            }
            checked += 1;
            let ahead = milepost - callout.at_mi;
            assert!(
                ahead > 0.0 && ahead <= 150.0,
                "\"Jacksonville ahead\" read {ahead:.1} miles from Jacksonville on seed {seed}"
            );
        }
    }
    assert!(checked > 0, "the sign never appeared on a route through it");
}

#[test]
fn test_no_billboard_names_a_place_the_truck_is_not_near() {
    let (shown, built) = sweep();
    assert!(built >= 200, "only {built} seeded runs built");
    assert!(
        shown.len() >= 2000,
        "only {} billboards over {built} runs",
        shown.len()
    );

    let mut misplaced: Vec<String> = Vec::new();
    let mut by_phrase: HashMap<&'static str, usize> = HashMap::new();
    let mut claiming = 0usize;
    for sign in &shown {
        for phrase in [
            "All his exes live around here somewhere",
            "Amarillo can wait till morning",
            "Black Bear Road",
            "Mexican Radio",
            "Haynesville Woods",
            "Ionia County, Michigan",
            "Arlo McKinley",
            "Russell County line",
            "Forty-Nine Winchester",
        ] {
            assert!(
                !sign.spoken.contains(phrase),
                "pulled line fired in {} at mile {:.1} on {}: {}",
                sign.state,
                sign.at_mi,
                sign.run,
                sign.spoken
            );
        }
        if sign.spoken.contains("Wall Drug") {
            assert!(
                sign.state == "SD" || sign.state == "MN" || sign.state.is_empty(),
                "Wall Drug in {} at mile {:.1} on {}",
                sign.state,
                sign.at_mi,
                sign.run
            );
        }
        if sign.spoken.contains("Dock of the Bay") {
            assert!(
                sign.state == "CA" || sign.state.is_empty(),
                "Dock of the Bay in {} at mile {:.1} on {}",
                sign.state,
                sign.at_mi,
                sign.run
            );
        }
        if sign.spoken.contains("caverns ahead") {
            assert!(
                sign.state == "MO" || sign.state.is_empty(),
                "Meramec in {} at mile {:.1} on {}",
                sign.state,
                sign.at_mi,
                sign.run
            );
        }
        let found = claims(&sign.spoken);
        if found.is_empty() {
            continue;
        }
        claiming += 1;
        for (phrase, honest) in found {
            // An unbaked state is not evidence of a misplacement; the sweep
            // counts only signs read somewhere the bake can name.
            if sign.state.is_empty() {
                continue;
            }
            if !honest.contains(&sign.state.as_str()) {
                *by_phrase.entry(phrase).or_default() += 1;
                misplaced.push(format!(
                    "\"{phrase}\" read in {} at mile {:.1} on {} -- honest in {honest:?}",
                    sign.state, sign.at_mi, sign.run
                ));
            }
        }
    }

    // A placement rule can always reach zero misplacements by never placing a
    // place-naming sign at all, which would quietly delete the corridor
    // character this catalog exists for. The floor is what stops that: the
    // sweep must still be SEEING these signs, in the states they belong to.
    // The floor sits above the 612 that were correctly placed before the
    // anchors went in, so it also records that anchoring did not cost the
    // roadside its corridor character -- it gained a little.
    assert!(
        claiming >= 600,
        "only {claiming} place-naming billboards over {} shown -- the corridor \
         pools have gone quiet, which is not the same as being right",
        shown.len()
    );
    let mut unique: Vec<&String> = misplaced
        .iter()
        .collect::<HashSet<_>>()
        .into_iter()
        .collect();
    unique.sort();
    // Lead with the tally so a regression names its worst offenders instead of
    // burying them in the first forty lines of a sorted list.
    let mut tally: Vec<(&str, usize)> = by_phrase.into_iter().collect();
    tally.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(b.0)));
    assert!(
        misplaced.is_empty(),
        "{} of {claiming} place-naming billboards ({:.1}%) were read somewhere the place is \
         not.\nworst offenders:\n{}\nexamples ({} distinct):\n{}",
        misplaced.len(),
        100.0 * misplaced.len() as f64 / claiming as f64,
        tally
            .iter()
            .take(15)
            .map(|(phrase, n)| format!("  {n:>4}  \"{phrase}\""))
            .collect::<Vec<_>>()
            .join("\n"),
        unique.len(),
        unique
            .iter()
            .take(25)
            .map(|s| s.as_str())
            .collect::<Vec<_>>()
            .join("\n")
    );
}

/// Wall Drug is a South Dakota attraction. Montana I-90 must never read it.
#[test]
fn test_wall_drug_never_reads_in_montana() {
    let world = world();
    let mut seen_any = false;
    for seed in 1..=40i64 {
        let trip = make_trip_with(
            world,
            "missoula_mt_us",
            "billings_mt_us",
            TripOptions::seeded(seed),
        );
        for callout in &trip.billboards {
            seen_any = true;
            assert!(
                !callout.spoken.contains("Wall Drug"),
                "seed {seed}: Wall Drug in Montana at mile {:.1}: {}",
                callout.at_mi,
                callout.spoken
            );
        }
    }
    assert!(
        seen_any,
        "the Montana I-90 run scheduled no billboard at all"
    );
}

/// The two Wall Drug lines must still speak on the South Dakota I-90 run,
/// or pulling Montana has traded a wrong sign for silence.
#[test]
fn test_wall_drug_still_reads_in_south_dakota() {
    let world = world();
    let mut hits = 0usize;
    for seed in 1..=40i64 {
        let trip = make_trip_with(
            world,
            "rapid_city_sd_us",
            "sioux_falls_sd_us",
            TripOptions::seeded(seed),
        );
        hits += trip
            .billboards
            .iter()
            .filter(|c| c.spoken.contains("Wall Drug"))
            .count();
    }
    assert!(hits > 0, "Wall Drug never appeared on South Dakota I-90");
}

/// Meramec Caverns is Interstate 44 Missouri. Interstate 40 Arkansas must
/// never read it.
#[test]
fn test_meramec_never_reads_in_arkansas() {
    let world = world();
    let mut seen_any = false;
    for seed in 1..=40i64 {
        for (a, b) in [
            ("fort_smith_ar_us", "little_rock_ar_us"),
            ("little_rock_ar_us", "fort_smith_ar_us"),
        ] {
            if world.route_options(a, b, 3, false).is_err() {
                continue;
            }
            let trip = make_trip_with(world, a, b, TripOptions::seeded(seed));
            for callout in &trip.billboards {
                seen_any = true;
                assert!(
                    !callout.spoken.contains("caverns ahead"),
                    "{a} -> {b} seed {seed}: Meramec in Arkansas at mile {:.1}: {}",
                    callout.at_mi,
                    callout.spoken
                );
            }
        }
    }
    assert!(
        seen_any,
        "the Arkansas I-40 run scheduled no billboard at all"
    );
}

/// The moved Meramec line must still speak on Interstate 44 in Missouri.
#[test]
fn test_meramec_still_reads_on_interstate_44_missouri() {
    let world = world();
    let mut hits = 0usize;
    for seed in 1..=40i64 {
        let trip = make_trip_with(
            world,
            "st_louis_mo_us",
            "springfield_mo_us",
            TripOptions::seeded(seed),
        );
        hits += trip
            .billboards
            .iter()
            .filter(|c| c.spoken.contains("Meramec-style caverns"))
            .count();
    }
    assert!(hits > 0, "Meramec never appeared on Interstate 44 Missouri");
}

/// Otis Redding's dock is the San Francisco bay. Nevada I-80 must never
/// read it.
#[test]
fn test_dock_of_the_bay_never_reads_in_nevada() {
    let world = world();
    let mut seen_any = false;
    for seed in 1..=40i64 {
        let trip = make_trip_with(world, "reno_nv_us", "elko_nv_us", TripOptions::seeded(seed));
        for callout in &trip.billboards {
            seen_any = true;
            assert!(
                !callout.spoken.contains("Dock of the Bay"),
                "seed {seed}: Dock of the Bay in Nevada at mile {:.1}: {}",
                callout.at_mi,
                callout.spoken
            );
        }
    }
    assert!(
        seen_any,
        "the Nevada I-80 run scheduled no billboard at all"
    );
}
