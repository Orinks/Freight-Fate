//! Nothing in a test process may reach the player's real save folder.
//!
//! Every test that wants its own saves pins a directory for its own thread,
//! which is what lets hundreds of them run at once. But the pin is a
//! thread-local, and a thread that has none falls through to the portable
//! `saves` folder beside the game -- somebody's careers. Nothing spawns such
//! a thread today; this is the one seam whose failure mode is writing over a
//! career, and "nothing does today" is not a guarantee.
//!
//! Read `ff_core::settings::paths` for the mechanism. In one line: the real
//! save folder is a capability the game's `main()` grants, a test binary has
//! no such `main()`, and so an unpinned lookup refuses, records the path, and
//! panics naming it.

use std::panic::catch_unwind;
use std::path::PathBuf;

use ff_core::settings::paths;

use freight_fate::app::testing::{env_lock, EnvGuard, TempDir};

/// Hold the environment while asking what an UNPINNED thread gets.
///
/// `FREIGHT_FATE_DATA_DIR` still answers ahead of the fallthrough, and the
/// sandbox cases really do set it, process-wide, while these run. A case here
/// that did not queue was asking a different question every time the two
/// overlapped -- and got the sandbox's directory, not a refusal.
fn with_no_environment_override() -> EnvGuard {
    env_lock()
}

fn was_refused(path: &std::path::Path) -> bool {
    paths::refused_save_dirs().contains(&path.display().to_string())
}

/// The capability itself: a test process is never the game.
///
/// If this ever passes with `true`, everything below it is decoration --
/// something has handed the suite the player's own careers.
#[test]
fn test_a_test_process_is_never_granted_the_real_save_directory() {
    assert!(!paths::real_save_dir_allowed());
}

#[test]
fn test_an_unpinned_lookup_is_refused_and_recorded_instead_of_answered() {
    let _env = with_no_environment_override();
    let root = paths::save_root();
    let outcome = catch_unwind(ff_core::settings::data_dir);
    assert!(outcome.is_err(), "the real save folder was handed over");
    assert!(was_refused(&root), "{:?}", paths::refused_save_dirs());
}

/// There are two doors to the same folder -- settings has one, the profile
/// model has the other -- and both carry the lock. Guarding only the one the
/// defect happened to come through would leave the other wide open.
#[test]
fn test_the_profile_model_door_is_locked_too() {
    let _env = with_no_environment_override();
    let root = paths::save_root();
    let outcome = catch_unwind(ff_core::models::profile::data_dir);
    assert!(outcome.is_err(), "the real save folder was handed over");
    assert!(was_refused(&root), "{:?}", paths::refused_save_dirs());
}

/// The case test discipline cannot catch, and the reason this seam exists.
///
/// The pin is per thread, so a worker the test did not pin was never covered
/// by it -- it saw the player's own folder, and no amount of remembering to
/// pin fixes that, because the thread is not the test's to pin. The
/// capability is process-wide, so the worker refuses while the parent thread
/// keeps the directory it pinned.
#[test]
fn test_a_spawned_thread_cannot_inherit_its_way_to_the_real_saves() {
    let _env = with_no_environment_override();
    let tmp = TempDir::new("save-dir-guard");
    let mine = tmp.path().to_path_buf();
    let previous = ff_core::settings::set_thread_data_dir(Some(mine.clone()));
    let root = paths::save_root();

    let worker = std::thread::Builder::new()
        .name("save-dir-guard-probe".to_string())
        .spawn(ff_core::settings::data_dir)
        .expect("the probe thread starts");
    let outcome = worker.join();

    // This thread still has exactly what it pinned: the refusal is the
    // worker's alone, and nothing about the parent moved.
    assert_eq!(ff_core::settings::data_dir(), mine);
    ff_core::settings::set_thread_data_dir(previous);

    assert!(
        outcome.is_err(),
        "a spawned thread read the real save folder: {outcome:?}"
    );
    assert!(was_refused(&root), "{:?}", paths::refused_save_dirs());
}

/// A pinned thread is untouched -- which is the whole test suite, and the
/// reason the capability sits on the fallthrough rather than on the lookup.
#[test]
fn test_a_pinned_directory_still_answers_for_both_doors() {
    let tmp = TempDir::new("save-dir-pinned");
    let mine: PathBuf = tmp.path().to_path_buf();
    let previous = ff_core::settings::set_thread_data_dir(Some(mine.clone()));

    assert_eq!(ff_core::settings::data_dir(), mine);
    assert_eq!(ff_core::models::profile::data_dir(), mine);

    ff_core::settings::set_thread_data_dir(previous);
}

/// A test app is a pinned thread, so building one is unaffected -- if this
/// ever fails the guard has been put somewhere it does not belong.
#[test]
fn test_a_test_app_still_gets_its_own_saves() {
    let app = freight_fate::app::testing::TestApp::new();
    let dir = ff_core::settings::data_dir();
    assert!(dir != paths::save_root(), "{}", dir.display());
    drop(app);
}
