//! Stage the vendored SDL2 import library and DLL next to the build output.
//!
//! SDL2 is linked dynamically against the prebuilt libsdl-org release under
//! `vendor/sdl2/<os>-<arch>/`; building SDL from source needs a CMake/VS
//! pairing this machine does not have, and the prebuilt links in seconds.
//!
//! That is a Windows arrangement. macOS has no vendored SDL2: it installs
//! `sdl2` from Homebrew, and the crate's `use-pkgconfig` feature finds it.
use std::{env, fs, path::PathBuf};

fn main() {
    let manifest = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let root = manifest.ancestors().nth(2).unwrap().to_path_buf();
    let os = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    let arch = env::var("CARGO_CFG_TARGET_ARCH").unwrap_or_default();
    let dir = root
        .join("vendor")
        .join("sdl2")
        .join(format!("{os}-{arch}"));
    println!("cargo:rerun-if-changed={}", dir.display());
    if !dir.is_dir() {
        // macOS is not vendored on purpose: SDL2 comes from Homebrew and the
        // `use-pkgconfig` feature (see Cargo.toml) tells the linker where it
        // lives, so there is nothing missing and nothing to warn about.
        if os != "macos" {
            println!("cargo:warning=freight-fate: no vendored SDL2 for {os}-{arch} under vendor/sdl2; expecting a system SDL2");
        }
        return;
    }
    println!("cargo:rustc-link-search=native={}", dir.display());
    let out = PathBuf::from(env::var("OUT_DIR").unwrap());
    if let Some(profile) = out.ancestors().nth(3) {
        for entry in fs::read_dir(&dir).into_iter().flatten().flatten() {
            let p = entry.path();
            let ext = p.extension().and_then(|e| e.to_str()).unwrap_or("");
            if matches!(ext, "dll" | "so" | "dylib") {
                let _ = fs::copy(&p, profile.join(p.file_name().unwrap()));
            }
        }
    }
}
