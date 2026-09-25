//! The exit lane is the deceleration lane (owner's drive, I-70 East into
//! Denver West, 2026-09-24). On the approach a driver moves to the rightmost
//! travel lane and stays centred there; the exit lane opens beside it at the
//! taper, just ahead of the gore, and that is the one place the cab asks for a
//! steer into it. The old model was a lateral offset held inside the right
//! lane for miles: the owner, already in the right lane, was told to steer
//! right again and again, pushed toward the shoulder, overcorrected into the
//! left lane, and came back onto the semi he had been following.
//!
//! Every case runs on a bench road with one invented truck stop, driven frame
//! by frame through the real lane model with partial lane keeping.

use ff_core::sim::traffic_manager::TrafficVehicle;
use ff_core::sim::trip_models::RoadStop;
use freight_fate::playtest::harness::{PlaytestHarness, StartDelivery};
use freight_fate::states::base::{Key, Mods};
use freight_fate::states::driving_core::{EXIT_COMMIT_WINDOW_MI, EXIT_TAPER_MI};

use crate::transcript_cruise_support::{bench_road, MPS_PER_MPH};

const DT: f64 = 1.0 / 30.0;
const STOP_MI: f64 = 40.0;

/// A truck at 60 on cruise in lane `lane`, `ahead_mi` short of a truck stop
/// on a bench road posted 65, with lane keeping `mode`. Not yet signalled.
fn rig(mode: &str, lane: i64, ahead_mi: f64) -> (PlaytestHarness, RoadStop) {
    let mut harness = PlaytestHarness::new();
    harness.start_delivery(StartDelivery::named("Exit Lane"));
    harness.app.ctx.settings.lane_keeping = mode.to_string();
    harness.app.ctx.settings.automatic_transmission = true;
    harness.with_drive(|d, _| {
        d.departure_checked = true;
        bench_road(d, 65.0, 0.0, 1.0);
        d.truck_mut().set_air_ready(false);
    });
    harness.press_key(Key::E, None); // engine on
    let mut stop = RoadStop::new("Prairie Travel Center", STOP_MI, "truck_stop");
    stop.actions = vec!["park".to_string(), "fuel".to_string()];
    stop.parking = "confirmed".to_string();
    stop.exit_label = "exit 42".to_string();
    let staged = stop.clone();
    harness.with_drive(move |d, _| {
        d.trip.stops = vec![staged.clone()];
        d.truck_mut().transmission.gear = 10;
        d.truck_mut().velocity_mps = 60.0 * MPS_PER_MPH;
        d.trip.position_mi = staged.at_mi - ahead_mi;
        d.lane.recentre(lane);
    });
    harness.press_key(Key::K, None); // cruise at 60
    frame(&mut harness);
    harness.clear_speech();
    (harness, stop)
}

fn frame(harness: &mut PlaytestHarness) {
    harness.advance_clock(DT);
    harness.with_drive(|d, ctx| d.update_frame(ctx, DT));
}

fn steer(harness: &mut PlaytestHarness, key: Option<Key>) {
    for k in [Key::Left, Key::Right] {
        if Some(k) == key {
            harness.app.ctx.input.press(k, Mods::NONE);
        } else {
            harness.app.ctx.input.release(k, Mods::NONE);
        }
    }
}

fn heard(harness: &PlaytestHarness) -> Vec<String> {
    harness.app.speech().lines()
}

fn count(harness: &PlaytestHarness, needle: &str) -> usize {
    heard(harness)
        .iter()
        .filter(|line| line.contains(needle))
        .count()
}

/// Every lane instruction the cab gave, word for word.
fn lane_instructions(harness: &PlaytestHarness) -> Vec<String> {
    heard(harness)
        .into_iter()
        .filter(|line| {
            line.contains("right lane") || line.contains("exit lane") || line.contains("Steer")
        })
        .collect()
}

/// Frames until `until` holds, or panic with the transcript.
fn drive_until(
    harness: &mut PlaytestHarness,
    what: &str,
    until: impl Fn(&PlaytestHarness) -> bool,
) {
    for _ in 0..(30 * 60 * 5) {
        if until(harness) {
            return;
        }
        frame(harness);
    }
    panic!("never {what}\n{}", harness.transcript_text());
}

/// The L key's neighbour clause: everything after "In the right lane, ...".
fn neighbour_readout(harness: &mut PlaytestHarness) -> String {
    let text = harness.with_drive(|d, _| d.lane_status_text());
    text.split_once(". ")
        .map(|(_, rest)| rest.to_string())
        .unwrap_or_default()
}

#[test]
fn already_in_the_right_lane_hears_one_steer_at_the_taper_and_takes_the_exit() {
    let (mut harness, stop) = rig("partial", 0, 2.3);
    harness.press_key(Key::X, None);
    assert!(heard(&harness).iter().any(|l| l.contains("Signal on")));

    // The whole approach, the two-mile, one-mile and half-mile anchors
    // included: no lane instruction, because the truck is where it belongs.
    drive_until(&mut harness, "reached the taper", |h| {
        h.read_drive(|d| d.lane.exit_lane_open)
    });
    let position = harness.read_drive(|d| d.trip.position_mi);
    assert!(
        position >= stop.at_mi - EXIT_TAPER_MI - 0.01,
        "the exit lane opened {:.2} mi early",
        stop.at_mi - position
    );
    assert_eq!(
        count(&harness, "in half a mile"),
        1,
        "{:?}",
        heard(&harness)
    );
    assert_eq!(
        lane_instructions(&harness),
        vec!["Exit lane opening. Steer right into it.".to_string()],
        "{:?}",
        heard(&harness)
    );

    // Right into it, and the truck is on the ramp: clean, with no shoulder.
    steer(&mut harness, Some(Key::Right));
    drive_until(&mut harness, "took the exit", |h| {
        h.read_drive(|d| d.ramp_mi.is_some())
    });
    steer(&mut harness, None);
    let position = harness.read_drive(|d| d.trip.position_mi);
    assert!(position <= stop.at_mi + EXIT_COMMIT_WINDOW_MI);
    assert!(heard(&harness)
        .iter()
        .any(|l| l.contains("You take exit 42")));
    assert_eq!(count(&harness, "Exit lane opening"), 1);
    assert_eq!(count(&harness, "sideswiped"), 0, "{:?}", heard(&harness));
    assert_eq!(count(&harness, "Off the road"), 0, "{:?}", heard(&harness));
    assert_eq!(count(&harness, "missed"), 0, "{:?}", heard(&harness));
}

