//! A turn-level source approach becomes the drivable route, and its first
//! local cue earns the straight-ahead earcon (the driving-layer case of
//! `tests/test_facility_approaches.py`; the coverage, the honest records and
//! the zone step-down are in `crates/ff-core/tests/data_facility_approaches.rs`
//! and `sim_facility_approaches.rs`).

use std::path::{Path, PathBuf};

use ff_core::data::world::get_world;
use ff_core::sim::trip::{Trip, TripOptions};
use ff_core::sim::trip_models::{TripEvent, TripEventData, TripEventKind};
use ff_core::sim::vehicle::TruckState;
use ff_core::sim::weather::WeatherSystem;
use ff_core::speech_text::SpokenMessage;
use freight_fate::states::driving_core::route_event_sound;

/// The Python package's `data/` folder in the source tree.
fn data_dir() -> PathBuf {
    let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
    let dir = manifest
        .join("..")
        .join("..")
        .join("src")
        .join("freight_fate")
        .join("data");
    dir.canonicalize().unwrap_or(dir)
}

#[test]
fn test_facility_route_prefers_turn_level_source_approach() {
    let world = get_world();
    let text = std::fs::read_to_string(data_dir().join("facility_approaches.json"))
        .expect("the baked facility approaches");
    let data: serde_json::Value =
        serde_json::from_str(text.trim_start_matches('\u{feff}')).expect("valid JSON");
    let (facility_id, record) = data["approaches"]
        .as_object()
        .expect("approaches")
        .iter()
        .find(|(_, record)| record["turn_level"].as_bool().unwrap_or(false))
        .expect("some facility has a turn-level approach");
    let city = record["city"].as_str().expect("city").to_string();
    let facility = world
        .facility_by_id(facility_id)
        .expect("the facility is on the map");
    let name = facility.name.clone();
    let route = world
        .facility_approach_route(&city, &name)
        .expect("an approach route");
    let approach = world
        .facility_source_approach(&city, &name)
        .expect("source approach lookup")
        .expect("a source approach record");

    assert!(approach.turn_level);
    assert!((route.miles() - approach.total_miles).abs() < 1e-9);
    let roads: Vec<String> = approach.segments.iter().map(|s| s.road.clone()).collect();
    assert_eq!(route.highways(), roads);

    let trip = Trip::new(
        route,
        TruckState::default(),
        WeatherSystem::new("heartland", None, None, None, true),
        TripOptions {
            world: Some(world),
            ..Default::default()
        },
    );
    let start_cue = trip
        .navigation_cues
        .iter()
        .find(|cue| cue.key == "local:start")
        .expect("the chain opens with a local start cue");
    assert_eq!(start_cue.direction, "ahead");
    let event = TripEvent {
        kind: TripEventKind::GpsCue,
        message: SpokenMessage::new(start_cue.near_text.clone()),
        data: TripEventData {
            cue: Some(start_cue.clone()),
            ..Default::default()
        },
    };
    assert_eq!(route_event_sound(&event), Some("events/turn_ahead"));
}
