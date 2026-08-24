//! Runtime loading of the Prism shared library.
//!
//! Speech is an enhancement, not a hard dependency: a missing library must not
//! stop the application from starting. So rather than linking against an import
//! library, the symbols are resolved once on first use and cached. If any part
//! of that fails, [`Api::get`] returns `None` and the caller falls back to
//! visual-only output.

use std::path::PathBuf;
use std::sync::OnceLock;

use libloading::{Library, Symbol};

use crate::*;

/// Shared-library file name for the current platform.
pub fn library_file_name() -> &'static str {
    if cfg!(windows) {
        "prism.dll"
    } else if cfg!(target_os = "macos") {
        "libprism.dylib"
    } else {
        "libprism.so"
    }
}

/// Environment variables naming the library file explicitly, first one wins.
///
/// `FREIGHT_FATE_PRISM_PATH` is the game's; `PORTKEYDROP_PRISM_PATH` is kept
/// because these crates began life in Portkey Drop and its scripts set it.
pub const PATH_ENV_VARS: [&str; 2] = ["FREIGHT_FATE_PRISM_PATH", "PORTKEYDROP_PRISM_PATH"];

/// The vendored library directory for the platform this crate was compiled
/// for, as an absolute path into the source tree.
///
/// Only meaningful on the machine that built the binary: it lets `cargo test`
/// and `cargo run` find the library even when the build script's staging copy
/// has not landed next to the executable (test binaries live one level down,
/// in `deps/`). A shipped binary never has this directory and skips it.
pub fn vendor_dir() -> PathBuf {
    let os = if cfg!(windows) {
        "windows"
    } else if cfg!(target_os = "macos") {
        "macos"
    } else if cfg!(target_os = "linux") {
        "linux"
    } else {
        "unknown"
    };
    let arch = if cfg!(target_arch = "x86_64") {
        "x86_64"
    } else if cfg!(target_arch = "aarch64") {
        "aarch64"
    } else {
        "unknown"
    };
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("vendor")
        .join(format!("{os}-{arch}"))
}

/// Candidate locations for the library, most specific first.
///
/// Order: an explicit path from [`PATH_ENV_VARS`], the executable's directory
/// (and its parent, which is the Cargo profile directory when the executable
/// is a test binary under `deps/`), the vendored copy in the source tree, and
/// finally the bare file name so the platform loader gets a chance to find a
/// system-wide install.
fn search_paths() -> Vec<PathBuf> {
    let file_name = library_file_name();
    let mut candidates = Vec::new();

    for var in PATH_ENV_VARS {
        if let Ok(explicit) = std::env::var(var) {
            if !explicit.is_empty() {
                candidates.push(PathBuf::from(explicit));
            }
        }
    }

    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            candidates.push(dir.join(file_name));
            // Packaged macOS bundles keep native libraries beside the app
            // resources rather than next to the executable.
            candidates.push(dir.join("..").join("Frameworks").join(file_name));
            candidates.push(dir.join("lib").join(file_name));
            // Test binaries run from `target/<profile>/deps/`; the build
            // script stages the library one level up.
            if let Some(parent) = dir.parent() {
                candidates.push(parent.join(file_name));
            }
        }
    }

    candidates.push(vendor_dir().join(file_name));
    candidates.push(PathBuf::from(file_name));
    candidates
}

