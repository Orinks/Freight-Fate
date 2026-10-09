//! Company in the other lanes of a busy freeway.
//!
//! A bubble cell carries at most one vehicle, which on a two-lane road is
//! about right and on a busy interstate is a tenth of what the road's own
//! count says is there: the cab heard a freeway with nobody on it (owner
//! drive, 2026-10-09). On a freeway cell that drew somebody, each lane left
//! of the right lane that the first vehicle is not already in gets its own
//! draw at the same density. The right lane is left alone on purpose: it is
//! the truck's lane, and a car placed in front of it is a slowdown the
//! driver has to answer, where one in the lane beside is company.

use super::{choose, TrafficManager, TrafficVehicle, EXIT_AFTER_MAX_MI, EXIT_AFTER_MIN_MI};
use super::{NO_SPAWN_AHEAD_MI, NO_SPAWN_BEHIND_MI, SPAWN_CELL_MI};
use crate::pyrandom::PyRandom;

impl TrafficManager {
    /// The vehicles beside the one `replenish` put in `cell`, drawn from
    /// the same `rng` after it so the first vehicle is placed exactly as
    /// before. Empty off a freeway.
    pub(super) fn lanes_beside(
        &self,
        cell: i64,
        density: f64,
        taken_lane: i64,
        position_mi: f64,
        rng: &mut PyRandom,
    ) -> Vec<TrafficVehicle> {
        let cell_mid = (cell as f64 + 0.5) * SPAWN_CELL_MI;
        if self.freeway_presence_at(cell_mid) <= 0.0 {
            return Vec::new();
        }
        let lanes = self.lane_count_at(cell_mid);
        let mut beside = Vec::new();
        for lane in 1..lanes {
            if lane == taken_lane || rng.random() > density {
                continue;
            }
            let mile = cell as f64 * SPAWN_CELL_MI + rng.uniform(0.0, SPAWN_CELL_MI);
            if -NO_SPAWN_BEHIND_MI < mile - position_mi && mile - position_mi < NO_SPAWN_AHEAD_MI {
                continue;
            }
            let Some(leg) = self.leg_at(mile) else {
                continue;
            };
            // The left lanes carry the faster traffic.
            let intent = choose(rng, &["passing", "cruising"], &[2.0, 1.0]);
            let vehicle_class = choose(
                rng,
                &["car", "box truck", "semi", "service vehicle"],
                &[5.0, 1.4, 2.0, 0.3],
            );
            let (limit_offset, governor) = Self::intent_speed_draw(intent, rng, vehicle_class);
            let rush_slowdown = if self.rush_hour_traffic_bias(leg) != 0.0 {
                rng.uniform(4.0, 10.0)
            } else {
                0.0
            };
            let speed = self.road_speed_mph(mile, limit_offset, governor, rush_slowdown);
            let exit_at = mile + rng.uniform(EXIT_AFTER_MIN_MI, EXIT_AFTER_MAX_MI);
            beside.push(
                TrafficVehicle::new(
                    &format!("bubble:{cell}:{lane}"),
                    mile,
                    speed,
                    speed,
                    -lane,
                    intent,
                    vehicle_class,
                )
                .with_lane(lane)
                .with_exit_at(Some(exit_at))
                .with_speed_draw(limit_offset, governor, rush_slowdown),
            );
        }
        beside
    }
}
