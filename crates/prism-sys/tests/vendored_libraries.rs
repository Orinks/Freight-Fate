//! Every vendored platform directory must hold the library its name promises.
//!
//! `build.rs` looks for `vendor/<os>-<arch>/<library>` and, when it is absent,
//! prints a warning and carries on: the app then starts and runs mute. That is
//! the right behaviour at run time and the wrong thing to discover in a
//! release, so the vendor tree is checked here instead.

use std::path::{Path, PathBuf};

fn vendor_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("vendor")
}

/// The library file name for a platform directory such as `macos-aarch64`.
fn expected_library(directory: &str) -> Option<&'static str> {
    match directory.split('-').next()? {
        "windows" => Some("prism.dll"),
        "macos" => Some("libprism.dylib"),
        "linux" => Some("libprism.so"),
        _ => None,
    }
}

#[test]
fn every_platform_directory_holds_its_library() {
    let mut checked = 0;
    for entry in std::fs::read_dir(vendor_dir()).expect("a vendor directory") {
        let entry = entry.expect("a readable vendor entry");
        if !entry.file_type().expect("a file type").is_dir() {
            continue;
        }
        let name = entry.file_name().to_string_lossy().into_owned();
        let Some(library) = expected_library(&name) else {
            // `licenses` and anything else that is not a platform.
            continue;
        };
        assert!(
            entry.path().join(library).is_file(),
            "vendor/{name} does not contain {library}, so builds for that \
             platform would ship without speech"
        );
        checked += 1;
    }
    assert!(checked > 0, "no vendored platforms were found at all");
}

#[test]
fn the_platforms_we_ship_are_vendored() {
    // Named explicitly rather than derived from the directory listing: the
    // point is to fail when one goes missing, which a listing cannot catch.
    for platform in ["windows-x86_64", "macos-x86_64", "macos-aarch64"] {
        let library = expected_library(platform).expect("a known platform");
        assert!(
            vendor_dir().join(platform).join(library).is_file(),
            "{platform} is a release target but has no vendored {library}"
        );
    }
}

#[test]
fn the_licence_travels_with_the_binaries() {
    // Prism is MPL-2.0. Distributing the library without its licence is not
    // something to leave to whoever assembles the release.
    for file in ["LICENSE", "NOTICE", "PRISM-VERSION.txt"] {
        assert!(
            vendor_dir().join("licenses").join(file).is_file(),
            "vendor/licenses/{file} is missing"
        );
    }
}

#[test]
fn linux_ships_no_speech_library() {
    // Prism's Linux build carries its own glib. The app links GTK, which uses
    // the system's. Two GObject type systems in one process abort on start-up:
    //
    //   GLib-GObject:ERROR gtype.c:1245: assertion failed: NODE_REFCOUNT > 0
    //
    // Established by launching the shipped tarball under WSLg: it aborts with
    // the speech libraries present and runs with them moved aside. No test can
    // catch this, because no test loads GTK -- which is how it survived a
    // green suite and a green CI run.
    //
    // Orca reads the interface through AT-SPI regardless; what Linux gives up
    // is the app's own announcements. Vendoring the library again means
    // solving the glib conflict first, not adding the file back.
    assert!(
        !vendor_dir().join("linux-x86_64").exists(),
        "a Linux library is vendored again; see the comment on this test"
    );
}
