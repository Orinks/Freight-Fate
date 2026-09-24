//! Can every signed bend in the game be held at the speed the cab calls out?
//!
//! Curve assistance brakes to the bend's advisory and hands the lane model the
//! wheel that tracks the bend. If the truck leaves its lane anyway the drive is
//! lost to a number the game itself just spoke, and the driver has no move that
//! helps: the assists are already doing everything they have.
//!
//! That is what an agent drive down AZ-260 into Payson hit on 2026-09-19 --
//! hands off, every assist on, at the advisory, off the pavement -- so this
//! sweeps the shipped bake rather than the one bend that happened to be
//! reported. Every mainline curve, at its own advisory, held for as long as the
//! truck is really in it.

use ff_core::data::curves::{
    advisory_side_friction, bend_bank, load, posted_advisory_mph, superelevation_at, CurveRecord,
    ADVISORY_MIN_MPH,
};
use ff_core::sim::lane::{LaneKeeping, RoadConditions, LANE_EDGE, MPH_PER_MPS};

/// How far through the bend the truck is carried, in seconds of arc.
fn seconds_in(record: &CurveRecord, mph: f64) -> f64 {
    let arc_ft = record.min_radius_ft as f64 * record.deflection_deg.to_radians();
    let fps = mph * 1.466_667;
    (arc_ft / fps.max(1.0)).clamp(1.0, 60.0)
}

/// The worst the truck sits in its lane taking `record` at `mph`, hands off.
fn offset_through(record: &CurveRecord, mph: f64) -> f64 {
    let mut lane = LaneKeeping::new(Some(11));
    let dt = 0.05;
    let speed_mps = mph / MPH_PER_MPS;
    let curvature =
        if record.direction == 'L' { -1.0 } else { 1.0 } / (record.min_radius_ft as f64).max(1.0);
    let bank = superelevation_at(record.min_radius_ft as f64, mph.max(15.0));
    let steps = (seconds_in(record, mph) / dt) as i64;
    let mut worst: f64 = 0.0;
    for _ in 0..steps {
        lane.update(
            dt,
            speed_mps,
            RoadConditions {
                curvature,
                wind: 0.0,
                grip: 1.0,
                bank,
            },
            "partial",
            true,
        );
        worst = worst.max(lane.offset.abs());
    }
    worst
}

#[test]
#[cfg_attr(ci_quick, ignore = "sweep: every mainline curve in the bake")]
fn test_every_signed_bend_is_holdable_at_its_own_advisory() {
    let mut checked = 0usize;
    let mut worst_of_all = 0.0f64;
    let mut failures: Vec<String> = Vec::new();

    for (leg, records) in load().iter() {
        for record in records.iter().filter(|r| !r.connector) {
            if record.advisory_mph <= 0 || record.min_radius_ft <= 0 {
                continue;
            }
            checked += 1;
            let worst = offset_through(record, record.advisory_mph as f64);
            worst_of_all = worst_of_all.max(worst);
            if worst >= LANE_EDGE {
                failures.push(format!(
                    "{leg} at mile {:.2}: {} ft, advisory {}, offset {worst:.2}",
                    record.start_mi, record.min_radius_ft, record.advisory_mph
                ));
            }
        }
    }

    assert!(
        checked > 1_000,
        "the curve bake did not load: {checked} rows"
    );
    assert!(
        failures.is_empty(),
        "{} of {checked} signed bends cannot be held at the speed the cab calls out.\n{}",
        failures.len(),
        failures
            .iter()
            .take(20)
            .cloned()
            .collect::<Vec<_>>()
            .join("\n")
    );
    // And the margin is real rather than the assertion scraping by: the
    // tightest bend in the country still sits inside its lane line.
    assert!(
        worst_of_all < 0.9,
        "the worst bend rides the lane line at its own advisory: {worst_of_all:.2}"
    );
}

#[test]
fn test_a_bend_taken_far_over_its_advisory_still_runs_wide() {
    // The other half of the rule, swept rather than argued: no amount of bank
    // credit may turn the advisory into a suggestion. Twenty-five over is a
    // truck that should be off the road, and the tighter the bend the sooner.
    let mut ran_wide = 0usize;
    let mut held = 0usize;
    for records in load().values() {
        for record in records
            .iter()
            .filter(|r| !r.connector && r.advisory_mph >= 25 && r.advisory_mph <= 45)
        {
            if record.min_radius_ft <= 0 {
                continue;
            }
            if offset_through(record, record.advisory_mph as f64 + 25.0) >= LANE_EDGE {
                ran_wide += 1;
            } else {
                held += 1;
            }
        }
    }
    assert!(
        ran_wide > 0,
        "no bend ran wide at 25 over; the ceiling is gone"
    );
    assert!(
        ran_wide > held,
        "only {ran_wide} of {} bends ran wide at 25 over their advisory",
        ran_wide + held
    );
}

/// The advisory formula's own terms, so the bank credit below can never be
/// read as a tuning knob: `e + f = V^2 / 15R`, with f the MUTCD ball-bank
/// criterion, is what posted every row.
#[test]
fn test_the_bank_credited_is_the_bank_the_advisory_was_posted_with() {
    for radius in [200.0, 500.0, 1_000.0, 3_000.0] {
        for design in [35.0, 55.0, 70.0] {
            let e = bend_bank(radius, Some(design));
            let advisory = posted_advisory_mph(radius, e);
            let tire_demand = (advisory * advisory) as f64 / (15.0 * radius) - e;
            assert!(
                tire_demand <= advisory_side_friction(advisory) + 1e-9,
                "at {radius} ft and {design} mph the advisory asks {tire_demand} of the tires"
            );
        }
    }
}

/// Every signed bend in the bake, at the number on its sign, asks a full
/// trailer less than its warning share: the game's own advisory never sits
/// above the speed its own roll model holds the load at. The only rows a sign
/// cannot carry are those too tight for the lowest plaque, and the cab speaks
/// the load's own number for those (`spoken_advisory_mph`).
#[test]
#[cfg_attr(ci_quick, ignore = "sweep: every mainline curve in the bake")]
fn test_every_signed_bend_holds_a_full_trailer_at_its_advisory() {
    use ff_core::sim::vehicle::{TruckState, REFERENCE_CARGO_KG, ROLL_WARN_SHARE};
    let full = TruckState {
        trailer_attached: true,
        cargo_kg: REFERENCE_CARGO_KG,
        ..TruckState::default()
    };
    let mut checked = 0usize;
    let mut plaque_floor = 0usize;
    for records in load().values() {
        for record in records
            .iter()
            .filter(|r| !r.connector && r.min_radius_ft > 0)
        {
            checked += 1;
            let radius = record.min_radius_ft as f64;
            // Credited the most bank any row is posted with, the built 6
            // percent: a row posted on less asks less than its criterion
            // anyway, and the criterion tops out at 0.26 g.
            let asks = (record.advisory_mph * record.advisory_mph) as f64 / (15.0 * radius)
                - ff_core::data::curves::SUPERELEVATION_BUILT;
            let share = asks / full.roll_threshold_g();
            if share > ROLL_WARN_SHARE {
                assert_eq!(
                    record.advisory_mph, ADVISORY_MIN_MPH,
                    "a {radius} ft bend posted {} asks a full trailer {share:.2}",
                    record.advisory_mph
                );
                plaque_floor += 1;
            }
        }
    }
    assert!(
        checked > 1_000,
        "the curve bake did not load: {checked} rows"
    );
    assert!(
        plaque_floor * 100 < checked,
        "{plaque_floor} of {checked} bends are too tight for any plaque"
    );
}
