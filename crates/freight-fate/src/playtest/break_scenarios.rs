//! The adversarial battery's scenarios (port of
//! `tools/playtest_break_scenarios/`).
//!
//! Python split these by system family across nine files, each registering
//! itself with a decorator. Here the registry is one explicit table,
//! [`SCENARIOS`], and the scenario bodies live in submodules of the same
//! names. A new scenario is a function plus a row.
//!
//! # Porting status
//!
//! `driving_physics` is ported bar one scenario -- `neutral_coast_mountain`
//! replaced `Trip::grade_at` with a constant-slope lambda, which Rust cannot
//! do to an inherent method; it needs a real 6% stretch or a grade override
//! on `Trip`, which is the adversarial-battery task's call, not a thing to
//! invent here. The other eight families
//! (`assists`, `career_economy`, `dispatch_saveload`, `enforcement`,
//! `radio_weather`, `resources`, `settings_misc`, `today_1_9`, `unlawful`)
//! belong to the adversarial-battery task, which owns `tests/adversarial`
//! and its `KNOWN_OPEN` list; the rig, the registry, the verdict fold and
//! the `--break-scenario` CLI they all need are here and finished.

pub mod driving_physics;

use super::breaker::Scenario;

/// Every scenario, in run order.
pub static SCENARIOS: &[Scenario] = &[
    Scenario {
        name: "floor_it_through_town",
        description: "Hold the floor through urban speed zones; every dollar it costs must \
                      come from an officer who was audibly there.",
        run: driving_physics::floor_it_through_town,
    },
    Scenario {
        name: "hairpin_at_70_no_assists",
        description: "Take a 25-mph hairpin at 70 with every assist off; does anything \
                      push back?",
        run: driving_physics::hairpin_at_70_no_assists,
    },
    Scenario {
        name: "reverse_down_the_route",
        description: "Engage reverse and back down the interstate; position must clamp, \
                      someone should object.",
        run: driving_physics::reverse_down_the_route,
    },
    Scenario {
        name: "dynamite_parking_brake_at_60",
        description: "Pull the parking brake valve at 60: flat-spots, no waiting \
                      fast-forward, honest speech.",
        run: driving_physics::dynamite_parking_brake_at_60,
    },
];
