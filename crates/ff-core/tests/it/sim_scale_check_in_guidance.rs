//! Open-scale guidance: the check-in notice, the half-mile reminder and the
//! rest key at the scale (port of `tests/test_scale_check_in_guidance.py`).
//! Every case drives the App shell's DrivingState and waits for it; the one
//! pure sentence-length check reads the driving layer's sample text.

#[test]
#[ignore = "wrong crate: ff-core cannot see the game crate, so this case belongs in crates/freight-fate/tests/ -- open scale notice"]
fn test_open_scale_notice_teaches_the_exit_key_then_the_rest_key() {}

#[test]
#[ignore = "wrong crate: ff-core cannot see the game crate, so this case belongs in crates/freight-fate/tests/ -- open scale notice priority"]
fn test_open_scale_notice_carries_route_priority() {}

// `test_scale_notice_lookahead_sample_covers_the_real_sentence` is live in `crates/freight-fate/tests/states_driving_enforcement.rs`.

// `test_reminder_fires_once_when_still_fast_with_no_scale_exit_armed` is live in `crates/freight-fate/tests/states_driving_enforcement.rs`.

// `test_reminder_speaks_the_road_actually_left` is live in `crates/freight-fate/tests/states_driving_enforcement.rs`.

// `test_reminder_stays_quiet_once_the_scale_exit_is_armed` is live in `crates/freight-fate/tests/states_driving_enforcement.rs`.

// `test_reminder_stays_quiet_below_the_bypass_speed` is live in `crates/freight-fate/tests/states_driving_enforcement.rs`.

// `test_rest_key_at_speed_defers_to_the_open_scale` is live in `crates/freight-fate/tests/states_driving_enforcement.rs`.

#[test]
#[ignore = "wrong crate: ff-core cannot see the game crate, so this case belongs in crates/freight-fate/tests/ -- rest key at the scale"]
fn test_rest_key_defer_notice_carries_route_priority() {}

// `test_rest_key_plans_normally_when_the_scale_is_closed` is live in `crates/freight-fate/tests/states_driving_enforcement.rs`.

// `test_rest_key_plans_normally_when_the_scale_is_behind` is live in `crates/freight-fate/tests/states_driving_enforcement.rs`.

// `test_rest_key_police_stop_guard_still_outranks_the_scale` is live in `crates/freight-fate/tests/states_driving_enforcement.rs`.

// `test_rest_key_ignores_the_scale_in_a_casual_hos_mode` is live in `crates/freight-fate/tests/states_driving_enforcement.rs`.

#[test]
#[ignore = "wrong crate: ff-core cannot see the game crate, so this case belongs in crates/freight-fate/tests/ -- exit key at the scale"]
fn test_exit_key_prefers_the_nearer_open_scale_over_the_planned_stop() {}

#[test]
#[ignore = "wrong crate: ff-core cannot see the game crate, so this case belongs in crates/freight-fate/tests/ -- exit key at the scale"]
fn test_exit_key_leaves_a_nearer_selected_stop_alone() {}

#[test]
#[ignore = "wrong crate: ff-core cannot see the game crate, so this case belongs in crates/freight-fate/tests/ -- scale bypass at the gore; seed 1 lands under the 85 percent catch chance"]
fn test_crossing_with_the_scale_exit_armed_is_not_charged_at_the_gore() {}

#[test]
#[ignore = "wrong crate: ff-core cannot see the game crate, so this case belongs in crates/freight-fate/tests/ -- pull-over stands down the armed exit"]
fn test_pull_over_stands_down_the_armed_exit() {}

#[test]
#[ignore = "wrong crate: ff-core cannot see the game crate, so this case belongs in crates/freight-fate/tests/ -- pull-over with no armed exit"]
fn test_pull_over_with_no_armed_exit_says_nothing_about_exits() {}

#[test]
#[ignore = "wrong crate: ff-core cannot see the game crate, so this case belongs in crates/freight-fate/tests/ -- nearest stop within at the scale"]
fn test_nearest_stop_within_returns_the_nearest_not_the_first_listed() {}

#[test]
#[ignore = "wrong crate: ff-core cannot see the game crate, so this case belongs in crates/freight-fate/tests/ -- rest key stopped at the scale"]
fn test_rest_key_stopped_at_the_scale_opens_the_scale_menu() {}

#[test]
#[ignore = "wrong crate: ff-core cannot see the game crate, so this case belongs in crates/freight-fate/tests/ -- rest key on the scale ramp"]
fn test_rest_key_on_the_scale_ramp_sends_you_to_the_scale() {}

#[test]
#[ignore = "wrong crate: ff-core cannot see the game crate, so this case belongs in crates/freight-fate/tests/ -- rest key stopped on the scale"]
fn test_rest_key_stopped_on_the_scale_opens_the_check_in() {}