/// Every symbol [`Api`] resolves, in declaration order.
///
/// Kept as data so a test can ask a library file for each one by name; the
/// typed fields below are the same list with signatures attached.
pub const REQUIRED_SYMBOLS: &[&str] = &[
    "prism_config_init",
    "prism_init",
    "prism_shutdown",
    "prism_registry_count",
    "prism_registry_id_at",
    "prism_registry_id",
    "prism_registry_name",
    "prism_registry_priority",
    "prism_registry_exists",
    "prism_registry_get",
    "prism_registry_create",
    "prism_registry_create_best",
    "prism_registry_acquire",
    "prism_registry_acquire_best",
    "prism_backend_free",
    "prism_backend_get_features",
    "prism_backend_name",
    "prism_backend_initialize",
    "prism_backend_speak",
    "prism_backend_speak_to_memory",
    "prism_backend_braille",
    "prism_backend_output",
    "prism_backend_stop",
    "prism_backend_pause",
    "prism_backend_resume",
    "prism_backend_is_speaking",
    "prism_backend_set_volume",
    "prism_backend_get_volume",
    "prism_backend_set_rate",
    "prism_backend_get_rate",
    "prism_backend_set_pitch",
    "prism_backend_get_pitch",
    "prism_backend_refresh_voices",
    "prism_backend_count_voices",
    "prism_backend_get_voice_name",
    "prism_backend_get_voice_language",
    "prism_backend_set_voice",
    "prism_backend_get_voice",
    "prism_backend_get_channels",
    "prism_backend_get_sample_rate",
    "prism_backend_get_bit_depth",
    "prism_error_string",
];

/// Resolved Prism entry points.
///
/// The whole public surface of prismatoid's cffi `cdef` is resolved, and every
/// symbol is required: the vendored binaries all carry all of them, and a
/// system install old enough to lack one would also lack `registry_priority`,
/// without which the game cannot choose a backend at all.
pub struct Api {
    _library: Library,

    pub config_init: FnConfigInit,
    pub init: FnInit,
    pub shutdown: FnShutdown,

    pub registry_count: FnRegistryCount,
    pub registry_id_at: FnRegistryIdAt,
    pub registry_id: FnRegistryId,
    pub registry_name: FnRegistryName,
    pub registry_priority: FnRegistryPriority,
    pub registry_exists: FnRegistryExists,
    /// Cached instance only; null when none is live.
    pub registry_get: FnRegistryAcquire,
    /// A fresh instance every call, never cached.
    pub registry_create: FnRegistryAcquire,
    pub registry_create_best: FnRegistryAcquireBest,
    /// Cached instance, created on first call.
    pub registry_acquire: FnRegistryAcquire,
    pub registry_acquire_best: FnRegistryAcquireBest,

    pub backend_free: FnBackendFree,
    pub backend_get_features: FnBackendFeatures,
    pub backend_name: FnBackendName,
    pub backend_initialize: FnBackendInitialize,
    pub backend_speak: FnBackendSpeak,
    pub backend_speak_to_memory: FnBackendSpeakToMemory,
    pub backend_braille: FnBackendBraille,
    pub backend_output: FnBackendSpeak,
    pub backend_stop: FnBackendVoid,
    pub backend_pause: FnBackendVoid,
    pub backend_resume: FnBackendVoid,
    pub backend_is_speaking: FnBackendGetBool,
    pub backend_set_volume: FnBackendSetF32,
    pub backend_get_volume: FnBackendGetF32,
    pub backend_set_rate: FnBackendSetF32,
    pub backend_get_rate: FnBackendGetF32,
    pub backend_set_pitch: FnBackendSetF32,
    pub backend_get_pitch: FnBackendGetF32,
    pub backend_refresh_voices: FnBackendVoid,
    pub backend_count_voices: FnBackendGetUsize,
    pub backend_get_voice_name: FnBackendGetIndexedStr,
    pub backend_get_voice_language: FnBackendGetIndexedStr,
    pub backend_set_voice: FnBackendSetUsize,
    pub backend_get_voice: FnBackendGetUsize,
    pub backend_get_channels: FnBackendGetUsize,
    pub backend_get_sample_rate: FnBackendGetUsize,
    pub backend_get_bit_depth: FnBackendGetUsize,

    pub error_string: FnErrorString,
}

// The library and its function pointers stay alive for the process lifetime and
// Prism guards its own internal state, so the resolved table is shareable.
unsafe impl Send for Api {}
unsafe impl Sync for Api {}

/// Resolve one symbol, logging and bailing out if it is absent.
///
/// # Safety
/// The caller must give a `T` matching the symbol's real C signature.
unsafe fn symbol<T: Copy>(library: &Library, name: &[u8]) -> Option<T> {
    match library.get::<T>(name) {
        Ok(found) => Some(*Symbol::into_raw(found)),
        Err(err) => {
            log::warn!(
                "prism: missing symbol {}: {err}",
                String::from_utf8_lossy(&name[..name.len().saturating_sub(1)])
            );
            None
        }
    }
}

