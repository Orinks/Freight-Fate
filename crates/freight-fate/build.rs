//! Stage the vendored SDL2 import library and DLL next to the build output.
//!
//! SDL2 is linked dynamically against the prebuilt libsdl-org release under
//! `vendor/sdl2/<os>-<arch>/`; building SDL from source needs a CMake/VS
//! pairing this machine does not have, and the prebuilt links in seconds.
//!
//! That is a Windows arrangement. macOS and Linux have no vendored SDL2: the
//! crate's `bundled` + `static-link` features compile it into the executable
//! (see Cargo.toml for why each platform does).
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
        // macOS and Linux are not vendored on purpose: SDL2 is compiled in
        // statically there (see Cargo.toml), so there is nothing missing and
        // nothing to warn about.
        if os != "macos" && os != "linux" {
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
