//! Navigation-cue wiring for curated interchanges, grounded exits/onramps and
//! metric navigation distances (the trip half of
//! `tests/test_interchanges.py`; phrasing and parsing live in
//! `data_interchanges.rs`).


use ff_core::data::world::World;
use ff_core::data::world_models::{Interchange, Leg, Route, Stop};
use ff_core::sim::trip::{Trip, TripOptions};
use ff_core::sim::trip_models::{NavigationCue, TripEventKind, Zone};
use ff_core::sim::trip_route_helpers::{leg_heading, nearest_exit_label};
use ff_core::sim::vehicle::TruckState;
use crate::sim_support::*;

fn strings(items: &[&str]) -> Vec<String> {
    items.iter().map(|s| s.to_string()).collect()
}

fn trip_on(route: Route, imperial: bool) -> Trip {
    Trip::new(
        route,
        TruckState::default(),
        weather("great_lakes", 1),
        TripOptions {
            seed: Some(2),
            imperial,
            world: Some(world()),
            ..Default::default()
        },
    )
}

/// A running automatic truck, as the drive-loop cases build one.
fn rolling_truck() -> TruckState {
    let mut truck = TruckState::default();
    truck.transmission.automatic = true;
    truck.start_engine();
    truck
}

/// One frame of the Python drive loop: shift, integrate, then step the trip.
fn drive_frame(trip: &mut Trip) -> Vec<ff_core::sim::trip_models::TripEvent> {
    trip.truck.auto_shift();
    trip.truck.update(1.0 / 60.0);
    trip.update(1.0 / 60.0)
}

/// `tests/test_interchanges.py::_route_with_interchange`.
fn route_with_interchange(w: &'static World, start: &str, end: &str) -> (Route, f64) {
    let route = first_route_option(w, start, end);
    let leg = route.legs[0].clone();
    let at = leg.miles / 2.0;
    let ix = Interchange {
        at_mi: at,
        exit_ref: "21".to_string(),
        destinations: strings(&["Lafayette"]),
        via: "US 52 West".to_string(),
        highway: leg.highway.clone(),
        source: "OSM".to_string(),
        ..Default::default()
    };
    let edited = with_corridor(&leg, |detail| detail.interchanges = vec![ix]);
    (replace_leg(&route, 0, edited), at)
}

/// `tests/test_interchanges.py::_leg0_curated_stop`: the first curated stop of
/// leg 0 that applies in the travel direction.
fn leg0_curated_stop(route: &Route) -> (Leg, Stop) {
    let leg = route.legs[0].clone();
    let forward = route.cities[0] == leg.a;
    let stop = leg
        .stops
        .iter()
        .find(|s| s.curated() && s.applies_to_direction(forward))
        .expect("leg 0 has a curated stop in this direction")
        .clone();
    ((*leg).clone(), stop)
}

// --- cue wiring -------------------------------------------------------------

#[test]
fn test_interchange_produces_navigation_cue() {
    let (route, _) = route_with_interchange(world(), "Chicago", "Indianapolis");
    let trip = trip_on(route, true);
    let cues: Vec<&NavigationCue> = trip
        .navigation_cues
        .iter()
        .filter(|c| c.kind == "interchange")
        .collect();
    assert_eq!(cues.len(), 1);
    assert!(cues[0].text.contains("exit 21"), "{}", cues[0].text);
    assert!(cues[0].text.contains("Lafayette"), "{}", cues[0].text);
}

#[test]
fn test_interchange_cue_stays_silent_during_drive() {
    let (route, _) = route_with_interchange(world(), "Chicago", "Indianapolis");
    let mut trip = Trip::new(
        route,
        rolling_truck(),
        weather("great_lakes", 1),
        TripOptions {
            seed: Some(2),
            world: Some(world()),
            ..Default::default()
        },
    );
    trip.truck.throttle = 0.85;
    let mut seen: Vec<String> = Vec::new();
    for _ in 0..(60 * 60 * 10) {
        for ev in drive_frame(&mut trip) {
            if ev
                .data
                .cue
                .as_ref()
                .is_some_and(|c| c.kind == "interchange")
            {
                seen.push(ev.text().to_string());
            }
        }
        if trip.finished {
            break;
        }
    }
    assert!(seen.is_empty(), "{seen:?}");
}

