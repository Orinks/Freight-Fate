//! NPC heavy trucks are governed like real ones (port of
//! `tests/test_traffic_bubble.py`).

use ff_core::pyrandom::PyRandom;
use ff_core::sim::traffic_manager::{TrafficManager, GOVERNED_CLASSES, GOVERNED_TRUCK_BAND_MPH};

#[test]
fn test_a_semi_out_there_is_governed_like_a_real_one() {
    // Speeds are drawn from the POSTED limit, which is right for cars; applied
    // to a semi it put one at 75 on a 70 road. ATRI's Operational Costs survey
    // finds ~85 percent of fleets running limiters, most commonly at 65
    // (Brandon, 2026-08-21).
    let mut rng = PyRandom::new_from_i64(11);
    let top = GOVERNED_TRUCK_BAND_MPH.1;
    for limit in [65.0, 70.0, 75.0, 80.0] {
        for intent in ["cruising", "passing", "following"] {
            for vehicle_class in GOVERNED_CLASSES {
                for _ in 0..60 {
                    let speed =
                        TrafficManager::intent_speed(intent, limit, &mut rng, vehicle_class);
                    assert!(speed <= top, "{vehicle_class} {intent} {limit} {speed}");
                }
            }
        }
    }
    // A car is untouched: it still runs the posted number and then some.
    let fast: Vec<f64> = (0..60)
        .map(|_| TrafficManager::intent_speed("passing", 75.0, &mut rng, "car"))
        .collect();
    assert!(fast.iter().cloned().fold(f64::MIN, f64::max) > top);
    // And the governor is a BAND, not one number.
    let governed: Vec<f64> = (0..200)
        .map(|_| TrafficManager::intent_speed("cruising", 80.0, &mut rng, "semi"))
        .collect();
    let lo = governed.iter().cloned().fold(f64::MAX, f64::min);
    let hi = governed.iter().cloned().fold(f64::MIN, f64::max);
    assert!(lo >= GOVERNED_TRUCK_BAND_MPH.0);
    assert!(hi - lo > 2.0);
}
