//! `--playtest-road --find destination`: does the finder land the truck at
//! the delivery off-ramp, with the approach still ahead of it?
//!
//! A finder that compiles but drops you in the wrong place is worse than no
//! finder: the owner drives, hears nothing, and reads that as the fix not
//! working. So placement is proved on the transcript -- from the mile the
//! tool chooses, driving forward produces the destination-exit call, and
//! driving past it produces the loop-back.

use ff_core::data::world::get_world;

use freight_fate::playtest::harness::PlaytestHarness;
use freight_fate::playtest::road::destination::destination_lead_mi;
use freight_fate::playtest::road::{
    build_trip, find_feature, Hit, RoadOptions, FEATURES, FLAT_ROUTES, MOUNTAIN_ROUTES,
    ROLLING_ROUTES,
};
use freight_fate::states::driving_core::DESTINATION_EXIT_SCAN_WINDOW_MI;

const MPH_PER_MPS: f64 = 2.23694;
const DT: f64 = 1.0 / 60.0;
/// The seed both the search and the drive run on, so a failure here is the
/// same road every time.
const TRIP_SEED: i64 = 20260826;

fn destination_options() -> RoadOptions {
    RoadOptions {
        feature: "destination".to_string(),
        trip_seed: Some(TRIP_SEED),
        // The driver must be able to blow the exit. With lane keeping on
        // full the truck takes it for them and there is no miss to test.
        lane_keeping: Some("off".to_string()),
        ..Default::default()
    }
}

fn find_one(origin: &str, destination: &str) -> Option<Hit> {
    let opts = destination_options();
    let pairs = vec![(origin.to_string(), destination.to_string())];
    find_feature(get_world(), &pairs, "destination", &opts, Some(TRIP_SEED))
        .into_iter()
        .next()
}

// -- the finder ------------------------------------------------------------------------

#[test]
fn destination_is_one_of_the_named_features() {
    assert!(FEATURES.contains(&"destination"));
    // The count is the list's own guard: a feature added to `find_feature`
    // and forgotten here is a feature no operator can discover.
    assert_eq!(FEATURES.len(), 11);
}

#[test]
fn every_named_route_offers_its_delivery_exit() {
    let world = get_world();
    let opts = destination_options();
    let pairs: Vec<(String, String)> = MOUNTAIN_ROUTES
        .iter()
        .chain(ROLLING_ROUTES.iter())
        .chain(FLAT_ROUTES.iter())
        .map(|(a, b)| (a.to_string(), b.to_string()))
        .collect();
    let hits = find_feature(world, &pairs, "destination", &opts, Some(TRIP_SEED));
    assert_eq!(
        hits.len(),
        pairs.len(),
        "every supported route has a delivery exit; got {hits:#?}"
    );
    for hit in &hits {
        assert!(
            hit.at_mi > 0.0 && hit.at_mi < hit.total_mi,
            "{} -> {} put the exit at {:.1} of {:.0}",
            hit.origin,
            hit.destination,
            hit.at_mi,
            hit.total_mi
        );
        // The drive only ever crowns an interchange inside its final
        // approach window; a hit outside it would be pointing somewhere the
        // game does not call the destination exit.
        assert!(
            hit.total_mi - hit.at_mi <= DESTINATION_EXIT_SCAN_WINDOW_MI,
            "{} -> {} put the exit {:.1} mi from the end",
            hit.origin,
            hit.destination,
            hit.total_mi - hit.at_mi
        );
        assert!(hit.label.starts_with("destination exit"), "{}", hit.label);
    }
    // Signed exits sort ahead of the synthetic end-of-route one, the way an
    // open weigh station sorts ahead of a dark one.
    let signed: Vec<bool> = hits.iter().map(|hit| hit.magnitude > 0.0).collect();
    let first_unsigned = signed.iter().position(|s| !s).unwrap_or(signed.len());
    assert!(
        signed[first_unsigned..].iter().all(|s| !s),
        "signed and unsigned exits are interleaved: {signed:?}"
    );
}

#[test]
fn a_small_city_delivery_still_gets_a_hit() {
    // Hattiesburg is where both reported destination-exit defects were
    // driven, and its approach carries NO signed interchange -- the drive
    // falls back to the synthetic end-of-route exit. A finder that only
    // matched real interchanges would have nothing to offer at exactly the
    // city the owner needs to reach.
    let hit = find_one("jackson_ms_us", "hattiesburg_ms_us")
        .expect("Jackson to Hattiesburg has a delivery exit");
    assert!(hit.at_mi > 0.0 && hit.at_mi < hit.total_mi);
    assert!(
        hit.total_mi - hit.at_mi <= DESTINATION_EXIT_SCAN_WINDOW_MI,
        "{:.1} of {:.0}",
        hit.at_mi,
        hit.total_mi
    );
}

#[test]
fn the_lead_clears_the_callout_window() {
    let world = get_world();
    let opts = destination_options();
    for (origin, destination) in MOUNTAIN_ROUTES.iter().chain(FLAT_ROUTES.iter()) {
        let trip = build_trip(world, origin, destination, Some(TRIP_SEED))
            .expect("the named routes route");
        let lead = destination_lead_mi(&trip, opts.speed);
        // The drive announces one exit window out; the lead has to be
        // strictly longer or the call fires before the wheel is handed over.
        // Five miles is the window's own floor, so nothing can be shorter.
        assert!(
            lead > 5.0,
            "{origin} -> {destination} lead is only {lead:.1} mi"
        );
    }
}

