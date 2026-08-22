//! Port of `tests/test_controls_reference.py`: the in-game controls
//! reference, reachable from the pause menu, opens to keys. Every test reads
//! `states::main_menu` (HELP_PAGES, HelpState) or the pause menu over a real
//! drive; listed here, ignored, so the suites diff by name.

#[test]
#[ignore = "needs states::main_menu (HELP_PAGES, controls_help_page)"]
fn test_controls_help_page_points_at_the_driving_keys() {}

#[test]
#[ignore = "needs states::main_menu (HELP_PAGES)"]
fn test_help_pages_explain_t_roadside_sleep_and_poi_priority() {}

#[test]
#[ignore = "needs states::main_menu_help (HelpState)"]
fn test_help_state_opens_to_a_chosen_page() {}

#[test]
#[ignore = "needs states::driving_pause_states and states::driving"]
fn test_pause_menu_offers_controls_and_help() {}

#[test]
#[ignore = "needs states::driving_pause_states and states::driving"]
fn test_pause_menu_emergency_shoulder_sleep_sits_between_mechanic_and_settings() {}