#[test]
fn out_of_the_right_lane_is_asked_to_move_right_until_it_is_there() {
    let (mut harness, _stop) = rig("partial", 1, 2.3);
    harness.press_key(Key::X, None);
    let arming = heard(&harness)
        .into_iter()
        .find(|l| l.contains("Signal on"))
        .expect("the signal line");
    assert!(arming.contains("Move to the right lane."), "{arming}");

    // The two-mile anchor still owes the move.
    drive_until(&mut harness, "heard the two-mile anchor", |h| {
        count(h, "in 2 miles") > 0
    });
    let two_mile = heard(&harness)
        .into_iter()
        .find(|l| l.contains("in 2 miles"))
        .unwrap_or_default();
    assert!(two_mile.contains("Move to the right lane."), "{two_mile}");

    // Across into the right lane, then centred there.
    steer(&mut harness, Some(Key::Right));
    drive_until(&mut harness, "reached the right lane", |h| {
        h.read_drive(|d| d.lane.lane == 0)
    });
    steer(&mut harness, None);
    harness.clear_speech();

    // From here the anchors name the exit and nothing else, until the taper.
    drive_until(&mut harness, "reached the taper", |h| {
        h.read_drive(|d| d.lane.exit_lane_open)
    });
    assert!(count(&harness, "in 1 mile") > 0, "{:?}", heard(&harness));
    assert_eq!(
        lane_instructions(&harness),
        vec!["Exit lane opening. Steer right into it.".to_string()],
        "{:?}",
        heard(&harness)
    );
}

#[test]
fn right_lane_traffic_is_never_in_the_exit_lane() {
    // The mirror check calls any vehicle within a third of a mile of a lane
    // change a sideswipe. The exit lane is an auxiliary lane with no through
    // traffic, so a car close behind in the right lane is not in it.
    let (mut harness, _stop) = rig("partial", 0, 0.3);
    harness.press_key(Key::X, None);
    harness.with_drive(|d, _| {
        let at = d.trip.position_mi - 0.04;
        let mph = d.truck().speed_mph();
        d.trip.set_npc_vehicles(vec![TrafficVehicle::new(
            "npc:behind",
            at,
            mph,
            mph,
            0,
            "cruising",
            "semi",
        )
        .with_lane(0)]);
    });
    drive_until(&mut harness, "reached the taper", |h| {
        h.read_drive(|d| d.lane.exit_lane_open)
    });
    steer(&mut harness, Some(Key::Right));
    drive_until(&mut harness, "took the exit", |h| {
        let (lanes, count) = h.read_drive(|d| {
            (
                d.trip
                    .traffic_manager
                    .vehicles
                    .iter()
                    .map(|v| v.lane)
                    .collect::<Vec<_>>(),
                d.lane.lane_count,
            )
        });
        assert!(
            lanes.iter().all(|lane| (0..count).contains(lane)),
            "traffic outside the travel lanes: {lanes:?} of {count}"
        );
        h.read_drive(|d| d.ramp_mi.is_some())
    });
    steer(&mut harness, None);
    assert_eq!(count(&harness, "sideswiped"), 0, "{:?}", heard(&harness));
}

#[test]
fn never_steering_in_misses_the_exit_at_the_end_of_the_gore_window() {
    let (mut harness, stop) = rig("partial", 0, 0.3);
    harness.press_key(Key::X, None);
    drive_until(&mut harness, "settled the exit", |h| {
        h.read_drive(|d| d.exit_stop.is_none())
    });
    let position = harness.read_drive(|d| d.trip.position_mi);
    assert!(position >= stop.at_mi + EXIT_COMMIT_WINDOW_MI, "{position}");
    assert!(harness.read_drive(|d| d.ramp_mi.is_none()));
    assert_eq!(count(&harness, "You were not in the exit lane"), 1);
}

#[test]
fn the_lane_readout_holds_steady_where_the_lane_count_does() {
    // The owner heard "Middle lane open" and "Left lane open" by turns while
    // the truck sat in the right lane. The log settled it: a real lane drop,
    // said once, and older lines replayed from the message history. Pinned
    // here so the exit lane opening beside the truck never renumbers the
    // travel lanes either.
    let (mut harness, _stop) = rig("partial", 0, 1.2);
    harness.press_key(Key::X, None);
    let first = neighbour_readout(&mut harness);
    assert!(first.ends_with("lane open."), "{first}");
    let mut exit_lane_seen = false;
    for step in 0..(30 * 90) {
        if harness.read_drive(|d| d.ramp_mi.is_some()) {
            break;
        }
        let open = harness.read_drive(|d| d.lane.exit_lane_open);
        exit_lane_seen |= open;
        steer(&mut harness, open.then_some(Key::Right));
        if step % 15 == 0 {
            assert_eq!(neighbour_readout(&mut harness), first);
        }
        frame(&mut harness);
    }
    assert!(exit_lane_seen);
}
