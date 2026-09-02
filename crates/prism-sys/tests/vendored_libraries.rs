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
    for platform in [
        "windows-x86_64",
        "macos-x86_64",
        "macos-aarch64",
        "linux-x86_64",
    ] {
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
fn the_linux_library_travels_with_its_bundled_dependencies() {
    // Prism's Linux build is the manylinux wheel's: `libprism.so` plus
    // auditwheel-renamed copies of glib, gio, glibmm, giomm and
    // speech-dispatcher, found through a RUNPATH of `$ORIGIN`. The game
    // process has no other glib in it -- SDL2 is compiled in and opens X11,
    // Wayland and the audio servers directly -- so unlike a GTK app
    // (PortkeyDrop had to drop the library for exactly that duplicate-GType
    // abort) two copies never meet. What must hold instead is that the
    // renamed dependencies ship beside the library: a stray `libprism.so`
    // on its own fails to load, and the game then starts mute.
    let dir = vendor_dir().join("linux-x86_64");
    for prefix in ["libspeechd-", "libglib-2-", "libgio-2-", "libgobject-2-"] {
        let present = std::fs::read_dir(&dir)
            .expect("a linux-x86_64 vendor directory")
            .flatten()
            .any(|entry| entry.file_name().to_string_lossy().starts_with(prefix));
        assert!(
            present,
            "vendor/linux-x86_64 has no {prefix}* library beside libprism.so; \
             the Linux build would start without speech"
        );
    }
}

#[cfg(windows)]
#[test]
fn the_vendored_windows_library_exports_every_required_symbol() {
    // Loaded by its vendored path, not through `Api::get`, so a system-wide
    // or staged copy cannot stand in for the file that ships.
    let path = vendor_dir().join("windows-x86_64").join("prism.dll");
    // SAFETY: loading Prism runs benign initialisers; no function is called.
    let library = unsafe { libloading::Library::new(&path) }
        .unwrap_or_else(|err| panic!("{} did not load: {err}", path.display()));
    let mut missing = Vec::new();
    for name in prism_sys::REQUIRED_SYMBOLS {
        let symbol = format!("{name}\0");
        // SAFETY: the pointer is only checked for presence, never called.
        if unsafe { library.get::<*const std::ffi::c_void>(symbol.as_bytes()) }.is_err() {
            missing.push(*name);
        }
    }
    assert!(
        missing.is_empty(),
        "vendored prism.dll is missing {missing:?}; prism-sys resolves every one \
         of these and refuses to load a library without them"
    );
}

#[cfg(windows)]
#[test]
fn the_vendored_windows_library_names_the_error_codes_it_knows() {
    // The error enum grew two entries after the PortkeyDrop copy was taken
    // (INTERNAL_BACKEND_LIMIT_EXCEEDED = 19, BACKEND_ENTERED_UNDEFINED_STATE
    // = 20, per prismatoid's cdef). The vendored 0.17.3 library's string
    // table stops at 18, though: 19 and 20 read back as "Unknown error",
    // exactly like an out-of-range code. The constants stay because the
    // library can still return them; this pins what the string table knows
    // so a future DLL that names them (or renumbers) is noticed.
    let api = prism_sys::Api::get().expect("vendored prism.dll loads on Windows");
    let text_of = |code| unsafe {
        let text = (api.error_string)(code);
        assert!(!text.is_null(), "error_string({code}) returned null");
        std::ffi::CStr::from_ptr(text)
            .to_string_lossy()
            .into_owned()
    };
    assert_eq!(text_of(prism_sys::PRISM_OK), "Success");
    assert_eq!(text_of(prism_sys::PRISM_ERROR_UNKNOWN), "Unknown error");
    assert_eq!(
        text_of(prism_sys::PRISM_ERROR_INVALID_AUDIO_FORMAT),
        "Invalid audio format"
    );
    let beyond = text_of(prism_sys::PRISM_ERROR_COUNT);
    assert_eq!(beyond, "Unknown error");
    // Every code through 18 except UNKNOWN itself has its own message.
    let mut seen = std::collections::HashSet::new();
    for code in 0..=prism_sys::PRISM_ERROR_INVALID_AUDIO_FORMAT {
        let text = text_of(code);
        if code != prism_sys::PRISM_ERROR_UNKNOWN {
            assert_ne!(
                text, beyond,
                "error code {code} has no message in this library"
            );
        }
        assert!(
            seen.insert(text.clone()),
            "error code {code} repeats {text:?}"
        );
    }
    assert_eq!(
        text_of(prism_sys::PRISM_ERROR_INTERNAL_BACKEND_LIMIT_EXCEEDED),
        beyond
    );
    assert_eq!(
        text_of(prism_sys::PRISM_ERROR_BACKEND_ENTERED_UNDEFINED_STATE),
        beyond
    );
}