#[test]
fn test_reverse_direction_mirrors_interchange_position() {
    let w = world();
    let forward = first_route_option(w, "Chicago", "Indianapolis");
    let leg = forward.legs[0].clone();
    let at = leg.miles / 2.0 - 10.0;
    let ix = Interchange {
        at_mi: at,
        exit_ref: "21".to_string(),
        destinations: strings(&["Lafayette"]),
        via: "US 52 West".to_string(),
        highway: leg.highway.clone(),
        source: "OSM".to_string(),
        ..Default::default()
    };

    let forward = replace_leg(
        &forward,
        0,
        with_corridor(&leg, |detail| detail.interchanges = vec![ix.clone()]),
    );
    let fwd_trip = trip_on(forward, true);
    let fwd_cue = fwd_trip
        .navigation_cues
        .iter()
        .find(|c| c.kind == "interchange")
        .expect("forward interchange cue");

    let reverse = first_route_option(w, "Indianapolis", "Chicago");
    let rev_leg = reverse.legs[0].clone();
    let rev_miles = rev_leg.miles;
    let mirrored = Interchange {
        highway: rev_leg.highway.clone(),
        ..ix
    };
    let reverse = replace_leg(
        &reverse,
        0,
        with_corridor(&rev_leg, |detail| detail.interchanges = vec![mirrored]),
    );
    let rev_trip = trip_on(reverse, true);
    let rev_cue = rev_trip
        .navigation_cues
        .iter()
        .find(|c| c.kind == "interchange")
        .expect("reverse interchange cue");

    // Same physical exit, mirrored mileage from the opposite travel direction.
    assert!(
        (fwd_cue.at_mi - (rev_miles - rev_cue.at_mi)).abs() < 0.2,
        "{} vs {}",
        fwd_cue.at_mi,
        rev_miles - rev_cue.at_mi
    );
}

#[test]
fn test_next_exit_context_mentions_flavor_exit() {
    let (route, _) = route_with_interchange(world(), "Chicago", "Indianapolis");
    let mut trip = trip_on(route, true);
    trip.navigation_cues = vec![NavigationCue::new(
        "interchange:0:50:21",
        "interchange",
        50.0,
        "exit 21 for US-52 West toward Lafayette",
        "",
    )];
    trip.position_mi = 40.0;
    assert_eq!(
        trip.next_navigation_context(true),
        "Destination Indianapolis ahead."
    );
    assert_eq!(
        trip.next_exit_context(),
        "Next listed exit in 10 miles: exit 21 for US-52 West toward Lafayette."
    );
}

#[test]
fn test_next_navigation_context_prioritizes_actionable_stop_over_exit() {
    let (route, _) = route_with_interchange(world(), "Chicago", "Indianapolis");
    let mut trip = trip_on(route, true);
    trip.navigation_cues = vec![
        NavigationCue::new(
            "interchange:0:40:21",
            "interchange",
            40.0,
            "exit 21 for US-52 West toward Lafayette",
            "",
        ),
        NavigationCue::new(
            "rest_stop:0:50:pilot",
            "rest_stop",
            50.0,
            "travel center ahead at exit 26",
            "",
        ),
    ];
    trip.position_mi = 30.0;
    assert_eq!(
        trip.next_navigation_context(true),
        "Next stop in 20 miles: travel center ahead at exit 26."
    );
    assert_eq!(
        trip.next_exit_context(),
        "Next listed exit in 10 miles: exit 21 for US-52 West toward Lafayette."
    );
}

// --- Scope A: grounded exits, ramps, onramps --------------------------------

#[test]
fn test_leg_heading_follows_route_numbering() {
    let w = world();
    // Odd routes are signed N/S even where the geometry runs diagonally
    // (I-95 NY->Philadelphia trends southwest but is signed South).
    assert_eq!(
        leg_heading(w, "I-95", "new_york_ny_us", "philadelphia_pa_us"),
        "South"
    );
    assert_eq!(
        leg_heading(w, "I-95", "philadelphia_pa_us", "new_york_ny_us"),
        "North"
    );
    // Even routes are signed E/W.
    assert_eq!(
        leg_heading(w, "I-80", "chicago_il_us", "cleveland_oh_us"),
        "East"
    );
    assert_eq!(
        leg_heading(w, "I-80", "cleveland_oh_us", "chicago_il_us"),
        "West"
    );
    // No route number -> no heading.
    assert_eq!(
        leg_heading(w, "Local Road", "chicago_il_us", "cleveland_oh_us"),
        ""
    );
}

