//! The street detail baked for facility chains (`tools/street_chain.py`):
//! the ramp terminal each exit hands over at, the chain from it, each
//! street's limit with its kind, the controls along the way, and the
//! driveway. One accessor each; Some for a known place, None where the bake
//! has nothing.

use crate::sim_support::*;
use ff_core::data::street_limits::load_street_limits;
use ff_core::data::world_local_data::load_facility_approaches;
use ff_core::data::world_models::Route;
use ff_core::data::world_parsing::parse_interchange;
use ff_core::sim::trip::{Trip, TripOptions};
use ff_core::sim::vehicle::TruckState;

// I-65 Louisville to Columbus, as baked from OSM 2026-09-24: exit 68's
// northbound ramp ends at node 1751803731 on Jonathan Moore Pike (SR 46),
// and the Columbus company yard has a chain from there.
const COLUMBUS: &str = "columbus_in_us";
const LOUISVILLE: &str = "louisville_ky_us";
const YARD: &str = "Columbus Company Yard";
const EXIT_68_TERMINAL: i64 = 1_751_803_731;

fn trip_on(route: Route) -> Trip {
    Trip::new(
        route,
        TruckState::default(),
        weather("heartland", 1),
        TripOptions {
            seed: Some(2),
            imperial: true,
            world: Some(world()),
            ..Default::default()
        },
    )
}

#[test]
fn a_known_exit_names_the_node_its_ramp_ends_at() {
    let w = world();
    let route = first_route_option(w, LOUISVILLE, COLUMBUS);
    assert_eq!(route.legs[0].highway, "I-65");
    let exit_68 = route.legs[0].miles - (72.0 - 69.63);
    let trip = trip_on(route.clone());
    assert_eq!(trip.ramp_terminal_node_at(exit_68), Some(EXIT_68_TERMINAL));
    // Southbound the same exit baked no terminal.
    let reverse = first_route_option(w, COLUMBUS, LOUISVILLE);
    let back = reverse.legs[0].miles - exit_68;
    assert_eq!(trip_on(reverse).ramp_terminal_node_at(back), None);
}

#[test]
fn a_terminal_without_a_source_is_refused() {
    let raw = serde_json::json!({
        "at_mi": 1.0,
        "exit_ref": "1",
        "source": "fixture",
        "ramp_terminal_forward": {"node": 42, "lat": 40.0, "lon": -80.0},
    });
    assert!(parse_interchange(&raw, 2.0, "A", "B", "I-1").is_err());
    let mut sourced = raw.clone();
    sourced["ramp_terminal_source"] = "read (fixture)".into();
    let ix = parse_interchange(&sourced, 2.0, "A", "B", "I-1").unwrap();
    assert_eq!(ix.ramp_terminal_node_forward, Some(42));
    assert_eq!(ix.ramp_terminal_node_backward, None);
}

#[test]
fn the_chain_from_a_terminal_starts_on_the_street_the_ramp_meets() {
    let w = world();
    let route = w
        .facility_exit_route(COLUMBUS, YARD, EXIT_68_TERMINAL)
        .unwrap()
        .expect("a chain from exit 68");
    assert_eq!(
        route.legs[0].local_cue,
        "Start on Jonathan Moore Pike (SR 46)."
    );
    assert!(route.legs.len() > 2);
    assert!(w.facility_exit_route(COLUMBUS, YARD, 1).unwrap().is_none());
}

#[test]
fn each_street_carries_its_limit_and_its_kind() {
    let route = world()
        .facility_exit_route(COLUMBUS, YARD, EXIT_68_TERMINAL)
        .unwrap()
        .unwrap();
    let trip = trip_on(route.clone());
    let pike = trip
        .street_limit_at(0.01)
        .expect("a limit on the first street");
    assert_eq!((pike.mph, pike.source.as_str()), (40.0, "read"));
    let second = route.legs[0].miles + 0.01;
    let goeller = trip.street_limit_at(second).expect("a limit on Goeller");
    assert_eq!(goeller.source, "statutory");
    // Off a facility chain there is none.
    let highway = trip_on(first_route_option(world(), LOUISVILLE, COLUMBUS));
    assert_eq!(highway.street_limit_at(10.0), None);
}

