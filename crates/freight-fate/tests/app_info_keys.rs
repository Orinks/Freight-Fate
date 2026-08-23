//! Port of the pure parts of `tests/test_info_keys.py`: the one case that does
//! not need a drive. The rest of the file drives a real `DrivingState` and is
//! ported in `crates/freight-fate/tests/states_driving_controls.rs`.

use freight_fate::states::base::State;
use freight_fate::states::main_menu::NameEntryState;

#[test]
fn test_name_entry_keeps_its_commas() {
    // A driver name may well contain a comma, so the field declines the
    // global message-review keys.
    let field = NameEntryState::new();
    assert!(field.captures_text_input());
}

// The rest of `tests/test_info_keys.py` is ported in
// `crates/freight-fate/tests/states_driving_controls.rs`, against a real
// `DrivingState`: 28 of those cases run live there and the remaining ones
// carry their own stub and their own reason. A macro used to restate all 49
// of them here as `#[ignore]`d empty bodies, which the parity sweep could not
// see (it reads `fn test_*`, and a macro writes `fn $name`) and which counted
// the same backlog twice.
//
// What is left below is only the R-key cases, which have no Rust namesake
// anywhere yet. They are written out rather than generated so the sweep can
// read them.

#[test]
#[ignore = "unblocked: states::driving exists; the R-key readout case is not written yet"]
fn test_route_key_reports_progress_then_road_state_and_destination() {}

#[test]
#[ignore = "unblocked: states::driving exists; the R-key readout case is not written yet"]
fn test_route_key_counts_down_to_a_planned_stop_instead_of_the_destination() {}

#[test]
#[ignore = "unblocked: states::driving exists; the R-key readout case is not written yet"]
fn test_route_key_falls_back_to_the_destination_once_the_plan_is_behind() {}

#[test]
#[ignore = "unblocked: states::driving exists; the R-key readout case is not written yet"]
fn test_route_key_reports_reverse_route_direction() {}

#[test]
#[ignore = "unblocked: states::driving exists; the R-key readout case is not written yet"]
fn test_route_key_uses_metric_distances() {}

#[test]
#[ignore = "unblocked: states::driving exists; the R-key readout case is not written yet"]
fn test_route_key_answers_with_the_gate_on_the_facility_approach() {}

#[test]
#[ignore = "unblocked: states::driving exists; the R-key readout case is not written yet"]
fn test_route_key_answers_with_the_gate_when_the_route_has_ended() {}

#[test]
#[ignore = "unblocked: states::driving exists; the R-key readout case is not written yet"]
fn test_route_key_never_says_zero_miles_closing_on_the_gate() {}

#[test]
#[ignore = "unblocked: states::driving exists; the R-key readout case is not written yet"]
fn test_route_key_names_the_street_under_the_wheels() {}

#[test]
#[ignore = "unblocked: states::driving exists; the R-key readout case is not written yet"]
fn test_route_key_counts_down_to_the_on_ramp_leaving_the_origin_gate() {}

#[test]
#[ignore = "unblocked: states::driving exists; the R-key readout case is not written yet"]
fn test_route_key_answers_the_pickup_drive_as_city_streets() {}