#[test]
fn test_nearest_exit_label_respects_tolerance() {
    let base = first_route_option(world(), "Chicago", "Indianapolis").legs[0].clone();
    let leg = with_corridor(&base, |detail| {
        detail.interchanges = vec![
            Interchange {
                at_mi: 50.0,
                exit_ref: "7".to_string(),
                source: "x".to_string(),
                ..Default::default()
            },
            Interchange {
                at_mi: 80.0,
                destinations: strings(&["Town"]),
                source: "x".to_string(),
                ..Default::default()
            },
        ]
    });
    assert_eq!(nearest_exit_label(&leg, 51.0, 2.0), "exit 7"); // within 2.0 mi
    assert_eq!(nearest_exit_label(&leg, 55.0, 2.0), ""); // too far
    assert_eq!(nearest_exit_label(&leg, 80.0, 2.0), ""); // nearest has no ref
}

#[test]
fn test_place_stops_attaches_exit_label() {
    let route = first_route_option(world(), "Chicago", "Indianapolis");
    let (leg, target) = leg0_curated_stop(&route);
    let ix = Interchange {
        at_mi: target.at_mi,
        exit_ref: "21".to_string(),
        destinations: strings(&["Lafayette"]),
        via: "US 52 West".to_string(),
        highway: leg.highway.clone(),
        source: "OSM".to_string(),
        ..Default::default()
    };
    let route = replace_leg(
        &route,
        0,
        with_corridor(&leg, |detail| detail.interchanges = vec![ix]),
    );
    let trip = trip_on(route, true);
    let placed = trip
        .stops
        .iter()
        .find(|s| s.name == target.name)
        .expect("the curated stop was placed");
    assert_eq!(placed.exit_label, "exit 21");
}

#[test]
fn test_rest_stop_cue_names_exit_when_linked() {
    let route = first_route_option(world(), "Chicago", "Indianapolis");
    let (leg, target) = leg0_curated_stop(&route);
    let ix = Interchange {
        at_mi: target.at_mi,
        exit_ref: "21".to_string(),
        destinations: strings(&["Lafayette"]),
        via: "US 52 West".to_string(),
        highway: leg.highway.clone(),
        source: "OSM".to_string(),
        ..Default::default()
    };
    let route = replace_leg(
        &route,
        0,
        with_corridor(&leg, |detail| detail.interchanges = vec![ix]),
    );
    let trip = trip_on(route, true);
    let cue = trip
        .navigation_cues
        .iter()
        .find(|c| c.kind == "rest_stop" && c.key.contains(&target.name))
        .expect("a rest-stop cue for the curated stop");
    assert!(cue.text.contains("at exit 21"), "{}", cue.text);
    assert_eq!(cue.near_text, "");
}

#[test]
fn test_rest_stop_cue_generic_without_linked_exit() {
    let route = first_route_option(world(), "Chicago", "Indianapolis");
    let (leg, target) = leg0_curated_stop(&route);
    let route = replace_leg(
        &route,
        0,
        with_corridor(&leg, |detail| detail.interchanges = Vec::new()),
    );
    let trip = trip_on(route, true);
    let cue = trip
        .navigation_cues
        .iter()
        .find(|c| c.kind == "rest_stop" && c.key.contains(&target.name))
        .expect("a rest-stop cue for the curated stop");
    assert!(!cue.text.contains("at exit"), "{}", cue.text); // no fabricated exit number
    assert_eq!(cue.near_text, "");
}

#[test]
fn test_first_leg_has_onramp_cue() {
    let route = first_route_option(world(), "Chicago", "Indianapolis");
    let highway = route.legs[0].highway.clone();
    let trip = trip_on(route, true);
    let onramps: Vec<&NavigationCue> = trip
        .navigation_cues
        .iter()
        .filter(|c| c.kind == "onramp")
        .collect();
    assert_eq!(onramps.len(), 1);
    let text = &onramps[0].near_text;
    assert!(
        text.starts_with(&format!("Merge onto {highway} South toward ")),
        "{text}"
    );
    assert!(
        text.contains("Indianapolis") && text.contains("miles."),
        "{text}"
    );
}