#[test]
fn every_statutory_limit_is_the_games_own_statutory_answer() {
    // The bake ports StreetLimits::statutory_mph to Python; this holds the
    // two to one rule over every street it filled.
    let limits = load_street_limits();
    let approaches = load_facility_approaches(&ff_core::data::data_resources::data_path(
        "facility_approaches.json",
    ))
    .unwrap();
    // The rural half is read straight off the table the bake used.
    let table: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(ff_core::data::data_resources::data_path(
            "street_limits.json",
        ))
        .unwrap(),
    )
    .unwrap();
    let rural = |state: &str| -> Vec<f64> {
        let row = &table["limits"][state]["rural"];
        ["highway_mph", "local_mph"]
            .iter()
            .filter_map(|key| row[*key].as_f64())
            .collect()
    };
    let (mut town, mut outside) = (0, 0);
    for approach in approaches.values() {
        let chains = std::iter::once(&approach.segments)
            .chain(approach.exit_chains.iter().map(|chain| &chain.segments));
        for segment in chains.flatten() {
            let Some(limit) = segment.limit.as_ref().filter(|l| l.source == "statutory") else {
                continue;
            };
            let what = format!("{} {} {}", approach.facility_id, segment.road, limit.basis);
            match limit.basis.as_str() {
                "town" => {
                    assert_eq!(
                        Some(limit.mph),
                        limits.statutory_mph(&approach.state),
                        "{what}"
                    );
                    town += 1;
                }
                "rural" => {
                    assert!(rural(&approach.state).contains(&limit.mph), "{what}");
                    outside += 1;
                }
                other => panic!("{what}: basis {other:?}"),
            }
        }
    }
    assert!(town > 1000 && outside > 100, "{town} {outside}");
}

#[test]
fn a_limit_without_its_kind_is_refused_at_load() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("facility_approaches.json");
    let file = |segment: serde_json::Value| {
        serde_json::json!({"approaches": {"x": {
            "facility_name": "X", "endpoint_name": "X", "approach_road": "Main Street",
            "source_type": "osm_local_road_graph", "fallback": false, "turn_level": true,
            "segments": [segment],
        }}})
        .to_string()
    };
    let street = serde_json::json!({
        "road": "Main Street", "cue": "Start on Main Street.", "miles": 0.5,
        "limit_mph": 30.0, "limit_source": "statutory", "limit_basis": "town",
        "controls": [{"at_mi": 0.2, "kind": "signal"}],
    });
    std::fs::write(&path, file(street.clone())).unwrap();
    let loaded = load_facility_approaches(&path).unwrap();
    let segment = &loaded["x"].segments[0];
    let limit = segment.limit.as_ref().unwrap();
    assert_eq!(
        (limit.source.as_str(), limit.basis.as_str()),
        ("statutory", "town")
    );
    assert_eq!(segment.controls[0].kind, "signal");
    // Which statute a statutory figure follows is part of the figure.
    let mut no_basis = street.clone();
    no_basis["limit_basis"] = "".into();
    std::fs::write(&path, file(no_basis)).unwrap();
    assert!(load_facility_approaches(&path).is_err());
    let mut unlabelled = street.clone();
    unlabelled["limit_source"] = "".into();
    std::fs::write(&path, file(unlabelled)).unwrap();
    assert!(load_facility_approaches(&path).is_err());
    let mut off_street = street;
    off_street["controls"][0]["at_mi"] = 3.0.into();
    std::fs::write(&path, file(off_street)).unwrap();
    assert!(load_facility_approaches(&path).is_err());
}

#[test]
fn controls_are_listed_where_osm_reads_them_and_nowhere_else() {
    let route = world()
        .facility_exit_route(COLUMBUS, YARD, EXIT_68_TERMINAL)
        .unwrap()
        .unwrap();
    let first = route.legs[0].miles;
    let trip = trip_on(route);
    let controls = trip.street_controls_between(0.0, trip.total_miles());
    assert!(controls
        .iter()
        .all(|(_, kind)| *kind == "signal" || ["all_way_stop", "stop", "give_way"].contains(kind)));
    // The signal at the corner onto Goeller Boulevard stands at the corner.
    assert!(controls
        .iter()
        .any(|(at, kind)| (*at - first).abs() < 1e-9 && *kind == "signal"));
    let highway = trip_on(first_route_option(world(), LOUISVILLE, COLUMBUS));
    assert!(highway.street_controls_between(0.0, 72.0).is_empty());
}

