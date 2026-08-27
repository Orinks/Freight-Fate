//! Acceleration and deceleration lanes, ramp design speeds and a loaded
//! truck's merge speed (the ramp half of `freight_fate/sim/trip_models.py`).

use crate::pyfmt::round_py;
use crate::sim::vehicle::TruckState;

// -- Getting onto the highway: the acceleration lane -------------------------
// HOW LONG IS THE LANE comes from AASHTO Green Book Table 10-3 (TxDOT RDM
// Table 3-13): feet of acceleration lane from a STOP by design speed. HOW
// FAST THE TRUCK GETS comes from Long, TRR 1737 (2000), for a loaded 200
// lb/hp WB-15. Keeping both is the point: the lane is sized for a car and the
// truck is a truck.
pub const ACCELERATION_LANE_FT: [(f64, f64); 7] = [
    (40.0, 360.0),
    (50.0, 720.0),
    (55.0, 960.0),
    (60.0, 1200.0),
    (65.0, 1410.0),
    (70.0, 1620.0),
    (75.0, 1790.0),
];

/// Long's model: a = ALPHA - BETA * v, feet and feet per second.
pub const TRUCK_ACCEL_ALPHA_FPS2: f64 = 1.90;
pub const TRUCK_ACCEL_BETA: f64 = 0.0199;
pub const GRADE_MODEL_MIN_PCT: f64 = -4.0;
pub const GRADE_MODEL_MAX_PCT: f64 = 2.0;

/// AASHTO's acceleration-lane design target: enter the mainline at 75 percent
/// of its design speed. This is the traffic-relative floor used for both the
/// assist handoff and the truthful slow-merge warning.
pub const MERGE_TRAFFIC_SPEED_SHARE: f64 = 0.75;

/// AASHTO's own grade multipliers on the lane length (TxDOT Table 3-14).
pub const ACCELERATION_LANE_GRADE_FACTOR: [(f64, f64); 4] =
    [(-3.0, 0.6), (-5.0, 0.55), (3.0, 1.5), (5.0, 2.2)];

fn interpolate_lane_ft(table: &[(f64, f64)], highway_mph: f64) -> f64 {
    // The tables are written in ascending speed order.
    let (first_speed, first_ft) = table[0];
    let (last_speed, last_ft) = table[table.len() - 1];
    if highway_mph <= first_speed {
        return first_ft;
    }
    if highway_mph >= last_speed {
        return last_ft;
    }
    let lo = table
        .iter()
        .filter(|(s, _)| *s <= highway_mph)
        .map(|(s, _)| *s)
        .fold(f64::NEG_INFINITY, f64::max);
    let hi = table
        .iter()
        .filter(|(s, _)| *s >= highway_mph)
        .map(|(s, _)| *s)
        .fold(f64::INFINITY, f64::min);
    let ft_at = |s: f64| {
        table
            .iter()
            .find(|(k, _)| *k == s)
            .map(|(_, v)| *v)
            .expect("speed is a table key")
    };
    if lo == hi {
        return ft_at(lo);
    }
    let span = (highway_mph - lo) / (hi - lo);
    ft_at(lo) + span * (ft_at(hi) - ft_at(lo))
}

/// Miles of acceleration lane an entrance at `highway_mph` really has,
/// interpolated between the table's design speeds then adjusted for grade.
pub fn acceleration_lane_mi(highway_mph: f64, grade_pct: f64) -> f64 {
    let feet = interpolate_lane_ft(&ACCELERATION_LANE_FT, highway_mph);
    let mut factor = 1.0;
    for (threshold, value) in ACCELERATION_LANE_GRADE_FACTOR {
        let downhill_enough = threshold < 0.0 && grade_pct <= threshold;
        let uphill_enough = threshold > 0.0 && grade_pct >= threshold;
        if downhill_enough || uphill_enough {
            factor = value;
        }
    }
    feet * factor / 5280.0
}

/// Traffic-relative speed at which an acceleration-lane merge is no longer a
/// materially slow join.
pub fn merge_traffic_target_mph(highway_mph: f64) -> f64 {
    highway_mph.max(0.0) * MERGE_TRAFFIC_SPEED_SHARE
}

/// What this exact truck can reach by the taper with its actual drivetrain,
/// load, transmission, wear, weather drag and grip, and the mapped grade.
///
/// The clone is an instrument only: the live truck still covers every foot
/// and gains every mile per hour through the ordinary vehicle physics.
pub fn acceleration_lane_capability_mph(truck: &TruckState, lane_mi: f64, grade: f64) -> f64 {
    const DT: f64 = 1.0 / 60.0;
    const TIMEOUT_S: f64 = 180.0;

    let mut simulated = truck.clone();
    let start_mi = simulated.odometer_mi;
    simulated.grade = grade;
    simulated.brake = 0.0;
    let mut elapsed = 0.0;
    while simulated.odometer_mi - start_mi < lane_mi.max(0.0) && elapsed < TIMEOUT_S {
        simulated.throttle = 1.0;
        simulated.auto_shift();
        simulated.update(DT);
        elapsed += DT;
    }
    simulated.speed_mph()
}

