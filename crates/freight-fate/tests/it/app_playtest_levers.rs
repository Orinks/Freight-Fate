//! Port of the `GameContext` tests of `tests/test_playtest_levers.py`: the
//! playtest sandbox keeps a forced scenario off the career file (the lever
//! logic itself is tested in `ff_core::playtest_levers`).

use ff_core::models::profile::{find_save_path, Profile};
use freight_fate::app::testing::TestApp;

fn profile(name: &str) -> Profile {
    let mut profile = Profile::new();
    profile.name = name.to_string();
    profile
}

#[test]
fn test_quit_save_honors_the_playtest_sandbox() {
    // The quit-time save must respect the sandbox: the owner's Denver snow
    // run held sandboxed for the whole drive, then App.shutdown() wrote the
    // final state straight to disk and the run persisted anyway.
    let mut app = TestApp::new();
    app.ctx.profile = Some(profile("Sandbox Quit"));
    app.ctx.playtest_sandbox = true;
    app.shutdown();
    assert!(find_save_path("Sandbox Quit").is_none());
}

#[test]
fn test_save_profile_honors_the_playtest_sandbox() {
    let mut app = TestApp::new();
    app.ctx.profile = Some(profile("Sandbox Save"));
    app.ctx.school_sandbox = false;
    app.ctx.playtest_sandbox = true;
    app.ctx.save_profile();
    assert!(find_save_path("Sandbox Save").is_none());

    app.ctx.playtest_sandbox = false;
    app.ctx.save_profile();
    assert!(find_save_path("Sandbox Save").is_some());
    app.shutdown();
}

/// The driving-school sandbox is the same guard.
#[test]
fn save_profile_honors_the_school_sandbox() {
    let mut app = TestApp::new();
    app.ctx.profile = Some(profile("School Save"));
    app.ctx.school_sandbox = true;
    app.ctx.save_profile();
    assert!(find_save_path("School Save").is_none());
    app.shutdown();
}
