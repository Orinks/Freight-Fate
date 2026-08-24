//! Retiring instructions the player has demonstrated (research doc R7; port
//! of `freight_fate/spoken_advice.py`).
//!
//! Some spoken prompts teach a control the game names on every wheel entry or
//! every stop callout, forever: "Press E to start the engine", "F1 lists the
//! controls", "Press X to signal for the exit". Once a player has done the
//! thing a few times the instruction is noise, and the pull-model query keys
//! keep the information reachable, so retiring the auto-nag loses nothing.
//!
//! Retirement is gated on a small persisted counter, but the counter is keyed
//! to the *control binding and the transmission mode it was earned under*, so
//! a remapped key or a switch to manual re-teaches the new hint afresh -- the
//! standing rule that spoken advice never names a control the current
//! settings do not give this driver, cutting both ways (never name a wrong
//! key, never go silent where the key is now different). The binding is
//! captured as the hint phrase itself: change the device, or remap the key,
//! and the phrase changes, which changes the key, which resets the count to
//! zero.
//!
//! The counters live in the profile's `achievement_stats` dict (already
//! persisted and general-purpose) under a `hint:` namespace, so no new save
//! field is needed.

use crate::achievements::{increment_stat, int_stat, AchievementProfile};

/// Spoken until the player has performed the action this many times under the
/// current binding and transmission. Small: three unremarkable repetitions is
/// enough to show the control is known.
pub const RETIRE_AFTER: i64 = 3;

fn counter_key(action: &str, binding: &str, transmission: &str) -> String {
    format!("hint:{action}:{binding}:{transmission}")
}

fn transmission_label(automatic: bool) -> &'static str {
    if automatic {
        "auto"
    } else {
        "manual"
    }
}

/// Whether `action`'s spoken instruction has been earned into silence for the
/// current `binding` and transmission mode.
pub fn instruction_retired(
    profile: &mut dyn AchievementProfile,
    action: &str,
    binding: &str,
    automatic: bool,
) -> bool {
    let key = counter_key(action, binding, transmission_label(automatic));
    int_stat(profile, &key) >= RETIRE_AFTER
}

/// Record that the player just performed `action` under this binding and
/// transmission. Returns the new count. Stops counting past the retirement
/// threshold so the stored number never runs away.
pub fn note_demonstrated(
    profile: &mut dyn AchievementProfile,
    action: &str,
    binding: &str,
    automatic: bool,
) -> i64 {
    let key = counter_key(action, binding, transmission_label(automatic));
    if int_stat(profile, &key) >= RETIRE_AFTER {
        return RETIRE_AFTER;
    }
    increment_stat(profile, &key)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::profile::Profile;

    #[test]
    fn a_hint_retires_after_three_demonstrations_under_one_binding() {
        let mut p = Profile::named("Hints");
        assert!(!instruction_retired(
            &mut p,
            "engine_start",
            "Press E",
            true
        ));
        for n in 1..=3 {
            assert_eq!(
                note_demonstrated(&mut p, "engine_start", "Press E", true),
                n
            );
        }
        assert!(instruction_retired(&mut p, "engine_start", "Press E", true));
        // The counter never runs away past the threshold.
        assert_eq!(
            note_demonstrated(&mut p, "engine_start", "Press E", true),
            RETIRE_AFTER
        );
        assert_eq!(p.achievement_stats["hint:engine_start:Press E:auto"], 3);
        // A remapped key or a switch to manual re-teaches afresh.
        assert!(!instruction_retired(
            &mut p,
            "engine_start",
            "Press Q",
            true
        ));
        assert!(!instruction_retired(
            &mut p,
            "engine_start",
            "Press E",
            false
        ));
    }
}
