//! Its own binary, not a module of `it`: it must start in a process where
//! nothing has registered the classics yet, which `it`'s parallel tests
//! cannot promise.
//!
//! A brand-new career sits at the title screen -- which plays
//! `classic_menu_theme` before any drive exists -- so app startup itself
//! must register the classics. This test never calls
//! `classic_music::register()` by hand, so it can only pass if
//! `TestApp::new()` (which goes through the same `App::build()` real
//! launches use) registered them.

use freight_fate::app::testing::TestApp;
use freight_fate::audio::assets::{asset_bytes, MUSIC_EXTENSIONS};

#[test]
fn the_menu_theme_is_registered_by_app_startup_alone() {
    assert!(
        ff_core::assets_pack::generated_sound("music/classic_menu_theme").is_none(),
        "something registered the classics before the app was built"
    );
    let _app = TestApp::new();
    let (bytes, ext) = asset_bytes("music/classic_menu_theme", MUSIC_EXTENSIONS)
        .expect("classic_menu_theme missing after a fresh TestApp::new()");
    assert_eq!(ext, "ogg");
    assert_eq!(&bytes[..4], b"OggS");
}
