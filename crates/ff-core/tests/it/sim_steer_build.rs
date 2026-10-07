//! The driver's steer asks for a heading (owner, 2026-09-30): a held key
//! angles the truck over at most enough to cross a lane in LANE_CHANGE_S,
//! letting go squares it up, a tap is a nudge, a stick asks for the share it
//! is pushed -- and a hold toward a called turn follows the road.

use ff_core::sim::lane::{
    LaneKeeping, RoadConditions, FPS_PER_MPH, HALF_LANE_FT, LANE_CHANGE_S, LANE_WIDTH, MPH_PER_MPS,
};

const DT: f64 = 1.0 / 60.0;

fn frames(seconds: f64) -> usize {
    (seconds / DT).round() as usize
}

/// The heading that crosses a lane in LANE_CHANGE_S at `mph`.
fn lane_change_heading(mph: f64) -> f64 {
    (LANE_WIDTH * HALF_LANE_FT / LANE_CHANGE_S / (mph * FPS_PER_MPH)).asin()
}

fn drive(lane: &mut LaneKeeping, mph: f64, key: i8, stick: f64, s: f64) {
    for _ in 0..frames(s) {
        lane.steer_input(key, stick);
        lane.update(
            DT,
            mph / MPH_PER_MPS,
            RoadConditions::default(),
            "off",
            false,
        );
    }
}

#[test]
fn a_held_key_angles_the_truck_no_further_than_a_lane_in_its_time() {
    // Two seconds at forty once built eleven degrees and took the truck
    // through the next lane into the median.
    for mph in [15.0, 40.0, 65.0] {
        let mut lane = LaneKeeping::new(Some(1));
        let mut steepest: f64 = 0.0;
        for _ in 0..frames(5.0) {
            drive(&mut lane, mph, 1, 0.0, DT);
            steepest = steepest.max(lane.yaw_rad);
        }
        let heading = lane_change_heading(mph);
        assert!(
            steepest <= heading * 1.05 && (lane.yaw_rad - heading).abs() < 0.002,
            "{mph} mph: held at {}, peaked {steepest}, lane-change heading {heading}",
            lane.yaw_rad
        );
    }
}

#[test]
fn letting_go_after_a_long_hold_stops_within_the_lane() {
    let mut lane = LaneKeeping::new(Some(2));
    drive(&mut lane, 40.0, -1, 0.0, 2.0);
    let released_at = lane.offset;
    drive(&mut lane, 40.0, 0, 0.0, 1.5);
    assert!(lane.yaw_rad.abs() < 0.002, "still angled: {}", lane.yaw_rad);
    // Offset runs across lane lines, so read it off the lane count too.
    let carried = (released_at - lane.offset).abs();
    assert!(
        carried < 0.5,
        "carried {carried} of a half lane past the release"
    );
}

#[test]
fn a_tap_is_a_nudge() {
    // The median of 44 taps on the owner's keyboard, 2026-09-30.
    let tap = 0.119;
    let mut tapped = LaneKeeping::new(Some(3));
    let mut untouched = LaneKeeping::new(Some(3));
    drive(&mut tapped, 65.0, 1, 0.0, tap);
    drive(&mut untouched, 65.0, 0, 0.0, tap);
    drive(&mut tapped, 65.0, 0, 0.0, 2.0);
    drive(&mut untouched, 65.0, 0, 0.0, 2.0);
    let moved = tapped.offset - untouched.offset;
    assert!(
        (0.0..0.1).contains(&moved),
        "a tap moved the truck {moved} of a half lane"
    );
}

#[test]
fn a_stick_asks_for_the_share_of_the_heading_it_is_pushed() {
    for push in [0.25, 0.5, 1.0] {
        let mut lane = LaneKeeping::new(Some(4));
        drive(&mut lane, 65.0, 0, push, 5.0);
        let wanted = push * lane_change_heading(65.0);
        assert!(
            (lane.yaw_rad - wanted).abs() < 0.002,
            "stick {push}: {} against {wanted}",
            lane.yaw_rad
        );
    }
}

