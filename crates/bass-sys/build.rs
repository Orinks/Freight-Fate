//! Stage the fetched BASS shared libraries next to the build output.
//!
//! BASS is un4seen's and proprietary, so it is NOT committed to this public
//! repository: `tools/fetch_bass.py` puts it under `vendor/<os>-<arch>/`,
//! pinned by sha256, and this script stages it from there.
//!
//! BASS is loaded at run time (see `src/loader.rs`), so nothing is linked
//! here. What this script does is copy the fetched `bass.dll` and its add-on
//! plugins (`bassopus`, `bassflac`, `bass_aac`, `basshls`) into the Cargo
//! target directory so `cargo run` and `cargo test` find them without the
//! developer having to touch PATH. The plugins land beside the core library
//! because that is the directory `safe::load_plugins_from` is pointed at.

use std::env;
use std::fs;
use std::path::{Path, PathBuf};

/// Shared-library file name for the target platform.
fn library_file_name(target_os: &str) -> &'static str {
    match target_os {
        "windows" => "bass.dll",
        "macos" => "libbass.dylib",
        _ => "libbass.so",
    }
}

/// Vendor subdirectory holding the libraries for one target.
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
        // library was dropped, would still be found and loaded by the loader.
        if let Some(profile_dir) = profile_dir(&out_dir) {
            let _ = fs::remove_file(profile_dir.join(file_name));
        }
        // A developer who has not run the fetch gets a silent game and no
        // obvious reason why, which is the worst way to learn that BASS is
        // not in the repository. Name the command in the warning.
        println!(
            "cargo:warning=bass-sys: {file_name} is missing for \
             {target_os}-{target_arch}. Run `uv run python tools/fetch_bass.py` \
             -- BASS is fetched, not committed. Until then the game runs without \
             audio unless the library is installed system-wide."
        );
        return;
    }

    let Some(profile_dir) = profile_dir(&out_dir) else {
        return;
    };
    // Everything in the platform directory, not just the core library: the
    // add-on plugins have to sit beside bass.dll so one directory scan finds
    // them all, and on Linux they resolve libbass.so through the loader's
    // search path, which includes the directory they were loaded from.
    let Ok(entries) = fs::read_dir(&vendor_dir) else {
        println!(
            "cargo:warning=bass-sys: could not read {}",
            vendor_dir.display()
        );
        return;
    };
    for entry in entries.flatten() {
        let name = entry.file_name();
        let Some(name) = name.to_str() else { continue };
        // Import libraries, headers and licence notes are for the build and
        // the reader, not the running program.
        if name.ends_with(".lib")
            || name.ends_with(".txt")
            || name.ends_with(".md")
            || name.ends_with(".h")
        {
            continue;
        }
        // Copy failures are not fatal: the loader also searches the vendor
        // directory and the system library path.
        if let Err(err) = fs::copy(entry.path(), profile_dir.join(name)) {
            println!("cargo:warning=bass-sys: could not stage {name}: {err}");
        }
    }
}
