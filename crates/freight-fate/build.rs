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
    delay_load_prism_backends();
    link_prism_system_libraries();
    build_ios_bridge();
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
        if os != "macos" && os != "linux" && os != "ios" {
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

/// Delay-load the DLLs behind Prism's Windows backends (NVDA, JAWS, ...).
///
/// prismer links Prism statically and publishes the list, but a link flag
/// only takes effect on the final link, which happens here. Without it every
/// screen reader client DLL becomes a hard import and the game will not start
/// on a machine missing any of them.
fn delay_load_prism_backends() {
    println!("cargo:rerun-if-env-changed=DEP_PRISMER_DELAY_LOAD_DLLS");
    if env::var("CARGO_CFG_TARGET_ENV").as_deref() != Ok("msvc") {
        return;
    }
    let Ok(dlls) = env::var("DEP_PRISMER_DELAY_LOAD_DLLS") else {
        return;
    };
    for dll in dlls.split(';').filter(|dll| !dll.is_empty()) {
        println!("cargo:rustc-link-arg=/DELAYLOAD:{dll}");
    }
}

/// Link what Prism's macOS and Linux backends import.
///
/// prism-sys names these for Windows only, and a static library leaves them
/// to the final link. macOS: the frameworks its CMake links (AVSpeech,
/// VoiceOver, power management). Linux: whichever of speech-dispatcher and
/// glibmm and giomm (Orca) pkg-config finds -- the same test Prism's CMake used to
/// decide whether to build those backends at all.
fn link_prism_system_libraries() {
    let os = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    if os == "linux" || os == "macos" || os == "ios" {
        // Each backend registers itself from a static initializer in its own
        // object, which nothing references, so a plain static link drops
        // every one and Prism starts with an empty registry. Prism anchors
        // them for MSVC only (`/include:`); GCC and Clang need the whole
        // archive. `-bundle` defers this to the final link, where prism-sys's
        // search path finds libprism.a.
        println!("cargo:rustc-link-lib=static:+whole-archive,-bundle=prism");
    }
    match env::var("CARGO_CFG_TARGET_OS").as_deref() {
        Ok("macos") => {
            for framework in [
                "Foundation",
                "AVFoundation",
                "AppKit",
                "IOKit",
                "CoreFoundation",
            ] {
                println!("cargo:rustc-link-lib=framework={framework}");
            }
            println!("cargo:rustc-link-lib=objc");
        }
        Ok("ios") => {
            // Prism (VoiceOver announcements, AVSpeech) and the SDL2 UIKit
            // backend compiled in by sdl2-sys, whose static link names only
            // the macOS frameworks.
            for framework in [
                "Foundation",
                "UIKit",
                "AVFoundation",
                "AudioToolbox",
                "CoreAudio",
                "CoreBluetooth",
                "CoreFoundation",
                "CoreGraphics",
                "CoreHaptics",
                "CoreMotion",
                "GameController",
                "Metal",
                "OpenGLES",
                "QuartzCore",
                "Security",
            ] {
                println!("cargo:rustc-link-lib=framework={framework}");
            }
            println!("cargo:rustc-link-lib=objc");
            println!("cargo:rustc-link-lib=iconv");
            println!("cargo:rustc-link-lib=c++");
            // BASS and its add-ons ship as embedded frameworks in the app's
            // own Frameworks folder.
            println!("cargo:rustc-link-arg=-Wl,-rpath,@executable_path/Frameworks");
            link_clang_runtime();
        }
        Ok("linux") => {
            link_libstdcxx_statically();
            for module in ["speech-dispatcher", "glibmm-2.68", "giomm-2.68"] {
                let Ok(out) = std::process::Command::new("pkg-config")
                    .args(["--libs", module])
                    .output()
                else {
                    continue;
                };
                if !out.status.success() {
                    continue;
                }
                for flag in String::from_utf8_lossy(&out.stdout).split_whitespace() {
                    if let Some(dir) = flag.strip_prefix("-L") {
                        println!("cargo:rustc-link-search=native={dir}");
                    } else if let Some(lib) = flag.strip_prefix("-l") {
                        println!("cargo:rustc-link-lib={lib}");
                    }
                }
            }
        }
        _ => {}
    }
}

/// Make prism-sys's `-lstdc++` resolve to the compiler's static archive.
///
/// Prism needs a newer libstdc++ than the oldest distribution the Linux
/// build supports ships, so it is linked in rather than required of the
/// player's system. prism-sys asks for plain `stdc++`; the linker takes the
/// first search directory holding any libstdc++, and this one holds only the
/// archive.
fn link_libstdcxx_statically() {
    println!("cargo:rerun-if-env-changed=CXX");
    let cxx = env::var("CXX").unwrap_or_else(|_| "c++".to_string());
    let Ok(out) = std::process::Command::new(&cxx)
        .arg("-print-file-name=libstdc++.a")
        .output()
    else {
        return;
    };
    // gcc echoes the bare name back when it has no such file.
    let archive = PathBuf::from(String::from_utf8_lossy(&out.stdout).trim());
    if !archive.is_absolute() {
        println!(
            "cargo:warning=freight-fate: {cxx} has no libstdc++.a; linking libstdc++ dynamically"
        );
        return;
    }
    let dir = PathBuf::from(env::var("OUT_DIR").unwrap()).join("static-libstdcxx");
    if fs::create_dir_all(&dir).is_ok() && fs::copy(&archive, dir.join("libstdc++.a")).is_ok() {
        println!("cargo:rustc-link-search=native={}", dir.display());
    }
}

/// Compile the UIKit gesture and VoiceOver bridge (`ios/ff_touch.m`).
///
/// It is the one piece of the iOS port that has to be Objective-C: a view
/// over SDL's own, carrying the gesture recognizers and the accessibility
/// element VoiceOver focuses. Everything it sees is queued as a plain gesture
/// code that `touch` turns into the same key events the desktop game reads.
fn build_ios_bridge() {
    let source = "ios/ff_touch.m";
    println!("cargo:rerun-if-changed={source}");
    if env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("ios") {
        return;
    }
    cc::Build::new()
        .file(source)
        .flag("-fobjc-arc")
        .flag("-fmodules")
        .compile("ff_touch");
}

/// Link clang's own runtime for iOS. SDL2's and Prism's `@available` checks
/// compile to `__isPlatformVersionAtLeast`, which lives there, and rustc links
/// with `-nodefaultlibs`, so clang does not add it by itself.
fn link_clang_runtime() {
    let simulator = env::var("CARGO_CFG_TARGET_ABI").as_deref() == Ok("sim");
    let Ok(output) = std::process::Command::new("xcrun")
        .args(["clang", "-print-resource-dir"])
        .output()
    else {
        println!("cargo:warning=freight-fate: xcrun clang not found; not linking clang_rt");
        return;
    };
    let resource_dir = String::from_utf8_lossy(&output.stdout).trim().to_string();
    // A fat archive, which rustc cannot bundle into the rlib, so it goes to
    // the final link directly.
    println!(
        "cargo:rustc-link-arg={resource_dir}/lib/darwin/libclang_rt.{}.a",
        if simulator { "iossim" } else { "ios" }
    );
}