// -- the drive -------------------------------------------------------------------------

/// Roll forward at a pinned speed, running the REAL frame, until `stop` says
/// so. Returns whether it stopped for that reason rather than running out.
fn roll(
    harness: &mut PlaytestHarness,
    speed_mph: f64,
    frames: usize,
    mut stop: impl FnMut(&mut PlaytestHarness) -> bool,
) -> bool {
    for _ in 0..frames {
        harness.advance_frame_clock();
        harness.with_drive(|drive, ctx| {
            let (tank, cut_out) = {
                let specs = &drive.truck().specs;
                (specs.fuel_tank_gal, specs.air_governor_cut_out_psi)
            };
            drive.truck_mut().fuel_gal = tank;
            drive.truck_mut().set_air_pressure_psi(cut_out);
            drive.truck_mut().parking_brake = false;
            drive.truck_mut().grade = 0.0;
            // Pinned rather than driven: this test is about WHERE the lines
            // land, and a truck that slows for a hill covers a different
            // stretch of road every time the map changes.
            drive.truck_mut().velocity_mps = speed_mph / MPH_PER_MPS;
            drive.update_frame(ctx, DT);
        });
        if stop(harness) {
            return true;
        }
    }
    false
}

fn said(harness: &PlaytestHarness, needle: &str) -> bool {
    harness
        .transcript()
        .iter()
        .any(|line| line.to_lowercase().contains(needle))
}

/// Start where the finder says, drive forward, and read what was heard.
fn drive_the_finder(origin: &str, destination: &str) -> (PlaytestHarness, Hit, f64) {
    let opts = destination_options();
    let hit = find_one(origin, destination)
        .unwrap_or_else(|| panic!("no delivery exit found for {origin} -> {destination}"));
    let mut harness = PlaytestHarness::new();
    let start_mi = harness.start_road_feature(&hit, &opts);
    harness.with_drive(|drive, _| {
        drive.tutorial = None;
        drive.trip.set_patrols(Vec::new());
        drive.truck_mut().transmission.automatic = true;
    });
    (harness, hit, start_mi)
}

#[test]
fn the_finder_starts_before_the_destination_exit_call_and_reaches_it() {
    let (mut harness, hit, start_mi) = drive_the_finder("Chicago", "Indianapolis");
    assert!(
        start_mi < hit.at_mi,
        "started at {start_mi:.1}, exit at {:.1}",
        hit.at_mi
    );

    // Nothing has been said about the exit yet: the whole point of the lead
    // is that the driver hears the approach OPEN rather than arriving in the
    // middle of it.
    let announced_at_start = harness.read_drive(|d| !d.destination_exit_announced_key.is_empty());
    assert!(!announced_at_start, "{}", harness.transcript_text());
    assert!(!said(&harness, "destination exit"));

    let reached = roll(&mut harness, 62.0, 200_000, |h| {
        h.read_drive(|d| !d.destination_exit_announced_key.is_empty())
    });
    assert!(
        reached,
        "the drive never reached the destination-exit call\n{}",
        harness.transcript_text()
    );
    assert!(
        said(&harness, "destination exit"),
        "{}",
        harness.transcript_text()
    );
    // The line names the exit and how far off it is, not a bare heading.
    assert!(
        said(&harness, "in ") && said(&harness, "destination exit"),
        "{}",
        harness.transcript_text()
    );
}

#[test]
fn blowing_past_the_exit_loops_back() {
    let (mut harness, _hit, _start_mi) = drive_the_finder("Chicago", "Indianapolis");
    // Never press X: the exit goes by unanswered, which is the case both
    // reported defects were driven from.
    let looped = roll(&mut harness, 62.0, 400_000, |h| {
        h.read_drive(|d| d.missed_destination_exit_said)
    });
    assert!(
        looped,
        "driving past the exit never produced the loop-back\n{}",
        harness.transcript_text()
    );
    assert!(
        said(&harness, "destination exit"),
        "the call was skipped entirely\n{}",
        harness.transcript_text()
    );
    assert!(
        said(&harness, "safe turnaround"),
        "the miss did not name the loop-back\n{}",
        harness.transcript_text()
    );
    // The loop-back puts the exit ahead again rather than stranding the trip
    // at the end of the route.
    let (position, total) = harness.read_drive(|d| (d.trip.position_mi, d.trip.total_miles()));
    assert!(
        position < total - 1.0,
        "the loop-back left the truck at {position:.1} of {total:.0}"
    );
}

#[test]
fn the_miss_names_the_city_not_its_map_key() {
    // `build_driving` fills in the job's spoken names; without them the miss
    // line reads out the slug -- "in hattiesburg_ms_us" -- and an owner
    // hearing that would file it as a fresh bug.
    let (mut harness, _hit, _start_mi) = drive_the_finder("jackson_ms_us", "hattiesburg_ms_us");
    let looped = roll(&mut harness, 55.0, 400_000, |h| {
        h.read_drive(|d| d.missed_destination_exit_said)
    });
    assert!(
        looped,
        "the Hattiesburg approach never missed its exit\n{}",
        harness.transcript_text()
    );
    let text = harness.transcript_text();
    assert!(
        !text.contains("hattiesburg_ms_us"),
        "the map key was spoken:\n{text}"
    );
    assert!(
        text.to_lowercase().contains("hattiesburg"),
        "the city was never named:\n{text}"
    );
}
