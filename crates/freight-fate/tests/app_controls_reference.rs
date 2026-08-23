//! Port of `tests/test_controls_reference.py`: the in-game controls
//! reference, reachable from the pause menu, opens to keys. The pause-menu
//! tests still read a real drive; listed here, ignored, so the suites diff
//! by name.

use freight_fate::states::main_menu::{controls_help_page, HelpState, HELP_PAGES};

#[test]
fn test_controls_help_page_points_at_the_driving_keys() {
    let idx = controls_help_page();
    let (title, lines) = HELP_PAGES[idx];
    assert_eq!(title, "Driving information keys");
    // The new keys are documented there.
    let joined = lines.join(" ");
    assert!(joined.contains("Space speaks your speed"));
    assert!(joined.contains("active speed-control mode"));
    assert!(joined.contains("open-road target"));
    assert!(joined.contains("S speaks the posted speed limit"));
    assert!(joined.contains("R speaks how far along you are"));
    assert!(joined.contains("A repeats the last driving announcement"));
    // U stopped being a recital of everything ahead (2026-08-15): the exit
    // cue, the traffic-pressure advisory and two of the three bends were
    // already other keys' answers, so the help now promises only the road
    // nothing else covers. Pinned on the promise, not the old phrasing.
    assert!(joined.contains("U speaks the road ahead that no other key answers"));
    // And U must never advertise police activity again (owner ruling): the
    // check is scoped to U's own line, because a sibling line legitimately
    // explains what the hours-of-service keys do with enforcement off.
    let u_line = lines
        .iter()
        .find(|line| line.starts_with("U speaks"))
        .unwrap()
        .to_lowercase();
    for word in ["patrol", "police", "bear"] {
        assert!(!u_line.contains(word));
    }
    assert!(lines
        .iter()
        .any(|line| line.contains('X') && line.to_lowercase().contains("signal")));
    assert!(lines
        .iter()
        .all(|line| !line.contains("X takes the next announced exit")));
    assert!(joined.contains("Left or Right Control stops the driving event voice"));
}

#[test]
fn test_help_pages_explain_t_roadside_sleep_and_poi_priority() {
    let joined = HELP_PAGES
        .iter()
        .flat_map(|(_title, lines)| lines.iter().copied())
        .collect::<Vec<&str>>()
        .join(" ");
    assert!(joined.contains("T opens the emergency shoulder-sleep warning"));
    assert!(joined.contains("nearby route points always take priority"));
    assert!(joined.contains("T or the pause menu offers emergency shoulder sleep"));
    assert!(joined.contains("plus D-pad down opens route-stop actions or emergency shoulder sleep"));
}

#[test]
fn test_help_state_opens_to_a_chosen_page() {
    let page = controls_help_page();
    assert_eq!(HelpState::at_page(page).page, page);
    // Out-of-range requests clamp instead of crashing.
    assert!(HelpState::at_page(9999).page < HELP_PAGES.len());
}

#[test]
#[ignore = "needs states::driving_pause_states and states::driving"]
fn test_pause_menu_offers_controls_and_help() {}

#[test]
#[ignore = "needs states::driving_pause_states and states::driving"]
fn test_pause_menu_emergency_shoulder_sleep_sits_between_mechanic_and_settings() {}