#[test]
fn test_onramp_cue_fires_at_drive_start() {
    let route = first_route_option(world(), "Chicago", "Indianapolis");
    let mut trip = Trip::new(
        route,
        rolling_truck(),
        weather("great_lakes", 1),
        TripOptions {
            seed: Some(2),
            world: Some(world()),
            ..Default::default()
        },
    );
    trip.truck.throttle = 0.85;
    let mut seen: Vec<String> = Vec::new();
    for _ in 0..(60 * 120) {
        for ev in drive_frame(&mut trip) {
            if ev.text().contains("Merge onto") {
                seen.push(ev.text().to_string());
            }
        }
        if !seen.is_empty() {
            break;
        }
    }
    assert!(
        seen.first().is_some_and(|m| m.starts_with("Merge onto")),
        "{seen:?}"
    );
}

// --- metric navigation distances --------------------------------------------

#[test]
fn test_metric_navigation_cues_use_kilometers() {
    let route = first_route_option(world(), "Chicago", "Indianapolis");
    let metric = trip_on(route.clone(), false);
    let blob = metric
        .navigation_cues
        .iter()
        .map(|c| format!("{} {}", c.text, c.near_text))
        .collect::<Vec<_>>()
        .join(" ");
    assert!(blob.contains("kilometers"));
    assert!(!blob.contains("mile"), "{blob}");

    // The default (imperial) trip keeps miles, so existing drives are unchanged.
    let imperial = trip_on(route, true);
    let blob_i = imperial
        .navigation_cues
        .iter()
        .map(|c| format!("{} {}", c.text, c.near_text))
        .collect::<Vec<_>>()
        .join(" ");
    assert!(blob_i.contains("miles"));
}

#[test]
fn test_metric_drive_speaks_distances_in_kilometers() {
    let route = first_route_option(world(), "Chicago", "Indianapolis");
    let mut trip = Trip::new(
        route,
        rolling_truck(),
        weather("great_lakes", 1),
        TripOptions {
            seed: Some(2),
            imperial: false,
            world: Some(world()),
            ..Default::default()
        },
    );
    trip.truck.throttle = 0.85;
    let mut nav: Vec<String> = Vec::new();
    for _ in 0..(60 * 60 * 12) {
        for ev in drive_frame(&mut trip) {
            if matches!(ev.kind, TripEventKind::GpsCue | TripEventKind::StopAhead) {
                nav.push(ev.text().to_string());
            }
        }
        if trip.finished {
            break;
        }
    }
    assert!(
        !nav.is_empty(),
        "expected navigation announcements on a long metric drive"
    );
    let blob = nav.join(" ");
    assert!(blob.contains("kilometers"));
    assert!(!blob.contains("mile"), "{blob}");
}

#[test]
fn test_unit_toggle_rerenders_baked_navigation_cues() {
    let route = first_route_option(world(), "Chicago", "Indianapolis");
    let mut trip = trip_on(route, true);

    fn cue_blob(trip: &Trip) -> String {
        trip.navigation_cues
            .iter()
            .map(|c| format!("{} {}", c.text, c.near_text))
            .collect::<Vec<_>>()
            .join(" ")
    }

    assert!(cue_blob(&trip).contains("miles") && !cue_blob(&trip).contains("kilometers"));
    // Switching units mid-trip re-renders the distances already on the route.
    trip.set_imperial(false);
    assert!(cue_blob(&trip).contains("kilometers") && !cue_blob(&trip).contains("mile"));
    trip.set_imperial(true);
    assert!(cue_blob(&trip).contains("miles") && !cue_blob(&trip).contains("kilometers"));
}

#[test]
fn test_metric_zone_warning_uses_metric_speed_limit() {
    let route = first_route_option(world(), "Chicago", "Indianapolis");
    let mut trip = trip_on(route, false);
    trip.zones = vec![Zone::new(5.0, 10.0, 45.0, "construction")];
    trip.announced_zone_warnings.clear();
    trip.position_mi = 4.0; // within the 2-mile warning lookahead of the zone

    let msgs: Vec<String> = trip
        .update(0.0)
        .iter()
        .filter(|ev| ev.kind == TripEventKind::GpsCue)
        .map(|ev| ev.text().to_string())
        .collect();
    let blob = msgs.join(" ");
    // 55/45 mph rendered as km/h
    assert!(
        blob.contains("Speed limit 89 at the taper, then 72"),
        "{blob}"
    );
    assert!(
        !blob.contains("Speed limit 55 at the taper, then 45"),
        "{blob}"
    );
}