impl Api {
    /// Load and cache the Prism API, or `None` when it is unavailable.
    ///
    /// The first call does the work; later calls return the cached result,
    /// including a cached failure — a missing library is not retried.
    pub fn get() -> Option<&'static Api> {
        static API: OnceLock<Option<Api>> = OnceLock::new();
        API.get_or_init(Api::load).as_ref()
    }

    fn load() -> Option<Api> {
        for candidate in search_paths() {
            // SAFETY: loading a shared library runs its initialisers. Prism's
            // are benign, and the candidate paths are app-controlled.
            match unsafe { Library::new(&candidate) } {
                Ok(library) => match unsafe { Api::resolve(library) } {
                    Some(api) => {
                        log::info!("prism: loaded from {}", candidate.display());
                        return Some(api);
                    }
                    None => {
                        log::warn!(
                            "prism: {} loaded but is missing required symbols",
                            candidate.display()
                        );
                    }
                },
                Err(err) => {
                    log::debug!("prism: {} not loadable: {err}", candidate.display());
                }
            }
        }
        log::info!("prism: library not found; speech output is unavailable");
        None
    }

    /// # Safety
    /// Every signature below must match the C header exactly.
    unsafe fn resolve(library: Library) -> Option<Api> {
        Some(Api {
            config_init: symbol(&library, b"prism_config_init\0")?,
            init: symbol(&library, b"prism_init\0")?,
            shutdown: symbol(&library, b"prism_shutdown\0")?,

            registry_count: symbol(&library, b"prism_registry_count\0")?,
            registry_id_at: symbol(&library, b"prism_registry_id_at\0")?,
            registry_id: symbol(&library, b"prism_registry_id\0")?,
            registry_name: symbol(&library, b"prism_registry_name\0")?,
            registry_priority: symbol(&library, b"prism_registry_priority\0")?,
            registry_exists: symbol(&library, b"prism_registry_exists\0")?,
            registry_get: symbol(&library, b"prism_registry_get\0")?,
            registry_create: symbol(&library, b"prism_registry_create\0")?,
            registry_create_best: symbol(&library, b"prism_registry_create_best\0")?,
            registry_acquire: symbol(&library, b"prism_registry_acquire\0")?,
            registry_acquire_best: symbol(&library, b"prism_registry_acquire_best\0")?,

            backend_free: symbol(&library, b"prism_backend_free\0")?,
            backend_get_features: symbol(&library, b"prism_backend_get_features\0")?,
            backend_name: symbol(&library, b"prism_backend_name\0")?,
            backend_initialize: symbol(&library, b"prism_backend_initialize\0")?,
            backend_speak: symbol(&library, b"prism_backend_speak\0")?,
            backend_speak_to_memory: symbol(&library, b"prism_backend_speak_to_memory\0")?,
            backend_braille: symbol(&library, b"prism_backend_braille\0")?,
            backend_output: symbol(&library, b"prism_backend_output\0")?,
            backend_stop: symbol(&library, b"prism_backend_stop\0")?,
            backend_pause: symbol(&library, b"prism_backend_pause\0")?,
            backend_resume: symbol(&library, b"prism_backend_resume\0")?,
            backend_is_speaking: symbol(&library, b"prism_backend_is_speaking\0")?,
            backend_set_volume: symbol(&library, b"prism_backend_set_volume\0")?,
            backend_get_volume: symbol(&library, b"prism_backend_get_volume\0")?,
            backend_set_rate: symbol(&library, b"prism_backend_set_rate\0")?,
            backend_get_rate: symbol(&library, b"prism_backend_get_rate\0")?,
            backend_set_pitch: symbol(&library, b"prism_backend_set_pitch\0")?,
            backend_get_pitch: symbol(&library, b"prism_backend_get_pitch\0")?,
            backend_refresh_voices: symbol(&library, b"prism_backend_refresh_voices\0")?,
            backend_count_voices: symbol(&library, b"prism_backend_count_voices\0")?,
            backend_get_voice_name: symbol(&library, b"prism_backend_get_voice_name\0")?,
            backend_get_voice_language: symbol(&library, b"prism_backend_get_voice_language\0")?,
            backend_set_voice: symbol(&library, b"prism_backend_set_voice\0")?,
            backend_get_voice: symbol(&library, b"prism_backend_get_voice\0")?,
            backend_get_channels: symbol(&library, b"prism_backend_get_channels\0")?,
            backend_get_sample_rate: symbol(&library, b"prism_backend_get_sample_rate\0")?,
            backend_get_bit_depth: symbol(&library, b"prism_backend_get_bit_depth\0")?,

            error_string: symbol(&library, b"prism_error_string\0")?,

            _library: library,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn search_paths_end_with_bare_library_name() {
        let paths = search_paths();
        let last = paths.last().expect("at least one candidate");
        assert_eq!(last, &PathBuf::from(library_file_name()));
    }

    #[test]
    fn search_paths_honour_the_override_env_vars() {
        // Both variables are read per call, so setting them here is enough;
        // the game's own variable outranks the Portkey Drop one. The env-var
        // tests share a lock so they cannot see each other's values.
        let _guard = env_lock();
        std::env::set_var("FREIGHT_FATE_PRISM_PATH", "/tmp/ff-prism-lib");
        std::env::set_var("PORTKEYDROP_PRISM_PATH", "/tmp/custom-prism-lib");
        let paths = search_paths();
        std::env::remove_var("FREIGHT_FATE_PRISM_PATH");
        std::env::remove_var("PORTKEYDROP_PRISM_PATH");
        assert_eq!(paths.first(), Some(&PathBuf::from("/tmp/ff-prism-lib")));
        assert_eq!(paths.get(1), Some(&PathBuf::from("/tmp/custom-prism-lib")));
    }

    #[test]
    fn an_empty_override_is_ignored() {
        let _guard = env_lock();
        std::env::set_var("FREIGHT_FATE_PRISM_PATH", "");
        let paths = search_paths();
        std::env::remove_var("FREIGHT_FATE_PRISM_PATH");
        assert!(!paths.iter().any(|p| p.as_os_str().is_empty()));
    }

    #[test]
    fn the_vendored_copy_is_searched_before_the_system() {
        let paths = search_paths();
        let vendored = vendor_dir().join(library_file_name());
        let position = paths
            .iter()
            .position(|p| p == &vendored)
            .expect("vendor dir is a candidate");
        assert_eq!(position, paths.len() - 2);
    }

    #[test]
    fn required_symbols_has_no_duplicates() {
        let mut sorted = REQUIRED_SYMBOLS.to_vec();
        sorted.sort_unstable();
        sorted.dedup();
        assert_eq!(sorted.len(), REQUIRED_SYMBOLS.len());
        assert!(REQUIRED_SYMBOLS
            .iter()
            .all(|name| name.starts_with("prism_")));
    }

    #[test]
    fn loading_is_cached_and_never_panics() {
        // Whether or not Prism is present, two calls must agree and neither
        // may panic.
        let first = Api::get().is_some();
        let second = Api::get().is_some();
        assert_eq!(first, second);
    }

    #[cfg(windows)]
    #[test]
    fn the_vendored_windows_library_loads_with_every_symbol() {
        // `Api::get` is `Some` only when every required symbol resolved, and
        // on Windows the vendored DLL is always a candidate.
        assert!(
            Api::get().is_some(),
            "vendored prism.dll did not load or is missing a required symbol"
        );
    }

    fn env_lock() -> std::sync::MutexGuard<'static, ()> {
        static LOCK: OnceLock<std::sync::Mutex<()>> = OnceLock::new();
        LOCK.get_or_init(|| std::sync::Mutex::new(()))
            .lock()
            .unwrap_or_else(|err| err.into_inner())
    }
}
