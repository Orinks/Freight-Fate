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
// The R-key cases that used to be stubbed here are live in that same file,
// under its "the R key: route status" heading: they drive a real
// `DrivingState` (and two of them a real street chain), so they belong with
// the drive helper that empties the road and pins the weather rather than
// beside this one pure case.
