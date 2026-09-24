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

/// Floor a loaded automatic from rest to `to_mph` on the flat at `pace`.
/// Returns (upshifts, downshifts, miles covered).
fn pull_away(pace: f64, to_mph: f64) -> (u32, u32, f64) {
    let mut truck = TruckState {
        fuel_burn_mult: pace,
        cargo_kg: 18_000.0,
        ..Default::default()
    };
    truck.transmission.automatic = true;
    truck.set_air_ready(false);
    truck.start_engine();
    truck.throttle = 1.0;
    let (mut up, mut down, mut miles) = (0, 0, 0.0);
    for _ in 0..((600.0 / DT) as usize) {
        let before = truck.transmission.gear;
        if let Some(gear) = truck.auto_shift() {
            if gear > before {
                up += 1;
            } else if gear < before {
                down += 1;
            }
        }
        truck.update(DT);
        miles += truck.velocity_mps * DT * pace / 1609.344;
        if truck.speed_mph() >= to_mph {
            break;
        }
    }
    assert!(
        truck.speed_mph() >= to_mph,
        "{pace}x never reached {to_mph} mph"
    );
    (up, down, miles)
}

#[test]
fn a_launch_shifts_the_same_gears_at_every_pace() {
    // The torque interruption ran on the real clock while the truck moved on
    // the game clock, so at 14x a quarter-second upshift left the truck
    // unpowered for three and a half game seconds. It bogged, the box
    // downshifted -- a full second, fourteen game seconds -- and hunted:
    // twenty-four shifts from 9 to 46 mph in eight real seconds (agent drive,
    // US-12, 2026-09-23).
    let (real_up, real_down, real_miles) = pull_away(1.0, 46.0);
    assert_eq!(real_down, 0, "the real-time launch must not hunt");
    for pace in [4.0, 14.0, 20.0] {
        let (up, down, miles) = pull_away(pace, 46.0);
        assert_eq!(down, 0, "{pace}x hunted: {up} up, {down} down");
        assert!(
            up <= real_up + 1,
            "{pace}x took {up} upshifts where real time takes {real_up}"
        );
        assert!(
            (miles - real_miles).abs() < real_miles * 0.1,
            "{pace}x needed {miles:.3} mi where real time needs {real_miles:.3}"
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
