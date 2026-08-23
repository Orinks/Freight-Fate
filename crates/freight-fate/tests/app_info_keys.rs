//! Port of the pure parts of `tests/test_info_keys.py`. Every test but one
//! drives the real `DrivingState`; they are listed here, ignored, so the
//! suites diff by name, and come alive with `states::driving`.

use freight_fate::states::base::State;
use freight_fate::states::main_menu::NameEntryState;

#[test]
fn test_name_entry_keeps_its_commas() {
    // A driver name may well contain a comma, so the field declines the
    // global message-review keys.
    let field = NameEntryState::new();
    assert!(field.captures_text_input());
}

macro_rules! needs_driving {
    ($($name:ident),* $(,)?) => {
        $(
            #[test]
            #[ignore = "needs states::driving"]
            fn $name() {}
        )*
    };
}

needs_driving!(
    test_speed_limit_key_reads_the_posted_limit,
    test_speed_key_includes_cruise_set_speed_when_active,
    test_speed_key_includes_speed_keeper_target_when_active,
    test_weather_key_reads_safe_speed_in_metric_units,
    test_speed_limit_key_reports_how_far_over_you_are,
    test_metric_speed_limit_key_reports_overage_in_metric_units,
    test_repeat_key_replays_the_last_route_announcement,
    test_upcoming_key_reports_an_imposed_limit_ahead,
    test_upcoming_key_never_reports_enforcement,
    test_upcoming_key_does_not_repeat_the_next_exit_key,
    test_upcoming_key_leads_with_the_ramp_light,
    test_upcoming_key_stays_a_couple_of_sentences,
    test_upcoming_key_handles_a_clear_road,
    test_driving_help_describes_x_as_signal_not_take_exit,
    test_safe_speed_key_speaks_one_number,
    test_route_key_reports_progress_then_road_state_and_destination,
    test_route_key_counts_down_to_a_planned_stop_instead_of_the_destination,
    test_route_key_falls_back_to_the_destination_once_the_plan_is_behind,
    test_safe_speed_key_answers_for_the_ramp,
    test_route_key_reports_reverse_route_direction,
    test_grade_key_reads_slope_and_verdict,
    test_clock_key_leads_with_time_then_schedule_verdict,
    test_terse_clock_key_drops_calendar_and_stop_planning,
    test_clock_key_keeps_one_hours_clause_instead_of_the_whole_report,
    test_clock_key_points_at_the_hours_keys_for_the_first_three_presses,
    test_alt_a_s_and_d_each_answer_one_hours_question,
    test_the_hours_keys_leave_plain_a_s_and_d_alone,
    test_alt_d_carries_the_next_legal_stop_context,
    test_controller_clock_button_keeps_the_whole_hours_report,
    test_status_menu_carries_the_drivers_board_progress_percent,
    test_upcoming_key_uses_metric_distances,
    test_route_key_uses_metric_distances,
    test_route_key_answers_with_the_gate_on_the_facility_approach,
    test_route_key_answers_with_the_gate_when_the_route_has_ended,
    test_route_key_never_says_zero_miles_closing_on_the_gate,
    test_route_key_names_the_street_under_the_wheels,
    test_route_key_counts_down_to_the_on_ramp_leaving_the_origin_gate,
    test_route_key_answers_the_pickup_drive_as_city_streets,
    test_grade_key_reads_the_slope_and_whether_the_truck_holds_it,
    test_grade_key_names_the_next_steep_grade_ahead,
    test_grade_key_says_when_nothing_steep_is_coming,
    test_grade_key_names_the_grade_the_preview_is_planning_for,
    test_grade_key_does_not_call_a_punchy_pull_nothing_steep,
    test_grade_key_names_the_same_hill_the_speed_control_cue_names,
    test_grade_key_names_a_grade_that_steepens_without_letting_up,
    test_grade_key_says_nothing_else_steep_while_on_a_steep_grade,
    test_controller_can_ask_for_the_speed_limit,
    test_controller_back_button_stops_the_driving_voice,
    test_controller_help_names_the_stop_and_the_speed_limit,
);