#[test]
fn the_driveway_is_known_where_the_chain_leaves_the_street() {
    let w = world();
    let from_exit = w
        .facility_driveway(COLUMBUS, YARD, Some(EXIT_68_TERMINAL))
        .unwrap()
        .expect("a driveway on the exit chain");
    assert_eq!(from_exit.kind, "service_road");
    assert!(from_exit.source.starts_with("derived"));
    let route = w
        .facility_exit_route(COLUMBUS, YARD, EXIT_68_TERMINAL)
        .unwrap()
        .unwrap();
    assert!(0.0 < from_exit.at_mi && from_exit.at_mi <= route.miles() + 0.05);
    assert!(w.facility_driveway(COLUMBUS, YARD, None).unwrap().is_some());
    assert_eq!(w.facility_driveway(COLUMBUS, YARD, Some(1)).unwrap(), None);
}

#[test]
fn a_stop_off_an_exit_has_its_streets_from_the_ramp_that_reaches_it() {
    // I-65 northbound, exit 16 (Memphis, IN): the ramp ends on Memphis-Blue
    // Lick Road and the Love's lot is 0.19 mi on. Southbound that exit's ramp
    // baked no terminal, so there is no chain that way.
    let w = world();
    let trip = trip_on(first_route_option(w, LOUISVILLE, COLUMBUS));
    let stops = trip.place_stops();
    let loves = stops
        .iter()
        .find(|stop| stop.name == "Love's Travel Stop Memphis")
        .expect("the stop is on the route");
    let route = trip
        .stop_approach_route(loves)
        .expect("a chain from the ramp");
    assert_eq!(route.legs[0].local_cue, "Start on Memphis-Blue Lick Road.");
    assert!(route.miles() < 0.5);
    let back = trip_on(first_route_option(w, COLUMBUS, LOUISVILLE));
    if let Some(stop) = back
        .place_stops()
        .iter()
        .find(|stop| stop.name == "Love's Travel Stop Memphis")
    {
        assert!(back.stop_approach_route(stop).is_none());
    }
    // A stop with no decided exit has none.
    let mut unlinked = loves.clone();
    unlinked.interchange_mi = None;
    assert!(trip.stop_approach_route(&unlinked).is_none());
}

#[test]
fn stop_chains_without_a_source_are_refused() {
    use ff_core::data::world_parsing::parse_stop;
    let chain = serde_json::json!([{
        "terminal_node": 7, "total_miles": 0.2,
        "segments": [{"road": "Main Street", "cue": "Start on Main Street.", "miles": 0.2}],
    }]);
    let stop = |with_source: bool| {
        let mut raw = serde_json::json!({
            "name": "Fixture Stop", "type": "travel_center", "at_mi": 1.0,
            "source": "OpenStreetMap fixture", "parking": "likely",
            "actions": ["park"], "services": ["parking"],
            "approach_chains": chain.clone(),
        });
        if with_source {
            raw["approach_source"] = "derived (fixture)".into();
        }
        raw
    };
    assert!(parse_stop(&stop(false), 2.0, "A", "B").is_err());
    let parsed = parse_stop(&stop(true), 2.0, "A", "B").unwrap();
    assert_eq!(parsed.approach_chains[0].terminal_node, 7);
}

#[test]
fn ia_175_beside_the_love_s_is_a_rural_road_at_55() {
    // I-35 exit 144 northbound, Love's Travel Stop: the ramp ends on 330th
    // Street (IA 175), untagged in OSM and outside any Census urban area. It
    // read 20 mph -- Iowa's business-district figure, which no statute puts
    // on a rural state highway; Iowa Code 321.285(3) makes it 55.
    let w = world();
    let trip = trip_on(first_route_option(w, "ames_ia_us", "mason_city_ia_us"));
    let stop = trip
        .place_stops()
        .into_iter()
        .find(|stop| stop.name == "Love's Travel Stop" && stop.interchange_mi.is_some())
        .expect("the Love's is on the route");
    let route = trip.stop_approach_route(&stop).expect("its chain");
    assert_eq!(route.legs[0].local_cue, "Start on 330th Street (IA 175).");
    let limit = trip_on(route)
        .street_limit_at(0.01)
        .cloned()
        .expect("a limit");
    assert_eq!(
        (limit.mph, limit.source.as_str(), limit.basis.as_str()),
        (55.0, "statutory", "rural")
    );
}