// Getting OFF is the same problem mirrored: AASHTO Green Book Table 10-5
// (TxDOT RDM Table 3-15), feet of deceleration lane by design speed.
pub const DECELERATION_LANE_FT: [(f64, f64); 8] = [
    (30.0, 235.0),
    (40.0, 315.0),
    (50.0, 435.0),
    (55.0, 480.0),
    (60.0, 530.0),
    (65.0, 570.0),
    (70.0, 615.0),
    (75.0, 660.0),
];

/// AASHTO ramp design speed as a share of the mainline: directional ramps
/// take the top of the 70-85 percent band, surface-road ramps the lower end.
pub const RAMP_DIRECTIONAL_SHARE: f64 = 0.85;
pub const RAMP_SURFACE_SHARE: f64 = 0.70;
pub const RAMP_MIN_DESIGN_MPH: f64 = 30.0;

/// Miles of deceleration lane an exit at `highway_mph` really has. The grade
/// multipliers are the acceleration table's, inverted in sense.
pub fn deceleration_lane_mi(highway_mph: f64, grade_pct: f64) -> f64 {
    let feet = interpolate_lane_ft(&DECELERATION_LANE_FT, highway_mph);
    let mut factor = 1.0;
    for (threshold, value) in ACCELERATION_LANE_GRADE_FACTOR {
        if threshold < 0.0 && grade_pct <= threshold {
            factor = 1.0 / value; // downhill: harder to shed, so more lane
        } else if threshold > 0.0 && grade_pct >= threshold {
            factor = 1.0 / value;
        }
    }
    feet * factor / 5280.0
}

/// The speed this ramp is built for, from the road it leaves.
pub fn ramp_speed_mph(highway_mph: f64, directional: bool) -> f64 {
    let share = if directional {
        RAMP_DIRECTIONAL_SHARE
    } else {
        RAMP_SURFACE_SHARE
    };
    RAMP_MIN_DESIGN_MPH.max(round_py(highway_mph * share))
}

/// Provenance travels with ramp speed so a calculated design fallback cannot
/// be mistaken for an observed advisory sign.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum RampAdvisorySpeed {
    /// A roadside value was read, but the truck target remains no faster than
    /// Freight Fate's existing conservative ramp calculation. Ordinary ramp
    /// advisory signs are generally intended for passenger vehicles.
    Observed {
        posted_mph: f64,
        truck_target_mph: f64,
    },
    Calculated {
        mph: f64,
    },
}

impl RampAdvisorySpeed {
    pub fn mph(self) -> f64 {
        match self {
            Self::Observed {
                truck_target_mph, ..
            } => truck_target_mph,
            Self::Calculated { mph } => mph,
        }
    }
}

/// What a loaded truck is really doing at the end of that lane: Long's curve
/// integrated over the lane, capped at the highway's own limit.
pub fn truck_merge_speed_mph(highway_mph: f64, entry_mph: f64, lane_mi: f64) -> f64 {
    let mut v = entry_mph.max(0.0) * 5280.0 / 3600.0; // feet per second
    let top = TRUCK_ACCEL_ALPHA_FPS2 / TRUCK_ACCEL_BETA;
    let mut remaining = lane_mi.max(0.0) * 5280.0;
    let step: f64 = 10.0;
    while remaining > 0.0 && v < top {
        let accel = TRUCK_ACCEL_ALPHA_FPS2 - TRUCK_ACCEL_BETA * v;
        if accel <= 0.0 {
            break;
        }
        // v dv = a dx
        v = (v * v + 2.0 * accel * step.min(remaining)).max(0.0).sqrt();
        remaining -= step;
    }
    highway_mph.min(v * 3600.0 / 5280.0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::trucks::truck_model_or_panic;
    use crate::sim::vehicle::{KG_PER_TON, MPS_TO_MPH};

    fn automatic_truck(model: &str, cargo_tons: f64) -> TruckState {
        let mut truck = TruckState::new(truck_model_or_panic(model).specs.clone());
        truck.engine_on = true;
        truck.transmission.automatic = true;
        // Brandon's 18 mph ramp approach was recorded in sixth at 1,412 RPM.
        // Neutral here would exercise the automatic's standing-start selector,
        // not the rolling Carlisle handoff this capability estimate models.
        truck.transmission.gear = 6;
        truck.rpm = 1412.0;
        truck.trailer_attached = true;
        truck.cargo_kg = cargo_tons * KG_PER_TON;
        truck.velocity_mps = 18.0 / MPS_TO_MPH;
        truck
    }

    #[test]
    fn merge_target_tracks_traffic_speed_instead_of_a_fixed_shortfall() {
        assert_eq!(merge_traffic_target_mph(70.0), 52.5);
        assert_eq!(merge_traffic_target_mph(55.0), 41.25);
    }

    #[test]
    fn capability_uses_the_actual_truck_and_load() {
        let lane_mi = acceleration_lane_mi(70.0, -1.1);
        let loaded =
            acceleration_lane_capability_mph(&automatic_truck("yard_mule", 25.0), lane_mi, -0.011);
        let light = acceleration_lane_capability_mph(&automatic_truck("rig", 0.0), lane_mi, -0.011);

        assert!(loaded > 18.0);
        assert!(light > loaded, "loaded={loaded:.1}, light={light:.1}");
    }
}
