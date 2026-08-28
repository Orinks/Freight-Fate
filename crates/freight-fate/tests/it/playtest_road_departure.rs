//! `--playtest-road --find departure`: a loaded truck must start at a real
//! facility's outbound street chain, with automatic speed control ready to
//! cover the on-ramp before adaptive cruise takes the highway.

use ff_core::data::world::get_world;

use freight_fate::playtest::harness::PlaytestHarness;
use freight_fate::playtest::road::{find_feature, route_pairs, RoadOptions, FEATURES};

const TRIP_SEED: i64 = 20260827;

fn departure_options() -> RoadOptions {
    RoadOptions {
        feature: "departure".to_string(),
        trip_seed: Some(TRIP_SEED),
        ..Default::default()
    }
}

fn departure_hit() -> freight_fate::playtest::road::Hit {
    let opts = departure_options();
    let pairs = route_pairs(get_world(), &opts);
    let hits = find_feature(get_world(), &pairs, "departure", &opts, Some(TRIP_SEED));
    assert_eq!(hits.len(), 1, "departure scenario: {hits:#?}");
    hits.into_iter().next().expect("one departure scenario")
}

#[test]
fn departure_is_a_named_finder_feature() {
    assert!(FEATURES.contains(&"departure"));
    assert_eq!(FEATURES.len(), 12);
}

#[test]
fn departure_finder_selects_the_loaded_carlisle_to_pittsburgh_run() {
    let hit = departure_hit();
    assert_eq!(hit.origin, "Carlisle");
    assert_eq!(hit.destination, "Pittsburgh");
    assert_eq!(hit.at_mi, 0.0, "the gate must still be ahead of the truck");
    assert!(
        hit.label.contains("Carlisle Dry Warehouse"),
        "{}",
        hit.label
    );
}

#[test]
fn departure_starts_loaded_on_the_real_facility_chain_with_speed_keeper_ready() {
    let opts = departure_options();
    let hit = departure_hit();
    let mut harness = PlaytestHarness::new();
    let start_mi = harness.start_road_feature(&hit, &opts);

    assert_eq!(start_mi, 0.0);
    assert!(harness.app.ctx.settings.speed_keeper);
    harness.with_drive(|drive, _| {
        assert_eq!(drive.job.origin_location, "Carlisle Dry Warehouse");
        assert!(drive.speed_control_armed);
        assert_eq!(drive.trip.position_mi, 0.0);
        assert_eq!(drive.truck().speed_mph(), 0.0);
    });

    // The first real frame must choose the origin facility's streets, not
    // leave the staged truck on a generic highway start. The existing
    // departure-merge regressions then cover the real I-76 lane and keeper
    // to adaptive-cruise handoff this scenario exposes to the player.
    harness.advance_frame_clock();
    harness.with_drive(|drive, ctx| drive.update_frame(ctx, 1.0 / 60.0));
    harness.with_drive(|drive, _| {
        assert!(drive.departure_chain, "the real departure chain did not start");
        assert!(drive.highway_trip.is_some(), "the highway trip was not held for the merge");
    });
}
