//! The truck's motion runs on the clock that moves it, so a game mile costs
//! and pays the same at any pacing (flight, 2026-09-22).

use super::*;

const DT: f64 = 1.0 / 60.0;
const FT_PER_MI: f64 = 5280.0;

/// Roll a truck with the engine off from `start_mph` over `grade` until it
/// is down to `stop_mph`, at `pace` game seconds per real second, advancing
/// the road the way `Trip::update` does. Returns the miles covered.
fn coast_miles(pace: f64, grade: f64, start_mph: f64, stop_mph: f64) -> f64 {
    let mut truck = TruckState {
        grade,
        velocity_mps: start_mph / MPS_TO_MPH,
        fuel_burn_mult: pace,
        ..Default::default()
    };
    let mut miles = 0.0;
    for _ in 0..((3600.0 / DT) as usize) {
        truck.update(DT);
        miles += truck.velocity_mps * DT * pace / 1609.344;
        if truck.speed_mph() <= stop_mph {
            break;
        }
    }
    miles
}

#[test]
fn a_coast_covers_the_same_road_at_every_pace() {
    // On the real clock a standard-pace truck coasted twenty times as far,
    // because drag and rolling resistance had a twentieth of the time per
    // mile to act.
    let real = coast_miles(1.0, 0.0, 60.0, 30.0);
    assert!(real > 0.2, "the truck has to actually roll: {real:.3} mi");
    for pace in [4.0, 10.0, 20.0, 40.0] {
        let paced = coast_miles(pace, 0.0, 60.0, 30.0);
        assert!(
            (paced - real).abs() * FT_PER_MI < 60.0,
            "{pace}x coasted {paced:.3} mi where real time coasts {real:.3}"
        );
    }
}

#[test]
fn a_downhill_pays_the_same_speed_at_every_pace() {
    // The trick: build speed down a hill in real time, where gravity had the
    // whole mile to work, then spend it on the flat at standard. Gravity
    // pays per mile now, whatever the clock.
    let speed_after = |pace: f64| {
        let mut truck = TruckState {
            grade: -0.04,
            velocity_mps: 30.0 / MPS_TO_MPH,
            fuel_burn_mult: pace,
            ..Default::default()
        };
        let mut miles = 0.0;
        while miles < 1.0 {
            truck.update(DT);
            miles += truck.velocity_mps * DT * pace / 1609.344;
        }
        truck.speed_mph()
    };
    let real = speed_after(1.0);
    assert!(real > 35.0, "the hill has to actually pay: {real:.1} mph");
    let standard = speed_after(20.0);
    assert!(
        (standard - real).abs() < 1.5,
        "a mile of 4 percent paid {standard:.1} mph at 20x and {real:.1} in real time"
    );
}
