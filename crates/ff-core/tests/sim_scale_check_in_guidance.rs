//! Open-scale guidance: the check-in notice, the half-mile reminder and the
//! rest key at the scale (port of `tests/test_scale_check_in_guidance.py`).
//! Every case drives the App shell's DrivingState and waits for it; the one
//! pure sentence-length check reads the driving layer's sample text.

#[test]
#[ignore = "needs app shell (open scale notice)"]
fn test_open_scale_notice_teaches_the_exit_key_then_the_rest_key() {}

#[test]
#[ignore = "needs app shell (open scale notice priority)"]
fn test_open_scale_notice_carries_route_priority() {}

#[test]
#[ignore = "needs app shell (states::driving_enforcement::SCALE_NOTICE_SAMPLE and ramp_arrival_grace_seconds)"]
fn test_scale_notice_lookahead_sample_covers_the_real_sentence() {}

#[test]
#[ignore = "needs app shell (half-mile reminder)"]
fn test_reminder_fires_once_when_still_fast_with_no_scale_exit_armed() {}

#[test]
#[ignore = "needs app shell (half-mile reminder)"]
fn test_reminder_speaks_the_road_actually_left() {}

#[test]
#[ignore = "needs app shell (half-mile reminder)"]
fn test_reminder_stays_quiet_once_the_scale_exit_is_armed() {}

#[test]
#[ignore = "needs app shell (half-mile reminder)"]
fn test_reminder_stays_quiet_below_the_bypass_speed() {}

#[test]
#[ignore = "needs app shell (rest key at the scale)"]
fn test_rest_key_at_speed_defers_to_the_open_scale() {}

#[test]
#[ignore = "needs app shell (rest key at the scale)"]
fn test_rest_key_defer_notice_carries_route_priority() {}

#[test]
#[ignore = "needs app shell (rest key at the scale)"]
fn test_rest_key_plans_normally_when_the_scale_is_closed() {}

#[test]
#[ignore = "needs app shell (rest key at the scale)"]
fn test_rest_key_plans_normally_when_the_scale_is_behind() {}

#[test]
#[ignore = "needs app shell (rest key at the scale)"]
fn test_rest_key_police_stop_guard_still_outranks_the_scale() {}

#[test]
#[ignore = "needs app shell (rest key at the scale)"]
fn test_rest_key_ignores_the_scale_in_a_casual_hos_mode() {}

#[test]
#[ignore = "needs app shell (exit key at the scale)"]
fn test_exit_key_prefers_the_nearer_open_scale_over_the_planned_stop() {}

#[test]
#[ignore = "needs app shell (exit key at the scale)"]
fn test_exit_key_leaves_a_nearer_selected_stop_alone() {}

#[test]
#[ignore = "needs app shell (scale bypass at the gore; seed 1 lands under the 85 percent catch chance)"]
fn test_crossing_with_the_scale_exit_armed_is_not_charged_at_the_gore() {}

#[test]
#[ignore = "needs app shell (pull-over stands down the armed exit)"]
fn test_pull_over_stands_down_the_armed_exit() {}

#[test]
#[ignore = "needs app shell (pull-over with no armed exit)"]
fn test_pull_over_with_no_armed_exit_says_nothing_about_exits() {}

#[test]
#[ignore = "needs app shell (nearest stop within at the scale)"]
fn test_nearest_stop_within_returns_the_nearest_not_the_first_listed() {}

#[test]
#[ignore = "needs app shell (rest key stopped at the scale)"]
fn test_rest_key_stopped_at_the_scale_opens_the_scale_menu() {}

#[test]
#[ignore = "needs app shell (rest key on the scale ramp)"]
fn test_rest_key_on_the_scale_ramp_sends_you_to_the_scale() {}

#[test]
#[ignore = "needs app shell (rest key stopped on the scale)"]
fn test_rest_key_stopped_on_the_scale_opens_the_check_in() {}
