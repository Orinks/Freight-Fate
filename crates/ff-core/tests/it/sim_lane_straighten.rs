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
fn without_it_the_heading_carries_the_truck_off() {
    let mut lane = pointing_off();
    run(&mut lane, 2.0);
    assert!(lane.yaw_rad.abs() > 0.05, "heading {}", lane.yaw_rad);
    assert_eq!(
        lane.lane, 1,
        "the heading should carry it into the left lane"
    );
}