// -- a hold toward a signed turn follows the road -------------------------------------

const BEND_MPH: f64 = 40.0;

/// A left-hander the truck can hold at forty: 600 feet, 0.18 g.
const LEFT_BEND: f64 = -1.0 / 600.0;

fn bend_step(lane: &mut LaneKeeping, curvature: f64, turn_assist: bool) {
    let road = RoadConditions {
        curvature,
        ..RoadConditions::default()
    };
    lane.update(DT, BEND_MPH / MPH_PER_MPS, road, "off", turn_assist);
}

fn hold(lane: &mut LaneKeeping, key: i8, stick: f64, curvature: f64, turn_assist: bool, s: f64) {
    for _ in 0..frames(s) {
        lane.steer_input(key, stick);
        bend_step(lane, curvature, turn_assist);
    }
}

#[test]
fn a_hold_toward_the_turn_goes_straight_until_it_begins_then_follows_it() {
    // The owner held right into a right turn and left the road
    // (2026-09-30): a held key was twice the wheel the corner wanted.
    let mut lane = LaneKeeping::new(Some(5));
    lane.turn_in_play = -1.0;
    // Held from the call, before the road bends: straight on, in lane.
    hold(&mut lane, -1, 0.0, 0.0, false, 2.0);
    in_lane(&lane, "turned early");
    // Through the bend: round with the road, not inside it.
    hold(&mut lane, -1, 0.0, LEFT_BEND, false, 4.0);
    in_lane(&lane, "left the road's line");
    // Out of it, still held: straight again.
    lane.turn_in_play = 0.0;
    hold(&mut lane, -1, 0.0, 0.0, false, 2.0);
    in_lane(&lane, "kept turning");
    // Let go and pressed again, it is a steer key once more.
    hold(&mut lane, 0, 0.0, 0.0, false, 0.1);
    hold(&mut lane, -1, 0.0, 0.0, false, 0.5);
    assert!(
        lane.yaw_rad < -0.001,
        "the new press never steered: {}",
        lane.yaw_rad
    );
}

#[test]
fn steering_away_from_the_turn_still_steers() {
    let mut lane = LaneKeeping::new(Some(6));
    lane.turn_in_play = -1.0;
    hold(&mut lane, 1, 0.0, 0.0, false, 0.5);
    assert!(
        lane.yaw_rad > 0.001,
        "a right press before a left-hander: {}",
        lane.yaw_rad
    );
}

#[test]
fn a_stick_pushed_toward_the_turn_follows_it_too() {
    let mut lane = LaneKeeping::new(Some(7));
    lane.turn_in_play = -1.0;
    hold(&mut lane, 0, -0.6, LEFT_BEND, false, 4.0);
    in_lane(&lane, "the stick into the bend");
}

#[test]
fn with_curve_assistance_on_a_hold_adds_nothing_on_top() {
    let mut lane = LaneKeeping::new(Some(8));
    lane.turn_in_play = -1.0;
    hold(&mut lane, -1, 0.0, LEFT_BEND, true, 4.0);
    in_lane(&lane, "doubled the steering");
}

#[test]
fn letting_go_squares_the_truck_with_the_road() {
    // Owner, 2026-09-30: unwinding after a corner crossed into the next lane.
    // There is no wheel to unwind now: let go and the heading comes out.
    let mut lane = LaneKeeping::new(Some(9));
    hold(&mut lane, 1, 0.0, 0.0, false, 0.5);
    assert!(lane.yaw_rad > 0.001, "never steered: {}", lane.yaw_rad);
    hold(&mut lane, 0, 0.0, 0.0, false, 1.0);
    assert!(lane.yaw_rad.abs() < 0.001, "still angled: {}", lane.yaw_rad);
}

/// Following the road and keeping the lane: pointing down it, near the
/// middle.
fn in_lane(lane: &LaneKeeping, what: &str) {
    assert!(
        lane.yaw_rad.abs() < 0.01 && lane.offset.abs() < 0.1,
        "{what}: heading {}, offset {}",
        lane.yaw_rad,
        lane.offset
    );
}
