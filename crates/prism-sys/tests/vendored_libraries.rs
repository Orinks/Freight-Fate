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
        // The Blazie BT Speak and BT Braille: Debian on a Raspberry Pi
        // Compute Module, so the game's first ARM64 Linux target.
        "linux-aarch64",
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
    // on its own fails to load, and the game then starts mute. The aarch64
    // wheel is laid out the same way, with its own hashes in the names.
    for platform in ["linux-x86_64", "linux-aarch64"] {
        let dir = vendor_dir().join(platform);
        for prefix in ["libspeechd-", "libglib-2-", "libgio-2-", "libgobject-2-"] {
            let present = std::fs::read_dir(&dir)
                .unwrap_or_else(|err| panic!("a {platform} vendor directory: {err}"))
                .flatten()
                .any(|entry| entry.file_name().to_string_lossy().starts_with(prefix));
            assert!(
                present,
                "vendor/{platform} has no {prefix}* library beside libprism.so; \
                 the Linux build would start without speech"
            );
        }
    }
}

#[test]
fn the_linux_libraries_are_built_for_the_architecture_their_directory_names() {
    // An ELF header's e_machine: 0x3E is x86-64, 0xB7 is AArch64. The
    // directories are filled by hand from two different wheels, and a copy
    // dropped into the wrong one would load on no machine at all.
    for (platform, machine) in [("linux-x86_64", 0x3Eu16), ("linux-aarch64", 0xB7u16)] {
        let dir = vendor_dir().join(platform);
        for entry in std::fs::read_dir(&dir)
            .unwrap_or_else(|err| panic!("a {platform} vendor directory: {err}"))
            .flatten()
        {
            let name = entry.file_name().to_string_lossy().into_owned();
            if !name.contains(".so") {
                continue;
            }
            let bytes = std::fs::read(entry.path()).expect("a readable vendored library");
            assert_eq!(
                &bytes[..4],
                b"\x7fELF",
                "vendor/{platform}/{name} is not an ELF file"
            );
            let e_machine = u16::from_le_bytes([bytes[18], bytes[19]]);
            assert_eq!(
                e_machine, machine,
                "vendor/{platform}/{name} is built for e_machine {e_machine:#x}, \
                 not this directory's"
            );
        }
    }
}

/// `DT_RUNPATH` (or the older `DT_RPATH`) of a 64-bit little-endian ELF
/// shared object, read straight from its dynamic section.
fn elf64_runpath(bytes: &[u8]) -> Option<String> {
    let u16_at = |o: usize| u16::from_le_bytes([bytes[o], bytes[o + 1]]);
    let u32_at = |o: usize| u32::from_le_bytes(bytes[o..o + 4].try_into().unwrap());
    let u64_at = |o: usize| u64::from_le_bytes(bytes[o..o + 8].try_into().unwrap());
    assert_eq!(bytes[4], 2, "not a 64-bit ELF");
    let shoff = u64_at(0x28) as usize;
    let (shentsize, shnum) = (u16_at(0x3a) as usize, u16_at(0x3c) as usize);
    let section = |i: usize| {
        let o = shoff + i * shentsize;
        // sh_type, sh_offset, sh_size, sh_link
        (
            u32_at(o + 4),
            u64_at(o + 24) as usize,
            u64_at(o + 32) as usize,
            u32_at(o + 40) as usize,
        )
    };
    let (_, dyn_off, dyn_size, strtab) = (0..shnum).map(section).find(|s| s.0 == 6)?;
    let (_, str_off, _, _) = section(strtab);
    let string_at = |o: usize| {
        let end = bytes[o..]
            .iter()
            .position(|&b| b == 0)
            .map_or(bytes.len(), |n| o + n);
        String::from_utf8_lossy(&bytes[o..end]).into_owned()
    };
    let mut rpath = None;
    for i in 0..dyn_size / 16 {
        let o = dyn_off + i * 16;
        match u64_at(o) {
            29 => return Some(string_at(str_off + u64_at(o + 8) as usize)),
            15 => rpath = Some(string_at(str_off + u64_at(o + 8) as usize)),
            _ => {}
        }
    }
    rpath
}

#[test]
fn the_linux_library_looks_beside_itself_for_its_dependencies() {
    // The wheel's libprism.so is built to find its renamed glib and
    // speech-dispatcher copies two directories up, in `prismatoid.libs`;
    // the game ships everything flat beside the executable, so the RUNPATH
    // is repointed to `$ORIGIN` when the library is vendored (patchelf).
    // A fresh copy dropped in without that step passes every other test
    // here and starts the Linux game mute.
    for platform in ["linux-x86_64", "linux-aarch64"] {
        let path = vendor_dir().join(platform).join("libprism.so");
        let bytes = std::fs::read(&path).expect("a readable vendored libprism.so");
        assert_eq!(
            elf64_runpath(&bytes).as_deref(),
            Some("$ORIGIN"),
            "vendor/{platform}/libprism.so must carry a RUNPATH of $ORIGIN"
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
    // The error enum has grown twice since the PortkeyDrop copy was taken:
    // INTERNAL_BACKEND_LIMIT_EXCEEDED (19) and BACKEND_ENTERED_UNDEFINED_STATE
    // (20), which the 0.17.3 string table did not yet name, then the three
    // library-loading codes (21..=23) that came with 0.18.2. Every code now
    // has its own message. This pins that the constants and the library's
    // string table agree, so a DLL that renumbers or grows the enum again
    // is noticed here rather than in a player's log.
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
    // Every code below COUNT except UNKNOWN itself has its own message.
    let mut seen = std::collections::HashSet::new();
    for code in 0..prism_sys::PRISM_ERROR_COUNT {
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
}
