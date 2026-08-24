//! Stage the vendored Prism shared library next to the build output.
//!
//! Prism is loaded at run time (see `src/loader.rs`), so nothing is linked
//! here. What this script does is copy the vendored shared object into the
//! Cargo target directory so `cargo run` and `cargo test` find it without the
//! developer having to touch PATH.

use std::env;
use std::fs;
use std::path::{Path, PathBuf};

/// Shared-library file name for the target platform.
fn library_file_name(target_os: &str) -> &'static str {
    match target_os {
        "windows" => "prism.dll",
        "macos" => "libprism.dylib",
        _ => "libprism.so",
    }
}

/// Vendor subdirectory holding the library for one target.
///
/// Keyed by architecture as well as OS: macOS ships separate Intel and Apple
/// silicon builds under the same file name, so a single directory cannot hold
/// both.
fn vendor_subdirectory(target_os: &str, target_arch: &str) -> String {
    format!("{target_os}-{target_arch}")
}

/// Walk up from `OUT_DIR` to the profile directory (`target/debug`), which is
/// where Cargo places binaries and where the loader looks first.
fn profile_dir(out_dir: &Path) -> Option<PathBuf> {
    // OUT_DIR is <target>/<profile>/build/<pkg>-<hash>/out
    out_dir.ancestors().nth(3).map(Path::to_path_buf)
}

fn main() {
    println!("cargo:rerun-if-changed=vendor");

    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let out_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    let target_arch = env::var("CARGO_CFG_TARGET_ARCH").unwrap_or_default();
    let file_name = library_file_name(&target_os);

    let vendor_dir = manifest_dir
        .join("vendor")
        .join(vendor_subdirectory(&target_os, &target_arch));
    let vendored = vendor_dir.join(file_name);
    println!("cargo:vendor_dir={}", vendor_dir.display());

    if !vendored.is_file() {
        // A copy staged by an earlier build, from before this platform's
        // library was dropped, is still found and loaded by the loader. That
        // cost a confusing half hour once: the tests kept crashing against a
        // library that was no longer in the tree.
        if let Some(profile_dir) = profile_dir(&out_dir) {
            let _ = fs::remove_file(profile_dir.join(file_name));
        }
        println!(
            "cargo:warning=prism-sys: {file_name} is not vendored for \
             {target_os}-{target_arch}; the app will run without speech unless the \
             library is installed system-wide"
        );
        return;
    }

    let Some(profile_dir) = profile_dir(&out_dir) else {
        return;
    };
    // Everything in the platform directory, not just the library itself: the
    // Linux build carries renamed copies of glib and speech-dispatcher that it
    // finds through a RUNPATH of `$ORIGIN`, so they have to land in the same
    // directory or it will not load at all.
    let Ok(entries) = fs::read_dir(&vendor_dir) else {
        println!(
            "cargo:warning=prism-sys: could not read {}",
            vendor_dir.display()
        );
        return;
    };
    for entry in entries.flatten() {
        let name = entry.file_name();
        let Some(name) = name.to_str() else { continue };
        // Import libraries and provenance notes are for the build and the
        // reader, not the running program.
        if name.ends_with(".lib") || name.ends_with(".txt") {
            continue;
        }
        // Copy failures are not fatal: the loader also searches the vendor
        // directory and the system library path.
        if let Err(err) = fs::copy(entry.path(), profile_dir.join(name)) {
            println!("cargo:warning=prism-sys: could not stage {name}: {err}");
        }
    }
}
