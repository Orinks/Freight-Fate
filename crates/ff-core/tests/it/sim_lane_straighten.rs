//! The straighten-up key: held, it steers out the heading and nothing else.

use ff_core::sim::lane::{LaneKeeping, RoadConditions};

const DT: f64 = 0.05;
const MPS: f64 = 25.0;

/// A truck pointing well off the road, a little right of lane centre.
fn pointing_off() -> LaneKeeping {
    let mut lane = LaneKeeping::new(Some(7));
    lane.offset = 0.3;
    lane.yaw_rad = -0.08;
    lane
}

fn run(lane: &mut LaneKeeping, seconds: f64) {
    for _ in 0..(seconds / DT) as usize {
        lane.update(DT, MPS, RoadConditions::default(), "off", false);
    }
}

#[test]
fn holding_it_points_the_truck_down_the_road() {
    let mut lane = pointing_off();
    lane.straighten = true;
    run(&mut lane, 2.0);
    assert!(lane.yaw_rad.abs() < 0.01, "heading {}", lane.yaw_rad);
    // It is not lane keeping: where the truck ended up in the lane stays the
    // driver's to fix, so it has not been walked back to the old spot.
    assert!(lane.offset < 0.3 - 0.1, "offset {}", lane.offset);
    assert_eq!(lane.lane, 0, "offset {}", lane.offset);
}

#[test]
fn letting_go_does_the_same_and_only_a_held_key_keeps_the_heading() {
    // Since 2026-09-30 letting go straightens too: a heading nobody can see
    // outlived every key and took the owner off the road three drives running.
    let mut lane = pointing_off();
    run(&mut lane, 2.0);
    assert!(lane.yaw_rad.abs() < 0.01, "heading {}", lane.yaw_rad);
    assert_eq!(lane.lane, 0, "offset {}", lane.offset);
    // A steer held that way keeps a heading -- the one that crosses a lane in
    // LANE_CHANGE_S -- and carries the truck over.
    let mut lane = pointing_off();
    for _ in 0..(3.0 / DT) as usize {
        lane.steering = -1.0;
        lane.update(DT, MPS, RoadConditions::default(), "off", false);
    }
    assert!(lane.yaw_rad.abs() > 0.05, "heading {}", lane.yaw_rad);
    assert_eq!(
        lane.lane, 1,
        "the held heading should carry it into the left lane"
    );
}
